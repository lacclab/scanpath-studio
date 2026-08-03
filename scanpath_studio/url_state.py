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
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode

import pandas as pd
import streamlit as st
from scanpath_studio.html_embed import embed_html_iframe

from .annotations import restore_records
from .constants import (
    _VIEW_CORPUS,
    _VIEW_SCANPATH,
    BACKGROUND_PRESETS,
    COLORSCALES,
    DEMO_CHOICE,
    FIXATION_SYMBOLS,
    MULTIPLEYE_BUNDLE_CHOICE,
    CUSTOM_PALETTE,
    ONESTOP_CHOICE,
    ONESTOP_PART_LABELS,
    ONESTOP_PUBLIC_CHOICE,
    ONESTOP_REGIME_LABELS,
    ONESTOP_VARIANT_LABELS,
    PALETTES,
    SACCADE_CLASS_EDITABLE,
    SACCADE_COLOR_MODES,
    SACCADE_DASH_OPTIONS,
    SACCADE_WIDTH_BOUNDS,
    SYNTHETIC_CHOICE,
)
from .controls import (
    _ALIGN_OPTIONS,
    _FIXCLASS_MODES,
    _OUT_OF_TEXT_MARKERS,
    color_field_options,
    numeric_field_options,
    palette_state,
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


# --- Share-link identity (S3) ----------------------------------------------
# A share link that names a participant is participant data in a URL, and URLs
# are logged, cached and pasted into issue trackers. The identifying half is
# therefore opt-out-able at the point of copying. The default keeps both ids
# (a link that reopens one trial has to identify it) and the panel says so;
# "Trial only" leans on `_restore_selection`'s trial-id-alone fallback, so the
# link still lands on the exact trial without naming a reader.
_SHARE_IDENTITY_KEY = "share_identity_mode"
_SHARE_IDENTITY_FULL = "Participant + trial"
_SHARE_IDENTITY_TRIAL = "Trial only"
_SHARE_IDENTITY_NONE = "Settings only"
_SHARE_IDENTITY_MODES = [
    _SHARE_IDENTITY_FULL,
    _SHARE_IDENTITY_TRIAL,
    _SHARE_IDENTITY_NONE,
]


def _share_identity_flags(mode: Optional[str]) -> Tuple[bool, bool]:
    """``mode`` → ``(include_participant, include_trial)`` for the link builder."""
    if mode == _SHARE_IDENTITY_TRIAL:
        return False, True
    if mode == _SHARE_IDENTITY_NONE:
        return False, False
    return True, True


def _share_identity_caution(query: str) -> str:
    """The caption printed under the link, naming the ids it actually carries."""
    params = dict(parse_qsl(query, keep_blank_values=True))
    named = [
        label
        for key, label in (("participant", "participant"), ("trial_id", "trial"))
        if params.get(key)
    ]
    if not named:
        return (
            "🔒 This link carries view settings only — no participant or trial id. "
            "The recipient lands on whichever trial their own session opens."
        )
    return (
        "⚠️ This link names the "
        + " and ".join(named)
        + " in its URL. URLs are kept in browser history, server logs and link "
        "previews — use *Trial only* or *Settings only* above if that matters."
    )


# --- Share-link parameter groups -------------------------------------------
# The Share link round-trips the *entire* Visualization-controls panel (plus the
# text/background settings from Experimental Setup), not just a handful of
# toggles. Each group maps a short URL key → the session_state key it reads/writes.
# `_build_share_query` (write) and `_apply_url_preset` (read) both iterate these,
# so the two sides can't drift. Data-dependent fields (color ranges, highlight
# column, axis/color-by fields) self-heal on load via the sidebar's _drop_stale /
# _clamp_range, so a link opened on a different trial degrades gracefully.
_SHARE_TOGGLE_PARAMS = {  # bool → "1"/"0"
    "show_words": "global_show_words",
    "show_labels": "global_show_labels",
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
    "hollow_fixations": "global_hollow_fixations",
    "scale_text_to_boxes": "global_scale_text_to_boxes",
}
_SHARE_VALUE_PARAMS = {  # string / choice / color → str (emitted only when set)
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
    # VIZ-8: colour-by-reading-type mode + the five class colours.
    "saccade_color_mode": "global_saccade_color_mode",
    "saccade_color_forward": "global_saccade_class_color_forward",
    "saccade_color_skip": "global_saccade_class_color_skip",
    "saccade_color_refixation": "global_saccade_class_color_refixation",
    "saccade_color_return_sweep": "global_saccade_class_color_return_sweep",
    "saccade_color_regression": "global_saccade_class_color_regression",
    "order_font_color": "global_order_font_color",
    "text_color": "global_text_color",
    "highlight_text_color": "global_highlight_text_color",
    "bg_choice": "global_bg_choice",
    "bg_custom": "global_bg_custom",
    "font_family": "global_font_family",
    "word_hover_measure": "global_word_hover_measure",
    "word_hover_fields": "global_word_hover_fields",
    "fixation_hover_fields": "global_fixation_hover_fields",
}
_SHARE_INT_PARAMS = {
    "order_font_size": "global_order_font_size",
    # VIZ-11 follow-up: the animation frame grid. Worth sharing — a link that
    # says "look at this replay" should reproduce the same smoothness.
    "anim_grid_step_ms": "global_anim_grid_step_ms",
    "anim_max_frames": "global_anim_max_frames",
}
_SHARE_FLOAT_PARAMS = {
    "line_spacing": "global_line_spacing",
    "saccade_width": "global_saccade_width",
    "fixation_opacity": "global_fixation_opacity",
    # VIZ-4: image-stimulus opacity (applies to dataset images too, so worth
    # sharing; the uploaded image itself can't ride a link).
    "stimulus_image_opacity": "global_stimulus_image_opacity",
    # VIZ-4: manual image alignment — origin nudge + size scale (apply to dataset
    # images, so they round-trip; an uploaded image is re-uploaded on the far end).
    "stimulus_image_offset_x": "global_stimulus_image_offset_x",
    "stimulus_image_offset_y": "global_stimulus_image_offset_y",
    "stimulus_image_scale": "global_stimulus_image_scale",
}
_SHARE_INT_RANGE_PARAMS = {"marker_size_range": "global_marker_size_range"}
_SHARE_FLOAT_RANGE_PARAMS = {
    "fixation_color_range": "global_fixation_color_range",
    "heatmap_color_range": "global_heatmap_color_range",
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
}

# Widget bounds for the URL-restorable params that feed a min/max-bounded widget
# (slider / number_input). A hand-crafted link with an out-of-range value would
# otherwise crash the widget on render — Streamlit raises when a Session-State
# value falls outside the widget's range. Clamp on the way in. (Data-dependent
# colour ranges aren't here — the sidebar's `_clamp_range` handles those against
# the live data.)
_URL_BOUNDED = {
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
# Sources absent here (uploaded tables, stored datasets, public corpora) can't be
# reconstructed from a link — the Share panel warns and shares the view settings
# only. Mirrors the `source` handling in `main()`.
_SHAREABLE_SOURCES = {
    DEMO_CHOICE: "demo",
    ONESTOP_CHOICE: "onestop",
    MULTIPLEYE_BUNDLE_CHOICE: "multipleye",
    SYNTHETIC_CHOICE: "synthetic",
    # DATA-3: the public OneStop corpus (OSF download-on-demand) is shareable too;
    # its variant/regime/parts options ride alongside via `_build_share_query`.
    ONESTOP_PUBLIC_CHOICE: "onestop_public",
}


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


def _apply_url_preset() -> Optional[str]:
    """Read `st.query_params` and preset Streamlit session state for deep links.

    Returns the URL-requested `source` ("onestop"/"demo"/"upload") or `None`.
    Call this at the very top of `main()` — before any widgets render — so
    session_state values are picked up as the widgets' initial values.

    URL schema (all params optional):
        ?source=onestop          → force "OneStop server bundle" data source
                                   (also demo / synthetic / upload — see main())
        &participant=p001        → preselect participant (Participant mode)
        &trial=37                → preselect trial_index slider
        &trial_id=p001_3_Adv     → land on this exact trial id, any picker mode
                                   (applied after combos build — see
                                   _apply_url_trial_selection; emitted by Share)
        &tab=animation           → pre-tick the Animate toggle (legacy; there's
                                   no separate Animated Scanpath tab anymore)
        &heatmap_colorscale=Greens
        &hide_fixation_numbers=1
        &show_saccades=1
        &show_heatmap=1
        ...etc — see _URL_PRESETS above

    Bonus side-effect: when any colorscale is set via URL, also forces the
    "Advanced styling" sidebar expander open so the value is visible/editable.

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

    # Heatmap / fixation colorscale only render under the Advanced expander —
    # auto-open it so the URL value is exposed in the sidebar.
    if "heatmap_colorscale" in qp or "fixation_colorscale" in qp:
        st.session_state.setdefault("global_advanced", True)

    # Animation is now a checkbox in the Scanpath Visualization tab (no separate
    # tab), so a legacy `?tab=animation` deep link just pre-ticks it.
    if (qp.get("tab") or "").lower() == "animation":
        st.session_state.setdefault("single_animate", True)

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

    source = qp.get("source")
    return source.lower() if source else None


# plot-config layer key → viz-control session_state key. The inverse of the
# `layers` block written by `tabs._render_plot_config_expander`.
_PLOT_CONFIG_LAYER_KEYS = {
    "words": "global_show_words",
    "word_labels": "global_show_labels",
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
# Static widget bounds, mirrored from controls.sidebar_controls /
# render_sidebar_canvas_controls, so a restored value is clamped to a range the
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
PLOT_CONFIG_SCHEMA = 2


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


# version N -> callable that upgrades an N config to N+1. Keyed by the *source*
# version so `_migrate_plot_config` can walk an old config forward step by step.
_PLOT_CONFIG_MIGRATIONS = {
    1: _migrate_config_1_to_2,
}


def _migrate_plot_config(config: dict) -> Tuple[dict, Optional[str]]:
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
    given ``key_prefix`` — including its composite vs. single-dropdown branch —
    so the seeded keys land on the right selectors.

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
    composite_cols = [
        c
        for c in (st.session_state.get("_composite_trial_columns") or [])
        if c in combos.columns
    ]
    if len(composite_cols) >= 2:
        for col in composite_cols:
            st.session_state[f"{key_prefix}_composite_{col}"] = str(row[col])
        st.session_state[f"{key_prefix}_composite_reading"] = str(row["trial_id"])
    else:
        # None/Trial mode renders a single dropdown keyed `<prefix>_trial_id`
        # whose *options* are the trial_field values (`unique_trial_id` when
        # present), so seed that one key with this row's option value — not a
        # `<prefix>_<trial_field>` key, which no widget reads.
        trial_field = (
            "unique_trial_id" if "unique_trial_id" in combos.columns else "trial_id"
        )
        st.session_state[f"{key_prefix}_trial_id"] = str(row[trial_field])
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


def _restore_plot_config(
    config: dict, combos: pd.DataFrame, fixations: pd.DataFrame
) -> Tuple[int, list]:
    """Seed session_state from an uploaded plot-config dict so the sidebar
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

    applied = 0
    skipped: list = []

    def section(name):
        """A config sub-section as a dict — empty if absent or the wrong type,
        so a hand-edited upload with a malformed section can't crash the rest."""
        value = config.get(name)
        return value if isinstance(value, dict) else {}

    def number(value):
        """Coerce a JSON scalar to float, or None for a non-numeric upload."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def put(key, value):
        nonlocal applied
        st.session_state[key] = value
        applied += 1

    def put_valid(valid, key, value, skip_label):
        """Apply ``value`` when ``valid``, else record ``skip_label``."""
        if valid:
            put(key, value)
        else:
            skipped.append(skip_label)

    def put_int(value, key, lo, hi, skip_label):
        """Apply an int clamped to ``[lo, hi]``; skip a non-numeric upload."""
        n = number(value)
        if n is None:
            skipped.append(skip_label)
        else:
            put(key, max(lo, min(int(n), hi)))

    def put_float(value, key, lo, hi, skip_label):
        """Apply a float clamped to ``[lo, hi]``; skip a non-numeric upload."""
        n = number(value)
        if n is None:
            skipped.append(skip_label)
        else:
            put(key, max(lo, min(float(n), hi)))

    # Re-apply the saved column mapping + kept-field choices (so restoring a
    # config skips re-mapping). Seeded before the mapping widgets render.
    _seed_column_mapping(config.get("column_mapping"))

    layers = section("layers")
    for cfg_key, state_key in _PLOT_CONFIG_LAYER_KEYS.items():
        if cfg_key in layers:
            put(state_key, bool(layers[cfg_key]))

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
            style in ("Word boxes", "Interpolated"),
            "global_heatmap_style",
            style,
            "heatmap style",
        )
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
    setup_context = isinstance(config.get("experimental_setup"), dict) or isinstance(
        config.get("canvas_px"), dict
    )
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
        display_dpi = number(setup.get("display_dpi", 96.0))
        put_valid(
            display_dpi is not None,
            "global_display_dpi",
            max(20.0, min(float(display_dpi), 1000.0))
            if display_dpi is not None
            else 96.0,
            "display DPI",
        )
        stimulus_font = number(setup.get("stimulus_font_pt", 12.0))
        put_valid(
            stimulus_font is not None,
            "global_stimulus_font_pt",
            max(4.0, min(float(stimulus_font), 144.0))
            if stimulus_font is not None
            else 12.0,
            "stimulus font",
        )
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
        # The sidebar's `_drop_stale` clears this if it isn't a column in the
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

    selection = section("selection")
    if selection:
        if _restore_selection(selection, combos):
            applied += 1
        else:
            skipped.append("trial selection")

    # Annotations travel with schema-2 configs (Save & restore). Only restore
    # when the key is present, so a plot-config-only file never clears them.
    if "annotations" in config and isinstance(config["annotations"], list):
        n_anno = restore_records(config["annotations"])
        applied += 1
        st.toast(f"Restored {n_anno} annotation(s) from config.", icon="📝")

    return applied, skipped


def _apply_uploaded_plot_config(combos: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """Restore settings from a freshly uploaded plot-config JSON, once per file.

    Reads the file captured by the sidebar ``plot_config_upload`` uploader
    (persisted in session_state across reruns) and writes the saved settings
    into session_state *before* the sidebar widgets render — the same mechanism
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
) -> Tuple[str, list]:
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

    params: Dict[str, str] = {}
    caveats: list = []

    source = _SHAREABLE_SOURCES.get(data_choice)
    if source:
        params["source"] = source
    else:
        caveats.append(
            "This data source can't be rebuilt from a link — the recipient will "
            "need to load the same data. The view settings below are still shared."
        )

    # DATA-3: the public OneStop source carries its variant / regime / parts so a
    # shared link reopens the same corpus slice. The recipient still needs the
    # reports present (or downloadable) — the source caveat above covers that.
    if data_choice == ONESTOP_PUBLIC_CHOICE:
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

    selection = st.session_state.get("_share_selection") or {}
    participant = selection.get("participant_id")
    trial_id = selection.get("trial_id")
    if include_participant and participant not in (None, ""):
        params["participant"] = str(participant)
    if include_trial and trial_id not in (None, ""):
        params["trial_id"] = str(trial_id)

    # Visualization toggles — emit an explicit 0/1 so a layer the user turned
    # *off* is shared as off (the URL coercion reads "0" as False).
    for url_key, state_key in _SHARE_TOGGLE_PARAMS.items():
        if state_key in st.session_state:
            params[url_key] = "1" if st.session_state[state_key] else "0"
    # Strings / choices / colours / numbers — emit only when set.
    for url_key, state_key in {**_SHARE_VALUE_PARAMS, **_SHARE_INT_PARAMS}.items():
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
    if st.session_state.get("single_animate"):
        params["tab"] = "animation"

    return urlencode(params), caveats


def _render_share_link_widget(query: str) -> None:
    """Render the copyable share link (read-only field + Copy button).

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
            <button id="sps-share-copy" type="button">Copy link</button>
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
          #sps-share-copy {{
            flex: 0 0 auto; padding: 0.45rem 0.9rem; cursor: pointer;
            border: 1px solid #1f77b4; border-radius: 8px; white-space: nowrap;
            background: #1f77b4; color: #fff; font-weight: 600; font-size: 0.85rem;
          }}
          #sps-share-copy:hover {{ background: #185fa5; }}
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
          const btn = document.getElementById("sps-share-copy");
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
        height=110,
    )


def _render_share_body(data_choice: str) -> None:
    """Render the **Share** subtab: a deep link to the current view (data source +
    trial + visualization settings).

    The link is built **lazily** — only when the user clicks *Refresh link* (and
    once on first open, or whenever the identity choice changes, so there's
    always something to copy that matches the control). It is NOT rebuilt on
    every rerun, so tweaking an unrelated control doesn't silently rewrite a link
    the user is about to share; the link reflects the settings as of the last
    refresh.

    S3: what the link *names* is a choice made here, at the point of copying.
    The default still carries the participant and trial ids (a link that
    reopens one trial has to identify it), but the caption says so and the
    **What the link includes** picker drops either half."""
    st.markdown(
        "**Share this view** — a link that reopens Scanpath Studio on the "
        "current trial with your visualization settings."
    )
    mode = st.radio(
        "What the link includes",
        _SHARE_IDENTITY_MODES,
        key=_SHARE_IDENTITY_KEY,
        horizontal=True,
        help=(
            "A link lands in browser history, server logs and chat previews. "
            "Drop the participant id when you don't want the link to name a "
            "reader — it still opens on the same trial."
        ),
    )
    include_participant, include_trial = _share_identity_flags(mode)
    refresh = st.button(
        "🔄 Refresh link",
        key="share_refresh",
        type="primary",
        help="Rebuild the link from the current trial + settings.",
    )
    stale = st.session_state.get("_share_query_identity") != mode
    if refresh or stale or st.session_state.get("_share_query_frozen") is None:
        st.session_state["_share_query_frozen"] = _build_share_query(
            data_choice,
            include_participant=include_participant,
            include_trial=include_trial,
        )
        st.session_state["_share_query_identity"] = mode
    query, caveats = st.session_state["_share_query_frozen"]
    for note in caveats:
        st.caption("⚠️ " + note)
    _render_share_link_widget(query)
    st.caption(_share_identity_caution(query))
    st.caption("Reflects your settings as of the last refresh.")


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------
def _go_corpus() -> None:
    st.session_state["main_nav"] = _VIEW_CORPUS


def _go_scanpath() -> None:
    st.session_state["main_nav"] = _VIEW_SCANPATH


def _active_view() -> str:
    """The active top-level view, normalized to one of the two pages.

    ``main_nav`` may carry a legacy/stale value (e.g. "Data Inspection", now a
    subtab); anything that isn't Corpus resolves to the Scanpath page."""
    return (
        _VIEW_CORPUS
        if st.session_state.get("main_nav") == _VIEW_CORPUS
        else _VIEW_SCANPATH
    )
