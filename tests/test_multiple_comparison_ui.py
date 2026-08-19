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
    gens, n_total = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "model", "p1", "t1"
    )
    # The comparison field is a selector. The other human trial survives even
    # though it is text B; the selected p1/t1 trial is excluded.
    assert set(gens) == {"pX · tX"}
    assert n_total == 1
    assert set(gens["pX · tX"]["text_id"]) == {"B"}


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
    gens, _ = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "participant_id", "p1", "t1"
    )
    # Participant matching crosses texts and returns one panel per trial.
    assert set(gens) == {"p1 · t4"}


def test_collect_generations_none_when_only_selected_matches():
    fix = _gen_fixations()
    # Claude occurs only on p3/t3, so no other trial matches that value.
    gens, n_total = _collect_generations(
        fix, fix[fix["trial_id"] == "t3"], "model", "p3", "t3"
    )
    assert gens == {} and n_total == 0


def test_collect_generations_can_match_on_paragraph_id():
    fix = _gen_fixations(text_col="paragraph_id")
    assert "text_id" not in fix.columns
    gens, _ = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "paragraph_id", "p1", "t1"
    )
    # Matching on the text field yields the other readings of A, one per trial.
    assert set(gens) == {"p2 · t2", "p3 · t3"}


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
    gens, n_total = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "gen", "p1", "t1"
    )
    # Each matching trial gets its own panel; the string "0" is not int 0.
    assert n_total == 2
    assert set(gens) == {"p2 · t2", "p4 · t4"}


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

    settings = _comparison_panel_settings({"show_word_labels": True})
    assert settings["show_word_labels"] is True
