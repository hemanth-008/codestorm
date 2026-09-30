"""Tests for spoof detection against deterministic telemetry fixtures."""
from __future__ import annotations

import math

from app.contract.schemas import StateVec, TwinState
from app.detect.spoof import SpoofGuard
from fixtures import clean_stream, noisy_stream, spoof_stream


def _twin(packet, residual_pos: float = 0.0) -> TwinState:
    state = StateVec(
        x=packet.x,
        y=packet.y,
        heading=packet.heading,
        speed=packet.speed,
        battery=packet.battery,
        motor_temp=packet.motor_temp,
        current=packet.current,
        vibration=packet.vibration,
    )
    return TwinState(
        robot_id=packet.robot_id,
        ts=packet.ts,
        mode="synced",
        pred=state,
        est=state,
        residual_pos=residual_pos,
        residual_norm=0.0,
        cross_track_err=0.0,
        heading_err=0.0,
        sync_score=100.0,
        confidence=1.0,
    )


def _first_event(kind: str, *, magnitude: float = 15.0) -> tuple[int, float]:
    clean = clean_stream(steps=100)
    attacked = spoof_stream(kind, steps=100, magnitude=magnitude, start_s=4.0, duration_s=10.0)
    guard = SpoofGuard()
    for index, packet in enumerate(attacked):
        residual = math.hypot(packet.x - clean[index].x, packet.y - clean[index].y)
        events = guard.update(packet, _twin(packet, residual))
        if events:
            return index, events[0].ts
    raise AssertionError("expected spoof event")


def test_clean_stream_has_no_spoof_event() -> None:
    guard = SpoofGuard()
    assert all(not guard.update(packet, _twin(packet)) for packet in clean_stream(steps=100))


def test_noise_stream_does_not_fire_spoof_guard_from_one_step_jitter() -> None:
    guard = SpoofGuard()
    assert all(not guard.update(packet, _twin(packet, residual_pos=1.0)) for packet in noisy_stream(steps=100, sigma=1.0, seed=1))


def test_jump_is_detected_on_first_attacked_packet() -> None:
    index, _ = _first_event("spoof_jump", magnitude=15.0)
    assert index <= 21


def test_battery_offset_is_detected_within_two_seconds() -> None:
    _, ts = _first_event("spoof_battery", magnitude=10.0)
    assert ts <= 6.0


def test_freeze_is_detected_within_three_seconds() -> None:
    _, ts = _first_event("spoof_freeze", magnitude=1.0)
    assert ts <= 7.0


def test_drift_is_detected_within_fifteen_seconds() -> None:
    _, ts = _first_event("spoof_drift", magnitude=0.5)
    assert ts <= 19.0


def test_sequence_regression_is_suspicious() -> None:
    packets = clean_stream(steps=3)
    guard = SpoofGuard()
    assert guard.update(packets[0], _twin(packets[0])) == []
    packets[1].seq = packets[0].seq
    events = guard.update(packets[1], _twin(packets[1]))
    assert events[0].detail["reasons"] == ["sequence_regression"]
