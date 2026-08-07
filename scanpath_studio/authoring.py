"""Pure helpers for the hand-authored scanpath source (VIZ-20)."""

from __future__ import annotations

import json
import re

import pandas as pd


def layout_text(
    text: str,
    *,
    canvas_width: int = 1200,
    margin: int = 70,
    character_width: int = 13,
    word_height: int = 32,
    line_height: int = 58,
) -> pd.DataFrame:
    """Lay plain text into deterministic word boxes on a reading canvas."""
    tokens = re.findall(r"\S+", str(text or ""))
    rows = []
    x, y, line = margin, margin, 0
    for index, token in enumerate(tokens, start=1):
        width = max(character_width * len(token), character_width * 2)
        if x > margin and x + width > canvas_width - margin:
            x, y, line = margin, y + line_height, line + 1
        rows.append(
            {
                "participant_id": "author",
                "trial_id": "authored-1",
                "text_id": "authored-text",
                "word_id": float(index),
                "text": token,
                "line_idx": float(line),
                # Canonical word geometry is box top-left + width/height.
                "x": float(x),
                "y": float(y),
                "width": float(width),
                "height": float(word_height),
            }
        )
        x += width + character_width
    return pd.DataFrame(rows)


def default_events(words: pd.DataFrame) -> pd.DataFrame:
    """One editable fixation per word, suitable as an authoring starting point."""
    if words.empty:
        return pd.DataFrame(columns=["word_id", "x", "y", "duration_ms"])
    return pd.DataFrame(
        {
            "word_id": words["word_id"].astype(int),
            "x": words["x"] + words["width"] / 2,
            "y": words["y"] + words["height"] / 2,
            "duration_ms": 220,
        }
    )


def event_target_word(event: dict) -> int | None:
    """The word a row targets, or ``None`` when it names no usable word."""
    try:
        return int(float(event.get("word_id")))
    except (TypeError, ValueError):
        return None


def unusable_event_rows(words: pd.DataFrame, events: pd.DataFrame) -> list[int]:
    """1-based row numbers that :func:`authored_fixations` will drop (BUG-19).

    A row whose **Target word** is blank or names a word the stimulus does not
    have produces no fixation at all. Dropping it is right — there is nowhere to
    put it — but doing so silently reads as "my edit didn't take", so the editor
    surfaces these rows instead. Same predicate as the builder below, so the two
    can never disagree about which rows survive.
    """
    if words.empty or events is None or events.empty:
        return []
    valid = set(words["word_id"].astype(int))
    return [
        number
        for number, event in enumerate(events.to_dict("records"), start=1)
        if event_target_word(event) not in valid
    ]


def authored_fixations(words: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Normalize editable author events into the standard fixation schema."""
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
    if words.empty or events is None or events.empty:
        return pd.DataFrame(columns=columns)
    centers = words.set_index(words["word_id"].astype(int))[
        ["x", "y", "width", "height"]
    ].copy()
    centers["x"] = centers["x"] + centers["width"] / 2
    centers["y"] = centers["y"] + centers["height"] / 2
    rows = []
    timestamp = 0.0
    for order, event in enumerate(events.to_dict("records"), start=1):
        word_id = event_target_word(event)
        if word_id is None or word_id not in centers.index:
            continue
        duration = pd.to_numeric(event.get("duration_ms"), errors="coerce")
        duration = float(duration) if pd.notna(duration) and duration > 0 else 220.0
        x = pd.to_numeric(event.get("x"), errors="coerce")
        y = pd.to_numeric(event.get("y"), errors="coerce")
        rows.append(
            {
                "participant_id": "author",
                "trial_id": "authored-1",
                "text_id": "authored-text",
                "x": float(x) if pd.notna(x) else float(centers.loc[word_id, "x"]),
                "y": float(y) if pd.notna(y) else float(centers.loc[word_id, "y"]),
                "duration_ms": duration,
                "timestamp_ms": timestamp,
                "fixation_id": float(order),
                "word_id": float(word_id),
                "order_in_trial": order,
            }
        )
        timestamp += duration
    return pd.DataFrame(rows, columns=columns)


def authoring_json(text: str, events: pd.DataFrame) -> str:
    """Portable source document used by the UI's save/restore controls."""
    return json.dumps(
        {"schema": 1, "text": text, "fixations": events.to_dict("records")},
        indent=2,
    )


def parse_authoring_json(payload: str) -> tuple[str, pd.DataFrame]:
    """Restore and validate a VIZ-20 authoring document."""
    value = json.loads(payload)
    if value.get("schema") != 1 or not isinstance(value.get("text"), str):
        raise ValueError("Not a Scanpath Studio authoring file (schema 1).")
    events = value.get("fixations", [])
    if not isinstance(events, list):
        raise ValueError("The authoring file's fixations must be a list.")
    # A range index is required, not cosmetic: `st.data_editor(num_rows="dynamic")`
    # cannot add rows to a gap-indexed frame, and its edits then land on the wrong
    # rows (BUG-19).
    return value["text"], pd.DataFrame(events).reset_index(drop=True)
