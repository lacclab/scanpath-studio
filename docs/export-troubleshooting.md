# Export & troubleshooting

## Figure formats

Every static format renders natively with matplotlib — fully in-process, with no
headless browser.

| Format | How | Needs anything extra? |
|--------|-----|-----------------------|
| **HTML** | `save_figure(fig, "x.html")` / `render -o x.html` | No — a self-contained SVG page (the animation's HTML is an interactive matplotlib player) |
| **PNG / SVG / PDF** | `save_figure(fig, "x.png")` / `render -o x.png` | No — matplotlib `savefig` |
| **GIF** | `animation_export.export_animation(anim, "x.gif")` | No — encoded by Pillow |
| **MP4** | `animation_export.export_animation(anim, "x.mp4")` | ffmpeg, bundled via the `imageio[ffmpeg]` extra |

## MP4 export

MP4 is the only format with an external piece: it encodes through an ffmpeg
binary, which ships bundled with the `imageio[ffmpeg]` dependency — no system
ffmpeg needed. If `export_animation` raises while writing MP4, you most likely
installed `imageio` without the `[ffmpeg]` extra. Fall back to **GIF** or the
interactive **HTML** player, both of which need nothing extra.

The CLI's `--animate` writes the interactive **HTML** player only; use the Python
API (`animation_export.export_animation`) for GIF/MP4.

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
