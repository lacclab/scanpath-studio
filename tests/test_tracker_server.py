from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_tracker_server():
    server_path = Path(__file__).parents[1] / "tracker" / "server.py"
    spec = importlib.util.spec_from_file_location("tracker_server", server_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SERVER = _load_tracker_server()
TRACKER_DIR = Path(__file__).parents[1] / "tracker"


def _load_catalog() -> dict:
    source = (TRACKER_DIR / "data.js").read_text()
    payload = source.split("window.TRACKER = ", 1)[1].strip().removesuffix(";")
    return json.loads(payload)


def test_open_catalog_items_follow_write_up_shape() -> None:
    catalog = _load_catalog()
    state = json.loads((TRACKER_DIR / "state.json").read_text())
    aliases = {
        "Pending approval": "Review",
        "Done": "Closed",
        "Dropped": "Closed",
        "Decided": "Closed",
        "Blocked": "On hold",
        "Parked": "On hold",
        "Partly done": "In progress",
    }
    order = ["Request.", "What was done.", "What's left.", "Background (technical)."]

    for item in [*catalog["items"], *state.get("createdItems", [])]:
        edit = state.get("items", {}).get(item["id"], {})
        status = aliases.get(
            edit.get("status", item["status"]), edit.get("status", item["status"])
        )
        if status == "Closed":
            continue

        labels = []
        for line in item["body"]:
            labels.extend(label for label in order if line.startswith(f"**{label}**"))

        assert labels and labels[0] == "Request.", item["id"]
        assert labels == sorted(labels, key=order.index), item["id"]
        assert len(labels) == len(set(labels)), item["id"]
        if status in {"In progress", "Review"}:
            assert labels == order, item["id"]


def test_validate_state_accepts_implementation_brief() -> None:
    state = SERVER._validate_state(
        {
            "version": 2,
            "revision": 3,
            "items": {
                "CMP-7": {
                    "status": "Planned",
                    "priority": "High",
                    "implementationBrief": "Use one shared colour scale.",
                    "archived": False,
                    "updated": "2026-08-03",
                }
            },
            "createdItems": [],
        }
    )

    assert (
        state["items"]["CMP-7"]["implementationBrief"] == "Use one shared colour scale."
    )


def test_validate_state_accepts_on_hold_status() -> None:
    state = SERVER._validate_state(
        {
            "version": 2,
            "revision": 0,
            "items": {"CMP-7": {"status": "On hold"}},
            "createdItems": [],
        }
    )

    assert state["items"]["CMP-7"]["status"] == "On hold"


@pytest.mark.parametrize(
    "change, message",
    [
        ({"UNKNOWN-1": {}}, "Unknown tracker item"),
        ({"CMP-7": {"status": "Partly done"}}, "Invalid status"),
        ({"CMP-7": {"priority": "Urgent"}}, "Invalid priority"),
        ({"CMP-7": {"privateField": True}}, "Unsupported field"),
    ],
)
def test_validate_state_rejects_invalid_changes(change: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        SERVER._validate_state(
            {"version": 2, "revision": 0, "items": change, "createdItems": []}
        )


def test_validate_state_accepts_created_task() -> None:
    item = {
        "id": "CMP-99",
        "prefix": "CMP",
        "num": 99,
        "sub": "",
        "title": "A new comparison task",
        "status": "Backlog",
        "priority": "Normal",
        "implementationBrief": "Keep the two views aligned.",
        "group": "Compare mode",
        "subgroup": "",
        "archived": False,
        "added": "2026-08-03",
        "body": ["**Request.** A new comparison task"],
    }

    state = SERVER._validate_state(
        {"version": 2, "revision": 0, "items": {}, "createdItems": [item]}
    )

    assert state["createdItems"][0]["id"] == "CMP-99"


def test_validate_state_rejects_group_prefix_mismatch() -> None:
    item = {
        "id": "UX-99",
        "prefix": "UX",
        "num": 99,
        "sub": "",
        "title": "Wrong group prefix",
        "status": "Backlog",
        "priority": "Normal",
        "implementationBrief": "",
        "group": "Compare mode",
        "subgroup": "",
        "archived": False,
        "added": "2026-08-03",
        "body": ["**Request.** Wrong group prefix"],
    }

    with pytest.raises(ValueError, match="Invalid prefix"):
        SERVER._validate_state(
            {"version": 2, "revision": 0, "items": {}, "createdItems": [item]}
        )


def test_write_state_is_valid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(SERVER, "TRACKER_DIR", tmp_path)
    monkeypatch.setattr(SERVER, "STATE_FILE", state_file)
    state = {"version": 2, "revision": 1, "items": {}, "createdItems": []}

    SERVER._write_state(state)

    assert json.loads(state_file.read_text()) == state
