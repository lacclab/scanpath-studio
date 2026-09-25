# Corpus workspace

The corpus tools share the active data source and trial filters with the Scanpath view.

## Inspect before analysing

Open the 🗂️ **Data** page to check the headline counts and raw tables (the column mapping is under ✏️ **Edit dataset**). Confirm that IDs mean what you intend, that word boxes and fixations share one coordinate system, and that the fields you need survived loading.

## Reading measures

The app exposes common per-word measures including first fixation duration, first-pass gaze duration, regression-path duration, total fixation duration, fixation count, skipping, and regressions. It uses recognized precomputed values when available; otherwise it derives them from fixation-to-word assignment. Every one of them — its formula, units, grouping keys, and what happens when a value is missing — is listed in [Computations & methodology](https://lacclab.github.io/scanpath-studio/computations/index.md).

## Choose the analysis view

Select **📊 Corpus Analysis** in the navigation.

| View             | Unit of interest            | Typical use                                                                                 |
| ---------------- | --------------------------- | ------------------------------------------------------------------------------------------- |
| **Per text**     | one stimulus across readers | per-reader and cohort word profiles, word × reader heatmap, word difficulty on the stimulus |
| **Per sentence** | one sentence across readers | one measure combined for each text/sentence pair                                            |
| **Per reader**   | one reader across trials    | reader summary and within-reader pattern                                                    |
| **Groups**       | one cohort or two cohorts   | condition/population summaries, differences, effect sizes                                   |

The measure, aggregation, and spread controls apply to the current result. A minimum-readers threshold prevents sparse word estimates from looking complete.

**Groups** defines a cohort either by splitting one field or from an independent filter set. With a [participant metadata](https://lacclab.github.io/scanpath-studio/data-format/#participant-metadata) table attached, its fields are offered alongside the trial conditions, marked 👤 — a reader attribute answers a different question from a trial condition, so the picker says which is which. A field with more than 60 distinct values is not offered: that is a range question, and the trial filters have the slider for it.

## Move between summary and evidence

Each result has a **⬇ Download this table (CSV)** button. When a point or group looks unusual, return to the Scanpath view and inspect the trials behind it.

For the compact end-to-end workflow, see the [Corpus analysis tutorial](https://lacclab.github.io/scanpath-studio/tutorials/corpus-analysis/index.md).
