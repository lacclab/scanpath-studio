"""The fixation-index window is per-trial unless *Apply to all trials* is on.

A window like "fixations 5-20" rarely means the same thing on a different
reading, so switching trials clears it by default. The checkbox
(``single_fix_range_all_trials``) opts into the old sticky behaviour, where the
window is re-applied to every trial and clamped to its length.

These tests drive ``controls._render_fix_range_slider`` directly: the slider
resolves its own bounds from session state (no ``value=``), so the stored range
after a run is exactly what the plot would be filtered by.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import controls

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _trial(pid: str, tid: str, n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": [pid] * n,
            "trial_id": [tid] * n,
            "order_in_trial": list(range(1, n + 1)),
            "duration_ms": [100] * n,
        }
    )


def _slider_app():
    """Render the window slider for whichever trial the test selected.

    ``AppTest.from_function`` ships only this function's source, so the frame is
    built inline rather than via the module-level ``_trial`` helper.
    """
    import pandas as pd
    import streamlit as st

    from scanpath_studio.controls import _render_fix_range_slider

    spec = st.session_state["_trial_spec"]
    n = spec["n"]
    frame = pd.DataFrame(
        {
            "participant_id": [spec["pid"]] * n,
            "trial_id": [spec["tid"]] * n,
            "order_in_trial": list(range(1, n + 1)),
            "duration_ms": [100] * n,
        }
    )
    _render_fix_range_slider(frame)


def _run_on_trial(at, pid: str, tid: str, n: int):
    at.session_state["_trial_spec"] = {"pid": pid, "tid": tid, "n": n}
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at.session_state["single_fix_range"]


def test_window_is_dropped_when_the_trial_changes_by_default():
    """Per-trial (default): a new trial shows all of its fixations again."""
    at = AppTest.from_function(_slider_app)
    _run_on_trial(at, "p1", "t1", 40)

    # The user drags the slider: the window freezes for THIS trial.
    at.session_state["single_fix_range"] = (5, 20)
    at.session_state["single_fix_range_user_set"] = True
    assert _run_on_trial(at, "p1", "t1", 40) == (5, 20), "same trial must keep it"

    # Switching trials releases it — the new trial renders whole.
    assert _run_on_trial(at, "p1", "t2", 30) == (1, 30)


def test_window_follows_every_trial_when_apply_to_all_is_on():
    """Checked: the window is re-applied to each trial, clamped to its length."""
    at = AppTest.from_function(_slider_app)
    at.session_state["single_fix_range_all_trials"] = True
    _run_on_trial(at, "p1", "t1", 40)

    at.session_state["single_fix_range"] = (5, 20)
    at.session_state["single_fix_range_user_set"] = True
    assert _run_on_trial(at, "p1", "t2", 30) == (5, 20), "window must carry over"

    # A shorter trial can't honour the upper bound; it clamps rather than raising.
    assert _run_on_trial(at, "p1", "t3", 12) == (5, 12)


def test_an_untouched_window_still_follows_the_trial():
    """BUG-16 is unchanged: an auto-default expands to each trial regardless."""
    at = AppTest.from_function(_slider_app)
    assert _run_on_trial(at, "p1", "t1", 40) == (1, 40)
    assert _run_on_trial(at, "p1", "t2", 25) == (1, 25)


def test_checkbox_default_is_off_and_pinned():
    """Off by default, and pinned so it re-syncs on a late-mounting popover."""
    assert controls._VIZ_WIDGET_DEFAULTS["single_fix_range_all_trials"] is False


def test_ambiguous_frame_never_drops_the_window():
    """A multi-trial frame has no single identity, so it must not reset."""
    at = AppTest.from_function(_slider_app)
    _run_on_trial(at, "p1", "t1", 40)
    at.session_state["single_fix_range"] = (5, 20)
    at.session_state["single_fix_range_user_set"] = True

    mixed = pd.concat([_trial("p1", "t1", 10), _trial("p1", "t2", 10)])
    assert controls._fix_range_trial_key(mixed) is None
    assert controls._fix_range_trial_key(_trial("p1", "t1", 3)) == ("p1", "t1")
