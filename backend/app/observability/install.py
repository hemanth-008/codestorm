"""FastAPI integration for health and Prometheus-compatible metrics."""

from __future__ import annotations

import time
from typing import Any

from fastapi import Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .metrics import FleetMetrics


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Measure every completed request, including requests returning errors."""

    def __init__(self, app: Any, metrics: FleetMetrics) -> None:
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        started = time.perf_counter()
        try:
            return await call_next(request)
        finally:
            self.metrics.record_request(time.perf_counter() - started)


def _metric_line(name: str, value: float | int) -> str:
    return f"{name} {value}"


def prometheus_text(metrics: FleetMetrics) -> str:
    """Render the operational counters in the Prometheus text exposition format."""

    snapshot = metrics.snapshot()
    lines = [
        "# HELP fleettwin_requests_total Total HTTP requests completed.",
        "# TYPE fleettwin_requests_total counter",
        _metric_line("fleettwin_requests_total", snapshot["request_count"]),
        "# HELP fleettwin_request_latency_seconds_total Sum of HTTP request latency.",
        "# TYPE fleettwin_request_latency_seconds_total counter",
        _metric_line("fleettwin_request_latency_seconds_total", snapshot["request_latency_sum_s"]),
        "# HELP fleettwin_ingest_messages_total Telemetry packets accepted by the ingest pipeline.",
        "# TYPE fleettwin_ingest_messages_total counter",
        _metric_line("fleettwin_ingest_messages_total", snapshot["ingest_count"]),
        "# HELP fleettwin_ingest_rate_per_second Recent telemetry ingest rate.",
        "# TYPE fleettwin_ingest_rate_per_second gauge",
        _metric_line("fleettwin_ingest_rate_per_second", snapshot["ingest_rate"]),
        "# HELP fleettwin_dropped_packets_total Telemetry packets dropped before processing.",
        "# TYPE fleettwin_dropped_packets_total counter",
        _metric_line("fleettwin_dropped_packets_total", snapshot["dropped_packets"]),
        "# HELP fleettwin_active_alerts Current active alert count.",
        "# TYPE fleettwin_active_alerts gauge",
        _metric_line("fleettwin_active_alerts", snapshot["active_alerts"]),
        "# HELP fleettwin_uptime_seconds Process uptime.",
        "# TYPE fleettwin_uptime_seconds gauge",
        _metric_line("fleettwin_uptime_seconds", snapshot["uptime_s"]),
    ]
    return "\n".join(lines) + "\n"


def install(app: Any) -> Any:
    """Mount root health and metrics endpoints once and return the app."""

    if getattr(app.state, "observability_installed", False):
        return app
    metrics = FleetMetrics()
    app.state.metrics = metrics

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, Any]:
        snapshot = metrics.snapshot()
        return {
            "status": "ok",
            "service": "fleettwin",
            "uptime_s": round(float(snapshot["uptime_s"]), 3),
            "ingest": {
                "msgs_per_s": round(float(snapshot["ingest_rate"]), 3),
                "dropped": snapshot["dropped_packets"],
            },
        }

    @app.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
    async def metrics_endpoint() -> PlainTextResponse:
        return PlainTextResponse(prometheus_text(metrics), media_type="text/plain; version=0.0.4")

    app.add_middleware(RequestMetricsMiddleware, metrics=metrics)
    app.state.observability_installed = True
    return app
