# Scanpath Studio — Improvements & Roadmap

Running list of planned improvements. The bulk is **new analysis views** (see
[Analysis sections](#analysis-sections)); a shorter [Engineering](#engineering)
section tracks code/test/docs debt.

Terminology follows `AGENTS.md`: canonical measures are **FFD**
(`first_fixation_ms`), **FPRT** (`first_pass_gaze_duration_ms`), **RPD / go-past**
(`regression_path_duration_ms`), **TFD** (`total_fixation_duration_ms`), plus
`n_fixations`, `skip_flag`, `regression_in/out_flag`. Canonical keys are
`participant_id`, `trial_id`, `paragraph_id`, `word_id`, `line_idx`.

---

## Analysis sections

**Goal:** replace the single *Corpus Analysis → Aggregated Views* subtab with a
set of analysis sections, each answering one question — *what does a text look
like? a reader? a group? two groups against each other?* All sections obey the
active trial filters and the current metric picker.

Proposed top-level structure (tabs or sidebar radio inside Corpus Analysis):

| Section | Unit of analysis | Answers |
|---|---|---|
| **Per text** | one `paragraph_id` / `trial_id`, many readers | where in *this* text do readers slow down / regress / skip? |
| **Per participant** | one `participant_id`, many trials | what kind of reader is this? how do their distributions look vs. the cohort? |
| **Per group** | a cohort defined by a filter (condition, difficulty, L1/L2, site…) | what's typical within the group? |
| **Group comparison** | two groups side by side | where do the groups differ, and is it meaningful? |
| **Trends** *(existing)* | corpus-wide, by trial/fixation index | learning/fatigue effects across the session |

Implementation: keep aggregation logic **pure** in `aggregation.py` (one helper
per view, returns a tidy DataFrame), build figures in `plots.py` via the existing
`make_*_figure` pattern, wire into `tabs.py`. Add a smoke test per figure
against the bundled sample (3 pid × 2 articles).

---

### Per text

The headline idea: **TFD-by-word, one panel per reader, stacked vertically** so a
text reads top-to-bottom and you can eyeball where individual readers diverge.

- **Stacked per-reader word profiles (small multiples).** X = `word_id` (in
  reading order), Y = chosen measure (TFD default; switchable to FFD/FPRT/RPD/
  `n_fixations`). One short line/area panel per `participant_id`, panels stacked
  with a shared X axis so word positions line up. Plotly faceted subplots
  (`make_subplots`, shared_xaxes). Optionally overlay the cohort mean as a faint
  line in each panel for reference. *This is the primary requested view.*
- **Word × reader heatmap.** Same data as above but collapsed to a single
  heatmap: rows = participants, columns = `word_id`, color = measure. Faster to
  scan for "which words are universally hard" (bright columns) vs. "which reader
  is slow everywhere" (bright rows). Reuses the word-level heatmap machinery.
- **Cohort word profile with spread band.** Single line of the mean measure per
  word, with a shaded IQR / ±1 SD band across readers. The "average reader of
  this text" with uncertainty.
- **Word difficulty annotated on the stimulus.** The actual text laid out
  (existing true-to-scale renderer), each word tinted by aggregate measure or
  `skip_rate` / `regression_in_rate` — a corpus-level version of the single-trial
  scanpath, no fixations drawn.
- **Measure vs. linguistic feature.** Scatter of per-word mean measure against a
  bundled feature (`gpt2_surprisal`, `wordfreq_frequency`, `word_length`,
  `universal_pos`), with a trend line. Connects reading behavior to text
  properties; OneStop sample ships these columns.
- **Skip / regression rate per word.** Bar or lollipop of `skip_flag` and
  `regression_in_flag` rates by `word_id` — where readers jump in/over.

### Per participant

The user ask: **distributions + the plots people expect for one reader.**

- **Measure distributions.** Histogram / violin / box of fixation
  `duration_ms`, saccade `saccade_amplitude`, and per-word TFD/FFD for the
  selected participant, with the cohort distribution drawn behind for context
  (this reader vs. everyone). KDE overlay optional.
- **Reading speed & summary card.** Words-per-minute, mean fixation duration,
  fixation count, regression rate, skip rate, mean saccade amplitude — a compact
  stat strip per participant (and the cohort percentile for each).
- **Fixation duration over time.** X = `timestamp_ms` (or `order_in_trial`),
  Y = `duration_ms` — within-trial fatigue / settling. Faceted by trial or
  averaged.
- **Saccade amplitude vs. fixation duration.** 2D density / hexbin — the classic
  oculomotor scatter; clusters distinguish careful vs. skimming reading.
- **Progressive vs. regressive saccades.** Counts/share of `is_regression` (or
  `regression_out_flag`) per trial; a reader's regression tendency.
- **Launch-site / landing-position curves.** Histogram of fixation landing
  position within words (needs `first_fix_x` relative to word box) — the
  preferred-viewing-location curve, a standard reading plot.
- **Per-trial trend for this reader.** The existing Trends line, but filtered to
  one participant — does *this* person slow down across the session?

### Per group

A group = whatever the current trial filter selects (condition Hunting/Gathering,
difficulty Adv/Ele, repeated reading, L1/L2, collection site, correctness…).

- **Group distribution summaries.** The per-participant distributions, pooled
  across the group: violin/box of fixation duration, saccade amplitude, TFD,
  reading speed — one violin per group member or one pooled shape.
- **Group word profile.** Cohort word profile (mean + band) computed within the
  group, for a selected text.
- **Per-reader summary table for the group.** Sortable table: one row per
  participant, columns = summary stats — spot outliers in the cohort.
- **Group trend.** Trends line averaged within the group (and optionally per
  participant faint behind the mean).

### Group comparison

- **Overlaid distributions.** Two groups' fixation-duration / saccade-amplitude /
  TFD distributions on shared axes (violin halves or overlaid KDE) — the core
  "do these groups read differently" view.
- **Difference word profile.** Per-word measure for group A minus group B along
  the text, with a zero reference line — *where in the text* the groups diverge
  (e.g. Adv vs. Ele, or L1 vs. L2). Diverging colormap.
- **Paired summary bars.** Side-by-side bars of group means per measure, with
  error bars (SD / SEM / bootstrap CI).
- **Effect size + simple test.** Per measure, show mean difference, Cohen's *d*,
  and a Mann–Whitney / t-test p-value with a clear "exploratory, not
  pre-registered" caveat. Keeps users from eyeballing significance.
- **Two-group word heatmap, stacked.** Group A heatmap above group B (shared word
  axis) for direct visual comparison of where each group spends time.

### Cross-cutting controls for these sections

- A shared **measure picker** (TFD/FFD/FPRT/RPD/n_fixations/skip/regression) that
  every section reads from.
- **Aggregation choice** (mean / median / sum) and **spread choice** (SD / IQR /
  SEM / bootstrap CI) where a band or error bar is drawn.
- **Normalization toggle** — raw vs. z-scored-within-reader — so slow and fast
  readers can be compared on shape rather than absolute level.
- **Min-readers / min-trials guard** — gray out or warn when a per-word cell is
  backed by too few observations (avoid over-reading n=1 words).
- Every aggregated view should offer **download of the underlying tidy table**
  (reuse the export plumbing) so users can re-plot elsewhere.

---

## Engineering

Lower priority than the analysis views, but tracked.

### Tests
- Add tests for each new `aggregation.py` helper (pure functions → easy: feed a
  tiny tidy frame, assert the grouped output) and a smoke test per new figure.
- Cover the OneStop per-pid shard fast-path (gated on `$ONESTOP_DATA_DIR`).
- Cover MultiplEYE side-data enrichment (questions / reader meta / measures / images).
- Extend `AppTest` coverage: column-mapping UI, trial filters, bulk-export zip.

### Code quality
- `app.py` is the largest module and mixes data-source dispatch, deep-link
  restore, column mapping, and view dispatch — extract a data-source strategy
  and a view dispatcher.
- Centralize `st.session_state` keys (TypedDict/Enum) to avoid stringly-typed
  collisions.
- Confirm whether `watchdog` is actually used; drop it from requirements if not.
- Resolve / promote the "Generations (WIP)" tab — finish it or hide it.

### UX / robustness
- Surface which columns schema auto-detection chose (currently silent) in the
  Column Mapping panel.
- Better animation-export errors when Chrome/Chromium is missing; consider a
  cold-Chrome fallback if the warm Kaleido server fails.
- Version saved plot-config JSON and add a migration path.

### Docs
- Document the **true-to-scale text rendering** model (data-space word size →
  screen px) — it's central and currently only in code comments.
- Document the new analysis sections in `docs/` once built.

> When any view, measure, severity, or path here lands, update `AGENTS.md`,
> `scanpath_studio/CLAUDE.md`, `CHANGELOG.md`, and the `docs/` site in the same
> change (project convention: keep docs in sync with code).
