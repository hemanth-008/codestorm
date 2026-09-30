"""Tests for sim/models.py – robot kinematics, battery, thermal, vibration."""
from __future__ import annotations

import math

from app.contract.schemas import StateVec
from app.contract.physics import (
    LIMITS, FAILURE_WEAR, T_AMB, K_THERMAL, DT,
    expected_current, expected_vibration,
)
from app.sim.models import Command, RobotModel, make_model


def _fresh_state(robot_type: str) -> StateVec:
    z = 20.0 if robot_type == "drone" else 0.0
    return StateVec(
        x=50.0, y=50.0, z=z, heading=0.0, speed=0.0,
        battery=100.0, motor_temp=T_AMB, current=2.0, vibration=0.1,
    )


class TestMakeModel:
    def test_returns_robot_model(self):
        for rt in ("rover", "drone", "agv"):
            m = make_model(rt)
            assert isinstance(m, RobotModel)
            assert m.robot_type == rt

    def test_limits_are_loaded(self):
        m = make_model("rover")
        assert m.vmax == LIMITS["rover"]["vmax"]
        assert m.wmax == LIMITS["rover"]["wmax"]


class TestRoverStep:
    """Rover is a unicycle: heading += yaw_rate*dt, x += speed*cos(h)*dt."""

    def test_straight_line(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        cmd = Command(speed=1.5, yaw_rate=0.0)
        s2 = m.step(s, cmd, DT)
        # Should move in +x direction (heading=0)
        assert s2.x > s.x
        assert abs(s2.y - s.y) < 1e-6  # no lateral motion

    def test_turn(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        cmd = Command(speed=1.0, yaw_rate=1.0)
        s2 = m.step(s, cmd, DT)
        assert s2.heading > s.heading  # heading increased

    def test_speed_clamped_to_vmax(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        cmd = Command(speed=999.0, yaw_rate=0.0)
        # Multiple steps to allow acceleration
        for _ in range(100):
            s = m.step(s, cmd, DT)
        assert s.speed <= LIMITS["rover"]["vmax"] + 1e-9

    def test_yaw_clamped_to_wmax(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        cmd = Command(speed=0.0, yaw_rate=999.0)
        s2 = m.step(s, cmd, DT)
        expected_heading = s.heading + LIMITS["rover"]["wmax"] * DT
        assert abs(s2.heading - expected_heading) < 1e-9

    def test_battery_drains(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        cmd = Command(speed=1.5, yaw_rate=0.0)
        for _ in range(50):
            s = m.step(s, cmd, DT)
        assert s.battery < 100.0

    def test_current_rises_with_speed(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        cmd_slow = Command(speed=0.5, yaw_rate=0.0)
        cmd_fast = Command(speed=2.0, yaw_rate=0.0)
        # Spin up both
        s_slow = s.model_copy()
        s_fast = s.model_copy()
        for _ in range(50):
            s_slow = m.step(s_slow, cmd_slow, DT)
            s_fast = m.step(s_fast, cmd_fast, DT)
        assert s_fast.current > s_slow.current


class TestDroneStep:
    def test_fixed_altitude(self):
        m = make_model("drone")
        s = _fresh_state("drone")
        cmd = Command(speed=5.0, yaw_rate=0.0)
        for _ in range(50):
            s = m.step(s, cmd, DT)
        assert s.z == 20.0

    def test_higher_vmax(self):
        assert LIMITS["drone"]["vmax"] > LIMITS["rover"]["vmax"]


class TestAGVStep:
    def test_lower_yaw_rate(self):
        assert LIMITS["agv"]["wmax"] < LIMITS["rover"]["wmax"]

    def test_moves(self):
        m = make_model("agv")
        s = _fresh_state("agv")
        cmd = Command(speed=2.0, yaw_rate=0.0)
        for _ in range(50):
            s = m.step(s, cmd, DT)
        assert s.x > 50.0  # moved forward


class TestWear:
    def test_failure_stops_robot(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        # First get some speed
        cmd = Command(speed=1.5, yaw_rate=0.0)
        for _ in range(20):
            s = m.step(s, cmd, DT, wear=0.0)
        assert s.speed > 0.0
        # Now step with wear = FAILURE_WEAR
        s2 = m.step(s, cmd, DT, wear=FAILURE_WEAR)
        # After enough steps the speed should go to 0
        for _ in range(100):
            s2 = m.step(s2, cmd, DT, wear=FAILURE_WEAR)
        assert s2.speed < 1e-6

    def test_wear_increases_current(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        cmd = Command(speed=1.5, yaw_rate=0.0)
        # Run to steady state at wear=0
        for _ in range(50):
            s = m.step(s, cmd, DT, wear=0.0)
        c0 = s.current
        # Reset and run at wear=0.5
        s2 = _fresh_state("rover")
        for _ in range(50):
            s2 = m.step(s2, cmd, DT, wear=0.5)
        assert s2.current > c0

    def test_wear_increases_vibration(self):
        m = make_model("rover")
        s = _fresh_state("rover")
        cmd = Command(speed=1.5, yaw_rate=0.0)
        for _ in range(50):
            s = m.step(s, cmd, DT, wear=0.0)
        v0 = s.vibration
        s2 = _fresh_state("rover")
        for _ in range(50):
            s2 = m.step(s2, cmd, DT, wear=0.5)
        assert s2.vibration > v0

    def test_temperature_rises_with_wear(self):
        """Higher wear → higher current → higher steady-state temperature."""
        m = make_model("rover")
        cmd = Command(speed=1.5, yaw_rate=0.0)
        # Long run at wear=0
        s0 = _fresh_state("rover")
        for _ in range(500):
            s0 = m.step(s0, cmd, DT, wear=0.0)
        # Long run at wear=0.8
        s1 = _fresh_state("rover")
        for _ in range(500):
            s1 = m.step(s1, cmd, DT, wear=0.8)
        assert s1.motor_temp > s0.motor_temp
