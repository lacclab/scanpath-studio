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
    │  │  ├─ layers/                 (VIZ-5, optional)
    │  │  │  ├─ word_boxes.svg
    │  │  │  ├─ fixations.svg
    │  │  │  ├─ saccades.svg
    │  │  │  └─ …                    (one per visible layer)
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
import re
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import List, Optional

import pandas as pd

from .aggregation import reader_summary_table, trial_summary_table
from .constants import (
    CITATION,
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_LINE_SPACING,
    DEFAULT_PALETTE,
    DEFAULT_SACCADE_WIDTH,
    HIGHLIGHTED_TEXT_COLOR,
    SACCADE_CLASS_ORDER,
    SACCADE_COLOR,
    UNIFORM_COLOR_FIELD,
    WORD_LABEL_COLOR,
)
from .data import compute_word_metrics
from .measures import assign_fixations_to_words, enrich_fixations
from .plots import make_scanpath_figure, split_scanpath_layers
from .preprocessing import (
    character_grid,
    cleaning_report,
    saccade_table,
    sentence_measures,
)
from .utils import extract_trial

# --- EXP-1 · customizable export paths ---------------------------------------
# A zip of 200 trials landed with names the tool chose, which is rarely how a
# user organizes figures for a paper. The path of every artifact is now a
# *pattern* over the trial's own fields, so a batch can be dropped straight into
# an existing folder structure. The default reproduces the historical layout
# exactly, so nothing changes unless the pattern is edited.
DEFAULT_PATH_PATTERN = "per_trial/{participant_id}__{trial_id}/{artifact}.{ext}"
# EXP-2 · a figure pulled into a paper or a slide loses its provenance the moment
# it leaves the app, so it can carry its own. Same substitution as the path
# patterns; empty means "no title / no caption".
DEFAULT_TITLE_PATTERN = "{participant_id} · {trial_id}"
DEFAULT_CAPTION_PATTERN = "{text_id} · {n_fixations} fixations · {settings}"


@dataclass
class ExportOptions:
    """User-chosen export artifacts.

    Defaults: figures on (PNG + SVG), tabular data off. The scope fields
    narrow the set of trials when not "all".
    """

    include_png: bool = True
    include_svg: bool = True
    include_pdf: bool = False
    # HTML is a browser-free figure format (fig.to_html — no Kaleido/Chrome) and
    # stays interactive; handled specially in the export loop.
    include_html: bool = False
    include_plot_config: bool = True
    include_fixations: bool = False
    include_measures: bool = False
    include_mega_table: bool = False
    include_analysis_family: bool = False
    # VIZ-5: also drop a per-layer breakdown of the figure (word boxes / fixations
    # / saccades / heatmap / labels / stimulus image) into `layers/` so each can be
    # restyled independently in Illustrator / Inkscape. Uses the selected vector /
    # raster formats (SVG when none was picked — the publication default).
    separable_layers: bool = False
    table_format: str = "csv"  # "csv" | "parquet" | "both"
    png_scale: int = 2
    # EXP-1: where each artifact lands inside the zip. `{artifact}` / `{ext}` name
    # the file (figure / fixations / measures / plot_config / layer names); every
    # other placeholder comes from the trial. The default is the historical layout.
    path_pattern: str = DEFAULT_PATH_PATTERN
    # EXP-2: an optional title + caption rendered into the exported image and
    # recorded in the per-trial manifest. Empty = off (the historical behaviour).
    title_pattern: str = ""
    caption_pattern: str = ""
    # When True, export operates on the whole loaded dataset, ignoring the
    # sidebar "Filter trials" panel; the caller supplies the unfiltered frames.
    export_unfiltered: bool = False
    scope: str = "all"  # "all" | "trial" | "participant" | "text"
    scope_participant: Optional[str] = None
    scope_trial: Optional[str] = None
    scope_text: Optional[str] = None

    def any_table(self) -> bool:
        return (
            self.include_fixations
            or self.include_measures
            or self.include_mega_table
            or self.include_analysis_family
        )

    def table_formats(self) -> List[str]:
        if self.table_format == "both":
            return ["csv", "parquet"]
        return [self.table_format]

    def figure_formats(self) -> List[str]:
        formats: List[str] = []
        if self.include_png:
            formats.append("png")
        if self.include_svg:
            formats.append("svg")
        if self.include_pdf:
            formats.append("pdf")
        if self.include_html:
            formats.append("html")
        return formats

    def raster_formats(self) -> List[str]:
        """Figure formats that need Kaleido/Chrome (everything but HTML)."""
        return [f for f in self.figure_formats() if f != "html"]

    def layer_formats(self) -> List[str]:
        """Formats for the per-layer breakdown (VIZ-5) — the selected non-HTML
        figure formats, or SVG when none was picked (vectors suit Illustrator).
        Empty when separable layers are off."""
        if not self.separable_layers:
            return []
        return self.raster_formats() or ["svg"]

    def needs_figure(self) -> bool:
        """Whether the export builds each trial's figure at all (combined figure
        formats, or the per-layer breakdown)."""
        return bool(self.figure_formats()) or self.separable_layers

    def needs_kaleido(self) -> bool:
        """Whether any figure render goes through Kaleido/Chrome (combined raster
        formats, or per-layer non-HTML formats)."""
        return bool(self.raster_formats()) or bool(self.layer_formats())


@dataclass
class ExportProgress:
    total_trials: int
    finished_trials: int = 0
    bytes_written: int = 0
    errors: List[str] = field(default_factory=list)


def _safe_id(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(text))


# Placeholders every pattern gets on top of the trial's own columns.
_PATTERN_EXTRA_FIELDS = (
    "artifact",
    "ext",
    "n_fixations",
    "n_words",
    "reading_time_s",
    "settings",
)
_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")


def _settings_summary(settings: dict) -> str:
    """A one-line description of the settings that produced the figure (EXP-2)."""
    layers = [
        name
        for name, key in (
            ("boxes", "show_words"),
            ("text", "show_word_labels"),
            ("fixations", "show_fixations"),
            ("saccades", "show_saccades"),
            ("heatmap", "show_heatmap"),
        )
        if settings.get(key)
    ]
    parts = [f"layers: {', '.join(layers) or 'none'}"]
    color_by = settings.get("color_by")
    if color_by and color_by != UNIFORM_COLOR_FIELD:
        parts.append(f"colour by {color_by}")
    palette = settings.get("palette", DEFAULT_PALETTE)
    if palette and palette != DEFAULT_PALETTE:
        parts.append(f"{palette} palette")
    return " · ".join(parts)


def pattern_fields(
    participant: str,
    trial: str,
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    settings: dict,
    combo_row: Optional[dict] = None,
) -> dict:
    """Every value a filename / title / caption pattern can substitute.

    The trial's own combo columns (participant, trial, text, conditions …) plus
    counts and the settings summary. Values are left raw here; path rendering
    sanitizes them, while titles and captions want them readable.
    """
    fields: dict = dict(combo_row or {})
    fields.update(
        participant_id=participant,
        trial_id=trial,
        n_fixations=len(trial_fixations),
        n_words=len(trial_words),
        reading_time_s=round(
            float(
                pd.to_numeric(trial_fixations.get("duration_ms"), errors="coerce").sum()
            )
            / 1000.0,
            1,
        )
        if "duration_ms" in getattr(trial_fixations, "columns", [])
        else 0.0,
        settings=_settings_summary(settings),
    )
    fields.setdefault("text_id", trial)
    return fields


def pattern_error(pattern: str, fields: dict) -> Optional[str]:
    """A human message naming any unknown placeholder, or ``None`` if valid.

    Validated up front (and shown live in the UI) rather than at export time —
    discovering a typo after a 200-trial render is the worst place to find it.
    """
    known = set(fields) | set(_PATTERN_EXTRA_FIELDS)
    unknown = [name for name in _PLACEHOLDER_RE.findall(pattern) if name not in known]
    if not unknown:
        return None
    return (
        f"Unknown field{'s' if len(unknown) > 1 else ''}: "
        f"{', '.join('{' + u + '}' for u in unknown)}. "
        f"Available: {', '.join('{' + k + '}' for k in sorted(known))}."
    )


def _path_component(text: str) -> str:
    """One path segment, sanitized. ``.`` / ``..`` collapse so nothing escapes."""
    safe = _safe_id(text)
    return "_" if set(safe) <= {"."} else safe


def render_pattern(
    pattern: str,
    fields: dict,
    *,
    as_path: bool = False,
    multi_segment_fields: tuple = (),
) -> str:
    """Substitute ``fields`` into ``pattern``.

    ``as_path`` sanitizes each substituted value, so a *data* value containing
    ``/`` or ``..`` becomes one flat segment and can't escape the folder the
    pattern describes; the pattern's own ``/`` stay real separators.
    ``multi_segment_fields`` names the tool-controlled fields allowed to expand
    into several segments (``artifact``, which carries ``layers/<name>``) — each
    of their segments is still sanitized individually. A missing or null value
    becomes ``na`` rather than failing the whole export.
    """

    def _sub(match: "re.Match") -> str:
        name = match.group(1)
        value = fields.get(name, "")
        if value is None or (isinstance(value, float) and pd.isna(value)):
            value = "na"
        text = str(value)
        if not as_path:
            return text
        if name in multi_segment_fields:
            return "/".join(_path_component(part) for part in text.split("/"))
        return _path_component(text)

    return _PLACEHOLDER_RE.sub(_sub, pattern)


def resolve_export_path(
    pattern: str, fields: dict, *, artifact: str, ext: str, used: set
) -> str:
    """The zip path for one artifact, de-duplicated against ``used``.

    Two trials can render to the same path (a pattern that omits the trial id,
    say). Writing both would put two entries at one name in the zip and silently
    lose one, so the second gets a ``-2`` suffix instead. ``used`` is mutated.
    """
    path = render_pattern(
        pattern,
        {**fields, "artifact": artifact, "ext": ext},
        as_path=True,
        multi_segment_fields=("artifact",),
    ).lstrip("/")
    if path not in used:
        used.add(path)
        return path
    stem, dot, suffix = path.rpartition(".")
    base, tail = (stem, f"{dot}{suffix}") if dot else (path, "")
    n = 2
    while f"{base}-{n}{tail}" in used:
        n += 1
    path = f"{base}-{n}{tail}"
    used.add(path)
    return path


# --- EXP-2 · titles and captions on the exported figure -----------------------
# Sized bands rather than Plotly's automatic title spacing: the scanpath figure
# is equal-aspect (`scaleanchor`), so anything that eats into the plot area
# shrinks the WHOLE plot — and the true-to-scale word labels, computed for the
# un-shrunk size, then no longer match their boxes. Same constraint the animation
# transport controls hit; same fix: grow the figure by exactly what the band
# takes, so the plot region is untouched.
_TITLE_BAND_PX = 46
_CAPTION_LINE_PX = 22
_CAPTION_PAD_PX = 12


def annotate_figure(fig, *, title: str = "", caption: str = "") -> None:
    """Stamp ``title`` / ``caption`` onto ``fig`` in place, without shrinking it.

    The figure grows by the height of each band and its margin grows to match, so
    the plotting area — and therefore the true-to-scale text — is byte-identical
    to the untitled figure.
    """
    if not title and not caption:
        return
    margin = fig.layout.margin
    height = fig.layout.height
    if title:
        fig.layout.margin.t = (margin.t or 0) + _TITLE_BAND_PX
        if height:
            height += _TITLE_BAND_PX
            fig.layout.height = height
        fig.update_layout(
            title=dict(
                text=title,
                x=0.5,
                xanchor="center",
                y=1.0,
                yanchor="top",
                pad=dict(t=14),
                font=dict(size=20),
            )
        )
    if caption:
        original_bottom = fig.layout.margin.b or 0
        band = _CAPTION_LINE_PX * (caption.count("\n") + 1) + _CAPTION_PAD_PX
        fig.layout.margin.b = original_bottom + band
        if height:
            fig.layout.height = height + band
        # Anchored to the plot's bottom edge and pushed into the space just
        # added, so it never overlaps whatever already lived in that margin.
        fig.add_annotation(
            text=caption.replace("\n", "<br>"),
            xref="paper",
            yref="paper",
            x=0,
            y=0,
            xanchor="left",
            yanchor="top",
            yshift=-(original_bottom + _CAPTION_PAD_PX // 2),
            showarrow=False,
            align="left",
            font=dict(size=13, color="#555555"),
        )


# DATA-16 (security audit S4). Columns that hold a filesystem path from the
# machine the app ran on. `image_path` is a `passthrough` meta field on both
# schemas, so it survives normalization and rides into the exported fixation
# tables — and a fixations CSV is exactly the file that gets attached to a paper,
# posted to OSF, or mailed to a collaborator. `/Users/<name>/` discloses the OS
# account; the rest discloses the directory layout, including where a MultiplEYE
# corpus lives. The basename still identifies the stimulus, which is all the
# column is used for downstream.
#
# `source_file` is deliberately NOT here: `data.read_tables` stores `Path(...).stem`,
# so it never held a directory in the first place.
_PATH_COLUMNS = ("image_path",)


def strip_local_paths(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce path-bearing columns to their basename (S4).

    Returns ``df`` unchanged (the same object) when it carries none of them, so
    the common case costs one membership test and no copy.
    """
    present = [c for c in _PATH_COLUMNS if c in df.columns]
    if not present:
        return df
    out = df.copy()
    for column in present:
        values = out[column]
        # `na_action="ignore"` is load-bearing: pandas evaluates the `other`
        # argument of `.where` eagerly, over every row including the missing
        # ones, and since pandas 3 `astype(str)` leaves NaN as a float instead
        # of stringifying it to "nan" — so the lambda would see a float.
        out[column] = values.where(
            values.isna(),
            values.astype(str).map(
                lambda text: PurePosixPath(text.replace("\\", "/")).name,
                na_action="ignore",
            ),
        )
    return out


def _write_table(zf: zipfile.ZipFile, path: str, df: pd.DataFrame, fmt: str) -> int:
    df = strip_local_paths(df)
    if fmt == "parquet":
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        data = buf.getvalue()
    else:
        data = df.to_csv(index=False).encode("utf-8")
    zf.writestr(path, data)
    return len(data)


@contextmanager
def _figure_renderer(enabled: bool):
    """Yield ``render(fig, fmt, width, height, scale) -> bytes``.

    When ``enabled`` and Kaleido starts, every trial's figure is rasterized
    through one persistent Kaleido browser (``calc_fig_sync``) instead of
    cold-starting a fresh Chrome on each ``fig.to_image`` call — the cold start
    is the "Resorting to unclean kill browser." log noise and ~seconds-per-trial
    latency. Falls back to per-call ``to_image`` if the warm server can't start
    (or no figures were requested), so behavior is unchanged when Kaleido/Chrome
    is unavailable — the per-trial failure is still surfaced as an export error.
    """
    server = None
    if enabled:
        try:
            import kaleido

            kaleido.start_sync_server(silence_warnings=True)
            server = kaleido
        except Exception:
            server = None

    def render(fig, fmt: str, width: int, height: int, scale: int) -> bytes:
        if server is not None:
            data = server.calc_fig_sync(
                fig,
                opts={
                    "format": fmt,
                    "width": int(width),
                    "height": int(height),
                    "scale": scale,
                },
            )
            return bytes(data)
        return fig.to_image(
            format=fmt, width=int(width), height=int(height), scale=scale
        )

    try:
        yield render
    finally:
        if server is not None:
            try:
                server.stop_sync_server(silence_warnings=True)
            except Exception:  # pragma: no cover - best-effort teardown
                pass


def _drift_corrected_for_figure(
    fix: pd.DataFrame, words: pd.DataFrame, settings: dict
) -> tuple[pd.DataFrame, Optional[tuple]]:
    """PRE-3 drift correction for one exported figure (EXP-4 / VIZ-24).

    Returns ``(figure_fixations, connector_y)``. When no algorithm is selected
    (``align_algorithm`` absent / ``"Off"`` — the default) or there is nothing to
    correct, hands back the very same frame object and ``None`` — a true no-op,
    mirroring ``tabs._drift_corrected``. Otherwise the returned frame has each
    fixation's ``y`` snapped to its assigned text line, and ``connector_y``
    carries the *original* y values when ``align_connectors`` is on (the faint
    original→corrected connector layer).

    Deliberate asymmetry: this feeds the **figure only** — the exported tables
    (fixations, measures, mega-table) stay uncorrected, because the correction
    is a view on the data, not a rewrite of it."""
    algorithm = settings.get("align_algorithm")
    if (
        not algorithm
        or str(algorithm) == "Off"
        or fix is None
        or fix.empty
        or words is None
        or words.empty
    ):
        return fix, None
    from .alignment import correct  # local: pulls in scipy only when used

    corrected, _ = correct(fix, words, method=str(algorithm).lower())
    connector_y = None
    if settings.get("align_connectors") and "y" in fix.columns:
        connector_y = tuple(pd.to_numeric(fix["y"], errors="coerce"))
    return corrected, connector_y


def _plot_config_dict(
    participant: str,
    trial: str,
    canvas_width: int,
    canvas_height: int,
    x_field: str,
    y_field: str,
    settings: dict,
    *,
    drift_applied: bool = False,
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
            "saccade_arrows": settings.get("show_saccade_arrows", False),
            "heatmap": settings.get("show_heatmap"),
            "raw_gaze": settings.get("show_raw_gaze"),
        },
        "coloring": {
            "color_by": settings.get("color_by"),
            "heatmap_metric": settings.get("heatmap_metric"),
            "heatmap_style": settings.get("heatmap_style", "Word boxes"),
            "fixation_colorscale": settings.get("fixation_colorscale"),
            "heatmap_colorscale": settings.get("heatmap_colorscale"),
            # VIZ-18 palette · VIZ-17 flat colour · VIZ-15 shape — part of how the
            # figure looked, so the manifest records them for reproduction.
            "palette": settings.get("palette", DEFAULT_PALETTE),
            "fixation_color": settings.get("fixation_color", DEFAULT_FIXATION_COLOR),
            "fixation_symbol": settings.get("fixation_symbol", DEFAULT_FIXATION_SYMBOL),
            "saccade_color_mode": settings.get("saccade_color_mode", "Uniform"),
            # VIZ-31: which reading classes the exported figures actually drew —
            # a regressions-only batch has to say so, or the files look like a
            # dataset with almost no saccades in it.
            "saccade_classes": list(
                settings.get("saccade_classes") or SACCADE_CLASS_ORDER
            ),
            # EXP-4 / VIZ-24: which PRE-3 drift correction produced the exported
            # figure ("Off" = none). The exported tables stay uncorrected — the
            # manifest is where that split is recorded. Same keys as the 💾 Save
            # & restore config (ENG-23). `color_by_line` records the EFFECTIVE
            # value: a corrected figure is force-coloured by line, like the
            # on-screen static path.
            "drift_correction": str(settings.get("align_algorithm", "Off") or "Off"),
            "drift_connectors": bool(settings.get("align_connectors", False)),
            "color_by_line": bool(settings.get("color_by_line", False))
            or drift_applied,
        },
        "sizing": {
            "marker_size_range": list(settings.get("marker_size_range", [])),
            "order_font_size": settings.get("order_font_size"),
        },
        # True-to-scale reading text: records how the word labels were sized so
        # the figure can be reproduced exactly (see plots._word_label_font_px).
        "text": {
            "scale_text_to_boxes": settings.get("scale_text_to_boxes", True),
            "line_spacing": settings.get("line_spacing", DEFAULT_LINE_SPACING),
        },
    }


def _render_scope_picker(
    st,
    combos: pd.DataFrame,
    key_prefix: str,
    combos_all: Optional[pd.DataFrame] = None,
) -> tuple[str, Optional[str], Optional[str], Optional[str], bool]:
    """Render the scope radio + dependent selectors.

    Returns ``(scope, pid, trial, text, export_unfiltered)``. The whole-dataset
    choice lives inside the "Trials to include" radio (an extra "All" option that
    ignores the sidebar filter) rather than as a separate checkbox.
    """
    # Build the ordered radio: label -> (scope, export_unfiltered). Both "All"
    # (the whole dataset, ignoring the sidebar filter) and "All filtered trials"
    # (the current sidebar selection) are always offered — they coincide only
    # when no filter is active.
    # A single trial is exported from the "This trial" section above (the
    # currently-viewed trial), so the bulk picker only offers multi-trial scopes.
    options_map: dict[str, tuple[str, bool]] = {
        "All": ("all", True),
        "All filtered trials": ("all", False),
    }
    options_map["All trials of one participant"] = ("participant", False)
    options_map["All trials of one text"] = ("text", False)

    # Default to the filtered subset (respect what the user narrowed to).
    default_index = 1
    scope_label = st.radio(
        "Trials to include",
        options=list(options_map),
        index=default_index,
        key=f"{key_prefix}_scope",
        horizontal=True,
        help="Limit the export to a subset of trials. **All** exports every "
        "trial in the dataset, ignoring the **Filter trials** sidebar panel.",
    )
    scope, export_unfiltered = options_map[scope_label]
    active = combos_all if (export_unfiltered and combos_all is not None) else combos

    scope_participant: Optional[str] = None
    scope_trial: Optional[str] = None
    scope_text: Optional[str] = None
    text_col = (
        "unique_text_id"
        if "unique_text_id" in active.columns
        else ("text_id" if "text_id" in active.columns else None)
    )

    if scope == "trial" and not active.empty:
        participants = sorted(active["participant_id"].dropna().astype(str).unique())
        scope_participant = st.selectbox(
            "Participant", options=participants, key=f"{key_prefix}_scope_pid"
        )
        trials_for_pid = (
            active.loc[
                active["participant_id"].astype(str) == str(scope_participant),
                "trial_id",
            ]
            .astype(str)
            .unique()
        )
        scope_trial = st.selectbox(
            "Trial", options=sorted(trials_for_pid), key=f"{key_prefix}_scope_trial"
        )
    elif scope == "participant" and not active.empty:
        participants = sorted(active["participant_id"].dropna().astype(str).unique())
        scope_participant = st.selectbox(
            "Participant", options=participants, key=f"{key_prefix}_scope_pid"
        )
    elif scope == "text" and not active.empty:
        if text_col is None:
            st.info("No text id is available in this dataset.")
        else:
            texts = sorted(active[text_col].dropna().astype(str).unique())
            scope_text = st.selectbox(
                "Text", options=texts, key=f"{key_prefix}_scope_text"
            )

    # Close the Scope section with a live count of what will be exported.
    n_export = len(
        _scope_frame(active, scope, scope_participant, scope_trial, scope_text)
    )
    n_total = len(combos_all) if combos_all is not None else len(combos)
    st.caption(f"**{n_export:,}** of **{n_total:,}** trials will be exported.")

    return scope, scope_participant, scope_trial, scope_text, export_unfiltered


def _preview_fields(combos: pd.DataFrame) -> dict:
    """Stand-in field values for the live pattern preview (EXP-1/EXP-2).

    Uses the first trial in scope, so the preview is a path the user will
    actually get rather than a made-up example.
    """
    row = combos.iloc[0].to_dict() if combos is not None and not combos.empty else {}
    fields = dict(row)
    fields.setdefault("participant_id", "p01")
    fields.setdefault("trial_id", "t01")
    fields.setdefault("text_id", fields["trial_id"])
    fields.update(
        n_fixations=123,
        n_words=45,
        reading_time_s=18.4,
        settings="layers: fixations, saccades, text",
    )
    return fields


def _render_naming_options(st, combos: pd.DataFrame, key_prefix: str):
    """The **Naming & labels** block: EXP-1's path pattern.

    Every pattern is validated and previewed against the first trial in scope as
    it's typed — finding a typo after a 200-trial render is the worst possible
    place to find it. Returns ``path_pattern``; an invalid pattern falls back to
    its default so a bad keystroke can't produce a broken zip.

    The title/caption pair used to live here too (EXP-2) but moved to the
    Scanpath rail's **📐 Figure & axes** group (EXP-5), so it's visible on the
    live figure and not just at export time; `render_export_options` reads it
    back from there instead of keeping a second, possibly-diverging copy.
    """
    st.markdown("### Naming & labels")
    fields = _preview_fields(combos)
    available = ", ".join(
        f"`{{{k}}}`" for k in sorted(set(fields) | set(_PATTERN_EXTRA_FIELDS))
    )

    def _pattern_input(label: str, default: str, key: str, help_text: str) -> str:
        value = st.text_input(label, value=default, key=key, help=help_text)
        error = pattern_error(value, fields)
        if error:
            st.error(error)
            return default
        return value

    path_pattern = _pattern_input(
        "File path pattern",
        DEFAULT_PATH_PATTERN,
        f"{key_prefix}_path_pattern",
        "Where each file lands inside the zip. `{artifact}` is the file "
        "(figure / fixations / measures / plot_config) and `{ext}` its format; "
        "`/` makes a folder.",
    )
    st.caption(
        "Preview — "
        + " · ".join(
            f"`{resolve_export_path(path_pattern, fields, artifact=a, ext=e, used=set())}`"
            for a, e in (("figure", "png"), ("fixations", "csv"))
        )
    )
    with st.expander("Available fields", expanded=False):
        st.markdown(available)
    return path_pattern


def render_export_options(
    st_module,
    combos: pd.DataFrame,
    key_prefix: str = "export",
    combos_all: Optional[pd.DataFrame] = None,
    title_pattern: str = "",
    caption_pattern: str = "",
) -> ExportOptions:
    """Render the bulk-export options UI and return a populated ExportOptions.

    ``combos`` is the currently filtered trial pool; ``combos_all`` (when given)
    is the whole loaded dataset. Picking the "All" scope switches the scope
    picker — and the export itself — to ``combos_all`` so the sidebar filters
    are ignored. ``title_pattern``/``caption_pattern`` come from the Scanpath
    rail's **📐 Figure & axes** → *Title & caption on the figure* (EXP-5) —
    this panel no longer has its own copy of that setting.
    """
    st = st_module
    # No expander — the options are always displayed.
    with st.container():
        st.caption(
            "Export many trials at once. Everything is packaged into a single "
            "zip you can download. (To export just the trial on screen, use "
            "**This trial** above.)"
        )

        st.markdown("### Scope")
        # The whole-dataset choice lives inside the scope radio.
        (
            scope,
            scope_pid,
            scope_trial,
            scope_text,
            export_unfiltered,
        ) = _render_scope_picker(st, combos, key_prefix, combos_all=combos_all)

        # Figures are the headline artifact, so they lead with a single
        # multi-select of formats (pills) rather than a column of checkboxes.
        st.markdown("### Figures")
        fig_formats = (
            st.pills(
                "Formats",
                options=["PDF", "SVG", "PNG", "HTML"],
                selection_mode="multi",
                default=["PDF"],
                key=f"{key_prefix}_figfmts",
                help="PDF / SVG are vector; PNG is raster (set the scale below). "
                "PDF / SVG / PNG render via Kaleido (needs Chrome). HTML is "
                "interactive and needs no browser.",
            )
            or []
        )
        include_pdf = "PDF" in fig_formats
        include_svg = "SVG" in fig_formats
        include_png = "PNG" in fig_formats
        include_html = "HTML" in fig_formats
        # Only surface the scale stepper when PNG is on, and keep it narrow.
        if include_png:
            scale_col, _ = st.columns([1, 3])
            png_scale = scale_col.number_input(
                "PNG scale",
                min_value=1,
                max_value=4,
                value=2,
                key=f"{key_prefix}_scale",
                help="Higher → better quality and larger files. 1 = 1×, 2 = retina, 4 = poster.",
            )
        else:
            png_scale = int(st.session_state.get(f"{key_prefix}_scale", 2))

        st.markdown("### Also include")
        # VIZ-5: per-layer figure breakdown for publication editing.
        separable_layers = st.toggle(
            "Separable layers",
            value=False,
            key=f"{key_prefix}_layers",
            help="Also export the figure split into one file per layer (word boxes "
            "/ fixations / saccades / heatmap / labels / stimulus image) under "
            "`layers/`, so you can restyle each independently in Illustrator / "
            "Inkscape. Uses the vector/raster figure formats above (SVG if only "
            "HTML or nothing is picked); the layers register perfectly when "
            "stacked.",
        )
        # Layers are static vectors/rasters — HTML can't be split. When no
        # vector/raster format is picked, they fall back to SVG (which needs
        # Kaleido/Chrome, unlike the browser-free HTML the user chose), so warn.
        if separable_layers and not (include_png or include_svg or include_pdf):
            st.caption(
                "⚠️ Separable layers export as **SVG** (a static vector needing "
                "Chrome/Kaleido) — HTML figures can't be split. Pick SVG/PDF/PNG "
                "above to choose the layer format."
            )
        include_plot_config = st.toggle(
            "Plot config (JSON)",
            value=True,
            key=f"{key_prefix}_cfg",
            help="A JSON snapshot of every plot setting (layers, colors, sizing, "
            "text scaling) — bundle it to reproduce or restore these exact "
            "figures later.",
        )
        tabular = (
            st.pills(
                "Tabular data",
                options=[
                    "Fixations",
                    "Word measures",
                    "Full measure family",
                    "Mega-table",
                ],
                selection_mode="multi",
                default=[],
                key=f"{key_prefix}_tabular",
                help="Fixations: per-trial fixation rows. Word measures: per-word "
                "FFD / FPRT / RPD / TFD … Mega-table: one aggregated table across "
                "every selected trial. Full measure family adds saccades, sentences, "
                "trial/reader summaries, character grids, cleaning QA, and run settings.",
            )
            or []
        )
        include_fixations = "Fixations" in tabular
        include_measures = "Word measures" in tabular
        include_mega_table = "Mega-table" in tabular
        include_analysis_family = "Full measure family" in tabular
        any_table = bool(tabular)
        if any_table:
            table_format = (
                st.segmented_control(
                    "Table format",
                    options=["csv", "parquet", "both"],
                    default="csv",
                    key=f"{key_prefix}_fmt",
                )
                or "csv"
            )
        else:
            table_format = str(st.session_state.get(f"{key_prefix}_fmt", "csv"))

        path_pattern = _render_naming_options(st, combos, key_prefix)
        if title_pattern or caption_pattern:
            st.caption(
                "Title & caption on the figure — set on the Scanpath rail's "
                "**📐 Figure & axes** → *Title & caption on the figure*, and "
                "applied here too."
            )

    return ExportOptions(
        include_png=include_png,
        include_svg=include_svg,
        include_pdf=include_pdf,
        include_html=include_html,
        include_plot_config=include_plot_config,
        include_fixations=include_fixations,
        include_measures=include_measures,
        include_mega_table=include_mega_table,
        include_analysis_family=include_analysis_family,
        separable_layers=separable_layers,
        table_format=table_format,
        png_scale=int(png_scale),
        path_pattern=path_pattern,
        title_pattern=title_pattern,
        caption_pattern=caption_pattern,
        export_unfiltered=export_unfiltered,
        scope=scope,
        scope_participant=scope_pid,
        scope_trial=scope_trial,
        scope_text=scope_text,
    )


def _scope_frame(
    combos: pd.DataFrame,
    scope: str,
    scope_participant: Optional[str],
    scope_trial: Optional[str],
    scope_text: Optional[str],
) -> pd.DataFrame:
    """Filter combos to the chosen scope (pure helper, no ExportOptions needed)."""
    if scope == "trial" and scope_participant and scope_trial:
        return combos[
            (combos["participant_id"].astype(str) == str(scope_participant))
            & (combos["trial_id"].astype(str) == str(scope_trial))
        ]
    if scope == "participant" and scope_participant:
        return combos[combos["participant_id"].astype(str) == str(scope_participant)]
    if scope == "text" and scope_text:
        text_col = (
            "unique_text_id"
            if "unique_text_id" in combos.columns
            else ("text_id" if "text_id" in combos.columns else None)
        )
        if text_col is None:
            return combos
        return combos[combos[text_col].astype(str) == str(scope_text)]
    return combos


def _apply_scope(combos: pd.DataFrame, options: ExportOptions) -> pd.DataFrame:
    """Filter combos according to options.scope."""
    return _scope_frame(
        combos,
        options.scope,
        options.scope_participant,
        options.scope_trial,
        options.scope_text,
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
    raw_gaze: Optional[pd.DataFrame] = None,
    progress_callback=None,
) -> tuple[bytes, ExportProgress]:
    """Build a zip archive of selected artifacts and return its bytes.

    progress_callback (if given) is invoked with an ExportProgress after every
    trial so the UI can update a progress bar.
    """
    combos = _apply_scope(combos, options)
    progress = ExportProgress(total_trials=len(combos))
    buf = io.BytesIO()
    zf = zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED)

    mega_fixations: list[pd.DataFrame] = []
    mega_measures: list[pd.DataFrame] = []
    mega_family: dict[str, list[pd.DataFrame]] = {
        "fixations": [],
        "word_measures": [],
        "saccades": [],
        "sentence_measures": [],
        "trial_summary": [],
        "characters": [],
        "cleaning_qa": [],
    }

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
        "- participant_id, trial_id, text_id, word_id",
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
    if options.include_analysis_family:
        zf.writestr(
            "run_config.json",
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "settings": settings,
                    "preprocessing": settings.get("preprocessing", {}),
                },
                indent=2,
                default=str,
            ),
        )

    # One warm Kaleido browser for every trial's figure (see _figure_renderer)
    # instead of cold-starting Chrome on each render. HTML needs no browser, so
    # only spin Kaleido up when a raster/vector format was requested (combined
    # figure or the per-layer breakdown).
    figure_formats = options.figure_formats()
    layer_formats = options.layer_formats()
    # EXP-1: a user pattern can map two trials to the same path (one that omits
    # the trial id, say). Two zip entries at one name silently loses a file, so
    # `resolve_export_path` disambiguates against what's already been written.
    used_paths: set = set()
    with _figure_renderer(options.needs_kaleido()) as render_figure:
        for combo in combos.itertuples(index=False):
            participant = getattr(combo, "participant_id")
            trial = getattr(combo, "trial_id")
            slug = f"{_safe_id(participant)}__{_safe_id(trial)}"

            # Slice via the same str-normalized position index the live view uses
            # (utils.extract_trial), so the export selects *exactly* what the trial
            # picker shows — not a raw dtype-sensitive boolean mask that can silently
            # miss rows the view finds.
            trial_words = extract_trial(words, participant, trial)
            trial_fix = extract_trial(fixations, participant, trial)

            # Skip only a genuinely empty trial (nothing to draw). The figure
            # builder renders from fixations alone (words optional — boxes/labels)
            # or from words alone (AOI layout), and the live view does too; so a
            # words-that-don't-join / fixations-only trial must still export
            # instead of being skipped with "empty data" (VIZ-5).
            if trial_words.empty and trial_fix.empty:
                progress.finished_trials += 1
                progress.errors.append(f"{slug}: empty data, skipped")
                if progress_callback:
                    progress_callback(progress)
                continue

            # EXP-1/EXP-2: everything this trial's paths, title and caption can
            # substitute — its combo row plus counts and the settings summary.
            fields = pattern_fields(
                participant,
                trial,
                trial_words,
                trial_fix,
                settings,
                combo_row=combo._asdict(),
            )

            def _path(artifact: str, ext: str, _f=fields) -> str:
                return resolve_export_path(
                    options.path_pattern,
                    _f,
                    artifact=artifact,
                    ext=ext,
                    used=used_paths,
                )

            title = (
                render_pattern(options.title_pattern, fields)
                if options.title_pattern
                else ""
            )
            caption = (
                render_pattern(options.caption_pattern, fields)
                if options.caption_pattern
                else ""
            )

            if options.needs_figure():
                fig = None
                try:
                    # EXP-4 / VIZ-24: apply the PRE-3 drift correction to the
                    # figure's fixations (a no-op when "Off"), so the batch
                    # matches the corrected figure on screen. `trial_fix` itself
                    # stays uncorrected — the tables below export the recording.
                    fig_fix, connector_y = _drift_corrected_for_figure(
                        trial_fix, trial_words, settings
                    )
                    fig = make_scanpath_figure(
                        trial_words,
                        fig_fix,
                        show_connectors=connector_y is not None,
                        connector_y=connector_y,
                        # A corrected figure colours by line, exactly as the
                        # on-screen static path forces it (tabs.py PRE-3
                        # overrides) — else the batch differs in colouring.
                        color_by_line=bool(settings.get("color_by_line", False))
                        or fig_fix is not trial_fix,
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
                        show_saccade_arrows=settings.get("show_saccade_arrows", False),
                        show_heatmap=settings.get("show_heatmap", False),
                        heatmap_style=settings.get("heatmap_style", "Word boxes"),
                        fit_to_monitor=settings.get("fit_to_monitor", True),
                        color_by=settings.get("color_by", "duration_ms"),
                        heatmap_metric=settings.get("heatmap_metric"),
                        marker_size_range=tuple(
                            settings.get("marker_size_range", (8, 24))
                        ),
                        order_font_size=int(settings.get("order_font_size", 10)),
                        order_font_color=settings.get("order_font_color", "#111111"),
                        show_colorbars=settings.get("show_colorbars", False),
                        fixation_color_range=settings.get("fixation_color_range"),
                        heatmap_range=settings.get("heatmap_range"),
                        fixation_colorscale=settings.get(
                            "fixation_colorscale", "Blues"
                        ),
                        heatmap_colorscale=settings.get(
                            "heatmap_colorscale", "Oranges"
                        ),
                        background_color=settings.get("background_color"),
                        fixation_flags=settings.get("fixation_flags"),
                        saccade_color=settings.get("saccade_color", SACCADE_COLOR),
                        saccade_style=settings.get("saccade_style", "solid"),
                        saccade_width=settings.get(
                            "saccade_width", DEFAULT_SACCADE_WIDTH
                        ),
                        hollow_fixations=settings.get("hollow_fixations", False),
                        fixation_opacity=settings.get("fixation_opacity", 1.0),
                        # VIZ-17 flat fixation colour · VIZ-15 marker shape.
                        fixation_color=settings.get(
                            "fixation_color", DEFAULT_FIXATION_COLOR
                        ),
                        fixation_symbol=settings.get(
                            "fixation_symbol", DEFAULT_FIXATION_SYMBOL
                        ),
                        # VIZ-8/19 saccade colour mode + VIZ-9 linear-reading mode:
                        # the bulk export rebuilds the figure from scratch, so it
                        # has to restate these or a batch silently comes out styled
                        # differently from the on-screen figure it was launched from.
                        saccade_color_mode=settings.get(
                            "saccade_color_mode", "Uniform"
                        ),
                        saccade_class_colors=settings.get("saccade_class_colors"),
                        saccade_type_legend=settings.get("saccade_type_legend", True),
                        # VIZ-31: the reading-class filter. A batch launched from
                        # a regressions-only view must export regressions-only
                        # figures, not the full scanpath.
                        saccade_classes=settings.get("saccade_classes"),
                        saccade_render_mode=settings.get(
                            "saccade_render_mode", "Straight"
                        ),
                        fixation_snap_to_word=settings.get(
                            "fixation_snap_to_word", False
                        ),
                        critical_span_style=settings.get(
                            "critical_span_style", "Mark text"
                        ),
                        highlight_column=settings.get(
                            "highlight_column", "is_in_aspan"
                        ),
                        text_color=settings.get("text_color", WORD_LABEL_COLOR),
                        highlight_text_color=settings.get(
                            "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
                        ),
                        line_spacing=settings.get("line_spacing", DEFAULT_LINE_SPACING),
                        scale_text_to_boxes=settings.get("scale_text_to_boxes", True),
                    )
                    # EXP-2: stamp the title/caption BEFORE measuring the output
                    # size — the bands grow the figure, and rendering at the
                    # pre-title size would crop them off.
                    annotate_figure(fig, title=title, caption=caption)
                    # Render at the figure's own fitted size (not the raw
                    # monitor canvas) so the exported reading text matches the
                    # on-screen scale.
                    out_w = int(fig.layout.width or canvas_width)
                    out_h = int(fig.layout.height or canvas_height)
                    for fmt in figure_formats:
                        if fmt == "html":
                            # Browser-free + interactive; no Kaleido needed.
                            data = fig.to_html(
                                include_plotlyjs="cdn", full_html=True
                            ).encode("utf-8")
                        else:
                            scale = options.png_scale if fmt == "png" else 1
                            data = render_figure(fig, fmt, out_w, out_h, scale)
                        zf.writestr(_path("figure", fmt), data)
                        progress.bytes_written += len(data)
                except Exception as exc:
                    progress.errors.append(f"{slug}: figure export failed ({exc})")

                # VIZ-5: per-layer breakdown into `layers/<layer>.<fmt>` — each a
                # copy of the figure with only one layer's elements, same
                # size/ranges so they register when stacked in Illustrator. Kept in
                # its own try so a layer-render failure is reported as such and
                # doesn't get misattributed to the combined figure (which may have
                # already been written above).
                if layer_formats and fig is not None:
                    try:
                        out_w = int(fig.layout.width or canvas_width)
                        out_h = int(fig.layout.height or canvas_height)
                        for layer_name, layer_fig in split_scanpath_layers(fig).items():
                            for fmt in layer_formats:
                                scale = options.png_scale if fmt == "png" else 1
                                data = render_figure(
                                    layer_fig, fmt, out_w, out_h, scale
                                )
                                zf.writestr(_path(f"layers/{layer_name}", fmt), data)
                                progress.bytes_written += len(data)
                    except Exception as exc:
                        progress.errors.append(f"{slug}: layer export failed ({exc})")

            if options.include_plot_config:
                # Same guard as _drift_corrected_for_figure: correction runs
                # when an algorithm is set and the trial has both frames.
                algorithm = settings.get("align_algorithm")
                drift_applied = (
                    bool(algorithm)
                    and str(algorithm) != "Off"
                    and not trial_fix.empty
                    and not trial_words.empty
                )
                cfg = _plot_config_dict(
                    participant,
                    trial,
                    canvas_width,
                    canvas_height,
                    x_field,
                    y_field,
                    settings,
                    drift_applied=drift_applied,
                )
                # EXP-2: the title/caption are part of how the figure looked, so
                # the manifest records them verbatim alongside the settings.
                cfg["annotations"] = {"title": title, "caption": caption}
                data = json.dumps(cfg, indent=2).encode("utf-8")
                zf.writestr(_path("plot_config", "json"), data)
                progress.bytes_written += len(data)

            # Per-word measures need the word table; a fixations-only trial has no
            # words to measure, so skip (an empty measures file adds nothing).
            per_trial_measures = (
                compute_word_metrics(trial_words, trial_fix)
                if (
                    options.include_measures
                    or options.include_mega_table
                    or options.include_analysis_family
                )
                and not trial_words.empty
                else None
            )
            family = {}
            if options.include_analysis_family:
                measured = (
                    per_trial_measures
                    if per_trial_measures is not None
                    else trial_words
                )
                analysis_fix = (
                    enrich_fixations(
                        assign_fixations_to_words(trial_fix, trial_words), trial_words
                    )
                    if not trial_fix.empty and not trial_words.empty
                    else trial_fix
                )
                family = {
                    "fixations": analysis_fix,
                    "word_measures": measured,
                    "saccades": saccade_table(
                        analysis_fix,
                        pixels_per_degree=settings.get("pixels_per_degree"),
                        raw_gaze=raw_gaze,
                        words=trial_words,
                    ),
                    "sentence_measures": sentence_measures(measured, analysis_fix),
                    "trial_summary": trial_summary_table(measured, analysis_fix),
                    "characters": character_grid(trial_words),
                    "cleaning_qa": cleaning_report(
                        analysis_fix,
                        short_policy=(settings.get("preprocessing") or {}).get(
                            "short_policy", "Off"
                        ),
                    ),
                }

            for fmt in options.table_formats():
                if options.include_fixations and not options.include_analysis_family:
                    progress.bytes_written += _write_table(
                        zf, _path("fixations", fmt), trial_fix, fmt
                    )
                if options.include_measures and per_trial_measures is not None:
                    progress.bytes_written += _write_table(
                        zf, _path("measures", fmt), per_trial_measures, fmt
                    )
                if options.include_analysis_family:
                    for artifact, table in family.items():
                        if table is not None and not table.empty:
                            progress.bytes_written += _write_table(
                                zf, _path(artifact, fmt), table, fmt
                            )

            if options.include_mega_table:
                mega_fixations.append(trial_fix)
                if per_trial_measures is not None:
                    mega_measures.append(per_trial_measures)
            if options.include_analysis_family:
                for artifact, table in family.items():
                    if table is not None and not table.empty:
                        mega_family[artifact].append(table)

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

    if options.include_analysis_family:
        for fmt in options.table_formats():
            for artifact, tables in mega_family.items():
                if tables:
                    progress.bytes_written += _write_table(
                        zf,
                        f"aggregate/all_{artifact}.{fmt}",
                        pd.concat(tables, ignore_index=True),
                        fmt,
                    )
            if mega_measures or words is not None:
                all_measures = (
                    pd.concat(mega_measures, ignore_index=True)
                    if mega_measures
                    else compute_word_metrics(words, fixations)
                )
                progress.bytes_written += _write_table(
                    zf,
                    f"aggregate/all_reader_summary.{fmt}",
                    reader_summary_table(
                        all_measures,
                        pd.concat(mega_family["fixations"], ignore_index=True)
                        if mega_family["fixations"]
                        else fixations,
                    ),
                    fmt,
                )
    zf.close()
    buf.seek(0)
    return buf.getvalue(), progress
