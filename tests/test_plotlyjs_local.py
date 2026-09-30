"""ENG-64: the in-app figure loads plotly.js from this app's own server.

It used to be ``fig.to_html(include_plotlyjs="cdn")``, so every figure asked
``cdn.plot.ly`` for the library and drew blank without a network — the desktop
app included. The installed plotly package's own ``plotly.min.js`` is now served
through Streamlit's custom-component route, and these tests pin each link of that
chain: the file is the installed build, the URL is the relative one the route
answers, the route really serves it, and the embedded figure asks for nothing else.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest
from plotly.offline import get_plotlyjs, get_plotlyjs_version
from starlette.applications import Starlette
from streamlit.components.lib.local_component_registry import LocalComponentRegistry
from streamlit.web.server.starlette.starlette_routes import create_component_routes

from scanpath_studio import html_embed
from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def test_the_served_file_is_the_installed_plotly_build():
    """Version-matched to the figure JSON: the bytes plotly.py itself would inline."""
    served = html_embed.plotlyjs_dir() / html_embed.PLOTLYJS_FILENAME
    assert served.read_text(encoding="utf-8") == get_plotlyjs()


def test_the_url_is_relative_versioned_and_ends_in_js():
    src = html_embed.plotlyjs_src()
    # Relative, so it resolves under server.baseUrlPath and a proxy prefix
    # (Community Cloud's /~/+/) exactly as Streamlit's own ./static/ bundle does.
    assert not src.startswith(("/", "http:", "https:"))
    assert src.startswith("component/")
    assert f"plotlyjs-{get_plotlyjs_version()}/" in src
    assert src.endswith("/plotly.min.js")


async def _asgi_get(app, path: str) -> tuple[int, dict[str, str], bytes]:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"127.0.0.1")],
        "server": ("127.0.0.1", 8501),
        "client": ("127.0.0.1", 50000),
    }
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    body = b"".join(
        m.get("body", b"") for m in sent if m["type"] == "http.response.body"
    )
    return start["status"], headers, body


def test_streamlits_component_route_serves_it():
    """Register the way a script run does, then GET the URL through the real route."""
    registry = LocalComponentRegistry()
    runtime = SimpleNamespace(component_registry=registry)
    target = "streamlit.components.v1.component_registry"
    with (
        mock.patch(f"{target}.get_script_run_ctx", return_value=object()),
        mock.patch(f"{target}.get_instance", return_value=runtime),
    ):
        src = html_embed.plotlyjs_src()
        # Every figure render registers again; the same component must not warn.
        assert html_embed.plotlyjs_src() == src
    assert len(registry.get_components()) == 1

    app = Starlette(routes=create_component_routes(registry, None))
    status, headers, body = asyncio.run(_asgi_get(app, f"/{src}"))
    assert status == 200
    assert "javascript" in headers["content-type"]
    assert body == get_plotlyjs().encode("utf-8")
    # Stored by the browser, but no max-age or validator — which is why the
    # loader keeps a copy on the page (see test_the_loader_script below).
    assert headers["cache-control"] == "public"


def test_the_loader_script():
    script = html_embed.plotlyjs_script()
    src = html_embed.plotlyjs_src()
    assert f'var src = "{src}"' in script
    assert "cdn.plot.ly" not in script
    # The page copy is read back out of the HTTP cache, not downloaded twice.
    assert 'cache: "force-cache"' in script
    assert "__scanpathPlotlyJs" in script
    # The written tag must not close the loader's own <script> early.
    assert "<\\/script>" in script
    assert script.count("</script>") == 1
    assert script.rstrip().endswith("</script>")


def test_the_app_figure_loads_plotly_from_its_own_server(monkeypatch):
    """End to end: the embedded figure names the local asset and no CDN."""
    import streamlit as st

    embedded: list[str] = []
    real_iframe = st.iframe

    def spy(src, *args, **kwargs):
        embedded.append(str(src))
        return real_iframe(src, *args, **kwargs)

    monkeypatch.setattr(st, "iframe", spy)
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["source"] = "demo"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    figures = [html for html in embedded if "Plotly.newPlot" in html]
    assert figures, "the scanpath figure was not embedded"
    assert not any("cdn.plot.ly" in html for html in embedded)
    for html in figures:
        assert html_embed.plotlyjs_src() in html
        # Loaded by URL, never inlined into the rerun's websocket payload.
        assert len(html) < 1_000_000
