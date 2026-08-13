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

Later grains (stimulus, trial, screen, word, fixation) add rows to the same
registry; :class:`MetadataField` already carries ``grain`` so the consumers
written here do not have to change shape when they arrive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Source columns that plausibly hold the reader id, most explicit first. Shares
# the spirit of `data.pick_column`'s candidate lists: first hit wins, and the
# user can always override the guess in the UI.
PARTICIPANT_ID_CANDIDATES: Tuple[str, ...] = (
    "participant_id",
    "participant",
    "subject_id",
    "subject",
    "reader_id",
    "reader",
    "pid",
    "RECORDING_SESSION_LABEL",
)

# Grain of a field — the entity one row describes. Only PARTICIPANT is ingested
# in milestone 1; the rest are named so the registry's shape is settled.
GRAIN_PARTICIPANT = "participant"

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

    matched: Tuple[str, ...] = ()
    only_in_table: Tuple[str, ...] = ()
    only_in_data: Tuple[str, ...] = ()
    duplicated: Tuple[str, ...] = ()
    conflicting: Tuple[str, ...] = ()

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
    fields: Tuple[MetadataField, ...]
    source_name: str
    id_column: str
    report: JoinReport = JoinReport()

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    def field(self, name: str) -> Optional[MetadataField]:
        for candidate in self.fields:
            if candidate.name == name:
                return candidate
        return None

    def values_for(self, participant_id) -> Dict[str, object]:
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


def active() -> Optional["ParticipantMetadata"]:
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


def participant_ids(*frames: Optional[pd.DataFrame]) -> List[str]:
    """Every distinct reader id across the given frames, as sorted strings."""
    found: set = set()
    for frame in frames:
        if frame is None or frame.empty or "participant_id" not in frame.columns:
            continue
        found |= {str(value) for value in frame["participant_id"].dropna().unique()}
    return sorted(found)


def infer_participant_id_column(frame: pd.DataFrame) -> Optional[str]:
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
    participants: Optional[Iterable] = None,
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

    work = frame.copy()
    work["participant_id"] = work[id_column].astype(str).str.strip()
    work = work[work["participant_id"] != ""]
    value_columns = [
        str(column)
        for column in frame.columns
        if str(column) not in {str(id_column), "participant_id", *_BOOKKEEPING_COLUMNS}
    ]

    duplicated = tuple(
        sorted(set(work.loc[work["participant_id"].duplicated(), "participant_id"]))
    )
    conflicting: List[str] = []
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

    fields: List[MetadataField] = []
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


def rejoin(
    metadata: ParticipantMetadata, participants: Iterable
) -> ParticipantMetadata:
    """Recompute the join report against a (possibly new) participant list."""
    data_ids = {str(pid) for pid in participants}
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
    metadata: Optional[ParticipantMetadata],
    selections: Optional[Dict[str, Sequence]] = None,
    ranges: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Optional[set]:
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
    metadata: Optional[ParticipantMetadata],
    frame: pd.DataFrame,
    columns: Optional[Iterable[str]] = None,
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


def options_for(metadata: Optional[ParticipantMetadata], name: str) -> List[str]:
    """Sorted distinct values of a categorical field, for a multiselect.

    Built from :attr:`ParticipantMetadata.joined_frame` — the loaded readers
    only — so the control cannot offer a value that matches nobody.
    """
    if metadata is None or metadata.frame.empty or name not in metadata.frame.columns:
        return []
    values = metadata.joined_frame[name].dropna()
    return sorted({str(value) for value in values})


def bounds_for(
    metadata: Optional[ParticipantMetadata], name: str
) -> Optional[Tuple[float, float]]:
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
# Serialization — 💾 Save & restore (the JSON config) and the payload
# NOT the ENG-26 on-device recovery cache: that stores uploaded *datasets*, and
# wiring the participant table into it is a separate piece of work. An attached
# table therefore survives a save/restore round trip but not a recovery-cache
# restore. Also the payload
# `api`/`cli` hand in. Records rather than a pickled frame, so it round-trips
# through JSON like every other saved setting.
# -----------------------------------------------------------------------------


def to_payload(metadata: Optional[ParticipantMetadata]) -> Optional[dict]:
    if metadata is None or metadata.frame.empty:
        return None
    return {
        "grain": GRAIN_PARTICIPANT,
        "id_column": metadata.id_column,
        "source_name": metadata.source_name,
        "records": metadata.frame.to_dict(orient="records"),
    }


def from_payload(payload: Optional[dict]) -> Optional[ParticipantMetadata]:
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
