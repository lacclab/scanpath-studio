# Tutorial 3 — Produce a figure for a paper

**Goal:** turn one trial into a figure a journal will accept — vector output,
legible at column width, greyscale-safe, and (if you want) split into layers
you can restyle in Illustrator or Inkscape.

**You need:** the bundled demo is enough. PNG / SVG / PDF go through
[Kaleido](https://github.com/plotly/Kaleido), which drives a headless Chrome —
run `plotly_get_chrome -y` once if you haven't. Interactive **HTML** needs no
browser.

---

## 1. Strip the figure back

The app's defaults are tuned for *exploring*. A paper figure wants less. In the
control rail, the changes that matter most:

| Turn **off** | Why |
| --- | --- |
| **Heatmap** | It fights with the word boxes at print size and rarely survives greyscale. |
| **Fixation numbers** (order labels) | Illegible below about 12 pt; the saccade path already carries the order. |
| **Word boxes** | Keep them only if the AOIs are the point. |
| **Raw gaze** | Almost never reproduces on paper. |

| Turn **on / tune** | Why |
| --- | --- |
| **Font size** | Raise it. The figure is drawn at monitor scale, then shrunk into a column. |
| **Fixation opacity** | Below 1.0 so overlapping fixations stay readable. |
| **Fixation symbol** | Shape survives greyscale printing; colour doesn't. |
| **Saccade colour by type** | Forward / skip / refixation / return-sweep / regression, each its own legended colour — often the whole point of the figure. |
| **Saccade width / style** | Thicker lines survive downscaling; dashed distinguishes a second condition. |

!!! tip "Set the monitor resolution first"
    Everything is drawn true-to-scale from the word boxes plus the recording
    **monitor resolution** (Experimental Setup). Get it wrong and the text is
    the wrong size relative to the fixations — see
    [True-to-scale rendering](../rendering.md).

---

## 2. Export from the app

**Export** subtab → **This trial**:

- **Download format** — PNG · SVG · PDF · HTML. **HTML downloads in one
  click**; PNG/SVG/PDF have a **Render <format>** step first, because each one
  spins up a headless Chrome and that's far too slow to run on every rerun. The
  download button appears once the image is ready.
- PNG is rendered at **3×** so it stays paper-quality; SVG and PDF are vector
  and unaffected.
- Exporting a **comparison** or an **animation** round-trips the on-screen view
  exactly — what you see is what is saved.

Below that, **Multiple trials** is the bulk exporter (figures, tables, and a
mega-table across many trials, zipped). Its scope picker offers *All*, *All
filtered trials*, *All trials of one participant* and *All trials of one text*,
and it prints how many trials that is before you commit.

!!! info "SVG or PDF, not PNG"
    Take vector out of the app whenever the target is a paper. A scanpath is
    lines, boxes and text — everything a raster format handles badly at print
    resolution.

---

## 3. The same figure headlessly

Reproducible beats clicked. This is the exact call behind a paper-shaped
figure:

```python
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
combos = sps.list_trials(words, fixations)
pid, tid = combos.iloc[0][["participant_id", "trial_id"]]

fig = sps.plot_scanpath(
    words, fixations, pid, tid,
    canvas_size=(2560, 1440),      # the recording monitor
    base_font_size=18,             # bigger: this gets shrunk into a column
    show_heatmap=False,            # noisy in print
    show_order=False,              # fixation-index labels: illegible when small
    show_words=True,               # keep the AOI boxes
    fixation_opacity=0.8,          # overlapping fixations stay readable
    saccade_color_mode="By type",  # forward / skip / refixation / sweep / regression
)
sps.save_figure(fig, "figure.pdf")     # .pdf / .svg / .png / .html
```

Every layer toggle is a keyword. To see the full list with its defaults:

```python
from scanpath_studio.api import figure_options

opts = figure_options()             # 57 options for the static figure
print(sorted(opts))
print(figure_options("animation"))  # the replay builder's subset
```

!!! tip "Typo'd a keyword? The error tells you the right one"
    `plot_scanpath(..., show_word_boxes=True)` raises

    ```text
    TypeError: plot_scanpath() got an unexpected keyword argument:
    'show_word_boxes' (did you mean 'show_word_labels', 'show_words',
    'show_order'?)
    ```

    — followed by the full list of valid options. It's the fastest way to find
    the name you meant. (The one you wanted there is `show_words`.)

---

## 4. From the command line

The same figure without writing Python:

```bash
scanpath-studio render --sample \
    -p l37_1129 -t l37_1129_2_2_1_Adv_r0 \
    --no-heatmap --no-order \
    --canvas 2560x1440 --font-size 18 --scale 3 \
    -o figure.png
```

Flags worth knowing for figures:

| Flag | Use |
| --- | --- |
| `--scale X` | Raster pixel-density multiplier (default 2.0). Use 3 for print PNG. |
| `--width PX` / `--height PX` | Fixed output size — for a thumbnail strip where every panel must match. |
| `--font-size PX` / `--font-family NAME` | Word-label typography (default 16, `monospace`). |
| `--marker-size-range MIN MAX` | Shrink fixation markers for a small figure (default `8 24`). |
| `--fixation-symbol SHAPE` | `circle`, `square`, `diamond`, `triangle-up`, `cross`, `x`, `star`, `hexagon`, `heart` — shape survives greyscale. |
| `--saccade-color-by-type` | The five reading classes, each its own colour, with a legend. |
| `--saccade-type-color CLASS=COLOR` | Override one class, e.g. `regression=#000000`. Repeatable. |
| `--no-saccade-type-legend` | Coloured saccades, no colour key (when the caption explains it). |
| `--heatmap-colorscale NAME` | A print-safe scale, e.g. `Greys`. |
| `--heatmap-norm log` | Compresses heavy-tailed dwell times so a few hot words don't wash out the rest. |

`--list-trials` prints the available `(participant, trial)` pairs; the full flag
reference is in the [CLI docs](../cli.md).

---

## 5. Separable layers

For a figure you'll finish by hand, export **one file per layer** — each the
full figure with only that layer drawn, on a transparent background, at the
same size and axis ranges. Stack them in Illustrator / Inkscape and they
register exactly.

```python
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
paths = sps.save_figure_layers(fig, "fig_layers", fmt="svg")   # {layer: Path}
print(sorted(paths))
```

```text
['fixations', 'frame', 'heatmap', 'labels', 'saccades', 'word_boxes']
```

(Layers only exist for what the figure actually drew — turn the heatmap off and
there's no `heatmap` file.)

From the CLI, add `--separable-layers` to a static export:

```bash
scanpath-studio render --sample --separable-layers -o figure.svg
```

```text
Wrote figure.svg
Wrote 6 layer files to figure_layers/
```

This is how you build a composite the app doesn't draw for you — two readers'
`saccades` layers over one shared `labels` layer, say.

---

## 6. Animated figures (talks, supplements)

```python
anim = sps.animate_scanpath(words, fixations, pid, tid,
                            canvas_size=(2560, 1440), playback_speed=4.0)
sps.save_figure(anim, "replay.html")     # autoplays on load
```

Saved HTML **autoplays at the playback speed**; pass `autoplay=False` for a
replay that opens paused. For a rasterized version:

```python
from scanpath_studio.animation_export import export_animation

export_animation(anim, "replay.mp4")     # or replay.gif
```

GIF is encoded by Pillow; MP4 uses the ffmpeg binary bundled with the
`imageio[ffmpeg]` dependency. Both render frames through Kaleido, so both need
Chrome. The CLI's `--animate` writes **interactive HTML only** — for GIF/MP4 use
the Python API. Details in
[Export & troubleshooting](../export-troubleshooting.md).

---

## 7. Before you submit

- **Cross-check the numbers.** If the figure carries measures, verify them
  against your own pipeline. Pre-computed EyeLink `IA_*` values are passed
  through unchanged; anything else is computed by this app.
- **Say what the figure is.** Which participant, which trial, which measure
  drives the colour, and what a zero means (a skipped word, not a missing one).
- **Cite it.** The metadata lives in
  [`CITATION.cff`](https://github.com/lacclab/scanpath-studio/blob/main/CITATION.cff)
  and in the app's **About** panel; if you used the bundled demo, cite
  [OneStop](https://doi.org/10.1038/s41597-025-06272-2) too. See the
  [FAQ → Citing](../faq.md#citing).
- **Keep the recipe.** The 💾 **Save & restore** JSON (or the script on this
  page) reproduces the figure months later; a downloaded PNG doesn't.

---

## Next

- Do this for every trial → **[Run it headless from a script](run-it-headless.md)**
- Chrome / ffmpeg problems → **[Export & troubleshooting](../export-troubleshooting.md)**
- Why the text is that size → **[True-to-scale rendering](../rendering.md)**
