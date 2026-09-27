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
  never fetches Plotly from a CDN, as the app itself has not since ENG-64.
"""

from __future__ import annotations

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


def on_post_build(config, **kwargs) -> None:
    """Ship ``plotly.min.js`` beside ``figures.js`` — the build the figure JSON
    was written for, since it comes from the same plotly package."""
    from scanpath_studio.html_embed import plotlyjs_dir

    target = Path(config["site_dir"]) / "javascripts" / "plotly.min.js"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(plotlyjs_dir() / "plotly.min.js", target)
