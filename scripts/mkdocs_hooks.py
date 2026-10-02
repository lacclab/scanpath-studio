"""MkDocs hooks for the docs build (ENG-78, ENG-79).

The pages' generated content — the gallery, printed example output, the CLI
and figure-option references, the Cite and Changelog pages — is produced by
``exec="true"`` fences run by markdown-exec, calling ``scripts/docs_support.py``.
(It replaced UX-21's hand-rolled fence runner: markdown-exec is also what
Zensical supports, so the pages do not tie the site to MkDocs.) What is left
here is the plumbing that plugin cannot do:

* put ``scripts/`` on ``sys.path`` so a fence can ``import docs_support``;
* copy the installed plotly's own ``plotly.min.js`` into the built site, which
  ``javascripts/figures.js`` loads on the pages that carry a figure — the site
  never fetches Plotly from a CDN, as the app itself has not since ENG-64;
* draw the app's icons (ENG-88). A page names an icon with the shortcode the
  app's labels use, ``:material/database:``, and it renders as the same
  Material Symbols glyph, from the font file Streamlit ships — copied into the
  built site, never fetched;
* check that ``llms.txt`` lists the pages (ENG-92). The llmstxt plugin only
  sees a page it rebuilt, so a ``--dirty`` build wrote the file as bare section
  headings — and the site shipped it that way for weeks.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent


def on_config(config, **kwargs):
    """Make ``docs_support`` importable from the pages' fences. Done here, not
    at import: MkDocs restores ``sys.path`` after loading a hooks file."""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    return config


#: ``:material/name:`` — the shortcode `constants.ICONS` holds, so a page and
#: the label it describes name an icon the same way.
_ICON = re.compile(r":material/([a-z0-9_]+):")
#: Fenced code and inline code, which keep a shortcode literal.
_CODE = re.compile(r"(^(```|~~~).*?^\2[^\n]*$|`[^`\n]+`)", re.MULTILINE | re.DOTALL)
#: Where the font lands in the built site, and where `extra.css` looks for it.
_ICON_FONT = Path("assets") / "fonts" / "material-symbols-rounded.woff2"


def _icon_span(match: re.Match) -> str:
    # The name is drawn by CSS (`::before { content: attr(data-icon) }`), so it
    # stays out of the page text, the search index and a copied sentence.
    return f'<span class="sps-icon" data-icon="{match.group(1)}" aria-hidden="true"></span>'


def on_page_markdown(markdown: str, **kwargs) -> str:
    """Turn each ``:material/…:`` shortcode outside code into its icon."""
    out, last = [], 0
    for code in _CODE.finditer(markdown):
        out.append(_ICON.sub(_icon_span, markdown[last : code.start()]))
        out.append(code.group(0))
        last = code.end()
    out.append(_ICON.sub(_icon_span, markdown[last:]))
    return "".join(out)


def _streamlit_icon_font() -> Path:
    """The Material Symbols font Streamlit's frontend loads for ``:material/…:``."""
    import streamlit

    media = Path(streamlit.__file__).parent / "static" / "static" / "media"
    fonts = sorted(media.glob("MaterialSymbols-Rounded*.woff2"))
    if not fonts:
        raise FileNotFoundError(f"no Material Symbols font under {media}")
    return fonts[0]


def on_post_build(config, **kwargs) -> None:
    """Ship ``plotly.min.js`` beside ``figures.js`` — the build the figure JSON
    was written for, since it comes from the same plotly package — and the
    icon font, the one the installed Streamlit draws its icons with."""
    from scanpath_studio.html_embed import plotlyjs_dir

    site = Path(config["site_dir"])
    target = site / "javascripts" / "plotly.min.js"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(plotlyjs_dir() / "plotly.min.js", target)

    font = site / _ICON_FONT
    font.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_streamlit_icon_font(), font)

    _check_llms_txt(site / "llms.txt")


def _check_llms_txt(path: Path) -> None:
    """Fail the build when a section of ``llms.txt`` lists no page.

    Hooks run after the plugins, so the llmstxt plugin has written the file."""
    sections = re.split(r"^## ", path.read_text(), flags=re.MULTILINE)[1:]
    empty = [s.splitlines()[0] for s in sections if "\n- [" not in s]
    if empty:
        raise RuntimeError(
            f"{path.name} lists no page under {', '.join(empty)}: a dirty build "
            "skips unchanged pages, and the llmstxt plugin only sees those it builds"
        )
