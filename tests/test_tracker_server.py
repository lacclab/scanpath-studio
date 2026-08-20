from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_tracker_server():
    server_path = Path(__file__).parents[1] / "tracker" / "server.py"
    spec = importlib.util.spec_from_file_location("tracker_server", server_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SERVER = _load_tracker_server()
TRACKER_DIR = Path(__file__).parents[1] / "tracker"
#: The write-up sections, in render order. This used to live in `server.py`,
#: which validated them on every save; the tracker is a read-only archive since
#: ENG-32, so the shape is pinned here and nowhere else.
WRITE_UP_FIELDS = ("statusNote", "request", "whatWasDone", "whatsLeft", "background")


def _load_catalog() -> dict:
    source = (TRACKER_DIR / "data.js").read_text(encoding="utf-8")
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
    source = (TRACKER_DIR / "index.html").read_text(encoding="utf-8")

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
    state = json.loads((TRACKER_DIR / "state.json").read_text(encoding="utf-8"))
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
            f"{WRITE_UP_FIELDS}."
        )
        assert item.get("request"), f"{item['id']} has no `request` section."
        for field in ("decisions", *WRITE_UP_FIELDS):
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


def test_review_items_ask_for_the_review_in_the_waiting_box() -> None:
    """An item in ``Review`` is holding on the user, and must say so where the
    user looks (ENG-38 round 2).

    ``whatsLeft`` is the *developer's* remainder — on a finished item that is
    honestly "Nothing". The review itself is not developer work, so it lives in
    ``decisions``, which is the amber *Waiting on you* box, the ``⚖ N for you``
    badge, and the *Waiting on me* filter. Without this, an implemented item
    reads as finished and drops off the one list the user actually scans.
    """
    for item in _open_items():
        if item["status"] != "Review":
            continue
        assert item.get("decisions"), (
            f"{item['id']} is in Review but has no `decisions` entry — name the "
            "review ask there (which surfaces to click, which calls to second-guess) "
            "so it lands in the 'Waiting on me' filter."
        )


def test_whats_left_is_developer_work_not_a_message_to_the_user() -> None:
    """``whatsLeft`` addresses the developer; anything for the user is a decision."""
    addressed = ("your review", "you should look", "for you to review", "your call")
    for item in _open_items():
        text = " ".join(item.get("whatsLeft") or []).lower()
        found = [phrase for phrase in addressed if phrase in text]
        assert not found, (
            f"{item['id']}: `whatsLeft` addresses the user ({found[0]!r}). It holds "
            "the developer's remaining work only — move the ask to `decisions`."
        )


def test_write_up_sections_do_not_repeat_their_own_lead() -> None:
    """The label is the field name now; a leftover `**Request.**` is a double."""
    leads = ("**Request.", "**What was done.", "**What's left.", "**Background (")
    for item in _open_items():
        for field in WRITE_UP_FIELDS:
            first = (item.get(field) or [""])[0]
            assert not first.startswith(leads), (
                f"{item['id']}: `{field}` repeats a bold lead — the tracker "
                "renders the section label itself."
            )


def _migrated() -> dict[str, int]:
    return json.loads((TRACKER_DIR / "migrated.json").read_text(encoding="utf-8"))


def test_every_item_still_open_has_a_github_issue() -> None:
    """The migration is complete: nothing live is only in the tracker (ENG-32).

    The archive is allowed to hold open-looking statuses — those are the items
    as they stood the day they moved — but each one must point at the issue that
    replaced it, or it is work that exists in a frozen file and nowhere else.
    """
    migrated = _migrated()
    stranded = sorted(
        item["id"] for item in _open_items() if item["id"] not in migrated
    )

    assert not stranded, (
        f"these items are open in the tracker but have no GitHub issue: {stranded}. "
        "Raise them at https://github.com/lacclab/scanpath-studio/issues and add the "
        "number to tracker/migrated.json, or archive them."
    )


def test_migrated_ids_all_exist_in_the_catalogue() -> None:
    known = {item["id"] for item in _load_catalog()["items"]}
    known |= {
        item["id"]
        for item in json.loads(
            (TRACKER_DIR / "state.json").read_text(encoding="utf-8")
        ).get("createdItems", [])
    }
    unknown = sorted(set(_migrated()) - known)

    assert not unknown, (
        f"migrated.json names items that aren't in the tracker: {unknown}"
    )


def test_the_tracker_server_has_no_write_endpoint() -> None:
    """The archive is served, never written (ENG-32).

    `state.json` was edited through this server until the migration. Leaving a
    write path behind would let the frozen copy drift from the issues that
    replaced it, which is the one failure mode the freeze exists to prevent.
    """
    source = (TRACKER_DIR / "server.py").read_text(encoding="utf-8")

    assert not hasattr(SERVER, "_write_state")
    assert not hasattr(SERVER, "_validate_state")
    for banned in ("do_PUT", "do_POST", "do_DELETE"):
        assert banned not in source, f"tracker/server.py still defines {banned}."


def test_the_tracker_page_offers_no_editing() -> None:
    """Nothing on the page pretends to save, so nothing can fail to save."""
    source = (TRACKER_DIR / "index.html").read_text(encoding="utf-8")

    for banned in ('method: "PUT"', "saveState", "stageEditor", "newTaskForm"):
        assert banned not in source, f"tracker/index.html still has {banned}."
    assert "https://github.com/lacclab/scanpath-studio/issues" in source
