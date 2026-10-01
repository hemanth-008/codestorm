import json
from typing import Dict, List
from fastapi import APIRouter
from app.core.db import conn
from app.core.pipeline import pipeline

# Wear rates extracted from simulation defaults to compute estimates
_DEFAULT_WEAR_RATES: Dict[str, float] = {
    "rover": 1.0 / (40 * 60),
    "drone": 1.0 / (80 * 60),
    "agv": 1.0 / (100 * 60),
}

router = APIRouter()

@router.get("/maintenance/log")
def get_maintenance_log() -> List[Dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT data FROM events WHERE kind IN ('health_warning', 'maintenance_due', 'health_critical') ORDER BY ts DESC LIMIT 200"
    )
    rows = cur.fetchall()
    
    log_entries = []
    for row in rows:
        evt = json.loads(row[0])
        detail = evt.get("detail", {})
        drivers = detail.get("drivers", {})
        
        dominant = "unknown"
        max_val = -1.0
        for k, v in drivers.items():
            if v > max_val:
                max_val = v
                dominant = k
                
        if dominant == "temp":
            reason = "Excessive motor temperature"
        elif dominant == "current":
            reason = "High current draw"
        elif dominant == "vibration":
            reason = "Severe vibration"
        else:
            reason = "Unknown wear"
            
        robot_id = evt.get("robot_id", "Unknown")
        robot_type = "unknown"
        if robot_id in pipeline.twins:
            robot_type = pipeline.twins[robot_id].robot_type
            
        recommended = "Schedule immediate inspection."
        if evt["kind"] == "maintenance_due":
            recommended = "Perform scheduled maintenance."
        elif evt["kind"] == "health_critical":
            recommended = "Halt operations and replace unit."
            
        log_entries.append({
            "robot_id": robot_id,
            "robot_type": robot_type,
            "ts": evt["ts"],
            "severity": evt["severity"],
            "plain_language_reason": reason,
            "health_index_at_time": detail.get("health_index", 1.0),
            "recommended_action": recommended,
        })
        
    return log_entries

@router.get("/maintenance/lifetime-reference")
def get_lifetime_reference() -> List[Dict]:
    # Compute from existing physics/wear constants
    ref = []
    for rtype, rate in _DEFAULT_WEAR_RATES.items():
        lifetime_s = 1.0 / rate if rate > 0 else 0
        maintenance_interval_s = 0.55 / rate if rate > 0 else 0
        
        ref.append({
            "robot_type": rtype,
            "typical_operating_duration_mins": round(lifetime_s / 60),
            "suggested_maintenance_interval_mins": round(maintenance_interval_s / 60),
            "common_failure_reasons": "Vibration (highest gain), motor temperature, or current draw",
            "note": "Simulated-model-based estimate, not a manufacturer spec"
        })
    return ref
