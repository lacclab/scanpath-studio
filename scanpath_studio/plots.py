"""Matplotlib figure builders for scanpath visualization.

These builders replace the former Plotly implementation; they return
``matplotlib.figure.Figure`` objects (and a :class:`ScanpathAnimation` for the
replay). The *pure* geometry/sizing/clock helpers (axis ranges, the true-to-scale
word-label font math, marker sizes, saccade arrows, the animation timeline) are
backend-agnostic and unchanged. The rendering primitives — exact-pixel figure
scaffolding and the screen-px↔point unit conversions that keep the word labels
matched to their boxes — live in :mod:`scanpath_studio.mpl_render`.

True-to-scale text, recap: word labels are sized in *data* px so each glyph fills
the same physical fraction of its word box, then converted to the figure's screen
px via the data→screen ``scale``. The equal-aspect plot region is pinned to an
exact ``fitted_w × fitted_h`` pixel box (``ax.set_aspect('equal')`` + the fitted
size), and colorbars/legends/animation controls are reserved *outside* that box
so they never shrink it — the matplotlib analog of Plotly's
``automargin=False`` + reserved margins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Tuple

import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from . import mpl_render as mr
from .constants import (
    CANVAS_PAD_FRACTION,
    CANVAS_PAD_MIN_PX,
    COMPARISON_PALETTE,
    CURRENT_FIX_COLOR,
    CURRENT_FIX_OUTLINE,
    DEFAULT_FIXATION_COLORSCALE,
    DEFAULT_HEATMAP_COLORSCALE,
    DEFAULT_LINE_SPACING,
    DEFAULT_MARKER_SIZE_RANGE,
    FIX_MARKER_OUTLINE,
    FONT_FAMILY,
    HIGHLIGHTED_TEXT_COLOR,
    HOLLOW_OUTLINE_WIDTH,
    OUT_OF_TEXT_COLOR,
    SACCADE_COLOR,
    WORD_BOX_COLOR,
    WORD_LABEL_COLOR,
)

COLORBAR_LEN_FRACTION = 0.33

# Draw-order (zorder) for the layered spatial scene, lowest first. Mirrors the
# Plotly layer order (heatmap below, boxes, labels, saccades, fixations, order
# numbers, out-of-text, critical-span border, canvas border on top).
_Z_HEATMAP = 0.5
_Z_BOX = 1.0
_Z_LABEL = 1.5
_Z_SACCADE = 2.0
_Z_ARROW = 2.3
_Z_RAW = 2.5
_Z_FIX = 3.0
_Z_OOT = 3.5
_Z_ORDER = 4.0
_Z_CURRENT = 4.5
_Z_CRITICAL = 5.0
_Z_BORDER = 6.0


# ---------------------------------------------------------------------------
# Pure geometry / sizing helpers (backend-agnostic — unchanged across the
# Plotly→matplotlib migration; the true-to-scale text contract lives here).
# ---------------------------------------------------------------------------
def _compute_axis_ranges(
    canvas_width: int,
    canvas_height: int,
    *frames_with_xy: Tuple[Optional[pd.DataFrame], str, str],
    word_frames: Iterable[pd.DataFrame] = (),
) -> Tuple[
    list, list, Optional[float], Optional[float], Optional[float], Optional[float]
]:
    """Compute padded x/y ranges from any number of (frame, x_col, y_col) tuples.

    word_frames contribute box-extent bounds: x, x+width and y, y+height.
    Falls back to (0..canvas_width, canvas_height..0) when there's no data.
    Returns: x_range, y_range (y inverted), and the unpadded mins/maxs.
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

    x_span = max(x_max - x_min, 1.0)
    y_span = max(y_max - y_min, 1.0)
    pad_x = max(CANVAS_PAD_MIN_PX, CANVAS_PAD_FRACTION * x_span)
    pad_y = max(CANVAS_PAD_MIN_PX, CANVAS_PAD_FRACTION * y_span)
    x_range = [x_min - pad_x, x_max + pad_x]
    y_range = [y_max + pad_y, y_min - pad_y]
    return x_range, y_range, x_min, x_max, y_min, y_max


# Cap the *fixed* render size so the true-to-scale plot (rendered at exactly
# these pixels and uniformly CSS-scaled to the column in the app) fits a typical
# research display without horizontal scrolling. Aspect ratio is preserved when
# shrinking — both dims scale together, so boxes/text/fixations keep one scale.
_DISPLAY_MAX_HEIGHT = 650
_DISPLAY_MAX_WIDTH = 900


def _fit_display_size(
    canvas_width: int,
    canvas_height: int,
    x_range: list,
    y_range: list,
    spatial_axes: bool,
) -> Tuple[int, int]:
    """Return the (width, height) px for the equal-aspect plot region.

    The plot region is matched to the data aspect ratio (so equal aspect leaves
    no large blank strips) and clamped so the whole plot fits one viewport.
    Falls back to (canvas_w, canvas_h) when axes aren't spatial or degenerate.
    """
    if not spatial_axes:
        return canvas_width, canvas_height
    x_span = x_range[1] - x_range[0]
    y_span = y_range[0] - y_range[1]  # y_range is inverted [y_max, y_min]
    if x_span <= 0 or y_span <= 0:
        return canvas_width, canvas_height
    aspect = x_span / y_span
    w, h = canvas_width, int(round(canvas_width / aspect))
    if h > _DISPLAY_MAX_HEIGHT:
        h = _DISPLAY_MAX_HEIGHT
        w = int(round(h * aspect))
    if w > _DISPLAY_MAX_WIDTH:
        w = _DISPLAY_MAX_WIDTH
        h = int(round(w / aspect))
    return max(w, 100), max(h, 100)


# Extra figure size (px) reserved OUTSIDE the equal-aspect plot region for a
# right-side colorbar or a top legend, so they never shrink the plot (which is
# sized for the true-to-scale labels — the "colorbar shrinks the plot" bug).
_COLORBAR_RESERVE_PX = 160
_LEGEND_RESERVE_PX = 60
# Top reserve for the overlay-comparison figure's title + A/B legend.
_OVERLAY_TOP_PX = 64

_MIN_LABEL_PX = 1.0
# Advance-width / em of a typical monospaced font (DejaVu Sans Mono ≈ 0.6).
_MONO_ASPECT = 0.6
_WIDTH_FIT_MARGIN = 0.92  # leave a sliver of horizontal padding inside each box


def _width_fit_font(words: pd.DataFrame) -> Optional[float]:
    """Largest font (data px) at which every word still fits its box width.

    ``box_width / n_chars`` is the per-character advance; dividing by the
    monospace aspect recovers the em. The tightest words bind, so we take a low
    quantile (robust to one odd box). None when there's no text/width.
    """
    if "width" not in words.columns or "text" not in words.columns:
        return None
    w = pd.to_numeric(words["width"], errors="coerce")
    n = words["text"].astype(str).str.len().clip(lower=1)
    per_char = (w / n).replace([np.inf, -np.inf], np.nan).dropna()
    if per_char.empty:
        return None
    tight = float(per_char.quantile(0.05))
    return tight / _MONO_ASPECT * _WIDTH_FIT_MARGIN if tight > 0 else None


def _display_scale(x_range: list, y_range: list, fitted_w: int, fitted_h: int) -> float:
    """Screen px per data unit for a fixed-size, equal-aspect spatial plot.

    With equal aspect the x and y mappings are identical; we take the min so
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

    ``scale_text_to_boxes`` (default): one line of text fills ``1 / line_spacing``
    of the line pitch (the median word-box height), also capped so the longest
    words fit their box width (:func:`_width_fit_font`); the smaller wins.
    Otherwise ``manual_font_px`` is treated as the real monitor font and scaled
    the same way. The returned value is multiplied by ``scale`` (screen px per
    data unit); the caller converts px→points via :func:`mpl_render.px_to_pt`.
    """
    font_data_px = float(manual_font_px)
    if scale_text_to_boxes and not words.empty and "height" in words.columns:
        box_h = float(pd.to_numeric(words["height"], errors="coerce").median())
        height_fit = box_h / line_spacing if (box_h > 0 and line_spacing > 0) else None
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
    color_data: Optional[pd.Series], is_numeric_color: bool
) -> Tuple[object, list]:
    """Return (marker_color, category_legend) for the fixation scatter.

    - Numeric color_data is passed straight through (mapped via colorscale).
    - Categorical color_data maps to a discrete palette; the returned legend is a
      list of (category, hex) pairs the caller renders as legend proxies.
    - Missing color_data falls back to the first palette color.
    """
    if color_data is None:
        return _QUALITATIVE_PALETTE[0], []
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


def _compute_marker_sizes(
    durations: pd.Series, size_range: Tuple[int, int] = DEFAULT_MARKER_SIZE_RANGE
) -> np.ndarray:
    """Map fixation durations to marker *pixel diameters* by linear interpolation."""
    durations = pd.to_numeric(durations, errors="coerce").fillna(0)
    d_min, d_max = float(durations.min()), float(durations.max())
    min_size, max_size = size_range
    if d_max - d_min > 0:
        return np.interp(durations, (d_min, d_max), (min_size, max_size))
    return np.full(len(durations), (min_size + max_size) / 2)


def _saccade_segments(
    fix_df: pd.DataFrame, x_col: str, y_col: str
) -> Tuple[list, list]:
    """Return concatenated x/y arrays separated by None for a single saccade trace.

    Kept for backward compatibility / callers that want the flat form; the
    matplotlib builders use :func:`_saccade_segment_pairs` (a LineCollection).
    """
    if len(fix_df) < 2:
        return [], []
    ordered = fix_df.sort_values("timestamp_ms")
    xs: list = []
    ys: list = []
    x_vals = ordered[x_col].tolist()
    y_vals = ordered[y_col].tolist()
    for i in range(len(ordered) - 1):
        xs.extend([x_vals[i], x_vals[i + 1], None])
        ys.extend([y_vals[i], y_vals[i + 1], None])
    return xs, ys


def _saccade_segment_pairs(fix_df: pd.DataFrame, x_col: str, y_col: str) -> list:
    """Return ``[[(x0,y0),(x1,y1)], …]`` segments for one ``LineCollection``.

    Drawing every saccade as a single ``LineCollection`` (rather than N lines)
    keeps the artist count constant — the matplotlib analog of the old
    one-trace-for-all-saccades perf contract.
    """
    if len(fix_df) < 2:
        return []
    ordered = fix_df.sort_values("timestamp_ms")
    xs = ordered[x_col].tolist()
    ys = ordered[y_col].tolist()
    return [[(xs[i], ys[i]), (xs[i + 1], ys[i + 1])] for i in range(len(ordered) - 1)]


# Saccades shorter than this fraction of the fixation-extent diagonal get no
# direction arrow — their heading is sub-pixel noise (refixations on one word).
_ARROW_MIN_LEN_FRAC = 0.005


def _saccade_arrow_markers(
    fix_df: pd.DataFrame, x_col: str, y_col: str
) -> Tuple[list, list, list, list]:
    """Arrowhead position + direction for each saccade.

    Returns ``(mid_x, mid_y, dir_x, dir_y)`` with one entry per consecutive
    fixation segment: a point at the segment midpoint and a *unit direction
    vector* (in data space) pointing along the gaze. matplotlib's ``quiver`` and
    inverted y-axis render the data-space vector correctly on screen, so no
    angle convention is needed. Micro-saccades (sub-pixel, scaled to the data
    extent) and zero-length segments are dropped.
    """
    if len(fix_df) < 2:
        return [], [], [], []
    ordered = fix_df.sort_values("timestamp_ms")
    xv = pd.to_numeric(ordered[x_col], errors="coerce").to_numpy()
    yv = pd.to_numeric(ordered[y_col], errors="coerce").to_numpy()
    finite = np.isfinite(xv) & np.isfinite(yv)
    if finite.any():
        x_ext = float(np.nanmax(xv[finite]) - np.nanmin(xv[finite]))
        y_ext = float(np.nanmax(yv[finite]) - np.nanmin(yv[finite]))
        min_len = np.hypot(x_ext, y_ext) * _ARROW_MIN_LEN_FRAC
    else:
        min_len = 0.0
    mid_x: list = []
    mid_y: list = []
    dir_x: list = []
    dir_y: list = []
    for i in range(len(ordered) - 1):
        x0, y0, x1, y1 = xv[i], yv[i], xv[i + 1], yv[i + 1]
        if not np.isfinite((x0, y0, x1, y1)).all():
            continue
        dx, dy = x1 - x0, y1 - y0
        seg_len = float(np.hypot(dx, dy))
        if seg_len == 0.0 or seg_len < min_len:
            continue
        mid_x.append((x0 + x1) / 2.0)
        mid_y.append((y0 + y1) / 2.0)
        dir_x.append(float(dx / seg_len))
        dir_y.append(float(dy / seg_len))
    return mid_x, mid_y, dir_x, dir_y


def build_word_boxes(words: pd.DataFrame, color: str = WORD_BOX_COLOR) -> list:
    """Return backend-neutral rect specs (one per word box).

    Each spec is ``{type:'rect', x0, y0, x1, y1, line, fillcolor}``; the
    matplotlib builders turn them into ``Rectangle`` patches via
    :func:`_add_rect_shapes`. The neutral dict is kept so the spec is shared and
    testable without a backend.
    """
    shapes = []
    for row in words.itertuples():
        x0, y0 = row.x, row.y
        x1, y1 = row.x + row.width, row.y + row.height
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


_CRITICAL_FRAME_COLOR = "#000000"  # black — high-contrast frame, readable over heatmaps
_CRITICAL_FRAME_WIDTH = 2
_CRITICAL_TEXT_COLOR = (
    HIGHLIGHTED_TEXT_COLOR  # dark pink — for critical_span_style="Mark text"
)


def build_critical_span_overlay(
    words: pd.DataFrame, column: str = "is_in_aspan"
) -> list:
    """Return outline rect specs for the highlighted span (``column``).

    One outline per visual line that contains highlighted words, from the first
    to the last highlighted word on that line. Lines are clustered by y (the
    source ``line_idx`` is often constant). Returns [] when no words match.
    """
    if not column or column not in words.columns:
        return []
    mask = words[column].fillna(False).astype(bool)
    if not mask.any():
        return []
    span = words[mask].copy()

    typical_h = float(span["height"].median() or 1.0)
    y_sorted = span["y"].sort_values()
    line_ids = (y_sorted.diff().fillna(0) > typical_h * 0.5).cumsum()
    span["_line_id"] = line_ids.reindex(span.index)

    shapes = []
    for _, group in span.groupby("_line_id"):
        x0 = float(group["x"].min())
        x1 = float((group["x"] + group["width"]).max())
        y0 = float(group["y"].min())
        y1 = float((group["y"] + group["height"]).max())
        shapes.append(
            dict(
                type="rect",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                line=dict(color=_CRITICAL_FRAME_COLOR, width=_CRITICAL_FRAME_WIDTH),
                fillcolor="rgba(0,0,0,0)",
                layer="above",
            )
        )
    return shapes


# ---------------------------------------------------------------------------
# matplotlib drawing primitives (shared by the spatial builders)
# ---------------------------------------------------------------------------
def _as_color_array(marker_color):
    """Normalise a colour (single string) or list of colours to a matplotlib
    facecolor argument — RGBA array for a list, passthrough for a scalar."""
    if isinstance(marker_color, (list, tuple, np.ndarray, pd.Series)) and not (
        isinstance(marker_color, str)
    ):
        return np.array([mr.to_mpl_color(c) for c in marker_color])
    return mr.to_mpl_color(marker_color)


def _add_rect_shapes(ax, shapes: list, *, zorder: float) -> None:
    """Draw backend-neutral rect specs (from build_word_boxes / overlays) as
    ``Rectangle`` patches in data coords. Honours each spec's fill/line/opacity;
    ``layer='above'`` bumps the zorder above regular boxes."""
    for shp in shapes:
        x0, y0, x1, y1 = shp["x0"], shp["y0"], shp["x1"], shp["y1"]
        line = shp.get("line") or {}
        lw = mr.px_to_pt(line.get("width", 1))
        edge = mr.to_mpl_color(line.get("color", WORD_BOX_COLOR))
        face = mr.to_mpl_color(shp.get("fillcolor"), default="none")
        z = zorder + (0.5 if shp.get("layer") == "above" else 0.0)
        ax.add_patch(
            Rectangle(
                (x0, y0),
                x1 - x0,
                y1 - y0,
                facecolor=face if face is not None else "none",
                edgecolor=edge,
                linewidth=lw if lw > 0 else 0,
                alpha=shp.get("opacity"),
                zorder=z,
            )
        )


def _draw_canvas_border(ax, x_range, y_range) -> None:
    """The thin black plot border, drawn as a data-space rectangle (Plotly drew
    it as a layout shape; matplotlib hides the spines and draws this instead)."""
    ax.add_patch(
        Rectangle(
            (x_range[0], y_range[1]),
            x_range[1] - x_range[0],
            y_range[0] - y_range[1],
            facecolor="none",
            edgecolor="#000000",
            linewidth=mr.px_to_pt(1),
            zorder=_Z_BORDER,
            label="canvas-border",
        )
    )


def _draw_word_labels(
    ax,
    words: pd.DataFrame,
    font_px: float,
    font_family: str,
    *,
    highlight_column: Optional[str] = None,
    text_color: str = WORD_LABEL_COLOR,
    highlight_text_color: str = _CRITICAL_TEXT_COLOR,
    zorder: float = _Z_LABEL,
) -> list:
    """Draw word labels centred in each box, sized true-to-scale.

    ``font_px`` is the screen-px size from :func:`_word_label_font_px`; it is
    converted to points so a save at :data:`mpl_render.DPI` renders the glyph at
    that pixel size. Returns the list of ``Text`` artists.
    """
    if words.empty or "text" not in words.columns:
        return []
    fontsize_pt = mr.px_to_pt(font_px)
    if highlight_column and highlight_column in words.columns:
        critical_mask = words[highlight_column].fillna(False).astype(bool)
    else:
        critical_mask = None
    texts = []
    xs = words["x"] + words["width"] / 2
    ys = words["y"] + words["height"] / 2
    for (idx, row), cx, cy in zip(words.iterrows(), xs, ys):
        is_crit = bool(critical_mask.loc[idx]) if critical_mask is not None else False
        color = highlight_text_color if is_crit else text_color
        texts.append(
            ax.text(
                cx,
                cy,
                str(row["text"]),
                ha="center",
                va="center",
                fontsize=fontsize_pt,
                family=font_family,
                color=mr.to_mpl_color(color),
                zorder=zorder,
                label="words",
            )
        )
    return texts


def _draw_fixation_markers(
    ax,
    x,
    y,
    sizes_px,
    *,
    marker_color,
    is_numeric: bool,
    colorscale: str,
    cmin: Optional[float],
    cmax: Optional[float],
    hollow: bool,
    zorder: float = _Z_FIX,
    label: str = "Fixations",
):
    """Draw the fixation markers. Returns (collection, mappable-or-None).

    Handles filled/hollow × numeric/categorical: numeric maps ``marker_color``
    through ``colorscale`` with a fixed ``Normalize`` (so a colorbar can attach);
    hollow moves the colour to the outline and clears the fill.
    """
    s = mr.marker_area(sizes_px)
    outline = mr.to_mpl_color(FIX_MARKER_OUTLINE)
    mappable = None
    if hollow:
        # Transparent (alpha-0) fill rather than "none" so the fill colour is
        # introspectable; the colour moves to the outline.
        if is_numeric:
            edge = mr.sample_colors(marker_color, colorscale, cmin, cmax)
        else:
            edge = _as_color_array(marker_color)
        coll = ax.scatter(
            x,
            y,
            s=s,
            facecolors=(0.0, 0.0, 0.0, 0.0),
            edgecolors=edge,
            linewidths=mr.px_to_pt(HOLLOW_OUTLINE_WIDTH),
            zorder=zorder,
            label=label,
        )
    elif is_numeric:
        norm = Normalize(vmin=cmin, vmax=cmax)
        coll = ax.scatter(
            x,
            y,
            s=s,
            c=np.asarray(
                pd.to_numeric(pd.Series(list(marker_color)), errors="coerce"),
                dtype=float,
            ),
            cmap=mr.resolve_cmap(colorscale),
            norm=norm,
            edgecolors=outline,
            linewidths=mr.px_to_pt(0.5),
            zorder=zorder,
            label=label,
        )
        mappable = coll
    else:
        face = _as_color_array(marker_color)
        # A single colour goes through `color=` (a per-point `c=` of one RGBA
        # tuple trips matplotlib's value-mapping ambiguity warning).
        color_kw = (
            {"c": face}
            if isinstance(face, np.ndarray) and face.ndim == 2
            else {"color": face}
        )
        coll = ax.scatter(
            x,
            y,
            s=s,
            edgecolors=outline,
            linewidths=mr.px_to_pt(0.5),
            zorder=zorder,
            label=label,
            **color_kw,
        )
    return coll, mappable


def _draw_saccades(
    ax, fix_df, x_col, y_col, *, color, linestyle, zorder=_Z_SACCADE, label="saccades"
):
    """Draw all saccades as one ``LineCollection`` (constant artist count)."""
    segs = _saccade_segment_pairs(fix_df, x_col, y_col)
    if not segs:
        return None
    lc = LineCollection(
        segs,
        colors=[mr.to_mpl_color(color)],
        linewidths=mr.px_to_pt(2),
        linestyles=mr.mpl_linestyle(linestyle),
        zorder=zorder,
    )
    lc.set_label(label)
    ax.add_collection(lc)
    return lc


# Arrowhead length + shaft width in screen px (mirrors the old ~12 px arrow
# marker); converted to data units via the display scale so they render ~constant
# under uniform scaling and the head stays proportional to the shaft.
_ARROW_PX = 14.0
_ARROW_SHAFT_PX = 1.8


def _draw_saccade_arrows(
    ax,
    fix_df,
    x_col,
    y_col,
    *,
    color,
    scale,
    zorder=_Z_ARROW,
    label="saccade direction",
):
    """Draw saccade-direction arrowheads as a single ``quiver`` artist.

    Both the arrow length and the shaft width are expressed in *data* units
    (``units="xy"``) so they render at a roughly constant pixel size (via the
    display ``scale``) and the head stays proportional to the length — otherwise
    quiver's default axes-fraction width makes a short arrow's head balloon into
    a blob (the "arrows look like hexagons" bug).
    """
    mid_x, mid_y, dir_x, dir_y = _saccade_arrow_markers(fix_df, x_col, y_col)
    if not mid_x:
        return None
    inv_scale = 1.0 / max(scale, 1e-9)
    arrow_len_data = _ARROW_PX * inv_scale  # ~_ARROW_PX px long
    shaft_w_data = _ARROW_SHAFT_PX * inv_scale  # ~_ARROW_SHAFT_PX px wide
    q = ax.quiver(
        mid_x,
        mid_y,
        dir_x,
        dir_y,
        angles="xy",
        scale_units="xy",
        scale=1.0 / arrow_len_data,
        units="xy",
        width=shaft_w_data,
        headwidth=3.5,
        headlength=4.5,
        headaxislength=4.0,
        pivot="mid",
        color=mr.to_mpl_color(color),
        zorder=zorder,
        label=label,
    )
    return q


def _draw_order_numbers(ax, xs, ys, labels, *, color, size_px, family, zorder=_Z_ORDER):
    """Draw fixation order numbers above each marker. Returns the Text artists."""
    fontsize_pt = mr.px_to_pt(size_px)
    col = mr.to_mpl_color(color)
    texts = []
    for x, y, txt in zip(xs, ys, labels):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            continue
        texts.append(
            ax.annotate(
                str(txt),
                (x, y),
                textcoords="offset points",
                xytext=(0, 4),
                ha="center",
                va="bottom",
                fontsize=fontsize_pt,
                family=family,
                color=col,
                zorder=zorder,
            )
        )
    return texts


def _finish_spatial_axes(ax, x_range, y_range, *, background_color) -> None:
    """Pin the equal-aspect, inverted-y data limits and strip the chrome.

    ``set_aspect('equal')`` realises ``px-per-data == _display_scale`` (the min of
    the two axis scales), which is exactly the scale the true-to-scale font was
    computed against — so the labels keep filling the boxes.
    """
    ax.set_xlim(x_range[0], x_range[1])
    ax.set_ylim(y_range[0], y_range[1])  # descending → y grows downward (reading order)
    ax.set_aspect("equal", adjustable="box")
    mr.strip_spatial_axes(ax)
    if background_color is not None:
        ax.set_facecolor(mr.to_mpl_color(background_color))


def _add_colorbars(fig, mappables, *, left, bottom, fitted_w, fitted_h, font_family):
    """Place up to two colorbars in the reserved right strip (does not shrink the
    plot). ``mappables`` is a list of ``(mappable, title)``."""
    cbar_h = COLORBAR_LEN_FRACTION * fitted_h
    y0 = bottom + (fitted_h - cbar_h) / 2.0
    for i, (mappable, title) in enumerate(mappables[:2]):
        cax = mr.add_axes_px(
            fig,
            left + fitted_w + 14 + i * 74,
            y0,
            16,
            cbar_h,
        )
        cb = fig.colorbar(mappable, cax=cax)
        if title:
            cb.set_label(title, fontsize=mr.px_to_pt(12), family=font_family)
        cax.tick_params(labelsize=mr.px_to_pt(10))


def _add_top_legend(ax, handles, labels, *, font_family):
    """Add the figure legend in the reserved top strip (Plotly's horizontal
    top-right legend)."""
    if not handles:
        return
    ax.legend(
        handles,
        labels,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.005),
        ncol=max(1, min(len(handles), 4)),
        frameon=False,
        fontsize=mr.px_to_pt(11),
        handletextpad=0.4,
        columnspacing=1.0,
        prop={"family": font_family} if font_family else None,
    )


def _legend_proxy(color, *, marker="o", markersize=8, hollow=False):
    """A Line2D legend proxy with no line, just a marker (for category/raw-gaze/
    out-of-text legend entries)."""
    c = mr.to_mpl_color(color)
    return Line2D(
        [],
        [],
        marker=marker,
        linestyle="none",
        markersize=markersize,
        markerfacecolor="none" if hollow else c,
        markeredgecolor=c if hollow else mr.to_mpl_color(FIX_MARKER_OUTLINE),
    )


# ---------------------------------------------------------------------------
# Core spatial figure
# ---------------------------------------------------------------------------
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
    show_saccade_arrows: bool = False,
    heatmap_style: str = "Word boxes",
    marker_size_range: Tuple[int, int],
    order_font_size: int,
    order_font_color: str,
    show_colorbars: bool,
    fixation_color_range: Optional[Tuple[float, float]],
    heatmap_range: Optional[Tuple[float, float]],
    fixation_colorscale: str = DEFAULT_FIXATION_COLORSCALE,
    heatmap_colorscale: str = DEFAULT_HEATMAP_COLORSCALE,
    raw_gaze: Optional[pd.DataFrame] = None,
    show_raw_gaze: bool = False,
    critical_span_style: str = "Mark text",
    highlight_column: Optional[str] = "is_in_aspan",
    saccade_color: str = SACCADE_COLOR,
    saccade_style: str = "solid",
    hollow_fixations: bool = False,
    text_color: str = WORD_LABEL_COLOR,
    highlight_text_color: str = HIGHLIGHTED_TEXT_COLOR,
    background_color: Optional[str] = None,
    color_by_line: bool = False,
    highlight_out_of_text: bool = False,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
) -> Figure:
    spatial_axes = x_field == "x" and y_field == "y"
    font_family = font_family or FONT_FAMILY

    raw_for_range = raw_gaze if (show_raw_gaze and raw_gaze is not None) else None
    if spatial_axes:
        x_range, y_range, x_min_data, x_max_data, y_min_data, y_max_data = (
            _compute_axis_ranges(
                canvas_width,
                canvas_height,
                (fixations, x_field, y_field),
                (raw_for_range, "x", "y"),
                word_frames=[words] if not words.empty else [],
            )
        )
    else:
        x_range = [0, canvas_width]
        y_range = [canvas_height, 0]
        x_min_data = x_max_data = y_min_data = y_max_data = None

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

    has_highlight = (
        bool(highlight_column)
        and highlight_column in words.columns
        and not words.empty
        and bool(words[highlight_column].fillna(False).astype(bool).any())
    )
    highlight_text = has_highlight and critical_span_style == "Mark text"

    # --- Resolve everything that decides colorbar/legend reserves up front, so
    # the figure can be sized before drawing (the data axes must occupy an exact
    # fitted_w × fitted_h box). ---
    ordered = (
        fixations.sort_values("timestamp_ms")
        if (show_fixations and not fixations.empty)
        else fixations.iloc[0:0]
    )
    is_numeric_color = False
    marker_color: object = None
    category_legend: list = []
    color_label = color_by
    if show_fixations and not ordered.empty:
        if color_by_line and spatial_axes and not words.empty:
            from .measures import assign_fixation_lines

            line_ids = assign_fixation_lines(ordered, words)
            color_data = line_ids.map(
                lambda v: f"Line {int(v) + 1}" if pd.notna(v) else "(off-text)"
            )
            color_label = "line"
            is_numeric_color = False
        else:
            color_data = ordered[color_by] if color_by in ordered.columns else None
            is_numeric_color = color_data is not None and pd.api.types.is_numeric_dtype(
                color_data
            )
        marker_color, category_legend = _resolve_marker_colors(
            color_data, is_numeric_color
        )

    out_of_text_df = None
    if (
        show_fixations
        and not ordered.empty
        and highlight_out_of_text
        and spatial_axes
        and not words.empty
    ):
        from .measures import fixation_in_text_mask

        off = ordered[~fixation_in_text_mask(ordered, words)]
        if not off.empty:
            out_of_text_df = off

    raw_active = show_raw_gaze and raw_gaze is not None and not raw_gaze.empty
    heatmap_intent = bool(spatial_axes and show_heatmap) and (
        (not fixations.empty)
        or (
            not words.empty
            and (
                "total_fixation_duration_ms"
                if heatmap_metric == "duration_ms"
                else "n_fixations"
            )
            in words.columns
        )
    )
    legend_active = bool(category_legend) or raw_active or (out_of_text_df is not None)
    colorbar_active = show_colorbars and (is_numeric_color or heatmap_intent)

    right = _COLORBAR_RESERVE_PX if (spatial_axes and colorbar_active) else 0
    top = _LEGEND_RESERVE_PX if (spatial_axes and legend_active) else 0

    # --- Build the figure with the data axes pinned to fitted_w × fitted_h. ---
    if spatial_axes:
        fig = mr.new_figure(
            fitted_w + right, fitted_h + top, background_color=background_color
        )
        ax = mr.add_axes_px(
            fig, 0, 0, fitted_w, fitted_h, background_color=background_color
        )
        _finish_spatial_axes(ax, x_range, y_range, background_color=background_color)
    else:
        fig = mr.new_figure(fitted_w, fitted_h, background_color=background_color)
        ax = mr.add_axes_px(
            fig,
            70,
            55,
            max(fitted_w - 95, 50),
            max(fitted_h - 80, 50),
            background_color=background_color,
        )
        ax.set_xlabel(x_field.replace("_", " ").title())
        ax.set_ylabel(y_field.replace("_", " ").title())
        ax.grid(True, color="#e6e6e6", linewidth=0.6)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    mappables: list = []
    legend_handles: list = []
    legend_labels: list = []

    # Word boxes + critical-span border + labels.
    if spatial_axes and not words.empty:
        if show_words:
            _add_rect_shapes(ax, build_word_boxes(words), zorder=_Z_BOX)
        if has_highlight and critical_span_style == "Mark border":
            _add_rect_shapes(
                ax,
                build_critical_span_overlay(words, highlight_column),
                zorder=_Z_CRITICAL,
            )
        if show_word_labels:
            _draw_word_labels(
                ax,
                words,
                label_font_px,
                font_family,
                highlight_column=highlight_column if highlight_text else None,
                text_color=text_color,
                highlight_text_color=highlight_text_color,
            )

    # Raw gaze overlay.
    if raw_active:
        if "timestamp_ms" in raw_gaze.columns:
            ax.scatter(
                raw_gaze["x"],
                raw_gaze["y"],
                s=mr.marker_area(4),
                c=np.asarray(
                    pd.to_numeric(raw_gaze["timestamp_ms"], errors="coerce"),
                    dtype=float,
                ),
                cmap=mr.resolve_cmap("Viridis"),
                alpha=0.6,
                linewidths=0,
                zorder=_Z_RAW,
                label="Raw gaze",
            )
        else:
            ax.scatter(
                raw_gaze["x"],
                raw_gaze["y"],
                s=mr.marker_area(4),
                color=mr.to_mpl_color("#888888"),
                alpha=0.6,
                linewidths=0,
                zorder=_Z_RAW,
                label="Raw gaze",
            )
        legend_handles.append(_legend_proxy("#888888"))
        legend_labels.append("Raw gaze")

    # Heatmap.
    if spatial_axes and show_heatmap and not fixations.empty:
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
            hm = _add_interpolated_heatmap(
                ax,
                fixations,
                x_field=x_field,
                y_field=y_field,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                weights=weights,
                heatmap_colorscale=heatmap_colorscale,
            )
            if hm is not None and show_colorbars:
                mappables.append(
                    (
                        hm,
                        "Dwell-time density"
                        if weights is not None
                        else "Fixation density",
                    )
                )
        elif not words.empty:
            hm = _add_word_level_heatmap(
                ax,
                words,
                fixations,
                x_field=x_field,
                y_field=y_field,
                weights=weights,
                heatmap_colorscale=heatmap_colorscale,
                heatmap_range=heatmap_range,
            )
            if hm is not None and show_colorbars:
                mappables.append(
                    (hm, "Fixation count" if weights is None else "Duration (ms)")
                )
        else:
            hm = _add_density_heatmap(
                ax,
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
            )
            if hm is not None and show_colorbars:
                mappables.append(
                    (hm, "Fixation density" if weights is None else "Duration (ms)")
                )
    elif spatial_axes and show_heatmap and not words.empty:
        measure = (
            "total_fixation_duration_ms"
            if heatmap_metric == "duration_ms"
            else "n_fixations"
        )
        if measure in words.columns:
            hm = _add_word_measure_heatmap(
                ax,
                words,
                measure,
                heatmap_colorscale=heatmap_colorscale,
                heatmap_range=heatmap_range,
            )
            if hm is not None and show_colorbars:
                mappables.append(
                    (
                        hm,
                        "Fixation count"
                        if measure == "n_fixations"
                        else "Duration (ms)",
                    )
                )

    # Saccades + arrows.
    if spatial_axes and show_saccades and len(fixations) > 1:
        _draw_saccades(
            ax,
            fixations,
            x_field,
            y_field,
            color=saccade_color,
            linestyle=saccade_style,
        )
        if show_saccade_arrows:
            _draw_saccade_arrows(
                ax, fixations, x_field, y_field, color=saccade_color, scale=scale
            )

    # Fixation markers + order numbers + categorical legend + out-of-text.
    if show_fixations and not ordered.empty:
        sizes = _compute_marker_sizes(ordered["duration_ms"], marker_size_range)
        cmin = fixation_color_range[0] if fixation_color_range else None
        cmax = fixation_color_range[1] if fixation_color_range else None
        _coll, mappable = _draw_fixation_markers(
            ax,
            ordered[x_field],
            ordered[y_field],
            sizes,
            marker_color=marker_color,
            is_numeric=is_numeric_color,
            colorscale=fixation_colorscale,
            cmin=cmin,
            cmax=cmax,
            hollow=hollow_fixations,
        )
        if mappable is not None and show_colorbars and not hollow_fixations:
            mappables.append((mappable, color_label.replace("_", " ").title()))
        if show_order:
            _draw_order_numbers(
                ax,
                ordered[x_field],
                ordered[y_field],
                ordered["order_in_trial"],
                color=order_font_color,
                size_px=order_font_size,
                family=font_family,
            )
        legend_limit = len(_QUALITATIVE_PALETTE)
        for category, color in category_legend[:legend_limit]:
            legend_handles.append(_legend_proxy(color))
            legend_labels.append(f"{color_label}: {category}")
        if len(category_legend) > legend_limit:
            legend_handles.append(_legend_proxy("#cccccc"))
            legend_labels.append(f"… +{len(category_legend) - legend_limit} more")

        if out_of_text_df is not None:
            ax.scatter(
                out_of_text_df[x_field],
                out_of_text_df[y_field],
                s=mr.marker_area(13),
                marker="x",
                c=[mr.to_mpl_color(OUT_OF_TEXT_COLOR)],
                linewidths=mr.px_to_pt(1.5),
                zorder=_Z_OOT,
                label="Out-of-text",
            )
            legend_handles.append(
                Line2D(
                    [],
                    [],
                    marker="x",
                    linestyle="none",
                    markeredgecolor=mr.to_mpl_color(OUT_OF_TEXT_COLOR),
                )
            )
            legend_labels.append("Out-of-text")

    if spatial_axes:
        _draw_canvas_border(ax, x_range, y_range)
        if mappables:
            _add_colorbars(
                fig,
                mappables,
                left=0,
                bottom=0,
                fitted_w=fitted_w,
                fitted_h=fitted_h,
                font_family=font_family,
            )
        if legend_handles:
            _add_top_legend(ax, legend_handles, legend_labels, font_family=font_family)

    return fig


# ---------------------------------------------------------------------------
# Heatmaps
# ---------------------------------------------------------------------------
def _add_word_level_heatmap(
    ax,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    x_field: str,
    y_field: str,
    weights: Optional[pd.Series],
    heatmap_colorscale: str,
    heatmap_range: Optional[Tuple[float, float]],
):
    fx = pd.to_numeric(fixations[x_field], errors="coerce").to_numpy(dtype=float)
    fy = pd.to_numeric(fixations[y_field], errors="coerce").to_numpy(dtype=float)
    w_arr = (
        pd.to_numeric(weights, errors="coerce").to_numpy(dtype=float)
        if weights is not None
        else None
    )
    word_values = []
    for word_row in words.itertuples():
        wx0, wy0 = word_row.x, word_row.y
        wx1, wy1 = wx0 + word_row.width, wy0 + word_row.height
        in_word = (fx >= wx0) & (fx <= wx1) & (fy >= wy0) & (fy <= wy1)
        val = (
            float(np.nansum(w_arr[in_word]))
            if w_arr is not None
            else float(in_word.sum())
        )
        word_values.append(val)
    return _draw_word_value_heatmap(
        ax,
        words,
        word_values,
        heatmap_colorscale=heatmap_colorscale,
        heatmap_range=heatmap_range,
    )


def _add_word_measure_heatmap(
    ax,
    words: pd.DataFrame,
    measure: str,
    *,
    heatmap_colorscale: str,
    heatmap_range: Optional[Tuple[float, float]],
):
    """Word-box heatmap from a pre-aggregated per-word measure (words-only data)."""
    values = pd.to_numeric(words[measure], errors="coerce").fillna(0.0)
    return _draw_word_value_heatmap(
        ax,
        words,
        [float(v) for v in values],
        heatmap_colorscale=heatmap_colorscale,
        heatmap_range=heatmap_range,
    )


def _draw_word_value_heatmap(
    ax,
    words: pd.DataFrame,
    word_values: list,
    *,
    heatmap_colorscale: str,
    heatmap_range: Optional[Tuple[float, float]],
):
    """Translucent per-word colour fill (one Rectangle per nonzero word).

    Returns a ``ScalarMappable`` (for an optional colorbar) or ``None`` when no
    word has a positive value. Colours use a fixed ``Normalize`` over
    ``heatmap_range`` (or the data min/max) so the scale is stable.
    """
    nonzero_rows = [(wr, v) for wr, v in zip(words.itertuples(), word_values) if v > 0]
    if not nonzero_rows:
        return None
    vals = [v for _, v in nonzero_rows]
    z_min = heatmap_range[0] if heatmap_range else float(min(vals))
    z_max = heatmap_range[1] if heatmap_range else float(max(vals))
    cmap = mr.resolve_cmap(heatmap_colorscale)
    norm = Normalize(vmin=z_min, vmax=z_max)
    for wr, v in nonzero_rows:
        ax.add_patch(
            Rectangle(
                (wr.x, wr.y),
                wr.width,
                wr.height,
                facecolor=cmap(norm(v)),
                edgecolor="none",
                alpha=0.5,
                zorder=_Z_HEATMAP,
            )
        )
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([z_min, z_max])
    return sm


def _add_density_heatmap(
    ax,
    fixations: pd.DataFrame,
    *,
    x_field: str,
    y_field: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    weights: Optional[pd.Series],
    heatmap_colorscale: str,
    heatmap_range: Optional[Tuple[float, float]],
):
    """2-D histogram density heatmap (40×40 bins) via ``pcolormesh``."""
    x_span = max(x_max - x_min, 1.0)
    y_span = max(y_max - y_min, 1.0)
    nx = max(2, int(round(x_span / (x_span / 40.0))))
    ny = max(2, int(round(y_span / (y_span / 40.0))))
    x_edges = np.linspace(x_min, x_max, nx + 1)
    y_edges = np.linspace(y_min, y_max, ny + 1)
    xs = pd.to_numeric(fixations[x_field], errors="coerce").to_numpy()
    ys = pd.to_numeric(fixations[y_field], errors="coerce").to_numpy()
    valid = np.isfinite(xs) & np.isfinite(ys)
    w = (
        pd.to_numeric(weights, errors="coerce").to_numpy()[valid]
        if weights is not None
        else None
    )
    hist, _, _ = np.histogram2d(
        xs[valid], ys[valid], bins=[x_edges, y_edges], weights=w
    )
    grid = np.ma.masked_less_equal(hist.T, 0.0)
    vmin = heatmap_range[0] if heatmap_range else None
    vmax = heatmap_range[1] if heatmap_range else None
    mesh = ax.pcolormesh(
        x_edges,
        y_edges,
        grid,
        cmap=mr.resolve_cmap(heatmap_colorscale),
        alpha=0.35,
        vmin=vmin,
        vmax=vmax,
        zorder=_Z_HEATMAP,
        shading="flat",
    )
    return mesh


def _gaussian_kernel_1d(sigma: float) -> np.ndarray:
    radius = max(1, int(round(sigma * 3)))
    offsets = np.arange(-radius, radius + 1)
    kernel = np.exp(-(offsets**2) / (2.0 * sigma * sigma))
    return kernel / kernel.sum()


def _gaussian_blur_2d(
    grid: np.ndarray, sigma_rows: float, sigma_cols: float
) -> np.ndarray:
    out = grid.astype(float)
    if sigma_rows and sigma_rows > 0:
        k = _gaussian_kernel_1d(sigma_rows)
        out = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, out)
    if sigma_cols and sigma_cols > 0:
        k = _gaussian_kernel_1d(sigma_cols)
        out = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, out)
    return out


_INTERP_GRID = 240
_INTERP_SIGMA_FRAC = 0.02
_INTERP_MIN_SIGMA_PX = 8.0
_INTERP_OPACITY = 0.45
_INTERP_FLOOR_FRAC = 0.02


def _add_interpolated_heatmap(
    ax,
    fixations: pd.DataFrame,
    *,
    x_field: str,
    y_field: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    weights: Optional[pd.Series],
    heatmap_colorscale: str,
):
    """Smooth Gaussian-interpolated fixation heatmap via ``imshow``.

    Empty cells render transparent (masked) so the reading text stays legible.
    Returns the ``AxesImage`` (a mappable) or ``None``.
    """
    xs = pd.to_numeric(fixations[x_field], errors="coerce")
    ys = pd.to_numeric(fixations[y_field], errors="coerce")
    valid = xs.notna() & ys.notna()
    if not valid.any():
        return None
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
    nx = _INTERP_GRID
    ny = max(10, int(round(_INTERP_GRID * y_span / x_span)))
    x_edges = np.linspace(x_min, x_max, nx + 1)
    y_edges = np.linspace(y_min, y_max, ny + 1)
    hist, _, _ = np.histogram2d(xs, ys, bins=[x_edges, y_edges], weights=w)
    grid = hist.T  # rows index y, cols index x

    sigma_px = max(_INTERP_MIN_SIGMA_PX, _INTERP_SIGMA_FRAC * max(x_span, y_span))
    blurred = _gaussian_blur_2d(
        grid, sigma_rows=sigma_px / (y_span / ny), sigma_cols=sigma_px / (x_span / nx)
    )
    peak = float(blurred.max())
    if peak <= 0:
        return None
    masked = np.ma.masked_less(blurred, peak * _INTERP_FLOOR_FRAC)
    # extent maps the grid to data coords; origin='upper' keeps row 0 at the top
    # of the (inverted) y-axis, matching the histogram's y orientation.
    img = ax.imshow(
        masked,
        extent=(x_min, x_max, y_max, y_min),
        origin="upper",
        cmap=mr.resolve_cmap(heatmap_colorscale),
        alpha=_INTERP_OPACITY,
        vmin=0.0,
        aspect="auto",
        interpolation="bilinear",
        zorder=_Z_HEATMAP,
    )
    return img


# =============================================================================
# Scanpath animation — one or two scanpaths on a shared real reading-time clock
# =============================================================================
_ANIM_MIN_FRAME_MS = 16

# The interactive ``to_jshtml`` player inlines every frame as a base64 PNG, so a
# long reading (hundreds/thousands of fixations) would be a huge page. Cap the
# on-screen player here, preserving the total runtime; the GIF/MP4 export has its
# own (separate) cap.
_PLAYER_FRAME_CAP = 250


def _scanpath_anim_specs(entries, marker_size_range):
    """Build per-scanpath animation specs from (fixations, color, label) entries.

    Onsets are ``timestamp_ms`` rebased to each reading's first fixation (shared
    real-time clock), falling back to back-to-back durations when timestamps are
    synthetic. Marker sizes scale over the COMBINED durations.
    """
    from .measures import rebased_fixation_onsets

    specs = []
    for fix_df, color, label in entries:
        if fix_df is None or fix_df.empty:
            continue
        ordered = fix_df.sort_values("timestamp_ms").reset_index(drop=True)
        dur = pd.to_numeric(ordered["duration_ms"], errors="coerce").fillna(0)
        onsets = rebased_fixation_onsets(ordered)
        specs.append(
            dict(
                ordered=ordered,
                dur=dur,
                onsets=onsets,
                end=float(onsets[-1] + dur.iloc[-1]),
                color=color,
                label=label,
            )
        )
    if specs:
        combined = _compute_marker_sizes(
            pd.concat([s["dur"] for s in specs], ignore_index=True), marker_size_range
        )
        cursor = 0
        for s in specs:
            n = len(s["dur"])
            s["sizes"] = np.asarray(combined[cursor : cursor + n], dtype=float)
            cursor += n
    return specs


def _anim_timeline(specs, playback_speed):
    """Merged frame timeline across all scanpaths.

    Returns ``(onset_times, frame_durations_ms, avg_frame_duration,
    reading_span_ms)``. A frame is emitted at every distinct fixation onset;
    each lasts the gap to the next onset / ``playback_speed``, floored at
    ``_ANIM_MIN_FRAME_MS``.
    """
    onset_times = sorted({float(t) for s in specs for t in s["onsets"]})
    reading_span_ms = max((s["end"] for s in specs), default=0.0)
    frame_durations_ms = []
    for k, t in enumerate(onset_times):
        nxt = onset_times[k + 1] if k + 1 < len(onset_times) else reading_span_ms
        gap = max(nxt - t, 0.0)
        frame_durations_ms.append(
            int(max(gap / max(playback_speed, 1e-6), _ANIM_MIN_FRAME_MS))
        )
    avg = (
        max(int(np.mean(frame_durations_ms)), _ANIM_MIN_FRAME_MS)
        if frame_durations_ms
        else _ANIM_MIN_FRAME_MS
    )
    return onset_times, frame_durations_ms, avg, reading_span_ms


def animation_playback_ms(fixations_list, playback_speed):
    """Reading span and *actual* animation runtime for the given scanpath(s).

    Returns ``(reading_span_ms, playback_ms)``; ``playback_ms == n_frames * avg``
    (the player advances every frame at the average frame duration). Both 0 with
    no fixations.
    """
    specs = _scanpath_anim_specs(
        [(f, None, None) for f in fixations_list], DEFAULT_MARKER_SIZE_RANGE
    )
    if not specs:
        return 0.0, 0.0
    onset_times, _frame_durations, avg, reading_span_ms = _anim_timeline(
        specs, playback_speed
    )
    return reading_span_ms, float(len(onset_times) * avg)


@dataclass
class ScanpathAnimation:
    """A matplotlib scanpath replay.

    Holds the prepared figure with its static layers drawn and a ``draw_frame``
    closure that updates only the dynamic artists for a given frame. ``frames``
    is ``range(n)`` over the merged onsets (so ``len(anim.frames)`` is the frame
    count downstream consumers read). The in-app view embeds :meth:`to_jshtml`
    (an interactive HTML5 player); the GIF/MP4 exporter rasterises each frame via
    :meth:`draw_frame` + ``savefig``.
    """

    figure: Figure
    frames: list
    frame_durations_ms: list
    avg_frame_duration: float
    elapsed_labels: list
    reading_span_ms: float
    width: int
    height: int
    # The per-scanpath trail marker collections (A, then B), for introspection.
    trails: list = field(default_factory=list, repr=False)
    _draw: Callable[[int], list] = field(repr=False, default=lambda k: [])

    def draw_frame(self, k: int) -> list:
        """Update the figure to frame ``k``; returns the changed artists."""
        return self._draw(k)

    def _player_frame_indices(self, max_frames: Optional[int]) -> list:
        n = len(self.frames)
        if not max_frames or max_frames <= 0 or n <= max_frames:
            return list(range(n))
        # Even downsample keeping the endpoints (start empty, end full).
        return sorted({int(round(i)) for i in np.linspace(0, n - 1, max_frames)})

    def funcanimation(
        self,
        *,
        interval: Optional[float] = None,
        blit: bool = False,
        max_frames: Optional[int] = _PLAYER_FRAME_CAP,
    ):
        """A ``FuncAnimation`` over the frames.

        ``max_frames`` evenly downsamples very long readings (the inlined
        ``to_jshtml`` player base64-encodes every frame, so an uncapped 1000-frame
        reading would be a huge page); the per-frame interval is scaled up to keep
        the total runtime unchanged.
        """
        from matplotlib.animation import FuncAnimation

        idx = self._player_frame_indices(max_frames)
        base = interval if interval is not None else self.avg_frame_duration
        if len(idx) < len(self.frames):
            base = base * len(self.frames) / len(idx)
        return FuncAnimation(
            self.figure, self._draw, frames=idx, interval=base, blit=blit, repeat=True
        )

    def to_jshtml(
        self,
        *,
        interval: Optional[float] = None,
        max_frames: Optional[int] = _PLAYER_FRAME_CAP,
    ) -> str:
        """Self-contained interactive HTML5 player (play/pause/scrub), no browser
        needed to build it. Embedded by the in-app animation view."""
        return self.funcanimation(interval=interval, max_frames=max_frames).to_jshtml()


def make_scanpath_animation(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    playback_speed: float = 1.0,
    show_words: bool = True,
    show_word_labels: bool = True,
    show_saccades: bool = True,
    show_order: bool = True,
    marker_size_range: Tuple[int, int] = DEFAULT_MARKER_SIZE_RANGE,
    order_font_size: int = 10,
    order_font_color: str = "#000000",
    color_by: Optional[str] = None,
    color_by_line: bool = False,
    fixation_colorscale: str = DEFAULT_FIXATION_COLORSCALE,
    fixation_color_range: Optional[Tuple[float, float]] = None,
    show_colorbars: bool = False,
    saccade_color: str = SACCADE_COLOR,
    saccade_style: str = "solid",
    hollow_fixations: bool = False,
    background_color: Optional[str] = None,
    fixations_b: Optional[pd.DataFrame] = None,
    words_b: Optional[pd.DataFrame] = None,
    label_a: str = "Scanpath A",
    label_b: str = "Scanpath B",
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
) -> ScanpathAnimation:
    """Frame-by-frame scanpath replay on a real reading-time clock.

    Pass ``fixations_b`` (+ optional ``words_b``) to overlay a SECOND scanpath on
    the same clock. The single replay honours the static figure's fixation
    colouring (``color_by`` numeric → ``fixation_colorscale`` pinned to the whole
    trial's range so colours stay stable as the trail grows; categorical →
    discrete palette + legend; ``color_by_line``). The dual overlay uses the flat
    A/B comparison colours. Returns a :class:`ScanpathAnimation`.
    """
    font_family = font_family or FONT_FAMILY

    word_frames = [w for w in (words, words_b) if w is not None and not w.empty]
    x_range, y_range, *_ = _compute_axis_ranges(
        canvas_width,
        canvas_height,
        (fixations, "x", "y"),
        (fixations_b, "x", "y"),
        word_frames=word_frames,
    )
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

    specs = _scanpath_anim_specs(
        [
            (fixations, COMPARISON_PALETTE[0], label_a),
            (fixations_b, COMPARISON_PALETTE[1], label_b),
        ],
        marker_size_range,
    )
    dual = len(specs) > 1
    if not dual and specs:
        specs[0]["color"] = COMPARISON_PALETTE[0]

    # Metric colouring (single replay only), pinned to the whole trial up front.
    for s in specs:
        s["marker_colors"] = None
        s["is_numeric"] = False
        s["cmin"] = None
        s["cmax"] = None
    category_legend: list = []
    color_label = color_by or ""
    numeric_mappable_spec = None
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
            specs[0]["is_numeric"] = is_numeric_color
            if is_numeric_color:
                rng = fixation_color_range or (
                    float(color_data.min()),
                    float(color_data.max()),
                )
                specs[0]["cmin"], specs[0]["cmax"] = rng[0], rng[1]
                numeric_mappable_spec = specs[0]

    colorbar_active = show_colorbars and numeric_mappable_spec is not None
    legend_active = dual or bool(category_legend)
    right = _COLORBAR_RESERVE_PX if colorbar_active else 0

    fig = mr.new_figure(fitted_w + right, fitted_h, background_color=background_color)
    ax = mr.add_axes_px(
        fig, 0, 0, fitted_w, fitted_h, background_color=background_color
    )
    _finish_spatial_axes(ax, x_range, y_range, background_color=background_color)

    # Static layers (drawn once).
    if show_words and not words.empty:
        _add_rect_shapes(ax, build_word_boxes(words), zorder=_Z_BOX)
    if show_word_labels and not words.empty:
        _draw_word_labels(ax, words, label_font_px, font_family)
    _draw_canvas_border(ax, x_range, y_range)

    onset_times, frame_durations, avg_frame_duration, _span = _anim_timeline(
        specs, playback_speed
    )
    elapsed_labels = [f"{t / 1000:.1f}s" for t in onset_times]

    # Per-scanpath dynamic artists, built empty and updated per frame.
    legend_handles: list = []
    legend_labels: list = []
    for s in specs:
        ordered = s["ordered"]
        s["all_x"] = ordered["x"].to_numpy(dtype=float)
        s["all_y"] = ordered["y"].to_numpy(dtype=float)
        s["n_total"] = len(ordered)
        s["order_text"] = [str(j + 1) for j in range(s["n_total"])]
        s["text_color"] = s["color"] if dual else order_font_color
        s["sac_color"] = s["color"] if dual else saccade_color
        s["curr_outline"] = s["color"] if dual else CURRENT_FIX_OUTLINE
        s["curr_outline_w"] = 2.5 if dual else 2.0

        # Trail markers: created at full length with real positions (so the
        # colour array / normalisation are computed whole and never re-masked);
        # each frame then masks the *offsets* of unreached fixations so they
        # aren't drawn, while the colour array stays pinned to the whole trial.
        sizes = s["sizes"]
        transparent = (0.0, 0.0, 0.0, 0.0)
        if s["is_numeric"]:
            norm = Normalize(vmin=s["cmin"], vmax=s["cmax"])
            cmap = mr.resolve_cmap(fixation_colorscale)
            trail = ax.scatter(
                s["all_x"],
                s["all_y"],
                s=mr.marker_area(sizes),
                c=np.asarray(
                    pd.to_numeric(pd.Series(s["marker_colors"]), errors="coerce"),
                    dtype=float,
                ),
                cmap=cmap,
                norm=norm,
                edgecolors=transparent
                if hollow_fixations
                else mr.to_mpl_color(FIX_MARKER_OUTLINE),
                linewidths=mr.px_to_pt(
                    HOLLOW_OUTLINE_WIDTH if hollow_fixations else 0.5
                ),
                zorder=_Z_FIX,
                label=s["label"],
            )
            if hollow_fixations:
                trail.set_facecolor(transparent)
        else:
            if s["marker_colors"] is not None:
                face = _as_color_array(s["marker_colors"])
            else:
                face = mr.to_mpl_color(s["color"])
            trail = ax.scatter(
                s["all_x"],
                s["all_y"],
                s=mr.marker_area(sizes),
                facecolors=transparent if hollow_fixations else face,
                edgecolors=face
                if hollow_fixations
                else mr.to_mpl_color(FIX_MARKER_OUTLINE),
                linewidths=mr.px_to_pt(
                    HOLLOW_OUTLINE_WIDTH if hollow_fixations else 0.5
                ),
                zorder=_Z_FIX,
                label=s["label"],
            )
        s["trail"] = trail

        # Saccade polyline (empty LineCollection, segments set per frame).
        if show_saccades:
            lc = LineCollection(
                [],
                colors=[mr.to_mpl_color(s["sac_color"])],
                linewidths=mr.px_to_pt(2),
                linestyles=mr.mpl_linestyle(saccade_style),
                zorder=_Z_SACCADE,
            )
            ax.add_collection(lc)
            s["sac"] = lc
        else:
            s["sac"] = None

        # Order numbers: one Text per fixation at its true position, hidden until
        # revealed (visibility toggle → numbers never glide in from the corner).
        if show_order:
            order_texts = []
            for j in range(s["n_total"]):
                t = ax.annotate(
                    s["order_text"][j],
                    (s["all_x"][j], s["all_y"][j]),
                    textcoords="offset points",
                    xytext=(0, 4),
                    ha="center",
                    va="bottom",
                    fontsize=mr.px_to_pt(order_font_size),
                    family=font_family,
                    color=mr.to_mpl_color(s["text_color"]),
                    zorder=_Z_ORDER,
                )
                t.set_visible(False)
                order_texts.append(t)
            s["order_texts"] = order_texts
        else:
            s["order_texts"] = []

        # Current-fixation highlight marker.
        curr = ax.scatter(
            [np.nan],
            [np.nan],
            s=[mr.marker_area(float(sizes[0]) + 8)],
            facecolors=[mr.to_mpl_color(CURRENT_FIX_COLOR)],
            edgecolors=[mr.to_mpl_color(s["curr_outline"])],
            linewidths=mr.px_to_pt(s["curr_outline_w"]),
            zorder=_Z_CURRENT,
        )
        s["curr"] = curr

        if dual:
            legend_handles.append(_legend_proxy(s["color"]))
            legend_labels.append(s["label"])

    legend_limit = len(_QUALITATIVE_PALETTE)
    for category, color in category_legend[:legend_limit]:
        legend_handles.append(_legend_proxy(color))
        legend_labels.append(f"{color_label}: {category}")
    if len(category_legend) > legend_limit:
        legend_handles.append(_legend_proxy("#cccccc"))
        legend_labels.append(f"… +{len(category_legend) - legend_limit} more")
    if legend_active and legend_handles:
        ax.legend(
            legend_handles,
            legend_labels,
            loc="upper right",
            fontsize=mr.px_to_pt(11),
            framealpha=0.7,
            prop={"family": font_family} if font_family else None,
        )

    if colorbar_active and numeric_mappable_spec is not None:
        _add_colorbars(
            fig,
            [(numeric_mappable_spec["trail"], color_label.replace("_", " ").title())],
            left=0,
            bottom=0,
            fitted_w=fitted_w,
            fitted_h=fitted_h,
            font_family=font_family,
        )

    # Elapsed-time readout (top-left, inside the plot — like the classic clock).
    # The label list stays the raw "X.Xs" clock values; the on-screen readout
    # prefixes "Elapsed: " (mirroring the old slider readout).
    def _elapsed_text(k: int) -> str:
        return f"Elapsed: {elapsed_labels[k]}" if elapsed_labels else ""

    elapsed_artist = ax.text(
        0.01,
        0.99,
        _elapsed_text(0),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=mr.px_to_pt(14),
        color="#444444",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7),
        zorder=_Z_BORDER + 1,
    )

    def _draw(k: int):
        changed = []
        for s in specs:
            onsets = s["onsets"]
            kk = max(int(np.searchsorted(onsets, onset_times[k], side="right")), 1)
            kk = min(kk, s["n_total"])
            ax_x, ax_y = s["all_x"], s["all_y"]
            # Mask (don't NaN) the offsets of unreached fixations: masked points
            # aren't drawn, but the colour array / Normalize stay intact, so
            # colours never renormalise to the partial trail.
            offs = np.ma.array(np.column_stack([ax_x, ax_y]), mask=False)
            if kk < len(ax_x):
                offs[kk:] = np.ma.masked
            s["trail"].set_offsets(offs)
            changed.append(s["trail"])
            if s["sac"] is not None:
                segs = [
                    [(ax_x[j], ax_y[j]), (ax_x[j + 1], ax_y[j + 1])]
                    for j in range(kk - 1)
                ]
                s["sac"].set_segments(segs)
                changed.append(s["sac"])
            for j, t in enumerate(s["order_texts"]):
                t.set_visible(j < kk)
                changed.append(t)
            ci = kk - 1
            s["curr"].set_offsets([[ax_x[ci], ax_y[ci]]])
            changed.append(s["curr"])
        if elapsed_labels:
            elapsed_artist.set_text(_elapsed_text(k))
            changed.append(elapsed_artist)
        return changed

    # Seed frame 0 so a static save (or the first player frame) is populated.
    if onset_times:
        _draw(0)

    return ScanpathAnimation(
        figure=fig,
        frames=list(range(len(onset_times))),
        frame_durations_ms=frame_durations,
        avg_frame_duration=float(avg_frame_duration),
        elapsed_labels=elapsed_labels,
        reading_span_ms=float(_span),
        width=fitted_w + right,
        height=fitted_h,
        trails=[s["trail"] for s in specs],
        _draw=_draw,
    )


# =============================================================================
# Comparison figures
# =============================================================================
def _resolve_trial_display_name(participant, trial_id, trial_words, trial_labels, idx):
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
    idx, override=None, *, default_marker_size_range=DEFAULT_MARKER_SIZE_RANGE
):
    base = {
        "fix_color": COMPARISON_PALETTE[idx % len(COMPARISON_PALETTE)],
        "saccade_color": COMPARISON_PALETTE[idx % len(COMPARISON_PALETTE)],
        "saccade_style": "solid",
        "marker_size_range": default_marker_size_range,
        "hollow": False,
    }
    if override:
        base.update({k: v for k, v in override.items() if v is not None})
    return base


def _add_comparison_fixation_trace(
    ax,
    trial_fix: pd.DataFrame,
    display_name: str,
    style: dict,
    *,
    font_family: str,
    scale: float,
    show_saccades: bool = True,
    show_saccade_arrows: bool = False,
    show_order: bool = True,
    order_font_size: Optional[int] = None,
):
    """Draw one scanpath's saccades + arrows + fixation markers (+ order numbers)
    onto ``ax`` with a single flat per-scanpath colour. Returns the marker
    collection (for legend handles)."""
    if trial_fix.empty:
        return None
    fix_color = style["fix_color"]
    saccade_color = style["saccade_color"]
    saccade_style = style.get("saccade_style", "solid")

    if show_saccades and len(trial_fix) > 1:
        _draw_saccades(
            ax,
            trial_fix,
            "x",
            "y",
            color=saccade_color,
            linestyle=saccade_style,
            label=display_name,
        )
    if show_saccade_arrows and len(trial_fix) > 1:
        _draw_saccade_arrows(
            ax,
            trial_fix,
            "x",
            "y",
            color=saccade_color,
            scale=scale,
            label=display_name,
        )

    ordered = trial_fix.sort_values("timestamp_ms")
    sizes = _compute_marker_sizes(ordered["duration_ms"], style["marker_size_range"])
    coll, _ = _draw_fixation_markers(
        ax,
        ordered["x"],
        ordered["y"],
        sizes,
        marker_color=fix_color,
        is_numeric=False,
        colorscale=None,
        cmin=None,
        cmax=None,
        hollow=bool(style.get("hollow")),
        label=display_name,
    )
    if show_order:
        _draw_order_numbers(
            ax,
            ordered["x"],
            ordered["y"],
            ordered["order_in_trial"],
            color=fix_color,
            size_px=order_font_size if order_font_size is not None else 10,
            family=font_family,
        )
    return coll


def _make_split_comparison_figure(
    words,
    fixations,
    trial_a,
    trial_b,
    *,
    canvas_width,
    canvas_height,
    font_family,
    base_font_size,
    show_words,
    show_word_labels,
    trial_labels,
    orientation,
    marker_size_range=DEFAULT_MARKER_SIZE_RANGE,
    styles=None,
    show_saccades=True,
    show_saccade_arrows=False,
    show_order=False,
    order_font_size=None,
    text_color=WORD_LABEL_COLOR,
    highlight_text_color=HIGHLIGHTED_TEXT_COLOR,
    background_color=None,
    line_spacing=DEFAULT_LINE_SPACING,
    scale_text_to_boxes=True,
) -> Figure:
    """Two-panel comparison: horizontal (side-by-side) or vertical (stacked)."""
    font_family = font_family or FONT_FAMILY
    is_stacked = orientation == "stacked"
    per_panel_w = canvas_width if is_stacked else canvas_width // 2

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
        display_name = _resolve_trial_display_name(
            participant, trial_id, trial_words, trial_labels, idx
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
                display_name=display_name,
                style=style,
                color=style["fix_color"],
            )
        )

    # Size each panel (and the whole figure) the same way the single plot does.
    panel_geoms = []
    for spec in trial_specs:
        x_range, y_range, *_ = _compute_axis_ranges(
            canvas_width,
            canvas_height,
            (spec["trial_fix"], "x", "y"),
            word_frames=[spec["trial_words"]] if not spec["trial_words"].empty else [],
        )
        pf_w, pf_h = _fit_display_size(
            per_panel_w, canvas_height, x_range, y_range, spatial_axes=True
        )
        panel_scale = _display_scale(x_range, y_range, pf_w, pf_h)
        panel_geoms.append(
            dict(x_range=x_range, y_range=y_range, w=pf_w, h=pf_h, scale=panel_scale)
        )

    panel_w = panel_geoms[-1]["w"]
    panel_h = panel_geoms[-1]["h"]
    title_band = 36
    gap = 24
    if is_stacked:
        total_width = panel_w
        total_height = panel_h * 2 + title_band * 2 + gap
    else:
        total_width = panel_w * 2 + gap
        total_height = panel_h + title_band

    fig = mr.new_figure(total_width, total_height, background_color=background_color)

    for idx, (spec, geom) in enumerate(zip(trial_specs, panel_geoms)):
        if is_stacked:
            ax_x = (total_width - panel_w) / 2.0
            ax_y = total_height - (idx + 1) * (panel_h + title_band) - idx * gap
        else:
            ax_x = idx * (panel_w + gap)
            ax_y = 0
        ax = mr.add_axes_px(
            fig, ax_x, ax_y, panel_w, panel_h, background_color=background_color
        )
        _finish_spatial_axes(
            ax, geom["x_range"], geom["y_range"], background_color=background_color
        )
        ax.set_title(spec["display_name"], fontsize=mr.px_to_pt(13), family=font_family)

        if show_words and not spec["trial_words"].empty:
            _add_rect_shapes(
                ax,
                build_word_boxes(spec["trial_words"], color=spec["color"]),
                zorder=_Z_BOX,
            )
        _draw_canvas_border(ax, geom["x_range"], geom["y_range"])
        _add_comparison_fixation_trace(
            ax,
            spec["trial_fix"],
            spec["display_name"],
            spec["style"],
            font_family=font_family,
            scale=geom["scale"],
            show_saccades=show_saccades,
            show_saccade_arrows=show_saccade_arrows,
            show_order=show_order,
            order_font_size=order_font_size,
        )
        if show_word_labels:
            _draw_word_labels(
                ax,
                spec["trial_words"],
                _word_label_font_px(
                    spec["trial_words"],
                    scale=geom["scale"],
                    line_spacing=line_spacing,
                    manual_font_px=base_font_size,
                    scale_text_to_boxes=scale_text_to_boxes,
                ),
                font_family,
                text_color=text_color,
                highlight_text_color=highlight_text_color,
            )
    return fig


def make_comparison_figure(
    words,
    fixations,
    trial_a,
    trial_b,
    *,
    canvas_width,
    canvas_height,
    font_family,
    base_font_size,
    show_words=True,
    show_word_labels=False,
    trial_labels=None,
    layout="overlay",
    marker_size_range=DEFAULT_MARKER_SIZE_RANGE,
    style_a=None,
    style_b=None,
    show_saccades=True,
    show_saccade_arrows=False,
    show_order=False,
    order_font_size=None,
    text_color=WORD_LABEL_COLOR,
    highlight_text_color=HIGHLIGHTED_TEXT_COLOR,
    background_color=None,
    line_spacing=DEFAULT_LINE_SPACING,
    scale_text_to_boxes=True,
) -> Figure:
    if layout in {"side_by_side", "stacked"}:
        return _make_split_comparison_figure(
            words,
            fixations,
            trial_a,
            trial_b,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            font_family=font_family,
            base_font_size=base_font_size,
            show_words=show_words,
            show_word_labels=show_word_labels,
            trial_labels=trial_labels,
            orientation=layout,
            marker_size_range=marker_size_range,
            styles=(style_a, style_b),
            show_saccades=show_saccades,
            show_saccade_arrows=show_saccade_arrows,
            show_order=show_order,
            order_font_size=order_font_size,
            text_color=text_color,
            highlight_text_color=highlight_text_color,
            background_color=background_color,
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
        )

    font_family = font_family or FONT_FAMILY
    overrides = (style_a, style_b)

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
        display_name = _resolve_trial_display_name(
            participant, trial_id, trial_words, trial_labels, idx
        )
        style = _comparison_scanpath_style(
            idx, overrides[idx], default_marker_size_range=marker_size_range
        )
        trial_specs.append(
            dict(
                trial_words=trial_words,
                trial_fix=trial_fix,
                display_name=display_name,
                style=style,
                color=style["fix_color"],
            )
        )

    x_range, y_range, *_ = _compute_axis_ranges(
        canvas_width,
        canvas_height,
        *((spec["trial_fix"], "x", "y") for spec in trial_specs),
        word_frames=[
            s["trial_words"] for s in trial_specs if not s["trial_words"].empty
        ],
    )
    fitted_w, fitted_h = _fit_display_size(
        canvas_width, canvas_height, x_range, y_range, spatial_axes=True
    )
    overlay_scale = _display_scale(x_range, y_range, fitted_w, fitted_h)

    fig = mr.new_figure(
        fitted_w, fitted_h + _OVERLAY_TOP_PX, background_color=background_color
    )
    ax = mr.add_axes_px(
        fig, 0, 0, fitted_w, fitted_h, background_color=background_color
    )
    _finish_spatial_axes(ax, x_range, y_range, background_color=background_color)

    legend_handles, legend_labels = [], []
    for spec in trial_specs:
        if show_words:
            _add_rect_shapes(
                ax,
                build_word_boxes(spec["trial_words"], color=spec["color"]),
                zorder=_Z_BOX,
            )
        if show_word_labels:
            _draw_word_labels(
                ax,
                spec["trial_words"],
                _word_label_font_px(
                    spec["trial_words"],
                    scale=overlay_scale,
                    line_spacing=line_spacing,
                    manual_font_px=base_font_size,
                    scale_text_to_boxes=scale_text_to_boxes,
                ),
                font_family,
                text_color=text_color,
                highlight_text_color=highlight_text_color,
            )
        coll = _add_comparison_fixation_trace(
            ax,
            spec["trial_fix"],
            spec["display_name"],
            spec["style"],
            font_family=font_family,
            scale=overlay_scale,
            show_saccades=show_saccades,
            show_saccade_arrows=show_saccade_arrows,
            show_order=show_order,
            order_font_size=order_font_size,
        )
        if coll is not None:
            legend_handles.append(_legend_proxy(spec["color"]))
            legend_labels.append(spec["display_name"])

    _draw_canvas_border(ax, x_range, y_range)
    ax.set_title("Overlay comparison", fontsize=mr.px_to_pt(14), family=font_family)
    if legend_handles:
        _add_top_legend(ax, legend_handles, legend_labels, font_family=font_family)
    return fig


# =============================================================================
# Reading-research figures: per-word bar, fixation-duration histogram, trends
# =============================================================================
def _research_fig(canvas_width: int, height: int, *, font_family: str):
    """A plain (non-spatial) research figure + axes sized in px."""
    font_family = font_family or FONT_FAMILY
    fig = mr.new_figure(int(canvas_width), int(height))
    ax = mr.add_axes_px(
        fig, 64, 52, max(int(canvas_width) - 88, 80), max(int(height) - 84, 60)
    )
    ax.grid(True, axis="y", color="#ececec", linewidth=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return fig, ax, font_family


def _empty_research_fig(canvas_width, height, *, font_family, title):
    fig, ax, _ = _research_fig(canvas_width or 600, height, font_family=font_family)
    ax.set_title(title, fontsize=mr.px_to_pt(14))
    ax.text(
        0.5,
        0.5,
        "No data",
        transform=ax.transAxes,
        ha="center",
        va="center",
        color="#888888",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    return fig


def make_word_measure_bar_figure(
    words: pd.DataFrame,
    *,
    measure: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    height: int = 360,
) -> Figure:
    """Vertical bar plot of a per-word measure, coloured by value."""
    if words.empty or measure not in words.columns:
        return _empty_research_fig(
            canvas_width,
            height,
            font_family=font_family,
            title=f"No data for '{measure}'",
        )
    fig, ax, font_family = _research_fig(canvas_width, height, font_family=font_family)
    ordered = words.sort_values(["line_idx", "word_id"]).reset_index(drop=True)
    labels = [
        f"{int(wid)}: {txt}" if pd.notna(wid) else str(txt)
        for wid, txt in zip(ordered["word_id"], ordered.get("text", ordered["word_id"]))
    ]
    values = pd.to_numeric(ordered[measure], errors="coerce")
    cmap = mr.resolve_cmap(DEFAULT_HEATMAP_COLORSCALE)
    finite = values.dropna()
    norm = Normalize(
        vmin=float(finite.min()) if len(finite) else 0.0,
        vmax=float(finite.max()) if len(finite) else 1.0,
    )
    positions = np.arange(len(labels))
    ax.bar(
        positions,
        values.fillna(0.0).to_numpy(),
        color=[cmap(norm(v)) for v in values.fillna(0.0)],
    )
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, rotation=-45, ha="left", fontsize=mr.px_to_pt(10))
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label(measure.replace("_", " ").title(), fontsize=mr.px_to_pt(11))
    mean_value = float(finite.mean()) if finite.size else None
    if mean_value is not None:
        ax.axhline(
            mean_value,
            color=mr.to_mpl_color(COMPARISON_PALETTE[1]),
            linewidth=mr.px_to_pt(2),
            linestyle=":",
        )
        ax.annotate(
            f"mean {mean_value:.2f}",
            (1.0, mean_value),
            xycoords=("axes fraction", "data"),
            ha="right",
            va="bottom",
            fontsize=mr.px_to_pt(10),
            color=mr.to_mpl_color(COMPARISON_PALETTE[1]),
        )
    ax.set_xlabel("Word")
    ax.set_ylabel(measure.replace("_", " ").title())
    ax.set_title(f"Per-word {measure.replace('_', ' ')}", fontsize=mr.px_to_pt(14))
    return fig


def make_fixation_duration_histogram(
    fixations: pd.DataFrame,
    *,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    bins: int = 30,
    overlay_words: Optional[pd.DataFrame] = None,
    height: int = 320,
) -> Figure:
    """Histogram of fixation durations (server-side pre-binned), with optional
    overlaid FFD/FPRT/TFD series and mean/median markers."""
    if fixations.empty:
        return _empty_research_fig(
            canvas_width,
            height,
            font_family=font_family,
            title="Fixation duration distribution (no data)",
        )
    fig, ax, font_family = _research_fig(canvas_width, height, font_family=font_family)
    durations = pd.to_numeric(fixations["duration_ms"], errors="coerce").dropna()
    series_list = [("All fixations", durations.to_numpy(), COMPARISON_PALETTE[0], 1.0)]
    if overlay_words is not None and not overlay_words.empty:
        for name, col in (
            ("FFD", "first_fixation_ms"),
            ("FPRT", "first_pass_gaze_duration_ms"),
            ("TFD", "total_fixation_duration_ms"),
        ):
            if col in overlay_words.columns:
                vals = pd.to_numeric(overlay_words[col], errors="coerce").dropna()
                if not vals.empty:
                    series_list.append((name, vals.to_numpy(), None, 0.4))

    all_vals = np.concatenate([arr for _, arr, _, _ in series_list])
    lo = float(all_vals.min()) if all_vals.size else 0.0
    hi = float(all_vals.max()) if all_vals.size else 1.0
    if hi <= lo:
        hi = lo + 1.0
    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    bar_width = float(edges[1] - edges[0])
    palette = iter(_QUALITATIVE_PALETTE[1:])
    for name, arr, color, opacity in series_list:
        counts, _ = np.histogram(arr, bins=edges)
        col = (
            mr.to_mpl_color(color)
            if color is not None
            else mr.to_mpl_color(next(palette))
        )
        ax.bar(
            centers,
            counts,
            width=bar_width,
            label=name,
            alpha=opacity,
            color=col,
            edgecolor="white",
            linewidth=0.5,
        )
    mean_ms = float(durations.mean()) if len(durations) else 0.0
    median_ms = float(durations.median()) if len(durations) else 0.0
    ax.axvline(
        mean_ms,
        color=mr.to_mpl_color(COMPARISON_PALETTE[1]),
        linewidth=mr.px_to_pt(2),
        linestyle="--",
        label=f"mean {mean_ms:.0f} ms",
    )
    ax.axvline(
        median_ms,
        color=mr.to_mpl_color(SACCADE_COLOR),
        linewidth=mr.px_to_pt(2),
        linestyle=":",
        label=f"median {median_ms:.0f} ms",
    )
    ax.set_xlabel("Duration (ms)")
    ax.set_ylabel("Count")
    ax.set_title("Fixation duration distribution", fontsize=mr.px_to_pt(14))
    ax.legend(fontsize=mr.px_to_pt(10), frameon=False)
    return fig


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
    y_range: Tuple[float, float] = (0.0, 1.02),
    highlight_x_range: Optional[Tuple[float, float]] = None,
) -> Figure:
    """Line chart of a metric (one line per model) over a cumulative x axis."""
    fig, ax, font_family = _research_fig(canvas_width, height, font_family=font_family)
    has_data = False
    for i, (name, xy) in enumerate(series.items()):
        xs, ys = xy
        if not len(xs):
            continue
        has_data = True
        color = mr.to_mpl_color(_QUALITATIVE_PALETTE[i % len(_QUALITATIVE_PALETTE)])
        ax.plot(
            list(xs),
            list(ys),
            marker="o",
            markersize=mr.px_to_pt(4),
            linewidth=mr.px_to_pt(2),
            color=color,
            label=str(name),
        )
    if has_data and highlight_x_range is not None:
        lo, hi = highlight_x_range
        if hi > lo:
            ax.axvspan(lo, hi, facecolor="#6c757d", alpha=0.10, linewidth=0)
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_ylim(y_range[0], y_range[1])
    ax.set_title(title, fontsize=mr.px_to_pt(14))
    if has_data:
        ax.legend(fontsize=mr.px_to_pt(10), frameon=False)
    else:
        ax.text(
            0.5,
            0.5,
            "No data",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color="#888888",
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
) -> Figure:
    """Line+marker trend of ``value`` vs ``x_col`` with a ±SEM shaded band."""
    if df is None or df.empty:
        return _empty_research_fig(
            canvas_width, height, font_family=font_family, title=f"{title} (no data)"
        )
    fig, ax, font_family = _research_fig(canvas_width, height, font_family=font_family)
    xs = df[x_col].to_numpy()
    ys = df["value"].to_numpy()
    sem = df["sem"].to_numpy() if "sem" in df.columns else np.zeros(len(xs))
    ax.fill_between(
        xs,
        ys - sem,
        ys + sem,
        color=(31 / 255, 119 / 255, 180 / 255, 0.15),
        linewidth=0,
    )
    ax.plot(
        xs,
        ys,
        marker="o",
        markersize=mr.px_to_pt(5),
        linewidth=mr.px_to_pt(2),
        color=mr.to_mpl_color(COMPARISON_PALETTE[0]),
        label=y_label,
    )
    ax.set_xlabel(x_col.replace("_", " ").title())
    ax.set_ylabel(y_label)
    ax.set_title(title, fontsize=mr.px_to_pt(14))
    return fig


def make_aggregated_histogram(
    groups: dict,
    *,
    metric_label: str,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    bins: int = 30,
    height: int = 360,
) -> Figure:
    """Overlaid binned histograms — one series per group (server-side counts)."""
    arrays = [(str(name), np.asarray(arr)) for name, arr in groups.items() if len(arr)]
    if not arrays:
        return _empty_research_fig(
            canvas_width,
            height,
            font_family=font_family,
            title=f"{metric_label} distribution (no data)",
        )
    fig, ax, font_family = _research_fig(canvas_width, height, font_family=font_family)
    all_vals = np.concatenate([arr for _, arr in arrays])
    lo, hi = float(all_vals.min()), float(all_vals.max())
    if hi <= lo:
        hi = lo + 1.0
    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    bar_width = float(edges[1] - edges[0])
    single = len(arrays) == 1
    for i, (name, arr) in enumerate(arrays):
        counts, _ = np.histogram(arr, bins=edges)
        color = mr.to_mpl_color(_QUALITATIVE_PALETTE[i % len(_QUALITATIVE_PALETTE)])
        ax.bar(
            centers,
            counts,
            width=bar_width,
            label=name,
            alpha=0.95 if single else 0.55,
            color=color,
            edgecolor="white",
            linewidth=0.4,
        )
    ax.set_xlabel(metric_label)
    ax.set_ylabel("Count")
    ax.set_title(f"{metric_label} distribution", fontsize=mr.px_to_pt(14))
    if not single:
        ax.legend(fontsize=mr.px_to_pt(10), frameon=False)
    return fig
