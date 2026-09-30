"""Fault injection logic for the simulator.

Attacks mutate the telemetry packet only. The true state (GroundTruth) is unaffected.
"""
from __future__ import annotations

import math
import random

from app.contract.schemas import AttackSpec, StateVec, Telemetry
from app.contract.physics import clamp


def apply_attack(
    tel: Telemetry,
    atk: AttackSpec | None,
    rng: random.Random,
    remaining_s: float,
    last_clean_state: StateVec | None,
) -> Telemetry:
    """Mutate the telemetry packet per the active attack.

    Parameters
    ----------
    tel : Telemetry
        The clean packet generated from the true state.
    atk : AttackSpec | None
        The active attack, if any.
    rng : random.Random
        A per-robot deterministic random number generator.
    remaining_s : float
        Time remaining for the attack (used for time-varying attacks like drift).
    last_clean_state : StateVec | None
        The snapshot of the true state when spoof_freeze started.

    Returns
    -------
    Telemetry
        The mutated packet.
    """
    if atk is None:
        return tel

    data = tel.model_dump()

    if atk.kind == "noise":
        sigma = atk.magnitude
        data["x"] += rng.gauss(0, sigma)
        data["y"] += rng.gauss(0, sigma)
        data["speed"] += rng.gauss(0, sigma * 0.3)
        data["current"] += rng.gauss(0, sigma * 0.5)
        data["motor_temp"] += rng.gauss(0, sigma * 0.5)
        data["speed"] = max(0.0, data["speed"])

    elif atk.kind == "dropout":
        pass  # Handled in FleetSim.step() by dropping the packet entirely

    elif atk.kind == "spoof_freeze":
        # Replay the snapshot values with advancing seq/ts
        if last_clean_state:
            frozen = last_clean_state
            data["x"] = frozen.x
            data["y"] = frozen.y
            data["heading"] = frozen.heading
            data["speed"] = frozen.speed
            data["battery"] = frozen.battery
            data["motor_temp"] = frozen.motor_temp
            data["current"] = frozen.current
            data["vibration"] = frozen.vibration

    elif atk.kind == "spoof_jump":
        # Add a fixed offset to position. We use a fixed deterministic angle
        # so the jump is stable for the duration of the attack.
        data["x"] += atk.magnitude * math.cos(0.7)
        data["y"] += atk.magnitude * math.sin(0.7)

    elif atk.kind == "spoof_drift":
        # Position offset grows linearly over time.
        elapsed = atk.duration_s - remaining_s
        drift = atk.magnitude * elapsed  # meters
        data["x"] += drift * math.cos(1.2)
        data["y"] += drift * math.sin(1.2)

    elif atk.kind == "spoof_battery":
        data["battery"] = clamp(data["battery"] + atk.magnitude, 0.0, 100.0)

    return Telemetry(**data)
