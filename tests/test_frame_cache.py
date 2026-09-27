"""The no-copy frame cache (PERF-6).

``st.cache_data`` hands every caller a private deep copy of its result. For the
corpus-scale frames that costs ~1.15 s and ~1.2 GB of churn on every rerun — on
data the app already has, and never writes to (see
``tests/test_frame_immutability.py``). ``frame_cache`` keeps the last result per
slot and hands back *the object itself*.

UX-166 added `_shared_build` (a rerun joins a build already in flight instead
of starting a second). Its fix rounds added "latest request wins" (T5-1): a
build that finishes only publishes into the shared cache while its key is
still the slot's most recently *requested* one, so a superseded build's late
finish can never clobber a newer result; and (T5-5, fix round 2) made the
owner branch exception-safe end to end — a raising `lookup`/`publish` must
never leak the in-flight registry entry or hang a waiter forever.
"""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass, field

import pandas as pd
import pytest
import streamlit as st

from scanpath_studio import data as data_module
from scanpath_studio import progress
from scanpath_studio.data import _shared_build, frame_cache

#: Every threaded test below is fully deterministic (Event-based, no sleeps)
#: and should finish in well under a second; this is a backstop only — a
#: regression that reintroduces a hang fails the test instead of the whole
#: suite (UX-166 fix-round-2, Minor #2 of Ruling T5-5).
_THREAD_TEST_TIMEOUT = 30


def _frame(n=3):
    return pd.DataFrame({"a": range(n)})


def _must_not_run():
    raise AssertionError("must not build — a waiter should not rebuild here")


class _FlagWaitEvent(threading.Event):
    """A `threading.Event` that flags when a caller is actually blocked in
    `wait()` — deterministic tests need to know a waiter has genuinely reached
    `entry.done.wait()` before releasing the owner, rather than guessing with
    a sleep (UX-166 fix-round-1, Minor #4)."""

    def __init__(self):
        super().__init__()
        self.waiting = threading.Event()

    def wait(self, timeout=None):
        self.waiting.set()
        return super().wait(timeout)


@dataclass
class _FlagWaitInFlight:
    """A drop-in `data._InFlight` whose `done` is a `_FlagWaitEvent`."""

    done: _FlagWaitEvent = field(default_factory=_FlagWaitEvent)
    value: object = None
    ok: bool = False
    error: Exception | None = None


def _run_daemon(target) -> threading.Thread:
    """Start `target` as a **daemon** thread (UX-166 fix-round-2, Minor #2):
    a regression that leaves it parked forever must not also block pytest —
    or the whole process — from exiting. Every caller still joins it with a
    bounded timeout and asserts it actually finished; the daemon flag is the
    second line of defense, not the only one."""
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def _join_or_fail(thread: threading.Thread, *, timeout: float = 5) -> None:
    thread.join(timeout=timeout)
    assert not thread.is_alive(), "thread did not finish within the timeout"


def _wait_or_fail(event: threading.Event, *, timeout: float = 5, msg: str) -> None:
    assert event.wait(timeout=timeout), msg


@contextlib.contextmanager
def _released_afterward(release: threading.Event):
    """`release.set()` always runs on the way out (UX-166 fix-round-2,
    Minor #2): an owner thread parked on `release.wait()` must never be left
    hanging just because an assertion inside the block failed first."""
    try:
        yield
    finally:
        release.set()


class TestFrameCache:
    def test_a_repeat_call_returns_the_very_same_object(self):
        built = _frame()
        first = frame_cache("t_same", "k", lambda: built)
        second = frame_cache("t_same", "k", lambda: _frame(99))
        assert first is second is built

    def test_it_does_not_rebuild_when_the_key_is_unchanged(self):
        calls = []

        def build():
            calls.append(1)
            return _frame()

        frame_cache("t_build", "k", build)
        frame_cache("t_build", "k", build)
        assert len(calls) == 1

    def test_a_new_key_rebuilds(self):
        first = frame_cache("t_key", "k1", _frame)
        second = frame_cache("t_key", "k2", _frame)
        assert first is not second

    def test_it_keeps_only_the_latest_entry(self):
        """Holding the previous corpus beside the current one would cost more
        memory than the copy it replaces."""
        first = frame_cache("t_evict", "k1", _frame)
        frame_cache("t_evict", "k2", _frame)
        assert frame_cache("t_evict", "k1", _frame) is not first

    def test_slots_are_independent(self):
        a = frame_cache("t_a", "k", _frame)
        frame_cache("t_b", "k", _frame)
        assert frame_cache("t_a", "k", _frame) is a

    def test_it_still_works_with_no_session_state(self, monkeypatch):
        """The API and CLI import this module outside a Streamlit runtime."""
        import scanpath_studio.data as data_module

        class _NoState:
            @property
            def session_state(self):
                raise RuntimeError("no runtime")

        monkeypatch.setattr(data_module, "st", _NoState())
        built = _frame()
        assert frame_cache("t_bare", "k", lambda: built) is built


class TestClearFrameCache:
    """`clear_computation_cache` must reach it, or a deleted dataset's frames
    outlive the delete — the thing that function exists to prevent."""

    def test_clearing_drops_every_slot(self):
        from scanpath_studio.data import clear_frame_cache

        first = frame_cache("t_clear_a", "k", _frame)
        frame_cache("t_clear_b", "k", _frame)
        clear_frame_cache()
        assert frame_cache("t_clear_a", "k", _frame) is not first

    def test_clearing_is_safe_with_no_session_state(self, monkeypatch):
        import scanpath_studio.data as data_module
        from scanpath_studio.data import clear_frame_cache

        class _NoState:
            @property
            def session_state(self):
                raise RuntimeError("no runtime")

        monkeypatch.setattr(data_module, "st", _NoState())
        clear_frame_cache()  # must not raise


class TestFingerprintsOutliveTheRun:
    """PERF-10: a frame `frame_cache` hands back as the same object run after
    run cannot change, so its fingerprint must not be recomputed every run —
    the per-run memo reset used to force a full re-hash of the normalized pair
    on every rerun (~0.5 s of a 1.9 s rerun at 50× the demo)."""

    def _counting(self, monkeypatch):
        from scanpath_studio import data

        calls = []
        real = data._compute_frame_fingerprint
        monkeypatch.setattr(
            data,
            "_compute_frame_fingerprint",
            lambda df: calls.append(1) or real(df),
        )
        return data, calls

    def test_a_cached_frame_is_hashed_once_across_runs(self, monkeypatch):
        data, calls = self._counting(monkeypatch)
        pair = frame_cache("t_fp_stable", "k", lambda: (_frame(5), _frame(7)))
        seen = set()
        for _ in range(3):
            data.reset_fingerprint_memo()
            seen.add(tuple(data.frame_fingerprint(f) for f in pair))
        assert len(calls) == 2
        assert len(seen) == 1

    def test_any_other_frame_is_still_hashed_every_run(self, monkeypatch):
        data, calls = self._counting(monkeypatch)
        frame = _frame(5)
        for _ in range(3):
            data.reset_fingerprint_memo()
            data.frame_fingerprint(frame)
        assert len(calls) == 3


@pytest.mark.timeout(_THREAD_TEST_TIMEOUT)
class TestSharedBuild:
    """UX-166: a rerun joins a build already in flight instead of starting one.

    Deterministic throughout (UX-166 fix-round-1, Minor #4): every test
    monkeypatches `data._InFlight` so the owner's build blocks on a `release`
    Event, and waits for `entry.done.waiting` — set only once a second caller
    has genuinely reached `entry.done.wait()` — before releasing it. A
    `_shared_build` that shares nothing fails these tests loudly: the
    `data_module._INFLIGHT[ident]` lookup right after `registered.wait()`
    raises `KeyError`, since a non-sharing implementation never registers
    anything there. Every wait/join is bounded and asserted, `release` always
    fires (even if an earlier assertion in the block failed), and threads are
    daemons — a regression that reintroduces a hang fails fast instead of
    parking the test suite (fix-round-2, Minor #2).
    """

    def test_two_callers_share_one_build(self, monkeypatch):
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        registered = threading.Event()
        release = threading.Event()
        calls = []

        def build():
            calls.append(1)
            registered.set()
            release.wait()
            return object()

        results = {}
        owner = _run_daemon(
            lambda: results.__setitem__("owner", _shared_build(("s", 1), build))
        )
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")
            entry = data_module._INFLIGHT[("s", 1)]

            waiter = _run_daemon(
                lambda: results.__setitem__(
                    "waiter", _shared_build(("s", 1), _must_not_run)
                )
            )
            _wait_or_fail(entry.done.waiting, msg="waiter never reached done.wait()")
        _join_or_fail(owner)
        _join_or_fail(waiter)

        assert len(calls) == 1
        assert results["owner"] is results["waiter"]

    def test_a_cancelled_owner_leaves_the_waiter_to_build_it_itself(self, monkeypatch):
        """A `BaseException` that is *not* an `Exception` (`progress.Cancelled`,
        Streamlit's `StopException`) means nobody actually finished the build:
        a waiter must build it itself. Contrast with the ordinary-exception
        test below, where it must not."""
        from scanpath_studio import progress

        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        registered = threading.Event()
        release = threading.Event()
        calls = []

        def cancelled():
            calls.append("owner")
            registered.set()
            release.wait()
            raise progress.Cancelled("stop")

        def succeeding():
            calls.append("waiter")
            return "ok"

        errors = []
        results = {}

        def owner_call():
            try:
                _shared_build(("s", 2), cancelled)
            except progress.Cancelled as exc:
                errors.append(exc)

        owner = _run_daemon(owner_call)
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")
            entry = data_module._INFLIGHT[("s", 2)]

            waiter = _run_daemon(
                lambda: results.__setitem__(
                    "waiter", _shared_build(("s", 2), succeeding)
                )
            )
            _wait_or_fail(entry.done.waiting, msg="waiter never reached done.wait()")
        _join_or_fail(owner)
        _join_or_fail(waiter)

        assert calls == ["owner", "waiter"]
        assert errors
        assert results["waiter"] == "ok"

    def test_an_ordinary_error_is_re_raised_in_the_waiter_not_rebuilt(
        self, monkeypatch
    ):
        """Minor #5 (fix-round-1): an ordinary `Exception` is not a
        cancellation — re-running the owner's build would just fail again the
        same way, so every waiter gets the SAME exception instead of
        rebuilding."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        registered = threading.Event()
        release = threading.Event()
        calls = []
        boom = RuntimeError("boom")

        def failing():
            calls.append("owner")
            registered.set()
            release.wait()
            raise boom

        def must_not_run():
            calls.append("waiter")
            raise AssertionError("the waiter must not rebuild")

        owner_errors = []
        waiter_errors = []

        def owner_call():
            try:
                _shared_build(("s", 3), failing)
            except RuntimeError as exc:
                owner_errors.append(exc)

        def waiter_call():
            try:
                _shared_build(("s", 3), must_not_run)
            except RuntimeError as exc:
                waiter_errors.append(exc)

        owner = _run_daemon(owner_call)
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")
            entry = data_module._INFLIGHT[("s", 3)]

            waiter = _run_daemon(waiter_call)
            _wait_or_fail(entry.done.waiting, msg="waiter never reached done.wait()")
        _join_or_fail(owner)
        _join_or_fail(waiter)

        assert calls == ["owner"]
        assert owner_errors == [boom]
        assert waiter_errors == [boom]

    def test_a_waiter_gets_its_own_publish_opportunity(self, monkeypatch):
        """Minor #1 of Ruling T5-5 (fix-round-2): the owner's own `publish`
        decides against whatever key was latest *at its own decision time* —
        a joined waiter's request can itself be the latest again by the time
        it wakes, so it gets an independent, guarded shot at publishing too.
        Proven here by giving the owner and the waiter two DIFFERENT publish
        callbacks and asserting both actually ran with the shared value."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        ident = ("s", "waiter-publish")
        registered = threading.Event()
        release = threading.Event()
        owner_publish_calls = []
        waiter_publish_calls = []

        def build():
            registered.set()
            release.wait()
            return "value"

        results = {}

        def owner_call():
            results["owner"] = _shared_build(
                ident, build, publish=owner_publish_calls.append
            )

        def waiter_call():
            results["waiter"] = _shared_build(
                ident, _must_not_run, publish=waiter_publish_calls.append
            )

        owner = _run_daemon(owner_call)
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")
            entry = data_module._INFLIGHT[ident]

            waiter = _run_daemon(waiter_call)
            _wait_or_fail(entry.done.waiting, msg="waiter never reached done.wait()")
        _join_or_fail(owner)
        _join_or_fail(waiter)

        assert results["owner"] == results["waiter"] == "value"
        assert owner_publish_calls == ["value"]
        assert waiter_publish_calls == ["value"]

    def test_a_raising_publish_does_not_leak_the_entry_or_hang_a_waiter(
        self, monkeypatch
    ):
        """Ruling T5-5 (fix-round-2): a24e105's try/finally always popped the
        entry and signalled `done`; the "latest request wins" fix (T5-1) lost
        that by writing the cleanup out per path, so a raising `publish`
        (reproduced by the reviewer via `_vouch_for_frames` racing another
        session's concurrent insert) leaked the `_INFLIGHT` entry and hung
        every waiter — already joined or not — forever."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        ident = ("s", "raising-publish")
        registered = threading.Event()
        release = threading.Event()

        def raising_publish(value):
            raise RuntimeError("dictionary changed size during iteration")

        def build():
            registered.set()
            release.wait()
            return "value"

        results = {}

        def owner_call():
            results["owner"] = _shared_build(ident, build, publish=raising_publish)

        def waiter_call():
            results["waiter"] = _shared_build(
                ident, _must_not_run, publish=raising_publish
            )

        owner = _run_daemon(owner_call)
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")
            entry = data_module._INFLIGHT[ident]

            waiter = _run_daemon(waiter_call)
            _wait_or_fail(entry.done.waiting, msg="waiter never reached done.wait()")
        _join_or_fail(owner)
        _join_or_fail(waiter)  # must not hang despite `publish` always raising

        assert results["owner"] == "value"
        assert results["waiter"] == "value"
        assert ident not in data_module._INFLIGHT

    def test_a_raising_lookup_still_builds_and_cleans_up(self, monkeypatch):
        """Ruling T5-5 (fix-round-2): a raising `lookup` is treated as a miss
        — logged, then built normally — never left to skip the cleanup."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        ident = ("s", "raising-lookup")
        calls = []

        def raising_lookup():
            raise RuntimeError("boom")

        def build():
            calls.append(1)
            return "value"

        result = _shared_build(ident, build, lookup=raising_lookup)

        assert result == "value"
        assert calls == [1]
        assert ident not in data_module._INFLIGHT

    def test_waiting_on_a_build_in_flight_counts_as_work(self, monkeypatch):
        """UX-166: a rerun that lands on another run's build waits for it, and
        the owner's reports go to the owner's task — so the waiter reports once
        itself, or a gated card over the wait (the Corpus measures) never shows."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        ident = ("s", "waiting-is-work")
        registered, release = threading.Event(), threading.Event()
        waiting_task = progress.Task(("t", "waiter"), title="Computing")

        def build():
            registered.set()
            release.wait()
            return "measures"

        def waiter_call():
            token = progress.activate(waiting_task)
            try:
                _shared_build(ident, _must_not_run)
            finally:
                progress.deactivate(token)

        owner = _run_daemon(lambda: _shared_build(ident, build))
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")
            entry = data_module._INFLIGHT[ident]
            waiter = _run_daemon(waiter_call)
            _wait_or_fail(entry.done.waiting, msg="waiter never reached done.wait()")
            worked_while_waiting = waiting_task.worked
        _join_or_fail(owner)
        _join_or_fail(waiter)
        assert worked_while_waiting is True

    def test_a_cancelled_waiter_stops_before_it_waits(self, monkeypatch):
        """The waiter's report is a cancel checkpoint too: a waiter whose own task
        was cancelled stops at once instead of waiting out a build it no longer
        wants."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        ident = ("s", "cancelled-waiter")
        registered, release = threading.Event(), threading.Event()
        cancelled_task = progress.Task(("t", "cancelled-waiter"), title="Computing")
        cancelled_task.cancel()
        raised = []

        def build():
            registered.set()
            release.wait()
            return "measures"

        def waiter_call():
            token = progress.activate(cancelled_task)
            try:
                _shared_build(ident, _must_not_run)
            except progress.Cancelled as exc:
                raised.append(exc)
            finally:
                progress.deactivate(token)

        owner = _run_daemon(lambda: _shared_build(ident, build))
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")
            entry = data_module._INFLIGHT[ident]
            waiter = _run_daemon(waiter_call)
            # Joined while the owner is still building: it did not wait for it.
            waiter.join(timeout=2)
            finished_first = not waiter.is_alive()
            waited = entry.done.waiting.is_set()
        _join_or_fail(owner)
        _join_or_fail(waiter)
        assert finished_first and not waited
        assert raised

    def test_a_waiter_on_the_owners_own_task_leaves_its_count(self, monkeypatch):
        """A rerun that joined the load's task (the dataset card's explicit key)
        and then waits on that load's build reports into the very task the
        owner is counting in — which must not wipe the owner's live count."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        ident = ("s", "joined-waiter")
        registered, release = threading.Event(), threading.Event()
        shared = progress.Task(("t", "joined-waiter"), title="Normalizing")

        def build():
            progress.report(1, 3, detail="fixations")
            registered.set()
            release.wait()
            return "normalized"

        def under_the_shared_task(call):
            def run():
                token = progress.activate(shared)
                try:
                    call()
                finally:
                    progress.deactivate(token)

            return run

        owner = _run_daemon(under_the_shared_task(lambda: _shared_build(ident, build)))
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")
            entry = data_module._INFLIGHT[ident]
            waiter = _run_daemon(
                under_the_shared_task(lambda: _shared_build(ident, _must_not_run))
            )
            _wait_or_fail(entry.done.waiting, msg="waiter never reached done.wait()")
            snap = shared.snapshot()
        _join_or_fail(owner)
        _join_or_fail(waiter)
        assert (snap.done, snap.total, snap.detail) == (1, 3, "fixations")


@pytest.mark.timeout(_THREAD_TEST_TIMEOUT)
class TestFrameCacheSharesInFlightBuilds:
    """Minor #8 (fix-round-1): `frame_cache` itself — not just `_shared_build`
    directly — shares one build in flight across two threads asking for the
    same slot and key, in the same bare-mode session store."""

    def test_two_threads_share_one_build(self, monkeypatch):
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        slot, key = "t_wiring_share", "k"
        registered = threading.Event()
        release = threading.Event()
        calls = []

        def build():
            calls.append(1)
            registered.set()
            release.wait()
            return _frame()

        results = {}
        owner = _run_daemon(
            lambda: results.__setitem__("owner", frame_cache(slot, key, build))
        )
        with _released_afterward(release):
            _wait_or_fail(registered, msg="owner never started building")

            store = st.session_state.setdefault(data_module._FRAME_CACHE_KEY, {})
            entry = data_module._INFLIGHT[(id(store), slot, key)]

            waiter = _run_daemon(
                lambda: results.__setitem__(
                    "waiter", frame_cache(slot, key, _must_not_run)
                )
            )
            _wait_or_fail(entry.done.waiting, msg="waiter never reached done.wait()")
        _join_or_fail(owner)
        _join_or_fail(waiter)

        assert len(calls) == 1
        assert results["owner"] is results["waiter"]


def test_a_stopped_sessions_build_still_lands_in_the_store(monkeypatch):
    """Minor #8 (fix-round-1), end to end with the debug_log fix: `timed()`'s
    log line runs *after* the build finishes, and used to let an abandoned
    run's StopException throw the just-finished result away before
    `frame_cache` could store it (UX-166's first bug)."""
    from streamlit.runtime.scriptrunner import StopException

    from scanpath_studio import debug_log

    debug_log.install_log_capture()

    def _stopped():
        raise StopException()

    monkeypatch.setattr(debug_log, "_buffer", _stopped)
    slot, key = "t_stopped_session", "k"
    built = _frame()

    def build():
        with debug_log.timed("build"):
            pass
        return built

    result = frame_cache(slot, key, build)
    assert result is built
    store = st.session_state[data_module._FRAME_CACHE_KEY]
    assert store.get(slot) == (key, built)


@pytest.mark.timeout(_THREAD_TEST_TIMEOUT)
class TestLatestRequestWins:
    """UX-166 fix-round-1 (T5-1): a build a newer request already superseded
    must not clobber that newer result when it finally finishes — its own
    caller still gets its value, but the shared store does not."""

    def test_a_slow_earlier_build_does_not_clobber_a_newer_one(self, monkeypatch):
        """K_A is slow and in flight; K_B is requested (a fresh, independent
        build — a different ident) and answered while A is still running;
        A's late finish must not overwrite K_B's entry."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        slot = "t_latest_a"
        registered = threading.Event()
        release = threading.Event()
        calls = []

        def build_a():
            calls.append("a")
            registered.set()
            release.wait()
            return "value_a"

        results = {}
        t_a = _run_daemon(
            lambda: results.__setitem__("a", frame_cache(slot, "K_A", build_a))
        )
        with _released_afterward(release):
            _wait_or_fail(registered, msg="A never started building")

            results["b"] = frame_cache(slot, "K_B", lambda: "value_b")
            assert results["b"] == "value_b"
        _join_or_fail(t_a)
        assert results["a"] == "value_a"  # still returned to A's own caller

        rebuilt = []
        hit = frame_cache(slot, "K_B", lambda: rebuilt.append(1) or "value_b_2")
        assert hit == "value_b"
        assert rebuilt == []  # a hit — the store still holds K_B, not K_A

    def test_a_hit_refreshes_the_latest_request_marker(self, monkeypatch):
        """K_B is already the stored entry; K_A starts a slow, independent
        build; K_B is requested again while A is in flight (a HIT, but it
        must still refresh "latest request") — A's later finish must still
        be dropped."""
        monkeypatch.setattr(data_module, "_InFlight", _FlagWaitInFlight)
        slot = "t_latest_b"

        frame_cache(slot, "K_B", lambda: "value_b")

        registered = threading.Event()
        release = threading.Event()
        calls = []

        def build_a():
            calls.append("a")
            registered.set()
            release.wait()
            return "value_a"

        results = {}
        rebuilt = []
        t_a = _run_daemon(
            lambda: results.__setitem__("a", frame_cache(slot, "K_A", build_a))
        )
        with _released_afterward(release):
            _wait_or_fail(registered, msg="A never started building")

            hit = frame_cache(
                slot, "K_B", lambda: rebuilt.append(1) or "should not run"
            )
            assert hit == "value_b"
            assert rebuilt == []
        _join_or_fail(t_a)
        assert results["a"] == "value_a"

        final = frame_cache(slot, "K_B", lambda: rebuilt.append(1) or "should not run")
        assert final == "value_b"
        assert rebuilt == []
