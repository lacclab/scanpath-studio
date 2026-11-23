---
description: "Visualize eye movements over the text: fixations, saccades, word boxes, heatmaps and raw gaze for each trial, plus replay and comparison of two scanpaths."
---

# Scanpath visualization

<figure class="sps-screenshot" markdown>
![The Scanpath view, its regions numbered](../../assets/screenshots/scanpath-view.webp)
</figure>

1. Views and :material/help: Help.
2. The **Essentials | Full** switch ([below](#essentials-and-full)).
3. The trial control bar: dataset, trial, screen, sort (⇅) and filter (:material/filter_alt:).
4. The trial's summary.
5. The figure.
6. Plot controls.
7. The tabs: Annotations, Stimulus & context, Comparisons, Export and Share.

The :material/route: **Scanpath** view draws one reading at a time, at the size of
the screen it was recorded on.

!!! tip "Looking for a specific button?"

    [All controls](controls.md) lists every button and setting on this view,
    menu by menu, with a picture of each menu. Search it for what you want to
    change, such as *saccade color* or *legend position*.

## Essentials and Full

The Scanpath view opens in **Essentials**, with the main controls for exploring
a reading. Switch to **Full** in the top bar whenever you want more options.
The app remembers your choice in this browser.

Essentials shows:

- the dataset and trial pickers with **◀ ▶**;
- the plot, which starts with a replay on a new visit;
- the **Animation** switch, five static views and the **Palette**;
- the **Export** tab, for the figure on screen, and **Share**.

The :material/add: **More** buttons show which additional controls are available
in Full and offer **Switch to Full**. The view controls and Palette stay in the same place when you switch modes.
An active comparison keeps its switch in Essentials. Settings you chose in Full, such as trial
filters, remain active in Essentials; a short note tells you when they apply.
Starting a tutorial from :material/help: **Help** switches to Full for the
current visit. :material/bar_chart: **Corpus Analysis** and
:material/database: **Data Management** are the same in both modes.

To open a mode for one visit, add `?ui=full` or `?ui=essentials` to the app's
address (use `&` if the address already has a `?`). This leaves your saved
choice unchanged. Links created with **Share** use the recipient's own mode.

The numbered regions above and the rest of this guide describe Full.

## Choose a trial

Pick a trial in **Select trial** above the plot, or step through the list with
**◀ ▶**. The filter (:material/filter_alt:) beside it narrows the list by text,
participant, condition or annotation, and **⇅** sorts it. On a trial recorded
over several screens, **Screen** picks the screen to draw. When several
participants have the same trial ID, the list shows each reading with its
participant in brackets, such as `3 [p2]`.

[All controls → Trial control bar](controls.md#trial-control-bar) describes
each control.

### Keyboard shortcuts

| With focus on | Keys | Action |
| --- | --- | --- |
| The page, plot background or trial arrow buttons | ++left++ / ++right++ | Previous or next trial in the current list (A in Compare) |
| The page, plot background or trial arrow buttons | ++shift+left++ / ++shift+right++ | Previous or next trial for B in Compare |
| The page or plot background | ++space++ | Play or pause the replay |
| The **Replay time** slider | ++left++ / ++right++ | Pause and step one frame |
| The **Replay time** slider | ++home++ / ++end++ | Jump to the first or last frame |
| The **Replay time** slider | ++space++ | Play or pause from the current frame |

With **A and B together** on, either pair of trial shortcuts steps both
readings. Use ++tab++ and ++shift+tab++ to reach the replay controls. The slider keys
also work in downloaded HTML replays.

## Control the layers

Both modes start with the same **View** tiles and **Palette**. In Full, use
**Find a setting** to jump to a control by name, or open **Layers** to change what appears in the plot. Click a layer’s name to edit
its settings or its switch to show or hide it. Choose **Axes** to chart the
reading by fixation order or time. **Figure** holds the settings for the whole
plot, including framing, titles and legends.

**Gaze over time** plots elapsed seconds along the horizontal axis and horizontal
screen position in pixels on the vertical axis. The length of each horizontal
bar shows how long the fixation lasted. Turn **Animation** on to replay the
reading on the text, then off to return to the same chart. **Custom** brings
back your last hand-edited figure.

| Section | What it controls |
| --- | --- |
| **View** | switch **Animation** on or off, or choose **Scanpath**, **Heatmap**, **Illustration**, **Gaze over time** or **Custom** |
| **Palette** | choose **Default (colorblind-safe)**, **Print / grayscale**, or **High contrast** |
| :material/compare: **Compare readings** | add a second reading over this one, beside it, or below it |
| :material/movie: **Animation settings** | set playback speed, autoplay, and frame quality |
| :material/palette: **My designs** | save a named design, apply it to another reading, or share it |
| :material/blur_on: **Fixations** | the fixation markers: color, shape and size, and the fixation index |
| :material/arrow_outward: **Saccades** | the saccade lines and arrows, in one color, by direction or by saccade type |
| :material/article: **Stimulus** | the text (or redacted blocks), highlighted words, the stimulus image, the font and the background |
| :material/crop_square: **Word boxes** | each word's box: outline and fill, color and opacity |
| :material/local_fire_department: **Heatmap** | where fixations concentrate, by fixation count or duration |
| :material/grain: **Raw gaze** | the gaze samples as recorded |
| :material/filter_list: **Filters & highlights** | which fixations and saccades are drawn, and which stand out |
| **Axes** | chart presets, X and Y fields, and the coordinate grid |
| **Figure** | screen framing, title and labels, hover fields and legends |

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
        fig = sps.plot_scanpath(words, fixations, "l37_273", "l37_273_2_1_1_Ele")
        sps.save_figure(fig, "scanpath.html")
        ```

    === "CLI"

        ```bash
        scanpath-studio render --sample \
          -p l37_273 -t l37_273_2_1_1_Ele -o scanpath.html
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
| favorites, tags and notes | :material/database: **Data Management** → **Current dataset** → **Annotations** → **Export** |
| column mapping and recording setup | :material/edit: **Edit dataset** → **Download setup file** |
| saved figure designs | :material/palette: **My designs** → **Export** |

Keep your source data alongside these files, and load the same dataset before
restoring them. In the desktop app or a local install, the app also keeps your datasets,
annotations and designs between sessions. See :material/database: **Data
Management** → **Saved work → Your session**.
