"""Tests for sandbox simulation and safety gates."""
from __future__ import annotations

from app.contract.schemas import HealthReport, Mission, StateVec, TwinSnapshot, Waypoint
from app.sandbox.simulate import simulate_mission


def _snapshot(*, battery: float = 90.0) -> TwinSnapshot:
    return TwinSnapshot(
        robot_id="R1",
        robot_type="rover",
        ts=0.0,
        est=StateVec(
            x=10.0,
            y=10.0,
            heading=0.0,
            speed=0.0,
            battery=battery,
            motor_temp=30.0,
            current=2.0,
            vibration=0.1,
        ),
        waypoint_idx=0,
    )


def _mission(*waypoints: Waypoint, cruise_speed: float = 1.0) -> Mission:
    return Mission(
        mission_id="M1",
        robot_id="R1",
        waypoints=list(waypoints),
        cruise_speed=cruise_speed,
    )


def test_safe_mission_forks_snapshot_and_returns_bounded_path() -> None:
    snapshot = _snapshot()
    mission = _mission(Waypoint(x=20.0, y=10.0))
    result = simulate_mission(snapshot, mission)

    assert result.safe_to_deploy is True
    assert result.violations == []
    assert result.eta_s > 0.0
    assert result.end_battery < snapshot.est.battery
    assert len(result.path) <= 200
    assert snapshot.est.x == 10.0


def test_safety_gate_rejects_low_battery_and_short_rul() -> None:
    mission = _mission(Waypoint(x=100.0, y=10.0), cruise_speed=1.0)
    health = HealthReport(robot_id="R1", ts=0.0, health_index=0.4, rul_s=5.0)
    result = simulate_mission(_snapshot(battery=16.0), mission, health)

    assert result.safe_to_deploy is False
    assert "RUL is shorter than mission ETA" in result.violations
    assert result.risk > 0.0


def test_mismatched_robot_is_rejected_without_simulation() -> None:
    mission = Mission(
        mission_id="M2",
        robot_id="D1",
        waypoints=[Waypoint(x=20.0, y=20.0)],
        cruise_speed=1.0,
    )
    result = simulate_mission(_snapshot(), mission)

    assert result.safe_to_deploy is False
    assert result.eta_s == 0.0
    assert result.violations == ["mission robot does not match snapshot"]

