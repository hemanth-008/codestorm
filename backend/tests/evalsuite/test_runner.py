"""Tests for deterministic scorecard execution."""
from __future__ import annotations

import time

from app.evalsuite.runner import run_suite


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

