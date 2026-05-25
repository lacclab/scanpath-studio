"""Configurable bulk export of figures and tabular data for filtered trials.

This module powers the "Bulk export" button. Users pick which artifacts they
want per trial (PNG, SVG, JSON plot config, fixations CSV/Parquet, per-word
measures CSV/Parquet) plus an optional aggregated mega-table across all
selected trials. Everything is packaged into a single zip archive with a
clean folder structure:

    bulk_export_<timestamp>.zip
    ├─ per_trial/
    │  ├─ <participant>__<trial>/
    │  │  ├─ figure.png
    │  │  ├─ figure.svg
    │  │  ├─ plot_config.json
    │  │  ├─ fixations.csv (and/or .parquet)
    │  │  └─ measures.csv (and/or .parquet)
    │  ├─ ...
    └─ aggregate/
       ├─ all_fixations.csv (and/or .parquet)
       └─ all_measures.csv (and/or .parquet)
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

import pandas as pd

from .constants import CITATION
from .data import compute_word_metrics
from .plots import make_scanpath_figure


@dataclass
class ExportOptions:
    """User-chosen export artifacts. Default is the full bundle."""

    include_png: bool = True
    include_svg: bool = True
    include_plot_config: bool = True
    include_fixations: bool = True
    include_measures: bool = True
    include_mega_table: bool = True
    table_format: str = "csv"  # "csv" | "parquet" | "both"
    png_scale: int = 1

    def any_table(self) -> bool:
        return self.include_fixations or self.include_measures

    def table_formats(self) -> List[str]:
        if self.table_format == "both":
            return ["csv", "parquet"]
        return [self.table_format]


@dataclass
class ExportProgress:
    total_trials: int
    finished_trials: int = 0
    bytes_written: int = 0
    errors: List[str] = field(default_factory=list)


def _safe_id(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(text))


def _write_table(zf: zipfile.ZipFile, path: str, df: pd.DataFrame, fmt: str) -> int:
    if fmt == "parquet":
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        data = buf.getvalue()
    else:
        data = df.to_csv(index=False).encode("utf-8")
    zf.writestr(path, data)
    return len(data)


def _figure_bytes(fig, fmt: str, width: int, height: int, scale: int) -> bytes:
    return fig.to_image(format=fmt, width=int(width), height=int(height), scale=scale)


def _plot_config_dict(
    participant: str,
    trial: str,
    canvas_width: int,
    canvas_height: int,
    x_field: str,
    y_field: str,
    settings: dict,
) -> dict:
    return {
        "selection": {"participant_id": participant, "trial_id": trial},
        "canvas_px": {"width": int(canvas_width), "height": int(canvas_height)},
        "axes": {"x_field": x_field, "y_field": y_field},
        "layers": {
            "words": settings.get("show_words"),
            "word_labels": settings.get("show_word_labels"),
            "fixations": settings.get("show_fixations"),
            "order_labels": settings.get("show_order"),
            "saccades": settings.get("show_saccades"),
            "heatmap": settings.get("show_heatmap"),
            "raw_gaze": settings.get("show_raw_gaze"),
        },
        "coloring": {
            "color_by": settings.get("color_by"),
            "heatmap_metric": settings.get("heatmap_metric"),
            "fixation_colorscale": settings.get("fixation_colorscale"),
            "heatmap_colorscale": settings.get("heatmap_colorscale"),
        },
        "sizing": {
            "marker_size_range": list(settings.get("marker_size_range", [])),
            "order_font_size": settings.get("order_font_size"),
        },
    }


def render_export_options(st_module, key_prefix: str = "export") -> ExportOptions:
    """Render the checkbox UI and return a populated ExportOptions."""
    st = st_module
    with st.expander("Bulk export options", expanded=False):
        st.markdown(
            "Pick which artifacts to include for **each filtered trial**. "
            "Everything is bundled into a single zip you can download."
        )
        cols = st.columns(3)
        with cols[0]:
            st.caption("**Figures**")
            include_png = st.checkbox(
                "PNG (raster)", value=True, key=f"{key_prefix}_png"
            )
            include_svg = st.checkbox(
                "SVG (vector, for papers)", value=True, key=f"{key_prefix}_svg"
            )
            include_plot_config = st.checkbox(
                "Plot config JSON", value=True, key=f"{key_prefix}_cfg"
            )
        with cols[1]:
            st.caption("**Tabular data**")
            include_fixations = st.checkbox(
                "Per-trial fixations", value=True, key=f"{key_prefix}_fix"
            )
            include_measures = st.checkbox(
                "Per-trial word measures (FFD/FPRT/RPD/TFD/...)",
                value=True,
                key=f"{key_prefix}_mes",
            )
            include_mega_table = st.checkbox(
                "Aggregated mega-table across all trials",
                value=True,
                key=f"{key_prefix}_mega",
            )
        with cols[2]:
            st.caption("**Format**")
            table_format = st.radio(
                "Table format",
                options=["csv", "parquet", "both"],
                index=0,
                key=f"{key_prefix}_fmt",
                horizontal=False,
            )
            png_scale = st.number_input(
                "PNG scale",
                min_value=1,
                max_value=4,
                value=2,
                key=f"{key_prefix}_scale",
                help="2 = retina, 4 = poster",
            )
    return ExportOptions(
        include_png=include_png,
        include_svg=include_svg,
        include_plot_config=include_plot_config,
        include_fixations=include_fixations,
        include_measures=include_measures,
        include_mega_table=include_mega_table,
        table_format=table_format,
        png_scale=int(png_scale),
    )


def bulk_export(
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
    settings: dict,
    options: ExportOptions,
    progress_callback=None,
) -> tuple[bytes, ExportProgress]:
    """Build a zip archive of selected artifacts and return its bytes.

    progress_callback (if given) is invoked with an ExportProgress after every
    trial so the UI can update a progress bar.
    """
    progress = ExportProgress(total_trials=len(combos))
    buf = io.BytesIO()
    zf = zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED)

    mega_fixations: list[pd.DataFrame] = []
    mega_measures: list[pd.DataFrame] = []

    readme_lines = [
        "# Bulk export",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        f"Authors: {CITATION['authors']}",
        f"Tool: {CITATION['title']}",
        "",
        "## Layout",
        "- `per_trial/<participant>__<trial>/` holds artifacts for each trial.",
        "- `aggregate/` holds long-form tables across every trial in this run.",
        "",
        "## Data dictionary",
        "Canonical column names from the visualization tool:",
        "- participant_id, trial_id, paragraph_id, word_id",
        "- x, y, width, height (word bounding boxes in screen px)",
        "- x, y, duration_ms, timestamp_ms (fixations)",
        "- first_fixation_ms (FFD), first_pass_gaze_duration_ms (FPRT / gaze duration)",
        "- regression_path_duration_ms (RPD / go-past)",
        "- total_fixation_duration_ms (TFD / dwell), n_fixations",
        "- skip_flag, regression_in_flag, regression_out_flag",
        "",
        f"Demo corpus note: {CITATION['corpus_note']}",
    ]
    zf.writestr("README.md", "\n".join(readme_lines))

    for combo in combos.itertuples(index=False):
        participant = getattr(combo, "participant_id")
        trial = getattr(combo, "trial_id")
        slug = f"{_safe_id(participant)}__{_safe_id(trial)}"
        prefix = f"per_trial/{slug}/"

        trial_words = words[
            (words["participant_id"] == participant) & (words["trial_id"] == trial)
        ]
        trial_fix = fixations[
            (fixations["participant_id"] == participant)
            & (fixations["trial_id"] == trial)
        ]

        if trial_words.empty or trial_fix.empty:
            progress.finished_trials += 1
            progress.errors.append(f"{slug}: empty data, skipped")
            if progress_callback:
                progress_callback(progress)
            continue

        if options.include_png or options.include_svg:
            try:
                fig = make_scanpath_figure(
                    trial_words,
                    trial_fix,
                    canvas_width=int(canvas_width),
                    canvas_height=int(canvas_height),
                    base_font_size=int(base_font_size),
                    font_family=font_family,
                    x_field=x_field,
                    y_field=y_field,
                    show_words=settings.get("show_words", True),
                    show_word_labels=settings.get("show_word_labels", True),
                    show_fixations=settings.get("show_fixations", True),
                    show_order=settings.get("show_order", True),
                    show_saccades=settings.get("show_saccades", True),
                    show_heatmap=settings.get("show_heatmap", False),
                    color_by=settings.get("color_by", "duration_ms"),
                    heatmap_metric=settings.get("heatmap_metric"),
                    marker_size_range=tuple(settings.get("marker_size_range", (8, 24))),
                    order_font_size=int(settings.get("order_font_size", 10)),
                    order_font_color=settings.get("order_font_color", "#111111"),
                    show_colorbars=settings.get("show_colorbars", False),
                    fixation_color_range=settings.get("fixation_color_range"),
                    heatmap_range=settings.get("heatmap_range"),
                    fixation_colorscale=settings.get("fixation_colorscale", "Blues"),
                    heatmap_colorscale=settings.get("heatmap_colorscale", "Oranges"),
                )
                if options.include_png:
                    data = _figure_bytes(
                        fig, "png", canvas_width, canvas_height, options.png_scale
                    )
                    zf.writestr(f"{prefix}figure.png", data)
                    progress.bytes_written += len(data)
                if options.include_svg:
                    data = _figure_bytes(fig, "svg", canvas_width, canvas_height, 1)
                    zf.writestr(f"{prefix}figure.svg", data)
                    progress.bytes_written += len(data)
            except Exception as exc:
                progress.errors.append(f"{slug}: figure export failed ({exc})")

        if options.include_plot_config:
            cfg = _plot_config_dict(
                participant,
                trial,
                canvas_width,
                canvas_height,
                x_field,
                y_field,
                settings,
            )
            data = json.dumps(cfg, indent=2).encode("utf-8")
            zf.writestr(f"{prefix}plot_config.json", data)
            progress.bytes_written += len(data)

        per_trial_measures = (
            compute_word_metrics(trial_words, trial_fix)
            if options.include_measures or options.include_mega_table
            else None
        )

        for fmt in options.table_formats():
            if options.include_fixations:
                progress.bytes_written += _write_table(
                    zf, f"{prefix}fixations.{fmt}", trial_fix, fmt
                )
            if options.include_measures and per_trial_measures is not None:
                progress.bytes_written += _write_table(
                    zf, f"{prefix}measures.{fmt}", per_trial_measures, fmt
                )

        if options.include_mega_table:
            mega_fixations.append(trial_fix)
            if per_trial_measures is not None:
                mega_measures.append(per_trial_measures)

        progress.finished_trials += 1
        if progress_callback:
            progress_callback(progress)

    if options.include_mega_table and (mega_fixations or mega_measures):
        for fmt in options.table_formats():
            if mega_fixations:
                progress.bytes_written += _write_table(
                    zf,
                    f"aggregate/all_fixations.{fmt}",
                    pd.concat(mega_fixations, ignore_index=True),
                    fmt,
                )
            if mega_measures:
                progress.bytes_written += _write_table(
                    zf,
                    f"aggregate/all_measures.{fmt}",
                    pd.concat(mega_measures, ignore_index=True),
                    fmt,
                )

    zf.close()
    buf.seek(0)
    return buf.getvalue(), progress
