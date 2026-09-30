"""Rule-based fusion of twin, health, detection, and operator state."""
from __future__ import annotations

from app.contract.physics import clamp
from app.contract.schemas import Decision, Event, HealthReport, OverrideState, TwinState


def decide(
    robot_id: str,
    twin: TwinState,
    health: HealthReport,
    recent_events: list[Event],
    override: OverrideState | None,
) -> Decision:
    """Return the highest-priority safe action for one robot.

    Priority is manual override, spoof quarantine, dead-reckoning return,
    critical health, maintenance, active deviation reroute, then the legacy
    battery/speed safety checks and a normal continue action.  The response is
    always the contract's ``Decision`` shape and carries ``robot_id``.
    """
    override_decision = _override_decision(robot_id, override)
    if override_decision is not None:
        return override_decision

    if _has_event(recent_events, robot_id, "spoof_suspected"):
        return _decision(
            robot_id,
            "QUARANTINE_TELEMETRY",
            "Telemetry integrity is suspicious; quarantine the packet stream",
            0.98,
        )

    if twin.mode == "dead_reckoning":
        return _decision(
            robot_id,
            "RETURN_TO_BASE",
            f"Telemetry link is unavailable for {twin.since_last_packet_s:.1f}s; return to base",
            clamp(0.85 + min(twin.since_last_packet_s, 5.0) * 0.02, 0.85, 0.95),
        )

    if health.status == "critical" or health.health_index < 0.2:
        return _decision(
            robot_id,
            "RETURN_TO_BASE",
            f"Health is critical at {health.health_index:.0%}; return to base",
            0.97,
        )

    if health.rul_s is not None and health.rul_s < 60.0:
        return _decision(
            robot_id,
            "SCHEDULE_MAINTENANCE",
            f"Remaining useful life is {health.rul_s:.0f}s; schedule maintenance",
            0.92,
        )

    if health.status in {"watch", "maintenance"} or health.health_index < 0.7:
        return _decision(
            robot_id,
            "SCHEDULE_MAINTENANCE",
            f"Health is {health.status} at {health.health_index:.0%}; schedule maintenance",
            0.82,
        )

    if _has_active_deviation(recent_events, robot_id):
        return _decision(
            robot_id,
            "REROUTE",
            "Twin deviation is sustained; reroute around the affected path",
            0.84,
        )

    battery = twin.est.battery
    if battery < 30.0:
        # Preserve the existing engine's battery behavior while returning the
        # contract action (the old prototype had no typed Decision model).
        return _decision(
            robot_id,
            "RETURN_TO_BASE",
            f"Battery at {battery:.0f}% is below the 30% safety threshold",
            round(clamp(0.95 - (battery / 300.0), 0.0, 1.0), 2),
        )

    # TwinState intentionally carries no robot_type, so retain the prototype's
    # documented 1.6 m/s decision threshold until the pipeline adds that context.
    speed_limit = 1.6
    if twin.est.speed > speed_limit:
        return _decision(
            robot_id,
            "REROUTE",
            f"Speed {twin.est.speed:.2f} m/s exceeds the safe operating limit",
            0.82,
        )

    return _decision(
        robot_id,
        "CONTINUE",
        "Battery, health, telemetry integrity, and navigation are within safe operating range",
        0.90,
    )


def _decision(robot_id: str, action: str, reason: str, confidence: float) -> Decision:
    """Construct a bounded per-robot decision."""
    return Decision(
        action=action,
        reason=reason,
        confidence=clamp(confidence, 0.0, 1.0),
        robot_id=robot_id,
    )


def _override_decision(robot_id: str, override: OverrideState | None) -> Decision | None:
    """Apply an active matching override, if any."""
    if override is None or override.seconds_left <= 0.0:
        return None
    if override.robot_id is not None and override.robot_id != robot_id:
        return None
    return Decision(
        action=override.action,
        reason=f"Manual override active for {override.seconds_left:.0f}s",
        confidence=1.0,
        robot_id=robot_id,
        override_active=True,
    )


def _has_event(events: list[Event], robot_id: str, kind: str) -> bool:
    """Check matching recent events without treating fleet events as foreign."""
    return any(event.kind == kind and event.robot_id in {None, robot_id} for event in events)


def _has_active_deviation(events: list[Event], robot_id: str) -> bool:
    """Fold deviation rising/cleared events into the current active state."""
    active = False
    for event in sorted(events, key=lambda item: item.ts):
        if event.robot_id not in {None, robot_id}:
            continue
        if event.kind == "deviation":
            active = True
        elif event.kind == "deviation_cleared":
            active = False
    return active
