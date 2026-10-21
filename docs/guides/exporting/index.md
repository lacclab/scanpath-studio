---
description: "Export eye-tracking figures as PNG, SVG or animated replays, export many trials at once, and share a view as a link or as Python and CLI code."
---

# Export and share

Save a figure, export many trials at once, or reuse a view in the app or in code.

## In the app

| Goal | Where |
| --- | --- |
| Save the figure or replay on screen | :material/file_export: **Export** → **Current figure** |
| Export many trials and their tables | :material/file_export: **Export** → **Export bundle** |
| Share a view or copy its code | :material/share: **Share** → **Link** or **Code** |
| Reuse the figure settings | :material/palette: **My designs**, or :material/share: **Share** → **Settings file** |

In Simple mode, **Export** holds **Current figure** only; **Export bundle** is
in Advanced.

For step-by-step instructions, see the [export tutorials](../../tutorials/exporting-figures/index.md).

## Cite what you export { #cite }

Every file you export says how to cite Scanpath Studio in its own metadata:
the PNG's text chunks, the SVG's `<metadata>`, the PDF's document properties,
the HTML page's `<head>`, and the GIF's and MP4's comment. Nothing is drawn on
the figure.

- :material/format_quote: **Cite**, under each download and in
  :material/share: **Share** → **Code**, gives a one-line figure credit, the
  APA reference and BibTeX, and `.bib` and `.ris` files for Zotero, Mendeley or
  EndNote. For the bundled demo, OneStop or PoTeC, it cites the corpus too.
- An export bundle has a `CITATION.bib`, and its `README.md` a *Cite* section.
- **Figure & canvas** → **Credit** adds a small *Made with Scanpath Studio*
  line under the plot, for a figure shared without its caption. In code, pass
  `show_credit=True`, or `--credit` to `render`.
- In code, [`cite`][scanpath_studio.api.cite] and `scanpath-studio cite` print
  the citation.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../assets/workflows/share-link_poster.webp" data-autoplay
       aria-label="Copying a link that reopens the same trial and design">
  <source src="../../assets/workflows/share-link.mp4" type="video/mp4">
</video>

A link reopens the trial and its settings for anyone who has the same dataset.
[All controls → Under the plot](../scanpath-visualization/controls.md#under-the-plot)
says what the recipient needs.

## Reproduce a figure { #from-the-app-to-a-script }

Open **Share** → **Code** and copy the Python or CLI code. It carries the
figure's settings and your column mapping. For a dataset you imported, replace
the placeholder file paths with your own.
[Render in code](../scanpath-visualization/index.md#render-in-code) shows a minimal example.

For a PNG at print size, pass `width_mm` and `dpi` to `save_figure`, or
`--width-mm` and `--dpi` to `render`. To edit the layers in a vector editor,
save each layer to a separate file with `save_figure_layers` or
`render --separable-layers`. In the app's export bundle, this is
**Layers as separate files**.

## Batch export { #batch-pattern }

In the app, **Export bundle** → **Trials to include** picks the trials:
**This trial**, **All filtered trials**, **All trials of one participant**,
**All trials of one text** or **All trials, ignoring filters**. For a scripted
batch, loop over the trial list:

??? example "Python: one HTML figure per trial"

    ```python
    from pathlib import Path

    import scanpath_studio as sps

    words, fixations = sps.load_sample_data()
    out = Path("figures")
    out.mkdir(exist_ok=True)

    for pid, tid in sps.list_trials(words, fixations).itertuples(index=False):
        fig = sps.plot_scanpath(words, fixations, pid, tid)
        sps.save_figure(fig, out / f"{pid}_{tid}.html")
    ```

    Use the [data loaders](../loading-data/index.md#load-and-inspect-in-code)
    for your own files. The CLI's `render` writes one trial per run.

## Replay export { #replays-as-gif-or-mp4 }

With :material/movie: **Animate** on, **Export** → **Current figure** saves the
replay as HTML, GIF or MP4. The CLI's `render --animate` saves interactive HTML
only. For a GIF or MP4 in Python:

??? example "Python: save a GIF or MP4"

    ```python
    from pathlib import Path

    import scanpath_studio as sps
    from scanpath_studio.animation_export import export_animation

    words, fixations = sps.load_sample_data()
    replay = sps.animate_scanpath(words, fixations, "l37_1129", "l37_1129_2_1_1_Ele")
    Path("replay.mp4").write_bytes(export_animation(replay, fmt="mp4"))
    ```

    Use `fmt="gif"` and a `.gif` filename for GIF output.

[Export setup and troubleshooting](../../faq.md#export-fails) ·
[Python save options](../../api.md#save) · [CLI options](../../cli.md#common-tasks)
