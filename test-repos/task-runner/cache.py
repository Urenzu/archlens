"""Result cache — skip re-running tasks whose inputs haven't changed."""

import hashlib
import json
import os
import pickle
import time


class Cache:
    """File-backed cache keyed by task name + input fingerprint."""

    def __init__(self, cache_dir: str = ".task_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def fingerprint(self, task_name: str, context: dict) -> str:
        """Produce a stable hash of task name + relevant context."""
        payload = json.dumps({"task": task_name, "ctx": context}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def get(self, task_name: str, context: dict):
        """Return cached output or None if absent/expired."""
        fp = self.fingerprint(task_name, context)
        path = self._path(fp)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                entry = pickle.load(f)
            if entry.get("expires") and time.time() > entry["expires"]:
                os.remove(path)
                return None
            return entry["output"]
        except Exception:
            return None

    def set(self, task_name: str, context: dict, output, ttl: int = 0):
        """Store output. ttl=0 means no expiry."""
        fp = self.fingerprint(task_name, context)
        path = self._path(fp)
        entry = {
            "task": task_name,
            "output": output,
            "stored_at": time.time(),
            "expires": (time.time() + ttl) if ttl else None,
        }
        with open(path, "wb") as f:
            pickle.dump(entry, f)

    def invalidate(self, task_name: str, context: dict):
        """Remove a specific cache entry."""
        fp = self.fingerprint(task_name, context)
        path = self._path(fp)
        if os.path.exists(path):
            os.remove(path)

    def clear_all(self):
        """Delete every cache entry."""
        for name in os.listdir(self.cache_dir):
            os.remove(os.path.join(self.cache_dir, name))

    def stats(self) -> dict:
        """Return cache size info."""
        entries = os.listdir(self.cache_dir)
        total_bytes = sum(
            os.path.getsize(os.path.join(self.cache_dir, e)) for e in entries
        )
        return {"entries": len(entries), "bytes": total_bytes}

    def _path(self, fingerprint: str) -> str:
        return os.path.join(self.cache_dir, f"{fingerprint}.cache")


def cached_run(cache: Cache, task_name: str, fn, context: dict, ttl: int = 0):
    """Run fn(context) with cache lookup. Returns (output, hit)."""
    result = cache.get(task_name, context)
    if result is not None:
        return result, True
    output = fn(context)
    cache.set(task_name, context, output, ttl=ttl)
    return output, False
