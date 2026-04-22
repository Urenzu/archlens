from typing import Optional, Callable
from core.logging import info, warn, error
from core.errors import AuthError, RateLimitError, raise_auth
from auth.tokens import verify_token, is_revoked, extract_user_id
from auth.permissions import require_permission, is_admin


_revocation_store: dict = {}
_rate_limit_counters: dict = {}
_rate_limit_window = 60
_rate_limit_max = 100


def extract_bearer_token(headers: dict) -> Optional[str]:
    auth = headers.get("Authorization") or headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def authenticate_request(headers: dict) -> dict:
    token = extract_bearer_token(headers)
    if not token:
        raise_auth("No token provided")
    if is_revoked(token, _revocation_store):
        raise_auth("Token has been revoked")
    claims = verify_token(token)
    info("request_authenticated", user_id=claims.get("sub"))
    return claims


def optional_authenticate(headers: dict) -> Optional[dict]:
    try:
        return authenticate_request(headers)
    except AuthError:
        return None


def check_rate_limit(user_id: str, endpoint: str) -> None:
    import time
    key = f"{user_id}:{endpoint}"
    now = int(time.time())
    window_start = now - _rate_limit_window
    hits = _rate_limit_counters.get(key, [])
    hits = [t for t in hits if t > window_start]
    if len(hits) >= _rate_limit_max:
        warn("rate_limit_exceeded", user_id=user_id, endpoint=endpoint)
        raise RateLimitError(f"Rate limit exceeded for {endpoint}")
    hits.append(now)
    _rate_limit_counters[key] = hits


def require_auth_middleware(handler: Callable) -> Callable:
    def wrapped(request: dict) -> dict:
        claims = authenticate_request(request.get("headers", {}))
        request["user"] = claims
        return handler(request)
    return wrapped


def require_admin_middleware(handler: Callable) -> Callable:
    def wrapped(request: dict) -> dict:
        claims = authenticate_request(request.get("headers", {}))
        if not is_admin(claims.get("roles", [])):
            raise_auth("Admin access required")
        request["user"] = claims
        return handler(request)
    return wrapped


def rate_limit_middleware(handler: Callable) -> Callable:
    def wrapped(request: dict) -> dict:
        user_id = request.get("user", {}).get("sub", request.get("remote_addr", "anon"))
        endpoint = request.get("path", "/")
        check_rate_limit(user_id, endpoint)
        return handler(request)
    return wrapped


def cors_headers(response: dict, origin: str = "*") -> dict:
    response.setdefault("headers", {})
    response["headers"]["Access-Control-Allow-Origin"] = origin
    response["headers"]["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response["headers"]["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    return response


def get_current_user_id(request: dict) -> str:
    user = request.get("user")
    if not user:
        raise_auth()
    return user["sub"]


def invalidate_user_sessions(user_id: str) -> int:
    removed = 0
    for token, exp in list(_revocation_store.items()):
        try:
            from auth.tokens import decode_without_verify
            claims = decode_without_verify(token)
            if claims.get("sub") == user_id:
                del _revocation_store[token]
                removed += 1
        except Exception:
            pass
    return removed
