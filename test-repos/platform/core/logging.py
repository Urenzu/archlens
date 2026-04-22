import sys
import json
import time
import traceback
from typing import Optional, Any


_log_level = "INFO"
_handlers = []
_context: dict = {}

LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3, "FATAL": 4}


def configure(level: str = "INFO", json_output: bool = False) -> None:
    global _log_level
    _log_level = level.upper()
    if json_output:
        _handlers.append(_json_handler)
    else:
        _handlers.append(_text_handler)


def set_context(**kwargs) -> None:
    _context.update(kwargs)


def clear_context() -> None:
    _context.clear()


def _should_log(level: str) -> bool:
    return LEVELS.get(level, 0) >= LEVELS.get(_log_level, 1)


def _build_record(level: str, msg: str, **kwargs) -> dict:
    return {
        "ts": time.time(),
        "level": level,
        "msg": msg,
        **_context,
        **kwargs,
    }


def _text_handler(record: dict) -> None:
    ts = record["ts"]
    level = record["level"]
    msg = record["msg"]
    extras = {k: v for k, v in record.items() if k not in ("ts", "level", "msg")}
    extra_str = " ".join(f"{k}={v}" for k, v in extras.items())
    print(f"[{level}] {msg} {extra_str}".strip(), file=sys.stderr)


def _json_handler(record: dict) -> None:
    print(json.dumps(record), file=sys.stderr)


def _emit(level: str, msg: str, **kwargs) -> None:
    if not _should_log(level):
        return
    if not _handlers:
        _handlers.append(_text_handler)
    record = _build_record(level, msg, **kwargs)
    for handler in _handlers:
        try:
            handler(record)
        except Exception:
            pass


def debug(msg: str, **kwargs) -> None:
    _emit("DEBUG", msg, **kwargs)


def info(msg: str, **kwargs) -> None:
    _emit("INFO", msg, **kwargs)


def warn(msg: str, **kwargs) -> None:
    _emit("WARN", msg, **kwargs)


def error(msg: str, exc: Optional[Exception] = None, **kwargs) -> None:
    if exc:
        kwargs["traceback"] = traceback.format_exc()
    _emit("ERROR", msg, **kwargs)


def fatal(msg: str, **kwargs) -> None:
    _emit("FATAL", msg, **kwargs)
    sys.exit(1)


def log_request(method: str, path: str, status: int, duration_ms: float) -> None:
    _emit("INFO", "http_request", method=method, path=path, status=status, duration_ms=round(duration_ms, 2))


def log_query(sql: str, duration_ms: float, rows: int = 0) -> None:
    _emit("DEBUG", "db_query", sql=sql[:120], duration_ms=round(duration_ms, 2), rows=rows)


def log_cache_hit(key: str) -> None:
    _emit("DEBUG", "cache_hit", key=key)


def log_cache_miss(key: str) -> None:
    _emit("DEBUG", "cache_miss", key=key)
