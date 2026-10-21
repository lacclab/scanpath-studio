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

A free, open-source app for exploring eye movements in reading.
Bring your own data, or start with the bundled demo.

<div class="sps-buttons" markdown>
[:material-play-circle: Try online](https://scanpath-studio.streamlit.app){ .md-button .md-button--primary }
[:material-download: Download](install.md#install){ .md-button }
[:material-school: Tutorials](tutorials/index.md){ .md-button }
[:material-format-quote-open: Cite](about.md#cite-scanpath-studio){ .md-button }
</div>

</div>
<div class="sps-home-preview" markdown>

<video class="sps-shot" controls muted loop playsinline preload="metadata"
       poster="assets/app_demo_poster.webp" data-autoplay
       aria-label="Using Scanpath Studio: a replay, the Heatmap preset, a figure built layer by layer, saccade filters, redacted text, two participants side by side, Export and Share">
  <source src="assets/app_demo.mp4" type="video/mp4">
</video>

</div>
</div>

## From recording to publication

<div class="sps-home-workflows" markdown>

=== "Bring your data"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/add-your-data_poster.webp" data-autoplay
           aria-label="Import your own recordings">
      <source src="assets/workflows/add-your-data.mp4" type="video/mp4">
    </video>

    **Import your own recordings.** Load your Fixations, Words or Raw gaze tables, and add participant, trial and text metadata.

    [Add your data :material-arrow-right:](guides/loading-data/index.md#add-your-own-data){ .md-button }

=== "Inspect & replay"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/home-replay_poster.webp" data-autoplay
           aria-label="Follow a reading">
      <source src="assets/workflows/home-replay.mp4" type="video/mp4">
    </video>

    **Follow a reading.** Inspect fixations, saccades and heatmaps. Replay the reading, fixation by fixation.

    [Review a session :material-arrow-right:](tutorials/data-collection/check-a-session.md){ .md-button }

=== "Customize"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/home-customize_poster.webp" data-autoplay
           aria-label="Design presets, palettes and plot controls">
      <source src="assets/workflows/home-customize.mp4" type="video/mp4">
    </video>

    **Make the view your own.** Start from a design preset, pick a palette, then adjust each layer in Plot controls, in Full mode.

    [Explore plot controls :material-arrow-right:](guides/scanpath-visualization/controls.md){ .md-button }

=== "Filter & annotate"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/home-filter-annotate_poster.webp" data-autoplay
           aria-label="Find the trials you need">
      <source src="assets/workflows/home-filter-annotate.mp4" type="video/mp4">
    </video>

    **Find the trials you need.** Filter by participant or condition. Star, tag and add notes to the readings you want to revisit.

    [Select trials for analysis :material-arrow-right:](tutorials/data-filtering/index.md){ .md-button }

=== "Compare readings"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/home-compare_poster.webp" data-autoplay
           aria-label="Put readings side by side">
      <source src="assets/workflows/home-compare.mp4" type="video/mp4">
    </video>

    **Put readings side by side.** Compare two participants, two conditions or two datasets. Overlay the scanpaths when both were recorded on the same screen size.

    [Compare two recordings :material-arrow-right:](guides/scanpath-visualization/controls.md#compare){ .md-button }

=== "Analyze a corpus"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/corpus-analysis_poster.webp" data-autoplay
           aria-label="Go beyond a single trial">
      <source src="assets/workflows/corpus-analysis.mp4" type="video/mp4">
    </video>

    **Go beyond a single trial.** Summarize the reading measures in your data by text, participant or group, and plot them against word features.

    [Analyze a text :material-arrow-right:](tutorials/corpus-analysis/analyze-one-text.md){ .md-button }

=== "Export & share"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="assets/workflows/home-export-share_poster.webp" data-autoplay
           aria-label="Take the figure with you">
      <source src="assets/workflows/home-export-share.mp4" type="video/mp4">
    </video>

    **Take the figure with you.** Save figures, replays or a batch of trials. Share a view as a link, or copy its Python or CLI code.

    [Export your first figure :material-arrow-right:](tutorials/exporting-figures/export-one-figure.md){ .md-button }

</div>

More examples in the [plot gallery](gallery.md).

<div class="sps-home-links" markdown>

[Python & CLI](guides/scanpath-visualization/index.md#render-in-code) · [FAQ](faq.md) · [Cite Scanpath Studio](about.md#cite-scanpath-studio) · [Feedback](https://github.com/lacclab/scanpath-studio/issues)

</div>

<div class="sps-development-note" markdown>

Scanpath Studio was developed with AI assistance. As with any research
software, cross-check its results before you rely on them in published work.
Found a bug, or have a feature request?
[Open an issue](https://github.com/lacclab/scanpath-studio/issues).

</div>
