"""Tests for the vertical drift-correction algorithms (PRE-3).

Two layers:

- **Recovery** on a clean, hand-built multi-line layout (mild drift, no
  outliers) — every one of the ten algorithms should reassign each fixation to
  its true line.
- **Integration + invariants** on the shared synthetic 2-line trial (which
  carries one far out-of-text fixation): `correct` snaps in-text fixations to a
  real line center and returns a line Series with the same semantics as
  `measures.assign_fixation_lines`. Some algorithms legitimately diverge from
  the naive nearest-line baseline here (the outlier pollutes their global
  y-statistics), so the trial-level assertions check invariants, not the exact
  baseline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import alignment
from tests.synthetic_data import make_synthetic_fixations, make_synthetic_words

# A clean 3-line layout, lines wide enough that compare's return-sweep detector
# (512 px default) fires on the line breaks. 4 words per line.
_LINE_Y = np.array([100.0, 200.0, 300.0])
_WORD_XY = np.array(
    [[x, y] for y in _LINE_Y for x in (100.0, 300.0, 500.0, 700.0)], dtype=float
)
# One fixation per word, read line-by-line left→right, with a few px of downward
# drift per line — the true line is encoded in _TRUE.
_FIX_XY = np.array(
    [
        [100, 104],
        [300, 106],
        [500, 108],
        [700, 110],
        [100, 205],
        [300, 207],
        [500, 209],
        [700, 211],
        [100, 306],
        [300, 308],
        [500, 310],
        [700, 312],
    ],
    dtype=float,
)
_TRUE = np.array([0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2])


@pytest.mark.parametrize("method", alignment.ALGORITHMS)
def test_assign_lines_shape_and_range(method):
    out = alignment.assign_lines(_FIX_XY, _LINE_Y, word_XY=_WORD_XY, method=method)
    assert isinstance(out, np.ndarray)
    assert out.dtype == np.int_ or np.issubdtype(out.dtype, np.integer)
    assert out.shape == (len(_FIX_XY),)
    assert out.min() >= 0 and out.max() < len(_LINE_Y)


@pytest.mark.parametrize("method", alignment.ALGORITHMS)
def test_recovers_clean_multiline_layout(method):
    out = alignment.assign_lines(_FIX_XY, _LINE_Y, word_XY=_WORD_XY, method=method)
    assert np.array_equal(out, _TRUE), f"{method}: {out.tolist()} != {_TRUE.tolist()}"


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        alignment.assign_lines(_FIX_XY, _LINE_Y, method="nope")


# --- DataFrame wrapper `correct` on the shared synthetic trial ----------------

_LINE_CENTERS = {110.0, 210.0}  # the synthetic 2-line trial's line centers


@pytest.mark.parametrize("method", alignment.ALGORITHMS)
def test_correct_snaps_to_line_centers(method):
    words = make_synthetic_words()
    fixations = make_synthetic_fixations()
    corrected, line = alignment.correct(fixations, words, method)

    # Same shape / index as the input; line Series matches assign_fixation_lines.
    assert len(corrected) == len(fixations)
    assert list(corrected.index) == list(fixations.index)
    assert list(line.index) == list(fixations.index)

    # Every snapped y is exactly one of the two line centers.
    assert set(round(float(y), 1) for y in corrected["y"]) <= _LINE_CENTERS
    # Assignments are valid 0-based line indices (only two lines here).
    assert set(int(v) for v in line.dropna()) <= {0, 1}
    # The synthetic trial has all-finite coords, so nothing is left unassigned.
    assert line.notna().all()


@pytest.mark.parametrize("method", ["attach", "chain", "split", "stretch", "warp"])
def test_correct_recovers_synthetic_lines(method):
    """The robust algorithms recover the hand-traced line structure even with the
    out-of-text fixation present."""
    words = make_synthetic_words()
    fixations = make_synthetic_fixations()
    _, line = alignment.correct(fixations, words, method)
    # Expected fixation→line (the out-of-text fix snaps to line 1).
    assert list(line.astype(int)) == [0, 0, 0, 0, 0, 1, 1, 1, 1]


def test_snap_false_leaves_coordinates_unchanged():
    words = make_synthetic_words()
    fixations = make_synthetic_fixations()
    corrected, line = alignment.correct(fixations, words, "attach", snap=False)
    pd.testing.assert_series_equal(corrected["y"], fixations["y"])
    # Assignments are still produced even when coordinates are not snapped.
    assert line.notna().all()


def test_single_line_passthrough():
    words = make_synthetic_words()
    # Collapse all words onto one line → no vertical drift to correct.
    words = words.assign(y=100, height=20)
    fixations = make_synthetic_fixations()
    corrected, line = alignment.correct(fixations, words, "cluster")
    pd.testing.assert_series_equal(corrected["y"], fixations["y"])
    assert line.isna().all()


def test_empty_fixations_passthrough():
    words = make_synthetic_words()
    empty = make_synthetic_fixations().iloc[0:0]
    corrected, line = alignment.correct(empty, words, "attach")
    assert corrected.empty
    assert line.empty


def test_nan_coords_left_unassigned():
    words = make_synthetic_words()
    fixations = make_synthetic_fixations().copy()
    fixations.loc[fixations.index[0], "y"] = np.nan
    corrected, line = alignment.correct(fixations, words, "attach")
    # The NaN-coord fixation is dropped from the algorithm input → NaN line, y
    # unchanged (still NaN); the rest are assigned.
    assert np.isnan(corrected.loc[fixations.index[0], "y"])
    assert np.isnan(line.iloc[0])
    assert line.iloc[1:].notna().all()


@pytest.mark.parametrize("method", ["warp", "compare"])
def test_word_order_methods_run_without_word_xy_arg(method):
    """warp/compare need word centers; `correct` derives them from the words
    frame, so they still produce valid assignments."""
    words = make_synthetic_words()
    fixations = make_synthetic_fixations()
    _, line = alignment.correct(fixations, words, method)
    assert set(int(v) for v in line.dropna()) <= {0, 1}
