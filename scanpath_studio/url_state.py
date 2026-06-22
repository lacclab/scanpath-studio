"""Deep links, plot-config save/restore, share links, and view-nav state.

Split out of ``app.py`` so the URL/deep-link contract, the plot-config
save/restore round-trip, the Share-link builder/widget, and the
Corpus⇄Scanpath view toggle live in one focused module. ``app.py`` imports
these; nothing here imports back from ``app`` (no cycle).
"""

from __future__ import annotations

import json
import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from .annotations import restore_records
from .controls import (
    _OUT_OF_TEXT_MARKERS,
    color_field_options,
    numeric_field_options,
)
from .constants import (
    BACKGROUND_PRESETS,
    COLORSCALES,
    DEMO_CHOICE,
    ONESTOP_CHOICE,
    SACCADE_DASH_OPTIONS,
    SACCADE_WIDTH_BOUNDS,
    SYNTHETIC_CHOICE,
    _VIEW_CORPUS,
    _VIEW_SCANPATH,
)

# URL query-param → session_state key map for the deep-link API. Used by
# `_apply_url_preset()` to preset widgets when the page is opened from an
# external tool with a deep link.
#
# Selection prefixes — every selectable tab (Scanpath Visualization,
# Generations, …) renders its own `select_trial` with a different `key_prefix`,
# so a URL deep link has to seed all of them or only the first tab lands on
# the requested trial. Keep this list in sync with the `key_prefix=` values
# passed to `select_trial` in tabs.py.
_SELECTION_PREFIXES = ("single", "multi")


def _coerce_bool(v) -> bool:
    return str(v).lower() not in {"0", "false", "no"}


def _parse_int_range(v) -> tuple:
    a, b = (int(float(x)) for x in str(v).split(",")[:2])
    return (min(a, b), max(a, b))


def _parse_float_range(v) -> tuple:
    a, b = (float(x) for x in str(v).split(",")[:2])
    return (min(a, b), max(a, b))


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
    "show_heatmap": "global_show_heatmap",
    "show_raw_gaze": "global_show_raw_gaze",
    "show_colorbars": "global_show_colorbars",
    "highlight_out_of_text": "global_highlight_out_of_text",
    "hollow_fixations": "global_hollow_fixations",
    "scale_text_to_boxes": "global_scale_text_to_boxes",
}
_SHARE_VALUE_PARAMS = {  # string / choice / color → str (emitted only when set)
    "color_by": "global_color_by",
    "heatmap_style": "global_heatmap_style",
    "heatmap_metric": "global_heatmap_metric",
    "critical_span_style": "global_critical_span_style",
    "highlight_column": "global_highlight_column",
    "x_field": "global_x_field",
    "y_field": "global_y_field",
    "saccade_style": "global_saccade_style",
    "fixation_colorscale": "global_fixation_colorscale",
    "heatmap_colorscale": "global_heatmap_colorscale",
    "saccade_color": "global_saccade_color",
    "order_font_color": "global_order_font_color",
    "text_color": "global_text_color",
    "highlight_text_color": "global_highlight_text_color",
    "bg_choice": "global_bg_choice",
    "bg_custom": "global_bg_custom",
    "font_family": "global_font_family",
}
_SHARE_INT_PARAMS = {"order_font_size": "global_order_font_size"}
_SHARE_FLOAT_PARAMS = {
    "line_spacing": "global_line_spacing",
    "saccade_width": "global_saccade_width",
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
    "global_marker_size_range": (4, 40),
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
    SYNTHETIC_CHOICE: "synthetic",
}


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
}
# Static widget bounds, mirrored from controls.sidebar_controls /
# render_sidebar_canvas_controls, so a restored value is clamped to a range the
# widget will accept.
_CANVAS_BOUNDS = (100, 10000)
_FONT_BOUNDS = (6, 72)
_MARKER_BOUNDS = (4, 40)


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
    if "heatmap_style" in coloring:
        style = coloring["heatmap_style"]
        put_valid(
            style in ("Word boxes", "Interpolated"),
            "global_heatmap_style",
            style,
            "heatmap style",
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
    if "hollow_fixations" in coloring:
        put("global_hollow_fixations", bool(coloring["hollow_fixations"]))
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

    canvas = section("canvas_px")
    if "width" in canvas:
        put_int(canvas["width"], "global_canvas_width", *_CANVAS_BOUNDS, "canvas width")
    if "height" in canvas:
        put_int(
            canvas["height"], "global_canvas_height", *_CANVAS_BOUNDS, "canvas height"
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
    if "highlight_out_of_text" in highlighting:
        put("global_highlight_out_of_text", bool(highlighting["highlight_out_of_text"]))
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
    sym = highlighting.get("out_of_text_symbol")
    if sym is not None:
        put_valid(
            sym in _OUT_OF_TEXT_MARKERS,
            "global_out_of_text_symbol",
            sym,
            "out-of-text marker",
        )
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


def _build_share_query(data_choice: str) -> Tuple[str, list]:
    """Build the deep-link query string that reproduces the current view.

    Reads the resolved trial selection and visualization settings back out of
    ``st.session_state`` and encodes them with the same URL schema
    ``_apply_url_preset`` / ``_apply_url_trial_selection`` parse, so opening the
    link reopens the app on this trial with these settings.

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

    selection = st.session_state.get("_share_selection") or {}
    participant = selection.get("participant_id")
    trial_id = selection.get("trial_id")
    if participant not in (None, ""):
        params["participant"] = str(participant)
    if trial_id not in (None, ""):
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
            params[url_key] = str(value)
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

    A same-origin ``components.html`` iframe (same trick as the tour — see
    ``tour.render_spotlight_tour``) composes the full URL from the *live* address:
    ``window.parent.location.origin + pathname`` + the query string built
    server-side. Doing the origin/path join client-side means the link is correct
    wherever the app is served (localhost, Streamlit Cloud, a reverse proxy)
    without the server having to know its own public URL. Copy uses the async
    Clipboard API with a ``document.execCommand`` fallback for insecure contexts.
    """
    payload = json.dumps(query)
    components.html(
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
    once on first open so there's always something to copy). It is NOT rebuilt on
    every rerun, so tweaking an unrelated control doesn't silently rewrite a link
    the user is about to share; the link reflects the settings as of the last
    refresh."""
    st.markdown(
        "**Share this view** — a link that reopens Scanpath Studio on the "
        "current trial with your visualization settings."
    )
    refresh = st.button(
        "🔄 Refresh link",
        key="share_refresh",
        type="primary",
        help="Rebuild the link from the current trial + settings.",
    )
    if refresh or st.session_state.get("_share_query_frozen") is None:
        st.session_state["_share_query_frozen"] = _build_share_query(data_choice)
    query, caveats = st.session_state["_share_query_frozen"]
    for note in caveats:
        st.caption("⚠️ " + note)
    _render_share_link_widget(query)
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
