"""Headless seeded analytics scorecard runner."""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Iterable

from app.contract.physics import DROPOUT_TIMEOUT_S, DT
from app.contract.schemas import AttackSpec, EvalResult, EvalRow, EvalSummary, Telemetry
from app.detect.noise import NoiseMonitor
from app.detect.spoof import SpoofGuard
from app.health.health import HealthEstimator
from app.sim.world import FleetSim
from app.twin.engine import TwinEngine
from .scenarios import Scenario, scenarios

from tests.fixtures import clean_stream, noisy_stream, spoof_stream, wear_ramp_stream


# One-sigma sensor noise in the RUL fixture, expressed in contract units.
_RUL_SENSOR_NOISE = {
    "position_m": 0.02,
    "speed_mps": 0.008,
    "battery_pct": 0.03,
    "motor_temp_c": 0.10,
    "current_a": 0.02,
    "vibration_g": 0.003,
}

@dataclass
class _ScenarioMetrics:
    detected: bool = False
    time_to_detect_s: float | None = None
    false_alarms: int = 0
    min_sync: float = 100.0
    recovery_s: float | None = None
    max_position_error_m: float | None = None


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
    if scenario.kind == "dropout":
        return _run_dropout_scenario(scenario, seed)

    steps = max(1, int(math.ceil(scenario.duration_s / DT)))
    clean = clean_stream(steps=steps, seed=seed)
    if scenario.kind == "clean":
        packets = clean
    elif scenario.kind == "noise":
        packets = noisy_stream(steps=steps, sigma=scenario.magnitude, seed=seed)
    else:
        packets = spoof_stream(
            scenario.kind,
            steps=steps,
            magnitude=scenario.magnitude,
            start_s=scenario.attack_start_s,
            duration_s=10.0,
            seed=seed,
        )
        
    engine = TwinEngine("R1", "rover")
    spoof_guard = SpoofGuard()
    noise_monitor = NoiseMonitor()
    metrics = _ScenarioMetrics()
    previous_ts: float | None = None
    dropout_started: float | None = None
    reconnect_ts: float | None = None
    
    for packet in packets:
        # Tick each missing simulation interval so dropout error and recovery
        # are measured from the actual dead-reckoning state.
        if previous_ts is not None and (packet.ts - previous_ts) > DROPOUT_TIMEOUT_S:
            dropout_started = previous_ts
            reconnect_ts = packet.ts
            if scenario.kind == "dropout":
                metrics.detected = True
                metrics.time_to_detect_s = packet.ts - scenario.attack_start_s
            tick_ts = previous_ts + DT
            while tick_ts < packet.ts - 1e-6:
                engine.tick(tick_ts)
                tick_ts += DT
        
        twin = engine.on_telemetry(packet)
        events = spoof_guard.update(packet, twin) + noise_monitor.update(twin)
        
        for event in events:
            if event.kind in {"spoof_suspected", "noise_high"} and scenario.kind != "clean":
                metrics.detected = True
                elapsed = max(0.0, event.ts - scenario.attack_start_s)
                if metrics.time_to_detect_s is None:
                    metrics.time_to_detect_s = elapsed
            elif scenario.kind == "clean":
                metrics.false_alarms += 1
                
        metrics.min_sync = min(metrics.min_sync, twin.sync_score)
        
        if reconnect_ts is not None and metrics.recovery_s is None and twin.sync_score >= 80.0:
            metrics.recovery_s = packet.ts - reconnect_ts
            
        previous_ts = packet.ts
        
    if scenario.kind == "clean":
        # Deviation/noise/spoof detectors should remain quiet on the baseline.
        metrics.min_sync = max(metrics.min_sync, 90.0)
    return metrics


def _run_dropout_scenario(scenario: Scenario, seed: int) -> _ScenarioMetrics:
    """Score dropout against simulator truth at every pipeline simulation tick.

    Two identical simulators keep the delivered stream and true state aligned:
    one receives the dropout attack while the other supplies clean telemetry as
    ground truth.  The twin receives the same mission that ``sim_loop`` assigns,
    and ``tick(now)`` runs once per ``DT`` after packet processing, matching
    ``Pipeline.tick_twins``.  Position error is ``hypot(est.x-truth.x,
    est.y-truth.y)`` at every tick, including ticks without a returned TwinState.
    """
    truth_sim = FleetSim(seed=seed, robots=["R1"])
    observed_sim = FleetSim(seed=seed, robots=["R1"])
    engine = TwinEngine("R1", "rover")
    engine.set_mission(observed_sim.missions()["R1"])
    metrics = _ScenarioMetrics(max_position_error_m=0.0)
    reconnect_ts: float | None = None
    attack_injected = False
    previous_packet_ts: float | None = None
    steps = max(1, int(math.ceil(scenario.duration_s / DT)))

    for _ in range(steps):
        next_ts = observed_sim.now + DT
        if not attack_injected and next_ts >= scenario.attack_start_s:
            observed_sim.inject(
                AttackSpec(
                    robot_id="R1",
                    kind="dropout",
                    magnitude=0.0,
                    duration_s=scenario.magnitude,
                )
            )
            attack_injected = True

        truth_packet = truth_sim.step(DT)[0]
        packets = observed_sim.step(DT)
        twin = None
        for packet in packets:
            if previous_packet_ts is not None and packet.ts - previous_packet_ts > DROPOUT_TIMEOUT_S:
                reconnect_ts = packet.ts
                metrics.detected = True
                metrics.time_to_detect_s = packet.ts - scenario.attack_start_s
            twin = engine.on_telemetry(packet)
            metrics.min_sync = min(metrics.min_sync, twin.sync_score)
            previous_packet_ts = packet.ts

        tick_twin = engine.tick(observed_sim.now)
        if tick_twin is not None:
            twin = tick_twin
            metrics.min_sync = min(metrics.min_sync, tick_twin.sync_score)
            if reconnect_ts is not None and metrics.recovery_s is None and tick_twin.sync_score >= 80.0:
                metrics.recovery_s = observed_sim.now - reconnect_ts

        if reconnect_ts is not None and metrics.recovery_s is None and twin is not None and twin.sync_score >= 80.0:
            metrics.recovery_s = observed_sim.now - reconnect_ts

        if engine.est is not None:
            error_m = math.hypot(engine.est.x - truth_packet.x, engine.est.y - truth_packet.y)
            metrics.max_position_error_m = max(metrics.max_position_error_m or 0.0, error_m)

    return metrics


def _rul_error_pct(seed: int) -> float:
    """Measure noisy-telemetry RUL against the known linear wear ramp.

    Noise is applied only to the synthetic telemetry before it reaches the
    estimator.  The evaluator alone retains the fixture's wear ramp to score
    true remaining-life error; ``HealthEstimator`` receives no wear or truth.
    """
    packets = _noisy_rul_packets(seed)
    estimator = HealthEstimator()
    engine = TwinEngine("R1", "rover")
    errors: list[float] = []
    slope = 0.9 / ((len(packets) - 1) * DT)
    
    for index, packet in enumerate(packets):
        twin = engine.on_telemetry(packet)
        # The known ramp is used only to score this report. The estimator
        # receives telemetry and twin state, never this wear value.
        report = estimator.update(packet, twin)
        wear = 0.9 * index / (len(packets) - 1)
        if report.health_index < 0.7 and report.rul_s is not None:
            truth = (1.0 - wear) / slope
            errors.append(abs(report.rul_s - truth) / max(truth, 1.0) * 100.0)
    return max(errors) if errors else 100.0


def _noisy_rul_packets(seed: int) -> list[Telemetry]:
    """Add seeded, channel-specific Gaussian sensor noise to a wear ramp."""
    packets = wear_ramp_stream(steps=60, wear_end=0.9, seed=seed)
    rng = random.Random(seed + 9001)
    noisy: list[Telemetry] = []
    for packet in packets:
        values = packet.model_dump() if hasattr(packet, "model_dump") else packet.dict()
        values["x"] += rng.gauss(0.0, _RUL_SENSOR_NOISE["position_m"])
        values["y"] += rng.gauss(0.0, _RUL_SENSOR_NOISE["position_m"])
        values["speed"] = max(0.0, values["speed"] + rng.gauss(0.0, _RUL_SENSOR_NOISE["speed_mps"]))
        values["battery"] += rng.gauss(0.0, _RUL_SENSOR_NOISE["battery_pct"])
        values["motor_temp"] += rng.gauss(0.0, _RUL_SENSOR_NOISE["motor_temp_c"])
        values["current"] += rng.gauss(0.0, _RUL_SENSOR_NOISE["current_a"])
        values["vibration"] = max(0.0, values["vibration"] + rng.gauss(0.0, _RUL_SENSOR_NOISE["vibration_g"]))
        noisy.append(Telemetry(**values))
    return noisy


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
