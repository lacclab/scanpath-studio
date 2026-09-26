"""UX-165: the Streamlit-free progress hook (`scanpath_studio.progress`)."""

from __future__ import annotations

import threading

import pytest

from scanpath_studio import progress


def test_calls_without_an_active_task_do_nothing():
    progress.report(3, 10, unit="files")
    progress.step_to(1)
    assert progress.active() is None


def test_a_task_records_counts_and_moves_through_its_steps():
    with progress.task(("t", "steps"), title="Loading", steps=("Read", "Norm")) as task:
        progress.report(3, 10, unit="files")
        snap = task.snapshot()
        assert (snap.current, snap.done, snap.total, snap.unit) == (0, 3, 10, "files")
        progress.step_to(1, "Normalizing 5 rows")
        snap = task.snapshot()
        assert snap.current == 1
        assert snap.steps == ("Read", "Normalizing 5 rows")
        assert snap.done is None and snap.unit == ""
        assert snap.step_seconds[0] is not None and snap.step_seconds[1] is None


def test_step_to_never_moves_back():
    with progress.task(("t", "back"), title="x", steps=("a", "b", "c")) as task:
        progress.step_to(2)
        progress.step_to(1)
        assert task.snapshot().current == 2


def test_cancel_makes_the_next_checkpoint_raise():
    with progress.task(("t", "cancel"), title="x"):
        progress.cancel(("t", "cancel"))
        with pytest.raises(progress.Cancelled):
            progress.report(1, 2)
        with pytest.raises(progress.Cancelled):
            progress.step_to(1)


def test_cancelled_is_not_an_exception_so_broad_handlers_cannot_swallow_it():
    assert not issubclass(progress.Cancelled, Exception)
    assert issubclass(progress.Cancelled, BaseException)


def test_begin_joins_a_running_task_but_not_a_finished_or_cancelled_one():
    first = progress.begin(("t", "join"), title="x")
    assert progress.begin(("t", "join"), title="x") is first
    first.finish()
    second = progress.begin(("t", "join"), title="x")
    assert second is not first
    second.cancel()
    assert progress.begin(("t", "join"), title="x") is not second


def test_finish_records_the_duration_under_its_duration_key():
    task = progress.begin(("t", "dur"), title="x")
    seconds = task.finish(duration_key=("dataset", "Demo"))
    assert progress.last_duration(("dataset", "Demo")) == pytest.approx(seconds)
    assert task.snapshot().finished


def test_the_active_task_belongs_to_its_own_thread():
    seen = []
    with progress.task(("t", "thread"), title="x"):
        worker = threading.Thread(target=lambda: seen.append(progress.active()))
        worker.start()
        worker.join()
    assert seen == [None]


def test_snapshots_stay_consistent_while_another_thread_reports():
    task = progress.begin(("t", "race"), title="x")
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            i += 1
            task.report(i, i + 5)

    worker = threading.Thread(target=writer)
    worker.start()
    try:
        for _ in range(2000):
            snap = task.snapshot()
            assert snap.done is None or snap.done <= snap.total
    finally:
        stop.set()
        worker.join()


def test_scope_clears_a_task_left_active_by_an_earlier_run():
    token = progress.activate(progress.begin(("t", "stale"), title="x"))
    try:
        with progress.scope():
            assert progress.active() is None
    finally:
        progress.deactivate(token)
