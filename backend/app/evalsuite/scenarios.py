"""Deterministic evaluation scenario definitions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    """One seeded attack or baseline scenario."""

    name: str
    kind: str
    magnitude: float
    duration_s: float
    attack_start_s: float = 4.0


def scenarios(*, fast: bool = True) -> list[Scenario]:
    """Return the deterministic scorecard matrix in stable display order."""
    duration = 20.0 if fast else 60.0
    return [
        Scenario("clean_baseline", "clean", 0.0, duration),
        Scenario("noise_1m", "noise", 1.0, duration),
        Scenario("noise_2m", "noise", 2.0, duration),
        Scenario("noise_4m", "noise", 4.0, duration),
        Scenario("dropout_2s", "dropout", 2.0, duration),
        Scenario("dropout_5s", "dropout", 5.0, duration),
        Scenario("dropout_10s", "dropout", 10.0, duration),
        Scenario("spoof_freeze", "spoof_freeze", 1.0, duration),
        Scenario("spoof_jump_15m", "spoof_jump", 15.0, duration),
        Scenario("spoof_drift_0_5mps", "spoof_drift", 0.5, duration),
        Scenario("spoof_battery_10pct", "spoof_battery", 10.0, duration),
    ]

