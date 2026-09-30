"""Small process-local metrics registry for the FleetTwin service."""

from __future__ import annotations

import threading
import time


class FleetMetrics:
    """Counters and gauges required by the operations contract."""

    def __init__(self) -> None:
        self.started_at = time.monotonic()
        self._lock = threading.Lock()
        self.request_count = 0
        self.request_latency_sum_s = 0.0
        self.ingest_count = 0
        self.dropped_packets = 0
        self.active_alerts = 0
        self.fleet_sync_score = 100.0
        self._last_ingest_at: float | None = None
        self._previous_ingest_count = 0
        self._previous_ingest_at = self.started_at

    def record_request(self, latency_s: float) -> None:
        """Record one completed HTTP request and its observed latency."""

        with self._lock:
            self.request_count += 1
            self.request_latency_sum_s += max(0.0, latency_s)

    def record_ingest(self, count: int = 1) -> None:
        """Increment ingested telemetry packets."""

        if count < 0:
            raise ValueError("ingest count must not be negative")
        with self._lock:
            self.ingest_count += count
            self._last_ingest_at = time.monotonic()

    def record_drop(self, count: int = 1) -> None:
        """Increment packets dropped before analytics processing."""

        if count < 0:
            raise ValueError("drop count must not be negative")
        with self._lock:
            self.dropped_packets += count

    def set_active_alerts(self, count: int) -> None:
        """Set the current number of active alert conditions."""

        with self._lock:
            self.active_alerts = max(0, count)

    def set_fleet_sync(self, score: float) -> None:
        """Set the current fleet sync score in the contract's 0-100 range."""

        with self._lock:
            self.fleet_sync_score = min(100.0, max(0.0, score))

    def snapshot(self) -> dict[str, float | int]:
        """Return a consistent point-in-time metric snapshot."""

        now = time.monotonic()
        with self._lock:
            elapsed = max(now - self._previous_ingest_at, 1e-9)
            ingest_delta = self.ingest_count - self._previous_ingest_count
            ingest_rate = ingest_delta / elapsed
            self._previous_ingest_count = self.ingest_count
            self._previous_ingest_at = now
            return {
                "uptime_s": max(0.0, now - self.started_at),
                "request_count": self.request_count,
                "request_latency_sum_s": self.request_latency_sum_s,
                "ingest_count": self.ingest_count,
                "ingest_rate": ingest_rate,
                "dropped_packets": self.dropped_packets,
                "active_alerts": self.active_alerts,
                "fleet_sync_score": self.fleet_sync_score,
                "last_ingest_age_s": (
                    -1.0 if self._last_ingest_at is None else max(0.0, now - self._last_ingest_at)
                ),
            }


# A descriptive alias makes integrations that use "metrics registry" terminology clearer.
ObservabilityMetrics = FleetMetrics
