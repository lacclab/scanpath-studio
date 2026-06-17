# Export & troubleshooting

## Figure formats

| Format | How | Needs Chrome? |
|--------|-----|---------------|
| **HTML** | `save_figure(fig, "x.html")` / `render -o x.html` | No — browser-free (`fig.to_html`) |
| **PNG / SVG / PDF** | `save_figure(fig, "x.png")` / `render -o x.png` | **Yes** — via Kaleido |
| **GIF / MP4** | `animation_export.export_animation(anim, "x.mp4")` | **Yes** (Kaleido) — ffmpeg is bundled |

## Kaleido needs a Chrome/Chromium binary

Static image export (PNG/SVG/PDF) and rasterized animation (GIF/MP4) render
through [Kaleido](https://github.com/plotly/Kaleido) v1, which drives a headless
Chrome. `pip install` does **not** install Chrome — run this once:

```bash
plotly_get_chrome -y
```

On **Streamlit Community Cloud** the repo-root `packages.txt` installs
`chromium` automatically. If Chrome is unavailable, fall back to **HTML** export
(it's browser-free).

## MP4 / GIF

- **GIF** is encoded by Pillow; **MP4** uses the ffmpeg binary bundled by the
  `imageio[ffmpeg]` dependency — no system ffmpeg needed.
- If `export_animation` raises, you most likely installed `imageio` without the
  `[ffmpeg]` extra, or Chrome is missing for the per-frame render.
- The CLI's `--animate` writes **interactive HTML** only; use the Python API for
  GIF/MP4.

## Common issues

??? question "“Ambiguous selection: N trials match” from `plot_scanpath`"
    The frames contain more than one `(participant, trial)` combo, so you must
    say which one: `plot_scanpath(words, fixations, participant, trial)`. Use
    [`list_trials`][scanpath_studio.api.list_trials] to see the options.

??? question "A column wasn't detected / mapped to the wrong field"
    Auto-detection matches common conventions case- and separator-insensitively.
    Override it with the app's **Column mapping** panel, or pass
    `word_schema` / `fix_schema` to
    [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data].

??? question "The reading text looks too big / too small"
    Text is drawn true-to-scale from the word boxes and the **monitor
    resolution**. Set the real monitor size (Experimental Setup in the app, or
    `canvas_size=(W, H)` in the API) — e.g. `(2560, 1440)` for OneStop.

??? question "OneStop server data"
    Pointing the app at a full OneStop export uses `$ONESTOP_DATA_DIR`; see
    [AGENTS.md](https://github.com/lacclab/scanpath-studio/blob/main/AGENTS.md)
    for the sharding/loader details.
