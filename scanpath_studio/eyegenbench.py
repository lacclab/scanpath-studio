"""Loader for a local bundle of harmonised reading corpora.

EyeGenBench (https://github.com/EyeBench/EyeGenBench) harmonises many public
eye-tracking-while-reading corpora into one schema, but discards screen
geometry. `scripts/prepare_eyegenbench.py` runs their pipeline, recovers the
geometry, and writes the bundle this module reads. See
`docs/benchmark-corpora.md` and `plans/data-27-eyegenbench-datasets.md`.

The pipeline can *load* 39 corpora; a bundle holds however many the user
prepared, which is fewer -- some publishers require manual acquisition. Read
the manifest for what is actually there rather than assuming a count.

Bundle contract for `fixations.parquet`: it must NOT carry a column literally
named `unique_trial_id`. `data.normalize_fixations` hard-codes that exact
column name to `trial_id` whenever it's present, which would override
`EYEGENBENCH_FIX_SCHEMA`'s `trial` mapping below and break the words
broadcast (paragraph-keyed stimulus-level words vs. reading-keyed fixations
would never match, silently broadcasting zero word boxes). If the prep
script carries EyeGenBench's own finer-grained (per-reading) trial identity
through at all, it must use the column name `eyegenbench_trial_id` instead --
registered as an opaque passthrough in Task 7. It must also give repeated
readings of the same paragraph by the same participant distinct
`unique_paragraph_id` values: this loader keys `trial_id` on that column
directly and does not disambiguate repeats itself.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    # Declared absent, not merely omitted. A prepared corpus is single-screen by
    # contract -- the prep script writes one coordinate space per paragraph --
    # but the frames carry the publisher's leftover columns through, and some
    # corpora (Provo, SBSAT) keep a `page`. Auto-detection finds it on the
    # fixations and not here, and `multipart.validate_matching_parts` then
    # rejects the pair outright ("Multipart identity is present in only one
    # report"). Saying `None` on BOTH schemas is what stops a leftover column
    # being read as a screen identity that this bundle does not have.
    screen_id=None,
)

# `trial` is `unique_paragraph_id`, matching the word schema above -- not
# EyeGenBench's own (finer-grained, per-reading) `unique_trial_id`. See the
# module docstring: a raw `unique_trial_id` column would silently override
# this mapping and break the stimulus-level words broadcast. Keying on
# unique_paragraph_id is what makes that broadcast join work; repeated
# readings of the same paragraph by the same participant are NOT separated
# here (`data._disambiguate_repeated_readings` no-ops without a raw
# TRIAL_INDEX column, which EyeGenBench frames don't carry) -- the prep
# script is responsible for giving each reading its own paragraph key
# upstream (Task 8, R17).
EYEGENBENCH_FIX_SCHEMA = dict(
    participant="unique_participant_id",
    trial="unique_paragraph_id",
    duration="fix_duration",
    x="x",
    y="y",
    fixation_id="fix_index",
    word_id="ia_index",
    screen_id=None,  # see EYEGENBENCH_WORD_SCHEMA
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


def entry_name(entry) -> str:
    """A manifest row's dataset name, or ``""`` when it hasn't got one.

    A row is data from a file on disk, so it can be malformed. Reading the name
    as ``entry["name"]`` raised `KeyError` — outside the `(FileNotFoundError,
    ValueError, OSError)` triple every caller guards with, so **one** nameless
    row ordered before a valid one took the whole app down through whichever
    surface looked at the manifest next (M7 / I2). Nameless rows are unusable
    by definition — nothing can address them — so every reader skips them here
    rather than each remembering to catch a third exception type.
    """
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("name") or "").strip()


def entry_count(entry, key: str) -> int | None:
    """A manifest row's integer count field: the number, ``0``, or ``None``.

    The same rule as `entry_name`, for the count fields (`n_texts`,
    `n_readers`, `n_fixations`, `paragraphs_without_real_boxes`): a manifest is
    data from a file on disk, and a bare ``int(entry.get(key))`` raises
    `ValueError`/`TypeError` on ``"many"``, ``[1]`` or any other shape a hand
    edit can produce — outside the catch every caller guards with, and now on
    the path that builds a picker entry for every discovered corpus (N1).

    ``0`` when the field is absent or blank — *not recorded* is a known
    quantity for a count, and every reader treats it as none. ``None`` when the
    value is there but isn't a number, so a caller can tell "no missing texts"
    from "the missing-text count is unreadable" and word its claim accordingly
    rather than asserting the confident one.

    **Never write ``entry_count(...) or 0``.** It collapses `None` into `0` and
    so reads an unreadable count as *nothing missing* — which is precisely how
    a corpus with unknown coverage gets badged a confident "Real", the
    overclaim R34 exists to prevent. Test the two cases apart (``if count :=
    entry_count(...)`` is fine — it drops both, which is right when the value is
    only being formatted), or handle `None` explicitly.
    """
    if not isinstance(entry, dict):
        return None
    raw = entry.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _find_entry(root, dataset: str) -> dict | None:
    """The manifest entry named ``dataset`` (case-insensitive), or ``None``.

    Shared by every function that resolves a dataset name against the
    manifest, so the case-insensitive comparison lives in exactly one place.
    """
    for entry in eyegenbench_datasets(root):
        if (name := entry_name(entry)) and name.lower() == str(dataset).lower():
            return entry
    return None


def eyegenbench_present(root, dataset: str | None = None) -> bool:
    """True when the bundle holds everything a load needs. Path stats only.

    Strict on purpose: a lenient check passes a partial tree and then crashes
    mid-load, whereas a strict one lets the app offer the fix. That includes
    resolving ``dataset`` against the manifest first -- a directory holding
    all three Parquet files under a name absent from the manifest must not
    read as present, since loading that same name would still raise.
    """
    root = Path(root)
    if not _manifest_path(root).is_file():
        return False
    try:
        if dataset is None:
            names = [n for e in eyegenbench_datasets(root) if (n := entry_name(e))]
        else:
            entry = _find_entry(root, dataset)
            names = [] if entry is None else [entry_name(entry)]
    except (OSError, ValueError):
        return False
    if not names:
        return False
    return all(
        all((root / name / f"{table}.parquet").is_file() for table in _TABLES)
        for name in names
    )


def declared_monitor(entry) -> tuple[int, int] | None:
    """A manifest row's screen when the corpus actually documents one (I3).

    ``monitor_source: "default"`` marks `eyegenbench_geometry.py`'s generic
    guess for a corpus that documents no screen at all -- 1920x1080, invented.
    Snapping a canvas to an invented screen presents a made-up geometry as the
    corpus', so both surfaces decline it: ``None`` means "no declared screen",
    and the caller falls back to the data's own extents.

    **The rule lives here, once.** The app reads it building each corpus'
    registry entry and the CLI reads it resolving ``--eyegenbench``'s canvas;
    duplicating the condition is how the same corpus came to render at two
    different scales depending on which surface asked.
    """
    if not isinstance(entry, dict):
        return None
    monitor = entry.get("monitor")
    if not monitor or entry.get("monitor_source") == "default":
        return None
    try:
        return int(monitor[0]), int(monitor[1])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def eyegenbench_monitor(root, dataset: str) -> tuple[int, int] | None:
    """The corpus' documented screen in pixels, or ``None`` (I3).

    ``None`` when the manifest records no screen for this corpus, or only the
    invented default one -- see `declared_monitor`. A `ValueError` still means
    the *dataset* isn't in the bundle, which is a different failure and stays
    loud.
    """
    entry = _find_entry(root, dataset)
    if entry is None:
        raise ValueError(f"{dataset!r} is not in the bundle at {root!s}")
    return declared_monitor(entry)


def _dataset_dir(root, dataset: str) -> Path:
    root = Path(root)
    eyegenbench_manifest(root)  # raises FileNotFoundError with the fix
    entry = _find_entry(root, dataset)
    if entry is None:
        raise ValueError(f"{dataset!r} is not in the bundle at {root!s}")
    return root / entry["name"]


def eyegenbench_raw_frames(root, *, dataset: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) ``(words, fixations)`` frames for ``dataset``."""
    directory = _dataset_dir(root, dataset)
    return (
        pd.read_parquet(directory / "words.parquet"),
        pd.read_parquet(directory / "fixations.parquet"),
    )


def load_eyegenbench(root, *, dataset: str) -> tuple[pd.DataFrame, pd.DataFrame]:
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
