"""Page isolation and lifetime of the native bulk renderer."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import plotly.graph_objects as go
import pytest
from kaleido import Kaleido

from scanpath_studio import bulk_renderer, export


def test_a_batch_reuses_pages_and_isolates_large_or_failed_draws(monkeypatch):
    page = 0
    draws = []
    lifecycle = []

    async def reload():
        nonlocal page
        page += 1

    tab = SimpleNamespace(reload=reload, js_logger=SimpleNamespace(reset=lambda: None))

    def init(browser, *, path):
        assert path == "/test/browser"
        browser.tabs_ready = asyncio.Queue()
        browser.subprocess = SimpleNamespace(poll=lambda: None)

    async def open_browser(browser):
        nonlocal page
        if lifecycle:
            assert lifecycle[-1][0] == "close"
            page += 1
        lifecycle.append(("open", threading.get_ident()))
        await browser.tabs_ready.put(tab)

    async def calc(browser, figure, opts):
        borrowed = await browser.tabs_ready.get()
        try:
            draws.append((opts["format"], page))
            if opts["format"] == "invalid":
                raise ValueError("unknown format")
            return b"rendered"
        finally:
            await browser._return_kaleido_tab(borrowed)

    async def close_browser(browser):
        lifecycle.append(("close", threading.get_ident()))

    monkeypatch.setattr(Kaleido, "__init__", init)
    monkeypatch.setattr(Kaleido, "open", open_browser)
    monkeypatch.setattr(Kaleido, "close", close_browser)
    monkeypatch.setattr(Kaleido, "calc_fig", calc)
    monkeypatch.setattr(bulk_renderer, "_MAX_PAGE_FIGURES", 3)
    monkeypatch.setattr(bulk_renderer, "_MAX_BROWSER_FIGURES", 9)
    monkeypatch.setattr(bulk_renderer, "MAX_RGBA_PIXELS", 50_000)
    monkeypatch.setattr(
        "scanpath_studio.animation_export.chromium_browser_path",
        lambda: "/test/browser",
    )

    async def from_running_loop():
        fig = go.Figure(go.Scatter(x=[1, 2], y=[1, 4]))
        with export._figure_renderer(10) as render:
            for fmt in ("png", "svg", "pdf", "pdf", "pdf", "svg"):
                render(fig, fmt, 100, 100, 1)
            render(fig, "png", 100, 100, 2)  # Fills the remaining 40k pixels.
            with pytest.raises(ValueError, match="unknown format"):
                render(fig, "invalid", 100, 100, 1)
            render(fig, "svg", 100, 100, 1)
            fig.add_layout_image(dict(source="data:image/png;base64,AA=="))
            render(fig, "svg", 100, 100, 1)
            fig.layout.images = ()
            render(fig, "svg", 100, 100, 1)

    asyncio.run(from_running_loop())
    assert draws == [
        ("png", 0),
        ("svg", 0),
        ("pdf", 0),
        ("pdf", 1),
        ("pdf", 1),
        ("svg", 2),  # Leave the PDF print stylesheet behind.
        ("png", 2),
        ("invalid", 3),
        ("svg", 4),
        ("svg", 5),  # New browser after nine attempted figures.
        ("svg", 6),  # The embedded image had a page to itself.
    ]
    assert [action for action, _ in lifecycle] == ["open", "close", "open", "close"]
    assert {thread for _, thread in lifecycle} == {lifecycle[0][1]}
    assert lifecycle[0][1] != threading.get_ident()


def test_dense_figures_get_the_entire_page_budget():
    opts = dict(width=100, height=100, scale=1)
    for trace in (
        go.Scatter(x=list(range(10_001))),
        go.Scatter(y=list(range(10_001))),
        go.Scatter(x={"dtype": "i1", "bdata": "AAAA" * 3_334}),
        go.Heatmap(z=[[1, 2], [3, 4]]),
    ):
        assert (
            bulk_renderer._page_pixels(go.Figure(trace), opts)
            == bulk_renderer.MAX_RGBA_PIXELS
        )


def test_a_failed_restart_closes_both_browsers_and_leaves_the_next_file_retryable(
    monkeypatch,
):
    events = []

    class Browser:
        def __init__(self, *, path):
            self.exited = None
            self.subprocess = SimpleNamespace(poll=lambda: self.exited)

        async def open(self):
            events.append("open")
            if events.count("open") == 2:
                raise OSError("cannot start Chrome")

        async def close(self):
            events.append("close")

        async def draw(self, fig, opts):
            self.exited = 1
            return b"image"

    monkeypatch.setattr(bulk_renderer, "_BulkBrowser", Browser)
    with bulk_renderer.bulk_renderer("/test/browser") as render:
        assert render(None, {}) == b"image"
        with pytest.raises(OSError, match="cannot start"):
            render(None, {})
        with pytest.raises(
            bulk_renderer.RendererStoppedError, match="could not restart"
        ):
            render(None, {})
    assert events == ["open", "close", "open", "close"]
