"""Manuscript screenshots of the running application.

The other scripts here render figures headlessly through the public API. This
one is the exception the README used to note: the interface figures can only
come from the app itself, so it drives a real browser over a running server and
saves what a user would see.

Run the app first (its port is the one this script talks to)::

    cd app && uv run streamlit run streamlit_app.py --server.port 8599

then, from the same directory::

    PAPER_FIGURES_DIR=../overleaf/figures \
        uv run --with playwright python paper/paper_ui_screenshots.py

Playwright is not a package dependency — it is pulled in for the run above.
Its Chromium build comes from ``playwright install chromium``; set
``PAPER_CHROME`` to point at another Chrome/Chromium binary instead.

Captured in the app's **light** theme at a 2x device scale factor, with
Streamlit's local-dev toolbar hidden, so the images stand up to print.

Two of the figures need data beyond the bundled demo: the MultiplEYE
question-screen heatmap loads the ZH-CH sample through the app's public-corpus
picker, so `data/MultiplEYE_ZH_CH_Zurich_1_2025` has to be in place (see
`datasets.load_multipleye`). Everything else is the demo the app ships with.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import Frame, Locator, Page, sync_playwright

URL = os.environ.get("PAPER_APP_URL", "http://localhost:8599")
OUT = Path(os.environ.get("PAPER_FIGURES_DIR", Path(__file__).parent / "figures"))
CHROME = os.environ.get("PAPER_CHROME")

#: Wide enough that the scanpath renders at true scale rather than fitted down.
VIEWPORT = {"width": 1680, "height": 1050}

#: The Deploy button and the ⋮ menu are local-dev chrome; they have no place in
#: a manuscript figure.
HIDE_CSS = """
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"],
[data-testid="stToolbarActions"],
header [data-testid="stActionButtonIcon"] { display: none !important; }
"""

#: Trailing whitespace to keep when a capture is trimmed, in device pixels.
TRIM_PAD = 48


# --- browser plumbing --------------------------------------------------------


def settle(page: Page, quiet: float = 1.5, timeout: float = 120) -> None:
    """Block until Streamlit has stopped rerunning for ``quiet`` seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not page.locator('[data-testid="stStatusWidget"]').count():
            page.wait_for_timeout(int(quiet * 1000))
            if not page.locator('[data-testid="stStatusWidget"]').count():
                return
        page.wait_for_timeout(250)
    print("  ! the app never went idle", flush=True)


def visible(locator: Locator) -> list[Locator]:
    return [el for el in locator.all() if el.is_visible()]


def trim(path: Path) -> None:
    """Crop the dead uniform margin off the bottom and right of a capture."""
    try:
        from PIL import Image
    except ImportError:  # optional — the untrimmed capture is still usable
        return
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    bg = px[w - 4, h - 4]
    bottom = h
    while bottom > 1 and all(px[x, bottom - 1] == bg for x in range(0, w, 4)):
        bottom -= 1
    bottom = min(h, bottom + TRIM_PAD)
    right = w
    while right > 1 and all(px[right - 1, y] == bg for y in range(0, bottom, 4)):
        right -= 1
    right = min(w, right + TRIM_PAD)
    if (right, bottom) != (w, h):
        im.crop((0, 0, right, bottom)).save(path)


def shot(page: Page, name: str, locator: Locator | None = None, **kw) -> None:
    # Tidy the page before every capture. A click Playwright had to scroll into
    # view leaves the page — or the control rail, which has a scroll area of its
    # own — part-way down; the control it pressed keeps focus, and Streamlit
    # renders that control's help tooltip while it has focus or the pointer.
    page.mouse.move(2, 2)
    page.evaluate("""() => {
      if (document.activeElement) document.activeElement.blur();
      window.scrollTo(0, 0);
      document.querySelectorAll('*').forEach(el => { if (el.scrollTop) el.scrollTop = 0; });
      document.querySelectorAll('[data-testid="stTooltipContent"], [role="tooltip"]')
        .forEach(el => {
          const host = el.closest('[data-baseweb="popover"]') || el;
          host.style.display = 'none';
        });
    }""")
    page.wait_for_timeout(500)
    path = OUT / f"{name}.png"
    (locator or page).screenshot(path=str(path), **kw)
    if kw.get("full_page"):
        # A full-page capture remounts the component iframes; let the app come
        # back before anything goes looking for the plot again.
        settle(page, quiet=2.0)
    trim(path)
    print(f"  {path.name} ({path.stat().st_size // 1024} KB)", flush=True)


def shot_block(page: Page, name: str, locator: Locator, max_h: int = 1000) -> None:
    """Capture one panel: no sticky header over it, no dead tail below it."""
    page.locator('[data-testid="stHeader"]').evaluate_all(
        "els => els.forEach(e => (e.style.visibility = 'hidden'))"
    )
    locator.evaluate(
        "(el, h) => { el.dataset.shotStyle = el.style.cssText;"
        " el.style.maxHeight = h + 'px'; el.style.overflow = 'hidden'; }",
        max_h,
    )
    page.wait_for_timeout(400)
    shot(page, name, locator=locator)
    locator.evaluate("el => { el.style.cssText = el.dataset.shotStyle || ''; }")
    page.locator('[data-testid="stHeader"]').evaluate_all(
        "els => els.forEach(e => (e.style.visibility = ''))"
    )


def close_tour(page: Page) -> None:
    """Dismiss the spotlight tour card — the welcome one or the wizard's."""
    for _ in range(3):
        btns = visible(page.locator(".st-key-tour_sp_close button")) or visible(
            page.locator('.st-key-tour_card button:has-text("Skip")')
        )
        if not btns:
            return
        btns[0].click()
        settle(page)


def plot_frame(page: Page, key: str) -> Frame:
    """The srcdoc iframe holding the true-scale plot rendered under ``key``."""
    for _ in range(80):
        for frame in page.frames:
            try:
                if frame.locator(f"#truescale-{key}").count():
                    return frame
            except Exception:  # noqa: BLE001 - a frame detached mid-scan
                pass
        page.wait_for_timeout(500)
    raise RuntimeError(f"no plot frame for #truescale-{key} — is a trial selected?")


def shot_plot(page: Page, name: str, key: str) -> None:
    """Capture the figure alone, without the surrounding application."""
    frame = plot_frame(page, key)
    el = frame.locator(f"#truescale-{key}")
    el.wait_for(state="visible")
    page.wait_for_timeout(1500)  # let Plotly finish drawing
    # The zoom toolbar is an interaction affordance, not part of the figure.
    frame.locator(f"#zoombar-{key}").evaluate_all(
        "els => els.forEach(e => (e.style.visibility = 'hidden'))"
    )
    shot(page, name, locator=el)


def nav(page: Page, label: str) -> None:
    page.locator(f'[data-testid="stTopNavLink"]:has-text("{label}")').first.click()
    settle(page, quiet=2.0)
    close_tour(page)


def toggle(page: Page, container_key: str) -> None:
    page.locator(f".st-key-{container_key} label").first.click()
    settle(page, quiet=2.0)


def deep_link(page: Page, params: dict) -> None:
    """Open a view through the app's own URL contract (``url_state``).

    Every layer a figure depends on is named explicitly: the app restores the
    previous session's plot settings on load, so anything left unsaid is
    inherited from whatever ran last rather than from the defaults.
    """
    page.goto(f"{URL}/?{urlencode(params)}", wait_until="domcontentloaded")
    settle(page, quiet=2.5)
    close_tour(page)
    if not page.locator(
        '[data-testid="stTopNavLink"][aria-current]:has-text("Scanpath")'
    ).count():
        nav(page, "Scanpath")
    settle(page, quiet=2.0)


def reset_viz(page: Page) -> None:
    """Press ♻️ Reset visualization, so a run never inherits the last one's view.

    The fixation-index window in particular has no URL param (VIZ-7), so a
    window left behind by an earlier run would silently subset every figure.
    """
    btns = visible(page.locator('button:has-text("Reset visualization")'))
    if not btns:
        print("  ! no reset button", flush=True)
        return
    btns[0].click()
    settle(page, quiet=2.0)
    confirm = visible(page.locator('button:has-text("Reset it")'))
    if confirm:
        confirm[0].click()
        settle(page, quiet=2.5)


def set_fix_window(page: Page, lo: int, hi: int) -> None:
    """Drive the 🧹 Filter panel's *Fixation index range* to ``lo``–``hi``.

    Keyboard rather than a drag: the range is two native ``input[type=range]``
    elements, and PageUp/Down move in one stride, so converging on a value takes
    a handful of presses instead of a pixel calculation that has to be right.
    """
    for attempt in range(5):
        if page.locator('.st-key-single_fix_range input[aria-label*="start"]').count():
            break
        btns = visible(page.locator(".st-key-split_mode_rail_filter button"))
        if btns:
            btns[0].click()
        settle(page, quiet=1.0)
    else:
        raise RuntimeError("the 🧹 Filter panel never opened")

    for aria, target in (("start", lo), ("end", hi)):
        thumb = page.locator(f'.st-key-single_fix_range input[aria-label*="{aria}"]')
        thumb.focus()
        for _ in range(300):
            current = int(thumb.input_value())
            if current == target:
                break
            delta = target - current
            if abs(delta) >= 15:
                page.keyboard.press("PageUp" if delta > 0 else "PageDown")
            else:
                page.keyboard.press("ArrowRight" if delta > 0 else "ArrowLeft")
        else:
            raise RuntimeError(f"fixation window {aria} never reached {target}")
    settle(page, quiet=1.5)
    page.keyboard.press("Escape")
    settle(page, quiet=1.5)


def shot_zoomed_plot(page: Page, name: str, key: str, w0: int, w1: int) -> None:
    """Capture the plot's own zoom/pan viewport, framed on words ``w0``–``w1``.

    The figure always draws the whole passage's word boxes — no setting crops
    the canvas to part of a text — so a sentence-sized figure comes from the
    plot's zoom (1×–8×, a CSS transform over the SVG, so it stays crisp) panned
    onto the words in question, which is how a reader would look at one there.
    """
    frame = plot_frame(page, key)
    frame.locator(f"#truescale-{key}").wait_for(state="visible")
    page.wait_for_timeout(1500)
    info = frame.evaluate(
        """([key, w0, w1]) => {
      const d = document, gd = d.getElementById('truescale-' + key);
      const outer = d.getElementById('fit-' + key), box = d.getElementById('box-' + key);
      const zoombar = d.getElementById('zoombar-' + key);
      if (zoombar) zoombar.style.visibility = 'hidden';
      const scaleOf = () => parseFloat(/scale\\(([\\d.]+)\\)/.exec(box.style.transform)[1]);
      const xs = Array.from(gd._fullData[0].x), ys = Array.from(gd._fullData[0].y);
      const xa = gd._fullLayout.xaxis, ya = gd._fullLayout.yaxis;
      const px = [], py = [];
      for (let i = w0; i <= w1; i++) {
        px.push(xa.l2p(xs[i]) + xa._offset);
        py.push(ya.l2p(ys[i]) + ya._offset);
      }
      // The word trace is anchored at box centres; pad for the glyphs, for the
      // fixations snapped above them, and for their index labels. Asymmetric,
      // because the schematic's saccade arcs rise above the line they leave.
      const PAD_X = 90, PAD_TOP = 58, PAD_BOTTOM = 48;
      const x0 = Math.min(...px) - PAD_X, x1 = Math.max(...px) + PAD_X;
      const y0 = Math.min(...py) - PAD_TOP, y1 = Math.max(...py) + PAD_BOTTOM;
      const base = scaleOf(), cw = outer.clientWidth, ch = outer.clientHeight;
      // The toolbar zooms in 1.25x steps, so take as many as still fit.
      const want = Math.min(cw / (x1 - x0), ch / (y1 - y0));
      const steps = Math.max(0, Math.floor(Math.log(want / base) / Math.log(1.25)));
      for (let i = 0; i < steps; i++) d.getElementById('zoomin-' + key).click();
      const s = scaleOf();
      // Shrink the scroll viewport onto the words too, so the capture is the
      // sentence and not a sentence in a field of white.
      const h = Math.min(ch, Math.round((y1 - y0) * s));
      const w = Math.min(cw, Math.round((x1 - x0) * s));
      outer.style.height = h + 'px';
      outer.style.width = w + 'px';
      outer.scrollLeft = ((x0 + x1) / 2) * s - w / 2;
      outer.scrollTop = ((y0 + y1) / 2) * s - h / 2;
      return {steps, zoom: d.getElementById('zoomlabel-' + key).textContent, w, h};
    }""",
        [key, w0, w1],
    )
    print(
        f"  zoom {info['zoom']} ({info['steps']} steps) → {info['w']}x{info['h']}",
        flush=True,
    )
    page.wait_for_timeout(800)
    shot(page, name, locator=frame.locator(f"#fit-{key}"))


# --- the captures ------------------------------------------------------------

#: Subtab label → figure name, in bar order.
SUBTABS = {
    "Annotations": "fig_ui_tab_annotations",
    "Stimulus & Context": "fig_ui_tab_stimulus",
    "Comparisons": "fig_ui_tab_comparisons",
    "Export": "fig_ui_tab_export",
    "Share": "fig_ui_tab_share",
}

#: The bundled demo trial every OneStop figure is taken from.
DEMO_TRIAL = {
    "source": "demo",
    "participant": "l37_1129",
    "trial_id": "l37_1129_2_1_1_Ele_r0",
}

#: Words 92–105 of that trial — “Our clients want to know how well their stores
#: are delivering on that experience.” — read by fixations 124–139. The whole
#: sentence sits inside the trial's answer span, so it renders highlighted.
SENTENCE_WORDS = (92, 105)
SENTENCE_FIXATIONS = (124, 139)

#: One MultiplEYE reading: a Chinese stimulus, on the last of its comprehension
#: -question screens (70 fixations over the question and its four options).
MULTIPLEYE_QUESTION = {
    "source": "corpus",
    "corpus": "multipleye",
    "participant": "001_ZH_CH_1_ET1",
    "trial_id": "Arg_PISACowsMilk_10",
    "screen": "question_10131",
}


def capture(page: Page) -> None:
    # The app restores the last session's dataset, view and plot settings, so
    # neither the trial nor the layers can be left to chance: name the trial in
    # the URL, then reset the view to the app's own defaults.
    deep_link(page, DEMO_TRIAL)
    reset_viz(page)

    print("scanpath", flush=True)
    shot_plot(page, "fig_ui_plot_scanpath", "single")
    shot(page, "fig_interface", full_page=True)

    print("heatmap", flush=True)
    page.locator(".st-key-viz_view_heatmap button").first.click()
    settle(page, quiet=2.5)
    shot_plot(page, "fig_ui_plot_heatmap", "single")
    shot(page, "fig_ui_scanpath_heatmap", full_page=True)
    page.locator(".st-key-viz_view_scanpath button").first.click()
    settle(page, quiet=2.5)

    print("comparison", flush=True)
    toggle(page, "split_mode_compare")
    shot_plot(page, "fig_ui_plot_comparison", "compare")
    shot(page, "fig_ui_scanpath_compare", full_page=True)
    toggle(page, "split_mode_compare")

    print("subtabs", flush=True)
    tabs = page.locator('[data-testid="stTabs"]').first
    for label, name in SUBTABS.items():
        page.locator(f'[data-testid="stTab"]:has-text("{label}")').first.click()
        settle(page, quiet=2.0)
        # The Comparisons grid runs long; two rows of it say enough.
        shot_block(page, name, tabs, max_h=800 if "comparisons" in name else 1000)
    page.locator('[data-testid="stTab"]:has-text("Annotations")').first.click()
    settle(page, quiet=1.5)

    print("session", flush=True)
    page.locator('[data-testid="stTopNavLink"]:has-text("Session")').first.click()
    settle(page, quiet=2.5)
    panel = page.locator('[data-testid="stDialog"] [role="dialog"]').first
    shot(page, "fig_ui_session", locator=panel)
    close = visible(page.locator('[data-testid="stDialog"] button[aria-label="Close"]'))
    if close:
        close[0].click()
    else:
        page.keyboard.press("Escape")
    settle(page, quiet=2.0)

    print("corpus analysis", flush=True)
    nav(page, "Corpus Analysis")
    page.wait_for_timeout(2000)
    shot(page, "fig_ui_corpus", full_page=True)

    print("data management", flush=True)
    nav(page, "Data")
    page.wait_for_timeout(1500)
    shot(page, "fig_ui_data", full_page=True)
    shot(
        page,
        "fig_ui_data_datasets",
        locator=page.locator(".st-key-data_overview").first,
    )

    print("add dataset", flush=True)
    visible(page.locator('button:has-text("Add dataset")'))[0].click()
    settle(page, quiet=2.5)
    page.wait_for_timeout(3000)  # the wizard's own tour card arrives late
    close_tour(page)
    close_tour(page)
    shot(page, "fig_ui_data_add", full_page=True)

    # Leave the app as it was found.
    cancel = visible(page.locator('button:has-text("Cancel")'))
    if cancel:
        cancel[0].click()
        settle(page, quiet=2.0)
    leave = visible(page.locator('button:has-text("Discard and leave")'))
    if leave:
        leave[0].click()
        settle(page, quiet=2.0)

    # The two figures that need a view of their own come last, because each
    # leaves the app somewhere the ones above would rather not start from.
    print("sentence schematic", flush=True)
    deep_link(
        page,
        {
            **DEMO_TRIAL,
            # VIZ-9's linear-reading schematic: fixations snapped above the word
            # they landed on, saccades arced over the text.
            "snap_fixations": 1,
            "saccade_render_mode": "Arc",
            "show_order": 1,
            "critical_span_style": "Mark text",
            "highlight_column": "is_in_aspan",
            "show_words": 1,
            "show_labels": 1,
            "show_fixations": 1,
            "show_saccades": 1,
            "show_heatmap": 0,
            "show_raw_gaze": 0,
            "full_monitor": 0,
            "palette": "Default (colourblind-safe)",
        },
    )
    set_fix_window(page, *SENTENCE_FIXATIONS)
    shot_zoomed_plot(page, "fig_ui_plot_sentence_schematic", "single", *SENTENCE_WORDS)

    print("multipleye question screen", flush=True)
    deep_link(
        page,
        {
            **MULTIPLEYE_QUESTION,
            "show_heatmap": 1,
            "heatmap_style": "Interpolated",
            "heatmap_colorscale": "Viridis",
            "show_colorbars": 1,
            "show_words": 1,
            "show_labels": 1,
            "show_fixations": 0,
            "show_saccades": 0,
            "show_raw_gaze": 0,
            "snap_fixations": 0,
            "saccade_render_mode": "Straight",
            "full_monitor": 1,
            "palette": "Default (colourblind-safe)",
            # BUG: every multipart screen after the first trips the "fixation
            # subset" disclosure — the window slider sizes itself to the screen's
            # highest parent-global fixation index (1..578) while the label
            # compares against the screen's own span (509..578), so they never
            # match and the figure is stamped for a subset nobody asked for.
            # Nothing here is subset, so the false stamp is turned off.
            "illustration_label": "Hide",
        },
    )
    shot_plot(page, "fig_ui_plot_multipleye_question", "single")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{URL} → {OUT}", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)
        ctx = browser.new_context(
            viewport=VIEWPORT, device_scale_factor=2, color_scheme="light"
        )
        ctx.add_init_script(
            "document.addEventListener('DOMContentLoaded', () => {"
            "const s = document.createElement('style');"
            f"s.textContent = {HIDE_CSS!r};"
            "document.head.appendChild(s);});"
        )
        page = ctx.new_page()
        capture(page)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
