# DATA-22 · Rebuild the data-upload pipeline

> **Status: Design, awaiting approval 2026-08-12.**
> Design doc for the [improvements tracker](../tracker/index.html) → **DATA-22**. It
> supersedes **DATA-19** (whose one-shot `_wizard_keep_open` marker is the mechanism
> being deleted) and should close it as *superseded* rather than approved.

## Context

The generic upload flow is one 620-line function,
[`_render_data_setup`](../scanpath_studio/wizard.py) (wizard.py:1119), rendering **16
expanders** across five numbered subsections on a single page, beneath a three-step
progress bar ([`_render_wizard_progress`](../scanpath_studio/wizard.py), wizard.py:902)
whose steps match neither the subsections nor the expanders. Four concrete failures:

1. **Steps collapse mid-edit.** `_wizard_step_expanded` (wizard.py:228) flips `expanded`
   `True→False` the instant `done` flips — and `done` is true after the *first* pick,
   via `mapped()` reading the `col_map_*` key as truthy. DATA-19's `_wizard_keep_open`
   marker survives exactly one rerun, so any second rerun re-collapses.
2. **The guide points at nothing.** `render_spotlight_wizard_guide` (tour.py:1519)
   documents its own gap: *"No backdrop / highlight / scroll — the steps are
   descriptive, not anchored to specific controls."* The welcome tour's
   selector-highlight and scroll-into-view machinery sits 800 lines above it in the
   same module (tour.py:650) and is not reused.
3. **Silent work.** `_trial_id_values`, `_distinct_id_count`, `propose_*_schema`,
   `categorize_columns` and `aggregate_char_boxes` all recompute uncached on every
   keystroke with no spinner. Only `read_table` and `_normalize_pair_cached` carry one.
4. **Assumed experimental setup.** For an upload, `seed_canvas_state` hard-codes a
   2560×1440 monitor (app.py:2170) plus 597 mm / 800 mm / 16 px (app.py:2239), with
   nothing telling the user those are guesses — and the panel renders as wizard *step
   2*, before the upload, so estimating from the data is not even possible.

The target user either collected the data (knows it well, not every detail by heart)
or merely uses it (knows much less). Either way they may not have the numbers to hand,
so the design must never silently substitute a plausible default.

## Confirmed decisions (with the user)

- **Navigation:** accordion stepper on one page, not a paged wizard. Every mapping
  widget keeps rendering each run, so no Streamlit state loss.
- **Experimental setup:** forced conscious choice per group, **blocking Add dataset**.
- **Scope:** the *generic* upload flow. MultiplEYE is adapted into the new shell, not
  rebuilt; public-dataset loaders and the Data Inspection remap editor are untouched.
- **Restore counts as an answer:** the setup JSON grows an optional `experimental_setup`
  section (choice + values + provenance). Additive, so per ENG-11 no
  `PLOT_CONFIG_SCHEMA` bump.
- **The gate stays hard** — no "decide later" escape. *Estimate from my data* is always
  available and always succeeds, so nobody is stuck; they just cannot proceed without
  saying which of the three they meant.
- **Provenance travels everywhere** (see *§7 Wire format*).
- **Answers are recalled across datasets as pre-filled values with the radio reset.**

## Streamlit facts this design rests on (verified, not assumed)

`st.expander` gained `key`, `on_change` and an `.open` property. Probed directly:

- With `key=` alone, `.open` is `None` — *state tracking is off*. The frontend keeps
  its own open state while session state keeps another, so a user's manual collapse is
  not recorded and the next rerun re-opens it. **`on_change="rerun"` is required.**
- With `key=` + `on_change="rerun"`, `.open` mirrors the session key, a programmatic
  write moves the expander, and **the open state survives a widget edit inside it**.
- `st.radio(..., index=None)` renders with nothing preselected and returns `None`.
- `st.popover` nests inside a keyed expander (expander-in-expander is still forbidden).
- `AppTest` exposes no expander accessor (`at.expander` is always `[]`), so tests drive
  `session_state["wiz_open_*"]` directly.

**Do not gate step bodies on `expander.open`.** A widget that does not render loses its
session key at end of run, and `controls.column_mapping_ui` builds every `col_map_*`
widget without `persist_state` — a collapsed step would silently drop its mapping.
Collapsed-but-rendered is correct.

## 1. New module `scanpath_studio/wizard_shell.py`

Step registry, status, accordion, progress and navigation. No knowledge of columns or
dataframes; `wizard.py` keeps the step bodies and finalize.

```python
class StepStatus(Enum):
    DONE = "done"        # ✅ satisfied
    ACTION = "action"    # ⚠️ required and currently blocked
    TODO = "todo"        # ⬜ required, not started
    OPTIONAL = "optional"  # ➖ optional, untouched

@dataclass(frozen=True)
class WizardStep:
    id: str
    number: int
    title: str
    caption: str
    required: bool

STEPS: tuple[WizardStep, ...] = (
    WizardStep("data",     1, "Your data",         "The tables you exported",             True),
    WizardStep("identity", 2, "Trials & readers",  "Which columns identify a trial",      True),
    WizardStep("geometry", 3, "Fixations & text",  "Where the eyes landed, where words are", True),
    WizardStep("setup",    4, "Recording setup",   "The screen and font it was recorded on", True),
    WizardStep("fields",   5, "Extra fields",      "What else to carry along",            False),
    WizardStep("review",   6, "Name & add",        "Check it over and add the dataset",   True),
)
```

Public API:

```python
def open_key(step_id) -> str                     # "wiz_open_<id>" — never a col_map_* prefix
def seed_open_step(statuses) -> None             # once per wizard entry, first non-DONE step
def go_to_step(step_id) -> None                  # on_click callback: closes others, opens one
def render_progress(host, statuses) -> None      # bar + clickable status chips
def step_panel(host, step, status, *, active) -> DeltaGenerator
def continue_button(host, step, *, label="Continue →") -> None
```

`step_panel` renders `host.expander(f"{n}. {title}", key=open_key(id), icon=badge,
on_change="rerun")` when `active`; when `active=False` (the collapsed *Data & mapping*
review panel, itself an expander) it degrades to `host.markdown(f"**{n}. {title}**")`
and returns `host` — preserving today's inline behaviour and the `wizard_reconfigure`
assertion in `tests/test_apptest.py`.

**`wiz_open_*` is written only by `go_to_step`, `seed_open_step`, `continue_button`, the
progress chips, and the guide.** Nothing inside a step body may touch it. That single
rule is the fix for failure (1).

## 2. Step bodies (`wizard.py`)

**1 · Your data.** Dataset-format control (`Generic | MultiplEYE`) at the top; MultiplEYE
branches to the existing `_render_multipleye_upload` wrapped in the new shell's header
and progress. Then the fixations and words/IA upload boxes with row counts, column
counts and first-rows previews; *Restore a saved setup* and *Raw gaze overlay* as
popovers. Privacy caption and the run-locally tip keep their current always-rendered
container (BUG-2: a conditional child here shifts the element tree mid-parse and leaves
a ghost DOM).

New: an **auto-detect summary card** after upload — ✓ per required field detected,
⚠️ per field still missing, naming the source column each time. When everything required
detects, a **"Everything needed was detected — jump to Recording setup"** button skips
steps 2 and 3. It lands on step 4, not step 6: the recording setup is precisely the part
that cannot be auto-answered.

**2 · Trials & readers.** Trial ID (required), participant, text — the existing unified
picker plus per-table override, unchanged in behaviour. The three separate
`success`/`info`/`warning` count callouts collapse into one readout: *N trials · N
readers · N texts*, with the cross-table coverage warning kept for the disjoint case.
Filename id-derivation and multipart screens move into an **⚙️ Advanced** popover.

**3 · Fixations & text.** Two labelled sub-blocks — *Fixations* (x, y, duration,
fixation id) and *Words / Interest Areas* (word id, text, box) — each with an **⚙️
Advanced** popover holding what are today the *More … mappings* expanders (word id,
timestamp; line index, char-AOI aggregation). Raw-gaze mapping renders here only when a
raw-gaze file was uploaded. Validation problems render against their own sub-block
rather than as one lumped warning above the Add button.

**4 · Recording setup.** See §3.

**5 · Extra fields.** `_wizard_keep_and_filter` unchanged, plus a one-line explanation of
what each picker feeds and the existing `wide_frame_warning`.

**6 · Name & add.** Dataset name moves here from step 1 — you name a thing once you know
what it is. A **review table**: every decision, its value, and its provenance. Remaining
blockers list with a *Go to step N* button each. Then Download setup and Add dataset.

## 3. Experimental setup provenance (`experimental_setup.py`)

The module is 30 lines of pure math today; it grows the pure model. No Streamlit.

```python
class Provenance(StrEnum):
    MEASURED  = "measured"   # user knows the values, or the corpus declares them
    ESTIMATED = "estimated"  # derived from the uploaded data
    ASSUMED   = "assumed"    # a named default
    SKIPPED   = "skipped"    # declined; everything derived from it is hidden

@dataclass(frozen=True)
class SetupAnswer:
    group: str                    # "screen" | "geometry" | "text"
    choice: str
    provenance: Provenance
    values: dict[str, float | str]
```

Three groups, each an `st.radio(index=None)` — nothing preselected:

| Group | Choices | Provenance |
| --- | --- | --- |
| **Screen** — how big was the display? | `I know the resolution` → w/h px · `Estimate from my data` — `data.compute_canvas_size(words, fixations)` (data.py:2417), shown as a number and stated to be a **lower bound**, since text rarely fills the screen · `Use a common default (2560×1440)` | measured / estimated / assumed |
| **Physical size & viewing distance** | `I know them` → mm + mm, shows px/degree · `Use typical lab values (597 mm / 800 mm)` · **`Skip — I don't need visual-angle units`** | measured / assumed / skipped |
| **Reading text size** | `Scale to the word boxes` (offered only when boxes exist) · `I know the stimulus font` → pt + family · `Use a default (16 px)` | measured / measured / assumed |

Screen has no *Skip*: the canvas size is structural, and *Estimate from my data* already
**is** the skip — it always succeeds, so the hard gate can never strand anyone.

Under `SKIPPED` geometry, the px/degree caption and the pt→px conversion are **hidden**,
not computed from a default. `global_use_stimulus_font_pt` is disabled with a reason
pointing back at the group.

Session keys `wizard_setup_{screen,geometry,text}_mode` are wizard-local UI state and
deliberately **not** wire format (same reasoning as `share_identity_mode` in
`url_state.py`). The *values* they produce — `global_canvas_width`,
`global_monitor_width_mm`, `global_base_font_size`, … — are already wire format and are
unchanged. Recall across datasets writes `_wizard_setup_recall` (values only); the radio
always resets to `index=None`.

Add dataset is disabled until all three groups are answered, listing which are open.

## 4. A guide that follows (`tour.py`)

Factor two helpers out of `render_spotlight_tour` (tour.py:650), leaving its behaviour
byte-identical:

```python
def _highlight_css(selector: str, accent: str) -> str     # outline + tour-pulse keyframes
def _scroll_into_view_script(selector: str, *, in_sidebar: bool) -> str
```

`_WIZARD_GUIDE_STEPS` becomes records carrying `selector` and `step_id`. Keyed expanders
supply `.st-key-wiz_open_<id>` for free, so step-level targets need no new wrapper
containers; finer targets reuse existing widget keys (`.st-key-wizard_finalize`,
`.st-key-col_map_fix_upload`, …) and only genuinely unkeyed regions get a container.
Guide **Next** also calls `wizard_shell.go_to_step(step_id)`, so the card drives the
wizard instead of narrating beside it.

The card keeps its own `wizard_guide_step` counter and `tour_mode == "wizard"`, and the
`_dismiss_listener_script` instant-hide is unchanged.

## 5. Progress feedback

Header: `render_progress` draws a six-step bar plus a chip row (`✅ 1 Your data ·
⚠️ 2 Trials & readers · …`), each chip a `go_to_step` button.

Per-rerun recomputation gets `@st.cache_data`, keyed on `data.frame_fingerprint` plus
the mapping signature, each with the house `show_spinner="…"` label:

| helper | today | cached label |
| --- | --- | --- |
| `_trial_id_values` / `_distinct_id_count` | uncached `nunique` over the whole frame, every keystroke | `"Counting trials…"` |
| `propose_word_schema` / `propose_fix_schema` / `propose_raw_gaze_schema` | uncached, every rerun | `"Detecting columns…"` |
| `categorize_columns` (per table) | uncached, every rerun | `"Scanning fields…"` |
| `aggregate_char_boxes` | uncached, runs before every normalize when toggled | `"Aggregating character boxes…"` |

Finalize itself is **cheap** — the payload is already normalized at render time, so
`_finalize_wizard_dataset` only stores a dict and switches source. The cost is the
*next* run's first figure, which already has the `_wizard_finalizing` bridge
(app.py:2959); it keeps its skeleton and gets honest wording. Wrapping finalize in
`st.status` would be theatre for work that is not happening there.

## 6. What gets deleted

`_wizard_step_expanded`, `_keep_wizard_step_open`, the `_wizard_keep_open` key,
`flow["claimed"]`, `_render_wizard_progress`, `_wizard_problems_last`, and the
`toggle()` / `subsection()` closures inside `_render_data_setup`.

## 7. Wire format and the four surfaces

Provenance is metadata *about* settings, not a new setting, so it rides the surfaces
where a recipient would otherwise be misled, and no further (YAGNI — a `render` flag or
a builder argument would take input that changes no figure):

1. **UI** — Review-step table, wizard badges, and a line in Data Inspection → *Column
   mapping*, which is where someone checks what the app did with their data.
2. **Deep link / Share** — a compact `setup_prov=screen:assumed,geom:skipped,text:measured`
   param. `_build_share_query` emits it when the active source is a wizard dataset;
   `_apply_url_preset` parses it (unknown groups ignored, unknown provenance dropped)
   and badges the assumed values on arrival. Needs a `session_keys.py` constant and a
   pin in `tests/test_session_key_contract.py`.
3. **Save & restore JSON** — an optional `experimental_setup` section, written by both
   `tabs._build_studio_config` and `wizard._wizard_setup_config` (which share the
   format). Additive; the reader already tolerates absent sections, so per ENG-11 this
   is a documented no-op migration and `PLOT_CONFIG_SCHEMA` stays at 2.
4. **Bulk export** — the same section in the `plot_config.json` that export already
   writes beside `coloring.drift_correction`, so an exported figure set records that its
   monitor size was assumed.

The stored dataset payload (`_wizard_finalize_payload` → `st.session_state["_datasets"]`)
gains `setup_provenance`, alongside `schemas` and `dropped_columns`.

## 8. Compatibility to preserve

- Every `col_map_*` widget key — `tabs._collect_column_mapping` sweeps the whole prefix
  into the saved config, and `url_state._seed_column_mapping` reads it back. Accordion
  keys are named `wiz_open_*` to stay clear of that sweep.
- `_wizard_finalize_payload` shape and the `on_click` finalize callback (an inline
  `if button:` handler is swallowed by a live `st.file_uploader` rerun — wizard.py:165).
- The `app._read_uploaded_frame` seam, monkeypatched by every AppTest.
- `wizard_dataset_name`, `wizard_filter_fields`, `wizard_keep_extra`, `wizard_filter_by`,
  `wizard_aggregate_char_boxes`, `_composite_trial_columns`.
- `persistence.py`'s recovery cache reads `_datasets` — the new payload key must survive
  a Parquet + manifest round-trip.

## 9. Tests

- `tests/test_wizard_helpers.py` — replace the two `_wizard_step_expanded` tests with
  step-status computation, `first_incomplete` seeding, and `go_to_step` exclusivity.
- **New (the regression that started this):** an AppTest that opens step 2, changes the
  trial-id multiselect, and asserts `session_state["wiz_open_identity"]` is still `True`
  — plus a second edit, since the DATA-19 mechanism survived exactly one.
- **New:** `wizard_finalize` is disabled until all three setup groups are answered, and
  enabled once they are.
- **New:** restoring a setup JSON with an `experimental_setup` section pre-answers step 4.
- **New:** the review table reports `assumed` for a default-taken group and `skipped`
  hides the px/degree caption.
- **New:** `setup_prov` round-trips through `_build_share_query` → `_apply_url_preset`.
- ~10 existing AppTests click `wizard_finalize` immediately and must answer the setup
  step first; a shared `conftest` helper (`answer_setup_step(at)`) keeps that to one line
  each.
- `tests/test_session_key_contract.py` gains the `setup_prov` pin.

## 10. Risks

- **State loss if a step body is ever made lazy.** Guarded by the §Streamlit-facts note;
  worth a comment at the `step_panel` call site.
- **`on_change="rerun"` makes every open/close a full app rerun.** The wizard body is
  ~40 widgets and no uncached frame work after §5, so this should stay well under the
  perceptible threshold — but it is the thing to measure first if the wizard feels slow.
- **Scope creep via provenance.** Surface 2 and 4 are the ones that can grow teeth;
  keep them to a string per group and resist making them configurable.
