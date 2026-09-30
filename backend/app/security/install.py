"""FastAPI integration for FleetTwin authentication and request limiting."""

from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from app.contract.schemas import Token

from .auth import AuthenticationError, AuthUser, authenticate, decode_token, issue_token
from .rate_limit import RateLimiter


class LoginRequest(BaseModel):
    username: str
    password: str


def auth_enabled() -> bool:
    """Read the feature flag using conventional truthy environment values."""

    return os.getenv("AUTH_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client is not None else "unknown"


class SecurityMiddleware(BaseHTTPMiddleware):
    """Apply authentication and role checks to API requests when enabled."""

    def __init__(self, app: Any, limiter: RateLimiter) -> None:
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        path = request.url.path
        if path.startswith("/api/") and not self.limiter.allow(f"{_client_key(request)}:{path}"):
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": "60"},
            )

        public = {
            "/api/auth/login",
            "/api/health",
            "/health",
            "/metrics",
        }
        if not auth_enabled() or path in public or request.method == "OPTIONS":
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse({"detail": "authentication required"}, status_code=status.HTTP_401_UNAUTHORIZED)
        try:
            user = decode_token(token)
        except AuthenticationError:
            return JSONResponse({"detail": "invalid or expired token"}, status_code=status.HTTP_401_UNAUTHORIZED)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and user.role != "operator":
            return JSONResponse({"detail": "operator role required"}, status_code=status.HTTP_403_FORBIDDEN)
        request.state.user = user
        return await call_next(request)


def get_current_user(request: Request) -> AuthUser:
    """FastAPI dependency for routes that need the authenticated identity."""

    if not auth_enabled():
        return AuthUser(username="anonymous", role="operator")
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return user


def install(app: Any) -> Any:
    """Install auth login, JWT middleware and rate limiting once on an app."""

    if getattr(app.state, "security_installed", False):
        return app
    limiter = RateLimiter(
        limit=int(os.getenv("RATE_LIMIT", "120")),
        window_s=float(os.getenv("RATE_LIMIT_WINDOW_S", "60")),
    )
    app.state.rate_limiter = limiter

    @app.post("/api/auth/login", response_model=Token, tags=["auth"])
    async def login(credentials: LoginRequest) -> Token:
        try:
            user = authenticate(credentials.username, credentials.password)
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password") from exc
        return Token(access_token=issue_token(user), role=user.role)

    app.add_middleware(SecurityMiddleware, limiter=limiter)
    app.state.security_installed = True
    return app
