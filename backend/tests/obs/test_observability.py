from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.install import install


def test_health_and_metrics_are_mounted():
    app = FastAPI()
    install(app)
    app.state.metrics.record_ingest(3)
    app.state.metrics.record_drop()
    app.state.metrics.set_active_alerts(2)

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        text = client.get("/metrics").text
        assert "fleettwin_ingest_messages_total 3" in text
        assert "fleettwin_dropped_packets_total 1" in text
        assert "fleettwin_active_alerts 2" in text
        assert app.state.metrics.request_count >= 2
