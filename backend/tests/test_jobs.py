from __future__ import annotations

from prompt_lab.jobs import JobManager


def assert_raises(expected_error: type[Exception], func: object) -> Exception:
    if not callable(func):
        raise AssertionError("assert_raises requires a callable")
    try:
        func()
    except expected_error as error:
        return error
    raise AssertionError(f"Expected {expected_error.__name__}")


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


def test_job_manager_records_initial_started_event() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="run_version", experiment_id="demo", version="v001", total_units=3)

    events = jobs.events(job.job_id)

    assert len(events) == 1
    assert events[0].event_id == 1
    assert events[0].job_id == job.job_id
    assert events[0].status == "running"
    assert events[0].message == "started"
    assert events[0].completed_units == 0
    assert events[0].total_units == 3
    assert job.finished_at is None


def test_job_manager_events_are_ordered_snapshots() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="run_version", experiment_id="demo", version="v001", total_units=2)
    jobs.update(job.job_id, completed_units=1, message="case a repeat 1")

    events = jobs.events(job.job_id)
    events.clear()
    loaded_events = jobs.events(job.job_id)

    assert [event.event_id for event in loaded_events] == [1, 2]
    assert [event.message for event in loaded_events] == ["started", "case a repeat 1"]


def test_job_manager_rejects_invalid_total_units() -> None:
    jobs = JobManager()

    assert_raises(
        ValueError,
        lambda: jobs.start_job(kind="run_version", experiment_id="demo", version="v001", total_units=0),
    )
    assert_raises(
        ValueError,
        lambda: jobs.start_job(kind="run_version", experiment_id="demo", version="v001", total_units=-1),
    )


def test_job_manager_rejects_completed_units_out_of_bounds() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="run_version", experiment_id="demo", version="v001", total_units=2)

    negative_error = assert_raises(
        ValueError,
        lambda: jobs.update(job.job_id, completed_units=-1, message="bad negative"),
    )
    too_high_error = assert_raises(
        ValueError,
        lambda: jobs.update(job.job_id, completed_units=3, message="bad high"),
    )

    assert "completed_units" in str(negative_error)
    assert "completed_units" in str(too_high_error)
    assert jobs.get(job.job_id).completed_units == 0
    assert [event.message for event in jobs.events(job.job_id)] == ["started"]


def test_job_manager_rejects_updates_after_completed() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="run_version", experiment_id="demo", version="v001", total_units=1)
    jobs.complete(job.job_id, message="done")

    error = assert_raises(
        ValueError,
        lambda: jobs.update(job.job_id, completed_units=1, message="late update"),
    )

    assert "completed" in str(error)
    assert jobs.get(job.job_id).status == "completed"
    assert [event.message for event in jobs.events(job.job_id)] == ["started", "done"]


def test_job_manager_fails_job_with_terminal_event() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=2)

    failed = jobs.fail(job.job_id, message="validation failed")
    terminal_event = jobs.events(job.job_id)[-1]

    assert failed.status == "failed"
    assert failed.message == "validation failed"
    assert failed.finished_at is not None
    assert terminal_event.event_id == 2
    assert terminal_event.status == "failed"
    assert terminal_event.message == "validation failed"
    assert terminal_event.completed_units == 0
    assert terminal_event.total_units == 2


def test_job_manager_rejects_updates_after_failed() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=1)
    jobs.fail(job.job_id, message="failed")

    error = assert_raises(
        ValueError,
        lambda: jobs.update(job.job_id, completed_units=1, message="late update"),
    )

    assert "failed" in str(error)
    assert jobs.get(job.job_id).status == "failed"
    assert [event.message for event in jobs.events(job.job_id)] == ["started", "failed"]


def test_job_manager_completed_event_has_terminal_fields() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=1)

    completed = jobs.complete(job.job_id, message="done")
    terminal_event = jobs.events(job.job_id)[-1]

    assert completed.finished_at is not None
    assert terminal_event.event_id == 2
    assert terminal_event.status == "completed"
    assert terminal_event.message == "done"
    assert terminal_event.completed_units == 1
    assert terminal_event.total_units == 1


def test_job_manager_rejects_fail_after_completed_without_appending_event() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=1)
    jobs.complete(job.job_id, message="done")
    event_count = len(jobs.events(job.job_id))

    error = assert_raises(
        ValueError,
        lambda: jobs.fail(job.job_id, message="late failure"),
    )

    assert "completed" in str(error)
    assert jobs.get(job.job_id).status == "completed"
    assert len(jobs.events(job.job_id)) == event_count
    assert [event.message for event in jobs.events(job.job_id)] == ["started", "done"]


def test_job_manager_rejects_complete_after_failed_without_appending_event() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=1)
    jobs.fail(job.job_id, message="failed")
    event_count = len(jobs.events(job.job_id))

    error = assert_raises(
        ValueError,
        lambda: jobs.complete(job.job_id, message="late done"),
    )

    assert "failed" in str(error)
    assert jobs.get(job.job_id).status == "failed"
    assert len(jobs.events(job.job_id)) == event_count
    assert [event.message for event in jobs.events(job.job_id)] == ["started", "failed"]


def test_job_manager_rejects_duplicate_complete_without_appending_event() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=1)
    jobs.complete(job.job_id, message="done")
    event_count = len(jobs.events(job.job_id))

    error = assert_raises(
        ValueError,
        lambda: jobs.complete(job.job_id, message="done again"),
    )

    assert "completed" in str(error)
    assert jobs.get(job.job_id).status == "completed"
    assert len(jobs.events(job.job_id)) == event_count
    assert [event.message for event in jobs.events(job.job_id)] == ["started", "done"]


def test_job_manager_rejects_duplicate_fail_without_appending_event() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=1)
    jobs.fail(job.job_id, message="failed")
    event_count = len(jobs.events(job.job_id))

    error = assert_raises(
        ValueError,
        lambda: jobs.fail(job.job_id, message="failed again"),
    )

    assert "failed" in str(error)
    assert jobs.get(job.job_id).status == "failed"
    assert len(jobs.events(job.job_id)) == event_count
    assert [event.message for event in jobs.events(job.job_id)] == ["started", "failed"]


def main() -> int:
    tests = [
        test_job_manager_records_progress_events,
        test_job_manager_completes_job,
        test_job_manager_records_initial_started_event,
        test_job_manager_events_are_ordered_snapshots,
        test_job_manager_rejects_invalid_total_units,
        test_job_manager_rejects_completed_units_out_of_bounds,
        test_job_manager_rejects_updates_after_completed,
        test_job_manager_fails_job_with_terminal_event,
        test_job_manager_rejects_updates_after_failed,
        test_job_manager_completed_event_has_terminal_fields,
        test_job_manager_rejects_fail_after_completed_without_appending_event,
        test_job_manager_rejects_complete_after_failed_without_appending_event,
        test_job_manager_rejects_duplicate_complete_without_appending_event,
        test_job_manager_rejects_duplicate_fail_without_appending_event,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
