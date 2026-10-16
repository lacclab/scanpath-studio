# Export and share

Save a figure, export a batch, or reuse a view in the app or in code.

## In the app

| Goal                                | Where                       |
| ----------------------------------- | --------------------------- |
| Save the figure or replay on screen | Export → Current figure     |
| Export many trials and their tables | Export → Export bundle      |
| Share a view or copy its code       | Share → Link or Code        |
| Reuse the design                    | My designs, or Share → File |

For step-by-step instructions, see the [export tutorials](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/index.md).

## Reproduce a figure

Open Share → Code and copy Python or CLI. The snippet carries the figure's settings and your column mapping; replace any placeholder file paths. [Render in code](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#render-in-code) shows a minimal example.

For a print-sized PNG, Python's `save_figure` accepts `width_mm` and `dpi`; the CLI uses `--width-mm` and `--dpi`. Use `save_figure_layers` or `render --separable-layers` for editable layers.

## Batch export

Export → Export bundle uses the chosen trials in the app. For a scripted batch, loop over the trial list:

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

Use the [data loaders](https://lacclab.github.io/scanpath-studio/guides/loading-data/#load-and-inspect-in-code) for your own files. The CLI's `render` writes one trial per invocation.

## Replay export

With Animate on, Export → Current figure saves HTML, GIF or MP4. The CLI's `render --animate` saves interactive HTML. For a GIF or MP4 in Python:

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

[Export setup and troubleshooting](https://lacclab.github.io/scanpath-studio/faq/#export-fails) · [Python save options](https://lacclab.github.io/scanpath-studio/api/#save) · [CLI options](https://lacclab.github.io/scanpath-studio/cli/#common-options)
