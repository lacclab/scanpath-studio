# Export and share

Save a figure, export many trials at once, or reuse a view in the app or in code.

## In the app

| Goal                                  | Where                                            |
| ------------------------------------- | ------------------------------------------------ |
| Save the figure or replay on screen   | **Export** → **Current figure**                  |
| Prepare a figure for a paper or slide | **Export** → **Prepare figure for export**       |
| Export many trials and their tables   | **Export** → **Export bundle**                   |
| Share a view or copy its code         | **Share** → **Link** or **Code**                 |
| Reuse the figure settings             | **My presets**, or **Share** → **Settings file** |

To export multiple trials, switch to Full and open **Export bundle**. Essentials offers **Current figure** for the figure or replay on screen.

For step-by-step instructions, see the [export tutorials](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/index.md).

## Prepare a paper figure or slide

Open **Scanpath → Export → Prepare figure for export**. The preview shows the current reading, comparison or replay still. For a corpus chart, open **Prepare figure for export** directly beneath the chart. Choose **Download PNG** for a slide or document, or switch the file format to SVG, PDF or TIFF.

- **Crop** lets you draw a rectangle, select a word span when words are available, or use the scanpath’s current zoom. Under **Label events**, pin a fixation or saccade and drag its label into position.
- **Caption and description** suggests a caption and alternative text. Edit them, download both as text, or include the caption below the artwork.
- For a replay, **Replay clip** lets you choose the interval, speed and poster frame. **Prepare MP4 and poster** produces a ZIP with the clip, poster and editable file. Rendering PDF or video in the app requires Chromium on the server.
- When a journal specifies dimensions, open **Print settings** to set the width, resolution or minimum text size. In Full mode on the Scanpath View, **Use this size for batch export** prints each bundle figure at the prepared artwork’s width and resolution; the crop, labels and caption stay with the prepared figure.

Under **Save or open**, save a copy on this device or download an editable file for a coauthor. The file includes the plotted data, tooltip fields and embedded images. Open it here, under **Data Management → Saved work → Saved figures**, or via **Share → Settings file**. A Share link opens the editor on the source view. An editable file also restores your crop, labels and caption. Older files containing several figures open with their saved layout.

## Reproduce a coauthor's results

The installed package includes a fictional three-reader study, its raw tables, recording setup, one tagged exclusion, figure settings and a cohort recipe. To work through it in an empty folder, copy the example and follow its README.

```
python -c "from importlib.resources import files; from shutil import copytree; copytree(files('scanpath_studio') / 'sample_data' / 'coauthor', 'canal-study')"
```

The commands recreate a figure and a two-word results table. A checksum from the original release lets the recipient verify the table byte for byte.

## Cite what you export

Files saved through **Export** include citation information in their metadata. To add a visible credit to the figure, use **Figure** → **Title & labels** → **Credit**.

- **Cite**, under each download and in **Share** → **Code**, gives a one-line figure credit, the APA reference and BibTeX, and `.bib` and `.ris` files for Zotero, Mendeley or EndNote. For the bundled demo, OneStop or PoTeC, it cites the corpus too.
- Each export bundle includes `CITATION.bib` and citation instructions in `README.md`.
- **Figure** → **Title & labels** → **Credit** adds a small *Made with Scanpath Studio* line under the plot, for a figure shared without its caption. In code, pass `show_credit=True`, or `--credit` to `render`.
- In code, cite and `scanpath-studio cite` print the citation.

\[!\[

\](../../assets/workflows/share-link_poster.webp)\](../../assets/workflows/share-link.mp4)

A link can find an imported dataset on the same computer after you rename it. On another computer, import the sender’s data under the name in the link. The link checks that the recording tables match, including those for a second imported dataset in a comparison. Older links can open without checking the tables. [All controls → Under the plot](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/#under-the-plot) says what the recipient needs.

## Reproduce a figure

Open **Share** → **Code** and copy the Python or CLI code. It includes the figure's settings and your column mapping. The compact code includes changes that affect this view. For example, a comparison uses each scanpath's own fixation color for its index numbers. Select **Show every option** to include the other accepted figure settings. For a dataset you imported, replace the placeholder file paths with your own. [Render in code](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#render-in-code) shows a minimal example.

For a PNG at print size, pass `width_mm` and `dpi` to `save_figure`, or `--width-mm` and `--dpi` to `render`. To edit the layers in a vector editor, save each layer to a separate file with `save_figure_layers` or `render --separable-layers`. In the app's export bundle, this is **Layers as separate files**.

## Batch export

In the app, **Export bundle** → **Trials to include** picks the trials: **This trial**, **All filtered trials**, **All trials of one participant**, **All trials of one text** or **All trials, ignoring filters**. Open **Preview bundle contents** to see the selected readings, their filenames and the columns in their tables. A word-measures CSV can contain the original stimulus words even when the figure masks them. When you select specific screens, the bundle includes notes on those screens and their parent trials.

When you export all screens, rows with no Screen ID are included once in the trial’s tables. Selecting specific screens includes only rows assigned to those screens. A screen with raw gaze alone has its own sample table.

If a figure fails, the download includes the files that succeeded. With the same data and settings still open, choose **Retry failed figure files**. The app retries each missing format or layer and keeps the successful files. If it could not split a figure into layers, it tries that step again. Check `index.csv` for any files that still failed. Stopping a retry leaves the previous download available.

CSV bundles include `columns.json` and an editable `read_csv.R`. In R, set the working directory to the extracted bundle and run `source("read_csv.R")` with the jsonlite package installed. The example preserves reader IDs such as `01` and `1` as text. A blank measurement becomes `NA` and zero stays zero.

For a scripted batch, loop over the trial list.

Python: one HTML figure per trial

```
from pathlib import Path

import scanpath_studio as sps

words, fixations = sps.load_sample_data()
out = Path("figures")
out.mkdir(exist_ok=True)

for pid, tid in sps.list_trials(words, fixations).itertuples(index=False):
    # Each demo reading has several screens; this saves its paragraph.
    fig = sps.plot_scanpath(words, fixations, pid, tid, screen="Paragraph")
    sps.save_figure(fig, out / f"{pid}_{tid}.html")
```

Use the [data loaders](https://lacclab.github.io/scanpath-studio/guides/loading-data/#load-and-inspect-in-code) for your own files. The CLI's `render` writes one trial per run.

## Replay export

With **Animation** selected, **Export** → **Current figure** saves the replay as HTML, GIF or MP4. In a saved HTML replay, **Previous fixation** and **Next fixation** move to individual onsets and show the fixation’s duration and assigned word when available. The time slider scrubs through the whole reading. Each frame of a GIF or MP4 shows the state reached at that frame’s start, and the last frame shows the complete scanpath. With a low frame cap, a fixation that begins between two frames first shows in the later one.

The CLI’s `render --animate` saves interactive HTML. For a GIF or MP4 in Python:

Python: save a GIF or MP4

```
from pathlib import Path

import scanpath_studio as sps
from scanpath_studio.animation_export import export_animation

words, fixations = sps.load_sample_data()
replay = sps.animate_scanpath(
    words, fixations, "l37_273", "l37_273_2_1_1_Ele", screen="Paragraph"
)
Path("replay.mp4").write_bytes(export_animation(replay, fmt="mp4"))
```

Use `fmt="gif"` and a `.gif` filename for GIF output.

[Export setup and troubleshooting](https://lacclab.github.io/scanpath-studio/faq/#export-fails) · [Python save options](https://lacclab.github.io/scanpath-studio/api/#save) · [CLI options](https://lacclab.github.io/scanpath-studio/cli/#common-tasks)

## Proof two manuscript panels

In **Compare**, choose two readings with the same screen dimensions and a side-by-side or stacked layout. In **Export → Current figure → Manuscript panel proof**, enter the total print width. The proof shows the resulting label sizes in points and the numeric color limits shared by the two panels. Use the Fixations or Heatmap controls to choose your own limits.

**Prepare manuscript SVG** provides the lettered vector panels at that physical width. **Save panel settings** preserves their order, styles, width and selected limits. Open the settings file in **Share → File**, replace one reading and prepare the revised SVG.
