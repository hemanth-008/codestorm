"""Main FastAPI application and entry point."""
import asyncio
import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.db import init_db
from app.api.endpoints import router as api_router
from app.sim.world import FleetSim
from app.contract.physics import DT

# We put fleet_sim here so it can be accessed by the endpoints (e.g. inject/clear attacks)
# A bit of a hack, but works for the current architecture without dependency injection
import backend_sim_global
backend_sim_global.fleet_sim = FleetSim(seed=42)

SIM_ENABLED = int(os.environ.get("SIM_ENABLED", "1"))
SIM_SPEED = float(os.environ.get("SIM_SPEED", "1.0"))
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

async def sim_loop():
    from app.core.pipeline import pipeline
    # Wait for the server to start fully
    await asyncio.sleep(1.0)
    
    sim = backend_sim_global.fleet_sim
    while True:
        t0 = time.perf_counter()
        
        # 1. Step physics
        packets = sim.step(DT)
        
        # 2. Push telemetry to pipeline
        for tel in packets:
            await pipeline.process_telemetry(tel)
            
        # 3. Tick twins (dead reckoning detection)
        await pipeline.tick_twins(sim.now)
        
        # Sleep to maintain SIM_SPEED
        elapsed = time.perf_counter() - t0
        target_sleep = (DT / SIM_SPEED) - elapsed
        if target_sleep > 0:
            await asyncio.sleep(target_sleep)
        else:
            await asyncio.sleep(0.001)  # Yield loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    
    task = None
    if SIM_ENABLED:
        task = asyncio.create_task(sim_loop())
        
    yield
    
    if task:
        task.cancel()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)