"""Capture the tutorial UI screenshots from a running local app (UX-22).

Usage:
    streamlit run scanpath_studio/app.py
    python scripts/capture_tutorial_screenshots.py

The locators are user-facing labels on purpose: if the product wording changes,
the capture fails loudly instead of silently publishing an unrelated picture.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8501/?tour=0")
    parser.add_argument("--output", type=Path, default=Path("docs/assets/tutorials"))
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Install Playwright and Chromium to capture screenshots"
        ) from exc

    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(args.url, wait_until="networkidle")
        page.get_by_role("button", name="➕ Add data").click()
        page.screenshot(path=args.output / "setup-wizard.png", full_page=True)
        page.goto(args.url, wait_until="networkidle")
        page.get_by_text("Compare", exact=True).click()
        page.get_by_role("button", name="⚙️ Compare options").click()
        page.screenshot(path=args.output / "compare-options.png", full_page=True)
        page.get_by_text("Export", exact=True).click()
        page.get_by_text("Multiple trials", exact=True).click()
        page.screenshot(path=args.output / "bulk-export.png", full_page=True)
        page.get_by_text("Line assignment", exact=True).click()
        page.screenshot(path=args.output / "line-assignment.png", full_page=True)
        page.get_by_role("button", name=re.compile("Fixation"), exact=False).click()
        page.screenshot(path=args.output / "fixation-filter.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
