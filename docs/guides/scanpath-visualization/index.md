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
6. Annotations, Stimulus & context, Comparisons, Export and Share.

The Scanpath view draws one reading on the screen it was recorded on.

!!! tip "Looking for a specific button?"

    [All controls](controls.md) lists every button and setting on this view,
    menu by menu, with a picture of each menu. Search it for what you want to
    change, such as *saccade color* or *legend position*.

## Choose a trial

Pick a trial above the plot. The filter (:material/filter_alt:) beside it
narrows the list by text, participant, condition or annotation, and **⇅** sorts
it. A trial with several screens gets a second navigator to move between them.
When several participants have the same trial ID, each reading is in the list
on its own, with its participant in brackets, `3 [p2]`.

## Control the layers

The **:material/tune: Plot controls** column holds every setting of the figure.
Each layer is one line: a switch, and a **▾** with its settings.

| Section | What it controls |
| --- | --- |
| :material/movie: Animate | play the reading as a video, at a speed you choose |
| :material/compare: Compare | a second reading beside or over this one |
| Design presets | restyle the whole figure in one click: Scanpath, Heatmap, Illustration or your last custom settings |
| :material/palette: My designs | save the current settings as a design, apply it again in one click, or export it to share or use on another computer |
| Palette | one color scheme for the whole figure, such as colorblind-safe or print |
| :material/blur_on: Fixations | markers: size, color, order |
| :material/arrow_outward: Saccades | lines and arrows, colored by direction or reading type |
| :material/article: Stimulus | text, span highlight, stimulus image, font and background |
| :material/crop_square: Word boxes | each word's interest area: outline and fill, color and opacity |
| :material/local_fire_department: Heatmap | where fixations concentrate, by count or duration |
| :material/grain: Raw gaze | the gaze samples as recorded |
| :material/filter_list: Filters & highlights | which fixations and saccades are drawn, and which stand out |
| :material/aspect_ratio: Figure & canvas | screen framing, axes and grid, title and labels, hover fields, legends |

## Under the plot

| Tab | What it is for |
| --- | --- |
| **Annotations** | Star, tag and write notes on the trial, to find or filter it later. |
| **Stimulus & context** | The trial's context, such as its title, question and answers, and its highlighted word spans. |
| **Comparisons** | Compare this trial with other trials that match it on a field you choose, such as other readings of the same text, shown side by side. |
| **Export** | Download the figure (PNG, SVG, PDF, HTML) or the video (HTML, GIF, MP4), or a zip bundle of figures and data for many trials. |
| **Share** | A link that reopens this view (for whoever has the same dataset loaded), the Python or command-line code that redraws the figure, or a settings file. |

## Render in code

Set up a figure in the app, then open Share → Code for its Python or CLI
recipe. For uploaded data, replace the placeholder file paths with your own.

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
    Figure settings are listed in the [API options](../../api.md#figure-options)
    and [CLI options](../../cli.md#common-options).

The [gallery](../../gallery.md) gives app, CLI and Python instructions for
heatmaps, comparisons, replays and other views.
For [batch exports and GIF/MP4](../exporting/index.md), see Export and share.

## Back up your work

Each of these files can be saved and loaded again:

| What | Where |
| --- | --- |
| figure settings | **:material/share: Share → File** |
| favorites, tags and notes | **:material/database: Data Management → Annotations → Export** |
| column mapping and recording setup | **:material/edit: Edit dataset → Download setup file** |
| saved figure designs | **:material/palette: My designs → Export** |

None of them holds your data, so load the same data before restoring one. On
your own computer, the app also keeps your datasets and work between sessions.
