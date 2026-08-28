"""Deep links, plot-config save/restore, share links, and view-nav state.

Split out of ``app.py`` so the URL/deep-link contract, the plot-config
save/restore round-trip, the Share-link builder/widget, and the
Corpus⇄Scanpath view toggle live in one focused module. ``app.py`` imports
these; nothing here imports back from ``app`` (no cycle).
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from scanpath_studio.html_embed import embed_html_iframe

from .annotations import restore_records
from .code_snippet import (
    SNIPPET_STATE_KEY,
    SOURCE_AUTHOR,
    SOURCE_BENCHMARK,
    SOURCE_DEMO,
    SOURCE_MULTIPLEYE,
    SOURCE_ONESTOP,
    SOURCE_POTEC,
    SOURCE_SYNTHETIC,
    SOURCE_UNKNOWN,
    UNKNOWN_SOURCE_NOTE,
    FigureState,
    SnippetSource,
    reproduction_code,
)
from .constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    AUTHOR_CHOICE,
    BACKGROUND_PRESETS,
    COLORSCALES,
    CUSTOM_PALETTE,
    DEMO_CHOICE,
    FIXATION_SYMBOLS,
    MULTIPLEYE_BUNDLE_CHOICE,
    ONESTOP_CHOICE,
    ONESTOP_PART_LABELS,
    ONESTOP_PUBLIC_CHOICE,
    ONESTOP_REGIME_LABELS,
    ONESTOP_VARIANT_LABELS,
    PALETTES,
    PUBLIC_DATASETS_CHOICE,
    SACCADE_CLASS_EDITABLE,
    SACCADE_CLASS_ORDER,
    SACCADE_COLOR_MODES,
    SACCADE_DASH_OPTIONS,
    SACCADE_WIDTH_BOUNDS,
    SYNTHETIC_CHOICE,
    drift_correction_enabled,
)
from .controls import (
    _ALIGN_OPTIONS,
    _FIXCLASS_MODES,
    _OUT_OF_TEXT_MARKERS,
    color_field_options,
    numeric_field_options,
    palette_state,
)
from .experimental_setup import format_provenance_param, parse_provenance_param
from .session_keys import (
    COMPARE_LAYOUT_PARAM,
    COMPARE_PARAM,
    COMPARE_SOURCE_PARAM,
    COMPARE_SOURCE_STATE_KEY,
    COMPARE_STIMULUS_PARAM,
    FIX_RANGE_PARAM,
    PARAM_CORPUS,
    PENDING_COMPARE_STATE_KEY,
    PUBLIC_DATASET_CHOICE,
    SETUP_PROVENANCE_PARAM,
    SETUP_PROVENANCE_STATE_KEY,
    SINGLE_COMPARE_TOGGLE,
)

# URL query-param → session_state key map for the deep-link API. Used by
# `_apply_url_preset()` to preset widgets when the page is opened from an
# external tool with a deep link.
#
# Selection prefixes — the trial pickers a URL deep link seeds so the link lands
# on the requested trial. There's only the Scanpath view's `single` picker now:
# the Comparisons subtab (ENG-8) reuses that same selection instead of rendering
# its own `select_trial`, so there's no second `multi` picker to seed. Keep this list
# in sync with the `key_prefix=` values passed to `select_trial` in tabs.py.
_SELECTION_PREFIXES = ("single",)


def _coerce_bool(v) -> bool:
    return str(v).lower() not in {"0", "false", "no"}


def _parse_int_range(v) -> tuple:
    a, b = (int(float(x)) for x in str(v).split(",")[:2])
    return (min(a, b), max(a, b))


def _parse_float_range(v) -> tuple:
    a, b = (float(x) for x in str(v).split(",")[:2])
    return (min(a, b), max(a, b))


def _parse_field_list(v) -> list[str]:
    """Comma-separated hover fields carried by a Share link (VIZ-26)."""
    return [part.strip() for part in str(v).split(",") if part.strip()]


def _parse_saccade_classes(v) -> list[str]:
    """VIZ-31 saccade reading-class filter carried by a Share link.

    Comma-separated class names (``regression,return_sweep``). An unknown name
    raises, so a link written against a build with different classes surfaces the
    reader's "Ignored bad URL param" warning instead of quietly showing a figure
    with the wrong saccades in it. The result is ordered by
    ``SACCADE_CLASS_ORDER`` to match what the multiselect writes.
    """
    names = [part.strip() for part in str(v).split(",") if part.strip()]
    unknown = [n for n in names if n not in SACCADE_CLASS_ORDER]
    if unknown:
        raise ValueError(f"unknown saccade class: {', '.join(unknown)}")
    return [cls for cls in SACCADE_CLASS_ORDER if cls in set(names)]


#: The exact option spellings the two compare `st.segmented_control`s hold.
#: A segmented control raises when session state carries a value outside its
#: options, so a link's spelling has to be checked before it is seeded.
_COMPARE_LAYOUT_OPTIONS = ("Overlay", "Side by side", "Stacked")
_COMPARE_STIMULUS_OPTIONS = ("Both", "A", "B")


def _parse_choice(value, options: tuple[str, ...], what: str) -> str:
    """Match ``value`` case-insensitively against a closed vocabulary.

    Raising (rather than falling back to the default) is what turns a mangled
    link into the reader's "Ignored bad URL param" warning instead of a wedged
    widget — the same contract `_parse_align_algorithm` follows. Hyphens are
    accepted for the layout so the CLI's `--compare-layout side-by-side` and the
    link agree on one spelling.
    """
    name = str(value).strip().replace("-", " ")
    for option in options:
        if option.lower() == name.lower():
            return option
    raise ValueError(f"unknown {what} {str(value)!r}")


def _parse_compare_layout(v) -> str:
    return _parse_choice(v, _COMPARE_LAYOUT_OPTIONS, "compare layout")


def _parse_compare_stimulus(v) -> str:
    return _parse_choice(v, _COMPARE_STIMULUS_OPTIONS, "compare stimulus source")


def _parse_align_algorithm(v) -> str:
    """PRE-3 drift-correction algorithm name → the picker's exact spelling.

    The widget stores ``"Off"`` or a title-cased algorithm (``"Warp"``), and the
    selectbox raises if session state holds anything else — so an unknown name
    must be rejected here (the caller turns a ``ValueError`` into the "Ignored
    bad URL param" warning) rather than wedging the rail. Matching is
    case-insensitive, as ``cli.render --drift-correction`` is (ENG-22).
    """
    name = str(v).strip()
    for option in _ALIGN_OPTIONS:
        if option.lower() == name.lower():
            return option
    raise ValueError(f"unknown drift-correction algorithm {name!r}")


# --- Share-link parameter groups -------------------------------------------
# The Share link round-trips the *entire* Visualization-controls panel (plus the
# text/background settings from Experimental Setup), not just a handful of
# toggles. Each group maps a short URL key → the session_state key it reads/writes.
# `_build_share_query` (write) and `_apply_url_preset` (read) both iterate these,
# so the two sides can't drift. Data-dependent fields (color ranges, highlight
# column, axis/color-by fields) self-heal on load via the rail's _drop_stale /
# _clamp_range, so a link opened on a different trial degrades gracefully.
_SHARE_TOGGLE_PARAMS = {  # bool → "1"/"0"
    "preproc_enabled": "global_preproc_enabled",
    "preproc_blink_adjacent": "global_preproc_blink_adjacent",
    "show_words": "global_show_words",
    "show_labels": "global_show_labels",
    # UX-128: the 📄 Stimulus section's master switch (default on, so always
    # emitted — a link/config that predates this toggle restores as "on").
    "show_stimulus": "global_show_stimulus",
    "show_fixations": "global_show_fix",
    "show_order": "global_show_order",
    "show_saccades": "global_show_saccades",
    "show_saccade_arrows": "global_show_saccade_arrows",
    # VIZ-8: saccade-type colour key (default on, so always emitted).
    "saccade_type_legend": "global_saccade_type_legend",
    "snap_fixations": "global_fixation_snap_to_word",
    # PRE-3 / ENG-23: the drift-correction connector layer. Its algorithm rides
    # in `_SHARE_VALUE_PARAMS` below — both, or a shared corrected view reopens
    # uncorrected.
    "align_connectors": "global_align_connectors",
    # VIZ-10: autoplay the animated replay on load (default on, so always emitted).
    "anim_autoplay": "global_anim_autoplay",
    "show_heatmap": "global_show_heatmap",
    "show_raw_gaze": "global_show_raw_gaze",
    "show_colorbars": "global_show_colorbars",
    "coordinate_grid": "global_show_coordinate_grid",
    "coordinate_grid_auto": "global_coordinate_grid_auto",
    "hollow_fixations": "global_hollow_fixations",
    "scale_text_to_boxes": "global_scale_text_to_boxes",
    # EXP-5: title/caption on the figure — off by default.
    "show_title_caption": "global_show_title_caption",
}
_SHARE_VALUE_PARAMS = {  # string / choice / color → str (emitted only when set)
    "preproc_short_policy": "global_preproc_short_policy",
    "color_by": "global_color_by",
    "heatmap_style": "global_heatmap_style",
    "heatmap_norm": "global_heatmap_norm",
    "heatmap_metric": "global_heatmap_metric",
    "critical_span_style": "global_critical_span_style",
    "highlight_column": "global_highlight_column",
    "x_field": "global_x_field",
    "y_field": "global_y_field",
    "saccade_style": "global_saccade_style",
    "saccade_render_mode": "global_saccade_render_mode",
    "illustration_label": "global_illustration_label",
    # PRE-3 / ENG-23: vertical drift correction ("Off" or a Carr et al. (2021)
    # algorithm). Since VIZ-23 it applies on all three render paths, so a link
    # that dropped it reopened a visibly different figure.
    "align_algorithm": "global_align_algorithm",
    # VIZ-15 marker shape · VIZ-17 uniform fixation colour · VIZ-18 palette. The
    # palette is a *preset* — the colours it implies ride in the individual params
    # below — so it's expanded first and any explicit colour in the same link
    # wins (see `_apply_url_palette`).
    "fixation_symbol": "global_fixation_symbol",
    "fixation_color": "global_fixation_color",
    "palette": "global_palette",
    "fixation_colorscale": "global_fixation_colorscale",
    "heatmap_colorscale": "global_heatmap_colorscale",
    "saccade_color": "global_saccade_color",
    # UX-86: raw gaze's own style.
    "raw_gaze_color": "global_raw_gaze_color",
    # VIZ-8: colour-by-reading-type mode + the five class colours.
    "saccade_color_mode": "global_saccade_color_mode",
    "saccade_color_forward": "global_saccade_class_color_forward",
    "saccade_color_skip": "global_saccade_class_color_skip",
    "saccade_color_refixation": "global_saccade_class_color_refixation",
    "saccade_color_return_sweep": "global_saccade_class_color_return_sweep",
    "saccade_color_regression": "global_saccade_class_color_regression",
    # VIZ-31: the reading-class *filter* (which classes are drawn at all), as a
    # comma-separated list — the generic writer below already joins a list value,
    # and `_URL_PRESETS` overrides the read side with a validating parser.
    "saccade_classes": "global_saccade_classes",
    "order_font_color": "global_order_font_color",
    "text_color": "global_text_color",
    "highlight_text_color": "global_highlight_text_color",
    "bg_choice": "global_bg_choice",
    "bg_custom": "global_bg_custom",
    "font_family": "global_font_family",
    "word_hover_measure": "global_word_hover_measure",
    "word_hover_fields": "global_word_hover_fields",
    "fixation_hover_fields": "global_fixation_hover_fields",
    # EXP-5: the pattern strings themselves — meaningless while
    # `show_title_caption` is off, but carried unconditionally like every other
    # value param (the reader only applies them once the toggle is on).
    "title_pattern": "global_title_pattern",
    "caption_pattern": "global_caption_pattern",
    # CMP-11: compare mode's own two settings. CMP-8 put `compare=<pid>:<trial>`
    # and `cmp_source` on the link but neither of these, so a shared comparison
    # always reopened as Overlay — and, cross-dataset, immediately resolved away
    # from it. Both read sides are overridden in `_URL_PRESETS` with validating
    # parsers, since each is a closed vocabulary.
    "cmp_layout": "single_compare_layout",
    "cmp_stimulus": "single_compare_stimulus",
}
_SHARE_INT_PARAMS = {
    "order_font_size": "global_order_font_size",
    # VIZ-11 follow-up: the animation frame grid. Worth sharing — a link that
    # says "look at this replay" should reproduce the same smoothness.
    "anim_grid_step_ms": "global_anim_grid_step_ms",
    "anim_max_frames": "global_anim_max_frames",
}
_SHARE_FLOAT_PARAMS = {
    "preproc_short_threshold_ms": "global_preproc_short_threshold_ms",
    "preproc_merge_distance_chars": "global_preproc_merge_distance_chars",
    "line_spacing": "global_line_spacing",
    "saccade_width": "global_saccade_width",
    "fixation_opacity": "global_fixation_opacity",
    "duration_mass_sigma_chars": "global_duration_mass_sigma_chars",
    # VIZ-4: image-stimulus opacity (applies to dataset images too, so worth
    # sharing; the uploaded image itself can't ride a link).
    "stimulus_image_opacity": "global_stimulus_image_opacity",
    # VIZ-4: manual image alignment — origin nudge + size scale (apply to dataset
    # images, so they round-trip; an uploaded image is re-uploaded on the far end).
    "stimulus_image_offset_x": "global_stimulus_image_offset_x",
    "stimulus_image_offset_y": "global_stimulus_image_offset_y",
    "stimulus_image_scale": "global_stimulus_image_scale",
    "coordinate_grid_spacing": "global_coordinate_grid_spacing",
    # UX-86: raw gaze's own style.
    "raw_gaze_marker_size": "global_raw_gaze_marker_size",
    "raw_gaze_opacity": "global_raw_gaze_opacity",
}
_SHARE_INT_RANGE_PARAMS = {
    "marker_size_range": "global_marker_size_range",
    # VIZ-40 (UX-135) closed VIZ-7's last surface gap: the window is now
    # linkable. Read like any other "lo,hi" range — `controls`' slider already
    # treats a value present before it first renders as explicit and clamps it
    # to the recipient's own trial. The **write** side is not generic, though:
    # see the `FIX_RANGE_PARAM` block in `_build_share_query`.
    FIX_RANGE_PARAM: "single_fix_range",
}
_SHARE_FLOAT_RANGE_PARAMS = {
    "fixation_color_range": "global_fixation_color_range",
    "heatmap_color_range": "global_heatmap_color_range",
}

#: PRE-21: URL params that belong to a gated feature. Each maps to the predicate
#: that says whether it is exposed; while it isn't, the param is neither read nor
#: emitted. Kept *in* the contract (`session_keys.py` still pins it, the parser
#: still knows how to read it) — this is a visibility gate, not a wire-format
#: change, so turning the flag on makes existing links work again.
_GATED_URL_PARAMS = {
    "align_algorithm": drift_correction_enabled,
    "align_connectors": drift_correction_enabled,
}

_URL_PRESETS = {
    # Booleans (read side of _SHARE_TOGGLE_PARAMS) + the legacy aliases.
    "hide_fixation_numbers": ("global_show_order", lambda v: not _coerce_bool(v)),
    **{k: (s, _coerce_bool) for k, s in _SHARE_TOGGLE_PARAMS.items()},
    # Strings / choices / colors.
    **{k: (s, str) for k, s in _SHARE_VALUE_PARAMS.items()},
    # Numbers + ranges.
    **{k: (s, int) for k, s in _SHARE_INT_PARAMS.items()},
    **{k: (s, float) for k, s in _SHARE_FLOAT_PARAMS.items()},
    **{k: (s, _parse_int_range) for k, s in _SHARE_INT_RANGE_PARAMS.items()},
    **{k: (s, _parse_float_range) for k, s in _SHARE_FLOAT_RANGE_PARAMS.items()},
    # Validated choice (must come after the generic `str` sweep above, which
    # covers the same param): the drift-correction picker rejects any value
    # outside its options, so the link's spelling is checked here (ENG-23).
    "align_algorithm": ("global_align_algorithm", _parse_align_algorithm),
    "word_hover_fields": ("global_word_hover_fields", _parse_field_list),
    "fixation_hover_fields": ("global_fixation_hover_fields", _parse_field_list),
    # VIZ-31 saccade reading-class filter — validated like `align_algorithm`
    # above, and for the same reason: the multiselect raises on a value outside
    # its options, so an unknown class name has to be rejected here rather than
    # wedging the rail.
    "saccade_classes": ("global_saccade_classes", _parse_saccade_classes),
    # CMP-11 — same rule again: both are `st.segmented_control` options.
    "cmp_layout": ("single_compare_layout", _parse_compare_layout),
    "cmp_stimulus": ("single_compare_stimulus", _parse_compare_stimulus),
}

# Widget bounds for the URL-restorable params that feed a min/max-bounded widget
# (slider / number_input). A hand-crafted link with an out-of-range value would
# otherwise crash the widget on render — Streamlit raises when a Session-State
# value falls outside the widget's range. Clamp on the way in. (Data-dependent
# colour ranges aren't here — the rail's `_clamp_range` handles those against
# the live data.)
_URL_BOUNDED = {
    "global_preproc_short_threshold_ms": (1.0, 500.0),
    "global_preproc_merge_distance_chars": (0.25, 10.0),
    "global_duration_mass_sigma_chars": (0.25, 10.0),
    "global_line_spacing": (1.0, 10.0),
    "global_saccade_width": SACCADE_WIDTH_BOUNDS,
    "global_order_font_size": (6, 72),
    "global_anim_grid_step_ms": (20, 500),
    "global_anim_max_frames": (30, 2000),
    "global_marker_size_range": (4, 40),
    "global_fixation_opacity": (0.1, 1.0),
    "global_stimulus_image_opacity": (0.1, 1.0),
    # VIZ-4: image-alignment nudge — clamp a hand-crafted link to sane ranges.
    "global_stimulus_image_offset_x": (-5000.0, 5000.0),
    "global_stimulus_image_offset_y": (-5000.0, 5000.0),
    "global_stimulus_image_scale": (0.25, 3.0),
    "global_coordinate_grid_spacing": (10.0, 5000.0),
}


def _clamp_url_value(state_key: str, value):
    """Clamp a deep-linked value to its widget bounds (scalars and 2-tuples)."""
    bounds = _URL_BOUNDED.get(state_key)
    if bounds is None:
        return value
    lo, hi = bounds
    if isinstance(value, (tuple, list)) and len(value) == 2:
        a, b = max(lo, min(value[0], hi)), max(lo, min(value[1], hi))
        return (min(a, b), max(a, b))
    return max(lo, min(value, hi))


# data_choice → ?source= value, for the built-in sources a URL can fully rebuild.
# Sources absent here (uploaded tables, stored datasets) can't be reconstructed
# from a link — the Share panel warns and shares the view settings only. Public
# corpora are covered by the generic `corpus` token below instead of one entry
# each. Mirrors the `source` handling in `main()`.
_SHAREABLE_SOURCES = {
    AUTHOR_CHOICE: "author",
    DEMO_CHOICE: "demo",
    ONESTOP_CHOICE: "onestop",
    MULTIPLEYE_BUNDLE_CHOICE: "multipleye",
    SYNTHETIC_CHOICE: "synthetic",
    # DATA-3: the public OneStop corpus (OSF download-on-demand) is shareable too;
    # its variant/regime/parts options ride alongside via `_build_share_query`.
    ONESTOP_PUBLIC_CHOICE: "onestop_public",
}


def _source_choice_for_param(value) -> str | None:
    """Invert `_SHAREABLE_SOURCES`: a ``?source=``-style token → the data choice.

    Used by CMP-8's `cmp_source`, which names scanpath **B's** corpus in the
    same vocabulary. An unknown token returns ``None`` — the link then simply
    doesn't move the comparison dataset, which is a safe degrade rather than a
    wedged picker.
    """
    if not value:
        return None
    token = str(value).lower()
    for choice, param in _SHAREABLE_SOURCES.items():
        if param == token:
            return choice
    return None


# ---------------------------------------------------------------------------
# DATA-27 (Task 12): every public corpus on the link — `?source=corpus&corpus=…`
#
# `_SHAREABLE_SOURCES` above works for sources whose *identity is the token*.
# The public corpora can't: `app.public_dataset_registry()` is the built-in
# corpora **∪ one entry per prepared corpus discovered in the local bundle**, a
# catalogue that varies per machine, so there is no fixed token per corpus to
# freeze. One generic token names the kind and a second param names the corpus.
#
# Deliberately generic (R42): a benchmark-only branch would have to re-derive
# which registry entry produced the picker's collapsed choice, duplicating
# `app.resolve_data_source`'s healing logic — and "these corpora are
# special" is the assumption this plan has been bitten by repeatedly. A built-in
# corpus and a prepared one are the same kind of thing here.
CORPUS_SOURCE_TOKEN = "corpus"

# What gets slugged is the entry's **stable identifier** — a prepared corpus'
# manifest `name`, a built-in's registry `short` — never its display label, which
# carries em-dashes and "(harmonised benchmark)" and is the thing most likely to
# be reworded. A link has to survive a rewording.
#
# Prepared corpora are namespaced with this prefix because the two identifier
# spaces overlap: PoTeC and OneStop each ship *both* natively and harmonised, and
# both entries are kept on purpose, so bare slugs would collide and a link would
# silently open the wrong corpus — the worst failure this feature can have. The
# prefix is a constant in code, so it is unaffected by any relabelling, and it
# names the property that actually differs (a re-derived harmonisation of the
# publisher's release) rather than the pipeline that produced it.
_PREPARED_CORPUS_SLUG_PREFIX = "harmonised-"


def _slugify_corpus(value: str) -> str:
    """Lowercase, ASCII-safe, hyphen-joined form of a corpus identifier."""
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


def corpus_slug(label: str, spec) -> str:
    """The ``?corpus=`` slug for one `public_dataset_registry()` entry, or ``""``.

    Empty for an entry a link cannot name:

    * the bootstrap placeholder the registry offers while **zero** corpora are
      discovered — it exists to carry a directory input, so there is nothing to
      reopen;
    * an identifier with nothing sluggable in it. A manifest ``name`` written in
      a non-Latin script slugifies to ``""``, and returning the bare namespace
      prefix for it would give *every* such corpus the same slug **and** one the
      reader can never match (it re-slugifies its input, which strips the
      trailing hyphen). Not shareable is honest, and is already a supported
      state; a slug naming several corpora is the failure this scheme exists to
      prevent.
    """
    if spec.get("setup_only"):
        return ""
    # `benchmark_dataset` is the manifest `name`, put on the spec by Task 11R
    # precisely as the stable identifier for this wire format.
    if dataset := str(spec.get("benchmark_dataset") or "").strip():
        slug = _slugify_corpus(dataset)
        return f"{_PREPARED_CORPUS_SLUG_PREFIX}{slug}" if slug else ""
    return _slugify_corpus(str(spec.get("short") or label))


def registry_corpus_slugs() -> dict[str, str]:
    """``registry label -> slug`` for every corpus a link can name right now.

    A slug **two** entries would claim is dropped from both — so it is neither
    emitted nor resolvable, and the link degrades onto the existing "doesn't move
    the picker" path. The namespace prefix stops the collision this catalogue is
    known to have (PoTeC and OneStop each ship natively *and* harmonised) from
    arising at all, but avoidance is not detection, and three ways in remain:
    `_slugify_corpus` is not injective (``ZuCo-1`` and ``ZuCo 1`` slug alike, and
    near-identical names are the norm here — ``MECOL1W1``/``MECOL1W2``/
    ``MECOL2W1``/``MECOL2W2``, ``ZuCo1``/``ZuCo2``); nothing reserves the prefix
    against a future built-in whose ``short`` is "Harmonised Foo"; and a bundle
    can hold two corpora whose names differ only in punctuation. Refusing to
    answer costs the recipient one link. Picking a winner opens the wrong
    corpus, silently, which is the worst failure this feature can have.

    Reads `app.public_dataset_registry()` — the *function*, never the static
    `PUBLIC_DATASET_REGISTRY` dict, which answers for the three built-ins only.
    The import is inside the function because `app` imports this module.
    """
    from scanpath_studio.app import public_dataset_registry

    claimed: dict[str, list] = {}
    for label, spec in public_dataset_registry().items():
        if slug := corpus_slug(label, spec):
            claimed.setdefault(slug, []).append(str(label))
    return {labels[0]: slug for slug, labels in claimed.items() if len(labels) == 1}


def corpus_choice_for_slug(value) -> str | None:
    """A ``?corpus=`` slug → its registry label, or ``None``.

    ``None`` covers "this reader's bundle doesn't hold that corpus" (the common
    case — the recipient has no bundle, or a different subset of one), an unknown
    slug, and a slug two entries would answer to (`registry_corpus_slugs` has
    already dropped that one). All degrade the way `_source_choice_for_param`
    does: the link simply doesn't move the picker. Never guess a near match — a
    slug resolving to the wrong corpus opens the wrong data silently.
    """
    if not value:
        return None
    slug = _slugify_corpus(value)
    for label, known in registry_corpus_slugs().items():
        if known == slug:
            return label
    return None


def _selected_corpus(data_choice: str) -> tuple[str, dict]:
    """Which registry corpus a share is describing: ``(label, spec)``.

    ``("", {})`` when the active source is not a public corpus.

    `app.resolve_data_source` collapses **any** registry label to
    `PUBLIC_DATASETS_CHOICE` and stashes the label on `public_dataset_choice`, so
    that is where the answer lives for a link built from the running app. A
    caller holding the label itself (the tests, and anything predating the
    collapse) is honoured as-is.
    """
    from scanpath_studio.app import public_dataset_registry

    registry = public_dataset_registry()
    if data_choice in registry:
        return str(data_choice), registry[data_choice]
    if data_choice == PUBLIC_DATASETS_CHOICE:
        chosen = st.session_state.get(PUBLIC_DATASET_CHOICE)
        if chosen in registry:
            return str(chosen), registry[chosen]
    return "", {}


def _apply_url_palette(qp) -> None:
    """Expand a ``?palette=<name>`` deep link into its colour session keys (VIZ-18).

    A palette is a preset over the ordinary colour keys, so it must be applied
    *before* the generic ``_URL_PRESETS`` loop — and any colour the same link
    states explicitly has to win over it. Both fall out of skipping the keys the
    URL already carries and using ``setdefault`` for the rest.
    """
    name = qp.get("palette")
    if name not in PALETTES:
        return
    explicit = {_URL_PRESETS[k][0] for k in qp if k in _URL_PRESETS}
    for state_key, value in palette_state(name).items():
        if state_key not in explicit:
            st.session_state.setdefault(state_key, value)


def _apply_url_preset() -> str | None:
    """Read `st.query_params` and preset Streamlit session state for deep links.

    Returns the URL-requested `source` ("onestop"/"demo"/"upload") or `None`.
    Call this at the very top of `main()` — before any widgets render — so
    session_state values are picked up as the widgets' initial values.

    URL schema (all params optional):
        ?source=onestop          → force "OneStop server bundle" data source
                                   (also demo / synthetic / upload — see main())
        ?source=corpus&corpus=potec
                                 → a public corpus: one entry of
                                   `app.public_dataset_registry()`, built-in or
                                   locally prepared (`corpus=harmonised-potec`).
                                   Resolved in main(); an unresolvable slug
                                   leaves the picker alone and says so.
        &participant=p001        → preselect participant (Participant mode)
        &trial=37                → preselect trial_index slider
        &trial_id=p001_3_Adv     → land on this exact trial id, any picker mode
                                   (applied after combos build — see
                                   _apply_url_trial_selection; emitted by Share)
        &screen=intro            → open this child screen of a multipart trial
        &tab=animation           → pre-tick the Animate toggle (legacy; there's
                                   no separate Animated Scanpath tab anymore)
        &heatmap_colorscale=Greens
        &hide_fixation_numbers=1
        &show_saccades=1
        &show_heatmap=1
        ...etc — see _URL_PRESETS above

    Bonus side-effect: when any colorscale is set via URL, also forces the
    "Advanced styling" expander open so the value is visible/editable.

    External tools can deep-link into this app via the URL schema above to
    land on a specific trial with the reviewer's preferred viz settings.
    """
    qp = st.query_params
    if not qp:
        return None

    # Seed selection state for every `select_trial` host (the prefixes in
    # `_SELECTION_PREFIXES`). `?participant=` + `?trial=` map onto Participant mode
    # with the matching participant / slider value. Seeding every prefix keeps a
    # non-first picker from defaulting to "Trial" mode and landing on the
    # alphabetically-first trial instead of the deep-linked one.
    if "participant" in qp or "trial" in qp:
        if "participant" in qp:
            # Capture the deep-link participant ONCE, in a dedicated key the live
            # selector never overwrites. The OneStop loader keys its per-pid shard
            # fast-path off this — so it loads one pid for an embedded review deep
            # link, while ordinary in-app participant switching just *filters*
            # already-loaded data instead of re-invoking the loader.
            st.session_state.setdefault("_deeplink_participant", str(qp["participant"]))
        for prefix in _SELECTION_PREFIXES:
            st.session_state.setdefault(f"{prefix}_select_trial_mode", "Participant")
            if "participant" in qp:
                st.session_state.setdefault(
                    f"{prefix}_participant", str(qp["participant"])
                )
            if "trial" in qp:
                try:
                    st.session_state.setdefault(f"{prefix}_slider", int(qp["trial"]))
                except (ValueError, TypeError):
                    st.warning(f"Ignored bad URL param ?trial={qp['trial']!r}")

    _apply_url_palette(qp)

    for url_key, (state_key, coerce) in _URL_PRESETS.items():
        if url_key not in qp:
            continue
        # PRE-21: a link naming a gated-off feature is ignored *silently* — no
        # "unavailable in this build" warning. The app hasn't been released, so
        # no such link exists in the world yet; this only has to not crash, and
        # not leave a value the rail can't show but the Share writer would emit.
        if url_key in _GATED_URL_PARAMS and not _GATED_URL_PARAMS[url_key]():
            continue
        raw = qp[url_key]
        try:
            value = coerce(raw)
        except (ValueError, TypeError):
            st.warning(f"Ignored bad URL param ?{url_key}={raw!r}")
            continue
        # Clamp bounded widgets so a hand-crafted out-of-range link can't crash
        # the slider / number_input on render.
        value = _clamp_url_value(state_key, value)
        st.session_state.setdefault(state_key, value)

    # DATA-22 §7 surface 2 (read side): badge the values this link is carrying
    # with how the *sender* knew them, so an assumed monitor arrives labelled as
    # assumed instead of looking measured. Parsing is deliberately forgiving —
    # unknown groups and unknown provenance words are dropped, never raised on —
    # because a mangled param should cost the recipient badges, not the link.
    if SETUP_PROVENANCE_PARAM in qp:
        arrived = parse_provenance_param(str(qp[SETUP_PROVENANCE_PARAM]))
        if arrived:
            st.session_state.setdefault(
                SETUP_PROVENANCE_STATE_KEY, {g: str(p) for g, p in arrived.items()}
            )

    # Heatmap / fixation colorscale only render under the Advanced expander —
    # auto-open it so the URL value is exposed in the rail.
    if "heatmap_colorscale" in qp or "fixation_colorscale" in qp:
        st.session_state.setdefault("global_advanced", True)

    # Animation is now a checkbox in the Scanpath Visualization tab (no separate
    # tab), so a legacy `?tab=animation` deep link just pre-ticks it.
    if (qp.get("tab") or "").lower() == "animation":
        st.session_state.setdefault("single_animate", True)
    if qp.get("screen") not in (None, ""):
        st.session_state.setdefault("single_screen_id", str(qp["screen"]))

    # CMP-8 §7: `?compare=<participant>:<trial>` turns Compare on and parks B's
    # ids for the picker to consume once its candidate list exists (the picker's
    # own key holds a render-time *label*, so a link can't seed it directly —
    # the same reason ENG-36's trial jump parks a request). `cmp_source` names
    # B's corpus; an unknown name is dropped rather than honoured, which falls
    # back to "B is in this dataset" instead of wedging the picker.
    compare_raw = str(qp.get(COMPARE_PARAM) or "")
    if ":" in compare_raw:
        participant_b, _, trial_b = compare_raw.partition(":")
        if participant_b and trial_b:
            st.session_state.setdefault(SINGLE_COMPARE_TOGGLE, True)
            st.session_state.setdefault(
                PENDING_COMPARE_STATE_KEY,
                {"participant_id": participant_b, "trial_id": trial_b},
            )
            source_b = _source_choice_for_param(qp.get(COMPARE_SOURCE_PARAM))
            if source_b is not None:
                st.session_state.setdefault(COMPARE_SOURCE_STATE_KEY, source_b)

    # DATA-3: the public OneStop source options (variant / regime / parts) ride
    # the deep link too, seeded before the loader's widgets render. Validate each
    # against its known domain so a hand-edited link can't wedge the widget.
    if qp.get("onestop_variant") in ONESTOP_VARIANT_LABELS:
        st.session_state.setdefault("onestop_variant", qp["onestop_variant"])
    if qp.get("onestop_regime") in ONESTOP_REGIME_LABELS:
        st.session_state.setdefault("onestop_regime", qp["onestop_regime"])
    if "onestop_parts" in qp:
        parts = [
            p for p in str(qp["onestop_parts"]).split(",") if p in ONESTOP_PART_LABELS
        ]
        if parts:
            st.session_state.setdefault("onestop_parts", parts)

    if (qp.get("source") or "").lower() == "author":
        if "author_text" in qp:
            st.session_state.setdefault("author_text", str(qp["author_text"]))
        if "author_events" in qp:
            try:
                events = json.loads(str(qp["author_events"]))
                if not isinstance(events, list):
                    raise ValueError
            except (ValueError, TypeError, json.JSONDecodeError):
                st.warning("Ignored malformed authored-fixation data in the URL.")
            else:
                st.session_state.setdefault(
                    "_authored_events_frame", pd.DataFrame(events)
                )
                # Prevent the authoring widget's text-change initializer from
                # replacing the just-restored events on its first render.
                st.session_state.setdefault(
                    "_author_text_for_events",
                    str(qp.get("author_text", st.session_state.get("author_text", ""))),
                )

    source = qp.get("source")
    return source.lower() if source else None


# plot-config layer key → viz-control session_state key. The inverse of the
# `layers` block written by `tabs._render_plot_config_expander`.
_PLOT_CONFIG_LAYER_KEYS = {
    "words": "global_show_words",
    "word_labels": "global_show_labels",
    # UX-128: the 📄 Stimulus section's master switch.
    "stimulus": "global_show_stimulus",
    "fixations": "global_show_fix",
    "order_labels": "global_show_order",
    "saccades": "global_show_saccades",
    "saccade_arrows": "global_show_saccade_arrows",
    "heatmap": "global_show_heatmap",
    "raw_gaze": "global_show_raw_gaze",
    "stimulus_image": "global_show_stimulus_image",
    "full_monitor": "global_fit_to_monitor",
    "autoplay": "global_anim_autoplay",
}
# Static widget bounds, mirrored from controls.render_plot_controls /
# render_canvas_controls, so a restored value is clamped to a range the
# widget will accept.
_CANVAS_BOUNDS = (100, 10000)
_FONT_BOUNDS = (6, 72)
_MARKER_BOUNDS = (4, 40)


# --- Save & restore config schema versioning (ENG-11) ---------------------
#
# Single source of truth for the "💾 Save & restore" JSON schema version. The
# writer (`tabs._build_studio_config`) stamps this onto every saved config; the
# reader (`_restore_plot_config`) upgrades an older upload to it before applying,
# so a config saved by an earlier build keeps loading as the layout evolves.
#
#   schema 1 — the original plot-config-only format (no `schema` key at all,
#              no annotations / provenance / text / highlighting sections).
#   schema 2 — config + annotations + text/highlighting + provenance.
#
# **Bump `PLOT_CONFIG_SCHEMA` and register a migration in `_PLOT_CONFIG_MIGRATIONS`
# whenever the config layout changes** (a renamed key, a moved section, a changed
# value encoding). Each migration is a pure `dict -> dict` upgrading version N to
# N+1; they run in sequence so a very old config is walked forward one step at a
# time. The field-by-field reader already tolerates *missing* sections, so a
# migration is only needed when an old key must be *translated*, not merely when
# new keys are added.
PLOT_CONFIG_SCHEMA = 3


def _detect_config_schema(config: dict) -> int:
    """Best-effort schema version of an uploaded config.

    Schema 1 (the original plot-config-only format) predates the ``schema`` key,
    so a missing or non-numeric value means version 1 rather than an error.
    ``OverflowError`` is caught too: Python's ``json.loads`` accepts the
    non-standard ``Infinity`` / ``NaN`` literals, and ``int(float("inf"))`` raises
    it — a hand-edited config with such a ``schema`` should still degrade to v1
    (and keep its valid plot settings) rather than abort the whole restore."""
    raw = config.get("schema")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError, OverflowError):
        return 1


def _migrate_config_1_to_2(config: dict) -> dict:
    """Upgrade a schema-1 config to schema 2.

    Schema 1 held only plot settings — no annotations / provenance / text /
    highlighting sections. Those were *added* in schema 2, and `_restore_plot_config`
    already treats an absent section as "keep the default", so a schema-1 config
    needs no key translation: this migration is intentionally an identity beyond
    the version stamp applied by `_migrate_plot_config`. It stays registered so the
    migration chain is exercised (and so a future schema-3 has a worked example to
    copy) rather than special-casing "no migration needed"."""
    return config


def _migrate_config_2_to_3(config: dict) -> dict:
    """Upgrade to the optional VIZ-34 coordinate-grid axes fields.

    Stamp explicit defaults so a v1/v2 file restores the complete current
    settings contract without changing its rendered result.
    """
    migrated = dict(config)
    if "axes" in config and not isinstance(config.get("axes"), dict):
        return migrated
    axes = dict(config.get("axes") or {})
    axes.setdefault("coordinate_grid", False)
    axes.setdefault("coordinate_grid_auto", True)
    axes.setdefault("coordinate_grid_spacing", 100.0)
    migrated["axes"] = axes
    return migrated


# version N -> callable that upgrades an N config to N+1. Keyed by the *source*
# version so `_migrate_plot_config` can walk an old config forward step by step.
_PLOT_CONFIG_MIGRATIONS = {
    1: _migrate_config_1_to_2,
    2: _migrate_config_2_to_3,
}


def _migrate_plot_config(config: dict) -> tuple[dict, str | None]:
    """Upgrade an uploaded plot-config dict to the current schema.

    Returns ``(config, note)``. ``config`` is a **deep** copy stamped with the
    resolved ``schema`` and walked through every registered migration between its
    detected version and :data:`PLOT_CONFIG_SCHEMA`. The copy is deep (configs are
    small) so a migration is genuinely ``dict -> dict`` pure: a future step that
    translates a renamed key by editing a nested section in place can't leak back
    into the caller's dict. ``note`` is a human-readable warning or ``None`` — set
    when the config was saved by a *newer* build than this one understands (we
    still restore best-effort: the reader simply ignores keys it doesn't
    recognise), or when the chain is missing a step and can't reach the current
    version."""
    version = _detect_config_schema(config)
    working = copy.deepcopy(config)
    if version > PLOT_CONFIG_SCHEMA:
        return working, (
            "This plot config was saved by a newer version of Scanpath Studio "
            f"(format v{version}; this build understands up to v{PLOT_CONFIG_SCHEMA}). "
            "Settings it doesn't recognise were ignored."
        )
    while version < PLOT_CONFIG_SCHEMA:
        migrate = _PLOT_CONFIG_MIGRATIONS.get(version)
        if migrate is None:
            note = (
                f"Couldn't fully upgrade this plot config (no migration from format "
                f"v{version} to v{PLOT_CONFIG_SCHEMA}); applied what still fit."
            )
            working["schema"] = version
            return working, note
        working = migrate(working)
        version += 1
    working["schema"] = version
    return working, None


def _restore_selection(
    selection: dict, combos: pd.DataFrame, key_prefix: str = "single"
) -> bool:
    """Best-effort: point a tab's trial picker at the saved ``(participant,
    trial)``. Returns True when a matching trial is found in the current
    (filtered) data. Mirrors the key scheme of ``utils.select_trial`` for the
    given ``key_prefix``, which is now one scheme for every dataset (BUG-23 —
    a composite trial id no longer gets a picker, or keys, of its own).

    The trial id is sufficient on its own: a missing/blank participant (e.g. a
    ``?trial_id=`` link with no ``?participant=``) falls through to the trial-id-
    alone match below, so the picker still lands on the trial."""
    pid = selection.get("participant_id")
    tid = selection.get("trial_id")
    if tid in (None, "") or combos.empty:
        return False
    pid, tid = str(pid), str(tid)
    match = combos[
        (combos["participant_id"].astype(str) == pid)
        & (combos["trial_id"].astype(str) == tid)
    ]
    if match.empty:  # participant absent/blank or filtered out — try trial id alone
        match = combos[combos["trial_id"].astype(str) == tid]
    if match.empty:
        return False
    row = match.iloc[0]
    st.session_state[f"{key_prefix}_select_trial_mode"] = "Trial"
    # The picker renders a single dropdown keyed `<prefix>_trial_id` whose
    # *options* are the trial_field values (`unique_trial_id` when present), so
    # seed that one key with this row's option value — not a
    # `<prefix>_<trial_field>` key, which no widget reads. The slider
    # (`<prefix>_trial_pos`) needs no seeding: the picker mirrors it onto the
    # selectbox's value before it renders.
    trial_field = (
        "unique_trial_id" if "unique_trial_id" in combos.columns else "trial_id"
    )
    st.session_state[f"{key_prefix}_trial_id"] = str(row[trial_field])
    if selection.get("screen_id") not in (None, ""):
        st.session_state[f"{key_prefix}_screen_id"] = str(selection["screen_id"])
    return True


def _apply_url_trial_selection(combos: pd.DataFrame) -> None:
    """Apply a ``?trial_id=`` deep link to the trial picker — exactly once.

    Unlike ``?trial=`` (a slider *index*, seeded before any widget renders in
    ``_apply_url_preset``), ``?trial_id=`` carries the canonical trial id, so it
    lands on the exact trial regardless of which picker mode produced the share
    link — but it needs the built ``combos``, so it runs from ``main()`` after
    they exist. Reuses ``_restore_selection`` (the same seeding the plot-config
    restore uses), seeding *every* selection prefix so non-first tabs land on the
    trial too (mirrors the ``_SELECTION_PREFIXES`` loop in ``_apply_url_preset``).
    The Share button emits this param; see ``_build_share_query``.
    """
    if st.session_state.get("_url_trial_applied"):
        return
    trial_id = st.query_params.get("trial_id")
    if not trial_id:
        return
    selection = {
        "participant_id": st.query_params.get("participant"),
        "trial_id": trial_id,
        "screen_id": st.query_params.get("screen"),
    }
    # Stamp the once-flag only after the trial is actually found, so a rerun
    # where `combos` is still empty/partial (e.g. the OneStop shard is mid-load)
    # retries on the next rerun instead of losing the deep link. `_restore_selection`
    # only writes when it matches, so retrying never clobbers manual navigation.
    # Materialize (not a short-circuiting any()) so EVERY prefix is seeded, not
    # just up to the first match.
    results = [
        _restore_selection(selection, combos, key_prefix=prefix)
        for prefix in _SELECTION_PREFIXES
    ]
    if any(results):
        st.session_state["_url_trial_applied"] = True


#: Where an in-app "open this trial" request waits for `combos` to exist.
PENDING_TRIAL_KEY = "_pending_trial_selection"


def request_trial(participant: str | None, trial_id: str | None) -> None:
    """Ask the app to open ``trial_id`` in the Scanpath view (ENG-36).

    Called from a *callback* — the reader/trial tables in Corpus Analysis have a
    "go to this trial" button — which runs before the script, so the trial pool
    it needs (``combos``) does not exist yet. The request is therefore parked and
    applied by :func:`_apply_pending_trial_selection` once ``main`` has built the
    pool, which is the same shape as the ``?trial_id=`` deep link and reuses the
    same seeding.
    """
    if not trial_id:
        return
    st.session_state[PENDING_TRIAL_KEY] = {
        "participant_id": str(participant) if participant else None,
        "trial_id": str(trial_id),
    }
    _go_scanpath()


def _apply_pending_trial_selection(combos: pd.DataFrame) -> None:
    """Consume a :func:`request_trial` hop, if one is waiting.

    Held over only while the pool cannot answer — an *empty* ``combos`` means
    still loading (the OneStop shard, a big upload), and dropping the request
    there would lose the click. Once the pool exists the request is resolved one
    way or the other and cleared either way: a request the pool has genuinely
    answered "not here" must not sit in session state and then fire later,
    silently re-pointing the picker the moment a filter change happens to bring
    that trial back into scope. Unlike the deep-link twin there is no once-flag —
    each click is its own request, and the key *is* the flag.
    """
    selection = st.session_state.get(PENDING_TRIAL_KEY)
    if not selection or combos is None or combos.empty:
        return
    for prefix in _SELECTION_PREFIXES:
        _restore_selection(selection, combos, key_prefix=prefix)
    st.session_state.pop(PENDING_TRIAL_KEY, None)


def _seed_column_mapping(mapping, *, overwrite: bool = False) -> None:
    """Seed the ``col_map_*`` session keys from a saved config's ``column_mapping``
    so a restored config pre-fills the wizard mapping + kept-field choices (and
    the user skips re-mapping). Stale values that don't match the current data are
    tolerated by the mapping widgets (selectbox index fallback / multiselect
    cleanup). Old configs used ``*_paragraph`` keys (now ``*_text_id``) — these
    are translated for backward compatibility.

    ``overwrite`` controls the write semantics. The plot-config restore runs
    *before* any widget renders, so ``setdefault`` (overwrite=False) is correct —
    it never clobbers a value a later widget will set. The wizard's "Restore a
    saved setup" step, however, runs *after* the mapping widgets were created on a
    previous render, so those keys already exist; ``setdefault`` would be a no-op
    and the restore would silently do nothing. There, pass ``overwrite=True`` so
    an explicit restore wins (the step reruns afterwards, and it runs before the
    mapping widgets re-instantiate, so writing the keys is safe)."""
    if not isinstance(mapping, dict):
        return
    for raw_key, value in mapping.items():
        if (
            not isinstance(raw_key, str)
            or not raw_key.startswith("col_map_")
            or raw_key.endswith("_upload")
        ):
            continue
        key = raw_key
        if key.endswith("_paragraph"):
            key = key[: -len("_paragraph")] + "_text_id"
        if overwrite:
            st.session_state[key] = value
        else:
            st.session_state.setdefault(key, value)


@dataclass
class _RestoreContext:
    """Validated writes and diagnostics for one plot-config restoration."""

    config: dict
    applied: int = 0
    skipped: list = field(default_factory=list)

    def section(self, name: str) -> dict:
        value = self.config.get(name)
        return value if isinstance(value, dict) else {}

    @staticmethod
    def number(value) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def put(self, key: str, value) -> None:
        st.session_state[key] = value
        self.applied += 1

    def put_valid(self, valid: bool, key: str, value, skip_label: str) -> None:
        if valid:
            self.put(key, value)
        else:
            self.skipped.append(skip_label)

    def put_int(self, value, key: str, lo: int, hi: int, skip_label: str) -> None:
        number = self.number(value)
        if number is None:
            self.skipped.append(skip_label)
        else:
            self.put(key, max(lo, min(int(number), hi)))

    def put_float(self, value, key: str, lo: float, hi: float, skip_label: str) -> None:
        number = self.number(value)
        if number is None:
            self.skipped.append(skip_label)
        else:
            self.put(key, max(lo, min(float(number), hi)))


def _restore_plot_config(
    config: dict, combos: pd.DataFrame, fixations: pd.DataFrame
) -> tuple[int, list]:
    """Seed session_state from an uploaded plot-config dict so the rail
    widgets render with the saved settings. Returns ``(applied, skipped)`` where
    ``skipped`` lists human-readable labels that didn't fit the current data.

    Inverse of the config built in ``tabs._render_plot_config_expander``. Runs
    before any widget renders (see ``_apply_uploaded_plot_config``); data-
    dependent fields are validated against the loaded data and skipped when they
    don't apply, so a config shared with a different dataset degrades gracefully."""
    # ENG-11: upgrade an older (or flag a newer) saved config to the current
    # schema before reading its fields, so configs keep loading across versions.
    config, migration_note = _migrate_plot_config(config)
    if migration_note:
        st.toast(migration_note, icon="⚠️")

    restore = _RestoreContext(config)
    section = restore.section
    number = restore.number
    put = restore.put
    put_valid = restore.put_valid
    put_int = restore.put_int
    put_float = restore.put_float
    skipped = restore.skipped

    # Older valid configs predate the illustration/preprocessing sections. They
    # still need deterministic defaults for the newly frozen state keys, while
    # a document made entirely of wrong-typed sections must remain a true no-op.
    has_valid_plot_section = any(
        isinstance(config.get(name), dict)
        for name in (
            "layers",
            "coloring",
            "sizing",
            "canvas_px",
            "axes",
            "text",
            "highlighting",
        )
    )

    # Re-apply the saved column mapping + kept-field choices (so restoring a
    # config skips re-mapping). Seeded before the mapping widgets render.
    _seed_column_mapping(config.get("column_mapping"))

    layers = section("layers")
    for cfg_key, state_key in _PLOT_CONFIG_LAYER_KEYS.items():
        if cfg_key in layers:
            put(state_key, bool(layers[cfg_key]))

    illustration = section("illustration")
    if "label_mode" in illustration:
        put_valid(
            illustration["label_mode"] in ("Auto", "Show", "Hide"),
            "global_illustration_label",
            illustration["label_mode"],
            "illustration label",
        )
    elif "illustration" not in config and has_valid_plot_section:
        put("global_illustration_label", "Auto")

    preprocessing = section("preprocessing")
    if "enabled" in preprocessing:
        put("global_preproc_enabled", bool(preprocessing["enabled"]))
    if "discard_blink_adjacent" in preprocessing:
        put(
            "global_preproc_blink_adjacent",
            bool(preprocessing["discard_blink_adjacent"]),
        )
    if "short_policy" in preprocessing:
        put_valid(
            preprocessing["short_policy"]
            in ("Off", "Merge", "Merge then discard", "Discard"),
            "global_preproc_short_policy",
            preprocessing["short_policy"],
            "short-fixation policy",
        )
    if "short_threshold_ms" in preprocessing:
        put_float(
            preprocessing["short_threshold_ms"],
            "global_preproc_short_threshold_ms",
            1.0,
            500.0,
            "short-fixation threshold",
        )
    if "merge_distance_chars" in preprocessing:
        put_float(
            preprocessing["merge_distance_chars"],
            "global_preproc_merge_distance_chars",
            0.25,
            10.0,
            "short-fixation merge distance",
        )
    elif "preprocessing" not in config and has_valid_plot_section:
        # Schema-1/2 configs have no preprocessing block; pin the same defaults
        # used by the controls without treating a malformed explicit block as
        # permission to overwrite live state.
        put("global_preproc_enabled", False)
        put("global_preproc_blink_adjacent", True)
        put("global_preproc_short_policy", "Off")
        put("global_preproc_short_threshold_ms", 80.0)
        put("global_preproc_merge_distance_chars", 1.0)

    coloring = section("coloring")
    # VIZ-18: the palette goes FIRST — it presets the individual colour keys, and
    # every explicit colour saved alongside it (below) must overwrite that preset,
    # not the other way round. Same ordering rule as the `?palette=` deep link.
    palette = coloring.get("palette")
    if palette is not None:
        if palette in PALETTES:
            for state_key, value in palette_state(palette).items():
                put(state_key, value)
            put("global_palette", palette)
        elif palette != CUSTOM_PALETTE:
            skipped.append("palette")
        # `Custom` is a legitimate saved value, not a bad one — it means the
        # config was written from hand-edited colours, which ride in the explicit
        # colour keys below. Nothing to preset, and nothing to warn about.
    if "heatmap_style" in coloring:
        style = coloring["heatmap_style"]
        put_valid(
            style in ("Word boxes", "Interpolated", "Duration mass"),
            "global_heatmap_style",
            style,
            "heatmap style",
        )
    if "duration_mass_sigma_chars" in coloring:
        put_float(
            coloring["duration_mass_sigma_chars"],
            "global_duration_mass_sigma_chars",
            0.25,
            10.0,
            "duration-mass sigma",
        )
    elif isinstance(config.get("coloring"), dict):
        put("global_duration_mass_sigma_chars", 1.0)
    if "heatmap_norm" in coloring:
        put_valid(
            coloring["heatmap_norm"] in ("Linear", "Log"),
            "global_heatmap_norm",
            coloring["heatmap_norm"],
            "heatmap colour scaling",
        )
    if "color_by" in coloring:
        put_valid(
            coloring["color_by"] in color_field_options(fixations),
            "global_color_by",
            coloring["color_by"],
            "color-by field",
        )
    if "heatmap_metric" in coloring:
        put_valid(
            coloring["heatmap_metric"] in ("duration_ms", "counts"),
            "global_heatmap_metric",
            coloring["heatmap_metric"],
            "heatmap metric",
        )
    if "show_colorbars" in coloring:
        put("global_show_colorbars", bool(coloring["show_colorbars"]))
    for cfg_key, state_key in (
        ("fixation_colorscale", "global_fixation_colorscale"),
        ("heatmap_colorscale", "global_heatmap_colorscale"),
    ):
        val = coloring.get(cfg_key)
        if val is not None:
            put_valid(val in COLORSCALES, state_key, val, cfg_key.replace("_", " "))
    sac = coloring.get("saccade_color")
    if isinstance(sac, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", sac):
        put("global_saccade_color", sac)
    if "saccade_style" in coloring:
        put_valid(
            coloring["saccade_style"] in SACCADE_DASH_OPTIONS,
            "global_saccade_style",
            coloring["saccade_style"],
            "saccade line style",
        )
    if "saccade_width" in coloring:
        put_float(
            coloring["saccade_width"],
            "global_saccade_width",
            SACCADE_WIDTH_BOUNDS[0],
            SACCADE_WIDTH_BOUNDS[1],
            "saccade line width",
        )
    # VIZ-9: linear-reading mode (arced saccades + snap fixations above words).
    if "saccade_render_mode" in coloring:
        put_valid(
            coloring["saccade_render_mode"] in ("Straight", "Arc"),
            "global_saccade_render_mode",
            coloring["saccade_render_mode"],
            "saccade line shape",
        )
    if "fixation_snap_to_word" in coloring:
        put("global_fixation_snap_to_word", bool(coloring["fixation_snap_to_word"]))
    # PRE-3 / ENG-23: vertical drift correction. Validated like the deep link —
    # an algorithm the build no longer ships must not reach the selectbox.
    # PRE-21: and skipped entirely while the feature is gated off, silently, for
    # the same reason the deep link is (there is no such config in the world yet
    # — this only has to not crash).
    if drift_correction_enabled():
        if "drift_correction" in coloring:
            put_valid(
                coloring["drift_correction"] in _ALIGN_OPTIONS,
                "global_align_algorithm",
                coloring["drift_correction"],
                "drift correction",
            )
        if "drift_connectors" in coloring:
            put("global_align_connectors", bool(coloring["drift_connectors"]))
    # VIZ-8: colour-by-reading-type mode + per-class palette + optional legend.
    mode = coloring.get("saccade_color_mode")
    if mode is not None:
        put_valid(
            mode in SACCADE_COLOR_MODES,  # VIZ-19 added "Forward / regression"
            "global_saccade_color_mode",
            mode,
            "saccade colour mode",
        )
    if "saccade_type_legend" in coloring:
        put("global_saccade_type_legend", bool(coloring["saccade_type_legend"]))
    class_colors = coloring.get("saccade_class_colors")
    if isinstance(class_colors, dict):
        for cls_name in SACCADE_CLASS_EDITABLE:
            col = class_colors.get(cls_name)
            if isinstance(col, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", col):
                put(f"global_saccade_class_color_{cls_name}", col)
    # VIZ-31: the reading-class filter. Unknown names are dropped rather than
    # rejecting the whole config — a class this build no longer classifies would
    # crash the multiselect, and silently widening the filter is the safe way to
    # be wrong (it shows more saccades, never fewer than the file asked for).
    saccade_classes = coloring.get("saccade_classes")
    if isinstance(saccade_classes, list):
        kept = [cls for cls in SACCADE_CLASS_ORDER if cls in set(saccade_classes)]
        if kept:
            put("global_saccade_classes", kept)
    # VIZ-15 marker shape · VIZ-17 uniform fixation colour.
    symbol = coloring.get("fixation_symbol")
    if symbol is not None:
        put_valid(
            symbol in FIXATION_SYMBOLS,
            "global_fixation_symbol",
            symbol,
            "fixation marker shape",
        )
    fix_color = coloring.get("fixation_color")
    if isinstance(fix_color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", fix_color):
        put("global_fixation_color", fix_color)
    if "hollow_fixations" in coloring:
        put("global_hollow_fixations", bool(coloring["hollow_fixations"]))
    if "fixation_opacity" in coloring:
        put_float(
            coloring["fixation_opacity"],
            "global_fixation_opacity",
            0.1,
            1.0,
            "fixation opacity",
        )
    if "stimulus_image_opacity" in coloring:  # VIZ-4
        put_float(
            coloring["stimulus_image_opacity"],
            "global_stimulus_image_opacity",
            0.1,
            1.0,
            "stimulus image opacity",
        )
    # VIZ-4: manual image alignment (origin nudge + size scale).
    if "stimulus_image_offset_x" in coloring:
        put_float(
            coloring["stimulus_image_offset_x"],
            "global_stimulus_image_offset_x",
            -5000.0,
            5000.0,
            "stimulus image X offset",
        )
    if "stimulus_image_offset_y" in coloring:
        put_float(
            coloring["stimulus_image_offset_y"],
            "global_stimulus_image_offset_y",
            -5000.0,
            5000.0,
            "stimulus image Y offset",
        )
    if "stimulus_image_scale" in coloring:
        put_float(
            coloring["stimulus_image_scale"],
            "global_stimulus_image_scale",
            0.25,
            3.0,
            "stimulus image scale",
        )
    co = coloring.get("colorbar_orientation")
    if co is not None:
        put_valid(
            co in ("Vertical", "Horizontal"),
            "global_colorbar_orientation",
            co,
            "color bar orientation",
        )
    if "colorbar_tickangle" in coloring:
        put_int(
            coloring["colorbar_tickangle"],
            "global_colorbar_tickangle",
            -90,
            90,
            "color bar tick angle",
        )
    if "colorbar_tickfont_size" in coloring:
        put_int(
            coloring["colorbar_tickfont_size"],
            "global_colorbar_tickfont_size",
            6,
            20,
            "color bar tick size",
        )
    # Range sliders only render when colour bars are on; store them anyway —
    # the widgets clamp to the current data via `controls._clamp_range`.
    for cfg_key, state_key, label in (
        ("fixation_range", "global_fixation_color_range", "fixation color range"),
        ("heatmap_range", "global_heatmap_color_range", "heatmap color range"),
    ):
        rng = coloring.get(cfg_key)
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            lo, hi = number(rng[0]), number(rng[1])
            put_valid(lo is not None and hi is not None, state_key, (lo, hi), label)

    sizing = section("sizing")
    marker = sizing.get("marker_size_range")
    if isinstance(marker, (list, tuple)) and len(marker) == 2:
        lo, hi = number(marker[0]), number(marker[1])
        if lo is None or hi is None:
            skipped.append("marker size range")
        else:
            lo = max(_MARKER_BOUNDS[0], min(int(lo), _MARKER_BOUNDS[1]))
            hi = max(_MARKER_BOUNDS[0], min(int(hi), _MARKER_BOUNDS[1]))
            put("global_marker_size_range", (min(lo, hi), max(lo, hi)))
    if "order_font_size" in sizing:
        put_int(
            sizing["order_font_size"],
            "global_order_font_size",
            *_FONT_BOUNDS,
            "order label size",
        )
    color = sizing.get("order_font_color")
    if isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        put("global_order_font_color", color)
    if "base_font_size" in sizing:
        put_int(
            sizing["base_font_size"],
            "global_base_font_size",
            *_FONT_BOUNDS,
            "figure font size",
        )

    # VIZ-11 follow-up: the animation frame grid.
    animation = section("animation")
    if "grid_step_ms" in animation:
        put_int(
            animation["grid_step_ms"],
            "global_anim_grid_step_ms",
            20,
            500,
            "animation frame step",
        )
    if "max_frames" in animation:
        put_int(
            animation["max_frames"],
            "global_anim_max_frames",
            30,
            2000,
            "animation frame cap",
        )

    canvas = section("canvas_px")
    if "width" in canvas:
        put_int(canvas["width"], "global_canvas_width", *_CANVAS_BOUNDS, "canvas width")
    if "height" in canvas:
        put_int(
            canvas["height"], "global_canvas_height", *_CANVAS_BOUNDS, "canvas height"
        )

    setup = section("experimental_setup")
    # DATA-2: write all five keys even for a pre-experimental-setup config. This
    # keeps schema-1/2 restores deterministic and makes the saved-state contract
    # explicit (rather than hiding the key names behind a dynamic loop).
    #
    # DATA-22 review: "all five" means all five of *this* section's keys, and
    # only for a full plot config. The wizard's setup file now also carries an
    # `experimental_setup` — a `SetupSnapshot`, which has no `display_dpi` /
    # `stimulus_font_pt` / `use_stimulus_font_pt` — and loading one through the
    # main 💾 Save & restore uploader used to flip this branch on and overwrite
    # those three with the reader's own fallbacks. A section that never mentions
    # a setting must not restate it.
    full_config = isinstance(config.get("canvas_px"), dict)
    setup_context = isinstance(config.get("experimental_setup"), dict) or full_config

    def _stated(key: str) -> bool:
        """Whether this config is entitled to write ``key``'s session state."""
        return full_config or key in setup

    if setup_context:
        monitor_width = number(setup.get("monitor_width_mm", 597.0))
        put_valid(
            monitor_width is not None,
            "global_monitor_width_mm",
            max(100.0, min(float(monitor_width), 3000.0))
            if monitor_width is not None
            else 597.0,
            "monitor width",
        )
        viewing_distance = number(setup.get("viewing_distance_mm", 800.0))
        put_valid(
            viewing_distance is not None,
            "global_viewing_distance_mm",
            max(100.0, min(float(viewing_distance), 3000.0))
            if viewing_distance is not None
            else 800.0,
            "viewing distance",
        )
        if _stated("display_dpi"):
            display_dpi = number(setup.get("display_dpi", 96.0))
            put_valid(
                display_dpi is not None,
                "global_display_dpi",
                max(20.0, min(float(display_dpi), 1000.0))
                if display_dpi is not None
                else 96.0,
                "display DPI",
            )
        if _stated("stimulus_font_pt"):
            stimulus_font = number(setup.get("stimulus_font_pt", 12.0))
            put_valid(
                stimulus_font is not None,
                "global_stimulus_font_pt",
                max(4.0, min(float(stimulus_font), 144.0))
                if stimulus_font is not None
                else 12.0,
                "stimulus font",
            )
        if _stated("use_stimulus_font_pt"):
            put(
                "global_use_stimulus_font_pt",
                bool(setup.get("use_stimulus_font_pt", False)),
            )

    axes = section("axes")
    numeric = numeric_field_options(fixations)
    for cfg_key, state_key, label in (
        ("x_field", "global_x_field", "X axis field"),
        ("y_field", "global_y_field", "Y axis field"),
    ):
        val = axes.get(cfg_key)
        if val is not None:
            put_valid(val in numeric, state_key, val, label)
    if "coordinate_grid" in axes:
        put("global_show_coordinate_grid", bool(axes["coordinate_grid"]))
    if "coordinate_grid_auto" in axes:
        put("global_coordinate_grid_auto", bool(axes["coordinate_grid_auto"]))
    if axes.get("coordinate_grid_spacing") is not None:
        put_float(
            axes["coordinate_grid_spacing"],
            "global_coordinate_grid_spacing",
            10.0,
            5000.0,
            "coordinate grid spacing",
        )

    text = section("text")
    if "scale_text_to_boxes" in text:
        put("global_scale_text_to_boxes", bool(text["scale_text_to_boxes"]))
    if "line_spacing" in text:
        n = number(text["line_spacing"])
        if n is None:
            skipped.append("line spacing")
        else:
            put("global_line_spacing", max(1.0, min(float(n), 10.0)))
    if isinstance(text.get("font_family"), str) and text["font_family"].strip():
        put("global_font_family", text["font_family"])
    tc = text.get("text_color")
    if isinstance(tc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", tc):
        put("global_text_color", tc)
    word_hover_fields = text.get(
        "word_hover_fields",
        ["text", "word_id", "line_idx", "total_fixation_duration_ms"]
        if isinstance(config.get("text"), dict)
        else None,
    )
    if isinstance(word_hover_fields, list) and all(
        isinstance(field, str) for field in word_hover_fields
    ):
        put("global_word_hover_fields", word_hover_fields)
    fixation_hover_fields = text.get(
        "fixation_hover_fields",
        ["order_in_trial", "duration_ms", "word_id"]
        if isinstance(config.get("text"), dict)
        else None,
    )
    if isinstance(fixation_hover_fields, list) and all(
        isinstance(field, str) for field in fixation_hover_fields
    ):
        put("global_fixation_hover_fields", fixation_hover_fields)

    # EXP-5: title/caption on the figure, moved here from being Export-only.
    labels = section("labels")
    if "show_title_caption" in labels:
        put("global_show_title_caption", bool(labels["show_title_caption"]))
    if isinstance(labels.get("title_pattern"), str):
        put("global_title_pattern", labels["title_pattern"])
    if isinstance(labels.get("caption_pattern"), str):
        put("global_caption_pattern", labels["caption_pattern"])
    elif "labels" not in config and has_valid_plot_section:
        # Pre-EXP-5 configs have no labels block; pin the off defaults so the
        # frozen state-key set is still fully written.
        put("global_show_title_caption", False)
        put("global_title_pattern", "")
        put("global_caption_pattern", "")

    highlighting = section("highlighting")
    if "critical_span_style" in highlighting:
        css = highlighting["critical_span_style"]
        put_valid(
            css in ("Mark text", "Mark border", "None"),
            "global_critical_span_style",
            css,
            "text highlighting",
        )
    if (
        isinstance(highlighting.get("highlight_column"), str)
        and highlighting["highlight_column"]
    ):
        # The rail's `_drop_stale` clears this if it isn't a column in the
        # restored-onto data, so it needs no validation against words here.
        put("global_highlight_column", highlighting["highlight_column"])
    # Fixation classification (PRE-2): short/long/out-of-bounds highlight or discard.
    flags = highlighting.get("fixation_flags")
    if isinstance(flags, dict):
        for cat in ("short", "long", "oob"):
            spec = flags.get(cat)
            if not isinstance(spec, dict):
                continue
            mode = spec.get("mode")
            if mode in _FIXCLASS_MODES:
                put(f"global_fixclass_{cat}_mode", mode)
            if cat != "oob" and spec.get("threshold_ms") is not None:
                try:
                    put(
                        f"global_fixclass_{cat}_threshold_ms",
                        int(float(spec["threshold_ms"])),
                    )
                except (TypeError, ValueError):
                    pass
            sym = spec.get("symbol")
            if sym in _OUT_OF_TEXT_MARKERS:
                put(f"global_fixclass_{cat}_symbol", sym)
            col = spec.get("color")
            if isinstance(col, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", col):
                put(f"global_fixclass_{cat}_color", col)
    htc = highlighting.get("highlight_text_color")
    if isinstance(htc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", htc):
        put("global_highlight_text_color", htc)
    bg = highlighting.get("background_color")
    if isinstance(bg, str) and bg:
        # Map a saved colour back to a preset name, else fall to the custom slot.
        preset = next(
            (n for n, v in BACKGROUND_PRESETS.items() if str(v).lower() == bg.lower()),
            None,
        )
        if preset is not None:
            put("global_bg_choice", preset)
        else:
            put("global_bg_choice", "Custom…")
            put("global_bg_custom", bg)
    sbc = highlighting.get("span_border_color")
    if isinstance(sbc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", sbc):
        put("global_span_border_color", sbc)

    # CMP-11 — the compare *view* (layout + whose stimulus an overlay draws).
    # Validated against the segmented controls' exact options for the same
    # reason the URL params are: seeding a value outside them makes the widget
    # raise. An absent section keeps the seeded defaults, so a pre-CMP-11 config
    # restores unchanged and no schema bump is needed.
    compare_view = config.get("compare_view")
    if isinstance(compare_view, dict):
        for field, options, label in (
            ("layout", _COMPARE_LAYOUT_OPTIONS, "compare layout"),
            ("stimulus", _COMPARE_STIMULUS_OPTIONS, "compare stimulus source"),
        ):
            if field not in compare_view:
                continue
            try:
                value = _parse_choice(compare_view[field], options, label)
            except ValueError:
                skipped.append(label)
                continue
            put(f"single_compare_{field}", value)

    # Per-scanpath comparison styling (cmp{idx}_*). A short or hand-edited list
    # degrades gracefully — a missing field just keeps the seeded default.
    compare = config.get("compare")
    if isinstance(compare, list):
        for idx, entry in enumerate(compare[:2]):
            if not isinstance(entry, dict):
                continue
            fc = entry.get("fix_color")
            if isinstance(fc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", fc):
                put(f"cmp{idx}_fix_color", fc)
            sc = entry.get("saccade_color")
            if isinstance(sc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", sc):
                put(f"cmp{idx}_saccade_color", sc)
            if "saccade_style" in entry:
                put_valid(
                    entry["saccade_style"] in SACCADE_DASH_OPTIONS,
                    f"cmp{idx}_saccade_style",
                    entry["saccade_style"],
                    f"scanpath {idx + 1} line style",
                )
            if "saccade_width" in entry:
                put_float(
                    entry["saccade_width"],
                    f"cmp{idx}_saccade_width",
                    SACCADE_WIDTH_BOUNDS[0],
                    SACCADE_WIDTH_BOUNDS[1],
                    f"scanpath {idx + 1} line width",
                )
            rng = entry.get("marker_size_range")
            if isinstance(rng, (list, tuple)) and len(rng) == 2:
                lo, hi = number(rng[0]), number(rng[1])
                if lo is None or hi is None:
                    skipped.append(f"scanpath {idx + 1} marker size")
                else:
                    lo = max(_MARKER_BOUNDS[0], min(int(lo), _MARKER_BOUNDS[1]))
                    hi = max(_MARKER_BOUNDS[0], min(int(hi), _MARKER_BOUNDS[1]))
                    put(f"cmp{idx}_marker_size_range", (min(lo, hi), max(lo, hi)))
            if "hollow" in entry:
                put(f"cmp{idx}_hollow", bool(entry["hollow"]))
            if "opacity" in entry:
                put_float(
                    entry["opacity"],
                    f"cmp{idx}_opacity",
                    0.1,
                    1.0,
                    f"scanpath {idx + 1} opacity",
                )
            # UX-31: the A/B legend label override.
            if isinstance(entry.get("label_pattern"), str):
                put(f"cmp{idx}_label_pattern", entry["label_pattern"])

    selection = section("selection")
    if selection:
        if _restore_selection(selection, combos):
            restore.applied += 1
        else:
            skipped.append("trial selection")

    # Annotations travel with schema-2 configs (Save & restore). Only restore
    # when the key is present, so a plot-config-only file never clears them.
    if "annotations" in config and isinstance(config["annotations"], list):
        n_anno = restore_records(config["annotations"])
        restore.applied += 1
        st.toast(f"Restored {n_anno} annotation(s) from config.", icon="📝")

    # DATA-20 — the participant table, restored *before* the filter widgets read
    # their keys, so a saved `filter_meta_*` selection lands on fields that
    # already exist. Absent key = leave whatever is attached alone, the same
    # rule the annotations above follow.
    payload = config.get("participant_metadata")
    if isinstance(payload, dict):
        from scanpath_studio import metadata as _metadata

        attached = _metadata.from_payload(payload)
        if attached is not None:
            st.session_state[_metadata.SESSION_KEY] = attached
            st.session_state[_metadata.RAW_SESSION_KEY] = attached.frame
            restore.applied += 1
            st.toast(
                f"Restored participant metadata ({len(attached.fields)} field(s)).",
                icon="👤",
            )

    # DATA-29 — the trial table, same contract and the same ordering reason.
    trial_payload = config.get("trial_metadata")
    if isinstance(trial_payload, dict):
        from scanpath_studio import metadata as _metadata

        attached_trials = _metadata.trial_from_payload(trial_payload)
        if attached_trials is not None:
            st.session_state[_metadata.TRIAL_SESSION_KEY] = attached_trials
            st.session_state[_metadata.TRIAL_RAW_SESSION_KEY] = attached_trials.frame
            restore.applied += 1
            st.toast(
                f"Restored trial metadata ({len(attached_trials.fields)} field(s)).",
                icon="🗂️",
            )

    # The text table, third grain, same contract and ordering reason.
    text_payload = config.get("text_metadata")
    if isinstance(text_payload, dict):
        from scanpath_studio import metadata as _metadata

        attached_texts = _metadata.text_from_payload(text_payload)
        if attached_texts is not None:
            st.session_state[_metadata.TEXT_SESSION_KEY] = attached_texts
            st.session_state[_metadata.TEXT_RAW_SESSION_KEY] = attached_texts.frame
            restore.applied += 1
            st.toast(
                f"Restored text metadata ({len(attached_texts.fields)} field(s)).",
                icon="📄",
            )

    # VIZ-39 — the saved-design library. Restored wholesale rather than merged:
    # a config describes one session's designs, and silently blending two
    # libraries would leave the user unable to say which file a design came
    # from. Absent key = leave whatever is there, the same rule as above.
    designs = config.get("design_presets")
    if isinstance(designs, dict):
        from scanpath_studio.controls import DESIGN_PRESETS_KEY

        clean = {
            str(name): dict(values)
            for name, values in designs.items()
            if isinstance(values, dict)
        }
        if clean:
            st.session_state[DESIGN_PRESETS_KEY] = clean
            restore.applied += 1
            st.toast(f"Restored {len(clean)} saved design(s).", icon="🎨")

    return restore.applied, skipped


def _apply_uploaded_plot_config(combos: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """Restore settings from a freshly uploaded plot-config JSON, once per file.

    Reads the file captured by the 💾 Session dialog's ``plot_config_upload``
    uploader (persisted in session_state across reruns) and writes the saved
    settings into session_state *before* the widgets render — the same mechanism
    as ``_apply_url_preset``. Deduped by ``(name, size)`` so manual tweaks made
    after a restore aren't clobbered on every rerun. Call right after the trial
    combos are built, before the canvas/visualization controls."""
    uploaded = st.session_state.get("plot_config_upload")
    if uploaded is None:
        return
    signature = (uploaded.name, uploaded.size)
    if st.session_state.get("_plot_config_last_import") == signature:
        return
    # Stamp the signature up front so a malformed file isn't retried every rerun.
    st.session_state["_plot_config_last_import"] = signature
    st.session_state.pop("_plot_config_skipped", None)
    try:
        config = json.loads(uploaded.getvalue().decode("utf-8"))
        if not isinstance(config, dict):
            raise ValueError("expected a JSON object")
    except (ValueError, UnicodeDecodeError) as exc:
        st.toast(f"Couldn't read plot config: {exc}", icon="⚠️")
        return
    try:
        applied, skipped = _restore_plot_config(config, combos, fixations)
    except Exception as exc:  # backstop for an unexpectedly shaped config
        st.toast(f"Couldn't apply plot config: {exc}", icon="⚠️")
        return
    st.session_state["_plot_config_skipped"] = skipped
    if applied:
        st.toast(f"Restored {applied} setting(s) from plot config.", icon="✅")
    elif not skipped:
        st.toast("Plot config had no recognized settings.", icon="⚠️")


def _build_share_query(
    data_choice: str,
    *,
    include_participant: bool = True,
    include_trial: bool = True,
) -> tuple[str, list]:
    """Build the deep-link query string that reproduces the current view.

    Reads the resolved trial selection and visualization settings back out of
    ``st.session_state`` and encodes them with the same URL schema
    ``_apply_url_preset`` / ``_apply_url_trial_selection`` parse, so opening the
    link reopens the app on this trial with these settings.

    ``include_participant`` / ``include_trial`` (S3) let the caller leave the
    identifying half out of the link — a URL lands in browser history, proxy
    logs, ``Referer`` headers and chat previews, so naming a participant there
    is opt-out-able. Dropping only the participant still lands on the exact
    trial: ``_restore_selection`` falls through to a trial-id-alone match. The
    view settings are unaffected either way.

    Returns ``(query_string, caveats)`` — ``caveats`` holds human-readable notes
    when the link can't fully reproduce the view (e.g. an uploaded data source
    a URL can't rebuild). The query string is URL-encoded and has no leading
    ``?``; the copy widget composes it onto the live origin client-side.
    """

    params: dict[str, str] = {}
    caveats: list = []

    source = _SHAREABLE_SOURCES.get(data_choice)
    # DATA-27 (Task 12): which public corpus this is, if any. Resolved only when
    # the choice isn't already a token of its own, so the ordinary sources never
    # pay for a registry lookup. `corpus_label` is the *registry label*, which is
    # what the picker collapsed away — see `_selected_corpus`.
    corpus_label, corpus_spec = ("", {}) if source else _selected_corpus(data_choice)
    if corpus_label and not source:
        # A corpus reachable by both tokens keeps emitting the older one:
        # `onestop_public` (with its variant / regime / parts) has been in links
        # since DATA-3, and those links must keep resolving unchanged. The new
        # generic token is additive, never a replacement.
        source = _SHAREABLE_SOURCES.get(corpus_label)
    # Read through `registry_corpus_slugs`, not `corpus_slug` directly, so a slug
    # another entry would also answer to is never emitted: the reader refuses it,
    # and a link the recipient cannot resolve is worse than no link at all.
    corpus_slug_out = (
        registry_corpus_slugs().get(corpus_label, "")
        if corpus_label and not source
        else ""
    )
    if source:
        params["source"] = source
    elif corpus_slug_out:
        params["source"] = CORPUS_SOURCE_TOKEN
        params[PARAM_CORPUS] = corpus_slug_out
        # Sharing "you'd need this corpus" beats sharing nothing, which is what a
        # public corpus got before this. The recipient's bundle is theirs — and
        # is the one thing a link can't carry — so the caveat names the corpus
        # and says what to do about it rather than the link quietly not working.
        if prepared := str(corpus_spec.get("benchmark_dataset") or ""):
            caveats.append(
                f"**{prepared}** is a locally prepared corpus. The link names it, "
                "but the data can't travel in a URL: the recipient needs their "
                "own harmonised bundle holding that corpus, with the app's "
                "benchmark data directory pointed at it. Everything else in the "
                "link still applies."
            )
    else:
        # A link carries settings, never files — so for a dataset the user added
        # there is nothing a URL could do that would save the recipient the
        # upload. What it *can* do is name the route that saves them the
        # re-mapping, which is a real second half of "load the same data": the
        # column mapping and recording setup are exportable as JSON from the
        # add-dataset screen's ⬇️ Save setup, and re-applied from that screen's
        # *Restore a saved setup*. The caveat used to stop at "load the same
        # data" and leave the mapping to be redone by hand.
        caveats.append(
            "This data source can't be rebuilt from a link — the recipient will "
            "need to load the same files themselves. Send them the dataset's "
            "**⬇️ Save setup** JSON (on the ➕ Add dataset screen, beside "
            "✅ Add dataset) along with the files: it carries the column mapping "
            "and recording setup, and they re-apply it from *Restore a saved "
            "setup* on that same screen. The view settings below travel in the "
            "link itself."
        )

    # DATA-3: the public OneStop source carries its variant / regime / parts so a
    # shared link reopens the same corpus slice. The recipient still needs the
    # reports present (or downloadable) — the source caveat above covers that.
    # Matched against the resolved corpus too, since the picker hands this
    # function the collapsed `PUBLIC_DATASETS_CHOICE` for every public corpus.
    if ONESTOP_PUBLIC_CHOICE in (data_choice, corpus_label):
        variant = st.session_state.get("onestop_variant")
        if variant in ONESTOP_VARIANT_LABELS:
            params["onestop_variant"] = str(variant)
        regime = st.session_state.get("onestop_regime")
        if regime in ONESTOP_REGIME_LABELS:
            params["onestop_regime"] = str(regime)
        parts = st.session_state.get("onestop_parts")
        if isinstance(parts, (list, tuple)):
            valid = [p for p in parts if p in ONESTOP_PART_LABELS]
            if valid:
                params["onestop_parts"] = ",".join(valid)

    if data_choice == AUTHOR_CHOICE:
        params["author_text"] = str(st.session_state.get("author_text", ""))
        events = st.session_state.get("_authored_events_frame")
        if isinstance(events, pd.DataFrame):
            params["author_events"] = json.dumps(
                events.to_dict("records"), separators=(",", ":")
            )

    selection = st.session_state.get("_share_selection") or {}
    participant = selection.get("participant_id")
    trial_id = selection.get("trial_id")
    screen_id = selection.get("screen_id")
    if include_participant and participant not in (None, ""):
        params["participant"] = str(participant)
    if include_trial and trial_id not in (None, ""):
        params["trial_id"] = str(trial_id)
    if include_trial and screen_id not in (None, ""):
        params["screen"] = str(screen_id)

    # CMP-8 §7: the second scanpath. Gated on `include_trial` for the same reason
    # A's trial is — lower-level callers may omit identity from a URL even though
    # the app's Share panel always includes it. B's source rides along only when it is one a URL
    # can rebuild; an uploaded dataset lives in session state, so the link says so
    # rather than silently dropping half the comparison.
    compare = selection.get("compare") if include_trial else None
    if isinstance(compare, dict) and compare.get("trial_id") not in (None, ""):
        participant_b = compare.get("participant_id")
        if include_participant and participant_b not in (None, ""):
            params[COMPARE_PARAM] = f"{participant_b}:{compare['trial_id']}"
        else:
            # `compare=` has no trial-only spelling — it is `<pid>:<trial>`, and
            # a trial id alone is ambiguous across readers in B's corpus. Under
            # a programmatic link that drops participants, the comparison therefore
            # cannot travel, and the link must say so rather than arrive as a
            # single scanpath the recipient has no way to know was a pair.
            caveats.append(
                "The compared scanpath names a second reader, so it isn't "
                "included at this privacy setting — the link opens the first "
                "scanpath only."
            )
        source_b = compare.get("source")
        if source_b:
            token = _SHAREABLE_SOURCES.get(source_b)
            if token and COMPARE_PARAM in params:
                params[COMPARE_SOURCE_PARAM] = token
            elif COMPARE_PARAM in params:
                params.pop(COMPARE_PARAM)
                caveats.append(
                    f"The compared scanpath comes from **{source_b}**, which "
                    "can't be rebuilt from a link — it isn't included."
                )

    # Visualization toggles — emit an explicit 0/1 so a layer the user turned
    # *off* is shared as off (the URL coercion reads "0" as False).
    for url_key, state_key in _SHARE_TOGGLE_PARAMS.items():
        if url_key in _GATED_URL_PARAMS and not _GATED_URL_PARAMS[url_key]():
            continue  # PRE-21
        if state_key in st.session_state:
            params[url_key] = "1" if st.session_state[state_key] else "0"
    # Strings / choices / colours / numbers — emit only when set.
    for url_key, state_key in {**_SHARE_VALUE_PARAMS, **_SHARE_INT_PARAMS}.items():
        if url_key in _GATED_URL_PARAMS and not _GATED_URL_PARAMS[url_key]():
            continue  # PRE-21: don't put a gated setting on a link.
        value = st.session_state.get(state_key)
        if value not in (None, ""):
            params[url_key] = (
                ",".join(str(item) for item in value)
                if isinstance(value, (list, tuple))
                else str(value)
            )
    for url_key, state_key in _SHARE_FLOAT_PARAMS.items():
        value = st.session_state.get(state_key)
        if value is not None:
            params[url_key] = str(value)
    # Two-element ranges → "lo,hi".
    for url_key, state_key in {
        **_SHARE_INT_RANGE_PARAMS,
        **_SHARE_FLOAT_RANGE_PARAMS,
    }.items():
        value = st.session_state.get(state_key)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            params[url_key] = f"{value[0]},{value[1]}"
    # CMP-11: the two compare-view params describe a comparison, so they only
    # travel when one does. Both widgets carry `persist_state="session"`, so the
    # generic value sweep above would otherwise stamp `cmp_layout`/`cmp_stimulus`
    # onto every later link — including ones where `compare=` was deliberately
    # withheld by the identity picker or dropped because B's corpus can't be
    # rebuilt. They restore nothing on their own.
    if COMPARE_PARAM not in params:
        params.pop(COMPARE_LAYOUT_PARAM, None)
        params.pop(COMPARE_STIMULUS_PARAM, None)
    # VIZ-40 — VIZ-7's fixation window travels only when it *is* a window, for
    # the same shape of reason as the two compare params above: `single_fix_range`
    # is set to the trial's own full range the moment the slider renders (and
    # re-expanded on every trial change), so the generic range sweep would stamp
    # `fix_range` on every link ever copied. Two things have to hold.
    #
    # `single_fix_range_user_set` is the slider's own record of a deliberate
    # drag — the same flag that stops an untouched window following the user from
    # trial to trial — so an auto-default never ships.
    #
    # And the window must differ from the trial's full range, which
    # `tabs.render_single_trial_tab` publishes as `full_fix_range`: dragging the
    # handles back out to both ends restores nothing, and a recipient whose copy
    # of the trial is longer would have it silently truncated to the sender's
    # length. When the trial has no `order_in_trial` there is no full range to
    # compare against, and the `user_set` flag alone decides.
    #
    # It is also gated on `include_trial`, exactly as `trial_id`, `screen` and
    # `compare` above are: an index window means nothing without the trial it
    # indexes into. On a link that withholds trial identity the recipient lands
    # on an arbitrary trial, and the slider clamps the window to *that* trial's
    # length — so a 509–540 window arriving at a 30-fixation trial silently
    # collapses to a single fixation. Only headless callers can reach this (the
    # UI has no identity-mode picker), which is what makes it worth stating.
    window = st.session_state.get("single_fix_range")
    if not include_trial or not st.session_state.get("single_fix_range_user_set"):
        params.pop(FIX_RANGE_PARAM, None)
    elif isinstance(window, (list, tuple)) and len(window) == 2:
        full = (st.session_state.get("_share_selection") or {}).get("full_fix_range")
        if full is not None and tuple(int(v) for v in window) == tuple(
            int(v) for v in full
        ):
            params.pop(FIX_RANGE_PARAM, None)
    if st.session_state.get("single_animate"):
        params["tab"] = "animation"

    # DATA-22 §7 surface 2: a compact provenance badge for the recording setup.
    # A link carries the *values* (canvas, mm, font) already; without this the
    # recipient cannot tell a monitor the sender measured from one the app
    # assumed on their behalf. Metadata about settings, not a setting — it takes
    # no input and changes no figure, which is why it stops here and never
    # becomes a `render` flag or a builder argument.
    from scanpath_studio.app import active_setup_snapshot

    snapshot = active_setup_snapshot(data_choice)
    if snapshot is not None:
        params[SETUP_PROVENANCE_PARAM] = format_provenance_param(snapshot)

    return urlencode(params), caveats


def _render_share_link_widget(query: str) -> None:
    """Render the current share link and its single Refresh & Copy action.

    A same-origin ``st.iframe`` embed (same trick as the tour — see
    ``tour.render_spotlight_tour``) composes the full URL from the *live* address:
    ``window.parent.location.origin + pathname`` + the query string built
    server-side. Doing the origin/path join client-side means the link is correct
    wherever the app is served (localhost, Streamlit Cloud, a reverse proxy)
    without the server having to know its own public URL. Copy uses the async
    Clipboard API with a ``document.execCommand`` fallback for insecure contexts.
    """
    payload = json.dumps(query)
    embed_html_iframe(
        f"""
        <div class="sps-share">
          <div class="sps-share-row">
            <input id="sps-share-url" type="text" readonly
                   aria-label="Shareable link" />
            <button id="sps-share-action" type="button">Refresh &amp; Copy</button>
          </div>
          <div id="sps-share-status" class="sps-share-status"></div>
        </div>
        <style>
          .sps-share {{
            font-family: "Source Sans Pro", system-ui, sans-serif;
            color-scheme: light dark;
          }}
          .sps-share-row {{ display: flex; gap: 0.4rem; align-items: stretch; }}
          #sps-share-url {{
            flex: 1 1 auto; min-width: 0; padding: 0.45rem 0.6rem;
            border: 1px solid rgba(128, 128, 128, 0.5); border-radius: 8px;
            background: rgba(128, 128, 128, 0.08); color: inherit;
            font-size: 0.85rem; font-family: ui-monospace, monospace;
          }}
          #sps-share-action {{
            flex: 0 0 auto; padding: 0.45rem 0.9rem; cursor: pointer;
            border: 1px solid #1f77b4; border-radius: 8px; white-space: nowrap;
            background: #1f77b4; color: #fff; font-weight: 600; font-size: 0.85rem;
          }}
          #sps-share-action:hover {{ background: #185fa5; }}
          .sps-share-status {{
            min-height: 1.1rem; margin-top: 0.35rem; font-size: 0.8rem;
            color: #2e7d32; font-weight: 600;
          }}
        </style>
        <script>
        (function () {{
          const query = {payload};
          const loc = window.parent.location;
          const base = loc.origin + loc.pathname;
          const url = query ? base + "?" + query : base;
          const input = document.getElementById("sps-share-url");
          const status = document.getElementById("sps-share-status");
          const btn = document.getElementById("sps-share-action");
          input.value = url;
          input.addEventListener("focus", function () {{ input.select(); }});
          function flash(msg) {{
            status.textContent = msg;
            setTimeout(function () {{ status.textContent = ""; }}, 2500);
          }}
          async function copy() {{
            try {{
              await navigator.clipboard.writeText(url);
              flash("✓ Link copied to clipboard");
            }} catch (err) {{
              input.focus();
              input.select();
              try {{
                document.execCommand("copy");
                flash("✓ Link copied to clipboard");
              }} catch (err2) {{
                flash("Press ⌘/Ctrl-C to copy the selected link");
              }}
            }}
          }}
          btn.addEventListener("click", copy);
        }})();
        </script>
        """,
        # One control row plus the transient copy-status line. The previous
        # 110 px frame reserved a visibly empty block before the note below.
        height=76,
    )


# -----------------------------------------------------------------------------
# EXP-7 — the API / CLI code that reproduces the figure on screen
# -----------------------------------------------------------------------------
#: The Share subtab's two snippet controls. UI-only, exactly like
#: `share_identity_mode`: they govern how the *recipe* is written, not what the
#: figure is, so neither belongs on the wire — a deep link carrying "show me the
#: CLI form" would be describing the reader's pane, not the view. If either is
#: ever persisted into a saved config it has to join
#: `session_keys.PLOT_CONFIG_STATE_KEYS` first.
SNIPPET_FLAVOR_KEY = "snippet_flavor"
SNIPPET_EXPLICIT_KEY = "snippet_explicit"

_SNIPPET_FLAVORS = ("🐍 Python", "⌨️ CLI")

#: Output filename the snippet saves to, per figure kind. An animation is
#: interactive HTML; the static and comparison figures raster.
_SNIPPET_OUTPUT = {
    "static": "scanpath.png",
    "comparison": "comparison.png",
    "animation": "scanpath.html",
}


def _snippet_source(data_choice: str) -> SnippetSource:
    """Describe the loaded data the way a script would have to load it.

    Dispatches on the registry entry's **stable identifier** (`short` for a
    built-in, `benchmark_dataset` for a prepared corpus), not the display label
    — the same rule `corpus_slug` follows for the share link, and for the same
    reason: the label is copy and can be reworded.

    A corpus root is a *local path*, which is why it is emitted only when the
    path box is the user's own (S2 `local_filesystem_enabled`). On a shared
    deployment the location comes from the server's configuration and the user
    never sees it, so quoting it back in a copyable snippet would hand every
    visitor the server's layout. There the snippet carries a placeholder.
    """
    from scanpath_studio.app import local_filesystem_enabled

    def root(key: str, placeholder: str) -> str:
        if not local_filesystem_enabled():
            return placeholder
        return str(st.session_state.get(key) or placeholder)

    if data_choice == DEMO_CHOICE:
        return SnippetSource(kind=SOURCE_DEMO, label=DEMO_CHOICE)
    if data_choice == SYNTHETIC_CHOICE:
        return SnippetSource(kind=SOURCE_SYNTHETIC, label=SYNTHETIC_CHOICE)
    if data_choice == AUTHOR_CHOICE:
        return SnippetSource(
            kind=SOURCE_AUTHOR,
            label=AUTHOR_CHOICE,
            options={"path": "scanpath.json"},
            note=(
                "An authored scanpath lives in this session — export it from "
                "the ✍️ authoring panel first, then point the snippet at that "
                "JSON file."
            ),
        )

    corpus_label, spec = _selected_corpus(data_choice)
    if spec.get("benchmark_dataset"):
        return SnippetSource(
            kind=SOURCE_BENCHMARK,
            label=corpus_label,
            options={
                "root": root("eyegenbench_dir", "data/eyegenbench"),
                "dataset": str(spec["benchmark_dataset"]),
            },
        )
    short = str(spec.get("short") or "")
    if short == "PoTeC":
        return SnippetSource(
            kind=SOURCE_POTEC,
            label=corpus_label,
            options={"root": root("potec_dir", "data/PoTeC")},
        )
    if short == "MultiplEYE":
        fixation_source = str(
            st.session_state.get("multipleye_fixation_source") or "scanpaths"
        )
        return SnippetSource(
            kind=SOURCE_MULTIPLEYE,
            label=corpus_label,
            options={
                "root": root("multipleye_dir", "data/MultiplEYE"),
                "fixation_source": fixation_source,
            },
            # `render --source multipleye` has no fixation-source flag, so the
            # non-default reading of the corpus can only be said in Python.
            cli_unsupported=(
                () if fixation_source == "scanpaths" else ("fixation_source",)
            ),
        )
    if short == "OneStop" or data_choice in (ONESTOP_CHOICE, ONESTOP_PUBLIC_CHOICE):
        variant = str(st.session_state.get("onestop_variant") or "public")
        note = ""
        if data_choice == ONESTOP_CHOICE:
            # The 🗄️ server bundle is the lab export by definition; it has no
            # variant picker of its own. It is also read through a *different*
            # loader from the public one — `data.load_onestop_server_bundle`,
            # which takes the per-pid shards or the CSV.zip exports under
            # `$ONESTOP_DATA_DIR`. `load_onestop` is the public API's nearest
            # twin but reads the regime/part report layout, so the difference is
            # stated rather than papered over: a snippet that silently pointed
            # the wrong loader at the right folder would fail on the user's
            # machine with nothing to explain it.
            variant = "lacclab"
            note = (
                "The app read this through its **server-bundle** path "
                "(`$ONESTOP_DATA_DIR`, per-participant shards or the CSV.zip "
                "exports). The snippet uses the public `load_onestop` loader, "
                "which expects the regime/part report layout in that same "
                "folder — point it at your reports if the two differ."
            )
        parts = st.session_state.get("onestop_parts")
        return SnippetSource(
            kind=SOURCE_ONESTOP,
            label=corpus_label or data_choice,
            options={
                "root": root(f"onestop_{variant}_dir", "data/OneStop"),
                "regime": str(st.session_state.get("onestop_regime") or "ordinary"),
                "variant": variant,
                "parts": list(parts) if parts else ["Paragraph"],
            },
            note=note,
        )
    if data_choice == MULTIPLEYE_BUNDLE_CHOICE:
        # Unlike OneStop's, this bundle loader *is* `multipleye_raw_frames` over
        # the configured root — the same call `load_multipleye` makes — so the
        # snippet reproduces it exactly and needs no caveat.
        return SnippetSource(
            kind=SOURCE_MULTIPLEYE,
            label=MULTIPLEYE_BUNDLE_CHOICE,
            options={"root": root("multipleye_dir", "data/MultiplEYE")},
        )
    return SnippetSource(
        kind=SOURCE_UNKNOWN,
        label=data_choice,
        note=UNKNOWN_SOURCE_NOTE,
    )


def _render_code_snippet_body(data_choice: str) -> None:
    """Render the **reproduce this figure in code** block of the Share subtab.

    The figure state comes from `tabs._publish_snippet_state`, written on the
    run that drew the figure — so what is quoted here is the plot's own input,
    not a second reading of the widgets. Nothing is rendered when no scanpath
    has been drawn this session (the Corpus view can reach this panel).
    """
    state = st.session_state.get(SNIPPET_STATE_KEY)
    if not isinstance(state, FigureState):
        st.caption(
            "Open a trial on the 🗺️ Scanpath view and the code that rebuilds "
            "its figure appears here."
        )
        return

    st.markdown(
        "**Reproduce this figure in code** — paste it into a notebook or a "
        "terminal to rebuild exactly this plot, headlessly."
    )
    flavor_col, explicit_col = st.columns([2, 3], vertical_alignment="center")
    flavor = flavor_col.segmented_control(
        "Flavour",
        options=_SNIPPET_FLAVORS,
        default=_SNIPPET_FLAVORS[0],
        key=SNIPPET_FLAVOR_KEY,
        label_visibility="collapsed",
    )
    explicit = explicit_col.checkbox(
        "Show every option",
        key=SNIPPET_EXPLICIT_KEY,
        help="By default only the options you changed are written, so the "
        "snippet stays readable. Tick this for the full explicit form — every "
        "figure option at its current value.",
    )
    code = reproduction_code(
        _snippet_source(data_choice),
        state,
        explicit=bool(explicit),
        output=_SNIPPET_OUTPUT.get(state.kind, "scanpath.png"),
    )
    # Inspectable from AppTest without re-deriving it (same trick as
    # `_share_query_current` above).
    st.session_state["_snippet_code_current"] = code
    for note in code.caveats:
        st.caption("⚠️ " + note)
    if flavor == _SNIPPET_FLAVORS[1]:
        if code.cli_unsupported:
            st.caption(
                "⚠️ `render` has no flag for "
                + ", ".join(f"`{name}`" for name in code.cli_unsupported)
                + " — the 🐍 Python form carries "
                + ("them." if len(code.cli_unsupported) > 1 else "it.")
            )
        st.code(code.cli, language="bash")
    else:
        st.code(code.python, language="python")


def _render_share_body(data_choice: str) -> None:
    """Render the **Share** subtab: a deep link to the current view (data source +
    trial + visualization settings).

    Streamlit reruns after every relevant control change, so the query handed to
    the embedded **Refresh & Copy** button already reflects the current view when
    the user clicks it. The link always carries the selected participant, trial
    and all shareable visualization settings."""
    st.markdown(
        "**Share this view** — a link that reopens Scanpath Studio on the "
        "current trial with your visualization settings."
    )
    query, caveats = _build_share_query(data_choice)
    # Keep the rendered value inspectable in AppTest without duplicating the
    # browser-only URL composition logic.
    st.session_state["_share_query_current"] = (query, caveats)
    for note in caveats:
        st.caption("⚠️ " + note)
    _render_share_link_widget(query)
    st.caption(
        "If the recipient runs Scanpath Studio at a different address or port, "
        "replace the start of the URL before opening it."
    )
    st.divider()
    _render_code_snippet_body(data_choice)


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------
# These *request* a view by writing `main_nav`; `menu.render_nav` reconciles the
# router to it on the next run. They are used as `on_click` callbacks, where
# Streamlit forbids `st.switch_page` — hence the request-then-reconcile split
# rather than navigating directly (`menu.switch_to_view` is the direct form, for
# top-level script code).
def _go_corpus() -> None:
    st.session_state["main_nav"] = _VIEW_CORPUS


def _go_scanpath() -> None:
    st.session_state["main_nav"] = _VIEW_SCANPATH


def _go_data() -> None:
    st.session_state["main_nav"] = _VIEW_DATA


def _active_view() -> str:
    """The active top-level view, normalized to one of the nav's entries.

    Reads the `main_nav` mirror `menu.render_nav` writes from the router's
    selection, so it stays the one answer every caller shares. It may also carry
    a legacy/stale value (e.g. "Data Inspection", the old standalone view, or
    "Session", which UX-100 turned back into a popover — and note that DATA-26's
    page is `_VIEW_DATA`, a different string, so an old cached value does *not*
    silently resolve to it), or a view *requested* for the next run; anything
    unrecognized resolves to the Scanpath page."""
    requested = st.session_state.get("main_nav")
    if requested in (_VIEW_CORPUS, _VIEW_DATA):
        return requested
    return _VIEW_SCANPATH
