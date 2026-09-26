"""Compare mode warns when the two readings are of **different texts**.

The overlay draws both scanpaths over one set of word boxes, so a mismatched
pair is not merely uninformative — it is misleading. The note used to exist for
the animated co-replay only, and only inside the rail's Playback popover; these
pin the wording and the fact that a matching pair stays quiet. A split layout
gives each panel its own stimulus, so it says nothing (CMP-23).
"""

from __future__ import annotations

import pytest

from scanpath_studio.session_keys import (
    SINGLE_COMPARE_LAYOUT,
    SINGLE_COMPARE_STIMULUS,
    SINGLE_COMPARE_TOGGLE,
)
from scanpath_studio.tabs import _different_texts_note

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


#: One booted app per distinct configuration, not per test — and as few distinct
#: configurations as the assertions actually need. Compare mode needs a pool with
#: more than one trial, so these have to boot the **demo** rather than the
#: synthetic source the rest of the AppTest suite leans on, which means rendering
#: every tab over a large dataset. Each boot is therefore a real exposure to
#: ENG-50 (#152), where an occasional `AppTest` boot hangs until its timeout for
#: reasons that have nothing to do with this file, so the fewer boots the better.
#:
#: Two suffice. The animating one is seeded with a **non-default** layout, which
#: lets one run answer all three of "is View greyed", "is Stimulus from still
#: live" and "did the stored layout survive" — the last being the point of
#: "resolve, don't rewrite". Every assertion is read-only (none interacts with a
#: widget), so sharing a finished run between tests is safe.
_BOOTED: dict[tuple[bool, str | None], object] = {}


def _compare_app(*, animate: bool, layout: str | None = None):
    """Boot the app in Compare mode (optionally animating) and return the run."""
    from tests.conftest import APP_SCRIPT

    cached = _BOOTED.get((animate, layout))
    if cached is not None:
        return cached
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state[SINGLE_COMPARE_TOGGLE] = True
    at.session_state["single_animate"] = animate
    if layout is not None:
        at.session_state[SINGLE_COMPARE_LAYOUT] = layout
    at.run()
    _BOOTED[(animate, layout)] = at
    return at


class TestDifferentTextsNote:
    def test_matching_texts_say_nothing(self):
        assert _different_texts_note("t1", "t1") is None

    @pytest.mark.parametrize("missing", [None, ""])
    def test_an_unknown_text_id_is_never_nagged(self, missing):
        """A dataset with no text column cannot answer the question, so it is
        not asked it."""
        assert _different_texts_note(missing, "t2") is None
        assert _different_texts_note("t1", missing) is None

    def test_an_overlay_says_the_boxes_are_shared(self):
        note = _different_texts_note("t1", "t2")
        assert note is not None
        assert "t1" in note and "t2" in note
        assert "one set of word boxes" in note

    def test_ids_are_compared_as_strings(self):
        """`text_id` arrives as whatever the frame held — int on one side and
        str on the other is the same text, not a mismatch."""
        assert _different_texts_note("7", "7") is None


class TestAnimateKeepsTheCompareSettingsOnScreen:
    """UX-140: Animate used to delete **View** and **Stimulus from** from the
    Compare ▾ popover. Both render now — one greyed, one live."""

    def test_the_layout_control_renders_and_is_greyed_under_animate(self):
        at = _compare_app(animate=True, layout="Side by side")
        view = next(w for w in at.segmented_control if w.key == SINGLE_COMPARE_LAYOUT)
        assert view.disabled, "View must render, greyed, while Animate is on"

    def test_the_layout_control_is_live_without_animate(self):
        at = _compare_app(animate=False)
        view = next(w for w in at.segmented_control if w.key == SINGLE_COMPARE_LAYOUT)
        assert not view.disabled

    def test_stimulus_from_stays_usable_under_animate(self):
        """`make_scanpath_animation` reads `compare_stimulus` — it is what stops
        a cross-dataset co-replay running B's trace over A's text — so hiding it
        was a bug, not a gate."""
        at = _compare_app(animate=True, layout="Side by side")
        pick = next(w for w in at.segmented_control if w.key == SINGLE_COMPARE_STIMULUS)
        assert not pick.disabled

    def test_the_stored_layout_survives_a_trip_through_animate(self):
        """Resolve, don't rewrite: Animate forces the figure to overlay without
        touching the key, so the user's own layout comes back.

        Shares the run above deliberately — that app is seeded with **Side by
        side** precisely so this can be asserted without a third boot.
        """
        at = _compare_app(animate=True, layout="Side by side")
        assert at.session_state[SINGLE_COMPARE_LAYOUT] == "Side by side"
