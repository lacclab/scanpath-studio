# Export one figure

Open **Export → Current figure** and choose:

| Need | Format |
| --- | --- |
| editable vector | SVG or PDF |
| image for slides/web | PNG |
| interactive inspection | HTML |

PNG and SVG are saved by your browser from the figure on screen, and HTML
needs nothing either (it loads Plotly from the internet when opened, or tick
**Self-contained HTML** for a larger file that opens offline); PDF needs
Chrome, Chromium or Edge. For print, give the PNG a **Width** (mm or in) and a
**DPI**: 180 mm at 600 dpi is 4,252 px wide, and **Share → Code** writes the
same size. Without a width, the plot's own camera button saves the same PNG.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/export-figure_poster.webp" data-autoplay
       aria-label="Exporting the figure 180 mm wide at 300 dpi">
  <source src="../../../assets/workflows/export-figure.mp4" type="video/mp4">
</video>

*Setting the width to 180 mm at 300 dpi and downloading the PNG.*

Keep a **:material/share: Share → File** settings file beside the figure, so it
can be [redrawn exactly](share-the-figure.md).
