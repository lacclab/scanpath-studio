# DATA-66 phase 2a — your column names on screen (rail, tables, setup): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wherever the plot rail, the Data Management tables and the dataset setup screens name a column, they show the name it has in the user's files, and they mark what the app computed.

**Architecture:** Phase 1's `ColumnNames` gains label rules (`label`, `merged`, `sort_options`, `option_labels`) and a session accessor (`active(session, table)`). Every widget keeps its canonical *values* — the wire format is unchanged — and gains a `format_func` built from the open dataset's map. Tables keep canonical frames and relabel headers with `st.column_config`. Phase 2b does chips, filters, trial sort, figure text and captions.

**Tech Stack:** Python 3.11+, Streamlit 1.6x (`format_func`, `st.column_config`), pandas 3, pytest via `uv run --extra test pytest`, ruff 0.16.3 via `uv run --extra lint ruff`.

**Spec:** [`plans/data-66-original-column-names.md`](data-66-original-column-names.md) §2 (On screen) and the settled defaults; builds on [`plans/data-66-phase-1-column-name-map.md`](data-66-phase-1-column-name-map.md).

## Global Constraints

- Widget **values** stay canonical (`global_color_by`, hover lists, `global_x_field` …) — only `format_func` / headers change. No key in `session_keys.py` changes.
- The computed marker is the text suffix `" (computed)"` — not ⚙: `tests/test_icons.py` forbids literal emoji in chrome, and option text cannot carry a Material icon. (Deviation from the spec's settled default; named in the PR.)
- A dataset with no map (synthetic, authored, a cache from before phase 1) falls back to today's names; computed columns still get their curated label + suffix.
- `uv run` for tests and lint; `(DATA-66)` in commit subjects; no AI co-author trailer.

---

### Task 1: label rules and the session accessor

**Files:**
- Modify: `scanpath_studio/column_names.py`, `scanpath_studio/app.py` (import the key from `column_names`)
- Test: `tests/test_column_names.py`

**Interfaces:**
- Produces:
  - `COMPUTED_SUFFIX = " (computed)"`, `ACTIVE_COLUMN_NAMES_KEY = "_active_column_names"` (moved from `app.py`; `app.ACTIVE_COLUMN_NAMES_KEY` keeps working as an import).
  - `canonical_label(column: str) -> str` — a curated label for an app-made column.
  - `ColumnNames.label(column) -> str`, `ColumnNames.merged(other: ColumnNames) -> ColumnNames` (self wins), `ColumnNames.option_labels(options, extra=None) -> dict[str, str]` (labels made unique), `ColumnNames.sort_options(options, first=()) -> list` (the user's first, computed last, `first` kept at the front).
  - `active(session: Mapping, table: str) -> ColumnNames`.

Label rule: *mapped / composite / converted* → the source name(s); *computed / generated* → `canonical_label(column) + COMPUTED_SUFFIX`; *yours* → the column itself.

- [ ] **Step 1: failing tests** (append)

```python
class TestLabels:
    NAMES = ColumnNames(
        {
            "duration_ms": SourceName(("CURRENT_FIX_DURATION",)),
            "trial_id": SourceName(("TRIAL",)),
            "unique_trial_id": SourceName(("TRIAL",)),
            "fixation_id": SourceName((), cn.GENERATED, "1, 2, …"),
        }
    )

    def test_a_mapped_column_is_labelled_by_its_source(self):
        assert self.NAMES.label("duration_ms") == "CURRENT_FIX_DURATION"

    def test_an_app_made_column_says_so(self):
        assert self.NAMES.label("is_regression") == "Regression (computed)"
        assert self.NAMES.label("fixation_id").endswith(cn.COMPUTED_SUFFIX)

    def test_a_carried_column_keeps_its_name(self):
        assert self.NAMES.label("gpt2_surprisal") == "gpt2_surprisal"

    def test_option_labels_are_unique(self):
        labels = self.NAMES.option_labels(["trial_id", "unique_trial_id"])
        assert len(set(labels.values())) == 2
        assert labels["trial_id"].startswith("TRIAL")

    def test_the_users_columns_come_first_and_computed_last(self):
        ordered = self.NAMES.sort_options(
            ["is_regression", "(uniform)", "duration_ms", "gpt2_surprisal"],
            first=("(uniform)",),
        )
        assert ordered == [
            "(uniform)",
            "duration_ms",
            "gpt2_surprisal",
            "is_regression",
        ]

    def test_merged_prefers_its_own_entries(self):
        words = ColumnNames({"duration_ms": SourceName(("OTHER",))})
        assert self.NAMES.merged(words).label("duration_ms") == "CURRENT_FIX_DURATION"

    def test_active_reads_the_session(self):
        session = {cn.ACTIVE_COLUMN_NAMES_KEY: {"fixations": self.NAMES.to_payload()}}
        assert cn.active(session, "fixations") == self.NAMES
        assert cn.active({}, "fixations") == cn.EMPTY
```

- [ ] **Step 2:** `uv run --extra test pytest tests/test_column_names.py -k TestLabels -q` → FAIL (`AttributeError`).

- [ ] **Step 3: implement** (in `column_names.py`, after `COMPUTED_COLUMNS`)

```python
COMPUTED_SUFFIX = " (computed)"

#: DATA-66: where the open dataset's map lives in session state (stashed by
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


def canonical_label(column) -> str:
    """A readable label for a column the app made (measure, run, angle …)."""
    from .data import READING_MEASURE_FIELDS

    column = str(column)
    for _key, canonical, _short, full, *_ in READING_MEASURE_FIELDS:
        if canonical == column:
            return str(full)
    if column in _CANONICAL_LABELS:
        return _CANONICAL_LABELS[column]
    text = column.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def active(session: Mapping, table: str) -> ColumnNames:
    """The open dataset's map for ``table``, read from a session mapping."""
    stash = session.get(ACTIVE_COLUMN_NAMES_KEY) or {}
    return ColumnNames.from_payload(stash.get(table))
```

Methods on `ColumnNames`:

```python
def label(self, column) -> str:
    """What a person is shown for ``column`` (DATA-66).

    The user's own name when the column was read from their files; a
    curated label marked ``(computed)`` when the app made it; else the
    column's own name.
    """
    entry = self.source(column)
    kind = self.kind_of(column)
    if entry is not None and entry.sources and kind in (MAPPED, COMPOSITE, CONVERTED):
        return entry.display
    if kind in (COMPUTED, GENERATED):
        return canonical_label(column) + COMPUTED_SUFFIX
    return str(column)


def merged(self, other: ColumnNames) -> ColumnNames:
    """Both tables' entries, this map's winning where both name a column."""
    return ColumnNames({**dict(other.entries), **dict(self.entries)})


def option_labels(self, options, extra: Mapping | None = None) -> dict[str, str]:
    """``{option: label}`` for a picker — ``extra`` for synthetic options
    (``"(uniform)"``, ``"line"``). Labels two options share get the internal
    name added, so the picker never shows two identical rows."""
    extra = dict(extra or {})
    labels = {o: extra.get(o) or self.label(o) for o in options}
    seen: dict[str, int] = {}
    for value in labels.values():
        seen[value] = seen.get(value, 0) + 1
    return {
        o: f"{label} · {o}" if seen[label] > 1 and label != o else label
        for o, label in labels.items()
    }


def sort_options(self, options, first=()) -> list:
    """The user's columns first, the app's last; ``first`` stays in front.
    Stable within each group, so a curated order survives."""
    options = list(options)
    head = [o for o in options if o in first]
    rest = [o for o in options if o not in first]
    mine = [o for o in rest if self.kind_of(o) not in (COMPUTED, GENERATED)]
    made = [o for o in rest if self.kind_of(o) in (COMPUTED, GENERATED)]
    return head + mine + made
```

In `app.py`: replace the `ACTIVE_COLUMN_NAMES_KEY = "_active_column_names"` definition with an import (`from scanpath_studio.column_names import ACTIVE_COLUMN_NAMES_KEY, ColumnNames, from_schema`) and make `active_column_names(table)` return `column_names.active(st.session_state, table)`.

- [ ] **Step 4:** `uv run --extra test pytest tests/test_column_names.py -q` → all pass.
- [ ] **Step 5:** lint; `git commit -m "Label a column by its name in the user's files (DATA-66)"`.

---

### Task 2: the plot rail's pickers

**Files:**
- Modify: `scanpath_studio/controls.py` — the six pickers: *Color fixations by* (~L5244), fixation *Hover fields* (~L5521), word *Hover fields* (~L6063), *Highlight words by* (~L5886), heatmap *Metric* (~L6166), *X/Y axis field* (~L6474–6489).
- Test: `tests/test_column_names.py` (AppTest)

**Interfaces:** Consumes `column_names.active`, `ColumnNames.option_labels/sort_options/merged`. Adds `controls._rail_names()`.

- [ ] **Step 1: failing AppTest** (append)

```python
@pytest.mark.timeout(180)
def test_the_rail_shows_the_demos_own_column_names(demo_raw):
    from tests.conftest import APP_SCRIPT

    _, fixations = demo_raw
    duration = data.propose_fix_schema(fixations)["duration"]
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    color = at.selectbox(key="global_color_by")
    assert duration in color.options, color.options
    assert "duration_ms" not in color.options
    hover = at.multiselect(key="global_fixation_hover_fields")
    assert duration in hover.options
    assert any(o.endswith(cn.COMPUTED_SUFFIX) for o in hover.options)
    # Values stay canonical: the wire format is unchanged.
    assert at.session_state["global_color_by"] in ("(uniform)", "duration_ms") or (
        "_" in at.session_state["global_color_by"]
    )
```

(AppTest exposes the *formatted* options, which is what is asserted.)

- [ ] **Step 2:** run → FAIL (options show `duration_ms`).

- [ ] **Step 3: implement.** Add near the top of the rail helpers in `controls.py`:

```python
def _rail_names() -> ColumnNames:
    """DATA-66: the open dataset's names for the rail — the fixations table's,
    then the words table's for the word-level fields merged onto fixations."""
    return cn.active(st.session_state, "fixations").merged(
        cn.active(st.session_state, "words")
    )
```

(imports: `from scanpath_studio import column_names as cn` and `from scanpath_studio.column_names import ColumnNames`.)

Then at each picker, compute labels from its options and pass `format_func`; reorder the options with `sort_options` where the list is not curated-first:

```python
        names = _rail_names()
        color_fields = names.sort_options(color_fields, first=(UNIFORM_COLOR_FIELD,))
        color_labels = names.option_labels(
            color_fields,
            {UNIFORM_COLOR_FIELD: UNIFORM_COLOR_FIELD, "line": "Line" + cn.COMPUTED_SUFFIX},
        )
        color_by = by_col.selectbox(
            "Color fixations by",
            options=color_fields,
            format_func=color_labels.__getitem__,
            ...  # every other argument unchanged
        )
```

The same pattern for the others (use `cn.active(st.session_state, "words")` for the word hover and highlight pickers):

```python
        fix_hover = hover_field_options(trial_fixations)
        fix_hover_labels = _rail_names().option_labels(fix_hover)
        _labeled(..., options=_rail_names().sort_options(fix_hover),
                 format_func=fix_hover_labels.__getitem__, ...)
```

```python
        metric_labels = _rail_names().option_labels(
            ["duration_ms", "counts"], {"counts": "Fixation count"}
        )
        heatmap_metric = metric_col.selectbox("Metric", options=["duration_ms", "counts"],
            format_func=metric_labels.__getitem__, ...)
```

```python
        axis_labels = _rail_names().option_labels(numeric_fields)
        axes_cols[2].selectbox("X axis field", options=numeric_fields,
            format_func=axis_labels.__getitem__, ...)   # and the Y one
```

If `_labeled` does not forward `format_func`, check its signature — it passes `**kwargs` to the widget; if it does not, add `format_func` to what it forwards.

- [ ] **Step 4:** `uv run --extra test pytest tests/test_column_names.py tests/test_widget_value_sync.py tests/test_plot_config_restore.py tests/test_viz_palette.py -q -n 4` → pass. A test that asserts a raw option name in a rail picker (e.g. `"duration_ms" in options`) is now asserting the old display: update it to compare the widget's **value** (`at.session_state[key]`) or the formatted label, never weaken what it checks.
- [ ] **Step 5:** lint; commit `"Show the dataset's own names in the plot rail's pickers (DATA-66)"`.

---

### Task 3: the Data Management tables

**Files:**
- Modify: `scanpath_studio/tabs.py` — `_render_raw_table` (~L10287) and its callers `render_fixations_tab`, `render_words_tab`, `render_raw_gaze_tab`.
- Test: `tests/test_column_names.py`

**Interfaces:** Produces `tabs.column_label_config(columns, names) -> dict` (`{column: st.column_config.Column(label=…)}` for every column whose label differs).

- [ ] **Step 1: failing test**

```python
def test_a_table_header_shows_the_users_name():
    from scanpath_studio import tabs

    names = ColumnNames({"duration_ms": SourceName(("CURRENT_FIX_DURATION",))})
    config = tabs.column_label_config(["duration_ms", "my_extra"], names)
    assert set(config) == {"duration_ms"}
    assert config["duration_ms"]["label"] == "CURRENT_FIX_DURATION"
```

(`st.column_config.Column(...)` returns a dict — the assertion reads its `label`.)

- [ ] **Step 2:** run → FAIL.

- [ ] **Step 3: implement**

```python
def column_label_config(columns, names: ColumnNames) -> dict:
    """DATA-66: header labels for a table of canonical columns — the user's
    own names, and the app's columns marked — leaving the frame canonical so
    sorting and the lazy stream are untouched."""
    labels = names.option_labels(list(columns))
    return {
        column: st.column_config.Column(label=label)
        for column, label in labels.items()
        if label != column
    }


def _render_raw_table(
    df: pd.DataFrame, caption: str | None = None, *, table: str | None = None
) -> None:
    ...  # docstring unchanged
    shown = drop_internal_columns(df)
    names = cn.active(st.session_state, table) if table else cn.EMPTY
    st.dataframe(
        shown,
        hide_index=True,
        width="stretch",
        lazy=True,
        column_config=column_label_config(shown.columns, names),
    )
```

Callers pass `table="fixations"`, `"words"`, `"raw_gaze"` respectively.

- [ ] **Step 4:** run the test and `tests/test_dataset_overview.py tests/test_apptest.py -q -n 4` → pass.
- [ ] **Step 5:** lint; commit `"Head the Data Management tables with the dataset's own names (DATA-66)"`.

---

### Task 4: the add wizard and ✏️ Edit dataset speak the user's names

**Files:**
- Modify: `scanpath_studio/wizard.py` — `_wizard_table_keep_picker` (~L1598: `labels[src] = d["dest"]`).
- Modify: `scanpath_studio/controls.py` — `column_mapping_ui` gains `option_labels: Mapping[str, str] | None = None`, used as `format_func` on its selectbox (~L2811) and multiselect (~L3026), and in the "currently mapped `…`" note.
- Modify: `scanpath_studio/tabs.py` — the remap editor's `_cell` (~L12157) passes `option_labels` built from the stored entry's map for a stored table.
- Test: `tests/test_column_names.py`

- [ ] **Step 1: failing tests**

```python
def test_the_keep_picker_lists_the_files_own_names(monkeypatch):
    """The add screen used to show `total_fixation_duration_ms` for a column the
    file calls `IA_DWELL_TIME` — before anything had been normalized."""
    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT

    words = _UPLOAD_WORDS.assign(IA_FIRST_FIXATION_DURATION=[1.0, 2.0, 3.0])
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {
            "col_map_words": words,
            "col_map_fix": _UPLOAD_FIXATIONS,
        }.get(kw["state_prefix"], pd.DataFrame()),
    )
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.run(timeout=180)
    assert not at.exception, at.exception
    keep = at.multiselect(key="wizard_keep_col_map_words")
    assert not any("_ms" in o for o in keep.options), keep.options


def test_the_edit_screen_offers_columns_by_their_users_names():
    from scanpath_studio import controls

    names = ColumnNames({"duration_ms": SourceName(("CURRENT_FIX_DURATION",))})
    labels = names.option_labels(["duration_ms", "x"])
    assert labels["duration_ms"] == "CURRENT_FIX_DURATION"
    assert "option_labels" in controls.column_mapping_ui.__code__.co_varnames
```

(If the keep picker's multiselect key differs, read it from `_wizard_table_keep_picker` — `f"wizard_keep_{prefix}"` with the words prefix the wizard passes.)

- [ ] **Step 2:** run → FAIL.

- [ ] **Step 3: implement**
  - `wizard.py`: `labels[src] = src` (the file's own name; the comment says why — DATA-66).
  - `controls.column_mapping_ui`: new keyword `option_labels: Mapping[str, str] | None = None`; define once `_label = (lambda c: option_labels.get(c, c)) if option_labels else (lambda c: c)`; pass `format_func=_label` to the field selectbox and the Trial ID multiselect; where the ✨ note formats the detected default, wrap it in `_label(...)`.
  - `tabs` remap `_cell`: for a stored table (not an added one), `option_labels=ColumnNames.from_payload((stored.get("column_names") or {}).get(table_key)).option_labels(user_columns(frames[table_key]))`.

- [ ] **Step 4:** run the tests plus `tests/test_remap.py tests/test_dataset_editor_parity.py tests/test_mapping_dataset_scope.py tests/test_broken_mapping_recovery.py -q -n 4` → pass.
- [ ] **Step 5:** lint; commit `"Name columns by the file's own names on the add and edit screens (DATA-66)"`.

---

### Task 5: changelog, docs, verify, review

- [ ] `changelog.d/DATA-66.changed.md`: `The plot controls, the Data Management tables and the dataset setup screens now name each column as it is in your files, and mark the columns Scanpath Studio computed.`
- [ ] `docs/guides/loading-data.md`: one sentence under *The Data Management page*: tables and pickers use your own column names; a column marked *(computed)* is one the app made.
- [ ] Full suite `uv run --extra test pytest -n auto -q`; ruff check + format.
- [ ] Live check in the app (demo): the rail's pickers and the Fixations table header show `CURRENT_FIX_*` names.
- [ ] `surface-parity-reviewer` + `perf-reviewer` on the diff (read-only, no server, `SCANPATH_STUDIO_PERSIST=0`).
- [ ] Commit; PR referencing #322; issue stays *In progress* until phase 4.

## Self-review

- Spec §2 coverage in 2a: pickers (Task 2), tables (Task 3), wizard + editor (Task 4), computed marked (Task 1 rule). Deferred to 2b, by name: chips and the chip picker, trial filters, trial sort, Stimulus & Context fields, Comparisons match field, Corpus Analysis group/sentence pickers, figure text (`FigureSettings.column_labels`), captions.
- Wire values unchanged: every change is a `format_func` or a header label.
- Names used: `cn.active`, `ColumnNames.label/merged/option_labels/sort_options`, `canonical_label`, `COMPUTED_SUFFIX`, `ACTIVE_COLUMN_NAMES_KEY`, `tabs.column_label_config`, `column_mapping_ui(option_labels=)` — consistent across tasks.
