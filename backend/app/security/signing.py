"""HMAC signing for telemetry packets."""

from __future__ import annotations

import hashlib
import hmac

from app.contract.schemas import Telemetry


def _canonical_payload(tel: Telemetry) -> str:
    """Return the stable wire representation covered by the telemetry MAC."""

    return (
        f"{tel.robot_id}|{tel.seq}|{tel.ts:.3f}|{tel.x:.3f}|{tel.y:.3f}|"
        f"{tel.speed:.3f}|{tel.battery:.2f}"
    )


def sign_telemetry(tel: Telemetry, key: str | bytes) -> str:
    """Sign the contract fields with HMAC-SHA256 and return a hex digest."""

    secret = key.encode("utf-8") if isinstance(key, str) else key
    if not secret:
        raise ValueError("telemetry signing key must not be empty")
    return hmac.new(
        secret,
        _canonical_payload(tel).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_telemetry(tel: Telemetry, key: str | bytes) -> bool:
    """Verify a packet signature without accepting unsigned packets."""

    if not tel.sig:
        return False
    try:
        expected = sign_telemetry(tel, key)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(tel.sig, expected)
