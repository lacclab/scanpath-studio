"""Matplotlib rendering helpers for the scanpath figure builders.

This module is the bridge that makes :mod:`scanpath_studio.plots` render with
matplotlib instead of Plotly while keeping every figure pixel-true to the old
output. It owns three things the builders rely on:

1. **A fixed render DPI and unit conversions.** Plotly sizes text/markers/lines
   in *screen pixels*; matplotlib sizes them in *points* (1 pt = 1/72 in) and
   scatter areas in points². The spatial builders compute a true-to-scale word
   font in screen px (``plots._word_label_font_px``) and size the equal-aspect
   plot region to an exact ``fitted_w × fitted_h`` pixel box. At :data:`DPI`
   that pixel box is reproduced exactly by ``savefig``, and ``px``→``pt``
   conversions are exact — so the rendered glyphs keep filling their boxes.

2. **Plotly-compatible colour parsing.** ``constants.py`` still stores Plotly
   idioms (``"rgba(255,127,14,0.6)"`` strings, ``"dash"`` dash tokens, named
   colorscales like ``"Viridis"``). matplotlib can't parse those directly, so we
   translate them here and leave the constants (and any saved plot configs)
   untouched.

3. **Exact-pixel figure scaffolding.** :func:`new_figure` / :func:`add_axes_px`
   place the data axes at an exact pixel rectangle, reserving margin *outside*
   it for a colorbar / legend / animation controls — the matplotlib analog of
   Plotly's ``automargin=False`` + ``_decoration_margins`` so decorations never
   shrink the equal-aspect plot (which would break the true-to-scale text).
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

import matplotlib

# Headless, server-side rendering: never touch a GUI backend (the app runs under
# Streamlit and the CLI/exports run with no display).
matplotlib.use("Agg")

# The interactive animation player (``FuncAnimation.to_jshtml``) inlines every
# frame as a base64 PNG. A long reading has hundreds of frames, which exceeds
# matplotlib's default 20 MB embed cap — and over the cap it silently *drops*
# frames. Raise it generously so the on-screen replay is always complete.
matplotlib.rcParams["animation.embed_limit"] = 256.0  # MB

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import colormaps  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.colors import to_rgba  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

# Fixed render DPI. The spatial builders size the AXES box to exactly
# ``fitted_w × fitted_h`` *pixels*; at this DPI a saved figure is exactly that
# many pixels and the screen-px → point conversions below are exact, so the
# true-to-scale word labels keep matching the boxes. 100 keeps the inch sizes
# (px / 100) tidy and the integer-px math round-trips cleanly.
DPI = 100.0


# ---------------------------------------------------------------------------
# Unit conversions (Plotly screen px ↔ matplotlib points / areas)
# ---------------------------------------------------------------------------
def px_to_pt(px):
    """Convert a screen-pixel length to typographic points at :data:`DPI`.

    Works on scalars or numpy arrays. Used for font sizes (``fontsize``) and
    line widths (``linewidth``), which matplotlib expresses in points.
    """
    return np.asarray(px, dtype=float) * 72.0 / DPI


def marker_area(diameter_px):
    """``scatter(s=…)`` area (points²) for a marker of the given pixel diameter.

    Plotly's ``marker.size`` is a pixel *diameter*; matplotlib's ``s`` is a
    point *area*. A marker drawn with area ``s`` has diameter ``sqrt(s)`` pt, so
    matching a pixel diameter means ``s = px_to_pt(diameter)²``.
    """
    d_pt = px_to_pt(diameter_px)
    return d_pt * d_pt


def figure_px_size(fig) -> Tuple[int, int]:
    """The figure's pixel ``(width, height)`` — the matplotlib replacement for
    Plotly ``fig.layout.width / fig.layout.height`` that the render/export layers
    read."""
    w_in, h_in = fig.get_size_inches()
    return int(round(w_in * fig.dpi)), int(round(h_in * fig.dpi))


# ---------------------------------------------------------------------------
# Colour / colorscale / dash translation (Plotly idioms → matplotlib)
# ---------------------------------------------------------------------------
_RGBA_RE = re.compile(r"\s*rgba?\(([^)]+)\)\s*", re.IGNORECASE)


def to_mpl_color(color, default=None):
    """Parse a colour into an ``(r, g, b, a)`` tuple matplotlib understands.

    Accepts the CSS ``rgb()`` / ``rgba()`` strings that ``constants.py`` stores
    (matplotlib can't parse these), plus hex, named colours, and existing RGBA
    tuples (passed through ``matplotlib.colors.to_rgba``). ``None`` returns
    ``default``.
    """
    if color is None:
        return default
    if isinstance(color, str):
        m = _RGBA_RE.fullmatch(color)
        if m:
            parts = [p.strip() for p in m.group(1).split(",")]
            r, g, b = (
                float(parts[0]) / 255.0,
                float(parts[1]) / 255.0,
                float(parts[2]) / 255.0,
            )
            a = float(parts[3]) if len(parts) > 3 else 1.0
            return (r, g, b, a)
    return to_rgba(color)


# Plotly named colorscales whose matplotlib colormap name differs only in case.
# The perceptual maps are lowercase-only in matplotlib; the sequential/diverging
# ones (Blues, Oranges, RdBu, Spectral, YlOrRd, YlGnBu, Greys, …) keep their
# capitalised names, so they fall through unchanged.
_CMAP_ALIASES = {
    "Viridis": "viridis",
    "Plasma": "plasma",
    "Inferno": "inferno",
    "Magma": "magma",
    "Cividis": "cividis",
    "Turbo": "turbo",
    "Hot": "hot",
}


def resolve_cmap(name: Optional[str]):
    """Return a matplotlib ``Colormap`` for a Plotly/matplotlib colorscale name.

    Maps the perceptual Plotly names (``"Viridis"`` …) to their lowercase
    matplotlib spelling and falls back to ``Blues`` for anything unknown so a
    stray name can never crash a figure build.
    """
    if not name:
        name = "Blues"
    key = _CMAP_ALIASES.get(name, name)
    for candidate in (key, str(key).lower(), "Blues"):
        try:
            return colormaps[candidate]
        except KeyError:
            continue
    return colormaps["Blues"]


def sample_colors(values, colorscale: str, cmin=None, cmax=None) -> np.ndarray:
    """Map numeric ``values`` through a colorscale to an ``(N, 4)`` RGBA array.

    The matplotlib analog of ``plotly.colors.sample_colorscale`` used by the
    hollow-marker / word-box-heatmap paths: normalise to ``[cmin, cmax]`` (the
    data range when not given) and look the colours up in the colormap. Degenerate
    ranges map everything to the colormap midpoint, mirroring the old behaviour.
    """
    cmap = resolve_cmap(colorscale)
    vals = pd.to_numeric(pd.Series(list(values)), errors="coerce")
    lo = (
        float(cmin)
        if cmin is not None
        else float(np.nanmin(vals))
        if len(vals)
        else 0.0
    )
    hi = (
        float(cmax)
        if cmax is not None
        else float(np.nanmax(vals))
        if len(vals)
        else 1.0
    )
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        norm = np.full(len(vals), 0.5)
    else:
        norm = ((vals.clip(lo, hi) - lo) / (hi - lo)).fillna(0.0).to_numpy()
    return cmap(norm)


# Plotly ``line.dash`` token → matplotlib ``linestyle``. Tolerant of both the
# Plotly tokens stored in ``constants.SACCADE_DASH_OPTIONS`` and raw matplotlib
# linestyles, so callers (and saved configs) can pass either.
_LINESTYLE = {
    "solid": "-",
    "dash": "--",
    "dot": ":",
    "dashdot": "-.",
    "-": "-",
    "--": "--",
    ":": ":",
    "-.": "-.",
}


def mpl_linestyle(token: Optional[str]) -> str:
    """Translate a Plotly ``line.dash`` token to a matplotlib ``linestyle``."""
    return _LINESTYLE.get(token or "solid", "-")


# ---------------------------------------------------------------------------
# Exact-pixel figure scaffolding
# ---------------------------------------------------------------------------
def new_figure(width_px: int, height_px: int, *, background_color=None):
    """A figure sized to exactly ``width_px × height_px`` at :data:`DPI`.

    ``savefig`` at :data:`DPI` (which the render/export layers use) then yields
    exactly that many pixels. ``background_color`` paints the figure *paper*
    (Plotly ``paper_bgcolor``); ``None`` leaves the matplotlib default (white).

    The figure is built directly (with an Agg canvas) rather than via
    ``pyplot.figure`` so it is *not* registered in pyplot's global figure manager
    — otherwise every Streamlit rerun would leak a figure. ``savefig`` and
    ``FuncAnimation`` work fine on this detached figure.
    """
    fig = Figure(figsize=(width_px / DPI, height_px / DPI), dpi=DPI)
    FigureCanvasAgg(fig)  # attaches as fig.canvas; enables savefig / animation
    if background_color is not None:
        fig.patch.set_facecolor(to_mpl_color(background_color))
    return fig


def add_axes_px(fig, x: float, y: float, w: float, h: float, *, background_color=None):
    """Add an Axes at a *pixel* rectangle measured from the figure's lower-left.

    ``(x, y)`` is the lower-left corner and ``(w, h)`` the size, all in pixels —
    the matplotlib analog of pinning a Plotly margin so the data plot occupies an
    exact pixel box and decorations live in the reserve around it.
    ``background_color`` paints the axes (Plotly ``plot_bgcolor``).
    """
    fig_w, fig_h = figure_px_size(fig)
    ax = fig.add_axes([x / fig_w, y / fig_h, w / fig_w, h / fig_h])
    if background_color is not None:
        ax.set_facecolor(to_mpl_color(background_color))
    return ax


def strip_spatial_axes(ax) -> None:
    """Hide ticks/spines for a spatial (scanpath) axes while keeping its
    background patch (so ``plot_bgcolor`` still shows). The black canvas border
    is drawn separately as a data-space rectangle, mirroring Plotly."""
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def save_to_buffer(fig, fmt: str, *, scale: float = 1.0) -> bytes:
    """Render ``fig`` to ``fmt`` bytes (``png``/``svg``/``pdf``) with no browser.

    PNG honours ``scale`` as a DPI multiplier (retina/poster export); SVG/PDF are
    vector and ignore it. The figure is saved at its own size with no tight bbox
    so the pixel dimensions stay exactly what the builder sized — any bbox trim
    would desync the true-to-scale text and break the MP4 even-dimension
    assumption in the animation exporter.
    """
    import io

    buf = io.BytesIO()
    save_dpi = DPI * float(scale) if fmt == "png" else DPI
    fig.savefig(
        buf, format=fmt, dpi=save_dpi, facecolor=fig.get_facecolor(), edgecolor="none"
    )
    return buf.getvalue()
