"""Serve the frozen improvements-tracker archive.

The tracker used to be an editable app: this server owned a write API, and
`tracker/state.json` was updated through it. ENG-32 moved every live item to
GitHub Issues on 2026-08-20, so there is nothing left to write — what remains is
the archive of every item ever raised, which the docs, the `plans/` notes and the
git history still cite by ID.

All that is needed for that is a static file server. It exists at all because
`tracker/index.html` reads `state.json` and `migrated.json` with `fetch`, which a
`file://` page is not allowed to do.

Run it with `python3 tracker/server.py`, or the `start.command` / `start.bat`
launchers beside this file.
"""

from __future__ import annotations

import argparse
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

APP_ROOT = Path(__file__).resolve().parent.parent
TRACKER_DIR = APP_ROOT / "tracker"
DATA_FILE = TRACKER_DIR / "data.js"
STATE_FILE = TRACKER_DIR / "state.json"
#: Tracker ID → GitHub issue number, written by `to_github_issues.py`. The page
#: reads it to put an "↗ #N" link on every item that moved.
MAP_FILE = TRACKER_DIR / "migrated.json"
ISSUES_URL = "https://github.com/lacclab/scanpath-studio/issues"


class TrackerHandler(SimpleHTTPRequestHandler):
    """Static server for the archive. No write endpoints — by design."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(APP_ROOT), **kwargs)

    #: The three files the page reads. They change on a `git pull`, and without
    #: an explicit header browsers fall back to *heuristic* freshness (a
    #: fraction of the time since `Last-Modified`) and can serve a stale copy
    #: without revalidating — items then just don't appear, with nothing to
    #: indicate why (ENG-29).
    _NO_STORE_PATHS = (
        "/tracker/data.js",
        "/tracker/state.json",
        "/tracker/migrated.json",
    )

    def end_headers(self) -> None:
        if urlsplit(self.path).path.endswith(self._NO_STORE_PATHS):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--no-open", action="store_true", help="Do not open the archive in a browser."
    )
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}/tracker/"

    with ThreadingHTTPServer(("127.0.0.1", args.port), TrackerHandler) as server:
        print(f"Tracker archive (read-only) at {url}")
        print(f"Open work lives on GitHub Issues: {ISSUES_URL}")
        print("Keep this window open; press Control-C to stop.")
        if not args.no_open:
            threading.Timer(0.35, webbrowser.open, args=(url,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nTracker archive stopped.")


if __name__ == "__main__":
    main()
