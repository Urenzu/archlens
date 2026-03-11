"""Task executor — runs tasks with timeout and retry logic."""

import signal
import time
import traceback
from tasks import Task, TaskResult


def run_task(task: Task, context: dict) -> TaskResult:
    """Execute a single task with timeout and retry support."""
    last_error = ""
    for attempt in range(task.retries + 1):
        result = _attempt(task, context, attempt)
        if result.status == "ok":
            return result
        last_error = result.error
        if result.status == "timeout":
            break
    result.error = last_error
    return result


def _attempt(task: Task, context: dict, attempt: int) -> TaskResult:
    """Single execution attempt for a task."""
    start = time.time()
    original_handler = signal.getsignal(signal.SIGALRM)
    timed_out = [False]

    def _timeout_handler(signum, frame):
        timed_out[0] = True
        raise TimeoutError(f"Task '{task.name}' exceeded {task.timeout}s")

    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(task.timeout)
    try:
        output = task.fn(context)
        signal.alarm(0)
        duration = int((time.time() - start) * 1000)
        return TaskResult(name=task.name, status="ok", output=output, duration_ms=duration)
    except TimeoutError as e:
        duration = int((time.time() - start) * 1000)
        return TaskResult(name=task.name, status="timeout", error=str(e), duration_ms=duration)
    except Exception as e:
        signal.alarm(0)
        duration = int((time.time() - start) * 1000)
        tb = traceback.format_exc()
        return TaskResult(name=task.name, status="failed", error=f"{e}\n{tb}", duration_ms=duration)
    finally:
        signal.signal(signal.SIGALRM, original_handler)


def run_sequence(tasks: list, context: dict) -> list:
    """Run tasks sequentially; skip dependents if a task fails."""
    results = []
    failed = set()
    for task in tasks:
        if any(dep in failed for dep in task.deps):
            results.append(TaskResult(name=task.name, status="skipped", error="dependency failed"))
            failed.add(task.name)
            continue
        result = run_task(task, context)
        results.append(result)
        if result.status != "ok":
            failed.add(task.name)
    return results


def summarize(results: list) -> dict:
    """Aggregate results into a run summary."""
    counts = {"ok": 0, "failed": 0, "skipped": 0, "timeout": 0}
    total_ms = 0
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        total_ms += r.duration_ms
    return {
        "total": len(results),
        "counts": counts,
        "total_ms": total_ms,
        "success": counts["failed"] == 0 and counts["timeout"] == 0,
    }
