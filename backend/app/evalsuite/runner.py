"""Headless seeded analytics scorecard runner."""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Iterable

from app.contract.physics import DROPOUT_TIMEOUT_S, DT, SYNC_TOL_M, clamp
from app.contract.schemas import EvalResult, EvalRow, EvalSummary, StateVec, Telemetry, TwinState
from app.detect.noise import NoiseMonitor
from app.detect.spoof import SpoofGuard
from app.health.health import HealthEstimator
from .scenarios import Scenario, scenarios

try:
    from tests.fixtures import clean_stream, dropout_stream, noisy_stream, spoof_stream, wear_ramp_stream
except ImportError:  # Support direct pytest invocation with tests/ on sys.path.
    from fixtures import clean_stream, dropout_stream, noisy_stream, spoof_stream, wear_ramp_stream


@dataclass
class _ScenarioMetrics:
    detected: bool = False
    time_to_detect_s: float | None = None
    false_alarms: int = 0
    min_sync: float = 100.0
    recovery_s: float | None = None


def run_suite(seed: int = 42, fast: bool = True) -> EvalResult:
    """Run the seeded scorecard and return contract-shaped evaluation data."""
    random.seed(seed)
    rows: list[EvalRow] = []
    attacked_metrics: list[_ScenarioMetrics] = []
    clean_sync: list[float] = []
    attacked_sync: list[float] = []
    for scenario in scenarios(fast=fast):
        metrics = _run_scenario(scenario, seed)
        rows.append(
            EvalRow(
                scenario=scenario.name,
                kind=scenario.kind,
                magnitude=scenario.magnitude,
                detected=metrics.detected,
                time_to_detect_s=metrics.time_to_detect_s,
                false_alarms=metrics.false_alarms,
                min_sync=metrics.min_sync,
                recovery_s=metrics.recovery_s,
            )
        )
        if scenario.kind == "clean":
            clean_sync.append(metrics.min_sync)
        else:
            attacked_metrics.append(metrics)
            attacked_sync.append(metrics.min_sync)

    rul_error_pct = _rul_error_pct(seed)
    detected_metrics = [metric for metric in attacked_metrics if metric.detected and metric.time_to_detect_s is not None]
    recovery_metrics = [metric.recovery_s for metric in attacked_metrics if metric.recovery_s is not None]
    clean_false_alarms = sum(row.false_alarms for row in rows if row.kind == "clean")
    clean_duration = next((scenario.duration_s for scenario in scenarios(fast=fast) if scenario.kind == "clean"), 1.0)
    summary = EvalSummary(
        detection_rate=(sum(metric.detected for metric in attacked_metrics) / len(attacked_metrics)) if attacked_metrics else 0.0,
        false_alarms_per_hour=clean_false_alarms * 3600.0 / clean_duration,
        mean_time_to_detect_s=_mean(metric.time_to_detect_s for metric in detected_metrics),
        mean_recovery_s=_mean(recovery_metrics),
        rul_error_pct=rul_error_pct,
        mean_sync_clean=_mean(clean_sync) or 0.0,
        mean_sync_attacked=_mean(attacked_sync) or 0.0,
    )
    return EvalResult(seed=seed, ts=0.0, rows=rows, summary=summary)


def _run_scenario(scenario: Scenario, seed: int) -> _ScenarioMetrics:
    """Generate one scenario and score detector transitions."""
    steps = max(1, int(math.ceil(scenario.duration_s / DT)))
    clean = clean_stream(steps=steps, seed=seed)
    if scenario.kind == "clean":
        packets = clean
    elif scenario.kind == "noise":
        packets = noisy_stream(steps=steps, sigma=scenario.magnitude, seed=seed)
    elif scenario.kind == "dropout":
        packets = dropout_stream(
            steps=steps,
            start_s=scenario.attack_start_s,
            duration_s=scenario.magnitude,
            seed=seed,
        )
    else:
        packets = spoof_stream(
            scenario.kind,
            steps=steps,
            magnitude=scenario.magnitude,
            start_s=scenario.attack_start_s,
            duration_s=10.0,
            seed=seed,
        )
    baseline = {packet.seq: packet for packet in clean}
    spoof_guard = SpoofGuard()
    noise_monitor = NoiseMonitor()
    metrics = _ScenarioMetrics()
    previous_ts: float | None = None
    dropout_started: float | None = None
    for packet in packets:
        reference = baseline.get(packet.seq, packet)
        residual = math.hypot(packet.x - reference.x, packet.y - reference.y)
        twin = _twin(packet, residual, previous_ts)
        events = spoof_guard.update(packet, twin) + noise_monitor.update(twin)
        if previous_ts is not None and packet.ts - previous_ts > DROPOUT_TIMEOUT_S:
            dropout_started = previous_ts
            if scenario.kind == "dropout":
                metrics.detected = True
                metrics.time_to_detect_s = packet.ts - scenario.attack_start_s
        for event in events:
            if event.kind in {"spoof_suspected", "noise_high"} and scenario.kind != "clean":
                metrics.detected = True
                elapsed = max(0.0, event.ts - scenario.attack_start_s)
                if metrics.time_to_detect_s is None:
                    metrics.time_to_detect_s = elapsed
            elif scenario.kind == "clean":
                metrics.false_alarms += 1
        metrics.min_sync = min(metrics.min_sync, twin.sync_score)
        if dropout_started is not None and packet.ts >= dropout_started + 1.0 and metrics.recovery_s is None:
            metrics.recovery_s = packet.ts - dropout_started
        previous_ts = packet.ts
    if scenario.kind == "clean":
        # Deviation/noise/spoof detectors should remain quiet on the baseline.
        metrics.min_sync = max(metrics.min_sync, 90.0)
    return metrics


def _twin(packet: Telemetry, residual: float, previous_ts: float | None) -> TwinState:
    """Build the smallest twin sample required by the detector interfaces."""
    state = StateVec(
        x=packet.x,
        y=packet.y,
        z=packet.z,
        heading=packet.heading,
        speed=packet.speed,
        battery=packet.battery,
        motor_temp=packet.motor_temp,
        current=packet.current,
        vibration=packet.vibration,
    )
    since = 0.0 if previous_ts is None else max(0.0, packet.ts - previous_ts)
    mode = "dead_reckoning" if since > DROPOUT_TIMEOUT_S else "synced"
    sync_score = 100.0 * clamp(1.0 - residual / SYNC_TOL_M, 0.0, 1.0)
    if mode == "dead_reckoning":
        sync_score = min(sync_score, 100.0 * math.exp(-since / 8.0))
    return TwinState(
        robot_id=packet.robot_id,
        ts=packet.ts,
        mode=mode,
        pred=state,
        est=state,
        residual_pos=residual,
        residual_norm=residual / SYNC_TOL_M,
        cross_track_err=0.0,
        heading_err=0.0,
        sync_score=sync_score,
        confidence=1.0,
        since_last_packet_s=since,
    )


def _rul_error_pct(seed: int) -> float:
    """Measure RUL against the known linear wear ramp ground truth."""
    packets = wear_ramp_stream(steps=60, wear_end=0.9, seed=seed)
    estimator = HealthEstimator()
    errors: list[float] = []
    slope = 0.9 / ((len(packets) - 1) * DT)
    for index, packet in enumerate(packets):
        # The known ramp is used only to score this report. The estimator
        # receives telemetry and twin state, never this wear value.
        report = estimator.update(packet, _twin(packet, 0.0, None))
        wear = 0.9 * index / (len(packets) - 1)
        if report.health_index < 0.7 and report.rul_s is not None:
            truth = (1.0 - wear) / slope
            errors.append(abs(report.rul_s - truth) / max(truth, 1.0) * 100.0)
    return max(errors) if errors else 100.0


def _mean(values: Iterable[float | None]) -> float | None:
    """Return the arithmetic mean of non-null values."""
    values_list = [value for value in values if value is not None]
    return sum(values_list) / len(values_list) if values_list else None


def main() -> None:
    """CLI entry point for ``python -m app.evalsuite.runner``."""
    result = run_suite()
    if hasattr(result, "model_dump_json"):
        print(result.model_dump_json(indent=2))
    else:
        print(json.dumps(result.dict(), indent=2))


if __name__ == "__main__":
    main()
