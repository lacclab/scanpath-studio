"""Plotly figure builders for scanpath visualization."""

from __future__ import annotations

import base64
import copy
import html
import math
import re
import struct
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import MISSING, dataclass, fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import progress
from .constants import (
    CANVAS_PAD_FRACTION,
    CANVAS_PAD_MIN_PX,
    COMPARE_FIXATION_OPACITY,
    COMPARISON_PALETTE,
    CURRENT_FIX_COLOR,
    CURRENT_FIX_OUTLINE,
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_COLORSCALE,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_HEATMAP_COLORSCALE,
    DEFAULT_LINE_SPACING,
    DEFAULT_MARKER_DURATION_RANGE,
    DEFAULT_MARKER_SIZE_RANGE,
    DEFAULT_MARKER_SIZE_SCALE,
    DEFAULT_SACCADE_WIDTH,
    FIX_MARKER_OUTLINE,
    FIXATION_GLYPH_SIZE_SCALE,
    FIXATION_GLYPH_SYMBOLS,
    FIXATION_SYMBOLS,
    FONT_FAMILY,
    HIGHLIGHTED_TEXT_COLOR,
    HOLLOW_OUTLINE_WIDTH,
    MARKER_SIZE_SCALES,
    OUT_OF_TEXT_COLOR,
    SACCADE_CLASS_COLORS,
    SACCADE_CLASS_LABELS,
    SACCADE_CLASS_ORDER,
    SACCADE_COLOR,
    SACCADE_COLOR_MODES,
    SACCADE_DASH_OPTIONS,
    SACCADE_DIRECTION_CLASSES,
    SACCADE_DIRECTION_FOLD,
    SACCADE_DIRECTION_LABELS,
    SAMPLE_INDEX,
    TRENDLINE_COLOR,
    UNIFORM_COLOR_FIELD,
    WORD_BOX_COLOR,
    WORD_BOX_FILL_COLOR,
    WORD_BOX_FILL_OPACITY,
    WORD_BOX_LINE_OPACITY,
    WORD_LABEL_COLOR,
    compare_palette_color,
)
from .multipart import SCREEN_ID

COLORBAR_LEN_FRACTION = 0.33


@dataclass(frozen=True)
class FigureSettings:
    """Immutable rendering settings shared by every scanpath figure builder.

    The app, headless API, CLI, and exporters used to forward parallel keyword
    lists into three builders with 45–69 parameters each.  This object is the
    single rendering contract instead.  Builder-specific fields live together
    deliberately: switching between static, animated, and comparison views must
    preserve the common visual choices without another translation layer.

    ``canvas_width``, ``canvas_height``, and ``base_font_size`` are the only
    context-dependent required values.  Everything else has the builder's
    behavior-preserving default and may be changed with :meth:`with_overrides`.
    """

    canvas_width: int
    canvas_height: int
    base_font_size: int
    font_family: str = FONT_FAMILY
    x_field: str = "x"
    y_field: str = "y"
    show_words: bool = True
    #: The word boxes' outline colour at ``word_box_line_opacity``, and their
    #: fill — a colour drawn at ``word_box_fill_opacity``. A comparison outlines
    #: each reading's boxes in its scanpath's ``box_color`` style (its fixation
    #: colour by default) instead, so ``word_box_color`` is static/replay only;
    #: the line opacity applies to every outline.
    word_box_color: str = WORD_BOX_COLOR
    word_box_line_opacity: float = WORD_BOX_LINE_OPACITY
    word_box_fill_color: str = WORD_BOX_FILL_COLOR
    word_box_fill_opacity: float = WORD_BOX_FILL_OPACITY
    show_word_labels: bool = True
    show_fixations: bool = True
    show_order: bool = True
    show_saccades: bool = True
    show_heatmap: bool = False
    color_by: str | None = UNIFORM_COLOR_FIELD
    heatmap_metric: str | None = None
    show_saccade_arrows: bool = False
    heatmap_style: str = "Word boxes"
    heatmap_norm: str = "Linear"
    #: The Interpolated heatmap's Gaussian σ in px; ``None`` picks it from the
    #: data (`interpolated_sigma_px`).
    heatmap_sigma_px: float | None = None
    marker_size_range: tuple[int, int] = DEFAULT_MARKER_SIZE_RANGE
    #: How duration maps onto ``marker_size_range`` — one of
    #: ``constants.MARKER_SIZE_SCALES``. The fixed scales ("sqrt", "linear",
    #: "log") map ``marker_duration_range`` (ms) onto it for every figure, so
    #: equal durations draw at equal sizes across trials, comparison sides,
    #: replays and exports; "relative" spans each figure's own durations.
    marker_size_scale: str = DEFAULT_MARKER_SIZE_SCALE
    marker_duration_range: tuple[float, float] = DEFAULT_MARKER_DURATION_RANGE
    #: A few reference circles labelled in ms, drawn under a fixed scale.
    duration_size_legend: bool = True
    order_font_size: int | None = 10
    order_font_color: str = "#111111"
    #: Each colour scale's bar has its own switch and style: the fixations'
    #: (a numeric ``color_by``) and the heatmap's.
    show_fixation_colorbar: bool = True
    fixation_colorbar_orientation: str = "Vertical"
    fixation_colorbar_tickangle: int = 0
    fixation_colorbar_tickfont_size: int = 12
    show_heatmap_colorbar: bool = True
    heatmap_colorbar_orientation: str = "Vertical"
    heatmap_colorbar_tickangle: int = 0
    heatmap_colorbar_tickfont_size: int = 12
    fixation_color_range: tuple[float, float] | None = None
    heatmap_range: tuple[float, float] | None = None
    fixation_colorscale: str = DEFAULT_FIXATION_COLORSCALE
    heatmap_colorscale: str = DEFAULT_HEATMAP_COLORSCALE
    show_raw_gaze: bool = False
    raw_gaze_color: str = "#888888"
    raw_gaze_marker_size: float = 4.0
    raw_gaze_opacity: float = 0.6
    critical_span_style: str = "Mark text"
    highlight_column: str | None = "is_in_aspan"
    saccade_color: str = SACCADE_COLOR
    saccade_style: str = "solid"
    saccade_width: float = DEFAULT_SACCADE_WIDTH
    saccade_color_mode: str = "Uniform"
    saccade_class_colors: dict | None = None
    saccade_type_legend: bool = True
    saccade_classes: Iterable[str] | None = None
    saccade_render_mode: str = "Straight"
    fixation_snap_to_word: bool = False
    hollow_fixations: bool = False
    fixation_opacity: float = 1.0
    fixation_color: str | None = DEFAULT_FIXATION_COLOR
    fixation_symbol: str = DEFAULT_FIXATION_SYMBOL
    text_color: str = WORD_LABEL_COLOR
    highlight_text_color: str = HIGHLIGHTED_TEXT_COLOR
    background_color: str | None = None
    color_by_line: bool = False
    fixation_flags: dict | None = None
    #: CMP-24: scanpath B's own flags in a co-animation (Animate + Compare);
    #: ``None`` gives B the same ``fixation_flags`` as A.
    fixation_flags_b: dict | None = None
    span_border_color: str = "#000000"
    line_spacing: float = DEFAULT_LINE_SPACING
    scale_text_to_boxes: bool = True
    background_image: str | None = None
    background_image_size: tuple[float, float] | None = None
    background_image_origin: tuple[float, float] | None = None
    background_image_opacity: float = 1.0
    fit_to_monitor: bool = False
    show_coordinate_grid: bool = False
    coordinate_grid_spacing: float | None = None
    word_heatmap_col: str | None = None
    word_heatmap_title: str | None = None
    word_hover_measure: str | None = "total_fixation_duration_ms"
    word_hover_fields: Sequence[str] | None = None
    fixation_hover_fields: Sequence[str] | None = None
    show_connectors: bool = False
    connector_y: Sequence[float] | None = None
    illustration_reasons: Sequence[str] | None = None
    #: The Illustration label's text; empty writes "Illustration · <reasons>".
    illustration_text: str = ""
    playback_speed: float = 1.0
    label_a: str = "Scanpath A"
    label_b: str = "Scanpath B"
    show_legend: bool = False
    autoplay: bool = True
    anim_grid_step_ms: float | None = None
    anim_max_frames: int | None = None
    trial_labels: tuple[str, str] | None = None
    layout: str = "overlay"
    style_a: dict | None = None
    style_b: dict | None = None
    # CMP-8 §4 — scanpath B's own screen, honoured *only* by
    # `_make_split_comparison_figure` (side-by-side / stacked). `None` means "the
    # same screen as A", which is every same-dataset comparison and so leaves
    # every existing figure byte-identical. Overlay never needs these: CMP-11
    # lets a cross-dataset pair overlay only when both screens are equal, so
    # there is no second canvas for it to reconcile.
    canvas_b: tuple[int, int] | None = None
    background_image_b: str | None = None
    background_image_size_b: tuple[float, float] | None = None
    background_image_origin_b: tuple[float, float] | None = None
    # CMP-11 — which reading supplies the stimulus layer (word boxes + labels)
    # on an OVERLAY: "both" (the default, and byte-identical to pre-CMP-11),
    # "a", or "b". Two datasets' AOIs coincide only when the text is identical,
    # so an overlay across corpora can otherwise stack two offset sets of
    # rectangles. Split layouts ignore it — each panel owns its own stimulus,
    # and hiding one panel's boxes would just leave a blank half.
    compare_stimulus: str = "both"
    # DATA-66 — the dataset's own names for the columns the figure's text names
    # (hover rows, colour-bar and legend titles, non-spatial axis titles),
    # canonical column → label. Built by the caller (`tabs`); not a figure
    # option, so no option set, link or `render` flag carries it.
    column_labels: dict | None = None

    @classmethod
    def from_mapping(
        cls,
        settings: FigureSettings | Mapping[str, Any] | None = None,
        /,
        **overrides: Any,
    ) -> FigureSettings:
        """Build settings from another instance or a plain option mapping."""
        valid = {field.name for field in fields(cls)}
        unknown = sorted(set(overrides) - valid)
        if isinstance(settings, cls):
            if unknown:
                raise TypeError(f"Unknown figure settings: {', '.join(unknown)}")
            return replace(settings, **overrides) if overrides else settings
        values = dict(settings or {})
        unknown = sorted((set(values) | set(overrides)) - valid)
        if unknown:
            raise TypeError(f"Unknown figure settings: {', '.join(unknown)}")
        values.update(overrides)
        return cls(**values)

    def with_overrides(self, **overrides: Any) -> FigureSettings:
        """Return a copy with the named settings replaced."""
        return self.from_mapping(self, **overrides)

    def for_builder(self, names: Iterable[str]) -> dict[str, Any]:
        """Return just the fields consumed by one concrete renderer."""
        return {name: getattr(self, name) for name in names}

    @classmethod
    def defaults(cls, names: Iterable[str]) -> dict[str, Any]:
        """Return dataclass defaults for the requested non-context fields."""
        defaults: dict[str, Any] = {}
        by_name = {field.name: field for field in fields(cls)}
        for name in names:
            field = by_name.get(name)
            if field is None:
                continue
            if field.default is not MISSING:
                defaults[name] = field.default
        return defaults


#: The figure options that take one of a fixed set of values → those values,
#: spelt as the builders compare them. `normalize_option_values` reads any
#: spelling of one (case, spaces, ``-`` / ``_`` and ``/`` ignored, so the CLI's
#: ``word-boxes`` and ``mark-border`` work) and refuses anything else, so a
#: script never gets the default drawn in place of a value it misspelt.
FIGURE_OPTION_CHOICES: dict[str, tuple[str, ...]] = {
    "heatmap_style": ("Word boxes", "Interpolated"),
    "heatmap_norm": ("Linear", "Log"),
    "critical_span_style": ("Mark text", "Mark border", "None"),
    "saccade_color_mode": tuple(SACCADE_COLOR_MODES),
    "saccade_render_mode": ("Straight", "Arc"),
    "saccade_style": tuple(SACCADE_DASH_OPTIONS.values()),
    "marker_size_scale": tuple(MARKER_SIZE_SCALES),
    "fixation_symbol": tuple(FIXATION_SYMBOLS),
    "fixation_colorbar_orientation": ("Vertical", "Horizontal"),
    "heatmap_colorbar_orientation": ("Vertical", "Horizontal"),
    "compare_stimulus": ("both", "a", "b"),
}


def _choice_key(value: object) -> str:
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


#: Other spellings a choice is known by: the CLI's flag names and the app's
#: labels where they differ from the value (``Dashed`` is ``dash``).
_CHOICE_ALIASES: dict[str, dict[str, str]] = {
    "saccade_color_mode": {
        "type": "By type",
        "direction": "Forward / regression",
        "bydirection": "Forward / regression",
    },
    "saccade_render_mode": {"arcs": "Arc"},
    "saccade_style": {
        _choice_key(label): value for label, value in SACCADE_DASH_OPTIONS.items()
    },
}


def normalize_option_value(name: str, value: object) -> object:
    """``value`` for the enumerated figure option ``name``, spelt as the
    builders compare it; any other option's value is returned as it is.

    Raises ``ValueError`` listing the choices for a value that is none of
    them. ``critical_span_style=None`` is the app's "None" (no marking)."""
    choices = FIGURE_OPTION_CHOICES.get(name)
    if choices is None:
        return value
    if value is None and "None" in choices:
        return "None"
    key = _choice_key(value)
    for choice in choices:
        if _choice_key(choice) == key:
            return choice
    alias = _CHOICE_ALIASES.get(name, {}).get(key)
    if alias is not None:
        return alias
    raise ValueError(f"Unknown {name} {value!r}; choose one of {', '.join(choices)}.")


def normalize_option_values(options: Mapping[str, Any]) -> dict[str, Any]:
    """``options`` with every enumerated value read by
    `normalize_option_value` (inside ``style_a`` / ``style_b`` too)."""
    out = {name: normalize_option_value(name, value) for name, value in options.items()}
    for side in ("style_a", "style_b"):
        style = out.get(side)
        if isinstance(style, Mapping):
            out[side] = {
                key: normalize_option_value(key, value) for key, value in style.items()
            }
    return out


def _sample_colorscale_colors(
    values, colorscale: str, cmin: float | None, cmax: float | None
) -> object:
    """Map numeric values to concrete CSS colours via a named Plotly colorscale.

    Used for hollow markers: Plotly can render a colorscale on a marker *fill*
    but not on its outline, so the gradient is sampled to literal colours that
    can sit on ``marker.line.color``. Falls back to a single outline colour if
    sampling is unavailable.
    """
    try:
        from plotly.colors import sample_colorscale
    except Exception:
        return FIX_MARKER_OUTLINE
    vals = pd.to_numeric(pd.Series(list(values)), errors="coerce")
    lo = float(cmin) if cmin is not None else float(vals.min())
    hi = float(cmax) if cmax is not None else float(vals.max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        norm = [0.5] * len(vals)
    else:
        norm = ((vals.clip(lo, hi) - lo) / (hi - lo)).fillna(0.0).tolist()
    try:
        return sample_colorscale(colorscale, norm)
    except Exception:
        return FIX_MARKER_OUTLINE


def _make_hollow(marker: dict) -> dict:
    """Return a copy of a fixation marker dict rendered as outline-only.

    The fill colour is moved onto the outline (so the colour is preserved) and
    the fill itself is made transparent. Numeric colorscale colours are sampled
    to concrete CSS colours because Plotly can't map a colorscale onto an
    outline. The colorbar is dropped in hollow mode (it needs the coloured fill).
    """
    m = dict(marker)
    color = m.get("color")
    colorscale = m.get("colorscale")
    if colorscale is not None and color is not None and not isinstance(color, str):
        outline_color = _sample_colorscale_colors(
            color, colorscale, m.get("cmin"), m.get("cmax")
        )
    else:
        outline_color = color if color is not None else FIX_MARKER_OUTLINE
    line = dict(m.get("line") or {})
    line["color"] = outline_color
    line["width"] = HOLLOW_OUTLINE_WIDTH
    m["line"] = line
    m["color"] = "rgba(0,0,0,0)"
    m["colorscale"] = None
    m["showscale"] = False
    m["colorbar"] = None
    return m


#: The numeric columns a figure places, sizes or times things by.
_PLOTTED_NUMBERS = ("x", "y", "width", "height", "duration_ms", "timestamp_ms")
#: A word whose box has an infinite edge has no box to draw.
_WORD_BOX_COLUMNS = ("x", "y", "width", "height")


def _finite_for_plotting(
    frame: pd.DataFrame | None,
    extra: Iterable[str] = (),
    *,
    drop_on: Iterable[str] = (),
) -> pd.DataFrame | None:
    """``frame`` with ±inf in its plotted numbers read as missing.

    Data checks reports such rows and keeps them in every table; the figure
    cannot place, size or time them, so it draws them as it draws a missing
    value — no marker and no saccade to or from them, the smallest marker for a
    duration, a replay timed by durations. A row infinite in a ``drop_on``
    column is left out (a word box). Copies only when there is one."""
    if frame is None or frame.empty:
        return frame
    numbers = {
        c: pd.to_numeric(frame[c], errors="coerce").astype(float)
        for c in dict.fromkeys((*_PLOTTED_NUMBERS, *extra))
        if c in frame.columns
    }
    infinite = {c: np.isinf(v) for c, v in numbers.items()}
    infinite = {c: m for c, m in infinite.items() if m.any()}
    if not infinite:
        return frame
    out = frame.copy()
    drop = pd.Series(False, index=frame.index)
    for column, mask in infinite.items():
        out[column] = numbers[column].mask(mask)
        if column in drop_on:
            drop |= mask
    return out[~drop] if drop.any() else out


def _compute_axis_ranges(
    canvas_width: int,
    canvas_height: int,
    *frames_with_xy: tuple[pd.DataFrame | None, str, str],
    word_frames: Iterable[pd.DataFrame] = (),
    fit_to_monitor: bool = False,
) -> tuple[list, list, float | None, float | None, float | None, float | None]:
    """Compute padded x/y ranges from any number of (frame, x_col, y_col) tuples.

    word_frames contribute box-extent bounds: x, x+width and y, y+height.
    Falls back to (0..canvas_width, canvas_height..0) when there's no data.
    Returns: x_range, y_range (y inverted), and the unpadded mins/maxs.

    With ``fit_to_monitor`` the range always spans the full virtual monitor
    (0..canvas_width, canvas_height..0) regardless of where the data sits, so the
    whole presentation screen is shown and the scanpath appears at its true
    on-monitor position rather than the view cropping to the data extent. The
    returned data mins/maxs still describe the actual data (they size the
    interpolated heatmap grid), so only the visible window changes.
    """
    x_candidates: list = []
    y_candidates: list = []

    for df, x_col, y_col in frames_with_xy:
        if df is None or df.empty:
            continue
        if x_col in df.columns:
            x_candidates.extend([df[x_col].min(), df[x_col].max()])
        if y_col in df.columns:
            y_candidates.extend([df[y_col].min(), df[y_col].max()])

    for df in word_frames:
        if df is None or df.empty:
            continue
        x_candidates.extend([df["x"].min(), (df["x"] + df["width"]).max()])
        y_candidates.extend([df["y"].min(), (df["y"] + df["height"]).max()])

    x_range = [0, canvas_width]
    y_range = [canvas_height, 0]
    if not x_candidates or not y_candidates:
        return x_range, y_range, None, None, None, None

    x_min = float(np.nanmin(x_candidates))
    x_max = float(np.nanmax(x_candidates))
    y_min = float(np.nanmin(y_candidates))
    y_max = float(np.nanmax(y_candidates))

    if fit_to_monitor:
        # Show the whole monitor; the scanpath keeps its true on-screen position.
        # Real data mins/maxs are still returned (heatmap-grid extent).
        return [0, canvas_width], [canvas_height, 0], x_min, x_max, y_min, y_max

    x_span = max(x_max - x_min, 1.0)
    y_span = max(y_max - y_min, 1.0)
    pad_x = max(CANVAS_PAD_MIN_PX, CANVAS_PAD_FRACTION * x_span)
    pad_y = max(CANVAS_PAD_MIN_PX, CANVAS_PAD_FRACTION * y_span)
    x_range = [x_min - pad_x, x_max + pad_x]
    y_range = [y_max + pad_y, y_min - pad_y]
    return x_range, y_range, x_min, x_max, y_min, y_max


@dataclass(frozen=True)
class CoordinateGridTicks:
    """Deterministic, zero-anchored screen-coordinate tick contract."""

    major_spacing: float
    minor_spacing: float
    x_values: tuple[float, ...]
    x_labels: tuple[str, ...]
    y_values: tuple[float, ...]
    y_labels: tuple[str, ...]


def _nice_grid_spacing(raw: float) -> float:
    """Round a positive interval up to the 1/2/5×10ⁿ sequence."""
    exponent = math.floor(math.log10(max(raw, 1e-12)))
    unit = 10.0**exponent
    normalized = raw / unit
    for candidate in (1.0, 2.0, 5.0, 10.0):
        if normalized <= candidate:
            return candidate * unit
    return 10.0 * unit


def _anchored_grid_values(lo: float, hi: float, spacing: float) -> tuple[float, ...]:
    """Ticks clipped to ``lo..hi`` and anchored at global screen coordinate 0."""
    lo, hi = min(lo, hi), max(lo, hi)
    first = math.ceil((lo - spacing * 1e-9) / spacing)
    last = math.floor((hi + spacing * 1e-9) / spacing)
    count = max(0, last - first + 1)
    if count > 10_000:
        raise ValueError(
            "Coordinate-grid spacing creates more than 10,000 ticks; choose a larger interval."
        )
    return tuple(round(index * spacing, 10) for index in range(first, last + 1))


def _grid_label(value: float) -> str:
    return f"{value:g}"


def coordinate_grid_ticks(
    x_range: Sequence[float],
    y_range: Sequence[float],
    *,
    spacing: float | None = None,
    rendered_width: int = 900,
    rendered_height: int = 650,
    monitor_bounds: tuple[float, float, float, float] | None = None,
) -> CoordinateGridTicks:
    """Return screen-X/Y grid ticks without changing either visible range.

    ``spacing=None`` chooses one shared 1/2/5×10ⁿ major interval for both axes.
    Manual intervals stay exact. Labels are thinned when the rendered display
    could not fit them, while the underlying tick/grid positions remain stable.
    ``monitor_bounds`` is accepted to make the coordinate frame explicit; ticks
    are intentionally clipped to the *visible* ranges and always anchored at
    screen zero, so cropped/full-monitor transitions cannot shift the grid.
    """
    if len(x_range) != 2 or len(y_range) != 2:
        raise ValueError("Coordinate-grid ranges must each contain two values.")
    if monitor_bounds is not None and len(monitor_bounds) != 4:
        raise ValueError("monitor_bounds must be (x_min, x_max, y_min, y_max).")
    x_span = abs(float(x_range[1]) - float(x_range[0]))
    y_span = abs(float(y_range[1]) - float(y_range[0]))
    if spacing is None:
        target_x = x_span / max(float(rendered_width) / 90.0, 1.0)
        target_y = y_span / max(float(rendered_height) / 70.0, 1.0)
        major = _nice_grid_spacing(max(target_x, target_y, 1.0))
    else:
        major = float(spacing)
        if not math.isfinite(major) or major <= 0:
            raise ValueError(
                "Coordinate-grid spacing must be a positive finite number."
            )
    x_values = _anchored_grid_values(float(x_range[0]), float(x_range[1]), major)
    y_values = _anchored_grid_values(float(y_range[0]), float(y_range[1]), major)

    def _labels(
        values: tuple[float, ...], pixels: int, minimum_px: int
    ) -> tuple[str, ...]:
        capacity = max(int(pixels) // minimum_px, 1)
        stride = max(1, math.ceil(len(values) / capacity))
        return tuple(
            _grid_label(value) if index % stride == 0 else ""
            for index, value in enumerate(values)
        )

    return CoordinateGridTicks(
        major_spacing=major,
        minor_spacing=major / 5.0,
        x_values=x_values,
        x_labels=_labels(x_values, rendered_width, 68),
        y_values=y_values,
        y_labels=_labels(y_values, rendered_height, 42),
    )


_GRID_LEFT_RESERVE_PX = 52
_GRID_BOTTOM_RESERVE_PX = 36
_GRID_TICK_FONT_PX = 18  # remains legible after true-scale responsive downscaling


def _coordinate_grid_axis_options(
    ticks: CoordinateGridTicks, *, axis: str
) -> dict[str, Any]:
    """Plotly axis options for one restrained major/minor coordinate grid."""
    values = ticks.x_values if axis == "x" else ticks.y_values
    labels = ticks.x_labels if axis == "x" else ticks.y_labels
    return dict(
        showticklabels=True,
        showgrid=True,
        tickmode="array",
        tickvals=list(values),
        ticktext=list(labels),
        ticks="outside",
        ticklen=4,
        tickwidth=1,
        tickcolor="#667085",
        tickfont=dict(size=_GRID_TICK_FONT_PX, color="#475467"),
        gridcolor="rgba(71,84,103,0.22)",
        gridwidth=1,
        zeroline=True,
        zerolinecolor="rgba(16,24,40,0.42)",
        zerolinewidth=1.25,
        minor=dict(
            showgrid=True,
            dtick=ticks.minor_spacing,
            gridcolor="rgba(71,84,103,0.09)",
            gridwidth=0.5,
            ticks="",
        ),
    )


def _apply_coordinate_grid_axes(
    xaxis: dict,
    yaxis: dict,
    *,
    show: bool,
    spacing: float | None,
    x_range: Sequence[float],
    y_range: Sequence[float],
    rendered_width: int,
    rendered_height: int,
) -> None:
    """Mutate spatial axis dicts only when the optional grid is enabled."""
    if not show:
        return
    ticks = coordinate_grid_ticks(
        x_range,
        y_range,
        spacing=spacing,
        rendered_width=rendered_width,
        rendered_height=rendered_height,
    )
    xaxis.update(_coordinate_grid_axis_options(ticks, axis="x"))
    yaxis.update(_coordinate_grid_axis_options(ticks, axis="y"))


# Cap the *fixed* render size so the true-to-scale plot (rendered at exactly
# these pixels via tabs._render_true_scale_chart) fits a typical research display
# without horizontal scrolling. Aspect ratio is preserved when shrinking — both
# dims scale together, so boxes/text/fixations keep one true scale. A wider
# monitor just leaves margin (the plot is "narrower than the column", never
# stretched); a narrower window scrolls rather than distorting.
_DISPLAY_MAX_HEIGHT = 690
_DISPLAY_MAX_WIDTH = 960


def _fit_display_size(
    canvas_width: int,
    canvas_height: int,
    x_range: list,
    y_range: list,
    spatial_axes: bool,
) -> tuple[int, int]:
    """Return (width, height) for `fig.update_layout` so the plot fits onscreen.

    With `scaleanchor="x", scaleratio=1` the plot domain shrinks to the data
    aspect ratio, leaving large blank vertical strips when the figure box is
    the full monitor height. We match the figure box to the actual plot
    domain — and additionally clamp both dims so the whole plot fits in one
    viewport without scrolling. Falls back to (canvas_w, canvas_h) when axes
    aren't spatial or the data range is degenerate.
    """
    if not spatial_axes:
        return canvas_width, canvas_height
    x_span = x_range[1] - x_range[0]
    y_span = y_range[0] - y_range[1]  # y_range is inverted [y_max, y_min]
    if x_span <= 0 or y_span <= 0:
        return canvas_width, canvas_height
    aspect = x_span / y_span
    w, h = canvas_width, round(canvas_width / aspect)
    # Shrink (preserving aspect) until both dims fit the viewport caps.
    if h > _DISPLAY_MAX_HEIGHT:
        h = _DISPLAY_MAX_HEIGHT
        w = round(h * aspect)
    if w > _DISPLAY_MAX_WIDTH:
        w = _DISPLAY_MAX_WIDTH
        h = round(w / aspect)
    return max(w, 100), max(h, 100)


#: The two colour bars' settings (fixations', heatmap's) and their defaults —
#: the one list the app's settings dicts and saved config copy them by.
COLORBAR_DEFAULTS: dict = {
    f.name: f.default
    for f in fields(FigureSettings)
    if f.name.endswith("_colorbar") or "_colorbar_" in f.name
}

# Extra figure size (px) reserved OUTSIDE the equal-aspect plot region for a
# right-side colorbar or a top legend. Without this, Plotly's automargin shrinks
# the scaleanchor'd plot domain to fit them — and because the word labels are
# sized for the full fitted_w x fitted_h plot region, a shrunken plot leaves the
# text overflowing the boxes (the "colorbar / discrete colour legend shrinks the
# plot and breaks the aspect ratio" bug). Mirroring the _CONTROLS_MARGIN_PX trick
# the animation uses for its transport controls, we instead grow the figure by
# the reserve and pin it as an explicit margin, so the plot region stays exactly
# fitted_w x fitted_h whether or not a colorbar/legend is shown.
_COLORBAR_RESERVE_PX = 160
_LEGEND_RESERVE_PX = 60
# Top reserve for the overlay-comparison figure's title + A/B legend (same idea
# as _LEGEND_RESERVE_PX, but the title needs a touch more room).
_OVERLAY_TOP_PX = 64
#: UX-172: the Compare A/B legend is the only thing naming the two readings, so
#: it reads larger than the figure's body text (overlay, split and co-animation).
_COMPARE_LEGEND_FONT_SCALE = 1.3


def _compare_legend_font(base_font_size, font_family=None) -> dict:
    """The A/B legend's font in every Compare figure (UX-172)."""
    font = {"size": round(float(base_font_size or 16) * _COMPARE_LEGEND_FONT_SCALE)}
    if font_family:
        font["family"] = font_family
    return font


# A horizontal colorbar sits below the plot, so it reserves bottom (not right).
_COLORBAR_BOTTOM_PX = 96


def _decoration_margins(
    fitted_w: int,
    fitted_h: int,
    *,
    legend: bool,
    colorbar_right: bool = False,
    colorbar_below: bool = False,
    bottom: int = 0,
    coordinate_grid: bool = False,
) -> dict:
    """Grow a spatial figure so a right/bottom colorbar + top legend sit in
    reserved margin instead of stealing space from the equal-aspect plot region.

    Returns ``{"width", "height", "margin"}`` for ``fig.update_layout``: the plot
    region stays ``fitted_w x fitted_h`` (so the true-to-scale word labels keep
    matching the boxes); ``bottom`` reserves additional space below the plot for
    transport controls (the animation figure); ``colorbar_right`` /
    ``colorbar_below`` reserve room for a vertical / horizontal colour bar —
    both, when the fixations' and the heatmap's bars point different ways.
    """
    right = _COLORBAR_RESERVE_PX if colorbar_right else 0
    cb_bottom = _COLORBAR_BOTTOM_PX if colorbar_below else 0
    top = _LEGEND_RESERVE_PX if legend else 0
    left = _GRID_LEFT_RESERVE_PX if coordinate_grid else 0
    grid_bottom = _GRID_BOTTOM_RESERVE_PX if coordinate_grid else 0
    return {
        "width": fitted_w + left + right,
        "height": fitted_h + top + bottom + cb_bottom + grid_bottom,
        "margin": dict(l=left, r=right, t=top, b=bottom + cb_bottom + grid_bottom),
    }


def _colorbar_reserves(*bars: tuple[bool, str]) -> dict:
    """``colorbar_right`` / ``colorbar_below`` for `_decoration_margins`, from
    each bar's ``(drawn, orientation)``."""
    return {
        "colorbar_right": any(on and o != "Horizontal" for on, o in bars),
        "colorbar_below": any(on and o == "Horizontal" for on, o in bars),
    }


def _colorbar_dict(
    title: str,
    *,
    orientation: str = "Vertical",
    tickangle: int = 0,
    tickfont_size: int = 12,
) -> dict:
    """A styled Plotly colorbar dict (vertical right / horizontal below), with
    rotatable, sizable tick labels and a slim bar."""
    horizontal = orientation == "Horizontal"
    cb = dict(
        title=dict(
            text=title,
            side="top" if horizontal else "right",
            font=dict(size=max(10, int(tickfont_size) + 1)),
        ),
        thickness=14,
        tickangle=int(tickangle),
        tickfont=dict(size=int(tickfont_size)),
        outlinewidth=0,
    )
    if horizontal:
        cb.update(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.04,
            yanchor="top",
            lenmode="fraction",
            len=0.6,
        )
    else:
        cb.update(
            x=1.02,
            xanchor="left",
            y=0.5,
            yanchor="middle",
            lenmode="fraction",
            len=COLORBAR_LEN_FRACTION,
        )
    return cb


def _colorbar_owners(fig: go.Figure) -> list:
    """Every object drawing a colour bar on ``fig``, in trace order: a trace
    with its own scale (``go.Heatmap``) or a trace's marker."""
    owners = []
    for trace in fig.data:
        if getattr(trace, "showscale", None):
            owners.append(trace)
            continue
        marker = getattr(trace, "marker", None)
        if marker is not None and getattr(marker, "showscale", None):
            owners.append(marker)
    return owners


def _arrange_colorbars(fig: go.Figure) -> None:
    """Give each of several colour bars its own place (round-7 review, finding 16).

    `_colorbar_dict` puts every bar of one orientation at one spot, so a
    heatmap's scale and the fixations' were drawn over each other. With two or
    more pointing the same way, vertical bars stand side by side to the right
    of the plot and horizontal ones stack below it, the figure growing by the
    room they take — the plot region, and so the true-to-scale text, keep
    their size. A bar alone in its orientation keeps its geometry exactly (a
    vertical and a horizontal bar each already have their reserved margin).
    Each bar is its own mapping (variable, units, palette, range): none is
    merged into another, so every scale stays readable.
    """
    owners = _colorbar_owners(fig)
    below = [o for o in owners if o.colorbar.orientation == "h"]
    right = [o for o in owners if o.colorbar.orientation != "h"]
    layout = fig.layout
    if len(below) > 1:
        first = below[0].colorbar
        tick_px = float(first.tickfont.size or 12)
        rotated = abs(float(first.tickangle or 0)) > 30
        # Title above the bar, the bar, its tick labels below.
        row_px = 56.0 + 2.0 * tick_px + (2.0 * tick_px if rotated else 0.0)
        height = float(layout.height or 450)
        top, bottom = float(layout.margin.t or 0), float(layout.margin.b or 0)
        plot_h = max(height - top - bottom, 1.0)
        base_y = float(first.y if first.y is not None else -0.04)
        for i, owner in enumerate(below):
            owner.colorbar.y = base_y - i * row_px / plot_h
        grow = (len(below) - 1) * row_px
        fig.update_layout(height=height + grow, margin=dict(b=bottom + grow))
    if len(right) > 1:
        first = right[0].colorbar
        tick_px = float(first.tickfont.size or 12)
        # The bar, its tick labels, then its title read sideways.
        step_px = 70.0 + 3.0 * tick_px
        # Every spatial builder sizes its figure; Plotly's own default otherwise.
        width = float(layout.width or 700)
        left, margin_r = float(layout.margin.l or 0), float(layout.margin.r or 0)
        plot_w = max(width - left - margin_r, 1.0)
        base_x = float(first.x if first.x is not None else 1.02)
        for i, owner in enumerate(right):
            owner.colorbar.x = base_x + i * step_px / plot_w
        new_right = (
            max(margin_r, float(_COLORBAR_RESERVE_PX)) + (len(right) - 1) * step_px
        )
        fig.update_layout(
            width=width + (new_right - margin_r), margin=dict(r=new_right)
        )


# Text in Plotly is sized in screen pixels with no native "data unit" mode, so
# to keep word labels true-to-scale we convert a real (monitor-pixel) font size
# into the figure's screen pixels using the same scale the boxes/fixations use.
_MIN_LABEL_PX = 1.0

# Advance-width / em of a monospaced glyph, used to back the box *width* cap that
# stops long words from colliding when the on-screen font is a touch wider than
# the one the experiment was rendered in. Latin monospace (DejaVu Sans Mono,
# Courier, …) ≈ 0.6 em; in a full-width CJK monospace (Noto Sans Mono CJK) the CJK
# glyphs are a full square (1.0 em) while Latin glyphs are half-width (0.5 em).
# Reading stimuli are monospaced (OneStop, MultiplEYE), so summing per-character
# advances recovers a per-word em (≈ the font size) even for mixed CJK+Latin runs
# (a Chinese paragraph with an English URL), which a single global aspect can't.
_MONO_ASPECT = 0.6
_CJK_LATIN_ASPECT = 0.5
_FULLWIDTH_ASPECT = 1.0
_WIDTH_FIT_MARGIN = 0.92  # leave a sliver of horizontal padding inside each box


def _is_fullwidth(ch: str) -> bool:
    """Whether ``ch`` is an East-Asian wide / full-width glyph (≈ 1 em advance)."""
    o = ord(ch)
    return (
        0x1100 <= o <= 0x115F  # Hangul Jamo
        or 0x2E80 <= o <= 0x303E  # CJK radicals / Kangxi / CJK symbols & punct
        or 0x3041 <= o <= 0x33FF  # Hiragana, Katakana, CJK symbols
        or 0x3400 <= o <= 0x4DBF  # CJK Unified Ext A
        or 0x4E00 <= o <= 0x9FFF  # CJK Unified
        or 0xA000 <= o <= 0xA4CF  # Yi
        or 0xAC00 <= o <= 0xD7A3  # Hangul syllables
        or 0xF900 <= o <= 0xFAFF  # CJK compatibility
        or 0xFF00 <= o <= 0xFF60  # full-width forms
        or 0xFFE0 <= o <= 0xFFE6  # full-width signs
    )


def _latin_advance(words: pd.DataFrame) -> float:
    """Per-em advance of *Latin* glyphs for this corpus' font.

    In a full-width CJK monospace (Noto Sans Mono CJK — MultiplEYE) Latin glyphs
    are half-width (0.5 em); in a plain Latin monospace (Courier/DejaVu — OneStop)
    they're ≈ 0.6 em. Detected from whether the labels are CJK-heavy, so a Chinese
    corpus' embedded English isn't measured with the wrong cell width.
    """
    if "text" not in words.columns:
        return _MONO_ASPECT
    # dropna first: with the Arrow `str` dtype, `.astype(str)` leaves a NaN as a
    # float (it doesn't stringify it), which would break the join + char scan.
    text = "".join(words["text"].dropna().astype(str).tolist())
    if not text:
        return _MONO_ASPECT
    wide = sum(_is_fullwidth(ch) for ch in text)
    return _CJK_LATIN_ASPECT if wide >= 0.3 * len(text) else _MONO_ASPECT


def _line_pitch(words: pd.DataFrame) -> float | None:
    """Median line-to-line distance (data px) of the word boxes.

    The true-to-scale font budget is a fraction of the *line pitch* (the gap
    between consecutive baselines), not the box height: some corpora (MultiplEYE)
    draw AOI boxes tight around the glyph (height ≈ font), while the line slot is
    much taller. OneStop's boxes tile the lines (height == pitch), so this returns
    the same value there and leaves OneStop sizing unchanged. Falls back to the
    median box height when there's only one line or geometry is missing.
    """
    if words.empty or "y" not in words.columns or "height" not in words.columns:
        return None
    from .measures import cluster_word_lines

    heights = pd.to_numeric(words["height"], errors="coerce")
    y_center = pd.to_numeric(words["y"], errors="coerce") + heights.fillna(0) / 2.0
    centers = y_center.groupby(cluster_word_lines(words)).median().sort_values()
    if len(centers) >= 2:
        pitch = float(centers.diff().dropna().median())
        if pitch > 0:
            return pitch
    box_h = float(heights.median()) if heights.notna().any() else None
    return box_h if box_h and box_h > 0 else None


def _width_fit_font(words: pd.DataFrame) -> float | None:
    """Largest font (data px) at which every word still fits its box width.

    Word boxes hug the rendered text, so a word's box width equals the sum of its
    glyph advances. Each glyph advances 1 em (full-width CJK) or ``_latin_advance``
    em (Latin), so ``box_width / Σ advances`` recovers the em ≈ the font size — per
    word, which is correct even for a CJK word boxed beside a half-width Latin URL
    (a single global aspect would size the line from the narrowest run). The
    tightest words bind, so we take a low quantile (robust to one odd box). For an
    all-Latin corpus this reduces exactly to the old ``(box_width / n) / aspect``.
    Returns None when there's no text/width to measure.
    """
    if "width" not in words.columns or "text" not in words.columns:
        return None
    latin_adv = _latin_advance(words)
    widths = pd.to_numeric(words["width"], errors="coerce")
    ems = []
    for text, width in zip(words["text"], widths):
        # Skip a NaN label (Arrow `str` keeps it a float, not "nan") or NaN width —
        # matches the old vectorized path, where both dropped out before the quantile.
        if pd.isna(text) or not np.isfinite(width):
            continue
        units = sum(
            _FULLWIDTH_ASPECT if _is_fullwidth(c) else latin_adv for c in str(text)
        )
        if units > 0:
            ems.append(width / units)
    if not ems:
        return None
    tight = float(pd.Series(ems).quantile(0.05))
    return tight * _WIDTH_FIT_MARGIN if tight > 0 else None


def _display_scale(x_range: list, y_range: list, fitted_w: int, fitted_h: int) -> float:
    """Screen px per data unit for a fixed-size, equal-aspect spatial plot.

    With ``scaleratio=1`` the x and y mappings are identical; we take the min so
    rounding can never make text/markers sized through this overflow the boxes.
    Returns 1.0 for degenerate ranges.
    """
    x_span = x_range[1] - x_range[0]
    y_span = y_range[0] - y_range[1]  # y_range is inverted [y_max, y_min]
    if x_span <= 0 or y_span <= 0:
        return 1.0
    return min(fitted_w / x_span, fitted_h / y_span)


def _word_label_font_px(
    words: pd.DataFrame,
    *,
    scale: float,
    line_spacing: float,
    manual_font_px: float,
    scale_text_to_boxes: bool,
) -> float:
    """Word-label font size in *screen* px so the text stays true-to-scale.

    The experiment's font lives in monitor pixels. To keep the rendered glyphs
    the same physical fraction of the (data-space) word boxes at any display
    size, the font is expressed in data px and multiplied by ``scale`` (screen
    px per data unit):

    - ``scale_text_to_boxes`` (default): one line of text fills
      ``1 / line_spacing`` of the **line pitch** (the median line-to-line distance
      from the data, see :func:`_line_pitch`) — *not* the raw box height, which is
      only equal to the pitch when the boxes tile the lines. For OneStop the boxes
      tile the lines (pitch == height) and ``line_spacing == 3`` (one blank line
      above + below), so the budget is height / 3 as before; for corpora whose AOI
      boxes hug the glyph (MultiplEYE), the pitch is the right, larger budget. The
      size is *also* capped so the longest words still fit their box width (see
      :func:`_width_fit_font`), which keeps the font from colliding; the smaller of
      the two wins.
    - otherwise / no usable boxes: ``manual_font_px`` is treated as the real
      monitor font size and scaled the same way.
    """
    font_data_px = float(manual_font_px)
    if scale_text_to_boxes and not words.empty and "height" in words.columns:
        pitch = _line_pitch(words)
        height_fit = pitch / line_spacing if (pitch and line_spacing > 0) else None
        width_fit = _width_fit_font(words)
        candidates = [c for c in (height_fit, width_fit) if c and c > 0]
        if candidates:
            font_data_px = min(candidates)
    return max(font_data_px * scale, _MIN_LABEL_PX)


_QUALITATIVE_PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


def _resolve_marker_colors(
    color_data: pd.Series | None,
    is_numeric_color: bool,
    uniform_color: str = DEFAULT_FIXATION_COLOR,
) -> tuple[object, list]:
    """Return (marker_color, category_legend) for the fixation scatter trace.

    - Numeric color_data is passed straight through (Plotly maps it via colorscale).
    - Categorical color_data is mapped to a discrete palette so the picker has
      visible effect; the returned legend is a list of (category, hex) pairs the
      caller can render as legend-only scatter traces.
    - No color_data (VIZ-17's uniform default, or a `color_by` column that isn't
      in the frame) paints every marker ``uniform_color``.
    """
    if color_data is None:
        return uniform_color, []
    if is_numeric_color:
        return color_data, []
    series = color_data.fillna("(missing)").astype(str)
    unique_vals = list(pd.unique(series))
    cat_to_color = {
        val: _QUALITATIVE_PALETTE[i % len(_QUALITATIVE_PALETTE)]
        for i, val in enumerate(unique_vals)
    }
    marker_color = [cat_to_color[val] for val in series]
    legend = [(val, cat_to_color[val]) for val in unique_vals]
    return marker_color, legend


def _fixation_category_labels(
    fixations: pd.DataFrame,
    words: pd.DataFrame | None,
    color_by: str | None,
    color_by_line: bool = False,
) -> pd.Series | None:
    """The discrete label each fixation is coloured by, or ``None`` when the
    colouring is not discrete (uniform, numeric, or a column the frame lacks).

    The same labels the static figure draws: ``"Line N"`` / ``"(off-text)"``
    for colour-by-line, against ``words``' own geometry; a categorical column's
    values as strings, ``"(missing)"`` for a gap. Aligned to ``fixations``.
    """
    if fixations.empty:
        return None
    if color_by_line or color_by == "line":
        if words is None or words.empty:
            return None
        from .measures import assign_fixation_lines

        line_ids = assign_fixation_lines(fixations, words)
        return line_ids.map(
            lambda v: f"Line {int(v) + 1}" if pd.notna(v) else "(off-text)"
        )
    if (
        not color_by
        or color_by == UNIFORM_COLOR_FIELD
        or color_by not in fixations.columns
        or pd.api.types.is_numeric_dtype(fixations[color_by])
    ):
        return None
    return fixations[color_by].fillna("(missing)").astype(str)


def _shared_category_colors(
    labels: Sequence[pd.Series | None],
    avoid: Iterable[str] = (),
) -> tuple[list[list[str] | None], list[tuple[str, str]]]:
    """One category→colour mapping across several scanpaths (Compare, the dual
    replay), so a category wears the same colour on A and on B.

    Categories are numbered in order of first appearance, A's before B's.
    ``avoid`` names the scanpaths' own colours, which outline their markers: a
    category never fills in one, or that scanpath's outline would vanish into
    its fill. Returns each scanpath's per-row colours (``None`` where it had no
    labels) and the shared legend.
    """
    present = [series for series in labels if series is not None]
    if not present:
        return [None] * len(labels), []
    taken = {str(color).lower() for color in avoid if color}
    palette = [c for c in _QUALITATIVE_PALETTE if c.lower() not in taken]
    palette = palette or list(_QUALITATIVE_PALETTE)
    order = list(pd.unique(pd.concat(present, ignore_index=True)))
    cat_to_color = {val: palette[i % len(palette)] for i, val in enumerate(order)}
    colors = [
        None if series is None else [cat_to_color[val] for val in series]
        for series in labels
    ]
    return colors, [(val, cat_to_color[val]) for val in order]


def _add_category_legend(
    fig: go.Figure, legend: Sequence[tuple[str, str]], color_label: str
) -> None:
    """Legend-only entries naming each colour category (``label: value``), with
    a "… +N more" entry past the qualitative palette's length."""
    limit = len(_QUALITATIVE_PALETTE)
    for category, color in list(legend)[:limit]:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    size=10,
                    color=color,
                    line=dict(color=FIX_MARKER_OUTLINE, width=0.5),
                ),
                name=f"{_column_name(color_label)}: {category}",
                showlegend=True,
                hoverinfo="skip",
            )
        )
    if len(legend) > limit:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, color="#cccccc"),
                name=f"… +{len(legend) - limit} more",
                showlegend=True,
                hoverinfo="skip",
            )
        )


#: How much larger (font px) the outline layer behind a glyph marker is: a text
#: glyph takes no stroke, so its outline is a second, larger glyph drawn under it.
_GLYPH_OUTLINE_PX = 4.0
#: The outline-only form of each glyph shape, for hollow markers.
_HOLLOW_GLYPHS = {"♥": "♡"}


def _glyph_scatter_traces(
    x, y, marker: dict, glyph: str, **top: Any
) -> list[go.Scatter]:
    """Draw a fixation ``marker`` dict as text glyphs (VIZ-15's ♥), bottom first.

    Plotly's marker-symbol enum has no heart, so every builder draws one as
    text, from the marker dict it would otherwise have used, keeping what that
    dict says: duration→size (an array ``textfont.size``, scaled by
    ``FIXATION_GLYPH_SIZE_SCALE``), the colour (a colorscale is sampled to
    literal colours — ``textfont.color`` takes none), the opacity, and a
    non-default outline (Compare's A/B cue) as a larger glyph underneath in the
    outline colour. A hollow marker becomes the outline glyph (♡) in its
    outline colour. ``top`` goes onto the glyph layer (name, hover, legend);
    the outline layer under it takes no hover and no legend entry.

    The two halves are separate so a replay can state the layers once
    (:func:`_glyph_layers`) and draw them at each frame's positions
    (:func:`_glyph_layer_traces`) without re-sampling the colours.
    """
    return _glyph_layer_traces(x, y, _glyph_layers(marker, glyph, len(x)), **top)


def _glyph_layers(marker: dict, glyph: str, n: int) -> list[dict]:
    """What :func:`_glyph_scatter_traces` draws, bottom first, minus positions.

    One dict per layer — ``text`` / ``textfont`` / ``opacity`` — with the
    colours sampled and the sizes scaled, for ``n`` fixations."""
    sizes = np.asarray(marker.get("size"), dtype=float) * FIXATION_GLYPH_SIZE_SCALE
    sizes = np.broadcast_to(sizes, (n,)) if sizes.ndim == 0 else sizes
    color = marker.get("color")
    line = marker.get("line") or {}
    layers: list[tuple[str, object, np.ndarray]] = []
    if isinstance(color, str) and color == "rgba(0,0,0,0)":
        layers.append(
            (
                _HOLLOW_GLYPHS.get(glyph, glyph),
                line.get("color") or FIX_MARKER_OUTLINE,
                sizes,
            )
        )
    else:
        if (
            marker.get("colorscale") is not None
            and color is not None
            and not isinstance(color, str)
        ):
            color = _sample_colorscale_colors(
                color, marker["colorscale"], marker.get("cmin"), marker.get("cmax")
            )
        elif color is not None and not isinstance(color, str):
            color = list(color)
        outline = line.get("color")
        if isinstance(outline, str) and outline != FIX_MARKER_OUTLINE:
            layers.append((glyph, outline, sizes + _GLYPH_OUTLINE_PX))
        layers.append((glyph, color, sizes))
    opacity = float(marker.get("opacity", 1.0))
    return [
        dict(
            text=[char] * n,
            textfont=dict(color=layer_color, size=list(layer_sizes)),
            opacity=opacity,
        )
        for char, layer_color, layer_sizes in layers
    ]


def _glyph_layer_traces(
    x, y, layers: list[dict], *, make: Callable = go.Scatter, **top: Any
) -> list:
    """:func:`_glyph_layers`' layers drawn at ``x``/``y``; ``top`` on the last.

    ``make=dict`` returns the traces unvalidated, for a replay frame (see the
    frame loop in :func:`_render_scanpath_animation`)."""
    traces = []
    for i, layer in enumerate(layers):
        is_top = i == len(layers) - 1
        traces.append(
            make(
                x=x,
                y=y,
                mode="text",
                text=layer["text"],
                textfont=layer["textfont"],
                textposition="middle center",
                opacity=layer["opacity"],
                **(
                    top
                    if is_top
                    else dict(
                        hoverinfo="skip",
                        showlegend=False,
                        legendgroup=top.get("legendgroup"),
                    )
                ),
            )
        )
    return traces


def _glyph_colorbar_trace(marker: dict, values) -> go.Scatter | None:
    """The colour bar a glyph marker's numeric colouring would have drawn.

    A text glyph carries no colorscale, so the bar rides on an invisible
    two-point marker trace pinned to the same range."""
    if not marker.get("showscale") or marker.get("colorscale") is None:
        return None
    numeric = pd.to_numeric(pd.Series(list(values)), errors="coerce")
    lo = marker.get("cmin")
    hi = marker.get("cmax")
    lo = float(numeric.min()) if lo is None else float(lo)
    hi = float(numeric.max()) if hi is None else float(hi)
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return None
    return go.Scatter(
        x=[None, None],
        y=[None, None],
        mode="markers",
        marker=dict(
            color=[lo, hi],
            colorscale=marker["colorscale"],
            cmin=lo,
            cmax=hi,
            showscale=True,
            colorbar=marker.get("colorbar"),
            size=0,
        ),
        name="colour scale",
        showlegend=False,
        hoverinfo="skip",
    )


def _marker_symbol(symbol: str | None) -> str:
    """A ``marker.symbol`` Plotly will accept.

    The VIZ-15 glyph shapes (♥) aren't in Plotly's symbol enum — the static
    figure draws them as text instead — so anywhere that *must* hand Plotly a
    marker symbol falls back to the default rather than raising.
    """
    if not symbol or symbol in FIXATION_GLYPH_SYMBOLS:
        return DEFAULT_FIXATION_SYMBOL
    return symbol


def _duration_bounds(duration_range) -> tuple[float, float]:
    """The fixed scale's (lo, hi) in ms, ordered and never empty."""
    lo, hi = sorted(float(v) for v in duration_range)
    lo = max(lo, 1.0)  # log needs a positive floor; no fixation is shorter
    return lo, max(hi, lo + 1.0)


def _scale_transform(scale: str):
    try:
        return {"sqrt": np.sqrt, "linear": lambda d: d, "log": np.log}[scale]
    except KeyError:
        raise ValueError(
            f"Unknown marker_size_scale {scale!r}; choose one of "
            f"{', '.join(MARKER_SIZE_SCALES)}."
        ) from None


def _compute_marker_sizes(
    durations: pd.Series,
    size_range: tuple[int, int] = DEFAULT_MARKER_SIZE_RANGE,
    scale: str = DEFAULT_MARKER_SIZE_SCALE,
    duration_range: tuple[float, float] = DEFAULT_MARKER_DURATION_RANGE,
) -> np.ndarray:
    """Map fixation durations to marker sizes (px diameter).

    A fixed ``scale`` ("sqrt" / "linear" / "log") maps ``duration_range`` (ms)
    onto ``size_range`` through that curve, the same for every figure: a
    duration at or below the lower bound gets the smallest marker, at or above
    the upper bound the largest, so a fixation's size never depends on the
    other fixations drawn beside it. ``"relative"`` is the original scale —
    linear between this set's own shortest and longest durations — which is
    why it is only comparable within one figure.
    """
    durations = pd.to_numeric(durations, errors="coerce").fillna(0)
    min_size, max_size = size_range
    if scale == "relative":
        d_min, d_max = float(durations.min()), float(durations.max())
        if d_max - d_min > 0:
            return np.interp(durations, (d_min, d_max), (min_size, max_size))
        return np.full(len(durations), (min_size + max_size) / 2)
    transform = _scale_transform(scale)
    lo, hi = _duration_bounds(duration_range)
    clipped = np.clip(durations.to_numpy(dtype=float), lo, hi)
    f_lo, f_hi = float(transform(lo)), float(transform(hi))
    frac = (transform(clipped) - f_lo) / (f_hi - f_lo)
    return min_size + frac * (max_size - min_size)


def _settings_size_scale(settings: FigureSettings) -> dict:
    """The duration-scale keywords of :func:`_compute_marker_sizes`."""
    return {
        "scale": settings.marker_size_scale,
        "duration_range": settings.marker_duration_range,
    }


def _duration_key_references(duration_range) -> list[tuple[float, str]]:
    """The durations a size key draws, each with its label.

    The two bounds (labelled ``≤`` / ``≥``, because everything beyond them
    clamps) plus the round values 100/200/400/800/1600 ms that fall strictly
    between them — at most three of those, so the key stays compact."""
    lo, hi = _duration_bounds(duration_range)
    inner = [d for d in (100, 200, 400, 800, 1600) if lo < d < hi][:3]
    if not inner and hi - lo > 2:
        inner = [round((lo + hi) / 2)]
    refs = [(lo, f"≤{lo:g}")]
    refs += [(float(d), f"{d:g}") for d in inner]
    refs.append((hi, f"≥{hi:g} ms"))
    return refs


# Name of the size key's label annotations, so the layer split can find them.
_SIZE_KEY_NAME = "duration_size_key"
# The Illustration stamp shares the size key's bottom-right corner.
_ILLUSTRATION_LABEL_NAME = "illustration_label"


def _stack_bottom_right(fig: go.Figure) -> None:
    """Lift the Illustration stamp above the duration size key when both are drawn.

    Both sit in the plot's bottom-right corner, and either can be added first
    (the public builders stamp the label inside ``make_scanpath_figure`` and add
    the key after; the app's replay does the reverse), so each calls this once
    it is on the figure. The key's height is read off its own circles — the
    only pixel-sized circles in paper coordinates — so the stamp clears the
    largest one at any size range."""
    key_top = [
        float(sh.y1)
        for sh in fig.layout.shapes or ()
        if sh.type == "circle" and sh.yref == "paper" and sh.ysizemode == "pixel"
    ]
    if not key_top:
        return
    for ann in fig.layout.annotations or ():
        if ann.name == _ILLUSTRATION_LABEL_NAME:
            ann.yshift = max(key_top) + 4.0


def _add_duration_size_key(
    fig: go.Figure,
    size_range: tuple[int, int],
    scale: str,
    duration_range,
    *,
    font_family: str | None = None,
) -> None:
    """Draw the fixed duration scale's key: reference circles labelled in ms.

    Pixel-sized shapes anchored in the plot's bottom-right corner (paper
    coordinates), so each circle is exactly the diameter a fixation of that
    duration gets — at any canvas size and through every export path, since
    they are layout shapes rather than a trace. Nothing is drawn for the
    relative scale: its sizes mean something only inside one figure."""
    if scale == "relative":
        return
    refs = _duration_key_references(duration_range)
    sizes = _compute_marker_sizes(
        pd.Series([d for d, _ in refs]), size_range, scale, duration_range
    )
    slot = max(float(size_range[1]), 30.0) + 8.0  # px per reference circle
    label_px = 16.0
    pad = 8.0
    n = len(refs)
    for i, ((_, label), size) in enumerate(zip(refs, sizes)):
        # Centre of slot i, counted from the right edge, in px.
        dx = -(pad + (n - i - 0.5) * slot)
        r = float(size) / 2.0
        cy = pad + label_px + float(size_range[1]) / 2.0
        fig.add_shape(
            type="circle",
            xref="paper",
            yref="paper",
            xsizemode="pixel",
            ysizemode="pixel",
            xanchor=1,
            yanchor=0,
            x0=dx - r,
            x1=dx + r,
            y0=cy - r,
            y1=cy + r,
            line=dict(color="#555555", width=1),
            fillcolor="rgba(120,120,120,0.35)",
            layer="above",
            # Rides the fixations layer of a separable export (VIZ-5).
            name=_shape_layer_tag("fixations"),
        )
        fig.add_annotation(
            x=1,
            y=0,
            xref="paper",
            yref="paper",
            xshift=dx,
            yshift=pad + label_px / 2.0,
            text=label,
            showarrow=False,
            xanchor="center",
            yanchor="middle",
            font=dict(size=10, color="#444444", family=font_family or FONT_FAMILY),
            name=_SIZE_KEY_NAME,
        )
    _stack_bottom_right(fig)


# VIZ-9 "linear reading" mode: draw saccades as upward arcs instead of straight
# connectors. The apex rises by _ARCH_FRAC of the saccade's horizontal span; each
# arc is sampled into _ARCH_SAMPLES points so it stays smooth in the true-scale
# embed. `arch_frac=None` (the default everywhere) keeps the straight connectors.
_ARCH_FRAC = 0.28
_ARCH_SAMPLES = 20


def _arch_control_point(
    x0: float, y0: float, x1: float, y1: float, frac: float
) -> tuple[float, float]:
    """Control point of the quadratic Bézier arch drawn between two fixations.

    Single source of truth for the arch geometry: ``_arch_points`` samples the
    curve it defines and ``_arch_point_and_tangent`` (the arrowheads, BUG-9)
    evaluates the same curve, so the marker can never drift off the drawn line.
    Screen y grows downward, so the control point sits *above* the chord."""
    return (x0 + x1) / 2.0, min(y0, y1) - frac * abs(x1 - x0)


def _arch_points(
    x0: float, y0: float, x1: float, y1: float, frac: float, n: int = _ARCH_SAMPLES
) -> tuple[list, list]:
    """Sample a quadratic Bézier arch from (x0,y0) to (x1,y1), bulging upward.

    Screen y grows downward, so the control point is *above* the chord (smaller
    y). Returns (xs, ys) of length ``n`` including both endpoints. A NaN endpoint
    propagates to NaN samples, which Plotly simply skips."""
    cx, cy = _arch_control_point(x0, y0, x1, y1, frac)
    ts = np.linspace(0.0, 1.0, n)
    xs = ((1 - ts) ** 2) * x0 + 2 * (1 - ts) * ts * cx + (ts**2) * x1
    ys = ((1 - ts) ** 2) * y0 + 2 * (1 - ts) * ts * cy + (ts**2) * y1
    return xs.tolist(), ys.tolist()


def _arch_apex_y(x0: float, y0: float, x1: float, y1: float, frac: float) -> float:
    """Topmost (smallest) ``y`` reached by the drawn arch — its true apex (BUG-13).

    Minimises ``y(t)`` over the SAME quadratic ``_arch_points`` samples and
    ``_arch_point_and_tangent`` evaluates, instead of reading off one sampled
    parameter. Writing the curve as ``y(t) = y0 + 2t(cy - y0) + t^2 * d`` with
    ``d = y0 - 2*cy + y1`` gives the closed-form extremum ``t* = (y0 - cy)/d`` and
    the value ``y0 - (y0 - cy)^2 / d``. The control point is at or above both
    endpoints (``cy <= min(y0, y1)``), so ``d >= 0`` and ``t*`` always lands in
    ``[0, 1]``.

    For a level saccade the peak is at ``t = 0.5`` (the old estimate), but as the
    endpoints diverge in ``y`` it slides toward the higher one and rises well
    above the ``t = 0.5`` point — which is why a wide, steeply-sloped arc used to
    clip against the top of the view.
    """
    _, cy = _arch_control_point(x0, y0, x1, y1, frac)
    denom = y0 - 2.0 * cy + y1
    if denom <= 0.0:
        # Degenerate: zero rise and level endpoints — the "arch" is a flat line.
        return min(y0, y1)
    t = (y0 - cy) / denom
    if t <= 0.0:
        return y0
    if t >= 1.0:
        return y1
    return y0 - (y0 - cy) ** 2 / denom


def _extend_segment(
    xs: list, ys: list, x0, y0, x1, y1, arch_frac: float | None
) -> None:
    """Append one saccade segment (straight, or an arch when ``arch_frac``) to the
    None-separated ``xs``/``ys`` accumulators."""
    if arch_frac is None:
        xs.extend([x0, x1, None])
        ys.extend([y0, y1, None])
    else:
        ax, ay = _arch_points(x0, y0, x1, y1, arch_frac)
        xs.extend(ax + [None])
        ys.extend(ay + [None])


def _saccade_segments(
    fix_df: pd.DataFrame,
    x_col: str,
    y_col: str,
    arch_frac: float | None = None,
) -> tuple[list, list]:
    """Return concatenated x/y arrays separated by None for a single saccade trace.

    ``arch_frac`` (VIZ-9) draws each segment as an upward arc instead of a straight
    line."""
    if len(fix_df) < 2:
        return [], []
    ordered = fix_df.sort_values("timestamp_ms")
    xs: list = []
    ys: list = []
    x_vals = ordered[x_col].tolist()
    y_vals = ordered[y_col].tolist()
    for i in range(len(ordered) - 1):
        _extend_segment(
            xs, ys, x_vals[i], y_vals[i], x_vals[i + 1], y_vals[i + 1], arch_frac
        )
    return xs, ys


def _saccade_segments_by_class(
    fix_df: pd.DataFrame,
    x_col: str,
    y_col: str,
    classes: pd.Series,
    arch_frac: float | None = None,
) -> dict:
    """Group saccade segments by reading class → ``{class: (xs, ys)}`` (VIZ-8).

    Each segment (fixation i → i+1) takes the class of its *departing* fixation
    (``classes[i]``), so it matches ``measures.classify_saccades``. Segments with
    no class (``None``/NaN — the last fixation, or an unclassifiable one) fall
    into ``"other"`` so they still draw. Each class's arrays are None-separated,
    ready for one Scatter trace per class. ``arch_frac`` (VIZ-9) arcs each
    segment."""
    if len(fix_df) < 2:
        return {}
    ordered = fix_df.sort_values("timestamp_ms")
    cls = classes.reindex(ordered.index).tolist()
    x_vals = ordered[x_col].tolist()
    y_vals = ordered[y_col].tolist()
    out: dict = {}
    for i in range(len(ordered) - 1):
        c = cls[i]
        if pd.isna(c):
            c = "other"
        xs, ys = out.setdefault(c, ([], []))
        _extend_segment(
            xs, ys, x_vals[i], y_vals[i], x_vals[i + 1], y_vals[i + 1], arch_frac
        )
    return out


def _snap_fixations_to_words(
    fixations: pd.DataFrame, words: pd.DataFrame, x_field: str, y_field: str
) -> pd.DataFrame:
    """Return a copy of ``fixations`` with each fixation moved to the top-centre of
    the word it lands on (VIZ-9 "linear reading" mode).

    Fixations with no assigned word keep their raw position. Uses a precomputed
    ``word_id`` column when present, else assigns via bounding-box containment."""
    out = fixations.copy()
    if "word_id" not in words.columns:
        return out
    if (
        "word_id" in out.columns
        and pd.to_numeric(out["word_id"], errors="coerce").notna().any()
    ):
        wid = pd.to_numeric(out["word_id"], errors="coerce")
    else:
        from .measures import assign_fixations_to_words

        wid = pd.to_numeric(
            assign_fixations_to_words(out, words)["word_id"], errors="coerce"
        )
    # Snap above the middle of the word's box, where its label is drawn (BUG-97).
    # Render-only: which word a fixation belongs to is still
    # `assign_fixations_to_words`, against the same boxes.
    from .measures import word_box_bounds

    x0, _, x1, _ = word_box_bounds(words)
    cx_by_id = dict(zip(words["word_id"], (x0 + x1) / 2.0))
    top_by_id = dict(zip(words["word_id"], pd.to_numeric(words["y"], errors="coerce")))
    snap_x = wid.map(cx_by_id)
    snap_y = wid.map(top_by_id)
    out[x_field] = snap_x.where(snap_x.notna(), out[x_field])
    out[y_field] = snap_y.where(snap_y.notna(), out[y_field])
    return out


# Saccades shorter than this fraction of the fixation-extent diagonal get no
# direction arrow — their heading is sub-pixel noise (refixations on one word).
_ARROW_MIN_LEN_FRAC = 0.005

# Bézier parameter at which the arrowhead sits on an arched saccade (BUG-9).
_ARROW_ARCH_T = 0.5


def _arch_point_and_tangent(
    x0: float, y0: float, x1: float, y1: float, frac: float, t: float = _ARROW_ARCH_T
) -> tuple[float, float, float, float]:
    """Point on the drawn arch at Bézier parameter ``t``, plus the curve's tangent.

    Evaluates the very curve ``_arch_points`` samples (same
    ``_arch_control_point``), so an arrowhead placed here lands exactly on the
    rendered line. Returns ``(x, y, dx, dy)`` where ``(dx, dy)`` is the
    (unnormalized) tangent B'(t).

    Note the quadratic's identity at ``t=0.5``: B'(0.5) == P1 - P0, i.e. the
    tangent at the parameter midpoint is parallel to the chord regardless of the
    control point. So arcing a saccade moves the arrowhead *up onto* the curve
    (the visible defect) without rotating it — which is exactly right, the curve
    really is chord-parallel there."""
    cx, cy = _arch_control_point(x0, y0, x1, y1, frac)
    u = 1.0 - t
    px = u * u * x0 + 2 * u * t * cx + t * t * x1
    py = u * u * y0 + 2 * u * t * cy + t * t * y1
    tx = 2 * u * (cx - x0) + 2 * t * (x1 - cx)
    ty = 2 * u * (cy - y0) + 2 * t * (y1 - cy)
    return px, py, tx, ty


def _saccade_arrow_rows(
    fix_df: pd.DataFrame,
    x_col: str,
    y_col: str,
    arch_frac: float | None = None,
) -> tuple[list, list, list, list]:
    """:func:`_saccade_arrow_markers` plus each arrowhead's saccade index.

    Returns ``(mid_x, mid_y, angle_deg, segment_index)``. Arrowheads are dropped
    for micro/degenerate saccades, so the arrays are shorter than the saccade
    count and the position alone doesn't say which saccade an arrow belongs to —
    ``segment_index[j]`` is the index of the departing fixation, which is what
    lets the animated replay reveal each arrow with its own saccade (VIZ-23).
    """
    if len(fix_df) < 2:
        return [], [], [], []
    ordered = fix_df.sort_values("timestamp_ms")
    xv = pd.to_numeric(ordered[x_col], errors="coerce").to_numpy()
    yv = pd.to_numeric(ordered[y_col], errors="coerce").to_numpy()
    # Suppress arrowheads on micro-saccades: a sub-pixel refixation has a
    # well-defined midpoint but its direction is just noise, so a full-size
    # arrow would point a random way. Threshold scales with the data extent so
    # it's dataset-agnostic.
    finite = np.isfinite(xv) & np.isfinite(yv)
    if finite.any():
        x_ext = float(np.nanmax(xv[finite]) - np.nanmin(xv[finite]))
        y_ext = float(np.nanmax(yv[finite]) - np.nanmin(yv[finite]))
        min_len = np.hypot(x_ext, y_ext) * _ARROW_MIN_LEN_FRAC
    else:
        min_len = 0.0
    mid_x: list = []
    mid_y: list = []
    angles: list = []
    seg_index: list = []
    for i in range(len(ordered) - 1):
        x0, y0, x1, y1 = xv[i], yv[i], xv[i + 1], yv[i + 1]
        if not np.isfinite((x0, y0, x1, y1)).all():
            continue
        dx, dy = x1 - x0, y1 - y0
        seg_len = float(np.hypot(dx, dy))
        if seg_len == 0.0 or seg_len < min_len:
            continue
        if arch_frac is None:
            mx, my, hx, hy = (x0 + x1) / 2.0, (y0 + y1) / 2.0, dx, dy
        else:
            mx, my, hx, hy = _arch_point_and_tangent(x0, y0, x1, y1, arch_frac)
        mid_x.append(mx)
        mid_y.append(my)
        # marker.angle is clockwise from up; screen-up is decreasing data y
        # (the y-axis is drawn reversed), so negate the heading's dy.
        angles.append(float(np.degrees(np.arctan2(hx, -hy))))
        seg_index.append(i)
    return mid_x, mid_y, angles, seg_index


def _saccade_arrow_markers(
    fix_df: pd.DataFrame,
    x_col: str,
    y_col: str,
    arch_frac: float | None = None,
) -> tuple[list, list, list]:
    """Arrowhead position + rotation for each saccade, for a marker trace.

    Returns (mid_x, mid_y, angle_deg) with one entry per consecutive-fixation
    segment: a marker at the segment midpoint, rotated to point along the gaze
    direction. Angles follow Plotly's ``marker.angle`` convention (degrees
    clockwise from "up") and account for the reversed y-axis — data y grows
    downward on screen — so they read correctly on the plot.

    ``arch_frac`` (BUG-9) must be the same value the segment builders got: in Arc
    mode (VIZ-9) the marker moves to the *arch's* midpoint and takes the arc's
    tangent there, instead of floating below the curve at the straight chord's
    midpoint. ``None`` (the default everywhere) keeps the straight-chord
    placement.
    """
    mid_x, mid_y, angles, _ = _saccade_arrow_rows(fix_df, x_col, y_col, arch_frac)
    return mid_x, mid_y, angles


_RGB_FUNCTION = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,[^)]*)?\)"
)


def color_with_alpha(color: str, alpha: float) -> str:
    """``color`` as ``rgba(r,g,b,alpha)`` — a fill drawn at its own opacity.

    Takes ``#rrggbb``, ``#rgb`` or ``rgb(…)`` / ``rgba(…)`` (whose own alpha is
    replaced). Anything else raises ``ValueError`` naming it, rather than
    quietly drawing some other colour.
    """
    text = str(color).strip()
    match = re.fullmatch(r"#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})", text)
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        r, g, b = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
        return f"rgba({r},{g},{b},{alpha})"
    match = _RGB_FUNCTION.fullmatch(text)
    if match and all(int(v) <= 255 for v in match.groups()):
        r, g, b = match.groups()
        return f"rgba({r},{g},{b},{alpha})"
    raise ValueError(
        f"{color!r} is not a colour a fill can take: use #rrggbb, #rgb or rgb(r, g, b)."
    )


def build_word_boxes(
    words: pd.DataFrame,
    color: str = WORD_BOX_COLOR,
    fill_color: str = WORD_BOX_FILL_COLOR,
    fill_opacity: float = WORD_BOX_FILL_OPACITY,
    line_opacity: float = WORD_BOX_LINE_OPACITY,
) -> list:
    """Rectangles for the word interest areas.

    Drawn from ``measures.word_box_bounds`` — the experiment's own rectangles
    (BUG-83) — so what's on screen is exactly what ``assign_fixations_to_words``
    assigns against. On a tiling corpus each outline therefore runs on across
    the space after its word, and the word *label* is centred in it (BUG-97).
    ``color`` is the outline, drawn at ``line_opacity`` (0 = no outline); the
    fill is ``fill_color`` at ``fill_opacity`` (0 = no fill). Each is its own
    alpha, so one never fades the other. A fully opaque outline keeps ``color``
    as given, so any colour Plotly accepts still works there.
    """
    from .measures import word_box_bounds

    fill = color_with_alpha(fill_color, fill_opacity)
    if line_opacity < 1:
        color = color_with_alpha(color, line_opacity)
    shapes = []
    for x0, y0, x1, y1 in zip(*word_box_bounds(words)):
        shapes.append(
            dict(
                type="rect",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                line=dict(color=color, width=1),
                fillcolor=fill,
                # VIZ-5: tag the layer so split_scanpath_layers can separate the
                # word boxes from the (visually similar) heatmap rects.
                name=_shape_layer_tag("word_boxes"),
            )
        )
    return shapes


# Bold-frame overlay for critical-span words; rendered on top of regular word
# boxes only when the trial was shown with a preview question (Hunting condition).
_CRITICAL_FRAME_COLOR = "#000000"  # black — high-contrast frame, readable over heatmaps
_CRITICAL_FRAME_WIDTH = 2
_CRITICAL_TEXT_COLOR = (
    HIGHLIGHTED_TEXT_COLOR  # dark pink — used when critical_span_style="Mark text"
)


def build_critical_span_overlay(
    words: pd.DataFrame,
    column: str = "is_in_aspan",
    color: str = _CRITICAL_FRAME_COLOR,
) -> list:
    """Return outline shapes for the highlighted span (``column``, default the
    OneStop answer span ``is_in_aspan``), outlined in ``color``.

    Each visual line that contains highlighted words gets its own outline
    rectangle, going from the *first* to the *last* highlighted word on that
    line (not the whole line). Returns [] when the column is missing or no
    words match.
    """
    if not column or column not in words.columns:
        return []
    mask = words[column].fillna(False).astype(bool)
    if not mask.any():
        return []
    span = words[mask].copy()

    # Cluster words into visual lines by y. `line_idx` upstream is often a
    # constant (no real per-word line numbers in OneStop IA exports), so we
    # group by y with a tolerance of ~half a word-height: rows whose y jumps
    # by more than that are on a new line.
    typical_h = float(span["height"].median() or 1.0)
    y_sorted = span["y"].sort_values()
    line_ids = (y_sorted.diff().fillna(0) > typical_h * 0.5).cumsum()
    span["_line_id"] = line_ids.reindex(span.index)

    from .measures import word_box_bounds

    span_x0, _, span_x1, _ = word_box_bounds(span)
    span["_box_x0"], span["_box_x1"] = span_x0, span_x1

    shapes = []
    for _, group in span.groupby("_line_id"):
        x0 = float(group["_box_x0"].min())
        x1 = float(group["_box_x1"].max())
        y0 = float(group["y"].min())
        y1 = float((group["y"] + group["height"]).max())
        shapes.append(
            dict(
                type="rect",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                line=dict(color=color, width=_CRITICAL_FRAME_WIDTH),
                fillcolor="rgba(0,0,0,0)",
                layer="above",
                # VIZ-5: the critical-span outline rides the word-boxes layer.
                name=_shape_layer_tag("word_boxes"),
            )
        )
    return shapes


# --- VIZ-5: separable-layer export ------------------------------------------
# The scanpath figure is a single flattened image, but publication workflows want
# to restyle each layer in Illustrator / Inkscape. `split_scanpath_layers` returns
# one figure per layer, each a copy of the full figure with only that layer's
# elements kept and everything else removed — so the layouts (axis ranges, size,
# equal-aspect scaleanchor) stay byte-identical and the exported files register
# perfectly when stacked. Every element is tagged with its layer: shapes carry a
# `_LAYER_SHAPE_TAG`-prefixed `name`, traces are classified by their (stable) name,
# and the single `layout.image` is the stimulus.
_LAYER_SHAPE_TAG = "__sps_layer:"
# Draw order (bottom → top), matching how make_scanpath_figure stacks them.
SCANPATH_LAYER_ORDER = (
    "stimulus_image",
    "heatmap",
    "word_boxes",
    "saccades",
    "fixations",
    "raw_gaze",
    "labels",
    "frame",
)
_TRANSPARENT = "rgba(0,0,0,0)"


def _shape_layer_tag(layer: str) -> str:
    """The `name` marker stamped on a shape so its layer survives into the figure."""
    return f"{_LAYER_SHAPE_TAG}{layer}"


def _shape_layer(shape) -> str | None:
    """Layer of a tagged shape, or None for an untagged one."""
    name = getattr(shape, "name", None) or ""
    if name.startswith(_LAYER_SHAPE_TAG):
        return name[len(_LAYER_SHAPE_TAG) :]
    return None


def _trace_layer(trace) -> str:
    """Classify a scanpath trace into its layer by its (stable) name.

    Only a handful of names are fixed — ``words`` (labels), the saccade traces,
    ``Raw gaze``, and any heatmap trace (``… heatmap …``). Every *other* trace the
    scanpath figure draws is a fixation-marker variant with a data-dependent name
    (``Fixations``, per-line ``line: …``, categorical colour-legend entries, the
    PRE-2 flag overlays, the PRE-3 ``drift`` connectors), so they all fall through
    to ``fixations`` — robust to those names changing."""
    name = trace.name or ""
    low = name.lower()
    if name == "words":
        return "labels"
    if "heatmap" in low:
        return "heatmap"
    if name == "Raw gaze":
        return "raw_gaze"
    if name in ("saccades", "saccade direction") or name in set(
        SACCADE_CLASS_LABELS.values()
    ):
        return "saccades"
    return "fixations"


def split_scanpath_layers(fig: go.Figure) -> dict[str, go.Figure]:
    """Split a `make_scanpath_figure` result into one figure per visible layer.

    Returns ``{layer_name: figure}`` in bottom-to-top draw order, keeping only the
    layers that actually have elements. Each returned figure is a copy of ``fig``
    with (a) only that layer's traces/shapes/images kept and (b) a transparent
    paper/plot background, so stacking the exported files in a vector editor
    reproduces the combined figure exactly (identical axis ranges + size ⇒ perfect
    registration). See VIZ-5."""
    # Which layers are present, and each trace's layer (computed once).
    trace_layers = [_trace_layer(tr) for tr in fig.data]
    shape_layers = [_shape_layer(sh) for sh in (fig.layout.shapes or ())]
    present = set(trace_layers) | {s for s in shape_layers if s}
    if fig.layout.images:
        present.add("stimulus_image")

    out: dict[str, go.Figure] = {}
    for layer in SCANPATH_LAYER_ORDER:
        if layer not in present:
            continue
        g = copy.deepcopy(fig)
        g.data = tuple(tr for tr, tl in zip(g.data, trace_layers) if tl == layer)
        g.layout.shapes = tuple(
            sh for sh, sl in zip(g.layout.shapes or (), shape_layers) if sl == layer
        )
        g.layout.images = fig.layout.images if layer == "stimulus_image" else ()
        # The duration size key's ms labels belong with its circles, which ride
        # the fixations layer; every other annotation (title text, the
        # Illustration stamp) stays on each layer as before.
        if layer != "fixations":
            g.layout.annotations = tuple(
                a for a in (g.layout.annotations or ()) if a.name != _SIZE_KEY_NAME
            )
        # Transparent background so the layers overlay cleanly when re-stacked.
        g.update_layout(paper_bgcolor=_TRANSPARENT, plot_bgcolor=_TRANSPARENT)
        out[layer] = g
    return out


_HOVER_MEASURE_LABELS: dict[str, str] = {
    "total_fixation_duration_ms": "Total fixation",
    "first_fixation_ms": "FFD",
    "first_pass_gaze_duration_ms": "FPRT",
    "regression_path_duration_ms": "RPD",
    "n_fixations": "Fixations",
}

#: DATA-66: `FigureSettings.column_labels` for the build in progress. The three
#: builders set it (`_labelled_columns`) and the helpers that write a column's
#: name into the figure read it (`_column_title`, `_hover_label`), so the dozen
#: helpers in between keep their signatures. Empty outside a build.
_COLUMN_LABELS: ContextVar[Mapping[str, str] | None] = ContextVar(
    "scanpath_column_labels", default=None
)


@contextmanager
def _labelled_columns(labels: Mapping[str, str] | None) -> Iterator[None]:
    """Make ``labels`` the column names one figure build writes."""
    token = _COLUMN_LABELS.set(dict(labels or {}))
    try:
        yield
    finally:
        _COLUMN_LABELS.reset(token)


def _humanize_column(column: str, *, unit: bool = True) -> str:
    """``total_fixation_duration_ms`` → "Total Fixation Duration (ms)", and
    ``participant_id`` → "Participant ID".

    ``unit=False`` drops the unit, for a hover row that writes it after the
    value — which used to read "… Duration Ms: 200 ms"."""
    text = str(column)
    in_ms = text.endswith("_ms")
    if in_ms:
        text = text[: -len("_ms")]
    title = re.sub(r"\bId\b", "ID", text.replace("_", " ").strip().title())
    return f"{title} (ms)" if in_ms and unit else title


def _column_name(column: str) -> str:
    """A column's name in a legend entry: the dataset's own (DATA-66), else the
    column's own, as the legend has always written it."""
    labels = _COLUMN_LABELS.get() or {}
    return labels.get(column, str(column))


def _column_title(column: str) -> str:
    """A column's name in a figure's titles: the dataset's own (DATA-66), else
    the column humanized."""
    labels = _COLUMN_LABELS.get() or {}
    return labels[column] if column in labels else _humanize_column(column)


def _table_label(field: str, table: str | None) -> str | None:
    """``field``'s label in ``table`` when the build names it: the
    ``"<table>:<field>"`` entry first — a word table and a fixation table can
    call one canonical column differently (``word_id``) — then the plain one."""
    labels = _COLUMN_LABELS.get() or {}
    if table is not None and f"{table}:{field}" in labels:
        return labels[f"{table}:{field}"]
    return labels.get(field)


def _hover_label(field: str, table: str | None = None) -> str:
    """Readable label for an arbitrary hover column.

    The dataset's own name when the build has one (DATA-66), as ``table``
    names it; else a short label for the app's own columns, else the column
    humanized without its unit (the row writes the unit after the value)."""
    own = _table_label(field, table)
    if own is not None:
        return own
    aliases = {
        "text": "Word",
        "word_id": "Word #",
        "line_idx": "Line #",
        "order_in_trial": "Fixation #",
        "duration_ms": "Duration",
        "timestamp_ms": "Timestamp",
    }
    return aliases.get(
        field,
        _HOVER_MEASURE_LABELS.get(field, _humanize_column(field, unit=False)),
    )


def _plotly_literal(value: str) -> str:
    """``value`` as Plotly text that draws its own characters.

    Plotly reads a text or hover string as its pseudo-HTML, so a stimulus
    token ``<b>bold</b>`` drew bold and ``x<br>y`` broke the line (round-8
    review, finding 6). Escaping ``&``, ``<`` and ``>`` — the entities Plotly
    decodes back — keeps the dataset's characters on screen, and ``%{`` is
    written ``&#37;{`` so a name placed in a hover template is not read as a
    template field (round 9). Applied once, to data values and user text only,
    at the figure boundary: the tables, exports and the app's own markup (a
    hover's ``<br>``) are left as they are."""
    return html.escape(value, quote=False).replace("%{", "&#37;{")


def _plotly_literal_values(series: pd.Series) -> pd.Series:
    """A hover column with its strings made literal (:func:`_plotly_literal`);
    numbers, missing values and anything else pass through untouched."""
    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return series
    return series.map(
        lambda value: _plotly_literal(value) if isinstance(value, str) else value,
        na_action="ignore",
    )


def _fixation_order_labels(ordered: pd.DataFrame) -> list[str]:
    """The fixation-number labels of a replay trail, one per row of ``ordered``.

    The trial's own ``order_in_trial``, as the static figure, the comparison
    and every hover show it — so a later screen of a multipart trial, a
    fixation window or a *Discard* keeps its gaps (501, 502 …) instead of
    renumbering what is left 1..n. A row without an index gets no label, as
    on the static figure. Only a frame with no usable index at all (no column,
    or nothing numeric in it) falls back to the ordinal 1..n."""
    n = len(ordered)
    if "order_in_trial" in ordered.columns:
        values = pd.to_numeric(ordered["order_in_trial"], errors="coerce")
        if values.notna().any():
            return [
                ""
                if pd.isna(value)
                else str(int(value))
                if float(value).is_integer()
                else f"{value:g}"
                for value in values.tolist()
            ]
    return [str(j + 1) for j in range(n)]


def _hover_payload(
    frame: pd.DataFrame,
    fields: Sequence[str],
    *,
    line_display: pd.Series | None = None,
    table: str | None = None,
) -> tuple[np.ndarray | None, str]:
    """Plotly customdata + template for a user-selected field list (VIZ-26);
    ``table`` says whose names label the rows (DATA-66)."""
    valid = [
        field
        for field in fields
        if field in frame.columns or (field == "line_idx" and line_display is not None)
    ]
    if not valid:
        return None, "<extra></extra>"
    values: list[pd.Series] = []
    rows: list[str] = []
    for idx, field in enumerate(valid):
        series = (
            line_display
            if field == "line_idx" and line_display is not None
            else frame[field]
        )
        values.append(_plotly_literal_values(series))
        suffix = " ms" if field.endswith("_ms") else ""
        rows.append(f"{_hover_label(field, table)}: %{{customdata[{idx}]}}{suffix}")
    customdata = pd.concat(values, axis=1).to_numpy(dtype=object)
    return customdata, "<br>".join(rows) + "<extra></extra>"


def _add_word_label_trace(
    fig: go.Figure,
    words: pd.DataFrame,
    base_font_size: int,
    font_family: str,
    row: int | None = None,
    col: int | None = None,
    highlight_column: str | None = None,
    text_color: str = WORD_LABEL_COLOR,
    highlight_text_color: str = _CRITICAL_TEXT_COLOR,
    word_hover_measure: str | None = None,
    word_hover_fields: Sequence[str] | None = None,
) -> None:
    if words.empty or "text" not in words.columns:
        return
    customdata = None
    hover = "Word: %{text}<extra></extra>"
    if "word_id" in words.columns:
        from .measures import cluster_word_lines

        # The source ``line_idx`` is often a constant (OneStop IA exports rarely
        # carry a real per-word line number), so infer the visual line from
        # word-box geometry — same clustering the by-line coloring uses — and
        # show it 1-based.
        line_display = (cluster_word_lines(words) + 1).rename("line")
        if word_hover_fields is not None:
            customdata, hover = _hover_payload(
                words, word_hover_fields, line_display=line_display, table="words"
            )
        else:
            # Legacy API/deep-link behaviour: the three fixed identity lines plus
            # the old single optional measure.
            customdata_parts: list[pd.Series] = [
                _plotly_literal_values(words["word_id"]),
                line_display,
            ]
            hover = "Word: %{text}<br>Word #%{customdata[0]}<br>Line #%{customdata[1]}"
            if word_hover_measure and word_hover_measure in words.columns:
                label = _table_label(
                    word_hover_measure, "words"
                ) or _HOVER_MEASURE_LABELS.get(word_hover_measure, word_hover_measure)
                suffix = " ms" if word_hover_measure.endswith("_ms") else ""
                hover += f"<br>{label}: %{{customdata[2]}}{suffix}"
                customdata_parts.append(
                    _plotly_literal_values(words[word_hover_measure])
                )
            hover += "<extra></extra>"
            customdata = pd.concat(customdata_parts, axis=1)
    # Per-word text color: the highlight colour for highlighted words when the
    # caller asks for "Mark text" (``highlight_column`` set), the base text
    # colour otherwise. Both are configurable from the plot rail.
    if highlight_column and highlight_column in words.columns:
        critical_mask = words[highlight_column].fillna(False).astype(bool)
        label_color = [
            highlight_text_color if is_crit else text_color for is_crit in critical_mask
        ]
    else:
        label_color = text_color
    # BUG-97 — the label is centred in its word's box, as the data defines it.
    # BUG-30 centred it on the glyph run instead, which on a tiling corpus (the
    # box carries the following space) drew every word flush left in its box.
    # Centred text needs no LTR/RTL anchor; the Unicode direction isolates stay —
    # they are about *shaping* mixed Hebrew/Arabic + punctuation, not placement.
    from .measures import word_box_bounds
    from .preprocessing import detect_right_to_left

    rtl = words.get("right_to_left")
    if rtl is None:
        rtl = words["text"].astype(str).map(detect_right_to_left)
    else:
        rtl = rtl.fillna(False).astype(bool)
    box_x0, _, box_x1, _ = word_box_bounds(words)
    label_x = (box_x0 + box_x1) / 2.0
    # The word drawn as its own characters (finding 6 — not as Plotly markup),
    # escaped before the direction isolates wrap it; the hover's `%{text}`
    # reads this same string, so it shows the word literally too.
    label_text = [
        f"\u2067{_plotly_literal(value)}\u2069" if is_rtl else _plotly_literal(value)
        for value, is_rtl in zip(words["text"].astype(str), rtl)
    ]
    trace = go.Scatter(
        x=label_x,
        y=words["y"] + words["height"] / 2,
        text=label_text,
        mode="text",
        textposition="middle center",
        showlegend=False,
        textfont=dict(color=label_color, size=base_font_size, family=font_family),
        hovertemplate=hover,
        customdata=customdata,
        name="words",
    )
    if row is not None and col is not None:
        fig.add_trace(trace, row=row, col=col)
    else:
        fig.add_trace(trace)


_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _image_to_data_uri(src: str | None) -> str | None:
    """A ``data:`` URI for an image path, or pass through an existing one.

    Returns None for a missing / unreadable file so the background-image layer
    simply doesn't draw (e.g. an uploaded MultiplEYE dataset has no image path)."""
    if not src:
        return None
    text = str(src)
    if text.startswith("data:"):
        return text
    path = Path(text)
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    mime = _IMAGE_MIME.get(path.suffix.lower(), "image/png")
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _png_pixel_size(src: str | None) -> tuple[int, int] | None:
    """(width, height) of a PNG from its header, without Pillow; None otherwise."""
    if not src:
        return None
    try:
        with open(src, "rb") as fh:
            head = fh.read(24)
    except OSError:
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
        width, height = struct.unpack(">II", head[16:24])
        return int(width), int(height)
    return None


def _background_image_spec(
    background_image: str | None,
    background_image_size: tuple[float, float] | None,
    background_image_origin: tuple[float, float] | None,
    background_image_opacity: float = 1.0,
) -> dict | None:
    """The ``layout.image`` dict for the stimulus-page background (VIZ-4).

    The rendered page sits at data coordinates ``(origin_x, origin_y)`` →
    ``(+image_w, +image_h)`` UNDER every other layer; the coords are where the
    (centered) stimulus appeared on the monitor, so the image aligns exactly and
    sidesteps CJK/RTL font rendering. ``background_image_origin`` defaults to
    ``(0, 0)``; ``yanchor="top"`` + the reversed y-axis put the image's top-left
    there. ``background_image_opacity`` dims a busy stimulus so the AOIs/scanpath
    read over it (1.0 = opaque). Returns ``None`` when there is nothing to draw
    (no image, no size, or an unreadable path), so callers can just skip it.
    """
    if not (background_image and background_image_size):
        return None
    uri = _image_to_data_uri(background_image)
    if not uri:
        return None
    image_w, image_h = background_image_size
    origin_x, origin_y = background_image_origin or (0.0, 0.0)
    return dict(
        source=uri,
        xref="x",
        yref="y",
        x=origin_x,
        y=origin_y,
        sizex=image_w,
        sizey=image_h,
        sizing="stretch",
        layer="below",
        xanchor="left",
        yanchor="top",
        opacity=float(background_image_opacity),
    )


def _add_background_image(
    fig: go.Figure,
    background_image: str | None,
    background_image_size: tuple[float, float] | None,
    background_image_origin: tuple[float, float] | None,
    background_image_opacity: float = 1.0,
    *,
    row: int | None = None,
    col: int | None = None,
) -> bool:
    """Add the stimulus-page background image to ``fig``; True when one was added.

    ``row``/``col`` bind it to one subplot's axes (the split comparison figure);
    without them it goes on the figure's single axis pair.
    """
    spec = _background_image_spec(
        background_image,
        background_image_size,
        background_image_origin,
        background_image_opacity,
    )
    if spec is None:
        return False
    if row is not None and col is not None:
        fig.add_layout_image(spec, row=row, col=col)
    else:
        fig.add_layout_image(spec)
    return True


def _add_saccade_layer(
    fig: go.Figure,
    fixations: pd.DataFrame,
    *,
    x_field: str,
    y_field: str,
    color: str,
    width: float,
    style: str,
    show_arrows: bool,
    saccade_classes: pd.Series | None = None,
    color_by_class: bool = True,
    class_colors: dict | None = None,
    class_legend: bool = True,
    visible_classes: Iterable[str] | None = None,
    render_mode: str = "Straight",
    two_way: bool = False,
) -> bool:
    """Add one scanpath's saccade lines (+ optional direction arrowheads) to ``fig``.

    Connects consecutive fixations in time order. When ``saccade_classes`` is
    given (the per-fixation reading class from ``measures.classify_saccades``)
    the segments are grouped by class; with ``color_by_class`` (VIZ-8 "By type")
    each group becomes its own sub-trace in its colour from ``class_colors``
    plus a small legend, and ``two_way`` (VIZ-19) first folds the five classes
    down to forward vs. regression. Otherwise a single uniform-``color`` trace is
    drawn. ``visible_classes`` (VIZ-31) is the reading-class **filter**: segments
    whose class isn't listed are not drawn at all — so it needs the
    classification even in uniform-colour mode, which is why ``color_by_class``
    exists separately. Filtering happens on the *unfolded* classes, before the
    two-way fold, so "show only regressions" means the same thing in every
    colour mode. It is read literally: an **empty** ``visible_classes`` draws no
    saccades. (The rail never sends one — ``controls._collect_viz_settings``
    reads a cleared multiselect as "no filter", since hiding the layer outright
    is what its toggle is for.) ``render_mode="Arc"`` (VIZ-9) draws each saccade as an upward
    arch instead of a straight connector. The arrowheads are a separate,
    independently-toggled trace drawn before the fixation markers so the dots sit
    on top (uniform ``color`` either way — they encode direction, the line colour
    encodes type), and they honour the same filter. The caller gates this on
    spatial axes, ``show_saccades`` and at least two fixations.

    Returns ``True`` when legend entries were added (by-type mode), so the caller
    reserves margin for the legend (mirrors ``_add_raw_gaze_layer``).
    """
    legend_added = False
    arch_frac = _ARCH_FRAC if render_mode == "Arc" else None
    keep = None if visible_classes is None else set(visible_classes)
    # Group once, on the raw (unfolded) classes, then filter — the two-way fold
    # and the uniform-colour merge below both work off the same grouping.
    segs = None
    if saccade_classes is not None:
        segs = _saccade_segments_by_class(
            fixations, x_field, y_field, saccade_classes, arch_frac
        )
        if keep is not None:
            segs = {c: s for c, s in segs.items() if c in keep}

    if segs is not None and color_by_class:
        # Merge over the full defaults so classes the caller omits (notably the
        # non-editable "other" catch-all — the UI palette only carries the five
        # reading classes) still get their intended colour instead of falling
        # back to the uniform line colour.
        palette = {**SACCADE_CLASS_COLORS, **(class_colors or {})}
        # VIZ-19: the two-way mode is the five-way one with the classes folded
        # into forward/regression buckets, so everything below — segments,
        # colours, legend — is shared. "Forward" takes the forward class's
        # colour, which is what the picker shows for it.
        if two_way:
            folded: dict = {}
            for cls_name, (fx, fy) in segs.items():
                bucket = SACCADE_DIRECTION_FOLD.get(cls_name, "other")
                bx, by = folded.setdefault(bucket, ([], []))
                bx.extend(fx)
                by.extend(fy)
            segs = folded
            draw_order = [*SACCADE_DIRECTION_CLASSES, "other"]
            labels = SACCADE_DIRECTION_LABELS
            legend_title = "Saccade direction"
        else:
            draw_order = SACCADE_CLASS_ORDER
            labels = SACCADE_CLASS_LABELS
            legend_title = "Saccade type"
        for cls_name in draw_order:
            seg = segs.get(cls_name)
            if not seg or not seg[0]:
                continue
            sx, sy = seg
            fig.add_trace(
                go.Scatter(
                    x=sx,
                    y=sy,
                    mode="lines",
                    line=dict(
                        color=palette.get(cls_name, color), width=width, dash=style
                    ),
                    hoverinfo="skip",
                    # VIZ-8: the colour key is optional — hide it (but keep the
                    # coloured sub-traces) when class_legend is off.
                    showlegend=class_legend,
                    legendgroup="saccade_type",
                    legendgrouptitle_text=legend_title,
                    name=labels.get(cls_name, cls_name),
                )
            )
            # Reserve legend margin only when the key is actually shown.
            legend_added = class_legend
    else:
        if segs is None:
            sx, sy = _saccade_segments(fixations, x_field, y_field, arch_frac)
        else:
            # Filtered, but drawn in one uniform colour: concatenate the classes
            # that survived. Each class's arrays are already None-separated, so
            # joining them is the same trace the unfiltered path builds minus the
            # hidden segments (their order within the trace doesn't render).
            sx, sy = [], []
            for cls_name in [
                *SACCADE_CLASS_ORDER,
                *(c for c in segs if c not in SACCADE_CLASS_ORDER),
            ]:
                seg = segs.get(cls_name)
                if seg:
                    sx.extend(seg[0])
                    sy.extend(seg[1])
        if sx:
            fig.add_trace(
                go.Scatter(
                    x=sx,
                    y=sy,
                    mode="lines",
                    line=dict(color=color, width=width, dash=style),
                    hoverinfo="skip",
                    showlegend=False,
                    name="saccades",
                )
            )
    if show_arrows:
        # BUG-9: same arch_frac as the segments above, so the arrowheads sit on
        # the drawn line (arched or straight) instead of on the chord.
        amx, amy, aang, aseg = _saccade_arrow_rows(
            fixations, x_field, y_field, arch_frac
        )
        if amx and keep is not None and saccade_classes is not None:
            mask = _arrow_class_mask(fixations, saccade_classes, keep, aseg)
            amx = [v for v, m in zip(amx, mask) if m]
            amy = [v for v, m in zip(amy, mask) if m]
            aang = [v for v, m in zip(aang, mask) if m]
        if amx:
            fig.add_trace(
                go.Scatter(
                    x=amx,
                    y=amy,
                    mode="markers",
                    marker=dict(
                        symbol="arrow",
                        size=12,
                        angle=aang,
                        angleref="up",
                        color=color,
                        line=dict(width=0),
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                    name="saccade direction",
                )
            )
    return legend_added


def _add_raw_gaze_layer(
    fig: go.Figure,
    raw_gaze: pd.DataFrame | None,
    *,
    show_raw_gaze: bool,
    raw_gaze_color: str = "#888888",
    raw_gaze_marker_size: float = 4.0,
    raw_gaze_opacity: float = 0.6,
) -> bool:
    """Add the raw-gaze sample-point scatter (time-coloured when available).

    Returns ``True`` if a trace was added, so the caller can mark the legend
    active (it reserves margin for the legend). Self-gates on ``show_raw_gaze``
    and a non-empty frame. **UX-86**: ``raw_gaze_color`` is the flat colour
    used when the data carries no ``timestamp_ms`` — when it does, fixations
    stay time-mapped (Viridis) since that is the more informative default and
    a flat colour would throw it away. Samples imported without a clock carry
    ``sample_index`` instead: coloured by that order, with the legend titled
    *Sample order* and the hover saying ``sample n`` — never milliseconds.
    """
    if not (show_raw_gaze and raw_gaze is not None and not raw_gaze.empty):
        return False
    legend_title = None
    if "timestamp_ms" in raw_gaze.columns:
        color_vals = raw_gaze["timestamp_ms"]
        colorscale = "Viridis"
        customdata = raw_gaze["timestamp_ms"]
        when = "<br>t: %{customdata} ms"
    elif SAMPLE_INDEX in raw_gaze.columns:
        # No clock (the import mapped none): coloured by the samples' order,
        # and said so — a ramp with no title would read as time.
        color_vals = raw_gaze[SAMPLE_INDEX]
        colorscale = "Viridis"
        customdata = raw_gaze[SAMPLE_INDEX]
        when = "<br>sample %{customdata}"
        legend_title = "Sample order"
    else:
        color_vals = raw_gaze_color
        colorscale = None
        customdata = None
        when = ""
    fig.add_trace(
        go.Scatter(
            x=raw_gaze["x"],
            y=raw_gaze["y"],
            mode="markers",
            marker=dict(
                size=raw_gaze_marker_size,
                color=color_vals,
                colorscale=colorscale,
                opacity=raw_gaze_opacity,
                showscale=False,
            ),
            hovertemplate=(
                "Raw gaze<br>x: %{x:.1f}<br>y: %{y:.1f}" + when + "<extra></extra>"
            ),
            customdata=customdata,
            legendgroup="raw_gaze" if legend_title else None,
            legendgrouptitle_text=legend_title,
            name="Raw gaze",
            showlegend=True,
        )
    )
    return True


# PRE-2 fixation classification (viz-only): SHORT / LONG / OUT-OF-BOUNDS, each
# Off / Highlight / Discard. Thresholds come from the caller's flags dict; these
# are the fallbacks the app's own controls default to.
_FIX_FLAG_SHORT_MS = 80.0
_FIX_FLAG_LONG_MS = 800.0
_FIX_FLAG_CATEGORIES = ("short", "long", "oob", "blink")
_FIX_FLAG_LABELS = {
    "short": "Short",
    "long": "Long",
    "oob": "Out of bounds",
    "blink": "Blink-adjacent",
}


def _fixation_flag_masks(
    fixations: pd.DataFrame,
    words: pd.DataFrame,
    flags: dict | None,
    *,
    spatial_axes: bool = True,
) -> dict[str, pd.Series]:
    """Boolean mask per PRE-2 fixation-flag category, over ``fixations``' index.

    ``{"short": …, "long": …, "oob": …}``, or ``{}`` when nothing is flagged.
    Out-of-bounds needs word boxes on spatial axes — without them no fixation
    counts as out of bounds. Shared by the static figure and the animated replay
    so the two classify identically (VIZ-23).
    """
    if not flags or fixations.empty:
        return {}
    dur = pd.to_numeric(fixations.get("duration_ms"), errors="coerce")
    oob = pd.Series(False, index=fixations.index)
    if spatial_axes and not words.empty:
        from .measures import fixation_in_text_mask

        oob = ~fixation_in_text_mask(fixations, words)
    short_ms = float(flags.get("short", {}).get("threshold_ms", _FIX_FLAG_SHORT_MS))
    long_ms = float(flags.get("long", {}).get("threshold_ms", _FIX_FLAG_LONG_MS))
    blink = pd.Series(False, index=fixations.index)
    for column in ("is_blink", "blink_before", "blink_after", "blink"):
        if column in fixations:
            blink |= fixations[column].fillna(False).astype(bool)
    return {
        "short": (dur < short_ms).fillna(False).astype(bool),
        "long": (dur > long_ms).fillna(False).astype(bool),
        "oob": oob.fillna(False).astype(bool),
        "blink": blink,
    }


def _discard_flagged_fixations(
    fixations: pd.DataFrame,
    words: pd.DataFrame,
    flags: dict | None,
    *,
    spatial_axes: bool = True,
) -> pd.DataFrame:
    """Drop the fixations whose PRE-2 flag mode is *Discard* (viz-only).

    Changes only what is DRAWN — the returned frame feeds the markers, the
    fixation-index labels and the marker-size scaling; reading measures and
    exports are untouched. Returns ``fixations`` itself when nothing is dropped.
    """
    masks = _fixation_flag_masks(fixations, words, flags, spatial_axes=spatial_axes)
    if not masks:
        return fixations
    drop = pd.Series(False, index=fixations.index)
    for category, mask in masks.items():
        if (flags or {}).get(category, {}).get("mode") == "Discard":
            drop = drop | mask
    return fixations[~drop] if bool(drop.any()) else fixations


def _render_scanpath_figure(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    settings: FigureSettings,
    raw_gaze: pd.DataFrame | None = None,
) -> go.Figure:
    canvas_width = settings.canvas_width
    canvas_height = settings.canvas_height
    base_font_size = settings.base_font_size
    font_family = settings.font_family
    x_field = settings.x_field
    y_field = settings.y_field
    show_words = settings.show_words
    show_word_labels = settings.show_word_labels
    show_fixations = settings.show_fixations
    show_order = settings.show_order
    show_saccades = settings.show_saccades
    show_heatmap = settings.show_heatmap
    color_by = settings.color_by
    heatmap_metric = settings.heatmap_metric
    show_saccade_arrows = settings.show_saccade_arrows
    heatmap_style = settings.heatmap_style
    heatmap_norm = settings.heatmap_norm
    heatmap_sigma_px = settings.heatmap_sigma_px
    marker_size_range = settings.marker_size_range
    order_font_size = settings.order_font_size
    order_font_color = settings.order_font_color
    show_colorbars = settings.show_fixation_colorbar
    show_heatmap_colorbar = settings.show_heatmap_colorbar
    fixation_color_range = settings.fixation_color_range
    heatmap_range = settings.heatmap_range
    fixation_colorscale = settings.fixation_colorscale
    heatmap_colorscale = settings.heatmap_colorscale
    show_raw_gaze = settings.show_raw_gaze
    raw_gaze_color = settings.raw_gaze_color
    raw_gaze_marker_size = settings.raw_gaze_marker_size
    raw_gaze_opacity = settings.raw_gaze_opacity
    critical_span_style = settings.critical_span_style
    highlight_column = settings.highlight_column
    saccade_color = settings.saccade_color
    saccade_style = settings.saccade_style
    saccade_width = settings.saccade_width
    saccade_color_mode = settings.saccade_color_mode
    saccade_class_colors = settings.saccade_class_colors
    saccade_type_legend = settings.saccade_type_legend
    saccade_classes = settings.saccade_classes
    saccade_render_mode = settings.saccade_render_mode
    fixation_snap_to_word = settings.fixation_snap_to_word
    hollow_fixations = settings.hollow_fixations
    fixation_opacity = settings.fixation_opacity
    fixation_color = settings.fixation_color
    fixation_symbol = settings.fixation_symbol
    text_color = settings.text_color
    highlight_text_color = settings.highlight_text_color
    background_color = settings.background_color
    # BUG-85: `color_by="line"` is the rail's own spelling of this (its "line"
    # option, a share link's `color_by=line`), so it colours by line from the
    # API and CLI too rather than falling through to a missing column.
    color_by_line = settings.color_by_line or settings.color_by == "line"
    fixation_flags = settings.fixation_flags
    span_border_color = settings.span_border_color
    # The fixations' colour bar; the heatmap's is `cb_style` below.
    colorbar_orientation = settings.fixation_colorbar_orientation
    colorbar_tickangle = settings.fixation_colorbar_tickangle
    colorbar_tickfont_size = settings.fixation_colorbar_tickfont_size
    line_spacing = settings.line_spacing
    scale_text_to_boxes = settings.scale_text_to_boxes
    background_image = settings.background_image
    background_image_size = settings.background_image_size
    background_image_origin = settings.background_image_origin
    background_image_opacity = settings.background_image_opacity
    fit_to_monitor = settings.fit_to_monitor
    show_coordinate_grid = settings.show_coordinate_grid
    coordinate_grid_spacing = settings.coordinate_grid_spacing
    word_heatmap_col = settings.word_heatmap_col
    word_heatmap_title = settings.word_heatmap_title
    word_hover_measure = settings.word_hover_measure
    word_hover_fields = settings.word_hover_fields
    fixation_hover_fields = settings.fixation_hover_fields
    show_connectors = settings.show_connectors
    connector_y = settings.connector_y
    illustration_reasons = settings.illustration_reasons
    fig = go.Figure()
    spatial_axes = x_field == "x" and y_field == "y"
    # Track whether a colorbar / legend will render, to reserve margin for them
    # below (so they don't shrink the equal-aspect plot). See _decoration_margins.
    legend_active = False
    heatmap_rendered = False
    is_numeric_color = False
    # The heatmap's colour-bar styling (orientation / tick angle / tick size).
    cb_style = dict(
        orientation=settings.heatmap_colorbar_orientation,
        tickangle=settings.heatmap_colorbar_tickangle,
        tickfont_size=settings.heatmap_colorbar_tickfont_size,
    )
    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)

    raw_for_range = raw_gaze if (show_raw_gaze and raw_gaze is not None) else None
    if spatial_axes:
        x_range, y_range, x_min_data, x_max_data, y_min_data, y_max_data = (
            _compute_axis_ranges(
                canvas_width,
                canvas_height,
                (fixations, x_field, y_field),
                (raw_for_range, "x", "y"),
                word_frames=[words] if not words.empty else [],
                fit_to_monitor=fit_to_monitor,
            )
        )
    else:
        x_range = [0, canvas_width]
        y_range = [canvas_height, 0]
        x_min_data = x_max_data = y_min_data = y_max_data = None

    # VIZ-9 "linear reading" mode: snap each fixation above the word it lands on,
    # so the saccade layer AND the fixation markers below draw from the snapped
    # positions. Off by default. The axis ranges above and the heatmaps below keep
    # the RECORDED positions (raw gaze density); only the drawn connectors and
    # markers move — and the Arc headroom just below, which must follow them.
    render_fix = fixations
    if (
        fixation_snap_to_word
        and spatial_axes
        and not fixations.empty
        and not words.empty
    ):
        render_fix = _snap_fixations_to_words(fixations, words, x_field, y_field)

    # VIZ-9 arc mode: the saccade arches rise ABOVE the fixations, so reserve
    # headroom at the top of the view (smaller y — the axis is inverted) or a wide
    # top-line saccade's apex gets clipped. Computed from the exact Bézier apex of
    # each segment so it's tight; only in Arc mode, so the default view is
    # unchanged. The apexes come from ``render_fix`` — the coordinates the
    # connectors are actually drawn from — because Snap to word can both widen a
    # saccade (two near-edge fixations jump to their words' centres) and lift its
    # endpoints (to the box tops), so an arc over the recorded positions would
    # under-reserve and clip the snapped curve.
    # Whole-monitor view (``fit_to_monitor``): the range still starts as the full
    # screen, and this only ever *grows* it — past the screen's top edge when an
    # arc would reach it — so a schematic arc is never silently cut off; the
    # screen itself is always shown whole.
    if (
        spatial_axes
        and saccade_render_mode == "Arc"
        and show_saccades
        and len(render_fix) > 1
    ):
        fo = render_fix.sort_values("timestamp_ms")
        fxv = pd.to_numeric(fo[x_field], errors="coerce").to_numpy(dtype=float)
        fyv = pd.to_numeric(fo[y_field], errors="coerce").to_numpy(dtype=float)
        apex = np.inf
        for i in range(len(fo) - 1):
            x0, y0, x1, y1 = fxv[i], fyv[i], fxv[i + 1], fyv[i + 1]
            if not np.isfinite((x0, y0, x1, y1)).all():
                continue
            # BUG-13: the curve's true peak, not its t=0.5 point — for endpoints
            # that differ in y the parabola crests higher than the midpoint
            # sample, and a wide top-line arc then clipped.
            apex = min(apex, _arch_apex_y(x0, y0, x1, y1, _ARCH_FRAC))
        if np.isfinite(apex):
            margin = 0.02 * abs(y_range[0] - y_range[1])
            y_range = [y_range[0], min(y_range[1], apex - margin)]

    # Stimulus-page background image (MultiplEYE / VIZ-4) — see
    # `_background_image_spec` for the placement contract.
    if spatial_axes:
        _add_background_image(
            fig,
            background_image,
            background_image_size,
            background_image_origin,
            background_image_opacity,
        )

    # Fix the display size up front so the data->screen scale is known: word
    # labels are then sized in that scale (true-to-scale text), and the same
    # fitted_w/fitted_h drive the final layout below.
    fitted_w, fitted_h = _fit_display_size(
        canvas_width, canvas_height, x_range, y_range, spatial_axes
    )
    scale = (
        _display_scale(x_range, y_range, fitted_w, fitted_h) if spatial_axes else 1.0
    )
    label_font_px = _word_label_font_px(
        words,
        scale=scale,
        line_spacing=line_spacing,
        manual_font_px=base_font_size,
        scale_text_to_boxes=scale_text_to_boxes,
    )

    # Words flagged by ``highlight_column`` (default the OneStop answer span
    # ``is_in_aspan``) get marked one of two ways:
    #   - "Mark text": color the highlighted words dark pink (no border).
    #   - "Mark border": draw a thin black outline around the span.
    has_highlight = (
        bool(highlight_column)
        and highlight_column in words.columns
        and not words.empty
        and bool(words[highlight_column].fillna(False).astype(bool).any())
    )
    highlight_text = has_highlight and critical_span_style == "Mark text"

    if spatial_axes and not words.empty:
        # Word-box grid (the "Bounding boxes" layer) and the "Mark border" span
        # overlay are independent: the span borders show even when the boxes are
        # off (then only the span outline is drawn).
        shapes = (
            build_word_boxes(
                words,
                color=settings.word_box_color,
                fill_color=settings.word_box_fill_color,
                fill_opacity=settings.word_box_fill_opacity,
                line_opacity=settings.word_box_line_opacity,
            )
            if show_words
            else []
        )
        if has_highlight and critical_span_style == "Mark border":
            shapes = shapes + build_critical_span_overlay(
                words, highlight_column, color=span_border_color
            )
        if shapes:
            fig.update_layout(shapes=shapes)
        if show_word_labels:
            _add_word_label_trace(
                fig,
                words,
                label_font_px,
                font_settings["family"],
                highlight_column=highlight_column if highlight_text else None,
                text_color=text_color,
                highlight_text_color=highlight_text_color,
                word_hover_measure=word_hover_measure,
                word_hover_fields=word_hover_fields,
            )

    if _add_raw_gaze_layer(
        fig,
        raw_gaze,
        show_raw_gaze=show_raw_gaze,
        raw_gaze_color=raw_gaze_color,
        raw_gaze_marker_size=raw_gaze_marker_size,
        raw_gaze_opacity=raw_gaze_opacity,
    ):
        legend_active = True

    if spatial_axes and show_heatmap and not fixations.empty:
        heatmap_rendered = True
        weights = fixations["duration_ms"] if heatmap_metric == "duration_ms" else None
        x_min = (
            x_min_data if x_min_data is not None else float(fixations[x_field].min())
        )
        x_max = (
            x_max_data if x_max_data is not None else float(fixations[x_field].max())
        )
        y_min = (
            y_min_data if y_min_data is not None else float(fixations[y_field].min())
        )
        y_max = (
            y_max_data if y_max_data is not None else float(fixations[y_field].max())
        )
        if heatmap_style == "Interpolated":
            _add_interpolated_heatmap(
                fig,
                fixations,
                x_field=x_field,
                y_field=y_field,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                weights=weights,
                heatmap_colorscale=heatmap_colorscale,
                show_colorbars=show_heatmap_colorbar,
                heatmap_norm=heatmap_norm,
                colorbar_style=cb_style,
                sigma_px=heatmap_sigma_px,
            )
        elif not words.empty:
            _add_word_level_heatmap(
                fig,
                words,
                fixations,
                x_field=x_field,
                y_field=y_field,
                weights=weights,
                heatmap_colorscale=heatmap_colorscale,
                heatmap_range=heatmap_range,
                show_colorbars=show_heatmap_colorbar,
                heatmap_norm=heatmap_norm,
                colorbar_style=cb_style,
            )
        else:
            _add_density_heatmap(
                fig,
                fixations,
                x_field=x_field,
                y_field=y_field,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                weights=weights,
                heatmap_colorscale=heatmap_colorscale,
                heatmap_range=heatmap_range,
                show_colorbars=show_heatmap_colorbar,
                heatmap_norm=heatmap_norm,
                colorbar_style=cb_style,
            )
    elif spatial_axes and show_heatmap and not words.empty:
        # Words-only dataset (no fixation report): fall back to the words
        # frame's own pre-aggregated reading measures for the box heatmap. The
        # corpus "word difficulty on the stimulus" view (AN-4) passes an explicit
        # ``word_heatmap_col`` + title so it can tint by any aggregate or rate.
        if word_heatmap_col is not None and word_heatmap_col in words.columns:
            heatmap_rendered = True
            values = pd.to_numeric(words[word_heatmap_col], errors="coerce").fillna(0.0)
            _draw_word_value_heatmap(
                fig,
                words,
                [float(v) for v in values],
                heatmap_colorscale=heatmap_colorscale,
                heatmap_range=heatmap_range,
                show_colorbars=show_heatmap_colorbar,
                heatmap_norm=heatmap_norm,
                colorbar_title=_plotly_literal(word_heatmap_title or "Value"),
                colorbar_style=cb_style,
            )
        else:
            measure = (
                "total_fixation_duration_ms"
                if heatmap_metric == "duration_ms"
                else "n_fixations"
            )
            if measure in words.columns:
                heatmap_rendered = True
                _add_word_measure_heatmap(
                    fig,
                    words,
                    measure,
                    heatmap_colorscale=heatmap_colorscale,
                    heatmap_range=heatmap_range,
                    show_colorbars=show_heatmap_colorbar,
                    heatmap_norm=heatmap_norm,
                    colorbar_style=cb_style,
                )

    # Saccade lines + optional direction arrowheads (drawn before the fixation
    # markers so the dots sit on top).
    if spatial_axes and show_saccades and len(fixations) > 1:
        # VIZ-8: "By type" colours each saccade by its reading class. The class is
        # geometry-derived per trial (like color-by-line above), so compute it
        # here from the trial's fixations + words — reuse a precomputed
        # `saccade_class` column if the pipeline already added one. Classify on the
        # RAW fixations (word_id is unchanged by the snap).
        # VIZ-19: "Forward / regression" is the same classification folded into
        # two buckets, so both non-uniform modes take this path.
        # VIZ-31: the same classification also backs the reading-class *filter*
        # (`saccade_classes` = the classes to draw, ``None`` meaning all), so
        # classify whenever either the colour mode or the filter needs it. A
        # filter naming every class is a no-op and takes the cheaper raw path.
        class_series = None
        two_way_saccades = saccade_color_mode == "Forward / regression"
        color_by_class = saccade_color_mode in ("By type", "Forward / regression")
        visible_classes = (
            None
            if saccade_classes is None
            or set(saccade_classes) >= set(SACCADE_CLASS_ORDER)
            else set(saccade_classes)
        )
        if color_by_class or visible_classes is not None:
            existing = fixations.get("saccade_class")
            if existing is not None:
                class_series = existing
            else:
                from .measures import classify_saccades

                class_series = classify_saccades(fixations, words)
        if _add_saccade_layer(
            fig,
            render_fix,
            x_field=x_field,
            y_field=y_field,
            color=saccade_color,
            width=saccade_width,
            style=saccade_style,
            show_arrows=show_saccade_arrows,
            saccade_classes=class_series,
            color_by_class=color_by_class,
            class_colors=saccade_class_colors,
            class_legend=saccade_type_legend,
            visible_classes=visible_classes,
            render_mode=saccade_render_mode,
            two_way=two_way_saccades,
        ):
            legend_active = True

    # Drift connectors (PRE-3): one faint grey vertical segment per fixation from
    # its original y (`connector_y`) to its drift-corrected y (the already-snapped
    # `fixations["y"]`). A SINGLE Scatter with None separators (scales with the
    # true-scale embed), drawn before the fixation markers so the dots sit on top.
    if (
        spatial_axes
        and show_connectors
        and connector_y is not None
        and not fixations.empty
    ):
        xs = pd.to_numeric(fixations[x_field], errors="coerce").to_numpy(dtype=float)
        y_corr = pd.to_numeric(fixations[y_field], errors="coerce").to_numpy(
            dtype=float
        )
        y_orig = np.asarray(connector_y, dtype=float)
        seg_x: list = []
        seg_y: list = []
        for xi, yo, yc in zip(xs, y_orig, y_corr):
            if not (np.isfinite(xi) and np.isfinite(yo) and np.isfinite(yc)):
                continue
            seg_x += [xi, xi, None]
            seg_y += [yo, yc, None]
        if seg_x:
            fig.add_trace(
                go.Scatter(
                    x=seg_x,
                    y=seg_y,
                    mode="lines",
                    line=dict(color="rgba(110,110,110,0.9)", width=1),
                    opacity=0.3,
                    hoverinfo="skip",
                    showlegend=False,
                    name="drift",
                )
            )

    if show_fixations and not fixations.empty:
        # ``render_fix`` == fixations unless VIZ-9 snap-to-word is on, in which
        # case the markers, order labels and colour-by-line use the snapped x/y.
        ordered = render_fix.sort_values("timestamp_ms")
        # Fixation classification (PRE-2, viz-only): SHORT / LONG / OUT-OF-BOUNDS,
        # each Off / Highlight / Discard. Apply Discard here — drop those rows from
        # `ordered` so they vanish from the markers, fixation-index labels and
        # marker-size scaling (the saccade layer above still bridges across them).
        # This changes only what's DRAWN; reading measures and exports are untouched.
        flags = fixation_flags or {}
        if flags:
            ordered = _discard_flagged_fixations(
                ordered, words, flags, spatial_axes=spatial_axes
            )
        # "Color by line" overrides the chosen color field: each fixation is
        # tinted by the text line it lands on (lines inferred from word
        # geometry). Rendered as discrete categories so the legend reads
        # "line: Line 1", "line: Line 2", …
        if color_by_line and spatial_axes and not words.empty:
            from .measures import assign_fixation_lines

            line_ids = assign_fixation_lines(ordered, words)
            color_data = line_ids.map(
                lambda v: f"Line {int(v) + 1}" if pd.notna(v) else "(off-text)"
            )
            color_label = "line"
            is_numeric_color = False
        elif color_by == UNIFORM_COLOR_FIELD:
            # VIZ-17: no variable mapped to hue — size already encodes duration.
            color_data = None
            color_label = color_by
            is_numeric_color = False
        else:
            color_data = ordered[color_by] if color_by in ordered.columns else None
            color_label = color_by
            is_numeric_color = color_data is not None and pd.api.types.is_numeric_dtype(
                color_data
            )
        marker_color, category_legend = _resolve_marker_colors(
            color_data, is_numeric_color, fixation_color
        )
        sizes = _compute_marker_sizes(
            ordered["duration_ms"], marker_size_range, **_settings_size_scale(settings)
        )
        marker = dict(
            size=sizes,
            symbol=fixation_symbol or DEFAULT_FIXATION_SYMBOL,
            color=marker_color,
            colorscale=fixation_colorscale if is_numeric_color else None,
            showscale=show_colorbars and is_numeric_color,
            colorbar=_colorbar_dict(
                _column_title(color_label),
                orientation=colorbar_orientation,
                tickangle=colorbar_tickangle,
                tickfont_size=colorbar_tickfont_size,
            )
            if show_colorbars and is_numeric_color
            else None,
            cmin=fixation_color_range[0] if fixation_color_range else None,
            cmax=fixation_color_range[1] if fixation_color_range else None,
            line=dict(color=FIX_MARKER_OUTLINE, width=0.5),
        )
        # Marker alpha (VIZ-6): lower it so overlapping fixations show through.
        # Always set it (even at 1.0) so the slider is authoritative — Plotly's
        # variable-size scatter markers otherwise render at a ~0.7 default, so an
        # unset 1.0 looked translucent ("opacity at 1 wasn't really 1").
        marker["opacity"] = float(
            fixation_opacity if fixation_opacity is not None else 1.0
        )
        if hollow_fixations:
            marker = _make_hollow(marker)
        hover_fields = (
            ["order_in_trial", "duration_ms", "word_id"]
            if fixation_hover_fields is None
            else list(fixation_hover_fields)
        )
        customdata, hovertemplate = _hover_payload(ordered, hover_fields)
        glyph = FIXATION_GLYPH_SYMBOLS.get(fixation_symbol or "")
        if glyph:
            # VIZ-15: a shape Plotly's marker enum doesn't carry (♥), drawn as
            # text from the same marker dict (`_glyph_scatter_traces`); the
            # fixation-index labels move to their own trace since one Scatter has
            # only one text field, and a numeric colour bar to its own.
            for trace in _glyph_scatter_traces(
                ordered[x_field],
                ordered[y_field],
                marker,
                glyph,
                hovertemplate=hovertemplate,
                customdata=customdata,
                name="Fixations",
                showlegend=False,
            ):
                fig.add_trace(trace)
            bar = _glyph_colorbar_trace(marker, color_data if is_numeric_color else ())
            if bar is not None:
                fig.add_trace(bar)
            if show_order:
                fig.add_trace(
                    go.Scatter(
                        x=ordered[x_field],
                        y=ordered[y_field],
                        mode="text",
                        text=ordered["order_in_trial"],
                        textfont=dict(
                            color=order_font_color,
                            size=order_font_size,
                            family=font_settings["family"],
                        ),
                        textposition="top center",
                        hoverinfo="skip",
                        name="Fixation index",
                        showlegend=False,
                    )
                )
        else:
            fig.add_trace(
                go.Scatter(
                    x=ordered[x_field],
                    y=ordered[y_field],
                    mode="markers+text" if show_order else "markers",
                    marker=marker,
                    text=ordered["order_in_trial"] if show_order else None,
                    textfont=dict(
                        color=order_font_color,
                        size=order_font_size,
                        family=font_settings["family"],
                    ),
                    textposition="top center",
                    hovertemplate=hovertemplate,
                    customdata=customdata,
                    name="Fixations",
                    showlegend=False,
                )
            )
        legend_limit = len(_QUALITATIVE_PALETTE)
        truncated_legend = category_legend[:legend_limit]
        if category_legend:
            legend_active = True
        for category, color in truncated_legend:
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker=dict(
                        size=10,
                        color=color,
                        line=dict(color=FIX_MARKER_OUTLINE, width=0.5),
                    ),
                    name=f"{_column_name(color_label)}: {category}",
                    showlegend=True,
                    hoverinfo="skip",
                )
            )
        if len(category_legend) > legend_limit:
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker=dict(size=10, color="#cccccc"),
                    name=f"… +{len(category_legend) - legend_limit} more",
                    showlegend=True,
                    hoverinfo="skip",
                )
            )

        # Highlight overlays (PRE-2): mark SHORT / LONG / OUT-OF-BOUNDS fixations
        # in the chosen marker + colour, on top of the regular markers. Masks are
        # recomputed on the (post-discard) `ordered`; out-of-bounds needs word
        # boxes + spatial axes, short/long are duration-based and apply anywhere.
        if flags:
            _overlay = _fixation_flag_masks(
                ordered, words, flags, spatial_axes=spatial_axes
            )
            for _cat in _FIX_FLAG_CATEGORIES:
                _spec = flags.get(_cat, {})
                if _spec.get("mode") != "Highlight":
                    continue
                _name = _FIX_FLAG_LABELS[_cat]
                hits = ordered[_overlay[_cat]]
                if hits.empty:
                    continue
                legend_active = True
                fig.add_trace(
                    go.Scatter(
                        x=hits[x_field],
                        y=hits[y_field],
                        mode="markers",
                        marker=dict(
                            symbol=_spec.get("symbol") or "x",
                            size=13,
                            color=_spec.get("color") or OUT_OF_TEXT_COLOR,
                            line=dict(color="#ffffff", width=1),
                        ),
                        name=_name,
                        showlegend=True,
                        hovertemplate=(
                            f"{_name} fixation<br>x %{{x:.0f}}, y %{{y:.0f}}"
                            "<extra></extra>"
                        ),
                    )
                )

    xaxis_cfg = dict(showticklabels=False, showgrid=False, zeroline=False, title=None)
    yaxis_cfg = dict(showticklabels=False, showgrid=False, zeroline=False, title=None)
    if spatial_axes:
        # automargin off: the colorbar/legend live in the reserved margin we size
        # below (_decoration_margins), so Plotly must not also shrink the
        # equal-aspect plot domain to fit them.
        xaxis_cfg.update(range=x_range, constrain="domain", automargin=False)
        yaxis_cfg.update(
            range=y_range,
            constrain="domain",
            scaleanchor="x",
            scaleratio=1,
            automargin=False,
        )
        _apply_coordinate_grid_axes(
            xaxis_cfg,
            yaxis_cfg,
            show=show_coordinate_grid,
            spacing=coordinate_grid_spacing,
            x_range=x_range,
            y_range=y_range,
            rendered_width=fitted_w,
            rendered_height=fitted_h,
        )
    else:
        xaxis_cfg.update(
            showticklabels=True, showgrid=True, title=_column_title(x_field)
        )
        yaxis_cfg.update(
            showticklabels=True, showgrid=True, title=_column_title(y_field)
        )

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
                # VIZ-5: the plot border is its own layer (a registration guide).
                name=_shape_layer_tag("frame"),
            )
        )

    # fitted_w / fitted_h were computed up front (so the label scale matched). A
    # colorbar (numeric colour / heatmap) or legend (discrete colour categories,
    # out-of-text, raw gaze) is given reserved margin so it never shrinks the
    # equal-aspect plot region — keeping the word labels matched to the boxes.
    decoration = (
        _decoration_margins(
            fitted_w,
            fitted_h,
            **_colorbar_reserves(
                (show_colorbars and is_numeric_color, colorbar_orientation),
                (show_heatmap_colorbar and heatmap_rendered, cb_style["orientation"]),
            ),
            legend=legend_active,
            coordinate_grid=show_coordinate_grid,
        )
        if spatial_axes
        else {"width": fitted_w, "height": fitted_h, "margin": dict(l=0, r=0, t=0, b=0)}
    )
    fig.update_layout(
        height=decoration["height"],
        width=decoration["width"],
        autosize=False,
        margin=decoration["margin"],
        xaxis=xaxis_cfg,
        yaxis=yaxis_cfg,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        # None leaves the template's default white; a hex value paints both the
        # plotting area and the surrounding paper (e.g. a neutral gray).
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        font=font_settings,
        shapes=shapes,
    )
    add_illustration_label(fig, illustration_reasons, text=settings.illustration_text)
    return fig


def add_illustration_label(
    fig: go.Figure, reasons: Sequence[str] | None, *, text: str = ""
) -> go.Figure:
    """Stamp a figure and its metadata when it is schematic or transformed.

    ``text`` replaces the drawn wording; empty draws "Illustration · <reasons>".
    The reasons are recorded in the metadata either way."""
    reasons = [str(reason) for reason in (reasons or []) if reason]
    if not reasons:
        return fig
    fig.add_annotation(
        x=1,
        y=0,
        xref="paper",
        yref="paper",
        xanchor="right",
        yanchor="bottom",
        text=_plotly_literal(str(text).strip())
        or "Illustration · " + "; ".join(reasons),
        showarrow=False,
        font=dict(size=10, color="#5f6368"),
        bgcolor="rgba(255,255,255,0.82)",
        borderpad=3,
        name=_ILLUSTRATION_LABEL_NAME,
    )
    _stack_bottom_right(fig)
    metadata = dict(fig.layout.meta or {})
    metadata["illustration"] = True
    metadata["illustration_reasons"] = reasons
    fig.update_layout(meta=metadata)
    return fig


# VIZ-3: alternative heatmap normalization. The colour of a heatmap cell maps
# LINEARLY between its z-range endpoints, so a few very-hot words (dwell times are
# heavy-tailed) can wash out the rest. "Log" instead maps colour to log1p(value),
# compressing the top of the range so mid-range words stay distinguishable. The
# transform is applied to the *values and the range endpoints together*, so the
# raw-unit `heatmap_range` slider keeps its meaning; only the colour curve changes.
_HEATMAP_NORMS = ("Linear", "Log")


def _apply_heatmap_norm(values, norm: str):
    """Transform heatmap values for the chosen normalization (VIZ-3).

    ``Log`` returns ``log1p(max(value, 0))`` (heavy-tail compression); anything
    else is the identity. Accepts a scalar or an array; returns the same shape."""
    arr = np.asarray(values, dtype=float)
    if norm == "Log":
        return np.log1p(np.clip(arr, 0.0, None))
    return arr


#: The duration-weighted word-box heatmap's colour-bar title: a box maps the
#: *summed* duration of its fixations, which a fixation-duration colour bar
#: beside it must not be mistaken for (round-7 review, findings 11 and 16).
_WORD_DWELL_TITLE = "Dwell time per word (ms)"


def _heatmap_title(base: str, norm: str) -> str:
    """Colour-bar title, marked ``(log)`` when the log normalization is active."""
    return f"{base} (log)" if norm == "Log" else base


def _add_word_level_heatmap(
    fig: go.Figure,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    x_field: str,
    y_field: str,
    weights: pd.Series | None,
    heatmap_colorscale: str,
    heatmap_range: tuple[float, float] | None,
    show_colorbars: bool,
    heatmap_norm: str = "Linear",
    colorbar_style: dict | None = None,
) -> None:
    # Pull the fixation coordinates (and optional weights) into numpy arrays once,
    # then test box membership per word against the arrays. Same O(words × fix)
    # work as before but without rebuilding pandas Series each iteration, and with
    # O(fix) memory (no full words × fix matrix).
    fx = pd.to_numeric(fixations[x_field], errors="coerce").to_numpy(dtype=float)
    fy = pd.to_numeric(fixations[y_field], errors="coerce").to_numpy(dtype=float)
    w_arr = (
        pd.to_numeric(weights, errors="coerce").to_numpy(dtype=float)
        if weights is not None
        else None
    )
    # Bin against the experiment's boxes (BUG-83) with the assignment's own
    # containment rule — the same boundary it uses and the heatmap then draws,
    # and half-open, so a fixation on a shared edge counts towards one word.
    from .measures import word_box_bounds, word_box_contains

    word_values = []
    for wx0, wy0, wx1, wy1 in zip(*word_box_bounds(words)):
        in_word = word_box_contains(fx, fy, wx0, wy0, wx1, wy1)
        val = (
            float(np.nansum(w_arr[in_word]))
            if w_arr is not None
            else float(in_word.sum())
        )
        word_values.append(val)

    _draw_word_value_heatmap(
        fig,
        words,
        word_values,
        heatmap_colorscale=heatmap_colorscale,
        heatmap_range=heatmap_range,
        show_colorbars=show_colorbars,
        heatmap_norm=heatmap_norm,
        colorbar_title="Fixation count" if weights is None else _WORD_DWELL_TITLE,
        colorbar_style=colorbar_style,
    )


def _add_word_measure_heatmap(
    fig: go.Figure,
    words: pd.DataFrame,
    measure: str,
    *,
    heatmap_colorscale: str,
    heatmap_range: tuple[float, float] | None,
    show_colorbars: bool,
    heatmap_norm: str = "Linear",
    colorbar_style: dict | None = None,
) -> None:
    """Word-box heatmap from a pre-aggregated per-word measure column.

    Used for words-only datasets (IA report without a fixation report): the
    usual heatmap aggregates fixation durations/counts into the boxes, but
    with no fixations the dataset's own reading measures (e.g. total fixation
    duration) carry the same information."""
    values = pd.to_numeric(words[measure], errors="coerce").fillna(0.0)
    _draw_word_value_heatmap(
        fig,
        words,
        [float(v) for v in values],
        heatmap_colorscale=heatmap_colorscale,
        heatmap_range=heatmap_range,
        show_colorbars=show_colorbars,
        heatmap_norm=heatmap_norm,
        colorbar_title="Fixation count"
        if measure == "n_fixations"
        else _WORD_DWELL_TITLE,
        colorbar_style=colorbar_style,
    )


def _draw_word_value_heatmap(
    fig: go.Figure,
    words: pd.DataFrame,
    word_values: list,
    *,
    heatmap_colorscale: str,
    heatmap_range: tuple[float, float] | None,
    show_colorbars: bool,
    heatmap_norm: str = "Linear",
    colorbar_title: str,
    colorbar_style: dict | None = None,
) -> None:
    from plotly.colors import sample_colorscale

    from .measures import word_box_bounds

    # Nonzero test on the RAW values (a word with no dwell stays uncoloured); the
    # colour position then maps through the chosen normalization (VIZ-3). Boxes
    # come from word_box_bounds so the tinted rects sit exactly on the outlines
    # build_word_boxes draws.
    boxes = zip(*word_box_bounds(words))
    nonzero_rows = [(box, v) for box, v in zip(boxes, word_values) if v > 0]
    if not nonzero_rows:
        return
    vals = [v for _, v in nonzero_rows]
    # Auto starts at 0: an empty word is the bottom of the scale.
    z_min_raw = heatmap_range[0] if heatmap_range else 0.0
    z_max_raw = heatmap_range[1] if heatmap_range else float(max(vals))
    z_min = float(_apply_heatmap_norm(z_min_raw, heatmap_norm))
    z_max = float(_apply_heatmap_norm(z_max_raw, heatmap_norm))
    z_span = max(z_max - z_min, 1e-9)

    heatmap_shapes = []
    for (x0, y0, x1, y1), v in nonzero_rows:
        tv = float(_apply_heatmap_norm(v, heatmap_norm))
        norm = max(0.0, min(1.0, (tv - z_min) / z_span))
        color = sample_colorscale(heatmap_colorscale, [norm])[0]
        heatmap_shapes.append(
            dict(
                type="rect",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                line=dict(width=0),
                fillcolor=color,
                opacity=0.5,
                layer="below",
                # VIZ-5: word-box heatmap rects belong to the heatmap layer.
                name=_shape_layer_tag("heatmap"),
            )
        )
    existing = list(fig.layout.shapes) if fig.layout.shapes else []
    fig.update_layout(shapes=existing + heatmap_shapes)
    if show_colorbars:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    colorscale=heatmap_colorscale,
                    showscale=True,
                    cmin=z_min,
                    cmax=z_max,
                    colorbar=_colorbar_dict(
                        _heatmap_title(colorbar_title, heatmap_norm),
                        **(colorbar_style or {}),
                    ),
                ),
                showlegend=False,
                hoverinfo="skip",
                # VIZ-5: the word-box heatmap's colorbar-carrier rides the heatmap
                # layer (name contains "heatmap" → classified there).
                name="heatmap colorbar",
            )
        )


def _add_density_heatmap(
    fig: go.Figure,
    fixations: pd.DataFrame,
    *,
    x_field: str,
    y_field: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    weights: pd.Series | None,
    heatmap_colorscale: str,
    heatmap_range: tuple[float, float] | None,
    show_colorbars: bool,
    heatmap_norm: str = "Linear",
    colorbar_style: dict | None = None,
) -> None:
    # A 40×40 count/duration grid drawn as a go.Heatmap (rather than
    # go.Histogram2d) so the colour mapping can go through _apply_heatmap_norm
    # (VIZ-3) — Plotly's Histogram2d bins internally and can't be log-scaled.
    xs = pd.to_numeric(fixations[x_field], errors="coerce")
    ys = pd.to_numeric(fixations[y_field], errors="coerce")
    valid = xs.notna() & ys.notna()
    if not valid.any():
        return
    if weights is not None:
        w = (
            pd.to_numeric(weights, errors="coerce")
            .reindex(fixations.index)
            .fillna(0.0)[valid]
            .to_numpy()
        )
    else:
        w = np.ones(int(valid.sum()))
    xv = xs[valid].to_numpy()
    yv = ys[valid].to_numpy()

    x_edges = np.linspace(x_min, x_max, 41)
    y_edges = np.linspace(y_min, y_max, 41)
    hist, _, _ = np.histogram2d(xv, yv, bins=[x_edges, y_edges], weights=w)
    grid = hist.T  # rows index y, cols index x — the orientation go.Heatmap wants
    if grid.max() <= 0:
        return
    z = np.where(grid > 0, _apply_heatmap_norm(grid, heatmap_norm), np.nan)
    z_range = (
        _apply_heatmap_norm(np.asarray(heatmap_range, dtype=float), heatmap_norm)
        if heatmap_range
        else (None, None)
    )
    base_title = "Fixation density" if weights is None else "Duration (ms)"
    fig.add_trace(
        go.Heatmap(
            x=(x_edges[:-1] + x_edges[1:]) / 2.0,
            y=(y_edges[:-1] + y_edges[1:]) / 2.0,
            z=z,
            colorscale=heatmap_colorscale,
            opacity=0.35,
            showscale=show_colorbars,
            colorbar=_colorbar_dict(
                _heatmap_title(base_title, heatmap_norm), **(colorbar_style or {})
            ),
            zmin=z_range[0],
            zmax=z_range[1],
            hoverinfo="skip",
            name="Fixation heatmap",
        )
    )


# Past this radius the 3-sigma kernel's normalising sum is taken from the
# Gaussian integral (exact to float precision at that sigma) instead of an array.
_KERNEL_EXACT_SUM_RADIUS = 100_000


def _gaussian_kernel_1d(sigma: float, max_radius: int | None = None) -> np.ndarray:
    """Normalized 1-D Gaussian kernel, truncated at 3 sigma.

    ``max_radius`` builds only the central taps, still normalized over the full
    3-sigma kernel, so a short axis pays for the taps it can reach rather than
    for sigma.
    """
    radius = max(1, round(sigma * 3))
    keep = radius if max_radius is None else max(0, min(radius, max_radius))
    offsets = np.arange(-keep, keep + 1)
    kernel = np.exp(-(offsets**2) / (2.0 * sigma * sigma))
    if keep == radius:
        total = kernel.sum()
    elif radius <= _KERNEL_EXACT_SUM_RADIUS:
        full = np.arange(-radius, radius + 1)
        total = np.exp(-(full**2) / (2.0 * sigma * sigma)).sum()
    else:
        total = (
            sigma
            * math.sqrt(2.0 * math.pi)
            * math.erf((radius + 0.5) / (sigma * math.sqrt(2.0)))
        )
    return kernel / total


def _blur_axis(grid: np.ndarray, sigma: float, axis: int) -> np.ndarray:
    """Zero-padded Gaussian blur along one axis; the output keeps ``grid``'s shape.

    ``np.convolve(mode="same")`` returns the *kernel's* length when the kernel
    is longer than the axis, which shifted the density off its coordinates on a
    short grid. Padding by the kernel radius and taking the ``valid`` part pins
    the length. Taps further out than the axis is long only ever meet the zero
    padding, so they are never built: the result is identical and the cost is
    bounded by the axis length, not by sigma.
    """
    kernel = _gaussian_kernel_1d(sigma, max_radius=grid.shape[axis] - 1)
    radius = len(kernel) // 2
    pad = [(0, 0)] * grid.ndim
    pad[axis] = (radius, radius)
    padded = np.pad(grid, pad)
    return np.apply_along_axis(
        lambda v: np.convolve(v, kernel, mode="valid"), axis, padded
    )


def _gaussian_blur_2d(
    grid: np.ndarray, sigma_rows: float, sigma_cols: float
) -> np.ndarray:
    """Separable Gaussian blur (a numpy-only stand-in for scipy.ndimage).

    Zero padding beyond the grid; the output always has the input's shape.
    """
    out = grid.astype(float)
    if out.size == 0:
        return out
    if sigma_rows and sigma_rows > 0:
        out = _blur_axis(out, sigma_rows, 0)
    if sigma_cols and sigma_cols > 0:
        out = _blur_axis(out, sigma_cols, 1)
    return out


# Interpolated-heatmap tuning. The Gaussian sigma defaults to a fraction of the
# larger data span — enough to merge a fixation cluster into one smooth blob
# without bleeding across neighbouring text lines.
_INTERP_GRID = 240  # cells along the wider axis
_INTERP_SIGMA_FRAC = 0.02  # sigma as a fraction of the larger data span
_INTERP_MIN_SIGMA_PX = 8.0


def interpolated_sigma_px(x_span: float, y_span: float) -> float:
    """The Interpolated heatmap's automatic Gaussian σ, in px: 2% of the data's
    larger span (fixations, word boxes and shown raw gaze), at least 8 px."""
    return max(_INTERP_MIN_SIGMA_PX, _INTERP_SIGMA_FRAC * max(x_span, y_span))


_INTERP_OPACITY = 0.45
_INTERP_FLOOR_FRAC = 0.02  # cells below this fraction of the peak render transparent
_INTERP_MIN_CELLS = 10  # cells along the narrower axis, at least
_INTERP_MIN_SPAN_PX = 2.0 * _INTERP_MIN_SIGMA_PX  # narrower than this is widened


def _interp_grid_shape(x_span: float, y_span: float) -> tuple[int, int]:
    """(nx, ny) cells: _INTERP_GRID on the wider axis, a proportional share on
    the other, each within [_INTERP_MIN_CELLS, _INTERP_GRID]."""
    wide = max(x_span, y_span)
    narrow = min(x_span, y_span)
    share = round(_INTERP_GRID * narrow / wide) if wide > 0 else _INTERP_GRID
    n_narrow = int(min(_INTERP_GRID, max(_INTERP_MIN_CELLS, share)))
    if x_span >= y_span:
        return _INTERP_GRID, n_narrow
    return n_narrow, _INTERP_GRID


def _add_interpolated_heatmap(
    fig: go.Figure,
    fixations: pd.DataFrame,
    *,
    x_field: str,
    y_field: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    weights: pd.Series | None,
    heatmap_colorscale: str,
    show_colorbars: bool,
    heatmap_norm: str = "Linear",
    colorbar_style: dict | None = None,
    sigma_px: float | None = None,
    title: str | None = None,
) -> None:
    """Smooth, word-box-independent fixation heatmap (Gaussian-interpolated).

    Bins the fixations onto a fine grid (weighted by duration when ``weights``
    is given), then blurs with a Gaussian — the classic eye-movement heatmap
    (cf. PyGaze's gaze plotter). Empty cells render transparent so the reading
    text stays legible underneath.
    """
    xs = pd.to_numeric(fixations[x_field], errors="coerce")
    ys = pd.to_numeric(fixations[y_field], errors="coerce")
    valid = xs.notna() & ys.notna()
    if not valid.any():
        return
    if weights is not None:
        w = (
            pd.to_numeric(weights, errors="coerce")
            .reindex(fixations.index)
            .fillna(0.0)[valid]
            .to_numpy()
        )
    else:
        w = np.ones(int(valid.sum()))
    xs = xs[valid].to_numpy()
    ys = ys[valid].to_numpy()

    x_span = max(x_max - x_min, 1.0)
    y_span = max(y_max - y_min, 1.0)
    sigma_px = float(sigma_px or interpolated_sigma_px(x_span, y_span))
    # An axis with (next to) no extent — coincident fixations, one row or one
    # column of a fixation-only import — is widened around its centre to the
    # blob's own size (±3 sigma), so the edges match the span the cells and the
    # sigma are computed from, and the blob is round rather than a sliver.
    min_span = max(_INTERP_MIN_SPAN_PX, 6.0 * sigma_px)
    if x_max - x_min < _INTERP_MIN_SPAN_PX:
        x_mid = (x_min + x_max) / 2.0
        x_min, x_max, x_span = x_mid - min_span / 2, x_mid + min_span / 2, min_span
    if y_max - y_min < _INTERP_MIN_SPAN_PX:
        y_mid = (y_min + y_max) / 2.0
        y_min, y_max, y_span = y_mid - min_span / 2, y_mid + min_span / 2, min_span
    # The cell budget sits on the wider axis and the other gets its share of it,
    # so neither axis, nor the grid, outgrows _INTERP_GRID (squared): a tall,
    # narrow reading must not ask for 240 cells across and 96,000 down.
    nx, ny = _interp_grid_shape(x_span, y_span)
    x_edges = np.linspace(x_min, x_max, nx + 1)
    y_edges = np.linspace(y_min, y_max, ny + 1)
    # histogram2d returns shape (nx, ny); transpose so rows index y, cols index x
    # (the orientation go.Heatmap's z expects).
    hist, _, _ = np.histogram2d(xs, ys, bins=[x_edges, y_edges], weights=w)
    grid = hist.T

    blurred = _gaussian_blur_2d(
        grid, sigma_rows=sigma_px / (y_span / ny), sigma_cols=sigma_px / (x_span / nx)
    )
    peak = float(blurred.max())
    if peak <= 0:
        return
    # Near-zero cells -> NaN so Plotly renders them transparent (only populated
    # regions get tinted, keeping the text readable). The remaining density maps
    # through the chosen normalization (VIZ-3; log1p(0)=0 keeps the floor at 0).
    z = np.where(blurred < peak * _INTERP_FLOOR_FRAC, np.nan, blurred)
    z = _apply_heatmap_norm(z, heatmap_norm)

    base_title = title or (
        "Dwell-time density" if weights is not None else "Fixation density"
    )
    fig.add_trace(
        go.Heatmap(
            x=(x_edges[:-1] + x_edges[1:]) / 2.0,
            y=(y_edges[:-1] + y_edges[1:]) / 2.0,
            z=z,
            colorscale=heatmap_colorscale,
            opacity=_INTERP_OPACITY,
            showscale=show_colorbars,
            # z is a Gaussian-smoothed density in arbitrary (weighted) units, not
            # the per-word counts/ms the `heatmap_range` slider is calibrated for,
            # so it autoscales from 0 rather than borrowing that range.
            zmin=0.0,
            colorbar=_colorbar_dict(
                _heatmap_title(base_title, heatmap_norm), **(colorbar_style or {})
            ),
            hoverinfo="skip",
            name="Fixation heatmap",
        )
    )


# =============================================================================
# Scanpath animation — one or two scanpaths on a shared real reading-time clock
# =============================================================================

# Floor on the ▶ Play button's own per-frame duration: ~one 60 fps display frame.
# That duration only drives Plotly's frame queue, which is what a figure plays on
# where the wall-clock player isn't embedded (`fig.show()`); every HTML surface
# replays on `animation_player_post_script` instead (BUG-93).
_ANIM_MIN_FRAME_MS = 16
# VIZ-11: animation frames sit on a UNIFORM time grid (one every
# _ANIM_GRID_STEP_MS of reading) rather than one per fixation onset, so the
# slider scrubs linearly through seconds regardless of how fixations cluster or
# how many scanpaths overlay. The grid coarsens past _ANIM_MAX_FRAMES so a long
# reading doesn't emit thousands of frames (which would balloon the GIF/MP4
# export); quantization is then at most one grid step.
_ANIM_GRID_STEP_MS = 100.0
_ANIM_MAX_FRAMES = 360

# Vertical space (px) reserved BELOW the animation plot for the transport
# controls (play / pause / restart buttons + the time slider with its "Elapsed"
# readout). The figure is grown by this much (plus a small safety buffer) and
# the controls are placed in the bottom margin, so Plotly's automargin never has
# to shrink the equal-aspect plot to fit them — which would make the word boxes
# smaller than the true-to-scale label font computed for fitted_h (the
# text-too-large bug). Keeps the animation plot the SAME size as the static one.
_CONTROLS_MARGIN_PX = 116
_CONTROLS_SAFETY_PX = 24


def _scanpath_anim_specs(
    entries,
    marker_size_range,
    scale: str = DEFAULT_MARKER_SIZE_SCALE,
    duration_range=DEFAULT_MARKER_DURATION_RANGE,
    *,
    size_ranges=None,
):
    """Build per-scanpath animation specs from (fixations, color, label) entries.

    Empty/None fixations are skipped. Onsets are the recorded ``timestamp_ms``
    rebased to each reading's first fixation, so multiple scanpaths share one
    *real reading-time* clock. When timestamps aren't real times — missing, or
    the 0,1,2,… row index ``data.normalize_fixations`` synthesises when the
    source has no timestamp column — fixations are instead laid out back-to-back
    by their durations. Marker sizes use the figure's duration scale; under the
    relative scale they span the COMBINED durations, so equal durations still
    render at equal sizes across the two scanpaths.

    ``size_ranges`` (one per entry, default ``marker_size_range`` for each)
    gives each scanpath its own size range, as Compare's per-scanpath *Size*
    does: the duration scale stays shared — one duration is one *fraction* of
    the range on either side — and each side maps that fraction onto its own.
    """
    from .measures import rebased_fixation_onsets

    if size_ranges is None:
        size_ranges = [marker_size_range] * len(entries)
    specs = []
    for (fix_df, color, label), size_range in zip(entries, size_ranges):
        if fix_df is None or fix_df.empty:
            continue
        ordered = fix_df.sort_values("timestamp_ms").reset_index(drop=True)
        dur = pd.to_numeric(ordered["duration_ms"], errors="coerce").fillna(0)
        # Recorded-timestamp-vs-synthetic-index heuristic (shared with the
        # similarity time-curve): trust recorded timestamps only when they look
        # like real times, else lay fixations back-to-back by their durations.
        onsets = rebased_fixation_onsets(ordered)
        specs.append(
            dict(
                ordered=ordered,
                dur=dur,
                onsets=onsets,
                end=float(onsets[-1] + dur.iloc[-1]),
                color=color,
                label=label,
                size_range=tuple(size_range),
            )
        )
    if specs:
        # Each duration's place on the shared scale, 0..1, then sized in its
        # own scanpath's range — identical to sizing the combined durations in
        # one range whenever the two ranges agree.
        fractions = _compute_marker_sizes(
            pd.concat([s["dur"] for s in specs], ignore_index=True),
            (0.0, 1.0),
            scale,
            duration_range,
        )
        cursor = 0
        for s in specs:
            n = len(s["dur"])
            low, high = s["size_range"]
            s["sizes"] = low + np.asarray(
                fractions[cursor : cursor + n], dtype=float
            ) * (high - low)
            cursor += n
    return specs


def _anim_frame_duration_ms(frame_step_ms: float, playback_speed: float) -> int:
    """▶ Play's own per-frame duration: one grid step at the playback speed.

    Floored at ``_ANIM_MIN_FRAME_MS``. The only part of a replay the speed
    changes besides ``layout.meta`` — which is what lets `set_replay_clock`
    re-time a built replay (PERF-15)."""
    return int(max(frame_step_ms / max(playback_speed, 1e-6), _ANIM_MIN_FRAME_MS))


def _anim_timeline(specs, *, grid_step_ms=None, max_frames=None):
    """Uniform time-grid frame timeline across all scanpaths (VIZ-11).

    Returns ``(frame_times, frame_step_ms, reading_span_ms)``. Frames are
    emitted on a **uniform time grid** — one every ``step`` ms, where ``step`` is
    ``grid_step_ms`` unless that would exceed ``max_frames`` frames (then it
    coarsens) — so the slider scrubs linearly through reading time no matter how
    fixations cluster or how many scanpaths overlay (the union of onset sets is
    meaningless for >1 reader). ``frame_step_ms`` is that exact step (``0.0`` with
    no frames). None of it depends on the playback speed: ▶ Play's own per-frame
    duration is :func:`_anim_frame_duration_ms` of the step, used only where the
    wall-clock player isn't embedded, and the player shows frame k once
    ``frame_times[k] / playback_speed`` has elapsed, so a replay takes
    ``reading_span_ms / playback_speed`` (BUG-93). Frame *content* is
    unchanged — every fixation whose onset ≤ t shows at time t. All readings are
    rebased to t=0; ``reading_span_ms`` is the longest reading's span. Returns an
    empty grid when there is nothing to animate.

    Both knobs are user-facing (VIZ-11 follow-up): they trade smoothness against
    frame count, which is what the GIF/MP4 export size and render time are made
    of. Defaults are ``_ANIM_GRID_STEP_MS`` / ``_ANIM_MAX_FRAMES``.
    """
    step_pref = float(grid_step_ms if grid_step_ms else _ANIM_GRID_STEP_MS)
    cap = int(max_frames if max_frames else _ANIM_MAX_FRAMES)
    reading_span_ms = max((s["end"] for s in specs), default=0.0)
    if not specs or reading_span_ms <= 0:
        return [], 0.0, reading_span_ms
    step = max(step_pref, reading_span_ms / max(cap, 1))
    frame_times = [
        min(k * step, reading_span_ms) for k in range(int(reading_span_ms // step) + 1)
    ]
    # Land the final frame exactly on the reading end so it reveals everything.
    if frame_times[-1] < reading_span_ms:
        frame_times.append(reading_span_ms)
    return frame_times, step, reading_span_ms


def _revealed_xy(all_x, all_y, kk):
    """Full-length x/y with only the first ``kk`` fixations revealed.

    Not-yet-reached fixations are masked to ``None`` so Plotly draws nothing
    there. The array length is the SAME in every frame — the replay reveals a
    fixation by un-masking its coordinate, never by growing the array — which is
    what lets the Play button animate with ``redraw=False`` (only positions
    change, so Plotly skips redrawing the static word boxes/labels each frame).
    """
    n = len(all_x)
    xs = [all_x[i] if i < kk else None for i in range(n)]
    ys = [all_y[i] if i < kk else None for i in range(n)]
    return xs, ys


def _revealed_saccade_xy(all_x, all_y, kk):
    """Constant-length saccade polyline for the first ``kk`` fixations.

    Every consecutive fixation pair occupies a fixed ``(x0, x1, None)`` slot;
    segments past the ``kk``-th fixation are blanked to ``None`` so the trace
    length never changes frame to frame (same ``redraw=False`` requirement as
    :func:`_revealed_xy`). Only which segments are drawn changes.
    """
    sx, sy = [], []
    for j in range(len(all_x) - 1):
        if j < kk - 1:
            sx.extend([all_x[j], all_x[j + 1], None])
            sy.extend([all_y[j], all_y[j + 1], None])
        else:
            sx.extend([None, None, None])
            sy.extend([None, None, None])
    return sx, sy


def _revealed_arrow_xy(all_x, all_y, seg_index, kk):
    """Constant-length saccade-arrow positions for the first ``kk`` fixations.

    An arrowhead belongs to the saccade leaving fixation ``seg_index[j]``, so it
    appears exactly when :func:`_revealed_saccade_xy` draws that segment — the
    arrows reveal *with* their saccades instead of all standing there from frame
    zero. Hidden arrows are masked to ``None`` rather than dropped, keeping the
    array (and its ``marker.angle``) the same length every frame, which is what
    the ``redraw=False`` playback needs.
    """
    xs = [x if seg_index[j] < kk - 1 else None for j, x in enumerate(all_x)]
    ys = [y if seg_index[j] < kk - 1 else None for j, y in enumerate(all_y)]
    return xs, ys


def animation_playback_ms(
    fixations_list, playback_speed, *, grid_step_ms=None, max_frames=None
):
    """Reading span and *actual* animation runtime for the given scanpath(s).

    Returns ``(reading_span_ms, playback_ms)``. ``playback_ms`` is what the replay
    takes: the wall-clock player (:func:`animation_player_post_script`) reaches the
    last frame once ``reading_span_ms / playback_speed`` has elapsed, so that is
    the time the side panel quotes and a GIF/MP4 lasts (BUG-93). Both 0 when there
    are no fixations.
    """
    summary = animation_timeline_summary(
        fixations_list, playback_speed, grid_step_ms=grid_step_ms, max_frames=max_frames
    )
    return summary["reading_span_ms"], summary["playback_ms"]


def animation_timeline_summary(
    fixations_list, playback_speed, *, grid_step_ms=None, max_frames=None
) -> dict:
    """What the chosen frame grid actually produces, without building the figure.

    VIZ-11 follow-up: the grid step and the frame cap are user controls, so the UI
    has to show their consequence — frame count, the effective step, and whether
    the cap *coarsened* the requested step. Silently coarsening is the thing that
    made the old hard-coded behaviour opaque.

    Returns ``{"n_frames", "step_ms", "requested_step_ms", "coarsened",
    "frame_duration_ms", "reading_span_ms", "playback_ms"}``.
    """
    requested = float(grid_step_ms if grid_step_ms else _ANIM_GRID_STEP_MS)
    specs = _scanpath_anim_specs(
        [(f, None, None) for f in fixations_list], DEFAULT_MARKER_SIZE_RANGE
    )
    frame_times, frame_step_ms, reading_span_ms = _anim_timeline(
        specs, grid_step_ms=grid_step_ms, max_frames=max_frames
    )
    n_frames = len(frame_times)
    step = (frame_times[1] - frame_times[0]) if n_frames > 1 else float(reading_span_ms)
    return {
        "n_frames": n_frames,
        "step_ms": float(step),
        "requested_step_ms": requested,
        "coarsened": bool(n_frames > 1 and step > requested + 1e-6),
        "frame_duration_ms": _anim_frame_duration_ms(frame_step_ms, playback_speed),
        "reading_span_ms": float(reading_span_ms),
        "playback_ms": float(reading_span_ms) / max(playback_speed, 1e-6),
    }


# BUG-93 — the replay's clock. Plotly's own ▶ Play steps a frame on the first
# display tick *after* its duration and restarts the next frame's clock from
# there, so every hold rounds up to whole ticks and the rounding accumulates: on
# a 60 Hz screen a 40 ms frame lasts 50 ms, and a 20.8 s reading replayed in 26 s.
# No duration can fix that from here — the tick is the viewer's. So every HTML
# surface (`tabs._true_scale_plot_html`, `tabs._animation_html`,
# `api.save_figure`) embeds a small player that shows whichever frame the wall
# clock has reached, reading the frame times, the speed and VIZ-10's autoplay
# intent off `fig.layout.meta`, where `make_scanpath_animation` stamps them.
_AUTOPLAY_META_FLAG = "scanpath_autoplay"
_REPLAY_META_TIMES = "scanpath_frame_times_ms"
_REPLAY_META_SPEED = "scanpath_playback_speed"

# `{plot_id}` stays literal: plotly.py substitutes it (a plain `str.replace`, so
# the braces need no escaping) and runs the script in a `.then()` after `newPlot`.
_REPLAY_PLAYER_JS = """(function () {
  var gd = document.getElementById('{plot_id}');
  if (!gd) { return; }
  var tries = 0;
  // Frames live on gd._transitionData._frames (gd.frames is undefined) and are
  // attached after newPlot resolves, so wait for them rather than a fixed delay.
  (function init() {
    var meta = gd.layout && gd.layout.meta;
    var td = gd._transitionData;
    if (typeof Plotly === 'undefined' || !gd.on || !meta ||
        !(td && td._frames && td._frames.length)) {
      if (++tries < 200) { setTimeout(init, 50); }
      return;
    }
    run(meta);
  })();

  function run(meta) {
    var times = meta.scanpath_frame_times_ms;
    var speed = meta.scanpath_playback_speed;
    if (!times || !times.length || !(speed > 0)) { return; }
    var last = times.length - 1;
    var jump = {mode: 'immediate', frame: {duration: 0, redraw: false},
                transition: {duration: 0}};
    var shown = 0, raf = null, t0 = 0, resume = false;

    function frameAt(ms) {  // the last frame whose reading time has been reached
      var lo = 0, hi = last;
      while (lo < hi) {
        var mid = (lo + hi + 1) >> 1;
        if (times[mid] <= ms) { lo = mid; } else { hi = mid - 1; }
      }
      return lo;
    }
    function show(k) {
      shown = k;
      Plotly.animate(gd, [String(k)], jump);
    }
    // A late tick skips frames rather than falling behind the clock.
    function tick() {
      if (!gd.isConnected) { raf = null; leave(); return; }
      var k = frameAt((performance.now() - t0) * speed);
      if (k !== shown) { show(k); }
      raf = k < last ? requestAnimationFrame(tick) : null;
    }
    function stop() {
      if (raf !== null) { cancelAnimationFrame(raf); raf = null; }
    }
    function play() {
      if (raf !== null) { return; }  // already playing: keep the clock
      show(shown < last ? shown : 0);  // at the end, Play starts over
      t0 = performance.now() - times[shown] / speed;
      raf = requestAnimationFrame(tick);
    }

    // Whatever put a frame on screen — this clock, the slider, Restart — Play
    // resumes from it.
    gd.on('plotly_animatingframe', function (e) {
      var k = parseInt(e && e.name, 10);
      if (k >= 0 && k <= last) { shown = k; }
    });
    gd.on('plotly_buttonclicked', function (e) {
      if (e && e.button && e.button.name === 'play') { play(); } else { stop(); }
    });
    gd.on('plotly_sliderstart', stop);
    gd.on('plotly_sliderchange', function (e) { if (e && e.interaction) { stop(); } });
    // A background tab gets no ticks; carry on from the same frame on return.
    function onVisibility() {
      if (!gd.isConnected) { stop(); leave(); return; }
      if (document.hidden) { resume = raf !== null; stop(); }
      else if (resume) { resume = false; play(); }
    }
    // A page that swaps content without reloading (the docs site) can drop the
    // plot; let go of the document then, so the plot can be collected.
    function leave() {
      document.removeEventListener('visibilitychange', onVisibility);
    }
    document.addEventListener('visibilitychange', onVisibility);

    // Plotly still draws the ▶ Play button; this clock takes over what it does.
    var edit = {};
    (gd.layout.updatemenus || []).forEach(function (menu, i) {
      (menu.buttons || []).forEach(function (button, j) {
        if (button.name === 'play') {
          edit['updatemenus[' + i + '].buttons[' + j + '].execute'] = false;
        }
      });
    });
    Promise.resolve(Plotly.relayout(gd, edit)).then(function () {
      if (meta.scanpath_autoplay) { play(); }
    });
  }
})();"""


def animation_player_post_script(fig) -> str | None:
    """The replay player for an animated scanpath, or ``None`` if there is none.

    Pass it to ``fig.to_html(post_script=…)`` / ``write_html(post_script=…)``
    (with ``auto_play=False``) for any figure :func:`make_scanpath_animation`
    built — or its ``to_dict()``; ``None`` — for a static figure, or a replay
    with no frames — is what those calls take for "no script" (BUG-93).

    The player keeps the replay on the wall clock: at every display tick it
    shows the last frame whose reading time ``elapsed × playback_speed`` has
    reached, so a replay takes ``reading span / playback_speed`` exactly — a slow
    tick skips frames instead of pushing every later one back — and a background
    tab pauses it. It takes the ▶ Play button over (the button's own command is
    switched off with ``execute: false``, Plotly's hook for exactly this, and the
    click still arrives as ``plotly_buttonclicked``); Pause, Restart and the time
    slider keep their own commands, and any of them stops the clock. VIZ-10's
    autoplay starts it on load, from the first frame.

    It **polls** for Plotly and the figure's frames before starting. Two things
    made a one-shot kick-off silently never fire (VIZ-10), both confirmed
    against a live Plotly build: frames live on ``gd._transitionData._frames``,
    **not** ``gd.frames`` (``undefined``), and the library can arrive late (CDN
    latency, the true-scale iframe mount) and attaches its frames only after
    ``newPlot`` resolves. Polling every 50 ms (capped at ~10 s) covers all of it,
    on the live embed and saved HTML alike.

    Without the script — ``fig.show()``, or a plain ``write_html`` — the figure
    still plays on Plotly's own queue, at the frame duration the ▶ Play button
    carries.
    """
    if isinstance(fig, dict):  # a figure's `to_dict()`
        meta = (fig.get("layout") or {}).get("meta")
    else:
        meta = getattr(fig.layout, "meta", None)
    if not isinstance(meta, dict) or not meta.get(_REPLAY_META_TIMES):
        return None
    return _REPLAY_PLAYER_JS


# PERF-17 — the replay's frames, as its HTML page carries them. Every frame
# restates every animated trace at full length (see `_revealed_xy`), ~33 KB a
# frame however little changed, so a 2,001-frame replay was a 66 MB page. The
# page instead carries frame 0 whole and, for each later frame, only what changed
# since the one before; this decoder rebuilds the exact frame list in the browser
# and hands it to `Plotly.addFrames`, ahead of the player (which already polls for
# the frames). Delta-against-the-previous-frame can't be Plotly's own frames: the
# slider jumps from any frame to any other, so each frame has to be complete.
#
# A delta node is `null` (unchanged), `[0, value]` (replaced), `[1, {key: node},
# [dropped keys]?]` (an object's changed keys), or `[2, [indices], [values]]` (a
# same-length array's changed slots). Unchanged values are shared between frames
# rather than copied: Plotly copies a frame's objects before applying it and
# never writes into a frame. `__SCANPATH_PACKED_FRAMES__` is replaced by the
# JSON; `{plot_id}` stays literal for plotly.py, as in the player.
_PACKED_FRAMES_TOKEN = "__SCANPATH_PACKED_FRAMES__"
_REPLAY_FRAMES_JS = """(function () {
  var gd = document.getElementById('{plot_id}');
  if (!gd || typeof Plotly === 'undefined') { return; }
  var packed = __SCANPATH_PACKED_FRAMES__;
  var own = Object.prototype.hasOwnProperty;
  function patch(prev, node) {
    if (node === null) { return prev; }
    var out, i, k;
    if (node[0] === 0) { return node[1]; }
    if (node[0] === 1) {
      out = {};
      for (k in prev) { if (own.call(prev, k)) { out[k] = prev[k]; } }
      for (k in node[1]) { if (own.call(node[1], k)) { out[k] = patch(prev[k], node[1][k]); } }
      for (i = 0; node[2] && i < node[2].length; i++) { delete out[node[2][i]]; }
      return out;
    }
    out = prev.slice();
    for (i = 0; i < node[1].length; i++) { out[node[1][i]] = node[2][i]; }
    return out;
  }
  var state = {};
  var frames = packed.map(function (f) {
    var frame = {}, k;
    for (k in f) { if (own.call(f, k) && k !== 'p') { frame[k] = f[k]; } }
    if (f.p) {
      frame.data = f.p.map(function (node, i) {
        var slot = f.traces ? f.traces[i] : i;
        state[slot] = patch(state[slot], node);
        return state[slot];
      });
    }
    return frame;
  });
  Plotly.addFrames(gd, frames);
})();"""

_ABSENT = object()


def _same_value(a, b) -> bool:
    """Whether two figure values serialize to the same JSON value.

    Strict where JSON is: ``True`` is not ``1``. Errs towards *different* —
    a value judged different is merely carried again, never lost.
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, np.ndarray):
        if a.dtype != b.dtype or a.shape != b.shape:
            return False
        if a.dtype.hasobject:
            return _same_value(a.tolist(), b.tolist())
        return a.tobytes() == b.tobytes()
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same_value(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False
        try:
            if a != b:  # C speed for the common case: plain numbers and strings
                return False
        except ValueError:  # an ndarray inside: no truth value
            pass
        except TypeError:  # `pd.NA` against anything else: no truth value either
            return False
        kinds = list(map(type, a))
        if kinds != list(map(type, b)):
            return False
        kind_set = set(kinds)
        if any(k in (list, tuple, dict, np.ndarray) for k in kind_set):
            return all(_same_value(x, y) for x, y in zip(a, b))
        # `==` holds -0.0 equal to 0.0, which JSON writes apart. Only an array
        # holding a zero pays for the sign check.
        if any(issubclass(k, float) for k in kind_set) and 0.0 in a:
            return all(
                not isinstance(x, float) or x != 0.0 or _same_sign(x, y)
                for x, y in zip(a, b)
            )
        return True
    try:
        same = bool(a == b)
    except (TypeError, ValueError):
        return False
    return same and (not isinstance(a, float) or a != 0.0 or _same_sign(a, b))


def _same_sign(a: float, b: float) -> bool:
    return math.copysign(1.0, a) == math.copysign(1.0, b)


def _frame_delta(prev, cur):
    """``cur`` as a change to ``prev`` — the delta node `_REPLAY_FRAMES_JS` applies."""
    if isinstance(cur, dict) and isinstance(prev, dict):
        changed = {}
        for key, value in cur.items():
            node = _frame_delta(prev.get(key, _ABSENT), value)
            if node is not None:
                changed[key] = node
        dropped = [key for key in prev if key not in cur]
        if dropped:
            return [1, changed, dropped]
        return [1, changed] if changed else None
    if prev is not _ABSENT and _same_value(prev, cur):
        return None
    if isinstance(cur, list) and isinstance(prev, list) and len(cur) == len(prev):
        slots = [i for i, (a, b) in enumerate(zip(prev, cur)) if not _same_value(a, b)]
        # A patch costs an index per slot; past half the array, restate it.
        if 2 * len(slots) < len(cur):
            return [2, slots, [cur[i] for i in slots]]
    return [0, cur]


def pack_replay_frames(frames: Sequence[Mapping]) -> list[dict]:
    """Delta-encode a replay's frames for `_REPLAY_FRAMES_JS` (PERF-17).

    ``frames`` are the figure's ``to_dict()["frames"]`` (or the same as plain
    JSON values). Each packed frame keeps its own keys (``name``, ``traces``, …)
    and replaces ``data`` with ``p``: one delta node per trace against that
    trace's state in the frame before — the trace index is ``traces[i]``, or
    ``i`` without it. Frame 0 has no frame before it, so it is carried whole.
    Values are carried as they are, so serializing the result the way
    ``to_html`` serializes frames (``to_json_plotly``) writes each exactly as
    the frames would have.
    """
    state: dict = {}
    packed = []
    for frame in frames:
        data = frame.get("data")
        # A frame whose `data` is null keeps it as it was.
        out = {k: v for k, v in frame.items() if k != "data" or data is None}
        if data is not None:
            traces = frame.get("traces")
            nodes = []
            for i, trace in enumerate(data):
                slot = traces[i] if traces is not None else i
                nodes.append(_frame_delta(state.get(slot, _ABSENT), trace))
                state[slot] = trace
            out["p"] = nodes
        packed.append(out)
    return packed


def replay_page(fig) -> tuple[dict, str] | None:
    """A replay as its HTML page carries it: ``(figure dict, post_script)``.

    PERF-17: the dict is the figure without its ``frames``, and the script
    rebuilds them in the browser from :func:`pack_replay_frames`' deltas, then
    runs :func:`animation_player_post_script`'s player — a 2,001-frame replay's
    page falls from 66 MB to under 1 MB. Serialize the dict with
    ``to_html(…, validate=False, post_script=script)``; ``auto_play`` no longer
    matters, since plotly.py sees no frames. ``fig`` may be a figure or its
    ``to_dict()``, which is not modified. ``None`` for a figure with no player (a
    static figure, or a replay with no frames): serialize that one as it is.

    The figure itself keeps its frames: `api.animate_scanpath`, the GIF/MP4
    export and ``fig.show()`` use them as they are.
    """
    player = animation_player_post_script(fig)
    if player is None:
        return None
    if not isinstance(fig, dict) and not fig.frames:
        return None
    fig_dict = fig if isinstance(fig, dict) else fig.to_dict()
    frames = fig_dict.get("frames") or []
    if not frames:
        return None
    if not all(_packable(frame) for frame in frames):
        # Frames this encoding can't address (a typed-array `traces`) travel as
        # plotly.py writes them, still on the player.
        return fig_dict, player
    page = {key: value for key, value in fig_dict.items() if key != "frames"}
    return page, _packed_frames_script(frames) + "\n" + player


def _packable(frame: Mapping) -> bool:
    """Whether `pack_replay_frames` can address ``frame``'s traces by index."""
    data = frame.get("data")
    traces = frame.get("traces")
    if data is not None and not isinstance(data, (list, tuple)):
        return False
    return traces is None or (
        isinstance(traces, (list, tuple))
        and all(isinstance(i, int) and not isinstance(i, bool) for i in traces)
    )


def _packed_frames_script(frames: Sequence[Mapping]) -> str:
    """`_REPLAY_FRAMES_JS` carrying ``frames``, packed (PERF-17)."""
    from plotly.io.json import to_json_plotly

    packed = to_json_plotly(pack_replay_frames(frames))
    # Inside a <script>: no `<` may close it, and plotly.py substitutes
    # `{plot_id}` across the whole script — both only ever occur inside a JSON
    # string, where the escapes decode to the same text.
    packed = packed.replace("<", "\\u003c").replace("{plot_id}", "\\u007bplot_id}")
    return _REPLAY_FRAMES_JS.replace(_PACKED_FRAMES_TOKEN, packed)


def animation_clip_frame_ms(fig) -> float | None:
    """How long a GIF/MP4 of ``fig`` holds each frame to last as long as its replay.

    The replay takes ``reading span / playback_speed`` — its last frame's
    reading time over the speed stamped on ``layout.meta`` — and a clip spreads
    that evenly over the frames (BUG-93). ``None`` for a figure
    :func:`make_scanpath_animation` didn't build."""
    meta = getattr(fig.layout, "meta", None)
    if not isinstance(meta, dict):
        return None
    times = meta.get(_REPLAY_META_TIMES)
    speed = meta.get(_REPLAY_META_SPEED)
    if not times or not speed or speed <= 0:
        return None
    return float(times[-1]) / float(speed) / len(times)


def _replay_clock_meta(frame_times, playback_speed: float, autoplay: bool) -> dict:
    """The replay's ``layout.meta``: the clock the player reads, and autoplay."""
    return {
        _AUTOPLAY_META_FLAG: bool(autoplay and frame_times),
        _REPLAY_META_TIMES: frame_times,
        _REPLAY_META_SPEED: float(playback_speed),
    }


def set_replay_clock(
    fig: go.Figure, frame_step_ms: float, *, playback_speed: float, autoplay: bool
) -> None:
    """Re-time a replay in place: a new playback speed and autoplay, same frames.

    PERF-15: the frames depend on neither (BUG-93), only ▶ Play's own frame
    duration and the clock on ``layout.meta`` do, so the app builds a replay once
    and stamps these onto the copy each cache hit returns. ``frame_step_ms`` is
    the exact grid step :func:`build_scanpath_replay` returned with the figure —
    the rounded frame times on ``layout.meta`` could truncate Play's duration to
    a different whole millisecond. The result is byte-identical to building the
    replay at that speed and autoplay. Only the clock's keys change: anything
    else on ``layout.meta`` (the Illustration label's) stays where it is.
    """
    meta = fig.layout.meta if isinstance(fig.layout.meta, dict) else {}
    times = list(meta.get(_REPLAY_META_TIMES) or [])
    if times:
        fig.layout.updatemenus = _animation_play_buttons(
            _anim_frame_duration_ms(frame_step_ms, playback_speed)
        )
    fig.layout.meta = {**meta, **_replay_clock_meta(times, playback_speed, autoplay)}


def _animation_play_buttons(frame_duration):
    """Play / Pause / Restart buttons.

    Each carries a ``name`` the replay player looks for: on every HTML surface
    :func:`animation_player_post_script` takes ▶ Play over and runs the frames on
    the wall clock (BUG-93), so Play's own ``frame_duration`` drives only a
    figure shown without it (``fig.show()``).

    Frames step with ``redraw=False``: every animated trace is full length with
    not-yet-reached fixations masked to ``None`` (see :func:`_revealed_xy`), so
    advancing a frame only changes point positions — Plotly updates just those
    few traces instead of redrawing the whole figure (the static word boxes +
    labels) every frame. A full redraw of the scanpath figure costs ~50 ms, which
    on a long trial dwarfed the per-frame budget. Transitions are 0 so frames snap
    into place (no tweening), and the constant array length means a new
    fixation/number appears on its mark instead of gliding in from the corner.
    """
    return [
        dict(
            type="buttons",
            showactive=False,
            # A horizontal row above the plot. The scrubber shares this top
            # transport band to keep playback controls together.
            direction="right",
            y=1.0,
            x=0.0,
            xanchor="left",
            yanchor="bottom",
            pad=dict(b=12, l=8),
            buttons=[
                dict(
                    label="▶ Play",
                    name="play",
                    method="animate",
                    args=[
                        None,
                        dict(
                            frame=dict(duration=frame_duration, redraw=False),
                            fromcurrent=True,
                            transition=dict(duration=0),
                        ),
                    ],
                ),
                dict(
                    label="⏸ Pause",
                    name="pause",
                    method="animate",
                    args=[
                        [None],
                        dict(
                            frame=dict(duration=0, redraw=False),
                            mode="immediate",
                            transition=dict(duration=0),
                        ),
                    ],
                ),
                dict(
                    label="⟲ Restart",
                    name="restart",
                    method="animate",
                    args=[
                        ["0"],
                        dict(
                            frame=dict(duration=0, redraw=True),
                            mode="immediate",
                            transition=dict(duration=0),
                        ),
                    ],
                ),
            ],
        )
    ]


def _animation_time_slider(frame_times, total_ms):
    """Linear time-scrubber slider (VIZ-11).

    Frame times sit on a uniform grid, so the handle moves linearly through
    reading time. Each step's label is **"elapsed / total s"** (e.g. "1.2 /
    30.0s"), surfaced in the single ``currentvalue`` readout — meaningful for any
    number of overlaid scanpaths, unlike a fixation index. A long reading would
    render a wall of overlapping numbers if every step drew a tick + label, so the
    per-step tick ruler (``ticklen``/``minorticklen`` = 0) and per-step labels
    (transparent ``font``) are hidden; the readout is the one time display.
    """
    total_s = total_ms / 1000.0
    return [
        dict(
            active=0,
            # Share the top transport band with Play / Pause / Restart.
            yanchor="bottom",
            xanchor="left",
            ticklen=0,
            minorticklen=0,
            # Per-step labels feed the readout but must not pile up under the
            # track, so draw them fully transparent.
            font=dict(color="rgba(0,0,0,0)"),
            currentvalue=dict(
                font=dict(size=14, color="#444"),
                visible=True,
                xanchor="right",
            ),
            transition=dict(duration=0),
            pad=dict(b=12),
            len=0.6,
            x=0.38,
            y=1.0,
            steps=[
                dict(
                    args=[
                        [str(k)],
                        dict(
                            frame=dict(duration=0, redraw=True),
                            mode="immediate",
                            transition=dict(duration=0),
                        ),
                    ],
                    label=f"{frame_times[k] / 1000:.1f} / {total_s:.1f}s",
                    method="animate",
                )
                for k in range(len(frame_times))
            ],
        )
    ]


def _render_scanpath_animation(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    settings: FigureSettings,
    fixations_b: pd.DataFrame | None = None,
    words_b: pd.DataFrame | None = None,
) -> tuple[go.Figure, float]:
    """Frame-by-frame scanpath replay on a real reading-time clock.

    Returns the figure and the exact grid step its frames sit on, which
    :func:`set_replay_clock` needs to re-time it (PERF-15).

    Pass ``fixations_b`` (and optionally ``words_b``) to overlay a SECOND
    scanpath animated on the same clock. Every scanpath is rebased to its first
    fixation's ``timestamp_ms``, so they share *real reading time* including the
    saccade/blink gaps between fixations; a frame is emitted at every fixation
    onset across all scanpaths, and the shorter reading finishes first and holds
    while the longer keeps going. The wall-clock player every HTML surface embeds
    (:func:`animation_player_post_script`) shows each frame once its reading time
    over ``playback_speed`` has elapsed, so the whole replay takes
    ``reading_span / playback_speed`` — exactly what
    :func:`animation_playback_ms` reports (and the side panel quotes).

    With two scanpaths each trail wears its own style — ``style_a`` /
    ``style_b``, resolved exactly as :func:`make_comparison_figure` resolves
    them (colour, size range, opacity, hollow markers and the saccade line's
    colour, dash and width; the comparison palette where a style names none) —
    order numbers are tinted per-scanpath, and an optional A/B legend
    (``show_legend``) names them; word boxes/labels come from
    ``words`` (scanpath A), so the overlay is meaningful for two readings of the
    same text. With one scanpath the behaviour matches the classic single replay
    (order numbers honour ``order_font_color``, no legend).

    The single replay honours the same fixation-colouring options as
    :func:`make_scanpath_figure`: ``color_by`` (numeric → ``fixation_colorscale``
    pinned to the whole trial's range so colours stay stable as the trail grows,
    categorical → discrete palette + legend), ``color_by_line``, and an optional
    colorbar (styled by the ``fixation_colorbar_*`` settings, like the static
    figure). The dual overlay
    colours as :func:`make_comparison_figure` does: the metric (on one range
    shared by both readings) or one shared category→colour mapping fills the
    markers, and each reading's flat A/B colour becomes its marker outline.

    VIZ-23 brought the remaining word-label, arrow and flag options across from
    the static figure, each defaulting to the replay's previous behaviour:

    - the word labels take ``text_color`` / ``highlight_column`` /
      ``highlight_text_color`` / ``word_hover_measure`` (``highlight_column`` is
      the *text*-marking channel — there is no border-overlay style here);
    - ``show_saccade_arrows`` adds the direction arrowheads, each revealed with
      the saccade it belongs to rather than all at frame zero;
    - ``fixation_flags`` applies the PRE-2 short/long/out-of-bounds
      classification: *Discard* drops those fixations from the replay entirely,
      *Highlight* overlays them in their flag marker as the replay reaches them.

    ``layout.meta`` carries the replay's clock (each frame's reading time and the
    speed) and, with ``autoplay`` (default on, VIZ-10), the intent to start on
    load *at the configured playback speed*; the player reads both. The figure
    itself is always built paused — autoplay is the embedder's to start.
    """
    canvas_width = settings.canvas_width
    canvas_height = settings.canvas_height
    base_font_size = settings.base_font_size
    font_family = settings.font_family
    playback_speed = settings.playback_speed
    show_words = settings.show_words
    show_word_labels = settings.show_word_labels
    show_saccades = settings.show_saccades
    show_saccade_arrows = settings.show_saccade_arrows
    show_order = settings.show_order
    marker_size_range = settings.marker_size_range
    order_font_size = settings.order_font_size
    order_font_color = settings.order_font_color
    color_by = settings.color_by
    # BUG-85: as in `make_scanpath_figure` — "line" is colour-by-line.
    color_by_line = settings.color_by_line or color_by == "line"
    fixation_colorscale = settings.fixation_colorscale
    fixation_color_range = settings.fixation_color_range
    fixation_flags = settings.fixation_flags
    fixation_flags_b = settings.fixation_flags_b
    # The replay has no heatmap: its one bar is the fixations'.
    show_colorbars = settings.show_fixation_colorbar
    colorbar_orientation = settings.fixation_colorbar_orientation
    colorbar_tickangle = settings.fixation_colorbar_tickangle
    colorbar_tickfont_size = settings.fixation_colorbar_tickfont_size
    saccade_color = settings.saccade_color
    saccade_style = settings.saccade_style
    saccade_width = settings.saccade_width
    hollow_fixations = settings.hollow_fixations
    fixation_opacity = settings.fixation_opacity
    fixation_color = settings.fixation_color
    fixation_symbol = settings.fixation_symbol
    text_color = settings.text_color
    highlight_column = settings.highlight_column
    highlight_text_color = settings.highlight_text_color
    word_hover_measure = settings.word_hover_measure
    word_hover_fields = settings.word_hover_fields
    fixation_hover_fields = settings.fixation_hover_fields
    background_color = settings.background_color
    # Drawn as written: a label is a name, not Plotly markup (round 9).
    label_a = _plotly_literal(settings.label_a)
    label_b = _plotly_literal(settings.label_b)
    show_legend = settings.show_legend
    line_spacing = settings.line_spacing
    scale_text_to_boxes = settings.scale_text_to_boxes
    background_image = settings.background_image
    background_image_size = settings.background_image_size
    background_image_origin = settings.background_image_origin
    background_image_opacity = settings.background_image_opacity
    fit_to_monitor = settings.fit_to_monitor
    show_coordinate_grid = settings.show_coordinate_grid
    coordinate_grid_spacing = settings.coordinate_grid_spacing
    autoplay = settings.autoplay
    anim_grid_step_ms = settings.anim_grid_step_ms
    anim_max_frames = settings.anim_max_frames
    fig = go.Figure()
    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)

    word_frames = [w for w in (words, words_b) if w is not None and not w.empty]
    x_range, y_range, *_ = _compute_axis_ranges(
        canvas_width,
        canvas_height,
        (fixations, "x", "y"),
        (fixations_b, "x", "y"),
        word_frames=word_frames,
        fit_to_monitor=fit_to_monitor,
    )

    # Fix the display size first so word labels are sized in the data->screen
    # scale (true-to-scale text); the same fitted_w/fitted_h drive the layout.
    fitted_w, fitted_h = _fit_display_size(
        canvas_width, canvas_height, x_range, y_range, spatial_axes=True
    )
    scale = _display_scale(x_range, y_range, fitted_w, fitted_h)
    label_font_px = _word_label_font_px(
        words,
        scale=scale,
        line_spacing=line_spacing,
        manual_font_px=base_font_size,
        scale_text_to_boxes=scale_text_to_boxes,
    )

    # CMP-11: which reading's stimulus the replay draws. The replay has only ever
    # had ONE stimulus layer, so "both" keeps meaning A's here rather than
    # stacking a second identical set of rectangles onto every existing
    # same-dataset co-animation. "b" is the one that matters: a cross-dataset
    # co-animation would otherwise run B's trace over A's text.
    stimulus_words = words
    if (
        _compare_stimulus_sides(settings.compare_stimulus) == (False, True)
        and words_b is not None
        and not words_b.empty
    ):
        stimulus_words = words_b
    shapes = (
        build_word_boxes(
            stimulus_words,
            color=settings.word_box_color,
            fill_color=settings.word_box_fill_color,
            fill_opacity=settings.word_box_fill_opacity,
            line_opacity=settings.word_box_line_opacity,
        )
        if show_words and not stimulus_words.empty
        else []
    )
    if show_word_labels and not stimulus_words.empty:
        _add_word_label_trace(
            fig,
            stimulus_words,
            label_font_px,
            font_settings["family"],
            highlight_column=highlight_column,
            text_color=text_color,
            highlight_text_color=highlight_text_color,
            word_hover_measure=word_hover_measure,
            word_hover_fields=word_hover_fields,
        )

    # PRE-2 fixation flags (VIZ-23), mirroring the static figure: *Discard* drops
    # the flagged rows before the specs are built, so they vanish from the trail,
    # the saccade polyline, the index labels and the marker-size scaling. Applied
    # AFTER the axis ranges above, exactly as in `make_scanpath_figure` — the view
    # is framed on the trial as recorded, not on what survives the filter.
    flags = fixation_flags or {}
    # B is flagged against its own word boxes when it brought them, else against
    # A's (the overlay draws A's boxes, and two readings of one text share them).
    entry_words = [
        words,
        words_b if (words_b is not None and not words_b.empty) else words,
    ]
    # CMP-24: B carries its own flags when it was given any — as
    # `fixation_flags_b`, or (the comparison's spelling) on its `style_b`.
    if fixation_flags_b is None and isinstance(settings.style_b, dict):
        fixation_flags_b = settings.style_b.get("fixation_flags")
    flags_b = flags if fixation_flags_b is None else (fixation_flags_b or {})
    entry_flags = [flags, flags_b]
    if flags:
        fixations = _discard_flagged_fixations(fixations, entry_words[0], flags)
    if flags_b and fixations_b is not None:
        fixations_b = _discard_flagged_fixations(fixations_b, entry_words[1], flags_b)

    # The co-animation draws each scanpath in its own style, exactly as the
    # static comparison resolves it (`_comparison_scanpath_style`: the rail's
    # per-scanpath colour, size range, opacity, hollow and saccade line). A lone
    # scanpath keeps the figure-wide settings below.
    dual_input = all(f is not None and not f.empty for f in (fixations, fixations_b))
    styles = [
        _comparison_scanpath_style(
            idx, style, default_marker_size_range=marker_size_range
        )
        for idx, style in enumerate((settings.style_a, settings.style_b))
    ]
    entries = [
        (frame, style["fix_color"], label)
        for frame, style, label in zip(
            (fixations, fixations_b), styles, (label_a, label_b)
        )
    ]
    specs = _scanpath_anim_specs(
        entries,
        marker_size_range,
        size_ranges=[
            style["marker_size_range"] if dual_input else marker_size_range
            for style in styles
        ],
        **_settings_size_scale(settings),
    )
    # The words frame each surviving scanpath is flagged against (the highlight
    # overlay's out-of-bounds test). `_scanpath_anim_specs` skips empty
    # scanpaths, so apply the same skip rule here to stay aligned with `specs`.
    surviving = [
        (w, f, style)
        for (fix_df, _color, _label), w, f, style in zip(
            entries, entry_words, entry_flags, styles
        )
        if fix_df is not None and not fix_df.empty
    ]
    for spec, (spec_words, spec_flags, spec_style) in zip(specs, surviving):
        spec["words"] = spec_words
        spec["flags"] = spec_flags
        spec["style"] = spec_style
    dual = len(specs) > 1
    if not dual and specs:
        # A lone scanpath always wears the canonical single-replay colour,
        # whether it arrived as `fixations` or (degenerately) only as
        # `fixations_b`, so the trail never silently renders in the B colour.
        # VIZ-17/18: honour the caller's uniform fixation colour when one is
        # given, so the replay matches the static figure (and the palette).
        specs[0]["color"] = fixation_color or COMPARISON_PALETTE[0]

    # Metric colouring, mirroring the static figure's fixation trace (the dual
    # overlay's, mirroring the comparison figure's, comes first). Numeric
    # metrics map through
    # `fixation_colorscale` with cmin/cmax pinned to the WHOLE trial (or the
    # caller's range) up front — otherwise the scale would renormalise to the
    # partial trail on every frame and colours would drift during playback.
    for s in specs:
        s["marker_colors"] = None
        s["marker_extra"] = {}
        s["marker_line"] = None
    category_legend: list = []
    color_label = color_by or ""
    # VIZ-17: the uniform sentinel means "no variable mapped to hue" — leave the
    # trail on its flat colour rather than looking for a column by that name.
    if color_by == UNIFORM_COLOR_FIELD:
        color_by, color_label = None, ""
    if dual and (color_by or color_by_line):
        # The co-animation colours as the static comparison does: the metric
        # (one shared range) or the shared category colours fill each marker,
        # and each scanpath's own colour becomes its outline — the A/B cue.
        labels = [
            _fixation_category_labels(s["ordered"], s["words"], color_by, color_by_line)
            for s in specs
        ]
        colors, category_legend = _shared_category_colors(
            labels, avoid=[s["color"] for s in specs]
        )
        if category_legend:
            color_label = "line" if (color_by_line or color_by == "line") else color_by
            for s, spec_colors in zip(specs, colors):
                if spec_colors is not None:
                    s["marker_colors"] = spec_colors
                    s["marker_line"] = dict(color=s["color"], width=1.4)
        elif color_by and all(
            color_by in s["ordered"].columns
            and pd.api.types.is_numeric_dtype(s["ordered"][color_by])
            for s in specs
        ):
            values = pd.concat([s["ordered"][color_by] for s in specs])
            if values.notna().any():
                rng = fixation_color_range or (
                    float(values.min()),
                    float(values.max()),
                )
                for i, s in enumerate(specs):
                    # One bar, on A's trail — the scale is shared.
                    bar = show_colorbars and i == 0
                    s["marker_colors"] = list(s["ordered"][color_by])
                    s["marker_line"] = dict(color=s["color"], width=1.4)
                    s["marker_extra"] = dict(
                        colorscale=fixation_colorscale,
                        cmin=rng[0],
                        cmax=rng[1],
                        showscale=bar,
                        colorbar=_colorbar_dict(
                            _column_title(color_label),
                            orientation=colorbar_orientation,
                            tickangle=colorbar_tickangle,
                            tickfont_size=colorbar_tickfont_size,
                        )
                        if bar
                        else None,
                    )
    if not dual and specs and (color_by or color_by_line):
        ordered0 = specs[0]["ordered"]
        if color_by_line and not words.empty:
            from .measures import assign_fixation_lines

            line_ids = assign_fixation_lines(ordered0, words)
            color_data = line_ids.map(
                lambda v: f"Line {int(v) + 1}" if pd.notna(v) else "(off-text)"
            )
            color_label = "line"
            is_numeric_color = False
        else:
            color_data = ordered0[color_by] if color_by in ordered0.columns else None
            is_numeric_color = color_data is not None and pd.api.types.is_numeric_dtype(
                color_data
            )
        if color_data is not None:
            marker_color, category_legend = _resolve_marker_colors(
                color_data, is_numeric_color
            )
            specs[0]["marker_colors"] = list(marker_color)
            if is_numeric_color:
                rng = fixation_color_range or (
                    float(color_data.min()),
                    float(color_data.max()),
                )
                # VIZ-23: the same styled colorbar the static figure builds, so
                # orientation / tick angle / tick size apply here too.
                colorbar = None
                if show_colorbars:
                    colorbar = _colorbar_dict(
                        _column_title(color_label),
                        orientation=colorbar_orientation,
                        tickangle=colorbar_tickangle,
                        tickfont_size=colorbar_tickfont_size,
                    )
                specs[0]["marker_extra"] = dict(
                    colorscale=fixation_colorscale,
                    cmin=rng[0],
                    cmax=rng[1],
                    showscale=show_colorbars,
                    colorbar=colorbar,
                )

    def _trail_marker(s):
        """Marker dict for a (full-length) trail trace.

        Every animated trace is full length with not-yet-reached fixations masked
        to ``None`` positions (see :func:`_revealed_xy`), so the size/colour
        arrays are stated once at full length and never change frame to frame —
        only which positions are revealed does. Restating the whole marker keeps
        the colorscale/cmin/cmax/colorbar attached to the trail."""
        colors = s["marker_colors"]
        marker = dict(
            size=list(s["sizes"]),
            # A glyph shape (♥) has no Plotly symbol: `_trail_traces` draws this
            # dict as text instead, so the symbol here only needs to be valid.
            symbol=_marker_symbol(fixation_symbol),
            color=colors if colors is not None else s["color"],
            line=s["marker_line"] or dict(color=FIX_MARKER_OUTLINE, width=0.5),
            **s["marker_extra"],
        )
        # Always set the alpha (even 1.0) so the control overrides Plotly's ~0.7
        # default for variable-size scatter markers (VIZ-6).
        marker["opacity"] = float(s["opacity"] if s["opacity"] is not None else 1.0)
        if s["hollow"]:
            marker = _make_hollow(marker)
        return marker

    glyph = FIXATION_GLYPH_SYMBOLS.get(fixation_symbol or "")

    def _trail_style(s) -> tuple[dict, list[dict] | None]:
        """The trail's marker dict and, for a glyph shape, its text layers —
        stated once per scanpath and reused by every frame, which only moves
        positions. Building them per frame re-sampled the colorscale (glyph and
        hollow markers) for every fixation on each of ~360 frames."""
        if "trail_style" not in s:
            marker = _trail_marker(s)
            layers = _glyph_layers(marker, glyph, s["n_total"]) if glyph else None
            s["trail_style"] = (marker, layers)
        return s["trail_style"]

    def _trail_traces(s, x, y, *, make: Callable = go.Scatter, **top) -> list:
        """The trail as drawn at positions ``x``/``y`` — one marker trace, or
        for a glyph shape (♥) its text layers (`_glyph_scatter_traces`), which
        un-mask exactly like the markers do. Full length either way, so the
        frames still only move positions. ``make=dict`` for a frame."""
        marker, layers = _trail_style(s)
        if layers is not None:
            return _glyph_layer_traces(
                x, y, layers, make=make, customdata=s["customdata"], **top
            )
        return [
            make(
                x=x,
                y=y,
                mode="markers",
                marker=marker,
                text=s["order_text"],
                customdata=s["customdata"],
                **top,
            )
        ]

    # Base traces, with stable indices the frames update by position. Each
    # animated trace is built at FULL length (one slot per fixation); the replay
    # reveals a fixation by un-masking its x/y, never by growing the array or
    # rewriting `text`. Constant length + position-only changes are what let the
    # Play button animate with `redraw=False` (see `_animation_play_buttons`):
    # Plotly then re-renders only these few traces per frame instead of redrawing
    # the static word boxes + labels every time — the redraw cost that made a
    # long replay run far slower than its quoted time. It also keeps the trail's
    # fixation number in `text` (hover only); the visible order numbers live in a
    # separate text trace (below).
    # Scanpath legend entries of their own (dual + legend only): see the trail.
    own_entries = bool(category_legend) or bool(glyph)
    for s in specs:
        ordered = s["ordered"]
        n_total = len(ordered)
        all_x = ordered["x"].tolist()
        all_y = ordered["y"].tolist()
        s["all_x"] = all_x
        s["all_y"] = all_y
        s["n_total"] = n_total
        hover_fields = (
            ["order_in_trial", "duration_ms"]
            if fixation_hover_fields is None
            else list(fixation_hover_fields)
        )
        s["customdata"], s["hovertemplate"] = _hover_payload(ordered, hover_fields)
        # The trial's own fixation numbers, as the static figure and the hover
        # show them — never a 1..n renumbering of what survived the filters.
        s["order_text"] = _fixation_order_labels(ordered)
        s["text_color"] = s["color"] if dual else order_font_color
        # The co-animation draws each scanpath's saccades, opacity and hollow
        # markers from its own style, as the static comparison does; a lone
        # replay keeps the figure-wide settings.
        style = s["style"]
        s["sac_color"] = style["saccade_color"] if dual else saccade_color
        s["sac_width"] = style["saccade_width"] if dual else saccade_width
        s["sac_dash"] = style["saccade_style"] if dual else saccade_style
        s["opacity"] = style["opacity"] if dual else fixation_opacity
        s["hollow"] = bool(style["hollow"]) if dual else hollow_fixations
        s["curr_outline"] = s["color"] if dual else CURRENT_FIX_OUTLINE
        s["curr_outline_w"] = 2.5 if dual else 2

        base_x, base_y = _revealed_xy(all_x, all_y, 1)
        trail = _trail_traces(
            s,
            base_x,
            base_y,
            # A/B legend on the dual overlay only — off by default, honours the
            # compare-legend toggle (CMP-2). The single-replay colour-by legend
            # below is separate and unaffected. Under shared category colours
            # the swatch would show a category, and a glyph has no swatch, so a
            # separate entry (below) names the scanpath instead.
            showlegend=dual and show_legend and not own_entries,
            name=s["label"],
            legendgroup=s["label"],
            hovertemplate=(s["label"] + "<br>" if dual else "") + s["hovertemplate"],
        )
        s["idx_trails"] = list(range(len(fig.data), len(fig.data) + len(trail)))
        for trace in trail:
            fig.add_trace(trace)
        # Order numbers: a text trace holding EVERY fixation's final position,
        # with not-yet-reached fixations masked to None x/y (so nothing is drawn
        # there). A number snaps on at its fixation when that position un-masks —
        # no gliding in from the (0,0) corner — and because the `text` strings
        # never change frame to frame, `redraw=False` renders the reveal purely
        # from the position change.
        if show_order:
            s["idx_order"] = len(fig.data)
            fig.add_trace(
                go.Scatter(
                    x=base_x,
                    y=base_y,
                    mode="text",
                    text=s["order_text"],
                    textfont=dict(
                        color=s["text_color"],
                        size=order_font_size,
                        family=font_settings["family"],
                    ),
                    textposition="top center",
                    showlegend=False,
                    legendgroup=s["label"],
                    hoverinfo="skip",
                )
            )
        else:
            s["idx_order"] = None
        if show_saccades:
            sac_x, sac_y = _revealed_saccade_xy(all_x, all_y, 1)
            s["idx_sac"] = len(fig.data)
            fig.add_trace(
                go.Scatter(
                    x=sac_x,
                    y=sac_y,
                    mode="lines",
                    line=dict(
                        color=s["sac_color"], width=s["sac_width"], dash=s["sac_dash"]
                    ),
                    showlegend=False,
                    legendgroup=s["label"],
                    hoverinfo="skip",
                )
            )
        else:
            s["idx_sac"] = None
        # Saccade direction arrowheads (VIZ-23). Same marker as the static
        # figure's, but each arrow is revealed with its own saccade (its position
        # un-masks when `_revealed_saccade_xy` draws that segment) rather than the
        # whole set standing there from frame zero. Angles are stated once at full
        # length and never change, so `redraw=False` still applies.
        arrow_x, arrow_y, arrow_angle, arrow_seg = (
            _saccade_arrow_rows(ordered, "x", "y")
            if (show_saccades and show_saccade_arrows)
            else ([], [], [], [])
        )
        s["arrow_x"], s["arrow_y"], s["arrow_seg"] = arrow_x, arrow_y, arrow_seg
        s["idx_arrow"] = None
        if arrow_x:
            ax0, ay0 = _revealed_arrow_xy(arrow_x, arrow_y, arrow_seg, 1)
            s["idx_arrow"] = len(fig.data)
            fig.add_trace(
                go.Scatter(
                    x=ax0,
                    y=ay0,
                    mode="markers",
                    marker=dict(
                        symbol="arrow",
                        size=12,
                        angle=arrow_angle,
                        angleref="up",
                        color=s["sac_color"],
                        line=dict(width=0),
                    ),
                    showlegend=False,
                    legendgroup=s["label"],
                    hoverinfo="skip",
                    name="saccade direction",
                )
            )
        s["idx_curr"] = len(fig.data)
        fig.add_trace(
            go.Scatter(
                x=[all_x[0]],
                y=[all_y[0]],
                mode="markers",
                marker=dict(
                    size=[float(s["sizes"][0]) + 8],
                    color=CURRENT_FIX_COLOR,
                    line=dict(color=s["curr_outline"], width=s["curr_outline_w"]),
                ),
                showlegend=False,
                legendgroup=s["label"],
                hoverinfo="skip",
            )
        )
        # PRE-2 *Highlight* overlays (VIZ-23): one trace per flagged category, in
        # that category's marker + colour, drawn over the trail. Full-length like
        # every animated trace — fixations that aren't flagged are masked out
        # permanently, the rest un-mask as the replay reaches them.
        s["flag_overlays"] = []
        s_flags = s.get("flags", flags)
        if s_flags:
            overlay_masks = _fixation_flag_masks(ordered, s["words"], s_flags)
            for category in _FIX_FLAG_CATEGORIES:
                spec_flags = s_flags.get(category, {})
                if spec_flags.get("mode") != "Highlight":
                    continue
                hit = overlay_masks[category].to_numpy()
                if not hit.any():
                    continue
                hx = [all_x[j] if hit[j] else None for j in range(n_total)]
                hy = [all_y[j] if hit[j] else None for j in range(n_total)]
                label = _FIX_FLAG_LABELS[category]
                name = f"{s['label']} · {label}" if dual else label
                fx0, fy0 = _revealed_xy(hx, hy, 1)
                s["flag_overlays"].append(
                    dict(
                        idx=len(fig.data),
                        x=hx,
                        y=hy,
                        marker=dict(
                            symbol=spec_flags.get("symbol") or "x",
                            size=13,
                            color=spec_flags.get("color") or OUT_OF_TEXT_COLOR,
                            line=dict(color="#ffffff", width=1),
                        ),
                        name=name,
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=fx0,
                        y=fy0,
                        mode="markers",
                        marker=s["flag_overlays"][-1]["marker"],
                        name=name,
                        legendgroup=s["label"],
                        showlegend=True,
                        hovertemplate=(
                            f"{label} fixation<br>x %{{x:.0f}}, y %{{y:.0f}}"
                            "<extra></extra>"
                        ),
                    )
                )

    # Categorical colour legend, as in the static figure. These dummy traces sit
    # AFTER the per-scanpath traces so the frame indices recorded above stay
    # valid; frames never touch them.
    if dual and show_legend and own_entries:
        for s in specs:
            coloured = s["marker_line"] is not None
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker=dict(
                        size=10,
                        symbol=_marker_symbol(fixation_symbol),
                        color="#ffffff" if coloured else s["color"],
                        line=dict(
                            color=s["color"] if coloured else FIX_MARKER_OUTLINE,
                            width=2 if coloured else 0.5,
                        ),
                    ),
                    name=s["label"],
                    legendgroup=s["label"],
                    showlegend=True,
                    hoverinfo="skip",
                )
            )
    _add_category_legend(fig, category_legend, color_label)
    if glyph and specs:
        # A glyph carries no colorscale, so A's numeric colour bar rides on a
        # trace of its own (after the animated ones, like the legend entries).
        bar = _glyph_colorbar_trace(
            _trail_style(specs[0])[0], specs[0]["marker_colors"] or ()
        )
        if bar is not None:
            fig.add_trace(bar)

    frame_times, frame_step_ms, reading_span_ms = _anim_timeline(
        specs,
        grid_step_ms=anim_grid_step_ms,
        max_frames=anim_max_frames,
    )

    # Frames are plain dicts, validated once, by the `fig.frames` assignment
    # below. Built from `go.Scatter`/`go.Frame` they were validated (and deep-
    # copied) three times over — each trace, each frame, then the figure —
    # which on a long replay is most of the build: every frame restates the
    # trail's full-length sizes and colours (see `_trail_marker`).
    frames = []
    n_frames = len(frame_times)
    for k, t in enumerate(frame_times):
        # UX-169: the card's "120 of 361 frames" — and a cancel checkpoint, so an
        # abandoned build stops within a frame. A no-op outside a card.
        progress.report(k + 1, n_frames, unit="frames")
        traces_in_frame = []
        traces_idx_in_frame = []
        for s in specs:
            all_x = s["all_x"]
            all_y = s["all_y"]
            # Fixations whose recorded onset has been reached by time t.
            kk = max(int(np.searchsorted(s["onsets"], t, side="right")), 1)

            # Trail: full-length, fixations past kk masked to None. The marker
            # (sizes/colours) and `text` are full-length and identical every
            # frame, so only positions change — `redraw=False` then re-renders
            # just this trace, not the whole figure.
            tx, ty = _revealed_xy(all_x, all_y, kk)
            for idx, trace in zip(s["idx_trails"], _trail_traces(s, tx, ty, make=dict)):
                traces_in_frame.append(trace)
                traces_idx_in_frame.append(idx)

            if show_order:
                # Same full-length positions/text as the base order trace; the
                # reveal is purely the un-masking of x/y for reached fixations,
                # so numbers appear in place (and `redraw=False` shows them).
                ox, oy = _revealed_xy(all_x, all_y, kk)
                traces_in_frame.append(
                    dict(
                        x=ox,
                        y=oy,
                        mode="text",
                        text=s["order_text"],
                        textfont=dict(
                            color=s["text_color"],
                            size=order_font_size,
                            family=font_settings["family"],
                        ),
                        textposition="top center",
                    )
                )
                traces_idx_in_frame.append(s["idx_order"])

            if show_saccades:
                sac_x, sac_y = _revealed_saccade_xy(all_x, all_y, kk)
                traces_in_frame.append(
                    dict(
                        x=sac_x,
                        y=sac_y,
                        mode="lines",
                        line=dict(
                            color=s["sac_color"],
                            width=s["sac_width"],
                            dash=s["sac_dash"],
                        ),
                    )
                )
                traces_idx_in_frame.append(s["idx_sac"])

            if s["idx_arrow"] is not None:
                # Arrowheads reveal with the saccades above: same constant-length
                # array, only the mask moves (angles are set on the base trace).
                arw_x, arw_y = _revealed_arrow_xy(
                    s["arrow_x"], s["arrow_y"], s["arrow_seg"], kk
                )
                traces_in_frame.append(dict(x=arw_x, y=arw_y, mode="markers"))
                traces_idx_in_frame.append(s["idx_arrow"])

            ci = kk - 1
            traces_in_frame.append(
                dict(
                    x=[all_x[ci]],
                    y=[all_y[ci]],
                    mode="markers",
                    marker=dict(
                        size=[float(s["sizes"][ci]) + 8],
                        color=CURRENT_FIX_COLOR,
                        line=dict(color=s["curr_outline"], width=s["curr_outline_w"]),
                    ),
                )
            )
            traces_idx_in_frame.append(s["idx_curr"])

            for overlay in s["flag_overlays"]:
                # A flagged fixation's highlight appears with the fixation itself.
                ox_f, oy_f = _revealed_xy(overlay["x"], overlay["y"], kk)
                traces_in_frame.append(
                    dict(x=ox_f, y=oy_f, mode="markers", marker=overlay["marker"])
                )
                traces_idx_in_frame.append(overlay["idx"])

        frames.append(
            dict(data=traces_in_frame, name=str(k), traces=traces_idx_in_frame)
        )
    fig.frames = frames

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

    sliders = (
        _animation_time_slider(frame_times, reading_span_ms) if frame_times else []
    )
    updatemenus = (
        _animation_play_buttons(_anim_frame_duration_ms(frame_step_ms, playback_speed))
        if frame_times
        else []
    )

    # fitted_w / fitted_h were computed up front (so the label scale matched).
    # ALL transport controls (play/pause/restart buttons + the time slider with
    # its elapsed-time readout) sit ABOVE the plot in the top margin. Critically,
    # the figure is made tall enough that the plot region stays >= fitted_h after
    # Plotly's automargin reserves space for those controls — otherwise the
    # equal-aspect (`scaleanchor`) plot would shrink to fit the leftover height,
    # making the word boxes smaller than the true-to-scale label font computed
    # for fitted_h (text-too-large bug). _CONTROLS_MARGIN_PX is that reserve.
    # A single-replay numeric colorbar gets the same treatment on the right
    # (the dual-overlay legend overlays the plot, so it needs no reserve).
    # A HORIZONTAL colorbar (VIZ-23) stays below the plot, so it takes bottom
    # reserve rather than right — the same trade `_decoration_margins` makes for
    # the static figure.
    anim_colorbar = bool(specs and specs[0].get("marker_extra", {}).get("showscale"))
    horizontal_colorbar = anim_colorbar and colorbar_orientation == "Horizontal"
    right_reserve = (
        _COLORBAR_RESERVE_PX if (anim_colorbar and not horizontal_colorbar) else 0
    )
    top_reserve = _CONTROLS_MARGIN_PX
    bottom_reserve = _COLORBAR_BOTTOM_PX if horizontal_colorbar else 0
    grid_left = _GRID_LEFT_RESERVE_PX if show_coordinate_grid else 0
    grid_bottom = _GRID_BOTTOM_RESERVE_PX if show_coordinate_grid else 0
    # Stimulus-page background image (MultiplEYE) — same layout image as
    # make_scanpath_figure: placed at its (centered) origin, UNDER every trace,
    # and persisting across frames (a layout image, not per-frame data). Lets the
    # animated replay show the rendered page exactly like the static plot.
    bg_spec = _background_image_spec(
        background_image,
        background_image_size,
        background_image_origin,
        background_image_opacity,
    )
    bg_images = [bg_spec] if bg_spec else []
    xaxis = dict(
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        title=None,
        range=x_range,
        constrain="domain",
        automargin=False,
    )
    yaxis = dict(
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        title=None,
        range=y_range,
        constrain="domain",
        scaleanchor="x",
        scaleratio=1,
        automargin=False,
    )
    _apply_coordinate_grid_axes(
        xaxis,
        yaxis,
        show=show_coordinate_grid,
        spacing=coordinate_grid_spacing,
        x_range=x_range,
        y_range=y_range,
        rendered_width=fitted_w,
        rendered_height=fitted_h,
    )
    layout = dict(
        height=(
            fitted_h + top_reserve + bottom_reserve + grid_bottom + _CONTROLS_SAFETY_PX
        ),
        width=fitted_w + grid_left + right_reserve,
        autosize=False,
        images=bg_images,
        margin=dict(
            l=grid_left,
            r=right_reserve,
            t=top_reserve,
            b=bottom_reserve + grid_bottom,
        ),
        xaxis=xaxis,
        yaxis=yaxis,
        template="plotly_white",
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        font=font_settings,
        shapes=shapes,
        sliders=sliders,
        updatemenus=updatemenus,
    )
    # The PRE-2 highlight overlays carry legend entries too, so they get the same
    # floating key as the A/B and colour-category legends.
    flag_legend = any(s.get("flag_overlays") for s in specs)
    if dual or category_legend or flag_legend:
        layout["legend"] = dict(
            orientation="h",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="#cccccc",
            borderwidth=1,
        )
        if dual:
            layout["legend"]["font"] = _compare_legend_font(base_font_size, font_family)
    fig.update_layout(**layout)
    # BUG-93: the replay's clock — each frame's reading time and the speed — for
    # the wall-clock player every HTML surface embeds, plus VIZ-10's autoplay
    # intent, which that player reads on load (Plotly's own `auto_play` ignores
    # the frame duration). No frames → no times, so no player and no autoplay.
    fig.layout.meta = _replay_clock_meta(
        [round(float(t), 3) for t in frame_times], playback_speed, autoplay
    )
    return fig, frame_step_ms


def _resolve_trial_display_name(
    participant: str,
    trial_id: str,
    trial_words: pd.DataFrame,
    trial_labels: tuple[str, str] | None,
    idx: int,
) -> str:
    """Scanpath ``idx``'s name as written; the builders make it literal
    (:func:`_plotly_literal`) where they draw it."""
    if trial_labels is not None and len(trial_labels) > idx:
        return trial_labels[idx]
    text_id = None
    if "text_id" in trial_words.columns and not trial_words.empty:
        text_id = trial_words["text_id"].iloc[0]
    text_str = str(text_id) if text_id is not None else ""
    trial_str = str(trial_id)
    contains_text = text_str and text_str.lower() in trial_str.lower()
    if text_str:
        return (
            f"{text_str} · {participant}"
            if contains_text
            else f"{text_str} · {participant} (trial {trial_str})"
        )
    return f"{trial_str} · {participant}"


def _comparison_scanpath_style(
    idx: int,
    override: dict | None = None,
    *,
    default_marker_size_range: tuple[int, int] = DEFAULT_MARKER_SIZE_RANGE,
) -> dict:
    """Resolve the per-scanpath style for a comparison trace.

    Defaults reproduce the classic two-flat-colour look (``COMPARISON_PALETTE``);
    ``override`` (from the rail's per-scanpath styling panel) wins per key.
    """
    base = {
        "fix_color": compare_palette_color(idx),
        "saccade_color": compare_palette_color(idx),
        "saccade_style": "solid",
        "saccade_width": DEFAULT_SACCADE_WIDTH,
        "marker_size_range": default_marker_size_range,
        "hollow": False,
        "opacity": COMPARE_FIXATION_OPACITY,
    }
    if override:
        # Drop falsy values (None / "") so a blank colour can't override the
        # palette default and reach Plotly as a dark/None marker colour. The
        # per-scanpath filters (CMP-24) are the exception: an empty one is a
        # real answer — "no filter on this scanpath" — not a missing colour.
        base.update(
            {
                k: v
                for k, v in override.items()
                if v or (k in COMPARE_FILTER_STYLE_KEYS and v is not None)
            }
        )
    return base


#: CMP-24: the style keys that carry a scanpath's own *filters* rather than its
#: look. A comparison draws each reading under its own — the figure-level
#: ``fixation_flags`` / ``saccade_classes`` apply to a scanpath whose style names
#: none, so one setting filters both and a style entry overrides it per side.
COMPARE_FILTER_STYLE_KEYS = frozenset({"fixation_flags", "saccade_classes"})


def _visible_saccade_classes(classes: Iterable[str] | None) -> set[str] | None:
    """The saccade classes to draw, ``None`` meaning all (VIZ-31's rule: an empty
    or complete list is no filter)."""
    if not classes or set(classes) >= set(SACCADE_CLASS_ORDER):
        return None
    return set(classes)


def _comparison_filters(style: dict, settings: FigureSettings) -> dict:
    """One scanpath's filters (CMP-24): its style's own, else the figure's."""
    return dict(
        fixation_flags=style.get("fixation_flags", settings.fixation_flags),
        saccade_classes=style.get("saccade_classes", settings.saccade_classes),
    )


def _arrow_class_mask(
    fixations: pd.DataFrame, saccade_classes: pd.Series, keep: set, aseg: list
) -> list[bool]:
    """Which arrowheads belong to a visible saccade class (VIZ-31).

    An arrowhead belongs to the saccade leaving fixation ``aseg[j]`` in time
    order, which is exactly how ``_saccade_segments_by_class`` keys a segment —
    so the filter drops arrows for hidden saccades instead of leaving them
    floating over nothing."""
    ordered_cls = saccade_classes.reindex(
        fixations.sort_values("timestamp_ms").index
    ).tolist()
    return [
        (
            "other"
            if i >= len(ordered_cls) or pd.isna(ordered_cls[i])
            else ordered_cls[i]
        )
        in keep
        for i in aseg
    ]


def _comparison_raw_gaze(
    raw_gaze: pd.DataFrame | None, trial: tuple[str, str], *, show: bool
) -> pd.DataFrame | None:
    """One reading's raw-gaze samples out of the comparison's frame, or ``None``.

    ``raw_gaze`` carries both readings keyed exactly as the words / fixations
    frames are — B's ids already namespaced or renamed apart by the caller — so
    it is sliced by the same ``(participant, trial)`` pair.
    """
    if not show or raw_gaze is None or raw_gaze.empty:
        return None
    rows = raw_gaze[
        (raw_gaze["participant_id"] == trial[0]) & (raw_gaze["trial_id"] == trial[1])
    ]
    return rows if not rows.empty else None


def _add_comparison_raw_gaze_trace(
    fig: go.Figure,
    samples: pd.DataFrame | None,
    display_name: str,
    color: str,
    settings: FigureSettings,
    *,
    row: int | None = None,
    col: int | None = None,
) -> None:
    """One reading's raw-gaze samples in a comparison figure (VIZ-48).

    Drawn in that scanpath's own colour (its style's ``raw_gaze_color``, else
    its fixation colour) rather than the single-trial figure's time scale: two clouds on one Viridis ramp could not be told apart in an
    overlay, and the A/B colour is the cue every other comparison layer keeps.
    Size and opacity are the 🔵 Raw gaze settings, as on the single figure. The
    trace joins its scanpath's legend group, so toggling A in the legend hides
    A's samples with it.
    """
    if samples is None or samples.empty:
        return
    if "timestamp_ms" in samples.columns:
        customdata, when = samples["timestamp_ms"], "<br>t: %{customdata} ms"
    elif SAMPLE_INDEX in samples.columns:  # no clock: the sample's number
        customdata, when = samples[SAMPLE_INDEX], "<br>sample %{customdata}"
    else:
        customdata, when = None, ""
    trace = go.Scatter(
        x=samples["x"],
        y=samples["y"],
        mode="markers",
        marker=dict(
            size=settings.raw_gaze_marker_size,
            color=color,
            opacity=settings.raw_gaze_opacity,
        ),
        hovertemplate=(
            f"Raw gaze · {display_name}<br>x: %{{x:.1f}}<br>y: %{{y:.1f}}"
            + when
            + "<extra></extra>"
        ),
        customdata=customdata,
        name=f"{display_name} · raw gaze",
        legendgroup=display_name,
        showlegend=bool(settings.show_legend),
    )
    if row is not None:
        fig.add_trace(trace, row=row, col=col)
    else:
        fig.add_trace(trace)


def _add_comparison_fixation_trace(
    fig: go.Figure,
    trial_fix: pd.DataFrame,
    display_name: str,
    style: dict,
    font_settings: dict,
    *,
    show_fixations: bool = True,
    show_saccades: bool = True,
    show_saccade_arrows: bool = False,
    show_order: bool = True,
    order_font_size: int | None = None,
    show_legend: bool = False,
    color_by: str | None = None,
    colorscale: str = DEFAULT_FIXATION_COLORSCALE,
    color_range: tuple[float, float] | None = None,
    show_colorbar: bool = False,
    colorbar_style: dict | None = None,
    fixation_symbol: str = DEFAULT_FIXATION_SYMBOL,
    fixation_hover_fields: Sequence[str] | None = None,
    row: int | None = None,
    col: int | None = None,
    trial_words: pd.DataFrame | None = None,
    fixation_flags: dict | None = None,
    saccade_classes: Iterable[str] | None = None,
    duration_scale: dict | None = None,
    category_colors: Sequence[str] | None = None,
) -> None:
    """Add one scanpath's saccades + fixation markers to a comparison figure.

    Saccades and markers are separate traces (mirroring the single-trial figure)
    so the per-scanpath saccade colour/line-style/line-width and hollow markers
    all apply, and the shared ``show_saccades`` / ``show_saccade_arrows`` /
    ``show_order`` toggles take effect.

    Fixation colour: by default each scanpath uses its flat per-scanpath colour
    (the A/B cue). When ``color_by`` names a numeric column, the marker **fill** is
    coloured by that metric (shared ``colorscale`` / ``color_range`` across both
    scanpaths) and the per-scanpath flat colour becomes the marker **outline**, so
    the readings stay distinguishable while still showing the metric. Order numbers
    are tinted to the per-scanpath colour either way.

    ``category_colors`` is the discrete counterpart — one literal colour per row
    of ``trial_fix``, from the figure's shared category→colour mapping
    (:func:`_shared_category_colors`, for a categorical column or colour-by-line).
    It is drawn the same way: category fill, per-scanpath outline.

    ``fixation_symbol`` (VIZ-15/23) sets the marker shape — shape is the channel
    that survives a greyscale print, which is exactly what comparison figures get
    used for. A glyph shape (♥) is drawn as text, as on the static figure
    (:func:`_glyph_scatter_traces`), its A/B outline a larger glyph beneath.

    ``show_fixations=False`` (CMP-7) drops the marker trace, and with it the
    fixation-index labels that ride on it as marker text — the same thing the
    toggle does on the static figure. The saccade and arrow layers are
    independent and keep their own toggles, so a lines-only comparison is still
    reachable. This is what makes a comparison *heatmap* readable: the whole
    point of the split word boxes is lost under two full sets of markers.

    CMP-24: ``fixation_flags`` and ``saccade_classes`` are *this* scanpath's
    filters, applied as the static figure applies them — *Discard* drops markers
    and their index labels (the saccades still bridge across them), *Highlight*
    overlays its marker, and hidden saccade classes lose their line and arrow.
    Both need ``trial_words`` for the geometry they classify against.

    ``duration_scale`` is the figure's (``_settings_size_scale``): both
    scanpaths share it, so under a fixed scale one duration draws at one size
    on either side; only the size *range* is per scanpath.
    """
    if trial_fix.empty:
        return
    if category_colors is not None:
        # Positional, before *Discard* drops rows, so the two stay aligned.
        trial_fix = trial_fix.assign(_category_color=list(category_colors))
    words_for_flags = trial_words if trial_words is not None else pd.DataFrame()
    keep = _visible_saccade_classes(saccade_classes)
    class_series = None
    if keep is not None and (show_saccades or show_saccade_arrows):
        existing = trial_fix.get("saccade_class")
        if existing is not None:
            class_series = existing
        else:
            from .measures import classify_saccades

            class_series = classify_saccades(trial_fix, words_for_flags)
    fix_color = style["fix_color"]
    saccade_color = style["saccade_color"]
    saccade_style = style.get("saccade_style", "solid")
    saccade_width = style.get("saccade_width", DEFAULT_SACCADE_WIDTH)

    def _add(trace):
        if row is not None and col is not None:
            fig.add_trace(trace, row=row, col=col)
        else:
            fig.add_trace(trace)

    # Comparison figures always draw straight connectors (no Arc mode here); bind
    # it once so the segments and the arrowheads can never disagree (BUG-9).
    arch_frac: float | None = None
    if show_saccades and len(trial_fix) > 1:
        if class_series is not None:
            segs = _saccade_segments_by_class(
                trial_fix, "x", "y", class_series, arch_frac
            )
            sx, sy = [], []
            for cls_name, (cx, cy) in segs.items():
                if cls_name in keep:
                    sx.extend(cx)
                    sy.extend(cy)
        else:
            sx, sy = _saccade_segments(trial_fix, "x", "y", arch_frac)
        if sx:
            _add(
                go.Scatter(
                    x=sx,
                    y=sy,
                    mode="lines",
                    line=dict(
                        color=saccade_color, width=saccade_width, dash=saccade_style
                    ),
                    name=display_name,
                    legendgroup=display_name,
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
    if show_saccade_arrows and len(trial_fix) > 1:
        amx, amy, aang, aseg = _saccade_arrow_rows(trial_fix, "x", "y", arch_frac)
        if amx and class_series is not None:
            mask = _arrow_class_mask(trial_fix, class_series, keep, aseg)
            amx = [v for v, m in zip(amx, mask) if m]
            amy = [v for v, m in zip(amy, mask) if m]
            aang = [v for v, m in zip(aang, mask) if m]
        if amx:
            _add(
                go.Scatter(
                    x=amx,
                    y=amy,
                    mode="markers",
                    marker=dict(
                        symbol="arrow",
                        size=12,
                        angle=aang,
                        angleref="up",
                        color=saccade_color,
                        line=dict(width=0),
                    ),
                    legendgroup=display_name,
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    if not show_fixations:
        return

    # Only the categories doing something: the rail always sends all four, so
    # an untouched set must cost nothing (the classification scans the boxes).
    flags = {
        cat: spec
        for cat, spec in (fixation_flags or {}).items()
        if isinstance(spec, dict) and str(spec.get("mode") or "Off") != "Off"
    }
    if flags:
        trial_fix = _discard_flagged_fixations(trial_fix, words_for_flags, flags)
        if trial_fix.empty:
            return
    sizes = _compute_marker_sizes(
        trial_fix["duration_ms"],
        style["marker_size_range"],
        **(duration_scale or {}),
    )
    # Metric colouring ("Color fixations by") when a numeric column is chosen:
    # colour the FILL by the metric (shared colorscale/range across both
    # scanpaths) and keep the per-scanpath flat colour as the marker OUTLINE so
    # A/B stay distinguishable. Otherwise the fill is the flat per-scanpath colour.
    metric_color = bool(
        color_by
        and color_by != "line"
        and color_by in trial_fix.columns
        and pd.api.types.is_numeric_dtype(trial_fix[color_by])
    )
    symbol = _marker_symbol(fixation_symbol)
    if metric_color:
        marker = dict(
            size=sizes,
            symbol=symbol,
            color=trial_fix[color_by],
            colorscale=colorscale,
            cmin=color_range[0] if color_range else None,
            cmax=color_range[1] if color_range else None,
            showscale=bool(show_colorbar),
            # VIZ-23: the same styled colorbar the static figure builds, so the
            # orientation / tick-angle / tick-size controls reach Compare too.
            colorbar=_colorbar_dict(_column_title(color_by), **(colorbar_style or {}))
            if show_colorbar
            else None,
            line=dict(color=fix_color, width=1.4),
        )
    elif category_colors is not None:
        # The discrete counterpart: the shared category colour fills, the
        # per-scanpath colour outlines — the same A/B cue as a numeric metric.
        marker = dict(
            size=sizes,
            symbol=symbol,
            color=trial_fix["_category_color"].tolist(),
            line=dict(color=fix_color, width=1.4),
        )
    else:
        marker = dict(
            size=sizes,
            symbol=symbol,
            color=fix_color,
            line=dict(color=FIX_MARKER_OUTLINE, width=0.5),
        )
    # Per-scanpath marker alpha (VIZ-6): always set it (even 1.0) so the control
    # overrides Plotly's ~0.7 default for variable-size scatter markers.
    opacity = style.get("opacity", 1.0)
    marker["opacity"] = float(opacity if opacity is not None else 1.0)
    if style.get("hollow"):
        marker = _make_hollow(marker)
    order_font = dict(font_settings)
    order_font["color"] = fix_color
    if order_font_size is not None:
        order_font["size"] = order_font_size
    # VIZ-26 hover fields (the "Hover fields" multiselect under 👁️ Fixations)
    # reach the comparison figure too — it used to hard-code Order/Time/Duration
    # regardless of that setting, which is what made the control look inert
    # while comparing. Same fallback list the static + animation builders use
    # when nothing is explicitly chosen, so the three render paths agree.
    hover_fields = (
        ["order_in_trial", "duration_ms", "word_id"]
        if fixation_hover_fields is None
        else list(fixation_hover_fields)
    )
    customdata, hovertemplate = _hover_payload(trial_fix, hover_fields)
    glyph = FIXATION_GLYPH_SYMBOLS.get(fixation_symbol or "")
    # The trace's own legend swatch would mislead under category colours (it
    # shows the first fixation's category) and cannot draw a glyph (♥), so in
    # either case a separate entry names the scanpath.
    own_entry = category_colors is not None or bool(glyph)
    if glyph:
        # VIZ-15: ♥ as text, as on the static figure (`_glyph_scatter_traces`);
        # the index labels and a numeric colour bar get traces of their own.
        for trace in _glyph_scatter_traces(
            trial_fix["x"],
            trial_fix["y"],
            marker,
            glyph,
            name=display_name,
            legendgroup=display_name,
            showlegend=False,
            hovertemplate=f"{display_name} {hovertemplate}",
            customdata=customdata,
        ):
            _add(trace)
        if show_order:
            _add(
                go.Scatter(
                    x=trial_fix["x"],
                    y=trial_fix["y"],
                    mode="text",
                    text=trial_fix["order_in_trial"],
                    textposition="top center",
                    textfont=order_font,
                    name=f"{display_name} · index",
                    legendgroup=display_name,
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
        bar = _glyph_colorbar_trace(marker, trial_fix[color_by] if metric_color else ())
        if bar is not None:
            _add(bar)
    else:
        _add(
            go.Scatter(
                x=trial_fix["x"],
                y=trial_fix["y"],
                mode="markers+text" if show_order else "markers",
                marker=marker,
                name=display_name,
                legendgroup=display_name,
                showlegend=show_legend and not own_entry,
                text=trial_fix["order_in_trial"] if show_order else None,
                textposition="top center",
                textfont=order_font,
                hovertemplate=f"{display_name} {hovertemplate}",
                customdata=customdata,
            )
        )
    if show_legend and own_entry:
        coloured = metric_color or category_colors is not None
        _add(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    size=10,
                    symbol=symbol,
                    color="#ffffff" if coloured else fix_color,
                    line=dict(
                        color=fix_color if coloured else FIX_MARKER_OUTLINE,
                        width=2 if coloured else 0.5,
                    ),
                ),
                name=display_name,
                legendgroup=display_name,
                showlegend=True,
                hoverinfo="skip",
            )
        )
    if flags:
        overlay = _fixation_flag_masks(trial_fix, words_for_flags, flags)
        for cat in _FIX_FLAG_CATEGORIES:
            spec = flags.get(cat, {})
            if spec.get("mode") != "Highlight" or cat not in overlay:
                continue
            hits = trial_fix[overlay[cat]]
            if hits.empty:
                continue
            name = _FIX_FLAG_LABELS[cat]
            _add(
                go.Scatter(
                    x=hits["x"],
                    y=hits["y"],
                    mode="markers",
                    marker=dict(
                        symbol=spec.get("symbol") or "x",
                        size=13,
                        color=spec.get("color") or OUT_OF_TEXT_COLOR,
                        line=dict(color=fix_color, width=1.5),
                    ),
                    name=f"{display_name} · {name}",
                    legendgroup=display_name,
                    showlegend=show_legend,
                    hovertemplate=(
                        f"{display_name} · {name} fixation<br>"
                        "x %{x:.0f}, y %{y:.0f}<extra></extra>"
                    ),
                )
            )


def _comparison_metric_colorbar(
    fixations: pd.DataFrame, color_by: str | None, show_colorbars: bool
) -> bool:
    """Whether a comparison figure will actually draw a metric colorbar.

    Same test :func:`_add_comparison_fixation_trace` makes per trace, hoisted so
    the layout can reserve room for a horizontal bar below the plot (VIZ-23).
    """
    return bool(
        show_colorbars
        and color_by
        and color_by != "line"
        and color_by in fixations.columns
        and pd.api.types.is_numeric_dtype(fixations[color_by])
    )


def _word_id_keys(values: pd.Series) -> pd.Series:
    """Word ids as join keys that mean the same thing on both frames (CMP-7).

    The words table and the fixations table routinely disagree on dtype: word
    boxes carry an integer ``word_id`` while a fixation's is a float, because it
    is NaN wherever the fixation landed outside every box. A plain ``str()`` then
    yields ``"7"`` on one side and ``"7.0"`` on the other, so a keyed join
    silently matches nothing — which is exactly how the comparison heatmap came
    out empty. Whole numbers lose the decimal tail here; anything non-numeric
    keeps its stripped string, so datasets with string word ids still join.
    """
    numeric = pd.to_numeric(values, errors="coerce")
    integral = numeric.notna() & (numeric % 1 == 0)
    text = values.astype(str).str.strip()
    if not integral.any():
        return text
    return text.mask(integral, numeric.where(integral, 0).astype("int64").astype(str))


def _comparison_word_heatmap_data(
    trial_specs: Sequence[dict],
    *,
    metric: str,
    heatmap_range: tuple[float, float] | None,
    heatmap_norm: str,
) -> tuple[list[dict[str, float]], float, float, str]:
    """Per-trial word values and one shared transformed colour range (CMP-7)."""
    value_maps: list[dict[str, float]] = []
    all_values: list[float] = []
    duration_weighted = metric == "duration_ms"
    for spec in trial_specs:
        fixations = spec["trial_fix"]
        if fixations.empty or "word_id" not in fixations.columns:
            values: dict[str, float] = {}
        else:
            valid = fixations[fixations["word_id"].notna()].copy()
            keys = _word_id_keys(valid["word_id"])
            if duration_weighted and "duration_ms" in valid.columns:
                grouped = (
                    pd.to_numeric(valid["duration_ms"], errors="coerce")
                    .groupby(keys)
                    .sum()
                )
            else:
                grouped = valid.groupby(keys).size()
            values = {str(key): float(value) for key, value in grouped.items()}
        value_maps.append(values)
        all_values.extend(value for value in values.values() if value > 0)
    if heatmap_range is not None:
        raw_min, raw_max = map(float, heatmap_range)
    elif all_values:
        # Auto starts at 0, as the single-trial word heatmap does.
        raw_min, raw_max = 0.0, max(all_values)
    else:
        raw_min, raw_max = 0.0, 1.0
    z_min = float(_apply_heatmap_norm(raw_min, heatmap_norm))
    z_max = float(_apply_heatmap_norm(raw_max, heatmap_norm))
    if z_max <= z_min:
        z_max = z_min + 1.0
    title = _WORD_DWELL_TITLE if duration_weighted else "Fixation count"
    return value_maps, z_min, z_max, title


def _comparison_heatmap_shapes(
    words: pd.DataFrame,
    values: dict[str, float],
    *,
    heatmap_colorscale: str,
    heatmap_norm: str,
    z_min: float,
    z_max: float,
    half: str | None = None,
    xref: str | None = None,
    yref: str | None = None,
) -> list[dict]:
    """Tint full word boxes or their left/right half on a shared scale."""
    if words.empty or not values:
        return []
    from plotly.colors import sample_colorscale

    from .measures import word_box_bounds

    shapes: list[dict] = []
    z_span = max(z_max - z_min, 1e-9)
    if "word_id" not in words.columns:
        return []
    keys = _word_id_keys(words["word_id"])
    for key, (x0, y0, x1, y1) in zip(keys, zip(*word_box_bounds(words))):
        value = values.get(key, 0.0)
        if value <= 0:
            continue
        midpoint = (x0 + x1) / 2.0
        if half == "left":
            x1 = midpoint
        elif half == "right":
            x0 = midpoint
        transformed = float(_apply_heatmap_norm(value, heatmap_norm))
        position = max(0.0, min(1.0, (transformed - z_min) / z_span))
        shape = dict(
            type="rect",
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            line=dict(width=0),
            fillcolor=sample_colorscale(heatmap_colorscale, [position])[0],
            opacity=0.55,
            layer="below",
            name=_shape_layer_tag("heatmap"),
        )
        if xref is not None:
            shape["xref"] = xref
        if yref is not None:
            shape["yref"] = yref
        shapes.append(shape)
    return shapes


def _comparison_heatmap_colorbar_trace(
    *,
    colorscale: str,
    z_min: float,
    z_max: float,
    title: str,
    heatmap_norm: str,
    colorbar_style: dict,
) -> go.Scatter:
    return go.Scatter(
        x=[None],
        y=[None],
        mode="markers",
        marker=dict(
            colorscale=colorscale,
            showscale=True,
            cmin=z_min,
            cmax=z_max,
            colorbar=_colorbar_dict(
                _heatmap_title(title, heatmap_norm), **colorbar_style
            ),
        ),
        showlegend=False,
        hoverinfo="skip",
        name="comparison heatmap colorbar",
    )


def _comparison_heatmap_colorbar_traces(
    trial_specs: Sequence[dict],
    *,
    z_min: float,
    z_max: float,
    title: str,
    heatmap_norm: str,
    colorbar_style: dict,
    overlay: bool,
) -> list[go.Scatter]:
    """The comparison heatmap's colour bar(s): one while A and B share a colour
    scale, else one per scanpath on the same range (`_arrange_colorbars` sets
    them side by side). The overlay's titles say which half is whose."""
    scales = [spec["heatmap_colorscale"] for spec in trial_specs]
    sides = ("left A", "right B") if overlay else ("A", "B")
    if len(set(scales)) == 1:
        named = [(scales[0], " · left A / right B" if overlay else "")]
    else:
        named = [(scale, f" · {side}") for scale, side in zip(scales, sides)]
    return [
        _comparison_heatmap_colorbar_trace(
            colorscale=scale,
            z_min=z_min,
            z_max=z_max,
            title=title + suffix,
            heatmap_norm=heatmap_norm,
            colorbar_style=colorbar_style,
        )
        for scale, suffix in named
    ]


def _make_split_comparison_figure(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    trial_a: tuple[str, str],
    trial_b: tuple[str, str],
    *,
    settings: FigureSettings,
    orientation: str,
    styles: tuple[dict, dict] | None = None,
    raw_gaze: pd.DataFrame | None = None,
) -> go.Figure:
    """Two-panel comparison, either horizontal (side-by-side) or vertical (stacked).

    Each panel computes its **own** axis ranges from its trial's words +
    fixations, which is what lets the two panels sit in different coordinate
    spaces at all (CMP-8).

    The stimulus-image background (VIZ-4) is added to both panels. It used to be
    the *same* image on the grounds that "the two readings are of the same
    text" — no longer true once B may come from another corpus, so B's panel
    takes ``background_image_b`` (and its size/origin) when given and falls back
    to A's otherwise, which is every same-dataset comparison.

    Likewise ``canvas_b``: B's screen, defaulting to A's. It feeds B's axis
    ranges *and* its label-fitting pair, so B's reading text stays true-to-scale
    on **B's** monitor rather than being sized against A's.
    """
    from plotly.subplots import make_subplots

    canvas_width = settings.canvas_width
    canvas_height = settings.canvas_height
    font_family = settings.font_family
    base_font_size = settings.base_font_size
    show_words = settings.show_words
    show_word_labels = settings.show_word_labels
    trial_labels = settings.trial_labels
    marker_size_range = settings.marker_size_range
    show_fixations = settings.show_fixations
    show_saccades = settings.show_saccades
    show_saccade_arrows = settings.show_saccade_arrows
    show_order = settings.show_order
    show_legend = settings.show_legend
    order_font_size = settings.order_font_size
    color_by = settings.color_by
    color_by_line = settings.color_by_line
    fixation_colorscale = settings.fixation_colorscale
    fixation_color_range = settings.fixation_color_range
    fixation_symbol = settings.fixation_symbol
    # The fixations' colour bar and the heatmap's, each with its own style.
    show_colorbars = settings.show_fixation_colorbar
    show_heatmap_colorbar = settings.show_heatmap_colorbar
    show_heatmap = settings.show_heatmap
    heatmap_metric = settings.heatmap_metric
    heatmap_range = settings.heatmap_range
    heatmap_norm = settings.heatmap_norm
    colorbar_orientation = settings.fixation_colorbar_orientation
    colorbar_tickangle = settings.fixation_colorbar_tickangle
    colorbar_tickfont_size = settings.fixation_colorbar_tickfont_size
    heat_cb_style = dict(
        orientation=settings.heatmap_colorbar_orientation,
        tickangle=settings.heatmap_colorbar_tickangle,
        tickfont_size=settings.heatmap_colorbar_tickfont_size,
    )
    text_color = settings.text_color
    highlight_column = settings.highlight_column
    highlight_text_color = settings.highlight_text_color
    word_hover_measure = settings.word_hover_measure
    word_hover_fields = settings.word_hover_fields
    fixation_hover_fields = settings.fixation_hover_fields
    background_color = settings.background_color
    line_spacing = settings.line_spacing
    scale_text_to_boxes = settings.scale_text_to_boxes
    background_image = settings.background_image
    background_image_size = settings.background_image_size
    background_image_origin = settings.background_image_origin
    background_image_opacity = settings.background_image_opacity
    fit_to_monitor = settings.fit_to_monitor
    show_coordinate_grid = settings.show_coordinate_grid
    coordinate_grid_spacing = settings.coordinate_grid_spacing

    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)
    cb_style = dict(
        orientation=colorbar_orientation,
        tickangle=colorbar_tickangle,
        tickfont_size=colorbar_tickfont_size,
    )
    is_stacked = orientation == "stacked"
    # Per-panel canvas: B falls back to A's, so a same-dataset comparison is
    # byte-identical to the pre-CMP-8 figure.
    canvas_b = settings.canvas_b or (canvas_width, canvas_height)
    panel_canvas = [(canvas_width, canvas_height), (int(canvas_b[0]), int(canvas_b[1]))]
    # Each panel's share of its screen, for the preliminary fit that picks the
    # figure's size. The word labels are *not* sized from it: they are sized
    # from the subplot space each panel finally gets (round-8 review, finding 5).
    panel_widths = [w if is_stacked else w // 2 for w, _ in panel_canvas]
    # B's stimulus page. Inheriting A's is right for a same-dataset pair (two
    # readings of the same text) and *wrong* across datasets — a PoTeC panel with
    # a OneStop page under it is a picture of two different things. So when B has
    # its own screen (`canvas_b`, i.e. a cross-dataset pair) B's panel draws only
    # an image explicitly given for it, and otherwise draws none.
    if settings.background_image_b is not None:
        image_b = (
            settings.background_image_b,
            settings.background_image_size_b,
            settings.background_image_origin_b,
        )
    elif settings.canvas_b is None:
        image_b = (background_image, background_image_size, background_image_origin)
    else:
        image_b = (None, None, None)
    panel_images = [
        (background_image, background_image_size, background_image_origin),
        image_b,
    ]

    # Shared metric colour range across both panels (when colouring by a metric
    # and no explicit range), so the two scanpaths use one comparable scale.
    metric_range = fixation_color_range
    if (
        color_by
        and color_by != "line"
        and metric_range is None
        and color_by in fixations.columns
        and pd.api.types.is_numeric_dtype(fixations[color_by])
    ):
        both = fixations[
            (
                (fixations["participant_id"] == trial_a[0])
                & (fixations["trial_id"] == trial_a[1])
            )
            | (
                (fixations["participant_id"] == trial_b[0])
                & (fixations["trial_id"] == trial_b[1])
            )
        ][color_by]
        if len(both) and pd.notna(both.min()) and pd.notna(both.max()):
            metric_range = (float(both.min()), float(both.max()))

    trial_specs = []
    for idx, trial in enumerate([trial_a, trial_b]):
        participant, trial_id = trial
        trial_words = words[
            (words["participant_id"] == participant) & (words["trial_id"] == trial_id)
        ]
        trial_fix = fixations[
            (fixations["participant_id"] == participant)
            & (fixations["trial_id"] == trial_id)
        ].sort_values("timestamp_ms")
        display_name = _plotly_literal(
            _resolve_trial_display_name(
                participant, trial_id, trial_words, trial_labels, idx
            )
        )
        style = _comparison_scanpath_style(
            idx,
            styles[idx] if styles else None,
            default_marker_size_range=marker_size_range,
        )
        trial_specs.append(
            dict(
                trial_words=trial_words,
                trial_fix=trial_fix,
                raw_gaze=_comparison_raw_gaze(
                    raw_gaze, trial, show=settings.show_raw_gaze
                ),
                display_name=display_name,
                style=style,
                color=style["fix_color"],
                # The word-box outline: the scanpath's own colour unless its
                # style names one (`box_color`).
                box_color=style.get("box_color") or style["fix_color"],
                # Its fill: the figure's unless the style names one.
                box_fill_color=(
                    style.get("box_fill_color") or settings.word_box_fill_color
                ),
                # Its raw-gaze samples: the scanpath's own colour unless its
                # style names one (`raw_gaze_color`).
                raw_gaze_color=style.get("raw_gaze_color") or style["fix_color"],
                # Its heatmap's colour scale: the figure's unless the style
                # names one (`heatmap_colorscale`). The range stays shared.
                heatmap_colorscale=(
                    style.get("heatmap_colorscale") or settings.heatmap_colorscale
                ),
            )
        )

    heatmap_maps, heatmap_min, heatmap_max, heatmap_title = (
        _comparison_word_heatmap_data(
            trial_specs,
            metric=heatmap_metric,
            heatmap_range=heatmap_range,
            heatmap_norm=heatmap_norm,
        )
        if show_heatmap
        else ([], 0.0, 1.0, "")
    )

    # A categorical column or colour-by-line: one category→colour mapping for
    # both panels, each reading's lines against its own word boxes.
    category_colors, category_legend = _shared_category_colors(
        [
            _fixation_category_labels(
                spec["trial_fix"], spec["trial_words"], color_by, color_by_line
            )
            for spec in trial_specs
        ],
        avoid=[spec["color"] for spec in trial_specs],
    )
    category_label = "line" if (color_by_line or color_by == "line") else color_by
    legend_on = show_legend or bool(category_legend)

    # The panel names are the split layouts' A/B legend, so they follow its
    # toggle (BUG-90): with it off the top margin is 0, which clipped the upper
    # title off the canvas while the lower one, sitting in the gap between the
    # panels, still showed.
    subplot_titles = (
        [trial_specs[0]["display_name"], trial_specs[1]["display_name"]]
        if show_legend
        else None
    )

    # Each panel's own axis ranges, from its trial's words + fixations (CMP-8).
    panel_ranges = []
    for idx, spec in enumerate(trial_specs):
        panel_cw, panel_ch = panel_canvas[idx]
        x_range, y_range, *_ = _compute_axis_ranges(
            panel_cw,
            panel_ch,
            (spec["trial_fix"], "x", "y"),
            (spec["raw_gaze"], "x", "y"),
            word_frames=[spec["trial_words"]] if not spec["trial_words"].empty else [],
            fit_to_monitor=fit_to_monitor,
        )
        panel_ranges.append((x_range, y_range))
    panel_fits = [
        _fit_display_size(
            panel_widths[idx], panel_canvas[idx][1], x_range, y_range, spatial_axes=True
        )
        for idx, (x_range, y_range) in enumerate(panel_ranges)
    ]

    # The figure's size, chosen before anything is sized against it. Two panels
    # that share a screen reuse the last panel's fit — which keeps every
    # same-dataset figure the size it always was. Two *different* screens can't
    # be reconciled that way: the panels then get the widest / tallest fit of the
    # pair, so neither is clipped. (Which is also why the caption in
    # `tabs._render_comparison_figure` says sizes are not comparable across
    # panels — each panel is true-to-scale on its own monitor.)
    if settings.canvas_b is None:
        panel_w, panel_h = panel_fits[-1]
    else:
        panel_w = max(fit[0] for fit in panel_fits)
        panel_h = max(fit[1] for fit in panel_fits)
    if is_stacked:
        total_width = panel_w
        total_height = panel_h * 2 + 40
    else:  # side-by-side
        total_width = panel_w * 2
        total_height = panel_h
    # A colour bar gets its own reserved band — below the panels when horizontal
    # (VIZ-23), to their right when vertical — so the figure grows by it rather
    # than Plotly's automargin shrinking the panels under text already sized for
    # them (the single-trial figure's `_decoration_margins` rule).
    reserves = _colorbar_reserves(
        (
            _comparison_metric_colorbar(fixations, color_by, show_colorbars),
            colorbar_orientation,
        ),
        (
            bool(show_heatmap and show_heatmap_colorbar and any(heatmap_maps)),
            heat_cb_style["orientation"],
        ),
    )
    bottom_px = _COLORBAR_BOTTOM_PX if reserves["colorbar_below"] else 0
    right_px = _COLORBAR_RESERVE_PX if reserves["colorbar_right"] else 0
    grid_left = _GRID_LEFT_RESERVE_PX if show_coordinate_grid else 0
    grid_bottom = _GRID_BOTTOM_RESERVE_PX if show_coordinate_grid else 0
    # The t band was the (now-removed) title; keep a slim band only for the
    # optional legend.
    top_px = (_compare_legend_font(base_font_size)["size"] + 14) if legend_on else 0
    figure_width = total_width + grid_left + right_px
    figure_height = total_height + bottom_px + grid_bottom
    plot_area = (
        max(figure_width - grid_left - right_px, 1),
        max(figure_height - top_px - bottom_px - grid_bottom, 1),
    )
    if is_stacked:
        fig = make_subplots(
            rows=2,
            cols=1,
            vertical_spacing=0.08,
            subplot_titles=subplot_titles,
        )
    else:
        fig = make_subplots(
            rows=1,
            cols=2,
            horizontal_spacing=0.04,
            subplot_titles=subplot_titles,
        )

    # Each panel's data→screen scale, from the subplot space it actually gets
    # in the final figure: its domain's share of the plot area, then the
    # equal-aspect constraint, which shrinks whichever side has room to spare.
    panel_displays = []
    for idx, (x_range, y_range) in enumerate(panel_ranges):
        suffix = "" if idx == 0 else str(idx + 1)
        x_domain = fig.layout[f"xaxis{suffix}"].domain
        y_domain = fig.layout[f"yaxis{suffix}"].domain
        scale = _display_scale(
            x_range,
            y_range,
            (x_domain[1] - x_domain[0]) * plot_area[0],
            (y_domain[1] - y_domain[0]) * plot_area[1],
        )
        panel_displays.append(
            (
                scale,
                round((x_range[1] - x_range[0]) * scale),
                round((y_range[0] - y_range[1]) * scale),
            )
        )

    all_shapes: list = []
    for idx, spec in enumerate(trial_specs):
        if is_stacked:
            row, col = idx + 1, 1
            axis_suffix = "" if idx == 0 else str(idx + 1)
        else:
            row, col = 1, idx + 1
            axis_suffix = "" if idx == 0 else str(idx + 1)
        xref = f"x{axis_suffix}"
        yref = f"y{axis_suffix}"
        trial_words = spec["trial_words"]
        trial_fix = spec["trial_fix"]
        x_range, y_range = panel_ranges[idx]
        panel_scale, panel_display_w, panel_display_h = panel_displays[idx]

        # Stimulus-page background image (VIZ-4/23), one per panel, UNDER every
        # trace — `row`/`col` bind it to this panel's axes. B may carry its own
        # (CMP-8); it falls back to A's when it doesn't.
        panel_image, panel_image_size, panel_image_origin = panel_images[idx]
        _add_background_image(
            fig,
            panel_image,
            panel_image_size,
            panel_image_origin,
            background_image_opacity,
            row=row,
            col=col,
        )

        if show_heatmap:
            all_shapes.extend(
                _comparison_heatmap_shapes(
                    trial_words,
                    heatmap_maps[idx],
                    heatmap_colorscale=spec["heatmap_colorscale"],
                    heatmap_norm=heatmap_norm,
                    z_min=heatmap_min,
                    z_max=heatmap_max,
                    xref=xref,
                    yref=yref,
                )
            )

        if show_words and not trial_words.empty:
            for box in build_word_boxes(
                trial_words,
                color=spec["box_color"],
                fill_color=spec["box_fill_color"],
                fill_opacity=settings.word_box_fill_opacity,
                line_opacity=settings.word_box_line_opacity,
            ):
                box = dict(box)
                box["xref"] = xref
                box["yref"] = yref
                all_shapes.append(box)

        all_shapes.append(
            dict(
                type="rect",
                xref=xref,
                yref=yref,
                x0=x_range[0],
                y0=y_range[1],
                x1=x_range[1],
                y1=y_range[0],
                line=dict(color="#000000", width=1),
                fillcolor="rgba(0,0,0,0)",
            )
        )

        # Under the scanpath, as on the single-trial figure.
        _add_comparison_raw_gaze_trace(
            fig,
            spec["raw_gaze"],
            spec["display_name"],
            spec["raw_gaze_color"],
            settings,
            row=row,
            col=col,
        )
        _add_comparison_fixation_trace(
            fig,
            trial_fix,
            spec["display_name"],
            spec["style"],
            font_settings,
            show_fixations=show_fixations,
            show_saccades=show_saccades,
            show_saccade_arrows=show_saccade_arrows,
            show_order=show_order,
            order_font_size=order_font_size,
            show_legend=show_legend,
            color_by=color_by,
            colorscale=fixation_colorscale,
            color_range=metric_range,
            show_colorbar=show_colorbars and idx == 0,
            colorbar_style=cb_style,
            fixation_symbol=fixation_symbol,
            fixation_hover_fields=fixation_hover_fields,
            row=row,
            col=col,
            trial_words=spec["trial_words"],
            **_comparison_filters(spec["style"], settings),
            duration_scale=_settings_size_scale(settings),
            category_colors=category_colors[idx],
        )

        if show_word_labels:
            _add_word_label_trace(
                fig,
                trial_words,
                _word_label_font_px(
                    trial_words,
                    scale=panel_scale,
                    line_spacing=line_spacing,
                    manual_font_px=base_font_size,
                    scale_text_to_boxes=scale_text_to_boxes,
                ),
                font_settings["family"],
                row=row,
                col=col,
                highlight_column=highlight_column,
                text_color=text_color,
                highlight_text_color=highlight_text_color,
                word_hover_measure=word_hover_measure,
                word_hover_fields=word_hover_fields,
            )

        xaxis_key = "xaxis" if idx == 0 else f"xaxis{idx + 1}"
        yaxis_key = "yaxis" if idx == 0 else f"yaxis{idx + 1}"
        xaxis = dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            title=None,
            range=x_range,
            constrain="domain",
        )
        yaxis = dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            title=None,
            range=y_range,
            constrain="domain",
            scaleanchor=xref,
            scaleratio=1,
        )
        _apply_coordinate_grid_axes(
            xaxis,
            yaxis,
            show=show_coordinate_grid,
            spacing=coordinate_grid_spacing,
            x_range=x_range,
            y_range=y_range,
            rendered_width=panel_display_w,
            rendered_height=panel_display_h,
        )
        fig.update_layout(**{xaxis_key: xaxis, yaxis_key: yaxis})

    if show_heatmap and show_heatmap_colorbar and any(heatmap_maps):
        for trace in _comparison_heatmap_colorbar_traces(
            trial_specs,
            z_min=heatmap_min,
            z_max=heatmap_max,
            title=heatmap_title,
            heatmap_norm=heatmap_norm,
            colorbar_style=heat_cb_style,
            overlay=False,
        ):
            fig.add_trace(trace)
    _add_category_legend(fig, category_legend, category_label or "")

    fig.update_layout(
        height=figure_height,
        width=figure_width,
        autosize=False,
        margin=dict(l=grid_left, r=right_px, t=top_px, b=bottom_px + grid_bottom),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="right",
            x=1,
            font=_compare_legend_font(base_font_size, font_family),
        ),
        template="plotly_white",
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        font=font_settings,
        shapes=all_shapes,
    )
    return fig


def _compare_stimulus_sides(value: str | None) -> tuple[bool, bool]:
    """``compare_stimulus`` → ``(draw A's stimulus, draw B's)`` (CMP-11).

    Tolerant of an unrecognised value on purpose: this reads a share-link param
    and a saved config, and drawing both sets of boxes is the honest fallback —
    it shows what is there rather than silently hiding one reading's AOIs.
    """
    normalized = str(value or "both").strip().lower()
    if normalized == "a":
        return True, False
    if normalized == "b":
        return False, True
    return True, True


def _render_comparison_figure(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    trial_a: tuple[str, str],
    trial_b: tuple[str, str],
    *,
    settings: FigureSettings,
    raw_gaze: pd.DataFrame | None = None,
) -> go.Figure:
    """Two scanpaths on one canvas — overlaid, side by side, or stacked.

    The shared settings contract keeps marker shape, highlighted text, stimulus
    image, and colorbar styling consistent across all three layouts (VIZ-23).
    """
    canvas_width = settings.canvas_width
    canvas_height = settings.canvas_height
    font_family = settings.font_family
    base_font_size = settings.base_font_size
    show_words = settings.show_words
    show_word_labels = settings.show_word_labels
    trial_labels = settings.trial_labels
    layout = settings.layout
    marker_size_range = settings.marker_size_range
    style_a = settings.style_a
    style_b = settings.style_b
    show_fixations = settings.show_fixations
    show_saccades = settings.show_saccades
    show_saccade_arrows = settings.show_saccade_arrows
    show_order = settings.show_order
    show_legend = settings.show_legend
    order_font_size = settings.order_font_size
    color_by = settings.color_by
    color_by_line = settings.color_by_line
    fixation_colorscale = settings.fixation_colorscale
    fixation_color_range = settings.fixation_color_range
    fixation_symbol = settings.fixation_symbol
    # The fixations' colour bar and the heatmap's, each with its own style.
    show_colorbars = settings.show_fixation_colorbar
    show_heatmap_colorbar = settings.show_heatmap_colorbar
    show_heatmap = settings.show_heatmap
    heatmap_metric = settings.heatmap_metric
    heatmap_range = settings.heatmap_range
    heatmap_norm = settings.heatmap_norm
    colorbar_orientation = settings.fixation_colorbar_orientation
    colorbar_tickangle = settings.fixation_colorbar_tickangle
    colorbar_tickfont_size = settings.fixation_colorbar_tickfont_size
    heat_cb_style = dict(
        orientation=settings.heatmap_colorbar_orientation,
        tickangle=settings.heatmap_colorbar_tickangle,
        tickfont_size=settings.heatmap_colorbar_tickfont_size,
    )
    text_color = settings.text_color
    highlight_column = settings.highlight_column
    highlight_text_color = settings.highlight_text_color
    word_hover_measure = settings.word_hover_measure
    word_hover_fields = settings.word_hover_fields
    fixation_hover_fields = settings.fixation_hover_fields
    background_color = settings.background_color
    line_spacing = settings.line_spacing
    scale_text_to_boxes = settings.scale_text_to_boxes
    background_image = settings.background_image
    background_image_size = settings.background_image_size
    background_image_origin = settings.background_image_origin
    background_image_opacity = settings.background_image_opacity
    fit_to_monitor = settings.fit_to_monitor
    show_coordinate_grid = settings.show_coordinate_grid
    coordinate_grid_spacing = settings.coordinate_grid_spacing
    if layout in {"side_by_side", "stacked"}:
        return _make_split_comparison_figure(
            words,
            fixations,
            trial_a,
            trial_b,
            settings=settings,
            orientation=layout,
            styles=(style_a, style_b),
            raw_gaze=raw_gaze,
        )

    # Shared metric colour range across BOTH trials (when colouring by a numeric
    # metric and the user didn't pin a range), so the two scanpaths use one
    # comparable scale.
    metric_range = fixation_color_range
    if (
        color_by
        and color_by != "line"
        and metric_range is None
        and color_by in fixations.columns
        and pd.api.types.is_numeric_dtype(fixations[color_by])
    ):
        both = fixations[
            (
                (fixations["participant_id"] == trial_a[0])
                & (fixations["trial_id"] == trial_a[1])
            )
            | (
                (fixations["participant_id"] == trial_b[0])
                & (fixations["trial_id"] == trial_b[1])
            )
        ][color_by]
        if len(both) and pd.notna(both.min()) and pd.notna(both.max()):
            metric_range = (float(both.min()), float(both.max()))

    fig = go.Figure()
    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)
    cb_style = dict(
        orientation=colorbar_orientation,
        tickangle=colorbar_tickangle,
        tickfont_size=colorbar_tickfont_size,
    )
    overrides = (style_a, style_b)
    # Stimulus-page background image (VIZ-4/23), UNDER both scanpaths.
    _add_background_image(
        fig,
        background_image,
        background_image_size,
        background_image_origin,
        background_image_opacity,
    )

    trial_specs = []
    for idx, trial in enumerate([trial_a, trial_b]):
        participant, trial_id = trial
        trial_words = words[
            (words["participant_id"] == participant) & (words["trial_id"] == trial_id)
        ]
        trial_fix = fixations[
            (fixations["participant_id"] == participant)
            & (fixations["trial_id"] == trial_id)
        ].sort_values("timestamp_ms")
        display_name = _plotly_literal(
            _resolve_trial_display_name(
                participant, trial_id, trial_words, trial_labels, idx
            )
        )
        style = _comparison_scanpath_style(
            idx, overrides[idx], default_marker_size_range=marker_size_range
        )
        trial_specs.append(
            dict(
                trial_words=trial_words,
                trial_fix=trial_fix,
                raw_gaze=_comparison_raw_gaze(
                    raw_gaze, trial, show=settings.show_raw_gaze
                ),
                display_name=display_name,
                style=style,
                color=style["fix_color"],
                # The word-box outline: the scanpath's own colour unless its
                # style names one (`box_color`).
                box_color=style.get("box_color") or style["fix_color"],
                # Its fill: the figure's unless the style names one.
                box_fill_color=(
                    style.get("box_fill_color") or settings.word_box_fill_color
                ),
                # Its raw-gaze samples: the scanpath's own colour unless its
                # style names one (`raw_gaze_color`).
                raw_gaze_color=style.get("raw_gaze_color") or style["fix_color"],
                # Its heatmap's colour scale: the figure's unless the style
                # names one (`heatmap_colorscale`). The range stays shared.
                heatmap_colorscale=(
                    style.get("heatmap_colorscale") or settings.heatmap_colorscale
                ),
            )
        )

    heatmap_maps, heatmap_min, heatmap_max, heatmap_title = (
        _comparison_word_heatmap_data(
            trial_specs,
            metric=heatmap_metric,
            heatmap_range=heatmap_range,
            heatmap_norm=heatmap_norm,
        )
        if show_heatmap
        else ([], 0.0, 1.0, "")
    )

    if show_heatmap:
        reference_words = next(
            (
                spec["trial_words"]
                for spec in trial_specs
                if not spec["trial_words"].empty
            ),
            pd.DataFrame(),
        )
        existing = list(fig.layout.shapes) if fig.layout.shapes else []
        for index, half in enumerate(("left", "right")):
            existing.extend(
                _comparison_heatmap_shapes(
                    reference_words,
                    heatmap_maps[index],
                    heatmap_colorscale=trial_specs[index]["heatmap_colorscale"],
                    heatmap_norm=heatmap_norm,
                    z_min=heatmap_min,
                    z_max=heatmap_max,
                    half=half,
                )
            )
        fig.update_layout(shapes=existing)
        if show_heatmap_colorbar and any(heatmap_maps):
            for trace in _comparison_heatmap_colorbar_traces(
                trial_specs,
                z_min=heatmap_min,
                z_max=heatmap_max,
                title=heatmap_title,
                heatmap_norm=heatmap_norm,
                colorbar_style=heat_cb_style,
                overlay=True,
            ):
                fig.add_trace(trace)

    x_range, y_range, *_ = _compute_axis_ranges(
        canvas_width,
        canvas_height,
        *((spec["trial_fix"], "x", "y") for spec in trial_specs),
        *((spec["raw_gaze"], "x", "y") for spec in trial_specs),
        word_frames=[
            spec["trial_words"] for spec in trial_specs if not spec["trial_words"].empty
        ],
        fit_to_monitor=fit_to_monitor,
    )

    # Both trials are overlaid on one shared canvas, so one display scale sizes
    # every word label true-to-scale (geometry is identical across the readings).
    fitted_w, fitted_h = _fit_display_size(
        canvas_width, canvas_height, x_range, y_range, spatial_axes=True
    )
    overlay_scale = _display_scale(x_range, y_range, fitted_w, fitted_h)

    # A categorical column or colour-by-line: one category→colour mapping for
    # both readings (see the split layouts).
    category_colors, category_legend = _shared_category_colors(
        [
            _fixation_category_labels(
                spec["trial_fix"], spec["trial_words"], color_by, color_by_line
            )
            for spec in trial_specs
        ],
        avoid=[spec["color"] for spec in trial_specs],
    )
    category_label = "line" if (color_by_line or color_by == "line") else color_by
    legend_on = show_legend or bool(category_legend)

    draws_stimulus = _compare_stimulus_sides(settings.compare_stimulus)
    # Both readings' samples before either scanpath, so neither cloud covers the
    # other reading's fixations.
    for spec in trial_specs:
        _add_comparison_raw_gaze_trace(
            fig,
            spec["raw_gaze"],
            spec["display_name"],
            spec["raw_gaze_color"],
            settings,
        )
    for _idx, spec in enumerate(trial_specs):
        _add_comparison_fixation_trace(
            fig,
            spec["trial_fix"],
            spec["display_name"],
            spec["style"],
            font_settings,
            show_fixations=show_fixations,
            show_saccades=show_saccades,
            show_saccade_arrows=show_saccade_arrows,
            show_order=show_order,
            order_font_size=order_font_size,
            show_legend=show_legend,
            color_by=color_by,
            colorscale=fixation_colorscale,
            color_range=metric_range,
            # One shared colorbar (on the first scanpath only) for the metric.
            show_colorbar=show_colorbars and _idx == 0,
            colorbar_style=cb_style,
            fixation_symbol=fixation_symbol,
            fixation_hover_fields=fixation_hover_fields,
            trial_words=spec["trial_words"],
            **_comparison_filters(spec["style"], settings),
            duration_scale=_settings_size_scale(settings),
            category_colors=category_colors[_idx],
        )
        if show_words and draws_stimulus[_idx]:
            existing = list(fig.layout.shapes) if fig.layout.shapes else []
            fig.update_layout(
                shapes=existing
                + build_word_boxes(
                    spec["trial_words"],
                    color=spec["box_color"],
                    fill_color=spec["box_fill_color"],
                    fill_opacity=settings.word_box_fill_opacity,
                    line_opacity=settings.word_box_line_opacity,
                )
            )
        if show_word_labels and draws_stimulus[_idx]:
            _add_word_label_trace(
                fig,
                spec["trial_words"],
                _word_label_font_px(
                    spec["trial_words"],
                    scale=overlay_scale,
                    line_spacing=line_spacing,
                    manual_font_px=base_font_size,
                    scale_text_to_boxes=scale_text_to_boxes,
                ),
                font_settings["family"],
                highlight_column=highlight_column,
                text_color=text_color,
                highlight_text_color=highlight_text_color,
                word_hover_measure=word_hover_measure,
                word_hover_fields=word_hover_fields,
            )

    _add_category_legend(fig, category_legend, category_label or "")

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

    # fitted_w / fitted_h were computed up front (so the label scale matched).
    # The title + top A/B legend get reserved space above the plot so they don't
    # shrink the equal-aspect plot region (same fix as make_scanpath_figure). With
    # the legend hidden (CMP-2 default) a slimmer band still fits the title.
    # The top band is now only needed for the optional A/B legend (the "Overlay
    # comparison" title was removed); reclaim it fully when the legend is hidden.
    top_px = _OVERLAY_TOP_PX if legend_on else 0
    # A horizontal colorbar (VIZ-23) sits below the plot, so reserve a band for
    # it; a vertical one keeps today's layout (it hangs off the right edge).
    bottom_px = (
        _COLORBAR_BOTTOM_PX
        if _colorbar_reserves(
            (
                _comparison_metric_colorbar(fixations, color_by, show_colorbars),
                colorbar_orientation,
            ),
            (
                bool(show_heatmap and show_heatmap_colorbar and any(heatmap_maps)),
                heat_cb_style["orientation"],
            ),
        )["colorbar_below"]
        else 0
    )
    grid_left = _GRID_LEFT_RESERVE_PX if show_coordinate_grid else 0
    grid_bottom = _GRID_BOTTOM_RESERVE_PX if show_coordinate_grid else 0
    xaxis = dict(
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        title=None,
        range=x_range,
        constrain="domain",
        automargin=False,
    )
    yaxis = dict(
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        title=None,
        range=y_range,
        constrain="domain",
        scaleanchor="x",
        scaleratio=1,
        automargin=False,
    )
    _apply_coordinate_grid_axes(
        xaxis,
        yaxis,
        show=show_coordinate_grid,
        spacing=coordinate_grid_spacing,
        x_range=x_range,
        y_range=y_range,
        rendered_width=fitted_w,
        rendered_height=fitted_h,
    )
    fig.update_layout(
        height=fitted_h + top_px + bottom_px + grid_bottom,
        width=fitted_w + grid_left,
        autosize=False,
        showlegend=legend_on,
        margin=dict(l=grid_left, r=0, t=top_px, b=bottom_px + grid_bottom),
        xaxis=xaxis,
        yaxis=yaxis,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=_compare_legend_font(base_font_size, font_family),
        ),
        template="plotly_white",
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        font=font_settings,
        shapes=shapes,
    )
    return fig


# =============================================================================
# Line figures: metric convergence, trial-index trend
# =============================================================================


def make_metric_convergence_figure(
    series: dict,
    *,
    x_title: str,
    y_title: str,
    title: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    height: int = 340,
    y_range: tuple[float, float] = (0.0, 1.02),
    highlight_x_range: tuple[float, float] | None = None,
) -> go.Figure:
    """Line chart of a metric (one line per model) over a cumulative x axis.

    ``series`` maps a model name to ``(xs, ys)``. Used by the Multiple Comparison
    tab to show how each model's NLD vs. the real scanpath evolves as more of the
    reading is included — either by cumulative fixation index or by elapsed time.
    Optionally shades ``highlight_x_range`` (e.g. the selected fixation window).
    """
    fig = go.Figure()
    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)
    has_data = False
    for i, (name, xy) in enumerate(series.items()):
        xs, ys = xy
        if not len(xs):
            continue
        has_data = True
        color = _QUALITATIVE_PALETTE[i % len(_QUALITATIVE_PALETTE)]
        fig.add_trace(
            go.Scatter(
                x=list(xs),
                y=list(ys),
                mode="lines+markers",
                name=str(name),
                line=dict(color=color, width=2),
                marker=dict(size=4, color=color),
                hovertemplate=(
                    f"{name}<br>{x_title}: %{{x}}<br>{y_title}: %{{y:.3f}}"
                    "<extra></extra>"
                ),
            )
        )
    if has_data and highlight_x_range is not None:
        lo, hi = highlight_x_range
        if hi > lo:
            fig.add_vrect(x0=lo, x1=hi, fillcolor="#6c757d", opacity=0.10, line_width=0)
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=55, r=10, t=40, b=45),
        template="plotly_white",
        font=font_settings,
        xaxis=dict(title=x_title),
        yaxis=dict(title=y_title, range=list(y_range)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title=title,
    )
    if not has_data:
        fig.add_annotation(
            text="No data", showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper"
        )
    return fig


def make_trend_figure(
    df: pd.DataFrame,
    *,
    x_col: str,
    y_label: str,
    title: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    height: int = 340,
    x_label: str | None = None,
) -> go.Figure:
    """Line+marker trend of ``value`` vs ``x_col`` with a ±SEM shaded band.

    ``df`` has columns ``[x_col, "value", "sem"]`` (see
    ``aggregation.metric_by_trial_index``). Used by the Per reader and Groups
    subtabs for the trial-index trend. ``x_label`` titles the x axis — the
    caller's name for what ``x_col`` holds (AN-9's frame calls it ``x``, which
    is no title); without one, ``x_col`` humanized.
    """
    if x_label is None:
        x_label = x_col.replace("_", " ").title()
    fig = go.Figure()
    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)
    if df is None or df.empty:
        fig.update_layout(
            template="plotly_white",
            font=font_settings,
            title=f"{title} (no data)",
            height=height,
        )
        return fig
    xs = df[x_col].to_numpy()
    ys = df["value"].to_numpy()
    sem = df["sem"].to_numpy() if "sem" in df.columns else np.zeros(len(xs))
    # ±SEM band (drawn first so the line sits on top).
    fig.add_trace(
        go.Scatter(
            x=np.concatenate([xs, xs[::-1]]),
            y=np.concatenate([ys + sem, (ys - sem)[::-1]]),
            fill="toself",
            fillcolor="rgba(31,119,180,0.15)",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            name="±SEM",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines+markers",
            line=dict(color=COMPARISON_PALETTE[0], width=2),
            marker=dict(size=5, color=COMPARISON_PALETTE[0]),
            name=y_label,
            hovertemplate=f"{x_label}: %{{x}}<br>{y_label}: %{{y:.1f}}<extra></extra>",
        )
    )
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=60, r=10, t=40, b=45),
        template="plotly_white",
        font=font_settings,
        xaxis=dict(title=x_label),
        yaxis=dict(title=y_label),
        title=title,
        showlegend=False,
    )
    return fig


# =============================================================================
# Analysis section figures (AN-1 … AN-22)
# =============================================================================
#
# Builders for the question-oriented Corpus Analysis subtabs. Each takes a tidy
# frame from ``aggregation.py`` plus the usual ``canvas_width`` / ``base_font_size``
# / ``font_family`` and returns a ``go.Figure``. Empty input → a "(no data)"
# placeholder, matching ``make_trend_figure``.

_DIVERGING_COLORSCALE = "RdBu"


def _hex_to_rgba(color: str, alpha: float) -> str:
    """``#rrggbb`` → ``rgba(r,g,b,alpha)`` for translucent spread bands. Passes
    through non-hex colours (already ``rgb(...)`` / named) by wrapping opacity in
    is impossible, so it returns a sensible grey fallback for those."""
    c = str(color).lstrip("#")
    if len(c) == 6:
        try:
            r, g, b = (int(c[i : i + 2], 16) for i in (0, 2, 4))
            return f"rgba({r},{g},{b},{alpha})"
        except ValueError:
            pass
    return f"rgba(120,120,120,{alpha})"


def _no_data_figure(title: str, *, font_family: str, base_font_size: int, height=340):
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title=f"{title} (no data)",
        height=height,
    )
    return fig


def make_small_multiples_figure(
    per_reader: pd.DataFrame,
    *,
    measure_label: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    cohort: pd.DataFrame | None = None,
    max_panels: int = 12,
    panel_height: int = 110,
) -> go.Figure:
    """Stacked per-reader word profiles — one panel per participant (AN-1).

    ``per_reader`` is tidy ``[participant_id, word_id, value]`` (see
    ``aggregation.per_reader_word_measure``); panels share the X (reading order).
    ``cohort`` (``[word_id, value]``) draws a faint cohort-mean overlay in each
    panel. Caps at ``max_panels`` readers and titles the overflow (no silent cut).
    """
    from plotly.subplots import make_subplots

    if per_reader is None or per_reader.empty:
        return _no_data_figure(
            f"{measure_label} per reader",
            font_family=font_family,
            base_font_size=base_font_size,
        )
    readers = list(pd.unique(per_reader["participant_id"]))
    n_total = len(readers)
    readers = readers[:max_panels]
    n = len(readers)
    # Each panel's title (the reader id) sits in the gap above it, so the gap
    # is sized in pixels from the font rather than as a fixed fraction of the
    # figure: a fraction shrinks with few panels and the title lands on the
    # panel above's lowest tick row.
    title_gap_px = round(base_font_size * 2.2) + 6
    plot_px = panel_height * n + title_gap_px * (n - 1)
    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=title_gap_px / plot_px if n > 1 else 0.0,
        subplot_titles=[str(r) for r in readers],
    )
    cohort_xy = None
    if cohort is not None and not cohort.empty:
        c = cohort.sort_values("word_id")
        cohort_xy = (c["word_id"].to_numpy(), c["value"].to_numpy())
    for i, reader in enumerate(readers, start=1):
        sub = per_reader[per_reader["participant_id"] == reader].sort_values("word_id")
        if cohort_xy is not None:
            fig.add_trace(
                go.Scatter(
                    x=cohort_xy[0],
                    y=cohort_xy[1],
                    mode="lines",
                    line=dict(color="rgba(120,120,120,0.45)", width=1.2, dash="dot"),
                    name="Cohort mean",
                    showlegend=(i == 1),
                    hoverinfo="skip",
                ),
                row=i,
                col=1,
            )
        fig.add_trace(
            go.Scatter(
                x=sub["word_id"].to_numpy(),
                y=sub["value"].to_numpy(),
                mode="lines+markers",
                line=dict(color=COMPARISON_PALETTE[0], width=1.5),
                marker=dict(size=3, color=COMPARISON_PALETTE[0]),
                name=str(reader),
                showlegend=False,
                customdata=sub["word_text"].to_numpy() if "word_text" in sub else None,
                hovertemplate=(
                    "word %{x}"
                    + ("  %{customdata}" if "word_text" in sub else "")
                    + f"<br>{measure_label}: %{{y:.1f}}<extra></extra>"
                ),
            ),
            row=i,
            col=1,
        )
    title = f"{measure_label} per reader (word profile)"
    if n_total > n:
        title += f" — showing {n} of {n_total} readers"
    margin_top = 50 + title_gap_px
    margin_bottom = 40
    fig.update_layout(
        height=plot_px + margin_top + margin_bottom,
        width=canvas_width,
        autosize=False,
        margin=dict(l=55, r=10, t=margin_top, b=margin_bottom),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title=title,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
    )
    fig.update_xaxes(title_text="Word (reading order)", row=n, col=1)
    return fig


def make_word_matrix_heatmap(
    df: pd.DataFrame,
    *,
    row_col: str,
    measure_label: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    value_col: str = "value",
    colorscale: str = DEFAULT_HEATMAP_COLORSCALE,
    row_order: Iterable | None = None,
    height: int | None = None,
    row_label: str | None = None,
) -> go.Figure:
    """Word × {reader|group} heatmap (AN-2, AN-22).

    ``df`` is long ``[row_col, word_id, value_col]``; rows become Y, ``word_id``
    X, ``value_col`` the color. ``row_order`` pins the row order (e.g. Group A
    above Group B). Bright columns = universally hard words; bright rows = a
    uniformly slow reader. ``row_label`` names the rows (the dataset's own name
    for ``row_col``, DATA-66); without one, ``row_col`` humanized.
    """
    if row_label is None:
        row_label = _humanize_column(row_col)
    if df is None or df.empty:
        return _no_data_figure(
            f"{measure_label} by {row_label} × word",
            font_family=font_family,
            base_font_size=base_font_size,
        )
    matrix = df.pivot_table(
        index=row_col, columns="word_id", values=value_col, aggfunc="mean"
    )
    if row_order is not None:
        keep = [r for r in row_order if r in matrix.index]
        matrix = matrix.reindex(keep)
    fig = go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(),
            x=[int(c) if float(c).is_integer() else c for c in matrix.columns],
            y=[str(r) for r in matrix.index],
            colorscale=colorscale,
            colorbar=dict(title=measure_label),
            hovertemplate="word %{x}<br>%{y}<br>"
            + measure_label
            + ": %{z:.1f}<extra></extra>",
        )
    )
    n_rows = max(len(matrix.index), 1)
    fig.update_layout(
        height=height or min(900, max(220, 26 * n_rows + 120)),
        width=canvas_width,
        autosize=False,
        margin=dict(l=120, r=10, t=50, b=45),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title=f"{measure_label} — {row_label} × word",
        xaxis=dict(title="Word (reading order)"),
        yaxis=dict(title=row_label, autorange="reversed"),
    )
    return fig


def make_word_profile_figure(
    profiles: dict,
    *,
    measure_label: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    spread_label: str = "SD",
    colors: Sequence[str] | None = None,
    height: int = 380,
) -> go.Figure:
    """Cohort word profile(s): mean line + shaded spread band (AN-3 / AN-15).

    ``profiles`` maps a label → ``[word_id, value, lo, hi]`` (see
    ``aggregation.cohort_word_profile``). One entry draws the "average reader of
    this text" with uncertainty; several overlay (e.g. two groups).
    """
    entries = [
        (str(k), v)
        for k, v in (profiles or {}).items()
        if v is not None and not v.empty
    ]
    if not entries:
        return _no_data_figure(
            f"{measure_label} word profile",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    fig = go.Figure()
    single = len(entries) == 1
    for i, (label, prof) in enumerate(entries):
        prof = prof.sort_values("word_id")
        xs = prof["word_id"].to_numpy()
        ys = prof["value"].to_numpy()
        color_choices = tuple(colors or COMPARISON_PALETTE)
        color = color_choices[i % len(color_choices)]
        rgba = _hex_to_rgba(color, 0.15)
        if {"lo", "hi"} <= set(prof.columns):
            lo = prof["lo"].to_numpy()
            hi = prof["hi"].to_numpy()
            fig.add_trace(
                go.Scatter(
                    x=np.concatenate([xs, xs[::-1]]),
                    y=np.concatenate([hi, lo[::-1]]),
                    fill="toself",
                    fillcolor=rgba,
                    line=dict(width=0),
                    hoverinfo="skip",
                    showlegend=False,
                    name=f"{label} {spread_label}",
                )
            )
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                line=dict(color=color, width=2),
                marker=dict(size=4, color=color),
                name=label,
                showlegend=not single,
                customdata=prof["word_text"].to_numpy()
                if "word_text" in prof
                else None,
                hovertemplate=(
                    "word %{x}"
                    + ("  %{customdata}" if "word_text" in prof else "")
                    + f"<br>{measure_label}: %{{y:.1f}}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=60, r=10, t=45, b=45),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title=f"{measure_label} by word — cohort mean ± {spread_label}",
        xaxis=dict(title="Word (reading order)"),
        yaxis=dict(title=measure_label),
        showlegend=not single,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def make_feature_scatter_figure(
    df: pd.DataFrame,
    *,
    measure_label: str,
    feature_label: str,
    categorical: bool,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    height: int = 400,
) -> go.Figure:
    """Per-word measure vs a bundled linguistic feature (AN-5).

    Numeric feature → scatter + OLS trend line (with Pearson r in the title);
    categorical feature (POS) → one box per category.
    """
    if df is None or df.empty or "feature" not in df.columns:
        return _no_data_figure(
            f"{measure_label} vs {feature_label}",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    font_settings = dict(family=font_family or FONT_FAMILY, size=base_font_size)
    fig = go.Figure()
    if categorical:
        cats = sorted(df["feature"].dropna().astype(str).unique())
        for i, cat in enumerate(cats):
            vals = df.loc[df["feature"].astype(str) == cat, "value"].dropna().to_numpy()
            if vals.size:
                fig.add_trace(
                    go.Box(
                        y=vals,
                        name=cat,
                        boxpoints="outliers",
                        marker_color=_QUALITATIVE_PALETTE[
                            i % len(_QUALITATIVE_PALETTE)
                        ],
                    )
                )
        fig.update_layout(
            xaxis=dict(title=feature_label),
            yaxis=dict(title=measure_label),
            showlegend=False,
        )
        title = f"{measure_label} by {feature_label}"
    else:
        x = pd.to_numeric(df["feature"], errors="coerce").to_numpy()
        y = pd.to_numeric(df["value"], errors="coerce").to_numpy()
        ok = ~(np.isnan(x) | np.isnan(y))
        x, y = x[ok], y[ok]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers",
                marker=dict(size=6, color=COMPARISON_PALETTE[0], opacity=0.6),
                name="words",
                customdata=df.loc[ok, "word_text"].to_numpy()
                if "word_text" in df
                else None,
                hovertemplate=(
                    f"{feature_label}: %{{x:.2f}}<br>{measure_label}: %{{y:.1f}}"
                    + ("<br>%{customdata}" if "word_text" in df else "")
                    + "<extra></extra>"
                ),
            )
        )
        r_txt = ""
        if x.size >= 2 and np.std(x) > 0:
            slope, intercept = np.polyfit(x, y, 1)
            xs = np.array([x.min(), x.max()])
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=slope * xs + intercept,
                    mode="lines",
                    line=dict(color=TRENDLINE_COLOR, width=2, dash="dash"),
                    name="trend",
                    hoverinfo="skip",
                )
            )
            r = float(np.corrcoef(x, y)[0, 1])
            r_txt = f"  (r = {r:.2f}, n = {x.size})"
        fig.update_layout(
            xaxis=dict(title=feature_label),
            yaxis=dict(title=measure_label),
            showlegend=False,
        )
        title = f"{measure_label} vs {feature_label}{r_txt}"
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=60, r=10, t=45, b=50),
        template="plotly_white",
        font=font_settings,
        title=title,
    )
    return fig


def make_word_rate_figure(
    df: pd.DataFrame,
    *,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    height: int = 360,
) -> go.Figure:
    """Skip / regression-in rate per word — lollipop bars (AN-6)."""
    if df is None or df.empty:
        return _no_data_figure(
            "Skip / regression rate per word",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    df = df.sort_values("word_id")
    xs = df["word_id"].to_numpy()
    fig = go.Figure()
    series = [
        ("Skip rate", "skip_rate", COMPARISON_PALETTE[0]),
        ("Regression-in rate", "regression_in_rate", COMPARISON_PALETTE[1]),
    ]
    for name, col, color in series:
        if col not in df.columns:
            continue
        ys = pd.to_numeric(df[col], errors="coerce").to_numpy()
        fig.add_trace(
            go.Bar(
                x=xs,
                y=ys,
                name=name,
                marker_color=color,
                opacity=0.8,
                hovertemplate="word %{x}<br>" + name + ": %{y:.0%}<extra></extra>",
            )
        )
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=55, r=10, t=45, b=45),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title="Skip / regression-in rate per word",
        xaxis=dict(title="Word (reading order)"),
        yaxis=dict(title="Rate", tickformat=".0%"),
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def make_distribution_figure(
    groups: dict,
    *,
    metric_label: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    kind: str = "violin",
    colors: Sequence[str] | None = None,
    height: int = 380,
) -> go.Figure:
    """Overlaid metric distributions — one violin/box per group (AN-7/14/18)."""
    arrays = [
        (str(name), np.asarray(arr, dtype="float64"))
        for name, arr in (groups or {}).items()
        if arr is not None and len(arr)
    ]
    if not arrays:
        return _no_data_figure(
            f"{metric_label} distribution",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    fig = go.Figure()
    for i, (name, arr) in enumerate(arrays):
        color_choices = tuple(colors or _QUALITATIVE_PALETTE)
        color = color_choices[i % len(color_choices)]
        if kind == "box":
            fig.add_trace(
                go.Box(
                    y=arr,
                    name=name,
                    marker_color=color,
                    boxmean=True,
                    boxpoints="outliers",
                )
            )
        else:
            fig.add_trace(
                go.Violin(
                    y=arr,
                    name=name,
                    line_color=color,
                    opacity=0.7,
                    box_visible=True,
                    meanline_visible=True,
                    points=False,
                )
            )
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=60, r=10, t=45, b=40),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title=f"{metric_label} distribution",
        yaxis=dict(title=metric_label),
        showlegend=False,
    )
    return fig


def make_density_scatter_figure(
    df: pd.DataFrame,
    *,
    x_col: str,
    y_col: str,
    x_label: str,
    y_label: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    height: int = 420,
) -> go.Figure:
    """2D density of two per-fixation measures — the oculomotor scatter (AN-10)."""
    if df is None or df.empty or not {x_col, y_col} <= set(df.columns):
        return _no_data_figure(
            f"{y_label} vs {x_label}",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    x = pd.to_numeric(df[x_col], errors="coerce").to_numpy()
    y = pd.to_numeric(df[y_col], errors="coerce").to_numpy()
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    fig = go.Figure(
        go.Histogram2d(
            x=x,
            y=y,
            colorscale=DEFAULT_HEATMAP_COLORSCALE,
            nbinsx=40,
            nbinsy=40,
            colorbar=dict(title="Fixations"),
            hovertemplate=f"{x_label}: %{{x}}<br>{y_label}: %{{y}}<br>count: %{{z}}<extra></extra>",
        )
    )
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=60, r=10, t=45, b=50),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title=f"{y_label} vs {x_label} (n = {x.size})",
        xaxis=dict(title=x_label),
        yaxis=dict(title=y_label),
    )
    return fig


def make_progression_figure(
    df: pd.DataFrame,
    *,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    height: int = 380,
) -> go.Figure:
    """Progressive vs regressive saccade counts per trial + regression share (AN-11)."""
    from plotly.subplots import make_subplots

    if df is None or df.empty:
        return _no_data_figure(
            "Progressive vs regressive saccades",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    df = df.copy()
    labels = [str(t) for t in df["trial_id"].to_numpy()]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=labels,
            y=df["progressive"].to_numpy(),
            name="Progressive",
            marker_color=COMPARISON_PALETTE[0],
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=df["regressive"].to_numpy(),
            name="Regressive",
            marker_color=COMPARISON_PALETTE[1],
        ),
        secondary_y=False,
    )
    if "regression_share" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=df["regression_share"].to_numpy(),
                name="Regression share",
                mode="lines+markers",
                line=dict(color="#555", width=2),
                marker=dict(size=5),
            ),
            secondary_y=True,
        )
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=55, r=55, t=45, b=80),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title="Progressive vs regressive saccades per trial",
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title_text="Trial", tickangle=-40)
    fig.update_yaxes(title_text="Saccade count", secondary_y=False)
    fig.update_yaxes(
        title_text="Regression share", tickformat=".0%", secondary_y=True, range=[0, 1]
    )
    return fig


def make_paired_bars_figure(
    df: pd.DataFrame,
    *,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    height: int = 380,
) -> go.Figure:
    """Side-by-side group-mean bars per measure with error bars (AN-20).

    ``df`` is ``[measure, group, value, err_lo, err_hi]`` (see
    ``aggregation.paired_group_summary``). One subplot per measure so differing
    units keep their own scale.
    """
    from plotly.subplots import make_subplots

    if df is None or df.empty:
        return _no_data_figure(
            "Group means",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    measures = list(dict.fromkeys(df["measure"]))
    groups = list(dict.fromkeys(df["group"]))
    fig = make_subplots(
        rows=1, cols=len(measures), subplot_titles=measures, horizontal_spacing=0.08
    )
    for gi, group in enumerate(groups):
        color = COMPARISON_PALETTE[gi % len(COMPARISON_PALETTE)]
        for mi, measure in enumerate(measures, start=1):
            sub = df[(df["measure"] == measure) & (df["group"] == group)]
            if sub.empty:
                continue
            row = sub.iloc[0]
            fig.add_trace(
                go.Bar(
                    x=[group],
                    y=[row["value"]],
                    name=group,
                    marker_color=color,
                    legendgroup=group,
                    showlegend=(mi == 1),
                    error_y=dict(
                        type="data",
                        symmetric=False,
                        array=[row.get("err_hi", 0)],
                        arrayminus=[row.get("err_lo", 0)],
                    ),
                    hovertemplate=f"{group}<br>{measure}: %{{y:.2f}}<extra></extra>",
                ),
                row=1,
                col=mi,
            )
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=55, r=10, t=55, b=40),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title="Group means per measure",
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1),
        barmode="group",
    )
    return fig


def make_landing_curve_figure(
    values: np.ndarray,
    *,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    as_fraction: bool = True,
    height: int = 360,
) -> go.Figure:
    """Preferred-viewing-location curve — landing-position histogram (AN-12).

    ``values`` come from ``aggregation.landing_positions``: fractions of the
    experiment's word box, unclipped (BUG-83), so a landing assigned from beside
    the box shows as a bar outside 0–1 instead of a spike on the edge.
    """
    arr = np.asarray(values, dtype="float64")
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return _no_data_figure(
            "Landing position within words",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    nbins = 20 if as_fraction else 30
    fig = go.Figure(
        go.Histogram(
            x=arr,
            nbinsx=nbins,
            marker_color=COMPARISON_PALETTE[0],
            marker_line=dict(color="white", width=0.4),
            hovertemplate="landing %{x}<br>count: %{y}<extra></extra>",
        )
    )
    x_title = (
        "Landing position within the word's interest area (0 = start, 1 = end)"
        if as_fraction
        else "Landing distance from word start (px)"
    )
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=55, r=10, t=45, b=50),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title=f"Landing-position curve (n = {arr.size})",
        xaxis=dict(title=x_title),
        yaxis=dict(title="Count"),
    )
    return fig


def make_difference_profile_figure(
    df: pd.DataFrame,
    *,
    measure_label: str,
    label_a: str = "Group A",
    label_b: str = "Group B",
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    colors: Sequence[str] | None = None,
    height: int = 380,
) -> go.Figure:
    """Per-word A−B difference profile, diverging color + zero line (AN-19)."""
    if df is None or df.empty or "diff" not in df.columns:
        return _no_data_figure(
            f"{measure_label} difference by word",
            font_family=font_family,
            base_font_size=base_font_size,
            height=height,
        )
    df = df.sort_values("word_id")
    xs = df["word_id"].to_numpy()
    diffs = pd.to_numeric(df["diff"], errors="coerce").to_numpy()
    vmax = np.nanmax(np.abs(diffs)) if np.isfinite(diffs).any() else 1.0
    vmax = vmax if vmax > 0 else 1.0
    difference_colors = tuple(colors or (COMPARISON_PALETTE[1], COMPARISON_PALETTE[0]))
    colorscale = [
        [0.0, difference_colors[1 % len(difference_colors)]],
        [0.5, "#f7f7f7"],
        [1.0, difference_colors[0]],
    ]
    fig = go.Figure(
        go.Bar(
            x=xs,
            y=diffs,
            marker=dict(
                color=diffs,
                colorscale=colorscale,
                cmin=-vmax,
                cmax=vmax,
                colorbar=dict(title=f"{label_a} − {label_b}"),
            ),
            customdata=df["word_text"].to_numpy() if "word_text" in df else None,
            hovertemplate=(
                "word %{x}"
                + ("  %{customdata}" if "word_text" in df else "")
                + f"<br>Δ {measure_label}: %{{y:.1f}}<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=0, line=dict(color="#333", width=1))
    fig.update_layout(
        height=height,
        width=canvas_width,
        autosize=False,
        margin=dict(l=60, r=10, t=50, b=45),
        template="plotly_white",
        font=dict(family=font_family or FONT_FAMILY, size=base_font_size),
        title=f"{measure_label}: {label_a} − {label_b} by word",
        xaxis=dict(title="Word (reading order)"),
        yaxis=dict(title=f"Δ {measure_label}"),
    )
    return fig


def _setting_names(excluded: Iterable[str]) -> tuple[str, ...]:
    excluded = set(excluded)
    return tuple(
        field.name for field in fields(FigureSettings) if field.name not in excluded
    )


def _resolve_figure_settings(
    settings: FigureSettings | Mapping[str, Any] | None,
    overrides: Mapping[str, Any],
    *,
    legacy_defaults: Mapping[str, Any] | None = None,
) -> FigureSettings:
    """Resolve a settings object while preserving old builder-only defaults."""
    if settings is None and legacy_defaults:
        return FigureSettings.from_mapping({**legacy_defaults, **overrides})
    return FigureSettings.from_mapping(settings, **dict(overrides))


STATIC_FIGURE_OPTIONS = _setting_names(
    {
        "playback_speed",
        "label_a",
        "label_b",
        "show_legend",
        "autoplay",
        "anim_grid_step_ms",
        "anim_max_frames",
        "trial_labels",
        "layout",
        "style_a",
        "style_b",
        # CMP-8 §4 — B-side geometry, read only by the split comparison layouts.
        "canvas_b",
        "background_image_b",
        "background_image_size_b",
        "background_image_origin_b",
        # CMP-11 — the static builder draws one trial, so it has no "whose
        # stimulus?" question to answer. The *animation* builder does read it (a
        # dual co-animation takes `words_b`), so it is NOT excluded there.
        "compare_stimulus",
        # CMP-24 — B's flags in a co-animation; one trial has no B.
        "fixation_flags_b",
        # DATA-66 — names, not an option: read by `_labelled_columns`.
        "column_labels",
    }
)
#: What `make_comparison_figure` accepts (CMP-9). Only the animation-only fields
#: are excluded — this is a typo-catcher for `api.compare_scanpaths`, not a
#: semantic filter, so it still admits settings the comparison builders ignore.
#: Which settings actually reach a comparison figure is the table in
#: `scanpath_studio/CLAUDE.md` → *Which viz settings apply in which render path*.
COMPARISON_FIGURE_OPTIONS = _setting_names(
    {
        "playback_speed",
        "label_a",
        "label_b",
        "autoplay",
        "anim_grid_step_ms",
        "anim_max_frames",
        # CMP-24 — a comparison reads B's filters off `style_b` instead.
        "fixation_flags_b",
        # DATA-66 — names, not an option: read by `_labelled_columns`.
        "column_labels",
    }
)
ANIMATION_FIGURE_OPTIONS = _setting_names(
    {
        "x_field",
        "y_field",
        "show_fixations",
        "show_heatmap",
        "heatmap_metric",
        "heatmap_style",
        "heatmap_norm",
        "heatmap_sigma_px",
        "heatmap_range",
        "heatmap_colorscale",
        "show_raw_gaze",
        "critical_span_style",
        "saccade_color_mode",
        "saccade_class_colors",
        "saccade_type_legend",
        "saccade_classes",
        "saccade_render_mode",
        "fixation_snap_to_word",
        "span_border_color",
        "word_heatmap_col",
        "word_heatmap_title",
        "show_connectors",
        "connector_y",
        "illustration_reasons",
        "trial_labels",
        "layout",
        # CMP-8 §4 — B-side geometry, read only by the split comparison layouts.
        "canvas_b",
        "background_image_b",
        "background_image_size_b",
        "background_image_origin_b",
        # DATA-66 — names, not an option: read by `_labelled_columns`.
        "column_labels",
    }
)


def make_scanpath_figure(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    settings: FigureSettings | Mapping[str, Any] | None = None,
    raw_gaze: pd.DataFrame | None = None,
    **overrides: Any,
) -> go.Figure:
    """Build a static scanpath from one shared rendering-settings object.

    Keyword overrides remain useful for focused programmatic calls and tests;
    application code should pass ``settings=FigureSettings(...)`` so the same
    object can flow unchanged through UI, export, and headless surfaces.
    """
    resolved = _resolve_figure_settings(settings, overrides)
    fields_xy = (resolved.x_field, resolved.y_field)
    words = _finite_for_plotting(words, drop_on=_WORD_BOX_COLUMNS)
    fixations = _finite_for_plotting(fixations, fields_xy)
    raw_gaze = _finite_for_plotting(raw_gaze)
    with _labelled_columns(resolved.column_labels):
        fig = _render_scanpath_figure(
            words,
            fixations,
            settings=resolved,
            raw_gaze=raw_gaze,
        )
    _arrange_colorbars(fig)
    if resolved.show_fixations:
        _maybe_add_duration_key(fig, resolved, resolved.marker_size_range, fixations)
    return fig


def make_scanpath_animation(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    settings: FigureSettings | Mapping[str, Any] | None = None,
    fixations_b: pd.DataFrame | None = None,
    words_b: pd.DataFrame | None = None,
    **overrides: Any,
) -> go.Figure:
    """Build an animated replay from the shared rendering settings."""
    fig, _frame_step_ms = build_scanpath_replay(
        words,
        fixations,
        settings=settings,
        fixations_b=fixations_b,
        words_b=words_b,
        **overrides,
    )
    return fig


def build_scanpath_replay(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    settings: FigureSettings | Mapping[str, Any] | None = None,
    fixations_b: pd.DataFrame | None = None,
    words_b: pd.DataFrame | None = None,
    **overrides: Any,
) -> tuple[go.Figure, float]:
    """:func:`make_scanpath_animation`, returning the grid step with the figure.

    ``(figure, frame_step_ms)``: pass the step to :func:`set_replay_clock` to
    re-time the replay at another speed or autoplay without rebuilding a frame
    (PERF-15)."""
    resolved = _resolve_figure_settings(
        settings,
        overrides,
        legacy_defaults={
            "order_font_color": "#000000",
            "color_by": None,
            "fixation_color": None,
            "highlight_column": None,
            "word_hover_measure": None,
        },
    )
    words = _finite_for_plotting(words, drop_on=_WORD_BOX_COLUMNS)
    words_b = _finite_for_plotting(words_b, drop_on=_WORD_BOX_COLUMNS)
    fixations = _finite_for_plotting(fixations)
    fixations_b = _finite_for_plotting(fixations_b)
    with _labelled_columns(resolved.column_labels):
        fig, frame_step_ms = _render_scanpath_animation(
            words,
            fixations,
            settings=resolved,
            fixations_b=fixations_b,
            words_b=words_b,
        )
    size_range = replay_size_key_range(resolved, fixations, fixations_b)
    if size_range is not None:
        _maybe_add_duration_key(fig, resolved, size_range, fixations, fixations_b)
    return fig, frame_step_ms


def replay_size_key_range(
    settings: FigureSettings,
    fixations: pd.DataFrame | None,
    fixations_b: pd.DataFrame | None = None,
) -> tuple[int, int] | None:
    """The size range a replay's duration key draws, or ``None`` for no key.

    A lone replay's is the figure's ``marker_size_range``. A co-animation sizes
    each scanpath in its own style's range, and one key serves both only while
    those agree — as on the static comparison."""
    dual = all(f is not None and not f.empty for f in (fixations, fixations_b))
    if not dual:
        return tuple(settings.marker_size_range)
    ranges = {
        tuple(
            _comparison_scanpath_style(
                idx, style, default_marker_size_range=settings.marker_size_range
            )["marker_size_range"]
        )
        for idx, style in enumerate((settings.style_a, settings.style_b))
    }
    return ranges.pop() if len(ranges) == 1 else None


def _require_one_screen_per_reading(
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    readings: Sequence[tuple[str, str]],
) -> None:
    """Refuse a comparison reading that spans several screens.

    Every screen of a multipart trial is its own coordinate space, so one
    scanpath drawn from two of them joins its last fixation on one page to the
    first on the next — a saccade nobody made. Callers cut each reading to one
    screen first (`multipart.extract_part`); this is the guard that keeps a new
    caller from forgetting to.
    """
    for label, (participant, trial) in zip(("A", "B"), readings, strict=False):
        for frame in (fixations, words):
            if frame is None or frame.empty or SCREEN_ID not in frame.columns:
                continue
            rows = frame[
                (frame["participant_id"] == participant) & (frame["trial_id"] == trial)
            ]
            screens = rows[SCREEN_ID].dropna().astype(str).unique()
            if len(screens) > 1:
                shown = ", ".join(repr(value) for value in screens[:5])
                raise ValueError(
                    f"Scanpath {label} (participant={participant!r}, "
                    f"trial={trial!r}) spans {len(screens)} screens ({shown}). "
                    "Each screen is its own coordinate space, so a comparison "
                    "draws one screen per scanpath: cut each reading to one "
                    "screen first (multipart.extract_part, or "
                    "compare_scanpaths' screen= / screen_b=)."
                )


def make_comparison_figure(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    trial_a: tuple[str, str],
    trial_b: tuple[str, str],
    *,
    settings: FigureSettings | Mapping[str, Any] | None = None,
    raw_gaze: pd.DataFrame | None = None,
    **overrides: Any,
) -> go.Figure:
    """Build a two-scanpath comparison from the shared rendering settings.

    ``raw_gaze`` (VIZ-48) holds either reading's samples, keyed like ``words``
    and ``fixations``; with ``show_raw_gaze`` each reading's are drawn under its
    scanpath, in its colour.

    Each scanpath must be one screen: a frame holding several screens of one
    multipart reading raises ``ValueError`` rather than pooling coordinate
    spaces (and drawing saccades across page boundaries)."""
    _require_one_screen_per_reading(words, fixations, (trial_a, trial_b))
    resolved = _resolve_figure_settings(
        settings,
        overrides,
        legacy_defaults={
            "show_word_labels": False,
            "show_order": False,
            "order_font_size": None,
            "color_by": None,
            "highlight_column": None,
            "heatmap_metric": "duration_ms",
        },
    )
    words = _finite_for_plotting(words, drop_on=_WORD_BOX_COLUMNS)
    fixations = _finite_for_plotting(fixations)
    raw_gaze = _finite_for_plotting(raw_gaze)
    with _labelled_columns(resolved.column_labels):
        fig = _render_comparison_figure(
            words,
            fixations,
            trial_a,
            trial_b,
            settings=resolved,
            raw_gaze=raw_gaze,
        )
    _arrange_colorbars(fig)
    # One key serves both scanpaths only while they share a size range; with
    # per-scanpath ranges (Compare's own Size) one duration is two sizes.
    ranges = {
        tuple(
            _comparison_scanpath_style(
                idx, style, default_marker_size_range=resolved.marker_size_range
            )["marker_size_range"]
        )
        for idx, style in enumerate((resolved.style_a, resolved.style_b))
    }
    if resolved.show_fixations and len(ranges) == 1:
        _maybe_add_duration_key(fig, resolved, ranges.pop(), fixations)
    return fig


def _maybe_add_duration_key(
    fig: go.Figure,
    settings: FigureSettings,
    size_range: tuple[int, int],
    *fixation_frames: pd.DataFrame | None,
) -> None:
    """Add the duration-size key when the figure draws fixation markers on a
    fixed scale and the caller asked for it (``duration_size_legend``)."""
    if not settings.duration_size_legend or settings.marker_size_scale == "relative":
        return
    if not any(f is not None and not f.empty for f in fixation_frames):
        return
    _add_duration_size_key(
        fig,
        size_range,
        settings.marker_size_scale,
        settings.marker_duration_range,
        font_family=settings.font_family,
    )
