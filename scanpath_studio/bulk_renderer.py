"""Draw successive bulk figures on one Kaleido page with bounded reuse."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Iterator
from concurrent.futures import CancelledError
from contextlib import contextmanager, suppress

from anyio.from_thread import start_blocking_portal
from kaleido import Kaleido
from plotly.graph_objects import Figure

from .animation_export import RendererStoppedError
from .export_png import MAX_RGBA_PIXELS

_MAX_PAGE_FIGURES = 16
# Chromium can retain native raster buffers across page reloads.
_MAX_BROWSER_FIGURES = 256
_BROWSER_TIMEOUT = 90


def _page_pixels(fig: Figure, opts: dict) -> int:
    """Charge an embedded image, a dense plot or a WebGL scene a whole page."""
    pixels = math.ceil(opts["width"] * opts["height"] * opts["scale"] ** 2)
    if pixels >= MAX_RGBA_PIXELS or fig.layout.images:
        return MAX_RGBA_PIXELS
    marks = len(fig.layout.shapes) + len(fig.layout.annotations)
    for trace in fig.data:
        if trace.type != "scatter":
            return MAX_RGBA_PIXELS
        coordinates = trace.x if trace.x is not None else trace.y
        if coordinates is not None:
            # Plotly can supply a base64 typed array. Its string length is a
            # conservative upper bound on the number of coordinates.
            if isinstance(coordinates, dict):
                if "bdata" not in coordinates:
                    return MAX_RGBA_PIXELS
                coordinates = coordinates["bdata"]
            marks += len(coordinates)
    return MAX_RGBA_PIXELS if marks > 10_000 else pixels


class _BulkBrowser(Kaleido):
    """A single tab owned by one export, drawing one figure at a time."""

    def __init__(self, path: str):
        super().__init__(path=path)
        self._tab = None
        self._draws = 0
        self._pixels = 0
        self._previous_format = None

    async def _return_kaleido_tab(self, tab) -> None:
        # Kaleido calls this even when drawing raises. Keep its normal render,
        # print, and timeout handling, and defer the reload until the next draw.
        self._tab = tab
        await self.tabs_ready.put(tab)

    async def draw(self, fig: Figure, opts: dict) -> bytes:
        pixels = _page_pixels(fig, opts)
        fmt = opts["format"]
        if self._tab is not None:
            if (
                self._draws >= _MAX_PAGE_FIGURES
                or self._pixels + pixels > MAX_RGBA_PIXELS
                # Each PDF replaces Kaleido's print image and page stylesheet.
                # Other formats draw on the standard page.
                or (self._previous_format == "pdf" and fmt != "pdf")
            ):
                async with asyncio.timeout(_BROWSER_TIMEOUT):
                    await self._tab.reload()
                self._draws = self._pixels = 0
            else:
                self._tab.js_logger.reset()
        try:
            data = await self.calc_fig(fig, opts=opts)
        except BaseException:
            # The next trial cannot inherit a partially drawn figure.
            self._pixels = MAX_RGBA_PIXELS
            raise
        self._draws += 1
        self._pixels += pixels
        self._previous_format = fmt
        return data


@contextmanager
def bulk_renderer(browser_path: str) -> Iterator[Callable[[Figure, dict], bytes]]:
    """Yield a synchronous draw call, including for callers running an event loop."""

    async def start():
        browser = _BulkBrowser(path=browser_path)
        try:
            async with asyncio.timeout(_BROWSER_TIMEOUT):
                await browser.open()
        except BaseException:
            await browser.close()
            raise
        return browser

    # Keep Chrome's pipe reader and watchdog running while the caller writes
    # the archive. Open, draw and close on this one event loop.
    with start_blocking_portal() as portal:
        browser = portal.call(start)
        count = 0

        def draw(fig, opts):
            nonlocal browser, count
            if browser is None:
                raise RendererStoppedError(
                    "The browser could not restart during figure export."
                )
            if count >= _MAX_BROWSER_FIGURES or browser.subprocess.poll() is not None:
                portal.call(browser.close)
                browser = None
                browser = portal.call(start)
                count = 0
            count += 1
            try:
                return portal.call(browser.draw, fig, opts)
            except CancelledError as exc:
                # Choreographer cancels outstanding commands when Chrome exits.
                raise RendererStoppedError(
                    "The browser closed during figure export."
                ) from exc

        try:
            yield draw
        finally:
            if browser is not None:
                with suppress(Exception):
                    portal.call(browser.close)
