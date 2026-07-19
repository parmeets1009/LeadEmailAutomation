"""Signed one-click unsubscribe tokens. Stdlib HMAC — no extra dependency.

Token = base64url(email) + "." + first 16 hex chars of HMAC-SHA256(secret, email).
Rotating the secret invalidates outstanding links (accepted tradeoff).
"""
from __future__ import annotations

import base64
import hashlib
import hmac

DEV_SECRET = "dev-secret-not-for-production"


def _signature(email: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), email.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def make_token(email: str, secret: str) -> str:
    normalized = email.strip().lower()
    encoded = base64.urlsafe_b64encode(normalized.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{encoded}.{_signature(normalized, secret)}"


def verify_token(token: str, secret: str) -> str | None:
    """Return the email for a valid token, None for anything else. Never raises."""
    try:
        encoded, signature = token.rsplit(".", 1)
        padded = encoded + "=" * (-len(encoded) % 4)
        email = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception:  # noqa: BLE001 — attacker-controlled input; any failure is just "invalid"
        return None
    if not email.strip():
        return None
    if not hmac.compare_digest(signature, _signature(email, secret)):
        return None
    return email.strip().lower()


def unsubscribe_url(base_url: str, email: str, secret: str) -> str:
    return f"{base_url.rstrip('/')}/u/{make_token(email, secret)}"
