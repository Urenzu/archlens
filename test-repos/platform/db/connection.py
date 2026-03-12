import time
import threading
from typing import Optional, Any
from core.config import get_database_url
from core.logging import info, warn, error, log_query


_pool: list = []
_pool_lock = threading.Lock()
_pool_size = 10
_checked_out: dict = {}


class Connection:
    def __init__(self, conn_id: int, url: str):
        self.id = conn_id
        self.url = url
        self.created_at = time.time()
        self.last_used = time.time()
        self._closed = False

    def execute(self, sql: str, params: tuple = ()) -> list:
        start = time.time()
        self.last_used = time.time()
        # stub — real implementation would use a driver
        rows = []
        log_query(sql, (time.time() - start) * 1000, len(rows))
        return rows

    def close(self) -> None:
        self._closed = True

    def is_healthy(self) -> bool:
        if self._closed:
            return False
        age = time.time() - self.created_at
        return age < 3600


def initialize_pool(size: int = 10) -> None:
    global _pool_size
    _pool_size = size
    url = get_database_url()
    with _pool_lock:
        for i in range(size):
            _pool.append(Connection(i, url))
    info("db_pool_initialized", size=size, url=url.split("@")[-1])


def acquire() -> Connection:
    deadline = time.time() + 5.0
    while time.time() < deadline:
        with _pool_lock:
            for conn in _pool:
                if conn.id not in _checked_out and conn.is_healthy():
                    _checked_out[conn.id] = time.time()
                    return conn
        time.sleep(0.05)
    raise TimeoutError("No database connections available")


def release(conn: Connection) -> None:
    with _pool_lock:
        _checked_out.pop(conn.id, None)


def execute_query(sql: str, params: tuple = ()) -> list:
    conn = acquire()
    try:
        return conn.execute(sql, params)
    finally:
        release(conn)


def execute_one(sql: str, params: tuple = ()) -> Optional[dict]:
    rows = execute_query(sql, params)
    return rows[0] if rows else None


def execute_many(sql: str, params_list: list) -> int:
    conn = acquire()
    count = 0
    try:
        for params in params_list:
            conn.execute(sql, params)
            count += 1
    finally:
        release(conn)
    return count


def transaction(fn) -> Any:
    conn = acquire()
    try:
        conn.execute("BEGIN")
        result = fn(conn)
        conn.execute("COMMIT")
        return result
    except Exception as e:
        conn.execute("ROLLBACK")
        error("transaction_failed", exc=e)
        raise
    finally:
        release(conn)


def health_check() -> bool:
    try:
        execute_query("SELECT 1")
        return True
    except Exception:
        return False


def pool_stats() -> dict:
    with _pool_lock:
        return {
            "total": len(_pool),
            "checked_out": len(_checked_out),
            "available": len(_pool) - len(_checked_out),
        }


def close_pool() -> None:
    with _pool_lock:
        for conn in _pool:
            conn.close()
        _pool.clear()
        _checked_out.clear()
    info("db_pool_closed")
