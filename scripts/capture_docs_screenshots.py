#!/usr/bin/env python
"""Re-capture the docs' app screenshots (ENG-78).

The feature guides each carry one or two screenshots of the running app. They
are taken by this script rather than by hand, so that re-capturing them after a
UI change is one command:

    uv run --with playwright python scripts/capture_docs_screenshots.py

``--controls`` captures the All controls page's pictures instead (one per part
of the Scanpath page, each menu open), into ``docs/assets/screenshots/controls/``.

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


def start_app(port: int, env: dict[str, str] | None = None) -> subprocess.Popen:
    """The app on ``port``, with the recovery cache off unless ``env`` says otherwise."""
    env = {**os.environ, "SCANPATH_STUDIO_PERSIST": "0", **(env or {})}
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


def capture_overview(page: Page) -> None:
    """The Scanpath view with its regions numbered (``--overview``), on a
    dataset whose trials have several screens, so the Screen picker shows."""
    ui.deep_link(page, {**MULTI_SCREEN_LINK, "screen": "Paragraph"})
    page.locator(".st-key-tour_grp_screen_picker").first.wait_for(
        state="visible", timeout=900_000
    )
    ui.reset_viz(page)
    ui.settle(page, quiet=3.0)
    page.evaluate(CALLOUT_JS, [list(c) for c in SCANPATH_CALLOUTS])
    page.wait_for_timeout(300)
    ui.shot(page, "scanpath-view")
    _webp("scanpath-view")


def capture(page: Page) -> None:
    ui.deep_link(page, ui.DEMO_TRIAL)
    ui.reset_viz(page)

    # The numbered overview (scanpath-view) is `--overview`'s: it needs a
    # dataset with screens, which the demo is not.

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


#: The All controls page's pictures: one per part of the Scanpath page, each
#: menu captured open with its own layer on, so nothing in it is greyed out.
#: ``(file, layer switch to turn on or None, menu container key)``.
CONTROL_MENUS = (
    ("fixations", "global_show_fix", "split_mode_rail_fix_popover"),
    ("saccades", "global_show_saccades", "split_mode_rail_sac_popover"),
    ("stimulus", "global_show_stimulus", "split_mode_rail_stim_popover"),
    ("word-boxes", "global_show_words", "split_mode_rail_boxes_popover"),
    ("heatmap", "global_show_heatmap", "split_mode_rail_heatmap_popover"),
    ("raw-gaze", "global_show_raw_gaze", "split_mode_rail_rawgaze_popover"),
    ("filters", None, "split_mode_rail_filter_popover"),
    ("figure-canvas", None, "split_mode_rail_figure_popover"),
)
CONTROLS_OUT = OUT / "controls"


def _switch_on(page: Page, key: str) -> None:
    box = page.locator(f".st-key-{key} input").first
    if box.count() and not box.is_checked():
        ui.toggle(page, key)


def _shot_controls(page: Page, name: str, locator, **kw) -> None:
    ui.shot(page, name, locator=None if locator is page else locator, **kw)
    png, webp = CONTROLS_OUT / f"{name}.png", CONTROLS_OUT / f"{name}.webp"
    Image.open(png).convert("RGB").save(webp, "WEBP", quality=WEBP_QUALITY, method=6)
    png.unlink()
    print(f"  → controls/{webp.name} ({webp.stat().st_size // 1024} KB)")


# The trial bar is shot on a dataset whose trials span several screens, so its
# Screen picker shows too: OneStop's ordinary reading, whose parts (title,
# paragraph, questions …) are screens, once downloaded into data/OneStop.
MULTI_SCREEN_LINK = {"source": "corpus", "corpus": "onestop-ordinary-reading"}


def _shot_trial_row(page: Page) -> None:
    ui.deep_link(page, MULTI_SCREEN_LINK)
    screens = page.locator(".st-key-tour_grp_screen_picker")
    try:
        screens.first.wait_for(state="visible", timeout=900_000)
    except Exception:
        print("  no multi-screen dataset here (data/OneStop); trial-row kept")
        return
    ui.settle(page, quiet=2.0)
    _shot_controls(
        page, "trial-row", page.locator(".st-key-tour_grp_trial_picker").first
    )


def _open_menu_body(page: Page, popover_key: str):
    """Open a rail ▾ menu and return its body, unclipped."""
    page.locator(f".st-key-{popover_key} button").first.click()
    ui.settle(page, quiet=1.5)
    body = page.locator('[data-testid="stPopoverBody"]').last
    # The whole menu, not the part its scroll area shows.
    body.evaluate(
        "el => { el.style.maxHeight = 'none'; el.style.overflow = 'visible';"
        " el.querySelectorAll('*').forEach(c => { if (c.scrollHeight > c.clientHeight)"
        " { c.style.maxHeight = 'none'; c.style.overflow = 'visible'; } }); }"
    )
    page.wait_for_timeout(400)
    return body


def _shot_mode_menu(page: Page, name: str, toggle_key: str, popover_key: str) -> None:
    """A mode's ▾ menu, with the mode on so nothing in it is greyed out."""
    _switch_on(page, toggle_key)
    _shot_controls(page, name, _open_menu_body(page, popover_key))
    page.keyboard.press("Escape")
    ui.settle(page, quiet=1.0)
    ui.toggle(page, toggle_key)


#: The two designs saved for the picture of My designs.
EXAMPLE_DESIGNS = ("My design 1", "My design 2")


def _save_design(page: Page, name: str) -> None:
    page.locator(".st-key-design_save button").first.click()
    ui.settle(page, quiet=1.5)
    dialog = page.locator('[role="dialog"]').last
    dialog.locator('input[type="text"]').last.fill(name)
    dialog.locator(".st-key-design_save_go button").first.click()
    ui.settle(page, quiet=2.0)


def _shot_designs(page: Page) -> None:
    """Design presets, My designs open on two saved designs, and the palette."""
    for name in EXAMPLE_DESIGNS:
        _save_design(page, name)
    shell = page.locator(".st-key-design_shell").first
    if shell.locator("details").first.get_attribute("open") is None:
        shell.locator("summary").first.click()
        ui.settle(page, quiet=1.5)
    page.evaluate("window.scrollTo(0, 0)")
    rail = page.locator(".st-key-scanpath_rail").first.bounding_box()
    top = page.get_by_text("Design presets", exact=True).first.bounding_box()
    palette = page.locator(".st-key-global_palette").first.bounding_box()
    pad = 10
    clip = {
        "x": rail["x"],
        "y": top["y"] - 2,
        "width": rail["width"],
        "height": palette["y"] + palette["height"] + pad - top["y"],
    }
    _shot_controls(page, "designs", page, clip=clip)


def _shot_chips_menu(page: Page) -> None:
    """The ✏️ chips menu, with one chip highlighted so its ✕ is live."""
    page.locator(".st-key-iconpop_chip_fields button").first.click()
    ui.settle(page, quiet=1.5)
    body = page.locator('[data-testid="stPopoverBody"]').last
    picker = body.locator(".st-key-trial_chip_color_participant_id")
    picker.locator('[data-testid="stColorPickerBlock"]').first.click()
    page.wait_for_timeout(400)
    hex_box = page.locator("input:visible").last  # the picker's hex box
    hex_box.fill("#FFD966")
    hex_box.press("Enter")
    body.locator("p").first.click()
    ui.settle(page, quiet=2.0)
    body = page.locator('[data-testid="stPopoverBody"]').last
    body.evaluate(
        "el => { el.style.maxHeight = 'none'; el.style.overflow = 'visible'; }"
    )
    page.wait_for_timeout(400)
    _shot_controls(page, "chips", body)
    page.keyboard.press("Escape")
    ui.settle(page, quiet=1.0)


def _shot_reset(page: Page) -> None:
    """The whole Plot controls column, the Reset visualization button circled."""
    page.locator(".st-key-reset_viz_settings_btn").first.evaluate(
        "el => { el.style.outline = '3px solid #e5262c';"
        " el.style.outlineOffset = '5px'; el.style.borderRadius = '999px'; }"
    )
    page.evaluate("window.scrollTo(0, 0)")
    box = page.locator(".st-key-scanpath_rail").first.bounding_box()
    pad = 12  # room for the ring, which sits outside the button
    clip = {
        "x": box["x"] - pad,
        "y": box["y"],
        "width": box["width"] + 2 * pad,
        "height": box["height"] + pad,
    }
    _shot_controls(page, "reset", page, clip=clip)
    page.locator(".st-key-reset_viz_settings_btn").first.evaluate(
        "el => { el.style.outline = ''; el.style.outlineOffset = '';"
        " el.style.borderRadius = ''; }"
    )


def _shot_compare_bar(page: Page) -> None:
    """The whole trial control bar in Compare: A's row and B's under it."""
    page.evaluate("window.scrollTo(0, 0)")
    a = page.locator(".st-key-tour_grp_trial_picker").first.bounding_box()
    b = page.locator(".st-key-tour_grp_compare_picker").first.bounding_box()
    left = min(a["x"], b["x"])
    right = max(a["x"] + a["width"], b["x"] + b["width"])
    clip = {
        "x": left,
        "y": a["y"],
        "width": right - left,
        "height": b["y"] + b["height"] - a["y"],
    }
    _shot_controls(page, "compare-row", page, clip=clip)


def capture_controls(page: Page, only: set[str] | None = None) -> None:
    """The All controls page's pictures (``--controls [NAME ...]``)."""
    CONTROLS_OUT.mkdir(parents=True, exist_ok=True)
    ui.OUT = CONTROLS_OUT

    def wanted(name: str) -> bool:
        return not only or name in only

    ui.deep_link(page, ui.DEMO_TRIAL)
    ui.reset_viz(page)

    if wanted("plot-controls"):
        print("plot controls")
        _shot_controls(
            page, "plot-controls", page.locator(".st-key-scanpath_rail").first
        )

    if wanted("animate"):
        print("animate menu")
        _shot_mode_menu(page, "animate", "single_animate", "split_mode_animate_popover")
    if wanted("compare-menu"):
        print("compare menu")
        _shot_mode_menu(
            page, "compare-menu", "single_compare_toggle", "split_mode_compare_popover"
        )
    if wanted("designs"):
        print("design presets, my designs and palette")
        _shot_designs(page)

    for name, layer, menu in CONTROL_MENUS:
        if not wanted(name):
            continue
        print(name)
        if layer:
            _switch_on(page, layer)
        page.locator(f".st-key-{menu} button").first.click()
        ui.settle(page, quiet=1.5)
        body = page.locator('[data-testid="stPopoverBody"]').last
        # The whole menu, not the part its scroll area shows.
        body.evaluate(
            "el => { el.style.maxHeight = 'none'; el.style.overflow = 'visible';"
            " el.querySelectorAll('*').forEach(c => { if (c.scrollHeight > c.clientHeight)"
            " { c.style.maxHeight = 'none'; c.style.overflow = 'visible'; } }); }"
        )
        page.wait_for_timeout(400)
        _shot_controls(page, name, body)
        page.keyboard.press("Escape")
        ui.settle(page, quiet=1.0)

    if wanted("reset"):
        print("reset visualization")
        _shot_reset(page)

    if wanted("chips"):
        print("chips menu")
        _shot_chips_menu(page)

    if wanted("under-the-plot"):
        print("tabs under the plot")
        _shot_controls(
            page, "under-the-plot", page.locator(".st-key-tour_grp_subtabs").first
        )

    if wanted("compare-row"):
        print("compare")
        ui.toggle(page, "single_compare_toggle")
        _shot_compare_bar(page)
        ui.toggle(page, "single_compare_toggle")

    if wanted("trial-row"):
        print("trial row")
        _shot_trial_row(page)
    ui.OUT = OUT


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    port = free_port()
    ui.URL = f"http://127.0.0.1:{port}"
    ui.OUT = OUT
    app = start_app(port)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=find_chrome())
            # --controls: a window tall enough that every menu opens whole,
            # instead of scrolling inside a box the window's height limits.
            viewport = (
                {**VIEWPORT, "height": 3000} if "--controls" in sys.argv else VIEWPORT
            )
            ctx = browser.new_context(
                viewport=viewport, device_scale_factor=2, color_scheme="light"
            )
            ctx.add_init_script(
                "document.addEventListener('DOMContentLoaded', () => {"
                "const s = document.createElement('style');"
                f"s.textContent = {ui.HIDE_CSS!r};"
                "document.head.appendChild(s);});"
            )
            if "--overview" in sys.argv:
                capture_overview(ctx.new_page())
            elif "--controls" in sys.argv:
                names = sys.argv[sys.argv.index("--controls") + 1 :]
                capture_controls(ctx.new_page(), set(names) or None)
            else:
                capture(ctx.new_page())
            browser.close()
    finally:
        app.terminate()
        app.wait(timeout=30)


if __name__ == "__main__":
    main()
