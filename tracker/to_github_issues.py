"""Migrate the live tracker items to GitHub Issues (ENG-32).

One-shot script, kept in the repo as the record of how the move was made.
It reads the tracker's two files exactly the way `index.html` does — the
catalogue in `data.js`, overridden per item by `state.json` — renders every
**live** item's structured write-up into an issue body, and creates the issues
with `gh`. Closed items are never imported: `data.js` stays as the archive.

Two properties matter more than anything else here:

* **Stable IDs survive.** The tracker's IDs are referenced throughout the docs,
  the plans, and the git history, so each issue is titled ``[VIZ-37] …`` and the
  ID→issue map is written to `migrated.json` for the frozen tracker to link
  against. GitHub's own numbering is treated as an implementation detail.
* **The approval gate survives.** It is a house rule, not a GitHub default, so
  the six statuses become `status:*` labels and *closing* an issue is the
  sign-off — an implemented item lands in `status:review`, open, with the review
  ask in its **Waiting on you** checklist.

Usage::

    python3 tracker/to_github_issues.py --dry-run        # print the bodies
    python3 tracker/to_github_issues.py --labels-only    # create labels
    python3 tracker/to_github_issues.py                  # create the issues
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

TRACKER_DIR = Path(__file__).resolve().parent
DATA_FILE = TRACKER_DIR / "data.js"
STATE_FILE = TRACKER_DIR / "state.json"
#: ID → issue number, written after a real run and read by `index.html` so the
#: frozen tracker can point each live item at the issue that replaced it.
MAP_FILE = TRACKER_DIR / "migrated.json"
REPO = "lacclab/scanpath-studio"
OWNER = REPO.split("/")[0]
#: The kanban view over the issues. The `status:*` labels stay the source of
#: truth — they need only the `repo` scope, and `gh issue list --label
#: status:in-progress` is what the docs tell agents to use — so the board's
#: Status column is a *mirror*, pushed by `--sync-board`. Nothing reads it back.
BOARD_TITLE = "Scanpath Studio"
BOARD_STATUS_FIELD = "Status"

#: `Parked` is retired wording for `On hold` (and `Done`/`Pending approval` for
#: the archived items). Normalizing on the way out means the retired vocabulary
#: does not get a second life as a GitHub label.
STATUS_ALIASES = {"Parked": "On hold", "Pending approval": "Review", "Done": "Closed"}
#: The board's Status column — the source of truth for where an item is.
#: GitHub has no issue-level status beyond open/closed, so this is a project
#: single-select field rather than a label. `Closed` is the sixth state and is
#: the issue being closed, which is the user's sign-off.
BOARD_STATUSES = {
    "Backlog": ("GRAY", "Wanted, not scheduled"),
    "Planned": ("BLUE", "Scheduled, not started"),
    "In progress": ("PURPLE", "Someone is working on it"),
    "On hold": ("ORANGE", "Deliberately deferred"),
    "Review": ("YELLOW", "Implemented — awaiting sign-off"),
}
#: The board's Priority column, replacing the old `priority:*` labels. The
#: tracker only ever had High / Normal / Low; Normal reads as Medium here, and
#: Urgent exists for work that should jump its status queue.
BOARD_PRIORITIES = {
    "Urgent": ("RED", "Drop what you are doing"),
    "High": ("ORANGE", "Before the rest of its status"),
    "Medium": ("GRAY", "The default"),
    "Low": ("BLUE", "Nice to have, no hurry"),
}
PRIORITY_FROM_TRACKER = {"High": "High", "Normal": "Medium", "Low": "Low"}
#: GitHub's org-level issue types — a native field, so it beats a label. Most
#: areas map cleanly; the exceptions are items whose *shape* differs from their
#: area's norm (a capability filed under Engineering, a chore under Datasets).
ISSUE_TYPE_BY_AREA = {
    "Bugs": "Bug",
    "Validation": "Task",
    "Performance": "Task",
    "Engineering": "Task",
}
ISSUE_TYPE_OVERRIDES = {
    "ENG-17": "Feature",  # hosted online mode is a capability, not a chore
    "DATA-15": "Task",  # replacing a bundled file is corpus maintenance
    "UX-56": "Task",  # a design decision to make, not a thing to build
}
DEFAULT_ISSUE_TYPE = "Feature"
GROUP_LABELS = {
    "UX & Interaction": ("area:ux", "c4b5fd"),
    "Compare mode": ("area:compare", "a7f3d0"),
    "Visualization & display": ("area:viz", "bfdbfe"),
    "Datasets & ingestion": ("area:data", "fde68a"),
    "Performance": ("area:perf", "fecaca"),
    "Analysis & corpus views": ("area:analysis", "ddd6fe"),
    "Preprocessing — eyekit parity": ("area:preprocessing", "99f6e4"),
    "Export": ("area:export", "fbcfe8"),
    "Validation": ("area:validation", "e9d5ff"),
    "Bugs": ("area:bug", "ef4444"),
    "Engineering": ("area:engineering", "d1d5db"),
}
#: The only flag left as a label: it has no native or project-field equivalent,
#: and it wants to be queryable from `gh issue list` without a project call.
EXTRA_LABELS = {
    "waiting-on-you": ("fbbf24", "Has an open call or review only the owner can make"),
}
#: Labels the structured fields replaced. Deleted from the repo by
#: `--labels-only` so two vocabularies cannot disagree.
RETIRED_LABELS = (
    "status:backlog",
    "status:planned",
    "status:in-progress",
    "status:on-hold",
    "status:review",
    "priority:high",
    "priority:low",
)
#: The people in `data.js` → their GitHub logins, for `--assignee`. A name with
#: no mapping is still recorded in the body; it just is not assigned.
GITHUB_LOGINS = {"Shubi": "OmerShubi", "Maya": "Maya705"}
SECTIONS = (
    ("request", "Request"),
    ("whatWasDone", "What was done"),
    ("whatsLeft", "What's left"),
    ("background", "Background"),
)
# `(?! \(#)` keeps the rewrite idempotent: a write-up that already spells a
# reference as `BUG-32 (#111)` must not pick up a second `(#111)`.
ID_RE = re.compile(r"#?\b([A-Z]{2,4}-\d+[a-z]?)\b(?! \(#)")
#: The tracker links code as `[plots.py](scanpath_studio/plots.py:339)` — a
#: repo-relative path plus an optional `:line`. Both halves are conventions of
#: the local page and render as a dead link in an issue, so they are rewritten
#: to real blob URLs on the way out.
LINK_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)\s]+?)(?::(\d+))?\)")
BLOB = f"https://github.com/{REPO}/blob/main"


def load_items() -> list[dict[str, Any]]:
    """Every tracker item, with `state.json`'s overrides already applied."""
    source = DATA_FILE.read_text(encoding="utf-8")
    start = source.index("=", source.index("window.TRACKER")) + 1
    data = json.loads(source[start:].strip().rstrip(";").strip())
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    edits = state["items"]
    items = [*data["items"], *state["createdItems"]]
    for item in items:
        edit = edits.get(item["id"], {})
        item.update({field: edit[field] for field in edit})
        item["status"] = STATUS_ALIASES.get(item["status"], item["status"])
    return items


def live_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The items worth migrating, ordered the way the tracker orders them."""
    # Active work first, so the low issue numbers land on what is being worked
    # on rather than on the backlog.
    order = ("In progress", "Review", "Planned", "Backlog", "On hold")
    rank = {name: i for i, name in enumerate(order)}
    live = [item for item in items if not item.get("archived")]
    return sorted(live, key=lambda item: (rank.get(item["status"], 9), item["id"]))


def link_ids(text: str, numbers: dict[str, int]) -> str:
    """Turn a reference to a *migrated* item into a GitHub autolink.

    References to archived items are left as plain text on purpose: they still
    resolve in the frozen tracker, and rewriting them to `#N` would point at an
    unrelated issue.
    """

    def replace(match: re.Match[str]) -> str:
        item_id = match.group(1)
        number = numbers.get(item_id)
        return f"{item_id} (#{number})" if number else match.group(0)

    return ID_RE.sub(replace, text)


def absolutize_links(text: str) -> str:
    """Repo-relative code links → blob URLs, `:line` → GitHub's `#L` anchor."""

    def replace(match: re.Match[str]) -> str:
        path, line = match.group(1), match.group(2)
        if not (TRACKER_DIR.parent / path).exists():
            return match.group(0)
        anchor = f"#L{line}" if line else ""
        return f"]({BLOB}/{path}{anchor})"

    return LINK_RE.sub(replace, text)


def render_body(item: dict[str, Any], numbers: dict[str, int]) -> str:
    """The issue body for one item — its write-up, in the house shape."""
    lines: list[str] = []
    if item.get("statusNote"):
        # Some notes were written as a markdown quote already, back when the
        # lede *was* a leading `>` block; don't quote them twice.
        note = [
            line.removeprefix("> ").removeprefix(">") for line in item["statusNote"]
        ]
        lines += [f"> {line}" if line else ">" for line in note] + [""]
    if item.get("decisions"):
        lines += ["### ⚖ Waiting on you", ""]
        lines += [f"- [ ] {call}" for call in item["decisions"]]
        lines += [
            "",
            "<sub>Every open call — a design decision, or a review to run. Tick one off"
            " in a comment saying what you decided; the implementer records the call"
            " under **Background**.</sub>",
            "",
        ]
    for field, heading in SECTIONS:
        if item.get(field):
            lines += [f"## {heading}", "", *item[field], ""]
    if item.get("implementationBrief"):
        lines += [
            "## Instructions for implementation",
            "",
            item["implementationBrief"],
            "",
        ]
    owner = item.get("owner") or "unclaimed"
    body = absolutize_links(link_ids("\n".join(lines).strip(), numbers))
    # The footer is appended *after* linking so the item's own ID is not
    # rewritten into a link back to the issue you are already reading.
    return (
        f"{body}\n\n---\n\n"
        f"<sub>Migrated from the in-repo tracker (ENG-32). Tracker ID **{item['id']}**"
        f" · added {item.get('added') or 'unknown'} · owner {owner}. Closed items and"
        " the full history stay in"
        f" [`tracker/data.js`]({BLOB}/tracker/data.js).</sub>\n"
    )


def labels_for(item: dict[str, Any]) -> list[str]:
    """The labels an issue keeps: its area, and whether it is blocking the user.

    Status, priority and type are structured fields now — the board's Status and
    Priority columns and GitHub's native issue type — so they are deliberately
    not mirrored here. Two vocabularies for one fact is how they drift.
    """
    labels = [GROUP_LABELS[item["group"]][0]]
    if item.get("decisions"):
        labels.append("waiting-on-you")
    return labels


def issue_type_for(item: dict[str, Any]) -> str:
    override = ISSUE_TYPE_OVERRIDES.get(item["id"])
    if override:
        return override
    return ISSUE_TYPE_BY_AREA.get(item["group"], DEFAULT_ISSUE_TYPE)


#: Transient network failures, which a run of ~100 API calls hits often enough
#: to matter — and every operation here is idempotent, so a retry is safe.
RETRYABLE = ("i/o timeout", "connection reset", "TLS handshake", "502 Bad Gateway")


def run_gh(args: list[str], attempts: int = 3) -> str:
    for attempt in range(1, attempts + 1):
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=False, timeout=120
        )
        if not result.returncode:
            return result.stdout.strip()
        error = result.stderr.strip() or f"gh {' '.join(args)} failed"
        if attempt == attempts or not any(hint in error for hint in RETRYABLE):
            raise RuntimeError(error)
        print(f"  retrying after: {error.splitlines()[0][:90]}")
        time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def ensure_labels() -> None:
    """Create the area labels, and delete the ones the structured fields replaced."""
    for name in RETIRED_LABELS:
        try:
            run_gh(["label", "delete", name, "--repo", REPO, "--yes"])
            print(f"label · removed {name}")
        except RuntimeError:
            pass  # already gone, which is the desired end state
    wanted: dict[str, tuple[str, str]] = {}
    for group, (name, color) in GROUP_LABELS.items():
        wanted[name] = (color, group)
    wanted.update(
        {name: (color, blurb) for name, (color, blurb) in EXTRA_LABELS.items()}
    )
    for name, (color, description) in wanted.items():
        run_gh(
            [
                "label",
                "create",
                name,
                "--repo",
                REPO,
                "--color",
                color,
                "--description",
                description,
                "--force",
            ]
        )
        print(f"label · {name}")


def create_issues(items: list[dict[str, Any]]) -> dict[str, int]:
    numbers: dict[str, int] = {}
    for item in items:
        args = [
            "issue",
            "create",
            "--repo",
            REPO,
            "--title",
            f"[{item['id']}] {item['title']}",
            "--body",
            render_body(item, numbers),
        ]
        for label in labels_for(item):
            args += ["--label", label]
        login = GITHUB_LOGINS.get(item.get("owner", ""))
        if login:
            args += ["--assignee", login]
        url = run_gh(args)
        numbers[item["id"]] = int(url.rstrip("/").rsplit("/", 1)[-1])
        print(f"{item['id']:<9} → {url}")
    return numbers


def update_issues(items: list[dict[str, Any]], numbers: dict[str, int]) -> None:
    """Re-render items that already have an issue, in place.

    The archive is still what the bodies are generated from, so correcting a
    write-up there and re-running is how an issue body gets fixed. Without this,
    `--only` on a migrated item would raise a *second* issue for it.
    """
    for item in items:
        number = numbers[item["id"]]
        args = [
            "issue",
            "edit",
            str(number),
            "--repo",
            REPO,
            "--title",
            f"[{item['id']}] {item['title']}",
            "--body",
            render_body(item, numbers),
        ]
        wanted = labels_for(item)
        for label in wanted:
            args += ["--add-label", label]
        # An item that changed status keeps its old `status:*` label otherwise —
        # `gh issue edit` adds, it does not replace, so a decision that has since
        # been answered would keep its `waiting-on-you` badge forever.
        for label in ("waiting-on-you",):
            if label not in wanted:
                args += ["--remove-label", label]
        run_gh(args)
        print(f"{item['id']:<9} → updated #{number}")


def backfill_links(items: list[dict[str, Any]], numbers: dict[str, int]) -> None:
    """Re-render every body now that all the issue numbers are known.

    The first pass can only link *backwards*, so an item referring to one
    created after it would keep a bare ID. Cheap to just rewrite them all.
    """
    for item in items:
        body = render_body(item, numbers)
        run_gh(
            ["issue", "edit", str(numbers[item["id"]]), "--repo", REPO, "--body", body]
        )
    print(f"cross-references resolved across {len(items)} issues")


def run_gh_json(args: list[str]) -> Any:
    return json.loads(run_gh([*args, "--format", "json"]) or "null")


def _board_number() -> int:
    """The project's number, creating the project the first time.

    `gh project` needs the `project` token scope, which the plain `repo` scope
    used everywhere else does not include — so this is the one code path that
    fails with an auth error until someone runs `gh auth refresh -s project`.
    """
    projects = run_gh_json(["project", "list", "--owner", OWNER]).get("projects", [])
    for project in projects:
        if project["title"] == BOARD_TITLE:
            return int(project["number"])
    created = run_gh_json(
        ["project", "create", "--owner", OWNER, "--title", BOARD_TITLE]
    )
    number = int(created["number"])
    run_gh(["project", "link", str(number), "--owner", OWNER, "--repo", REPO])
    print(f"created project #{number} ({BOARD_TITLE})")
    return number


def _option_literals(options: dict[str, tuple[str, str]]) -> str:
    """The `singleSelectOptions` list, inlined into the mutation.

    `gh api graphql -F name=value` sends every variable as a *string*, so a list
    of objects arrives as one JSON blob and the server rejects it. Writing the
    literals into the query sidesteps the variable plumbing entirely; `color` is
    a GraphQL enum, so it is the one value that must not be quoted.
    """
    return ", ".join(
        f"{{name: {json.dumps(label)}, color: {colour},"
        f" description: {json.dumps(blurb)}}}"
        for label, (colour, blurb) in options.items()
    )


def _select_field(
    number: int, name: str, options: dict[str, tuple[str, str]]
) -> dict[str, Any]:
    """A project single-select field whose options are exactly ``options``.

    A new project ships a Status field reading Todo / In Progress / Done, which
    cannot express *On hold* or the review gate — and it is a built-in, so it
    cannot be deleted and recreated (`Only custom fields can be deleted`). The
    GraphQL mutation rewrites the options in place instead, which works for the
    built-in and for fields this creates. Options not passed are dropped, so the
    field ends up matching the tracker's vocabulary one-to-one.
    """
    fields = run_gh_json(["project", "field-list", str(number), "--owner", OWNER])
    field = next((f for f in fields.get("fields", []) if f["name"] == name), None)
    if field is None:
        run_gh(
            [
                "project",
                "field-create",
                str(number),
                "--owner",
                OWNER,
                "--name",
                name,
                "--data-type",
                "SINGLE_SELECT",
                "--single-select-options",
                ",".join(options),
            ]
        )
        return _select_field(number, name, options)

    current = {option["name"] for option in field.get("options", [])}
    if current == set(options):
        return {
            "id": field["id"],
            "options": {o["name"]: o["id"] for o in field["options"]},
        }
    mutation = f"""
    mutation {{
      updateProjectV2Field(input: {{
        fieldId: {json.dumps(field["id"])},
        singleSelectOptions: [{_option_literals(options)}]
      }}) {{
        projectV2Field {{
          ... on ProjectV2SingleSelectField {{ id options {{ id name }} }}
        }}
      }}
    }}
    """
    result = json.loads(run_gh(["api", "graphql", "-f", f"query={mutation}"]))
    updated = result["data"]["updateProjectV2Field"]["projectV2Field"]
    print(f"board · {name} options → {', '.join(options)}")
    return {
        "id": updated["id"],
        "options": {o["name"]: o["id"] for o in updated["options"]},
    }


def sync_board(items: list[dict[str, Any]], numbers: dict[str, int]) -> None:
    """Put every issue on the board with its Status, Priority and issue type set.

    One-way, and it is the *tracker archive* that is being read from — this is
    the migration's own tool, not a two-way sync. Day to day, a status is changed
    on the board itself; nothing here reads it back.
    """
    board = _board_number()
    project_id = _project_id(board)
    status = _select_field(board, "Status", BOARD_STATUSES)
    priority = _select_field(board, "Priority", BOARD_PRIORITIES)
    existing = {
        entry.get("content", {}).get("number"): entry["id"]
        for entry in run_gh_json(
            ["project", "item-list", str(board), "--owner", OWNER, "--limit", "500"]
        ).get("items", [])
        if entry.get("content")
    }
    for item in items:
        issue = numbers[item["id"]]
        item_id = existing.get(issue)
        if item_id is None:
            added = run_gh_json(
                [
                    "project",
                    "item-add",
                    str(board),
                    "--owner",
                    OWNER,
                    "--url",
                    f"https://github.com/{REPO}/issues/{issue}",
                ]
            )
            item_id = added["id"]
        rank = PRIORITY_FROM_TRACKER[item.get("priority", "Normal")]
        for field, option in (
            (status, item["status"]),
            (priority, rank),
        ):
            run_gh(
                [
                    "project",
                    "item-edit",
                    "--id",
                    item_id,
                    "--project-id",
                    project_id,
                    "--field-id",
                    field["id"],
                    "--single-select-option-id",
                    field["options"][option],
                ]
            )
        kind = issue_type_for(item)
        # `gh` has no flag for the native issue type; REST does.
        run_gh(
            ["api", "-X", "PATCH", f"repos/{REPO}/issues/{issue}", "-f", f"type={kind}"]
        )
        print(f"{item['id']:<9} → #{issue} · {kind} · {item['status']} · {rank}")


def _project_id(number: int) -> str:
    project = run_gh_json(["project", "view", str(number), "--owner", OWNER])
    return str(project["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print, create nothing.")
    parser.add_argument(
        "--labels-only", action="store_true", help="Create labels only."
    )
    parser.add_argument("--only", help="Act on a single tracker ID (for a retry).")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Re-render items that already have an issue instead of creating new ones.",
    )
    parser.add_argument(
        "--sync-board",
        action="store_true",
        help="Mirror the status labels onto the Project board (needs the project scope).",
    )
    args = parser.parse_args()

    items = live_items(load_items())
    if args.only:
        items = [item for item in items if item["id"] == args.only]
        if not items:
            raise SystemExit(f"No live item {args.only}.")

    if args.dry_run:
        # Placeholder numbers, so the cross-reference rewriting is visible.
        preview = {item["id"]: index + 1 for index, item in enumerate(items)}
        for item in items:
            print(f"\n{'=' * 72}\n[{item['id']}] {item['title']}")
            print(f"labels: {', '.join(labels_for(item))}")
            print(f"assignee: {GITHUB_LOGINS.get(item.get('owner', '')) or '—'}")
            print(f"{'-' * 72}\n{render_body(item, preview)}")
        print(f"\n{len(items)} live items would be migrated.")
        return

    ensure_labels()
    if args.labels_only:
        return

    known = (
        json.loads(MAP_FILE.read_text(encoding="utf-8")) if MAP_FILE.exists() else {}
    )
    if args.sync_board:
        missing = [item["id"] for item in items if item["id"] not in known]
        if missing:
            raise SystemExit(
                f"--sync-board needs an existing issue; missing: {missing}"
            )
        sync_board(items, known)
        return

    if args.update:
        missing = [item["id"] for item in items if item["id"] not in known]
        if missing:
            raise SystemExit(f"--update needs an existing issue; missing: {missing}")
        update_issues(items, known)
        return

    already = [item["id"] for item in items if item["id"] in known]
    if already:
        raise SystemExit(
            f"already migrated: {already}. Re-run with --update to rewrite the body."
        )
    numbers = create_issues(items)
    backfill_links(items, numbers)
    MAP_FILE.write_text(
        f"{json.dumps({**known, **numbers}, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    print(f"wrote {MAP_FILE.relative_to(TRACKER_DIR.parent)}")


if __name__ == "__main__":
    main()
