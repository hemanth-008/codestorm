"""Pipeline-level dropout tests.

Verify that the real TwinEngine in the pipeline produces:
- Position error < 6 m during 5 s and 10 s outages
- Sync score >= 80 within 5 s of recovery
"""
import math
import pytest

from app.contract.schemas import Telemetry, Mission, Waypoint
from app.contract.physics import DT
from app.sim.world import FleetSim
from app.sim.models import make_model
from app.sim.control import follow
from app.twin.engine import TwinEngine


def _run_dropout(outage_s: float, seed: int = 1):
    """Run a FleetSim, inject a dropout, and measure twin error.

    Returns (max_error_m, sync_after_recovery_5s).
    """
    sim = FleetSim(seed=seed)
    rid = "R1"
    mission = sim.missions()[rid]

    engine = TwinEngine(rid, "rover")
    engine.set_mission(mission)

    max_error_during_outage = 0.0
    inject_time = 10.0  # start dropout at 10 s sim-time
    end_time = inject_time + outage_s
    recovery_check_time = end_time + 5.0
    total_time = recovery_check_time + 1.0

    sync_after_recovery = None

    while sim.now < total_time:
        packets = sim.step(DT)
        in_dropout = inject_time <= sim.now < end_time

        for tel in packets:
            if tel.robot_id != rid:
                continue
            if in_dropout:
                # During dropout: tick the twin but don't feed packets
                ts = engine.tick(sim.now)
                if ts is not None:
                    # Measure error against ground truth
                    truth = sim._robots[rid].state
                    err = math.hypot(ts.est.x - truth.x, ts.est.y - truth.y)
                    max_error_during_outage = max(max_error_during_outage, err)
            else:
                # Feed the packet normally
                ts = engine.on_telemetry(tel)

                # Check sync after recovery
                if sim.now >= end_time and sim.now <= recovery_check_time + 0.5:
                    if ts is not None:
                        sync_after_recovery = ts.sync_score

        # If no packets for this robot during dropout, still tick
        if in_dropout:
            ts = engine.tick(sim.now)
            if ts is not None:
                truth = sim._robots[rid].state
                err = math.hypot(ts.est.x - truth.x, ts.est.y - truth.y)
                max_error_during_outage = max(max_error_during_outage, err)

    return max_error_during_outage, sync_after_recovery


class TestDropoutPipeline:
    """Dropout accuracy in the real pipeline (not eval harness)."""

    def test_5s_dropout_error_under_6m(self):
        max_err, sync = _run_dropout(5.0)
        assert max_err < 6.0, f"5s dropout max error {max_err:.2f} m >= 6 m"

    def test_5s_dropout_sync_recovers(self):
        _, sync = _run_dropout(5.0)
        assert sync is not None, "No sync score recorded after recovery"
        assert sync >= 80.0, f"5s dropout sync {sync:.1f} < 80 after recovery"

    def test_10s_dropout_error_under_6m(self):
        max_err, sync = _run_dropout(10.0)
        assert max_err < 6.0, f"10s dropout max error {max_err:.2f} m >= 6 m"

    def test_10s_dropout_sync_recovers(self):
        _, sync = _run_dropout(10.0)
        assert sync is not None, "No sync score recorded after recovery"
        assert sync >= 80.0, f"10s dropout sync {sync:.1f} < 80 after recovery"

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_5s_dropout_multi_seed(self, seed):
        max_err, sync = _run_dropout(5.0, seed=seed)
        assert max_err < 6.0, f"seed {seed}: 5s dropout max error {max_err:.2f} m"

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_10s_dropout_multi_seed(self, seed):
        max_err, sync = _run_dropout(10.0, seed=seed)
        assert max_err < 6.0, f"seed {seed}: 10s dropout max error {max_err:.2f} m"
