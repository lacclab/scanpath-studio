# DATA-27 · EyeGenBench: load all 39 benchmark corpora as one built-in source

> **Status: design, 2026-08-14** — spec for the
> [improvements tracker](../tracker/index.html) → **DATA-27** ("Load every
> EyeGenBench dataset into the app"). Consumes
> [EyeBench/EyeGenBench](https://github.com/EyeBench/EyeGenBench) as an offline
> preprocessing step; adds a fourth built-in corpus source alongside OneStop,
> PoTeC and MultiplEYE.

## Context

[EyeGenBench](https://github.com/EyeBench/EyeGenBench) harmonises 39 public
eye-tracking-while-reading corpora into one schema. Its `prepare_data()`
downloads each corpus from its own host, parses it, validates it against a
pandera schema, and writes three feather files per dataset into
`data/<Name>/processed/`:

| File | Grain | Columns |
| --- | --- | --- |
| `fixations.feather` | one fixation | `unique_trial_id`, `unique_participant_id`, `unique_paragraph_id`, `fix_index`, `ia_index`, `fix_duration`, `fix_landing_position`, `ia_label`, `dataset_name` |
| `texts.feather` | one paragraph | `unique_paragraph_id`, `text`, `text_language`, `ia_list` (list[str]) |
| `participants.feather` | one reader | `unique_participant_id`, `participant_language`, + per-corpus metadata |

That schema is the whole appeal — 39 corpora, one shape, one loader. It is also
the whole problem:

**EyeGenBench discards screen geometry.** Its output records *which word* each
fixation landed on (`ia_index`) and *where within the word* (`fix_landing_position`,
a 0–1 normalised offset), but no pixel coordinates and no word bounding boxes.
Scanpath Studio is a spatial visualiser: `normalize_words` requires
`x`/`y`/`width`/`height` ([data.py:2007](../scanpath_studio/data.py:2007)) and the
true-scale chart draws real screen positions. A direct read of the harmonised
feathers cannot produce a scanpath plot.

The geometry is not gone from the *world*, only from EyeGenBench's output — and
recovering it, per dataset, at the best fidelity available, is what this spec is
mostly about.

PoTeC is the precedent: its adapter already reconstructs x/y from which
*character* was fixated ([contributing-a-dataset.md](../docs/contributing-a-dataset.md)),
because PoTeC's fixations carry no coordinates either. DATA-27 generalises that
move to 39 corpora and makes the fidelity of each reconstruction explicit in the
data.

## Research: where real geometry actually lives

Surveyed 2026-08-14 across three sources. Reproducible: the UZH table is an
inline `const DATA` array (80 datasets × 53 fields) in the page source; the
pymovements specs are `experiment:` blocks in its shipped dataset YAMLs.

### Tier 1 — exact geometry inside the raw files EyeGenBench downloads

The strongest source, and better than anything reported in the papers. EyeLink
interest-area exports carry per fixation:

- `CURRENT_FIX_INTEREST_AREA_DATA` = `[STATIC, RECTANGLE, left, top, right, bottom]`
  — **the actual on-screen pixel box of the fixated word**
- `CURRENT_FIX_X` (and `CURRENT_FIX_Y` in many exports)

EyeGenBench reads exactly these, divides them into a normalised landing position,
and drops them (`eyegenbench/data/utils/landing_position.py:25-32`). Confirmed
available for OneStop; PoTeC ships per-character `.ias` boxes plus
`word_aoi_*.tsv`; SB-SAT ships raw gaze as pixel coordinates. 26 of the 40
dataset modules already touch coordinate-bearing columns for one reason or
another.

**True Tier-1 coverage cannot be known until the corpora are downloaded.** The
prep step establishes it empirically, per dataset, while the raw files are on
disk, and records the answer.

### Tier 2 — published display parameters

| Source | Fields | Covers (of the 40 modules) |
| --- | --- | --- |
| `pymovements` dataset YAMLs | `screen_width_px`/`height_px`, `width_cm`/`height_cm`, `distance_cm`, sampling rate | **11** — colagaze, copco, emtec, etdd70, gaze4hate, gazebase, ggtg, interead, potec, raccoons, sb_sat (10 of the 39 loadable; the 11th is the `gazebasereading` stub) |
| UZH [dataset review table](https://pub.cl.uzh.ch/projects/eyetracker/datasets.html) | resolution, monitor, viewing distance, **font, font size, monospaced, characters per visual angle, spacing, fg/bg colour** | **+6** with resolution (bsc, chinesereading, cuentos, eyevoicespan, iitbhgc, psr); **10** with font |
| Papers, per dataset | fills specific gaps | CopCo: Courier 14, double-spaced · Provo: 1600×900, 60 cm, ~3 chars/° · ZuCo: Arial 20 pt, black on light grey · MECO L2 W2: Consolas 20–22 |

**22 of the 40 have nothing published in either registry** — all five CFILT
sets, MECO L1 W1/W2 and L2 W1, ZuCo 1/2, UCL, RSC, PSC II, Provo, OneStop,
celer, adegbts, bscii, oasstetc, readingbrain, readingbrainl2, vqamhug. Several
of those are nonetheless Tier 1: OneStop and Provo have no registry entry but do
ship coordinates.

**Fidelity honestly stated.** For a *monospaced* corpus, resolution + font size +
characters-per-degree reconstructs a layout that is genuinely true-to-scale. For
a proportional font (Arial, Noto Sans, Times New Roman) the same inputs fix the
canvas and the line pitch but leave within-line word positions approximate.

## Scope

**In.** All 39 implemented EyeGenBench datasets, preprocessed through
EyeGenBench itself, converted to app-native bundles, and exposed as one
built-in **EyeGenBench** source with a dataset picker — on all four surfaces.
Per-dataset geometry at the best tier available, with the tier recorded in the
data and shown in the UI.

**Out.** `gazebasereading` — still a `NotImplementedError` stub upstream. 39
loadable, not 40; reported as skipped rather than implemented in their repo.

**Out.** Upstreaming geometry carry-through as a PR to EyeGenBench. Tier-1
extraction lives in this repo as a sidecar (see §3). Worth proposing to them
later; not a dependency for shipping this.

**Out.** Any change to EyeGenBench's own harmonisation. We run their
`prepare_data()` unmodified so our bundles stay reproducible from their `main`.

**Out.** Vendoring corpus data into this repository. Bundles are generated
locally, gitignored, and every corpus keeps its own licence and attribution.

## 1 · Geometry resolution — three tiers

Resolved per dataset at prep time, in order, first hit wins:

**`real`** — parse boxes from EyeGenBench's `interim/` and `downloads/` trees and
join to the harmonised feathers on `(unique_paragraph_id, ia_index)`. A single
*generic* EyeLink parser covers the `IA_DATA` and `IA_LEFT…IA_BOTTOM` shapes;
per-dataset adapters only where the shape differs (PoTeC's `.ias`, SB-SAT's raw
gaze).

> Per-fixation `IA_DATA` only carries boxes for words that were *fixated*.
> Skipped words are filled from the corpus' full IA report where one ships,
> otherwise interpolated along the line from their neighbours' boxes. Which of
> the two happened is recorded per dataset, because interpolation is a weaker
> claim than a real box.

**`reconstructed`** — lay out `ia_list` using that dataset's published
resolution / font / size / spacing, from a checked-in table carrying a **source
citation per field** (`pymovements` → UZH → paper, in that order).

**`synthesized`** — generic monospace defaults where nothing is known: wrap
`ia_list` to a default canvas, uniform character width, uniform line pitch.

Every trial carries a **`geometry_source`** column with that value. It is
registered in `data.WORD_OPTIONAL_FIELDS` and `FIX_OPTIONAL_FIELDS` (without
which normalisation silently drops it) and surfaced as a badge in the UI, so a
reconstructed layout can never be mistaken for the real screen.

Within a word's box, a fixation's x is placed at
`left + fix_landing_position × width` — exactly inverting EyeGenBench's own
formula, so the round trip is lossless wherever the box is real.

## 2 · Module layout

Everything below is pandas plus the standard library and imports no Streamlit,
matching `datasets.py`'s constraint.

| File | Responsibility |
| --- | --- |
| `scanpath_studio/eyegenbench.py` | The bridge: bundle → raw `(words, fixations)` frames, `eyegenbench_raw_frames` / `load_eyegenbench` / `eyegenbench_present`, schema dicts, per-dataset monitor constants |
| `scanpath_studio/eyegenbench_geometry.py` | Tier-1 extractors (generic EyeLink + per-dataset adapters), the Tier-2 display-parameter table with citations, the Tier-3 layout engine |
| `scripts/prepare_eyegenbench.py` | Offline prep: run EyeGenBench `prepare_data()` per dataset, extract geometry while raw files are on disk, emit the bundle, write the manifest |

The layout engine is shared by Tiers 2 and 3 — same code, different inputs
(measured font metrics vs. defaults), so there is one place where text becomes
boxes.

## 3 · Bundle format

The prep script is the only thing that ever needs torch, lightning and pandera.
The app reads only the emitted bundle, which is plain Parquet:

```text
data/EyeGenBench/
├─ manifest.json              # per-dataset: geometry tier, monitor, counts, licence, citation, prep timestamp
└─ <Dataset>/
   ├─ words.parquet           # participant-free stimulus-level word boxes (broadcast on load)
   ├─ fixations.parquet
   └─ participants.parquet    # → the existing DATA-20 participant-metadata table
```

`words.parquet` is **stimulus-level** — one row per word per text, no
participant column — which `data.broadcast_stimulus_words` already expands
across readers, exactly as PoTeC's word AOIs do. `participants.feather` maps
straight onto the DATA-20 participant-metadata path; it is never broadcast onto
the word or fixation frames.

`manifest.json` is what the sidebar reads to list datasets without opening any
Parquet, so the picker stays instant.

## 4 · Prep step

`scripts/prepare_eyegenbench.py --dataset <name> | --all`, run in its own venv
(EyeGenBench's dependencies stay out of the app's `.venv`):

1. Run EyeGenBench's `prepare_data()` unmodified → harmonised feathers.
2. Probe `interim/` + `downloads/` for geometry; resolve the tier.
3. Build word boxes and fixation coordinates.
4. Emit `words/fixations/participants.parquet` + the manifest entry.
5. Report per dataset: tier, rows, readers, texts, and any approximation.

Idempotent per dataset, so an interrupted run resumes. Raw downloads are
**kept** (user's call, 2026-08-14). With ~116 GB free at design time and
OneStop's raw alone at ~15 GB, the script **stops and reports when free space
drops below 15 GB** rather than deleting anything.

Failures are per-dataset and non-fatal: a corpus needing manual or credentialed
download is recorded as skipped with its reason, and the run continues.

## 5 · App integration — the four surfaces

Following [contributing-a-dataset.md](../docs/contributing-a-dataset.md) exactly:

- **UI** — `_load_eyegenbench_source(...)` in `app.py` using the shared
  `_dataset_dir_input` / `_dataset_access_status` helpers, plus one
  `PUBLIC_DATASET_REGISTRY` entry. A **dataset picker** inside the source (39
  entries, grouped by language) is the one shape the existing three corpora
  don't have; it lives in the DATA-9 `options_host` sub-slot.
  `EYEGENBENCH_DEFAULT_DIR` goes in `constants.py`, and into the tuple
  `tests/test_apptest.py` monkeypatches to an empty `tmp_path`.
- **Headless API** — `load_eyegenbench(root, dataset=...)`, lazy re-export in
  `__init__.py` (`__all__` + `_DATASET_EXPORTS`), autodoc block in `docs/api.md`.
- **CLI** — `--eyegenbench DIR` plus `--eyegenbench-dataset NAME` in `render`'s
  input group, added to the exactly-one-input check.
- **Deep link / Share** — registered in `_SHAREABLE_SOURCES`, with the chosen
  dataset carried through `_apply_url_preset` / `_build_share_query`. Without
  this a shared link can't reopen the corpus.

Monitor size per dataset comes from the manifest rather than a single constant —
39 corpora do not share a screen — so the canvas snaps to each corpus' real
resolution where known.

## 6 · Error handling

- Missing bundle → `FileNotFoundError` naming the prep command to run. The app
  prints loader errors verbatim in the sidebar, so the message *is* the error UI.
- `eyegenbench_present(root)` is path-stats only and **strict**: manifest plus
  the three Parquet files for the selected dataset. A lenient check would pass a
  partial tree and crash mid-load.
- Data missing → `load_sample_data()`, so the app stays usable.
- A dataset whose geometry tier is `synthesized` loads normally but carries the
  badge; it is never silently presented as real.

## 7 · Testing

Per the repo's dataset-adapter contract:

- Loader against a tiny bundle-shaped tree in `tmp_path` (mirroring the
  `potec_root` / `multipleye_root` fixtures), asserting normalized output
  exactly — ids, word text, reconstructed coordinates, durations.
- **Round-trip invariant**: for a real-geometry fixture, `fix_landing_position`
  recomputed from the emitted x and box reproduces the input to floating-point
  tolerance.
- One test per geometry tier, asserting `geometry_source` is stamped correctly
  and that the tier-2 layout is monotone in x within a line and in y across lines.
- Auto-detection parity — the app runs raw frames through `propose_*_schema`, so:
  `assert data.validate_word_schema(data.propose_word_schema(words)) == []` and
  the fixation equivalent.
- Failure paths: unknown dataset name → `ValueError`; missing bundle →
  `FileNotFoundError` whose message says what to run; `eyegenbench_present`
  returns `False` on a partial tree.
- `tests/test_apptest.py` picks the registry entry up automatically.

## 8 · Licensing

No corpus data is vendored. EyeGenBench downloads each corpus from its **own**
host; our bundles are generated locally and gitignored. The manifest carries each
corpus' licence and citation so attribution travels with the data into export
bundles. EyeGenBench itself is only a build-time dependency of the prep script,
never an install dependency of the app.

## 9 · Docs

A `docs/eyegenbench.md` page under **Datasets** — what the benchmark is, the 39
corpora, and, prominently, the three geometry tiers and which datasets fall in
each. Listed in `mkdocs.yml`'s `nav:`.

## Open decisions

Recorded for the tracker's *Waiting on you* box:

- **Tier-3 default canvas.** A synthesized layout needs *some* screen. 1920×1080
  with a 20 px monospace font is the proposal; a corpus-typical 1280×1024 is the
  alternative. Affects only the 22 datasets with nothing published.
- **Picker grouping.** 39 entries need structure — by language (proposed), by
  script, or flat alphabetical.
