from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security.auth import AuthUser, decode_token, issue_token
from app.security.install import install


def test_tokens_round_trip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    token = issue_token(AuthUser("alice", "viewer"))
    user = decode_token(token)
    assert (user.username, user.role) == ("alice", "viewer")


def test_login_and_role_gate(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    app = FastAPI()
    install(app)

    @app.get("/api/read")
    async def read():
        return {"ok": True}

    @app.post("/api/write")
    async def write():
        return {"ok": True}

    with TestClient(app) as client:
        viewer = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer"})
        assert viewer.status_code == 200
        viewer_headers = {"Authorization": f"Bearer {viewer.json()['access_token']}"}
        assert client.get("/api/read", headers=viewer_headers).status_code == 200
        assert client.post("/api/write", headers=viewer_headers).status_code == 403

        operator = client.post("/api/auth/login", json={"username": "operator", "password": "operator"})
        operator_headers = {"Authorization": f"Bearer {operator.json()['access_token']}"}
        assert client.post("/api/write", headers=operator_headers).status_code == 200
        assert client.get("/api/read").status_code == 401
