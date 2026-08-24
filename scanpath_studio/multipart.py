"""Canonical identity and validation for trials made of ordered screens.

Legacy Scanpath Studio data identifies one coordinate space with
``(participant_id, trial_id)``.  Multipart trials retain that logical parent
identity and add ``screen_id`` plus a 1-based ``screen_index`` on every row.
This module is deliberately pandas-only so ingestion, measures, UI, API, CLI,
and export can share the exact same boundary rules without importing Streamlit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

PARENT_KEY = ("participant_id", "trial_id")
SCREEN_ID = "screen_id"
SCREEN_INDEX = "screen_index"
PART_KEY = (*PARENT_KEY, SCREEN_ID)
SCREEN_TIMESTAMP = "screen_timestamp_ms"
SCREEN_FIXATION_ID = "screen_fixation_id"
CANVAS_WIDTH = "canvas_width"
CANVAS_HEIGHT = "canvas_height"
PART_METADATA = (SCREEN_ID, SCREEN_INDEX, CANVAS_WIDTH, CANVAS_HEIGHT)


def has_screen_identity(frame: pd.DataFrame | None) -> bool:
    """Whether ``frame`` carries canonical screen identity."""
    return bool(frame is not None and SCREEN_ID in frame.columns)


def grouping_columns(frame: pd.DataFrame, *, include_word: bool = False) -> list[str]:
    """Identity columns for a scientific operation on ``frame``.

    Single-screen frames keep the historical parent key. Multipart frames add
    ``screen_id`` so assignment, saccades, runs, passes, and measures can never
    connect two coordinate spaces accidentally.
    """
    keys = [column for column in PARENT_KEY if column in frame.columns]
    if has_screen_identity(frame):
        keys.append(SCREEN_ID)
    if include_word and "word_id" in frame.columns:
        keys.append("word_id")
    return keys


def _parent_columns(frame: pd.DataFrame) -> list[str]:
    missing = [column for column in PARENT_KEY if column not in frame.columns]
    if missing:
        raise ValueError(
            "Multipart identity needs canonical parent columns: " + ", ".join(missing)
        )
    return list(PARENT_KEY)


def normalize_screen_identity(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize/validate screen columns, preserving legacy frame shape.

    ``screen_id`` alone is enough: order is derived from first appearance
    within each logical trial. ``screen_index`` alone is also accepted and its
    string value becomes the id. When both are supplied, the mapping must be
    one-to-one inside a parent. Canvas dimensions, when supplied, must be
    positive and constant within a screen.
    """
    has_id = SCREEN_ID in frame.columns
    has_index = SCREEN_INDEX in frame.columns
    if not has_id and not has_index:
        return frame

    parents = _parent_columns(frame)
    out = frame.copy()
    if not has_id:
        numeric_index = pd.to_numeric(out[SCREEN_INDEX], errors="coerce")
        if numeric_index.isna().any():
            raise ValueError("screen_index contains missing or non-numeric values.")
        out[SCREEN_ID] = numeric_index.astype(int).astype(str)
    else:
        # `stable_id`, not a plain `.astype(str)` — BUG-44's hazard applies here
        # too: a whole-number screen_id reads as float64 the moment any OTHER
        # row anywhere in that column is missing, so one report's `"1"` becomes
        # another's `"1.0"` and `validate_matching_parts` below rejects every
        # screen as an orphan even though both sides recorded the same one.
        # Imported locally — `data.py` imports from this module, so a
        # module-level import would cycle.
        from .data import stable_id

        # A missing/blank cell is tolerated exactly as `trial_id_series` (via
        # `stable_id`) already tolerates one in a trial id — no proactive
        # `isna()` check here either. Rejecting it outright meant a screen_id
        # column with a stray blank cell (the same dtype-coercion quirk
        # BUG-44 fixed for identity columns generally) failed the whole
        # mapping instead of just reading that one blank cell as "nan".
        out[SCREEN_ID] = stable_id(out[SCREEN_ID])

    if not has_index:
        distinct = out[parents + [SCREEN_ID]].drop_duplicates()
        distinct[SCREEN_INDEX] = distinct.groupby(parents, sort=False).cumcount() + 1
        out = out.merge(distinct, on=parents + [SCREEN_ID], how="left", sort=False)
    else:
        numeric_index = pd.to_numeric(out[SCREEN_INDEX], errors="coerce")
        if numeric_index.isna().any() or (numeric_index <= 0).any():
            raise ValueError("screen_index must contain positive integers.")
        if (numeric_index % 1 != 0).any():
            raise ValueError("screen_index must contain whole numbers.")
        out[SCREEN_INDEX] = numeric_index.astype(int)

    pairs = out[parents + [SCREEN_ID, SCREEN_INDEX]].drop_duplicates()
    if pairs.duplicated(parents + [SCREEN_ID], keep=False).any():
        raise ValueError("A screen_id maps to more than one screen_index in a trial.")
    if pairs.duplicated(parents + [SCREEN_INDEX], keep=False).any():
        raise ValueError("A screen_index maps to more than one screen_id in a trial.")

    for column in (CANVAS_WIDTH, CANVAS_HEIGHT):
        if column not in out.columns:
            continue
        values = pd.to_numeric(out[column], errors="coerce")
        if values.notna().any() and (values.dropna() <= 0).any():
            raise ValueError(f"{column} must be positive when supplied.")
        out[column] = values
        counts = out.groupby(list(PART_KEY), dropna=False)[column].nunique(dropna=True)
        if (counts > 1).any():
            raise ValueError(f"{column} conflicts within one screen.")
    return out


def part_catalog(*frames: pd.DataFrame | None) -> pd.DataFrame:
    """One ordered row per screen across ``frames``.

    Metadata conflicts between words and fixations are rejected rather than
    resolved with a silent ``first()``. Legacy data returns an empty catalogue.
    """
    rows: list[pd.DataFrame] = []
    metadata = [SCREEN_INDEX, CANVAS_WIDTH, CANVAS_HEIGHT, "text_id"]
    for frame in frames:
        if frame is None or frame.empty or not has_screen_identity(frame):
            continue
        normalized = normalize_screen_identity(frame)
        columns = [*PART_KEY, *(c for c in metadata if c in normalized.columns)]
        candidate = normalized[columns].drop_duplicates()
        for column in metadata:
            if column not in candidate.columns:
                candidate[column] = pd.NA
        rows.append(candidate[[*PART_KEY, *metadata]])
    if not rows:
        return pd.DataFrame(columns=[*PART_KEY, *metadata])

    combined = pd.concat(rows, ignore_index=True)
    for column in metadata:
        conflicts = combined.groupby(list(PART_KEY), dropna=False)[column].nunique(
            dropna=True
        )
        if (conflicts > 1).any():
            raise ValueError(f"Multipart metadata {column!r} conflicts across tables.")
    catalog = (
        combined.groupby(list(PART_KEY), as_index=False, dropna=False)
        .first()
        .sort_values([*PARENT_KEY, SCREEN_INDEX, SCREEN_ID], kind="stable")
        .reset_index(drop=True)
    )
    return catalog


def validate_matching_parts(words: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """Reject orphan screens when both normalized reports carry part identity."""
    if words.empty or fixations.empty:
        return
    if not has_screen_identity(words) and not has_screen_identity(fixations):
        return
    if has_screen_identity(words) != has_screen_identity(fixations):
        raise ValueError(
            "Multipart identity is present in only one report; map screen_id in "
            "both words and fixations, or omit it from both."
        )
    word_parts = set(map(tuple, words[list(PART_KEY)].drop_duplicates().to_numpy()))
    fixation_parts = set(
        map(tuple, fixations[list(PART_KEY)].drop_duplicates().to_numpy())
    )
    if word_parts != fixation_parts:
        missing_words = sorted(fixation_parts - word_parts)
        missing_fix = sorted(word_parts - fixation_parts)
        details = []
        if missing_words:
            details.append(f"no words for {missing_words[:3]}")
        if missing_fix:
            details.append(f"no fixations for {missing_fix[:3]}")
        raise ValueError(
            "Multipart reports contain orphan screens: " + "; ".join(details)
        )


def extract_part(
    frame: pd.DataFrame,
    participant_id: Any,
    trial_id: Any,
    screen_id: Any | None = None,
) -> pd.DataFrame:
    """Extract one parent trial or one screen without concatenating screens."""
    if frame is None or frame.empty:
        return frame
    mask = (frame["participant_id"].astype(str) == str(participant_id)) & (
        frame["trial_id"].astype(str) == str(trial_id)
    )
    if screen_id is not None:
        if SCREEN_ID not in frame.columns:
            raise ValueError("screen= was supplied for a single-screen dataset.")
        mask &= frame[SCREEN_ID].astype(str) == str(screen_id)
    return frame.loc[mask]


def _manifest_trials(manifest: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list:
    if isinstance(manifest, Mapping):
        trials = manifest.get("trials", manifest.get("multipart_trials", []))
    else:
        trials = manifest
    if not isinstance(trials, Sequence) or isinstance(trials, (str, bytes)):
        raise ValueError("trial_parts_manifest must contain a 'trials' list.")
    return list(trials)


def apply_trial_parts_manifest(
    normalized: pd.DataFrame,
    source: pd.DataFrame,
    manifest: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    kind: str,
) -> pd.DataFrame:
    """Attach a nested trial-parts manifest to a normalized report.

    Each part declares ``screen_id``, optional ``screen_index``/canvas size, and
    a source-row selector under ``words`` or ``fixations``. Example::

        {"trials": [{"participant_id": "p1", "trial_id": "t1", "parts": [
          {"screen_id": "intro", "screen_index": 1,
           "words": {"page": "intro"}, "fixations": {"page": "intro"}}
        ]}]}

    Selectors are exact column/value mappings. Overlapping selectors, unmatched
    rows inside a declared parent, duplicate order keys, and unknown columns are
    errors; the function never chooses a first row silently.
    """
    if normalized.empty:
        return normalized
    if kind not in {"words", "fixations"}:
        raise ValueError("kind must be 'words' or 'fixations'.")
    out = normalized.copy()
    assigned = pd.Series(False, index=out.index)
    declared_parent = pd.Series(False, index=out.index)
    for trial in _manifest_trials(manifest):
        if not isinstance(trial, Mapping):
            raise ValueError("Each manifest trial must be an object.")
        pid, tid = trial.get("participant_id"), trial.get("trial_id")
        parts = trial.get("parts", trial.get("screens", []))
        if pid is None or tid is None or not isinstance(parts, Sequence):
            raise ValueError(
                "Each manifest trial needs participant_id, trial_id, and parts."
            )
        parent_mask = (out["participant_id"].astype(str) == str(pid)) & (
            out["trial_id"].astype(str) == str(tid)
        )
        if not parent_mask.any():
            raise ValueError(
                f"Manifest parent {(str(pid), str(tid))!r} matches no rows."
            )
        declared_parent |= parent_mask
        for position, part in enumerate(parts, start=1):
            if not isinstance(part, Mapping) or part.get(SCREEN_ID) in (None, ""):
                raise ValueError("Each manifest part needs a non-empty screen_id.")
            selector = part.get(kind)
            if not isinstance(selector, Mapping) or not selector:
                raise ValueError(
                    f"Manifest screen {part[SCREEN_ID]!r} needs a {kind} selector."
                )
            mask = parent_mask.copy()
            for column, wanted in selector.items():
                if column not in source.columns:
                    raise ValueError(
                        f"Manifest {kind} selector names unknown column {column!r}."
                    )
                mask &= source[column].eq(wanted)
            if not mask.any():
                raise ValueError(
                    f"Manifest screen {part[SCREEN_ID]!r} {kind} selector matches no rows."
                )
            if (assigned & mask).any():
                raise ValueError(
                    f"Manifest screen {part[SCREEN_ID]!r} overlaps another part."
                )
            assigned |= mask
            out.loc[mask, SCREEN_ID] = str(part[SCREEN_ID])
            out.loc[mask, SCREEN_INDEX] = int(part.get(SCREEN_INDEX, position))
            for column in (CANVAS_WIDTH, CANVAS_HEIGHT):
                if part.get(column) is not None:
                    out.loc[mask, column] = part[column]
    if (declared_parent & ~assigned).any():
        count = int((declared_parent & ~assigned).sum())
        raise ValueError(
            f"Trial-parts manifest leaves {count} declared-parent row(s) unmatched."
        )
    return normalize_screen_identity(out)


def screen_canvas_size(frame: pd.DataFrame) -> tuple[int, int] | None:
    """Per-screen canvas metadata when both dimensions are present."""
    if frame is None or frame.empty:
        return None
    values = []
    for column in (CANVAS_WIDTH, CANVAS_HEIGHT):
        if column not in frame.columns:
            return None
        numeric = pd.to_numeric(frame[column], errors="coerce").dropna().unique()
        if len(numeric) != 1 or numeric[0] <= 0:
            return None
        values.append(int(numeric[0]))
    return values[0], values[1]
