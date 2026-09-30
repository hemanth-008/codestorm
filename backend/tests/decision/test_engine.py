"""Tests for decision priority and contract response shape."""
from __future__ import annotations

from app.contract.schemas import Event, HealthReport, OverrideState, StateVec, TwinState
from app.decision.engine import decide


def _inputs(
    *,
    battery: float = 90.0,
    speed: float = 1.0,
    mode: str = "synced",
    health_index: float = 1.0,
    status: str = "ok",
    rul_s: float | None = None,
    since: float = 0.0,
) -> tuple[TwinState, HealthReport]:
    state = StateVec(
        x=10.0,
        y=10.0,
        heading=0.0,
        speed=speed,
        battery=battery,
        motor_temp=32.0,
        current=5.0,
        vibration=0.1,
    )
    twin = TwinState(
        robot_id="R1",
        ts=10.0,
        mode=mode,
        pred=state,
        est=state,
        residual_pos=0.0,
        residual_norm=0.0,
        cross_track_err=0.0,
        heading_err=0.0,
        sync_score=100.0,
        confidence=1.0,
        since_last_packet_s=since,
    )
    health = HealthReport(
        robot_id="R1",
        ts=10.0,
        health_index=health_index,
        rul_s=rul_s,
        status=status,
    )
    return twin, health


def _event(kind: str, ts: float = 10.0) -> Event:
    return Event(
        id=f"event:{kind}:{ts}",
        ts=ts,
        robot_id="R1",
        kind=kind,
        severity="warn",
        message=kind,
    )


def test_decision_always_has_per_robot_contract_shape() -> None:
    twin, health = _inputs()
    result = decide("R1", twin, health, [], None)
    assert result.action == "CONTINUE"
    assert result.robot_id == "R1"
    assert 0.0 <= result.confidence <= 1.0


def test_safety_priority_battery_dead_reckoning_and_critical_health() -> None:
    twin, health = _inputs(battery=20.0)
    assert decide("R1", twin, health, [], None).action == "RETURN_TO_BASE"

    twin, health = _inputs(mode="dead_reckoning", since=2.0)
    assert decide("R1", twin, health, [], None).action == "RETURN_TO_BASE"

    twin, health = _inputs(health_index=0.1, status="critical")
    assert decide("R1", twin, health, [], None).action == "RETURN_TO_BASE"


def test_spoof_quarantine_precedes_deviation_and_health() -> None:
    twin, health = _inputs(health_index=0.6, status="watch")
    result = decide("R1", twin, health, [_event("spoof_suspected"), _event("deviation")], None)
    assert result.action == "QUARANTINE_TELEMETRY"


def test_maintenance_and_deviation_actions() -> None:
    twin, health = _inputs(health_index=0.6, status="watch")
    assert decide("R1", twin, health, [], None).action == "SCHEDULE_MAINTENANCE"

    twin, health = _inputs()
    result = decide("R1", twin, health, [_event("deviation")], None)
    assert result.action == "REROUTE"
    assert decide("R1", twin, health, [_event("deviation"), _event("deviation_cleared", 11.0)], None).action == "CONTINUE"

    twin, health = _inputs(speed=1.8)
    assert decide("R1", twin, health, [], None).action == "REROUTE"


def test_active_override_wins_and_robot_scoping_is_honored() -> None:
    twin, health = _inputs(battery=10.0)
    override = OverrideState(robot_id="R1", action="CONTINUE", seconds_left=5.0)
    result = decide("R1", twin, health, [], override)
    assert result.action == "CONTINUE"
    assert result.override_active is True

    other_robot_override = OverrideState(robot_id="D1", action="RETURN_TO_BASE", seconds_left=5.0)
    assert decide("R1", twin, health, [], other_robot_override).action == "RETURN_TO_BASE"
