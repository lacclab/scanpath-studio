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
Inspect, compare, analyze, and export eye-tracking-while-reading scanpaths.
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
       aria-label="Using Scanpath Studio: stepping through trials, a heatmap, a replay, a two-participant comparison and Corpus Analysis">
  <source src="assets/app_demo.mp4" type="video/mp4">
</video>

## With Scanpath Studio you can

<div class="grid cards" markdown>

- :material-clipboard-pulse:{ .lg .middle } **[Run better data collection](tutorials/data-collection.md)**

    Pilot your eye tracker, software, and stimulus layout (font, spacing)
    before you commit — for example, [compare two eye trackers on the same
    text](tutorials/data-collection.md#compare-two-eye-trackers). Catch
    calibration and setup problems that only show up in a plot, and train new
    experimenters to spot issues such as frequent blinking, or check their
    sessions as you supervise.

- :material-check-decagram:{ .lg .middle } **[Validate your data](tutorials/data-collection.md#4-record-the-decision)**

    Mark trials or whole sessions for exclusion, and decide whether you need
    to collect more. Check that fixation detection and line assignment hold up
    on this dataset by viewing fixations against the raw gaze and word boxes.

- :material-filter:{ .lg .middle } **[Filter data for analysis or publication](tutorials/data-filtering.md)**

    Exclude or flag poorly calibrated, skimming, or non-reading trials, and
    trials with out-of-bounds, very short, or very long fixations. Find the
    trials a specific analysis needs — for example, participants with a given
    native language and good calibration — and export the marked trial IDs.

- :material-file-export:{ .lg .middle } **[Export figures](tutorials/exporting-figures.md)**

    Show a real scanpath in a paper or talk as a heatmap or a replay, and
    save the look as a design to reuse. Or bulk-export every trial
    consistently, for example as training data for models that generate
    scanpaths on images.

- :material-chart-box:{ .lg .middle } **[Compare and analyze](tutorials/corpus-analysis.md)**

    Compare model-generated scanpaths with human ones, contrast groups and
    conditions, and see how reading progresses over time.

</div>

## What the app includes

- **Scanpath visualization:** true-position text, fixations, saccades, raw gaze,
  heatmaps, replay, and comparison — including two trials from different
  datasets.
- **Flexible loading:** your own word, fixation, and raw-gaze tables.
- **Corpus analysis:** per-text, per-participant, and group summaries
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
