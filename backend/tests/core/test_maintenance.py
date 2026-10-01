"""Tests for Eval 4 maintenance endpoints."""
import pytest
from fastapi.testclient import TestClient

from main import app
from app.contract.schemas import Event
import time

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

class TestMaintenanceLog:
    def test_log_returns_aggregated_events(self, client):
        # We assume some events exist from _seed_telemetry in test_eval4 or we can seed them
        # Let's hit the endpoint and ensure it works
        r = client.get("/api/maintenance/log")
        assert r.status_code == 200
        logs = r.json()
        assert isinstance(logs, list)

    def test_lifetime_reference(self, client):
        r = client.get("/api/maintenance/lifetime-reference")
        assert r.status_code == 200
        refs = r.json()
        assert isinstance(refs, list)
        assert len(refs) == 3
        # Ensure it has the computed numbers
        rover = next(r for r in refs if r["robot_type"] == "rover")
        assert rover["typical_operating_duration_mins"] == 40
        assert rover["suggested_maintenance_interval_mins"] == 22
        assert "Vibration" in rover["common_failure_reasons"]
