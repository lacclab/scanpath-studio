"""DATA-66: the dataset's own column names, behind the canonical ones.

Normalization (`data.normalize_*`) rebuilds every table under canonical names —
`duration_ms`, `total_fixation_duration_ms` — and, until this module, kept no
record of what each was called in the user's files. A :class:`ColumnNames` is
that record, one per table of a dataset: for each canonical column, the source
column(s) it was read from and how (`kind`). :func:`from_schema` builds it from
the same schema, registries and raw columns normalization used, so the two
cannot disagree. Pure — no Streamlit, no I/O.

The canonical names stay the internal contract and every wire format's values;
this map is what a person is shown, what an export writes and what the API
accepts (DATA-66 phases 2–4).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

#: How a canonical column came to be.
MAPPED = "mapped"  # read from one source column, unchanged
COMPOSITE = "composite"  # several source columns joined (a composite id)
CONVERTED = "converted"  # read, then changed (a unit, edges → a box width)
GENERATED = "generated"  # the data had none, so the app made a stand-in
COMPUTED = "computed"  # derived by the app (measures, runs, angles …)
YOURS = "yours"  # carried through under its own name
KINDS = (MAPPED, COMPOSITE, CONVERTED, GENERATED, COMPUTED, YOURS)

#: Columns the app derives (measures.py, preprocessing.py, alignment.py,
#: data.normalize_*) when the data did not bring them. A column the dataset
#: *did* bring under one of these names is the user's: its map entry wins.
COMPUTED_COLUMNS: frozenset[str] = frozenset(
    {
        # data.normalize_fixations / harmonize_frames
        "order_in_trial",
        "order_in_screen",
        "right_to_left",
        # measures.compute_per_word_measures
        "first_fixation_ms",
        "first_pass_gaze_duration_ms",
        "regression_path_duration_ms",
        "total_fixation_duration_ms",
        "gaze_duration_ms",
        "n_fixations",
        "skip_flag",
        "regression_in_flag",
        "regression_out_flag",
        "first_fix_x",
        "first_fix_y",
        "initial_landing_position",
        "initial_landing_distance",
        "number_of_regressions_in",
        "second_pass_duration_ms",
        "single_fixation_duration_ms",
        # measures.enrich_fixations / materialize_runs
        "saccade_amplitude",
        "angle_incoming",
        "angle_outgoing",
        "progression",
        "is_regression",
        "run",
        "linerun",
        "word_runid",
        "word_run",
        "word_run_fix",
        "nrun",
        "reread",
        # preprocessing.preprocess_fixations / merge_short_fixations
        "excluded",
        "excluded_reason",
        "blink_before",
        "blink_after",
        "original_duration_ms",
        # alignment.correct
        "y_original",
        "y_correction",
        "alignment_agreement",
    }
)


@dataclass(frozen=True)
class SourceName:
    """What one canonical column was read from: its source column(s) and how."""

    sources: tuple[str, ...]
    kind: str = MAPPED
    note: str = ""

    @property
    def display(self) -> str:
        return " + ".join(self.sources)


@dataclass(frozen=True)
class ColumnNames:
    """One table's canonical column → :class:`SourceName` record."""

    entries: Mapping[str, SourceName] = field(default_factory=dict)

    def source(self, column) -> SourceName | None:
        return self.entries.get(str(column))

    def kind_of(self, column) -> str:
        entry = self.source(column)
        if entry is not None:
            return entry.kind
        return COMPUTED if str(column) in COMPUTED_COLUMNS else YOURS

    def display(self, column) -> str:
        """The name to show for ``column`` — the user's when there is one."""
        entry = self.source(column)
        return entry.display if entry is not None and entry.sources else str(column)

    def to_canonical(self, name) -> str:
        """The canonical column a user's ``name`` stands for (else ``name``)."""
        name = str(name)
        for column, entry in self.entries.items():
            if entry.sources == (name,) and entry.kind in (MAPPED, CONVERTED):
                return column
        return name

    def through(self, earlier: ColumnNames) -> ColumnNames:
        """This map with each source renamed by ``earlier``.

        ✏️ Edit dataset maps fields onto the stored frame's *canonical* columns,
        so a map built from that edit names canonical columns as its sources;
        read through the dataset's earlier map they are the user's names again.
        A source that was generated or converted stays so. Columns this map does
        not rebuild keep their earlier record.
        """
        out: dict[str, SourceName] = {}
        for column, entry in self.entries.items():
            sources: list[str] = []
            kind, note = entry.kind, entry.note
            for source in entry.sources:
                prior = earlier.entries.get(source)
                if prior is None:
                    sources.append(source)
                    continue
                sources.extend(prior.sources)
                if kind == MAPPED and prior.kind != MAPPED:
                    kind, note = prior.kind, prior.note
            out[column] = SourceName(tuple(sources), kind, note)
        for column, entry in earlier.entries.items():
            out.setdefault(column, entry)
        return ColumnNames(out)

    def to_payload(self) -> dict:
        """A JSON-safe form, for a `_datasets` entry and the recovery cache."""
        return {
            column: {"sources": list(e.sources), "kind": e.kind, "note": e.note}
            for column, e in self.entries.items()
        }

    @classmethod
    def from_payload(cls, payload) -> ColumnNames:
        """The inverse of :meth:`to_payload`; anything malformed reads as empty."""
        if not isinstance(payload, Mapping):
            return EMPTY
        entries: dict[str, SourceName] = {}
        for column, raw in payload.items():
            if not isinstance(raw, Mapping):
                return EMPTY
            kind = raw.get("kind", MAPPED)
            sources = raw.get("sources") or ()
            if kind not in KINDS or not isinstance(sources, Iterable):
                return EMPTY
            entries[str(column)] = SourceName(
                tuple(str(s) for s in sources), kind, str(raw.get("note") or "")
            )
        return cls(entries)


EMPTY = ColumnNames({})


#: Mapped screen fields: schema key → canonical column (`data._copy_screen_fields`).
_SCREEN_FIELDS = (
    ("screen_id", "screen_id"),
    ("screen_index", "screen_index"),
    ("screen_timestamp", "screen_timestamp_ms"),
    ("screen_fixation_id", "screen_fixation_id"),
    ("canvas_width", "canvas_width"),
    ("canvas_height", "canvas_height"),
)


def _id_entry(value) -> SourceName | None:
    """A schema id field — one column, or several joined (a composite id)."""
    from .data import trial_mapping_columns

    if not value:
        return None
    columns = [str(c) for c in trial_mapping_columns(value)]
    if len(columns) > 1:
        return SourceName(tuple(columns), COMPOSITE)
    return SourceName((columns[0],), MAPPED)


def _timed(column: str) -> SourceName:
    """A time column, which normalization converts to ms when its unit says so."""
    from .data import time_unit_ms

    if time_unit_ms(column) != 1.0:
        return SourceName((column,), CONVERTED, f"{column}, in ms")
    return SourceName((column,), MAPPED)


def _mapped_or(schema: Mapping, key: str, kind: str, note: str) -> SourceName:
    """The schema's column for ``key``, else a stand-in of ``kind``."""
    column = schema.get(key)
    return SourceName((str(column),)) if column else SourceName((), kind, note)


def _registry(out: dict, registry, present: set, keep: set | None) -> None:
    """The optional-field renames normalization applied (`_apply_optional_fields`).

    A later entry for the same destination overwrites an earlier one there, so
    it does here too; a passthrough (`src == dest`) keeps its own name and needs
    no entry.
    """
    for src, dest, _kind, _category in registry:
        if src not in present or (keep is not None and src not in keep):
            continue
        if dest != src:
            out[dest] = SourceName((src,), MAPPED)


def from_schema(
    table: str,
    schema: Mapping | None,
    columns: Iterable[str],
    *,
    keep_columns: Iterable[str] | None = None,
) -> ColumnNames:
    """The map ``data.normalize_<table>`` implies for ``schema`` over ``columns``.

    ``table`` is ``"words"``, ``"fixations"`` or ``"raw_gaze"``; ``columns`` are
    the raw table's; ``keep_columns`` the set normalization was given (``None``
    carries every registry field, as normalization does).
    """
    from . import data

    schema = dict(schema or {})
    present = {str(c) for c in columns}
    keep = None if keep_columns is None else {str(c) for c in keep_columns}
    out: dict[str, SourceName] = {}

    out["participant_id"] = _id_entry(schema.get("participant")) or SourceName(
        (), GENERATED, "one reader for the whole table"
    )
    if trial := _id_entry(schema.get("trial")):
        out["trial_id"] = out["unique_trial_id"] = trial
    if table != "raw_gaze" and "unique_paragraph_id" in present:
        out["text_id"] = out["unique_text_id"] = SourceName(("unique_paragraph_id",))
    else:
        out["text_id"] = _id_entry(schema.get("text_id")) or SourceName(
            (), GENERATED, "the trial id"
        )
    for key, canonical in _SCREEN_FIELDS:
        if schema.get(key):
            out[canonical] = SourceName((str(schema[key]),))

    if table == "words":
        out["word_id"] = _mapped_or(schema, "word_id", GENERATED, "the row order")
        out["text"] = _mapped_or(schema, "text", GENERATED, "w0, w1 … from the word id")
        out["line_idx"] = _mapped_or(schema, "line", GENERATED, "1 — one line")
        if all(schema.get(k) for k in ("x", "y", "width", "height")):
            for key in ("x", "y", "width", "height"):
                out[key] = SourceName((str(schema[key]),))
        elif all(schema.get(k) for k in ("left", "right", "top", "bottom")):
            left, right = str(schema["left"]), str(schema["right"])
            top, bottom = str(schema["top"]), str(schema["bottom"])
            out["x"], out["y"] = SourceName((left,)), SourceName((top,))
            out["width"] = SourceName((right, left), CONVERTED, f"{right} − {left}")
            out["height"] = SourceName((bottom, top), CONVERTED, f"{bottom} − {top}")
        _registry(out, data.WORD_OPTIONAL_FIELDS, present, keep)
        # AN-32: a measure the schema names decides it, after the passthrough.
        for key, canonical, *_ in data.READING_MEASURE_FIELDS:
            if key not in schema:
                continue
            column = schema.get(key)
            if column and column in present:
                out[canonical] = SourceName((str(column),))
            else:
                out.pop(canonical, None)
    elif table == "fixations":
        for coord in ("x", "y"):
            out[coord] = _mapped_or(
                schema, coord, COMPUTED, "the fixated word's box centre"
            )
        if schema.get("duration"):
            out["duration_ms"] = _timed(str(schema["duration"]))
        out["timestamp_ms"] = (
            _timed(str(schema["timestamp"]))
            if schema.get("timestamp")
            else SourceName((), GENERATED, "the fixation's order in its trial")
        )
        out["fixation_id"] = _mapped_or(
            schema, "fixation_id", GENERATED, "1, 2, … per trial"
        )
        out["word_id"] = _mapped_or(
            schema, "word_id", COMPUTED, "assigned from the word boxes"
        )
        _registry(out, data.FIX_OPTIONAL_FIELDS, present, keep)
    else:  # raw gaze
        for key in ("x", "y", "text", "word_id"):
            if schema.get(key):
                out[key] = SourceName((str(schema[key]),))
        out["timestamp_ms"] = (
            _timed(str(schema["timestamp"]))
            if schema.get("timestamp")
            else SourceName((), GENERATED, "the sample's order in its trial")
        )
    return ColumnNames(out)


def for_tables(
    schemas: Mapping[str, Mapping | None],
    frames: Mapping[str, object],
    keeps: Mapping[str, Iterable[str] | None] | None = None,
) -> dict[str, dict]:
    """``{table: payload}`` for every table with a schema and a raw frame."""
    keeps = keeps or {}
    out: dict[str, dict] = {}
    for table, schema in schemas.items():
        columns = getattr(frames.get(table), "columns", None)
        if not schema or columns is None or len(columns) == 0:
            continue
        out[table] = from_schema(
            table, schema, columns, keep_columns=keeps.get(table)
        ).to_payload()
    return out
