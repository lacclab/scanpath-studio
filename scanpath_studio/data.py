from __future__ import annotations

import glob
import hashlib
import importlib.resources as resources
import io
import logging
import os
import re
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import streamlit as st

from .constants import DEFAULT_FIGURE_SIZE, PACKAGE_NAME

_LOGGER = logging.getLogger(__name__)

# DATA-16 / audit S5. Up to this many rows the fingerprint hashes the WHOLE
# frame, so any edit anywhere changes the key. Measured on a 4-column frame:
# 8 ms at 100k rows, 59 ms at 1M, 237 ms at 5M — and roughly six corpus-sized
# fingerprints are taken per rerun, so a full hash of a multi-million-row corpus
# would cost seconds of latency on every interaction. 200k keeps the exact path
# under ~16 ms while covering the case that actually matters: a user editing
# their own table and re-uploading it.
_FINGERPRINT_FULL_MAX_ROWS = 200_000
# Above the threshold: rows sampled from each end, plus an evenly-spaced stride.
_FINGERPRINT_EDGE_ROWS = 64
_FINGERPRINT_STRIDE_ROWS = 256

# PERF-3. Per-run memo, `id(frame) -> (frame, fingerprint)`.
#
# Once the expensive subtabs went lazy the biggest remaining cost in a rerun was
# the cache keys themselves: ~26 calls, 43% of the run, and the same handful of
# frame OBJECTS over and over — every `_c_*` wrapper re-fingerprints the words
# and fixations frames `app.main` loaded once. Hashing the same object twice in
# one run cannot produce two answers, so the second hash onwards is pure waste.
#
# The dict holds a **strong reference** to each frame, which is what makes an
# `id()` key safe: a memoized frame cannot be collected, so its id cannot be
# handed to a different object while the entry lives. (The `is` re-check below
# costs nothing and documents the invariant.)
#
# `threading.local` scopes it to the ScriptRunner thread — one per Streamlit
# session — so two sessions never share entries and one session's reset can't
# drop another's. `reset_fingerprint_memo()` at the top of `app.main` bounds the
# lifetime to a single script run, which bounds both memory and the blast radius
# of the assumption below.
#
# THE ASSUMPTION: a fingerprinted frame is not mutated **in place** part-way
# through a run. That holds today — the frames the app fingerprints are built by
# `normalize_*` / `filter_*` / `.copy()` and then only read; helpers that add
# columns (`aggregation.py`) do it to a local copy — and it is the within-run
# form of the DATA-16 / audit S5 hazard the sampling threshold above is about.
# If you ever add an in-place `frame[col] = …` to a long-lived frame, either
# copy instead or the caches downstream of it will serve pre-mutation results
# for the rest of that run.
_FINGERPRINT_MEMO = threading.local()
#: Backstop for a non-Streamlit caller (headless `api.py`, the CLI) that never
#: reaches `reset_fingerprint_memo`: keep the memo from growing without bound.
_FINGERPRINT_MEMO_MAX = 64


def reset_fingerprint_memo() -> None:
    """Drop the per-run fingerprint memo. Called once per script run (PERF-3)."""
    getattr(_FINGERPRINT_MEMO, "cache", {}).clear()


def frame_fingerprint(df: Optional[pd.DataFrame]) -> tuple:
    """Cheap, content-sensitive identity for a DataFrame.

    Used as an *explicit* ``@st.cache_data`` key for functions that take an
    underscore-prefixed (un-hashed) frame argument — so Streamlit never re-hashes
    a multi-million-row frame on every rerun just to look up the cache.

    **Up to ``_FINGERPRINT_FULL_MAX_ROWS`` the whole frame is hashed**, so any
    edit anywhere changes the key. This is the fix for DATA-16 / audit S5: the
    previous key sampled only the first and last 64 rows, so a table of ≥129 rows
    edited anywhere in between produced an *identical* key — not a probabilistic
    collision but a certain one. Re-uploading a corrected table of the same shape
    then served every figure, measure and aggregate from the pre-edit data,
    silently, which is a route to a wrong number in a paper.

    **Above the threshold the key is a sample** (both ends plus an evenly-spaced
    stride) and detection becomes probabilistic: a single-cell edit in a
    5-million-row corpus has roughly a 1-in-19,000 chance of landing on a sampled
    row. That is a deliberate trade — a full hash there costs ~237 ms, taken
    about six times per rerun. It is the right trade because the frames people
    hand-edit and re-upload are their own tables, not multi-million-row public
    corpora, but it *is* a limit: after editing a corpus that large, use **Clear
    cache** in the ☰ menu.

    The per-row hashes are digested **in order** rather than summed. Summing is
    order-invariant, so a frame and a ``sort_values`` of itself — same rows, same
    index labels, different order — used to share a key while producing different
    results downstream.

    ``hash_pandas_object`` raises on columns of unhashable objects (lists/arrays —
    e.g. parquet-preserved span-index fields). We stringify and retry rather than
    drop the content signal entirely: zeroing the hash would collapse every frame
    of the same shape + columns to one fingerprint, serving stale cached results
    when switching between two such frames. If even that fails the key becomes
    *unique* rather than zero — an unhashable frame must miss the cache, not
    match every other frame of its shape.

    **The same frame object is only hashed once per run** — see the
    ``_FINGERPRINT_MEMO`` note above for why that is safe and what it assumes.
    """
    if df is None or getattr(df, "empty", True):
        return (0, ())
    memo = getattr(_FINGERPRINT_MEMO, "cache", None)
    if memo is None:
        memo = _FINGERPRINT_MEMO.cache = {}
    hit = memo.get(id(df))
    if hit is not None and hit[0] is df:
        return hit[1]
    value = _compute_frame_fingerprint(df)
    if len(memo) >= _FINGERPRINT_MEMO_MAX:
        memo.clear()
    memo[id(df)] = (df, value)
    return value


def _compute_frame_fingerprint(df: pd.DataFrame) -> tuple:
    """The actual hash behind :func:`frame_fingerprint`, memo aside."""
    cols = tuple(map(str, df.columns))
    n = int(len(df))

    def _hash(sample: pd.DataFrame) -> str:
        try:
            per_row = pd.util.hash_pandas_object(sample, index=True)
        except TypeError:
            # Unhashable cell objects — stringify so content still drives the key.
            per_row = pd.util.hash_pandas_object(sample.astype(str), index=True)
        # Digest the per-row hashes in ORDER. Summing them (the previous
        # approach) is order-invariant, so a frame and a `sort_values` of itself
        # — same rows, same index labels, different order — produced the same
        # key while yielding different results downstream.
        return hashlib.blake2b(
            per_row.to_numpy(dtype="uint64").tobytes(), digest_size=16
        ).hexdigest()

    try:
        if n <= _FINGERPRINT_FULL_MAX_ROWS:
            return (n, cols, _hash(df))
        head = _hash(df.head(_FINGERPRINT_EDGE_ROWS))
        tail = _hash(df.tail(_FINGERPRINT_EDGE_ROWS))
        # An evenly-spaced sample of the whole frame, capped at
        # _FINGERPRINT_STRIDE_ROWS rows however long the table is.
        middle = _hash(df.iloc[:: max(1, n // _FINGERPRINT_STRIDE_ROWS)])
    except Exception:
        # Fail CLOSED: a key nothing else can equal, so this frame simply doesn't
        # share a cache entry. `(n, cols, 0, 0)` failed *open* — every frame of
        # the same shape collided.
        return (n, cols, uuid.uuid4().hex)
    return (n, cols, head, tail, middle)


# ---------------------------------------------------------------------------
# Server-side OneStop data source.
#
# When the env var `ONESTOP_DATA_DIR` points at a OneStop lacclab export
# folder (containing `ia_Paragraph.csv.zip` and `fixations_Paragraph.csv.zip`),
# `load_onestop_server_bundle()` returns them as the (words, fixations) tuple
# the rest of the pipeline expects. The schema is identical to the bundled
# sample (the sample is a 3-pid subset of OneStop), so no extra normalisation
# is required.
#
# Drives the "OneStop server bundle" data source option in app.py, used by
# an external review-app deep-link integration (single pid+trial into this UI).
# ---------------------------------------------------------------------------

ONESTOP_DATA_DIR_ENV = "ONESTOP_DATA_DIR"


def onestop_data_dir() -> Optional[Path]:
    """Resolved value of `$ONESTOP_DATA_DIR`, or `None` if unset/blank."""
    raw = os.environ.get(ONESTOP_DATA_DIR_ENV, "").strip()
    return Path(raw) if raw else None


def onestop_full_bundle_exists() -> bool:
    """True when the full OneStop CSV.zip exports are present (not just per-pid
    shards).

    When the whole corpus is available the app loads it once and filters in-app
    (so switching participant is instant); a shards-only setup must instead load
    one participant's shard at a time (it can't materialize the ~60 GB corpus)."""
    base = onestop_data_dir()
    if base is None:
        return False
    return (base / "ia_Paragraph.csv.zip").exists() and (
        base / "fixations_Paragraph.csv.zip"
    ).exists()


def _onestop_shard_paths(base: Path, pid: str) -> Tuple[Path, Path]:
    """Resolved per-participant shard paths under `<base>/by_pid/`."""
    pid = pid.strip().lower()
    return (
        base / "by_pid" / "ia" / f"{pid}.parquet",
        base / "by_pid" / "fixations" / f"{pid}.parquet",
    )


def onestop_data_provenance(participant: Optional[str] = None) -> dict:
    """Where the currently-loaded OneStop data came from, for the Raw Data tab.

    Parses `ONESTOP_DATA_DIR` (typically `…/onestop_<cohort>/reports/<source>/<date>/full/`)
    to surface cohort, export source (lacclab / public / osf), and date in the
    UI so reviewers can verify they're looking at the right export. Also
    reports the per-pid shard's mtime when a participant is set — that's the
    timestamp of the actual data the page is currently rendering.

    Returns an empty dict when `ONESTOP_DATA_DIR` is unset (i.e. the OneStop
    data source isn't in use — caller should suppress the provenance panel).
    """
    base = onestop_data_dir()
    if base is None:
        return {}

    info: dict = {"data_dir": str(base)}

    # Best-effort parse of the canonical path layout.
    parts = base.resolve().parts
    try:
        # Look for "reports" anchor and grab source/date after it.
        i = parts.index("reports")
        info["source"] = parts[i + 1]  # lacclab / public / osf
        info["date"] = parts[i + 2]  # YYYYMMDD
    except (ValueError, IndexError):
        pass
    for p in parts:
        if p.startswith("onestop_"):
            info["cohort"] = p.removeprefix("onestop_")  # L1 / L2
            break

    # Reports the per-pid shard's mtime when a participant is set — that's the
    # timestamp of the bytes the page is rendering right now.
    if participant:
        ia_shard, fix_shard = _onestop_shard_paths(base, participant)
        info["loaded_from"] = "per-pid shard"
        info["ia_shard"] = str(ia_shard)
        info["fix_shard"] = str(fix_shard)
        if ia_shard.is_file():
            info["ia_shard_mtime"] = ia_shard.stat().st_mtime
        if fix_shard.is_file():
            info["fix_shard_mtime"] = fix_shard.stat().st_mtime
    else:
        ia_csv = base / "ia_Paragraph.csv.zip"
        fix_csv = base / "fixations_Paragraph.csv.zip"
        info["loaded_from"] = "full CSV.zip export"
        if ia_csv.is_file():
            info["ia_shard"] = str(ia_csv)
            info["ia_shard_mtime"] = ia_csv.stat().st_mtime
        if fix_csv.is_file():
            info["fix_shard"] = str(fix_csv)
            info["fix_shard_mtime"] = fix_csv.stat().st_mtime
    return info


@st.cache_data(show_spinner="Loading OneStop lacclab export…")
def load_onestop_server_bundle(
    participant: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load OneStop lacclab IA + fixation reports from `$ONESTOP_DATA_DIR`.

    Fast path — when `participant` is given and per-pid shards exist under
    `<ONESTOP_DATA_DIR>/by_pid/{ia,fixations}/<pid>.parquet`, load just that
    one participant (sub-second). Shards are generated by
    `python -m scanpath_studio.onestop_shard --data-dir <ONESTOP_DATA_DIR>`.

    Slow path — fall back to loading the full CSV.zip exports (~3 min, ~60 GB
    RAM for the L2 cohort). Used when no participant is specified, or when
    a deep link points at a pid whose shard hasn't been generated yet.
    """
    base = onestop_data_dir()
    if base is None:
        return pd.DataFrame(), pd.DataFrame()

    # Fast path: per-pid shards.
    if participant:
        ia_shard, fix_shard = _onestop_shard_paths(base, participant)
        ia_present = ia_shard.exists()
        fix_present = fix_shard.exists()
        if ia_present and fix_present:
            return pd.read_parquet(ia_shard), pd.read_parquet(fix_shard)
        # NEVER fall through to the 15 GB load when a participant is named —
        # the deep link is for one pid only, so loading the whole cohort just
        # to discover the pid still has no data is pure waste. Surface a clear
        # error and stop. Common cause: pid was excluded from the IA report
        # (no exported reading data), or shards haven't been generated yet.
        missing = [
            p.name
            for p, ok in [(ia_shard, ia_present), (fix_shard, fix_present)]
            if not ok
        ]
        st.error(
            f"No scanpath data for participant {participant!r}. "
            f"Missing shards: {', '.join(missing)}. "
            f"If the pid was added since the last shard run, regenerate with: "
            f"`python -m scanpath_studio.onestop_shard --data-dir <ONESTOP_DATA_DIR>`. "
            f"Pids with no IA report (e.g. metadata-status excluded) cannot be visualized."
        )
        st.stop()

    # Slow path: full CSV.zip load.
    ia_path = base / "ia_Paragraph.csv.zip"
    fix_path = base / "fixations_Paragraph.csv.zip"
    if not ia_path.exists() or not fix_path.exists():
        st.error(
            f"OneStop data not found under {base}. Expected ia_Paragraph.csv.zip + "
            f"fixations_Paragraph.csv.zip."
        )
        return pd.DataFrame(), pd.DataFrame()
    words = pd.read_csv(ia_path, low_memory=False)
    fixations = pd.read_csv(fix_path, low_memory=False)
    return words, fixations


# ---------------------------------------------------------------------------
# Server-side MultiplEYE data source.
#
# When the env var `MULTIPLEYE_DATA_DIR` points at a MultiplEYE **raw export
# root** (e.g. `MultiplEYE_ZH_CH_Zurich_1_2025`, with per-session subfolders
# under `scanpaths/` and `fixations/`), `load_multipleye_server_bundle()`
# returns the (words, fixations) raw frames the rest of the pipeline expects.
#
# It reuses the *exact same* native loader as the "MultiplEYE — multilingual
# reading (ZH-CH sample)" public dataset (`datasets.multipleye_raw_frames` on
# the raw export), so it renders identically — proper word boxes / page layout /
# image-origin coordinate offsets. We do NOT read any reshaped per-pid parquet:
# those mangle the page/coordinate layout. The MultiplEYE column schema is then
# applied the same way the public source applies it — via `prepare_data`
# auto-detection in app.py, plus the authoritative 1920x1080 monitor snap (the
# image-origin offsets are baked into the frames' coordinate columns here).
#
# Mirrors the OneStop server bundle above: drives the "MultiplEYE server bundle"
# data source option in app.py, used by an external review-app deep-link
# integration (single pid+trial into this UI). Distinct from — but shares the
# loader with — the MultiplEYE *public corpus* source (`app._load_multipleye_source`).
# ---------------------------------------------------------------------------

MULTIPLEYE_DATA_DIR_ENV = "MULTIPLEYE_DATA_DIR"
# scanpaths/ fixations are pre-tagged with page + word index (richer than the
# raw fixations/ source) — the same default the public MultiplEYE source uses.
MULTIPLEYE_BUNDLE_FIXATION_SOURCE = "scanpaths"


def multipleye_bundle_dir() -> Optional[Path]:
    """Resolved MultiplEYE raw-export root from `$MULTIPLEYE_DATA_DIR`, or `None`.

    Points at the raw export root (the dir holding `scanpaths/`/`fixations/`
    per-session subfolders), NOT a reshaped per-pid parquet dir."""
    raw = os.environ.get(MULTIPLEYE_DATA_DIR_ENV, "").strip()
    if not raw:
        from .constants import MULTIPLEYE_BUNDLE_DEFAULT_DIR

        raw = MULTIPLEYE_BUNDLE_DEFAULT_DIR.strip()
    return Path(raw) if raw else None


def _resolve_multipleye_session(
    root: Path, participant: str, fixation_source: str
) -> Optional[str]:
    """Match a (possibly lowercased) deep-link pid to a real export session id.

    The review app passes the session label lowercased (e.g. `001_zh_ch_1_et2`),
    while the export's folder/inventory ids are uppercase (`001_ZH_CH_1_ET2`).
    Resolve case-insensitively to the canonical id `multipleye_raw_frames`
    expects; `None` if no session matches."""
    from .datasets import multipleye_inventory

    sessions, _ = multipleye_inventory(root, fixation_source=fixation_source)
    want = participant.strip().lower()
    for sess in sessions:
        if sess.lower() == want:
            return sess
    return None


@st.cache_data(show_spinner="Loading MultiplEYE server bundle…")
def load_multipleye_server_bundle(
    participant: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load MultiplEYE raw (words, fixations) frames from the `$MULTIPLEYE_DATA_DIR`
    raw export, via the same native loader as the public MultiplEYE source.

    Fast path — when `participant` is given (the deep-link case), resolve the
    session id case-insensitively from the export inventory and load only that
    one session.

    Slow path — when no participant is given, load every session in the export.

    Returns raw (pre-normalization) frames exactly like
    `app._load_multipleye_source` does; the app auto-detects the MultiplEYE
    schema and snaps the canvas to the 1920x1080 monitor. Returns empty frames
    when the dir / sessions are missing — the caller falls back to demo data.
    """
    base = multipleye_bundle_dir()
    if base is None or not base.is_dir():
        return pd.DataFrame(), pd.DataFrame()

    from .datasets import multipleye_raw_frames

    fixation_source = MULTIPLEYE_BUNDLE_FIXATION_SOURCE

    # Fast path: one session, resolved from the deep-link pid.
    if participant:
        session = _resolve_multipleye_session(base, participant, fixation_source)
        if session is None:
            # A named participant means a one-session deep link — surface a clear
            # error rather than silently loading the whole corpus.
            st.error(
                f"No MultiplEYE session matching participant {participant!r} "
                f"under {base / fixation_source}."
            )
            st.stop()
        try:
            return multipleye_raw_frames(
                base,
                sessions=[session],
                stimuli=None,
                fixation_source=fixation_source,
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            st.error(f"Couldn't load MultiplEYE session {session!r}: {exc}")
            st.stop()

    # Slow path: every session in the export.
    try:
        return multipleye_raw_frames(
            base,
            sessions=None,
            stimuli=None,
            fixation_source=fixation_source,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        st.error(
            f"MultiplEYE export not found under {base}: {exc} Expected a raw "
            f"export root with `scanpaths/` / `fixations/` per-session subfolders."
        )
        return pd.DataFrame(), pd.DataFrame()


def _norm_col(name) -> str:
    """Fold a column name to its case- and separator-insensitive key.

    Lowercases and drops every non-alphanumeric char, so ``IA_LEFT``,
    ``ia_left``, ``Ia-Left`` and ``ia left`` all collapse to ``ialeft`` —
    letting auto-detection match real-world column names that differ only in
    capitalization or word separators."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def pick_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    """Return the first matching column name from a candidate list.

    Matching is case- and separator-insensitive (see ``_norm_col``). Candidate
    order is still priority order — the first candidate with any match wins (so
    EyeLink names keep beating Gazepoint), and among equally-normalized columns
    the leftmost one wins."""
    lookup: Dict[str, str] = {}
    for col in df.columns:
        lookup.setdefault(_norm_col(col), col)
    for name in candidates:
        hit = lookup.get(_norm_col(name))
        if hit is not None:
            return hit
    return None


def trial_mapping_columns(trial_mapping) -> list:
    """Column list behind a trial mapping — a plain column name or a list of
    names (the column-mapping UI returns a list when the user composes a
    unique trial ID from several columns)."""
    if isinstance(trial_mapping, str):
        return [trial_mapping]
    return list(trial_mapping)


def trial_id_series(source: pd.DataFrame, trial_mapping) -> pd.Series:
    """Trial-id values for a single-column or composite (multi-column) mapping.

    A multi-column mapping builds a unique trial ID on the fly by joining the
    columns' string values with ``_`` — for datasets that ship no precomputed
    unique-trial column (e.g. OneStop-style participant + paragraph +
    repeated-reading)."""
    cols = trial_mapping_columns(trial_mapping)
    if len(cols) == 1:
        return source[cols[0]].astype(str)
    return source[cols].astype(str).agg("_".join, axis=1)


def _preserve_composite_columns(
    df: pd.DataFrame, source: pd.DataFrame, trial_mapping
) -> pd.DataFrame:
    """Carry a composite mapping's source columns into the normalized frame
    under their original names.

    A multi-column trial mapping gets joined into a single opaque ``trial_id``
    (e.g. ``2_1_1_Ele_l37_1129_False``). Keeping the individual component
    columns lets the trial picker offer one cascading selector per part —
    mirroring the Text / Participant modes (see
    ``utils._select_trial_composite_mode``). No-op for single-column mappings.
    Rows are 1:1 with ``source`` here (no filtering in the composite path), so a
    positional copy stays aligned."""
    cols = trial_mapping_columns(trial_mapping)
    if len(cols) < 2:
        return df
    for col in cols:
        if col not in df.columns and col in source.columns:
            df[col] = source[col].to_numpy()
    return df


# Candidate column names checked during auto-inference. Centralised so the
# proposal step and the override UI share the same defaults. Matching is case-
# and separator-insensitive (see ``pick_column``), so these list only *distinct*
# conventions — no ALL_CAPS / snake_case twins of the same name needed.
PARTICIPANT_CANDIDATES = [
    "participant_id",
    "subject_id",
    "participant",
    "recording_session_label",
    "reader_id",
]
TRIAL_CANDIDATES = [
    "unique_trial_id",
    "trial_id",
    "unique_paragraph_id",
    "paragraph_id",
    "text_id",
    "trial",
    "trial_index",
]
# Source column names that identify which *text* (passage) a row belongs to.
# Output canonical column is `text_id` (was `paragraph_id`); the source names stay
# as the real-world conventions so auto-detection keeps working.
TEXT_ID_CANDIDATES = [
    "unique_paragraph_id",
    "paragraph_id",
    "unique_text_id",
    "text_id",
]
TEXT_CANDIDATES = [
    "text",
    "IA_LABEL",
    "label",
    "word",
    "content",
    "token",
]
# `word_idx` / `char_idx` are MultiplEYE's word- and character-level indices
# (word_idx first so word-level boxes win over per-character ones).
WORD_ID_CANDIDATES = [
    "word_id",
    "IA_ID",
    "ia_index",
    "word_index",
    "aoi",
    "word_idx",
    "char_idx",
]
LINE_CANDIDATES = ["line_idx", "line", "line_index", "IA_LINE_ID"]

# `top_left_x` / `top_left_y` are MultiplEYE's box origin (paired with width/height).
WORD_X_CANDIDATES = ["x", "left", "top_left_x"]
WORD_Y_CANDIDATES = ["y", "top", "top_left_y"]
WORD_WIDTH_CANDIDATES = ["width"]
WORD_HEIGHT_CANDIDATES = ["height"]
WORD_LEFT_CANDIDATES = ["IA_LEFT", "left", "start_x", "top_left_x"]
WORD_RIGHT_CANDIDATES = ["IA_RIGHT", "right", "end_x"]
WORD_TOP_CANDIDATES = ["IA_TOP", "top", "start_y", "top_left_y"]
WORD_BOTTOM_CANDIDATES = ["IA_BOTTOM", "bottom", "end_y"]

# `location_x` / `location_y` are MultiplEYE's fixation pixel coordinates.
FIX_X_CANDIDATES = ["x", "CURRENT_FIX_X", "FPOGX", "location_x"]
FIX_Y_CANDIDATES = ["y", "CURRENT_FIX_Y", "FPOGY", "location_y"]
FIX_DURATION_CANDIDATES = [
    "duration_ms",
    "CURRENT_FIX_DURATION",
    "CURRENT_FIX_LEN",
    "duration",
    "fixation_duration",
]
FIX_TIMESTAMP_CANDIDATES = [
    "timestamp_ms",
    "CURRENT_FIX_START",
    "CURRENT_FIX_START_TIME",
    "CURRENT_FIX_TIME",
    "CURRENT_FIX_ONSET",
    "onset",  # MultiplEYE fixation onset (ms)
]
FIX_FIXATION_ID_CANDIDATES = [
    "fixation_id",
    "CURRENT_FIX_INDEX",
    "CURRENT_FIX_NUM",
    "fixation_index",
]
FIX_WORD_ID_CANDIDATES = [
    "word_id",
    "IA_ID",
    "CURRENT_FIX_INTEREST_AREA_ID",
    "CURRENT_FIX_INTEREST_AREA_INDEX",
    "word_index_in_text",
    "word_index",
    "word_idx",  # MultiplEYE word index (resets per page)
    "char_idx",  # MultiplEYE character index
]
RAW_GAZE_X_CANDIDATES = ["x", "FPOGX", "gaze_x"]
RAW_GAZE_Y_CANDIDATES = ["y", "FPOGY", "gaze_y"]
RAW_GAZE_TIMESTAMP_CANDIDATES = [
    "timestamp",
    "time",
    "ms",
    "timestamp_ms",
    "time_ms",
]


def propose_word_schema(words: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Return a candidate column mapping for words/IA data without erroring."""
    return dict(
        participant=pick_column(words, PARTICIPANT_CANDIDATES),
        trial=pick_column(words, TRIAL_CANDIDATES),
        text_id=pick_column(words, TEXT_ID_CANDIDATES),
        word_id=pick_column(words, WORD_ID_CANDIDATES),
        text=pick_column(words, TEXT_CANDIDATES),
        line=pick_column(words, LINE_CANDIDATES),
        x=pick_column(words, WORD_X_CANDIDATES),
        y=pick_column(words, WORD_Y_CANDIDATES),
        width=pick_column(words, WORD_WIDTH_CANDIDATES),
        height=pick_column(words, WORD_HEIGHT_CANDIDATES),
        left=pick_column(words, WORD_LEFT_CANDIDATES),
        right=pick_column(words, WORD_RIGHT_CANDIDATES),
        top=pick_column(words, WORD_TOP_CANDIDATES),
        bottom=pick_column(words, WORD_BOTTOM_CANDIDATES),
    )


def propose_fix_schema(fixations: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Return a candidate column mapping for fixations data without erroring.

    pass_index / saccade_type / saccade_amplitude / eye are not schema fields —
    they're auto-detected and kept via ``FIX_OPTIONAL_FIELDS`` (and offered under
    *fields to keep*), so they're not proposed here."""
    return dict(
        participant=pick_column(fixations, PARTICIPANT_CANDIDATES),
        trial=pick_column(fixations, TRIAL_CANDIDATES),
        text_id=pick_column(fixations, TEXT_ID_CANDIDATES),
        fixation_id=pick_column(fixations, FIX_FIXATION_ID_CANDIDATES),
        timestamp=pick_column(fixations, FIX_TIMESTAMP_CANDIDATES),
        duration=pick_column(fixations, FIX_DURATION_CANDIDATES),
        x=pick_column(fixations, FIX_X_CANDIDATES),
        y=pick_column(fixations, FIX_Y_CANDIDATES),
        word_id=pick_column(fixations, FIX_WORD_ID_CANDIDATES),
    )


def propose_raw_gaze_schema(raw_gaze: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Return a candidate column mapping for raw gaze data without erroring."""
    return dict(
        participant=pick_column(raw_gaze, PARTICIPANT_CANDIDATES),
        trial=pick_column(raw_gaze, TRIAL_CANDIDATES),
        text=pick_column(raw_gaze, TEXT_CANDIDATES),
        x=pick_column(raw_gaze, RAW_GAZE_X_CANDIDATES),
        y=pick_column(raw_gaze, RAW_GAZE_Y_CANDIDATES),
        timestamp=pick_column(raw_gaze, RAW_GAZE_TIMESTAMP_CANDIDATES),
    )


def validate_word_schema(schema: Dict[str, Optional[str]]) -> list:
    """Return a list of human-readable problems with a words/IA schema.

    Participant ID is optional: word/AoI tables without one are treated as
    stimulus-level (one row per word per *text*, not per reading) and are
    broadcast across the participants found in the fixations — see
    ``broadcast_stimulus_words``."""
    problems = []
    for key, label in [
        ("trial", "Trial ID"),
        ("word_id", "Word/IA ID"),
    ]:
        if not schema.get(key):
            problems.append(f"missing {label}")
    has_xywh = all(schema.get(k) for k in ["x", "y", "width", "height"])
    has_box = all(schema.get(k) for k in ["left", "right", "top", "bottom"])
    if not has_xywh and not has_box:
        problems.append(
            "need either (x, y, width, height) or (left, right, top, bottom)"
        )
    return problems


def validate_fix_schema(schema: Dict[str, Optional[str]]) -> list:
    """Return a list of human-readable problems with a fixations schema.

    X/Y coordinates are optional when a Word/IA ID is mapped: AOI-sequence
    datasets (fixations recorded as "which word", not "which pixel") get
    coordinates from the matching word-box centers — see
    ``fill_fixation_xy_from_words``."""
    problems = []
    # Participant is optional — a dataset without it is treated as a single
    # anonymous reader (see SYNTHETIC_PARTICIPANT).
    for key, label in [
        ("trial", "Trial ID"),
        ("duration", "Duration"),
    ]:
        if not schema.get(key):
            problems.append(f"missing {label}")
    has_xy = schema.get("x") and schema.get("y")
    if not has_xy and not schema.get("word_id"):
        problems.append(
            "need either (X, Y) coordinates or a Word/IA ID "
            "(AOI-only fixations are placed at word-box centers)"
        )
    return problems


def validate_raw_gaze_schema(schema: Dict[str, Optional[str]]) -> list:
    """Return a list of human-readable problems with a raw gaze schema."""
    problems = []
    # Participant optional — single anonymous reader when absent.
    for key, label in [
        ("trial", "Trial ID"),
        ("x", "X"),
        ("y", "Y"),
    ]:
        if not schema.get(key):
            problems.append(f"missing {label}")
    return problems


# Column added when concatenating several files (multi-file upload, glob, or a
# multi-member zip): the source file's stem. Lets datasets that key metadata in
# the *filename* (one file per participant and/or per text, e.g. PoTeC's
# `reader0_b0_scanpath.tsv`) recover it after concatenation — map it as (part
# of) the Trial/Participant ID.
SOURCE_FILE_COLUMN = "source_file"

# Prefix for the positional columns split out of `source_file` by
# `split_source_file` (file_part_1, file_part_2, …).
FILE_PART_PREFIX = "file_part_"

TablesInput = Union[str, os.PathLike, object, List]


def split_source_file(
    df: pd.DataFrame,
    *,
    delimiter: str = "_",
    column: str = SOURCE_FILE_COLUMN,
    prefix: str = FILE_PART_PREFIX,
) -> pd.DataFrame:
    """Split a ``source_file`` column into positional ``file_part_N`` columns.

    Lets the upload wizard derive a trial / participant id from a structured
    filename when no data column carries it — e.g. ``reader0_b0_scanpath`` split
    on ``_`` yields ``file_part_1=reader0``, ``file_part_2=b0``,
    ``file_part_3=scanpath`` (the user then maps the relevant part(s), composing
    several if needed). Returns ``df`` unchanged if ``column`` is absent or
    ``delimiter`` is empty. Rows with fewer parts get empty strings for the
    missing tail, so every row has the same part columns."""
    if column not in df.columns or not delimiter:
        return df
    parts = (
        df[column].astype(str).str.split(delimiter, expand=True, regex=False).fillna("")
    )
    df = df.copy()
    for i in range(parts.shape[1]):
        df[f"{prefix}{i + 1}"] = parts[i].to_numpy()
    return df


def extract_columns_from_source_file(
    df: pd.DataFrame,
    pattern: str,
    *,
    column: str = SOURCE_FILE_COLUMN,
    lowercase: bool = False,
) -> pd.DataFrame:
    """Add one column per *named group* of a regex applied to ``source_file``.

    Sibling of :func:`split_source_file` for filenames whose fields are
    positionally irregular — varying-length parts or an optional prefix make a
    fixed delimiter split unreliable. A regex with named groups, e.g.
    ``r"(?P<session>\\d+_\\w+_ET\\d)_.*_(?P<stimulus>.+)_scanpath"``, extracts each
    group into its own column the wizard can then map as a trial / participant id.
    ``lowercase`` folds the captured values (useful when one table names a field
    CamelCase and another lowercase). No-op (returns ``df`` unchanged) when
    ``column`` is absent, ``pattern`` is empty / uncompilable, or it declares no
    named groups; rows that don't match get NaN. A named group that collides with
    an existing column is **skipped** (the real data wins) — see
    :func:`source_file_regex_collisions` to surface those in a UI."""
    if not pattern or column not in df.columns:
        return df
    try:
        compiled = re.compile(pattern)
    except re.error:
        return df
    if not compiled.groupindex:
        return df
    extracted = df[column].astype(str).str.extract(compiled)
    df = df.copy()
    for group in compiled.groupindex:  # named groups only
        if group in df.columns:  # don't clobber an existing data column
            continue
        values = extracted[group]
        if lowercase:
            values = values.str.lower()
        df[group] = values.to_numpy()
    return df


def source_file_regex_collisions(df: pd.DataFrame, pattern: str) -> list:
    """Named groups of ``pattern`` that already exist as columns in ``df``.

    :func:`extract_columns_from_source_file` skips these (so it never clobbers
    real data); the wizard surfaces them so the user can rename the group."""
    if not pattern:
        return []
    try:
        groups = re.compile(pattern).groupindex
    except re.error:
        return []
    return [g for g in groups if g in df.columns]


def aggregate_char_boxes(
    df: pd.DataFrame, schema: Dict[str, Optional[str]]
) -> pd.DataFrame:
    """Collapse character-level AOI rows into one bounding box per word.

    For interest-area tables shipped one row per *character* (e.g. CJK corpora
    that have no whitespace word boundaries), aggregate the characters of each
    word — grouped by the mapped trial id + word id (plus participant / text id
    when mapped) — into a single bounding box: min/max over the mapped box columns,
    first value of every other column. Run this on the RAW frame *before*
    :func:`normalize_words` (which expects one row per word box). ``schema`` is a
    word schema dict (field → source column). Returns ``df`` unchanged when the
    trial or word-id column isn't mapped, or no box columns are."""
    word_col = schema.get("word_id")
    trial = schema.get("trial")
    if not word_col or not trial:
        return df
    group_cols = list(trial_mapping_columns(trial))
    for key in ("participant", "text_id"):
        mapped = schema.get(key)
        if mapped:
            group_cols += trial_mapping_columns(mapped)
    group_cols.append(word_col)
    # De-dup, keep only columns actually present, and require the word id.
    group_cols = [c for c in dict.fromkeys(group_cols) if c in df.columns]
    if word_col not in group_cols:
        return df

    has_xywh = all(schema.get(k) for k in ("x", "y", "width", "height"))
    has_edges = all(schema.get(k) for k in ("left", "right", "top", "bottom"))
    if not has_xywh and not has_edges:
        return df

    df = df.copy()
    if has_xywh:
        left = pd.to_numeric(df[schema["x"]], errors="coerce")
        top = pd.to_numeric(df[schema["y"]], errors="coerce")
        df["_box_l"], df["_box_t"] = left, top
        df["_box_r"] = left + pd.to_numeric(df[schema["width"]], errors="coerce")
        df["_box_b"] = top + pd.to_numeric(df[schema["height"]], errors="coerce")
    else:
        df["_box_l"] = pd.to_numeric(df[schema["left"]], errors="coerce")
        df["_box_r"] = pd.to_numeric(df[schema["right"]], errors="coerce")
        df["_box_t"] = pd.to_numeric(df[schema["top"]], errors="coerce")
        df["_box_b"] = pd.to_numeric(df[schema["bottom"]], errors="coerce")

    temp = {"_box_l", "_box_r", "_box_t", "_box_b"}
    agg = {c: "first" for c in df.columns if c not in group_cols and c not in temp}
    agg.update(_box_l="min", _box_t="min", _box_r="max", _box_b="max")
    out = df.groupby(group_cols, sort=False, as_index=False).agg(agg)

    # Write the aggregated box back into the SAME schema columns so the existing
    # word schema still maps it (origin+size or edges, matching the input form).
    if has_xywh:
        out[schema["x"]] = out["_box_l"]
        out[schema["y"]] = out["_box_t"]
        out[schema["width"]] = out["_box_r"] - out["_box_l"]
        out[schema["height"]] = out["_box_b"] - out["_box_t"]
    else:
        out[schema["left"]] = out["_box_l"]
        out[schema["right"]] = out["_box_r"]
        out[schema["top"]] = out["_box_t"]
        out[schema["bottom"]] = out["_box_b"]
    return out.drop(columns=list(temp))


def _read_by_extension(buf, name: str) -> pd.DataFrame:
    """Dispatch a buffer/path to a pandas reader by its (lowercased) name.

    CSV/TSV reads pass ``low_memory=False`` so pandas infers one dtype per
    column in a single pass. The default chunked parser can otherwise read the
    same column as numeric in early chunks and as strings in a later chunk that
    holds a sentinel (e.g. EyeLink's ``.`` in ``CURRENT_FIX_PRECISION_MEASURE_*``
    columns), leaving a single ``object`` column that mixes Python ``float`` and
    ``str`` values. Such a column emits a ``DtypeWarning`` and later crashes
    pyarrow when Streamlit serializes the frame for display — only on large
    (multi-chunk) files, which is why a small upload reads fine locally but a
    full report kills the worker on the cloud. Matches the other read paths
    (``load_onestop_server_bundle``, ``onestop_shard``)."""
    if name.endswith(".parquet"):
        return pd.read_parquet(buf)
    if name.endswith(".feather"):
        return pd.read_feather(buf)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(buf)  # first sheet (e.g. MultiplEYE questions workbook)
    if name.endswith((".tsv", ".tab")):
        return pd.read_csv(buf, sep="\t", low_memory=False)
    return pd.read_csv(buf, low_memory=False)


def _tag_and_concat(
    frames: List[pd.DataFrame],
    labels: List[str],
    source_column: Optional[str],
    *,
    always_tag: bool = False,
) -> pd.DataFrame:
    """Concatenate frames into one, tagging each with its source label in
    ``source_column`` (unless that frame already carries the column, or
    ``source_column`` is None) so rows stay traceable to their origin.

    By default only multi-frame reads are tagged (a lone frame needs no origin
    marker). ``always_tag=True`` tags a single frame too — used by
    :func:`read_tables` so a one-file upload still exposes its filename (as
    ``source_file``), which the upload wizard can map as the trial / participant
    id when no column carries it. Columns are aligned by name; fields absent
    from a frame become NaN for its rows."""
    if source_column and (always_tag or len(frames) > 1):
        for df, label in zip(frames, labels):
            if source_column not in df.columns:
                df[source_column] = label
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True, sort=False)


# DATA-16 (security review S6): bound zip decompression. `_read_zipped_table`
# used to `read()` every member with no ceiling, so a small archive of highly
# compressible CSV could expand to many gigabytes and OOM-kill the process — on
# the ~1 GB hosted demo that takes every concurrent visitor's session with it.
# The limits are deliberately generous: real eye-tracking exports are large (the
# OneStop reports are hundreds of MB to a few GB of CSV per zipped table), so the
# absolute caps only catch the honestly-enormous case, and the *ratio* is what
# actually distinguishes a zip bomb from a big corpus.
ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES = 4 * 1024**3  # 4 GB for any single member
ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES = 8 * 1024**3  # 8 GB across the whole archive
ZIP_MAX_COMPRESSION_RATIO = 200.0  # uncompressed / compressed
# Below this the ratio is not checked at all: a small but very repetitive table
# can legitimately compress 1000×, and expanding it costs nothing.
ZIP_RATIO_CHECK_MIN_BYTES = 256 * 1024 * 1024


def _format_bytes(n: float) -> str:
    """Human-readable byte size for a user-facing error message."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def _check_zip_limits(infos: List[zipfile.ZipInfo]) -> None:
    """Reject an archive that would decompress past the DATA-16 limits.

    Checks the *declared* sizes (``ZipInfo.file_size``) before a single member is
    opened, so an oversized archive fails fast instead of being discovered by
    exhausting RAM. Declared sizes can be forged, so :func:`_read_zipped_table`
    additionally reads each member under a hard byte budget.
    """
    total = sum(int(i.file_size) for i in infos)
    compressed = sum(int(i.compress_size) for i in infos)
    for info in infos:
        if int(info.file_size) > ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES:
            raise ValueError(
                f"{info.filename!r} in the zip archive expands to "
                f"{_format_bytes(info.file_size)}, above the per-file limit of "
                f"{_format_bytes(ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES)}. Unzip it "
                "and load the table directly, or split it into smaller files."
            )
    if total > ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise ValueError(
            f"the zip archive expands to {_format_bytes(total)}, above the "
            f"{_format_bytes(ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES)} decompression "
            "limit. Unzip it and load the tables directly, or split the archive."
        )
    if total >= ZIP_RATIO_CHECK_MIN_BYTES:
        ratio = total / max(compressed, 1)
        if ratio > ZIP_MAX_COMPRESSION_RATIO:
            raise ValueError(
                f"the zip archive expands {ratio:.0f}× (to "
                f"{_format_bytes(total)}), above the "
                f"{ZIP_MAX_COMPRESSION_RATIO:.0f}× limit — it doesn't look like "
                "a normal data export. Unzip it and load the tables directly if "
                "this is genuine."
            )


def _read_zipped_table(file_like_or_path) -> pd.DataFrame:
    """Read table(s) from a ``.zip`` archive (e.g. ``data.csv.zip``).

    Each member is dispatched on its own extension, so a zip may wrap any
    supported format. A multi-member archive is concatenated just like a
    multi-file upload — every member's rows tagged with its stem in
    ``source_file``. pandas infers compression only from string paths, not from
    uploaded file-like objects, so we open the archive ourselves. Raises
    ``ValueError`` if the archive holds no data file (macOS ``__MACOSX``/dotfile
    cruft is ignored), or if it would decompress past the DATA-16 size limits
    (``ZIP_MAX_*``) — both the declared sizes and the bytes actually read are
    bounded, so a forged header can't slip past."""
    with zipfile.ZipFile(file_like_or_path) as zf:
        infos = [
            i
            for i in zf.infolist()
            if not i.is_dir() and not Path(i.filename).name.startswith((".", "__"))
        ]
        if not infos:
            raise ValueError("the zip archive contains no readable table files")
        _check_zip_limits(infos)
        remaining = ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES
        frames, labels = [], []
        for info in infos:
            member = info.filename
            with zf.open(info) as inner:
                # Read one byte past the budget: if we get it, the member lied
                # about its declared size and the archive is rejected.
                payload = inner.read(remaining + 1)
            if len(payload) > remaining:
                raise ValueError(
                    f"{member!r} in the zip archive decompresses past the "
                    f"{_format_bytes(ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES)} limit "
                    "(its declared size was wrong). Refusing to read it."
                )
            remaining -= len(payload)
            frames.append(_read_by_extension(io.BytesIO(payload), member.lower()))
            labels.append(Path(member).stem)
    return _tag_and_concat(frames, labels, SOURCE_FILE_COLUMN)


# BUG-5: guard the memory-constrained hosted demo against a too-large upload.
# The bytes upload fine; the OOM comes later, when a big (often zipped) table
# decompresses and pandas holds several copies through parse + normalization —
# on Streamlit Community Cloud (~1 GB RAM) that silently kills the process with
# no traceback. Above this raw-upload size the wizard warns and asks for an
# explicit opt-in before parsing (a one-click confirm locally, real protection on
# the host). Tuned to sit below the OneStop repeated-reading export
# (~29–37 MB per zipped table) that first surfaced this.
UPLOAD_SIZE_WARN_BYTES = 25 * 1024 * 1024


def uploaded_files_total_bytes(uploaded) -> int:
    """Total byte size of a Streamlit upload — one ``UploadedFile`` or a list.

    Reads the ``.size`` each file already carries (no data copy). ``None`` /
    empty → 0, so an absent upload is trivially under any threshold."""
    if not uploaded:
        return 0
    files = uploaded if isinstance(uploaded, (list, tuple)) else [uploaded]
    return sum(int(getattr(f, "size", 0) or 0) for f in files)


def upload_exceeds_limit(
    uploaded, threshold_bytes: int = UPLOAD_SIZE_WARN_BYTES
) -> bool:
    """Whether a Streamlit upload's total size is over the guard threshold (BUG-5)."""
    return uploaded_files_total_bytes(uploaded) > threshold_bytes


def read_table(file_like_or_path) -> pd.DataFrame:
    """Read a tabular file by extension: csv, tsv, parquet, feather, or a
    ``.zip`` wrapping one or more of those (e.g. ``data.csv.zip``). A
    multi-member zip is concatenated like a multi-file upload."""
    name = getattr(file_like_or_path, "name", str(file_like_or_path)).lower()
    if name.endswith(".zip"):
        return _read_zipped_table(file_like_or_path)
    return _read_by_extension(file_like_or_path, name)


def expand_table_inputs(inputs: TablesInput) -> list:
    """Flatten a path / glob pattern / file-like / list-of-those into a list.

    Glob patterns are expanded in sorted order so multi-file datasets (one
    file per participant or per stimulus) can be referenced with a single
    pattern like ``scanpaths/*.tsv``. Raises ``FileNotFoundError`` for a
    pattern that matches nothing — silently loading zero files would read as
    success."""
    if not isinstance(inputs, (list, tuple)):
        inputs = [inputs]
    expanded: list = []
    for item in inputs:
        if isinstance(item, (str, os.PathLike)) and glob.has_magic(str(item)):
            matches = sorted(glob.glob(str(item), recursive=True))
            if not matches:
                raise FileNotFoundError(f"No files match pattern: {item}")
            expanded.extend(matches)
        else:
            expanded.append(item)
    return expanded


def read_tables(
    inputs: TablesInput, source_column: Optional[str] = SOURCE_FILE_COLUMN
) -> pd.DataFrame:
    """Read one or many tabular files and concatenate them into one frame.

    ``inputs`` may be a single path or file-like object, a glob pattern, or a
    list mixing those (a ``.zip`` member counts as a file too). Each part gets a
    ``source_file`` column holding the file's stem (unless the data already has
    that column, or ``source_column=None``) — *including a single file*, so
    datasets that key identity in the filename can recover it (the upload wizard
    maps ``source_file`` as the trial / participant id). Columns are aligned by
    name across files; fields absent from a file become NaN for its rows."""
    items = expand_table_inputs(inputs)
    frames, labels = [], []
    for item in items:
        frames.append(read_table(item))
        labels.append(Path(getattr(item, "name", str(item))).stem)
    return _tag_and_concat(frames, labels, source_column, always_tag=True)


def _load_bundled(name: str) -> pd.DataFrame:
    """Load a single bundled sample, preferring Parquet over CSV."""
    data_root = resources.files(PACKAGE_NAME).joinpath("sample_data")
    for ext in (".parquet", ".csv"):
        resource = data_root / f"{name}{ext}"
        try:
            with resources.as_file(resource) as path:
                if not path.is_file():
                    continue
                return read_table(path)
        except FileNotFoundError:
            continue
    return pd.DataFrame()


def _resolve_sample_image_paths(df: pd.DataFrame) -> pd.DataFrame:
    """Expand the bundled demo's relative ``image_path`` (e.g.
    ``images/2_2_1_Adv__paragraph.png``) into an absolute path under the
    packaged ``sample_data`` directory, so the stimulus-image background layer
    (``tabs._render_single_trial`` → ``plots.make_scanpath_figure``) can load it
    via ``os.path.exists``. The CSVs ship a *relative* reference (stable across
    installs); this resolves it at load time against wherever the wheel landed.
    No-op when the column is absent or a value is already absolute."""
    if "image_path" not in df.columns:
        return df
    try:
        root = Path(str(resources.files(PACKAGE_NAME).joinpath("sample_data")))
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        return df

    def _abs(value: object) -> object:
        if isinstance(value, str) and value and not os.path.isabs(value):
            return str(root.joinpath(*value.split("/")))
        return value

    df = df.copy()
    df["image_path"] = df["image_path"].map(_abs)
    return df


def resolve_stimulus_image_paths(
    frame: pd.DataFrame,
    root: Union[str, os.PathLike],
    pattern: str = "{text_id}.png",
    *,
    require_exists: bool = True,
) -> pd.DataFrame:
    """Attach per-row stimulus images from a local folder and filename pattern.

    Placeholders are read from the row (for example ``{text_id}``,
    ``{trial_id}``, or ``{participant_id}``). Relative subdirectories are
    supported, but resolved files must remain under ``root``; absolute and
    parent-traversal patterns are rejected. Rows whose placeholders are missing
    or whose file does not exist keep their previous ``image_path`` value.

    This pure helper is the headless/API surface for VIZ-14 and is also used by
    the desktop-only folder controls and the CLI.
    """
    if frame is None or frame.empty:
        return frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    base = Path(root).expanduser().resolve()
    if not pattern or Path(pattern).is_absolute():
        raise ValueError("Image filename pattern must be a non-empty relative path.")

    class _Row(dict):
        def __missing__(self, key):
            raise KeyError(key)

    def _resolved(row: pd.Series) -> object:
        previous = row.get("image_path")
        values = _Row(
            {str(key): str(value) for key, value in row.items() if pd.notna(value)}
        )
        try:
            relative = pattern.format_map(values)
        except (KeyError, ValueError, AttributeError):
            return previous
        candidate = (base / relative).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise ValueError(
                f"Image pattern resolves outside the selected folder: {relative!r}"
            ) from exc
        if require_exists and not candidate.is_file():
            return previous
        return str(candidate)

    result = frame.copy()
    result["image_path"] = result.apply(_resolved, axis=1)
    return result


@st.cache_data
def load_sample_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load bundled demo IA and fixation tables (prefer Parquet).

    The tables ship per-trial stimulus-image references (``image_path`` +
    ``image_x``/``image_y`` origin) pointing at the rendered paragraph PNGs
    under ``sample_data/images/``; the relative paths are resolved to absolute
    here so the optional stimulus-image background layer renders the page
    behind the scanpath (aligned to the 2560x1440 OneStop monitor)."""
    words = _resolve_sample_image_paths(_load_bundled("ia"))
    fixations = _resolve_sample_image_paths(_load_bundled("fixations"))
    if words.empty or fixations.empty:
        st.error(
            "Bundled sample data not found. Expected ia.{parquet,csv} and "
            "fixations.{parquet,csv} under the installed package's sample_data "
            "directory."
        )
        return pd.DataFrame(), pd.DataFrame()
    return words, fixations


@st.cache_data
def load_sample_raw_gaze() -> pd.DataFrame:
    """Load bundled raw gaze sample (millisecond-level x,y)."""
    return _load_bundled("raw_gaze")


def infer_raw_gaze_schema(raw_gaze: pd.DataFrame) -> Optional[Dict[str, str]]:
    """Infer schema for raw millisecond-level gaze data."""
    schema = propose_raw_gaze_schema(raw_gaze)
    problems = validate_raw_gaze_schema(schema)
    if problems:
        st.error(f"Missing required raw gaze fields: {', '.join(problems)}")
        return None
    return schema


def normalize_raw_gaze(raw_gaze: pd.DataFrame, schema: Dict[str, str]) -> pd.DataFrame:
    """Normalize raw gaze data to canonical column names."""
    df = pd.DataFrame(index=raw_gaze.index)
    if schema.get("participant"):
        # str or list (a composite participant id), joined like normalize_words —
        # so a composite participant stays key-compatible with the fixations.
        df["participant_id"] = trial_id_series(raw_gaze, schema["participant"])
    else:
        df["participant_id"] = SYNTHETIC_PARTICIPANT
    trial_cols = trial_mapping_columns(schema["trial"])
    if len(trial_cols) > 1:
        # User-composed unique trial ID — see normalize_words.
        df["trial_id"] = trial_id_series(raw_gaze, trial_cols)
        df["unique_trial_id"] = df["trial_id"]
    else:
        trial_col = (
            "unique_trial_id"
            if "unique_trial_id" in raw_gaze.columns
            else trial_cols[0]
        )
        df["trial_id"] = raw_gaze[trial_col].astype(str)
        if "unique_trial_id" in raw_gaze.columns:
            df["unique_trial_id"] = raw_gaze["unique_trial_id"].astype(str)
    # Raw gaze has no text/passage concept; mirror trial_id so a raw-gaze-only
    # dataset still works with the trial picker (utils.build_combo_options needs
    # a text_id column).
    df["text_id"] = df["trial_id"]
    if schema.get("text"):
        df["text"] = raw_gaze[schema["text"]].astype(str)
    else:
        df["text"] = ""
    df["x"] = pd.to_numeric(raw_gaze[schema["x"]], errors="coerce")
    df["y"] = pd.to_numeric(raw_gaze[schema["y"]], errors="coerce")
    if schema.get("timestamp"):
        df["timestamp_ms"] = pd.to_numeric(
            raw_gaze[schema["timestamp"]], errors="coerce"
        )
    else:
        # Each row represents one millisecond, so use row index within trial as timestamp
        df["timestamp_ms"] = df.groupby(["participant_id", "trial_id"]).cumcount()
    df = _preserve_composite_columns(df, raw_gaze, schema["trial"])
    return df


def infer_word_schema(words: pd.DataFrame) -> Optional[Dict[str, str]]:
    schema = propose_word_schema(words)
    problems = validate_word_schema(schema)
    if problems:
        st.error(f"Words/IA schema problems: {'; '.join(problems)}")
        return None
    return schema


def infer_fix_schema(fixations: pd.DataFrame) -> Optional[Dict[str, str]]:
    schema = propose_fix_schema(fixations)
    problems = validate_fix_schema(schema)
    if problems:
        st.error(f"Fixations schema problems: {'; '.join(problems)}")
        return None
    return schema


# Placeholder participant id for stimulus-level word/AoI tables (no participant
# column — one row per word per text, shared by every reading). The marker
# column flags the frame so broadcast_stimulus_words() knows to expand it.
STIMULUS_PARTICIPANT = ""
STIMULUS_WORDS_FLAG = "_stimulus_words"

# Synthetic participant id used when a dataset has no participant column at all
# (a single anonymous reader). Distinct from STIMULUS_PARTICIPANT ("") so it
# never collides with the stimulus-word broadcast machinery — participant_id is
# always present downstream (combos/filters/annotations/export/measures groupby),
# and the UI hides the participant selector when there's only this one value.
SYNTHETIC_PARTICIPANT = "(all)"


def broadcast_stimulus_words(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> pd.DataFrame:
    """Expand stimulus-level words across the participants who read each trial.

    Datasets like PoTeC ship word/AoI tables per *text* (no participant
    column) while fixations are per participant × text. After normalization,
    such words carry the ``_stimulus_words`` flag; this replicates each
    trial's word rows once per participant that has fixations for that
    ``trial_id``, so downstream (participant, trial) filtering works
    unchanged. Words for trials nobody read are dropped. No-op for ordinary
    per-participant word tables, or when there are no fixations to broadcast
    against (the stimulus rows then keep their placeholder participant)."""
    if STIMULUS_WORDS_FLAG not in words.columns:
        return words
    words = words.drop(columns=[STIMULUS_WORDS_FLAG])
    if words.empty or fixations.empty:
        # No fixations to broadcast across (e.g. a words-only dataset): there's a
        # single anonymous reader, so give the placeholder a real synthetic id.
        if not words.empty:
            words = words.copy()
            words["participant_id"] = SYNTHETIC_PARTICIPANT
        return words
    pairs = fixations[["participant_id", "trial_id"]].drop_duplicates()
    pairs["participant_id"] = pairs["participant_id"].astype(str)
    pairs["trial_id"] = pairs["trial_id"].astype(str)
    return words.drop(columns=["participant_id"]).merge(
        pairs, on="trial_id", how="inner"
    )


def fill_fixation_xy_from_words(
    fixations: pd.DataFrame, words: pd.DataFrame
) -> pd.DataFrame:
    """Fill missing fixation coordinates from the fixated word's box center.

    AOI-sequence datasets record *which* word/character each fixation landed
    on but not the pixel position. When normalized fixations have NaN x/y and
    a ``word_id``, place them at the center of the matching word box (keyed by
    participant_id + trial_id + word_id). Fixations whose word_id matches no
    box keep NaN coordinates. Rows that already have coordinates are left
    untouched."""
    if fixations.empty or words.empty:
        return fixations
    missing = fixations["x"].isna() | fixations["y"].isna()
    if not missing.any() or "word_id" not in fixations.columns:
        return fixations
    from .measures import word_box_bounds

    # BUG-11: place them at the *corrected* box centre, i.e. the glyph centre.
    x0, y0, x1, y1 = word_box_bounds(words)
    centers = words[["participant_id", "trial_id", "word_id"]].copy()
    centers["_word_cx"] = (x0 + x1) / 2.0
    centers["_word_cy"] = (y0 + y1) / 2.0
    centers = centers.drop_duplicates(["participant_id", "trial_id", "word_id"])
    merged = fixations[["participant_id", "trial_id", "word_id"]].merge(
        centers, on=["participant_id", "trial_id", "word_id"], how="left"
    )
    fixations = fixations.copy()
    fill = missing.to_numpy()
    fixations.loc[fill, "x"] = merged["_word_cx"].to_numpy()[fill]
    fixations.loc[fill, "y"] = merged["_word_cy"].to_numpy()[fill]
    return fixations


def _reconcile_participant_asymmetry(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> pd.DataFrame:
    """Re-key word boxes to the synthetic participant when the fixations have no
    participant but the words do.

    With participant now optional per table, a fixations table can be
    participant-less (every row stamped ``SYNTHETIC_PARTICIPANT``) while the words
    table still carries real participant ids. The trial picker keys off the
    fixations, so it offers ``(all)`` — but the boxes are keyed by the real ids
    and ``extract_trial`` then finds none, rendering fixations with no text. Stamp
    the words with the synthetic id (dropping the now-duplicate per-reader boxes)
    so they line up. No-op unless the fixations are entirely synthetic and the
    words are not — the stimulus-words broadcast already covers the reverse."""
    if words.empty or fixations.empty or "participant_id" not in words.columns:
        return words
    if set(fixations["participant_id"].unique()) != {SYNTHETIC_PARTICIPANT}:
        return words
    word_parts = set(words["participant_id"].unique())
    if not word_parts or word_parts == {SYNTHETIC_PARTICIPANT}:
        return words
    words = words.copy()
    words["participant_id"] = SYNTHETIC_PARTICIPANT
    subset = [
        c for c in ("participant_id", "trial_id", "word_id") if c in words.columns
    ]
    if subset:
        words = words.drop_duplicates(subset=subset)
    return words


_WORD_ID_AGGS = ["min", "max", "nunique"]


def _key_frame(frame: pd.DataFrame, ids: pd.Series) -> pd.DataFrame:
    """``(participant_id, trial_id, _id)`` view of ``frame``, aligned to ``ids``.

    ``ids`` is a NaN-dropped numeric word-id series taken from ``frame``, so the
    id columns are re-indexed onto its (subset) index.
    """
    return pd.DataFrame(
        {
            "participant_id": frame["participant_id"].reindex(ids.index),
            "trial_id": frame["trial_id"].reindex(ids.index),
            "_id": ids,
        }
    )


def detect_word_id_offset(words: pd.DataFrame, fixations: pd.DataFrame) -> int:
    """Detect a 1-based fixation ``word_id`` against 0-based word boxes (BUG-8).

    Some exports (the bundled OneStop demo among them) number the fixation
    report's word column ``1..N`` while the interest-area table numbers its rows
    ``0..N-1``, so every fixation's pre-assigned ``word_id`` points at the *next*
    word. ``measures.assign_fixations_to_words`` keeps existing ids, so the
    computed reading measures then attach to the wrong words.

    Returns the offset to **subtract** from the fixation word ids: ``1`` when the
    shift is unambiguous, ``0`` (by far the common case) otherwise. A false
    positive silently corrupts a correct dataset, so the test is deliberately
    strict — every condition below must hold across the whole dataset:

    * both frames carry whole-number ``word_id`` values,
    * the words ids start at ``0`` and the fixation ids start at ``1``,
    * *every* trial present in both frames has 0-based, gap-free word ids and no
      fixation id below ``1`` or more than one past its last word, and
    * at least one trial actually overflows by exactly one
      (``max fixation id == max word id + 1``) — without that there is no
      evidence of a shift, just a reader who never looked at the first word.
    """
    if words is None or fixations is None or words.empty or fixations.empty:
        return 0
    keys = ["participant_id", "trial_id"]
    needed = set(keys) | {"word_id"}
    if not needed.issubset(words.columns) or not needed.issubset(fixations.columns):
        return 0
    w_ids = pd.to_numeric(words["word_id"], errors="coerce").dropna()
    f_ids = pd.to_numeric(fixations["word_id"], errors="coerce").dropna()
    if w_ids.empty or f_ids.empty:
        return 0
    # Fractional ids (character-level indices, say) aren't a word numbering we
    # can reason about.
    if not (w_ids % 1 == 0).all() or not (f_ids % 1 == 0).all():
        return 0
    if float(w_ids.min()) != 0.0 or float(f_ids.min()) != 1.0:
        return 0
    # Project onto (keys + id) rather than .assign()-ing onto the source frames:
    # the OneStop words/fixations tables are wide, and this runs on every load.
    w_stats = (
        _key_frame(words, w_ids).groupby(keys, sort=False)["_id"].agg(_WORD_ID_AGGS)
    )
    f_stats = (
        _key_frame(fixations, f_ids)
        .groupby(keys, sort=False)["_id"]
        .agg(["min", "max"])
    )
    joined = w_stats.join(f_stats, how="inner", lsuffix="_w", rsuffix="_f")
    if joined.empty:
        return 0
    zero_based = joined["min_w"] == 0
    gap_free = joined["nunique"] == joined["max_w"] + 1
    in_range = joined["min_f"] >= 1
    overflow = joined["max_f"] == joined["max_w"] + 1
    runaway = joined["max_f"] > joined["max_w"] + 1
    if not (zero_based.all() and gap_free.all() and in_range.all()):
        return 0
    if runaway.any() or not overflow.any():
        return 0
    return 1


def correct_word_id_offset(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> pd.DataFrame:
    """Shift fixation ``word_id`` back onto the words table when it's 1-based.

    No-op unless :func:`detect_word_id_offset` finds an unambiguous shift.
    Renumbering someone's ids is never silent — it's logged at WARNING, which
    `debug_log.install_log_capture` surfaces in the in-app 🐛 Debug panel as
    well as the server terminal. A `st.warning` would be wrong here: the bundled
    demo corpus trips this on *every* load, so the banner would be permanent
    furniture on the default landing view rather than a signal.
    """
    offset = detect_word_id_offset(words, fixations)
    if not offset:
        return fixations
    fixations = fixations.copy()
    fixations["word_id"] = pd.to_numeric(fixations["word_id"], errors="coerce") - offset
    _LOGGER.warning(
        "BUG-8: the fixation report's word ids are numbered from 1 while the word "
        "boxes are numbered from 0, so every fixation pointed at the next word. "
        "Shifted the fixation word ids down by %d to line the two tables up.",
        offset,
    )
    return fixations


def harmonize_frames(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Cross-frame fixups applied right after normalization.

    Broadcast stimulus-level words across participants, reconcile a
    participant-less fixations table with participant-bearing words, correct a
    1-based fixation ``word_id`` (BUG-8), then fill missing fixation coordinates
    from word-box centers. Call whenever both frames are available (the API and
    the app both route through this)."""
    from .preprocessing import add_text_direction

    words = add_text_direction(broadcast_stimulus_words(words, fixations))
    words = _reconcile_participant_asymmetry(words, fixations)
    fixations = correct_word_id_offset(words, fixations)
    fixations = fill_fixation_xy_from_words(fixations, words)
    return words, fixations


def _disambiguate_repeated_readings(
    df: pd.DataFrame,
    source: pd.DataFrame,
    trial_col: str,
) -> pd.DataFrame:
    """Suffix `trial_id` with `_r2`, `_r3` … when a participant read the same
    paragraph more than once.

    OneStop L2's per-pid parquet shards don't carry a `unique_trial_id` column,
    so the schema-inference fallback uses `unique_paragraph_id` — but that's
    the same string for both readings of a repeated-reading trial. Without
    this fix, the two readings' fixations collapse into one scanpath (and into
    one row of the trial picker), which is what the cached PNG thumbnails
    (which filter on TRIAL_INDEX) correctly avoid. We rank by TRIAL_INDEX so
    the chronologically-first reading keeps its original id; later readings
    get `_r2`, `_r3`, … appended.

    Groups on the already-computed ``df["participant_id"]`` (1:1 with ``source``),
    so a composite participant id is handled without recomputing the join.
    """
    if "unique_trial_id" in source.columns:
        return df
    idx_col = next(
        (c for c in ("TRIAL_INDEX", "trial_index") if c in source.columns), None
    )
    if idx_col is None:
        return df
    grouper = pd.DataFrame(
        {
            "_pk": df["participant_id"].to_numpy(),
            "_tc": source[trial_col].astype(str).to_numpy(),
            "_idx": source[idx_col].to_numpy(),
        }
    )
    rank = (
        grouper.groupby(["_pk", "_tc"])["_idx"]
        .rank(method="dense")
        .astype(int)
        .to_numpy()
    )
    df["trial_id"] = [
        tid if r == 1 else f"{tid}_r{r}"
        for tid, r in zip(df["trial_id"].to_numpy(), rank)
    ]
    return df


def has_explicit_trial_index(frame: pd.DataFrame) -> bool:
    """True when the data already carries a per-trial index column."""
    return any(c in frame.columns for c in ("trial_index", "TRIAL_INDEX"))


def derive_trial_index(frame: pd.DataFrame) -> pd.Series:
    """Per-participant 1-based trial order, aligned to ``frame``'s rows.

    Prefers an existing ``trial_index`` / ``TRIAL_INDEX`` column (the order the
    data already records). Otherwise it ranks each participant's trials by their
    earliest ``timestamp_ms`` (falling back to first-appearance order when no
    timestamps) and numbers them 1, 2, 3, …. Used by the Corpus Analysis tab to
    plot a metric as a function of where the trial fell in the session. Returns a
    float Series (NaN where the index can't be determined)."""
    if frame.empty or not {"participant_id", "trial_id"} <= set(frame.columns):
        return pd.Series([np.nan] * len(frame), index=frame.index, dtype="float64")
    for col in ("trial_index", "TRIAL_INDEX"):
        if col in frame.columns:
            return pd.to_numeric(frame[col], errors="coerce")
    if "timestamp_ms" in frame.columns:
        order_key = frame.groupby(["participant_id", "trial_id"])[
            "timestamp_ms"
        ].transform("min")
    else:
        # First-appearance order: row position of each trial's first row.
        order_key = pd.Series(range(len(frame)), index=frame.index)
        order_key = (
            frame.assign(_k=order_key)
            .groupby(["participant_id", "trial_id"])["_k"]
            .transform("min")
        )
    per_trial = (
        frame[["participant_id", "trial_id"]]
        .assign(_k=pd.to_numeric(order_key, errors="coerce"))
        .drop_duplicates(["participant_id", "trial_id"])
        .sort_values(["participant_id", "_k"])
    )
    per_trial["_idx"] = per_trial.groupby("participant_id").cumcount() + 1
    merged = frame[["participant_id", "trial_id"]].merge(
        per_trial[["participant_id", "trial_id", "_idx"]],
        on=["participant_id", "trial_id"],
        how="left",
    )
    return pd.Series(
        pd.to_numeric(merged["_idx"], errors="coerce").to_numpy(),
        index=frame.index,
        dtype="float64",
    )


# ---------------------------------------------------------------------------
# Optional-field registry. Drives (a) which known optional source columns are
# carried into the normalized frame and (b) the setup wizard's opt-out checklist.
# Each entry: (source, dest, kind, category) where `kind` ∈
# {numeric, string, boolean, passthrough} and `category` ∈
# {measure, linguistic, meta} groups the fields in the UI. Matched by exact
# source name (same as the legacy keep-lists this replaced).
# ---------------------------------------------------------------------------
WORD_OPTIONAL_FIELDS = [
    ("IA_FIRST_FIXATION_DURATION", "first_fixation_ms", "numeric", "measure"),
    ("IA_DWELL_TIME", "total_fixation_duration_ms", "numeric", "measure"),
    ("IA_FIRST_RUN_DWELL_TIME", "first_pass_gaze_duration_ms", "numeric", "measure"),
    (
        "IA_SECOND_RUN_DWELL_TIME",
        "second_pass_duration_ms",
        "numeric",
        "measure",
    ),
    # Compatibility aliases retained for existing datasets/API consumers; the
    # PRE-4 canonical field above is the one measure computation consults.
    (
        "IA_SECOND_RUN_DWELL_TIME",
        "higher_pass_fixation_duration_ms",
        "numeric",
        "measure",
    ),
    ("IA_LAST_RUN_DWELL_TIME", "last_run_dwell_time_ms", "numeric", "measure"),
    ("IA_FIXATION_COUNT", "n_fixations", "numeric", "measure"),
    ("IA_SKIP", "skip_flag", "boolean", "measure"),
    (
        "IA_REGRESSION_IN_COUNT",
        "number_of_regressions_in",
        "numeric",
        "measure",
    ),
    ("IA_REGRESSION_IN_COUNT", "regression_in_count", "numeric", "measure"),
    ("IA_REGRESSION_OUT_COUNT", "regression_out_count", "numeric", "measure"),
    ("IA_REGRESSION_IN", "regression_in_flag", "boolean", "measure"),
    ("IA_REGRESSION_OUT", "regression_out_flag", "boolean", "measure"),
    (
        "IA_REGRESSION_PATH_DURATION",
        "regression_path_duration_ms",
        "numeric",
        "measure",
    ),
    ("TRIAL_DWELL_TIME", "trial_dwell_time_ms", "numeric", "measure"),
    ("TRIAL_FIXATION_COUNT", "trial_fixation_count", "numeric", "measure"),
    ("TRIAL_IA_COUNT", "trial_ia_count", "numeric", "measure"),
    ("word_length", "word_length", "numeric", "measure"),
    ("word_length_no_punctuation", "word_length_no_punctuation", "numeric", "measure"),
    ("gpt2_surprisal", "gpt2_surprisal", "numeric", "linguistic"),
    ("wordfreq_frequency", "wordfreq_frequency", "numeric", "linguistic"),
    ("subtlex_frequency", "subtlex_frequency", "numeric", "linguistic"),
    ("universal_pos", "universal_pos", "string", "linguistic"),
    ("ptb_pos", "ptb_pos", "string", "linguistic"),
    ("Reduced_POS", "reduced_pos", "string", "linguistic"),
    ("dependency_relation", "dependency_relation", "string", "linguistic"),
    ("morphological_features", "morphological_features", "string", "linguistic"),
    ("entity_type", "entity_type", "string", "linguistic"),
    ("head_word_index", "head_word_index", "numeric", "linguistic"),
    ("distance_to_head", "distance_to_head", "numeric", "linguistic"),
    ("left_dependents_count", "left_dependents_count", "numeric", "linguistic"),
    ("right_dependents_count", "right_dependents_count", "numeric", "linguistic"),
    ("sentence_id", "sentence_id", "passthrough", "linguistic"),
    ("SENTENCE_ID", "sentence_id", "passthrough", "linguistic"),
    ("right_to_left", "right_to_left", "boolean", "meta"),
    ("RIGHT_TO_LEFT", "right_to_left", "boolean", "meta"),
    (SOURCE_FILE_COLUMN, SOURCE_FILE_COLUMN, "passthrough", "meta"),
    ("TRIAL_INDEX", "TRIAL_INDEX", "passthrough", "meta"),
    ("trial_index", "trial_index", "passthrough", "meta"),
    ("article_batch", "article_batch", "passthrough", "meta"),
    ("article_id", "article_id", "passthrough", "meta"),
    ("difficulty_level", "difficulty_level", "passthrough", "meta"),
    ("article_title", "article_title", "passthrough", "meta"),
    ("question", "question", "passthrough", "meta"),
    ("question_preview", "question_preview", "boolean", "meta"),
    ("selected_answer", "selected_answer", "passthrough", "meta"),
    ("is_correct", "is_correct", "passthrough", "meta"),
    ("repeated_reading_trial", "repeated_reading_trial", "boolean", "meta"),
    ("critical_span_indices", "critical_span_indices", "passthrough", "meta"),
    ("distractor_span_indices", "distractor_span_indices", "passthrough", "meta"),
    ("aspan_ind_start", "aspan_ind_start", "passthrough", "meta"),
    ("aspan_ind_end", "aspan_ind_end", "passthrough", "meta"),
    ("dspan_ind_start", "dspan_ind_start", "passthrough", "meta"),
    ("dspan_ind_end", "dspan_ind_end", "passthrough", "meta"),
    ("is_in_aspan", "is_in_aspan", "boolean", "meta"),
    ("is_in_dspan", "is_in_dspan", "boolean", "meta"),
    # MultiplEYE side-data (also see FIX_OPTIONAL_FIELDS): the comprehension
    # questions JSON + the per-trial stimulus-image path + the genre facet, kept
    # so the panels / image layer can read them off the word frame too.
    ("comprehension_questions", "comprehension_questions", "passthrough", "meta"),
    ("image_path", "image_path", "passthrough", "meta"),
    ("image_x", "image_x", "numeric", "meta"),
    ("image_y", "image_y", "numeric", "meta"),
    # Stimulus typeface (size in monitor px + CSS family) the images were rendered
    # with — the app snaps its font controls to these so the reading text matches.
    ("stimulus_font_px", "stimulus_font_px", "numeric", "meta"),
    ("stimulus_font_family", "stimulus_font_family", "passthrough", "meta"),
    ("genre", "genre", "string", "meta"),
]

FIX_OPTIONAL_FIELDS = [
    (SOURCE_FILE_COLUMN, SOURCE_FILE_COLUMN, "passthrough", "meta"),
    ("TRIAL_INDEX", "TRIAL_INDEX", "passthrough", "meta"),
    ("trial_index", "trial_index", "passthrough", "meta"),
    ("article_batch", "article_batch", "passthrough", "meta"),
    ("article_id", "article_id", "passthrough", "meta"),
    ("difficulty_level", "difficulty_level", "passthrough", "meta"),
    ("article_title", "article_title", "passthrough", "meta"),
    ("question", "question", "passthrough", "meta"),
    ("selected_answer", "selected_answer", "passthrough", "meta"),
    ("is_correct", "is_correct", "passthrough", "meta"),
    ("repeated_reading_trial", "repeated_reading_trial", "boolean", "meta"),
    ("question_preview", "question_preview", "boolean", "meta"),
    # Per-fixation extras — auto-detected + kept (renamed to canonical so the
    # colour-by / per-fixation filters still find them), but not schema mapping
    # fields. saccade_amplitude is also recomputed from X/Y by measures when
    # absent, so it's never lost.
    ("pass_index", "pass_index", "numeric", "fixation"),
    ("reread", "pass_index", "numeric", "fixation"),
    ("saccade_type", "saccade_type", "string", "fixation"),
    ("NEXT_SAC_DIRECTION", "saccade_type", "string", "fixation"),
    ("saccade_amplitude", "saccade_amplitude", "numeric", "fixation"),
    ("NEXT_SAC_AMPLITUDE", "saccade_amplitude", "numeric", "fixation"),
    ("PREVIOUS_SAC_AMPLITUDE", "saccade_amplitude", "numeric", "fixation"),
    ("eye", "eye", "string", "fixation"),
    ("EYE_USED", "eye", "string", "fixation"),
    ("EYE_TRACKED", "eye", "string", "fixation"),
    ("is_blink", "is_blink", "boolean", "fixation"),
    ("blink", "is_blink", "boolean", "fixation"),
    ("blink_flag", "is_blink", "boolean", "fixation"),
    ("BLINK", "is_blink", "boolean", "fixation"),
    # MultiplEYE trial-level facets + side-data → Trial Info chips / filter
    # facets / the comprehension panel / the stimulus-image layer. All are
    # MultiplEYE-specific source names (carried only when the loader emits them),
    # so they're inert for other corpora.
    ("genre", "genre", "string", "meta"),
    ("session", "session", "string", "meta"),
    ("participant", "participant", "string", "meta"),
    ("is_practice", "is_practice", "boolean", "meta"),
    ("trial_num", "trial_num", "numeric", "meta"),
    ("comprehension_questions", "comprehension_questions", "passthrough", "meta"),
    ("image_path", "image_path", "passthrough", "meta"),
    ("image_x", "image_x", "numeric", "meta"),
    ("image_y", "image_y", "numeric", "meta"),
    ("stimulus_font_px", "stimulus_font_px", "numeric", "meta"),
    ("stimulus_font_family", "stimulus_font_family", "passthrough", "meta"),
    # Reader metadata merged from participant_data.csv (namespaced pp_*).
    ("pp_age", "pp_age", "numeric", "meta"),
    ("pp_gender", "pp_gender", "string", "meta"),
    ("pp_native_language", "pp_native_language", "string", "meta"),
    ("pp_years_education", "pp_years_education", "numeric", "meta"),
    ("pp_education_level", "pp_education_level", "string", "meta"),
]


def _schema_source_columns(schema: Dict) -> set:
    """Set of raw source column names a normalization schema references."""
    cols: set = set()
    for value in schema.values():
        if not value:
            continue
        if isinstance(value, list):
            cols.update(value)
        else:
            cols.add(value)
    return cols


def dropped_columns(
    raw: pd.DataFrame,
    *,
    keep: Optional[set] = None,
    schema: Optional[Dict] = None,
) -> list:
    """Original source columns discarded during normalization (sorted).

    Pass ``keep`` (the set handed to ``normalize_words``/``normalize_fixations``,
    i.e. a ``compute_keep_columns`` result) for the union-keep tables, or
    ``schema`` for raw gaze (``normalize_raw_gaze`` keeps the schema-referenced
    columns plus any ``unique_trial_id`` it consults directly). With neither,
    returns ``[]``."""
    if keep is None and schema is not None:
        keep = _schema_source_columns(schema) | {"unique_trial_id"}
    if keep is None:
        return []
    return sorted(c for c in raw.columns if c not in keep)


# EyeLink writes a missing value as the string ``'.'`` and booleans as ``'0'`` /
# ``'1'``, so a whole flag column arrives as *strings* (BUG-7). A plain
# ``astype(bool)`` then reads every non-empty string as True — including ``'0'``
# and ``'.'`` — and `regression_in_flag` came out True for every row in the
# bundled demo. Anything a reader would write for "false" or "missing" has to be
# recognised before the cast.
_FALSEY_FLAG_STRINGS = {"", ".", "0", "0.0", "false", "f", "no", "n", "na", "nan", "-"}


def coerce_flag(col: pd.Series) -> pd.Series:
    """Coerce a flag-like column to real booleans (BUG-7).

    Numbers go by ``!= 0``; strings are matched against the sentinels above
    (case-insensitively) rather than by truthiness. NaN / missing is ``False``,
    which is what every downstream flag consumer already assumed.
    """
    if pd.api.types.is_bool_dtype(col):
        return col.fillna(False).astype(bool)
    numeric = pd.to_numeric(col, errors="coerce")
    if numeric.notna().any():
        # A numeric-looking column ('0'/'1', 0/1, 0.0/1.0): non-zero is True.
        # Values that didn't parse fall through to the string test below, so a
        # mixed '0'/'1'/'.' column doesn't lose its '.' rows to True.
        parsed = numeric.notna()
        # Build the boolean array positionally: assigning a bool ndarray into a
        # bool Series by mask is deprecated in pandas as a dtype-incompatible set.
        values = (numeric.to_numpy() != 0) & parsed.to_numpy()
        unparsed = (~parsed & col.notna()).to_numpy()
        if unparsed.any():
            values[unparsed] = ~(
                col[unparsed]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(_FALSEY_FLAG_STRINGS)
            ).to_numpy()
        result = pd.Series(values, index=col.index, dtype=bool)
        return result
    return (
        ~col.fillna("").astype(str).str.strip().str.lower().isin(_FALSEY_FLAG_STRINGS)
    ).astype(bool)


def _apply_optional_fields(
    df: pd.DataFrame, source: pd.DataFrame, registry: list, keep: Optional[set]
) -> set:
    """Carry registry-listed optional source columns into ``df`` (renamed +
    dtype-coerced). ``keep`` is ``None`` (carry every detected field — the
    backward-compatible default) or a set of *source* column names to limit to.
    Returns the set of source columns actually emitted."""
    emitted: set = set()
    for src, dest, kind, _category in registry:
        if src not in source.columns:
            continue
        if keep is not None and src not in keep:
            continue
        emitted.add(src)
        col = source[src]
        if kind == "numeric":
            df[dest] = pd.to_numeric(col, errors="coerce")
        elif kind == "string":
            df[dest] = col.astype(str)
        elif kind == "boolean":
            df[dest] = coerce_flag(col)
        else:
            df[dest] = col
    return emitted


def _carry_extra_columns(
    df: pd.DataFrame, source: pd.DataFrame, keep: Optional[set], skip: set
) -> None:
    """Carry user-chosen extra ``keep`` source columns through verbatim, skipping
    those already emitted (canonical / registry) or in ``skip``."""
    if not keep:
        return
    for col in keep:
        if col in source.columns and col not in skip and col not in df.columns:
            df[col] = source[col].to_numpy()


def categorize_columns(raw: pd.DataFrame, schema: Dict, registry: list) -> Dict:
    """Split a raw frame's columns into {mapped, detected_optional, unclaimed}.

    ``mapped`` = source columns the schema references; ``detected_optional`` =
    registry entries present in the frame (each ``{source, dest, category}``);
    ``unclaimed`` = everything else (offered as filter fields / extra keeps)."""
    mapped = {c for c in _schema_source_columns(schema) if c in raw.columns}
    detected = [
        {"source": src, "dest": dest, "category": category}
        for src, dest, _kind, category in registry
        if src in raw.columns
    ]
    detected_sources = {d["source"] for d in detected}
    unclaimed = [
        c for c in raw.columns if c not in mapped and c not in detected_sources
    ]
    return {"mapped": mapped, "detected_optional": detected, "unclaimed": unclaimed}


def compute_keep_columns(
    schema: Dict,
    *,
    optional_sources: Optional[Iterable[str]] = None,
    filter_fields: Optional[Iterable[str]] = None,
    keep_columns: Optional[Iterable[str]] = None,
) -> set:
    """Source columns to retain before normalization (everything else is dropped
    for speed). Union of: schema-mapped sources, always-kept structural columns,
    chosen optional fields, chosen filter fields, and extra keep columns."""
    keep = set(_schema_source_columns(schema))
    # Structural columns consulted directly by normalize_* (not via schema).
    for col in (
        SOURCE_FILE_COLUMN,
        "unique_trial_id",
        "unique_paragraph_id",
        "TRIAL_INDEX",
        "trial_index",
    ):
        keep.add(col)
    for group in (optional_sources, filter_fields, keep_columns):
        if group:
            keep.update(group)
    return keep


def normalize_words(
    words: pd.DataFrame, schema: Dict[str, str], *, keep_columns: Optional[set] = None
) -> pd.DataFrame:
    # The explicit index makes scalar assignments (e.g. the stimulus-level
    # participant placeholder) fill every row even when assigned first.
    df = pd.DataFrame(index=words.index)
    if schema.get("participant"):
        # str or list (a composite participant id, joined like the trial id).
        df["participant_id"] = trial_id_series(words, schema["participant"])
    else:
        # Stimulus-level word/AoI table (one row per word per text, shared by
        # all participants) — broadcast_stimulus_words() expands it across the
        # participants found in the fixations.
        df["participant_id"] = STIMULUS_PARTICIPANT
        df[STIMULUS_WORDS_FLAG] = True
    trial_cols = trial_mapping_columns(schema["trial"])
    if len(trial_cols) > 1:
        # User-composed unique trial ID: authoritative, so it wins over a raw
        # `unique_trial_id` column and needs no repeated-reading suffixing.
        df["trial_id"] = trial_id_series(words, trial_cols)
        df["unique_trial_id"] = df["trial_id"]
    else:
        trial_col = (
            "unique_trial_id" if "unique_trial_id" in words.columns else trial_cols[0]
        )
        df["trial_id"] = words[trial_col].astype(str)
        if schema.get("participant"):
            df = _disambiguate_repeated_readings(df, words, trial_col)
        if "unique_trial_id" in words.columns:
            df["unique_trial_id"] = words["unique_trial_id"].astype(str)
    if "unique_paragraph_id" in words.columns:
        df["unique_text_id"] = words["unique_paragraph_id"].astype(str)
        df["text_id"] = df["unique_text_id"]
    elif schema.get("text_id"):
        # str or list (a composite text id, joined like the trial id).
        df["text_id"] = trial_id_series(words, schema["text_id"])
    else:
        df["text_id"] = df["trial_id"]
    df["word_id"] = pd.to_numeric(words[schema["word_id"]], errors="coerce")
    if schema.get("text"):
        df["text"] = words[schema["text"]].astype(str)
    else:
        df["text"] = df["word_id"].apply(lambda v: f"w{int(v)}" if pd.notna(v) else "")
    df["text"] = df["text"].str.replace(r"\s+", " ", regex=True).str.strip()
    if schema.get("line"):
        df["line_idx"] = pd.to_numeric(words[schema["line"]], errors="coerce")
    else:
        df["line_idx"] = 1

    if all(schema.get(k) for k in ["x", "y", "width", "height"]):
        df["x"] = pd.to_numeric(words[schema["x"]], errors="coerce")
        df["y"] = pd.to_numeric(words[schema["y"]], errors="coerce")
        df["width"] = pd.to_numeric(words[schema["width"]], errors="coerce")
        df["height"] = pd.to_numeric(words[schema["height"]], errors="coerce")
    else:
        left = pd.to_numeric(words[schema["left"]], errors="coerce")
        right = pd.to_numeric(words[schema["right"]], errors="coerce")
        top = pd.to_numeric(words[schema["top"]], errors="coerce")
        bottom = pd.to_numeric(words[schema["bottom"]], errors="coerce")
        df["x"] = left
        df["y"] = top
        df["width"] = right - left
        df["height"] = bottom - top

    emitted = _apply_optional_fields(df, words, WORD_OPTIONAL_FIELDS, keep_columns)
    if keep_columns is not None:
        _carry_extra_columns(
            df, words, keep_columns, _schema_source_columns(schema) | emitted
        )

    df = _preserve_composite_columns(df, words, schema["trial"])
    return df


def normalize_fixations(
    fixations: pd.DataFrame,
    schema: Dict[str, str],
    *,
    keep_columns: Optional[set] = None,
) -> pd.DataFrame:
    # Explicit index so a constant participant placeholder fills every row.
    df = pd.DataFrame(index=fixations.index)
    if schema.get("participant"):
        # str or list (a composite participant id, joined like the trial id).
        df["participant_id"] = trial_id_series(fixations, schema["participant"])
    else:
        # No participant column → a single anonymous reader.
        df["participant_id"] = SYNTHETIC_PARTICIPANT
    trial_cols = trial_mapping_columns(schema["trial"])
    if len(trial_cols) > 1:
        # User-composed unique trial ID — see normalize_words.
        df["trial_id"] = trial_id_series(fixations, trial_cols)
        df["unique_trial_id"] = df["trial_id"]
    else:
        trial_col = (
            "unique_trial_id"
            if "unique_trial_id" in fixations.columns
            else trial_cols[0]
        )
        df["trial_id"] = fixations[trial_col].astype(str)
        if schema.get("participant"):
            df = _disambiguate_repeated_readings(df, fixations, trial_col)
        if "unique_trial_id" in fixations.columns:
            df["unique_trial_id"] = fixations["unique_trial_id"].astype(str)
    if "unique_paragraph_id" in fixations.columns:
        df["text_id"] = fixations["unique_paragraph_id"].astype(str)
    elif schema.get("text_id"):
        # str or list (a composite text id, joined like the trial id).
        df["text_id"] = trial_id_series(fixations, schema["text_id"])
    else:
        df["text_id"] = df["trial_id"]
    if "unique_paragraph_id" in fixations.columns:
        df["unique_text_id"] = fixations["unique_paragraph_id"].astype(str)
    # X/Y may be unmapped for AOI-sequence datasets (no pixel coordinates) —
    # left NaN here and filled from word-box centers by harmonize_frames().
    for coord in ("x", "y"):
        if schema.get(coord):
            df[coord] = pd.to_numeric(fixations[schema[coord]], errors="coerce")
        else:
            df[coord] = np.nan
    df["duration_ms"] = pd.to_numeric(
        fixations[schema["duration"]], errors="coerce"
    ).fillna(0)

    if schema.get("timestamp"):
        df["timestamp_ms"] = pd.to_numeric(
            fixations[schema["timestamp"]], errors="coerce"
        ).fillna(0)
    else:
        df["timestamp_ms"] = df.groupby(["participant_id", "trial_id"]).cumcount()

    if schema.get("fixation_id"):
        df["fixation_id"] = fixations[schema["fixation_id"]]
    else:
        df["fixation_id"] = df.groupby(["participant_id", "trial_id"]).cumcount().add(1)

    if schema.get("word_id"):
        df["word_id"] = pd.to_numeric(fixations[schema["word_id"]], errors="coerce")
    else:
        df["word_id"] = np.nan

    # pass_index / saccade_type / saccade_amplitude / eye are no longer schema
    # fields — they ride through _apply_optional_fields (FIX_OPTIONAL_FIELDS) when
    # the data carries them. saccade_amplitude is also recomputed from X/Y by
    # measures.enrich_fixations when absent.
    emitted = _apply_optional_fields(df, fixations, FIX_OPTIONAL_FIELDS, keep_columns)
    if keep_columns is not None:
        _carry_extra_columns(
            df, fixations, keep_columns, _schema_source_columns(schema) | emitted
        )

    df = _preserve_composite_columns(df, fixations, schema["trial"])

    df["order_in_trial"] = (
        df.sort_values(["timestamp_ms", "duration_ms"])
        .groupby(["participant_id", "trial_id"])
        .cumcount()
        + 1
    )
    return df


# Canonical columns produced by normalize_words / normalize_fixations. Used to
# build typed empty frames when a dataset ships only one of the two reports,
# so every downstream consumer can keep selecting columns unconditionally.
WORDS_CANONICAL_COLUMNS: Dict[str, str] = {
    "participant_id": "object",
    "trial_id": "object",
    "text_id": "object",
    "word_id": "float64",
    "text": "object",
    "line_idx": "float64",
    "x": "float64",
    "y": "float64",
    "width": "float64",
    "height": "float64",
}
FIX_CANONICAL_COLUMNS: Dict[str, str] = {
    "participant_id": "object",
    "trial_id": "object",
    "text_id": "object",
    "x": "float64",
    "y": "float64",
    "duration_ms": "float64",
    "timestamp_ms": "float64",
    "fixation_id": "float64",
    "word_id": "float64",
    "order_in_trial": "int64",
}


def empty_words_frame() -> pd.DataFrame:
    """An empty words frame with the canonical post-normalization columns."""
    return pd.DataFrame(
        {col: pd.Series(dtype=dt) for col, dt in WORDS_CANONICAL_COLUMNS.items()}
    )


def empty_fixations_frame() -> pd.DataFrame:
    """An empty fixations frame with the canonical post-normalization columns."""
    return pd.DataFrame(
        {col: pd.Series(dtype=dt) for col, dt in FIX_CANONICAL_COLUMNS.items()}
    )


# Identity columns recomputed (not carried) by a remap — see remap_normalized_frame.
_REMAP_DERIVED_IDS = ("unique_trial_id", "unique_text_id", "unique_paragraph_id")


def remap_normalized_frame(
    frame: pd.DataFrame, schema: Dict[str, Optional[str]], *, kind: str
) -> pd.DataFrame:
    """Re-derive an already-normalized frame under a new column mapping.

    Stored datasets keep only their post-normalization frames — canonical column
    names (``duration_ms``, ``x``, ``word_id``, …) plus any kept extras; the
    original upload columns are gone. To change the mapping without re-uploading,
    re-run the matching ``normalize_*`` over the *normalized* frame, treating its
    current columns as the source universe. ``schema`` therefore references
    canonical/extra column names (e.g. ``{"duration": "duration_ms",
    "trial": "trial_id", ...}``).

    The precomputed identity columns (``unique_trial_id`` etc.) are dropped first
    so the new Trial/Text mapping is authoritative: otherwise ``normalize_*``
    would keep deriving ``trial_id`` from the existing ``unique_trial_id`` and
    silently ignore a changed Trial ID pick. A derived-id column the new schema
    *references* is NOT dropped, though — a composite trial id can be built from
    ``unique_paragraph_id``, and dropping a chosen component would make
    ``trial_id_series`` raise ``KeyError``. Every surviving column is kept
    (``keep_columns`` = all current columns) so the remap only reassigns roles
    and never drops data that already survived the first normalization. After
    normalization ``unique_trial_id`` / ``unique_text_id`` are restored
    (= ``trial_id`` / ``text_id``) when the single-column path didn't set them,
    so the frame's identity columns stay consistent with the composite path and
    downstream readers of ``unique_text_id`` keep working."""
    referenced = _schema_source_columns(schema)
    working = frame.drop(
        columns=[
            c for c in _REMAP_DERIVED_IDS if c in frame.columns and c not in referenced
        ]
    )
    keep = set(working.columns)
    if kind == "words":
        result = normalize_words(working, schema, keep_columns=keep)
    elif kind == "fixations":
        result = normalize_fixations(working, schema, keep_columns=keep)
    elif kind == "raw_gaze":
        result = normalize_raw_gaze(working, schema)
    else:
        raise ValueError(f"unknown frame kind: {kind!r}")
    if "unique_trial_id" not in result.columns and "trial_id" in result.columns:
        result["unique_trial_id"] = result["trial_id"]
    if "unique_text_id" not in result.columns and "text_id" in result.columns:
        result["unique_text_id"] = result["text_id"]
    return result


def _union_column_values(
    words: pd.DataFrame, fixations: pd.DataFrame, column: str
) -> list:
    """Sorted union of a column's values across both frames (either may be
    empty — single-report datasets have words or fixations, not both)."""
    values: set = set()
    for df in (words, fixations):
        if df is not None and not df.empty and column in df.columns:
            values.update(df[column].unique())
    return sorted(values)


def filter_data(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    filters: Dict,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # When the participant/trial selection covers the whole frame (the default —
    # any narrowing already happened upstream in filter_trials), skip the two
    # O(n) membership masks entirely; only the optional fixation-level filters
    # below apply. ``default_filters`` sets the cover-all flags.
    cover_all = bool(
        filters.get("_participants_cover_all") and filters.get("_trials_cover_all")
    )
    if cover_all:
        # participant/trial cover the whole frame and default_filters set the
        # pass/saccade/eye filters to their full value sets (no-ops), so nothing
        # can narrow the fixations — return the frames untouched (no full-frame
        # mask, no copy), the common large-upload case.
        return words, fixations

    participants = filters.get("participants") or _union_column_values(
        words, fixations, "participant_id"
    )
    trials = filters.get("trials") or _union_column_values(words, fixations, "trial_id")
    word_mask = words["participant_id"].isin(participants) & words["trial_id"].isin(
        trials
    )
    words_filtered = words[word_mask]
    fix_mask = fixations["participant_id"].isin(participants) & fixations[
        "trial_id"
    ].isin(trials)
    if "pass_index" in fixations.columns:
        pass_indices = filters.get("pass_indices")
        if pass_indices:
            fix_mask &= fixations["pass_index"].isin(pass_indices)
    if "saccade_type" in fixations.columns:
        saccade_types = filters.get("saccade_types")
        if saccade_types:
            fix_mask &= fixations["saccade_type"].isin(saccade_types)
    if "eye" in fixations.columns:
        eyes = filters.get("eyes")
        if eyes:
            fix_mask &= fixations["eye"].isin(eyes)
    fixations_filtered = fixations[fix_mask]
    return words_filtered, fixations_filtered


def filter_trials(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participants: Optional[list] = None,
    metadata: Optional[Dict[str, set]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Narrow words + fixations by participant and categorical trial metadata.

    ``metadata`` maps a column name to the set of allowed values. Only columns
    present on a frame are applied, so a condition like ``question_preview``
    (Hunting/Gathering) narrows both words and fixations — the column is copied
    onto both during normalization. A falsy selection means "no constraint".
    """
    w, f = words, fixations
    if participants:
        # participant_id is already string after normalization (as the metadata
        # filters below also assume), so skip a full-column .astype(str) recast.
        keep = set(map(str, participants))
        w = w[w["participant_id"].isin(keep)]
        f = f[f["participant_id"].isin(keep)]
    for col, allowed in (metadata or {}).items():
        if not allowed:
            continue
        allowed = set(allowed)
        if col in w.columns:
            w = w[w[col].isin(allowed)]
        if col in f.columns:
            f = f[f[col].isin(allowed)]
    return w, f


def trial_keys(frame: pd.DataFrame) -> set:
    """The distinct ``(participant_id, trial_id)`` string keys a frame carries.

    Deduplicates before materializing the tuples, so it stays cheap on a
    sample-level table (raw gaze) where every trial spans thousands of rows.
    A missing/empty frame, or one without both id columns, yields an empty set.
    """
    if frame is None or frame.empty:
        return set()
    if "participant_id" not in frame.columns or "trial_id" not in frame.columns:
        return set()
    pairs = frame[["participant_id", "trial_id"]].drop_duplicates()
    return {
        (str(p), str(t)) for p, t in zip(pairs["participant_id"], pairs["trial_id"])
    }


def filter_frame_to_keys(frame: pd.DataFrame, keys: set) -> pd.DataFrame:
    """Keep only rows whose ``(participant_id, trial_id)`` is in ``keys``.

    Single-frame counterpart of :func:`filter_to_keys`. BUG-12: the raw-gaze
    samples table has to be narrowed by the annotation filters (favorites /
    tags) exactly like the words and fixations frames, or a sample row for an
    unstarred trial survives "⭐ Favorites only". Vectorized via a MultiIndex
    membership test so it stays fast on large tables.
    """
    if frame is None or frame.empty:
        return frame
    if "participant_id" not in frame.columns or "trial_id" not in frame.columns:
        return frame
    idx = pd.MultiIndex.from_arrays(
        [frame["participant_id"].astype(str), frame["trial_id"].astype(str)]
    )
    return frame[idx.isin(keys)]


def filter_to_keys(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    keys: set,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only rows whose (participant_id, trial_id) is in ``keys``.

    ``keys`` is a set of ``(str, str)`` tuples. Used to apply annotation-based
    filtering (favorites / tags). Vectorized via a MultiIndex membership test so
    it stays fast on large fixation tables."""
    return filter_frame_to_keys(words, keys), filter_frame_to_keys(fixations, keys)


def count_trials(words: pd.DataFrame, fixations: pd.DataFrame) -> int:
    """How many distinct ``(participant_id, trial_id)`` trials the frames hold.

    Counts across both frames, so a words-only or fixations-only dataset is
    measured just as well as a paired one.
    """
    keys: set = set()
    for df in (words, fixations):
        if df is None or df.empty:
            continue
        if "participant_id" not in df.columns or "trial_id" not in df.columns:
            continue
        keys.update(zip(df["participant_id"].astype(str), df["trial_id"].astype(str)))
    return len(keys)


def diagnose_filters(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    steps: Sequence[Tuple],
) -> List[Dict]:
    """Attribute an empty trial pool to the filter(s) that caused it (UX-7).

    ``steps`` is ``(label, apply)`` or ``(label, apply, keys)``, where
    ``apply(words, fixations)`` returns the frames with *only that one* filter
    applied and ``keys`` is the session-state key(s) that filter is stored under
    (so the caller can offer "clear just this one"). Each step is measured against
    the **unfiltered** frames, so the result says what each filter does on its
    own — which is the question a user staring at an empty plot is asking. A step
    that alone leaves nothing is the culprit; if every step leaves something but
    the combination doesn't, it's their intersection, and the caller can say so.

    Returns one dict per step: ``{"label", "kept", "dropped", "empties", "keys"}``.
    """
    total = count_trials(words, fixations)
    report: List[Dict] = []
    for step in steps:
        label, apply = step[0], step[1]
        keys = tuple(step[2]) if len(step) > 2 else ()
        w, f = apply(words, fixations)
        kept = count_trials(w, f)
        report.append(
            {
                "label": label,
                "kept": kept,
                "dropped": total - kept,
                "empties": total > 0 and kept == 0,
                "keys": keys,
            }
        )
    return report


def filter_raw_gaze(
    raw_gaze: pd.DataFrame,
    participants: list,
    trials: list,
) -> pd.DataFrame:
    """Filter raw gaze data by participants and trials."""
    if raw_gaze.empty:
        return raw_gaze
    mask = raw_gaze["participant_id"].isin(participants) & raw_gaze["trial_id"].isin(
        trials
    )
    return raw_gaze[mask]


def compute_canvas_size(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> Tuple[int, int]:
    """Estimate canvas size from word boxes and fixation extents.

    Returns the smallest power-of-100 dimensions that comfortably enclose the
    rightmost/bottommost data point. Falls back to DEFAULT_FIGURE_SIZE when
    nothing is available.
    """
    default_w, default_h = DEFAULT_FIGURE_SIZE
    x_candidates: list[float] = []
    y_candidates: list[float] = []
    if words is not None and not words.empty and "x" in words.columns:
        x_candidates.append(float((words["x"] + words.get("width", 0)).max()))
        y_candidates.append(float((words["y"] + words.get("height", 0)).max()))
    if fixations is not None and not fixations.empty and "x" in fixations.columns:
        x_candidates.append(float(fixations["x"].max()))
        y_candidates.append(float(fixations["y"].max()))
    # NaN maxima happen when fixations ship without coordinates (AOI-sequence
    # data) and no word boxes were available to fill them in.
    x_candidates = [v for v in x_candidates if np.isfinite(v)]
    y_candidates = [v for v in y_candidates if np.isfinite(v)]
    if not x_candidates or not y_candidates:
        return max(int(default_w), 100), max(int(default_h), 100)
    width = int(np.ceil(max(x_candidates) / 100.0) * 100)
    height = int(np.ceil(max(y_candidates) / 100.0) * 100)
    return max(width, 100), max(height, 100)


# Primary EyeLink IA measures. When a words frame already carries all of these
# (a pre-aggregated export, e.g. OneStop), the fixation-based recompute is a
# fallback whose output is discarded by the "existing values win" merge — so we
# skip it entirely. See compute_per_word_measures for the precedence rule.
_PREAGGREGATED_METRIC_COLUMNS = [
    "first_fixation_ms",
    "first_pass_gaze_duration_ms",
    "total_fixation_duration_ms",
    "n_fixations",
]


def compute_word_metrics(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """Return per-word reading measures.

    If the words table already carries pre-aggregated measures (EyeLink IA
    export), those values are preserved. Anything missing is computed from
    fixations + bounding boxes via `measures.compute_per_word_measures`.

    Cached on a cheap content *fingerprint* of the inputs (see
    ``frame_fingerprint``) rather than a full DataFrame hash, so a rerun that
    doesn't change the data reuses the result without re-hashing millions of
    rows. The frames themselves are passed un-hashed (underscore args).
    """
    return _compute_word_metrics_cached(
        words,
        fixations,
        cache_key=(frame_fingerprint(words), frame_fingerprint(fixations)),
    )


def preprocess_fixation_stage(
    words: pd.DataFrame, fixations: pd.DataFrame, settings: Dict
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached PRE-1 stage; disabled returns the original fixation object."""
    if not settings.get("enabled"):
        return fixations, pd.DataFrame()
    key = (
        frame_fingerprint(words),
        frame_fingerprint(fixations),
        tuple(sorted(settings.items())),
    )
    return _preprocess_fixation_stage_cached(words, fixations, settings, key)


@st.cache_data(show_spinner="Preprocessing fixations…")
def _preprocess_fixation_stage_cached(
    _words: pd.DataFrame, _fixations: pd.DataFrame, settings: Dict, cache_key
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from .measures import assign_fixations_to_words, enrich_fixations
    from .preprocessing import preprocess_fixations

    assigned = enrich_fixations(assign_fixations_to_words(_fixations, _words), _words)
    return preprocess_fixations(assigned, _words, settings=settings)


@st.cache_data(show_spinner="Computing reading measures…")
def _compute_word_metrics_cached(
    _words: pd.DataFrame, _fixations: pd.DataFrame, cache_key
) -> pd.DataFrame:
    from .measures import compute_per_word_measures

    if _words.empty:
        return _words.copy()

    # Existing IA measures still win column-by-column inside the measure
    # function, but PRE-4 adds measures EyeLink exports do not usually carry.
    # Compute whenever fixations exist so those missing fields are not silently
    # absent merely because the four legacy headline columns were pre-aggregated.
    enriched = (
        compute_per_word_measures(_fixations, _words)
        if not _fixations.empty
        else _words
    )

    metric_fields = [
        "first_fixation_ms",
        "first_pass_gaze_duration_ms",
        "regression_path_duration_ms",
        "total_fixation_duration_ms",
        "higher_pass_fixation_duration_ms",
        "last_run_dwell_time_ms",
        "n_fixations",
        "skip_flag",
        "regression_in_count",
        "regression_out_count",
        "regression_in_flag",
        "regression_out_flag",
        "trial_dwell_time_ms",
        "trial_fixation_count",
        "trial_ia_count",
        "word_length",
        "word_length_no_punctuation",
        "gaze_duration_ms",
        "initial_landing_position",
        "initial_landing_distance",
        "number_of_regressions_in",
        "second_pass_duration_ms",
        "single_fixation_duration_ms",
        "first_fix_x",
        "first_fix_y",
        "gpt2_surprisal",
        "wordfreq_frequency",
        "subtlex_frequency",
        "universal_pos",
        "ptb_pos",
        "reduced_pos",
        "dependency_relation",
        "morphological_features",
        "entity_type",
        "head_word_index",
        "distance_to_head",
        "left_dependents_count",
        "right_dependents_count",
    ]
    base_fields = [
        "participant_id",
        "trial_id",
        "text_id",
        "word_id",
        "text",
        "line_idx",
    ]
    present_fields = [
        col for col in base_fields + metric_fields if col in enriched.columns
    ]
    metrics = enriched[present_fields].copy()

    numeric_fields = [
        "first_fixation_ms",
        "first_pass_gaze_duration_ms",
        "regression_path_duration_ms",
        "total_fixation_duration_ms",
        "higher_pass_fixation_duration_ms",
        "last_run_dwell_time_ms",
        "trial_dwell_time_ms",
        "trial_fixation_count",
        "trial_ia_count",
        "regression_in_count",
        "regression_out_count",
        "word_length",
        "word_length_no_punctuation",
        "gaze_duration_ms",
        "first_fix_x",
        "first_fix_y",
        "gpt2_surprisal",
        "wordfreq_frequency",
        "subtlex_frequency",
        "head_word_index",
        "distance_to_head",
        "left_dependents_count",
        "right_dependents_count",
    ]
    for col in numeric_fields:
        if col in metrics.columns:
            metrics[col] = pd.to_numeric(metrics[col], errors="coerce")
    if "n_fixations" in metrics.columns:
        metrics["n_fixations"] = (
            pd.to_numeric(metrics["n_fixations"], errors="coerce")
            .fillna(0)
            .astype("Int64")
        )
    for col in ["skip_flag", "regression_in_flag", "regression_out_flag"]:
        if col in metrics.columns:
            # BUG-7: same sentinel-aware coercion as normalization — a frame can
            # reach here carrying raw `'0'` / `'.'` strings (a pre-computed IA
            # measure joined straight in), and a truthiness cast would flag every
            # row True.
            metrics[col] = coerce_flag(metrics[col])
    return metrics


def default_filters(words: pd.DataFrame, fixations: pd.DataFrame) -> Dict:
    """Default ("everything selected") filter dict for the current frames.

    Cached on a cheap content fingerprint so the full-column ``unique()`` scans
    don't re-run on every rerun when the data hasn't changed.
    """
    return _default_filters_cached(
        words,
        fixations,
        cache_key=(frame_fingerprint(words), frame_fingerprint(fixations)),
    )


@st.cache_data(show_spinner=False)
def _default_filters_cached(
    _words: pd.DataFrame, _fixations: pd.DataFrame, cache_key
) -> Dict:
    filters = dict(
        participants=_union_column_values(_words, _fixations, "participant_id"),
        trials=_union_column_values(_words, _fixations, "trial_id"),
        # The participant/trial lists above are the *full* unique set of the
        # (already trial-filtered) frame, so filter_data's membership masks are
        # no-ops — flag that so it can skip the two O(n) scans.
        _participants_cover_all=True,
        _trials_cover_all=True,
    )
    if "pass_index" in _fixations.columns:
        filters["pass_indices"] = sorted(_fixations["pass_index"].dropna().unique())
    if "saccade_type" in _fixations.columns:
        filters["saccade_types"] = sorted(
            _fixations["saccade_type"].dropna().astype(str).unique()
        )
    if "eye" in _fixations.columns:
        filters["eyes"] = sorted(_fixations["eye"].dropna().astype(str).unique())
    return filters
