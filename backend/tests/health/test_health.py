"""Tests for physics-derived health and robust RUL."""
from __future__ import annotations

from app.contract.physics import DT
from app.contract.schemas import StateVec, TwinState
from app.health.health import HealthEstimator
from fixtures import clean_stream, wear_ramp_stream


def _twin(packet) -> TwinState:
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
        residual_pos=0.0,
        residual_norm=0.0,
        cross_track_err=0.0,
        heading_err=0.0,
        sync_score=100.0,
        confidence=1.0,
    )


def test_clean_stream_stays_healthy_without_events() -> None:
    estimator = HealthEstimator()
    reports = [estimator.update(packet, _twin(packet)) for packet in clean_stream(steps=30)]

    assert reports[-1].status == "ok"
    assert reports[-1].health_index > 0.95
    assert estimator.drain_events() == []


def test_wear_ramp_tracks_health_and_rul_within_target_error() -> None:
    packets = wear_ramp_stream(steps=60, duration_s=None, wear_start=0.0, wear_end=0.9)
    estimator = HealthEstimator()
    reports = [estimator.update(packet, _twin(packet)) for packet in packets]
    truth_slope = 0.9 / ((len(packets) - 1) * DT)
    checked = 0
    for index, report in enumerate(reports):
        truth_wear = 0.9 * index / (len(packets) - 1)
        if truth_wear < 0.3 or report.rul_s is None:
            continue
        truth_rul = (1.0 - truth_wear) / truth_slope
        assert abs(report.rul_s - truth_rul) / max(truth_rul, 1.0) < 0.25
        assert report.rul_low_s is not None
        assert report.rul_high_s is not None
        assert report.rul_low_s <= report.rul_s <= report.rul_high_s
        checked += 1
    assert checked > 0


def test_health_warning_and_maintenance_events_are_transition_only() -> None:
    packets = wear_ramp_stream(steps=30, wear_start=0.0, wear_end=0.8)
    estimator = HealthEstimator()
    for packet in packets:
        estimator.update(packet, _twin(packet))
    events = estimator.drain_events()

    kinds = [event.kind for event in events]
    assert kinds.count("health_warning") == 1
    assert kinds.count("maintenance_due") == 1
    assert estimator.drain_events() == []


def test_robot_health_state_is_isolated() -> None:
    estimator = HealthEstimator()
    clean = clean_stream(steps=3, robot_id="R1")
    worn = wear_ramp_stream(steps=3, robot_id="D1", robot_type="drone", wear_start=0.8, wear_end=0.9)
    for clean_packet, worn_packet in zip(clean, worn):
        estimator.update(clean_packet, _twin(clean_packet))
        estimator.update(worn_packet, _twin(worn_packet))
    reports = estimator.events
    assert all(event.robot_id == "D1" for event in reports)
