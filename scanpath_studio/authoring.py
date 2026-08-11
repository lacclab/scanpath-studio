"""Pure helpers for hand-authored scanpath documents and edits (VIZ-33)."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional

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
    return [
        f"Word {ids}{suffix} is wider than the available canvas and extends past the right margin."
    ]


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


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_int(value: Any) -> Optional[int]:
    number = _number(value)
    if number is None or number <= 0 or not number.is_integer():
        return None
    return int(number)


def event_target_word(event: Mapping[str, Any]) -> int | None:
    """Return an optional target word; spatial X/Y remain independently valid."""
    return _positive_int(event.get("word_id"))


def normalize_event_table(events: Optional[pd.DataFrame]) -> pd.DataFrame:
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


def event_problems(words: pd.DataFrame, events: Optional[pd.DataFrame]) -> list[str]:
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
            f"Row {listed}{suffix} has neither finite X/Y coordinates nor a valid target word."
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
    events: Optional[pd.DataFrame], selected_fixation_id: Optional[int] = None
) -> tuple[pd.DataFrame, Optional[int]]:
    """Normalize table edits and preserve selection by stable fixation id."""
    frame = normalize_event_table(events)
    problems = _structural_problems(frame)
    if problems:
        raise ValueError(" ".join(problems))
    ids = {_positive_int(value) for value in frame["fixation_id"]}
    selected = selected_fixation_id if selected_fixation_id in ids else None
    return frame, selected


def apply_authoring_event(
    events: Optional[pd.DataFrame],
    event: Mapping[str, Any],
    *,
    selected_fixation_id: Optional[int] = None,
) -> tuple[pd.DataFrame, Optional[int]]:
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
    layout: Optional[Mapping[str, int]] = None,
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


def parse_authoring_document(payload: str) -> AuthoringDocument:
    """Restore schema 2 or migrate a VIZ-20 schema-1 authoring document."""
    value = json.loads(payload)
    schema = value.get("schema")
    if schema not in {1, AUTHORING_SCHEMA} or not isinstance(value.get("text"), str):
        raise ValueError("Not a Scanpath Studio authoring file (schema 1 or 2).")
    events = value.get("fixations", [])
    if not isinstance(events, list):
        raise ValueError("The authoring file's fixations must be a list.")
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
    frame, _ = reconcile_event_table(pd.DataFrame(events).reset_index(drop=True))
    return AuthoringDocument(value["text"], frame, normalized_layout)


def parse_authoring_json(payload: str) -> tuple[str, pd.DataFrame]:
    """Backward-compatible two-value wrapper around :func:`parse_authoring_document`."""
    document = parse_authoring_document(payload)
    return document.text, document.events
