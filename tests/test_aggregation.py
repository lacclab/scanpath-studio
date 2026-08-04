"""Unit tests for the Corpus Analysis aggregation helpers (``aggregation.py``).

Every public helper gets a tiny hand-built tidy frame whose grouped output is
worked out by hand in the test — grouping keys, NaN/empty handling, the
min-readers guard, the raw-vs-z-scored normalization toggle, and the two-group
difference + effect size. Figure builders are smoke-tested separately in
``tests/test_analysis_figures.py``.

Two of these started life as ``xfail(strict=True)`` against real defects found
while writing them — a min-readers guard that counted rows rather than readers,
and a normalization step that turned an unfixated word into an exactly-average
observation. Both helpers are fixed; the tests are ordinary regression tests now.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio.aggregation import (
    MEASURES,
    Measure,
    add_normalized_column,
    aggregate_value,
    aggregate_word_measures_by_text,
    apply_group,
    available_features,
    available_measures,
    bootstrap_ci,
    cohort_summary_table,
    cohort_word_profile,
    ensure_fixation_enrichment,
    group_effect_size,
    group_mask,
    group_word_difference,
    grouped_metric_values,
    landing_positions,
    measure_values,
    metric_by_fixation_index,
    metric_by_trial_index,
    metric_over_time,
    paired_group_summary,
    per_participant_trend,
    per_reader_word_measure,
    progressive_regressive_counts,
    reader_summary_table,
    reader_summary,
    reader_vs_cohort_values,
    saccade_vs_duration,
    spread_bounds,
    text_read_counts,
    trial_summary_table,
    two_group_values,
    two_group_word_profiles,
    word_box_aggregate,
    word_measure_vs_feature,
    word_rate_profile,
)
from scanpath_studio.data import derive_trial_index, has_explicit_trial_index
from scanpath_studio.measures import word_box_space_px

# -----------------------------------------------------------------------------
# Hand-built fixtures
# -----------------------------------------------------------------------------
#
# Text "A" is read by p1 and p2 (3 words each); text "B" by p3 (1 word), so every
# helper that takes a ``text_col``/``text_id`` can be checked for actually
# scoping. p1's word 2 was skipped, so its TFD is NaN — that single NaN drives
# the NaN-handling and min-readers assertions below.
#
# TFD by (reader, word):        word 0   word 1   word 2
#   p1                            100      300      NaN   (skipped)
#   p2                            200      500      150
#   cohort mean                   150      400      150   (n = 2, 2, 1)


def _tidy_words() -> pd.DataFrame:
    """Two readers × a 3-word text, plus a third reader on a different text.

    The boxes are 10 px wide at x = 0/20/40, i.e. with real 10 px gaps, so
    ``measures.word_box_space_px`` reads the layout as glyph-tight (no trailing
    padding baked into the box) and every landing position below is measured
    from the raw box left. ``test_layout_is_glyph_tight`` pins that premise.
    """
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p2", "p2", "p2", "p3"],
            "trial_id": ["t1", "t1", "t1", "t2", "t2", "t2", "t3"],
            "text_id": ["A", "A", "A", "A", "A", "A", "B"],
            "difficulty_level": ["Adv", "Adv", "Adv", "Ele", "Ele", "Ele", "Adv"],
            "word_id": [0, 1, 2, 0, 1, 2, 0],
            "x": [0.0, 20.0, 40.0, 0.0, 20.0, 40.0, 0.0],
            "y": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "width": [10.0] * 7,
            "height": [10.0] * 7,
            "text": ["the", "cat", "sat", "the", "cat", "sat", "dog"],
            "total_fixation_duration_ms": [
                100.0,
                300.0,
                np.nan,
                200.0,
                500.0,
                150.0,
                900.0,
            ],
            "first_fixation_ms": [80.0, 120.0, np.nan, 90.0, 140.0, 100.0, 200.0],
            "n_fixations": [1, 2, 0, 1, 3, 1, 4],
            "skip_flag": [False, False, True, False, False, False, False],
            "regression_in_flag": [False, True, False, False, True, False, False],
            "gpt2_surprisal": [2.0, 8.0, 5.0, 2.0, 8.0, 5.0, 1.0],
            "universal_pos": ["DET", "NOUN", "VERB", "DET", "NOUN", "VERB", "NOUN"],
            "first_fix_x": [2.0, 23.0, np.nan, 1.0, 25.0, 44.0, 3.0],
        }
    )


def _tidy_fixations() -> pd.DataFrame:
    """p1: 3 fixations (word 0 → 1 → back to 0); p2: 2 fixations (0 → 1).

    p1's third fixation is the only regression. Reading spans: p1 = 380 ms
    (0 → 250+130), p2 = 300 ms (0 → 120+180).
    """
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t1", "t1", "t2", "t2"],
            "difficulty_level": ["Adv", "Adv", "Adv", "Ele", "Ele"],
            "order_in_trial": [1, 2, 3, 1, 2],
            "timestamp_ms": [0.0, 100.0, 250.0, 0.0, 120.0],
            "duration_ms": [100.0, 150.0, 130.0, 200.0, 180.0],
            "saccade_amplitude": [np.nan, 3.0, 1.0, np.nan, 4.0],
            "word_id": [0.0, 1.0, 0.0, 0.0, 1.0],
            "x": [2.0, 23.0, 4.0, 1.0, 25.0],
            "y": [0.0, 0.0, 0.0, 0.0, 0.0],
            "is_regression": [False, False, True, False, False],
        }
    )


def _trend_frame() -> pd.DataFrame:
    """Per-trial-index frame: p1 reads t1 (index 1) then t2 (index 2), p2 tA."""
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p1", "p2", "p2", "p2"],
            "trial_id": ["t1", "t1", "t2", "t2", "tA", "tA", "tA"],
            "trial_index": [1, 1, 2, 2, 1, 1, 1],
            "duration_ms": [10.0, 20.0, 30.0, 50.0, 100.0, 200.0, np.nan],
        }
    )


def test_layout_is_glyph_tight():
    """The fixture's boxes leave real gaps, so box left == raw ``x`` (BUG-11)."""
    assert word_box_space_px(_tidy_words()) == 0.0


class TestDeriveTrialIndex:
    def test_uses_explicit_column(self):
        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t2", "t1"],
                "trial_index": [5, 6, 1],
            }
        )
        assert has_explicit_trial_index(df)
        out = derive_trial_index(df)
        assert list(out) == [5.0, 6.0, 1.0]

    def test_derives_from_timestamp_per_participant(self):
        # p1 reads t2 (ts 0) before t1 (ts 100) → t2=1, t1=2.
        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1", "p1", "p2"],
                "trial_id": ["t1", "t1", "t2", "t2", "tX"],
                "timestamp_ms": [100, 150, 0, 50, 999],
            }
        )
        assert not has_explicit_trial_index(df)
        out = derive_trial_index(df)
        # rows for t1 → 2, t2 → 1, p2 tX → 1
        assert list(out) == [2.0, 2.0, 1.0, 1.0, 1.0]

    def test_single_trial_per_participant(self):
        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "timestamp_ms": [0, 10],
            }
        )
        assert list(derive_trial_index(df)) == [1.0, 1.0]

    def test_empty(self):
        out = derive_trial_index(pd.DataFrame())
        assert out.empty


class TestMetricByTrialIndex:
    def test_averages_per_trial_then_per_index(self):
        # Two trials at index 1 (means 100 and 200) → index-1 value = 150.
        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2", "p2"],
                "trial_id": ["t1", "t1", "tA", "tA"],
                "trial_index": [1, 1, 1, 1],
                "duration_ms": [50, 150, 100, 300],
            }
        )
        out = metric_by_trial_index(df, "duration_ms")
        assert list(out["trial_index"]) == [1]
        assert out.iloc[0]["value"] == 150.0
        assert out.iloc[0]["n_trials"] == 2

    def test_missing_metric_returns_empty(self):
        df = pd.DataFrame(
            {"participant_id": ["p1"], "trial_id": ["t1"], "trial_index": [1]}
        )
        assert metric_by_trial_index(df, "nope").empty

    def test_exact_values_sem_and_nan_rows_dropped(self):
        # Per-trial means: (p1,t1)=15, (p1,t2)=40, (p2,tA)=150 — the NaN row is
        # dropped before the per-trial mean, so tA is mean(100, 200) not NaN.
        out = metric_by_trial_index(_trend_frame(), "duration_ms")
        assert list(out["trial_index"]) == [1, 2]
        assert list(out["value"]) == [82.5, 40.0]  # mean(15, 150), mean(40)
        assert list(out["n_trials"]) == [2, 1]
        # sd([15, 150], ddof=1) / sqrt(2) = 95.4594 / 1.41421
        assert out.loc[0, "sem"] == pytest.approx(67.5)
        assert out.loc[1, "sem"] == 0.0  # single trial → NaN sem filled with 0

    def test_agg_applies_within_trial_only(self):
        # agg collapses each trial; the across-trial step is always the mean.
        out = metric_by_trial_index(_trend_frame(), "duration_ms", agg="sum")
        # per-trial sums 30 / 80 / 300 → index 1 = mean(30, 300) = 165.
        assert list(out["value"]) == [165.0, 80.0]

    def test_empty_frame(self):
        out = metric_by_trial_index(pd.DataFrame(), "duration_ms")
        assert out.empty
        assert list(out.columns) == ["trial_index", "value", "sem", "n_trials"]


class TestMetricByFixationIndex:
    def test_groups_by_order_in_trial(self):
        fix = pd.DataFrame(
            {
                "order_in_trial": [1, 1, 2, 2],
                "duration_ms": [100, 200, 50, 50],
            }
        )
        out = metric_by_fixation_index(fix, "duration_ms")
        assert list(out["fixation_index"]) == [1, 2]
        assert list(out["value"]) == [150.0, 50.0]

    def test_respects_max_index(self):
        fix = pd.DataFrame({"order_in_trial": [1, 2, 3], "duration_ms": [10, 20, 30]})
        out = metric_by_fixation_index(fix, "duration_ms", max_index=2)
        assert list(out["fixation_index"]) == [1, 2]

    def test_pools_across_participants_with_sem(self):
        out = metric_by_fixation_index(_tidy_fixations(), "duration_ms")
        assert list(out["fixation_index"]) == [1, 2, 3]
        assert list(out["value"]) == [150.0, 165.0, 130.0]
        assert list(out["n"]) == [2, 2, 1]
        assert list(out["sem"]) == pytest.approx([50.0, 15.0, 0.0])

    def test_nan_index_or_metric_rows_are_dropped(self):
        fix = pd.DataFrame(
            {
                "order_in_trial": [1, 1, np.nan, 2],
                "duration_ms": [100.0, np.nan, 50.0, 40.0],
            }
        )
        out = metric_by_fixation_index(fix, "duration_ms")
        assert list(out["fixation_index"]) == [1.0, 2.0]
        assert list(out["value"]) == [100.0, 40.0]
        assert list(out["n"]) == [1, 1]  # the NaN-metric row never reaches index 1

    def test_missing_order_column_returns_empty(self):
        fix = _tidy_fixations().drop(columns=["order_in_trial"])
        out = metric_by_fixation_index(fix, "duration_ms")
        assert out.empty
        assert list(out.columns) == ["fixation_index", "value", "sem", "n"]


class TestGroupedMetricValues:
    def test_all_data_single_group(self):
        df = pd.DataFrame({"duration_ms": [1.0, 2.0, 3.0]})
        groups, dropped = grouped_metric_values(df, "duration_ms")
        assert set(groups) == {"All"}
        assert dropped == 0
        np.testing.assert_array_equal(groups["All"], np.array([1.0, 2.0, 3.0]))

    def test_keeps_the_largest_groups_and_reports_the_rest(self):
        # Sizes 5/4/3/2/1 → the cap keeps the two *largest*, not the first two
        # encountered, and the other three are reported through ``n_dropped``.
        sizes = {"e": 1, "c": 3, "a": 5, "d": 2, "b": 4}
        labels = [k for k, n in sizes.items() for _ in range(n)]
        df = pd.DataFrame({"m": np.arange(len(labels), dtype=float), "g": labels})
        groups, dropped = grouped_metric_values(df, "m", "g", max_groups=2)
        assert set(groups) == {"a", "b"}
        assert dropped == 3
        # "a" holds rows 4-8 (it follows "e" and "c" in the frame), "b" the last 4.
        np.testing.assert_array_equal(groups["a"], np.arange(4.0, 9.0))
        np.testing.assert_array_equal(groups["b"], np.arange(11.0, 15.0))

    def test_nan_values_dropped_and_all_nan_group_omitted(self):
        df = pd.DataFrame(
            {"m": [1.0, 2.0, np.nan, np.nan, 5.0], "g": ["a", "a", "a", "b", "c"]}
        )
        groups, dropped = grouped_metric_values(df, "m", "g")
        # "b" is all-NaN so it produces no entry — and it is NOT counted in
        # `dropped`, which only reports groups cut by `max_groups`.
        assert set(groups) == {"a", "c"}
        assert dropped == 0
        np.testing.assert_array_equal(groups["a"], np.array([1.0, 2.0]))
        np.testing.assert_array_equal(groups["c"], np.array([5.0]))

    def test_unknown_group_col_falls_back_to_all(self):
        df = pd.DataFrame({"m": [1.0, 2.0]})
        groups, dropped = grouped_metric_values(df, "m", "not_a_column")
        assert set(groups) == {"All"}
        assert dropped == 0

    def test_missing_metric_and_empty_frame(self):
        assert grouped_metric_values(pd.DataFrame({"m": [1.0]}), "nope") == ({}, 0)
        assert grouped_metric_values(pd.DataFrame(), "m") == ({}, 0)


class TestPerTextAggregates:
    def _words(self):
        return pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2", "p2"],
                "trial_id": ["t1", "t1", "t2", "t2"],
                "text_id": ["A", "A", "A", "A"],
                "word_id": [0, 1, 0, 1],
                "x": [0, 10, 0, 10],
                "y": [0, 0, 0, 0],
                "width": [10, 10, 10, 10],
                "height": [10, 10, 10, 10],
                "text": ["the", "cat", "the", "cat"],
                "total_fixation_duration_ms": [100, 200, 300, 400],
                "n_fixations": [1, 2, 3, 4],
            }
        )

    def test_aggregate_word_measures_by_text(self):
        out = aggregate_word_measures_by_text(self._words(), "text_id", "A")
        assert len(out) == 2  # one row per word_id
        word0 = out[out["word_id"] == 0].iloc[0]
        assert word0["total_fixation_duration_ms"] == 200.0  # mean(100, 300)
        assert {"x", "y", "width", "height", "text"} <= set(out.columns)

    def test_text_read_counts(self):
        counts = text_read_counts(self._words(), "text_id")
        assert list(counts["text"]) == ["A"]
        assert list(counts["n_participants"]) == [2]

    def test_aggregate_skips_nans_and_stamps_synthetic_trial(self):
        out = aggregate_word_measures_by_text(_tidy_words(), "text_id", "A")
        assert list(out["word_id"]) == [0, 1, 2]
        # word 2: p1 is NaN → the mean is p2's value alone, not NaN.
        assert list(out["total_fixation_duration_ms"]) == [150.0, 400.0, 150.0]
        assert list(out["n_fixations"]) == [1.0, 2.5, 0.5]
        assert list(out["text"]) == ["the", "cat", "sat"]
        # Synthetic identity so the words-only heatmap path accepts the frame.
        assert set(out["participant_id"]) == {"aggregate"}
        assert set(out["trial_id"]) == {"A"}

    def test_aggregate_honours_agg_and_text_scope(self):
        out = aggregate_word_measures_by_text(_tidy_words(), "text_id", "A", agg="sum")
        assert list(out["total_fixation_duration_ms"]) == [300.0, 800.0, 150.0]
        # Text B (p3, TFD 900) must not leak into text A.
        assert 900.0 not in set(out["total_fixation_duration_ms"])

    def test_aggregate_needs_word_id_and_geometry(self):
        assert aggregate_word_measures_by_text(
            _tidy_words().drop(columns=["word_id"]), "text_id", "A"
        ).empty
        no_geom = _tidy_words().drop(columns=["x", "y", "width", "height", "text"])
        assert aggregate_word_measures_by_text(no_geom, "text_id", "A").empty
        assert aggregate_word_measures_by_text(
            _tidy_words(), "text_id", "does-not-exist"
        ).empty

    def test_text_read_counts_sorted_by_readers_desc(self):
        counts = text_read_counts(_tidy_words(), "text_id")
        assert list(counts["text"]) == ["A", "B"]
        assert list(counts["n_participants"]) == [2, 1]

    def test_text_read_counts_missing_columns(self):
        out = text_read_counts(_tidy_words(), "nope")
        assert out.empty
        assert list(out.columns) == ["text", "n_participants"]


# -----------------------------------------------------------------------------
# Measure registry + primitives
# -----------------------------------------------------------------------------


class TestMeasureRegistry:
    def test_axis_label_appends_unit_only_when_present(self):
        assert MEASURES["tfd"].axis_label == "Total fixation duration — TFD (ms)"
        assert MEASURES["sacc_amp"].axis_label == "Saccade amplitude (px)"
        assert MEASURES["skip"].axis_label == "Skip rate"  # unitless → bare label

    def test_registry_invariants(self):
        for key, m in MEASURES.items():
            assert isinstance(m, Measure)
            assert m.key == key  # the dict is keyed by the measure's own key
            assert m.frame in {"words", "fixations"}
            if m.is_rate:
                assert m.unit == ""  # a 0–1 rate has no axis unit
                assert m.frame == "words"
        # TFD is the default → first in insertion (picker) order.
        assert next(iter(MEASURES)) == "tfd"

    def test_available_measures_filters_on_backing_column(self):
        words = pd.DataFrame({"total_fixation_duration_ms": [1.0], "skip_flag": [True]})
        fixations = pd.DataFrame({"duration_ms": [1.0]})
        assert [m.key for m in available_measures(words, fixations)] == [
            "tfd",
            "skip",
            "fix_dur",
        ]
        assert [
            m.key for m in available_measures(words, fixations, per_word_only=True)
        ] == ["tfd", "skip"]
        # A missing fixations frame simply contributes nothing.
        assert [m.key for m in available_measures(words, None)] == ["tfd", "skip"]

    def test_available_features(self):
        feats = available_features(_tidy_words())
        assert feats == {
            "GPT-2 surprisal": ("gpt2_surprisal", False),
            "Part of speech": ("universal_pos", True),
        }
        assert available_features(pd.DataFrame()) == {}
        assert available_features(None) == {}
        # A frame carrying every registered column gets the whole registry —
        # pins the four labels the AN-5 feature picker offers.
        rich = _tidy_words().assign(wordfreq_frequency=1.0, word_length=3)
        assert available_features(rich) == {
            "GPT-2 surprisal": ("gpt2_surprisal", False),
            "Word frequency (wordfreq)": ("wordfreq_frequency", False),
            "Word length": ("word_length", False),
            "Part of speech": ("universal_pos", True),
        }


class TestPrimitives:
    def test_aggregate_value(self):
        assert aggregate_value([1, 2, 3], "mean") == 2.0
        assert aggregate_value([1, 2, 3, 4], "median") == 2.5
        assert aggregate_value([1, 2, 3], "sum") == 6.0
        assert aggregate_value([1.0, np.nan, 3.0], "mean") == 2.0  # NaNs ignored
        assert np.isnan(aggregate_value([np.nan], "mean"))
        assert np.isnan(aggregate_value([], "mean"))
        assert aggregate_value([1, 2, 3], "not-an-agg") == 2.0  # falls back to mean

    def test_spread_bounds_bands(self):
        vals = np.array([10.0, 20.0, 30.0])  # sd(ddof=1) = 10.0
        assert spread_bounds(vals, 20.0, "IQR") == (15.0, 25.0)
        assert spread_bounds(vals, 20.0, "SD") == pytest.approx((10.0, 30.0))
        # SEM = sd / sqrt(3) = 5.7735
        assert spread_bounds(vals, 20.0, "SEM") == pytest.approx(
            (20.0 - 10.0 / np.sqrt(3), 20.0 + 10.0 / np.sqrt(3))
        )

    def test_spread_bounds_degenerate_inputs(self):
        assert spread_bounds(np.array([]), 5.0, "SD") == (5.0, 5.0)
        lo, hi = spread_bounds(np.array([1.0, 2.0]), float("nan"), "SD")
        assert np.isnan(lo) and np.isnan(hi)
        # A single observation has no SD → a zero-width band around the centre.
        assert spread_bounds(np.array([7.0]), 7.0, "SD") == (7.0, 7.0)

    def test_bootstrap_spread_delegates_to_bootstrap_ci(self):
        vals = np.array([10.0, 20.0, 30.0, 40.0])
        assert spread_bounds(vals, 25.0, "Bootstrap CI") == bootstrap_ci(vals)
        # The band is around the *aggregate*, so it is far tighter than the SD
        # of the individual observations.
        lo, hi = spread_bounds(vals, 25.0, "Bootstrap CI")
        assert lo > 25.0 - float(np.std(vals, ddof=1))
        assert hi < 25.0 + float(np.std(vals, ddof=1))

    def test_sum_band_brackets_the_total(self):
        # SD/SEM of individual observations is meaningless around a total, so
        # `sum` bootstraps the aggregate instead.
        lo, hi = spread_bounds(np.array([100.0, 200.0, 300.0]), 600.0, "SD", agg="sum")
        assert lo <= 600.0 <= hi

    def test_bootstrap_ci(self):
        vals = np.arange(50, dtype=float)
        assert bootstrap_ci(vals, seed=0) == bootstrap_ci(vals, seed=0)
        lo, hi = bootstrap_ci(vals, seed=0)
        assert lo < float(np.mean(vals)) < hi
        # A narrower CI level is strictly inside the wider one.
        lo50, hi50 = bootstrap_ci(vals, seed=0, ci=50.0)
        assert lo < lo50 and hi50 < hi
        # Fewer than two observations → the point estimate for both bounds.
        assert bootstrap_ci(np.array([4.0]), seed=0) == (4.0, 4.0)


class TestAddNormalizedColumn:
    def test_z_scores_within_group(self):
        df = pd.DataFrame(
            {"participant_id": ["p1", "p1", "p2", "p2"], "v": [100.0, 300.0, 1.0, 3.0]}
        )
        out = add_normalized_column(df, "v")
        # Two observations per reader → z = ±1/sqrt(2) in both groups, so slow
        # and fast readers land on the same scale.
        assert list(out["v"]) == pytest.approx(
            [-1 / np.sqrt(2), 1 / np.sqrt(2), -1 / np.sqrt(2), 1 / np.sqrt(2)]
        )

    def test_zero_variance_and_singleton_groups_map_to_zero(self):
        df = pd.DataFrame({"participant_id": ["p1", "p1", "p2"], "v": [5.0, 5.0, 42.0]})
        out = add_normalized_column(df, "v")
        assert list(out["v"]) == [0.0, 0.0, 0.0]

    def test_out_col_keeps_the_source_column(self):
        df = pd.DataFrame({"participant_id": ["p1", "p1"], "v": [1.0, 3.0]})
        out = add_normalized_column(df, "v", out_col="z")
        assert list(out["v"]) == [1.0, 3.0]
        assert list(out["z"]) == pytest.approx([-1 / np.sqrt(2), 1 / np.sqrt(2)])

    def test_missing_by_column_z_scores_globally(self):
        df = pd.DataFrame({"v": [1.0, 2.0, 3.0]})  # sd(ddof=1) = 1.0
        assert list(add_normalized_column(df, "v")["v"]) == pytest.approx(
            [-1.0, 0.0, 1.0]
        )
        flat = pd.DataFrame({"v": [2.0, 2.0, 2.0]})
        assert list(add_normalized_column(flat, "v")["v"]) == [0.0, 0.0, 0.0]

    def test_does_not_mutate_the_input(self):
        df = pd.DataFrame({"participant_id": ["p1", "p1"], "v": [1.0, 3.0]})
        add_normalized_column(df, "v")
        assert list(df["v"]) == [1.0, 3.0]


# -----------------------------------------------------------------------------
# Per text: one text, many readers
# -----------------------------------------------------------------------------


class TestPerReaderWordMeasure:
    def test_one_row_per_reader_word_scoped_to_the_text(self):
        out = per_reader_word_measure(_tidy_words(), "text_id", "A", MEASURES["tfd"])
        assert list(out["participant_id"]) == ["p1", "p1", "p2", "p2", "p2"]
        assert list(out["word_id"]) == [0, 1, 0, 1, 2]
        assert list(out["value"]) == [100.0, 300.0, 200.0, 500.0, 150.0]
        assert list(out["word_text"]) == ["the", "cat", "the", "cat", "sat"]
        # p3 reads text B only.
        assert "p3" not in set(out["participant_id"])

    def test_repeated_readings_collapse_under_agg(self):
        # Same reader, same word, two readings → one row.
        w = pd.concat([_tidy_words(), _tidy_words().head(1)], ignore_index=True)
        w.loc[w.index[-1], "total_fixation_duration_ms"] = 500.0
        out = per_reader_word_measure(w, "text_id", "A", MEASURES["tfd"], agg="mean")
        assert len(out) == 5
        val = out[(out.participant_id == "p1") & (out.word_id == 0)]["value"].iloc[0]
        assert val == 300.0  # mean(100, 500)
        out_max = per_reader_word_measure(w, "text_id", "A", MEASURES["tfd"], agg="max")
        val_max = out_max[(out_max.participant_id == "p1") & (out_max.word_id == 0)][
            "value"
        ].iloc[0]
        assert val_max == 500.0

    def test_normalize_z_scores_within_reader(self):
        out = per_reader_word_measure(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], normalize=True
        )
        p1 = out[out.participant_id == "p1"]["value"].to_numpy()
        assert list(p1) == pytest.approx([-1 / np.sqrt(2), 1 / np.sqrt(2)])
        p2 = out[out.participant_id == "p2"]["value"].to_numpy()
        assert p2.mean() == pytest.approx(0.0)
        assert p2.std(ddof=1) == pytest.approx(1.0)

    def test_normalize_is_a_no_op_for_rates(self):
        # A 0–1 rate is already on a comparable scale; z-scoring would destroy it.
        raw = per_reader_word_measure(_tidy_words(), "text_id", "A", MEASURES["skip"])
        z = per_reader_word_measure(
            _tidy_words(), "text_id", "A", MEASURES["skip"], normalize=True
        )
        assert list(raw["value"]) == [0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
        pd.testing.assert_frame_equal(raw, z)

    def test_missing_columns_and_unknown_text(self):
        cols = ["participant_id", "word_id", "value", "word_text"]
        assert (
            list(
                per_reader_word_measure(
                    _tidy_words(), "text_id", "nope", MEASURES["tfd"]
                ).columns
            )
            == cols
        )
        no_measure = _tidy_words().drop(columns=["total_fixation_duration_ms"])
        out = per_reader_word_measure(no_measure, "text_id", "A", MEASURES["tfd"])
        assert out.empty and list(out.columns) == cols


class TestCohortWordProfile:
    def test_centre_band_and_reader_counts(self):
        out = cohort_word_profile(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], spread="SD"
        )
        assert list(out["word_id"]) == [0, 1, 2]
        assert list(out["value"]) == [150.0, 400.0, 150.0]
        assert list(out["n"]) == [2, 2, 1]  # p1's word 2 is NaN → one reader
        assert list(out["word_text"]) == ["the", "cat", "sat"]
        sd0 = float(np.std([100.0, 200.0], ddof=1))  # 70.7107
        assert out.loc[0, "lo"] == pytest.approx(150.0 - sd0)
        assert out.loc[0, "hi"] == pytest.approx(150.0 + sd0)
        # One contributing reader → a zero-width band, not NaN.
        assert (out.loc[2, "lo"], out.loc[2, "hi"]) == (150.0, 150.0)

    def test_min_readers_guard_is_per_word(self):
        out = cohort_word_profile(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], min_readers=2
        )
        assert list(out["enough"]) == [True, True, False]
        assert list(
            cohort_word_profile(
                _tidy_words(), "text_id", "A", MEASURES["tfd"], min_readers=3
            )["enough"]
        ) == [False, False, False]
        # The guard flags rows, it never drops them.
        assert len(out) == 3

    def test_iqr_band(self):
        out = cohort_word_profile(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], spread="IQR"
        )
        assert (out.loc[1, "lo"], out.loc[1, "hi"]) == (350.0, 450.0)

    def test_sum_agg_totals_across_readers_and_bootstraps_the_band(self):
        out = cohort_word_profile(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], agg="sum", spread="SD"
        )
        assert list(out["value"]) == [300.0, 800.0, 150.0]  # totals, not means
        # An SD of individual readers says nothing about their total, so the
        # band bootstraps the sum instead: resampling two readers from
        # {100, 200} can only total 200 / 300 / 400.
        assert (out.loc[0, "lo"], out.loc[0, "hi"]) == (200.0, 400.0)
        assert (out.loc[1, "lo"], out.loc[1, "hi"]) == (600.0, 1000.0)
        # One contributing reader can't be resampled → a point band.
        assert (out.loc[2, "lo"], out.loc[2, "hi"]) == (150.0, 150.0)

    def test_empty_returns_typed_columns(self):
        out = cohort_word_profile(_tidy_words(), "text_id", "nope", MEASURES["tfd"])
        assert out.empty
        assert list(out.columns) == [
            "word_id",
            "value",
            "lo",
            "hi",
            "n",
            "enough",
            "word_text",
        ]


class TestWordBoxAggregate:
    def test_geometry_plus_value_and_synthetic_identity(self):
        out = word_box_aggregate(_tidy_words(), "text_id", "A", MEASURES["tfd"])
        assert list(out["word_id"]) == [0, 1, 2]
        assert list(out["value"]) == [150.0, 400.0, 150.0]  # NaN skipped on word 2
        assert list(out["x"]) == [0.0, 20.0, 40.0]
        assert {"x", "y", "width", "height", "text"} <= set(out.columns)
        assert set(out["participant_id"]) == {"aggregate"}
        assert set(out["trial_id"]) == {"A"}

    def test_sum_agg_totals_across_readers(self):
        out = word_box_aggregate(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], agg="sum"
        )
        assert list(out["value"]) == [300.0, 800.0, 150.0]

    def test_rate_measure_becomes_a_share(self):
        out = word_box_aggregate(_tidy_words(), "text_id", "A", MEASURES["skip"])
        # Word 2 skipped by p1 only → 0.5; the others by nobody → 0.0.
        assert list(out["value"]) == [0.0, 0.0, 0.5]

    def test_missing_measure_or_geometry(self):
        assert word_box_aggregate(
            _tidy_words().drop(columns=["total_fixation_duration_ms"]),
            "text_id",
            "A",
            MEASURES["tfd"],
        ).empty
        no_geom = _tidy_words().drop(columns=["x", "y", "width", "height", "text"])
        assert word_box_aggregate(no_geom, "text_id", "A", MEASURES["tfd"]).empty


class TestWordMeasureVsFeature:
    def test_pairs_cohort_value_with_the_per_word_feature(self):
        out = word_measure_vs_feature(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], "gpt2_surprisal"
        )
        assert list(out["word_id"]) == [0, 1, 2]
        assert list(out["value"]) == [150.0, 400.0, 150.0]
        assert list(out["feature"]) == [2.0, 8.0, 5.0]
        assert list(out["word_text"]) == ["the", "cat", "sat"]

    def test_categorical_feature_passes_through(self):
        out = word_measure_vs_feature(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], "universal_pos"
        )
        assert list(out["feature"]) == ["DET", "NOUN", "VERB"]

    def test_missing_feature_column(self):
        out = word_measure_vs_feature(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], "not_a_feature"
        )
        assert out.empty
        assert list(out.columns) == ["word_id", "value", "feature", "word_text"]

    def test_no_text_column_yields_no_word_text_at_all(self):
        # Without a `text` column the named-aggregation must not synthesize a
        # `word_text` key — pandas would fill it with the per-word row count,
        # and the hover label would read "2" instead of the word.
        w = _tidy_words().drop(columns=["text"])
        out = word_measure_vs_feature(
            w, "text_id", "A", MEASURES["tfd"], "gpt2_surprisal"
        )
        assert list(out.columns) == ["word_id", "value", "feature"]
        assert list(out["value"]) == [150.0, 400.0, 150.0]


class TestWordRateProfile:
    def test_rates_counts_and_guard(self):
        out = word_rate_profile(_tidy_words(), "text_id", "A", min_readers=2)
        assert list(out["word_id"]) == [0, 1, 2]
        assert list(out["skip_rate"]) == [0.0, 0.0, 0.5]  # p1 skipped word 2
        assert list(out["regression_in_rate"]) == [0.0, 1.0, 0.0]
        assert list(out["n"]) == [2, 2, 2]
        assert list(out["enough"]) == [True, True, True]
        assert list(out["word_text"]) == ["the", "cat", "sat"]
        assert list(
            word_rate_profile(_tidy_words(), "text_id", "A", min_readers=3)["enough"]
        ) == [False, False, False]

    def test_min_readers_guard_counts_readers_not_rows(self):
        # p1 reads text A a second time: word 0 now has three rows but still
        # only two distinct readers, so a 3-reader guard must reject it.
        w = pd.concat([_tidy_words(), _tidy_words().head(1)], ignore_index=True)
        reference = cohort_word_profile(
            w, "text_id", "A", MEASURES["tfd"], min_readers=3
        )
        assert list(reference["n"]) == [2, 2, 1]  # the per-reader collapse
        assert not reference["enough"].any()
        assert not word_rate_profile(w, "text_id", "A", min_readers=3)["enough"].any()

    def test_missing_flag_columns_yield_nan_rates(self):
        w = _tidy_words().drop(columns=["skip_flag", "regression_in_flag"])
        out = word_rate_profile(w, "text_id", "A")
        assert out["skip_rate"].isna().all()
        assert out["regression_in_rate"].isna().all()
        assert list(out["n"]) == [2, 2, 2]  # the row count still stands

    def test_empty_returns_typed_columns(self):
        out = word_rate_profile(_tidy_words(), "text_id", "nope")
        assert out.empty
        assert list(out.columns) == [
            "word_id",
            "skip_rate",
            "regression_in_rate",
            "n",
            "enough",
            "word_text",
        ]


# -----------------------------------------------------------------------------
# Per reader: one reader, many trials
# -----------------------------------------------------------------------------


class TestMeasureValues:
    def test_flat_values_with_nans_dropped(self):
        vals = measure_values(_tidy_words(), MEASURES["tfd"])
        assert sorted(vals) == [100.0, 150.0, 200.0, 300.0, 500.0, 900.0]

    def test_rates_coerced_to_floats_and_never_normalized(self):
        raw = measure_values(_tidy_words(), MEASURES["skip"])
        assert raw.dtype == np.dtype("float64")
        assert raw.sum() == 1.0 and raw.size == 7
        z = measure_values(_tidy_words(), MEASURES["skip"], normalize=True)
        np.testing.assert_array_equal(raw, z)

    def test_normalize_z_scores_within_reader(self):
        w = _tidy_words()
        # p1's two *observed* words → z = ±1/sqrt(2) about their own mean.
        one_reader = w[
            (w.participant_id == "p1") & w.total_fixation_duration_ms.notna()
        ]
        vals = measure_values(one_reader, MEASURES["tfd"], normalize=True)
        assert sorted(vals) == pytest.approx([-1 / np.sqrt(2), 1 / np.sqrt(2)])

    def test_normalize_keeps_the_same_observations_as_raw(self):
        raw = measure_values(_tidy_words(), MEASURES["tfd"])
        z = measure_values(_tidy_words(), MEASURES["tfd"], normalize=True)
        assert z.size == raw.size

    def test_missing_column_and_empty_frame(self):
        assert measure_values(_tidy_words(), MEASURES["sacc_amp"]).size == 0
        assert measure_values(pd.DataFrame(), MEASURES["tfd"]).size == 0
        assert measure_values(None, MEASURES["tfd"]).size == 0


class TestReaderViews:
    def test_trial_summary_table_includes_runs_and_reading_splits(self):
        words = _tidy_words().copy()
        words["is_correct"] = [True, True, True, False, False, False, True]
        table = trial_summary_table(words, _tidy_fixations())
        p1 = table[table.participant_id == "p1"].iloc[0]
        assert p1["n_fixations"] == 3
        assert p1["total_fixation_ms"] == pytest.approx(380.0)
        assert p1["mean_forward_saccade_px"] == pytest.approx(3.0)
        assert p1["nrun"] == 3
        assert p1["first_pass_ms"] == pytest.approx(250.0)
        assert p1["rereading_ms"] == pytest.approx(130.0)
        assert p1["refixation_rate"] == pytest.approx(0.0)
        assert p1["regression_in_rate"] == pytest.approx(1 / 3)
        assert p1["question_correct"] == 1.0

    def test_reader_summary_table_aggregates_trial_table_fields(self):
        words = _tidy_words().copy()
        words["is_correct"] = [True, True, True, False, False, False, True]
        table = reader_summary_table(words, _tidy_fixations())
        p1 = table[table.participant_id == "p1"].iloc[0]
        assert p1["total_fixation_ms"] == pytest.approx(380.0)
        assert p1["first_pass_ms"] == pytest.approx(250.0)
        assert p1["rereading_ms"] == pytest.approx(130.0)
        assert p1["n_question_correct"] == 1.0
        assert p1["comprehension_accuracy"] == 1.0

    def test_reader_vs_cohort_values(self):
        groups = reader_vs_cohort_values(_tidy_fixations(), "p1", MEASURES["fix_dur"])
        assert set(groups) == {"This reader", "Cohort"}
        np.testing.assert_array_equal(
            groups["This reader"], np.array([100.0, 150.0, 130.0])
        )
        np.testing.assert_array_equal(groups["Cohort"], np.array([200.0, 180.0]))

    def test_reader_vs_cohort_omits_an_empty_side(self):
        groups = reader_vs_cohort_values(
            _tidy_fixations(), "nobody", MEASURES["fix_dur"]
        )
        assert set(groups) == {"Cohort"}
        assert groups["Cohort"].size == 5

    def test_reader_summary_exact(self):
        s = reader_summary(_tidy_words(), _tidy_fixations(), "p1")
        assert s["participant_id"] == "p1"
        assert s["n_trials"] == 1
        assert s["n_fixations"] == 3
        assert s["mean_fixation_ms"] == pytest.approx(380 / 3)
        assert s["mean_saccade_px"] == pytest.approx(2.0)  # mean(3, 1); NaN skipped
        assert s["regression_rate"] == pytest.approx(1 / 3)
        assert s["skip_rate"] == pytest.approx(1 / 3)
        # 3 words over a 380 ms span (0 → 250 + 130).
        assert s["wpm"] == pytest.approx(3 / (380 / 60000.0))

    def test_reading_time_falls_back_to_summed_durations(self):
        fx = _tidy_fixations().drop(columns=["timestamp_ms"])
        s = reader_summary(_tidy_words(), fx, "p1")
        assert s["wpm"] == pytest.approx(3 / (380 / 60000.0))  # 100+150+130 = 380

    def test_cohort_summary_table_one_row_per_reader(self):
        t = cohort_summary_table(_tidy_words(), _tidy_fixations())
        assert list(t["participant_id"]) == ["p1", "p2"]
        assert list(t["n_fixations"]) == [3, 2]
        row = t[t.participant_id == "p1"].iloc[0]
        assert row["wpm"] == pytest.approx(3 / (380 / 60000.0))

    def test_reader_summary_for_a_reader_with_no_fixations(self):
        # p3 has word rows but no fixation stream: only the words-derived stat
        # is reported, and nothing is faked for the fixation-derived ones.
        assert reader_summary(_tidy_words(), _tidy_fixations(), "p3") == {
            "participant_id": "p3",
            "skip_rate": 0.0,
        }

    def test_cohort_summary_reader_list_comes_from_the_fixations(self):
        # The reader list is taken from the FIRST frame carrying participant_id
        # (fixations, then words), so p3 — words-only — gets no row at all,
        # even though `reader_summary` happily builds one for it.
        table = cohort_summary_table(_tidy_words(), _tidy_fixations())
        assert list(table["participant_id"]) == ["p1", "p2"]
        # With no fixations at all the list falls back to the words frame.
        words_only = cohort_summary_table(_tidy_words(), pd.DataFrame())
        assert list(words_only["participant_id"]) == ["p1", "p2", "p3"]
        assert list(words_only["skip_rate"]) == pytest.approx([1 / 3, 0.0, 0.0])
        assert "n_fixations" not in words_only.columns

    def test_cohort_summary_table_participant_filter(self):
        t = cohort_summary_table(_tidy_words(), _tidy_fixations(), participants=["p2"])
        assert list(t["participant_id"]) == ["p2"]
        assert cohort_summary_table(
            _tidy_words(), _tidy_fixations(), participants=["nobody"]
        ).empty

    def test_metric_over_time_by_fixation_index(self):
        out = metric_over_time(_tidy_fixations(), MEASURES["fix_dur"])
        assert list(out["x"]) == [1, 2, 3]
        assert list(out["value"]) == [150.0, 165.0, 130.0]
        assert list(out["n"]) == [2, 2, 1]
        assert list(out["sem"]) == pytest.approx([50.0, 15.0, 0.0])

    def test_metric_over_time_filters_and_switches_axis(self):
        out = metric_over_time(
            _tidy_fixations(), MEASURES["fix_dur"], participant_id="p2"
        )
        assert list(out["x"]) == [1, 2]
        assert list(out["value"]) == [200.0, 180.0]
        by_time = metric_over_time(
            _tidy_fixations(), MEASURES["fix_dur"], by="timestamp_ms"
        )
        assert list(by_time["x"]) == [0.0, 100.0, 120.0, 250.0]
        assert list(by_time["value"]) == [150.0, 150.0, 180.0, 130.0]

    def test_metric_over_time_missing_axis_column(self):
        out = metric_over_time(_tidy_fixations(), MEASURES["fix_dur"], by="nope")
        assert out.empty and list(out.columns) == ["x", "value", "sem", "n"]

    def test_saccade_vs_duration_drops_nan_rows(self):
        out = saccade_vs_duration(_tidy_fixations())
        assert list(out["duration_ms"]) == [150.0, 130.0, 180.0]
        assert list(out["saccade_amplitude"]) == [3.0, 1.0, 4.0]
        one = saccade_vs_duration(_tidy_fixations(), participant_id="p1")
        assert len(one) == 2

    def test_saccade_vs_duration_missing_columns(self):
        out = saccade_vs_duration(_tidy_fixations().drop(columns=["saccade_amplitude"]))
        assert out.empty
        assert list(out.columns) == ["duration_ms", "saccade_amplitude"]

    def test_progressive_regressive_counts(self):
        out = progressive_regressive_counts(_tidy_fixations())
        assert list(out["trial_id"]) == ["t1", "t2"]
        assert list(out["regressive"]) == [1, 0]
        assert list(out["progressive"]) == [2, 2]
        assert list(out["regression_share"]) == pytest.approx([1 / 3, 0.0])
        one = progressive_regressive_counts(_tidy_fixations(), participant_id="p2")
        assert list(one["trial_id"]) == ["t2"]

    def test_progressive_regressive_requires_is_regression(self):
        out = progressive_regressive_counts(
            _tidy_fixations().drop(columns=["is_regression"])
        )
        assert out.empty
        assert list(out.columns) == [
            "trial_id",
            "progressive",
            "regressive",
            "regression_share",
        ]

    def test_per_participant_trend(self):
        out = per_participant_trend(_trend_frame(), "duration_ms")
        assert list(out["participant_id"]) == ["p1", "p1", "p2"]
        assert list(out["trial_index"]) == [1, 2, 1]
        assert list(out["value"]) == [15.0, 40.0, 150.0]

    def test_per_participant_trend_missing_columns(self):
        out = per_participant_trend(_trend_frame().drop(columns=["trial_index"]), "x")
        assert out.empty
        assert list(out.columns) == ["participant_id", "trial_index", "value"]


class TestEnsureFixationEnrichment:
    def test_derives_regression_and_amplitude(self):
        fx = _tidy_fixations().drop(columns=["is_regression", "saccade_amplitude"])
        out = ensure_fixation_enrichment(fx, _tidy_words())
        # p1 goes word 0 → 1 → 0: the third fixation is behind the running max.
        assert list(out["is_regression"]) == [False, False, True, False, False]
        # Amplitude = |Δx| along a flat line; the first fixation of a trial has none.
        amps = out["saccade_amplitude"].to_numpy()
        assert np.isnan(amps[0]) and np.isnan(amps[3])
        assert list(amps[[1, 2, 4]]) == pytest.approx([21.0, 19.0, 24.0])

    def test_passthrough_when_already_enriched_or_unassignable(self):
        already = _tidy_fixations()
        assert ensure_fixation_enrichment(already, _tidy_words()) is already
        no_words = _tidy_fixations().drop(columns=["is_regression", "word_id"])
        assert ensure_fixation_enrichment(no_words, _tidy_words()) is no_words
        empty = pd.DataFrame()
        assert ensure_fixation_enrichment(empty, _tidy_words()) is empty


class TestLandingPositions:
    def test_from_precomputed_first_fix_x(self):
        # p1: word 0 lands at 2 px into a 10 px box → 0.2; word 1 at 23 − 20 → 0.3.
        # Word 2 is flagged skipped, so it contributes nothing.
        fracs = landing_positions(_tidy_words(), participant_id="p1")
        assert list(fracs) == pytest.approx([0.2, 0.3])

    def test_as_pixels(self):
        px = landing_positions(_tidy_words(), participant_id="p1", as_fraction=False)
        assert list(px) == pytest.approx([2.0, 3.0])

    def test_derived_from_fixations_matches_precomputed(self):
        w = _tidy_words().drop(columns=["first_fix_x"])
        derived = landing_positions(w, _tidy_fixations(), participant_id="p1")
        # The earliest fixation on each word: word 0 at x = 2 (not the later
        # revisit at x = 4), word 1 at x = 23.
        assert list(derived) == pytest.approx([0.2, 0.3])

    def test_pools_every_reader_when_unfiltered(self):
        # No participant filter → every non-skipped word of all three readers,
        # in row order: p1 (2, 3 px), p2 (1, 5, 4 px), p3 (3 px) over 10 px boxes.
        assert list(landing_positions(_tidy_words())) == pytest.approx(
            [0.2, 0.3, 0.1, 0.5, 0.4, 0.3]
        )

    def test_derived_ordering_falls_back_to_timestamp(self):
        w = _tidy_words().drop(columns=["first_fix_x"])
        fx = _tidy_fixations().drop(columns=["order_in_trial"])
        # Re-time p1 so the *revisit* of word 0 (x = 4) is now its earliest
        # fixation — the landing has to follow the clock, not the row order.
        fx["timestamp_ms"] = [250.0, 100.0, 0.0, 0.0, 120.0]
        assert list(landing_positions(w, fx, participant_id="p1")) == pytest.approx(
            [0.4, 0.3]
        )

    def test_clipped_to_the_box(self):
        w = _tidy_words().head(2).copy()
        w["first_fix_x"] = [-5.0, 400.0]
        assert list(landing_positions(w)) == [0.0, 1.0]

    def test_no_usable_source(self):
        w = _tidy_words().drop(columns=["first_fix_x"])
        assert landing_positions(w).size == 0
        assert landing_positions(pd.DataFrame(), pd.DataFrame()).size == 0


# -----------------------------------------------------------------------------
# Groups + group comparison
# -----------------------------------------------------------------------------


class TestGroupSelection:
    def test_group_mask_ands_columns_and_ors_values(self):
        w = _tidy_words()
        assert group_mask(w, {"difficulty_level": ["Adv"]}).sum() == 4  # p1 + p3
        assert group_mask(w, {"difficulty_level": ["Adv"], "text_id": ["A"]}).sum() == 3
        assert group_mask(w, {"text_id": ["A", "B"]}).sum() == 7
        assert group_mask(w, {}).all()  # empty spec → every row
        # Values are compared as strings, so a numeric column takes "0".
        assert group_mask(w, {"word_id": ["0"]}).sum() == 3
        # An unknown column (or an empty value list) is ignored, not fatal.
        assert group_mask(w, {"nope": ["x"]}).all()
        assert group_mask(w, {"text_id": []}).all()
        assert group_mask(pd.DataFrame(), {"text_id": ["A"]}).empty

    def test_apply_group(self):
        w = _tidy_words()
        assert len(apply_group(w, {"text_id": ["A"]})) == 6
        assert set(apply_group(w, {"difficulty_level": ["Ele"]})["participant_id"]) == {
            "p2"
        }
        assert len(apply_group(w, {})) == 7
        empty = pd.DataFrame()
        assert apply_group(empty, {"text_id": ["A"]}) is empty

    def test_two_group_values(self):
        groups = two_group_values(
            _tidy_fixations(),
            MEASURES["fix_dur"],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            label_a="Adv",
            label_b="Ele",
        )
        assert set(groups) == {"Adv", "Ele"}
        np.testing.assert_array_equal(groups["Adv"], np.array([100.0, 150.0, 130.0]))
        np.testing.assert_array_equal(groups["Ele"], np.array([200.0, 180.0]))

    def test_two_group_values_omits_an_empty_group(self):
        groups = two_group_values(
            _tidy_fixations(),
            MEASURES["fix_dur"],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Nope"]},
        )
        assert set(groups) == {"Group A"}

    def test_two_group_values_normalizes_within_reader(self):
        # Each group is z-scored inside itself, so the two readers' absolute
        # levels (p1 ≈ 127 ms, p2 = 190 ms) stop driving the comparison.
        groups = two_group_values(
            _tidy_fixations(),
            MEASURES["fix_dur"],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            normalize=True,
        )
        assert groups["Group A"].mean() == pytest.approx(0.0)
        assert groups["Group A"].std(ddof=1) == pytest.approx(1.0)
        assert sorted(groups["Group B"]) == pytest.approx(
            [-1 / np.sqrt(2), 1 / np.sqrt(2)]
        )


class TestGroupComparison:
    _SPEC_A = {"participant_id": ["p1"]}
    _SPEC_B = {"participant_id": ["p2"]}

    def test_group_word_difference(self):
        out = group_word_difference(
            _tidy_words(), "text_id", "A", MEASURES["tfd"], self._SPEC_A, self._SPEC_B
        )
        assert list(out["word_id"]) == [0, 1, 2]
        assert list(out["a"]) == pytest.approx([100.0, 300.0, np.nan], nan_ok=True)
        assert list(out["b"]) == [200.0, 500.0, 150.0]
        assert list(out["diff"]) == pytest.approx([-100.0, -200.0, np.nan], nan_ok=True)
        assert list(out["n_a"]) == [1, 1, 0]
        assert list(out["n_b"]) == [1, 1, 1]
        # Word 2 has no A reader → below the guard even at min_readers=1.
        assert list(out["enough"]) == [True, True, False]
        assert list(out["word_text"]) == ["the", "cat", ""]

    def test_group_word_difference_guard(self):
        out = group_word_difference(
            _tidy_words(),
            "text_id",
            "A",
            MEASURES["tfd"],
            self._SPEC_A,
            self._SPEC_B,
            min_readers=2,
        )
        assert not out["enough"].any()  # one reader per group, guard wants two

    def test_group_word_difference_empty(self):
        out = group_word_difference(
            _tidy_words(),
            "text_id",
            "A",
            MEASURES["tfd"],
            {"participant_id": ["nobody"]},
            {"participant_id": ["also-nobody"]},
        )
        assert out.empty
        assert list(out.columns) == [
            "word_id",
            "a",
            "b",
            "diff",
            "n_a",
            "n_b",
            "enough",
            "word_text",
        ]

    def test_two_group_word_profiles(self):
        out = two_group_word_profiles(
            _tidy_words(),
            "text_id",
            "A",
            MEASURES["tfd"],
            self._SPEC_A,
            self._SPEC_B,
            label_a="P1",
            label_b="P2",
        )
        assert list(out.columns) == ["group", "word_id", "value"]
        assert list(out["group"]) == ["P1", "P1", "P2", "P2", "P2"]
        assert list(out["word_id"]) == [0, 1, 0, 1, 2]
        assert list(out["value"]) == [100.0, 300.0, 200.0, 500.0, 150.0]

    def test_two_group_word_profiles_empty(self):
        out = two_group_word_profiles(
            _tidy_words(),
            "text_id",
            "A",
            MEASURES["tfd"],
            {"participant_id": ["nobody"]},
            {"participant_id": ["also-nobody"]},
        )
        assert out.empty and list(out.columns) == ["group", "word_id", "value"]

    def test_paired_group_summary_values_and_error_bars(self):
        out = paired_group_summary(
            _tidy_fixations(),
            [MEASURES["fix_dur"]],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            spread="SEM",
            label_a="Adv",
            label_b="Ele",
        )
        assert list(out["measure"]) == ["Fixation duration", "Fixation duration"]
        assert list(out["group"]) == ["Adv", "Ele"]
        assert list(out["value"]) == pytest.approx([380 / 3, 190.0])
        assert list(out["n"]) == [3, 2]
        sem_adv = float(np.std([100.0, 150.0, 130.0], ddof=1)) / np.sqrt(3)
        assert out.loc[0, "err_lo"] == pytest.approx(sem_adv)
        assert out.loc[0, "err_hi"] == pytest.approx(sem_adv)
        assert out.loc[1, "err_hi"] == pytest.approx(10.0)  # sd(200,180)/sqrt(2)

    def test_paired_group_summary_routes_each_measure_to_its_frame(self):
        out = paired_group_summary(
            pd.DataFrame(),
            [MEASURES["tfd"], MEASURES["fix_dur"]],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            words=_tidy_words(),
            fixations=_tidy_fixations(),
        )
        tfd = out[out.measure == "Total fixation duration — TFD"]
        # Adv words = p1 (100, 300) + p3 (900) → mean 433.33; Ele = p2's three.
        assert list(tfd["value"]) == pytest.approx([1300 / 3, 850 / 3])
        assert list(tfd["n"]) == [3, 3]
        fix = out[out.measure == "Fixation duration"]
        assert list(fix["value"]) == pytest.approx([380 / 3, 190.0])

    def test_paired_group_summary_skips_a_measure_with_no_frame(self):
        out = paired_group_summary(
            _tidy_fixations(),
            [MEASURES["tfd"], MEASURES["fix_dur"]],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            words=_tidy_words(),
            fixations=None,
        )
        # Once either frame is supplied, `frame` stops being a fallback: the
        # fixation-level measure has no source and is dropped rather than being
        # silently read off the words frame.
        assert list(out["measure"]) == ["Total fixation duration — TFD"] * 2
        assert list(out["value"]) == pytest.approx([1300 / 3, 850 / 3])

    def test_paired_group_summary_error_bars_never_negative(self):
        # mean + IQR on right-skewed data can put the mean outside [Q1, Q3];
        # a negative Plotly error length would render in the wrong direction.
        frame = pd.DataFrame(
            {
                "participant_id": ["p"] * 10,
                "difficulty_level": ["Adv"] * 10,
                "duration_ms": [0.0] * 9 + [1000.0],
            }
        )
        out = paired_group_summary(
            frame,
            [MEASURES["fix_dur"]],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Adv"]},
            spread="IQR",
        )
        assert (out["err_lo"] >= 0).all() and (out["err_hi"] >= 0).all()

    def test_group_effect_size(self):
        a = np.array([1.0, 2, 3, 4, 5])
        b = np.array([3.0, 4, 5, 6, 7])
        res = group_effect_size(a, b, test="t-test")
        assert res["mean_a"] == 3.0 and res["mean_b"] == 5.0
        assert res["mean_diff"] == pytest.approx(-2.0)
        assert res["n_a"] == 5 and res["n_b"] == 5
        # Both groups have sd = sqrt(2.5) → pooled sd = sqrt(2.5), d = -2/1.5811.
        assert res["cohen_d"] == pytest.approx(-2.0 / np.sqrt(2.5))
        assert 0 <= res["p_value"] <= 1
        res_mw = group_effect_size(a, b, test="Mann–Whitney")
        assert res_mw["test"] == "Mann–Whitney"
        assert 0 <= res_mw["p_value"] <= 1

    def test_group_effect_size_ignores_nans(self):
        res = group_effect_size(
            np.array([1.0, 2, 3, 4, 5, np.nan]), np.array([3.0, 4, 5, 6, 7])
        )
        assert res["n_a"] == 5 and res["mean_a"] == 3.0

    def test_group_effect_size_tiny_and_empty_groups(self):
        res = group_effect_size(np.array([1.0]), np.array([2.0]))
        assert np.isnan(res["cohen_d"]) and np.isnan(res["p_value"])
        assert res["mean_diff"] == pytest.approx(-1.0)
        empty = group_effect_size(np.array([]), np.array([]))
        assert empty["n_a"] == 0 and empty["n_b"] == 0
        assert np.isnan(empty["mean_a"]) and np.isnan(empty["mean_diff"])

    def test_cohen_d_nan_when_pooled_sd_zero(self):
        # Both groups internally constant but means differ → d is undefined;
        # 0.0 would falsely read as "no effect" next to a non-zero mean diff.
        res = group_effect_size(np.array([1.0, 1, 1]), np.array([2.0, 2, 2]))
        assert res["mean_diff"] == -1.0
        assert np.isnan(res["cohen_d"])
