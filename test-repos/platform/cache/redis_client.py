import json
import time
import threading
from typing import Optional, Any
from core.config import get_redis_url
from core.logging import debug, warn, log_cache_hit, log_cache_miss


# In-memory stub simulating Redis behaviour
_store: dict = {}
_expiry: dict = {}
_lock = threading.Lock()


def connect() -> bool:
    url = get_redis_url()
    debug("redis_connect", url=url)
    return True


def get(key: str) -> Optional[str]:
    with _lock:
        if key in _expiry and _expiry[key] < time.time():
            del _store[key]
            del _expiry[key]
            log_cache_miss(key)
            return None
        val = _store.get(key)
    if val is not None:
        log_cache_hit(key)
    else:
        log_cache_miss(key)
    return val


def set(key: str, value: str, ttl: Optional[int] = None) -> None:
    with _lock:
        _store[key] = value
        if ttl:
            _expiry[key] = time.time() + ttl
        debug("cache_set", key=key, ttl=ttl)


def delete(key: str) -> bool:
    with _lock:
        existed = key in _store
        _store.pop(key, None)
        _expiry.pop(key, None)
    return existed


def exists(key: str) -> bool:
    with _lock:
        if key in _expiry and _expiry[key] < time.time():
            return False
        return key in _store


def get_json(key: str) -> Optional[Any]:
    val = get(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        warn("cache_json_decode_error", key=key)
        return None


def set_json(key: str, value: Any, ttl: Optional[int] = None) -> None:
    set(key, json.dumps(value), ttl)


def increment(key: str, amount: int = 1) -> int:
    with _lock:
        current = int(_store.get(key, 0))
        new_val = current + amount
        _store[key] = str(new_val)
    return new_val


def expire(key: str, ttl: int) -> bool:
    with _lock:
        if key not in _store:
            return False
        _expiry[key] = time.time() + ttl
    return True


def flush_pattern(pattern: str) -> int:
    import fnmatch
    removed = 0
    with _lock:
        keys = [k for k in list(_store.keys()) if fnmatch.fnmatch(k, pattern)]
        for k in keys:
            del _store[k]
            _expiry.pop(k, None)
            removed += 1
    debug("cache_flush_pattern", pattern=pattern, removed=removed)
    return removed


def stats() -> dict:
    with _lock:
        now = time.time()
        live = sum(1 for k in _store if _expiry.get(k, now + 1) > now)
        return {"total_keys": len(_store), "live_keys": live, "expired_keys": len(_store) - live}
