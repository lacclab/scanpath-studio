#!/usr/bin/env python
"""Re-capture the docs' app screenshots (ENG-78).

The feature guides each carry one or two screenshots of the running app. They
are taken by this script rather than by hand, so that re-capturing them after a
UI change is one command:

    uv run --with playwright python scripts/capture_docs_screenshots.py

It starts its own app on a free port with the recovery cache off — so the
captures show the bundled demo at its defaults, never whatever a local session
last held — drives it through deep links, and writes WebP files to
``docs/assets/screenshots/``. The browser plumbing (waiting for Streamlit to go
idle, closing the tour, resetting the view) is the manuscript's
``paper/paper_ui_screenshots.py``, reused rather than copied.

Chrome: ``DOCS_CHROME`` if set, else the Chrome for Testing that Kaleido already
downloaded for static export, else Playwright's own Chromium
(``playwright install chromium``).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets" / "screenshots"
sys.path.insert(0, str(ROOT / "paper"))
import paper_ui_screenshots as ui  # noqa: E402

VIEWPORT = {"width": 1440, "height": 1000}
WEBP_QUALITY = 82

#: Numbered callouts for the annotated Scanpath view, in reading order:
#: (selector, which visible match). Each is a container the in-app tour already
#: spotlights, so the numbers land on the regions the tour names. A badge sits
#: on its region's top-right corner, where the app leaves space.
SCANPATH_CALLOUTS = (
    ('[data-testid="stTopNavLinkContainer"]', "last"),  # the views and dialogs
    (".st-key-tour_grp_trial_picker", "first"),  # dataset and trial pickers
    (".st-key-tour_grp_chips", "first"),  # the trial's summary chips
    (".st-key-tour_grp_plot", "first"),  # the figure
    (".st-key-tour_grp_viz_controls", "first"),  # the plot controls
    (".st-key-tour_grp_subtabs", "first"),  # the subtabs
)

CALLOUT_JS = """(callouts) => {
  document.querySelectorAll('.docs-callout').forEach(el => el.remove());
  callouts.forEach(([selector, which], i) => {
    const shown = [...document.querySelectorAll(selector)]
      .filter(el => el.getBoundingClientRect().width > 0);
    const target = which === 'last' ? shown[shown.length - 1] : shown[0];
    if (!target) throw new Error(`no visible ${selector}`);
    const box = target.getBoundingClientRect();
    const badge = document.createElement('div');
    badge.className = 'docs-callout';
    badge.textContent = String(i + 1);
    badge.style.cssText = [
      'position:absolute', 'z-index:2147483647', 'width:26px', 'height:26px',
      'border-radius:50%', 'background:#d55e00', 'color:#fff',
      'font:700 14px/26px system-ui,sans-serif', 'text-align:center',
      'box-shadow:0 0 0 3px #fff,0 2px 6px rgba(0,0,0,.35)',
      `left:${box.right + window.scrollX - 14}px`,
      `top:${box.top + window.scrollY - 14}px`,
    ].join(';');
    document.body.appendChild(badge);
  });
}"""


def find_chrome() -> str | None:
    if os.environ.get("DOCS_CHROME"):
        return os.environ["DOCS_CHROME"]
    try:
        from choreographer.browsers.chromium import Chromium

        found = Chromium.find_browser(skip_local=False)
        return str(found) if found else None
    except Exception:  # choreographer missing or no Chrome found
        return None


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_app(port: int) -> subprocess.Popen:
    env = {**os.environ, "SCANPATH_STUDIO_PERSIST": "0"}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_app.py",
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
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health") as r:
                if r.status == 200:
                    return proc
        except OSError:
            time.sleep(1)
    proc.kill()
    raise SystemExit("the app never answered its health check")


def _webp(name: str) -> None:
    """Replace ``name.png`` (as ``ui.shot`` writes it, trimmed) with WebP."""
    png, webp = OUT / f"{name}.png", OUT / f"{name}.webp"
    Image.open(png).convert("RGB").save(webp, "WEBP", quality=WEBP_QUALITY, method=6)
    png.unlink()
    print(f"  → {webp.name} ({webp.stat().st_size // 1024} KB)")


def capture(page: Page) -> None:
    ui.deep_link(page, ui.DEMO_TRIAL)
    ui.reset_viz(page)

    print("scanpath view")
    page.evaluate(CALLOUT_JS, [list(c) for c in SCANPATH_CALLOUTS])
    page.wait_for_timeout(300)
    ui.shot(page, "scanpath-view")
    _webp("scanpath-view")
    page.evaluate(
        "() => document.querySelectorAll('.docs-callout').forEach(e => e.remove())"
    )

    print("export and share")
    tabs = page.locator('[data-testid="stTabs"]').first
    for label, name in (("Export", "export"), ("Share", "share")):
        page.locator(f'[data-testid="stTab"]:has-text("{label}")').first.click()
        ui.settle(page, quiet=2.0)
        ui.shot_block(page, name, tabs, max_h=900)
        _webp(name)
    page.locator('[data-testid="stTab"]:has-text("Annotations")').first.click()
    ui.settle(page, quiet=1.5)

    print("corpus analysis")
    ui.nav(page, "Corpus Analysis")
    page.wait_for_timeout(2000)
    ui.shot(page, "corpus-analysis")
    _webp("corpus-analysis")

    print("data page")
    ui.nav(page, "Data")
    page.wait_for_timeout(1500)
    ui.shot(page, "data-page")
    _webp("data-page")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    port = free_port()
    ui.URL = f"http://127.0.0.1:{port}"
    ui.OUT = OUT
    app = start_app(port)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=find_chrome())
            ctx = browser.new_context(
                viewport=VIEWPORT, device_scale_factor=2, color_scheme="light"
            )
            ctx.add_init_script(
                "document.addEventListener('DOMContentLoaded', () => {"
                "const s = document.createElement('style');"
                f"s.textContent = {ui.HIDE_CSS!r};"
                "document.head.appendChild(s);});"
            )
            capture(ctx.new_page())
            browser.close()
    finally:
        app.terminate()
        app.wait(timeout=30)


if __name__ == "__main__":
    main()
