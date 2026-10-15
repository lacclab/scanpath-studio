# Export one figure

A real scanpath for a paper or a talk — as a scanpath, a heatmap or a comparison — at the size the page needs.

## 1. Choose the view

Set the monitor size first, under **Data Management → Edit dataset → Recording setup**; it defines the figure's coordinate system. Then choose the participant and trial, and keep only the layers that answer the question:

- **Fixations + saccades + text** for a conventional scanpath;
- **Heatmap + text** for spatial concentration;
- **Compare** for two trials of the same text.

The design presets set a whole view in one click — **Scanpath**, **Heatmap**, **Illustration** — and every layer stays adjustable from there.

\[!\[

\](../../../assets/workflows/design-presets_poster.webp)\](../../../assets/workflows/design-presets.mp4)

*One click for each design: Heatmap, Illustration and Scanpath, then a heatmap added to the scanpath.*

## 2. Make it clean

Check the whole canvas for clipped marks, unreadable text, and an unnecessary legend. When several figures must share identical grid marks, set a manual interval under **Figure & canvas → Axes & grid → Grid** (untick **Auto**).

## 3. Export it

Open **Export → Current figure** and choose:

| Need                   | Format     |
| ---------------------- | ---------- |
| editable vector        | SVG or PDF |
| image for slides/web   | PNG        |
| interactive inspection | HTML       |

PNG and SVG are saved by your browser from the figure on screen, and HTML needs nothing either (it loads Plotly from the internet when opened, or tick **Self-contained HTML** for a larger file that opens offline); PDF needs Chrome, Chromium or Edge. For print, give the PNG a **Width** (mm or in) and a **DPI**: 180 mm at 600 dpi is 4,252 px wide, and **Share → Code** writes the same size. Without a width, the plot's own camera button saves the same PNG.

\[!\[

\](../../../assets/workflows/export-figure_poster.webp)\](../../../assets/workflows/export-figure.mp4)

*Setting the width to 180 mm at 300 dpi and downloading the PNG.*

## 4. Save the look for next time

To give the next figure the same look, save its settings as a design: open **My designs** in the plot rail and select its save button. A saved design applies the same layers, colors and sizes to any trial in one click. **Export** writes your designs to a file, and **Import** reads one back on another computer or shares them with a colleague.

## 5. Keep it reproducible

Under the plot, **Share** keeps the figure reproducible: **Link** reopens the app on this trial with these settings, **Code** writes the Python or command line that redraws it, and **File** saves the settings to load again later.

\[!\[

\](../../../assets/workflows/share-link_poster.webp)\](../../../assets/workflows/share-link.mp4)

*Looking at the code that redraws the figure, then copying a link that reopens the same trial with the same design.*
