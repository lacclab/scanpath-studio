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


def test_validate_state_accepts_an_owner_from_the_people_list() -> None:
    people = SERVER._known_people()
    assert people, "tracker/data.js must declare `people` for Claim to work (ENG-39)."

    state = SERVER._validate_state(
        {
            "version": SERVER.STATE_VERSION,
            "items": {"CMP-7": {"owner": people[0]}},
            "createdItems": [],
        }
    )

    assert state["items"]["CMP-7"]["owner"] == people[0]


def test_validate_state_rejects_an_unknown_owner() -> None:
    """A typo'd owner is a rejected save, not a third person who doesn't exist."""
    with pytest.raises(ValueError, match="Invalid owner"):
        SERVER._validate_state(
            {
                "version": SERVER.STATE_VERSION,
                "items": {"CMP-7": {"owner": "Nobody"}},
                "createdItems": [],
            }
        )


def test_validated_state_never_carries_the_revision_counter() -> None:
    """``revision`` is machine-local now (ENG-39), so it never reaches state.json.

    It changed on every save, which made the git-tracked file conflict on every
    parallel pull even when two people touched different items. The two-tabs
    protection it provides is per-machine, so it lives in a gitignored
    ``tracker/.local.json`` — and a version 2 file that still has it inline is
    read, then written back without it.
    """
    state = SERVER._validate_state(
        {"version": 2, "revision": 349, "items": {}, "createdItems": []}
    )

    assert "revision" not in state
    assert state["version"] == SERVER.STATE_VERSION


def test_state_file_is_free_of_the_revision_counter() -> None:
    state = json.loads((TRACKER_DIR / "state.json").read_text(encoding="utf-8"))

    assert "revision" not in state, (
        "tracker/state.json still carries `revision` — it belongs in the "
        "gitignored tracker/.local.json (ENG-39)."
    )


def test_local_state_file_is_gitignored() -> None:
    ignored = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")

    assert "tracker/.local.json" in ignored


def test_every_status_offers_a_directed_transition() -> None:
    """Each status names the moves it actually makes, as buttons (ENG-38)."""
    source = (TRACKER_DIR / "index.html").read_text(encoding="utf-8")
    block = source.split("const TRANSITIONS = {", 1)[1].split("};", 1)[0]

    for status in SERVER.STATUSES:
        assert f'"{status}": [' in block, f"{status} has no directed transitions."
    for expected in ('["Closed", "Approve & close"]', '["In progress", "Send back"]'):
        assert expected in block, f"Review is missing {expected}."


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


#: A task as the page's "New task" form builds it.
# Numbers far above anything `data.js` will reach: these stand for a task the
# user just created, so they must not collide with a real item (UX-99 did).
CREATED_TASK = {
    "id": "CMP-9099",
    "prefix": "CMP",
    "num": 9099,
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


def test_validate_state_accepts_created_task() -> None:
    state = SERVER._validate_state(
        {"version": 2, "revision": 0, "items": {}, "createdItems": [dict(CREATED_TASK)]}
    )

    assert state["createdItems"][0]["id"] == "CMP-9099"


def test_a_created_task_can_be_claimed() -> None:
    """Claiming a UI-created task must not poison every later save (ENG-42).

    The page keeps one object per created item, shared between `ITEMS` and
    `STATE.createdItems`, and `stageEditor` assigns the edited fields onto it —
    so a claim stamps `owner` there. `owner` was not in the created-item
    contract, so the whole payload was rejected and *every* save from that page
    failed, for every item, with "Save failed".
    """
    people = SERVER._known_people()
    item = {**CREATED_TASK, "owner": people[0]}

    state = SERVER._validate_state({"version": 3, "items": {}, "createdItems": [item]})

    assert state["createdItems"][0]["owner"] == people[0]


def test_a_created_task_rejects_an_owner_who_does_not_exist() -> None:
    item = {**CREATED_TASK, "owner": "Nobody"}

    with pytest.raises(ValueError, match="Invalid owner"):
        SERVER._validate_state({"version": 3, "items": {}, "createdItems": [item]})


def test_validate_state_rejects_group_prefix_mismatch() -> None:
    item = {
        "id": "UX-9099",
        "prefix": "UX",
        "num": 9099,
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
    state = {"version": SERVER.STATE_VERSION, "items": {}, "createdItems": []}

    SERVER._write_state(state)

    assert json.loads(state_file.read_text(encoding="utf-8")) == state


def test_revision_is_derived_from_the_state_file_not_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The concurrency token is a hash of `state.json`, kept nowhere (ENG-41)."""
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(SERVER, "TRACKER_DIR", tmp_path)
    monkeypatch.setattr(SERVER, "STATE_FILE", state_file)
    monkeypatch.setattr(SERVER, "LOCAL_FILE", tmp_path / ".local.json")

    assert SERVER._state_revision() == 0  # no file yet
    SERVER._write_state(
        {"version": SERVER.STATE_VERSION, "items": {}, "createdItems": []}
    )
    first = SERVER._state_revision()

    assert first > 0
    assert SERVER._state_revision() == first  # stable while the file is untouched
    assert not (tmp_path / ".local.json").exists()


def test_an_out_of_band_edit_moves_the_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An agent editing `state.json` by hand must invalidate an open page's token.

    This is the whole point of ENG-41: `CLAUDE.md` tells agents to edit
    `tracker/state.json` directly, and the old counter only moved when the API
    wrote. A page loaded before such an edit then PUT its stale copy straight
    over it and reported success.
    """
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(SERVER, "TRACKER_DIR", tmp_path)
    monkeypatch.setattr(SERVER, "STATE_FILE", state_file)
    SERVER._write_state(
        {"version": SERVER.STATE_VERSION, "items": {}, "createdItems": []}
    )
    before = SERVER._state_revision()

    state_file.write_text(
        json.dumps(
            {
                "version": SERVER.STATE_VERSION,
                "items": {"ENG-1": {"status": "Closed"}},
                "createdItems": [],
            }
        ),
        encoding="utf-8",
    )

    assert SERVER._state_revision() != before


def test_whoami_prefers_an_explicit_choice_over_the_git_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    people = SERVER._known_people()
    monkeypatch.setattr(SERVER, "LOCAL_FILE", tmp_path / ".local.json")
    monkeypatch.setattr(SERVER, "_git_name", lambda: people[0])

    assert SERVER._whoami() == {"person": people[0], "people": people}

    SERVER._write_local({"person": people[-1]})

    assert SERVER._whoami()["person"] == people[-1]


def test_whoami_matches_a_full_git_name_token_wise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "Omer Shubi" resolves to "Shubi" with nobody configuring anything."""
    people = SERVER._known_people()
    monkeypatch.setattr(SERVER, "LOCAL_FILE", tmp_path / ".local.json")
    monkeypatch.setattr(SERVER, "_git_name", lambda: f"Some {people[0].lower()}")

    assert SERVER._whoami()["person"] == people[0]


def test_whoami_is_empty_when_the_git_name_matches_nobody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(SERVER, "LOCAL_FILE", tmp_path / ".local.json")
    monkeypatch.setattr(SERVER, "_git_name", lambda: "Someone Else")

    assert SERVER._whoami()["person"] == ""
