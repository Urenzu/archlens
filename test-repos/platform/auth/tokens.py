import hmac
import hashlib
import time
import json
import base64
from typing import Optional

from core.config import get_secret_key
from core.logging import debug, warn
from core.errors import AuthError


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def _sign(payload: str) -> str:
    key = get_secret_key().encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_token(user_id: str, roles: list[str], ttl: int = 3600) -> str:
    header = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    claims = {
        "sub": user_id,
        "roles": roles,
        "iat": now,
        "exp": now + ttl,
    }
    payload = _b64_encode(json.dumps(claims).encode())
    sig = _sign(f"{header}.{payload}")
    debug("token_created", user_id=user_id, ttl=ttl)
    return f"{header}.{payload}.{sig}"


def verify_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Malformed token")
    header, payload, sig = parts
    expected = _sign(f"{header}.{payload}")
    if not hmac.compare_digest(sig, expected):
        warn("token_signature_invalid")
        raise AuthError("Invalid token signature")
    try:
        claims = json.loads(_b64_decode(payload))
    except Exception:
        raise AuthError("Token payload unreadable")
    if claims.get("exp", 0) < int(time.time()):
        raise AuthError("Token expired")
    return claims


def refresh_token(token: str, ttl: int = 3600) -> str:
    claims = verify_token(token)
    return create_token(claims["sub"], claims.get("roles", []), ttl)


def extract_user_id(token: str) -> str:
    return verify_token(token)["sub"]


def extract_roles(token: str) -> list[str]:
    return verify_token(token).get("roles", [])


def revoke_token(token: str, store: dict) -> None:
    claims = verify_token(token)
    store[token] = claims.get("exp", 0)
    debug("token_revoked", user_id=claims.get("sub"))


def is_revoked(token: str, store: dict) -> bool:
    return token in store


def decode_without_verify(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    try:
        return json.loads(_b64_decode(parts[1]))
    except Exception:
        return {}
