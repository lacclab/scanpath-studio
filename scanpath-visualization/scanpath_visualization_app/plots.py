from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .constants import FONT_FAMILY

COLORBAR_LEN_FRACTION = 0.33


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
    x_range = [0, canvas_width]
    y_range = [canvas_height, 0]
    x_min_data = x_max_data = y_min_data = y_max_data = None

    if spatial_axes:
        x_candidates = []
        y_candidates = []
        if not words.empty:
            x_candidates.extend([words["x"].min(), (words["x"] + words["width"]).max()])
            y_candidates.extend([words["y"].min(), (words["y"] + words["height"]).max()])
        if not fixations.empty:
            x_candidates.extend([fixations[x_field].min(), fixations[x_field].max()])
            y_candidates.extend([fixations[y_field].min(), fixations[y_field].max()])

        if x_candidates and y_candidates:
            x_min_data = float(np.nanmin(x_candidates))
            x_max_data = float(np.nanmax(x_candidates))
            y_min_data = float(np.nanmin(y_candidates))
            y_max_data = float(np.nanmax(y_candidates))

            x_span = max(x_max_data - x_min_data, 1.0)
            y_span = max(y_max_data - y_min_data, 1.0)
            pad_x = max(20.0, 0.05 * x_span)
            pad_y = max(20.0, 0.05 * y_span)
            x_range = [x_min_data - pad_x, x_max_data + pad_x]
            y_range = [y_max_data + pad_y, y_min_data - pad_y]

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
        x_min = x_min_data if x_min_data is not None else float(fixations[x_field].min())
        x_max = x_max_data if x_max_data is not None else float(fixations[x_field].max())
        y_min = y_min_data if y_min_data is not None else float(fixations[y_field].min())
        y_max = y_max_data if y_max_data is not None else float(fixations[y_field].max())
        x_span = max(x_max - x_min, 1.0)
        y_span = max(y_max - y_min, 1.0)
        if not words.empty:
            # Word-level heatmap: aggregate fixations per word
            word_values = []
            for _, word_row in words.iterrows():
                wx0, wy0 = word_row["x"], word_row["y"]
                wx1, wy1 = wx0 + word_row["width"], wy0 + word_row["height"]
                # Find fixations within this word's bounding box
                in_word = (
                    (fixations[x_field] >= wx0) & (fixations[x_field] <= wx1) &
                    (fixations[y_field] >= wy0) & (fixations[y_field] <= wy1)
                )
                if weights is not None:
                    val = float(weights[in_word].sum())
                else:
                    val = float(in_word.sum())
                word_values.append(val)

            words_with_vals = words.copy()
            words_with_vals["heatmap_val"] = word_values

            # Only show words with non-zero values
            words_nonzero = words_with_vals[words_with_vals["heatmap_val"] > 0]
            if not words_nonzero.empty:
                z_min = heatmap_range[0] if heatmap_range else float(words_nonzero["heatmap_val"].min())
                z_max = heatmap_range[1] if heatmap_range else float(words_nonzero["heatmap_val"].max())
                z_range = max(z_max - z_min, 1e-9)

                # Use shapes for word-level heatmap cells
                from plotly.colors import sample_colorscale
                heatmap_shapes = []
                for _, wr in words_nonzero.iterrows():
                    norm_val = (wr["heatmap_val"] - z_min) / z_range
                    norm_val = max(0.0, min(1.0, norm_val))
                    color = sample_colorscale("Blues", [norm_val])[0]
                    heatmap_shapes.append(
                        dict(
                            type="rect",
                            x0=wr["x"],
                            y0=wr["y"],
                            x1=wr["x"] + wr["width"],
                            y1=wr["y"] + wr["height"],
                            line=dict(width=0),
                            fillcolor=color,
                            opacity=0.5,
                            layer="below",
                        )
                    )
                existing_shapes = list(fig.layout.shapes) if fig.layout.shapes else []
                fig.update_layout(shapes=existing_shapes + heatmap_shapes)

                # Add invisible scatter for colorbar
                if show_colorbars:
                    fig.add_trace(
                        go.Scatter(
                            x=[None],
                            y=[None],
                            mode="markers",
                            marker=dict(
                                colorscale="Blues",
                                showscale=True,
                                cmin=z_min,
                                cmax=z_max,
                                colorbar=dict(
                                    title="Fixation count" if weights is None else "Duration (ms)",
                                    x=1.02,
                                    lenmode="fraction",
                                    len=COLORBAR_LEN_FRACTION,
                                    y=0.5,
                                    yanchor="middle",
                                ),
                            ),
                            showlegend=False,
                            hoverinfo="skip",
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
                        lenmode="fraction",
                        len=COLORBAR_LEN_FRACTION,
                        y=0.5,
                        yanchor="middle",
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
                        lenmode="fraction",
                        len=COLORBAR_LEN_FRACTION,
                        y=0.5,
                        yanchor="middle",
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
                    "Fixation #%{customdata[0]}<br>"
                    "Duration %{customdata[1]} ms<br>"
                    "Word #%{customdata[2]}<br>"
                    "Pass #%{customdata[3]}<br>"
                ),
                customdata=np.stack(
                    [
                        ordered["order_in_trial"],
                        ordered["duration_ms"],
                        ordered.get("word_id", pd.Series([np.nan] * len(ordered))),
                        ordered.get("pass_index", pd.Series([np.nan] * len(ordered))),
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
        xaxis_cfg.update(range=x_range, constrain="domain")
        yaxis_cfg.update(range=y_range, constrain="domain", scaleanchor="x", scaleratio=1)

    shapes = list(fig.layout.shapes) if fig.layout.shapes else []
    if spatial_axes:
        shapes.append(
            dict(
                type="rect",
                x0=x_range[0],
                y0=y_range[1],
                x1=x_range[1],
                y1=y_range[0],
                line=dict(color="#000000", width=1),
                fillcolor="rgba(0,0,0,0)",
            )
        )

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
        shapes=shapes,
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
    x_candidates = []
    y_candidates = []
    for idx, trial in enumerate([trial_a, trial_b]):
        participant, trial_id = trial
        trial_words = words[
            (words["participant_id"] == participant) & (words["trial_id"] == trial_id)
        ]
        trial_fix = fixations[
            (fixations["participant_id"] == participant) & (fixations["trial_id"] == trial_id)
        ].sort_values("timestamp_ms")
        if not trial_words.empty:
            x_candidates.extend([trial_words["x"].min(), (trial_words["x"] + trial_words["width"]).max()])
            y_candidates.extend([trial_words["y"].min(), (trial_words["y"] + trial_words["height"]).max()])
        if not trial_fix.empty:
            x_candidates.extend([trial_fix["x"].min(), trial_fix["x"].max()])
            y_candidates.extend([trial_fix["y"].min(), trial_fix["y"].max()])
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

    x_range = [0, canvas_width]
    y_range = [canvas_height, 0]
    if x_candidates and y_candidates:
        x_min = float(np.nanmin(x_candidates))
        x_max = float(np.nanmax(x_candidates))
        y_min = float(np.nanmin(y_candidates))
        y_max = float(np.nanmax(y_candidates))

        x_span = max(x_max - x_min, 1.0)
        y_span = max(y_max - y_min, 1.0)
        pad_x = max(20.0, 0.05 * x_span)
        pad_y = max(20.0, 0.05 * y_span)
        x_range = [x_min - pad_x, x_max + pad_x]
        y_range = [y_max + pad_y, y_min - pad_y]

    shapes = list(fig.layout.shapes) if fig.layout.shapes else []
    shapes.append(
        dict(
            type="rect",
            x0=x_range[0],
            y0=y_range[1],
            x1=x_range[1],
            y1=y_range[0],
            line=dict(color="#000000", width=1),
            fillcolor="rgba(0,0,0,0)",
        )
    )

    fig.update_layout(
        height=canvas_height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False, title=None, range=x_range, constrain="domain"),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, title=None, range=y_range, constrain="domain", scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        title="Overlay comparison",
        font=font_settings,
        shapes=shapes,
    )
    return fig
