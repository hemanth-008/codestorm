"""FleetSim – the simulated world containing a heterogeneous robot fleet.

Default fleet: R1 (rover), D1 (drone), G1 (AGV) on looping missions.
Two circular obstacles force lateral swerves, producing realistic deviation.

Public API: step, assign_mission, missions, inject, clear, ground_truth.
"""
from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.contract.schemas import (
    AttackKind, AttackSpec, GroundTruth, Mission,
    RobotType, StateVec, Telemetry, Waypoint, Event
)
from app.contract.physics import (
    ARENA_M, DT, DEFAULT_CRUISE, FAILURE_WEAR, clamp,
)
from app.sim.models import Command, RobotModel, make_model
from app.sim.control import follow
from app.sim.faults import apply_attack


# ---------------------------------------------------------------------------
# Obstacle avoidance helpers
# ---------------------------------------------------------------------------
@dataclass
class Obstacle:
    cx: float
    cy: float
    radius: float


# Two obstacles placed near common patrol paths
DEFAULT_OBSTACLES: list[Obstacle] = [
    Obstacle(cx=80.0, cy=50.0, radius=6.0),
    Obstacle(cx=40.0, cy=130.0, radius=5.0),
]

SWERVE_MARGIN_M: float = 2.0  # robots swerve at radius + margin


def _swerve_command(
    s: StateVec,
    cmd: Command,
    obstacles: list[Obstacle],
    robot_type: RobotType,
) -> Command:
    """Apply a lateral swerve if the robot is heading into an obstacle.

    Simple reactive avoidance: if within `radius + SWERVE_MARGIN_M`, steer
    away from the obstacle centre and reduce speed.
    """
    from app.contract.physics import LIMITS
    wmax = LIMITS[robot_type]["wmax"]

    for obs in obstacles:
        dx = s.x - obs.cx
        dy = s.y - obs.cy
        dist = math.hypot(dx, dy)
        avoid_r = obs.radius + SWERVE_MARGIN_M
        if dist < avoid_r and dist > 0.01:
            # Angle from obstacle centre to robot
            away_angle = math.atan2(dy, dx)
            # Signed heading difference toward "away"
            diff = (away_angle - s.heading + math.pi) % (2 * math.pi) - math.pi
            yaw = clamp(3.0 * diff, -wmax, wmax)
            # Reduce speed when close
            speed_factor = clamp((dist - obs.radius) / SWERVE_MARGIN_M, 0.3, 1.0)
            return Command(speed=cmd.speed * speed_factor, yaw_rate=yaw)
    return cmd


# ---------------------------------------------------------------------------
# Per-robot simulation state
# ---------------------------------------------------------------------------
@dataclass
class _RobotSim:
    robot_id: str
    robot_type: RobotType
    model: RobotModel
    state: StateVec
    mission: Optional[Mission] = None
    wp_idx: int = 0
    seq: int = 0
    wear: float = 0.0
    wear_rate: float = 0.0  # per second
    rng: random.Random = field(default_factory=lambda: random.Random(0))

    # Active attack state
    attack: Optional[AttackSpec] = None
    attack_remaining_s: float = 0.0
    _last_clean_state: Optional[StateVec] = None  # for spoof_freeze

    recharge_remaining_s: float = 0.0


# ---------------------------------------------------------------------------
# Default missions (looping patrols inside the arena)
# ---------------------------------------------------------------------------
def _default_missions() -> dict[str, Mission]:
    """Looping patrol missions for R1, D1, G1."""
    return {
        "R1": Mission(
            mission_id="patrol-R1",
            robot_id="R1",
            waypoints=[
                Waypoint(x=20, y=20), Waypoint(x=120, y=20),
                Waypoint(x=120, y=80), Waypoint(x=60, y=80),
                Waypoint(x=60, y=140), Waypoint(x=20, y=140),
            ],
            cruise_speed=DEFAULT_CRUISE["rover"],
            loop=True,
        ),
        "D1": Mission(
            mission_id="patrol-D1",
            robot_id="D1",
            waypoints=[
                Waypoint(x=30, y=170), Waypoint(x=170, y=170),
                Waypoint(x=170, y=30), Waypoint(x=30, y=30),
            ],
            cruise_speed=DEFAULT_CRUISE["drone"],
            loop=True,
        ),
        "G1": Mission(
            mission_id="patrol-G1",
            robot_id="G1",
            waypoints=[
                Waypoint(x=50, y=50), Waypoint(x=150, y=50),
                Waypoint(x=150, y=150), Waypoint(x=50, y=150),
            ],
            cruise_speed=DEFAULT_CRUISE["agv"],
            loop=True,
        ),
    }


def _default_starts() -> dict[str, StateVec]:
    return {
        "R1": StateVec(x=20, y=20, heading=0.0, speed=0.0,
                       battery=100.0, motor_temp=30.0, current=2.0, vibration=0.1),
        "D1": StateVec(x=30, y=170, z=20.0, heading=0.0, speed=0.0,
                       battery=100.0, motor_temp=30.0, current=6.0, vibration=0.2),
        "G1": StateVec(x=50, y=50, heading=0.0, speed=0.0,
                       battery=100.0, motor_temp=30.0, current=3.0, vibration=0.08),
    }


# Wear rates tuned so R1 reaches watch at ~12 min (fails at 40 min),
# D1 and G1 stay OK for >20 min (fail at 80 and 100 min respectively).
_DEFAULT_WEAR_RATES: dict[str, float] = {
    "R1": 1.0 / (40 * 60),
    "D1": 1.0 / (80 * 60),
    "G1": 1.0 / (100 * 60),
}

_ROBOT_TYPES: dict[str, RobotType] = {
    "R1": "rover",
    "D1": "drone",
    "G1": "agv",
}


# ---------------------------------------------------------------------------
# FleetSim
# ---------------------------------------------------------------------------
class FleetSim:
    """Deterministic fleet simulator.

    Usage::

        sim = FleetSim(seed=42)
        for _ in range(1500):          # 5 min @ 5 Hz
            packets = sim.step()       # list[Telemetry]
    """

    def __init__(
        self,
        seed: int = 42,
        wear_rate_scale: float = 1.0,
        robots: list[str] | None = None,
    ) -> None:
        self._rng = random.Random(seed)
        self.now: float = 0.0
        self._obstacles = list(DEFAULT_OBSTACLES)
        self.events: list[Event] = []

        robot_ids = robots or ["R1", "D1", "G1"]
        starts = _default_starts()
        missions = _default_missions()

        self._robots: dict[str, _RobotSim] = {}
        for rid in robot_ids:
            rtype = _ROBOT_TYPES[rid]
            model = make_model(rtype)
            rs = _RobotSim(
                robot_id=rid,
                robot_type=rtype,
                model=model,
                state=starts[rid].model_copy(),
                mission=missions.get(rid),
                wear_rate=_DEFAULT_WEAR_RATES[rid] * wear_rate_scale,
                rng=random.Random(self._rng.randint(0, 2**31)),
            )
            self._robots[rid] = rs

    # ---- Public API -------------------------------------------------------

    def step(self, dt: float = DT) -> list[Telemetry]:
        """Advance simulation by *dt*; return telemetry packets that arrive.

        Dropped packets (from dropout attacks) are omitted from the list.
        """
        self.now += dt
        packets: list[Telemetry] = []

        for rs in self._robots.values():
            # --- Wear ---
            if rs.wear < FAILURE_WEAR and rs.recharge_remaining_s <= 0:
                rs.wear += rs.wear_rate * dt
                rs.wear = min(rs.wear, FAILURE_WEAR)

            # --- Control ---
            cmd = Command(speed=0.0, yaw_rate=0.0)
            if rs.recharge_remaining_s > 0:
                pass # speed 0 command
            elif rs.mission and rs.wear < FAILURE_WEAR:
                old_idx = rs.wp_idx
                cmd, rs.wp_idx, _done = follow(
                    rs.state, rs.mission.waypoints, rs.wp_idx,
                    rs.mission.cruise_speed, rs.robot_type,
                )
                
                if old_idx == 0 and rs.wp_idx == 1 and rs.state.battery < 30.0:
                    rs.recharge_remaining_s = 20.0
                    cmd = Command(speed=0.0, yaw_rate=0.0)
                    self.events.append(Event(
                        id=str(uuid.uuid4()),
                        ts=self.now,
                        robot_id=rs.robot_id,
                        kind="auto_recharge",
                        severity="info",
                        message=f"Battery low ({rs.state.battery:.1f}%), auto-recharging at base."
                    ))

                if _done and rs.mission.loop:
                    rs.wp_idx = 0

            # Obstacle avoidance
            cmd = _swerve_command(rs.state, cmd, self._obstacles, rs.robot_type)

            # --- Step the physics ---
            rs.state = rs.model.step(rs.state, cmd, dt, wear=rs.wear, rng=rs.rng)

            # --- Auto-recharge battery override ---
            if rs.recharge_remaining_s > 0:
                rs.recharge_remaining_s -= dt
                rs.state.battery += (100.0 / 20.0) * dt
                rs.state.battery = min(100.0, rs.state.battery)
                if rs.recharge_remaining_s <= 0:
                    rs.recharge_remaining_s = 0.0
                    rs.state.battery = 100.0

            # Clamp to arena
            rs.state = rs.state.model_copy(update={
                "x": clamp(rs.state.x, 0.0, ARENA_M),
                "y": clamp(rs.state.y, 0.0, ARENA_M),
            })

            # --- Build telemetry packet (clean, before faults) ---
            rs.seq += 1
            tel = Telemetry(
                robot_id=rs.robot_id,
                robot_type=rs.robot_type,
                ts=self.now,
                seq=rs.seq,
                x=rs.state.x,
                y=rs.state.y,
                z=rs.state.z,
                heading=rs.state.heading,
                speed=rs.state.speed,
                battery=rs.state.battery,
                motor_temp=rs.state.motor_temp,
                current=rs.state.current,
                vibration=rs.state.vibration,
            )

            # --- Apply active attack to the PACKET (not the true state) ---
            if rs.attack and rs.attack_remaining_s > 0:
                tel = apply_attack(tel, rs.attack, rs.rng, rs.attack_remaining_s, rs._last_clean_state)
                rs.attack_remaining_s -= dt
                if rs.attack_remaining_s <= 0:
                    rs.attack = None
                    rs.attack_remaining_s = 0.0
                    rs._last_clean_state = None

                # Dropout means the packet is NOT delivered
                if rs.attack and rs.attack.kind == "dropout":
                    continue
            # Packet delivered
            packets.append(tel)

        return packets

    def assign_mission(self, m: Mission) -> None:
        """Assign (or replace) a mission for the given robot."""
        rs = self._robots[m.robot_id]
        rs.mission = m
        rs.wp_idx = 0

    def missions(self) -> dict[str, Mission]:
        """Return the current mission for each robot."""
        return {
            rid: rs.mission
            for rid, rs in self._robots.items()
            if rs.mission is not None
        }

    def inject(self, spec: AttackSpec) -> None:
        """Start a fault/attack on a specific robot."""
        rs = self._robots[spec.robot_id]
        rs.attack = spec
        rs.attack_remaining_s = spec.duration_s
        # Snapshot clean state for spoof_freeze
        if spec.kind == "spoof_freeze":
            rs._last_clean_state = rs.state.model_copy()

    def clear(self, robot_id: str | None = None) -> None:
        """Clear active attacks. If robot_id is None, clear all."""
        targets = [robot_id] if robot_id else list(self._robots.keys())
        for rid in targets:
            rs = self._robots[rid]
            rs.attack = None
            rs.attack_remaining_s = 0.0
            rs._last_clean_state = None

    def ground_truth(self, robot_id: str) -> GroundTruth:
        """Return the ground truth for the given robot."""
        rs = self._robots[robot_id]
        ttf: Optional[float] = None
        if rs.wear < FAILURE_WEAR and rs.wear_rate > 0:
            ttf = (FAILURE_WEAR - rs.wear) / rs.wear_rate
        return GroundTruth(
            robot_id=robot_id,
            wear=rs.wear,
            time_to_failure_s=ttf,
            attack_active=rs.attack.kind if rs.attack else None,
        )

    # ---- Internal ---------------------------------------------------------

