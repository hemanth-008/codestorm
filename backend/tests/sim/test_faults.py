"""Tests for sim/faults.py – fault injection logic."""
from __future__ import annotations

import math
import random

from app.contract.schemas import AttackSpec, StateVec, Telemetry
from app.sim.faults import apply_attack


def _dummy_tel(x: float = 10.0, y: float = 10.0, speed: float = 1.0) -> Telemetry:
    return Telemetry(
        robot_id="R1",
        robot_type="rover",
        ts=1.0,
        seq=1,
        x=x,
        y=y,
        z=0.0,
        heading=0.0,
        speed=speed,
        battery=100.0,
        motor_temp=30.0,
        current=2.0,
        vibration=0.1,
    )


def _dummy_state(x: float = 10.0, y: float = 10.0) -> StateVec:
    return StateVec(
        x=x,
        y=y,
        z=0.0,
        heading=0.0,
        speed=1.0,
        battery=100.0,
        motor_temp=30.0,
        current=2.0,
        vibration=0.1,
    )


class TestApplyAttack:
    def test_no_attack(self):
        tel = _dummy_tel()
        res = apply_attack(tel, None, random.Random(0), 10.0, None)
        assert res.x == tel.x
        assert res.speed == tel.speed

    def test_noise(self):
        tel = _dummy_tel(x=10.0, y=10.0, speed=2.0)
        atk = AttackSpec(robot_id="R1", kind="noise", magnitude=1.0, duration_s=10.0)
        # Apply multiple times to see variation
        rng = random.Random(42)
        diff_x = False
        diff_speed = False
        for _ in range(10):
            res = apply_attack(tel, atk, rng, 10.0, None)
            if abs(res.x - tel.x) > 1e-3:
                diff_x = True
            if abs(res.speed - tel.speed) > 1e-3:
                diff_speed = True
        assert diff_x
        assert diff_speed
        
    def test_spoof_freeze(self):
        # Even as true telemetry advances, the packet should output the frozen values
        tel1 = _dummy_tel(x=12.0)
        frozen = _dummy_state(x=10.0)
        atk = AttackSpec(robot_id="R1", kind="spoof_freeze", magnitude=1.0, duration_s=10.0)
        res1 = apply_attack(tel1, atk, random.Random(0), 10.0, frozen)
        assert res1.x == 10.0

    def test_spoof_jump(self):
        tel = _dummy_tel(x=10.0, y=10.0)
        atk = AttackSpec(robot_id="R1", kind="spoof_jump", magnitude=20.0, duration_s=10.0)
        res = apply_attack(tel, atk, random.Random(0), 10.0, None)
        dist = math.hypot(res.x - tel.x, res.y - tel.y)
        assert abs(dist - 20.0) < 1e-3

    def test_spoof_drift(self):
        tel = _dummy_tel(x=10.0, y=10.0)
        atk = AttackSpec(robot_id="R1", kind="spoof_drift", magnitude=2.0, duration_s=10.0)
        # At start (remaining_s = 10.0) elapsed = 0
        res0 = apply_attack(tel, atk, random.Random(0), 10.0, None)
        assert res0.x == 10.0
        
        # After 5 seconds, drift is magnitude * 5 = 10.0 meters
        res5 = apply_attack(tel, atk, random.Random(0), 5.0, None)
        dist = math.hypot(res5.x - tel.x, res5.y - tel.y)
        assert abs(dist - 10.0) < 1e-3

    def test_spoof_battery(self):
        tel = _dummy_tel()
        tel.battery = 50.0
        atk = AttackSpec(robot_id="R1", kind="spoof_battery", magnitude=-20.0, duration_s=10.0)
        res = apply_attack(tel, atk, random.Random(0), 10.0, None)
        assert res.battery == 30.0

    def test_dropout_returns_same(self):
        # apply_attack does nothing for dropout; the sim loop drops the packet entirely
        tel = _dummy_tel()
        atk = AttackSpec(robot_id="R1", kind="dropout", duration_s=10.0)
        res = apply_attack(tel, atk, random.Random(0), 10.0, None)
        assert res.model_dump() == tel.model_dump()
