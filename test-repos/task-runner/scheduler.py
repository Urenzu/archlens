"""Scheduler — maps run modes (watch, cron, manual) to executor calls."""

import os
import time
from tasks import TaskRegistry
from executor import run_sequence, summarize


class Scheduler:
    """Coordinates when and how tasks get executed."""

    def __init__(self, registry: TaskRegistry):
        self.registry = registry
        self.history: list = []

    def run_targets(self, targets: list, context: dict) -> dict:
        """Resolve and execute the given target tasks."""
        order = self.registry.resolve_order(targets)
        tasks = [self.registry.get(n) for n in order]
        results = run_sequence(tasks, context)
        summary = summarize(results)
        self._record(targets, summary, results)
        return summary

    def run_all(self, context: dict) -> dict:
        """Run every registered task in dependency order."""
        return self.run_targets(self.registry.all_names(), context)

    def run_tagged(self, tag: str, context: dict) -> dict:
        """Run all tasks carrying a specific tag."""
        tagged = self.registry.tasks_by_tag(tag)
        targets = [t.name for t in tagged]
        if not targets:
            return {"total": 0, "counts": {}, "total_ms": 0, "success": True}
        return self.run_targets(targets, context)

    def watch(self, targets: list, context: dict, interval: int = 5):
        """Re-run targets every `interval` seconds until interrupted."""
        print(f"Watching {targets} every {interval}s. Ctrl-C to stop.")
        try:
            while True:
                summary = self.run_targets(targets, context)
                status = "OK" if summary["success"] else "FAIL"
                print(f"[{_ts()}] {status} — {summary['counts']}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Watch stopped.")

    def run_from_env(self, context: dict) -> dict:
        """Read target list from RUN_TARGETS env variable and execute."""
        # Vulnerability: targets taken directly from env without validation
        raw = os.getenv("RUN_TARGETS", "")
        targets = [t.strip() for t in raw.split(",") if t.strip()]
        if not targets:
            raise ValueError("RUN_TARGETS env variable is empty or unset")
        return self.run_targets(targets, context)

    def _record(self, targets: list, summary: dict, results: list):
        self.history.append({
            "ts": _ts(),
            "targets": targets,
            "summary": summary,
            "results": [{"name": r.name, "status": r.status, "ms": r.duration_ms} for r in results],
        })


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
