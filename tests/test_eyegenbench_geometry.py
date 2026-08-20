"""Tests for EyeGenBench display-parameter geometry.

Validates published display specifications and the layout engine that reconstructs
word boxes from interest areas when pixel coordinates are unavailable.
"""

from __future__ import annotations

import warnings

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
    extract_text_df_boxes,
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


def test_onestop_reconstructs_its_published_layout():
    """R49 -- Berzak et al. 2025 (Sci Data 12:1995), Methods -> Apparatus.

    Every number here is quoted by the paper, so each assertion is a check that
    `_spec`'s model reproduces a published figure rather than a plausible one:
    the Dell U2715H's 2560x1440 over a 597 mm display area, the 19 px x 38 px
    letter cell, and the 76 px ("triple") line pitch. The character width is
    the interesting one -- it comes out of the visual-angle path (0.34 deg per
    letter at the published 75 cm eye-to-top-of-display) and has to land on the
    independently published 19 px, which is what makes 75 the defensible end of
    the paper's 75.0/79.5 cm pair.
    """
    spec = display_spec_for("onestop")
    assert (spec.width_px, spec.height_px) == (2560, 1440)
    assert spec.font_px == 38
    assert spec.monospaced is True
    assert spec.line_pitch_px == 76  # published "triple spacing (76 px)"
    assert spec.char_width_px == pytest.approx(19, rel=0.01)  # published 19 px cell
    # 2560 - 2*368 = 1824 px, the published text-column width (96 characters).
    assert spec.width_px - 2 * spec.margin_px == 1824
    assert "Berzak2025" in spec.source


def test_onestop_is_reconstructed_not_synthesized():
    _, report = resolve_geometry("onestop", TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_RECONSTRUCTED
    assert display_spec_for("onestop") is not DEFAULT_SPEC


def test_rsc_reconstructs_its_published_layout():
    """R49 -- Laurinavichyute et al. 2019, Method -> Procedure.

    `font_px` is the assertion that matters: the paper publishes *22 points*,
    and 28 px is that converted at the screen's own 92 ppi. A regression that
    dropped the conversion would leave 22 here -- the same points-as-pixels
    mistake R50 removed from `mecol2w2`.
    """
    spec = display_spec_for("rsc")
    assert (spec.width_px, spec.height_px) == (1920, 1080)
    assert spec.font_px == 28
    assert spec.font_px != 22  # not the published POINT size used as pixels
    assert spec.monospaced is True
    # 0.29 deg per character at 90 cm on a 53.1 cm-wide panel.
    assert spec.char_width_px == pytest.approx(16.46, abs=0.05)
    assert spec.char_width_px != pytest.approx(spec.font_px * 0.6)
    assert "Laurinavichyute2019" in spec.source


def test_bscii_does_not_inherit_the_bsc_apparatus():
    """R49 -- Yan, Pan & Kliegl 2025, Apparatus.

    BSC-II is a different lab setup a decade after BSC, not the same one: a
    24.5" LCD at 1920x1080 / 70 cm / 0.909 characters per degree, against BSC's
    19" CRT at 1024x768 / 43 cm / 0.75. Inheriting BSC's numbers would have
    been wrong by ~2x in pixels per degree (21 vs 44) -- and would have looked
    perfectly consistent in the table, since the two corpora are the same
    group's successive Chinese sentence corpora.
    """
    spec = display_spec_for("bscii")
    bsc = display_spec_for("bsc")
    assert (spec.width_px, spec.height_px) == (1920, 1080)
    assert (bsc.width_px, bsc.height_px) == (1024, 768)
    assert spec.char_width_px == pytest.approx(48, rel=0.01)  # 1.1 deg at 70 cm
    # px per degree = char width x characters per degree; the ~2x gap is the
    # whole reason the two entries cannot share numbers.
    assert spec.char_width_px * 0.909 == pytest.approx(43.6, abs=0.5)
    assert bsc.char_width_px * 0.75 == pytest.approx(21.3, abs=0.5)
    # A Song-font CJK cell is square, so the character width IS the font size.
    assert spec.font_px == pytest.approx(spec.char_width_px, rel=0.01)
    assert "YanPanKliegl2025" in spec.source


@pytest.mark.parametrize("dataset", ["onestop", "rsc", "bscii"])
def test_the_three_published_corpora_leave_the_synthesized_tier(dataset):
    _, report = resolve_geometry(dataset, TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_RECONSTRUCTED
    assert report["display_source"] == display_spec_for(dataset).source


def test_psc2_stays_synthesized_because_the_published_setup_is_another_experiment():
    """R49's trap, pinned so nobody "fixes" it.

    A complete apparatus IS published for the PSC2 sentences -- 1280x960,
    Courier New 24 pt, 14 px per letter, 60 cm (Laubrock & Kliegl 2015) -- but
    it belongs to the 32-reader ORAL reading experiment, which is already in
    this table as `eyevoicespan`. The corpus shipped as `psc2` is a 149-reader
    SILENT reading collection whose only cited document has no methods section
    at all. Copying those numbers across would be confidently, invisibly wrong:
    the two corpora would become indistinguishable here and nothing in the data
    would reveal it. If you arrived at this test holding the eye-voice-span
    paper, that paper is the reason the entry is absent, not the reason to add
    it.
    """
    assert display_spec_for("psc2") is DEFAULT_SPEC
    _, report = resolve_geometry("psc2", TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    # The tell: psc2 must not silently acquire eyevoicespan's screen.
    assert display_spec_for("psc2") != display_spec_for("eyevoicespan")
    assert (
        display_spec_for("eyevoicespan").width_px,
        display_spec_for("eyevoicespan").height_px,
    ) == (1280, 960)


@pytest.mark.parametrize(
    "dataset",
    [
        # R50: both MECO L2 waves -- same sites, same protocol, same materials,
        # so they are decided together. `mecol2w2` used to carry
        # `_spec(1920, 1080, 21, ...)`; neither of its two cited sources
        # contains that screen. The SSLA Wave 2 paper never prints "1920", says
        # font size ranges 20-22 *points* "given variation in screen size and
        # resolution at different testing sites", names one site (Zurich) at
        # 10 pt and 1280x1024, and defers the rest to supplementary S2; the UZH
        # review row has a null resolution and a LINK to those same
        # supplementary materials where a monitor would go.
        "mecol2w1",
        "mecol2w2",
        # R49: MECO L1 is multi-lab by construction too -- Wave 1 states that a
        # common font size, viewing distance and resolution were "unfeasible",
        # Wave 2 tabulates 16 different screens.
        "mecol1w1",
        "mecol1w2",
        # R49: partial (physical geometry but no pixel resolution and no font
        # size for readingbrain; a monitor's physical size and nothing else for
        # oasstetc), or nothing published at all.
        "readingbrain",
        "readingbrainl2",
        "oasstetc",
        "adegbts",
    ],
)
def test_corpora_with_no_published_corpus_level_screen_stay_synthesized(dataset):
    """A corpus whose screen is per-site, partial, or unpublished stays
    `synthesized`, and that is the tier doing its job -- it tells the user the
    geometry is invented. A plausible-but-unsourced `reconstructed` is worse
    than an honest `synthesized`, because the user cannot tell it is a guess.
    """
    assert display_spec_for(dataset) is DEFAULT_SPEC
    _, report = resolve_geometry(dataset, TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED


def test_no_spec_reads_a_point_size_as_a_pixel_size():
    """R50's unit error, generalised.

    `font_px` is pixels. Points are not pixels: at a reading-study screen
    density a point is ~1.3 px, so a point size copied into this field renders
    the text ~25% small and, through `line_pitch_px`, packs the lines the same
    way. The removed `mecol2w2` entry carried `font_px=21` -- the midpoint of a
    published *20-22 pt* range. There is no way to detect the mistake from the
    number alone, so what this pins is the shape of the table: every entry that
    quotes a point size in its comment converts it, and 8 px is below anything
    a legible reading stimulus was ever rendered at.
    """
    for name, spec in DISPLAY_SPECS.items():
        assert spec.font_px >= 12, f"{name}: font_px={spec.font_px} looks like points"


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


def test_extract_eyelink_boxes_rejects_a_negative_coordinate_box():
    """R28: a negative screen coordinate is malformed data, not a real box."""
    frame = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [0],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, -500, -80, 60, 40]"
            ],
        }
    )
    assert extract_eyelink_boxes(frame).empty


def test_extract_eyelink_boxes_rejects_a_box_straddling_the_origin():
    """R28: not representable on a 0-origin canvas even though end_x > 0."""
    frame = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [0],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, -5, 20, 40, 40]"],
        }
    )
    assert extract_eyelink_boxes(frame).empty


def test_extract_eyelink_boxes_returns_empty_when_paragraph_col_is_absent():
    """R33: `paragraph_col` is indexed alongside `ia_col` and must be guarded
    the same way `data_col` already is -- mirroring the discipline
    `extract_text_df_boxes` established (R23/R28)."""
    frame = pd.DataFrame(
        {
            "ia_index": [0],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 10, 20, 60, 40]"],
        }
    )
    assert extract_eyelink_boxes(frame).empty


def test_extract_eyelink_boxes_returns_empty_when_ia_col_is_absent():
    """R33: same as above, for `ia_col`."""
    frame = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 10, 20, 60, 40]"],
        }
    )
    assert extract_eyelink_boxes(frame).empty


def test_extract_eyelink_boxes_returns_empty_when_both_harmonised_columns_are_absent():
    """R33 -- the actual onestop shape: an un-prefixed `paragraph_id` and no
    interest-area index column at all, alongside the raw EyeLink data
    column."""
    frame = pd.DataFrame(
        {
            "paragraph_id": ["p1"],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 10, 20, 60, 40]"],
        }
    )
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
    filled, _interpolated = fill_missing_boxes(boxes, {"p1": 3}, SPEC)

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


def test_resolve_geometry_falls_through_when_raw_frame_lacks_harmonised_ia_columns():
    """R33 headline: the actual onestop failure. Its raw EyeLink export
    carries `CURRENT_FIX_INTEREST_AREA_DATA` (so `run_prepare_data` picks it
    as the raw tier's data source) but neither `unique_paragraph_id` nor
    `ia_index` -- it has an un-prefixed `paragraph_id` and no interest-area
    index at all, because it is the untouched EyeLink export rather than a
    harmonised frame. `extract_eyelink_boxes` must not raise `KeyError`
    indexing those two unguarded columns; `resolve_geometry` must fall
    through to the next tier and stamp `geometry_source` accordingly rather
    than sinking the whole corpus.

    R49 changed *which* tier that is for onestop -- the corpus now has a
    published screen, so the fall-through lands on `reconstructed` rather than
    `synthesized`. The property under test is unchanged: no raise, and no
    `real` stamp for a raw frame that contributed no box. A spec-less corpus
    given the identical frame still falls all the way to `synthesized`, which
    is what keeps this a fall-through test rather than a tier-name test."""
    raw = pd.DataFrame(
        {
            "paragraph_id": ["p1", "p1"],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 70, 20, 120, 40]",
            ],
        }
    )
    words, report = resolve_geometry("onestop", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_RECONSTRUCTED
    assert (words["geometry_source"] == GEOMETRY_RECONSTRUCTED).all()

    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


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
    assert placed.loc[0, "fixation_y_source"] == "word-box-center"


def test_place_fixations_uses_recorded_y_only_with_real_boxes():
    words = pd.DataFrame(
        {
            "unique_paragraph_id": ["real", "reconstructed"],
            "ia_index": [0, 0],
            "start_x": [10.0, 10.0],
            "end_x": [60.0, 60.0],
            "start_y": [20.0, 20.0],
            "end_y": [40.0, 40.0],
            "geometry_source": [GEOMETRY_REAL, GEOMETRY_RECONSTRUCTED],
        }
    )
    fix = pd.DataFrame(
        {
            "unique_paragraph_id": ["real", "reconstructed"],
            "ia_index": [0, 0],
            "fix_landing_position": [0.5, 0.5],
            "recorded_fixation_y": [23.25, 23.25],
        }
    )
    placed = place_fixations(fix, words)
    assert placed["y"].tolist() == [23.25, 30.0]
    assert placed["fixation_y_source"].tolist() == [
        "recorded",
        "word-box-center",
    ]


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


def test_a_dot_sentinel_ia_index_does_not_raise_or_earn_the_real_stamp():
    # EyeGenBench's own docstrings document "." as a valid CURRENT_FIX_INTEREST_AREA_ID
    # missing-value sentinel (the same "landed on no interest area" event as the
    # -1 case above), and we parse the raw file directly rather than EyeGenBench's
    # coerced frame -- so this is the expected shape, not exotic input. Must
    # resolve, not raise `ValueError: invalid literal for int() with base 10: '.'`.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": ["."],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 500, 20, 560, 40]"],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert report["paragraphs_without_real_boxes"] == 1
    assert report["interpolated_fraction"] == 1.0
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_a_nan_ia_index_does_not_raise_or_earn_the_real_stamp():
    # EyeGenBench's other documented sentinel for the same event, np.nan
    # itself rather than the string ".". Must resolve, not raise
    # `ValueError: cannot convert float NaN to integer`.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [float("nan")],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 500, 20, 560, 40]"],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert report["paragraphs_without_real_boxes"] == 1
    assert report["interpolated_fraction"] == 1.0
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_a_dot_row_alongside_a_real_row_still_earns_real_and_is_interpolated():
    # One genuinely fixated interest area (ia_index=0, a real box) plus one
    # that landed on no interest area at all (ia_index="."), same paragraph.
    # Per Ruling R8 the tier is stamped per PARAGRAPH: p1 contributed a real
    # box, so the whole paragraph -- and both its rows -- read `real` (this is
    # the same per-paragraph granularity round 1 already established, not a
    # new distinction). The "." interest area itself is simply interpolated
    # like any other gap: it must not raise, must not be treated as its own
    # real box, and must land somewhere distinct from ia_index 0 (never a
    # crash, never a guess masquerading as measured geometry).
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, "."],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 500, 20, 560, 40]",
            ],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_REAL
    assert report["paragraphs_without_real_boxes"] == 0
    assert report["interpolated_fraction"] == 0.5
    assert (words["geometry_source"] == GEOMETRY_REAL).all()
    real_box = words.loc[words["ia_index"] == 0].iloc[0]
    interpolated_box = words.loc[words["ia_index"] == 1].iloc[0]
    assert real_box["start_x"] == 10
    # Interpolated, not a copy of the real box and not the malformed row's own
    # (unusable) coordinates (500) either.
    assert interpolated_box["start_x"] not in (real_box["start_x"], 500)


def test_a_negative_fractional_ia_index_does_not_earn_the_real_stamp():
    # -0.5 is doubly invalid: negative (like the -1 case) AND fractional. A
    # coercion that only checks `>= 0` would keep it (-0.5 >= 0 is False, so
    # this alone doesn't reproduce the bug) -- the real hazard is int(-0.5)
    # truncating TOWARD ZERO to 0, landing the malformed row's own raw box at
    # slot 0 un-interpolated. Assert the box actually placed at slot 0 is the
    # interpolated one, not the malformed row's raw (900, 950) coordinates.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [-0.5],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 900, 20, 950, 40]"],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert report["paragraphs_without_real_boxes"] == 1
    assert report["interpolated_fraction"] == 1.0
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()
    slot0 = words.loc[words["ia_index"] == 0].iloc[0]
    assert slot0["start_x"] != 900, (
        "the malformed row's raw box leaked through un-interpolated"
    )


def test_a_fractional_ia_index_does_not_silently_overwrite_the_genuine_box():
    # The worst variant: ia_index=0 is a genuine real box at (10, 60);
    # ia_index=0.9 is bogus and (before validation) truncates to the SAME
    # slot 0. If both were allowed into the lookup keyed by int(ia_index),
    # boxes sorted ascending would insert 0 before 0.9 and the dict's
    # last-write-wins semantics would let the bogus row's box (900, 950)
    # silently overwrite the measured one -- wrong geometry still labelled
    # `real`. Assert slot 0 keeps the genuine box.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, 0.9],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 900, 20, 950, 40]",
            ],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_REAL
    slot0 = words.loc[words["ia_index"] == 0].iloc[0]
    assert slot0["start_x"] == 10
    assert slot0["start_x"] != 900
    # The bogus 0.9 row contributed nothing: only one real box (index 0), so
    # half of the paragraph's interest areas were interpolated (slot 1).
    assert report["interpolated_fraction"] == 0.5


def test_a_fractional_ia_index_alone_contributes_no_box():
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [1.7],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 900, 20, 950, 40]"],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert report["paragraphs_without_real_boxes"] == 1
    assert report["interpolated_fraction"] == 1.0
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


@pytest.mark.parametrize(
    "bad_ia_index", [".", float("nan"), "abc", -1, -0.5, 0.9, 1.7, 99]
)
def test_no_flavour_of_invalid_ia_index_ever_earns_the_real_stamp(bad_ia_index):
    # One place asserting `_valid_ia_index` and `fill_missing_boxes` agree on
    # the whole invalid set: EyeGenBench's documented sentinels ("." / NaN),
    # unparseable text, negative, fractional (negative-and-fractional, and
    # positive-fractional), and simply past the end (99, for this 2-word
    # paragraph). None of these may resolve to `real` or raise.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [bad_ia_index],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 900, 20, 950, 40]"],
        }
    )
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def _resolve_with_warnings_as_errors(dataset, text_df, raw_fix_df):
    """`resolve_geometry`, promoting any warning to an exception.

    Round 3's `.astype("Int64")` emitted a silent `RuntimeWarning: invalid
    value encountered in cast` alongside its `TypeError` on an oversized
    ``ia_index`` -- test output must be pristine, not merely non-crashing.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return resolve_geometry(dataset, text_df, raw_fix_df)


def test_an_ia_index_past_int64_range_resolves_without_raising_or_warning():
    # 2**63 is exactly one past the signed-64-bit range a fixed-width Int64
    # cast can hold (2**63 - 1 was already fine). Nothing here bounds the
    # *magnitude* of an otherwise valid-shaped index -- only the existing
    # `< count` check does, the same one that already rejects a merely
    # past-the-end value -- so this must resolve like any other oversized
    # index: no `real` stamp, no exception, no warning.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [2**63],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 900, 20, 950, 40]"],
        }
    )
    words, report = _resolve_with_warnings_as_errors("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_a_huge_float_ia_index_resolves_without_raising_or_warning():
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [1e19],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 900, 20, 950, 40]"],
        }
    )
    words, report = _resolve_with_warnings_as_errors("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_an_infinite_ia_index_resolves_without_raising_or_warning():
    # Previously OverflowError -- `_valid_ia_index`'s explicit finite check
    # closes it, the same way the whole-number check closes fractional
    # values and the >= 0 check closes negative ones.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [float("inf")],
            "CURRENT_FIX_INTEREST_AREA_DATA": ["[STATIC, RECTANGLE, 900, 20, 950, 40]"],
        }
    )
    words, report = _resolve_with_warnings_as_errors("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_an_oversized_ia_index_does_not_poison_the_genuine_boxes_beside_it():
    # The worst variant round 4 found: two real, well-formed boxes (indices 0
    # and 1) plus one 2**63 row, all on the same paragraph. A fixed-width
    # cast over the whole per-paragraph series raises the moment it hits the
    # huge value -- which would take down BOTH genuine boxes with it, a
    # harder failure than any earlier round (those mislabelled a paragraph;
    # this would abort resolving it at all). Assert both real boxes still
    # resolve with their own coordinates and the oversized row contributes
    # nothing -- no interpolation needed, since the two real indices (0, 1)
    # already cover this 2-word paragraph completely.
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1", "p1"],
            "ia_index": [0, 1, 2**63],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 70, 20, 120, 40]",
                "[STATIC, RECTANGLE, 900, 20, 950, 40]",
            ],
        }
    )
    words, report = _resolve_with_warnings_as_errors("cfiltsarcasm", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_REAL
    assert report["interpolated_fraction"] == 0.0
    assert words.loc[words["ia_index"] == 0, "start_x"].item() == 10
    assert words.loc[words["ia_index"] == 1, "start_x"].item() == 70
    assert (words["geometry_source"] == GEOMETRY_REAL).all()


# --- R23/R24: real boxes carried directly on text_df (verified: PoTeC) -----
#
# The real EyeGenBench frames are richer than the documented schema: text_df
# is one row per (paragraph, interest area) -- not one row per paragraph --
# and (for some corpora) carries its own genuinely measured start_x/start_y/
# end_x/end_y, and fix_df carries those same four column names too. Both
# facts, together, are what produced the R24 KeyError and the R23 honesty
# inversion (synthesizing a layout while real boxes sat unused in the frame).

TEXT_DF_WITH_BOXES = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1", "p1"],
        "ia_index": [0, 1],
        "text": ["ab cd", "ab cd"],
        "text_language": ["en", "en"],
        "ia_list": [["ab", "cd"], ["ab", "cd"]],
        "start_x": [10.0, 70.0],
        "start_y": [20.0, 20.0],
        "end_x": [60.0, 120.0],
        "end_y": [40.0, 40.0],
    }
)


def test_extract_text_df_boxes_returns_empty_when_the_columns_are_absent():
    assert extract_text_df_boxes(TEXTS).empty


def test_extract_text_df_boxes_falls_through_when_ia_index_is_missing():
    """Round-3 regression (item 1): the four box columns alone are not enough
    -- TEXTS (the brief's own fixture) has box-less columns AND no ia_index.
    A text_df carrying the box columns but not ia_index must resolve to
    empty (falling through to the existing tiers), not raise KeyError and
    drop the whole dataset from the manifest.
    """
    box_columns_no_ia_index = TEXT_DF_WITH_BOXES.drop(columns=["ia_index"])
    assert extract_text_df_boxes(box_columns_no_ia_index).empty
    _words, report = resolve_geometry("potec", box_columns_no_ia_index, None)
    assert report["geometry_source"] == GEOMETRY_RECONSTRUCTED


def test_place_fixations_uses_the_words_box_even_when_fix_df_has_its_own():
    """R24 regression: fix_df carrying its own start_x/... must not crash the
    merge, and the box used for placement must be the words frame's, never
    fix_df's own (different) values -- which survive untouched as
    passthrough data on the output.
    """
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
            # fix_df's own (different) box columns -- must be ignored for
            # placement, and must not raise a KeyError on the merge.
            "start_x": [999.0],
            "end_x": [999.0],
            "start_y": [999.0],
            "end_y": [999.0],
        }
    )
    placed = place_fixations(fix, words)
    assert placed.loc[0, "x"] == 35.0  # from the words box: 10 + 0.5 * 50
    assert placed.loc[0, "y"] == 30.0
    assert placed.loc[0, "start_x"] == 999.0  # fix_df's own column, untouched


def test_resolve_geometry_uses_real_boxes_straight_off_text_df():
    words, report = resolve_geometry("potec", TEXT_DF_WITH_BOXES, None)
    assert report["geometry_source"] == GEOMETRY_REAL
    assert report["display_source"] == "eyegenbench:texts"
    assert report["interpolated_fraction"] == 0.0
    box0 = words.loc[words["ia_index"] == 0].iloc[0]
    box1 = words.loc[words["ia_index"] == 1].iloc[0]
    # Passed through unchanged -- exact coordinates, not just presence.
    assert (box0["start_x"], box0["end_x"], box0["start_y"], box0["end_y"]) == (
        10.0,
        60.0,
        20.0,
        40.0,
    )
    assert (box1["start_x"], box1["end_x"], box1["start_y"], box1["end_y"]) == (
        70.0,
        120.0,
        20.0,
        40.0,
    )


def test_text_df_boxes_win_over_raw_eyelink_boxes_when_both_are_present():
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, 1],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 999, 999, 1999, 1999]",
                "[STATIC, RECTANGLE, 999, 999, 1999, 1999]",
            ],
        }
    )
    words, report = resolve_geometry("potec", TEXT_DF_WITH_BOXES, raw)
    assert report["display_source"] == "eyegenbench:texts"
    box0 = words.loc[words["ia_index"] == 0].iloc[0]
    assert box0["start_x"] == 10.0  # text_df's box, not the raw EyeLink 999s


TEXT_DF_INVALID_BOXES = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1", "p1", "p1"],
        "ia_index": [0, 1, -1],
        "text": ["ab cd ef"] * 3,
        "text_language": ["en"] * 3,
        "ia_list": [["ab", "cd", "ef"]] * 3,
        "start_x": [100.0, float("inf"), 5.0],
        "start_y": [20.0, 20.0, 20.0],
        "end_x": [50.0, 120.0, 55.0],  # row 0: start_x >= end_x
        "end_y": [40.0, 40.0, 40.0],
    }
)


def test_invalid_text_df_boxes_do_not_earn_real_and_fall_back_to_reconstructed():
    """Three different ways a row can be invalid -- start_x >= end_x, a
    non-finite coordinate, and a negative ia_index -- and none of them may
    earn the `real` stamp. With no valid box left, the paragraph falls all
    the way back to the reconstructed tier.
    """
    assert extract_text_df_boxes(TEXT_DF_INVALID_BOXES).empty
    words, report = resolve_geometry("potec", TEXT_DF_INVALID_BOXES, None)
    assert report["geometry_source"] == GEOMETRY_RECONSTRUCTED
    assert (words["geometry_source"] == GEOMETRY_RECONSTRUCTED).all()


TEXT_DF_NEGATIVE_BOX = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1", "p1"],
        "ia_index": [0, 1],
        "text": ["ab cd", "ab cd"],
        "text_language": ["en", "en"],
        "ia_list": [["ab", "cd"], ["ab", "cd"]],
        "start_x": [-500.0, 70.0],
        "start_y": [-80.0, 20.0],
        "end_x": [60.0, 120.0],
        "end_y": [40.0, 40.0],
    }
)


def test_extract_text_df_boxes_rejects_a_negative_coordinate_box():
    """R28: a negative screen coordinate is malformed data, not a real box."""
    boxes = extract_text_df_boxes(TEXT_DF_NEGATIVE_BOX)
    assert list(boxes["ia_index"]) == [1]  # only the valid row survives


def test_resolve_geometry_negative_box_is_interpolated_not_used_as_is():
    """The paragraph still reads `real` overall (ia_index 1's box IS real --
    same per-paragraph stamping R8/round-1 already established), but the
    rejected negative box at ia_index 0 must never reach the words frame
    as-is: `fill_missing_boxes` interpolates it instead, honestly, and the
    interpolation can never itself produce a negative coordinate.
    """
    words, report = resolve_geometry("potec", TEXT_DF_NEGATIVE_BOX, None)
    assert report["geometry_source"] == GEOMETRY_REAL
    assert (words["geometry_source"] == GEOMETRY_REAL).all()
    assert report["interpolated_fraction"] > 0.0
    # The rejected negative box's own coordinates never reach the words frame.
    assert not (words["start_x"] < 0).any()
    assert not (words["start_y"] < 0).any()


TEXT_DF_ORIGIN_STRADDLING_BOX = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1", "p1"],
        "ia_index": [0, 1],
        "text": ["ab cd", "ab cd"],
        "text_language": ["en", "en"],
        "ia_list": [["ab", "cd"], ["ab", "cd"]],
        "start_x": [-5.0, 70.0],
        "start_y": [20.0, 20.0],
        "end_x": [40.0, 120.0],  # row 0: start_x < end_x, but start_x < 0
        "end_y": [40.0, 40.0],
    }
)


def test_extract_text_df_boxes_rejects_a_box_straddling_the_origin():
    """R28: start_x=-5 < end_x=40 passes the shape check but is still not
    representable on a 0-origin canvas -- must be rejected all the same.
    """
    boxes = extract_text_df_boxes(TEXT_DF_ORIGIN_STRADDLING_BOX)
    assert list(boxes["ia_index"]) == [1]


def test_a_corpus_without_text_df_box_columns_resolves_exactly_as_before():
    """Regression pin (R23): a corpus whose text_df carries no start_x/...
    columns must resolve byte-identically to the pre-R23 behaviour -- the new
    highest-priority tier is a no-op for the other 38 corpora.
    """
    assert extract_text_df_boxes(TEXTS).empty
    words, report = resolve_geometry("potec", TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_RECONSTRUCTED
    assert report["display_source"].startswith("pymovements")
    assert len(words) == 2
