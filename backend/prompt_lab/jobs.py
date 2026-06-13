from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from itertools import count
from threading import Lock


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_COUNTER = count(1)
_TERMINAL_STATUSES = {"completed", "failed"}


@dataclass(frozen=True)
class JobEvent:
    event_id: int
    job_id: str
    status: str
    message: str
    completed_units: int
    total_units: int
    created_at: str


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    kind: str
    experiment_id: str
    version: str
    status: str
    total_units: int
    completed_units: int = 0
    message: str = ""
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None


class JobManager:
    """In-memory job status and event store for local Prompt Lab."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, JobStatus] = {}
        self._events: dict[str, list[JobEvent]] = {}

    def start_job(self, *, kind: str, experiment_id: str, version: str, total_units: int) -> JobStatus:
        if total_units <= 0:
            raise ValueError("total_units must be at least 1")
        with self._lock:
            job_id = f"{kind}-{next(_COUNTER):06d}"
            job = JobStatus(
                job_id=job_id,
                kind=kind,
                experiment_id=experiment_id,
                version=version,
                status="running",
                total_units=total_units,
            )
            self._jobs[job_id] = job
            self._events[job_id] = []
            self._append_event(job, "started")
            return job

    def get(self, job_id: str) -> JobStatus:
        with self._lock:
            return self._jobs[job_id]

    def events(self, job_id: str) -> list[JobEvent]:
        with self._lock:
            return list(self._events[job_id])

    def update(self, job_id: str, *, completed_units: int, message: str) -> JobStatus:
        with self._lock:
            old = self._jobs[job_id]
            if old.status in _TERMINAL_STATUSES:
                raise ValueError(f"Cannot update {old.status} job {job_id}")
            if completed_units < 0 or completed_units > old.total_units:
                raise ValueError(
                    f"completed_units must be between 0 and total_units ({old.total_units})"
                )
            job = replace(old, completed_units=completed_units, message=message)
            self._jobs[job_id] = job
            self._append_event(job, message)
            return job

    def complete(self, job_id: str, *, message: str) -> JobStatus:
        with self._lock:
            old = self._jobs[job_id]
            if old.status in _TERMINAL_STATUSES:
                raise ValueError(f"Cannot complete {old.status} job {job_id}")
            job = replace(
                old,
                status="completed",
                completed_units=old.total_units,
                message=message,
                finished_at=_now(),
            )
            self._jobs[job_id] = job
            self._append_event(job, message)
            return job

    def fail(self, job_id: str, *, message: str) -> JobStatus:
        with self._lock:
            old = self._jobs[job_id]
            if old.status in _TERMINAL_STATUSES:
                raise ValueError(f"Cannot fail {old.status} job {job_id}")
            job = replace(old, status="failed", message=message, finished_at=_now())
            self._jobs[job_id] = job
            self._append_event(job, message)
            return job

    def _append_event(self, job: JobStatus, message: str) -> None:
        events = self._events[job.job_id]
        events.append(
            JobEvent(
                event_id=len(events) + 1,
                job_id=job.job_id,
                status=job.status,
                message=message,
                completed_units=job.completed_units,
                total_units=job.total_units,
                created_at=_now(),
            )
        )
