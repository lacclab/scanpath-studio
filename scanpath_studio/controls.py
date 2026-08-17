from __future__ import annotations

import html
import math
import re
from collections.abc import Callable

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException
from streamlit_sortables import sort_items

from .alignment import ALGORITHMS as ALIGN_ALGORITHMS
from .annotations import known_tags
from .constants import (
    BACKGROUND_PRESETS,
    COLORSCALES,
    CUSTOM_PALETTE,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_COLORSCALE,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_HEATMAP_COLORSCALE,
    DEFAULT_MARKER_SIZE_RANGE,
    DEFAULT_PALETTE,
    DEFAULT_SACCADE_WIDTH,
    DEMO_CHOICE,
    FIXATION_SYMBOLS,
    HIGHLIGHTED_TEXT_COLOR,
    OUT_OF_TEXT_COLOR,
    PALETTES,
    SACCADE_CLASS_COLORS,
    SACCADE_CLASS_EDITABLE,
    SACCADE_CLASS_LABELS,
    SACCADE_CLASS_ORDER,
    SACCADE_COLOR,
    SACCADE_COLOR_MODES,
    SACCADE_DASH_OPTIONS,
    SACCADE_WIDTH_BOUNDS,
    UNIFORM_COLOR_FIELD,
    WORD_LABEL_COLOR,
    compare_palette_color,
    drift_correction_enabled,
    palette_settings,
)
from .data import frame_fingerprint
from .export import (
    DEFAULT_CAPTION_PATTERN,
    DEFAULT_TITLE_PATTERN,
    pattern_error,
    pattern_fields,
    render_pattern,
)

NONE_OPTION = "(none)"


# --- UX-51: compact `label | field` rows --------------------------------------
# Every control in the Scanpath rail used to stack its title ABOVE its field, so
# one ⚙️ Style popover spent well over a screen's height on eight controls. The
# title now sits in a column to the LEFT of the field: a row is one line instead
# of two, and a section reads as a compact form rather than a long scroll.
#
# Built from per-row `st.columns`, not CSS on Streamlit's own widget-label DOM.
# The split is then ordinary layout — it cannot leak outside the containers we
# build it in, and it does not ride on internal test ids a Streamlit re-skin can
# move. (Container-scoped CSS is the fallback if this reads badly when the rail
# is tight, not the starting point.)
#
# ONE label width for the whole rail (`_LABEL_W`) rather than a width per row:
# labels lining up down a section — and across sections — is most of what makes
# the result read as a form. A label too long for the column truncates with an
# ellipsis and shows in full on hover, instead of widening the column for every
# other row in the section.
#
# The widget keeps its real `label` and `help`, and merely hides them
# (`label_visibility="collapsed"`), so the accessible name, `AppTest` lookups and
# the wire format are all untouched. What the user sees is the markdown twin in
# the left column — and the `?` tooltip icon folds INTO it: the help text becomes
# the label's own hover tooltip, which buys back the icon's width on every row.
#
# Controls whose label already sits beside the field — `st.checkbox`,
# `st.toggle` — keep their native one-line shape; splitting those would only
# indent them away from the section's other rows.

#: The label column's share of a `label | field` row. Tuned for the ~28rem
#: popover body (`styles.get_app_css` pins `stPopoverBody`), which is where these
#: rows live: ~160px of label — about 23 characters at the rail's 0.92rem — while
#: leaving the field wide enough for a multiselect's chips, or for a slider plus
#: the UX-9 box you type an exact value into.
_LABEL_W = 0.36

#: Tighter than the 1rem default: these rows are dense and the width is scarce.
_LABEL_GAP = "xsmall"

#: `label | field | note` for one column-mapping row (UX-52 round 3). Its own
#: triple rather than `_LABEL_W`: the mapping renders full-width on the 🗂️ Data
#: page and inside the upload wizard, not in the rail's ~28rem popover, so there
#: is room for the "✨ auto-detected …" note beside the field instead of under it.
_MAPPING_ROW_W = (0.24, 0.40, 0.36)

#: Markdown emphasis, which a plain-text `title=` attribute would show as
#: literal punctuation.
_MD_MARKS = re.compile(r"\*\*|`")


def _plain(text: str) -> str:
    """``text`` with markdown emphasis stripped, for a plain-text tooltip."""
    return _MD_MARKS.sub("", text).strip()


def _row_label(host, label: str, help: str | None) -> None:
    """Render one row's title into its own (left) column — see the UX-51 note.

    ``help`` folds into the title's own hover tooltip rather than getting a `?`
    icon beside it, and the title text is repeated at the head of that tooltip so
    a label the column had to truncate is still readable in full.

    The tooltip is CSS (``data-tip`` + ``styles.py``'s ``.sps-fhelp::after``),
    not the browser's native ``title=``. Native ``title`` waits about a second
    before it appears — fine for an occasional "what is this file", far too slow
    for a form whose every row hides its description there. The CSS one opens in
    ~120 ms, matching the `?` icons Streamlit draws elsewhere. ``aria-label``
    keeps the text reachable now that no ``title`` carries it.
    """
    text = _plain(label)
    if not help:
        host.markdown(
            f'<span class="sps-flabel">{html.escape(text)}</span>',
            unsafe_allow_html=True,
        )
        return
    tip = html.escape(f"{text} — {_plain(help)}", quote=True)
    host.markdown(
        f'<span class="sps-fhelp" data-tip="{tip}" aria-label="{tip}">'
        f'<span class="sps-flabel sps-flabel-help">{html.escape(text)}</span>'
        "</span>",
        unsafe_allow_html=True,
    )


def _labeled(
    host,
    kind: str,
    label: str,
    *,
    display: str | None = None,
    help: str | None = None,
    **kwargs,
):
    """Render one control as a ``label | field`` row; return the widget's value.

    ``kind`` names the Streamlit method to call (``"selectbox"``,
    ``"multiselect"``, ``"color_picker"``, …) and every other argument is
    forwarded untouched, so converting a call site is a matter of *naming* the
    widget instead of calling it. The widget still receives the real ``label``
    and ``help`` — only where they are drawn changes.

    ``display`` overrides the *visible* text without touching the widget's own
    label. Use it where the accessible name has to stay unique but would be far
    too long for the column — the per-scanpath comparison styling, whose rows are
    already captioned with the scanpath they belong to.
    """
    label_col, field_col = host.columns(
        [_LABEL_W, 1.0 - _LABEL_W], gap=_LABEL_GAP, vertical_alignment="center"
    )
    _row_label(label_col, display if display is not None else label, help)
    return getattr(field_col, kind)(
        label, help=help, label_visibility="collapsed", **kwargs
    )


def _slider_row(host, n_boxes: int) -> list:
    """Columns for a ``label | slider | box…`` row, label column first (UX-51).

    The slider keeps its pre-UX-51 5 : 1.5 proportion against each typed box; the
    label takes ``_LABEL_W`` off the top so the row lines up with the plain
    ``label | field`` rows around it. ``vertical_alignment="center"`` is what puts
    the label beside the slider's *track*: a slider prints its current value
    above the track, so a top-aligned label would sit against that number instead
    of against the control.
    """
    rest = 1.0 - _LABEL_W
    total = 5.0 + 1.5 * n_boxes
    weights = [_LABEL_W, rest * 5.0 / total, *([rest * 1.5 / total] * n_boxes)]
    return host.columns(weights, gap=_LABEL_GAP, vertical_alignment="center")


# --- UX-9: sliders you can also type an exact value into ----------------------
# A slider is the right control for "sweep until it looks right", but it can't be
# set to a precise value — awkward when a figure has to match a spec (marker size
# 12, opacity 0.65, line width 1.5). These wrappers pair each slider with a
# number box.
#
# The SLIDER keeps the canonical session key, so nothing downstream changes: deep
# links, Share, Save & restore and `_collect_viz_settings` all still read
# `global_*` / `cmp*_*` / `single_*` exactly as before. The box owns a shadow
# `{key}__num*` key and writes the canonical one from its `on_change`; the
# canonical value is mirrored back into the box *before* either widget renders,
# so a slider drag, a deep link, a restored config and a Quick-view preset all
# move the box too — one-way sync each direction, no feedback loop.


def _shadow_key_missing(*keys: str) -> bool:
    """True when a number box's shadow key is not in session state (BUG-18).

    An ``on_change`` callback runs *before* the script that would (re)create the
    widget, and Streamlit drops a widget's key at the end of any run in which it
    did not render. Several of these boxes are conditional — the heatmap
    colour-range pair only renders when the current trial/metric has data — so a
    change queued while a slow rerun was still in flight can reach a callback
    whose own key no longer exists, and reading it raised ``KeyError`` and took
    the app down mid-rerun.

    A missing shadow key means there is no user edit left to apply: the canonical
    key still holds the last committed value, and the box re-seeds from it the
    next time it renders. So the callback becomes a no-op rather than a crash.
    """
    return any(k not in st.session_state for k in keys)


_INT_NUMBER_FORMATS = frozenset({"%d", "%u", "%i"})


def _number_box_format(fmt: str | None, *values) -> str | None:
    """Adapt a slider's ``format`` for the number box beside it.

    ``st.number_input`` renders a yellow "value below has type float, but format
    %d displays as integer" warning above itself when an integer format meets a
    float value — and the colour-range sliders pass float bounds on purpose (so a
    restored config clamps into another dataset's range) while wanting whole
    numbers on screen. ``"%.0f"`` shows the same digits without the warning.
    """
    if fmt in _INT_NUMBER_FORMATS and any(isinstance(v, float) for v in values):
        return "%.0f"
    return fmt


def _numeric_slider(
    host,
    label: str,
    *,
    key: str,
    min_value,
    max_value,
    step=None,
    slider_format: str | None = None,
    number_format: str | None = None,
    help: str | None = None,
    disabled: bool = False,
    on_change=None,
    persist_state: str | None = None,
    label_left: bool = False,
    display: str | None = None,
) -> None:
    """A single-value slider plus a number box bound to the same setting.

    ``number_format`` defaults to ``slider_format``; pass it separately when the
    slider's format carries a unit suffix (``"%.1f px"``), which ``number_input``
    does not accept.

    ``disabled`` greys BOTH halves (VIZ-21) without touching the canonical key —
    a disabled Streamlit widget still owns and keeps its value, so a mode toggle
    never rewrites a deep-linked / restored setting.

    ``label_left`` opts the row into the UX-51 ``label | slider | box`` shape.
    It is opt-in rather than the default because the sliders in the rail's
    ⚙️ Playback popover are laid out two-up in half-width columns, where a third
    column would leave the slider unusable.
    """
    num_key = f"{key}__num"
    if key in st.session_state:
        st.session_state[num_key] = st.session_state[key]

    def _apply() -> None:
        if _shadow_key_missing(num_key):  # BUG-18
            return
        st.session_state[key] = st.session_state[num_key]
        if on_change is not None:
            on_change()

    # A narrow box on the same line as the slider: the box is for typing an
    # exact value, so it only needs room for the number itself (the CSS drops its
    # +/- steppers and caps its width), and the slider keeps most of the row.
    if label_left:
        label_col, slider_col, num_col = _slider_row(host, 1)
        _row_label(label_col, display if display is not None else label, help)
    else:
        slider_col, num_col = host.columns([5, 1.5], vertical_alignment="bottom")
    slider_col.slider(
        label,
        min_value=min_value,
        max_value=max_value,
        step=step,
        format=slider_format,
        key=key,
        help=help,
        disabled=disabled,
        on_change=on_change,
        persist_state=persist_state,
        label_visibility="collapsed" if label_left else "visible",
    )
    num_col.number_input(
        label,
        min_value=min_value,
        max_value=max_value,
        step=step,
        format=_number_box_format(
            number_format if number_format is not None else slider_format,
            min_value,
            max_value,
            step,
            st.session_state.get(num_key),
        ),
        key=num_key,
        on_change=_apply,
        label_visibility="collapsed",
        disabled=disabled,
    )


def _range_slider(
    host,
    label: str,
    *,
    key: str,
    min_value,
    max_value,
    step=None,
    slider_format: str | None = None,
    number_format: str | None = None,
    help: str | None = None,
    disabled: bool = False,
    on_change=None,
    persist_state: str | None = None,
    label_left: bool = False,
    display: str | None = None,
) -> None:
    """A two-handle range slider plus min/max number boxes, all on one line.

    The boxes are deliberately small — they hold a number, not a sentence — so
    the slider still gets most of the row. A min typed above the max is swapped
    rather than rejected. ``disabled`` greys all three without changing the
    stored range (VIZ-21).

    ``label_left`` / ``display`` behave as in :func:`_numeric_slider` (UX-51).
    """
    lo_key, hi_key = f"{key}__num_lo", f"{key}__num_hi"
    current = st.session_state.get(key)
    if isinstance(current, (tuple, list)) and len(current) == 2:
        st.session_state[lo_key], st.session_state[hi_key] = current

    def _apply() -> None:
        if _shadow_key_missing(lo_key, hi_key):  # BUG-18
            return
        lo, hi = st.session_state[lo_key], st.session_state[hi_key]
        st.session_state[key] = (min(lo, hi), max(lo, hi))
        if on_change is not None:
            on_change()

    if label_left:
        label_col, slider_col, lo_col, hi_col = _slider_row(host, 2)
        _row_label(label_col, display if display is not None else label, help)
    else:
        slider_col, lo_col, hi_col = host.columns(
            [5, 1.5, 1.5], vertical_alignment="bottom"
        )
    slider_col.slider(
        label,
        min_value=min_value,
        max_value=max_value,
        step=step,
        format=slider_format,
        key=key,
        help=help,
        disabled=disabled,
        on_change=on_change,
        persist_state=persist_state,
        label_visibility="collapsed" if label_left else "visible",
    )
    fmt = number_format if number_format is not None else slider_format
    for col, num_key, side in ((lo_col, lo_key, "min"), (hi_col, hi_key, "max")):
        col.number_input(
            f"{label} ({side})",
            min_value=min_value,
            max_value=max_value,
            step=step,
            format=_number_box_format(
                fmt, min_value, max_value, step, st.session_state.get(num_key)
            ),
            key=num_key,
            on_change=_apply,
            label_visibility="collapsed",
            disabled=disabled,
        )


# VIZ-4: MIME by extension for a user-uploaded stimulus image → a `data:` URI the
# figure builders accept as `background_image` (plots._image_to_data_uri passes a
# `data:` URI straight through).
_UPLOAD_IMAGE_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _uploaded_image_data_uri(uploaded) -> str | None:
    """Base64 ``data:`` URI for a Streamlit ``UploadedFile`` image, or ``None``.

    Cached in session state keyed by the file's id so a multi-MB screenshot is
    encoded once, not on every rerun (VIZ-4)."""
    if uploaded is None:
        return None
    import base64

    cache = st.session_state.get("_stimulus_image_upload_cache")
    if isinstance(cache, dict) and cache.get("id") == uploaded.file_id:
        return cache.get("uri")
    ext = (uploaded.name.rsplit(".", 1)[-1] if "." in uploaded.name else "").lower()
    mime = _UPLOAD_IMAGE_MIME.get(ext, "image/png")
    uri = f"data:{mime};base64," + base64.b64encode(uploaded.getvalue()).decode("ascii")
    st.session_state["_stimulus_image_upload_cache"] = {
        "id": uploaded.file_id,
        "uri": uri,
    }
    return uri


# PRE-3: drift-correction picker options — "Off" + each algorithm title-cased.
_ALIGN_OPTIONS = ["Off", *(a.title() for a in ALIGN_ALGORITHMS)]


# --- VIZ-21/23: which rail controls actually apply in Animate / Compare -------
# One rail feeds the static, animation, and comparison renderers, but some layers
# do not exist in every mode. Each affected control therefore declares which
# render paths consume it. Unsupported controls stay visible but disabled so the
# reason is discoverable, and their stored values survive mode switches, deep
# links, and restored configs. Keep the authoritative setting → render-path
# table in `CLAUDE.md` in sync with these gates.


def _mode_gate(
    animating: bool,
    comparing: bool,
    *,
    in_animation: bool = True,
    in_compare: bool = True,
) -> tuple[bool, str]:
    """``(disabled, reason)`` for a control, given which paths honour it.

    ``in_animation`` / ``in_compare`` state whether the corresponding builder
    actually consumes the setting. The reason string is prefixed onto the
    control's ``help`` so the tooltip explains the greying instead of leaving
    the user guessing."""
    modes = []
    if animating and not in_animation:
        modes.append("**Animate**")
    if comparing and not in_compare:
        modes.append("**Compare**")
    if not modes:
        return False, ""
    return True, (
        "⚠️ Not available in " + " / ".join(modes) + " mode — that render path "
        "ignores this setting. Your value is kept and applies again once the "
        "mode is off."
    )


def _gated_help(base: str | None, reason: str) -> str | None:
    """Prefix ``reason`` (from :func:`_mode_gate`) onto a control's help text."""
    if not reason:
        return base
    return f"{reason}\n\n{base}" if base else reason


# Static defaults for the keyed visualization widgets that the plot-config
# restore (app._restore_plot_config) can set. Seeded into session_state so those
# widgets render WITHOUT a `value=`/`index=` argument — that keeps their key
# programmatically settable without Streamlit's "default value but also set via
# Session State API" warning. Data-dependent defaults (color-by / axis fields /
# sizing / canvas) are seeded locally where they're computed.
_VIZ_WIDGET_DEFAULTS = {
    # First-load layers default to the *core scanpath* only — fixations, saccades
    # and the reading text — so a new user lands on a legible picture instead of
    # seven stacked encodings. The bounding-box grid and the density heatmap are
    # analytical overlays, off by default and one click (or one Quick view) away.
    "global_show_words": False,
    "global_show_labels": True,
    "global_show_fix": True,
    "global_show_order": False,
    "global_show_saccades": True,
    "global_show_saccade_arrows": False,
    "global_saccade_color": SACCADE_COLOR,
    "global_saccade_style": "Solid",
    "global_saccade_width": DEFAULT_SACCADE_WIDTH,
    # VIZ-8: colour saccades uniformly, or by reading type (forward / skip /
    # refixation / return sweep / regression). "By type" splits the saccade trace
    # into one colour per class with a small legend; the five class colours are
    # each restorable, so seed them here.
    "global_saccade_color_mode": "Uniform",
    # VIZ-8: show the saccade-type colour key on the plot (default on). Optional,
    # like the other legends.
    "global_saccade_type_legend": True,
    "global_saccade_class_color_forward": SACCADE_CLASS_COLORS["forward"],
    "global_saccade_class_color_skip": SACCADE_CLASS_COLORS["skip"],
    "global_saccade_class_color_refixation": SACCADE_CLASS_COLORS["refixation"],
    "global_saccade_class_color_return_sweep": SACCADE_CLASS_COLORS["return_sweep"],
    "global_saccade_class_color_regression": SACCADE_CLASS_COLORS["regression"],
    # VIZ-31: the saccade *filter* — which reading classes are drawn at all. The
    # same `measures.classify_saccades` split the colour mode above uses, applied
    # as visibility instead of hue ("show me only the regressions"). Default is
    # every class, which the figure builder treats as "no filter" and short-
    # circuits, so the common case pays nothing.
    "global_saccade_classes": list(SACCADE_CLASS_ORDER),
    # VIZ-9 "linear reading" mode: draw saccades as upward arcs (`Arc`) instead of
    # straight connectors, and/or snap each fixation above the word it lands on.
    "global_saccade_render_mode": "Straight",
    "global_fixation_snap_to_word": False,
    "global_illustration_label": "Auto",
    # VIZ-10: autoplay the animated replay on load (default on). The toggle lives
    # in the Animate ⚙ Playback popover (tabs.render_single_trial_tab); the kickoff
    # runs at the configured playback speed (plots.animation_autoplay_post_script).
    "global_anim_autoplay": True,
    # VIZ-11 follow-up: the animation frame grid, exposed instead of decided for
    # the user. Step = smoothness; max frames = the ceiling that keeps a long
    # reading's GIF/MP4 bounded (it coarsens the step, and the popover says so).
    # Defaults match the old constants, so nothing changes until someone moves them.
    "global_anim_grid_step_ms": 100,
    "global_anim_max_frames": 360,
    # VIZ-6: fixation marker alpha. Default 0.7 so overlapping fixations show
    # through (the classic translucent scanpath look); drag to 1.0 for fully
    # opaque markers. This replaced the old binary `Hollow circles` toggle in the
    # UI — the `global_hollow_fixations` key is kept (no widget) so saved configs
    # / deep links that carry it still render hollow.
    "global_fixation_opacity": 0.7,
    "global_hollow_fixations": False,
    # VIZ-17: the flat colour every fixation wears when "Color fixations by" is
    # "(uniform)" — the default, since marker size already encodes duration.
    "global_fixation_color": DEFAULT_FIXATION_COLOR,
    # VIZ-15: fixation marker shape. A second encoding channel that, unlike hue,
    # survives greyscale printing.
    "global_fixation_symbol": DEFAULT_FIXATION_SYMBOL,
    # VIZ-18: the active colour palette. A preset, not a rendering mode — picking
    # one writes the individual colour keys below, so every per-element picker
    # still overrides it and every surface carries the resulting colours.
    "global_palette": DEFAULT_PALETTE,
    # PRE-3: in-place vertical drift-correction. "Off" = raw fixations; otherwise
    # one of alignment.ALGORITHMS (title-cased in the UI) snaps each fixation to
    # its assigned text line. `align_connectors` draws faint original→corrected
    # connector lines.
    "global_align_algorithm": "Off",
    "global_align_connectors": False,
    "global_highlight_text_color": HIGHLIGHTED_TEXT_COLOR,
    "global_show_heatmap": False,
    "global_duration_mass_sigma_chars": 1.0,
    "global_show_raw_gaze": False,
    "global_show_stimulus_image": False,
    # VIZ-4: image-based stimuli. Opacity dims a busy stimulus image so the AOIs /
    # scanpath read over it (round-trips in Share / Save & restore, since it also
    # applies to dataset images). A user-uploaded image (session-only — an uploaded
    # image can't ride a deep link) is stretched to fill the monitor; precise
    # crop placement is available via the CLI / headless API (background_image_*).
    "global_stimulus_image_opacity": 1.0,
    # VIZ-4: manual image alignment — nudge the image origin (px) and scale its
    # size so it lines up with the text boxes / fixations when the data's frame
    # doesn't match the image. Applies to dataset + uploaded images alike.
    "global_stimulus_image_offset_x": 0.0,
    "global_stimulus_image_offset_y": 0.0,
    "global_stimulus_image_scale": 1.0,
    "global_heatmap_style": "Word boxes",
    "global_heatmap_metric": "duration_ms",
    # VIZ-3: heatmap colour-scaling. "Linear" maps colour straight to the value;
    # "Log" maps to log1p(value), compressing heavy-tailed dwell times so a few
    # very-hot words don't wash out the rest.
    "global_heatmap_norm": "Linear",
    "global_show_colorbars": False,
    # Frame the view to the whole presentation monitor (scanpath sits at its true
    # on-screen position) rather than cropping to the data extent. Default on.
    "global_fit_to_monitor": True,
    # VIZ-34: optional monitor-pixel coordinate grid. Auto chooses a stable
    # 1/2/5×10ⁿ interval from the visible range; the stored manual value remains
    # available while Auto is on so switching back does not lose it.
    "global_show_coordinate_grid": False,
    "global_coordinate_grid_auto": True,
    "global_coordinate_grid_spacing": 100.0,
    "global_order_font_color": "#111111",
    "global_order_font_size": 10,
    "global_fixation_colorscale": DEFAULT_FIXATION_COLORSCALE,
    "global_heatmap_colorscale": DEFAULT_HEATMAP_COLORSCALE,
    # Restorable by the Save & restore config too, so seed here (no inline
    # value=/index=) to avoid Streamlit's "default value but also set via
    # Session State API" warning when a restore pre-sets them.
    "global_critical_span_style": "Mark text",
    "global_span_border_color": "#000000",
    # Fixation classification (viz-only — PRE-2). SHORT / LONG / OUT-OF-BOUNDS
    # each get a mode (Off | Highlight | Discard); Highlight overlays a marker in
    # the chosen symbol+colour, Discard hides them from the plot only (reading
    # measures and export tables are untouched). Short/long thresholds in ms
    # follow eyekit's discard_short (~80) / discard_long (~800).
    "global_fixclass_short_mode": "Off",
    "global_fixclass_short_threshold_ms": 80,
    "global_fixclass_short_symbol": "triangle-up-open",
    "global_fixclass_short_color": "#ff7f0e",
    "global_fixclass_long_mode": "Off",
    "global_fixclass_long_threshold_ms": 800,
    "global_fixclass_long_symbol": "square-open",
    "global_fixclass_long_color": "#9467bd",
    "global_fixclass_oob_mode": "Off",
    "global_fixclass_oob_symbol": "x",
    "global_fixclass_oob_color": OUT_OF_TEXT_COLOR,
    "global_fixclass_blink_mode": "Off",
    "global_fixclass_blink_symbol": "diamond-open",
    "global_fixclass_blink_color": "#17becf",
    # VIZ-7: single-trial fixation-index window (start, end over `order_in_trial`)
    # for the main scanpath plot. `None` = full trial; the real bounds depend on
    # the selected trial's fixation count, so `sidebar_controls` resolves/clamps
    # the concrete (1, max_fix) range at render time (mirroring `multi_fix_range`).
    "single_fix_range": None,
    # Whether that window survives a trial change. Off = the window belongs to
    # the trial it was drawn on (switching trials shows the whole new trial); on
    # = re-apply it to every trial, clamped to each one's length. Pinned here so
    # it re-syncs when its popover first mounts on a later run (BUG-15).
    "single_fix_range_all_trials": False,
    # Show the A/B legend on the two-trial comparison overlay (CMP-2). Off by
    # default — the per-scanpath colours already tell the readings apart.
    "global_show_compare_legend": False,
    # VIZ-13: reading measure shown in the word hover tooltip. "Off" (None) hides
    # the measure line; any canonical measure column name shows it.
    "global_word_hover_measure": "total_fixation_duration_ms",
    # Colour-bar styling (Axes & color bars expander).
    "global_colorbar_orientation": "Vertical",
    "global_colorbar_tickangle": 0,
    "global_colorbar_tickfont_size": 12,
    # EXP-5: title/caption on the figure (Figure & canvas group). Off by default;
    # the two patterns are only meaningful while the toggle is on — see
    # `_collect_viz_settings`, which reports them empty otherwise.
    "global_show_title_caption": False,
    "global_title_pattern": "",
    "global_caption_pattern": "",
}


# Out-of-text fixation marker options: Plotly symbol → emoji-prefixed label (the
# emoji makes each choice stand out in the dropdown).
_OUT_OF_TEXT_MARKERS = {
    "x": "✖️ Cross",
    "circle-open": "⭕ Circle",
    "diamond-open": "🔷 Diamond",
    "square-open": "🟦 Square",
    "star": "⭐ Star",
    "triangle-up-open": "🔺 Triangle",
    "triangle-down-open": "🔻 Triangle (down)",
}

# Fixation-classification modes (PRE-2): a category can be left alone, marked with
# an overlay marker, or hidden from the plot (viz-only — never changes measures).
_FIXCLASS_MODES = ("Off", "Highlight", "Discard")


def _render_fixclass_category(
    key_prefix: str,
    label: str,
    *,
    threshold_label: str | None = None,
    disabled: bool = False,
    reason: str = "",
) -> None:
    """Render one fixation-classification category (PRE-2) inside the Fixation popover.

    A mode radio (Off / Highlight / Discard); when not Off and ``threshold_label``
    is given, a ms threshold number input; when Highlight, a marker + colour picker.
    All values ride ``global_fixclass_{key_prefix}_*`` keys (seeded in
    ``_VIZ_WIDGET_DEFAULTS``). ``disabled``/``reason`` come from
    :func:`_mode_gate` — since VIZ-23 the flags reach the static figure *and* the
    animated replay, but no comparison builder takes them."""
    mode = _labeled(
        st,
        "radio",
        label,
        options=_FIXCLASS_MODES,
        horizontal=True,
        key=f"global_fixclass_{key_prefix}_mode",
        persist_state="session",
        help=_gated_help(
            "Highlight marks these fixations with an overlay marker; Discard hides "
            "them from the plot only (reading measures and exported tables are "
            "unchanged).",
            reason,
        ),
        disabled=disabled,
    )
    if threshold_label is not None and mode != "Off":
        _labeled(
            st,
            "number_input",
            threshold_label,
            min_value=1,
            step=10,
            key=f"global_fixclass_{key_prefix}_threshold_ms",
            persist_state="session",
            disabled=disabled,
        )
    if mode == "Highlight":
        _labeled(
            st,
            "selectbox",
            "Marker",
            options=list(_OUT_OF_TEXT_MARKERS),
            format_func=lambda s: _OUT_OF_TEXT_MARKERS[s],
            key=f"global_fixclass_{key_prefix}_symbol",
            persist_state="session",
            disabled=disabled,
        )
        _labeled(
            st,
            "color_picker",
            "Color",
            key=f"global_fixclass_{key_prefix}_color",
            disabled=disabled,
        )


def _render_fixation_cleaning(*, disabled: bool = False, reason: str = "") -> None:
    """PRE-2 short / long / out-of-bounds visual filtering controls.

    VIZ-27 gives this its own popover instead of burying data inclusion under
    marker styling. Viz-only: highlight or discard, with
    customizable short/long thresholds, all on the spot.

    ``make_scanpath_figure`` and ``make_scanpath_animation`` both consume
    ``fixation_flags`` (VIZ-23 — *Discard* drops the rows before the replay's
    frames are built, *Highlight* overlays them as the trail reaches them); the
    comparison builders take no flags argument, so the whole block renders
    disabled (with the reason) in Compare only."""
    st.caption("Highlight or hide classes on the plot only")
    for prefix, label, threshold in (
        ("short", "Short fixations", "Short threshold (ms)"),
        ("long", "Long fixations", "Long threshold (ms)"),
        ("oob", "Out-of-bounds fixations", None),
        ("blink", "Blink / blink-adjacent fixations", None),
    ):
        _render_fixclass_category(
            prefix,
            label,
            threshold_label=threshold,
            disabled=disabled,
            reason=reason,
        )


def _collect_fixation_flags() -> dict:
    """Build the ``fixation_flags`` dict the figure builder consumes from the
    ``global_fixclass_*`` session keys (PRE-2). One entry per category; ``oob`` has
    no threshold."""
    ss = st.session_state
    return {
        "short": {
            "mode": ss.get("global_fixclass_short_mode", "Off"),
            "threshold_ms": float(ss.get("global_fixclass_short_threshold_ms") or 80),
            "symbol": ss.get("global_fixclass_short_symbol") or "triangle-up-open",
            "color": ss.get("global_fixclass_short_color") or "#ff7f0e",
        },
        "long": {
            "mode": ss.get("global_fixclass_long_mode", "Off"),
            "threshold_ms": float(ss.get("global_fixclass_long_threshold_ms") or 800),
            "symbol": ss.get("global_fixclass_long_symbol") or "square-open",
            "color": ss.get("global_fixclass_long_color") or "#9467bd",
        },
        "oob": {
            "mode": ss.get("global_fixclass_oob_mode", "Off"),
            "symbol": ss.get("global_fixclass_oob_symbol") or "x",
            "color": ss.get("global_fixclass_oob_color") or OUT_OF_TEXT_COLOR,
        },
        "blink": {
            "mode": ss.get("global_fixclass_blink_mode", "Off"),
            "symbol": ss.get("global_fixclass_blink_symbol") or "diamond-open",
            "color": ss.get("global_fixclass_blink_color") or "#17becf",
        },
    }


def _fixation_filter_badge() -> str:
    """Compact VIZ-27 badge summarising active visual filters."""
    active = [
        st.session_state.get(f"global_fixclass_{name}_mode", "Off")
        for name in ("short", "long", "oob", "blink")
    ]
    n_active = sum(mode != "Off" for mode in active)
    n_discard = sum(mode == "Discard" for mode in active)
    if not n_active:
        return ""
    detail = f"{n_active} active"
    if n_discard:
        detail += f", {n_discard} hidden"
    return f" · {detail}"


def _saccade_filter_badge() -> str:
    """Compact badge summarising the VIZ-31 saccade reading-class filter.

    Mirrors :func:`_fixation_filter_badge` — an active filter must be visible
    without opening the popover, or a figure missing half its saccades reads as
    a data problem. Empty (or a full selection) means no filter, so no badge.
    """
    selected = st.session_state.get("global_saccade_classes")
    if not selected:
        return ""
    hidden = [cls for cls in SACCADE_CLASS_ORDER if cls not in set(selected)]
    if not hidden:
        return ""
    if len(hidden) == len(SACCADE_CLASS_ORDER) - 1:
        # One class left standing — name it; "5 hidden" says much less than
        # "regression only" when that is the whole point of the figure.
        kept = next(c for c in SACCADE_CLASS_ORDER if c not in set(hidden))
        return f" · {SACCADE_CLASS_LABELS[kept].lower()} only"
    return f" · {len(hidden)} hidden"


# Quick-view presets: one click sets the *layer* toggles to a focused subset, so
# a user lands on a legible picture instead of toggling layers one by one. The
# Illustration preset also applies four presentation overrides. Those overrides
# are temporary: ``_apply_view_preset`` snapshots them on the way in and restores
# them on the way out, so Illustration → Scanpath cannot leave arc/snap/opacity
# settings behind while the button says Scanpath. Other per-layer styling
# (colours, sizes, colorscales) remains untouched.
_ILLUSTRATION_OVERRIDE_KEYS = (
    "global_saccade_render_mode",
    "global_fixation_snap_to_word",
    "global_saccade_color_mode",
    "global_fixation_opacity",
)
_PRE_ILLUSTRATION_STATE = "_quick_view_pre_illustration"

_VIEW_PRESETS: dict[str, dict[str, object]] = {
    "scanpath": {
        "global_show_fix": True,
        "global_show_saccades": True,
        "global_show_saccade_arrows": False,
        "global_show_labels": True,
        "global_show_order": False,
        "global_show_heatmap": False,
        "global_show_words": False,
        "global_show_raw_gaze": False,
    },
    "heatmap": {
        "global_show_heatmap": True,
        "global_show_labels": True,
        "global_show_fix": False,
        "global_show_saccades": False,
        "global_show_order": False,
        "global_show_words": False,
        "global_show_raw_gaze": False,
    },
    "illustration": {
        "global_show_fix": True,
        "global_show_saccades": True,
        "global_show_saccade_arrows": False,
        "global_show_labels": True,
        "global_show_order": False,
        "global_show_heatmap": False,
        "global_show_words": False,
        "global_show_raw_gaze": False,
        "global_saccade_render_mode": "Arc",
        "global_fixation_snap_to_word": True,
        "global_saccade_color_mode": "Uniform",
        "global_fixation_opacity": 1.0,
    },
    "reading_order": {
        "global_show_fix": True,
        "global_show_order": True,
        "global_show_saccades": True,
        "global_show_saccade_arrows": True,
        "global_show_labels": True,
        "global_show_heatmap": False,
        "global_show_words": False,
        "global_show_raw_gaze": False,
    },
    "everything": {
        "global_show_words": True,
        "global_show_labels": True,
        "global_show_fix": True,
        "global_show_saccades": True,
        "global_show_saccade_arrows": True,
        "global_show_heatmap": True,
        "global_show_order": False,
        "global_show_raw_gaze": False,
    },
}


def _apply_view_preset(name: str) -> None:
    """Apply a Quick-view preset and keep Illustration overrides reversible.

    Runs as a button ``on_click`` callback, i.e. *before* the next rerun
    instantiates the layer checkboxes — so writing their ``global_show_*`` keys
    here is picked up cleanly (no "set after widget instantiated" warning).

    Illustration owns four style/geometry values that ordinary quick views do
    not. Preserve their incoming values once, then restore each value that is
    still carrying Illustration's override when another preset is selected. A
    value edited explicitly while Illustration is active is therefore retained.
    """
    if name not in _VIEW_PRESETS:
        raise ValueError(f"Unknown quick-view preset: {name}")

    ss = st.session_state
    illustration = _VIEW_PRESETS["illustration"]
    was_illustration = all(ss.get(key) == value for key, value in illustration.items())
    if name == "illustration":
        if _PRE_ILLUSTRATION_STATE not in ss:
            ss[_PRE_ILLUSTRATION_STATE] = {
                key: (
                    _VIZ_WIDGET_DEFAULTS[key]
                    if was_illustration
                    else ss.get(key, _VIZ_WIDGET_DEFAULTS[key])
                )
                for key in _ILLUSTRATION_OVERRIDE_KEYS
            }
    else:
        previous = ss.pop(_PRE_ILLUSTRATION_STATE, None)
        # A saved config, deep link, or hot-reloaded session can enter on the
        # Illustration values without ever running the callback that captures a
        # snapshot. Falling back to the ordinary defaults still makes the exit
        # deterministic instead of leaving Illustration geometry behind.
        if previous is None and was_illustration:
            previous = {
                key: _VIZ_WIDGET_DEFAULTS[key] for key in _ILLUSTRATION_OVERRIDE_KEYS
            }
        if previous is not None:
            for key in _ILLUSTRATION_OVERRIDE_KEYS:
                # Do not overwrite an explicit edit made after Illustration was
                # applied; only undo the value the preset itself still owns.
                if ss.get(key) == illustration[key]:
                    ss[key] = previous.get(key, _VIZ_WIDGET_DEFAULTS[key])

    for key, value in _VIEW_PRESETS[name].items():
        ss[key] = value


def _active_quick_view() -> str | None:
    """Return the quick-view preset whose owned values match current state.

    Illustration is deliberately checked before Scanpath: its layer set is a
    superset of the Scanpath contract, so the old order mislabeled an active
    Illustration as Scanpath even while arc-and-snap geometry remained live.
    """
    ss = st.session_state
    for name in ("illustration", "scanpath", "heatmap"):
        if all(ss.get(k) == v for k, v in _VIEW_PRESETS[name].items()):
            return name
    return None


# VIZ-18: palette setting name → the session key it writes. A palette is applied
# by writing the *ordinary* colour keys, so nothing downstream has to know
# palettes exist — the per-element pickers, the deep link, Save & restore, the
# CLI and the API all keep carrying plain colours.
_PALETTE_STATE_KEYS = {
    "fixation_color": "global_fixation_color",
    "fixation_colorscale": "global_fixation_colorscale",
    "heatmap_colorscale": "global_heatmap_colorscale",
    "saccade_color": "global_saccade_color",
    "word_label_color": "global_text_color",
    "highlight_text_color": "global_highlight_text_color",
}


def palette_state(name: str) -> dict:
    """The ``session_state`` writes that applying palette ``name`` performs."""
    settings = palette_settings(name)
    state = {
        state_key: settings[setting]
        for setting, state_key in _PALETTE_STATE_KEYS.items()
        if setting in settings
    }
    for cls_name, color in settings.get("saccade_class_colors", {}).items():
        if cls_name in SACCADE_CLASS_EDITABLE:
            state[f"global_saccade_class_color_{cls_name}"] = color
    return state


def apply_palette(name: str) -> None:
    """Apply a VIZ-18 palette by writing its colours into ``session_state``.

    Runs as a widget ``on_change`` callback — i.e. before the next rerun
    instantiates the colour pickers — so writing their keys here is picked up
    cleanly, exactly like ``_apply_view_preset``. Deliberately does *not* touch
    the background colour: that's a canvas/Experimental-Setup choice the user
    makes for their output medium, not part of the mark palette.

    ``CUSTOM_PALETTE`` is a no-op: it names the *absence* of a palette, so
    re-selecting it must not overwrite the colours the user just set by hand.
    """
    if name == CUSTOM_PALETTE:
        return
    for key, value in palette_state(name).items():
        st.session_state[key] = value


def _palette_match_key(value):
    """Normalize a colour for comparison — the pickers hand back lowercase hex."""
    return value.lower() if isinstance(value, str) and value.startswith("#") else value


def _active_palette() -> str | None:
    """Which palette the live colour keys match, or ``None`` once customized.

    The VIZ-12 rule applied to VIZ-18: a palette is one-way (it writes the
    ordinary colour keys and never reads them back), so without this the selector
    keeps reading "Colourblind-safe" after the user has hand-edited one of its
    colours — naming a property the figure no longer has.
    """
    ss = st.session_state
    for name in PALETTES:
        wanted = palette_state(name)
        if all(
            _palette_match_key(ss.get(key)) == _palette_match_key(value)
            for key, value in wanted.items()
        ):
            return name
    return None


def _on_palette_change() -> None:
    name = st.session_state.get("global_palette") or DEFAULT_PALETTE
    if name != CUSTOM_PALETTE:
        # What "Custom" is a departure *from*, for the caption below.
        st.session_state["_palette_picked"] = name
    apply_palette(name)


def _popover_selectbox(label: str, options: list, state_key: str, host=None, **kwargs):
    """A selectbox inside a popover whose seeded session value actually shows.

    A *keyed* selectbox first painted inside a (closed-until-clicked) popover
    renders its first option rather than the value seeded into session state, and
    commits that wrong value on the next interaction — the same first-open quirk
    the VIZ-8 class colour pickers hit. Passing an explicit ``index=`` and writing
    the pick back by hand sidesteps it, which is what lets a VIZ-18 palette (or a
    deep link, or a restored config) set a non-first colorscale and have the
    picker agree with the figure.

    Renders as a UX-51 ``label | field`` row like every other rail control.
    """
    current = st.session_state.get(state_key)
    index = options.index(current) if current in options else 0
    picked = _labeled(
        host if host is not None else st,
        "selectbox",
        label,
        options=options,
        index=index,
        **kwargs,
    )
    st.session_state[state_key] = picked
    return picked


# Help text for the (multi-capable) Trial ID mapping, shared by all tables.
_TRIAL_MAPPING_HELP = (
    "Pick the column holding your unique trial ID — or pick SEVERAL columns "
    "to build one on the fly (values joined with '_'), e.g. participant + "
    "paragraph + repeated-reading when no single column identifies a trial. "
    "Use the same columns for every uploaded table so trials line up."
)

# Word-box geometry is one rectangle in two interchangeable encodings. The
# mapping UI shows a format picker plus four fields instead of all eight at once;
# both encodings normalize to canonical x/y/width/height in
# ``data.normalize_words``, so the returned schema still carries all eight keys.
BOX_FORMAT_EDGES = "Edges"
BOX_FORMAT_ORIGIN = "Origin + size"
_BOX_SUBFIELDS: dict[str, list[tuple]] = {
    BOX_FORMAT_EDGES: [
        ("left", "Box left"),
        ("right", "Box right"),
        ("top", "Box top"),
        ("bottom", "Box bottom"),
    ],
    BOX_FORMAT_ORIGIN: [
        ("x", "Box x (top-left)"),
        ("y", "Box y (top-left)"),
        ("width", "Box width"),
        ("height", "Box height"),
    ],
}
_ALL_BOX_KEYS = [key for fields in _BOX_SUBFIELDS.values() for key, _ in fields]


def _default_box_format(proposed: dict[str, str | None]) -> str:
    """Which box encoding to show first, from what auto-detect found.

    Edges if all four edge columns were detected, else origin+size if those four
    were, else edges."""
    if all(proposed.get(k) for k in ("left", "right", "top", "bottom")):
        return BOX_FORMAT_EDGES
    if all(proposed.get(k) for k in ("x", "y", "width", "height")):
        return BOX_FORMAT_ORIGIN
    return BOX_FORMAT_EDGES


# UX-52: mapping fields that only a **multipart** dataset needs (one logical
# trial spread over several screens, DATA-21/DATA-24) plus the per-screen canvas
# size. All optional, all inert for an ordinary single-screen corpus, and
# together they were half the rows in the editor — so they fold into an
# "Advanced" group instead of padding the list everyone reads.
_ADVANCED_MAPPING_KEYS = frozenset({"screen_id", "screen_index"})

#: Mapping keys that are **resolved but never rendered** (UX-53 round 3).
#:
#: `screen_fixation_id` and the two `canvas_*` fields are per-screen bookkeeping
#: that only a multipart export carries, and when it does carry them the column
#: names are the canonical ones auto-detection already finds. They were three
#: more rows on a page whose complaint was length, offering a choice nobody
#: makes. `_assemble_mapping` still puts them in the schema straight from the
#: proposal, so multipart datasets keep their per-screen canvas and nothing
#: downstream sees a narrower schema — what is gone is the widget, not the
#: field. Anything genuinely unmappable this way is a column-name problem, and
#: `data.py`'s candidate lists are where that gets fixed.
_HIDDEN_MAPPING_KEYS = frozenset(
    {"screen_fixation_id", "canvas_width", "canvas_height"}
)

WORD_FIELD_SPECS: list[dict] = [
    {
        "key": "participant",
        "label": "Participant ID",
        "required": False,
        "help": "Which reader produced this row. Splits scanpaths per "
        "participant; omit for stimulus-level word boxes shared across all readers.",
    },
    {
        "key": "trial",
        "label": "Trial ID",
        "required": True,
        "multi": True,
        "help": _TRIAL_MAPPING_HELP,
    },
    {
        "key": "screen_id",
        "label": "Screen / part ID",
        "required": False,
        "help": "Child screen inside a logical trial. Leave empty for ordinary "
        "single-screen trials.",
    },
    {
        "key": "screen_index",
        "label": "Screen order",
        "required": False,
        "help": "Positive 1-based screen order inside the parent trial. If only a "
        "screen ID is mapped, order follows first appearance.",
    },
    {
        "key": "word_id",
        "label": "Word/IA ID",
        "required": True,
        "help": "Identifier of each word / interest-area — the key fixations "
        "attach to, and the order of words within a trial.",
    },
    {
        "key": "text",
        "label": "Word text/label",
        "required": False,
        "help": "The word's text; drawn on the stimulus and shown in tooltips.",
    },
    {
        "key": "text_id",
        "label": "Text ID",
        "required": False,
        "help": "Groups words by the text/passage they belong to, for filtering "
        "and selection; falls back to the trial id.",
    },
    {
        "key": "line",
        "label": "Line index",
        "required": False,
        "help": "Line number of the word on screen; used for color-by-line "
        "(otherwise inferred from box Y).",
    },
    {
        "key": "canvas_width",
        "label": "Screen canvas width",
        "required": False,
        "help": "Recorded canvas width in pixels; must be constant within a screen.",
    },
    {
        "key": "canvas_height",
        "label": "Screen canvas height",
        "required": False,
        "help": "Recorded canvas height in pixels; must be constant within a screen.",
    },
    {
        "key": "box",
        "kind": "box",
        "label": "Word box",
        "required": True,
        "help": "Bounding box per word/AOI. Edges = left/right/top/bottom (EyeLink IA_*); origin+size = x/y/width/height.",
    },
]

FIX_FIELD_SPECS: list[dict] = [
    {
        "key": "participant",
        "label": "Participant ID",
        "required": True,
        "help": "Which reader produced this fixation. Splits scanpaths per participant.",
    },
    {
        "key": "trial",
        "label": "Trial ID",
        "required": True,
        "multi": True,
        "help": _TRIAL_MAPPING_HELP,
    },
    {
        "key": "screen_id",
        "label": "Screen / part ID",
        "required": False,
        "help": "Child screen inside a logical trial. Map this in both reports.",
    },
    {
        "key": "screen_index",
        "label": "Screen order",
        "required": False,
        "help": "Positive 1-based screen order inside the parent trial.",
    },
    {
        "key": "x",
        "label": "X coordinate",
        "required": False,
        "help": "Fixation pixel X. Leave empty for AOI-only data and map "
        "Word/IA ID instead — those fixations are placed at word-box centers.",
    },
    {
        "key": "y",
        "label": "Y coordinate",
        "required": False,
        "help": "Fixation pixel Y. Leave empty for AOI-only data (map Word/IA ID instead).",
    },
    {
        "key": "duration",
        "label": "Duration (ms)",
        "required": True,
        "help": "Fixation length in milliseconds; drives marker size and "
        "dwell-time / reading measures.",
    },
    {
        "key": "timestamp",
        "label": "Timestamp (ms)",
        "required": False,
        "help": "Parent-trial fixation onset (ms); orders the full trial and drives "
        "animation. Defaults to row order.",
    },
    # UX-53 removed *Screen-local timestamp (ms)* from the mapping: it was a
    # second clock for the same fixations, and the parent-trial timestamp above
    # already orders every screen. `screen_timestamp_ms` survives as a
    # passthrough column for the corpora that ship one (datasets.py stamps it),
    # so nothing downstream loses it — it just stops being a question every
    # uploader has to answer.
    {
        "key": "fixation_id",
        "label": "Fixation ID",
        "required": False,
        "help": "Sequential fixation number within a trial. Defaults to row order.",
    },
    {
        "key": "screen_fixation_id",
        "label": "Screen-local fixation ID",
        "required": False,
        "help": "Optional fixation number that resets within each screen; the "
        "parent-global fixation ID is retained separately.",
    },
    {
        "key": "text_id",
        "label": "Text ID",
        "required": False,
        "help": "Groups fixations by the text/passage they belong to, for "
        "filtering and selection.",
    },
    {
        "key": "word_id",
        "label": "Word/IA ID",
        "required": False,
        "help": "Which word/AOI each fixation landed on. Authoritative when "
        "present (overrides geometric assignment), and supplies the location "
        "when X/Y are absent — for AOI-only data, leave X/Y empty and map this.",
    },
    {
        "key": "canvas_width",
        "label": "Screen canvas width",
        "required": False,
        "help": "Recorded canvas width in pixels; must be constant within a screen.",
    },
    {
        "key": "canvas_height",
        "label": "Screen canvas height",
        "required": False,
        "help": "Recorded canvas height in pixels; must be constant within a screen.",
    },
    # pass_index / saccade_type / saccade_amplitude / eye are no longer explicit
    # mapping fields — they're auto-detected and offered under "fields to keep"
    # (see data.FIX_OPTIONAL_FIELDS), so they don't clutter the wizard and aren't
    # hardcoded as schema. noise_flag was removed (it silently dropped fixations
    # with no UI to undo); saccade_amplitude is recomputed from X/Y by measures.
]

RAW_GAZE_FIELD_SPECS: list[dict] = [
    {
        "key": "participant",
        "label": "Participant ID",
        "required": True,
        "help": "Which reader produced this gaze sample.",
    },
    {
        "key": "trial",
        "label": "Trial ID",
        "required": True,
        "multi": True,
        "help": _TRIAL_MAPPING_HELP,
    },
    {
        "key": "screen_id",
        "label": "Screen / part ID",
        "required": False,
        "help": "Child screen inside a logical trial.",
    },
    {
        "key": "screen_index",
        "label": "Screen order",
        "required": False,
        "help": "Positive 1-based order inside the parent trial.",
    },
    {
        "key": "x",
        "label": "X coordinate",
        "required": True,
        "help": "Gaze pixel X at this timepoint.",
    },
    {
        "key": "y",
        "label": "Y coordinate",
        "required": True,
        "help": "Gaze pixel Y at this timepoint.",
    },
    {
        "key": "timestamp",
        "label": "Timestamp (ms)",
        "required": False,
        "help": "Sample time (ms); orders the continuous gaze path. "
        "Defaults to row order.",
    },
    {
        "key": "text",
        "label": "Word text/label",
        "required": False,
        "help": "Optional word/label associated with the sample.",
    },
]


def _assemble_mapping(
    df: pd.DataFrame,
    field_specs: list[dict],
    proposed: dict[str, str | None],
    only_keys: list[str] | None,
    *,
    pick: Callable[..., str | None],
    pick_box_format: Callable[[dict], str],
    pick_multi: Callable[..., list[str]],
) -> dict[str, str | None]:
    """Build the schema dict, deferring every *choice* to the caller.

    The **shape** of a mapping — which keys exist, that a ``kind: "box"`` field
    expands into all eight box keys with the inactive four set to ``None``, that
    a ``multi`` field collapses to a plain string when exactly one column is
    picked — is defined once, here. :func:`column_mapping_ui` supplies choices by
    rendering widgets; :func:`resolve_column_mapping` supplies them by reading the
    session keys those widgets wrote. Sharing the loop is what stops the two
    answering differently for the same dataset (DATA-26): the resolver runs on
    every view where the editor is *not* on screen, so a divergence would show up
    as the app quietly normalizing under a different mapping than the one the
    user can see.
    """
    mapping: dict[str, str | None] = {}
    for spec in field_specs:
        key = spec["key"]
        # When ``only_keys`` is given, handle just that subset (the wizard
        # renders fields in grouped, ordered steps).
        if only_keys is not None and key not in only_keys:
            continue
        default = proposed.get(key)
        # Resolved from auto-detection, never offered as a row (UX-53). Both
        # callers share this loop, so the editor and the resolver stay in
        # agreement — the whole reason `_assemble_mapping` exists.
        if key in _HIDDEN_MAPPING_KEYS:
            mapping[key] = default
            continue
        label = spec["label"] + (" *" if spec.get("required") else "")
        if spec.get("kind") == "box":
            fmt = pick_box_format(spec)
            # Always emit all eight box keys; only the active format's four
            # get a column, the rest stay None.
            mapping.update({box_key: None for box_key in _ALL_BOX_KEYS})
            for sub_key, sub_label in _BOX_SUBFIELDS[fmt]:
                mapping[sub_key] = pick(sub_key, sub_label, None)
            continue
        if spec.get("multi"):
            chosen_cols = pick_multi(spec, default, label)
            if not chosen_cols:
                mapping[key] = None
            elif len(chosen_cols) == 1:
                mapping[key] = chosen_cols[0]
            else:
                mapping[key] = list(chosen_cols)
            continue
        mapping[key] = pick(key, label, spec.get("help"))
    return mapping


#: Set once the user has pressed **✅ Add dataset** on a wizard that still has a
#: required field unmapped. Until then a blank required field is simply *not
#: filled in yet* — colouring it red on arrival would paint a fresh upload with
#: errors before the user has done anything wrong (UX-53).
ADD_ATTEMPTED_KEY = "_wizard_add_attempted"

#: UX-53 round 4 — the field's state is a **tint on the select itself**, not a
#: dot and a sentence beside it. `● ✨ auto-detected \`CURRENT_FIX_INDEX\`` was
#: longer than the control it described, on every row. Low-alpha rgba so it
#: tints whatever the active theme paints underneath rather than assuming a
#: light background.
_FIELD_TINT = {
    "user": "rgba(34, 197, 94, 0.16)",
    "auto": "rgba(234, 179, 8, 0.16)",
    "missing": "rgba(239, 68, 68, 0.20)",
}


def _field_state(
    *, chosen, default, is_required: bool, attempted: bool, detected_label: str
) -> tuple[str, str]:
    """``(state, hover)`` for one mapping row.

    ``state`` keys `_FIELD_TINT`: **user** picked it, **auto** detection found it
    and it was left alone, **missing** it is required and still empty *after* an
    add was attempted (before that, empty is simply not filled in yet). ``""``
    for an optional empty field — most rows on most datasets, and tinting all of
    them would say nothing.

    ``hover`` is the ✨ icon's tooltip, and it is the only place the detected
    column name is now written: the name is what made the old inline note run
    past the width of the control it annotated, and it is looked at once.
    """
    unmapped = chosen in (None, NONE_OPTION)
    if unmapped:
        if is_required and attempted:
            return "missing", "required — pick a column"
        if default:
            return "auto", f"{detected_label} `{default}` · not used"
        return "", ""
    if default and chosen == default:
        return "auto", f"{detected_label} `{default}`"
    if default:
        return "user", f"{detected_label} `{default}` · overridden"
    return "user", ""


#: Marker key recording which table a stored mapping was made for.
#:
#: The prefix, not a suffix, and deliberately outside ``col_map_*``:
#: `tabs._collect_column_mapping` sweeps **every** `col_map_*` key that does not
#: end in `_upload` into the saved config, so a marker named
#: ``col_map_fix__mapped_columns`` would travel in one — come back from JSON as a
#: *list* rather than the tuple it was written as, never compare equal to the
#: signature again, and so clear the mapping on the first run after every
#: restore. It describes this session's widget state, not the mapping, and has
#: no business in a file that opens on another machine.
def _mapped_columns_key(state_key_prefix: str) -> str:
    """Session key holding the column signature ``state_key_prefix`` maps."""
    return f"_mapped_columns_{state_key_prefix}"


def _mapping_state_keys(state_key_prefix: str, field_specs: list[dict]) -> list[str]:
    """Every session key the mapping widgets for ``field_specs`` write."""
    keys: list[str] = []
    for spec in field_specs:
        if spec.get("kind") == "box":
            keys.append(f"{state_key_prefix}_box_format")
            keys.extend(f"{state_key_prefix}_{box_key}" for box_key in _ALL_BOX_KEYS)
            continue
        keys.append(f"{state_key_prefix}_{spec['key']}")
    return keys


def forget_mapping_for_other_table(
    df: pd.DataFrame, state_key_prefix: str, field_specs: list[dict]
) -> None:
    """Drop a stored mapping that was made for a *different* table (DATA-24).

    A mapping widget owns its key once it has rendered, and a key that exists
    beats the ``index=`` computed from auto-detection — that is what makes a
    user's override stick. But the app switches data sources in place, so the
    same keys outlive the table they describe: opening the bundled demo (no
    screen columns → *Screen order* = ``(none)``) and then switching to
    MultiplEYE left *Screen order* on ``(none)`` while the caption beneath it
    still read "✨ auto-detected `screen_index`", because the proposal had indeed
    found the column and only the widget was stale. The multipart trial then
    ordered its screens by name instead of by reading order, and the user had to
    set a field the app had already detected.

    The discriminator is the **column universe**, not the data: a new file with
    the same headers is the case where keeping the mapping is the whole point,
    while different headers mean this mapping was never about this table. The
    first sighting of a prefix only *records* the signature — it must not clear,
    or it would wipe the ``col_map_*`` keys a deep link or a restored config
    seeds before any widget renders (``url_state._seed_column_mapping``).

    Even then it clears only what has gone stale — a pick naming a column the new
    table still has survives. That is not tidiness: the wizard *grows* its own
    frame mid-flow (``_wizard_filename_derive`` appends ``file_part_N``), so a
    signature change is routine there and dropping the whole mapping would reset
    steps the user had already filled in. What gets cleared is a field left at
    ``(none)`` or pointing at a column that is gone — in both cases there is no
    user choice to lose, and auto-detection deserves another go.
    """
    signature = tuple(str(column) for column in df.columns)
    marker = _mapped_columns_key(state_key_prefix)
    previous = st.session_state.get(marker)
    st.session_state[marker] = signature
    if previous is None or previous == signature:
        return
    columns = set(signature)
    for key in _mapping_state_keys(state_key_prefix, field_specs):
        stored = st.session_state.get(key)
        if isinstance(stored, str) and stored != NONE_OPTION and stored in columns:
            continue
        # The multi-capable Trial ID. Keep a composite whose every component
        # survived; a partial one is not a mapping the user can have meant.
        if (
            isinstance(stored, (list, tuple))
            and stored
            and all(column in columns for column in stored)
        ):
            continue
        # The box *format* is a property of the table (which four columns it
        # has), not a preference, so it is re-derived from the new proposal.
        st.session_state.pop(key, None)


def resolve_column_mapping(
    df: pd.DataFrame,
    state_key_prefix: str,
    field_specs: list[dict],
    proposed: dict[str, str | None],
    only_keys: list[str] | None = None,
) -> dict[str, str | None]:
    """The mapping :func:`column_mapping_ui` *would* return, without rendering it.

    **DATA-26.** The column-mapping editor used to live in a menu popover, which
    executes on every rerun, so the load path could simply render it and use what
    came back. On the **Data** page it executes only while that page is the
    active view — and the mapping still has to drive ``prepare_data`` on the
    Scanpath and Corpus views, which is precisely the trap that item flags.

    Both halves of the answer are needed. The widgets carry
    ``persist_state="session"`` so Streamlit keeps their values through the runs
    in which they don't render (ENG-36; without it the keys are dropped at the
    end of any such run and the mapping silently reverts to auto-detection).
    This function then reads those values instead of re-rendering, so no view has
    to draw the editor just to know the answer.

    A stored column that no longer exists in ``df`` — a new upload with different
    headers — falls back to the auto-detected proposal rather than to ``None``,
    matching the rendering editor, whose selectbox ``index`` lookup self-heals the
    same way.
    """
    forget_mapping_for_other_table(df, state_key_prefix, field_specs)
    columns = set(df.columns)

    def _stored(field_key: str) -> str | None:
        value = st.session_state.get(f"{state_key_prefix}_{field_key}")
        if value == NONE_OPTION:
            return None
        if isinstance(value, str) and value in columns:
            return value
        # Nothing usable stored: fall back to what auto-detection proposed.
        fallback = proposed.get(field_key)
        return fallback if fallback in columns else None

    def _pick(field_key: str, _label, _help=None) -> str | None:
        return _stored(field_key)

    def _pick_box_format(_spec) -> str:
        fmt = st.session_state.get(f"{state_key_prefix}_box_format")
        return fmt if fmt in _BOX_SUBFIELDS else _default_box_format(proposed)

    def _pick_multi(spec, default, _label) -> list[str]:
        stored = st.session_state.get(f"{state_key_prefix}_{spec['key']}")
        if isinstance(stored, (list, tuple)):
            valid = [c for c in stored if c in columns]
            if valid:
                return valid
        return [default] if default in columns else []

    return _assemble_mapping(
        df,
        field_specs,
        proposed,
        only_keys,
        pick=_pick,
        pick_box_format=_pick_box_format,
        pick_multi=_pick_multi,
    )


def column_mapping_ui(
    df: pd.DataFrame,
    table_label: str,
    state_key_prefix: str,
    field_specs: list[dict],
    proposed: dict[str, str | None],
    expand_on_problem: bool = True,
    problems: list[str] | None = None,
    container=None,
    use_expander: bool = True,
    only_keys: list[str] | None = None,
    header: bool = True,
    detected_label: str = "auto-detected",
) -> dict[str, str | None]:
    """Render a column-mapping expander letting users override the inferred mapping.

    Renders in the sidebar by default; pass ``container`` (e.g. a main-area
    container from the setup wizard) to render it there instead.

    Returns a mapping {field_key: column_name_or_None}. Fields marked
    ``multi: True`` (Trial ID) render as a multiselect: picking several columns
    yields a list, meaning "build this ID on the fly by joining the columns'
    values" (see ``data.trial_id_series``); a single pick stays a plain string.
    A field marked ``kind: "box"`` (the word box) renders a coordinate-format
    radio plus the four sub-fields for that format, and expands into all eight
    box keys (the four inactive ones set to None) so the returned schema keeps
    its fixed shape.
    """
    forget_mapping_for_other_table(df, state_key_prefix, field_specs)
    options = [NONE_OPTION] + list(df.columns)
    expanded = bool(expand_on_problem and problems)
    # UX-53 field colour: which rows *must* be filled, and whether the user has
    # already tried to add the dataset (before that, empty is not an error).
    required_keys = {spec["key"] for spec in field_specs if spec.get("required")}
    add_attempted = bool(st.session_state.get(ADD_ATTEMPTED_KEY))
    #: state -> the keyed cells in that state, filled as rows render and emitted
    #: as ONE <style> block at the end. Per-row style tags would be one extra
    #: element per field on a page whose whole problem is length.
    tint_cells: dict[str, list[str]] = {}
    # UX-52 round 2 — "the column mapping can be overwhelming". Two changes:
    # every row is `label | field` (UX-51's shape, which the user asked for here
    # too), and the multipart/canvas fields fold into an **Advanced** group.
    # They are all optional, all meaningless for an ordinary single-screen
    # dataset, and they were half the rows. The group is skipped when the caller
    # asks for a subset (`only_keys`) — that is the wizard, which already groups
    # these fields into its own ordered steps (DATA-22).
    group_advanced = only_keys is None
    hosts: dict[str, object] = {}

    def _host_for(field_key: str):
        """The container a field's row renders into (main, or Advanced)."""
        if group_advanced and field_key in _ADVANCED_MAPPING_KEYS:
            return hosts.get("advanced") or hosts["main"]
        return hosts["main"]

    def _row(field_key: str, field_label: str, help_text):
        """A `label | field | note` triple; returns the field and note columns.

        UX-52 round 3 — the "✨ auto-detected …" caption used to sit *under* the
        control, so every row was two lines tall while the right half of a
        full-width page sat empty. It now rides in a third column beside the
        field: same information, half the vertical space.
        """
        host = _host_for(field_key)
        label_col, field_col, note_col = host.columns(
            _MAPPING_ROW_W, gap=_LABEL_GAP, vertical_alignment="center"
        )
        _row_label(label_col, field_label, help_text)
        return field_col, note_col

    def _selectbox(field_key: str, field_label: str, help_text=None) -> str | None:
        default = proposed.get(field_key)
        index = options.index(default) if default in options else 0
        field_col, note_col = _row(field_key, field_label, help_text)
        # The select goes in its own keyed container so the state tint has
        # something to attach to: Streamlit stamps `.st-key-<key>` on it, and the
        # one <style> block emitted at the end of this mapping lists the cells
        # per state (see `tint_cells`).
        cell_key = f"{state_key_prefix}_{field_key}_cell"
        field_col = field_col.container(key=cell_key)
        chosen = field_col.selectbox(
            field_label,
            options=options,
            index=index,
            key=f"{state_key_prefix}_{field_key}",
            help=help_text,
            label_visibility="collapsed",
            # DATA-26: the editor lives on the Data page, which executes only
            # while it is the active view — but the mapping drives `prepare_data`
            # on every view. Without this, Streamlit drops the key at the end of
            # any run in which the widget did not render and the mapping reverts
            # to auto-detection the moment the user clicks over to Scanpath.
            persist_state="session",
        )
        # Surface what auto-detection found for this field (ENG-9), flag when the
        # user has overridden it, and carry UX-53's colour so the row's state is
        # readable without parsing the sentence. DATA-24: `(none)` gets its own
        # wording — it used to fall into the plain branch, so a field detection
        # had found but the widget was not using read exactly like one it was.
        state, hover = _field_state(
            chosen=chosen,
            default=default if default in df.columns else None,
            is_required=field_key in required_keys,
            attempted=add_attempted,
            detected_label=detected_label,
        )
        if state:
            tint_cells.setdefault(state, []).append(cell_key)
        if hover:
            # Icon only. The sentence — which column was detected, and whether it
            # was overridden or left unused — is on the icon's tooltip, reusing
            # the rail's CSS hover (`.sps-fhelp`, 120ms) rather than the
            # browser's ~1s native one.
            note_col.markdown(
                f'<span class="sps-map-flag sps-fhelp" '
                f'data-tip="{html.escape(hover, quote=True)}">✨</span>',
                unsafe_allow_html=True,
            )
        return None if chosen == NONE_OPTION else chosen

    host = container if container is not None else st.container()
    # Render inside an expander by default; ``use_expander=False`` renders inline
    # (the collapsed wizard panel already lives in an expander, and the ⚙️ Configure
    # menu popover nests no expander either — Streamlit forbids both).
    section = (
        host.expander(f"Column mapping — {table_label}", expanded=expanded)
        if use_expander
        else host.container()
    )
    with section:
        if not use_expander and header:
            st.markdown(f"**Column mapping — {table_label}**")
        if header:
            st.caption(
                "Auto-detected from your CSV. Override any row if your column "
                "names differ."
            )
        if problems:
            st.warning(
                "Fix these before the app can use this table: " + "; ".join(problems)
            )
        # Both hosts are reserved up front, so the Advanced group sits *after*
        # every ordinary row no matter where its fields fall in the spec order
        # (Streamlit lays containers out in creation order, and
        # `_assemble_mapping` interleaves them).
        hosts["main"] = st.container()
        advanced_slot = st.container()
        if group_advanced and any(
            spec["key"] in _ADVANCED_MAPPING_KEYS for spec in field_specs
        ):
            # Open when the dataset actually uses one of them, so a multipart
            # corpus does not hide its screen mapping behind a fold.
            def _mapped(key: str) -> bool:
                # `NONE_OPTION` is the literal string the selectbox holds for
                # "not mapped" — truthy, so a bare `or` kept the group open
                # forever once the widgets had rendered once.
                stored = st.session_state.get(f"{state_key_prefix}_{key}")
                if stored in (None, NONE_OPTION, ""):
                    stored = None
                return bool(proposed.get(key) or stored)

            in_use = any(_mapped(key) for key in _ADVANCED_MAPPING_KEYS)
            hosts["advanced"] = advanced_slot.expander(
                "⚙️ Multipart screens & canvas — advanced", expanded=bool(in_use)
            )
            hosts["advanced"].caption(
                "Only for a dataset where one logical trial spans several "
                "screens, or that records its canvas size per screen. Leave "
                "empty otherwise."
            )

        def _render_box_format(spec: dict) -> str:
            fmt_key = f"{state_key_prefix}_box_format"
            if fmt_key not in st.session_state:
                # Seed via session state (no `index=`) so it survives reruns
                # and never fights a default arg — same pattern as the
                # multiselect below.
                st.session_state[fmt_key] = _default_box_format(proposed)
            star = " \\*" if spec.get("required") else ""
            box_host = hosts["main"]
            box_host.markdown(f"**{spec['label']}**{star}")
            if spec.get("help"):
                box_host.caption(spec["help"])
            return box_host.radio(
                "Coordinate format",
                options=list(_BOX_SUBFIELDS),
                key=fmt_key,
                horizontal=True,
                label_visibility="collapsed",
                persist_state="session",
            )

        def _render_multi(spec: dict, default, label: str) -> list[str]:
            state_key = f"{state_key_prefix}_{spec['key']}"
            proposed_default = [default] if default in df.columns else []
            stored = st.session_state.get(state_key)
            if stored is None:
                # Seed via session state instead of `default=` so the
                # stale-column reset below never fights a default arg.
                st.session_state[state_key] = proposed_default
            else:
                # A new upload changes the column universe — silently
                # keeping stale picks would leave the field empty (the
                # selectboxes self-heal via their index fallback; a
                # multiselect doesn't). Drop unknown columns and fall
                # back to the auto-proposal when nothing survives.
                valid = [c for c in stored if c in df.columns]
                if len(valid) != len(stored):
                    st.session_state[state_key] = valid or proposed_default
            field_col, note_col = _row(spec["key"], label, spec.get("help"))
            chosen_cols = field_col.multiselect(
                label,
                options=list(df.columns),
                key=state_key,
                help=spec.get("help"),
                label_visibility="collapsed",
                persist_state="session",
            )
            if default and default in df.columns:
                note_col.markdown(
                    f'<span class="sps-map-flag sps-fhelp" '
                    f'data-tip="{html.escape(f"{detected_label} `{default}`", quote=True)}">'
                    "✨</span>",
                    unsafe_allow_html=True,
                )
            return list(chosen_cols)

        mapping = _assemble_mapping(
            df,
            field_specs,
            proposed,
            only_keys,
            pick=_selectbox,
            pick_box_format=_render_box_format,
            pick_multi=_render_multi,
        )
        _emit_field_tints(tint_cells)
    return mapping


def _emit_field_tints(tint_cells: dict[str, list[str]]) -> None:
    """One <style> block tinting each mapping cell by its state (UX-53 r4).

    Written after the rows because a cell's state is only known once its widget
    has returned a value. Targets the BaseWeb select *control* rather than the
    Streamlit wrapper, so the colour lands on the box the user is looking at and
    not on the whole row.
    """
    rules = []
    for state, keys in tint_cells.items():
        tint = _FIELD_TINT.get(state)
        if not tint or not keys:
            continue
        # BaseWeb paints the control's background itself, through an emotion
        # class that outranks a plain class selector — the first cut of this
        # rule was simply never visible. `!important` on several nodes of the
        # widget is what makes it land: the outer control, its value container,
        # and the Streamlit wrapper for the case where BaseWeb's own node is
        # transparent and the colour has to come from behind it.
        selector = ", ".join(
            f'.st-key-{key} [data-baseweb="select"] > div, '
            f'.st-key-{key} [data-baseweb="select"] [data-baseweb="input"], '
            f".st-key-{key} [data-testid='stSelectbox'] > div > div"
            for key in keys
        )
        rules.append(f"{selector} {{ background-color: {tint} !important; }}")
    if rules:
        st.markdown(f"<style>{''.join(rules)}</style>", unsafe_allow_html=True)


def data_dictionary_help_text() -> str:
    return (
        "Data dictionary / expected columns:\n"
        "The app auto-detects column names from csv tables using common conventions.\n"
        "- Words/IA: tries `participant_id`/`subject_id`, `unique_trial_id`/`trial_id`/`unique_paragraph_id`, "
        "`IA_ID`/`word_id`, optional `IA_LABEL`/`text`, paragraph ids, and bounding boxes via either "
        "edges `(IA_LEFT, IA_RIGHT, IA_TOP, IA_BOTTOM)` or origin+size `(x, y, width, height)` — "
        "pick which in the *Word box* selector.\n"
        "- Fixations: tries `participant_id`/`subject_id`, `unique_trial_id`/`trial_id`/`unique_paragraph_id`, "
        "`CURRENT_FIX_DURATION`, `CURRENT_FIX_X`/`CURRENT_FIX_Y`, and optionally `CURRENT_FIX_START`, "
        "`IA_ID`, and a fixation id. X/Y are optional when `IA_ID` is mapped "
        "(AOI-only fixations are placed at word-box centers). Extra fixation "
        "columns (`pass_index`/`reread`, `saccade_type`, `saccade_amplitude`, "
        "`eye`, …) are auto-detected and offered under *fields to keep*.\n"
        "- Raw gaze (optional): millisecond-level data with `participant_id`, `trial_id`, `x`, `y`. "
        "Each row represents one timepoint.\n"
        "If your columns are named differently, after uploading expand the "
        "*Column mapping* sections in the sidebar to map each field to your column.\n"
        "No single column uniquely identifies a trial? Map *Trial ID* to several "
        "columns (e.g. participant + paragraph + repeated reading) and the app "
        "builds a combined unique trial ID on the fly.\n"
        "Multi-file datasets: upload several files at once (e.g. one per "
        "participant or text) and they're concatenated, each row tagged by its "
        "`source_file`.\n"
        "Single-report datasets: upload only a words/IA table OR only a "
        "fixations table — the missing layer is skipped. A words-only table "
        "still draws a heatmap from its pre-aggregated reading measures.\n"
        "Stimulus-level word boxes (no participant column) are shared across "
        "every participant who read that trial; fixations with a word/AoI id "
        "but no x/y are placed at the matching word-box centers.\n"
        "Only fields present in your data are used for filters, coloring, and tooltips.\n"
        "Areas of interest (word boxes) are taken from your data, not computed; "
        "fixations are tied to words by bounding-box containment with a small "
        "nearest-word fallback, and fixations outside every box are flagged out-of-text."
    )


# Field-option helpers — shared by the sidebar selectors and the plot-config
# restore path (`app._restore_plot_config`) so both agree on what's valid for
# the current data.
def color_field_options(trial_fixations: pd.DataFrame) -> list[str]:
    """Columns offered in the 'Color fixations by' selector — a preferred order
    intersected with what's present, falling back to ``['duration_ms']``."""
    preferred_color_fields = [
        "duration_ms",
        "pass_index",
        "eye",
        "saccade_type",
        "saccade_amplitude",
        # BUG-25: EyeLink's own amplitudes, in degrees, kept distinct from the
        # pixel one above (and from each other — outgoing vs incoming saccade).
        "next_saccade_amplitude_deg",
        "prev_saccade_amplitude_deg",
        "word_id",
        "timestamp_ms",
        "is_regression",
        "progression",
        "gpt2_surprisal",
        "wordfreq_frequency",
        "subtlex_frequency",
        "universal_pos",
        "ptb_pos",
    ]
    fields = [f for f in preferred_color_fields if f in trial_fixations.columns]
    fields = fields or ["duration_ms"]
    # `(uniform)` leads and is the default (VIZ-17): marker *size* already encodes
    # duration, so mapping duration to hue as well spends the colour channel on a
    # variable that's already shown. Colour-by is then an opt-in for a *second*
    # variable. "line" is likewise synthetic (not a real column): colour each
    # fixation by the text line it lands on, inferred from word geometry.
    return [UNIFORM_COLOR_FIELD] + fields + ["line"]


def hover_field_options(
    frame: pd.DataFrame | None, *, words: bool = False
) -> list[str]:
    """Scalar columns that can be added to a VIZ-26 hover tooltip."""
    if frame is None or frame.empty:
        return []
    preferred = (
        [
            "text",
            "word_id",
            "line_idx",
            "total_fixation_duration_ms",
            "first_fixation_ms",
            "first_pass_gaze_duration_ms",
            "regression_path_duration_ms",
            "n_fixations",
        ]
        if words
        else [
            "order_in_trial",
            "duration_ms",
            "word_id",
            "timestamp_ms",
            "pass_index",
            "eye",
            "saccade_type",
            "saccade_amplitude",
        ]
    )
    available = list(frame.columns)
    if words and {"x", "y", "height"} <= set(frame.columns):
        available.append("line_idx")  # geometry-derived in plots._add_word_label_trace
    result: list[str] = []
    for column in [*preferred, *available]:
        if column in available and column != "image_path" and column not in result:
            result.append(column)
    return result


def numeric_field_options(trial_fixations: pd.DataFrame) -> list[str]:
    """Numeric columns offered as X/Y axis fields."""
    return [
        col
        for col in trial_fixations.columns
        if pd.api.types.is_numeric_dtype(trial_fixations[col])
    ]


# Word columns that look like a per-word boolean flag the user might want to
# highlight on the text (the OneStop answer/distractor spans first, then any
# other boolean column).
_PREFERRED_HIGHLIGHT_FIELDS = ["is_in_aspan", "is_in_dspan"]


def highlight_column_options(words: pd.DataFrame | None) -> list[str]:
    """Boolean word columns offered in the 'Highlight words by' selector.

    The OneStop answer/distractor spans lead, followed by any other boolean
    column in the words frame. Empty when there's nothing to highlight."""
    if words is None or words.empty:
        return []
    cols = [c for c in _PREFERRED_HIGHLIGHT_FIELDS if c in words.columns]
    for col in words.columns:
        if col not in cols and pd.api.types.is_bool_dtype(words[col]):
            cols.append(col)
    return cols


def _drop_stale(state_key: str, options: list) -> None:
    """Clear a persisted selectbox value that isn't valid for the current
    ``options`` (e.g. after switching datasets, or restoring a config built on
    different data) so ``st.selectbox`` falls back to its ``index=`` default
    instead of raising."""
    if state_key in st.session_state and st.session_state[state_key] not in options:
        del st.session_state[state_key]


def _drop_stale_multi(state_key: str, options: list) -> None:
    """Keep only still-valid values in a persisted multiselect list."""
    value = st.session_state.get(state_key)
    if isinstance(value, (list, tuple)):
        filtered = [item for item in value if item in options]
        if list(value) != filtered:
            st.session_state[state_key] = filtered
    elif value is not None:
        st.session_state.pop(state_key, None)


def _clamp_range(state_key: str, lo: float, hi: float) -> None:
    """Clamp a persisted ``(min, max)`` range-slider value into ``[lo, hi]`` so a
    restored value built on different data can't fall outside the slider bounds
    and raise. Drops anything that isn't a 2-tuple."""
    val = st.session_state.get(state_key)
    if not (isinstance(val, (list, tuple)) and len(val) == 2):
        st.session_state.pop(state_key, None)
        return
    try:
        a, b = float(val[0]), float(val[1])
    except (TypeError, ValueError):
        del st.session_state[state_key]
        return
    a, b = max(lo, min(a, hi)), max(lo, min(b, hi))
    st.session_state[state_key] = (min(a, b), max(a, b))


def _clamped_pair(val, lo: float, hi: float) -> tuple | None:
    """Pure twin of ``_clamp_range``: clamp a stored ``(min, max)`` into ``[lo,
    hi]`` and return it, or ``None`` for a malformed/missing value — WITHOUT
    touching session_state. Used by ``_collect_viz_settings`` (the non-rendering
    reader) so a colour range stored on differently-scaled data is clamped the
    same way the rendered slider clamps it, instead of leaking out-of-bounds into
    the Corpus / Save-&-restore figures."""
    if not (isinstance(val, (list, tuple)) and len(val) == 2):
        return None
    try:
        a, b = float(val[0]), float(val[1])
    except (TypeError, ValueError):
        return None
    a, b = max(lo, min(a, hi)), max(lo, min(b, hi))
    return (min(a, b), max(a, b))


_COMPARE_SCANPATHS = ((0, "Scanpath 1"), (1, "Scanpath 2"))


def render_pattern_help(host, fields: dict) -> None:
    """The one place the ``{field}`` vocabulary is spelled out (UX-31).

    Three surfaces speak this little language — the figure title/caption, the
    Compare A/B legend labels, and the bulk-export file-naming pattern — and two
    of them used to describe it only as "same fields as the other one", so a user
    who had seen neither had no way to learn that ``{participant_id}`` was even a
    thing. Rendered as a collapsed expander: it is reference material, not a
    control, and the rail is narrow.
    """
    if not fields:
        return
    with host.expander("Available fields", expanded=False):
        st.markdown(
            "Type any of these in a pattern and the trial's own value is "
            "substituted:\n\n"
            + "\n".join(f"- `{{{name}}}`" for name in sorted(fields))
            + "\n\nAnything else is left as literal text."
        )


def render_pattern_input(
    host,
    label: str,
    key: str,
    fields: dict,
    *,
    help: str | None = None,
    placeholder: str | None = None,
    label_left: bool = False,
) -> str:
    """A pattern text box with live validation and a rendered preview.

    Returns the pattern, or ``""`` when it names a field that does not exist —
    an invalid pattern must not reach a figure or a filename, and the error says
    which placeholder is wrong (see ``export.pattern_error``).

    ``placeholder`` is what an *empty* box falls back to, printed greyed inside
    the box itself (UX-31). These boxes default to empty — the fallback used to
    be stated only in the `help` tooltip, so the one thing you need to know
    before typing (what you get if you don't) needed a hover to find.

    Pass it **only** where an empty box really does produce that string. The
    Compare A/B labels qualify (empty → the auto ``participant · trial``); the
    figure title/caption do not (empty → no title at all), and a placeholder
    there would promise the opposite of what happens.

    ``label_left`` opts into the UX-51 ``label | field`` row (the rail's
    Title/Caption boxes). The error and the preview still span the full width
    below the row — they are the box's *output*, not a second field.
    """
    if label_left:
        _labeled(
            host,
            "text_input",
            label,
            key=key,
            persist_state="session",
            help=help,
            placeholder=placeholder,
        )
    else:
        host.text_input(
            label, key=key, persist_state="session", help=help, placeholder=placeholder
        )
    value = st.session_state.get(key, "")
    if not value:
        return ""
    error = pattern_error(value, fields)
    if error:
        host.error(error)
        return ""
    host.caption(f"{label} preview — **{render_pattern(value, fields)}**")
    return value


def _pin(key: str, default) -> None:
    """Seed ``key``'s default if it has none yet. Never overwrites.

    This is the *first value* half of the widget-state contract. The other half
    — keeping that value alive through runs where the widget doesn't render, and
    pushing it to the browser when the widget finally mounts — used to be a
    matching ``rewrite=True`` re-assertion here (BUG-15: Streamlit only sent a
    value down on the run it was written programmatically, so a control whose
    popover first opened on a *later* run mounted at its proto default — nothing
    pressed on a segmented control, black on a colour picker). Streamlit 1.61
    owns that natively: every widget on these keys passes
    ``persist_state="session"``, which preserves the value while unmounted and
    marks it as changed on remount so the frontend adopts it (ENG-36). Keep the
    kwarg when adding a widget on a ``global_*`` / ``single_*`` / ``cmp{idx}_*``
    key — it is what makes this a plain ``setdefault`` again.

    Safe only because no viz widget passes ``value=``/``index=`` (see
    ``_seed_viz_state``); adding one would fight the stored value *and* log
    Streamlit's "default value but also set via Session State API" warning.

    A **list** default is copied on the way in: ``_VIZ_WIDGET_DEFAULTS`` is a
    module-level table, so seeding a multiselect (``global_saccade_classes``)
    with the list object itself would hand session state a live alias of the
    default, and one in-place edit anywhere would change it for the rest of the
    process.
    """
    if key in st.session_state:
        return
    try:
        st.session_state[key] = list(default) if isinstance(default, list) else default
    except StreamlitAPIException:
        # The key belongs to a widget already created this run (⚙ Compare
        # options / ⚙ Playback render in tabs.py before the rail). It is already
        # carrying its value, so there is nothing to seed.
        pass


def _seed_compare_styles() -> None:
    """Seed the per-scanpath comparison styling keys (so the collected dicts have
    values even when the relevant layer popover isn't open this run).

    Seeding is all that is needed: the widgets themselves carry
    ``persist_state="session"``, which keeps the value alive through the runs
    where the popover isn't open (ENG-36)."""
    for idx, _ in _COMPARE_SCANPATHS:
        _pin(f"cmp{idx}_fix_color", compare_palette_color(idx))
        _pin(f"cmp{idx}_saccade_color", compare_palette_color(idx))
        _pin(f"cmp{idx}_saccade_style", "Solid")
        _pin(f"cmp{idx}_saccade_width", DEFAULT_SACCADE_WIDTH)
        _pin(f"cmp{idx}_marker_size_range", DEFAULT_MARKER_SIZE_RANGE)
        # VIZ-6: per-scanpath marker alpha (replaces the per-scanpath hollow
        # checkbox). Default 0.7 matches the single-trial default so overlapping
        # fixations show through. `cmp{idx}_hollow` kept seeded for saved-config /
        # deep-link backward compatibility (no widget renders it anymore).
        _pin(f"cmp{idx}_opacity", 0.7)
        _pin(f"cmp{idx}_hollow", False)


def _render_compare_fix_styles() -> None:
    """Per-scanpath *fixation* styling for the two-trial comparison — rendered
    inside the Fixation-style popover (when comparing), beside the single-trial
    fixation controls.

    UX-51: each scanpath's name is a caption over its own three rows rather than
    a prefix on every label — "Scanpath 1 — marker size range" is far too long
    for a label column that has to line up with "Opacity". The widgets keep the
    prefixed label as their accessible name (it is what tells the six rows
    apart); only the visible text is shortened."""
    st.caption("Per-scanpath (comparison)")
    for idx, name in _COMPARE_SCANPATHS:
        st.caption(f"**{name}**")
        _labeled(
            st,
            "color_picker",
            f"{name} — fixation color",
            display="Fixation color",
            key=f"cmp{idx}_fix_color",
            persist_state="session",
        )
        _range_slider(
            st,
            f"{name} — marker size range",
            display="Marker size range",
            label_left=True,
            key=f"cmp{idx}_marker_size_range",
            persist_state="session",
            min_value=4,
            max_value=40,
        )
        _numeric_slider(
            st,
            f"{name} — opacity",
            display="Opacity",
            label_left=True,
            key=f"cmp{idx}_opacity",
            persist_state="session",
            min_value=0.1,
            max_value=1.0,
            step=0.05,
            slider_format="%.2f",
            help="Marker opacity for this scanpath (1.0 = fully opaque).",
        )


def _render_compare_saccade_styles() -> None:
    """Per-scanpath *saccade* styling for the two-trial comparison — rendered
    inside the Saccade-style popover (when comparing). Laid out like
    :func:`_render_compare_fix_styles` — see its note on the UX-51 captions."""
    st.caption("Per-scanpath (comparison)")
    style_labels = list(SACCADE_DASH_OPTIONS.keys())
    for idx, name in _COMPARE_SCANPATHS:
        st.caption(f"**{name}**")
        _labeled(
            st,
            "color_picker",
            f"{name} — saccade color",
            display="Saccade color",
            key=f"cmp{idx}_saccade_color",
            persist_state="session",
        )
        _labeled(
            st,
            "selectbox",
            f"{name} — line style",
            display="Line style",
            options=style_labels,
            key=f"cmp{idx}_saccade_style",
            persist_state="session",
        )
        _numeric_slider(
            st,
            f"{name} — line width",
            display="Line width",
            label_left=True,
            key=f"cmp{idx}_saccade_width",
            persist_state="session",
            min_value=SACCADE_WIDTH_BOUNDS[0],
            max_value=SACCADE_WIDTH_BOUNDS[1],
            step=0.5,
            slider_format="%.1f px",
            number_format="%.1f",
        )


def _collect_compare_styles() -> tuple[dict, dict]:
    """Build the ``(style_a, style_b)`` dicts the comparison figure consumes from
    the ``cmp{idx}_*`` session keys (rendered under each layer's popover)."""
    styles: list[dict] = []
    for idx, _ in _COMPARE_SCANPATHS:
        default_color = compare_palette_color(idx)
        styles.append(
            dict(
                # `or default_color` so a falsy ("" / None) value can never escape
                # as a colour (defensive against the color-picker black desync).
                fix_color=st.session_state.get(f"cmp{idx}_fix_color") or default_color,
                saccade_color=(
                    st.session_state.get(f"cmp{idx}_saccade_color") or default_color
                ),
                saccade_style=SACCADE_DASH_OPTIONS.get(
                    st.session_state.get(f"cmp{idx}_saccade_style", "Solid"), "solid"
                ),
                saccade_width=float(
                    st.session_state.get(
                        f"cmp{idx}_saccade_width", DEFAULT_SACCADE_WIDTH
                    )
                ),
                marker_size_range=tuple(
                    st.session_state.get(
                        f"cmp{idx}_marker_size_range", DEFAULT_MARKER_SIZE_RANGE
                    )
                ),
                hollow=bool(st.session_state.get(f"cmp{idx}_hollow", False)),
                opacity=float(st.session_state.get(f"cmp{idx}_opacity", 1.0)),
            )
        )
    return styles[0], styles[1]


def _fix_range_max(fixations: pd.DataFrame | None) -> int:
    """Highest 1-based fixation index in ``fixations`` (0 when none)."""
    if (
        fixations is None
        or fixations.empty
        or "order_in_trial" not in fixations.columns
    ):
        return 0
    top = pd.to_numeric(fixations["order_in_trial"], errors="coerce").max()
    return int(top) if pd.notna(top) else 0


def _fix_range_trial_key(fixations: pd.DataFrame | None) -> tuple | None:
    """Identity of the trial the window slider is sizing, or ``None`` if unclear.

    Used only to notice a *trial change*; a frame that isn't a single trial (or
    carries no identity columns) returns ``None``, which is treated as "don't
    reset" so an ambiguous frame never silently drops the user's window.
    """
    if fixations is None or fixations.empty:
        return None
    parts = []
    for col in ("participant_id", "trial_id"):
        if col not in fixations.columns:
            continue
        values = fixations[col].dropna().unique()
        if len(values) != 1:
            return None
        parts.append(str(values[0]))
    return tuple(parts) or None


def _render_fix_range_slider(fixations: pd.DataFrame | None) -> None:
    """Render the VIZ-7 fixation-index window slider (``single_fix_range``).

    The slider value persists across trial changes (which shift ``max_fix``), so
    it is seeded/clamped via session_state *only* (no ``value=`` arg) to stay
    inside ``[1, max_fix]`` — a stored out-of-range value would otherwise raise.
    This is the single fixation-index control for the app; the Comparisons subtab
    deliberately has none of its own (ENG-8). A trial with fewer than two
    fixations can't host a range slider (a one-value slider throws in the
    browser), so the window is cleared to ``None`` (the full, unsliced trial).

    **Scope.** A window is per-trial by default: picking another trial shows all
    of that trial's fixations again, because a range like "fixations 5–20" rarely
    means the same thing on a different reading. The *Apply to all trials*
    checkbox opts into the sticky behaviour (the window is re-applied to every
    trial, clamped to each one's length).

    The checkbox is deliberately **UI-only** state (cf. ``share_identity_mode``),
    because what it governs — what happens to the window when you select a
    *different* trial — has no referent on the other three surfaces: a share link,
    a ``render`` invocation and an ``api.plot_scanpath`` call each address one
    explicit trial, and ``api``'s ``fix_index_range`` is a per-call argument
    rather than sticky state. If it is ever persisted into a saved config it must
    be added to ``session_keys.PLOT_CONFIG_STATE_KEYS``.

    Note ``single_fix_range`` *itself* currently reaches only the UI and the
    headless API — there is no ``fix_range`` URL param and
    ``tabs._build_studio_config`` doesn't write one — so a window is not
    shareable today. That is a pre-existing VIZ-7 gap, not something this
    checkbox introduces; wiring it up would not change the reasoning above.
    """
    if fixations is None:
        return
    max_fix = _fix_range_max(fixations)
    if max_fix < 2:
        # Nothing meaningful to window — clear any stale stored range so the
        # plot isn't filtered by a window the slider can no longer show.
        if st.session_state.get("single_fix_range") is not None:
            st.session_state["single_fix_range"] = None
        st.session_state["single_fix_range_user_set"] = False
        return
    # Notice a trial change *before* resolving the stored window: in per-trial
    # mode, un-freezing the window is what makes the `user_set is False` branch
    # below expand it to the new trial's full range.
    all_trials = bool(st.session_state.get("single_fix_range_all_trials", False))
    trial_key = _fix_range_trial_key(fixations)
    if trial_key is not None:
        previous = st.session_state.get("_fix_range_trial")
        st.session_state["_fix_range_trial"] = trial_key
        if previous is not None and previous != trial_key and not all_trials:
            st.session_state["single_fix_range_user_set"] = False
    stored = st.session_state.get("single_fix_range")
    user_set = st.session_state.get("single_fix_range_user_set")
    if stored is None:
        st.session_state["single_fix_range"] = (1, max_fix)
        st.session_state["single_fix_range_user_set"] = False
    elif user_set is False:
        # BUG-16: an untouched auto-default follows the selected trial and always
        # expands to its full range. Only a widget interaction freezes a window.
        st.session_state["single_fix_range"] = (1, max_fix)
    elif isinstance(stored, (tuple, list)) and len(stored) == 2:
        # A value supplied before this widget first renders (test seam, restored
        # session, or future deep link) is explicit and should be preserved.
        st.session_state.setdefault("single_fix_range_user_set", True)
        lo = max(1, min(int(stored[0]), max_fix))
        hi = max(lo, min(int(stored[1]), max_fix))
        st.session_state["single_fix_range"] = (lo, hi)
    else:
        st.session_state["single_fix_range"] = (1, max_fix)
        st.session_state["single_fix_range_user_set"] = False

    def _mark_fix_range_user_set() -> None:
        st.session_state["single_fix_range_user_set"] = True

    _range_slider(
        st,
        "Fixation index range",
        label_left=True,
        key="single_fix_range",
        persist_state="session",
        min_value=1,
        max_value=max_fix,
        on_change=_mark_fix_range_user_set,
        help="Draw only fixations whose index falls in this range (their "
        "saccades follow). The chips and panels still describe the full trial; "
        "the bulk (multiple-trial) export is unaffected.",
    )
    # Seeded via `_VIZ_WIDGET_DEFAULTS`, so no `value=` here (see `_pin`).
    st.checkbox(
        "Apply to all trials",
        key="single_fix_range_all_trials",
        persist_state="session",
        help="**Off** (default) — the window belongs to this trial; picking "
        "another trial shows all of its fixations again. **On** — keep the same "
        "index window as you move through trials, clamped to each trial's "
        "length (a shorter trial narrows it). Either way **Compare** windows "
        "both scanpaths by the same range, since the two readings share one "
        "index axis there.",
    )


def _seed_viz_state(
    trial_fixations: pd.DataFrame,
    base_font_size: int,
    words: pd.DataFrame | None,
) -> tuple[list[str], list[str], list[str]]:
    """Seed every viz widget's session_state default (pure — renders nothing).

    Both ``sidebar_controls`` (which renders the widgets) and
    ``viz_settings_from_state`` (the non-rendering reader used by the Corpus view
    and the Save & restore panel) call this first, so the controls and their
    consumers can't drift. The widgets render WITHOUT a ``value=``/``index=``
    argument and rely on these defaults, which keeps their keys programmatically
    settable (deep links / plot-config restore) without Streamlit's "default
    value but also set via Session State API" warning.

    Seeding only — keeping a stored value alive through a run where its widget
    doesn't render is the widgets' own ``persist_state="session"`` (ENG-36), so
    this is safe to call both before rendering (``sidebar_controls``) and after
    (``app.main`` re-reads the settings once the rail has rendered, where writing
    a widget key would raise). Returns ``(color_fields, numeric_fields,
    highlight_options)`` for the caller to reuse.
    """
    for _key, _default in _VIZ_WIDGET_DEFAULTS.items():
        _pin(_key, _default)
    _pin("global_marker_size_range", (8, 24))
    _seed_compare_styles()

    color_fields = color_field_options(trial_fixations)
    _drop_stale("global_color_by", color_fields)
    # VIZ-17: one flat colour by default — see `color_field_options`.
    _pin("global_color_by", UNIFORM_COLOR_FIELD)

    numeric_fields = numeric_field_options(trial_fixations)
    if numeric_fields:
        x_default = "x" if "x" in numeric_fields else numeric_fields[0]
        y_default = (
            "y"
            if "y" in numeric_fields
            else numeric_fields[min(1, len(numeric_fields) - 1)]
        )
        _drop_stale("global_x_field", numeric_fields)
        _pin("global_x_field", x_default)
        _drop_stale("global_y_field", numeric_fields)
        _pin("global_y_field", y_default)

    # Highlight-column default + stale-clear run every time (even when the Text
    # styling popover isn't rendered this run) so a restored config on data with
    # no boolean columns can't carry a dangling pick.
    highlight_options = highlight_column_options(words)
    _drop_stale("global_highlight_column", highlight_options)
    if highlight_options:
        _pin(
            "global_highlight_column",
            "is_in_aspan"
            if "is_in_aspan" in highlight_options
            else highlight_options[0],
        )

    # VIZ-26: arbitrary multi-field word/fixation hover. The legacy one-measure
    # key remains as a fallback for old links/configs, but new surfaces write the
    # explicit lists.
    word_hover_options = hover_field_options(words, words=True)
    fix_hover_options = hover_field_options(trial_fixations)
    _drop_stale_multi("global_word_hover_fields", word_hover_options)
    _drop_stale_multi("global_fixation_hover_fields", fix_hover_options)
    if "global_word_hover_fields" not in st.session_state:
        legacy = st.session_state.get(
            "global_word_hover_measure", "total_fixation_duration_ms"
        )
        default_word_hover = ["text", "word_id", "line_idx"]
        if legacy:
            default_word_hover.append(legacy)
        _pin(
            "global_word_hover_fields",
            [field for field in default_word_hover if field in word_hover_options],
        )
    if "global_fixation_hover_fields" not in st.session_state:
        _pin(
            "global_fixation_hover_fields",
            [
                field
                for field in ("order_in_trial", "duration_ms", "word_id")
                if field in fix_hover_options
            ],
        )
    return color_fields, numeric_fields, highlight_options


def _collect_viz_settings(
    trial_fixations: pd.DataFrame,
    words: pd.DataFrame | None,
    *,
    numeric_fields: list[str] | None = None,
    highlight_options: list[str] | None = None,
) -> dict:
    """Build the viz-settings dict from session_state (pure — renders nothing).

    The single source of truth for the dict the figure builders consume, so the
    rendered controls (``sidebar_controls``) and the non-rendering reader
    (``viz_settings_from_state``) return identical shapes. Conditionally-applied
    fields (colour ranges, the highlight column, saccade arrows) are gated here
    exactly as the widgets gate them, so a stored value for an off layer doesn't
    leak into the figure. ``compare_style_a``/``_b`` are ``None``; the rendering
    path fills them in when the comparison toggle is on.
    """
    ss = st.session_state
    if highlight_options is None:
        highlight_options = highlight_column_options(words)

    show_fix = bool(ss.get("global_show_fix"))
    show_saccades = bool(ss.get("global_show_saccades"))
    show_heatmap = bool(ss.get("global_show_heatmap"))
    show_labels = bool(ss.get("global_show_labels"))
    color_by = ss.get("global_color_by")

    # Fixation colour range only applies when fixations are shown AND coloured by
    # a numeric column with a valid spread — mirror the widget's gate.
    fixation_color_range = None
    if (
        show_fix
        and color_by in trial_fixations.columns
        and pd.api.types.is_numeric_dtype(trial_fixations[color_by])
    ):
        cmin, cmax = trial_fixations[color_by].min(), trial_fixations[color_by].max()
        if pd.notna(cmin) and pd.notna(cmax):
            # Clamp to the same [floor(min), ceil(max)] bounds the rendered slider
            # uses, so the non-rendering reader can't leak a stale out-of-bounds
            # range (cmax_eff mirrors the slider's `cmax if cmax > cmin else +1`).
            lo = float(math.floor(cmin))
            hi = float(math.ceil(cmax))
            hi = hi if hi > lo else lo + 1.0
            fixation_color_range = _clamped_pair(
                ss.get("global_fixation_color_range"), lo, hi
            )

    # Heatmap colour range only applies for the duration-weighted heatmap.
    heatmap_range = None
    if (
        show_heatmap
        and ss.get("global_heatmap_metric") == "duration_ms"
        and "duration_ms" in trial_fixations.columns
    ):
        heat = trial_fixations["duration_ms"]
        if len(heat) > 0 and pd.notna(heat.min()) and pd.notna(heat.max()):
            lo = float(math.floor(heat.min()))
            hi = float(math.ceil(heat.max()))
            hi = hi if hi > lo else lo + 1.0
            heatmap_range = _clamped_pair(ss.get("global_heatmap_color_range"), lo, hi)

    # Fixation-index window (VIZ-7): a (start, end) tuple over `order_in_trial`,
    # or None for the full trial. Read straight from the slider's session key;
    # the rendering path clamps it to the trial's fixation count, and the
    # non-rendering Corpus reader simply leaves it None (it never windows).
    fix_index_range = None
    _fr = ss.get("single_fix_range")
    if isinstance(_fr, (tuple, list)) and len(_fr) == 2:
        fix_index_range = (int(_fr[0]), int(_fr[1]))

    # Highlight column only applies when Text is shown and a span style is active.
    critical_span_style = ss.get("global_critical_span_style", "Mark text")
    highlight_column = None
    if show_labels and critical_span_style != "None" and highlight_options:
        candidate = ss.get("global_highlight_column")
        highlight_column = candidate if candidate in highlight_options else None

    # Background colour comes from the Experimental Setup picker (read here so it
    # flows into the figure via viz_settings).
    bg_options = list(BACKGROUND_PRESETS.keys()) + ["Custom…"]
    bg_choice = ss.get("global_bg_choice", bg_options[0])
    if bg_choice == "Custom…":
        background_color = ss.get("global_bg_custom", DEFAULT_BACKGROUND_COLOR)
    else:
        background_color = BACKGROUND_PRESETS.get(
            bg_choice, BACKGROUND_PRESETS[bg_options[0]]
        )

    return dict(
        show_words=bool(ss.get("global_show_words")),
        show_labels=show_labels,
        show_fix=show_fix,
        show_order=bool(ss.get("global_show_order")),
        show_saccades=show_saccades,
        # Arrows are a saccade sub-layer: never report them on when saccades off.
        show_saccade_arrows=bool(ss.get("global_show_saccade_arrows"))
        and show_saccades,
        show_heatmap=show_heatmap,
        # `or default` (not get-default) so a segmented_control deselect → None
        # falls back instead of propagating None into the figure builders.
        heatmap_style=ss.get("global_heatmap_style") or "Word boxes",
        heatmap_norm=ss.get("global_heatmap_norm") or "Linear",
        duration_mass_sigma_chars=float(
            ss.get("global_duration_mass_sigma_chars", 1.0)
        ),
        show_raw_gaze=bool(ss.get("global_show_raw_gaze")),
        show_stimulus_image=bool(ss.get("global_show_stimulus_image")),
        # VIZ-4: image-stimulus opacity (applies to dataset + uploaded images) and
        # the uploaded image's data URI (session-only; set by sidebar_controls).
        stimulus_image_opacity=float(ss.get("global_stimulus_image_opacity", 1.0)),
        stimulus_image_upload_uri=ss.get("_stimulus_image_upload_uri"),
        # VIZ-4: manual image alignment (origin nudge + size scale).
        stimulus_image_offset_x=float(ss.get("global_stimulus_image_offset_x", 0.0)),
        stimulus_image_offset_y=float(ss.get("global_stimulus_image_offset_y", 0.0)),
        stimulus_image_scale=float(ss.get("global_stimulus_image_scale", 1.0)),
        color_by=color_by,
        heatmap_metric=ss.get("global_heatmap_metric") or "duration_ms",
        x_field=ss.get("global_x_field"),
        y_field=ss.get("global_y_field"),
        marker_size_range=tuple(ss.get("global_marker_size_range", (8, 24))),
        order_font_size=ss.get("global_order_font_size"),
        order_font_color=ss.get("global_order_font_color"),
        show_colorbars=bool(ss.get("global_show_colorbars")),
        fit_to_monitor=bool(ss.get("global_fit_to_monitor")),
        show_coordinate_grid=bool(ss.get("global_show_coordinate_grid")),
        coordinate_grid_auto=bool(ss.get("global_coordinate_grid_auto", True)),
        coordinate_grid_spacing=(
            None
            if bool(ss.get("global_coordinate_grid_auto", True))
            else float(ss.get("global_coordinate_grid_spacing", 100.0))
        ),
        fixation_color_range=fixation_color_range,
        heatmap_range=heatmap_range,
        fixation_colorscale=ss.get("global_fixation_colorscale")
        or DEFAULT_FIXATION_COLORSCALE,
        heatmap_colorscale=ss.get("global_heatmap_colorscale")
        or DEFAULT_HEATMAP_COLORSCALE,
        critical_span_style=critical_span_style,
        highlight_column=highlight_column,
        saccade_color=ss.get("global_saccade_color", SACCADE_COLOR),
        saccade_style=ss.get("global_saccade_style") or "Solid",
        saccade_width=float(ss.get("global_saccade_width") or DEFAULT_SACCADE_WIDTH),
        # VIZ-8: colour-by-reading-type mode + the per-class palette + optional
        # colour-key legend.
        saccade_color_mode=ss.get("global_saccade_color_mode") or "Uniform",
        saccade_type_legend=bool(ss.get("global_saccade_type_legend", True)),
        saccade_class_colors={
            cls_name: ss.get(
                f"global_saccade_class_color_{cls_name}", SACCADE_CLASS_COLORS[cls_name]
            )
            for cls_name in SACCADE_CLASS_EDITABLE
        },
        # VIZ-31: the reading-class filter. Ordered by SACCADE_CLASS_ORDER (not by
        # click order) so the same selection always produces the same figure key,
        # and unknown names are dropped — a stale link must not smuggle a class
        # the build no longer classifies into the builder. An *empty* selection
        # reads as "no filter", not "draw nothing": hiding the layer entirely is
        # what the Saccades toggle above the filter is for, and a cleared
        # multiselect that blanks the figure reads as a bug.
        saccade_classes=[
            cls_name
            for cls_name in SACCADE_CLASS_ORDER
            if cls_name in set(ss.get("global_saccade_classes") or SACCADE_CLASS_ORDER)
        ],
        # VIZ-9: linear-reading mode (arced saccades + snap fixations above words).
        saccade_render_mode=ss.get("global_saccade_render_mode") or "Straight",
        fixation_snap_to_word=bool(ss.get("global_fixation_snap_to_word")),
        illustration_label=ss.get("global_illustration_label") or "Auto",
        # VIZ-10: autoplay the animated replay on load (default on).
        anim_autoplay=bool(ss.get("global_anim_autoplay", True)),
        # VIZ-11 follow-up: the animation frame grid (smoothness vs. frame count).
        anim_grid_step_ms=float(ss.get("global_anim_grid_step_ms", 100) or 100),
        anim_max_frames=int(ss.get("global_anim_max_frames", 360) or 360),
        hollow_fixations=bool(ss.get("global_hollow_fixations")),
        fixation_opacity=float(ss.get("global_fixation_opacity", 1.0)),
        # VIZ-17 uniform fixation colour + VIZ-15 marker shape.
        fixation_color=ss.get("global_fixation_color") or DEFAULT_FIXATION_COLOR,
        fixation_symbol=ss.get("global_fixation_symbol") or DEFAULT_FIXATION_SYMBOL,
        # VIZ-18: the active palette name — *derived* from the colour keys above
        # rather than read back from the selector, so a hand-edited figure is
        # reported as `Custom` on every surface instead of carrying a palette
        # name it no longer matches. The colours themselves ride in the
        # individual keys, so `Custom` restores exactly; the name is only there
        # for the picker to come back on the right entry and for export captions.
        palette=_active_palette() or CUSTOM_PALETTE,
        fix_index_range=fix_index_range,
        highlight_text_color=ss.get("global_highlight_text_color"),
        text_color=ss.get("global_text_color", WORD_LABEL_COLOR),
        color_by_line=color_by == "line",
        # Fixation classification (PRE-2) + compare-overlay legend (CMP-2).
        fixation_flags=_collect_fixation_flags(),
        show_compare_legend=bool(ss.get("global_show_compare_legend")),
        span_border_color=ss.get("global_span_border_color", "#000000"),
        colorbar_orientation=ss.get("global_colorbar_orientation") or "Vertical",
        colorbar_tickangle=int(ss.get("global_colorbar_tickangle") or 0),
        colorbar_tickfont_size=int(ss.get("global_colorbar_tickfont_size") or 12),
        background_color=background_color,
        compare_style_a=None,
        compare_style_b=None,
        word_hover_measure=ss.get(
            "global_word_hover_measure", "total_fixation_duration_ms"
        ),
        word_hover_fields=list(ss.get("global_word_hover_fields") or []),
        fixation_hover_fields=list(ss.get("global_fixation_hover_fields") or []),
        # PRE-3: in-place drift correction. `tabs._drift_corrected` applies it once
        # above the render-mode split, so it reaches all three builders (VIZ-23);
        # only the connector layer is still static-figure-only.
        #
        # PRE-21: resolved to "Off" while the feature is gated, rather than each
        # consumer gating separately. That is what makes an old share link or
        # saved config carrying `align_algorithm=warp` degrade *silently* — the
        # setting is read, then ignored, and nothing downstream can disagree.
        align_algorithm=(
            (ss.get("global_align_algorithm") or "Off")
            if drift_correction_enabled()
            else "Off"
        ),
        align_connectors=drift_correction_enabled()
        and bool(ss.get("global_align_connectors"))
        and (ss.get("global_align_algorithm") or "Off") != "Off",
        # EXP-5: empty when the toggle is off, regardless of stored pattern text,
        # so turning it off can never leave a stale pattern silently applied.
        title_pattern=(
            ss.get("global_title_pattern") or ""
            if ss.get("global_show_title_caption")
            else ""
        ),
        caption_pattern=(
            ss.get("global_caption_pattern") or ""
            if ss.get("global_show_title_caption")
            else ""
        ),
    )


def viz_settings_from_state(
    trial_fixations: pd.DataFrame,
    base_font_size: int,
    words: pd.DataFrame | None = None,
) -> dict:
    """Resolve the viz-settings dict from session_state WITHOUT rendering widgets.

    Used by the views that consume the settings but don't host the controls — the
    Corpus Analysis figures and the Save & restore panel — so they stay in sync
    with the scanpath rail (which renders the actual widgets via
    ``sidebar_controls``) on whatever the user last set.
    """
    _, numeric_fields, highlight_options = _seed_viz_state(
        trial_fixations, base_font_size, words
    )
    return _collect_viz_settings(
        trial_fixations,
        words,
        numeric_fields=numeric_fields,
        highlight_options=highlight_options,
    )


def corpus_style_controls(
    trial_fixations: pd.DataFrame,
    base_font_size: int,
    *,
    words: pd.DataFrame | None = None,
    host=None,
    canvas_renderer=None,
) -> dict:
    """Focused, shared-key styling controls for Corpus Analysis (AN-29).

    Corpus figures intentionally expose only the palette channels they consume;
    the single-scanpath layer controls remain in the Scanpath rail. Because these
    widgets write the same ``global_*`` keys, Share/config restore, the CLI
    palette, and headless builder parameters stay one contract.

    ``canvas_renderer`` renders the canvas / text panel here too (VIZ-31). The
    corpus figures are drawn true-to-scale from exactly those values — monitor
    size, fonts, line spacing, background — so the view that consumes them needs
    a way to change them; before VIZ-31 the panel lived in the always-present
    sidebar and was reachable from here for free.
    """
    _seed_viz_state(trial_fixations, base_font_size, words)
    target = host or st
    with target.expander("🎨 Corpus figure style", expanded=False):
        active = _active_palette()
        options = list(PALETTES) if active else [CUSTOM_PALETTE, *PALETTES]
        st.session_state["global_palette"] = active or CUSTOM_PALETTE
        st.selectbox(
            "Palette",
            options=options,
            key="global_palette",
            persist_state="session",
            on_change=_on_palette_change,
            help="Shared with the Scanpath view and every saved/shareable figure setting.",
        )
        columns = st.columns(2)
        columns[0].color_picker(
            "Primary series",
            key="global_fixation_color",
            persist_state="session",
            help="First group or profile.",
        )
        columns[1].color_picker(
            "Secondary series",
            key="global_saccade_color",
            persist_state="session",
            help="Second group.",
        )
        st.selectbox(
            "Heatmap colorscale",
            options=COLORSCALES,
            key="global_heatmap_colorscale",
            persist_state="session",
            help="Used by word matrices and stimulus heatmaps.",
        )
    if canvas_renderer is not None:
        canvas_renderer(target)
    return viz_settings_from_state(trial_fixations, base_font_size, words=words)


def render_viz_reset(host) -> None:
    """Render the scoped visualization reset popover into ``host``.

    Full width, like every other trigger in the rail. UX-44's compact ``↺ Reset``
    pill was for sharing the heading row; BUG-24 moved the control to the foot of
    the rail, where it has a row of its own, so the compact form is gone.
    """
    reset = host.popover(
        "♻️ Reset settings",
        width="stretch",
        help="Reset visualization settings to their defaults.",
    )
    reset.caption(
        "Put every visualization control back to the app's defaults. Your "
        "**annotations**, trial filters, column mapping, data source and the "
        "selected trial are kept."
    )
    reset.button(
        "♻️ Reset visualization",
        key="reset_viz_settings_btn",
        type="primary",
        on_click=reset_viz_settings,
        width="stretch",
        help="Every layer, colour, size and axis control back to its default — "
        "including the settings a Share link put there.",
    )


def sidebar_controls(
    trial_fixations: pd.DataFrame,
    base_font_size: int,
    *,
    host=None,
    has_raw_gaze: bool = False,
    has_stimulus_image: bool = False,
    words: pd.DataFrame | None = None,
    fix_range_fixations: pd.DataFrame | None = None,
    canvas_renderer=None,
) -> dict:
    """Render the visualization controls and return the resolved settings dict.

    Layout (VIZ-31 / UX-44 — grouped so the rail reads by category):
      1. Quick-view presets + Palette at the top: the two controls that get to a
         good figure without opening anything.
      2. Five collapsible sections — **👁️ Fixations** (expanded), then collapsed
         **↗️ Saccades**, **📄 Stimulus**, **🔥 Overlays**, and
         **📐 Figure & canvas** (canvas/text plus axes/labels).
      3. Inside a section: **layer toggle → ⚙️ style → 🧹 filter**, the detail
         popovers shown only while the layer is on. Streamlit nests neither
         expander-in-expander nor popover-in-popover, so an expander holding
         popovers is the only two-level shape available — which is also why
         Fixations and Saccades are peer sections rather than sub-sections of a
         single "Scanpath" group.
      4. **📐 Figure & canvas** follows the same shape with no layer to toggle
         (UX-48): the framing toggle inline, then four popovers — 🖥️ Screen &
         geometry · 🔤 Text & fonts (both from ``canvas_renderer``) · 📊 Axes &
         grid · 🏷️ Title & labels.

    The sections are created up front (Streamlit lays containers out in creation
    order), so each block below renders into its section without moving in this
    file — see the "Layer groups" comment.

    ``canvas_renderer`` is an optional ``callable(slot)`` rendering the canvas /
    text panel (``app.render_sidebar_canvas_controls``) into a slot reserved
    between the Overlays and Figure groups. VIZ-31 moved that panel out of the
    sidebar so the figure's fonts, text colour and background sit beside the
    other visual controls; when it is ``None`` (the wizard, the non-rendering
    readers) nothing is drawn there and the panel keeps its own home.

    ``host`` is the container to render into — the app passes the scanpath rail
    (``tabs.render_single_trial_tab``); ``None`` renders in place. The returned
    dict is built by
    ``_collect_viz_settings`` (shared with ``viz_settings_from_state``) so the
    rendered controls and the non-rendering readers can't drift.

    ``fix_range_fixations`` is the *selected trial's* fixations, used only to size
    the VIZ-7 fixation-index window slider (its max is that trial's fixation
    count). When omitted, the slider isn't rendered (e.g. the non-rendering
    Corpus reader, which never windows).
    """
    # can re-push the stored values to the browser (BUG-15 — see `_pin`).
    color_fields, numeric_fields, highlight_options = _seed_viz_state(
        trial_fixations, base_font_size, words
    )
    if not numeric_fields:
        st.error("No numeric fields found in fixations to map axes.")
        st.stop()

    # The keyed container is the spotlight-tour target
    # (`.st-key-tour_grp_viz_controls`). Values for controls not rendered this run
    # are read back from session_state by `_collect_viz_settings`, so the returned
    # dict always carries every key the figure builders depend on.
    viz = (host if host is not None else st).container(key="tour_grp_viz_controls")

    # --- Quick views ------------------------------------------------------
    # Focused presets stay one compact row; Reading-order / Everything
    # are still reachable by toggling layers. The remaining preset keys
    # (`reading_order`, `everything`) stay in `_VIEW_PRESETS` for any deep link.
    viz.caption("Quick views")
    # Side by side to keep the rail short. The active preset (whichever Quick-view
    # preset the current layer toggles match) renders as "primary" so the user can
    # see which view is active at a glance. When neither preset matches (the user
    # has customized layers manually) both buttons render without highlight.
    _active = _active_quick_view()
    _qv = viz.columns(3)
    _qv[0].button(
        "👁️ Scanpath",
        key="viz_view_scanpath",
        type="primary" if _active == "scanpath" else "secondary",
        width="stretch",
        help="Fixations + saccades over the text — the core scanpath.",
        on_click=_apply_view_preset,
        args=("scanpath",),
    )
    _qv[1].button(
        "🔥 Heatmap",
        key="viz_view_heatmap",
        type="primary" if _active == "heatmap" else "secondary",
        width="stretch",
        help="Fixation-density heatmap over the text, nothing else.",
        on_click=_apply_view_preset,
        args=("heatmap",),
    )
    _qv[2].button(
        "✏️ Illustration",
        key="viz_view_illustration",
        type="primary" if _active == "illustration" else "secondary",
        width="stretch",
        help="A clean schematic: snapped fixations, arced connectors, and a "
        "uniform visual style.",
        on_click=_apply_view_preset,
        args=("illustration",),
    )
    # VIZ-31: the Illustration *label* (the publication-disclosure override) now
    # lives in the "📐 Figure & canvas" group below, with the other figure-level
    # presentation settings, rather than as a third top-level row up here.

    # VIZ-18: these figures end up in papers — printed, sometimes in black &
    # white — and are read by colourblind viewers, so the colour defaults are a
    # choice rather than a constant. Picking one writes the individual colour
    # keys, so every per-element picker below still overrides it — and once one
    # is overridden the selector says **Custom** rather than keeping a name the
    # figure no longer earns (the same rule the Quick-view buttons follow above).
    # `Custom` is offered only while it's true, so the list stays the three real
    # palettes the moment the colours match one again.
    _active = _active_palette()
    _palette_options = list(PALETTES) if _active else [CUSTOM_PALETTE, *PALETTES]
    st.session_state["global_palette"] = _active or CUSTOM_PALETTE
    viz.selectbox(
        "Palette",
        options=_palette_options,
        key="global_palette",
        persist_state="session",
        on_change=_on_palette_change,
        help="Colour defaults for the marks. **Default (colourblind-safe)** uses "
        "the Okabe–Ito hues; **Print / greyscale** drops hue entirely so the "
        "figure survives a black & white print (pair it with a marker shape); "
        "**High contrast** is for projectors. Each one just presets the colour "
        "pickers — change any of them afterwards and this reads **Custom**.",
    )

    # Keep the palette controls visually separate from the bordered layer cards.
    # A keyed wrapper gives the spacing a stable, narrowly scoped CSS hook.
    viz.container(key="palette_layers_divider").divider()

    # Each main layer is an `st.toggle`; the layer's detailed styling lives in a
    # per-layer popover shown only while the layer is on — so the rail shows just
    # the toggles (plus, for fixations, the primary "Color by" control), and the
    # fiddly knobs open in an overlay instead of growing the rail past the plot.
    # Values for off layers are read back from session_state by
    # `_collect_viz_settings`, so the returned dict always carries every key.

    # VIZ-21: the two view modes (rail → 🎛️ Plot controls, rendered *before* this
    # function) route the figure through different builders, and each ignores a
    # different slice of these controls. Read both flags and gate every affected
    # widget through `_mode_gate` — greyed with a reason, never silently ignored,
    # and never with its stored value rewritten. VIZ-23 then made a batch of them
    # live in Animate / Compare, so what remains gated below is the genuinely
    # builder-less set (see CLAUDE.md's setting → render-path table).
    comparing = bool(
        st.session_state.get(
            "_resolved_comparing", st.session_state.get("single_compare_toggle")
        )
    )
    animating = bool(
        st.session_state.get(
            "_resolved_animating", st.session_state.get("single_animate")
        )
    )
    # Handy shorthands for the two recurring gates.
    _static_only = dict(in_animation=False, in_compare=False)
    _no_compare = dict(in_compare=False)

    # --- Layer groups (VIZ-31) --------------------------------------------
    # The seven layers used to sit as one flat top-to-bottom run of toggles, so
    # the rail opened as ~13 peer rows with no hint that Text / Bounding boxes /
    # Stimulus image describe the *stimulus* while Fixations / Saccades / Raw
    # gaze describe the *recording*. They are now named groups, plus two for how
    # the figure is framed.
    #
    # The groups are created HERE, up front, because Streamlit lays containers
    # out in **creation** order — which lets each block below keep its current
    # position in this file while rendering into whichever group it belongs to.
    # So the visual order is exactly the order of these six lines; the code
    # order further down is unchanged (and irrelevant to the layout).
    #
    # **Section shape.** Each group is `layer toggle → ⚙️ style → 🧹 filter`, the
    # nesting the original wireframe asked for. Streamlit nests neither
    # expander-in-expander nor popover-in-popover, but popover-in-**expander** is
    # allowed — so a section is an expander and its sub-sections are popovers,
    # which is the only two-level shape the framework actually renders. That is
    # also why Fixations and Saccades are *peer* sections rather than one
    # "Scanpath" group holding two sub-sections: the sub-section level is spent
    # on style/filter, where it earns more than on the layer split.
    #
    # Fixations opens because it is the primary layer; Saccades and the less-used
    # groups stay collapsed so the independent rail starts compact. The preset row
    # above still covers the common combinations without opening anything at all.
    fix_grp = viz.expander("👁️ Fixations", expanded=True)
    sac_grp = viz.expander("↗️ Saccades", expanded=False)
    stim_grp = viz.expander("📄 Stimulus", expanded=False)
    ovl_grp = viz.expander("🔥 Overlays", expanded=False)
    # Canvas/text and the former Figure/axes controls share one disclosure: both
    # describe the figure's framing rather than a data layer. The injected canvas
    # renderer writes directly into this expander (not a nested expander), as its
    # own popover sub-groups — see the "Figure & canvas" block below.
    figure_grp = viz.expander("📐 Figure & canvas", expanded=False)

    # --- Fixations --------------------------------------------------------
    # The Fixations toggle reaches the static figure AND Compare (CMP-7 — the
    # comparison heatmap is unreadable under two full sets of markers). Only the
    # animated replay ignores it: the replay *is* the fixation trail, so there is
    # nothing left to draw with it off, and `make_scanpath_animation` takes no
    # `show_fixations` argument.
    fix_off_disabled, _ = _mode_gate(
        animating, comparing, in_animation=False, in_compare=True
    )
    show_fix = fix_grp.toggle(
        "**Visible**",
        key="global_show_fix",
        persist_state="session",
        disabled=fix_off_disabled,
        help=_gated_help(
            "Draw the fixation markers.",
            "⚠️ Fixations always draw in **Animate** mode — the replay is made "
            "of them. Your setting is kept for the static and comparison "
            "figures; the styling below still applies."
            if fix_off_disabled
            else "",
        ),
    )
    # …but the styling below is still (partly) live in those modes, so keep the
    # popover reachable even when the (inert) layer toggle reads off.
    if show_fix or fix_off_disabled:
        with fix_grp.popover("⚙️ Style", width="stretch"):
            # The metric that maps to fixation HUE — applies to the static
            # figure, the single animated replay AND the comparison overlay (in
            # compare it colours both scanpaths by the metric; the per-scanpath
            # flat colour below becomes the A/B marker outline). The one path
            # that ignores it is the DUAL animation (Animate + Compare), where
            # the flat A/B colours are all that tells the readings apart.
            metric_disabled, metric_reason = _mode_gate(
                animating, comparing, in_animation=not comparing
            )
            color_by = _labeled(
                st,
                "selectbox",
                "Color fixations by",
                options=color_fields,
                key="global_color_by",
                persist_state="session",
                disabled=metric_disabled,
                help=_gated_help(
                    f"The metric mapped to fixation marker hue. **{UNIFORM_COLOR_FIELD}** "
                    "(the default) maps nothing — marker *size* already shows fixation "
                    "duration, so colour is free for a second variable. Pick a column, "
                    "or 'line' to tint each fixation by the text line it lands on "
                    "(static plot + single animation only). In compare mode it "
                    "colours both scanpaths by this metric.",
                    metric_reason,
                ),
            )
            # VIZ-17: the flat colour, shown only when nothing is mapped to hue.
            # The comparison overlay draws each scanpath in its own colour
            # instead (see "Per-scanpath (comparison)" below), so grey it there.
            if color_by == UNIFORM_COLOR_FIELD:
                _dis, _reason = _mode_gate(animating, comparing, **_no_compare)
                _labeled(
                    st,
                    "color_picker",
                    "Fixation color",
                    key="global_fixation_color",
                    persist_state="session",
                    disabled=_dis,
                    help=_gated_help(
                        "The single colour every fixation marker wears.", _reason
                    ),
                )
            # VIZ-15: marker shape — a channel that survives greyscale printing,
            # so a figure stays readable where hue doesn't (see the Palette
            # picker's **Print / greyscale** option). VIZ-23 gave the comparison
            # builder `fixation_symbol` too, so shape is now a true global: it is
            # the one marker property Compare does NOT override per scanpath
            # (colour / size / opacity / hollow still come from `cmp{idx}_*`).
            _labeled(
                st,
                "selectbox",
                "Marker shape",
                options=list(FIXATION_SYMBOLS),
                format_func=lambda s: FIXATION_SYMBOLS[s],
                key="global_fixation_symbol",
                persist_state="session",
                help="Shape of the fixation markers. Unlike colour, shape "
                "still reads in black & white. Applies on all three render "
                "paths, including both compared scanpaths.",
            )
            # PRE-3: vertical drift correction. Snap each fixation to its assigned
            # text line using one of the Carr et al. (2021) algorithms; "Off"
            # leaves the raw coordinates. VIZ-23 hoisted the correction above the
            # render-mode split in `tabs.py`, so the *algorithm* now applies on all
            # three paths. The CONNECTORS don't: only `make_scanpath_figure` has a
            # connector layer, and drawing a full-length "original position" layer
            # from frame zero would misread as part of the replay's trail.
            static_disabled, static_reason = _mode_gate(
                animating, comparing, **_static_only
            )
            # PRE-21: not fully integrated, so hidden unless SCANPATH_EXPERIMENTAL
            # is set. The keys keep their defaults ("Off"), so nothing downstream
            # needs a second gate to render correctly.
            if drift_correction_enabled():
                align_algo = _labeled(
                    st,
                    "selectbox",
                    "Drift correction",
                    options=_ALIGN_OPTIONS,
                    key="global_align_algorithm",
                    persist_state="session",
                    help="Snap fixations to their assigned text line using a "
                    "vertical drift-correction algorithm (Carr et al., 2021). "
                    "'Off' shows the raw fixations. See also the 📐 Line "
                    "assignment subtab to compare all algorithms side by side.",
                )
                if align_algo != "Off":
                    _labeled(
                        st,
                        "checkbox",
                        "Show drift connectors",
                        key="global_align_connectors",
                        persist_state="session",
                        disabled=static_disabled,
                        help=_gated_help(
                            "Draw a faint line from each fixation's original "
                            "position to its corrected (snapped) position.",
                            static_reason,
                        ),
                    )
            # UX-13: "Snap fixations above words" used to sit flush under the
            # Drift-correction selectbox, which made it read as a
            # drift-correction option. It is not — it's the fixation half of
            # the VIZ-9 *linear-reading schematic* (its partner, arcing
            # saccades, is Saccades → Style → Line shape → Arc). Keep it under
            # Fixations (it moves fixations), but in its own captioned block
            # so the two are never confused.
            st.divider()
            st.caption("Linear-reading schematic")
            # Still `make_scanpath_figure`-only (VIZ-9's `fixation_snap_to_word`),
            # unlike the drift correction above it — hence its own gate.
            st.checkbox(
                "Snap fixations above words",
                key="global_fixation_snap_to_word",
                persist_state="session",
                disabled=static_disabled,
                help=_gated_help(
                    "Schematic layout, **not** drift correction: every "
                    "fixation is redrawn at the top-centre of the word it landed "
                    "on, so the scanpath reads as a diagram rather than as "
                    "recorded gaze. Drift correction (above) instead nudges the "
                    "raw coordinates onto their true text line. Pairs with "
                    "Saccades → ⚙️ Style → Line shape → **Arc**.",
                    static_reason,
                ),
            )
            # Size / opacity are per-scanpath in Compare (`cmp*_marker_size_range`
            # / `cmp*_opacity` always override the global values there).
            _dis, _reason = _mode_gate(animating, comparing, **_no_compare)
            _range_slider(
                st,
                "Size",
                label_left=True,
                key="global_marker_size_range",
                persist_state="session",
                min_value=4,
                max_value=40,
                disabled=_dis,
                help=_gated_help("Fixation marker size (px).", _reason),
            )
            _numeric_slider(
                st,
                "Opacity",
                label_left=True,
                key="global_fixation_opacity",
                persist_state="session",
                min_value=0.1,
                max_value=1.0,
                step=0.05,
                slider_format="%.2f",
                disabled=_dis,
                help=_gated_help(
                    "Fixation marker opacity. Lower it so overlapping "
                    "fixations show through (1.0 = fully opaque).",
                    _reason,
                ),
            )
            # Only meaningful once a variable is mapped to hue (VIZ-17): with
            # "(uniform)" there is nothing for a colorscale to scale. Follows the
            # same gate as "Color fixations by" (dead in a dual animation).
            if color_by != UNIFORM_COLOR_FIELD:
                _popover_selectbox(
                    "Colorscale",
                    COLORSCALES,
                    "global_fixation_colorscale",
                    disabled=metric_disabled,
                    help=_gated_help(
                        "Colour palette for fixation markers when colouring by "
                        "numeric values.",
                        metric_reason,
                    ),
                )
            raw_cmin = (
                trial_fixations[color_by].min()
                if color_by in trial_fixations.columns
                and pd.api.types.is_numeric_dtype(trial_fixations[color_by])
                else None
            )
            raw_cmax = trial_fixations[color_by].max() if raw_cmin is not None else None
            if pd.notna(raw_cmin) and pd.notna(raw_cmax):
                # Integer bounds + step so the range reads as whole numbers
                # (durations, surprisal, … all read cleaner as ints); values
                # stay floats so a restored config on different data clamps in.
                cmin = float(math.floor(raw_cmin))
                cmax = float(math.ceil(raw_cmax))
                cmax_eff = cmax if cmax > cmin else cmin + 1.0
                _clamp_range("global_fixation_color_range", cmin, cmax_eff)
                st.session_state.setdefault(
                    "global_fixation_color_range", (cmin, cmax_eff)
                )
                _range_slider(
                    st,
                    "Fixation color range",
                    label_left=True,
                    key="global_fixation_color_range",
                    persist_state="session",
                    min_value=cmin,
                    max_value=cmax_eff,
                    step=1.0,
                    slider_format="%d",
                    disabled=metric_disabled,
                    help=_gated_help(None, metric_reason),
                )
            show_order = st.checkbox(
                "Fixation index", key="global_show_order", persist_state="session"
            )
            if show_order:
                # In Compare (and in a dual animation) the index labels are tinted
                # to each scanpath's own colour, so the global colour is inert.
                _dis, _reason = _mode_gate(animating, comparing, **_no_compare)
                _labeled(
                    st,
                    "color_picker",
                    "Index label color",
                    key="global_order_font_color",
                    persist_state="session",
                    disabled=_dis,
                    help=_gated_help("Fixation-index label colour.", _reason),
                )
                _numeric_slider(
                    st,
                    "Index label size",
                    label_left=True,
                    key="global_order_font_size",
                    persist_state="session",
                    min_value=6,
                    max_value=72,
                    help="Fixation-index label size (figure pixels; the plot is "
                    "then scaled to fit the column, so on-screen it is a touch "
                    "smaller). Default 10.",
                )
            _hover_dis, _hover_reason = _mode_gate(animating, comparing, **_no_compare)
            _labeled(
                st,
                "multiselect",
                "Hover fields",
                options=hover_field_options(trial_fixations),
                key="global_fixation_hover_fields",
                persist_state="session",
                disabled=_hover_dis,
                help=_gated_help(
                    "Fields shown when hovering a fixation. Choose any retained "
                    "fixation column; order here is tooltip order.",
                    _hover_reason,
                ),
            )
            # When comparing two trials, the per-scanpath fixation styling lives
            # here (under the Fixation settings), not in a separate panel.
            if comparing:
                _render_compare_fix_styles()

    # VIZ-27: filtering decides which fixations are visible; it is not marker
    # appearance. Keep it beside the fixation layer as a first-class popover and
    # show a local badge so an active Discard cannot be forgotten. A chip in the
    # trial-fact strip was rejected because this is a view setting, not trial data.
    _flag_dis, _flag_reason = _mode_gate(animating, comparing, **_no_compare)
    if show_fix or fix_off_disabled:
        with fix_grp.popover(
            f"🧹 Filter{_fixation_filter_badge()}",
            width="stretch",
            help=_gated_help(
                "Highlight or hide short, long, and out-of-bounds fixations.",
                _flag_reason,
            ),
        ):
            # VIZ-27 follow-up: the index window removes fixations just like the
            # short/long/OOB rules, so it belongs here rather than under marker style.
            # The max follows the selected trial (BUG-16).
            _render_fix_range_slider(fix_range_fixations)
            _render_fixation_cleaning(disabled=_flag_dis, reason=_flag_reason)

    # --- Saccades ---------------------------------------------------------
    show_saccades = sac_grp.toggle(
        "**Visible**", key="global_show_saccades", persist_state="session"
    )
    if show_saccades:
        with sac_grp.popover("⚙️ Style", width="stretch"):
            # VIZ-23 gave `make_scanpath_animation` an arrow layer of its own
            # (each arrowhead un-masks with the saccade it belongs to), so
            # direction arrows now reach all three builders.
            st.checkbox(
                "Direction arrows",
                key="global_show_saccade_arrows",
                persist_state="session",
                help="Draw an arrowhead on each saccade pointing in the gaze "
                "direction. In **Animate** each arrow appears with its own "
                "saccade rather than all at once.",
            )
            # VIZ-8 / VIZ-19: uniform colour, the two-way forward-vs-regression
            # split, or the full reading-class breakdown. Reading-class colouring
            # is a `make_scanpath_figure` feature — the animation draws one
            # uniform saccade colour and the comparison overlay one colour per
            # scanpath — so the mode picker greys out in both.
            class_disabled, class_reason = _mode_gate(
                animating, comparing, **_static_only
            )
            color_mode = _labeled(
                st,
                "radio",
                "Saccade color",
                options=SACCADE_COLOR_MODES,
                key="global_saccade_color_mode",
                persist_state="session",
                disabled=class_disabled,
                help=_gated_help(
                    "**Uniform** — one colour for every saccade. **Forward / "
                    "regression** — the two-way split most reading figures want. "
                    "**By type** — the full reading-class breakdown (forward, "
                    "skip, refixation, return sweep, regression).",
                    class_reason,
                ),
            )
            # In Animate / Compare the class breakdown never draws, so fall back
            # to the uniform Line-colour control below rather than showing five
            # dead class swatches.
            if color_mode != "Uniform" and not class_disabled:
                # VIZ-19: the two-way mode reuses the same class colours, so
                # only show the pickers it actually draws with.
                classes = (
                    ["forward", "regression"]
                    if color_mode == "Forward / regression"
                    else SACCADE_CLASS_EDITABLE
                )
                st.caption(
                    "Each saccade is classed by where it lands relative to "
                    "the departing fixation."
                    if color_mode == "By type"
                    else "Every non-backward saccade counts as forward."
                )
                swatches = st.columns(len(classes))
                for col, cls_name in zip(swatches, classes):
                    state_key = f"global_saccade_class_color_{cls_name}"
                    col.color_picker(
                        SACCADE_CLASS_LABELS[cls_name],
                        key=state_key,
                    )
                st.checkbox(
                    "Show legend",
                    key="global_saccade_type_legend",
                    persist_state="session",
                    help="Show the saccade-type colour key on the plot. Turn "
                    "it off for a cleaner figure once the colours are learned.",
                )
            else:
                # The single uniform saccade colour: honoured by the static
                # figure and the animation; Compare paints each scanpath in its
                # own colour instead (see "Per-scanpath (comparison)" below).
                _dis, _reason = _mode_gate(animating, comparing, **_no_compare)
                _labeled(
                    st,
                    "color_picker",
                    "Line color",
                    key="global_saccade_color",
                    persist_state="session",
                    disabled=_dis,
                    help=_gated_help(
                        "Colour of the saccade lines and direction arrows.", _reason
                    ),
                )
            _dis, _reason = _mode_gate(animating, comparing, **_no_compare)
            _labeled(
                st,
                "segmented_control",
                "Saccade line style",
                options=list(SACCADE_DASH_OPTIONS.keys()),
                key="global_saccade_style",
                persist_state="session",
                disabled=_dis,
                help=_gated_help("Line style for the saccade traces.", _reason),
            )
            _numeric_slider(
                st,
                "Saccade line width",
                label_left=True,
                key="global_saccade_width",
                persist_state="session",
                min_value=SACCADE_WIDTH_BOUNDS[0],
                max_value=SACCADE_WIDTH_BOUNDS[1],
                step=0.5,
                slider_format="%.1f px",
                number_format="%.1f",
                disabled=_dis,
                help=_gated_help("Thickness of the saccade lines. Default 2.", _reason),
            )
            # VIZ-9: "linear reading" schematic — arched saccades. Its paired
            # control, "Snap fixations above words", lives under Fixations
            # (it moves fixations) in its own "Linear-reading schematic"
            # block — see UX-13. Arcs are a `make_scanpath_figure` feature.
            _labeled(
                st,
                "segmented_control",
                "Line shape",
                options=["Straight", "Arc"],
                key="global_saccade_render_mode",
                persist_state="session",
                disabled=class_disabled,
                help=_gated_help(
                    "Straight connectors, or upward **arcs** over the text "
                    "(the classic linear-reading diagram). Pairs with Fixations → "
                    "Fixations → ⚙️ Style → **Snap fixations above words**.",
                    class_reason,
                ),
            )
            # Per-scanpath saccade styling for the two-trial comparison.
            if comparing:
                _render_compare_saccade_styles()

    # VIZ-31: the Saccades section's *filter* sub-section, the counterpart to the
    # fixation one above — which reading classes are drawn at all, as opposed to
    # what colour they are drawn in. "Show only the regressions" is the figure a
    # reading paper asks for, and until now the only way to approximate it was to
    # colour the other four classes to match the background. Static-only for the
    # same reason the class *colouring* is: the classification never reaches the
    # animation or comparison builders (see CLAUDE.md's render-path table), so the
    # picker greys out there rather than silently dropping the filter.
    if show_saccades:
        _cls_dis, _cls_reason = _mode_gate(animating, comparing, **_static_only)
        with sac_grp.popover(
            f"🧹 Filter{_saccade_filter_badge()}",
            width="stretch",
            help=_gated_help(
                "Draw only some reading classes — forward, skip, refixation, "
                "return sweep, regression.",
                _cls_reason,
            ),
        ):
            _labeled(
                st,
                "multiselect",
                "Show saccade types",
                options=SACCADE_CLASS_ORDER,
                format_func=lambda cls: SACCADE_CLASS_LABELS[cls],
                key="global_saccade_classes",
                persist_state="session",
                disabled=_cls_dis,
                help=_gated_help(
                    "Hidden classes are dropped from the figure entirely — line "
                    "**and** direction arrow. Clearing the list means *no "
                    "filter*, not an empty plot; to hide the whole layer use the "
                    "↗️ Saccades **Visible** toggle above.",
                    _cls_reason,
                ),
            )
            st.caption(
                "Classes come from the same reading-class split as ⚙️ Saccade "
                "style → **By type**, so the two agree on what a regression is."
            )

    # --- Text -------------------------------------------------------------
    show_labels = stim_grp.toggle(
        "**Text**", key="global_show_labels", persist_state="session"
    )
    if show_labels:
        with stim_grp.popover("⚙️ Text & highlight", width="stretch"):
            # "Highlight a span" is an on/off toggle; the Mark-text / Mark-border
            # choice appears only when it's on (no "None" option). The canonical
            # value stays in `global_critical_span_style` ("Mark text" |
            # "Mark border" | "None") so deep-links / Share / restore are
            # unchanged — the toggle + mode widgets are derived from it each run,
            # and their callbacks write it back on interaction.
            canonical = st.session_state.get("global_critical_span_style", "Mark text")

            def _on_span_toggle():
                st.session_state["global_critical_span_style"] = (
                    st.session_state.get("global_highlight_span_mode", "Mark text")
                    if st.session_state["global_highlight_span_on"]
                    else "None"
                )

            def _on_span_mode():
                st.session_state["global_critical_span_style"] = st.session_state[
                    "global_highlight_span_mode"
                ]

            st.session_state["global_highlight_span_on"] = canonical != "None"
            if canonical in ("Mark text", "Mark border"):
                st.session_state["global_highlight_span_mode"] = canonical
            else:
                st.session_state.setdefault("global_highlight_span_mode", "Mark text")

            # VIZ-23: the span's *text*-marking channel now reaches all three
            # builders — the animation and the comparison figure take
            # `highlight_column` + `highlight_text_color` and recolour the word
            # labels. Neither has a border-overlay layer, though, so **Mark
            # border** stays a `make_scanpath_figure` feature and only its colour
            # picker is gated (`tabs._marked_text_column` hands the other two
            # builders `None` under that style, so nothing is marked there rather
            # than silently falling back to text marking).
            border_disabled, border_reason = _mode_gate(
                animating, comparing, **_static_only
            )
            span_on = st.toggle(
                "Highlight a span",
                key="global_highlight_span_on",
                persist_state="session",
                on_change=_on_span_toggle,
                help="Highlight a per-word span (e.g. the answer span) on the text.",
            )
            if span_on:
                # Which column defines the span first, then how to mark it.
                if highlight_options:
                    _labeled(
                        st,
                        "selectbox",
                        "Highlight words by",
                        options=highlight_options,
                        key="global_highlight_column",
                        persist_state="session",
                        help="Which per-word column to highlight on the text (words "
                        "where it is true). Defaults to the OneStop answer span.",
                    )
                critical_span_style = _labeled(
                    st,
                    "radio",
                    "Style",
                    options=["Mark text", "Mark border"],
                    horizontal=True,
                    key="global_highlight_span_mode",
                    persist_state="session",
                    on_change=_on_span_mode,
                    help="Mark text: colour the span's words. Mark border: draw a "
                    "thin outline around the span."
                    + (
                        "\n\n⚠️ **Mark border** draws on the static plot only — "
                        "the replay and the comparison figure have no border "
                        "layer, so the span shows unmarked there. Use **Mark "
                        "text** in those modes."
                        if border_disabled
                        else ""
                    ),
                )
            else:
                critical_span_style = "None"
            st.session_state["global_critical_span_style"] = critical_span_style
            if critical_span_style == "Mark text":
                _labeled(
                    st,
                    "color_picker",
                    "Highlighted text color",
                    key="global_highlight_text_color",
                    persist_state="session",
                    help="Colour of the highlighted reading text (used with "
                    "'Mark text').",
                )
            elif critical_span_style == "Mark border":
                _labeled(
                    st,
                    "color_picker",
                    "Border color",
                    key="global_span_border_color",
                    persist_state="session",
                    disabled=border_disabled,
                    help=_gated_help(
                        "Colour of the span outline (used with 'Mark border').",
                        border_reason,
                    ),
                )

            st.divider()
            _hover_dis, _hover_reason = _mode_gate(animating, comparing, **_no_compare)
            _labeled(
                st,
                "multiselect",
                "Hover fields",
                options=hover_field_options(words, words=True),
                key="global_word_hover_fields",
                persist_state="session",
                disabled=_hover_dis,
                help=_gated_help(
                    "Fields shown when hovering a word: identity, any reading "
                    "measure, linguistic feature, or retained metadata column.",
                    _hover_reason,
                ),
            )

    # --- Heatmap ----------------------------------------------------------
    # Compare supports a shared word-box scale: overlay splits each box into
    # A/B halves; side-by-side and stacked tint their respective full boxes.
    # Animation remains disabled because a time-varying density layer would
    # need a distinct frame contract.
    heat_disabled, heat_reason = _mode_gate(animating, comparing, in_animation=False)
    show_heatmap = ovl_grp.toggle(
        "**Heatmap**",
        key="global_show_heatmap",
        persist_state="session",
        disabled=heat_disabled,
        help=_gated_help("Tint the reading by fixation density.", heat_reason),
    )
    if show_heatmap:
        with ovl_grp.popover("⚙️ Heatmap style", width="stretch"):
            # A radio (not segmented_control) so the active style is always shown
            # selected from the seeded default — segmented_control could render
            # with nothing selected on first open.
            _labeled(
                st,
                "radio",
                "Heatmap style",
                options=["Word boxes", "Interpolated", "Duration mass"],
                horizontal=True,
                key="global_heatmap_style",
                persist_state="session",
                disabled=heat_disabled or comparing,
                help=_gated_help(
                    "Comparison always uses word boxes with one shared scale. "
                    "In overlay mode each box is split into A/B halves. "
                    "Word boxes: tint each word box by fixation count / duration. "
                    "Interpolated: a smooth Gaussian density over the fixations "
                    "themselves. Duration mass spreads dwell time across nearby "
                    "characters with a Gaussian.",
                    "Comparison heatmaps use split word boxes."
                    if comparing
                    else heat_reason,
                ),
            )
            if st.session_state.get("global_heatmap_style") == "Duration mass":
                _labeled(
                    st,
                    "number_input",
                    "Duration-mass sigma (characters)",
                    min_value=0.25,
                    max_value=10.0,
                    step=0.25,
                    key="global_duration_mass_sigma_chars",
                    persist_state="session",
                    disabled=heat_disabled,
                    help="Gaussian standard deviation measured in character widths.",
                )
            _popover_selectbox(
                "Heatmap colorscale",
                COLORSCALES,
                "global_heatmap_colorscale",
                disabled=heat_disabled,
                help=_gated_help(
                    "Colour palette for the density heatmap overlay.", heat_reason
                ),
            )
            _labeled(
                st,
                "radio",
                "Color scaling",
                options=["Linear", "Log"],
                horizontal=True,
                key="global_heatmap_norm",
                persist_state="session",
                disabled=heat_disabled,
                help=_gated_help(
                    "Linear maps colour straight to the value. Log maps to "
                    "log(1+value) — compresses heavy-tailed dwell times so a few very "
                    "hot words don't wash out the rest (VIZ-3).",
                    heat_reason,
                ),
            )
            heatmap_metric = _labeled(
                st,
                "selectbox",
                "Heatmap metric",
                options=["duration_ms", "counts"],
                disabled=heat_disabled,
                help=_gated_help(
                    "Heatmap can be raw counts or weighted by fixation duration.",
                    heat_reason,
                ),
                key="global_heatmap_metric",
                persist_state="session",
            )
            heat_data = (
                trial_fixations["duration_ms"]
                if heatmap_metric == "duration_ms"
                and "duration_ms" in trial_fixations.columns
                else None
            )
            if (
                heat_data is not None
                and len(heat_data) > 0
                and pd.notna(heat_data.min())
                and pd.notna(heat_data.max())
            ):
                hmin = float(math.floor(heat_data.min()))
                hmax = float(math.ceil(heat_data.max()))
                hmax_eff = hmax if hmax > hmin else hmin + 1.0
                _clamp_range("global_heatmap_color_range", hmin, hmax_eff)
                st.session_state.setdefault(
                    "global_heatmap_color_range", (hmin, hmax_eff)
                )
                _range_slider(
                    st,
                    "Heatmap color range",
                    label_left=True,
                    key="global_heatmap_color_range",
                    persist_state="session",
                    min_value=hmin,
                    max_value=hmax_eff,
                    step=1.0,
                    slider_format="%d",
                    disabled=heat_disabled,
                    help=_gated_help(
                        "Min/max heatmap value mapped to the two ends of the "
                        "colorscale (the metric above — fixation duration or count; "
                        "for Interpolated, the smoothed density of those values). "
                        "Lower the max for more contrast; raise it to compress.",
                        heat_reason,
                    ),
                )

    # --- Bounding boxes / Stimulus image / Raw gaze -----------------------
    stim_grp.toggle(
        "**Bounding boxes**", key="global_show_words", persist_state="session"
    )
    # VIZ-4: a stimulus image can come from the dataset (MultiplEYE stamps a
    # per-trial `image_path`) OR be uploaded here for any dataset (a full-monitor
    # screenshot of the reading screen). The upload's `data:` URI is stashed in
    # session for the tab to place + the (pure) collector to read; the toggle is
    # enabled whenever either source exists.
    uploaded_img = st.session_state.get("global_stimulus_image_upload")
    upload_uri = _uploaded_image_data_uri(uploaded_img)
    st.session_state["_stimulus_image_upload_uri"] = upload_uri
    can_show_image = has_stimulus_image or upload_uri is not None
    # VIZ-23: `background_image*` are now parameters of all three builders — the
    # comparison figure places one `layout.image` per panel in the split layouts —
    # so the whole stimulus-image group is live in every mode.
    show_stim_image = stim_grp.toggle(
        "**Stimulus image**",
        help="Show a stimulus page behind the scanpath — the dataset's rendered "
        "page (exact coordinates; sidesteps CJK / RTL font issues) or an image "
        "you upload below (stretched to fill the monitor). "
        + (
            ""
            if can_show_image
            else "(Upload one below, or load a dataset with images)"
        ),
        disabled=not can_show_image,
        key="global_show_stimulus_image",
        persist_state="session",
    )
    # Keep the popover reachable even while the toggle is off-and-disabled (no
    # image loaded yet) — its uploader is the only way to get an image in and
    # enable the toggle in the first place.
    if show_stim_image or not can_show_image:
        with stim_grp.popover("⚙️ Stimulus image", width="stretch"):
            st.file_uploader(
                "Upload a stimulus image",
                type=["png", "jpg", "jpeg", "gif", "webp"],
                # No persist_state: st.file_uploader does not take it, and an
                # UploadedFile is already stashed by _uploaded_image_data_uri.
                key="global_stimulus_image_upload",
                help="Use a screenshot of the reading screen as the background for "
                "any dataset. An upload **overrides** a dataset's built-in image and "
                "is stretched to fill the monitor; use the **Align to text** controls "
                "below to position/scale it. Not carried by Share links (upload it on "
                "the other end).",
            )
            _numeric_slider(
                st,
                "Image opacity",
                label_left=True,
                key="global_stimulus_image_opacity",
                persist_state="session",
                min_value=0.1,
                max_value=1.0,
                step=0.05,
                number_format="%.2f",
                help="Dim the stimulus image so the fixations, saccades and word "
                "boxes stand out over it (1.0 = fully opaque).",
            )
            # VIZ-4: manual alignment. The text was shown at some position on the
            # screen; when the data's coordinates don't match the image exactly, nudge
            # the image (X/Y px) and scale it to line it up with the word boxes and
            # fixations. Applies to dataset and uploaded images alike.
            st.caption("**Align to text** — nudge/scale the image to fit the boxes.")
            # UX-51: the two offsets used to share a `st.columns(2)` row purely to
            # save a line. They are ordinary `label | field` rows now, which costs
            # the same height (one line each instead of one two-line row) and lets
            # them line up with the opacity and scale sliders around them.
            _labeled(
                st,
                "number_input",
                "Image X offset (px)",
                step=5.0,
                key="global_stimulus_image_offset_x",
                persist_state="session",
                help="Shift the image horizontally to line it up with the text.",
            )
            _labeled(
                st,
                "number_input",
                "Image Y offset (px)",
                step=5.0,
                key="global_stimulus_image_offset_y",
                persist_state="session",
                help="Shift the image vertically to line it up with the text.",
            )
            _numeric_slider(
                st,
                "Image scale",
                label_left=True,
                key="global_stimulus_image_scale",
                persist_state="session",
                min_value=0.25,
                max_value=3.0,
                step=0.05,
                number_format="%.2f",
                help="Scale the image up/down so its text matches the word boxes "
                "(1.0 = the image's native / dataset size).",
            )
    # Raw gaze is a `make_scanpath_figure`-only overlay.
    raw_disabled, raw_reason = _mode_gate(animating, comparing, **_static_only)
    ovl_grp.toggle(
        "**Raw gaze data**",
        help=_gated_help(
            "Display millisecond-level gaze positions as small dots. "
            + ("" if has_raw_gaze else "(No raw gaze data loaded)"),
            raw_reason,
        ),
        disabled=not has_raw_gaze or raw_disabled,
        key="global_show_raw_gaze",
        persist_state="session",
    )
    # DATA-15: the bundled demo's raw gaze is SYNTHESIZED from the fixation
    # report (OneStop ships no sample-level gaze) — it looks like eye-tracker
    # output and isn't, so say so wherever it can be switched on.
    if (
        has_raw_gaze
        and st.session_state.get("data_source_choice") == DEMO_CHOICE
        and st.session_state.get("global_show_raw_gaze")
    ):
        ovl_grp.caption(
            "⚠️ The demo's raw gaze is **synthesized** from its fixations for "
            "illustration — it is not recorded eye-tracker output."
        )

    # --- Figure & canvas --------------------------------------------------
    # UX-48: this group merged two former sections (canvas/text + axes/labels)
    # and read as one ~26-row flat run — two `**bold caption**` lines were the
    # only structure in it. It now follows the same shape as every layer group:
    # ONE headline control inline, everything else behind named popovers.
    #
    #   **Show full monitor**   (inline — the framing decision, cheap to reach)
    #   🖥️ Screen & geometry    ┐ rendered by `canvas_renderer`
    #   🔤 Text & fonts         ┘ (app.render_sidebar_canvas_controls, bare mode)
    #   📊 Axes & grid          ┐ rendered here
    #   🏷️ Title & labels       ┘
    #
    # The two containers below are created up front so each block keeps its place
    # in this file while rendering into its own sub-group (same trick as the
    # section expanders above). Popovers, not expanders, because Streamlit nests
    # neither expander-in-expander nor popover-in-popover — and this group is
    # already an expander.
    figure_grp.toggle(
        "**Show full monitor**",
        key="global_fit_to_monitor",
        persist_state="session",
        help="Frame the whole presentation monitor so the scanpath sits where it "
        "appeared on screen. Turn off to crop the view tightly to the data.",
    )
    # The renderer is bound by app.main and writes its canvas/text sub-groups
    # directly into the shared disclosure, followed by the figure/axis ones.
    if canvas_renderer is not None:
        canvas_renderer(figure_grp)

    # The plot frame itself: the coordinate grid, the colour bar and which
    # fixation columns the two axes plot.
    axes = figure_grp.popover("📊 Axes & grid", width="stretch")
    # Everything the figure says in words: the Illustration disclosure label and
    # the EXP-5 title/caption.
    labels = figure_grp.popover("🏷️ Title & labels", width="stretch")

    show_coordinate_grid = axes.toggle(
        "Coordinate grid",
        key="global_show_coordinate_grid",
        persist_state="session",
        help="Overlay screen X/Y coordinates in monitor pixels. The grid uses "
        "the same inverted-Y coordinate frame as word boxes and fixations.",
    )
    if show_coordinate_grid:
        automatic_grid = axes.toggle(
            "Automatic grid spacing",
            key="global_coordinate_grid_auto",
            persist_state="session",
            help="Choose a readable 1/2/5×10ⁿ interval from the visible range. "
            "Turn off to pin a reproducible pixel interval.",
        )
        if not automatic_grid:
            _labeled(
                axes,
                "number_input",
                "Major grid interval (px)",
                min_value=10.0,
                max_value=5000.0,
                step=10.0,
                key="global_coordinate_grid_spacing",
                persist_state="session",
                help="Major labels and lines repeat at this pixel interval; "
                "minor lines divide it into fifths.",
            )
    show_colorbars = axes.checkbox(
        "Show color bars", key="global_show_colorbars", persist_state="session"
    )
    if show_colorbars:
        # VIZ-23: all three builders now route their colour bar through
        # `_colorbar_dict`, so the styling below applies wherever a colour bar is
        # actually drawn. The one mode without one is the DUAL animation (Animate
        # + Compare) — there the flat A/B colours replace metric colouring
        # entirely, so there is no bar to style. Same gate as "Color fixations by".
        cb_disabled, cb_reason = _mode_gate(
            animating, comparing, in_animation=not comparing
        )
        _labeled(
            axes,
            "radio",
            "Color bar orientation",
            options=["Vertical", "Horizontal"],
            horizontal=True,
            key="global_colorbar_orientation",
            persist_state="session",
            disabled=cb_disabled,
            help=_gated_help(
                "Vertical bar on the right, or a horizontal bar below the plot.",
                cb_reason,
            ),
        )
        _numeric_slider(
            axes,
            "Tick label angle",
            label_left=True,
            key="global_colorbar_tickangle",
            persist_state="session",
            min_value=-90,
            max_value=90,
            step=15,
            disabled=cb_disabled,
            help=_gated_help("Rotate the color-bar tick labels (degrees).", cb_reason),
        )
        _numeric_slider(
            axes,
            "Tick label size",
            label_left=True,
            key="global_colorbar_tickfont_size",
            persist_state="session",
            min_value=6,
            max_value=20,
            disabled=cb_disabled,
            help=_gated_help("Color-bar tick-label font size (px).", cb_reason),
        )
    # The animation and the comparison figures always plot spatial x/y — only
    # `make_scanpath_figure` takes `x_field`/`y_field`.
    axis_disabled, axis_reason = _mode_gate(animating, comparing, **_static_only)
    _labeled(
        axes,
        "selectbox",
        "X axis field",
        options=numeric_fields,
        key="global_x_field",
        persist_state="session",
        disabled=axis_disabled,
        help=_gated_help(
            "Fixation column plotted on the X axis (default `x`).", axis_reason
        ),
    )
    _labeled(
        axes,
        "selectbox",
        "Y axis field",
        options=numeric_fields,
        key="global_y_field",
        persist_state="session",
        disabled=axis_disabled,
        help=_gated_help(
            "Fixation column plotted on the Y axis (default `y`).", axis_reason
        ),
    )

    # EXP-5: title/caption on the figure — moved here from being Export-only
    # (EXP-2), so it's visible live rather than a setting a user has to remember
    # to go find under Export. This is now the single source of truth: the
    # Export panel's bulk section reads these two patterns back instead of
    # keeping its own copy, and the live figure on screen (all three render
    # paths) carries the same title/caption a bulk export would produce.
    def _on_toggle_title_caption() -> None:
        # Pre-fill a friendly starting pattern the first time this is switched
        # on, rather than an empty box the user has to know the field syntax
        # to fill in. `_seed_viz_state`'s `_pin` already seeded both keys to
        # "" earlier this run, so a plain `setdefault` below would be a no-op —
        # this has to run as the toggle's own callback (before that seeding
        # happens on the next rerun) to actually take.
        if st.session_state.get("global_show_title_caption"):
            if not st.session_state.get("global_title_pattern"):
                st.session_state["global_title_pattern"] = DEFAULT_TITLE_PATTERN
            if not st.session_state.get("global_caption_pattern"):
                st.session_state["global_caption_pattern"] = DEFAULT_CAPTION_PATTERN

    _labeled(
        labels,
        "selectbox",
        "Illustration label",
        options=["Auto", "Show", "Hide"],
        key="global_illustration_label",
        persist_state="session",
        help="Auto labels figures when geometry or data is transformed. Show "
        "forces the label; Hide is an explicit publication override.",
    )
    show_title_caption = labels.toggle(
        "Title & caption on the figure",
        key="global_show_title_caption",
        persist_state="session",
        on_change=_on_toggle_title_caption,
        help="Render a title and/or caption into the figure — on screen, in "
        "**This trial** export, and in a bulk export — so a figure dropped "
        "into a paper or a slide carries its own provenance. The plot itself "
        "is not scaled down; the figure grows to make room.",
    )
    if show_title_caption:
        _title_caption_fields = pattern_fields(
            "p01",
            "t01",
            words if words is not None else pd.DataFrame(),
            trial_fixations if trial_fixations is not None else pd.DataFrame(),
            {},
        )
        # EXP-5: two text boxes, two previews and a field list is far too tall
        # for the rail — inline it ran "very long and narrow", so it opened in a
        # nested ⚙️ popover. UX-48 made the *group* a popover instead, and
        # Streamlit won't nest popover-in-popover — the pattern boxes are simply
        # inline here now, where the overlay's width is the point.
        box = labels.container()
        render_pattern_input(
            box,
            "Title",
            "global_title_pattern",
            _title_caption_fields,
            # No placeholder here, unlike the Compare A/B labels: a
            # placeholder promises "this is what an empty box gives you",
            # and an empty box here gives *no title at all*. Both boxes are
            # pre-filled with the defaults on the run the toggle is switched
            # on, so there is nothing an empty one needs to explain (UX-31).
            help="Leave empty for no title.",
            label_left=True,
        )
        render_pattern_input(
            box,
            "Caption",
            "global_caption_pattern",
            _title_caption_fields,
            help="Leave empty for no caption.",
            label_left=True,
        )
        render_pattern_help(box, _title_caption_fields)

    # Build the dict from session_state so it matches viz_settings_from_state
    # exactly; then fill in the per-scanpath comparison styling, shown only when
    # the Compare toggle (rail plot-controls section) is on, so all styling sits here.
    settings = _collect_viz_settings(
        trial_fixations,
        words,
        numeric_fields=numeric_fields,
        highlight_options=highlight_options,
    )
    # The per-scanpath comparison styling is rendered inline under each layer's
    # popover (Fixation / Saccade) above; here we just collect it from the keys.
    if st.session_state.get("single_compare_toggle"):
        settings["compare_style_a"], settings["compare_style_b"] = (
            _collect_compare_styles()
        )
    return settings


# Cached option-list scans for the sidebar filter panel. These run on every
# rerun to populate the multiselects; caching them on a cheap frame fingerprint
# keeps them off the hot path on large corpora (full-column unique() scans).
@st.cache_data(show_spinner=False)
def _participant_options(
    _words: pd.DataFrame, _fixations: pd.DataFrame, cache_key
) -> list[str]:
    return sorted(
        set(_words["participant_id"].dropna().astype(str))
        | set(_fixations["participant_id"].dropna().astype(str))
    )


@st.cache_data(show_spinner=False)
def _column_unique_strs(_df: pd.DataFrame, column: str, cache_key) -> list[str]:
    if column not in _df.columns:
        return []
    # Drop missing values, including the literal "nan" a string-coerced optional
    # field leaves for NaN (e.g. ET2 readers with no recorded gender) — a "nan"
    # filter option would be meaningless.
    values = _df[column].dropna().astype(str).unique()
    return sorted(v for v in values if v.strip().lower() not in ("nan", "none", "<na>"))


@st.cache_data(show_spinner=False)
def _numeric_column_bounds(_df: pd.DataFrame, column: str, cache_key):
    """``(lo, hi, distinct)`` over a column's **finite** values, or ``None``.

    UX-49's slider needs finite bounds and at least two distinct values — a
    one-option range control is the same family as the single-option
    ``st.select_slider`` that throws ``RangeError`` in the browser. ``None`` here
    means "render no slider", not "render a degenerate one". Infinities are
    dropped along with NaN: one ``inf`` would otherwise pin the whole slider.

    A full-column scan, hence the cache — keyed on the frame fingerprint by the
    caller, exactly like ``_column_unique_strs``.
    """
    if column not in _df.columns:
        return None
    values = pd.to_numeric(_df[column], errors="coerce")
    finite = values[np.isfinite(values)] if len(values) else values
    if finite.empty:
        return None
    distinct = int(finite.nunique())
    if distinct < 2:
        return None
    lo, hi = finite.min(), finite.max()
    # A whole-numbered column gets whole-numbered bounds, so the slider steps in
    # 1s and reads "3 – 17" rather than "3.00 – 17.00". Streamlit picks int vs
    # float behaviour from the *type* of min_value/max_value, so the decision has
    # to be made here, on the data. `%` on a float that happens to be whole (an
    # int column with NaNs is float64) counts as whole — the point is the values,
    # not the dtype pandas landed on.
    if bool((finite % 1 == 0).all()):
        return int(lo), int(hi), distinct
    return float(lo), float(hi), distinct


@st.cache_data(show_spinner=False)
def _trials_missing_column(_df: pd.DataFrame, column: str, cache_key) -> int:
    """How many trials carry no numeric value for ``column``.

    Counted in *trials*, not rows, because that is the unit the filter keeps or
    drops — and it is what makes the "kept anyway" caption honest.
    """
    if column not in _df.columns or "trial_id" not in _df.columns:
        return 0
    keys = (
        ["participant_id", "trial_id"]
        if "participant_id" in _df.columns
        else ["trial_id"]
    )
    values = pd.to_numeric(_df[column], errors="coerce")
    usable = pd.DataFrame({"_v": np.isfinite(values)})
    for k in keys:
        usable[k] = _df[k].astype(str).to_numpy()
    per_trial = usable.groupby(keys, dropna=False)["_v"].any()
    return int((~per_trial).sum())


@st.cache_data(show_spinner=False)
def _column_present_bools(_df: pd.DataFrame, column: str, cache_key) -> frozenset:
    if column not in _df.columns:
        return frozenset()
    return frozenset(
        bool(v) for v in pd.Series(_df[column]).dropna().astype(bool).unique()
    )


def _bool_metadata_filter(
    label: str,
    col: str,
    df: pd.DataFrame,
    true_label: str,
    false_label: str,
    key: str,
    host,
    on_change=None,
) -> None:
    """Render a friendly multiselect for a boolean metadata column.

    Rendering only — the narrowing value is derived from the widget key by
    ``_compute_trial_filters``. Renders nothing when the column is absent or has
    fewer than two classes."""
    if col not in df.columns:
        return
    present = _column_present_bools(df, col, cache_key=(frame_fingerprint(df), col))
    label_to_val = {true_label: True, false_label: False}
    options = [lbl for lbl, val in label_to_val.items() if val in present]
    if len(options) < 2:
        return
    _seed_filter_widget(key, options, options)
    _labeled(host, "multiselect", label, options=options, key=key, on_change=on_change)


def _bool_filter_narrowing(
    col: str, df: pd.DataFrame, true_label: str, false_label: str, key: str
) -> set | None:
    """The set of raw bool values to keep for a boolean metadata column, read
    from its widget key — or None when absent / fewer than two classes / the user
    kept everything (no narrowing). The read-side twin of ``_bool_metadata_filter``."""
    if col not in df.columns:
        return None
    present = _column_present_bools(df, col, cache_key=(frame_fingerprint(df), col))
    label_to_val = {true_label: True, false_label: False}
    options = [lbl for lbl, val in label_to_val.items() if val in present]
    if len(options) < 2:
        return None
    chosen = st.session_state.get(key)
    if not chosen or set(chosen) == set(options):
        return None
    vals = {label_to_val[c] for c in chosen if c in label_to_val}
    return vals or None


# Friendly labels for well-known trial-level condition columns. Any other field
# the user picks as a filter just uses its column name + raw values.
_FILTER_FIELD_LABELS = {
    "question_preview": {
        "label": "Reading regime",
        "true": "Hunting",
        "false": "Gathering",
    },
    "repeated_reading_trial": {
        "label": "Reading number",
        "true": "Repeated",
        "false": "First",
    },
    "is_correct": {"label": "Answer", "true": "Correct", "false": "Incorrect"},
    "difficulty_level": {"label": "Difficulty"},
}

# Built-in sources (no wizard) auto-offer these known trial-level conditions when
# present; the Upload source uses the fields the user chose in the wizard.
_DEFAULT_FILTER_FIELDS = [
    "question_preview",
    "difficulty_level",
    "repeated_reading_trial",
    "is_correct",
    # UX-49: the offered set is otherwise all-categorical, which left the range
    # slider invisible on every bundled and public corpus. Presentation order is
    # the one numeric trial-level field that is both universal (EyeLink writes it
    # on every export) and worth filtering on — it is how you exclude the start
    # or the tail of a session when you suspect practice or fatigue effects.
    "TRIAL_INDEX",
    # MultiplEYE facets (present only when that corpus is loaded).
    "genre",
    "session",
    "is_practice",
]


_EMPTY_TRIAL_FILTERS: dict = {
    "participants": None,
    "metadata": {},
    # UX-49: column → (lo, hi) for the numeric trial-level range filters. Kept
    # apart from `metadata` because that one is membership (`.isin`) and
    # enumerating a float column's values is exactly what doesn't work.
    "ranges": {},
    # DATA-20: widget keys behind a participant-grain metadata narrowing (which
    # lands in `participants`, not `metadata`), so UX-7's per-filter clear can
    # reset the control that actually caused it.
    "participant_filter_keys": (),
    "favorites_only": False,
    "required_tags": [],
    "excluded_tags": [],
}


#: Every filter-layer namespace in the app. ``""`` is the main trial pool;
#: ``"cmp"`` is compare mode's scanpath B (CMP-8 §5.2). The empty prefix's
#: clear-sweep uses this to know which keys are *not* its own — without it,
#: "Clear all filters" on A would wipe B too, since ``"filter_"`` is a prefix of
#: ``"cmpfilter_"``. Register a new instance here, not just at its call site.
FILTER_PREFIXES: tuple = ("", "cmp")


def read_trial_filters(prefix: str = "") -> dict:
    """The trial-filter selections to apply this run.

    ``prefix`` scopes the whole filter layer to one instance (CMP-8 §5.2). The
    default ``""`` is the main pool and leaves every existing call site
    byte-identical; compare mode's scanpath **B** renders with ``prefix="cmp"``
    so it can be narrowed on *its own* dataset's columns, which A's filters may
    not even have.

    Computed last run by ``render_trial_filters`` and stashed in a *plain*
    session_state value (not a widget key), so it survives runs where the filter
    panel itself isn't rendered — e.g. when a non-Scanpath view is active under
    the sidebar nav. ``main()`` reads this *before* the tab renders, so filtering
    stays global even though the controls now live in the Trial Selection panel.
    """
    return dict(st.session_state.get(f"{prefix}_trial_filters", _EMPTY_TRIAL_FILTERS))


def clear_trial_filters(prefix: str = "") -> None:
    """Reset every trial filter to "no constraint" (UX-7's one-click escape).

    All of them — the Narrow-by multiselects, the More-popover condition filters,
    and the annotation filters — live under the ``filter_`` key prefix, so
    dropping those keys is the whole reset: each widget re-seeds to its own empty
    default (an empty multiselect means *no* narrowing) on the next render. The
    derived results and the cross-view mirror are cleared with them so the same
    run already sees an unfiltered pool.

    Safe to call as a button ``on_click``: callbacks run before the rerun
    instantiates the widgets, so removing their keys doesn't trip Streamlit's
    "set after instantiation" guard.
    """
    for key in _own_filter_keys(prefix):
        del st.session_state[key]
    st.session_state.pop(f"{prefix}_trial_filters", None)
    st.session_state.pop(f"{prefix}_trial_filters_raw", None)


def _own_filter_keys(prefix: str) -> list:
    """Filter widget keys belonging to ``prefix`` and to no *longer* prefix.

    The sweep used to be prefix-blind, which is fine while there is one filter
    set and wrong the moment there are two: ``"filter_"`` is a prefix of
    ``"cmpfilter_"``, so clearing A's filters would silently wipe B's as well.
    Matching forwards is not enough — the empty prefix has to explicitly skip
    keys carrying a known namespace.
    """
    own = f"{prefix}filter_"
    foreign = tuple(f"{p}filter_" for p in FILTER_PREFIXES if p and p != prefix)
    return [
        k
        for k in list(st.session_state)
        if str(k).startswith(own) and not (prefix == "" and str(k).startswith(foreign))
    ]


def reset_viz_settings() -> None:
    """Put every visualization setting back to the app's defaults (UX-26).

    The mechanism is ``clear_trial_filters``' — delete the widget keys and let
    each control re-seed from ``_VIZ_WIDGET_DEFAULTS`` (plus the data-dependent
    defaults `_seed_viz_state` computes) on the next render — so it must run as a
    button ``on_click``: callbacks run before the rerun instantiates the widgets,
    which is what keeps deleting their keys clear of Streamlit's "set after
    instantiation" guard.

    The key set is the honest inventory of what *visualization settings* means:
    every ``global_*`` key, the per-scanpath compare styles
    (``session_keys.compare_state_keys``), and the fixation-window pair the rail
    owns. ``session_keys.PLOT_CONFIG_STATE_KEYS`` is folded in so a setting that
    is restorable-but-not-currently-rendered is reset too. Deliberately NOT
    touched: the trial selection, the annotations (user-authored content, not a
    setting), the column mapping, and the data source.

    Deep links re-apply: ``url_state._apply_url_preset`` seeds from
    ``st.query_params`` at the top of every rerun, so on a page opened from a
    Share link, deleting the keys alone would let the link reinstate itself on
    the very next run. The viz params are stripped from the query string here;
    the selection params (source / participant / trial) are left, so a reset
    keeps you on the trial you were looking at.
    """
    from . import session_keys as _sk

    keys = set(_sk.PLOT_CONFIG_STATE_KEYS)
    keys |= set(_sk.compare_state_keys(0)) | set(_sk.compare_state_keys(1))
    keys |= {k for k in st.session_state if str(k).startswith("global_")}
    keys |= {"single_fix_range", "single_fix_range_all_trials"}
    for key in keys:
        st.session_state.pop(key, None)
    # Re-seeding is source-driven for these two (see app.seed_canvas_state);
    # dropping the guard makes the canvas / font snap back to the source's
    # authoritative monitor on the next run rather than sticking at the old size.
    st.session_state.pop("_canvas_seeded_for", None)
    st.session_state.pop("_font_seeded_for", None)
    st.session_state.pop("_palette_picked", None)
    st.session_state.pop(_PRE_ILLUSTRATION_STATE, None)
    for param in _sk.URL_PRESET_PARAMS:
        st.query_params.pop(param, None)


def clear_trial_filter(*keys: str, prefix: str = "") -> None:
    """Reset *one* trial filter (UX-7) — the same mechanism as the reset-all.

    Deleting the widget's key is the correct reset for every filter shape here,
    because each re-seeds to its own "no constraint" default on the next render:
    an empty multiselect for Narrow-by, *all* values selected for a condition,
    unchecked for Favorites. Safe as a button ``on_click`` for the same reason
    :func:`clear_trial_filters` is.
    """
    for key in keys:
        st.session_state.pop(key, None)
    st.session_state.pop(f"{prefix}_trial_filters", None)
    st.session_state.pop(f"{prefix}_trial_filters_raw", None)


def has_active_trial_filters(prefix: str = "") -> bool:
    """Whether any trial filter is currently narrowing the pool."""
    f = read_trial_filters(prefix)
    return bool(
        # `[]` is a narrowing that matched nobody — the *most* active a filter
        # can be. `None` is the no-constraint default.
        f.get("participants") is not None
        or f.get("metadata")
        or f.get("ranges")
        or f.get("favorites_only")
        or f.get("required_tags")
        or f.get("excluded_tags")
    )


# --- Trial summary chips (the "Field = Value" strip above the plot) ----------
_CHIP_TEXT_ID_COLS = (
    "unique_text_id",
    "text_id",
    "unique_paragraph_id",
    "paragraph_id",
)
# Sensible default chips: trial identity + the common OneStop conditions + the
# computed trial-level summary stats (which the chips replaced the Trial Info tab
# with). The "@"-prefixed keys are virtual fields computed per trial in
# `tabs._render_trial_condition_chips` (see SUMMARY_CHIP_FIELDS).
_CHIP_DEFAULT_CONDITIONS = [
    "difficulty_level",
    "question_preview",
    "repeated_reading_trial",
    "is_correct",
    # MultiplEYE facets + reader metadata (present only for that corpus).
    "genre",
    "session",
    "pp_age",
    "pp_gender",
]
# Virtual chip fields → label. These are computed per trial (not data columns),
# always trial-level, and folded in from the former Trial Info tab's summary.
SUMMARY_CHIP_FIELDS = {
    "@reading_time_s": "Total reading time (s)",
    "@word_count": "Number of words",
    "@fixation_count": "Number of fixations",
    "@in_text_fixations": "Fixations in word boxes",
}


def _trial_level_columns(words: pd.DataFrame, fixations: pd.DataFrame) -> set:
    """Columns that are constant within a trial (so a single chip value is
    meaningful), sampled from the first trial only — cheap, and trial-level-ness
    is essentially a property of the dataset, not the specific trial. A column
    counts as trial-level when it has ≤1 distinct value within that sample trial.
    """
    level: set = set()
    src = fixations if (fixations is not None and not fixations.empty) else words
    if (
        src is None
        or src.empty
        or "participant_id" not in src.columns
        or "trial_id" not in src.columns
    ):
        return level
    pid, tid = str(src["participant_id"].iloc[0]), str(src["trial_id"].iloc[0])
    for frame in (words, fixations):
        if (
            frame is None
            or frame.empty
            or "participant_id" not in frame.columns
            or "trial_id" not in frame.columns
        ):
            continue
        sub = frame[
            (frame["participant_id"].astype(str) == pid)
            & (frame["trial_id"].astype(str) == tid)
        ]
        if sub.empty:
            continue
        for col in sub.columns:
            if sub[col].nunique(dropna=True) <= 1:
                level.add(col)
    return level


def _chip_field_options(words, fixations, trial_level: set) -> list[str]:
    """Pickable chip fields: participant + a text id + the data's *trial-level*
    columns + the computed summary fields. Non-trial-level columns (per-word /
    per-fixation) are intentionally excluded — a single chip value for them would
    be misleading."""
    cols: list[str] = []

    def add(c: str) -> None:
        if c and c not in cols:
            cols.append(c)

    if "participant_id" in words.columns or "participant_id" in fixations.columns:
        add("participant_id")
    add(next((c for c in _CHIP_TEXT_ID_COLS if c in words.columns), ""))
    for c in list(words.columns) + list(fixations.columns):
        if c in trial_level:
            add(c)
    # DATA-20: participant-grain metadata is constant within a trial by
    # construction, so it belongs in this list on exactly the same terms as a
    # trial-level recorded column — no allowlist of its own.
    for field in participant_metadata_fields():
        add(field.name)
    cols.extend(SUMMARY_CHIP_FIELDS)
    return cols


def _chip_option_label(col: str) -> str:
    """Display label for a chip-field option (identity / virtual / humanized)."""
    if col in SUMMARY_CHIP_FIELDS:
        return SUMMARY_CHIP_FIELDS[col]
    if col == "participant_id":
        return "Participant"
    if col in _CHIP_TEXT_ID_COLS:
        return "Text"
    return col.replace("_", " ").strip().capitalize()


def _default_chip_fields(available: list[str]) -> list[str]:
    text_col = next((c for c in _CHIP_TEXT_ID_COLS if c in available), None)
    wanted = (
        ["participant_id"]
        + ([text_col] if text_col else [])
        + _CHIP_DEFAULT_CONDITIONS
        + list(SUMMARY_CHIP_FIELDS)
    )
    return [f for f in wanted if f in available]


def render_trial_chip_picker(
    words: pd.DataFrame, fixations: pd.DataFrame, host
) -> None:
    """Render the inline **Edit chips** control: choose which ``Field = Value``
    chips appear above the scanpath and **drag to reorder** them (UX-1 / UX-1a).

    Two drag buckets — *Shown* (in display order) and *Available* — via
    ``streamlit_sortables.sort_items``: drag a field between buckets to show / hide
    it, and within *Shown* to reorder. The resulting order is written to the plain
    session key ``trial_chip_fields`` (read by ``tabs._render_trial_condition_chips``).

    Only *trial-level* fields are offered (constant within a trial) plus the
    computed summary stats, so a chip never shows a per-word column whose single
    value would mislead. The trial-level set is computed once (sampling the first
    trial) and cached per column-signature; a **Refresh** button recomputes it.
    Default seeded once (participant + text + common conditions + summary)."""
    # Cached per column-signature (stable across trials / filters within a
    # dataset), recomputed on a dataset/column change or Refresh. Shared with
    # UX-49's range filters, which gate on the same answer.
    # DATA-20: the field universe now also depends on the attached participant
    # registry, so it has to be part of the signature — attaching or detaching a
    # table changes what the picker offers, and without this the component kept
    # a drag order built from the old set.
    signature = (
        tuple(words.columns),
        tuple(fixations.columns),
        tuple(field.name for field in participant_metadata_fields()),
    )
    available = _chip_field_options(
        words, fixations, cached_trial_level_columns(words, fixations)
    )
    if not available:
        return

    # Display labels must be unique to stay invertible: some fields humanize to the
    # same text (e.g. two text-id columns both read "Text"), so disambiguate.
    label_to_key: dict[str, str] = {}
    key_to_label: dict[str, str] = {}
    for key in available:
        base = _chip_option_label(key)
        label = base if base not in label_to_key else f"{base} ({key})"
        label_to_key[label] = key
        key_to_label[key] = label

    # Current selection/order, pruned to what's available + seeded once.
    if "trial_chip_fields" in st.session_state:
        st.session_state["trial_chip_fields"] = [
            f for f in st.session_state["trial_chip_fields"] if f in available
        ]
    st.session_state.setdefault("trial_chip_fields", _default_chip_fields(available))
    selected = list(st.session_state["trial_chip_fields"])
    hidden = [k for k in available if k not in selected]

    host.caption(
        "Drag fields between **Shown** and **Available**, and reorder within "
        "**Shown** — these chips appear above the scanpath."
    )
    buckets = [
        {
            "header": "Shown · drag to reorder",
            "items": [key_to_label[k] for k in selected],
        },
        {"header": "Available", "items": [key_to_label[k] for k in hidden]},
    ]
    with host:
        # Key varies with the field universe so the component re-mounts (rather than
        # keeping a stale drag order) when the dataset / columns change.
        result = sort_items(
            buckets,
            multi_containers=True,
            direction="vertical",
            key=f"trial_chip_sort_{abs(hash(signature))}",
        )
    shown_labels = result[0]["items"] if result else []
    st.session_state["trial_chip_fields"] = [
        label_to_key[lbl] for lbl in shown_labels if lbl in label_to_key
    ]
    host.button(
        "🔄 Refresh fields",
        key="trial_chip_refresh",
        help="Re-scan which fields are trial-level (if the offered list looks off "
        "for the current data).",
        on_click=lambda: st.session_state.pop("_trial_level_cache", None),
    )

    # UX-28: per-chip colour, generalized from what used to be a handful of
    # hardcoded OneStop column/value special-cases (tabs._chip_color) — any
    # dataset's condition chips can now be highlighted, not just OneStop's.
    # `#EEF2F7` must match `tabs._CHIP_NEUTRAL_BG`: picking it back is how a
    # chip returns to "no override" rather than staying pinned to a colour.
    _neutral = "#EEF2F7"
    shown_now = st.session_state["trial_chip_fields"]
    if shown_now:
        host.caption("Chip colours — optional highlight per shown field.")
        colors = dict(st.session_state.get("trial_chip_colors") or {})
        for key in shown_now:
            label_col, swatch_col = host.columns([3, 1], vertical_alignment="center")
            label_col.caption(key_to_label[key])
            picked = swatch_col.color_picker(
                key_to_label[key],
                value=colors.get(key) or _neutral,
                key=f"trial_chip_color_{key}",
                label_visibility="collapsed",
                help="Pick back to the default grey to remove the highlight.",
            )
            if picked.lower() == _neutral.lower():
                colors.pop(key, None)
            else:
                colors[key] = picked
        st.session_state["trial_chip_colors"] = colors


def _seed_filter_widget(
    key: str, options: list, default: list, *, prefix: str = ""
) -> None:
    """Pre-seed a filter widget's state from the persistent mirror.

    Filter controls live in the Scanpath tab body, which doesn't render on every
    run (other views under the sidebar nav). Streamlit clears a not-rendered
    widget's key, so on return we re-seed it from ``_trial_filters_raw`` (the last
    selections), dropping any value no longer in ``options`` (e.g. after a dataset
    switch). Setting the key *before* the widget renders avoids the
    default-plus-session-state warning."""
    if key in st.session_state:
        return
    mirror = st.session_state.get(f"{prefix}_trial_filters_raw", {})
    if key in mirror:
        kept = [v for v in mirror[key] if v in options]
        st.session_state[key] = kept if kept else list(default)
    else:
        st.session_state[key] = list(default)


def _seed_range_widget(col: str, lo, hi, *, prefix: str = "") -> None:
    """Pre-seed a range slider from the persistent mirror, clamped to the column.

    The range twin of :func:`_seed_filter_widget`, and it needs its own because
    the stored value is a *pair*, not a list of options to intersect. A stored
    range outside the current column's extent (a dataset switch, or a filter that
    shrank the pool) is clamped rather than dropped, so the slider never renders
    a value Streamlit would reject.

    The seeded pair keeps ``lo``/``hi``'s own type: Streamlit reads int-vs-float
    slider behaviour off the values, so seeding ``(0.0, 10.0)`` for an integer
    column would put it back on decimal steps.
    """
    cast = int if isinstance(lo, int) and isinstance(hi, int) else float
    key = _range_filter_key(col, prefix)

    def _clamped(pair) -> tuple:
        return (
            cast(min(max(pair[0], lo), hi)),
            cast(min(max(pair[1], lo), hi)),
        )

    if key in st.session_state:
        stored = st.session_state[key]
        if isinstance(stored, (tuple, list)) and len(stored) == 2:
            st.session_state[key] = _clamped(stored)
            return
    mirror = st.session_state.get(f"{prefix}_trial_filters_raw", {})
    stored = mirror.get(key)
    if isinstance(stored, (tuple, list)) and len(stored) == 2:
        st.session_state[key] = _clamped(stored)
    else:
        st.session_state[key] = (lo, hi)


def _filter_fields_for(words: pd.DataFrame, fixations: pd.DataFrame) -> list:
    """Trial-level condition columns to offer as filters (wizard-chosen for an
    upload, else the built-in defaults present in the data)."""
    filter_fields = st.session_state.get("wizard_filter_fields")
    if filter_fields is None:
        filter_fields = [
            c
            for c in _DEFAULT_FILTER_FIELDS
            if c in words.columns or c in fixations.columns
        ]
    return filter_fields


def cached_trial_level_columns(words: pd.DataFrame, fixations: pd.DataFrame) -> set:
    """``_trial_level_columns`` memoized per column-signature for this session.

    Trial-level-ness is a property of the dataset's shape, so the signature is
    the two frames' column tuples — stable across trials and filters. Shared by
    the ✏️ Edit chips picker and UX-49's range filters, which need the *same*
    answer: a column that varies inside a trial would filter rows rather than
    trials, silently cutting a scanpath in half.
    """
    signature = (tuple(words.columns), tuple(fixations.columns))
    cache = st.session_state.get("_trial_level_cache")
    if not cache or cache.get("signature") != signature:
        cache = {
            "signature": signature,
            "fields": _trial_level_columns(words, fixations),
        }
        st.session_state["_trial_level_cache"] = cache
    return cache["fields"]


def _range_filter_key(col: str, prefix: str = "") -> str:
    """Session key of ``col``'s range slider (prefix-scoped, CMP-8 §5.2).

    Under the ``filter_`` prefix on purpose: that is what gets it swept by
    *✕ Clear all filters* and kept out of compare-mode B's namespace for free.
    """
    return f"{prefix}filter_{col}_range"


def _numeric_filter_fields(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> dict[str, tuple]:
    """UX-49: which of the offered filter fields render as a *range*, and over what.

    Maps column → ``(frame, lo, hi)``. The set of columns the panel offers does
    **not** grow — this only auto-detects the *dtype* of what
    ``_filter_fields_for`` already returns, so a numeric one renders as a
    two-ended slider instead of a multiselect with one option per distinct float.
    That also bounds the panel's size: it can show no more rows than it does now.

    Two gates, both load-bearing. **Trial-level**: a column that varies inside a
    trial (fixation duration, word surprisal) would filter *rows*, not trials —
    that is PRE-2's render-layer territory, not this one. **Two distinct finite
    values**: fewer, and there is no range to pick.
    """
    trial_level = cached_trial_level_columns(words, fixations)
    fields: dict[str, tuple] = {}
    for col in _filter_fields_for(words, fixations):
        if col not in trial_level:
            continue
        frame = words if col in words.columns else fixations
        if col not in frame.columns or pd.api.types.is_bool_dtype(frame[col]):
            continue
        if not pd.api.types.is_numeric_dtype(frame[col]):
            continue
        bounds = _numeric_column_bounds(
            frame, col, cache_key=(frame_fingerprint(frame), col)
        )
        if bounds is None:
            continue
        lo, hi, _distinct = bounds
        fields[col] = (frame, lo, hi)
    return fields


def metadata_filter_key(name: str, prefix: str = "") -> str:
    """Session key of a participant-metadata filter (DATA-20).

    Under the ``filter_`` prefix like every other trial filter, which is what
    gets it swept by *✕ Clear all filters*, mirrored into
    ``_trial_filters_raw``, and kept out of compare-mode B's namespace — all
    for free, rather than by teaching each of those about a new field kind.
    """
    return f"{prefix}filter_meta_{name}"


def participant_metadata_fields():
    """The attached participant table's fields, or ``()`` when none (DATA-20)."""
    from scanpath_studio.tabs import active_participant_metadata

    attached = active_participant_metadata()
    return attached.fields if attached is not None else ()


def _render_participant_metadata_filters(host, *, prefix: str, on_change) -> None:
    """One control per registered participant-grain field.

    A reader attribute narrows by **reader**, so these do not need the field to
    exist on the words/fixations frames — `_compute_trial_filters` resolves the
    selection to a set of participant ids and intersects it with the participant
    filter. That is the whole reason the table never has to be broadcast.
    """
    from scanpath_studio import metadata as md
    from scanpath_studio.tabs import active_participant_metadata

    attached = active_participant_metadata()
    if attached is None or not attached.fields:
        return
    host.markdown("**By reader**")
    for field in attached.fields:
        key = metadata_filter_key(field.name, prefix)
        if field.is_numeric:
            bounds = md.bounds_for(attached, field.name)
            if bounds is None:
                continue
            low, high = bounds
            _seed_range_bounds(key, low, high, prefix=prefix)
            host.slider(
                field.label,
                min_value=low,
                max_value=high,
                key=key,
                on_change=on_change,
                help=f"From your participant table ({field.source}). Readers with "
                "no value are kept.",
            )
            continue
        options = md.options_for(attached, field.name)
        if len(options) <= 1:
            continue
        _seed_filter_widget(key, options, options, prefix=prefix)
        _labeled(
            host,
            "multiselect",
            field.label,
            options=options,
            key=key,
            on_change=on_change,
            help=f"From your participant table ({field.source}).",
        )


def _seed_range_bounds(key: str, low: float, high: float, *, prefix: str) -> None:
    """``_seed_range_widget`` for a key that is not derived from a column name."""

    def _clamped(pair) -> tuple:
        return (min(max(pair[0], low), high), min(max(pair[1], low), high))

    if key in st.session_state:
        stored = st.session_state[key]
        if isinstance(stored, (tuple, list)) and len(stored) == 2:
            st.session_state[key] = _clamped(stored)
            return
    mirror = st.session_state.get(f"{prefix}_trial_filters_raw", {})
    stored = mirror.get(key)
    if isinstance(stored, (tuple, list)) and len(stored) == 2:
        st.session_state[key] = _clamped(stored)
    else:
        st.session_state[key] = (low, high)


def _participant_metadata_narrowing(prefix: str) -> tuple:
    """``(reader ids | None, widget keys)`` for the active metadata filters.

    ``None`` means no constraint; an **empty set** means a constraint nothing
    satisfies. The keys are the widgets that produced it, so UX-7's per-filter
    clear can reset the right controls.
    """
    from scanpath_studio import metadata as md
    from scanpath_studio.tabs import active_participant_metadata

    attached = active_participant_metadata()
    if attached is None or not attached.fields:
        return None, ()
    selections: dict[str, list] = {}
    ranges: dict[str, tuple] = {}
    keys: list = []
    for field in attached.fields:
        key = metadata_filter_key(field.name, prefix)
        chosen = st.session_state.get(key)
        if field.is_numeric:
            bounds = md.bounds_for(attached, field.name)
            if (
                bounds
                and isinstance(chosen, (tuple, list))
                and len(chosen) == 2
                and tuple(chosen) != bounds
            ):
                ranges[field.name] = (float(chosen[0]), float(chosen[1]))
                keys.append(key)
            continue
        options = md.options_for(attached, field.name)
        if chosen and len(chosen) < len(options):
            selections[field.name] = list(chosen)
            keys.append(key)
    return md.participants_matching(attached, selections, ranges), tuple(keys)


def _compute_trial_filters(
    words: pd.DataFrame, fixations: pd.DataFrame, *, prefix: str = ""
) -> dict:
    """Derive the narrowing filter result from the live filter-widget values.

    Reads the widget keys (filter_participants / filter_<col> / filter_favorites /
    filter_req_tags / filter_exc_tags) — which Streamlit has already updated on the
    rerun the user changed a filter — so the filter applies on the SAME run. The
    on_change callbacks in ``render_trial_filters`` call this *before* the rerun;
    it also runs at the end of that function for no-change runs. Only narrowing
    selections feed the result.
    """
    result: dict = {
        "participants": None,
        "metadata": {},
        "ranges": {},
        # column -> the session key holding it, so "clear just this filter"
        # (UX-7) can reset one widget. Not derivable from the column name: the
        # Narrow-by Text multiselect lands in `metadata` under the *text column*
        # but lives under `filter_text_id`.
        "metadata_keys": {},
        # DATA-20: widget keys behind a participant-grain metadata narrowing,
        # which lands in `participants` above rather than in `metadata`.
        "participant_filter_keys": (),
        "favorites_only": False,
        "required_tags": [],
        "excluded_tags": [],
    }
    parts = _participant_options(
        words,
        fixations,
        cache_key=(frame_fingerprint(words), frame_fingerprint(fixations)),
    )
    if len(parts) > 1:
        sel = st.session_state.get(f"{prefix}filter_participants")
        if sel and len(sel) < len(parts):
            result["participants"] = list(sel)
    # DATA-20: a participant-grain metadata constraint *is* a participant
    # constraint, so it folds into the same slot rather than becoming a fourth
    # kind of filter every consumer would have to learn. Intersection, not
    # replacement: an explicit reader pick still wins over the table.
    by_metadata, meta_keys = _participant_metadata_narrowing(prefix)
    if by_metadata is not None:
        chosen = result["participants"]
        keep = by_metadata if chosen is None else by_metadata & {str(p) for p in chosen}
        # Ordered by the dataset's own participant order, so the resulting
        # selector list doesn't reshuffle when a metadata filter changes. May
        # legitimately be **empty** — an impossible combination narrows to no
        # reader, which `data.filter_trials` distinguishes from "no constraint".
        result["participants"] = [p for p in parts if str(p) in keep]
        # UX-7's per-filter report clears by widget key, and this narrowing did
        # not come from `filter_participants`. Its own top-level slot, not an
        # entry in `metadata_keys`: that dict is column-name → *one* key string,
        # and a dataset is free to have a column called "participants".
        result["participant_filter_keys"] = meta_keys
    # Text narrowing (the "Narrow by → Text" multiselect). Like a categorical
    # condition, but the text id isn't in the condition list, so handle it here.
    text_field, text_frame = _text_field_and_frame(words, fixations)
    if text_field is not None:
        text_vals = _column_unique_strs(
            text_frame,
            text_field,
            cache_key=(frame_fingerprint(text_frame), text_field),
        )
        sel = st.session_state.get(f"{prefix}filter_text_id")
        if sel and len(text_vals) > 1 and len(sel) < len(text_vals):
            result["metadata"][text_field] = set(sel)
            # UX-7's per-filter clear pops exactly this key, so it must be
            # emitted already-prefixed or clearing one of B's filters no-ops.
            result["metadata_keys"][text_field] = f"{prefix}filter_text_id"
    # UX-49: numeric trial-level columns narrow by range, not by membership. A
    # slider still at full extent is "no filter" and contributes nothing.
    numeric_fields = _numeric_filter_fields(words, fixations)
    for col, (_frame, lo, hi) in numeric_fields.items():
        key = _range_filter_key(col, prefix)
        chosen = st.session_state.get(key)
        if not (isinstance(chosen, (tuple, list)) and len(chosen) == 2):
            continue
        sel_lo, sel_hi = float(chosen[0]), float(chosen[1])
        if sel_lo <= lo and sel_hi >= hi:
            continue
        result["ranges"][col] = (sel_lo, sel_hi)
        result["metadata_keys"][col] = key
    for col in _filter_fields_for(words, fixations):
        if col in numeric_fields:
            continue
        frame = words if col in words.columns else fixations
        if col not in frame.columns:
            continue
        spec = _FILTER_FIELD_LABELS.get(col, {})
        if pd.api.types.is_bool_dtype(frame[col]):
            vals = _bool_filter_narrowing(
                col,
                frame,
                spec.get("true", "Yes"),
                spec.get("false", "No"),
                f"{prefix}filter_{col}",
            )
            if vals is not None:
                result["metadata"][col] = vals
                result["metadata_keys"][col] = f"{prefix}filter_{col}"
        else:
            values = _column_unique_strs(
                frame, col, cache_key=(frame_fingerprint(frame), col)
            )
            sel = st.session_state.get(f"{prefix}filter_{col}")
            if sel and len(values) > 1 and len(sel) < len(values):
                result["metadata"][col] = set(sel)
                result["metadata_keys"][col] = f"{prefix}filter_{col}"
    result["favorites_only"] = bool(
        st.session_state.get(f"{prefix}filter_favorites", False)
    )
    result["required_tags"] = list(
        st.session_state.get(f"{prefix}filter_req_tags") or []
    )
    result["excluded_tags"] = list(
        st.session_state.get(f"{prefix}filter_exc_tags") or []
    )
    return result


def _text_field_and_frame(words: pd.DataFrame, fixations: pd.DataFrame):
    """The text/passage id column to narrow by + the frame it lives on (prefer
    fixations, where trials live). ``(None, fixations)`` when no text column."""
    for field in ("unique_text_id", "text_id"):
        if field in fixations.columns:
            return field, fixations
        if field in words.columns:
            return field, words
    return None, fixations


def render_narrow_by(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    prefix: str = "",
    text_host=None,
    part_host=None,
) -> None:
    """Inline **Narrow by** multiselects — Text + Participant — that narrow the
    trial pool feeding the picker (the former Browse-by Text/Participant modes, now
    filters). They write the same ``filter_*`` keys the "More" popover uses and
    recompute via ``_compute_trial_filters``, so narrowing applies the same run.
    Start empty = no narrowing; pick values to narrow."""

    def _apply() -> None:
        st.session_state[f"{prefix}_trial_filters"] = _compute_trial_filters(
            words, fixations, prefix=prefix
        )

    th = text_host if text_host is not None else st
    ph = part_host if part_host is not None else st

    text_field, text_frame = _text_field_and_frame(words, fixations)
    if text_field is not None:
        text_vals = _column_unique_strs(
            text_frame,
            text_field,
            cache_key=(frame_fingerprint(text_frame), text_field),
        )
        if len(text_vals) > 1:
            _seed_filter_widget(f"{prefix}filter_text_id", text_vals, [], prefix=prefix)
            th.multiselect(
                "Text",
                options=text_vals,
                key=f"{prefix}filter_text_id",
                on_change=_apply,
                placeholder="All texts",
                label_visibility="collapsed",
            )

    parts = _participant_options(
        words,
        fixations,
        cache_key=(frame_fingerprint(words), frame_fingerprint(fixations)),
    )
    if len(parts) > 1:
        _seed_filter_widget(f"{prefix}filter_participants", parts, [], prefix=prefix)
        ph.multiselect(
            "Participant",
            options=parts,
            key=f"{prefix}filter_participants",
            on_change=_apply,
            placeholder="All participants",
            label_visibility="collapsed",
        )


def render_trial_filters(
    words: pd.DataFrame, fixations: pd.DataFrame, *, prefix: str = "", host=None
) -> dict:
    """Render the trial-filter controls into ``host`` and persist the selections.

    Lets the user narrow the trial pool by participant and by categorical
    condition (Hunting/Gathering, difficulty, first/repeated reading,
    correctness) plus annotation state (favorites / tags). Renders into ``host``
    (the Trial Selection panel; defaults to the sidebar). The narrowing result is
    derived by ``_compute_trial_filters`` and stashed in session_state
    (`_trial_filters`); each widget's ``on_change`` recomputes it *before* the
    rerun so ``main()``'s ``read_trial_filters`` applies the change on the same
    run. The persisted value also survives runs where this panel isn't rendered
    (a non-Scanpath view under the sidebar nav).
    """
    if host is None:
        host = st.sidebar

    def _apply() -> None:
        st.session_state[f"{prefix}_trial_filters"] = _compute_trial_filters(
            words, fixations, prefix=prefix
        )

    # Text + Participant narrowing now lives in the inline "Narrow by" row
    # (``render_narrow_by``); this popover keeps the condition + annotation filters.
    #
    # UX-49: a numeric trial-level column gets a two-ended range slider instead
    # of a multiselect over its distinct floats. Rendered first, as extra rows
    # among the categorical ones rather than in a section of their own.
    numeric_fields = _numeric_filter_fields(words, fixations)
    for col, (frame, lo, hi) in numeric_fields.items():
        spec = _FILTER_FIELD_LABELS.get(col, {})
        label = spec.get("label", col.replace("_", " ").strip().title())
        _seed_range_widget(col, lo, hi, prefix=prefix)
        host.slider(
            label,
            min_value=lo,
            max_value=hi,
            key=_range_filter_key(col, prefix),
            on_change=_apply,
            help="Keep only trials whose value falls in this range. Trials with "
            "no value are kept — a range narrows, it doesn't exclude the "
            "unmeasured.",
        )
        missing = _trials_missing_column(
            frame, col, cache_key=(frame_fingerprint(frame), col)
        )
        if missing:
            # Say it, or the kept-anyway trials look like the range isn't working.
            host.caption(
                f"{missing} trial{'s' if missing != 1 else ''} have no "
                f"**{label}** value and are kept regardless."
            )
    for col in _filter_fields_for(words, fixations):
        if col in numeric_fields:
            continue
        frame = words if col in words.columns else fixations
        if col not in frame.columns:
            continue
        spec = _FILTER_FIELD_LABELS.get(col, {})
        label = spec.get("label", col.replace("_", " ").strip().title())
        if pd.api.types.is_bool_dtype(frame[col]):
            _bool_metadata_filter(
                label,
                col,
                frame,
                spec.get("true", "Yes"),
                spec.get("false", "No"),
                f"{prefix}filter_{col}",
                host,
                on_change=_apply,
            )
        else:
            values = _column_unique_strs(
                frame, col, cache_key=(frame_fingerprint(frame), col)
            )
            if len(values) > 1:
                _seed_filter_widget(
                    f"{prefix}filter_{col}", values, values, prefix=prefix
                )
                _labeled(
                    host,
                    "multiselect",
                    label,
                    options=values,
                    key=f"{prefix}filter_{col}",
                    on_change=_apply,
                )

    _render_participant_metadata_filters(host, prefix=prefix, on_change=_apply)

    host.markdown("**By annotation**")
    if f"{prefix}filter_favorites" not in st.session_state:
        st.session_state[f"{prefix}filter_favorites"] = bool(
            st.session_state.get(f"{prefix}_trial_filters_raw", {}).get(
                f"{prefix}filter_favorites", False
            )
        )
    host.checkbox(
        "⭐ Favorites only", key=f"{prefix}filter_favorites", on_change=_apply
    )
    tags = known_tags()
    if tags:
        _seed_filter_widget(f"{prefix}filter_req_tags", tags, [], prefix=prefix)
        _labeled(
            host,
            "multiselect",
            "With any of these tags",
            options=tags,
            key=f"{prefix}filter_req_tags",
            on_change=_apply,
        )
        _seed_filter_widget(f"{prefix}filter_exc_tags", tags, [], prefix=prefix)
        _labeled(
            host,
            "multiselect",
            "Excluding tags",
            options=tags,
            key=f"{prefix}filter_exc_tags",
            on_change=_apply,
            help="e.g. hide everything tagged 'To exclude'.",
        )

    # UX-26: the filter reset used to appear only in the empty-result diagnostic
    # panel — you had to filter yourself into nothing before the escape hatch
    # showed up. It now has a permanent home at the foot of the panel that set
    # the filters (and a second one in the rail's Reset settings popover).
    host.divider()
    host.button(
        "✕ Clear all filters",
        key=f"{prefix}clear_all_filters_panel",
        on_click=clear_trial_filters,
        args=(prefix,),
        width="stretch",
        help="Reset every Narrow-by, condition and annotation filter.",
    )

    # Mirror the rendered widget values so _seed_filter_widget can restore them on
    # a run where this panel isn't shown (the keys get cleared); then publish the
    # derived result for read_trial_filters (covers no-change runs).
    # UX-49: the range keys have to be listed explicitly. Without them a range
    # silently resets on any run where this popover isn't rendered — a trip
    # through Corpus Analysis is enough, since Streamlit drops the key and
    # `_seed_range_widget` would then find nothing to restore.
    keys = (
        [
            f"{prefix}filter_participants",
            f"{prefix}filter_text_id",
            f"{prefix}filter_req_tags",
            f"{prefix}filter_exc_tags",
        ]
        + [f"{prefix}filter_{c}" for c in _filter_fields_for(words, fixations)]
        + [_range_filter_key(c, prefix) for c in numeric_fields]
        # DATA-20 — mirrored like any other filter, so a metadata narrowing
        # survives a run where the popover didn't render and round-trips
        # through Share / save & restore with the rest of the filter layer.
        + [metadata_filter_key(f.name, prefix) for f in participant_metadata_fields()]
    )
    st.session_state[f"{prefix}_trial_filters_raw"] = {
        k: st.session_state[k] for k in keys if k in st.session_state
    }
    result = _compute_trial_filters(words, fixations, prefix=prefix)
    st.session_state[f"{prefix}_trial_filters"] = result
    return result
