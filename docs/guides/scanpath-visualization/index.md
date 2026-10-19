---
description: "Visualize eye movements over the text: fixations, saccades, word boxes, heatmaps and raw gaze for each trial, plus replay and comparison of two scanpaths."
---

# Scanpath visualization

<figure class="sps-screenshot" markdown>
![The Scanpath view, its regions numbered](../../assets/screenshots/scanpath-view.webp)
</figure>

1. Views and :material/help: Help.
2. The trial control bar: dataset, trial, screen, sort (⇅) and filter (:material/filter_alt:).
3. The trial's summary.
4. The figure.
5. Plot controls.
6. The tabs: Annotations, Stimulus & context, Comparisons, Export and Share.

The :material/route: **Scanpath** view draws one reading at a time, at the size of
the screen it was recorded on.

!!! tip "Looking for a specific button?"

    [All controls](controls.md) lists every button and setting on this view,
    menu by menu, with a picture of each menu. Search it for what you want to
    change, such as *saccade color* or *legend position*.

## Choose a trial

Pick a trial in **Select trial** above the plot, or step through the list with
**◀ ▶**. The filter (:material/filter_alt:) beside it narrows the list by text,
participant, condition or annotation, and **⇅** sorts it. On a trial recorded
over several screens, **Screen** picks the screen to draw. When several
participants have the same trial ID, the list shows each reading with its
participant in brackets, such as `3 [p2]`.

[All controls → Trial control bar](controls.md#trial-control-bar) describes
each control.

## Control the layers

The :material/tune: **Plot controls** column, on the right of the plot, holds
the figure's settings. Each layer has a row with a switch that turns it on or
off and a **▾** that opens its settings.

| Section | What it controls |
| --- | --- |
| :material/movie: **Animate** | replay the fixations in the order they happened, at a speed you choose |
| :material/compare: **Compare** | draw a second reading over this one, beside it or below it |
| **Design presets** | restyle the whole figure in one click: **Scanpath**, **Heatmap**, **Illustration**, or **Custom** for your most recent settings |
| :material/palette: **My designs** | save the current settings as a design, apply it again in one click, or export your designs to share them or use them on another computer |
| **Palette** | one color scheme for the whole figure: **Default (colorblind-safe)**, **Print / grayscale** or **High contrast** |
| :material/blur_on: **Fixations** | the fixation markers: color, shape and size, and the fixation index |
| :material/arrow_outward: **Saccades** | the saccade lines and arrows, in one color, by direction or by saccade type |
| :material/article: **Stimulus** | the text (or redacted blocks), highlighted words, the stimulus image, the font and the background |
| :material/crop_square: **Word boxes** | each word's box: outline and fill, color and opacity |
| :material/local_fire_department: **Heatmap** | where fixations concentrate, by fixation count or duration |
| :material/grain: **Raw gaze** | the gaze samples as recorded |
| :material/filter_list: **Filters & highlights** | which fixations and saccades are drawn, and which stand out |
| :material/aspect_ratio: **Figure & canvas** | screen framing, axes and grid, title and labels, hover fields and legends |

[All controls → Plot controls](controls.md#plot-controls) describes every
setting in each menu.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../assets/workflows/plot-controls_poster.webp" data-autoplay
       aria-label="Changing the plot layers and their settings">
  <source src="../../assets/workflows/plot-controls.mp4" type="video/mp4">
</video>

## Under the plot

| Tab | What it is for |
| --- | --- |
| **Annotations** | Star, tag and write notes on the trial, to find or filter it later. |
| **Stimulus & context** | The trial's context, such as its title, question and answers, and its highlighted word spans. |
| **Comparisons** | Show the other trials that share a field with this one, such as other readings of the same text, in a grid of small figures. |
| **Export** | Download the figure on screen (PNG, SVG, PDF or HTML) or its replay (HTML, GIF or MP4), or build a zip bundle of figures and data for many trials. |
| **Share** | **Link** reopens this trial with these settings for anyone who has the same dataset. **Code** gives the Python or CLI code that redraws the figure. **Settings file** saves the plot settings and restores them. |

[All controls → Under the plot](controls.md#under-the-plot) lists each tab's
controls.

??? example "Watch the tabs under the figure"

    <video class="sps-shot" controls muted loop playsinline preload="none"
           poster="../../assets/workflows/subtabs_poster.webp" data-autoplay
           aria-label="Annotations, stimulus context, comparisons, export and share">
      <source src="../../assets/workflows/subtabs.mp4" type="video/mp4">
    </video>

## Render in code

Set up a figure in the app, then open **Share** → **Code** for the Python or
CLI code that redraws it. For a dataset you imported, replace the placeholder
file paths with your own.

??? example "Python and CLI: render the demo"

    === "Python"

        ```python
        import scanpath_studio as sps

        words, fixations = sps.load_sample_data()
        fig = sps.plot_scanpath(words, fixations, "l37_1129", "l37_1129_2_1_1_Ele_r0")
        sps.save_figure(fig, "scanpath.html")
        ```

    === "CLI"

        ```bash
        scanpath-studio render --sample \
          -p l37_1129 -t l37_1129_2_1_1_Ele_r0 -o scanpath.html
        ```

    For your own files, use the [data loaders](../loading-data/index.md#load-and-inspect-in-code).
    The [figure options table](../../api.md#figure-options) lists every figure
    setting with its Python keyword and CLI flag. For more CLI examples, see
    [Common tasks](../../cli.md#common-tasks).

The [gallery](../../gallery.md) shows how to make heatmaps, comparisons,
replays and other figures in the app, the CLI and Python. For batch export and
GIF or MP4 replays, see [Export and share](../exporting/index.md).

## Back up your work

You can save each of these to a file and load it again:

| What | Where |
| --- | --- |
| figure settings | :material/share: **Share** → **Settings file** |
| favorites, tags and notes | :material/database: **Data Management** → **Annotations** → **Export** |
| column mapping and recording setup | :material/edit: **Edit dataset** → **Download setup file** |
| saved figure designs | :material/palette: **My designs** → **Export** |

None of these files holds your data, so load the same data before you restore
one. In the desktop app or a local install, the app also keeps your datasets,
annotations and designs between sessions. See :material/database: **Data
Management** → :material/history: **Saved on this computer**.
