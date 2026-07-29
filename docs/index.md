---
hide:
  - navigation
  - toc
---

<div class="sps-hero" markdown>
<img class="sps-hero-logo" src="assets/icon.png" alt="Scanpath Studio icon" />
<div class="sps-hero-text" markdown>

# Scanpath Studio

<p class="sps-tagline">
See eye-tracking-while-reading data the way the reader saw it — words at their
true on-screen positions, with fixations, saccades, heatmaps, and animated
replay layered on top. Publication-ready figures included.
</p>

<div class="sps-buttons" markdown>
[:material-play-circle: Try the live demo](https://scanpath-studio.streamlit.app){ .md-button .md-button--primary }
[:material-rocket-launch: Get started](getting-started.md){ .md-button }
[:material-school: Tutorials](tutorials/index.md){ .md-button }
[:material-download: Desktop app](desktop.md){ .md-button }
</div>

</div>
</div>

![The Scanpath Studio app: a scanpath drawn true-to-scale over the stimulus text, with the layer controls on the right](assets/app_screenshot.png){ .sps-shot }

## What it does

<div class="grid cards" markdown>

- :material-eye:{ .lg .middle } **True-to-scale scanpaths**

    ---

    The stimulus text is re-rendered at its exact on-screen geometry, so
    fixations, saccades, and word boxes line up with what the reader actually
    saw — or overlay the original stimulus image. See
    [how the rendering works](rendering.md).

- :material-counter:{ .lg .middle } **Canonical reading measures**

    ---

    FFD, gaze duration, go-past, total fixation duration, skips, and
    regressions per word — precomputed EyeLink IA values are used when present,
    computed natively when not.

- :material-chart-bar:{ .lg .middle } **Corpus analysis**

    ---

    Question-oriented views: profile a **text** across readers, a **reader**
    across trials, or one or two **groups** — with shared measure pickers,
    spread bands, effect sizes, and per-view CSV downloads.

- :material-format-align-middle:{ .lg .middle } **Vertical drift correction**

    ---

    The ten Carr et al. (2021) line-assignment algorithms, applied in place or
    compared side-by-side in a grid, ported natively (no GPL dependency).

- :material-database-import:{ .lg .middle } **Any dataset**

    ---

    Auto-detects EyeLink / Gazepoint / snake-case columns, with a guided
    upload wizard and manual mapping override. OneStop, PoTeC, and MultiplEYE
    load out of the box. See the [data format](data-format.md).

- :material-export:{ .lg .middle } **Everything exports**

    ---

    HTML / PNG / SVG / PDF figures (also as separable layers), GIF / MP4
    replays, tidy CSV/Parquet tables, and shareable deep links. The scanpath
    and replay figures are also scriptable via the [Python API](api.md) and
    [CLI](cli.md).

</div>

## Ways to run it

<div class="grid cards" markdown>

- :material-web:{ .lg .middle } **In the browser**

    ---

    The [hosted demo](https://scanpath-studio.streamlit.app) runs the bundled
    3-participant [OneStop](https://github.com/lacclab/OneStop-Eye-Movements)
    sample — nothing to install.

- :material-language-python:{ .lg .middle } **From PyPI**

    ---

    ```bash
    pip install scanpath-studio
    scanpath-studio
    ```

    Python 3.11–3.14 — see [Getting started](getting-started.md).

- :material-download-box:{ .lg .middle } **As a desktop app**

    ---

    A double-clickable build for Windows / macOS / Linux — no Python needed,
    and private data never leaves your machine.
    [Download & instructions](desktop.md).

</div>

## The app in one paragraph

Two views, toggled from the header: **Scanpath Visualization** (one trial —
the layered plot plus Annotations, Stimulus & questions, Comparisons, Line
assignment, Export, Data Inspection, and Share subtabs) and **Corpus Analysis**
(*Per text* · *Per reader* · *Groups*). Layers — text, fixations, saccades,
word boxes, heatmap, stimulus image — toggle independently; **Animate** replays
the reading, **Compare** overlays a second trial, and the **Comparisons**
subtab ranks same-text scanpaths by similarity. Everything obeys the active
trial filters, and the single-trial scanpath and replay figures are
reproducible headless through the same pipeline.

![Two readers of the same paragraph, animated on a shared real-time clock](assets/demo_dual_scanpath.gif){ .sps-shot }

<p class="sps-caption">Compare mode replaying two readers of the same paragraph
on one shared real-time clock.</p>

!!! info "Built with AI assistance"
    Much of this code was written with AI assistance. Two things you can check:
    the reading measures are pinned to a ground-truth trial with expected values
    per measure (open it with `?source=synthetic`), and EyeLink `IA_*` measures
    already in your export are passed through, not recomputed.

    That is not the same as bug-free. **Cross-check anything you publish against
    your own pipeline.** If something looks wrong,
    [open an issue](https://github.com/lacclab/scanpath-studio/issues) with the
    JSON from **💾 Save & restore** — it reproduces the exact view.

!!! quote "Citing Scanpath Studio"
    If you use Scanpath Studio in your research, please cite it — the citation
    metadata lives in
    [`CITATION.cff`](https://github.com/lacclab/scanpath-studio/blob/main/CITATION.cff)
    (also surfaced in the app's About panel), and the bundled demo data comes
    from [OneStop Eye Movements](https://doi.org/10.1038/s41597-025-06272-2).
