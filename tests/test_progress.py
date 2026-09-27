"""UX-165: the Streamlit-free progress hook (`scanpath_studio.progress`)."""

from __future__ import annotations

import threading

import pytest

from scanpath_studio import api, progress
from scanpath_studio.synthetic import load_synthetic_data


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


def test_a_report_marks_its_task_as_having_worked_but_a_step_does_not():
    """UX-166: a gated card shows only once its task has done real work — a
    cache miss, which each build under one reports, if only with a bare
    ``report()``. Moving between steps is the orchestrator's bookkeeping, done
    on a cache hit just the same, so it counts for nothing."""
    with progress.task(("t", "worked"), title="Loading", steps=("a", "b")) as task:
        assert task.worked is False
        progress.step_to(1)
        assert task.worked is False
        progress.report()
        assert task.worked is True


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


def test_begin_fresh_replaces_any_existing_record_even_mid_flight():
    first = progress.begin(("t", "fresh"), title="x")
    second = progress.begin(("t", "fresh"), title="x", fresh=True)
    assert second is not first
    assert not first.finished and not first.cancelled  # replaced, not touched
    assert progress.begin(("t", "fresh"), title="x") is second


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


class _FakeTime:
    """A clock the test moves by hand, and a sleep that only records."""

    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


@pytest.fixture
def fake_time(monkeypatch):
    fake = _FakeTime()
    monkeypatch.setattr(progress, "_clock", fake.clock)
    monkeypatch.setattr(progress, "_sleep", fake.sleep)
    return fake


def test_reporting_hands_the_gil_over_at_most_every_yield_interval(fake_time):
    """A CPU-bound build on the script thread starves the server's event loop,
    so nothing a run sends reaches the browser until the build ends — a card's
    own reveal included. A report inside a task therefore sleeps briefly, but
    only once per ``YIELD_EVERY_S``; the first one yields at once, draining
    what the run queued before its slow work began."""
    step = progress.YIELD_EVERY_S
    with progress.task(("t", "yield"), title="Building"):
        progress.report(0, 10)  # first: yields at once
        fake_time.now += step * 0.4
        progress.report(1, 10)  # too soon
        fake_time.now += step * 0.4
        progress.report(2, 10)  # still too soon (0.8 of the interval)
        fake_time.now += step * 0.4
        progress.report(3, 10)  # 1.2 intervals since the last yield
        fake_time.now += step * 3
        progress.step_to(1)  # a step change is a checkpoint too
    assert fake_time.sleeps == [progress.YIELD_S] * 3


def test_no_yield_without_an_active_task(fake_time):
    progress.report(1, 2)
    progress.step_to(1)
    assert fake_time.sleeps == []


def test_a_cancelled_task_raises_before_it_yields(fake_time):
    with progress.task(("t", "yield-cancel"), title="Building") as task:
        task.cancel()
        with pytest.raises(progress.Cancelled):
            progress.report(0, 10)
    assert fake_time.sleeps == []


def test_building_a_replay_reports_every_frame():
    words, fixations = api.load_scanpath_data(*load_synthetic_data())
    pid = str(fixations["participant_id"].iloc[0])
    trial = str(fixations["trial_id"].iloc[0])
    with progress.task(("t", "replay"), title="x", steps=("Building frames",)) as task:
        fig = api.animate_scanpath(words, fixations, pid, trial)
    snap = task.snapshot()
    assert snap.unit == "frames"
    assert snap.done == snap.total == len(fig.frames)


def test_two_threads_reporting_to_one_task_share_one_yield(monkeypatch):
    """A joined task is reported to from two threads. The slot is claimed under
    the task's lock *before* the sleep, so while one thread sleeps the other
    sees the window taken — one yield per window, not one per thread."""
    sleeps: list[float] = []
    in_sleep = threading.Event()
    release = threading.Event()

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 1:  # hold the first sleeper mid-yield
            in_sleep.set()
            release.wait(timeout=5)

    monkeypatch.setattr(progress, "_clock", lambda: 100.0)
    monkeypatch.setattr(progress, "_sleep", sleep)
    task = progress.Task(("t", "joined"), title="Building")
    first = threading.Thread(target=task.report, args=(0, 10), daemon=True)
    first.start()
    try:
        assert in_sleep.wait(timeout=5)
        task.report(1, 10)  # the second thread, mid-way through the first's yield
    finally:
        release.set()
        first.join(timeout=5)
    assert not first.is_alive()
    assert sleeps == [progress.YIELD_S]
