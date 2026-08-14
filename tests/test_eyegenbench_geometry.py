"""Tests for EyeGenBench display-parameter geometry.

Validates published display specifications and the layout engine that reconstructs
word boxes from interest areas when pixel coordinates are unavailable.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.eyegenbench_geometry import (
    DEFAULT_SPEC,
    DISPLAY_SPECS,
    DisplaySpec,
    display_spec_for,
    extract_eyelink_boxes,
    fill_missing_boxes,
    layout_words,
    parse_ia_data,
)

SPEC = DisplaySpec(
    width_px=200,
    height_px=100,
    font_px=10,
    char_width_px=10,
    line_pitch_px=30,
    monospaced=True,
    margin_px=10,
    source="test",
)


def test_layout_places_words_left_to_right_on_one_line():
    words = layout_words(["ab", "cd"], SPEC)
    assert list(words["word_id"]) == [0, 1]
    assert list(words["text"]) == ["ab", "cd"]
    assert list(words["line"]) == [0, 0]
    # margin 10, "ab" = 2 chars * 10px = 20 -> [10, 30); space then "cd".
    assert words.loc[0, "start_x"] == 10
    assert words.loc[0, "end_x"] == 30
    assert words.loc[1, "start_x"] == 40
    assert words.loc[1, "end_x"] == 60


def test_layout_wraps_when_the_line_is_full():
    # usable width = 200 - 2*10 = 180px = 18 chars.
    words = layout_words(["aaaaaaaaaa", "bbbbbbbbbb"], SPEC)
    assert list(words["line"]) == [0, 1]
    assert words.loc[1, "start_x"] == 10
    assert words.loc[1, "start_y"] == words.loc[0, "start_y"] + 30


def test_layout_boxes_never_overlap_and_advance_monotonically():
    words = layout_words(["the", "quick", "brown", "fox", "jumps"], SPEC)
    for line, group in words.groupby("line"):
        assert group["start_x"].is_monotonic_increasing
        assert (group["start_x"].shift(-1).dropna() >= group["end_x"][:-1]).all()


def test_layout_rejects_an_empty_word_list():
    with pytest.raises(ValueError, match="at least one interest area"):
        layout_words([], SPEC)


def test_default_spec_is_a_usable_screen():
    words = layout_words(["hello", "world"], DEFAULT_SPEC)
    assert (words["end_x"] <= DEFAULT_SPEC.width_px).all()
    assert isinstance(words, pd.DataFrame)


def test_known_corpus_uses_its_published_screen():
    spec = display_spec_for("potec")
    assert (spec.width_px, spec.height_px) == (1680, 1050)
    assert spec.source.startswith("pymovements")


def test_copco_uses_its_paper_reported_font():
    spec = display_spec_for("copco")
    assert (spec.width_px, spec.height_px) == (1920, 1080)
    assert spec.monospaced is True
    # Courier 14, double-spaced (Hollenstein et al. 2022).
    assert spec.line_pitch_px == spec.font_px * 2
    assert "copco" in spec.source or "paper" in spec.source


def test_unknown_corpus_falls_back_to_the_default_screen():
    assert display_spec_for("no-such-corpus") is DEFAULT_SPEC


def test_lookup_is_case_insensitive():
    assert display_spec_for("PoTeC") == display_spec_for("potec")


def test_every_spec_cites_a_source_and_is_physically_sane():
    for name, spec in DISPLAY_SPECS.items():
        assert spec.source, f"{name} has no citation"
        assert spec.width_px > 0 and spec.height_px > 0, name
        assert spec.char_width_px > 0 and spec.line_pitch_px >= spec.font_px, name
        assert 2 * spec.margin_px < spec.width_px, name


def test_chars_per_degree_entries_use_the_measured_width_not_the_ratio():
    spec = display_spec_for("emtec")
    # Derived from 1280px / 38.2cm at 60cm with 2.86 chars per degree of visual
    # angle -- deliberately distinct from the font_px * 0.6 fallback (8.4px), so
    # this fails if the formula inverts or silently takes the ratio path.
    assert spec.char_width_px == pytest.approx(12.2693, abs=1e-4)
    assert spec.char_width_px != pytest.approx(spec.font_px * 0.6)


def test_parse_ia_data_reads_the_eyelink_rectangle():
    boxes = parse_ia_data(pd.Series(["[STATIC, RECTANGLE, 10, 20, 60, 40]"]))
    assert boxes.loc[0, "start_x"] == 10
    assert boxes.loc[0, "start_y"] == 20
    assert boxes.loc[0, "end_x"] == 60
    assert boxes.loc[0, "end_y"] == 40


def test_parse_ia_data_yields_nan_for_unparseable_rows():
    boxes = parse_ia_data(pd.Series([".", "", None]))
    assert boxes["start_x"].isna().all()


def test_extract_dedupes_repeat_fixations_on_one_interest_area():
    frame = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1", "p1"],
            "ia_index": [0, 0, 1],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 70, 20, 120, 40]",
            ],
        }
    )
    boxes = extract_eyelink_boxes(frame)
    assert len(boxes) == 2
    assert list(boxes["ia_index"]) == [0, 1]
    assert boxes.loc[boxes["ia_index"] == 1, "start_x"].item() == 70


def test_extract_returns_empty_when_the_column_is_absent():
    frame = pd.DataFrame({"unique_paragraph_id": ["p1"], "ia_index": [0]})
    assert extract_eyelink_boxes(frame).empty


def _boxes(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "unique_paragraph_id",
            "ia_index",
            "start_x",
            "start_y",
            "end_x",
            "end_y",
        ],
    )


def test_fill_inserts_the_gap_between_two_real_boxes():
    boxes = _boxes([["p1", 0, 10, 20, 60, 40], ["p1", 2, 130, 20, 180, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 3}, SPEC)
    assert list(filled["ia_index"]) == [0, 1, 2]
    gap = filled[filled["ia_index"] == 1].iloc[0]
    assert gap["start_x"] >= 60 and gap["end_x"] <= 130
    assert gap["start_y"] == 20 and gap["end_y"] == 40
    assert interpolated == pytest.approx(1 / 3)


def test_fill_is_a_no_op_when_every_area_is_real():
    boxes = _boxes([["p1", 0, 10, 20, 60, 40], ["p1", 1, 70, 20, 120, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 2}, SPEC)
    assert len(filled) == 2
    assert interpolated == 0.0


def test_fill_handles_a_leading_gap_before_any_real_box():
    boxes = _boxes([["p1", 1, 70, 20, 120, 40]])
    filled, _ = fill_missing_boxes(boxes, {"p1": 2}, SPEC)
    first = filled[filled["ia_index"] == 0].iloc[0]
    assert first["end_x"] <= 70
    assert first["start_y"] == 20
