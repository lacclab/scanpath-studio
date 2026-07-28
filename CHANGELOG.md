# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Type an exact value into any slider** (UX-9) — marker size, opacity, line width, label sizes, colour ranges and the fixation-index window each pair their slider with a number box.
- **"Don't show this again" on the welcome tour** (UX-12) — persisted per browser in a first-party cookie; **🎓 Show tutorial** always brings it back.
- **Documentation link in the app** (UX-17) — the docs site is now one click away from the sidebar Help group and the About popover.

### Changed
- **Corpus Analysis is easier to find** (UX-18) — the header toggle is a primary button with a directional cue and a one-line caption naming what's on the other side.
- **About popover** (UX-16) — the BibTeX citation opens from a collapsed **📖 How to cite** expander instead of filling the panel.
- **"Snap fixations above words"** (UX-13) moved into its own *Linear-reading schematic* block so it no longer reads as a drift-correction option; both it and the Arc saccade mode now name each other.

### Fixed
- The sidebar's collapse control (UX-8) is always visible and has a proper hit area, so an open sidebar is as easy to dismiss as it is to open.
- Tutorial card spacing — the ✕ sits a touch lower in the corner, and the Back / Next footer no longer crowds the progress bar.
- The header's **Corpus Analysis** / **← Scanpath** nav button now lines up exactly with the control rail below it (same width and right edge).

## [0.25.0] - 2026-07-16

### Added
- **Standalone desktop app** (ENG-15) — a double-clickable PyInstaller bundle per OS (Windows / macOS-arm64 / Linux; no Python install needed, data stays local): `desktop/` launcher + spec + icons + smoke test, built and attached to releases by the new `Desktop builds` workflow. Design in `plans/eng-15-desktop-app.md`.

### Changed
- **Docs overhaul** — branded MkDocs Material theme (app palette + logo, nav tabs, grouped sections), a landing page with feature cards and a fresh app screenshot (README screenshot refreshed too), and a dedicated **Desktop app** page with per-OS install steps. Stale claims fixed: the two-view layout (was "three tabs"), OneStop part names, PoTeC reader ids (also in the `--potec` CLI help).

## [0.24.0] - 2026-07-03

### Added
- **Comparisons subtab** (ENG-8) — score the selected scanpath against other scanpaths of the same text, grouped by a **Comparison column** you pick (regime / repeated-reading id / model generation / participant / trial); closest shown, ranked by NLD. **Line assignment** (drift-correction grid) is now its own top-level subtab.
- **Corpus Analysis** (AN) — question-oriented views **Per text · Per reader · Groups** (profile one cohort or compare two): metric distributions + word profiles, per-text heatmaps pooled over readers, reader summaries, and group differences with effect sizes; shared measure / aggregation / spread pickers with 95% bootstrap CI bands.
- **Image-based stimuli** (VIZ-4) — show a stimulus image on any dataset: an upload **overrides** a dataset's built-in image; `image_path` / `image_x` / `image_y` columns declare native per-trial images; **Align to text** (X/Y offset + scale) and an opacity slider fit/dim it.
- **Colour saccades by reading type** (VIZ-8) — Uniform / By type (forward · skip · refixation · return-sweep · regression), editable class colours, optional legend.
- **"Linear reading" view** (VIZ-9) — arched saccades + snap each fixation above its word.
- **Animated replay autoplays on load** (VIZ-10) — at the configured speed; an **Autoplay on load** checkbox turns it off. Slider is now a linear time scrubber with an elapsed/total-seconds readout (VIZ-11).
- **Vertical drift correction** (PRE-3) — the ten Carr et al. (2021) line-assignment algorithms, applied in place or compared in the Line assignment subtab.
- **Separable-layer export** (VIZ-5) — one file per layer (boxes / fixations / saccades / heatmap / labels / image) that register when stacked.
- **Heatmap colour scaling: Linear or Log** (VIZ-3).
- **Public OneStop corpus** (DATA-3) — all four regimes, seven parts, two variants; shareable via deep link. The bundled demo now ships per-trial stimulus images.
- **Data sidebar reorganized** (DATA-8/9) — one flat source picker tagged by kind, one ordered ⚙️ Configure group, native folder picker; plus stable trial selectors + annotation markers (UX-5/6), a quick-view preset indicator (VIZ-12), a configurable word-hover measure (VIZ-13), and a px-vs-pt font note (VIZ-1).

Every feature reaches all surfaces: UI · deep-link + Share · Save & restore · CLI · headless API.

### Changed
- **Save & restore configs are versioned** (ENG-11) — a schema version + migration on load; a newer config restores best-effort with a warning.
- **Word labels are left-aligned in their AOI box** (was centered) so they coincide with the stimulus image + fixations.
- **Author list** (ENG-14) — full co-author set with affiliations in the About panel, `CITATION.cff`, and README.
- **Slightly larger small text** (VIZ-2).

### Fixed
- **Branded theme applies from any launch directory** (BUG-6) — injected as `--theme.*` flags, so `python -m scanpath_studio` from anywhere renders the pinned blue theme instead of Streamlit's default red.
- **Bulk export no longer skips trials whose words don't join** (VIZ-5) — a fixations-only / non-joining-words dataset now exports instead of reporting "empty data".
- **Large uploads no longer OOM-crash the hosted demo** (BUG-5) — a pre-parse size guard warns and asks to confirm above ~25 MB.
- **MultiplEYE stimulus text alignment** (BUG-3), the **bundled-demo stimulus-image vertical origin**, and **"No data found" when run outside the repo root** (default data dirs anchored to the project root).

### Docs
- **True-to-scale rendering guide** (ENG-12) — new [`docs/rendering.md`](docs/rendering.md).

## [0.23.0] - 2026-06-24

### Added
- **Stimulus-font install hint** — when a dataset declares its typeface
  (MultiplEYE), a note under **Text font** names the font, links a download, and
  gives per-OS install steps. The overlaid labels only match the stimulus image
  pixel-for-pixel when that exact font is installed (the browser otherwise falls
  back per script, so a CJK font's half-width Latin — URLs/digits — drifts); the
  note also points to the stimulus image as the reliable fallback.
- **Corpus Analysis — question-oriented analysis sections (AN-1…28)** — the single
  *Aggregated Views* subtab is replaced by four sections, each answering one
  question, plus the WIP *Generations* tab:
  - **Per text** (one text, many readers): stacked per-reader word profiles with an
    optional cohort-mean overlay, a word × reader heatmap, the cohort word profile
    with a spread band, word difficulty tinted on the true-to-scale stimulus, a
    per-word measure-vs-linguistic-feature scatter (surprisal / frequency / length /
    POS) with a trend line, and skip / regression-in rates per word.
  - **Per reader** (one reader, many trials): measure distribution vs the cohort
    (violin/box), a reading-speed summary card with cohort percentiles, fixation
    duration over time, the saccade-amplitude × fixation-duration density scatter,
    progressive vs regressive saccades per trial, the landing-position (PVL) curve,
    and this reader's per-trial trend.
  - **Per group** (a cohort): pooled distributions, the group word profile, a
    per-reader summary table, and the group trend (optionally with per-reader lines).
  - **Group comparison** (two cohorts): overlaid distributions, the per-word A−B
    difference profile (diverging colormap + zero line), paired summary bars with
    error bars, an effect size + significance test (Cohen's *d*, Welch t-test /
    Mann–Whitney; exploratory), and a stacked two-group word heatmap.
  - **Cross-cutting controls** every section reads: a shared measure picker
    (TFD/FFD/FPRT/RPD/n_fixations/skip/regression-in/out + fixation duration /
    saccade amplitude), mean/median/sum aggregation and SD/SEM/IQR/bootstrap-CI
    spread, a *z-score within reader* normalization toggle, a min-readers/min-trials
    guard, and a per-view tidy-table CSV download. Groups are defined either by
    splitting a categorical field or by two independent filter sets. The per-text
    stimulus view now honours the active `global_*` visualization settings instead
    of hard-coded display options (AN-28). Adds `scipy` for the group tests.
- **Saccade line width** — a width slider (0.5–10 px, default 2) in the Saccade-style
  popover, threaded through every plot, bulk export, save/restore, and deep links
  (per-scanpath in comparisons); plus headless `--saccade-color`/`--saccade-style`/
  `--saccade-width` CLI flags and a `plot_scanpath(saccade_width=…)` kwarg.
- **Show full monitor** toggle — frame the plot to the whole presentation monitor
  instead of cropping to the data extent (single, animated, comparison, bulk export).
- **MultiplEYE corpus support** — `load_multipleye()`, the in-app *Public datasets*
  picker, and the *Add dataset* wizard (browser upload) load the multilingual
  reading corpus (identity parsed from folder/file names, one trial per stimulus
  page, character AOIs aggregated to word boxes), with its comprehension questions,
  pre-aggregated reading measures (`IA_*`), reader metadata, and a true-to-scale
  stimulus-page background image.
- **OneStop public dataset** — the *Public datasets* picker now offers the
  [OneStop](https://github.com/lacclab/OneStop-Eye-Movements) 360-participant
  English corpus, downloading the paragraph-level interest-area + fixation
  reports from [OSF](https://osf.io/2prdq/) on demand (regime-selectable:
  ordinary / information seeking / repeated / information-seeking-repeated),
  rendered true-to-scale on OneStop's 2560×1440 monitor. Distinct from the
  env-var `$ONESTOP_DATA_DIR` server bundle. See [docs](docs/onestop.md).
- **Public datasets (PoTeC + MultiplEYE) shown by default** (`SCANPATH_PUBLIC_DATASETS=0`
  to hide). Schema auto-detection now recognizes MultiplEYE columns.
- **MultiplEYE server-bundle source** — a URL-addressable `multipleye` data
  source (`?source=multipleye`) for deep-linking a review app straight into the
  viewer at a given participant + trial. Gated on `$MULTIPLEYE_DATA_DIR` pointing
  at a raw export root, it reuses the native MultiplEYE loader (same raw frames,
  schema auto-detection, and authoritative 1920×1080 monitor) as the public
  source — so it renders identically — and fast-paths to a single session for
  `?participant` (resolved case-insensitively). Exposed on every surface: the
  sidebar source list, the Share/deep-link round-trip, and headless
  `render --source multipleye [--export DIR]`. Mirrors the OneStop server
  bundle.
- **Upload-wizard helpers** — derive trial/participant ids from the filename
  (delimiter split or regex) and aggregate character AOIs into word boxes.
- **Fixation classification (visual only)** — under the Fixation controls, flag
  **short / long / out-of-bounds** fixations and either highlight them (chosen
  marker + colour) or discard them from the plot, with editable short/long
  duration thresholds. Affects only what's drawn — measures and exports are
  unchanged. Replaces the old out-of-text marker toggle.
- **Drag-to-reorder trial chips** — an inline **✏️ Edit chips** popover beside the
  chip strip (replaces the sidebar picker): drag fields between *Shown* and
  *Available* and reorder within *Shown*. The chip strip's **More** dropdown now
  holds the full chip list (so any chip clipped at the line edge is always
  reachable) alongside the summary stats.
- **Column mapping surfaces auto-detected columns** per field (and flags when
  you've overridden the detected default).
- **Fixation marker opacity** — an opacity slider (global + per-scanpath, default
  0.7) replaces the *Hollow circles* toggle, so overlapping fixations show through;
  threaded through every plot, animation, comparison, bulk export, save/restore and
  deep links.
- **Fixation-index window on the main plot** — a range slider in the Fixation popover
  draws only fixations (and their saccades) within the chosen `order_in_trial` range,
  applied to the single, animated and comparison views; chips/panels keep the full trial.

### Changed
- **Public-datasets picker reworked** (DATA-4…7) — the corpus list is now a
  searchable selectbox (shows each corpus' short name + a *language · size*
  caption, one-line description, and home link) that scales as more datasets are
  added; **local/private upload stays the primary path**. Each loader now shows
  an **Expected files** layout for its data directory and a **found vs. Download**
  status — a one-click ⬇ Download (PoTeC, OneStop) replaces the always-on
  *Download if missing* checkbox, so an already-downloaded corpus never re-checks
  the network. The per-source participant/text narrowing (PoTeC *Texts/Readers*,
  MultiplEYE *Sessions/Stimuli*) is gone — each source loads the whole corpus and
  the global **Narrow by** trial filters scope it. (The headless `load_potec` /
  `load_multipleye` keep their `readers`/`texts`/`sessions`/`stimuli` args.)
- _Internal:_ split `app.py` (4087 → ~1640 lines) into focused modules —
  deep-link/share/config → `url_state.py`, the upload wizard → `wizard.py` — and
  factored plot overlay layers into helpers. No behavior change.
- **Navigation streamlined** — Corpus Analysis is a header toggle; Data Inspection
  and Share are Scanpath subtabs; the sidebar view-nav is gone.
- **Trial selection reworked into Filter → Pick** — Text/Participant/condition
  filters narrow the pool, then one row picks the trial (dropdown + scrubbing
  slider + ◀ ▶); Browse-by modes removed.
- **Comparison styling moved into the per-layer Fixation/Saccade popovers**, beside
  the single-trial controls.
- **Compare mode reworked.** The second-trial selector sits above the chips and
  mirrors the main picker — trial id + **★ same-text** / **👤 same-participant**
  markers in the dropdown (ordered stars → same-participant → rest), `index/N · id`
  slider, ◀ ▶. The overlay/layout + show-A/B-legend config moved into a rail
  **⚙️ Compare** popover; the A/B legend (static **and** animated overlay) is
  optional and hidden by default; the figure title is removed; each chip strip's
  trial id is coloured to its scanpath (replacing the A/B legend line). **Color
  fixations by** now works in compare too — it colours both scanpaths by the metric
  (shared scale), with the per-scanpath flat colour as the A/B marker outline; the
  redundant global saccade controls stay hidden.
- **Welcome tour walks the whole Scanpath screen in reading order** (plot →
  selection → chips → rail → panels → sidebar); the redundant *Exit* button is
  gone (the ✕ closes it).
- **Styling & chrome polish** — saccade arrows off by default, span-border colour,
  horizontal/rotatable colour bars, tighter control rail, less heading clutter,
  a dismiss ✕ on the welcome tour.

### Fixed
- **MultiplEYE reading text now aligns with the stimulus image** (BUG-3). The
  loader reads the real `FONT_SIZE` + font from the stimulus config and stamps
  them onto the data (`stimulus_font_px` / `stimulus_font_family`); on a dataset
  switch the app snaps its font controls to the exact size and CJK typeface (and
  off "scale text to boxes", since the precise px is known), so the word labels
  land on the printed text instead of being inferred ~3× too small in a generic
  font. The *scale-text-to-boxes* path also improved: the font is budgeted from
  the **line pitch** (not the glyph-tight box height) and the box-width cap is
  script-aware (full-width CJK vs half-width Latin, per word), so CJK corpora and
  mixed CJK+Latin lines size sensibly. OneStop sizing is unchanged.
- **Compare-mode fixations no longer turn black.** The per-scanpath colour pickers
  (rendered only when Compare is on) desynced to black and committed that on the
  next interaction; they now pass an explicit value and a falsy colour can't leak.
- **Trial filter resets on a dataset switch** (and is restored per-dataset when you
  switch back), so a stale filter can't silently apply to a different corpus.
- **Clearer image-export errors when Chrome is missing** — point to
  `kaleido_get_chrome` / the browser-free HTML export, with a pre-flight check and
  a warm→cold render fallback for the animation export.
- **Stimulus image now shows in Animate mode** (was static-only).
- **Switching public datasets re-detects the column mapping and snaps the canvas to
  that corpus' monitor** — fixes MultiplEYE pages collapsing into one trial and
  off-scale rendering.
- **Heatmap colour matches the picker** (default now blue; style uses a radio).
- **Save & restore captures every setting** — colour-bar orientation/ticks,
  fixation classification, span-border colour, and per-scanpath comparison styling.
- **Chips stay on one line** when space is tight.

## [0.22.0] - 2026-06-19

### Changed
- **Scanpath screen reworked for sidebar-closed use.** Visualization controls
  moved out of the sidebar into a **control rail beside the plot** (per-layer
  styling in popovers; **Animate** / **Compare** as toggle + popover; quick views
  trimmed and stacked). Selection is a **one-line row** above the plot — **Browse
  by** pills · trial selectbox · a **Filter trials** popover — with the scrubbing
  slider (showing the trial id) below. The view nav is sidebar menu buttons.
- **Browse-by** always offers Trial / Text / Participant: **Text** = one selectbox
  + a participant slider; **Participant** = the participant selector + a **Pick by**
  pill row.
- **Trial info → chips.** The Trial Info subtab is folded into a configurable,
  trial-level **`Field = Value` chip strip** above the plot (identity, conditions,
  and summary stats — reading time, word / fixation counts, in-box fixations),
  including the participant id and the compared trial when comparing. Per-trial
  subtabs are now **Annotations · Stimulus & questions · Export**.

### Fixed
- **Mark border** span overlay draws even when **Bounding boxes** is off.
- **Animation** starts paused at the configured speed instead of autoplaying.
- `CITATION.cff` version kept in sync with the package.

### Docs
- README, docs site, AGENTS, the welcome tour, and in-code comments updated for the
  three-tab layout + control rail; headless API docstrings clarified (it renders
  the full figure by default; the app opens on a minimal first view).

## [0.21.0] - 2026-06-18

### Added
- **Scanpath Visualization screen redesign (cognitive-load pass).** The plot now
  sits full-width at the top; a **Trial Selection** panel below it gathers the
  trial picker, the **Filter trials** controls (moved out of the sidebar), the
  **Compare with another trial** toggle, and **Animate** in one place. The
  per-trial panels became one full-width subtab bar under the plot —
  **Stimulus & questions · Annotations · Trial Info · Export**.
- **Quick-view presets.** One-click buttons in the Visualization panel
  (**Scanpath · Heatmap · Reading order · Everything**) set the layers for a
  focused picture instead of toggling each one.
- **Calmer default.** First load now shows just the core scanpath (text +
  fixations + saccades); the density **Heatmap** and the **Bounding boxes** grid
  are off by default and one click (or one Quick view) away.
- **Layer toggles + inline styling.** Each main layer (Fixations, Saccades, Text,
  Heatmap, Bounding boxes, Raw gaze) is now an `st.toggle` with a **bold** label,
  and that layer's styling appears inline only while it's on — no catch-all
  "advanced" drawer.
- **Sidebar navigation.** The top tab strip is replaced by a vertical menu at the
  top of the sidebar (Scanpath Visualization · Corpus Analysis · Data Inspection),
  removing the brittle client-side tab-persistence hack.
- **Consolidated Export.** The standalone **Bulk Export** tab is folded into an
  **Export** subtab with two sections — **This trial** (the live figure: static
  PNG/SVG/PDF/HTML, or the HTML/GIF/MP4 animation) and **Multiple trials** (the
  bulk export). Bulk export gained an **HTML** figure format, and its figure /
  config / tabular pickers were modernized (pills + a toggle).
- **About in the sidebar.** The About popover (version, authors, citation) moved
  to the sidebar **Help** group; **Share** stays in the header.
- **Setup-wizard progress indicator.** The upload wizard shows a native progress
  bar + step checklist driven by the actual upload/mapping state.
- **Trial Info table.** The trial id / participant / text now lead the metadata
  table (renamed **Trial Info**); the separate header block is gone.

### Changed
- **Streamlit 1.58** and all dependencies bumped to current latest;
  `use_container_width` migrated to the `width=` API.
- Cohesive visual polish (gradient title, refined tabs / expanders / buttons,
  pill-style id badges) that adapts to both light and dark themes.

### Fixed
- Saccade **direction arrows** no longer draw when the **Saccades** layer is off.
- **Highlight a span** is now an on/off `st.toggle` that reveals the
  Mark-text / Mark-border choice only when on (the "None" option is gone).

### Added
- **One Data Inspection tab.** The former **Raw Data** and **Data Statistics**
  tabs are merged into a single **Data Inspection** tab that, top to bottom,
  shows the headline dataset counts, every raw table (Stimuli, Word-level,
  Fixation-level, Raw gaze), the per-metric summary statistics, and a new
  **Column mapping** table.
- **Column mapping table.** Data Inspection now lists how each source column was
  mapped to the app's canonical fields (per table: Words/IA, Fixations, Raw
  gaze) — so you can confirm at a glance which of your columns became the
  participant, trial id, word box, fixation duration, and so on.
- **Share button.** A **Share** popover in the header builds a link that reopens
  the app on the current trial with your visualization settings (which layers are
  on, the colorscales, animation). The link uses the existing deep-link URL schema
  and a new `?trial_id=` param that lands on the exact trial regardless of how it
  was picked; copy it from the popover and send it. Works for the bundled demo,
  the synthetic trial, and the OneStop server bundle (an uploaded dataset can't be
  rebuilt from a URL, so the link then shares the view settings only, with a note).
- **Stimuli view.** A new **Stimuli** subtab (first under *Data Inspection*)
  reconstructs each passage from the word table — one row per Text ID with the
  full text rebuilt by joining its words in reading order, plus a word count.
  It honours the column mapping (groups by the mapped Text ID, uses the mapped
  word text) and dedupes shared stimulus words across readers.
- **Guided setup wizard for uploads.** Uploading now walks you through an
  incremental flow where only the step you still need to fill stays open
  (finished and auto-detected steps tuck away). You name the dataset and set the
  display up front, upload each table in its own toggle (each showing its row
  count — "✓ N fixations detected — make sure this is the number you expect"),
  then map the trial id, participants, texts, and required fields in collapsible
  parts. After loading it collapses into a compact **Data & mapping** panel you
  can re-open to tweak.
- **Reusable named datasets.** Finishing an upload saves it (under a name you
  choose) as a first-class data source. Switching between it, the bundled demo,
  and other datasets is instant — no re-uploading or re-mapping. Add another via
  the sidebar's **➕ Add data** button.
- **Optional participant & text.** Datasets without a participant column (a
  single anonymous reader) or without a text/passage column now load and
  visualize — the app fills sensible defaults and hides the Participant / Text
  selectors when a dimension has only one value. The wizard maps **Participants**
  and **Texts** in their own steps (mirroring the Trial id: one shared picker, an
  opt-in per-table override, and several columns composable into one id).
- **Choose the text-highlight column.** A new *Highlight words by* picker chooses
  which per-word column (the OneStop answer span by default, or any boolean
  column in your data) is marked on the reading text.
- **Pick the saccade colour.** A colour picker under *Saccades* sets the saccade
  line and arrow colour (two-trial comparisons keep their per-scanpath colours).
- **Saved configs record their export date** (and the data source + app version),
  shown when you restore one — including a confirmation line under the wizard's
  *Restore a saved setup* box naming where the loaded setup came from.
- **Keep only the fields you need.** The wizard auto-detects reading measures,
  linguistic features and condition columns and lets you drop the ones you don't
  need; everything unmapped is pruned before processing, which is the main
  speed-up on wide datasets (hundreds of columns).
- **Dynamic trial filters.** The **Filter trials** panel now offers a value
  picker for whichever condition fields your dataset actually has (and which you
  chose to keep), instead of a fixed set of OneStop-specific conditions.
- **Display calibration in the loading flow.** The **Experimental Setup**
  (monitor size, font, line spacing, background) is now part of the wizard, so
  the scanpath is true-to-scale from the first render; it stays adjustable from
  the sidebar afterwards.
- **PoTeC loader.** `sps.load_potec(root, download=True)` /
  `scanpath-studio render --potec` load the Potsdam Textbook Corpus end-to-end
  — its filename-encoded ids and separate character-AoI coordinates can't go
  through the generic upload flow. An in-app **Public datasets** source (with
  a dataset registry built for more corpora) ships feature-flagged off
  (`SCANPATH_PUBLIC_DATASETS=1` to preview); it will be enabled in a future
  release.
- **Step-by-step setup guide.** The upload wizard now has a short guided
  walkthrough — a **❓ Show setup guide** dialog that explains each step (naming,
  experimental setup, uploading, column mapping, and finishing). It opens
  automatically the first time you set up a dataset in a session and is
  replayable anytime.
- **Export your column mapping.** A **⬇️ Download setup** button next to **Add
  dataset** saves the current column mapping to a JSON file you can re-apply to
  similar data later via *Restore a saved setup*.

### Changed
- **Header buttons grouped together.** The **Share** and **About** buttons in
  the header now sit side by side with a small gap, instead of a wide blank
  between them.
- **Much faster on large datasets.** Switching trial, participant, or settings
  on a big dataset (hundreds of columns, many trials) is now near-instant
  instead of taking minutes — heavy work is cached and thinned, with a visible
  loading spinner while the first render builds.
- **One Visualization controls panel.** The former *Advanced styling* expander
  is merged into **Visualization controls**, grouped by layer (Fixations,
  Saccades, Text, Heatmap) with thin separators; per-layer size/colour/colorscale
  controls sit under each layer, and the fixation/heatmap colour-range sliders
  show whenever they apply (no longer gated behind *Show color bars*).
- **Clearer trial-id mapping.** One shared **Trial ID** picker applies to every
  table by default (with an opt-in *Different trial-id columns per table* toggle
  that keeps the columns you already picked instead of clearing them), and
  defaults to composing the participant and the finest passage id (paragraph,
  plus a repeated-reading column when the data has one, so the two readings of a
  paragraph stay distinct). If the per-table trial counts disagree the wizard
  says so.
- **Tidier wizard.** The mapping steps are grouped under **Column mapping** with
  one collapsible part each (trial id, participants, texts, **Column mapping:
  Fixations**, **Column mapping: Text & Interest Areas**, **More text mappings**,
  **More fixation mappings**); a single cross-table **Filter trials by** picker
  and a single **Additional fields to keep** picker replace the per-table
  duplicates; the upload boxes are narrower; and uploaded data defaults to a
  2560×1440 monitor. Niche fixation columns (pass index, saccade type/amplitude,
  eye) are auto-detected under *fields to keep* rather than mapped by hand.
- **Integer colour ranges.** The fixation- and heatmap-colour range sliders read
  as whole numbers instead of long decimals.
- **Refreshed the welcome tour** to match the current app (the *Experimental
  Setup* / merged *Visualization controls* panels, the guided upload).
- **Simpler data-source picker.** "Use bundled demo" is now **Bundled Demo**;
  the synthetic trial is no longer offered as a fresh source; a grayed-out
  **Public Datasets** entry previews what's coming.
- **Clearer Bulk Export controls.** The whole-dataset and filtered scopes are
  now both **All** / **All filtered trials** options inside the *Trials to
  include* picker (no separate checkbox), and the Scope section ends with a live
  "*N of M trials will be exported*" count. Figures are listed one per row
  (PDF → SVG → PNG), default to **PDF + Config** only, the plot-config checkbox
  is renamed **Config** with a short explanation, and the PNG-scale stepper is
  compact and only shown when PNG is ticked.
- **Faster bulk figure export.** Rasterizing PNG/SVG/PDF for many trials now
  reuses one persistent Kaleido browser for the whole batch instead of
  cold-starting Chrome per trial — quicker on large exports and no more
  per-trial "Resorting to unclean kill browser." log noise.
- **Clearer, numbered setup steps.** The wizard's sections are now numbered
  (1 Dataset name → 5 Filter & keep), the "upload to begin" prompt moved to the
  top of the upload step, and a tip points large-dataset users to running the
  app locally (`pip install scanpath-studio`).
- **See your uploaded tables.** Each table's upload box stays open after
  uploading and previews its first rows, so you can sanity-check the columns;
  the participant and text counts now carry the same "make sure this is the
  number you expect to see" reassurance as the trial and row counts.

### Fixed
- **Animated scanpath replays at its real speed again.** The Play button forced a
  full figure redraw on every frame, so each frame also paid the ~50 ms cost of
  re-rendering the static word boxes + labels; on a long trial that dwarfed the
  per-frame budget and the replay crawled — far slower than its quoted time, and
  the speed slider stopped helping above ~×4. Every animated trace is now full
  length with not-yet-reached fixations masked out, so a frame only changes point
  positions and Play can use `redraw=False` (updating just those traces). The
  replay now actually runs at `reading time ÷ speed`.
- **Uploading a large EyeLink report no longer crashes the app.** Reports with
  sentinel values (e.g. `.` in the `CURRENT_FIX_PRECISION_MEASURE_*` columns)
  could read as a column mixing numbers and text, which crashed the cloud worker
  when the table was displayed — a full report would die on the cloud while a
  small one loaded fine locally. Uploaded CSV/TSV files are now parsed in a
  single pass so the column type stays consistent.
- **Colour bars no longer squash the scanpath.** Turning on *Show color bars* or
  colouring fixations by a categorical field used to shrink the plot and throw
  off its aspect ratio (the reading text then overflowed its word boxes). The
  colour bar / legend now sits in reserved margin, so the plot keeps its true
  scale either way.
- Dropped the stale **Reading regime** line from the Text & question panel, and
  fixed the per-trial annotations note that pointed at an *Annotations* sidebar
  panel that no longer exists (it lives in **💾 Save & restore**).
- **Word hover shows the real line number.** The word tooltip used to always say
  *Line 1* because it read the source `line_idx` column, which is usually a
  constant. It now infers the visual line from the word-box layout (the same
  clustering the by-line colouring uses), so each line reads correctly.
- **Fixation hover no longer shows *Pass #NaN*.** The fixation tooltip dropped the
  *Pass* line, which displayed `NaN` whenever the data had no pass/reread column.

### Removed
- **Noise-flag auto-filtering.** A mapped noise/validity column used to silently
  drop "noisy" fixations from every view with no way to turn it off. It's gone —
  every uploaded fixation is shown. If your data has such a column you can still
  keep it (via *fields to keep*) and filter on it explicitly.
- **Trimmed the data views.** Folding Raw Data and Data Statistics together
  dropped the second statistics row (mean fixation duration / saccade amplitude
  / regression rate / reading speed), the fixation-duration distribution plot,
  and the per-word measure picker, plus the per-table download buttons,
  pagination banner, and descriptive captions — keeping the merged tab focused
  on inspecting the tables and their mapping.

## [0.19.1] - 2026-06-14

### Added
- **Zipped tables.** Upload boxes now accept `.zip` archives (e.g.
  `data.csv.zip`) wrapping any supported format (csv/tsv/parquet/feather); a
  multi-member zip is concatenated like a multi-file upload.

### Changed
- Raised the max upload size from 500 MB to 5000 MB.

### Fixed
- **Save & restore** no longer crashes when files are uploaded — the upload
  widgets were being swept into the config's column mapping, which isn't
  JSON-serializable.
- Highlighted text in **Trial metadata** and **Paragraph & question** (critical
  / distractor spans, difficulty / preview rows) is now readable in dark mode —
  the light highlight backgrounds now pin a dark text color instead of
  inheriting the theme's light one.

## [0.19.0] - 2026-06-13

### Added
- **Dark mode.** Ships a polished dark theme for the app chrome (☰ →
  **Settings → Appearance**, or follows your OS). The scanpath plot stays light
  in both themes, so it always reproduces the experiment's stimulus faithfully.
- **Raw-gaze-only datasets.** Upload just a raw-gaze table (no words or
  fixations) and visualize the gaze trace — the Scanpath Visualization tab draws
  the time-coloured gaze scatter, the trial picker and Data Statistics work off
  the raw gaze, and the fixation-only views (animation, Generations) show a
  "needs a fixations table" note.
- **Upload a config to restore it.** The sidebar *💾 Save & restore* panel gains a
  JSON uploader that re-applies a previously downloaded config — layers, coloring,
  sizing, text/highlighting, canvas, axes, trial selection, and annotations —
  silently skipping anything that doesn't fit the loaded data.

### Changed
- **Reorganized layout & usability pass.** The **Animated Scanpath** tab folds
  into the main tab (now **Scanpath Visualization**) as an **Animate** checkbox;
  bulk export moves to its own **Bulk Export** tab (with an *export the whole
  dataset* option); **Multiple Comparison** is renamed **Generations (WIP)**.
  In the side panel: a **Trial Info** header (showing the compared trial's info
  too), the trial selectors below it, annotations above a collapsible metadata
  table, and an **Export** toggle. Participant-mode selection now offers trial
  index / text / trial id. Defaults flip to **Fixation index off, saccade
  arrows on**; "Color fixations by line" is now a `line` option in *Color
  fixations by*; Text-highlighting and Heatmap-style options grey out when their
  layer is off. The animation's playback speed, info box, and play / pause /
  restart + scrub controls all move into one place (speed + info under the
  Animate toggle, transport below the plot); default playback is now ×4. The
  monitor/font controls (renamed **Experimental Setup**) move under 📂 Data.
- **Plot configuration + Annotations merged into 💾 Save & restore.** One sidebar
  panel saves the full figure configuration, all annotations, **and** the data
  source + column mapping + app version to a single JSON file (and restores the
  settings + annotations) — capturing more state than before (text sizing,
  highlighting, background).

### Fixed
- **Animated scanpath text is now true-to-scale.** Its transport controls used
  to shrink the equal-aspect plot, leaving the word labels oversized relative to
  the boxes; the figure now reserves the control space without shrinking the
  plot, so the animation matches the static view exactly.
- **The tutorial is now a guided spotlight tour.** The welcome opens centered
  like a modal over a closed sidebar — appearing as soon as the page opens,
  not after the first full render; the following steps open the sidebar and
  drop to a corner card that scrolls the relevant panel into view and pulses
  an outline around it. The previous all-dialog style remains one constant
  away (`tour.TOUR_STYLE = "dialog"`).
- **README trimmed and refreshed** — a concise rewrite (264 → 157 lines)
  reflecting the current five-tab app, with a regenerated hero GIF and
  screenshot.
- **Simpler, more general column mapping.** The Words/IA word-box mapping is now
  a single coordinate-format selector (edges ↔ origin+size) plus four fields
  instead of eight, and column auto-detection matches names case- and
  separator-insensitively (`IA_LEFT`, `ia_left` and `Participant ID` all
  resolve). Required-field markers now match what the loader actually needs.
- **Search-engine discoverability.** Keyword-rich page title and tagline, so the
  `<title>` and the social/search description Streamlit Cloud serves to crawlers
  are no longer brand-only.
- **Mapping panels grouped under each upload box.** On the Upload source each
  table's column-mapping panel now sits directly beneath its own upload box
  (Words/IA, Fixations, Raw gaze), raw-gaze mapping is a first-class peer, and
  every field has a `?` tooltip describing what it is and how it's used.

### Fixed
- Animated scanpath order numbers no longer glide in from the top-left corner —
  they now snap on at their fixation. The labels render in a constant-length
  text trace, so a new number turns on in place instead of a fresh node
  flashing at the (0,0) origin before placement.
- The tutorial's Skip/Done buttons now close the dialog instantly instead of
  leaving it on screen for the ~10 s full-app rerun.

### CI
- **Leaner AppTest suite.** Data-independent integration tests now boot the tiny
  synthetic trial instead of the bundled demo (~10x cheaper per boot, in a
  single run), cutting the AppTest file ~4x. The bundled-demo render still gets
  guardrail coverage.
- **Parallel test runs.** `pytest -n auto` (via `pytest-xdist`) fans the suite
  across the runner's cores, roughly cutting the AppTest-dominated wall-clock to
  a third.
- **Faster dependency install.** The test job installs with `uv` (cached)
  instead of `pip`, trimming the install step that now dominates each run.
- Test on Python 3.14 (the version Streamlit Cloud runs); CI now runs on pull
  requests only. Added a supported-Python-versions badge to the README.
- Added a pull request template (`.github/pull_request_template.md`) with a
  summary/verification prompt and a checklist mirroring the CONTRIBUTING and CI
  checks (tests, ruff, `[Unreleased]` changelog, dependency manifests).
- The publish workflow now creates a GitHub release (with the matching CHANGELOG
  section as the body) on every `v*` tag, alongside the PyPI publish and Slack
  post; `scripts/changelog_notes.py` gained a `--format markdown` mode for it.

## [0.18.0] - 2026-06-11

### Added
- **Flexible dataset support.** Load multi-file datasets (several files, a list,
  or a glob — concatenated with a `source_file` tag), single-report datasets
  (words-only or fixations-only), stimulus-level word boxes (broadcast across
  participants), and AOI-sequence fixations (placed at word/character-box
  centers). TSV inputs are now read directly. The upload panel takes several
  files per table, and either table alone.
- **First-visit tutorial.** A welcome dialog walks through the app's main
  surfaces on first entry (suppressed for embeds and deep links); replay it
  anytime via **🎓 Show tutorial** at the bottom of the sidebar.

### Changed
- **Raw data is shown while the column mapping is incomplete.** A missing
  required column no longer halts the whole app — the uploaded tables render in
  the Raw Data tab so you can see the columns and finish the mapping.
- **About popover in the header.** The LaCC Lab / Code pill links are replaced
  by a single ℹ️ About toggle with credits, the code link, citation guidance,
  and more from the lab.

### Fixed
- The animated scanpath now honours the fixation colour options (Color
  fixations by / by line, colorscale, colour range, colour bar) like the static
  plot; previously they only affected the image. Colours are pinned to the full
  trial's range so they stay stable during playback. Dual-overlay replays keep
  the flat A/B colours.

## [0.17.0] - 2026-06-11

### Added
- **Headless CLI:** `scanpath-studio render` builds one trial's figure straight
  to `.html`/`.png`/`.svg`/`.pdf` (or `--animate` for the HTML replay) without
  launching the app — `--sample` or `--words`/`--fixations`, `--list-trials`,
  per-layer `--no-*` toggles. Bare `scanpath-studio` still launches the app.
- **Public Python API:** `import scanpath_studio as sps` →
  `load_scanpath_data`, `load_sample_data`, `list_trials`,
  `compute_word_metrics`, `plot_scanpath`, `animate_scanpath`, `save_figure` —
  the app's canonical figures, programmatically.

## [0.16.3] - 2026-06-11

### Added
- **Composite trial ids are spelled out in the trial header.** Each remaining
  part gets its own labeled line (e.g. `Repeated reading trial: False`) next to
  Participant / Text, instead of only the joined id.

## [0.16.2] - 2026-06-11

### Added
- **Composite trial IDs in the column mapping.** The *Trial ID* row of every
  Column mapping panel (Words/IA, Fixations, Raw gaze) is now a multiselect:
  pick several columns and the app builds a unique trial ID on the fly by
  joining their values with `_` — for datasets with no precomputed
  unique-trial column (e.g. OneStop-style participant + paragraph +
  repeated-reading). A multi-column choice is authoritative: it overrides any
  raw `unique_trial_id` column and skips the repeated-reading `_r2` suffix
  fallback. Selections that reference columns missing from a newly uploaded
  file are dropped and re-proposed automatically.
- **Composite trials are selectable by their parts.** When the trial id is
  composite, *Select trials by → Trial* breaks it into one cascading selector
  per component (e.g. Text → Participant → repeated-reading) — each narrowed by
  the previous picks — instead of a single opaque `a_b_c` dropdown, mirroring
  the existing Text / Participant modes. Single-column trial ids keep the plain
  unique-trial dropdown.

### Fixed
- **Single-trial data no longer breaks "Select trials by → Participant".**
  With one trial per participant (a one-trial upload, the synthetic source, or
  filters narrowing to one), the Participant picker rendered a one-option
  `st.select_slider`, which crashes the Streamlit frontend (`RangeError: min
  (0) is equal/bigger than max (0)`) and blanks the tab. The picker now shows
  the lone trial as static text. Affected every tab's trial picker (Interactive
  Plot, Animated Scanpath + its overlay, Multiple Comparison, Data Statistics).

## [0.16.1] - 2026-06-09

### Internal
- **Slack release notifications.** A successful PyPI publish now posts a message
  to the lab Slack (`#scanpath-studio`) — including these release notes — via a
  webhook in the `publish.yml` workflow. `scripts/changelog_notes.py` renders the
  matching changelog section to Slack mrkdwn. No changes to the packaged app.

## [0.16.0] - 2026-06-09

### Added
- **Export the animated scanpath as GIF or MP4** (in addition to the existing
  interactive HTML). The Animated Scanpath tab gains an export-format selector;
  GIF/MP4 rasterize every animation frame through Kaleido (the same headless
  Chrome the PNG/SVG/PDF export uses) and encode them — Pillow for GIF,
  imageio-ffmpeg (bundled ffmpeg, no system package) for MP4. The clip
  reproduces the on-screen Play exactly: every frame held for the average
  duration so the runtime equals the quoted playback time, the slider's
  "Elapsed: X.Xs" readout re-drawn as a per-frame annotation, and the
  play/slider chrome stripped. A single browser is kept warm across frames
  (`kaleido.start_sync_server` → `calc_fig_sync`), so rendering is ~0.1–0.25 s
  per frame instead of a ~10 s cold start each. A progress bar tracks the
  render, the result is cached in session state (so the download button
  survives reruns), and long readings can be capped to a fixed frame count
  (duration preserved) to keep export quick. MP4 is far smaller than GIF and is
  recommended for long readings. New module `scanpath_studio/animation_export.py`
  (+ `tests/test_animation_export.py`).

## [0.15.1] - 2026-06-06

### Changed
- **Multiple Comparison tab layout.** The model-generated scanpath grid now
  renders directly beneath the real scanpath, with the similarity-score table
  below it (previously the table came first). The grid is the visual payload
  compared against the real scanpath, so it now sits adjacent to it.
- **Cite Levenshtein (1966) as the source of NLD.** The NLD metric description
  now credits the underlying edit distance to Levenshtein (1966) and notes
  Eyettention (Deng et al. 2023) as a user of the same normalization.
- **Internal: de-duplicated shared geometry/timing helpers** (no behaviour
  change). Fixation→word-id bounding-box assignment now lives in a single
  `measures._assign_word_ids_single` (used by both
  `measures.assign_fixations_to_words` and
  `similarity.assign_single_trial_word_ids`); the recorded-vs-synthetic
  timestamp heuristic lives in `measures.rebased_fixation_onsets` (used by both
  the similarity time-curve and the animation clock); and
  `model_scanpaths._ordered_word_rows` now reuses `measures.cluster_word_lines`
  for its line-clustering fallback. The 50 px line-misregistration tolerance and
  the 0.5 real-timestamp threshold are now single module constants
  (`LINE_MISREGISTRATION_PX`, `REAL_TIMESTAMP_DWELL_FRAC`). The animation clock's
  threshold was reconciled to compare against the full summed durations (matching
  the documented intent and the similarity time-curve).

### Removed
- The two explanatory captions under the similarity table (the header-arrow
  legend and the per-metric description block). The table keeps its direction
  arrows and best-model highlight.

## [0.15.0] - 2026-06-06

### Added
- **Multiple Comparison tab.** Shows a real scanpath on top, then a grid of
  model-generated scanpaths over the same text, and a similarity table scoring
  each model against the real reading. Until real model outputs are connected,
  the model scanpaths are reproducible, reading-like **synthetic placeholders**
  (deterministic per trial; a 🎲 Regenerate button re-rolls them). The number of
  models is inferred from the data; a "Grid columns" control sets the layout.
- **Scanpath similarity metrics** (`scanpath_studio/similarity.py`): **NLD**
  (Normalized Levenshtein Distance on the word-index/AOI sequence — the metric
  reported by Eyettention) computed for real, with ScanMatch / MultiMatch /
  Scasim registered as labeled placeholders. Table headers carry a direction
  arrow (↓ lower-is-better / ↑ higher-is-better) and highlight the best model.
- **Fixation-index range slider** to window which fixations are drawn and scored.
- **Metric-convergence plots**: NLD vs cumulative fixation index and NLD vs
  elapsed reading time, one line per model, computed over the full reading.

## [0.14.0] - 2026-06-06

### Changed
- **Renamed the project to Scanpath Studio.** The PyPI distribution is now
  `scanpath-studio` (was `scanpath-visualization-app`), the import package is
  `scanpath_studio` (was `scanpath_visualization_app`), the console entry point
  is `scanpath-studio`, and the repository moved to `lacclab/scanpath-studio`.
  Update imports and reinstall: `pip install scanpath-studio`.
- `requirements.txt` now uses compatible-release pins (`~=`) so the Streamlit
  Cloud demo stays on a known-good minor without drifting.

### Added
- Project metadata and docs: `CHANGELOG.md`, `CITATION.cff` (GitHub "Cite this
  repository"), and `CONTRIBUTING.md`.
- A demo GIF generator (`scripts/make_demo_gif.py`) and README animation/screenshot.

### Fixed
- Release pipeline no longer double-fires: dropped the redundant
  `release: published` trigger and added `skip-existing: true`, so a re-run can't
  fail on an already-published version.

### Internal
- Single-source the version (`pyproject.toml` reads `scanpath_studio.__version__`
  dynamically), so a release bumps one file.
- CI cancels superseded in-progress runs (`concurrency`).

## [0.13.0] - 2026-06-06

### Added
- **Interpolated fixation heatmap** — a smooth, word-box-independent density over the
  fixations themselves (duration-weighted when the metric is duration, blurred with a
  numpy-only separable Gaussian). Selected via a new "Heatmap style" radio
  (Word boxes | Interpolated).
- **Saccade direction arrows** — an arrowhead at each saccade midpoint, rotated to gaze
  direction (accounts for the reversed, screen-space y-axis).

## [0.12.0] - 2026-06-06

### Added
- **Simultaneous second scanpath** in the Animated Scanpath tab — two readings of the
  same text co-animated on a shared real-time clock (per-reading rebased `timestamp_ms`),
  with blue/red trails, per-scanpath saccades and current-fixation highlights, a legend,
  and an elapsed-time slider. Opt-in via an "Overlay a second scanpath" toggle with an
  independent trial picker; defaults to another reading of the same text (preferring the
  same participant).

### Changed
- Unified the two animation builders into a single `make_scanpath_animation`; the quoted
  playback time now equals the real animation runtime (one timeline source).
- Lowered the per-frame floor from 50 ms to ~16 ms (one 60 fps frame), making the speed
  slider far more effective at high speeds.
- **Interactive Plot cosmetics:** moved the trial-metadata field picker into the sidebar;
  folded the reading-time / word-count / fixation-count stats into the trial summary table
  as rows; replaced the out-of-box caption with a "Fixations in word boxes → N / N" row;
  single-click "Download HTML" (headless Chrome via Kaleido now only spins up for
  PNG/SVG/PDF).

## [0.11.0] - 2026-06-03

### Added
- **Trial annotations** — per-trial favorites, tags, and notes held in session state, with
  JSON download/restore.
- **Trial filtering & grouping** — sidebar panel to filter by condition (Hunting/Gathering,
  difficulty, repeated reading, correctness) and by annotation state (favorites/tags).
- **Questions/answers panel** — reading regime, selected answer + correctness, and
  answer/distractor spans annotated with whether each was fixated.
- **Plot options** — background color (incl. gray), highlight + count out-of-text
  fixations, and color fixations by line.
- Trial metadata shown per-trial in the comparison view.
- **Synthetic ground-truth test trial** — a hand-built trial shared by the test suite and a
  new "Synthetic test trial" data source, so the visualization can be checked against
  documented expected values.

### Fixed
- Static image export (PNG/SVG/PDF) on Streamlit Cloud, which failed because Kaleido v1
  needs Chrome — ship `packages.txt` (chromium), add a browser-free HTML save format, and
  give a clearer error message.
- Bundled raw-gaze sample always filtering to 0 rows (it was recorded for a participant
  absent from the demo) — synthesize a raw-gaze path from a real bundled trial and add a
  regression guard.

### Changed
- Test suite grown from 85 to 114 tests.

[0.21.0]: https://github.com/lacclab/scanpath-studio/releases/tag/v0.21.0
[0.19.0]: https://github.com/lacclab/scanpath-studio/releases/tag/v0.19.0
[0.14.0]: https://github.com/lacclab/scanpath-studio/releases/tag/v0.14.0
[0.13.0]: https://github.com/lacclab/scanpath-studio/releases/tag/v0.13.0
[0.12.0]: https://github.com/lacclab/scanpath-studio/releases/tag/v0.12.0
[0.11.0]: https://github.com/lacclab/scanpath-studio/releases/tag/v0.11.0
