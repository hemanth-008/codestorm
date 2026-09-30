"""Pure-pursuit path follower for the FleetTwin simulator.

Waypoint reached when distance < REACH_M.  Lookahead circle at LOOKAHEAD_M.
The robot steers toward the intersection of the lookahead circle with the
path segment, producing smooth curves rather than hard turns.

Loop support: when `mission.loop` is True and the last waypoint is reached,
the index wraps back to 0.
"""
from __future__ import annotations

import math

from app.contract.schemas import StateVec, Waypoint, RobotType
from app.contract.physics import LIMITS, clamp
from app.sim.models import Command

LOOKAHEAD_M: float = 4.0
REACH_M: float = 3.0


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(bx - ax, by - ay)


def _angle_diff(a: float, b: float) -> float:
    """Signed shortest angular difference (radians), result in [-pi, pi]."""
    d = (a - b) % (2 * math.pi)
    if d > math.pi:
        d -= 2 * math.pi
    return d


def follow(
    s: StateVec,
    wps: list[Waypoint],
    idx: int,
    cruise: float,
    robot_type: RobotType,
) -> tuple[Command, int, bool]:
    """Pure-pursuit controller.

    Parameters
    ----------
    s : StateVec
        Current robot state.
    wps : list[Waypoint]
        Ordered waypoints of the mission.
    idx : int
        Index of the next waypoint the robot is heading toward.
    cruise : float
        Desired cruise speed (m/s).
    robot_type : RobotType
        Robot type string (for looking up limits).

    Returns
    -------
    (Command, new_idx, done)
        The steering command, possibly updated waypoint index, and whether
        the mission is complete.
    """
    if not wps:
        return Command(speed=0.0, yaw_rate=0.0), idx, True

    n = len(wps)
    lim = LIMITS[robot_type]
    wmax = lim["wmax"]
    vmax = lim["vmax"]

    # Advance past any waypoints already reached
    max_advance = n  # guard against infinite loop
    advanced = 0
    while advanced < max_advance:
        wp = wps[idx % n]
        d = _dist(s.x, s.y, wp.x, wp.y)
        if d >= REACH_M:
            break
        idx += 1
        advanced += 1
        if idx >= n:
            # Completed a full pass
            idx = 0
            return Command(speed=0.0, yaw_rate=0.0), idx, True

    # Target: the current waypoint (could be smarter with segment intersection)
    target = wps[idx % n]
    tx, ty = target.x, target.y

    # Look-ahead: if close to current wp, blend toward the next one
    d_target = _dist(s.x, s.y, tx, ty)
    if d_target < LOOKAHEAD_M and n > 1:
        next_wp = wps[(idx + 1) % n]
        blend = 1.0 - d_target / LOOKAHEAD_M  # 0 at lookahead, 1 at waypoint
        tx = tx + blend * (next_wp.x - tx)
        ty = ty + blend * (next_wp.y - ty)

    # Desired heading toward target
    desired_heading = math.atan2(ty - s.y, tx - s.x)
    heading_err = _angle_diff(desired_heading, s.heading)

    # Proportional yaw controller (P-gain 2.0, clamped to wmax)
    yaw_rate = clamp(2.0 * heading_err, -wmax, wmax)

    # Slow down when turning hard (reduce speed proportional to heading error)
    turn_factor = max(0.3, 1.0 - abs(heading_err) / math.pi)
    speed = clamp(cruise * turn_factor, 0.0, vmax)

    return Command(speed=speed, yaw_rate=yaw_rate), idx, False
