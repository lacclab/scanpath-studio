# Export one figure

Save a scanpath, heatmap or comparison at the size you need.

In Essentials, use the view tiles to choose a figure. For **Design presets**, **Compare** and **My designs**, switch to **Full** at the top of the **Scanpath** view ([Essentials and Full](https://lacclab.github.io/scanpath-studio/dev/guides/scanpath-visualization/#essentials-and-full)).

## 1. Choose the view

Pick a trial in the **Scanpath** view. Choose one of the **Design presets**, or set the layers in the Plot controls. Turn on **Compare** if the figure needs two readings. Check that text and markers are readable and nothing is clipped.

## 2. Set the format and size

Open the **Export** tab and find **Current figure**. Choose the **Download format**:

| Output             | Format     |
| ------------------ | ---------- |
| Image              | PNG        |
| Vector figure      | SVG or PDF |
| Interactive figure | HTML       |

For a print PNG, set **Width** and **DPI**. For HTML that opens offline, tick **Self-contained HTML**.

## 3. Download

Click the download button for the chosen format, such as **⬇ Download PNG**.

\[!\[

\](../../../assets/workflows/export-figure_poster.webp)\](../../../assets/workflows/export-figure.mp4)

*Exporting a PNG at 180 mm and 300 dpi.*

## 4. Reuse the design or share the figure

- **My designs** in the Plot controls saves the look for other trials.
- **Share** → **Link** reopens the trial and its settings. For data you imported, send the source files and tell the recipient the dataset name shown in the link. They can open the link after importing the files under that name. If a comparison uses two imported datasets, send both. Someone who has only A can open its trial and return to the link after adding B. Your own copy of the link still works if you rename either dataset later.
- [**Share** → **Code**](https://lacclab.github.io/scanpath-studio/dev/guides/exporting/#from-the-app-to-a-script) gives Python or CLI code that redraws the figure.
- **Share** → **Settings file** → **Download settings** saves the settings, and **Restore settings** loads them again.
