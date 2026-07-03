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


def test_collect_generations_scopes_to_text_and_excludes_selected():
    fix = _gen_fixations()
    gens, n_total = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "model", "p1", "t1"
    )
    # Same text (pA) only — the pB row's "human" generation must not appear; the
    # selected trial (p1/t1, human) is excluded, leaving gpt + claude.
    assert set(gens) == {"gpt", "claude"}
    assert n_total == 2
    assert set(gens["gpt"]["participant_id"]) == {"p2"}


def test_collect_generations_by_participant_id():
    fix = _gen_fixations()
    gens, _ = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "participant_id", "p1", "t1"
    )
    # Grouping the same text by reader: the two OTHER readers of pA.
    assert set(gens) == {"p2", "p3"}


def test_collect_generations_none_when_only_selected_matches():
    fix = _gen_fixations()
    # text B is read only by pX, so pX/tX has no OTHER generations of its text.
    gens, n_total = _collect_generations(
        fix, fix[fix["trial_id"] == "tX"], "model", "pX", "tX"
    )
    assert gens == {} and n_total == 0


def test_collect_generations_scopes_by_paragraph_id_fallback():
    # When the fixations carry paragraph_id (not text_id), scoping still works —
    # the text column is picked from the canonical priority list.
    fix = _gen_fixations(text_col="paragraph_id")
    assert "text_id" not in fix.columns
    gens, _ = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "model", "p1", "t1"
    )
    # Still scoped to text A (text B's "human" row must not appear).
    assert set(gens) == {"gpt", "claude"}


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


def test_collect_generations_disambiguates_stringified_collisions():
    # Distinct values that stringify identically (int 1 vs str "1" in a mixed
    # object column) must not collapse into one generation or under-count.
    fix = pd.DataFrame(
        {
            "participant_id": ["p1", "p2", "p3", "p4"],
            "trial_id": ["t1", "t2", "t3", "t4"],
            "text_id": ["A", "A", "A", "A"],
            "gen": [0, 1, "1", 2],  # int 1 and str "1" both stringify to "1"
            "x": [1.0, 2.0, 3.0, 4.0],
            "y": [1.0, 1.0, 1.0, 1.0],
            "duration_ms": [1, 1, 1, 1],
            "order_in_trial": [1, 1, 1, 1],
        }
    )
    gens, n_total = _collect_generations(
        fix, fix[fix["trial_id"] == "t1"], "gen", "p1", "t1"
    )
    # Selected p1/t1 (gen=0) excluded → three distinct others (1, "1", 2) survive.
    assert n_total == 3
    assert len(gens) == 3
