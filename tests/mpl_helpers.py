"""Helpers for asserting on the matplotlib figures the builders now return.

The builders label their artists so tests look them up **by label**, not by
positional index — matplotlib's add-order / zorder differs from the old Plotly
trace order, so a positional ``fig.data[1]`` has no stable equivalent.

Stable artist contract (on the data ``Axes`` = ``fig.axes[0]``):

==================  ==============================  ===================
layer               matplotlib artist               label
==================  ==============================  ===================
word boxes          ``Rectangle`` patches           (none; count them)
critical span       ``Rectangle`` patches           (none)
canvas border       ``Rectangle`` patch             ``"canvas-border"``
word labels         ``Text``                        ``"words"``
fixations           ``PathCollection``              ``"Fixations"``
saccades            ``LineCollection``              ``"saccades"``
saccade arrows      ``Quiver``                      ``"saccade direction"``
raw gaze            ``PathCollection``              ``"Raw gaze"``
out-of-text         ``PathCollection``              ``"Out-of-text"``
word-box heatmap    ``Rectangle`` patches (alpha)   (none)
density heatmap      ``QuadMesh``                    (none)
interpolated heatmap ``AxesImage`` (``ax.images``)  (none)
comparison fix       ``PathCollection``              the trial display name
==================  ==============================  ===================

A numeric colorbar / a legend live in *extra* axes added beside the data axes,
so ``fig.axes[0]`` stays the data plot. Colours come from a categorical legend
(``ax.get_legend()``) or a fixed ``Normalize`` on the fixation collection.
"""

from __future__ import annotations

from matplotlib.collections import LineCollection, PathCollection, QuadMesh
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.quiver import Quiver

from scanpath_studio import mpl_render as mr


def data_axes(ax_or_fig):
    """The main data Axes (``axes[0]``; colorbars/legends are later axes).

    Accepts either a ``Figure`` (returns its first Axes) or an ``Axes`` (returned
    as-is) so the lookup helpers can call it idempotently.
    """
    if isinstance(ax_or_fig, Figure):
        return ax_or_fig.axes[0]
    return ax_or_fig


def figure_px(fig):
    """The figure's pixel ``(width, height)`` — replaces ``fig.layout.width/height``."""
    return mr.figure_px_size(fig)


def collection(ax, label):
    """First collection on ``ax`` with ``get_label() == label`` (or ``None``).

    Excludes ``Quiver`` (an arrow collection) so ``collection(ax, "saccades")``
    can't accidentally match an arrow trace.
    """
    ax = data_axes(ax)
    for c in ax.collections:
        if c.get_label() == label and not isinstance(c, Quiver):
            return c
    return None


def path_collection(ax, label):
    ax = data_axes(ax)
    for c in ax.collections:
        if isinstance(c, PathCollection) and c.get_label() == label:
            return c
    return None


def line_collection(ax, label="saccades"):
    ax = data_axes(ax)
    for c in ax.collections:
        if (
            isinstance(c, LineCollection)
            and not isinstance(c, Quiver)
            and c.get_label() == label
        ):
            return c
    return None


def quiver(ax, label="saccade direction"):
    ax = data_axes(ax)
    for c in ax.collections:
        if isinstance(c, Quiver) and c.get_label() == label:
            return c
    return None


def quivers(ax):
    ax = data_axes(ax)
    return [c for c in ax.collections if isinstance(c, Quiver)]


def texts(ax, label):
    ax = data_axes(ax)
    return [t for t in ax.texts if t.get_label() == label]


def word_label_texts(ax):
    return texts(ax, "words")


def rectangles(ax):
    """All ``Rectangle`` patches on the data axes (word boxes, border, span, …)."""
    ax = data_axes(ax)
    return [p for p in ax.patches if isinstance(p, Rectangle)]


def has_density_mesh(ax):
    ax = data_axes(ax)
    return any(isinstance(c, QuadMesh) for c in ax.collections)


def has_axes_image(ax):
    ax = data_axes(ax)
    return len(ax.images) > 0


def legend_labels(ax):
    """The set of legend entry labels (or empty set if no legend)."""
    ax = data_axes(ax)
    leg = ax.get_legend()
    if leg is None:
        return set()
    return {t.get_text() for t in leg.get_texts()}


def n_drawn_layers(ax):
    """Collections + line/quiver + images — the matplotlib analog of the old
    'len(fig.data)' trace count (used by the perf-bound smoke test)."""
    ax = data_axes(ax)
    return len(ax.collections) + len(ax.images)


def word_label_px(fig):
    """The word-label font size read back in *screen px* (the unit
    ``_word_label_font_px`` returns), for true-to-scale assertions."""
    ax = data_axes(fig)
    ws = word_label_texts(ax)
    if not ws:
        return None
    # matplotlib fontsize is in points; convert back to px at the render DPI.
    return float(ws[0].get_fontsize()) * mr.DPI / 72.0
