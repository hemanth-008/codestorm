from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random, time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "time": time.time()}

@app.get("/api/telemetry")
def telemetry():
    return {
        "x": round(random.uniform(0, 100), 2),
        "y": round(random.uniform(0, 100), 2),
        "battery": random.randint(20, 100),
        "speed": round(random.uniform(0, 2), 2),
    }