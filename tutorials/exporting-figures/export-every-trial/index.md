# Export every trial

Build a ZIP of static figures and data tables for a set of trials.

Before you start, switch to **Full** at the top of the **Scanpath View** ([Essentials and Full](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#essentials-and-full)).

1. [Set the figure's design](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/export-one-figure/#1-choose-the-view) once. Each exported trial uses that design, without animation or a comparison partner.
1. Open the **Export** tab. Under **Export bundle** → **Trials to include**, choose **This trial**, **All filtered trials**, **All trials of one participant**, **All trials of one text** or **All trials, ignoring filters**.
1. Choose the **Figure formats** and, under **Also include**, the tables and their **Table format**. Check the **File path pattern**. To edit individual layers later, turn on **Layers as separate files**.
1. Click **Build export**, download the bundle, and inspect one exported figure.

For PNGs, turn on **Smaller PNG files** to reduce file size at the same resolution. This adds encoding time. Images over 16.8 megapixels use the standard encoding to limit memory use. Outside the app, `scanpath-studio render --compact-png` and `save_figure(..., compact_png=True)` do the same for one figure and its layers. **PNG scale** controls resolution separately. A scale of 1 writes one pixel per figure pixel, and the default scale of 2 doubles both dimensions.

Large bundles are kept on temporary disk and download as one ZIP in a new tab. Keep the Export panel open until the download finishes. If your browser cannot stream the ZIP, the download page offers numbered parts and instructions for joining them.

\[!\[

\](../../../assets/workflows/export-bundle_poster.webp)\](../../../assets/workflows/export-bundle.mp4)

*Exporting figures and tables for the bundled demo's trials. The build is sped up in this recording.*

Keep each trial's `plot_config.json` for the design, `README.md` for the build details and `index.csv` for the file list and failures. Keep your original data and record its version and the selected trial filters separately.

For a [scripted batch](https://lacclab.github.io/scanpath-studio/guides/exporting/#batch-pattern), use the Python recipe in Export and share.
