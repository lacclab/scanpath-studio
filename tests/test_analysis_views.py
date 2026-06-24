"""Unit + smoke tests for the question-oriented Corpus Analysis views (AN-1…28).

Pure aggregation helpers (``aggregation.py``) get small hand-built frames where
the answer is obvious, plus a pass over the bundled demo (3 pid × 2 articles) so
the per-view aggregation + figure builders are exercised end to end against real
data (the implementation convention's "smoke test per figure").
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import scanpath_studio.plots as plots
from scanpath_studio.aggregation import (
    MEASURES,
    aggregate_value,
    available_features,
    available_measures,
    bootstrap_ci,
    cohort_summary_table,
    cohort_word_profile,
    ensure_fixation_enrichment,
    group_effect_size,
    group_mask,
    group_word_difference,
    landing_positions,
    metric_over_time,
    paired_group_summary,
    per_participant_trend,
    per_reader_word_measure,
    progressive_regressive_counts,
    reader_summary,
    reader_vs_cohort_values,
    saccade_vs_duration,
    spread_bounds,
    two_group_values,
    two_group_word_profiles,
    word_box_aggregate,
    word_measure_vs_feature,
    word_rate_profile,
)

# -----------------------------------------------------------------------------
# Tiny hand-built frames (unit tests)
# -----------------------------------------------------------------------------


def _words():
    # Text "A": 2 words, 2 readers (one Adv, one Ele). Word 1 is harder (longer
    # TFD) and more skipped by reader p2.
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t1", "t2", "t2"],
            "text_id": ["A", "A", "A", "A"],
            "difficulty_level": ["Adv", "Adv", "Ele", "Ele"],
            "word_id": [0, 1, 0, 1],
            "x": [0, 10, 0, 10],
            "y": [0, 0, 0, 0],
            "width": [10, 10, 10, 10],
            "height": [10, 10, 10, 10],
            "text": ["the", "cat", "the", "cat"],
            "total_fixation_duration_ms": [100, 300, 200, 500],
            "first_fixation_ms": [80, 120, 90, 140],
            "n_fixations": [1, 2, 1, 3],
            "skip_flag": [False, False, True, False],
            "regression_in_flag": [False, True, False, True],
            "regression_out_flag": [False, False, False, True],
            "gpt2_surprisal": [2.0, 8.0, 2.0, 8.0],
            "word_length": [3, 3, 3, 3],
            "universal_pos": ["DET", "NOUN", "DET", "NOUN"],
            "first_fix_x": [2.0, 15.0, 1.0, 18.0],
        }
    )


def _fix():
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t1", "t1", "t2", "t2"],
            "difficulty_level": ["Adv", "Adv", "Adv", "Ele", "Ele"],
            "order_in_trial": [1, 2, 3, 1, 2],
            "timestamp_ms": [0, 100, 250, 0, 120],
            "duration_ms": [100, 150, 130, 200, 180],
            "saccade_amplitude": [np.nan, 3.0, 1.0, np.nan, 4.0],
            "word_id": [0, 1, 0, 0, 1],
            "x": [2.0, 15.0, 3.0, 1.0, 18.0],
            "y": [0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )


class TestPrimitives:
    def test_aggregate_value(self):
        assert aggregate_value([1, 2, 3], "mean") == 2.0
        assert aggregate_value([1, 2, 3, 4], "median") == 2.5
        assert aggregate_value([1, 2, 3], "sum") == 6.0
        assert np.isnan(aggregate_value([np.nan], "mean"))

    def test_spread_bounds(self):
        vals = np.array([10.0, 20.0, 30.0])
        lo, hi = spread_bounds(vals, 20.0, "IQR")
        assert lo == 15.0 and hi == 25.0
        lo, hi = spread_bounds(vals, 20.0, "SD")
        assert lo < 20.0 < hi
        lo, hi = spread_bounds(vals, 20.0, "SEM")
        assert hi - 20.0 < np.std(vals, ddof=1)  # SEM band narrower than SD

    def test_bootstrap_ci_deterministic(self):
        vals = np.arange(50, dtype=float)
        lo1, hi1 = bootstrap_ci(vals, seed=0)
        lo2, hi2 = bootstrap_ci(vals, seed=0)
        assert (lo1, hi1) == (lo2, hi2)  # seeded → reproducible
        assert lo1 < np.mean(vals) < hi1

    def test_group_mask_and_features(self):
        w = _words()
        m = group_mask(w, {"difficulty_level": ["Adv"]})
        assert m.sum() == 2
        # AND across columns; isin within a column.
        m2 = group_mask(w, {"difficulty_level": ["Adv", "Ele"], "word_id": ["0"]})
        assert m2.sum() == 2
        assert group_mask(w, {}).all()  # empty spec → all rows

    def test_available_measures(self):
        keys = {m.key for m in available_measures(_words(), _fix())}
        assert {"tfd", "ffd", "skip", "fix_dur", "sacc_amp"} <= keys
        per_word = {
            m.key for m in available_measures(_words(), _fix(), per_word_only=True)
        }
        assert "fix_dur" not in per_word and "tfd" in per_word


class TestPerText:
    def test_per_reader_word_measure(self):
        out = per_reader_word_measure(_words(), "text_id", "A", MEASURES["tfd"])
        assert set(out.columns) >= {"participant_id", "word_id", "value"}
        assert len(out) == 4  # 2 readers × 2 words
        v = out[(out.participant_id == "p2") & (out.word_id == 1)]["value"].iloc[0]
        assert v == 500.0

    def test_cohort_word_profile_band_and_guard(self):
        out = cohort_word_profile(
            _words(), "text_id", "A", MEASURES["tfd"], spread="SD"
        )
        assert list(out["word_id"]) == [0, 1]
        w0 = out[out.word_id == 0].iloc[0]
        assert w0["value"] == 150.0  # mean(100, 200)
        assert w0["lo"] <= w0["value"] <= w0["hi"]
        assert (out["n"] == 2).all()
        # Min-readers guard.
        guarded = cohort_word_profile(
            _words(), "text_id", "A", MEASURES["tfd"], min_readers=3
        )
        assert (~guarded["enough"]).all()

    def test_normalize_within_reader(self):
        out = per_reader_word_measure(
            _words(), "text_id", "A", MEASURES["tfd"], normalize=True
        )
        # Each reader z-scored → mean ~0 within reader.
        for _, grp in out.groupby("participant_id"):
            assert abs(grp["value"].mean()) < 1e-9

    def test_word_box_aggregate(self):
        out = word_box_aggregate(_words(), "text_id", "A", MEASURES["skip"])
        assert {"x", "y", "width", "height", "value"} <= set(out.columns)
        # Word 0 skipped by p2 only → rate 0.5.
        assert out[out.word_id == 0]["value"].iloc[0] == 0.5

    def test_word_measure_vs_feature(self):
        out = word_measure_vs_feature(
            _words(), "text_id", "A", MEASURES["tfd"], "gpt2_surprisal"
        )
        assert {"word_id", "value", "feature"} <= set(out.columns)
        assert len(out) == 2

    def test_word_rate_profile(self):
        out = word_rate_profile(_words(), "text_id", "A")
        assert {"skip_rate", "regression_in_rate"} <= set(out.columns)
        assert out[out.word_id == 0]["skip_rate"].iloc[0] == 0.5
        assert out[out.word_id == 1]["regression_in_rate"].iloc[0] == 1.0


class TestPerReader:
    def test_reader_vs_cohort(self):
        groups = reader_vs_cohort_values(_fix(), "p1", MEASURES["fix_dur"])
        assert set(groups) == {"This reader", "Cohort"}
        assert groups["This reader"].size == 3 and groups["Cohort"].size == 2

    def test_reader_summary(self):
        s = reader_summary(_words(), _fix(), "p1")
        assert s["n_fixations"] == 3
        assert s["mean_fixation_ms"] == pytest.approx((100 + 150 + 130) / 3)

    def test_cohort_summary_table(self):
        t = cohort_summary_table(_words(), _fix())
        assert len(t) == 2 and "participant_id" in t.columns

    def test_metric_over_time(self):
        out = metric_over_time(_fix(), MEASURES["fix_dur"], participant_id="p1")
        assert list(out["x"]) == [1, 2, 3]

    def test_saccade_vs_duration(self):
        out = saccade_vs_duration(_fix())
        assert set(out.columns) == {"duration_ms", "saccade_amplitude"}
        assert out["saccade_amplitude"].notna().all()  # NaNs dropped

    def test_progressive_regressive(self):
        fx = ensure_fixation_enrichment(_fix(), _words())
        out = progressive_regressive_counts(fx, participant_id="p1")
        assert "regressive" in out.columns and not out.empty

    def test_landing_positions_from_words_and_fixations(self):
        # first_fix_x present → fraction (first_fix_x - x)/width.
        fracs = landing_positions(_words(), participant_id="p1")
        assert fracs.size == 2 and ((fracs >= 0) & (fracs <= 1)).all()
        # Drop first_fix_x → derive from fixations.
        w = _words().drop(columns=["first_fix_x"])
        fracs2 = landing_positions(w, _fix(), participant_id="p1")
        assert fracs2.size >= 1 and ((fracs2 >= 0) & (fracs2 <= 1)).all()

    def test_per_participant_trend(self):
        f = _fix().copy()
        f["trial_index"] = [1, 1, 1, 1, 1]
        out = per_participant_trend(f, "duration_ms")
        assert {"participant_id", "trial_index", "value"} <= set(out.columns)


class TestGroupComparison:
    def test_two_group_values(self):
        groups = two_group_values(
            _fix(),
            MEASURES["fix_dur"],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            label_a="Adv",
            label_b="Ele",
        )
        assert set(groups) == {"Adv", "Ele"}

    def test_group_word_difference(self):
        out = group_word_difference(
            _words(),
            "text_id",
            "A",
            MEASURES["tfd"],
            {"participant_id": ["p1"]},
            {"participant_id": ["p2"]},
        )
        assert "diff" in out.columns
        # Word 1: p1=300, p2=500 → diff = -200.
        assert out[out.word_id == 1]["diff"].iloc[0] == -200.0

    def test_two_group_word_profiles(self):
        out = two_group_word_profiles(
            _words(),
            "text_id",
            "A",
            MEASURES["tfd"],
            {"participant_id": ["p1"]},
            {"participant_id": ["p2"]},
            label_a="P1",
            label_b="P2",
        )
        assert set(out["group"].unique()) == {"P1", "P2"}

    def test_paired_group_summary(self):
        out = paired_group_summary(
            _fix(),
            [MEASURES["fix_dur"], MEASURES["sacc_amp"]],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            words=_words(),
            fixations=_fix(),
        )
        assert set(out["measure"]) == {"Fixation duration", "Saccade amplitude"}
        assert {"value", "err_lo", "err_hi", "n"} <= set(out.columns)

    def test_group_effect_size(self):
        a = np.array([1.0, 2, 3, 4, 5])
        b = np.array([3.0, 4, 5, 6, 7])
        res = group_effect_size(a, b, test="t-test")
        assert res["mean_diff"] == pytest.approx(-2.0)
        assert res["cohen_d"] < 0
        assert 0 <= res["p_value"] <= 1
        res_mw = group_effect_size(a, b, test="Mann–Whitney")
        assert 0 <= res_mw["p_value"] <= 1

    def test_effect_size_handles_tiny_groups(self):
        res = group_effect_size(np.array([1.0]), np.array([2.0]))
        assert np.isnan(res["cohen_d"]) and np.isnan(res["p_value"])

    def test_cohen_d_nan_when_pooled_sd_zero(self):
        # Both groups internally constant but means differ → d undefined (NaN),
        # never a misleading 0.0 alongside a non-zero mean diff (review fix).
        res = group_effect_size(np.array([1.0, 1, 1]), np.array([2.0, 2, 2]))
        assert res["mean_diff"] == -1.0
        assert np.isnan(res["cohen_d"])

    def test_paired_summary_error_bars_non_negative(self):
        # mean + IQR on right-skewed data can put the mean outside [Q1, Q3];
        # the Plotly error lengths must still be ≥ 0 (review fix).
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
            agg="mean",
            spread="IQR",
        )
        assert (out["err_lo"] >= 0).all() and (out["err_hi"] >= 0).all()

    def test_sum_band_brackets_total(self):
        # SD/SEM of individuals is meaningless around a sum → bootstrap the total
        # so the band brackets it (review fix).
        vals = np.array([100.0, 200.0, 300.0])
        lo, hi = spread_bounds(vals, 600.0, "SD", agg="sum")
        assert lo <= 600.0 <= hi


class TestReviewRegressions:
    def test_feature_no_bogus_word_text_without_text_col(self):
        # Without a `text` column, word_text must not be backfilled with the
        # per-word reader count (review fix).
        w = _words().drop(columns=["text"])
        out = word_measure_vs_feature(
            w, "text_id", "A", MEASURES["tfd"], "gpt2_surprisal"
        )
        assert "word_text" not in out.columns or out["word_text"].eq("").all()

    def test_difference_word_text_backfilled_for_b_only_words(self):
        # p1 reads words 0,1; p2 reads words 0,1,2 → word 2 is B-only and its
        # word_text must be "" not NaN (review fix).
        w = pd.concat(
            [
                _words(),
                pd.DataFrame(
                    {
                        "participant_id": ["p2"],
                        "trial_id": ["t2"],
                        "text_id": ["A"],
                        "word_id": [2],
                        "x": [20],
                        "y": [0],
                        "width": [10],
                        "height": [10],
                        "text": ["sat"],
                        "total_fixation_duration_ms": [120],
                    }
                ),
            ],
            ignore_index=True,
        )
        out = group_word_difference(
            w,
            "text_id",
            "A",
            MEASURES["tfd"],
            {"participant_id": ["p1"]},
            {"participant_id": ["p2"]},
        )
        b_only = out[out.word_id == 2].iloc[0]
        assert b_only["word_text"] == ""


# -----------------------------------------------------------------------------
# Figure builders — smoke against the bundled demo (one figure per AN view)
# -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample():
    api = pytest.importorskip("scanpath_studio.api")
    words, fixations = api.load_sample_data()
    fixations = ensure_fixation_enrichment(fixations, words)
    text_col = next(
        (c for c in ("unique_text_id", "text_id", "unique_paragraph_id") if c in words),
        None,
    )
    text_id = words[text_col].iloc[0]
    pid = fixations["participant_id"].iloc[0]
    return words, fixations, text_col, text_id, pid


_FW = dict(canvas_width=700, base_font_size=12, font_family="Arial")


class TestAnalysisFigures:
    def test_small_multiples(self, sample):
        words, _, tc, tid, _ = sample
        per = per_reader_word_measure(words, tc, tid, MEASURES["tfd"])
        coh = cohort_word_profile(words, tc, tid, MEASURES["tfd"])[["word_id", "value"]]
        fig = plots.make_small_multiples_figure(
            per, measure_label="TFD (ms)", cohort=coh, **_FW
        )
        assert len(fig.data) >= 1

    def test_word_matrix_heatmap(self, sample):
        words, _, tc, tid, _ = sample
        per = per_reader_word_measure(words, tc, tid, MEASURES["tfd"])
        fig = plots.make_word_matrix_heatmap(
            per, row_col="participant_id", measure_label="TFD (ms)", **_FW
        )
        assert any(t.type == "heatmap" for t in fig.data)

    def test_word_profile(self, sample):
        words, _, tc, tid, _ = sample
        prof = cohort_word_profile(words, tc, tid, MEASURES["tfd"], spread="SD")
        fig = plots.make_word_profile_figure(
            {"Cohort": prof}, measure_label="TFD (ms)", **_FW
        )
        assert len(fig.data) >= 1

    def test_feature_scatter_numeric_and_categorical(self, sample):
        words, _, tc, tid, _ = sample
        feats = available_features(words)
        assert feats  # OneStop demo ships these
        for label, (col, cat) in feats.items():
            df = word_measure_vs_feature(words, tc, tid, MEASURES["tfd"], col)
            fig = plots.make_feature_scatter_figure(
                df,
                measure_label="TFD (ms)",
                feature_label=label,
                categorical=cat,
                **_FW,
            )
            assert len(fig.data) >= 1

    def test_word_rate(self, sample):
        words, _, tc, tid, _ = sample
        fig = plots.make_word_rate_figure(word_rate_profile(words, tc, tid), **_FW)
        assert any(t.type == "bar" for t in fig.data)

    def test_distribution_violin_box(self, sample):
        _, fix, _, _, pid = sample
        groups = reader_vs_cohort_values(fix, pid, MEASURES["fix_dur"])
        for kind in ("violin", "box"):
            fig = plots.make_distribution_figure(
                groups, metric_label="Fixation duration (ms)", kind=kind, **_FW
            )
            assert len(fig.data) >= 1

    def test_density_scatter(self, sample):
        _, fix, _, _, pid = sample
        df = saccade_vs_duration(fix, participant_id=pid)
        fig = plots.make_density_scatter_figure(
            df,
            x_col="duration_ms",
            y_col="saccade_amplitude",
            x_label="dur",
            y_label="amp",
            **_FW,
        )
        assert len(fig.data) >= 1

    def test_progression(self, sample):
        _, fix, _, _, pid = sample
        df = progressive_regressive_counts(fix, participant_id=pid)
        fig = plots.make_progression_figure(df, **_FW)
        assert len(fig.data) >= 1

    def test_landing_curve(self, sample):
        words, fix, _, _, pid = sample
        vals = landing_positions(words, fix, participant_id=pid)
        fig = plots.make_landing_curve_figure(vals, **_FW)
        assert len(fig.data) >= 1

    def test_paired_bars(self, sample):
        words, fix, _, _, _ = sample
        df = paired_group_summary(
            fix,
            [MEASURES["fix_dur"], MEASURES["sacc_amp"]],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            words=words,
            fixations=fix,
        )
        fig = plots.make_paired_bars_figure(df, **_FW)
        assert len(fig.data) >= 1

    def test_difference_profile(self, sample):
        words, _, tc, tid, _ = sample
        pids = list(pd.unique(words["participant_id"].astype(str)))[:2]
        diff = group_word_difference(
            words,
            tc,
            tid,
            MEASURES["tfd"],
            {"participant_id": [pids[0]]},
            {"participant_id": [pids[1]]},
        )
        fig = plots.make_difference_profile_figure(
            diff, measure_label="TFD (ms)", **_FW
        )
        assert len(fig.data) >= 1

    def test_no_data_fallbacks(self):
        empty = pd.DataFrame()
        for fig in (
            plots.make_small_multiples_figure(empty, measure_label="x", **_FW),
            plots.make_word_profile_figure({}, measure_label="x", **_FW),
            plots.make_difference_profile_figure(empty, measure_label="x", **_FW),
            plots.make_landing_curve_figure(np.array([]), **_FW),
        ):
            assert "no data" in (fig.layout.title.text or "").lower()
