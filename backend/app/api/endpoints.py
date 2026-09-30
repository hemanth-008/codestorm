import asyncio
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from app.contract.schemas import (
    Telemetry, AttackSpec, OverrideState, Decision, StreamFrame, RobotFrame,
    IngestStats
)
from app.core.pipeline import pipeline
from app.core.db import history_cache, events_cache

router = APIRouter(prefix="/api")

@router.get("/stream")
async def get_stream(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
                
            frame = pipeline.build_stream_frame()
            if frame:
                yield f"data: {frame.model_dump_json()}\n\n"
            await asyncio.sleep(0.2)  # 5 Hz
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/fleet")
def get_fleet():
    frame = pipeline.build_stream_frame()
    return frame.robots if frame else []

@router.get("/robots/{robot_id}")
def get_robot(robot_id: str):
    frame = pipeline.build_stream_frame()
    if not frame:
        raise HTTPException(status_code=404, detail="No data yet")
        
    rframe = next((r for r in frame.robots if r.robot_id == robot_id), None)
    if not rframe:
        raise HTTPException(status_code=404, detail="Robot not found")
        
    return {
        "frame": rframe,
        "history": list(history_cache.get(robot_id, [])),
        "events": [e for e in events_cache if e.robot_id in (robot_id, None)]
    }

@router.get("/events")
def get_events(limit: int = 50):
    evts = list(events_cache)
    return evts[-limit:]

@router.get("/decision")
def get_decision(robot_id: str = None):
    if robot_id:
        if robot_id in pipeline.last_decision:
            return pipeline.last_decision[robot_id]
        return Decision(action="CONTINUE", reason="Nominal", confidence=0.9, robot_id=robot_id)
    return Decision(action="CONTINUE", reason="Nominal fleet-wide", confidence=0.9)

@router.post("/override")
def post_override(req: dict):
    # Backward compatible with legacy main.py
    robot_id = req.get("robot_id")
    action = req.get("action")
    seconds = req.get("seconds", 15.0)
    
    override = OverrideState(robot_id=robot_id, action=action, seconds_left=seconds)
    pipeline.set_override(override)
    return override

@router.post("/telemetry", status_code=202)
async def post_telemetry(tel: Telemetry):
    await pipeline.process_telemetry(tel)
    return {"status": "accepted"}

@router.post("/attacks/inject")
def inject_attack(spec: AttackSpec):
    # This modifies the simulator which is running in main.py loop
    # We will need a way to pass this to FleetSim
    from backend_sim_global import fleet_sim  # A bit hacky, but works for the architecture
    if fleet_sim:
        fleet_sim.inject(spec)
    return {"status": "injected"}

@router.post("/attacks/clear")
def clear_attacks(req: dict = None):
    req = req or {}
    robot_id = req.get("robot_id")
    from backend_sim_global import fleet_sim
    if fleet_sim:
        fleet_sim.clear(robot_id)
    return {"status": "cleared"}

@router.get("/missions")
def get_missions():
    from backend_sim_global import fleet_sim
    if fleet_sim:
        return fleet_sim.missions()
    return {}

@router.post("/missions/simulate")
def simulate_mission():
    raise HTTPException(status_code=501, detail="Sandbox not available until Lane B")

@router.post("/missions/deploy")
def deploy_mission():
    raise HTTPException(status_code=501, detail="Sandbox not available until Lane B")

@router.post("/eval/run")
def run_eval():
    raise HTTPException(status_code=501, detail="Eval suite not available until Lane B")

@router.get("/eval/latest")
def latest_eval():
    raise HTTPException(status_code=501, detail="Eval suite not available until Lane B")

@router.post("/auth/login")
def login():
    raise HTTPException(status_code=501, detail="Auth not available until Lane D")
