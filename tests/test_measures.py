"""Tests for scanpath_studio.measures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio.measures import (
    assign_fixations_to_words,
    classify_saccades,
    compute_per_word_measures,
    enrich_fixations,
)


@pytest.fixture
def four_word_layout():
    """Single trial, 4 words laid out horizontally."""
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 4,
            "trial_id": ["t1"] * 4,
            "word_id": [1, 2, 3, 4],
            "text": ["the", "cat", "sat", "down"],
            "x": [100, 200, 300, 400],
            "y": [50, 50, 50, 50],
            "width": [80, 80, 80, 80],
            "height": [40, 40, 40, 40],
            "line_idx": [1, 1, 1, 1],
        }
    )


def _make_fixations(rows: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["x", "y", "duration_ms", "timestamp_ms"])
    df["participant_id"] = "p1"
    df["trial_id"] = "t1"
    return df


class TestAssignFixationsToWords:
    def test_box_containment(self, four_word_layout):
        # Fixation at x=140 falls inside word 1 (100-180); x=240 inside word 2.
        fix = _make_fixations(
            [(140, 70, 200, 0), (240, 70, 250, 250), (340, 70, 180, 500)]
        )
        assigned = assign_fixations_to_words(fix, four_word_layout, overwrite=True)
        assert list(assigned["word_id"]) == [1.0, 2.0, 3.0]

    def test_nearest_fallback(self, four_word_layout):
        # Out-of-box but within 50 px of word 2 (center=240, y=70).
        fix = _make_fixations([(245, 110, 200, 0)])
        assigned = assign_fixations_to_words(
            fix, four_word_layout, overwrite=True, nearest_within_px=80
        )
        assert assigned["word_id"].iloc[0] == 2.0

    def test_far_fixation_unassigned(self, four_word_layout):
        fix = _make_fixations([(1000, 1000, 200, 0)])
        assigned = assign_fixations_to_words(
            fix, four_word_layout, overwrite=True, nearest_within_px=20
        )
        assert pd.isna(assigned["word_id"].iloc[0])


class TestEnrichFixations:
    def test_saccade_amplitude(self, four_word_layout):
        fix = _make_fixations(
            [(140, 70, 200, 0), (240, 70, 250, 200), (440, 70, 180, 450)]
        )
        fix = assign_fixations_to_words(fix, four_word_layout, overwrite=True)
        enriched = enrich_fixations(fix, four_word_layout)
        amps = enriched["saccade_amplitude"].tolist()
        assert pd.isna(amps[0])  # first fixation has no predecessor
        assert amps[1] == pytest.approx(100.0)
        assert amps[2] == pytest.approx(200.0)

    def test_is_regression(self, four_word_layout):
        # forward, forward, back to word 1 (regression)
        fix = _make_fixations(
            [(140, 70, 200, 0), (240, 70, 250, 200), (140, 70, 180, 450)]
        )
        fix = assign_fixations_to_words(fix, four_word_layout, overwrite=True)
        enriched = enrich_fixations(fix, four_word_layout)
        assert list(enriched["is_regression"]) == [False, False, True]


@pytest.fixture
def two_line_layout():
    """Single trial, 6 words on 2 lines (3 per line) — enough to exercise every
    reading-saccade class (return sweep needs a line change)."""
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 6,
            "trial_id": ["t1"] * 6,
            "word_id": [1, 2, 3, 4, 5, 6],
            "text": ["the", "cat", "sat", "on", "the", "mat"],
            "x": [100, 200, 300, 100, 200, 300],
            "y": [50, 50, 50, 150, 150, 150],
            "width": [80, 80, 80, 80, 80, 80],
            "height": [40, 40, 40, 40, 40, 40],
            "line_idx": [1, 1, 1, 2, 2, 2],
        }
    )


class TestClassifySaccades:
    def test_all_reading_classes(self, two_line_layout):
        # word1 → word2 → word3 (forward, forward), sweep down to word4
        # (return sweep), refixate word4 (refixation), skip to word6 (skip),
        # regress back to word4 (regression), end on word4 (no outgoing saccade).
        fix = _make_fixations(
            [
                (140, 70, 200, 0),  # word1  → forward
                (240, 70, 200, 200),  # word2  → forward
                (340, 70, 200, 400),  # word3  → return sweep (to line 2)
                (140, 170, 200, 600),  # word4  → refixation
                (140, 170, 200, 800),  # word4  → skip (to word6)
                (340, 170, 200, 1000),  # word6  → regression (back to word4)
                (140, 170, 200, 1200),  # word4  → None (last fixation)
            ]
        )
        fix = assign_fixations_to_words(fix, two_line_layout, overwrite=True)
        cls = classify_saccades(fix, two_line_layout)
        # Align to reading order (the fixtures are already in timestamp order).
        ordered = cls.reindex(fix.sort_values("timestamp_ms").index).tolist()
        assert ordered == [
            "forward",
            "forward",
            "return_sweep",
            "refixation",
            "skip",
            "regression",
            None,
        ]

    def test_out_of_text_endpoint_is_other(self, two_line_layout):
        # The middle fixation lands far outside every box (word_id NaN), so the
        # saccades touching it can't be classified → "other"; the last fixation
        # still has no outgoing saccade → None.
        fix = _make_fixations(
            [
                (140, 70, 200, 0),  # word1 → segment to an off-text point
                (5000, 5000, 200, 200),  # off-text → segment to word2
                (240, 70, 200, 400),  # word2 → None
            ]
        )
        fix = assign_fixations_to_words(fix, two_line_layout, overwrite=True)
        cls = classify_saccades(fix, two_line_layout)
        ordered = cls.reindex(fix.sort_values("timestamp_ms").index).tolist()
        assert ordered == ["other", "other", None]

    def test_single_fixation_has_no_saccade(self, two_line_layout):
        fix = _make_fixations([(140, 70, 200, 0)])
        fix = assign_fixations_to_words(fix, two_line_layout, overwrite=True)
        cls = classify_saccades(fix, two_line_layout)
        assert cls.tolist() == [None]

    def test_empty_frame(self, two_line_layout):
        empty = _make_fixations([]).iloc[0:0]
        cls = classify_saccades(empty, two_line_layout)
        assert cls.empty

    def test_aligned_to_input_index(self, two_line_layout):
        # A shuffled (non-monotonic) index must round-trip: the result is aligned
        # to fixations.index, not to reading order.
        fix = _make_fixations(
            [
                (240, 70, 200, 200),  # word2, ts=200
                (140, 70, 200, 0),  # word1, ts=0 (earlier, but row 1)
                (340, 70, 200, 400),  # word3, ts=400
            ]
        )
        fix = assign_fixations_to_words(fix, two_line_layout, overwrite=True)
        cls = classify_saccades(fix, two_line_layout)
        # Reading order is word1(ts0) → word2(ts200) → word3(ts400): forward,
        # forward, then None on the last. Row 0 is word2 (a forward), row 1 is
        # word1 (a forward), row 2 is word3 (the last → None).
        assert cls.iloc[2] is None
        assert cls.iloc[0] == "forward"
        assert cls.iloc[1] == "forward"


class TestComputePerWordMeasures:
    def test_basic_first_pass(self, four_word_layout):
        # Read words 1,2,3,4 left-to-right, one fixation each
        fix = _make_fixations(
            [
                (140, 70, 200, 0),
                (240, 70, 250, 200),
                (340, 70, 180, 450),
                (440, 70, 220, 630),
            ]
        )
        out = compute_per_word_measures(fix, four_word_layout)
        ffd = dict(zip(out["word_id"], out["first_fixation_ms"]))
        assert ffd[1] == 200
        assert ffd[4] == 220
        # No skips since each word got a first-pass fixation
        assert (~out["skip_flag"]).all()
        # No regressions
        assert (~out["regression_in_flag"]).all()
        assert (~out["regression_out_flag"]).all()
        # n_fixations all 1
        assert (out["n_fixations"] == 1).all()

    def test_skip_flag(self, four_word_layout):
        # Read only words 1 and 3 (skipping 2 and 4)
        fix = _make_fixations([(140, 70, 200, 0), (340, 70, 250, 200)])
        out = compute_per_word_measures(fix, four_word_layout).sort_values("word_id")
        skipped = dict(zip(out["word_id"], out["skip_flag"]))
        assert skipped[1] is False or skipped[1] == False  # noqa: E712
        assert skipped[2] is True or skipped[2] == True  # noqa: E712
        assert skipped[3] is False or skipped[3] == False  # noqa: E712
        assert skipped[4] is True or skipped[4] == True  # noqa: E712

    def test_gaze_duration_multiple_fixations(self, four_word_layout):
        # Two fixations on word 1, then move to word 2 — gaze duration on
        # word 1 should be sum of those two.
        fix = _make_fixations(
            [
                (110, 70, 100, 0),
                (150, 70, 120, 100),
                (240, 70, 200, 220),
            ]
        )
        out = compute_per_word_measures(fix, four_word_layout)
        row1 = out[out["word_id"] == 1].iloc[0]
        assert row1["first_pass_gaze_duration_ms"] == 220
        assert row1["total_fixation_duration_ms"] == 220
        assert row1["n_fixations"] == 2

    def test_regression_path(self, four_word_layout):
        # Read w1, w2, then regress back to w1, then re-fixate w2, then go to w3.
        # Under DataViewer's regression-path definition (Vasishth/Inhoff):
        #   RPD(w2) = sum of fixation durations from first entry to w2 until
        #             the first fixation in a later word, INCLUDING any
        #             regressions to earlier words during that window.
        #   = 250 (w2 first pass) + 180 (regression to w1) + 150 (w2 re-fix) = 580
        fix = _make_fixations(
            [
                (140, 70, 200, 0),  # w1
                (240, 70, 250, 200),  # w2 first pass
                (140, 70, 180, 450),  # regression to w1
                (240, 70, 150, 630),  # back to w2
                (340, 70, 200, 780),  # w3 — first fixation past w2, closes RPD(w2)
            ]
        )
        out = compute_per_word_measures(fix, four_word_layout)
        row2 = out[out["word_id"] == 2].iloc[0]
        assert row2["first_pass_gaze_duration_ms"] == 250
        assert row2["regression_path_duration_ms"] == 580
        # Total fixation duration on word 2 = 250 + 150
        assert row2["total_fixation_duration_ms"] == 400
        # regression_in_flag on word 1: a fixation on w1 followed a fixation on
        # a later word (w2), so w1 has a regression-in.
        row1 = out[out["word_id"] == 1].iloc[0]
        assert bool(row1["regression_in_flag"]) is True
        # And w2 has a regression-out (we left w2 going backward to w1).
        assert bool(row2["regression_out_flag"]) is True

    def test_preserves_existing_eyelink_metrics(self, four_word_layout):
        # If words already has IA-exported values, those should win.
        four_word_layout["first_fixation_ms"] = [999, 888, 777, 666]
        four_word_layout["total_fixation_duration_ms"] = [1, 2, 3, 4]
        fix = _make_fixations([(140, 70, 200, 0), (240, 70, 250, 200)])
        out = compute_per_word_measures(fix, four_word_layout)
        # Existing values preserved
        assert out.set_index("word_id").loc[1, "first_fixation_ms"] == 999
        assert out.set_index("word_id").loc[2, "total_fixation_duration_ms"] == 2

    def test_empty_fixations(self, four_word_layout):
        empty = pd.DataFrame(
            columns=[
                "x",
                "y",
                "duration_ms",
                "timestamp_ms",
                "participant_id",
                "trial_id",
            ]
        )
        out = compute_per_word_measures(empty, four_word_layout)
        # With no fixations, all words skipped
        assert out["skip_flag"].all()
        assert (out["n_fixations"] == 0).all()


class TestSaccadeAmplitudePreserved:
    def test_existing_saccade_amplitude_kept(self, four_word_layout):
        fix = _make_fixations([(140, 70, 200, 0), (240, 70, 250, 200)])
        fix["saccade_amplitude"] = [42.0, np.nan]
        fix = assign_fixations_to_words(fix, four_word_layout, overwrite=True)
        enriched = enrich_fixations(fix, four_word_layout)
        assert enriched["saccade_amplitude"].iloc[0] == 42.0
        # NaN gets filled from x,y diff
        assert enriched["saccade_amplitude"].iloc[1] == pytest.approx(100.0)
