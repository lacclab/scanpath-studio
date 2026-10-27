#!/usr/bin/env python
"""Record the README's opening animation: a captioned session in the running app.

``make_hero_gif.py`` renders one figure's replay; this captures the application
itself, on the Scanpath page — replaying a reading, the Heatmap preset, building
a figure layer by layer, filtering saccades, redacting the text, comparing two
participants side by side, then Export and Share — between a title card and a
closing card, so the first thing a README reader sees is what using the tool
looks like. Writes
``docs/assets/app_demo.gif`` for the README and, from the same recording, the
docs home page's ``app_demo.mp4`` and its ``app_demo_poster.webp``::

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
from collections.abc import Callable
from pathlib import Path

from capture_docs_screenshots import find_chrome, free_port, start_app
from playwright.sync_api import Locator, Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = os.environ.get("DEMO_APP_URL")
OUT = Path(os.environ.get("DEMO_OUT", ROOT / "docs" / "assets" / "app_demo.gif"))
CHROME = os.environ.get("DEMO_CHROME")

#: Wide enough that the trial picker keeps its slider and its ◀ ▶ buttons on
#: one line (they wrap below 1536 px).
VIEWPORT = {"width": 1600, "height": 1000}
#: The README column is ~900 px wide, which a HiDPI screen draws at up to twice
#: that, so 1280 keeps the app's text legible there. From lossless frames the
#: GIFs land between 1 and 4 MB, under the 5 MB default cap of camo, the image
#: proxy GitHub and PyPI show README images through.
GIF_WIDTH = 1280
GIF_COLORS = 128
GIF_FPS = 10
#: Played back a little faster than recorded: Streamlit's reruns make the
#: real-time session feel slower than using the app does.
GIF_SPEEDUP = 1.3
#: Where the pointer rests between clicks: in the gutter between the figure
#: (which ends near x = 1234 at this width) and the plot controls (x = 1298).
PARK = (1266, 560)
#: This demo's own playback: its session is long, so it plays faster than the
#: workflow demos, and its GIF is a little narrower to stay under camo's 5 MB.
DEMO_SPEEDUP = 1.75
DEMO_GIF_WIDTH = 1120
#: How much faster the waits on a rerun play than the rest (`Session.warp`).
WAIT_SPEEDUP = 12.0
ICON = base64.b64encode((ROOT / "docs" / "assets" / "icon.png").read_bytes()).decode()

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
  // The pointer crosses the figure on its way to a control, and Plotly's
  // hover label and toolbar would pop up there; neither is in the story.
  const quiet = () => {
    const style = document.createElement('style');
    style.textContent = '.hoverlayer, .modebar-container { display: none !important; }';
    (document.head || document.documentElement).appendChild(style);
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', quiet);
  } else quiet();
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

#: The caption pill along the bottom, and the full-screen title / closing card.
OVERLAY_CSS = """
#demo-caption{position:fixed;left:50%;bottom:46px;transform:translate(-50%,24px);
 opacity:0;transition:opacity .35s ease,transform .35s ease;z-index:2147483646;
 background:#0f1219;color:#fff;font:600 30px/1.2 'Source Sans','Source Sans Pro','Segoe UI',sans-serif;
 padding:16px 30px 16px 26px;border-radius:16px;box-shadow:0 10px 34px rgba(0,0,0,.28);
 display:flex;align-items:center;gap:16px;white-space:nowrap;pointer-events:none}
#demo-caption.on{opacity:1;transform:translate(-50%,0)}
#demo-caption .dot{width:16px;height:16px;border-radius:50%;background:#ff7f0e;
 box-shadow:0 0 0 4px rgba(255,127,14,.25)}
#demo-card{position:fixed;inset:0;z-index:2147483647;display:flex;flex-direction:column;
 align-items:center;justify-content:center;gap:22px;background:#0f1219;color:#fff;
 font-family:'Source Sans','Source Sans Pro','Segoe UI',sans-serif;opacity:0;transition:opacity .5s ease;
 pointer-events:none;text-align:center}
#demo-card.on{opacity:1}
#demo-card img{width:150px;height:150px;border-radius:30px}
#demo-card h1{font-size:76px;font-weight:700;margin:0;letter-spacing:-1px}
#demo-card h1 b{color:#ff7f0e}
#demo-card p{font-size:32px;color:#c3cbd9;margin:0}
#demo-card .tags{display:flex;gap:14px;margin-top:10px}
#demo-card .tags span{border:1.5px solid #3a4558;border-radius:999px;padding:8px 20px;
 font-size:22px;color:#dfe5ee}
#demo-card code{font:600 30px 'Consolas','Menlo',monospace;background:#1b2230;color:#5aaee0;
 padding:14px 28px;border-radius:12px;border:1px solid #2c3647}
"""

#: `window.demoCaption(text)` and `window.demoCard(html)`; a falsy argument
#: fades the overlay out. Both live outside Streamlit's root, so reruns keep them.
OVERLAY_JS = """
(() => {
  if (window !== window.top) return;
  const overlay = (id) => {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement('div');
      el.id = id;
      document.body.appendChild(el);
    }
    return el;
  };
  window.demoCaption = (text) => {
    const el = overlay('demo-caption');
    if (!text) return el.classList.remove('on');
    el.innerHTML = '<span class="dot"></span><span>' + text + '</span>';
    requestAnimationFrame(() => el.classList.add('on'));
  };
  window.demoCard = (html) => {
    const el = overlay('demo-card');
    if (!html) return el.classList.remove('on');
    el.innerHTML = html;
    requestAnimationFrame(() => el.classList.add('on'));
  };
})();
"""

#: Ease the main column's scroll to ``y`` over ``ms`` milliseconds.
SCROLL_JS = """async ([y, ms]) => {
  const el = [...document.querySelectorAll(
    '[data-testid="stMain"], [data-testid="stAppViewContainer"]')]
    .find(e => e.scrollHeight > e.clientHeight);
  if (!el) return;
  const y0 = el.scrollTop, t0 = performance.now();
  await new Promise(done => {
    const step = now => {
      const k = Math.min(1, (now - t0) / ms);
      const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      el.scrollTop = y0 + (y - y0) * e;
      k < 1 ? requestAnimationFrame(step) : done();
    };
    requestAnimationFrame(step);
  });
}"""

#: Whether the switch under a key is drawn on. Its input's `checked` can be
#: stale after the app writes the key itself, so this reads the track: opaque
#: blue when on; grey when off, or a faint blue under the pointer.
SWITCH_ON_JS = """(key) => {
  const track = document.querySelector(`.st-key-${key} label > div`);
  const [r, , b, a = 1] = getComputedStyle(track).backgroundColor
    .match(/[\\d.]+/g).map(Number);
  return a > 0.9 && b > r + 60;
}"""

INTRO = f"""
<img src="data:image/png;base64,{ICON}" alt="">
<h1>Scanpath <b>Studio</b></h1>
<p><b style="color:#fff">See how people read.</b> &nbsp;Explore eye movements in reading.</p>
"""

OUTRO = f"""
<img src="data:image/png;base64,{ICON}" alt="" style="width:120px;height:120px">
<h1>Scanpath <b>Studio</b></h1>
<div class="tags"><span>Web app</span><span>Desktop</span><span>Python API</span><span>CLI</span></div>
<code>pip install scanpath-studio</code>
<p style="font-size:26px">Free &amp; open source &nbsp;·&nbsp; lacclab.github.io/scanpath-studio</p>
"""


class Pointer:
    """The mouse, and the pointer drawn where it is.

    The drawn pointer lives in the top document and moves when this says so,
    not on mouse events: over the figure's iframe the page receives none, so an
    event-driven pointer would stick at the iframe's edge while a second copy,
    drawn inside the iframe, followed the mouse.
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
    that change from one frame to the next, so that shimmer would cost as much
    as the content, and more the busier the machine. These frames are PNG: a region
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
        stamp = event["metadata"].get("timestamp") or time.time()
        # Chrome occasionally stamps a frame a few ms before its predecessor,
        # which would be a negative duration in the ffconcat listing.
        self.times.append(max(stamp, self.times[-1]) if self.times else stamp)

    def start(self) -> None:
        size = self.page.viewport_size or VIEWPORT
        self.cdp.send(
            "Page.startScreencast",
            {"format": "png", "maxWidth": size["width"], "maxHeight": size["height"]},
        )

    def stop(self, warp: Callable[[float], float] = lambda t: t) -> Path:
        """Stop, and list the frames with their durations for ffmpeg's concat.

        ``warp`` maps a frame's wall-clock stamp to its time in the output, so a
        recording can play some stretches faster than others
        (``record_workflow_demos.py`` fast-forwards its long waits that way).
        """
        end = time.time()
        self.cdp.send("Page.stopScreencast")
        self.page.wait_for_timeout(500)  # frames already on their way
        if not self.times:
            raise RuntimeError("the screencast sent no frames")
        lines = ["ffconcat version 1.0"]
        for i, t in enumerate(self.times):
            until = self.times[i + 1] if i + 1 < len(self.times) else max(end, t + 0.1)
            lines += [f"file {i:05d}.png", f"duration {warp(until) - warp(t):.4f}"]
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


def switch(page: Page, key: str) -> Locator:
    """The toggle rendered under Streamlit key ``key``."""
    return page.locator(f".st-key-{key} label")


class Session:
    """The recording's pointer, plus the stretches spent waiting on a rerun.

    Those waits are fast-forwarded in the output (`warp`): a rerun reads as the
    app thinking, not as the feature being shown.
    """

    def __init__(self, pointer: Pointer) -> None:
        self.pointer = pointer
        self.page = pointer.page
        self.busy: list[tuple[float, float]] = []

    def idle(self, quiet: float = 0.5, timeout: float = 120) -> None:
        """Wait for Streamlit to go quiet, leaving the scroll position alone."""
        status = self.page.locator('[data-testid="stStatusWidget"]')
        t0 = time.time()
        deadline = t0 + timeout
        while time.time() < deadline:
            if not status.count():
                self.wait(int(quiet * 1000))
                if not status.count():
                    break
            self.wait(200)
        # The final `quiet` stretch plays at speed: it is the result on screen.
        t1 = time.time() - quiet
        if t1 - t0 > 0.3:
            self.busy.append((t0, t1))

    def warp(self, t: float) -> float:
        """A frame's wall-clock time ``t`` in the output, waits fast-forwarded."""
        cut = sum(max(0.0, min(t, b) - a) for a, b in self.busy)
        return t - cut * (1 - 1 / WAIT_SPEEDUP)

    def wait(self, ms: int) -> None:
        self.page.wait_for_timeout(ms)

    def park(self) -> None:
        self.pointer.move(*PARK, steps=8)

    def glide(self, target: Locator, click: bool = True) -> None:
        """Move the pointer to ``target`` the way a hand would, and click it."""
        # Streamlit keeps hidden copies of some controls (a popover's, a rerun's).
        target = target.filter(visible=True).first
        target.wait_for(state="visible", timeout=90_000)
        box = target.bounding_box()
        if box is None:
            raise RuntimeError(f"{target} is not on screen")
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.pointer.move(x, y, steps=11)
        self.wait(200)
        if click:
            self.pointer.click()

    def toggle(self, key: str, on: bool) -> None:
        """Set the rail switch ``key`` to ``on``, again if a rerun moved it."""
        for _ in range(4):
            self.idle(quiet=0.4)
            if self.page.evaluate(SWITCH_ON_JS, key) == on:
                return
            self.glide(switch(self.page, key))
            self.wait(500)
        self.idle()

    def popover(self, key: str) -> Locator:
        """Open the rail popover ``key``; its body."""
        self.glide(self.page.locator(f".st-key-{key} button"))
        self.wait(700)
        return self.page.locator('[data-testid="stPopoverBody"]').filter(visible=True)

    def close_popover(self) -> None:
        self.page.keyboard.press("Escape")
        self.park()
        self.idle()

    def pick(self, key: str, option: str, nth: int = 0) -> None:
        """In the rail popover ``key``, pick ``option`` in its ``nth`` selectbox."""
        body = self.popover(key)
        self.glide(body.locator("[role=combobox]").nth(nth))
        self.wait(400)
        self.glide(self.page.locator("[role=option]", has_text=option))
        self.idle()
        self.wait(900)
        self.close_popover()

    def tab(self, name: str) -> None:
        """Open the subtab ``name``, again if a late rerun moved it."""
        tab = self.page.get_by_role("tab", name=name, exact=True)
        for _ in range(4):
            self.glide(tab)
            self.wait(400)
            if tab.filter(visible=True).first.get_attribute("aria-selected") == "true":
                break
            self.idle()
        self.idle()

    def caption(self, text: str | None) -> None:
        self.page.evaluate("(t) => window.demoCaption(t)", text)

    def card(self, html: str | None) -> None:
        self.page.evaluate("(h) => window.demoCard(h)", html)

    def scroll(self, y: int, ms: int = 900) -> None:
        self.page.evaluate(SCROLL_JS, [y, ms])


def story(s: Session) -> None:
    """The recorded session: the Scanpath page, scene by scene."""
    page = s.page
    s.wait(1700)
    s.card(None)
    s.wait(400)

    s.caption("Replay the reading, fixation by fixation")
    s.toggle("single_animate", True)
    s.park()
    s.idle()
    s.wait(5200)
    s.toggle("single_animate", False)

    s.caption("See where participants dwell")
    s.glide(page.locator(".st-key-viz_view_heatmap button"))
    s.park()
    s.idle()
    s.wait(1800)

    s.caption("Build your figure layer by layer")
    # A popover setting comes first: the first layer switch flipped right
    # after a preset is put back, while one after any other change holds.
    s.pick("split_mode_rail_heatmap_popover", "Oranges", nth=2)
    s.wait(600)
    s.toggle("global_show_fix", True)
    s.pick("split_mode_rail_fix_popover", "Duration (ms)")
    s.toggle("global_show_saccades", True)
    arrows = s.popover("split_mode_rail_sac_popover").locator("label", has_text="Show")
    s.glide(arrows)
    s.idle()
    s.wait(900)
    s.close_popover()
    s.toggle("global_show_words", True)
    s.wait(500)
    s.toggle("global_show_heatmap", False)
    s.park()
    s.idle()
    s.wait(1200)

    s.caption("Filter saccades by type")
    body = s.popover("split_mode_rail_filter_popover")
    s.glide(body.locator('button[aria-label="Remove Forward"]'))
    s.idle()
    s.close_popover()
    s.wait(1900)

    s.caption("Redact the text in one click")
    for hold in (1900, 0):
        body = s.popover("split_mode_rail_stim_popover")
        s.glide(body.locator("label", has_text="Redact"))
        s.idle()
        s.close_popover()
        s.wait(hold)

    s.caption("Compare two participants, side by side")
    s.toggle("single_compare_toggle", True)
    body = s.popover("split_mode_compare_popover")
    s.glide(body.locator("button, label", has_text="Side by side"))
    s.idle()
    s.close_popover()
    s.wait(2600)
    s.toggle("single_compare_toggle", False)

    s.caption("Publication-ready export")
    s.idle(quiet=1.0)
    s.tab("Export")
    s.scroll(700, 1100)
    s.wait(400)
    for fmt in ("SVG", "PDF"):
        s.glide(page.locator('[data-testid="stRadio"] label', has_text=fmt))
        s.idle()
        s.wait(400)
    s.glide(page.locator('[data-testid="stDownloadButton"] button'), click=False)
    s.wait(700)
    s.scroll(1150, 1400)
    s.wait(1500)

    s.caption("Share a link — or the code that redraws it")
    s.scroll(360, 800)
    s.tab("Share")
    s.scroll(700, 900)
    s.wait(1000)
    code_tab = page.locator("button, [role=tab], label", has_text="Code")
    s.glide(code_tab.filter(visible=True).last)
    snippet = page.locator("code", has_text="plot_scanpath").filter(visible=True)
    snippet.first.wait_for(timeout=90_000)
    s.idle()
    s.scroll(1000, 900)
    s.wait(2600)

    s.caption(None)
    s.pointer.move(-40, -40)
    s.card(OUTRO)
    s.wait(3600)


def _frames_input(listing: Path) -> list[str]:
    """ffmpeg's input arguments for a `Screencast.stop` frame list."""
    return ["-f", "concat", "-safe", "0", "-i", str(listing)]


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def encode_gif(
    listing: Path,
    out: Path,
    *,
    width: int = GIF_WIDTH,
    speedup: float = GIF_SPEEDUP,
    colors: int = GIF_COLORS,
) -> None:
    """The recorded frames as a palette-optimised GIF.

    The frames are first resampled to a fixed rate on disk. With palettegen and
    paletteuse in one graph over the concat input, ffmpeg can drop every frame
    queued before the palette is ready, leaving only the last few seconds.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frames = Path(tmp) / "%05d.png"
        palette = Path(tmp) / "palette.png"
        scale = f"setpts=PTS/{speedup},fps={GIF_FPS},scale={width}:-1:flags=lanczos"
        _ffmpeg(*_frames_input(listing), "-vf", scale, str(frames))
        fixed = ["-framerate", str(GIF_FPS), "-i", str(frames)]
        _ffmpeg(
            *fixed,
            "-vf",
            f"palettegen=max_colors={colors}:stats_mode=diff",
            str(palette),
        )
        _ffmpeg(
            *fixed,
            "-i",
            str(palette),
            "-lavfi",
            "[0:v][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
            "-loop",
            "0",
            str(out),
        )
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)", flush=True)


def encode_mp4(
    listing: Path, out: Path, *, width: int = GIF_WIDTH, speedup: float = GIF_SPEEDUP
) -> None:
    """The same frames as `encode_gif`, as H.264 — what the docs page plays."""
    scale = f"setpts=PTS/{speedup},fps={GIF_FPS * 2},scale={width}:-2"
    _ffmpeg(
        *_frames_input(listing),
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
    )
    poster = out.with_name(f"{out.stem}_poster.webp")
    _ffmpeg(
        "-i",
        str(out),
        "-vframes",
        "1",
        "-c:v",
        "libwebp",
        "-quality",
        "85",
        str(poster),
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
        context.add_init_script(OVERLAY_JS)
        page = context.new_page()
        session = Session(Pointer(page))
        # The deep link sets the replay to ×3: at real time a few seconds of GIF
        # show a handful of fixations.
        page.goto(f"{url}/?playback_speed=3&ui=full", wait_until="domcontentloaded")
        settle(page, quiet=3.0)
        page.add_style_tag(content=HIDE_CSS + OVERLAY_CSS)
        close_tour(page)
        settle(page, quiet=2.0)
        session.card(INTRO)
        page.wait_for_timeout(800)
        screencast = Screencast(page, frames)
        screencast.start()
        story(session)
        listing = screencast.stop(session.warp)
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
            encode_gif(listing, OUT, width=DEMO_GIF_WIDTH, speedup=DEMO_SPEEDUP)
            encode_mp4(listing, OUT.with_suffix(".mp4"), speedup=DEMO_SPEEDUP)
    finally:
        if app is not None:
            app.terminate()
            app.wait(timeout=30)


if __name__ == "__main__":
    main()
