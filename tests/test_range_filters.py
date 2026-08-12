"""UX-49: narrowing the trial pool by a *continuous* variable.

Every filter before this one was categorical — a multiselect over a column's
distinct values — which on a numeric column meant one option per distinct float.
The change is that the panel now parses a numeric trial-level column *as
numeric*: a two-ended slider, and a mask that keeps trials with no value.
"""

from __future__ import annotations

import pandas as pd
import pytest
import streamlit as st

from scanpath_studio import controls
from scanpath_studio.data import filter_trials


@pytest.fixture(autouse=True)
def clean_state():
    st.session_state.clear()
    yield
    st.session_state.clear()


def _words():
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2", "p3", "p3"],
            "trial_id": ["a", "a", "a", "a", "a", "a"],
            "word_id": [0, 1, 0, 1, 0, 1],
            # Trial-level: constant within each (participant, trial).
            "comprehension_score": [0.2, 0.2, 0.9, 0.9, float("nan"), float("nan")],
        }
    )


def _fixations():
    # Two fixations per trial, so `duration_ms` genuinely varies *within* one —
    # which is what makes it a row-level column rather than a trial-level one.
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2", "p3", "p3"],
            "trial_id": ["a", "a", "a", "a", "a", "a"],
            "duration_ms": [200, 310, 220, 330, 240, 350],
            "comprehension_score": [0.2, 0.2, 0.9, 0.9, float("nan"), float("nan")],
        }
    )


class TestFilterTrialsRanges:
    def test_it_keeps_only_rows_inside_the_range(self):
        w, f = filter_trials(
            _words(), _fixations(), ranges={"comprehension_score": (0.0, 0.5)}
        )
        assert set(w["participant_id"]) == {"p1", "p3"}
        assert set(f["participant_id"]) == {"p1", "p3"}

    def test_a_missing_value_survives(self):
        """Settled call (4). A range is a *narrowing* control, so a reader with
        no comprehension score is not what the user asked to exclude — and
        pandas compares NaN as False, so a bare `.between()` would drop every
        one of them silently."""
        w, _ = filter_trials(
            _words(), _fixations(), ranges={"comprehension_score": (0.8, 1.0)}
        )
        assert set(w["participant_id"]) == {"p2", "p3"}

    def test_a_full_extent_range_keeps_everything(self):
        w, f = filter_trials(
            _words(), _fixations(), ranges={"comprehension_score": (0.2, 0.9)}
        )
        assert len(w) == 6 and len(f) == 6

    def test_an_absent_column_is_ignored(self):
        w, f = filter_trials(_words(), _fixations(), ranges={"nope": (0, 1)})
        assert len(w) == 6 and len(f) == 6

    def test_ranges_compose_with_categorical_metadata(self):
        words = _words().assign(difficulty_level=["Adv"] * 4 + ["Ele"] * 2)
        w, _ = filter_trials(
            words,
            _fixations(),
            metadata={"difficulty_level": {"Adv"}},
            ranges={"comprehension_score": (0.0, 0.5)},
        )
        assert set(w["participant_id"]) == {"p1"}


class TestWhichColumnsGetASlider:
    """The set of columns the panel *offers* does not grow — what is
    auto-detected is the dtype of what it already offers."""

    def _fields(self, words, fixations, offered):
        st.session_state["wizard_filter_fields"] = offered
        return controls._numeric_filter_fields(words, fixations)

    def test_a_numeric_trial_level_column_gets_one(self):
        fields = self._fields(_words(), _fixations(), ["comprehension_score"])
        assert "comprehension_score" in fields
        _frame, lo, hi = fields["comprehension_score"]
        # Bounds come from the finite values only.
        assert (lo, hi) == (0.2, 0.9)

    def test_a_column_that_varies_inside_a_trial_does_not(self):
        """It would filter *rows*, not trials — silently cutting a scanpath in
        half. That is PRE-2's render-layer territory."""
        fields = self._fields(_words(), _fixations(), ["duration_ms"])
        assert "duration_ms" not in fields

    def test_a_categorical_column_does_not(self):
        words = _words().assign(difficulty_level="Adv")
        fields = self._fields(words, _fixations(), ["difficulty_level"])
        assert "difficulty_level" not in fields

    def test_a_boolean_column_does_not(self):
        words = _words().assign(is_correct=True)
        fields = self._fields(words, _fixations(), ["is_correct"])
        assert "is_correct" not in fields

    def test_a_single_valued_column_gets_no_degenerate_slider(self):
        """Same family as the one-option `st.select_slider` that throws
        RangeError in the browser: render nothing rather than a dead control."""
        words = _words().assign(comprehension_score=0.5)
        fields = self._fields(words, _fixations(), ["comprehension_score"])
        assert "comprehension_score" not in fields

    def test_a_whole_numbered_column_gets_integer_bounds(self):
        """Streamlit reads int-vs-float slider behaviour off the bound *types*,
        so a trial index has to arrive as ints or it steps in 0.01s."""
        words = _words().assign(comprehension_score=[1, 1, 4, 4, 9, 9])
        fields = self._fields(words, _fixations(), ["comprehension_score"])
        _frame, lo, hi = fields["comprehension_score"]
        assert (lo, hi) == (1, 9)
        assert isinstance(lo, int) and isinstance(hi, int)

    def test_a_whole_numbered_column_with_gaps_is_still_integer(self):
        """An int column carrying a NaN is float64 in pandas; what matters is
        that its values are whole, not the dtype it landed on."""
        words = _words().assign(
            comprehension_score=[1, 1, 4, 4, float("nan"), float("nan")]
        )
        _frame, lo, hi = self._fields(words, _fixations(), ["comprehension_score"])[
            "comprehension_score"
        ]
        assert isinstance(lo, int) and isinstance(hi, int)

    def test_a_fractional_column_stays_float(self):
        _frame, lo, hi = self._fields(_words(), _fixations(), ["comprehension_score"])[
            "comprehension_score"
        ]
        assert isinstance(lo, float) and isinstance(hi, float)

    def test_infinities_do_not_pin_the_bounds(self):
        words = _words().assign(
            comprehension_score=[0.2, 0.2, 0.9, 0.9, float("inf")] + [float("inf")]
        )
        fields = self._fields(words, _fixations(), ["comprehension_score"])
        assert fields["comprehension_score"][1:] == (0.2, 0.9)


class TestReadingTheSliderBack:
    def _compute(self, chosen, prefix=""):
        st.session_state["wizard_filter_fields"] = ["comprehension_score"]
        if chosen is not None:
            st.session_state[
                controls._range_filter_key("comprehension_score", prefix)
            ] = chosen
        return controls._compute_trial_filters(_words(), _fixations(), prefix=prefix)

    def test_a_full_extent_slider_is_no_filter(self):
        result = self._compute((0.2, 0.9))
        assert result["ranges"] == {}

    def test_a_narrowed_slider_becomes_a_range(self):
        result = self._compute((0.3, 0.9))
        assert result["ranges"] == {"comprehension_score": (0.3, 0.9)}
        # UX-7's per-filter clear needs the key, already prefixed.
        assert result["metadata_keys"]["comprehension_score"] == (
            "filter_comprehension_score_range"
        )

    def test_the_keys_are_prefix_scoped_for_compare_mode(self):
        result = self._compute((0.3, 0.9), prefix="cmp")
        assert result["metadata_keys"]["comprehension_score"] == (
            "cmpfilter_comprehension_score_range"
        )

    def test_an_untouched_column_contributes_nothing(self):
        assert self._compute(None)["ranges"] == {}

    def test_it_does_not_also_appear_as_a_categorical_filter(self):
        """A numeric column must render as a range *instead of*, not as well as,
        the thousand-option multiselect."""
        result = self._compute((0.3, 0.9))
        assert "comprehension_score" not in result["metadata"]


class TestSeedingAcrossRunsWhereThePanelIsHidden:
    def test_a_stored_range_is_restored_from_the_mirror(self):
        st.session_state["_trial_filters_raw"] = {
            "filter_score_range": (0.3, 0.7),
        }
        controls._seed_range_widget("score", 0.0, 1.0)
        assert st.session_state["filter_score_range"] == (0.3, 0.7)

    def test_a_stored_range_outside_the_new_bounds_is_clamped_not_dropped(self):
        st.session_state["_trial_filters_raw"] = {"filter_score_range": (0.3, 5.0)}
        controls._seed_range_widget("score", 0.0, 1.0)
        assert st.session_state["filter_score_range"] == (0.3, 1.0)

    def test_no_stored_range_seeds_the_full_extent(self):
        controls._seed_range_widget("score", 0.0, 1.0)
        assert st.session_state["filter_score_range"] == (0.0, 1.0)

    def test_integer_bounds_seed_an_integer_pair(self):
        controls._seed_range_widget("idx", 1, 9)
        seeded = st.session_state["filter_idx_range"]
        assert seeded == (1, 9)
        assert all(isinstance(v, int) for v in seeded)

    def test_a_clamped_integer_range_stays_integer(self):
        st.session_state["_trial_filters_raw"] = {"filter_idx_range": (2, 99)}
        controls._seed_range_widget("idx", 1, 9)
        seeded = st.session_state["filter_idx_range"]
        assert seeded == (2, 9)
        assert all(isinstance(v, int) for v in seeded)


class TestTheMissingValueCaption:
    def test_it_counts_trials_not_rows(self):
        missing = controls._trials_missing_column(
            _words(), "comprehension_score", cache_key="t"
        )
        assert missing == 1  # p3 — two word rows, one trial


def test_has_active_trial_filters_notices_a_range():
    st.session_state["_trial_filters"] = {"ranges": {"score": (0.3, 0.9)}}
    assert controls.has_active_trial_filters() is True


class TestTheBundledDemoOffersOne:
    """UX-49 shipped with an all-categorical offered field set, so the slider was
    invisible on every bundled and public corpus — nothing to look at, and
    nothing to catch a regression either. `TRIAL_INDEX` is the presentation
    order: universal on EyeLink exports, genuinely worth filtering on (drop the
    start or the tail of a session), and whole-numbered, so it also exercises the
    integer-slider path end to end.
    """

    @staticmethod
    def _demo_frames():
        from scanpath_studio import data as sps_data

        raw = sps_data.load_sample_data()
        words = sps_data.normalize_words(raw[0], sps_data.infer_word_schema(raw[0]))
        fixations = sps_data.normalize_fixations(
            raw[1], sps_data.infer_fix_schema(raw[1])
        )
        return sps_data.harmonize_frames(words, fixations)

    def test_it_is_offered(self):
        assert "TRIAL_INDEX" in controls._DEFAULT_FILTER_FIELDS

    def test_the_demo_actually_carries_it_as_a_trial_level_column(self):
        """Offered is not the same as present: the field list is intersected
        with the normalized frames, so a name that doesn't survive
        normalization shows nothing (which is how `TRIAL_DWELL_TIME` was ruled
        out — it is dropped as an unregistered passthrough)."""
        words, fixations = self._demo_frames()
        assert "TRIAL_INDEX" in words.columns
        assert "TRIAL_INDEX" in controls._trial_level_columns(words, fixations)

    def test_it_resolves_to_an_integer_slider(self):
        words, _ = self._demo_frames()
        bounds = controls._numeric_column_bounds(words, "TRIAL_INDEX", cache_key="demo")
        assert bounds is not None
        low, high, _ = bounds
        assert isinstance(low, int) and isinstance(high, int)
        assert low < high
