from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import math, time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# The robot patrols this loop on a 100x100 map
WAYPOINTS = [(10, 10), (90, 10), (90, 50), (50, 50), (50, 90), (10, 90)]
CRUISE = 4.0  # map units per second

SEGMENTS = []
total = 0.0
for i, (x1, y1) in enumerate(WAYPOINTS):
    x2, y2 = WAYPOINTS[(i + 1) % len(WAYPOINTS)]
    length = math.hypot(x2 - x1, y2 - y1)
    SEGMENTS.append((x1, y1, x2, y2, length, total))
    total += length
PERIMETER = total


def robot_state(t):
    d = (t * CRUISE) % PERIMETER
    for i, (x1, y1, x2, y2, length, start) in enumerate(SEGMENTS):
        if d <= start + length:
            f = (d - start) / length
            x = x1 + (x2 - x1) * f
            y = y1 + (y2 - y1) * f
            heading = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 360
            return x, y, heading, i
    return WAYPOINTS[0][0], WAYPOINTS[0][1], 0.0, 0


@app.get("/api/health")
def health():
    return {"status": "ok", "time": time.time()}


@app.get("/api/telemetry")
def telemetry():
    t = time.time()
    x, y, heading, wp = robot_state(t)
    battery = 100 - ((t / 6) % 75)  # drains from 100 to 25, then "recharges"
    speed = 1.2 + 0.3 * math.sin(t / 2)
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "battery": round(battery, 1),
        "speed": round(speed, 2),
        "heading": round(heading),
        "waypoint": wp,
        "status": "LOW BATTERY" if battery < 30 else "NAVIGATING",
        "time": t,
    }
