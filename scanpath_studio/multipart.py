"""Canonical identity and validation for trials made of ordered screens.

Single-screen data identifies one coordinate space with
``(participant_id, trial_id)``.  Multipart trials retain that logical parent
identity and add ``screen_id`` plus a 1-based ``screen_index`` on every row.
This module is deliberately pandas-only so ingestion, measures, UI, API, CLI,
and export can share the exact same boundary rules without importing Streamlit.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from graphlib import CycleError, TopologicalSorter
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd

PARENT_KEY = ("participant_id", "trial_id")
SCREEN_ID = "screen_id"
SCREEN_INDEX = "screen_index"
PART_KEY = (*PARENT_KEY, SCREEN_ID)
SCREEN_TIMESTAMP = "screen_timestamp_ms"
SCREEN_FIXATION_ID = "screen_fixation_id"
CANVAS_WIDTH = "canvas_width"
CANVAS_HEIGHT = "canvas_height"


def has_screen_identity(frame: pd.DataFrame | None) -> bool:
    """Whether ``frame`` carries canonical screen identity."""
    return bool(frame is not None and SCREEN_ID in frame.columns)


def grouping_columns(frame: pd.DataFrame, *, include_word: bool = False) -> list[str]:
    """Identity columns for a scientific operation on ``frame``.

    Single-screen frames keep the parent key. Multipart frames add
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
    """Normalize/validate screen columns, preserving single-screen frame shape.

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
            raise ValueError(
                "`screen_index` (screen order) has blank or non-numeric cells."
            )
        out[SCREEN_ID] = numeric_index.astype(int).astype(str)
    else:
        # `stable_id`, not a plain `.astype(str)`: a whole-number screen_id
        # reads as float64 the moment any OTHER row anywhere in that column is
        # missing, so one report's `"1"` becomes another's `"1.0"` and
        # `validate_matching_parts` below rejects every screen as an orphan
        # even though both sides recorded the same one.
        # Imported locally — `data.py` imports from this module, so a
        # module-level import would cycle.
        from .data import stable_id

        ids = stable_id(out[SCREEN_ID])
        out[SCREEN_ID] = ids.where(out[SCREEN_ID].notna() & ids.ne(""))

    if not has_index:
        distinct = (
            out[parents + [SCREEN_ID]].dropna(subset=[SCREEN_ID]).drop_duplicates()
        )
        distinct[SCREEN_INDEX] = distinct.groupby(parents, sort=False).cumcount() + 1
        keys = parents + [SCREEN_ID]
        out[SCREEN_INDEX] = (
            out[keys]
            .merge(distinct, on=keys, how="left", sort=False)[SCREEN_INDEX]
            .to_numpy()
        )
    else:
        numeric_index = pd.to_numeric(out[SCREEN_INDEX], errors="coerce")
        assigned = out[SCREEN_ID].notna()
        if numeric_index[assigned].isna().any() or (numeric_index[assigned] <= 0).any():
            raise ValueError("`screen_index` (screen order) must count from 1.")
        if (numeric_index[assigned] % 1 != 0).any():
            raise ValueError("`screen_index` (screen order) must be whole numbers.")
        out[SCREEN_INDEX] = (
            numeric_index.astype(int)
            if assigned.all()
            else numeric_index.where(assigned).astype("Int64")
        )

    pairs = (
        out[parents + [SCREEN_ID, SCREEN_INDEX]]
        .dropna(subset=[SCREEN_ID])
        .drop_duplicates()
    )
    if pairs.duplicated(parents + [SCREEN_ID], keep=False).any():
        raise ValueError("Within a trial, one Screen ID has two `screen_index` values.")
    if pairs.duplicated(parents + [SCREEN_INDEX], keep=False).any():
        raise ValueError("Within a trial, two Screen IDs share one `screen_index`.")

    for column in (CANVAS_WIDTH, CANVAS_HEIGHT):
        if column not in out.columns:
            continue
        values = pd.to_numeric(out[column], errors="coerce")
        if values.notna().any() and (values.dropna() <= 0).any():
            raise ValueError(f"{_FIELD_LABELS[column]} must be positive.")
        out[column] = values
        counts = out.groupby(list(PART_KEY), dropna=False)[column].nunique(dropna=True)
        if (counts > 1).any():
            raise ValueError(f"{_FIELD_LABELS[column]} changes within one screen.")
    return out


#: What a user calls each screen column in a message (the add screen's names).
_FIELD_LABELS = {
    SCREEN_INDEX: "Screen number",
    CANVAS_WIDTH: "Screen canvas width",
    CANVAS_HEIGHT: "Screen canvas height",
}


def _screens(parts: list) -> str:
    """Up to three ``(participant, trial, screen)`` keys, as ``p01/3/page_2``."""
    return ", ".join("/".join(str(v) for v in part) for part in parts[:3])


def _merge_screen_order(
    hints: pd.DataFrame, recorded: dict[str, int]
) -> dict[str, int]:
    """Fit partial screen sequences together while preserving recorded ordinals."""
    graph = {s: set() for s in hints[SCREEN_ID].unique()}
    sequences = [sorted(recorded, key=recorded.__getitem__)]
    for _, rows in hints.groupby("_source", sort=False):
        sequences.append(
            rows.sort_values("_order_hint")[SCREEN_ID].drop_duplicates().tolist()
        )
    # A file can list the same pages in another order. Give recorded ordinals
    # first choice, then the most complete table's order. Compatible partial
    # sequences contribute their before/after relationships.
    order = list(graph)
    for sequence in sequences:
        proposed = {s: set(before) for s, before in graph.items()}
        for before, after in pairwise(sequence):
            proposed[after].add(before)
        try:
            order = list(TopologicalSorter(proposed).static_order())
        except CycleError:
            continue
        graph = proposed
    # Reserve early slots for predecessors of a recorded page. Otherwise an
    # unrelated page can take the only available slot before that page.
    deadlines = {screen: recorded.get(screen, np.inf) for screen in order}
    for screen in reversed(order):
        for before in graph[screen]:
            deadlines[before] = min(deadlines[before], deadlines[screen] - 1)
    order.sort(key=deadlines.__getitem__)
    numbers = recorded.copy()
    occupied = set(recorded.values())
    next_number = 1
    for screen in order:
        if screen in recorded:
            next_number = max(next_number, recorded[screen] + 1)
        else:
            while next_number in occupied:
                next_number += 1
            numbers[screen] = next_number
            next_number += 1
    return numbers


def part_catalog(*frames: pd.DataFrame | None) -> pd.DataFrame:
    """One ordered row per screen across ``frames``.

    Recorded metadata must agree across tables. A derived screen order or
    fallback text ID fills a gap when no table recorded that field.
    """
    from .data import SCREEN_ORDER_DERIVED, TEXT_ID_MAPPED

    rows: list[pd.DataFrame] = []
    metadata = [SCREEN_INDEX, CANVAS_WIDTH, CANVAS_HEIGHT, "text_id"]
    for source, frame in enumerate(frames):
        if frame is None or frame.empty or not has_screen_identity(frame):
            continue
        # Millions of samples can refer to a handful of screens. Validate
        # just their distinct metadata, preserving first appearance.
        columns = [
            *PART_KEY,
            *(
                c
                for c in (*metadata, SCREEN_ORDER_DERIVED, TEXT_ID_MAPPED)
                if c in frame
            ),
        ]
        candidate = normalize_screen_identity(frame[columns].drop_duplicates()).dropna(
            subset=[SCREEN_ID]
        )
        if candidate.empty:
            continue
        derived = candidate.get(SCREEN_ORDER_DERIVED, SCREEN_INDEX not in frame)
        candidate["_order_hint"] = candidate[SCREEN_INDEX]
        candidate["_source"] = source
        if isinstance(derived, pd.Series):
            candidate.loc[derived.fillna(False), SCREEN_INDEX] = pd.NA
        elif derived:
            candidate[SCREEN_INDEX] = pd.NA
        candidate["_coverage"] = candidate.groupby(list(PARENT_KEY))[
            SCREEN_ID
        ].transform("nunique")
        if "text_id" in candidate:
            mapped = candidate.get(
                TEXT_ID_MAPPED, candidate["text_id"].ne(candidate["trial_id"])
            )
            candidate["_text_hint"] = candidate["text_id"]
            candidate["text_id"] = candidate["text_id"].where(mapped)
        else:
            candidate["_text_hint"] = pd.NA
        for column in metadata:
            if column not in candidate.columns:
                candidate[column] = pd.NA
        rows.append(
            candidate[
                [
                    *PART_KEY,
                    *metadata,
                    "_order_hint",
                    "_text_hint",
                    "_coverage",
                    "_source",
                ]
            ]
        )
    if not rows:
        return pd.DataFrame(columns=[*PART_KEY, *metadata])

    combined = pd.concat(rows, ignore_index=True)
    for column in metadata:
        conflicts = combined.groupby(list(PART_KEY), dropna=False)[column].nunique(
            dropna=True
        )
        if (conflicts > 1).any():
            # tabs.py matches this text exactly (the screen_index case), so
            # keep its wording.
            raise ValueError(f"Multipart metadata {column!r} conflicts across tables.")
    # The most complete table gives the best first-appearance order when a
    # reading supplies no explicit ordinal for a screen.
    combined = combined.sort_values("_coverage", ascending=False, kind="stable")
    grouped = combined.groupby(list(PART_KEY), as_index=False, dropna=False, sort=False)
    catalog = grouped.first()
    catalog["text_id"] = catalog["text_id"].fillna(catalog["_text_hint"])
    inferred = catalog[SCREEN_INDEX].isna()
    catalog[SCREEN_INDEX] = (
        catalog[SCREEN_INDEX].fillna(catalog["_order_hint"]).astype(int)
    )
    ordinal = [*PARENT_KEY, SCREEN_INDEX]
    if catalog.loc[~inferred].duplicated(ordinal).any():
        raise ValueError(
            "Within a trial, two Screen IDs share one recorded `screen_index`."
        )
    different_hints = grouped["_order_hint"].nunique()["_order_hint"].gt(1)
    ambiguous = catalog.duplicated(ordinal, keep=False) | different_hints
    if ambiguous.any():
        readings = combined.groupby(list(PARENT_KEY), sort=False)
        parents = catalog.groupby(list(PARENT_KEY), sort=False)
        for key in (
            catalog.loc[ambiguous, list(PARENT_KEY)]
            .drop_duplicates()
            .itertuples(index=False, name=None)
        ):
            parent = parents.get_group(key)
            known = parent.loc[~inferred.loc[parent.index]].set_index(SCREEN_ID)[
                SCREEN_INDEX
            ]
            numbers = _merge_screen_order(readings.get_group(key), known.to_dict())
            catalog.loc[parent.index, SCREEN_INDEX] = parent[SCREEN_ID].map(numbers)
    return catalog[[*PART_KEY, *metadata]].sort_values(
        [*PARENT_KEY, SCREEN_INDEX, SCREEN_ID], kind="stable", ignore_index=True
    )


class ScreensWithoutFixationsWarning(UserWarning):
    """Some screens have word boxes but no fixations.

    A screen the eye tracker did not record — or one the reader never looked
    at — is a gap in the data, not a mapping mistake: the screen loads with its
    word boxes and an empty fixation layer, as a trial only the Words table has
    does. A ``UserWarning``, so the API and the CLI see it; its own class so
    the add-dataset wizard and ✏️ Edit dataset can show it on the page."""


def _parts(frame: pd.DataFrame) -> set:
    return set(map(tuple, frame[list(PART_KEY)].drop_duplicates().to_numpy()))


def _matching_parts(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> tuple[list, list] | None:
    """``(screens with no words, screens with no fixations)``, or ``None`` when
    the pair carries no screen identity to compare."""
    if words.empty or fixations.empty:
        return None
    if not has_screen_identity(words) and not has_screen_identity(fixations):
        return None
    if has_screen_identity(words) != has_screen_identity(fixations):
        raise ValueError(
            "Screen ID is set in only one table; set it in both or neither."
        )
    word_parts = _parts(words)
    fixation_parts = _parts(fixations)
    return sorted(fixation_parts - word_parts), sorted(word_parts - fixation_parts)


def screens_without_fixations(words: pd.DataFrame, fixations: pd.DataFrame) -> list:
    """The ``(participant, trial, screen)`` keys only the Words table has."""
    found = _matching_parts(words, fixations)
    return found[1] if found else []


def screens_without_fixations_notice(parts: list) -> str:
    """What the load says about screens with word boxes but no fixations."""
    more = f" and {len(parts) - 3} more" if len(parts) > 3 else ""
    noun = "screen has" if len(parts) == 1 else "screens have"
    return (
        f"{len(parts)} {noun} word boxes but no fixations "
        f"({_screens(parts)}{more}). They load with their word boxes and no "
        "fixations. If those screens were recorded, check that **Screen ID** "
        "names the same screens in both tables."
    )


def validate_matching_parts(words: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """Reject fixations on a screen the Words table has no boxes for.

    Such fixations have no stimulus to land on, so they mean the two tables'
    Screen IDs do not line up. A screen with boxes but no fixations is a gap in
    the recording instead: it loads, with a
    :class:`ScreensWithoutFixationsWarning`."""
    found = _matching_parts(words, fixations)
    if found is None:
        return
    missing_words, missing_fix = found
    if missing_words:
        details = [f"no words for {_screens(missing_words)}"]
        if missing_fix:
            details.append(f"no fixations for {_screens(missing_fix)}")
        raise ValueError("Some screens are in one table only: " + "; ".join(details))
    if missing_fix:
        warnings.warn(
            screens_without_fixations_notice(missing_fix),
            ScreensWithoutFixationsWarning,
            stacklevel=3,
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


def screen_rows(trial: pd.DataFrame, screen: str | None) -> pd.DataFrame:
    """One screen of an already selected reading. Unassigned rows have no screen."""
    if screen is None or trial.empty:
        return trial
    if SCREEN_ID not in trial:
        return trial.iloc[:0]
    return trial.loc[trial[SCREEN_ID].astype(str).eq(str(screen))]


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
    """Per-screen canvas metadata when both dimensions are present.

    ``None`` — the caller's own screen size — unless each dimension holds one
    finite, positive value."""
    if frame is None or frame.empty:
        return None
    values = []
    for column in (CANVAS_WIDTH, CANVAS_HEIGHT):
        if column not in frame.columns:
            return None
        numeric = pd.to_numeric(frame[column], errors="coerce").dropna().unique()
        if len(numeric) != 1 or not np.isfinite(numeric[0]) or numeric[0] <= 0:
            return None
        values.append(int(numeric[0]))
    return values[0], values[1]
