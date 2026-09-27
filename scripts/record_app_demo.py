#!/usr/bin/env python
"""Record the README's opening animation: a short session in the running app.

``make_hero_gif.py`` renders one figure's replay; this captures the application
itself — stepping through trials, switching on the heatmap, replaying a reading,
comparing two readers, and opening Corpus Analysis — so the first thing a README
reader sees is what using the tool looks like. Writes
``docs/assets/app_demo.gif`` for the README and, from the same recording, the
docs home page's ``app_demo.mp4`` and its ``app_demo_poster.webp`` (ENG-78)::

    uv run --with playwright python scripts/record_app_demo.py

Like ``capture_docs_screenshots.py``, it starts its own app on a free port with
the recovery cache off, so the recording starts from the bundled demo at its
defaults rather than from whatever ran last. Set ``DEMO_APP_URL`` to record an
app that is already running instead.

Playwright is not a package dependency; it is pulled in for the run above.
Chrome: ``DEMO_CHROME`` if set, else the one the screenshots use. Everything is
encoded with ``ffmpeg`` (on PATH).
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from capture_docs_screenshots import find_chrome, free_port, start_app
from playwright.sync_api import Locator, Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = os.environ.get("DEMO_APP_URL")
OUT = Path(os.environ.get("DEMO_OUT", ROOT / "docs" / "assets" / "app_demo.gif"))
CHROME = os.environ.get("DEMO_CHROME")

VIEWPORT = {"width": 1440, "height": 900}
#: The README column is ~900 px wide, which a HiDPI screen draws at up to twice
#: that, so 1200 keeps the app's text legible there. From lossless frames the
#: GIF lands near 1.5 MB, well under the 5 MB default cap of camo, the image
#: proxy PyPI shows README images through.
GIF_WIDTH = 1200
GIF_COLORS = 128
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

#: A visible pointer — a headless recording has none, and without one the
#: clicks look like the page changing by itself — drawn by `Pointer`.
CURSOR_JS = """
(() => {
  // A rerun that re-focuses a control scrolls it into view, which in the
  // recording is the page jumping away and back for no visible reason.
  Element.prototype.scrollIntoView = function () {};
  // Init scripts run in every frame, and the figure is an iframe.
  if (window !== window.top) return;
  window.demoCursor = (x, y, pressed) => {
    let c = document.getElementById('demo-cursor');
    if (!c) {
      c = document.createElement('div');
      c.id = 'demo-cursor';
      c.style.cssText = 'position:fixed;width:22px;height:22px;' +
        'margin:-11px 0 0 -11px;border-radius:50%;background:rgba(230,80,60,.35);' +
        'border:2px solid rgba(230,80,60,.9);z-index:2147483647;pointer-events:none;' +
        'transition:transform .12s ease;';
      document.body.appendChild(c);
    }
    c.style.left = x + 'px';
    c.style.top = y + 'px';
    c.style.transform = pressed ? 'scale(.7)' : '';
  };
})();
"""

#: Back to the top of the page, with nothing focused.
TO_TOP_JS = """() => {
  if (document.activeElement) document.activeElement.blur();
  window.scrollTo(0, 0);
  document.querySelectorAll('[data-testid="stMain"], [data-testid="stAppViewContainer"]')
    .forEach(el => (el.scrollTop = 0));
}"""


class Pointer:
    """The mouse, and the pointer drawn where it is.

    The drawn pointer lives in the top document and moves when this says so,
    not on mouse events: over the figure's iframe the page receives none, so an
    event-driven pointer stuck at the iframe's edge while a second copy, drawn
    inside the iframe, followed the mouse.
    """

    def __init__(self, page: Page) -> None:
        self.page = page
        self.x, self.y = -40.0, -40.0

    def _draw(self, pressed: bool = False) -> None:
        self.page.evaluate(
            "([x, y, pressed]) => window.demoCursor?.(x, y, pressed)",
            [self.x, self.y, pressed],
        )

    def move(self, x: float, y: float, steps: int = 1) -> None:
        """Move to ``(x, y)`` in ``steps`` straight-line steps."""
        x0, y0 = self.x, self.y
        for i in range(1, steps + 1):
            self.x = x0 + (x - x0) * i / steps
            self.y = y0 + (y - y0) * i / steps
            self.page.mouse.move(self.x, self.y)
            self._draw()

    def click(self) -> None:
        self._draw(pressed=True)
        self.page.mouse.down()
        self.page.wait_for_timeout(90)
        self.page.mouse.up()
        self._draw()


class Screencast:
    """The page's frames, losslessly, as Chrome paints them.

    Playwright's own video is VP8 encoded in real time, and its noise shimmers
    across the parts of the page that don't change. A GIF stores only the pixels
    that change from one frame to the next, so that shimmer cost as much as the
    content, and more the busier the machine was. These frames are PNG: a region
    that doesn't change stays identical, and costs nothing.
    """

    def __init__(self, page: Page, frames: Path) -> None:
        self.page = page
        self.frames = frames
        self.times: list[float] = []
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._frame)

    def _frame(self, event: dict) -> None:
        self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
        path = self.frames / f"{len(self.times):05d}.png"
        path.write_bytes(base64.b64decode(event["data"]))
        self.times.append(event["metadata"].get("timestamp") or time.time())

    def start(self) -> None:
        self.cdp.send(
            "Page.startScreencast",
            {
                "format": "png",
                "maxWidth": VIEWPORT["width"],
                "maxHeight": VIEWPORT["height"],
            },
        )

    def stop(self) -> Path:
        """Stop, and list the frames with their durations for ffmpeg's concat."""
        end = time.time()
        self.cdp.send("Page.stopScreencast")
        self.page.wait_for_timeout(500)  # frames already on their way
        if not self.times:
            raise RuntimeError("the screencast sent no frames")
        lines = ["ffconcat version 1.0"]
        for i, t in enumerate(self.times):
            until = self.times[i + 1] if i + 1 < len(self.times) else max(end, t + 0.1)
            lines += [f"file {i:05d}.png", f"duration {until - t:.4f}"]
        # The concat demuxer ignores the last entry's duration unless it repeats.
        lines.append(f"file {len(self.times) - 1:05d}.png")
        listing = self.frames / "frames.ffconcat"
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return listing


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


def glide_click(pointer: Pointer, target: Locator, hold: float = 0.0) -> None:
    """Move the pointer to ``target`` the way a hand would, then click it."""
    page = pointer.page
    # Streamlit keeps hidden copies of some controls (a popover's, a rerun's).
    target = target.filter(visible=True).first
    box = target.bounding_box()
    if box is None:
        raise RuntimeError(f"{target} is not on screen")
    pointer.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=18)
    page.wait_for_timeout(250)
    pointer.click()
    page.evaluate(TO_TOP_JS)
    pointer.move(*PARK, steps=10)
    if hold:
        page.wait_for_timeout(int(hold * 1000))


def switch(page: Page, key: str) -> Locator:
    """The toggle rendered under Streamlit key ``key``."""
    return page.locator(f".st-key-{key} label")


def story(pointer: Pointer) -> None:
    """The recorded session, about half a minute of it."""
    page = pointer.page
    page.wait_for_timeout(1200)
    # Step through a few trials.
    for _ in range(2):
        glide_click(pointer, page.locator(".st-key-single_next_trial button"))
        settle(page, quiet=0.8)
        page.wait_for_timeout(700)
    # Where did the reader dwell?
    glide_click(pointer, switch(page, "global_show_heatmap"))
    settle(page, quiet=0.8)
    page.wait_for_timeout(1600)
    glide_click(pointer, switch(page, "global_show_heatmap"))
    settle(page, quiet=0.6)
    # Replay the reading.
    glide_click(pointer, switch(page, "single_animate"))
    settle(page, quiet=0.8)
    pointer.move(*PARK, steps=12)
    page.wait_for_timeout(5500)
    glide_click(pointer, switch(page, "single_animate"))
    settle(page, quiet=0.6)
    # Two readers of the same text.
    glide_click(pointer, switch(page, "single_compare_toggle"))
    settle(page, quiet=0.8)
    page.wait_for_timeout(2200)
    glide_click(pointer, switch(page, "single_compare_toggle"))
    settle(page, quiet=0.6)
    # And the corpus as a whole.
    glide_click(
        pointer,
        page.locator('[data-testid="stTopNavLink"]:has-text("Corpus Analysis")').first,
    )
    settle(page, quiet=1.0)
    close_tour(page)
    pointer.move(*PARK, steps=10)
    page.wait_for_timeout(2500)


def _frames_input(listing: Path) -> list[str]:
    """ffmpeg's input arguments for a `Screencast.stop` frame list."""
    return ["-f", "concat", "-safe", "0", "-i", str(listing)]


def encode_gif(listing: Path, out: Path) -> None:
    """The recorded frames as a palette-optimised GIF."""
    scale = f"setpts=PTS/{GIF_SPEEDUP},fps={GIF_FPS},scale={GIF_WIDTH}:-1:flags=lanczos"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error"]
        + _frames_input(listing)
        + [
            "-filter_complex",
            f"[0:v]{scale},split[a][b];"
            f"[a]palettegen=max_colors={GIF_COLORS}:stats_mode=diff[p];"
            "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
            str(out),
        ],
        check=True,
    )
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)", flush=True)


def encode_mp4(listing: Path, out: Path) -> None:
    """The same frames as `encode_gif`, as H.264 — what the docs page plays."""
    scale = f"setpts=PTS/{GIF_SPEEDUP},fps={GIF_FPS * 2},scale={GIF_WIDTH}:-2"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error"]
        + _frames_input(listing)
        + [
            "-vf",
            scale,
            "-c:v",
            "libx264",
            "-crf",
            "26",
            "-preset",
            "slow",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(out),
        ],
        check=True,
    )
    poster = out.with_name(f"{out.stem}_poster.webp")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-vframes", "1"]
        + ["-c:v", "libwebp", "-quality", "85", str(poster)],
        check=True,
    )
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB) and {poster.name}")


def record(url: str, frames: Path) -> Path:
    """Play `story` against the app at ``url``, into ``frames``; their listing."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME or find_chrome())
        context = browser.new_context(
            viewport=VIEWPORT, device_scale_factor=1, color_scheme="light"
        )
        context.add_init_script(CURSOR_JS)
        page = context.new_page()
        pointer = Pointer(page)
        # The deep link sets the replay to ×3: at real time a few seconds of GIF
        # show a handful of fixations.
        page.goto(f"{url}/?playback_speed=3", wait_until="domcontentloaded")
        settle(page, quiet=3.0)
        page.add_style_tag(content=HIDE_CSS)
        close_tour(page)
        settle(page, quiet=2.0)
        pointer.move(*PARK)
        screencast = Screencast(page, frames)
        screencast.start()
        story(pointer)
        listing = screencast.stop()
        browser.close()
    return listing


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH")
    app = None
    url = URL
    if not url:
        port = free_port()
        app = start_app(port)
        url = f"http://127.0.0.1:{port}"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            listing = record(url, Path(tmp))
            encode_gif(listing, OUT)
            encode_mp4(listing, OUT.with_suffix(".mp4"))
    finally:
        if app is not None:
            app.terminate()
            app.wait(timeout=30)


if __name__ == "__main__":
    main()
