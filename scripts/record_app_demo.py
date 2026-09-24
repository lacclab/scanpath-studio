#!/usr/bin/env python
"""Record the README's opening animation: a short session in the running app.

``make_hero_gif.py`` renders one figure's replay; this captures the application
itself — stepping through trials, switching on the heatmap, replaying a reading,
comparing two readers, and opening Corpus Analysis — so the first thing a README
reader sees is what using the tool looks like. Writes
``docs/assets/app_demo.gif``.

Run the app first, on the bundled demo, with the recovery cache off so the
recording starts from the defaults rather than from whatever ran last::

    SCANPATH_STUDIO_PERSIST=0 uv run streamlit run streamlit_app.py \\
        --server.address 127.0.0.1 --server.port 8611

then::

    uv run --with playwright python scripts/record_app_demo.py

Playwright is not a package dependency; it is pulled in for the run above. Its
Chromium comes from ``playwright install chromium``; set ``DEMO_CHROME`` to use
another Chrome/Chromium binary. The GIF is encoded with ``ffmpeg`` (on PATH).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

URL = os.environ.get("DEMO_APP_URL", "http://127.0.0.1:8611")
OUT = Path(os.environ.get("DEMO_OUT", "docs/assets/app_demo.gif"))
CHROME = os.environ.get("DEMO_CHROME")

VIEWPORT = {"width": 1440, "height": 900}
#: README width is ~900 px; a little over keeps the text legible on HiDPI.
GIF_WIDTH = 1000
GIF_FPS = 10
#: Played back a little faster than recorded: Streamlit's reruns make the
#: real-time session feel slower than using the app does.
GIF_SPEEDUP = 1.3
#: Where the pointer rests between clicks: off the figure, whose hover labels
#: would otherwise pop up in the recording.
PARK = (1080, 520)

#: Local-dev chrome that has no place in the recording.
HIDE_CSS = """
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"],
[data-testid="stToolbarActions"] { display: none !important; }
"""

#: A visible pointer: a headless recording has none, and without one the
#: clicks look like the page changing by itself.
CURSOR_JS = """
(() => {
  const add = () => {
    if (document.getElementById('demo-cursor')) return;
    const c = document.createElement('div');
    c.id = 'demo-cursor';
    c.style.cssText = 'position:fixed;left:-40px;top:-40px;width:22px;height:22px;' +
      'margin:-11px 0 0 -11px;border-radius:50%;background:rgba(230,80,60,.35);' +
      'border:2px solid rgba(230,80,60,.9);z-index:2147483647;pointer-events:none;' +
      'transition:transform .12s ease;';
    document.body.appendChild(c);
    addEventListener('mousemove', e => {
      c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
    }, true);
    addEventListener('mousedown', () => (c.style.transform = 'scale(.7)'), true);
    addEventListener('mouseup', () => (c.style.transform = ''), true);
  };
  if (document.body) add(); else addEventListener('DOMContentLoaded', add);
  // A rerun that re-focuses a control scrolls it into view, which in the
  // recording is the page jumping away and back for no visible reason.
  Element.prototype.scrollIntoView = function () {};
})();
"""

#: Back to the top of the page, with nothing focused.
TO_TOP_JS = """() => {
  if (document.activeElement) document.activeElement.blur();
  window.scrollTo(0, 0);
  document.querySelectorAll('[data-testid="stMain"], [data-testid="stAppViewContainer"]')
    .forEach(el => (el.scrollTop = 0));
}"""


def settle(page: Page, quiet: float = 1.5, timeout: float = 120) -> None:
    """Block until Streamlit has stopped rerunning for ``quiet`` seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not page.locator('[data-testid="stStatusWidget"]').count():
            page.wait_for_timeout(int(quiet * 1000))
            if not page.locator('[data-testid="stStatusWidget"]').count():
                page.evaluate(TO_TOP_JS)
                return
        page.wait_for_timeout(250)
    print("  ! the app never went idle", flush=True)


def close_tour(page: Page) -> None:
    """Dismiss the welcome tour's spotlight card."""
    for _ in range(3):
        btns = [
            b
            for b in page.locator(".st-key-tour_sp_close button").all()
            + page.locator('.st-key-tour_card button:has-text("Skip")').all()
            if b.is_visible()
        ]
        if not btns:
            return
        btns[0].click()
        settle(page)


def glide_click(page: Page, target: Locator, hold: float = 0.0) -> None:
    """Move the pointer to ``target`` the way a hand would, then click it."""
    # Streamlit keeps hidden copies of some controls (a popover's, a rerun's).
    target = target.filter(visible=True).first
    box = target.bounding_box()
    if box is None:
        raise RuntimeError(f"{target} is not on screen")
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=18)
    page.wait_for_timeout(250)
    page.mouse.down()
    page.wait_for_timeout(90)
    page.mouse.up()
    page.evaluate(TO_TOP_JS)
    page.mouse.move(*PARK, steps=10)
    if hold:
        page.wait_for_timeout(int(hold * 1000))


def switch(page: Page, key: str) -> Locator:
    """The toggle rendered under Streamlit key ``key``."""
    return page.locator(f".st-key-{key} label")


def story(page: Page) -> None:
    """The recorded session, about half a minute of it."""
    page.wait_for_timeout(1200)
    # Step through a few trials.
    for _ in range(2):
        glide_click(page, page.locator(".st-key-single_next_trial button"))
        settle(page, quiet=0.8)
        page.wait_for_timeout(700)
    # Where did the reader dwell?
    glide_click(page, switch(page, "global_show_heatmap"))
    settle(page, quiet=0.8)
    page.wait_for_timeout(1600)
    glide_click(page, switch(page, "global_show_heatmap"))
    settle(page, quiet=0.6)
    # Replay the reading.
    glide_click(page, switch(page, "single_animate"))
    settle(page, quiet=0.8)
    page.mouse.move(*PARK, steps=12)
    page.wait_for_timeout(5500)
    glide_click(page, switch(page, "single_animate"))
    settle(page, quiet=0.6)
    # Two readers of the same text.
    glide_click(page, switch(page, "single_compare_toggle"))
    settle(page, quiet=0.8)
    page.wait_for_timeout(2200)
    glide_click(page, switch(page, "single_compare_toggle"))
    settle(page, quiet=0.6)
    # And the corpus as a whole.
    glide_click(
        page,
        page.locator('[data-testid="stTopNavLink"]:has-text("Corpus Analysis")').first,
    )
    settle(page, quiet=1.0)
    close_tour(page)
    page.mouse.move(*PARK, steps=10)
    page.wait_for_timeout(2500)


def encode_gif(video: Path, start: float, out: Path) -> None:
    """``video`` from ``start`` seconds on, as a palette-optimised GIF."""
    scale = f"setpts=PTS/{GIF_SPEEDUP},fps={GIF_FPS},scale={GIF_WIDTH}:-1:flags=lanczos"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.2f}",
            "-i",
            str(video),
            "-filter_complex",
            f"[0:v]{scale},split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
            "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
            str(out),
        ],
        check=True,
    )
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)", flush=True)


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH")
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        browser = (
            pw.chromium.launch(executable_path=CHROME)
            if CHROME
            else (pw.chromium.launch())
        )
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=1,
            color_scheme="light",
            record_video_dir=tmp,
            record_video_size=VIEWPORT,
        )
        context.add_init_script(CURSOR_JS)
        page = context.new_page()
        opened = time.time()
        # The deep link sets the replay to ×3: at real time a few seconds of GIF
        # show a handful of fixations.
        page.goto(f"{URL}/?playback_speed=3", wait_until="domcontentloaded")
        settle(page, quiet=3.0)
        page.add_style_tag(content=HIDE_CSS)
        close_tour(page)
        settle(page, quiet=2.0)
        page.mouse.move(*PARK)
        start = time.time() - opened
        story(page)
        video = Path(page.video.path())
        context.close()  # finalises the recording
        browser.close()
        encode_gif(video, start, OUT)


if __name__ == "__main__":
    main()
