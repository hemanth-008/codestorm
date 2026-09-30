"""Tests for sim/control.py – pure-pursuit path follower."""
from __future__ import annotations

import math

from app.contract.schemas import StateVec, Waypoint
from app.contract.physics import T_AMB
from app.sim.control import follow, REACH_M


def _state(x: float, y: float, heading: float = 0.0, speed: float = 1.0) -> StateVec:
    return StateVec(
        x=x, y=y, heading=heading, speed=speed,
        battery=100.0, motor_temp=T_AMB, current=2.0, vibration=0.1,
    )


class TestFollow:
    def test_empty_waypoints_done(self):
        s = _state(0, 0)
        cmd, idx, done = follow(s, [], 0, 1.5, "rover")
        assert done
        assert cmd.speed == 0.0

    def test_reaches_waypoint(self):
        wps = [Waypoint(x=10, y=0)]
        s = _state(0, 0, heading=0.0)
        # Run the follower in a simulated loop
        from app.sim.models import make_model
        from app.contract.physics import DT
        model = make_model("rover")
        idx = 0
        for step in range(500):
            cmd, idx, done = follow(s, wps, idx, 1.5, "rover")
            if done:
                break
            s = model.step(s, cmd, DT)
        assert done, f"Did not reach waypoint after 500 steps, pos=({s.x:.1f},{s.y:.1f})"

    def test_multiple_waypoints(self):
        wps = [Waypoint(x=10, y=0), Waypoint(x=10, y=10), Waypoint(x=0, y=10)]
        s = _state(0, 0, heading=0.0)
        from app.sim.models import make_model
        from app.contract.physics import DT
        model = make_model("rover")
        idx = 0
        done = False
        for _ in range(2000):
            cmd, idx, done = follow(s, wps, idx, 1.5, "rover")
            if done:
                break
            s = model.step(s, cmd, DT)
        assert done

    def test_loop_does_not_finish(self):
        """With loop=True the sim should keep going; follow itself returns done
        after one pass and the caller resets idx to 0."""
        wps = [Waypoint(x=10, y=0)]
        s = _state(9.5, 0, heading=0.0)  # already near the waypoint
        cmd, idx, done = follow(s, wps, 0, 1.5, "rover")
        # At idx=0, within REACH_M -> done=True, idx wraps
        assert done

    def test_steers_toward_target(self):
        """Robot at origin facing +x, waypoint at (10, 10) => yaw_rate > 0."""
        wps = [Waypoint(x=10, y=10)]
        s = _state(0, 0, heading=0.0)
        cmd, _, _ = follow(s, wps, 0, 1.5, "rover")
        assert cmd.yaw_rate > 0  # needs to turn left (CCW)

    def test_slows_for_sharp_turn(self):
        """When the heading error is large, speed should be reduced."""
        wps = [Waypoint(x=-10, y=0)]  # behind the robot
        s = _state(0, 0, heading=0.0)
        cmd, _, _ = follow(s, wps, 0, 1.5, "rover")
        assert cmd.speed < 1.5  # reduced from cruise
