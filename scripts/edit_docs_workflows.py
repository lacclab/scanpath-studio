"""Build the homepage's concise task montages from the app recordings.

Run from the repo root once ``record_workflow_demos.py`` has written the source
clips; ffmpeg must be on PATH::

    uv run --with playwright python scripts/edit_docs_workflows.py

Each scene's caption is the recorder's own bar — its pill, font and orange
badge, drawn by the same ``demoHud`` in headless Chrome — with the scene's
number in the badge where a source clip counts its clicks. The PDF scenes are
stills of the running app's Export tab; ``--stills`` re-captures them first,
from an app it starts itself, and its last still follows a verified PDF
download. Source clips remain intact for use in the individual feature guides.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit
from capture_docs_screenshots import find_chrome, free_port, start_app
from playwright.sync_api import Page, sync_playwright
from record_app_demo import HIDE_CSS, settle
from record_workflow_demos import (
    HUD_MAX_WIDTH,
    HUD_RIGHT,
    LOCAL_PATHS_CSS,
    OPT_OUT_COOKIES,
    OVERLAY_JS,
    VIEWPORT,
)

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ROOT / "docs/assets/workflows"
STILLS = ROOT / "assets/workflow-sources"
#: The montages' frame, and how far the recordings' viewport is scaled to fit
#: it — the caption is drawn at the same scale, so it matches the source bars.
WIDTH, HEIGHT = 1280, 800
SCALE = WIDTH / VIEWPORT["width"]
#: Room around the pill for its shadow.
SHADOW = 16
#: Where a source clip's own bar can be, in the montage's frame: the header
#: strip from its widest left edge to its right edge, shadow included.
BAR_LEFT = round((VIEWPORT["width"] - HUD_RIGHT - HUD_MAX_WIDTH - SHADOW) * SCALE)
BAR_RIGHT = round((VIEWPORT["width"] - HUD_RIGHT + SHADOW // 2) * SCALE)
#: The face the app and the recorder's bar are set in, from Streamlit's own
#: static files, so the caption renders the same on any machine.
FONT_FILE = next(
    (Path(streamlit.__file__).parent / "static" / "static" / "media").glob(
        "SourceSansVF-Upright*.woff2"
    )
)
# (source, start, duration, caption); time ranges omit the source clips' extra
# trial steps, replay-speed adjustment, and click-count closing cards.
EDITS = {
    "home-replay": [
        ("replay", 0, 4.8, "Replay the reading"),
        ("replay", 9, 4, "Follow the fixation sequence"),
    ],
    "home-filter-annotate": [
        ("trial-filtering", 5.1, 7.6, "Filter by condition and reader"),
        ("favorites", 0.5, 5.9, "Star and tag readings for follow-up"),
    ],
    "home-compare": [
        ("compare", 0, 12.5, "Overlay readings or place them side by side"),
        ("subtabs", 7.2, 2.5, "Comparisons - find matching trials"),
    ],
    "home-customize": [
        ("design-presets", 0, 10.8, "Start with a design preset"),
        ("plot-controls", 0.7, 14.8, "Adjust layers, properties and palette"),
    ],
    "home-export-share": [
        ("pdf-format.png", 0, 1.5, "Choose a download format"),
        ("pdf-selected.png", 0, 2, "Choose PDF"),
        ("pdf-downloaded.png", 0, 1.5, "Download the PDF figure"),
        ("share-link", 2.5, 8.5, "Share the view as code or a link"),
    ],
}


def capture_stills(browser) -> None:
    """The Export tab's PDF scenes: the format choice, PDF picked, PDF saved."""
    port = free_port()
    app = start_app(port)
    url = f"http://127.0.0.1:{port}"
    try:
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=1,
            color_scheme="light",
            accept_downloads=True,
        )
        context.add_cookies(
            [{"name": n, "value": "1", "url": url} for n in OPT_OUT_COOKIES]
        )
        page = context.new_page()
        page.goto(f"{url}/?ui=full", wait_until="domcontentloaded")
        settle(page, quiet=3.0)
        page.add_style_tag(content=HIDE_CSS + LOCAL_PATHS_CSS)
        page.locator('[data-testid="stTab"]').filter(has_text="Export").click()
        settle(page)

        def scroll_to_tabs(below: float = 0) -> None:
            # A rerun can put the page back at its top, so each still scrolls
            # from wherever it is to the tab bar. The wheel scrolls what is
            # under the pointer (the page, not the header); then the pointer
            # goes where it hovers nothing.
            tabs = page.locator('[data-testid="stTabs"]').first.bounding_box()
            page.mouse.move(VIEWPORT["width"] / 2, VIEWPORT["height"] / 2)
            page.mouse.wheel(0, tabs["y"] - 60 + below)
            page.mouse.move(VIEWPORT["width"] - 5, VIEWPORT["height"] - 5)
            page.wait_for_timeout(800)

        scroll_to_tabs()
        page.screenshot(path=STILLS / "pdf-format.png")
        page.locator('[data-testid="stRadio"] label').filter(has_text="PDF").click()
        settle(page)
        scroll_to_tabs()
        page.screenshot(path=STILLS / "pdf-selected.png")
        with page.expect_download(timeout=120_000) as saved:
            page.locator("button").filter(has_text="Download PDF").first.click()
        if not saved.value.suggested_filename.endswith(".pdf"):
            raise SystemExit(f"not a PDF: {saved.value.suggested_filename}")
        settle(page)
        scroll_to_tabs(below=60)
        page.screenshot(path=STILLS / "pdf-downloaded.png")
        context.close()
    finally:
        app.terminate()
        app.wait(timeout=30)
    print("stills", flush=True)


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def render_caption(page: Page, caption: str, label: str, out: Path) -> tuple[int, int]:
    """Draw ``caption`` as the recorder's bar into ``out``, a transparent PNG at
    the montage's scale; return where its top-left corner sits in the frame."""
    page.evaluate("([c, l]) => window.demoHud(0, c, null, null, l)", [caption, label])
    box = page.locator("#demo-hud").bounding_box()
    clip = {
        "x": box["x"] - SHADOW,
        "y": max(0, box["y"] - SHADOW),
        "width": box["width"] + 2 * SHADOW,
        "height": box["height"] + 2 * SHADOW,
    }
    page.screenshot(path=str(out), clip=clip, omit_background=True)
    return round(clip["x"] * SCALE), round(clip["y"] * SCALE)


def caption_page(browser) -> Page:
    """A blank page at the recordings' viewport, with the recorder's overlay."""
    page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
    font = base64.b64encode(FONT_FILE.read_bytes()).decode()
    page.set_content(
        "<style>@font-face{font-family:'Source Sans 3';font-weight:200 900;"
        f"src:url(data:font/woff2;base64,{font}) format('woff2')}}"
        "html,body{background:transparent;margin:0}</style>"
    )
    page.evaluate(OVERLAY_JS)
    page.evaluate("document.fonts.ready")
    return page


def main() -> None:
    with (
        tempfile.TemporaryDirectory(prefix="docs-video-edit-") as temp,
        sync_playwright() as pw,
    ):
        folder = Path(temp)
        browser = pw.chromium.launch(executable_path=find_chrome())
        if "--stills" in sys.argv:
            capture_stills(browser)
        page = caption_page(browser)
        for name, scenes in EDITS.items():
            parts = []
            for index, (source, start, duration, caption) in enumerate(scenes):
                output = folder / f"{name}-{index}.mp4"
                pill = folder / f"{name}-{index}.png"
                x, y = render_caption(
                    page, caption, f"{index + 1} of {len(scenes)}", pill
                )
                is_still = source.endswith(".png")
                path = STILLS / source if is_still else VIDEOS / f"{source}.mp4"
                inputs = ["-loop", "1"] if is_still else ["-ss", str(start)]
                filters = (
                    f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                    f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:white,setsar=1,fps=20,"
                    # Cover the source clip's own bar, whose click count would
                    # describe that clip rather than the montage.
                    f"drawbox=x={BAR_LEFT}:y=0:w={BAR_RIGHT - BAR_LEFT}:h=56:"
                    "color=white:t=fill[base];"
                    f"[base][1:v]overlay=x={x}:y={y}:shortest=1"
                )
                run(
                    *inputs,
                    "-i",
                    str(path),
                    "-loop",
                    "1",
                    "-i",
                    str(pill),
                    "-t",
                    str(duration),
                    "-filter_complex",
                    filters,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    str(output),
                )
                parts.append(output)
            listing = folder / "parts.txt"
            listing.write_text("".join(f"file '{part}'\n" for part in parts))
            output = VIDEOS / f"{name}.mp4"
            run(
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output),
            )
            run(
                "-ss",
                "1",
                "-i",
                str(output),
                "-frames:v",
                "1",
                "-c:v",
                "libwebp",
                "-quality",
                "85",
                str(VIDEOS / f"{name}_poster.webp"),
            )
            print(name, flush=True)
        browser.close()


if __name__ == "__main__":
    main()
