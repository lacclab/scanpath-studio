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


class TestEyeLinkAmplitudesStayInDegrees:
    """BUG-25: EyeLink's two amplitude columns are degrees, and are two
    *different* saccades. Neither may land on the pixel-valued canonical
    ``saccade_amplitude``."""

    def test_normalization_gives_each_source_column_its_own_name(self):
        from scanpath_studio import data as data_mod

        raw = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "CURRENT_FIX_X": [140, 240],
                "CURRENT_FIX_Y": [70, 70],
                "CURRENT_FIX_DURATION": [200, 250],
                "CURRENT_FIX_START": [0, 200],
                "NEXT_SAC_AMPLITUDE": [1.9, 2.1],
                "PREVIOUS_SAC_AMPLITUDE": [0.8, 1.9],
            }
        )
        schema = data_mod.infer_fix_schema(raw)
        keep = data_mod.compute_keep_columns(schema, optional_sources=list(raw.columns))
        out = data_mod.normalize_fixations(raw, schema, keep_columns=keep)
        assert out["next_saccade_amplitude_deg"].tolist() == [1.9, 2.1]
        assert out["prev_saccade_amplitude_deg"].tolist() == [0.8, 1.9]
        # The px column must NOT have been claimed by either of them.
        assert "saccade_amplitude" not in out.columns

    def test_the_pixel_amplitude_is_computed_not_borrowed(self, four_word_layout):
        fix = _make_fixations([(140, 70, 200, 0), (240, 70, 250, 200)])
        fix["next_saccade_amplitude_deg"] = [1.9, 2.1]
        fix = assign_fixations_to_words(fix, four_word_layout, overwrite=True)
        enriched = enrich_fixations(fix, four_word_layout)
        # 100 px apart — the degree column must not leak into the px one.
        assert enriched["saccade_amplitude"].iloc[1] == pytest.approx(100.0)
        assert enriched["next_saccade_amplitude_deg"].iloc[1] == 2.1


class TestWithinWordLetterScale:
    """VAL-5: a letter is one *advance* wide, not ``width / len(text)``.

    The audit found the within-word measures and the between-word boundary
    disagreeing. ``measures.word_box_bounds`` had been corrected for BUG-11's
    trailing inter-word padding; the letter scale had not, so on a tiling corpus
    it divided a box of ``n + 1`` advances by ``n`` characters — every letter
    ~``(n+1)/n`` too wide, and by a factor that *varied with word length*.
    """

    @staticmethod
    def _tiling_layout(advance: float = 20.0) -> pd.DataFrame:
        """Monospaced boxes that tile, each carrying one trailing space.

        The bundled OneStop demo's shape: ``width == (len(text) + 1) * advance``
        and no gap between neighbours.
        """
        words = ["the", "cats", "sat"]
        widths = [(len(w) + 1) * advance for w in words]
        xs = np.cumsum([100.0] + widths[:-1])
        return pd.DataFrame(
            {
                "participant_id": ["p1"] * len(words),
                "trial_id": ["t1"] * len(words),
                "word_id": list(range(1, len(words) + 1)),
                "text": words,
                "x": xs,
                "y": [50.0] * len(words),
                "width": widths,
                "height": [40.0] * len(words),
                "line_idx": [1] * len(words),
            }
        )

    def test_the_advance_is_constant_across_word_lengths(self):
        from scanpath_studio.measures import word_char_advance

        layout = self._tiling_layout(advance=20.0)
        assert word_char_advance(layout) == pytest.approx([20.0, 20.0, 20.0])

    def test_a_glyph_tight_layout_keeps_width_over_characters(self, four_word_layout):
        """The correction is conditional — a layout with real gaps between the
        boxes is already glyph-tight, and dividing by ``n + 1`` there would
        introduce the very error this fixes."""
        from scanpath_studio.measures import word_char_advance

        # 80px boxes at 100px pitch: 20px gaps, so no trailing padding.
        assert word_char_advance(four_word_layout) == pytest.approx(
            [80 / 3, 80 / 3, 80 / 3, 80 / 4]
        )

    def test_landing_on_the_third_letter_reports_three(self):
        """A fixation on the centre of letter 3 of a 4-letter word lands at 3.5 —
        the convention is that an integer is a letter *boundary* and 1.0 is the
        word's first glyph, so the middle of letter k is k + 0.5."""
        advance = 20.0
        layout = self._tiling_layout(advance)
        word = layout.iloc[1]  # "cats", x = 180
        centre_of_letter_3 = float(word["x"]) + 2.5 * advance
        fix = _make_fixations([(centre_of_letter_3, 70, 200, 0)])
        out = compute_per_word_measures(fix, layout)
        row = out[out["word_id"] == word["word_id"]].iloc[0]
        assert row["initial_landing_position"] == pytest.approx(3.5)
        # …and the centred distance is measured against the same scale: the
        # glyphs span [1, 5), so the centre is 3.0 and letter 3's middle is
        # half a letter right of it (BUG-65 — this asserted 3.5 − 2.5).
        assert row["initial_landing_distance"] == pytest.approx(0.5)

    def test_the_exact_centre_of_a_word_is_zero(self):
        """BUG-65: "0 = word centre" is the register's promise — the old
        ``(n + 1) / 2`` read the exact middle of every word as +0.5."""
        advance = 20.0
        layout = self._tiling_layout(advance)
        word = layout.iloc[1]  # "cats": 4 glyphs from x
        centre = float(word["x"]) + 2.0 * advance
        fix = _make_fixations([(centre, 70, 200, 0)])
        out = compute_per_word_measures(fix, layout)
        row = out[out["word_id"] == word["word_id"]].iloc[0]
        assert row["initial_landing_distance"] == pytest.approx(0.0)

    def test_the_last_letter_stays_inside_the_word(self):
        """The old ``width / n`` scale put the end of a 4-letter word at 5.0 even
        though the box is 5 advances wide, so a landing on the final glyph read
        as if it were a letter earlier."""
        advance = 20.0
        layout = self._tiling_layout(advance)
        word = layout.iloc[1]
        last_glyph_centre = float(word["x"]) + 3.5 * advance
        fix = _make_fixations([(last_glyph_centre, 70, 200, 0)])
        out = compute_per_word_measures(fix, layout)
        row = out[out["word_id"] == word["word_id"]].iloc[0]
        assert row["initial_landing_position"] == pytest.approx(4.5)
        assert 4.0 < row["initial_landing_position"] < 5.0

    def test_right_to_left_counts_from_where_the_glyphs_end(self):
        """The RTL origin is `x + n × advance`, not the padded box edge.

        Those are one whole advance apart on a tiling layout, so the first pass
        at BUG-27 fixed the scale and left RTL reading a letter late — and
        disagreeing with `aggregation.landing_positions`, which measures across
        the glyph run on both sides. Caught by the surface-parity reviewer.
        """
        from scanpath_studio import aggregation

        advance = 20.0
        layout = self._tiling_layout(advance)
        layout["right_to_left"] = True
        word = layout.iloc[1]  # "cats" — 4 glyphs, running x … x + 80
        # 2.5 advances in *from the right*, i.e. the middle of letter 3.
        fix = _make_fixations(
            [(float(word["x"]) + 4 * advance - 2.5 * advance, 70, 200, 0)]
        )
        out = compute_per_word_measures(fix, layout)
        row = out[out["word_id"] == word["word_id"]].iloc[0]
        assert row["initial_landing_position"] == pytest.approx(3.5)
        # …and the fraction agrees, as it does for LTR.
        fraction = aggregation.landing_positions(out, fix)
        assert fraction[0] == pytest.approx(2.5 / 4.0)

    def test_the_landing_fraction_agrees_with_the_letter_position(self):
        """``aggregation.landing_positions`` and ``initial_landing_position`` are
        the same quantity in different units — the inconsistency VAL-5 found was
        that they were not."""
        from scanpath_studio import aggregation

        advance = 20.0
        layout = self._tiling_layout(advance)
        word = layout.iloc[1]  # "cats" — 4 glyphs
        fix = _make_fixations([(float(word["x"]) + 2.5 * advance, 70, 200, 0)])
        measured = compute_per_word_measures(fix, layout)
        fraction = aggregation.landing_positions(measured, fix)
        assert len(fraction) == 1
        # 2.5 advances into a 4-glyph run.
        assert fraction[0] == pytest.approx(2.5 / 4.0)


def _read_words(layout: pd.DataFrame, sequence: list, *, step: int = 250):
    """Fixations landing on the centre of each word id in ``sequence`` in turn
    (``None`` = a fixation outside every box), durations from the tuple."""
    centres = {
        int(r.word_id): (float(r.x) + float(r.width) / 2, float(r.y) + 20)
        for r in layout.itertuples()
    }
    rows = []
    for i, (word, duration) in enumerate(sequence):
        x, y = centres[word] if word is not None else (2000.0, 2000.0)
        rows.append((x, y, duration, i * step))
    return _make_fixations(rows)


def _row(out: pd.DataFrame, word_id: int) -> pd.Series:
    return out[out["word_id"] == word_id].iloc[0]


class TestEyeLinkDefinitions:
    """BUG-61/62/64/66: the computed measures mean what EyeLink's IA_* columns
    mean, because an imported value takes precedence over a computed one and the
    two must not disagree about what a column *is*. Validated on the bundled
    OneStop demo (its IA report came from these fixations): FFD, first run,
    total time, skip and regression-in agree on all 1780 fixated words, RPD on
    1779 and regression-out on 1774."""

    def test_go_past_counts_a_first_visit_made_during_the_regression(
        self, four_word_layout
    ):
        # 1 → 3 → 2 → 3 → 4: word 2 is first seen *during* the regression
        # from 3, and that fixation belongs to 3's go-past time.
        fix = _read_words(
            four_word_layout, [(1, 200), (3, 210), (2, 220), (3, 230), (4, 240)]
        )
        out = compute_per_word_measures(fix, four_word_layout)
        assert _row(out, 3)["regression_path_duration_ms"] == pytest.approx(660)
        assert _row(out, 1)["regression_path_duration_ms"] == pytest.approx(200)
        assert _row(out, 2)["regression_path_duration_ms"] == pytest.approx(220)

    def test_a_word_first_reached_by_a_regression_was_skipped(self, four_word_layout):
        fix = _read_words(
            four_word_layout, [(1, 200), (3, 210), (2, 220), (3, 230), (4, 240)]
        )
        out = compute_per_word_measures(fix, four_word_layout)
        assert bool(_row(out, 2)["skip_flag"]) is True
        assert [bool(_row(out, w)["skip_flag"]) for w in (1, 3, 4)] == [False] * 3
        # First fixation / first run stay defined, as EyeLink reports them.
        assert _row(out, 2)["first_fixation_ms"] == pytest.approx(220)

    def test_regression_out_is_a_first_pass_event(self, four_word_layout):
        # 1 2 3 4 → 2 → 1: the regression from 4 happens in first pass; the one
        # from 2 comes after 2 was left forwards, so it does not count.
        fix = _read_words(
            four_word_layout,
            [(1, 200), (2, 200), (3, 200), (4, 200), (2, 200), (1, 200)],
        )
        out = compute_per_word_measures(fix, four_word_layout)
        assert bool(_row(out, 4)["regression_out_flag"]) is True
        assert bool(_row(out, 2)["regression_out_flag"]) is False
        assert bool(_row(out, 1)["regression_in_flag"]) is True

    def test_an_off_text_fixation_ends_the_first_run(self, four_word_layout):
        fix = _read_words(four_word_layout, [(2, 100), (None, 50), (2, 120), (3, 200)])
        out = compute_per_word_measures(fix, four_word_layout)
        row = _row(out, 2)
        assert row["first_pass_gaze_duration_ms"] == pytest.approx(100)
        assert row["second_pass_duration_ms"] == pytest.approx(120)
        assert row["total_fixation_duration_ms"] == pytest.approx(220)
        assert row["single_fixation_duration_ms"] == pytest.approx(100)


class TestImportedMeasuresOnUnfixatedWords:
    """BUG-63: an IA report may store 0 rather than a blank for a word nobody
    fixated — the bundled OneStop one does, for all 1191 such words — and a 0
    wins the imported-over-computed precedence, so every mean counted skipped
    words as 0-ms fixations."""

    def test_an_imported_zero_on_an_unfixated_word_becomes_nan(self, four_word_layout):
        words = four_word_layout.assign(
            n_fixations=[1, 0, 0, 0],
            first_fixation_ms=[200.0, 0.0, 0.0, 0.0],
            first_pass_gaze_duration_ms=[200.0, 0.0, 0.0, 0.0],
            regression_path_duration_ms=[200.0, 0.0, 0.0, 0.0],
            total_fixation_duration_ms=[200.0, 0.0, 0.0, 0.0],
        )
        fix = _read_words(four_word_layout, [(1, 200)])
        out = compute_per_word_measures(fix, words)
        for column in (
            "first_fixation_ms",
            "first_pass_gaze_duration_ms",
            "regression_path_duration_ms",
        ):
            assert out[column].iloc[1:].isna().all(), column
            assert out[column].iloc[0] == pytest.approx(200)
        # Total time stays 0: the word was read past and got no time.
        assert (out["total_fixation_duration_ms"].iloc[1:] == 0).all()

    def test_an_imported_blank_second_pass_reads_as_zero(self, four_word_layout):
        words = four_word_layout.assign(
            n_fixations=[1, 1, 0, 0],
            second_pass_duration_ms=[np.nan, 150.0, np.nan, np.nan],
        )
        fix = _read_words(four_word_layout, [(1, 200), (2, 150)])
        out = compute_per_word_measures(fix, words)
        assert list(out["second_pass_duration_ms"]) == [0.0, 150.0, 0.0, 0.0]
