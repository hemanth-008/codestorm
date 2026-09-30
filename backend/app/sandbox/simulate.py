"""Forkable mission simulation with the contract safety gate."""
from __future__ import annotations

import math
from typing import Any

from app.contract.physics import ARENA_M, DT, LIMITS, clamp
from app.contract.schemas import HealthReport, Mission, SimResult, TwinSnapshot
from app.sim.control import follow
from app.sim.models import make_model

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
    model = make_model(snap.robot_type)
    waypoint_idx = snap.waypoint_idx
    path: list[tuple[float, float]] = [(current.x, current.y)]
    violations: list[str] = []
    elapsed = 0.0
    done = not mission.waypoints
    steps = 0

    while not done and elapsed < MAX_SIM_SECONDS:
        command, waypoint_idx, done = follow(
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
