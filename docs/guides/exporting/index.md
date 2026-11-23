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

To export multiple trials, switch to Full and open **Export bundle**.
Essentials offers **Current figure** for the figure or replay on screen.

For step-by-step instructions, see the [export tutorials](../../tutorials/exporting-figures/index.md).

## Reproduce a coauthor's results

The installed package includes a fictional three-reader study, its raw tables,
recording setup, one tagged exclusion, figure settings and a cohort recipe.
To work through it in an empty folder, copy the example and follow its README.

```sh
python -c "from importlib.resources import files; from shutil import copytree; copytree(files('scanpath_studio') / 'sample_data' / 'coauthor', 'canal-study')"
```

The commands recreate a figure and a two-word results table. A checksum from
the original release lets the recipient verify the table byte for byte.

## Cite what you export { #cite }

Files saved through **Export** include citation information in their metadata.
To add a visible credit to the figure, use **Figure & canvas** → **Credit**.

- :material/format_quote: **Cite**, under each download and in
  :material/share: **Share** → **Code**, gives a one-line figure credit, the
  APA reference and BibTeX, and `.bib` and `.ris` files for Zotero, Mendeley or
  EndNote. For the bundled demo, OneStop or PoTeC, it cites the corpus too.
- Each export bundle includes `CITATION.bib` and citation instructions in `README.md`.
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

A link can find an imported dataset on the same computer after you rename it.
On another computer, import the sender’s data under the name in the link.
The link checks that the recording tables match, including those for a second
imported dataset in a comparison. Older links can open without checking the tables.
[All controls → Under the plot](../scanpath-visualization/controls.md#under-the-plot)
says what the recipient needs.

## Reproduce a figure { #from-the-app-to-a-script }

Open **Share** → **Code** and copy the Python or CLI code. It includes the
figure's settings and your column mapping. The compact code includes changes
that affect this view. For example, a comparison uses each scanpath's own
fixation color for its index numbers. Select **Show every option** to include
the other accepted figure settings. For a dataset you imported, replace
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
**All trials of one text** or **All trials, ignoring filters**. Open **Preview
bundle contents** to see the selected readings, their filenames and the columns
in their tables. A word-measures CSV can contain the original stimulus words
even when the figure masks them. When you select specific screens, the bundle
includes notes on those screens and their parent trials.

When you export all screens, rows with no Screen ID are included once in the
trial’s tables. Selecting specific screens includes only rows assigned to those
screens. A screen with raw gaze alone has its own sample table.

If a figure fails, the download includes the files that succeeded. With the same data
and settings still open, choose **Retry failed figure files**. The app retries each
missing format or layer and keeps the successful files. If it could not split a figure
into layers, it tries that step again. Check `index.csv` for any files that still failed.
Stopping a retry leaves the previous download available.

CSV bundles include `columns.json` and an editable `read_csv.R`. In R, set
the working directory to the extracted bundle and run `source("read_csv.R")`
with the jsonlite package installed. The example preserves reader IDs such as
`01` and `1` as text. A blank measurement becomes `NA` and zero stays zero.

For a scripted batch, loop over the trial list.

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
replay as HTML, GIF or MP4. In a saved HTML replay, **Previous fixation** and
**Next fixation** move to individual onsets and show the fixation’s duration and
assigned word when available. The time slider scrubs through the whole reading.
A GIF or MP4 with a low frame cap shows the state reached at each frame’s start.
A fixation after the last frame starts can be absent from the clip.

The CLI’s `render --animate` saves interactive HTML. For a GIF or MP4 in Python:

??? example "Python: save a GIF or MP4"

    ```python
    from pathlib import Path

    import scanpath_studio as sps
    from scanpath_studio.animation_export import export_animation

    words, fixations = sps.load_sample_data()
    replay = sps.animate_scanpath(words, fixations, "l37_273", "l37_273_2_1_1_Ele")
    Path("replay.mp4").write_bytes(export_animation(replay, fmt="mp4"))
    ```

    Use `fmt="gif"` and a `.gif` filename for GIF output.

[Export setup and troubleshooting](../../faq.md#export-fails) ·
[Python save options](../../api.md#save) · [CLI options](../../cli.md#common-tasks)
## Proof two manuscript panels

In **Compare**, choose two readings with the same screen dimensions and a
side-by-side or stacked layout. In **Export → Current figure → Manuscript
panel proof**, enter the total print width. The proof shows the resulting
label sizes in points and the numeric color limits shared by the two panels.
Use the Fixations or Heatmap controls to choose your own limits.

**Prepare manuscript SVG** provides the lettered vector panels at that
physical width. **Save panel settings** preserves their order, styles, width
and selected limits. Open the settings file in **Share → File**, replace
one reading and prepare the revised SVG.
