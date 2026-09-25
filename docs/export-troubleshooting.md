# Export troubleshooting

## Figure formats

| Format | How | Needs Chrome? |
|--------|-----|---------------|
| **HTML** | `save_figure(fig, "x.html")` / `render -o x.html` | No — browser-free (`fig.to_html`) |
| **PNG / SVG / PDF** | `save_figure(fig, "x.png")` / `render -o x.png` | **Yes** — via Kaleido |
| **GIF / MP4** | `animation_export.export_animation(anim, fmt="mp4", frame_duration_ms=…)` → bytes (see [below](#mp4-gif)) | **Yes** (Kaleido) — ffmpeg is bundled |

## Kaleido needs Chrome, Chromium or Edge

Static image export (PNG/SVG/PDF) and rasterized animation (GIF/MP4) render
through [Kaleido](https://github.com/plotly/Kaleido) v1, which drives a headless
browser. It finds an installed Google Chrome, Chromium or Microsoft Edge by
itself, in the desktop app and in a `pip` install alike, so installing one of
them is enough. A `pip` install can instead download a copy for Kaleido, once:

```bash
plotly_get_chrome -y
```

(From Python: `import kaleido; kaleido.get_chrome_sync()`.) Without a browser,
use **HTML** export; the export panel says so when it finds none.

## MP4 / GIF

`export_animation` takes the replay figure and returns the encoded bytes; the
format and the per-frame duration are keyword-only:

```python
from pathlib import Path

import scanpath_studio as sps
from scanpath_studio.animation_export import export_animation
from scanpath_studio.plots import animation_autoplay_frame_duration

words, fixations = sps.load_sample_data()
anim = sps.animate_scanpath(words, fixations, "l37_1129", "l37_1129_2_1_1_Ele_r0")
clip = export_animation(
    anim,
    fmt="mp4",  # or "gif"
    frame_duration_ms=animation_autoplay_frame_duration(anim),  # keeps the speed
)
Path("replay.mp4").write_bytes(clip)
```

- **GIF** is encoded by Pillow; **MP4** uses the ffmpeg binary bundled by the
  `imageio[ffmpeg]` dependency — no system ffmpeg needed.
- If `export_animation` raises, Chrome is usually missing (see above).
- The CLI's `--animate` writes **interactive HTML** only; use the Python API for
  GIF/MP4.

## Common issues

??? question "“Ambiguous selection: N trials match” from `plot_scanpath`"
    The frames contain more than one `(participant, trial)` combo, so you must
    say which one: `plot_scanpath(words, fixations, participant, trial)`. Use
    [`list_trials`][scanpath_studio.api.list_trials] to see the options.

??? question "A column wasn't detected / mapped to the wrong field"
    Auto-detection matches common conventions case- and separator-insensitively.
    Override it with the app's **Column mapping** panel (🗂️ Data → ✏️ Edit
    dataset → *1 · Data tables & column mapping*), or pass
    `word_schema` / `fix_schema` to
    [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data].

??? question "The reading text looks too big / too small"
    Text is drawn true-to-scale from the word boxes and the **monitor
    resolution**. Set the real monitor size (🗂️ **Data → ✏️ Edit dataset →
    2 · Recording setup**, **📐 Figure & canvas → 🖥️ Screen & framing** in the
    visualization rail, or `canvas_size=(W, H)` in the API) — e.g.
    `(2560, 1440)` for OneStop.

