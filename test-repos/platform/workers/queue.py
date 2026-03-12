import threading
import time
import uuid
from typing import Any, Callable, Optional
from core.logging import debug, info, warn


_queue: list = []
_lock = threading.Lock()
_job_index: dict = {}


JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_RETRYING = "retrying"


def enqueue(job_type: str, payload: dict, priority: int = 5, delay: float = 0.0) -> str:
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "type": job_type,
        "payload": payload,
        "priority": priority,
        "status": JOB_PENDING,
        "enqueued_at": time.time(),
        "run_after": time.time() + delay,
        "attempts": 0,
        "max_attempts": 3,
        "result": None,
        "error": None,
    }
    with _lock:
        _queue.append(job)
        _queue.sort(key=lambda j: (-j["priority"], j["run_after"]))
        _job_index[job_id] = job
    info("job_enqueued", job_id=job_id, job_type=job_type, priority=priority)
    return job_id


def dequeue() -> Optional[dict]:
    now = time.time()
    with _lock:
        for job in _queue:
            if job["status"] == JOB_PENDING and job["run_after"] <= now:
                job["status"] = JOB_RUNNING
                job["started_at"] = now
                return job
    return None


def complete(job_id: str, result: Any = None) -> None:
    with _lock:
        job = _job_index.get(job_id)
        if job:
            job["status"] = JOB_DONE
            job["result"] = result
            job["finished_at"] = time.time()
    info("job_completed", job_id=job_id)


def fail(job_id: str, error: str, retry: bool = True) -> None:
    with _lock:
        job = _job_index.get(job_id)
        if not job:
            return
        job["attempts"] += 1
        job["error"] = error
        if retry and job["attempts"] < job["max_attempts"]:
            backoff = 2 ** job["attempts"]
            job["status"] = JOB_RETRYING
            job["run_after"] = time.time() + backoff
            warn("job_retrying", job_id=job_id, attempt=job["attempts"], backoff=backoff)
        else:
            job["status"] = JOB_FAILED
            job["finished_at"] = time.time()
            warn("job_failed", job_id=job_id, error=error)


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        return _job_index.get(job_id)


def cancel(job_id: str) -> bool:
    with _lock:
        job = _job_index.get(job_id)
        if job and job["status"] == JOB_PENDING:
            job["status"] = "cancelled"
            return True
    return False


def queue_depth() -> dict:
    with _lock:
        counts: dict = {JOB_PENDING: 0, JOB_RUNNING: 0, JOB_DONE: 0, JOB_FAILED: 0, JOB_RETRYING: 0}
        for job in _queue:
            s = job["status"]
            if s in counts:
                counts[s] += 1
    return counts


def drain_completed(max_age: float = 3600.0) -> int:
    now = time.time()
    removed = 0
    with _lock:
        to_remove = [
            j for j in _queue
            if j["status"] in (JOB_DONE, JOB_FAILED)
            and (now - j.get("finished_at", now)) > max_age
        ]
        for j in to_remove:
            _queue.remove(j)
            del _job_index[j["id"]]
            removed += 1
    debug("queue_drained", removed=removed)
    return removed


def peek(n: int = 10) -> list:
    with _lock:
        return [j.copy() for j in _queue[:n]]


def requeue_stuck(timeout: float = 300.0) -> int:
    now = time.time()
    requeued = 0
    with _lock:
        for job in _queue:
            if job["status"] == JOB_RUNNING:
                started = job.get("started_at", now)
                if (now - started) > timeout:
                    job["status"] = JOB_PENDING
                    job["run_after"] = now
                    requeued += 1
    if requeued:
        warn("stuck_jobs_requeued", count=requeued)
    return requeued
