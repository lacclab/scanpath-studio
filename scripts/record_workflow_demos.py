#!/usr/bin/env python
"""Record one short GIF per workflow in the running app, with the clicks counted.

``record_app_demo.py`` records the README's tour of the whole app. This records
the workflows one at a time — exporting a figure, adding your own data, styling
the plot, filtering trials, comparing readers — each as its own clip, for the
README's *See it in action* and the docs Gallery's *The app at work*. A bar in
the app's header counts the clicks as they happen and names each step, a ripple
marks every click, and the last frame says how many it took::

    uv run --with playwright python scripts/record_workflow_demos.py           # all
    uv run --with playwright python scripts/record_workflow_demos.py compare   # one
    uv run --with playwright python scripts/record_workflow_demos.py --list

Each workflow is written twice from one recording: a GIF to ``assets/workflows/``
for the README, and an MP4 with its poster to ``docs/assets/workflows/`` for the
Gallery, which plays video at a fraction of a GIF's size (``DEMO_OUT`` writes
both to one folder instead). It starts
its own app on a free port, so every workflow starts from the bundled demo at
its defaults; set ``DEMO_APP_URL`` to record an app that is already running
instead. Each workflow gets a fresh browser context, so nothing one does
carries into the next. The browser is a returning user's — it has opted out of
the welcome tour and the setup guide, as the guides' own *Don't show this again*
does — and the app saves, as a local install does, into a scratch folder emptied
before each workflow (without it, an upload brings up the hosted demo's
"nothing is saved here" reminder).

The recording is real time, sped up by the same ``GIF_SPEEDUP`` as the app demo.
A wait for the app's own work — building a zip of 24 trials, rendering a replay —
is fast-forwarded, and the bar says so while it is (``⏩ ×4``).
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import shutil
import socket
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from capture_docs_screenshots import find_chrome, free_port, start_app
from playwright.sync_api import Frame, Locator, Page, sync_playwright
from record_app_demo import (
    CHROME,
    HIDE_CSS,
    Pointer,
    Screencast,
    encode_gif,
    encode_mp4,
)

ROOT = Path(__file__).resolve().parent.parent
URL = os.environ.get("DEMO_APP_URL")
#: The README's GIFs, and the Gallery's MP4s (beside the docs' other assets).
OUT = Path(os.environ.get("DEMO_OUT", ROOT / "assets" / "workflows"))
VIDEO_OUT = Path(os.environ.get("DEMO_OUT", ROOT / "docs" / "assets" / "workflows"))
SAMPLE = ROOT / "scanpath_studio" / "sample_data"

#: Taller than the app demo's 1440×900: under the figure, a subtab and the trial
#: picker above it then fit on one screen, so a workflow needn't scroll between them.
VIEWPORT = {"width": 1440, "height": 960}
#: Where the pointer rests between clicks: in the gutter between the figure and
#: the plot controls, where it sets off no hover label.
PARK = (1105, 520)
#: The app's header: a target under it is scrolled into view before a click.
HEADER = 70
#: The orange the docs' screenshot callouts use, so the two read as one set.
ACCENT = "#d55e00"
#: What *Don't show this again* writes (``tour.TOUR_OPTOUT_COOKIE`` and
#: ``tour.WIZARD_GUIDE_OPTOUT_COOKIE``): a returning user's browser.
OPT_OUT_COOKIES = ("sps_tour_optout", "sps_wizard_guide_optout")
#: Room below the content, so a short subtab can sit under the header too.
PAD_CSS = '[data-testid="stMainBlockContainer"] { min-height: 2400px !important; }'

#: Everything drawn over the page: the pointer, the ripple a click leaves, the
#: bar that counts the clicks, the fast-forward note, a download's "saved" chip,
#: and the closing card. It all lives in the top document and is redrawn from
#: Python on every change, so a page load (the Share link) loses nothing.
OVERLAY_JS = f"""
(() => {{
  // A rerun that re-focuses a control scrolls it into view, which in the
  // recording is the page jumping away and back for no visible reason.
  Element.prototype.scrollIntoView = function () {{}};
  // The pointer crosses a figure on its way to a control, and Plotly's hover
  // label would pop up there and linger; none of these tasks is about one.
  const noHover = () => {{
    const style = document.createElement('style');
    style.textContent = '.hoverlayer {{ display: none !important; }}';
    (document.head || document.documentElement).appendChild(style);
  }};
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', noHover);
  }} else noHover();
  // Init scripts run in every frame, and the figure is an iframe.
  if (window !== window.top) return;
  const FONT = '"Source Sans 3","Source Sans Pro",system-ui,-apple-system,sans-serif';
  const MOUSE = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" ' +
    'stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px">' +
    '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 7v4"/></svg>';
  const SAVE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" ' +
    'stroke="{ACCENT}" stroke-width="2.4" stroke-linecap="round" ' +
    'stroke-linejoin="round" style="vertical-align:-3px;margin-right:8px">' +
    '<path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M5 20h14"/></svg>';
  const node = (id, css) => {{
    let e = document.getElementById(id);
    if (!e) {{
      e = document.createElement('div');
      e.id = id;
      e.style.cssText = css;
      document.body.appendChild(e);
    }}
    return e;
  }};
  const text = (tag, css, value) => {{
    const e = document.createElement(tag);
    e.style.cssText = css;
    e.textContent = value;
    return e;
  }};
  window.demoCursor = (x, y, pressed) => {{
    const c = node('demo-cursor',
      'position:fixed;width:22px;height:22px;margin:-11px 0 0 -11px;' +
      'border-radius:50%;background:rgba(230,80,60,.35);' +
      'border:2px solid rgba(230,80,60,.9);z-index:2147483647;' +
      'pointer-events:none;transition:transform .12s ease;');
    c.style.left = x + 'px';
    c.style.top = y + 'px';
    c.style.transform = pressed ? 'scale(.7)' : '';
  }};
  window.demoRipple = (x, y) => {{
    const r = document.createElement('div');
    r.style.cssText = `position:fixed;left:${{x}}px;top:${{y}}px;width:18px;` +
      'height:18px;margin:-9px 0 0 -9px;border-radius:50%;' +
      'border:3px solid {ACCENT};z-index:2147483646;pointer-events:none;';
    document.body.appendChild(r);
    r.animate(
      [{{transform: 'scale(1)', opacity: 1}}, {{transform: 'scale(4)', opacity: 0}}],
      {{duration: 650, easing: 'ease-out'}},
    ).onfinish = () => r.remove();
  }};
  window.demoHud = (n, caption, fast, where) => {{
    const h = node('demo-hud',
      'position:fixed;right:22px;z-index:2147483647;pointer-events:none;' +
      'display:flex;align-items:center;gap:12px;max-width:800px;' +
      'padding:6px 18px 6px 6px;border-radius:999px;' +
      'background:rgba(17,24,39,.94);color:#fff;' +
      `font:600 18px/1.3 ${{FONT}};box-shadow:0 4px 14px rgba(0,0,0,.25);`);
    h.style.top = where === 'bottom' ? '' : '11px';
    h.style.bottom = where === 'bottom' ? '20px' : '';
    const before = h.dataset.n;
    h.dataset.n = String(n);
    h.replaceChildren();
    const badge = document.createElement('span');
    badge.style.cssText = 'background:{ACCENT};border-radius:999px;' +
      'padding:4px 14px;white-space:nowrap;font-weight:700;display:inline-block;';
    badge.innerHTML = MOUSE;
    badge.append(`${{n}} click${{n === 1 ? '' : 's'}}`);
    h.append(badge);
    h.append(text('span',
      'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;', caption));
    if (fast) h.append(text('span',
      'white-space:nowrap;color:#fbbf24;font-weight:700;', fast));
    if (before !== undefined && before !== String(n)) {{
      badge.animate(
        [{{transform: 'scale(1.3)'}}, {{transform: 'scale(1)'}}],
        {{duration: 350, easing: 'ease-out'}},
      );
    }}
  }};
  window.demoToast = (label) => {{
    const t = node('demo-toast',
      'position:fixed;right:22px;bottom:22px;z-index:2147483647;' +
      'pointer-events:none;padding:12px 20px;border-radius:12px;' +
      'background:#fff;color:#111827;border:1px solid #e5e7eb;' +
      `font:600 17px/1.3 ${{FONT}};box-shadow:0 6px 20px rgba(0,0,0,.18);`);
    t.innerHTML = SAVE;
    t.append(label);
    t.animate([{{opacity: 0, transform: 'translateY(12px)'}}, {{opacity: 1}}],
      {{duration: 300, easing: 'ease-out'}});
  }};
  window.demoEnd = (n, title) => {{
    document.getElementById('demo-toast')?.remove();
    const o = node('demo-end',
      'position:fixed;inset:0;z-index:2147483646;display:flex;' +
      'align-items:center;justify-content:center;pointer-events:none;' +
      'background:rgba(255,255,255,.6);');
    o.replaceChildren();
    const card = document.createElement('div');
    card.style.cssText = 'background:#fff;border-radius:20px;padding:30px 52px;' +
      'text-align:center;box-shadow:0 12px 40px rgba(0,0,0,.22);' +
      `font-family:${{FONT}};color:#111827;`;
    card.append(text('div', 'font-size:60px;font-weight:700;line-height:1.1;color:{ACCENT};',
      `${{n}} click${{n === 1 ? '' : 's'}}`));
    card.append(text('div', 'font-size:26px;font-weight:600;line-height:1.3;margin-top:10px;', title));
    o.append(card);
    o.animate([{{opacity: 0}}, {{opacity: 1}}], {{duration: 350, easing: 'ease-out'}});
  }};
}})();
"""

#: The page scrolls inside Streamlit's main container, not the window.
#: Smooth scrolling, as a wheel would do it: ``SCROLL_JS`` moves the page (which
#: scrolls inside Streamlit's main container, not the window) by ``dy``;
#: ``REVEAL_JS`` scrolls whichever container clips an element — the page, or a
#: popover whose rows run past its bottom — just far enough to show it.
_GLIDE = """
  const glide = (box, dy, ms) => new Promise(done => {
    const y0 = box.scrollTop, t0 = performance.now();
    const step = now => {
      const k = Math.min(1, (now - t0) / ms);
      const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      box.scrollTop = y0 + dy * e;
      k < 1 ? requestAnimationFrame(step) : done();
    };
    requestAnimationFrame(step);
  });
"""
SCROLL_JS = f"""([dy, ms]) => {{{_GLIDE}
  return glide(document.querySelector('[data-testid="stMain"]'), dy, ms);
}}"""
REVEAL_JS = f"""([el, header]) => {{{_GLIDE}
  let box = el.parentElement;
  while (box && !(/(auto|scroll)/.test(getComputedStyle(box).overflowY)
                  && box.scrollHeight > box.clientHeight + 2)) box = box.parentElement;
  if (!box) return;
  const main = box.matches('[data-testid="stMain"]');
  const r = el.getBoundingClientRect(), b = box.getBoundingClientRect();
  const top = Math.max(b.top + 8, header), bottom = Math.min(b.bottom, innerHeight) - 30;
  let dy = 0;
  if (r.top < top) dy = r.top - top - 40;
  else if (r.bottom > bottom) dy = r.bottom - bottom + (main ? 110 : 20);
  if (dy) return glide(box, dy, main ? 700 : 450);
}}"""


class Warp:
    """Wall-clock stretches to play faster, and the time map that does it."""

    def __init__(self) -> None:
        self.spans: list[tuple[float, float, float]] = []

    def __call__(self, t: float) -> float:
        out = t
        for start, end, factor in self.spans:
            inside = max(0.0, min(t, end) - start)
            out -= inside * (1 - 1 / factor)
        return out


@dataclass
class Workflow:
    name: str
    #: What the bar says before the first click — the task, in a user's words.
    goal: str
    run: Callable[[Demo], None]


WORKFLOWS: dict[str, Workflow] = {}


def workflow(name: str, goal: str) -> Callable[[Callable[[Demo], None]], None]:
    def register(fn: Callable[[Demo], None]) -> None:
        WORKFLOWS[name] = Workflow(name, goal, fn)

    return register


class Demo:
    """One recording: the page, the pointer, and the bar counting the clicks."""

    def __init__(self, page: Page, goal: str) -> None:
        self.page = page
        self.pointer = Pointer(page)
        self.warp = Warp()
        self.goal = goal
        self.clicks = 0
        self.steps: list[str] = []
        self.fast_label = ""
        self.where = "top"

    # -- the overlay ---------------------------------------------------------

    def hud(self) -> None:
        caption = self.goal
        if self.steps:
            shown = self.steps[-4:]
            caption = (
                (" → ".join(shown))
                if len(shown) == len(self.steps)
                else "… → " + " → ".join(shown)
            )
        self.page.evaluate(
            "([n, c, f, w]) => window.demoHud?.(n, c, f, w)",
            [self.clicks, caption, self.fast_label, self.where],
        )

    def step(self, label: str) -> None:
        """Add ``label`` to the bar's breadcrumb without a click."""
        self.steps.append(label)
        self.hud()

    def bar_at(self, where: str) -> None:
        """Move the bar to the ``top`` (the header) or the ``bottom``."""
        self.where = where
        self.hud()

    def toast(self, label: str) -> None:
        self.page.evaluate("(t) => window.demoToast?.(t)", label)

    @contextlib.contextmanager
    def fast(self, factor: float = 4) -> Iterator[None]:
        """Play what happens inside the block ``factor`` times faster."""
        self.fast_label = f"⏩ ×{factor:g}"
        self.hud()
        start = time.time()
        try:
            yield
        finally:
            self.warp.spans.append((start, time.time(), factor))
            self.fast_label = ""
            self.hud()

    def finish(self, title: str, hold: float = 2.6) -> None:
        self.pointer.move(*PARK, steps=10)
        self.page.evaluate("([n, t]) => window.demoEnd?.(n, t)", [self.clicks, title])
        self.page.wait_for_timeout(int(hold * 1000))

    # -- waiting -------------------------------------------------------------

    def settle(self, quiet: float = 0.7, timeout: float = 240) -> None:
        """Block until Streamlit has stopped rerunning for ``quiet`` seconds."""
        status = self.page.locator('[data-testid="stStatusWidget"]')
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not status.count():
                self.page.wait_for_timeout(int(quiet * 1000))
                if not status.count():
                    return
            self.page.wait_for_timeout(200)
        print("  ! the app never went idle", flush=True)

    def pause(self, seconds: float) -> None:
        self.page.wait_for_timeout(int(seconds * 1000))

    # -- moving around -------------------------------------------------------

    def scroll(self, dy: float, ms: int = 700) -> None:
        """Scroll the page by ``dy`` pixels, the way a wheel would."""
        self.page.evaluate(SCROLL_JS, [dy, ms])
        self.page.wait_for_timeout(150)

    def scroll_to(self, target: Locator, top: float = 110) -> None:
        """Scroll until ``target`` sits ``top`` pixels below the window's top."""
        box = self._box(target)
        self.scroll(box["y"] - top)

    def _visible(self, target: Locator) -> Locator:
        # Streamlit keeps hidden copies of some controls (a popover's, a rerun's).
        return target.filter(visible=True).first

    def _box(self, target: Locator) -> dict:
        target = self._visible(target)
        target.wait_for(state="visible", timeout=60_000)
        box = target.bounding_box()
        if box is None:
            raise RuntimeError(f"{target} is not on screen")
        return box

    def _bring_into_view(self, target: Locator) -> dict:
        self._box(target)  # waits for it
        self.page.evaluate(REVEAL_JS, [self._visible(target).element_handle(), HEADER])
        self.page.wait_for_timeout(150)
        return self._box(target)

    def point_at(self, target: Locator, steps: int = 18) -> None:
        box = self._bring_into_view(target)
        self.pointer.move(
            box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps
        )

    def park(self) -> None:
        self.pointer.move(*PARK, steps=10)

    # -- acting --------------------------------------------------------------

    def click(
        self,
        target: Locator,
        step: str | None = None,
        *,
        hold: float = 0.5,
        wait: bool = True,
        park: bool = True,
        blur: bool = True,
    ) -> None:
        """Glide to ``target``, click it, count it, and name the step."""
        self.point_at(target)
        self.page.wait_for_timeout(200)
        self.page.evaluate(
            "([x, y]) => window.demoRipple?.(x, y)", [self.pointer.x, self.pointer.y]
        )
        self.pointer.click()
        self.clicks += 1
        if step:
            self.steps.append(step)
        self.hud()
        if blur:  # else the focus ring stays on the control until the next click
            self.page.evaluate("() => document.activeElement?.blur?.()")
        if park:
            self.park()
        if wait:
            self.settle()
        if hold:
            self.pause(hold)

    def open(self, target: Locator) -> None:
        """Click a control that opens a list, and leave it open (one click)."""
        self.click(target, wait=False, hold=0.35, park=False, blur=False)

    def choose(
        self, key: str, option: str, step: str | None = None, *, hold: float = 0.6
    ) -> None:
        """Pick ``option`` in the selectbox keyed ``key``: two clicks."""
        self.open(self.page.locator(f".st-key-{key} [role=group]"))
        self.click(_option(self.page, option), step or option, hold=hold)

    def pad_page(self) -> None:
        """Let the page scroll a short subtab up under the header."""
        self.page.add_style_tag(content=PAD_CSS)

    def type_into(self, target: Locator, text: str, step: str | None = None) -> None:
        """Click a text field, replace what it holds with ``text``, and commit it."""
        self.click(target, wait=False, hold=0.2, park=False, blur=False)
        self.page.keyboard.press("ControlOrMeta+a")
        self.page.keyboard.type(text, delay=55)
        self.page.keyboard.press("Enter")
        if step:
            self.steps.append(step)
            self.hud()
        self.park()
        self.settle()

    def download(self, target: Locator, step: str) -> str:
        """Click a download button and show the file it saved; its name."""
        with self.page.expect_download(timeout=240_000) as info:
            self.click(target, step, wait=False, hold=0)
        download = info.value
        name = download.suggested_filename
        size = Path(download.path()).stat().st_size
        self.toast(f"Saved {name}  ·  {_size(size)}")
        self.settle()
        return name

    def upload(self, target: Locator, path: Path, step: str) -> None:
        """Click an upload button and pick ``path`` in the file chooser."""
        with self.page.expect_file_chooser() as chooser:
            self.click(target, step, wait=False, hold=0)
        chooser.value.set_files(str(path))
        self.settle(quiet=1.0)

    def drag_slider(self, key: str, fraction: float, step: str) -> None:
        """Drag the slider keyed ``key`` to ``fraction`` of its track (one click)."""
        slider = self.page.locator(f".st-key-{key} [data-testid=stSlider]")
        # The thumb is a div around the slider's (visually hidden) range input.
        thumb = slider.locator("div:has(> input[type=range])")
        track = self._box(slider.locator("[data-orientation=horizontal]").last)
        self.point_at(thumb)
        self.page.wait_for_timeout(200)
        self.page.evaluate(
            "([x, y]) => window.demoRipple?.(x, y)", [self.pointer.x, self.pointer.y]
        )
        self.page.mouse.down()
        self.pointer.move(track["x"] + track["width"] * fraction, self.pointer.y, 14)
        self.page.mouse.up()
        self.clicks += 1
        self.step(step)

    def close_popover(self) -> None:
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(350)


def _size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1000 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in {"B", "KB"} else f"{n:.1f} {unit}"
        n /= 1000
    return ""


def _option(page: Page, label: str) -> Locator:
    """The open list's option reading exactly ``label`` ("Select all" has "ele")."""
    exact = re.compile(rf"^\s*{re.escape(label)}\s*$")
    return page.locator("[role=option]").filter(has_text=exact)


def _trial_count(page: Page) -> int:
    """How many trials the picker steps through (its ``n/N`` label)."""
    label = page.locator(".st-key-single_trial_pos").filter(visible=True).first
    found = re.search(r"\d+\s*/\s*(\d+)", label.inner_text())
    return int(found.group(1)) if found else 0


def _frame_with(page: Page, selector: str) -> Frame:
    """The frame (the page, or one of its iframes) that holds ``selector``."""
    for frame in page.frames:
        if frame.locator(selector).count():
            return frame
    raise RuntimeError(f"no frame holds {selector}")


#: The share link as the Share widget shows it.
_SHARE_URL_JS = """() => [...document.querySelectorAll('input, textarea, code, div, span')]
  .map(e => (e.value || e.textContent || '').trim())
  .find(v => /^https?:\\/\\/\\S+\\?\\S+$/.test(v))"""


def _tab(page: Page, label: str) -> Locator:
    return page.locator('[data-testid="stTab"]').filter(has_text=label)


def _toggle(page: Page, key: str) -> Locator:
    return page.locator(f".st-key-{key} label")


def _button(page: Page, label: str) -> Locator:
    return page.locator("button").filter(has_text=label)


def _nav(page: Page, label: str) -> Locator:
    return page.locator('[data-testid="stTopNavLink"]').filter(has_text=label)


# -- the workflows -------------------------------------------------------------


@workflow("export-figure", "Export this figure for a paper")
def export_figure(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    d.click(_tab(page, "Export"), "Export")
    d.scroll_to(page.locator(".st-key-tutorial_export"), top=150)
    d.type_into(
        page.locator(".st-key-export_figure_width input"), "180", "180 mm at 300 dpi"
    )
    d.pause(0.6)
    d.download(_button(page, "Download PNG"), "Download")
    d.pause(1.6)
    d.finish("A 180 mm, 300 dpi figure, ready for the paper")


@workflow("export-bundle", "Export every trial at once")
def export_bundle(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    d.click(_tab(page, "Export"), "Export")
    d.scroll_to(
        page.locator('h2:has-text("Export bundle"), h1:has-text("Export bundle")'),
        top=90,
    )
    d.pause(0.6)
    d.click(
        page.locator(".st-key-bulk_export_figfmts button").filter(has_text="PNG"),
        "PNG too",
    )
    tabular = page.locator(".st-key-bulk_export_tabular button")
    d.click(tabular.filter(has_text="Fixations"), "fixations table")
    d.click(tabular.filter(has_text="Word measures"), "word measures")
    build = _button(page, "Build export")
    d.point_at(build)
    with d.fast(4):
        d.click(build, "Build", hold=0, wait=False, park=False)
        d.pause(0.6)
        d.settle(quiet=0.8)
    d.download(_button(page, "Download bundle"), "Download zip")
    d.pause(1.6)
    d.finish("24 trials, every figure and table, in one zip")


@workflow("add-your-data", "Bring your own EyeLink reports")
def add_your_data(d: Demo) -> None:
    page = d.page
    data = Path(tempfile.mkdtemp(prefix="demo-data-"))
    fixations = data / "fixation_report.csv"
    words = data / "ia_report.csv"
    shutil.copy(SAMPLE / "fixations.csv", fixations)
    shutil.copy(SAMPLE / "ia.csv", words)
    d.pause(0.8)
    d.click(page.locator(".st-key-add_dataset_menu button"), "+", wait=False, hold=0.4)
    d.click(
        page.locator('[data-testid="stPopoverBody"] button').filter(
            has_text="Import files"
        ),
        "Import files",
    )
    d.type_into(
        page.locator('[data-testid="stMain"] input[type="text"]').first,
        "My reading study",
        "name it",
    )
    uploads = page.locator('[data-testid="stMain"] button').filter(has_text="Upload")
    d.upload(uploads.first, fixations, "fixation report")
    d.step("columns found for you")
    d.pause(2.2)
    d.upload(uploads.first, words, "interest-area report")
    d.pause(1.6)
    for label, step in (
        ("Use a common default (2560×1440)", "screen"),
        ("Use typical lab values", "distance"),
        ("Scale to the word boxes", "text size"),
    ):
        d.click(page.locator("label").filter(has_text=label), step, hold=0.3)
    d.click(_button(page, "Add dataset"), "Add dataset", hold=0.4)
    # Up to the new row in the datasets table and its summary, rather than the
    # download folder below them (which names a path on this machine).
    d.scroll(-380)
    d.pause(1.8)
    d.click(_nav(page, "Scanpath"), "Scanpath", hold=0.6)
    d.settle(quiet=1.2)
    d.pause(1.6)
    d.finish("Your data, mapped and on screen")


@workflow("plot-controls", "Make the regressions stand out")
def plot_controls(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    d.click(
        page.locator(".st-key-split_mode_rail_sac_popover button"),
        "Saccades ▾",
        wait=False,
        hold=0.5,
    )
    d.choose(
        "global_saccade_color_mode", "Forward / regression", "forward / regression"
    )
    d.close_popover()
    d.pause(0.8)
    d.click(_toggle(page, "global_show_words"), "word boxes", hold=1.0)
    d.click(
        page.locator(".st-key-split_mode_rail_fix_popover button"),
        "Fixations ▾",
        wait=False,
        hold=0.5,
    )
    d.click(page.locator(".st-key-global_show_order label"), "fixation order", hold=0.4)
    d.close_popover()
    d.pause(1.4)
    d.choose("global_palette", "High contrast", "high-contrast palette")
    d.pause(1.6)
    d.finish("Regressions, word boxes and reading order")


@workflow("design-presets", "Switch between ready-made designs")
def design_presets(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    for key, label, hold in (
        ("viz_view_heatmap", "Heatmap", 2.0),
        ("viz_view_illustration", "Illustration", 2.0),
        ("viz_view_scanpath", "Scanpath", 1.2),
    ):
        d.click(page.locator(f".st-key-{key} button"), label, hold=hold)
    d.click(_toggle(page, "global_show_heatmap"), "heatmap on top", hold=1.8)
    d.finish("One click per design")


@workflow("subtabs", "What sits under the figure")
def subtabs(d: Demo) -> None:
    page = d.page
    d.pad_page()
    d.pause(0.6)
    d.scroll_to(page.locator('[data-testid="stTabs"]').first, top=HEADER + 10)
    d.pause(0.4)
    for label, hold in (
        ("Annotations", 1.4),
        ("Stimulus & context", 2.0),
        ("Comparisons", 2.2),
        ("Export", 1.8),
        ("Share", 1.8),
    ):
        d.click(_tab(page, label), label, hold=hold)
    d.finish("Notes, context, matches, export and sharing")


@workflow("corpus-analysis", "From one trial to the whole corpus")
def corpus_analysis(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    d.click(_nav(page, "Corpus Analysis"), "Corpus Analysis", hold=1.4)
    d.choose("ptext_view", "Measure on the stimulus", "on the stimulus", hold=0.8)
    d.scroll(330)
    d.pause(2.0)
    d.scroll(-330)
    d.choose("ptext_view", "Measure vs feature", "vs surprisal", hold=0.8)
    d.scroll(330)
    d.pause(2.0)
    d.scroll(-330)
    d.click(_tab(page, "Groups"), "Groups", hold=0.6)
    d.click(_toggle(page, "groups_compare"), "Adv vs Ele", hold=0.6)
    d.scroll(520)
    d.pause(2.4)
    d.finish("Word profiles, maps, features and group contrasts")


@workflow("trial-filtering", "Find the trials you need")
def trial_filtering(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    for _ in range(2):
        d.click(
            page.locator(".st-key-single_next_trial button"), "next trial", hold=0.6
        )
    d.click(
        page.locator(".st-key-iconpop_filter_trials button"),
        "Filter ▾",
        wait=False,
        hold=0.5,
    )
    d.open(page.locator(".st-key-filter_difficulty_level [role=group]"))
    d.click(_option(page, "Ele"), "Ele texts only", hold=0.6)
    d.open(page.locator(".st-key-filter_participants [role=group]"))
    d.click(_option(page, "l7_1090"), "one participant", hold=0.6)
    d.close_popover()
    d.close_popover()
    d.pause(0.8)
    d.click(page.locator(".st-key-single_next_trial button"), "next trial", hold=1.4)
    d.finish(f"24 trials narrowed to the {_trial_count(page)} you need")


@workflow("favorites", "Star and tag trials, then come back to them")
def favorites(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    star = page.locator(".st-key-tutorial_annotations label").filter(
        has_text="Favorite"
    )
    # Just far enough down that the trial picker and the Favorite box both
    # show, so stepping between them never scrolls the page.
    d.pad_page()
    tag = page.get_by_placeholder("Add a new tag")
    d.scroll_to(tag, top=VIEWPORT["height"] - 75)
    d.pause(0.3)
    d.click(star, "★", hold=0.4)
    d.type_into(tag, "long regression", "tag it")
    d.pause(0.6)
    for _ in range(2):
        d.click(page.locator(".st-key-single_next_trial button"), "next", hold=0.4)
    d.click(star, "★", hold=0.6)
    d.click(
        page.locator(".st-key-iconpop_filter_trials button"),
        "Filter ▾",
        wait=False,
        hold=0.5,
    )
    d.click(page.locator(".st-key-filter_favorites label"), "favorites only", hold=0.6)
    d.close_popover()
    d.pause(0.8)
    d.click(
        page.locator(".st-key-single_prev_trial button"), "previous favorite", hold=1.4
    )
    d.finish("Your starred trials, one click apart")


@workflow("replay", "Replay how the text was read")
def replay(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    d.click(_toggle(page, "single_animate"), "Animate", hold=2.4)
    d.click(
        page.locator(".st-key-split_mode_animate_popover button"),
        "Animate ▾",
        wait=False,
        hold=0.4,
    )
    # ×4 is the 8th of the ten speeds (tabs._ANIM_SPEED_OPTIONS), 7/9 along.
    d.drag_slider("single_playback_speed", 7 / 9, "×4 speed")
    d.close_popover()
    d.settle()
    d.park()
    d.pause(5.5)
    d.finish("Fixation by fixation, at any speed")


@workflow("replay-export", "Save the replay as a GIF")
def replay_export(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    d.click(_toggle(page, "single_animate"), "Animate", hold=1.0)
    d.click(_tab(page, "Export"), "Export")
    d.scroll_to(page.locator(".st-key-tutorial_export"), top=150)
    d.click(page.locator("label").filter(has_text="GIF"), "GIF", hold=0.6)
    generate = page.locator(".st-key-anim_export_generate button")
    d.point_at(generate)
    with d.fast(6):
        d.click(generate, "Render", hold=0, wait=False, park=False)
        d.pause(0.6)
        d.settle(quiet=1.0)
    d.download(page.locator(".st-key-anim_export_download button"), "Download")
    d.pause(1.6)
    d.finish("The replay, as a GIF for slides")


@workflow("compare", "Compare two readers of the same text")
def compare(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    d.click(_toggle(page, "single_compare_toggle"), "Compare", hold=2.2)
    d.click(
        page.locator(".st-key-split_mode_compare_popover button"),
        "Compare ▾",
        wait=False,
        hold=0.4,
    )
    d.click(
        page.locator(".st-key-single_compare_layout button").filter(
            has_text="Side by side"
        ),
        "side by side",
        hold=0.6,
    )
    d.click(
        page.locator(".st-key-single_compare_step_linked label"),
        "A and B together",
        hold=0.4,
    )
    d.close_popover()
    d.pause(1.6)
    # Both readers move on to the next text.
    d.click(page.locator(".st-key-single_next_trial button"), "next text", hold=2.0)
    d.finish("Two readers, overlaid or side by side, text by text")


@workflow("share-link", "Send a colleague exactly this view")
def share_link(d: Demo) -> None:
    page = d.page
    d.pause(0.8)
    d.click(page.locator(".st-key-viz_view_heatmap button"), "Heatmap", hold=1.0)
    d.click(_tab(page, "Share"), "Share")
    d.scroll_to(_tab(page, "Share").first, top=HEADER + 10)
    d.click(
        page.locator("button, label").filter(has_text="Code").first, "Code", hold=2.4
    )
    d.click(
        page.locator("button, label").filter(has_text="Link").first, "Link", hold=0.6
    )
    # The link and its button are drawn in the Share widget's own iframe.
    widget = _frame_with(page, 'button:has-text("Copy link")')
    url = widget.evaluate(_SHARE_URL_JS)
    d.click(
        widget.locator("button").filter(has_text="Copy link"), "Copy link", hold=0.8
    )
    d.step("a colleague opens it")
    d.pause(1.0)
    page.goto(url, wait_until="domcontentloaded")
    d.settle(quiet=1.5)
    page.add_style_tag(content=HIDE_CSS)
    # A new page: draw the bar and the pointer on it again.
    d.hud()
    d.pointer.move(d.pointer.x, d.pointer.y)
    d.pause(2.6)
    d.finish("Same trial, same design, one link")


# -- running them ---------------------------------------------------------------


def record_one(browser, url: str, flow: Workflow, frames: Path) -> Path:
    context = browser.new_context(
        viewport=VIEWPORT,
        device_scale_factor=1,
        color_scheme="light",
        accept_downloads=True,
    )
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=url)
    context.add_cookies(
        [{"name": n, "value": "1", "url": url} for n in OPT_OUT_COOKIES]
    )
    context.add_init_script(OVERLAY_JS)
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")
    demo = Demo(page, flow.goal)
    demo.settle(quiet=3.0)
    page.add_style_tag(content=HIDE_CSS)
    demo.pointer.move(*PARK)
    demo.hud()
    cast = Screencast(page, frames)
    cast.start()
    try:
        flow.run(demo)
    except Exception:
        shot = OUT / f"{flow.name}.failed.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=shot)
        print(f"  ! failed; the page as it was: {shot}", flush=True)
        context.close()
        raise
    listing = cast.stop(demo.warp)
    context.close()
    return listing


def _usual_port() -> int:
    """The first free port from the app's own 8501, so the Share link looks usual."""
    for port in range(8501, 8521):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return free_port()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", help="workflows to record (default: all)")
    parser.add_argument(
        "--list", action="store_true", help="list the workflows and exit"
    )
    args = parser.parse_args()
    if args.list:
        for flow in WORKFLOWS.values():
            print(f"{flow.name:16} {flow.goal}")
        return
    unknown = sorted(set(args.names) - set(WORKFLOWS))
    if unknown:
        parser.error(f"no such workflow: {', '.join(unknown)} (see --list)")
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH")
    flows = (
        [WORKFLOWS[n] for n in args.names] if args.names else list(WORKFLOWS.values())
    )
    app = None
    url = URL
    state = Path(tempfile.mkdtemp(prefix="demo-state-"))
    if not url:
        port = _usual_port()
        app = start_app(
            port,
            {"SCANPATH_STUDIO_PERSIST": "1", "SCANPATH_STUDIO_STATE_DIR": str(state)},
        )
        url = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME or find_chrome())
            failed = []
            for flow in flows:
                print(f"{flow.name}: {flow.goal}", flush=True)
                # Nothing the last workflow saved may be restored into this one.
                shutil.rmtree(state, ignore_errors=True)
                state.mkdir()
                with tempfile.TemporaryDirectory() as tmp:
                    try:
                        listing = record_one(browser, url, flow, Path(tmp))
                    except Exception as exc:  # the next workflow may still work
                        print(
                            f"  ! {type(exc).__name__}: {str(exc).splitlines()[0]}",
                            flush=True,
                        )
                        failed.append(flow.name)
                        continue
                    encode_gif(listing, OUT / f"{flow.name}.gif")
                    VIDEO_OUT.mkdir(parents=True, exist_ok=True)
                    encode_mp4(listing, VIDEO_OUT / f"{flow.name}.mp4")
            browser.close()
        if failed:
            raise SystemExit(f"not recorded: {', '.join(failed)}")
    finally:
        if app is not None:
            app.terminate()
            app.wait(timeout=30)
        shutil.rmtree(state, ignore_errors=True)


if __name__ == "__main__":
    main()
