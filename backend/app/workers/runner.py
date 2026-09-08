"""Small in-process task runner for a single-user local installation.

The crawler performs network and file I/O, so a bounded thread pool keeps API
requests responsive without requiring Redis, Celery, or a separate worker.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from app.core.config import settings


_executor = ThreadPoolExecutor(
    max_workers=max(1, settings.local_task_workers),
    thread_name_prefix="northstar-scan",
)
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = Lock()


def _iso_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def enqueue(func: Callable[..., Any], *args: Any, label: str | None = None) -> str:
    job_id = uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "label": label or func.__name__.replace("_", " "),
            "status": "queued",
            "created_at": _iso_now(),
            "started_at": None,
            "finished_at": None,
            "error": None,
            "error_detail": None,
            "result": None,
        }

    def run() -> None:
        with _jobs_lock:
            _jobs[job_id]["status"] = "running"
            _jobs[job_id]["started_at"] = _iso_now()
        try:
            result = func(*args)
        except Exception as exc:  # the UI receives a concise local diagnostic
            with _jobs_lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = str(exc)[:500]
                if callable(getattr(exc, "as_dict", None)):
                    _jobs[job_id]["error_detail"] = exc.as_dict()
        else:
            with _jobs_lock:
                _jobs[job_id]["status"] = "completed"
                _jobs[job_id]["result"] = result
        finally:
            with _jobs_lock:
                _jobs[job_id]["finished_at"] = _iso_now()

    _executor.submit(run)
    return job_id


def recent_jobs(limit: int = 30) -> list[dict[str, Any]]:
    with _jobs_lock:
        jobs = list(_jobs.values())
    return sorted(jobs, key=lambda item: item["created_at"], reverse=True)[:limit]


def get_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None
