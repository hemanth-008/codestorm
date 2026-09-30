"""Forkable mission simulation with the contract safety gate."""
from __future__ import annotations

import math
from typing import Any

from app.contract.physics import ARENA_M, DT, LIMITS, clamp, expected_current, expected_drain_pct_per_s, expected_temp_step, expected_vibration
from app.contract.schemas import HealthReport, Mission, SimResult, StateVec, TwinSnapshot

try:  # Lane A is present after integration; keep B5 independently testable.
    from app.sim.control import follow as _lane_a_follow
    from app.sim.models import make_model as _lane_a_make_model
except ImportError:  # pragma: no cover - exercised in the pre-merge lane tree
    _lane_a_follow = None
    _lane_a_make_model = None


SIM_DT = 0.5
MAX_SIM_SECONDS = 600.0


def simulate_mission(
    snap: TwinSnapshot,
    mission: Mission,
    health: HealthReport | None = None,
) -> SimResult:
    """Simulate a mission from a copied snapshot and evaluate deployment safety.

    Each step advances by ``SIM_DT`` seconds.  The returned path is sampled to
    at most 200 points, and ``safe_to_deploy`` is false whenever the path leaves
    the arena, end battery is below 15%, RUL is shorter than ETA, or speed/
    acceleration exceed the robot limits.
    """
    if mission.robot_id != snap.robot_id:
        return SimResult(
            mission_id=mission.mission_id,
            robot_id=mission.robot_id,
            eta_s=0.0,
            end_battery=snap.est.battery,
            risk=1.0,
            path=[(snap.est.x, snap.est.y)],
            violations=["mission robot does not match snapshot"],
            safe_to_deploy=False,
            notes="Mission robot_id must match the selected twin snapshot.",
        )

    current = snap.est.model_copy(deep=True) if hasattr(snap.est, "model_copy") else snap.est.copy(deep=True)
    model = _lane_a_make_model(snap.robot_type) if _lane_a_make_model is not None else _FallbackModel(snap.robot_type)
    waypoint_idx = snap.waypoint_idx
    path: list[tuple[float, float]] = [(current.x, current.y)]
    violations: list[str] = []
    elapsed = 0.0
    done = not mission.waypoints
    steps = 0

    while not done and elapsed < MAX_SIM_SECONDS:
        if _lane_a_follow is not None:
            command, waypoint_idx, done = _lane_a_follow(
                current,
                mission.waypoints,
                waypoint_idx,
                mission.cruise_speed,
                snap.robot_type,
            )
        else:
            command, waypoint_idx, done = _fallback_follow(
                current,
                mission.waypoints,
                waypoint_idx,
                mission.cruise_speed,
                snap.robot_type,
            )
        previous_speed = current.speed
        current = model.step(current, command, SIM_DT, wear=0.0)
        elapsed += SIM_DT
        steps += 1
        path.append((current.x, current.y))
        limits = LIMITS[snap.robot_type]
        acceleration = abs(current.speed - previous_speed) / SIM_DT
        if current.speed > limits["vmax"] + 1e-6:
            _add_violation(violations, "speed limit exceeded")
        if acceleration > limits["amax"] + 1e-6:
            _add_violation(violations, "acceleration limit exceeded")
        if not 0.0 <= current.x <= ARENA_M or not 0.0 <= current.y <= ARENA_M:
            _add_violation(violations, "predicted path leaves arena")
        if steps >= int(MAX_SIM_SECONDS / SIM_DT):
            _add_violation(violations, "mission did not complete within simulation horizon")
            break

    if health is not None and health.rul_s is not None and health.rul_s < elapsed:
        _add_violation(violations, "RUL is shorter than mission ETA")
    if current.battery < 15.0:
        _add_violation(violations, "end battery below 15%")

    downsampled = _downsample(path)
    risk = _risk(current.battery, health, violations)
    safe = not violations
    notes = "Mission satisfies the sandbox safety gate." if safe else "; ".join(violations)
    return SimResult(
        mission_id=mission.mission_id,
        robot_id=mission.robot_id,
        eta_s=elapsed,
        end_battery=current.battery,
        risk=risk,
        path=downsampled,
        violations=violations,
        safe_to_deploy=safe,
        notes=notes,
    )


def _add_violation(violations: list[str], message: str) -> None:
    """Keep safety violations unique while preserving first-seen order."""
    if message not in violations:
        violations.append(message)


def _downsample(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return a path with no more than the contract's 200 points."""
    if len(path) <= 200:
        return path
    indices = [round(index * (len(path) - 1) / 199) for index in range(200)]
    return [path[index] for index in indices]


def _risk(end_battery: float, health: HealthReport | None, violations: list[str]) -> float:
    """Combine hard violations and soft battery/health risk into [0, 1]."""
    risk = min(1.0, 0.2 * len(violations))
    risk += max(0.0, (15.0 - end_battery) / 15.0) * 0.5
    if health is not None:
        risk += (1.0 - health.health_index) * 0.4
    return clamp(risk, 0.0, 1.0)


class _FallbackModel:
    """Small contract-only model used until Lane A's model is integrated."""

    def __init__(self, robot_type: str) -> None:
        self.robot_type = robot_type

    def step(self, state: StateVec, command: Any, dt: float, wear: float = 0.0) -> StateVec:
        """Advance a bounded unicycle and apply shared battery/thermal formulas."""
        limits = LIMITS[self.robot_type]
        desired_speed = 0.0 if wear >= 1.0 else clamp(command.speed, 0.0, limits["vmax"])
        speed = state.speed + clamp(
            desired_speed - state.speed,
            -limits["amax"] * dt,
            limits["amax"] * dt,
        )
        speed = clamp(speed, 0.0, limits["vmax"])
        heading = state.heading + clamp(command.yaw_rate, -limits["wmax"], limits["wmax"]) * dt
        x = state.x + speed * math.cos(heading) * dt
        y = state.y + speed * math.sin(heading) * dt
        current = expected_current(self.robot_type, speed)
        return StateVec(
            x=x,
            y=y,
            z=20.0 if self.robot_type == "drone" else state.z,
            heading=heading,
            speed=speed,
            battery=max(0.0, state.battery - expected_drain_pct_per_s(self.robot_type, speed) * dt),
            motor_temp=expected_temp_step(state.motor_temp, current, dt),
            current=current,
            vibration=expected_vibration(self.robot_type, speed),
        )


def _fallback_follow(
    state: StateVec,
    waypoints: list,
    index: int,
    cruise: float,
    robot_type: str,
) -> tuple[Any, int, bool]:
    """Follow the next waypoint when Lane A's pure-pursuit helper is absent."""
    from types import SimpleNamespace

    if not waypoints:
        return SimpleNamespace(speed=0.0, yaw_rate=0.0), index, True
    target = waypoints[index % len(waypoints)]
    dx, dy = target.x - state.x, target.y - state.y
    distance = math.hypot(dx, dy)
    if distance < 3.0:
        index += 1
        if index >= len(waypoints):
            return SimpleNamespace(speed=0.0, yaw_rate=0.0), index, True
        target = waypoints[index]
        dx, dy = target.x - state.x, target.y - state.y
    desired = math.atan2(dy, dx)
    error = (desired - state.heading + math.pi) % (2.0 * math.pi) - math.pi
    wmax = LIMITS[robot_type]["wmax"]
    speed = min(abs(cruise), LIMITS[robot_type]["vmax"])
    return SimpleNamespace(speed=speed, yaw_rate=clamp(2.0 * error, -wmax, wmax)), index, False
