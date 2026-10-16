# Export every trial

Build a ZIP of static figures and data tables for a set of trials.

1. [Set the figure's design](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/export-one-figure/#1-choose-the-view) once. Each exported trial uses that design, without animation or a comparison partner.
1. Open Export → Export bundle and select this trial, the active filtered pool, or the whole dataset.
1. Choose figure and table formats and check the filename pattern. For editing individual layers later, enable separable layers.
1. Build and download the bundle, then inspect one exported figure.

\[!\[

\](../../../assets/workflows/export-bundle_poster.webp)\](../../../assets/workflows/export-bundle.mp4)

*Exporting figures and tables for the demo's trials; the build is fast-forwarded.*

Keep `plot_config.json` for the design, `README.md` for the build details and `index.csv` for the file list and failures. Keep your original data and record its version and the selected trial filters separately.

For a [scripted batch](https://lacclab.github.io/scanpath-studio/guides/exporting/#batch-pattern), use the Python recipe in Export and share.
