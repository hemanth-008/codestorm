"""Deterministic telemetry fixtures for Lane B analytics tests.

The real simulator is intentionally not imported here.  These helpers model a
small circular patrol and use only the shared contract schemas and physics
formulas, so analytics tests can run before Lane A is merged.
"""
from __future__ import annotations

import math
import random
from typing import Iterable

from app.contract.physics import (
    ARENA_M,
    DEFAULT_CRUISE,
    DT,
    T_AMB,
    WEAR_CURRENT_GAIN,
    WEAR_VIB_GAIN,
    clamp,
    expected_current,
    expected_drain_pct_per_s,
    expected_temp_step,
    expected_vibration,
)
from app.contract.schemas import AttackKind, RobotType, Telemetry


_DEFAULT_STEPS = 100
_CENTER = ARENA_M / 2.0
_PATROL_RADIUS_M = 35.0


def _model_data(packet: Telemetry) -> dict:
    """Copy a Pydantic packet across v1 and v2 without version-specific tests."""
    model_dump = getattr(packet, "model_dump", None)
    return model_dump() if model_dump is not None else packet.dict()


def _step_count(steps: int | None, duration_s: float | None) -> int:
    """Resolve a packet count while keeping the default stream 20 seconds long."""
    if steps is not None and steps < 0:
        raise ValueError("steps must be non-negative")
    if duration_s is not None and duration_s < 0:
        raise ValueError("duration_s must be non-negative")
    if steps is not None:
        return steps
    if duration_s is not None:
        return max(1, int(math.ceil(duration_s / DT)))
    return _DEFAULT_STEPS


def _packet_count(steps: int | None, duration_s: float | None) -> int:
    """Return a packet count and retain a separate name for readable call sites."""
    return _step_count(steps, duration_s)


def _patrol_state(
    robot_type: RobotType,
    ts: float,
    speed: float,
    battery: float,
    motor_temp: float,
    wear: float,
    *,
    current: float | None = None,
) -> dict[str, float]:
    """Generate a bounded circular-patrol state at simulation time ``ts``.

    The circular path has angular rate ``speed / radius`` and therefore keeps
    the implied tangential speed equal to the reported speed.
    """
    theta = ts * speed / _PATROL_RADIUS_M
    x = _CENTER + _PATROL_RADIUS_M * math.cos(theta)
    y = _CENTER + _PATROL_RADIUS_M * math.sin(theta)
    heading = theta + math.pi / 2.0
    observed_current = (
        expected_current(robot_type, speed) * (1.0 + WEAR_CURRENT_GAIN * wear)
        if current is None
        else current
    )
    return {
        "x": x,
        "y": y,
        "z": 20.0 if robot_type == "drone" else 0.0,
        "heading": heading,
        "speed": speed if wear < 1.0 else 0.0,
        "battery": battery,
        "motor_temp": motor_temp,
        "current": observed_current,
        "vibration": expected_vibration(robot_type, speed) + WEAR_VIB_GAIN * wear,
    }


def _clean_packets(
    *,
    robot_id: str,
    robot_type: RobotType,
    count: int,
    seed: int,
    dt: float,
    start_seq: int,
    start_ts: float,
    wear_values: Iterable[float] | None = None,
) -> list[Telemetry]:
    """Create a deterministic clean stream with physics-derived channels."""
    # Seed is consumed here so every public fixture has an explicit, stable
    # random source even when the clean baseline itself needs no randomness.
    random.Random(seed)
    speed = DEFAULT_CRUISE[robot_type]
    battery = 100.0
    motor_temp = T_AMB
    wear_list = list(wear_values) if wear_values is not None else [0.0] * count
    if len(wear_list) != count:
        raise ValueError("wear_values must contain one value per packet")

    packets: list[Telemetry] = []
    for index, raw_wear in enumerate(wear_list):
        wear = clamp(float(raw_wear), 0.0, 1.0)
        ts = start_ts + index * dt
        observed_speed = speed if wear < 1.0 else 0.0
        current = expected_current(robot_type, observed_speed) * (1.0 + WEAR_CURRENT_GAIN * wear)
        motor_temp = expected_temp_step(motor_temp, current, dt)
        battery -= expected_drain_pct_per_s(robot_type, observed_speed) * (1.0 + 0.1 * wear) * dt
        state = _patrol_state(
            robot_type,
            ts,
            observed_speed,
            max(0.0, battery),
            motor_temp,
            wear,
            current=current,
        )
        packets.append(
            Telemetry(
                robot_id=robot_id,
                robot_type=robot_type,
                ts=round(ts, 6),
                seq=start_seq + index,
                **state,
            )
        )
    return packets


def clean_stream(
    robot_id: str = "R1",
    robot_type: RobotType = "rover",
    *,
    steps: int | None = None,
    duration_s: float | None = None,
    seed: int = 42,
    dt: float = DT,
) -> list[Telemetry]:
    """Return a clean, moving stream with no injected faults."""
    return _clean_packets(
        robot_id=robot_id,
        robot_type=robot_type,
        count=_packet_count(steps, duration_s),
        seed=seed,
        dt=dt,
        start_seq=0,
        start_ts=0.0,
    )


def noisy_stream(
    robot_id: str = "R1",
    robot_type: RobotType = "rover",
    *,
    sigma: float = 1.0,
    steps: int | None = None,
    duration_s: float | None = None,
    seed: int = 42,
    dt: float = DT,
) -> list[Telemetry]:
    """Return clean telemetry with Gaussian noise on measured channels.

    Position, speed, current, and temperature receive independent Gaussian
    noise with standard deviation ``sigma``; battery and sequence metadata are
    left intact so the fixture isolates noise monitoring.
    """
    if sigma < 0:
        raise ValueError("sigma must be non-negative")
    rng = random.Random(seed)
    packets = clean_stream(
        robot_id,
        robot_type,
        steps=steps,
        duration_s=duration_s,
        seed=seed,
        dt=dt,
    )
    noisy: list[Telemetry] = []
    for packet in packets:
        values = _model_data(packet)
        for field in ("x", "y", "speed", "current", "motor_temp"):
            values[field] += rng.gauss(0.0, sigma)
        noisy.append(Telemetry(**values))
    return noisy


def dropout_stream(
    robot_id: str = "R1",
    robot_type: RobotType = "rover",
    *,
    start_s: float = 4.0,
    duration_s: float = 2.0,
    steps: int | None = None,
    total_duration_s: float | None = None,
    seed: int = 42,
    dt: float = DT,
) -> list[Telemetry]:
    """Return a clean stream with packets omitted during one dropout window."""
    if start_s < 0 or duration_s < 0:
        raise ValueError("dropout times must be non-negative")
    total = total_duration_s
    if total is None:
        total = max(20.0, start_s + duration_s + 4.0)
    packets = clean_stream(
        robot_id,
        robot_type,
        steps=steps,
        duration_s=total if steps is None else None,
        seed=seed,
        dt=dt,
    )
    end_s = start_s + duration_s
    return [packet for packet in packets if not start_s <= packet.ts < end_s]


def spoof_stream(
    kind: AttackKind,
    robot_id: str = "R1",
    robot_type: RobotType = "rover",
    *,
    magnitude: float = 1.0,
    start_s: float = 4.0,
    duration_s: float = 10.0,
    steps: int | None = None,
    total_duration_s: float | None = None,
    seed: int = 42,
    dt: float = DT,
) -> list[Telemetry]:
    """Return telemetry altered by one supported spoof attack kind.

    The packet sequence and timestamps remain monotonic.  ``spoof_freeze``
    replays the last pre-attack values while advancing metadata; jump, drift,
    and battery attacks apply the documented offsets only while active.
    """
    if kind not in {"spoof_freeze", "spoof_jump", "spoof_drift", "spoof_battery"}:
        raise ValueError(f"unsupported spoof kind: {kind}")
    if start_s < 0 or duration_s < 0:
        raise ValueError("spoof times must be non-negative")
    total = total_duration_s or max(20.0, start_s + duration_s + 4.0)
    packets = clean_stream(
        robot_id,
        robot_type,
        steps=steps,
        duration_s=total if steps is None else None,
        seed=seed,
        dt=dt,
    )
    end_s = start_s + duration_s
    frozen = packets[0] if packets else None
    for packet in packets:
        if packet.ts < start_s:
            frozen = packet
    altered: list[Telemetry] = []
    for packet in packets:
        if not start_s <= packet.ts < end_s:
            altered.append(packet)
            continue
        values = _model_data(packet)
        if kind == "spoof_freeze":
            if frozen is not None:
                for field in ("x", "y", "z", "heading", "speed", "battery", "motor_temp", "current", "vibration"):
                    values[field] = getattr(frozen, field)
        elif kind == "spoof_jump":
            values["x"] += magnitude
        elif kind == "spoof_drift":
            values["x"] += magnitude * (packet.ts - start_s)
        elif kind == "spoof_battery":
            # Preserve the requested offset even above 100%; detectors should
            # see the impossible reading rather than a silently clipped one.
            values["battery"] += magnitude
        altered.append(Telemetry(**values))
    return altered


def wear_ramp_stream(
    robot_id: str = "R1",
    robot_type: RobotType = "rover",
    *,
    steps: int | None = None,
    duration_s: float | None = None,
    wear_start: float = 0.0,
    wear_end: float = 1.0,
    seed: int = 42,
    dt: float = DT,
) -> list[Telemetry]:
    """Return telemetry whose wear rises linearly from ``wear_start`` to end.

    The resulting current, temperature, vibration, and failure speed follow
    the shared wear formulas, providing a deterministic RUL test signal.
    """
    count = _packet_count(steps, duration_s)
    if not 0.0 <= wear_start <= 1.0 or not 0.0 <= wear_end <= 1.0:
        raise ValueError("wear values must be between 0 and 1")
    if count == 1:
        wear_values = [wear_end]
    else:
        wear_values = [wear_start + (wear_end - wear_start) * i / (count - 1) for i in range(count)]
    return _clean_packets(
        robot_id=robot_id,
        robot_type=robot_type,
        count=count,
        seed=seed,
        dt=dt,
        start_seq=0,
        start_ts=0.0,
        wear_values=wear_values,
    )


# Descriptive aliases make scenario code read naturally without duplicating
# the fixture implementations.
clean_telemetry = clean_stream
noisy_telemetry = noisy_stream
spoof_telemetry = spoof_stream
dropout_telemetry = dropout_stream
wear_ramp = wear_ramp_stream
