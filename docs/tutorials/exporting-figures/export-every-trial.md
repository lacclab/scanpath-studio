---
description: "Batch-export scanpath figures and data tables for every selected eye-tracking trial as one ZIP."
---

# Export every trial

Build a ZIP of static figures and data tables for a set of trials.

1. [Set the figure's design](export-one-figure.md#1-choose-the-view) once.
   Each exported trial uses that design, without animation or a comparison partner.
2. Open Export → Export bundle and select this trial, the active filtered pool,
   or the whole dataset.
3. Choose figure and table formats and check the filename pattern.
   For editing individual layers later, turn on **Layers as separate files**.
4. Build and download the bundle, then inspect one exported figure.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/export-bundle_poster.webp" data-autoplay
       aria-label="Exporting every trial's figures and tables as one zip">
  <source src="../../../assets/workflows/export-bundle.mp4" type="video/mp4">
</video>

*Exporting figures and tables for the demo's trials; the build is fast-forwarded.*

Keep `plot_config.json` for the design, `README.md` for the build details and
`index.csv` for the file list and failures. Keep your original data and record
its version and the selected trial filters separately.

For a [scripted batch](../../guides/exporting/index.md#batch-pattern), use the
Python recipe in Export and share.
