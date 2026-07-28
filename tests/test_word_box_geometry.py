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
    recentre_word_boxes,
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
