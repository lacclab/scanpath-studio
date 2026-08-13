"""Pure aggregation helpers for the Corpus Analysis subtabs.

Headless (no Streamlit), so they're unit-testable. They turn the filtered
words / fixations frames into the small summary tables the plot builders draw:
per-trial-index trends, per-fixation-index trends, grouped metric distributions,
and per-text word-level aggregates for heatmaps. The heavy work is plain pandas
groupby; the tabs cache the results with ``@st.cache_data``.

The lower block (from :data:`MEASURES` onward) backs the question-oriented
analysis sections — *per text* (one text, many readers), *per reader* (one
reader, many trials), *per group* (a cohort), and *group comparison* (two
cohorts). Every section reads a single :class:`Measure` (the shared measure
picker), an aggregation (mean/median/sum) and a spread (SD/IQR/SEM/bootstrap
CI), and may z-score within reader — see :data:`MEASURES`,
:func:`aggregate_value`, :func:`spread_bounds`, :func:`add_normalized_column`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .multipart import SCREEN_ID, SCREEN_INDEX, grouping_columns, has_screen_identity


def metric_by_trial_index(
    frame: pd.DataFrame, metric: str, *, agg: str = "mean"
) -> pd.DataFrame:
    """Average of ``metric`` per trial index across all trials.

    ``frame`` must carry a ``trial_index`` column (see
    :func:`data.derive_trial_index`) and the ``metric`` column. Each trial
    contributes its own per-trial aggregate (``agg``), then those are averaged
    within each trial index. Returns ``DataFrame[trial_index, value, sem,
    n_trials]`` sorted by trial index.
    """
    cols = {"participant_id", "trial_id", "trial_index", metric}
    if frame.empty or not cols <= set(frame.columns):
        return pd.DataFrame(columns=["trial_index", "value", "sem", "n_trials"])
    df = frame[["participant_id", "trial_id", "trial_index"]].copy()
    df["_m"] = pd.to_numeric(frame[metric], errors="coerce")
    df = df.dropna(subset=["trial_index", "_m"])
    if df.empty:
        return pd.DataFrame(columns=["trial_index", "value", "sem", "n_trials"])
    per_trial = (
        df.groupby(["participant_id", "trial_id", "trial_index"])["_m"]
        .agg(agg)
        .reset_index()
    )
    out = (
        per_trial.groupby("trial_index")["_m"]
        .agg(["mean", "sem", "count"])
        .reset_index()
    )
    out.columns = ["trial_index", "value", "sem", "n_trials"]
    out["sem"] = out["sem"].fillna(0.0)
    return out.sort_values("trial_index").reset_index(drop=True)


def metric_by_fixation_index(
    fixations: pd.DataFrame, metric: str, *, max_index: Optional[int] = None
) -> pd.DataFrame:
    """Average of ``metric`` per within-trial fixation index (``order_in_trial``).

    Returns ``DataFrame[fixation_index, value, sem, n]`` sorted by index. Only
    meaningful for per-fixation metrics (duration, saccade amplitude, …).
    """
    if (
        fixations.empty
        or metric not in fixations.columns
        or "order_in_trial" not in fixations.columns
    ):
        return pd.DataFrame(columns=["fixation_index", "value", "sem", "n"])
    df = pd.DataFrame(
        {
            "fixation_index": pd.to_numeric(
                fixations["order_in_trial"], errors="coerce"
            ),
            "_m": pd.to_numeric(fixations[metric], errors="coerce"),
        }
    ).dropna()
    if df.empty:
        return pd.DataFrame(columns=["fixation_index", "value", "sem", "n"])
    out = df.groupby("fixation_index")["_m"].agg(["mean", "sem", "count"]).reset_index()
    out.columns = ["fixation_index", "value", "sem", "n"]
    out["sem"] = out["sem"].fillna(0.0)
    if max_index is not None:
        out = out[out["fixation_index"] <= max_index]
    return out.sort_values("fixation_index").reset_index(drop=True)


def grouped_metric_values(
    frame: pd.DataFrame,
    metric: str,
    group_col: Optional[str] = None,
    *,
    max_groups: int = 12,
) -> Tuple[Dict[str, np.ndarray], int]:
    """Return ``({group_label: values_array}, n_dropped)`` for histograms.

    ``group_col=None`` yields a single ``"All"`` group. Otherwise one entry per
    distinct value of ``group_col``, keeping the ``max_groups`` largest by row
    count; ``n_dropped`` reports how many groups were left out (so the caller can
    note the cap rather than silently truncating).
    """
    if frame.empty or metric not in frame.columns:
        return {}, 0
    vals = pd.to_numeric(frame[metric], errors="coerce")
    if group_col is None or group_col not in frame.columns:
        arr = vals.dropna().to_numpy()
        return ({"All": arr} if arr.size else {}), 0
    counts = frame[group_col].value_counts()
    kept = list(counts.index[:max_groups])
    dropped = max(0, len(counts) - len(kept))
    groups: Dict[str, np.ndarray] = {}
    for g in kept:
        arr = vals[frame[group_col] == g].dropna().to_numpy()
        if arr.size:
            groups[str(g)] = arr
    return groups, dropped


def aggregate_word_measures_by_text(
    words: pd.DataFrame, text_col: str, text_id, *, agg: str = "mean", screen_id=None
) -> pd.DataFrame:
    """One-row-per-word frame for a text: word boxes + reading measures averaged
    across every participant who read it.

    The returned frame keeps the canonical measure column names
    (``total_fixation_duration_ms`` / ``n_fixations``) and the word-box geometry,
    so it can be fed straight to ``plots.make_scanpath_figure`` (words-only
    heatmap branch) for a per-text aggregated heatmap. Returns an empty frame
    when the text or geometry is missing.
    """
    if words.empty or "word_id" not in words.columns:
        return pd.DataFrame()
    # One screen only, like every other per-text helper (BUG-26) — grouping on
    # `word_id` across screens pools two coordinate spaces.
    sub = _text_subset(words, text_col, text_id, screen_id)
    if sub.empty:
        return pd.DataFrame()
    measure_cols = [
        c
        for c in ("total_fixation_duration_ms", "n_fixations", "first_fixation_ms")
        if c in sub.columns
    ]
    geom_cols = [
        c for c in ("x", "y", "width", "height", "text", "line_idx") if c in sub.columns
    ]
    if not geom_cols:
        return pd.DataFrame()
    grouped = sub.groupby("word_id")
    out = grouped[geom_cols].first()
    for col in measure_cols:
        out[col] = grouped[col].agg(
            lambda s: pd.to_numeric(s, errors="coerce").agg(agg)
        )
    out = out.reset_index()
    # The heatmap path keys off participant/trial existence only for filtering;
    # tag a synthetic single "trial" so downstream code that expects the columns
    # doesn't choke.
    out["participant_id"] = "aggregate"
    out["trial_id"] = str(text_id)
    return out


def text_read_counts(words: pd.DataFrame, text_col: str) -> pd.DataFrame:
    """Per-text participant counts: ``DataFrame[text, n_participants]`` sorted
    by count desc — used to populate the per-text heatmap picker and annotate
    sample sizes."""
    if words.empty or text_col not in words.columns or "participant_id" not in words:
        return pd.DataFrame(columns=["text", "n_participants"])
    counts = words.groupby(text_col)["participant_id"].nunique().reset_index()
    counts.columns = ["text", "n_participants"]
    return counts.sort_values("n_participants", ascending=False).reset_index(drop=True)


# =============================================================================
# Question-oriented analysis sections (AN-1 … AN-28)
# =============================================================================
#
# Everything below is pure pandas/numpy feeding ``plots.make_*`` builders, one
# tidy DataFrame per view. The shared cross-cutting controls — measure picker
# (AN-23), aggregation/spread (AN-24), within-reader normalization (AN-25), and
# the min-observations guard (AN-26) — are expressed here so the figures and the
# CSV downloads (AN-27) all read the same numbers.


@dataclass(frozen=True)
class Measure:
    """One selectable eye-movement measure (the shared measure picker, AN-23).

    ``frame`` is ``"words"`` (a per-word reading measure, keyed by ``word_id``)
    or ``"fixations"`` (a per-fixation measure). ``per_word`` marks the
    word-level measures that support the per-word *profile* views (AN-1/2/3/…);
    ``is_rate`` marks boolean flags aggregated as a 0–1 rate (skip / regression).
    """

    key: str
    label: str
    frame: str  # "words" | "fixations"
    column: str
    unit: str  # axis-label unit, e.g. "ms", "px", "" (rates)
    per_word: bool
    is_rate: bool = False

    @property
    def axis_label(self) -> str:
        return f"{self.label} ({self.unit})" if self.unit else self.label


# Registry — insertion order is the picker order. TFD is the default.
MEASURES: Dict[str, Measure] = {
    m.key: m
    for m in (
        Measure(
            "tfd",
            "Total fixation duration — TFD",
            "words",
            "total_fixation_duration_ms",
            "ms",
            True,
        ),
        Measure(
            "ffd",
            "First fixation duration — FFD",
            "words",
            "first_fixation_ms",
            "ms",
            True,
        ),
        Measure(
            "fprt",
            "First-pass gaze — FPRT",
            "words",
            "first_pass_gaze_duration_ms",
            "ms",
            True,
        ),
        Measure(
            "rpd",
            "Regression-path — RPD",
            "words",
            "regression_path_duration_ms",
            "ms",
            True,
        ),
        Measure("nfix", "Fixations per word", "words", "n_fixations", "", True),
        Measure("skip", "Skip rate", "words", "skip_flag", "", True, is_rate=True),
        Measure(
            "reg_in",
            "Regression-in rate",
            "words",
            "regression_in_flag",
            "",
            True,
            is_rate=True,
        ),
        Measure(
            "reg_out",
            "Regression-out rate",
            "words",
            "regression_out_flag",
            "",
            True,
            is_rate=True,
        ),
        Measure(
            "landing_position",
            "Initial landing position",
            "words",
            "initial_landing_position",
            "letters",
            True,
        ),
        Measure(
            "landing_distance",
            "Centred landing distance",
            "words",
            "initial_landing_distance",
            "letters",
            True,
        ),
        Measure(
            "reg_in_count",
            "Regressions into word",
            "words",
            "number_of_regressions_in",
            "",
            True,
        ),
        Measure(
            "second_pass",
            "Second-pass duration",
            "words",
            "second_pass_duration_ms",
            "ms",
            True,
        ),
        Measure(
            "single_fix",
            "Single-fixation duration",
            "words",
            "single_fixation_duration_ms",
            "ms",
            True,
        ),
        Measure(
            "fix_dur", "Fixation duration", "fixations", "duration_ms", "ms", False
        ),
        # BUG-25: "px" is honest now — `saccade_amplitude` is always the pixel
        # distance between consecutive fixations. EyeLink's degree-valued
        # amplitudes normalize to `next_/prev_saccade_amplitude_deg` and never
        # reach this measure, so the axis label can't disagree with the data.
        Measure(
            "sacc_amp",
            "Saccade amplitude",
            "fixations",
            "saccade_amplitude",
            "px",
            False,
        ),
    )
}

# Bundled per-word linguistic features (AN-5). label → (column, is_categorical).
LINGUISTIC_FEATURES: Dict[str, Tuple[str, bool]] = {
    "GPT-2 surprisal": ("gpt2_surprisal", False),
    "Word frequency (wordfreq)": ("wordfreq_frequency", False),
    "Word length": ("word_length", False),
    "Part of speech": ("universal_pos", True),
}


def available_measures(
    words: pd.DataFrame, fixations: pd.DataFrame, *, per_word_only: bool = False
) -> List[Measure]:
    """The measures whose backing column is actually present in the data."""
    out: List[Measure] = []
    for m in MEASURES.values():
        if per_word_only and not m.per_word:
            continue
        frame = words if m.frame == "words" else fixations
        if frame is not None and m.column in getattr(frame, "columns", []):
            out.append(m)
    return out


def available_features(words: pd.DataFrame) -> Dict[str, Tuple[str, bool]]:
    """Linguistic features present in this words frame (AN-5)."""
    if words is None or words.empty:
        return {}
    return {
        label: spec
        for label, spec in LINGUISTIC_FEATURES.items()
        if spec[0] in words.columns
    }


# --- Aggregation + spread primitives (AN-24) ---------------------------------

_AGG_FUNCS = {"mean": np.nanmean, "median": np.nanmedian, "sum": np.nansum}


def aggregate_value(values: np.ndarray, agg: str = "mean") -> float:
    """Collapse ``values`` to a single number under ``agg`` (mean/median/sum)."""
    arr = np.asarray(values, dtype="float64")
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return float("nan")
    return float(_AGG_FUNCS.get(agg, np.nanmean)(arr))


def bootstrap_ci(
    values: np.ndarray,
    *,
    agg: str = "mean",
    n_boot: int = 1000,
    ci: float = 95.0,
    seed: int = 0,
) -> Tuple[float, float]:
    """Percentile bootstrap CI of the ``agg`` statistic (AN-24 spread option)."""
    arr = np.asarray(values, dtype="float64")
    arr = arr[~np.isnan(arr)]
    if arr.size < 2:
        v = aggregate_value(arr, agg)
        return (v, v)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_boot, arr.size))
    stats = _AGG_FUNCS.get(agg, np.nanmean)(arr[idx], axis=1)
    lo = float(np.percentile(stats, (100.0 - ci) / 2.0))
    hi = float(np.percentile(stats, 100.0 - (100.0 - ci) / 2.0))
    return (lo, hi)


def spread_bounds(values: np.ndarray, center: float, spread: str, *, agg: str = "mean"):
    """``(lo, hi)`` band for ``values`` around ``center`` under ``spread``.

    ``SD`` → ±1 std · ``SEM`` → ±std/√n · ``IQR`` → 25th/75th percentiles ·
    ``Bootstrap CI`` → 95 % percentile bootstrap of the aggregate.
    """
    arr = np.asarray(values, dtype="float64")
    arr = arr[~np.isnan(arr)]
    if arr.size == 0 or np.isnan(center):
        return (center, center)
    if spread == "IQR":
        return (float(np.percentile(arr, 25)), float(np.percentile(arr, 75)))
    if spread == "Bootstrap CI":
        return bootstrap_ci(arr, agg=agg)
    if agg == "sum":
        # SD/SEM describe the spread of individual observations, which is
        # meaningless around a *total*; bootstrap the aggregate so the band
        # actually brackets the plotted sum.
        return bootstrap_ci(arr, agg=agg)
    sd = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    half = sd / np.sqrt(arr.size) if spread == "SEM" else sd
    return (center - half, center + half)


def add_normalized_column(
    frame: pd.DataFrame,
    col: str,
    *,
    by: str = "participant_id",
    out_col: Optional[str] = None,
) -> pd.DataFrame:
    """Return ``frame`` with ``col`` z-scored within each ``by`` group (AN-25).

    Slow and fast readers then compare on *shape*, not absolute level. Groups of
    one (or zero variance) map to 0. ``out_col`` defaults to overwriting ``col``.
    """
    out = frame.copy()
    out_col = out_col or col
    vals = pd.to_numeric(out[col], errors="coerce")
    if by in out.columns:
        grp = vals.groupby(out[by])
        mean = grp.transform("mean")
        std = grp.transform("std")
    else:
        mean = vals.mean()
        std = vals.std()
    z = (
        (vals - mean) / std.replace(0, np.nan)
        if hasattr(std, "replace")
        else ((vals - mean) / (std or np.nan))
    )
    # `fillna(0.0)` alone conflates two different undefined-z cases: a
    # zero-variance or singleton group (where 0 *is* the group mean, so 0 is
    # right) and a genuinely missing observation, which would re-enter the
    # distribution as an exactly-average data point. Keep the first, restore NaN
    # for the second — so normalizing doesn't change how many observations there
    # are (ENG-1).
    out[out_col] = z.fillna(0.0).where(vals.notna())
    return out


#: Sentinel for "every screen" — only :func:`text_screen_options` passes it, to
#: enumerate the screens *before* one has been picked. It is deliberately not
#: part of the public helpers' contract: pooling across screens is the defect
#: BUG-26 fixed, so there is no user-reachable way back to it.
_ALL_SCREENS = object()


def text_screen_options(frame: pd.DataFrame, text_col: str, text_id) -> List[str]:
    """The screens one text is spread over, in reading order (BUG-26).

    Empty for a single-screen dataset — which is every corpus without DATA-21
    screen identity, so callers can treat "no options" as "there is nothing to
    pick". Ordered by ``screen_index`` when present (MultiplEYE ranks it by first
    fixation onset, i.e. the order the reader actually went through the pages),
    else by first appearance.
    """
    if frame is None or frame.empty or not has_screen_identity(frame):
        return []
    sub = _text_subset(frame, text_col, text_id, screen_id=_ALL_SCREENS)
    if sub.empty:
        return []
    if SCREEN_INDEX in sub.columns:
        order = (
            sub[[SCREEN_ID, SCREEN_INDEX]]
            .assign(**{SCREEN_INDEX: pd.to_numeric(sub[SCREEN_INDEX], errors="coerce")})
            .groupby(SCREEN_ID, sort=False)[SCREEN_INDEX]
            .min()
            .sort_values(kind="stable")
        )
        return [str(value) for value in order.index]
    return [str(value) for value in sub[SCREEN_ID].astype(str).unique()]


def _text_subset(
    frame: pd.DataFrame, text_col: str, text_id, screen_id=None
) -> pd.DataFrame:
    """One text's rows, scoped to **one screen** when the frame has screens.

    BUG-26: ``word_id`` is unique only *within* a screen (which is why
    :func:`multipart.grouping_columns` appends ``screen_id``), so a per-text
    aggregation keyed on ``(text_id, word_id)`` pools page 1's word 0 with page
    2's — and, on MultiplEYE since DATA-24, with each comprehension-question
    screen's first word as well.

    ``screen_id=None`` therefore does **not** mean "all screens": on a frame with
    screen identity it scopes to the *first* screen in reading order, so a caller
    that hasn't been updated gets a coherent single-screen answer rather than a
    silently pooled one. Frames without screen identity ignore the argument
    entirely, which is every dataset that is not multipart.
    """
    if frame is None or frame.empty:
        return pd.DataFrame()
    sub = frame
    if text_col and text_col in sub.columns:
        sub = sub[sub[text_col].astype(str) == str(text_id)]
    if screen_id is _ALL_SCREENS or not has_screen_identity(sub) or sub.empty:
        return sub
    screens = sub[SCREEN_ID].astype(str)
    if screen_id is None:
        wanted = _first_screen(sub, screens)
        if wanted is None:
            return sub
    else:
        wanted = str(screen_id)
    return sub[screens == wanted]


def _first_screen(sub: pd.DataFrame, screens: pd.Series) -> Optional[str]:
    """The lowest-``screen_index`` screen id in ``sub``, else the first seen."""
    if SCREEN_INDEX in sub.columns:
        index = pd.to_numeric(sub[SCREEN_INDEX], errors="coerce")
        if index.notna().any():
            return str(screens[index.idxmin()])
    return str(screens.iloc[0]) if len(screens) else None


def _measure_series(frame: pd.DataFrame, measure: Measure) -> pd.Series:
    """Numeric series for ``measure``; booleans/rates coerced to 0/1 floats."""
    s = frame[measure.column]
    if measure.is_rate:
        if pd.api.types.is_bool_dtype(s):
            return s.astype("float64")
        return pd.to_numeric(s, errors="coerce").astype("float64")
    return pd.to_numeric(s, errors="coerce")


# --- Per text: one text, many readers (AN-1 … AN-6) --------------------------


def per_reader_word_measure(
    words: pd.DataFrame,
    text_col: str,
    text_id,
    measure: Measure,
    *,
    agg: str = "mean",
    normalize: bool = False,
    screen_id=None,
) -> pd.DataFrame:
    """Tidy ``[participant_id, word_id, value, word_text]`` for one text (AN-1/2).

    One row per (reader, word). ``agg`` collapses any repeated readings; values
    are optionally z-scored within reader first (AN-25). ``screen_id`` picks the
    screen on a multipart text — see :func:`_text_subset` for why there is no
    "all screens".
    """
    cols = {"participant_id", "word_id", measure.column}
    sub = _text_subset(words, text_col, text_id, screen_id)
    if sub.empty or not cols <= set(sub.columns):
        return pd.DataFrame(columns=["participant_id", "word_id", "value", "word_text"])
    df = sub[["participant_id", "word_id"]].copy()
    df["value"] = _measure_series(sub, measure).to_numpy()
    if "text" in sub.columns:
        df["word_text"] = sub["text"].to_numpy()
    df = df.dropna(subset=["word_id", "value"])
    if df.empty:
        return pd.DataFrame(columns=["participant_id", "word_id", "value", "word_text"])
    if normalize and not measure.is_rate:
        df = add_normalized_column(df, "value")
    keys = ["participant_id", "word_id"]
    agg_map = {"value": agg}
    if "word_text" in df.columns:
        agg_map["word_text"] = "first"
    out = df.groupby(keys, as_index=False).agg(agg_map)
    return out.sort_values(["participant_id", "word_id"]).reset_index(drop=True)


def cohort_word_profile(
    words: pd.DataFrame,
    text_col: str,
    text_id,
    measure: Measure,
    *,
    agg: str = "mean",
    spread: str = "SD",
    normalize: bool = False,
    min_readers: int = 1,
    screen_id=None,
) -> pd.DataFrame:
    """Per-word cohort centre + spread band across readers (AN-3 / AN-15).

    Returns ``[word_id, value, lo, hi, n, enough, word_text]`` where ``value`` is
    the ``agg`` across readers of each reader's per-word value, ``lo``/``hi`` the
    ``spread`` band, ``n`` the contributing reader count and ``enough`` the
    min-readers guard (AN-26).
    """
    per = per_reader_word_measure(
        words,
        text_col,
        text_id,
        measure,
        agg=agg,
        normalize=normalize,
        screen_id=screen_id,
    )
    cols = ["word_id", "value", "lo", "hi", "n", "enough", "word_text"]
    if per.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    texts = (
        per.groupby("word_id")["word_text"].first()
        if "word_text" in per.columns
        else None
    )
    for wid, grp in per.groupby("word_id"):
        vals = grp["value"].to_numpy()
        center = aggregate_value(vals, agg)
        lo, hi = spread_bounds(vals, center, spread, agg=agg)
        rows.append(
            {
                "word_id": wid,
                "value": center,
                "lo": lo,
                "hi": hi,
                "n": int(np.sum(~np.isnan(vals))),
                "enough": int(np.sum(~np.isnan(vals))) >= min_readers,
                "word_text": texts.get(wid, "") if texts is not None else "",
            }
        )
    return (
        pd.DataFrame(rows, columns=cols).sort_values("word_id").reset_index(drop=True)
    )


def word_box_aggregate(
    words: pd.DataFrame,
    text_col: str,
    text_id,
    measure: Measure,
    *,
    agg: str = "mean",
    screen_id=None,
) -> pd.DataFrame:
    """One-row-per-word frame: word-box geometry + a ``value`` column = the
    ``measure`` aggregated across readers (AN-4 stimulus tint).

    Carries the canonical geometry (x/y/width/height/text/line_idx) + a synthetic
    participant/trial so it feeds straight into ``plots.make_scanpath_figure``'s
    words-only path. One screen only (BUG-26): the boxes are measured against
    their own screen's origin, so two screens' geometry would draw on top of each
    other however the values were keyed.
    """
    sub = _text_subset(words, text_col, text_id, screen_id)
    if sub.empty or "word_id" not in sub.columns or measure.column not in sub.columns:
        return pd.DataFrame()
    geom_cols = [
        c for c in ("x", "y", "width", "height", "text", "line_idx") if c in sub.columns
    ]
    if not geom_cols:
        return pd.DataFrame()
    work = sub[["word_id"] + geom_cols].copy()
    work["_m"] = _measure_series(sub, measure).to_numpy()
    grouped = work.groupby("word_id")
    out = grouped[geom_cols].first()
    out["value"] = grouped["_m"].agg(lambda s: aggregate_value(s.to_numpy(), agg))
    out = out.reset_index()
    out["participant_id"] = "aggregate"
    out["trial_id"] = str(text_id)
    return out


def word_measure_vs_feature(
    words: pd.DataFrame,
    text_col: str,
    text_id,
    measure: Measure,
    feature_col: str,
    *,
    agg: str = "mean",
    normalize: bool = False,
    screen_id=None,
) -> pd.DataFrame:
    """Per-word ``[word_id, value, feature, word_text]`` for a measure vs a
    bundled linguistic feature (AN-5). ``value`` is the cross-reader aggregate;
    ``feature`` is the per-word feature (constant across readers)."""
    per = per_reader_word_measure(
        words,
        text_col,
        text_id,
        measure,
        agg=agg,
        normalize=normalize,
        screen_id=screen_id,
    )
    sub = _text_subset(words, text_col, text_id, screen_id)
    if per.empty or feature_col not in sub.columns:
        return pd.DataFrame(columns=["word_id", "value", "feature", "word_text"])
    center_agg = {"value": ("value", lambda s: aggregate_value(s.to_numpy(), agg))}
    if "word_text" in per.columns:
        # Gate on column presence — never synthesize a count under this name.
        center_agg["word_text"] = ("word_text", "first")
    center = per.groupby("word_id").agg(**center_agg).reset_index()
    feat = sub.groupby("word_id")[feature_col].first().rename("feature").reset_index()
    out = center.merge(feat, on="word_id", how="left")
    return out.dropna(subset=["value"]).reset_index(drop=True)


def word_rate_profile(
    words: pd.DataFrame,
    text_col: str,
    text_id,
    *,
    min_readers: int = 1,
    screen_id=None,
) -> pd.DataFrame:
    """Per-word skip / regression-in rates across readers (AN-6).

    Returns ``[word_id, skip_rate, regression_in_rate, n, enough, word_text]``.
    """
    sub = _text_subset(words, text_col, text_id, screen_id)
    cols = ["word_id", "skip_rate", "regression_in_rate", "n", "enough", "word_text"]
    if sub.empty or "word_id" not in sub.columns:
        return pd.DataFrame(columns=cols)
    work = sub[["word_id"]].copy()
    for src, dst in (
        ("skip_flag", "skip_rate"),
        ("regression_in_flag", "regression_in_rate"),
    ):
        if src in sub.columns:
            s = sub[src]
            work[dst] = (
                s.astype("float64")
                if pd.api.types.is_bool_dtype(s)
                else pd.to_numeric(s, errors="coerce")
            ).to_numpy()
        else:
            work[dst] = np.nan
    if "text" in sub.columns:
        work["word_text"] = sub["text"].to_numpy()
    # Collapse to one row per (word, reader) FIRST, the way per_reader_word_measure
    # does. Without it `n` counts rows, so a reader who read the text twice counts
    # as two readers and clears a min_readers guard they shouldn't — and the rates
    # below are row-weighted, over-counting whoever re-read (ENG-1).
    if "participant_id" in sub.columns:
        work["participant_id"] = sub["participant_id"].to_numpy()
        text_by_word = (
            work.groupby("word_id")["word_text"].first()
            if "word_text" in work.columns
            else None
        )
        work = work.groupby(["word_id", "participant_id"], as_index=False).mean(
            numeric_only=True
        )
        if text_by_word is not None:
            work["word_text"] = work["word_id"].map(text_by_word)
    grouped = work.groupby("word_id")
    out = grouped.agg(
        skip_rate=("skip_rate", "mean"),
        regression_in_rate=("regression_in_rate", "mean"),
        n=("skip_rate", "size"),
    ).reset_index()
    if "word_text" in work.columns:
        out = out.merge(
            grouped["word_text"].first().reset_index(), on="word_id", how="left"
        )
    else:
        out["word_text"] = ""
    out["enough"] = out["n"] >= min_readers
    return out[cols].sort_values("word_id").reset_index(drop=True)


# --- Per reader: one reader, many trials (AN-7 … AN-13) ----------------------


def measure_values(
    frame: pd.DataFrame, measure: Measure, *, normalize: bool = False
) -> np.ndarray:
    """Flat array of a measure's values (for distribution plots)."""
    if frame is None or frame.empty or measure.column not in frame.columns:
        return np.array([], dtype="float64")
    work = frame.copy()
    work["_m"] = _measure_series(work, measure).to_numpy()
    if normalize and not measure.is_rate:
        work = add_normalized_column(work, "_m")
    return work["_m"].dropna().to_numpy()


def reader_vs_cohort_values(
    frame: pd.DataFrame,
    participant_id,
    measure: Measure,
    *,
    normalize: bool = False,
) -> Dict[str, np.ndarray]:
    """``{"This reader": …, "Cohort": …}`` value arrays for a measure (AN-7)."""
    if frame is None or frame.empty or "participant_id" not in frame.columns:
        return {}
    work = frame.copy()
    work["_m"] = _measure_series(work, measure).to_numpy()
    if normalize and not measure.is_rate:
        work = add_normalized_column(work, "_m")
    is_target = work["participant_id"].astype(str) == str(participant_id)
    out: Dict[str, np.ndarray] = {}
    me = work.loc[is_target, "_m"].dropna().to_numpy()
    others = work.loc[~is_target, "_m"].dropna().to_numpy()
    if me.size:
        out["This reader"] = me
    if others.size:
        out["Cohort"] = others
    return out


def _trial_reading_time_ms(fixations: pd.DataFrame) -> pd.DataFrame:
    """Per-(participant, trial) reading time in ms from the fixation span.

    Span = last fixation end − first fixation start (falls back to the sum of
    fixation durations when timestamps are missing)."""
    if fixations.empty or not {"participant_id", "trial_id"} <= set(fixations.columns):
        return pd.DataFrame(columns=["participant_id", "trial_id", "reading_time_ms"])
    keys = grouping_columns(fixations)
    df = fixations[keys].copy()
    dur = pd.to_numeric(fixations.get("duration_ms"), errors="coerce")
    if "timestamp_ms" in fixations.columns:
        ts = pd.to_numeric(fixations["timestamp_ms"], errors="coerce")
        df["_start"] = ts
        df["_end"] = ts + dur.fillna(0)
        grp = df.groupby(keys)
        out = (grp["_end"].max() - grp["_start"].min()).rename("reading_time_ms")
    else:
        df["_d"] = dur
        out = df.groupby(keys)["_d"].sum().rename("reading_time_ms")
    return out.reset_index()


def _first_present(frame: pd.DataFrame, columns: Sequence[str]):
    """First non-null value from the first available column."""
    if frame is None or frame.empty:
        return None
    for column in columns:
        if column not in frame.columns:
            continue
        values = frame[column].dropna()
        if not values.empty:
            return values.iloc[0]
    return None


def _as_accuracy(value) -> Optional[float]:
    """Coerce common correctness encodings to 0/1 without guessing blanks."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return float(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(bool(value))
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "correct", "1"}:
        return 1.0
    if text in {"false", "f", "no", "n", "incorrect", "0"}:
        return 0.0
    return None


def _run_summary(fixations: pd.DataFrame, n_words: int) -> Dict[str, float]:
    """Run/refixation and first-pass/rereading stats for one ordered trial.

    A run is a contiguous visit to one word. The first run on each word belongs
    to first pass; later visits are rereading. This works on normalized streams
    without requiring a corpus-specific ``pass_index`` convention.
    """
    if fixations.empty or "word_id" not in fixations.columns:
        return {}
    order = [
        c for c in ("timestamp_ms", "order_in_trial", "fixation_id") if c in fixations
    ]
    fx = fixations.sort_values(order, kind="stable") if order else fixations.copy()
    word = fx["word_id"]
    valid = word.notna()
    if not bool(valid.any()):
        return {}
    run_start = word.ne(word.shift()) | ~valid | ~valid.shift(fill_value=False)
    run_id = run_start.cumsum()
    visits = pd.DataFrame(
        {
            "word_id": word.to_numpy(),
            "run_id": run_id.to_numpy(),
            "duration_ms": pd.to_numeric(
                fx.get("duration_ms"), errors="coerce"
            ).to_numpy(),
        },
        index=fx.index,
    ).loc[valid]
    runs = (
        visits.groupby(["word_id", "run_id"], sort=False)
        .agg(duration_ms=("duration_ms", "sum"), n_fixations=("duration_ms", "size"))
        .reset_index()
    )
    runs["visit_index"] = runs.groupby("word_id", sort=False).cumcount()
    first = runs["visit_index"] == 0
    denominator = n_words or int(runs["word_id"].nunique())
    return {
        "nrun": int(len(runs)),
        "first_pass_ms": float(runs.loc[first, "duration_ms"].sum()),
        "rereading_ms": float(runs.loc[~first, "duration_ms"].sum()),
        "refixation_rate": float(
            (runs.loc[first, "n_fixations"] > 1).sum() / denominator
        )
        if denominator
        else np.nan,
    }


def trial_summary_table(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """One export-ready summary row per trial screen (or legacy trial) (AN-30).

    Includes the standard reading totals plus run-derived refixation and
    first-pass/rereading measures. Missing source concepts stay absent/NaN
    rather than being silently invented (for example blink count).
    """
    source = fixations if fixations is not None and not fixations.empty else words
    key_columns = grouping_columns(source)
    keys: list[tuple] = []
    for frame in (fixations, words):
        if frame is None or frame.empty or not set(key_columns) <= set(frame.columns):
            continue
        pairs = frame[key_columns].drop_duplicates()
        keys.extend(tuple(str(value) for value in row) for row in pairs.to_numpy())
    keys = list(dict.fromkeys(keys))
    rows: list[dict] = []
    for identity in keys:
        selected = dict(zip(key_columns, identity))

        def _slice(frame: pd.DataFrame) -> pd.DataFrame:
            if (
                frame is None
                or frame.empty
                or not set(key_columns) <= set(frame.columns)
            ):
                return pd.DataFrame()
            mask = pd.Series(True, index=frame.index)
            for column, value in selected.items():
                mask &= frame[column].astype(str) == value
            return frame[mask]

        fx, wd = _slice(fixations), _slice(words)
        row: dict = dict(selected)
        text_id = _first_present(
            wd if not wd.empty else fx, ("text_id", "unique_text_id")
        )
        if text_id is not None:
            row["text_id"] = text_id
        n_words = (
            int(wd["word_id"].nunique())
            if not wd.empty and "word_id" in wd.columns
            else 0
        )
        row["n_words"] = n_words
        if not fx.empty and "excluded" in fx.columns:
            fx = fx.loc[~fx["excluded"].fillna(False).astype(bool)]
        if not fx.empty:
            duration = pd.to_numeric(
                fx.get("duration_ms", pd.Series(np.nan, index=fx.index)),
                errors="coerce",
            )
            row["n_fixations"] = int(len(fx))
            if duration.notna().any():
                row["mean_fixation_ms"] = float(duration.mean())
                row["total_fixation_ms"] = float(duration.sum())
            amplitude = pd.to_numeric(
                fx.get("saccade_amplitude", pd.Series(np.nan, index=fx.index)),
                errors="coerce",
            )
            if amplitude.notna().any():
                row["mean_saccade_px"] = float(amplitude.mean())
                regression = (
                    pd.to_numeric(
                        fx.get("is_regression", pd.Series(False, index=fx.index)),
                        errors="coerce",
                    )
                    .fillna(0)
                    .astype(bool)
                )
                forward = amplitude[~regression]
                if forward.notna().any():
                    row["mean_forward_saccade_px"] = float(forward.mean())
            if "is_regression" in fx.columns:
                row["regression_rate"] = float(
                    pd.to_numeric(fx["is_regression"], errors="coerce").mean()
                )
            reading = _trial_reading_time_ms(fx)
            if not reading.empty:
                row["reading_time_ms"] = float(reading.iloc[0]["reading_time_ms"])
            row.update(_run_summary(fx, n_words))
            if "blink_count" in fx.columns:
                blink = pd.to_numeric(fx["blink_count"], errors="coerce").dropna()
                if not blink.empty:
                    row["blink_count"] = float(blink.max())
            elif "is_blink" in fx.columns:
                row["blink_count"] = int(
                    pd.to_numeric(fx["is_blink"], errors="coerce")
                    .fillna(0)
                    .astype(bool)
                    .sum()
                )
        if not wd.empty:
            if "skip_flag" in wd.columns:
                row["skip_rate"] = float(
                    pd.to_numeric(wd["skip_flag"], errors="coerce").mean()
                )
            if "regression_in_flag" in wd.columns:
                row["regression_in_rate"] = float(
                    pd.to_numeric(wd["regression_in_flag"], errors="coerce").mean()
                )
        if "regression_in_rate" not in row and "regression_rate" in row:
            row["regression_in_rate"] = row["regression_rate"]
        reading_ms = row.get("reading_time_ms")
        if n_words and reading_ms and reading_ms > 0:
            row["wpm"] = float(n_words / (reading_ms / 60000.0))
        correct = _as_accuracy(
            _first_present(
                wd if not wd.empty else fx, ("is_correct", "question_correct")
            )
        )
        if correct is not None:
            row["question_correct"] = correct
        rows.append(row)
    return pd.DataFrame(rows)


def reader_summary(
    words: pd.DataFrame, fixations: pd.DataFrame, participant_id
) -> Dict[str, float]:
    """Compact reading-profile stats for one reader (AN-8).

    WPM, mean fixation duration, fixation count, regression rate, skip rate,
    mean saccade amplitude, trial count — computed from whatever columns exist.
    """
    return _summary_row(words, fixations, participant_id)


def _summary_row(words, fixations, pid) -> Dict[str, float]:
    out: Dict[str, float] = {"participant_id": str(pid)}
    fx = (
        fixations[fixations["participant_id"].astype(str) == str(pid)]
        if not fixations.empty and "participant_id" in fixations.columns
        else pd.DataFrame()
    )
    wd = (
        words[words["participant_id"].astype(str) == str(pid)]
        if not words.empty and "participant_id" in words.columns
        else pd.DataFrame()
    )
    if not fx.empty:
        out["n_trials"] = (
            int(fx.groupby(["participant_id", "trial_id"]).ngroups)
            if {"participant_id", "trial_id"} <= set(fx.columns)
            else 0
        )
        out["n_fixations"] = int(len(fx))
        if "duration_ms" in fx.columns:
            out["mean_fixation_ms"] = float(
                pd.to_numeric(fx["duration_ms"], errors="coerce").mean()
            )
        if "saccade_amplitude" in fx.columns:
            out["mean_saccade_px"] = float(
                pd.to_numeric(fx["saccade_amplitude"], errors="coerce").mean()
            )
        if "is_regression" in fx.columns:
            out["regression_rate"] = float(
                pd.to_numeric(fx["is_regression"], errors="coerce").mean()
            )
        rt = _trial_reading_time_ms(fx)
        total_ms = float(pd.to_numeric(rt["reading_time_ms"], errors="coerce").sum())
        n_words = (
            int(wd.groupby(["trial_id", "word_id"]).ngroups)
            if not wd.empty and {"trial_id", "word_id"} <= set(wd.columns)
            else 0
        )
        if total_ms > 0 and n_words:
            out["wpm"] = float(n_words / (total_ms / 60000.0))
        trials = trial_summary_table(wd, fx)
        if not trials.empty:
            for column in (
                "total_fixation_ms",
                "blink_count",
                "nrun",
                "first_pass_ms",
                "rereading_ms",
                "n_question_correct",
            ):
                source = (
                    "question_correct" if column == "n_question_correct" else column
                )
                if source in trials.columns:
                    values = pd.to_numeric(trials[source], errors="coerce").dropna()
                    if not values.empty:
                        out[column] = float(values.sum())
            for column in (
                "mean_forward_saccade_px",
                "refixation_rate",
                "regression_in_rate",
                "comprehension_accuracy",
            ):
                source = (
                    "question_correct" if column == "comprehension_accuracy" else column
                )
                if source in trials.columns:
                    values = pd.to_numeric(trials[source], errors="coerce").dropna()
                    if not values.empty:
                        out[column] = float(values.mean())
    if not wd.empty and "skip_flag" in wd.columns:
        out["skip_rate"] = float(pd.to_numeric(wd["skip_flag"], errors="coerce").mean())
    return out


def cohort_summary_table(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    participants: Optional[Sequence] = None,
) -> pd.DataFrame:
    """One summary row per reader (AN-16 / AN-8 cohort percentiles)."""
    pids: List = []
    for frame in (fixations, words):
        if frame is not None and not frame.empty and "participant_id" in frame.columns:
            pids = list(pd.unique(frame["participant_id"].astype(str)))
            break
    if participants is not None:
        keep = {str(p) for p in participants}
        pids = [p for p in pids if p in keep]
    if not pids:
        return pd.DataFrame()
    rows = [_summary_row(words, fixations, p) for p in pids]
    return pd.DataFrame(rows)


def reader_summary_table(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    participants: Optional[Sequence] = None,
) -> pd.DataFrame:
    """First-class per-reader summary table (AN-30).

    Kept as an explicit public name rather than forcing callers to know the
    older ``cohort_summary_table`` terminology.
    """
    return cohort_summary_table(words, fixations, participants=participants)


def metric_over_time(
    fixations: pd.DataFrame,
    measure: Measure,
    *,
    participant_id=None,
    by: str = "order_in_trial",
) -> pd.DataFrame:
    """Mean of a per-fixation measure vs within-trial index (AN-9).

    Returns ``[x, value, sem, n]``. ``by`` is ``order_in_trial`` (default) or
    ``timestamp_ms``. Filtered to ``participant_id`` when given.
    """
    if (
        fixations.empty
        or measure.column not in fixations.columns
        or by not in fixations
    ):
        return pd.DataFrame(columns=["x", "value", "sem", "n"])
    fx = fixations
    if participant_id is not None and "participant_id" in fx.columns:
        fx = fx[fx["participant_id"].astype(str) == str(participant_id)]
    df = pd.DataFrame(
        {
            "x": pd.to_numeric(fx[by], errors="coerce"),
            "_m": _measure_series(fx, measure).to_numpy(),
        }
    ).dropna()
    if df.empty:
        return pd.DataFrame(columns=["x", "value", "sem", "n"])
    out = df.groupby("x")["_m"].agg(["mean", "sem", "count"]).reset_index()
    out.columns = ["x", "value", "sem", "n"]
    out["sem"] = out["sem"].fillna(0.0)
    return out.sort_values("x").reset_index(drop=True)


def saccade_vs_duration(
    fixations: pd.DataFrame, *, participant_id=None
) -> pd.DataFrame:
    """``[duration_ms, saccade_amplitude]`` rows for the oculomotor scatter (AN-10)."""
    need = {"duration_ms", "saccade_amplitude"}
    if fixations.empty or not need <= set(fixations.columns):
        return pd.DataFrame(columns=["duration_ms", "saccade_amplitude"])
    fx = fixations
    if participant_id is not None and "participant_id" in fx.columns:
        fx = fx[fx["participant_id"].astype(str) == str(participant_id)]
    out = pd.DataFrame(
        {
            "duration_ms": pd.to_numeric(fx["duration_ms"], errors="coerce"),
            "saccade_amplitude": pd.to_numeric(
                fx["saccade_amplitude"], errors="coerce"
            ),
        }
    ).dropna()
    return out.reset_index(drop=True)


def progressive_regressive_counts(
    fixations: pd.DataFrame, *, participant_id=None
) -> pd.DataFrame:
    """Per-trial progressive / regressive saccade counts + share (AN-11).

    Returns ``[trial_id, progressive, regressive, regression_share]``.
    """
    cols = ["trial_id", "progressive", "regressive", "regression_share"]
    if (
        fixations.empty
        or "is_regression" not in fixations.columns
        or "trial_id" not in fixations.columns
    ):
        return pd.DataFrame(columns=cols)
    fx = fixations
    if participant_id is not None and "participant_id" in fx.columns:
        fx = fx[fx["participant_id"].astype(str) == str(participant_id)]
    if fx.empty:
        return pd.DataFrame(columns=cols)
    reg = pd.to_numeric(fx["is_regression"], errors="coerce").fillna(0).astype(bool)
    df = pd.DataFrame({"trial_id": fx["trial_id"].to_numpy(), "_reg": reg.to_numpy()})
    out = df.groupby("trial_id")["_reg"].agg(["sum", "size"]).reset_index()
    out.columns = ["trial_id", "regressive", "_total"]
    out["progressive"] = out["_total"] - out["regressive"]
    out["regression_share"] = out["regressive"] / out["_total"].replace(0, np.nan)
    return out[cols].sort_values("trial_id").reset_index(drop=True)


def ensure_fixation_enrichment(
    fixations: pd.DataFrame, words: pd.DataFrame
) -> pd.DataFrame:
    """Add ``is_regression`` / ``saccade_amplitude`` to ``fixations`` if missing.

    The pre-aggregated OneStop path keeps the EyeLink IA measures on *words* and
    never enriches the fixation stream, so derived per-fixation columns (AN-11)
    aren't there. When ``word_id`` is present we run the same native enrichment
    (``measures.enrich_fixations``) the computed path uses; otherwise the frame
    is returned unchanged. Cheap and idempotent.
    """
    if fixations is None or fixations.empty:
        return fixations
    if "is_regression" in fixations.columns or "word_id" not in fixations.columns:
        return fixations
    try:
        from .measures import enrich_fixations

        return enrich_fixations(fixations, words)
    except Exception:  # pragma: no cover - defensive
        return fixations


def _box_left(
    words: pd.DataFrame, *, layout: Optional[pd.DataFrame] = None
) -> np.ndarray:
    """Corrected AOI left edges (BUG-11) — where "0% into the word" actually is.

    Landing position is a *within-word* measure, so it is exactly what a
    half-space offset corrupts: measured from the raw box left, every landing
    reads half a character later than it was.
    """
    from .measures import word_box_bounds

    return word_box_bounds(words, layout=layout)[0]


def landing_positions(
    words: pd.DataFrame,
    fixations: Optional[pd.DataFrame] = None,
    *,
    participant_id=None,
    as_fraction: bool = True,
) -> np.ndarray:
    """Within-word landing positions of the first fixation on each word (AN-12).

    Prefers the pre-computed ``first_fix_x`` on ``words`` (relative to the word
    box ``x``/``width``). When that's absent — the pre-aggregated OneStop path —
    it derives the landing from ``fixations``: the earliest fixation on each
    ``(participant, trial, word)``, joined to the word box. Returns the landing
    *fraction* (0 = word start, 1 = word end) by default, else the px distance.
    """
    if words is not None and not words.empty and "first_fix_x" in words.columns:
        wd = words
        if participant_id is not None and "participant_id" in wd.columns:
            wd = wd[wd["participant_id"].astype(str) == str(participant_id)]
        ffx = pd.to_numeric(wd.get("first_fix_x"), errors="coerce")
        left = pd.Series(_box_left(wd, layout=words), index=wd.index)
        width = pd.to_numeric(wd.get("width"), errors="coerce")
        dist = ffx - left
        if "right_to_left" in wd.columns:
            rtl = wd["right_to_left"].fillna(False).astype(bool)
            dist = dist.where(~rtl, width - dist)
        mask = ffx.notna() & left.notna() & width.notna() & (width > 0)
        if "skip_flag" in wd.columns:
            mask &= ~pd.to_numeric(wd["skip_flag"], errors="coerce").fillna(0).astype(
                bool
            )
        dist = dist[mask]
        width = width[mask]
    elif (
        fixations is not None
        and not fixations.empty
        and {"word_id", "x"} <= set(fixations.columns)
        and words is not None
        and {"word_id", "x", "width"} <= set(words.columns)
    ):
        fx = fixations
        if participant_id is not None and "participant_id" in fx.columns:
            fx = fx[fx["participant_id"].astype(str) == str(participant_id)]
        if fx.empty:
            return np.array([], dtype="float64")
        order_col = (
            "order_in_trial" if "order_in_trial" in fx.columns else "timestamp_ms"
        )
        keys = grouping_columns(fx, include_word=True)
        first = (
            fx.sort_values(order_col)
            .dropna(subset=["word_id"])
            .drop_duplicates(keys, keep="first")[keys + ["x"]]
            .rename(columns={"x": "_fx"})
        )
        box_keys = [k for k in keys if k in words.columns]
        extra = ["right_to_left"] if "right_to_left" in words else []
        box = words[box_keys + ["x", "width", *extra]].assign(_left=_box_left(words))
        box = box.drop_duplicates(box_keys)
        merged = first.merge(box, on=box_keys, how="inner")
        left = pd.to_numeric(merged["_left"], errors="coerce")
        width = pd.to_numeric(merged["width"], errors="coerce")
        dist = pd.to_numeric(merged["_fx"], errors="coerce") - left
        if "right_to_left" in merged:
            rtl = merged["right_to_left"].fillna(False).astype(bool)
            dist = dist.where(~rtl, width - dist)
        ok = dist.notna() & width.notna() & (width > 0)
        dist, width = dist[ok], width[ok]
    else:
        return np.array([], dtype="float64")
    if as_fraction:
        return (dist / width).clip(lower=0.0, upper=1.0).dropna().to_numpy()
    return dist.dropna().to_numpy()


def per_participant_trend(
    frame: pd.DataFrame, metric: str, *, agg: str = "mean"
) -> pd.DataFrame:
    """Per-participant per-trial-index trend (faint lines behind AN-17).

    Returns ``[participant_id, trial_index, value]``.
    """
    cols = {"participant_id", "trial_id", "trial_index", metric}
    if frame.empty or not cols <= set(frame.columns):
        return pd.DataFrame(columns=["participant_id", "trial_index", "value"])
    df = frame[["participant_id", "trial_id", "trial_index"]].copy()
    df["_m"] = pd.to_numeric(frame[metric], errors="coerce")
    df = df.dropna(subset=["trial_index", "_m"])
    per_trial = (
        df.groupby(["participant_id", "trial_id", "trial_index"])["_m"]
        .agg(agg)
        .reset_index()
    )
    out = (
        per_trial.groupby(["participant_id", "trial_index"])["_m"].mean().reset_index()
    )
    out.columns = ["participant_id", "trial_index", "value"]
    return out.sort_values(["participant_id", "trial_index"]).reset_index(drop=True)


# --- Groups + group comparison (AN-14 … AN-22) -------------------------------


def group_mask(frame: pd.DataFrame, spec: Mapping[str, Sequence]) -> pd.Series:
    """Boolean row mask for a group ``spec`` = ``{column: [allowed values]}``.

    Columns are AND-ed; within a column the row matches any listed value
    (compared as strings). Unifies both group-definition modes: a *field split*
    is two specs over the same column with disjoint values, while *independent
    filter sets* are specs with several columns. An empty spec selects all rows.
    """
    if frame is None or frame.empty:
        return pd.Series([], dtype=bool)
    mask = pd.Series(True, index=frame.index)
    for col, vals in (spec or {}).items():
        if col in frame.columns and vals:
            allowed = {str(v) for v in vals}
            mask &= frame[col].astype(str).isin(allowed)
    return mask


def apply_group(frame: pd.DataFrame, spec: Mapping[str, Sequence]) -> pd.DataFrame:
    """``frame`` rows selected by ``spec`` (see :func:`group_mask`)."""
    if frame is None or frame.empty:
        return frame
    return frame[group_mask(frame, spec)]


def two_group_values(
    frame: pd.DataFrame,
    measure: Measure,
    spec_a: Mapping,
    spec_b: Mapping,
    *,
    label_a: str = "Group A",
    label_b: str = "Group B",
    normalize: bool = False,
) -> Dict[str, np.ndarray]:
    """``{label_a: values, label_b: values}`` for overlaid distributions (AN-18)."""
    out: Dict[str, np.ndarray] = {}
    a = measure_values(apply_group(frame, spec_a), measure, normalize=normalize)
    b = measure_values(apply_group(frame, spec_b), measure, normalize=normalize)
    if a.size:
        out[label_a] = a
    if b.size:
        out[label_b] = b
    return out


def group_word_difference(
    words: pd.DataFrame,
    text_col: str,
    text_id,
    measure: Measure,
    spec_a: Mapping,
    spec_b: Mapping,
    *,
    agg: str = "mean",
    min_readers: int = 1,
) -> pd.DataFrame:
    """Per-word A−B difference profile for one text (AN-19).

    Returns ``[word_id, a, b, diff, n_a, n_b, enough, word_text]``.
    """
    cols = ["word_id", "a", "b", "diff", "n_a", "n_b", "enough", "word_text"]
    pa = cohort_word_profile(
        apply_group(words, spec_a),
        text_col,
        text_id,
        measure,
        agg=agg,
        min_readers=min_readers,
    )
    pb = cohort_word_profile(
        apply_group(words, spec_b),
        text_col,
        text_id,
        measure,
        agg=agg,
        min_readers=min_readers,
    )
    if pa.empty and pb.empty:
        return pd.DataFrame(columns=cols)
    a = pa[["word_id", "value", "n", "word_text"]].rename(
        columns={"value": "a", "n": "n_a"}
    )
    b = pb[["word_id", "value", "n"]].rename(columns={"value": "b", "n": "n_b"})
    out = a.merge(b, on="word_id", how="outer")
    out["diff"] = out["a"] - out["b"]
    # `a` always carries word_text (cohort_word_profile always returns it), so the
    # outer merge leaves NaN word_text on B-only words — backfill, don't no-op.
    out["word_text"] = out["word_text"].fillna("")
    out["n_a"] = out["n_a"].fillna(0).astype(int)
    out["n_b"] = out["n_b"].fillna(0).astype(int)
    out["enough"] = (out["n_a"] >= min_readers) & (out["n_b"] >= min_readers)
    return out[cols].sort_values("word_id").reset_index(drop=True)


def two_group_word_profiles(
    words: pd.DataFrame,
    text_col: str,
    text_id,
    measure: Measure,
    spec_a: Mapping,
    spec_b: Mapping,
    *,
    agg: str = "mean",
    label_a: str = "Group A",
    label_b: str = "Group B",
) -> pd.DataFrame:
    """Long ``[group, word_id, value]`` for the stacked two-group heatmap (AN-22)."""
    frames = []
    for spec, label in ((spec_a, label_a), (spec_b, label_b)):
        prof = cohort_word_profile(
            apply_group(words, spec), text_col, text_id, measure, agg=agg
        )
        if not prof.empty:
            frames.append(prof[["word_id", "value"]].assign(group=label))
    if not frames:
        return pd.DataFrame(columns=["group", "word_id", "value"])
    return pd.concat(frames, ignore_index=True)[["group", "word_id", "value"]]


def paired_group_summary(
    frame: pd.DataFrame,
    measures: Sequence[Measure],
    spec_a: Mapping,
    spec_b: Mapping,
    *,
    agg: str = "mean",
    spread: str = "SEM",
    label_a: str = "Group A",
    label_b: str = "Group B",
    words: Optional[pd.DataFrame] = None,
    fixations: Optional[pd.DataFrame] = None,
    normalize: bool = False,
) -> pd.DataFrame:
    """Per-measure group means + error for the paired bars (AN-20).

    Returns ``[measure, group, value, err_lo, err_hi, n]``. ``measures`` may mix
    word- and fixation-level measures; pass ``words``/``fixations`` so each reads
    its backing frame (``frame`` is the fallback).
    """
    rows = []
    for m in measures:
        src = (
            (words if m.frame == "words" else fixations)
            if (words is not None or fixations is not None)
            else frame
        )
        if src is None:
            continue
        for spec, label in ((spec_a, label_a), (spec_b, label_b)):
            vals = measure_values(apply_group(src, spec), m, normalize=normalize)
            center = aggregate_value(vals, agg)
            lo, hi = spread_bounds(vals, center, spread, agg=agg)
            rows.append(
                {
                    "measure": m.label,
                    "group": label,
                    # Clamp to ≥0: an asymmetric band (e.g. mean + IQR on skewed
                    # data) can put the centre outside [lo, hi], and a negative
                    # Plotly error-bar length renders in the wrong direction.
                    "value": center,
                    "err_lo": max(center - lo, 0.0),
                    "err_hi": max(hi - center, 0.0),
                    "n": int(vals.size),
                }
            )
    return pd.DataFrame(
        rows, columns=["measure", "group", "value", "err_lo", "err_hi", "n"]
    )


def group_effect_size(
    values_a: np.ndarray,
    values_b: np.ndarray,
    *,
    test: str = "Mann–Whitney",
) -> Dict[str, object]:
    """Mean difference, Cohen's *d*, and a significance test (AN-21).

    ``test`` is ``"Mann–Whitney"`` (rank-sum) or ``"t-test"`` (Welch). Returns a
    dict with the means, ``mean_diff``, ``cohen_d``, ``test``, ``statistic``,
    ``p_value`` and the group sizes. Exploratory — *not* pre-registered.
    """
    a = np.asarray(values_a, dtype="float64")
    a = a[~np.isnan(a)]
    b = np.asarray(values_b, dtype="float64")
    b = b[~np.isnan(b)]
    out: Dict[str, object] = {
        "mean_a": float(np.mean(a)) if a.size else float("nan"),
        "mean_b": float(np.mean(b)) if b.size else float("nan"),
        "n_a": int(a.size),
        "n_b": int(b.size),
        "test": test,
        "statistic": float("nan"),
        "p_value": float("nan"),
        "cohen_d": float("nan"),
    }
    out["mean_diff"] = out["mean_a"] - out["mean_b"]
    if a.size < 2 or b.size < 2:
        return out
    # Pooled-SD Cohen's d.
    va, vb = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled = np.sqrt(((a.size - 1) * va + (b.size - 1) * vb) / (a.size + b.size - 2))
    # NaN (not 0.0) when pooled SD is 0 but the means differ — 0.0 would falsely
    # read as "no effect" next to a non-zero mean difference. Matches the n<2 /
    # empty-input sentinels above.
    out["cohen_d"] = (
        float((np.mean(a) - np.mean(b)) / pooled) if pooled > 0 else float("nan")
    )
    try:
        from scipy import stats  # BSD-3; added for AN-21 (see PRE-0 ADR).

        if test == "t-test":
            res = stats.ttest_ind(a, b, equal_var=False)
        else:
            res = stats.mannwhitneyu(a, b, alternative="two-sided")
        out["statistic"] = float(res.statistic)
        out["p_value"] = float(res.pvalue)
    except Exception:  # pragma: no cover - scipy always present once added
        pass
    return out
