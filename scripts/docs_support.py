"""What the docs build generates instead of restating (ENG-77, ENG-78, ENG-79).

The pages call these from ``exec="true"`` fences (markdown-exec), and
``scripts/mkdocs_hooks.py`` puts this folder on ``sys.path`` for them. Each
function returns the Markdown or HTML for one block, read from the thing it
describes — ``CITATION.cff``, ``CHANGELOG.md``, the ``render`` parser, the figure
option registry, a built figure — so none of it can drift from the code the way
a hand-maintained copy does.
"""

from __future__ import annotations

import argparse
import html
import inspect
import json
import re
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/lacclab/scanpath-studio"
BLOB_URL = f"{REPO_URL}/blob/main/"


# ---------------------------------------------------------------------------
# Cite
# ---------------------------------------------------------------------------

#: Combining mark → the BibTeX accent command that spells it, so the entry
#: compiles under classic BibTeX as well as biber.
_BIBTEX_ACCENTS = {
    "\u0300": "`",  # grave
    "\u0301": "'",  # acute
    "\u0302": "^",  # circumflex
    "\u0303": "~",  # tilde
    "\u0308": '"',  # diaeresis
    "\u030a": "r",  # ring
    "\u030c": "v",  # caron
    "\u0327": "c",  # cedilla
}


def _bibtex_text(text: str) -> str:
    """``Jäger`` → ``J{\\"a}ger``: every accented letter as an escaped group."""
    out = []
    for char in unicodedata.normalize("NFD", text):
        accent = _BIBTEX_ACCENTS.get(char)
        if accent and out:
            base = out.pop()
            sep = " " if accent.isalpha() else ""
            out.append(f"{{\\{accent}{sep}{base}}}")
        else:
            out.append(char)
    return unicodedata.normalize("NFC", "".join(out))


def _initials(given: str) -> str:
    """``Deborah N.`` → ``D. N.``; ``Jean-Paul`` → ``J.-P.`` (APA 7)."""
    parts = []
    for name in given.split():
        if name.endswith(".") and len(name) <= 3:
            parts.append(name)
        else:
            parts.append("-".join(f"{piece[0]}." for piece in name.split("-")))
    return " ".join(parts)


def _cff() -> dict:
    return yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))


def software_citation() -> str:
    """The software citation, as BibTeX and APA tabs, from ``CITATION.cff``.

    The same file feeds GitHub's *Cite this repository* button and the Zenodo
    record, so the page cannot disagree with either.
    """
    cff = _cff()
    year = str(cff["date-released"])[:4]
    doi = cff["doi"]
    authors = cff["authors"]
    # One author per line, so the entry fits a code block without scrolling.
    bib_authors = " and\n             ".join(
        f"{_bibtex_text(a['family-names'])}, {_bibtex_text(a['given-names'])}"
        for a in authors
    )
    bibtex = "\n".join(
        [
            f"@software{{Shubi_Scanpath_Studio_{year},",
            f"  author  = {{{bib_authors}}},",
            f"  title   = {{{{{cff['title']}}}}},",
            f"  year    = {{{year}}},",
            f"  version = {{{cff['version']}}},",
            f"  doi     = {{{doi}}},",
            f"  url     = {{https://doi.org/{doi}}},",
            f"  license = {{{cff['license']}}},",
            "}",
        ]
    )
    names = [f"{a['family-names']}, {_initials(a['given-names'])}" for a in authors]
    listed = ", ".join(names[:-1]) + f", & {names[-1]}" if len(names) > 1 else names[0]
    apa = (
        f"{listed} ({year}). *{cff['title']}* (Version {cff['version']}) "
        f"[Computer software]. https://doi.org/{doi}"
    )
    return "\n".join(
        [
            '=== "BibTeX"',
            "",
            "    ```bibtex",
            *(f"    {line}" for line in bibtex.splitlines()),
            "    ```",
            "",
            '=== "APA"',
            "",
            f"    {apa}",
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


#: The first release written in the two-tier shape (ENG-34): a short headline
#: list per group, the longer notes under ``### Details``. Sections before it
#: are one long paragraph per item; they stay in the repository file.
CHANGELOG_SINCE = "0.28.0"


def changelog() -> str:
    """The headline lists of ``CHANGELOG.md``, from `CHANGELOG_SINCE` on.

    The repository file is the one people edit, and the one that keeps the full
    notes (ENG-80: the site carries only the headlines, which are written to be
    read on their own). Group headings become bold labels, so the table of
    contents is one entry per version.
    """
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    # The file's own title and preamble ("documented in this file") are the
    # repository's; the page has its own.
    start = next(i for i, line in enumerate(lines) if line.startswith("## "))
    out: list[str] = []
    in_details = done = False
    for line in lines[start:]:
        if line.startswith("## "):
            if done:
                break
            in_details = False
            done = line.startswith(f"## [{CHANGELOG_SINCE}]")
            # `## [0.31.0] - 2026-09-24` → `## 0.31.0 — 2026-09-24`: the
            # brackets are Keep a Changelog's link syntax.
            version = re.sub(r"^## \[([^\]]+)\](?: - )?", r"## \1 — ", line)
            out.append(version.removesuffix(" — "))
        elif line.strip() == "### Details":
            in_details = True
        elif in_details:
            continue
        elif line.startswith("#"):
            out += [f"**{line.lstrip('#').strip()}**", ""]
        else:
            line = _RELATIVE_LINK.sub(lambda m: f"]({_link_target(m.group(1))})", line)
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# In-app tutorials
# ---------------------------------------------------------------------------


def in_app_tutorials() -> str:
    """The ❓ Help → 🧭 Tutorials registry, one section per tutorial.

    The page used to restate these steps by hand, a second copy of
    `tour.TUTORIALS` to keep in sync (ENG-77). Each heading's anchor is the
    fragment of that tutorial's own ``docs_url``, so the app's "docs" link lands
    on its section by construction; steps a gated feature owns are dropped by
    `tour.steps_of`, exactly as the release build's app drops them.
    """
    from scanpath_studio import tour

    out = []
    for tutorial in tour.TUTORIALS:
        anchor = tutorial.docs_url.partition("#")[2]
        out += [
            f"### {tutorial.title} {{ #{anchor} }}",
            "",
            f"{tutorial.outcome} *About {tutorial.estimated_time}; needs "
            f"{tutorial.prerequisite[0].lower()}{tutorial.prerequisite[1:]}.*",
            "",
        ]
        for number, step in enumerate(tour.steps_of(tutorial), 1):
            body = " ".join(step.body.split())
            out.append(f"{number}. **{step.title}.** {body}")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI reference
# ---------------------------------------------------------------------------


def _parsers() -> dict:
    from scanpath_studio import cli

    return {
        "render": cli._render_parser,
        "analyze": cli._analyze_parser,
        "corpus": cli._corpus_parser,
        "cache": cli._cache_parser,
    }


#: A tracker id as the CLI's help strings cite them — ``(VIZ-8)``, a leading
#: ``VIZ-7:`` or ``PRE-2 `` — which a reader of the reference has no use for.
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


def cli_help() -> str:
    """``scanpath-studio --help`` as the installed command prints it."""
    from scanpath_studio import cli

    return f"```text\n{cli._HELP}\n```"


def cli_reference(command: str) -> str:
    """Every flag of one subcommand, one table per argument group.

    Walks the parser the command itself parses with, so a flag cannot exist
    without appearing here, and its default and help are the ones ``--help``
    prints.
    """
    parser = _parsers()[command]()
    formatter = parser._get_formatter()
    out = []
    for group in parser._action_groups:
        actions = [
            action
            for action in group._group_actions
            if action.help != argparse.SUPPRESS
            and not isinstance(action, argparse._HelpAction)
        ]
        if not actions:
            continue
        out += [f"**{_cell(group.title)}**", ""]
        out += [
            "| Option | Value | Default | Description |",
            "| --- | --- | --- | --- |",
        ]
        for action in actions:
            flags = ", ".join(f"`{flag}`" for flag in action.option_strings)
            if action.nargs == 0:
                value = "switch"
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
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Figure options
# ---------------------------------------------------------------------------


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
    if len(text) > 48:
        return f"`{type(value).__name__}` (see `figure_options()`)"
    return f"`{text}`"


def figure_options_table() -> str:
    """Every figure keyword → its default, its ``render`` flag, its builders.

    Built from `api.figure_options` (the defaults the builders render with) and
    the CLI emitter table the Share subtab's *Reproduce this figure* block uses,
    and checked against the ``render`` parser: a flag that parser does not have
    fails the docs build rather than being printed.
    """
    from scanpath_studio import api, cli
    from scanpath_studio.code_snippet import _CLI_EMITTERS

    kinds = {
        "plot": api.figure_options("static"),
        "animate": api.figure_options("animation"),
        "compare": api.figure_options("comparison"),
    }
    known = {
        flag
        for action in cli._render_parser()._actions
        for flag in action.option_strings
    }
    # `md_in_html` renders the table inside the div, which is what lets the
    # stylesheet keep the option names from wrapping mid-word.
    rows = [
        '<div class="sps-reference-table" markdown>',
        "",
        "| Option | Default | `render` flag | Accepted by |",
        "| --- | --- | --- | --- |",
    ]
    for name in sorted(set().union(*kinds.values())):
        default = next(k[name] for k in kinds.values() if name in k)
        flags = _emitter_flags(_CLI_EMITTERS.get(name))
        unknown = [flag for flag in flags if flag not in known]
        if unknown:
            raise RuntimeError(f"{name}: {unknown} is not a `render` flag")
        builders = [kind for kind, options in kinds.items() if name in options]
        accepted = "all three" if len(builders) == len(kinds) else ", ".join(builders)
        flag_cell = ", ".join(f"`{flag}`" for flag in flags) or "—"
        rows.append(
            f"| `{name}` | {_default_cell(default)} | {flag_cell} | {accepted} |"
        )
    rows += ["", "</div>"]
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

#: The app's own figure config (`tabs._render_true_scale_chart`): Plotly's zoom
#: re-lays-out the axes and leaves markers and text at their pixel sizes, which
#: is exactly what the true-scale embed exists to avoid.
_PLOT_CONFIG = {
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


def embed(fig, *, caption: str | None = None, legend=None) -> str:
    """A figure for a docs page, drawn the way the app draws it.

    The figure's own JSON rides in the page, and ``javascripts/figures.js``
    renders it at its exact pixel size and scales the whole block uniformly to
    the column — the app's true-to-scale rule, so word labels keep the size they
    were fitted to. Plotly itself is loaded only on a page that has a figure,
    from the site's own copy (``mkdocs_hooks.on_post_build``), never a CDN.
    ``legend`` is ``[(label, colour), …]``, drawn as swatches under the figure.
    """
    width = int(fig.layout.width or 900)
    height = int(fig.layout.height or 600)
    spec = json.loads(fig.to_json())
    spec["config"] = _PLOT_CONFIG
    payload = json.dumps(spec, separators=(",", ":")).replace("</", "<\\/")
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
        f'style="aspect-ratio: {width} / {height}; max-width: {width}px">'
        f'<script type="application/json">{payload}</script></div>'
        f"{extra}</div>"
    )
