"""The no-copy frame cache (PERF-6).

``st.cache_data`` hands every caller a private deep copy of its result. For the
corpus-scale frames that costs ~1.15 s and ~1.2 GB of churn on every rerun — on
data the app already has, and never writes to (see
``tests/test_frame_immutability.py``). ``frame_cache`` keeps the last result per
slot and hands back *the object itself*.

UX-166 added `_shared_build` (a rerun joins a build already in flight instead
of starting a second) and its fix round (T5-1) added "latest request wins": a
build that finishes only publishes into the shared cache while its key is
still the slot's most recently *requested* one, so a superseded build's late
finish can never clobber a newer result.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from scanpath_studio import data as data_module
from scanpath_studio.data import _shared_build, frame_cache


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


class TestSharedBuild:
    """UX-166: a rerun joins a build already in flight instead of starting one.

    Deterministic throughout (UX-166 fix-round-1, Minor #4): every test
    monkeypatches `data._InFlight` so the owner's build blocks on a `release`
    Event, and waits for `entry.done.waiting` — set only once a second caller
    has genuinely reached `entry.done.wait()` — before releasing it. A
    `_shared_build` that shares nothing fails these tests loudly: the
    `data_module._INFLIGHT[ident]` lookup right after `registered.wait()`
    raises `KeyError`, since a non-sharing implementation never registers
    anything there.
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

        def owner_call():
            results["owner"] = _shared_build(("s", 1), build)

        owner = threading.Thread(target=owner_call)
        owner.start()
        registered.wait()
        entry = data_module._INFLIGHT[("s", 1)]

        def waiter_call():
            results["waiter"] = _shared_build(("s", 1), _must_not_run)

        waiter = threading.Thread(target=waiter_call)
        waiter.start()
        assert entry.done.waiting.wait(timeout=5), "waiter never reached done.wait()"
        release.set()
        owner.join()
        waiter.join()

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

        def owner_call():
            try:
                _shared_build(("s", 2), cancelled)
            except progress.Cancelled as exc:
                errors.append(exc)

        owner = threading.Thread(target=owner_call)
        owner.start()
        registered.wait()
        entry = data_module._INFLIGHT[("s", 2)]

        results = {}

        def waiter_call():
            results["waiter"] = _shared_build(("s", 2), succeeding)

        waiter = threading.Thread(target=waiter_call)
        waiter.start()
        assert entry.done.waiting.wait(timeout=5), "waiter never reached done.wait()"
        release.set()
        owner.join()
        waiter.join()

        assert calls == ["owner", "waiter"]
        assert errors
        assert results["waiter"] == "ok"

    def test_an_ordinary_error_is_re_raised_in_the_waiter_not_rebuilt(
        self, monkeypatch
    ):
        """Minor #5: an ordinary `Exception` is not a cancellation — re-running
        the owner's build would just fail again the same way, so every waiter
        gets the SAME exception instead of rebuilding."""
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

        def owner_call():
            try:
                _shared_build(("s", 3), failing)
            except RuntimeError as exc:
                owner_errors.append(exc)

        owner = threading.Thread(target=owner_call)
        owner.start()
        registered.wait()
        entry = data_module._INFLIGHT[("s", 3)]

        waiter_errors = []

        def waiter_call():
            try:
                _shared_build(("s", 3), must_not_run)
            except RuntimeError as exc:
                waiter_errors.append(exc)

        waiter = threading.Thread(target=waiter_call)
        waiter.start()
        assert entry.done.waiting.wait(timeout=5), "waiter never reached done.wait()"
        release.set()
        owner.join()
        waiter.join()

        assert calls == ["owner"]
        assert owner_errors == [boom]
        assert waiter_errors == [boom]


class TestFrameCacheSharesInFlightBuilds:
    """Minor #8: `frame_cache` itself — not just `_shared_build` directly —
    shares one build in flight across two threads asking for the same slot
    and key, in the same bare-mode session store."""

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

        def owner_call():
            results["owner"] = frame_cache(slot, key, build)

        owner = threading.Thread(target=owner_call)
        owner.start()
        registered.wait()

        store = st.session_state.setdefault(data_module._FRAME_CACHE_KEY, {})
        entry = data_module._INFLIGHT[(id(store), slot, key)]

        def waiter_call():
            results["waiter"] = frame_cache(slot, key, _must_not_run)

        waiter = threading.Thread(target=waiter_call)
        waiter.start()
        assert entry.done.waiting.wait(timeout=5), "waiter never reached done.wait()"
        release.set()
        owner.join()
        waiter.join()

        assert len(calls) == 1
        assert results["owner"] is results["waiter"]


def test_a_stopped_sessions_build_still_lands_in_the_store(monkeypatch):
    """Minor #8, end to end with the debug_log fix: `timed()`'s log line runs
    *after* the build finishes, and used to let an abandoned run's
    StopException throw the just-finished result away before `frame_cache`
    could store it (UX-166's first bug)."""
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

        def request_a():
            results["a"] = frame_cache(slot, "K_A", build_a)

        t_a = threading.Thread(target=request_a)
        t_a.start()
        registered.wait()

        results["b"] = frame_cache(slot, "K_B", lambda: "value_b")
        assert results["b"] == "value_b"

        release.set()
        t_a.join()
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

        def request_a():
            results["a"] = frame_cache(slot, "K_A", build_a)

        t_a = threading.Thread(target=request_a)
        t_a.start()
        registered.wait()

        rebuilt = []
        hit = frame_cache(slot, "K_B", lambda: rebuilt.append(1) or "should not run")
        assert hit == "value_b"
        assert rebuilt == []

        release.set()
        t_a.join()
        assert results["a"] == "value_a"

        final = frame_cache(slot, "K_B", lambda: rebuilt.append(1) or "should not run")
        assert final == "value_b"
        assert rebuilt == []
