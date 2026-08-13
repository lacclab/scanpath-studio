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


def test_every_item_belongs_to_a_declared_group() -> None:
    """An item whose ``group`` matches no declared group is invisible (ENG-29).

    ``tracker/index.html`` renders by iterating ``DATA.groups`` and filtering
    items into each one, so a typo'd or renamed group silently drops the item
    from the page — the file is valid, the server serves it, and it just isn't
    there. VIZ-30 shipped with ``"Visualization"`` instead of
    ``"Visualization & display"`` and vanished exactly this way.
    """
    catalog = _load_catalog()
    declared = {group["name"] for group in catalog["groups"]}
    orphans = sorted(
        f"{item['id']} -> {item['group']!r}"
        for item in catalog["items"]
        if item["group"] not in declared
    )
    assert not orphans, (
        "these items name a group that isn't in TRACKER.groups, so the tracker "
        f"page won't render them at all: {orphans}. Declared groups: {sorted(declared)}"
    )


def test_decision_callout_renders_numbered_list() -> None:
    source = (TRACKER_DIR / "index.html").read_text()

    assert '<ol>${decisions.map(d => `<li>${inline(d)}</li>`).join("")}</ol>' in source
    assert ".decisions ol" in source
    assert ".decisions ul" not in source


ALIASES = {
    "Pending approval": "Review",
    "Done": "Closed",
    "Dropped": "Closed",
    "Decided": "Closed",
    "Blocked": "On hold",
    "Parked": "On hold",
    "Partly done": "In progress",
}


def _open_items() -> list[dict]:
    """Every catalogue + UI-created item that is not archived or Closed."""
    catalog = _load_catalog()
    state = json.loads((TRACKER_DIR / "state.json").read_text())
    items = []
    for item in [*catalog["items"], *state.get("createdItems", [])]:
        edit = state.get("items", {}).get(item["id"], {})
        raw = edit.get("status", item["status"])
        if ALIASES.get(raw, raw) == "Closed" or edit.get("archived", item["archived"]):
            continue
        item = {**item, "status": ALIASES.get(raw, raw)}
        items.append(item)
    return items


def test_open_items_carry_the_structured_write_up() -> None:
    """Open items store the write-up as fields, not as bold leads in one blob.

    The four-paragraph shape used to live entirely inside ``body`` as
    ``**Request.**`` / ``**What was done.**`` prose leads, which agents dropped,
    reordered, or reworded often enough to be worth making structural. Each
    section is now its own array of markdown lines, so a missing section is a
    missing key and this test can see it. The archived catalogue keeps ``body``.
    """
    for item in _open_items():
        assert "body" not in item, (
            f"{item['id']} still uses the legacy `body` blob — split it into "
            f"{SERVER.WRITE_UP_FIELDS}."
        )
        assert item.get("request"), f"{item['id']} has no `request` section."
        for field in ("decisions", *SERVER.WRITE_UP_FIELDS):
            lines = item.get(field)
            if lines is None:
                continue
            assert isinstance(lines, list) and all(
                isinstance(line, str) for line in lines
            ), f"{item['id']}: `{field}` must be an array of markdown lines."
            assert lines, f"{item['id']}: `{field}` is empty — omit the field instead."


def test_implemented_items_say_what_was_done_and_what_is_left() -> None:
    """An item being worked on or awaiting review owes all four sections."""
    for item in _open_items():
        if item["status"] not in {"In progress", "Review"}:
            continue
        for field in ("whatWasDone", "whatsLeft", "background"):
            assert item.get(field), (
                f"{item['id']} is {item['status']} but has no `{field}` section."
            )


def test_write_up_sections_do_not_repeat_their_own_lead() -> None:
    """The label is the field name now; a leftover `**Request.**` is a double."""
    leads = ("**Request.", "**What was done.", "**What's left.", "**Background (")
    for item in _open_items():
        for field in SERVER.WRITE_UP_FIELDS:
            first = (item.get(field) or [""])[0]
            assert not first.startswith(leads), (
                f"{item['id']}: `{field}` repeats a bold lead — the tracker "
                "renders the section label itself."
            )


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
        "request": ["A new comparison task"],
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
        "request": ["Wrong group prefix"],
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
