"""HTTP API endpoints for FleetTwin.

Wires Lane B sandbox (simulate_mission), eval suite (run_suite), and
keeps backward-compatible /api/decision and /api/override routes.
"""
import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import StreamingResponse

from app.contract.schemas import (
    AttackSpec, Decision, EvalResult, Mission, OverrideState,
    Telemetry, TwinSnapshot,
)
from app.core.pipeline import pipeline
from app.core.db import history_cache, events_cache

# Lane B – sandbox and eval suite
from app.sandbox.simulate import simulate_mission as _simulate_mission
from app.evalsuite import run_suite as _run_suite

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Cached eval result (in-memory, most recent run)
# ---------------------------------------------------------------------------
_last_eval: Optional[EvalResult] = None


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Fleet / robot / events
# ---------------------------------------------------------------------------
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
        "events": [e for e in events_cache if e.robot_id in (robot_id, None)],
    }


@router.get("/events")
def get_events(limit: int = 50):
    return list(events_cache)[-limit:]


# ---------------------------------------------------------------------------
# Decision / override (backward compatible)
# ---------------------------------------------------------------------------
@router.get("/decision")
def get_decision(robot_id: Optional[str] = None):
    if robot_id and robot_id in pipeline.last_decision:
        return pipeline.last_decision[robot_id]
    if robot_id:
        return Decision(action="CONTINUE", reason="Nominal",
                        confidence=0.9, robot_id=robot_id)
    return Decision(action="CONTINUE", reason="Nominal fleet-wide",
                    confidence=0.9)


@router.post("/override")
def post_override(req: dict):
    robot_id = req.get("robot_id")
    action = req.get("action")
    seconds = req.get("seconds", 15.0)
    override = OverrideState(robot_id=robot_id, action=action,
                             seconds_left=seconds)
    pipeline.set_override(override)
    return override


# ---------------------------------------------------------------------------
# Telemetry ingest
# ---------------------------------------------------------------------------
@router.post("/telemetry", status_code=202)
async def post_telemetry(tel: Telemetry):
    await pipeline.process_telemetry(tel)
    return {"status": "accepted"}


# ---------------------------------------------------------------------------
# Attack injection / clear
# ---------------------------------------------------------------------------
@router.post("/attacks/inject")
def inject_attack(spec: AttackSpec):
    import backend_sim_global
    if backend_sim_global.fleet_sim:
        backend_sim_global.fleet_sim.inject(spec)
        pipeline.active_attacks.setdefault(spec.robot_id, [])
        if spec.kind not in pipeline.active_attacks[spec.robot_id]:
            pipeline.active_attacks[spec.robot_id].append(spec.kind)
    return {"status": "injected"}


@router.post("/attacks/clear")
def clear_attacks(req: dict | None = None):
    req = req or {}
    robot_id = req.get("robot_id")
    import backend_sim_global
    if backend_sim_global.fleet_sim:
        backend_sim_global.fleet_sim.clear(robot_id)
    # Clear tracked attacks
    if robot_id:
        pipeline.active_attacks[robot_id] = []
    else:
        for rid in pipeline.active_attacks:
            pipeline.active_attacks[rid] = []
    return {"status": "cleared"}


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------
@router.post("/sim/reset")
def reset_sim(seed: int = Query(42)):
    import backend_sim_global
    from app.sim.world import FleetSim
    from app.core.db import reset_db
    
    # 1. Recreate FleetSim
    backend_sim_global.fleet_sim = FleetSim(seed=seed)
    
    # 2. Reset Pipeline
    pipeline.reset()
    
    # 3. Reset DB and Caches
    reset_db()
    
    # 4. Re-init twins
    sim = backend_sim_global.fleet_sim
    for rid, mission in sim.missions().items():
        rtype = sim._robots[rid].robot_type
        pipeline.init_robot(rid, rtype)
        pipeline.twins[rid].set_mission(mission)
        
    return {"status": "reset", "seed": seed}

@router.get("/missions")
def get_missions():
    import backend_sim_global
    if backend_sim_global.fleet_sim:
        return backend_sim_global.fleet_sim.missions()
    return {}


@router.post("/missions/simulate")
def simulate_mission_endpoint(mission: Mission):
    """Run the sandbox simulation and return a SimResult."""
    # Find the twin snapshot for this robot
    engine = pipeline.twins.get(mission.robot_id)
    if engine is None:
        raise HTTPException(status_code=404,
                            detail=f"No twin for robot {mission.robot_id}")
    snap = engine.snapshot()
    health = pipeline.last_health.get(mission.robot_id)
    result = _simulate_mission(snap, mission, health)
    return result


@router.post("/missions/deploy")
def deploy_mission_endpoint(mission: Mission, force: int = Query(0)):
    """Simulate, check safety gate, and deploy if safe (or force=1)."""
    engine = pipeline.twins.get(mission.robot_id)
    if engine is None:
        raise HTTPException(status_code=404,
                            detail=f"No twin for robot {mission.robot_id}")
    snap = engine.snapshot()
    health = pipeline.last_health.get(mission.robot_id)
    result = _simulate_mission(snap, mission, health)

    if not result.safe_to_deploy and not force:
        raise HTTPException(
            status_code=400,
            detail=f"Deployment refused: {'; '.join(result.violations)}",
        )
    # Deploy the mission into the simulator
    import backend_sim_global
    if backend_sim_global.fleet_sim:
        backend_sim_global.fleet_sim.assign_mission(mission)
    engine.set_mission(mission)
    return result


# ---------------------------------------------------------------------------
# Eval suite
# ---------------------------------------------------------------------------
@router.post("/eval/run")
def run_eval(seed: int = Query(42)):
    global _last_eval
    t0 = time.perf_counter()
    result = _run_suite(seed=seed, fast=True)
    elapsed = time.perf_counter() - t0
    # Stamp with wall time
    result = result.model_copy(update={"ts": time.time()})
    _last_eval = result
    return result


@router.get("/eval/latest")
def latest_eval():
    if _last_eval is None:
        raise HTTPException(status_code=404, detail="No eval run yet")
    return _last_eval


