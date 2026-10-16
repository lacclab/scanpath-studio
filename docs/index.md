---
title: "Eye-tracking scanpath visualization for reading research"
description: "Free, open-source software for visualizing eye movements in reading: scanpaths, fixations, saccades, gaze heatmaps and raw gaze over the text, from EyeLink, Tobii and other eye trackers."
hide:
  - navigation
  - toc
---

<div class="sps-home-hero" markdown>
<div class="sps-home-intro" markdown>
<div class="sps-home-brand" markdown>
<img src="assets/icon.png" alt="" width="56" height="56" />

# Scanpath Studio

</div>

<p class="sps-home-headline">See how people read.</p>

A free, open-source tool for visualizing eye movements in reading.
Bring your own data, or start with the bundled demo.

<div class="sps-buttons" markdown>
[:material-play-circle: Try online](https://scanpath-studio.streamlit.app){ .md-button .md-button--primary }
[:material-download: Download](install.md#install){ .md-button }
[:material-school: Tutorials](tutorials/index.md){ .md-button }
</div>

</div>
<div class="sps-home-preview" markdown>

<video class="sps-shot" controls muted loop playsinline preload="metadata"
       poster="assets/app_demo_poster.webp" data-autoplay
       aria-label="Using Scanpath Studio: stepping through trials, a heatmap, a replay, a two-participant comparison and Corpus Analysis">
  <source src="assets/app_demo.mp4" type="video/mp4">
</video>

</div>
</div>

## From recording to publication

<div class="grid cards sps-home-features" markdown>

- :material-database-import:{ .lg .middle } **[Bring your own data](guides/loading-data/index.md)**

    - Load words, fixations and raw gaze
    - Add participant, trial and text metadata

- :material-eye:{ .lg .middle } **[Inspect and replay](guides/scanpath-visualization/index.md)**

    - View scanpaths, word boxes and heatmaps
    - Replay a reading at your chosen speed

- :material-filter:{ .lg .middle } **[Filter and annotate](tutorials/data-filtering/index.md)**

    - Select participants, conditions and trials
    - Star, tag and write notes on trials

- :material-compare-horizontal:{ .lg .middle } **[Compare readings](guides/scanpath-visualization/controls.md#compare)**

    - Overlay trials or place them side by side
    - Compare readers and datasets

- :material-chart-box:{ .lg .middle } **[Analyze a corpus](guides/corpus-workspace/index.md)**

    - Summarize measures by text, reader or group
    - Plot them against word features

- :material-file-export:{ .lg .middle } **[Export and share](guides/exporting/index.md)**

    - Save figures, replays or every trial at once
    - Share a view or get its Python / CLI code

</div>

## See it in action

=== "Add your data"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/add-your-data_poster.webp" data-autoplay
           aria-label="Adding EyeLink fixation and interest-area reports">
      <source src="assets/workflows/add-your-data.mp4" type="video/mp4">
    </video>

=== "Compare readings"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/compare_poster.webp" data-autoplay
           aria-label="Two readers of one text side by side">
      <source src="assets/workflows/compare.mp4" type="video/mp4">
    </video>

=== "Analyze a corpus"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/corpus-analysis_poster.webp" data-autoplay
           aria-label="A reading measure on the text, against surprisal and between groups">
      <source src="assets/workflows/corpus-analysis.mp4" type="video/mp4">
    </video>

More examples in the [plot gallery](gallery.md).

<div class="sps-home-links" markdown>

[Python & CLI](guides/scanpath-visualization/index.md#render-in-code) · [FAQ](faq.md) · [Cite Scanpath Studio](cite.md) · [Feedback](https://github.com/lacclab/scanpath-studio/issues)

</div>

<div class="sps-development-note" markdown>

Scanpath Studio was developed with AI assistance. As with any research
software, cross-check its results before relying on them in published work.
Found a bug, or have a feature request?
[Open an issue](https://github.com/lacclab/scanpath-studio/issues).

</div>
