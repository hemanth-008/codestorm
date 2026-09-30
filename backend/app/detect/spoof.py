"""Telemetry spoof and packet-integrity detection."""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.contract.physics import LIMITS, expected_drain_pct_per_s
from app.contract.schemas import Event, Telemetry, TwinState


@dataclass
class _SpoofState:
    previous: Telemetry | None = None
    active: bool = False
    duplicate_count: int = 0
    last_event_ts: float | None = None


class SpoofGuard:
    """Detect inconsistent, frozen, or implausible telemetry packets.

    Packet displacement is converted to implied speed with
    ``sqrt(dx**2 + dy**2) / dt``; speed and heading changes are similarly
    differentiated and compared with the robot's contract limits.  A packet is
    suspicious when any integrity, kinematic, battery, freeze, or persistent
    twin-residual check fires.  One rising ``spoof_suspected`` event is emitted
    until the packet stream returns to a clean state.
    """

    def __init__(self, *, residual_threshold_m: float = 2.0, cooldown_s: float = 5.0) -> None:
        if residual_threshold_m < 0:
            raise ValueError("residual_threshold_m must be non-negative")
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be non-negative")
        self.residual_threshold_m = residual_threshold_m
        self.cooldown_s = cooldown_s
        self._states: dict[str, _SpoofState] = {}

    def update(self, tel: Telemetry, twin: TwinState) -> list[Event]:
        """Inspect one packet and its twin residual for spoof indicators."""
        state = self._states.setdefault(tel.robot_id, _SpoofState())
        reasons, metrics = self._indicators(tel, twin, state.previous)
        state.previous = tel
        if not reasons:
            state.active = False
            state.duplicate_count = 0
            return []

        state.duplicate_count += int("frozen_values" in reasons)
        if state.active:
            return []
        state.active = True
        return self._emit_if_allowed(state, tel, reasons, metrics)

    def _indicators(
        self,
        tel: Telemetry,
        twin: TwinState,
        previous: Telemetry | None,
    ) -> tuple[list[str], dict[str, float | int | str]]:
        """Return reasons and measurements for a suspicious packet."""
        reasons: list[str] = []
        metrics: dict[str, float | int | str] = {}
        if previous is None:
            return reasons, metrics

        dt = tel.ts - previous.ts
        if tel.seq <= previous.seq:
            reasons.append("sequence_regression")
        if dt <= 0.0:
            reasons.append("timestamp_regression")
            return reasons, metrics

        limits = LIMITS[tel.robot_type]
        distance = math.hypot(tel.x - previous.x, tel.y - previous.y)
        implied_speed = distance / dt
        acceleration = abs(tel.speed - previous.speed) / dt
        yaw_rate = abs(_angle_delta(tel.heading, previous.heading)) / dt
        metrics.update(
            implied_speed_mps=implied_speed,
            acceleration_mps2=acceleration,
            yaw_rate_rps=yaw_rate,
        )
        if implied_speed > limits["vmax"] * 1.5 or abs(implied_speed - abs(tel.speed)) > max(1.0, limits["vmax"] * 0.75):
            reasons.append("implied_speed_mismatch")
        if acceleration > limits["amax"] * 1.5:
            reasons.append("acceleration_limit")
        if yaw_rate > limits["wmax"] * 1.5:
            reasons.append("yaw_limit")

        battery_delta = tel.battery - previous.battery
        metrics["battery_delta_pct"] = battery_delta
        if battery_delta > 0.5:
            reasons.append("battery_rise")
        expected_drain = expected_drain_pct_per_s(tel.robot_type, abs(tel.speed)) * dt
        metrics["expected_drain_pct"] = expected_drain
        if battery_delta < -expected_drain * 5.0:
            reasons.append("battery_drain_mismatch")

        same_values = all(
            getattr(tel, field) == getattr(previous, field)
            for field in ("x", "y", "z", "heading", "speed", "battery", "motor_temp", "current", "vibration")
        )
        if same_values and abs(tel.speed) > 0.05:
            reasons.append("frozen_values")
        if twin.residual_pos > self.residual_threshold_m:
            reasons.append("twin_residual")
        metrics["residual_pos_m"] = twin.residual_pos
        if reasons:
            metrics["reason_count"] = len(reasons)
        return reasons, metrics

    def _emit_if_allowed(
        self,
        state: _SpoofState,
        tel: Telemetry,
        reasons: list[str],
        metrics: dict[str, float | int | str],
    ) -> list[Event]:
        """Emit a critical event unless the guard is still cooling down."""
        if state.last_event_ts is not None and tel.ts - state.last_event_ts < self.cooldown_s:
            return []
        state.last_event_ts = tel.ts
        detail = {"reasons": reasons, **metrics}
        return [
            Event(
                id=f"spoof_suspected:{tel.robot_id}:{tel.ts:.3f}",
                ts=tel.ts,
                robot_id=tel.robot_id,
                kind="spoof_suspected",
                severity="critical",
                message=f"{tel.robot_id} telemetry spoof suspected",
                detail=detail,
            )
        ]


def _angle_delta(current: float, previous: float) -> float:
    """Return the shortest signed heading difference in radians."""
    return (current - previous + math.pi) % (2.0 * math.pi) - math.pi

