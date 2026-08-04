# True-to-scale rendering

Scanpath Studio reproduces the experiment's stimulus **true to scale** — the word
boxes, fixations, and reading text keep the same physical proportions the reader
actually saw, at any display size. This page explains the model so you can reason
about font sizes, the px-vs-pt question, and why the spatial plot takes a special
render path. It's a reference for contributors and power users; nothing here is
required for day-to-day use.

## Data space vs. screen space

Everything the eye-tracker recorded lives in **monitor pixels** — the *data
space*. A word's bounding box, a fixation's `(x, y)`, the stimulus image: all are
positioned in the same coordinate system the experiment screen used (e.g. a
1920×1080 monitor).

The on-screen plot is a separate **screen space**. The figure is drawn at a fixed,
equal-aspect size (Plotly `scaleratio=1`, so one data unit is the same number of
screen pixels on both axes), capped to a research-display-friendly box
(`plots._DISPLAY_MAX_WIDTH` / `_DISPLAY_MAX_HEIGHT`), then the whole block is
CSS-scaled uniformly to fill the column. The bridge between the two spaces is a
single number:

```
display_scale = screen pixels per data unit
              = min(fitted_w / x_span, fitted_h / y_span)   # plots._display_scale
```

Because the aspect ratio is locked, `x` and `y` share this scale; the `min` keeps
rounding from ever pushing text or markers past their boxes.

## Sizing the reading text

The experiment's font is a fixed size in monitor pixels, so to stay true-to-scale
the label font is computed in **data pixels** and multiplied by `display_scale`
into screen pixels (`plots._word_label_font_px`). Two modes feed the data-pixel
size:

- **Scale text to boxes** (default). One line of text is budgeted to fill
  `1 / line_spacing` of the **line pitch** — the median line-to-line distance
  measured from the data (`plots._line_pitch`), *not* the raw box height. The two
  differ for corpora whose AOI boxes hug the glyph (e.g. MultiplEYE): there the
  line slot is much taller than a box, and the pitch is the right budget. For
  OneStop the boxes tile the lines (pitch == height) and the default
  `line_spacing = 3` (one blank line above and below) reduces to the familiar
  `height / 3`. The size is then **capped so the longest word still fits its box
  width** (`plots._width_fit_font`); the smaller of the height- and width-fits
  wins, so text never collides or overflows.

- **Manual font**. When box geometry is missing or you turn scaling off, the font
  control's value is treated as the real monitor font size and scaled the same
  way.

### Script-aware width fitting

Word boxes hug their text, so a box's width equals the sum of its glyph advances.
`plots._width_fit_font` recovers the em (≈ the font size) as `box_width / Σ
advances`, where each glyph advances **1 em** for full-width CJK and a smaller
`latin_advance` em for half-width Latin. Doing this per word — not with one global
aspect — keeps a CJK word boxed next to a half-width Latin URL from being shrunk
to the narrow run. For an all-Latin corpus it reduces exactly to
`(box_width / n_chars) / aspect`.

### Datasets that ship their real typeface

Inferring the font from geometry is a good default, but a dataset that knows its
own typography can hand it over directly. MultiplEYE reads `FONT_SIZE` + `FONT`
from the stimulus config and stamps `stimulus_font_px` / `stimulus_font_family`
onto the frames; the app then snaps the font controls to the exact size and a
CJK-capable family (and turns scale-to-boxes off) on a source switch, so the
labels match the stimulus precisely rather than relying on inference.

## Pixels, not points

!!! warning "Font-size controls are in pixels (px), not points (pt)"
    Every font-size control in the app — the base label size, order-number size,
    colour-bar tick size — is in **pixels**. Stimulus typography, however, is
    usually specified in **points**. The two are not interchangeable: a point is a
    physical unit (1 pt = 1/72 inch), a pixel is a screen unit, and the conversion
    depends on the display's DPI:

    ```
    px = pt × DPI / 72          pt = px × 72 / DPI
    ```

    So "18 pt" is only "18 px" on a 72-DPI display; on a 96-DPI monitor it is
    24 px. If you're trying to reproduce an original stimulus font exactly, convert
    through the experiment's DPI — or, better, use a dataset that stamps its real
    `stimulus_font_px` (see above) and let the app snap to it. Folding the
    experimental-setup values (screen resolution, viewing distance, DPI, stimulus
    font pt) into the display settings so this conversion is automatic is tracked
    as a roadmap item.

## Why the spatial plot needs a special render path

The true-to-scale text only holds if the figure is embedded at its **exact pixel
size**. Rendering the spatial plots with `st.plotly_chart` pins the chart *width*
to the column while keeping the layout *height*, which re-lays-out Plotly to an
unknown scale and leaves the px-sized word labels mismatched to the boxes. So the
single-trial, animation, and comparison plots all go through
`tabs._render_true_scale_chart`, which embeds the figure's own HTML at its exact
size and CSS-scales the whole block uniformly to the column width. Static image
export bumps the raster `scale` to stay crisp; SVG/PDF are vector and need no bump.

If you add a new spatial figure, keep it on `_render_true_scale_chart` — never
`st.plotly_chart` — or the reading text will drift from the boxes.

## Duration mass and illustration disclosure

The **Duration mass** heatmap spreads each fixation's duration over nearby
character centres with a Gaussian kernel. Its sigma is expressed in characters,
so the setting remains meaningful across display resolutions and fonts. It uses
the same linear/log normalization and colour controls as the other heatmaps.

Geometry-changing views—snapped fixations, arced saccades, drift correction,
discarded/subset paths, synthetic data, or a hand-authored scanpath—can be
marked **Illustration** automatically. The annotation is part of the Plotly
figure and export metadata, so it survives PNG/SVG and layered export. Use the
manual Show/Hide override only when the publication context already supplies
an equivalent disclosure.
