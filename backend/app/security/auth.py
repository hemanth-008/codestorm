"""Small JWT-compatible authentication implementation for FleetTwin."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping


class AuthenticationError(ValueError):
    """Raised when credentials or a bearer token cannot be verified."""


@dataclass(frozen=True)
class AuthUser:
    """Authenticated identity attached to a request."""

    username: str
    role: str


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def jwt_secret() -> bytes:
    """Return the configured signing key, with a local-only development fallback."""

    return os.getenv("JWT_SECRET", "fleettwin-development-secret").encode("utf-8")


def _configured_users() -> dict[str, tuple[str, str]]:
    """Read credentials from environment variables without storing plaintext globally."""

    users: dict[str, tuple[str, str]] = {
        "operator": (os.getenv("AUTH_OPERATOR_PASSWORD", "operator"), "operator"),
        "viewer": (os.getenv("AUTH_VIEWER_PASSWORD", "viewer"), "viewer"),
    }
    raw_users = os.getenv("AUTH_USERS", "")
    if raw_users:
        try:
            parsed = json.loads(raw_users)
        except json.JSONDecodeError as exc:
            raise AuthenticationError("AUTH_USERS must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise AuthenticationError("AUTH_USERS must be a JSON object")
        for username, value in parsed.items():
            if isinstance(value, str):
                users[str(username)] = (value, "viewer")
            elif isinstance(value, dict):
                password = value.get("password")
                role = value.get("role", "viewer")
                if isinstance(password, str) and role in {"operator", "viewer"}:
                    users[str(username)] = (password, role)
    return users


def authenticate(username: str, password: str) -> AuthUser:
    """Validate a configured username/password pair."""

    configured = _configured_users().get(username)
    if configured is None or not hmac.compare_digest(password, configured[0]):
        raise AuthenticationError("invalid username or password")
    return AuthUser(username=username, role=configured[1])


def issue_token(user: AuthUser, *, ttl_s: int = 3600) -> str:
    """Issue an HS256 JWT with an expiry in Unix seconds."""

    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user.username, "role": user.role, "iat": now, "exp": now + ttl_s}
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(jwt_secret(), message, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64encode(signature)}"


def decode_token(token: str) -> AuthUser:
    """Verify an HS256 JWT and return its FleetTwin identity."""

    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        message = f"{encoded_header}.{encoded_payload}".encode("ascii")
        actual = _b64decode(encoded_signature)
        expected = hmac.new(jwt_secret(), message, hashlib.sha256).digest()
        if not hmac.compare_digest(actual, expected):
            raise AuthenticationError("invalid token signature")
        header = json.loads(_b64decode(encoded_header))
        payload: Mapping[str, Any] = json.loads(_b64decode(encoded_payload))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise AuthenticationError("unsupported token")
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise AuthenticationError("token expired")
        username = payload.get("sub")
        role = payload.get("role")
        if not isinstance(username, str) or role not in {"operator", "viewer"}:
            raise AuthenticationError("invalid token claims")
        return AuthUser(username=username, role=role)
    except (AuthenticationError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, AuthenticationError):
            raise
        raise AuthenticationError("invalid token") from exc
