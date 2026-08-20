# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Rebuilt data-upload wizard with an honest experimental setup** (DATA-22)
- **Compare scanpaths across datasets** (CMP-8)
- **Overlay two datasets recorded on the same screen** (CMP-11)
- **Compare mode on the CLI and the Python API** (CMP-9)
- **Multipart trials** (DATA-21)
- **Use-case-specific tutorials** (UX-40)
- **Author scanpaths directly on the stimulus canvas** (VIZ-33)
- **Optional monitor-pixel coordinate grid** (VIZ-34)
- **Honest progress for every app export path** (EXP-6)
- **An easter egg in the header** (UX-39)
- **Rename a dataset after you have added it** (DATA-23)
- **Step both compared trials at once** (CMP-13)
- **Narrow the trial pool by a numeric range** (UX-49)
- **A warning when one trial id covers more than one reading** (VAL-7)
- **MultiplEYE: every screen of a trial, including the comprehension questions** (DATA-24)
- **Attach a table of participant metadata** (DATA-20)
- **A computation register and a methodology page** (VAL-5)
- **Thirty-one harmonised public reading corpora, each its own data source** (DATA-27)
- **Word-box geometry recovered in four tiers, and labelled with which one you got** (DATA-27)
- **Every public corpus on a share link** (DATA-27)
- **Harmonised corpora on the CLI and in the Python API** (DATA-27)
- **Harmonised corpora are marked (WIP) in the picker** (DATA-27)
- **Raw gaze gets its own colour, marker size and opacity controls** (UX-86)
- **Each tutorial can be told not to auto-show, on its own** (UX-85)
- **A `{dataset_name}` placeholder for plot titles and captions** (VIZ-36)
- **Attach a table of trial information** (DATA-29)
- **A benchmark that times every computation in the register at corpus scale** (PERF-4)
- **OneStop's real word boxes are recovered from its raw EyeLink export** (DATA-30)
- **Recorded fixation y is retained when it shares the word boxes' real coordinate frame** (DATA-31)

### Fixed
- **The dataset table's counts were the first dataset's, for every row** (DATA-32)
- **Trial-level source merging no longer emits pandas' empty-concatenation FutureWarning**
- **MultiplEYE no longer crashes when a cached word table has stale screen order** — the screen picker uses the fixation-onset order, which is authoritative for each reader, while other multipart metadata conflicts still fail loudly.
- **The Session page's panels no longer render on every view** (BUG-34)
- **A word's label sits centred in its box, not jammed against the left edge** (BUG-30)
- **Leaving the add-dataset wizard asks first, instead of switching to the half-built dataset** (BUG-31)
- **A greyed-out control in the plot rail no longer prints raw HTML beside its name** (UX-68)
- **The tracker starts on Windows, so its Save button works there** (BUG-33)
- **The tracker server reads its own files as UTF-8, not as the machine's locale codec** (ENG-40)
- **The tracker no longer silently overwrites edits made outside the page** (ENG-41)
- **Claiming a task created in the UI no longer breaks every later tracker save** (ENG-42)
- **A harmonised corpus loads by its published schema, not by guesswork** (DATA-27)
- **Wizard steps no longer collapse while you are editing them** (DATA-22, supersedes DATA-19)
- **The upload-size warning no longer appears when you run locally** (DATA-22)
- **Uploads are no longer capped at 200 MB outside the repo root** (DATA-22)
- **Adding a dataset no longer hangs after "Dataset added"** (PRE-6)
- **A public corpus now reports its declared monitor, not its data extents** (CMP-11)
- **Switching to a stored upload no longer keeps the previous source's monitor** (CMP-8)
- **Quick-view and full-monitor transitions keep the current visualization state** (BUG-20, BUG-21)
- **Participant narrowing keeps eligible trial-sort fields** (BUG-22)
- **Trial selection is always the same picker — selectbox, slider and ◀ ▶ arrows** (BUG-23)
- **Corpus Analysis no longer pools a multipart trial's screens into one word axis** (BUG-26)
- **Switching datasets no longer keeps the previous one's column mapping** (DATA-24)
- **Reset settings is visible in the plot rail without zooming out** (BUG-24)
- **Saccade amplitude is pixels everywhere, and EyeLink's degrees keep their own columns** (BUG-25)
- **A letter is one character advance wide, not one character plus an inter-word space** (BUG-27)
- **A Data-page tutorial step no longer offers to open the page you are on** (UX-40)
- **Starting a tutorial from the chooser now actually starts it** (UX-40)
- **The "Loading…" banner no longer lingers above a finished page** (DATA-26)
- **A column mapping the pipeline rejects no longer takes the whole app down** (BUG-28)
- **The AOI picker's participant/text counts were never shown, only the Fixations one's** (BUG-35)
- **Confirmation dialogs' buttons did nothing, and two destructive buttons had no confirmation at all** (BUG-36)
- **Plot-rail popovers now open reliably on the first click** (BUG-37)
- **A spreadsheet upload no longer fails on a dependency the package never declared** (BUG-41)
- **Clearing the recovery cache no longer fails when a file cannot be deleted** (BUG-42)
- **Three computation-log tests no longer fail on Streamlit's bare-mode warnings** (BUG-39)

### Changed
- **💾 Session is a dialog opened from the nav, not a top-level page** (UX-100)
- **The Data page is two screens: 📂 Available datasets and ✏️ Edit dataset** (DATA-35)
- **Clearer wording and a wider page: trial-picker help, Summary stats, page gutters, Automatic recovery** (UX-99)
- **Data, annotations, comparisons, export and plot controls are more compact and consistent** (UX-94)
- **Session is organized around recovery, JSON backup, reset and debug tools** (UX-96)
- **🔥 Overlays is gone — Heatmap and Raw gaze are their own plot-rail sections** (UX-86)
- **Compare mode puts both control lines above both chip strips** (CMP-16)
- **Deleting a dataset drops the computations derived from it** (UX-87)
- **The add-dataset page drops *Screen name* and every "still to do" badge** (UX-88)
- **The column mapping groups its rows by table, not by kind** (UX-89)
- **The add-dataset page objects only once you press Add, and then everywhere at once** (UX-90)
- **Every required field really does go red on a failed add, including Trial ID** (UX-91)
- **Confirming an auto-detected column clears its amber mark** (UX-92)
- **The wizard's two footer buttons are one matched pair** (UX-93)
- **The add-dataset wizard's two Help buttons are one ❓ Help popover** (UX-84)
- **The add-dataset wizard's mapping merges each table's identity and geometry fields into one two-line block** (UX-55)
- **Every plot-rail section is a toggle and a ▾ on one line, with its controls in a popover** (UX-80)
- **Stimulus typography moves beside the text it draws; the screen's physical geometry leaves the rail** (UX-81)
- **A zipped table may be up to 32 GB, and the caps are yours to move** (DATA-34)
- **A layer's settings stay readable while the layer is switched off** (UX-97)
- **Streamlit is upgraded to 1.62, with native no-wrap rows and viewport-bounded popovers** (ENG-43)
- **The dataset list is *Available datasets*: click a name to open, and the open row is tinted** (UX-77, UX-78)
- **Each dataset's counts are computed once and remembered** (DATA-32)
- **Deleting a dataset and leaving the wizard both ask in a modal** (UX-79)
- **Preprocessing is held back from the app until the next release** (PRE-22)
- **One 🧹 Filter section for the whole figure, replacing the per-layer filters** (UX-72)
- **Reset visualization is a button, not a popover holding one** (UX-73)
- **Each reading's title and chips are one line, under that reading's control line** (UX-75)
- **One control line on the Scanpath view — and the same line for compare's second trial** (UX-64)
- **A cross-dataset comparison names both corpora, not just the second** (CMP-15)
- **The datasets are a sortable table; editing a mapping looks like adding one, and deleting asks first** (UX-54)
- **Help is a menu that opens the tutorial, the FAQ and About over your work** (UX-65)
- **The add-dataset screen keeps one title row on screen while you scroll** (UX-66)
- **A mapping dropdown opens wide enough to read the whole column name** (UX-71, UX-57)
- **Each count sits under the field it counts, in small text** (UX-67)
- **Fixation fields run over two lines, and the AOI fields group together** (UX-55)
- **One menu: Scanpath, Corpus Analysis, Data, Session, Help** (UX-63)
- **The app's name is a wordmark in the header, not a heading on the page** (UX-62)
- **Animate and Compare are split buttons: the toggle, and a ▾ for its settings** (UX-68)
- **The Scanpath subtabs read `label | field`, so a panel fits on one screen** (UX-69)
- **The Word box and Recording setup match the rest of the wizard** (UX-57, UX-58)
- **Every wizard field's title sits above its control** (UX-53)
- **A mapping dropdown never truncates a column name** (UX-53)
- **One picker per table, and a whole theme on one row** (UX-53)
- **Choosing a mapping approves it; clearing one drops the suggestion** (UX-53)
- **A field's clear button is Streamlit's own, inside the select** (UX-53)
- **The wizard is two linear parts, with the dataset name above both** (UX-53)
- **Mapping fields share a row instead of one per line** (UX-53)
- **The setup page drops its summary card, and raw gaze joins the other tables** (UX-53)
- **The wizard is one part, and *Advanced* is gone** (UX-53)
- **Explanatory text on the setup page is hover-only** (UX-53)
- **The upload wizard is two parts, not seven steps** (UX-53)
- **A mapping row shows its state as a tint on the select, not a sentence beside it** (UX-53)
- **The Data page is denser, and its smallest text is legible** (UX-53)
- **One figure-settings contract now powers every renderer** (ENG-28)
- **Core module ownership is one-way** (ENG-28)
- **The visualization rail scrolls independently and packs controls more tightly** (UX-43, UX-44)
- **Every control row above the plot shares one column grid** (UX-47)
- **Figure & canvas is grouped instead of one long list** (UX-48)
- **A layer section's own toggle reads "Visible"** (UX-50)
- **One Data page — the source, the column mapping, the tables and preprocessing in one place** (DATA-26)
- **The menu bar is down to Help and Session** (UX-38)
- **Rail controls read as a form: label beside the field, not above it** (UX-51)
- **The sidebar is gone — a top menu bar and Streamlit's native top navigation replace it** (UX-38)
- **Nothing is hidden behind a URL param any more — debug mode and the ground-truth trial are both in the UI** (UX-37)
- **Drift correction and NLD similarity are not exposed in this build** (PRE-21)
- **The Data page has one heading level and folds its tables away** (UX-52)
- **The column mapping reads as a form, and hides what only multipart data needs** (UX-52)
- **The tutorials follow the app as it is today, and "explore a corpus" answers a real question** (UX-40)
- **The mapping's "auto-detected" note sits beside its field, and trial identity is its own section** (UX-52)
- **Participant metadata is a step of the upload wizard, groups a cohort, and can be trimmed on the way out** (DATA-20)
- **Tracker write-ups are structured fields, not bold-led prose** (ENG-38)
- **One-click status moves, and one home for everything waiting on you** (ENG-38)
- **CONTRIBUTING covers joining an in-flight project, not just opening a PR** (ENG-39)
- **The tracker records who has an item, and state.json stops conflicting on every pull** (ENG-39)
- **Three more corpora reconstruct their published screen, and one stops claiming a screen it never had** (DATA-27)
- **Zooming the plot magnifies it, instead of stretching the axes** (VIZ-38)
- **The trial control line reads as a form: a funnel, a titled sort row, and a dataset tooltip that is about datasets** (UX-98)

### Details

#### Added
- **A `{dataset_name}` placeholder for plot titles and captions** (VIZ-36) — `{dataset_name}` substitutes the name the dataset picker shows for the source the fixations and AOIs come from, so a figure can say which corpus it is. It reaches the title, the caption, the compare A/B legend labels and the bulk-export path pattern, because all four draw on the same `export.pattern_fields` vocabulary. The value is passed in rather than read from session state — `pattern_fields` is pure and also runs headless under `api.save_figure_layers` and `cli render`. An overlay draws two readings into one frame, so `dataset_name`, `participant_id`, `trial_id` and `text_id` each gain `_a` / `_b` variants; they are always defined (with `_b` empty when there is no second reading) so a pattern written in compare mode still validates and renders on a single-trial figure. Scanpath B resolves against its own dataset, which matters once CMP-8 lets it come from a second corpus.
- **Attach a table of trial information** (DATA-29) — the sibling of DATA-20's participant metadata, one grain down: a separate one-row-per-trial table attached on the 🗂️ Data page, whose columns then behave like fields in the data — trial filters on `filter_trialmeta_<name>` keys, chips, trial sorting, Data Inspection, and the save & restore round trip. The key is asked, never inferred: a table keyed by trial id alone describes a *text* and every reading of it inherits the row, while keying by reader **and** trial describes one *reading* — so the reader column is a picker that defaults to unset rather than being auto-filled from any plausible column. Like the participant table it is **never broadcast onto the word or fixation frames**: a trial constraint resolves to `(participant_id, trial_id)` keys applied through `filter_to_keys`, and the only join is `metadata.project_trials` onto the small per-trial `combos` frame. Duplicate rows that disagree are dropped and named, never resolved by taking the first. The export bundle, `render --trial-metadata` and `api.load_trial_metadata` are still to come.

- **Rebuilt data-upload wizard with an honest experimental setup** (DATA-22) — the generic upload flow is now six accordion steps (Your data · Trials & readers · Fixations & text · Recording setup · Extra fields · Name & add) in a new `wizard_shell.py`, with a clickable progress chip per step and a setup guide that highlights and scrolls to the step it is describing instead of narrating beside it. The recording setup moved *after* the upload and asks how each of three groups is known — *I know these* / *Estimate from my data* / *Use a named default* / *Skip* — with nothing preselected; **Add dataset** stays disabled until all three are answered, so an uploaded dataset can no longer silently inherit a 2560×1440 monitor, 597 mm/800 mm geometry or a 16 px font nobody chose. The answer rides with the dataset as a `measured | estimated | assumed | skipped` provenance, surfaced in the review table and Data Inspection, carried on the share link as `setup_prov`, and written into the saved-setup JSON and bulk export's `plot_config.json`. Values derived from a skipped group (px/degree, pt→px) are hidden rather than computed from a default. Per-keystroke trial counting, schema proposal, field scanning and character-box aggregation are now cached on the frame fingerprint behind labelled spinners.
- **Compare scanpaths across datasets** (CMP-8) — a **Compare with** picker above *Compare To* chooses which dataset scanpath B comes from: any loaded upload, the bundled demo, the synthetic trial, or a public corpus whose files are already where the app last looked (one that isn't shows *(needs setup)* rather than loading something else in its place — the compare picker deliberately cannot draw the folder/download controls that would set it up). B carries its own **Filter B by** controls, its own candidate pool, and its own screen: the two panels are drawn to their own monitors and a caption names both, since sizes are not comparable across them. Overlay is unavailable across datasets (it pools both readings into one coordinate space) and resolves to Side by side without forgetting the stored choice; a metric only one corpus ships falls back with a note instead of colouring one panel and blanking the other; and 👤 markers never fire, because two corpora don't share readers. Underneath, the throwaway compare frames namespace B's `participant_id` by dataset — two corpora holding the same `(participant, trial)` would otherwise render *the wrong scanpath*, silently — while everything user-facing keeps the real ids. New: a **pair export bundle** (figure + both scanpaths' tables + a manifest naming each side's dataset, trial and recording setup, so the comparison is reproducible), and the comparison on the share link as `compare=<participant>:<trial>` + `cmp_source=<dataset>`, which is also the first time compare mode has been shareable at all. Built on the per-dataset `SetupSnapshot` below.
- **Overlay two datasets recorded on the same screen** (CMP-11) — CMP-8 refused to overlay *any* cross-dataset pair, because pooling two readings into one axis range is meaningless across two monitors. That block was too coarse: two corpora recorded on the same screen already share one coordinate space, and the caption even said so ("…which happen to share a 2560×1440 screen") while still refusing. Overlay is now allowed whenever the two canvases match. If either dataset never *recorded* its screen — most public corpora don't, so their canvas is a shared default rather than a measurement — the overlay is still drawn, with a warning beside it: the app can't prove the two displays matched, but you usually can, and a matching canvas is real evidence rather than none. Two different screens still fall back to Side by side. Nothing is rescaled or reprojected to force an overlay; when the screens differ the layout still resolves to Side by side, now with the specific reason in the caption, and the stored Overlay choice is still never overwritten. An animated comparison co-animates both readings on one clock — an overlay — so it unlocks under the same rule instead of being refused outright. New **Stimulus from** control (⚙️ Compare options, overlay only): *Both* (default, unchanged), *A*, or *B*, because two datasets' word boxes coincide only when the text, font and wrapping are identical, so *Both* can otherwise stack two offset sets of rectangles under the two traces. The compare layout and stimulus source now also ride the share link (`cmp_layout`, `cmp_stimulus`) and the saved config — CMP-8 shared the *pair* but not how it was arranged, so a shared comparison always reopened as Overlay. **Scope note:** the item originally asked for an **Align by** control that rescaled each reading through its own monitor geometry (visual angle) or its text bounding box. That was dropped on the user's call — and no bundled corpus records the physical measurements a visual-angle mode needs, so it would have been unreachable for every built-in dataset. Tracked separately for if that changes.
- **Compare mode on the CLI and the Python API** (CMP-9) — compare mode existed only in the app and the share link; there was no way to build a two-scanpath figure from a script. `api.compare_scanpaths(words, fixations, trial_a, trial_b, …)` is that surface, taking `layout`, `compare_stimulus`, per-scanpath styles, a fixation-index window and drift correction, and accepting `words_b`/`fixations_b` to draw scanpath B from a *different* corpus — with the same participant-namespacing the app uses, since two corpora holding the same `(participant, trial)` would otherwise render one reading as two. On the CLI, `render --compare-with PARTICIPANT:TRIAL` plus `--compare-layout`, `--compare-stimulus`, `--compare-words`/`--compare-fixations`, `--compare-canvas` and the `--monitor-mm`/`--viewing-distance` pairs. Headless deliberately **raises** on an incomparable overlay rather than resolving to Side by side the way the app does: a user can see which layout they got, a script cannot, so silently returning a differently-shaped figure is the wrong failure. A second dataset is loaded from files only on the CLI; Python callers pass frames directly, so any loader works.
- **Per-dataset recording-setup snapshot** (CMP-8) — `experimental_setup.SetupSnapshot` records the canvas, physical size, viewing distance and typography a dataset was set up with, plus the provenance of each. Stored uploads persist it in their payload and through the on-device recovery cache; the source → monitor table is now one function (`app.resolve_source_monitor`) rather than two.
- **Multipart trials** (DATA-21) — an optional `screen_id` + positive `screen_index` extends the existing participant/trial key without changing legacy data. The loader validates matching reports, unique order, and per-screen canvas metadata; parent-global and screen-local clocks/indices coexist. The main view navigates one screen at a time, annotations support parent or screen scope, measures/saccades cannot cross coordinate spaces, Share/save state retains the screen, and bulk output gets deterministic screen folders. Explicit columns work in the upload wizard; arbitrary source selectors work through an API/CLI JSON manifest. `list_parts`, `plot_scanpath(screen=…)`, `animate_scanpath(screen=…)`, and `render_parent_trial` expose the same model headlessly, with user-selected instant or recorded animation gaps.
- **Use-case-specific tutorials** (UX-40) — **Help → Tutorials** now offers five short workflows: load/verify data, filter/annotate, build a publication figure, compare readings, and explore the corpus. Each entry states outcome, time, prerequisite, and availability; progress/completion are independent. Steps can open the needed top-level view or subtab, spotlight stable UI targets, restore the starting location on Exit, and link to matching written instructions. They remain available when the automatic welcome tour is opted out and do not mutate filters, annotations, data, or scientific settings.
- **Attach a table of participant metadata** (DATA-20, milestone 1) — a table of **one row per reader** — native language, age, a comprehension score, a group label — can be attached on the 🗂️ Data page under **👤 Participant metadata**, for any source rather than only for an upload. Its columns then behave like fields in the data with no allowlist to extend per surface: they narrow the trial pool (*More → By reader*, a multiselect per categorical field and a range slider per numeric one), sit in the chip strip above the plot, sort the trial picker, get their own Data Inspection table, and travel with the export bundle (`metadata/participants.csv`) and the saved session. The table is **never broadcast onto the word or fixation rows**: a participant-grain constraint resolves to a set of reader ids and folds into the existing participant filter, and the one join that does happen is onto the per-trial `combos` frame — which is what keeps a reader attribute distinguishable from a per-fixation measurement, in memory and in the exported bundle. Nothing is guessed: the join is reported before anything uses it (readers with no row, rows for readers you did not load, duplicates), and duplicate rows that *disagree* are dropped and named rather than resolved by a `groupby.first()` winner, so the field reads as missing. Attaching a table that forgets someone never removes them from the pool. Headless: `--participant-metadata FILE` on `render`, which prints the same join report, and `load_participant_metadata()` in the Python API. Round 2 finished the remaining surfaces: the table is now **step 5 of the upload wizard** (*About your readers*) — its main home, since a first-time uploader is answering exactly this question and would otherwise never meet the feature, with the Data-page section staying for the sources the wizard never runs for; a reader attribute can **group a cohort in Corpus Analysis**, offered in the group-field picker marked 👤 and translated to reader ids rather than joined onto the frames (a group matching nobody resolves to an impossible id, because an empty value list reads as *no constraint* and would have selected every row); and the export bundle gained a **per-field opt-out** — reader attributes are the most re-identifying thing an export can carry, so clearing a field drops it from `metadata/participants.*`, and clearing them all leaves the table out entirely rather than shipping a bare list of reader ids.
- **A computation register and a methodology page** (VAL-5) — every operation that derives or semantically changes a value you can see, export or fetch through the API is now catalogued once in `scanpath_studio/computations.py`: 64 entries across normalization, assignment, preprocessing, the reading measures, aggregation and statistics, similarity, unit conversion and display transforms, each with its exact formula, input columns, output name and unit, grouping keys, missing-data behaviour, imported-vs-computed precedence, code link, tests and consumers. It generates [Computations & methodology](https://lacclab.github.io/scanpath-studio/computations/), linked from ❓ Help, and it is test-pinned: every `aggregation.MEASURES` entry, every drift-correction algorithm and the similarity metric must map to an entry, every entry must point at a function and tests that exist, and the docs page must be current. Verification status is deliberately conservative — *Verified* means a hand-calculated oracle passes, not that a line of code ran, and tier B (comparison against an independent implementation) is systematically absent because #VAL-4 is on hold, so most scientific measures read *Partially verified* even where their oracle is exact. Two inconsistencies found while writing it were recorded rather than silently fixed, then fixed under their own items: the saccade-amplitude units (BUG-25) and the within-word letter scale (BUG-27) — an audit records what it finds and lets a separate change move the numbers, which is the whole point of the separation.
- **Author scanpaths directly on the stimulus canvas** (VIZ-33) — typed text now produces inspectable word geometry and one default fixation per word; click to add, drag to move, select/delete on the canvas, or edit stable-ID rows where X/Y are primary and target word is optional. Schema-2 authoring JSON preserves the layout and remains loadable from the app, CLI, and Python API.
- **Optional monitor-pixel coordinate grid** (VIZ-34) — a zero-anchored X/Y grid with automatic or manual major spacing is available in static, animation, and all comparison layouts, and round-trips through Share links, saved configs, the CLI, Python API, and bulk manifests without changing the default off-state.
- **Honest progress for every app export path** (EXP-6) — static, animation, and bulk exports now share visible stages, expose determinate counts only for real frames/trials, include encoding and zip finalization, retain successful downloads across reruns, and safely reuse identical static bytes by a full output signature.
- **An easter egg in the header** (UX-39) — triple-click the **Scanpath Studio** title. It lives entirely in the browser (one same-origin script bound to a triple click), so it adds no setting, no session state and nothing to the share link, CLI or headless API; it stays inert in embeds (`?embed=true`) and while a tour or tutorial is running, can't intercept a click meant for the app, and removes itself after a few seconds.
- **Rename a dataset after you have added it** (DATA-23) — the name you type in the wizard's last step used to be final: a dataset added as “Dataset 3”, or misspelled, kept that label in the Data source picker for the rest of the session, and the only fix was to upload it again. The 🗂️ **Data** page now names the active dataset at the top with an **✏️ Rename** control beside it, for datasets you added (a built-in source, the synthetic trial and the public corpora are named by the app or by the corpus, and the load path dispatches on that name). The new name carries the same rules as the wizard's — it cannot shadow a built-in source's label or overwrite another dataset's frames, and a clash is suffixed and reported rather than applied silently — and the selection, the comparison's second dataset and the on-device recovery cache all follow it, the cache by renaming its stored files rather than re-encoding them.
- **Step both compared trials at once** (CMP-13) — walking a *pair* of readings through a corpus took two clicks per step, one on each picker's ◀ ▶, and it was easy to lose your place. **⚙️ Compare options → Step both trials together** links them: ◀ ▶ on either picker now applies the same ±1 to both. It is "advance both", not "keep them aligned" — the two pools are different sizes (the compared list excludes the trial you are comparing, and a second dataset is a whole other corpus), so a side that reaches the end of its own list simply stays put while the other keeps going, and an arrow greys out only once *both* have run out. When the main trial moves, the compared candidate is re-found by its participant and trial rather than by its position or its label, since the candidate list is rebuilt relative to the new main trial — same-text 📄 first, then same-participant 👤 — so both would otherwise name a different reading. Off by default, and UI-only: a share link already names both trials, and the CLI and Python API render a stated pair. The compared trial is now also remembered by **identity** rather than by its label: the candidate labels are rebuilt relative to the selected trial (the 📄/👤 markers are computed against it), so moving the main trial to another text used to leave the compared picker's stored label matching nothing, and it silently fell back to the first candidate — a jump that looked random. When the compared trial genuinely leaves the pool (usually because the main picker just landed on it, and a trial is never a candidate to compare with itself) a caption now says so instead of swapping the panel silently. Linking also **pins the candidate order to Trial ID** for as long as it is on: the default order ranks the candidates relative to the main trial, so crossing into another text re-laid the whole list and the compared trial's position readout leapt — "12/24" against "22/23" — even though the step had landed on exactly the right reading. Stepping two trials in lockstep only means anything against a list that holds still. Un-linking restores whatever sort you had chosen; the pin is resolved per run and never written back over your choice.
- **Narrow the trial pool by a numeric range** (UX-49) — every filter in the **More** panel was categorical: a multiselect over a column's distinct values. On a numeric column — a comprehension score, a trial index, a reading time — that meant one option per distinct float, which is unusable. Such a column now renders as a **two-ended slider** instead, because a slider shows the column's spread (most of why you would reach for the filter) and a slider at full extent is visibly "no filter" where two number boxes are not. **Trials with no value are kept**: a range narrows, it doesn't exclude the unmeasured, and a caption says how many trials that covers so they don't look like the filter failing. One field was added to the offered set — **`TRIAL_INDEX`**, the presentation order — because every column the panel offered was categorical, so on the bundled demo and every public corpus the new slider had nothing to appear on; it is universal on EyeLink exports and is how you drop the start or the tail of a session when you suspect practice or fatigue effects. Everything else the panel offers is unchanged; what changed is that it reads their type. Only columns that are constant within a trial qualify, since a column that varies inside one (fixation duration, word surprisal) would cut a scanpath in half rather than drop a trial. A column with fewer than two distinct finite values renders no slider at all, and a whole-numbered column gets an integer slider — stepping in 1s and reading "3 – 17", not "3.00 – 17.00" — including an integer column that pandas widened to float because it carries a missing value. Compare mode's second scanpath gets the same control on its own dataset, and **✕ Clear all filters** resets ranges with everything else.
- **A warning when one trial id covers more than one reading** (VAL-7) — a Trial ID mapping that doesn't fully identify a reading concatenates several readings into one scanpath, and nothing said so: the figure rendered happily, looking like an ordinary trial with a lot of regressions. The app now checks the loaded dataset and, when it finds evidence, says so once under the menu bar with the **column that would fix it** — "`article_id` takes more than one value inside a trial; adding it to the Trial ID mapping would separate them" — because the column name is the remedy. 🗂️ **Data → Trial identity** shows the evidence, and says so when everything is fine too. Three independent signals: a word box appearing twice in one trial (structural — one row per word per reading is a property of the stimulus, and it needs no clock), a fixation id repeating, and a timestamp jumping backwards mid-trial (a second recording starting, not a regression). Checked on the whole dataset before any filtering, keyed on `(participant, trial, screen)` — a legitimate multipart trial restarts word ids per screen, so grouping by trial alone would report duplicates that are correct data.

- **MultiplEYE: every screen of a trial, including the comprehension questions** (DATA-24) — a MultiplEYE trial was modelled as *one stimulus page*: `trial_id` was `<stimulus>__page_0N`, so reading a whole text meant stepping through five unrelated "trials", and the comprehension question screens were dropped entirely. A trial is now **one reading of a stimulus** (`trial_id == text_id`), and its pages are DATA-21 **screens** — the corpus's own `page` values, ordered by first fixation onset rather than by name, so a reader who went back to page 2 is recorded in the order they actually read. **Question screens are included by default** and carry their own word boxes: the question stem and the four answer options, in geometric reading order across the answer blocks, resolved **per reader** from that reader's answer-layout version — two readers on the same question genuinely saw the options in different positions, so a single stimulus-level layout would have put every fixation on the wrong option for most of the corpus. Pass `include_question_screens=False` (or `render --no-question-screens`) for reading pages only. On the CLI, `render --source multipleye --trial <stimulus>` now resolves the stimulus id, which is the id the picker shows — it previously demanded the `__page_NN` form and raised on anything else. Loading the full 30-trial corpus got ~2.5x faster on the way (6.4 s to 2.6 s): the shared question-AOI file was being re-read once per reader-stimulus pair. **Breaking, deliberately:** an old share link naming `<stimulus>__page_01` no longer resolves, and lands on the app's "ignored bad URL param" path. On the upload path, a stimulus whose `*_aoi.csv` was not uploaded now has its fixations dropped with a logged warning instead of being kept box-less, because a screen present in one report and not the other is invalid under the multipart rules.

- **Thirty-one harmonised public reading corpora, each its own data source** (DATA-27) — thirty-one public eye-tracking-while-reading corpora — ~14.0 million fixations across 22,255 texts, in Chinese, German, Danish, Spanish, Persian, Russian, Dutch and English, plus the two multilingual MECO waves — can now be loaded after being re-derived into one common schema by the [EyeGenBench](https://github.com/EyeBench/EyeGenBench) pipeline and prepared into a local bundle by `scripts/prepare_eyegenbench.py`. **Each prepared corpus is its own top-level entry in the flat data-source picker**, tagged 🌐 and searchable beside the demo and the app's own public corpora — deliberately *not* one "benchmark" source with a corpus picker inside it, which would make the corpora harder to find than any other dataset and put the pipeline's name on something the user selects. PoTeC and OneStop ship both natively and harmonised and both are kept, the harmonised copy marked *(harmonised benchmark)*, because they are not the same data: one is the publisher's release, the other a re-derivation prepared for cross-corpus comparison. There is no download — the bundle is built locally, in a separate virtualenv with EyeGenBench installed, one corpus at a time so an interrupted sweep leaves a valid smaller bundle; the raw downloads are kept rather than cleaned up (the geometry recovery below reads them) and the script stops on a free-space guard rather than filling the disk. Of the 39 corpora the pipeline can load, 31 prepare and ship, seven need manual acquisition from their publisher (`celer`, the five CFILT corpora, `vqamhug`), and one (`etdd70`) fails inside the pipeline's own Zenodo downloader on a bare `assert` in `httpx`'s sync transport — which carries no message, so the prep script reports it with an empty reason. Repeated readings of the same text by the same reader are kept apart as separate trials rather than collapsing into one scanpath. With no bundle yet, the picker offers a single *set up a local bundle* entry carrying the directory input, so a bundle at a non-default path is reachable at all; new page: [Harmonised benchmark corpora](https://lacclab.github.io/scanpath-studio/benchmark-corpora/).
- **Word-box geometry recovered in four tiers, and labelled with which one you got** (DATA-27) — the benchmark harmonises the data but discards screen geometry, and a reading corpus without word boxes cannot be drawn. Geometry is recovered during preparation in four tiers, first hit wins: EyeLink's measured coordinates carried on the corpus's own text table; measured coordinates parsed out of the raw EyeLink export the pipeline downloaded; a layout reconstructed from the corpus's **published** display parameters (screen, font size, character width, line pitch, margin — collected for 22 corpora); and a synthesized layout on generic defaults when nothing is published. Which one you got is recorded per corpus (`real` / `reconstructed` / `synthesized` — 1 / 20 / 10 across the 31 corpora that currently prepare) and shown as a caption on the corpus's picker entry, because the difference is whether absolute pixel positions mean anything. Two honesty rules came out of building it. The tier is stamped **per paragraph** and the corpus-level value is the best tier *any* paragraph reached, so a "Real" badge that implied uniformity would overclaim — whenever some texts fell back the badge instead reads *measured word boxes for N of M texts; the rest fall back to reconstructed layout*. And a corpus that documents **no** screen declares no monitor at all: the fallback layout is laid out on a generic 1920×1080, and presenting that invented number as the corpus's screen would snap the canvas to a measurement nobody made, so the canvas falls back to the data's own extents instead. That rule has exactly one implementation (`eyegenbench.declared_monitor`), read by the app and by `render --eyegenbench` alike, so the same corpus cannot render at two different scales depending on which surface asked.
- **Every public corpus on a share link** (DATA-27) — a share link can now name the corpus it was built from: `?source=corpus&corpus=<slug>`, one generic token covering every entry the public-corpus registry returns, built-in and locally prepared alike. In practice **no public corpus was shareable from the running app before this**: the flat picker collapses a corpus's registry label to the generic "public datasets" choice, so the one branch that existed (OneStop's, from DATA-3) never fired outside tests, and a link built while a corpus was open silently described a different source. The slug comes from the entry's **stable identifier** — a prepared corpus's manifest name under a `harmonised-` prefix (`harmonised-provo`), a built-in's short name (`potec`) — never its display label, which is copy and gets reworded; the prefix is what keeps the two PoTeCs and the two OneStops apart, and a slug that two entries would answer to is **refused on both sides** rather than resolved to a guess, since opening the wrong corpus silently is the worst failure this can have. A recipient who hasn't prepared that corpus is the common case, not an edge case: the link names the corpus, says how to point at a bundle, and leaves their data source exactly where it was. The bundle directory never travels on the link — it is a local path, and it is the sender's.
- **Harmonised corpora on the CLI and in the Python API** (DATA-27) — `render --eyegenbench DIR --eyegenbench-dataset NAME` renders from a prepared bundle (corpus names match the manifest, case-insensitively) and works with `--list-trials` and everything else `render` offers; the canvas resolves through the same declared-monitor rule as the app. In Python, `load_eyegenbench(root, dataset=…)` returns the normalized `(words, fixations)` pair the rest of the API expects, `eyegenbench_datasets(root)` lists what a bundle holds without reading a single Parquet file, and `load_eyegenbench_participants` returns the per-reader table as DATA-20 participant metadata — never broadcast onto the word or fixation rows. A malformed manifest row degrades rather than raising: a row with no usable name is skipped, and an unreadable count is reported as unknown instead of taking the source list down.
- **Harmonised corpora are marked (WIP) in the picker** (DATA-27) — DATA-27 is on main before it is finished, so every harmonised corpus entry — and the *set up a local bundle* placeholder — reads **(WIP)** in the data-source picker. It is a formatting step applied where the option is rendered, not a change to the entry: the value the picker stores, the `?corpus=` slug on a share link and the key a saved config carries are all untouched, so removing the marker later invalidates no link and no config written while it was up. The app's own public corpora (PoTeC, MultiplEYE, OneStop) are finished work and stay unmarked — the marker keys on a registry entry's `benchmark_dataset` rather than on the words in its label, which is what keeps the natively-shipped PoTeC clear of the harmonised one beside it.
- **Raw gaze gets its own colour, marker size and opacity controls** (UX-86) — raw gaze was one toggle with no styling of its own (fixed grey dots, size 4, opacity 0.6, hard-coded in `plots._add_raw_gaze_layer`). Its new ⚙️ style popover adds all three (`global_raw_gaze_color`/`_marker_size`/`_opacity`), reaching the plot, the Share link and the headless API (`plot_scanpath(..., raw_gaze_color=…)`, already reachable through the builder's existing `**figure_overrides`). The colour only applies when the data carries no `timestamp_ms` — a dataset that does keeps the more informative Viridis time-mapping, same as before. Not yet wired into the CLI (raw gaze has no `render` flag at all, a pre-existing gap) or the 💾 Save & restore JSON.
- **Each tutorial can be told not to auto-show, on its own** (UX-85) — #UX-12's *Don't show this again* gates only the automatic welcome card. Every card in the 🧭 Tutorials chooser now has its own **🔕 Don't auto-show this one** checkbox, backed by one `sps_tutorial_optout` cookie holding the *set* of dismissed tutorial ids (not one cookie per tutorial). Dismissing a tutorial never removes it from the list — #UX-12's rule, "stop greeting me" not "take it away" — and Start/Resume are unaffected either way. Nothing in the library auto-opens itself today, so this has no visible effect yet; it is the opt-out for whichever tutorial starts doing that next.
- **A benchmark that times every computation in the register at corpus scale** (PERF-4) — `benchmarks/computation_benchmark.py` walks the pipeline in dependency order — normalize → assign → measure → preprocess → aggregate, then the per-trial similarity, drift-correction and figure builders — timing each stage with wall clock and RSS delta and tagging it with the `computations.py` entry ids it exercises, so a row reads next to `docs/computations.md`. All 65 register entries are covered. `--participants N` is the scale knob and stops the reader after N readers rather than parsing a whole multi-gigabyte export, so the same command profiles the bundled demo or the full OneStop reports; `--skip` drops stages that cannot finish at the scale being measured. Nothing in the app changed — the first run's numbers (360 OneStop readers, 24,046 trials, 2.4 M fixations) are written up in PERF-4, and the three fixes they argue for are PERF-5.
#### Fixed

- **The dataset table's counts were the first dataset's, for every row** (DATA-32) — the helper that counts a dataset took its cache key as `_key`, and `@st.cache_data` **skips underscore-prefixed arguments** when building its key (that is how the frames are passed without being hashed) — so the fingerprint was skipped too and the cache held exactly one entry. Every dataset after the first was served the first one's numbers. It was invisible only because UX-54's second round had narrowed the table to counting the open dataset alone; counting several rows, which DATA-32 does, would have shown identical counts down the column. The parameter is `key` now.
- **The Session page's panels no longer render on every view** (BUG-34) — 💾 Save & restore, 🗄️ Recovery cache, 🧹 Start fresh and the 🐛 Debug toggle appeared above every screen. They are rendered on every run on purpose: the widgets inside are gates whose keys Streamlit drops if they do not render (the debug toggle *is* the debug gate; the persistence toggle governs what is written to disk), so the copy that is not the active page is hidden by key rather than skipped. That hiding rule had been lost — retiring the Help page's off-screen twin left the Session selector dangling on a comma, folding it into the *next* rule's selector list, and a stylesheet does not raise when a selector stops matching. The rule is restored and a test now asserts that each off-screen page key carries a `display: none` rule of its own.
- **A word's label sits centred in its box, not jammed against the left edge** (BUG-30) — labels were anchored at the box's leading edge, so whatever room the text did not fill showed up entirely as a gap on the *trailing* side and none on the leading one. On the bundled demo the drawn text covers 77–91% of its box, which is a visible 9–23% of empty box after every word and nothing before it. The label is now centred in the box **as drawn** — `measures.word_box_bounds`, not the raw frame — which is what keeps it a no-op where it should be one: on a corpus whose AOI boxes tile the line, BUG-11 already pulls every edge back half a space, so the corrected centre coincides with the glyph run's (415.0 against 416.3 for the demo's first word), while on a corpus whose boxes hug the glyphs the padding now lands half on each side. Centring retired the separate LTR/RTL anchoring as well; the Unicode direction isolates stay, because they shape mixed runs rather than place them. **No AOI edge moved and no reading measure changed** — this is the rendering, deliberately not the extents.
- **Leaving the add-dataset wizard asks first, instead of switching to the half-built dataset** (BUG-31) — opening the wizard made the *in-progress* upload the app's active source immediately, so navigating to Scanpath mid-setup reported "this dataset isn't set up yet, so there's nothing to plot" over a session that still held every finished dataset — it read as data loss when it was an unfinished wizard. The 🗂️ Data page now stays on screen while the wizard is open, wherever the nav says you are, and the wizard asks: *Leave setup and go to ⟨view⟩? This dataset isn't added yet — the files you uploaded won't be kept*, with **Keep setting up** and **Discard and leave**. It says the files go because they do: `st.file_uploader` is the one widget `persist_state` cannot save, so "park it and come back" is not something the app can honestly offer. Nothing in the fix navigates, and that is the point — every way to move the router ends in `st.switch_page`, which aborts the run it is called in, and a run that renders no wizard is exactly what would throw the uploads away. So the nav highlight is left on the view you clicked while the page under it asks, and discarding needs no navigation at all.
- **A greyed-out control in the plot rail no longer prints raw HTML beside its name** (UX-68) — every rail row draws its title as an HTML `<span>` carrying the description in a `data-tip` attribute (UX-51), and `controls._gated_help` joins a mode-gate warning to that description with a **blank line**. A blank line ends a raw-HTML block in markdown, so the opening tag was cut in half and the remainder of it — `data-tip="…" aria-label="…">` and all — rendered on the page as literal text wherever a control was greyed out. `_plain` now collapses every run of whitespace before the text reaches the attribute, which a one-line tooltip wanted anyway. Found while building UX-68's greyed settings menus, but it affected every mode-gated control in the rail.
- **The tracker starts on Windows, so its Save button works there** (BUG-33) — reported as a dead Save button, but the button never ran: `saveState()` returns before issuing the request unless a `GET /tracker/api/state` succeeded on load, and the server logs across the affected sessions contain no `PUT` at all. Neither documented way to start the tracker works on Windows — `tracker/start.command` is a zsh script, and `python3` there is normally the Microsoft Store alias, which prints *"Python was not found"* and exits 9009 without starting anything — so the page ends up opened from the filesystem, where `file:` short-circuits straight to the offline view and every edit is unsaveable. Adds `tracker/start.bat` (tries `py`, then `python`, never `python3`; explains itself and pauses rather than vanishing when Python is absent), makes the offline screen name the launcher and command for the *viewer's* platform instead of macOS's, and corrects `README.md` + `CONTRIBUTING.md`. The write path itself was healthy all along — a hand-issued `PUT` returned `200` — and BUG-33 is the second half of the same Windows story as ENG-40 below, which had been taking `GET /api/state` down with a `UnicodeDecodeError`.
- **The tracker server reads its own files as UTF-8, not as the machine's locale codec** (ENG-40) — `tracker/server.py` read `data.js`, `state.json` and `.local.json` with a bare `Path.read_text()`, which decodes using the *process locale's* codec. On a Hebrew-locale Windows clone that is cp1255, so the first em dash or emoji in a write-up — and the write-ups are full of both — raised `UnicodeDecodeError: 'charmap' codec can't decode byte 0x9c`. The failure was quiet in the worst way: the server still started and still served the page, but every `GET /tracker/api/state` 500'd, so the tracker rendered the `data.js` catalogue with no state layered on top of it — no status overrides, no owners, no UI-created items, and nothing that could be saved. Every text read and write of the three files now passes `encoding="utf-8"` (the atomic save path already did, so saves were fine and only reads were broken), and `tests/test_tracker_server.py` — which carried the same bare reads and so failed 9 of its 26 tests on the same machine for the same reason — was pinned alongside it. Invisible on macOS and in CI, both of which already run a UTF-8 locale; Python 3.15 defaults to UTF-8 mode and will retire the class of bug, but not for anyone on 3.11–3.14. Only the tracker was audited — the app's own file I/O has not been swept for the same pattern.
- **The tracker no longer silently overwrites edits made outside the page** (ENG-41) — reported as "the tracker isn't saving things", with a malformed item suspected; nothing was malformed and the save path was healthy. The page holds the whole state in memory from load and `PUT`s all of it on every save, so any write to `tracker/state.json` from elsewhere — an agent editing it by hand as `CLAUDE.md` instructs, another tab, a `git pull` — was overwritten wholesale on the next click. The guard that should have caught it could not: `revision` was a counter in the gitignored `.local.json` that only the API bumped (ENG-39), so a direct file write left it untouched, the stale page's token still matched, and the page reported *Live · saved to project* over the edits it had just erased. `_state_revision()` now derives the token from `state.json` itself (a 48-bit slice of its SHA-256), replacing `_read_revision` / `_bump_revision` — any write by anyone moves it, so a stale save is a `409` instead of a silent overwrite, and nothing revision-shaped is stored in the repo, which is what ENG-39 wanted. A conflict used to surface as *Save failed* in the corner chip, indistinguishable from the server being down; it now paints a sticky banner naming the cause with a **Reload now** button. Reproduced before the fix and re-run after it: the hand-written canary survives, a reload picks it up, and the next save goes through.
- **Claiming a task created in the UI no longer breaks every later tracker save** (ENG-42) — the red *Save failed* chip, and a different bug from ENG-41 above, which was silent. `initializePersistence` pushes each `createdItems` entry into `ITEMS` / `BY_ID` by reference, so one object is shared between the catalogue and the outgoing payload; `stageEditor` then assigns `{status, priority, owner, implementationBrief, archived}` straight onto it. `owner` was not part of the created-item contract on the server, so editing or **Claim**ing a UI-created task stamped an unknown key onto `createdItems` and `_validate_created_item` rejected the payload with *Invalid created tracker item.* Because the page `PUT`s the whole state at once, that one poisoned object then failed **every** save from that page — for every item, not just the created one — until reload. `owner` is now in `CREATED_OPTIONAL_FIELDS` and validated against `TRACKER.people` like any other owner; optional rather than required, since created items written before ENG-39 have no owner key.
- **A harmonised corpus loads by its published schema, not by guesswork** (DATA-27) — a prepared corpus has a known schema, and every surface loaded one through it except the app, which re-guessed the mapping from column names. That is right for an upload and wrong here: the prepared frames carry the publisher's ~190 original columns through beside the harmonised ones, and auto-detection preferred some of them. **EMTeC** ships a `TRIAL_ID` that outranks `unique_paragraph_id` on the fixations while the word boxes still key on `unique_paragraph_id`, so the two joined on nothing: the corpus opened with **zero word boxes** — no stimulus, no interest areas, no word-level measure — and said nothing, because only the words frame was empty and the empty-pool guard needs all three. **Provo** and **SBSAT** ship a `page` column that reads as a multipart screen id on the fixations alone, which is rejected outright, so they could not be opened at all. The same three corpora were always correct on the CLI, in the Python API and as a comparison's dataset B — two surfaces disagreeing about one corpus was the tell. The app now starts from the corpus' declared mapping and lets auto-detection fill in only what the corpus says nothing about, so optional passthroughs still arrive; the Column-mapping panels stay editable, and a field the corpus declares as absent is now stated as absent rather than left for the detector to claim.
- **Switching datasets no longer keeps the previous one's column mapping** (DATA-24) — a mapping dropdown owns its value once it has rendered, which is what makes an override stick; but the app switches data sources *in place*, so those choices outlived the table they described. Opening the bundled demo (no screen columns, so **Screen order** = `(none)`) and then switching to MultiplEYE left that field on `(none)` while the caption under it still read "✨ auto-detected `screen_index`" — auto-detection had found the column and only the dropdown was stale, so a multipart trial ordered its screens by name instead of by reading order and you had to set a field the app had already worked out. A mapping is now recognised as belonging to a *table*: when the columns change, a field left at `(none)` or pointing at a column that is gone goes back to auto-detection, while a pick that still names a real column stands — the upload wizard grows its own frame mid-flow (`file_part_N`), so a column change is routine there and must not reset the steps you already filled in. Within one table the dropdown stays authoritative, so a field you deliberately cleared is not quietly re-detected. `(none)` also gets its own caption wording (“· not used”), since it used to read exactly like a field that *was* using the detected column.
- **Saccade amplitude is pixels everywhere, and EyeLink's degrees keep their own columns** (BUG-25) — `saccade_amplitude` meant two different quantities depending on which columns an export happened to carry. EyeLink writes `NEXT_SAC_AMPLITUDE` / `PREVIOUS_SAC_AMPLITUDE` in **degrees of visual angle**, and both were mapped onto the canonical name; when neither was present the app computed a euclidean **pixel** distance instead. Nothing recorded which one you got, and `aggregation.MEASURES["sacc_amp"]` labelled the axis `px` either way — so the bundled demo's saccade-amplitude figure read *1.95 px* for what is a ~2° reading saccade, against a true pixel median of 151. The canonical column is now always pixels (the app's own computation, or a source column of that name), and the two EyeLink columns normalize to `next_saccade_amplitude_deg` / `prev_saccade_amplitude_deg` — separate from the pixel measure *and* from each other, since they describe different saccades (the one leaving this fixation and the one that arrived at it) and the shared name also shifted the column by one fixation relative to `progression` / `is_regression` / `angle_outgoing`. They stay available for colour-by, hover and filters under their own names. No conversion is attempted in either direction: that would need `pixels_per_degree`, which is `ASSUMED` on every built-in corpus.
- **A letter is one character advance wide, not one character plus an inter-word space** (BUG-27) — the within-word measures divided the word box by its character count (`width / len(text)`). On a corpus whose AOI boxes tile the line, each box carries the *following space* as trailing padding — it is `len(text) + 1` advances wide — so every letter was reported too wide, by a factor that **varied with word length** (+33% on a three-letter word, +7% on a fifteen-letter one), which distorts the shape of a landing-position-by-word-length curve rather than just shifting it. `measures.word_char_advance` is now the single accessor for that scale, the way `word_box_bounds` is for the boundary *between* words, and all three call sites read it: initial landing position and centred landing distance, a saccade's launch/landing letter, and the AN-12 landing curve — which also moves its origin from the BUG-11-corrected AOI edge back to the word's `x`, so its documented "0 = word start, 1 = word end" is finally true. On the bundled demo the advance is a flat 19 px for every word where the old formula gave 21.4–25.3 px; a mid-word landing on a five-letter word now reads ~3.7 letters instead of ~4.3. The correction stays conditional on the same detector BUG-11 uses, so glyph-tight corpora (PoTeC, MultiplEYE) are untouched. Found by #VAL-5's audit and split out of it deliberately.
- **A Data-page tutorial step no longer offers to open the page you are on** (UX-40) — the tutorial's "is the right surface visible" check predated DATA-26's third top-level view and folded everything that was not Corpus Analysis into Scanpath. A step targeting the 🗂️ Data page therefore reported *not open* while the user was standing on it: the card showed **Show me / Open this panel** for a panel already on screen, and withheld the spotlight that belonged on it.
- **Starting a tutorial from the chooser now actually starts it** (UX-40) — an `st.dialog` body is a fragment, so the chooser's `on_click` reran only the dialog. The state it wrote never reached the page: the modal sat there unchanged and the task card it was meant to hand over to was never drawn.
- **The "Loading…" banner no longer lingers above a finished page** (DATA-26) — the view-switch bridge cleared itself with `container.empty()`, which *appends* an empty child rather than dropping the children already written. The banner and its skeleton survived the clear and sat above the finished page until some later rerun happened to redraw the slot.
- **A column mapping the pipeline rejects no longer takes the whole app down** (BUG-28) — mapping `screen_id` on the fixations report and not on the words report replaced the entire app with a `ValueError` traceback ("Multipart identity is present in only one report…"), and the controls that could undo it were on the far side of the exception: the Column-mapping panels are written *during* the run that died, and the 🗂️ Data page they live on is hidden while another view is active — so from the Scanpath view the crash left the top nav and nothing else. The refusal itself is correct (with a screen id on one side only, every fixation would be matched against every screen's word boxes); treating it as fatal to the session was not. A rejected mapping now recovers exactly like an incomplete one — the error and its reason on the Data page, the raw tables under it, the mapping panels still editable, and a signpost from whichever view you were on — plus **↩️ Reset to the auto-detected mapping**, which drops every stored `col_map_*` pick, including one restored from the on-device recovery cache. The upload wizard's two paths (generic and the MultiplEYE preset) do the same: the wizard stays up with the reason against its review step and **✅ Add dataset** disabled. The exception is logged with its traceback, so the 🐛 Debug panel and the terminal keep the full story. Nothing was ever cached that had to be cleared by hand — `st.cache_data` does not store exceptions — but the stored mapping could survive a refresh, which the reset button now handles.

  Two escape hatches that don't route through the 🗂️ Data page came with it, because being sent to a page to fix a dataset is not always what you want — sometimes you just want something that draws. The signpost offers **🧪 Load the bundled demo** beside *Go to Data setup* (it switches source *and* re-detects the mapping, so it works even when the wedged dataset is the demo), while Session's confirmed **Reset everything** clears the live and recoverable state. Session's reset controls are filled before data loads: every path where the dataset cannot be drawn returns early, so a recovery action rendered only in `main`'s epilogue would disappear precisely when it is needed.
- **The AOI picker's participant/text counts were never shown, only the Fixations one's** (BUG-35) — *Map data fields*' Participant ID and Text ID steps count a *single* table and caption only the Fixations cell, whatever the AOI row is mapped to — so a mismatched AOI mapping (in the reported case, AOI Participant ID pointed at `combo_id` and Text ID at `line_number`) had nothing under it to catch by comparing two numbers side by side, the exact thing #UX-67 r2 put the numbers there for. The trial step next to it already counted each present table separately; the participant/text step now does the same.
- **Confirmation dialogs' buttons did nothing, and two destructive buttons had no confirmation at all** (BUG-36) — *Delete this dataset?* and *Leave setup?* opened, but **Delete it** / **Keep it** and **Keep setting up** / **Discard and leave** did nothing: an `st.dialog` body is a fragment, so an `on_click` callback inside it reran only the dialog, wrote its session state, and then `main()` never re-executed to show the result — the same trap #UX-40's tutorial chooser hit first. Both are handled by the button's return value now, closing with `st.rerun(scope="app")`. **✕ Cancel** inside the wizard used to call `leave_add_data_wizard` directly, discarding an in-progress upload with no confirmation at all; it now raises the same *Leave setup?* prompt, targeting 🗂️ Data. **♻️ Reset visualization** and both 💾 Session cache buttons (**🧹 Clear cached computations**, **🗑 Forget saved session**) gained a confirmation too — each states plainly what it keeps and what it drops before acting. Three follow-on issues the working buttons then exposed: navigating to the 💾 Session page while the wizard was open and choosing *Keep setting up* still showed the Session page underneath, because that page is a CSS-keyed panel `menu.render_top_menu` draws for itself, early in the run, from the *raw* nav click — `app.main` now resolves the wizard's hold-the-view override before calling it, not after; confirming 🗑 *Forget saved session* raised a `StreamlitAPIException`, because writing the *Keep saving here* toggle's own key after that toggle had already rendered this run is exactly what its old `on_click`-only design existed to avoid — the confirm handler now pops the key instead of assigning it, same as `reset_viz_settings` already does; and clicking Session in the nav, *Keep setting up*, then ✕ Cancel → *Discard and leave* still landed back on Session instead of 🗂️ Data — `discard_and_leave_wizard` assumed the nav was already sitting on wherever it should end up (true for a nav-triggered prompt, false for Cancel's fixed Data destination), so it now requests that destination through the same `main_nav` seam the rest of the router uses.
- **Plot-rail popovers now open reliably on the first click** (BUG-37) — every section of the 🎛️ Plot controls rail (👁️ Fixations, ↗️ Saccades, 📄 Stimulus, 🔥 Overlays, 🧹 Filter, 📐 Figure & canvas, plus 🎬 Animate and ⚖️ Compare) opens through the same `st.popover(...)` call with an empty `""` label, since the trigger carries no text of its own. In this Streamlit version a popover is a stateful widget — `key`/`on_change` are part of its signature, exactly like `st.expander` — and without an explicit `key` it falls back to a positional auto-key. Downstream of several booleans that change which widgets render (`_mode_gate`'s `disabled=`, the layer toggles), that auto-key could shift between reruns, which reads to Streamlit as a brand-new widget and drops the one thing it tracks: whether it is open. Every other popover in the app carries a distinct label (🔎, ⇅, Details, …) and was unaffected. Each of the eight now carries an explicit, slug-based `key`.
- **Wizard steps no longer collapse while you are editing them** (DATA-22, supersedes DATA-19) — a step's open state used to be recomputed from whether it was "done", and "done" flipped on the *first* pick, so the expander shut under the cursor mid-edit; DATA-19's one-shot marker survived exactly one rerun. The accordion is now a keyed `st.expander` whose flag is written only by the shell's own navigation (`seed_open_step` / `go_to_step` / the progress chips / the guide), so an edit inside a step cannot move it. **Its header is also held constant**: Streamlit remounts a keyed expander at its collapsed default on the next run after its label *or icon* changes, so carrying the step's status badge as the expander icon slammed *Your data* shut the instant an upload finished — the same symptom through a different mechanism. The badges now live only on the progress chips. `_wizard_step_expanded`, `_keep_wizard_step_open`, the `_wizard_keep_open` key, `flow["claimed"]`, `_render_wizard_progress` and `_wizard_problems_last`'s progress role are gone, along with the now-dead `on_change` plumbing in `controls.column_mapping_ui`.
- **The upload-size warning no longer appears when you run locally** (DATA-22) — the "this upload is N MB / Load it anyway" guard exists because the ~1 GB hosted demo OOM-kills without a traceback. On a local install there is no such ceiling, so it was noise plus an extra tick between you and your own data; it is now gated on the same loopback check as the wizard's "run locally" tip.
- **Adding a dataset no longer hangs after "Dataset added"** (PRE-6) — the reading-direction detection (`preprocessing.add_text_direction`) built each trial's whole joined text on *every row* and then scanned that string per row, making it quadratic in trial length: a 500-word trial scanned ~500× more characters than it needed to. It now detects once per trial and broadcasts, which is **61× faster** on a 144k-word upload (18.3 s → 0.30 s) with byte-identical output. All of that time was spent after the wizard had already reported success, so it read as the app hanging rather than as a slow load.
- **Uploads are no longer capped at 200 MB outside the repo root** (DATA-22) — `.streamlit/config.toml` raises `server.maxUploadSize`, but Streamlit resolves that file against the *launch* directory, so a pip-installed `scanpath-studio` started from anywhere else silently fell back to the 200 MB default and refused a normal-sized fixation report. The cap now travels as an injected `--server.maxUploadSize` flag, exactly like the branded theme (BUG-6) and the usage-stats opt-out (DATA-12), with `constants.UPLOAD_MAX_SIZE_MB` as the single source of truth and an explicit caller flag still winning.
- **A public corpus now reports its declared monitor, not its data extents** (CMP-11) — `app.resolve_source_monitor` recognised a public corpus only when it was reached through the *Public datasets* picker, but the active source is held as the corpus's own registry **label** (DATA-9's flat picker), and compare mode names scanpath B by label too. So PoTeC reported its rounded data extents instead of the 1680×1050 its registry entry declares, marked "estimated" rather than "measured". Harmless while only the side-by-side panels' canvas read it; load-bearing once CMP-11 started gating the overlay on the canvas, where it refused precisely the same-screen pairs that feature exists to allow. `app.active_setup_snapshot` already had the label fallback; `resolve_source_monitor` now has it too.
- **Switching to a stored upload no longer keeps the previous source's monitor** (CMP-8) — a stored upload recorded no geometry at all, so the canvas snap (which only fires for sources declaring an authoritative monitor) skipped it and the figure was drawn to whichever corpus was loaded before. A stored dataset now answers for itself from its setup snapshot.
- **Quick-view and full-monitor transitions keep the current visualization state** (BUG-20, BUG-21) — leaving Illustration restores the styling it temporarily overrode, including after a restored/deep-linked Illustration state; Scanpath/Heatmap highlighting and the rendered figure now agree.
- **Trial selection is always the same picker — selectbox, slider and ◀ ▶ arrows** (BUG-23) — a Trial ID mapped from several columns no longer gets a picker of its own. It used to get two, in turn: one selector per mapped column, and then (briefly) a Participant → Text cascade. Both made the shape of the *mapping* visible in the interface, and neither offered the scrubbing slider or the step arrows, so walking through a dataset's trials worked on some uploads and not others. The per-column version could also fail to reach a trial at all: a OneStop paragraph is identified by batch + article + paragraph + difficulty, all four are detected as trial-level metadata, so the wizard ticks all four under *Filter trials by* — and UX-5 hid exactly the components that were also filter columns, leaving Participant and a bare paragraph number, which is only a per-article index. Every (participant, paragraph) pair then matched several trials and the picker fell through to an opaque **Reading (multiple trials available)** list for a trial it could have named exactly. Now there is one picker for every dataset: the trial dropdown (showing the joined id as-is), the slider, and ◀ ▶ — with **Narrow by** Text / Participant and the **More** filters above it doing the narrowing, as they do everywhere else. The trial chips still spell a composite id out part by part, and a share link or saved setup lands on the same trial as before. On the way, this also clears the `TypeError: select_trial() got an unexpected keyword argument 'filter_cols'` that BUG-16 left behind — it had removed the parameter but not the `tabs.py` call site or the docstring paragraph, so the Scanpath view was a traceback before the picker rendered at all.
- **Participant narrowing keeps eligible trial-sort fields** (BUG-22) — trial-level metadata is discovered from the scoped word/fixation tables instead of only the compact picker projection, with cross-table conflicts and event-level fields excluded.
- **Reset settings is visible in the plot rail without zooming out** (BUG-24) — the reset control in the Scanpath view's 🎛️ Plot controls rail was off screen at ordinary zoom and appeared only once the browser was zoomed out far enough. UX-44 had put it beside the rail heading as a compact **↺ Reset** pill and stacked the two below a narrow width, but the stacking rule flipped the header's flex direction without also turning off the wrap Streamlit puts on every horizontal block — so instead of dropping below the heading, Reset wrapped sideways into a second column about 100px outside the rail, where the rail's own scroll box clipped it. Since the rail is only ~150px wide at a normal desktop width, that was the everyday case, not an edge one. **♻️ Reset settings** now closes the rail instead: full width at the foot of the scroll area, below every control it resets, with the heading row holding nothing but the heading.

- **Corpus Analysis no longer pools a multipart trial's screens into one word axis** (BUG-26) — the **Per text** views aggregated per-word measures by `(text_id, word_id)` with no screen key, but a word id is only unique *within* a screen. On MultiplEYE, where `text_id` is the stimulus and DATA-24 made a trial the whole stimulus, that pooled page 1's word 0 with page 2's word 0 — and with each comprehension-question screen's first word as well. *Word difficulty on stimulus* drew reading-page and answer-block boxes on top of each other, because each screen's boxes are measured against their own origin. The per-text views now take a **Screen** picker beside the Text picker and describe one screen at a time. There is deliberately no "all screens" option: a profile across screens would be keyed on a word id that means a different word per page. The helpers default to the *first screen in reading order* rather than to pooling, so the wrong answer is unreachable even from a caller that predates the fix, and the Groups tab's word profile names the screen it is showing. **Single-screen datasets are untouched** — the bundled demo, OneStop, PoTeC and any upload without `screen_id` render no picker and produce byte-identical figures.
- **A spreadsheet upload no longer fails on a dependency the package never declared** (BUG-41) — `pd.read_excel` needs **openpyxl**, and nothing in the project ever depended on it: not `pyproject.toml`, not `requirements.txt`, not the lock file. It happened to be installed wherever the feature was written. Two things were affected. `data._read_one` routes any `.xlsx` / `.xls` upload straight to `pd.read_excel` with no guard, so dropping MultiplEYE's comprehension-questions workbook into the wizard's own upload slot raised an unhandled `ImportError` at the user; and `datasets._multipleye_questions_by_stimulus` *does* catch it, so a MultiplEYE corpus loaded with no comprehension questions and said nothing about why. That degrade is still right — optional enrichment should not fail a whole corpus load — but it had been quietly covering for a missing dependency rather than for a missing file. `openpyxl>=3.1.5` is now declared, and the test that caught this passes unchanged.
- **Clearing the recovery cache no longer fails when a file cannot be deleted** (BUG-42) — a `PermissionError` unlinking `~/.cache/scanpath-studio/session-v1/manifest.json` escaped `persistence.clear_local_state` and took the rerun down with it. The two actions that call it — **Clear recovery cache** and **Reset everything** — are precisely what someone reaches for when the session is *already* broken, so failing there strands them with no way out. The on-disk half is best-effort now: an `OSError` is logged through the module logger (so the line reaches the 🐛 Debug panel rather than a terminal nobody is watching), the in-session bookkeeping is forgotten either way, and the function reports whether the files actually went. The boundary is deliberate — `forget_state` still raises, because it is the file operation and a caller that wants to know should be told; what must not fail is the button above it. A read-only or synced home directory, a file open in another process, or a cache owned by another user all produce this.
- **Three computation-log tests no longer fail on Streamlit's bare-mode warnings** (BUG-39) — `tests/test_debug_log.py::TestTheComputationLog` asserted over the *exact* list of `caplog.records`, and `caplog` collects from the **root** logger — so Streamlit's own *"missing ScriptRunContext! This warning can be ignored when running in bare mode"* landed in it, nine records ahead of the one the test wanted. How many failed depended on how the file was run (four alone, three under `-n 4`, none in a full parallel suite), which is itself the evidence: an exact-equality assertion over a shared handler is hostage to whatever else ran in that worker. The app's own lines were all still being emitted, confirmed before anything changed. The three assertions now read through one helper that keeps only records whose logger root is `scanpath_studio`. Fixing the tests rather than the app was the call: the warning is Streamlit's, it is correct in a bare-mode run, and silencing it would hide a real signal from anyone debugging a background thread.
#### Changed
- **💾 Session is a dialog opened from the nav, not a top-level page** (UX-100) — UX-63 had made it a nav entry you *travelled* to; once UX-96 cut it to four short blocks (🗄️ Automatic recovery · ⬇️ JSON backup · ♻️ Reset · 🐛 Debug tools), a whole destination for them was more chrome than they were worth. 💾 Session now sits beside the three views as an **action** entry — the same shape ❓ Help's Tutorials / FAQ / About already had: selecting it arms a modal and bounces the router back, so the panel opens over your work. A dialog body is a fragment, which is what the panels had to be written for: it runs only while the modal is open, and Streamlit drops a widget's key at the end of any run in which it did not render — so the 🐛 Debug toggle got its own widget key mirrored into the durable gate (it *was* the gate, and dismissing the modal used to switch debug mode back off), the two confirmations became inline rows rather than nested modals, and restoring a backup ends in an explicit whole-app rerun. The escape hatches still reach you on every path where the dataset can't be drawn. Two dead things went with the old page: `.st-key-top_menu`, which had not existed since UX-63 emptied the settings row — so the welcome tour's last step had been highlighting nothing — and the injected-JS "jump to Save & restore" shortcut, whose last caller had already gone.
- **The Data page is two screens: 📂 Available datasets and ✏️ Edit dataset** (DATA-35) — the page used to put a forty-row dataset table, twenty column-mapping selectboxes, the recording setup and three upload widgets in one scroll, on the screen you visit to answer "which datasets do I have?". It now splits: an overview (the table, ➕ **Add dataset** underneath it where you reach for it, and 🔎 *What's in the open dataset*) and an **✏️ Edit dataset** screen carrying everything that *configures* a dataset — source options and location, column mapping, recording setup, trial identity, stimulus images, the two metadata tables and preprocessing. ✏️ Edit is on every row now rather than uploads only, and the screen wears the add-dataset screen's own sticky header, because they ask the same questions of the same dataset — one before it exists and one after. Both screens render every run and are switched by key, the same mechanism DATA-26 uses for the page itself, because the editor is made of the widgets that drive the load. The table gains **Language** and a **Home** link, plus an ℹ️ **About** dialog per row carrying the description and where that corpus' coordinates come from — real, reconstructed or synthesized, taken from what each loader actually does rather than assumed (PoTeC's release keeps no recorded x/y, so its fixations sit at the centre of the character they name). And the table is a fragment, so About / Rename / Remove cost a redraw of the table instead of two full page renders — which is what made renaming a dataset feel slow.
- **Clearer wording and a wider page: trial-picker help, Summary stats, page gutters, Automatic recovery** (UX-99) — five display-only fixes. The trial picker's help drops the 💡 and names what to click ("Click this dropdown, then type to narrow the list."); the chip strip's *Details* popover is now **Summary stats**, which is what it holds; the main block container's side padding goes from Streamlit's ~5 rem a side to 1.5 rem (0.75 rem under 640 px), giving the scanpath canvas and the wide tables about 7 rem more width; the compare checkbox is **Step A + B** rather than *Step both trials together*, which the rail's fixed label column truncated to "Step both trials toge…"; and the **Automatic recovery** panel opens by saying what it does — your datasets, mappings, settings and annotations are kept on *this computer* and nothing is uploaded — with the environment-variable escape hatches spelled out in their own line instead of packed into a tooltip on the folder path.
- **The trial control line reads as a form: a funnel, a titled sort row, and a dataset tooltip that is about datasets** (UX-98) — three fixes on the Scanpath view's control line. The **Select Dataset** picker's `?` opened a whole upload-and-column-mapping data dictionary — advice about CSV conventions and *Column mapping* panels "in the sidebar", which UX-38 removed — none of which is about choosing between datasets that are already loaded; it now says what the picker does and where datasets are added, and the dictionary itself is gone from the code, since [Data format](https://lacclab.github.io/scanpath-studio/data-format/) is the maintained version of it. The **⇅ sort** popover moved onto the shared `label | field` row (`fields.labeled`): *Sort trials by* and *Descending* are titles on the left with their controls to the right, each title carrying its description on a dotted-underline hover instead of a `?` icon, and the sort help lost its parenthetical example. The comparison picker's own sort menu moved to the same row so the two are not half-converted. And the trial **filter** popover is a funnel rather than a magnifier — it narrows the list, it does not search it; Unicode has no funnel emoji, so it is Streamlit's Material `filter_alt`, the same mechanism as the dataset table's buttons. A numeric filter's range help (*Trial index* and friends) also drops its trailing aside and stops at "Trials with no value are kept."
- **Zooming the plot magnifies it, instead of stretching the axes** (VIZ-38) — Plotly's box zoom only rescales the *axes*, so the word boxes and saccades spread apart while the fixation markers, the word labels and the saccade line widths stayed pinned at the screen-pixel sizes they were built with: zooming in broke exactly the true-to-scale sizing the embed exists to protect, leaving tiny text stranded between metre-long saccades. Zoom now rides on the same uniform CSS transform that already fits the figure to the column, so everything magnifies together and the plot stays true to scale at any magnification. Controls: a small **− 100% + ⟲** toolbar over the figure, Ctrl/Cmd + wheel (which is also what a trackpad pinch sends), and drag-to-pan inside a fixed-height viewport, from 1× (fit) to 8×. Plotly's own zoom/pan modebar buttons are removed and `dragmode` is switched off so there is one zoom rather than two fighting each other; hover, Box/Lasso select and the PNG button are untouched. The zoom is **view-only** — it never touches the figure, so exports, Share links and headless renders are unaffected, and it needs no deep-link / CLI / API surface. The *Multiple Comparison* small multiples stay zoom-free.
- **Data, annotations, comparisons, export and plot controls are more compact and consistent** (UX-94) — Data is now **Data Management**, with complete integer dataset counts, explicit dataset kinds, row-level Rename / Remove actions, named inspection headings, and editing controls aligned with the add-dataset flow. Annotations update favorites immediately and use a compact tag row. **Stimulus & Context** supports general trial context. Comparisons select trials by a matching field, may cross texts, preserve the main plot's stimulus and styling, omit the selected trial, and give scanpath B its own filter. Export adds **This trial**, uses **Trials to Include** and **Figure Formats**, and simplifies labels and file naming. Share always includes the full view and combines link generation and copying. The scanpath header, plot rail, Quick views, stimulus typography, animation controls, reset flow, tutorials, spacing and authorship were tightened for a clearer and more consistent interface.
- **Session is organized around recovery, JSON backup, reset and debug tools** (UX-96) — four compact sections replace the mixed list. **Automatic recovery** shows the saved-copy status and folder; clearing it leaves automatic saving enabled and suppresses only the immediate rewrite. **JSON backup** presents Download before Restore. **Reset everything** clears the recovery copy, query parameters and live session after confirmation. **Debug tools** remains opt-in, while the standalone computation-cache action and most explanatory copy are gone.
- **Compare mode puts both control lines above both chip strips** (CMP-16) — the four rows used to interleave (control A, chips A, control B, chips B) because UX-75 paired each reading's chips with the row that chose it. They are now grouped by kind — control A · control B · chips A · chips B — so the two selectors sit adjacent and can be read against each other instead of across an unrelated block. Creation order is screen order, so this is three container reservations in `tabs.py` and nothing that fills them moved; `compare_slot` gained a `tour_grp_compare_picker` key for symmetry with the strips beside it. CMP-15's per-strip dataset naming is what carries the attribution the old pairing carried by adjacency.
- **Deleting a dataset drops the computations derived from it** (UX-87) — every figure, table and normalization cached for a dataset is dead the moment its frames leave the session, so `_remove_dataset` clears the shared computation cache when it removes the frames. `@st.cache_data` has no per-key eviction, so surviving datasets recompute lazily on their next use. The standalone **Clear cached computations** Session action is gone: the safe dataset-scoped lifecycle action and the confirmed **Reset everything** action cover the two useful cases without exposing an implementation-detail button.
- **The add-dataset page drops *Screen name* and every "still to do" badge** (UX-88) — `screen_index` was already hidden from the mapping by UX-55 r4 but still resolved from auto-detection into every schema; its three field specs are now deleted outright, so nothing offers, proposes or records it. The `screen_index` **column** is untouched and still load-bearing — `multipart.normalize_screen_identity` derives it from first appearance and the public corpora stamp it onto the frames, neither of which goes through a mapping. The page also stops narrating: no status badge on the numbered part headline, none on the section headings, and no **Still to do** block above ✅ Add dataset. Three places were saying the same thing about a field visible on the same screen, on a page whose whole complaint has been length. What points at the problem is what already did: pressing ✅ Add dataset turns every unmapped required row red in place, and still cannot finalize. A blocker with no on-screen field to redden — a raw-gaze-only upload whose trial id cannot be mapped is the known one — prints as a red line above the button after you press it, so the button never refuses without a reason.
- **The column mapping groups its rows by table, not by kind** (UX-89) — the four rows used to interleave (both identity rows, then both feature rows), so a table's own two lines sat two rows apart and the name on the left read as labelling one line rather than the block. Each table's identity row and feature row are now adjacent under one name — Fixations, then a hairline, then AOI. Streamlit's creation order is screen order, so all four rows are reserved in the loop that builds the blocks and filled where their mapping code already lives; the row widths from UX-55 are reused unchanged. The separator is a tight custom rule rather than `st.divider`, whose margins would put back the vertical cost this page keeps fighting. The two per-block validation warnings (*Words/IA — missing Word/IA ID*, *…need either (x, y, width, height) or (left, right, top, bottom)*) are gone with them: pressing ✅ Add dataset already turns every unmapped required field red in place.
- **The add-dataset page objects only once you press Add, and then everywhere at once** (UX-90) — *Still to answer* was a yellow warning that printed the moment the page opened, so the wizard greeted a fresh upload already complaining about questions nobody had reached. It is red now, and gated on the same `ADD_ATTEMPTED_KEY` the mapping fields use. Each of the three mandatory setup groups carries a trailing `*`, matching the required mapping fields, and unanswered ones are ringed red after a failed add. Two fields that could previously survive a failed add in neutral grey now go red with the rest: the word box's four coordinate sub-fields (the spec is required under its own `box` key, but the sub-fields are not in `field_specs`, so they read as optional) and Trial ID (the page's only required multiselect, which had no keyed cell for the tint to land on). Section and part headings also gained the bottom margin they were missing — Streamlit's negative block gap had been eating it, leaving headings sitting on the first control's label.
- **Every required field really does go red on a failed add, including Trial ID** (UX-91) — the red-marking rule had been targeting `[data-baseweb="select"]`, an attribute this Streamlit version does not emit at all. Two of its three selectors were dead; selectboxes tinted anyway through the `stSelectbox` fallback beside them, which is precisely why it looked correct — every field that did go red was a selectbox, while the page's one required **multiselect**, Trial ID, had no matching selector and silently never coloured. The selector is now `[data-testid="stSelectbox"|"stMultiSelect"] > div > div`, checked against the rendered DOM. Trial ID also needed wiring up at all: `wizard._render_identity_field` builds its own multiselect per table, because trial / participant / text each span both tables and the caller owns the row, so it never passed through the tint machinery; each identity picker now renders in a keyed cell and takes a `required=` flag, painted through the same `<style>` builder via `controls.mark_missing_cells`. Separately, the word box stops stacking title, radio and a row of four selects into three lines — it is one row now, `Word box * + format radio | Box left | Box right | Box top | Box bottom`, with Line index closing it — and its four coordinates each carry the `*` their required parent does.
- **Confirming an auto-detected column clears its amber mark** (UX-92) — picking a *different* column already went neutral; picking the one detection proposed could not, because re-selecting the value a select already holds fires no `on_change` — Streamlit dedupes it in the frontend and does not rerun at all. Nor can that be worked around at the widget: since UX-53 r10 the value lives in the widget key with `index=None` (what makes the ✕ clear work), so the detected column *is* the select's value and confirming it by hand is invisible to Python by construction. While a row is amber its ✨ flag is now a button: one click means "I chose this", the field goes neutral, and the mapping is unchanged — a claim about who decided, not a change of value. It occupies the space the icon already had, with the button chrome stripped so it still reads as a flag.
- **The wizard's two footer buttons are one matched pair** (UX-93) — the add-dataset page had three endings and drew this footer differently in each: two full-width buttons stacked with a grey Add (blocked on required fields), a lone bare button with no download at all (blocked on a rejected mapping), and a 50/50 split of the section (finished). `_wizard_footer` is now the one renderer for all three, on a `(1.4, 1.4, 8.0)` row — `1.4` being the ✕ Cancel width from the sticky bar — so both buttons are exactly as wide as the way out of the wizard, side by side, with ✅ Add dataset filled blue on every path. *Download setup (JSON)* became **⬇️ Save setup** because the longer label wrapped to two lines at that width, making the pair 55 px and 40 px tall; what it saves and how to restore it was already the tooltip's sentence.
- **A zipped table may be up to 32 GB, and the caps are yours to move** (DATA-34) — DATA-16 bounded how far an uploaded `.zip` may decompress before any member is opened, so a small archive of highly compressible CSV could not fill the machine's RAM. The absolute caps it picked — 4 GB for one member, 8 GB for the archive — turned out to sit *below* honest data: a full OneStop fixation report is a single ~8 GB CSV inside its zip, and a workstation with the memory to read it was told to split the file. They are now **32 GB** and **64 GB**, and all three limits read from the environment (`SCANPATH_ZIP_MAX_MEMBER_GB`, `SCANPATH_ZIP_MAX_TOTAL_GB`, `SCANPATH_ZIP_MAX_RATIO`, read once at import), so a memory-capped deployment sets them *down* instead of every workstation living inside a container's budget — and the two size errors now name the variable that moves them. The trade is deliberate: the absolute caps are a memory guard, not a security boundary (on the ~1 GB hosted demo any upload approaching even the old ones was already fatal), and the **ratio** check that actually distinguishes a zip bomb from a corpus is unchanged at 200×. A member is also **streamed into pandas** now rather than being read whole into `bytes` first, so the honest large case no longer needs a second full-size copy of itself in memory before parsing starts; the forged-declared-size protection moves into that stream (`_BudgetedZipMember` counts the bytes that actually arrive and raises the moment they overrun the budget), and formats whose reader seeks — Parquet, Feather, Excel — still land in memory whole under the same budget.
- **A layer's settings stay readable while the layer is switched off** (UX-97) — every layer section on the Scanpath rail is a `toggle → ⚙️ style → 🧹 filter` row, and the ▾ that opens the style popover has always been clickable. Its *body*, though, was gated `if show_<layer>:` — so switching 👁️ Fixations, ↗️ Saccades, 🔥 Heatmap or 🔵 Raw gaze off left an affordance that said there was something there opening onto nothing. The controls now always render and are **greyed** instead, with one caption at the head of the popover saying to turn the layer on, so a layer's styling can be prepared before it is switched on and inspected after it is switched off. The two halves of the 🧹 Filter section that belong to Fixations and Saccades are included, having had the same empty-popover shape for the same reason; 📄 Stimulus is not, because it holds three independent layers with no single switch to be off. Fixations keeps its existing exception — in **Animate** its toggle reads off but is inert (the replay *is* the fixation trail) and the styling below is still live, so that case greys nothing. As with the mode gate, **greying never rewrites a value**: these are `global_*` keys, which are share-link and saved-config wire format, and a disabled Streamlit widget keeps its own key.

- **🔥 Overlays is gone — Heatmap and Raw gaze are their own plot-rail sections** (UX-86) — Overlays held exactly two layers, so pulling either out left a section wrapping one toggle. Both are now peer `[toggle | ▾]` sections beside Fixations / Saccades, each with its style in its own popover — Heatmap's is the same content it always had, just under its own trigger now.
- **The add-dataset wizard's two Help buttons are one ❓ Help popover** (UX-84) — the sticky bar's 🧭 guide button and 📖 documentation link merge into a single ❓ Help popover offering both, matching how the top nav's own Help already works (UX-65). ✕ Cancel is unchanged; the docs link still opens in a new tab rather than navigating in-app, so it can't discard an in-progress upload.
- **The add-dataset wizard's mapping merges each table's identity and geometry fields into one two-line block** (UX-55) — the separate "which columns identify a trial" and "where the eyes/words are" sections are now one per-table block: row 1 is Trial ID · Screen ID · Participant ID · Text ID · Word/IA ID · Fixation ID-or-Word text, row 2 is the coordinates (Fixations) or the word box + Line index (AOI). **Screen name is gone from every mapping surface** — the wizard and the 🗂️ Data page's remap editor both — though the column stays auto-detected and applied; **Screen / part ID** is relabelled **Screen ID**.
- **Every plot-rail section is a toggle and a ▾ on one line, with its controls in a popover** (UX-80) — a section used to be an expander holding a layer toggle and a `⚙️ Style` popover: two levels, two clicks, and no hint from outside which knobs were where. Each is now the row **🎬 Animate** and **⚖️ Compare** already used (UX-68) — the layer's switch and a ▾ sharing one line — and the section's controls are that ▾'s popover. 👁️ Fixations and ↗️ Saccades carry their toggle on the row; 📄 Stimulus (Text · Bounding boxes · Stimulus image) and 🔥 Overlays (Heatmap · Raw gaze) hold several layers, so their rows carry the section's name and each layer's toggle leads its group inside; 📐 Figure & canvas groups Screen & framing · Axes & grid · Title & labels the same way; and 🧹 Filter keeps no toggle but takes the same row. The reason is width, not tidiness: the rail is ~150–200 px by design, so an expander lays its controls out inside that and crops them, while a popover is positioned over the page and sizes to its content — which is also why the opposite experiment (inlining the popovers) had to be reverted. Round 2 put every section on **one** line: the trigger is `width="content"` rather than `"stretch"` (a stretched popover claims the whole row, which is what wrapped the ▾ under its own switch), the row cannot wrap, and a label shrinks before the trigger moves. It is also one arrow now — Streamlit draws a chevron on every popover trigger, so the `▾` label the sections carried and the `arrow_drop_down` icon Animate and Compare carried were a second one — and no `?` icons: a widget's `help` renders as an icon while a popover trigger's is a plain hover tooltip, so the Fixations, Animate and Compare tooltips moved onto their own ▾. **Palette** had no second hover target, so its note on the three presets was dropped rather than moved.
- **Stimulus typography moves beside the text it draws; the screen's physical geometry leaves the rail** (UX-81) — *Scale text to boxes*, line spacing, the stimulus and figure font sizes, the multilingual font stack, the text font, the text colour and the plot background were two sections away from the text they apply to, under 📐 Figure & canvas → 🔤 Text & fonts. They are now 📄 Stimulus → **Text**. Same widgets and the same `global_*` keys, so every share link and saved config restores as before. In the other direction, *Monitor physical width*, *Viewing distance* and *Display DPI* are no longer offered in the rail at all: they are experiment facts, and the 🗂️ Data page's **Recording setup** already records them with a provenance, so a second set could disagree with it. Their values are unaffected — they are pinned every run, and the px/degree conversion behind saccade amplitude in degrees, the derived saccade table and the point-to-pixel font conversion all read the same numbers. The px/degree caption stays beside the canvas and now says where the geometry comes from.
- **The dataset list is *Available datasets*: click a name to open, and the open row is tinted** (UX-77, UX-78) — the section that lists every dataset was still titled *Data source*, from when it picked one, and its ➕ **Add dataset** button sat in a row of its own *below* the table it acts on; the title now reads **📂 Available datasets** and the button shares its line. In the table itself, the dataset's **name is the control**: `st.column_config.ButtonColumn` takes its label from the cell value, so the column that says which dataset a row is also opens it, and the separate **Open** column is gone. The open dataset is a tinted row rather than a ▶ in a column of its own, which retires the marker column too — five non-data columns down to two. The tint is a pandas `Styler`, the only per-row colour `st.dataframe` takes; it is a fixed translucent blue rather than a theme token, because a Styler emits inline CSS and cannot read the theme's variables.
- **Each dataset's counts are computed once and remembered** (DATA-32) — Readers · Trials · Fixations · Words were recomputed on every rerun of the page, and only for the dataset that was open. They are now keyed on the frames' fingerprints and remembered: a dataset you have opened keeps its row filled even when it is not loaded, including after a restart (the store rides in the on-device recovery cache's manifest). Because the key is the fingerprint, a remap or a re-upload recomputes rather than showing a number that no longer describes the data. A dataset that leaves the list takes its counts with it, and both 🗑 *Forget saved session* and 🧹 *Clear cached computations* drop them. A corpus you have never opened stays blank on purpose: reading one costs minutes, and the app should not spend them unasked.
- **Deleting a dataset and leaving the wizard both ask in a modal** (UX-79) — the delete confirmation opened *under* the table, which on a long list is off-screen from the row that raised it, and the wizard's "leave and discard?" prompt appeared inside a screen you are scrolled down in although the click that raises it is on the nav at the top of the window. Both are `st.dialog` modals now. The arming flags and the callbacks are unchanged — a dialog is opened by calling it, so all that moved is where the flag is read.
- **Preprocessing is held back from the app until the next release** (PRE-22) — the 🧹 Preprocessing section on the 🗂️ Data page, the pipeline stage behind it, its *Cleaning QA* provenance table and the tutorial step that pointed at it are all hidden, behind the same `SCANPATH_EXPERIMENTAL=1` flag that carries PRE-21's unfinished work. Nothing is deleted or branched: `preprocessing.py` is unchanged, the suite still runs with the flag on so its coverage is intact, and setting the flag brings the panel back for a local session. A saved config or share link carrying `global_preproc_*` is ignored while it is hidden — running a pipeline whose controls are absent would change every number with nothing on screen to explain it — and those stored answers are kept rather than cleared, so they survive to the release that shows the panel again. The five analysis tables that merely live in `preprocessing.py` (Sentences · Saccades · Trials · Readers · Characters) are not part of this and stay. **The Python API and the CLI keep working**: `api.preprocess_data` and `scanpath-studio analyze` shipped in 0.28.0, so unlike PRE-21's gate this one does not raise — a hidden button and a broken function call are different promises.
- **One 🧹 Filter section for the whole figure, replacing the per-layer filters** (UX-72) — thinning what is drawn was two controls in two places, one inside 👁️ Fixations and one inside ↗️ Saccades. They are one section now, a peer of the layer sections, holding both halves under their own headings: the fixation-index window and the short / long / out-of-bounds rules, then the saccade reading classes. It sits after the layers and before 📐 Figure & canvas, so the rail reads *what is drawn → what is thinned out of it → how it is framed*. Each half still badges itself with its own detail and the section header carries a `•` while either is narrowing, because a thinned figure otherwise reads as missing data. Not to be confused with the 🔎 on the control line, which narrows which trials you can pick rather than what is drawn inside one. Nothing was dropped in the move: the fixation-index window, the short / long / out-of-bounds / blink rules and the saccade reading classes are all there, and each half carries the sentence its popover trigger used to show as a tooltip.
- **Reset visualization is a button, not a popover holding one** (UX-73) — the rail's one escape hatch was itself a click deep, and behind that click was a single button. The caption it held (what is reset, and that annotations, filters, mapping, data source and the selected trial are kept) is the button's tooltip now.
- **Each reading's title and chips are one line, under that reading's control line** (UX-75) — the strip above the plot ran chips-then-controls, and in compare mode it stacked A's label, A's chips, B's label and B's chips all below *both* control rows, so which chips described which reading was inferred from colour and order. Each reading now has one line — title left, chips filling the rest, **Details** and ✏️ at the right — directly under the control row that selected it. The line takes the control-line grid with its trial and scrub tracks merged, so the title sits under the dataset picker and the chips under the trial picker and scrubber. Outside compare mode the title is the reader id, which is what compare mode's titles name too; B's line carries no ✏️ or Details of its own, since the chip fields are one setting for both readings.
- **One control line on the Scanpath view — and the same line for compare's second trial** (UX-64) — the view opened with two stacked rows: a Narrow-by row (data source · *Filter by* Text and Participant · **More**) and, under it, the trial picker (selectbox · scrub slider · ◀ ▶ ⇅). They are now one row. Everything that narrows the trial pool moved into a single 🔎 popover at the end of it, so there is one place that filters instead of two. The dataset picker keeps its full width on purpose: you may be comparing two datasets, and its label is what tells them apart, so the scrubber gives up the room and the filter becomes an icon. ➕ **Add data** left this row entirely — the 🗂️ Data page is the only way in now. A one-trial pool degrades to dataset · trial · 🔎, since a single-option slider cannot be drawn at all. **Compare mode's scanpath B is now the same line**: its dataset row, its *Filter B by* row and its picker row are one row of the same four-track grid — `[Compare with] [Compare To] [scrub slider] [◀ ▶ ⇅ 🔎]` — so the two readings' controls line up down the page. B's 🔎 holds its own `cmp`-prefixed Narrow-by pair plus the condition filters that used to sit behind **More**, and appears only when B has a dataset of its own to narrow; under *This dataset* its candidates come out of A's pool, which A's own filters already define. Because the row must know how many candidates B has before it can decide whether it carries a scrubber, B's dataset and filters are resolved from session state before the row's widgets render — the order `main()` already resolves A's pool in. The one run that would be wrong, the one that switches B to another corpus, deliberately narrows nothing rather than applying the previous corpus' reader ids to the new one. The multipart screen navigator keeps the three-track shape, built by merging two tracks of the same grid so every row's outer boundaries still line up.
- **A cross-dataset comparison names both corpora, not just the second** (CMP-15) — the coloured label above each chip strip named B's dataset (it came free with the *Compare with* pick) and left A as a bare reader id, which read as though only one panel had a corpus. Both are now `⟨dataset⟩ · ⟨reader⟩` when the two sides come from different datasets. Same-dataset comparisons — the common case — are unchanged: one corpus name printed twice says nothing, so those labels stay the bare reader (or trial) ids. Display only; the participant namespacing that keeps two corpora's identical ids apart inside the figure is untouched, and exports, share links and annotations still carry each corpus' own ids.
- **The datasets are a sortable table; editing a mapping looks like adding one, and deleting asks first** (UX-54) — the 🗂️ Data page's data-source selectbox is replaced by a table: one row per dataset, sortable and scrollable, carrying Readers · Trials · Fixations · Words beside the name and the actions that belong to that dataset — Open, Edit its mapping, Delete. ✏️ **Edit** opens a mapping editor laid out the way the add-dataset screen lays its mapping out: rows named down a narrow left column (Fixations · AOI · Raw gaze), one field per cell, each title stacked over its select, committed with **✅ Save changes** where the wizard has ✅ Add dataset — in place of one stacked expander per table. Fields the layout does not name land on a trailing *More* row, so none can be dropped if the field list grows. ✕ **Delete** no longer removes an upload on the click: it arms a confirmation, because the button is one cell away from ✏️ Edit and an upload's tables, mapping and annotations leave the session with no undo. The counts are filled for the **open** dataset only (a table where some rows carry counts and others are blank invites reading the blanks as zeroes) and are deliberately cheap — two `nunique` calls and two lengths, cached on the frames' fingerprints. Row actions use `st.column_config.ButtonColumn` following ENG-36's pattern, including its gotcha: a click reports a *source* row position, not a position in whatever order the columns were sorted into.
- **Help is a menu that opens the tutorial, the FAQ and About over your work** (UX-65) — UX-63 had just made ❓ Help a page in the top menu, which meant reaching the FAQ took you away from the plot you were reading it about. Help is a **collapsible section of the nav** now: 🎓 Show tutorial · 🧭 Tutorials · ❔ FAQ · ℹ️ About, each opening the dialog it always opened, over whatever view you are on. Nothing about the tours, the tutorials or the dialogs changed — the entries arm exactly the same request the buttons armed, and the router returns you to your view in the same breath. 📚 Documentation is no longer listed there, because a nav entry cannot be a URL and the wordmark beside the nav already opens the docs site. 🐛 Debug mode moved to the foot of 💾 Session: it is a gate rather than a link, and it has to keep rendering every run to survive.
- **The add-dataset screen keeps one title row on screen while you scroll** (UX-66) — the top of that page carried four separate pieces of copy written from three different modules — a page header, its one-line summary, a **📂 Data source** subheading, an "Adding a dataset…" caption — and then the wizard repeated the title again. All five are replaced by a single row that **stays put as the fields scroll under it**: *Set up your dataset*, **📘 Show setup guide**, a **📖 More documentation ↗** link, and **✕ Cancel**, which moved onto it from the source-picker block. The long "first time?" paragraph survives as that link's tooltip. The page's top and bottom padding is cut with it, so the first mapping field is visible without scrolling. ✕ Cancel is filled blue, the same button shape as ✅ Add dataset — the two are the ends of one decision, and a ghost button beside a filled one read as the disabled half of a pair.
- **A mapping dropdown opens wide enough to read the whole column name** (UX-71, UX-57) — a mapping row packs four or five selects across, so each control is narrow by design and its dropdown inherited that width; a clipped option is not merely ugly but ambiguous, since `CURRENT_FIX_INTEREST_AREA_ID` and `…_INDEX` share every visible character. Two earlier attempts to wrap the option text changed nothing on screen, for a reason neither recorded: they styled BaseWeb markup, and Streamlit no longer renders a selectbox with BaseWeb — it is a react-aria ComboBox whose option list is portalled to the document body with the trigger's width written inline. That list is also virtualized (fixed row heights, absolutely positioned rows), so wrapping would overlap the neighbouring option, and `max-content` collapses straight back to the control's width. The list is given a width instead — the trigger's plus 9rem, capped at the viewport — and react-aria shifts the popover sideways when that would run off-screen. It is emitted by the two mapping screens rather than added to the global stylesheet: a portalled popover cannot be scoped by an ancestor selector, and a blanket rule would widen the plot rail's dropdowns too, where the extra width has nowhere to go but over the figure.
- **Each count sits under the field it counts, in small text** (UX-67) — the wizard confirmed a mapping with coloured banners: one green `✓ N trials detected` per identifier, stacked on a screen whose whole point is that the mapping fits on it, and placed several sections away from the menus that produced the numbers. Each count is now a caption directly under its own picker, one per table — so differing trial coverage between the Fixations and AOI tables reads as two numbers side by side rather than as a sentence about them. Only a genuine problem still gets a box, and it renders directly above **Add dataset**: the case where the two tables share no trial ids at all, which is a mapping error rather than a count. The green tint on a chosen mapping went with them; detection and blocking gaps are the only coloured things left on the screen.
- **Fixation fields run over two lines, and the AOI fields group together** (UX-55) — the geometry step is two named groups on the identity rows' grid, a short word in a narrow left column instead of headings and spacer lines: **Fixations** (X · Y · Timestamp · Duration, then Fixation ID) and **AOI** (the fixations table's Word/IA ID beside the AOI table's own Word/IA ID, Word text and Line index, with the Word box on the line directly beneath). The fixations table's `word_id` sits with the AOI fields rather than with the fixation fields: it is a column of the fixation file, but what it says is *which AOI this fixation hit*. The *AOI features* sub-heading and the blank line under it are gone — the whole mapping has to fit on one screen, and each heading was a line it could not spare.
- **Animate and Compare are split buttons: the toggle, and a ▾ for its settings** (UX-68) — each mode's settings used to sit in a full-width `⚙️ Playback` / `⚙️ Compare options` button on the line below its toggle, and only appeared once the mode was on. Both now share one row with the toggle, the settings behind a small ▾ beside it, in the shape of a Zoom-style split button. The menu **opens whether or not the mode is on**: off, every control inside is greyed with a tooltip naming the toggle that frees it, so what a mode offers can be read before deciding to turn it on. Nothing is hidden and no value is rewritten — a greyed control keeps its key, so a deep link or restored config still lands on it — and the ▾ itself never disappears, since a trigger that comes and goes reflows the row under the cursor. The two halves are drawn as one control: a shared outline and corner radius on the row, a 1px seam between the switch and the ▾, and no border, radius or background of its own on the button, which also shrinks from Streamlit's ~55 px default to a glyph's width — that is where the room to fit both on one line comes from. Hovering lights the whole right half to the seam. On a rail too narrow for the label the row *wraps* rather than clipping, so the ▾ is always reachable even though the wrapped shape reads more like a card. Compare and Animate only for now — the rail's layer sections keep their `toggle → ⚙️ style → 🧹 filter` rows.
- **The Scanpath subtabs read `label | field`, so a panel fits on one screen** (UX-69) — every field in the subtab bar puts its name in a fixed-width column to the **left** of the control instead of on a line above it, so the titles line up down a panel and the Export tab's *Multiple trials* block is about half its old height. Twenty-five fields moved: 📝 Annotations, the Stimulus panel's ⚙️ Fields popover, 🔬 Comparisons, 📐 Line assignment, both halves of Export (the live figure, the animation, the pair bundle and every bulk option) and 🔗 Share. The row is UX-51's, which is why it looks like the rail's — but it could not be *taken* from `controls.py`, which imports `annotations` and `export`, the modules rendering three of these subtabs; it now lives in a new `fields.py` below all of them, with `controls`' own `_labeled` / `_row_label` delegating there, so the rail's call sites are untouched. Two departures from the rail: the label column is narrower relative to the panel (20% of a full-width subtab against 36% of the rail's popover), and **checkboxes and toggles are split too** — the rail leaves them native because splitting only indents them, but here the label column is the spine every other row aligns on, and a native checkbox would put its box at that edge instead of its title. Descriptions keep folding into the title's own hover rather than taking a `?` icon's width per row, and two labels the column would have ellipsized are shortened on screen only (**⭐ Favorite**, **Frame cap**) with the full sentence on the tooltip. Nothing on the wire moved: each widget keeps its real label and key and merely collapses them, so accessible names, `AppTest` lookups, share links and saved configs are all unchanged. The Corpus Analysis subtabs are a separate call (UX-70) — their controls already sit side by side, so a label column there would spend width rather than buy back height.
- **A mapping row shows its state as a tint on the select, not a sentence beside it** (UX-53) — the first cut wrote `● ✨ auto-detected \`CURRENT_FIX_INDEX\`` beside every field, which ran wider than the control it annotated and repeated on each row. The state is now a low-alpha background on the select itself — **green** you picked it, **amber** auto-detected and left alone, **red** required and still empty — emitted as one `<style>` block per mapping (`controls._emit_field_tints`) keyed on each cell's `.st-key-…`, so there is no extra element per row. It needs `!important` on several nodes of the widget: BaseWeb paints the control's background through an emotion class that outranks a plain class selector, so the first cut of the rule was never visible at all. What remains beside the field is a single **✨**, whose tooltip carries the detected column name and whether it was overridden or left unused. Red appears only *after* **✅ Add dataset** has been pressed on an incomplete wizard — a required field the user has not reached yet is unfilled, not wrong, so a fresh upload does not arrive covered in errors. That attempt is what the button now records: while blocked it stays **enabled** rather than disabled, because a disabled button cannot be tried, and the click sets `ADD_ATTEMPTED_KEY` instead of finalizing. The colours are Streamlit's own `:green[…]` markdown, so they follow the active theme rather than hard-coding hex that reads on one background only.
- **The Data page is denser, and its smallest text is legible** (UX-53) — the vertical gap between blocks closes, captions come up to 0.86rem, and the stage dividers stop spacing the page twice. Scoped to `.st-key-data_setup_page` so the plot rail and the analysis views keep the metrics UX-51 tuned them against. The page's own five-line summary is one line, and the *Data source* stage drops a caption that restated its heading.
- **One menu: Scanpath, Corpus Analysis, Data, Session, Help** (UX-63) — 💾 Session and ❓ Help were popovers in a row *under* the nav; they are entries of the nav itself now, so the header carries one menu instead of a menu plus a row of buttons. `menu.py` had recorded this as impossible without `position: fixed` against Streamlit's internals — true of lifting a *widget* into the header strip, and false of the route taken: `st.navigation` takes pages, and these two are now pages. **They still render on every run**, into a container hidden by CSS unless its entry is active — the trick DATA-26 uses for the Data page. That is not incidental: a popover executes every run, and Streamlit drops a widget's key at the end of any run in which it did not render, so content that only drew while its own page was open would silently reset the 🐛 Debug gate and the persistence pause toggle between visits. Because they keep rendering, every `host=` fill site in `app.main` is unchanged and no `persist_state` audit was needed.
- **The app's name is a wordmark in the header, not a heading on the page** (UX-62) — *Scanpath Studio* and its one-line description used to print in the page body, a row below the nav, costing a row on every view. The name is now the wordmark in Streamlit's own header, top-left of **Scanpath · Corpus Analysis · Data**, linking to the docs site; the description leaves the chrome and survives in **About** and the README. `st.logo` is the only door into that strip — the nav is drawn there by Streamlit itself, and the page body cannot reach up into it — so `app.render_app_logo` runs before the nav, when the header is assembled. The image lives in `scanpath_studio/assets/` and is declared in `package-data`: at the repo root it would have shipped with nothing, leaving every pip install with an empty header while a source checkout looked fine. A missing file warns rather than raising, because a wordmark is chrome and an editable checkout that has not been reinstalled should still open.
- **The Word box and Recording setup match the rest of the wizard** (UX-57, UX-58) — the last two groups that did not. The **word box**'s four coordinates are one row of names over selects instead of four stacked rows: `_render_box_format` reserves that row and `_row` drains it, rather than the box borrowing the group's `columns_per_row` — which is keyed on *top-level* specs and would have flowed the edges/origin radio into a cell meant for a select. **Recording setup**'s three groups sit side by side with their headings level, each column starting with its own radio (what follows one depends on the answer, so the columns end at different heights but begin together); the headings shorten to *Screen* / *Physical size* / *Text size* **for display only**, leaving `SETUP_GROUP_LABELS` — and so the review table and the blockers — reporting the full names. Both groups' descriptions move onto their titles' hover, finishing what UX-53 started: `_render_box_format` and `_wizard_setup_step` wrote theirs directly rather than through the shared helpers, which is how they were missed. Nothing preselected is intact — all three setup radios keep `index=None`, and `setup_blockers` still holds **✅ Add dataset** until each is answered.
- **Every wizard field's title sits above its control** (UX-53) — the stacked shape was inferred from the field count (`columns_per_row > 1`), which was wrong for a *single* field dropped into a row the caller had already laid out: the Screen ID and Screen name pickers arrived on the identity rows with their titles beside them while every neighbour had its title above. `column_mapping_ui` takes an explicit `stack_labels` now, defaulting to the old inference, so the wizard stacks everywhere and the 🗂️ Data page's editor keeps `label | field`.
- **A mapping dropdown never truncates a column name** (UX-53) — the mapping packs six or eight selects onto a line, so the *control* is narrow by design; BaseWeb sizes the open menu to its anchor, which made the list inherit that width and clip the names being chosen between. The menu is now sized to its content and may overhang its column, and an option that is still too long wraps rather than ellipsising — a truncated column name is the exact failure being fixed, since two columns can share a visible prefix. Necessarily a global rule: the popover is portalled to the body, so it cannot be scoped by our own `.st-key-…`.
- **One picker per table, and a whole theme on one row** (UX-53) — the *Different … per table* toggles are gone. They were a mode switch guarding a case that costs nothing to show: **Fixations** and **AOI** now each get their own Trial ID, Participant ID and Text ID picker, seeded from the same proposal, so identical columns stay identical and a genuine difference no longer hides behind a control nobody finds. With that, *Trials & readers* becomes **one row per table** — a Fixations line and an AOI line, each holding that table's Trial / Participant / Text / Screen ID / Screen name pickers behind a single name at its head — the multipart screen fields moved in beside them, since a screen id is part of how a multipart trial is *identified*, which also retired the *Words / Interest Areas* and *Fixations* sub-headings that block carried. *Screen order* is relabelled **Screen name**; its tooltip still states the requirement, which is unchanged — the column has to be a positive 1-based number, because `multipart` orders screens by it, so you read across a line to see how one table is identified and down a column to see whether the two agree. The other themes pack onto one row each (the six fixation fields, the raw-gaze eight), each cell writing its title first and its select second, so the titles line up on one line and the controls on the next. Counts and other sentences move to a full-width strip under the row, since a sentence in a sixth of the width is a column of single words. `col_map_<table>_<field>` was already the stored value, so save/restore and deep links are unchanged; the extra `col_map_<field>_unified` key simply stops being written.
- **Choosing a mapping approves it; clearing one drops the suggestion** (UX-53) — two rules about *who decided*. Picking a column now turns the row **green even when it is the column detection already proposed**: amber means "nobody has looked at this yet", which stops being true the moment someone picks. And clearing a detected field goes **neutral** rather than back to amber — the ✕ is a decision that this column is *not* the one, so continuing to flag the suggestion would argue with the user; it stays red only while the field is required and an add has been attempted, because then it is genuinely blocking. The approval is tracked in one session key outside the `col_map_` namespace (anything named that way is swept into saved configs as if it were mapping), is sticky once given, and is discarded together with the field when a new table re-proposes it.
- **A field's clear button is Streamlit's own, inside the select** (UX-53) — the mapping's `"(none)"` *option* is gone; "not mapped" is now the select's real empty state, which is what turns on Streamlit's built-in clear (its selectbox sets `clearable=(index is None)`). So every field carries a **✕ inside the control**, and the first cut — a button of ours beside it — is deleted. The value lives in the widget key with `index=None` passed on every run, since `index` is only a default and passing a real one would switch the ✕ back off. Three states are handled where the key is seeded: absent seeds from auto-detection, a stored value this table cannot offer is blanked (a legacy `"(none)"` from a saved config, or a column a new upload lacks — Streamlit raises on a stored value outside `options`), and an existing `None` is left alone, because that is the user having cleared it on purpose.
- **The wizard is two linear parts, with the dataset name above both** (UX-53) — **1 · Upload data files** then **2 · Map data fields**. They run in a fixed order (there is nothing to map before a file is read), so `wizard_shell.part()` *labels* them rather than navigating: a one-line headline with a numbered chip, no expander, no open state, and none of the DATA-19 / DATA-22 collapse machinery. The progress chips are gone with it — they were navigation for an accordion that no longer exists, i.e. a menu with one path through it. The **dataset name** moves above both parts and is set larger than an ordinary field: it names the whole thing, so it belongs to neither the upload nor the mapping. The tour's two cards anchor to the parts' own container keys (`wiz_part_*`) now that there are no keyed expanders to borrow a selector from.
- **Mapping fields share a row instead of one per line** (UX-53) — `column_mapping_ui(columns_per_row=…)` packs as many selects onto a line as fit: fixation **X / Y / timestamp / duration** now occupy one row where each took its own, with *Fixation ID* and *Word/IA ID* completing the four-across grid. Above one per row the shape flips from `label | field` to label-over-field — four labelled pairs side by side would leave a sliver for each select — and the ✨ flag moves up beside the label, its cell reserved before the select renders because the flag depends on the value the select returns. Word **id / text / line** go three across, the raw-gaze fields four, the multipart screen fields two. The fixation block also loses its second heading: *Fixations & text* plus an inner **Fixations** was two titles for one group of controls, and the section is now simply **Fixation features**, with **Word features** and **Raw gaze features** under it. The 🗂️ Data page's own mapping editor keeps one field per row (the default), where the width is shared with a preview table.
- **The setup page drops its summary card, and raw gaze joins the other tables** (UX-53) — the auto-detect card (*✓ Trial id — Trial_Id* … *⚠️ Word box — not detected*, *Map whatever is missing in the next two steps*) restated in a block of its own what every field now shows in place: the ✨ flag and the select's tint say detected-or-not per row, and a missing required field turns red and is listed above **✅ Add dataset**. With the fields all on one screen it had become a second copy of what sat directly below it. The **raw gaze** upload comes out of its popover to stand beside Fixations, Words/IA and the participant table — it is an upload like the rest, and hiding it made it look like a different kind of thing. The participant table loses its *About your readers* heading — it is one uploader among four, not a stage — and is renamed **Participant metadata table (optional)**, with its paragraph on the uploader's own tooltip.
- **Explanatory text on the setup page is hover-only** (UX-53) — the wizard's prose was the bulk of its length and most of it is read once. Section headings, the privacy note and the per-field explanations now carry their sentences as a `.sps-fhelp` tooltip (`wizard_shell.section(caption=…)`, `wizard._hover_note`) — the same CSS mechanism UX-51 uses for the rail, chosen over the browser's native `title=` because that waits about a second. The words are still there; they stop costing a line each. A dotted underline marks what is hoverable, since the page has no neighbouring `?` to imply it.
- **The wizard is one part, and *Advanced* is gone** (UX-53) — two parts was still two headers and two clicks for one continuous job, so `wizard_shell.STEPS` is a single *Set up your dataset*. The `⚙️ Advanced` disclosures went with it — no popover and no *Advanced* heading; those fields simply sit last in their section, which is what "advanced" ever meant. **Screen-local fixation ID** and the two **Screen canvas** fields stop being rendered at all: `controls._HIDDEN_MAPPING_KEYS` resolves them from auto-detection inside `_assemble_mapping`, so multipart datasets keep their per-screen canvas and no downstream schema narrows — what is gone is three widgets nobody set, not the fields.
- **The upload wizard is two parts, not seven steps** (UX-53) — the seven-step accordion (DATA-22) meant the mapping you were checking was never on screen beside the mapping you had just set: each topic cost a click, and the fields you needed to compare sat in different panels. `wizard_shell.STEPS` is now **1 · Your data** and **2 · Map it & add it**, and the former steps survive as `SECTION_TITLES` rendered through a new `wizard_shell.section()` — a one-line heading rather than an expander, so every field is visible at once. Sections carry no open state, which is why they sidestep the DATA-19 / DATA-22 collapse hazards entirely; the "only the shell moves the accordion" rule still governs the two real steps. Part 2 now reads top to bottom: **dataset name** (promoted out of the old step 7, where it sat below every mapping field) → *Trials & readers* → *Fixations & text* → *Recording setup* → *Extra fields* → what is still missing → **✅ Add dataset**, with the blockers directly above the button they block and naming their section instead of offering *Go to step N* buttons. The four `⚙️ Advanced` popovers — derive-ids-from-filename, multipart screens, more fixation mappings, more text mappings, raw-gaze mapping — are inline blocks now: advanced is a reason to place a control last, not to hide it behind a click. DATA-20's participant table moves up into part 1, beside the uploads it belongs with. ***Screen-local timestamp (ms)* leaves the mapping** — a second clock for the same fixations, when the parent-trial timestamp already orders every screen; `screen_timestamp_ms` remains a passthrough column, so corpora that ship one keep it. *Screen / part ID*, *Screen order* and the canvas fields are unchanged. The wizard guide (`tour._WIZARD_GUIDE_STEPS`) follows, seven cards to two.
- **Tracker write-ups are structured fields, not bold-led prose** (ENG-38) — an item's four-paragraph write-up lived entirely inside one `body` array as `**Request.**` / `**What was done.**` prose leads, which coding agents dropped, reordered or reworded often enough to be worth making structural. Each section is now its own field on the item — `request` (required), `whatWasDone`, `whatsLeft`, `background`, plus an optional `statusNote` lede — so a missing section is a missing key, and three new tests in `tests/test_tracker_server.py` fail on one rather than letting it rot. All 116 open items were migrated word-for-word (the script reused the original string literals, so no escape or code anchor moved); the 144 archived items keep the legacy `body` array and both shapes render. `tracker/index.html` prints the section label itself, so the bold lead is gone from the text, and search spans the new fields. The same pass writes the *keep it current* discipline into `data.js`, the tracker's own *How this works* panel, `CLAUDE.md` and the `/track` skill: flip to `In progress` when you pick an item up rather than when you finish, clear an answered decision in the same edit that acts on it (even before implementing) and record the call in `background`, and commit one feature or fix at a time with the tracker edit in the same commit as the code.
- **One-click status moves, and one home for everything waiting on you** (ENG-38) — two follow-ups to the structured write-up. *Directed transitions*: expanding an item now shows the moves that status actually makes, the likeliest one first — Backlog → *Plan it* / *Put on hold*, Planned → *Start work*, In progress → *Ready for review*, On hold → *Resume*, Review → *Approve & close* / *Send back*, Closed → *Reopen*. A click sets the status **and saves**, so the common move is one action instead of hunting through a dropdown and then pressing *Save changes*; the dropdown stays for anything off that path, and a test fails if a status loses its moves. *One home for what needs you*: `whatsLeft` is now strictly the developer's remaining work — on a finished item it honestly says "Nothing" — and everything waiting on the user moved into `decisions`, both the design calls that block the work and, once it is built, the ask to review it. That box is relabelled **Waiting on you**, badges the card **⚖ N for you**, and feeds the *Waiting on me* filter, so one click now lists every item holding on the user; previously half of that was prose buried inside *What's left* and only findable by reading each item. Two tests hold the split: an item in `Review` must carry a `decisions` entry, and `whatsLeft` may not address the user.
- **CONTRIBUTING covers joining an in-flight project, not just opening a PR** (ENG-39) — the setup section now ends where a new contributor actually starts: `python3 tracker/server.py`, left running, with a note that a taken port belongs to somebody else's server rather than being yours to kill, and a pointer at the `CLAUDE.md` / `AGENTS.md` pair an AI assistant reads on its own. A new **Working together** section writes down what had only been habit: claim a tracker item by flipping it to `In progress` *and pushing that* before you write code; pull before you start, commit one change at a time, push often, and don't sit on a large uncommitted tree; resolve a `tracker/state.json` conflict by keeping **both** sides' entries and setting `revision` to the higher plus one, never by taking a side, then reload the page; and check the next-free-ID panel again after pulling, since two people adding to one group reach for the same number. The test command is now `uv run pytest` throughout — a hand-managed virtualenv that has drifted to an older pandas passes tests CI then fails, pandas 3.0's string inference being the usual culprit. #ENG-39 tracks the two tracker changes this section works around: an `owner` on the item, and a `revision` that does not conflict on every pull.
- **The tracker records who has an item, and state.json stops conflicting on every pull** (ENG-39) — `In progress` said the work had started but not by whom, so the only way to avoid picking up something already underway was to ask. Items now carry an `owner` from a fixed list (`TRACKER.people` in `data.js`), set by a **Claim** / **Release** button that works from any status — claiming is not the same as starting, so you can take something still in Planned. The card shows **👤 name** beside the status and the sidebar gains an *Owner* facet (each person, plus *Unassigned*); an owner outside the list is a rejected save rather than a third person who does not exist. Who you are is resolved once from `git config user.name`, matched token-wise against the list so "Omer Shubi" becomes `Shubi` with nothing configured, and a header picker overrides it. Separately, the `revision` save counter moved out of the git-tracked `tracker/state.json` and into a gitignored `tracker/.local.json`: it changed on **every** save, so it conflicted on every parallel pull even when two people had touched different items, while the two-tabs-on-one-machine protection it provides is per-machine by definition. `state.json` is now sorted one block per item, so disjoint edits merge without asking. The server reads a version-2 file with `revision` still inline and writes it back without, so nothing needs migrating by hand — **but restart `tracker/server.py` after pulling**, since the old process cannot read the new file.
- **One Data page — the source, the column mapping, the tables and preprocessing in one place** (DATA-26) — setting a dataset up was two jobs on opposite sides of the app: the source picker, its data location and its column mapping sat in a **⚙️ Configure** menu popover at the top, while the same dataset's name, counts, raw tables and a *second* column-mapping editor sat in a **🔎 Data Inspection** subtab buried inside the Scanpath view. You had to know both places existed and that they were the same task. There is now a third top-level view, **🗂️ Data** — *"Set up your dataset"* — holding all of it in pipeline order: data source · description · options · data location · the add-a-dataset wizard · **Column mapping** · what's in the dataset (name + ✏️ Rename, headline counts, raw tables, derived tables, summary statistics, trial identity) · recording setup · **🧹 Preprocessing**. ⚙️ Configure and 🧹 Preprocessing have left the menu bar, and 🔎 Data Inspection has left the Scanpath subtab bar; what remains on the bar is genuinely session-wide (💾 Save & restore, 🗄️ Recovery cache, ❓ Help). The two column-mapping editors became **one section with three modes**, resolved from the dataset's own state — the editable pre-normalization panels for a raw source, the post-normalization remap form for an upload you stored, a read-only table for everything else — so the same question is never asked twice on one page. Preprocessing belongs here rather than in the Scanpath rail because it reshapes the frames *every* view reads, including Corpus Analysis, which has no rail. Nothing moved on the wire: no `global_*` / `single_*` / `filter_*` key changed, so share links, saved configs, the CLI and the Python API are untouched. Under the hood the page is built on every rerun and merely hidden when another view is showing — the loaders' directory input, ⬇ Download button and mapping selectboxes drive the load itself, and Streamlit discards the state of a widget that did not render, so rendering-then-hiding keeps exactly the semantics the popovers had. Entering the add-dataset wizard now takes you to this page, and an unfinished dataset says so from the other views with one click to get there instead of leaving a blank screen.
- **Rail controls read as a form: label beside the field, not above it** (UX-51) — every control in the plot rail stacked its label above its field, so the 👁️ Fixations → ⚙️ Style popover spent well over a screen's height on eight controls. Labels now sit to the **left** of the field on one shared column width across the whole rail, so they line up down *and* across sections, and each control's `?` icon is gone: its help is the label's own hover tooltip, which buys back a column on every row and is what makes a truncated label recoverable. Converted across ⚙️ Style / 🧹 Filter for Fixations and Saccades, 📄 Stimulus, ⚙️ Stimulus image, 🔥 Overlays, 📊 Axes & grid, 🏷️ Title & labels and the trial-filter **More** panel. Sliders keep their number box and centre the label on the track rather than on the value printed above it. Layout only — no setting, key or default moved, so share links, saved configs, the CLI and the Python API are untouched. The pass now covers the whole rail: ⚙️ Playback and ⚙️ Compare options came over too, and 📐 Figure & canvas's 🖥️ Screen & geometry / 🔤 Text & fonts panels do it in the rail while the setup wizard's copy of the same form stays label-above (that step *is* the form, laid out across the page, so there is no height to buy back). Playback's *Frame every* and *Max frames* went from two half-width columns back to full width — a label-left row is one row either way, so each slider gets a usable track for the same height. The label's tooltip is **CSS, not the browser's native `title=`**: it opens in 120 ms, the same feel as the `?` icons Streamlit draws elsewhere, where the native one waited about a second — unusable when it is where every row in the rail keeps its description.
- **The Data page has one heading level and folds its tables away** (UX-52) — the page was four stages deep but read flat: five same-weight `st.subheader`s separated by five dividers, with the source block opening on no heading at all, so the headings below it read as the whole page rather than as three of its four parts. It is now four peer sections — **📂 Data source · 🔤 Column mapping · 🔎 What's in this dataset · 🧹 Preprocessing** — one divider between each, and everything inside a section is subordinate to it. The answer stays open (the dataset's name, the headline counts, the provenance banner, the trial-identity verdict) and the appendix folds: **Raw data**, **Derived analysis tables**, **Summary statistics** and the identity evidence table are collapsed expanders, so the page opens on the counts and the mapping instead of several screens of dataframe. Every expander body still renders on every run — collapse is client-side, so no widget key is dropped, which is the rule that makes the whole page work.
- **The column mapping reads as a form, and hides what only multipart data needs** (UX-52) — every mapping row is now `label | field` on UX-51's shared label column, with the ✨ auto-detected caption under the *field* rather than under the label. The six multipart/canvas fields — Screen / part ID, Screen order, Screen canvas width/height, and the fixations table's screen-local timestamp and fixation id — fold into an **⚙️ Multipart screens & canvas — advanced** group; all six are optional and inert for an ordinary single-screen corpus, and together they were half the rows. The group opens by itself when the dataset actually maps one of them, so a multipart corpus never hides its screen mapping. **🔎 What's in this dataset now comes before 🔤 Column mapping**: the counts answer "did it load, and is it the right size?", and the mapping is what you scroll to when they look wrong (a dataset whose mapping is still broken keeps its raw tables *below* the editor, so the controls that fix them are never under the tables they explain). The ✨ auto-detected note then moved again, into a **third column beside the field** rather than under it — the rows were two lines tall while the right half of a full-width page sat empty. On the bundled demo the mapping section is now **1601 px against the original 2698 px**, with nothing hidden that was not hidden before. Separately, **🧾 Trial identity is its own section** instead of an `#####` item at the foot of the counts: it carries a *verdict* — sometimes a warning — and the fix it names is an edit to the Column mapping directly above it, so a level below the counts was the wrong place for both.
- **The tutorials follow the app as it is today, and "explore a corpus" answers a real question** (UX-40) — *Explore a corpus question* was two steps where the others are four or five, and it named the three subtabs without answering anything — a menu, not a tutorial. It now walks one question end to end: **Per reader → View: Per-trial trend → fixation duration**, i.e. did this reader speed up over the experiment, with an optional closing step putting them against the cohort. The five flows were also written before the 🗂️ Data page existed and had drifted. *Load and verify a dataset* is now four steps that walk the page in its own pipeline order (source → column mapping → what's in it → preprocessing) rather than two that describe the old subtab; *Filter and mark trials* gains an optional step for the multipart screen navigator; *Build a publication figure* ends at 🔗 Share, because a PNG on its own does not reproduce a figure; and *Compare readings* no longer promises a similarity ranking this build hides — the NLD sentence appears only when `SCANPATH_EXPERIMENTAL=1`, the same honesty rule the FAQ already followed. The chooser is five bordered cards instead of a flat wall of captions: one **Start** button, the step count and time, and **Start over** only once there is progress to discard.
- **The menu bar is down to Help and Session** (UX-38) — the placement pass the top bar was always meant to get. **Help leads**: it is the one group a first-time user is looking for, and the only one they can reach before they have a dataset. **Save & restore and Recovery cache merged into one 💾 Session group** — both answer *what is kept, and how do I get it back*, differing only in whether the state travels to another machine, which is why neither sat comfortably beside dataset setup or figure styling; the portable JSON is on top, the on-device cache below it, under one trigger. With ⚙️ Configure and 🧹 Preprocessing gone to the 🗂️ Data page (DATA-26 above), the bar is two buttons instead of five. The trigger key is unchanged, so the guided tour's spotlight and the annotations panel's "jump to Save & restore" both keep working.
- **The sidebar is gone — a top menu bar and Streamlit's native top navigation replace it** (UX-38) — every group that lived in the left sidebar is now a popover on a horizontal bar under the header: **⚙️ Configure** (the data source, its options, where its files are, and its column mapping), **🧹 Preprocessing**, **💾 Save & restore**, **🗄️ Recovery cache** and **❓ Help**, plus **🐛 Debug** under `?debug=1`. (The first two have since moved to the 🗂️ Data page — see DATA-26 above.) Nothing writes to `st.sidebar` any more, so Streamlit draws no sidebar chrome at all and the page is full width; `initial_sidebar_state` is gone from the page config, and with it the tour's machinery for prising the sidebar open (a retrying click on the expand control, gated on `aria-expanded` because a collapsed sidebar still reports a nonzero size). Panels that used to wrap themselves in an expander now render bare — the popover trigger is the disclosure — and the two that were popovers inside the Help group (**🧭 Tutorials**, **ℹ️ About**) became dialogs, since Streamlit nests neither popover-in-popover nor expander-in-popover. Roomier, not tighter: the sidebar was ~21 rem and a popover is 28–32 rem. Top-level navigation is now Streamlit's own **`st.navigation(position="top")`**, so **Scanpath** and **Corpus Analysis** sit in the header strip as platform chrome, both always visible with the current one marked — replacing the single right-aligned button that showed only the place you were *not*. `main_nav` survives as a mirror of the router's selection, so the tour, the recovery cache and every existing reader are unchanged. Switching view also *looks* immediate now: Streamlit leaves the old page painted until the new one overwrites it, so a click on Corpus Analysis used to leave the scanpath sitting there for the length of a full rerun; a loading bridge now claims that space at once. Load-time warnings that used to sit in the always-visible sidebar (an unusable raw-gaze schema, raw gaze that doesn't overlap the trial filter) render in the page instead, because a warning inside a closed popover is invisible. No widget key moved, so share links, saved configs, the CLI and the Python API are untouched.
- **Trial filters are prefix-scoped** (CMP-8) — the nine `controls.py` filter helpers take a key `prefix` (default `""`, so every existing call site is unchanged), and the "Clear all filters" sweep matches its own namespace instead of every key starting with `filter_`. This is the groundwork for compare mode's scanpath B carrying its own filters; nothing new reaches the share link or saved config, since `filter_*` was never wire format.
- **The visualization rail scrolls independently and packs controls more tightly** (UX-43, UX-44) — the rail now matches the plot row's height and scrolls without moving the plot or the plot-width subtabs below it. One **🎛️ Plot controls** heading replaces separate mode/visualization headings; the presets retain their **Quick views** caption; Fixation/Saccade popovers use contextual **Style** and **Filter** labels; Saccades starts collapsed; canvas/text and axes/labels share **📐 Figure & canvas**; and the scoped **↺ Reset** popover sits beside the heading. At very narrow rail widths that header stacks, and the popover reserves enough room for Streamlit's disclosure chevron. Scrolling past either end of the rail now carries on into the page instead of stopping dead, so reaching the reset control at the foot no longer traps the scroll there.
- **One figure-settings contract now powers every renderer** (ENG-28) — the UI, headless API, bulk export, static scanpath, animation, and comparison paths share `FigureSettings` instead of forwarding dozens of parallel arguments. Public `plot_scanpath` and `animate_scanpath` keywords remain unchanged.
- **Core module ownership is one-way** (ENG-28) — MultiplEYE server loading belongs to `datasets.py`, while run materialization belongs to `measures.py`, removing the `data`/`datasets` and `measures`/`preprocessing` import cycles.
- **Every control row above the plot shares one column grid** (UX-47) — the rows stacked above the plot — data source + **Filter by**, the trial picker, the multipart screen navigator, the chip strip, and in Compare mode the second dataset's picker and its own filters — were each built with their own column weights, so nothing lined up: the source dropdown ended 50 px short of the trial dropdown directly below it, and the filters started 38 px left of the scrub slider they sat above. They now share **one three-track grid** (pick · scrub · act), so every left edge, every track boundary and every right-hand pill cluster agrees down the whole stack, at any window width. The ➕ *Add data* button joins the shared pill shape it had never adopted — it was a 40 px stretched rectangle beside 27 px pills, and it alone made that row the tallest of the four. On a multipart trial the child-screen row already followed the trial picker (scrubbing slider, ◀ ▶ in the right-packed cluster); a single-screen trial still shows the dropdown alone. Layout only — every selection, step and deep link is unchanged.
- **Figure & canvas is grouped instead of one long list** (UX-48) — the rail's **📐 Figure & canvas** section held roughly twenty-six controls in one flat run, separated only by two bold captions. It now has the same shape as every layer group: **Show full monitor** stays inline, and everything else opens in a named popover — **🖥️ Screen & geometry** (monitor pixels, physical size, viewing distance, DPI, px/degree), **🔤 Text & fonts** (scale-to-boxes, line spacing, font sizes and typeface, text colour, plot background), **📊 Axes & grid** (coordinate grid, colour bars, X/Y axis fields) and **🏷️ Title & labels** (Illustration label, figure title/caption). Five rows instead of twenty-six. The title/caption pattern boxes are now inline in their popover rather than behind a second one, and the same two canvas popovers appear in Corpus Analysis. No setting was added, removed or renamed, so share links, saved configs, the CLI and the Python API are unaffected. The upload wizard's *Recording setup* step stays flat — it is a form to read at a glance.
- **A layer section's own toggle reads "Visible"** (UX-50) — inside the rail's **👁️ Fixations** and **↗️ Saccades** sections, the layer toggle repeated the section header one line below itself; it now reads **Visible**. The other two sections keep their names, because their toggles name distinct layers (Text / Bounding boxes / Stimulus image, Heatmap / Raw gaze data) rather than repeating the section. Label only — no key, setting or surface changed.
- **Nothing is hidden behind a URL param any more — debug mode and the ground-truth trial are both in the UI** (UX-37) — two features were reachable only by hand-editing the address bar, which meant only someone who already knew they existed could find them. **Debug mode** is now a **🐛 Debug mode** toggle at the foot of **❓ Help**; turning it on adds the 🐛 Debug popover to the menu bar with the captured log, the state snapshot and the JSON download to attach to a bug report. The **🧪 Synthetic test trial** — the hand-checked ground-truth trial the AI-assistance note asks you to verify the measures against — is a normal entry in the data-source picker instead of being offered only once something had already selected it, and the note, the docs and the README now name that entry rather than quoting a URL. Both old links (`?debug=1`, `?source=synthetic`) keep working: `source=synthetic` is still how a share link encodes that dataset, and `?debug=1` now pre-arms the toggle rather than being the gate — so a session that opens on such a link can still switch debug mode back off. Debug mode also *does* more now: the app logs its expensive stages with how long they took (normalization, figure building — only on a cache miss, since a hit and a miss look identical on screen) and one line per real state change (dataset ready, view, filters applied), so the panel answers "what did that click actually do?" rather than only showing warnings. The **🧪 Synthetic test trial** is offered in the data-source picker **while debug mode is on**: it is a six-word verification fixture, not a corpus, so it sits with the developer affordances rather than in every user's source list. The panel now shows the app's *own* log rather than the whole process's: the capture handler sits on the root logger, and raising the root level to INFO to catch our lines switched on every library in the process at once — tornado logging a line per websocket frame, watchdog per filesystem event — which buried the six lines worth reading under hundreds of identical ones. The level is scoped to the app's logger, third-party records are dropped unless they are a warning or worse (a library that failed is exactly what a bug report needs), and identical lines are **collapsed into one row with a × count** so a rerun-heavy session can no longer push real events out of the buffer. The state snapshot gained a **(?)** explaining what it is and why to send it. The AI-assistance note itself is back to three lines — built with AI assistance, cross-check before publishing, here is where to report it; the two paragraphs telling you how to verify the measures were cut as clutter, and the guarantees they described keep their tests.
- **Three more corpora reconstruct their published screen, and one stops claiming a screen it never had** (DATA-27) — a pass over the eleven corpora that had no display-parameter entry, applying one rule: `reconstructed` requires a **published** parameter, not a plausible one. Three of the eleven have one, and now reconstruct their real layout instead of a generic 1920×1080 — **OneStop** (Dell U2715H, 2560×1440 over a 597 mm display area, 25 pt Lucida Sans Typewriter in a published 19 px × 38 px letter cell, 76 px line pitch, 1824 px text column; Berzak et al. 2025), **the Russian Sentence Corpus** (1920×1080, 22 pt Courier New at 90 cm, 0.29° per character; Laurinavichyute et al. 2019) and **Beijing Sentence Corpus II** (1920×1080 at 70 cm, Song font at 1.1° per character; Yan, Pan & Kliegl 2025 — a different lab setup from BSC a decade earlier, not an inherited one). Going the other way, **MECO L2 Wave 2** loses its entry and falls back to `synthesized`: neither source it cited contains the 1920×1080 it asserted — the paper never prints that resolution, says font size ranges 20–22 *points* "given variation in screen size and resolution at different testing sites", and defers the screen to per-site supplementary materials, while the review table it also cited has a null resolution and a link to those same materials where a monitor would go. Its `font_px=21` was the midpoint of that point range used as a *pixel* size, which is a unit error on its own terms. That is a visible downgrade for one corpus and the correct direction: an unsourced `reconstructed` is worse than an honest `synthesized`, because nothing on screen tells you it is a guess. The other seven stay `synthesized` for reasons now recorded in the code — the MECO waves are multi-site by construction (Wave 1 of L1 states outright that a common font size, distance and resolution were "unfeasible"; Wave 2 tabulates sixteen different screens), Reading Brain and OASST-ETC publish physical geometry but not the pixel resolution that would have to be invented, and PSC2 is the trap: a complete apparatus *is* published for those sentences, but for the oral-reading experiment already in the table as Eye-voice span, not for the 149-reader silent-reading collection actually shipped — so it is pinned `synthesized` by a test that names the trap. Supersedes the tier counts quoted in *Word-box geometry recovered in four tiers* above: the published-parameter table now covers 22 corpora, and the thirty prepared corpora divide 1 `real` / 20 `reconstructed` / 9 `synthesized`. **The change reaches a corpus only when its bundle is re-prepared** — the tier and the declared monitor are written into the manifest by `scripts/prepare_eyegenbench.py`, so an existing bundle keeps whatever it was built with until the corpus is prepared again.
- **Drift correction and NLD similarity are not exposed in this build** (PRE-21) — two features are built but not fully integrated, and shipping a half-wired control invites results it can't support: **vertical drift correction** (the rail's *Drift correction* picker, its connectors, and the whole **📐 Line assignment** subtab) and the **NLD similarity scoring** under 🔬 Comparisons (the *Similarity to the selected scanpath* table — where three of its four metrics still read "Not yet computed" — and the *Metric convergence* plots). Both are hidden, on **every** surface: the controls, the deep link, the saved config, the export manifest, the `render --drift-correction` flag, `api.plot_scanpath(drift_correction=…)`, `api.alignment_sensitivity`, the FAQ entry and the docs. Nothing was deleted — `alignment.py` and `similarity.py` ship unchanged and `SCANPATH_EXPERIMENTAL=1` turns everything back on. The **Comparisons** grid itself stays; only the scoring comes off it, so it now orders alphabetically by the comparison column and shows more panels (the 24-panel cap existed to keep a *ranked* grid readable), with the cap still stated in the caption so it never silently truncates. Links and saved configs naming drift correction are ignored **silently** rather than warned about; the headless API instead **raises**, naming the env var — a person can see that a figure came back uncorrected, a script cannot.

## [0.28.0] - 2026-08-08

### Added
- **Reset settings** (UX-26)
- **Draw only some saccade types** (VIZ-31)
- **Title & caption on the figure, live on the rail** (EXP-5)
- **Per-chip colour highlight, for any dataset** (UX-28)
- **Editable Compare A/B legend labels** (UX-31)
- **Pick which columns "Stimulus & questions" shows** (UX-32)
- **FAQ: "I edited the code and nothing changed?"** (UX-35)
- **A coverage badge, a published coverage report, and a CI floor** (ENG-37)

### Fixed
- **Reruns are ~28× faster, and per-trial subtabs load on demand** (PERF-3)
- **Author a scanpath: edits stick, and "Target word" is explained** (BUG-19)
- **The compare-mode heatmap now actually draws** (CMP-7)
- **Changing a rail setting mid-rerun no longer crashes the app** (BUG-18)
- **Rail labels no longer break mid-word** (`styles.py`)
- **Stimulus & questions no longer shows bogus Q&A fields on generic uploads** (UX-32)

### Changed
- **The data-source picker moved into the main view** (UX-25)
- **The visualization rail is grouped instead of flat** (VIZ-31)
- **Canvas, font and background controls moved to the rail** (VIZ-31)
- **Colourblind-safe is now the default palette** (VIZ-32)
- **The three control rows above the plot read as one cluster** (UX-27)
- **Title & caption moved into a popover, and the `{field}` vocabulary is documented** (EXP-5, UX-31)
- **Trial picker reads "Select Trial"** (UX-33)
- **About panel's AI-assistance note trimmed to match the docs** (UX-36)
- **View modes: neutral section icon, and the Playback popover tightened further** (UX-30)
- **Quick-view labels fall back to emoji-only when the rail is narrow** (UX-29)
- **Welcome tour: copy, step order and highlighting polish** (UX-34)
- **CHANGELOG entries: a Slack-pasteable headline, details below** (ENG-34)
- **Runtime moved to Streamlit 1.61.1** (ENG-31)
- **Widget values now persist natively instead of by hand** (ENG-36)
- **Raw data tables scroll instead of paginating** (ENG-36)
- **Open a trial straight from a Corpus Analysis table** (ENG-36)

### Removed
- **Five helpers nothing referenced** (ENG-28)

### Details

#### Added
- **Reset settings** (UX-26) — a **♻️ Reset settings** popover at the foot of the rail puts every visualization control back to the app's defaults in one click (annotations, trial filters, column mapping, data source and the selected trial are kept); it also strips the viz parameters from the URL, so the reset sticks on a page opened from a Share link. Trial filters get their own permanent **✕ Clear all filters** button at the foot of the **More** filter popover, instead of only appearing once a filter left nothing.
- **Draw only some saccade types** (VIZ-31) — a new **🧹 Saccade filter** picks which reading classes are drawn at all (forward, skip, refixation, return sweep, regression), so a regressions-only figure takes one click instead of colouring the other four to match the background. Hidden classes lose their direction arrows too, and it composes with any saccade colour mode. On every surface: the rail, the share link (`?saccade_classes=`), the saved config, `scanpath-studio render --saccade-classes`, and `sps.plot_scanpath(saccade_classes=…)`.
- **Title & caption on the figure, live on the rail** (EXP-5) — the EXP-2 pattern-language title/caption is no longer Export-only: a **📐 Figure & axes → Title & caption on the figure** control shows it live on screen (all three render paths — static, animation, compare), and both **This trial** and bulk export now read it back instead of the old Export-only toggle. On every surface: the rail, the share link, saved configs, `scanpath-studio render --title/--caption`, and `sps.plot_scanpath(title=, caption=)` / `sps.animate_scanpath(title=, caption=)`.
- **Per-chip colour highlight, for any dataset** (UX-28) — the ✏️ Edit chips popover gained a colour picker per shown field, generalizing what used to be a handful of hardcoded OneStop-only chip colours (difficulty/preview/repeat/correctness), which still apply as defaults until overridden.
- **Editable Compare A/B legend labels** (UX-31) — the ⚙️ Compare options popover's **Show A/B legend** now has Label A / Label B pattern overrides (same language as the title/caption control above), applied on both the static comparison figure and the dual-animation co-animation, and saved with the rest of the per-scanpath compare styling.
- **A coverage badge, a published coverage report, and a CI floor** (ENG-37) — `pytest-cov` was a dependency that nothing invoked. Coverage is now configured in `pyproject.toml` (with a `fail_under` floor and the two one-shot data-prep scripts omitted — they walk corpora that cannot exist in CI), a `Coverage` job runs it on every PR and prints the table into the run summary, and the browsable HTML report ships with the docs site so the README badge links to it. No third-party coverage service and no new secret. The audit that came with it closed the thinnest gaps: `experimental_setup.py` (the DPI / pixels-per-degree conversions behind every visual-angle number) went 69% → 100% with hand-computed expectations, `debug_log.py` 47% → 91% including the HTML-escaping of log messages, and `python -m scanpath_studio` is now exercised as a real subprocess. A second pass then covered what the on-demand subtabs had quietly stopped exercising — the ten-algorithm drift-correction grid and the same-text generations comparison now have tests that open and drive them, where before they were only ever rendered incidentally — and the GIF/MP4 export panel, whose ~100 lines had never run under test at all (the existing test's "no exception" turned out to be vacuous: changing session state let the tab bar fall back to its default, so the panel silently didn't render). Overall: **90%**, floor 89.
- **Pick which columns "Stimulus & questions" shows** (UX-32) — the panel highlights spans and lists question/answer fields by matching column *names*, so a corpus whose critical span is called `focus_region`, or whose question column is `q_text`, got nothing out of it. A **⚙️ Fields** popover now lets you choose both lists yourself: the name matching picks the defaults, and everything else about the trial is offered — every per-word true/false column as a possible span, every trial-level column as a possible field, numeric ones included. Your choice sticks while you step through trials and goes back to auto-detection when you switch to a differently-shaped dataset.
- **FAQ: "I edited the code and nothing changed?"** (UX-35) — the module-reload / `st.cache_data` gotcha (already documented for contributors) now has an in-app FAQ entry and a `docs/faq.md` entry too, distinguished from the on-device Recovery cache.

#### Fixed
- **Reruns are ~28× faster, and per-trial subtabs load on demand** (PERF-3) — changing a fixation colour, a colorscale, or anything else on the rail left "Running…" up for many seconds. Neither suspect in the triage notes was to blame; the cause was that **Data Inspection is a subtab**, and Streamlit executes every subtab's body on every run — only the *display* is client-side. So its six derived analysis tables (Sentences / Saccades / Trials / Readers / Characters / Cleaning QA) were rebuilt on every single rerun of the Scanpath view, whether or not the tab had ever been opened. Two fixes: they are now built once per dataset behind `@st.cache_data` keyed on the frame fingerprints, and `preprocessing.saccade_table`'s letter-position lookup — which scanned the *entire* words frame twice per saccade — now indexes the word geometry once up front. On the bundled demo a rerun went from ~12.9 s to ~0.45 s, and the same work no longer scales with corpus size on every keystroke. (The test suite got ~4× faster with it.) A second pass then made the four expensive per-trial subtabs — **Comparisons**, **Line assignment**, **Export** and **Data Inspection** — load only when you open them, via Streamlit 1.61's keyed tabs (`tab.open`): they were 42% of every rerun despite being panels you may never look at, and **cold boot dropped from ~7.7 s to ~3.6 s**. Switching to one of those tabs now costs a rerun instead of being instant — the deliberate trade. A third pass then went after what that left as the biggest single cost — **the cache keys themselves**: `frame_fingerprint` was ~26 calls and 43% of a rerun, re-hashing the same handful of frame *objects* over and over. It now remembers a frame it has already hashed for the rest of the run, so those 26 calls collapse to 7 real hashes. On the bundled demo an idle rerun went **275 ms → 147 ms** and a rail change **304 ms → 171 ms**; the bigger the corpus, the larger the share this was.
- **Author a scanpath: edits stick, and "Target word" is explained** (BUG-19) — in the ✏️ **Author a scanpath** grid some rows refused to take an edit. The editor was feeding its own return value back in as the next run's input, but `st.data_editor` keeps edits as a *delta* against the frame it was handed and the browser re-sends that delta on every rerun — so it was applied twice, and after a row deletion the frame carried a gapped index, which `num_rows="dynamic"` cannot add rows to. From there edits landed on the wrong rows and rows silently vanished. The base frame is now stable and always range-indexed. **Target word** also got the explanation it never had: a caption and per-column help saying it is the word the fixation lands on (1 = the first word of the stimulus), that it drives the per-word reading measures, and that blank X/Y means the word's centre — plus a `max_value` so an out-of-range word can't be typed, and a warning naming any row that still targets no real word instead of quietly dropping it.
- **The compare-mode heatmap now actually draws** (CMP-7) — turning the heatmap on while comparing two scanpaths showed nothing. The per-word values are joined to the word boxes by `word_id` across two frames that disagree on dtype — boxes carry an integer id, fixations a float (it is `NaN` wherever a fixation landed outside every box) — so `"7"` was compared against `"7.0"`, every word scored zero, and not one box was tinted. Both sides now go through the same key. All three layouts draw: **overlay** (the default) splits each word box into left-A / right-B halves on one shared scale, side-by-side and stacked tint their own boxes. The **Fixations** toggle also reaches Compare now instead of being greyed out — two full sets of markers bury the split boxes, and hiding them is the whole point of a comparison heatmap.
- **Changing a rail setting mid-rerun no longer crashes the app** (BUG-18) — typing in one of the slider number boxes (reported on the heatmap colour range) while the previous rerun was still running could take the whole app down with `KeyError: st.session_state has no key "global_heatmap_color_range__num_lo"`. Streamlit runs a widget's `on_change` *before* the script that recreates the widget, and drops the key of any widget that didn't render — so a conditional box (the heatmap range only renders when the trial/metric has data) could be handed a callback pointing at a key that no longer existed. The callback is now a no-op in that case: there is no pending edit to apply, and the canonical setting still holds its last committed value.
- **Rail labels no longer break mid-word** (`styles.py`) — below 1200 px the rail rendered "Anima/te" and "Com/pare": a bolded toggle label puts its text in a `<strong>` whose `overflow-wrap: anywhere` overrode the wrap rule set on the parent `<p>`.
- **Stimulus & questions no longer shows bogus Q&A fields on generic uploads** (UX-32) — the panel's question/answer field detection matched any column whose name loosely resembled a QA hint ("response", "prompt", …) regardless of type, so an unrelated numeric column like `response_time_ms` could render as a fabricated "Response time ms: 120" line; it's now excluded unless boolish.

#### Changed
- **The data-source picker moved into the main view** (UX-25) — it now sits at the left of the **Filter by** row (and at the top of Corpus Analysis), so the page reads *which dataset → how to narrow it → which trial* and the sidebar no longer has to be opened to switch sources. Adding and removing datasets moved behind the ➕ beside it.
- **The visualization rail is grouped instead of flat** (VIZ-31) — the seven layer toggles now sit in named, collapsible sections, each shaped *toggle → ⚙️ style → 🧹 filter* — **👁️ Fixations** and **↗️ Saccades** (open by default), **📄 Stimulus** (text, bounding boxes, stimulus image) and **🔥 Overlays** (heatmap, raw gaze) — followed by **🖥️ Canvas & text** and **📐 Figure & axes**, so the rail opens as six rows instead of ~18. No setting was renamed, removed, or changed in behaviour.
- **Canvas, font and background controls moved to the rail** (VIZ-31) — monitor geometry, typography, text colour and plot background left the sidebar's *Experimental Setup* expander (under 📂 Data) for the Scanpath rail, beside the layers they restyle, and are also reachable from Corpus Analysis under **🎨 Corpus figure style** (its figures are drawn from them); the setup wizard still shows the same panel inline. The Illustration-label override moved from a top-level rail row into **📐 Figure & axes**.
- **Colourblind-safe is now the default palette** (VIZ-32) — the old colour-screen "Default" palette is gone; "Colourblind-safe" is renamed **"Default (colourblind-safe)"** and is what a fresh session (or a link/config with no explicit colour keys) now opens with — three palettes instead of four. Existing links/configs that name explicit colours are unaffected.
- **Title & caption moved into a popover, and the `{field}` vocabulary is documented** (EXP-5, UX-31) — the EXP-5 title/caption editor rendered inline in the rail: two text boxes, two previews and a field list, which came out "very long and narrow" in a ~320px column. It now sits behind a **⚙️ Title & caption** popover, the same `toggle → ⚙️ style` shape every layer uses. Three surfaces speak the same little `{participant_id}` pattern language — the figure title/caption, the Compare **A/B legend labels**, and the bulk-export file-naming pattern — and two of them described it only as "the same fields as the other one", which is no help to someone who has found neither. A shared `controls.render_pattern_input` / `render_pattern_help` now gives all of them the same box, the same live preview, the same validation error, and an **Available fields** list spelling out every placeholder. Each box also prints its own default *inside* the box, greyed — **Label A**/**B** show `{participant_id} · {trial_id}` — so what an empty box gives you no longer needs a hover to find.
- **The three control rows above the plot read as one cluster** (UX-27) — the Narrow-by row's **More**, the trial picker's **◀ ▶ ⇅**, and the chip strip's **Details** / **✏️** are built in three different functions across two modules, each with its own `st.columns` and its own width unit, so they rendered at three heights and two shapes (square icon buttons beside pill-shaped labelled ones). All six triggers now sit in `railbtn_*` containers and take one geometry from `styles.py` — the chip pill, plus a `min-width` that squares up the icon-only ones — and the rest was fixed by looking at the result in a browser: the trailing controls were **ragged by up to 43 px**, and once the right-most three were flushed the *second* control in each row (**◀ ▶**, **Details**) was still adrift — a full column gutter in from its neighbour, at a different offset per row. Each row's trailing controls now share one container that packs right, so **More**, **◀ ▶ ⇅** and **Details ✏️** all end on the same pixel with the same 3 px between neighbours and one height. Purely visual — no behaviour, session key or wire format changed.
- **Trial picker reads "Select Trial"** (UX-33) — was plainly "Trial ID"; now bolded **Select Trial**, an invitation to act rather than a data-field label.
- **About panel's AI-assistance note trimmed to match the docs** (UX-36) — the sidebar's note was a heading plus two full paragraphs; now four short sentences, matching `docs/index.md`'s length and tone.
- **View modes: neutral section icon, and the Playback popover tightened further** (UX-30) — Compare now reads **⚖️ Compare** (Animate keeps 🎬) on its own toggle label, not just the shared section header. In the ⚙️ Playback popover: the reading-time/playback-duration info box moved up under Playback speed, a divider now separates the playback controls from Frame grid, and Frame every (ms) / Max frames render only while quality is **Custom**. A second pass took the section header off Animate's icon — `🎬 View modes` became **🎛️ View modes**, since 🎬 belongs to the Animate toggle and made the whole section read as being about animation — and finished the popover: **Autoplay** moved up beside Playback speed (both are *how it plays*, where the grid is *how it's sampled*), **Frame every / Max frames** sit side by side rather than stacked, and the frame-count line folded into the info box instead of trailing at the foot of the popover.
- **Quick-view labels fall back to emoji-only when the rail is narrow** (UX-29) — below a ~320px rail width the Scanpath/Heatmap/Illustration buttons drop their text and show only the emoji, via a CSS container query, instead of wrapping to 2–3 lines; the three-button row never stacks.
- **Welcome tour: copy, step order and highlighting polish** (UX-34) — simplified step 2's copy; split trial-picking from pool-narrowing into two steps; Animate/Compare now spotlights just that block, not the whole rail; the per-trial-panels step lists Comparisons and both export scopes; Data source moved earlier; Corpus Analysis got its own step; the final step is now a general "the left sidebar" step. A follow-up pass fixed the two steps that still highlighted too much: **Narrow the pool** and **Pick a trial** both pointed at one wrapper around *both* rows, so each lit up the other's subject as well. They now have a container each and run in reading order (narrow, then pick) instead of jumping down the page and back up. A new test pins the whole convention — every spotlight selector must resolve to a real `tour_grp_*` container, and no two steps may share one.
- **CHANGELOG entries: a Slack-pasteable headline, details below** (ENG-34) — `[Unreleased]` entries are now a short headline list per group, with the longer per-item text moved to a `### Details` subsection underneath (this section is the first to use the new shape). Already-released sections are unchanged.
- **Raw data tables scroll instead of paginating** (ENG-36) — the four Data Inspection tables (Stimuli / Word-level / Fixation-level / Raw gaze) and the derived preprocessing tables lost their **Page** number box, the `.iloc` slice behind it and the "rows 1,001 – 2,000 of 4,300,000" caption, in favour of Streamlit 1.61's `st.dataframe(lazy=True)`: the frame stays on the app server and only the rows in view are sent. You can now scroll and sort across the whole corpus instead of a thousand rows at a time, and a rerun no longer re-ships the visible page.
- **Widget values now persist natively instead of by hand** (ENG-36) — every rail / canvas / compare control on a `global_*`, `single_*` or `cmp*` key now declares Streamlit 1.61's `persist_state="session"`. That is the native answer to BUG-15: Streamlit itself keeps the value alive through runs where the widget doesn't render and re-pushes it to the browser when the widget mounts again. The hand-rolled equivalent — re-asserting every stored value from Python on every run (`controls._pin(rewrite=True)`) — is gone, and `_pin` is back to a plain default-if-absent. No setting changed name or behaviour; a new test fails if a widget is added on a persisted key without the kwarg.
- **Open a trial straight from a Corpus Analysis table** (ENG-36) — the Per-reader **Summary tables → Trials** list has an **Open** button on each row that shows that trial's scanpath, instead of you reading the id off the table, switching view and hunting it down in the picker. The same release's `st.metric(icon=…)` gives the Dataset-statistics counts and the Per-reader summary numbers a glyph each, so a row of six numbers is scannable rather than uniform. Two other 1.61 additions were looked at and left alone on purpose: `st.tabs(height=)` (a fixed panel height would clip the twelve-figure grids or pad the three-line forms) and `client.disableDataExport`, which is app-wide and therefore documented as a hosted-deployment setting in `docs/security.md` rather than set in the repo.
- **Runtime moved to Streamlit 1.61.1** (ENG-31) — from 1.58.0, in one step: `requirements.txt` (`~=1.61.1`), `pyproject.toml` (`>=1.61.1`) and the regenerated lock. The only breaking change that reached this repo is in the tests — Streamlit 1.61 resolves a relative `AppTest.from_file` path against the *calling file* instead of the process CWD, so all seven call sites now pass `tests/conftest.py`'s absolute `APP_SCRIPT`. Everything the release notes flagged was checked and needed no change: the `?embed=true` iframe path (`st.iframe` still treats any string containing `<` as srcdoc, never a file path), the VIZ-21/23 disabled-widget gating under 1.61's server-side enforcement, and the 1.60 query-string / widget-state caps. `docs/security.md` records the two new config surfaces (`server.allowedHosts`, `client.allowedOrigins`), both left at their defaults.

#### Removed
- **Five helpers nothing referenced** (ENG-28) — `annotations.starred_keys` / `keys_with_tag` / `annotated_count`, `measures.compute_trial_measures` (an unused convenience wrapper), and `tabs._ordered_trial_ids`, whose docstring described "the under-image Prev/Next buttons" — a UI element that no longer exists. Found by the ENG-28 inventory pass, which also established that this is *all* the dead code in the package: at 100% confidence a dead-code scan reports only `@st.cache_data` fingerprint parameters (unused by design — they are the cache key), and no dependency is genuinely unused.

## [0.27.2] - 2026-08-05

### Added
- **The on-device recovery cache is visible and controllable** (ENG-30) — the sidebar's new **🗄️ Recovery cache** panel names the folder, reports what is stored (datasets, rows, annotations, size, last written), pauses saving, and forgets the stored session; a one-shot toast says when a session was restored. Also `scanpath-studio cache [--json|--path|--clear]`, `scanpath-studio --no-persist`, and `sps.cache_status()` / `sps.clear_cache()`.

### Changed
- **Privacy, FAQ, CLI and security docs describe the recovery cache** (ENG-26/30) — the security audit's "no on-disk residue of loaded data" now says explicitly that it holds for hosted deployments only, and privacy.md documents the cache's contents, folder, and how to inspect or delete it.

## [0.27.1] - 2026-08-04

### Added
- **Scope the fixation-index window** (`controls._render_fix_range_slider`) — an **Apply to all trials** checkbox beside the range slider. Off by default: the window now belongs to the trial it was drawn on, so switching trials shows the whole new trial; check it to keep the window across trials (clamped to each one's length).

### Fixed
- **The tracker always reloads its catalogue** (`tracker/server.py`) — `data.js` was served with no `Cache-Control`, so browsers applied heuristic freshness and could show a stale item list; newly added items simply didn't appear. It now goes out `no-store`, like `state.json`.
- **Widgets no longer fight their restored value** (`app._preprocessing_settings`, `app.render_sidebar_canvas_controls`, `tabs.render_single_trial_tab`) — the five PRE-1 preprocessing controls, the custom background colour, the OneStop **Parts** picker and the **Animate** toggle each passed an explicit default beside a key that a deep link / saved config writes pre-widget, logging Streamlit's "default value but also had its value set via the Session State API" warning on every run. They now seed the default into session state instead, so a restored value wins.

## [0.27.0] - 2026-08-04

### Added
- **Optional, auditable preprocessing pipeline** (PRE-1/4/6/11–19) — soft exclusion, blink handling, run/pass/sentence/saccade/character tables, RTL-aware landing positions, cleaning QA, and consensus line assignment, exposed across app, API, CLI, and export.
- **Duration-mass heatmaps and line-assignment review tools** (PRE-8/10) — a Gaussian duration-mass heatmap style, plus larger comparison panels with moved-fixation overlays and correction-sensitivity tables.
- **Full analysis-family export** (EXP-3 / AN-30) — saccade, sentence, and trial/reader summary tables now export alongside cleaning QA and run config; also readable in Corpus Analysis and Data Inspection.
- **Authorable, auto-disclosed illustrations** (VIZ-20/22) — build a scanpath from text + fixation events; geometry-changing or synthetic figures are now auto-labelled as illustrations.
- **Per-trial local stimulus-image patterns** (VIZ-14) — resolve per-row images (e.g. `{text_id}.png`) under a safe local root, from the UI, CLI, or API.
- **Two-reader comparison heatmaps and corpus styling** (CMP-7 / AN-29) — split/stacked word heatmaps on a shared scale, plus corpus palette controls reaching the CLI and API.
- **Wide-table performance warning** (PERF-2) — the setup wizard warns before a wide/large selection would slow normalization and hashing.
- **Redesigned scanpath icon** (VIZ-29) — legible down to 16 px; all desktop and docs formats regenerated from code.
- **Claude Code skills** (`.claude/skills/`) — `/release`, `/track`, `/new-feature`, `/preflight`, and `/paper-figs` package the release checklist, tracker conventions, every-surface scaffold, pre-commit gate, and manuscript-figure pipeline as repo-shipped skills.
- **Claude Code hooks, guardrails and review subagents** (`.claude/`) — every edited `.py` file is auto-run through ruff (PostToolUse hook); edits to `uv.lock` / `site/` / `*.egg-info` are denied; `surface-parity-reviewer` + `perf-reviewer` subagents check a diff against the four-surface rule and the caching conventions; shared permission allowlist for ruff/pytest/uv.
- **Agent-docs refresh** — AGENTS.md (9 missing modules added to the tree, 5 stale symbol references fixed, canonical columns updated to `text_id`), `scanpath_studio/CLAUDE.md` (bullets for `aggregation`/`similarity`/`model_scanpaths`/`debug_log`, pre-redesign leftovers fixed), `docs/agents.md` (CLI drift-correction + corpus flags, `raw_gaze=`, similarity/aggregation pointers), `tests/README.md` rewritten for the 53-file suite, CONTRIBUTING (docs-site build, tracker pointer, real demo-asset scripts, desktop workflow on release).
- **Order the compare-trial candidates** (CMP-6) — an **Order by** picker on the compare-B selector: same-text-first (default), most similar / most different to the selected trial (NLD), most fixations, or longest reading.

### Changed
- **Documentation follows four research workflows** (UX-23) — the site now separates four compact use-case tutorials from four feature guides, with leaner Getting started, automation, API/CLI, FAQ, and privacy pages and forwarding pages in place of repeated legacy tutorials.
- **The Comparisons subtab says what it's showing** (CMP-5) — the reference scanpath is named in the heading, every panel names its trial (or flags how many readings its group lumps together), and the grouping, ranking and truncation rules are stated in the tab.
- **The demo's raw gaze is labelled as synthetic** (DATA-15) — under the Raw-gaze toggle, atop the Data Inspection raw-gaze table, and in the getting-started docs: it is synthesized from the fixation report, not recorded eye-tracker output.

### Fixed
- **Fixation filter and Stimulus image popovers now hide with their layer toggle** (`scanpath_studio/controls.py`) — previously visible even when the layer was off.
- **Review hardening for the new preprocessing/authoring surfaces** — soft-excluded rows no longer leak into summaries/runs/saccades; saccade-gap timing, column survival through normalization, import precedence, sensitivity scoping, and authored-event persistence now match their intended contracts.
- **macOS desktop downloads are ad-hoc signed and self-checked** (ENG-19) — release CI verifies bundle integrity, and the install guide documents the quarantine-removal fallback for unnotarized builds.
- **Bulk-exported figures now honour drift correction** (EXP-4 / VIZ-24) — **Export → Multiple trials** silently exported uncorrected figures even when the on-screen plot was drift-corrected. Each trial is now corrected with the active algorithm (connectors included), `plot_config.json` records it, and the exported tables deliberately stay uncorrected.

## [0.26.0] - 2026-08-02

### Added
- **Manuscript scripts ship with the software** (`paper/`) — every figure and number in the Scanpath Studio paper is produced by a script in the repo, so an archived release reproduces them on its own. Output goes to `paper/figures/`, or to `$PAPER_FIGURES_DIR`.
- **Export path patterns** (EXP-1) — name files and folders in the export zip from the trial's own fields, with a live preview.
- **Titles and captions on exported figures** (EXP-2) — auto-generated from the trial or hand-written; the figure grows to make room rather than shrinking the plot.
- **Sort the trial picker** (UX-10) — order the pool by a computed stat or any trial-level column, either direction. Each option shows its value for the active key, and the picker label names the ordering.
- **Selectable colour palettes** (VIZ-18) — colourblind-safe (Okabe–Ito), print/greyscale, and high-contrast presets over the existing colour pickers; the selector reads **Custom** once you edit one of them.
- **Fixation marker shape** (VIZ-15) — nine shapes incl. heart; a channel that survives black & white.
- **Forward vs. regression saccade colouring** (VIZ-19) — a two-way split beside the five-class breakdown.
- **Numeric entry beside every slider** (UX-9) — type an exact value instead of dragging.
- **"Don't show this again" on the welcome tour** (UX-12) — per-browser cookie; **🎓 Show tutorial** brings it back.
- **Documentation link in the app** (UX-17) — from the sidebar Help group and the About popover.
- **AI-assistance disclosure** (UX-20) — in About, the README and the docs: what was checked, cross-check before publishing, and how to file a reproducible report.
- **Animation frame grid is now yours to set** (VIZ-11) — **Frame every (ms)** and **Max frames** in the Animate ⚙ popover, with a readout of the frames they produce and whether the cap coarsened your step. All four surfaces.
- **Six new documentation pages** — bring your own data (DATA-11), privacy (DATA-12), a code-cited security audit (DATA-13), contributing a dataset (DATA-14), corpus analysis (ENG-13), and a headless-usage guide for coding agents (ENG-18).
- **Tutorials on the docs site** (UX-14) — six task-shaped walkthroughs (load your own data, compare two readers, produce a figure for a paper, run it headless, correct vertical drift, export a batch), placed ahead of the reference pages. Every snippet and CLI command in them was executed against the bundled demo before publication; the two newest tab their **In the app / Python / CLI** variants.
- **FAQ** (UX-15) — a **❓ FAQ** dialog in the sidebar Help group answering the recurring questions, plus the full version at `docs/faq.md`.
- **The animated replay honours the rest of the rail** (VIZ-23) — word-label colour, text highlighting, hover measure, saccade direction arrows (each revealing with its own saccade) and the short/long/out-of-bounds fixation flags.
- **Comparison figures honour marker shape, text highlighting and the stimulus image** (VIZ-23) — shape is the channel that survives greyscale print, and these are the figures that reach papers. The image works on the overlay and both split layouts.
- **Drift correction from the command line** (ENG-22) — `render --drift-correction ALGORITHM [--drift-connectors]`, validated against the ten algorithm names.
- **Drift correction rides share links and saved configs** (ENG-23) — `?align_algorithm=Warp&align_connectors=1` (any casing) and `coloring.drift_correction` in the 💾 Save & restore JSON, so a corrected view can finally be linked to and restored. Completes the four-surface contract for PRE-3.
- **Share links can leave the participant out** (DATA-16 / S3) — a **What the link includes** picker: *Participant + trial* (default), *Trial only* (still lands on the exact trial), or *Settings only*.
- **A wire-format contract for the session keys that carry one** (ENG-6) — `session_keys.py` names the share-link and saved-config keys, and a test pins them against a frozen list so a rename fails CI instead of someone's old link.

### Changed
- **Trial chip strip wraps instead of clipping** (UX-11) — no truncation, so the duplicate **More** list is gone; summary stats moved to a **Details** popover.
- **The layout holds down to ~1024 px** (UX-19) — real width breakpoints, where there were none. The scanpath still only ever scales down, uniformly.
- **Empty states say what happened** (UX-7) — one panel naming the filter that emptied the pool (with a **Clear** beside each culprit) or the missing corpus and its download, instead of a blank chart.
- **Fixations default to one colour** (VIZ-17) — size already encodes duration; **Color fixations by** now opts *in* to a second variable. All four surfaces.
- **Corpus Analysis is easier to find** (UX-18) — the header toggle is a primary button with a directional cue.
- **About popover** (UX-16) — BibTeX moved into a collapsed **📖 How to cite** expander.
- **"Snap fixations above words"** (UX-13) moved out of Drift correction into its own *Linear-reading schematic* block.
- **Rail controls the active mode ignores now say so** (VIZ-21) — greyed with a stated reason instead of silently doing nothing; **Animate** previously gated nothing at all. Disabling never rewrites the stored value, so deep links and Save & restore survive a mode toggle. The full setting → render-path map lives in `scanpath_studio/CLAUDE.md`.
- **Drift correction applies while animating and comparing** (VIZ-23) — it was computed on the static figure only, so the two Drift-correction controls were inert in the other two modes. Both scanpaths are corrected in Compare. Connectors stay static-only; no other builder has that layer.
- **The animation's and comparison figure's colour bars are styled like the static one** (VIZ-23) — orientation, tick angle and tick font now apply; a horizontal bar takes reserved margin instead of overlapping the transport controls.
- **A `.zip` upload is bounded before decompression** (DATA-16 / S6) — rejected past a per-member, total, or compression-ratio limit, instead of being read with no ceiling.

### Internal
- **Test coverage** — every `aggregation.py` helper plus a structural smoke test per Corpus Analysis figure (ENG-1), the OneStop per-pid shard fast-path incl. its refusal-to-fall-back (ENG-2), MultiplEYE side-data enrichment (ENG-3), and widget-driven `AppTest` flows for column mapping, trial filters and bulk export (ENG-4).

### Fixed
- **Rail controls showed a stale value when their popover first rendered late** (BUG-15) — with the saccade layer off at load (a deep link or a restored config), turning it on showed **no** line style or line shape selected and a black colour picker, while the figure drew the real settings. Streamlit only pushes a stored value to the browser on the run it was written, so a widget appearing later missed it; the settings are now re-asserted each run.
- **Export crashed on a missing image path** (BUG-14) — `strip_local_paths` raised `AttributeError: 'float' object has no attribute 'replace'` when a path column held a NaN, because pandas 3's `astype(str)` no longer stringifies missing values.
- **Word-box boundaries now fall mid-space** (BUG-11) — EyeLink boxes carry the inter-word space as trailing padding, so every boundary sat a half-space right and a fixation *before* a word went to the previous one. One `measures.word_box_bounds` accessor now feeds all nine consumers — assignment, out-of-text, drawn boxes, the word heatmap, critical spans, landing position, snap-to-word, drift correction, model scanpaths. Glyph-tight corpora (PoTeC / MultiplEYE) are untouched.
- **Regression flags were True for every word** (BUG-7) — EyeLink writes flags as `'0'`/`'1'`/`'.'` strings and the bool cast took every non-empty string as true. On the demo, `regression_in_flag` went from 3,922 True to 815.
- **Arc saccades no longer clip the top line** (BUG-13) — the reserved headroom used the curve's midpoint rather than its true peak, so a wide, sloped arc could arch out of frame.
- **Arc saccades: arrowheads sit on the arc** (BUG-9) — with `saccade_render_mode="Arc"` they were placed at the straight chord's midpoint, floating off the drawn arch.
- **Annotation filters reach the raw-gaze table** (BUG-12) — an unstarred trial's gaze samples survived ⭐ *Favorites only*, which also kept the UX-7 "filters removed everything" panel from ever appearing.
- **Fixation `word_id` numbered from 1 is detected and shifted** (BUG-8) — against 0-based word boxes (the bundled demo's shape) every fixation pointed at the *next* word, so measures computed from raw fixations attached one word to the right. Masked in normal use only because pre-computed IA measures take precedence.
- The sidebar collapse control (UX-8) is always visible and has a real hit area.
- Tutorial card spacing — the ✕ and the Back / Next footer no longer crowd the progress bar.
- The header nav button lines up with the control rail below it.
- **Security** (DATA-16, from the `docs/security.md` audit) — the desktop bundle binds loopback instead of every network interface (S1); the corpus **Data directory** box, folder picker and ⬇ Download are gated behind `SCANPATH_LOCAL_FS` and confined by `SCANPATH_DATA_ROOT`, so a shared deployment is no longer a path oracle and an arbitrary-directory write (S2); exported tables no longer carry an absolute local path, which leaked the OS username into any fixations CSV attached to a paper (S4). Cache keys now hash the whole frame up to 200k rows and respect row order, so editing a value mid-table and reloading no longer serves the pre-edit results (S5). Stimulus text and column names are HTML-escaped before reaching `unsafe_allow_html`, so a crafted corpus can't inject markup (S7); the debug-log handler is installed once per *process* instead of once per session, which was leaking every session's records into every other session's log view (S10); and an unreachable Data Inspection download helper was deleted rather than left to be wired up later (S11). **Every finding from the audit is now either fixed or accepted with a recorded reason.**
- **README weight** (ENG-16) — the dual-reader demo is a still, not a second GIF; the animation moved to the docs site. Both are now rendered from the real pipeline against the bundled demo (`assets/render_dual_scanpath.py`) instead of being hand-made, and palette-quantized (still 197 KB, GIF 1.36 MB).
- The narrow-screen horizontal-scroll fallback for the scanpath figure matched an iframe title Streamlit no longer uses, so a figure that couldn't scale down far enough was clipped instead of scrolling.

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
