"""Tests for transition-based deviation detection."""
from __future__ import annotations

from app.contract.schemas import StateVec, TwinState
from app.detect.deviation import DeviationDetector


def _twin(
    ts: float,
    *,
    cross_track: float = 0.0,
    heading: float = 0.0,
    residual_pos: float = 0.0,
    residual_norm: float = 0.0,
    robot_id: str = "R1",
) -> TwinState:
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
        residual_pos=residual_pos,
        residual_norm=residual_norm,
        cross_track_err=cross_track,
        heading_err=heading,
        plan_x=10.0,
        plan_y=10.0,
        sync_score=95.0,
        confidence=1.0,
    )


def test_deviation_requires_sustained_error_and_emits_clear_edge() -> None:
    detector = DeviationDetector(confirm_packets=3)

    assert detector.update(_twin(0.0, cross_track=4.0)) == []
    assert detector.update(_twin(0.2, cross_track=4.0)) == []
    events = detector.update(_twin(0.4, cross_track=4.0))
    assert len(events) == 1
    assert events[0].kind == "deviation"
    assert events[0].detail["cause"] == "obstacle"

    assert detector.update(_twin(0.6, cross_track=4.0)) == []
    cleared = detector.update(_twin(0.8))
    assert len(cleared) == 1
    assert cleared[0].kind == "deviation_cleared"


def test_heading_only_error_is_navigation_and_large_residual_is_sensor() -> None:
    navigation = DeviationDetector(confirm_packets=1)
    event = navigation.update(_twin(1.0, heading=0.5))[0]
    assert event.detail["cause"] == "navigation"

    sensor = DeviationDetector(confirm_packets=1)
    event = sensor.update(_twin(1.0, cross_track=4.0, residual_pos=9.0))[0]
    assert event.detail["cause"] == "sensor"


def test_each_event_kind_obeys_cooldown_across_repeated_edges() -> None:
    detector = DeviationDetector(confirm_packets=1, cooldown_s=5.0)
    assert detector.update(_twin(0.0, cross_track=4.0))
    assert detector.update(_twin(0.1))
    # This is a new rising edge, but both event kinds are still cooling down.
    assert detector.update(_twin(1.0, cross_track=4.0)) == []
    assert detector.update(_twin(1.1)) == []
    assert detector.update(_twin(5.1, cross_track=4.0))
    assert detector.update(_twin(5.2))[0].kind == "deviation_cleared"


def test_robot_state_is_isolated() -> None:
    detector = DeviationDetector(confirm_packets=2)
    assert detector.update(_twin(0.0, robot_id="R1", cross_track=4.0)) == []
    assert detector.update(_twin(0.0, robot_id="D1", cross_track=4.0)) == []
    assert detector.update(_twin(0.2, robot_id="R1", cross_track=4.0))
    assert detector.update(_twin(0.2, robot_id="D1", cross_track=4.0))

