"""Rolling residual-variance noise monitoring."""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field

from app.contract.schemas import Event, TwinState


@dataclass
class _NoiseState:
    residuals: deque[float]
    active: bool = False
    last_event_ts: dict[str, float] = field(default_factory=dict)


class NoiseMonitor:
    """Detect high measurement noise from a rolling twin residual window.

    The monitor computes population variance
    ``sum((r - trend(r))**2) / n`` over the last ``window_size`` residual
    magnitudes, where ``trend`` is a least-squares linear trend.  Removing a
    persistent slope prevents spoof drift from being mislabeled as white
    sensor noise.  A rising ``noise_high`` edge is emitted above the configured
    variance threshold, and ``noise_cleared`` is emitted after the window falls
    back below it.
    """

    def __init__(
        self,
        *,
        window_size: int = 25,
        variance_threshold_m2: float = 0.25,
        min_samples: int = 5,
        cooldown_s: float = 5.0,
    ) -> None:
        if window_size < 2:
            raise ValueError("window_size must be at least 2")
        if variance_threshold_m2 < 0:
            raise ValueError("variance_threshold_m2 must be non-negative")
        if min_samples < 2 or min_samples > window_size:
            raise ValueError("min_samples must be between 2 and window_size")
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be non-negative")
        self.window_size = window_size
        self.variance_threshold_m2 = variance_threshold_m2
        self.min_samples = min_samples
        self.cooldown_s = cooldown_s
        self._states: dict[str, _NoiseState] = {}

    def update(self, twin: TwinState) -> list[Event]:
        """Record one residual and return noise state-transition events."""
        state = self._states.setdefault(
            twin.robot_id,
            _NoiseState(residuals=deque(maxlen=self.window_size)),
        )
        state.residuals.append(float(twin.residual_pos))
        if len(state.residuals) < self.min_samples:
            return []
        variance = _detrended_variance(state.residuals)
        high = variance > self.variance_threshold_m2
        detail = {
            "variance_m2": variance,
            "threshold_m2": self.variance_threshold_m2,
            "window": len(state.residuals),
        }
        if high and not state.active:
            state.active = True
            return self._emit_if_allowed(state, twin, "noise_high", "warn", "noise level high", detail)
        if not high and state.active:
            state.active = False
            return self._emit_if_allowed(state, twin, "noise_cleared", "info", "noise level cleared", detail)
        return []

    def _emit_if_allowed(
        self,
        state: _NoiseState,
        twin: TwinState,
        kind: str,
        severity: str,
        message: str,
        detail: dict[str, float | int],
    ) -> list[Event]:
        """Emit one event per kind per robot during the cooldown interval."""
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
                message=f"{twin.robot_id} {message}",
                detail=detail,
            )
        ]


def _detrended_variance(values: deque[float]) -> float:
    """Return residual variance after removing a least-squares linear trend."""
    samples = list(values)
    if len(samples) < 2:
        return 0.0
    mean_x = (len(samples) - 1) / 2.0
    mean_y = statistics.fmean(samples)
    denominator = sum((index - mean_x) ** 2 for index in range(len(samples)))
    slope = (
        sum((index - mean_x) * (value - mean_y) for index, value in enumerate(samples)) / denominator
        if denominator
        else 0.0
    )
    intercept = mean_y - slope * mean_x
    residuals = [value - (intercept + slope * index) for index, value in enumerate(samples)]
    return statistics.pvariance(residuals)
