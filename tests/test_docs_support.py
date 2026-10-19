"""The docs' generated content.

``scripts/docs_support.py`` writes the parts of the site that are read from
the code rather than restated: the CLI and figure-option references, the Cite
and Changelog pages, the gallery's figures. The docs build runs it too
(``mkdocs build --strict`` fails on an exception), but these catch a break in
the ordinary test run, before anyone builds the site.
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
        ("check", cli._check_parser),
        ("cache", cli._cache_parser),
        ("version", cli._version_parser),
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


def test_the_figure_option_reference_covers_every_option_once():
    page = docs_support.figure_options_reference()
    names = (
        set(api.figure_options())
        | set(api.figure_options("animation"))
        | set(api.figure_options("comparison"))
    )
    for name in names:
        assert page.count(f"| `{name}`") == 1, name


def test_the_figure_option_reference_describes_every_option():
    # Every row has a description: its flag's help, or a note for the few
    # options no flag sets.
    page = docs_support.figure_options_reference()
    rows = [line for line in page.splitlines() if line.startswith("| `")]
    assert rows
    for row in rows:
        assert row.rstrip("| ").split(" | ")[-1].strip(), row


def test_a_figure_option_without_a_section_fails_the_build():
    names = set().union(*docs_support._figure_kinds().values())
    with pytest.raises(RuntimeError, match="unplaced"):
        docs_support._option_topics(names | {"new_option"})


def test_the_published_references_leave_out_drift_correction(monkeypatch):
    # The site is built without SCANPATH_EXPERIMENTAL, so the experimental
    # feature's options and flags stay off it.
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL", raising=False)
    assert "## Drift correction" not in docs_support.figure_options_reference()
    render = docs_support.cli_reference("render", heading="###")
    assert "--drift-correction" not in render
    assert "### Drift correction" not in render


def test_the_render_reference_is_split_by_topic():
    page = docs_support.cli_reference("render", heading="###")
    headings = re.findall(r"^### (.+)$", page, flags=re.MULTILINE)
    assert headings[:2] == ["Trial and output", "Input"]
    assert {"Fixations", "Heatmap", "Compare", "Size and export"} <= set(headings)
    assert len(headings) == len(set(headings))


def test_the_api_index_lists_what_the_page_documents():
    page = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    documented = re.findall(r"^::: (\S+)$", page, flags=re.MULTILINE)
    index = docs_support.api_index()
    assert documented
    for path in documented:
        assert f"][{path}] |" in index, path


def _heading_anchors(page: Path) -> set[str]:
    """The anchors a page's headings get: an explicit ``{ #id }``, else the
    toc extension's default slug (lower-case, punctuation dropped, spaces to
    hyphens)."""
    anchors = set()
    for line in page.read_text(encoding="utf-8").splitlines():
        match = re.match(r"#+\s+(.*?)\s*(?:\{\s*#([\w-]+)\s*\})?\s*$", line)
        if not match:
            continue
        title, explicit = match.groups()
        anchors.add(
            explicit
            or re.sub(r"[\s]+", "-", re.sub(r"[^\w\s-]", "", title).strip().lower())
        )
    return anchors


@pytest.mark.parametrize("tutorial", tour.TUTORIALS, ids=lambda t: t.id)
def test_every_in_app_tutorial_links_a_page_and_heading_that_exist(tutorial):
    # The "Matching written tutorial" button opens the docs page that
    # covers the task, so a renamed page or heading must fail here, not 404.
    url, _, fragment = tutorial.docs_url.partition("#")
    base = tour.DOCS_URL
    assert url.startswith(base), tutorial.docs_url
    path = url.removeprefix(base).strip("/")
    page = ROOT / "docs" / f"{path}.md"
    if not page.exists():
        page = ROOT / "docs" / path / "index.md"
    assert page.exists(), tutorial.docs_url
    if fragment:
        assert fragment in _heading_anchors(page), tutorial.docs_url


def test_the_citation_is_the_cff():
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    doi = re.search(r"^doi:\s*\"?([^\s\"]+)", text, re.MULTILINE).group(1)
    version = re.search(r"^version:\s*([^\s]+)", text, re.MULTILINE).group(1)
    page = docs_support.software_citation()
    assert f"doi     = {{{doi}}}" in page
    assert f"version = {{{version}}}" in page
    # Accented names are escaped for classic BibTeX, and read plainly in APA.
    assert 'J{\\"a}ger, Lena' in page and "Jäger, L." in page


def test_an_embedded_figure_cannot_leave_its_attribute():
    # The JSON is an attribute, not an inline script, which Material's
    # instant navigation would re-run as JavaScript.
    import html
    import json

    import plotly.graph_objects as go

    name = '"></div><script>x</script><b>x</b>'
    fig = go.Figure(go.Scatter(x=[1], y=[1], name=name))
    fig.update_layout(width=400, height=300)
    page = docs_support.embed(fig)
    assert "<script" not in page
    assert 'data-width="400" data-height="300"' in page
    found = re.search(r'data-figure="([^"]*)"', page)
    assert json.loads(html.unescape(found.group(1)))["data"][0]["name"] == name


def test_an_embedded_replay_carries_the_replay_player():
    # The Gallery's ▶ Play keeps real time on the app's own player —
    # figures.js runs it against the drawn plot — and a static figure has none.
    import html
    import json

    from scanpath_studio import api
    from scanpath_studio.plots import animation_player_post_script, replay_page

    words, fixations = api.load_sample_data(names="canonical")
    pid, tid = api.list_trials(words, fixations).iloc[0]
    replay = api.animate_scanpath(words, fixations, pid, tid, fix_index_range=(1, 5))
    static = api.plot_scanpath(words, fixations, pid, tid, fix_index_range=(1, 5))

    def payload(fig) -> dict:
        page = docs_support.embed(fig)
        found = re.search(r'data-figure="([^"]*)"', page)
        return json.loads(html.unescape(found.group(1)))

    # The spec leaves the frames out; the script ahead of the player
    # rebuilds them (`plots.replay_page`).
    assert payload(replay)["player"].endswith(animation_player_post_script(replay))
    assert payload(replay)["player"] == replay_page(replay)[1]
    assert "frames" not in payload(replay)
    assert "player" not in payload(static)
    # The page draws a figure before it is on screen, so a replay waits for ▶.
    assert replay.layout.meta["scanpath_autoplay"] is True
    assert payload(replay)["layout"]["meta"]["scanpath_autoplay"] is False
