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

# Global sim reference so the API can reach it for inject/clear/missions
import backend_sim_global
backend_sim_global.fleet_sim = FleetSim(seed=42)

SIM_ENABLED = int(os.environ.get("SIM_ENABLED", "1"))
SIM_SPEED = float(os.environ.get("SIM_SPEED", "1.0"))
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")


async def sim_loop() -> None:
    try:
        from app.core.pipeline import pipeline
        await asyncio.sleep(1.0)

        sim = backend_sim_global.fleet_sim

        # Seed twin engines with the default missions so the twin predictor
        # can use follow() from the start.
        for rid, mission in sim.missions().items():
            pipeline.init_robot(rid, mission.robot_id[0].upper() == "D" and "drone"
                                or (mission.robot_id[0].upper() == "G" and "agv" or "rover"))
            # Determine robot type from the sim internals
            rtype = sim._robots[rid].robot_type
            pipeline.init_robot(rid, rtype)
            pipeline.twins[rid].set_mission(mission)

        while True:
            t0 = time.perf_counter()

            packets = sim.step(DT)

            for tel in packets:
                try:
                    await pipeline.process_telemetry(tel)
                except Exception as e:
                    print(f"Error processing sim telemetry: {e}")

            try:
                await pipeline.tick_twins(sim.now)
            except Exception as e:
                print(f"Error ticking twins: {e}")

            elapsed = time.perf_counter() - t0
            target_sleep = (DT / SIM_SPEED) - elapsed
            if target_sleep > 0:
                await asyncio.sleep(target_sleep)
            else:
                await asyncio.sleep(0.001)
    except asyncio.CancelledError:
        print("Simulator loop gracefully shutting down.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    task = None
    if SIM_ENABLED:
        task = asyncio.create_task(sim_loop())

    yield

    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# --- Optional Lane D: security and observability ---
try:
    from app.security.install import install as install_security  # type: ignore[import-not-found]
    install_security(app)
except ImportError:
    pass  # Lane D not merged yet

try:
    from app.observability.install import install as install_obs  # type: ignore[import-not-found]
    install_obs(app)
except ImportError:
    pass  # Lane D not merged yet