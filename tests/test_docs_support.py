"""The docs' generated content (ENG-77, ENG-78, ENG-79).

``scripts/docs_support.py`` writes the parts of the site that are read from
the code rather than restated: the CLI and figure-option references, the in-app
tutorial steps, the Cite and Changelog pages, the gallery's figures. The docs
build runs it too (``mkdocs build --strict`` fails on an exception), but these
catch a break in the ordinary test run, before anyone builds the site.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import docs_support  # noqa: E402

from scanpath_studio import api, cli, tour  # noqa: E402


@pytest.mark.parametrize(
    ("command", "parser"),
    [
        ("render", cli._render_parser),
        ("analyze", cli._analyze_parser),
        ("corpus", cli._corpus_parser),
        ("cache", cli._cache_parser),
    ],
)
def test_the_cli_reference_lists_every_flag(command, parser):
    page = docs_support.cli_reference(command)
    for action in parser()._actions:
        if action.help == argparse.SUPPRESS or isinstance(action, argparse._HelpAction):
            continue
        for flag in action.option_strings:
            assert f"`{flag}`" in page, f"{command}: {flag} missing"


def test_the_cli_reference_leaves_out_tracker_ids():
    page = docs_support.cli_reference("render")
    assert not re.search(r"\b(VIZ|PRE|EXP|CMP|DATA)-\d+\b", page)


def test_the_figure_option_table_covers_every_option():
    table = docs_support.figure_options_table()
    names = (
        set(api.figure_options())
        | set(api.figure_options("animation"))
        | set(api.figure_options("comparison"))
    )
    for name in names:
        assert f"| `{name}` |" in table, name


def test_every_in_app_tutorial_has_the_anchor_its_docs_link_names():
    page = docs_support.in_app_tutorials()
    for tutorial in tour.TUTORIALS:
        fragment = tutorial.docs_url.partition("#")[2]
        assert fragment, tutorial.id
        assert f"{{ #{fragment} }}" in page, tutorial.id


def test_the_changelog_page_is_headlines_from_the_two_tier_release_on():
    page = docs_support.changelog()
    assert page.startswith("## Unreleased")
    assert f"## {docs_support.CHANGELOG_SINCE} — " in page
    # Nothing older, and none of the long notes.
    assert "## 0.27.2" not in page
    assert "### Details" not in page and "#### " not in page


def test_the_citation_is_the_cff():
    # PyYAML is a docs-extra dependency; CI's test legs install only the test
    # extra, and its Docs build job builds this page anyway.
    pytest.importorskip("yaml")
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    doi = re.search(r"^doi:\s*\"?([^\s\"]+)", text, re.MULTILINE).group(1)
    version = re.search(r"^version:\s*([^\s]+)", text, re.MULTILINE).group(1)
    page = docs_support.software_citation()
    assert f"doi     = {{{doi}}}" in page
    assert f"version = {{{version}}}" in page
    # Accented names are escaped for classic BibTeX, and read plainly in APA.
    assert 'J{\\"a}ger, Lena' in page and "Jäger, L." in page


def test_an_embedded_figure_cannot_close_its_script_tag():
    import plotly.graph_objects as go

    fig = go.Figure(go.Scatter(x=[1], y=[1], name="</script><b>x</b>"))
    fig.update_layout(width=400, height=300)
    html = docs_support.embed(fig)
    assert html.count("</script>") == 1
    assert 'data-width="400" data-height="300"' in html
