"""Compute reading measures from fixations and word bounding boxes.

Definitions follow standard reading-research conventions (Rayner 1998;
Inhoff & Radach 1998). All measures are per (participant, trial, word). When a
column already exists on the words dataframe (e.g. pre-aggregated EyeLink IA
metrics) it is preserved; we only compute values that are not present.

Canonical output columns added to words:
- first_fixation_ms       — FFD: duration of the first fixation on this word
- first_pass_gaze_ms      — FPRT / gaze duration
- regression_path_ms      — RPD / go-past time
- total_fixation_ms       — TFD / dwell
- n_fixations             — fixation count
- skip_flag               — True if no first-pass fixation
- regression_in_flag      — True if any later fixation returned here
- regression_out_flag     — True if a fixation here was followed by a regression
- first_fix_x, first_fix_y — landing position of the first-pass first fixation

The fixations dataframe is also enriched with:
- word_id            — assigned via bbox containment + nearest-word fallback
- saccade_amplitude  — pixel distance from the previous fixation in the trial.
                       Always pixels (BUG-25): EyeLink's degree-valued
                       NEXT_SAC_AMPLITUDE / PREVIOUS_SAC_AMPLITUDE keep their
                       own `*_deg` names rather than sharing this one.
- progression        — 1 if the next fixation moves to a later word, -1 if earlier, 0 otherwise
- is_regression      — True if this fixation lands on a word earlier than the
                       running maximum word reached in the trial
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .multipart import grouping_columns

# Default line-misregistration tolerance (px): a fixation that falls outside
# every word box snaps to the nearest word centre within this radius before it
# is left unassigned. Shared by the grouped assigner here and the single-frame
# helper used for model scanpaths in :mod:`scanpath_studio.similarity`.
LINE_MISREGISTRATION_PX = 50.0

# A recorded ``timestamp_ms`` series is trusted as real reading time only when
# its span covers at least this fraction of the summed fixation durations.
# Fixations don't overlap, so a genuine recording spans at least its total
# dwell; the 0,1,2,… row index ``data.normalize_fixations`` synthesises when the
# source has no timestamps collapses to a few ms and must NOT be read as
# milliseconds. Shared by the similarity time-curve and the animation clock.
REAL_TIMESTAMP_DWELL_FRAC = 0.5


def _assign_word_ids_single(
    fix_chunk: pd.DataFrame,
    word_chunk: pd.DataFrame,
    nearest_within_px: float = LINE_MISREGISTRATION_PX,
) -> np.ndarray:
    """Vectorized fixation→word_id assignment for a single trial's frames.

    Tests every fixation in ``fix_chunk`` against every word box in
    ``word_chunk`` (no participant/trial grouping — the caller is responsible
    for slicing to one trial, or for passing frames whose ids deliberately
    don't match, as the model scanpaths do). Fixations outside every box snap
    to the nearest word centre within ``nearest_within_px`` (line-
    misregistration tolerance), else NaN.

    Returns a float array aligned to ``fix_chunk`` rows (NaN = out of text).
    """
    wx0, wy0, wx1, wy1 = word_box_bounds(word_chunk)
    wids = word_chunk["word_id"].to_numpy()
    wcx = (wx0 + wx1) / 2.0
    wcy = (wy0 + wy1) / 2.0

    fx = pd.to_numeric(fix_chunk["x"], errors="coerce").to_numpy(dtype=float)
    fy = pd.to_numeric(fix_chunk["y"], errors="coerce").to_numpy(dtype=float)

    in_box = (
        (fx[:, None] >= wx0[None, :])
        & (fx[:, None] <= wx1[None, :])
        & (fy[:, None] >= wy0[None, :])
        & (fy[:, None] <= wy1[None, :])
    )
    word_idx = np.where(in_box.any(axis=1), in_box.argmax(axis=1), -1)

    # Fallback: nearest word center within nearest_within_px.
    unassigned = word_idx == -1
    if unassigned.any() and nearest_within_px > 0:
        dists = np.sqrt(
            (fx[unassigned, None] - wcx[None, :]) ** 2
            + (fy[unassigned, None] - wcy[None, :]) ** 2
        )
        nearest = dists.argmin(axis=1)
        within = dists[np.arange(len(nearest)), nearest] <= nearest_within_px
        word_idx[unassigned] = np.where(within, nearest, -1)

    return np.where(word_idx >= 0, wids[np.clip(word_idx, 0, None)], np.nan)


# --- BUG-11 · word-box boundaries that sit mid-space ------------------------
# An interest-area boundary should fall in the MIDDLE of the whitespace between
# two words. In some corpora it doesn't. Interest areas are defined by the
# *experiment*, not by the tracker — EyeLink Data Viewer just measures against
# whatever rectangles the IAS file gives it — and a stimulus generator that
# tiles a monospaced line hands every box the whole following inter-word space
# as trailing padding. The boxes then tile with no gaps, but every boundary sits
# a half-space too far right, and a fixation landing in the space *before* a
# word is credited to the previous word. On the bundled demo every box is
# exactly ``(n_chars + 1) × advance`` px wide and starts at the word's first
# glyph (checked against the corpus's own stimulus images: per line the ink
# starts within 3 px of the first box's left edge and stops ~1 advance short of
# the last box's right edge).
#
# The correction has to be conditional: glyph-tight AOIs (PoTeC, MultiplEYE)
# leave real gaps between boxes and are already centred by construction, so
# shifting them would introduce the very error this fixes. `word_box_space_px`
# therefore only reports a padding width when the layout actually looks like
# "tiling boxes with one trailing space", and returns 0.0 otherwise.
#
# Only the BOUNDARY moves. ``x`` keeps meaning "where the glyphs start", so the
# true-to-scale word labels and the stimulus-image alignment (BUG-3 / VIZ-4) are
# untouched — the labels are drawn from the original frame, the boundaries from
# the recentred one.
_TILING_GAP_TOL_PX = 1.0
# Box widths are integers in the exports, so `(n_chars + 1) × advance` is only
# met to within a pixel of rounding; and a stray token (a stripped-out glyph, a
# joined punctuation mark) shouldn't disqualify an otherwise regular layout.
_ADVANCE_RESIDUAL_TOL_PX = 1.5
_ADVANCE_MIN_AGREEMENT = 0.95


def _sample_trial_words(words: pd.DataFrame) -> pd.DataFrame:
    """One trial's words — the layout is a property of the corpus, not a trial.

    Necessary as well as cheap: every trial is drawn at the same screen
    positions, so clustering lines across a whole corpus would merge different
    trials' words into one "line" and read their interleaved x as gaps.
    """
    keys = grouping_columns(words)
    if not keys:
        return words
    first = words[keys].iloc[0]
    mask = pd.Series(True, index=words.index)
    for key in keys:
        mask &= words[key] == first[key]
    return words[mask]


def word_box_space_px(words: pd.DataFrame) -> float:
    """Width of the trailing inter-word padding baked into each box, or ``0.0``.

    Non-zero only for a monospaced, *tiling* layout whose boxes are consistently
    ``(n_chars + 1)`` advances wide — the shape that carries the whole space as
    trailing padding. Anything else (glyph-tight AOIs, proportional fonts,
    missing text) reports 0.0, i.e. "don't touch this layout".
    """
    needed = {"x", "width", "text"}
    if words is None or words.empty or not needed <= set(words.columns):
        return 0.0
    sample = _sample_trial_words(words)
    x = pd.to_numeric(sample["x"], errors="coerce")
    width = pd.to_numeric(sample["width"], errors="coerce")
    chars = sample["text"].astype(str).str.len()
    ok = x.notna() & width.notna() & (chars > 0) & (width > 0)
    if ok.sum() < 3:
        return 0.0
    # One advance per character plus exactly one for the trailing space.
    advance = float((width[ok] / (chars[ok] + 1)).median())
    if advance <= 0:
        return 0.0
    residual = (width[ok] - (chars[ok] + 1) * advance).abs()
    if (residual <= _ADVANCE_RESIDUAL_TOL_PX).mean() < _ADVANCE_MIN_AGREEMENT:
        return 0.0  # not monospaced-with-one-trailing-space
    # And the boxes must actually tile: a layout with real gaps is glyph-tight,
    # so its boundaries already sit in the whitespace.
    lines = cluster_word_lines(sample)
    for _, line_words in sample[ok].groupby(lines[ok], sort=False):
        ordered = line_words.sort_values("x")
        if len(ordered) < 2:
            continue
        left = pd.to_numeric(ordered["x"], errors="coerce").to_numpy()
        right = left + pd.to_numeric(ordered["width"], errors="coerce").to_numpy()
        gaps = left[1:] - right[:-1]
        if len(gaps) and np.nanmax(np.abs(gaps)) > _TILING_GAP_TOL_PX:
            return 0.0
    return advance


def word_box_bounds(
    words: pd.DataFrame,
    *,
    layout: pd.DataFrame | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(x0, y0, x1, y1)`` AOI edges with the mid-space correction applied.

    **The** accessor for word-box geometry: anything that tests a point against a
    box, draws one, or measures a position within one goes through here, so the
    boundary is in one place instead of re-derived per call site. Pure — it reads
    ``x``/``y``/``width``/``height`` and returns arrays, never a shifted frame, so
    it cannot be applied twice by accident (the failure mode that made the first
    pass at BUG-11 fragile). For a glyph-tight corpus the correction is zero and
    these are the raw edges.

    Pass ``layout`` when ``words`` is a *subset* of a trial (a highlighted span,
    the words that got any dwell): tiling is a property of the whole line, and a
    subset has holes in it, so detection has to run on the full frame or it reads
    the holes as glyph-tight gaps and silently declines to correct.
    """
    if words is None or words.empty:
        # A column-less empty frame is a legitimate "no words" input.
        empty = np.empty(0, dtype=float)
        return empty, empty.copy(), empty.copy(), empty.copy()
    x = pd.to_numeric(words["x"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(words["y"], errors="coerce").to_numpy(dtype=float)
    w = pd.to_numeric(words["width"], errors="coerce").to_numpy(dtype=float)
    h = pd.to_numeric(words["height"], errors="coerce").to_numpy(dtype=float)
    x0 = x - word_box_space_px(words if layout is None else layout) / 2.0
    return x0, y, x0 + w, y + h


def word_char_advance(
    words: pd.DataFrame,
    *,
    layout: pd.DataFrame | None = None,
    chars: np.ndarray | None = None,
) -> np.ndarray:
    """Width of one character in each word, in px — the *within-word* scale.

    **The** accessor for anything that measures a position *inside* a word in
    letters (initial landing position, a saccade's launch/landing letter), the
    way :func:`word_box_bounds` is the accessor for the boundary between words.

    VAL-5 found the two disagreeing. The boundary had been corrected for BUG-11's
    trailing inter-word padding while the letter scale had not: ``width /
    len(text)`` divides a box that is ``len(text) + 1`` advances wide by
    ``len(text)``, so on a tiling corpus every letter was reported ~``(n+1)/n``
    too wide and every landing position that far into the word. The fix is the
    same detection, applied to the denominator — ``width / (len(text) + 1)`` for
    a tiling layout, ``width / len(text)`` for a glyph-tight one.

    The *origin* of a within-word position stays the word's ``x`` (where the
    glyphs start), not the corrected boundary: half an inter-word space to the
    left of the first glyph is where the AOI begins, not where the word does.
    With the advance fixed, ``x`` and the corrected boundary are one advance/2
    apart by construction, so the two accessors describe one consistent geometry.

    ``layout`` has the same meaning as in :func:`word_box_bounds`: pass the full
    trial when ``words`` is a subset, since tiling is a property of the line.

    ``chars`` lets a caller that already counted the characters hand them in —
    ``.astype(str).str.len()`` is a Python-level pass over the frame, and
    ``aggregation._glyph_span`` needs the same counts for the glyph run.
    """
    if words is None or words.empty or not {"width", "text"} <= set(words.columns):
        # NaN, never `np.empty` — that returns *uninitialized* floats, and a
        # garbage positive one passes the `isfinite and > 0` guard at the call
        # site and lands a silently wrong landing position in a cached frame.
        return np.full(0 if words is None else len(words), np.nan, dtype=float)
    width = pd.to_numeric(words["width"], errors="coerce").to_numpy(dtype=float)
    counts = word_char_counts(words) if chars is None else chars
    padded = word_box_space_px(words if layout is None else layout) > 0
    return width / (counts + (1.0 if padded else 0.0))


def word_char_counts(words: pd.DataFrame) -> np.ndarray:
    """Characters per word, floor 1 — the companion of :func:`word_char_advance`."""
    return words["text"].astype(str).str.len().clip(lower=1).to_numpy(dtype=float)


def recentre_word_boxes(words: pd.DataFrame) -> pd.DataFrame:
    """The :func:`word_box_bounds` correction as a frame, for row-wise consumers.

    Returns ``words`` unchanged (the same object) for layouts
    :func:`word_box_space_px` doesn't recognise, so the common case costs one
    check and no copy. Prefer :func:`word_box_bounds` — this shifts ``x``, so a
    frame that has been through it must not go through it again.
    """
    space = word_box_space_px(words)
    if space <= 0:
        return words
    out = words.copy()
    out["x"] = pd.to_numeric(out["x"], errors="coerce") - space / 2.0
    return out


def assign_fixations_to_words(
    fixations: pd.DataFrame,
    words: pd.DataFrame,
    *,
    overwrite: bool = False,
    nearest_within_px: float = LINE_MISREGISTRATION_PX,
) -> pd.DataFrame:
    """Assign each fixation to a word via bounding-box containment.

    If a fixation does not fall inside any word box, assign it to the nearest
    word center within `nearest_within_px` pixels (a common practice for line
    misregistration). Beyond that radius, the fixation gets word_id=NaN.

    If `overwrite=False` and the fixations already carry word_id values, those
    are kept; only NaN rows get re-assigned.

    Box edges come from :func:`word_box_bounds` (BUG-11), so a fixation in the
    whitespace *before* a word is credited to that word rather than the previous
    one.
    """
    if fixations.empty or words.empty:
        return fixations

    out = fixations.copy()
    if "word_id" not in out.columns or overwrite:
        out["word_id"] = np.nan

    need_idx = out["word_id"].isna()
    if not need_idx.any():
        return out

    # Per (participant, trial), do a fast vectorized box-test against that
    # trial's words.
    keys = grouping_columns(out)
    if keys != grouping_columns(words):
        raise ValueError("Words and fixations use different multipart identities.")
    groups = out[need_idx].groupby(keys, sort=False)
    word_groups = words.groupby(keys, sort=False)

    assignments = pd.Series(np.nan, index=out.index[need_idx], dtype=float)
    for group_key, fix_chunk in groups:
        lookup_key = group_key if len(keys) > 1 else group_key[0]
        try:
            wchunk = word_groups.get_group(lookup_key)
        except KeyError:
            continue
        if wchunk.empty:
            continue
        assignments.loc[fix_chunk.index] = _assign_word_ids_single(
            fix_chunk, wchunk, nearest_within_px
        )

    out.loc[need_idx, "word_id"] = assignments
    return out


def materialize_runs(fixations: pd.DataFrame) -> pd.DataFrame:
    """Add trial run, line run, and per-word visit/pass columns (PRE-16)."""
    if fixations.empty:
        return fixations.copy()
    derived = (
        "run",
        "linerun",
        "word_runid",
        "word_run",
        "word_run_fix",
        "nrun",
        "reread",
    )
    out = fixations.drop(columns=[c for c in derived if c in fixations]).copy()
    if "word_id" not in out:
        out["word_id"] = pd.Series(pd.NA, index=out.index, dtype="Float64")
    excluded = out.get("excluded", pd.Series(False, index=out.index)).fillna(False)
    active = out.loc[~excluded.astype(bool)].copy()
    for column in derived:
        out[column] = pd.NA
    if active.empty:
        return out.sort_index()
    keys = grouping_columns(active)
    order_cols = keys + (["timestamp_ms"] if "timestamp_ms" in out else [])
    active = active.sort_values(order_cols, kind="stable")
    group = active.groupby(keys, sort=False, dropna=False) if keys else [((), active)]
    pieces = []
    for _, chunk in group:
        chunk = chunk.copy()
        word = pd.to_numeric(
            chunk.get("word_id", pd.Series(pd.NA, index=chunk.index)),
            errors="coerce",
        )
        line_source = (
            chunk["line_id"]
            if "line_id" in chunk
            else chunk.get("line_idx", pd.Series(pd.NA, index=chunk.index))
        )
        line = pd.to_numeric(line_source, errors="coerce")
        chunk["run"] = (word.diff().fillna(0) < 0).cumsum().astype("Int64") + 1
        chunk["linerun"] = (
            (line.ne(line.shift()) & line.notna()).cumsum().astype("Int64")
        )
        visit_start = word.ne(word.shift()) | word.isna()
        chunk["word_runid"] = visit_start.cumsum().astype("Int64")
        valid = chunk[word.notna()].copy()
        if not valid.empty:
            visits = valid[["word_id", "word_runid"]].drop_duplicates()
            visits["word_run"] = visits.groupby("word_id", sort=False).cumcount() + 1
            lookup = visits.set_index(["word_id", "word_runid"])["word_run"]
            visit_keys = pd.MultiIndex.from_frame(chunk[["word_id", "word_runid"]])
            chunk["word_run"] = lookup.reindex(visit_keys).to_numpy()
            chunk["word_run_fix"] = (
                chunk.groupby(["word_id", "word_runid"], dropna=False).cumcount() + 1
            )
        else:
            chunk["word_run"] = pd.NA
            chunk["word_run_fix"] = pd.NA
        chunk["nrun"] = chunk.groupby("word_id", dropna=False)["word_runid"].transform(
            "nunique"
        )
        chunk["reread"] = pd.to_numeric(chunk["word_run"], errors="coerce").gt(1)
        pieces.append(chunk)
    computed = pd.concat(pieces).sort_index() if pieces else active
    for column in derived:
        out.loc[computed.index, column] = computed[column]
    return out.sort_index()


def enrich_fixations(fixations: pd.DataFrame, words: pd.DataFrame) -> pd.DataFrame:
    """Add saccade_amplitude, progression, and is_regression to fixations."""
    if fixations.empty:
        return fixations
    out = fixations.copy()
    keys = grouping_columns(out)
    out = out.sort_values(keys + ["timestamp_ms"])

    g = out.groupby(keys, sort=False)
    dx = g["x"].diff()
    dy = g["y"].diff()
    if "saccade_amplitude" not in out.columns:
        out["saccade_amplitude"] = np.sqrt(dx * dx + dy * dy)
    else:
        out["saccade_amplitude"] = out["saccade_amplitude"].where(
            out["saccade_amplitude"].notna(), np.sqrt(dx * dx + dy * dy)
        )
    incoming = np.degrees(np.arctan2(-dy, dx))
    out["angle_incoming"] = incoming
    g = out.groupby(keys, sort=False)
    out["angle_outgoing"] = g["angle_incoming"].shift(-1)

    next_word = g["word_id"].shift(-1)
    out["progression"] = np.sign(next_word - out["word_id"]).fillna(0).astype(int)

    running_max = g["word_id"].cummax()
    out["is_regression"] = (out["word_id"] < running_max).fillna(False).astype(bool)
    return materialize_runs(out)


def classify_saccades(fixations: pd.DataFrame, words: pd.DataFrame) -> pd.Series:
    """Classify each *outgoing* saccade by its reading type (VIZ-8).

    A saccade is the segment from one fixation to the next in reading order; its
    class is stored on the *departing* fixation, so the last fixation of every
    trial (which has no outgoing saccade) is ``None``. Classes follow the classic
    reading schematic:

    - ``refixation`` — lands back on the same word (``word_id`` unchanged),
    - ``regression`` — moves to an earlier line, or backward within a line,
    - ``return_sweep`` — sweeps down to a later line (forward reading),
    - ``forward`` — advances to the next word on the same line,
    - ``skip`` — advances past one or more words on the same line,
    - ``other`` — a real saccade whose endpoints can't be classified (an
      out-of-text fixation with no assigned word).

    Line membership comes from :func:`assign_fixation_lines` (word-box geometry),
    word order from the fixation ``word_id`` assignment. Returns an object Series
    aligned to ``fixations.index`` (pure — no plotting), so both the render path
    (``plots._add_saccade_layer``) and any future analysis can reuse it. Works on
    a single already-sliced trial or a multi-trial frame (grouped by
    participant/trial).
    """
    if fixations.empty:
        return pd.Series([], dtype=object, index=fixations.index)

    keys = grouping_columns(fixations)
    sort_cols = keys + (["timestamp_ms"] if "timestamp_ms" in fixations.columns else [])
    order = fixations.sort_values(sort_cols).index if sort_cols else fixations.index

    if "word_id" in fixations.columns:
        word = pd.to_numeric(fixations["word_id"], errors="coerce").reindex(order)
    else:
        word = pd.Series(np.nan, index=order, dtype=float)
    if words is not None and not words.empty:
        line = assign_fixation_lines(fixations, words).reindex(order)
    else:
        line = pd.Series(np.nan, index=order, dtype=float)

    if keys:
        grp = [fixations[k].reindex(order) for k in keys]
        next_word = word.groupby(grp).shift(-1)
        next_line = line.groupby(grp).shift(-1)
        next_pos = pd.Series(np.arange(len(order)), index=order).groupby(grp).shift(-1)
    else:
        next_word = word.shift(-1)
        next_line = line.shift(-1)
        next_pos = pd.Series(np.arange(len(order)), index=order).shift(-1)

    word_arr = word.to_numpy(dtype=float)
    next_word_arr = next_word.to_numpy(dtype=float)
    dw = next_word_arr - word_arr
    dl = (next_line - line).to_numpy(dtype=float)
    has_next = next_pos.notna().to_numpy()
    # A saccade is classifiable only when BOTH endpoints have an assigned word;
    # otherwise the word/line deltas are meaningless (an off-text fixation still
    # gets a *nearest* line, which would spuriously read as a line change).
    both_words = ~np.isnan(word_arr) & ~np.isnan(next_word_arr)
    same_line = np.isnan(dl) | (dl == 0)

    # Priority order: same word first, then line moves, then within-line word moves.
    conds = [
        dw == 0,  # refixation
        dl < 0,  # regression — up to an earlier line
        dl > 0,  # return sweep — down to a later line
        same_line & (dw < 0),  # regression — backward within the line
        same_line & (dw == 1),  # forward
        same_line & (dw >= 2),  # skip
    ]
    choices = [
        "refixation",
        "regression",
        "return_sweep",
        "regression",
        "forward",
        "skip",
    ]
    classed = np.select(conds, choices, default="other").astype(object)
    classed[~both_words] = "other"  # a real saccade, but an endpoint is off-text
    classed[~has_next] = None  # last fixation of a trial: no outgoing saccade
    # dtype=object is load-bearing: pandas 3.0 infers a dedicated `str` dtype for
    # an all-string+None array and coerces the None sentinel to NaN, breaking the
    # "None for the last fixation" contract. Pin object so None survives.
    return pd.Series(classed, index=order, dtype=object).reindex(fixations.index)


def rebased_fixation_onsets(ordered_fixations: pd.DataFrame) -> np.ndarray:
    """Fixation onset times (ms), rebased so the first fixation is t=0.

    ``ordered_fixations`` must already be in reading order (sorted by
    ``timestamp_ms``); the returned array is aligned to its rows. Uses the
    recorded ``timestamp_ms`` when they look like real times — their span is at
    least ``REAL_TIMESTAMP_DWELL_FRAC`` of the summed durations — otherwise lays
    fixations back-to-back by their durations, so a synthesised 0,1,2,… index
    doesn't crush the time axis. Shared by the similarity time-curve
    (:func:`scanpath_studio.similarity._rebased_onsets`) and the animation clock
    (:func:`scanpath_studio.plots._scanpath_anim_specs`).
    """
    if ordered_fixations.empty:
        return np.array([], dtype=float)
    if "duration_ms" in ordered_fixations.columns:
        dur = (
            pd.to_numeric(ordered_fixations["duration_ms"], errors="coerce")
            .fillna(0)
            .to_numpy(dtype=float)
        )
    else:
        dur = np.zeros(len(ordered_fixations))
    contiguous = np.concatenate(([0.0], np.cumsum(dur)[:-1])) if len(dur) else dur
    if "timestamp_ms" in ordered_fixations.columns:
        ts = pd.to_numeric(ordered_fixations["timestamp_ms"], errors="coerce").to_numpy(
            dtype=float
        )
        total_dwell = float(dur.sum()) if len(dur) else 0.0
        if (
            len(ts)
            and not np.isnan(ts).any()
            and (ts[-1] - ts[0]) >= REAL_TIMESTAMP_DWELL_FRAC * total_dwell
        ):
            return ts - ts[0]
    return contiguous


# ---------------------------------------------------------------------------
# Geometry helpers: line clustering, in-text test, fixation -> line.
#
# These power the "highlight out-of-text fixations" and "color fixations by
# line" plot options. They are deliberately pure (no Streamlit, no plotting)
# so they can be unit-tested against a known synthetic layout.
# ---------------------------------------------------------------------------


def _in_any_box(fix_chunk: pd.DataFrame, word_chunk: pd.DataFrame) -> np.ndarray:
    """Boolean array (aligned to fix_chunk order): is each fixation inside any box?"""
    x0, y0, x1, y1 = word_box_bounds(word_chunk)
    fx = pd.to_numeric(fix_chunk["x"], errors="coerce").to_numpy(dtype=float)
    fy = pd.to_numeric(fix_chunk["y"], errors="coerce").to_numpy(dtype=float)
    inside = (
        (fx[:, None] >= x0[None, :])
        & (fx[:, None] <= x1[None, :])
        & (fy[:, None] >= y0[None, :])
        & (fy[:, None] <= y1[None, :])
    )
    return inside.any(axis=1)


def cluster_word_lines(words: pd.DataFrame, tol_frac: float = 0.5) -> pd.Series:
    """Assign each word a 0-based line id by clustering on vertical position.

    OneStop IA exports rarely carry a real per-word line number (the
    normalized ``line_idx`` is often a constant), so we infer visual lines from
    word-box geometry: words are sorted by vertical center and a new line
    starts whenever the center jumps by more than ``tol_frac`` of the median
    word height. Lines are numbered top-to-bottom starting at 0.

    Returns an int Series aligned to ``words.index`` (empty when ``words`` is
    empty). Mirrors the line clustering used by ``plots.build_critical_span_overlay``.
    """
    if words.empty:
        return pd.Series([], dtype="int64", index=words.index)
    heights = pd.to_numeric(words["height"], errors="coerce")
    typical_h = float(heights.median()) if heights.notna().any() else 1.0
    typical_h = typical_h if typical_h > 0 else 1.0
    y_center = pd.to_numeric(words["y"], errors="coerce") + heights.fillna(0) / 2.0
    order = y_center.sort_values(kind="stable")
    line_of_sorted = (
        (order.diff().fillna(0) > typical_h * tol_frac).cumsum().astype(int)
    )
    return line_of_sorted.reindex(words.index)


def _groupwise(fixations: pd.DataFrame, words: pd.DataFrame, fn) -> pd.Series:
    """Apply ``fn(fix_chunk, word_chunk)`` per (participant, trial), aligning
    the per-chunk result back onto a Series indexed like ``fixations``.

    Falls back to a single group when the id columns are absent (e.g. the
    figure builders pass already-sliced single-trial frames)."""
    keys = grouping_columns(fixations)
    # object dtype so a chunk fn may return bools (in-text) or floats (line ids)
    # without triggering a dtype-incompatibility cast; callers coerce the result.
    out = pd.Series(np.nan, index=fixations.index, dtype=object)
    has_groups = bool(keys) and keys == grouping_columns(words)
    if not has_groups:
        out.loc[:] = fn(fixations, words)
        return out
    word_groups = words.groupby(keys, sort=False)
    for key, fix_chunk in fixations.groupby(keys, sort=False):
        try:
            word_chunk = word_groups.get_group(key)
        except KeyError:
            continue
        if word_chunk.empty:
            continue
        out.loc[fix_chunk.index] = fn(fix_chunk, word_chunk)
    return out


def fixation_in_text_mask(fixations: pd.DataFrame, words: pd.DataFrame) -> pd.Series:
    """Boolean Series: True where a fixation falls inside any word box.

    "Out-of-text" fixations are simply ``~fixation_in_text_mask(...)``. Works
    on multi-trial frames (grouped by participant/trial) or on a single
    already-sliced trial. Fixations with non-finite coordinates count as
    out-of-text (mask = False)."""
    if fixations.empty:
        return pd.Series([], dtype=bool, index=fixations.index)
    if words.empty:
        return pd.Series(False, index=fixations.index)
    res = _groupwise(fixations, words, _in_any_box)
    return res.where(res.notna(), other=False).astype(bool)


def assign_fixation_lines(fixations: pd.DataFrame, words: pd.DataFrame) -> pd.Series:
    """Assign each fixation the 0-based line id of the nearest text line.

    Lines are derived from word geometry via :func:`cluster_word_lines`; each
    fixation is mapped to the line whose mean vertical center is closest to the
    fixation's y. Returns a float Series (NaN where unmappable) aligned to
    ``fixations.index`` so it can be used as a categorical color field."""
    if fixations.empty:
        return pd.Series([], dtype="float64", index=fixations.index)
    if words.empty:
        return pd.Series(np.nan, index=fixations.index, dtype="float64")

    def _nearest_line(fix_chunk: pd.DataFrame, word_chunk: pd.DataFrame) -> np.ndarray:
        lines = cluster_word_lines(word_chunk)
        y_center = (
            pd.to_numeric(word_chunk["y"], errors="coerce")
            + pd.to_numeric(word_chunk["height"], errors="coerce").fillna(0) / 2.0
        )
        centers = y_center.groupby(lines).mean()
        line_ids = centers.index.to_numpy(dtype=float)
        line_cy = centers.to_numpy(dtype=float)
        fy = pd.to_numeric(fix_chunk["y"], errors="coerce").to_numpy(dtype=float)
        dist = np.abs(fy[:, None] - line_cy[None, :])
        nearest = np.where(np.isnan(fy), -1, dist.argmin(axis=1))
        result = np.where(nearest >= 0, line_ids[np.clip(nearest, 0, None)], np.nan)
        return result

    return pd.to_numeric(_groupwise(fixations, words, _nearest_line), errors="coerce")


def compute_per_word_measures(
    fixations: pd.DataFrame, words: pd.DataFrame
) -> pd.DataFrame:
    """Compute canonical reading measures per word.

    Returns a copy of `words` with computed columns added. Existing values on
    `words` (e.g. EyeLink IA metrics) take precedence over computed ones.
    """
    if words.empty:
        return words.copy()

    enriched = (
        enrich_fixations(assign_fixations_to_words(fixations, words), words)
        if not fixations.empty
        else fixations
    )

    out = words.copy()
    key_cols = grouping_columns(words, include_word=True)
    # VAL-5: the letter scale for the landing measures, resolved once on the
    # whole frame (tiling is a property of the layout, so it must not be
    # re-detected per trial word, which is a subset with holes in it).
    char_advance = pd.Series(word_char_advance(words), index=words.index)

    # Initialize defaults
    computed = (
        words[key_cols]
        .drop_duplicates()
        .assign(
            _first_fixation_ms=np.nan,
            _first_pass_gaze_ms=np.nan,
            _regression_path_ms=np.nan,
            _total_fixation_ms=0.0,
            _n_fixations=0,
            _skip_flag=True,
            _regression_in_flag=False,
            _regression_out_flag=False,
            _first_fix_x=np.nan,
            _first_fix_y=np.nan,
            _initial_landing_position=np.nan,
            _initial_landing_distance=np.nan,
            _number_of_regressions_in=0,
            _second_pass_duration=0.0,
            _single_fixation_duration=np.nan,
        )
    )

    analysis_fixations = enriched
    if "excluded" in enriched.columns:
        analysis_fixations = enriched[~enriched["excluded"].fillna(False).astype(bool)]
    if not analysis_fixations.empty and "word_id" in analysis_fixations.columns:
        per_word_rows = []
        # Group fixations by trial to walk them in temporal order.
        trial_keys = grouping_columns(analysis_fixations)
        for group_key, fix_chunk in analysis_fixations.dropna(
            subset=["word_id"]
        ).groupby(trial_keys, sort=False):
            values = group_key if isinstance(group_key, tuple) else (group_key,)
            identity = dict(zip(trial_keys, values))
            fix_chunk = fix_chunk.sort_values("timestamp_ms")
            # Total / n / first-fixation are per-word aggregations
            grp = fix_chunk.groupby("word_id")
            tot = grp["duration_ms"].sum()
            n = grp.size()
            ffd = grp["duration_ms"].first()
            ffx = grp["x"].first()
            ffy = grp["y"].first()
            second_pass = (
                fix_chunk[
                    pd.to_numeric(fix_chunk.get("word_run"), errors="coerce").eq(2)
                ]
                .groupby("word_id")["duration_ms"]
                .sum()
            )
            first_pass_counts = (
                fix_chunk[
                    pd.to_numeric(fix_chunk.get("word_run"), errors="coerce").eq(1)
                ]
                .groupby("word_id")
                .size()
            )

            # First-pass gaze: walk the trial in order, accumulate runs.
            first_pass_gaze: dict[float, float] = {}
            regression_path: dict[float, float] = {}
            regression_in: set = set()
            regression_out: set = set()
            regression_in_count: dict[float, int] = {}

            running_max = -np.inf
            current_run_word: float | None = None
            current_run_duration: float = 0.0
            # For regression-path: from first entry into a word until first
            # fixation past it, sum all durations.
            first_entry_seen: set = set()
            rp_open_for: dict[float, float] = {}

            prev_word: float | None = None
            for row in fix_chunk.itertuples():
                w = float(row.word_id)
                dur = float(row.duration_ms)

                # First-pass gaze duration: continuous run on this word
                # starting from first entry, ending the first time we leave.
                if w not in first_pass_gaze:
                    if current_run_word == w:
                        current_run_duration += dur
                    else:
                        if current_run_word is not None:
                            first_pass_gaze.setdefault(
                                current_run_word, current_run_duration
                            )
                        current_run_word = w
                        current_run_duration = dur
                else:
                    # Already past first pass; reset run tracker.
                    if (
                        current_run_word is not None
                        and current_run_word not in first_pass_gaze
                    ):
                        first_pass_gaze.setdefault(
                            current_run_word, current_run_duration
                        )
                    current_run_word = None
                    current_run_duration = 0.0

                # Regression-path: from the first entry into a word, sum
                # durations until the next fixation lands on a strictly later
                # word.
                if w not in first_entry_seen:
                    first_entry_seen.add(w)
                    rp_open_for[w] = dur
                else:
                    for k in list(rp_open_for.keys()):
                        if w <= k:
                            # Still within or back-tracking; keep accumulating.
                            rp_open_for[k] += dur
                # Close any open RP windows for words we've now moved past.
                for k in list(rp_open_for.keys()):
                    if w > k and k != w:
                        regression_path.setdefault(k, rp_open_for.pop(k))

                # Regression-in: stepping back to an earlier word counts the
                # destination as receiving an in-regression.
                if prev_word is not None and w < prev_word:
                    regression_in.add(w)
                    regression_out.add(prev_word)
                    regression_in_count[w] = regression_in_count.get(w, 0) + 1

                running_max = max(running_max, w)
                prev_word = w

            # Flush remaining first-pass run
            if current_run_word is not None and current_run_word not in first_pass_gaze:
                first_pass_gaze[current_run_word] = current_run_duration
            # Flush remaining regression-path windows (reader never moved past)
            for k, v in rp_open_for.items():
                regression_path.setdefault(k, v)

            for w in tot.index:
                word_mask = pd.to_numeric(words["word_id"], errors="coerce") == w
                for column, value in identity.items():
                    word_mask &= words[column] == value
                trial_word = words[word_mask]
                landing_position = landing_distance = np.nan
                if not trial_word.empty:
                    target = trial_word.iloc[0]
                    text_len = max(len(str(target.get("text", ""))), 1)
                    width = float(pd.to_numeric(target.get("width"), errors="coerce"))
                    char_width = float(char_advance.loc[trial_word.index[0]])
                    if np.isfinite(char_width) and char_width > 0 and width > 0:
                        rtl = bool(target.get("right_to_left", False))
                        # BUG-27: RTL counts from where the glyphs *end*
                        # (`x + n × advance`), not from the padded box edge
                        # `x + width` — on a tiling layout those are one whole
                        # advance apart, so an RTL landing read a letter late
                        # and disagreed with `aggregation.landing_positions`,
                        # which measures across the glyph run on both sides.
                        offset = (
                            float(target.get("x"))
                            + text_len * char_width
                            - float(ffx.loc[w])
                            if rtl
                            else float(ffx.loc[w]) - float(target.get("x"))
                        )
                        landing_position = offset / char_width + 1.0
                        landing_distance = landing_position - (text_len + 1) / 2.0
                per_word_rows.append(
                    dict(
                        **identity,
                        word_id=w,
                        _first_fixation_ms=float(ffd.loc[w]),
                        _first_pass_gaze_ms=float(first_pass_gaze.get(w, np.nan)),
                        _regression_path_ms=float(
                            regression_path.get(w, np.nan)
                            if w in first_entry_seen
                            else np.nan
                        ),
                        _total_fixation_ms=float(tot.loc[w]),
                        _n_fixations=int(n.loc[w]),
                        _skip_flag=bool(np.isnan(first_pass_gaze.get(w, np.nan))),
                        _regression_in_flag=w in regression_in,
                        _regression_out_flag=w in regression_out,
                        _first_fix_x=float(ffx.loc[w]),
                        _first_fix_y=float(ffy.loc[w]),
                        _initial_landing_position=landing_position,
                        _initial_landing_distance=landing_distance,
                        _number_of_regressions_in=int(regression_in_count.get(w, 0)),
                        _second_pass_duration=float(second_pass.get(w, 0.0)),
                        _single_fixation_duration=(
                            float(ffd.loc[w])
                            if int(first_pass_counts.get(w, 0)) == 1
                            else np.nan
                        ),
                    )
                )

        if per_word_rows:
            new_df = pd.DataFrame(per_word_rows)
            updated = computed.merge(
                new_df, on=key_cols, how="left", suffixes=("_default", "")
            )
            for col in new_df.columns:
                if col in key_cols:
                    continue
                default_col = f"{col}_default"
                if default_col in updated.columns:
                    updated[col] = updated[col].where(
                        updated[col].notna(), updated[default_col]
                    )
                    updated = updated.drop(columns=default_col)
            computed = updated

    out = out.merge(computed, on=key_cols, how="left")

    # Map computed -> canonical name, keeping any existing value.
    rename_map = {
        "_first_fixation_ms": "first_fixation_ms",
        "_first_pass_gaze_ms": "first_pass_gaze_duration_ms",
        "_regression_path_ms": "regression_path_duration_ms",
        "_total_fixation_ms": "total_fixation_duration_ms",
        "_n_fixations": "n_fixations",
        "_skip_flag": "skip_flag",
        "_regression_in_flag": "regression_in_flag",
        "_regression_out_flag": "regression_out_flag",
        "_first_fix_x": "first_fix_x",
        "_first_fix_y": "first_fix_y",
        "_initial_landing_position": "initial_landing_position",
        "_initial_landing_distance": "initial_landing_distance",
        "_number_of_regressions_in": "number_of_regressions_in",
        "_second_pass_duration": "second_pass_duration_ms",
        "_single_fixation_duration": "single_fixation_duration_ms",
    }
    for src, dst in rename_map.items():
        if src not in out.columns:
            continue
        if dst in out.columns:
            out[dst] = out[dst].where(out[dst].notna(), out[src])
        else:
            out[dst] = out[src]
        out = out.drop(columns=src)

    # Canonical aliases used elsewhere in the app
    if (
        "first_pass_gaze_duration_ms" in out.columns
        and "gaze_duration_ms" not in out.columns
    ):
        out["gaze_duration_ms"] = out["first_pass_gaze_duration_ms"]

    # Ensure dtypes
    for col in ["n_fixations"]:
        if col in out.columns:
            out[col] = (
                pd.to_numeric(out[col], errors="coerce").fillna(0).astype("Int64")
            )
    for col in ["skip_flag", "regression_in_flag", "regression_out_flag"]:
        if col in out.columns:
            out[col] = (
                out[col].astype(object).where(out[col].notna(), False).astype(bool)
            )

    return out
