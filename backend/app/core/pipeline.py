"""Telemetry processing pipeline."""
import os
import uuid
import time
from typing import Optional

from app.contract.schemas import (
    Event, HealthReport, Decision, StreamFrame, RobotFrame,
    Telemetry, IngestStats
)
from app.twin.engine import TwinEngine
from app.core.db import insert_telemetry, insert_twin_state, insert_event, append_history, append_event_cache, history_cache
from app.core.bus import bus

# Stand-in models until Lane B lands
class DummySpoofGuard:
    def update(self, tel, twin) -> list[Event]: return []

class DummyNoiseMonitor:
    def update(self, twin) -> list[Event]: return []

class DummyDeviationDetector:
    def update(self, twin) -> list[Event]: return []

class DummyHealthEstimator:
    def update(self, tel, twin) -> HealthReport:
        return HealthReport(
            robot_id=tel.robot_id, ts=tel.ts, health_index=1.0,
            status="ok", drivers={"current": tel.current, "temp": tel.motor_temp}
        )

def dummy_decide(robot_id, twin, health, recent_events, override) -> Decision:
    if override and override.robot_id in (robot_id, None):
        return Decision(action=override.action, reason="Manual override", confidence=1.0, robot_id=robot_id, override_active=True)
    return Decision(action="CONTINUE", reason="Nominal", confidence=0.9, robot_id=robot_id)

TELEMETRY_KEY = os.environ.get("TELEMETRY_KEY")

class Pipeline:
    def __init__(self):
        self.twins: dict[str, TwinEngine] = {}
        self.spoof_guards = {}
        self.noise_monitors = {}
        self.dev_detectors = {}
        self.health_estimators = {}
        
        self.last_health: dict[str, HealthReport] = {}
        self.last_decision: dict[str, Decision] = {}
        self.active_attacks: dict[str, list[str]] = {}
        
        self.recent_events = [] # For decision engine
        
        # Override state from API
        self.active_override = None
        
        # Stream frame accumulation
        self.new_events_for_stream = []
        
        # Ingest metrics
        self.msg_count = 0
        self.dropped_count = 0
        self.last_ingest_time = time.time()
        self.lag_ms = 0.0

    def init_robot(self, robot_id: str, robot_type: str):
        if robot_id not in self.twins:
            self.twins[robot_id] = TwinEngine(robot_id, robot_type)
            self.spoof_guards[robot_id] = DummySpoofGuard()
            self.noise_monitors[robot_id] = DummyNoiseMonitor()
            self.dev_detectors[robot_id] = DummyDeviationDetector()
            self.health_estimators[robot_id] = DummyHealthEstimator()
            self.active_attacks[robot_id] = []

    def set_override(self, override):
        self.active_override = override

    async def process_telemetry(self, tel: Telemetry):
        now = time.time()
        self.msg_count += 1
        
        # 1. Signature
        if TELEMETRY_KEY:
            # Stand-in: verify signature (Lane D will provide real one)
            # If invalid:
            # self.dropped_count += 1
            # evt = Event(id=str(uuid.uuid4()), ts=tel.ts, robot_id=tel.robot_id, kind="spoof_suspected", severity="critical", message="bad signature")
            # await self._emit(evt)
            # return
            pass
            
        self.init_robot(tel.robot_id, tel.robot_type)
        
        # 2. Twin
        twin_engine = self.twins[tel.robot_id]
        prev_mode = twin_engine.mode
        twin = twin_engine.on_telemetry(tel)
        
        if prev_mode == "dead_reckoning" and twin.mode == "synced":
            await self._emit(Event(
                id=str(uuid.uuid4()), ts=tel.ts, robot_id=tel.robot_id,
                kind="link_recovered", severity="info", message="Telemetry link recovered"
            ))

        # 3. Detectors
        events = []
        events.extend(self.spoof_guards[tel.robot_id].update(tel, twin))
        events.extend(self.noise_monitors[tel.robot_id].update(twin))
        events.extend(self.dev_detectors[tel.robot_id].update(twin))
        
        # 4. Health
        health = self.health_estimators[tel.robot_id].update(tel, twin)
        self.last_health[tel.robot_id] = health
        
        # 5. Decide
        # Check override expiry
        if self.active_override and self.active_override.seconds_left <= 0:
            self.active_override = None
            
        decision = dummy_decide(tel.robot_id, twin, health, self.recent_events, self.active_override)
        self.last_decision[tel.robot_id] = decision
        
        # Emit detector events
        for evt in events:
            await self._emit(evt)
            
        # 6. Persist & Bus
        insert_telemetry(tel)
        insert_twin_state(twin)
        append_history(twin)
        
        # Compute lag
        self.lag_ms = (now - tel.ts) * 1000.0 if tel.ts < now else 0.0

    async def _emit(self, evt: Event):
        insert_event(evt)
        append_event_cache(evt)
        self.new_events_for_stream.append(evt)
        await bus.publish("events", evt)
        
    async def tick_twins(self, sim_now: float):
        """Called every sim step to update twins that haven't received telemetry."""
        for rid, engine in self.twins.items():
            prev_mode = engine.mode
            twin = engine.tick(sim_now)
            if twin:
                if prev_mode == "synced" and twin.mode == "dead_reckoning":
                    await self._emit(Event(
                        id=str(uuid.uuid4()), ts=sim_now, robot_id=rid,
                        kind="dropout", severity="warn", message="Telemetry dropout, entering dead reckoning"
                    ))
                insert_twin_state(twin)
                append_history(twin)
                
        # Also update ingest stats
        now = time.time()
        dt = now - self.last_ingest_time
        self.ingest_stats = IngestStats(
            msgs_per_s=self.msg_count / dt if dt > 0 else 0.0,
            dropped=self.dropped_count,
            lag_ms=self.lag_ms
        )
        self.last_ingest_time = now
        self.msg_count = 0
        
    def build_stream_frame(self) -> Optional[StreamFrame]:
        if not self.twins:
            return None
            
        robots = []
        sync_sum = 0.0
        count = 0
        
        for rid, engine in self.twins.items():
            hist = history_cache.get(rid)
            if not hist:
                continue
            twin_state = hist[-1]
            
            # Find the latest telemetry
            tel = Telemetry(
                robot_id=rid, robot_type=engine.robot_type, ts=twin_state.ts, seq=0,
                x=twin_state.est.x, y=twin_state.est.y, z=twin_state.est.z,
                heading=twin_state.est.heading, speed=twin_state.est.speed,
                battery=twin_state.est.battery, motor_temp=twin_state.est.motor_temp,
                current=twin_state.est.current, vibration=twin_state.est.vibration
            )
            
            health = self.last_health.get(rid, HealthReport(robot_id=rid, ts=twin_state.ts, health_index=1.0, status="ok"))
            decision = self.last_decision.get(rid, Decision(action="CONTINUE", reason="Nominal", confidence=0.9, robot_id=rid))
            
            rf = RobotFrame(
                robot_id=rid,
                robot_type=engine.robot_type,
                name=rid,
                telemetry=tel,
                twin=twin_state,
                health=health,
                decision=decision,
                mission=engine.mission,
                active_attacks=self.active_attacks.get(rid, [])
            )
            robots.append(rf)
            sync_sum += twin_state.sync_score
            count += 1
            
        fleet_sync = sync_sum / count if count > 0 else 100.0
        
        events = self.new_events_for_stream.copy()
        self.new_events_for_stream.clear()
        
        return StreamFrame(
            ts=time.time(),
            robots=robots,
            events=events,
            fleet_sync=fleet_sync,
            ingest=getattr(self, 'ingest_stats', IngestStats())
        )

pipeline = Pipeline()
