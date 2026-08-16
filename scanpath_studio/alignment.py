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
belongs to. The module ships the ten methods surveyed by Carr et al. (2021), a
native implementation of the later run-based ``slice`` method, and a consensus
vote:

    attach, chain, cluster, compare, merge, regress, segment, split, stretch,
    warp, slice, consensus

Pure functions, no Streamlit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.vq import kmeans2
from scipy.optimize import minimize
from scipy.stats import norm

from .measures import cluster_word_lines, word_box_bounds
from .model_scanpaths import _ordered_word_rows

NOTICE = (
    "Vertical drift-correction algorithms (alignment.py) adapted from "
    "Carr, Pescuma, Furlan, Ktori & Crepaldi (2021), 'Algorithms for the "
    "automated correction of vertical drift in eye-tracking data', Behavior "
    "Research Methods. Reference code: https://github.com/jwcarr/drift "
    "(CC BY 4.0). Adapted/modified."
)

METHOD_CITATIONS = {
    "attach": "Carr et al. (2021), nearest-line baseline",
    "chain": "Carr et al. (2021), chain",
    "cluster": "Carr et al. (2021), cluster",
    "compare": "Carr et al. (2021), compare",
    "merge": "Carr et al. (2021), merge",
    "regress": "Carr et al. (2021), regress",
    "segment": "Carr et al. (2021), segment",
    "split": "Carr et al. (2021), split",
    "stretch": "Carr et al. (2021), stretch",
    "warp": "Carr et al. (2021), warp",
    "slice": "Schroeder (2022), run-based Slice line assignment",
    "consensus": "Carr et al. (2021), wisdom-of-the-crowd vote",
}

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
    "slice",
    "consensus",
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
    line_change_indices = {int(i) for i in np.argsort(diff_X)[: m - 1]}
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


def _slice(
    fixation_XY: np.ndarray,
    line_Y: np.ndarray,
    word_XY,
    *,
    run_y_factor: float = 0.65,
    run_x_factor: float = 0.60,
    same_line_factor: float = 0.45,
    adjacent_factor: float = 1.50,
) -> np.ndarray:
    """Assign locally coherent reading runs to lines.

    This is an independent implementation of Slice's published algorithmic
    idea: split the scanpath at large horizontal/vertical jumps, seed the run
    with the broadest horizontal coverage, then grow line labels by comparing
    each run with already labelled fixations at nearby x positions.  The final
    relative labels are aligned to the absolute stimulus line centres.

    Keeping a run together is the important distinction from ``attach``: a
    locally drifted fixation does not jump to another line merely because it is
    a few pixels closer to that line's centre.
    """
    n = len(fixation_XY)
    if n == 0:
        return np.zeros(0, dtype=int)

    sorted_lines = np.sort(np.asarray(line_Y, dtype=float))
    line_gaps = np.diff(sorted_lines)
    line_gaps = line_gaps[np.isfinite(line_gaps) & (line_gaps > 0)]
    if not len(line_gaps):
        return np.zeros(n, dtype=int)
    line_height = float(np.median(line_gaps))

    if word_XY is not None and len(word_XY):
        text_x = np.asarray(word_XY, dtype=float)[:, 0]
    else:
        text_x = fixation_XY[:, 0]
    text_x = text_x[np.isfinite(text_x)]
    text_span = float(np.ptp(text_x)) if len(text_x) > 1 else 0.0
    # A line-height-derived floor keeps narrow stimuli from fragmenting at
    # ordinary within-line saccades.
    run_x = max(text_span * run_x_factor, line_height * 3.0)
    run_y = line_height * run_y_factor

    dx = np.abs(np.diff(fixation_XY[:, 0]))
    dy = np.abs(np.diff(fixation_XY[:, 1]))
    boundaries = np.flatnonzero((dx >= run_x) | (dy >= run_y)) + 1
    runs = [run for run in np.split(np.arange(n), boundaries) if len(run)]

    def horizontal_span(run: np.ndarray) -> float:
        return float(np.ptp(fixation_XY[run, 0])) if len(run) > 1 else 0.0

    seed = max(range(len(runs)), key=lambda i: (horizontal_span(runs[i]), len(runs[i])))
    relative: dict[int, int] = {seed: 0}

    def residual(run: np.ndarray, labelled_indices: np.ndarray) -> float:
        """Mean y offset from the closest-in-x labelled fixation."""
        labelled = fixation_XY[labelled_indices]
        offsets = []
        for point in fixation_XY[run]:
            nearest = int(np.argmin(np.abs(labelled[:, 0] - point[0])))
            offsets.append(point[1] - labelled[nearest, 1])
        return float(np.mean(offsets))

    while len(relative) < len(runs):
        candidates: list[tuple[float, int, int]] = []
        for run_i, run in enumerate(runs):
            if run_i in relative:
                continue
            for anchor_label in sorted(set(relative.values())):
                anchor_runs = [
                    runs[i] for i, label in relative.items() if label == anchor_label
                ]
                anchor_indices = np.concatenate(anchor_runs)
                offset = residual(run, anchor_indices)
                if abs(offset) < same_line_factor * line_height:
                    candidates.append((abs(offset), run_i, anchor_label))
                elif (
                    same_line_factor * line_height
                    <= offset
                    < adjacent_factor * line_height
                ):
                    candidates.append(
                        (abs(offset - line_height), run_i, anchor_label + 1)
                    )
                elif (
                    -adjacent_factor * line_height
                    < offset
                    <= -same_line_factor * line_height
                ):
                    candidates.append(
                        (abs(offset + line_height), run_i, anchor_label - 1)
                    )
        if candidates:
            _, run_i, label = min(candidates)
            relative[run_i] = label
            continue

        # A skipped line or unusually large drift can leave no adjacent
        # candidate. Extend from the closest labelled run by an integer number
        # of typical line heights, ensuring deterministic forward progress.
        best: tuple[float, int, int] | None = None
        for run_i, run in enumerate(runs):
            if run_i in relative:
                continue
            run_mean = float(np.mean(fixation_XY[run, 1]))
            for anchor_i, anchor_label in relative.items():
                anchor_mean = float(np.mean(fixation_XY[runs[anchor_i], 1]))
                delta = (run_mean - anchor_mean) / line_height
                step = int(np.rint(delta))
                step = step if step else (1 if delta > 0 else -1)
                score = abs(delta - step)
                candidate = (score, run_i, anchor_label + step)
                if best is None or candidate < best:
                    best = candidate
        assert best is not None
        _, run_i, label = best
        relative[run_i] = label

    # Slice labels are relative to the seed. Find the vertical shift that best
    # aligns those labels with the available absolute stimulus lines while
    # preserving their ordering and spacing.
    labels = np.array([relative[i] for i in range(len(runs))], dtype=int)
    unique_labels = np.unique(labels)
    lowest = int(unique_labels.min())
    label_range = int(unique_labels.max() - lowest)
    run_means = np.array([np.mean(fixation_XY[run, 1]) for run in runs])
    if label_range < len(sorted_lines):
        fits = []
        for shift in range(len(sorted_lines) - label_range):
            absolute = labels - lowest + shift
            error = float(np.sum((run_means - sorted_lines[absolute]) ** 2))
            fits.append((error, shift))
        shift = min(fits)[1]
        run_assignment = labels - lowest + shift
    else:
        # More inferred gaze lines than stimulus lines: merge excess relative
        # labels into the closest physical line instead of discarding runs.
        label_means = {
            label: float(np.mean(run_means[labels == label])) for label in unique_labels
        }
        mapping = {
            label: int(np.argmin(np.abs(sorted_lines - mean_y)))
            for label, mean_y in label_means.items()
        }
        run_assignment = np.array([mapping[label] for label in labels], dtype=int)

    assignment = np.zeros(n, dtype=int)
    for run, line_i in zip(runs, run_assignment):
        assignment[run] = int(line_i)
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
    "slice": _slice,
}


# ---------------------------------------------------------------------------
# Public core + DataFrame wrapper
# ---------------------------------------------------------------------------


def assign_lines(
    fixation_XY: np.ndarray,
    line_Y: np.ndarray,
    *,
    word_XY: np.ndarray | None = None,
    method: str = "attach",
) -> np.ndarray:
    """Assign each fixation a line index in ``[0, len(line_Y))``.

    ``fixation_XY`` is an ``(n, 2)`` float array, ``line_Y`` a sorted-ascending
    ``(m,)`` array of line centers, and ``word_XY`` an ``(k, 2)`` array of word
    centers in reading order (required by ``warp`` / ``compare``; ignored
    otherwise). Returns an int ``(n,)`` array of line indices.
    """
    if method not in _DISPATCH and method != "consensus":
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
    if method == "consensus":
        votes = np.vstack(
            [
                _DISPATCH[name](fixation_XY, line_Y, word_XY)
                for name in _DISPATCH
                if name not in {"slice"}
            ]
        )
        assignment = np.apply_along_axis(
            lambda column: np.bincount(
                column.astype(int), minlength=len(line_Y)
            ).argmax(),
            0,
            votes,
        )
    else:
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
    # BUG-11: the corrected box centre is the glyph centre — which is what warp /
    # compare are matching fixations against.
    x0, y0, x1, y1 = word_box_bounds(ordered, layout=words)
    finite = np.isfinite(x0) & np.isfinite(y0) & np.isfinite(x1) & np.isfinite(y1)
    cx = ((x0 + x1) / 2.0)[finite]
    cy = ((y0 + y1) / 2.0)[finite]
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
    if method in ("warp", "compare", "slice", "consensus"):
        word_XY = _word_centers_reading_order(words)

    line_idx = assign_lines(fixation_XY, line_Y, word_XY=word_XY, method=method)
    idx = fixations.index[finite.to_numpy()]
    assigned.loc[idx] = line_idx.astype(float)
    if snap:
        # Snap to (float) line centers — cast first so an int64 `y` column
        # doesn't raise pandas' lossy-upcast error.
        corrected["y"] = corrected["y"].astype(float)
        corrected.loc[idx, "y"] = line_Y[line_idx]
    corrected["y_original"] = pd.to_numeric(fixations["y"], errors="coerce")
    corrected["y_correction"] = (
        pd.to_numeric(corrected["y"], errors="coerce") - corrected["y_original"]
    )
    if method == "consensus":
        votes = np.vstack(
            [
                assign_lines(fixation_XY, line_Y, word_XY=word_XY, method=name)
                for name in _DISPATCH
                if name != "slice"
            ]
        )
        agreement = [
            int(np.sum(votes[:, pos] == line_idx[pos])) for pos in range(len(line_idx))
        ]
        corrected["alignment_agreement"] = np.nan
        corrected.loc[idx, "alignment_agreement"] = agreement
    return corrected, assigned


def correction_sensitivity(
    fixations: pd.DataFrame,
    words: pd.DataFrame,
    methods: tuple[str, ...] = ("attach", "slice", "consensus"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carry several assignments together and report mean correction (PRE-18)."""
    combined = fixations.copy()
    report = []
    for method in methods:
        corrected, assigned = correct(fixations, words, method)
        combined[f"y_{method}"] = corrected["y"]
        combined[f"y_{method}_correction"] = corrected["y_correction"]
        combined[f"line_{method}"] = assigned
        if "alignment_agreement" in corrected:
            combined[f"agreement_{method}"] = corrected["alignment_agreement"]
        report.append(
            {
                "algorithm": method,
                "average_y_correction": float(corrected["y_correction"].abs().mean()),
                "max_y_correction": float(corrected["y_correction"].abs().max()),
            }
        )
    line_cols = [f"line_{method}" for method in methods]
    combined["assignment_disagreement"] = combined[line_cols].nunique(axis=1) > 1
    return combined, pd.DataFrame(report)
