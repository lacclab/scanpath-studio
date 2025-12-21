from __future__ import annotations

import importlib.resources as resources
import io
import zipfile
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="Scanpath Visualization Workbench",
    page_icon="👀",
    layout="wide",
)

PACKAGE_NAME = "scanpath_visualization_app"
FONT_FAMILY = "Lucida Sans Typewriter, Lucida Console, monospace"
DEFAULT_FIGURE_SIZE = (1100, 720)


def pick_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    """Return the first matching column name from a candidate list."""
    for name in candidates:
        if name in df.columns:
            return name
    return None


@st.cache_data
def load_sample_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load the bundled demo data (csv only) so users can try the app instantly."""
    data_root = resources.files(PACKAGE_NAME).joinpath("sample_data")
    words_resource = data_root / "ia.csv"
    fixations_resource = data_root / "fixations.csv"

    try:
        with resources.as_file(words_resource) as words_path, resources.as_file(fixations_resource) as fixations_path:
            words = pd.read_csv(words_path)
            fixations = pd.read_csv(fixations_path)
    except FileNotFoundError:
        st.error(
            "Bundled sample data not found. Expected ia.csv and fixations.csv "
            "under the installed package's sample_data directory."
        )
        return pd.DataFrame(), pd.DataFrame()

    return words, fixations


def infer_word_schema(words: pd.DataFrame) -> Optional[Dict[str, str]]:
    participant = pick_column(words, ["participant_id", "subject_id", "participant", "recording_session_label"])
    trial = pick_column(
        words,
        ["trial_id", "paragraph_id", "unique_paragraph_id", "trial", "trial_index", "TRIAL_INDEX"],
    )
    paragraph = pick_column(words, ["paragraph_id", "unique_paragraph_id", "PARAGRAPH_ID"])
    word_id = pick_column(words, ["word_id", "IA_ID", "ia_id", "ia_index"])
    text = pick_column(
        words,
        [
            "text",
            "IA_LABEL",
            "ia_label",
            "label",
            "word",
            "WORD",
            "content",
            "CONTENT",
            "token",
            "TOKEN",
        ],
    )
    line = pick_column(words, ["line_idx", "line", "line_index", "IA_LINE_ID"])

    x = pick_column(words, ["x", "X", "left"])
    y = pick_column(words, ["y", "Y", "top"])
    width = pick_column(words, ["width", "WIDTH"])
    height = pick_column(words, ["height", "HEIGHT"])
    left = pick_column(words, ["IA_LEFT", "ia_left", "left"])
    right = pick_column(words, ["IA_RIGHT", "ia_right", "right"])
    top = pick_column(words, ["IA_TOP", "ia_top", "top"])
    bottom = pick_column(words, ["IA_BOTTOM", "ia_bottom", "bottom"])

    missing_core = [name for name, val in [("participant", participant), ("trial", trial), ("word_id", word_id)] if val is None]
    if missing_core:
        st.error(f"Missing required word fields in uploaded data: {', '.join(missing_core)}")
        return None

    has_xywh = all([x, y, width, height])
    has_box = all([left, right, top, bottom])
    if not has_xywh and not has_box:
        st.error("Words/IA data needs either (x, y, width, height) or (IA_LEFT, IA_RIGHT, IA_TOP, IA_BOTTOM).")
        return None

    return dict(
        participant=participant,
        trial=trial,
        paragraph=paragraph,
        word_id=word_id,
        text=text,
        line=line,
        x=x,
        y=y,
        width=width,
        height=height,
        left=left,
        right=right,
        top=top,
        bottom=bottom,
    )


def infer_fix_schema(fixations: pd.DataFrame) -> Optional[Dict[str, str]]:
    participant = pick_column(fixations, ["participant_id", "subject_id", "participant", "recording_session_label"])
    trial = pick_column(
        fixations,
        ["trial_id", "paragraph_id", "unique_paragraph_id", "trial", "trial_index", "TRIAL_INDEX"],
    )
    paragraph = pick_column(fixations, ["paragraph_id", "unique_paragraph_id", "PARAGRAPH_ID"])
    fixation_id = pick_column(fixations, ["fixation_id", "CURRENT_FIX_INDEX", "CURRENT_FIX_NUM"])
    timestamp = pick_column(
        fixations,
        ["timestamp_ms", "CURRENT_FIX_START", "CURRENT_FIX_START_TIME", "CURRENT_FIX_TIME", "CURRENT_FIX_ONSET"],
    )
    duration = pick_column(fixations, ["duration_ms", "CURRENT_FIX_DURATION", "CURRENT_FIX_LEN"])
    x = pick_column(fixations, ["x", "X", "CURRENT_FIX_X", "FPOGX"])
    y = pick_column(fixations, ["y", "Y", "CURRENT_FIX_Y", "FPOGY"])
    word_id = pick_column(
        fixations,
        ["word_id", "IA_ID", "ia_id", "CURRENT_FIX_INTEREST_AREA_ID", "CURRENT_FIX_INTEREST_AREA_INDEX"],
    )
    pass_index = pick_column(fixations, ["pass_index", "reread", "PASS_INDEX"])
    saccade_type = pick_column(fixations, ["saccade_type", "SACCADE_TYPE", "NEXT_SAC_DIRECTION"])
    eye = pick_column(fixations, ["eye", "EYE_USED", "eye_used"])
    noise_flag = pick_column(fixations, ["noise_flag", "CURRENT_FIX_VALIDITY", "CURRENT_FIX_VALID"])

    missing_core = [name for name, val in [("participant", participant), ("trial", trial), ("duration", duration), ("x", x), ("y", y)] if val is None]
    if missing_core:
        st.error(f"Missing required fixation fields in uploaded data: {', '.join(missing_core)}")
        return None

    return dict(
        participant=participant,
        trial=trial,
        paragraph=paragraph,
        fixation_id=fixation_id,
        timestamp=timestamp,
        duration=duration,
        x=x,
        y=y,
        word_id=word_id,
        pass_index=pass_index,
        saccade_type=saccade_type,
        eye=eye,
        noise_flag=noise_flag,
    )


def normalize_words(words: pd.DataFrame, schema: Dict[str, str]) -> pd.DataFrame:
    df = pd.DataFrame()
    df["participant_id"] = words[schema["participant"]].astype(str)
    df["trial_id"] = words[schema["trial"]].astype(str)
    if schema.get("paragraph"):
        df["paragraph_id"] = words[schema["paragraph"]].astype(str)
    else:
        df["paragraph_id"] = df["trial_id"]
    df["word_id"] = pd.to_numeric(words[schema["word_id"]], errors="coerce")
    if schema.get("text"):
        df["text"] = words[schema["text"]].astype(str)
    else:
        df["text"] = df["word_id"].apply(lambda v: f"w{int(v)}" if pd.notna(v) else "")
    df["text"] = df["text"].str.replace(r"\s+", " ", regex=True).str.strip()
    if schema.get("line"):
        df["line_idx"] = pd.to_numeric(words[schema["line"]], errors="coerce")
    else:
        df["line_idx"] = 1

    if all(schema.get(k) for k in ["x", "y", "width", "height"]):
        df["x"] = pd.to_numeric(words[schema["x"]], errors="coerce")
        df["y"] = pd.to_numeric(words[schema["y"]], errors="coerce")
        df["width"] = pd.to_numeric(words[schema["width"]], errors="coerce")
        df["height"] = pd.to_numeric(words[schema["height"]], errors="coerce")
    else:
        left = pd.to_numeric(words[schema["left"]], errors="coerce")
        right = pd.to_numeric(words[schema["right"]], errors="coerce")
        top = pd.to_numeric(words[schema["top"]], errors="coerce")
        bottom = pd.to_numeric(words[schema["bottom"]], errors="coerce")
        df["x"] = left
        df["y"] = top
        df["width"] = right - left
        df["height"] = bottom - top

    return df


def normalize_fixations(fixations: pd.DataFrame, schema: Dict[str, str]) -> pd.DataFrame:
    df = pd.DataFrame()
    df["participant_id"] = fixations[schema["participant"]].astype(str)
    df["trial_id"] = fixations[schema["trial"]].astype(str)
    if schema.get("paragraph"):
        df["paragraph_id"] = fixations[schema["paragraph"]].astype(str)
    else:
        df["paragraph_id"] = df["trial_id"]
    df["x"] = pd.to_numeric(fixations[schema["x"]], errors="coerce")
    df["y"] = pd.to_numeric(fixations[schema["y"]], errors="coerce")
    df["duration_ms"] = pd.to_numeric(fixations[schema["duration"]], errors="coerce").fillna(0)

    if schema.get("timestamp"):
        df["timestamp_ms"] = pd.to_numeric(fixations[schema["timestamp"]], errors="coerce").fillna(0)
    else:
        # Fall back to ordered index if no timestamps are available
        df["timestamp_ms"] = fixations.groupby([schema["participant"], schema["trial"]]).cumcount()

    if schema.get("fixation_id"):
        df["fixation_id"] = fixations[schema["fixation_id"]]
    else:
        df["fixation_id"] = (
            df.groupby(["participant_id", "trial_id"])
            .cumcount()
            .add(1)
        )

    if schema.get("word_id"):
        df["word_id"] = pd.to_numeric(fixations[schema["word_id"]], errors="coerce")
    else:
        df["word_id"] = np.nan
    if schema.get("pass_index"):
        df["pass_index"] = pd.to_numeric(fixations[schema["pass_index"]], errors="coerce")
    else:
        df["pass_index"] = 1
    if schema.get("saccade_type"):
        df["saccade_type"] = fixations[schema["saccade_type"]].astype(str)
    else:
        df["saccade_type"] = "unknown"
    if schema.get("eye"):
        df["eye"] = fixations[schema["eye"]].astype(str)
    else:
        df["eye"] = "Both"
    if schema.get("noise_flag"):
        df["noise_flag"] = fixations[schema["noise_flag"]]
    else:
        df["noise_flag"] = False

    df["order_in_trial"] = (
        df.sort_values(["timestamp_ms", "duration_ms"])
        .groupby(["participant_id", "trial_id"])
        .cumcount()
        + 1
    )
    return df


def filter_data(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    filters: Dict,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    participants = filters.get("participants") or list(words["participant_id"].unique())
    trials = filters.get("trials") or list(words["trial_id"].unique())
    word_mask = words["participant_id"].isin(participants) & words["trial_id"].isin(trials)
    words_filtered = words[word_mask]

    fix_mask = fixations["participant_id"].isin(participants) & fixations["trial_id"].isin(trials)
    if "pass_index" in fixations.columns:
        pass_indices = filters.get("pass_indices")
        if pass_indices:
            fix_mask &= fixations["pass_index"].isin(pass_indices)
    if "saccade_type" in fixations.columns:
        saccade_types = filters.get("saccade_types")
        if saccade_types:
            fix_mask &= fixations["saccade_type"].isin(saccade_types)
    if "eye" in fixations.columns:
        eyes = filters.get("eyes")
        if eyes:
            fix_mask &= fixations["eye"].isin(eyes)
    include_noise = filters.get("include_noise", True)
    if not include_noise and "noise_flag" in fixations.columns:
        fix_mask &= ~fixations["noise_flag"].fillna(False)
    fixations_filtered = fixations[fix_mask]
    return words_filtered, fixations_filtered


def build_word_boxes(words: pd.DataFrame, color: str = "#6c757d") -> list:
    shapes = []
    for _, row in words.iterrows():
        x0, y0 = row["x"], row["y"]
        x1, y1 = row["x"] + row["width"], row["y"] + row["height"]
        shapes.append(
            dict(
                type="rect",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                line=dict(color=color, width=1),
                fillcolor="rgba(100,100,100,0.05)",
            )
        )
    return shapes


def compute_canvas_size(words: pd.DataFrame, fixations: pd.DataFrame) -> Tuple[int, int]:
    """Suggest a canvas size based on observed coordinates."""
    candidates_x = []
    candidates_y = []
    if not words.empty:
        candidates_x.append((words["x"] + words["width"]).max())
        candidates_y.append((words["y"] + words["height"]).max())
    if not fixations.empty:
        candidates_x.append(fixations["x"].max())
        candidates_y.append(fixations["y"].max())
    default_w, default_h = DEFAULT_FIGURE_SIZE
    width = default_w
    height = default_h
    if candidates_x:
        x_max = np.nanmax(candidates_x)
        if not np.isnan(x_max):
            width = int(x_max)
    if candidates_y:
        y_max = np.nanmax(candidates_y)
        if not np.isnan(y_max):
            height = int(y_max)
    width = max(width, 100)
    height = max(height, 100)
    return width, height


def make_scanpath_figure(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    x_field: str,
    y_field: str,
    show_words: bool,
    show_word_labels: bool,
    show_fixations: bool,
    show_order: bool,
    show_saccades: bool,
    show_heatmap: bool,
    color_by: str,
    heatmap_metric: Optional[str],
    marker_size_range: Tuple[int, int],
    order_font_size: int,
    order_font_color: str,
    show_colorbars: bool,
    fixation_color_range: Optional[Tuple[float, float]],
    heatmap_range: Optional[Tuple[float, float]],
) -> go.Figure:
    fig = go.Figure()
    spatial_axes = x_field == "x" and y_field == "y"
    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)

    if spatial_axes and not words.empty:
        if show_words:
            fig.update_layout(shapes=build_word_boxes(words))
        if show_word_labels and "text" in words.columns:
            fig.add_trace(
                go.Scatter(
                    x=words["x"] + words["width"] / 2,
                    y=words["y"] + words["height"] / 2,
                    text=words["text"],
                    mode="text",
                    showlegend=False,
                    textfont=dict(color="#343a40", size=base_font_size, family=font_settings["family"]),
                    hovertemplate=(
                        "Word %{text}<br>Word ID %{customdata[0]}<br>Line %{customdata[1]}"
                        "<extra></extra>"
                    ),
                    customdata=words[["word_id", "line_idx"]],
                )
            )

    if spatial_axes and show_heatmap and not fixations.empty:
        weights = None
        if heatmap_metric == "duration_ms":
            weights = fixations["duration_ms"]
        histfunc = "sum" if weights is not None else "count"
        x_min = float((words["x"]).min()) if not words.empty else float(fixations[x_field].min())
        x_max = float((words["x"] + words["width"]).max()) if not words.empty else float(fixations[x_field].max())
        y_min = float((words["y"]).min()) if not words.empty else float(fixations[y_field].min())
        y_max = float((words["y"] + words["height"]).max()) if not words.empty else float(fixations[y_field].max())
        x_span = max(x_max - x_min, 1.0)
        y_span = max(y_max - y_min, 1.0)
        if not words.empty:
            x_edges = np.unique(np.sort(np.concatenate([words["x"].values, (words["x"] + words["width"]).values])))
            y_edges = np.unique(np.sort(np.concatenate([words["y"].values, (words["y"] + words["height"]).values])))
            if len(x_edges) > 1 and len(y_edges) > 1:
                hist, _, _ = np.histogram2d(
                    fixations[x_field],
                    fixations[y_field],
                    bins=[x_edges, y_edges],
                    weights=weights,
                )
                z_vals = hist.T
                x_centers = (x_edges[:-1] + x_edges[1:]) / 2
                y_centers = (y_edges[:-1] + y_edges[1:]) / 2
                fig.add_trace(
                    go.Heatmap(
                        x=x_centers,
                        y=y_centers,
                        z=z_vals,
                        colorscale="Blues",
                        opacity=0.35,
                        showscale=show_colorbars,
                        colorbar=dict(
                            title="Fixation density" if weights is None else "Duration (ms)",
                            x=1.02,
                        ),
                        zmin=heatmap_range[0] if heatmap_range else None,
                        zmax=heatmap_range[1] if heatmap_range else None,
                        xgap=0,
                        ygap=0,
                        zsmooth=False,
                    )
                )
        else:
            x_bin_size = x_span / 40.0
            y_bin_size = y_span / 40.0
            fig.add_trace(
                go.Histogram2d(
                    x=fixations[x_field],
                    y=fixations[y_field],
                    xbins=dict(start=x_min, end=x_max, size=x_bin_size),
                    ybins=dict(start=y_min, end=y_max, size=y_bin_size),
                    colorscale="Blues",
                    opacity=0.35,
                    showscale=show_colorbars,
                    colorbar=dict(
                        title="Fixation density" if weights is None else "Duration (ms)",
                        x=1.02,
                    ),
                    histfunc=histfunc,
                    z=weights,
                    zmin=heatmap_range[0] if heatmap_range else None,
                    zmax=heatmap_range[1] if heatmap_range else None,
                )
            )

    if spatial_axes and show_saccades and len(fixations) > 1:
        ordered = fixations.sort_values("timestamp_ms")
        for (_, row_a), (_, row_b) in zip(ordered.iloc[:-1].iterrows(), ordered.iloc[1:].iterrows()):
            fig.add_trace(
                go.Scatter(
                    x=[row_a[x_field], row_b[x_field]],
                    y=[row_a[y_field], row_b[y_field]],
                    mode="lines",
                    line=dict(color="#6f42c1", width=2),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    if show_fixations and not fixations.empty:
        ordered = fixations.sort_values("timestamp_ms")
        color_data = ordered[color_by] if color_by in ordered.columns else None
        is_numeric_color = (
            color_data is not None and pd.api.types.is_numeric_dtype(color_data)
        )

        durations = ordered["duration_ms"].fillna(0)
        d_min, d_max = float(durations.min()), float(durations.max())
        min_size, max_size = marker_size_range
        if d_max - d_min > 0:
            sizes = np.interp(durations, (d_min, d_max), (min_size, max_size))
        else:
            sizes = np.full(len(durations), (min_size + max_size) / 2)

        fig.add_trace(
            go.Scatter(
                x=ordered[x_field],
                y=ordered[y_field],
                mode="markers+text" if show_order else "markers",
                marker=dict(
                    size=sizes,
                    color=color_data,
                    colorscale="Blues" if is_numeric_color else None,
                    showscale=show_colorbars and is_numeric_color,
                    colorbar=dict(
                        title=color_by.replace("_", " ").title(),
                        x=1.12,
                    )
                    if show_colorbars and is_numeric_color
                    else None,
                    cmin=fixation_color_range[0] if fixation_color_range else None,
                    cmax=fixation_color_range[1] if fixation_color_range else None,
                    line=dict(color="#111", width=0.5),
                ),
                text=ordered["order_in_trial"] if show_order else None,
                textfont=dict(color=order_font_color, size=order_font_size, family=font_settings["family"]),
                textposition="top center",
                hovertemplate=(
                    "Order %{customdata[0]}<br>"
                    "Duration %{customdata[1]} ms<br>"
                    "Word %{customdata[2]}<br>"
                    "Pass %{customdata[3]}<br>"
                    "Saccade %{customdata[4]}<br>"
                    "Eye %{customdata[5]}<extra></extra>"
                ),
                customdata=np.stack(
                    [
                        ordered["order_in_trial"],
                        ordered["duration_ms"],
                        ordered.get("word_id", pd.Series([np.nan] * len(ordered))),
                        ordered.get("pass_index", pd.Series([np.nan] * len(ordered))),
                        ordered.get("saccade_type", pd.Series(["?"] * len(ordered))),
                        ordered.get("eye", pd.Series(["?"] * len(ordered))),
                    ],
                    axis=1,
                ),
                name="Fixations",
                showlegend=False,
            )
        )

    xaxis_cfg = dict(showticklabels=False, showgrid=False, zeroline=False, title=None)
    yaxis_cfg = dict(showticklabels=False, showgrid=False, zeroline=False, title=None)
    if spatial_axes:
        xaxis_cfg.update(range=[0, canvas_width], constrain="domain")
        yaxis_cfg.update(range=[canvas_height, 0], constrain="domain", scaleanchor="x", scaleratio=1)

    fig.update_layout(
        height=canvas_height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=xaxis_cfg,
        yaxis=yaxis_cfg,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        font=font_settings,
    )
    return fig


def make_timeline_chart(fixations: pd.DataFrame) -> go.Figure:
    if fixations.empty:
        return go.Figure()

    ordered = fixations.sort_values("timestamp_ms").copy()
    ordered["end_time_ms"] = ordered["timestamp_ms"] + ordered["duration_ms"]
    color_field = "pass_index" if "pass_index" in ordered.columns else None
    marker_kwargs = dict(size=8)
    if color_field:
        marker_kwargs.update(
            dict(color=ordered[color_field], colorscale="Plasma", showscale=True)
        )
    else:
        marker_kwargs.update(dict(color="#1f77b4"))

    fig = go.Figure(
        go.Scatter(
            x=ordered["timestamp_ms"],
            y=ordered["duration_ms"],
            mode="markers+lines",
            marker=marker_kwargs,
            text=ordered["order_in_trial"],
            hovertemplate=(
                "Order %{text}<br>Start %{x} ms<br>Duration %{y} ms<br>"
                "Word %{customdata[0]}<br>Saccade %{customdata[1]}<extra></extra>"
            ),
            customdata=np.stack(
                [
                    ordered.get("word_id", pd.Series([np.nan] * len(ordered))),
                    ordered.get("saccade_type", pd.Series([""] * len(ordered))),
                ],
                axis=1,
            ),
        )
    )
    fig.update_layout(
        height=300,
        xaxis_title="Start time (ms)",
        yaxis_title="Duration (ms)",
        template="plotly_white",
        margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig


def make_comparison_figure(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    trial_a: Tuple[str, str],
    trial_b: Tuple[str, str],
    *,
    canvas_width: int,
    canvas_height: int,
    font_family: str,
    base_font_size: int,
) -> go.Figure:
    fig = go.Figure()
    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)
    palette = ["#1f77b4", "#e45756"]
    for idx, trial in enumerate([trial_a, trial_b]):
        participant, trial_id = trial
        trial_words = words[
            (words["participant_id"] == participant) & (words["trial_id"] == trial_id)
        ]
        trial_fix = fixations[
            (fixations["participant_id"] == participant) & (fixations["trial_id"] == trial_id)
        ].sort_values("timestamp_ms")
        fig.add_trace(
            go.Scatter(
                x=trial_fix["x"],
                y=trial_fix["y"],
                mode="markers+lines",
                marker=dict(
                    size=9 + trial_fix["duration_ms"] * 0.04,
                    color=palette[idx],
                    line=dict(color="#111", width=0.5),
                ),
                line=dict(color=palette[idx], width=2, dash="solid"),
                name=f"{participant} – {trial_id}",
                text=trial_fix["order_in_trial"],
                textposition="top center",
                textfont=font_settings,
                hovertemplate=(
                    f"{participant}-{trial_id} "
                    "Order %{text}<br>Time %{customdata[0]} ms<br>Duration %{customdata[1]} ms<extra></extra>"
                ),
                customdata=trial_fix[["timestamp_ms", "duration_ms"]],
            )
        )
        existing_shapes = list(fig.layout.shapes) if fig.layout.shapes else []
        fig.update_layout(
            shapes=existing_shapes + build_word_boxes(trial_words, color=palette[idx])
        )

    fig.update_layout(
        height=canvas_height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False, title=None, range=[0, canvas_width], constrain="domain"),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, title=None, range=[canvas_height, 0], constrain="domain", scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        title="Overlay comparison",
        font=font_settings,
    )
    return fig


def compute_word_metrics(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    base = words[
        [
            "participant_id",
            "trial_id",
            "word_id",
            "text",
            "line_idx",
            "x",
            "y",
            "width",
            "height",
        ]
    ].copy()
    agg = (
        fixations.sort_values("timestamp_ms")
        .groupby(["participant_id", "trial_id", "word_id"])
        .agg(
            n_fixations=("fixation_id", "size"),
            total_duration_ms=("duration_ms", "sum"),
            first_fixation_ms=("duration_ms", "first"),
            first_timestamp_ms=("timestamp_ms", "first"),
            last_timestamp_ms=("timestamp_ms", "last"),
            first_pass_ms=(
                "duration_ms",
                lambda s: (
                    s[fixations.loc[s.index, "pass_index"] == 1].sum()
                    if "pass_index" in fixations.columns
                    else s.sum()
                ),
            ),
        )
        .reset_index()
    )
    metrics = base.merge(agg, on=["participant_id", "trial_id", "word_id"], how="left")
    metrics["skipped"] = metrics["n_fixations"].isna()
    metrics["n_fixations"] = metrics["n_fixations"].fillna(0).astype(int)
    metrics["total_duration_ms"] = metrics["total_duration_ms"].fillna(0)
    metrics["first_pass_ms"] = metrics["first_pass_ms"].fillna(0)
    return metrics


def default_filters(words: pd.DataFrame, fixations: pd.DataFrame) -> Dict:
    filters = dict(
        participants=sorted(words["participant_id"].unique()),
        trials=sorted(words["trial_id"].unique()),
    )
    if "pass_index" in fixations.columns:
        filters["pass_indices"] = sorted(fixations["pass_index"].dropna().unique())
    if "saccade_type" in fixations.columns:
        filters["saccade_types"] = sorted(fixations["saccade_type"].dropna().astype(str).unique())
    if "eye" in fixations.columns:
        filters["eyes"] = sorted(fixations["eye"].dropna().astype(str).unique())
    filters["include_noise"] = False if "noise_flag" in fixations.columns else True
    return filters


def sidebar_controls(trial_fixations: pd.DataFrame, base_font_size: int) -> Dict:
    st.sidebar.header("Visualization controls")
    show_words = st.sidebar.checkbox("Show word boxes", value=True)
    show_labels = st.sidebar.checkbox("Show word labels", value=True)
    show_fix = st.sidebar.checkbox("Show fixations", value=True)
    show_order = st.sidebar.checkbox("Number fixation order", value=True)
    show_saccades = st.sidebar.checkbox("Show saccades", value=True)
    show_heatmap = st.sidebar.checkbox("Add density heatmap", value=True)

    color_fields = [
        field
        for field in ["duration_ms", "pass_index", "eye", "saccade_type", "word_id", "timestamp_ms"]
        if field in trial_fixations.columns
    ]
    if not color_fields:
        color_fields = ["duration_ms"]
    color_by = st.sidebar.selectbox(
        "Color fixations by",
        options=color_fields,
        index=color_fields.index("duration_ms") if "duration_ms" in color_fields else 0,
    )
    heatmap_metric = st.sidebar.selectbox(
        "Heatmap metric",
        options=["duration_ms", "counts"],
        help="Heatmap can be raw counts or weighted by fixation duration.",
        index=0,
    )

    numeric_fields = [col for col in trial_fixations.columns if pd.api.types.is_numeric_dtype(trial_fixations[col])]
    if not numeric_fields:
        st.error("No numeric fields found in fixations to map axes.")
        st.stop()
    x_default = "x" if "x" in numeric_fields else numeric_fields[0]
    y_default = "y" if "y" in numeric_fields else numeric_fields[min(1, len(numeric_fields) - 1)]
    x_field = st.sidebar.selectbox("X axis field", options=numeric_fields, index=numeric_fields.index(x_default))
    y_field = st.sidebar.selectbox("Y axis field", options=numeric_fields, index=numeric_fields.index(y_default))

    st.sidebar.subheader("Advanced styling")
    advanced = st.sidebar.checkbox("Advanced styling", value=False)
    order_font_color = "#111111"
    order_font_size = int(base_font_size)
    size_min, size_max = 8, 24
    show_colorbars = True
    fixation_color_range = None
    heatmap_range = None
    if advanced:
        order_font_color = st.sidebar.color_picker("Order label color", value="#111111")
        order_font_size = st.sidebar.slider("Order label size", 6, 72, int(base_font_size))
        size_min, size_max = st.sidebar.slider("Fixation marker size (px)", 4, 40, (8, 24))
        show_colorbars = st.sidebar.checkbox("Show color bars", value=True)
        if show_colorbars and pd.api.types.is_numeric_dtype(trial_fixations[color_by]):
            cmin = float(trial_fixations[color_by].min())
            cmax = float(trial_fixations[color_by].max())
            fixation_color_range = st.sidebar.slider(
                "Fixation color range",
                min_value=cmin,
                max_value=cmax if cmax > cmin else cmin + 1.0,
                value=(cmin, cmax if cmax > cmin else cmin + 1.0),
                step=(cmax - cmin) / 100 if cmax > cmin else 1.0,
            )
        if show_colorbars and show_heatmap:
            heat_data = trial_fixations["duration_ms"] if heatmap_metric == "duration_ms" else None
            if heat_data is not None and len(heat_data) > 0:
                hmin = float(heat_data.min())
                hmax = float(heat_data.max())
                heatmap_range = st.sidebar.slider(
                    "Heatmap color range",
                    min_value=hmin,
                    max_value=hmax if hmax > hmin else hmin + 1.0,
                    value=(hmin, hmax if hmax > hmin else hmin + 1.0),
                    step=(hmax - hmin) / 100 if hmax > hmin else 1.0,
                )
    else:
        show_colorbars = True

    return dict(
        show_words=show_words,
        show_labels=show_labels,
        show_fix=show_fix,
        show_order=show_order,
        show_saccades=show_saccades,
        show_heatmap=show_heatmap,
        color_by=color_by,
        heatmap_metric=heatmap_metric,
        x_field=x_field,
        y_field=y_field,
        marker_size_range=(size_min, size_max),
        order_font_size=order_font_size,
        order_font_color=order_font_color,
        show_colorbars=show_colorbars,
        fixation_color_range=fixation_color_range,
        heatmap_range=heatmap_range,
    )


def render_dictionary():
    with st.expander("Data dictionary / expected columns"):
        st.markdown(
            """
            The app auto-detects column names from csv tables using common conventions.
            - Words/IA: tries `participant_id`/`subject_id`, `trial_id`/`unique_paragraph_id`, `IA_ID`/`word_id`, optional `IA_LABEL`/`text`, paragraph ids, and bounding boxes via either `(x, y, width, height)` or `(IA_LEFT, IA_RIGHT, IA_TOP, IA_BOTTOM)`.
            - Fixations: tries `participant_id`/`subject_id`, `trial_id`/`unique_paragraph_id`, `CURRENT_FIX_DURATION`, `CURRENT_FIX_X`/`CURRENT_FIX_Y`, and optionally `CURRENT_FIX_START`, `IA_ID`, `pass_index`/`reread`, `saccade_type`, `eye`, `noise_flag`.
            Only fields present in your data are used for filters, coloring, and tooltips.
            """
        )


def main():
    st.title("Scanpath Visualization Workbench")
    st.caption(
        "Visualize eye-tracking-while-reading scanpaths with filterable overlays for words, fixations, saccades, and heatmaps."
    )

    data_choice = st.sidebar.radio(
        "Data source", ["Use bundled demo", "Upload csv tables"], index=0
    )

    if data_choice == "Upload csv tables":
        uploaded_words = st.sidebar.file_uploader("Words/IA csv", type=["csv"])
        uploaded_fixations = st.sidebar.file_uploader("Fixations csv", type=["csv"])
        if uploaded_words and uploaded_fixations:
            words_df = pd.read_csv(uploaded_words)
            fixations_df = pd.read_csv(uploaded_fixations)
        else:
            st.sidebar.info("Upload both files or switch to demo data.")
            words_df, fixations_df = load_sample_data()
    else:
        words_df, fixations_df = load_sample_data()

    word_schema = infer_word_schema(words_df)
    fix_schema = infer_fix_schema(fixations_df)
    if not word_schema or not fix_schema:
        st.stop()

    words_df = normalize_words(words_df, word_schema)
    fixations_df = normalize_fixations(fixations_df, fix_schema)

    filters = default_filters(words_df, fixations_df)
    words_filtered, fixations_filtered = filter_data(
        words_df,
        fixations_df,
        filters,
    )

    render_dictionary()

    if words_filtered.empty or fixations_filtered.empty:
        st.warning("No data after filtering. Try selecting more participants or trials.")
        return

    combos = (
        fixations_filtered[["participant_id", "trial_id", "paragraph_id"]]
        .drop_duplicates()
        .sort_values(["participant_id", "trial_id"])
    )

    combo_labels = [f"{row.participant_id} / {row.trial_id}" for row in combos.itertuples()]
    # Comparison view only needs participant and trial; drop paragraph_id so unpacking doesn't break.
    label_to_combo = dict(
        zip(
            combo_labels,
            combos[["participant_id", "trial_id"]].itertuples(index=False, name=None),
        )
    )

    default_canvas_w, default_canvas_h = compute_canvas_size(words_filtered, fixations_filtered)
    default_canvas_w = min(max(default_canvas_w, 100), 10000)
    default_canvas_h = min(max(default_canvas_h, 100), 10000)
    col_canvas_w, col_canvas_h, col_font = st.columns(3)
    with col_canvas_w:
        canvas_width = st.number_input(
            "Monitor width (px)",
            min_value=100,
            max_value=10000,
            value=default_canvas_w,
            step=10,
            help="Use the real monitor width in pixels to keep coordinates true to scale.",
        )
    with col_canvas_h:
        canvas_height = st.number_input(
            "Monitor height (px)",
            min_value=100,
            max_value=10000,
            value=default_canvas_h,
            step=10,
            help="Use the real monitor height in pixels to keep coordinates true to scale.",
        )
    with col_font:
        base_font_size = st.number_input(
            "Figure font size (px)",
            min_value=6,
            max_value=72,
            value=12,
            step=1,
            help="Controls label text size; uses a Lucida Sans monospace family.",
        )
    font_family = FONT_FAMILY

    tab_single, tab_compare, tab_metrics = st.tabs(
        ["Interactive builder", "Comparison", "Word-level metrics"]
    )

    with tab_single:
        st.subheader("Layered scanpath view")
        selection_mode = st.radio(
            "Selection mode",
            ["By participant", "By paragraph/text"],
            horizontal=True,
        )

        selected_participant = None
        selected_trial = None

        if selection_mode == "By participant":
            participants = sorted(combos["participant_id"].unique())
            if not participants:
                st.warning("No participants available after filtering.")
                st.stop()
            selected_participant = st.selectbox("Participant", options=participants)
            trials_for = combos[combos["participant_id"] == selected_participant]["trial_id"].unique()
            trials_for = sorted(trials_for)
            if trials_for:
                trial_idx = st.slider("Trial", min_value=1, max_value=len(trials_for), value=1, step=1)
                selected_trial = trials_for[trial_idx - 1]
        else:
            paragraphs = sorted(combos["paragraph_id"].unique())
            if not paragraphs:
                st.warning("No paragraph/text ids available after filtering.")
                st.stop()
            selected_paragraph = st.selectbox("Paragraph / text id", options=paragraphs)
            paragraph_combos = combos[combos["paragraph_id"] == selected_paragraph]
            if not paragraph_combos.empty:
                idx = st.slider(
                    "Trial within paragraph/text",
                    min_value=1,
                    max_value=len(paragraph_combos),
                    value=1,
                    step=1,
                    format="%d",
                )
                chosen = paragraph_combos.iloc[idx - 1]
                selected_participant = chosen.participant_id
                selected_trial = chosen.trial_id

        if selected_participant and selected_trial:
            trial_words = words_filtered[
                (words_filtered["participant_id"] == selected_participant)
                & (words_filtered["trial_id"] == selected_trial)
            ]
            trial_fixations = fixations_filtered[
                (fixations_filtered["participant_id"] == selected_participant)
                & (fixations_filtered["trial_id"] == selected_trial)
            ]

            st.markdown(
                f"Showing **{selected_participant} / {selected_trial}** "
                f"(paragraph/text: {trial_words['paragraph_id'].iloc[0] if 'paragraph_id' in trial_words.columns else selected_trial})"
            )

            viz_settings = sidebar_controls(trial_fixations, base_font_size)
            show_words = viz_settings["show_words"]
            show_labels = viz_settings["show_labels"]
            show_fix = viz_settings["show_fix"]
            show_order = viz_settings["show_order"]
            show_saccades = viz_settings["show_saccades"]
            show_heatmap = viz_settings["show_heatmap"]
            color_by = viz_settings["color_by"]
            heatmap_metric = viz_settings["heatmap_metric"]
            x_field = viz_settings["x_field"]
            y_field = viz_settings["y_field"]
            order_font_size = viz_settings["order_font_size"]
            order_font_color = viz_settings["order_font_color"]
            size_min, size_max = viz_settings["marker_size_range"]
            show_colorbars = viz_settings["show_colorbars"]
            fixation_color_range = viz_settings["fixation_color_range"]
            heatmap_range = viz_settings["heatmap_range"]

            fig = make_scanpath_figure(
                trial_words,
                trial_fixations,
                canvas_width=int(canvas_width),
                canvas_height=int(canvas_height),
                base_font_size=int(base_font_size),
                font_family=font_family,
                x_field=x_field,
                y_field=y_field,
                show_words=show_words,
                show_word_labels=show_labels,
                show_fixations=show_fix,
                show_order=show_order,
                show_saccades=show_saccades,
                show_heatmap=show_heatmap,
                color_by=color_by,
                heatmap_metric=heatmap_metric if heatmap_metric != "counts" else None,
                marker_size_range=(size_min, size_max),
                order_font_size=order_font_size,
                order_font_color=order_font_color,
                show_colorbars=show_colorbars,
                fixation_color_range=fixation_color_range,
                heatmap_range=heatmap_range,
            )
            st.plotly_chart(fig, use_container_width=False, config={"responsive": False})

            st.markdown("**Filtered fixations**")
            table_cols = [
                col
                for col in [
                    "fixation_id",
                    "order_in_trial",
                    "timestamp_ms",
                    "duration_ms",
                    "word_id",
                    "pass_index",
                    "saccade_type",
                    "eye",
                    "noise_flag",
                ]
                if col in trial_fixations.columns or col in ["order_in_trial", "timestamp_ms", "duration_ms"]
            ]
            st.dataframe(
                trial_fixations[table_cols],
                width="stretch",
                hide_index=True,
            )

            if st.button("Export all filtered trials as PNG (zip)"):
                if combos.empty:
                    st.warning("No trials to export.")
                else:
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w") as zf:
                        for combo in combos.itertuples(index=False):
                            combo_words = words_filtered[
                                (words_filtered["participant_id"] == combo.participant_id)
                                & (words_filtered["trial_id"] == combo.trial_id)
                            ]
                            combo_fix = fixations_filtered[
                                (fixations_filtered["participant_id"] == combo.participant_id)
                                & (fixations_filtered["trial_id"] == combo.trial_id)
                            ]
                            combo_fig = make_scanpath_figure(
                                combo_words,
                                combo_fix,
                                canvas_width=int(canvas_width),
                                canvas_height=int(canvas_height),
                                base_font_size=int(base_font_size),
                                font_family=font_family,
                                x_field=x_field,
                                y_field=y_field,
                                show_words=show_words,
                                show_word_labels=show_labels,
                                show_fixations=show_fix,
                                show_order=show_order,
                                show_saccades=show_saccades,
                                show_heatmap=show_heatmap,
                                color_by=color_by,
                                heatmap_metric=heatmap_metric if heatmap_metric != "counts" else None,
                                marker_size_range=(size_min, size_max),
                                order_font_size=order_font_size,
                                order_font_color=order_font_color,
                                show_colorbars=show_colorbars,
                                fixation_color_range=fixation_color_range,
                                heatmap_range=heatmap_range,
                            )
                            img_bytes = combo_fig.to_image(
                                format="png",
                                width=int(canvas_width),
                                height=int(canvas_height),
                            )
                            filename = f"{combo.participant_id}_{combo.trial_id}.png"
                            zf.writestr(filename, img_bytes)
                    buf.seek(0)
                    st.download_button(
                        "Download zip",
                        data=buf.getvalue(),
                        file_name="scanpaths.zip",
                        mime="application/zip",
                    )

    with tab_compare:
        st.subheader("Overlay two trials")
        if len(combo_labels) < 2:
            st.info("Select at least two trials in the filters to compare.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                label_a = st.selectbox("Primary trial", options=combo_labels, index=0)
            with col_b:
                label_b = st.selectbox("Trial to overlay", options=combo_labels, index=1)

            trial_a = label_to_combo[label_a]
            trial_b = label_to_combo[label_b]
            fig_compare = make_comparison_figure(
                words_filtered,
                fixations_filtered,
                trial_a,
                trial_b,
                canvas_width=int(canvas_width),
                canvas_height=int(canvas_height),
                font_family=font_family,
                base_font_size=int(base_font_size),
            )
            st.plotly_chart(fig_compare, use_container_width=False, config={"responsive": False})

    with tab_metrics:
        st.subheader("Word-level measures")
        metrics = compute_word_metrics(words_filtered, fixations_filtered)
        st.dataframe(
            metrics[
                [
                    "participant_id",
                    "trial_id",
                    "word_id",
                    "text",
                    "line_idx",
                    "n_fixations",
                    "total_duration_ms",
                    "first_pass_ms",
                    "skipped",
                ]
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Computed metrics: counts & durations per word, with skip detection and first-pass totals."
        )
        st.download_button(
            label="Download metrics as CSV",
            data=metrics.to_csv(index=False),
            file_name="word_metrics.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
