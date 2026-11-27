"""The export download page links only to its own folder.

`assets/bundle_download/index.html` reads the export's folder, file name and
sizes from its URL hash, which whoever opened the page controls. It must build
same-folder links from them and refuse anything else: a script URL or another
host in the hash must never become a link. Runs in a real browser, because the
page's script is the code under test.
"""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGE_DIR = (
    Path(__file__).resolve().parents[1]
    / "scanpath_studio"
    / "assets"
    / "bundle_download"
)
NAME = "scanpath_export_20261123_101500.zip"
VALID = f"id=abc_DEF-123&name={NAME}&size=2500&part=1000"
REFUSED = "Open this download from the Export panel in Scanpath Studio."


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def origin():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(_Quiet, directory=str(PAGE_DIR))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


def _open(browser, origin, fragment, *, stream=True):
    """Open the page with ``fragment``; return the visible link's href (or None) and the status."""
    context = browser.new_context(accept_downloads=False)
    page = context.new_page()
    if not stream:
        # A browser without service workers takes the download-in-parts path.
        page.add_init_script(
            "Object.defineProperty(Navigator.prototype, 'serviceWorker', {get: () => undefined})"
        )
    page.goto(f"{origin}/index.html#{fragment}")
    page.wait_for_function(
        "!document.getElementById('status').textContent.startsWith('Preparing')"
    )
    link = "download" if stream else "piece"
    href = page.evaluate(
        f"(() => {{ const a = document.getElementById('{link}');"
        " return a.hidden || !a.getAttribute('href') ? null : a.href; })()"
    )
    status = page.evaluate("document.getElementById('status').textContent")
    context.close()
    return href, status


def test_the_stream_link_stays_in_the_page_folder(browser, origin):
    href, _ = _open(browser, origin, VALID)
    assert href == f"{origin}/abc_DEF-123/{NAME}?size=2500&part=1000"


def test_the_part_links_stay_in_the_page_folder(browser, origin):
    href, status = _open(browser, origin, VALID, stream=False)
    assert href == f"{origin}/abc_DEF-123/0.part"
    assert status.startswith("This browser cannot stream the ZIP")


@pytest.mark.parametrize("stream", [True, False], ids=["stream", "parts"])
@pytest.mark.parametrize(
    "fragment",
    [
        f"id=javascript:alert(1)&name={NAME}&size=1&part=1",
        f"id=//evil.example&name={NAME}&size=1&part=1",
        "id=abc&name=javascript:alert(1)//.zip&size=1&part=1",
        "id=abc&name=x.zip&size=1&part=1",
        f"id=abc&name={NAME}&size=-1&part=1",
        "",
    ],
    ids=["script-id", "host-id", "script-name", "other-name", "bad-size", "empty"],
)
def test_a_hash_it_did_not_write_is_refused(browser, origin, fragment, stream):
    href, status = _open(browser, origin, fragment, stream=stream)
    assert href is None
    assert status == REFUSED
