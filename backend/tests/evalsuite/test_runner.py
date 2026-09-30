"""Tests for deterministic scorecard execution."""
from __future__ import annotations

import time

from app.evalsuite.runner import _run_scenario, run_suite
from app.evalsuite.scenarios import scenarios


def test_run_suite_is_seeded_and_contract_shaped() -> None:
    first = run_suite(seed=7, fast=True)
    second = run_suite(seed=7, fast=True)

    assert first == second
    assert first.seed == 7
    assert len(first.rows) == 11
    assert first.summary.detection_rate > 0.5
    assert first.summary.rul_error_pct is not None
    assert first.summary.rul_error_pct < 25.0


def test_run_suite_fast_completes_within_fifteen_seconds() -> None:
    started = time.perf_counter()
    result = run_suite(seed=42, fast=True)
    elapsed = time.perf_counter() - started

    assert result.rows
    assert elapsed < 15.0


def test_seed_one_noise_timing_uses_zero_second_injection_start() -> None:
    result = run_suite(seed=1, fast=True)
    noise = next(row for row in result.rows if row.scenario == "noise_1m")

    assert noise.time_to_detect_s is not None
    assert 0.0 < noise.time_to_detect_s <= 5.0


def test_dropout_uses_sim_mission_and_scores_truth_each_tick() -> None:
    scenario = next(item for item in scenarios() if item.name == "dropout_10s")

    metrics = _run_scenario(scenario, seed=1)

    assert metrics.max_position_error_m is not None
    assert metrics.max_position_error_m < 6.0
    assert metrics.recovery_s is not None
    assert metrics.recovery_s <= 5.0
