"""Tests for Eval 4 features: flat history, maintenance log, lifetime ref, critical events."""
import asyncio
import time
import pytest
from fastapi.testclient import TestClient

import os
os.environ.setdefault("SIM_ENABLED", "0")

from main import app
from app.core.pipeline import pipeline
from app.contract.schemas import Telemetry


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def _seed_telemetry(client):
    """Feed a few telemetry packets so history and events exist."""
    base_ts = 1.0
    for i in range(5):
        tel = Telemetry(
            robot_id="R1", robot_type="rover", ts=base_ts + i * 0.2, seq=i + 1,
            x=10.0 + i * 2.0, y=20.0 + i, z=0.0, heading=0.1 * i,
            speed=1.0 + 0.1 * i, battery=100.0 - i * 0.5,
            motor_temp=30.0 + i * 2.0, current=5.0 + i * 0.3,
            vibration=0.2 + i * 0.05,
        )
        asyncio.run(pipeline.process_telemetry(tel))


class TestFlatHistory:
    """GET /api/robots/{id} history should have sensor values at top level."""

    def test_history_has_top_level_battery(self, client, _seed_telemetry):
        r = client.get("/api/robots/R1")
        assert r.status_code == 200
        history = r.json()["history"]
        assert len(history) >= 1
        h = history[-1]
        # battery must be at top level, not nested in est
        assert "battery" in h, "battery should be a top-level field"
        assert "motor_temp" in h, "motor_temp should be a top-level field"
        assert "speed" in h, "speed should be a top-level field"
        assert "x" in h, "x should be a top-level field"

    def test_history_values_vary(self, client, _seed_telemetry):
        r = client.get("/api/robots/R1")
        history = r.json()["history"]
        if len(history) < 2:
            pytest.skip("Need at least 2 history entries")
        batteries = [h["battery"] for h in history]
        # At least some variation
        assert len(set(batteries)) > 1, "Battery values should vary over time"

    def test_history_has_ts(self, client, _seed_telemetry):
        r = client.get("/api/robots/R1")
        history = r.json()["history"]
        assert all("ts" in h for h in history)

    def test_history_preserves_pred(self, client, _seed_telemetry):
        r = client.get("/api/robots/R1")
        history = r.json()["history"]
        h = history[-1]
        assert "pred" in h, "pred should still be available"
        assert isinstance(h["pred"], dict)
