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
