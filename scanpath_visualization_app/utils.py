"""Utility functions for trial selection, statistics, and export."""

from __future__ import annotations

import io
import zipfile
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd
import streamlit as st

from scanpath_visualization_app.plots import make_scanpath_figure


# -----------------------------------------------------------------------------
# Trial combo building
# -----------------------------------------------------------------------------


def build_combo_options(
    fixations: pd.DataFrame,
) -> Tuple[pd.DataFrame, list[str], Dict[str, Tuple[str, str]]]:
    """Build participant/trial/paragraph combinations for selection UI.

    Returns:
        Tuple of (combos DataFrame, label list, label-to-combo mapping).
    """
    paragraph_col = (
        "unique_paragraph_id"
        if "unique_paragraph_id" in fixations.columns
        else "paragraph_id"
    )
    trial_col = (
        "unique_trial_id" if "unique_trial_id" in fixations.columns else "trial_id"
    )
    combo_cols = ["participant_id", trial_col, paragraph_col]
    for col in ["unique_trial_id", "unique_paragraph_id", "TRIAL_INDEX", "trial_index"]:
        if col in fixations.columns and col not in combo_cols:
            combo_cols.append(col)

    combos = (
        fixations[combo_cols]
        .drop_duplicates()
        .rename(columns={trial_col: "trial_id", paragraph_col: "paragraph_id"})
    )
    if trial_col == "unique_trial_id" and "unique_trial_id" not in combos.columns:
        combos["unique_trial_id"] = combos["trial_id"]
    if (
        paragraph_col == "unique_paragraph_id"
        and "unique_paragraph_id" not in combos.columns
    ):
        combos["unique_paragraph_id"] = combos["paragraph_id"]
    sort_cols = ["participant_id"]
    if "TRIAL_INDEX" in combos.columns:
        sort_cols.append("TRIAL_INDEX")
    elif "trial_index" in combos.columns:
        sort_cols.append("trial_index")
    sort_cols.append("trial_id")
    combos = combos.sort_values(sort_cols)

    combo_labels = [
        f"{row.participant_id} / {row.trial_id} · {row.paragraph_id}"
        for row in combos.itertuples()
    ]
    label_to_combo = dict(
        zip(
            combo_labels,
            combos[["participant_id", "trial_id"]].itertuples(index=False, name=None),
        )
    )
    return combos, combo_labels, label_to_combo


# -----------------------------------------------------------------------------
# Trial selection UI
# -----------------------------------------------------------------------------


def _select_trial_none_mode(
    combos: pd.DataFrame, trial_field: str, paragraph_field: str, key_prefix: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Handle trial selection when mode is 'None' (direct trial selection)."""
    available_trials = combos.drop_duplicates(subset=[trial_field])
    trial_options = sorted(
        available_trials[trial_field].dropna().astype(str).unique()
    )
    if not trial_options:
        st.warning("No trials available after filtering.")
        st.stop()

    # Session state for navigation
    state_key = f"{key_prefix}_trial_index" if key_prefix else "trial_index"
    if state_key not in st.session_state:
        st.session_state[state_key] = 0

    current_idx = st.session_state[state_key]
    current_idx = max(0, min(current_idx, len(trial_options) - 1))
    st.session_state[state_key] = current_idx

    # Navigation buttons
    nav_col1, nav_col2, select_col = st.columns([1, 1, 4])
    with nav_col1:
        if st.button(
            "← Prev",
            key=f"{key_prefix}_prev_btn" if key_prefix else "prev_btn",
            disabled=current_idx <= 0,
            width="stretch",
        ):
            st.session_state[state_key] = current_idx - 1
            st.rerun()
    with nav_col2:
        if st.button(
            "Next →",
            key=f"{key_prefix}_next_btn" if key_prefix else "next_btn",
            disabled=current_idx >= len(trial_options) - 1,
            width="stretch",
        ):
            st.session_state[state_key] = current_idx + 1
            st.rerun()
    with select_col:
        selected_trial_label = st.selectbox(
            "Unique trial id",
            options=trial_options,
            index=current_idx,
            key=f"{key_prefix}_trial_id" if key_prefix else None,
        )
        if selected_trial_label:
            new_idx = trial_options.index(selected_trial_label)
            if new_idx != current_idx:
                st.session_state[state_key] = new_idx

    if not selected_trial_label:
        return None, None, None

    chosen = available_trials[
        available_trials[trial_field].astype(str) == selected_trial_label
    ].iloc[0]
    selected_text = (
        str(chosen[paragraph_field]) if paragraph_field in chosen.index else None
    )
    return chosen["participant_id"], chosen["trial_id"], selected_text


def _select_trial_text_mode(
    combos: pd.DataFrame, paragraph_field: str, key_prefix: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Handle trial selection when mode is 'Text' (select by text first)."""
    paragraph_options = sorted(combos[paragraph_field].dropna().astype(str).unique())
    if not paragraph_options:
        st.warning("No text ids available after filtering.")
        st.stop()

    selected_paragraph = st.selectbox(
        "Text id",
        options=paragraph_options,
        key=f"{key_prefix}_text_id" if key_prefix else None,
    )
    if not selected_paragraph:
        st.warning("No text selected after filtering.")
        st.stop()

    paragraph_combos = combos[
        combos[paragraph_field].astype(str) == str(selected_paragraph)
    ]
    participant_options = sorted(paragraph_combos["participant_id"].dropna().unique())
    if not participant_options:
        st.warning("No participants available for this text.")
        st.stop()

    selected_participant = st.selectbox(
        "Participant",
        options=participant_options,
        key=f"{key_prefix}_participant_text" if key_prefix else None,
    )

    # Handle multiple readings
    candidate_trials = (
        paragraph_combos[paragraph_combos["participant_id"] == selected_participant]
        .drop_duplicates(subset=["trial_id"])
        .sort_values("trial_id")
    )
    if candidate_trials.empty:
        return None, None, selected_paragraph

    if len(candidate_trials) > 1:
        trial_options = candidate_trials["trial_id"].tolist()
        selected_trial = st.selectbox(
            "Reading (multiple trials available)",
            options=trial_options,
            key=f"{key_prefix}_reading_text" if key_prefix else None,
            help="This participant read this text multiple times.",
        )
    else:
        selected_trial = candidate_trials.iloc[0]["trial_id"]

    return selected_participant, selected_trial, selected_paragraph


def _select_trial_participant_mode(
    combos: pd.DataFrame,
    paragraph_field: str,
    trial_index_field: Optional[str],
    key_prefix: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Handle trial selection when mode is 'Participant' (select participant first)."""
    participants = sorted(combos["participant_id"].dropna().unique())
    if not participants:
        st.warning("No participants available after filtering.")
        st.stop()

    selected_participant = st.selectbox(
        "Participant",
        options=participants,
        key=f"{key_prefix}_participant" if key_prefix else None,
    )

    participant_trials = combos[combos["participant_id"] == selected_participant]
    if participant_trials.empty:
        st.warning("No trials available for this participant.")
        return None, None, None

    # Determine slider field
    use_trial_index = (
        trial_index_field and participant_trials[trial_index_field].notna().any()
    )
    if use_trial_index:
        slider_options = sorted(
            participant_trials[trial_index_field].dropna().unique().tolist()
        )
        slider_label = "Trial index"
        slider_field = trial_index_field
    else:
        slider_options = sorted(
            participant_trials[paragraph_field].dropna().astype(str).unique().tolist()
        )
        slider_label = "Text id"
        slider_field = paragraph_field

    if not slider_options:
        return None, None, None

    slider_value = st.select_slider(
        slider_label,
        options=slider_options,
        key=f"{key_prefix}_slider" if key_prefix else None,
    )
    if slider_value is None:
        return None, None, None

    if slider_field == paragraph_field:
        trial_candidates = participant_trials[
            participant_trials[slider_field].astype(str) == str(slider_value)
        ]
        selected_text = str(slider_value)
    else:
        trial_candidates = participant_trials[
            participant_trials[slider_field] == slider_value
        ]
        selected_text = (
            str(trial_candidates.iloc[0][paragraph_field])
            if not trial_candidates.empty and paragraph_field in trial_candidates.columns
            else None
        )

    trial_candidates = trial_candidates.drop_duplicates(subset=["trial_id"]).sort_values(
        "trial_id"
    )
    if trial_candidates.empty:
        return None, None, selected_text

    if len(trial_candidates) > 1:
        trial_options = trial_candidates["trial_id"].tolist()
        selected_trial = st.selectbox(
            "Reading (multiple trials available)",
            options=trial_options,
            key=f"{key_prefix}_reading_participant" if key_prefix else None,
            help="This participant read this text multiple times.",
        )
    else:
        selected_trial = trial_candidates.iloc[0]["trial_id"]

    return selected_participant, selected_trial, selected_text


def select_trial(
    combos: pd.DataFrame, key_prefix: str = ""
) -> Tuple[Optional[str], Optional[str], str, Optional[str]]:
    """Select a trial using a three-mode UI (None/Text/Participant).

    Returns:
        Tuple of (participant_id, trial_id, selection_mode, selected_text).
    """
    if combos.empty:
        st.warning("No trials available after filtering.")
        st.stop()

    selection_mode = st.radio(
        label="Select trials by",
        options=["None", "Text", "Participant"],
        horizontal=True,
        key=f"{key_prefix}_select_trial_mode" if key_prefix else None,
    )

    trial_field = (
        "unique_trial_id" if "unique_trial_id" in combos.columns else "trial_id"
    )
    paragraph_field = (
        "unique_paragraph_id"
        if "unique_paragraph_id" in combos.columns
        else "paragraph_id"
    )
    trial_index_field = next(
        (c for c in ["TRIAL_INDEX", "trial_index"] if c in combos.columns), None
    )

    if selection_mode == "None":
        participant, trial, text = _select_trial_none_mode(
            combos, trial_field, paragraph_field, key_prefix
        )
    elif selection_mode == "Text":
        participant, trial, text = _select_trial_text_mode(
            combos, paragraph_field, key_prefix
        )
    else:
        participant, trial, text = _select_trial_participant_mode(
            combos, paragraph_field, trial_index_field, key_prefix
        )

    return participant, trial, selection_mode, text


# -----------------------------------------------------------------------------
# Statistics and metadata
# -----------------------------------------------------------------------------


def compute_trial_stats(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame
) -> Dict[str, float]:
    """Compute summary statistics for a single trial."""
    total_time = None
    if "trial_dwell_time_ms" in trial_words.columns:
        dwell_values = (
            pd.to_numeric(trial_words["trial_dwell_time_ms"], errors="coerce")
            .dropna()
            .unique()
        )
        if len(dwell_values):
            total_time = float(dwell_values[0])
    if total_time is None:
        total_time = (
            float(trial_fixations["duration_ms"].sum())
            if not trial_fixations.empty
            else 0.0
        )
    return dict(
        total_reading_time_ms=total_time,
        total_reading_time_s=total_time / 1000.0,
        word_count=int(len(trial_words)),
        fixation_count=int(len(trial_fixations)),
    )


def gather_trial_metadata(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame, fields: Iterable[str]
) -> pd.DataFrame:
    """Gather metadata for selected fields from words and fixations."""
    rows = []
    for field in fields:
        if field in trial_words.columns:
            series = pd.Series(trial_words[field])
        elif field in trial_fixations.columns:
            series = pd.Series(trial_fixations[field])
        else:
            continue

        cleaned = series.dropna()
        if cleaned.empty:
            value = "—"
        else:
            unique_values = cleaned.unique()
            if len(unique_values) == 1:
                value = unique_values[0]
            else:
                numeric_series = pd.to_numeric(cleaned, errors="coerce")
                numeric_values = numeric_series.dropna()
                is_numeric = (
                    not pd.api.types.is_bool_dtype(cleaned)
                    and (
                        pd.api.types.is_numeric_dtype(cleaned)
                        or len(numeric_values) == len(cleaned)
                    )
                    and not numeric_values.empty
                )
                if is_numeric:
                    value = f"mean={numeric_values.mean():.2f}, std={numeric_values.std():.2f}"
                else:
                    modes = cleaned.mode(dropna=True)
                    mode_value = modes.iloc[0] if not modes.empty else "—"
                    value = f"{mode_value} (mode, {len(unique_values)} unique)"
        rows.append({"Field": field, "Value": value})

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Value"] = df["Value"].astype(str)
    return df


def safe_summary(series: pd.Series) -> dict:
    """Compute summary statistics for a series, handling empty data."""
    if series.empty:
        nan_val = float("nan")
        return dict(mean=nan_val, std=nan_val, min=nan_val, max=nan_val, median=nan_val)
    return dict(
        mean=float(series.mean()),
        std=float(series.std(ddof=0)),
        min=float(series.min()),
        max=float(series.max()),
        median=float(series.median()),
    )


# -----------------------------------------------------------------------------
# Comparison helpers
# -----------------------------------------------------------------------------


def friendly_trial_label(
    participant_id: str,
    trial_id: str,
    text_id: Optional[str],
    existing_labels: set[str],
    prefix: str = "",
) -> str:
    """Create a short, de-duplicated label for comparison dropdowns/legends."""
    trial_str = str(trial_id) if trial_id is not None else ""
    text_str = str(text_id) if text_id is not None else ""
    text_str = text_str.strip()
    trial_contains_text = text_str and text_str.lower() in trial_str.lower()

    if text_str:
        base = f"{text_str} · {participant_id}"
        if not trial_contains_text:
            base = f"{base} (trial {trial_str})" if trial_str else base
    else:
        base = f"{trial_str} · {participant_id}" if trial_str else participant_id

    label = f"{prefix}{base}"
    if label in existing_labels:
        label = f"{prefix}{base} [{trial_str or 'trial'}]"
    existing_labels.add(label)
    return label


def build_comparison_options(
    combos: pd.DataFrame,
    selection_mode: str,
    primary_participant: str,
    primary_trial: str,
    primary_text: Optional[str],
) -> list[Tuple[str, str, str]]:
    """Build prioritized list of comparison trial options.

    Returns list of (participant_id, trial_id, label) tuples, prioritized by:
    - Same text trials first (marked with ★)
    - Other trials after
    """
    paragraph_field = (
        "unique_paragraph_id"
        if "unique_paragraph_id" in combos.columns
        else "paragraph_id"
    )

    options: list[Tuple[str, str, str]] = []
    added = set()
    used_labels: set[str] = set()

    def add_options(df: pd.DataFrame, prefix: str = ""):
        for row in df.itertuples():
            key = (row.participant_id, row.trial_id)
            if key not in added and key != (primary_participant, primary_trial):
                text_id = getattr(row, paragraph_field, "")
                label = friendly_trial_label(
                    row.participant_id,
                    row.trial_id,
                    text_id,
                    used_labels,
                    prefix=prefix,
                )
                options.append((row.participant_id, row.trial_id, label))
                added.add(key)

    if primary_text:
        # Same text first
        same_text_all = combos[
            (combos[paragraph_field].astype(str) == str(primary_text))
        ].drop_duplicates(subset=["participant_id", "trial_id"])
        add_options(same_text_all, "★ ")

        # Then other texts
        other_texts = combos[
            (combos[paragraph_field].astype(str) != str(primary_text))
        ].drop_duplicates(subset=["participant_id", "trial_id"])
        add_options(other_texts)
    else:
        all_others = combos.drop_duplicates(subset=["participant_id", "trial_id"])
        add_options(all_others)

    return options


# -----------------------------------------------------------------------------
# Export
# -----------------------------------------------------------------------------


def export_filtered_trials(
    combos: pd.DataFrame,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    x_field: str,
    y_field: str,
    settings: Dict,
) -> None:
    """Export all filtered trials as PNG images in a zip archive."""
    if combos.empty:
        st.warning("No trials to export.")
        return

    total_trials = len(combos)
    progress = st.progress(0, text="Preparing exports...")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for idx, combo in enumerate(combos.itertuples(index=False), start=1):
            combo_words = words[
                (words["participant_id"] == combo.participant_id)
                & (words["trial_id"] == combo.trial_id)
            ]
            combo_fix = fixations[
                (fixations["participant_id"] == combo.participant_id)
                & (fixations["trial_id"] == combo.trial_id)
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
                show_words=settings["show_words"],
                show_word_labels=settings["show_word_labels"],
                show_fixations=settings["show_fixations"],
                show_order=settings["show_order"],
                show_saccades=settings["show_saccades"],
                show_heatmap=settings["show_heatmap"],
                color_by=settings["color_by"],
                heatmap_metric=settings["heatmap_metric"],
                marker_size_range=settings["marker_size_range"],
                order_font_size=settings["order_font_size"],
                order_font_color=settings["order_font_color"],
                show_colorbars=settings["show_colorbars"],
                fixation_color_range=settings["fixation_color_range"],
                heatmap_range=settings["heatmap_range"],
                fixation_colorscale=settings.get("fixation_colorscale", "Blues"),
                heatmap_colorscale=settings.get("heatmap_colorscale", "Oranges"),
            )
            img_bytes = combo_fig.to_image(
                format="png",
                width=int(canvas_width),
                height=int(canvas_height),
            )
            filename = f"{combo.participant_id}_{combo.trial_id}.png"
            zf.writestr(filename, img_bytes)
            progress.progress(
                int(idx / total_trials * 100),
                text=f"Exporting trial {idx} of {total_trials}...",
            )

    progress.progress(100, text="Export ready! Click below to download.")
    buf.seek(0)
    st.download_button(
        "Download zip",
        data=buf.getvalue(),
        file_name="scanpaths.zip",
        mime="application/zip",
    )
