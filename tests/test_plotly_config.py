"""No figure offers Plotly Cloud's "Share chart…" upload (BUG-101).

plotly.js 3 turns `showSendToCloud` on by default, which puts a modebar button
on every figure that serializes it — words, coordinates, hover fields — and
sends it to cloud.plotly.com. Every surface that draws a figure must pass
``constants.PLOTLY_CONFIG``, which turns it off.
"""

from __future__ import annotations

import ast
import html
import json
import re
import sys
from pathlib import Path

import plotly.graph_objects as go

from scanpath_studio import api, tabs
from scanpath_studio.constants import PLOTLY_CONFIG

ROOT = Path(__file__).resolve().parents[1]
_OFF = re.compile(r'"showSendToCloud":\s*false')


def _fig() -> go.Figure:
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4], text=["a", "b"]))
    fig.update_layout(width=300, height=200)
    return fig


def _animated() -> go.Figure:
    fig = _fig()
    fig.frames = [go.Frame(data=[go.Scatter(x=[1], y=[3])], name="0")]
    return fig


def test_the_config_turns_cloud_sharing_off():
    assert PLOTLY_CONFIG["showSendToCloud"] is False


def test_the_app_embed_turns_it_off():
    assert _OFF.search(tabs._true_scale_plot_html(_fig(), key="t"))


def test_the_html_downloads_turn_it_off():
    download = tabs._figure_download_data(
        _fig(), "HTML", canvas_width=300, canvas_height=200
    )
    assert _OFF.search(download())
    assert _OFF.search(tabs._animation_html(_animated()))


def test_save_figure_html_turns_it_off(tmp_path):
    for name, fig in (("static.html", _fig()), ("replay.html", _animated())):
        path = api.save_figure(fig, tmp_path / name)
        assert _OFF.search(path.read_text(encoding="utf-8")), name


def test_the_docs_figures_turn_it_off():
    sys.path.insert(0, str(ROOT / "scripts"))
    import docs_support

    markup = docs_support.embed(_fig())
    payload = re.search(r'data-figure="([^"]*)"', markup).group(1)
    spec = json.loads(html.unescape(payload))
    assert spec["config"]["showSendToCloud"] is False


def test_every_figure_call_passes_a_config():
    """A new `to_html` / `write_html` / `st.plotly_chart` must pass one too.

    ``config=`` or a ``**options`` that carries it — the behavioural tests above
    cover the latter's contents.
    """
    missing = []
    for path in sorted((ROOT / "scanpath_studio").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else None
            if name not in {"to_html", "write_html", "plotly_chart"}:
                continue
            if any(kw.arg in (None, "config") for kw in node.keywords):
                continue
            missing.append(f"{path.name}:{node.lineno}")
    assert not missing, missing
