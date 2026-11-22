"""Trace one fixation to the parsed input cells used to draw it."""

from __future__ import annotations

import json
from collections.abc import Mapping

import numpy as np
import pandas as pd

from .column_names import MAPPED, ColumnNames

SOURCE_ROW = "_fixation_input_row"
SOURCE_FILE = "_fixation_input_file"
MERGED_ROWS = "_fixation_contributors"
FILE_SPANS = "scanpath_studio.input_files"
ROLES = {
    "duration_ms": "duration",
    "timestamp_ms": "timestamp",
    "x": "x",
    "y": "y",
    "word_id": "word_id",
}
INPUT_CELLS = {column: f"_fixation_input_{role}" for column, role in ROLES.items()}
PRIVATE_COLUMNS = frozenset(
    {SOURCE_ROW, SOURCE_FILE, MERGED_ROWS, *INPUT_CELLS.values()}
)


def without_source_cells(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    """Keep input cells inside the inspector, outside figures and public tables."""
    if frame is None:
        return None
    private = PRIVATE_COLUMNS.intersection(frame.columns)
    return frame.drop(columns=sorted(private)) if private else frame


def record_rows(target, source, keep, *, remap):
    """Record the one-based parsed row before identity filtering or sorting."""
    if remap:
        for key in (SOURCE_ROW, SOURCE_FILE, MERGED_ROWS):
            if key in source:
                target[key] = source[key].iloc[keep]
        return
    spans = source.attrs.get(FILE_SPANS, ())
    if spans and sum(count for _, count in spans) == len(source):
        # Expand the categorical codes, so each filename is stored only once.
        names = pd.Categorical([name for name, _ in spans])
        target[SOURCE_FILE] = names.repeat([n for _, n in spans])[keep]
        rows = np.concatenate([np.arange(1, n + 1) for _, n in spans])
        target[SOURCE_ROW] = rows[keep]
    else:
        target[SOURCE_ROW] = keep + 1


def record_cells(target, source, schema, *, remap):
    """Retain only cells that normalization might change or replace."""
    from .data import time_unit_ms

    for column, role in ROLES.items():
        original = INPUT_CELLS[column]
        mapped = schema.get(role)
        if not mapped or mapped not in source:
            continue
        if remap and mapped == column:
            if original in source:
                target[original] = source[original]
            continue
        values = source[mapped]
        # A remap can point at another canonical, already transformed column.
        # Its earlier raw cells, when present, name the actual source.
        if remap and mapped in INPUT_CELLS and INPUT_CELLS[mapped] in source:
            target[original] = source[INPUT_CELLS[mapped]]
        elif (
            not pd.api.types.is_numeric_dtype(values)
            or values.hasnans
            or (role in ("duration", "timestamp") and time_unit_ms(mapped) != 1)
        ):
            target[original] = values.astype("string")


def _value(value) -> str:
    return "Blank" if pd.isna(value) else str(value)


def source_location(row) -> dict:
    """The source record, with a file only when the reader recorded its name."""
    where = row.get(SOURCE_ROW)
    file = row.get(SOURCE_FILE)
    return {
        "File": str(file) if pd.notna(file) else None,
        "Row": int(where) if pd.notna(where) else None,
    }


def merge_sources(frame, target, donor) -> None:
    """Preserve chained contributions while the preprocessing table still has every row."""
    if SOURCE_ROW not in frame:
        return
    if MERGED_ROWS not in frame:
        frame[MERGED_ROWS] = pd.Series(pd.NA, index=frame.index, dtype="string")
    refs = []
    for index in (target, donor):
        existing = frame.at[index, MERGED_ROWS]
        if pd.notna(existing):
            refs.extend(json.loads(existing))
        else:
            refs.append(source_location(frame.loc[index]))
    frame.at[target, MERGED_ROWS] = json.dumps(refs, ensure_ascii=False)


def explain(
    row: pd.Series,
    words: pd.DataFrame,
    names: ColumnNames,
    *,
    displayed: Mapping | None = None,
) -> dict:
    """The parsed source of one point, its normalized values and its word assignment."""
    from .data import FIX_WORD_ID_MAPPED, time_unit_ms
    from .measures import assign_fixations_to_words

    where = source_location(row)
    rows = row.get(MERGED_ROWS)
    contributors = json.loads(rows) if isinstance(rows, str) else []
    fields = []
    for column, role in ROLES.items():
        entry = names.source(column)
        name = entry.display if entry and entry.sources else None
        cell = INPUT_CELLS[column]
        normalized = row.get(column)
        if cell in row:
            raw = _value(row[cell])
        elif name and where["Row"] is not None and entry.kind == MAPPED:
            previous = {"duration_ms": "original_duration_ms", "y": "y_original"}.get(
                column, column
            )
            raw = _value(row.get(previous, normalized))
        else:
            raw = "Unavailable" if name else "—"
        unit = ""
        if role in ("duration", "timestamp") and name:
            unit = {1000: "s", 1: "ms", 0.001: "µs", 0.000001: "ns"}[time_unit_ms(name)]
        elif role in ("x", "y") and name:
            unit = "px"
        fields.append(
            {
                "Field": column,
                "Input column": name or "—",
                "Input value": raw,
                "Input unit": unit,
                "Current value": _value(normalized),
            }
        )
    assigned = assign_fixations_to_words(row.to_frame().T, words).iloc[0].get("word_id")
    mapped = row.get(FIX_WORD_ID_MAPPED)
    if pd.notna(mapped):
        if mapped:
            method = (
                "Mapped word ID"
                if pd.notna(assigned)
                else "Mapped word ID is blank or unmatched"
            )
        else:
            method = (
                "Contained by word box"
                if pd.notna(assigned)
                else "Outside the word boxes"
            )
    else:
        method = "Assignment source unavailable for this reading"
    return {
        "location": where,
        "contributors": contributors,
        "fields": fields,
        "word": _value(assigned),
        "assignment": method,
        "displayed": dict(displayed or {}),
    }
