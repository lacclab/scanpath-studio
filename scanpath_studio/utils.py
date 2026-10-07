"""Utility functions for trial selection, statistics, and labelling."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

import numpy as np
import pandas as pd
import streamlit as st

from . import progress
from .annotations import current_dataset as annotations_dataset
from .annotations import get_entry, store_for_prefix
from .column_names import COMPUTED_SUFFIX, active_all
from .constants import (
    SELECTOR_ROW_GRID,
    SELECTOR_ROW_TRIO,
    SELECTOR_SCREEN_TRACK,
    spoken,
)
from .data import frame_fingerprint, stable_id
from .fields import labeled
from .styles import widen_menu

# Annotation markers shown beside a trial in the pickers (UX-6). Independent of
# the same-text/same-participant markers (UX-4) and of each other — a trial can
# carry any combination, so they compose. ★ favorite · 🏷️ tagged · 📝 noted.
FAVORITE_MARKER = "★"
TAGGED_MARKER = "🏷️"
NOTE_MARKER = "📝"


def annotation_markers(participant_id, trial_id, *, store=None) -> str:
    """Composable annotation markers (★ favorite · 🏷️ tagged · 📝 noted) for a
    trial, or ``""`` when it carries no annotations. Reads the session store —
    the open dataset's — or ``store``, another dataset's (DATA-48)."""
    if participant_id is None or trial_id is None:
        return ""
    entry = (
        get_entry(str(participant_id), str(trial_id))
        if store is None
        else store.get((str(participant_id), str(trial_id))) or {}
    )
    marks = ""
    if entry.get("star"):
        marks += FAVORITE_MARKER
    if entry.get("tags"):
        marks += TAGGED_MARKER
    if str(entry.get("note") or "").strip():
        marks += NOTE_MARKER
    return marks


# -----------------------------------------------------------------------------
# Trial combo building
# -----------------------------------------------------------------------------

#: The identity columns `build_combo_options` reads off a frame (besides any
#: composite-trial components) — all `combo_source` has to carry.
_COMBO_ID_COLUMNS = (
    "participant_id",
    "trial_id",
    "unique_trial_id",
    "unique_text_id",
    "text_id",
    "unique_paragraph_id",
    "paragraph_id",
    "TRIAL_INDEX",
    "trial_index",
)


def combo_source(
    fixations: pd.DataFrame,
    words: pd.DataFrame,
    raw_gaze: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """The frame the trial picker's combos are built from.

    Fixations when there are any, else words (a words-only dataset), else raw
    gaze (a raw-gaze-only one) — and, since VIZ-45, **plus the trials only the
    raw gaze has**. A trial recorded as samples alone is a trial: in a dataset
    whose fixations cover other trials, or whose words table covers other
    texts, it used to be unpickable because the picker listed the first
    non-empty table and nothing else.

    Returns the chosen frame itself whenever the raw gaze adds no trial (the
    common case, and every dataset without raw gaze), so `build_combo_options`
    keys its cache on the same object as before. Otherwise it returns a small
    frame of identity rows — the chosen frame's, in their order, then the
    raw-gaze-only trials' — which is all `build_combo_options` reads.
    """
    for primary in (fixations, words):
        if primary is not None and not primary.empty:
            break
    else:
        return raw_gaze if raw_gaze is not None else pd.DataFrame()
    if raw_gaze is None or raw_gaze.empty:
        return primary
    composite_cols = tuple(st.session_state.get("_composite_trial_columns") or [])
    combined = _combo_source_with_raw_gaze(
        primary,
        raw_gaze,
        composite_cols,
        cache_key=(frame_fingerprint(primary), frame_fingerprint(raw_gaze)),
    )
    return primary if combined is None else combined


@st.cache_data(show_spinner=False, max_entries=16)
def _combo_source_with_raw_gaze(
    _primary: pd.DataFrame,
    _raw_gaze: pd.DataFrame,
    composite_cols: tuple[str, ...],
    cache_key,
) -> pd.DataFrame | None:
    """`combo_source`'s identity rows, or ``None`` when raw gaze adds no trial."""
    progress.report()
    from .data import trial_keys

    # One deduplication per table, on the identity columns only; every key
    # set below comes off those small frames rather than another pass over
    # every sample (PERF: three full scans at 5M samples was ~0.8 s a miss).
    wanted = [*_COMBO_ID_COLUMNS, *composite_cols]
    primary_cols = [c for c in dict.fromkeys(wanted) if c in _primary.columns]
    rows = _primary[primary_cols].drop_duplicates()
    raw_cols = [c for c in dict.fromkeys(wanted) if c in _raw_gaze.columns]
    raw_rows = _raw_gaze[raw_cols].drop_duplicates()
    extra_keys = trial_keys(raw_rows) - trial_keys(rows)
    if not extra_keys:
        return None
    index = pd.MultiIndex.from_arrays(
        [raw_rows["participant_id"].astype(str), raw_rows["trial_id"].astype(str)]
    )
    raw_rows = raw_rows[index.isin(extra_keys)].copy()
    # The picker keys on the primary frame's trial and text columns; a raw-gaze
    # row that lacks one takes its own trial id / text id, which is what those
    # columns mean for a normalized frame (`data.normalize_raw_gaze`).
    if "unique_trial_id" in rows.columns and "unique_trial_id" not in raw_rows:
        raw_rows["unique_trial_id"] = raw_rows["trial_id"]
    for text_col in ("unique_text_id", "text_id", "unique_paragraph_id"):
        if text_col in rows.columns and text_col not in raw_rows.columns:
            raw_rows[text_col] = raw_rows.get("text_id", raw_rows["trial_id"])
    return pd.concat([rows, raw_rows], ignore_index=True)


def build_combo_options(
    fixations: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[str, str]]]:
    """Build participant/trial/text combinations for selection UI.

    Returns:
        Tuple of (combos DataFrame, label list, label-to-combo mapping).

    Cached on a cheap fingerprint of the frame + the composite-trial columns, so
    the full-frame ``drop_duplicates`` + label build don't re-run on every rerun
    (e.g. selecting a different trial). The session-state read happens here, in
    the un-cached wrapper, and is threaded into the cached core as an argument.
    """
    composite_cols = tuple(st.session_state.get("_composite_trial_columns") or [])
    return build_combo_options_for(fixations, composite_cols)


def build_combo_options_for(
    fixations: pd.DataFrame,
    composite_cols: tuple[str, ...] = (),
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[str, str]]]:
    """`build_combo_options` for a frame that is **not** the active dataset.

    CMP-8 §2: a comparison source has its own composite-trial columns, so the
    session-state read in `build_combo_options` would answer for the wrong
    dataset. Everything else — the cache key, the cached core — is shared.
    """
    composite_cols = tuple(composite_cols or ())
    return _build_combo_options_cached(
        fixations,
        composite_cols,
        cache_key=(frame_fingerprint(fixations), composite_cols),
    )


# UX-166: the dataset card lists this step.
@st.cache_data(show_spinner=False)
def _build_combo_options_cached(
    _fixations: pd.DataFrame,
    composite_cols: tuple[str, ...],
    cache_key,
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[str, str]]]:
    progress.report()  # a miss: real work, so a gated card over it may show
    fixations = _fixations
    trial_col = (
        "unique_trial_id" if "unique_trial_id" in fixations.columns else "trial_id"
    )
    # The text/passage column is optional. Normalized frames carry a text_id (it
    # falls back to trial_id when no text is mapped), but a frame may arrive with
    # only the source name (e.g. unique_paragraph_id — the pre-rename text id, and
    # which can also be a composite-trial component). Detect it via the same
    # priority list normalization uses, and *copy* it to text_id rather than
    # renaming so a shared composite component column survives for the picker.
    text_col = next(
        (
            c
            for c in (
                "unique_text_id",
                "text_id",
                "unique_paragraph_id",
                "paragraph_id",
            )
            if c in fixations.columns
        ),
        None,
    )
    combo_cols = ["participant_id", trial_col]
    if text_col is not None and text_col not in combo_cols:
        combo_cols.append(text_col)
    for col in ["unique_trial_id", "unique_text_id", "TRIAL_INDEX", "trial_index"]:
        if col in fixations.columns and col not in combo_cols:
            combo_cols.append(col)
    # Carry the composite trial id's component columns through, so the trial
    # picker can detect a composite id and cascade on identity (see select_trial).
    for col in composite_cols:
        if col in fixations.columns and col not in combo_cols:
            combo_cols.append(col)

    # UX-24: preserve each trial's first appearance before the historical
    # participant/id sort. The visible pool may still default to Trial ID, but
    # the ⇅ menu can now reconstruct source-file order exactly.
    combos = fixations[combo_cols].drop_duplicates().copy()
    combos["_data_order"] = np.arange(len(combos), dtype=int)
    combos = combos.rename(columns={trial_col: "trial_id"})
    if "text_id" not in combos.columns:
        combos["text_id"] = (
            combos[text_col] if text_col is not None else combos["trial_id"]
        )
    if trial_col == "unique_trial_id" and "unique_trial_id" not in combos.columns:
        combos["unique_trial_id"] = combos["trial_id"]
    if text_col == "unique_text_id" and "unique_text_id" not in combos.columns:
        combos["unique_text_id"] = combos["text_id"]
    sort_cols = ["participant_id"]
    if "TRIAL_INDEX" in combos.columns:
        sort_cols.append("TRIAL_INDEX")
    elif "trial_index" in combos.columns:
        sort_cols.append("trial_index")
    sort_cols.append("trial_id")
    combos = combos.sort_values(sort_cols)

    combo_labels = [
        f"{row.participant_id} / {row.trial_id} · {row.text_id}"
        for row in combos.itertuples()
    ]
    label_to_combo = dict(
        zip(
            combo_labels,
            combos[["participant_id", "trial_id"]].itertuples(index=False, name=None),
        )
    )
    return combos, combo_labels, label_to_combo


@st.cache_data(show_spinner=False)
def _trial_positions(_frame: pd.DataFrame, cache_key) -> dict[tuple[str, str], object]:
    """Map ``(participant_id, trial_id)`` → positional row indices.

    Built once per frame (cached on its fingerprint) so extracting a single
    trial is an O(trial) ``iloc`` rather than an O(corpus) boolean mask on every
    rerun — and shared across the tabs, which all slice the same filtered frames.
    """
    if _frame is None or _frame.empty:
        return {}
    grouped = _frame.groupby(["participant_id", "trial_id"], sort=False).indices
    # Normalise keys to (str, str) so lookups match the picker's string values.
    return {(str(p), str(t)): idx for (p, t), idx in grouped.items()}


def extract_trial(frame: pd.DataFrame, participant_id, trial_id) -> pd.DataFrame:
    """Rows of one (participant, trial), sliced via the cached position index.

    Equivalent to ``frame[(frame.participant_id == p) & (frame.trial_id == t)]``
    but O(trial) instead of O(corpus) once the index is built — the per-rerun win
    on large datasets, where every tab extracts the selected trial."""
    if frame is None or getattr(frame, "empty", True):
        return frame
    positions = _trial_positions(frame, cache_key=frame_fingerprint(frame))
    pos = positions.get((str(participant_id), str(trial_id)))
    if pos is None or len(pos) == 0:
        return frame.iloc[0:0]
    return frame.iloc[pos]


# -----------------------------------------------------------------------------
# Trial selection UI
# -----------------------------------------------------------------------------

# UX-10 · sorting the trial pool.
#
# The picker listed trials in data order, so finding "the slowest reader", "the
# one with the most fixations" or "the trials this reader got wrong" meant
# scrolling the whole list. These build a sort key per trial from three sources:
# computed per-trial stats, reader/text properties, and any trial-level column
# the dataset carries. Pure and frame-driven, so they're testable without the UI.
TRIAL_SORT_DEFAULT = "Trial ID"
#: UX-171: the order the trials appear in the data — the picker's default when
#: the combos carry it. ``Trial ID`` (sorted by id, so ``1, 10, 100, 2`` for
#: numeric ids) stays in the menu as a choice.
TRIAL_SORT_DATA_ORDER = "Data order"
# Computed stat label → (frame it needs, how to aggregate it per trial).
# "fixations" / "words" name which frame the aggregation runs on.
# DATA-66: these are the app's, not columns of the dataset, so they say so and
# are listed after the dataset's own columns.
_TRIAL_SORT_STATS = {
    "Fixation count (computed)": ("fixations", "size"),
    "Total fixation time, s (computed)": ("fixations", "duration_sum_s"),
    "Mean fixation duration, ms (computed)": ("fixations", "duration_mean"),
    "Word count (computed)": ("words", "size"),
    "First timestamp (computed)": ("fixations", "timestamp_min"),
}
# Columns worth offering as a sort key when the dataset carries them, in the
# order they're shown. Reader properties first, then text, then behaviour.
_TRIAL_SORT_PREFERRED_COLS = (
    "participant_id",
    "text_id",
    "unique_text_id",
    "paragraph_id",
    "difficulty_level",
    "question_preview",
    "repeated_reading_trial",
    "is_correct",
    "genre",
    "session",
    "pp_age",
    "pp_gender",
    "TRIAL_INDEX",
    "trial_index",
)

# Event/geometry fields can occasionally be constant by accident (for example a
# one-fixation trial), but that does not make them trial metadata. Keep them out
# of the generic metadata tail; computed timing/count keys above are the useful
# sortable representation of those event columns.
_TRIAL_SORT_EXCLUDED_COLS = {
    "trial_id",
    "unique_trial_id",
    "word",
    "token",
    "text",
    "sentence",
    "question",
    "answer",
    "response",
    "x",
    "y",
    "x_start",
    "x_end",
    "y_start",
    "y_end",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
    "width",
    "height",
    "timestamp",
    "timestamp_ms",
    "duration",
    "duration_ms",
    "order_in_trial",
    "fixation_index",
    "word_index",
    "word_id",
    "ia_id",
    "char_index",
    "line_index",
    "source_file",
}
_TRIAL_SORT_PRIVATE_NAME_PARTS = (
    "path",
    "filepath",
    "filename",
    "directory",
    "folder",
    "url",
    "uri",
)
_TRIAL_SORT_GEOMETRY_SUFFIXES = (
    "_x",
    "_y",
    "_xmin",
    "_xmax",
    "_ymin",
    "_ymax",
    "_x_start",
    "_x_end",
    "_y_start",
    "_y_end",
    "_width",
    "_height",
)


def _trial_sort_column_allowed(column: object) -> bool:
    """Whether ``column`` can be discovered as generic trial metadata."""
    name = str(column)
    lower = name.lower()
    if name.startswith("_") or lower in _TRIAL_SORT_EXCLUDED_COLS:
        return False
    if lower.endswith(_TRIAL_SORT_GEOMETRY_SUFFIXES):
        return False
    return not any(part in lower for part in _TRIAL_SORT_PRIVATE_NAME_PARTS)


def _effective_trial_field(
    frame: pd.DataFrame | None, trial_field: str, picker_ids: set[str]
) -> str | None:
    """Find the frame column that names the picker's effective trial ids."""
    if frame is None or frame.empty:
        return None
    for field in (trial_field, "unique_trial_id", "trial_id"):
        if field not in frame.columns:
            continue
        values = set(frame[field].dropna().astype(str).unique())
        if values & picker_ids:
            return field
    return None


def _is_missing_scalar(value) -> bool:
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, (bool, np.bool_)) else False


def _same_sort_value(left, right) -> bool:
    """Scalar equality for reconciling the words and fixations tables."""
    if _is_missing_scalar(left) or _is_missing_scalar(right):
        # Partial missingness is not a conflict; the table carrying a value wins.
        return True
    try:
        equal = left == right
    except (TypeError, ValueError):
        return False
    return bool(equal) if isinstance(equal, (bool, np.bool_)) else False


def _looks_like_free_text(series: pd.Series) -> bool:
    """Reject prose-like cells while retaining ordinary categorical metadata."""
    values = [str(v).strip() for v in series if not _is_missing_scalar(v)]
    return bool(values) and any(len(v) > 200 or len(v.split()) > 24 for v in values)


def _trial_level_columns_from_frame(
    frame: pd.DataFrame | None,
    trial_field: str,
    picker_ids: set[str],
    participants: set[str],
) -> dict[str, pd.Series]:
    """Discover one scalar value per active trial directly from one source table.

    Grouping includes participant identity, preventing repeated plain trial ids
    from being merged before the active picker scope is applied. The returned
    Series uses the picker's effective id because that is what
    ``sort_trial_options`` consumes.
    """
    identity = _effective_trial_field(frame, trial_field, picker_ids)
    if frame is None or frame.empty or identity is None:
        return {}

    scoped = frame
    if participants and "participant_id" in scoped.columns:
        scoped = scoped[scoped["participant_id"].astype(str).isin(participants)]
    scoped = scoped[scoped[identity].astype(str).isin(picker_ids)]
    if scoped.empty:
        return {}

    group_cols = [identity]
    if "participant_id" in scoped.columns and identity != "participant_id":
        group_cols.insert(0, "participant_id")
    grouped = scoped.groupby(group_cols, sort=False, dropna=False)
    discovered: dict[str, pd.Series] = {}
    for col in scoped.columns:
        if col == identity or not _trial_sort_column_allowed(col):
            continue
        try:
            if (grouped[col].nunique(dropna=False) > 1).any():
                continue
            if col in group_cols:
                values = scoped[group_cols].drop_duplicates().copy()
            else:
                values = grouped[col].agg(lambda cells: cells.iloc[0]).reset_index()
            # If the same effective id survives for multiple participants, it is
            # usable only when those rows agree. A participant-narrowed picker
            # naturally has one row here; a global ambiguous picker is not
            # allowed to choose one participant silently.
            by_id = values.groupby(values[identity].astype(str), sort=False)[col]
            if (by_id.nunique(dropna=False) > 1).any():
                continue
            deduped = values.drop_duplicates(subset=[identity])
        except (TypeError, ValueError):
            # Nested/list-like event payloads are not sortable scalar metadata.
            continue
        series = pd.Series(
            deduped[col].to_numpy(),
            index=deduped[identity].astype(str).to_numpy(),
        )
        if series.dropna().empty or _looks_like_free_text(series):
            continue
        discovered[str(col)] = series
    return discovered


def _merge_trial_level_sources(
    sources: Iterable[dict[str, pd.Series]],
) -> dict[str, pd.Series]:
    """Merge compatible metadata sources; omit cross-table disagreements."""
    by_column: dict[str, list[pd.Series]] = {}
    for source in sources:
        for col, series in source.items():
            by_column.setdefault(col, []).append(series)

    merged: dict[str, pd.Series] = {}
    for col, series_list in by_column.items():
        combined = pd.Series(dtype=object)
        conflict = False
        for series in series_list:
            current = series.copy()
            current.index = current.index.astype(str)
            for trial_id in combined.index.intersection(current.index):
                if not _same_sort_value(combined[trial_id], current[trial_id]):
                    conflict = True
                    break
            if conflict:
                break
            # pandas warns when concatenation/combine_first has to infer a
            # dtype from an empty object Series. The first real source needs no
            # merge at all; starting from it also preserves its native dtype.
            combined = current if combined.empty else combined.combine_first(current)
        if not conflict and not combined.empty:
            merged[col] = combined
    return merged


@st.cache_data(show_spinner=False, max_entries=16)
def _trial_level_sort_columns_cached(
    _combos: pd.DataFrame,
    _words: pd.DataFrame | None,
    _fixations: pd.DataFrame | None,
    trial_field: str,
    cache_key,
) -> dict[str, pd.Series]:
    """Cached metadata discovery over the participant-scoped picker frames."""
    del cache_key  # explicit hash input for the underscore-prefixed frames
    if _combos is None or _combos.empty or trial_field not in _combos.columns:
        return {}
    picker_ids = set(_combos[trial_field].dropna().astype(str).unique())
    participants = (
        set(_combos["participant_id"].dropna().astype(str).unique())
        if "participant_id" in _combos.columns
        else set()
    )
    return _merge_trial_level_sources(
        (
            _trial_level_columns_from_frame(
                _combos, trial_field, picker_ids, participants
            ),
            _trial_level_columns_from_frame(
                _words, trial_field, picker_ids, participants
            ),
            _trial_level_columns_from_frame(
                _fixations, trial_field, picker_ids, participants
            ),
        )
    )


def _trial_level_sort_columns(
    combos: pd.DataFrame,
    trial_field: str,
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
) -> dict[str, pd.Series]:
    return _trial_level_sort_columns_cached(
        combos,
        words,
        fixations,
        trial_field,
        cache_key=(
            frame_fingerprint(combos),
            frame_fingerprint(words),
            frame_fingerprint(fixations),
            trial_field,
        ),
    )


def _per_trial_stat(frame: pd.DataFrame, trial_field: str, how: str) -> pd.Series:
    """One computed stat per trial id, as a Series indexed by that id."""
    if frame is None or frame.empty or trial_field not in frame.columns:
        return pd.Series(dtype=float)
    grouped = frame.groupby(frame[trial_field].astype(str), sort=False)
    if how == "size":
        return grouped.size().astype(float)
    if how == "timestamp_min":
        if "timestamp_ms" not in frame.columns:
            return pd.Series(dtype=float)
        return pd.to_numeric(grouped["timestamp_ms"].min(), errors="coerce").astype(
            float
        )
    if "duration_ms" not in frame.columns:
        return pd.Series(dtype=float)
    durations = grouped["duration_ms"].agg("sum" if "sum" in how else "mean")
    return (durations / 1000.0) if how.endswith("_s") else durations.astype(float)


def trial_sort_keys(
    combos: pd.DataFrame,
    trial_field: str,
    *,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    label_of: Callable[[str], str] = str,
) -> dict[str, pd.Series]:
    """Available sort keys (UX-10): label → Series indexed by trial id.

    The dataset's own trial-level columns come first, each under ``label_of``
    (the dataset's own name, DATA-66 — `ColumnNames.label`), then the statistics
    Scanpath Studio computes per trial, marked as computed.

    Offers a computed stat only when the frame it needs is present, and a column
    only when it is actually trial-level in the active participant-scoped words,
    fixations, or combo frame. This deliberately discovers metadata before the
    lossy combo projection can discard it.
    """
    keys: dict[str, pd.Series] = {}
    # This rank was captured before build_combo_options' canonical sort.
    if (
        combos is not None
        and not combos.empty
        and trial_field in combos.columns
        and "_data_order" in combos.columns
    ):
        deduped = combos.drop_duplicates(subset=[trial_field])
        keys[TRIAL_SORT_DATA_ORDER] = pd.Series(
            deduped["_data_order"].to_numpy(),
            index=deduped[trial_field].astype(str).to_numpy(),
        )
    has_combos = (
        combos is not None and not combos.empty and trial_field in combos.columns
    )
    if has_combos:
        discovered = _trial_level_sort_columns(combos, trial_field, words, fixations)
        ordered_cols = [c for c in _TRIAL_SORT_PREFERRED_COLS if c in discovered]
        ordered_cols.extend(
            sorted(set(discovered) - set(ordered_cols), key=str.casefold)
        )
        labelled = [(col, label_of(col)) for col in ordered_cols if col != trial_field]
        # The dataset's own columns first, then the ones the app made.
        labelled.sort(key=lambda pair: pair[1].endswith(COMPUTED_SUFFIX))
        for col, label in labelled:
            series = discovered[col]
            if label in keys:
                # An alias read from the same column sorts the same way: once.
                if keys[label].equals(series):
                    continue
                label = f"{label} ({col})"
            elif label in (TRIAL_SORT_DEFAULT, TRIAL_SORT_DATA_ORDER):
                # A column the dataset itself calls "Trial ID" is not the menu's.
                label = f"{label} ({col})"
            keys[label] = series
    keys.update(
        _trial_sort_stats_cached(
            combos if has_combos else None,
            words,
            fixations,
            trial_field,
            cache_key=(
                frame_fingerprint(combos) if has_combos else None,
                frame_fingerprint(words),
                frame_fingerprint(fixations),
                trial_field,
            ),
        )
    )
    return keys


@st.cache_data(show_spinner=False, max_entries=16)
def _trial_sort_stats_cached(
    _combos: pd.DataFrame | None,
    _words: pd.DataFrame | None,
    _fixations: pd.DataFrame | None,
    trial_field: str,
    cache_key,
) -> dict[str, pd.Series]:
    """The computed sort keys (fixation count, reading time …), label → Series.

    Each is a group-by over the whole fixation or word table, ~0.25 s a rerun
    at OneStop scale for numbers that change only with the trial pool."""
    del cache_key  # explicit hash input for the underscore-prefixed frames
    picker_ids = (
        set(_combos[trial_field].dropna().astype(str).unique())
        if _combos is not None
        else set()
    )
    stats: dict[str, pd.Series] = {}
    for label, (which, how) in _TRIAL_SORT_STATS.items():
        frame = _fixations if which == "fixations" else _words
        field = _effective_trial_field(frame, trial_field, picker_ids)
        series = _per_trial_stat(frame, field or trial_field, how)
        if not series.empty:
            stats[label] = series
    return stats


def sort_trial_options(
    options: list[str],
    key_series: pd.Series | None,
    *,
    descending: bool = False,
) -> list[str]:
    """Order ``options`` (trial ids) by ``key_series``, ties broken by id.

    Trials the key doesn't cover sort last regardless of direction — an unranked
    trial is missing information, not an extreme value, so it shouldn't lead.
    """
    if key_series is None or key_series.empty:
        return sorted(options)
    lookup = key_series.to_dict()
    ranked = [o for o in options if o in lookup and pd.notna(lookup[o])]
    ranked_set = set(ranked)
    unranked = sorted(o for o in options if o not in ranked_set)
    ranked.sort(key=lambda o: (_sort_scalar(lookup[o]), o), reverse=descending)
    return ranked + unranked


def _sort_scalar(value):
    """A comparable key for a cell that may be numeric, boolean or text."""
    if isinstance(value, bool):
        return (0, float(value))
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, str(value))


def format_sort_value(value) -> str:
    """A sort key's value, short enough to ride along in a picker option.

    Sorting the pool is only useful if you can *see* what you sorted by — an
    ordering with the ordering key hidden just looks shuffled. Integers keep a
    thousands separator, floats get one decimal, booleans read Yes/No.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, (bool, np.bool_)):
        return "Yes" if value else "No"
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        return f"{number:,.0f}" if number == int(number) else f"{number:,.1f}"
    return str(value)


def _trial_display_label(trial_id) -> str:
    """Human-readable label for a trial id in the pickers.

    A per-page trial id reads cleanly — ``Lit_Alchemist_4__page_07`` →
    ``Lit_Alchemist_4 · page 7`` (the id stays zero-padded so it sorts
    numerically; only the display drops the padding). Any other id passes
    through unchanged, so this is a no-op for every other corpus. MultiplEYE
    used to be the one producing those ids; since DATA-24 its pages are screens
    inside one trial, so this is now generic dressing for whatever ships them."""
    text = str(trial_id)
    stim, sep, page = text.rpartition("__page_")
    if sep and page.isdigit():
        return f"{stim} · page {int(page)}"
    return text


# --- UX-187: a trial id spelled out part by part ------------------------------
# A trial id is usually several ids joined with "_" — OneStop's
# `l37_1129_2_2_1_Adv_r0` is reader `l37_1129`, text `2_2_1_Adv`, first reading.
# The pickers show it with " · " between the parts so you can tell where one
# ends, which a plain split on "_" cannot do: the reader id has an underscore of
# its own. So the parts are found from the ids the trial is known to be made of —
# its participant, its text, a composite mapping's columns — and an id that
# matches none of them is shown exactly as it is. Only the display changes: the
# selection, the deep link and every export keep the id itself.
#
# UX-202: the text id is one part, as it is everywhere else in the app (it was
# split into OneStop's batch · article · paragraph · level), and a first reading
# (`r0`) is not shown — only a repeated one says which reading it is.

#: What the pickers put between the parts of a trial id.
TRIAL_ID_PART_SEPARATOR = " · "

#: UX-202 — the reading number a first reading carries, which the display leaves
#: out. OneStop composes `_r0` / `_r1`; `data._disambiguate_repeated_readings`
#: leaves a first reading unsuffixed and numbers the next `_r2`.
FIRST_READING = "r0"

_READING_SUFFIX = re.compile(r"_(r\d+)$")


def trial_id_parts(
    trial_id,
    *,
    participant_id=None,
    text_id=None,
    components: list[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    """``(name, value)`` for each part of ``trial_id``, in the order it is written.

    ``components`` (a composite trial mapping's ``(column, value)`` pairs) are the
    answer outright. Otherwise the id is read as ``[<participant>_]<text>[_rN]``.
    An id that shape does not account for entirely is one part,
    ``("trial id", trial_id)``.
    """
    if components:
        return [(str(name), str(value)) for name, value in components]
    tid = str(trial_id)
    whole = [("trial id", tid)]
    pid = "" if participant_id is None else str(participant_id)
    text = "" if text_id is None else str(text_id)
    parts: list[tuple[str, str]] = []
    rest = tid
    if pid and rest.startswith(f"{pid}_"):
        parts.append(("participant", pid))
        rest = rest[len(pid) + 1 :]
    if text and text != tid and (rest == text or rest.startswith(f"{text}_")):
        parts.append(("text", text))
        rest = rest[len(text) + 1 :]
    # Split only an id its parts account for entirely: the text must be in it,
    # and anything after the text a reading number. `synthetic_2line_demo`
    # starts with its reader's id, but is not made of it.
    if not parts or parts[-1][0] == "participant":
        return whole
    if rest:
        if not (rest[:1] == "r" and rest[1:].isdigit()):
            return whole
        parts.append(("reading", rest))
    return parts


def shown_parts(parts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The parts the display writes: all but a first reading (UX-202)."""
    return [
        (name, value)
        for name, value in parts
        if not (name == "reading" and value == FIRST_READING)
    ]


def trial_id_display(parts: list[tuple[str, str]]) -> str:
    """A trial id as the pickers show it: its parts, `TRIAL_ID_PART_SEPARATOR`-joined.

    A first reading is left out (UX-202), and an id that does not split still
    has a trailing reading number set off by the separator, not an underscore.
    """
    parts = shown_parts(parts)
    if len(parts) == 1:
        label = _trial_display_label(parts[0][1])
        return _READING_SUFFIX.sub(rf"{TRIAL_ID_PART_SEPARATOR}\1", label)
    return TRIAL_ID_PART_SEPARATOR.join(value for _, value in parts)


def trial_id_layout(
    combos: pd.DataFrame,
    trial_field: str = "trial_id",
    *,
    composite_cols: Iterable[str] = (),
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Display string per trial id in ``combos``, plus the part names they share.

    ``composite_cols`` are the composite trial mapping's columns (carried on
    ``combos``). The part names are the most common shown layout's — what the
    picker's help names — with ``"reading"`` added when any trial shows one, and
    empty when no id splits.
    """
    if combos.empty or trial_field not in combos.columns:
        return {}, ()
    composite = [c for c in composite_cols if c in combos.columns]
    text_field = next(
        (c for c in ("unique_text_id", "text_id") if c in combos.columns), None
    )
    rows = combos.drop_duplicates(subset=[trial_field])
    trial_ids = rows[trial_field].astype(str).to_numpy()
    pids = rows["participant_id"].to_numpy() if "participant_id" in rows else None
    texts = rows[text_field].to_numpy() if text_field else None
    comp_values = (
        rows[composite].apply(stable_id).to_numpy() if len(composite) > 1 else None
    )
    display: dict[str, str] = {}
    layouts: dict[tuple[str, ...], int] = {}
    any_reading = False
    for i, tid in enumerate(trial_ids):
        parts = trial_id_parts(
            tid,
            participant_id=None if pids is None else pids[i],
            text_id=None if texts is None else texts[i],
            components=(
                None
                if comp_values is None
                else list(zip(composite, comp_values[i], strict=True))
            ),
        )
        display[tid] = trial_id_display(parts)
        shown = shown_parts(parts)
        if len(shown) > 1:
            names = tuple(name for name, _ in shown if name != "reading")
            layouts[names] = layouts.get(names, 0) + 1
            any_reading = any_reading or any(name == "reading" for name, _ in shown)
    names = max(layouts, key=layouts.__getitem__) if layouts else ()
    if names and any_reading:
        names = (*names, "reading")
    return display, names


def trial_id_shown(
    trial_id,
    *frames: pd.DataFrame | None,
    participant_id=None,
    composite_cols: Iterable[str] = (),
) -> str:
    """One trial's id as the pickers show it, read off the first of ``frames``
    (that trial's own rows) that has any. ``participant_id`` overrides the
    frame's — a cross-dataset B carries a namespaced one (`qualify_for_compare`)."""
    frame = next((f for f in frames if f is not None and not f.empty), None)
    if frame is None:
        return trial_id_display(trial_id_parts(trial_id))
    row = frame.iloc[:1].copy()
    row["trial_id"] = str(trial_id)
    if participant_id is not None:
        row["participant_id"] = participant_id
    display, _ = trial_id_layout(row, composite_cols=composite_cols)
    return display.get(str(trial_id), str(trial_id))


def trial_id_help(part_names: tuple[str, ...]) -> str:
    """The sentence the pickers' help gives about what a trial id is made of."""
    if not part_names:
        return ""
    sentence = (
        "A trial id is written as its parts, "
        f"**{TRIAL_ID_PART_SEPARATOR.join(part_names)}**."
    )
    if "reading" in part_names:
        sentence += (
            " A repeated reading ends in its number (`r1`, `r2` …); a first"
            " reading has none."
        )
    return sentence


def _render_trial_sort_popover(
    host,
    combos: pd.DataFrame,
    trial_field: str,
    key_prefix: str,
    *,
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
) -> tuple[pd.Series | None, bool, str]:
    """The ⇅ sort control beside the trial picker (UX-10).

    Lives in a popover rather than inline: the picker row is already a selectbox,
    a slider and two step buttons wide, and sorting is a "set it once" choice, not
    a per-trial one. Returns ``(key_series, descending, choice)`` for
    :func:`sort_trial_options` — ``(None, False, TRIAL_SORT_DEFAULT)`` for the
    default id order. The chosen key's *name* comes back too, because the picker
    labels the ordering it's showing.
    """
    keys = trial_sort_keys(
        combos,
        trial_field,
        words=words,
        fixations=fixations,
        label_of=active_all(st.session_state).label,
    )
    if not keys:
        return None, False, TRIAL_SORT_DEFAULT
    # UX-171: data order leads and is the default; Trial ID follows it.
    default = TRIAL_SORT_DATA_ORDER if TRIAL_SORT_DATA_ORDER in keys else None
    options = [
        *([default] if default else []),
        TRIAL_SORT_DEFAULT,
        *(k for k in keys if k != default),
    ]
    state_key = f"{key_prefix}_trial_sort"
    if st.session_state.get(state_key) not in options:
        st.session_state[state_key] = options[0]
    # UX-200: named for screen readers; `styles.py` draws ⇅ alone.
    with host.popover(
        "Sort the trial list",
        width="content",
        wrap=True,
        help="Sort the trial list",
        key=f"iconpop_sort_trial_{key_prefix}",
    ):
        choice = labeled(
            st,
            "selectbox",
            "Sort trials by",
            options=options,
            key=state_key,
            help="Reorder the trial list by a computed statistic or by a participant, "
            "text or condition property.",
        )
        descending = labeled(
            st,
            "checkbox",
            "Descending",
            key=f"{key_prefix}_trial_sort_desc",
            help="Reverse the order.",
        )
    if choice == TRIAL_SORT_DEFAULT:
        return None, False, TRIAL_SORT_DEFAULT
    return keys[choice], bool(descending), choice


# --- CMP-13: one ◀ ▶ that advances both compared trials ----------------------
# The two pickers are built in different modules (A here, B in `tabs.py`), so the
# linked step is a callback on one side writing the *other* side's selection. It
# needs the other list, which is why each picker publishes what it just rendered.
# Both directions clamp independently: per the settled call, a side that has run
# out simply stays put while the other keeps stepping.

#: The ⚙️ Compare options checkbox that arms the link. UI-only — a navigation
#: control, not a render setting, so it is deliberately not on the share link or
#: in a saved config (same call as ``share_identity_mode``).
COMPARE_STEP_LINK_KEY = "single_compare_step_linked"

#: Scanpath B's canonical selection (a *label*; see the snapshot note below).
COMPARE_TRIAL_KEY = "single_compare_trial"

#: What the *Compare To* picker last rendered: ``(label, participant, trial)``
#: per candidate, in display order.
COMPARE_OPTIONS_SNAPSHOT_KEY = "_compare_options_snapshot"


def trial_options_snapshot_key(key_prefix: str) -> str:
    """Session key holding the trial picker's options as it last rendered them."""
    return f"_{key_prefix}_trial_options" if key_prefix else "_trial_options"


def compare_step_linked() -> bool:
    """True when ◀ ▶ should advance scanpath A **and** B (CMP-13).

    Both halves matter: the checkbox only exists while compare mode is on, and
    Streamlit drops an unrendered widget's key, so a stale ``True`` must not
    quietly steer the main picker once the user has left compare mode.
    """
    return bool(
        st.session_state.get("single_compare_toggle")
        and st.session_state.get(COMPARE_STEP_LINK_KEY)
    )


def step_within(options: list[str], state_key: str, delta: int) -> int | None:
    """Move ``state_key``'s selection ``delta`` places within ``options``.

    Clamped to the ends, and clamped *independently* of any other picker — the
    linked step is "advance both", not "keep them aligned": the two pools have
    different sizes (B has its own filters, and a cross-dataset B is another
    corpus entirely), so their indices carry no shared meaning.

    Returns the new index, or ``None`` when there was nothing to step.
    """
    opts = list(options or [])
    if not opts:
        return None
    try:
        pos = opts.index(st.session_state.get(state_key))
    except ValueError:
        pos = 0
    new_pos = max(0, min(pos + delta, len(opts) - 1))
    st.session_state[state_key] = opts[new_pos]
    return new_pos


def at_list_end(options: list[str], state_key: str, delta: int) -> bool:
    """True when ``state_key``'s selection cannot move ``delta`` within ``options``.

    Used to decide whether a step button is dead. An unknown list answers
    **False** so the button stays live: a click that turns out to be a no-op is a
    better failure than a button greyed out while the other side could still move.
    """
    opts = list(options or [])
    if not opts:
        return False
    try:
        pos = opts.index(st.session_state.get(state_key))
    except ValueError:
        return False
    return not (0 <= pos + delta < len(opts))


def step_linked_compare(delta: int) -> None:
    """Advance scanpath **B** by ``delta``, resolved against the list A last saw.

    Written as an *identity* rather than an index or a label, because both are
    unstable across this step: ``build_comparison_options`` builds B's pool
    relative to A (📄 same-text first, then 👤 same-participant), so once A
    moves, B's list is re-ordered *and* re-labelled — the same trial can gain or
    lose its 📄 marker. Parking the identity in the same
    pending slot the ``?compare=`` deep link uses lets the rebuilt picker re-find
    the trial the user was actually looking at.
    """
    from .session_keys import PENDING_COMPARE_STATE_KEY

    snapshot = list(st.session_state.get(COMPARE_OPTIONS_SNAPSHOT_KEY) or [])
    if not snapshot:
        return
    labels = [row[0] for row in snapshot]
    try:
        pos = labels.index(st.session_state.get(COMPARE_TRIAL_KEY))
    except ValueError:
        pos = 0
    _, participant, trial = snapshot[max(0, min(pos + delta, len(snapshot) - 1))]
    st.session_state[PENDING_COMPARE_STATE_KEY] = {
        "participant_id": participant,
        "trial_id": trial,
    }


#: #374 F34 — ``{"<key prefix>|<dataset>": trial id}``: the trial each
#: dataset's picker was last on.
_TRIAL_BY_DATASET_KEY = "_trial_by_dataset"


def row_tail(column, key_prefix: str, reserve_screen_cell):
    """Lay out a selector row's last cell: the screen navigator, then the menus.

    ``reserve_screen_cell`` is handed the cell's container to keep a slot for
    the screen navigator (filled once the trial is resolved). Returns the
    ``railbtn_*`` cluster after it, where the row's ⇅ 🔎 ✏️ go — at the row's
    right end, while ◀ ▶ stay beside the slider they step.
    """
    tail = column.container(
        key=f"{key_prefix}_row_tail",
        horizontal=True,
        vertical_alignment="bottom",
        gap="small",
    )
    reserve_screen_cell(tail)
    return tail.container(key=f"railbtn_{key_prefix}_menus", width="content")


def _select_trial_none_mode(
    combos: pd.DataFrame,
    trial_field: str,
    text_field: str,
    key_prefix: str,
    picker_host=None,
    *,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    leading_renderer=None,
    filter_renderer=None,
    trailing_renderer=None,
) -> tuple[str | None, str | None, str | None]:
    """The trial picker: **dataset + selectbox + scrubbing slider + ◀ ▶ steps + ⇅
    sort + 🔎 filters**, all on one row (UX-64). The slider thumb shows ``index/TOTAL · id``
    (index first). The pool is narrowed upstream (the "Narrow by" multiselects +
    the "More" filters), so this just picks one trial from it and orders it.

    Creates its own row of columns, so call it where columns are allowed (the
    Scanpath/Corpus body), not nested inside another column. ``picker_host``
    (when given) is the container to render into; defaults to the current one.
    ``words`` / ``fixations`` (optional) unlock the computed sort keys (UX-10);
    without them only column-based orderings are offered.

    ``trailing_renderer`` (optional) is handed a slot in one more column at
    the row's right end — the multipart screen navigator, which the caller can
    only draw once the trial is resolved, so it keeps the slot and fills it
    later. The row's ⇅ 🔎 ✏️ then move after it (``row_tail``)."""
    host = picker_host if picker_host is not None else st
    available_trials = combos.drop_duplicates(subset=[trial_field])
    trial_options = sorted(available_trials[trial_field].dropna().astype(str).unique())
    if not trial_options:
        st.warning(
            "No trials match the filters. Clear one, or use ✕ Clear all filters."
        )
        st.stop()

    # Trial id → participant, so the annotation markers (UX-6) can be looked up per
    # option (annotations are keyed by (participant, trial)). Mirrors the selection
    # below, which resolves the participant the same way (first matching row).
    trial_to_pid = dict(
        zip(
            available_trials[trial_field].astype(str),
            available_trials["participant_id"],
            strict=True,
        )
    )

    # Populated once the ⇅ popover has rendered (below), and read by the option
    # labels — so an active ordering is *visible* in the picker itself rather than
    # only inside the popover that set it.
    sort_values: dict[str, str] = {}

    # UX-187: each id shown part by part, and the help says what the parts are.
    id_display, id_part_names = trial_id_layout(
        available_trials,
        trial_field,
        composite_cols=st.session_state.get("_composite_trial_columns") or (),
    )

    # Read once: a picker lists every trial in the pool, and going through the
    # session for each one cost ~0.3 s a rerun at OneStop scale.
    store = store_for_prefix()

    def _option_label(value: str) -> str:
        marks = annotation_markers(trial_to_pid.get(value), value, store=store)
        base = id_display.get(value) or _trial_display_label(value)
        # #374 F27: the badges follow the trial, so a narrow picker cuts the
        # badges rather than the trial.
        label = f"{base} {marks}" if marks else base
        shown = sort_values.get(value)
        return f"{label}  ·  {shown}" if shown else label

    # Every label made once, when the order is final (filled below): Streamlit
    # formats each option more than once a run, and the slider's twice over.
    option_labels: dict[str, str] = {}

    def _format_option(value: str) -> str:
        label = option_labels.get(value)
        return _option_label(value) if label is None else label

    n_trials = len(trial_options)
    picker_label = "Select trial"
    trial_id_key = f"{key_prefix}_trial_id" if key_prefix else None
    slider_key = f"{key_prefix}_trial_pos" if key_prefix else "trial_pos"

    # The selectbox (`*_trial_id`) is the canonical selection — the deep-link /
    # Save-&-restore code seeds it (`_restore_selection`). The slider mirrors it
    # and ◀ ▶ step it; all stay in sync via the trial id.
    current_label = st.session_state.get(trial_id_key) if trial_id_key else None
    # #374 F34: the trial each dataset was last on, so switching away and back
    # returns to it rather than to the first trial.
    dataset = annotations_dataset(st.session_state)
    remembered = st.session_state.setdefault(_TRIAL_BY_DATASET_KEY, {})
    last_dataset_key = f"{_TRIAL_BY_DATASET_KEY}_{key_prefix}"
    previous = st.session_state.get(last_dataset_key, dataset)
    st.session_state[last_dataset_key] = dataset
    # A trial carried over from the dataset left behind is not a choice; one a
    # link or a restored settings file put there with the switch is.
    chosen = st.session_state.pop(f"_{key_prefix}_trial_chosen", None)
    carried = (
        previous != dataset
        and current_label != chosen
        and current_label == remembered.get(f"{key_prefix}|{previous}")
    )
    back_to = remembered.get(f"{key_prefix}|{dataset}")
    if (
        trial_id_key
        and back_to in trial_options
        and (carried or current_label not in trial_options)
    ):
        current_label = back_to
        st.session_state[trial_id_key] = current_label
    # Seeded rather than chosen: re-seeded to the *sorted* list's first trial
    # once the ⇅ order is known (UX-171 — data order's first, not the id's).
    seeded = current_label not in trial_options
    if seeded:
        current_label = trial_options[0]
        if trial_id_key:
            st.session_state[trial_id_key] = current_label

    idx_of = {opt: i for i, opt in enumerate(trial_options)}

    if n_trials > 1:
        # Mirror the slider to the current selection BEFORE it renders, so picking
        # a trial in the dropdown moves the slider too; the drag callback writes
        # the selectbox key, reconciling next run.
        st.session_state[slider_key] = current_label

        def _on_trial_slider() -> None:
            if trial_id_key:
                st.session_state[trial_id_key] = st.session_state[slider_key]

        def _step_trial(delta: int) -> None:
            # ◀ / ▶ : move the canonical selection one trial earlier/later.
            if not trial_id_key:
                return
            step_within(trial_options, trial_id_key, delta)
            # CMP-13: while the link is armed, the same ±1 also moves scanpath B.
            if compare_step_linked():
                step_linked_compare(delta)

        def _slider_label(value: str) -> str:
            # index/TOTAL first, then the id — the slider doubles as the counter,
            # so a separate "Trial X / N" caption is redundant.
            return f"{idx_of.get(value, 0) + 1}/{n_trials}  ·  {_format_option(value)}"

        # UX-64 — ONE row for everything: [dataset] [trial] [slider] [◀ ▶ ⇅ 🔎].
        # The Narrow-by row above it is gone; its filters live in the 🔎 popover
        # at the end of this row. The dataset picker keeps its width on purpose
        # (you may be comparing two datasets, and the label is what tells them
        # apart) — the slider gives up the room instead, and the filter is an
        # icon, which is what makes six controls fit.
        #
        # The three triggers share ONE trailing column as a `railbtn_*` cluster
        # (UX-27), which styles.py packs right at a uniform 3px spacing. A column
        # each put a full gutter between them, so a prev/next *pair* didn't read
        # as a pair.
        lead_col, sel_col, slider_col, trail_col, *extra = host.columns(
            SELECTOR_ROW_GRID + ([SELECTOR_SCREEN_TRACK] if trailing_renderer else []),
            vertical_alignment="bottom",
        )
        if leading_renderer is not None:
            leading_renderer(lead_col)
        menus = (
            row_tail(extra[0], key_prefix, trailing_renderer)
            if trailing_renderer is not None
            else None
        )
        trail = trail_col.container(
            key=f"railbtn_{key_prefix}_trail{'_steps' if menus else ''}"
        )
        # Created in display order (◀ ▶ then ⇅) but filled out of order: the sort
        # popover has to render first, because the order it returns is what the
        # selectbox, the slider and the ◀ ▶ steps all walk. With a screen cell,
        # ⇅ 🔎 ✏️ close the row after it, and ◀ ▶ stay by the slider.
        step_col = trail.container(key=f"railbtn_{key_prefix}_step")
        cluster = trail if menus is None else menus
        sort_col = cluster.container(key=f"railbtn_{key_prefix}_sort")
        filter_col = cluster.container(key=f"railbtn_{key_prefix}_filter")
        # Filled by the caller, which owns the filter widgets — but created here,
        # in display order, so 🔎 lands after ⇅ in the cluster (UX-64).
        if filter_renderer is not None:
            filter_renderer(filter_col)
        # UX-10: order the pool *before* the widgets read `trial_options`, so the
        # selectbox, the slider and the ◀ ▶ steps all walk the same order. The
        # canonical selection is a trial *id*, so re-sorting never changes which
        # trial is selected — only where it sits in the list.
        # UX-27: each of the three step/sort triggers goes in a `railbtn_*`
        # container so styles.py can give the whole cluster above the plot one
        # button shape — these were square (each `width="stretch"` inside its own
        # narrow column) beside pill-shaped labelled buttons on the rows above
        # and below.
        sort_key, sort_desc, sort_choice = _render_trial_sort_popover(
            sort_col,
            combos,
            trial_field,
            key_prefix,
            words=words,
            fixations=fixations,
        )
        if sort_key is not None:
            trial_options = sort_trial_options(
                trial_options, sort_key, descending=sort_desc
            )
            idx_of = {opt: i for i, opt in enumerate(trial_options)}
            # UX-171: data order is the default and its values are bare ranks,
            # so it carries no per-option value and names itself only reversed.
            if sort_choice != TRIAL_SORT_DATA_ORDER:
                lookup = sort_key.to_dict()
                sort_values.update(
                    {opt: format_sort_value(lookup.get(opt)) for opt in trial_options}
                )
            if sort_choice != TRIAL_SORT_DATA_ORDER or sort_desc:
                picker_label = (
                    f"Select trial  ·  by {sort_choice} {'↓' if sort_desc else '↑'}"
                )
            if seeded:
                current_label = trial_options[0]
                if trial_id_key:
                    st.session_state[trial_id_key] = current_label
                st.session_state[slider_key] = current_label
        current_idx = trial_options.index(current_label)
    else:
        # A one-trial pool has no slider (`st.select_slider` throws on a single
        # option — BUG-23) and nothing to step through, but it still needs the
        # dataset picker and the filters: a pool of one is *usually the result of
        # a filter*, so this is exactly when the user reaches for them. UX-64.
        lead_col, sel_col, trail_col, *extra = host.columns(
            SELECTOR_ROW_TRIO + ([SELECTOR_SCREEN_TRACK] if trailing_renderer else []),
            vertical_alignment="bottom",
        )
        if leading_renderer is not None:
            leading_renderer(lead_col)
        menus = (
            row_tail(extra[0], key_prefix, trailing_renderer)
            if trailing_renderer is not None
            else None
        )
        if filter_renderer is not None:
            filter_renderer(
                (trail_col if menus is None else menus).container(
                    key=f"railbtn_{key_prefix}_filter_solo"
                )
            )

    # CMP-13: publish the list as rendered (post-sort), so the *Compare To*
    # picker's linked ◀ ▶ can step this picker without rebuilding its ordering.
    if trial_id_key:
        st.session_state[trial_options_snapshot_key(key_prefix)] = list(trial_options)
        # #374 F10: the browser identifies the picked option by its *label*, and
        # a label carries the trial's ★ 🏷️ 📝 marks. Written only when it moved,
        # the browser kept the label from that run; a tag added later renamed the
        # option, the old label matched nothing, and the view fell back to trial
        # 1. Written every run (as the slider is), the browser always holds the
        # label it was last shown, which the next run can still read back.
        st.session_state[trial_id_key] = current_label
        remembered[f"{key_prefix}|{dataset}"] = current_label

    option_labels.update({opt: _option_label(opt) for opt in trial_options})

    # The label is shown so its help "?" icon (the type-to-search hint) is visible
    # — a collapsed label hides it.
    selected_trial_label = sel_col.selectbox(
        picker_label,
        options=trial_options,
        key=trial_id_key,
        # BUG-80: the picker renders only on the Scanpath view, and Streamlit
        # drops an unrendered widget's key at the end of the run — so a trip to
        # Corpus Analysis or 🗂️ Data came back on trial 1 (and, in Compare,
        # left A and B on different texts). A value the pool no longer holds is
        # still reset above, before this renders.
        persist_state="session",
        format_func=_format_option,
        help=" ".join(
            filter(
                None,
                (
                    trial_id_help(id_part_names),
                    "Click this dropdown, then type to narrow the list. "
                    "★ favorite · 🏷️ tagged · 📝 has notes. When a sort key is "
                    "active, each option ends with that trial's value for it.",
                ),
            )
        ),
    )
    if trial_id_key:
        # The menu opens as wide as its longest trial id (+ marks / sort value).
        widen_menu(trial_id_key, option_labels.values())

    if n_trials > 1:
        slider_labels = {opt: _slider_label(opt) for opt in trial_options}
        with slider_col:
            st.select_slider(
                "Trial",
                options=trial_options,
                key=slider_key,
                persist_state="session",
                on_change=_on_trial_slider,
                help=f"Scrub through the {n_trials} trials (index/total · id, "
                "plus the sort value when one is active); the dropdown jumps to "
                "a specific id.",
                label_visibility="collapsed",
                format_func=lambda value: (
                    slider_labels.get(value) or _slider_label(value)
                ),
            )
        # Both step buttons in the keyed container reserved above, which styles.py
        # lays out as a flex ROW (a Streamlit vertical block stacks its children
        # by default).
        steps = step_col
        # CMP-13: linked, a button stays live until BOTH sides have run out — a
        # side at the end of its own list just stays put while the other keeps
        # stepping. `at_list_end` answers False for a list it can't see, so the
        # worst case is a click that moves only one scanpath.
        linked = compare_step_linked()
        compare_snapshot = (
            [
                row[0]
                for row in (st.session_state.get(COMPARE_OPTIONS_SNAPSHOT_KEY) or [])
            ]
            if linked
            else []
        )
        step_help = " Linked: also steps the compared trial." if linked else ""
        # UX-200: `spoken` names the glyph buttons for screen readers.
        steps.button(
            f"◀ {spoken('Previous trial')}",
            key=f"{key_prefix}_prev_trial" if key_prefix else "prev_trial",
            wrap=True,
            on_click=_step_trial,
            args=(-1,),
            disabled=current_idx == 0
            and (not linked or at_list_end(compare_snapshot, COMPARE_TRIAL_KEY, -1)),
            help="Previous trial." + step_help,
        )
        steps.button(
            f"▶ {spoken('Next trial')}",
            key=f"{key_prefix}_next_trial" if key_prefix else "next_trial",
            wrap=True,
            on_click=_step_trial,
            args=(1,),
            disabled=current_idx == n_trials - 1
            and (not linked or at_list_end(compare_snapshot, COMPARE_TRIAL_KEY, 1)),
            help="Next trial." + step_help,
        )

    if not selected_trial_label:
        return None, None, None

    chosen = available_trials[
        available_trials[trial_field].astype(str) == selected_trial_label
    ].iloc[0]
    selected_text = str(chosen[text_field]) if text_field in chosen.index else None
    return chosen["participant_id"], chosen["trial_id"], selected_text


def select_trial(
    combos: pd.DataFrame,
    key_prefix: str = "",
    picker_host=None,
    *,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    leading_renderer=None,
    filter_renderer=None,
    trailing_renderer=None,
) -> tuple[str | None, str | None, str, str | None]:
    """Pick a specific trial from the (already-narrowed) pool.

    There are no Browse-by modes anymore, and no per-mapping variants either: the
    pool is narrowed by the inline **Narrow by** Text / Participant multiselects +
    the **More** filters (``controls.render_narrow_by`` /
    ``render_trial_filters``), and this always picks one trial via the same
    selectbox + slider + ◀ ▶ arrows — whatever the Trial ID mapping looks like.

    BUG-23: a composite trial id (built from several mapped columns) used to get a
    picker of its own — first one selector per mapped component, then a Participant
    → Text cascade. Both made the *shape of the mapping* visible in the UI, and
    neither offered the slider or the step buttons, so stepping through trials
    worked on some datasets and not others. Participant and Text are what **Narrow
    by** is for; the composite flag now only tells the chip strip to spell the
    joined id out (``tabs._render_trial_condition_chips``).

    ``picker_host`` is the container to render into (defaults to the current one);
    the picker builds its own row of columns, so call it where columns are allowed.

    ``words`` / ``fixations`` (optional) are the frames ``combos`` was built from;
    passing them unlocks the UX-10 ⇅ sort popover's computed keys (fixation count,
    reading time). Without them the sort still offers the column-based orderings.

    Returns:
        Tuple of (participant_id, trial_id, selection_mode, selected_text).
        ``selection_mode`` is always ``"Trial"`` (kept for the comparison-options
        builder, which still supports the other modes when called directly).
    """
    if combos.empty:
        st.warning(
            "No trials match the filters. Clear one, or use ✕ Clear all filters."
        )
        st.stop()

    trial_field = (
        "unique_trial_id" if "unique_trial_id" in combos.columns else "trial_id"
    )
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"

    participant, trial, text = _select_trial_none_mode(
        combos,
        trial_field,
        text_field,
        key_prefix,
        picker_host=picker_host,
        # UX-64: the row's lead cell (the dataset picker) and its 🔎 filter
        # popover are filled by the caller, which owns those widgets.
        leading_renderer=leading_renderer,
        filter_renderer=filter_renderer,
        trailing_renderer=trailing_renderer,
        words=words,
        fixations=fixations,
    )

    return participant, trial, "Trial", text


# -----------------------------------------------------------------------------
# Statistics and metadata
# -----------------------------------------------------------------------------


def compute_trial_stats(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame
) -> dict[str, float]:
    """Compute summary statistics for a single trial."""
    total_time = None
    if "trial_dwell_time_ms" in trial_words.columns:
        dwell_values = (
            pd.to_numeric(trial_words["trial_dwell_time_ms"], errors="coerce")
            .dropna()
            .unique()
        )
        if len(dwell_values):
            total_time = float(dwell_values[0])
    if total_time is None:
        total_time = (
            float(trial_fixations["duration_ms"].sum())
            if not trial_fixations.empty
            else 0.0
        )
    return dict(
        total_reading_time_ms=total_time,
        total_reading_time_s=total_time / 1000.0,
        word_count=len(trial_words),
        fixation_count=len(trial_fixations),
    )


def safe_summary(series: pd.Series) -> dict:
    """Compute summary statistics for a series, handling empty data."""
    if series.empty:
        nan_val = float("nan")
        return dict(mean=nan_val, std=nan_val, min=nan_val, max=nan_val, median=nan_val)
    return dict(
        mean=float(series.mean()),
        std=float(series.std(ddof=0)),
        min=float(series.min()),
        max=float(series.max()),
        median=float(series.median()),
    )


# -----------------------------------------------------------------------------
# Comparison helpers
# -----------------------------------------------------------------------------


# Markers shown beside comparison-trial options.
SAME_TEXT_MARKER = (
    "📄"  # same stimulus text as the primary trial (★ reserved for favorites, UX-6)
)
SAME_PARTICIPANT_MARKER = "👤"  # same participant as the primary trial


def _allocate_label(label: str, qualified: str, used_labels: set[str]) -> str:
    """``label`` if unused, else ``qualified``, else ``qualified (n)`` for the
    first free ``n`` — always a label no earlier option holds (round 11: the
    qualified form itself could already be taken, by a trial id that reads
    like it, and the later option then overwrote the earlier one's identity)."""
    candidate = label if label not in used_labels else qualified
    n = 2
    while candidate in used_labels:
        candidate = f"{qualified} ({n})"
        n += 1
    used_labels.add(candidate)
    return candidate


def _compare_option_label(
    participant_id: str,
    trial_id: str,
    markers: str,
    used_labels: set[str],
) -> str:
    """Selectbox label for a comparison option: ``"<markers> <trial_id>"``.

    De-duplicates on ``trial_id`` (two participants can share one) by appending
    the participant in brackets — and a counter when even that is taken — so the
    label stays a unique selectbox option / dict key in
    ``tabs._render_compare_selector``."""
    trial_str = str(trial_id) if trial_id is not None else ""
    prefix = f"{markers} " if markers else ""
    return _allocate_label(
        f"{prefix}{trial_str}", f"{prefix}{trial_str} [{participant_id}]", used_labels
    )


def friendly_trial_label(
    participant_id: str,
    trial_id: str,
    text_id: str | None,
    existing_labels: set[str],
    prefix: str = "",
) -> str:
    """Create a short, de-duplicated label for comparison dropdowns/legends."""
    trial_str = str(trial_id) if trial_id is not None else ""
    text_str = str(text_id) if text_id is not None else ""
    text_str = text_str.strip()
    trial_contains_text = text_str and text_str.lower() in trial_str.lower()

    if text_str:
        base = f"{text_str} · {participant_id}"
        if not trial_contains_text:
            base = f"{base} (trial {trial_str})" if trial_str else base
        elif trial_str != text_str:
            # Surface any trial_id suffix beyond the text id (e.g. a
            # repeat-reading "_r2" tag added during normalization). Without
            # this the primary and compare titles look identical when a
            # participant re-read the same text.
            extra = trial_str
            if extra.lower().startswith(text_str.lower()):
                extra = extra[len(text_str) :].lstrip("_- ")
            if extra:
                base = f"{text_str} ({extra}) · {participant_id}"
    else:
        base = f"{trial_str} · {participant_id}" if trial_str else participant_id

    return _allocate_label(
        f"{prefix}{base}", f"{prefix}{base} [{trial_str or 'trial'}]", existing_labels
    )


def build_comparison_options(
    combos: pd.DataFrame,
    selection_mode: str,
    primary_participant: str,
    primary_trial: str,
    primary_text: str | None,
    *,
    cross_dataset: bool = False,
    include_primary: bool = True,
) -> list[tuple[str, str, str, str]]:
    """Build a prioritized list of comparison-trial options.

    Returns ``(participant_id, trial_id, label, markers)`` tuples, where
    ``markers`` leads with the relation icons ``"📄"`` (same text) / ``"👤"`` (same
    participant) and then the trial's annotation markers ``★`` (favorite) / ``🏷️``
    (tagged) / ``📝`` (noted) when present (UX-6), and ``label`` is
    ``"<markers> <trial_id>"``. Ordered: same-text (📄) first, then same-participant
    (👤), then the rest. A trial that is BOTH same-text and same-participant sorts
    with the 📄 group (text-matches lead) and shows both markers.

    ``cross_dataset`` (CMP-8 §5.1) says ``combos`` describes a *different*
    dataset, and degrades the three id-based signals that would otherwise lie:
    two corpora do not share readers, so 👤 never fires; a foreign trial's ★ /
    🏷️ / 📝 are read from *its* dataset's annotations, never the active
    dataset's, whose matching-looking ids name other trials (DATA-48 — they
    were dropped altogether before annotations were per dataset); and the
    primary trial is not in this pool, so a
    coincidentally identical ``(participant, trial)`` is a real candidate rather
    than the trial being compared. 📄 survives — a text id that matches across
    corpora is exactly the pairing this feature exists for.

    ``include_primary`` (CMP-22) keeps the selected trial itself in the pool, so
    B's picker lists every trial A's does and the two position readouts agree.
    It is only a *candidate*: the picker defaults B to the first trial that is
    not A. Pass ``False`` to ask "is there anything else to compare with?" —
    the question the Compare gate asks.
    """
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"
    uniq = combos.drop_duplicates(subset=["participant_id", "trial_id"])

    foreign_store = store_for_prefix("cmp") if cross_dataset else None
    rows: list[dict] = []
    for row in uniq.itertuples():
        if (
            not include_primary
            and not cross_dataset
            and (row.participant_id, row.trial_id)
            == (primary_participant, primary_trial)
        ):
            continue
        text_id = getattr(row, text_field, "")
        same_text = bool(primary_text and str(text_id) == str(primary_text))
        same_participant = not cross_dataset and bool(
            str(row.participant_id) == str(primary_participant)
        )
        markers = (
            (SAME_TEXT_MARKER if same_text else "")
            + (SAME_PARTICIPANT_MARKER if same_participant else "")
            + annotation_markers(row.participant_id, row.trial_id, store=foreign_store)
        )
        rows.append(
            {
                "participant_id": row.participant_id,
                "trial_id": row.trial_id,
                "same_text": same_text,
                "same_participant": same_participant,
                "markers": markers,
            }
        )

    # ★ group first, then 👤 group, then the rest. same_text is the primary sort
    # key so a both-★-👤 trial leads the ★ group. Stable sort preserves combos
    # order within a group.
    rows.sort(
        key=lambda r: (0 if r["same_text"] else 1, 0 if r["same_participant"] else 1)
    )

    used_labels: set[str] = set()
    options: list[tuple[str, str, str, str]] = []
    for r in rows:
        label = _compare_option_label(
            r["participant_id"], r["trial_id"], r["markers"], used_labels
        )
        options.append((r["participant_id"], r["trial_id"], label, r["markers"]))
    return options


# -----------------------------------------------------------------------------
# Cross-dataset comparison frames (CMP-8 · promoted from tabs.py for CMP-9)
# -----------------------------------------------------------------------------
# These live here, not in tabs.py, because three surfaces now build a
# cross-dataset comparison — the app, `api.compare_scanpaths` and
# `cli.render --compare-*` — and the namespacing rule below is the one piece of
# it that must not be re-derived per surface. `tests/test_compare_cross_dataset.py`
# exists because getting it wrong renders a *plausible-looking wrong figure*
# rather than an error.

#: Separator between a dataset name and a participant id in a qualified id.
COMPARE_DATASET_SEP = " · "


def qualify_for_compare(frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """A copy of ``frame`` whose ``participant_id`` is namespaced by ``dataset``.

    Two corpora can hold the same ``(participant_id, trial_id)``, and
    `plots.make_comparison_figure` slices its frame by exactly that pair — so an
    unqualified merge would silently render *the wrong scanpath*, or two.

    Only ever applied to the single-trial frames that feed the comparison
    builder. Nothing the annotations, the export slug, the deep link or Corpus
    Analysis reads goes through here: those key on the real ids, and must.
    """
    if frame.empty:
        return frame
    out = frame.copy()
    out["dataset"] = dataset
    out["participant_id"] = (
        dataset + COMPARE_DATASET_SEP + out["participant_id"].astype(str)
    )
    return out


def separate_self_compare(frame: pd.DataFrame, participant: str) -> pd.DataFrame:
    """A copy of B's single-trial ``frame`` renamed apart from A's (CMP-22).

    B may now be A's own trial. `plots.make_comparison_figure` slices its merged
    frame by ``(participant_id, trial_id)``, so two copies of one trial would hand
    *each* side both copies (and a duplicated index the word-line clustering
    rejects). Giving B's copy `self_compare_participant`'s id keeps the halves
    apart — the same trick `qualify_for_compare` plays across corpora, and just
    as figure-only: labels, lookups, exports and links keep the real id.
    """
    if frame.empty:
        return frame
    return frame.assign(participant_id=self_compare_participant(participant))


def self_compare_participant(participant: str) -> str:
    """The id `separate_self_compare` gives B's copy of ``participant``."""
    return f"{participant}{COMPARE_DATASET_SEP}B"


def qualified_participant(dataset: str, participant: str) -> str:
    """The id `qualify_for_compare` gives ``participant`` inside ``dataset``."""
    return f"{dataset}{COMPARE_DATASET_SEP}{participant}"


def unqualify_for_export(frame: pd.DataFrame, participant: str) -> pd.DataFrame:
    """Undo `qualify_for_compare`'s rename, restoring the corpus' own id.

    The namespace exists so `make_comparison_figure` can slice two colliding
    ``(participant, trial)`` pairs apart. An exported table must carry the id the
    corpus actually uses, or it won't join back to anything (CMP-8 §6). The
    stamped ``dataset`` column is kept — that is what disambiguates the rows.
    """
    if frame is None or frame.empty or "dataset" not in frame.columns:
        return frame
    out = frame.copy()
    out["participant_id"] = str(participant)
    return out


def align_compare_columns(
    a: pd.DataFrame, b: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, frozenset]:
    """Reindex two frames onto their column **union**, and report shared numerics.

    A bare ``pd.concat`` of frames with disjoint columns warns and churns dtypes
    (int columns become float once the other frame's rows fill in as NaN), which
    matters here because two corpora rarely ship the same measure set. Aligning
    first keeps the concat quiet and the dtypes stable.

    The third element is the columns both frames carry *as the same kind* —
    numeric in both, or categorical in both: what a cross-dataset figure may
    legitimately colour by (CMP-8 §5.4; categorical since Compare colours by a
    category too). A column present in only one corpus would colour one panel
    and blank the other, and one numeric on one side only would be a scale on
    one panel and a palette on the other.
    """
    union = list(dict.fromkeys([*a.columns, *b.columns]))
    a_aligned = a.reindex(columns=union) if list(a.columns) != union else a
    b_aligned = b.reindex(columns=union) if list(b.columns) != union else b
    shared = frozenset(
        col
        for col in set(a.columns) & set(b.columns)
        if pd.api.types.is_numeric_dtype(a[col])
        == pd.api.types.is_numeric_dtype(b[col])
    )
    return a_aligned, b_aligned, shared
