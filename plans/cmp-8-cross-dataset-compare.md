# CMP-8 · Compare scanpaths across datasets

> **Status: implemented 2026-08-12** — design doc for the
> [improvements tracker](../tracker/index.html) → **CMP-8** ("Compare scanpaths
> across datasets"), now in *Review*. All six scoping calls were settled before
> implementation (three on 2026-08-12 in chat, three from the item's
> *Instructions for implementation*).
>
> **Three things the implementation had to decide differently**, recorded here so
> the doc doesn't contradict the code:
>
> 1. **§7 was bigger than stated.** This doc says "the share link already names
>    B's exact (participant, trial)". It does not — compare mode had *no* link
>    representation at all (Animate has `?tab=animation`; Compare had nothing).
>    A `cmp_source` on its own would have pinned a wire-format param that
>    restores nothing, so `compare=<participant>:<trial>` ships with it. That
>    makes same-dataset compare shareable for the first time as a side effect.
> 2. **Overlay is gated with a caption, not a disabled option.** Streamlit's
>    `st.segmented_control` has no per-option disable, so all three options stay
>    and the resolve explains itself inline. The rule the doc actually cares
>    about — resolve without rewriting `single_compare_layout` — holds.
> 3. **Animate + Compare is gated too**, which §5.3 doesn't mention: a dual
>    animation co-animates both scanpaths on one clock, i.e. an overlay, so it
>    hits the same one-coordinate-space problem. It replays A alone with a
>    warning.
>
> §10's live cross-corpus check (demo vs. PoTeC) is **not** done — PoTeC isn't
> present in this checkout and the preview harness can't launch the app. Covered
> by `tests/test_compare_cross_dataset.py` plus a demo-vs-synthetic AppTest flow.

## Context

Compare mode picks scanpath **B** out of the *same* loaded dataset as scanpath
**A**. `tabs._build_compare_meta` ([tabs.py:2127](../scanpath_studio/tabs.py:2127))
extracts B with `utils.extract_trial(words_filtered, …)`, and
`utils.build_comparison_options` ([utils.py:1157](../scanpath_studio/utils.py:1157))
enumerates candidates from the one `combos` frame `app.main` built. There is no
way to put a reader from one corpus next to a reader from another — the same text
read under two corpora, or a PoTeC reader against a OneStop reader.

The hard part is not the picker. It is that a *dataset* carries a coordinate
space (screen pixels on a specific monitor), a stimulus layout, an experimental
setup (monitor mm + viewing distance), and a column set — and Scanpath Studio
holds exactly one of each, globally, in `global_*` session keys.

**What makes this tractable** is that three seams already exist:

1. **Split layouts already reconcile nothing.** `plots._make_split_comparison_figure`
   ([plots.py:4532](../scanpath_studio/plots.py:4532)) computes `_compute_axis_ranges`
   **per panel**, from that trial's own words + fixations. Side-by-side and stacked
   therefore tolerate two coordinate spaces today; only the shared
   `canvas_width`/`canvas_height` and the single `background_image` are global.
   Overlay ([plots.py:5068](../scanpath_studio/plots.py:5068)) pools both trials
   into one range — that is the layout that genuinely needs a normalization step.
2. **The two scanpaths are already separate frames until the last moment.**
   `tabs.py` builds `cmp_words` / `cmp_fixations` by concatenating A's and B's
   single-trial frames right before the builder
   ([tabs.py:3383-3390](../scanpath_studio/tabs.py:3383)). That concat is the
   merge point; nothing upstream of it has to become dataset-aware.
3. **Per-dataset monitors are already declared** for built-in corpora —
   `PUBLIC_DATASET_REGISTRY[...]["monitor"]` ([app.py:1292](../scanpath_studio/app.py:1292))
   and the OneStop/demo 2560×1440 and MultiplEYE 1920×1080 branches in
   `app.seed_canvas_state` ([app.py:2144-2174](../scanpath_studio/app.py:2144)).
   What is missing is a *snapshot* per **uploaded** dataset, and a way to read
   either without switching the app to that source.

## Confirmed decisions

Settled with the user in chat, 2026-08-12:

1. **Split layouts only** in this first cut. Side-by-side and stacked; overlay
   renders disabled with a reason, and the normalization work (visual angle /
   text-box fit) is split out as **CMP-11**.
2. **B may come from any source**, not just stored uploads — via a cached,
   widget-free secondary loader, subject to the readiness gate in §2.
3. **Experimental setup is snapshotted per dataset**, not made globally
   per-dataset-editable. Each dataset records the canvas/monitor/typography it
   was set up with; the Experimental Setup panel keeps editing the *active*
   dataset only, and the compare figure reads B's snapshot for B's panel.

Settled in the tracker item's *Instructions for implementation*, 2026-08-12:

4. **B gets its own filter set**, scoped to B's dataset — not A's filters
   applied to a corpus that may not share their columns, and not "B is
   unfiltered". This is the one answer that grew the plan; see §5.2.
5. **A cross-dataset pair is exportable.** Both the figure and a reproducible
   two-trial data bundle; see §6.
6. **No hard cap on resident datasets** (user's call, left to implementation).
   Taken as: one live secondary slot, evicted when the picker changes, with
   `@st.cache_data` doing the rest — a ceiling that falls out of the UI rather
   than a number to tune. See §2.

## Non-goals

- Overlay across datasets, in any normalization space (→ **CMP-11**).
- **Bulk** export over cross-dataset *pairs*. Bulk iterates a trial list; pairing
  two corpora needs a pairing rule (by text? by reader index?), which is a
  feature of its own. §6 covers the pair on screen, not a batch of pairs.
- Cross-dataset **Corpus Analysis**, group comparison, or the Comparisons →
  Generations subtab (which is same-text-within-one-dataset by construction).
- Cross-dataset similarity/NLD scoring. `similarity.ordered_word_ids` compares
  word-id sequences, which only align when two corpora tokenize a text
  identically — an assumption this item does not want to make. (CMP-10 already
  removed the similarity sorts from the compare picker, so nothing regresses.)
- Renaming or namespacing `participant_id` anywhere but the throwaway compare
  frames — annotations, export slugs and deep links all key on the real ids.

## 1. Per-dataset setup snapshot (prerequisite)

A dataset must be able to state its own geometry without being the active source.

**Home for the type: `experimental_setup.py`**, not `app.py`. DATA-2 already left
a pure, Streamlit-free 30-line module there holding `dpi_from_width`,
`font_pt_to_px` and `pixels_per_degree` — the snapshot is the value those
conversions apply to, and keeping it there means the headless API and CMP-11's
visual-angle mode can use it without importing `app`.

```python
# experimental_setup.py
@dataclass(frozen=True)
class SetupSnapshot:
    canvas_width: int
    canvas_height: int
    monitor_width_mm: float
    viewing_distance_mm: float
    base_font_size: int
    font_family: str
    line_spacing: float
    scale_text_to_boxes: bool

    @property
    def dpi(self) -> float: ...          # dpi_from_width(canvas_width, monitor_width_mm)
    @property
    def px_per_degree(self) -> float: ...  # pixels_per_degree(...)

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: Mapping, *, fallback: "SetupSnapshot") -> "SetupSnapshot": ...
```

`from_dict` takes a `fallback` on purpose: a recovery cache or stored dataset
written by an older build has no snapshot, and the read path must degrade rather
than raise.

**Extract the source→monitor table.** `app.seed_canvas_state` currently inlines
the branch that maps a `data_choice` to a monitor
([app.py:2144-2174](../scanpath_studio/app.py:2144)). Lift it to

```python
# app.py — Streamlit-side, because it reads the public-dataset registry
def resolve_source_monitor(
    data_choice: Optional[str],
    words: pd.DataFrame,
    fixations: pd.DataFrame,
) -> Tuple[int, int, bool]:      # (width, height, authoritative)
```

and have `seed_canvas_state` call it, so there is one table, not two.
`authoritative` keeps its current meaning: the source declares a real
presentation monitor, so the canvas should snap to it rather than to data-derived
extents (`data.compute_canvas_size`, [data.py:2417](../scanpath_studio/data.py:2417)).

**Capture and store.** `app.capture_setup_snapshot() -> SetupSnapshot` reads the
resolved `global_*` values — reuse the `defaults` table `seed_canvas_state`
already resolves ([app.py:2236](../scanpath_studio/app.py:2236)); do not restate
the key list. Both `_wizard_finalize_payload` writers gain
`"setup": capture_setup_snapshot().to_dict()` — the generic flow
([wizard.py:1716](../scanpath_studio/wizard.py:1716)) and the MultiplEYE branch
([wizard.py:1092](../scanpath_studio/wizard.py:1092)). Stored datasets today
carry `words / fixations / raw_gaze / filter_fields / composite_trial_columns /
schemas / dropped_columns` and no geometry at all, which is why this is a
prerequisite rather than a detail.

**Persist it.** `persistence.py` mirrors `_datasets` to the ENG-26 recovery cache;
the manifest writer must round-trip the new `setup` key, and an older cache
without it falls back through `SetupSnapshot.from_dict(..., fallback=…)`.

**Independently useful.** Even without CMP-8, this fixes the current behaviour
where switching to a stored upload leaves the canvas on the *previous* source's
monitor (the `_canvas_seeded_for` snap at [app.py:2190](../scanpath_studio/app.py:2190)
only fires for authoritative built-ins). Land §1 on its own if CMP-8 stalls.

## 2. Secondary dataset loading

```python
@dataclass(frozen=True)
class SecondaryDataset:
    name: str                 # display name, also the compare-label prefix
    words: pd.DataFrame       # normalized
    fixations: pd.DataFrame   # normalized
    combos: pd.DataFrame      # its own build_combo_options output
    setup: SetupSnapshot      # §1
```

```python
def secondary_dataset_options() -> list[tuple[str, bool, str]]   # (name, ready, why_not)
def load_secondary_dataset(name: str) -> Optional[SecondaryDataset]
```

**It must not render.** This is the one hard constraint. The public-corpus
loaders draw directory inputs, Expected-files layouts and ⬇ Download buttons
(`app._load_public_dataset`, [app.py:1333](../scanpath_studio/app.py:1333)) — none
of that can appear inside the compare picker. So:

- **Stored uploads** load straight out of `st.session_state["_datasets"]`, the
  same branch `main` uses at [app.py:3039](../scanpath_studio/app.py:3039). Always ready.
- **Bundled demo** and **Synthetic test trial** are always ready.
- **Public corpora** are offered but gated on the *existing* readiness helpers —
  `datasets.potec_present` / `onestop_present` / `multipleye_inventory`. Ready →
  load through the cached raw-frame functions (`datasets.potec_raw_frames` etc.)
  plus the widget-free `app._normalize_pair`, never `prepare_data` (which takes a
  `mapping_host` and renders). Not ready → the option renders disabled with
  "Open <corpus> as the main dataset once to set its location."
- **OneStop server bundle** follows the same rule via `$ONESTOP_DATA_DIR`.

Wrap the whole thing in `@st.cache_data(show_spinner="Loading comparison dataset…")`
keyed on the name plus whatever location state the underlying loader uses, so
re-selecting B costs nothing and a corpus already loaded as A is a cache hit.

**Memory (decision 6).** No hard cap. The picker holds exactly one B, so keep
**one** secondary dataset resident and drop the reference when the selection
changes; `@st.cache_data` then governs whether a re-selected corpus is re-read or
served from cache. The ceiling is the UI's shape, not a tunable number. What this
does owe the user is *visibility*, not a limit: when both sides are large, the
disclosure caption in §5.3 names them, and the existing sidebar 🗄️ Recovery-cache
panel already reports dataset row counts. Revisit only if a real session actually
hits pressure — an eviction policy invented ahead of that evidence is a guess.

## 3. Namespacing and the merge

Two datasets can hold the same `participant_id` / `trial_id`, and the compare
builder slices its frame by exactly that pair — so an unqualified merge would
silently render the wrong scanpath, or two.

Qualify **only in the throwaway compare frames**:

```python
_COMPARE_DATASET_SEP = " · "

def _qualify_for_compare(frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Copy `frame` with `participant_id` prefixed by the dataset name and a
    `dataset` column stamped. Only ever applied to the single-trial frames that
    feed `make_comparison_figure` — never to anything the annotations, export
    slug, deep link or Corpus Analysis paths read."""
```

Changes:

- `_build_compare_meta` ([tabs.py:2127](../scanpath_studio/tabs.py:2127)) gains
  `source: Optional[SecondaryDataset] = None`. When given, it extracts from
  `source.words` / `source.fixations`, qualifies them, and returns the qualified
  `participant` alongside a new `dataset` and `text_id` entry (the latter because
  `_render_comparison_figure`'s `_lookup_text_id` searches A's `combos`
  ([tabs.py:3907](../scanpath_studio/tabs.py:3907)) and will miss a foreign trial).
- `tabs._render_comparison_figure` ([tabs.py:3880](../scanpath_studio/tabs.py:3880))
  takes B's text id as an argument instead of looking it up, and the label pool
  gets the dataset prefix so the two panels read `OneStop · l3_10` /
  `PoTeC · reader_03`. The UX-31 `cmp{idx}_label_pattern` override still wins.
- `_align_compare_columns(a, b) -> (a, b, shared_numeric: frozenset[str])`
  reindexes both frames onto the column **union** before the concat at
  [tabs.py:3383](../scanpath_studio/tabs.py:3383) (a bare `pd.concat` of disjoint
  frames warns and churns dtypes), and reports the intersection of numeric
  columns for §5.4.
- Drift correction is already applied per side above the render-mode split
  ([tabs.py:3372-3378](../scanpath_studio/tabs.py:3372)), each against its own
  words frame — no change needed, it keeps working across datasets.

## 4. Per-panel geometry in the split builder

`FigureSettings` ([plots.py:55](../scanpath_studio/plots.py:55)) gains four
optional B-side fields, honoured **only** by `_make_split_comparison_figure`:

```python
canvas_b: Optional[Tuple[int, int]] = None
background_image_b: Optional[str] = None
background_image_size_b: Optional[Tuple[float, float]] = None
background_image_origin_b: Optional[Tuple[float, float]] = None
```

In the per-panel loop ([plots.py:4697](../scanpath_studio/plots.py:4697)), `idx == 1`
resolves its canvas from `canvas_b or (canvas_width, canvas_height)` and feeds it
to both `_compute_axis_ranges` and the panel's `_fit_display_size` /
`_display_scale` pair, so B's word labels stay true-to-scale on **B's** monitor.
`per_panel_w` becomes per-panel rather than one value.

Note the existing docstring on that function — "the two readings are of the same
text, so the same page sits under each" — stops being true; update it, and route
each panel's `_add_background_image` call through its own image spec.

Overlay (`_render_comparison_figure`, [plots.py:4888](../scanpath_studio/plots.py:4888))
is untouched: §5.3 prevents a cross-dataset pair from reaching it.

## 5. UI

### 5.1 Dataset picker

`_render_compare_selector` ([tabs.py:881](../scanpath_studio/tabs.py:881)) grows a
leading `st.selectbox` keyed `cmp_dataset`, defaulting to `"This dataset"`.
Options come from `secondary_dataset_options()`; not-ready entries render disabled
with their reason. On a foreign selection the candidate list is built from
`source.combos` instead of `combos`, and the 📄 / 👤 relation markers degrade
honestly: 📄 only when the text-id *string* matches across corpora, 👤 never
(two corpora do not share readers). The picker row keeps the CMP-10 geometry —
the new selectbox joins the `[3, 5, 1.9]` split rather than adding a fourth column.

### 5.2 An independent filter set for B (decision 4)

B's candidate pool must be narrowable on **B's own** columns. Today the filter
layer is single-instance by construction: `render_narrow_by`
([controls.py:4013](../scanpath_studio/controls.py:4013)), `render_trial_filters`
([controls.py:4063](../scanpath_studio/controls.py:4063)) and
`_compute_trial_filters` ([controls.py:3928](../scanpath_studio/controls.py:3928))
all write and read **hardcoded** widget keys — `filter_text_id`,
`filter_participants`, `filter_favorites`, `filter_req_tags`, `filter_exc_tags`
and a generated `filter_<col>` — and stash the derived result under the equally
hardcoded `_trial_filters` / `_trial_filters_raw`.

Thread a **key prefix** through the nine functions that touch those keys:

```python
def render_narrow_by(words, fixations, *, prefix="", text_host=None, part_host=None)
def render_trial_filters(words, fixations, *, prefix="", host=None)
def _compute_trial_filters(words, fixations, *, prefix="") -> Dict
def read_trial_filters(prefix="") -> Dict
def clear_trial_filters(prefix="") -> None
def clear_trial_filter(*keys, prefix="") -> None
def has_active_trial_filters(prefix="") -> bool
def _seed_filter_widget(key, options, default, *, prefix="")
def _filter_fields_for(words, fixations)          # unchanged — pure column scan
```

Every literal becomes `f"{prefix}filter_…"` and the two stashes become
`f"{prefix}_trial_filters"` / `f"{prefix}_trial_filters_raw"`. B renders with
`prefix="cmp"`. The default `prefix=""` keeps every existing call site byte-identical —
`app.py` (388, 438, 3196), `tabs.py` (2844, 2850) and
`tests/test_empty_states.py` need no change.

Three things to get right:

- **The clear-sweep is prefix-blind today.** `clear_trial_filters` deletes every
  session key starting with `"filter_"` ([controls.py:3599](../scanpath_studio/controls.py:3599)).
  Unprefixed, "Clear filters" on A would wipe B's filters too. The sweep must
  match `f"{prefix}filter_"` *and* exclude longer prefixes — `"filter_"` is a
  prefix of `"cmpfilter_"` only in the other direction, so sweeping `""` must
  additionally skip keys carrying a known namespace.
- **`metadata_keys` carries widget keys** ([controls.py:3945](../scanpath_studio/controls.py:3945))
  so UX-7 can clear one filter; those values must be emitted already-prefixed, or
  the per-filter clear silently no-ops for B.
- **Nothing new lands on the wire.** `filter_*` appears in neither
  `session_keys.py` nor `url_state.py` — it is not share-link or saved-config
  format — so a second set adds nothing to the wire contract. B's filters are
  deliberately UI-only, the same call CMP-10 made for the compare sort: the share
  link already names B's exact (participant, trial), so the filter that *found*
  it need not travel.

Placement: B's Narrow-by pair + a **More** popover render inside the compare
selector row, under the dataset picker, mirroring A's row above the chips.

### 5.3 Layout gating and disclosure

In ⚙️ Compare options ([tabs.py:3156](../scanpath_studio/tabs.py:3156)), `Overlay`
renders disabled for a cross-dataset pair with `help="Overlay needs one
coordinate space — these trials come from different datasets."`, following
`controls._mode_gate` / `_gated_help`. If the stored `single_compare_layout` is
already `Overlay`, resolve to `Side by side` for this render **without rewriting
the key** — the same rule every gated widget follows, so switching back to a
same-dataset pair restores the user's choice.

A caption under the figure names both datasets and their monitors when they
differ: *"Panels are drawn to each dataset's own screen — PoTeC 1680×1050,
OneStop 2560×1440. Sizes are not comparable across panels."* Consider registering
this with `illustration.py` as a geometry-changing view; at minimum it must not
be silent.

### 5.4 Metric pickers

When comparing across datasets, `color_by` and the heatmap metric offer the
shared-numeric intersection from §3. A metric already selected but absent from B
shows an inline note rather than a blank panel.

## 6. Export (decision 5)

**The figure is nearly free.** "This trial" (`_render_save_plot_button`,
[tabs.py:335](../scanpath_studio/tabs.py:335)) downloads the *live* figure and
reads `fig.layout.width/height` from the figure itself, so a split cross-dataset
comparison already saves at its on-screen size once §4 renders it. The existing
`save_slug` is already pair-shaped —
`f"{pa}__{ta}__vs__{pb}__{tb}"` ([tabs.py:3546](../scanpath_studio/tabs.py:3546)).

**The bundle is the real work.** An exported cross-dataset figure is
unreproducible on its own — nothing in it records where B came from. Add a
**pair export** beside the figure download, writing the bulk exporter's per-trial
shape for the pair rather than for one trial:

```text
<A>__vs__<B>/
├─ figure.<fmt>
├─ plot_config.json     # + a `datasets` block: {a: {source, participant, trial, setup},
│                       #                        b: {...}}  ← what makes it reproducible
├─ fixations.csv        # both scanpaths, `dataset` column stamped
└─ measures.csv         # ditto
```

Reuse `export.ExportOptions` field-for-field (`include_png` … `table_format`,
`path_pattern`) rather than inventing a second options object; the pair is one
more "trial folder" as far as the writer is concerned. The `dataset` column is
the one from §3's `_qualify_for_compare`, which is why the tables must be built
from the qualified frames — un-namespaced rows from two corpora with a shared
participant id would be indistinguishable in the CSV.

Two things this deliberately does **not** do: it does not touch the drift-correction
rule (exported tables stay uncorrected, EXP-4/VIZ-24), and it does not extend
`bulk_export` to iterate pairs (a non-goal above).

## 7. Wire format and the four-surface rule

- **Deep link / Share.** New param `cmp_source` alongside the existing compare
  selection. Emitted by `_build_share_query`
  ([url_state.py:1510](../scanpath_studio/url_state.py:1510)) **only** when B's
  source is in `_SHAREABLE_SOURCES` ([url_state.py:352](../scanpath_studio/url_state.py:352))
  — an uploaded dataset lives in session state and cannot travel, so the Share
  panel says so instead of emitting a link that silently drops B. New keys go in
  `session_keys.py` and get pinned by `tests/test_session_key_contract.py`.
  B's filters (§5.2) are not on the wire, by decision.
- **CLI + headless API — blocked on CMP-9.** Compare mode has *no* headless
  surface at all today: there is no `api.compare_scanpaths` and no
  `render --compare-with`. CMP-8 does not build one; it specifies the spelling
  CMP-9 should adopt so cross-dataset arrives with it —
  `compare_with=(source, participant, trial)` on the API, and
  `--compare-with SOURCE:PID:TRIAL` on `render`, where an omitted `SOURCE` means
  the primary dataset. **Sequence CMP-9 before CMP-8's §7**, or CMP-8 ships a
  UI-only feature and widens the very gap CMP-9 exists to close.

## 8. Tests

- `tests/test_compare_cross_dataset.py` (new)
  - `_qualify_for_compare` purity: the source frames are unmutated; ids collide
    before qualification and not after.
  - A colliding `(participant_id, trial_id)` in both datasets renders the two
    *intended* trials (the regression this whole section exists to prevent).
  - `_make_split_comparison_figure` with `canvas_b` set produces two panels whose
    axis ranges differ per monitor, and whose label font scales differ.
  - `_align_compare_columns` on disjoint frames: union preserved, no warning,
    intersection correct.
  - Overlay gating: a cross-dataset pair resolves to a split layout and leaves
    `single_compare_layout` untouched.
- `tests/test_filters.py` — the §5.2 prefix refactor: two prefixes hold
  independent selections; `clear_trial_filters("")` does **not** clear
  `cmpfilter_*` and vice versa; `metadata_keys` values come back prefixed; the
  default-prefix behaviour is unchanged (the existing cases are the regression).
- `tests/test_experimental_setup.py` — `SetupSnapshot` round-trip, derived `dpi` /
  `px_per_degree`, and the `from_dict` fallback when a stored dataset predates the
  `setup` key.
- `tests/test_dataset_support.py` — `secondary_dataset_options` readiness gate;
  a not-present public corpus is offered-but-disabled, never loaded.
- `tests/test_export.py` — the pair bundle: folder shape, `dataset` column present
  in both tables, `plot_config.json` names both sources and both setups.
- `tests/test_session_key_contract.py` — the new share key.
- `tests/test_apptest_flows.py` — AppTest: add a second dataset via the
  `app._read_uploaded_frame` seam, select it as B, assert the figure builds and
  no `st.error`. Re-pin `single_subtab` on the same run (the conftest
  `open_subtab` gotcha).
- `tests/test_persistence.py` — the `setup` key survives a cache round-trip.

## 9. Docs / changelog

- `docs/` Compare-mode page: what cross-dataset compare does, why overlay is
  unavailable, the "each panel is on its own screen" caveat, and that B carries
  its own filters.
- `CHANGELOG.md` `[Unreleased]` → Added, two-tier shape (headline list entry
  `- **Compare scanpaths across datasets** (CMP-8)` plus a short paragraph under
  `### Details` → `#### Added`).
- `scanpath_studio/CLAUDE.md`: the *Which viz settings apply in which render path*
  table gains the B-side geometry fields; the split-comparison "same text under
  each panel" claim needs correcting; the `controls.py` entry should note that the
  filter helpers are now prefix-scoped.

## 10. Verification

- `ruff check --exclude other_vis .` **and** `ruff format --exclude other_vis .`
- `pytest` full suite; `pytest --cov` stays above the `fail_under` floor.
- Live check on the bundled demo + one public corpus: A from the demo, B from
  PoTeC, side-by-side and stacked, with and without word boxes / heatmap; confirm
  each panel's boxes sit true-to-scale on its own monitor, that narrowing B does
  not disturb A's pool, and that the exported pair bundle re-identifies both sides.
- Run both repo subagents before moving the item to *Review*:
  `surface-parity-reviewer` (this touches the wire format) and `perf-reviewer`
  (a second corpus in session, and new `@st.cache_data` keys).

## 11. Build order

1. §1 setup snapshot (ships alone, fixes a real canvas bug).
2. §5.2 filter-prefix refactor with `prefix=""` everywhere — a pure no-op
   refactor with the existing filter tests as its guard. Landing it *before* any
   cross-dataset code keeps the diff that introduces B small and reviewable.
3. §2 secondary loader + §5.1 picker, restricted to stored uploads — end-to-end
   on the cheapest source.
4. §3 namespacing/merge + §4 per-panel geometry — the figure actually renders.
5. §5.2's second filter instance, §5.3 gating/disclosure, §5.4 metric intersection.
6. §6 pair export.
7. §2's public-corpus readiness gate.
8. §7 share key; the CLI/API half rides with **CMP-9**.

## Critical files

`tabs.py` (2127 `_build_compare_meta`, 881 `_render_compare_selector`, 3383 the
merge, 3880 `_render_comparison_figure`, 3156 the Compare popover, 335
`_render_save_plot_button`, 2489 `_render_export_panel`) ·
`plots.py` (55 `FigureSettings`, 4532 `_make_split_comparison_figure`, 4888/6489
the comparison builders) · `controls.py` (3928 `_compute_trial_filters`, 3573
`read_trial_filters`, 3585 `clear_trial_filters`, 4013 `render_narrow_by`, 4063
`render_trial_filters`) · `app.py` (2119 `seed_canvas_state`, 1292
`PUBLIC_DATASET_REGISTRY`, 1333 `_load_public_dataset`, 3039 the stored-dataset
branch) · `experimental_setup.py` · `wizard.py` (165 `_finalize_wizard_dataset`,
1092/1716 the payloads) · `utils.py` (1157 `build_comparison_options`) ·
`url_state.py` (352 `_SHAREABLE_SOURCES`, 1510 `_build_share_query`) ·
`export.py` · `persistence.py` · `session_keys.py`
