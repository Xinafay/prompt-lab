from __future__ import annotations

from prompt_lab.jobs import JobManager


def test_job_manager_records_progress_events() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="run_version", experiment_id="demo", version="v001", total_units=2)

    jobs.update(job.job_id, completed_units=1, message="case a repeat 1")
    loaded = jobs.get(job.job_id)
    events = jobs.events(job.job_id)

    assert loaded.completed_units == 1
    assert events[-1].message == "case a repeat 1"


def test_job_manager_completes_job() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=1)

    jobs.complete(job.job_id, message="done")

    assert jobs.get(job.job_id).status == "completed"


def main() -> int:
    tests = [
        test_job_manager_records_progress_events,
        test_job_manager_completes_job,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
