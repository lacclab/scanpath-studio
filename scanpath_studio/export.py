"""Configurable bulk export of figures and tabular data for filtered trials.

This module powers the "Bulk export" button. Users pick which artifacts they
want per trial (PNG, SVG, JSON plot config, fixations CSV/Parquet, per-word
measures CSV/Parquet), or each table once with every trial stacked in it
(*Combine all trials into one file*). Everything is packaged into a
single zip archive with a clean folder structure:

    bulk_export_<timestamp>.zip
    ├─ per_trial/
    │  ├─ <participant>__<trial>/
    │  │  ├─ figure.png
    │  │  ├─ figure.svg
    │  │  ├─ layers/                 (optional)
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
    └─ annotations.json          (optional)
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath
from time import perf_counter

import pandas as pd

from . import chart_axes, dataset_credit
from .aggregation import reader_summary_table, trial_summary_table
from .citation import CORPORA, CREDIT_LINE, cite, corpus_for, software_apa
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
    DEFAULT_CAPTION_COLOR,
    DEFAULT_CAPTION_FONT_SIZE,
    DEFAULT_PALETTE,
    DEFAULT_TITLE_FONT_SIZE,
    ICONS,
    PLOTLY_CONFIG,
    UNIFORM_COLOR_FIELD,
    computed_measures_enabled,
)
from .data import brought_reading_measures, shareable_frame, with_onset_provenance
from .export_dictionary import R_IMPORT, CsvDictionary
from .export_status import ExportStage, StatusCallback, emit_status
from .fields import panel_field
from .file_citation import stamp as stamp_citation
from .file_citation import stamp_html
from .illustration import illustration_reasons, resolve_label_reasons
from .measures import assign_fixations_to_words, enrich_fixations
from .multipart import (
    SCREEN_ID,
    SCREEN_INDEX,
    part_catalog,
    screen_canvas_size,
    screen_rows,
)
from .plot_config import render_plot_config
from .plots import (
    SCANPATH_LAYER_ORDER,
    STATIC_FIGURE_OPTIONS,
    FigureSettings,
    _plotly_literal,
    make_scanpath_figure,
    reading_stimulus_image,
    split_scanpath_layers,
    stimulus_image_settings,
)
from .preprocessing import (
    character_grid,
    cleaning_report,
    saccade_table,
    sentence_measures,
)
from .progress import report as report_progress
from .utils import extract_trial


def _local_stamp() -> str:
    """Now in this computer's local time, with its UTC offset said:
    ``2026-10-06 21:21:01 (UTC+03:00)``."""
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    return f"{now:%Y-%m-%d %H:%M:%S} (UTC{offset[:3]}:{offset[3:]})"


# --- A raster figure's print size --------------------------------------------
#: The units a print width is given in → millimetres per unit.
PRINT_UNITS = {"mm": 1.0, "in": 25.4}
#: The resolution a print width is drawn at when none is named.
DEFAULT_PRINT_DPI = 300
#: The print width and dpi every surface accepts: Export → Current figure's
#: boxes, a link or settings file (clamped), `render` and `save_figure` (refused
#: outside them).
PRINT_WIDTH_BOUNDS = (1.0, 2000.0)
PRINT_DPI_BOUNDS = (50, 2400)
#: What the app's Export → Current figure PNG is drawn at without a print width
#: (`tabs._PNG_EXPORT_SCALE`): three pixels per figure pixel.
SCREEN_PNG_SCALE = 3


def print_width_px(width: float, unit: str = "mm", dpi: int = DEFAULT_PRINT_DPI) -> int:
    """The pixel width of a raster figure ``width`` ``unit`` wide at ``dpi``:
    180 mm at 600 dpi is 4,252 px."""
    if unit not in PRINT_UNITS:
        raise ValueError(f"Unknown width unit {unit!r}; use 'mm' or 'in'.")
    if not width or width <= 0 or not dpi or dpi <= 0:
        raise ValueError("A print width and its dpi must both be positive.")
    low, high = PRINT_WIDTH_BOUNDS
    if not low <= float(width) <= high:
        raise ValueError(f"A print width must be {low:g}–{high:g} {unit}.")
    low, high = PRINT_DPI_BOUNDS
    if not low <= float(dpi) <= high:
        raise ValueError(f"A print dpi must be {low}–{high}.")
    return max(1, round(float(width) * PRINT_UNITS[unit] / 25.4 * float(dpi)))


def print_scale(
    figure_width: int, width: float, unit: str = "mm", dpi: int = DEFAULT_PRINT_DPI
) -> float:
    """The ``scale`` that draws a ``figure_width``-px figure ``width`` ``unit``
    wide at ``dpi`` (the height follows the figure's own aspect)."""
    return print_width_px(width, unit, dpi) / float(figure_width)


def png_save_kwargs(
    width: float | None, unit: str = "mm", dpi: int | None = None
) -> dict:
    """The `api.save_figure` keywords that write the PNG Export → *Current
    figure* writes: the print width at its dpi, else the screen size at
    `SCREEN_PNG_SCALE` — so Share → Code writes the same pixel size."""
    if not width:
        return {"scale": SCREEN_PNG_SCALE}
    return {f"width_{unit}": float(width), "dpi": int(dpi or DEFAULT_PRINT_DPI)}


def set_png_dpi(path, dpi: int) -> None:
    """Stamp ``dpi`` into a PNG's header (``pHYs``), so a layout program
    places it at its print size. The pixels are untouched."""
    from PIL import Image

    with Image.open(path) as image:
        image.load()
        image.save(path, format="PNG", dpi=(dpi, dpi))


# --- Customizable export paths -----------------------------------------------
# Names the tool chooses are rarely how a user organizes figures for a paper, so
# the path of every artifact is a *pattern* over the trial's own fields, and a
# batch can be dropped straight into an existing folder structure.
DEFAULT_PATH_PATTERN = "per_trial/{participant_id}__{trial_id}/{artifact}.{ext}"
# A figure pulled into a paper or a slide loses its provenance the moment it
# leaves the app, so it can carry its own title and caption. Same substitution
# as the path patterns; empty means "no title / no caption".
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
    # The exported trials' annotations (favorites, tags, notes) as one
    # `annotations.json` at the bundle root — the file 🗂️ Data → Annotations
    # exports and imports. Off by default: notes can be personal.
    include_annotations: bool = False
    include_fixations: bool = False
    # Each trial's raw (sample-level) gaze as its own table, written as
    # recorded — for a raw-gaze-only dataset it is the only recording there is.
    include_raw_gaze: bool = False
    # The word table with the reading measures the dataset *brought*. Export
    # computes none, as the Corpus Analysis page doesn't.
    include_measures: bool = False
    include_analysis_family: bool = False
    # Write each chosen table once, every exported trial stacked, as
    # `aggregate/all_<table>` — instead of one file per trial.
    combine_trials: bool = False
    # Also drop a per-layer breakdown of the figure (word boxes / fixations
    # / saccades / heatmap / labels / stimulus image) into `layers/` so each can be
    # restyled independently in Illustrator / Inkscape. Uses the selected vector /
    # raster formats (SVG when none was picked — the publication default).
    separable_layers: bool = False
    table_format: str = "csv"  # "csv" | "parquet" | "both"
    png_scale: int = 2
    # Where each artifact lands inside the zip. `{artifact}` / `{ext}` name the
    # file (figure / fixations / measures / plot_config / layer names); every
    # other placeholder comes from the trial.
    path_pattern: str = DEFAULT_PATH_PATTERN
    # An optional title + caption rendered into the exported image and
    # recorded in the per-trial manifest. Empty = off.
    title_pattern: str = ""
    caption_pattern: str = ""
    # What `{dataset_name}` substitutes to. The app fills it from the
    # dataset picker's label; a headless caller that says nothing gets "", so
    # the placeholder renders empty rather than erroring on a surface nobody is
    # watching.
    dataset_name: str = ""
    # Which columns of the attached participant table go into
    # `metadata/participants.*`. `None` is every field (the default, and what a
    # headless caller that knows nothing about this gets); a tuple is exactly
    # those, always alongside the reader id; an **empty** tuple leaves the table
    # out of the bundle. Reader attributes are the most re-identifying thing an
    # export can carry, so the opt-out has to be per field rather than
    # all-or-nothing.
    metadata_fields: tuple[str, ...] | None = None
    # The same per-field opt-out for the attached *trial* table, written to
    # `metadata/trials.*`. Kept as its own field rather than folded into
    # `metadata_fields` because the two tables are attached and cleared
    # independently, and because what is safe to ship differs by grain: a
    # reader attribute re-identifies a person, a trial attribute usually
    # describes the material.
    trial_metadata_fields: tuple[str, ...] | None = None
    # And the same opt-out for the attached *text* table, written to
    # `metadata/texts.*` — the third grain, same reasoning again.
    text_metadata_fields: tuple[str, ...] | None = None
    # HTML figures embed the Plotly library (opens offline, ~4.8 MB more per
    # file) instead of loading it from cdn.plot.ly when opened. Off by default:
    # the bundle's *Self-contained HTML* choice, shown while HTML is picked.
    html_self_contained: bool = False
    # When True, export operates on the whole loaded dataset, ignoring the
    # trial-filter funnel; the caller supplies the unfiltered frames.
    export_unfiltered: bool = False
    scope: str = "all"  # "all" | "trial" | "participant" | "text"
    scope_participant: str | None = None
    scope_trial: str | None = None
    scope_text: str | None = None
    # Which screens of a multipart trial go in, by `screen_id` — one id across
    # trials (OneStop's `Paragraph`, MultiplEYE's `page_1`). `None` is every
    # screen; a trial showing none of the chosen screens is left out.
    screens: tuple[str, ...] | None = None

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
        """Formats for the per-layer breakdown — the selected non-HTML
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
    # What the build produced, for the summary under it — every file in
    # the zip, and the figure files (combined figures and per-layer files)
    # written and failed, one per format per trial.
    files_written: int = 0
    figures_written: int = 0
    figures_failed: int = 0
    trials_skipped: int = 0
    retryable_figures: int = 0


@dataclass(frozen=True)
class ExportSummary:
    """How a finished bundle reads — ``level`` is ``"success"``, ``"warning"``
    (some of it failed) or ``"error"`` (figures were asked for and none was
    made), and ``expand_errors`` opens the error list for the last."""

    level: str
    message: str
    expand_errors: bool


#: Session key of the current figure's *Self-contained HTML* choice — the figure's
#: and the replay's HTML follow it; the bundle asks its own
#: (``<key_prefix>_html_self_contained``).
HTML_SELF_CONTAINED_KEY = "export_html_self_contained"


def html_plotlyjs(self_contained: bool) -> bool | str:
    """``to_html``'s ``include_plotlyjs`` for a downloaded HTML file: the
    library embedded (opens offline), or loaded from cdn.plot.ly when opened."""
    return True if self_contained else "cdn"


def missing_browser_note(static_formats: bool) -> str:
    """The bundle's browser prerequisite, when it is unmet, else ``""``.

    The bundle draws PNG, SVG and PDF through Kaleido on the server, which
    needs Chrome, Chromium or Edge there; the current figure's PNG and SVG are
    saved by the reader's own browser and need none. Saying so up front keeps a
    machine without a browser from building a zip of failures. Asked only when
    ``static_formats`` are picked.
    """
    if not static_formats:
        return ""
    from .animation_export import chrome_available

    if chrome_available():
        return ""
    return (
        "PNG, SVG and PDF bundle figures need Chrome, Chromium or Edge on the "
        "computer running Scanpath Studio, and none was found. Pick **HTML**, "
        "which needs no browser, or install one. The PNG and SVG downloads of the "
        "current figure use your own browser."
    )


def summarize_export(progress: ExportProgress, size_bytes: int) -> ExportSummary:
    """What a built bundle holds and what failed, in one line.

    A generic "Ready" over a zip whose figures all failed would read as a
    success, with the failures one click away in an expander. The line counts
    what was made and what wasn't; a build whose requested figures all failed
    is an error, with its list open. The zip stays downloadable either way —
    the files it does hold are good.
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
    """A one-line description of the settings that produced the figure."""
    layers = [
        name
        for name, key in (
            ("boxes", "show_words"),
            ("text", "show_word_labels"),
            ("fixations", "show_fixations"),
            ("saccades", "show_saccades"),
            ("heatmap", "show_heatmap"),
            ("raw gaze", "show_raw_gaze"),
        )
        if settings.get(key)
    ]
    parts = [f"layers: {', '.join(layers) or 'none'}"]
    color_by = settings.get("color_by")
    if color_by and color_by != UNIFORM_COLOR_FIELD:
        parts.append(f"color by {color_by}")
    palette = settings.get("palette", DEFAULT_PALETTE)
    if palette and palette != DEFAULT_PALETTE:
        parts.append(f"{palette} palette")
    return " · ".join(parts)


#: The fields that can hold *two* values at once, because an overlay
#: draws two readings into one frame. Each gains an ``_a`` / ``_b`` variant.
PAIRED_PATTERN_FIELDS = ("dataset_name", "participant_id", "trial_id", "text_id")

#: The tables a pattern can name a field of, as ``{table.field}``, and
#: the heading each gets in the *Available fields* list. The metadata tables
#: plus the two data tables' saved fields; a qualified name is what tells two
#: tables' ``font_size`` apart, and what keeps them out of the plain list.
TABLE_PATTERN_LABELS = {
    "participants": "Participants table",
    "trials": "Trials table",
    "texts": "Texts table",
    "fixations": "Fixations table",
    "words": "Words table",
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
    """``{table: {"table.field": value}}`` for one trial.

    ``metadata_rows`` is this trial's row of each attached metadata table
    (``metadata.pattern_rows``); the fixations and Words tables contribute their
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

    With ``column_names`` (the dataset's map), every field its file named is
    also reachable under that name — ``{RECORDING_SESSION_LABEL}`` and
    ``{participant_id}`` both work, so a pattern can be written in either
    vocabulary.

    The trial's own combo columns (participant, trial, text, conditions …) plus
    counts and the settings summary. Values are left raw here; path rendering
    sanitizes them, while titles and captions want them readable.

    **``dataset_name`` arrives as an argument, never read from here.** The app
    supplies the label shown in its picker. This function also runs headless under
    ``api.save_figure_layers`` and ``cli render``, where there is no session at
    all. Each caller supplies it.

    ``compare_row`` is the *other* reading in an overlay — two scanpaths in one
    frame, so a single ``{dataset_name}`` is ambiguous exactly where a title
    most wants to name both. Every field in :data:`PAIRED_PATTERN_FIELDS` gains
    an ``_a`` / ``_b`` variant, which are defined **always** (``_b`` empty when
    there is no second reading) so that a pattern written in compare mode still
    validates and renders on a single-trial figure instead of erroring on a
    surface the author cannot see.

    Every attached metadata table's fields and each data table's saved
    fields join as ``{table.field}`` (:func:`table_pattern_fields`) — qualified,
    so a trial table's ``font_size`` and a recorded ``font_size`` are both
    reachable, and none of the plain names above changes.
    """
    # The trial's row, less its bookkeeping (`_data_order`): a `_` column is the
    # app's, as `_saved_table_fields` already holds for the tables.
    fields: dict = {
        name: value
        for name, value in (combo_row or {}).items()
        if not str(name).startswith("_")
    }
    for table in table_pattern_fields(
        trial_words, trial_fixations, metadata_rows
    ).values():
        fields.update(table)
    if compare_row is None:
        settings = dict(settings)
        if trial_words.empty:
            settings.update(show_words=False, show_word_labels=False)
        if trial_fixations.empty:
            settings.update(show_fixations=False, show_saccades=False)
            if not settings.get("word_heatmap_col"):
                settings["show_heatmap"] = False
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
        + (
            f"Available: {', '.join('{' + k + '}' for k in sorted(known))}."
            if len(known) <= 25
            else f"{len(known)} fields are available; the app's Fields list shows them."
        )
    )


_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_WINDOWS_DEVICE = re.compile(
    r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³])", re.IGNORECASE
)
_WINDOWS_PATH_CHAR = re.compile(r'[<>:"|?*\x00-\x1f]')


def path_structure_error(pattern: str) -> str | None:
    """What is wrong with ``pattern``'s own text as a path inside the ZIP, or
    ``None``.

    The values put into ``{…}`` are sanitized one by one (:func:`render_pattern`),
    but the text around them is the pattern's: ``../{artifact}.{ext}`` would
    write a member outside the archive's root, and an empty pattern one with no
    name.
    Every member must be a relative path of named folders ending in a file
    name, so this refuses an empty pattern, a leading ``/`` or drive, a
    backslash (a separator to some unzip tools), and an empty, ``.`` or ``..``
    folder or file name. Checked before any figure is rendered, in the app and
    by :func:`bulk_export`.
    """
    text = str(pattern or "")
    probe = _PLACEHOLDER_RE.sub("x", text)
    if not probe.strip():
        return "The file path pattern is empty."
    if "\\" in probe:
        return (
            "Use `/` between folders. Some unzip tools read a backslash as a separator."
        )
    if probe.startswith("/") or _DRIVE_PREFIX.match(probe):
        return "The file path must be relative to the ZIP. Start it with a folder or file name."
    for part in probe.split("/"):
        if not part.strip():
            return "The file path has an empty folder or file name (`//`, or a trailing `/`)."
        if set(part) <= {"."}:
            return f"`{part}` can't be a folder or file name in the ZIP."
    return None


def _path_component(text: str) -> str:
    """One path segment, sanitized. ``.`` / ``..`` collapse so nothing escapes."""
    safe = _safe_id(text)
    return "_" if set(safe) <= {"."} else safe


def _portable_component(name: str) -> str:
    """Make a complete ZIP path component extractable on Windows as well."""
    name = _WINDOWS_PATH_CHAR.sub("_", name)
    stripped = name.rstrip(". ")
    name = stripped + "_" * (len(name) - len(stripped))
    if _WINDOWS_DEVICE.fullmatch(name.partition(".")[0].rstrip(" ")):
        return "_" + name
    return name


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


#: The tables a bundle can write once across every trial, as
#: `aggregate/all_<table>` — each per-trial table artifact, and the reader
#: summary, which has no per-trial form.
_AGGREGATE_TABLES = (
    "fixations",
    "raw_gaze",
    "measures",
    "word_measures",
    "saccades",
    "sentence_measures",
    "trial_summary",
    "characters",
    "cleaning_qa",
    "reader_summary",
)
#: The attached metadata tables, as `metadata/<grain>`.
_METADATA_TABLES = ("participants", "trials", "texts")


def bundle_member_names(options: ExportOptions | None = None) -> list[str]:
    """The paths a bulk export writes for itself, whichever trials it holds.

    Reserved before any trial's file is named (:class:`ArchiveNames`), so a
    path pattern can never give a trial's file one of them — the README, its
    ``CITATION.bib``, the ``index.csv`` inventory, ``columns.json``, ``run_config.json``,
    ``annotations.json``, the combined tables and the metadata tables, in each
    table format. ``options`` narrows the combined tables to the ones a run
    with them can write; without it, every name a bundle can have.
    """
    formats = options.table_formats() if options is not None else ["csv", "parquet"]
    if options is None or (options.combine_trials and options.any_table()):
        combined = _AGGREGATE_TABLES
    elif options.include_analysis_family:
        combined = ("reader_summary",)
    else:
        combined = ()
    names = [
        "README.md",
        "CITATION.bib",
        "index.csv",
        "columns.json",
        "read_csv.R",
        "run_config.json",
        "annotations.json",
    ]
    for fmt in formats:
        names += [f"aggregate/all_{table}.{fmt}" for table in combined]
        names += [f"metadata/{table}.{fmt}" for table in _METADATA_TABLES]
    return names


class ArchiveNames:
    """Every member name one ZIP has given out, so that no two collide.

    A bundle's own files are reserved up front (:func:`bundle_member_names`)
    and keep their names (:meth:`own`); a file the user's path pattern names
    takes the first free ``-2``, ``-3`` … variant of its name instead
    (:meth:`claim`) — so a pattern of ``README.md`` writes ``README-2.md``
    beside the README rather than a second ``README.md`` that hides it, and the
    inventory names the file it describes. Names compare without case, since
    unpacking on macOS or Windows merges ``README.md`` and ``readme.md`` into
    one file; and a file never takes a folder's name, nor a folder a file's,
    since the two cannot both be unpacked.
    """

    def __init__(self, reserved: Iterable[str] = ()) -> None:
        self._files: set[str] = set()
        self._folders: set[str] = set()
        self._reserved: set[str] = set()
        self._suffixes: dict[tuple[str, str, bool], int] = {}
        for path in reserved:
            self._take(path)
            self._reserved.add(path.casefold())

    def _take(self, path: str) -> None:
        key = path.casefold()
        self._files.add(key)
        parts = key.split("/")
        self._folders.update("/".join(parts[:end]) for end in range(1, len(parts)))

    def _free(self, parents: list[str], name: str, *, folder: bool) -> str:
        """``name`` under ``parents``, or its first free ``-N`` variant."""

        prefix = ("/".join(parents) + "/").casefold() if parents else ""

        def taken(candidate: str) -> bool:
            key = prefix + candidate.casefold()
            # A folder may be shared; only a file may not have its name.
            return key in self._files or (not folder and key in self._folders)

        if not taken(name):
            return name
        stem, dot, suffix = name.rpartition(".")
        base, tail = (stem, f".{suffix}") if dot and stem else (name, "")
        series = (prefix, name.casefold(), folder)
        n = self._suffixes.get(series, 2)
        while taken(f"{base}-{n}{tail}"):
            n += 1
        # Remember the candidate itself. A preview leaves it free, and a
        # disambiguated folder may be shared by subsequent files.
        self._suffixes[series] = n
        return f"{base}-{n}{tail}"

    def claim(self, path: str, *, record: bool = True) -> str:
        """``path``, made free of every name given out so far, and recorded.

        ``record=False`` only says what the name would be — for a file that
        failed, listed in the inventory without taking the name from the next.
        """
        parts = path.split("/")
        for index, name in enumerate(parts):
            parts[index] = self._free(
                parts[:index], name, folder=index < len(parts) - 1
            )
        path = "/".join(parts)
        if record:
            self._take(path)
        return path

    def own(self, path: str) -> str:
        """A bundle's own member: its reserved name, given out once.

        One that was not reserved is claimed like any other, so even a name
        missing from :func:`bundle_member_names` never becomes a duplicate.
        """
        key = path.casefold()
        if key in self._reserved:
            self._reserved.discard(key)
            return path
        return self.claim(path)


def resolve_export_path(
    pattern: str,
    fields: dict,
    *,
    artifact: str,
    ext: str,
    used: ArchiveNames,
    record: bool = True,
) -> str:
    """The zip path for one artifact, made unique among the names in ``used``.

    Two trials can render to the same path (a pattern that omits the trial id,
    say), and a pattern can name a file as one of the bundle's own
    (``README.md``). Writing both would put two entries at one name in the zip
    and silently lose one, so the later file gets a ``-2`` suffix instead
    (:class:`ArchiveNames`). ``used`` records the name unless ``record`` is
    false.
    """
    path = render_pattern(
        pattern,
        {**fields, "artifact": artifact, "ext": ext},
        as_path=True,
        multi_segment_fields=("artifact",),
    ).lstrip("/")
    portable = "/".join(_portable_component(part) for part in path.split("/"))
    return used.claim(portable, record=record)


# --- Titles and captions on the exported figure ------------------------------
# Sized bands rather than Plotly's automatic title spacing: the scanpath figure
# is equal-aspect (`scaleanchor`), so anything that eats into the plot area
# shrinks the WHOLE plot — and the true-to-scale word labels, computed for the
# un-shrunk size, then no longer match their boxes. Same constraint the animation
# transport controls hit; same fix: grow the figure by exactly what the band
# takes, so the plot region is untouched.
# The bands follow the text's size: at the default 20 px title and 13 px
# caption they are a 46 px band and 22 px lines.
_TITLE_BAND_PAD_PX = 26
_CAPTION_LINE_FACTOR = 22 / 13
_CAPTION_PAD_PX = 12
#: The credit line: small, grey, right-aligned in a band of its own at the
#: very bottom, below any caption.
_CREDIT_FONT_PX = 10
_CREDIT_COLOR = "#8a8a8a"
_CREDIT_BAND_PX = 18


def annotate_figure(
    fig,
    *,
    title: str = "",
    caption: str = "",
    title_font_size: float = DEFAULT_TITLE_FONT_SIZE,
    caption_font_size: float = DEFAULT_CAPTION_FONT_SIZE,
    caption_color: str = DEFAULT_CAPTION_COLOR,
    show_credit: bool = False,
) -> None:
    """Stamp ``title`` / ``caption`` onto ``fig`` in place, without shrinking it.

    The figure grows by the height of each band and its margin grows to match, so
    the plotting area — and therefore the true-to-scale text — is byte-identical
    to the untitled figure. Both are drawn as written: ``<b>`` in a title shows
    as ``<b>``, and only a real newline starts a new caption line. The sizes are
    in px; each band grows with its text. ``show_credit`` adds the
    ``citation.CREDIT_LINE`` in a small band of its own below everything else.
    """
    if not title and not caption and not show_credit:
        return
    margin = fig.layout.margin
    height = fig.layout.height
    if title:
        band = round(float(title_font_size)) + _TITLE_BAND_PAD_PX
        fig.layout.margin.t = (margin.t or 0) + band
        if height:
            height += band
            fig.layout.height = height
        fig.update_layout(
            title=dict(
                text=_plotly_literal(title),
                x=0.5,
                xanchor="center",
                y=1.0,
                yanchor="top",
                pad=dict(t=14),
                font=dict(size=int(title_font_size)),
            )
        )
    if caption:
        original_bottom = fig.layout.margin.b or 0
        line_px = round(float(caption_font_size) * _CAPTION_LINE_FACTOR)
        band = line_px * (caption.count("\n") + 1) + _CAPTION_PAD_PX
        fig.layout.margin.b = original_bottom + band
        if height:
            fig.layout.height = height + band
        # Anchored to the plot's bottom edge and pushed into the space just
        # added, so it never overlaps whatever already lived in that margin.
        fig.add_annotation(
            text=_plotly_literal(caption).replace("\n", "<br>"),
            xref="paper",
            yref="paper",
            x=0,
            y=0,
            xanchor="left",
            yanchor="top",
            yshift=-(original_bottom + _CAPTION_PAD_PX // 2),
            showarrow=False,
            align="left",
            font=dict(size=int(caption_font_size), color=caption_color),
        )
    if show_credit:
        original_bottom = fig.layout.margin.b or 0
        fig.layout.margin.b = original_bottom + _CREDIT_BAND_PX
        if fig.layout.height:
            fig.layout.height = fig.layout.height + _CREDIT_BAND_PX
        fig.add_annotation(
            text=_plotly_literal(CREDIT_LINE),
            xref="paper",
            yref="paper",
            x=1,
            y=0,
            xanchor="right",
            yanchor="top",
            yshift=-(original_bottom + 2),
            showarrow=False,
            font=dict(size=_CREDIT_FONT_PX, color=_CREDIT_COLOR),
        )


def figure_text_style(settings) -> dict:
    """``annotate_figure``'s text styling from a ``FigureSettings`` or a
    settings mapping (the app's ``viz_settings``); what is missing is the
    default."""
    if isinstance(settings, Mapping):
        get = settings.get
    else:

        def get(name, default):
            return getattr(settings, name, default)

    return dict(
        title_font_size=int(get("title_font_size", DEFAULT_TITLE_FONT_SIZE)),
        caption_font_size=int(get("caption_font_size", DEFAULT_CAPTION_FONT_SIZE)),
        caption_color=str(get("caption_color", DEFAULT_CAPTION_COLOR)),
        show_credit=bool(get("show_credit", False)),
    )


# Columns that hold a filesystem path from the machine the app ran on.
# `image_path` is a `passthrough` meta field on both schemas, so it survives
# normalization and rides into the exported fixation tables — and a fixations
# CSV is exactly the file that gets attached to a paper,
# posted to OSF, or mailed to a collaborator. `/Users/<name>/` discloses the OS
# account; the rest discloses the directory layout, including where a MultiplEYE
# corpus lives. The basename still identifies the stimulus, which is all the
# column is used for downstream.
#
# `source_file` is deliberately NOT here: it is an identity label, not a path.
# `data.source_labels` stores the file's stem, qualified only by the trailing
# folders that tell two same-named files apart — never the folders they share,
# so an absolute path's `/Users/<name>/…` prefix does not reach it.
_PATH_COLUMNS = ("image_path",)


def strip_local_paths(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce path-bearing columns to their basename.

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


#: The artifacts that *are* one of the dataset's tables (rows of it,
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
    *,
    dictionary: CsvDictionary | None = None,
    table: str | None = None,
) -> int:
    # The pipeline's bookkeeping columns stay out of what is shared.
    df = strip_local_paths(shareable_frame(df, table=table))
    # And the columns the user's file named go out under those names.
    if dictionary is not None and fmt == "csv":
        if hidden is None and names is not None:
            hidden = names.redundant_aliases(df)
        canonical = [name for name in df if not hidden or name not in hidden]
    df = as_written(df, names, hidden)
    if fmt == "parquet":
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        data = buf.getvalue()
        zf.writestr(path, data)
        return len(data)
    # csv.writer sends complete rows to the member. Only a chunk of converted
    # values is kept in memory, even for a multi-gigabyte gaze table.
    with (
        zf.open(path, "w", force_zip64=True) as member,
        io.TextIOWrapper(member, encoding="utf-8", newline="") as text,
    ):
        df.to_csv(text, index=False, chunksize=5000)
    if dictionary is not None:
        dictionary.record(path, canonical, df)
    return zf.getinfo(path).file_size


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
    stopped, since that server is one per process. Every file it draws carries
    the citation in its metadata (`file_citation.stamp`).
    """
    from .animation_export import KALEIDO_LOCK, warm_calc_fig

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
            try:
                if server is not None:
                    data = warm_calc_fig(
                        fig,
                        {
                            "format": fmt,
                            "width": int(width),
                            "height": int(height),
                            "scale": scale,
                        },
                    )
                else:
                    data = fig.to_image(
                        format=fmt, width=int(width), height=int(height), scale=scale
                    )
            except Exception as exc:
                if "kaleido_scopes" in str(exc):
                    raise RuntimeError(
                        f"The installed browser opened before Kaleido’s plotting scripts were ready to draw the {fmt.upper()} file. "
                        "Let other exports finish and try again. HTML export also works offline with a self-contained file."
                    ) from exc
                raise
            return stamp_citation(bytes(data), fmt)

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
            "Starting the browser that draws the figure (this can take a few seconds)…",
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
            "Finishing the file…",
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
    """Drift correction for one exported figure.

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
    base_font_size: int = 16,
    font_family: str = "monospace",
) -> dict:
    """The same restorable settings file as Share, for one exported figure."""
    return render_plot_config(
        {
            **settings,
            "color_by_line": bool(settings.get("color_by_line")) or drift_applied,
        },
        participant=participant,
        trial=trial,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        base_font_size=base_font_size,
        font_family=font_family,
        x_field=x_field,
        y_field=y_field,
        screen_id=screen_id,
        setup=_setup_section(),
    )


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
        persist_state="session",  # The stored value stays "All"; only what the radio shows says more.
        format_func=lambda label: (
            "All trials, ignoring filters" if label == "All" else label
        ),
        horizontal=True,
        help="Pick the trials to export. *All trials, ignoring filters* also "
        "includes trials the trial filters hide.",
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
                persist_state="session",
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
                persist_state="session",
            )
    elif scope == "participant" and not active.empty:
        participants = sorted(active["participant_id"].dropna().astype(str).unique())
        scope_participant = panel_field(
            st,
            "selectbox",
            "Participant",
            options=participants,
            key=f"{key_prefix}_scope_pid",
            persist_state="session",
        )
    elif scope == "text" and not active.empty:
        if text_col is None:
            st.info("This dataset has no text ids, so it can't be exported by text.")
        else:
            texts = sorted(active[text_col].dropna().astype(str).unique())
            scope_text = panel_field(
                st,
                "selectbox",
                "Text",
                options=texts,
                key=f"{key_prefix}_scope_text",
                persist_state="session",
            )

    # Close the Scope section with a live count of what will be exported.
    n_export = len(
        _scope_frame(active, scope, scope_participant, scope_trial, scope_text)
    )
    n_total = len(combos_all) if combos_all is not None else len(combos)
    st.caption(f"**{n_export:,}** of **{n_total:,}** trials will be exported.")

    return scope, scope_participant, scope_trial, scope_text, export_unfiltered


@dataclass(frozen=True)
class NamingExample:
    """One selected file, under the trial's pattern or at a fixed bundle path."""

    fields: dict
    artifact: str = ""
    ext: str = ""
    fixed_path: str = ""


def _screen_folder(row: dict) -> str:
    screen = row.get(SCREEN_ID)
    if pd.isna(screen):
        return ""
    return f"screen-{int(row[SCREEN_INDEX]):03d}-{_safe_id(screen)}"


_UNASSIGNED = "_unassigned_screen_rows"


def _unassigned_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows whose recorded screen is unknown, kept once in the trial's tables."""
    if SCREEN_ID not in frame:
        return frame
    ids = frame[SCREEN_ID]
    return frame.loc[ids.isna() | ids.astype("string").str.strip().eq("")]


def _unit_frames(
    participant,
    trial,
    screen,
    words,
    fixations,
    raw_gaze,
    *,
    elapsed_axis=False,
    unassigned=False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The single-screen tables shared by the filename example and bundle writer."""
    trial_words = extract_trial(words, participant, trial)
    trial_fix = extract_trial(fixations, participant, trial)
    trial_fix = with_onset_provenance(trial_fix)
    if elapsed_axis:
        trial_fix = chart_axes.with_origin(trial_fix)
    trial_gaze = (
        extract_trial(raw_gaze, participant, trial)
        if raw_gaze is not None and not raw_gaze.empty
        else pd.DataFrame()
    )
    if unassigned:
        return (
            _unassigned_rows(trial_words),
            _unassigned_rows(trial_fix),
            _unassigned_rows(trial_gaze),
        )
    if pd.notna(screen):
        trial_words = screen_rows(trial_words, str(screen))
        trial_fix = screen_rows(trial_fix, str(screen))
        trial_gaze = screen_rows(trial_gaze, str(screen))
    return trial_words, trial_fix, trial_gaze


@dataclass
class UnitFiles:
    """Per-reading artifact names committed by the plan, before rendering."""

    fields: dict
    paths: dict[tuple[str, str], str]


def _plain_tables(options, words, fixations, raw_gaze):
    return {
        name: frame
        for name, frame in (
            (
                "fixations",
                fixations
                if options.include_fixations or options.include_analysis_family
                else None,
            ),
            ("raw_gaze", raw_gaze if options.include_raw_gaze else None),
            (
                "word_measures" if options.include_analysis_family else "measures",
                words
                if (options.include_measures or options.include_analysis_family)
                and brought_reading_measures(words)
                else None,
            ),
        )
        if frame is not None and not frame.empty
    }


def _plan_unit(
    row,
    frames,
    options,
    settings,
    axes,
    names,
    metadata_rows_for,
    members,
    *,
    paths=None,
) -> UnitFiles:
    pid, tid = row["participant_id"], row["trial_id"]
    words, fixations, raw_gaze = frames
    fields = pattern_fields(
        pid,
        tid,
        words,
        fixations,
        {
            **settings,
            "show_raw_gaze": bool(settings.get("show_raw_gaze"))
            and chart_axes.drawable_raw_samples(axes, raw_gaze, fixations),
        },
        combo_row=row,
        dataset_name=options.dataset_name,
        column_names=names,
        metadata_rows=metadata_rows_for(pid, tid, row.get("text_id"))
        if metadata_rows_for
        else None,
    )
    if paths is not None:
        # Retry keeps names already assigned by the original full-scope plan.
        return UnitFiles(fields, paths)
    requests = (
        []
        if row.get(_UNASSIGNED)
        else [("figure", fmt) for fmt in options.figure_formats()]
    )
    if options.include_plot_config and not row.get(_UNASSIGNED):
        requests.append(("plot_config", "json"))
    if not options.combine_trials:
        tables = _plain_tables(options, *frames)
        requests.extend(
            (table, fmt) for fmt in options.table_formats() for table in tables
        )
    screen = _screen_folder(row)
    return UnitFiles(
        fields,
        {
            (artifact, fmt): resolve_export_path(
                options.path_pattern,
                fields,
                artifact=f"screens/{screen}/{artifact}" if screen else artifact,
                ext=fmt,
                used=members,
            )
            for artifact, fmt in requests
        },
    )


def _readings_with_files(
    units,
    words,
    fixations,
    raw_gaze,
    options,
    settings,
    axes,
    names,
    metadata_rows_for,
    members,
):
    """Assign the standard figure, configuration and table paths once across the scope."""
    for values in units.itertuples(index=False, name=None):
        row = dict(zip(units.columns, values, strict=True))
        frames = _unit_frames(
            row["participant_id"],
            row["trial_id"],
            row.get(SCREEN_ID),
            words,
            fixations,
            raw_gaze,
            elapsed_axis=chart_axes.ELAPSED in axes,
            unassigned=row.get(_UNASSIGNED, False),
        )
        unit = (
            None
            if all(frame.empty for frame in frames)
            else _plan_unit(
                row, frames, options, settings, axes, names, metadata_rows_for, members
            )
        )
        yield row, unit, frames


def naming_example(
    options: ExportOptions,
    combos: pd.DataFrame,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    raw_gaze: pd.DataFrame | None = None,
    *,
    settings: dict | None = None,
    axes: tuple[str, str] = ("x", "y"),
    column_names: ColumnNames | None = None,
    metadata_rows_for=None,
) -> NamingExample:
    """First file in the selected scope, using the writer's fields and file order."""
    empty = pd.DataFrame()
    have_frames = words is not None or fixations is not None or raw_gaze is not None
    words = words if words is not None else empty
    fixations = fixations if fixations is not None else empty
    for position in range(len(combos)):
        units = export_units(
            combos.iloc[position : position + 1],
            words,
            fixations,
            raw_gaze,
            options.screens,
            include_unassigned=options.any_table(),
        )
        for row in units.to_dict("records"):
            pid, tid = row["participant_id"], row["trial_id"]
            screen_folder = _screen_folder(row)
            trial_words, trial_fix, trial_gaze = _unit_frames(
                pid,
                tid,
                row.get(SCREEN_ID),
                words,
                fixations,
                raw_gaze,
                elapsed_axis=chart_axes.ELAPSED in axes,
                unassigned=row.get(_UNASSIGNED, False),
            )
            if (
                have_frames
                and trial_words.empty
                and trial_fix.empty
                and trial_gaze.empty
            ):
                continue
            frames = trial_words, trial_fix, trial_gaze
            plan = _plan_unit(
                row,
                frames,
                options,
                settings or {},
                axes,
                column_names,
                metadata_rows_for,
                ArchiveNames(),
            )
            if plan.paths:
                artifact, ext = next(iter(plan.paths))
            elif options.combine_trials and (tables := _plain_tables(options, *frames)):
                artifact = next(iter(tables))
                return NamingExample(
                    plan.fields,
                    fixed_path=f"aggregate/all_{artifact}.{options.table_formats()[0]}",
                )
            elif options.any_table():
                continue
            else:
                return NamingExample(plan.fields, fixed_path="index.csv")
            if screen_folder:
                artifact = f"screens/{screen_folder}/{artifact}"
            return NamingExample(plan.fields, artifact, ext)
    fields = pattern_fields(
        "", "", empty, empty, settings or {}, dataset_name=options.dataset_name
    )
    fields.update(dict.fromkeys(combos.columns, ""))
    return NamingExample(fields)


def _metadata_fields(attached, key: str, grain: str) -> tuple[str, ...] | None:
    """Keep an explicit publication selection when the attached table changes."""
    import streamlit as st

    if attached is None or not attached.fields:
        return None
    labels = {field.name: field.label for field in attached.fields}
    names = list(labels)
    state = st.session_state
    selection_key = f"{key}_selection"
    stored = state.get(key)
    if selection_key not in state:
        # A session from before explicit selections were tracked can already
        # have a partial or cleared picker. Preserve that choice.
        state[selection_key] = (
            tuple(stored) if stored is not None and set(stored) != set(names) else None
        )
    selection = state[selection_key]
    allowed = set(names if selection is None else selection)
    current = [name for name in names if name in allowed]
    if stored is not None and list(stored) != current:
        state[key] = current

    def remember_selection() -> None:
        state[selection_key] = tuple(state[key])

    panel_field(
        st,
        "multiselect",
        f"{grain.title()} fields to include",
        options=names,
        **({"default": current} if key not in state else {}),
        format_func=labels.__getitem__,
        key=key,
        persist_state="session",
        on_change=remember_selection,
        help=f"The {grain} ID is included with the fields you choose.",
    )
    if selection and not current:
        st.caption(
            f"The attached {grain} table has none of your selected fields. "
            "Choose fields to include this table in the bundle."
        )
    return None if selection is None else tuple(current)


def _render_metadata_field_picker(key_prefix: str):
    from scanpath_studio import metadata as md

    return _metadata_fields(md.active(), f"{key_prefix}_meta_fields", "participant")


def _render_trial_metadata_field_picker(key_prefix: str):
    from scanpath_studio import metadata as md

    return _metadata_fields(
        md.active_trials(), f"{key_prefix}_trial_meta_fields", "trial"
    )


def _render_text_metadata_field_picker(key_prefix: str):
    from scanpath_studio import metadata as md

    return _metadata_fields(md.active_texts(), f"{key_prefix}_text_meta_fields", "text")


def _render_naming_options(
    st, options: ExportOptions, example: NamingExample, key_prefix: str
) -> str:
    """Show the selected path and keep a mistyped pattern in the field for editing."""
    fields = example.fields
    available = ", ".join(
        f"`{{{k}}}`" for k in sorted(set(fields) | set(_PATTERN_EXTRA_FIELDS))
    )
    heading, fields_slot = st.columns([4, 1], vertical_alignment="bottom")
    heading.markdown("### File naming")
    with fields_slot.popover(
        "Placeholders", help="The `{…}` fields the path pattern can use."
    ):
        st.markdown(available)
    path_pattern = panel_field(
        st,
        "text_input",
        "File path pattern",
        value=DEFAULT_PATH_PATTERN,
        key=f"{key_prefix}_path_pattern",
        persist_state="session",
        help="Path inside the ZIP. Use `/` for folders and `{…}` placeholders.",
    )
    error = path_structure_error(path_pattern) or pattern_error(path_pattern, fields)
    if error:
        st.error(error)
        return ""
    if example.fixed_path:
        st.caption(f"Example: `{example.fixed_path}` (fixed bundle path)")
    elif example.artifact:
        plain, path = (
            resolve_export_path(
                path_pattern,
                fields,
                artifact=example.artifact,
                ext=example.ext,
                used=ArchiveNames(names),
            )
            for names in ((), bundle_member_names(options))
        )
        clash = (
            f" (`{plain}` is taken by another file in the bundle, so the next free "
            "name is used)"
            if path != plain
            else ""
        )
        st.caption(f"Example: `{path}`{clash}")
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
    screen_options: list[str] | None = None,
    example_for: Callable = naming_example,
) -> ExportOptions:
    """Render the bulk-export options UI and return a populated ExportOptions.

    ``screen_options`` are the dataset's screen ids (:func:`screen_choices`);
    when there are any, a *Screens* picker narrows the bundle to some of them.

    ``combos`` is the currently filtered trial pool; ``combos_all`` (when given)
    is the whole loaded dataset. Picking the "All" scope switches the scope
    picker — and the export itself — to ``combos_all`` so the trial filters
    are ignored. ``title_pattern``/``caption_pattern`` come from the Scanpath
    rail's **📐 Figure & canvas** → *Title* / *Caption* — this panel has no
    copy of that setting of its own.
    """
    st = st_module
    # No expander — the options are always displayed.
    with st.container():
        st.markdown("### Trials to include")
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
        screens = _render_screen_picker(st, screen_options or [], key_prefix)

        # Figures are the headline artifact, so they lead with a single
        # multi-select of formats (pills) rather than a column of checkboxes.
        st.markdown("### Figure formats")
        fig_formats = (
            panel_field(
                st,
                "pills",
                "Formats",
                options=["PDF", "SVG", "PNG", "HTML"],
                selection_mode="multi",
                default=["PDF"],
                key=f"{key_prefix}_figfmts",
                persist_state="session",
                help=(
                    "PDF and SVG are vector images, PNG is a pixel image, and HTML is "
                    "interactive. Creating PDF, SVG or PNG files requires Chrome, Chromium or"
                    " Edge. HTML needs no additional browser installation."
                ),
            )
            or []
        )
        include_pdf = "PDF" in fig_formats
        include_svg = "SVG" in fig_formats
        include_png = "PNG" in fig_formats
        include_html = "HTML" in fig_formats
        # Asked only while HTML is picked, as for the current figure above.
        html_self_contained = include_html and bool(
            panel_field(
                st,
                "checkbox",
                "Self-contained HTML (opens offline, larger file)",
                display="Self-contained HTML",
                value=False,
                key=f"{key_prefix}_html_self_contained",
                persist_state="session",
                help=(
                    "Include the plotting library so the bundle's HTML figures open offline "
                    "(adds about 4.8 MB per figure). Otherwise, an internet connection is "
                    "needed when you open them."
                ),
            )
        )
        # The bundle's static figures need a browser on the server,
        # which the current figure's PNG/SVG do not — said only when it is
        # missing, and only while one of those formats is picked.
        if note := missing_browser_note(include_pdf or include_svg or include_png):
            st.warning(note, icon=ICONS["warning"])
        # Only surface the scale stepper when PNG is on, and keep it narrow
        # with `width` (columns would nest inside the row's own): a 1–4 stepper
        # stretched across the whole field column reads as a text box.
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
                persist_state="session",
                help="Higher values give sharper images and larger files.",
            )
        else:
            png_scale = int(st.session_state.get(f"{key_prefix}_scale", 2))

        st.markdown("### Also include")
        # Per-layer figure breakdown for publication editing.
        separable_layers = panel_field(
            st,
            "toggle",
            "Layers as separate files",
            value=False,
            key=f"{key_prefix}_layers",
            persist_state="session",
            help="Export each visual layer as a separate file.",
        )
        # Layers are static vectors/rasters — HTML can't be split. When no
        # vector/raster format is picked, they fall back to SVG (which needs
        # Kaleido/Chrome, unlike the browser-free HTML the user chose), so warn.
        if separable_layers and not (include_png or include_svg or include_pdf):
            st.caption(
                f"{ICONS['warning']} HTML figures can't be split, so the layers "
                "export as **SVG**, which needs Chrome, Chromium or Edge. Pick SVG, "
                "PDF or PNG above to choose the layer format."
            )
        include_plot_config = panel_field(
            st,
            "toggle",
            "Settings file (JSON)",
            value=True,
            key=f"{key_prefix}_cfg",
            persist_state="session",
            help="Include the figure's settings file.",
        )
        include_annotations = panel_field(
            st,
            "toggle",
            "Annotations (JSON)",
            value=False,
            key=f"{key_prefix}_annotations",
            persist_state="session",
            help="Include the exported trials' favorites, tags and notes as "
            "annotations.json. You can import it on "
            f"{ICONS['view_data']} Data Management → Annotations.",
        )
        tabular = (
            panel_field(
                st,
                "pills",
                "Tabular data",
                # The measure family is computed by the app, so it is offered
                # only while the computed measures are enabled.
                options=[
                    "Fixations",
                    "Raw gaze",
                    "Word measures",
                    *(["Computed measures"] if computed_measures_enabled() else []),
                ],
                selection_mode="multi",
                default=[],
                key=f"{key_prefix}_tabular",
                persist_state="session",
                help=(
                    "Choose the data tables to include. Word measures are the reading "
                    "measures provided in your dataset; the app does not compute them."
                ),
            )
            or []
        )
        include_fixations = "Fixations" in tabular
        include_raw_gaze = "Raw gaze" in tabular
        include_measures = "Word measures" in tabular
        include_analysis_family = "Computed measures" in tabular
        any_table = bool(tabular)
        if any_table:
            table_format = (
                panel_field(
                    st,
                    "segmented_control",
                    "Table format",
                    options=["csv", "parquet", "both"],
                    format_func=lambda value: {
                        "csv": "CSV",
                        "parquet": "Parquet",
                        "both": "Both",
                    }[value],
                    default="csv",
                    key=f"{key_prefix}_fmt",
                    persist_state="session",
                )
                or "csv"
            )
            combine_trials = panel_field(
                st,
                "toggle",
                "Combine all trials into one file per table",
                value=False,
                key=f"{key_prefix}_combine",
                persist_state="session",
                help="Write each table once under aggregate/, with all exported "
                "trials in it, instead of one file per trial.",
            )
        else:
            table_format = str(st.session_state.get(f"{key_prefix}_fmt", "csv"))
            combine_trials = bool(st.session_state.get(f"{key_prefix}_combine", False))

        metadata_fields = _render_metadata_field_picker(key_prefix)
        trial_metadata_fields = _render_trial_metadata_field_picker(key_prefix)
        text_metadata_fields = _render_text_metadata_field_picker(key_prefix)
        naming_slot = st.container()
        if title_pattern or caption_pattern:
            st.caption(
                "The figures use the title and caption set in Plot controls under "
                f"**{ICONS['figure']} Figure & canvas** → *Title* / *Caption*."
            )

    from .controls import current_dataset_name

    options = ExportOptions(
        include_png=include_png,
        include_svg=include_svg,
        include_pdf=include_pdf,
        include_html=include_html,
        html_self_contained=html_self_contained,
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
        title_pattern=title_pattern,
        caption_pattern=caption_pattern,
        # This panel only runs inside the app, so the picker's label is
        # available; `pattern_fields` itself stays session-free.
        dataset_name=current_dataset_name(),
        metadata_fields=metadata_fields,
        trial_metadata_fields=trial_metadata_fields,
        text_metadata_fields=text_metadata_fields,
        export_unfiltered=export_unfiltered,
        scope=scope,
        scope_participant=scope_pid,
        scope_trial=scope_trial,
        scope_text=scope_text,
        screens=screens,
    )
    pool = combos_all if export_unfiltered and combos_all is not None else combos
    with naming_slot:
        try:
            example = example_for(options, _apply_scope(pool, options))
        except ValueError as error:
            st.error(str(error))
            options.path_pattern = ""
        else:
            options.path_pattern = _render_naming_options(
                st, options, example, key_prefix
            )
    return options


def _render_screen_picker(
    st, screen_options: list[str], key_prefix: str
) -> tuple[str, ...] | None:
    """The *Screens* row: which screens of each multipart trial go in. Nothing
    picked is every screen (``None``); drawn only for a dataset with screens."""
    if not screen_options:
        return None
    key = f"{key_prefix}_screens"
    # A pick from another dataset names screens this one does not have.
    held = st.session_state.get(key)
    if held is not None:
        kept = [screen for screen in held if screen in screen_options]
        if kept != list(held):
            st.session_state[key] = kept
    picked = (
        panel_field(
            st,
            "multiselect",
            "Screens",
            options=screen_options,
            key=key,
            persist_state="session",
            placeholder="All screens",
            help="Export only these screens of each trial. Leave empty for all "
            "screens. Trials that show none of the picked screens are left out.",
        )
        or []
    )
    return tuple(picked) if picked else None


def _scope_frame(
    combos: pd.DataFrame,
    scope: str,
    scope_participant: str | None,
    scope_trial: str | None,
    scope_text: str | None,
) -> pd.DataFrame:
    """Filter combos to the chosen scope (pure helper, no ExportOptions needed)."""
    if scope == "all":
        return combos
    if scope == "trial":
        required = {"participant_id": scope_participant, "trial_id": scope_trial}
    elif scope == "participant":
        required = {"participant_id": scope_participant}
    elif scope == "text":
        text_col = "unique_text_id" if "unique_text_id" in combos else "text_id"
        required = {text_col: scope_text}
    else:
        raise ValueError(
            f"Unknown export scope {scope!r}. Choose all, trial, participant or text."
        )
    for column, value in required.items():
        if column not in combos or value is None or value == "":
            return combos.iloc[0:0]
        combos = combos[
            combos[column].notna() & combos[column].astype(str).eq(str(value))
        ]
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
    """Text metadata belonging to one export unit, using the recording tables' precedence."""
    from .metadata import recording_keys, text_keys

    recorded = text_keys(recording_keys(*frames))
    if recorded:
        # Two equally ranked recorded IDs leave the reading unassigned. Its
        # combo row must never pick a winner or revive a synthetic trial ID.
        return recorded if len(recorded) == 1 else set()
    value = combo_row.get("text_id")
    return {str(value)} if pd.notna(value) else set()


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
    """The attached trial table, when running inside the app.

    Handed over on a private session key for the same reason its participant
    twin is: the frame must not reach the bulk-export cache signature.
    """
    try:
        import streamlit as st

        return st.session_state.get("_export_trial_metadata")
    except Exception:  # no script run context (API, CLI)
        return None


def _session_participant_metadata():
    """The attached participant table, when running inside the app.

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


def _write_inventory(
    zf: zipfile.ZipFile, inventory: list[dict], path: str = "index.csv"
) -> None:
    """Write ``index.csv``: one row per file in the bundle, plus each requested
    file that failed and each reading skipped. ``status`` is ``written``,
    ``failed`` or ``skipped``; a file type nobody asked for has no row."""
    frame = pd.DataFrame(inventory, columns=list(INVENTORY_COLUMNS))
    zf.writestr(path, frame.to_csv(index=False))


def screen_choices(*frames: pd.DataFrame | None) -> list[str]:
    """The screen ids ``frames`` carry, for the export's screen picker: in the
    order they are shown (their lowest ``screen_index``), then by id. Empty when
    no frame has screens."""
    parts = [
        # De-duplicated first: a raw-gaze table can hold millions of samples.
        frame[
            [c for c in (SCREEN_ID, SCREEN_INDEX) if c in frame.columns]
        ].drop_duplicates()
        for frame in frames
        if frame is not None and not frame.empty and SCREEN_ID in frame.columns
    ]
    if not parts:
        return []
    pairs = pd.concat(parts, ignore_index=True).dropna(subset=[SCREEN_ID])
    pairs[SCREEN_ID] = pairs[SCREEN_ID].astype(str).str.strip()
    pairs = pairs.loc[pairs[SCREEN_ID].ne("")]
    if SCREEN_INDEX not in pairs.columns:
        pairs[SCREEN_INDEX] = float("nan")
    pairs[SCREEN_INDEX] = pd.to_numeric(pairs[SCREEN_INDEX], errors="coerce")
    first = pairs.groupby(SCREEN_ID)[SCREEN_INDEX].min().reset_index()
    first = first.sort_values([SCREEN_INDEX, SCREEN_ID], na_position="last")
    return first[SCREEN_ID].tolist()


def export_units(
    combos: pd.DataFrame,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    raw_gaze: pd.DataFrame | None = None,
    screens: tuple[str, ...] | None = None,
    *,
    include_unassigned: bool = False,
) -> pd.DataFrame:
    """One row per **screen export unit**: each trial in ``combos``, or each of
    its screens when it is a multipart reading. ``combos`` is already scoped.

    ``screens`` (``ExportOptions.screens``) keeps only the units on those
    screen ids, so a trial without screens has none of them and is left out.
    """
    if not any(
        frame is not None and SCREEN_ID in frame
        for frame in (words, fixations, raw_gaze)
    ):
        return (combos if screens is None else combos.iloc[0:0]).reset_index(drop=True)
    rows: list[dict] = []
    for combo in combos.to_dict("records"):
        participant, trial = combo["participant_id"], combo["trial_id"]
        parent_words = extract_trial(words, participant, trial)
        parent_fixations = extract_trial(fixations, participant, trial)
        parent_samples = (
            extract_trial(raw_gaze, participant, trial)
            if raw_gaze is not None and (SCREEN_ID in raw_gaze or include_unassigned)
            else None
        )
        catalog = part_catalog(parent_words, parent_fixations, parent_samples)
        if catalog.empty:
            rows.append(combo)
        else:
            for screen in catalog.to_dict("records"):
                rows.append({**combo, **screen})
            if (
                include_unassigned
                and screens is None
                and any(
                    frame is not None and not _unassigned_rows(frame).empty
                    for frame in (parent_words, parent_fixations, parent_samples)
                )
            ):
                rows.append({**combo, SCREEN_ID: None, _UNASSIGNED: True})
    units = pd.DataFrame(rows)
    if _UNASSIGNED in units:
        units[_UNASSIGNED] = units[_UNASSIGNED].eq(True)
    if screens is None:
        return units
    if units.empty or SCREEN_ID not in units.columns:
        return units.iloc[0:0]
    chosen = {str(screen) for screen in screens}
    keep = units[SCREEN_ID].notna() & units[SCREEN_ID].astype(str).isin(chosen)
    return units[keep].reset_index(drop=True)


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
    trials, units = count_export(scoped, words, fixations, raw_gaze, options.screens)
    return plan_from_counts(trials, units, options)


def count_export_units(
    combos: pd.DataFrame,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    raw_gaze: pd.DataFrame | None = None,
) -> int:
    """``len(export_units(...))`` — without walking every trial when no frame
    carries screens, the common case, where each trial is one unit."""
    return len(export_units(combos, words, fixations, raw_gaze))


def count_export(
    combos: pd.DataFrame,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    raw_gaze: pd.DataFrame | None = None,
    screens: tuple[str, ...] | None = None,
) -> tuple[int, int]:
    """``(trials, units)`` a bundle of ``combos`` exports: with ``screens``
    chosen, only the trials that show one of them count."""
    if screens is None:
        return len(combos), count_export_units(combos, words, fixations, raw_gaze)
    units = export_units(combos, words, fixations, raw_gaze, screens)
    if units.empty:
        return 0, 0
    trials = units[["participant_id", "trial_id"]].drop_duplicates()
    return len(trials), len(units)


def _keep_unit_trials(combos: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    """``combos`` cut to the trials ``units`` still holds — after a screen
    choice, the trials the bundle actually exports."""
    if units.empty:
        return combos.iloc[0:0]
    keys = set(
        zip(
            units["participant_id"].astype(str),
            units["trial_id"].astype(str),
            strict=True,
        )
    )
    held = [
        (str(pid), str(tid)) in keys
        for pid, tid in zip(combos["participant_id"], combos["trial_id"], strict=True)
    ]
    return combos[held]


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


def _cite_lines(corpus: str | None) -> list[str]:
    """The README's *Cite* section: the software, and the corpus the trials
    come from when it is a public one (`citation.corpus_for`)."""
    lines = [
        "If you use these files in a publication, please cite Scanpath Studio"
        + (f" and {CORPORA[corpus].name}:" if corpus else ":"),
        "",
        f"- {software_apa()}",
    ]
    if corpus:
        lines.append(f"- {CORPORA[corpus].apa()}")
    lines += ["", "`CITATION.bib` has the same as BibTeX."]
    return lines


def _package_version() -> str:
    from scanpath_studio import __version__

    return __version__


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _scope_lines(
    options: ExportOptions, combos: pd.DataFrame, units: pd.DataFrame
) -> list[str]:
    """The README's *Scope* section: which trials the bundle was built from."""
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
        f"- Trials: {chosen}",
        f"- {_plural(len(combos), 'trial')}"
        + (f" ({_plural(len(units), 'screen')})" if len(units) != len(combos) else ""),
    ]
    if options.screens is not None:
        lines.append(f"- Screens: only {', '.join(options.screens)}")
    return lines


@dataclass
class BundleContents:
    """File paths, data columns and release notes shown before a bundle is built."""

    files: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def bundle_contents(
    combos,
    words,
    fixations,
    raw_gaze,
    *,
    options,
    settings,
    axes=("x", "y"),
    column_names=None,
    metadata_rows_for=None,
    annotation_records=None,
) -> BundleContents:
    """Plan known files and columns without rendering a figure or creating a ZIP."""
    scope = _apply_scope(combos, options)
    units = export_units(
        scope,
        words,
        fixations,
        raw_gaze,
        options.screens,
        include_unassigned=options.any_table(),
    )
    maps = column_names or {}
    members = ArchiveNames(bundle_member_names(options))
    contents = BundleContents()
    pairs = set()
    texts = set()
    combined = {}
    wrote_table = False
    includes_word_text = False
    text_metadata = _selected_text_metadata_columns(
        settings.get("text_metadata"), options.text_metadata_fields
    )
    hidden = {
        table: names.redundant_aliases(frame)
        for table, frame in (
            ("words", words),
            ("fixations", fixations),
            ("raw_gaze", raw_gaze),
        )
        if (names := maps.get(table)) and names.entries and frame is not None
    }

    def add(path, kind, row=None, columns=()):
        row = row or {}
        contents.files.append(
            {
                "Path": path,
                "Contents": kind,
                "Participant": str(row.get("participant_id", "")),
                "Trial": str(row.get("trial_id", "")),
                "Screen": str(row[SCREEN_ID]) if pd.notna(row.get(SCREEN_ID)) else "",
                "Table columns": ", ".join(map(str, columns)),
            }
        )

    for path, kind in (
        ("README.md", "Bundle guide"),
        ("CITATION.bib", "Citation"),
        ("index.csv", "File inventory"),
    ):
        add(path, kind)
    for row, layout, frames in _readings_with_files(
        units,
        words,
        fixations,
        raw_gaze,
        options,
        settings,
        axes,
        across_tables(maps),
        metadata_rows_for,
        members,
    ):
        if layout is None:
            continue
        pid, tid = str(row["participant_id"]), str(row["trial_id"])
        pairs.add((pid, tid))
        if text_metadata is not None and not text_metadata.empty:
            texts.update(_unit_text_ids(row, *frames))
        headers = {}
        for artifact, frame in _plain_tables(options, *frames).items():
            table = _ARTIFACT_TABLE[artifact]
            if table == "words" and "text" in frame.columns:
                includes_word_text = True
            headers[artifact] = as_written(
                shareable_frame(frame, table=table), maps.get(table), hidden.get(table)
            ).columns
            if options.combine_trials:
                combined.setdefault(artifact, {}).update(
                    dict.fromkeys(headers[artifact])
                )
            wrote_table = True
        for (artifact, _fmt), path in layout.paths.items():
            add(path, artifact, row, headers.get(artifact, ()))
    for artifact, columns in combined.items():
        for fmt in options.table_formats():
            add(f"aggregate/all_{artifact}.{fmt}", artifact, columns=columns)
    for grain, source, selected, restrict in (
        (
            "participant",
            "participants",
            options.metadata_fields,
            _selected_metadata_columns,
        ),
        (
            "trial",
            "trials",
            options.trial_metadata_fields,
            _selected_trial_metadata_columns,
        ),
        (
            "text",
            "texts",
            options.text_metadata_fields,
            _selected_text_metadata_columns,
        ),
    ):
        frame = _rows_in_scope(
            restrict(settings.get(f"{grain}_metadata"), selected),
            pairs=pairs,
            texts=texts,
            grain=grain,
        )
        if frame is not None:
            for fmt in options.table_formats():
                add(
                    f"metadata/{source}.{fmt}",
                    f"{grain.title()} metadata · {_plural(len(frame), 'row')}",
                    columns=frame.columns,
                )
            wrote_table = True
    notes = (
        _annotations_in_scope(units, options.screens, annotation_records)
        if options.include_annotations
        else []
    )
    if notes:
        add("annotations.json", _plural(len(notes), "annotation record"))
    if wrote_table and (
        "csv" in options.table_formats()
        or any(names.entries for names in maps.values())
    ):
        add("columns.json", "Column dictionary")
    if wrote_table and "csv" in options.table_formats():
        add("read_csv.R", "R import example")
    if includes_word_text:
        contents.notes.append(
            "Word-measure tables include the recorded stimulus words. Figure text masking applies to figures only."
        )
    if options.needs_figure() and settings.get("show_stimulus_image"):
        contents.notes.append(
            "Figures can include the stimulus image where an image is available and permitted."
        )
    if options.separable_layers:
        contents.notes.append(
            "The figure's visible layers determine the additional layer files. Their final paths appear in index.csv."
        )
    if options.include_analysis_family:
        add("run_config.json", "Analysis settings")
        contents.notes.append(
            "Computed tables depend on each reading. The finished index lists them, and the column dictionary describes the CSV fields."
        )
    return contents


def _annotations_in_scope(units, screens, annotation_records) -> list[dict]:
    annotations_kept: list[dict] = []
    if annotation_records and not units.empty:
        from .annotations import records_in, records_to_store

        trials = zip(units["participant_id"], units["trial_id"], strict=True)
        annotations_kept = records_in(records_to_store(annotation_records), trials)
        if screens is not None:
            selected = set(
                units[["participant_id", "trial_id", SCREEN_ID]]
                .astype(str)
                .itertuples(index=False, name=None)
            )
            annotations_kept = [
                record
                for record in annotations_kept
                if SCREEN_ID not in record
                or (record["participant_id"], record["trial_id"], record[SCREEN_ID])
                in selected
            ]
    return annotations_kept


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
    stimulus_image_resolver: Callable | None = None,
    _retry=None,
) -> tuple[bytes, ExportProgress]:
    """Build a zip archive of selected artifacts and return its bytes.

    ``column_names`` is the dataset's map per table
    (``{"fixations": …, "words": …, "raw_gaze": …}``): each table is written
    with the columns its file named under those names, the README's data
    dictionary says where every column came from, and a ``columns.json``
    records the map; patterns accept either name. Without it the tables keep
    the internal names.

    ``metadata_rows_for(participant, trial, text_id)`` returns a
    trial's metadata-table rows for ``{table.field}`` patterns — the app passes
    ``metadata.pattern_rows``; headless callers have no attached tables.

    ``annotation_records`` are the annotations to write as
    ``annotations.json`` when ``options.include_annotations`` is set, in
    ``annotations.current_records()``'s shape; only those on the exported
    trials go in. A screen selection includes each selected screen's notes and
    its parent trial's note. The app passes the session's; headless callers have none.
    ``annotation_dataset`` is the dataset they were made on, which the file
    names (annotations file schema 3).

    progress_callback (if given) is invoked with an ExportProgress after every
    trial so the UI can update a progress bar.

    Raises ``ValueError`` before any work when ``options.path_pattern`` is not
    a path that stays inside the ZIP (:func:`path_structure_error`).
    """
    pattern_problem = path_structure_error(options.path_pattern)
    if pattern_problem:
        raise ValueError(pattern_problem)
    combos = _apply_scope(combos, options)
    units = export_units(
        combos,
        words,
        fixations,
        raw_gaze,
        options.screens,
        include_unassigned=options.any_table(),
    )
    if options.screens is not None:
        # Only the trials that show a chosen screen are exported — for the
        # annotations, the README and every per-trial table alike.
        combos = _keep_unit_trials(combos, units)
    if _retry is not None:
        units = _retry.select_units(units)
    # The annotations, cut to the exported trials once: the README says the
    # file is there exactly when the writer below writes it.
    annotations_kept = (
        _annotations_in_scope(units, options.screens, annotation_records)
        if options.include_annotations
        else []
    )
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
        table: shareable_frame(frame, table=table)
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
    # Every member's name comes from one registry, with the bundle's own files
    # reserved first. A trial's file the path pattern names like one of them, or
    # like another trial's, gets a `-2` instead of a second member of that name —
    # which would hide the README behind a plot config, and leave the inventory
    # pointing at whichever one a reader happened to open.
    reserved = set(bundle_member_names(options))
    if _retry is not None:
        reserved.update(_retry.reserved)
    members = ArchiveNames(reserved)
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

    # Each table's per-trial frames, stacked into `aggregate/all_<table>`
    # when the tables are combined. The family's words + fixations are kept
    # either way, for the reader summary, which only exists across trials.
    combined: dict[str, list[pd.DataFrame]] = {}
    family_words: list[pd.DataFrame] = []
    family_fixations: list[pd.DataFrame] = []
    # The export writes the reading measures the dataset
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

    corpus = corpus_for(settings.get("data_source") or options.dataset_name)
    refs = settings.get("dataset_references") or []
    if refs:
        cite_lines = [f"- {software_apa()}"]
        for ref in refs:
            role = (
                "Dataset for the exported trials"
                if ref["side"] == "A"
                else "Second dataset in the on-screen comparison"
            )
            cite_lines.append(f"- {role}: {dataset_credit.reference_text(ref, 'apa')}")
        cite_lines.extend(("", "`CITATION.bib` contains the references in BibTeX."))
    else:
        cite_lines = _cite_lines(corpus)
    readme_lines = [
        "# Bulk export",
        f"Generated: {_local_stamp()}",
        "",
        f"Made with: {CITATION['title']}",
        f"Version: {_package_version()}",
        f"DOI: https://doi.org/{CITATION['doi']}",
        "",
        "## Cite",
        *cite_lines,
        "",
        "## Scope",
        *_scope_lines(options, combos, units),
        "",
        "## Layout",
        "- `index.csv` lists every file in this bundle (its path, what it is, "
        "its participant, trial and screen), plus every requested file that "
        "failed (`status` = `failed`) or was skipped (`skipped`). File types "
        "you did not request are not listed.",
        "- `per_trial/<participant>__<trial>/` holds each trial's files, "
        "unless the File naming pattern put them elsewhere (`index.csv` has "
        "every path). A file whose name is already taken in the bundle has "
        "`-2`, `-3` … added to its name.",
        "- A trial shown on several screens adds `screens/screen-001-<id>/` "
        "inside its folder.",
        *(
            [
                "- `aggregate/` holds each table once, with all trials in this "
                "run (*Combine all trials into one file per table*)."
            ]
            if options.combine_trials and options.any_table()
            else (
                ["- `aggregate/` holds the reader summary across all trials."]
                if options.include_analysis_family
                else []
            )
        ),
        *(
            [
                "- `annotations.json` holds the favorites, tags and notes on "
                "these trials; import it on the app's Data Management page → Annotations."
            ]
            if annotations_kept
            else []
        ),
        "",
        "## Data dictionary",
        *(
            [
                "Columns keep the names they have in the dataset's files. A "
                "column Scanpath Studio built, converted or computed has its "
                "internal name. `columns.json` maps each column below to its "
                "internal name, for scripts that work across datasets. Columns "
                "not listed keep their names. Tables the app derives (summaries, "
                "saccades) use the dataset's names for the ids and the app's "
                "names for the values they add.",
                *dictionary_lines(written, maps),
                *(
                    ["", "Reading measures in the word tables:"]
                    if measures_wanted
                    else []
                ),
            ]
            if any(written.values())
            else [
                "Column names (Scanpath Studio's standard names):",
                "- participant_id, trial_id, text_id, word_id",
                "- screen_id, screen_index (multipart trials only)",
                "- x, y, width, height (word bounding boxes in screen px)",
                "- x, y, duration_ms, timestamp_ms (fixations)",
            ]
        ),
        *(
            [f"- {measure_headers.get(column, column)}" for column in brought]
            if brought
            else ["- (no reading measures; see below)"]
            if measures_wanted
            else []
        ),
        "",
        "## Reading measures",
        "The word tables carry the reading measures that came with the dataset, "
        "as mapped on the app's Data Management page. Scanpath Studio computes "
        "none of them.",
        *(
            [
                "",
                "This dataset has none, so the bundle has no word-measure table. "
                "To add them, map them in the app on Data Management → Edit "
                "dataset → Reading measures.",
            ]
            if measures_wanted and not brought
            else []
        ),
    ]
    csv_dictionary = CsvDictionary()
    readme_path = members.own("README.md")
    _inventory(readme_path, "readme", "written")
    path = members.own("CITATION.bib")
    citations = (
        dataset_credit.cited_text("bibtex", refs) if refs else cite("bibtex", corpus)
    )
    zf.writestr(path, citations + "\n")
    _inventory(path, "citation", "written")
    if options.include_analysis_family:
        path = members.own("run_config.json")
        zf.writestr(
            path,
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
        _inventory(path, "run_config", "written")

    # One warm Kaleido browser for every trial's figure (see _figure_renderer)
    # instead of cold-starting Chrome on each render. HTML needs no browser, so
    # only spin Kaleido up when a raster/vector format was requested (combined
    # figure or the per-layer breakdown).
    # A user pattern can map two trials to the same path (one that omits
    # the trial id, say). Two zip entries at one name silently loses a file, so
    # `resolve_export_path` disambiguates against `members` — every name given
    # out so far, the bundle's own reserved among them.
    # The readers, trials and texts the bundle actually holds — what its
    # metadata tables are narrowed to at the end.
    exported_pairs: set[tuple[str, str]] = set()
    exported_texts: set[str] = set()
    text_metadata = (settings or {}).get("text_metadata")
    if text_metadata is None:
        text_metadata = _session_text_metadata()
    text_metadata = _selected_text_metadata_columns(
        text_metadata, options.text_metadata_fields
    )
    needs_kaleido = (
        options.needs_kaleido() if _retry is None else _retry.needs_kaleido()
    )
    emit_status(
        status_callback,
        (
            ExportStage.STARTING_RENDERER
            if needs_kaleido
            else ExportStage.ENCODING_WRITING
        ),
        (
            "Starting the browser that draws the figures…"
            if needs_kaleido
            else "Writing selected files…"
        ),
        started_at=started,
    )
    axes = (x_field, y_field)
    if (options.separable_layers or options.include_analysis_family) and _retry is None:
        readings = [
            (row, plan)
            for row, plan, _frames in _readings_with_files(
                units,
                words,
                fixations,
                raw_gaze,
                options,
                settings,
                axes,
                every_table,
                metadata_rows_for,
                members,
            )
        ]
    else:
        readings = (
            (dict(zip(units.columns, values, strict=True)), None)
            for values in units.itertuples(index=False, name=None)
        )
    with _figure_renderer(needs_kaleido) as render_figure:
        for combo, layout in readings:
            # The cancel checkpoint (`progress.Cancelled`), between units so a
            # stopped build never leaves one half-written; a no-op headlessly.
            try:
                report_progress(
                    progress.finished_trials, progress.total_trials, unit="screens"
                )
            except BaseException:  # `progress.Cancelled`: close the zip, go
                zf.close()
                raise
            participant = combo["participant_id"]
            trial = combo["trial_id"]
            screen_id = combo.get(SCREEN_ID)
            screen_slug = _screen_folder(combo)
            slug = f"{_safe_id(participant)}__{_safe_id(trial)}"
            if screen_slug:
                slug += f"__{screen_slug}"
            unit_ids = {
                "participant_id": str(participant),
                "trial_id": str(trial),
                "screen_id": str(screen_id) if screen_slug else "",
            }

            trial_words, trial_fix, trial_raw_gaze = _unit_frames(
                participant,
                trial,
                screen_id,
                words,
                fixations,
                raw_gaze,
                elapsed_axis=chart_axes.ELAPSED in (x_field, y_field),
                unassigned=combo.get(_UNASSIGNED, False),
            )

            # Skip only a genuinely empty trial (nothing to draw). The figure
            # builder renders from fixations alone (words optional — boxes/labels)
            # or from words alone (AOI layout), and the live view does too; so a
            # words-that-don't-join / fixations-only trial must still export
            # instead of being skipped with "empty data". And a trial recorded
            # as raw gaze alone is drawn from its samples.
            if trial_words.empty and trial_fix.empty and trial_raw_gaze.empty:
                progress.finished_trials += 1
                progress.trials_skipped += 1
                progress.errors.append(f"{slug}: empty data, skipped")
                _inventory("", "reading", "skipped", unit_ids, "no data", fmt="")
                if progress_callback:
                    progress_callback(progress)
                continue

            exported_pairs.add((str(participant), str(trial)))
            if text_metadata is not None and not text_metadata.empty:
                exported_texts.update(
                    _unit_text_ids(combo, trial_words, trial_fix, trial_raw_gaze)
                )

            # A screen's own canvas, for its figure and its plot config alike.
            unit_canvas = (
                screen_canvas_size(trial_words)
                or screen_canvas_size(trial_fix)
                or screen_canvas_size(trial_raw_gaze)
            )
            unit_width = int(unit_canvas[0] if unit_canvas else canvas_width)
            unit_height = int(unit_canvas[1] if unit_canvas else canvas_height)

            unit_settings = dict(settings)
            if "show_stimulus_image" in settings:
                resolver = stimulus_image_resolver or reading_stimulus_image
                page = (
                    resolver(trial_words, trial_fix)
                    if settings.get("show_stimulus_image")
                    and not settings.get("stimulus_image_upload_uri")
                    else None
                )
                unit_settings.update(
                    stimulus_image_settings(
                        settings,
                        (unit_width, unit_height),
                        page,
                    )
                )
                # The resolver has already allowed or refused this page.
                # Never retry an app-refused server path in the builder.
                unit_settings["show_stimulus_image"] = False
            reasons = illustration_reasons(
                {**unit_settings, "x_field": x_field, "y_field": y_field},
                data_source=settings.get("data_source"),
                synthetic=bool(settings.get("synthetic_source")),
                static=True,
            )
            unit_settings["illustration_reasons"] = resolve_label_reasons(
                str(settings.get("illustration_label", "Auto")).title(),
                reasons,
            )

            retry_unit = (
                _retry.units[(str(participant), str(trial), unit_ids["screen_id"])]
                if _retry is not None
                else None
            )
            figure_formats = [
                fmt
                for fmt in options.figure_formats()
                if not combo.get(_UNASSIGNED)
                and (retry_unit is None or retry_unit.wants("figure", fmt))
            ]
            layer_formats = (
                options.layer_formats()
                if not combo.get(_UNASSIGNED)
                and (retry_unit is None or retry_unit.layer_failures)
                else []
            )
            if layout is None:
                layout = _plan_unit(
                    combo,
                    (trial_words, trial_fix, trial_raw_gaze),
                    options,
                    settings,
                    axes,
                    every_table,
                    metadata_rows_for,
                    members,
                    paths=retry_unit.paths if retry_unit is not None else None,
                )
            fields = layout.fields

            def _path(
                artifact: str, ext: str, _layout=layout, _slug=screen_slug
            ) -> str:
                if (artifact, ext) in _layout.paths:
                    return _layout.paths[artifact, ext]
                if _slug:
                    artifact = f"screens/{_slug}/{artifact}"
                return resolve_export_path(
                    options.path_pattern,
                    _layout.fields,
                    artifact=artifact,
                    ext=ext,
                    used=members,
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

            def record_failure(path, artifact, fmt, exc, unit=unit_ids, name=slug):
                progress.figures_failed += 1
                progress.retryable_figures += 1
                label = "layer" if artifact == "layers" else f"{fmt.upper()} {artifact}"
                progress.errors.append(f"{name}: {label} export failed ({exc})")
                _inventory(path, artifact, "failed", unit, str(exc), fmt=fmt)

            def record_layer_set_failure(exc, retry=retry_unit):
                # Before a successful split we cannot know which layers exist.
                # If only named layers were retried, keep those exact names.
                failed = (
                    retry.layer_failures if retry is not None else [("layers", "", "")]
                )
                for artifact, fmt, path in failed:
                    record_failure(path, artifact, fmt, exc)

            if figure_formats or layer_formats:
                emit_status(
                    status_callback,
                    ExportStage.RASTERIZING,
                    f"Rendering {progress.finished_trials + 1} of {progress.total_trials}…",
                    started_at=started,
                    completed=progress.finished_trials,
                    total=progress.total_trials,
                )
                fig = None
                try:
                    # Apply the drift correction to the
                    # figure's fixations (a no-op when "Off"), so the batch
                    # matches the corrected figure on screen. `trial_fix` itself
                    # stays uncorrected — the tables below export the recording.
                    fig_fix, connector_y = _drift_corrected_for_figure(
                        trial_fix, trial_words, settings
                    )
                    render_values = {
                        name: unit_settings[name]
                        for name in STATIC_FIGURE_OPTIONS
                        if name in unit_settings
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
                        # on-screen static path forces it (tabs.py's drift-
                        # correction overrides) — else the batch differs in
                        # colouring.
                        color_by_line=bool(settings.get("color_by_line", False))
                        or fig_fix is not trial_fix,
                    )
                    # The trial's own samples, as the live figure
                    # gets them (the layer self-gates on `show_raw_gaze`).
                    fig = make_scanpath_figure(
                        trial_words,
                        fig_fix,
                        settings=render_settings,
                        raw_gaze=trial_raw_gaze if not trial_raw_gaze.empty else None,
                    )
                    # Stamp the title/caption BEFORE measuring the output
                    # size — the bands grow the figure, and rendering at the
                    # pre-title size would crop them off.
                    annotate_figure(
                        fig,
                        title=title,
                        caption=caption,
                        **figure_text_style(render_settings),
                    )
                except Exception as exc:
                    fig = None
                    for fmt in figure_formats:
                        record_failure(_path("figure", fmt), "figure", fmt, exc)
                    if layer_formats:
                        record_layer_set_failure(exc)
                # Each format on its own, so a missing browser costs the
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
                                data = stamp_html(
                                    fig.to_html(
                                        include_plotlyjs=html_plotlyjs(
                                            options.html_self_contained
                                        ),
                                        full_html=True,
                                        config={**PLOTLY_CONFIG},
                                    )
                                ).encode("utf-8")
                            else:
                                scale = options.png_scale if fmt == "png" else 1
                                data = render_figure(fig, fmt, out_w, out_h, scale)
                            path = _path("figure", fmt)
                            zf.writestr(path, data)
                        except Exception as exc:
                            record_failure(_path("figure", fmt), "figure", fmt, exc)
                            continue
                        _inventory(path, "figure", "written", unit_ids, fmt=fmt)
                        progress.bytes_written += len(data)
                        progress.figures_written += 1

                if layer_formats and fig is not None:
                    try:
                        names = (
                            retry_unit.layer_names if retry_unit is not None else None
                        )
                        layers = (
                            split_scanpath_layers(fig)
                            if names is None
                            else split_scanpath_layers(fig, only=names)
                        )
                    except Exception as exc:
                        record_layer_set_failure(exc)
                    else:
                        for layer_name, layer_fig in layers.items():
                            artifact = f"layer:{layer_name}"
                            for fmt in layer_formats:
                                if retry_unit is not None and not retry_unit.wants(
                                    artifact, fmt
                                ):
                                    continue
                                # Claim the name even on failure. No later
                                # layer can take the path offered for retry.
                                path = _path(f"layers/{layer_name}", fmt)
                                try:
                                    scale = options.png_scale if fmt == "png" else 1
                                    data = render_figure(
                                        layer_fig, fmt, out_w, out_h, scale
                                    )
                                    zf.writestr(path, data)
                                except Exception as exc:
                                    record_failure(path, artifact, fmt, exc)
                                    continue
                                _inventory(path, artifact, "written", unit_ids, fmt=fmt)
                                progress.bytes_written += len(data)
                                progress.figures_written += 1

            if options.include_plot_config and not combo.get(_UNASSIGNED):
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
                    unit_settings,
                    screen_id=str(screen_id) if screen_slug else None,
                    drift_applied=drift_applied,
                    base_font_size=base_font_size,
                    font_family=font_family,
                )
                # The title/caption are part of how the figure looked, so
                # the manifest records them verbatim alongside the settings.
                cfg["figure_text"] = {"title": title, "caption": caption}
                if not trial_raw_gaze.empty:
                    cfg["raw_gaze"].update(
                        available=True,
                        points=len(trial_raw_gaze),
                        synthesized=bool(settings.get("raw_gaze_synthesized")),
                    )
                data = json.dumps(cfg, indent=2).encode("utf-8")
                path = _path("plot_config", "json")
                zf.writestr(path, data)
                _inventory(path, "plot_config", "written", unit_ids)
                progress.bytes_written += len(data)

            # The word table *is* the measures table — it carries
            # what the dataset brought, and nothing is computed. A trial with no
            # words, or a dataset that brought no measures, writes none.
            per_trial_measures = (
                trial_words
                if measures_wanted and brought and not trial_words.empty
                else None
            )
            family = {}
            if options.include_analysis_family and not combo.get(_UNASSIGNED):
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
            # in for the plain Fixations / Word measures files (two members
            # with one name, and a reader keeps only one of them).
            tables = {
                **_plain_tables(options, trial_words, trial_fix, trial_raw_gaze),
                **{
                    name: frame
                    for name, frame in family.items()
                    if frame is not None and not frame.empty
                },
            }
            if options.combine_trials:
                for artifact, table in tables.items():
                    combined.setdefault(artifact, []).append(table)
            else:
                for fmt in options.table_formats():
                    for artifact, table in tables.items():
                        path = _path(artifact, fmt)
                        progress.bytes_written += _write_table(
                            zf,
                            path,
                            table,
                            fmt,
                            *names_for(artifact),
                            dictionary=csv_dictionary,
                            table=_ARTIFACT_TABLE.get(artifact, "derived"),
                        )
                        _inventory(path, artifact, "written", unit_ids, fmt=fmt)
            if family:
                family_words.append(measured)
                family_fixations.append(family["fixations"])

            progress.finished_trials += 1
            if progress_callback:
                progress_callback(progress)
            emit_status(
                status_callback,
                ExportStage.ENCODING_WRITING,
                f"Wrote {progress.finished_trials} of {progress.total_trials}…",
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
            path = members.own(f"aggregate/all_{artifact}.{fmt}")
            progress.bytes_written += _write_table(
                zf,
                path,
                table,
                fmt,
                *names_for(artifact),
                dictionary=csv_dictionary,
                table=_ARTIFACT_TABLE.get(artifact, "derived"),
            )
            _inventory(path, artifact, "written")
    # The participant table travels as its own per-grain table rather
    # than as columns smeared across the trial files — which is what keeps a
    # reader attribute distinguishable from a per-fixation measurement on the
    # way out, exactly as it is on the way in. Whenever one is attached, narrowed
    # to `options.metadata_fields` (the per-field opt-out; `None` is every
    # field). The frame is handed over out-of-band (the settings dict carries
    # only its fingerprint, so the bulk-export cache signature stays honest —
    # see the note in `tabs._render_export_panel`). API/CLI callers can pass
    # the frame in `settings` directly.
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
            path = members.own(f"metadata/participants.{fmt}")
            progress.bytes_written += _write_table(
                zf,
                path,
                participant_metadata,
                fmt,
                dictionary=csv_dictionary,
                table="metadata",
            )
            _inventory(path, "participant_metadata", "written")
    # And the trial table beside it, on the same terms — its own
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
            path = members.own(f"metadata/trials.{fmt}")
            progress.bytes_written += _write_table(
                zf,
                path,
                trial_metadata,
                fmt,
                dictionary=csv_dictionary,
                table="metadata",
            )
            _inventory(path, "trial_metadata", "written")
    # And the text table, the third grain — same reasoning again.
    text_metadata = _rows_in_scope(
        text_metadata,
        pairs=exported_pairs,
        texts=exported_texts,
        grain="text",
    )
    if text_metadata is not None and not text_metadata.empty:
        for fmt in options.table_formats():
            path = members.own(f"metadata/texts.{fmt}")
            progress.bytes_written += _write_table(
                zf,
                path,
                text_metadata,
                fmt,
                dictionary=csv_dictionary,
                table="metadata",
            )
            _inventory(path, "text_metadata", "written")
    # The exported trials' annotations, in the Data → Annotations file
    # format, so the bundle's notes can be imported back into the app.
    if annotations_kept:
        from .annotations import records_to_store, serialize

        data = serialize(
            records_to_store(annotations_kept), dataset=annotation_dataset
        ).encode("utf-8")
        path = members.own("annotations.json")
        zf.writestr(path, data)
        _inventory(path, "annotations", "written")
        progress.bytes_written += len(data)
    emit_status(
        status_callback,
        ExportStage.FINALIZING,
        "Compressing the zip archive…",
        started_at=started,
        completed=progress.finished_trials,
        total=progress.total_trials,
    )
    if csv_dictionary.files:
        path = members.own("read_csv.R")
        zf.writestr(path, R_IMPORT)
        _inventory(path, "r_import", "written")
        readme_lines += [
            "",
            "## Reading CSV files in R",
            "",
            'From the extracted bundle folder, run `source("read_csv.R")` with jsonlite installed. '
            "The example reads one table. Edit its path to read another. "
            "`columns.json` records the written column types, measurement units where known, "
            "and how to interpret missing values.",
        ]
    if any(written.values()) or csv_dictionary.files:
        path = members.own("columns.json")
        zf.writestr(
            path,
            json.dumps(columns_manifest(written) | csv_dictionary.manifest(), indent=2),
        )
        _inventory(path, "columns", "written")
    zf.writestr(readme_path, "\n".join(readme_lines))
    _write_inventory(zf, inventory, members.own("index.csv"))
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
