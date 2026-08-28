"""PERF-8: three per-rerun scans whose results were thrown away.

Streamlit reruns the whole script on every widget touch, so anything that walks
the *unfiltered* frames on the way past is paid for on every click — even from a
view that never looks at the answer. Three of them, all found by the same
reading of `app.main`:

* `resolve_source_monitor`'s last-resort branch estimates a canvas from data
  extents. It is reached only by a source that declares no monitor, and what it
  returns then feeds `seed_canvas_state`'s `defaults` — a `setdefault`. After
  the first run the key exists, so every later rerun scanned both frames for a
  number it discarded.
* The 🗂️ Data page's stimulus-folder caption stat'd every row of both frames to
  count matches, undoing `data.resolve_stimulus_image_paths`' own dedup.
* `_slice_fix_range` boolean-masked a copy of the trial's fixations even when
  the window was the untouched default — which *is* the trial's full range, so
  the mask selected everything.

`tabs._compare_setups` withheld the same corpus scan from B's side under CMP-11;
this is A's side and the two others found beside it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import app, tabs
from scanpath_studio.code_snippet import SNIPPET_STATE_KEY
from scanpath_studio.constants import DEMO_CHOICE, SYNTHETIC_CHOICE

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


_WORDS = pd.DataFrame(
    {
        "participant_id": ["p1"] * 3,
        "trial_id": ["t1"] * 3,
        "word_id": [0, 1, 2],
        "text": ["a", "b", "c"],
        "x": [10.0, 60.0, 110.0],
        "y": [10.0] * 3,
        "width": [40.0] * 3,
        "height": [20.0] * 3,
    }
)
_FIXATIONS = pd.DataFrame(
    {
        "participant_id": ["p1"] * 3,
        "trial_id": ["t1"] * 3,
        "x": [20.0, 70.0, 120.0],
        "y": [15.0] * 3,
        "duration_ms": [200.0] * 3,
        "order_in_trial": [1, 2, 3],
    }
)


def _seed_app():
    """Call `seed_canvas_state` on a source that has no declared monitor.

    Everything it needs is built in here: `AppTest.from_function` execs the
    function as a standalone script, so this module's globals are not visible.
    """
    import pandas as pd
    import streamlit as st

    from scanpath_studio import app as app_mod

    _WORDS = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "word_id": [0, 1, 2],
            "text": ["a", "b", "c"],
            "x": [10.0, 60.0, 110.0],
            "y": [10.0] * 3,
            "width": [40.0] * 3,
            "height": [20.0] * 3,
        }
    )
    _FIXATIONS = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "x": [20.0, 70.0, 120.0],
            "y": [15.0] * 3,
            "duration_ms": [200.0] * 3,
            "order_in_trial": [1, 2, 3],
        }
    )
    st.session_state["_calls"] = []
    real = app_mod.compute_canvas_size

    def _counted(words, fixations):
        st.session_state["_calls"].append(
            (None if words is None else len(words), None if fixations is None else 1)
        )
        return real(words, fixations)

    app_mod.compute_canvas_size = _counted
    try:
        app_mod.seed_canvas_state(_WORDS, _FIXATIONS, data_choice="Some upload")
    finally:
        app_mod.compute_canvas_size = real


class TestTheDerivedCanvasIsNotRederivedForever:
    """`seed_canvas_state` withholds the frames once the keys exist."""

    def test_the_first_run_estimates_from_the_data(self):
        at = AppTest.from_function(_seed_app)
        at.run(timeout=30)

        assert not at.exception, at.exception
        assert at.session_state["_calls"] == [(3, 1)], (
            "with no canvas seeded yet, the estimate is the only answer there is"
        )

    def test_a_later_rerun_does_not_touch_the_frames(self):
        at = AppTest.from_function(_seed_app)
        at.session_state["global_canvas_width"] = 1920
        at.session_state["global_canvas_height"] = 1080
        at.run(timeout=30)

        assert not at.exception, at.exception
        assert at.session_state["_calls"] == [(None, None)], (
            "the stored canvas already answers, so neither frame is scanned"
        )
        assert at.session_state["global_canvas_width"] == 1920

    def test_half_a_canvas_still_estimates(self):
        # Only one of the pair present is not "seeded" — `defaults` still has to
        # supply the other, so the estimate is genuinely needed.
        at = AppTest.from_function(_seed_app)
        at.session_state["global_canvas_width"] = 1920
        at.run(timeout=30)

        assert not at.exception, at.exception
        assert at.session_state["_calls"] == [(3, 1)]


class TestWithholdingTheFramesIsHonest:
    """`resolve_source_monitor` degrades rather than inventing an answer."""

    def test_a_declared_monitor_never_needed_the_frames_anyway(self):
        with_frames = app.resolve_source_monitor(DEMO_CHOICE, _WORDS, _FIXATIONS)
        without = app.resolve_source_monitor(DEMO_CHOICE, None, None)

        assert with_frames == without
        assert without[2] is True, "a declared monitor stays authoritative"

    def test_an_undeclared_source_falls_back_and_says_it_is_not_authoritative(self):
        width, height, authoritative = app.resolve_source_monitor(
            "Some upload", None, None
        )

        assert authoritative is False
        assert (width, height) == tuple(app.DEFAULT_FIGURE_SIZE)


class TestTheImageCaptionCountsPathsNotRows:
    def test_a_thousand_rows_of_two_images_stat_two_paths(self, tmp_path, monkeypatch):
        good = tmp_path / "a.png"
        good.write_bytes(b"\x89PNG")
        probes: list[str] = []
        real = app.os.path.isfile
        monkeypatch.setattr(
            app.os.path,
            "isfile",
            lambda path: (probes.append(path), real(path))[1],
        )
        frame = pd.DataFrame(
            {"image_path": [str(good), str(tmp_path / "missing.png")] * 500}
        )

        found = app._rows_with_local_images(frame)

        assert found == 500, "every row naming the real file counts"
        assert len(probes) == 2, "one probe per distinct path"

    def test_missing_values_are_not_probed(self, tmp_path, monkeypatch):
        probes: list[str] = []
        monkeypatch.setattr(
            app.os.path, "isfile", lambda path: (probes.append(path), False)[1]
        )

        found = app._rows_with_local_images(
            pd.DataFrame({"image_path": [None, np.nan, None]})
        )

        assert found == 0
        assert probes == []

    def test_a_frame_with_no_image_path_column_counts_nothing(self):
        assert app._rows_with_local_images(pd.DataFrame({"x": [1.0]})) == 0

    def test_none_counts_nothing(self):
        assert app._rows_with_local_images(None) == 0


class TestAFullWindowIsATrueNoOp:
    """`_slice_fix_range` returns the same object, like `_drift_corrected`."""

    def test_no_window_returns_the_same_frame_object(self):
        assert tabs._slice_fix_range(_FIXATIONS, None) is _FIXATIONS

    def test_a_frame_without_order_in_trial_returns_the_same_object(self):
        bare = _FIXATIONS.drop(columns=["order_in_trial"])

        assert tabs._slice_fix_range(bare, (1, 2)) is bare

    def test_a_real_window_still_slices(self):
        sliced = tabs._slice_fix_range(_FIXATIONS, (2, 3))

        assert sliced is not _FIXATIONS
        assert sliced["order_in_trial"].tolist() == [2, 3]


class TestTheUntouchedSliderDoesNotMask:
    """End to end: the default window reaches `_slice_fix_range` as ``None``.

    The gate lives at the call site rather than in the helper, because the
    trial's full range is already computed there for VIZ-40's Share writer — and
    a length-based shortcut would be wrong on a multipart trial, where
    ``order_in_trial`` is parent-global and a later screen runs 509-578 rather
    than starting at 1 (BUG-47).
    """

    @staticmethod
    def _windows_seen(monkeypatch) -> list:
        seen: list = []
        real = tabs._slice_fix_range

        def _recorded(fix, fix_range):
            seen.append(fix_range)
            return real(fix, fix_range)

        monkeypatch.setattr(tabs, "_slice_fix_range", _recorded)
        return seen

    def test_the_default_window_is_handed_through_as_none(self, monkeypatch):
        seen = self._windows_seen(monkeypatch)
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = SYNTHETIC_CHOICE
        at.run(timeout=120)

        assert not at.exception, at.exception
        assert seen, "the single-trial view always slices once"
        assert seen[-1] is None, (
            "an untouched slider sits at the trial's own full range, so the "
            f"mask is skipped entirely (got {seen[-1]!r})"
        )

    def test_a_dragged_window_is_passed_on(self, monkeypatch):
        seen = self._windows_seen(monkeypatch)
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = SYNTHETIC_CHOICE
        at.session_state["single_fix_range"] = (2, 3)
        at.session_state["single_fix_range_user_set"] = True
        at.run(timeout=120)

        assert not at.exception, at.exception
        assert seen[-1] == (2, 3)


class TestTheCombosRowIsMaskedOnceAtMost:
    """PERF-7: four call sites wanted A's `combos` row; each masked for it.

    ~3.9 ms per mask on a full-OneStop-grain `combos` (~60k rows), on every
    widget toggle — including rail toggles that otherwise hit
    `_cached_scanpath_figure` and draw nothing new. The row's only consumer is
    EXP-5's title/caption pattern, which is unset by default and whose renderer
    early-returns before reading it, so the fix is a *thunk* rather than one
    hoisted mask: the default path does no scan at all.
    """

    @staticmethod
    def _masks(monkeypatch) -> list:
        calls: list = []
        real = tabs._combo_row

        def _counted(combos, participant, trial):
            calls.append((participant, trial))
            return real(combos, participant, trial)

        monkeypatch.setattr(tabs, "_combo_row", _counted)
        return calls

    def _run(self, monkeypatch, **state):
        calls = self._masks(monkeypatch)
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = SYNTHETIC_CHOICE
        # EXP-5's master toggle. Off by default — which is exactly why a thunk
        # beats a hoisted mask: on the default path nothing ever asks.
        at.session_state["global_show_title_caption"] = bool(state)
        for key, value in state.items():
            at.session_state[key] = value
        at.run(timeout=120)
        assert not at.exception, at.exception
        return at, calls

    def test_the_default_path_never_masks(self, monkeypatch):
        # No title and no caption pattern is the default, and nothing else
        # reads the row.
        _at, calls = self._run(monkeypatch)

        assert calls == [], f"nothing asked for the row, yet it was built: {calls}"

    def test_a_title_pattern_masks_exactly_once(self, monkeypatch):
        _at, calls = self._run(monkeypatch, global_title_pattern="{participant_id}")

        assert len(calls) == 1, (
            "the snippet publish and the static branch share one memoized row "
            f"(got {len(calls)} masks)"
        )

    def test_a_caption_pattern_alone_is_enough_to_ask(self, monkeypatch):
        _at, calls = self._run(monkeypatch, global_caption_pattern="{trial_id}")

        assert len(calls) == 1

    def test_the_pattern_still_resolves_against_the_row(self, monkeypatch):
        # The memo must not have turned the row into None on the way through:
        # `{text_id}` comes off the combos row, not off the trial frames.
        at, _calls = self._run(monkeypatch, global_title_pattern="T:{text_id}")

        assert at.session_state["global_title_pattern"] == "T:{text_id}"
        published = at.session_state[SNIPPET_STATE_KEY]
        assert published.title.startswith("T:"), published.title
        assert published.title != "T:{text_id}", (
            "the placeholder should have been rendered against the combos row"
        )
