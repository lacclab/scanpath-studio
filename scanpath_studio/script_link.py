"""A link that opens a local app on one dataset, reading and figure.

`api.app_link` and ``scanpath-studio open`` write it. A script names the
figure in the API's own vocabulary — the keywords `api.plot_scanpath` takes —
and the app reads a link in the rail's: session keys behind URL params. This
module is the translation, figure keyword → the session keys the rail would
hold for it (:func:`options_state`), after which the Share → Link writer's own
sweep (`url_state.settings_params`) spells the params. So a link written here
and one copied from 🔗 Share are the same link for the same view, and the reader
(`url_state._apply_url_preset`) needs nothing new.

The way back — session keys → figure keywords — is the app's own
(`controls._collect_viz_settings` → `tabs._build_figure_settings`).
`tests/test_app_link.py` holds the two to each other; `tests/test_properties.py`
holds that every session key a link carries is the one the reader seeds.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from urllib.parse import urlencode

from .constants import (
    BACKGROUND_PRESETS,
    FIXATION_FLAG_CATEGORIES,
    FIXATION_LABEL_OPTIONS,
    OPACITY_OPTIONS,
    SACCADE_CLASS_COLORS,
    SACCADE_CLASS_EDITABLE,
    SACCADE_CLASS_ORDER,
    SACCADE_DASH_OPTIONS,
)
from .session_keys import (
    PARAM_DATASET,
    PARAM_DATASET_DIGEST,
    PARAM_DATASET_ID,
    PARAM_MATCH,
    PARAM_MATCH_VIEW,
    REPLAY_FIXATIONS_PARAM,
)

#: The host a link names: the app on this computer.
LOCAL_HOST = "localhost"
#: Streamlit's own port, and `scanpath-studio run`'s.
DEFAULT_PORT = 8501

#: Keywords whose value is the session key's, under another name.
_SAME_VALUE = {
    "show_words": "global_show_words",
    "show_fixations": "global_show_fix",
    "show_order": "global_show_order",
    "show_saccades": "global_show_saccades",
    "show_saccade_arrows": "global_show_saccade_arrows",
    "show_heatmap": "global_show_heatmap",
    "show_raw_gaze": "global_show_raw_gaze",
    "show_coordinate_grid": "global_show_coordinate_grid",
    "reverse_x_axis": "global_reverse_x_axis",
    "reverse_y_axis": "global_reverse_y_axis",
    "heatmap_style": "global_heatmap_style",
    "heatmap_norm": "global_heatmap_norm",
    "heatmap_colorscale": "global_heatmap_colorscale",
    "fixation_colorscale": "global_fixation_colorscale",
    "fixation_color_range": "global_fixation_color_range",
    "heatmap_range": "global_heatmap_color_range",
    "x_field": "global_x_field",
    "y_field": "global_y_field",
    "fixation_color": "global_fixation_color",
    "fixation_symbol": "global_fixation_symbol",
    "hollow_fixations": "global_hollow_fixations",
    "redact_text": "global_redact_text",
    "marker_size_range": "global_marker_size_range",
    "marker_size_scale": "global_marker_size_scale",
    "marker_duration_range": "global_marker_duration_range",
    "duration_size_legend": "global_duration_size_legend",
    "fixation_snap_to_line": "global_fixation_snap_to_line",
    "fixation_snap_position": "global_fixation_snap_position",
    "fixation_hover_fields": "global_fixation_hover_fields",
    "word_hover_fields": "global_word_hover_fields",
    "word_hover_measure": "global_word_hover_measure",
    "saccade_color": "global_saccade_color",
    "saccade_width": "global_saccade_width",
    "saccade_color_mode": "global_saccade_color_mode",
    "saccade_type_legend": "global_saccade_type_legend",
    "show_color_legend": "global_show_color_legend",
    "show_highlight_legend": "global_show_highlight_legend",
    "saccade_render_mode": "global_saccade_render_mode",
    "fit_to_monitor": "global_fit_to_monitor",
    "critical_span_style": "global_critical_span_style",
    "highlight_column": "global_highlight_column",
    "span_border_color": "global_span_border_color",
    "text_color": "global_text_color",
    "highlight_text_color": "global_highlight_text_color",
    "line_spacing": "global_line_spacing",
    "scale_text_to_boxes": "global_scale_text_to_boxes",
    "raw_gaze_color": "global_raw_gaze_color",
    "raw_gaze_marker_size": "global_raw_gaze_marker_size",
    "raw_gaze_opacity": "global_raw_gaze_opacity",
    "word_box_color": "global_word_box_color",
    "word_box_line_opacity": "global_word_box_line_opacity",
    "word_box_fill_color": "global_word_box_fill_color",
    "word_box_fill_opacity": "global_word_box_fill_opacity",
    "illustration_text": "global_illustration_text",
    "title_font_size": "global_title_font_size",
    "caption_font_size": "global_caption_font_size",
    "caption_color": "global_caption_color",
    "show_credit": "global_show_credit",
    "show_plot_frame": "global_show_plot_frame",
    "plot_frame_color": "global_plot_frame_color",
    "coordinate_grid_font_size": "global_coordinate_grid_font_size",
    "saccade_arrow_size": "global_saccade_arrow_size",
    "fixation_outline_width": "global_fixation_outline_width",
    "fixation_outline_color": "global_fixation_outline_color",
    # The stimulus page's opacity: the API names it after the background
    # image it draws, the rail after the stimulus.
    "background_image_opacity": "global_stimulus_image_opacity",
    "anim_grid_step_ms": "global_anim_grid_step_ms",
    "anim_max_frames": "global_anim_max_frames",
    "palette": "global_palette",
    # The replay's player.
    "playback_speed": "single_playback_speed",
    "autoplay": "global_anim_autoplay",
    "grow_fixations": "global_anim_grow_fixations",
    "fade_fixations": "global_anim_fade_fixations",
    **{name: option.state_key for name, option in FIXATION_LABEL_OPTIONS.items()},
    **{name: option.state_key for name, option in OPACITY_OPTIONS.items()},
    **{
        f"{bar}_colorbar_{part}": f"global_{bar}_colorbar_{part}"
        for bar in ("fixation", "heatmap")
        for part in ("orientation", "tickangle", "tickfont_size", "thickness")
    },
    **{
        f"show_{bar}_colorbar": f"global_show_{bar}_colorbar"
        for bar in ("fixation", "heatmap")
    },
}

#: Keywords whose ``None`` is the rail's *Auto* box: ``None`` ticks it, a
#: value unticks it and sets the value. Keyword → (Auto key, value key).
_AUTO_VALUE = {
    "heatmap_sigma_px": ("global_heatmap_sigma_auto", "global_heatmap_sigma_px"),
    "heatmap_opacity": ("global_heatmap_opacity_auto", "global_heatmap_opacity"),
    "crop_margin": ("global_crop_margin_auto", "global_crop_margin_px"),
    "coordinate_grid_spacing": (
        "global_coordinate_grid_auto",
        "global_coordinate_grid_spacing",
    ),
    **{
        f"{bar}_colorbar_length": (
            f"global_{bar}_colorbar_length_auto",
            f"global_{bar}_colorbar_length",
        )
        for bar in ("fixation", "heatmap")
    },
}

_LINE_STYLE_LABELS = {dash: label for label, dash in SACCADE_DASH_OPTIONS.items()}


def _saccade_style(value) -> dict:
    """The API's Plotly dash name (``"dash"``), or the rail's label (``"Dashed"``)."""
    text = str(value)
    if text in SACCADE_DASH_OPTIONS:
        return {"global_saccade_style": text}
    if text in _LINE_STYLE_LABELS:
        return {"global_saccade_style": _LINE_STYLE_LABELS[text]}
    raise ValueError(
        f"saccade_style={value!r}: expected one of "
        f"{', '.join(map(repr, SACCADE_DASH_OPTIONS.values()))}."
    )


def _heatmap_metric(value) -> dict:
    # The API's ``None`` is the rail's *Fixation count*.
    return {"global_heatmap_metric": "counts" if value is None else value}


def _background_color(value) -> dict:
    from .controls import BG_CUSTOM_CHOICE

    color = str(value)
    preset = next(
        (name for name, c in BACKGROUND_PRESETS.items() if c.lower() == color.lower()),
        None,
    )
    if preset is not None:
        return {"global_bg_choice": preset}
    return {"global_bg_choice": BG_CUSTOM_CHOICE, "global_bg_custom": color}


def _fixation_flags(value) -> dict:
    """The API's flags name only the categories that are on; the rest are off."""
    flags = dict(value or {})
    unknown = set(flags) - set(FIXATION_FLAG_CATEGORIES)
    if unknown:
        raise ValueError(
            f"fixation_flags: unknown categories {sorted(unknown)}; expected "
            f"{', '.join(FIXATION_FLAG_CATEGORIES)}."
        )
    state = {}
    for cat, category in FIXATION_FLAG_CATEGORIES.items():
        spec = dict(flags.get(cat) or {})
        state[f"global_fixclass_{cat}_mode"] = str(spec.get("mode", "Off"))
        if category.has_threshold and spec.get("threshold_ms") is not None:
            threshold = float(spec["threshold_ms"])
            if not threshold.is_integer():
                raise ValueError(
                    f"fixation_flags: the {cat} threshold_ms={spec['threshold_ms']!r} "
                    "is not a whole number of ms, which the app's threshold is."
                )
            state[f"global_fixclass_{cat}_threshold_ms"] = int(threshold)
        for part in ("symbol", "color"):
            if spec.get(part):
                state[f"global_fixclass_{cat}_{part}"] = str(spec[part])
    return state


def _saccade_class_colors(value) -> dict:
    colors = {**SACCADE_CLASS_COLORS, **dict(value or {})}
    unknown = set(colors) - set(SACCADE_CLASS_COLORS)
    if unknown:
        raise ValueError(
            f"saccade_class_colors: unknown classes {sorted(unknown)}; expected "
            f"{', '.join(SACCADE_CLASS_EDITABLE)}."
        )
    # The rail colours every class but *other*, which keeps its stock grey.
    fixed = [
        cls
        for cls in SACCADE_CLASS_COLORS
        if cls not in SACCADE_CLASS_EDITABLE
        and str(colors[cls]).lower() != SACCADE_CLASS_COLORS[cls].lower()
    ]
    if fixed:
        raise ValueError(
            f"saccade_class_colors: the app can't recolour {', '.join(fixed)}; "
            f"a link carries {', '.join(SACCADE_CLASS_EDITABLE)}."
        )
    return {
        f"global_saccade_class_color_{cls}": str(colors[cls])
        for cls in SACCADE_CLASS_EDITABLE
    }


def _saccade_classes(value) -> dict:
    """In the rail's order; an unknown class is left for the reader's check
    to name."""
    classes = [str(cls) for cls in value]
    if not classes:
        raise ValueError(
            "saccade_classes=[] draws no saccades, which a link can't say: the "
            "app reads no class as every class. Pass show_saccades=False."
        )
    known = [cls for cls in SACCADE_CLASS_ORDER if cls in classes]
    return {
        "global_saccade_classes": known
        + [cls for cls in classes if cls not in SACCADE_CLASS_ORDER]
    }


def _illustration_label(value) -> dict:
    labels = {"auto": "Auto", "show": "Show", "hide": "Hide"}
    key = str(value).lower()
    if key not in labels:
        raise ValueError(
            f"illustration_label={value!r}: expected one of {', '.join(labels)}."
        )
    return {"global_illustration_label": labels[key]}


def _fix_index_range(value) -> dict:
    """The fixation-index slider's window: 1-based, both ends inclusive."""
    try:
        lo, hi = (int(bound) for bound in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"fix_index_range must be a (start, end) pair of fixation indices, "
            f"got {value!r}."
        ) from exc
    if lo < 1 or hi < lo:
        raise ValueError(
            f"fix_index_range={value!r} needs 1 <= start <= end (1-based, both "
            "inclusive)."
        )
    return {"single_fix_range": [lo, hi]}


def _legend_layout(value) -> dict:
    """The legends moved off *Auto*; a link says nothing of the others, as
    Share writes it."""
    from .plots import _legend_is_moved, normalize_legend_layout
    from .url_state import _legend_state

    state = {}
    for kind, spec in normalize_legend_layout(value).items():
        if _legend_is_moved(spec):
            state.update(_legend_state(kind, spec))
    return state


#: Keywords that become more than one session key, or a key in another form.
_CONVERTED: dict[str, Callable[[object], dict]] = {
    "saccade_style": _saccade_style,
    "heatmap_metric": _heatmap_metric,
    "background_color": _background_color,
    "fixation_flags": _fixation_flags,
    "saccade_class_colors": _saccade_class_colors,
    "legend_layout": _legend_layout,
    "saccade_classes": _saccade_classes,
    "illustration_label": _illustration_label,
    "fix_index_range": _fix_index_range,
    # Word labels and the stimulus page are drawn under the 📄 Stimulus
    # switch, so asking for one asks for the switch too.
    "show_word_labels": lambda v: {
        "global_show_labels": bool(v),
        **({"global_show_stimulus": True} if v else {}),
    },
    "show_stimulus_image": lambda v: {
        "global_show_stimulus_image": bool(v),
        **({"global_show_stimulus": True} if v else {}),
    },
}

#: Every figure keyword a link carries.
LINKED_OPTIONS = frozenset(
    {*_SAME_VALUE, *_AUTO_VALUE, *_CONVERTED, "color_by", "color_by_line"}
)

#: Figure keywords a link can't carry, and why — named in the error.
UNLINKABLE_OPTIONS = {
    "background_image": "an image file; show_stimulus_image=True draws the "
    "dataset's own pages",
    "background_image_size": "the size of an image file",
    "background_image_origin": "the position of an image file",
    "word_heatmap_col": "a Corpus Analysis setting, not one of the Scanpath view's",
    "word_heatmap_title": "a Corpus Analysis setting, not one of the Scanpath view's",
    "connector_y": "computed by the app from the drift correction",
    "show_connectors": "computed by the app from the drift correction",
    "illustration_reasons": "computed by the app from the figure's settings",
    "title": "text the app writes from its own title pattern; set it in the app",
    "caption": "text the app writes from its own caption pattern; set it in the app",
    **dict.fromkeys(
        (
            "show_legend",
            "style_a",
            "style_b",
            "label_a",
            "label_b",
            "words_b",
            "fixations_b",
            "fixation_flags_b",
            "compare_stimulus",
            "background_image_b",
            "background_image_size_b",
            "background_image_origin_b",
        ),
        "a comparison's; a link from a script opens one reading",
    ),
}

#: Converted keywords whose ``None`` means nothing of its own: like every
#: plain keyword's, it leaves the app's value.
_NONE_KEEPS = frozenset(
    {
        "saccade_style",
        "background_color",
        "show_word_labels",
        "show_stimulus_image",
        "saccade_classes",
        "illustration_label",
        "fix_index_range",
    }
)


def options_state(options: Mapping) -> dict:
    """The session keys the rail holds for these figure keywords.

    ``None`` for a keyword leaves the app's own value, as a keyword left out
    does, except where ``None`` is the API's own choice the rail can show: the
    fixation-count heatmap, no fixation flags, the stock saccade colours,
    every legend on *Auto*, and each *Auto* box.

    Raises:
        TypeError: A keyword that is no figure option a link carries.
        ValueError: A value that has no rail equivalent.
    """
    unknown = sorted(set(options) - LINKED_OPTIONS)
    if unknown:
        reasons = [
            f"{name} ({UNLINKABLE_OPTIONS[name]})"
            for name in unknown
            if name in UNLINKABLE_OPTIONS
        ]
        others = [name for name in unknown if name not in UNLINKABLE_OPTIONS]
        parts = []
        if reasons:
            parts.append("a link can't carry " + "; ".join(reasons))
        if others:
            parts.append(
                f"no figure option is called {', '.join(others)} "
                "(api.figure_options() lists them)"
            )
        raise TypeError("app_link: " + ", and ".join(parts) + ".")
    state: dict = {}
    for name, value in options.items():
        if name in _SAME_VALUE:
            # A link writes no empty value (`settings_params`): ``None`` and
            # ``""`` leave the app's own.
            if value not in (None, ""):
                state[_SAME_VALUE[name]] = (
                    list(value) if isinstance(value, (list, tuple)) else value
                )
        elif name in _AUTO_VALUE:
            auto_key, value_key = _AUTO_VALUE[name]
            state[auto_key] = value is None
            if value is not None:
                state[value_key] = value
        elif name in _CONVERTED:
            if value is None and name in _NONE_KEEPS:
                continue
            state.update(_CONVERTED[name](value))
    # The colour field: *line* is a choice of the same menu in the rail.
    if options.get("color_by_line"):
        state["global_color_by"] = "line"
    elif options.get("color_by") is not None:
        state["global_color_by"] = options["color_by"]
    return state


def _check_link_values(params: Mapping[str, str]) -> None:
    """Refuse a value the app would ignore or clamp when it reads the link."""
    from . import url_state as us

    for param, raw in params.items():
        if len(str(raw)) > us._MAX_LINK_VALUE_CHARS:
            raise ValueError(
                f"{param} is {len(str(raw)):,} characters long; the app reads at "
                f"most {us._MAX_LINK_VALUE_CHARS:,} from a link."
            )
        if param not in us._URL_PRESETS:
            continue
        state_key, coerce = us._URL_PRESETS[param]
        try:
            value = coerce(raw)
            if value is not None and state_key in us._CHOICE_STATE_PARSERS:
                value = us._CHOICE_STATE_PARSERS[state_key](value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f"The app can't read {param}={raw!r}: {exc}") from exc
        if us._clamp_url_value(state_key, value) != value:
            lo, hi = us._URL_BOUNDED[state_key]
            raise ValueError(f"{param}={raw} is outside the app's range {lo}–{hi}.")


def link_query(
    dataset: str,
    participant: str | None = None,
    trial: str | None = None,
    *,
    screen: str | None = None,
    animate: bool = False,
    match: str | None = None,
    match_view: str | None = None,
    options: Mapping | None = None,
    share_id: str | None = None,
    digest: str | None = None,
    aliases: Mapping[str, str] | None = None,
) -> str:
    """The query string of a link to ``dataset``'s reading, URL-encoded, no ``?``.

    The params are the ones 🔗 Share → Link writes for the same view: the
    dataset by name (with its share ID and the digest of its tables, when
    given; a dataset the app has itself by its ``?source=``, see
    `builtin_source_params`), the reading, the Comparisons subtab's *Match
    field* when ``match`` names one, then the figure settings.
    """
    from .url_state import settings_params

    name = str(dataset or "").strip()
    if not name:
        raise ValueError("Name the dataset the link opens.")
    builtin = None if share_id or digest else builtin_source_params(name, aliases)
    params = builtin or {PARAM_DATASET: name}
    if share_id:
        params[PARAM_DATASET_ID] = str(share_id)
    if digest:
        params[PARAM_DATASET_DIGEST] = str(digest)
    if participant not in (None, ""):
        params["participant"] = _id_text(participant)
    if trial not in (None, ""):
        params["trial_id"] = _id_text(trial)
    if screen not in (None, ""):
        if trial in (None, ""):
            raise ValueError("A screen belongs to a trial: pass trial= with screen=.")
        params["screen"] = _id_text(screen)
    if match is not None:
        if not isinstance(match, str):
            raise TypeError(f"match is a field name, not {type(match).__name__}.")
        if not match.strip():
            raise ValueError("Name the field match= matches on, or leave it out.")
        params[PARAM_MATCH] = match
    if match_view is not None:
        from .session_keys import MATCH_VIEW_LINK_VALUES

        if match is None:
            raise ValueError("match_view= is the view of a match=: pass match= too.")
        view = str(match_view).strip().lower()
        if view not in MATCH_VIEW_LINK_VALUES:
            raise ValueError(
                f"match_view is one of {', '.join(MATCH_VIEW_LINK_VALUES)}; "
                f"got {match_view!r}."
            )
        params[PARAM_MATCH_VIEW] = view
    state = options_state(options or {})
    if state:
        # A link with layer switches and no duration scale is read as one
        # written before the fixed scale existed (`_apply_url_preset`), so the
        # scale always travels beside them, as Share writes it.
        state.setdefault("global_marker_size_scale", _default_marker_size_scale())
    settings = settings_params(state)
    _check_link_values(settings)
    params.update(settings)
    if animate:
        params["tab"] = "animation"
        # A linked replay draws fixations unless it says not to, as Share
        # writes it (`_build_share_query`).
        if params.get("show_fixations") == "0":
            params[REPLAY_FIXATIONS_PARAM] = "0"
    return urlencode(params)


def builtin_source_params(
    name: str, aliases: Mapping[str, str] | None = None
) -> dict[str, str] | None:
    """The params 🔗 Share writes for a dataset the app ships or downloads
    itself, named as its list shows it (ignoring case), or ``None``.

    The app reads ``?dataset=`` as a dataset someone added, so a link naming the
    bundled demo or a public corpus that way finds nothing of that name. These
    sources travel as ``?source=`` instead (``?source=corpus&corpus=…`` for a
    public corpus), as Share writes them. The list shows a public corpus by its
    short name (``PoTeC``) and a renamed one by its new name, from ``aliases``
    (``{source: name}``); its full registry label is accepted too.
    """
    from .app import picker_name_for, public_dataset_registry
    from .url_state import (
        _SHAREABLE_SOURCES,
        CORPUS_SOURCE_TOKEN,
        PARAM_CORPUS,
        registry_corpus_slugs,
    )

    registry = public_dataset_registry()
    aliases = aliases or {}
    wanted = name.casefold()

    def named(choice: str) -> bool:
        shown = (choice, picker_name_for(choice, registry), aliases.get(choice))
        return any(str(n).casefold() == wanted for n in shown if n)

    for choice, token in _SHAREABLE_SOURCES.items():
        if named(choice):
            return {"source": token}
    for label, slug in registry_corpus_slugs().items():
        if named(label):
            return {"source": CORPUS_SOURCE_TOKEN, PARAM_CORPUS: slug}
    return None


def _id_text(value) -> str:
    """An ID as the app spells it (`data.stable_id`): ``101.0`` is ``"101"``."""
    import pandas as pd

    from .data import stable_id

    return str(stable_id(pd.Series([value])).iloc[0])


def _default_marker_size_scale() -> str:
    from .constants import DEFAULT_MARKER_SIZE_SCALE

    return DEFAULT_MARKER_SIZE_SCALE


def local_url(query: str, port: int = DEFAULT_PORT) -> str:
    """``query`` on the app at ``localhost:port``."""
    port = int(port)
    if not 0 < port < 65536:
        raise ValueError(f"port={port} is not a TCP port (1–65535).")
    return f"http://{LOCAL_HOST}:{port}/?{query}"
