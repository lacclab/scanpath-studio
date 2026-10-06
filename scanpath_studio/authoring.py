"""Pure helpers for hand-authored scanpath documents and edits (VIZ-33)."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

AUTHORING_SCHEMA = 2
DEFAULT_LAYOUT = {
    "canvas_width": 1200,
    "margin": 70,
    "character_width": 13,
    "word_height": 32,
    "line_height": 58,
}
EVENT_COLUMNS = [
    "fixation_id",
    "order_in_trial",
    "word_id",
    "x",
    "y",
    "duration_ms",
]


@dataclass(frozen=True)
class AuthoringDocument:
    """Portable source text, layout settings, and stable fixation events."""

    text: str
    events: pd.DataFrame
    layout: dict[str, int]
    schema: int = AUTHORING_SCHEMA


def layout_text(
    text: str,
    *,
    canvas_width: int = 1200,
    margin: int = 70,
    character_width: int = 13,
    word_height: int = 32,
    line_height: int = 58,
) -> pd.DataFrame:
    """Lay text into deterministic boxes while preserving explicit line breaks.

    Source lines are handled independently. Long lines wrap at ``canvas_width``;
    explicit blank lines still consume a line, so ``line_idx`` mirrors the text a
    user typed instead of collapsing all whitespace into one paragraph.
    """
    rows: list[dict[str, Any]] = []
    x, y, line = margin, margin, 0
    word_index = 1
    source_lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for source_index, source_line in enumerate(source_lines):
        if source_index:
            x, y, line = margin, y + line_height, line + 1
        for token in re.findall(r"\S+", source_line):
            width = max(character_width * len(token), character_width * 2)
            if x > margin and x + width > canvas_width - margin:
                x, y, line = margin, y + line_height, line + 1
            rows.append(
                {
                    "participant_id": "author",
                    "trial_id": "authored-1",
                    "text_id": "authored-text",
                    "word_id": float(word_index),
                    "text": token,
                    "line_idx": float(line),
                    # Canonical word geometry is box top-left + width/height.
                    "x": float(x),
                    "y": float(y),
                    "width": float(width),
                    "height": float(word_height),
                }
            )
            word_index += 1
            x += width + character_width
    return pd.DataFrame(
        rows,
        columns=[
            "participant_id",
            "trial_id",
            "text_id",
            "word_id",
            "text",
            "line_idx",
            "x",
            "y",
            "width",
            "height",
        ],
    )


def layout_problems(
    words: pd.DataFrame, *, canvas_width: int, margin: int
) -> list[str]:
    """Describe geometry that cannot fit inside the configured horizontal bounds."""
    if words.empty:
        return []
    overflow = words[
        (words["x"] < margin) | (words["x"] + words["width"] > canvas_width - margin)
    ]
    if overflow.empty:
        return []
    ids = ", ".join(str(int(value)) for value in overflow["word_id"].head(8))
    suffix = f" (+{len(overflow) - 8} more)" if len(overflow) > 8 else ""
    return [f"Too wide for the canvas: word {ids}{suffix}."]


def default_events(words: pd.DataFrame) -> pd.DataFrame:
    """Return one stable, centered fixation per word as the authoring seed."""
    if words.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    ids = pd.Series(range(1, len(words) + 1), dtype="int64")
    return pd.DataFrame(
        {
            "fixation_id": ids,
            "order_in_trial": ids,
            "word_id": words["word_id"].astype(int).reset_index(drop=True),
            "x": (words["x"] + words["width"] / 2).reset_index(drop=True),
            "y": (words["y"] + words["height"] / 2).reset_index(drop=True),
            "duration_ms": 220,
        },
        columns=EVENT_COLUMNS,
    )


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_int(value: Any) -> int | None:
    number = _number(value)
    if number is None or number <= 0 or not number.is_integer():
        return None
    return int(number)


def event_target_word(event: Mapping[str, Any]) -> int | None:
    """Return an optional target word; spatial X/Y remain independently valid."""
    return _positive_int(event.get("word_id"))


def normalize_event_table(events: pd.DataFrame | None) -> pd.DataFrame:
    """Migrate/edit an event table into the stable schema-2 column contract."""
    frame = pd.DataFrame() if events is None else pd.DataFrame(events).copy()
    for column in EVENT_COLUMNS:
        if column not in frame:
            frame[column] = None
    frame = frame[EVENT_COLUMNS].reset_index(drop=True)

    used_ids = [
        value for value in (_positive_int(v) for v in frame["fixation_id"]) if value
    ]
    next_id = max(used_ids, default=0) + 1
    used_orders = [
        value for value in (_positive_int(v) for v in frame["order_in_trial"]) if value
    ]
    next_order = max(used_orders, default=0) + 1
    for index in frame.index:
        if _positive_int(frame.at[index, "fixation_id"]) is None:
            frame.at[index, "fixation_id"] = next_id
            next_id += 1
        if _positive_int(frame.at[index, "order_in_trial"]) is None:
            frame.at[index, "order_in_trial"] = next_order
            next_order += 1
    return frame


def _is_scalar_cell(value: Any) -> bool:
    return value is None or (
        isinstance(value, (str, int, float)) and not isinstance(value, bool)
    )


def event_records_frame(records: Any) -> pd.DataFrame:
    """Build the normalized event table from untrusted JSON records.

    ``records`` comes from a link or a file, so its shape is checked before
    pandas sees it: a list of objects, each naming at least one event column,
    with plain number/text/null values. Anything else raises ``ValueError``
    with a reason, rather than a ``TypeError`` from deep inside pandas.
    """
    if not isinstance(records, list):
        raise ValueError("Authored fixations must be a list of objects.")
    for number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Authored fixation {number} is not an object.")
        if not any(column in record for column in EVENT_COLUMNS):
            raise ValueError(
                f"Authored fixation {number} has none of: {', '.join(EVENT_COLUMNS)}."
            )
        bad = sorted(
            str(key)
            for key in EVENT_COLUMNS
            if key in record and not _is_scalar_cell(record[key])
        )
        if bad:
            raise ValueError(
                f"Authored fixation {number} has a non-scalar {', '.join(bad)}."
            )
    frame, _ = reconcile_event_table(pd.DataFrame(records).reset_index(drop=True))
    return frame


def event_problems(words: pd.DataFrame, events: pd.DataFrame | None) -> list[str]:
    """Return actionable structural problems without silently renumbering rows."""
    frame = normalize_event_table(events)
    problems: list[str] = []
    ids = [_positive_int(value) for value in frame["fixation_id"]]
    orders = [_positive_int(value) for value in frame["order_in_trial"]]
    duplicate_ids = sorted({value for value in ids if value and ids.count(value) > 1})
    duplicate_orders = sorted(
        {value for value in orders if value and orders.count(value) > 1}
    )
    if duplicate_ids:
        problems.append(
            "Fixation id must be unique; duplicate: "
            + ", ".join(str(value) for value in duplicate_ids)
            + "."
        )
    if duplicate_orders:
        problems.append(
            "Order must be unique; duplicate: "
            + ", ".join(str(value) for value in duplicate_orders)
            + "."
        )
    unusable = unusable_event_rows(words, frame)
    if unusable:
        listed = ", ".join(str(number) for number in unusable[:10])
        suffix = f" (+{len(unusable) - 10} more)" if len(unusable) > 10 else ""
        problems.append(
            f"Not drawn — no X/Y and no valid target word: row {listed}{suffix}."
        )
    return problems


def _structural_problems(events: pd.DataFrame) -> list[str]:
    """Problems that make stable id/order reconciliation ambiguous."""
    return [
        problem
        for problem in event_problems(pd.DataFrame(), events)
        if problem.startswith(("Fixation id", "Order"))
    ]


def reconcile_event_table(
    events: pd.DataFrame | None, selected_fixation_id: int | None = None
) -> tuple[pd.DataFrame, int | None]:
    """Normalize table edits and preserve selection by stable fixation id."""
    frame = normalize_event_table(events)
    problems = _structural_problems(frame)
    if problems:
        raise ValueError(" ".join(problems))
    ids = {_positive_int(value) for value in frame["fixation_id"]}
    selected = selected_fixation_id if selected_fixation_id in ids else None
    return frame, selected


def apply_authoring_event(
    events: pd.DataFrame | None,
    event: Mapping[str, Any],
    *,
    selected_fixation_id: int | None = None,
) -> tuple[pd.DataFrame, int | None]:
    """Apply one compact canvas event keyed by stable ``fixation_id``."""
    frame, selected = reconcile_event_table(events, selected_fixation_id)
    action = str(event.get("type", ""))
    fixation_id = _positive_int(event.get("fixation_id"))
    if action == "add":
        x, y = _number(event.get("x")), _number(event.get("y"))
        if x is None or y is None:
            raise ValueError("A new fixation needs finite X and Y coordinates.")
        existing_ids = [_positive_int(value) or 0 for value in frame["fixation_id"]]
        existing_orders = [
            _positive_int(value) or 0 for value in frame["order_in_trial"]
        ]
        fixation_id = max(existing_ids, default=0) + 1
        frame.loc[len(frame)] = {
            "fixation_id": fixation_id,
            "order_in_trial": max(existing_orders, default=0) + 1,
            "word_id": None,
            "x": x,
            "y": y,
            "duration_ms": 220,
        }
        selected = fixation_id
    elif action in {"move", "update"}:
        if fixation_id is None:
            raise ValueError("The canvas edit has no valid fixation id.")
        matches = frame.index[
            frame["fixation_id"].map(_positive_int).eq(fixation_id)
        ].tolist()
        if not matches:
            raise ValueError(f"Fixation {fixation_id} no longer exists.")
        allowed = (
            {"x", "y"}
            if action == "move"
            else {
                "x",
                "y",
                "word_id",
                "duration_ms",
                "order_in_trial",
            }
        )
        for field in allowed:
            if field in event:
                frame.at[matches[0], field] = event[field]
        selected = fixation_id
    elif action == "delete":
        if fixation_id is not None:
            frame = frame[
                ~frame["fixation_id"].map(_positive_int).eq(fixation_id)
            ].reset_index(drop=True)
        selected = None if selected == fixation_id else selected
    elif action == "select":
        selected = fixation_id
    else:
        raise ValueError(f"Unknown authoring event: {action or '(blank)'}.")
    return reconcile_event_table(frame, selected)


def _word_key(text: Any) -> str:
    """A word as a target names it: letters and digits, case folded — so a
    punctuation or capitalisation fix leaves the target where it was."""
    return "".join(char for char in str(text).casefold() if char.isalnum())


def _target_keys(words: pd.DataFrame) -> dict[int, str]:
    if words.empty:
        return {}
    return {
        int(word_id): _word_key(text)
        for word_id, text in zip(words["word_id"], words["text"], strict=True)
    }


def stale_target_words(
    old_words: pd.DataFrame, new_words: pd.DataFrame, events: pd.DataFrame | None
) -> dict[int, tuple[int, str]]:
    """The fixations whose target word a text edit removed or replaced, as
    ``{fixation_id: (word_id, the word it named)}``.

    Editing the stimulus keeps every authored fixation as it is — X/Y, order,
    duration and id. Only the optional target word can go out of date: its id
    may no longer exist, or now name a different word. Those are reported, not
    changed; a punctuation or capitalisation fix to the word is not a change.
    :func:`unresolved_targets` says which are still out of date later on.
    """
    if events is None or events.empty:
        return {}
    before, after = _target_keys(old_words), _target_keys(new_words)
    stale: dict[int, tuple[int, str]] = {}
    for event in normalize_event_table(events).to_dict("records"):
        word_id = event_target_word(event)
        fixation_id = _positive_int(event.get("fixation_id"))
        if word_id is None or fixation_id is None or word_id not in before:
            continue
        if after.get(word_id) != before[word_id]:
            stale[fixation_id] = (word_id, before[word_id])
    return stale


def unresolved_targets(
    stale: Mapping[int, tuple[int, str]], words: pd.DataFrame, events: pd.DataFrame
) -> dict[int, int]:
    """``{fixation_id: word_id}`` for the entries of :func:`stale_target_words`
    that are still out of date: the fixation exists, still targets that word id,
    and the text there is still not the word it named. Changing or clearing the
    target, deleting the fixation or undoing the text edit resolves one."""
    if not stale or events is None or events.empty:
        return {}
    current = _target_keys(words)
    targets = {
        _positive_int(event.get("fixation_id")): event_target_word(event)
        for event in normalize_event_table(events).to_dict("records")
    }
    return {
        fixation_id: word_id
        for fixation_id, (word_id, named) in stale.items()
        if targets.get(fixation_id) == word_id and current.get(word_id) != named
    }


def destructive_change(before: pd.DataFrame | None, after: pd.DataFrame | None) -> bool:
    """Whether going from ``before`` to ``after`` lost authored work: a fixation
    removed, or one that is still there moved, retimed, reordered or retargeted.

    Adding a fixation loses nothing, so it is not one. This is what decides when
    the authoring screen keeps the previous draft for **Restore previous draft**.
    """
    old = normalize_event_table(before)
    new = normalize_event_table(after)
    if old.empty:
        return False

    def keyed(frame: pd.DataFrame) -> dict[int, tuple]:
        rows = {}
        for event in frame.to_dict("records"):
            fixation_id = _positive_int(event.get("fixation_id"))
            rows[fixation_id] = (
                _number(event.get("x")),
                _number(event.get("y")),
                _number(event.get("duration_ms")),
                _positive_int(event.get("order_in_trial")),
                event_target_word(event),
            )
        return rows

    old_rows, new_rows = keyed(old), keyed(new)
    return any(new_rows.get(key) != value for key, value in old_rows.items())


def unusable_event_rows(words: pd.DataFrame, events: pd.DataFrame) -> list[int]:
    """Return rows that have neither usable X/Y nor a valid word fallback."""
    if events is None or events.empty:
        return []
    valid_words = (
        set(words["word_id"].astype(int))
        if not words.empty and "word_id" in words
        else set()
    )
    unusable: list[int] = []
    for number, event in enumerate(events.to_dict("records"), start=1):
        has_xy = (
            _number(event.get("x")) is not None and _number(event.get("y")) is not None
        )
        if not has_xy and event_target_word(event) not in valid_words:
            unusable.append(number)
    return unusable


def authored_fixations(words: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Normalize authored events into the ordinary canonical fixation schema."""
    columns = [
        "participant_id",
        "trial_id",
        "text_id",
        "x",
        "y",
        "duration_ms",
        "timestamp_ms",
        "fixation_id",
        "word_id",
        "order_in_trial",
    ]
    if events is None or events.empty:
        return pd.DataFrame(columns=columns)
    frame, _ = reconcile_event_table(events)
    centers = pd.DataFrame(columns=["x", "y"])
    if not words.empty:
        centers = words.set_index(words["word_id"].astype(int))[
            ["x", "y", "width", "height"]
        ].copy()
        centers["x"] = centers["x"] + centers["width"] / 2
        centers["y"] = centers["y"] + centers["height"] / 2

    frame = frame.assign(
        _order=frame["order_in_trial"].map(_positive_int),
        _row=range(len(frame)),
    ).sort_values(["_order", "_row"], kind="stable")
    rows: list[dict[str, Any]] = []
    timestamp = 0.0
    for event in frame.to_dict("records"):
        word_id = event_target_word(event)
        x, y = _number(event.get("x")), _number(event.get("y"))
        if (x is None or y is None) and word_id in centers.index:
            x, y = float(centers.loc[word_id, "x"]), float(centers.loc[word_id, "y"])
        if x is None or y is None:
            continue
        duration = _number(event.get("duration_ms"))
        duration = duration if duration is not None and duration > 0 else 220.0
        order = _positive_int(event.get("order_in_trial"))
        fixation_id = _positive_int(event.get("fixation_id"))
        rows.append(
            {
                "participant_id": "author",
                "trial_id": "authored-1",
                "text_id": "authored-text",
                "x": x,
                "y": y,
                "duration_ms": duration,
                "timestamp_ms": timestamp,
                "fixation_id": float(fixation_id),
                "word_id": float(word_id) if word_id in centers.index else float("nan"),
                "order_in_trial": int(order),
            }
        )
        timestamp += duration
    return pd.DataFrame(rows, columns=columns)


def _json_records(events: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in normalize_event_table(events).to_dict("records"):
        records.append(
            {
                key: None
                if value is None or (isinstance(value, float) and math.isnan(value))
                else value
                for key, value in row.items()
            }
        )
    return records


def authoring_json(
    text: str,
    events: pd.DataFrame,
    *,
    layout: Mapping[str, int] | None = None,
) -> str:
    """Serialize a schema-2 source document for portable save/restore."""
    layout_value = {**DEFAULT_LAYOUT, **dict(layout or {})}
    return json.dumps(
        {
            "schema": AUTHORING_SCHEMA,
            "text": text,
            "layout": layout_value,
            "fixations": _json_records(events),
        },
        indent=2,
    )


#: Schema 1 or 2 is accepted; the user is told only what the file is not.
_NOT_AUTHORING = "That file isn't an authoring file saved from this editor."


def parse_authoring_document(payload: str) -> AuthoringDocument:
    """Restore schema 2 or migrate a VIZ-20 schema-1 authoring document."""
    try:
        value = json.loads(payload)
    except ValueError:
        value = None
    if not isinstance(value, dict):
        raise ValueError(_NOT_AUTHORING)
    schema = value.get("schema")
    if schema not in {1, AUTHORING_SCHEMA} or not isinstance(value.get("text"), str):
        raise ValueError(_NOT_AUTHORING)
    events = value.get("fixations", [])
    if not isinstance(events, list):
        raise ValueError("The authoring file's fixations must be a list.")
    frame = event_records_frame(events)
    layout = value.get("layout", {}) if schema == AUTHORING_SCHEMA else {}
    if not isinstance(layout, dict):
        raise ValueError("The authoring file's layout must be an object.")
    unknown = sorted(set(layout) - set(DEFAULT_LAYOUT))
    if unknown:
        raise ValueError(f"Unknown authoring layout option: {', '.join(unknown)}.")
    try:
        normalized_layout = {
            key: int({**DEFAULT_LAYOUT, **layout}[key]) for key in DEFAULT_LAYOUT
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("Authoring layout values must be whole numbers.") from exc
    return AuthoringDocument(value["text"], frame, normalized_layout)
