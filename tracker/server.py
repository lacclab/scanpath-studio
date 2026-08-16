"""Serve the improvements tracker and persist its editable task overrides."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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
#: Machine-local, git-ignored (ENG-39). Holds the two things that must *not* be
#: shared: the save counter — which changes on every save and so conflicted on
#: every parallel pull — and which of the people in `data.js` is at this
#: keyboard. Neither means anything in another clone.
LOCAL_FILE = TRACKER_DIR / ".local.json"
API_PATH = "/tracker/api/state"
WHOAMI_PATH = "/tracker/api/whoami"
MAX_BODY_BYTES = 2 * 1024 * 1024
STATE_VERSION = 3
STATUSES = {
    "Backlog",
    "Planned",
    "In progress",
    "On hold",
    "Review",
    "Closed",
}
PRIORITIES = {"High", "Normal", "Low"}
GROUP_PREFIXES = {
    "UX & Interaction": "UX",
    "Compare mode": "CMP",
    "Visualization & display": "VIZ",
    "Datasets & ingestion": "DATA",
    "Performance": "PERF",
    "Analysis & corpus views": "AN",
    "Preprocessing — eyekit parity": "PRE",
    "Export": "EXP",
    "Validation": "VAL",
    "Bugs": "BUG",
    "Engineering": "ENG",
}
EDIT_FIELDS = (
    "status",
    "priority",
    "owner",
    "implementationBrief",
    "archived",
    "updated",
)
# The write-up is structured, one array of markdown lines per section, so a
# section cannot be silently dropped, reordered, or hidden inside prose. Only
# `request` is required; the rest appear once there is work behind the item.
WRITE_UP_FIELDS = ("statusNote", "request", "whatWasDone", "whatsLeft", "background")
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
    "request",
}
CREATED_OPTIONAL_FIELDS = {"decisions", *WRITE_UP_FIELDS} - CREATED_FIELDS
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
STATE_LOCK = threading.Lock()


def _known_item_ids() -> set[str]:
    return set(
        re.findall(
            r'"id"\s*:\s*"([A-Z]{2,4}-\d+[a-z]?)"',
            DATA_FILE.read_text(encoding="utf-8"),
        )
    )


def _known_groups() -> set[str]:
    return set(
        re.findall(r'"group"\s*:\s*"([^"]+)"', DATA_FILE.read_text(encoding="utf-8"))
    )


def _known_people() -> list[str]:
    """The names an item may be claimed by, from ``TRACKER.people`` in data.js.

    A fixed list rather than free text (ENG-39): it is the only shape a *Mine* /
    *Unassigned* filter can be honest about, and a typo'd owner is then a
    rejected save instead of a third person who does not exist.
    """
    match = re.search(
        r'"people"\s*:\s*\[([^\]]*)\]', DATA_FILE.read_text(encoding="utf-8")
    )
    return re.findall(r'"([^"]+)"', match.group(1)) if match else []


def _validate_created_item(value: Any, known_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not CREATED_FIELDS <= set(value):
        raise ValueError("Invalid created tracker item.")
    if set(value) - CREATED_FIELDS - CREATED_OPTIONAL_FIELDS:
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
    if GROUP_PREFIXES.get(value["group"]) != prefix:
        raise ValueError(f"Invalid prefix for {value['group']}.")
    if not isinstance(value["implementationBrief"], str):
        raise ValueError(f"Invalid implementation brief for {item_id}.")
    if not isinstance(value["archived"], bool):
        raise ValueError(f"Invalid archive value for {item_id}.")
    if not isinstance(value["added"], str) or not DATE_RE.fullmatch(value["added"]):
        raise ValueError(f"Invalid creation date for {item_id}.")
    for field in ("decisions", *WRITE_UP_FIELDS):
        lines = value.get(field)
        if lines is None:
            continue
        if not isinstance(lines, list) or not all(
            isinstance(line, str) for line in lines
        ):
            raise ValueError(f"Invalid {field} for {item_id}.")
        if not lines:
            raise ValueError(f"Empty {field} for {item_id} — omit the field instead.")
    if not isinstance(value["sub"], str) or not isinstance(value["subgroup"], str):
        raise ValueError(f"Invalid grouping for {item_id}.")
    return {
        field: value[field]
        for field in (*CREATED_FIELDS, *CREATED_OPTIONAL_FIELDS)
        if field in value
    }


def _validate_state(value: Any) -> dict[str, Any]:
    # `revision` is accepted but never stored: it is a machine-local save
    # counter that lives in `.local.json` now, and version 2 files (and every
    # request from the page) still carry it inline.
    expected = {"version", "items", "createdItems"}
    if not isinstance(value, dict) or not expected <= set(value):
        raise ValueError("Invalid tracker state.")
    if set(value) - expected - {"revision"}:
        raise ValueError("Invalid tracker state.")
    if value["version"] not in (2, STATE_VERSION):
        raise ValueError("Unsupported tracker state version.")
    if "revision" in value and (
        not isinstance(value["revision"], int) or value["revision"] < 0
    ):
        raise ValueError("Invalid tracker state revision.")
    if not isinstance(value["items"], dict):
        raise ValueError("Tracker items must be a JSON object.")
    if not isinstance(value["createdItems"], list):
        raise ValueError("Created tracker items must be an array.")

    people = _known_people()
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
            raise ValueError(f"Unsupported field for {item_id}: {min(extra)}")
        if "status" in edit and edit["status"] not in STATUSES:
            raise ValueError(f"Invalid status for {item_id}.")
        if "priority" in edit and edit["priority"] not in PRIORITIES:
            raise ValueError(f"Invalid priority for {item_id}.")
        if "owner" in edit and edit["owner"] not in ("", *people):
            raise ValueError(f"Invalid owner for {item_id}.")
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
        "version": STATE_VERSION,
        "items": clean,
        "createdItems": created_items,
    }


def _read_state() -> dict[str, Any]:
    return _validate_state(json.loads(STATE_FILE.read_text(encoding="utf-8")))


def _read_local() -> dict[str, Any]:
    try:
        value = json.loads(LOCAL_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_local(local: dict[str, Any]) -> None:
    LOCAL_FILE.write_text(
        f"{json.dumps(local, indent=2, ensure_ascii=False)}\n", encoding="utf-8"
    )


def _read_revision() -> int:
    revision = _read_local().get("revision")
    return revision if isinstance(revision, int) and revision >= 0 else 0


def _bump_revision() -> int:
    local = _read_local()
    local["revision"] = _read_revision() + 1
    _write_local(local)
    return local["revision"]


def _git_name() -> str:
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=APP_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def _whoami() -> dict[str, Any]:
    """Who is at this keyboard, resolved once and remembered locally.

    An explicit choice wins; otherwise `git config user.name` is matched
    token-wise against the people in `data.js`, which covers the ordinary case
    ("Omer Shubi" → "Shubi") without anyone configuring anything. No match just
    means unclaimed work stays unclaimed until someone picks a name.
    """
    people = _known_people()
    stored = _read_local().get("person")
    if isinstance(stored, str) and stored in people:
        return {"person": stored, "people": people}
    tokens = {token.casefold() for token in _git_name().split()}
    guess = next((p for p in people if p.casefold() in tokens), "")
    return {"person": guess, "people": people}


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

    #: Files that are edited while the tracker is open, so a cached copy is
    #: always wrong. `data.js` matters as much as `state.json`: it carries the
    #: item catalogue, and without an explicit header browsers fall back to
    #: *heuristic* freshness (a fraction of the time since `Last-Modified`) and
    #: can serve a stale copy without revalidating — newly added items then just
    #: don't appear, with nothing to indicate why.
    _NO_STORE_PATHS = ("/tracker/state.json", "/tracker/data.js")

    def end_headers(self) -> None:
        path = urlsplit(self.path).path
        if path.endswith(self._NO_STORE_PATHS) or path in (API_PATH, WHOAMI_PATH):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == API_PATH:
            state = {**_read_state(), "revision": _read_revision()}
            self._send_json(HTTPStatus.OK, {"ok": True, "state": state})
            return
        if path == WHOAMI_PATH:
            self._send_json(HTTPStatus.OK, {"ok": True, **_whoami()})
            return
        super().do_GET()

    def _read_body(self) -> Any:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Expected application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_BODY_BYTES:
            raise ValueError("Invalid request size.")
        return json.loads(self.rfile.read(length))

    def do_PUT(self) -> None:
        path = urlsplit(self.path).path
        if path not in (API_PATH, WHOAMI_PATH):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found."})
            return
        try:
            body = self._read_body()
            if path == WHOAMI_PATH:
                self._put_whoami(body)
                return
            incoming = _validate_state(body)
            with STATE_LOCK:
                if body.get("revision") != _read_revision():
                    self._send_json(
                        HTTPStatus.CONFLICT,
                        {
                            "ok": False,
                            "error": "The tracker changed in another tab. Reload before saving.",
                        },
                    )
                    return
                _write_state(incoming)
                incoming["revision"] = _bump_revision()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(error)})
            return
        self._send_json(HTTPStatus.OK, {"ok": True, "state": incoming})

    def _put_whoami(self, body: Any) -> None:
        person = body.get("person") if isinstance(body, dict) else None
        if person is not None and (
            not isinstance(person, str) or person not in ("", *_known_people())
        ):
            raise ValueError("Unknown person.")
        with STATE_LOCK:
            local = _read_local()
            local["person"] = person or ""
            _write_local(local)
        self._send_json(HTTPStatus.OK, {"ok": True, **_whoami()})


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
