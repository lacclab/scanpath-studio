"""Shared constants for the Scanpath Studio app."""

from __future__ import annotations

import os
import re

PACKAGE_NAME = "scanpath_studio"

#: On raw gaze imported with no clock: each sample's position in its trial, 1,
#: 2, … — in place of `timestamp_ms`, which such a table does not have
#: (`data.normalize_raw_gaze`). A column the user sees and exports, the sample
#: number, so the plot can colour by order without calling it time.
SAMPLE_INDEX = "sample_index"


# --- Experimental features ----------------------------------------------------
# Features that are built but not yet validated or fully integrated are off
# unless ``SCANPATH_EXPERIMENTAL`` is set: vertical drift correction (a port of
# Carr et al. 2021's line-assignment algorithms) and the NLD similarity scoring
# under 🔬 Comparisons both work, but the similarity table still shows three
# metrics as "Not yet computed" and the Line assignment subtab is unfinished.
# This is a **visibility gate, not a removal**: `alignment.py` and
# `similarity.py` stay where they are and stay importable.
#
# Polarity is the opposite of `app.public_datasets_enabled`: these default
# **off** and the env var turns them on. Read at *call time*, which is both what
# lets a test toggle them and what stops a stale import-time read from making
# one surface disagree with another.
EXPERIMENTAL_ENV_VAR = "SCANPATH_EXPERIMENTAL"


def experimental_features_enabled() -> bool:
    """Whether the experimental features are exposed.

    Off unless ``SCANPATH_EXPERIMENTAL`` is set to something truthy (``1``,
    ``true``, ``yes``, ``on``). Every gate below reads this one switch.
    """
    return os.environ.get(EXPERIMENTAL_ENV_VAR, "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def drift_correction_enabled() -> bool:
    """Whether vertical drift correction / line assignment is exposed.

    Turning it on adds the rail's drift-correction control, the Line
    assignment subtab and `render`'s ``--drift-correction`` flag. Off unless
    ``SCANPATH_EXPERIMENTAL`` is set: the algorithms work, but the subtab is
    unfinished. While it is off, an API call that asks for drift correction
    raises rather than returning uncorrected fixations.
    """
    return experimental_features_enabled()


def similarity_enabled() -> bool:
    """Whether NLD scanpath-similarity scoring is exposed under 🔬 Comparisons.

    Off unless ``SCANPATH_EXPERIMENTAL`` is set: NLD works, but three of the
    table's four metrics are not computed yet.
    """
    return experimental_features_enabled()


def preprocessing_enabled() -> bool:
    """Whether the soft-exclusion / merge pipeline is exposed **in the app**.

    Turning it on adds the 🗂️ Data page's Preprocessing panel. Off unless
    ``SCANPATH_EXPERIMENTAL`` is set: the pipeline is built and tested but not
    yet validated by hand.

    `api.preprocess_data` and `scanpath-studio analyze` are gated by
    `computed_measures_enabled` instead, which raises rather than hides.
    """
    return experimental_features_enabled()


def computed_measures_enabled() -> bool:
    """Whether the numbers Scanpath Studio works out itself are exposed.

    Off unless ``SCANPATH_EXPERIMENTAL`` is set, until each is validated by
    hand: the per-word reading measures (`api.compute_word_metrics`), the
    reader / trial summaries, the analysis tables and `scanpath-studio
    analyze`, the export bundle's measure family, and the Corpus Analysis views
    built on them (Reading summary, Progressive vs regressive, Landing-position
    curve, Participant summary table). Everything that shows the dataset's own
    values stays. Unlike the app-only gates, the API raises and the CLI
    refuses: a script that gets no number is better off than one that gets an
    unchecked one.
    """
    return experimental_features_enabled()


def sentence_analysis_enabled() -> bool:
    """Whether Corpus Analysis offers its **Per sentence** subtab.

    Off unless ``SCANPATH_EXPERIMENTAL`` is set: it works its numbers out from
    the fixation table, while the rest of the page shows only the measures the
    dataset brought, so a dataset with supplied measures and no fixations reads
    as 0 ms and skipped. Off, the subtab is not drawn and its table is never
    computed; `preprocessing.sentence_measures` is untouched
    (`api.analysis_tables` is gated by `computed_measures_enabled`).
    """
    return experimental_features_enabled()


def derived_analysis_tables_enabled() -> bool:
    """Whether the 🗂️ Data page's "🧮 Derived analysis tables" section (Sentences
    / Saccades / Trial summary / Participant summary / Characters) is exposed
    **in the app**.

    Off unless ``SCANPATH_EXPERIMENTAL`` is set, for the same reason as
    `preprocessing_enabled()`: built and tested, not yet validated by hand.
    Off, the section doesn't render *and* its backing computation
    (`tabs._c_derived_tables` — full reading-measure + saccade/sentence/reader
    aggregation) never runs, not just its display — a Data page rerun with the
    flag off does none of that work. Scope is the **app** only:
    `preprocessing.py`'s own table builders are untouched and still directly
    callable.
    """
    return experimental_features_enabled()


# Default text font. A single generic family that renders (monospaced) on every
# platform including the Streamlit Cloud demo; the font field accepts any CSS
# font name or stack if you want the exact experiment font.
FONT_FAMILY = "monospace"

# The demo corpus' own presentation monitor, so a figure with no declared
# canvas still renders true-to-scale. Sourced from Berzak et al. 2025, Sci Data
# 12:1995 — Dell U2715H, 2560 px × 1440 px over 597 mm × 336 mm.
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

# Both colour scales open in Blues: one hue, light to dark, colourblind-safe.
# A keyed selectbox first-rendered inside a popover would otherwise display its
# first option rather than a non-index-0 seeded value on first open — handled by
# `controls._popover_selectbox` (explicit `index=`) / `_pin` + `persist_state`, so a
# non-index-0 default here still keeps the picker and the figure in sync.
DEFAULT_FIXATION_COLORSCALE = "Blues"
DEFAULT_HEATMAP_COLORSCALE = "Blues"
#: Heatmap styles that scale their smoothed density to each figure's own peak
#: (`plots._add_interpolated_heatmap`), so a ``heatmap_range`` does nothing to
#: them: the rail greys the range for these, and the code snippet omits it.
#: Compare always draws word boxes, where the range applies again.
SELF_SCALED_HEATMAP_STYLES = frozenset({"Smoothed"})

DEFAULT_MARKER_SIZE_RANGE = (8, 24)
# How fixation duration maps onto that size range. The three *fixed* scales map
# one duration range (ms, below) onto it for every figure, so a 200 ms fixation
# is the same size in any trial, comparison side, replay or export — EyeLink
# Data Viewer's convention. With "relative", each figure spans its own
# shortest-to-longest duration, so sizes only compare within it.
# √ is the default because a marker's size is its diameter: √duration makes the
# marker's area grow in step with duration.
MARKER_SIZE_SCALES = {
    "sqrt": "Square root (area tracks duration)",
    "linear": "Linear (diameter tracks duration)",
    "log": "Logarithmic",
    "relative": "Relative to this figure",
}
DEFAULT_MARKER_SIZE_SCALE = "sqrt"
#: What a figure saved before the fixed scale existed was drawn with — the
#: migration target for old saved configs and Share links.
LEGACY_MARKER_SIZE_SCALE = "relative"
# 50–600 ms covers 99% of the bundled OneStop fixations (1st percentile 51 ms,
# 99th 448 ms), sits below the 80 ms short-fixation flag, and leaves the long
# tail distinguishable before it clamps. Durations outside it clamp to the
# smallest / largest marker.
DEFAULT_MARKER_DURATION_RANGE = (50, 600)
#: The duration-bounds widget's own limits (ms).
MARKER_DURATION_BOUNDS = (10, 3000)
DEFAULT_ORDER_FONT_COLOR = "#111111"

WORD_BOX_COLOR = "#6c757d"
#: The outline's opacity; 1 draws it solid.
WORD_BOX_LINE_OPACITY = 1.0
#: The word boxes' fill, drawn translucent (``WORD_BOX_FILL_OPACITY``) so it
#: tints the interest area without hiding the text, fixations or image under it.
WORD_BOX_FILL_COLOR = "#646464"
WORD_BOX_FILL_OPACITY = 0.05
# Black, matching the colourblind-safe default palette.
WORD_LABEL_COLOR = "#000000"
# Default colour for highlighted ("Mark text") reading text — vermillion,
# matching the colourblind-safe default palette. The visualization controls
# expose a picker that overrides it per figure.
HIGHLIGHTED_TEXT_COLOR = "#D55E00"
# Reddish purple, matching the colourblind-safe default palette.
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
    never drift from what's drawn."""
    return COMPARISON_PALETTE[idx % len(COMPARISON_PALETTE)]


#: Each comparison scanpath's default marker alpha, shared the same way: the
#: rail seeds ``cmp{idx}_opacity`` from it (``controls._seed_compare_styles``)
#: and the builder falls back to it (``plots._comparison_scanpath_style``), so
#: a headless ``compare_scanpaths`` / ``render --compare-with`` draws the app's
#: default. 0.7 matches the single-trial default, so overlaps show through.
COMPARE_FIXATION_OPACITY = 0.7


# Saccade line styles offered in the plot rail. Maps the friendly UI label to the
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
#: The Smoothed heatmap's fixed blur σ (px): the box's limits and default.
HEATMAP_SIGMA_BOUNDS = (1.0, 500.0)
DEFAULT_HEATMAP_SIGMA_PX = 20.0
#: Snap to line: where on its text line a snapped fixation sits, in line
#: heights from the line's middle (negative = up). The default, −0.5, is the
#: line's top edge, just above the word.
DEFAULT_SNAP_POSITION = -0.5
SNAP_POSITION_BOUNDS = (-2.0, 2.0)

# Colour saccades by reading type. Each saccade (the segment from one
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
    "other": "Off the text",
}
# Okabe-Ito, matching the colourblind-safe default palette.
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

# Saccade colour modes. The five-way "By type" split is more than most
# figures need, so there's a middle option between one flat colour and the full
# reading-class breakdown: "Forward / regression", the distinction almost every
# reading paper actually draws. It reuses the same per-class machinery — the
# classes are just folded into two buckets before the segments are built, so it
# shares the colour pickers, the legend toggle and every surface.
SACCADE_COLOR_MODES = ("One color", "Forward / regression", "By type")
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
    "other": "Off the text",
}

# Fixation marker shape. Plotly symbol name → the label shown in the picker.
# Shape is a *second* encoding channel, and unlike hue it survives greyscale
# printing — so it pairs with the flat default colour (below) and the print /
# colourblind palettes.
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

# The "Color fixations by" option meaning *don't* map a variable to hue.
# Marker size already encodes fixation duration, so colouring by duration too
# double-encodes one variable and spends the colour channel on nothing. The
# default is therefore one flat colour, and colour-by is an explicit opt-in for a
# *different* variable (surprisal, frequency, line, pass index).
UNIFORM_COLOR_FIELD = "(uniform)"
# Blue, matching the colourblind-safe default palette.
DEFAULT_FIXATION_COLOR = "#0072B2"

# Outline width (px) for hollow (outline-only) fixation markers.
HOLLOW_OUTLINE_WIDTH = 2.0

# Distinct mark for fixations that fall outside every word box ("out of text").
OUT_OF_TEXT_COLOR = "#d62728"  # red

# Plot background. Default white; some analyses prefer a neutral gray. The
# rail's colour swatch takes any colour; one that matches no preset is stored
# as *Custom…*.
DEFAULT_BACKGROUND_COLOR = "#ffffff"
BACKGROUND_PRESETS = {
    "White": "#ffffff",
    "Light gray": "#e9ecef",
    "Gray": "#bdbdbd",
    "Black": "#000000",
}

#: Crop to data's automatic margin: 5% of the data's extent on each axis, at
#: least this many screen px (`plots._compute_axis_ranges`).
CANVAS_PAD_MIN_PX = 20.0
CANVAS_PAD_FRACTION = 0.05
#: Crop to data's own margin, in screen px: where the box starts once
#: *Auto* is unticked, and the range a link or settings file is held to.
DEFAULT_CROP_MARGIN_PX = 50.0
CROP_MARGIN_BOUNDS = (0.0, 2000.0)

# --- Figure design settings ----------------------------------------------------
# Each `*_BOUNDS` is the range the rail, a link, a settings file and `render`
# hold its setting to.
#: The heatmap's opacity once set by hand; unset, each style keeps its own
#: (`plots.HEATMAP_STYLE_OPACITY`). The rail's box starts from Word boxes'.
DEFAULT_HEATMAP_OPACITY = 0.5
HEATMAP_OPACITY_BOUNDS = (0.05, 1.0)
#: The export title and caption (`export.annotate_figure`), in px.
DEFAULT_TITLE_FONT_SIZE = 20
TITLE_FONT_SIZE_BOUNDS = (8, 48)
DEFAULT_CAPTION_FONT_SIZE = 13
CAPTION_FONT_SIZE_BOUNDS = (6, 36)
DEFAULT_CAPTION_COLOR = "#555555"
#: The static figure's border round the plot area.
DEFAULT_PLOT_FRAME_COLOR = "#000000"
#: The saccades' direction arrowheads, in px.
DEFAULT_SACCADE_ARROW_SIZE = 12.0
SACCADE_ARROW_SIZE_BOUNDS = (4.0, 40.0)
#: The outline round a filled fixation marker; a width of 0 draws none. The
#: colour is `FIX_MARKER_OUTLINE`, spelt out for a colour picker.
DEFAULT_FIXATION_OUTLINE_WIDTH = 0.5
FIXATION_OUTLINE_WIDTH_BOUNDS = (0.0, 5.0)
DEFAULT_FIXATION_OUTLINE_COLOR = "#111111"
#: The coordinate grid's tick labels, in px.
DEFAULT_GRID_FONT_SIZE = 18
GRID_FONT_SIZE_BOUNDS = (6, 36)
#: A colour bar's thickness in px, and its length as a fraction of the plot's
#: side (unset: a third of the height upright, 0.6 of the width lying down).
DEFAULT_COLORBAR_THICKNESS = 14
COLORBAR_THICKNESS_BOUNDS = (4, 40)
DEFAULT_COLORBAR_LENGTH = 0.33
COLORBAR_LENGTH_BOUNDS = (0.1, 1.0)


# --- The Plotly config every figure is drawn with ------------------------------
# plotly.js 3 defaults `showSendToCloud` to true: the modebar's "Share chart…"
# button uploads the whole figure — words, coordinates, hover fields — to
# cloud.plotly.com. Nothing in Scanpath Studio sends data anywhere unasked, and
# its own Share means something else, so every figure turns the button off:
# the app's embeds and charts, the HTML it writes, and the docs site's figures.
# Merge it into any other config: ``{**PLOTLY_CONFIG, "responsive": False}``.
PLOTLY_CONFIG: dict = {"showSendToCloud": False}


# --- Selectable palettes -----------------------------------------------------
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
#     greyscale conversion. Marker shape and the two-way saccade mode are the
#     redundant channels when colour alone can't carry it.
PALETTES: dict[str, dict] = {
    # Okabe & Ito's eight-colour set — the de-facto standard for qualitative
    # colourblind-safe encoding — plus single-hue Blues scales, which vary in
    # lightness only and so survive every common deficiency. This is the
    # default a fresh session opens with.
    "Default (colorblind-safe)": {
        "description": "Okabe–Ito hues and Blues scales, chosen to stay "
        "distinguishable with common color-vision deficiencies.",
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
    "Print / grayscale": {
        "description": "Grays only, so it still reads in a black-and-white "
        "print. Pair with marker shape.",
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
DEFAULT_PALETTE = "Default (colorblind-safe)"


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


# --- App theme -----------------------------------------------------------------
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
    # No built-in gap under the last element (Streamlit's default is ~10rem of
    # empty scroll), through Streamlit's own setting. Its top counterpart,
    # `paddingTop`, is measured from *below* the header, so it cannot express
    # styles.py's tighter `padding-top` — that one is CSS.
    "paddingBottom": "0",
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
#: pip-installed console script started from anywhere else would silently fall
#: back to the 200 MB default. This is the transport limit only — what a machine can
#: actually parse is a separate question, which `data.UPLOAD_SIZE_WARN_BYTES`
#: answers for the memory-capped hosted demo.
UPLOAD_MAX_SIZE_MB = 5000

#: A deployment's own, lower per-file ceiling, in MB — set on the hosted
#: demo (its Community Cloud secrets, which Streamlit loads into the environment
#: at startup) so a visitor cannot send a multi-GB file at a ~1 GB container,
#: while every other install keeps :data:`UPLOAD_MAX_SIZE_MB`.
UPLOAD_LIMIT_ENV = "SCANPATH_MAX_UPLOAD_MB"


#: The file types every table upload box accepts (``zip`` wraps any of the
#: others; ``txt`` is a tab-separated report; ``xls`` is a legacy workbook or
#: EyeLink Data Viewer's text-in-an-``.xls`` export).
UPLOAD_FILE_TYPES = ("csv", "tsv", "txt", "parquet", "feather", "zip", "xlsx", "xls")


def configured_upload_limit_mb() -> int | None:
    """``SCANPATH_MAX_UPLOAD_MB`` as a positive whole number of MB, else ``None``.

    The raw deployment setting, before it meets the server's own limit — what
    ``scanpath-studio run`` hands the server.
    """
    raw = os.environ.get(UPLOAD_LIMIT_ENV, "").strip()
    try:
        limit = int(raw)
    except ValueError:
        return None
    return limit if limit > 0 else None


def upload_limit_mb() -> int | None:
    """The per-file cap every ``st.file_uploader`` passes as ``max_upload_size``.

    ``None`` — the server's own ``server.maxUploadSize`` — unless
    ``SCANPATH_MAX_UPLOAD_MB`` sets one, which is held to the server's limit so
    the browser never accepts a file the server then refuses. Read at call
    time, like the other deployment switches, so tests can toggle it.

    The per-widget cap is checked **in the browser**: Streamlit's upload route
    only enforces ``server.maxUploadSize``, which cannot change once the server
    runs. ``scanpath-studio run`` therefore passes the cap to the server too;
    on Community Cloud, where secrets load after the server config, a scripted
    client can still send up to the config file's limit.
    """
    limit = configured_upload_limit_mb()
    if limit is None:
        return None
    try:
        import streamlit as st

        server = int(st.get_option("server.maxUploadSize"))
    except Exception:
        server = UPLOAD_MAX_SIZE_MB
    return min(limit, server)


def upload_limit_label() -> str:
    """The per-file limit in force, as Streamlit writes it (``5GB``, ``200MB``)."""
    mb = upload_limit_mb() or UPLOAD_MAX_SIZE_MB
    return f"{mb // 1000}GB" if mb >= 1000 and mb % 1000 == 0 else f"{mb}MB"


def upload_identity(uploaded) -> tuple[str | None, str]:
    """Which upload this is: ``(file_id, sha256 of the bytes)``.

    An import that applies a file once — a settings or setup file — compares
    this with the identity it last applied, so an ordinary rerun is a no-op
    while a *fresh* upload applies again. The ``file_id`` Streamlit gives each
    upload event makes re-uploading the very same file count as fresh; the
    content hash makes a different file count as fresh even where no
    ``file_id`` exists. Name and size alone would do neither: two files can
    share both.
    """
    import hashlib

    digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
    return getattr(uploaded, "file_id", None), digest


CITATION = {
    "authors": (
        "Omer Shubi, Keren Gruteke Klein, Maya Grossman, Ella Lion, Deborah N. Jakobi, "
        "David R. Reich, Lena Jäger, Yevgeni Berzak"
    ),
    "title": "Scanpath Studio",
    # The Zenodo *concept* DOI — resolves to the latest archived
    # release. Kept equal to CITATION.cff's `doi` by tests/test_citation.py.
    "doi": "10.5281/zenodo.22933884",
    "url": "https://github.com/lacclab/scanpath-studio",
    "docs_url": "https://lacclab.github.io/scanpath-studio/",
    # Where a user asks, reports, and gets the desktop app.
    "questions_url": "https://github.com/lacclab/scanpath-studio/discussions/categories/q-a",
    "bug_report_url": "https://github.com/lacclab/scanpath-studio/issues/new?template=bug_report.md",
    "feature_request_url": (
        "https://github.com/lacclab/scanpath-studio/issues/new?template=feature_request.md"
    ),
    "ideas_url": "https://github.com/lacclab/scanpath-studio/discussions/new?category=ideas",
    "desktop_url": "https://github.com/lacclab/scanpath-studio/releases/latest",
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
# Here rather than in app.py so url_state.py / wizard.py can import them without
# a cycle (app.py re-imports them for its own use and for tests).
UPLOAD_CHOICE = "Upload tables"
AUTHOR_CHOICE = "My scanpath"
MANUAL_SAMPLE_CHOICE = "Hand-drawn sample"
DEMO_CHOICE = "Bundled demo"
SYNTHETIC_CHOICE = "Synthetic test trial"
PUBLIC_DATASETS_CHOICE = "Public datasets"
POTEC_DEFAULT_DIR = "data/PoTeC"
ONESTOP_CHOICE = "OneStop (local export)"
# Public OneStop (OSF download-on-demand) — distinct from the env-var
# ONESTOP_CHOICE server bundle. Each reading regime is its own dataset in the
# flat data-source picker, holding every part of that regime; these are their
# registry labels. Named constants (not inline strings) so the deep-link /
# Share contract in url_state.py and compare_source.py can reference them
# without importing app.py's PUBLIC_DATASET_REGISTRY.
ONESTOP_PUBLIC_DEFAULT_DIR = "data/OneStop"
# Default folder for the lacclab OneStop variant (a lab-processed local export;
# superset schema, no download). Blank, since there is no path that holds for
# every user: set `ONESTOP_LACCLAB_DIR`, or type the path on the 🗂️ Data page.
ONESTOP_LACCLAB_DEFAULT_DIR = ""
ONESTOP_REGIME_LABELS = {
    "ordinary": "Ordinary reading",
    "information_seeking": "Information seeking",
    "repeated": "Repeated reading",
    "information_seeking_repeated": "Information seeking (repeated)",
}
#: Regime → the registry label of that regime's dataset.
ONESTOP_REGIME_CHOICES = {
    regime: f"OneStop — {label}" for regime, label in ONESTOP_REGIME_LABELS.items()
}


#: Each regime dataset's ``?source=`` token. Its own per regime, because the
#: token also names Compare's dataset B (``cmp_source``), which carries no
#: regime of its own. Older links' ``onestop_public`` token is still read:
#: with its ``onestop_regime`` it names one of these four.
ONESTOP_REGIME_SOURCE_TOKENS = {
    regime: f"onestop_{regime}" for regime in ONESTOP_REGIME_LABELS
}
ONESTOP_LEGACY_SOURCE_TOKEN = "onestop_public"


def onestop_regime_for_choice(choice: str | None) -> str | None:
    """The regime a OneStop dataset label names, else ``None``."""
    return next((r for r, c in ONESTOP_REGIME_CHOICES.items() if c == choice), None)


# OneStop trial parts (screens) → display label, in presentation order. Mirrors
# datasets._ONESTOP_PARTS; the Parts multiselect + the parts URL/CLI contract
# use these keys. Paragraph is the reading passage (the default).
ONESTOP_PART_LABELS = {
    "Title": "Title",
    "Question_Preview": "Question preview",
    "Paragraph": "Paragraph",
    "Questions": "Question",
    "Answers": "Answers",
    "QA": "Question + answers combined (QA)",
    "Feedback": "Feedback",
}
# OneStop source variants → display label. `public` downloads from OSF on demand;
# `lacclab` reads a lab-processed local export (superset schema, no download).
ONESTOP_VARIANT_LABELS = {
    "public": "Public (OSF download)",
    "lacclab": "LaCC lab (local export)",
}
_VIEW_SCANPATH = "Scanpath Visualization"
_VIEW_CORPUS = "Corpus Analysis"
# The third top-level view — everything about the dataset *itself* (source,
# location, column mapping, contents, recording setup, preprocessing).
_VIEW_DATA = "Data"
_MAIN_TAB_LABELS = [_VIEW_SCANPATH, _VIEW_CORPUS, _VIEW_DATA]

#: The dataset table's remembered headline counts, `{token: {...}}`.
#: A session-state key that also travels in the recovery cache's manifest, so it
#: lives here rather than in `app`: `persistence` writes it and `app` fills it,
#: and `persistence` cannot import `app` (that is the cycle `app` already
#: avoids by importing `persistence` one way).
DATASET_COUNTS_STORE_KEY = "_dataset_counts_store"

#: ``{dataset token: description}``, every description the user
#: wrote (on the add wizard or ✏️ Edit dataset), for any kind of dataset. One
#: small dict persisted as a recovery-cache session key, *not* a field on an
#: upload's ``_datasets`` entry: every non-frame field there is part of the
#: cache's dataset identity, so editing one sentence would rewrite every
#: upload's Parquet files. Here for the same import-cycle reason as above.
DATASET_DESCRIPTIONS_KEY = "_dataset_descriptions"

#: ``{dataset token: {"folder": str, "pattern": str}}``, the local
#: folder of stimulus images each dataset was pointed at (the add screen's and
#: ✏️ Edit dataset's *Stimulus images*), for any kind of dataset. Kept beside
#: the store like the descriptions, for the same reason. A machine-local path,
#: so it is in the recovery cache — which is local itself — and never on a
#: share link or in a settings file.
DATASET_STIMULUS_IMAGES_KEY = "_dataset_stimulus_images"
#: The filename pattern a dataset starts with when none was given.
DEFAULT_STIMULUS_IMAGE_PATTERN = "{text_id}.png"

#: ``{dataset token: SetupSnapshot.to_dict()}`` — the recording setup the user
#: saved on ✏️ Edit dataset for a **built-in or public** dataset, in place of
#: the one the corpus declares (which is never rewritten). An upload keeps its
#: setup on its own ``_datasets`` entry instead. A recovery-cache session key,
#: like the descriptions, for the same reason.
DATASET_SETUP_OVERRIDES_KEY = "_dataset_setup_overrides"
#: Which dataset's own setup the ``global_*`` setup keys hold now — a saved
#: override, or an added dataset's recorded setup — and what they held before
#: it was applied: put back when that dataset is left or its override is reset
#: (the same stash-and-restore shape as the font snap). Both
#: persisted, so a relaunch onto the dataset does not stash the override as its
#: own "before".
SETUP_OVERRIDE_FOR_KEY = "_setup_override_for"
SETUP_OVERRIDE_RESTORE_KEY = "_setup_override_restore"
#: The ``global_*`` keys an override writes (and its restore puts back).
SETUP_OVERRIDE_SESSION_KEYS = (
    "global_canvas_width",
    "global_canvas_height",
    "global_monitor_width_mm",
    "global_viewing_distance_mm",
    "global_display_dpi",
    "global_base_font_size",
    "global_use_stimulus_font_pt",
    "global_font_family",
    "global_line_spacing",
    "global_scale_text_to_boxes",
)

#: The folder every public corpus downloads into, each in a subfolder
#: (``<folder>/PoTeC``), set on the 🗂️ Data page. A recovery-cache session key
#: so the choice survives a restart; never in a link, since it is a local path
#: (see `session_keys.PARAM_CORPUS`). Unset, `DOWNLOAD_DIR_ENV` decides, then
#: the checkout's ``data/`` or the per-user data home.
DOWNLOAD_DIR_KEY = "download_dir"
DOWNLOAD_DIR_ENV = "SCANPATH_STUDIO_DOWNLOAD_DIR"

#: The raw-gaze layer's per-dataset default (`app.seed_raw_gaze_default`):
#: the dataset it was last decided for, and the value that decision overwrote.
#: Recovery-cache session keys, so a relaunch onto the same dataset does not
#: decide again over the user's own choice; here for the import-cycle reason
#: above (`persistence`, `controls` and `app` all read them).
RAW_GAZE_SEEDED_FOR_KEY = "_raw_gaze_seeded_for"
RAW_GAZE_SNAP_RESTORE_KEY = "_raw_gaze_snap_restore"
#: …and the dataset an open deep link's `show_raw_gaze` belongs to — the first
#: one decided while the link was on the URL. Session-only: a link is a visit.
RAW_GAZE_LINK_FOR_KEY = "_raw_gaze_link_for"

#: "The ✏️ Edit dataset screen is open". The Data page is two screens: the
#: **overview** (the dataset table + what's in the open dataset) and the
#: **editor** (everything that configures it — source options and location,
#: column mapping, recording setup, trial identity, stimulus images, the two
#: metadata tables, preprocessing). Both are built every run and switched by key,
#: for exactly the reason the page itself is (see below): the editor is nothing
#: but widgets that drive `prepare_data`, and Streamlit drops the key of a widget
#: that did not render.
DATASET_EDITOR_OPEN_KEY = "_dataset_editor_open"
DATA_OVERVIEW_KEY = "data_overview"
DATA_EDITOR_KEY = "data_dataset_editor"
DATA_EDITOR_OFFSCREEN_KEY = "data_dataset_editor_offscreen"

# The two keys the Data page's outer container is built with — visible when
# that view is active, off-screen otherwise.
#
# The setup widgets (the loaders' directory input and ⬇ Download button, the
# source options, the column-mapping selectboxes) *drive* `prepare_data` on
# every rerun, and Streamlit drops the key of a widget that did not render. A
# page body would only execute while its view is selected, so the page is
# rendered every run either way and simply hidden — `styles.py` gives the
# off-screen key `display: none` — rather than splitting every loader into a
# render/resolve pair.
DATA_PAGE_KEY = "data_setup_page"
DATA_PAGE_OFFSCREEN_KEY = "data_setup_page_offscreen"

#: The view the user tried to reach while the add-dataset wizard was
#: open. `app.main` holds them on the 🗂️ Data page and the wizard asks whether to
#: discard the setup; this remembers where they were headed so *Discard and
#: leave* can finish the trip. Session state only, never a wire format.
WIZARD_LEAVE_KEY = "_wizard_leave_requested"

#: The view the user answered *Keep setting up* for. The prompt is
#: suppressed while the nav sits on exactly that view, so choosing to stay does
#: not re-ask on every rerun; clicking a *different* view asks again. Session
#: state only, never a wire format.
WIZARD_STAY_KEY = "_wizard_leave_acknowledged"

#: Set by the dataset table's ✏️ Edit button to the dataset it opened, so
#: the Column mapping section below can say that is why the page changed under
#: the user. Read once and cleared; session state only, never a wire format.
FOCUS_MAPPING_KEY = "_focus_column_mapping"

# ONE column grid for every control row stacked above the plot — A's trial row
# and, in Compare mode, B's (plus the page skeleton that stands in for them while
# loading). Four tracks: **dataset** (the dataset picker and its + menu),
# **trial** (the row's own dropdown), **scrub** (the wide middle — the trial
# slider), **actions** (the right-hand `railbtn_*` pills, which `styles.py`
# packs flush right; the filters are one icon there).
#
# It is a shared constant rather than a repeated literal because the rows are
# built in several functions across two modules, and rows that each own their
# weights drift out of alignment. Tracks span by *summing* the weights they
# cover, never by inventing a second set; a `st.columns` of merged weights
# differs from the separate-track boundary by a fraction of one gutter (~3 px at
# the default 1 rem), which is below the threshold where an eye reads two edges
# as unaligned.
#
# Widths, not pixels: Streamlit shares the row minus its gutters out by weight,
# so the grid holds at every window size. The dataset track is as wide as the
# trial track: two datasets under comparison are told apart by that label. The
# weights favour the scrubber, and `styles.py` puts floors under the other three
# tracks. The actions track is a fixed width: its pills are a fixed width, and a
# proportional track would grow with the window and leave an empty gap to the
# left of ◀. Its weight is nominal. The dataset and trial tracks shrink with the
# window down to a floor that still shows a name in full. So a wide window gives
# its extra width to the scrubber, and a narrow one takes it from the scrubber
# first. Every row of this grid gets the same floors, so the rows still line up.
SELECTOR_ROW_GRID = [2.6, 2.3, 5.1, 1.0]

#: The minimum width of each `SELECTOR_ROW_GRID` track, in rem. `None` is no
#: floor (the scrubber). The actions floor fits A's ◀ ▶ ⇅ 🔎 ✏️ — five pills,
#: about 15rem with their gaps. The dataset floor fits the dataset dropdown
#: beside its + menu, and the trial floor fits a OneStop trial id.
#: `styles.py` caps the two picker floors at a share of the row
#: (`SELECTOR_ROW_FLOOR_CAPS`), so a narrow window still has room for the
#: scrubber.
SELECTOR_ROW_FLOORS_REM = (15.75, 12.5, None, 15.0)

#: The share of the row that caps each picker floor, as a percentage.
SELECTOR_ROW_FLOOR_CAPS = (25, 20, None, None)

#: The three-track shape, for a selector row with no scrubber — a one-trial
#: pool, A's or Compare's B. Built by merging the trial and scrub tracks, so its
#: outer boundaries still line up with the four-track rows (which is the whole
#: point of sharing one grid — see the note at the top of this block).
SELECTOR_ROW_TRIO = [
    SELECTOR_ROW_GRID[0],
    SELECTOR_ROW_GRID[1] + SELECTOR_ROW_GRID[2],
    SELECTOR_ROW_GRID[3],
]

#: The multipart screen navigator's track, appended at the right end of a trial
#: row (after ◀ ▶ ⇅ 🔎) when the dataset has screens: a narrow dropdown + ◀ ▶,
#: so the screens need no row of their own under each trial row. Its
#: width is mostly its floor (`SELECTOR_SCREEN_FLOOR_REM`); the weight is
#: nominal, like the actions track's.
SELECTOR_SCREEN_TRACK = 1.0

#: The screen track's minimum width, in rem: a ~7rem dropdown beside its
#: ~5rem ◀ ▶ pair, then the row's ⇅ 🔎 ✏️ (~10rem, measured 160px), which follow it.
SELECTOR_SCREEN_FLOOR_REM = 24.5

#: The screen navigator's own width inside that track, in rem: the track less
#: A's ⇅ 🔎 ✏️ and the gap before them (~10.75rem). Fixed rather than "what the
#: menus leave", because B's row has no ✏️: taking the difference would make
#: B's navigator wider than A's, right under it.
SELECTOR_SCREEN_PICKER_REM = SELECTOR_SCREEN_FLOOR_REM - 10.75

#: With a screen track, the actions track keeps only ◀ ▶: its floor, in rem.
SELECTOR_STEPS_FLOOR_REM = 5.2

#: The least the trial scrubber is squeezed to before a selector row wraps.
SELECTOR_SCRUB_MIN_REM = 7.5
#: How wide a selector row must be to stay on one line: every floor of its
#: widest shape (dataset · trial · scrubber · ◀ ▶ · screen + ⇅ 🔎 ✏️) plus
#: the 1rem gaps between its five columns. Wider, the row keeps one line and
#: compresses (the scrubber gives first); narrower, it wraps, the screen and
#: action cluster moving to a line of their own rather than running past the
#: column into the plot-controls rail.
SELECTOR_ROW_WRAP_REM = (
    SELECTOR_ROW_FLOORS_REM[0]
    + SELECTOR_ROW_FLOORS_REM[1]
    + SELECTOR_SCRUB_MIN_REM
    + SELECTOR_STEPS_FLOOR_REM
    + SELECTOR_SCREEN_FLOOR_REM
    + 4 * 1.0
)

#: The trial-identity check screens a sample of trials by default. The
#: 🗂️ Data page's *Check every trial* button sets this session flag to ask for
#: the full census instead. UI-only — it is deliberately not wire format, so it
#: travels in neither a share link nor a saved config.
TRIAL_IDENTITY_FULL_KEY = "_trial_identity_full_scan"

#: The trial-identity check's verdict is about a decision made only twice:
#: when a dataset is added, and when its mapping is edited. Both moments set
#: this flag, and ``app.main`` pops it once the (already computed) report for
#: the newly derived frames exists — raising the verdict as a modal exactly
#: where the Trial ID mapping was just chosen, rather than as a page-wide
#: banner on every run. The value says which flow asked, so the modal's "go
#: back" button can name the right screen: ``"add"`` or ``"edit"``.
TRIAL_IDENTITY_CHECK_KEY = "_trial_identity_check_after"

#: The name of the dataset ✅ Add dataset just stored, popped by
#: ``app.main`` once its frames are loaded to confirm what arrived.
DATASET_ADDED_KEY = "_dataset_added_name"


# --- The icon vocabulary -------------------------------------------------------
# One Material Symbols (Rounded) icon per *concept* the app draws as chrome — a
# nav entry, a rail section, a subtab, a button, an alert — so the same idea
# looks the same everywhere and swapping one is a one-line change. Streamlit
# renders the shortcode in markdown and in every ``icon=`` parameter.
#
# Keyed by meaning, not by glyph: the Scanpath preset, the Fixations layer and
# a data preview are three entries here. Prose keeps its emoji — help text, tour bodies, docstrings,
# ``cli.py`` and ``docs/`` still write "the 🗂️ **Data** page" — and so do the
# places a shortcode cannot reach: selectbox options and dataframe cells are
# plain text (the trial-picker ★ 🏷️ 📝 markers, the dataset-kind tags), and
# Plotly text is baked into every export (▶ Play, the marker-shape previews).
# The typographic glyphs on buttons (◀ ▶ ⇅ ✕ ⬇ ↗) are kept too.
ICONS: dict[str, str] = {
    # Navigation and dialogs. `app` is the welcome tour's; the favicon itself
    # is 👀 — see `app.set_page_config`'s call site.
    "app": ":material/visibility:",
    "view_scanpath": ":material/route:",
    "view_corpus": ":material/bar_chart:",
    "view_data": ":material/database:",
    "help": ":material/help:",
    "tutorials": ":material/explore:",
    "faq": ":material/quiz:",
    "about": ":material/info:",
    "course": ":material/school:",
    "question": ":material/forum:",
    "bug": ":material/bug_report:",
    "feedback": ":material/feedback:",
    "feature_request": ":material/lightbulb:",
    "comment": ":material/chat:",
    "desktop": ":material/computer:",
    # Plot rail: design presets, layer sections and figure groups.
    "preset_scanpath": ":material/timeline:",
    "preset_custom": ":material/build:",
    "illustration": ":material/draw:",
    "fixations": ":material/blur_on:",
    "saccades": ":material/arrow_outward:",
    "stimulus": ":material/article:",
    "word_boxes": ":material/crop_square:",
    "heatmap": ":material/local_fire_department:",
    "raw_gaze": ":material/grain:",
    "plot_filter": ":material/filter_list:",
    "figure": ":material/aspect_ratio:",
    "screen": ":material/desktop_windows:",
    "axes": ":material/grid_on:",
    "labels": ":material/title:",
    "hover": ":material/ads_click:",
    "legend": ":material/legend_toggle:",
    "designs": ":material/palette:",
    "plot_controls": ":material/tune:",
    "animate": ":material/movie:",
    "compare": ":material/compare:",
    # Scanpath subtabs, the trial row and the welcome tour's stops.
    "annotations": ":material/edit_note:",
    "comparisons": ":material/difference:",
    "line_assignment": ":material/format_line_spacing:",
    "export": ":material/file_export:",
    "share": ":material/share:",
    "favorite": ":material/star:",
    "trial_filter": ":material/filter_alt:",
    "pick_trial": ":material/my_location:",
    "chips": ":material/label:",
    "panels": ":material/tab:",
    "views": ":material/dashboard:",
    "nav": ":material/explore:",
    "preview": ":material/visibility:",
    "python": ":material/code:",
    "cli": ":material/terminal:",
    # Generic actions.
    "save": ":material/save:",
    "download": ":material/download:",
    "upload": ":material/upload:",
    "delete": ":material/delete:",
    "reset": ":material/restart_alt:",
    "undo": ":material/undo:",
    "edit": ":material/edit:",
    "add": ":material/add:",
    "confirm": ":material/check:",
    "settings": ":material/settings:",
    "search": ":material/search:",
    "refresh": ":material/refresh:",
    "rename": ":material/drive_file_rename_outline:",
    "close": ":material/close:",
    "open": ":material/open_in_new:",
    "mute": ":material/notifications_off:",
    # Data → Saved on this computer, and ❓ Help → About → Debug.
    "recovery": ":material/history:",
    "debug": ":material/bug_report:",
    # Data page and the add-dataset wizard.
    "datasets": ":material/folder_open:",
    "folder": ":material/folder_open:",
    "demo": ":material/science:",
    "author": ":material/draw:",
    # The dataset table: the two kinds without an icon of their own,
    # the open dataset's badge, the row menu and the sort arrows.
    "private": ":material/lock:",
    "public": ":material/public:",
    "current": ":material/check_circle:",
    "more": ":material/more_horiz:",
    "sort_asc": ":material/arrow_upward:",
    "sort_desc": ":material/arrow_downward:",
    "data_mapping": ":material/assignment:",
    "docs": ":material/menu_book:",
    "auto_detected": ":material/auto_awesome:",
    "stats": ":material/query_stats:",
    "derived_tables": ":material/calculate:",
    # Dataset and reader metrics (the `st.metric` rows).
    "participants": ":material/group:",
    "texts": ":material/article:",
    "trials": ":material/list_alt:",
    "words": ":material/abc:",
    "gaze_points": ":material/scatter_plot:",
    "screens": ":material/view_carousel:",
    "reading_speed": ":material/speed:",
    "fixation_duration": ":material/timer:",
    "regressions": ":material/keyboard_backspace:",
    "skip_rate": ":material/fast_forward:",
    "saccade_amplitude": ":material/arrow_range:",
    # Setup-step badges (`wizard_shell.StepStatus`).
    "step_done": ":material/check_circle:",
    "step_action": ":material/error:",
    "step_todo": ":material/radio_button_unchecked:",
    "step_optional": ":material/remove:",
    # Alerts, toasts and inline status.
    "warning": ":material/warning:",
    "error": ":material/block:",
    "success": ":material/check_circle:",
    "info": ":material/info:",
    "tip": ":material/lightbulb:",
    "participant": ":material/person:",
    "trial_metadata": ":material/table:",
    "text_metadata": ":material/article:",
    # About dialog.
    "code": ":material/code:",
    "doi": ":material/bookmark:",
    "ai": ":material/smart_toy:",
    "update": ":material/update:",
    "missing_bundle": ":material/inventory_2:",
}


def plural(count: int, noun: str, plural_noun: str | None = None) -> str:
    """``"1 trial"`` / ``"3 trials"`` — a count with its noun agreeing.

    For a caption, in place of ``trial(s)``. ``plural_noun`` is for a noun that
    does not take an *s* (``"entry"`` → ``"entries"``).
    """
    word = noun if count == 1 else (plural_noun or f"{noun}s")
    return f"{count:,} {word}"


_MARKDOWN_SPECIALS = re.compile(r"([\\`*_{}\[\]<>()#+\-.!|~:$])")


def spoken(name: str) -> str:
    """``name`` as an icon-only button's accessible name.

    A button whose face is a glyph (◀, ⇅) or an icon reads, to a screen reader,
    as the glyph's own name ("black left-pointing triangle") or the icon's
    ligature ("folder_open"). Append this to its label — ``f"◀ {spoken('Previous
    trial')}"``, or on its own beside ``icon=`` — and the button is named for
    what it does. The text is an ``<em>`` that ``styles.py`` clips to nothing,
    the ``.sps-sr-only`` way, so the face stays the glyph alone; markdown in
    ``name`` is escaped so a design called ``*draft*`` stays text.

    Buttons only. A popover passes its raw label to its dialog's
    ``aria-label`` as well, asterisks and all, so a popover is named with a
    plain label clipped by key instead (`styles.py`).
    """
    escaped = _MARKDOWN_SPECIALS.sub(r"\\\1", name)
    return f"*{escaped}*"


def icon_html(concept: str) -> str:
    """``ICONS[concept]`` for raw HTML, where a ``:material/…:`` shortcode is inert.

    A ``<span>`` in the Material Symbols font Streamlit already ships, so the
    ligature — the icon's snake-case name — draws as the same glyph the
    shortcode renders. Styled by ``.sps-icon`` in ``styles.py``.
    """
    return icons_to_html(ICONS[concept])


_SHORTCODE = re.compile(r":material/([a-z0-9_]+):")


def icons_to_html(text: str) -> str:
    """``text`` with every ``:material/…:`` shortcode drawn as :func:`icon_html` does.

    For a label that arrives as markdown (``ICONS[…]`` and all) but is written
    into a raw HTML block — a line starting ``<div`` — where Streamlit leaves
    the shortcode as literal text.
    """
    return _SHORTCODE.sub(r'<span class="sps-icon" aria-hidden="true">\1</span>', text)


#: The Scanpath view's subtab labels. Named because the set is not fixed: Line
#: assignment is offered only while drift correction is exposed, so the
#: tabs are built as a list and mapped back by label. They live here rather than
#: in `tabs` because the tutorial steps in `tour` open a subtab by its label too,
#: and `tests/conftest.py` imports them rather than repeating the strings.
SUBTAB_ANNOTATIONS = f"{ICONS['annotations']} Annotations"
SUBTAB_STIMULUS = f"{ICONS['stimulus']} Stimulus & context"
SUBTAB_COMPARISONS = f"{ICONS['comparisons']} Comparisons"
SUBTAB_LINE_ASSIGNMENT = f"{ICONS['line_assignment']} Line assignment"
SUBTAB_EXPORT = f"{ICONS['export']} Export"
SUBTAB_SHARE = f"{ICONS['share']} Share"


# --- Legend layout ------------------------------------------------------------
# Where each legend sits (📐 Figure & canvas → Legends; `plots.apply_legend_layout`).
# The values are wire format — share links, saved configs, `render --legend` —
# so never rename one.

#: The legends a figure can draw, in the order the controls list them.
LEGEND_KINDS = ("compare", "saccades", "colors", "size_key", "highlight")
#: What the controls call each legend.
LEGEND_KIND_LABELS = {
    "compare": "Compare (A/B)",
    "saccades": "Saccade types",
    "colors": "Fixation colors",
    "size_key": "Fixation sizes",
    "highlight": "Text highlight",
}
#: The eight spots a legend can take around the plot — each corner, the middle
#: of the top and bottom edges, and the middle of the left and right sides
#: (where a legend runs down the side).
LEGEND_SPOTS = (
    "top-left",
    "top-center",
    "top-right",
    "left",
    "right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
)
LEGEND_SPOT_LABELS = {
    "top-left": "Top left",
    "top-center": "Top center",
    "top-right": "Top right",
    "left": "Left",
    "right": "Right",
    "bottom-left": "Bottom left",
    "bottom-center": "Bottom center",
    "bottom-right": "Bottom right",
}
#: Where a legend can go: *Auto*, or a spot outside the plot (the figure grows
#: to make room) or inside it (over the plot), spelled ``<spot>-<side>``.
LEGEND_POSITIONS = (
    "auto",
    *(f"{spot}-outside" for spot in LEGEND_SPOTS),
    *(f"{spot}-inside" for spot in LEGEND_SPOTS),
)
LEGEND_POSITION_LABELS = {
    "auto": "Auto",
    **{
        f"{spot}-{side}": f"{label}, {side}"
        for side in ("outside", "inside")
        for spot, label in LEGEND_SPOT_LABELS.items()
    },
}
#: The positions links, settings files and scripts wrote before the eight
#: spots, read as the spot each one drew at.
LEGEND_POSITION_ALIASES = {
    "above": "top-right-outside",
    "below": "bottom-left-outside",
    "left": "left-outside",
    "right": "right-outside",
    "top-left": "top-left-inside",
    "top-right": "top-right-inside",
    "bottom-left": "bottom-left-inside",
    "bottom-right": "bottom-right-inside",
}


def canonical_legend_position(value) -> str | None:
    """``value`` as one of `LEGEND_POSITIONS` (an old spelling is read through
    `LEGEND_POSITION_ALIASES`), or ``None`` when it is neither."""
    text = str(value or "auto").strip().lower()
    text = LEGEND_POSITION_ALIASES.get(text, text)
    return text if text in LEGEND_POSITIONS else None


#: How a legend's items run: one under the other, or side by side.
LEGEND_ARRANGEMENTS = ("auto", "stacked", "side-by-side")
LEGEND_ARRANGEMENT_LABELS = {
    "auto": "Auto",
    "stacked": "Stacked",
    "side-by-side": "Side by side",
}
