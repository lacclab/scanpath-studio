"""Loader for EyeGenBench bundles -- 39 harmonised reading corpora.

EyeGenBench (https://github.com/EyeBench/EyeGenBench) harmonises many public
eye-tracking-while-reading corpora into one schema, but discards screen
geometry. `scripts/prepare_eyegenbench.py` runs their pipeline, recovers the
geometry, and writes the bundle this module reads. See
`docs/eyegenbench.md` and `plans/data-27-eyegenbench-datasets.md`.

Bundle contract for `fixations.parquet`: it must NOT carry a column literally
named `unique_trial_id`. `data.normalize_fixations` hard-codes that exact
column name to `trial_id` whenever it's present, which would override
`EYEGENBENCH_FIX_SCHEMA`'s `trial` mapping below and break the words
broadcast (paragraph-keyed stimulus-level words vs. reading-keyed fixations
would never match, silently broadcasting zero word boxes). If the prep
script carries EyeGenBench's own finer-grained (per-reading) trial identity
through at all, it must use the column name `eyegenbench_trial_id` instead --
registered as an opaque passthrough in Task 7.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

MANIFEST_NAME = "manifest.json"
_TABLES = ("words", "fixations", "participants")

# Stimulus-level: `participant=None` marks one shared layout rather than one row
# per reader, so `data.broadcast_stimulus_words` expands it (as for PoTeC).
EYEGENBENCH_WORD_SCHEMA = dict(
    participant=None,
    trial="unique_paragraph_id",
    word_id="ia_index",
    text="ia_label",
    line="line",
    left="start_x",
    right="end_x",
    top="start_y",
    bottom="end_y",
)

# `trial` is `unique_paragraph_id`, matching the word schema above -- not
# EyeGenBench's own (finer-grained, per-reading) `unique_trial_id`. See the
# module docstring: a raw `unique_trial_id` column would silently override
# this mapping and break the stimulus-level words broadcast. Trial identity
# isn't lost -- (participant_id, trial_id=paragraph) identifies a reading,
# and `data._disambiguate_repeated_readings` still separates repeated
# readings of the same paragraph by the same participant.
EYEGENBENCH_FIX_SCHEMA = dict(
    participant="unique_participant_id",
    trial="unique_paragraph_id",
    duration="fix_duration",
    x="x",
    y="y",
    fixation_id="fix_index",
    word_id="ia_index",
)


def _manifest_path(root) -> Path:
    return Path(root) / MANIFEST_NAME


def eyegenbench_manifest(root) -> dict:
    """The bundle manifest, or a `FileNotFoundError` naming the fix."""
    path = _manifest_path(root)
    if not path.is_file():
        raise FileNotFoundError(
            f"No EyeGenBench bundle at {root!s} (missing {MANIFEST_NAME}). "
            "Build one with: python scripts/prepare_eyegenbench.py --all"
        )
    return json.loads(path.read_text())


def eyegenbench_datasets(root) -> list:
    """Manifest entries, one per prepared dataset. Cheap -- no Parquet is read."""
    return list(eyegenbench_manifest(root).get("datasets", []))


def eyegenbench_present(root, dataset: Optional[str] = None) -> bool:
    """True when the bundle holds everything a load needs. Path stats only.

    Strict on purpose: a lenient check passes a partial tree and then crashes
    mid-load, whereas a strict one lets the app offer the fix.
    """
    root = Path(root)
    if not _manifest_path(root).is_file():
        return False
    try:
        entries = eyegenbench_datasets(root)
    except (OSError, ValueError):
        return False
    names = [e["name"] for e in entries] if dataset is None else [dataset]
    if not names:
        return False
    return all(
        all((root / name / f"{table}.parquet").is_file() for table in _TABLES)
        for name in names
    )


def eyegenbench_monitor(root, dataset: str) -> Tuple[int, int]:
    """The corpus' screen in pixels -- what makes the plot true-to-scale."""
    for entry in eyegenbench_datasets(root):
        if entry["name"].lower() == str(dataset).lower():
            width, height = entry["monitor"]
            return int(width), int(height)
    raise ValueError(f"{dataset!r} is not in the bundle at {root!s}")


def _dataset_dir(root, dataset: str) -> Path:
    root = Path(root)
    eyegenbench_manifest(root)  # raises FileNotFoundError with the fix
    for entry in eyegenbench_datasets(root):
        if entry["name"].lower() == str(dataset).lower():
            return root / entry["name"]
    raise ValueError(f"{dataset!r} is not in the bundle at {root!s}")


def eyegenbench_raw_frames(root, *, dataset: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) ``(words, fixations)`` frames for ``dataset``."""
    directory = _dataset_dir(root, dataset)
    return (
        pd.read_parquet(directory / "words.parquet"),
        pd.read_parquet(directory / "fixations.parquet"),
    )


def load_eyegenbench(root, *, dataset: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load an EyeGenBench corpus as normalized ``(words, fixations)``."""
    from .api import load_scanpath_data

    words, fixations = eyegenbench_raw_frames(root, dataset=dataset)
    return load_scanpath_data(
        words,
        fixations,
        word_schema=EYEGENBENCH_WORD_SCHEMA,
        fix_schema=EYEGENBENCH_FIX_SCHEMA,
    )


def load_eyegenbench_participants(root, dataset: str) -> pd.DataFrame:
    """Per-reader metadata -- the DATA-20 participant-metadata table.

    Never broadcast onto the word/fixation frames.
    """
    return pd.read_parquet(_dataset_dir(root, dataset) / "participants.parquet")
