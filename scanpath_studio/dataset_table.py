"""UX-174: the row model behind 📂 Available datasets.

Pure — no Streamlit, no pandas — so what a row *says* can be tested without
booting the app. `app.render_dataset_table` builds one :class:`DatasetRow` per
dataset and draws it; everything that decides a cell's text lives here:

- **Counts or a reason.** A count is shown as a grouped integer (``2,400,788``)
  and only when something was actually counted or published. A missing count is
  never a ``0``, a ``None`` or a ``NaN`` on screen: it names why it is missing
  (:data:`NOT_LOADED`, :data:`NOT_REPORTED`, :data:`NOT_APPLICABLE`), or says
  :data:`UNKNOWN` when the evidence does not say which.
- **Sorting on the numbers, not the text.** :func:`sort_rows` orders by the
  integer value, and a missing value sorts last in either direction, so
  formatting a cell can never turn a numeric sort into a lexical one.
- **Provenance beside the name.** Whether a row's numbers were *loaded* (counted
  from rows this session held) or *published* (the corpus' own figures) is the
  row's :attr:`DatasetRow.provenance` — DATA-36's distinction, unchanged — kept
  apart from any operational state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

#: The dataset table's count fields, in display order — and the only field names
#: a catalogue entry may publish figures under (DATA-36). A typo would otherwise
#: be dropped in silence; `tests/test_dataset_published_counts.py` checks every
#: declaration against this tuple.
DATASET_COUNT_FIELDS: tuple[str, ...] = (
    "Participants",
    "Texts",
    "Trials",
    "Screens",
    "Words",
    "Fixations",
    "Gaze points",
)

#: The four counts the table shows by default. The other three — Screens, Words
#: and Gaze points — are in **Details** and in the table's *All counts* view.
DEFAULT_COUNT_FIELDS: tuple[str, ...] = ("Participants", "Texts", "Trials", "Fixations")

#: The one count kept on a phone-width screen, beside the name and the actions.
KEY_COUNT_FIELD = "Participants"

NOT_LOADED = "Not loaded"
NOT_REPORTED = "Not reported"
NOT_APPLICABLE = "Not applicable"
UNKNOWN = "Unknown"

#: Each missing-value label's meaning, for its hover text and for **Details**.
GAP_EXPLANATIONS: Mapping[str, str] = {
    NOT_LOADED: "Not counted yet — this dataset has not been opened in this "
    "session, and it publishes no figures of its own.",
    NOT_REPORTED: "The corpus' published figures do not include this one. Open "
    "the dataset to count it.",
    NOT_APPLICABLE: "This dataset has nothing of this kind to count.",
    UNKNOWN: "Not available — the data loaded, but this count could not be "
    "determined from it.",
}

#: Why a loaded dataset can hold no value for a field: the table the count is
#: taken from is absent, which is a property of the dataset, not a gap in the
#: counting. Every other field left blank by a load is :data:`UNKNOWN`.
_NOT_APPLICABLE_WHEN_LOADED: Mapping[str, str] = {
    "Screens": "Every trial is a single screen.",
    "Words": "This dataset has no AOI (word) table.",
    "Fixations": "This dataset has no fixation table.",
    "Gaze points": "This dataset has no raw-gaze samples.",
}

#: DATA-36's two sources, as the row's secondary line says them.
PROVENANCE_LABELS: Mapping[str, str] = {
    "loaded": "Loaded counts",
    "published": "Published counts",
}

#: Kind is ordered by what a row is, not alphabetically, when it is sorted.
KIND_ORDER: tuple[str, ...] = ("Demo", "Manual", "Private", "Public")


def format_count(value: int) -> str:
    """A count with thousands separators — ``2400788`` → ``"2,400,788"``."""
    return f"{int(value):,}"


@dataclass(frozen=True)
class DatasetRow:
    """What one dataset's row of the table shows.

    ``source`` is DATA-36's ``"loaded"`` / ``"published"`` / ``""``, and
    ``counts`` holds only that source's numbers (a row never mixes the two).
    ``measured`` says whether the session ever counted this dataset at all,
    which is what tells *Not loaded* from *Unknown* on a row with no numbers.
    ``status`` is an operational state (*Needs setup*), deliberately a field of
    its own: it says what the app can do with the dataset right now, which is a
    different question from where its numbers came from.
    ``order`` is the row's place in the unsorted list, so the list returns to
    it and does not move when the open dataset changes.
    """

    token: str
    name: str
    kind: str = ""
    language: str = ""
    source: str = ""
    counts: Mapping[str, int | None] = field(default_factory=dict)
    exceeds_published: tuple[str, ...] = ()
    active: bool = False
    measured: bool = False
    status: str = ""
    order: int = 0

    def value(self, count_field: str) -> int | None:
        value = self.counts.get(count_field)
        return None if value is None else int(value)

    def gap(self, count_field: str) -> str:
        """Why ``count_field`` has no value — ``""`` when it has one."""
        if self.value(count_field) is not None:
            return ""
        if self.source == "loaded":
            if count_field in _NOT_APPLICABLE_WHEN_LOADED:
                return NOT_APPLICABLE
            return UNKNOWN
        if self.source == "published":
            return NOT_REPORTED
        return UNKNOWN if self.measured else NOT_LOADED

    def gap_explanation(self, count_field: str) -> str:
        """The sentence behind :meth:`gap`, specific to the field where it can be."""
        gap = self.gap(count_field)
        if gap == NOT_APPLICABLE:
            return _NOT_APPLICABLE_WHEN_LOADED[count_field]
        return GAP_EXPLANATIONS.get(gap, "")

    def cell(self, count_field: str) -> str:
        """The cell's text: the grouped count, or the reason there is none."""
        value = self.value(count_field)
        return self.gap(count_field) if value is None else format_count(value)

    @property
    def provenance(self) -> str:
        return PROVENANCE_LABELS.get(self.source, "")

    @property
    def secondary(self) -> str:
        """The line under the name: language and where the counts came from."""
        return " · ".join(part for part in (self.language, self.provenance) if part)


def _text_key(row: DatasetRow, column: str) -> str | int | None:
    if column == "Dataset":
        return row.name.casefold() or None
    if column == "Language":
        return row.language.casefold() or None
    if column == "Kind":
        return KIND_ORDER.index(row.kind) if row.kind in KIND_ORDER else None
    raise ValueError(f"not a sortable column: {column!r}")


def sort_key(row: DatasetRow, column: str):
    """The value ``column`` sorts ``row`` on, or ``None`` for a missing one."""
    if column in DATASET_COUNT_FIELDS:
        return row.value(column)
    return _text_key(row, column)


def default_descending(column: str) -> bool:
    """A count column sorts largest first; a text column A → Z."""
    return column in DATASET_COUNT_FIELDS


def sort_rows(
    rows: Iterable[DatasetRow], column: str | None, *, descending: bool = False
) -> list[DatasetRow]:
    """``rows`` sorted on ``column``'s value, missing values last either way.

    ``column=None`` is the unsorted list — the order the datasets are offered
    in, which nothing in the table (least of all opening a dataset) changes.
    """
    rows = sorted(rows, key=lambda row: row.order)
    if column is None:
        return rows
    present = [row for row in rows if sort_key(row, column) is not None]
    missing = [row for row in rows if sort_key(row, column) is None]
    present.sort(key=lambda row: sort_key(row, column), reverse=descending)
    return present + missing


def next_sort(current: tuple[str, bool] | None, column: str) -> tuple[str, bool] | None:
    """A header click: default direction → reversed → back to unsorted."""
    first = default_descending(column)
    if current is None or current[0] != column:
        return (column, first)
    if current[1] == first:
        return (column, not first)
    return None


def filter_rows(
    rows: Iterable[DatasetRow],
    *,
    query: str = "",
    kinds: Sequence[str] = (),
    languages: Sequence[str] = (),
) -> list[DatasetRow]:
    """The rows matching a name search and the Kind / Language picks.

    An empty pick means "any", so the filters narrow only once something is
    chosen. The search is a case-insensitive substring of the name.
    """
    needle = query.strip().casefold()
    return [
        row
        for row in rows
        if (not needle or needle in row.name.casefold())
        and (not kinds or row.kind in kinds)
        and (not languages or row.language in languages)
    ]


def row_record(row: DatasetRow) -> dict:
    """``row`` as a flat record — the table's inspection seam for tests.

    Keys follow the columns' names; a count is the integer or ``None`` (the
    *value*, never its formatted cell), and ``Counts`` is DATA-36's badge word.
    """
    record = {
        "Kind": row.kind,
        "Dataset": row.name,
        "Language": row.language,
        "Counts": {"loaded": "Loaded", "published": "Published"}.get(row.source, ""),
    }
    for count_field in DATASET_COUNT_FIELDS:
        record[count_field] = row.value(count_field)
    record["Status"] = row.status
    record["_token"] = row.token
    record["_active"] = row.active
    record["_cells"] = {f: row.cell(f) for f in DATASET_COUNT_FIELDS}
    return record
