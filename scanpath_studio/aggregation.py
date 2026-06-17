"""Pure aggregation helpers for the Corpus Analysis → Aggregated Views subtab.

Headless (no Streamlit), so they're unit-testable. They turn the filtered
words / fixations frames into the small summary tables the plot builders draw:
per-trial-index trends, per-fixation-index trends, grouped metric distributions,
and per-text word-level aggregates for heatmaps. The heavy work is plain pandas
groupby; the tab caches the results with ``@st.cache_data``.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


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
    words: pd.DataFrame, text_col: str, text_id, *, agg: str = "mean"
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
    sub = words[words[text_col] == text_id] if text_col in words.columns else words
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
