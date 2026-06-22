"""Shared constants for the Scanpath Studio app."""

from __future__ import annotations

PACKAGE_NAME = "scanpath_studio"

# Default text font. A single generic family that renders (monospaced) on every
# platform including the Streamlit Cloud demo; the sidebar field accepts any CSS
# font name or stack if you want the exact experiment font.
FONT_FAMILY = "monospace"

DEFAULT_FIGURE_SIZE = (2560, 1440)

# Reading text is drawn true-to-scale: one line of text fills ``1/line_spacing``
# of the line pitch (the word-box height that the data already encodes). OneStop
# rendered each line of text with one blank line above and one below it, so the
# line pitch is 3x the single-line height — hence a default line spacing of 3.
DEFAULT_LINE_SPACING = 3.0

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
# Index 0 of COLORSCALES on purpose: a keyed selectbox first-rendered inside a
# popover (the Heatmap-style popover) displays its first option, not the seeded
# session value, on first open — so a non-index-0 default would show the wrong
# colorscale (and get committed on the next interaction). Keeping the default at
# index 0 keeps the picker and the figure in sync. See controls.sidebar_controls.
DEFAULT_HEATMAP_COLORSCALE = "Blues"

DEFAULT_MARKER_SIZE_RANGE = (8, 24)
DEFAULT_PAGE_SIZE = 1000
DEFAULT_ORDER_FONT_COLOR = "#111111"

WORD_BOX_COLOR = "#6c757d"
WORD_LABEL_COLOR = "#343a40"
# Default colour for highlighted ("Mark text") reading text — dark pink. The
# visualization controls expose a picker that overrides it per figure.
HIGHLIGHTED_TEXT_COLOR = "#C8097C"
SACCADE_COLOR = "#6f42c1"
TRENDLINE_COLOR = "#dc3545"
CURRENT_FIX_COLOR = "rgba(255, 127, 14, 0.6)"
CURRENT_FIX_OUTLINE = "#ff7f0e"
FIX_MARKER_OUTLINE = "#111"
COMPARISON_PALETTE = ["#1f77b4", "#e45756"]

# Saccade line styles offered in the sidebar. Maps the friendly UI label to the
# Plotly ``line.dash`` value used in the figure builders.
SACCADE_DASH_OPTIONS = {
    "Solid": "solid",
    "Dashed": "dash",
    "Dotted": "dot",
    "Dash-dot": "dashdot",
}
# Saccade line width (px): default + the (min, max) the width slider allows.
DEFAULT_SACCADE_WIDTH = 2.0
SACCADE_WIDTH_BOUNDS = (0.5, 10.0)

# Outline width (px) for hollow (outline-only) fixation markers.
HOLLOW_OUTLINE_WIDTH = 2.0

# Distinct mark for fixations that fall outside every word box ("out of text").
OUT_OF_TEXT_COLOR = "#d62728"  # red

# Plot background. Default white; some analyses prefer a neutral gray.
# A "Custom…" entry in the sidebar reveals a free color picker.
DEFAULT_BACKGROUND_COLOR = "#ffffff"
BACKGROUND_PRESETS = {
    "White": "#ffffff",
    "Light gray": "#e9ecef",
    "Gray": "#bdbdbd",
    "Black": "#000000",
}

CANVAS_PAD_MIN_PX = 20.0
CANVAS_PAD_FRACTION = 0.05

CITATION = {
    "authors": "Omer Shubi, LACC Lab (Technion)",
    "title": "Scanpath Studio",
    "url": "https://github.com/lacclab/scanpath-studio",
    "lab_url": "https://lacclab.github.io/",
    "corpus_note": (
        "Bundled demo data is a subset of OneStop Eye Movements: "
        "Berzak, Malmaud, Shubi, Meiri, Lion, Levy (2025), "
        '"OneStop: A 360-Participant English Eye Tracking Dataset with '
        'Different Reading Regimes," Scientific Data. '
        "https://doi.org/10.1038/s41597-025-06272-2"
    ),
}


# --- Data-source identity + main view labels --------------------------------
# Moved out of app.py so url_state.py / wizard.py can import them without a
# cycle (app.py re-imports them for its own use and for tests).
UPLOAD_CHOICE = "Upload tables"
DEMO_CHOICE = "Bundled Demo"
SYNTHETIC_CHOICE = "Synthetic test trial"
PUBLIC_DATASETS_CHOICE = "Public datasets"
POTEC_DEFAULT_DIR = "data/PoTeC"
POTEC_TEXT_IDS = [f"{d}{i}" for d in ("b", "p") for i in range(6)]
MULTIPLEYE_DEFAULT_DIR = "data/MultiplEYE_ZH_CH_Zurich_1_2025"
ONESTOP_CHOICE = "OneStop server bundle"
_VIEW_SCANPATH = "Scanpath Visualization"
_VIEW_CORPUS = "Corpus Analysis"
_MAIN_TAB_LABELS = [_VIEW_SCANPATH, _VIEW_CORPUS]
