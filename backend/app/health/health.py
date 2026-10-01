"""Physics-based health index and robust RUL estimation."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.contract.physics import (
    DT,
    K_THERMAL,
    T_AMB,
    WEAR_CURRENT_GAIN,
    WEAR_VIB_GAIN,
    clamp,
    expected_current,
    expected_temp_step,
    expected_vibration,
)
from app.contract.schemas import Event, HealthReport, Telemetry, TwinState


@dataclass
class _RobotHealthState:
    expected_temp: float = T_AMB
    last_ts: float | None = None
    wear_history: list[tuple[float, float]] = field(default_factory=list)
    warning_active: bool = False
    maintenance_active: bool = False
    critical_active: bool = False
    last_event_ts: dict[str, float] = field(default_factory=dict)


class HealthEstimator:
    """Estimate wear from physics residuals and predict remaining useful life.

    Current wear is ``(I / I_expected - 1) / WEAR_CURRENT_GAIN``; vibration
    wear is ``(vibration - vibration_expected) / WEAR_VIB_GAIN``.  Temperature
    wear compares the observed value with an internal
    ``expected_temp_step`` predictor.  The estimator uses the median of the
    three clamped wear channels, then computes ``health_index = 1 - wear``.
    RUL uses a Theil–Sen slope (the median of pairwise wear/time slopes), with
    ``rul_s = health_index / slope`` for a positive trend.
    """

    def __init__(
        self,
        *,
        trend_window: int = 60,
        cooldown_s: float = 5.0,
    ) -> None:
        if trend_window < 3:
            raise ValueError("trend_window must be at least 3")
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be non-negative")
        self.trend_window = trend_window
        self.cooldown_s = cooldown_s
        self._states: dict[str, _RobotHealthState] = {}
        self._pending_events: list[Event] = []

    def update(self, tel: Telemetry, twin: TwinState) -> HealthReport:
        """Update one robot's health estimate and queue transition events."""
        state = self._states.setdefault(tel.robot_id, _RobotHealthState())
        dt = DT if state.last_ts is None else max(0.0, tel.ts - state.last_ts)
        expected_i = expected_current(tel.robot_type, abs(tel.speed))
        expected_vibration_value = expected_vibration(tel.robot_type, abs(tel.speed))
        state.expected_temp = expected_temp_step(
            state.expected_temp,
            expected_i,
            dt,
        )
        state.last_ts = tel.ts

        current_wear = _normalised_current_wear(tel.current, expected_i)
        temp_scale = max(1.0, K_THERMAL * expected_i * WEAR_CURRENT_GAIN)
        temp_wear = clamp((tel.motor_temp - state.expected_temp) / temp_scale, 0.0, 1.0)
        vibration_wear = _normalised_vibration_wear(tel.vibration, expected_vibration_value)
        wear = clamp(statistics.median((current_wear, temp_wear, vibration_wear)), 0.0, 1.0)
        state.wear_history.append((tel.ts, wear))
        if len(state.wear_history) > self.trend_window:
            state.wear_history.pop(0)

        health_index = clamp(1.0 - wear, 0.0, 1.0)
        status = _status_for(health_index)
        rul_s, rul_low_s, rul_high_s = _rul_from_history(state.wear_history, health_index)
        drivers = {
            "current": current_wear,
            "temp": temp_wear,
            "vibration": vibration_wear,
        }
        self._queue_transition_events(
            state,
            tel,
            health_index=health_index,
            status=status,
            drivers=drivers,
        )
        return HealthReport(
            robot_id=tel.robot_id,
            ts=tel.ts,
            health_index=health_index,
            rul_s=rul_s,
            rul_low_s=rul_low_s,
            rul_high_s=rul_high_s,
            status=status,
            drivers=drivers,
        )

    @property
    def events(self) -> tuple[Event, ...]:
        """Return queued events without removing them."""
        return tuple(self._pending_events)

    def drain_events(self) -> list[Event]:
        """Return and clear health events queued since the previous drain."""
        events = self._pending_events[:]
        self._pending_events.clear()
        return events

    # ``pop_events`` is a convenient alias for pipeline integrations.
    pop_events = drain_events

    def _queue_transition_events(
        self,
        state: _RobotHealthState,
        tel: Telemetry,
        *,
        health_index: float,
        status: str,
        drivers: dict[str, float],
    ) -> None:
        """Queue warning/maintenance edges while suppressing repeats."""
        warning = health_index < 0.7
        maintenance = health_index < 0.45
        critical = health_index < 0.2
        if warning and not state.warning_active:
            event = self._event_if_allowed(
                state,
                tel,
                kind="health_warning",
                severity="warn",
                message=f"{tel.robot_id} health warning",
                detail={"health_index": health_index, "status": status, "drivers": drivers},
            )
            if event is not None:
                self._pending_events.append(event)
        if maintenance and not state.maintenance_active:
            event = self._event_if_allowed(
                state,
                tel,
                kind="maintenance_due",
                severity="warn",
                message=f"{tel.robot_id} maintenance due",
                detail={"health_index": health_index, "status": status, "drivers": drivers},
            )
            if event is not None:
                self._pending_events.append(event)
        if critical and not state.critical_active:
            event = self._event_if_allowed(
                state,
                tel,
                kind="health_critical",
                severity="critical",
                message=f"{tel.robot_id} health critical",
                detail={"health_index": health_index, "status": status, "drivers": drivers},
            )
            if event is not None:
                self._pending_events.append(event)
        state.warning_active = warning
        state.maintenance_active = maintenance
        state.critical_active = critical

    def _event_if_allowed(
        self,
        state: _RobotHealthState,
        tel: Telemetry,
        *,
        kind: str,
        severity: str,
        message: str,
        detail: dict,
    ) -> Event | None:
        """Create one event when its per-kind cooldown has elapsed."""
        previous = state.last_event_ts.get(kind)
        if previous is not None and tel.ts - previous < self.cooldown_s:
            return None
        state.last_event_ts[kind] = tel.ts
        return Event(
            id=f"{kind}:{tel.robot_id}:{tel.ts:.3f}",
            ts=tel.ts,
            robot_id=tel.robot_id,
            kind=kind,
            severity=severity,
            message=message,
            detail=detail,
        )


def _normalised_current_wear(observed: float, expected: float) -> float:
    """Convert current excess into a bounded wear fraction."""
    if expected <= 0.0:
        return 0.0
    return clamp((observed / expected - 1.0) / WEAR_CURRENT_GAIN, 0.0, 1.0)


def _normalised_vibration_wear(observed: float, expected: float) -> float:
    """Convert vibration excess into a bounded wear fraction."""
    if WEAR_VIB_GAIN <= 0.0:
        return 0.0
    return clamp((observed - expected) / WEAR_VIB_GAIN, 0.0, 1.0)


def _status_for(health_index: float) -> str:
    """Map health index bands to the contract's health statuses."""
    if health_index >= 0.7:
        return "ok"
    if health_index >= 0.45:
        return "watch"
    if health_index >= 0.2:
        return "maintenance"
    return "critical"


def _rul_from_history(
    history: list[tuple[float, float]],
    health_index: float,
) -> tuple[float | None, float | None, float | None]:
    """Compute a robust RUL and a residual-based low/high interval."""
    if len(history) < 3:
        return None, None, None
    slopes: list[float] = []
    for left_index, (left_ts, left_wear) in enumerate(history[:-1]):
        for right_ts, right_wear in history[left_index + 1 :]:
            dt = right_ts - left_ts
            if dt > 0.0:
                slopes.append((right_wear - left_wear) / dt)
    positive_slopes = [slope for slope in slopes if slope > 1e-9]
    if not positive_slopes:
        return None, None, None
    slope = statistics.median(positive_slopes)
    rul_s = max(0.0, health_index / slope)
    # The median absolute slope deviation gives a robust uncertainty fraction;
    # retain a small floor so a perfect synthetic ramp still has useful bounds.
    deviation = statistics.median(abs(value - slope) for value in positive_slopes)
    uncertainty = max(0.05 * rul_s, deviation / slope * rul_s if slope else 0.0)
    return rul_s, max(0.0, rul_s - uncertainty), rul_s + uncertainty
