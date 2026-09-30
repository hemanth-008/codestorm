"""Tests for twin/engine.py."""
from __future__ import annotations

import math

from app.contract.schemas import Mission, Telemetry, Waypoint
from app.twin.engine import TwinEngine


def _dummy_tel(ts: float, x: float = 10.0, y: float = 10.0) -> Telemetry:
    return Telemetry(
        robot_id="R1", robot_type="rover", ts=ts, seq=int(ts*5),
        x=x, y=y, z=0.0, heading=0.0, speed=1.5,
        battery=100.0, motor_temp=30.0, current=2.0, vibration=0.1
    )


class TestTwinEngine:
    def test_clean_run(self):
        engine = TwinEngine("R1", "rover")
        engine.set_mission(Mission(
            mission_id="m1", robot_id="R1",
            waypoints=[Waypoint(x=100, y=10)], cruise_speed=1.5
        ))
        
        # Feed clean telemetry
        x, y = 10.0, 10.0
        ts = 0.0
        for _ in range(50):
            ts += 0.2
            x += 1.5 * 0.2
            tel = _dummy_tel(ts, x=x, y=y)
            state = engine.on_telemetry(tel)
            
        assert state.sync_score > 90.0
        assert state.mode == "synced"

    def test_dropout(self):
        engine = TwinEngine("R1", "rover")
        # 1 packet to init
        engine.on_telemetry(_dummy_tel(0.0, x=10.0, y=10.0))
        
        # 5 seconds dropout
        state = engine.tick(5.0)
        assert state is not None
        assert state.mode == "dead_reckoning"
        assert state.confidence < 1.0
        # Position error against original 10.0 shouldn't be massive but it's dead reckoning
        
        # Recover
        tel_recover = _dummy_tel(5.2, x=10.0 + 1.5*5.2, y=10.0)
        state2 = engine.on_telemetry(tel_recover)
        assert state2.mode == "synced"

    def test_jump_does_not_drag_estimate(self):
        engine = TwinEngine("R1", "rover")
        
        # Feed clean telemetry to establish sync
        x, y = 10.0, 10.0
        ts = 0.0
        for _ in range(10):
            ts += 0.2
            x += 1.5 * 0.2
            engine.on_telemetry(_dummy_tel(ts, x=x, y=y))
            
        # Spoofed jump of 20m
        jump_tel = _dummy_tel(ts + 0.2, x=x + 20.0, y=y)
        state = engine.on_telemetry(jump_tel)
        
        # The observed is 20m away. The estimator should use GATE_M and drop gain to 0.1
        # The estimate shouldn't just jump 20m, but 0.1 * 20m = 2m
        # Wait, the prediction would have been around `x + 1.5*0.2`.
        # So estimate x should be around prediction x + 2m.
        dist_from_jump = math.hypot(jump_tel.x - state.est.x, jump_tel.y - state.est.y)
        assert dist_from_jump > 15.0  # Means it didn't drag to the jump
        assert state.residual_pos > 15.0
