---
description: "Batch-export scanpath figures and data tables for every selected eye-tracking trial as one ZIP."
---

# Export every trial

Build a ZIP of static figures and data tables for a set of trials.

These steps use the **Full** mode: switch to it in the top bar of the
:material/route: **Scanpath** view, or add `ui=full` to the app's
address ([Essentials and Full](../../guides/scanpath-visualization/index.md#essentials-and-full)).

1. [Set the figure's design](export-one-figure.md#1-choose-the-view) once.
   Each exported trial uses that design, without animation or a comparison partner.
2. Open the :material/file_export: **Export** tab. Under **Export bundle** →
   **Trials to include**, choose **This trial**, **All filtered trials**,
   **All trials of one participant**, **All trials of one text** or
   **All trials, ignoring filters**.
3. Choose the **Figure formats** and, under **Also include**, the tables and
   their **Table format**. Check the **File path pattern**. To edit individual
   layers later, turn on **Layers as separate files**.
4. Click **Build export**, download the bundle, and inspect one exported figure.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/export-bundle_poster.webp" data-autoplay
       aria-label="Exporting every trial's figures and tables as one zip">
  <source src="../../../assets/workflows/export-bundle.mp4" type="video/mp4">
</video>

*Exporting figures and tables for the bundled demo's trials. The recording
speeds up the build.*

Keep each trial's `plot_config.json` for the design, `README.md` for the build
details and `index.csv` for the file list and failures. Keep your original data
and record its version and the selected trial filters separately.

For a [scripted batch](../../guides/exporting/index.md#batch-pattern), use the
Python recipe in Export and share.
