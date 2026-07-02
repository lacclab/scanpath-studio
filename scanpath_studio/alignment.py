"""Vertical drift-correction (line-assignment) algorithms.

Native port of the ten algorithms surveyed by

    Carr, J. W., Pescuma, V. N., Furlan, M., Ktori, M., & Crepaldi, D. (2021).
    Algorithms for the automated correction of vertical drift in eye-tracking
    data. *Behavior Research Methods*, 54, 287–310.
    https://doi.org/10.3758/s13428-021-01554-0

The reference implementations live in the companion repository
``https://github.com/jwcarr/drift`` (``algorithms.py``), released under
**CC BY 4.0**. They are adapted/modified here (returning *line assignments*
rather than mutating coordinates, plus DataFrame plumbing for this app); see
:data:`NOTICE`. We reimplement natively rather than depend on ``eyekit``, which
is GPL-3.0 and incompatible with this MIT-licensed, PyPI-distributed project.

Each fixation in a trial is assigned the index of the text line it most likely
belongs to. ``slice`` (a later eyekit addition outside the 2021 paper) is *not*
included; this module ships exactly the ten of Carr et al. (2021):

    attach, chain, cluster, compare, merge, regress, segment, split, stretch, warp

Pure functions, no Streamlit.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from scipy.cluster.vq import kmeans2
from scipy.optimize import minimize
from scipy.stats import norm

from .measures import cluster_word_lines
from .model_scanpaths import _ordered_word_rows

NOTICE = (
    "Vertical drift-correction algorithms (alignment.py) adapted from "
    "Carr, Pescuma, Furlan, Ktori & Crepaldi (2021), 'Algorithms for the "
    "automated correction of vertical drift in eye-tracking data', Behavior "
    "Research Methods. Reference code: https://github.com/jwcarr/drift "
    "(CC BY 4.0). Adapted/modified."
)

ALGORITHMS = (
    "attach",
    "chain",
    "cluster",
    "compare",
    "merge",
    "regress",
    "segment",
    "split",
    "stretch",
    "warp",
)

# Deterministic seed for the k-means based algorithms (cluster / split) so the
# same trial always yields the same assignment across reruns.
_KMEANS_SEED = 0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _dynamic_time_warping(
    sequence1: np.ndarray, sequence2: np.ndarray
) -> tuple[list[list[int]], np.ndarray]:
    """DTW between two point sequences.

    Returns ``(path, cost)`` where ``path[i]`` lists the indices of
    ``sequence2`` aligned to ``sequence1[i]`` and ``cost`` is the accumulated
    cost matrix (total cost is ``cost[-1, -1]``). Ported from ``jwcarr/drift``.
    """
    n1 = len(sequence1)
    n2 = len(sequence2)
    dtw_cost = np.zeros((n1 + 1, n2 + 1))
    dtw_cost[0, :] = np.inf
    dtw_cost[:, 0] = np.inf
    dtw_cost[0, 0] = 0
    for i in range(n1):
        for j in range(n2):
            this_cost = np.sqrt(np.sum((sequence1[i] - sequence2[j]) ** 2))
            dtw_cost[i + 1, j + 1] = this_cost + min(
                dtw_cost[i, j + 1], dtw_cost[i + 1, j], dtw_cost[i, j]
            )
    dtw_cost = dtw_cost[1:, 1:]
    dtw_path = [[] for _ in range(n1)]
    i = n1 - 1
    j = n2 - 1
    while i > 0 or j > 0:
        dtw_path[i].append(j)
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            neighbours = (
                dtw_cost[i - 1, j - 1],
                dtw_cost[i - 1, j],
                dtw_cost[i, j - 1],
            )
            best = min(neighbours)
            if dtw_cost[i - 1, j] == best:
                i -= 1
            elif dtw_cost[i, j - 1] == best:
                j -= 1
            else:
                i -= 1
                j -= 1
    dtw_path[0].append(0)
    return dtw_path, dtw_cost


def _mode(values: np.ndarray) -> float:
    """Most common value (lowest wins ties) — used by ``warp``."""
    uniq, counts = np.unique(values, return_counts=True)
    return float(uniq[np.argmax(counts)])


def _nearest_line_indices(fixation_Y: np.ndarray, line_Y: np.ndarray) -> np.ndarray:
    """Index of the nearest line center for each fixation y."""
    return np.abs(fixation_Y[:, None] - line_Y[None, :]).argmin(axis=1)


# ---------------------------------------------------------------------------
# The ten algorithms — each returns an int array of line indices (0..m-1),
# one per fixation, aligned to the rows of ``fixation_XY``.
# ---------------------------------------------------------------------------


def _attach(fixation_XY: np.ndarray, line_Y: np.ndarray, word_XY) -> np.ndarray:
    return _nearest_line_indices(fixation_XY[:, 1], line_Y)


def _chain(
    fixation_XY: np.ndarray,
    line_Y: np.ndarray,
    word_XY,
    *,
    x_thresh: float = 192,
    y_thresh: float = 32,
) -> np.ndarray:
    n = len(fixation_XY)
    assignment = np.zeros(n, dtype=int)
    dist_X = np.abs(np.diff(fixation_XY[:, 0]))
    dist_Y = np.abs(np.diff(fixation_XY[:, 1]))
    end_chain_indices = list(np.where((dist_X > x_thresh) | (dist_Y > y_thresh))[0] + 1)
    end_chain_indices.append(n)
    start_of_chain = 0
    for end_of_chain in end_chain_indices:
        mean_y = np.mean(fixation_XY[start_of_chain:end_of_chain, 1])
        line_i = int(np.argmin(np.abs(line_Y - mean_y)))
        assignment[start_of_chain:end_of_chain] = line_i
        start_of_chain = end_of_chain
    return assignment


def _cluster(fixation_XY: np.ndarray, line_Y: np.ndarray, word_XY) -> np.ndarray:
    m = len(line_Y)
    n = len(fixation_XY)
    fixation_Y = fixation_XY[:, 1].reshape(-1, 1).astype(float)
    try:
        centers, labels = kmeans2(
            fixation_Y, m, iter=100, minit="++", missing="raise", seed=_KMEANS_SEED
        )
    except Exception:
        # Degenerate clustering (e.g. an empty cluster) → naive fallback.
        return _attach(fixation_XY, line_Y, word_XY)
    order = np.argsort(centers[:, 0])
    line_for_cluster = np.empty(m, dtype=int)
    line_for_cluster[order] = np.arange(m)
    return line_for_cluster[labels.astype(int)][:n]


def _segment(fixation_XY: np.ndarray, line_Y: np.ndarray, word_XY) -> np.ndarray:
    n = len(fixation_XY)
    m = len(line_Y)
    assignment = np.zeros(n, dtype=int)
    diff_X = np.diff(fixation_XY[:, 0])
    # The m-1 largest return sweeps (most negative Δx) mark the line changes.
    line_change_indices = set(int(i) for i in np.argsort(diff_X)[: m - 1])
    current_line_i = 0
    for fixation_i in range(n):
        assignment[fixation_i] = min(current_line_i, m - 1)
        if fixation_i in line_change_indices:
            current_line_i += 1
    return assignment


def _split(fixation_XY: np.ndarray, line_Y: np.ndarray, word_XY) -> np.ndarray:
    n = len(fixation_XY)
    assignment = np.zeros(n, dtype=int)
    diff_X = np.diff(fixation_XY[:, 0]).reshape(-1, 1).astype(float)
    if len(diff_X) < 2:
        return _attach(fixation_XY, line_Y, word_XY)
    try:
        centers, labels = kmeans2(
            diff_X, 2, iter=100, minit="++", missing="raise", seed=_KMEANS_SEED
        )
    except Exception:
        return _attach(fixation_XY, line_Y, word_XY)
    # The cluster with the most negative mean Δx holds the return sweeps.
    sweep_marker = int(np.argmin(centers[:, 0]))
    end_line_indices = list(np.where(labels == sweep_marker)[0] + 1)
    end_line_indices.append(n)
    start_of_line = 0
    for end_of_line in end_line_indices:
        mean_y = np.mean(fixation_XY[start_of_line:end_of_line, 1])
        line_i = int(np.argmin(np.abs(line_Y - mean_y)))
        assignment[start_of_line:end_of_line] = line_i
        start_of_line = end_of_line
    return assignment


def _merge(
    fixation_XY: np.ndarray,
    line_Y: np.ndarray,
    word_XY,
    *,
    y_thresh: float = 32,
    gradient_thresh: float = 0.1,
    error_thresh: float = 20,
) -> np.ndarray:
    n = len(fixation_XY)
    m = len(line_Y)
    diff_X = np.diff(fixation_XY[:, 0])
    dist_Y = np.abs(np.diff(fixation_XY[:, 1]))
    boundaries = list(np.where((diff_X < 0) | (dist_Y > y_thresh))[0] + 1)
    starts = [0] + boundaries
    ends = boundaries + [n]
    sequences = [list(range(s, e)) for s, e in zip(starts, ends) if e > s]
    # Phases progressively relax the minimum sequence lengths, ending with an
    # unconstrained pass that always merges down to m lines (paper defaults).
    phases = [
        (3, 3, False),
        (1, 3, False),
        (1, 1, False),
        (1, 1, True),
    ]
    for min_i, min_j, no_constraints in phases:
        while len(sequences) > m:
            best_merger = None
            best_error = np.inf
            for i in range(len(sequences) - 1):
                if len(sequences[i]) < min_i:
                    continue
                for j in range(i + 1, len(sequences)):
                    if len(sequences[j]) < min_j:
                        continue
                    candidate = sequences[i] + sequences[j]
                    xy = fixation_XY[candidate]
                    if len(np.unique(xy[:, 0])) < 2:
                        gradient = 0.0
                        intercept = float(np.mean(xy[:, 1]))
                    else:
                        gradient, intercept = np.polyfit(xy[:, 0], xy[:, 1], 1)
                    residuals = xy[:, 1] - (gradient * xy[:, 0] + intercept)
                    error = float(np.sqrt(np.mean(residuals**2)))
                    if not no_constraints and (
                        abs(gradient) > gradient_thresh or error > error_thresh
                    ):
                        continue
                    if error < best_error:
                        best_error = error
                        best_merger = (i, j)
            if best_merger is None:
                break
            i, j = best_merger
            sequences[i] = sequences[i] + sequences[j]
            del sequences[j]
    assignment = np.zeros(n, dtype=int)
    order = sorted(
        range(len(sequences)), key=lambda s: np.mean(fixation_XY[sequences[s], 1])
    )
    for line_i, seq_i in enumerate(order):
        assignment[sequences[seq_i]] = min(line_i, m - 1)
    return assignment


def _regress(
    fixation_XY: np.ndarray,
    line_Y: np.ndarray,
    word_XY,
    *,
    slope_bounds: tuple[float, float] = (-0.1, 0.1),
    offset_bounds: tuple[float, float] = (-50, 50),
    std_bounds: tuple[float, float] = (1, 20),
) -> np.ndarray:
    n = len(fixation_XY)
    m = len(line_Y)
    fixation_X = fixation_XY[:, 0]
    fixation_Y = fixation_XY[:, 1]
    density = np.zeros((n, m))

    def fit_lines(params, return_assignment=False):
        k = slope_bounds[0] + (slope_bounds[1] - slope_bounds[0]) * norm.cdf(params[0])
        o = offset_bounds[0] + (offset_bounds[1] - offset_bounds[0]) * norm.cdf(
            params[1]
        )
        s = std_bounds[0] + (std_bounds[1] - std_bounds[0]) * norm.cdf(params[2])
        predicted = np.array([fixation_X * k + (line_y + o) for line_y in line_Y])
        for line_i in range(m):
            density[:, line_i] = norm.logpdf(fixation_Y, predicted[line_i], s)
        if return_assignment:
            return density.argmax(axis=1)
        return -np.sum(density.max(axis=1))

    best_fit = minimize(fit_lines, [0, 0, 0], method="powell")
    return np.asarray(fit_lines(best_fit.x, return_assignment=True), dtype=int)


def _stretch(
    fixation_XY: np.ndarray,
    line_Y: np.ndarray,
    word_XY,
    *,
    scale_bounds: tuple[float, float] = (0.9, 1.1),
    offset_bounds: tuple[float, float] = (-50, 50),
) -> np.ndarray:
    fixation_Y = fixation_XY[:, 1]

    def fit_lines(params, return_assignment=False):
        candidate_Y = fixation_Y * params[0] + params[1]
        nearest = _nearest_line_indices(candidate_Y, line_Y)
        if return_assignment:
            return nearest
        return float(np.sum(np.abs(candidate_Y - line_Y[nearest])))

    best_fit = minimize(
        fit_lines,
        [1.0, 0.0],
        method="nelder-mead",
        bounds=[scale_bounds, offset_bounds],
    )
    return np.asarray(fit_lines(best_fit.x, return_assignment=True), dtype=int)


def _warp(fixation_XY: np.ndarray, line_Y: np.ndarray, word_XY) -> np.ndarray:
    if word_XY is None or len(word_XY) == 0:
        return _attach(fixation_XY, line_Y, word_XY)
    n = len(fixation_XY)
    dtw_path, _ = _dynamic_time_warping(fixation_XY, word_XY)
    assignment = np.zeros(n, dtype=int)
    for fixation_i, mapped_words in enumerate(dtw_path):
        candidate_Y = word_XY[mapped_words, 1]
        line_y = _mode(candidate_Y)
        assignment[fixation_i] = int(np.argmin(np.abs(line_Y - line_y)))
    return assignment


def _compare(
    fixation_XY: np.ndarray,
    line_Y: np.ndarray,
    word_XY,
    *,
    x_thresh: float = 512,
    n_nearest_lines: int = 3,
) -> np.ndarray:
    if word_XY is None or len(word_XY) == 0:
        return _attach(fixation_XY, line_Y, word_XY)
    n = len(fixation_XY)
    assignment = np.zeros(n, dtype=int)
    diff_X = np.diff(fixation_XY[:, 0])
    end_line_indices = list(np.where(diff_X < -x_thresh)[0] + 1)
    end_line_indices.append(n)
    start_of_line = 0
    for end_of_line in end_line_indices:
        gaze_line = fixation_XY[start_of_line:end_of_line]
        mean_y = np.mean(gaze_line[:, 1])
        nearest = np.argsort(np.abs(line_Y - mean_y))[:n_nearest_lines]
        costs = np.zeros(len(nearest))
        for k, candidate_line_i in enumerate(nearest):
            text_line = word_XY[word_XY[:, 1] == line_Y[candidate_line_i]]
            if len(text_line) == 0:
                costs[k] = np.inf
                continue
            _, cost = _dynamic_time_warping(gaze_line[:, 0:1], text_line[:, 0:1])
            costs[k] = cost[-1, -1]
        line_i = int(nearest[int(np.argmin(costs))])
        assignment[start_of_line:end_of_line] = line_i
        start_of_line = end_of_line
    return assignment


_DISPATCH = {
    "attach": _attach,
    "chain": _chain,
    "cluster": _cluster,
    "compare": _compare,
    "merge": _merge,
    "regress": _regress,
    "segment": _segment,
    "split": _split,
    "stretch": _stretch,
    "warp": _warp,
}


# ---------------------------------------------------------------------------
# Public core + DataFrame wrapper
# ---------------------------------------------------------------------------


def assign_lines(
    fixation_XY: np.ndarray,
    line_Y: np.ndarray,
    *,
    word_XY: Optional[np.ndarray] = None,
    method: str = "attach",
) -> np.ndarray:
    """Assign each fixation a line index in ``[0, len(line_Y))``.

    ``fixation_XY`` is an ``(n, 2)`` float array, ``line_Y`` a sorted-ascending
    ``(m,)`` array of line centers, and ``word_XY`` an ``(k, 2)`` array of word
    centers in reading order (required by ``warp`` / ``compare``; ignored
    otherwise). Returns an int ``(n,)`` array of line indices.
    """
    if method not in _DISPATCH:
        raise ValueError(
            f"unknown alignment method {method!r}; choose from {ALGORITHMS}"
        )
    fixation_XY = np.asarray(fixation_XY, dtype=float)
    line_Y = np.asarray(line_Y, dtype=float)
    n = len(fixation_XY)
    if n == 0:
        return np.zeros(0, dtype=int)
    if len(line_Y) < 2:
        return np.zeros(n, dtype=int)
    if word_XY is not None:
        word_XY = np.asarray(word_XY, dtype=float)
    assignment = _DISPATCH[method](fixation_XY, line_Y, word_XY)
    return np.clip(np.asarray(assignment, dtype=int), 0, len(line_Y) - 1)


def _line_centers(words: pd.DataFrame) -> np.ndarray:
    """Sorted-ascending line center y-coordinates from a single-trial words frame."""
    lines = cluster_word_lines(words)
    y_center = (
        pd.to_numeric(words["y"], errors="coerce")
        + pd.to_numeric(words["height"], errors="coerce").fillna(0) / 2.0
    )
    centers = y_center.groupby(lines).mean().sort_values()
    return centers.to_numpy(dtype=float)


def _word_centers_reading_order(words: pd.DataFrame) -> np.ndarray:
    """Word-box centers ``(x_center, y_center)`` in reading order, NaN-geometry dropped."""
    ordered = _ordered_word_rows(words)
    x = pd.to_numeric(ordered["x"], errors="coerce")
    y = pd.to_numeric(ordered["y"], errors="coerce")
    w = pd.to_numeric(ordered["width"], errors="coerce")
    h = pd.to_numeric(ordered["height"], errors="coerce")
    finite = x.notna() & y.notna() & w.notna() & h.notna()
    cx = (x + w / 2.0)[finite].to_numpy(dtype=float)
    cy = (y + h / 2.0)[finite].to_numpy(dtype=float)
    return np.column_stack([cx, cy]) if len(cx) else np.empty((0, 2))


def correct(
    fixations: pd.DataFrame,
    words: pd.DataFrame,
    method: str,
    *,
    snap: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Apply a drift-correction algorithm to a single trial's fixations.

    Returns ``(corrected_fixations, assigned_line)``:

    - ``corrected_fixations`` is a copy of ``fixations`` with ``y`` snapped to
      the assigned line center when ``snap=True`` (unchanged otherwise).
    - ``assigned_line`` is a float Series (0-based line index, NaN where
      unmappable) index-aligned to ``fixations`` — the same shape/semantics as
      :func:`measures.assign_fixation_lines`, so the plots' ``color_by_line``
      path consumes it unchanged.

    Passthrough (no change, all-NaN line) when fewer than two text lines, empty
    words, or empty fixations. Fixations with non-finite coordinates are dropped
    from the algorithm input and left unassigned (NaN, y unchanged).
    """
    corrected = fixations.copy()
    assigned = pd.Series(np.nan, index=fixations.index, dtype="float64")
    if fixations.empty or words is None or words.empty:
        return corrected, assigned

    line_Y = _line_centers(words)
    if len(line_Y) < 2:
        return corrected, assigned

    fx = pd.to_numeric(fixations["x"], errors="coerce")
    fy = pd.to_numeric(fixations["y"], errors="coerce")
    finite = fx.notna() & fy.notna()
    if not finite.any():
        return corrected, assigned

    fixation_XY = np.column_stack(
        [fx[finite].to_numpy(dtype=float), fy[finite].to_numpy(dtype=float)]
    )
    word_XY = None
    if method in ("warp", "compare"):
        word_XY = _word_centers_reading_order(words)

    line_idx = assign_lines(fixation_XY, line_Y, word_XY=word_XY, method=method)
    idx = fixations.index[finite.to_numpy()]
    assigned.loc[idx] = line_idx.astype(float)
    if snap:
        # Snap to (float) line centers — cast first so an int64 `y` column
        # doesn't raise pandas' lossy-upcast error.
        corrected["y"] = corrected["y"].astype(float)
        corrected.loc[idx, "y"] = line_Y[line_idx]
    return corrected, assigned
