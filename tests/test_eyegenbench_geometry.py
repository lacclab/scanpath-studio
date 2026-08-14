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
    GEOMETRY_REAL,
    GEOMETRY_RECONSTRUCTED,
    GEOMETRY_SYNTHESIZED,
    DisplaySpec,
    display_spec_for,
    extract_eyelink_boxes,
    fill_missing_boxes,
    layout_words,
    parse_ia_data,
    place_fixations,
    resolve_geometry,
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


def _assert_invariant_within_line(filled):
    """Check that boxes on the same line never invert or overlap."""
    grouped = filled.groupby("start_y")
    for line_y, group in grouped:
        sorted_by_idx = group.sort_values("ia_index")
        for i in range(len(sorted_by_idx) - 1):
            curr = sorted_by_idx.iloc[i]
            nxt = sorted_by_idx.iloc[i + 1]
            # Next box must start at or after this one ends
            assert nxt["start_x"] >= curr["end_x"], (
                f"Overlap on line {line_y}: box {curr['ia_index']} ends at {curr['end_x']}, "
                f"box {nxt['ia_index']} starts at {nxt['start_x']}"
            )


def test_fill_two_consecutive_gaps_are_distinct_and_ordered():
    # Real boxes at indices 0 and 3, gaps at 1 and 2
    boxes = _boxes([["p1", 0, 10, 20, 60, 40], ["p1", 3, 200, 20, 250, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 4}, SPEC)
    assert list(filled["ia_index"]) == [0, 1, 2, 3]

    box1 = filled[filled["ia_index"] == 1].iloc[0]
    box2 = filled[filled["ia_index"] == 2].iloc[0]

    # Both should be between the real boxes
    assert box1["start_x"] >= 60 and box1["end_x"] <= 200
    assert box2["start_x"] >= 60 and box2["end_x"] <= 200

    # Should be distinct (not identical)
    assert not (box1["start_x"] == box2["start_x"] and box1["end_x"] == box2["end_x"])

    # Should be ordered
    assert box1["start_x"] >= box1["end_x"] - box2["end_x"] + box2["start_x"]

    _assert_invariant_within_line(filled)
    assert interpolated == pytest.approx(2 / 4)


def test_fill_narrow_gap_does_not_exceed_next_real_box():
    # Real boxes are close together
    boxes = _boxes([["p1", 0, 10, 20, 60, 40], ["p1", 2, 80, 20, 130, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 3}, SPEC)

    box1 = filled[filled["ia_index"] == 1].iloc[0]
    box2 = filled[filled["ia_index"] == 2].iloc[0]

    # Interpolated box's end should not exceed the next real box's start
    assert box1["end_x"] <= box2["start_x"], (
        f"Interpolated box end {box1['end_x']} exceeds next real box start {box2['start_x']}"
    )

    _assert_invariant_within_line(filled)


def test_fill_trailing_run_boxes_advance():
    # Real box at 0, trailing gaps at 1 and 2
    boxes = _boxes([["p1", 0, 10, 20, 60, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 3}, SPEC)

    box0 = filled[filled["ia_index"] == 0].iloc[0]
    box1 = filled[filled["ia_index"] == 1].iloc[0]
    box2 = filled[filled["ia_index"] == 2].iloc[0]

    # All three should be distinct
    assert not (box0["start_x"] == box1["start_x"] and box0["end_x"] == box1["end_x"])
    assert not (box1["start_x"] == box2["start_x"] and box1["end_x"] == box2["end_x"])

    # Trailing boxes should advance rightward
    assert box1["start_x"] > box0["end_x"]
    assert box2["start_x"] > box1["end_x"]

    _assert_invariant_within_line(filled)
    assert interpolated == pytest.approx(2 / 3)


def test_fill_no_anchor_creates_distinct_ordered_boxes():
    # No real boxes at all, count = 3
    boxes = _boxes([])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 3}, SPEC)

    assert len(filled) == 3
    assert list(filled["ia_index"]) == [0, 1, 2]

    # All on the same line (margin_px)
    assert all(filled["start_y"] == SPEC.margin_px)
    assert all(filled["end_y"] == SPEC.margin_px + SPEC.font_px)

    # All distinct
    for i in range(len(filled) - 1):
        curr = filled.iloc[i]
        nxt = filled.iloc[i + 1]
        assert not (curr["start_x"] == nxt["start_x"] and curr["end_x"] == nxt["end_x"])

    # Ordered left-to-right
    _assert_invariant_within_line(filled)

    # All boxes should be interpolated (fraction = 1.0)
    assert interpolated == pytest.approx(1.0)


def test_fill_leading_run_with_low_room():
    # Real box at index 2 near margin, leading gaps at 0 and 1 (low room)
    # With margin_px=10, R.start_x=60, k=2:
    # available = 60 - 10 = 50, slot = 25
    # i=0: [10, 35], i=1: [35, 60]
    boxes = _boxes([["p1", 2, 60, 20, 110, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 3}, SPEC)

    box0 = filled[filled["ia_index"] == 0].iloc[0]
    box1 = filled[filled["ia_index"] == 1].iloc[0]
    box2 = filled[filled["ia_index"] == 2].iloc[0]

    # All three should be distinct
    assert not (
        box0["start_x"] == box1["start_x"] and box0["end_x"] == box1["end_x"]
    ), "Leading gap boxes should not be identical"

    # Should be ordered and fill the space
    assert box0["start_x"] >= SPEC.margin_px
    assert box0["end_x"] <= box1["start_x"]
    assert box1["end_x"] <= box2["start_x"]

    _assert_invariant_within_line(filled)
    assert interpolated == pytest.approx(2 / 3)


def test_fill_leading_run_with_ample_room():
    # Real box at index 2 far from margin, leading gaps at 0 and 1 (ample room)
    boxes = _boxes([["p1", 2, 200, 20, 250, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 3}, SPEC)

    box0 = filled[filled["ia_index"] == 0].iloc[0]
    box1 = filled[filled["ia_index"] == 1].iloc[0]
    box2 = filled[filled["ia_index"] == 2].iloc[0]

    # All three should be distinct
    assert not (box0["start_x"] == box1["start_x"] and box0["end_x"] == box1["end_x"])
    assert not (box1["start_x"] == box2["start_x"] and box1["end_x"] == box2["end_x"])

    # Should be ordered left-to-right
    assert box0["start_x"] >= SPEC.margin_px
    assert box0["end_x"] <= box1["start_x"]
    assert box1["end_x"] <= box2["start_x"]
    assert box2["end_x"] >= box2["start_x"]  # box2 is real, should have valid bounds

    _assert_invariant_within_line(filled)
    assert interpolated == pytest.approx(2 / 3)


TEXTS = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1"],
        "text": ["ab cd"],
        "text_language": ["en"],
        "ia_list": [["ab", "cd"]],
    }
)


def test_real_geometry_wins_when_ia_data_is_present():
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, 1],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 70, 20, 120, 40]",
            ],
        }
    )
    words, report = resolve_geometry("onestop", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_REAL
    assert report["interpolated_fraction"] == 0.0
    assert words.loc[words["ia_index"] == 0, "start_x"].item() == 10
    assert (words["geometry_source"] == GEOMETRY_REAL).all()


def test_reconstructed_when_no_raw_boxes_but_a_published_screen():
    words, report = resolve_geometry("potec", TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_RECONSTRUCTED
    assert report["display_source"].startswith("pymovements")
    assert len(words) == 2


def test_synthesized_when_nothing_is_known():
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_words_carry_their_interest_area_labels():
    words, _ = resolve_geometry("potec", TEXTS, None)
    assert list(words["ia_label"]) == ["ab", "cd"]


def test_place_fixations_inverts_the_landing_position_formula():
    words = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [0],
            "start_x": [10.0],
            "end_x": [60.0],
            "start_y": [20.0],
            "end_y": [40.0],
        }
    )
    fix = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [0],
            "fix_landing_position": [0.5],
        }
    )
    placed = place_fixations(fix, words)
    assert placed.loc[0, "x"] == 35.0  # 10 + 0.5 * 50
    assert placed.loc[0, "y"] == 30.0  # box vertical centre
    # Round-trip invariant: recovering the landing position reproduces the input.
    recovered = (placed.loc[0, "x"] - 10.0) / 50.0
    assert recovered == pytest.approx(0.5)


def test_place_fixations_drops_rows_with_no_matching_box():
    words = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [0],
            "start_x": [10.0],
            "end_x": [60.0],
            "start_y": [20.0],
            "end_y": [40.0],
        }
    )
    fix = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p9"],
            "ia_index": [0, 3],
            "fix_landing_position": [0.5, 0.5],
        }
    )
    assert len(place_fixations(fix, words)) == 1


# Controller addendum, Ruling R8: a paragraph with no measured boxes must not be
# stamped `real`, even when the raw file DID yield real boxes for a sibling
# paragraph in the same dataset. `unique_paragraph_id` "p2" never appears in the
# raw fixture below -- EyeGenBench's raw file has nothing on it at all.
TEXTS_TWO_PARAGRAPHS = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1", "p2"],
        "text": ["ab cd", "ef gh"],
        "text_language": ["en", "en"],
        "ia_list": [["ab", "cd"], ["ef", "gh"]],
    }
)


def _raw_boxes_for_p1_only():
    return pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, 1],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 70, 20, 120, 40]",
            ],
        }
    )


def test_paragraph_without_real_boxes_falls_back_to_reconstructed():
    words, report = resolve_geometry(
        "potec", TEXTS_TWO_PARAGRAPHS, _raw_boxes_for_p1_only()
    )
    # Dataset-level tier is the best tier any single paragraph achieved.
    assert report["geometry_source"] == GEOMETRY_REAL
    assert report["paragraphs_without_real_boxes"] == 1
    p1_source = words.loc[words["unique_paragraph_id"] == "p1", "geometry_source"]
    p2_source = words.loc[words["unique_paragraph_id"] == "p2", "geometry_source"]
    assert (p1_source == GEOMETRY_REAL).all()
    assert (p2_source == GEOMETRY_RECONSTRUCTED).all()


def test_paragraph_without_real_boxes_falls_back_to_synthesized_for_an_unknown_corpus():
    words, report = resolve_geometry(
        "cfiltsarcasm", TEXTS_TWO_PARAGRAPHS, _raw_boxes_for_p1_only()
    )
    assert report["geometry_source"] == GEOMETRY_REAL
    assert report["paragraphs_without_real_boxes"] == 1
    p2_source = words.loc[words["unique_paragraph_id"] == "p2", "geometry_source"]
    assert (p2_source == GEOMETRY_SYNTHESIZED).all()


def test_paragraphs_without_real_boxes_is_zero_when_every_paragraph_is_real():
    _, report = resolve_geometry("onestop", TEXTS, _raw_boxes_for_p1_only())
    assert report["paragraphs_without_real_boxes"] == 0


def test_a_raw_box_past_the_end_of_the_word_list_does_not_earn_the_real_stamp():
    # `fill_missing_boxes` only ever places indices 0..count-1 for a paragraph,
    # so an ia_index the raw file recorded past the end of this paragraph's own
    # 2-word list (a harmonised-text/raw-export mismatch) is never used -- every
    # box actually placed for "p1" is synthesized. Counting the unused row as a
    # contribution would stamp `real` on a paragraph that is 100% placeholder.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [5],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 500, 20, 560, 40]"],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert report["paragraphs_without_real_boxes"] == 1
    assert report["interpolated_fraction"] == 1.0
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_a_negative_ia_index_does_not_earn_the_real_stamp():
    # EyeLink writes -1 for a fixation that landed on no interest area at all
    # -- the raw-export sentinel, not a corner case, since we parse the raw
    # file directly rather than EyeGenBench's coerced frame. `fill_missing_boxes`
    # only ever places indices 0..count-1, so -1 is never used either; every
    # box actually placed for "p1" is synthesized.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [-1],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 500, 20, 560, 40]"],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert report["paragraphs_without_real_boxes"] == 1
    assert report["interpolated_fraction"] == 1.0
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_string_typed_ia_index_resolves_without_raising():
    # Raw CSVs routinely come back with ia_index as an object/string column
    # rather than integer. This must resolve like the integer-typed fixture in
    # test_real_geometry_wins_when_ia_data_is_present, not raise.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": ["0", "1"],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 70, 20, 120, 40]",
            ],
        }
    )
    words, report = resolve_geometry("onestop", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_REAL
    assert report["paragraphs_without_real_boxes"] == 0
    assert words.loc[words["ia_index"] == 0, "start_x"].item() == 10
    assert (words["geometry_source"] == GEOMETRY_REAL).all()


def test_paragraphs_without_real_boxes_counts_every_paragraph_when_there_is_no_raw_data():
    _, reconstructed_report = resolve_geometry("potec", TEXTS, None)
    assert reconstructed_report["paragraphs_without_real_boxes"] == 1
    _, synthesized_report = resolve_geometry("cfiltsarcasm", TEXTS, None)
    assert synthesized_report["paragraphs_without_real_boxes"] == 1
