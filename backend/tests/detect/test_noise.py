"""Tests for rolling residual variance monitoring."""
from __future__ import annotations

import random

from app.contract.schemas import StateVec, TwinState
from app.detect.noise import NoiseMonitor


def _twin(ts: float, residual: float, robot_id: str = "R1") -> TwinState:
    state = StateVec(
        x=10.0,
        y=10.0,
        heading=0.0,
        speed=1.0,
        battery=90.0,
        motor_temp=32.0,
        current=5.0,
        vibration=0.1,
    )
    return TwinState(
        robot_id=robot_id,
        ts=ts,
        mode="synced",
        pred=state,
        est=state,
        residual_pos=residual,
        residual_norm=0.0,
        cross_track_err=0.0,
        heading_err=0.0,
        sync_score=100.0,
        confidence=1.0,
    )


def test_noise_high_rises_with_one_meter_residual_noise_and_clears() -> None:
    monitor = NoiseMonitor(window_size=25, min_samples=5, variance_threshold_m2=0.4)
    rng = random.Random(42)
    events = []
    for index in range(25):
        events.extend(monitor.update(_twin(index * 0.2, rng.gauss(0.0, 1.0))))
    assert any(event.kind == "noise_high" for event in events)

    for index in range(25, 55):
        events.extend(monitor.update(_twin(index * 0.2, 0.0)))
    assert any(event.kind == "noise_cleared" for event in events)


def test_constant_clean_residuals_do_not_raise_noise() -> None:
    monitor = NoiseMonitor()
    events = []
    for index in range(40):
        events.extend(monitor.update(_twin(index * 0.2, 0.1)))
    assert events == []

