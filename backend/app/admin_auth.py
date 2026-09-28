"""
Minimal stateless admin authentication.

DELIBERATE SCOPE DECISION (see decision log): this is a single shared admin
password (ADMIN_PASSWORD in .env), not per-admin accounts. No password
hashing/salting (there's nothing to hash - it's one shared secret compared
directly), no server-side session storage, no login-attempt rate limiting,
no per-admin audit trail. The assignment calls the admin interface an
"observation and control interface, not a CRM" (Section 2.5), so gating it
behind a shared password correctly signals "this is restricted" without
building a disproportionate amount of real user-account infrastructure for
an internal tool. A real product would replace this with per-admin
accounts behind a proper identity provider.

Tokens are self-verifying (HMAC-signed, with an embedded issue timestamp),
so the backend needs no session table at all - verifying a token is just
recomputing its signature and checking the embedded timestamp hasn't
expired.
"""
import base64
import hashlib
import hmac
import time

TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60  # 8-hour admin session


def create_admin_token(secret: str) -> str:
    payload = f"admin:{int(time.time())}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def verify_admin_token(token: str, secret: str) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        _, issued_at_str, signature = decoded.split(":")
        payload = f"admin:{issued_at_str}"
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        return (time.time() - int(issued_at_str)) <= TOKEN_MAX_AGE_SECONDS
    except Exception:
        return False
