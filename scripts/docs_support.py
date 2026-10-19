"""What the docs build generates instead of restating.

The pages call these from ``exec="true"`` fences (markdown-exec), and
``scripts/mkdocs_hooks.py`` puts this folder on ``sys.path`` for them. Each
function returns the Markdown or HTML for one block, read from the thing it
describes — the package's citation, ``CHANGELOG.md``, the ``render`` parser, the
figure option registry, a built figure — so none of it can drift from the code
the way a hand-maintained copy does.
"""

from __future__ import annotations

import argparse
import html
import inspect
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/lacclab/scanpath-studio"
BLOB_URL = f"{REPO_URL}/blob/main/"


# ---------------------------------------------------------------------------
# Cite
# ---------------------------------------------------------------------------


def software_citation() -> str:
    """The software citation, as BibTeX and APA tabs.

    Built by ``scanpath_studio.citation``, the same code ❓ Help → About shows,
    so the site and the app print one entry; ``tests/test_citation.py`` keeps
    its metadata equal to ``CITATION.cff``, which feeds GitHub's *Cite this
    repository* button and the Zenodo record.
    """
    from scanpath_studio.citation import software_apa, software_bibtex

    return "\n".join(
        [
            '=== "BibTeX"',
            "",
            "    ```bibtex",
            *(f"    {line}" for line in software_bibtex().splitlines()),
            "    ```",
            "",
            '=== "APA"',
            "",
            f"    {software_apa()}",
            "",
        ]
    )


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------

_RELATIVE_LINK = re.compile(r"\]\((?!https?://|mailto:|#)([^)\s]+)\)")


def _link_target(path: str) -> str:
    """A repo-relative link as it has to read from the docs site: a docs page
    stays on the site, anything else goes to the file on GitHub."""
    if path.startswith("docs/") and path.endswith(".md"):
        return path.removeprefix("docs/")
    return BLOB_URL + path


# ---------------------------------------------------------------------------
# CLI reference
# ---------------------------------------------------------------------------


def _parsers() -> dict:
    from scanpath_studio import cli

    return {
        "render": cli._render_parser,
        "analyze": cli._analyze_parser,
        "corpus": cli._corpus_parser,
        "check": cli._check_parser,
        "cache": cli._cache_parser,
        "version": cli._version_parser,
    }


#: A tracker-style id as a CLI help string may cite one — ``(ABC-8)``, a
#: leading ``ABC-7:`` or ``ABC-2 `` — which a reader of the reference has no
#: use for.
_ID = r"[A-Z]{2,5}-\d+"
_ID_PARENTHETICAL = re.compile(rf"\s*\((?:{_ID}(?:,\s*)?)+\)")
_ID_LEAD = re.compile(rf"^{_ID}:?\s+")


def _without_ids(text: str) -> str:
    text = _ID_LEAD.sub("", _ID_PARENTHETICAL.sub("", text))
    return text[:1].upper() + text[1:]


def _cell(text: str) -> str:
    """One table cell: HTML-safe, single-line, pipes escaped, flags as code."""
    text = html.escape(_without_ids(" ".join(text.split())), quote=False)
    # `[,symbol=S]` would otherwise read as a reference-style link, which
    # mkdocs-autorefs then fails to resolve.
    for char in "|*[]":
        text = text.replace(char, "\\" + char)
    return re.sub(r"(?<![`\w-])(--[a-z][a-z0-9-]*)", r"`\1`", text)


# ---------------------------------------------------------------------------
# API reference
# ---------------------------------------------------------------------------


def api_index(page: str = "api.md") -> str:
    """The Python API page's at-a-glance table: every function it documents,
    under its section, with the first line of its docstring.

    Read off the page's own ``::: path`` lines, so the table lists exactly what
    the page documents, in its order.
    """
    import importlib

    out = ["| Function | What it does |", "| --- | --- |"]
    section = None
    for line in (ROOT / "docs" / page).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        elif line.startswith("::: "):
            if section is not None:
                # The section's own row, heading the functions under it.
                out.append(f"| **{section}** | |")
                section = None
            path = line[4:].strip()
            module, _, name = path.rpartition(".")
            obj = getattr(importlib.import_module(module), name)
            summary = (inspect.getdoc(obj) or "").split("\n\n")[0]
            summary = " ".join(summary.split()).replace("|", "\\|")
            out.append(f"| [`{name}`][{path}] | {summary} |")
    return '<div class="sps-reference-table sps-api-index" markdown>\n\n' + (
        "\n".join(out) + "\n\n</div>"
    )


def _flag_rows(actions, formatter) -> list[str]:
    """One reference table: a row per flag, its value, default and help."""
    out = [
        "| Option | Value | Default | Description |",
        "| --- | --- | --- | --- |",
    ]
    for action in actions:
        # One alias a line: the column stays as narrow as the longest flag.
        flags = "<br>".join(f"`{flag}`" for flag in action.option_strings)
        if action.nargs == 0:
            value = "switch"
        elif action.choices and action.nargs in (None, "?"):
            # One code span per choice, so a long set can wrap between them.
            value = ", ".join(f"`{choice}`" for choice in action.choices)
        else:
            metavar = formatter._get_default_metavar_for_optional(action)
            value = f"`{formatter._format_args(action, metavar)}`"
        if action.required:
            default = "required"
        elif action.nargs == 0 or action.default in (None, argparse.SUPPRESS):
            # A switch's default is simply not being given; printing the
            # value it stores (`--no-words` → True) would read as "on".
            default = "—"
        else:
            default = f"`{action.default}`"
        description = _cell(formatter._expand_help(action)) if action.help else ""
        out.append(f"| {flags} | {value} | {default} | {description} |")
    return ['<div class="sps-reference-table sps-flag-table" markdown>', "", *out]


def _visible_actions(group) -> list:
    return [
        action
        for action in group._group_actions
        if action.help != argparse.SUPPRESS
        and not isinstance(action, argparse._HelpAction)
    ]


def cli_reference(command: str, *, heading: str = "") -> str:
    """Every flag of one subcommand, one table per argument group.

    Walks the parser the command itself parses with, so a flag cannot exist
    without appearing here, and its default and help are the ones ``--help``
    prints. ``render`` is split by topic instead (`_render_flag_topics`), under
    ``heading``-level headings (``"###"``), since its figure group alone holds
    over a hundred flags.
    """
    parser = _parsers()[command]()
    formatter = parser._get_formatter()
    if command == "render":
        out = []
        for topic, actions in _render_flag_topics(parser).items():
            out += [f"{heading} {topic}", "", *_flag_rows(actions, formatter)]
            out += ["", "</div>", ""]
        return "\n".join(out)
    groups = [(g.title, _visible_actions(g)) for g in parser._action_groups]
    groups = [(title, actions) for title, actions in groups if actions]
    out = []
    for title, actions in groups:
        if len(groups) > 1:
            out += [f"**{_cell(title)}**", ""]
        out += [*_flag_rows(actions, formatter), "", "</div>", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Figure options
# ---------------------------------------------------------------------------

#: The figure-option sections, named and ordered like the sections of the
#: app's Plot controls; the ``render`` flags are listed under the same
#: headings. Every figure option belongs to exactly one: `_option_topics`
#: refuses an option none of them names, so a new option fails the docs build
#: until it has a place.
OPTION_TOPICS: dict[str, tuple[str, ...]] = {
    "Fixations": (
        "show_fixations",
        "fixation_color",
        "color_by",
        "color_by_line",
        "fixation_colorscale",
        "fixation_color_range",
        "fixation_opacity",
        "fixation_symbol",
        "hollow_fixations",
        "fixation_outline_color",
        "fixation_outline_width",
        "marker_size_scale",
        "marker_size_range",
        "marker_duration_range",
        "show_fixation_colorbar",
        "fixation_colorbar_orientation",
        "fixation_colorbar_length",
        "fixation_colorbar_thickness",
        "fixation_colorbar_tickangle",
        "fixation_colorbar_tickfont_size",
        "show_order",
        "order_font_size",
        "order_font_color",
        "fixation_snap_to_line",
        "fixation_snap_position",
    ),
    "Saccades": (
        "show_saccades",
        "saccade_color",
        "saccade_style",
        "saccade_width",
        "saccade_opacity",
        "show_saccade_arrows",
        "saccade_arrow_size",
        "saccade_render_mode",
        "saccade_color_mode",
        "saccade_class_colors",
    ),
    "Stimulus": (
        "show_word_labels",
        "redact_text",
        "line_spacing",
        "scale_text_to_boxes",
        "text_color",
        "background_color",
        "highlight_column",
        "highlight_text_color",
        "critical_span_style",
        "span_border_color",
        "show_stimulus_image",
        "background_image",
        "background_image_size",
        "background_image_origin",
        "background_image_opacity",
    ),
    "Word boxes": (
        "show_words",
        "word_box_color",
        "word_box_line_opacity",
        "word_box_fill_color",
        "word_box_fill_opacity",
    ),
    "Heatmap": (
        "show_heatmap",
        "heatmap_style",
        "heatmap_metric",
        "heatmap_colorscale",
        "heatmap_norm",
        "heatmap_range",
        "heatmap_opacity",
        "heatmap_sigma_px",
        "word_heatmap_col",
        "word_heatmap_title",
        "show_heatmap_colorbar",
        "heatmap_colorbar_orientation",
        "heatmap_colorbar_length",
        "heatmap_colorbar_thickness",
        "heatmap_colorbar_tickangle",
        "heatmap_colorbar_tickfont_size",
    ),
    "Raw gaze": (
        "show_raw_gaze",
        "raw_gaze_color",
        "raw_gaze_marker_size",
        "raw_gaze_opacity",
    ),
    "Filters & highlights": ("fixation_flags", "saccade_classes"),
    "Figure & canvas": (
        "fit_to_monitor",
        "crop_margin",
        "show_plot_frame",
        "plot_frame_color",
        "show_coordinate_grid",
        "coordinate_grid_spacing",
        "coordinate_grid_font_size",
        "x_field",
        "y_field",
    ),
    "Title & labels": (
        "illustration_text",
        "illustration_reasons",
        "title_font_size",
        "caption_font_size",
        "caption_color",
    ),
    "Hover": ("word_hover_fields", "word_hover_measure", "fixation_hover_fields"),
    "Legends": (
        "legend_layout",
        "show_color_legend",
        "show_highlight_legend",
        "saccade_type_legend",
        "duration_size_legend",
    ),
    "Animate": ("anim_grid_step_ms", "anim_max_frames"),
    "Compare": (
        "label_a",
        "label_b",
        "style_a",
        "style_b",
        "show_legend",
        "compare_stimulus",
        "words_b",
        "fixations_b",
        "fixation_flags_b",
        "background_image_b",
        "background_image_size_b",
        "background_image_origin_b",
    ),
    "Drift correction": ("show_connectors", "connector_y"),
}

#: The options no ``render`` flag sets, so no flag help can describe them.
_OPTION_NOTES = {
    "illustration_reasons": (
        "Why the figure is labeled an illustration. The builder works it out "
        "from `illustration_label`. Pass it only to word the label yourself."
    ),
    "words_b": "Scanpath B's Words table, for a replay of two scanpaths.",
    "fixations_b": "Scanpath B's Fixations table, for a replay of two scanpaths.",
    "show_connectors": (
        "Draw a line from each fixation's recorded height to its corrected "
        "one. Set by `plot_scanpath(drift_connectors=True)`."
    ),
    "connector_y": (
        "The recorded heights those lines start from. Set by `plot_scanpath`."
    ),
}

#: The ``render`` flags that set no single figure option, by the topic they
#: are listed under. The rest are placed through the option they set.
_FLAG_TOPICS = {
    "--palette": "Fixations",
    "--fix-index-range": "Filters & highlights",
    "--illustration": "Title & labels",
    "--illustration-label": "Title & labels",
    "--canvas": "Figure & canvas",
    "--crop-to-data": "Figure & canvas",
    "--font-size": "Stimulus",
    "--font-family": "Stimulus",
    "--sample-raw-gaze": "Raw gaze",
    "--raw-gaze-schema": "Raw gaze",
    # Hidden from --help: each sets both color bars.
    "--colorbars": "Fixations",
    "--colorbar-orientation": "Fixations",
    "--colorbar-tickangle": "Fixations",
    "--colorbar-tickfont-size": "Fixations",
    "--title": "Title & labels",
    "--caption": "Title & labels",
    "--playback-speed": "Animate",
    "--no-autoplay": "Animate",
    "--width": "Size and export",
    "--height": "Size and export",
    "--scale": "Size and export",
    "--width-mm": "Size and export",
    "--width-in": "Size and export",
    "--dpi": "Size and export",
    "--separable-layers": "Size and export",
    "--print-code": "Size and export",
    "--print-code-explicit": "Size and export",
    # Only with SCANPATH_EXPERIMENTAL=1, which the published site is built
    # without; the test suite runs with it.
    "--drift-correction": "Drift correction",
    "--drift-connectors": "Drift correction",
}

#: `render`'s argument groups other than the figure one, by the heading they
#: are listed under (matched on the title's first word).
_RENDER_GROUP_TOPICS = {
    "options": "Trial and output",
    "input": "Input",
    "comparison": "Compare",
}


def _figure_kinds() -> dict:
    from scanpath_studio import api

    return {
        "plot": api.figure_options("static"),
        "animate": api.figure_options("animation"),
        "compare": api.figure_options("comparison"),
    }


def _option_topics(names) -> dict[str, str]:
    """Option name → its section, refusing one no section (or two) names."""
    topic_of: dict[str, str] = {}
    for topic, members in OPTION_TOPICS.items():
        for name in members:
            if name in topic_of:
                raise RuntimeError(f"{name} is under {topic_of[name]} and {topic}")
            topic_of[name] = topic
    unplaced = sorted(set(names) - set(topic_of))
    stale = sorted(set(topic_of) - set(names))
    if unplaced or stale:
        raise RuntimeError(
            f"OPTION_TOPICS is out of date: unplaced {unplaced}, unknown {stale}"
        )
    return topic_of


def _option_flags(name: str) -> list[str]:
    from scanpath_studio.code_snippet import _CLI_EMITTERS

    return _emitter_flags(_CLI_EMITTERS.get(name)) or _UNEMITTED_FLAGS.get(name, [])


def _render_flag_topics(parser) -> dict[str, list]:
    """``render``'s flags by topic: trial and input first, then the figure
    sections in `OPTION_TOPICS` order, then size and export, then comparison."""
    kinds = _figure_kinds()
    topic_of = _option_topics(set().union(*kinds.values()))
    flag_topic = {
        flag: topic_of[name] for name in topic_of for flag in _option_flags(name)
    } | _FLAG_TOPICS
    order = [
        "Trial and output",
        "Input",
        *OPTION_TOPICS,
        "Size and export",
    ]
    # Compare's flags stay together after everything they style.
    order.remove("Compare")
    order.append("Compare")
    topics: dict[str, list] = {topic: [] for topic in order}
    for group in parser._action_groups:
        group_topic = _RENDER_GROUP_TOPICS.get(group.title.split()[0].rstrip(":"))
        for action in _visible_actions(group):
            if group_topic is not None and group_topic != "Compare":
                topic = group_topic
            else:
                topic = next(
                    (flag_topic[f] for f in action.option_strings if f in flag_topic),
                    group_topic,
                )
            if topic is None:
                raise RuntimeError(
                    f"{action.option_strings} has no topic: add it to _FLAG_TOPICS"
                )
            topics[topic].append(action)
    return {topic: actions for topic, actions in topics.items() if actions}


def _emitter_flags(emitter) -> list[str]:
    """The ``render`` flag(s) a `code_snippet._CLI_EMITTERS` entry writes.

    Most entries are closures over their flag (``_valued("--x")``); the rest are
    plain functions that spell theirs in the source. Either way the flag is read,
    never listed a second time here.
    """
    if emitter is None:
        return []
    cells = [cell.cell_contents for cell in emitter.__closure__ or ()]
    flags = [c for c in cells if isinstance(c, str) and c.startswith("--")]
    if not flags:
        flags = re.findall(r"\"(--[a-z0-9-]+)\"", inspect.getsource(emitter))
    return list(dict.fromkeys(flags))


def _default_cell(value) -> str:
    text = repr(value)
    if len(text) > 40:
        return f"`{type(value).__name__}`, see `figure_options()`"
    return f"`{text}`"


#: Options a snippet never writes as a flag but `render` still sets:
#: the raw-gaze layer follows the table `--raw-gaze` loads.
_UNEMITTED_FLAGS = {"show_raw_gaze": ["--raw-gaze", "--no-raw-gaze"]}


#: A help string's "(default: …)", which the options table has a column for.
_DEFAULT_NOTE = re.compile(r"\s*\(default: [^()]*\)")


def _describing_flag(flags: list[str], default):
    """The flag whose help describes the option: the one that changes its
    default (``--no-heatmap`` for an option that is off, ``--heatmap``)."""
    if len(flags) > 1 and isinstance(default, bool):
        negative = [flag for flag in flags if flag.startswith("--no-")]
        positive = [flag for flag in flags if not flag.startswith("--no-")]
        preferred = negative if default else positive
        if preferred:
            return preferred[0]
    return flags[0] if flags else None


def figure_options_reference(*, heading: str = "##") -> str:
    """Every figure keyword, by section: its default, its ``render`` flag, what
    it does, the values it takes, and the builders that accept it.

    Built from `api.figure_options` (the defaults the builders render with), the
    CLI emitter table the Share tab's Code uses, and
    the ``render`` parser, whose help strings describe each option. A flag that
    parser does not have fails the docs build rather than being printed.
    """
    from scanpath_studio import cli
    from scanpath_studio.constants import drift_correction_enabled
    from scanpath_studio.plots import FIGURE_OPTION_CHOICES

    kinds = _figure_kinds()
    parser = cli._render_parser()
    formatter = parser._get_formatter()
    action_of = {
        flag: action for action in parser._actions for flag in action.option_strings
    }
    topic_of = _option_topics(set().union(*kinds.values()))
    out = []
    for topic, names in OPTION_TOPICS.items():
        if topic == "Drift correction" and not drift_correction_enabled():
            # Set by an experimental feature: the published site leaves it out.
            continue
        out += [
            f"{heading} {topic}",
            "",
            '<div class="sps-reference-table sps-option-table" markdown>',
            "",
            "| Option and `render` flag | Default | Description |",
            "| --- | --- | --- |",
        ]
        for name in names:
            assert topic_of[name] == topic
            default = next(k[name] for k in kinds.values() if name in k)
            flags = _option_flags(name)
            unknown = [flag for flag in flags if flag not in action_of]
            if unknown:
                raise RuntimeError(f"{name}: {unknown} is not a `render` flag")
            flag = _describing_flag(flags, default)
            if flag is not None:
                # The Default column already says it.
                help_text = _DEFAULT_NOTE.sub(
                    "", formatter._expand_help(action_of[flag])
                )
                description = _cell(help_text)
            else:
                description = _OPTION_NOTES[name]
            choices = FIGURE_OPTION_CHOICES.get(name)
            if choices:
                values = ", ".join(f"`{c!r}`" for c in choices)
                description += f" One of {values}."
            builders = [kind for kind, options in kinds.items() if name in options]
            if len(builders) < len(kinds):
                description += f" *{' and '.join(builders).capitalize()} only.*"
            # The flags go under the name, so the description keeps the width.
            names_cell = "<br>".join([f"`{name}`", *(f"`{f}`" for f in flags)])
            out.append(f"| {names_cell} | {_default_cell(default)} | {description} |")
        out += ["", "</div>", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

#: The app's own figure config (`tabs._render_true_scale_chart`): Plotly's zoom
#: re-lays-out the axes and leaves markers and text at their pixel sizes, which
#: is exactly what the true-scale embed exists to avoid. No "Share chart…"
#: upload to Plotly Cloud, as in the app (`constants.PLOTLY_CONFIG`).
_PLOT_CONFIG = {
    "showSendToCloud": False,
    "displaylogo": False,
    "responsive": False,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "pan2d",
        "select2d",
        "lasso2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "resetScale2d",
    ],
}


def saccade_class_legend() -> list[tuple[str, str]]:
    """The reading classes' labels and colours, as the app draws them."""
    from scanpath_studio.constants import (
        SACCADE_CLASS_COLORS,
        SACCADE_CLASS_LABELS,
        SACCADE_CLASS_ORDER,
    )

    return [
        (SACCADE_CLASS_LABELS[c], SACCADE_CLASS_COLORS[c]) for c in SACCADE_CLASS_ORDER
    ]


def embed(
    fig, *, caption: str | None = None, legend=None, preview: bool = False
) -> str:
    """A figure for a docs page, drawn the way the app draws it.

    The figure's own JSON rides in the page, in its ``data-figure`` attribute,
    and ``javascripts/figures.js`` renders it at its exact pixel size and scales
    the whole block uniformly to the column — the app's true-to-scale rule, so
    word labels keep the size they were fitted to. Plotly itself is loaded only
    on a page that has a figure, from the site's own copy (``mkdocs_hooks.on_post_build``), never a CDN.
    ``legend`` is ``[(label, colour), …]``, drawn as swatches under the figure.
    ``preview`` disables interaction for gallery thumbnails; replays loop while visible.
    A replay also carries the app's player, so its ▶ Play keeps real time, and
    its frames packed, as the app's page does.
    """
    from plotly.io.json import to_json_plotly

    from scanpath_studio.plots import replay_page

    width = int(fig.layout.width or 900)
    height = int(fig.layout.height or 600)
    # A replay keeps time on the app's own wall-clock player, not on
    # Plotly's frame queue; figures.js runs it once the plot is drawn — and the
    # script rebuilds the frames the spec leaves out. It waits for ▶
    # on detail pages; gallery previews instead loop while visible.
    page = replay_page(fig)
    if page is None:
        spec = json.loads(fig.to_json())
    else:
        figure_dict, player = page
        spec = json.loads(to_json_plotly(figure_dict))
        spec["player"] = player
        spec["layout"]["meta"]["scanpath_autoplay"] = preview
        if preview:
            spec["layout"]["meta"]["sps_preview_loop"] = True
            spec["layout"]["updatemenus"] = []
            spec["layout"]["sliders"] = []
    spec["config"] = {**_PLOT_CONFIG, "staticPlot": True} if preview else _PLOT_CONFIG
    # An attribute, not a `<script type="application/json">`: Material's instant
    # navigation re-creates every inline script in the new page from its text
    # alone, dropping the type, so the JSON would run as JavaScript and the
    # figure would be gone after a click from another page or a heading link.
    payload = html.escape(json.dumps(spec, separators=(",", ":")))
    # A <div>, not a <figure>: Material sizes figures to fit their content, and
    # the plot's content is positioned absolutely, so a figure collapses to 0.
    extra = ""
    if legend:
        items = "".join(
            f'<span class="sps-legend-item"><span class="sps-swatch" '
            f'style="background:{html.escape(color)}"></span>{html.escape(label)}</span>'
            for label, color in legend
        )
        extra += f'<p class="sps-legend">{items}</p>'
    if caption:
        extra += f'<p class="sps-caption">{html.escape(caption)}</p>'
    return (
        '<div class="sps-figure">'
        f'<div class="sps-plot" data-width="{width}" data-height="{height}" '
        f'style="aspect-ratio: {width} / {height}; max-width: {width}px" '
        f'data-figure="{payload}"></div>'
        f"{extra}</div>"
    )
