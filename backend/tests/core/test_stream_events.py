"""Test pipeline stream frames include health events."""
import asyncio
import pytest

from app.core.pipeline import pipeline
from app.contract.schemas import Telemetry
from app.health.health import HealthEstimator

@pytest.mark.asyncio
async def test_stream_includes_health_events():
    # Make a dummy pipeline instance or just use the global one but clear it
    # We will simulate wear to generate a health_critical event
    
    # We need to make wear high. We can just send a telemetry with very high motor_temp
    pipeline.health_estimators.clear()
    
    tel = Telemetry(
        robot_id="TestRobot", robot_type="rover", ts=1.0, seq=1,
        x=0.0, y=0.0, z=0.0, heading=0.0, speed=1.0,
        battery=100.0, motor_temp=20000.0, current=10.0, vibration=5.0
    )
    
    await pipeline.process_telemetry(tel)
    
    frame = pipeline.build_stream_frame()
    
    # Check that events in frame contain health_warning or similar
    health_events = [e for e in frame.events if "health" in e.kind or "maintenance" in e.kind]
    assert len(health_events) > 0, "Health events should be emitted to the stream"
