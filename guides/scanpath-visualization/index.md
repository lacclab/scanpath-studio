# Scanpath visualization

1. Views and Help.
1. The trial control bar: dataset, trial, screen, sort (⇅) and filter ().
1. The trial's summary.
1. The figure.
1. Plot controls.
1. Annotations, Stimulus & context, Comparisons, Export and Share.

The Scanpath view draws one reading on the screen it was recorded on.

Looking for a specific button?

[All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md) lists every button and setting on this view, menu by menu, with a picture of each menu. Search it for what you want to change, such as *saccade color* or *legend position*.

## Choose a trial

Pick a trial above the plot. The filter () beside it narrows the list by text, participant, condition or annotation, and **⇅** sorts it. A trial with several screens gets a second navigator to move between them. When several participants have the same trial ID, each reading is in the list on its own, with its participant in brackets, `3 [p2]`.

## Control the layers

The **Plot controls** column holds every setting of the figure. Each layer is one line: a switch, and a **▾** with its settings.

| Section              | What it controls                                                                                                     |
| -------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Animate              | play the reading as a video, at a speed you choose                                                                   |
| Compare              | a second reading beside or over this one                                                                             |
| Design presets       | restyle the whole figure in one click: Scanpath, Heatmap, Illustration or your last custom settings                  |
| My designs           | save the current settings as a design, apply it again in one click, or export it to share or use on another computer |
| Palette              | one color scheme for the whole figure, such as colorblind-safe or print                                              |
| Fixations            | markers: size, color, order                                                                                          |
| Saccades             | lines and arrows, colored by direction or reading type                                                               |
| Stimulus             | text, span highlight, stimulus image, font and background                                                            |
| Word boxes           | each word's interest area: outline and fill, color and opacity                                                       |
| Heatmap              | where fixations concentrate, by count or duration                                                                    |
| Raw gaze             | the gaze samples as recorded                                                                                         |
| Filters & highlights | which fixations and saccades are drawn, and which stand out                                                          |
| Figure & canvas      | screen framing, axes and grid, title and labels, hover fields, legends                                               |

\[!\[

\](../../assets/workflows/plot-controls_poster.webp)\](../../assets/workflows/plot-controls.mp4)

## Under the plot

| Tab                    | What it is for                                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Annotations**        | Star, tag and write notes on the trial, to find or filter it later.                                                                                   |
| **Stimulus & context** | The trial's context, such as its title, question and answers, and its highlighted word spans.                                                         |
| **Comparisons**        | Compare this trial with other trials that match it on a field you choose, such as other readings of the same text, shown side by side.                |
| **Export**             | Download the figure (PNG, SVG, PDF, HTML) or the video (HTML, GIF, MP4), or a zip bundle of figures and data for many trials.                         |
| **Share**              | A link that reopens this view (for whoever has the same dataset loaded), the Python or command-line code that redraws the figure, or a settings file. |

Watch the tabs under the figure

\[!\[

\](../../assets/workflows/subtabs_poster.webp)\](../../assets/workflows/subtabs.mp4)

## Render in code

Set up a figure in the app, then open Share → Code for its Python or CLI recipe. For uploaded data, replace the placeholder file paths with your own.

Python and CLI: render the demo

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
fig = sps.plot_scanpath(words, fixations, "l37_1129", "l37_1129_2_1_1_Ele_r0")
sps.save_figure(fig, "scanpath.html")
```

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 -o scanpath.html
```

For your own files, use the [data loaders](https://lacclab.github.io/scanpath-studio/guides/loading-data/#load-and-inspect-in-code). Figure settings are listed in the [API options](https://lacclab.github.io/scanpath-studio/figure-options/index.md) and [CLI options](https://lacclab.github.io/scanpath-studio/cli/#common-tasks).

The [gallery](https://lacclab.github.io/scanpath-studio/gallery/index.md) gives app, CLI and Python instructions for heatmaps, comparisons, replays and other views. For [batch exports and GIF/MP4](https://lacclab.github.io/scanpath-studio/guides/exporting/index.md), see Export and share.

## Back up your work

Each of these files can be saved and loaded again:

| What                               | Where                                      |
| ---------------------------------- | ------------------------------------------ |
| figure settings                    | **Share → File**                           |
| favorites, tags and notes          | **Data Management → Annotations → Export** |
| column mapping and recording setup | **Edit dataset → Download setup file**     |
| saved figure designs               | **My designs → Export**                    |

None of them holds your data, so load the same data before restoring one. On your own computer, the app also keeps your datasets and work between sessions.
