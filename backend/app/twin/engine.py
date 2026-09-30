"""Digital twin engine for a single robot.

Maintains the state estimate via predict-then-correct logic.
"""
from __future__ import annotations

import collections
import math
from typing import Optional

from app.contract.schemas import Mission, RobotType, StateVec, Telemetry, TwinSnapshot, TwinState, TwinMode
from app.contract.physics import (
    DROPOUT_TIMEOUT_S, GATE_M, SYNC_TOL_M, SYNC_WINDOW,
    expected_current, expected_drain_pct_per_s, expected_temp_step, expected_vibration
)
from app.sim.models import Command, make_model
from app.sim.control import follow

_NOMINAL = {
    "speed": 2.0,
    "battery": 100.0,
    "motor_temp": 50.0,
    "current": 5.0,
    "vibration": 0.5,
}

def _angle_diff(a: float, b: float) -> float:
    d = (a - b) % (2 * math.pi)
    if d > math.pi:
        d -= 2 * math.pi
    return d

class TwinEngine:
    def __init__(self, robot_id: str, robot_type: RobotType):
        self.robot_id = robot_id
        self.robot_type = robot_type
        self.model = make_model(robot_type)
        
        # Internal state
        self.est: Optional[StateVec] = None
        self.est_ts: float = 0.0
        self.last_packet_ts: float = 0.0
        
        self.mission: Optional[Mission] = None
        self.wp_idx: int = 0
        
        self.mode: TwinMode = "synced"
        self.rmse_buffer: collections.deque = collections.deque(maxlen=SYNC_WINDOW)
        self.last_sync_score: float = 100.0
        
        # We need an initial state to start predicting if we don't have one?
        # Typically the first telemetry packet will initialize it.

    def set_mission(self, m: Mission | None) -> None:
        self.mission = m
        self.wp_idx = 0

    def _predict(self, dt: float) -> StateVec:
        if not self.est:
            # Fallback if predicting before any telemetry (should not happen in normal flow)
            return StateVec(x=0, y=0, z=0, heading=0, speed=0, battery=100, motor_temp=30, current=0, vibration=0)
            
        cmd = Command(speed=0.0, yaw_rate=0.0)
        if self.mission:
            cmd, self.wp_idx, _ = follow(
                self.est, self.mission.waypoints, self.wp_idx,
                self.mission.cruise_speed, self.robot_type
            )
            # Wear is 0 for the twin's prediction
        pred = self.model.step(self.est, cmd, dt, wear=0.0)
        
        # Override physics with the ideal twin predictions if they differ from kinematic step
        # Note: the model.step uses expected_ formulas, but we'll enforce them just in case.
        return pred

    def _update_sync_score(self, residual_pos: float, confidence: float) -> float:
        self.rmse_buffer.append(residual_pos ** 2)
        mse = sum(self.rmse_buffer) / len(self.rmse_buffer)
        rmse = math.sqrt(mse)
        
        # sync_score: 100 * clamp(1 - rmse_pos / SYNC_TOL_M, 0, 1)
        score = 100.0 * max(0.0, min(1.0, 1.0 - rmse / SYNC_TOL_M))
        
        if self.mode == "dead_reckoning":
            score = min(score, 100.0 * confidence)
            
        self.last_sync_score = score
        return score

    def _get_path_errors(self, s: StateVec) -> tuple[float, float, Optional[float], Optional[float]]:
        if not self.mission or not self.mission.waypoints:
            return 0.0, 0.0, None, None
            
        n = len(self.mission.waypoints)
        idx = self.wp_idx % n
        target = self.mission.waypoints[idx]
        
        # Find previous waypoint
        if n == 1:
            prev = target
        else:
            prev = self.mission.waypoints[(idx - 1) % n]
            
        # Segment vector
        dx = target.x - prev.x
        dy = target.y - prev.y
        seg_len = math.hypot(dx, dy)
        
        if seg_len < 1e-6:
            return math.hypot(s.x - target.x, s.y - target.y), 0.0, target.x, target.y
            
        # Unit vector
        ux = dx / seg_len
        uy = dy / seg_len
        
        # Vector from prev to robot
        rx = s.x - prev.x
        ry = s.y - prev.y
        
        # Projection of robot onto segment
        proj = rx * ux + ry * uy
        
        # Plan position
        plan_x = prev.x + ux * max(0.0, min(seg_len, proj))
        plan_y = prev.y + uy * max(0.0, min(seg_len, proj))
        
        # Cross track error
        cross_track_err = math.hypot(s.x - plan_x, s.y - plan_y)
        
        # Heading error
        seg_heading = math.atan2(dy, dx)
        heading_err = _angle_diff(s.heading, seg_heading)
        
        return cross_track_err, heading_err, plan_x, plan_y

    def on_telemetry(self, tel: Telemetry) -> TwinState:
        # Initialize if first packet
        if not self.est:
            self.est = StateVec(
                x=tel.x, y=tel.y, z=tel.z, heading=tel.heading,
                speed=tel.speed, battery=tel.battery, motor_temp=tel.motor_temp,
                current=tel.current, vibration=tel.vibration
            )
            self.est_ts = tel.ts
            self.last_packet_ts = tel.ts
            self.mode = "synced"
            
        dt = tel.ts - self.est_ts
        if dt < 0:
            dt = 0.0  # Should not happen
            
        # 1. Predict
        pred = self._predict(dt)
        
        # 2. Residuals
        residual_pos = math.hypot(tel.x - pred.x, tel.y - pred.y)
        
        # Normalized residual (multi-channel)
        norm_r = 0.0
        norm_r += (residual_pos / SYNC_TOL_M)**2
        norm_r += ((tel.speed - pred.speed) / _NOMINAL["speed"])**2
        norm_r += ((tel.battery - pred.battery) / _NOMINAL["battery"])**2
        residual_norm = math.sqrt(norm_r)
        
        # 3. Correct (gain)
        gain = 0.6 if residual_pos <= GATE_M else 0.1
        
        def _blend(p, o, g): return p + g * (o - p)
        
        self.est = StateVec(
            x=_blend(pred.x, tel.x, gain),
            y=_blend(pred.y, tel.y, gain),
            z=_blend(pred.z, tel.z, gain),
            heading=pred.heading + gain * _angle_diff(tel.heading, pred.heading),
            speed=_blend(pred.speed, tel.speed, gain),
            battery=_blend(pred.battery, tel.battery, gain),
            motor_temp=_blend(pred.motor_temp, tel.motor_temp, gain),
            current=_blend(pred.current, tel.current, gain),
            vibration=_blend(pred.vibration, tel.vibration, gain)
        )
        self.est_ts = tel.ts
        self.last_packet_ts = tel.ts
        
        self.mode = "synced"
        confidence = 1.0
        sync_score = self._update_sync_score(residual_pos, confidence)
        
        cte, he, px, py = self._get_path_errors(self.est)
        
        return TwinState(
            robot_id=self.robot_id,
            ts=tel.ts,
            mode=self.mode,
            pred=pred,
            est=self.est,
            residual_pos=residual_pos,
            residual_norm=residual_norm,
            cross_track_err=cte,
            heading_err=he,
            plan_x=px,
            plan_y=py,
            sync_score=sync_score,
            confidence=confidence,
            since_last_packet_s=0.0
        )

    def tick(self, now: float) -> TwinState | None:
        if not self.est:
            return None
            
        dt = now - self.est_ts
        if dt <= 0.001:
            # We already updated at this timestamp via on_telemetry
            return None
            
        since_last = now - self.last_packet_ts
        
        if since_last > DROPOUT_TIMEOUT_S:
            self.mode = "dead_reckoning"
            
        if self.mode == "dead_reckoning":
            # In dead reckoning, the estimate IS the prediction
            pred = self._predict(dt)
            self.est = pred
            self.est_ts = now
            
            confidence = math.exp(-since_last / 8.0)
            
            # Use last calculated residual pos for sync score decay
            last_res = math.sqrt(sum(self.rmse_buffer) / max(1, len(self.rmse_buffer))) if self.rmse_buffer else 0.0
            sync_score = self._update_sync_score(last_res, confidence)
            
            cte, he, px, py = self._get_path_errors(self.est)
            
            return TwinState(
                robot_id=self.robot_id,
                ts=now,
                mode=self.mode,
                pred=pred,
                est=self.est,
                residual_pos=0.0,
                residual_norm=0.0,
                cross_track_err=cte,
                heading_err=he,
                plan_x=px,
                plan_y=py,
                sync_score=sync_score,
                confidence=confidence,
                since_last_packet_s=since_last
            )
            
        return None

    def snapshot(self) -> TwinSnapshot:
        return TwinSnapshot(
            robot_id=self.robot_id,
            robot_type=self.robot_type,
            ts=self.est_ts,
            est=self.est.model_copy() if self.est else StateVec(x=0, y=0, heading=0, speed=0, battery=100, motor_temp=30, current=0, vibration=0),
            mission=self.mission,
            waypoint_idx=self.wp_idx
        )
