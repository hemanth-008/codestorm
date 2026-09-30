"""Tests for the deterministic Lane B telemetry fixtures."""
from __future__ import annotations

import math

from app.contract.physics import DT, WEAR_CURRENT_GAIN
from fixtures import (
    clean_stream,
    dropout_stream,
    noisy_stream,
    spoof_stream,
    wear_ramp_stream,
)


def test_clean_stream_is_deterministic_and_moves() -> None:
    first = clean_stream(steps=10, seed=7)
    second = clean_stream(steps=10, seed=7)

    assert first == second
    assert len(first) == 10
    assert first[0].seq == 0
    assert first[-1].ts == 9 * DT
    assert first[0].x != first[-1].x


def test_noisy_stream_changes_measured_channels_but_preserves_metadata() -> None:
    clean = clean_stream(steps=8, seed=10)
    noisy = noisy_stream(steps=8, sigma=1.0, seed=10)

    assert [(p.seq, p.ts) for p in noisy] == [(p.seq, p.ts) for p in clean]
    assert any(not math.isclose(a.x, b.x) for a, b in zip(clean, noisy))
    assert any(not math.isclose(a.motor_temp, b.motor_temp) for a, b in zip(clean, noisy))


def test_spoof_variants_apply_only_during_attack_window() -> None:
    clean = clean_stream(steps=80)
    for kind in ("spoof_jump", "spoof_drift", "spoof_battery", "spoof_freeze"):
        attacked = spoof_stream(kind, steps=80, magnitude=15.0, start_s=4.0, duration_s=2.0)
        before = [p for p in attacked if p.ts < 4.0][-1]
        during = next(p for p in attacked if 4.0 < p.ts < 6.0)
        after = next(p for p in attacked if p.ts >= 6.0)
        baseline_during = next(p for p in clean if p.ts == during.ts)
        baseline_after = next(p for p in clean if p.ts == after.ts)
        assert during.seq == baseline_during.seq
        assert after == baseline_after
        if kind == "spoof_jump":
            assert math.isclose(during.x - baseline_during.x, 15.0)
        elif kind == "spoof_battery":
            assert math.isclose(during.battery - baseline_during.battery, 15.0)
        elif kind == "spoof_freeze":
            assert during.x == before.x
        else:
            assert during.x > baseline_during.x


def test_dropout_omits_window_and_keeps_sequence_gap_visible() -> None:
    packets = dropout_stream(steps=80, start_s=4.0, duration_s=2.0)

    assert packets
    gap = next(b.seq - a.seq for a, b in zip(packets, packets[1:]) if b.seq - a.seq > 1)
    assert gap == 11


def test_wear_ramp_increases_current_and_vibration() -> None:
    packets = wear_ramp_stream(steps=10, wear_start=0.0, wear_end=0.8)

    assert packets[-1].current > packets[0].current
    assert packets[-1].vibration > packets[0].vibration
    expected_ratio = 1.0 + WEAR_CURRENT_GAIN * 0.8
    assert packets[-1].current / packets[0].current > expected_ratio - 0.01
