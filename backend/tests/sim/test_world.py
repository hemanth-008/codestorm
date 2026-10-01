"""Tests for sim/world.py – FleetSim determinism, limits, wear, ground_truth."""
from __future__ import annotations

import time as _time

from app.contract.schemas import AttackSpec, Mission, Waypoint
from app.contract.physics import ARENA_M, DT, FAILURE_WEAR, LIMITS
from app.sim.world import FleetSim


FIVE_MIN_STEPS = int(5 * 60 / DT)  # 1500 steps


class TestDeterminism:
    """Same seed must produce identical output."""

    def test_two_runs_identical(self):
        sim1 = FleetSim(seed=42)
        sim2 = FleetSim(seed=42)
        for _ in range(200):
            p1 = sim1.step()
            p2 = sim2.step()
            assert len(p1) == len(p2)
            for t1, t2 in zip(p1, p2):
                assert t1.robot_id == t2.robot_id
                assert abs(t1.x - t2.x) < 1e-9
                assert abs(t1.y - t2.y) < 1e-9


class TestLimits:
    """All telemetry must stay within physics LIMITS and the arena."""

    def test_telemetry_within_limits(self):
        sim = FleetSim(seed=7)
        for _ in range(500):
            for tel in sim.step():
                lim = LIMITS[tel.robot_type]
                assert tel.speed <= lim["vmax"] + 0.01, \
                    f"{tel.robot_id} speed {tel.speed} > vmax {lim['vmax']}"
                assert 0.0 <= tel.x <= ARENA_M + 0.01
                assert 0.0 <= tel.y <= ARENA_M + 0.01
                assert tel.battery >= 0.0
                assert tel.battery <= 100.0


class TestWear:
    """Wear should rise, and current/temp/vib should visibly increase."""

    def test_wear_rises(self):
        sim = FleetSim(seed=42)
        gt0 = sim.ground_truth("R1")
        for _ in range(500):
            sim.step()
        gt1 = sim.ground_truth("R1")
        assert gt1.wear > gt0.wear

    def test_current_temp_vib_rise_with_wear(self):
        """Compare two separate sims at same time offset: one with wear (default)
        vs one without (wear_rate_scale=0). Current and vibration should be
        higher in the worn sim."""
        sim_wear = FleetSim(seed=42, wear_rate_scale=1.0)
        sim_clean = FleetSim(seed=42, wear_rate_scale=0.0)
        # Skip to steady state
        for _ in range(500):
            sim_wear.step()
            sim_clean.step()
        # Collect samples
        wear_current = []
        wear_vib = []
        clean_current = []
        clean_vib = []
        for _ in range(200):
            for tel in sim_wear.step():
                if tel.robot_id == "R1":
                    wear_current.append(tel.current)
                    wear_vib.append(tel.vibration)
            for tel in sim_clean.step():
                if tel.robot_id == "R1":
                    clean_current.append(tel.current)
                    clean_vib.append(tel.vibration)
        avg_w_cur = sum(wear_current) / len(wear_current)
        avg_c_cur = sum(clean_current) / len(clean_current)
        avg_w_vib = sum(wear_vib) / len(wear_vib)
        avg_c_vib = sum(clean_vib) / len(clean_vib)
        assert avg_w_cur > avg_c_cur, f"worn current {avg_w_cur:.3f} <= clean {avg_c_cur:.3f}"
        assert avg_w_vib > avg_c_vib, f"worn vib {avg_w_vib:.3f} <= clean {avg_c_vib:.3f}"

    def test_robot_stops_at_failure(self):
        """With high wear_rate_scale, robot should stop within a reasonable time."""
        sim = FleetSim(seed=42, wear_rate_scale=20.0)
        for _ in range(FIVE_MIN_STEPS):
            sim.step()
        gt = sim.ground_truth("R1")
        assert gt.wear >= FAILURE_WEAR


class TestGroundTruth:
    def test_time_to_failure(self):
        sim = FleetSim(seed=42)
        gt = sim.ground_truth("R1")
        assert gt.time_to_failure_s is not None
        assert gt.time_to_failure_s > 0

    def test_no_attack_by_default(self):
        sim = FleetSim(seed=42)
        gt = sim.ground_truth("R1")
        assert gt.attack_active is None
        
class TestAutoRecharge:
    def test_auto_recharge(self):
        sim = FleetSim(seed=42)
        # Drain the battery manually to < 30
        sim._robots["R1"].state.battery = 29.0
        # Fast forward simulation to let it loop and recharge
        recharge_started = False
        recharge_finished = False
        for _ in range(3000): # 10 mins
            sim.step()
            for evt in sim.events:
                if evt.kind == "auto_recharge" and evt.robot_id == "R1" and "auto-recharging" in evt.message:
                    recharge_started = True
            sim.events.clear()
            if recharge_started and sim._robots["R1"].state.battery == 100.0:
                recharge_finished = True
                break
        assert recharge_started
        assert recharge_finished


class TestMissions:
    def test_default_missions(self):
        sim = FleetSim(seed=42)
        m = sim.missions()
        assert "R1" in m
        assert "D1" in m
        assert "G1" in m

    def test_assign_mission(self):
        sim = FleetSim(seed=42)
        new_m = Mission(
            mission_id="test-1",
            robot_id="R1",
            waypoints=[Waypoint(x=30, y=30), Waypoint(x=100, y=100)],
            cruise_speed=1.0,
        )
        sim.assign_mission(new_m)
        assert sim.missions()["R1"].mission_id == "test-1"


class TestPerformance:
    """5 min of headless sim must run in under 3 s."""

    def test_five_min_under_three_seconds(self):
        t0 = _time.perf_counter()
        sim = FleetSim(seed=42)
        for _ in range(FIVE_MIN_STEPS):
            sim.step()
        elapsed = _time.perf_counter() - t0
        assert elapsed < 3.0, f"5 min sim took {elapsed:.2f}s (limit: 3s)"

