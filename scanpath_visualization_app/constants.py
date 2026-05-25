"""Shared constants for the Scanpath Visualization app."""

from __future__ import annotations

PACKAGE_NAME = "scanpath_visualization_app"

# Default monospace stack. Lucida Sans Typewriter is common on Windows; we list
# generic monospace last so any platform falls back gracefully.
FONT_FAMILY = "Lucida Sans Typewriter, Lucida Console, Courier New, monospace"

DEFAULT_FIGURE_SIZE = (2560, 1440)

COLORSCALES = [
    "Blues",
    "Greens",
    "Oranges",
    "Reds",
    "Purples",
    "Greys",
    "Viridis",
    "Plasma",
    "Inferno",
    "Magma",
    "Cividis",
    "Turbo",
    "Hot",
    "YlOrRd",
    "YlGnBu",
    "RdBu",
    "Spectral",
]

DEFAULT_FIXATION_COLORSCALE = "Blues"
DEFAULT_HEATMAP_COLORSCALE = "Oranges"

DEFAULT_MARKER_SIZE_RANGE = (8, 24)
DEFAULT_PAGE_SIZE = 1000
DEFAULT_ORDER_FONT_COLOR = "#111111"

WORD_BOX_COLOR = "#6c757d"
WORD_LABEL_COLOR = "#343a40"
SACCADE_COLOR = "#6f42c1"
TRENDLINE_COLOR = "#dc3545"
CURRENT_FIX_COLOR = "rgba(255, 127, 14, 0.6)"
CURRENT_FIX_OUTLINE = "#ff7f0e"
FIX_MARKER_OUTLINE = "#111"
COMPARISON_PALETTE = ["#1f77b4", "#e45756"]

CANVAS_PAD_MIN_PX = 20.0
CANVAS_PAD_FRACTION = 0.05

CITATION = {
    "authors": "Omer Shubi, LACC Lab (Technion)",
    "title": "Scanpath Visualization App",
    "url": "https://github.com/lacclab/scanpath-visualization",
    "corpus_note": (
        "Bundled demo data is a subset of OneStop Eye Movements: "
        "Berzak, Malmaud, Shubi, Meiri, Lion, Levy (2025), "
        '"OneStop: A 360-Participant English Eye Tracking Dataset with '
        'Different Reading Regimes," Scientific Data. '
        "https://doi.org/10.1038/s41597-025-06272-2"
    ),
}
