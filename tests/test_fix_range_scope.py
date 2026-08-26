"""The fixation-index window is per-trial unless *Apply to all trials* is on.

A window like "fixations 5-20" rarely means the same thing on a different
reading, so switching trials clears it by default. The checkbox
(``single_fix_range_all_trials``) opts into the old sticky behaviour, where the
window is re-applied to every trial and clamped to its length.

These tests drive ``controls._render_fix_range_slider`` directly: the slider
resolves its own bounds from session state (no ``value=``), so the stored range
after a run is exactly what the plot would be filtered by.

BUG-47 adds the multipart half: a screen's ``order_in_trial`` values are
PARENT-GLOBAL, so a later screen runs e.g. 509-578. Both slider bounds therefore
follow the displayed frame — an untouched window has to equal that frame's own
full range, or ``illustration.illustration_reasons`` reads the difference as a
deliberate "fixation subset" and stamps the figure on every screen but the first.
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
    # BUG-47: `start` is the frame's first PARENT-GLOBAL fixation index — 1 on a
    # single-screen trial, and wherever the screen begins on a multipart one.
    start = spec.get("start", 1)
    frame = pd.DataFrame(
        {
            "participant_id": [spec["pid"]] * n,
            "trial_id": [spec["tid"]] * n,
            "order_in_trial": list(range(start, start + n)),
            "duration_ms": [100] * n,
        }
    )
    screen = spec.get("screen")
    if screen is not None:
        frame["screen_id"] = [screen] * n
    _render_fix_range_slider(frame)


def _run_on_trial(at, pid: str, tid: str, n: int, *, start: int = 1, screen=None):
    at.session_state["_trial_spec"] = {
        "pid": pid,
        "tid": tid,
        "n": n,
        "start": start,
        "screen": screen,
    }
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


# --- BUG-47: multipart screens share one parent-global fixation-index axis -----


def test_untouched_window_covers_a_later_multipart_screen_whole():
    """The default window is the *displayed frame's* range, not ``(1, max)``.

    A later screen of a multipart trial starts at 509, so an untouched window of
    ``(1, 578)`` would not equal the frame's own ``(509, 578)`` — which is exactly
    what the Illustration policy reads as a user-chosen subset.
    """
    at = AppTest.from_function(_slider_app)
    assert _run_on_trial(at, "p1", "t1", 70, start=1, screen="page_1") == (1, 70)
    assert _run_on_trial(at, "p1", "t1", 70, start=509, screen="question_10131") == (
        509,
        578,
    )


def test_a_later_screen_is_not_stamped_as_an_illustration():
    """The end of the chain: no "fixation subset" disclosure on screen 2+.

    ``tabs`` derives ``full_fixation_range`` from the same displayed frame, so
    this pins the two index spaces the bug compared against each other.
    """
    from scanpath_studio.illustration import illustration_reasons

    at = AppTest.from_function(_slider_app)
    window = _run_on_trial(at, "p1", "t1", 70, start=509, screen="question_10131")
    full_range = (509, 578)  # what tabs computes from min/max of the same frame
    reasons = illustration_reasons(
        {},
        fix_index_range=window,
        full_fixation_range=full_range,
    )
    assert reasons == [], reasons

    # ...and a window the user really did narrow is still disclosed.
    narrowed = illustration_reasons(
        {},
        fix_index_range=(520, 540),
        full_fixation_range=full_range,
    )
    assert "fixation subset" in narrowed


def test_window_is_dropped_when_the_screen_changes():
    """A screen is a different reading: a frozen window doesn't follow it.

    Without this the clamp would squash a page-1 window like ``(12, 40)`` onto
    the next screen's floor and draw a single fixation.
    """
    at = AppTest.from_function(_slider_app)
    _run_on_trial(at, "p1", "t1", 70, start=1, screen="page_1")
    at.session_state["single_fix_range"] = (12, 40)
    at.session_state["single_fix_range_user_set"] = True
    assert _run_on_trial(at, "p1", "t1", 70, start=1, screen="page_1") == (12, 40)

    assert _run_on_trial(at, "p1", "t1", 70, start=509, screen="question_10131") == (
        509,
        578,
    )


def test_screen_is_part_of_the_window_identity():
    """The identity key that makes the reset above happen."""
    frame = _trial("p1", "t1", 3)
    frame["screen_id"] = "page_2"
    assert controls._fix_range_trial_key(frame) == ("p1", "t1", "page_2")
    # A frame spanning two screens has no single identity, so it must not reset.
    other = _trial("p1", "t1", 3)
    other["screen_id"] = "page_3"
    assert controls._fix_range_trial_key(pd.concat([frame, other])) is None


def test_bounds_follow_the_displayed_frame():
    """``_fix_range_bounds`` reports the frame's own floor, not a hard-coded 1."""
    assert controls._fix_range_bounds(_trial("p1", "t1", 40)) == (1, 40)
    later = _trial("p1", "t1", 70)
    later["order_in_trial"] = list(range(509, 579))
    assert controls._fix_range_bounds(later) == (509, 578)
    assert controls._fix_range_bounds(None) == (0, 0)
    assert controls._fix_range_bounds(pd.DataFrame()) == (0, 0)


def test_a_one_fixation_screen_clears_the_window():
    """One fixation can't host a range slider wherever its index happens to be.

    The old ``max_fix < 2`` guard only caught this at the start of a trial; a
    single-fixation *screen* at index 509 sailed past it into a degenerate
    one-value slider.
    """
    at = AppTest.from_function(_slider_app)
    _run_on_trial(at, "p1", "t1", 70, start=1, screen="page_1")
    at.session_state["single_fix_range"] = (12, 40)
    at.session_state["single_fix_range_user_set"] = True

    # No exception is half the assertion: a one-value range slider throws.
    assert _run_on_trial(at, "p1", "t1", 1, start=509, screen="question_10131") is None
    assert at.session_state["single_fix_range_user_set"] is False
