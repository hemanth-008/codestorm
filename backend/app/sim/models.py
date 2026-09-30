"""Robot kinematic models for the FleetTwin simulator.

Each model implements a `step` method that advances the state by `dt` seconds
given a `Command`. The wear parameter degrades performance (higher current,
temperature, vibration) but does NOT change kinematics until wear >= 1.0
(failure, speed forced to 0).
"""
from __future__ import annotations

import math
from typing import Literal

from app.contract.schemas import StateVec, RobotType
from app.contract.physics import (
    LIMITS, DT, FAILURE_WEAR, T_AMB, K_THERMAL, THERMAL_TAU_S,
    WEAR_CURRENT_GAIN, WEAR_VIB_GAIN,
    expected_current, expected_drain_pct_per_s, expected_vibration, clamp,
)

from pydantic import BaseModel


class Command(BaseModel):
    """Desired speed (m/s) and yaw rate (rad/s)."""
    speed: float
    yaw_rate: float


class RobotModel:
    """Base kinematic/thermal model for a single robot type.

    Kinematics:
      heading += yaw_rate * dt       (clamped to wmax)
      speed    = clamp(cmd.speed, 0, vmax)  (0 if failed)
      x       += speed * cos(heading) * dt
      y       += speed * sin(heading) * dt

    For the drone: z is fixed at DRONE_ALT (20 m) and wind gusts add
    random perturbation (handled in step via an optional rng).
    """

    DRONE_ALT: float = 20.0

    def __init__(self, robot_type: RobotType) -> None:
        self.robot_type: RobotType = robot_type
        lim = LIMITS[robot_type]
        self.vmax: float = lim["vmax"]
        self.amax: float = lim["amax"]
        self.wmax: float = lim["wmax"]

    def step(
        self,
        s: StateVec,
        cmd: Command,
        dt: float,
        wear: float = 0.0,
        rng=None,
    ) -> StateVec:
        """Advance the state by *dt* seconds.

        Parameters
        ----------
        s : StateVec
            Current state.
        cmd : Command
            Desired speed and yaw rate.
        dt : float
            Time step (s).
        wear : float
            Wear level [0, 1]. At >= FAILURE_WEAR the robot stops.
        rng : random.Random | None
            Used only by the drone for wind gusts.

        Returns
        -------
        StateVec
            Updated state after the step.
        """
        failed = wear >= FAILURE_WEAR

        # --- Yaw ---
        yaw_rate = clamp(cmd.yaw_rate, -self.wmax, self.wmax)
        heading = s.heading + yaw_rate * dt

        # --- Speed (rate-limited) ---
        desired_speed = 0.0 if failed else clamp(cmd.speed, 0.0, self.vmax)
        max_dv = self.amax * dt
        speed = s.speed + clamp(desired_speed - s.speed, -max_dv, max_dv)
        speed = clamp(speed, 0.0, self.vmax)

        # --- Position ---
        x = s.x + speed * math.cos(heading) * dt
        y = s.y + speed * math.sin(heading) * dt
        z = s.z

        # Drone wind gusts (small random perturbation)
        if self.robot_type == "drone" and rng is not None and not failed:
            x += rng.gauss(0, 0.05) * dt
            y += rng.gauss(0, 0.05) * dt
            z = self.DRONE_ALT  # fixed altitude

        if self.robot_type == "drone":
            z = self.DRONE_ALT

        # --- Battery drain ---
        drain_rate = expected_drain_pct_per_s(self.robot_type, speed)
        battery = max(0.0, s.battery - drain_rate * dt)

        # --- Current (wear inflates it) ---
        base_current = expected_current(self.robot_type, speed)
        current = base_current * (1.0 + WEAR_CURRENT_GAIN * wear)

        # --- Temperature (first-order lag toward steady state) ---
        t_ss = T_AMB + K_THERMAL * current
        motor_temp = s.motor_temp + (t_ss - s.motor_temp) * dt / THERMAL_TAU_S

        # --- Vibration (wear inflates it) ---
        base_vib = expected_vibration(self.robot_type, speed)
        vibration = base_vib + WEAR_VIB_GAIN * wear
        # Add a tiny deterministic jitter so it's not perfectly flat
        vibration += 0.001 * math.sin(speed * 7.3 + wear * 11.1)

        return StateVec(
            x=x, y=y, z=z,
            heading=heading,
            speed=speed,
            battery=battery,
            motor_temp=motor_temp,
            current=current,
            vibration=vibration,
        )


def make_model(robot_type: RobotType) -> RobotModel:
    """Factory: return the appropriate RobotModel for the given type."""
    return RobotModel(robot_type)
