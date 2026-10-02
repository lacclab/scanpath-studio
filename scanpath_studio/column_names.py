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
