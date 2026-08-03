"""Serve the improvements tracker and persist its editable task overrides."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

APP_ROOT = Path(__file__).resolve().parent.parent
TRACKER_DIR = APP_ROOT / "tracker"
DATA_FILE = TRACKER_DIR / "data.js"
STATE_FILE = TRACKER_DIR / "state.json"
API_PATH = "/tracker/api/state"
MAX_BODY_BYTES = 2 * 1024 * 1024
STATUSES = {
    "Backlog",
    "Planned",
    "In progress",
    "Review",
    "Closed",
}
PRIORITIES = {"High", "Normal", "Low"}
EDIT_FIELDS = ("status", "priority", "implementationBrief", "archived", "updated")
CREATED_FIELDS = {
    "id",
    "prefix",
    "num",
    "sub",
    "title",
    "status",
    "priority",
    "implementationBrief",
    "group",
    "subgroup",
    "archived",
    "added",
    "body",
}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
STATE_LOCK = threading.Lock()


def _known_item_ids() -> set[str]:
    return set(
        re.findall(r'"id"\s*:\s*"([A-Z]{2,4}-\d+[a-z]?)"', DATA_FILE.read_text())
    )


def _known_groups() -> set[str]:
    return set(re.findall(r'"group"\s*:\s*"([^"]+)"', DATA_FILE.read_text()))


def _validate_created_item(value: Any, known_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CREATED_FIELDS:
        raise ValueError("Invalid created tracker item.")
    item_id = value["id"]
    prefix = value["prefix"]
    if not isinstance(item_id, str) or not isinstance(prefix, str):
        raise ValueError("Invalid created tracker item ID.")
    if not re.fullmatch(r"[A-Z]{2,4}", prefix) or not re.fullmatch(
        rf"{re.escape(prefix)}-\d+[a-z]?", item_id
    ):
        raise ValueError(f"Invalid created tracker item ID: {item_id}")
    if item_id in known_ids:
        raise ValueError(f"Duplicate tracker item: {item_id}")
    if not isinstance(value["num"], int) or value["num"] < 1:
        raise ValueError(f"Invalid item number for {item_id}.")
    if not isinstance(value["title"], str) or not value["title"].strip():
        raise ValueError(f"Invalid title for {item_id}.")
    if value["status"] not in STATUSES or value["priority"] not in PRIORITIES:
        raise ValueError(f"Invalid status or priority for {item_id}.")
    if value["group"] not in _known_groups():
        raise ValueError(f"Invalid group for {item_id}.")
    if not isinstance(value["implementationBrief"], str):
        raise ValueError(f"Invalid implementation brief for {item_id}.")
    if not isinstance(value["archived"], bool):
        raise ValueError(f"Invalid archive value for {item_id}.")
    if not isinstance(value["added"], str) or not DATE_RE.fullmatch(value["added"]):
        raise ValueError(f"Invalid creation date for {item_id}.")
    if not isinstance(value["body"], list) or not all(
        isinstance(line, str) for line in value["body"]
    ):
        raise ValueError(f"Invalid body for {item_id}.")
    if not isinstance(value["sub"], str) or not isinstance(value["subgroup"], str):
        raise ValueError(f"Invalid grouping for {item_id}.")
    return {field: value[field] for field in CREATED_FIELDS}


def _validate_state(value: Any) -> dict[str, Any]:
    expected = {"version", "revision", "items", "createdItems"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("Invalid tracker state.")
    if value["version"] != 2:
        raise ValueError("Unsupported tracker state version.")
    if not isinstance(value["revision"], int) or value["revision"] < 0:
        raise ValueError("Invalid tracker state revision.")
    if not isinstance(value["items"], dict):
        raise ValueError("Tracker items must be a JSON object.")
    if not isinstance(value["createdItems"], list):
        raise ValueError("Created tracker items must be an array.")

    known_ids = _known_item_ids()
    created_items = []
    for raw_item in value["createdItems"]:
        item = _validate_created_item(raw_item, known_ids)
        known_ids.add(item["id"])
        created_items.append(item)
    clean: dict[str, dict[str, Any]] = {}
    for item_id, edit in sorted(value["items"].items()):
        if item_id not in known_ids:
            raise ValueError(f"Unknown tracker item: {item_id}")
        if not isinstance(edit, dict):
            raise ValueError(f"Changes for {item_id} must be an object.")
        extra = set(edit) - set(EDIT_FIELDS)
        if extra:
            raise ValueError(f"Unsupported field for {item_id}: {sorted(extra)[0]}")
        if "status" in edit and edit["status"] not in STATUSES:
            raise ValueError(f"Invalid status for {item_id}.")
        if "priority" in edit and edit["priority"] not in PRIORITIES:
            raise ValueError(f"Invalid priority for {item_id}.")
        if "implementationBrief" in edit:
            note = edit["implementationBrief"]
            if not isinstance(note, str) or len(note) > 100_000:
                raise ValueError(f"Invalid implementation brief for {item_id}.")
        if "archived" in edit and not isinstance(edit["archived"], bool):
            raise ValueError(f"Invalid archive value for {item_id}.")
        if "updated" in edit:
            updated = edit["updated"]
            if not isinstance(updated, str) or not DATE_RE.fullmatch(updated):
                raise ValueError(f"Invalid update date for {item_id}.")
        clean[item_id] = {field: edit[field] for field in EDIT_FIELDS if field in edit}
    return {
        "version": 2,
        "revision": value["revision"],
        "items": clean,
        "createdItems": created_items,
    }


def _read_state() -> dict[str, Any]:
    return _validate_state(json.loads(STATE_FILE.read_text()))


def _write_state(state: dict[str, Any]) -> None:
    source = f"{json.dumps(state, indent=2, ensure_ascii=False)}\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=TRACKER_DIR,
            prefix=".state.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(source)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, STATE_FILE)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


class TrackerHandler(SimpleHTTPRequestHandler):
    """Static project server with one same-origin endpoint for tracker edits."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(APP_ROOT), **kwargs)

    def end_headers(self) -> None:
        if (
            self.path.endswith("/tracker/state.json")
            or urlsplit(self.path).path == API_PATH
        ):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if urlsplit(self.path).path == API_PATH:
            self._send_json(HTTPStatus.OK, {"ok": True, "state": _read_state()})
            return
        super().do_GET()

    def do_PUT(self) -> None:  # noqa: N802
        if urlsplit(self.path).path != API_PATH:
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found."})
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"ok": False, "error": "Expected application/json."},
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_BODY_BYTES:
            self._send_json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Invalid request size."}
            )
            return
        try:
            incoming = _validate_state(json.loads(self.rfile.read(length)))
            with STATE_LOCK:
                current = _read_state()
                if incoming["revision"] != current["revision"]:
                    self._send_json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": "The tracker changed in another tab. Reload before saving.",
                        },
                    )
                    return
                incoming["revision"] += 1
                _write_state(incoming)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(error)})
            return
        self._send_json(HTTPStatus.OK, {"ok": True, "state": incoming})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--no-open", action="store_true", help="Do not open the tracker in a browser."
    )
    args = parser.parse_args()
    address = ("127.0.0.1", args.port)
    url = f"http://127.0.0.1:{args.port}/tracker/"

    with ThreadingHTTPServer(address, TrackerHandler) as server:
        print(f"Tracker running at {url}")
        print("Keep this window open; press Control-C to stop.")
        if not args.no_open:
            threading.Timer(0.35, webbrowser.open, args=(url,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nTracker stopped.")


if __name__ == "__main__":
    main()
