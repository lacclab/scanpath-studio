"""A real browser on the running app: it loads, the figure draws, a popover opens.

``AppTest`` runs no frontend, so nothing else in the suite sees what the app's
CSS and page scripts do to Streamlit's page: the true-scale plot iframe, the
rail's popovers, the scripts that reach into the parent document. A Streamlit
release that changes the markup those rely on breaks the app without failing
any other test, and the package pins no upper bound on Streamlit.

Needs Playwright and its Chromium (``pip install playwright`` then
``playwright install chromium``); skipped without them. CI runs it in its own
job (``ci.yml`` → *Browser smoke test*).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.timeout(300)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def app_url():
    """The app on a free loopback port, saving nothing to the recovery cache."""
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "streamlit_app.py"),
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=ROOT,
        env={**os.environ, "SCANPATH_STUDIO_PERSIST": "0"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 120
    while True:
        if proc.poll() is not None:
            pytest.fail(f"the app exited with code {proc.returncode}")
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2):
                break
        except OSError:
            if time.time() > deadline:
                proc.terminate()
                pytest.fail("the app did not answer its health check in 120 s")
            time.sleep(0.5)
    yield url
    proc.terminate()
    proc.wait(timeout=30)


@pytest.fixture(scope="module")
def page(app_url):
    """One page on the app's first visit, with its uncaught errors collected."""
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except sync_api.Error as exc:
            pytest.skip(f"no Chromium for Playwright ({exc.message.splitlines()[0]})")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.errors = []
        page.on("pageerror", lambda exc: page.errors.append(str(exc)))
        page.goto(app_url)
        _settle(page)
        _close_tour(page)
        yield page
        browser.close()


def _settle(page, quiet_ms: int = 1500, timeout_s: float = 150) -> None:
    """Wait until Streamlit has stopped running the script for ``quiet_ms``."""
    page.locator('[data-testid="stApp"]').wait_for(timeout=timeout_s * 1000)
    status = page.locator('[data-testid="stStatusWidget"]')
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not status.count():
            page.wait_for_timeout(quiet_ms)
            if not status.count():
                return
        page.wait_for_timeout(250)
    pytest.fail("the app never stopped running")


def _close_tour(page) -> None:
    """Dismiss the first-visit tour card, which covers the page."""
    for _ in range(3):
        buttons = [
            button
            for button in page.locator(
                '.st-key-tour_sp_close button, .st-key-tour_card button:has-text("Skip")'
            ).all()
            if button.is_visible()
        ]
        if not buttons:
            return
        buttons[0].click()
        _settle(page)


def _plot_frame(page, key: str):
    """The iframe holding the true-scale plot drawn under ``key``."""
    deadline = time.time() + 60
    while time.time() < deadline:
        for frame in page.frames:
            try:
                if frame.locator(f"#truescale-{key}").count():
                    return frame
            except sync_api.Error:
                continue
        page.wait_for_timeout(500)
    pytest.fail(f"no plot iframe holds #truescale-{key}")


def test_the_page_renders_without_an_exception(page):
    assert page.locator('[data-testid="stTopNavLink"]').count() >= 3
    assert not page.locator('[data-testid="stException"]').count()


def test_the_scanpath_figure_draws(page):
    frame = _plot_frame(page, "single")
    frame.locator("#truescale-single.js-plotly-plot").wait_for(timeout=60_000)
    # Plotly has drawn: the figure's own SVG layers and at least one trace.
    assert frame.locator("#truescale-single .main-svg").count() >= 1
    assert frame.locator("#truescale-single .scatterlayer .trace").count() >= 1


def test_a_rail_popover_opens(page):
    page.locator(".st-key-split_mode_rail_fix_popover button").first.click()
    body = page.locator('[data-testid="stPopoverBody"]')
    body.first.wait_for(state="visible", timeout=15_000)
    assert "Size" in body.first.inner_text()
    page.keyboard.press("Escape")


def test_no_script_error_reached_the_page(page):
    assert page.errors == []
