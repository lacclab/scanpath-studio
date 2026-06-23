# Scanpath Studio

An interactive workbench for visualizing **eye-tracking-while-reading** data.
Drop in a trial and see the scanpath the way the reader saw it — words at their
true on-screen positions, with fixations, saccades, a density heatmap, and
animated replay layered on top, all exportable as publication-ready figures.

It is **dataset-agnostic** (auto-detects EyeLink / Gazepoint / snake-case
columns) and ships with a small [OneStop](https://github.com/lacclab/OneStop-Eye-Movements)
demo, so you can try it with zero setup.

[Try the live demo](https://scanpath-studio.streamlit.app){ .md-button .md-button--primary }
[Get started](getting-started.md){ .md-button }

## What's here

- **[Getting started](getting-started.md)** — install (pip / conda / source),
  launch the app, and make your first figure.
- **[Python API](api.md)** — the headless surface: load → list → measure →
  plot / animate → save.
- **[CLI reference](cli.md)** — `scanpath-studio` (launch) and
  `scanpath-studio render` (headless figures) with every flag.
- **[Data format](data-format.md)** — what tables to bring and how column
  mapping works.
- **[Export & troubleshooting](export-troubleshooting.md)** — HTML vs.
  PNG/SVG/PDF (Kaleido/Chrome), GIF/MP4, and common gotchas.
- **[Architecture](architecture.md)** — a map of the codebase for contributors.

## At a glance

The scanpath plot is built from layers you toggle independently — **text** at
true pixel coordinates, **fixations** (sized by duration, colored by any
column), **saccades**, **areas of interest**, and a word-level **heatmap** —
plus **animated replay**, two-trial **comparison**, and **bulk export**. The app
is organized into three tabs: **Scanpath Visualization**, **Corpus Analysis**, and
**Data Inspection** (bulk export is the **Export** subtab of Scanpath
Visualization). **Corpus Analysis** holds the question-oriented analysis sections —
*Per text* (one text, many readers), *Per reader* (one reader, many trials), *Per
group* (a cohort), and *Group comparison* (two cohorts) — plus the WIP model
*Generations* tab; all share a measure picker, aggregation/spread, within-reader
normalization, and per-view CSV downloads.

Everything the app draws is also available headless through the
[Python API](api.md) and the [CLI](cli.md) — same pipeline, same figure.
