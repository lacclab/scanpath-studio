# DATA-66 phase 2b: your column names on the rest of the screen

**Goal:** every column name that phase 2a did not reach shows under the name the dataset's own files gave it: chips, trial filters, trial sort, the Scanpath subtabs, Corpus Analysis, figure text and captions.

**Spec:** [`plans/data-66-original-column-names.md`](data-66-original-column-names.md) §2. Phase 2a: [`plans/data-66-phase-2a-names-on-screen.md`](data-66-phase-2a-names-on-screen.md).

**Architecture:** one session-aware labeller replaces the curated per-surface dicts: `column_names.active_all(session)`, the open dataset's map over all three tables, then `ColumnNames.label`. Widget values stay canonical, so the wire format is unchanged. Figure text takes a `FigureSettings.column_labels` mapping, which the caller builds, so the builders stay pure. That mapping is not a figure option: it is left out of `*_FIGURE_OPTIONS`, so neither the snippet nor `render` sees it, and the API's headless output keeps today's labels until phase 4.

## Global constraints

- Values on the wire (`global_*`, `filter_*`, `trial_chip_fields`, link params) keep canonical names; only labels change.
- A column the dataset brought shows its own name. That includes columns the curated dicts used to rename ("Reading regime" for `question_preview`), because the user asked for "the original fields everywhere". Curated *value* labels (Hunting / Gathering) stay; they name values, not columns.
- A column Scanpath Studio made reads `<label> (computed)` (`ColumnNames.label`). The trial-sort menu lists computed statistics after the dataset's own columns.
- Compare's B uses B's own map (`SecondaryDataset.column_names`) for its own panel; the shared rail stays A's.

## Tasks

1. **Shared labeller.** `column_names.active_all(session)`; `controls._rail_names` uses it. `metadata.field_label` returns the user's metadata column verbatim.
2. **Chips + ✏️ Edit chips.** `_chip_field_label` / `_chip_option_label` read the map; `CHIP_FIELD_LABELS` goes. Summary chips (statistics) keep their labels.
3. **Trial filters.** Titles come from the map; `_FILTER_FIELD_LABELS` keeps only the value labels.
4. **Trial sort.** Columns are labelled by the map, so the `TRIAL_INDEX` / `trial_index` collision goes away. Computed statistics are listed after the columns.
5. **Scanpath subtabs.** Stimulus & Context fields and the Comparisons match field are labelled by the map (`_STIMULUS_FIELD_LABELS` keeps only span colours).
6. **Corpus Analysis.** The group-field, sentence-measure and per-reader X-axis pickers go through the map (`_GROUP_COL_LABELS` goes).
7. **Figure text.** `FigureSettings.column_labels`: categorical legend, colour-bar titles, hover labels, non-spatial axis titles. Fixes the double unit ("… Ms: N ms") and "Total Fixation Duration Ms".
8. **Captions.** Captions that name a canonical column say the user's name or plain words.
9. **Docs, changelog, reviews, PR.**

## Not in 2b

Exports (phase 3), API/CLI names (phase 4). The measure pickers keep `aggregation.MEASURES`' curated labels, which carry the units the corpus figures need; AN-32 maps them from the dataset's own `IA_*` columns, so the figure says which measure it plots. Whether they should show `IA_DWELL_TIME` instead is a review call.
