from __future__ import annotations

import importlib.resources as resources
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
    cols = set(words.columns)
    participant = pick_column(words, ["participant_id", "subject_id", "participant", "recording_session_label"])
    trial = pick_column(
        words,
        ["trial_id", "paragraph_id", "unique_paragraph_id", "trial", "trial_index", "TRIAL_INDEX"],
    )
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
    df["word_id"] = pd.to_numeric(words[schema["word_id"]], errors="coerce")
    if schema.get("text"):
        df["text"] = words[schema["text"]].astype(str)
    else:
        df["text"] = df["word_id"].apply(lambda v: f"w{int(v)}" if pd.notna(v) else "")
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
    participants = filters.get("participants", [])
    trials = filters.get("trials", [])
    word_mask = words["participant_id"].isin(participants) & words["trial_id"].isin(trials)
    words_filtered = words[word_mask]

    fix_mask = fixations["participant_id"].isin(participants) & fixations["trial_id"].isin(trials)
    if "pass_indices" in filters and "pass_index" in fixations.columns:
        fix_mask &= fixations["pass_index"].isin(filters["pass_indices"])
    if "saccade_types" in filters and "saccade_type" in fixations.columns:
        fix_mask &= fixations["saccade_type"].isin(filters["saccade_types"])
    if "eyes" in filters and "eye" in fixations.columns:
        fix_mask &= fixations["eye"].isin(filters["eyes"])
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


def make_scanpath_figure(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    show_words: bool,
    show_word_labels: bool,
    show_fixations: bool,
    show_order: bool,
    show_saccades: bool,
    show_heatmap: bool,
    color_by: str,
    heatmap_metric: Optional[str],
) -> go.Figure:
    fig = go.Figure()
    if show_words and not words.empty:
        fig.update_layout(shapes=build_word_boxes(words))
        if show_word_labels:
            fig.add_trace(
                go.Scatter(
                    x=words["x"] + words["width"] / 2,
                    y=words["y"] + words["height"] / 2,
                    text=words["text"],
                    mode="text",
                    showlegend=False,
                    textfont=dict(color="#343a40", size=12),
                    hovertemplate=(
                        "Word %{text}<br>Word ID %{customdata[0]}<br>Line %{customdata[1]}"
                        "<extra></extra>"
                    ),
                    customdata=words[["word_id", "line_idx"]],
                )
            )

    if show_heatmap and not fixations.empty:
        weights = None
        if heatmap_metric == "duration_ms":
            weights = fixations["duration_ms"]
        histfunc = "sum" if weights is not None else "count"
        fig.add_trace(
            go.Histogram2d(
                x=fixations["x"],
                y=fixations["y"],
                nbinsx=25,
                nbinsy=25,
                colorscale="YlOrRd",
                opacity=0.35,
                showscale=True,
                colorbar=dict(
                    title="Fixation density" if weights is None else "Duration (ms)"
                ),
                histfunc=histfunc,
                z=weights,
            )
        )

    if show_saccades and len(fixations) > 1:
        ordered = fixations.sort_values("timestamp_ms")
        for (_, row_a), (_, row_b) in zip(ordered.iloc[:-1].iterrows(), ordered.iloc[1:].iterrows()):
            fig.add_trace(
                go.Scatter(
                    x=[row_a["x"], row_b["x"]],
                    y=[row_a["y"], row_b["y"]],
                    mode="lines",
                    line=dict(color="#6f42c1", width=2),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    if show_fixations and not fixations.empty:
        ordered = fixations.sort_values("timestamp_ms")
        color_data = ordered[color_by] if color_by in ordered.columns else None
        fig.add_trace(
            go.Scatter(
                x=ordered["x"],
                y=ordered["y"],
                mode="markers+text" if show_order else "markers",
                marker=dict(
                    size=8 + ordered["duration_ms"].fillna(0) * 0.05,
                    color=color_data,
                    colorscale="Viridis" if color_data is not None else None,
                    showscale=color_data is not None,
                    colorbar=dict(title=color_by.replace("_", " ").title()) if color_data is not None else None,
                    line=dict(color="#111", width=0.5),
                ),
                text=ordered["order_in_trial"] if show_order else None,
                textposition="top center",
                hovertemplate=(
                    "Fixation %{customdata[0]}<br>"
                    "Order %{customdata[1]}<br>"
                    "Time %{customdata[2]} ms<br>"
                    "Duration %{customdata[3]} ms<br>"
                    "Word %{customdata[4]}<br>"
                    "Pass %{customdata[5]}<br>"
                    "Saccade %{customdata[6]}<br>"
                    "Eye %{customdata[7]}<extra></extra>"
                ),
                customdata=np.stack(
                    [
                        ordered.get("fixation_id", ordered.index),
                        ordered["order_in_trial"],
                        ordered["timestamp_ms"],
                        ordered["duration_ms"],
                        ordered.get("word_id", pd.Series([np.nan] * len(ordered))),
                        ordered.get("pass_index", pd.Series([np.nan] * len(ordered))),
                        ordered.get("saccade_type", pd.Series(["?"] * len(ordered))),
                        ordered.get("eye", pd.Series(["?"] * len(ordered))),
                    ],
                    axis=1,
                ),
                name="Fixations",
            )
        )

    fig.update_layout(
        height=650,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(title="X (px)", showgrid=True),
        yaxis=dict(title="Y (px)", autorange="reversed", showgrid=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
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
) -> go.Figure:
    fig = go.Figure()
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
        height=650,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(title="X (px)", showgrid=True),
        yaxis=dict(title="Y (px)", autorange="reversed", showgrid=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        title="Overlay comparison",
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


def layout_sidebar(words: pd.DataFrame, fixations: pd.DataFrame) -> Dict:
    st.sidebar.header("Data & Filters")
    participants = sorted(words["participant_id"].unique())
    selected_participants = st.sidebar.multiselect(
        "Participants",
        options=participants,
        default=participants,
    )

    trials = sorted(
        words[words["participant_id"].isin(selected_participants)]["trial_id"].unique()
    )
    selected_trials = st.sidebar.multiselect("Trials", options=trials, default=trials)

    filters = dict(
        participants=selected_participants or participants,
        trials=selected_trials or trials,
    )

    if "pass_index" in fixations.columns:
        pass_indices = sorted(fixations["pass_index"].dropna().unique())
        selected_passes = st.sidebar.multiselect(
            "N-pass (pass_index)",
            options=pass_indices,
            default=pass_indices,
        )
        filters["pass_indices"] = selected_passes or pass_indices

    if "saccade_type" in fixations.columns:
        saccade_types = sorted(fixations["saccade_type"].dropna().astype(str).unique())
        selected_saccades = st.sidebar.multiselect(
            "Saccade types",
            options=saccade_types,
            default=saccade_types,
        )
        filters["saccade_types"] = selected_saccades or saccade_types

    if "eye" in fixations.columns:
        eyes = sorted(fixations["eye"].dropna().astype(str).unique())
        selected_eyes = st.sidebar.multiselect("Eyes", options=eyes, default=eyes)
        filters["eyes"] = selected_eyes or eyes

    if "noise_flag" in fixations.columns:
        filters["include_noise"] = st.sidebar.checkbox(
            "Include samples flagged as noise", value=False
        )
    else:
        filters["include_noise"] = True

    return filters


def render_dictionary():
    with st.expander("Data dictionary / expected columns"):
        st.markdown(
            """
            The app auto-detects column names from csv files using common conventions.
            - Words/IA: tries `participant_id`/`subject_id`, `trial_id`/`unique_paragraph_id`, `IA_ID`/`word_id`, `IA_LABEL`/`text`, and bounding boxes via either `(x, y, width, height)` or `(IA_LEFT, IA_RIGHT, IA_TOP, IA_BOTTOM)`.
            - Fixations: tries `participant_id`/`subject_id`, `trial_id`/`unique_paragraph_id`, `CURRENT_FIX_DURATION`, `CURRENT_FIX_X`/`CURRENT_FIX_Y`, and optionally `CURRENT_FIX_START`, `IA_ID`, `pass_index`/`reread`, `saccade_type`, `eye`, `noise_flag`.
            Only fields present in your data are used for filters, coloring, and tooltips.
            """
        )


def main():
    st.title("Scanpath Visualization Workbench")
    st.caption(
        "Layered, filterable scanpath visualizations inspired by the 14/4 brainstorming "
        "session: words + fixations + saccades + heatmaps, plus aggregation and comparison."
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

    filters = layout_sidebar(words_df, fixations_df)
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
        fixations_filtered[["participant_id", "trial_id"]]
        .drop_duplicates()
        .sort_values(["participant_id", "trial_id"])
    )
    combo_labels = [f"{row.participant_id} / {row.trial_id}" for row in combos.itertuples()]
    label_to_combo = dict(zip(combo_labels, combos.itertuples(index=False)))

    tab_single, tab_compare, tab_metrics = st.tabs(
        ["Interactive builder", "Comparison", "Word-level metrics"]
    )

    with tab_single:
        st.subheader("Layered scanpath view")
        selected_label = st.selectbox(
            "Select participant & trial",
            options=combo_labels,
            index=0 if combo_labels else None,
        )
        if selected_label:
            participant, trial_id = label_to_combo[selected_label]
            trial_words = words_filtered[
                (words_filtered["participant_id"] == participant)
                & (words_filtered["trial_id"] == trial_id)
            ]
            trial_fixations = fixations_filtered[
                (fixations_filtered["participant_id"] == participant)
                & (fixations_filtered["trial_id"] == trial_id)
            ]

            col_opts1, col_opts2, col_opts3 = st.columns(3)
            with col_opts1:
                show_words = st.checkbox("Show word boxes", value=True)
                show_labels = st.checkbox("Show word labels", value=True)
                show_fix = st.checkbox("Show fixations", value=True)
            with col_opts2:
                show_order = st.checkbox("Number fixation order", value=True)
                show_saccades = st.checkbox("Show saccades", value=True)
                color_fields = [
                    field
                    for field in ["duration_ms", "pass_index", "eye", "saccade_type", "word_id", "timestamp_ms"]
                    if field in trial_fixations.columns
                ]
                if not color_fields:
                    color_fields = ["duration_ms"]
                color_by = st.selectbox(
                    "Color fixations by",
                    options=color_fields,
                    index=color_fields.index("duration_ms") if "duration_ms" in color_fields else 0,
                )
            with col_opts3:
                show_heatmap = st.checkbox("Add density heatmap", value=True)
                heatmap_metric = st.selectbox(
                    "Heatmap metric",
                    options=["counts", "duration_ms"],
                    help="Heatmap can be raw counts or weighted by fixation duration.",
                )

            fig = make_scanpath_figure(
                trial_words,
                trial_fixations,
                show_words=show_words,
                show_word_labels=show_labels,
                show_fixations=show_fix,
                show_order=show_order,
                show_saccades=show_saccades,
                show_heatmap=show_heatmap,
                color_by=color_by,
                heatmap_metric=heatmap_metric if heatmap_metric != "counts" else None,
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("**Temporal trace (start time vs duration)**")
            st.plotly_chart(make_timeline_chart(trial_fixations), use_container_width=True)

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
                use_container_width=True,
                hide_index=True,
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
                words_filtered, fixations_filtered, trial_a, trial_b
            )
            st.plotly_chart(fig_compare, use_container_width=True)

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
            use_container_width=True,
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
