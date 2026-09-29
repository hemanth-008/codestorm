from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import math, time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WAYPOINTS = [(10, 10), (90, 10), (90, 50), (50, 50), (50, 90), (10, 90)]
CRUISE = 4.0

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
    for x1, y1, x2, y2, length, start in SEGMENTS:
        if d <= start + length:
            f = (d - start) / length
            x = x1 + (x2 - x1) * f
            y = y1 + (y2 - y1) * f
            heading = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 360
            return x, y, heading
    return WAYPOINTS[0][0], WAYPOINTS[0][1], 0.0


# ---- Decision engine: state in, {action, reason, confidence} out ----
# Swap this function's body for any other PS: network load, energy demand,
# sensor readings - the shape (state -> action + reason) stays the same.
def decide(battery, speed):
    if battery < 30:
        return {
            "action": "RETURN_TO_BASE",
            "reason": f"Battery at {battery:.0f}% is below the 30% safety threshold",
            "confidence": round(0.95 - (battery / 300), 2),
        }
    if speed > 1.6:
        return {
            "action": "SLOW_DOWN",
            "reason": f"Speed {speed:.2f} m/s exceeds the 1.6 m/s safe operating limit",
            "confidence": 0.82,
        }
    return {
        "action": "CONTINUE",
        "reason": "Battery and speed are within safe operating range",
        "confidence": 0.9,
    }


# Manual override, kept in memory. A real system would persist this.
_override = {"action": None, "reason": None, "until": 0}


class Override(BaseModel):
    action: str
    reason: str
    seconds: int = 15


@app.get("/api/health")
def health():
    return {"status": "ok", "time": time.time()}


@app.get("/api/telemetry")
def telemetry():
    t = time.time()
    x, y, heading = robot_state(t)
    battery = 100 - ((t / 6) % 75)
    speed = 1.2 + 0.3 * math.sin(t / 2)
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "battery": round(battery, 1),
        "speed": round(speed, 2),
        "heading": round(heading),
        "status": "LOW BATTERY" if battery < 30 else "NAVIGATING",
        "time": t,
    }


@app.get("/api/decision")
def decision():
    t = time.time()
    _, _, _ = robot_state(t)
    battery = 100 - ((t / 6) % 75)
    speed = 1.2 + 0.3 * math.sin(t / 2)

    if _override["action"] and t < _override["until"]:
        result = {
            "action": _override["action"],
            "reason": _override["reason"],
            "confidence": 1.0,
            "source": "MANUAL OVERRIDE",
        }
    else:
        result = decide(battery, speed)
        result["source"] = "AUTONOMOUS"

    result["time"] = t
    return result


@app.post("/api/override")
def override(o: Override):
    _override["action"] = o.action
    _override["reason"] = o.reason
    _override["until"] = time.time() + o.seconds
    return {"ok": True}