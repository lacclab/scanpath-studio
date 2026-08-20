# Open task inventory

Generated from the live tracker model on 2026-08-20: tracker/data.js with tracker/state.json overrides and UI-created tasks applied. This matches the tracker UI counts.

## Summary

| Status | Count |
|---|---:|
| In progress | 2 |
| Review | 8 |
| On hold | 14 |
| Backlog | 15 |
| **Total** | **39** |

## In progress (2)

### UX-83 — A tutorial opens its own page before the tour starts

- Group: **UX & Interaction** · Owner: **Maya**
- Planned / left: Nothing.
- Waiting on user / review: Review: start a Corpus-Analysis-first or Data-first tutorial from the 🧭 chooser and confirm the app lands on that page immediately, with no "Show me" click needed; then Exit and confirm it returns to the page you actually started from.
- Live tracker note: moves to the right page but tutorial itself doesnt start. also i wanted a "dont show again" checkbox inside each tutorial's dialogs

### DATA-29 — Attach a table of trial information, the way participant metadata attaches

- Group: **Datasets & ingestion** · Owner: **Maya**
- Planned / left: **The headless half only** — everything on screen is wired. 1. **Export bundle** — `metadata/trials.*` beside `metadata/participants.*`, with the same per-field opt-out `ExportOptions.metadata_fields` gives the participant table (reader-linked trial attributes are re-identifying in the same way). 2. **CLI** — `render --trial-metadata`, copying `--participant-metadata`. 3. **Headless API** — `api.load_trial_metadata`, copying `api.load_participant_metadata`. The deep link needs nothing: the filter keys are under `filter_`, so they mirror and round-trip with the rest of the filter layer already.
- Waiting on user / review: Review the visible half: attach a trial table on the 🗂️ Data page, filter by one of its columns, and turn a column on as a chip. Two judgement calls to check — the reader picker defaults to *(none)*, i.e. one row describes a text and every reading inherits it; and a filter it can't satisfy narrows to nothing rather than being ignored. The headless half (export bundle, `--trial-metadata`, `api.load_trial_metadata`) is still open — finish it under this item, or split it out so this one can close on the visible feature?
- Live tracker note: 1. this is the right model, the usecase is the same - appear as metadata chips on the scanpath screen and let the user choose which fields he would like to see 2. auto fill. trial field is mandatory, reader isnt

## Review (8)

### UX-81 — Text & fonts moves to Stimulus; the physical-geometry fields leave the rail

- Group: **UX & Interaction** · Owner: **Maya**
- Planned / left: Nothing.
- Waiting on user / review: Open 📄 **Stimulus → Text**: line spacing, the fonts, the text colour and the plot background should all be there. Anything that should have stayed with the figure rather than the stimulus? 📐 **Figure & canvas** now has no physical-geometry fields. A dataset whose Recording setup says nothing still falls back to 597 mm / 800 mm / 96 dpi **silently** — should a figure that reports degrees say the geometry was assumed? You lose the per-figure override those rail copies allowed ("what if the screen were bigger"). Acceptable, or should Recording setup gain an explicit override?

### DATA-33 — Edit dataset reuses the finished add-dataset screen

- Group: **Datasets & ingestion** · Owner: **Maya**
- Planned / left: Nothing.
- Waiting on user / review: Review Edit on a stored dataset: mapping and the three Recording setup columns should look like the completed add flow and save together. Only columns retained during the original normalization can be remapped; re-upload remains necessary to recover a column dropped at import. Review a loaded public corpus in Available datasets: its row should be tinted and its remembered counts should remain integers after switching away.

### UX-94 — Tighten Data, Annotations, Comparisons and Export

- Group: **UX & Interaction** · Owner: **Maya**
- Planned / left: Nothing.
- Waiting on user / review: Review **Refresh & Copy** in Share and confirm it replaces both old actions while copying the current view. Review the 3rem top inset, compact single-outline plot controls with a full-width dropdown target, visible **♻️ Reset it** button, and Scanpath-default / Custom-restore Quick-view behavior at the supplied window sizes. Review Compare with This dataset: B's 🔎 should narrow only B, while A remains selected and unchanged, including when A's own filters exclude the chosen B trial.

### UX-96 — Rebuild Session around recovery, backup and debug tools

- Group: **UX & Interaction** · Owner: **Maya**
- Planned / left: Nothing in implementation. Automated and browser verification were deferred at the user's explicit request.
- Waiting on user / review: Review Session locally and on a hosted deployment: local should show its folder and controls; hosted should explain that no recovery copy is written. Confirm the JSON-backup boundary is clear enough: portable work state, not the uploaded eye-tracking tables themselves.

### DATA-27 — EyeGenBench — load all 39 benchmark corpora as one built-in source

- Group: **Datasets & ingestion** · Owner: **Shubi**
- Planned / left: Nothing. Two corpora remain unprepared for reasons outside this work: `etdd70` dies inside the pipeline's own Zenodo downloader (a bare `assert` in `httpx`'s sync transport, which is why the sweep reported an empty error for it), and seven more need manual acquisition from their publishers.
- Waiting on user / review: **Review the branch** — 31 corpora in the source picker, each marked (WIP). Worth clicking: pick *EMTeC (WIP)* and confirm the stimulus and word boxes draw (it silently loaded zero word boxes until the branch review caught it), and *PoTeC (harmonised benchmark) (WIP)* beside the native *PoTeC* to see the two kept apart. **Is (WIP) the marker you want, and on those entries only?** It is display only — the stored choice, the `?corpus=` slug and saved configs are untouched, so removing it later breaks no link. **Geometry honesty is the judgement call to check.** 1 corpus is `real`, 20 `reconstructed`, 10 `synthesized`, and a corpus stays `synthesized` unless a display parameter can be cited. MECO L2 W2 was *downgraded* on this branch: its shipped 1920x1080 appears in neither cited source, and its font size was a points value used as pixels. **Docs churn inside the ruff commit** (merged from main): 0.16 formats Python inside Markdown, so README and four docs pages were rewrapped and one README one-liner now spans three lines. Cosmetic, and revertible if you dislike it.

### ENG-40 — The tracker server could not read its own files on a Hebrew-locale Windows machine

- Group: **Engineering** · Owner: **Maya**
- Planned / left: Nothing.
- Waiting on user / review: Review: the fix is mechanical (`encoding="utf-8"` on six reads plus a write in `server.py`, seven more in the test file) — worth a look that no call site was missed. Sweep the app's own `read_text` / `write_text` / `open()` calls for the same latent bug as a follow-up item, or leave it until someone trips over one? Annotation JSON, the recovery-cache manifest and saved plot configs are the candidates (see *Background*).

### ENG-41 — The tracker silently threw away edits made outside the page

- Group: **Engineering** · Owner: **Maya**
- Planned / left: Nothing.
- Waiting on user / review: Review: click through a save, then have a second tab (or an agent) touch `tracker/state.json` and save again — the banner should appear and *Reload now* should bring the other edit in. Judgement call worth checking: a conflict now costs you a reload and a re-typed edit, rather than the page merging the two. Merging per-item is possible but it silently picks a winner; blocking is honest. The old `revision` key is still sitting in your `tracker/.local.json` — harmless and unread. Leave it, or should the server prune it on next write?

### ENG-42 — Claiming a task created in the UI made every later save fail

- Group: **Engineering** · Owner: **Maya**
- Planned / left: Nothing.
- Waiting on user / review: Review: claim #UX-87 (or any task you create in the UI) and then save something else — both should now go through. The judgement call: `owner` is optional on a created item rather than required, so pre-#ENG-39 created items still load; the alternative was backfilling them with an empty owner on read. The server's created-item check is an allow-list of keys, which is why an unknown one is a hard 400 rather than being dropped. Keep it strict (a typo'd field fails loudly), or ignore unknown keys so one stale page can never block saving again?

## On hold (14)

### BUG-29 — Zooming out of a rectangle zoom lags and sometimes doesn't take

- Group: **Bugs** · Owner: **Maya**
- Planned / left: No separate remaining-work field is recorded. Current scope: When zooming in on a scanpath by marking a rectangle, zoom out has lag and doesn't always work. Maybe the message about double click for zoom out should be permanent on the screen.
- Waiting on user / review: Permanent on-screen hint, a visible **Reset zoom** button near the plot, or both? A modebar button costs no vertical space on every figure, but it is small and easy to miss.

### UX-56 — Decide whether the add-dataset view goes table-by-table or stage-by-stage

- Group: **UX & Interaction** · Owner: **Maya**
- Planned / left: No separate remaining-work field is recorded. Current scope: Should the add-dataset view show **each dataset and then its field mappings**, or **first all the datasets and then all the mappings**?
- Waiting on user / review: Table-by-table (each dataset then its mappings) or stage-by-stage (all datasets, then all mappings)? If table-by-table: what happens to the cross-table checks that live on the current layout — the trial-count comparison and the "no trial ids are shared" warning — which exist precisely because the two tables are mapped side by side?

### CMP-12 — Rescale an overlay so two different screens share one scale

- Group: **Compare mode** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: The half of **CMP-11** the user dropped on 2026-08-12. CMP-11 allows a cross-dataset overlay only when both corpora used the same screen; a pair recorded on two different monitors still falls back to side-by-side panels. This item is the **Align by** control that would let those overlay too: *Visual angle* (scale each reading by its own px/degree so one degree is one degree on both) and *Text box* (translate + scale so the two texts' bounding boxes coincide — the pragmatic one for a corpus that never recorded its physical setup).

### PERF-1 — Replace Plotly with matplotlib (or lighter renderer) for speed

- Group: **Performance** · Owner: unassigned
- Planned / left: Unpark the branch, finish the renderer migration, and verify the speed improvement without regressing the true-scale spatial path.

### PRE-2 — Fixation cleaning: discard short / long / out-of-bounds + purge

- Group: **Preprocessing — eyekit parity** · Owner: unassigned
- Planned / left: The actual eyekit-parity pipeline version: a real `excluded` soft-flag stage between `data.normalize_fixations` and `measures.enrich_fixations` (depends **PRE-1**, still Backlog), an "N excluded" count surfaced in the UI, and `purge` — a hard-drop + reindex that propagates to reading measures, corpus aggregation, and every export, not just the plot. Today's shipped version never touches measures or exports: a Discarded fixation still counts toward FFD/FPRT/TFD and still appears in the CSV/Parquet/mega-table export.
- Waiting on user / review: Does an excluded fixation stay excluded everywhere by default — reading measures, corpus aggregation, every export — or is that opt-in with the plot-only behaviour as the default? Today's shipped half silently means "plot only", which is the mismatch users would trip on. Should `purge` reindex `fixation_id` / `order_in_trial` after the hard drop (matching eyekit), knowing that breaks ID stability against anything exported before the purge?

### PRE-3 — Vertical drift correction (`snap_to_lines`) + before/after viz

- Group: **Preprocessing — eyekit parity** · Owner: unassigned
- Planned / left: User review and sign-off are paused until this item is revisited. CLI and headless-API exposure also remain if full surface parity is still wanted.

### PRE-5 — Custom interest areas + IA-level reports

- Group: **Preprocessing — eyekit parity** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Today AOIs == precomputed per-word boxes only. Define IAs per text by word range, regex over word text, or eyekit-style `[bracket]{id}` markup (union of member word boxes). Render as distinct highlighted regions in [`plots.py`](scanpath_studio/plots.py). IA-level measures (reuse PRE-4) → `interest_area_report`-style table for Corpus Analysis + export. Persist definitions per `text_id` via the Save & restore JSON.

### ENG-20 — Windows desktop build: the rough edges

- Group: **Engineering** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Two known v1 limits, both documented at release rather than fixed: - **A console window stays open** behind the app for the life of the session. Closing it kills the server. Options: `console=False` in the spec (loses the crash output the launcher prints), or a native window (pywebview) that owns the lifecycle — the ADR deferred this. - **SmartScreen warns on first run** because the build is unsigned — **ENG-21**. Also unverified: only the Linux build was checked by hand, so the same "does it actually run on a clean machine" pass **ENG-19** needs is owed to Windows.

### ENG-21 — Sign and notarize the desktop builds

- Group: **Engineering** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Unsigned bundles make both non-Linux platforms hostile on first run: macOS Gatekeeper blocks (or quarantines) the app, Windows SmartScreen warns. Needs an Apple Developer ID + notarization/stapling in the macOS CI job, and an Authenticode certificate for Windows — i.e. **paid certificates and secrets in the repo**, which is a decision for the user, not just work to schedule. Blocks a comfortable install story for the audience the desktop build exists for (researchers without a toolchain). Feeds **ENG-19** / **ENG-20**.

### ENG-17 — Hosted online mode: login + remote data backend (Snowflake?)

- Group: **Engineering** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: A deployed multi-user mode: authentication (`st.login` / OIDC), per-user datasets that persist between sessions, and optionally a warehouse backend (Snowflake via `st.connection`) instead of local files — so a lab could keep a shared corpus online rather than everyone loading their own copy. The opposite trade-off from **ENG-15** (the desktop bundle keeps everything local), and it would make **DATA-13** (data security) a hard prerequisite. **Parked at the user's request (2026-07-28)** — captured so the idea isn't lost, not scoped.

### PRE-20 — Neural line assignment (DIST / DIST-Ensemble)

- Group: **Preprocessing — eyekit parity** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: GazeGenie's headline differentiator over the classic algorithms is a **trained model** for line assignment: `DIST` (a single network) and `DIST-Ensemble`, plus hybrids that feed the model's prediction into the consensus vote (`Wisdom_of_Crowds_with_DIST[_Ensemble]`). It ships checkpoints in `models/`, uses PyTorch Lightning + timm, and falls back to the classic-only consensus when the model fails or the fixation sequence exceeds the model's max length. **Parked, not rejected.** The cost is the problem, not the idea: torch + lightning + timm + bundled checkpoints against a package that is `pip install scanpath-studio`, runs the demo on Streamlit Cloud, and ships a desktop build (**ENG-19**/**20**). If this is ever wanted, the shape is an **optional extra** (`pip install scanpath-studio[neural]`) that registers itself as one more entry in `alignment.ALGORITHMS` and is simply absent when the extra isn't installed — never a hard dependency. **PRE-17**'s consensus is the cheap 80 % of the benefit and should land first. Related: **PRE-3**, **PRE-17**. *Surveyed 2026-08-02 from [GazeGenie](https://github.com/Gittingthehubbing/GazeGenie) (Streamlit, parsing → cleaning → line assignment → measures for reading eye-tracking; measure definitions adapted from popEye).* **2026-08-07.** The model also ships as its own standalone repo, [DIST-Dual_Input_Stream_Transformer](https://github.com/Gittingthehubbing/DIST-Dual_Input_Stream_Transformer) (same author, same drift-correction task), with a Hugging Face Space demo, a notebook-based correction workflow, a full training pipeline, and a companion OSF dataset — decoupled from the rest of the GazeGenie app. Worth re-checking against that repo directly if this is picked up: it may be a lighter integration path than pulling in the full GazeGenie stack (still torch + lightning + timm, but without GazeGenie's other dependencies), which would change the cost side of the parked decision above.

### DATA-18 — Derive interest areas from a stimulus image (OCR)

- Group: **Datasets & ingestion** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: GazeGenie ships `create_interest_areas_from_image.py`: run Tesseract over the stimulus screenshot, recover per-word **and** per-character bounding boxes, and draw them back over the image so the result can be eyeballed before use. That is the missing on-ramp for a common case — a lab kept the screenshots but never exported an interest-area report — which today the app simply cannot open, since word boxes are the one thing it can't derive. It pairs naturally with **VIZ-14** (per-trial stimulus images from a folder + naming pattern): the same image that becomes the plot background becomes the AOIs. Keep it optional (pytesseract is a *system* dependency, not a wheel — same "absent when not installed" shape as **PRE-20**), always render the derived boxes over the image for inspection, and let the result be corrected/saved rather than trusted blind. Related: **VIZ-14**, **PRE-5**, **DATA-1**. *Surveyed 2026-08-02 from [GazeGenie](https://github.com/Gittingthehubbing/GazeGenie) (Streamlit, parsing → cleaning → line assignment → measures for reading eye-tracking; measure definitions adapted from popEye).*

### VAL-4 — Cross-validate the reading measures against reference implementations

- Group: **Validation** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: GazeGenie is useful to us as an **oracle**, independent of whether we adopt any of its features: it computes word measures three ways over the same trial — its own (`analysis_funcs.py`), popEye's aggregation (`popEye_funcs.py`), and EMReading's (`emreading_funcs.word_measures_EM`) — and can run eyekit's alongside. Take one trial with a known-good line assignment, run it through `measures.compute_per_word_measures` and through the references, and diff the shared measures: FFD, gaze duration (FPRT), go-past (RPD), total (TFD), skip, regression-in, regression-out. Every systematic difference is either a bug or a documented definitional choice — and the manuscript should say which. This also settles the audit **PRE-4** asks for (is our `regression_path_duration` the same thing as `go_past_duration`?) with a number rather than a reading of the code. Related: **PRE-4**, **PRE-11**, **VAL-1**. *Surveyed 2026-08-02 from [GazeGenie](https://github.com/Gittingthehubbing/GazeGenie) (Streamlit, parsing → cleaning → line assignment → measures for reading eye-tracking; measure definitions adapted from popEye).*

### ENG-32 — Migrate the improvements tracker to GitHub Issues when the time comes

- Group: **Engineering** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Should the tracker move to GitHub Issues? Reviewed and **deliberately deferred** — not rejected. Park the decision with the reasoning written down so the next look starts from the analysis rather than redoing it.

## Backlog (15)

### UX-95 — Improve the comparison A/B legend

- Group: **UX & Interaction** · Owner: **Maya**
- Planned / left: Audit the current automatic and custom A/B labels on every comparison layout. Design a concise legend that remains unambiguous in-app and in exported figures. Carry the decision through the app, deep links, saved configs, CLI/API surfaces, tests, documentation, and changelog where the chosen behavior requires it.

### VIZ-37 — Add a fullscreen control to true-scale Plotly scanpath figures

- Group: **Visualization & display** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Add a visible **Fullscreen** button to the Plotly modebar on the main scanpath figure. Entering fullscreen should expand the complete figure to the available screen, preserve its aspect ratio and true-scale geometry, and provide an obvious way to exit, including the Escape key.

### UX-70 — Lay the Corpus Analysis subtabs out label-left too

- Group: **UX & Interaction** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Do #UX-69 for **Corpus Analysis** as well: field names to the left of the fields instead of above them, so the subtabs are more compact.

### BUG-32 — Reusing another dataset's AOI file silently leaves the new dataset with no AOIs

- Group: **Bugs** · Owner: **Maya**
- Planned / left: No separate remaining-work field is recorded. Current scope: I uploaded my dataset with AOIs, and the AOI file was the same as another of my uploaded datasets' — and now I don't see the AOIs, as if I hadn't uploaded them. Why is that? It's for my `eyelink_c55_s42_mg_px` dataset.
- Waiting on user / review: Should the mapping carry over between two *different datasets* at all? Keeping it within one dataset (#DATA-24's case, a table growing mid-wizard) is clearly right; inheriting across a dataset boundary is what bites here. Scoping the signature to the dataset name would fix it without touching #DATA-24's behaviour. Should an empty words frame beside a non-empty fixations frame be a hard error, or a prominent warning that still lets the trial draw fixations-only? A hard error is safer for measures; a warning keeps a fixations-only dataset usable.

### DATA-30 — EyeGenBench — OneStop's real word boxes are skipped on a key-name mismatch

- Group: **Datasets & ingestion** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Noticed while asking why fixations in the newly added corpora sit at a fixed `y` per line (#DATA-31): OneStop's harmonised bundle is stamped `geometry_source: reconstructed`, so its word boxes are a synthesized greedy wrap on the published 2560x1440 screen — even though the **real** EyeLink boxes are sitting in the raw file we already read. Join them, and let the corpus reach the `real` tier it qualifies for.
- Live tracker note: Yes. (background: When eyegenbench will be finalized and included all onestop subset, I will be removing the native onestop at one point.)

### DATA-31 — EyeGenBench — fixation y is one value per line; the real y still exists for some corpora

- Group: **Datasets & ingestion** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Every newly added corpus draws its fixations at a fixed `y` per line, which reads as a drift-free reader rather than as missing data. Recover the real vertical position where the raw files still have it.
- Live tracker note: Chase the real y.

### DATA-15 — Real raw-gaze samples in the bundled demo

- Group: **Datasets & ingestion** · Owner: unassigned
- Planned / left: Ship **real raw-gaze samples** for the bundled demo trials (user, 2026-08-03: *"we have it somewhere"* — the lab holds the raw OneStop EyeLink recordings even though the public release ships none). Steps: locate the lab's raw recordings (likely the original `.edf`/`.asc` sessions behind the lacclab export), extract the gaze samples for the 3 bundled pids × their demo trials, convert to the demo's `raw_gaze` schema (participant_id, trial_id, x, y, timestamp) via `update_sample_data.py`, and confirm the participants consented to sample-level release before bundling. Once real samples replace the synthesized file, remove the DATA-15 captions (controls, Data Inspection, getting-started note) and the `synthesize_raw_gaze` path, and update `tests/test_raw_gaze_sample.py`. Export needed no label either way: bulk export writes fixations/measures tables only.

### PRE-7 — EyeLink `.asc` import

- Group: **Preprocessing — eyekit parity** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: App requires pre-extracted fixations today. Wrap `eyekit.io.import_asc` (EFIX fixations; optional messages/variables) → normalized fixation schema; derive participant/trial from filename (like the MultiplEYE path). New "Dataset format" in the upload wizard; optional raw-sample surfacing; message-based trial segmentation. Word boxes/AOIs still come from a separate stimulus file. Feeds **DATA-1**.

### VAL-2 — Validate OneStop text-spacing v1 (1px difference)

- Group: **Validation** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Verify the 1-pixel text-spacing difference in OneStop spacing version 1 shows up correctly in the layout.

### BUG-4 — MultiplEYE: residual small text-vs-image mismatch

- Group: **Bugs** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Follow-up to **BUG-3** (signed off 2026-07-03, archived). After the BUG-3 fixes (real `FONT_SIZE`/`FONT` threaded through, line-pitch-based `scale_text_to_boxes`, script-aware width cap) the MultiplEYE true-to-scale word text lines up *much* better, but a **small** residual offset between the rendered text layer and the stimulus image remains — the labels are close but not pixel-exact on top of the image words. Likely the leftover slack noted in BUG-3's root cause (2): the nominal-vs-inked glyph size + anchor difference between how PIL drew the image glyphs (top-left in a glyph-tight cell) and how Plotly centers/rasterizes the label in the box, and/or remaining font-metric differences between the CJK fallback font and the exact stimulus font. Quantify the residual (by how much, and whether it's a constant shift vs. per-line/per-word drift) before fixing. Code anchors: `_word_label_font_px` / `scale_text_to_boxes` / `_line_pitch` ([`plots.py`](scanpath_studio/plots.py:339)), MultiplEYE font stamping (`datasets._multipleye_font_config` / `_multipleye_font_css`), and the font snap in `app.render_sidebar_canvas_controls`. Related: **BUG-3**, **VIZ-4**, **PRE-6**.

### ENG-43 — Move to Streamlit 1.62 and adopt the relevant layout fixes

- Group: **Engineering** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Upgrade the locked Streamlit runtime from **1.61.1** to **1.62.x**, then adopt the parts of 1.62 that materially improve Scanpath Studio rather than treating this as a version-only bump. The direct wins to assess are full popover contents in narrow / embedded viewports, native wrapping controls for dense layouts, and safer sampled hashing in `st.cache_data`.

### VAL-8 — Read every computation in the register and confirm the science

- Group: **Validation** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: *"Add a followup task for me to manually review all computations."* — the manual read-through that #VAL-5's register was built to make possible, split out so #VAL-5 can close on the artefact while the reading proceeds at your pace.
- Waiting on user / review: **Start with `pre.merge_short` and `pre.character_grid`.** Both moved onto the shared letter scale under #BUG-27 on 2026-08-13, so both changed *meaning* rather than just wording. The merge distance is the one with real consequences: it is a preprocessing setting that travels in share links and export bundles, so a wrong scale there silently changes other people's results, not just a number on a page. **Then the four reading measures** — `measure.first_fixation`, `measure.first_pass`, `measure.regression_path`, `measure.total_fixation`. They are what a reader of a paper would assume standard, so a definition that quietly differs from the field's is the most expensive kind of error here. **Say which entries you have cleared** as you go, so the status column can move from *Partially verified* to *Verified* for those. There is no point in me guessing which ones you actually read.

### VAL-6 — Validate the complete OneStop upload-to-scanpath-to-export pipeline

- Group: **Validation** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Prove that a researcher can complete the real OneStop workflow from end to end: start with a fresh session, upload the supported full OneStop files, verify the parsed data, inspect representative scanpaths, and finish a corpus-wide figures-only export. Execute the workflow by following the user tutorials verbatim once those tutorials are added; a step that cannot be followed is a product or documentation gap, not something the validator should silently work around.

### DATA-25 — Auto-detect prefixed column names (AOI_LEFT → LEFT)

- Group: **Datasets & ingestion** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: Make the automatic column mapping catch vendor-prefixed spellings of a name it already knows: a table whose word boxes are `AOI_LEFT` / `AOI_RIGHT` / `AOI_TOP` / `AOI_BOTTOM` should map itself the way `IA_LEFT` / `left` already do, instead of landing the user in the manual column-mapping step. Same for the other families — an `AOI_LABEL` text column, an `AOI_ID`, and whatever the equivalent prefix is on the fixation side.
- Waiting on user / review: Prefix-vocabulary pass (`ia`/`aoi`/`roi`/`currentfix` only) or a general token-suffix match on any prefix? The first is safe but needs a new prefix added per corpus; the second auto-detects more and risks a silent mis-map. When the prefixed pass fires, flag it to the user (a caption in the mapping UI naming the guessed column) or map silently the way exact matches do?

### UX-87 — 🧹 Clear cached computations button is pretty useless - delete it?

- Group: **UX & Interaction** · Owner: unassigned
- Planned / left: No separate remaining-work field is recorded. Current scope: 🧹 Clear cached computations button is pretty useless - delete it?
- Live tracker note: I think claude created this card when i told him to delete the calculations when a dataset is deleted. is there a button that deletes all uploaded datasets? if so that this should be the button that clears calculations. no point in a button that does only that.
