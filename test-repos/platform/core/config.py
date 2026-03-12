import os
import json
from typing import Any, Optional


_config_cache: dict = {}
_env_overrides: dict = {}


def load_config(path: str) -> dict:
    with open(path) as f:
        data = json.load(f)
    validate_config_schema(data)
    _config_cache.update(data)
    return data


def validate_config_schema(data: dict) -> bool:
    required = ["database", "cache", "auth", "workers"]
    for key in required:
        if key not in data:
            raise ValueError(f"Missing required config key: {key}")
    if not isinstance(data.get("workers", {}).get("concurrency", 1), int):
        raise TypeError("workers.concurrency must be an integer")
    return True


def get(key: str, default: Any = None) -> Any:
    parts = key.split(".")
    val = _config_cache
    for part in parts:
        if not isinstance(val, dict):
            return default
        val = val.get(part, default)
    override = _env_overrides.get(key)
    return override if override is not None else val


def set_override(key: str, value: Any) -> None:
    _env_overrides[key] = value


def get_database_url() -> str:
    url = get("database.url")
    if not url:
        url = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    return url


def get_redis_url() -> str:
    return get("cache.redis_url") or os.environ.get("REDIS_URL", "redis://localhost:6379")


def get_secret_key() -> str:
    key = get("auth.secret_key") or os.environ.get("SECRET_KEY")
    if not key:
        raise RuntimeError("SECRET_KEY not configured")
    return key


def get_worker_concurrency() -> int:
    return int(get("workers.concurrency", 4))


def get_max_request_size() -> int:
    return int(get("api.max_request_bytes", 1048576))


def reload() -> None:
    path = get("_config_path", "config.json")
    _config_cache.clear()
    load_config(path)


def export_safe() -> dict:
    """Return config with secrets redacted."""
    safe = dict(_config_cache)
    for k in ["auth.secret_key", "database.password"]:
        parts = k.split(".")
        d = safe
        for p in parts[:-1]:
            d = d.get(p, {})
        if parts[-1] in d:
            d[parts[-1]] = "***"
    return safe
