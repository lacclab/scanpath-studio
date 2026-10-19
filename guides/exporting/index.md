# Export and share

Save a figure, export many trials at once, or reuse a view in the app or in code.

## In the app

| Goal                                | Where                                            |
| ----------------------------------- | ------------------------------------------------ |
| Save the figure or replay on screen | **Export** → **Current figure**                  |
| Export many trials and their tables | **Export** → **Export bundle**                   |
| Share a view or copy its code       | **Share** → **Link** or **Code**                 |
| Reuse the figure settings           | **My designs**, or **Share** → **Settings file** |

For step-by-step instructions, see the [export tutorials](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/index.md).

\[!\[

\](../../assets/workflows/share-link_poster.webp)\](../../assets/workflows/share-link.mp4)

A link reopens the trial and its settings for anyone who has the same dataset. [All controls → Under the plot](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/#under-the-plot) says what the recipient needs.

## Reproduce a figure

Open **Share** → **Code** and copy the Python or CLI code. It carries the figure's settings and your column mapping. For a dataset you imported, replace the placeholder file paths with your own. [Render in code](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#render-in-code) shows a minimal example.

For a PNG at print size, pass `width_mm` and `dpi` to `save_figure`, or `--width-mm` and `--dpi` to `render`. To edit the layers in a vector editor, save each layer to a separate file with `save_figure_layers` or `render --separable-layers`. In the app's export bundle, this is **Layers as separate files**.

## Batch export

In the app, **Export bundle** → **Trials to include** picks the trials: **This trial**, **All filtered trials**, **All trials of one participant**, **All trials of one text** or **All trials, ignoring filters**. For a scripted batch, loop over the trial list:

Python: one HTML figure per trial

```
from pathlib import Path

import scanpath_studio as sps

words, fixations = sps.load_sample_data()
out = Path("figures")
out.mkdir(exist_ok=True)

for pid, tid in sps.list_trials(words, fixations).itertuples(index=False):
    fig = sps.plot_scanpath(words, fixations, pid, tid)
    sps.save_figure(fig, out / f"{pid}_{tid}.html")
```

Use the [data loaders](https://lacclab.github.io/scanpath-studio/guides/loading-data/#load-and-inspect-in-code) for your own files. The CLI's `render` writes one trial per run.

## Replay export

With **Animate** on, **Export** → **Current figure** saves the replay as HTML, GIF or MP4. The CLI's `render --animate` saves interactive HTML only. For a GIF or MP4 in Python:

Python: save a GIF or MP4

```
from pathlib import Path

import scanpath_studio as sps
from scanpath_studio.animation_export import export_animation

words, fixations = sps.load_sample_data()
replay = sps.animate_scanpath(words, fixations, "l37_1129", "l37_1129_2_1_1_Ele_r0")
Path("replay.mp4").write_bytes(export_animation(replay, fmt="mp4"))
```

Use `fmt="gif"` and a `.gif` filename for GIF output.

[Export setup and troubleshooting](https://lacclab.github.io/scanpath-studio/faq/#export-fails) · [Python save options](https://lacclab.github.io/scanpath-studio/api/#save) · [CLI options](https://lacclab.github.io/scanpath-studio/cli/#common-tasks)
