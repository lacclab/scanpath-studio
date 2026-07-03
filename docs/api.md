# Python API

Everything the app draws is available headless through the package's public
functions. They follow one pipeline:

```text
load_scanpath_data / load_sample_data / load_potec   →   (words, fixations)
        list_trials            →  which (participant, trial) combos exist
        compute_word_metrics   →  per-word reading measures (FFD/FPRT/RPD/TFD …)
        plot_scanpath          →  a static Plotly figure
        animate_scanpath       →  an animated replay figure
        save_figure            →  .html / .png / .svg / .pdf on disk
```

All names are importable straight from the package root:

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
fig = sps.plot_scanpath(words, fixations, "p1", "t3", show_heatmap=False)
sps.save_figure(fig, "scanpath.png")
```

!!! note "Lazy imports"
    `import scanpath_studio` stays cheap — pandas / plotly / streamlit are only
    pulled in on the first API call (the package re-exports `api.py` /
    `datasets.py` lazily). The first call therefore pays a one-time import cost.

## Loading data

::: scanpath_studio.api.load_scanpath_data

::: scanpath_studio.api.load_sample_data

::: scanpath_studio.datasets.load_potec

## Inspecting & measuring

::: scanpath_studio.api.list_trials

::: scanpath_studio.api.compute_word_metrics

## Plotting

Any keyword accepted by the underlying figure builder can be passed through
`plot_scanpath` / `animate_scanpath` (e.g. `show_heatmap=False`,
`color_by="pass_index"`, `saccade_color="#444"`, `fixation_opacity=0.5`,
`x_field="order_in_trial"`). To colour saccades by reading type instead of one
uniform colour, pass `saccade_color_mode="By type"` (optionally with a
`saccade_class_colors={"regression": "#000", …}` palette). For the heatmap,
`heatmap_norm="Log"` compresses heavy-tailed dwell times. For the linear-reading
schematic, `saccade_render_mode="Arc"` arches the saccades and
`fixation_snap_to_word=True` places each fixation above its word. To overlay an
image stimulus (a screenshot of the reading screen) behind the scanpath, pass
`background_image="stim.png"` with `background_image_size=(w, h)` (and
`background_image_origin=(x0, y0)` for a centered crop); `background_image_opacity`
dims a busy image so the AOIs / fixations read over it.

::: scanpath_studio.api.plot_scanpath

::: scanpath_studio.api.animate_scanpath

## Saving

::: scanpath_studio.api.save_figure

To keep the layers **separable** for publication editing, `save_figure_layers`
writes one file per layer (word boxes / fixations / saccades / heatmap / labels /
stimulus image) — each the full figure with only that layer and a transparent
background, at the same size and axis ranges, so they register when stacked in
Illustrator / Inkscape:

```python
fig = sps.plot_scanpath(words, fixations, "p1", "t3", show_heatmap=True)
paths = sps.save_figure_layers(fig, "fig_layers", fmt="svg")   # {layer: Path}
```

::: scanpath_studio.api.save_figure_layers

Saved interactive HTML **autoplays on load** at the playback speed by default;
pass `autoplay=False` to save a replay that opens paused:

```python
anim = sps.animate_scanpath(words, fixations, "p1", "t3", playback_speed=4.0)
sps.save_figure(anim, "replay.html")                       # autoplays on load
paused = sps.animate_scanpath(words, fixations, "p1", "t3", autoplay=False)
sps.save_figure(paused, "replay_paused.html")              # opens paused
```

For rasterized animation (GIF / MP4) use the animation exporter:

```python
from scanpath_studio.animation_export import export_animation

anim = sps.animate_scanpath(words, fixations, "p1", "t3")
export_animation(anim, "replay.mp4")   # or replay.gif — needs Kaleido + Chrome
```

See [Export & troubleshooting](export-troubleshooting.md) for the Chrome /
ffmpeg requirements.
