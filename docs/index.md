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
Inspect, compare, analyse, and export eye-tracking-while-reading scanpaths.
</p>

<div class="sps-buttons" markdown>
[:material-play-circle: Try the demo](https://scanpath-studio.streamlit.app){ .md-button .md-button--primary }
[:material-rocket-launch: Get started](getting-started.md){ .md-button }
[:material-school: Tutorials](tutorials/index.md){ .md-button }
</div>

</div>
</div>

<video class="sps-shot" controls muted loop playsinline preload="metadata"
       poster="assets/app_demo_poster.webp" data-autoplay
       aria-label="Using Scanpath Studio: stepping through trials, a heatmap, a replay, a two-reader comparison and Corpus Analysis">
  <source src="assets/app_demo.mp4" type="video/mp4">
</video>

## Start with your task

<div class="grid cards" markdown>

- :material-clipboard-pulse:{ .lg .middle } **[Check data collection](tutorials/data-collection.md)**

    Review a pilot or session for calibration, setup, and recording problems.

- :material-filter:{ .lg .middle } **[Filter data](tutorials/data-filtering.md)**

    Find unsuitable trials, annotate decisions, and keep the analysis pool.

- :material-file-export:{ .lg .middle } **[Export figures](tutorials/exporting-figures.md)**

    Produce one publication figure or export a consistent batch.

- :material-chart-box:{ .lg .middle } **[Analyse a corpus](tutorials/corpus-analysis.md)**

    Compare texts, readers, conditions, or groups and download the result.

</div>

## What the app includes

- **Scanpath visualization:** true-position text, fixations, saccades, raw gaze,
  heatmaps, replay, and comparison — including two trials from different
  datasets.
- **Flexible loading:** your own word, fixation, and raw-gaze tables.
- **Corpus analysis:** per-text, per-sentence, per-reader, and group summaries
  of the reading measures in your data.
- **Reproducible output:** static and animated figures, bulk exports, share
  links, and restorable configurations.

See the [Gallery](gallery.md) for what it draws, the
[feature guides](guides/index.md) for the controls, or
[Automation](automation.md) for Python and the CLI.

!!! note "AI-assisted software"
    Scanpath Studio was built with AI assistance. Cross-check results before
    publishing. If something looks wrong — or if you have a feature request or
    suggestion — [report it](https://github.com/lacclab/scanpath-studio/issues).

## Citing

If you use Scanpath Studio in your research, please [cite it](cite.md).
