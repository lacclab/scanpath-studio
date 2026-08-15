"""Shared constants for the Scanpath Studio app."""

from __future__ import annotations

import os

PACKAGE_NAME = "scanpath_studio"


# --- PRE-21: features that are built but not fully integrated ----------------
# Vertical drift correction (the PRE-3 port of Carr et al. 2021) and the NLD
# similarity scoring under 🔬 Comparisons both work, and both are half-wired:
# the similarity table still shows three metrics as "Not yet computed", and the
# drift-correction subtab's follow-ups (PRE-9, PRE-10) are unfinished. Shipping
# them visible invites users to lean on them, so ahead of publication they are
# gated off — a **visibility gate, not a removal**: `alignment.py` and
# `similarity.py` stay exactly where they are and stay reachable for us.
#
# Polarity is the opposite of `app.public_datasets_enabled`: these default
# **off** and the env var turns them on. Read at *call time*, which is both what
# lets a test toggle them and what stops a stale import-time read from making
# one surface disagree with another.
EXPERIMENTAL_ENV_VAR = "SCANPATH_EXPERIMENTAL"


def experimental_features_enabled() -> bool:
    """Whether the not-fully-integrated features are exposed (PRE-21).

    Off unless ``SCANPATH_EXPERIMENTAL`` is set to something truthy.
    """
    return os.environ.get(EXPERIMENTAL_ENV_VAR, "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def drift_correction_enabled() -> bool:
    """Whether vertical drift correction / line assignment is exposed (PRE-21)."""
    return experimental_features_enabled()


def similarity_enabled() -> bool:
    """Whether NLD scanpath-similarity scoring is exposed (PRE-21)."""
    return experimental_features_enabled()


# Default text font. A single generic family that renders (monospaced) on every
# platform including the Streamlit Cloud demo; the sidebar field accepts any CSS
# font name or stack if you want the exact experiment font.
FONT_FAMILY = "monospace"

# The demo corpus' own presentation monitor, so a figure with no declared
# canvas still renders true-to-scale. Sourced once, in
# `eyegenbench_geometry.DISPLAY_SPECS["onestop"]` (Berzak et al. 2025, Sci Data
# 12:1995 — Dell U2715H, 2560 px × 1440 px over 597 mm × 336 mm).
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

# VIZ-32: colourblind-safe (Viridis) is the default a fresh session opens with.
# A keyed selectbox first-rendered inside a popover would otherwise display its
# first option rather than a non-index-0 seeded value on first open — handled by
# `controls._popover_selectbox` (explicit `index=`) / `_pin` + `persist_state`, so a
# non-index-0 default here still keeps the picker and the figure in sync.
DEFAULT_FIXATION_COLORSCALE = "Viridis"
DEFAULT_HEATMAP_COLORSCALE = "Viridis"

DEFAULT_MARKER_SIZE_RANGE = (8, 24)
DEFAULT_PAGE_SIZE = 1000
DEFAULT_ORDER_FONT_COLOR = "#111111"

WORD_BOX_COLOR = "#6c757d"
# VIZ-32: black, matching the colourblind-safe default palette.
WORD_LABEL_COLOR = "#000000"
# Default colour for highlighted ("Mark text") reading text — vermillion,
# matching the colourblind-safe default palette. The visualization controls
# expose a picker that overrides it per figure.
HIGHLIGHTED_TEXT_COLOR = "#D55E00"
# VIZ-32: reddish purple, matching the colourblind-safe default palette.
SACCADE_COLOR = "#CC79A7"
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
# VIZ-32: Okabe-Ito, matching the colourblind-safe default palette.
SACCADE_CLASS_COLORS = {
    "forward": "#009E73",  # bluish green — normal left-to-right progression
    "skip": "#56B4E9",  # sky blue — jumps over one or more words
    "refixation": "#CC79A7",  # reddish purple — lands back on the same word
    "return_sweep": "#E69F00",  # orange — long sweep to the next line
    "regression": "#D55E00",  # vermillion — moves backward
    "other": "#999999",  # grey — unclassifiable (off-text endpoint)
}
# The five reading classes the palette UI lets the user recolour (``other`` is
# fixed grey).
SACCADE_CLASS_EDITABLE = SACCADE_CLASS_ORDER[:-1]

# VIZ-19 · saccade colour modes. The five-way "By type" split is more than most
# figures need, so there's a middle option between one flat colour and the full
# reading-class breakdown: "Forward / regression", the distinction almost every
# reading paper actually draws. It reuses the same per-class machinery — the
# classes are just folded into two buckets before the segments are built, so the
# colour pickers, the legend toggle and every surface stay as they are.
SACCADE_COLOR_MODES = ("Uniform", "Forward / regression", "By type")
SACCADE_DIRECTION_CLASSES = ("forward", "regression")
# reading class → the bucket it is drawn in under "Forward / regression".
# ``other`` stays ``other`` (grey catch-all) so unclassifiable saccades aren't
# silently counted as progressive.
SACCADE_DIRECTION_FOLD = {
    "forward": "forward",
    "skip": "forward",
    "refixation": "forward",
    "return_sweep": "forward",
    "regression": "regression",
    "other": "other",
}
SACCADE_DIRECTION_LABELS = {
    "forward": "Forward",
    "regression": "Regression",
    "other": "Other",
}

# VIZ-15 · fixation marker shape. Plotly symbol name → the label shown in the
# picker. Shape is a *second* encoding channel, and unlike hue it survives
# greyscale printing — so it pairs with VIZ-17 (colour freed up once it stops
# duplicating size) and VIZ-18 (print / colourblind palettes).
FIXATION_SYMBOLS = {
    "circle": "● Circle",
    "square": "■ Square",
    "diamond": "◆ Diamond",
    "triangle-up": "▲ Triangle",
    "cross": "✚ Cross",
    "x": "✖ X",
    "star": "★ Star",
    "hexagon": "⬡ Hexagon",
    "heart": "♥ Heart",
}
DEFAULT_FIXATION_SYMBOL = "circle"

# Shapes Plotly's ``marker.symbol`` enum doesn't have. They're drawn as *text*
# glyphs instead — a Scatter in text mode, sized per point via an array
# ``textfont.size``, so duration→size still holds. Kept as a mapping so adding
# another glyph shape needs no new branch in the figure builder.
# Glyphs render at roughly half the visual weight of a marker of the same
# nominal size, so the sizes are scaled up to match the other shapes.
FIXATION_GLYPH_SYMBOLS = {"heart": "♥"}
FIXATION_GLYPH_SIZE_SCALE = 1.8

# VIZ-17 · the "Color fixations by" option meaning *don't* map a variable to hue.
# Marker size already encodes fixation duration, so colouring by duration too
# double-encodes one variable and spends the colour channel on nothing. The
# default is therefore one flat colour, and colour-by is an explicit opt-in for a
# *different* variable (surprisal, frequency, line, pass index).
UNIFORM_COLOR_FIELD = "(uniform)"
# VIZ-32: blue, matching the colourblind-safe default palette.
DEFAULT_FIXATION_COLOR = "#0072B2"

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


# --- VIZ-18 · selectable palettes --------------------------------------------
# These figures don't only get looked at on the screen they were made on: they go
# into papers (printed, sometimes in black & white) and are read by colourblind
# viewers. One palette can't serve all of that, so the colour defaults are a
# *choice* rather than a constant.
#
# A palette is a preset, not a second rendering path: picking one writes the
# ordinary per-element colour keys, so every existing picker still overrides it
# and every surface (deep link, Save & restore, CLI, API) carries the resulting
# colours with no new plumbing. ``palette_settings`` returns the figure-kwarg
# form; ``controls.apply_palette`` writes the session keys.
#
# Rules each non-default palette follows:
#   * hues distinguishable under deuteranopia/protanopia (no red-vs-green pair
#     carrying meaning on its own), and
#   * **lightness** ordered as well as hue, so the figure still reads after a
#     greyscale conversion. Marker shape (VIZ-15) and the two-way saccade mode
#     (VIZ-19) are the redundant channels when colour alone can't carry it.
PALETTES: dict[str, dict] = {
    # Okabe & Ito's eight-colour set — the de-facto standard for qualitative
    # colourblind-safe encoding — plus Viridis, which is both perceptually
    # uniform and safe across the common deficiencies. VIZ-32: this is the
    # default a fresh session opens with, not just an opt-in choice.
    "Default (colourblind-safe)": {
        "description": "Okabe–Ito hues + Viridis scales; safe for deuteran-, "
        "protan- and tritanopia.",
        "fixation_color": DEFAULT_FIXATION_COLOR,
        "fixation_colorscale": DEFAULT_FIXATION_COLORSCALE,
        "heatmap_colorscale": DEFAULT_HEATMAP_COLORSCALE,
        "saccade_color": SACCADE_COLOR,
        "saccade_class_colors": dict(SACCADE_CLASS_COLORS),
        "word_label_color": WORD_LABEL_COLOR,
        "highlight_text_color": HIGHLIGHTED_TEXT_COLOR,
        "background_color": DEFAULT_BACKGROUND_COLOR,
    },
    # Lightness-only encoding: everything survives a black & white print or
    # photocopy, because nothing depends on hue at all.
    "Print / greyscale": {
        "description": "Greys only — nothing depends on hue, so it survives a "
        "black & white print. Pair with marker shape.",
        "fixation_color": "#1a1a1a",
        "fixation_colorscale": "Greys",
        "heatmap_colorscale": "Greys",
        "saccade_color": "#7a7a7a",
        "saccade_class_colors": {
            # Ordered by lightness, darkest = the thing you're looking for.
            "forward": "#a6a6a6",
            "skip": "#8a8a8a",
            "refixation": "#5e5e5e",
            "return_sweep": "#c4c4c4",
            "regression": "#000000",
            "other": "#d9d9d9",
        },
        "word_label_color": "#333333",
        "highlight_text_color": "#000000",
        "background_color": "#ffffff",
    },
    # Maximum separation from the background and from each other — projectors,
    # low-quality displays, and low-vision viewers.
    "High contrast": {
        "description": "Saturated, dark-on-white hues for projectors and "
        "low-contrast displays.",
        "fixation_color": "#0033cc",
        "fixation_colorscale": "Cividis",
        "heatmap_colorscale": "Cividis",
        "saccade_color": "#cc0000",
        "saccade_class_colors": {
            "forward": "#006600",
            "skip": "#0033cc",
            "refixation": "#6600cc",
            "return_sweep": "#cc6600",
            "regression": "#cc0000",
            "other": "#4d4d4d",
        },
        "word_label_color": "#000000",
        "highlight_text_color": "#cc0066",
        "background_color": "#ffffff",
    },
}
DEFAULT_PALETTE = "Default (colourblind-safe)"
# Not a palette — the honest answer when the live colours match none of them.
# A palette only *presets* the individual colour keys, so the moment one of those
# pickers is changed the selector would otherwise keep naming a palette the figure
# no longer uses. Deliberately kept OUT of ``PALETTES`` so the registry stays the
# set of things that can actually be applied: `--palette` choices, the API's
# expansion, and the deep link all iterate `PALETTES` and must not offer this.
CUSTOM_PALETTE = "Custom"


def palette_settings(name: str) -> dict:
    """Figure-kwarg colour settings for palette ``name`` (falls back to Default).

    Returns a fresh dict (nested ``saccade_class_colors`` copied too), so callers
    can mutate the result without corrupting the registry.
    """
    entry = PALETTES.get(name) or PALETTES[DEFAULT_PALETTE]
    settings = {k: v for k, v in entry.items() if k != "description"}
    settings["saccade_class_colors"] = dict(settings["saccade_class_colors"])
    return settings


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

#: Per-file upload ceiling, in MB. Streamlit's own default is **200 MB**, which
#: is far under a real eye-tracking export — a single zipped fixation report for
#: one OneStop regime already runs to tens of MB, and a full corpus is orders
#: above that. Kept in sync with ``.streamlit/config.toml``'s
#: ``server.maxUploadSize``; `cli._max_upload_cli_flags` passes it explicitly
#: because that config file is resolved against the *launch* directory, so a
#: pip-installed console script started from anywhere else silently fell back to
#: the 200 MB default. This is the transport limit only — what a machine can
#: actually parse is a separate question, which `data.UPLOAD_SIZE_WARN_BYTES`
#: answers for the memory-capped hosted demo.
UPLOAD_MAX_SIZE_MB = 5000

CITATION = {
    "authors": (
        "Omer Shubi, Keren Gruteke Klein, Ella Lion, Deborah N. Jakobi, "
        "David R. Reich, Lena Jäger, Yevgeni Berzak"
    ),
    "title": "Scanpath Studio",
    "url": "https://github.com/lacclab/scanpath-studio",
    "docs_url": "https://lacclab.github.io/scanpath-studio/",
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
AUTHOR_CHOICE = "Author a scanpath"
DEMO_CHOICE = "Bundled Demo"
SYNTHETIC_CHOICE = "Synthetic test trial"
PUBLIC_DATASETS_CHOICE = "Public datasets"
POTEC_DEFAULT_DIR = "data/PoTeC"
EYEGENBENCH_DEFAULT_DIR = "data/EyeGenBench"
# DATA-27 (Task 11R): every prepared benchmark corpus is its own top-level entry
# in the flat data-source picker, exactly like PoTeC / MultiplEYE / OneStop —
# there is no "EyeGenBench" source fronting them. Two consequences live in these
# constants:
#
# 1. **"EyeGenBench" is provenance, not a source.** It names the pipeline that
#    harmonises the corpora and is being extracted into its own repository, so
#    it appears in descriptions and help strings only — never in an entry label.
# 2. A corpus entry's label is built from its manifest name (`app.py`), so the
#    only fixed label here is the **bootstrap** entry: when zero corpora are
#    discovered there is nowhere to type the bundle path, so exactly one
#    placeholder entry renders the directory input + prep instructions. It
#    disappears as soon as a corpus is discoverable.
BENCHMARK_SETUP_CHOICE = "Harmonised benchmark corpora — set up a local bundle"
# The suffix that distinguishes a harmonised corpus from a *native* entry for the
# same corpus (PoTeC, OneStop ship both ways). Applied by property — the
# harmonised copy is re-derived and its geometry may be weaker — never by vendor
# name; see consequence 1 above.
BENCHMARK_SHORT_SUFFIX = " (harmonised benchmark)"
# The registry-key suffix. Keys must be unique across the whole registry, and a
# native entry's key is `"<Corpus> — <full name>"`, so this shape can't collide.
BENCHMARK_LABEL_SUFFIX = " — harmonised benchmark corpus"

# DATA-27 R35: a benchmark manifest records `language` as an **ISO 639-1 code**
# ('zh', 'da', 'en', …), not a name, and the picker shows it to a reader. A small
# explicit table beats a dependency for a field this narrow; unknown codes fall
# back to the code itself (never "Unknown" — the code is real information, and
# inventing a placeholder for it loses that).
LANGUAGE_NAMES = {
    "ar": "Arabic",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "eu": "Basque",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "ga": "Irish",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mk": "Macedonian",
    "ml": "Malayalam",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sq": "Albanian",
    "sr": "Serbian",
    "sv": "Swedish",
    "ta": "Tamil",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh": "Chinese",
}


def language_display(value) -> str:
    """An ISO language code (or comma-joined list of them) as display names.

    A multilingual corpus records several codes in one field (`"en,de,ru"` — MECO,
    celer), so each part is mapped and the list re-joined. An unrecognised code
    renders as itself: it still identifies the language to anyone who knows it,
    which "Unknown" does not. A blank/absent value gives ``""`` so the caller can
    drop the caption rather than print an empty label.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return ", ".join(LANGUAGE_NAMES.get(part.lower(), part) for part in parts)


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
# DATA-26: the third top-level view — everything about the dataset *itself*
# (source, location, column mapping, contents, recording setup, preprocessing),
# which used to be split between the ⚙️ Configure / 🧹 Preprocessing menu
# popovers and a 🔎 Data Inspection subtab buried in the Scanpath view.
_VIEW_DATA = "Data"
_MAIN_TAB_LABELS = [_VIEW_SCANPATH, _VIEW_CORPUS, _VIEW_DATA]

# DATA-26: the two keys the Data page's outer container is built with — visible
# when that view is active, off-screen otherwise.
#
# The setup widgets (the loaders' directory input and ⬇ Download button, the
# source options, the column-mapping selectboxes) *drive* `prepare_data` on
# every rerun, and Streamlit drops the key of a widget that did not render. The
# menu popovers they used to live in executed every run for exactly that reason;
# a page body only executes while its view is selected. So the page is rendered
# every run either way and simply hidden — `styles.py` gives the off-screen key
# `display: none` — which keeps this a re-host rather than a rewrite of every
# loader into a render/resolve pair.
DATA_PAGE_KEY = "data_setup_page"
DATA_PAGE_OFFSCREEN_KEY = "data_setup_page_offscreen"

# UX-47: ONE column grid for every control row stacked above the plot — the
# Narrow-by row, the trial picker, the multipart screen navigator, the chip
# strip, and (in Compare mode) the second dataset's picker and its own Narrow-by
# row. Three tracks: **pick** (the row's own dropdown), **scrub** (the wide
# middle — a slider, a pair of multiselects, the chips), **act** (the right-hand
# `railbtn_*` pills, which `styles.py` packs flush right).
#
# It is a shared constant rather than a repeated literal because that is the
# whole feature: the rows are built in three functions across two modules, and
# each of them owning its own weights is exactly how they drifted apart — the
# source dropdown ended 50 px short of the trial dropdown directly below it, and
# the middle track started 38 px further left on one row than the next. Tracks
# span by *summing* the weights they cover (the chip strip is 3 + 5), never by
# inventing a second pair; a `st.columns` of merged weights differs from the
# three-track boundary by a fraction of one gutter (~3 px at the default 1 rem),
# which is below the threshold where an eye reads two edges as unaligned.
#
# Widths, not pixels: Streamlit shares the row minus its gutters out by weight,
# so the grid holds at every window size.
SELECTOR_ROW_GRID = [3.0, 5.0, 1.9]

#: The first two tracks of ``SELECTOR_ROW_GRID`` as one — for a row whose left
#: side is a single wide element (the chip strip) rather than pick + scrub.
SELECTOR_ROW_WIDE_GRID = [
    SELECTOR_ROW_GRID[0] + SELECTOR_ROW_GRID[1],
    SELECTOR_ROW_GRID[2],
]

#: The Narrow-by row's middle track, split into `label | text | participant`.
#: Used by both A's row and (in Compare mode) B's, so the two line up too.
NARROW_BY_GRID = [0.9, 2.2, 2.2]
