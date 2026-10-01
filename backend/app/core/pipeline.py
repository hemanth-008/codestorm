"""Telemetry processing pipeline.

Integrates twin engine (Lane A) with real detectors, health, and decision
engine (Lane B). Security signing/verification is imported optionally
from Lane D.
"""
import os
import uuid
import time
from typing import Optional

from app.contract.schemas import (
    Event, HealthReport, Decision, StreamFrame, RobotFrame,
    Telemetry, IngestStats, OverrideState,
)
from app.twin.engine import TwinEngine
from app.core.db import (
    insert_telemetry, insert_twin_state, insert_event,
    append_history, append_event_cache, history_cache,
)
from app.core.bus import bus

# --- Real Lane B detectors ---
from app.detect.deviation import DeviationDetector
from app.detect.spoof import SpoofGuard
from app.detect.noise import NoiseMonitor
from app.health.health import HealthEstimator
from app.decision.engine import decide

# --- Optional Lane D security ---
try:
    from app.security.signing import verify_telemetry  # type: ignore[import-not-found]
except ImportError:
    verify_telemetry = None  # Lane D not merged yet

TELEMETRY_KEY = os.environ.get("TELEMETRY_KEY")


MAX_STREAM_EVENTS = 200  # backpressure: drop oldest events if stream buffer exceeds this


class Pipeline:
    """Central pipeline: signature → twin → detectors → health → decision.

    Hardening: malformed packets are dropped with a counter increment,
    the stream event buffer is bounded by MAX_STREAM_EVENTS, and
    each detector/health step is wrapped so a single failure does not
    crash the pipeline.
    """

    def __init__(self) -> None:
        self.twins: dict[str, TwinEngine] = {}
        self.spoof_guards: dict[str, SpoofGuard] = {}
        self.noise_monitors: dict[str, NoiseMonitor] = {}
        self.dev_detectors: dict[str, DeviationDetector] = {}
        self.health_estimators: dict[str, HealthEstimator] = {}

        self.last_health: dict[str, HealthReport] = {}
        self.last_decision: dict[str, Decision] = {}
        self.active_attacks: dict[str, list[str]] = {}

        self.recent_events: list[Event] = []
        self.active_override: Optional[OverrideState] = None

        # Stream frame accumulation
        self.new_events_for_stream: list[Event] = []

        # Ingest metrics
        self.msg_count: int = 0
        self.dropped_count: int = 0
        self.last_ingest_time: float = time.time()
        self.lag_ms: float = 0.0
        self.ingest_stats: IngestStats = IngestStats()

    def init_robot(self, robot_id: str, robot_type: str) -> None:
        if robot_id not in self.twins:
            self.twins[robot_id] = TwinEngine(robot_id, robot_type)
            self.spoof_guards[robot_id] = SpoofGuard()
            self.noise_monitors[robot_id] = NoiseMonitor()
            self.dev_detectors[robot_id] = DeviationDetector()
            self.health_estimators[robot_id] = HealthEstimator()
            self.active_attacks[robot_id] = []

    def reset(self) -> None:
        self.twins.clear()
        self.spoof_guards.clear()
        self.noise_monitors.clear()
        self.dev_detectors.clear()
        self.health_estimators.clear()
        self.last_health.clear()
        self.last_decision.clear()
        self.active_attacks.clear()
        self.recent_events.clear()
        self.active_override = None
        self.new_events_for_stream.clear()
        self.msg_count = 0
        self.dropped_count = 0
        self.last_ingest_time = time.time()
        self.lag_ms = 0.0
        self.ingest_stats = IngestStats()

    def set_override(self, override: OverrideState | None) -> None:
        self.active_override = override

    async def process_telemetry(self, tel: Telemetry) -> None:
        """Ingest one telemetry packet through the full pipeline.

        Malformed or unexpected packets increment the drop counter rather
        than crashing the loop.
        """
        now = time.time()
        self.msg_count += 1

        # 0. Basic sanity – reject packets with obviously bad fields
        try:
            if not tel.robot_id or tel.ts < 0:
                self.dropped_count += 1
                return
        except Exception:
            self.dropped_count += 1
            return

        # 1. Signature verification (Lane D, optional)
        if TELEMETRY_KEY and verify_telemetry is not None:
            if not verify_telemetry(tel, TELEMETRY_KEY):
                self.dropped_count += 1
                evt = Event(
                    id=str(uuid.uuid4()), ts=tel.ts, robot_id=tel.robot_id,
                    kind="spoof_suspected", severity="critical",
                    message="bad signature",
                )
                await self._emit(evt)
                return

        self.init_robot(tel.robot_id, tel.robot_type)

        # 2. Twin update
        twin_engine = self.twins[tel.robot_id]
        prev_mode = twin_engine.mode
        twin = twin_engine.on_telemetry(tel)

        if prev_mode == "dead_reckoning" and twin.mode == "synced":
            await self._emit(Event(
                id=str(uuid.uuid4()), ts=tel.ts, robot_id=tel.robot_id,
                kind="link_recovered", severity="info",
                message="Telemetry link recovered",
            ))

        # 3. Detectors (Lane B) — wrapped so one failing detector
        #    does not crash the entire pipeline.
        events: list[Event] = []
        for fn in [
            lambda: self.spoof_guards[tel.robot_id].update(tel, twin),
            lambda: self.noise_monitors[tel.robot_id].update(twin),
            lambda: self.dev_detectors[tel.robot_id].update(twin),
        ]:
            try:
                events.extend(fn())
            except Exception as exc:
                print(f"Detector error for {tel.robot_id}: {exc}")

        # 4. Health (Lane B)
        try:
            health = self.health_estimators[tel.robot_id].update(tel, twin)
            self.last_health[tel.robot_id] = health
            events.extend(self.health_estimators[tel.robot_id].drain_events())
        except Exception as exc:
            print(f"Health error for {tel.robot_id}: {exc}")
            health = self.last_health.get(
                tel.robot_id,
                HealthReport(robot_id=tel.robot_id, ts=tel.ts,
                             health_index=1.0, status="ok"),
            )

        # Health events are included in the health estimator output
        # but we also want them in recent_events for the decision engine
        for evt in events:
            self.recent_events.append(evt)
        # Keep recent_events bounded
        if len(self.recent_events) > 200:
            self.recent_events = self.recent_events[-100:]

        # 5. Decision (Lane B)
        if self.active_override and self.active_override.seconds_left <= 0:
            self.active_override = None

        decision = decide(
            tel.robot_id, twin, health,
            self.recent_events, self.active_override,
        )
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

    async def _emit(self, evt: Event) -> None:
        insert_event(evt)
        append_event_cache(evt)
        self.new_events_for_stream.append(evt)
        await bus.publish("events", evt)

    async def tick_twins(self, sim_now: float) -> None:
        """Called every sim step to update twins that haven't received telemetry."""
        for rid, engine in self.twins.items():
            prev_mode = engine.mode
            twin = engine.tick(sim_now)
            if twin:
                if prev_mode == "synced" and twin.mode == "dead_reckoning":
                    await self._emit(Event(
                        id=str(uuid.uuid4()), ts=sim_now, robot_id=rid,
                        kind="dropout", severity="warn",
                        message="Telemetry dropout, entering dead reckoning",
                    ))
                insert_twin_state(twin)
                append_history(twin)

        # Update ingest stats
        now = time.time()
        dt = now - self.last_ingest_time
        self.ingest_stats = IngestStats(
            msgs_per_s=self.msg_count / dt if dt > 0 else 0.0,
            dropped=self.dropped_count,
            lag_ms=self.lag_ms,
        )
        self.last_ingest_time = now
        self.msg_count = 0

    def build_stream_frame(self) -> Optional[StreamFrame]:
        if not self.twins:
            return None

        robots: list[RobotFrame] = []
        sync_sum = 0.0
        count = 0

        for rid, engine in self.twins.items():
            hist = history_cache.get(rid)
            if not hist:
                continue
            twin_state = hist[-1]

            tel = Telemetry(
                robot_id=rid, robot_type=engine.robot_type, ts=twin_state.ts,
                seq=0,
                x=twin_state.est.x, y=twin_state.est.y, z=twin_state.est.z,
                heading=twin_state.est.heading, speed=twin_state.est.speed,
                battery=twin_state.est.battery,
                motor_temp=twin_state.est.motor_temp,
                current=twin_state.est.current,
                vibration=twin_state.est.vibration,
            )

            health = self.last_health.get(
                rid,
                HealthReport(robot_id=rid, ts=twin_state.ts,
                             health_index=1.0, status="ok"),
            )
            decision = self.last_decision.get(
                rid,
                Decision(action="CONTINUE", reason="Nominal",
                         confidence=0.9, robot_id=rid),
            )

            rf = RobotFrame(
                robot_id=rid,
                robot_type=engine.robot_type,
                name=rid,
                telemetry=tel,
                twin=twin_state,
                health=health,
                decision=decision,
                mission=engine.mission,
                active_attacks=self.active_attacks.get(rid, []),
            )
            robots.append(rf)
            sync_sum += twin_state.sync_score
            count += 1

        fleet_sync = sync_sum / count if count > 0 else 100.0

        events = self.new_events_for_stream.copy()
        self.new_events_for_stream.clear()

        # Determine sim ts from the latest robot state
        latest_ts = max((h[-1].ts for h in history_cache.values() if h), default=0.0)

        return StreamFrame(
            ts=latest_ts,
            robots=robots,
            events=events,
            fleet_sync=fleet_sync,
            ingest=self.ingest_stats,
        )


pipeline = Pipeline()
