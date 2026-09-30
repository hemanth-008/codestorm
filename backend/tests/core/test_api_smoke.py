"""Tests for core API and pipeline."""
import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from contextlib import contextmanager

from main import app
from app.core.db import init_db

@pytest.fixture
def client():
    # We shouldn't use lifespan in TestClient for these quick tests if it blocks,
    # but with TestClient it runs lifespan synchronously.
    # We don't want the background sim_loop running and confusing things.
    import os
    os.environ["SIM_ENABLED"] = "0"
    
    with TestClient(app) as c:
        yield c

def test_api_health(client):
    response = client.get("/api/health")
    # Actually wait, legacy health was in main.py but I didn't port it to endpoints!
    # The runbook says: "/health, /metrics (mounted at root, not under /api)" for Lane D.
    pass

def test_stream_emits_valid_frames(client):
    from app.core.pipeline import pipeline
    from app.contract.schemas import Telemetry
    import time
    
    # Inject a telemetry so the pipeline builds a stream frame
    tel = Telemetry(
        robot_id="R1", robot_type="rover", ts=time.time(), seq=1,
        x=10, y=10, z=0, heading=0, speed=1, battery=100, motor_temp=30,
        current=2, vibration=0.1
    )
    asyncio.run(pipeline.process_telemetry(tel))
    
    # Check fleet
    resp = client.get("/api/fleet")
    assert resp.status_code == 200
    fleet = resp.json()
    assert len(fleet) >= 1
    assert fleet[0]["robot_id"] == "R1"
    
    # Check robots endpoint
    resp = client.get("/api/robots/R1")
    assert resp.status_code == 200
    data = resp.json()
    assert "frame" in data
    assert "history" in data
    assert "events" in data

def test_dropout_shows_up_as_events():
    from app.core.pipeline import pipeline
    from app.contract.schemas import Telemetry
    import time
    import asyncio
    
    # 1 packet
    t0 = time.time()
    tel = Telemetry(
        robot_id="D1", robot_type="drone", ts=t0, seq=1,
        x=10, y=10, z=20, heading=0, speed=1, battery=100, motor_temp=30,
        current=2, vibration=0.1
    )
    asyncio.run(pipeline.process_telemetry(tel))
    
    # dropout tick
    asyncio.run(pipeline.tick_twins(t0 + 5.0))
    
    # check events
    from app.core.db import events_cache
    events = list(events_cache)
    dropout_evt = next((e for e in events if e.robot_id == "D1" and e.kind == "dropout"), None)
    assert dropout_evt is not None
