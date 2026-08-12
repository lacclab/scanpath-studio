# Corpus workspace

The corpus tools answer questions across trials. They share the active data
source and trial filters with the Scanpath view.

## Inspect before analysing

Open the 🗂️ **Data** page to check headline counts, column mappings, stimulus
rows, fixations, and raw gaze. Use it to confirm:

- participant, text, and trial IDs have the intended meaning;
- word boxes and fixations use the same coordinate system;
- each analysis field survived loading;
- the filtered pool still contains the expected groups.

## Reading measures

The app exposes common per-word measures including first fixation duration,
first-pass gaze duration, regression-path duration, total fixation duration,
fixation count, skipping, and regressions. It uses recognized precomputed
values when available; otherwise it derives them from fixation-to-word
assignment.

## Choose the analysis view

Select **📊 Corpus Analysis →** in the header.

| View | Unit of interest | Typical use |
| --- | --- | --- |
| **Per text** | one stimulus across readers | word profile, distribution, pooled heatmap |
| **Per reader** | one reader across trials | reader summary and within-reader pattern |
| **Groups** | one cohort or two cohorts | condition/population summaries, differences, effect sizes |

The measure, aggregation, and spread controls apply to the current result. A
minimum-readers threshold prevents sparse word estimates from looking complete.

## Move between summary and evidence

Download the table beside a result for downstream analysis. When a point or
group looks unusual, return to the Scanpath view and inspect contributing
trials. Corpus charts summarize the active pool; they do not diagnose recording
quality on their own.

For the compact end-to-end workflow, see the
[Corpus analysis tutorial](../tutorials/corpus-analysis.md).
