
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
