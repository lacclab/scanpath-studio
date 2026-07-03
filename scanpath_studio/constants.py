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


def compare_palette_color(idx: int) -> str:
    """Default A/B colour for comparison scanpath ``idx`` — the single source of
    truth shared by the per-scanpath style controls (``controls._seed_compare_styles``
    / ``_collect_compare_styles``) and the figure builders
    (``plots._comparison_scanpath_style``), so the swatch shown in the controls can
    never drift from what's drawn (CMP-3)."""
    return COMPARISON_PALETTE[idx % len(COMPARISON_PALETTE)]


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

# VIZ-8 · colour saccades by reading type. Each saccade (the segment from one
# fixation to the next) is classified into one of these reading-schematic
# classes by ``measures.classify_saccades`` and — in the "By type" colour mode —
# drawn as its own sub-trace with a small legend. ``other`` is the catch-all for
# saccades that can't be classified (an endpoint fell outside every word box); it
# isn't user-editable, so the palette UI exposes only the five reading classes.
# Order controls the legend order.
SACCADE_CLASS_ORDER = [
    "forward",
    "skip",
    "refixation",
    "return_sweep",
    "regression",
    "other",
]
SACCADE_CLASS_LABELS = {
    "forward": "Forward",
    "skip": "Skip",
    "refixation": "Refixation",
    "return_sweep": "Return sweep",
    "regression": "Regression",
    "other": "Other",
}
SACCADE_CLASS_COLORS = {
    "forward": "#2ca02c",  # green — normal left-to-right progression
    "skip": "#1f77b4",  # blue — jumps over one or more words
    "refixation": "#9467bd",  # purple — lands back on the same word
    "return_sweep": "#ff7f0e",  # orange — long sweep to the next line
    "regression": "#d62728",  # red — moves backward
    "other": "#7f7f7f",  # grey — unclassifiable (off-text endpoint)
}
# The five reading classes the palette UI lets the user recolour (``other`` is
# fixed grey).
SACCADE_CLASS_EDITABLE = SACCADE_CLASS_ORDER[:-1]

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

# --- App theme (BUG-6) -------------------------------------------------------
# The branded look. Streamlit only auto-loads ``.streamlit/config.toml`` relative
# to the *launch* directory, so ``streamlit run streamlit_app.py`` from ``app/``
# (Streamlit Cloud) picks it up but ``python -m scanpath_studio`` from anywhere
# else — or a ``pip``-installed console script, which never ships that file —
# falls back to Streamlit's default red accent. ``cli.launch_app`` injects these
# as ``--theme.*`` flags so every launch path renders the same theme regardless
# of the working directory. Kept in sync with ``app/.streamlit/config.toml`` —
# ``tests/test_theme.py`` asserts parity so the two can't drift.
APP_THEME = {
    "base": "light",
    "primaryColor": "#1f77b4",
    "backgroundColor": "#ffffff",
    "secondaryBackgroundColor": "#f5f7fa",
    "textColor": "#212529",
    "font": "sans-serif",
}
# Dark-variant overrides ([theme.dark] in config.toml). Users switch via the ☰
# menu → Settings → Appearance, or follow their OS.
APP_THEME_DARK = {
    "primaryColor": "#5aa9e6",
    "backgroundColor": "#0e1117",
    "secondaryBackgroundColor": "#1c2030",
    "textColor": "#e8eaed",
}

CITATION = {
    "authors": (
        "Omer Shubi, Keren Gruteke Klein, Ella Lion, Deborah Jacobi, "
        "David Reiche, Lena Jäger, Yevgeni Berzak"
    ),
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
MULTIPLEYE_DEFAULT_DIR = "data/MultiplEYE_ZH_CH_Zurich_1_2025"
ONESTOP_CHOICE = "OneStop server bundle"
# Public OneStop (OSF download-on-demand) — distinct from the env-var
# ONESTOP_CHOICE server bundle. Reading regimes map to the OSF reports the
# loader fetches (see datasets._ONESTOP_REGIMES); labels are the picker text.
# The registry label for the public OneStop corpus in the flat data-source picker.
# A named constant (not an inline string) so the deep-link/Share contract in
# url_state.py can reference it without importing app.py's PUBLIC_DATASET_REGISTRY
# (DATA-3: the public source + its variant/regime/parts are shareable).
ONESTOP_PUBLIC_CHOICE = "OneStop — 360-participant English corpus"
ONESTOP_PUBLIC_DEFAULT_DIR = "data/OneStop"
# Default folder for the lacclab OneStop variant (a lab-processed local export;
# superset schema, no download). Path-editable in the sidebar and overridable via
# the `ONESTOP_LACCLAB_DIR` env var — never the *only* option, just the default.
ONESTOP_LACCLAB_DEFAULT_DIR = (
    "/Users/shubi/Library/CloudStorage/OneDrive-Technion/In-lab Experiments/"
    "OneStopGaze L1 English/Reports/lacclab"
)
ONESTOP_REGIME_LABELS = {
    "ordinary": "Ordinary reading",
    "information_seeking": "Information seeking",
    "repeated": "Repeated reading",
    "information_seeking_repeated": "Information seeking (repeated)",
}
# OneStop trial parts (screens) → display label, in presentation order. Mirrors
# datasets._ONESTOP_PARTS; the sidebar multiselect + the parts URL/CLI contract
# use these keys. Paragraph is the reading passage (the default).
ONESTOP_PART_LABELS = {
    "Title": "Title",
    "Question_Preview": "Question preview",
    "Paragraph": "Paragraph",
    "Questions": "Question",
    "Answers": "Answers",
    "QA": "Question + answers (QA)",
    "Feedback": "Feedback",
}
# OneStop source variants → display label. `public` downloads from OSF on demand;
# `lacclab` reads a lab-processed local export (superset schema, no download).
ONESTOP_VARIANT_LABELS = {
    "public": "Public (OSF download)",
    "lacclab": "LaCC lab (local export)",
}
MULTIPLEYE_BUNDLE_CHOICE = "MultiplEYE server bundle"
# Default dir for the MultiplEYE *server bundle* (per-session parquet shards
# under `<dir>/scanpath/`), overridable via the `MULTIPLEYE_DATA_DIR` env var.
# Empty default so the source only appears when the env var is set (like the
# OneStop server bundle). Distinct from MULTIPLEYE_DEFAULT_DIR above, which is
# the public-corpus loader's tree.
MULTIPLEYE_BUNDLE_DEFAULT_DIR = ""
_VIEW_SCANPATH = "Scanpath Visualization"
_VIEW_CORPUS = "Corpus Analysis"
_MAIN_TAB_LABELS = [_VIEW_SCANPATH, _VIEW_CORPUS]
