"""The no-copy frame cache (PERF-6).

``st.cache_data`` hands every caller a private deep copy of its result. For the
corpus-scale frames that costs ~1.15 s and ~1.2 GB of churn on every rerun — on
data the app already has, and never writes to (see
``tests/test_frame_immutability.py``). ``frame_cache`` keeps the last result per
slot and hands back *the object itself*.
"""

from __future__ import annotations

import pandas as pd

from scanpath_studio.data import frame_cache


def _frame(n=3):
    return pd.DataFrame({"a": range(n)})


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
