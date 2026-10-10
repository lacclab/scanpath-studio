"""Tests for the Multiple Comparison tab's table-formatting / help-text helpers.

These are pure (Styler / string) helpers, so they're unit-testable without
spinning up the full Streamlit app — guarding the best-model highlight direction
and the placeholder formatting against regressions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scanpath_studio.similarity import METRICS
from scanpath_studio.tabs import (
    _best_model_indices,
    _collect_generations,
    _comparison_panel_settings,
    _comparison_trial_words,
    _generation_column_options,
    _slice_fix_range,
    _style_similarity_table,
)

_PLACEHOLDER_LABELS = [m.label for m in METRICS if m.fn is None]


def _sample_table() -> pd.DataFrame:
    columns = ["Model"] + [m.label for m in METRICS]
    row1 = {"Model": "Model 1", "NLD": 0.30}
    row2 = {"Model": "Model 2", "NLD": 0.70}
    for label in _PLACEHOLDER_LABELS:
        row1[label] = np.nan
        row2[label] = np.nan
    return pd.DataFrame([row1, row2], columns=columns)


def test_best_model_indices_picks_min_for_nld():
    table = _sample_table()
    best = _best_model_indices(table)
    # NLD is lower-is-better -> Model 1 (row 0) is best.
    assert best["NLD"] == 0
    # Placeholder columns get no entry.
    for label in _PLACEHOLDER_LABELS:
        assert label not in best


def test_best_model_indices_ignores_all_nan_columns():
    table = _sample_table()
    table["NLD"] = np.nan
    assert _best_model_indices(table) == {}


def test_style_table_formats_placeholders_and_highlights_best():
    table = _sample_table()
    html = _style_similarity_table(table).to_html()
    # Placeholder NaN cells render as the em-dash.
    assert "—" in html
    # The best (min-NLD) cell is tinted green.
    assert "#d4edda" in html
    # Real values are formatted to 3 decimals.
    assert "0.300" in html and "0.700" in html


def test_style_table_headers_carry_direction_arrows():
    table = _sample_table()
    html = _style_similarity_table(table).to_html()
    # NLD is lower-is-better -> down arrow in its header.
    assert "NLD ↓" in html
    # The higher-is-better placeholders (ScanMatch, MultiMatch) get an up arrow.
    assert "↑" in html


def _fix_frame(n: int) -> pd.DataFrame:
    return pd.DataFrame({"order_in_trial": range(1, n + 1), "x": range(n)})


def test_slice_fix_range_windows_by_order_index():
    # VIZ-7: keep only fixations whose 1-based order index is in [start, end].
    sliced = _slice_fix_range(_fix_frame(10), (3, 6))
    assert list(sliced["order_in_trial"]) == [3, 4, 5, 6]


def test_slice_fix_range_none_is_identity():
    frame = _fix_frame(5)
    # A None window (full trial) returns the frame untouched.
    assert _slice_fix_range(frame, None) is frame
    # A frame without the order column is also returned unchanged.
    no_order = pd.DataFrame({"x": [1, 2, 3]})
    assert _slice_fix_range(no_order, (1, 2)) is no_order


# --- ENG-8: generation-column selection + collection -------------------------


def _gen_fixations(text_col: str = "text_id") -> pd.DataFrame:
    """One text (A) read by three readers + a second text (B); a `model` column
    tags each row's generation. ``text_col`` names the text identifier — real
    normalized fixations use ``text_id``, not always ``paragraph_id``."""
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2", "p3", "pX"],
            "trial_id": ["t1", "t1", "t2", "t2", "t3", "tX"],
            text_col: ["A", "A", "A", "A", "A", "B"],
            "model": ["human", "human", "gpt", "gpt", "claude", "human"],
            "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "y": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "duration_ms": [100, 120, 90, 80, 110, 70],
            "order_in_trial": [1, 2, 1, 2, 1, 1],
        }
    )


def test_generation_column_options_excludes_coordinates_and_ranks_hints():
    opts = _generation_column_options(_gen_fixations())
    # Continuous / coordinate columns are never offered as a generation id.
    for excluded in ("x", "y", "duration_ms", "order_in_trial"):
        assert excluded not in opts
    # A generation-y name ranks first; participant/trial ids come next.
    assert opts[0] == "model"
    assert set(opts) >= {"model", "participant_id", "trial_id"}


def test_generation_column_options_empty_frame():
    assert _generation_column_options(pd.DataFrame()) == []


def test_collect_generations_matches_selected_field_value_across_texts():
    fix = _gen_fixations()
    gens = _collect_generations(fix, fix[fix["trial_id"] == "t1"], "model", "p1", "t1")
    # The comparison field is a selector. The other human trial survives even
    # though it is text B; the selected p1/t1 trial is excluded.
    assert set(gens) == {("pX", "tX")}
    assert len(gens) == 1
    assert set(gens[("pX", "tX")]["text_id"]) == {"B"}


def test_collect_generations_by_participant_id():
    fix = _gen_fixations()
    fix = pd.concat(
        [
            fix,
            pd.DataFrame(
                {
                    "participant_id": ["p1"],
                    "trial_id": ["t4"],
                    "text_id": ["B"],
                    "model": ["human"],
                    "x": [7.0],
                    "y": [1.0],
                    "duration_ms": [80],
                    "order_in_trial": [1],
                }
            ),
        ],
        ignore_index=True,
    )
    gens = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "participant_id", "p1", "t1"
    )
    # Participant matching crosses texts and returns one panel per trial.
    assert set(gens) == {("p1", "t4")}


def test_collect_generations_none_when_only_selected_matches():
    fix = _gen_fixations()
    # Claude occurs only on p3/t3, so no other trial matches that value.
    gens = _collect_generations(fix, fix[fix["trial_id"] == "t3"], "model", "p3", "t3")
    assert gens == {}


def test_collect_generations_can_match_on_paragraph_id():
    fix = _gen_fixations(text_col="paragraph_id")
    assert "text_id" not in fix.columns
    gens = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "paragraph_id", "p1", "t1"
    )
    # Matching on the text field yields the other readings of A, one per trial.
    assert set(gens) == {("p2", "t2"), ("p3", "t3")}


def test_generation_column_options_excludes_within_trial_ids():
    fix = _gen_fixations()
    fix["word_id"] = [10, 11, 10, 11, 10, 12]
    fix["fixation_id"] = [1, 2, 3, 4, 5, 6]
    opts = _generation_column_options(fix)
    # Per-fixation identifiers aren't generation columns.
    assert "word_id" not in opts and "fixation_id" not in opts
    assert "model" in opts


def test_generation_column_options_skips_unhashable_columns():
    # A list/JSON-valued column (e.g. MultiplEYE comprehension_questions) must be
    # skipped, not crash nunique() with TypeError.
    fix = _gen_fixations()
    fix["questions"] = [["a"], ["b"], ["a"], ["b"], ["a"], ["c"]]
    opts = _generation_column_options(fix)  # must not raise
    assert "questions" not in opts
    assert "model" in opts


def test_collect_generations_preserves_distinct_matching_trials():
    fix = pd.DataFrame(
        {
            "participant_id": ["p1", "p2", "p3", "p4"],
            "trial_id": ["t1", "t2", "t3", "t4"],
            "text_id": ["A", "A", "A", "A"],
            "gen": [0, 0, "0", 0],
            "x": [1.0, 2.0, 3.0, 4.0],
            "y": [1.0, 1.0, 1.0, 1.0],
            "duration_ms": [1, 1, 1, 1],
            "order_in_trial": [1, 1, 1, 1],
        }
    )
    gens = _collect_generations(fix, fix[fix["trial_id"] == "t1"], "gen", "p1", "t1")
    # Each matching trial gets its own panel; the string "0" is not int 0.
    assert set(gens) == {("p2", "t2"), ("p4", "t4")}


def test_comparison_panels_use_the_candidate_words_and_keep_text_visible():
    words = pd.DataFrame(
        {
            "participant_id": ["p1", "pX"],
            "trial_id": ["t1", "tX"],
            "text_id": ["A", "B"],
            "text": ["alpha", "beta"],
        }
    )
    candidate = _gen_fixations().query("trial_id == 'tX'")

    selected_words = _comparison_trial_words(words, candidate)
    assert selected_words["text"].tolist() == ["beta"]

    settings = _comparison_panel_settings(
        {
            "show_word_labels": True,
            "color_by": None,
            "fixation_color": "#123456",
        }
    )
    assert settings["show_word_labels"] is True
    assert settings["color_by"] is None
    assert settings["fixation_color"] == "#123456"


def test_the_grid_keeps_by_line_colouring_off_when_the_rail_says_line(
    normalized_words_df, normalized_fixations_df
):
    """The grid switches by-line colouring off (`color_by_line: False`), but
    BUG-85 taught the builders to read the rail's own `color_by="line"` as
    colour-by-line too — so with the rail on "line", every panel grew per-line
    legend entries unless the grid neutralises the value as well."""
    from scanpath_studio.plots import FigureSettings, make_scanpath_figure

    settings = _comparison_panel_settings({"color_by": "line", "color_by_line": True})
    fig = make_scanpath_figure(
        normalized_words_df,
        normalized_fixations_df,
        settings=FigureSettings.from_mapping(
            settings, canvas_width=1920, canvas_height=1080, base_font_size=16
        ),
    )
    assert not [t.name for t in fig.data if str(t.name).startswith("line: ")]


def test_match_offers_same_text_first_then_conditions_once():
    """#374 F18: the two readings-of-interest lead, ids are not conditions, and
    no field is offered twice."""
    from scanpath_studio.column_names import ColumnNames
    from scanpath_studio.tabs import (
        _MATCH_SAME_PARTICIPANT,
        _MATCH_SAME_TEXT,
        _match_options,
    )

    fix = _gen_fixations()
    fix["TRIAL_INDEX"] = [1, 1, 2, 2, 3, 4]
    opts = _match_options(fix, ColumnNames({}))
    assert opts[:2] == [_MATCH_SAME_TEXT, _MATCH_SAME_PARTICIPANT]
    assert "model" in opts
    for not_a_condition in ("participant_id", "trial_id", "text_id", "TRIAL_INDEX"):
        assert not_a_condition not in opts
    assert len(opts) == len(set(opts))


def test_same_text_shows_other_participants_only():
    from scanpath_studio.tabs import _MATCH_SAME_TEXT, _resolve_match

    fix = _gen_fixations()
    # p1 rereads text A: a second trial of the same participant.
    reread = fix[fix["trial_id"] == "t1"].assign(trial_id="t1b")
    fix = pd.concat([fix, reread], ignore_index=True)
    column, differ = _resolve_match(_MATCH_SAME_TEXT, fix)
    gens = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], column, "p1", "t1", differ
    )
    assert set(gens) == {("p2", "t2"), ("p3", "t3")}


# --- #412: two readings whose ids join to the same label ---------------------

#: `(p1, "t1 · t2")` and `("p1 · t1", "t2")` both read `p1 · t1 · t2` once
#: joined, and the collector used to key on that label; `p9` sorts after both.
_LOOKALIKE_READINGS = [
    ("p0", "base"),
    ("p1", "t1 · t2"),
    ("p1 · t1", "t2"),
    ("p9", "z"),
]


def _lookalike_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    words = pd.DataFrame(
        [
            {
                "participant_id": p,
                "trial_id": t,
                "text_id": "same",
                "word_id": i,
                "text": w,
                "x": 10.0 + 60 * i,
                "y": 20.0,
                "width": 50.0,
                "height": 20.0,
            }
            for p, t in _LOOKALIKE_READINGS
            for i, w in enumerate(["one", "two"])
        ]
    )
    fixations = pd.DataFrame(
        [
            {
                "participant_id": p,
                "trial_id": t,
                "text_id": "same",
                "x": 20.0 + 60 * i,
                "y": 30.0,
                "duration_ms": 200,
                "timestamp_ms": 250 * i,
                "fixation_id": i,
                "order_in_trial": i + 1,
            }
            for p, t in _LOOKALIKE_READINGS
            for i in range(2)
        ]
    )
    return words, fixations


def test_readings_whose_labels_match_are_two_matches():
    _words, fix = _lookalike_frames()
    selected = fix[fix["participant_id"] == "p0"]
    gens = _collect_generations(fix, selected, "text_id", "p0", "base")
    assert list(gens) == [("p1", "t1 · t2"), ("p1 · t1", "t2"), ("p9", "z")]
    assert gens[("p1", "t1 · t2")]["participant_id"].unique().tolist() == ["p1"]
    assert gens[("p1 · t1", "t2")]["participant_id"].unique().tolist() == ["p1 · t1"]


def test_lookalike_readings_are_labelled_apart():
    from scanpath_studio.tabs import (
        _MATCH_SAME_PARTICIPANT,
        _panel_captions,
        _reading_labels,
    )

    readings = [("p1", "t1 · t2"), ("p1 · t1", "t2"), ("p9", "z")]
    labels = _reading_labels(readings)
    assert labels[("p9", "z")] == "p9 · z"
    assert labels[("p1", "t1 · t2")] != labels[("p1 · t1", "t2")]
    assert labels[("p1", "t1 · t2")] == "participant p1, trial t1 · t2"
    # Two of one participant's readings of a text share the caption *Text A*.
    panels = {
        (p, t): pd.DataFrame({"participant_id": [p], "trial_id": [t], "text_id": ["A"]})
        for p, t in (("p1", "a"), ("p1", "a_r2"))
    }
    captions = _panel_captions(
        _MATCH_SAME_PARTICIPANT, panels, "text_id", _reading_labels(panels)
    )
    assert captions == {
        ("p1", "a"): "Text A (p1 · a)",
        ("p1", "a_r2"): "Text A (p1 · a_r2)",
    }


def _lookalike_comparisons_app() -> None:
    from scanpath_studio import tabs
    from tests.test_mode_parity import _viz
    from tests.test_multiple_comparison_ui import _lookalike_frames

    words, fixations = _lookalike_frames()
    tabs.render_multiple_comparison_tab(
        words[words["participant_id"] == "p0"],
        fixations[fixations["participant_id"] == "p0"],
        words,
        fixations,
        selected_participant="p0",
        selected_trial="base",
        canvas_width=400,
        canvas_height=200,
        base_font_size=14,
        font_family="Arial",
        viz_settings=_viz(),
    )


def test_lookalike_readings_get_a_panel_each_on_a_page_of_two(monkeypatch):
    """#412 acceptance: both readings are drawn, each in its own panel, when
    a page holds two — and the similarity table names all three apart."""
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "_GEN_PAGE_SIZE", 2)
    at = AppTest.from_function(_lookalike_comparisons_app).run(timeout=60)
    assert not at.exception, at.exception
    panels = [c.value for c in at.caption if str(c.value).startswith("**")]
    assert len(panels) == 2, panels
    assert panels[0].startswith("**Participant p1**")
    assert panels[1].startswith("**Participant p1 · t1**")
    # The suite runs with similarity on (conftest), so every match is scored.
    trials = at.dataframe[0].value["Trial"].tolist()
    assert len(set(trials)) == len(trials) == 3, trials


# --- #422: the grid pages through every match --------------------------------


def _panel_captions_shown(at) -> list[str]:
    return [c.value for c in at.caption if str(c.value).startswith("**")]


def _count_line(at) -> str:
    return next(c.value for c in at.caption if "match" in str(c.value))


def test_the_grid_shows_one_page_and_says_how_to_see_more(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "_GEN_PAGE_SIZE", 2)
    at = AppTest.from_function(_lookalike_comparisons_app).run(timeout=60)
    assert not at.exception, at.exception
    assert len(_panel_captions_shown(at)) == 2
    assert _count_line(at) == "Showing 1–2 of 3 matches — pick a page for more."
    # A pager above the grid and one under it.
    assert len(at.get("pagination")) == 2

    at.session_state["multi_gen_page"] = 2
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert [c.split(" · NLD")[0] for c in _panel_captions_shown(at)] == [
        "**Participant p9**"
    ]
    assert _count_line(at) == "Showing 3 of 3 matches — pick a page for more."


def test_one_page_has_no_pager():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_lookalike_comparisons_app).run(timeout=60)
    assert not at.exception, at.exception
    assert _count_line(at) == "3 matches."
    assert not at.get("pagination")


def test_another_match_set_starts_on_page_one(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "_GEN_PAGE_SIZE", 2)
    at = AppTest.from_function(_lookalike_comparisons_app)
    at.session_state["multi_gen_page"] = 2
    at.session_state[tabs._GEN_PAGE_FOR_KEY] = ("another trial",)
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert _count_line(at).startswith("Showing 1–2 of 3")


def test_either_pager_moves_both(monkeypatch):
    from scanpath_studio import tabs

    state = {"multi_gen_page": 1, "multi_gen_page_end": 3}
    monkeypatch.setattr(tabs.st, "session_state", state)
    tabs._sync_gen_pages("multi_gen_page_end")
    assert state == {"multi_gen_page": 3, "multi_gen_page_end": 3}


# --- #422: the chips above the plot, for the selected trial and its matches --


def _chip_tables(at) -> list[str]:
    return [m.value for m in at.markdown if "sps-chip-table" in str(m.value)]


def test_the_matches_get_the_chip_table_one_row_each(monkeypatch):
    import re

    from streamlit.testing.v1 import AppTest

    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "_GEN_PAGE_SIZE", 2)
    at = AppTest.from_function(_lookalike_comparisons_app)
    at.session_state["trial_chip_fields"] = ["participant_id", "@fixation_count"]
    at.run(timeout=60)
    assert not at.exception, at.exception
    (table,) = _chip_tables(at)
    rows = re.findall(r'<th scope="row" class="sps-ct-side">([^<]*)</th>', table)
    # The selected trial, then the page's matches, named as their panels are.
    assert rows == ["Selected", "Participant p1", "Participant p1 · t1"]
    # The chosen fields, as the table above the plot heads them.
    assert "Number of fixations" in table
    # Every reading has two fixations: one value they share, written quieter.
    assert table.count('class="sps-ct-num sps-ct-same">2<') == 3


def test_no_chip_fields_no_table():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_lookalike_comparisons_app)
    at.session_state["trial_chip_fields"] = []
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert not _chip_tables(at)
