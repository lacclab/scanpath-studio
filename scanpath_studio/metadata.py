"""Keyed, entity-level metadata tables (DATA-20).

Milestone 1 is **participant grain**: a separate table whose rows are readers
and whose columns (``native_language``, ``age``, ``comprehension_score``, …)
should behave "as if they were fields in the data" — filterable, chip-able,
sortable, inspectable, exportable — without being any part of the recorded eye
movements.

Two rules shape everything here.

**The table stays separate.** It is never broadcast across every word/fixation
row: a 40-row participant table joined onto three million fixations costs
memory and buys nothing, and it would make a *reader* attribute look like a
per-fixation measurement. Instead the frame is kept as-is and consumed at three
narrow boundaries:

* *filtering* — a participant-grain constraint is a **participant** constraint,
  so :func:`participants_matching` turns a selection into the set of ids the
  existing participant filter already knows how to apply. No join at all.
* *projection* — :func:`project` left-joins chosen columns onto a **small**
  frame (the per-trial ``combos`` table, a group-by result), which is where
  sorting, grouping and chips read from.
* *display / export* — the frame itself, shown and written as its own table.

**Nothing is silently collapsed.** Duplicate participant rows that disagree are
not resolved by taking the first one: the id is reported as *conflicting* and
contributes no value, so a downstream field reads as missing rather than as an
arbitrary winner. Unmatched ids are reported on both sides — rows describing
readers who are not in the data, and readers in the data with no row.

**Milestone 2 is trial grain (DATA-29)**: the same idea one level down — a
table whose rows are *readings*. It reuses everything that is about validating a
keyed table (the dtype classification, the field registry, the join report, the
"conflicting rows are dropped, not resolved" rule) and differs only where the
grain genuinely differs:

* the **key** is the user's call — a trial id alone, or a reader **and** a trial
  id, because a repeated reading is a different trial for the same reader only
  in corpora that record it that way;
* **filtering** narrows to a set of ``(participant_id, trial_id)`` keys, applied
  by ``data.filter_to_keys`` — there is no participant-constraint indirection to
  mirror, because a trial constraint already *is* the grain the pool is keyed on.

Later grains (stimulus, screen, word, fixation) add rows to the same registry;
:class:`MetadataField` already carries ``grain``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .data import (
    stable_id,
    trial_id_series,
    trial_mapping_columns,
    zero_padding_map,
)
from .session_keys import COMPARE_SOURCE_STATE_KEY

# Source columns that plausibly hold the reader id, most explicit first. Shares
# the spirit of `data.pick_column`'s candidate lists: first hit wins, and the
# user can always override the guess in the UI.
PARTICIPANT_ID_CANDIDATES: tuple[str, ...] = (
    "participant_id",
    "participant",
    "subject_id",
    "subject",
    "reader_id",
    "reader",
    "pid",
    "RECORDING_SESSION_LABEL",
)

# Grain of a field — the entity one row describes. PARTICIPANT (DATA-20),
# TRIAL (DATA-29) and TEXT are ingested; the rest are named so the registry's
# shape is settled.
GRAIN_PARTICIPANT = "participant"
GRAIN_TRIAL = "trial"
GRAIN_TEXT = "text"

# Source columns that plausibly hold the trial id, most explicit first — the
# trial-grain twin of PARTICIPANT_ID_CANDIDATES, and deliberately the same names
# `data.TRIAL_ID_CANDIDATES` looks for, so a metadata file exported beside the
# data usually needs no picking at all.
TRIAL_ID_CANDIDATES: tuple[str, ...] = (
    "trial_id",
    "unique_trial_id",
    "trial",
    "trial_index",
    "TRIAL_INDEX",
    "item_id",
    "paragraph_id",
    "text_id",
)

# The text-grain twin of TRIAL_ID_CANDIDATES — most explicit first.
TEXT_ID_CANDIDATES: tuple[str, ...] = (
    "text_id",
    "unique_text_id",
    "text",
    "paragraph_id",
    "item_id",
    "stimulus_id",
    "stimulus",
)

# Loader bookkeeping, never user metadata: `data.read_tables` tags each row with
# the file it came from, which would otherwise be registered as a field called
# "Source file" and offered as a filter and a chip. Excluded here, in the one
# place every ingestion route passes through, rather than at each caller.
_BOOKKEEPING_COLUMNS = frozenset({"source_file"})

# Session state: the validated table, and the raw frame it was built from (kept
# so a different id column can be picked without re-uploading the file). Both
# are plain session state rather than widget keys — they are not wire format,
# and `session_keys.py` deliberately does not pin them.
SESSION_KEY = "_participant_metadata"
RAW_SESSION_KEY = "_participant_metadata_raw"
FILE_SESSION_KEY = "_participant_metadata_file"

# DATA-29 — the same three, for the trial table. Separate keys rather than one
# keyed-by-grain dict: the two tables are attached, replaced and cleared
# independently, and every consumer wants one of them specifically.
TRIAL_SESSION_KEY = "_trial_metadata"
TRIAL_RAW_SESSION_KEY = "_trial_metadata_raw"
TRIAL_FILE_SESSION_KEY = "_trial_metadata_file"

# The same three, for the text table (one row per text_id) — the third grain.
TEXT_SESSION_KEY = "_text_metadata"
TEXT_RAW_SESSION_KEY = "_text_metadata_raw"
TEXT_FILE_SESSION_KEY = "_text_metadata_file"

_DTYPE_CATEGORICAL = "categorical"
_DTYPE_NUMERIC = "numeric"
_DTYPE_BOOLEAN = "boolean"


@dataclass(frozen=True)
class MetadataField:
    """One registered column, with everything a consumer needs to place it."""

    name: str
    label: str
    grain: str
    dtype: str
    source: str
    n_unique: int
    n_missing: int

    @property
    def is_numeric(self) -> bool:
        return self.dtype == _DTYPE_NUMERIC

    @property
    def is_categorical(self) -> bool:
        return self.dtype in (_DTYPE_CATEGORICAL, _DTYPE_BOOLEAN)


@dataclass(frozen=True)
class JoinReport:
    """What happened when the table met the participants actually loaded.

    Every count is a list of ids rather than a number so the UI can name them —
    "3 unmatched" is not actionable, "``p07``, ``p12``, ``p31``" is.
    """

    matched: tuple[str, ...] = ()
    only_in_table: tuple[str, ...] = ()
    only_in_data: tuple[str, ...] = ()
    duplicated: tuple[str, ...] = ()
    conflicting: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not (
            self.only_in_table
            or self.only_in_data
            or self.duplicated
            or self.conflicting
        )


@dataclass(frozen=True)
class ParticipantMetadata:
    """A validated participant table plus its field registry.

    ``frame`` is indexed by nothing in particular but always carries a string
    ``participant_id`` column; conflicting ids have been dropped from it (and
    named in :attr:`report`), so a lookup either finds one unambiguous row or
    finds none.
    """

    frame: pd.DataFrame
    fields: tuple[MetadataField, ...]
    source_name: str
    id_column: str
    report: JoinReport = JoinReport()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    def field(self, name: str) -> MetadataField | None:
        for candidate in self.fields:
            if candidate.name == name:
                return candidate
        return None

    def values_for(self, participant_id) -> dict[str, object]:
        """Every registered value for one reader (missing ids give ``{}``)."""
        if self.frame.empty:
            return {}
        match = self.frame[self.frame["participant_id"] == str(participant_id)]
        if match.empty:
            return {}
        row = match.iloc[0]
        return {name: row[name] for name in self.names if name in match.columns}

    @property
    def joined_frame(self) -> pd.DataFrame:
        """Only the rows describing readers that are actually loaded.

        What the *controls* must be built from. Offering a value that belongs to
        a reader the report has just called "not loaded — ignored" gives the
        user a filter that can only ever empty the pool, and stretches a numeric
        slider to a bound nobody in the data has. With no participant list to
        join against (``participants=None``), the report matches everything and
        this is the whole frame.
        """
        if self.frame.empty:
            return self.frame
        return self.frame[self.frame["participant_id"].isin(set(self.report.matched))]

    def series(self, name: str) -> pd.Series:
        """``participant_id`` → value for one field, for projection/lookup."""
        if self.frame.empty or name not in self.frame.columns:
            return pd.Series(dtype="object")
        return self.frame.set_index("participant_id")[name]


@dataclass(frozen=True)
class TrialMetadata:
    """A validated trial table plus its field registry (DATA-29).

    ``frame`` always carries a string ``trial_id`` column, and a string
    ``participant_id`` column as well when the table is keyed by both. Rows
    whose key repeats *with different values* have been dropped and named in
    :attr:`report`, so a lookup either finds one unambiguous row or none — the
    same rule the participant table follows.

    ``keyed_by_participant`` is the user's answer to the question DATA-29 opened
    with. It is not inferred: a corpus where every reader reads every text can
    key by trial id alone and mean it, and one with repeated readings cannot,
    and nothing in the file itself says which world you are in.
    """

    frame: pd.DataFrame
    fields: tuple[MetadataField, ...]
    source_name: str
    trial_column: str
    participant_column: str | None = None
    report: JoinReport = JoinReport()

    @property
    def keyed_by_participant(self) -> bool:
        return bool(self.participant_column)

    @property
    def key_columns(self) -> tuple[str, ...]:
        return (
            ("participant_id", "trial_id")
            if self.keyed_by_participant
            else ("trial_id",)
        )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    def field(self, name: str) -> MetadataField | None:
        for candidate in self.fields:
            if candidate.name == name:
                return candidate
        return None

    def key_series(self) -> pd.Series:
        """The frame's own keys, as the string tuples the reports speak in."""
        if self.frame.empty:
            return pd.Series(dtype="object")
        if self.keyed_by_participant:
            return pd.Series(
                list(
                    zip(
                        self.frame["participant_id"].astype(str),
                        self.frame["trial_id"].astype(str),
                    )
                ),
                index=self.frame.index,
            )
        return self.frame["trial_id"].astype(str)

    @property
    def joined_frame(self) -> pd.DataFrame:
        """Only the rows describing trials that are actually loaded.

        What the *controls* are built from, for `ParticipantMetadata`'s reason:
        offering a value that belongs to a trial the report has just called "not
        loaded — ignored" gives the user a filter that can only empty the pool.
        """
        if self.frame.empty:
            return self.frame
        return self.frame[self.key_series().isin(set(self.report.matched))]

    def values_for(self, participant_id, trial_id) -> dict[str, object]:
        """Every registered value for one reading (an unknown key gives ``{}``)."""
        if self.frame.empty:
            return {}
        match = self.frame[self.frame["trial_id"] == str(trial_id)]
        if self.keyed_by_participant:
            match = match[match["participant_id"] == str(participant_id)]
        if match.empty:
            return {}
        row = match.iloc[0]
        return {name: row[name] for name in self.names if name in match.columns}


@dataclass(frozen=True)
class TextMetadata:
    """A validated text table plus its field registry — the third grain.

    ``frame`` always carries a string ``text_id`` column; conflicting ids have
    been dropped from it (and named in :attr:`report`), the same rule
    :class:`ParticipantMetadata`/:class:`TrialMetadata` follow. Flat grain —
    one row per text, joined the way :class:`ParticipantMetadata` joins by
    reader, never :class:`TrialMetadata`'s participant-pairing option: a text
    is a stimulus, not something one reader owns.
    """

    frame: pd.DataFrame
    fields: tuple[MetadataField, ...]
    source_name: str
    text_column: str
    report: JoinReport = JoinReport()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    def field(self, name: str) -> MetadataField | None:
        for candidate in self.fields:
            if candidate.name == name:
                return candidate
        return None

    def values_for(self, text_id) -> dict[str, object]:
        """Every registered value for one text (an unknown id gives ``{}``)."""
        if self.frame.empty:
            return {}
        match = self.frame[self.frame["text_id"] == str(text_id)]
        if match.empty:
            return {}
        row = match.iloc[0]
        return {name: row[name] for name in self.names if name in match.columns}

    @property
    def joined_frame(self) -> pd.DataFrame:
        """Only the rows describing texts that are actually loaded.

        Same reasoning as :attr:`ParticipantMetadata.joined_frame` — the
        controls must be built from what is on screen, not from every text
        the table happens to mention.
        """
        if self.frame.empty:
            return self.frame
        return self.frame[self.frame["text_id"].isin(set(self.report.matched))]

    def series(self, name: str) -> pd.Series:
        """``text_id`` → value for one field, for projection/lookup."""
        if self.frame.empty or name not in self.frame.columns:
            return pd.Series(dtype="object")
        return self.frame.set_index("text_id")[name]


def _rows_with_ids(frame: pd.DataFrame, columns) -> pd.DataFrame:
    """A copy of ``frame`` without the rows that have no value in an id column.

    A blank row — the one Excel leaves at the end of a sheet — became a phantom
    reader named "nan": under pandas 3 a missing id stays NaN through
    ``stable_id``, and the ``!= ""`` test that used to drop it let NaN
    through (BUG-60). A composite id with a missing part raised in the join
    instead. Such a row describes no one, so it goes.
    """
    ids = frame[list(columns)]
    missing = ids.isna() | ids.apply(lambda c: c.astype(str).str.strip() == "")
    return frame.loc[~missing.any(axis=1)].copy()


def active_trials() -> TrialMetadata | None:
    """The trial table attached to this session, or ``None`` (DATA-29)."""
    try:
        import streamlit as st

        return st.session_state.get(TRIAL_SESSION_KEY)
    except Exception:  # no script run context (API, CLI, plain import)
        return None


def trial_keys(combos: pd.DataFrame | None) -> set:
    """The ``(participant_id, trial_id)`` pairs the loaded data actually has."""
    if combos is None or combos.empty:
        return set()
    if not {"participant_id", "trial_id"} <= set(combos.columns):
        return set()
    pairs = combos[["participant_id", "trial_id"]].astype(str).drop_duplicates()
    return set(map(tuple, pairs.to_numpy()))


def infer_trial_id_column(frame: pd.DataFrame) -> str | None:
    """First plausible trial-id column, or ``None`` — the UI's initial guess."""
    if frame is None or frame.empty:
        return None
    lookup = {str(column).lower(): str(column) for column in frame.columns}
    for candidate in TRIAL_ID_CANDIDATES:
        hit = lookup.get(candidate.lower())
        if hit is not None:
            return hit
    return None


def _trial_column_label(trial_column) -> str:
    """Display form of a (possibly composite) trial-column mapping — joined
    with " + ", matching how the wizard spells a composite trial id back out."""
    return " + ".join(trial_mapping_columns(trial_column))


def build_trial_metadata(
    frame: pd.DataFrame,
    trial_column: str | list[str],
    participant_column: str | None = None,
    *,
    source_name: str = "trial metadata",
    keys: Iterable | None = None,
) -> TrialMetadata:
    """Validate a raw trial table into a registry + clean frame (DATA-29).

    ``trial_column`` is a single column name, or **several** to build a unique
    trial id on the fly (joined with ``_``, like the Trial ID mapping the
    uploaded data itself uses — see :func:`data.trial_id_series`) — for a
    table whose own trial id needs the same composite key the data does.

    The participant half of the key is **optional and explicit**: pass
    ``participant_column`` to key by reader *and* trial. ``keys`` is the set of
    ``(participant_id, trial_id)`` pairs present in the loaded data, which fills
    in the two "unmatched" halves of the report — and, when the table is keyed by
    trial alone, is collapsed to trial ids first so a table that legitimately
    describes one reading per text is not reported as missing every reader.

    Mirrors :func:`build_participant_metadata` deliberately, including the rule
    that duplicate rows are only a problem when they *disagree*.
    """
    trial_cols = trial_mapping_columns(trial_column)
    label = _trial_column_label(trial_column)
    empty = TrialMetadata(
        pd.DataFrame(columns=["trial_id"]),
        (),
        source_name,
        label,
        str(participant_column) if participant_column else None,
    )
    if (
        frame is None
        or frame.empty
        or not trial_cols
        or any(c not in frame.columns for c in trial_cols)
    ):
        return empty
    if participant_column and participant_column not in frame.columns:
        participant_column = None

    work = _rows_with_ids(
        frame, [*trial_cols, *([participant_column] if participant_column else [])]
    )
    # `trial_id_series` — not a plain `.astype(str)` — so this table's own
    # trial id is spelled the same way `data.normalize_*` spells the app's: a
    # blank cell anywhere else in *this* file's trial-id column is enough to
    # read it as floats ("101.0") against the data's "101", and the join below
    # would silently match nothing (DATA-29's "no reading matched" is exactly
    # this) — and a composite id is built the identical way (joined with "_",
    # each part through `stable_id` first).
    work["trial_id"] = trial_id_series(work, trial_column)
    if participant_column:
        work["participant_id"] = stable_id(work[participant_column])
    reserved = {
        *trial_cols,
        str(participant_column) if participant_column else "",
        "trial_id",
        "participant_id",
        *_BOOKKEEPING_COLUMNS,
    }
    value_columns = [
        str(column) for column in frame.columns if str(column) not in reserved
    ]

    key_frame = (
        pd.Series(list(zip(work["participant_id"], work["trial_id"])), index=work.index)
        if participant_column
        else work["trial_id"]
    )
    duplicated = tuple(sorted(set(key_frame[key_frame.duplicated()]), key=str))
    conflicting: list = []
    if duplicated:
        for key, group in work.groupby(key_frame, sort=False):
            if key not in set(duplicated):
                continue
            for column in value_columns:
                if group[column].dropna().nunique() > 1:
                    conflicting.append(key)
                    break
    conflicting_set = set(conflicting)
    keep = ~key_frame.isin(conflicting_set)
    work, key_frame = work[keep], key_frame[keep]
    first = ~key_frame.duplicated(keep="first")
    work, key_frame = work[first], key_frame[first]

    clean = pd.DataFrame({"trial_id": work["trial_id"].to_numpy()})
    if participant_column:
        clean.insert(0, "participant_id", work["participant_id"].to_numpy())
    fields: list[MetadataField] = []
    for column in value_columns:
        dtype = _classify(work[column])
        values = _coerce(work[column], dtype)
        clean[column] = values.to_numpy()
        fields.append(
            MetadataField(
                name=column,
                label=field_label(column),
                grain=GRAIN_TRIAL,
                dtype=dtype,
                source=source_name,
                n_unique=int(values.dropna().nunique()),
                n_missing=int(values.isna().sum()),
            )
        )

    metadata = TrialMetadata(
        clean,
        tuple(fields),
        source_name,
        label,
        str(participant_column) if participant_column else None,
        JoinReport(
            matched=tuple(sorted(set(key_frame), key=str)),
            duplicated=tuple(sorted(duplicated, key=str)),
            conflicting=tuple(sorted(conflicting_set, key=str)),
        ),
    )
    if keys is None:
        return metadata
    return rejoin_trials(metadata, keys)


def rejoin_trials(metadata: TrialMetadata, keys: Iterable) -> TrialMetadata:
    """Recompute the join report against the trials actually loaded (DATA-29).

    ``keys`` are ``(participant_id, trial_id)`` pairs; a table keyed by trial
    alone is compared on the trial half, so "this file describes texts, not
    readings" is a supported answer rather than a report full of misses.
    """
    data_keys = {tuple(str(part) for part in key) for key in keys}
    if not metadata.keyed_by_participant:
        data_keys = {key[1] for key in data_keys if len(key) > 1}
    table_keys = set(metadata.key_series()) | set(metadata.report.conflicting)
    usable = set(metadata.key_series())
    return TrialMetadata(
        metadata.frame,
        metadata.fields,
        metadata.source_name,
        metadata.trial_column,
        metadata.participant_column,
        JoinReport(
            matched=tuple(sorted(usable & data_keys, key=str)),
            only_in_table=tuple(sorted(table_keys - data_keys, key=str)),
            only_in_data=tuple(sorted(data_keys - table_keys, key=str)),
            duplicated=metadata.report.duplicated,
            conflicting=metadata.report.conflicting,
        ),
    )


def trials_matching(
    metadata: TrialMetadata | None,
    selections: dict[str, Sequence] | None = None,
    ranges: dict[str, tuple[float, float]] | None = None,
    *,
    keys: Iterable | None = None,
) -> set | None:
    """``(participant_id, trial_id)`` keys satisfying every trial constraint.

    ``None`` means "no constraint" — the same contract as
    :func:`participants_matching`, and for the same reason: an empty selection
    must not narrow the pool to the trials the table happens to list.

    ``keys`` are the loaded trials, needed for two things a trial-grain table
    cannot do without: expanding a trial-id-keyed table back to the readings
    that share that trial id, and keeping the trials the table never mentions
    when the only constraint is a numeric range (``data.filter_trials``' rule
    that a range narrows rather than excludes the unmeasured — UX-49).
    """
    if metadata is None or metadata.frame.empty:
        return None
    active_selections = {
        name: list(values)
        for name, values in (selections or {}).items()
        if values and name in metadata.frame.columns
    }
    active_ranges = {
        name: bounds
        for name, bounds in (ranges or {}).items()
        if bounds and name in metadata.frame.columns
    }
    if not active_selections and not active_ranges:
        return None

    frame = metadata.frame
    mask = pd.Series(True, index=frame.index)
    for name, values in active_selections.items():
        allowed = {str(value) for value in values}
        mask &= frame[name].astype(str).isin(allowed)
    for name, (low, high) in active_ranges.items():
        numeric = pd.to_numeric(frame[name], errors="coerce")
        mask &= numeric.between(low, high) | numeric.isna()
    matching = set(metadata.key_series()[mask])

    loaded = {tuple(str(part) for part in key) for key in (keys or ())}
    if metadata.keyed_by_participant:
        result = {key for key in loaded if key in matching} if loaded else set(matching)
    else:
        # Trial-id grain describes every reading of that trial.
        result = {key for key in loaded if key[1] in matching}
    if not active_selections and loaded:
        # Range-only narrowing keeps the unmeasured, including a reading with no
        # row at all — the participant table's rule, one grain down.
        described = (
            matching
            if metadata.keyed_by_participant
            else {key for key in loaded if key[1] in set(metadata.key_series())}
        )
        result |= {key for key in loaded if key not in described}
    return result


def project_trials(
    metadata: TrialMetadata | None,
    frame: pd.DataFrame,
    columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Left-join chosen trial-metadata columns onto a **small** trial-keyed frame.

    For ``combos`` (one row per trial) — never for words or fixations, which is
    the rule the participant table follows for the same reason. Columns already
    on ``frame`` win, so a recorded column is never shadowed.
    """
    if (
        metadata is None
        or metadata.frame.empty
        or frame is None
        or frame.empty
        or "trial_id" not in frame.columns
    ):
        return frame
    if metadata.keyed_by_participant and "participant_id" not in frame.columns:
        return frame
    wanted = [
        name
        for name in (list(columns) if columns is not None else list(metadata.names))
        if name in metadata.frame.columns and name not in frame.columns
    ]
    if not wanted:
        return frame
    out = frame.copy()
    if metadata.keyed_by_participant:
        keys = pd.Series(
            list(zip(out["participant_id"].astype(str), out["trial_id"].astype(str))),
            index=out.index,
        )
    else:
        keys = out["trial_id"].astype(str)
    lookup = metadata.frame.set_index(metadata.key_series())
    for name in wanted:
        out[name] = keys.map(lookup[name])
    return out


def trial_options_for(metadata: TrialMetadata | None, name: str) -> list[str]:
    """Sorted distinct values of a categorical trial field, for a multiselect."""
    if metadata is None or metadata.frame.empty or name not in metadata.frame.columns:
        return []
    return sorted({str(value) for value in metadata.joined_frame[name].dropna()})


def trial_bounds_for(
    metadata: TrialMetadata | None, name: str
) -> tuple[float, float] | None:
    """``(min, max)`` of a numeric trial field over the loaded trials."""
    if metadata is None or metadata.frame.empty or name not in metadata.frame.columns:
        return None
    numeric = pd.to_numeric(metadata.joined_frame[name], errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.min()), float(numeric.max())


def trial_to_payload(metadata: TrialMetadata | None) -> dict | None:
    """Serialize the trial table for save & restore (DATA-29)."""
    if metadata is None or metadata.frame.empty:
        return None
    return {
        "source_name": metadata.source_name,
        "trial_column": metadata.trial_column,
        "participant_column": metadata.participant_column,
        "rows": metadata.frame.to_dict("records"),
    }


def trial_from_payload(payload: dict | None) -> TrialMetadata | None:
    """Rebuild a trial table from :func:`trial_to_payload`'s output."""
    if not isinstance(payload, dict) or not payload.get("rows"):
        return None
    frame = pd.DataFrame(payload["rows"])
    trial_column = str(payload.get("trial_column") or "trial_id")
    participant_column = payload.get("participant_column")
    if "trial_id" in frame.columns:
        # The payload holds the *clean* frame, whose key columns are already
        # canonical — rebuild against those rather than the original names.
        return build_trial_metadata(
            frame,
            "trial_id",
            "participant_id" if participant_column else None,
            source_name=str(payload.get("source_name") or "trial metadata"),
        )
    return build_trial_metadata(
        frame,
        trial_column,
        participant_column,
        source_name=str(payload.get("source_name") or "trial metadata"),
    )


def active_texts() -> TextMetadata | None:
    """The text table attached to this session, or ``None``."""
    try:
        import streamlit as st

        return st.session_state.get(TEXT_SESSION_KEY)
    except Exception:  # no script run context (API, CLI, plain import)
        return None


def text_keys(combos: pd.DataFrame | None) -> set:
    """The distinct ``text_id`` values the loaded data actually has."""
    if combos is None or combos.empty or "text_id" not in combos.columns:
        return set()
    return {str(value) for value in combos["text_id"].dropna().unique()}


def infer_text_id_column(frame: pd.DataFrame) -> str | None:
    """First plausible text-id column, or ``None`` — the UI's initial guess."""
    if frame is None or frame.empty:
        return None
    lookup = {str(column).lower(): str(column) for column in frame.columns}
    for candidate in TEXT_ID_CANDIDATES:
        hit = lookup.get(candidate.lower())
        if hit is not None:
            return hit
    return None


def _text_column_label(text_column) -> str:
    """Display form of a (possibly composite) text-column mapping — joined
    with " + ", matching how the wizard spells a composite trial id back out."""
    return " + ".join(trial_mapping_columns(text_column))


def build_text_metadata(
    frame: pd.DataFrame,
    text_column: str | list[str],
    *,
    source_name: str = "text metadata",
    keys: Iterable | None = None,
) -> TextMetadata:
    """Validate a raw text table into a registry + clean frame — third grain.

    ``text_column`` is a single column name, or **several** to build a unique
    text id on the fly (joined with ``_``, like the Trial ID mapping the
    uploaded data itself uses — see :func:`data.trial_id_series`), the same
    composite-key trick :func:`build_trial_metadata` uses. The join/report
    logic underneath is flat, though — one dimension (``text_id``), never
    :func:`build_trial_metadata`'s participant-pairing option, since a text is
    a stimulus and nothing reads it as belonging to one reader.

    ``keys`` is the set of text ids actually present in the loaded data;
    passing it fills in the two "unmatched" halves of the report. Rows whose
    id repeats are only a problem when they *disagree* — the rule every grain
    here follows.
    """
    text_cols = trial_mapping_columns(text_column)
    label = _text_column_label(text_column)
    empty = TextMetadata(pd.DataFrame(columns=["text_id"]), (), source_name, label)
    if (
        frame is None
        or frame.empty
        or not text_cols
        or any(c not in frame.columns for c in text_cols)
    ):
        return empty

    work = _rows_with_ids(frame, text_cols)
    # See the matching comment in `build_trial_metadata` — the same "one
    # blank cell spells the id two ways" hazard applies to a text id.
    work["text_id"] = trial_id_series(work, text_column)
    reserved = {*text_cols, "text_id", *_BOOKKEEPING_COLUMNS}
    value_columns = [
        str(column) for column in frame.columns if str(column) not in reserved
    ]

    duplicated = tuple(sorted(set(work.loc[work["text_id"].duplicated(), "text_id"])))
    conflicting: list[str] = []
    if duplicated:
        for tid, group in work[work["text_id"].isin(duplicated)].groupby(
            "text_id", sort=True
        ):
            for column in value_columns:
                if group[column].dropna().nunique() > 1:
                    conflicting.append(str(tid))
                    break
    conflicting_set = set(conflicting)
    work = work[~work["text_id"].isin(conflicting_set)]
    work = work.drop_duplicates(subset=["text_id"], keep="first")

    fields: list[MetadataField] = []
    clean = pd.DataFrame({"text_id": work["text_id"].to_numpy()})
    for column in value_columns:
        dtype = _classify(work[column])
        values = _coerce(work[column], dtype)
        clean[column] = values.to_numpy()
        fields.append(
            MetadataField(
                name=column,
                label=field_label(column),
                grain=GRAIN_TEXT,
                dtype=dtype,
                source=source_name,
                n_unique=int(values.dropna().nunique()),
                n_missing=int(values.isna().sum()),
            )
        )

    table_ids = set(clean["text_id"]) | conflicting_set
    if keys is None:
        report = JoinReport(
            matched=tuple(sorted(clean["text_id"])),
            duplicated=duplicated,
            conflicting=tuple(sorted(conflicting_set)),
        )
    else:
        data_ids = {str(tid) for tid in keys}
        report = JoinReport(
            matched=tuple(sorted(set(clean["text_id"]) & data_ids)),
            only_in_table=tuple(sorted(table_ids - data_ids)),
            only_in_data=tuple(sorted(data_ids - table_ids)),
            duplicated=duplicated,
            conflicting=tuple(sorted(conflicting_set)),
        )
    return TextMetadata(clean, tuple(fields), source_name, label, report)


def texts_matching(
    metadata: TextMetadata | None,
    selections: dict[str, Sequence] | None = None,
    ranges: dict[str, tuple[float, float]] | None = None,
) -> set | None:
    """Text ids satisfying every metadata constraint, or ``None`` for "any".

    Flat-grain sibling of :func:`participants_matching` — an empty constraint
    must not narrow the pool to the texts *listed in the table*, and a numeric
    range keeps a text with no value (``data.filter_trials``' rule that a
    range narrows rather than excludes the unmeasured).
    """
    if metadata is None or metadata.frame.empty:
        return None
    active = {
        name: list(values)
        for name, values in (selections or {}).items()
        if values and name in metadata.frame.columns
    }
    active_ranges = {
        name: bounds
        for name, bounds in (ranges or {}).items()
        if bounds and name in metadata.frame.columns
    }
    if not active and not active_ranges:
        return None

    frame = metadata.frame
    mask = pd.Series(True, index=frame.index)
    for name, values in active.items():
        allowed = {str(value) for value in values}
        mask &= frame[name].astype(str).isin(allowed)
    for name, (low, high) in active_ranges.items():
        numeric = pd.to_numeric(frame[name], errors="coerce")
        mask &= numeric.between(low, high) | numeric.isna()
    matching = set(frame.loc[mask, "text_id"])
    if not active:
        # Range-only narrowing keeps the unmeasured, including a text with no
        # row at all (`participants_matching`'s rule, one grain over).
        matching |= set(metadata.report.only_in_data)
    return matching


def project_texts(
    metadata: TextMetadata | None,
    frame: pd.DataFrame,
    columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Left-join chosen text-metadata columns onto a **small** text-keyed frame.

    For ``combos`` — never for words or fixations, the rule every grain here
    follows. Columns already present on ``frame`` win, so a recorded column is
    never shadowed by a metadata field of the same name.
    """
    if (
        metadata is None
        or metadata.frame.empty
        or frame is None
        or frame.empty
        or "text_id" not in frame.columns
    ):
        return frame
    wanted = [
        name
        for name in (list(columns) if columns is not None else list(metadata.names))
        if name in metadata.frame.columns and name not in frame.columns
    ]
    if not wanted:
        return frame
    out = frame.copy()
    keys = out["text_id"].astype(str)
    for name in wanted:
        out[name] = keys.map(metadata.series(name))
    return out


def text_options_for(metadata: TextMetadata | None, name: str) -> list[str]:
    """Sorted distinct values of a categorical text field, for a multiselect."""
    if metadata is None or metadata.frame.empty or name not in metadata.frame.columns:
        return []
    return sorted({str(value) for value in metadata.joined_frame[name].dropna()})


def text_bounds_for(
    metadata: TextMetadata | None, name: str
) -> tuple[float, float] | None:
    """``(min, max)`` of a numeric text field, or ``None`` when it has no range."""
    if metadata is None or metadata.frame.empty or name not in metadata.frame.columns:
        return None
    numeric = pd.to_numeric(metadata.joined_frame[name], errors="coerce").dropna()
    if numeric.empty:
        return None
    low, high = float(numeric.min()), float(numeric.max())
    if low == high:
        return None
    return low, high


def text_to_payload(metadata: TextMetadata | None) -> dict | None:
    """Serialize the text table for save & restore."""
    if metadata is None or metadata.frame.empty:
        return None
    return {
        "source_name": metadata.source_name,
        "text_column": metadata.text_column,
        "rows": metadata.frame.to_dict("records"),
    }


def text_from_payload(payload: dict | None) -> TextMetadata | None:
    """Rebuild a text table from :func:`text_to_payload`'s output."""
    if not isinstance(payload, dict) or not payload.get("rows"):
        return None
    frame = pd.DataFrame(payload["rows"])
    text_column = str(payload.get("text_column") or "text_id")
    if "text_id" in frame.columns:
        # The payload holds the *clean* frame, whose key column is already
        # canonical — rebuild against that rather than the original name.
        return build_text_metadata(
            frame,
            "text_id",
            source_name=str(payload.get("source_name") or "text metadata"),
        )
    return build_text_metadata(
        frame,
        text_column,
        source_name=str(payload.get("source_name") or "text metadata"),
    )


def active() -> ParticipantMetadata | None:
    """The participant table attached to this session, or ``None``.

    Lives here rather than in the UI layer so the pure consumers
    (:func:`project`, the filter resolution in ``controls``) can reach it
    without importing Streamlit page code. Returns ``None`` outside a script
    run, which is what the headless API and CLI see.
    """
    try:
        import streamlit as st

        return st.session_state.get(SESSION_KEY)
    except Exception:  # no script run context (API, CLI, plain import)
        return None


def participant_ids(*frames: pd.DataFrame | None) -> list[str]:
    """Every distinct reader id across the given frames, as sorted strings."""
    found: set = set()
    for frame in frames:
        if frame is None or frame.empty or "participant_id" not in frame.columns:
            continue
        found |= {str(value) for value in frame["participant_id"].dropna().unique()}
    return sorted(found)


def infer_participant_id_column(frame: pd.DataFrame) -> str | None:
    """Best guess at the reader-id column, or ``None`` when nothing fits."""
    if frame is None or frame.empty:
        return None
    lowered = {str(column).lower(): str(column) for column in frame.columns}
    for candidate in PARTICIPANT_ID_CANDIDATES:
        if candidate in frame.columns:
            return candidate
        hit = lowered.get(candidate.lower())
        if hit is not None:
            return hit
    return None


def _classify(series: pd.Series) -> str:
    """Dtype bucket driving which control a field gets (range vs membership)."""
    cleaned = series.dropna()
    if cleaned.empty:
        return _DTYPE_CATEGORICAL
    if pd.api.types.is_bool_dtype(cleaned):
        return _DTYPE_BOOLEAN
    if pd.api.types.is_numeric_dtype(cleaned):
        return _DTYPE_NUMERIC
    # A column of numeric strings ("23", "4.5") is numeric in every way the user
    # cares about; anything else stays categorical rather than being coerced.
    numeric = pd.to_numeric(cleaned, errors="coerce")
    if numeric.notna().all():
        return _DTYPE_NUMERIC
    return _DTYPE_CATEGORICAL


def _coerce(series: pd.Series, dtype: str) -> pd.Series:
    if dtype == _DTYPE_NUMERIC:
        return pd.to_numeric(series, errors="coerce")
    if dtype == _DTYPE_BOOLEAN:
        return series
    return series.astype("object").where(series.notna(), np.nan)


def field_label(name: str) -> str:
    """Human-readable label for a raw column name (``native_language`` → …).

    Public because it is the *only* labeller for a metadata field: the picker in
    ``tabs._pretty_col`` has to name a field the same way whether or not it can
    reach the attached table at that moment.
    """
    text = str(name).replace("_", " ").replace("-", " ").strip()
    return text[:1].upper() + text[1:] if text else str(name)


def build_participant_metadata(
    frame: pd.DataFrame,
    id_column: str,
    *,
    source_name: str = "participant metadata",
    participants: Iterable | None = None,
) -> ParticipantMetadata:
    """Validate a raw participant table into a registry + clean frame.

    ``participants`` is the set of reader ids actually present in the loaded
    data; passing it fills in the two "unmatched" halves of the report. Rows
    whose id repeats are only a problem when they *disagree* — a duplicated row
    that says the same thing collapses silently, a duplicated row that says
    something different is dropped and reported.
    """
    if frame is None or frame.empty or id_column not in frame.columns:
        return ParticipantMetadata(
            pd.DataFrame(columns=["participant_id"]), (), source_name, str(id_column)
        )

    work = _rows_with_ids(frame, [id_column])
    # See the matching comment in `build_trial_metadata` — the same "one blank
    # cell spells the id two ways" hazard applies to a reader id.
    work["participant_id"] = stable_id(work[id_column])
    if participants is not None:
        work["participant_id"] = _match_padding(work["participant_id"], participants)
    value_columns = [
        str(column)
        for column in frame.columns
        if str(column) not in {str(id_column), "participant_id", *_BOOKKEEPING_COLUMNS}
    ]

    duplicated = tuple(
        sorted(set(work.loc[work["participant_id"].duplicated(), "participant_id"]))
    )
    conflicting: list[str] = []
    if duplicated:
        for pid, group in work[work["participant_id"].isin(duplicated)].groupby(
            "participant_id", sort=True
        ):
            for column in value_columns:
                if group[column].dropna().nunique() > 1:
                    conflicting.append(str(pid))
                    break
    conflicting_set = set(conflicting)
    work = work[~work["participant_id"].isin(conflicting_set)]
    work = work.drop_duplicates(subset=["participant_id"], keep="first")

    fields: list[MetadataField] = []
    clean = pd.DataFrame({"participant_id": work["participant_id"].to_numpy()})
    for column in value_columns:
        dtype = _classify(work[column])
        values = _coerce(work[column], dtype)
        clean[column] = values.to_numpy()
        fields.append(
            MetadataField(
                name=column,
                label=field_label(column),
                grain=GRAIN_PARTICIPANT,
                dtype=dtype,
                source=source_name,
                n_unique=int(values.dropna().nunique()),
                n_missing=int(values.isna().sum()),
            )
        )

    table_ids = set(clean["participant_id"]) | conflicting_set
    if participants is None:
        report = JoinReport(
            matched=tuple(sorted(clean["participant_id"])),
            duplicated=duplicated,
            conflicting=tuple(sorted(conflicting_set)),
        )
    else:
        data_ids = {str(pid) for pid in participants}
        report = JoinReport(
            matched=tuple(sorted(set(clean["participant_id"]) & data_ids)),
            only_in_table=tuple(sorted(table_ids - data_ids)),
            only_in_data=tuple(sorted(data_ids - table_ids)),
            duplicated=duplicated,
            conflicting=tuple(sorted(conflicting_set)),
        )
    return ParticipantMetadata(
        clean, tuple(fields), source_name, str(id_column), report
    )


def _match_padding(ids: pd.Series, participants: Iterable) -> pd.Series:
    """``ids`` spelled the data's way when only zero-padding differs (BUG-59).

    A metadata CSV reads a reader ``007`` as the number 7 while the data kept
    "007", and the table then joined to no one; ``data.zero_padding_map``
    decides, and refuses whenever the match is not unambiguous.
    """
    mapping = zero_padding_map(ids.unique(), {str(pid) for pid in participants})
    return ids.replace(mapping) if mapping else ids


def rejoin(
    metadata: ParticipantMetadata, participants: Iterable
) -> ParticipantMetadata:
    """Recompute the join report against a (possibly new) participant list."""
    data_ids = {str(pid) for pid in participants}
    if not metadata.frame.empty:
        renamed = _match_padding(metadata.frame["participant_id"], data_ids)
        if not renamed.equals(metadata.frame["participant_id"]):
            metadata = replace(
                metadata, frame=metadata.frame.assign(participant_id=renamed)
            )
    usable_ids = (
        set(metadata.frame["participant_id"]) if not metadata.frame.empty else set()
    )
    # Conflicting ids are *in the table* — so they are not "only in the data" —
    # but they carry no values, so they are not joined either. Counting them as
    # matched (as an earlier version did) made "Joined to N readers" grow by the
    # conflict count on the first rerun after the file was attached, disagreeing
    # with what `build_participant_metadata` had just reported.
    table_ids = usable_ids | set(metadata.report.conflicting)
    return ParticipantMetadata(
        metadata.frame,
        metadata.fields,
        metadata.source_name,
        metadata.id_column,
        JoinReport(
            matched=tuple(sorted(usable_ids & data_ids)),
            only_in_table=tuple(sorted(table_ids - data_ids)),
            only_in_data=tuple(sorted(data_ids - table_ids)),
            duplicated=metadata.report.duplicated,
            conflicting=metadata.report.conflicting,
        ),
    )


def participants_matching(
    metadata: ParticipantMetadata | None,
    selections: dict[str, Sequence] | None = None,
    ranges: dict[str, tuple[float, float]] | None = None,
) -> set | None:
    """Reader ids satisfying every metadata constraint, or ``None`` for "any".

    Returning ``None`` rather than "all ids" is deliberate: an empty constraint
    must not narrow the pool to the readers *listed in the table*, which would
    quietly drop everyone the table forgot.

    Membership follows the categorical filters; a numeric range keeps readers
    with **no value**, matching ``data.filter_trials``' rule that a range is a
    narrowing control and not an exclusion of the unmeasured.
    """
    if metadata is None or metadata.frame.empty:
        return None
    active = {
        name: list(values)
        for name, values in (selections or {}).items()
        if values and name in metadata.frame.columns
    }
    active_ranges = {
        name: bounds
        for name, bounds in (ranges or {}).items()
        if bounds and name in metadata.frame.columns
    }
    if not active and not active_ranges:
        return None

    frame = metadata.frame
    mask = pd.Series(True, index=frame.index)
    for name, values in active.items():
        allowed = {str(value) for value in values}
        mask &= frame[name].astype(str).isin(allowed)
    for name, (low, high) in active_ranges.items():
        numeric = pd.to_numeric(frame[name], errors="coerce")
        mask &= numeric.between(low, high) | numeric.isna()
    matching = set(frame.loc[mask, "participant_id"])
    if not active:
        # Range-only narrowing keeps the unmeasured (`data.filter_trials`' rule,
        # UX-49) — and a reader with **no row at all** is the most unmeasured
        # there is, so they are kept on the same terms as a reader whose value
        # is NaN. A *categorical* selection still excludes them, matching every
        # other membership filter in the app: "only Hebrew speakers" cannot
        # include a reader whose language is unknown.
        matching |= set(metadata.report.only_in_data)
    return matching


def project(
    metadata: ParticipantMetadata | None,
    frame: pd.DataFrame,
    columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Left-join chosen metadata columns onto a **small** participant-keyed frame.

    For ``combos`` (one row per trial) and group-by results — never for words or
    fixations. Columns already present on ``frame`` win, so a real recorded
    column is never shadowed by a metadata field of the same name.
    """
    if (
        metadata is None
        or metadata.frame.empty
        or frame is None
        or frame.empty
        or "participant_id" not in frame.columns
    ):
        return frame
    wanted = [
        name
        for name in (list(columns) if columns is not None else list(metadata.names))
        if name in metadata.frame.columns and name not in frame.columns
    ]
    if not wanted:
        return frame
    out = frame.copy()
    keys = out["participant_id"].astype(str)
    for name in wanted:
        out[name] = keys.map(metadata.series(name))
    return out


def options_for(metadata: ParticipantMetadata | None, name: str) -> list[str]:
    """Sorted distinct values of a categorical field, for a multiselect.

    Built from :attr:`ParticipantMetadata.joined_frame` — the loaded readers
    only — so the control cannot offer a value that matches nobody.
    """
    if metadata is None or metadata.frame.empty or name not in metadata.frame.columns:
        return []
    values = metadata.joined_frame[name].dropna()
    return sorted({str(value) for value in values})


def bounds_for(
    metadata: ParticipantMetadata | None, name: str
) -> tuple[float, float] | None:
    """``(min, max)`` of a numeric field, or ``None`` when it has no range."""
    if metadata is None or metadata.frame.empty or name not in metadata.frame.columns:
        return None
    numeric = pd.to_numeric(metadata.joined_frame[name], errors="coerce").dropna()
    if numeric.empty:
        return None
    low, high = float(numeric.min()), float(numeric.max())
    if low == high:
        return None
    return low, high


# -----------------------------------------------------------------------------
# Serialization — 💾 Save & restore (the JSON config), the ENG-26 on-device
# recovery cache (DATA-38, see `session_payloads` below), and the payload
# `api`/`cli` hand in. Records rather than a pickled frame, so it round-trips
# through JSON like every other saved setting.
# -----------------------------------------------------------------------------


def to_payload(metadata: ParticipantMetadata | None) -> dict | None:
    if metadata is None or metadata.frame.empty:
        return None
    return {
        "grain": GRAIN_PARTICIPANT,
        "id_column": metadata.id_column,
        "source_name": metadata.source_name,
        "records": metadata.frame.to_dict(orient="records"),
    }


def from_payload(payload: dict | None) -> ParticipantMetadata | None:
    if not payload or not payload.get("records"):
        return None
    frame = pd.DataFrame(payload["records"])
    if "participant_id" not in frame.columns:
        return None
    return build_participant_metadata(
        frame,
        "participant_id",
        source_name=str(payload.get("source_name") or "participant metadata"),
    )


# -----------------------------------------------------------------------------
# DATA-38 — attached tables in the ENG-26 on-device recovery cache, and DATA-47 —
# the tables belong to a dataset.
#
# The session keys above hold the tables of the *selected* dataset only — the
# one every consumer (filters, chips, sort, inspection, export) reads through
# `active()` / `active_trials()` / `active_texts()`. Every other dataset's
# tables wait in a per-dataset store, and `activate_dataset` swaps them in and
# out when the selection changes. They used to be one slot per grain for the
# whole session, so a new dataset opened with the last one's tables, attaching a
# table to dataset B replaced dataset A's, and detaching it anywhere removed it
# everywhere. The cache writes the store, keyed by dataset.
# -----------------------------------------------------------------------------

#: What a grain's ``*_FILE_SESSION_KEY`` holds when its table came back from the
#: recovery cache or a saved config, rather than from a file in the uploader.
#: The metadata sections read an empty uploader as "the user just removed the
#: file" and detach on sight (UX-115) — and a restored table has no file in the
#: uploader, so without this marker the first visit to the 🗂️ Data page would
#: detach exactly what the restore brought back.
RESTORED_FILE_SIGNATURE = "restored"

#: ``(grain, table key, raw key, file key, to_payload, from_payload)`` per grain.
_GRAINS = (
    (
        GRAIN_PARTICIPANT,
        SESSION_KEY,
        RAW_SESSION_KEY,
        FILE_SESSION_KEY,
        to_payload,
        from_payload,
    ),
    (
        "trial",
        TRIAL_SESSION_KEY,
        TRIAL_RAW_SESSION_KEY,
        TRIAL_FILE_SESSION_KEY,
        trial_to_payload,
        trial_from_payload,
    ),
    (
        "text",
        TEXT_SESSION_KEY,
        TEXT_RAW_SESSION_KEY,
        TEXT_FILE_SESSION_KEY,
        text_to_payload,
        text_from_payload,
    ),
)
_GRAIN_KEYS = {grain: (key, raw, file) for grain, key, raw, file, *_ in _GRAINS}


#: The payloads' row lists — `to_payload` says ``records``, the other two ``rows``.
_ROW_KEYS = ("records", "rows")


def session_payloads(session) -> dict[str, dict]:
    """Every attached table as its save & restore payload, keyed by grain.

    Each carries its frame's ``columns`` too: the cache writes its manifest with
    sorted keys, which would otherwise hand the rows back alphabetised and
    reorder the table's fields everywhere they are listed.
    """
    payloads = {}
    for grain, key, _raw, _file, dump, _load in _GRAINS:
        attached = session.get(key)
        payload = dump(attached)
        if payload is not None:
            payloads[grain] = {**payload, "columns": list(attached.frame.columns)}
    return payloads


def _in_column_order(payload):
    """``payload`` with each row's keys back in its ``columns`` order."""
    columns = payload.get("columns") if isinstance(payload, dict) else None
    if not columns:
        return payload
    ordered = dict(payload)
    for rows_key in _ROW_KEYS:
        rows = payload.get(rows_key)
        if isinstance(rows, list):
            ordered[rows_key] = [
                {column: row[column] for column in columns if column in row}
                for row in rows
                if isinstance(row, dict)
            ]
    return ordered


def session_signature(session) -> list:
    """A cheap content fingerprint of the attached tables.

    For the recovery cache's every-rerun "did anything change" check. Object
    identity will not do: the tables are rebuilt on every render of the Data
    page, and the participant one is re-joined on every run, so a new object
    arrives when nothing changed. The frames are small (one row per reader,
    trial or text), so hashing their content is cheap.
    """
    signature = []
    for grain, key, *_ in _GRAINS:
        attached = session.get(key)
        frame = getattr(attached, "frame", None)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        try:
            # Row hashes in row order — a sum would miss a reordered table.
            cells = pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes()
        except (TypeError, ValueError):  # unhashable cells — hash their text
            cells = frame.to_csv(index=False).encode("utf-8")
        digest = hashlib.sha256(cells).hexdigest()
        signature.append(
            [
                grain,
                str(getattr(attached, "source_name", "")),
                list(frame.columns),
                digest,
            ]
        )
    return signature


def grain_keys(grain: str) -> tuple[str, str, str]:
    """``(table key, raw key, file key)`` in session state for ``grain``."""
    return _GRAIN_KEYS[grain]


def mark_restored(session, grain: str, attached) -> None:
    """Attach ``attached`` as a table with no live upload behind it.

    Shared by the recovery cache and 💾 Save & restore, which both hand back a
    table the uploader never saw — see :data:`RESTORED_FILE_SIGNATURE`.
    """
    key, raw, file = _GRAIN_KEYS[grain]
    session[key] = attached
    session[raw] = attached.frame
    session[file] = RESTORED_FILE_SIGNATURE


def is_restored(session, grain: str) -> bool:
    """Whether ``grain``'s attached table came back without a file behind it."""
    return session.get(_GRAIN_KEYS[grain][2]) == RESTORED_FILE_SIGNATURE


def restore_payloads(session, payloads) -> int:
    """Re-attach the tables :func:`session_payloads` wrote; how many landed.

    A grain already attached in this session keeps its own table — the same
    "never overwrite what is already seeded" rule the rest of the restore
    follows — and a payload that no longer builds is skipped, not raised: a
    stale cache must never stop the app opening.
    """
    if not isinstance(payloads, dict):
        return 0
    restored = 0
    for grain, key, _raw, _file, _dump, load in _GRAINS:
        if session.get(key) is not None:
            continue
        try:
            attached = load(_in_column_order(payloads.get(grain)))
        except (ValueError, TypeError, KeyError):
            attached = None
        if attached is None:
            continue
        mark_restored(session, grain, attached)
        restored += 1
    return restored


#: DATA-47 — every dataset's tables but the selected one's, as the payloads
#: :func:`session_payloads` builds: ``{dataset: {grain: payload}}``. Payloads
#: rather than table objects so the cache can write them as they are.
DATASET_STORE_KEY = "_metadata_by_dataset"
#: Which dataset the session keys' tables belong to right now.
OWNER_KEY = "_metadata_owner"
#: Bumped on every change to the store — the cache's cheap "did it change" test,
#: since hashing every stored table on every rerun would not be cheap.
STORE_REVISION_KEY = "_metadata_store_revision"
#: The add-dataset wizard's dataset, before it has a name. Never cached.
PENDING_DATASET = "\x00pending"


def _widget_keys(grain: str) -> tuple[str, ...]:
    """The UI state of ``grain``'s section that describes one dataset's table.

    The uploader above all: a swap that left it holding the last dataset's file
    would read that file as a new upload and attach it to the dataset just
    opened. The display name, the id-column and keep-fields picks go with it,
    so the next dataset's table starts from its own auto-detect.
    """
    return (
        f"_{grain}_metadata_name",
        f"{grain}_metadata_upload",
        f"{grain}_metadata_id_column",
        f"{grain}_metadata_keep_fields",
    )


def clear_active(session) -> None:
    """Detach the selected dataset's tables from the session keys — all grains."""
    for grain, key, raw, file, *_ in _GRAINS:
        for name in (key, raw, file, *_widget_keys(grain)):
            session.pop(name, None)


def _store(session) -> dict:
    store = session.get(DATASET_STORE_KEY)
    return dict(store) if isinstance(store, dict) else {}


def _set_store(session, store: dict) -> None:
    session[DATASET_STORE_KEY] = store
    session[STORE_REVISION_KEY] = int(session.get(STORE_REVISION_KEY) or 0) + 1


def stash_active(session) -> None:
    """File the session keys' tables under the dataset they belong to."""
    owner = session.get(OWNER_KEY)
    if owner is None:
        return
    store = _store(session)
    payloads = session_payloads(session)
    if payloads:
        if store.get(owner) == payloads:
            return  # unchanged since it was restored — nothing for the cache to do
        store[owner] = payloads
    elif owner not in store:
        return
    else:
        store.pop(owner)
    _set_store(session, store)


def activate_dataset(session, dataset: str) -> bool:
    """Make ``dataset``'s tables the attached ones; whether anything moved.

    Called by ``app.main`` on every run with the selected dataset. When the
    selection changed, the outgoing dataset's tables are filed away, the session
    keys are cleared — widgets included, see :func:`_widget_keys` — and the
    incoming dataset's are restored (marked restored, since no uploader holds
    their file). A session whose tables have no owner yet (its first run) adopts
    whatever is attached for ``dataset`` rather than clearing it.
    """
    dataset = str(dataset)
    owner = session.get(OWNER_KEY)
    if owner == dataset:
        return False
    if owner is not None:
        stash_active(session)
        clear_active(session)
    session[OWNER_KEY] = dataset
    restore_payloads(session, _store(session).get(dataset))
    return True


#: CMP-8's key prefix for scanpath B's filters, and the picker's "same dataset"
#: answer (``compare_source.THIS_DATASET`` — not imported: `compare_source`
#: imports `app`, which imports this).
_COMPARE_PREFIX = "cmp"
_COMPARE_SAME_DATASET = "This dataset"
_BUILT_KEY = "_metadata_built_for_compare"


def attached_for(grain: str, prefix: str = ""):
    """The table ``grain``'s filters under key ``prefix`` narrow by (DATA-47).

    The main pool's filters read the selected dataset's table. Compare mode's
    scanpath B (the ``cmp`` prefix) can come from another dataset, and then its
    filters must read *that* dataset's own table — which waits in the store —
    not A's. Built from the stored payload once per store revision.
    """
    try:
        import streamlit as st

        session = st.session_state
        live = session.get(_GRAIN_KEYS[grain][0])
    except Exception:  # no script run context (API, CLI, plain import)
        return None
    if prefix != _COMPARE_PREFIX:
        return live
    other = session.get(COMPARE_SOURCE_STATE_KEY)
    if (
        not other
        or other == _COMPARE_SAME_DATASET
        or str(other) == session.get(OWNER_KEY)
    ):
        return live
    payload = (_store(session).get(str(other)) or {}).get(grain)
    if not isinstance(payload, dict):
        return None
    revision = session.get(STORE_REVISION_KEY)
    built = session.get(_BUILT_KEY)
    cache_key = (str(other), grain, revision)
    if not isinstance(built, dict) or cache_key not in built:
        load = next(entry[-1] for entry in _GRAINS if entry[0] == grain)
        try:
            table = load(_in_column_order(payload))
        except (ValueError, TypeError, KeyError):
            table = None
        kept = {
            k: v
            for k, v in (built or {}).items()
            if isinstance(k, tuple) and k[-1] == revision
        }
        session[_BUILT_KEY] = built = {**kept, cache_key: table}
    return built[cache_key]


def begin_pending_dataset(session) -> None:
    """Start the add-dataset wizard's dataset with no tables of its own."""
    store = _store(session)
    if PENDING_DATASET in store:
        store.pop(PENDING_DATASET)
        _set_store(session, store)


def adopt_pending_dataset(session, dataset: str) -> None:
    """✅ Add dataset: the wizard's tables become ``dataset``'s.

    The session keys already hold them (the deferred join has just attached
    them), so this only renames who owns them — the next run's
    :func:`activate_dataset` then sees nothing to swap.
    """
    begin_pending_dataset(session)
    session[OWNER_KEY] = str(dataset)


def forget_dataset(session, dataset: str) -> None:
    """A removed dataset's tables go with it."""
    dataset = str(dataset)
    store = _store(session)
    if dataset in store:
        store.pop(dataset)
        _set_store(session, store)
    if session.get(OWNER_KEY) == dataset:
        clear_active(session)
        session.pop(OWNER_KEY, None)


def rename_dataset(session, old: str, new: str) -> None:
    """A renamed dataset keeps its tables."""
    old, new = str(old), str(new)
    store = _store(session)
    if old in store:
        _set_store(session, {(new if k == old else k): v for k, v in store.items()})
    if session.get(OWNER_KEY) == old:
        session[OWNER_KEY] = new


def dataset_payloads(session) -> dict[str, dict]:
    """Every dataset's tables, the selected one's live: ``{dataset: {grain: …}}``.

    What the recovery cache writes. The add-dataset wizard's unnamed dataset is
    left out — it is not a dataset yet, and a restart discards the wizard.
    """
    store = _store(session)
    owner = session.get(OWNER_KEY)
    if owner is not None:
        live = session_payloads(session)
        if live:
            store[owner] = live
        else:
            store.pop(owner, None)
    store.pop(PENDING_DATASET, None)
    return {name: payloads for name, payloads in store.items() if payloads}


def store_signature(session) -> list:
    """A cheap fingerprint of every dataset's tables, for the cache (DATA-47).

    The live tables by content (:func:`session_signature` — they are rebuilt on
    every render), the rest by the store's revision counter. Empty when nothing
    is attached anywhere, which is what tells the cache to delete its file.
    """
    live = session_signature(session)
    # Deliberately not `dataset_payloads`, which serializes the live tables: this
    # runs on every rerun, and the live half is already covered by `live`.
    owner = session.get(OWNER_KEY)
    stored = any(
        tables
        for name, tables in _store(session).items()
        if name not in (owner, PENDING_DATASET)
    )
    if not live and not stored:
        return []
    return [
        ["store", int(session.get(STORE_REVISION_KEY) or 0)],
        ["owner", str(session.get(OWNER_KEY))],
        *live,
    ]


def restore_dataset_payloads(session, payloads) -> int:
    """Put the tables :func:`dataset_payloads` wrote back in the store; how many.

    A dataset this session already holds tables for keeps its own. The selected
    dataset's go straight onto the session keys, grain by grain — one already
    attached is kept, like the rest of the restore's ``setdefault`` — and the
    others wait in the store for :func:`activate_dataset`.
    """
    datasets = payloads.get("datasets") if isinstance(payloads, dict) else None
    if not isinstance(datasets, dict):
        return 0
    store = _store(session)
    owner = session.get(OWNER_KEY)
    restored = 0
    changed = False
    for name, tables in datasets.items():
        name = str(name)
        if not isinstance(tables, dict) or name == PENDING_DATASET or name in store:
            continue
        store[name] = tables
        changed = True
        if name == owner:
            restored += restore_payloads(session, tables)
        else:
            restored += sum(
                1 for grain, *_ in _GRAINS if isinstance(tables.get(grain), dict)
            )
    if changed:
        _set_store(session, store)
    return restored
