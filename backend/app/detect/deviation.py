"""Twin-plan deviation detection."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.contract.schemas import Event, TwinState


@dataclass
class _RobotDeviationState:
    """State needed to turn noisy samples into rising/cleared edges."""

    consecutive_bad: int = 0
    active: bool = False
    last_event_ts: dict[str, float] = field(default_factory=dict)


class DeviationDetector:
    """Emit deviation events after a sustained cross-track or heading error.

    A sample is bad when ``abs(cross_track_err) > cross_track_threshold_m`` or
    ``abs(heading_err) > heading_threshold_rad``.  The detector emits a rising
    edge after ``confirm_packets`` consecutive bad samples and one cleared edge
    when the next good sample arrives.  Each event kind has a simulation-time
    cooldown so repeated edge transitions cannot exceed one event per
    ``cooldown_s`` seconds for a robot.
    """

    def __init__(
        self,
        *,
        cross_track_threshold_m: float = 3.0,
        heading_threshold_rad: float = 0.35,
        confirm_packets: int = 3,
        cooldown_s: float = 5.0,
    ) -> None:
        if cross_track_threshold_m < 0:
            raise ValueError("cross_track_threshold_m must be non-negative")
        if heading_threshold_rad < 0:
            raise ValueError("heading_threshold_rad must be non-negative")
        if confirm_packets < 1:
            raise ValueError("confirm_packets must be positive")
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be non-negative")
        self.cross_track_threshold_m = cross_track_threshold_m
        self.heading_threshold_rad = heading_threshold_rad
        self.confirm_packets = confirm_packets
        self.cooldown_s = cooldown_s
        self._states: dict[str, _RobotDeviationState] = {}

    def update(self, twin: TwinState) -> list[Event]:
        """Process one twin sample and return any state-transition events."""
        state = self._states.setdefault(twin.robot_id, _RobotDeviationState())
        is_bad = self._is_deviating(twin)
        if is_bad and not state.active:
            state.consecutive_bad += 1
            if state.consecutive_bad >= self.confirm_packets:
                state.active = True
                state.consecutive_bad = 0
                return self._emit_if_allowed(
                    state,
                    twin,
                    kind="deviation",
                    severity="warn",
                    message=self._message(twin),
                    detail=self._detail(twin),
                )
            return []

        if is_bad:
            return []

        state.consecutive_bad = 0
        if not state.active:
            return []
        state.active = False
        return self._emit_if_allowed(
            state,
            twin,
            kind="deviation_cleared",
            severity="info",
            message=f"{twin.robot_id} deviation cleared",
            detail={"cause": self._cause(twin)},
        )

    def _is_deviating(self, twin: TwinState) -> bool:
        """Apply the contract thresholds to one twin state."""
        return (
            abs(twin.cross_track_err) > self.cross_track_threshold_m
            or abs(twin.heading_err) > self.heading_threshold_rad
        )

    def _cause(self, twin: TwinState) -> str:
        """Infer a coarse operational cause from plan and residual channels."""
        # A large residual means the observation disagrees with the twin even
        # when the plan error is modest, which is more consistent with a sensor
        # problem than a navigation or obstacle excursion.
        if twin.residual_pos > 8.0 or twin.residual_norm > 2.0:
            return "sensor"
        if abs(twin.cross_track_err) > self.cross_track_threshold_m:
            return "obstacle"
        return "navigation"

    def _detail(self, twin: TwinState) -> dict[str, float | str]:
        """Return machine-readable measurements and the likely cause."""
        return {
            "cause": self._cause(twin),
            "cross_track_err_m": twin.cross_track_err,
            "heading_err_rad": twin.heading_err,
            "residual_pos_m": twin.residual_pos,
        }

    def _message(self, twin: TwinState) -> str:
        """Build a concise operator-facing deviation message."""
        return f"{twin.robot_id} deviation detected ({self._cause(twin)})"

    def _emit_if_allowed(
        self,
        state: _RobotDeviationState,
        twin: TwinState,
        *,
        kind: str,
        severity: str,
        message: str,
        detail: dict,
    ) -> list[Event]:
        """Emit an event unless this kind is still inside its cooldown."""
        previous = state.last_event_ts.get(kind)
        if previous is not None and twin.ts - previous < self.cooldown_s:
            return []
        state.last_event_ts[kind] = twin.ts
        return [
            Event(
                id=f"{kind}:{twin.robot_id}:{twin.ts:.3f}",
                ts=twin.ts,
                robot_id=twin.robot_id,
                kind=kind,
                severity=severity,
                message=message,
                detail=detail,
            )
        ]

