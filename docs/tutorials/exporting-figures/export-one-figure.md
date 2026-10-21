---
description: "Export a publication-ready scanpath, gaze heatmap or comparison figure at the size you need, as PNG or SVG."
---

# Export one figure

Save a scanpath, heatmap or comparison at the size you need.

**Design presets**, **Compare** and **My designs** are in the **Advanced**
mode: switch to it in the top bar of the :material/route: **Scanpath** view,
or add `ui=advanced` to the app's address
([Simple and Advanced](../../guides/scanpath-visualization/index.md#simple-and-advanced)). In Simple, the view tiles choose the figure.

## 1. Choose the view { #1-choose-the-view }

Pick a trial in the :material/route: **Scanpath** view. Choose one of the
**Design presets**, or set the layers in the Plot controls. Turn on
:material/compare: **Compare** if the figure needs two readings.
Check that text and markers are readable and nothing is clipped.

## 2. Set the format and size

Open the :material/file_export: **Export** tab and find **Current figure**.
Choose the **Download format**:

| Output | Format |
| --- | --- |
| Image | PNG |
| Vector figure | SVG or PDF |
| Interactive figure | HTML |

For a print PNG, set **Width** and **DPI**. For HTML that opens offline, tick
**Self-contained HTML**.

## 3. Download

Click the download button for the chosen format, such as **⬇ Download PNG**.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/export-figure_poster.webp" data-autoplay
       aria-label="Exporting the figure 180 mm wide at 300 dpi">
  <source src="../../../assets/workflows/export-figure.mp4" type="video/mp4">
</video>

*Exporting a PNG at 180 mm and 300 dpi.*

## 4. Reuse the design or share the figure

- :material/palette: **My designs** in the Plot controls saves the look for
  other trials.
- :material/share: **Share** → **Link** reopens the trial and its settings.
  The link does not carry data you uploaded, so load that data separately.
- [**Share** → **Code**](../../guides/exporting/index.md#from-the-app-to-a-script)
  gives Python or CLI code that redraws the figure.
- **Share** → **Settings file** → **Download settings** saves the settings,
  and **Restore settings** loads them again.
