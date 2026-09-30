"""BUG-83: word boxes are used exactly as the experiment defined them.

EyeLink-style exports tile the line: each box is one character cell wider than
its word and carries the following space as trailing padding. BUG-11 used to
pull every such boundary back half a space; that reassigned 7.4% of the demo's
fixations relative to EyeLink's own interest-area assignment, so it was
reverted. The boxes are now ``x .. x + width`` everywhere a point is tested
against one or one is drawn, and a fixation on the space after a word belongs to
that word.

The layout's *shape* still matters inside a word: `word_box_space_px` detects the
trailing space so the letter scale (BUG-27) and the drawn label (BUG-30) stay on
the glyphs, which is what the second half of this module pins.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio.measures import (
    assign_fixations_to_words,
    fixation_in_text_mask,
    word_box_bounds,
    word_box_space_px,
    word_glyph_span,
)

ADVANCE = 19.0


def _tiling_words(texts=("Robert", "Myslajek", "finds", "what", "he")) -> pd.DataFrame:
    """One line of EyeLink-style boxes: `(n_chars + 1) × advance`, tiling.

    'Robert' is the box 358 → 491: glyphs 358 → 472, then its trailing space
    472 → 491. 'Myslajek' starts at 491.
    """
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


def _fixation(x: float, **extra) -> pd.DataFrame:
    """One fixation on the line's vertical centre."""
    row = dict(participant_id="p1", trial_id="t1", x=x, y=115.0, duration_ms=200.0)
    return pd.DataFrame([row | extra])


class TestSpaceInference:
    """The detector survives BUG-83 — the letter scale and the labels need it."""

    def test_detects_the_trailing_space_in_a_tiling_layout(self):
        assert word_box_space_px(_tiling_words()) == pytest.approx(ADVANCE)

    def test_glyph_tight_aois_carry_no_padding(self):
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


class TestWordBoxBounds:
    """`word_box_bounds` is THE accessor, and it returns the data's own boxes."""

    def test_returns_the_experiments_edges_on_a_tiling_layout(self):
        """BUG-11 returned 348.5 → 481.5 here, half a space left of the box."""
        words = _tiling_words()
        x0, y0, x1, y1 = word_box_bounds(words)
        assert list(x0) == list(words["x"])
        assert list(x1) == list(words["x"] + words["width"])
        assert x0[0] == 358.0 and x1[0] == 491.0
        assert y0[0] == 100.0 and y1[0] == 130.0

    def test_glyph_tight_bounds_are_the_raw_edges(self):
        words = _glyph_tight_words()
        x0, _, x1, _ = word_box_bounds(words)
        assert list(x0) == list(words["x"])
        assert list(x1) == list(words["x"] + words["width"])

    def test_a_subset_gets_the_same_edges_as_the_whole_line(self):
        """With no correction there is nothing for a subset to fail to detect."""
        words = _tiling_words()
        span = words.iloc[[0, 3]]
        assert list(word_box_bounds(span)[0]) == list(word_box_bounds(words)[0][[0, 3]])

    def test_is_pure(self):
        words = _tiling_words()
        word_box_bounds(words)
        pd.testing.assert_frame_equal(words, _tiling_words())

    def test_an_empty_frame_has_no_boxes(self):
        assert all(len(edge) == 0 for edge in word_box_bounds(pd.DataFrame()))


class TestAssignment:
    def _assign_at(self, words: pd.DataFrame, x: float):
        return assign_fixations_to_words(_fixation(x), words, overwrite=True)[
            "word_id"
        ].iloc[0]

    def test_the_space_after_a_word_belongs_to_that_word(self):
        """'Robert' glyphs end at 472 and its box at 491, so the whole space is
        Robert's — as EyeLink assigns it. BUG-11 gave 485 to 'Myslajek'."""
        words = _tiling_words()
        assert self._assign_at(words, 475.0) == 0
        assert self._assign_at(words, 485.0) == 0
        assert self._assign_at(words, 495.0) == 1

    def test_a_fixation_on_the_glyphs_is_unaffected(self):
        assert self._assign_at(_tiling_words(), 400.0) == 0  # Robert

    def test_glyph_tight_assignment_is_unchanged(self):
        assert self._assign_at(_glyph_tight_words(), 110.0) == 0

    def test_a_shared_edge_belongs_to_the_box_that_starts_there(self):
        """491 is both Robert's right edge and Myslajek's left one. Boxes are
        half-open, ``[x, x + width)``, so it is Myslajek's — where EyeLink put
        every such fixation in the demo. A closed test gave it to Robert."""
        words = _tiling_words()
        assert self._assign_at(words, 491.0) == 1
        assert self._assign_at(words, 490.0) == 0

    def test_a_shared_line_edge_belongs_to_the_line_below(self):
        above = _tiling_words()
        below = _tiling_words()
        below["word_id"] += len(above)
        below["y"] += 30.0  # the next line starts where this one ends
        words = pd.concat([above, below], ignore_index=True)
        fix = _fixation(400.0)
        fix["y"] = 130.0
        out = assign_fixations_to_words(fix, words, overwrite=True)
        assert out["word_id"].iloc[0] == len(above)  # 'Robert', second line


class TestInTextMask:
    def _mask_at(self, words: pd.DataFrame, x: float) -> bool:
        return bool(fixation_in_text_mask(_fixation(x), words).iloc[0])

    def test_the_text_starts_at_the_first_box(self):
        """BUG-11 reached half a space into the left margin; the first box
        starts at the first glyph, so 352 is off the text."""
        words = _tiling_words()
        assert self._mask_at(words, 352.0) is False
        assert self._mask_at(words, 360.0) is True

    def test_the_text_ends_where_the_last_box_does(self):
        """'he' is the last word: glyphs end at 909, its box at 928. The box
        is the experiment's, so a fixation at 925 is on the text."""
        words = _tiling_words()
        assert float((words["x"] + words["width"]).max()) == pytest.approx(928.0)
        assert self._mask_at(words, 925.0) is True
        assert self._mask_at(words, 935.0) is False


class TestDependentConsumers:
    """Every consumer that tests against a box or draws one uses the same box."""

    def test_the_drawn_outlines_are_the_experiments_boxes(self):
        from scanpath_studio import plots

        words = _tiling_words()
        outlines = [(s["x0"], s["x1"]) for s in plots.build_word_boxes(words)]
        assert outlines == list(
            zip(words["x"], words["x"] + words["width"], strict=True)
        )

    def test_the_word_heatmap_rects_sit_on_the_word_box_outlines(self):
        from scanpath_studio import plots

        words = _tiling_words()
        fixations = _fixation(485.0, timestamp_ms=0.0)  # Robert's trailing space
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
        # The fixation on the space counts towards Robert, and only Robert.
        assert rects == {(358.0, 491.0)}
        assert rects <= outlines

    def test_a_fixation_on_a_shared_edge_is_counted_once(self):
        """The heatmap bins with the assignment's rule. A closed test per word
        counted a fixation at 491 towards both Robert and Myslajek."""
        from scanpath_studio import plots

        words = _tiling_words()
        fig = plots.go.Figure()
        plots._add_word_level_heatmap(
            fig,
            words,
            _fixation(491.0, timestamp_ms=0.0),
            x_field="x",
            y_field="y",
            weights=None,
            heatmap_colorscale="Viridis",
            heatmap_range=None,
            show_colorbars=False,
        )
        rects = [(s.x0, s.x1) for s in fig.layout.shapes if "heatmap" in (s.name or "")]
        assert rects == [(491.0, 662.0)]

    def test_the_critical_span_outline_uses_the_experiments_edges(self):
        from scanpath_studio import plots

        words = _tiling_words()
        words["is_in_aspan"] = [False, True, True, False, False]
        (shape,) = plots.build_critical_span_overlay(words)
        # 'Myslajek' box starts at 491; 'finds' box ends at 491 + 9·19 + 6·19.
        assert shape["x0"] == pytest.approx(491.0)
        assert shape["x1"] == pytest.approx(491.0 + 15 * ADVANCE)

    def test_fill_xy_places_a_coordinate_less_fixation_in_its_box(self):
        """AOI-sequence data gets the interest area's centre, which the
        assignment then credits to the same word."""
        from scanpath_studio.data import fill_fixation_xy_from_words

        words = _tiling_words()
        fix = _fixation(np.nan, word_id=0)
        filled = fill_fixation_xy_from_words(fix, words)
        assert filled["x"].iloc[0] == pytest.approx(358.0 + 7 * ADVANCE / 2)
        again = assign_fixations_to_words(filled.drop(columns="word_id"), words)
        assert again["word_id"].iloc[0] == 0


class TestTheGlyphsStayWhereTheStimulusHadThem:
    """What BUG-83 deliberately keeps: rendering and the letter scale."""

    def test_the_glyph_span_stops_one_advance_short_of_a_tiling_box(self):
        start, run = word_glyph_span(_tiling_words())
        assert start[0] == 358.0
        assert run[0] == pytest.approx(6 * ADVANCE)  # 'Robert' — 358 → 472

    def test_a_glyph_tight_box_is_its_glyph_span(self):
        words = _glyph_tight_words()
        start, run = word_glyph_span(words)
        assert list(start) == list(words["x"])
        assert list(run) == pytest.approx(list(words["width"]))

    def test_the_label_is_centred_on_the_glyphs_not_the_box(self):
        """Centring in the raw tiling box would draw 'Robert' at 424.5, half a
        space right of the text the stimulus image shows at 358 → 472."""
        from scanpath_studio import plots

        words = _tiling_words()
        fig = plots.go.Figure()
        plots._add_word_label_trace(fig, words, base_font_size=12, font_family="mono")
        (trace,) = [t for t in fig.data if t.name == "words"]
        assert trace.x[0] == pytest.approx(415.0)

    def test_snapping_a_fixation_lands_on_the_glyph_centre(self):
        """Render-only, like the label: the linear-reading schematic puts the
        dot above the text, not half a character right of it."""
        from scanpath_studio import plots

        words = _tiling_words()
        out = plots._snap_fixations_to_words(
            _fixation(400.0, word_id=0), words, "x", "y"
        )
        assert out["x"].iloc[0] == pytest.approx(415.0)
        assert out["y"].iloc[0] == pytest.approx(100.0)

    def test_a_landing_on_the_trailing_space_is_not_clipped(self):
        """#BUG-83: the fraction is over the experiment's box.

        'Robert' is seven 19 px cells, 358 → 491: six glyphs and its trailing
        space, so a first fixation at 400 is 42/133 of the box. 'Myslajek' is
        nine, 491 → 662, with its glyphs ending at 643; a first fixation at 655
        is on its space — Myslajek's, as in EyeLink — and reads 164/171, where
        the glyph-run fraction (164/152) used to be clipped onto exactly 1.0.
        """
        from scanpath_studio.aggregation import landing_positions

        words = _tiling_words()
        words["first_fix_x"] = [400.0, 655.0, np.nan, np.nan, np.nan]
        assert list(landing_positions(words, as_fraction=False)) == pytest.approx(
            [42.0, 164.0]
        )
        fraction = landing_positions(words)
        assert list(fraction) == pytest.approx([42.0 / 133.0, 164.0 / 171.0])
        assert 8 / 9 < fraction[1] < 1.0  # past the last glyph, inside the box


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


@pytest.fixture(scope="module")
def demo():
    from scanpath_studio import api

    return api.load_sample_data()


class TestTheBundledDemoAgreesWithEyeLink:
    """The acceptance numbers for BUG-83, on the corpus that motivated it."""

    def test_geometry_assigns_fixations_as_eyelink_did(self, demo):
        """`CURRENT_FIX_INTEREST_AREA_ID` is EyeLink's own assignment against the
        same rectangles. The half-space shift disagreed on 7.4% of them, and a
        closed containment test on the 0.9% that sit exactly on a shared edge."""
        words, fix = demo
        eyelink = pd.to_numeric(fix["word_id"], errors="coerce")
        ours = pd.to_numeric(
            assign_fixations_to_words(fix.drop(columns="word_id"), words)["word_id"],
            errors="coerce",
        )
        assigned = eyelink.notna()
        assert assigned.sum() > 3000
        assert (ours[assigned] == eyelink[assigned]).all()

    def test_no_landing_fraction_piles_up_at_the_end_of_the_word(self, demo):
        """15% of the demo's first-fixation landings read exactly 1.0 — the
        trailing space, clipped onto the last letter's edge."""
        from scanpath_studio.aggregation import landing_positions
        from scanpath_studio.measures import compute_per_word_measures

        words, fix = demo
        words = words[words["participant_id"].isin(set(fix["participant_id"]))]
        measured = compute_per_word_measures(fix, words)
        fractions = landing_positions(measured, fix)
        assert fractions.size > 1000
        assert (fractions == 1.0).mean() < 0.01
        assert ((fractions >= 0.0) & (fractions <= 1.0)).mean() > 0.99
