import threading
import time
from typing import Optional
from core.logging import info, warn, debug
from workers.queue import dequeue, complete, fail, queue_depth, drain_completed, requeue_stuck
from workers.jobs import dispatch_job


_running = False
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()

DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_DRAIN_INTERVAL = 300.0
DEFAULT_STUCK_TIMEOUT = 300.0


def start(poll_interval: float = DEFAULT_POLL_INTERVAL) -> bool:
    global _running, _thread
    with _lock:
        if _running:
            warn("executor_already_running")
            return False
        _running = True
        _thread = threading.Thread(target=_run_loop, args=(poll_interval,), daemon=True)
        _thread.start()
    info("executor_started", poll_interval=poll_interval)
    return True


def stop(timeout: float = 5.0) -> bool:
    global _running, _thread
    with _lock:
        if not _running:
            return True
        _running = False
    if _thread:
        _thread.join(timeout=timeout)
        _thread = None
    info("executor_stopped")
    return True


def is_running() -> bool:
    with _lock:
        return _running


def _run_loop(poll_interval: float) -> None:
    last_drain = time.time()
    last_stuck_check = time.time()
    info("executor_loop_started")
    while _running:
        _process_one()
        now = time.time()
        if now - last_drain > DEFAULT_DRAIN_INTERVAL:
            _run_maintenance(now)
            last_drain = now
        if now - last_stuck_check > DEFAULT_STUCK_TIMEOUT:
            requeue_stuck(DEFAULT_STUCK_TIMEOUT)
            last_stuck_check = now
        time.sleep(poll_interval)
    info("executor_loop_stopped")


def _process_one() -> bool:
    job = dequeue()
    if job is None:
        return False
    job_id = job["id"]
    job_type = job["type"]
    debug("job_processing", job_id=job_id, job_type=job_type)
    try:
        result = dispatch_job(job)
        complete(job_id, result)
        return True
    except Exception as e:
        warn("job_error", job_id=job_id, job_type=job_type, error=str(e))
        fail(job_id, str(e))
        return False


def _run_maintenance(now: float) -> None:
    removed = drain_completed(max_age=3600.0)
    depth = queue_depth()
    debug("executor_maintenance", removed=removed, depth=depth)


def run_once() -> int:
    processed = 0
    while True:
        job = dequeue()
        if job is None:
            break
        job_id = job["id"]
        try:
            result = dispatch_job(job)
            complete(job_id, result)
        except Exception as e:
            fail(job_id, str(e))
        processed += 1
    info("executor_run_once", processed=processed)
    return processed


def status() -> dict:
    return {
        "running": is_running(),
        "queue": queue_depth(),
    }


def run_job_inline(job_type: str, payload: dict) -> dict:
    from workers.queue import enqueue, get_job
    job_id = enqueue(job_type, payload)
    job = get_job(job_id)
    if not job:
        return {"error": "job not found"}
    try:
        result = dispatch_job(job)
        complete(job_id, result)
        return {"status": "done", "result": result}
    except Exception as e:
        fail(job_id, str(e), retry=False)
        return {"status": "failed", "error": str(e)}
