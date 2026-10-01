# Outputs and sharing

## Export

Open the **Export** subtab in the Scanpath view.

- **Current figure** downloads what is on screen: PNG, SVG, PDF or HTML, or the replay as HTML, GIF or MP4.
- **Export bundle** writes figures and tables for this trial, the filtered trials, or the whole dataset, plus a `plot_config.json` to recreate them. Options add separable layers for a vector editor, raw gaze, annotations, and more tables. Tables are written per trial, or combined into one file each. Word tables carry the reading measures your data brought; the export computes none.

HTML, and the current figure's PNG and SVG, always work. PDF, GIF, MP4 and the bundle's images need Chrome, Chromium or Edge installed ([FAQ](https://lacclab.github.io/scanpath-studio/faq/#export-fails)).

## Share

The **Share** subtab passes a view on in three ways:

- **Link** — a URL with the dataset choice, trial and every figure setting. It never contains your uploaded data: the recipient must load the same dataset. (A scanpath created by hand is the exception; its link carries it.)
- **Code** — Python or a CLI command that reproduces the figure.
- **File** — the figure's settings as a file, to restore later.

## Back up your work

| What                               | Where                           |
| ---------------------------------- | ------------------------------- |
| figure settings                    | **Share → File**                |
| favorites, tags and notes          | **Data → Annotations → Export** |
| column mapping and recording setup | **Edit dataset → Save setup**   |
| saved figure designs               | **My designs → Export**         |

None of these files contain your data rows; load the same data before restoring one. Notes may contain participant information, so check them before sharing.

On a local or desktop install, the app also keeps a recovery copy of your datasets and work, restored after a refresh or restart.

For scripted output, see [Automation](https://lacclab.github.io/scanpath-studio/automation/index.md).
