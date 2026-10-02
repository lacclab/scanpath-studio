# DATA-66 phase 1 — the column-name map: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record, per table of every dataset, the user's own name for each canonical column (and whether the app converted, generated or computed it), and keep that record through every place a dataset lives.

**Architecture:** A pure module, `scanpath_studio/column_names.py`, holds a frozen `ColumnNames` value and a `from_schema` builder that derives it from the same schema, registries and raw columns `data.normalize_*` use — so normalization itself is untouched. The app stashes the map beside the column mapping it already stashes (`_active_column_mapping` → `_active_column_names`), stores it on each uploaded dataset's `_datasets` entry (`column_names`, a JSON payload the recovery cache carries for free), composes it through ✏️ Edit dataset → Save instead of losing it, and hands it to Compare's `SecondaryDataset`. Nothing user-visible changes in phase 1; phases 2–4 (on screen, exports, API/CLI) read the map.

**Tech Stack:** Python 3.11+, pandas 3, Streamlit (AppTest for integration tests), pytest via `uv run --extra test pytest`, ruff 0.16.3 via `uv run --extra lint ruff`.

**Spec:** [`plans/data-66-original-column-names.md`](data-66-original-column-names.md) — §Design 1 (the map), §5 (what does not change), the settled defaults, and the appendix's "Wire formats and where the mapping lives".

## Global Constraints

- Canonical column names stay the internal contract and every wire format's values (Share links, saved configs, designs, recovery cache) — phase 1 changes **no** wire value and **no** session key in `session_keys.py`.
- `from __future__ import annotations` at the top of every Python file; pure modules import no Streamlit.
- No back-compat shims (house rule): a dataset stored before this change simply has no `column_names` and falls back to canonical names.
- Run tests as `uv run --extra test pytest …` and lint as `uv run --extra lint ruff check .` + `uv run --extra lint ruff format --check .` — never the bare `python3` / `ruff` on PATH (other versions).
- Commit subject carries `(DATA-66)`; no AI co-author trailer.
- No changelog fragment in phase 1 (nothing user-visible); phase 2 adds `changelog.d/DATA-66.changed.md`.

---

## File structure

| File | Responsibility |
|---|---|
| Create `scanpath_studio/column_names.py` | `SourceName`, `ColumnNames`, `COMPUTED_COLUMNS`, `from_schema`, `for_tables` — what each canonical column was called, and how it came to be. |
| Create `tests/test_column_names.py` | Unit tests of the module against the real registries and the bundled demo. |
| Modify `scanpath_studio/app.py` | Stash/read the active dataset's map (`_stash_column_names`, `active_column_names`); build it in `prepare_data` and the raw-gaze loaders; republish a stored upload's map. |
| Modify `scanpath_studio/wizard.py` | Store `column_names` on the finalize payload (generic and MultiplEYE uploads). |
| Modify `scanpath_studio/tabs.py` | `_apply_remap` composes the map through the edit instead of dropping the source names. |
| Modify `scanpath_studio/compare_source.py` | `SecondaryDataset.column_names` for a stored upload. |
| Modify `tests/test_persistence.py` | The payload survives a recovery-cache round trip. |
| Modify `AGENTS.md`, `scanpath_studio/CLAUDE.md` | The new module in the architecture map; the gotcha about `_apply_remap`. |

---

### Task 1: `column_names.py` — the value type and the computed-column set

**Files:**
- Create: `scanpath_studio/column_names.py`
- Test: `tests/test_column_names.py`

**Interfaces:**
- Produces:
  - `SourceName(sources: tuple[str, ...], kind: str = MAPPED, note: str = "")` with property `display -> str` (sources joined `" + "`).
  - Kind constants `MAPPED, COMPOSITE, CONVERTED, GENERATED, COMPUTED, YOURS`.
  - `COMPUTED_COLUMNS: frozenset[str]`.
  - `ColumnNames(entries: Mapping[str, SourceName])` with `source(column) -> SourceName | None`, `kind_of(column) -> str`, `display(column) -> str`, `to_canonical(name) -> str`, `through(earlier: ColumnNames) -> ColumnNames`, `to_payload() -> dict`, classmethod `from_payload(payload) -> ColumnNames`, and `EMPTY = ColumnNames({})`.

- [ ] **Step 1: Write the failing tests**

```python
"""DATA-66 phase 1: the dataset's own column names, behind the canonical ones."""

from __future__ import annotations

from scanpath_studio import column_names as cn
from scanpath_studio.column_names import ColumnNames, SourceName


class TestColumnNames:
    def test_display_is_the_source_or_the_column_itself(self):
        names = ColumnNames({"duration_ms": SourceName(("CURRENT_FIX_DURATION",))})
        assert names.display("duration_ms") == "CURRENT_FIX_DURATION"
        assert names.display("my_extra") == "my_extra"

    def test_a_composite_displays_its_parts(self):
        names = ColumnNames(
            {"trial_id": SourceName(("reader_id", "text_id"), cn.COMPOSITE)}
        )
        assert names.display("trial_id") == "reader_id + text_id"

    def test_kind_falls_back_to_computed_then_yours(self):
        names = ColumnNames({"duration_ms": SourceName(("dur",))})
        assert names.kind_of("duration_ms") == cn.MAPPED
        assert names.kind_of("is_regression") == cn.COMPUTED
        assert names.kind_of("my_extra") == cn.YOURS

    def test_an_imported_measure_is_the_users_not_computed(self):
        names = ColumnNames(
            {"total_fixation_duration_ms": SourceName(("IA_DWELL_TIME",))}
        )
        assert names.kind_of("total_fixation_duration_ms") == cn.MAPPED

    def test_to_canonical_reads_the_map_backwards(self):
        names = ColumnNames({"duration_ms": SourceName(("dur",), cn.CONVERTED)})
        assert names.to_canonical("dur") == "duration_ms"
        assert names.to_canonical("duration_ms") == "duration_ms"
        assert names.to_canonical("unknown") == "unknown"

    def test_payload_round_trips(self):
        names = ColumnNames(
            {
                "trial_id": SourceName(("a", "b"), cn.COMPOSITE),
                "fixation_id": SourceName((), cn.GENERATED, "1, 2, … per trial"),
            }
        )
        assert ColumnNames.from_payload(names.to_payload()) == names
        assert ColumnNames.from_payload(None) == cn.EMPTY
        assert ColumnNames.from_payload({"x": "not a dict"}) == cn.EMPTY

    def test_through_renames_sources_by_an_earlier_map(self):
        """An Edit-dataset save maps fields onto the stored *canonical* columns;
        read through the dataset's earlier map, they are the user's names again."""
        earlier = ColumnNames(
            {
                "trial_id": SourceName(("TRIAL",)),
                "text_id": SourceName(("PARAGRAPH",)),
                "timestamp_ms": SourceName((), cn.GENERATED, "order"),
                "total_fixation_duration_ms": SourceName(("IA_DWELL_TIME",)),
            }
        )
        edit = ColumnNames(
            {
                "trial_id": SourceName(("text_id",)),
                "timestamp_ms": SourceName(("timestamp_ms",)),
            }
        )
        merged = edit.through(earlier)
        assert merged.display("trial_id") == "PARAGRAPH"
        assert merged.kind_of("timestamp_ms") == cn.GENERATED
        # What the edit did not touch keeps the earlier record.
        assert merged.display("total_fixation_duration_ms") == "IA_DWELL_TIME"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_column_names.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scanpath_studio.column_names'`.

- [ ] **Step 3: Write the module**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_column_names.py -q`
Expected: 7 passed.

- [ ] **Step 5: Lint and commit**

```bash
uv run --extra lint ruff check . -q && uv run --extra lint ruff format --check . -q
git add scanpath_studio/column_names.py tests/test_column_names.py
git commit -m "Add the column-name map's value type (DATA-66)"
```

---

### Task 2: `from_schema` — build the map the way normalization reads the data

**Files:**
- Modify: `scanpath_studio/column_names.py` (append)
- Test: `tests/test_column_names.py` (append)

**Interfaces:**
- Consumes: Task 1's types; `data.trial_mapping_columns`, `data.time_unit_ms`, `data.WORD_OPTIONAL_FIELDS`, `data.FIX_OPTIONAL_FIELDS`, `data.READING_MEASURE_FIELDS` (all exist).
- Produces:
  - `from_schema(table: str, schema: Mapping | None, columns: Iterable[str], *, keep_columns: Iterable[str] | None = None) -> ColumnNames` — `table` is `"words"`, `"fixations"` or `"raw_gaze"`; `columns` are the **raw** frame's columns; `keep_columns` the same set `normalize_*` was given (`None` = every registry field, as normalization does).
  - `for_tables(schemas: Mapping[str, Mapping | None], frames: Mapping[str, pd.DataFrame | None], keeps: Mapping[str, Iterable[str] | None] | None = None) -> dict[str, dict]` — `{table: payload}` for every table with a schema and a frame.

Normalization rules mirrored (read `data.normalize_words` / `normalize_fixations` / `normalize_raw_gaze` while implementing):
- A schema id field (`participant`, `trial`, `text_id`) that is a list of ≥ 2 columns is `COMPOSITE`; one column is `MAPPED`. No participant → `GENERATED` ("one reader for the whole table"). `unique_trial_id` mirrors `trial_id`.
- Words/fixations with a raw `unique_paragraph_id`: `text_id` and `unique_text_id` are `MAPPED` from it (it wins over the schema). Else the schema's `text_id`, else `GENERATED` ("the trial id").
- Words: no `text` → `GENERATED` ("w0, w1 … from the word id"); no `line` → `GENERATED` ("1 — one line"); edges → `x`/`y` `MAPPED` from left/top, `width`/`height` `CONVERTED` with note `"<right> − <left>"`.
- Fixations: no `x`/`y` → `COMPUTED` ("the fixated word's box centre"); `duration`/`timestamp` `CONVERTED` when `data.time_unit_ms(column) != 1` (note `"<column>, in ms"`); no `timestamp` → `GENERATED` ("the fixation's order in its trial"); no `fixation_id` → `GENERATED` ("1, 2, … per trial"); no `word_id` → `COMPUTED` ("assigned from the word boxes").
- Raw gaze: no `timestamp` → `GENERATED` ("the sample's order in its trial"); no `text` → none.
- Screen fields: each mapped one (`screen_id`, `screen_index`, `screen_timestamp`→`screen_timestamp_ms`, `screen_fixation_id`, `canvas_width`, `canvas_height`) `MAPPED`.
- Registries: every `(src, dest, …)` whose `src` is in `columns` (and in `keep_columns` when given) and whose `dest != src` is `MAPPED` from `src`; a later entry for the same `dest` wins (as `_apply_optional_fields` overwrites).
- Reading measures (words only): a `measure_*` key in the schema decides — mapped and present → `MAPPED` from it; cleared → no entry.

- [ ] **Step 1: Write the failing tests**

```python
import pandas as pd
import pytest

from scanpath_studio import data
from scanpath_studio.column_names import from_schema


@pytest.fixture(scope="module")
def demo_raw():
    return data.load_sample_data()


class TestFromSchema:
    def test_the_demo_words_keep_their_eyelink_names(self, demo_raw):
        words, _ = demo_raw
        names = from_schema("words", data.propose_word_schema(words), words.columns)
        assert names.display("word_id") == "IA_ID"
        assert names.display("text") == "IA_LABEL"
        assert names.display("total_fixation_duration_ms") == "IA_DWELL_TIME"
        assert names.kind_of("width") == cn.CONVERTED
        assert "IA_RIGHT" in names.source("width").note

    def test_the_demo_fixations_keep_their_eyelink_names(self, demo_raw):
        _, fixations = demo_raw
        schema = data.propose_fix_schema(fixations)
        names = from_schema("fixations", schema, fixations.columns)
        assert names.display("duration_ms") == schema["duration"]
        assert names.display("x") == schema["x"]
        assert names.kind_of("order_in_trial") == cn.COMPUTED

    def test_every_canonical_column_has_a_name_or_is_computed(self, demo_raw):
        words, fixations = demo_raw
        for table, raw, canonical in (
            ("words", words, data.WORDS_CANONICAL_COLUMNS),
            ("fixations", fixations, data.FIX_CANONICAL_COLUMNS),
        ):
            schema = (
                data.propose_word_schema(raw)
                if table == "words"
                else data.propose_fix_schema(raw)
            )
            names = from_schema(table, schema, raw.columns)
            for column in canonical:
                assert names.source(column) is not None or (
                    names.kind_of(column) == cn.COMPUTED
                ), (table, column)

    def test_missing_fields_are_generated_not_named(self):
        raw = pd.DataFrame(columns=["trial", "dur", "px", "py"])
        schema = {"trial": "trial", "duration": "dur", "x": "px", "y": "py"}
        names = from_schema("fixations", schema, raw.columns)
        for column in ("participant_id", "fixation_id", "timestamp_ms", "text_id"):
            assert names.kind_of(column) == cn.GENERATED, column
            assert names.display(column) == column

    def test_a_unit_conversion_is_said(self):
        raw = pd.DataFrame(columns=["trial", "FPOGD", "FPOGX", "FPOGY"])
        schema = {"trial": "trial", "duration": "FPOGD", "x": "FPOGX", "y": "FPOGY"}
        names = from_schema("fixations", schema, raw.columns)
        assert names.kind_of("duration_ms") == cn.CONVERTED
        assert names.display("duration_ms") == "FPOGD"

    def test_a_composite_trial_id_names_every_part(self):
        raw = pd.DataFrame(columns=["reader", "item", "dur", "x", "y"])
        schema = {
            "participant": "reader",
            "trial": ["reader", "item"],
            "duration": "dur",
            "x": "x",
            "y": "y",
        }
        names = from_schema("fixations", schema, raw.columns)
        assert names.kind_of("trial_id") == cn.COMPOSITE
        assert names.display("trial_id") == "reader + item"

    def test_keep_columns_limit_the_registry(self):
        """A registry rename (`Reduced_POS` → `reduced_pos`) is named only when
        normalization carried it — every field by default, the kept ones when
        the wizard narrowed the read."""
        raw = pd.DataFrame(
            columns=["trial", "IA_ID", "IA_LABEL", "x", "y", "width", "height",
                     "Reduced_POS"]
        )
        schema = {
            "trial": "trial",
            "word_id": "IA_ID",
            "text": "IA_LABEL",
            "x": "x",
            "y": "y",
            "width": "width",
            "height": "height",
        }
        assert from_schema("words", schema, raw.columns).display("reduced_pos") == (
            "Reduced_POS"
        )
        kept_none = from_schema("words", schema, raw.columns, keep_columns=set())
        assert kept_none.source("reduced_pos") is None

    def test_a_cleared_reading_measure_has_no_name(self, demo_raw):
        words, _ = demo_raw
        schema = dict(data.propose_word_schema(words), measure_tfd=None)
        names = from_schema("words", schema, words.columns)
        assert names.source("total_fixation_duration_ms") is None

    def test_for_tables_skips_absent_tables(self, demo_raw):
        words, fixations = demo_raw
        payloads = cn.for_tables(
            {"words": data.propose_word_schema(words), "fixations": None},
            {"words": words, "fixations": fixations},
        )
        assert set(payloads) == {"words"}
        assert ColumnNames.from_payload(payloads["words"]).display("text") == "IA_LABEL"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --extra test pytest tests/test_column_names.py -q`
Expected: FAIL — `ImportError: cannot import name 'from_schema'`.

- [ ] **Step 3: Implement `from_schema` and `for_tables`** (append to `column_names.py`)

```python
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
    from .data import trial_mapping_columns

    if not value:
        return None
    columns = trial_mapping_columns(value)
    if len(columns) > 1:
        return SourceName(tuple(columns), COMPOSITE)
    return SourceName((columns[0],), MAPPED)


def _timed(column: str) -> SourceName:
    from .data import time_unit_ms

    if time_unit_ms(column) != 1.0:
        return SourceName((column,), CONVERTED, f"{column}, in ms")
    return SourceName((column,), MAPPED)


def _registry(out, registry, present: set, keep: set | None) -> None:
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

    ``columns`` are the raw table's; ``keep_columns`` the set normalization was
    given (``None`` carries every registry field, as normalization does).
    """
    from . import data

    schema = dict(schema or {})
    present = {str(c) for c in columns}
    keep = None if keep_columns is None else {str(c) for c in keep_columns}
    out: dict[str, SourceName] = {}

    participant = _id_entry(schema.get("participant"))
    out["participant_id"] = participant or SourceName(
        (), GENERATED, "one reader for the whole table"
    )
    if trial := _id_entry(schema.get("trial")):
        out["trial_id"] = out["unique_trial_id"] = trial
    if table != "raw_gaze" and "unique_paragraph_id" in present:
        out["text_id"] = out["unique_text_id"] = SourceName(("unique_paragraph_id",))
    elif text_id := _id_entry(schema.get("text_id")):
        out["text_id"] = text_id
    else:
        out["text_id"] = SourceName((), GENERATED, "the trial id")
    for key, canonical in _SCREEN_FIELDS:
        if schema.get(key):
            out[canonical] = SourceName((schema[key],))

    if table == "words":
        out["word_id"] = SourceName((schema["word_id"],)) if schema.get(
            "word_id"
        ) else SourceName((), GENERATED, "the row order")
        out["text"] = (
            SourceName((schema["text"],))
            if schema.get("text")
            else SourceName((), GENERATED, "w0, w1 … from the word id")
        )
        out["line_idx"] = (
            SourceName((schema["line"],))
            if schema.get("line")
            else SourceName((), GENERATED, "1 — one line")
        )
        if all(schema.get(k) for k in ("x", "y", "width", "height")):
            for k in ("x", "y", "width", "height"):
                out[k] = SourceName((schema[k],))
        elif all(schema.get(k) for k in ("left", "right", "top", "bottom")):
            left, right = schema["left"], schema["right"]
            top, bottom = schema["top"], schema["bottom"]
            out["x"], out["y"] = SourceName((left,)), SourceName((top,))
            out["width"] = SourceName((right, left), CONVERTED, f"{right} − {left}")
            out["height"] = SourceName((bottom, top), CONVERTED, f"{bottom} − {top}")
        _registry(out, data.WORD_OPTIONAL_FIELDS, present, keep)
        for key, canonical, *_ in data.READING_MEASURE_FIELDS:
            if key not in schema:
                continue
            column = schema.get(key)
            if column and column in present:
                out[canonical] = SourceName((column,))
            else:
                out.pop(canonical, None)
    elif table == "fixations":
        for coord in ("x", "y"):
            out[coord] = (
                SourceName((schema[coord],))
                if schema.get(coord)
                else SourceName((), COMPUTED, "the fixated word's box centre")
            )
        if schema.get("duration"):
            out["duration_ms"] = _timed(schema["duration"])
        out["timestamp_ms"] = (
            _timed(schema["timestamp"])
            if schema.get("timestamp")
            else SourceName((), GENERATED, "the fixation's order in its trial")
        )
        out["fixation_id"] = (
            SourceName((schema["fixation_id"],))
            if schema.get("fixation_id")
            else SourceName((), GENERATED, "1, 2, … per trial")
        )
        out["word_id"] = (
            SourceName((schema["word_id"],))
            if schema.get("word_id")
            else SourceName((), COMPUTED, "assigned from the word boxes")
        )
        _registry(out, data.FIX_OPTIONAL_FIELDS, present, keep)
    else:  # raw gaze
        for coord in ("x", "y"):
            if schema.get(coord):
                out[coord] = SourceName((schema[coord],))
        out["timestamp_ms"] = (
            _timed(schema["timestamp"])
            if schema.get("timestamp")
            else SourceName((), GENERATED, "the sample's order in its trial")
        )
        for key in ("text", "word_id"):
            if schema.get(key):
                out[key] = SourceName((schema[key],))
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
        frame = frames.get(table)
        columns = getattr(frame, "columns", None)
        if not schema or columns is None or len(columns) == 0:
            continue
        out[table] = from_schema(
            table, schema, columns, keep_columns=keeps.get(table)
        ).to_payload()
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_column_names.py -q`
Expected: all passed. If `test_every_canonical_column_has_a_name_or_is_computed` names a column, add the rule for it from the matching `data.normalize_*` branch rather than adding it to `COMPUTED_COLUMNS`.

- [ ] **Step 5: Guard `COMPUTED_COLUMNS` against the measures code** (append to the test file)

```python
def test_every_column_the_measures_add_is_known_as_computed(
    normalized_words_df, normalized_fixations_df
):
    """A column `measures.py` starts adding must be classed as computed, or it
    would be shown as if it were the user's."""
    from scanpath_studio import measures

    fixations = measures.enrich_fixations(
        measures.assign_fixations_to_words(normalized_fixations_df, normalized_words_df),
        normalized_words_df,
    )
    added = set(fixations.columns) - set(normalized_fixations_df.columns)
    words = measures.compute_per_word_measures(
        normalized_fixations_df, normalized_words_df
    )
    added |= set(words.columns) - set(normalized_words_df.columns)
    assert added - cn.COMPUTED_COLUMNS - {"word_id"} == set()
```

Run: `uv run --extra test pytest tests/test_column_names.py -q`. A failure names a column; add it to `COMPUTED_COLUMNS` under the comment for the module that adds it.

- [ ] **Step 6: Lint and commit**

```bash
uv run --extra lint ruff check . -q && uv run --extra lint ruff format --check . -q
git add scanpath_studio/column_names.py tests/test_column_names.py
git commit -m "Build the column-name map from the schema normalization used (DATA-66)"
```

---

### Task 3: the open dataset's map in the app — built-ins, raw gaze, stored uploads

**Files:**
- Modify: `scanpath_studio/app.py` — `_reset_active_mapping` (~L3123), `_stash_active_mapping` (~L3129), `prepare_data`'s stash (~L3542), the raw-gaze stashes (~L4087, ~L4129), the stored-dataset republish (~L8502).
- Test: `tests/test_column_names.py` (append an AppTest)

**Interfaces:**
- Consumes: `column_names.from_schema`, `ColumnNames`.
- Produces:
  - `app.ACTIVE_COLUMN_NAMES_KEY = "_active_column_names"` — `{table: payload}`.
  - `app._stash_active_mapping(table: str, schema: dict | None, columns: Iterable[str] | None = None, *, keep_columns=None, names: ColumnNames | None = None) -> None` — also stashes the map (from `names`, else built from `columns`).
  - `app.active_column_names(table: str) -> ColumnNames` — `EMPTY` when nothing is stashed.

- [ ] **Step 1: Write the failing test**

```python
streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.timeout(180)
def test_the_demo_is_opened_with_its_own_column_names():
    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT

    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    stashed = at.session_state[app.ACTIVE_COLUMN_NAMES_KEY]
    words = ColumnNames.from_payload(stashed["words"])
    assert words.display("total_fixation_duration_ms") == "IA_DWELL_TIME"
    assert ColumnNames.from_payload(stashed["fixations"]).display("x") != "x"
    assert "raw_gaze" in stashed  # the demo ships raw gaze
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --extra test pytest tests/test_column_names.py -k demo_is_opened -q`
Expected: FAIL — `AttributeError: module 'scanpath_studio.app' has no attribute 'ACTIVE_COLUMN_NAMES_KEY'`.

- [ ] **Step 3: Implement**

In `app.py`, beside `_reset_active_mapping` / `_stash_active_mapping`:

```python
#: DATA-66 — the open dataset's column-name map per table, as payloads
#: (`column_names.ColumnNames.to_payload`), stashed beside the mapping.
ACTIVE_COLUMN_NAMES_KEY = "_active_column_names"


def _reset_active_mapping() -> None:
    """Clear the stashed column mapping at the start of each data load, so a new
    source doesn't inherit the previous one's mapping in the Data Inspection tab."""
    st.session_state["_active_column_mapping"] = {}
    st.session_state[ACTIVE_COLUMN_NAMES_KEY] = {}


def _stash_active_mapping(
    table: str,
    schema: dict | None,
    columns: Iterable[str] | None = None,
    *,
    keep_columns: Iterable[str] | None = None,
    names: ColumnNames | None = None,
) -> None:
    """Record the schema (field → source column) actually used for ``table`` so
    ``tabs.render_data_inspection_tab`` can show how columns were mapped, and —
    DATA-66 — the column-name map it implies: ``names`` when the caller already
    has one (a stored upload), else built from the raw ``columns``."""
    mapping = st.session_state.setdefault("_active_column_mapping", {})
    mapping[table] = dict(schema) if schema else None
    stash = st.session_state.setdefault(ACTIVE_COLUMN_NAMES_KEY, {})
    if names is None and schema and columns is not None:
        names = from_schema(table, schema, columns, keep_columns=keep_columns)
    if names is None:
        stash.pop(table, None)
    else:
        stash[table] = names.to_payload()


def active_column_names(table: str) -> ColumnNames:
    """The open dataset's column-name map for ``table`` (DATA-66)."""
    stash = st.session_state.get(ACTIVE_COLUMN_NAMES_KEY) or {}
    return ColumnNames.from_payload(stash.get(table))
```

Add the import near the other local imports: `from scanpath_studio.column_names import ColumnNames, from_schema` (and `Iterable` from `collections.abc` if not imported).

Pass the raw columns at each call:

```python
    # prepare_data (~L3542)
    _stash_active_mapping(
        "words", word_schema if has_words else None, words_df.columns
    )
    _stash_active_mapping(
        "fixations", fix_schema if has_fixations else None, fixations_df.columns
    )
```

```python
        # demo raw gaze (~L4087): the raw sample is inside the cached builder,
        # so read its columns once more (load_sample_raw_gaze is cached).
        if raw_gaze_schema:
            _stash_active_mapping(
                "raw_gaze", raw_gaze_schema, load_sample_raw_gaze().columns
            )
```

```python
                # uploaded raw gaze (~L4129): `raw_gaze_df` is still the raw frame here.
                _stash_active_mapping("raw_gaze", raw_gaze_schema, raw_gaze_df.columns)
```

```python
        # stored-dataset republish (~L8502)
        stored_names = stored.get("column_names") or {}
        for table, schema in (stored.get("schemas") or {}).items():
            _stash_active_mapping(
                table,
                schema,
                names=ColumnNames.from_payload(stored_names.get(table))
                if table in stored_names
                else None,
            )
```

- [ ] **Step 4: Run the tests**

Run: `uv run --extra test pytest tests/test_column_names.py -q`
Expected: all passed.

- [ ] **Step 5: Lint and commit**

```bash
uv run --extra lint ruff check . -q && uv run --extra lint ruff format --check . -q
git add scanpath_studio/app.py tests/test_column_names.py
git commit -m "Keep the open dataset's column-name map beside its mapping (DATA-66)"
```

---

### Task 4: uploaded datasets store their map

**Files:**
- Modify: `scanpath_studio/wizard.py` — the generic finalize payload (~L4046–4080) and the MultiplEYE payload (~L2655–2690).
- Test: `tests/test_column_names.py` (append an AppTest using the wizard's upload seam)

**Interfaces:**
- Consumes: `column_names.for_tables`, `app._stash_active_mapping(..., names=)`.
- Produces: `_datasets[name]["column_names"]: dict[str, dict]` (table → payload) on every stored upload.

- [ ] **Step 1: Write the failing test** (it reuses the one-sided-upload pattern from `tests/test_broken_mapping_recovery.py`)

```python
_UPLOAD_WORDS = pd.DataFrame(
    {
        "reader": ["r0"] * 3,
        "item": ["t0"] * 3,
        "IA_ID": [0, 1, 2],
        "IA_LABEL": ["one", "two", "three"],
        "IA_LEFT": [0.0, 50.0, 100.0],
        "IA_RIGHT": [50.0, 100.0, 150.0],
        "IA_TOP": [10.0] * 3,
        "IA_BOTTOM": [30.0] * 3,
        "IA_DWELL_TIME": [200.0, 180.0, 240.0],
    }
)
_UPLOAD_FIXATIONS = pd.DataFrame(
    {
        "reader": ["r0"] * 3,
        "item": ["t0"] * 3,
        "CURRENT_FIX_DURATION": [200.0, 180.0, 240.0],
        "CURRENT_FIX_X": [15.0, 65.0, 115.0],
        "CURRENT_FIX_Y": [24.0] * 3,
    }
)


@pytest.mark.timeout(240)
def test_an_upload_stores_its_column_names(monkeypatch):
    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT, pin_data_view

    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {
            "col_map_words": _UPLOAD_WORDS,
            "col_map_fix": _UPLOAD_FIXATIONS,
        }.get(kw["state_prefix"], pd.DataFrame()),
    )
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.session_state["setup_complete"] = False
    pin_data_view(at)
    at.run(timeout=180)
    assert not at.exception, at.exception
    payload = at.session_state["_wizard_finalize_payload"]
    fixations = ColumnNames.from_payload(payload["column_names"]["fixations"])
    assert fixations.display("duration_ms") == "CURRENT_FIX_DURATION"
    words = ColumnNames.from_payload(payload["column_names"]["words"])
    assert words.display("total_fixation_duration_ms") == "IA_DWELL_TIME"
```

If the wizard needs a name or an attempt flag before it builds the payload, set the same session keys `tests/test_apptest.py`'s generic-upload tests set (search there for `_wizard_finalize_payload`); do not change the wizard's flow to make the test pass.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --extra test pytest tests/test_column_names.py -k upload_stores -q`
Expected: FAIL — `KeyError: 'column_names'`.

- [ ] **Step 3: Implement**

In the generic payload, beside `"schemas": wizard_schemas,`:

```python
            # DATA-66: what each canonical column was called in these files —
            # the record the app shows, exports and accepts names from. Built
            # from the raw tables, before character aggregation reshapes them.
            "column_names": for_tables(
                wizard_schemas,
                {"words": raw_words, "fixations": raw_fix, "raw_gaze": raw_gaze},
                {"words": keep_words, "fixations": keep_fix},
            ),
```

`raw_words` must be the pre-aggregation frame: if `raw_words` is reassigned by the character aggregation above this point, capture `raw_words_for_names = raw_words` before it and use that. Then stash it for the live session right after the payload is built:

```python
        for table, payload in st.session_state["_wizard_finalize_payload"][
            "column_names"
        ].items():
            app._stash_active_mapping(
                table,
                wizard_schemas.get(table),
                names=ColumnNames.from_payload(payload),
            )
```

In the MultiplEYE payload (beside `"schemas": schemas,`):

```python
            "column_names": for_tables(
                schemas, {"words": words_raw, "fixations": fix_raw}
            ),
```

Imports in `wizard.py`: `from .column_names import ColumnNames, for_tables`.

- [ ] **Step 4: Run the tests**

Run: `uv run --extra test pytest tests/test_column_names.py tests/test_broken_mapping_recovery.py tests/test_apptest.py -q -n 4`
Expected: all passed.

- [ ] **Step 5: Lint and commit**

```bash
uv run --extra lint ruff check . -q && uv run --extra lint ruff format --check . -q
git add scanpath_studio/wizard.py tests/test_column_names.py
git commit -m "Store each uploaded dataset's column-name map (DATA-66)"
```

---

### Task 5: ✏️ Edit dataset → Save keeps the user's names

**Files:**
- Modify: `scanpath_studio/tabs.py` — `_apply_remap` (~L11658).
- Test: `tests/test_column_names.py` (append)

**Interfaces:**
- Consumes: `from_schema`, `ColumnNames.through`, `ColumnNames.from_payload/to_payload`.
- Produces: `_datasets[name]["column_names"]` updated on every save, in the user's names.

The remap's schema names the stored frame's **canonical** columns (`tabs._WORD_REMAP_CANON` …), so a map built from it with the stored frame's columns names canonical columns as sources; `through(old)` turns them back into the user's names. A table *added* on the save screen is raw, so its map is built from the raw frame directly.

- [ ] **Step 1: Write the failing test** (pure — calls `_apply_remap` with session state prepared the way `tests/test_dataset_editor_parity.py` does; read that file first and reuse its setup helper if it has one)

```python
def test_an_edit_dataset_save_keeps_the_users_names(monkeypatch):
    import streamlit as st

    from scanpath_studio import api, tabs

    words, fixations = api.load_scanpath_data(_UPLOAD_WORDS, _UPLOAD_FIXATIONS)
    names = cn.for_tables(
        {
            "words": data.propose_word_schema(_UPLOAD_WORDS),
            "fixations": data.propose_fix_schema(_UPLOAD_FIXATIONS),
        },
        {"words": _UPLOAD_WORDS, "fixations": _UPLOAD_FIXATIONS},
    )
    stored = {
        "words": words,
        "fixations": fixations,
        "raw_gaze": pd.DataFrame(),
        "filter_fields": [],
        "composite_trial_columns": [],
        "schemas": {},
        "column_names": names,
    }
    state = {
        "_datasets": {"Mine": stored},
        "data_source_choice": "Mine",
        "_remap_pending_schemas": {
            "fixations": {
                "participant": "participant_id",
                "trial": "trial_id",
                "duration": "duration_ms",
                "x": "x",
                "y": "y",
            }
        },
    }
    monkeypatch.setattr(st, "session_state", state, raising=False)
    tabs._apply_remap()
    saved = state["_datasets"]["Mine"]["column_names"]
    fixations_names = ColumnNames.from_payload(saved["fixations"])
    assert fixations_names.display("duration_ms") == "CURRENT_FIX_DURATION"
    # The words table was not edited: its record is unchanged.
    assert saved["words"] == names["words"]
```

If `tabs._apply_remap` reads more session keys than this sets (it raises `KeyError` / `AttributeError`), add them with the values `tests/test_dataset_editor_parity.py` uses; the assertion lines stay as written.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --extra test pytest tests/test_column_names.py -k edit_dataset_save -q`
Expected: FAIL — `KeyError: 'column_names'` or the display assertion (the save drops the record).

- [ ] **Step 3: Implement** — in `_apply_remap`, start a names dict beside `new_schemas` and fill it in the two loops:

```python
    new_schemas = dict(stored.get("schemas") or {})
    # DATA-66: the save maps fields onto the stored frame's canonical columns;
    # read through the dataset's earlier record, the map keeps the user's names
    # (it used to be lost here, with `schemas` overwritten by the identity).
    new_names = dict(stored.get("column_names") or {})
```

In the remap loop, after `new_schemas[table_key] = schema`:

```python
        earlier = ColumnNames.from_payload(new_names.get(table_key))
        new_names[table_key] = (
            from_schema(table_key, schema, frame.columns).through(earlier).to_payload()
        )
```

In the added-tables loop, after `new_schemas[table_key] = schema` (here `raw` is the raw upload):

```python
        new_names[table_key] = from_schema(table_key, schema, raw.columns).to_payload()
```

Before the existing `new_entry["schemas"] = new_schemas`:

```python
    new_entry["column_names"] = new_names
```

Imports in `tabs.py`: `from .column_names import ColumnNames, from_schema`.

- [ ] **Step 4: Run the tests**

Run: `uv run --extra test pytest tests/test_column_names.py tests/test_dataset_editor_parity.py tests/test_mapping_dataset_scope.py -q -n 4`
Expected: all passed.

- [ ] **Step 5: Lint and commit**

```bash
uv run --extra lint ruff check . -q && uv run --extra lint ruff format --check . -q
git add scanpath_studio/tabs.py tests/test_column_names.py
git commit -m "Keep the user's column names through Edit dataset → Save (DATA-66)"
```

---

### Task 6: Compare's B and the recovery cache

**Files:**
- Modify: `scanpath_studio/compare_source.py` — `SecondaryDataset` (~L59), `load_secondary_dataset` (~L365).
- Modify: `tests/test_persistence.py` (append)
- Test: `tests/test_column_names.py` (append)

**Interfaces:**
- Consumes: `ColumnNames.from_payload`.
- Produces: `SecondaryDataset.column_names: Mapping[str, ColumnNames]` (table → map; empty for a public corpus or the demo until phase 4 gives the loaders their maps).

- [ ] **Step 1: Write the failing tests**

In `tests/test_column_names.py`:

```python
def test_compare_b_carries_a_stored_uploads_names(monkeypatch):
    import streamlit as st

    from scanpath_studio import api, compare_source

    words, fixations = api.load_scanpath_data(_UPLOAD_WORDS, _UPLOAD_FIXATIONS)
    names = cn.for_tables(
        {"fixations": data.propose_fix_schema(_UPLOAD_FIXATIONS)},
        {"fixations": _UPLOAD_FIXATIONS},
    )
    state = {
        "_datasets": {
            "Mine": {
                "words": words,
                "fixations": fixations,
                "raw_gaze": pd.DataFrame(),
                "composite_trial_columns": [],
                "column_names": names,
            }
        }
    }
    monkeypatch.setattr(st, "session_state", state, raising=False)
    b = compare_source.load_secondary_dataset("Mine")
    assert b.column_names["fixations"].display("duration_ms") == (
        "CURRENT_FIX_DURATION"
    )
```

In `tests/test_persistence.py`, next to `test_setup_snapshot_survives_a_cache_round_trip`:

```python
def test_column_names_survive_a_cache_round_trip(tmp_path):
    """DATA-66: the column-name map is a plain payload on the entry, so the
    manifest carries it like `setup` — a restored upload keeps its names."""
    names = {
        "fixations": {
            "duration_ms": {
                "sources": ["CURRENT_FIX_DURATION"],
                "kind": "mapped",
                "note": "",
            }
        }
    }
    payload = _dataset()
    payload["column_names"] = names
    assert save_state({"_datasets": {"Corpus": payload}}, tmp_path)
    restored = {}
    assert restore_state(restored, tmp_path)
    assert restored["_datasets"]["Corpus"]["column_names"] == names
```

- [ ] **Step 2: Run them**

Run: `uv run --extra test pytest tests/test_column_names.py tests/test_persistence.py -k "compare_b or column_names_survive" -q`
Expected: the Compare test FAILS (`AttributeError: … has no attribute 'column_names'`); the persistence test may already PASS (non-frame entry fields are persisted generically) — if so, it stays as the regression guard.

- [ ] **Step 3: Implement** — in `compare_source.py`:

```python
    #: DATA-66: B's column-name map per table — a stored upload's own; empty for
    #: a public corpus or the demo until their loaders return one (phase 4).
    column_names: Mapping[str, ColumnNames] = field(default_factory=dict)
```

In `load_secondary_dataset`, in the `isinstance(stored, dict)` branch:

```python
        column_names = {
            table: ColumnNames.from_payload(payload)
            for table, payload in (stored.get("column_names") or {}).items()
        }
```

set `column_names = {}` in the other branch, and pass `column_names=column_names` to `SecondaryDataset(...)`. Imports: `from collections.abc import Mapping` (if absent) and `from .column_names import ColumnNames`.

- [ ] **Step 4: Run the tests**

Run: `uv run --extra test pytest tests/test_column_names.py tests/test_persistence.py tests/test_compare_cross_dataset.py -q -n 4`
Expected: all passed.

- [ ] **Step 5: Lint and commit**

```bash
uv run --extra lint ruff check . -q && uv run --extra lint ruff format --check . -q
git add scanpath_studio/compare_source.py tests/test_column_names.py tests/test_persistence.py
git commit -m "Give Compare's B its column-name map; pin the cache round trip (DATA-66)"
```

---

### Task 7: document the module, then verify the whole

**Files:**
- Modify: `AGENTS.md` (architecture tree, after the `metadata.py` line)
- Modify: `scanpath_studio/CLAUDE.md` (Modules list and Gotchas)

- [ ] **Step 1: Add the architecture line** to `AGENTS.md`'s tree:

```text
├─ column_names.py   DATA-66: the dataset's own column names behind the canonical ones — `ColumnNames` (canonical → `SourceName(sources, kind, note)`; kinds mapped / composite / converted / generated / computed / yours), built by `from_schema` from the schema + registries normalization used. Stored as a payload per table: `_active_column_names` (open dataset), `_datasets[name]["column_names"]` (uploads, and so the recovery cache), `SecondaryDataset.column_names`. Pure
```

- [ ] **Step 2: Add the gotcha** to `scanpath_studio/CLAUDE.md`'s Gotchas:

```markdown
- **DATA-66 — a dataset's column-name map must survive every rewrite of the entry.** ✏️ Edit dataset → Save (`tabs._apply_remap`) maps fields onto the stored *canonical* columns, so it composes the map through the earlier one (`ColumnNames.through`) rather than rebuilding it — rebuilt, every source would read as its canonical name. Anything else that rewrites `_datasets[name]` must carry `column_names` along.
```

- [ ] **Step 3: Full suite and lint**

Run: `uv run --extra test pytest -n auto -q` → all passed (report the counts).
Run: `uv run --extra lint ruff check . -q && uv run --extra lint ruff format --check . -q` → clean.

- [ ] **Step 4: Reviewers** — run the `surface-parity-reviewer` and `perf-reviewer` subagents on `git diff origin/main...HEAD` (tell them: read-only, no server, no browser, `SCANPATH_STUDIO_PERSIST=0`). The perf review's question: does `from_schema` add per-rerun cost? (`prepare_data` builds it on every run — it walks the registries, a few hundred tuples, no frame work; if the reviewer measures it above ~1 ms, cache it on `(table, frozenset(schema items), tuple(columns))` with `functools.lru_cache`.)

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md scanpath_studio/CLAUDE.md
git commit -m "Document the column-name map (DATA-66)"
```

---

## Self-review

- **Spec coverage (phase 1):** the map type (Task 1), built at normalization's inputs (Task 2), stored per dataset — open dataset (Task 3), uploads (Task 4), Edit-dataset save fixed (Task 5), Compare's B + recovery cache (Task 6). Public corpora and the demo get their maps on the open dataset via `prepare_data` (Task 3); as Compare's B they stay empty until phase 4 changes the loaders' return values — stated in Task 6's interface. Synthetic and authored data have no schema, so no map: they fall back to canonical names, as the spec says.
- **Out of scope here (phases 2–4):** labels on screen, the ⚙ computed marker, alias hiding, exports, `ScanpathData`, either-name API inputs.
- **Type consistency:** `from_schema(table, schema, columns, *, keep_columns)`, `for_tables(schemas, frames, keeps)`, `ColumnNames.through(earlier)`, `app._stash_active_mapping(table, schema, columns=None, *, keep_columns=None, names=None)`, `app.active_column_names(table)`, `SecondaryDataset.column_names` — used with these signatures throughout.
