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

import json
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

#: What marks a column the app made, wherever a column is named on screen.
#: Text, not an icon: option labels cannot carry a Material icon, and literal
#: emoji are kept out of chrome (`tests/test_icons.py`).
COMPUTED_SUFFIX = " (computed)"

#: Where the open dataset's map lives in session state (stashed by
#: `app._stash_active_mapping`), one payload per table.
ACTIVE_COLUMN_NAMES_KEY = "_active_column_names"

#: Curated labels for columns the app makes. A reading measure's comes from
#: `data.READING_MEASURE_FIELDS` (its full name) — see `canonical_label`.
_CANONICAL_LABELS: dict[str, str] = {
    "order_in_trial": "Fixation order",
    "order_in_screen": "Fixation order on screen",
    "fixation_id": "Fixation #",
    "timestamp_ms": "Time (ms)",
    "participant_id": "Participant",
    "text_id": "Text",
    "line_idx": "Line",
    "text": "Word",
    "word_id": "Word #",
    "x": "X",
    "y": "Y",
    "saccade_amplitude": "Saccade amplitude (px)",
    "angle_incoming": "Incoming angle",
    "angle_outgoing": "Outgoing angle",
    "progression": "Progression",
    "is_regression": "Regression",
    "right_to_left": "Right to left",
    "first_fix_x": "First fixation X",
    "first_fix_y": "First fixation Y",
    "gaze_duration_ms": "Gaze duration (ms)",
    "run": "Run",
    "linerun": "Line run",
    "word_runid": "Word run id",
    "word_run": "Word run",
    "word_run_fix": "Fixation in word run",
    "nrun": "Runs on word",
    "reread": "Reread",
    "excluded": "Excluded",
    "excluded_reason": "Excluded because",
    "blink_before": "Blink before",
    "blink_after": "Blink after",
    "original_duration_ms": "Original duration (ms)",
    "y_original": "Y before correction",
    "y_correction": "Y correction",
    "alignment_agreement": "Line agreement",
}


#: Canonical columns that can carry a copy of a partner's values — see
#: `ColumnNames.aliases`.
_ALIAS_PAIRS = (("trial_id", "unique_trial_id"), ("text_id", "unique_text_id"))

#: The note a time column read in another unit carries ("FPOGD, in ms"). A
#: figure drops it: its hover writes the unit after the value.
IN_MS = ", in ms"

#: The id columns a derived table (a summary, a saccade table) shares with the
#: dataset's own — the only ones it may carry under the file's names.
IDENTITY_COLUMNS = frozenset(
    {
        "participant_id",
        "trial_id",
        "unique_trial_id",
        "text_id",
        "unique_text_id",
        "screen_id",
        "word_id",
    }
)


def canonical_label(column) -> str:
    """A readable label for a column the app made (a measure, a run, an angle …)."""
    from .data import READING_MEASURE_FIELDS

    column = str(column)
    for _key, canonical, _short, full, *_ in READING_MEASURE_FIELDS:
        if canonical == column:
            return str(full)
    if column in _CANONICAL_LABELS:
        return _CANONICAL_LABELS[column]
    text = column.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


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

    def label(self, column) -> str:
        """What a person is shown for ``column`` (DATA-66 phase 2).

        The user's own name when the column was read from their files; a
        curated label marked :data:`COMPUTED_SUFFIX` when the app made it; else
        the column's own name.
        """
        entry = self.source(column)
        kind = self.kind_of(column)
        if (
            entry is not None
            and entry.sources
            and kind in (MAPPED, COMPOSITE, CONVERTED)
        ):
            # A converted column says what it holds now: a box width is the
            # difference of two edges, not their sum, and a duration read in
            # seconds is in ms.
            if kind == CONVERTED and entry.note:
                return entry.note
            return entry.display
        if kind in (COMPUTED, GENERATED):
            return canonical_label(column) + COMPUTED_SUFFIX
        return str(column)

    def figure_labels(self, columns: Iterable) -> dict[str, str]:
        """``{column: label}`` for a figure's text (`FigureSettings.column_labels`).

        Every column the dataset brought, under its own name; the columns the
        app made are left out, so a figure keeps its short labels for them
        ("Fixation #", "FFD") rather than writing "(computed)" into a hover.
        Bookkeeping columns (`data.INTERNAL_COLUMNS`) are no figure's text. A
        column converted from one source (a duration read in seconds) is named
        by that source: the figure writes its unit after the value, and the
        note's "…, in ms" would say it twice.
        """
        from .data import INTERNAL_COLUMNS

        out: dict[str, str] = {}
        for column in columns:
            if column in INTERNAL_COLUMNS or self.kind_of(column) in (
                COMPUTED,
                GENERATED,
            ):
                continue
            entry = self.source(column)
            unit_conversion = (
                entry is not None
                and entry.kind == CONVERTED
                and entry.note.endswith(IN_MS)
            )
            out[str(column)] = (
                entry.note.removesuffix(IN_MS)
                if unit_conversion
                else self.label(column)
            )
        return out

    def merged(self, other: ColumnNames) -> ColumnNames:
        """Both tables' entries, this map's winning where both name a column."""
        return ColumnNames({**dict(other.entries), **dict(self.entries)})

    def option_labels(self, options, extra: Mapping | None = None) -> dict[str, str]:
        """``{option: label}`` for a picker; ``extra`` labels synthetic options
        (``"(uniform)"``, ``"line"``). A label two options share gets the
        internal name added, so a picker never shows two identical rows."""
        extra = dict(extra or {})
        labels = {o: extra.get(o) or self.label(o) for o in options}
        counts: dict[str, int] = {}
        for value in labels.values():
            counts[value] = counts.get(value, 0) + 1
        return {
            o: f"{label} · {o}" if counts[label] > 1 and label != str(o) else label
            for o, label in labels.items()
        }

    def sort_options(self, options, first=()) -> list:
        """The user's columns first, the app's last; ``first`` stays in front.

        Stable within each group, so a curated order survives."""
        options = list(options)
        head = [o for o in options if o in first]
        rest = [o for o in options if o not in first]
        made = (COMPUTED, GENERATED)
        return (
            head
            + [o for o in rest if self.kind_of(o) not in made]
            + [o for o in rest if self.kind_of(o) in made]
        )

    def aliases(self, columns: Iterable[str]) -> set[str]:
        """Columns in ``columns`` that only repeat a partner from the same source.

        `unique_trial_id` mirrors `trial_id` (BUG-58) and `unique_text_id`
        usually mirrors `text_id`; when both of a pair were read from one column
        of the user's file, a table needs to show it once.
        """
        present = {str(c) for c in columns}
        hidden: set[str] = set()
        for main, alias in _ALIAS_PAIRS:
            first, second = self.source(main), self.source(alias)
            if (
                main in present
                and alias in present
                and first is not None
                and second is not None
                and first.sources
                and first.sources == second.sources
            ):
                hidden.add(alias)
        return hidden

    def with_rewrites(self, table: str, rewrites: Iterable) -> ColumnNames:
        """This map with every column the load rewrote (``data.Rewrite``s for
        ``table``) marked converted: a padded id, a shifted word id, positions
        filled from word boxes are no longer what the file held under its name,
        so the column is labelled "<source><how>" and exported under its
        internal name."""
        changed = dict(self.entries)
        for rewritten_table, column, how in rewrites or ():
            entry = changed.get(column)
            if rewritten_table != table or entry is None or entry.kind != MAPPED:
                continue
            note = " + ".join(entry.sources) + how
            changed[column] = SourceName(entry.sources, CONVERTED, note)
        return ColumnNames(changed)

    def identity(self) -> ColumnNames:
        """This map's id columns only (:data:`IDENTITY_COLUMNS`).

        For a table the app derives — a summary, a saccade table, a character
        grid — whose other columns reuse a canonical name (`n_fixations`,
        `duration_ms`, `x`) for a value of their own: only its ids are the
        file's."""
        return self.restricted_to(IDENTITY_COLUMNS)

    def redundant_aliases(self, frame) -> set[str]:
        """:meth:`aliases` that really repeat their partner in ``frame``.

        The map says both came from one column; the values decide, since a
        padded or suffixed id can part from its copy (BUG-59)."""
        partners = {alias: main for main, alias in _ALIAS_PAIRS}
        return {
            alias
            for alias in self.aliases(frame.columns)
            if frame[alias].equals(frame[partners[alias]])
        }

    def export_headers(self, columns: Iterable) -> dict[str, str]:
        """``{column: header}`` for a table written out (DATA-66 phase 3).

        A column read from one column of the user's file is written under that
        column's name. One built from several (a composite trial id), converted
        (a box width from two edges, a duration read in seconds) or made by the
        app keeps its canonical name — its values are not what the file held
        under any one name — and the bundle's `columns.json` and README say
        where it came from. A header that would repeat another column's name
        keeps the canonical one. Columns not renamed are left out.
        """
        names = [str(c) for c in columns]
        taken = set(names)
        out: dict[str, str] = {}
        for column in names:
            entry = self.source(column)
            if entry is None or entry.kind != MAPPED or len(entry.sources) != 1:
                continue
            header = entry.sources[0]
            if header == column or header in taken:
                continue
            taken.add(header)
            out[column] = header
        return out

    def provenance(self, column) -> str:
        """Where ``column`` came from, in a sentence fragment (the README's)."""
        entry = self.source(column)
        kind = self.kind_of(column)
        sources = ", ".join(f"`{s}`" for s in entry.sources) if entry else ""
        note = entry.note if entry else ""
        if kind == MAPPED and sources:
            return f"your column {sources}"
        if kind == COMPOSITE:
            return f"joined from your columns {sources}"
        if kind == CONVERTED:
            return f"converted from your {sources}" + (f" ({note})" if note else "")
        if kind == GENERATED:
            return "made by Scanpath Studio" + (f" ({note})" if note else "")
        if kind == COMPUTED:
            return "computed by Scanpath Studio"
        return "your column, under its own name"

    def restricted_to(self, columns: Iterable[str]) -> ColumnNames:
        """Only the entries for ``columns`` — a frame's actual columns.

        After an edit, :meth:`through` keeps every earlier entry the edit did
        not rebuild, including one for a column the edit removed (a cleared
        reading measure); restricting to the saved frame drops those, so the
        record never names a column the dataset no longer has.
        """
        keep = {str(c) for c in columns}
        return ColumnNames({c: e for c, e in self.entries.items() if c in keep})

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


def active(session: Mapping, table: str) -> ColumnNames:
    """The open dataset's map for ``table``, read from a session mapping.

    Takes the session as an argument so this module stays free of Streamlit;
    callers pass ``st.session_state``.
    """
    stash = session.get(ACTIVE_COLUMN_NAMES_KEY) or {}
    return ColumnNames.from_payload(stash.get(table))


def active_all(session: Mapping) -> ColumnNames:
    """The open dataset's map over all its tables, for a label any table can own.

    The fixations table's entries win, then the words table's (word-level
    fields such as surprisal are carried onto fixations), then raw gaze's.
    """
    return across_tables({table: active(session, table) for table in _TABLES})


def table_figure_labels(
    maps: Mapping[str, ColumnNames], columns: Mapping[str, Iterable]
) -> dict[str, str]:
    """`FigureSettings.column_labels` for a figure drawn from several tables.

    One flat map cannot hold two names for one column — ``word_id`` is the AOI
    table's ``IA_ID`` and the fixation table's interest-area column — so the
    merged map's labels (fixations' winning) sit under the plain keys and a
    word column the words table names differently also under
    ``"words:<column>"``, which a word hover reads first (`plots._table_label`).
    Only the tables the figure is drawn from are consulted, so a words-only
    figure is labelled by the words table alone.
    """
    columns = {table: list(cols) for table, cols in columns.items()}
    drawn = {table: names for table, names in maps.items() if table in columns}
    out = across_tables(drawn).figure_labels(
        [column for cols in columns.values() for column in cols]
    )
    words = maps.get("words")
    if words is not None and "words" in columns:
        for column, label in words.figure_labels(columns["words"]).items():
            if out.get(column) != label:
                out[f"words:{column}"] = label
    return out


def active_figure_labels(session: Mapping, **columns: Iterable) -> dict[str, str]:
    """:func:`table_figure_labels` for the open dataset — ``columns`` keyed by
    table (``words=…``, ``fixations=…``)."""
    return table_figure_labels(
        {table: active(session, table) for table in _TABLES}, columns
    )


#: The tables a dataset's map covers, in the order their entries win.
_TABLES = ("fixations", "words", "raw_gaze")


def across_tables(maps: Mapping[str, ColumnNames]) -> ColumnNames:
    """One map from a dataset's per-table maps (fixations', then words', then
    raw gaze's entries win) — what :func:`active_all` reads from the session,
    for a dataset held elsewhere (Compare's B, `SecondaryDataset.column_names`)."""
    out = EMPTY
    for table in _TABLES:
        if table in maps:
            out = out.merged(maps[table])
    return out


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
    elif text_id := _id_entry(schema.get("text_id")):
        # A remap fills `unique_text_id` from the mapped Text ID
        # (`data.remap_normalized_frame`); a first load has no such column, and
        # an entry for an absent column names nothing. A `unique_text_id` the
        # file itself has is the user's own column, under its own name.
        out["text_id"] = text_id
        if "unique_text_id" not in present:
            out["unique_text_id"] = text_id
    else:
        out["text_id"] = SourceName((), GENERATED, "the trial id")
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
    rewrites: Iterable | None = None,
) -> dict[str, dict]:
    """``{table: payload}`` for every table with a schema and a raw frame.

    ``rewrites`` are the ``data.Rewrite``s the load made
    (:meth:`ColumnNames.with_rewrites`)."""
    keeps = keeps or {}
    rewrites = tuple(rewrites or ())
    out: dict[str, dict] = {}
    for table, schema in schemas.items():
        columns = getattr(frames.get(table), "columns", None)
        if not schema or columns is None or len(columns) == 0:
            continue
        names = from_schema(table, schema, columns, keep_columns=keeps.get(table))
        out[table] = names.with_rewrites(table, rewrites).to_payload()
    return out


# --- Phase 3: what a written table calls its columns -------------------------

#: The `columns.json` format a bundle writes beside its tables.
COLUMNS_FILE_SCHEMA = 1


def _written_plan(frame, names: ColumnNames) -> tuple[set[str], dict[str, str]]:
    """``(left out, renamed)`` for writing ``frame``: the `unique_*` aliases that
    only repeat their partner, and each remaining column's header."""
    hidden = names.redundant_aliases(frame)
    kept = [c for c in frame.columns if c not in hidden]
    return hidden, names.export_headers(kept)


def as_written(frame, names: ColumnNames | None, hidden: set[str] | None = None):
    """``frame`` as a bundle writes it: each column the user's file named under
    that name (`ColumnNames.export_headers`), and a `unique_*` alias that only
    repeats its partner left out. The same object when nothing changes.

    ``hidden`` is the aliases to leave out, decided once for the whole table
    (:meth:`ColumnNames.redundant_aliases`) so every per-trial file of it has
    the same columns; without it, ``frame`` decides."""
    if names is None or not names.entries:
        return frame
    if hidden is None:
        hidden, headers = _written_plan(frame, names)
    else:
        hidden = {c for c in hidden if c in frame.columns}
        headers = names.export_headers([c for c in frame.columns if c not in hidden])
    if hidden:
        frame = frame.drop(columns=sorted(hidden))
    return frame.rename(columns=headers) if headers else frame


def written_columns(frame, names: ColumnNames | None) -> list[dict]:
    """What :func:`as_written` makes of ``frame``'s mapped columns, one row each:
    the header written, the internal (canonical) name, its kind, its sources and
    note. Columns the map does not record are written under their own names and
    are not listed."""
    if names is None or not names.entries:
        return []
    hidden, headers = _written_plan(frame, names)
    rows = []
    for column in frame.columns:
        entry = names.source(column)
        if column in hidden or entry is None:
            continue
        rows.append(
            {
                "column": headers.get(column, column),
                "canonical": column,
                "kind": entry.kind,
                "sources": list(entry.sources),
                "note": entry.note,
            }
        )
    return rows


def columns_manifest(tables: Mapping[str, list[dict]]) -> dict:
    """The `columns.json` a bundle carries: ``{table: written_columns(…)}``, so a
    script can map every file back to the internal names."""
    return {
        "schema": COLUMNS_FILE_SCHEMA,
        "tables": {table: rows for table, rows in tables.items() if rows},
    }


def dictionary_lines(
    tables: Mapping[str, list[dict]], names: Mapping[str, ColumnNames]
) -> list[str]:
    """The README's data dictionary: for each table's :func:`written_columns`,
    the header written and where it came from, in markdown."""
    titles = {"fixations": "Fixations", "words": "Words (AOIs)", "raw_gaze": "Raw gaze"}
    lines: list[str] = []
    for table, rows in tables.items():
        if not rows:
            continue
        lines += ["", f"### {titles.get(table, table)}"]
        for row in rows:
            written, column = row["column"], row["canonical"]
            internal = "" if written == column else f" (internally `{column}`)"
            lines.append(f"- `{written}`{internal}: {names[table].provenance(column)}")
    return lines


def source_schema(
    schema: Mapping | None, names: ColumnNames
) -> tuple[dict | None, tuple[str, ...]]:
    """``schema`` restated in the dataset's own files' column names.

    ✏️ Edit dataset maps fields onto the stored frame's *canonical* columns
    (``{"trial": "trial_id", "x": "x"}``), which say nothing to a script that
    reads the original files. Read through ``names`` — the map from before
    that edit — each becomes the column(s) it was read from, so the result can
    be handed to ``api.load_scanpath_data`` over those files (Share → Code). A
    column the app *made* (a generated stand-in, a computed value) maps to
    nothing, which makes the loader make it again; a box stored as
    ``x/y/width/height`` but read from edges is restated as those edges.

    Returns ``(schema, unresolved)``: the fields that could not be traced back,
    left as they were, for the caller to name.
    """
    from .data import trial_mapping_columns

    if schema is None:
        return None, ()
    out: dict = {}
    unresolved: list[str] = []
    for key, value in schema.items():
        if not value:
            out[key] = value
            continue
        columns: list[str] = []
        made = traced = False
        for column in trial_mapping_columns(value):
            entry = names.source(column)
            if entry is None:
                columns.append(str(column))
            elif entry.kind in (GENERATED, COMPUTED) or not entry.sources:
                made = True
            elif entry.kind == CONVERTED and len(entry.sources) != 1:
                traced = True  # right − left: only the edges say it
            else:
                columns.extend(entry.sources)
        if traced:
            out[key] = value
            unresolved.append(str(key))
        elif made:
            out[key] = None
        elif isinstance(value, str) and len(columns) == 1:
            out[key] = columns[0]
        else:
            out[key] = columns
    # A box read from edges is stored as x/y/width/height, its width and height
    # computed as right − left: restate it as the edges it came from.
    sizes = [names.source(schema.get(side) or "") for side in ("width", "height")]
    if (
        {"width", "height"} <= set(unresolved)
        and all(e is not None and len(e.sources) == 2 for e in sizes)
        and isinstance(out.get("x"), str)
        and isinstance(out.get("y"), str)
    ):
        out.update(
            left=out["x"],
            top=out["y"],
            right=sizes[0].sources[0],
            bottom=sizes[1].sources[0],
            x=None,
            y=None,
            width=None,
            height=None,
        )
        unresolved = [k for k in unresolved if k not in ("width", "height")]
    return out, tuple(unresolved)


def stored_source_recipe(stored: Mapping) -> dict:
    """A stored dataset's ``source_recipe`` — how a script loads its files.

    Written when the dataset is added (`wizard._source_recipe`) and kept
    current by ✏️ Edit dataset; read by Share → Code
    (`code_snippet.upload_source`). A dataset stored before the recipe existed
    gets one read off its stored mapping through its column-name map, which is
    right unless one of its files used a canonical column name for a different
    field.
    """
    recipe = stored.get("source_recipe")
    if isinstance(recipe, Mapping):
        return dict(recipe)
    names = stored.get("column_names") or {}
    schemas: dict = {}
    unresolved: dict = {}
    for table, schema in (stored.get("schemas") or {}).items():
        schemas[table], missing = source_schema(
            schema, ColumnNames.from_payload(names.get(table))
        )
        if missing:
            unresolved[table] = list(missing)
    return {"schemas": schemas, "unresolved": unresolved}


# --- Phase 4: a frame that carries its own names ------------------------------

#: The `DataFrame.attrs` key a frame under the dataset's own names carries its
#: map in (`attach`). pandas 3 keeps `attrs` through filtering, `loc`, `copy`,
#: `assign` and `groupby`, so a script can slice the frame it loaded and hand it
#: back to the API. `merge` and `concat` keep them only when every input carries
#: the same `attrs`: a frame joined with a table of the user's own loses its map,
#: and `api._require_normalized` says how to get it back.
ATTRS_KEY = "scanpath_studio.columns"


def attach(frame, table: str, names: ColumnNames | None):
    """``frame`` under the dataset's own names (:func:`as_written`), carrying
    its map in ``attrs`` so :func:`to_canonical_frame` can undo it. A frame
    with no names to apply comes back as it was."""
    if frame is None or names is None or not names.entries:
        return frame
    hidden, headers = _written_plan(frame, names)
    partners = {alias: main for main, alias in _ALIAS_PAIRS}
    out = as_written(frame, names, hidden)
    # One JSON string, not a nested dict: pandas deep-copies `attrs` on every
    # operation, and walking a dict of dicts made a script's per-trial loop
    # over a corpus 2-3x slower; a string is copied for nothing.
    record = {
        "table": table,
        "names": names.to_payload(),
        "renamed": {header: column for column, header in headers.items()},
        "aliases": {alias: partners[alias] for alias in hidden},
    }
    out.attrs = {**frame.attrs, ATTRS_KEY: json.dumps(record)}
    return out


def _record(frame) -> dict | None:
    """The record :func:`attach` left on ``frame``, else ``None``."""
    raw = getattr(frame, "attrs", {}).get(ATTRS_KEY)
    if not isinstance(raw, str):
        return None
    try:
        record = json.loads(raw)
    except ValueError:
        return None
    return record if isinstance(record, dict) else None


def frame_names(frame) -> tuple[str, ColumnNames] | None:
    """``(table, map)`` a frame under the dataset's own names carries, else
    ``None`` (a canonical frame, or any other table)."""
    record = _record(frame)
    if record is None:
        return None
    return str(record.get("table", "")), ColumnNames.from_payload(record.get("names"))


def to_canonical_frame(frame):
    """A frame :func:`attach` named, back under the canonical names it is
    processed in — the inverse every API function applies on entry. Any other
    frame is returned unchanged."""
    record = _record(frame)
    if record is None:
        return frame
    renamed = {
        header: column
        for header, column in (record.get("renamed") or {}).items()
        if header in frame.columns and column not in frame.columns
    }
    out = frame.rename(columns=renamed) if renamed else frame.copy(deep=False)
    for alias, main in (record.get("aliases") or {}).items():
        if alias not in out.columns and main in out.columns:
            out[alias] = out[main]
    out.attrs = {k: v for k, v in frame.attrs.items() if k != ATTRS_KEY}
    return out
