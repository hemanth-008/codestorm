"""Shared physics constants and formulas. READ-ONLY for agents (owner: Hemanth).

The simulator GENERATES telemetry with these formulas plus wear. The twin and the
health estimator PREDICT with the same formulas without wear. The gap between
observed and expected is the signal for failure prediction.

Wear model (simulator only):
  current_obs   = expected_current(...) * (1 + WEAR_CURRENT_GAIN * wear)
  temp          = first-order lag toward T_AMB + K_THERMAL * current_obs
  vibration_obs = expected_vibration(...) + WEAR_VIB_GAIN * wear + noise
  wear in [0, 1]; the robot fails (speed forced to 0) when wear >= FAILURE_WEAR.
"""
from __future__ import annotations

from typing import Dict

DT = 0.2                  # s; sim step and telemetry period (5 Hz)
DROPOUT_TIMEOUT_S = 1.0   # no packet this long => twin enters dead_reckoning
SYNC_TOL_M = 3.0          # position RMSE at which sync_score reaches 0
SYNC_WINDOW = 50          # packets (10 s) used for the sync RMSE
GATE_M = 8.0              # residual above this => estimator gain drops (twin acts as verifier)
ARENA_M = 200.0           # arena is [0, ARENA_M] x [0, ARENA_M] meters

T_AMB = 30.0
THERMAL_TAU_S = 25.0
K_THERMAL = 2.0           # steady-state temp = T_AMB + K_THERMAL * current
WEAR_CURRENT_GAIN = 0.6
WEAR_VIB_GAIN = 1.5
FAILURE_WEAR = 1.0

LIMITS: Dict[str, Dict[str, float]] = {
    "rover": {"vmax": 2.0, "amax": 1.5, "wmax": 1.5},
    "drone": {"vmax": 8.0, "amax": 4.0, "wmax": 2.5},
    "agv": {"vmax": 3.0, "amax": 1.0, "wmax": 0.8},
}
DEFAULT_CRUISE = {"rover": 1.5, "drone": 6.0, "agv": 2.0}

_CURRENT_BASE = {"rover": 2.0, "drone": 6.0, "agv": 3.0}
_CURRENT_PER_MS = {"rover": 3.0, "drone": 1.0, "agv": 4.0}
_DRAIN_BASE = {"rover": 0.010, "drone": 0.030, "agv": 0.012}      # battery % per second
_DRAIN_PER_MS = {"rover": 0.004, "drone": 0.003, "agv": 0.004}
_VIB_BASE = {"rover": 0.10, "drone": 0.20, "agv": 0.08}
_VIB_PER_MS = 0.03


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def expected_current(robot_type: str, speed: float) -> float:
    return _CURRENT_BASE[robot_type] + _CURRENT_PER_MS[robot_type] * abs(speed)


def expected_temp_step(temp: float, current: float, dt: float = DT) -> float:
    """One first-order thermal step toward the steady-state temperature."""
    t_ss = T_AMB + K_THERMAL * current
    return temp + (t_ss - temp) * dt / THERMAL_TAU_S


def expected_drain_pct_per_s(robot_type: str, speed: float) -> float:
    return _DRAIN_BASE[robot_type] + _DRAIN_PER_MS[robot_type] * abs(speed)


def expected_vibration(robot_type: str, speed: float) -> float:
    return _VIB_BASE[robot_type] + _VIB_PER_MS * abs(speed)
