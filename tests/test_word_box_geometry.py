"""BUG-11: word-box boundaries should fall in the middle of the inter-word space.

EyeLink-style exports bake the whole space into each box as *trailing* padding,
so the boxes tile the line but every boundary sits a half-space too far right —
and a fixation in the space *before* a word is credited to the previous one.
Glyph-tight AOIs (PoTeC / MultiplEYE) must be left alone, so the correction is
conditional on the layout.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.measures import (
    assign_fixations_to_words,
    fixation_in_text_mask,
    recentre_word_boxes,
    word_box_bounds,
    word_box_space_px,
)

ADVANCE = 19.0


def _tiling_words(texts=("Robert", "Myslajek", "finds", "what", "he")) -> pd.DataFrame:
    """One line of EyeLink-style boxes: `(n_chars + 1) × advance`, tiling."""
    rows, x = [], 358.0
    for i, text in enumerate(texts):
        width = (len(text) + 1) * ADVANCE
        rows.append(
            dict(
                participant_id="p1",
                trial_id="t1",
                word_id=i,
                text=text,
                x=x,
                y=100.0,
                width=width,
                height=30.0,
            )
        )
        x += width
    return pd.DataFrame(rows)


def _glyph_tight_words() -> pd.DataFrame:
    """PoTeC / MultiplEYE shape: boxes hug the glyphs, real gaps between them."""
    rows, x = [], 100.0
    for i, text in enumerate(("Der", "Wolf", "frisst", "gern")):
        width = len(text) * ADVANCE
        rows.append(
            dict(
                participant_id="p1",
                trial_id="t1",
                word_id=i,
                text=text,
                x=x,
                y=100.0,
                width=width,
                height=30.0,
            )
        )
        x += width + ADVANCE  # a real gap where the space is
    return pd.DataFrame(rows)


class TestSpaceInference:
    def test_detects_the_trailing_space_in_a_tiling_layout(self):
        assert word_box_space_px(_tiling_words()) == pytest.approx(ADVANCE)

    def test_leaves_glyph_tight_aois_alone(self):
        """Their boundaries already sit in the whitespace — shifting them would
        introduce the very error this fixes."""
        assert word_box_space_px(_glyph_tight_words()) == 0.0

    def test_a_proportional_layout_is_not_recognised(self):
        words = _tiling_words()
        words.loc[1, "width"] = 40.0  # breaks (n_chars + 1) × advance
        words.loc[3, "width"] = 300.0
        assert word_box_space_px(words) == 0.0

    def test_pixel_rounding_does_not_defeat_detection(self):
        """Export widths are integers, so the relation only holds to ±1 px."""
        words = _tiling_words()
        words["width"] = words["width"].round()
        words.loc[0, "width"] += 1
        words.loc[2, "width"] -= 1
        assert word_box_space_px(words) == pytest.approx(ADVANCE, abs=0.5)

    def test_missing_text_means_no_inference(self):
        words = _tiling_words().drop(columns=["text"])
        assert word_box_space_px(words) == 0.0

    def test_too_few_words_to_be_sure(self):
        assert word_box_space_px(_tiling_words(texts=("a", "b"))) == 0.0

    def test_only_one_trial_is_sampled(self):
        """Every trial is drawn at the same screen positions, so clustering
        across the corpus would read interleaved trials as broken tiling."""
        a = _tiling_words()
        b = _tiling_words()
        b["trial_id"] = "t2"
        both = pd.concat([a, b], ignore_index=True)
        assert word_box_space_px(both) == pytest.approx(ADVANCE)


class TestRecentring:
    def test_shifts_every_box_left_by_half_a_space(self):
        words = _tiling_words()
        out = recentre_word_boxes(words)
        assert (words["x"] - out["x"]).unique().tolist() == [ADVANCE / 2]

    def test_the_boxes_still_tile(self):
        out = recentre_word_boxes(_tiling_words()).sort_values("x")
        right = (out["x"] + out["width"]).to_numpy()[:-1]
        assert list(out["x"].to_numpy()[1:]) == pytest.approx(list(right))

    def test_a_boundary_now_sits_mid_space(self):
        """'Robert' ends at 491 (6 glyphs + a space from 472); the boundary
        should land at 481.5, halfway through that space."""
        out = recentre_word_boxes(_tiling_words())
        assert out.iloc[0]["x"] + out.iloc[0]["width"] == pytest.approx(481.5)

    def test_glyph_tight_boxes_are_returned_untouched(self):
        words = _glyph_tight_words()
        assert recentre_word_boxes(words) is words

    def test_width_is_unchanged(self):
        words = _tiling_words()
        assert list(recentre_word_boxes(words)["width"]) == list(words["width"])


class TestAssignment:
    def _assign_at(self, words: pd.DataFrame, x: float):
        fixations = pd.DataFrame(
            [
                dict(
                    participant_id="p1",
                    trial_id="t1",
                    x=x,
                    y=115.0,
                    duration_ms=200.0,
                )
            ]
        )
        return assign_fixations_to_words(fixations, words, overwrite=True)[
            "word_id"
        ].iloc[0]

    def test_the_space_between_two_words_is_split_between_them(self):
        """'Robert' glyphs end at 472 and 'Myslajek' starts at 491, so the
        boundary belongs at 481.5. Before the fix the whole space counted as
        'Robert' — a fixation at 485 was credited to the wrong word."""
        words = _tiling_words()
        assert self._assign_at(words, 475.0) == 0  # first half → Robert
        assert self._assign_at(words, 485.0) == 1  # second half → Myslajek

    def test_a_fixation_on_the_glyphs_is_unaffected(self):
        words = _tiling_words()
        fixations = pd.DataFrame(
            [
                dict(
                    participant_id="p1",
                    trial_id="t1",
                    x=400.0,
                    y=115.0,
                    duration_ms=200.0,
                )
            ]
        )
        out = assign_fixations_to_words(fixations, words, overwrite=True)
        assert out["word_id"].iloc[0] == 0  # Robert

    def test_glyph_tight_assignment_is_unchanged(self):
        words = _glyph_tight_words()
        fixations = pd.DataFrame(
            [
                dict(
                    participant_id="p1",
                    trial_id="t1",
                    x=110.0,
                    y=115.0,
                    duration_ms=200.0,
                )
            ]
        )
        out = assign_fixations_to_words(fixations, words, overwrite=True)
        assert out["word_id"].iloc[0] == 0


class TestWordBoxBounds:
    """`word_box_bounds` is THE accessor — everything that touches AOI geometry
    goes through it, which is what the first pass at BUG-11 got wrong (it
    corrected two call sites out of nine)."""

    def test_returns_the_corrected_edges(self):
        x0, y0, x1, y1 = word_box_bounds(_tiling_words())
        assert x0[0] == pytest.approx(358.0 - ADVANCE / 2)
        assert x1[0] == pytest.approx(481.5)
        assert y0[0] == 100.0 and y1[0] == 130.0

    def test_is_pure_so_it_cannot_be_applied_twice(self):
        """The frame-shaped `recentre_word_boxes` shifts `x`, so a second pass
        shifts again. Returning arrays makes that structurally impossible."""
        words = _tiling_words()
        first = word_box_bounds(words)
        second = word_box_bounds(words)
        assert list(first[0]) == list(second[0])
        assert list(words["x"]) == list(_tiling_words()["x"])  # caller's frame intact

    def test_a_subset_needs_the_full_layout_to_be_recognised(self):
        """Tiling is a property of the whole line. A subset has holes, and the
        holes read as glyph-tight gaps — so detection has to see the full frame."""
        words = _tiling_words()
        span = words.iloc[[0, 3]]  # 'Robert' and 'what' — not adjacent
        assert word_box_bounds(span)[0][0] == pytest.approx(358.0)  # undetected
        assert word_box_bounds(span, layout=words)[0][0] == pytest.approx(348.5)

    def test_glyph_tight_bounds_are_the_raw_edges(self):
        words = _glyph_tight_words()
        x0, _, x1, _ = word_box_bounds(words)
        assert list(x0) == list(words["x"])
        assert list(x1) == list(words["x"] + words["width"])


class TestInTextMask:
    def _mask_at(self, words: pd.DataFrame, x: float) -> bool:
        fixations = pd.DataFrame(
            [dict(participant_id="p1", trial_id="t1", x=x, y=115.0, duration_ms=200.0)]
        )
        return bool(fixation_in_text_mask(fixations, words).iloc[0])

    def test_the_text_starts_half_a_space_before_the_first_glyph(self):
        """The corrected first box reaches back into the left margin by half a
        space — a fixation there is on the text, not out of bounds."""
        words = _tiling_words()
        assert self._mask_at(words, 352.0) is True

    def test_the_text_ends_half_a_space_after_the_last_glyph(self):
        """'he' is the last word: its glyphs end at 909 and the raw box ran on to
        928. Corrected, the line stops at 918.5, so a fixation at 925 — a whole
        space past the last letter — is off the text, where it used to count."""
        words = _tiling_words()
        assert float((words["x"] + words["width"]).max()) == pytest.approx(928.0)
        assert self._mask_at(words, 925.0) is False
        assert self._mask_at(words, 915.0) is True


class TestDependentConsumers:
    """Every downstream measure that reads a box edge, not just assignment."""

    def test_the_word_heatmap_rects_sit_on_the_word_box_outlines(self):
        """The visible symptom: with the heatmap on, the tinted rects were drawn
        from the raw frame while the outlines came from the corrected one, so
        every rect was half a space out."""
        from scanpath_studio import plots

        words = _tiling_words()
        fixations = pd.DataFrame(
            [
                dict(
                    participant_id="p1",
                    trial_id="t1",
                    x=400.0,
                    y=115.0,
                    duration_ms=200.0,
                    timestamp_ms=0.0,
                )
            ]
        )
        fig = plots.go.Figure()
        plots._add_word_level_heatmap(
            fig,
            words,
            fixations,
            x_field="x",
            y_field="y",
            weights=None,
            heatmap_colorscale="Viridis",
            heatmap_range=None,
            show_colorbars=False,
        )
        outlines = {(s["x0"], s["x1"]) for s in plots.build_word_boxes(words)}
        rects = {(s.x0, s.x1) for s in fig.layout.shapes if "heatmap" in (s.name or "")}
        assert rects and rects <= outlines

    def test_the_critical_span_outline_uses_corrected_edges(self):
        """The span is a *subset* of the words, so this only works if the overlay
        passes the full frame as the detection layout."""
        from scanpath_studio import plots

        words = _tiling_words()
        words["is_in_aspan"] = [False, True, True, False, False]
        (shape,) = plots.build_critical_span_overlay(words)
        assert shape["x0"] == pytest.approx(491.0 - ADVANCE / 2)

    def test_snapping_a_fixation_lands_on_the_glyph_centre(self):
        """The raw box centre is half a character right of the word's visual
        centre, which reads as a systematic rightward bias in linear-reading mode."""
        from scanpath_studio import plots

        words = _tiling_words()
        fixations = pd.DataFrame(
            [
                dict(
                    participant_id="p1",
                    trial_id="t1",
                    x=400.0,
                    y=115.0,
                    duration_ms=200.0,
                    word_id=0,
                )
            ]
        )
        out = plots._snap_fixations_to_words(fixations, words, "x", "y")
        # 'Robert' glyphs run 358 → 472, so the centre is 415.
        assert out["x"].iloc[0] == pytest.approx(415.0)

    def test_landing_position_is_measured_from_the_first_glyph(self):
        """#BUG-27 moved this origin, on purpose.

        It used to measure from the **corrected left edge** — 348.5, half an
        advance left of the first glyph — because that is where the word's
        *interest area* starts. But a within-word position is a position among
        the word's letters, and the test directly above already pins where those
        are: 'Robert' glyphs run 358 → 472, centre 415. Measuring the landing
        from 348.5 put "0% into the word" half a space before the word, and
        dividing by the padded 133 px width put "100%" half a space after it —
        so `landing_positions`' own docstring promise (0 = word start, 1 = word
        end) was untrue in both directions on a tiling corpus.

        `word_box_bounds` still answers *which* word a point is in, from the
        corrected edge; this answers *where in it*, from the glyphs. The two are
        exactly half an advance apart by construction.
        """
        from scanpath_studio.aggregation import landing_positions

        words = _tiling_words()
        words["first_fix_x"] = [400.0] * len(words)
        got = landing_positions(words, as_fraction=False)
        # 400 is 42 px past 'Robert''s first glyph at 358.
        assert got[0] == pytest.approx(42.0)
        # …and 42 of the 114 px its six glyphs occupy, not of the padded 133.
        fraction = landing_positions(words)
        assert fraction[0] == pytest.approx(42.0 / (6 * ADVANCE))


def test_the_bundled_demo_is_recognised_as_a_tiling_layout():
    """Regression guard for the measured repro (2026-07-03)."""
    from scanpath_studio.data import (
        infer_word_schema,
        load_sample_data,
        normalize_words,
    )

    words_raw, _ = load_sample_data()
    words = normalize_words(words_raw, infer_word_schema(words_raw))
    assert word_box_space_px(words) == pytest.approx(19.0)
