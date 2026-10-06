"""Configurable bulk export of figures and tabular data for filtered trials.

This module powers the "Bulk export" button. Users pick which artifacts they
want per trial (PNG, SVG, JSON plot config, fixations CSV/Parquet, per-word
measures CSV/Parquet), or each table once with every trial stacked in it
(EXP-23's *Combine all trials into one file*). Everything is packaged into a
single zip archive with a clean folder structure:

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
    ├─ aggregate/                 (combined tables, instead of the per-trial ones)
    │  ├─ all_fixations.csv (and/or .parquet)
    │  └─ all_measures.csv (and/or .parquet)
    └─ annotations.json          (UX-179, optional)
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Mapping
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath
from time import perf_counter

import pandas as pd

from .aggregation import reader_summary_table, trial_summary_table
from .column_names import (
    ColumnNames,
    across_tables,
    as_written,
    columns_manifest,
    dictionary_lines,
    written_columns,
)
from .constants import (
    CITATION,
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_LINE_SPACING,
    DEFAULT_PALETTE,
    ICONS,
    PLOTLY_CONFIG,
    SACCADE_CLASS_ORDER,
    UNIFORM_COLOR_FIELD,
    computed_measures_enabled,
    drift_correction_enabled,
)
from .data import brought_reading_measures, shareable_frame
from .export_status import ExportStage, StatusCallback, emit_status
from .fields import panel_field
from .measures import assign_fixations_to_words, enrich_fixations
from .multipart import (
    SCREEN_ID,
    SCREEN_INDEX,
    extract_part,
    part_catalog,
    screen_canvas_size,
)
from .plots import (
    SCANPATH_LAYER_ORDER,
    STATIC_FIGURE_OPTIONS,
    FigureSettings,
    make_scanpath_figure,
    split_scanpath_layers,
)
from .preprocessing import (
    character_grid,
    cleaning_report,
    saccade_table,
    sentence_measures,
)
from .progress import report as report_progress
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
    # UX-179: the exported trials' annotations (favorites, tags, notes) as one
    # `annotations.json` at the bundle root — the file 🗂️ Data → Annotations
    # exports and imports. Off by default: notes can be personal.
    include_annotations: bool = False
    include_fixations: bool = False
    # VIZ-45: each trial's raw (sample-level) gaze as its own table, written as
    # recorded — for a raw-gaze-only dataset it is the only recording there is.
    include_raw_gaze: bool = False
    # AN-32 / EXP-23: the word table with the reading measures the dataset
    # *brought*. Export computes none, as the Corpus Analysis page doesn't.
    include_measures: bool = False
    include_analysis_family: bool = False
    # EXP-23: write each chosen table once, every exported trial stacked, as
    # `aggregate/all_<table>` — instead of one file per trial. Replaced the
    # "Mega-table", which stacked two of the tables beside the per-trial ones.
    combine_trials: bool = False
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
    # VIZ-36: what `{dataset_name}` substitutes to. The app fills it from the
    # dataset picker's label; a headless caller that says nothing gets "", so
    # the placeholder renders empty rather than erroring on a surface nobody is
    # watching.
    dataset_name: str = ""
    # DATA-20 milestone 10: which columns of the attached participant table go
    # into `metadata/participants.*`. `None` is every field (the default, and
    # what a headless caller that knows nothing about this gets); a tuple is
    # exactly those, always alongside the reader id; an **empty** tuple leaves
    # the table out of the bundle. Reader attributes are the most re-identifying
    # thing an export can carry, so the opt-out has to be per field rather than
    # all-or-nothing.
    metadata_fields: tuple[str, ...] | None = None
    # DATA-29: the same per-field opt-out for the attached *trial* table,
    # written to `metadata/trials.*`. Kept as its own field rather than
    # folded into `metadata_fields` because the two tables are attached and
    # cleared independently, and because what is safe to ship differs by
    # grain: a reader attribute re-identifies a person, a trial attribute
    # usually describes the material.
    trial_metadata_fields: tuple[str, ...] | None = None
    # And the same opt-out for the attached *text* table, written to
    # `metadata/texts.*` — the third grain, same reasoning again.
    text_metadata_fields: tuple[str, ...] | None = None
    # HTML figures embed the Plotly library (opens offline, ~4.8 MB more per
    # file) instead of loading it from cdn.plot.ly when opened. Off by default:
    # the app's Export subtab sets it from its *HTML files* choice.
    html_self_contained: bool = False
    # When True, export operates on the whole loaded dataset, ignoring the
    # trial-filter funnel; the caller supplies the unfiltered frames.
    export_unfiltered: bool = False
    scope: str = "all"  # "all" | "trial" | "participant" | "text"
    scope_participant: str | None = None
    scope_trial: str | None = None
    scope_text: str | None = None

    def any_table(self) -> bool:
        return (
            self.include_fixations
            or self.include_raw_gaze
            or self.include_measures
            or self.include_analysis_family
        )

    def table_formats(self) -> list[str]:
        if self.table_format == "both":
            return ["csv", "parquet"]
        return [self.table_format]

    def figure_formats(self) -> list[str]:
        formats: list[str] = []
        if self.include_png:
            formats.append("png")
        if self.include_svg:
            formats.append("svg")
        if self.include_pdf:
            formats.append("pdf")
        if self.include_html:
            formats.append("html")
        return formats

    def raster_formats(self) -> list[str]:
        """Figure formats that need Kaleido/Chrome (everything but HTML)."""
        return [f for f in self.figure_formats() if f != "html"]

    def layer_formats(self) -> list[str]:
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
    errors: list[str] = field(default_factory=list)
    # EXP-24: what the build produced, for the summary under it — every file in
    # the zip, and the figure files (combined figures and per-layer files)
    # written and failed, one per format per trial.
    files_written: int = 0
    figures_written: int = 0
    figures_failed: int = 0
    trials_skipped: int = 0


@dataclass(frozen=True)
class ExportSummary:
    """EXP-24: how a finished bundle reads — ``level`` is ``"success"``,
    ``"warning"`` (some of it failed) or ``"error"`` (figures were asked for and
    none was made), and ``expand_errors`` opens the error list for the last."""

    level: str
    message: str
    expand_errors: bool


#: Session key of the Export subtab's *HTML files* choice — every HTML file
#: the subtab writes (the figure, the replay, the bundles) follows it.
HTML_SELF_CONTAINED_KEY = "export_html_self_contained"


def html_plotlyjs(self_contained: bool) -> bool | str:
    """``to_html``'s ``include_plotlyjs`` for a downloaded HTML file: the
    library embedded (opens offline), or loaded from cdn.plot.ly when opened."""
    return True if self_contained else "cdn"


def missing_browser_note(static_formats: bool) -> str:
    """EXP-24: the bundle's browser prerequisite, when it is unmet, else ``""``.

    The bundle draws PNG, SVG and PDF through Kaleido on the server, which
    needs Chrome, Chromium or Edge there; the current figure's PNG and SVG are
    saved by the reader's own browser and need none — a distinction the panel
    used to keep to itself, so a bundle on a machine without one built a zip
    of failures. Asked only when ``static_formats`` are picked.
    """
    if not static_formats:
        return ""
    from .animation_export import chrome_available

    if chrome_available():
        return ""
    return (
        "PNG, SVG and PDF bundle figures are drawn on this server with Chrome, "
        "Chromium or Edge, and none was found, so they will fail. Pick **HTML**, "
        "which needs no browser — or install one. The current figure's PNG and "
        "SVG downloads are saved by your own browser and need none."
    )


def summarize_export(progress: ExportProgress, size_bytes: int) -> ExportSummary:
    """What a built bundle holds and what failed, in one line (EXP-24).

    A generic "Ready" over a zip whose figures all failed read as a success,
    with the failures one click away in an expander. The line counts what was
    made and what wasn't; a build whose requested figures all failed is an
    error, with its list open. The zip stays downloadable either way — the
    files it does hold are good.
    """

    def plural(n: int, word: str) -> str:
        return f"{n:,} {word}{'' if n == 1 else 's'}"

    parts = [
        f"{plural(progress.files_written, 'file')} · {size_bytes / 1_048_576:.1f} MB"
    ]
    asked = progress.figures_written + progress.figures_failed
    if asked:
        parts.append(f"{progress.figures_written:,} of {plural(asked, 'figure')} made")
    if progress.figures_failed:
        parts.append(f"{progress.figures_failed:,} failed")
    if progress.trials_skipped:
        parts.append(f"{plural(progress.trials_skipped, 'trial')} skipped (no data)")
    message = " · ".join(parts)
    if asked and not progress.figures_written:
        return ExportSummary(
            "error",
            f"No figures were made · {message}. The errors are listed below.",
            True,
        )
    if progress.errors:
        return ExportSummary("warning", f"Partly built · {message}", False)
    return ExportSummary("success", f"Ready · {message}", False)


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


#: VIZ-36 — the fields that can hold *two* values at once, because an overlay
#: draws two readings into one frame. Each gains an ``_a`` / ``_b`` variant.
PAIRED_PATTERN_FIELDS = ("dataset_name", "participant_id", "trial_id", "text_id")

#: EXP-22 — the tables a pattern can name a field of, as ``{table.field}``, and
#: the heading each gets in the *Available fields* list. The metadata tables
#: plus the two data tables' saved fields; a qualified name is what tells two
#: tables' ``font_size`` apart, and what keeps them out of the plain list.
TABLE_PATTERN_LABELS = {
    "participants": "Participants table",
    "trials": "Trials table",
    "texts": "Texts table",
    "fixations": "Fixations table",
    "words": "AOI table",
}

#: Columns a data table always carries or the app derives — the trial's own
#: identity, geometry and timing, which the plain fields already cover or which
#: are not one value per trial. What is left is what the user kept.
_CORE_TABLE_COLUMNS = frozenset(
    {
        "participant_id",
        "trial_id",
        "text_id",
        "paragraph_id",
        "unique_trial_id",
        "unique_text_id",
        "unique_paragraph_id",
        "word_id",
        "text",
        "line_idx",
        "x",
        "y",
        "width",
        "height",
        "screen_id",
        "screen_index",
        "canvas_width",
        "canvas_height",
        "screen_timestamp_ms",
        "screen_fixation_id",
        "duration_ms",
        "timestamp_ms",
        "fixation_id",
        "order_in_trial",
        "pass_index",
        "saccade_type",
        "saccade_amplitude",
        "eye",
        "source_file",
        "TRIAL_INDEX",
        "trial_index",
    }
)


def _saved_table_fields(frame: pd.DataFrame | None) -> dict:
    """A data table's saved fields that hold one value for the whole trial.

    A field that varies within the trial (a word's surprisal, a fixation's
    pupil size) has no single value to put in a title, so it is not offered."""
    out: dict = {}
    if frame is None or getattr(frame, "empty", True):
        return out
    for column in frame.columns:
        name = str(column)
        if name.startswith("_") or name in _CORE_TABLE_COLUMNS:
            continue
        values = frame[column].dropna()
        if values.empty:
            continue
        try:
            distinct = values.unique()
        except TypeError:  # unhashable cells (lists, dicts)
            continue
        if len(distinct) != 1 or isinstance(distinct[0], (list, dict, set, tuple)):
            continue
        out[name] = distinct[0]
    return out


def table_pattern_fields(
    trial_words: pd.DataFrame | None,
    trial_fixations: pd.DataFrame | None,
    metadata_rows: dict | None = None,
) -> dict[str, dict]:
    """``{table: {"table.field": value}}`` for one trial (EXP-22).

    ``metadata_rows`` is this trial's row of each attached metadata table
    (``metadata.pattern_rows``); the fixations and AOI tables contribute their
    saved fields that are constant within the trial. Grouped by table so the
    *Available fields* list can head each group; :func:`pattern_fields`
    flattens it."""
    tables: dict[str, dict] = {}
    for table, row in (metadata_rows or {}).items():
        if row:
            tables[table] = {f"{table}.{name}": value for name, value in row.items()}
    for table, frame in (("fixations", trial_fixations), ("words", trial_words)):
        saved = _saved_table_fields(frame)
        if saved:
            tables[table] = {f"{table}.{name}": value for name, value in saved.items()}
    return tables


def pattern_fields(
    participant: str,
    trial: str,
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    settings: dict,
    combo_row: dict | None = None,
    dataset_name: str = "",
    compare_row: dict | None = None,
    metadata_rows: dict | None = None,
    column_names: ColumnNames | None = None,
) -> dict:
    """Every value a filename / title / caption pattern can substitute.

    DATA-66: with ``column_names`` (the dataset's map), every field its file
    named is also reachable under that name — ``{RECORDING_SESSION_LABEL}`` and
    ``{participant_id}`` both work, so a pattern can be written in either
    vocabulary.

    The trial's own combo columns (participant, trial, text, conditions …) plus
    counts and the settings summary. Values are left raw here; path rendering
    sanitizes them, while titles and captions want them readable.

    **VIZ-36 — ``dataset_name`` arrives as an argument, never read from here.**
    The app knows it as ``data_source_choice`` (since DATA-9 that key *is* the
    picker's label, and DATA-23's rename re-keys it), but this function is pure
    and also runs headless under ``api.save_figure_layers`` and ``cli render``,
    where there is no session at all. Each of the five callers supplies it.

    ``compare_row`` is the *other* reading in an overlay — two scanpaths in one
    frame, so a single ``{dataset_name}`` is ambiguous exactly where a title
    most wants to name both. Every field in :data:`PAIRED_PATTERN_FIELDS` gains
    an ``_a`` / ``_b`` variant, which are defined **always** (``_b`` empty when
    there is no second reading) so that a pattern written in compare mode still
    validates and renders on a single-trial figure instead of erroring on a
    surface the author cannot see.

    EXP-22: every attached metadata table's fields and each data table's saved
    fields join as ``{table.field}`` (:func:`table_pattern_fields`) — qualified,
    so a trial table's ``font_size`` and a recorded ``font_size`` are both
    reachable, and none of the plain names above changes.
    """
    fields: dict = dict(combo_row or {})
    for table in table_pattern_fields(
        trial_words, trial_fixations, metadata_rows
    ).values():
        fields.update(table)
    fields.update(
        participant_id=participant,
        trial_id=trial,
        dataset_name=dataset_name,
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
    for name in PAIRED_PATTERN_FIELDS:
        fields[f"{name}_a"] = fields.get(name, "")
        fields[f"{name}_b"] = (compare_row or {}).get(name, "")
    if column_names is not None:
        # The counts and the settings summary are the app's, whatever a column
        # of the same canonical name was called in the file.
        own = {"n_fixations", "n_words", "reading_time_s", "settings", "dataset_name"}
        named = [field for field in fields if field not in own]
        for canonical, header in column_names.export_headers(named).items():
            fields.setdefault(header, fields[canonical])
    return fields


def pattern_error(pattern: str, fields: dict) -> str | None:
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

    def _sub(match: re.Match) -> str:
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


#: DATA-66: the artifacts that *are* one of the dataset's tables (rows of it,
#: perhaps with computed columns added), and which one — so a fixation table's
#: `x` is named as the fixation file named it and a word table's `x` as the AOI
#: file did. Every other artifact is derived (a saccade table, a summary, a
#: character grid) and reuses canonical names for values of its own, so only its
#: id columns take the file's names (`ColumnNames.identity`).
_ARTIFACT_TABLE = {
    "fixations": "fixations",
    "raw_gaze": "raw_gaze",
    "measures": "words",
    "word_measures": "words",
}


def _write_table(
    zf: zipfile.ZipFile,
    path: str,
    df: pd.DataFrame,
    fmt: str,
    names: ColumnNames | None = None,
    hidden: set[str] | None = None,
) -> int:
    # DATA-49: the pipeline's bookkeeping columns stay out of what is shared.
    df = strip_local_paths(shareable_frame(df))
    # DATA-66: and the columns the user's file named go out under those names.
    df = as_written(df, names, hidden)
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

    ``enabled`` also holds ``animation_export.KALEIDO_LOCK`` until the server has
    stopped, since that server is one per process (UX-150).
    """
    from .animation_export import KALEIDO_LOCK

    with KALEIDO_LOCK if enabled else nullcontext():
        server = None
        if enabled:
            try:
                import kaleido

                from .animation_export import chromium_browser_path

                browser_path = chromium_browser_path()
                if browser_path is not None:
                    kaleido.start_sync_server(path=browser_path, silence_warnings=True)
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


def render_static_figure_bytes(
    fig,
    *,
    fmt: str,
    width: int,
    height: int,
    scale: float,
    status_callback: StatusCallback | None = None,
) -> bytes:
    """Render one static figure with observable indeterminate job stages."""
    from .animation_export import CHROME_INSTALL_HINT, chrome_available

    started = perf_counter()
    emit_status(
        status_callback,
        ExportStage.PREPARING,
        "Preparing figure and checking export settings…",
        started_at=started,
    )
    try:
        if not chrome_available():
            raise RuntimeError(CHROME_INSTALL_HINT)
        emit_status(
            status_callback,
            ExportStage.STARTING_RENDERER,
            "Starting the Chrome/Kaleido renderer (cold starts can take a few seconds)…",
            started_at=started,
        )
        with _figure_renderer(True) as render:
            emit_status(
                status_callback,
                ExportStage.RASTERIZING,
                f"Rendering {fmt.upper()}…",
                started_at=started,
            )
            data = render(fig, fmt.lower(), int(width), int(height), float(scale))
        emit_status(
            status_callback,
            ExportStage.FINALIZING,
            "Finalizing output bytes…",
            started_at=started,
        )
        result = bytes(data)
        emit_status(
            status_callback,
            ExportStage.READY,
            "Ready to download.",
            started_at=started,
        )
        return result
    except Exception as exc:
        emit_status(
            status_callback,
            ExportStage.ERROR,
            "Export failed.",
            started_at=started,
            error=str(exc),
        )
        raise


def _drift_corrected_for_figure(
    fix: pd.DataFrame, words: pd.DataFrame, settings: dict
) -> tuple[pd.DataFrame, tuple | None]:
    """PRE-3 drift correction for one exported figure (EXP-4 / VIZ-24).

    Returns ``(figure_fixations, connector_y)``. When no algorithm is selected
    (``align_algorithm`` absent / ``"Off"`` — the default) or there is nothing to
    correct, hands back the very same frame object and ``None`` — a true no-op,
    mirroring ``tabs._drift_corrected``. Otherwise the returned frame has each
    fixation's ``y`` snapped to its assigned text line, and ``connector_y``
    carries the *original* y values when ``align_connectors`` is on (the faint
    original→corrected connector layer).

    Deliberate asymmetry: this feeds the **figure only** — the exported tables
    (fixations, measures, combined tables) stay uncorrected, because the correction
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
    screen_id: str | None = None,
    drift_applied: bool = False,
) -> dict:
    selection = {"participant_id": participant, "trial_id": trial}
    if screen_id not in (None, ""):
        selection[SCREEN_ID] = str(screen_id)
    return {
        "selection": selection,
        "canvas_px": {"width": int(canvas_width), "height": int(canvas_height)},
        "axes": {
            "x_field": x_field,
            "y_field": y_field,
            "coordinate_grid": bool(settings.get("show_coordinate_grid", False)),
            "coordinate_grid_auto": settings.get("coordinate_grid_spacing") is None,
            "coordinate_grid_spacing": settings.get("coordinate_grid_spacing"),
        },
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
            # PRE-21: omitted entirely while drift correction is gated off —
            # recording `"drift_correction": "Off"` in every bundle would
            # advertise a control the build doesn't have.
            **(
                {
                    "drift_correction": str(
                        settings.get("align_algorithm", "Off") or "Off"
                    ),
                    "drift_connectors": bool(settings.get("align_connectors", False)),
                }
                if drift_correction_enabled()
                else {}
            ),
            "color_by_line": bool(settings.get("color_by_line", False))
            or drift_applied,
        },
        "sizing": {
            "marker_size_range": list(settings.get("marker_size_range", [])),
            "marker_size_scale": settings.get("marker_size_scale"),
            "marker_duration_range": list(settings.get("marker_duration_range") or []),
            "duration_size_legend": bool(settings.get("duration_size_legend", True)),
            "order_font_size": settings.get("order_font_size"),
        },
        # True-to-scale reading text: records how the word labels were sized so
        # the figure can be reproduced exactly (see plots._word_label_font_px).
        "text": {
            "scale_text_to_boxes": settings.get("scale_text_to_boxes", True),
            "line_spacing": settings.get("line_spacing", DEFAULT_LINE_SPACING),
        },
        # DATA-22 §7 surface 4: the recording setup + how each group is known, so
        # an exported figure set records that (say) its monitor size was assumed.
        # Sits beside `coloring.drift_correction`, which makes the same kind of
        # "what produced these files" statement. Omitted when the source declared
        # no setup — an absent key means unknown, which is the truth.
        **({"experimental_setup": setup} if (setup := _setup_section()) else {}),
    }


def _setup_section() -> dict | None:
    """The active source's `SetupSnapshot` as a dict, or ``None``.

    Imported lazily and defensively: `bulk_export` also runs headlessly (the CLI
    and `api.py`), where there is no session to read a snapshot from, and an
    export must never fail because it could not describe its own geometry.
    """
    try:
        from scanpath_studio.app import active_setup_snapshot

        snapshot = active_setup_snapshot()
    except Exception:  # pragma: no cover - headless / no session
        return None
    return snapshot.to_dict() if snapshot is not None else None


def _render_scope_picker(
    st,
    combos: pd.DataFrame,
    key_prefix: str,
    combos_all: pd.DataFrame | None = None,
    selected_participant: str | None = None,
    selected_trial: str | None = None,
) -> tuple[str, str | None, str | None, str | None, bool]:
    """Render the scope radio + dependent selectors.

    Returns ``(scope, pid, trial, text, export_unfiltered)``. The whole-dataset
    choice lives inside the "Trials to include" radio (an extra "All" option that
    ignores the trial filters) rather than as a separate checkbox.
    """
    # Build the ordered radio: label -> (scope, export_unfiltered). Both "All"
    # (the whole dataset, ignoring the trial filters) and "All filtered trials"
    # (the current filter selection) are always offered — they coincide only
    # when no filter is active.
    options_map: dict[str, tuple[str, bool]] = {
        "This trial": ("trial", False),
        "All": ("all", True),
        "All filtered trials": ("all", False),
    }
    options_map["All trials of one participant"] = ("participant", False)
    options_map["All trials of one text"] = ("text", False)

    # Default to the filtered subset (respect what the user narrowed to).
    default_index = 2
    scope_label = st.radio(
        "Trials to include",
        options=list(options_map),
        index=default_index,
        key=f"{key_prefix}_scope",
        horizontal=True,
        help="Choose a subset. All ignores active filters.",
        label_visibility="collapsed",
    )
    scope, export_unfiltered = options_map[scope_label]
    active = combos_all if (export_unfiltered and combos_all is not None) else combos

    scope_participant: str | None = None
    scope_trial: str | None = None
    scope_text: str | None = None
    text_col = (
        "unique_text_id"
        if "unique_text_id" in active.columns
        else ("text_id" if "text_id" in active.columns else None)
    )

    if scope == "trial" and not active.empty:
        if selected_participant is not None and selected_trial is not None:
            scope_participant = str(selected_participant)
            scope_trial = str(selected_trial)
        else:
            participants = sorted(
                active["participant_id"].dropna().astype(str).unique()
            )
            scope_participant = panel_field(
                st,
                "selectbox",
                "Participant",
                options=participants,
                key=f"{key_prefix}_scope_pid",
            )
            trials_for_pid = (
                active.loc[
                    active["participant_id"].astype(str) == str(scope_participant),
                    "trial_id",
                ]
                .astype(str)
                .unique()
            )
            scope_trial = panel_field(
                st,
                "selectbox",
                "Trial",
                options=sorted(trials_for_pid),
                key=f"{key_prefix}_scope_trial",
            )
    elif scope == "participant" and not active.empty:
        participants = sorted(active["participant_id"].dropna().astype(str).unique())
        scope_participant = panel_field(
            st,
            "selectbox",
            "Participant",
            options=participants,
            key=f"{key_prefix}_scope_pid",
        )
    elif scope == "text" and not active.empty:
        if text_col is None:
            st.info("No text id is available in this dataset.")
        else:
            texts = sorted(active[text_col].dropna().astype(str).unique())
            scope_text = panel_field(
                st,
                "selectbox",
                "Text",
                options=texts,
                key=f"{key_prefix}_scope_text",
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


def _prune_stale_fields(state, state_key: str, names: list[str]) -> None:
    """Drop field names the attached table no longer has from a stored picker
    selection — the house `controls._drop_stale_multi` pattern.

    Two states must stay apart. An **empty** stored list is the user clearing
    the picker, which leaves the table out of the bundle, so it is kept as is.
    A non-empty list that names **only** stale fields is what a replaced table
    leaves behind; Streamlit would filter it to `[]` and read it as that same
    omission, so it is removed and the picker starts again on every field.
    """
    stored = state.get(state_key)
    if not isinstance(stored, (list, tuple)) or not stored:
        return
    kept = [name for name in stored if name in names]
    if not kept:
        state.pop(state_key, None)
    elif list(stored) != kept:
        state[state_key] = kept


def _render_metadata_field_picker(key_prefix: str):
    """DATA-20 milestone 10 — which participant fields ride along in the bundle.

    Renders nothing when no table is attached, and returns ``None`` — "no
    restriction" — while every field is still selected, so an export made
    without touching this control is byte-identical to one made before the
    control existed.

    It lives with the export options rather than beside the table on the 🗂️ Data
    page because it is a decision about *this bundle*: the same attached table
    can reasonably ship its full detail to a collaborator and only a group label
    to a public repository.
    """
    import streamlit as st

    from scanpath_studio import metadata as md

    attached = md.active()
    if attached is None or not attached.fields:
        return None
    names = [field.name for field in attached.fields]
    labels = {field.name: field.label for field in attached.fields}
    state_key = f"{key_prefix}_meta_fields"
    _prune_stale_fields(st.session_state, state_key, names)
    chosen = panel_field(
        st,
        "multiselect",
        "Participant fields to include",
        options=names,
        default=names,
        format_func=lambda name: labels.get(name, name),
        key=state_key,
        persist_state="session",
        help="Participant fields to include. Reader ID is always kept.",
    )
    ordered = tuple(name for name in names if name in set(chosen))
    return None if len(ordered) == len(names) else ordered


def _render_trial_metadata_field_picker(key_prefix: str):
    """DATA-29 — which trial fields ride along, the twin of the picker above.

    Same contract in every respect: nothing rendered and ``None`` returned when
    no trial table is attached or while every field is still chosen, so an
    export made without touching it is unchanged.
    """
    import streamlit as st

    from scanpath_studio import metadata as md

    attached = md.active_trials()
    if attached is None or not attached.fields:
        return None
    names = [field.name for field in attached.fields]
    labels = {field.name: field.label for field in attached.fields}
    state_key = f"{key_prefix}_trial_meta_fields"
    _prune_stale_fields(st.session_state, state_key, names)
    chosen = panel_field(
        st,
        "multiselect",
        "Trial fields to include",
        options=names,
        default=names,
        format_func=lambda name: labels.get(name, name),
        key=state_key,
        persist_state="session",
        help="Trial fields to include. The trial key is always kept.",
    )
    ordered = tuple(name for name in names if name in set(chosen))
    return None if len(ordered) == len(names) else ordered


def _render_text_metadata_field_picker(key_prefix: str):
    """Which text fields ride along — third grain, twin of the two above.

    Same contract: nothing rendered and ``None`` returned when no text table
    is attached or while every field is still chosen, so an export made
    without touching it is unchanged.
    """
    import streamlit as st

    from scanpath_studio import metadata as md

    attached = md.active_texts()
    if attached is None or not attached.fields:
        return None
    names = [field.name for field in attached.fields]
    labels = {field.name: field.label for field in attached.fields}
    state_key = f"{key_prefix}_text_meta_fields"
    _prune_stale_fields(st.session_state, state_key, names)
    chosen = panel_field(
        st,
        "multiselect",
        "Text fields to include",
        options=names,
        default=names,
        format_func=lambda name: labels.get(name, name),
        key=state_key,
        persist_state="session",
        help="Text fields to include. The text key is always kept.",
    )
    ordered = tuple(name for name in names if name in set(chosen))
    return None if len(ordered) == len(names) else ordered


def _render_naming_options(st, combos: pd.DataFrame, key_prefix: str):
    """The compact **File naming** block: EXP-1's path pattern.

    Every pattern is validated and previewed against the first trial in scope as
    it's typed — finding a typo after a 200-trial render is the worst possible
    place to find it. Returns ``path_pattern``; an invalid pattern falls back to
    its default so a bad keystroke can't produce a broken zip.

    The title/caption pair used to live here too (EXP-2) but moved to the
    Scanpath rail's **📐 Figure & canvas** group (EXP-5), so it's visible on the
    live figure and not just at export time; `render_export_options` reads it
    back from there instead of keeping a second, possibly-diverging copy.
    """
    fields = _preview_fields(combos)
    available = ", ".join(
        f"`{{{k}}}`" for k in sorted(set(fields) | set(_PATTERN_EXTRA_FIELDS))
    )

    def _pattern_input(label: str, default: str, key: str, help_text: str) -> str:
        value = panel_field(
            st, "text_input", label, value=default, key=key, help=help_text
        )
        error = pattern_error(value, fields)
        if error:
            st.error(error)
            return default
        return value

    heading, fields_slot = st.columns([5, 1], vertical_alignment="bottom")
    heading.markdown("### File naming")
    with fields_slot.popover(
        "Fields", help="Placeholders available in the path pattern."
    ):
        st.markdown(available)
    path_pattern = _pattern_input(
        "File path pattern",
        DEFAULT_PATH_PATTERN,
        f"{key_prefix}_path_pattern",
        "Path inside the ZIP. Use `/` for folders and `{…}` placeholders.",
    )
    st.caption(
        "Example: `"
        + resolve_export_path(
            path_pattern, fields, artifact="figure", ext="png", used=set()
        )
        + "`"
    )
    return path_pattern


def render_export_options(
    st_module,
    combos: pd.DataFrame,
    key_prefix: str = "export",
    combos_all: pd.DataFrame | None = None,
    title_pattern: str = "",
    caption_pattern: str = "",
    selected_participant: str | None = None,
    selected_trial: str | None = None,
) -> ExportOptions:
    """Render the bulk-export options UI and return a populated ExportOptions.

    ``combos`` is the currently filtered trial pool; ``combos_all`` (when given)
    is the whole loaded dataset. Picking the "All" scope switches the scope
    picker — and the export itself — to ``combos_all`` so the trial filters
    are ignored. ``title_pattern``/``caption_pattern`` come from the Scanpath
    rail's **📐 Figure & canvas** → *Title* / *Caption* (EXP-5) —
    this panel no longer has its own copy of that setting.
    """
    st = st_module
    # No expander — the options are always displayed.
    with st.container():
        st.markdown("### Trials to Include")
        # The whole-dataset choice lives inside the scope radio.
        (
            scope,
            scope_pid,
            scope_trial,
            scope_text,
            export_unfiltered,
        ) = _render_scope_picker(
            st,
            combos,
            key_prefix,
            combos_all=combos_all,
            selected_participant=selected_participant,
            selected_trial=selected_trial,
        )

        # Figures are the headline artifact, so they lead with a single
        # multi-select of formats (pills) rather than a column of checkboxes.
        st.markdown("### Figure Formats")
        fig_formats = (
            panel_field(
                st,
                "pills",
                "Formats",
                options=["PDF", "SVG", "PNG", "HTML"],
                selection_mode="multi",
                default=["PDF"],
                key=f"{key_prefix}_figfmts",
                help="PDF/SVG are vector, PNG is raster, and HTML is interactive. "
                "The bundle draws PDF, SVG and PNG on the server with Chrome, "
                "Chromium or Edge; HTML needs no browser.",
            )
            or []
        )
        include_pdf = "PDF" in fig_formats
        include_svg = "SVG" in fig_formats
        include_png = "PNG" in fig_formats
        include_html = "HTML" in fig_formats
        # EXP-24: the bundle's static figures need a browser on the server,
        # which the current figure's PNG/SVG do not — said only when it is
        # missing, and only while one of those formats is picked.
        if note := missing_browser_note(include_pdf or include_svg or include_png):
            st.warning(note, icon=ICONS["warning"])
        # Only surface the scale stepper when PNG is on, and keep it narrow.
        # `width` does here what the old `st.columns([1, 3])` did: a 1–4 stepper
        # stretched across the whole field column reads as a text box. UX-69
        # dropped the columns because they nested inside the row's own.
        if include_png:
            png_scale = panel_field(
                st,
                "number_input",
                "PNG scale",
                min_value=1,
                max_value=4,
                value=2,
                width=140,
                key=f"{key_prefix}_scale",
                help="Higher values increase quality and file size.",
            )
        else:
            png_scale = int(st.session_state.get(f"{key_prefix}_scale", 2))

        st.markdown("### Also include")
        # VIZ-5: per-layer figure breakdown for publication editing.
        separable_layers = panel_field(
            st,
            "toggle",
            "Separable layers",
            value=False,
            key=f"{key_prefix}_layers",
            help="Export each visual layer as a separate file.",
        )
        # Layers are static vectors/rasters — HTML can't be split. When no
        # vector/raster format is picked, they fall back to SVG (which needs
        # Kaleido/Chrome, unlike the browser-free HTML the user chose), so warn.
        if separable_layers and not (include_png or include_svg or include_pdf):
            st.caption(
                f"{ICONS['warning']} Separable layers export as **SVG** (a static vector needing "
                "Chrome/Kaleido) — HTML figures can't be split. Pick SVG/PDF/PNG "
                "above to choose the layer format."
            )
        include_plot_config = panel_field(
            st,
            "toggle",
            "Plot config (JSON)",
            value=True,
            key=f"{key_prefix}_cfg",
            help="Include plot settings as JSON.",
        )
        include_annotations = panel_field(
            st,
            "toggle",
            "Annotations (JSON)",
            value=False,
            key=f"{key_prefix}_annotations",
            help="Include the exported trials' favorites, tags and notes as one "
            f"annotations.json — the file {ICONS['view_data']} Data Management → Annotations imports.",
        )
        tabular = (
            panel_field(
                st,
                "pills",
                "Tabular data",
                # The measure family is computed by the app, and held back
                # with the other computed measures.
                options=[
                    "Fixations",
                    "Raw gaze",
                    "Word measures",
                    *(["Full measure family"] if computed_measures_enabled() else []),
                ],
                selection_mode="multi",
                default=[],
                key=f"{key_prefix}_tabular",
                help="Choose the data tables to include. Word measures are the "
                "reading measures the dataset brought; none are computed.",
            )
            or []
        )
        include_fixations = "Fixations" in tabular
        include_raw_gaze = "Raw gaze" in tabular
        include_measures = "Word measures" in tabular
        include_analysis_family = "Full measure family" in tabular
        any_table = bool(tabular)
        if any_table:
            table_format = (
                panel_field(
                    st,
                    "segmented_control",
                    "Table format",
                    options=["csv", "parquet", "both"],
                    default="csv",
                    key=f"{key_prefix}_fmt",
                )
                or "csv"
            )
            combine_trials = panel_field(
                st,
                "toggle",
                "Combine all trials into one file",
                value=False,
                key=f"{key_prefix}_combine",
                help="Write each table once, with every exported trial stacked "
                "in it, under aggregate/ — instead of one file per trial.",
            )
        else:
            table_format = str(st.session_state.get(f"{key_prefix}_fmt", "csv"))
            combine_trials = bool(st.session_state.get(f"{key_prefix}_combine", False))

        metadata_fields = _render_metadata_field_picker(key_prefix)
        trial_metadata_fields = _render_trial_metadata_field_picker(key_prefix)
        text_metadata_fields = _render_text_metadata_field_picker(key_prefix)
        path_pattern = _render_naming_options(st, combos, key_prefix)
        if title_pattern or caption_pattern:
            st.caption(
                "Title and caption on the figure — set on the Scanpath rail's "
                f"**{ICONS['figure']} Figure & canvas** → *Title* / *Caption*, and "
                "applied here too."
            )

    return ExportOptions(
        include_png=include_png,
        include_svg=include_svg,
        include_pdf=include_pdf,
        include_html=include_html,
        include_plot_config=include_plot_config,
        include_annotations=include_annotations,
        include_fixations=include_fixations,
        include_raw_gaze=include_raw_gaze,
        include_measures=include_measures,
        include_analysis_family=include_analysis_family,
        combine_trials=combine_trials,
        separable_layers=separable_layers,
        table_format=table_format,
        png_scale=int(png_scale),
        path_pattern=path_pattern,
        title_pattern=title_pattern,
        caption_pattern=caption_pattern,
        # VIZ-36: this panel only runs inside the app, so the picker's label is
        # available; `pattern_fields` itself stays session-free.
        dataset_name=_session_dataset_name(),
        metadata_fields=metadata_fields,
        trial_metadata_fields=trial_metadata_fields,
        text_metadata_fields=text_metadata_fields,
        export_unfiltered=export_unfiltered,
        scope=scope,
        scope_participant=scope_pid,
        scope_trial=scope_trial,
        scope_text=scope_text,
    )


def _session_dataset_name() -> str:
    """The dataset picker's label, for the options UI only (VIZ-36).

    Guarded because `export` is imported headless by `api` and `cli`, where
    there is no session; the value only ever reaches `ExportOptions`, never
    `pattern_fields`, which takes it as an argument by design.
    """
    import streamlit as st

    try:
        return str(st.session_state.get("data_source_choice") or "")
    except Exception:
        return ""


def _scope_frame(
    combos: pd.DataFrame,
    scope: str,
    scope_participant: str | None,
    scope_trial: str | None,
    scope_text: str | None,
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


@dataclass(frozen=True)
class ComparisonSide:
    """One half of an exported comparison pair (CMP-8 §6).

    ``dataset`` is the corpus label — ``None`` for the active dataset, which is
    what every same-dataset comparison passes. ``participant`` / ``trial`` are
    the **real** ids, as the corpus spells them: the ``dataset · pid`` namespace
    exists only inside the figure's throwaway frames, and an exported table that
    used it would not match its own corpus.
    """

    participant: str
    trial: str
    words: pd.DataFrame
    fixations: pd.DataFrame
    dataset: str | None = None
    setup: dict | None = None

    @property
    def slug(self) -> str:
        return f"{_safe_id(self.participant)}__{_safe_id(self.trial)}"

    def stamped(self, side: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Both frames with a ``dataset`` column, so the pair's tables are readable.

        Two corpora can hold the same ``(participant_id, trial_id)``; without
        this column the rows in ``fixations.csv`` would be indistinguishable.
        ``side`` (CMP-22) also stamps a ``scanpath`` column, ``"A"`` or ``"B"``:
        B can now be A's own trial, whose rows match A's on every other column.
        """
        label = self.dataset or "(this dataset)"
        out = []
        for frame in (self.words, self.fixations):
            if frame is None or frame.empty:
                out.append(frame)
                continue
            stamped = frame.copy()
            stamped["dataset"] = label
            if side is not None:
                stamped["scanpath"] = side
            out.append(stamped)
        return out[0], out[1]

    def manifest(self) -> dict:
        return {
            "source": self.dataset,
            "participant": str(self.participant),
            "trial": str(self.trial),
            "setup": self.setup,
        }


def pair_export(
    fig,
    side_a: ComparisonSide,
    side_b: ComparisonSide,
    *,
    canvas_width: int,
    canvas_height: int,
    x_field: str,
    y_field: str,
    settings: dict,
    options: ExportOptions,
    status_callback: StatusCallback | None = None,
    column_names: Mapping[str, ColumnNames] | None = None,
) -> bytes:
    """Zip one comparison **pair** — figure, manifest, and both scanpaths' tables.

    ``column_names`` (DATA-66) is the active dataset's map per table. It names
    the tables' columns only when both scanpaths come from that dataset: a pair
    across two datasets shares no file names, so its tables keep the internal
    ones, which both datasets understand.

    CMP-8 §6. An exported cross-dataset figure is unreproducible on its own:
    nothing in the image records where B came from. The bundle writes the bulk
    exporter's per-trial shape for the pair instead of for one trial, and the
    ``datasets`` block in ``plot_config.json`` is what makes it reproducible —
    it names both sources, both trials, and both recording setups::

        <A>__vs__<B>/
        ├─ figure.<fmt>
        ├─ plot_config.json
        ├─ fixations.csv
        └─ measures.csv

    ``options`` is the ordinary `ExportOptions` — the pair is one more "trial
    folder" as far as the writer is concerned, so the formats, table format and
    figure toggles all mean what they already mean. Deliberately unchanged from
    bulk export: the tables stay **uncorrected** by drift correction (EXP-4 /
    VIZ-24), which the manifest records.
    """
    folder = f"{side_a.slug}__vs__{side_b.slug}"
    buffer = io.BytesIO()
    started = perf_counter()
    emit_status(
        status_callback,
        ExportStage.PREPARING,
        "Preparing the comparison pair…",
        started_at=started,
    )
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fmt in options.figure_formats():
            if fig is None:
                break
            width = int(getattr(fig.layout, "width", None) or canvas_width)
            height = int(getattr(fig.layout, "height", None) or canvas_height)
            if fmt == "html":
                data = fig.to_html(
                    include_plotlyjs=html_plotlyjs(options.html_self_contained),
                    full_html=True,
                    config={**PLOTLY_CONFIG},
                ).encode("utf-8")
            else:
                data = render_static_figure_bytes(
                    fig,
                    fmt=fmt,
                    width=width,
                    height=height,
                    scale=3 if fmt == "png" else 1,
                    status_callback=status_callback,
                )
            zf.writestr(f"{folder}/figure.{fmt}", data)

        words_a, fix_a = side_a.stamped("A")
        words_b, fix_b = side_b.stamped("B")
        maps = (
            {
                table: names
                for table, names in (column_names or {}).items()
                if names is not None and names.entries
            }
            if side_b.dataset in (None, side_a.dataset)
            else {}
        )
        # AN-32 / EXP-23: the measures each side's dataset brought.
        measures = [
            words.assign(scanpath=side)
            for side, words in (("A", words_a), ("B", words_b))
            if words is not None and not words.empty and brought_reading_measures(words)
        ]
        tables = {
            "fixations": pd.concat([fix_a, fix_b], ignore_index=True)
            if options.include_fixations
            else None,
            "words": pd.concat(measures, ignore_index=True)
            if options.include_measures and measures
            else None,
        }
        files = {"fixations": "fixations", "words": "measures"}
        written = {
            table: written_columns(shareable_frame(frame), maps[table])
            for table, frame in tables.items()
            if frame is not None and table in maps
        }
        for fmt in options.table_formats():
            for table, frame in tables.items():
                if frame is not None:
                    _write_table(
                        zf,
                        f"{folder}/{files[table]}.{fmt}",
                        frame,
                        fmt,
                        maps.get(table),
                    )
        if any(written.values()):
            zf.writestr(
                f"{folder}/columns.json",
                json.dumps(columns_manifest(written), indent=2),
            )

        config = _plot_config_dict(
            side_a.participant,
            side_a.trial,
            canvas_width,
            canvas_height,
            x_field,
            y_field,
            settings,
        )
        # The block that makes the pair reproducible — without it the figure
        # names two readers and no way to find either of them again.
        config["datasets"] = {"a": side_a.manifest(), "b": side_b.manifest()}
        zf.writestr(
            f"{folder}/plot_config.json", json.dumps(config, indent=2).encode("utf-8")
        )
    emit_status(
        status_callback,
        ExportStage.READY,
        "Comparison pair ready.",
        started_at=started,
    )
    return buffer.getvalue()


def _selected_metadata_columns(frame, fields: tuple[str, ...] | None):
    """``frame`` narrowed to ``fields`` (+ the reader id), or ``None`` to drop it.

    ``fields is None`` keeps every column — the default, so nothing changes for
    a caller that never heard of the opt-out. An **empty** tuple means the user
    cleared the picker: the table is left out of the bundle entirely, rather
    than shipped as a bare list of reader ids.
    """
    if frame is None or fields is None:
        return frame
    if not fields:
        return None
    keep = ["participant_id"] if "participant_id" in frame.columns else []
    keep += [name for name in fields if name in frame.columns and name not in keep]
    return frame[keep] if keep else None


def _selected_trial_metadata_columns(frame, fields: tuple[str, ...] | None):
    """``frame`` narrowed to ``fields`` (+ the trial key), or ``None`` to drop it.

    The trial twin of :func:`_selected_metadata_columns`. The key it always
    keeps is whichever the table was attached with — ``trial_id`` alone, or
    ``participant_id`` beside it — because a trial table shipped without its
    key cannot be joined back to anything.
    """
    if frame is None or fields is None:
        return frame
    if not fields:
        return None
    keep = [name for name in ("participant_id", "trial_id") if name in frame.columns]
    keep += [name for name in fields if name in frame.columns and name not in keep]
    return frame[keep] if keep else None


def _selected_text_metadata_columns(frame, fields: tuple[str, ...] | None):
    """``frame`` narrowed to ``fields`` (+ the text key), or ``None`` to drop it.

    The text twin of :func:`_selected_metadata_columns`/
    :func:`_selected_trial_metadata_columns` — a text table shipped without
    its key cannot be joined back to anything.
    """
    if frame is None or fields is None:
        return frame
    if not fields:
        return None
    keep = ["text_id"] if "text_id" in frame.columns else []
    keep += [name for name in fields if name in frame.columns and name not in keep]
    return frame[keep] if keep else None


def _rows_in_scope(
    frame,
    *,
    pairs: set[tuple[str, str]],
    texts: set[str],
    grain: str,
):
    """``frame``'s rows about what the bundle exports, or ``None`` when none are.

    A bundle's metadata describes only its own readers, trials and texts:
    ``grain`` ``"participant"`` keeps the readers in ``pairs``, ``"trial"`` the
    readings — by the (reader, trial) pair when the table has a reader column,
    else by trial id — and ``"text"`` the texts in ``texts``. Ids compare as
    text, as the metadata module matches them. A table with no key column, or
    no matching row, is left out rather than shipped whole.
    """
    if frame is None or frame.empty:
        return None
    if grain == "participant":
        if "participant_id" not in frame.columns:
            return None
        mask = frame["participant_id"].astype(str).isin({p for p, _ in pairs})
    elif grain == "trial":
        if "trial_id" not in frame.columns:
            return None
        if "participant_id" in frame.columns:
            keys = pd.Series(
                list(
                    zip(
                        frame["participant_id"].astype(str),
                        frame["trial_id"].astype(str),
                        strict=True,
                    )
                ),
                index=frame.index,
                dtype=object,
            )
            mask = keys.isin(pairs)
        else:
            mask = frame["trial_id"].astype(str).isin({t for _, t in pairs})
    else:
        if "text_id" not in frame.columns:
            return None
        mask = frame["text_id"].astype(str).isin(texts)
    kept = frame[mask]
    return None if kept.empty else kept


def _unit_text_ids(combo_row: dict, *frames: pd.DataFrame) -> set[str]:
    """Every text id one exported reading carries — its combo row's, and the
    ``unique_text_id`` / ``text_id`` values in its own rows — as text."""
    found: set[str] = set()
    value = combo_row.get("text_id")
    if value is not None and not pd.isna(value):
        found.add(str(value))
    for frame in frames:
        if frame is None or frame.empty:
            continue
        for column in ("unique_text_id", "text_id"):
            if column in frame.columns:
                found.update(frame[column].dropna().astype(str).unique())
    return found


def _session_text_metadata():
    """The attached text table, when running inside the app.

    Handed over on a private session key for the same reason its two
    siblings are: the frame must not reach the bulk-export cache signature.
    """
    try:
        import streamlit as st

        return st.session_state.get("_export_text_metadata")
    except Exception:  # no script run context (API, CLI)
        return None


def _session_trial_metadata():
    """The attached trial table, when running inside the app (DATA-29).

    Handed over on a private session key for the same reason its participant
    twin is: the frame must not reach the bulk-export cache signature.
    """
    try:
        import streamlit as st

        return st.session_state.get("_export_trial_metadata")
    except Exception:  # no script run context (API, CLI)
        return None


def _session_participant_metadata():
    """The attached participant table, when running inside the app (DATA-20).

    Handed over through session state rather than through ``settings`` so the
    frame never reaches the bulk-export cache signature, which stringifies the
    settings dict and would truncate a long table into a colliding key. Returns
    ``None`` headlessly, where callers pass the frame in ``settings`` instead.
    """
    try:
        import streamlit as st

        return st.session_state.get("_export_participant_metadata")
    except Exception:  # no script run context (API, CLI)
        return None


#: `index.csv`'s columns, in order.
INVENTORY_COLUMNS = (
    "path",
    "artifact",
    "format",
    "participant_id",
    "trial_id",
    "screen_id",
    "status",
    "note",
)


def _write_inventory(zf: zipfile.ZipFile, inventory: list[dict]) -> None:
    """Write ``index.csv``: one row per file in the bundle, plus each requested
    file that failed and each reading skipped. ``status`` is ``written``,
    ``failed`` or ``skipped``; a file type nobody asked for has no row."""
    frame = pd.DataFrame(inventory, columns=list(INVENTORY_COLUMNS))
    zf.writestr("index.csv", frame.to_csv(index=False))


def export_units(
    combos: pd.DataFrame,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    raw_gaze: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per **screen export unit**: each trial in ``combos``, or each of
    its screens when it is a multipart reading. ``combos`` is already scoped.
    """
    rows: list[dict] = []
    for combo in combos.to_dict("records"):
        participant, trial = combo["participant_id"], combo["trial_id"]
        parent_words = extract_trial(words, participant, trial)
        parent_fixations = extract_trial(fixations, participant, trial)
        screens = part_catalog(parent_words, parent_fixations)
        if (
            screens.empty
            and parent_words.empty
            and parent_fixations.empty
            and raw_gaze is not None
            and SCREEN_ID in raw_gaze.columns
        ):
            # VIZ-45, as `api._select_part` decides it: a trial recorded as raw
            # gaze alone takes its screens from its samples, so each screen's
            # coordinate space is exported on its own instead of pooled.
            screens = part_catalog(extract_trial(raw_gaze, participant, trial))
        if screens.empty:
            rows.append(combo)
        else:
            for screen in screens.to_dict("records"):
                rows.append({**combo, **screen})
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class ExportPlan:
    """What a bundle will hold, worked out before it is built.

    ``layer_files`` is a ceiling: a screen writes one file per layer it
    actually draws, which is only known once its figure is built.
    """

    trials: int
    units: int
    figure_files: int
    layer_files: int


def apply_export_scope(combos: pd.DataFrame, options: ExportOptions) -> pd.DataFrame:
    """``combos`` narrowed to ``options``' scope, as :func:`bulk_export` does."""
    return _apply_scope(combos, options)


def plan_export(
    combos: pd.DataFrame,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    options: ExportOptions,
    raw_gaze: pd.DataFrame | None = None,
) -> ExportPlan:
    """The trial, screen and figure-file counts :func:`bulk_export` will
    produce for these inputs and ``options``."""
    scoped = _apply_scope(combos, options)
    units = count_export_units(scoped, words, fixations, raw_gaze)
    return plan_from_counts(len(scoped), units, options)


def count_export_units(
    combos: pd.DataFrame,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    raw_gaze: pd.DataFrame | None = None,
) -> int:
    """``len(export_units(...))`` — without walking every trial when no frame
    carries screens, the common case, where each trial is one unit."""
    if not any(
        frame is not None and SCREEN_ID in frame.columns
        for frame in (words, fixations, raw_gaze)
    ):
        return len(combos)
    return len(export_units(combos, words, fixations, raw_gaze))


def plan_from_counts(trials: int, units: int, options: ExportOptions) -> ExportPlan:
    """:class:`ExportPlan` for known trial and unit counts — the formats'
    multiplication, apart from the (slower) unit expansion."""
    return ExportPlan(
        trials=trials,
        units=units,
        figure_files=units * len(options.figure_formats()),
        layer_files=units * len(SCANPATH_LAYER_ORDER) * len(options.layer_formats()),
    )


def describe_plan(plan: ExportPlan) -> str:
    """One line for the panel: what Build export is about to write."""

    def plural(n: int, word: str) -> str:
        return f"{n:,} {word}{'' if n == 1 else 's'}"

    readings = plural(plan.trials, "trial")
    if plan.units != plan.trials:
        readings += f" ({plural(plan.units, 'screen')})"
    parts = []
    if plan.figure_files:
        parts.append(plural(plan.figure_files, "figure file"))
    if plan.layer_files:
        parts.append(f"up to {plural(plan.layer_files, 'layer file')}")
    if not parts:
        return f"Exports {readings}."
    return f"Exports {readings}: {' and '.join(parts)}."


def _package_version() -> str:
    from scanpath_studio import __version__

    return __version__


def _scope_lines(
    options: ExportOptions, combos: pd.DataFrame, units: pd.DataFrame
) -> list[str]:
    """The README's *Scope* section: which readings the bundle was built from."""
    if options.scope == "trial":
        chosen = (
            f"one trial (participant {options.scope_participant}, "
            f"trial {options.scope_trial})"
        )
    elif options.scope == "participant":
        chosen = f"one participant ({options.scope_participant})"
    elif options.scope == "text":
        chosen = f"one text ({options.scope_text})"
    elif options.export_unfiltered:
        chosen = "the whole dataset, ignoring the trial filters"
    else:
        chosen = "the trials passing the trial filters"
    lines = []
    if options.dataset_name:
        lines.append(f"- Dataset: {options.dataset_name}")
    lines += [
        f"- Readings: {chosen}",
        f"- {len(combos):,} trial(s), {len(units):,} screen export unit(s)",
    ]
    return lines


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
    raw_gaze: pd.DataFrame | None = None,
    progress_callback=None,
    status_callback: StatusCallback | None = None,
    metadata_rows_for=None,
    annotation_records: list[dict] | None = None,
    annotation_dataset: str | None = None,
    column_names: Mapping[str, ColumnNames] | None = None,
) -> tuple[bytes, ExportProgress]:
    """Build a zip archive of selected artifacts and return its bytes.

    ``column_names`` (DATA-66) is the dataset's map per table
    (``{"fixations": …, "words": …, "raw_gaze": …}``): each table is written
    with the columns its file named under those names, the README's data
    dictionary says where every column came from, and a ``columns.json``
    records the map; patterns accept either name. Without it (headless
    callers, until the API carries maps) the tables keep the internal names.

    ``metadata_rows_for(participant, trial, text_id)`` (EXP-22) returns a
    trial's metadata-table rows for ``{table.field}`` patterns — the app passes
    ``metadata.pattern_rows``; headless callers have no attached tables.

    ``annotation_records`` (UX-179) are the annotations to write as
    ``annotations.json`` when ``options.include_annotations`` is set, in
    ``annotations.current_records()``'s shape; only those on the exported
    trials go in. The app passes the session's; headless callers have none.
    ``annotation_dataset`` is the dataset they were made on, which the file
    names (annotations file schema 3, DATA-48).

    progress_callback (if given) is invoked with an ExportProgress after every
    trial so the UI can update a progress bar.
    """
    combos = _apply_scope(combos, options)
    maps = {
        table: names
        for table, names in (column_names or {}).items()
        if names is not None and names.entries
    }
    every_table = across_tables(maps)
    # Each table's columns as written, decided once from the whole table so
    # every per-trial file of it has the same columns — and what `columns.json`
    # and the README then describe.
    whole = {
        table: shareable_frame(frame)
        for table, frame in (
            ("fixations", fixations),
            ("words", words),
            ("raw_gaze", raw_gaze),
        )
        if table in maps and frame is not None and not frame.empty
    }
    hidden = {
        table: maps[table].redundant_aliases(frame) for table, frame in whole.items()
    }

    def names_for(artifact: str) -> tuple[ColumnNames, set[str] | None]:
        """The map an artifact is written with, and the aliases it leaves out:
        its own table's for the three tables, only the ids for a derived one."""
        table = _ARTIFACT_TABLE.get(artifact)
        if table in maps:
            return maps[table], hidden.get(table)
        return every_table.identity(), None

    units = export_units(combos, words, fixations, raw_gaze)
    progress = ExportProgress(total_trials=len(units))
    started = perf_counter()
    emit_status(
        status_callback,
        ExportStage.PREPARING,
        "Preparing trials and export manifest…",
        started_at=started,
    )
    buf = io.BytesIO()
    zf = zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED)
    # The bundle's inventory, written last as `index.csv`: every file in it at
    # its actual path, and every requested file that failed, with the reading
    # and screen it belongs to.
    inventory: list[dict] = []

    def _inventory(path, artifact, status, unit=None, note="", fmt=None):
        inventory.append(
            {
                "path": path,
                "artifact": artifact,
                "format": PurePosixPath(path).suffix.lstrip(".")
                if fmt is None
                else fmt,
                "participant_id": (unit or {}).get("participant_id", ""),
                "trial_id": (unit or {}).get("trial_id", ""),
                "screen_id": (unit or {}).get("screen_id", ""),
                "status": status,
                "note": note,
            }
        )

    # EXP-23: each table's per-trial frames, stacked into `aggregate/all_<table>`
    # when the tables are combined. The family's words + fixations are kept
    # either way, for the reader summary, which only exists across trials.
    combined: dict[str, list[pd.DataFrame]] = {}
    family_words: list[pd.DataFrame] = []
    family_fixations: list[pd.DataFrame] = []
    # AN-32 / EXP-23: the export writes the reading measures the dataset
    # brought and computes none — so with none, the word tables are left out
    # and the README says why.
    measures_wanted = options.include_measures or options.include_analysis_family
    brought = brought_reading_measures(words)
    # What the bundle's own tables are written as, for its README and its
    # `columns.json`: only the tables it writes.
    exported = {
        "fixations": options.include_fixations or options.include_analysis_family,
        "words": measures_wanted and bool(brought),
        "raw_gaze": options.include_raw_gaze,
    }
    written = {
        table: written_columns(frame, maps[table])
        for table, frame in whole.items()
        if exported[table]
    }
    measure_headers = {
        row["canonical"]: row["column"] for row in written.get("words", [])
    }

    readme_lines = [
        "# Bulk export",
        f"Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        "",
        f"Authors: {CITATION['authors']}",
        f"Tool: {CITATION['title']}",
        f"Version: {_package_version()}",
        f"DOI: https://doi.org/{CITATION['doi']}",
        "",
        "## Scope",
        *_scope_lines(options, combos, units),
        "",
        "## Layout",
        "- `index.csv` lists every file in this bundle — its path, what it is, "
        "its participant, trial and screen — and every requested file that "
        "failed (`status` = `failed`) or reading skipped (`skipped`). A file "
        "type that was not requested is not listed.",
        "- `per_trial/<participant>__<trial>/` holds artifacts for each trial.",
        "- Multipart parents add `screens/screen-001-<id>/` below that trial.",
        *(
            [
                "- `aggregate/` holds each table once, every trial in this run "
                "stacked in it (*Combine all trials into one file*)."
            ]
            if options.combine_trials and options.any_table()
            else (
                ["- `aggregate/` holds the reader summary, across every trial."]
                if options.include_analysis_family
                else []
            )
        ),
        *(
            [
                "- `annotations.json` holds the favorites, tags and notes on "
                "these trials; import it on the app's Data Management page → Annotations."
            ]
            if options.include_annotations and annotation_records
            else []
        ),
        "",
        "## Data dictionary",
        *(
            [
                "Columns keep the names they have in the dataset's own files. "
                "A column Scanpath Studio built, converted or computed keeps its "
                "internal name; `columns.json` maps every column below to its "
                "internal name, for scripts that work across datasets. Columns "
                "not listed are written under their own names. A table the app "
                "derives (a summary, the saccades) carries the dataset's ids under "
                "these names, and its own values under the app's.",
                *dictionary_lines(written, maps),
                *(
                    ["", "Reading measures in the word tables:"]
                    if measures_wanted
                    else []
                ),
            ]
            if any(written.values())
            else [
                "Canonical column names from the visualization tool:",
                "- participant_id, trial_id, text_id, word_id",
                "- screen_id, screen_index (multipart trials only)",
                "- x, y, width, height (word bounding boxes in screen px)",
                "- x, y, duration_ms, timestamp_ms (fixations)",
            ]
        ),
        *(
            [f"- {measure_headers.get(column, column)}" for column in brought]
            if brought
            else ["- (no reading measures — see below)"]
            if measures_wanted
            else []
        ),
        "",
        "## Reading measures",
        "The word tables carry the reading measures the dataset brought, as "
        "mapped on the app's Data Management page; Scanpath Studio computes none of them.",
        *(
            [
                "",
                "This dataset brought none, so the bundle has no word-measure "
                f"table. Map them on {ICONS['view_data']} Data Management → {ICONS['edit']} Edit dataset → Reading measures.",
            ]
            if measures_wanted and not brought
            else []
        ),
        "",
        f"Demo corpus note: {CITATION['corpus_note']}",
    ]
    zf.writestr("README.md", "\n".join(readme_lines))
    _inventory("README.md", "readme", "written")
    if any(written.values()):
        zf.writestr("columns.json", json.dumps(columns_manifest(written), indent=2))
        _inventory("columns.json", "columns", "written")
    if options.include_analysis_family:
        zf.writestr(
            "run_config.json",
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "settings": settings,
                    "preprocessing": settings.get("preprocessing", {}),
                },
                indent=2,
                default=str,
            ),
        )
        _inventory("run_config.json", "run_config", "written")

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
    # The readers, trials and texts the bundle actually holds — what its
    # metadata tables are narrowed to at the end.
    exported_pairs: set[tuple[str, str]] = set()
    exported_texts: set[str] = set()
    emit_status(
        status_callback,
        (
            ExportStage.STARTING_RENDERER
            if options.needs_kaleido()
            else ExportStage.ENCODING_WRITING
        ),
        (
            "Starting one shared Chrome/Kaleido renderer…"
            if options.needs_kaleido()
            else "Writing selected files…"
        ),
        started_at=started,
    )
    with _figure_renderer(options.needs_kaleido()) as render_figure:
        for combo in units.itertuples(index=False):
            # The cancel checkpoint (`progress.Cancelled`), between units so a
            # stopped build never leaves one half-written; a no-op headlessly.
            try:
                report_progress(
                    progress.finished_trials, progress.total_trials, unit="screens"
                )
            except BaseException:  # `progress.Cancelled`: close the zip, go
                zf.close()
                raise
            participant = combo.participant_id
            trial = combo.trial_id
            screen_id = getattr(combo, SCREEN_ID, None)
            screen_index = getattr(combo, SCREEN_INDEX, None)
            screen_slug = (
                f"screen-{int(screen_index):03d}-{_safe_id(screen_id)}"
                if screen_id is not None and pd.notna(screen_id)
                else ""
            )
            slug = f"{_safe_id(participant)}__{_safe_id(trial)}"
            if screen_slug:
                slug += f"__{screen_slug}"
            unit_ids = {
                "participant_id": str(participant),
                "trial_id": str(trial),
                "screen_id": str(screen_id) if screen_slug else "",
            }

            # Slice via the same str-normalized position index the live view uses
            # (utils.extract_trial), so the export selects *exactly* what the trial
            # picker shows — not a raw dtype-sensitive boolean mask that can silently
            # miss rows the view finds.
            trial_words = extract_trial(words, participant, trial)
            trial_fix = extract_trial(fixations, participant, trial)
            trial_raw_gaze = (
                extract_trial(raw_gaze, participant, trial)
                if raw_gaze is not None and not raw_gaze.empty
                else pd.DataFrame()
            )
            if screen_slug:
                trial_words = extract_part(
                    trial_words, participant, trial, str(screen_id)
                )
                trial_fix = extract_part(trial_fix, participant, trial, str(screen_id))
                trial_raw_gaze = (
                    extract_part(trial_raw_gaze, participant, trial, str(screen_id))
                    if not trial_raw_gaze.empty and SCREEN_ID in trial_raw_gaze.columns
                    else pd.DataFrame()
                )

            # Skip only a genuinely empty trial (nothing to draw). The figure
            # builder renders from fixations alone (words optional — boxes/labels)
            # or from words alone (AOI layout), and the live view does too; so a
            # words-that-don't-join / fixations-only trial must still export
            # instead of being skipped with "empty data" (VIZ-5). VIZ-45: and
            # a trial recorded as raw gaze alone is drawn from its samples.
            if trial_words.empty and trial_fix.empty and trial_raw_gaze.empty:
                progress.finished_trials += 1
                progress.trials_skipped += 1
                progress.errors.append(f"{slug}: empty data, skipped")
                _inventory("", "reading", "skipped", unit_ids, "no data", fmt="")
                if progress_callback:
                    progress_callback(progress)
                continue

            exported_pairs.add((str(participant), str(trial)))
            exported_texts.update(
                _unit_text_ids(combo._asdict(), trial_words, trial_fix, trial_raw_gaze)
            )

            # A screen's own canvas, for its figure and its plot config alike.
            unit_canvas = (
                screen_canvas_size(trial_words)
                or screen_canvas_size(trial_fix)
                or screen_canvas_size(trial_raw_gaze)
            )
            unit_width = int(unit_canvas[0] if unit_canvas else canvas_width)
            unit_height = int(unit_canvas[1] if unit_canvas else canvas_height)

            # EXP-1/EXP-2: everything this trial's paths, title and caption can
            # substitute — its combo row plus counts and the settings summary.
            fields = pattern_fields(
                participant,
                trial,
                trial_words,
                trial_fix,
                settings,
                combo_row=combo._asdict(),
                dataset_name=options.dataset_name,
                column_names=every_table,
                metadata_rows=(
                    metadata_rows_for(
                        participant, trial, combo._asdict().get("text_id")
                    )
                    if metadata_rows_for is not None
                    else None
                ),
            )

            def _path(
                artifact: str, ext: str, _f=fields, _slug=screen_slug, reserve=True
            ) -> str:
                # `reserve=False` names a file that failed: the path it would
                # have had, for the inventory, without taking it from the next.
                if _slug:
                    artifact = f"screens/{_slug}/{artifact}"
                return resolve_export_path(
                    options.path_pattern,
                    _f,
                    artifact=artifact,
                    ext=ext,
                    used=used_paths if reserve else set(used_paths),
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
                emit_status(
                    status_callback,
                    ExportStage.RASTERIZING,
                    f"Rendering trial {progress.finished_trials + 1}/{progress.total_trials}…",
                    started_at=started,
                    completed=progress.finished_trials,
                    total=progress.total_trials,
                )
                fig = None
                try:
                    # EXP-4 / VIZ-24: apply the PRE-3 drift correction to the
                    # figure's fixations (a no-op when "Off"), so the batch
                    # matches the corrected figure on screen. `trial_fix` itself
                    # stays uncorrected — the tables below export the recording.
                    fig_fix, connector_y = _drift_corrected_for_figure(
                        trial_fix, trial_words, settings
                    )
                    render_values = {
                        name: settings[name]
                        for name in STATIC_FIGURE_OPTIONS
                        if name in settings
                    }
                    render_settings = FigureSettings.from_mapping(
                        render_values,
                        canvas_width=unit_width,
                        canvas_height=unit_height,
                        base_font_size=int(base_font_size),
                        font_family=font_family,
                        x_field=x_field,
                        y_field=y_field,
                        show_connectors=connector_y is not None,
                        connector_y=connector_y,
                        # A corrected figure colours by line, exactly as the
                        # on-screen static path forces it (tabs.py PRE-3
                        # overrides) — else the batch differs in colouring.
                        color_by_line=bool(settings.get("color_by_line", False))
                        or fig_fix is not trial_fix,
                    )
                    # VIZ-45: the trial's own samples, as the live figure
                    # gets them (the layer self-gates on `show_raw_gaze`).
                    fig = make_scanpath_figure(
                        trial_words,
                        fig_fix,
                        settings=render_settings,
                        raw_gaze=trial_raw_gaze if not trial_raw_gaze.empty else None,
                    )
                    # EXP-2: stamp the title/caption BEFORE measuring the output
                    # size — the bands grow the figure, and rendering at the
                    # pre-title size would crop them off.
                    annotate_figure(fig, title=title, caption=caption)
                except Exception as exc:
                    fig = None
                    # Its formats, and its layer set when one was asked for.
                    progress.figures_failed += len(figure_formats) + bool(layer_formats)
                    progress.errors.append(f"{slug}: figure export failed ({exc})")
                    for fmt in figure_formats:
                        _inventory(
                            _path("figure", fmt, reserve=False),
                            "figure",
                            "failed",
                            unit_ids,
                            str(exc),
                        )
                    if layer_formats:
                        _inventory("", "layers", "failed", unit_ids, str(exc), fmt="")
                # EXP-24: each format on its own, so a missing browser costs the
                # PNG/SVG/PDF and still leaves the trial's HTML in the zip.
                if fig is not None:
                    # Render at the figure's own fitted size (not the raw
                    # monitor canvas) so the exported reading text matches the
                    # on-screen scale.
                    out_w = int(fig.layout.width or unit_width)
                    out_h = int(fig.layout.height or unit_height)
                    for fmt in figure_formats:
                        try:
                            if fmt == "html":
                                # Browser-free + interactive; no Kaleido needed.
                                data = fig.to_html(
                                    include_plotlyjs=html_plotlyjs(
                                        options.html_self_contained
                                    ),
                                    full_html=True,
                                    config={**PLOTLY_CONFIG},
                                ).encode("utf-8")
                            else:
                                scale = options.png_scale if fmt == "png" else 1
                                data = render_figure(fig, fmt, out_w, out_h, scale)
                            path = _path("figure", fmt)
                            zf.writestr(path, data)
                        except Exception as exc:
                            progress.figures_failed += 1
                            progress.errors.append(
                                f"{slug}: {fmt.upper()} figure export failed ({exc})"
                            )
                            _inventory(
                                _path("figure", fmt, reserve=False),
                                "figure",
                                "failed",
                                unit_ids,
                                str(exc),
                            )
                            continue
                        _inventory(path, "figure", "written", unit_ids)
                        progress.bytes_written += len(data)
                        progress.figures_written += 1

                # VIZ-5: per-layer breakdown into `layers/<layer>.<fmt>` — each a
                # copy of the figure with only one layer's elements, same
                # size/ranges so they register when stacked in Illustrator. Kept in
                # its own try so a layer-render failure is reported as such and
                # doesn't get misattributed to the combined figure (which may have
                # already been written above).
                if layer_formats and fig is not None:
                    try:
                        out_w = int(fig.layout.width or unit_width)
                        out_h = int(fig.layout.height or unit_height)
                        for layer_name, layer_fig in split_scanpath_layers(fig).items():
                            for fmt in layer_formats:
                                scale = options.png_scale if fmt == "png" else 1
                                data = render_figure(
                                    layer_fig, fmt, out_w, out_h, scale
                                )
                                path = _path(f"layers/{layer_name}", fmt)
                                zf.writestr(path, data)
                                _inventory(
                                    path, f"layer:{layer_name}", "written", unit_ids
                                )
                                progress.bytes_written += len(data)
                                progress.figures_written += 1
                    except Exception as exc:
                        progress.figures_failed += 1
                        progress.errors.append(f"{slug}: layer export failed ({exc})")
                        _inventory("", "layers", "failed", unit_ids, str(exc), fmt="")

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
                    unit_width,
                    unit_height,
                    x_field,
                    y_field,
                    settings,
                    screen_id=str(screen_id) if screen_slug else None,
                    drift_applied=drift_applied,
                )
                # EXP-2: the title/caption are part of how the figure looked, so
                # the manifest records them verbatim alongside the settings.
                cfg["figure_text"] = {"title": title, "caption": caption}
                # VIZ-50: the trial's samples, and whether they were recorded —
                # the bundled demo's are synthesized, which its figure and its
                # raw-gaze table cannot say for themselves.
                if not trial_raw_gaze.empty:
                    cfg["raw_gaze"] = {
                        "points": len(trial_raw_gaze),
                        "synthesized": bool(settings.get("raw_gaze_synthesized")),
                    }
                data = json.dumps(cfg, indent=2).encode("utf-8")
                path = _path("plot_config", "json")
                zf.writestr(path, data)
                _inventory(path, "plot_config", "written", unit_ids)
                progress.bytes_written += len(data)

            # AN-32 / EXP-23: the word table *is* the measures table — it carries
            # what the dataset brought, and nothing is computed. A trial with no
            # words, or a dataset that brought no measures, writes none.
            per_trial_measures = (
                trial_words
                if measures_wanted and brought and not trial_words.empty
                else None
            )
            family = {}
            if options.include_analysis_family:
                measured = trial_words
                analysis_fix = (
                    enrich_fixations(
                        assign_fixations_to_words(trial_fix, trial_words), trial_words
                    )
                    if not trial_fix.empty and not trial_words.empty
                    else trial_fix
                )
                family = {
                    "fixations": analysis_fix,
                    "word_measures": per_trial_measures,
                    "saccades": saccade_table(
                        analysis_fix,
                        pixels_per_degree=settings.get("pixels_per_degree"),
                        raw_gaze=trial_raw_gaze,
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

            # The family's word-enriched fixations and its word_measures stand
            # in for the plain Fixations / Word measures files (EXP-15: two
            # members with one name, and a reader keeps only one of them).
            tables = {
                "fixations": trial_fix
                if options.include_fixations and not options.include_analysis_family
                else None,
                "raw_gaze": trial_raw_gaze if options.include_raw_gaze else None,
                "measures": per_trial_measures
                if options.include_measures and not options.include_analysis_family
                else None,
                **family,
            }
            tables = {
                artifact: table
                for artifact, table in tables.items()
                if table is not None and not table.empty
            }
            if options.combine_trials:
                for artifact, table in tables.items():
                    combined.setdefault(artifact, []).append(table)
            else:
                for fmt in options.table_formats():
                    for artifact, table in tables.items():
                        path = _path(artifact, fmt)
                        progress.bytes_written += _write_table(
                            zf, path, table, fmt, *names_for(artifact)
                        )
                        _inventory(path, artifact, "written", unit_ids)
            if options.include_analysis_family:
                family_words.append(measured)
                family_fixations.append(family["fixations"])

            progress.finished_trials += 1
            if progress_callback:
                progress_callback(progress)
            emit_status(
                status_callback,
                ExportStage.ENCODING_WRITING,
                f"Wrote trial {progress.finished_trials}/{progress.total_trials}…",
                started_at=started,
                completed=progress.finished_trials,
                total=progress.total_trials,
            )

    # A reader summary has no per-trial form, so it is written across the
    # exported trials whether or not the tables are combined.
    if options.include_analysis_family and family_words:
        summary = reader_summary_table(
            pd.concat(family_words, ignore_index=True),
            pd.concat(family_fixations, ignore_index=True),
        )
        if not summary.empty:
            combined["reader_summary"] = [summary]
    stacked = {
        artifact: pd.concat(frames, ignore_index=True)
        for artifact, frames in combined.items()
    }
    for fmt in options.table_formats():
        for artifact, table in stacked.items():
            path = f"aggregate/all_{artifact}.{fmt}"
            progress.bytes_written += _write_table(
                zf, path, table, fmt, *names_for(artifact)
            )
            _inventory(path, artifact, "written")
    # DATA-20: the participant table travels as its own per-grain table rather
    # than as columns smeared across the trial files — which is what keeps a
    # reader attribute distinguishable from a per-fixation measurement on the
    # way out, exactly as it is on the way in. Whenever one is attached, narrowed
    # to `options.metadata_fields` (milestone 10's per-field opt-out; `None` is
    # every field). The frame is handed over out-of-band (the settings dict
    # carries only its fingerprint, so the bulk-export cache signature stays
    # honest — see the note in `tabs._render_export_panel`). API/CLI callers can
    # pass the frame in `settings` directly, which still works.
    participant_metadata = (settings or {}).get("participant_metadata")
    if participant_metadata is None:
        participant_metadata = _session_participant_metadata()
    participant_metadata = _rows_in_scope(
        _selected_metadata_columns(participant_metadata, options.metadata_fields),
        pairs=exported_pairs,
        texts=exported_texts,
        grain="participant",
    )
    if participant_metadata is not None and not participant_metadata.empty:
        for fmt in options.table_formats():
            path = f"metadata/participants.{fmt}"
            progress.bytes_written += _write_table(zf, path, participant_metadata, fmt)
            _inventory(path, "participant_metadata", "written")
    # DATA-29: and the trial table beside it, on the same terms — its own
    # per-grain file, keyed as it was attached, so a reading's attributes stay
    # distinguishable from the per-fixation measurements of that reading.
    trial_metadata = (settings or {}).get("trial_metadata")
    if trial_metadata is None:
        trial_metadata = _session_trial_metadata()
    trial_metadata = _rows_in_scope(
        _selected_trial_metadata_columns(trial_metadata, options.trial_metadata_fields),
        pairs=exported_pairs,
        texts=exported_texts,
        grain="trial",
    )
    if trial_metadata is not None and not trial_metadata.empty:
        for fmt in options.table_formats():
            path = f"metadata/trials.{fmt}"
            progress.bytes_written += _write_table(zf, path, trial_metadata, fmt)
            _inventory(path, "trial_metadata", "written")
    # And the text table, the third grain — same reasoning again.
    text_metadata = (settings or {}).get("text_metadata")
    if text_metadata is None:
        text_metadata = _session_text_metadata()
    text_metadata = _rows_in_scope(
        _selected_text_metadata_columns(text_metadata, options.text_metadata_fields),
        pairs=exported_pairs,
        texts=exported_texts,
        grain="text",
    )
    if text_metadata is not None and not text_metadata.empty:
        for fmt in options.table_formats():
            path = f"metadata/texts.{fmt}"
            progress.bytes_written += _write_table(zf, path, text_metadata, fmt)
            _inventory(path, "text_metadata", "written")
    # UX-179: the exported trials' annotations, in the Data → Annotations file
    # format, so the bundle's notes can be imported back into the app.
    if options.include_annotations and annotation_records:
        from .annotations import records_in, records_to_store, serialize

        trials = zip(combos["participant_id"], combos["trial_id"], strict=True)
        kept = records_in(records_to_store(annotation_records), trials)
        if kept:
            data = serialize(records_to_store(kept), dataset=annotation_dataset).encode(
                "utf-8"
            )
            zf.writestr("annotations.json", data)
            _inventory("annotations.json", "annotations", "written")
            progress.bytes_written += len(data)
    emit_status(
        status_callback,
        ExportStage.FINALIZING,
        "Finalizing and compressing the zip archive…",
        started_at=started,
        completed=progress.finished_trials,
        total=progress.total_trials,
    )
    _write_inventory(zf, inventory)
    progress.files_written = len(zf.namelist())
    zf.close()
    buf.seek(0)
    result = buf.getvalue()
    emit_status(
        status_callback,
        ExportStage.READY,
        "Export archive is ready.",
        started_at=started,
        completed=progress.finished_trials,
        total=progress.total_trials,
    )
    return result, progress
