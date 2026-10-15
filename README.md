# Scanpath Studio

[![PyPI](https://img.shields.io/pypi/v/scanpath-studio.svg)](https://pypi.org/project/scanpath-studio/)
[![Python versions](https://img.shields.io/pypi/pyversions/scanpath-studio.svg)](https://pypi.org/project/scanpath-studio/)
[![Live demo](https://img.shields.io/badge/Live_demo-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://scanpath-studio.streamlit.app)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue)](https://lacclab.github.io/scanpath-studio/)
[![CI](https://github.com/lacclab/scanpath-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/lacclab/scanpath-studio/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Flacclab.github.io%2Fscanpath-studio%2Fcoverage%2Fbadge.json)](https://lacclab.github.io/scanpath-studio/coverage/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/lacclab/scanpath-studio/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22933884.svg)](https://doi.org/10.5281/zenodo.22933884)

**Scanpath Studio shows you how people read.** Load eye-tracking data from reading studies and watch each trial unfold over the text, exactly where it sat on the screen — then compare participants, analyze a corpus, and export figures ready for a paper.

![Using Scanpath Studio: stepping through trials, a heatmap, a replay, a two-participant comparison and Corpus Analysis](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/docs/assets/app_demo.gif)

## Install

- **As a desktop app** — recommended, and the easiest way to work with your own data. It updates itself from the app's About menu:
  [Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64-setup.exe)
  [macOS (Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg)
  [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz)
- **With pip** (Python 3.11–3.14):

  ```bash
  pip install scanpath-studio
  scanpath-studio      # opens the app in your browser
  ```

- **In the browser**, to try it on the bundled demo data: the live demo at
  <https://scanpath-studio.streamlit.app>.

The desktop and pip installs keep your data on your own machine, handle large datasets, and download the public corpora (PoTeC, OneStop) in one click. The hosted demo runs on Streamlit Community Cloud, with limited memory and no corpus downloads.

## Your data

Bring any of these tables, in CSV, TSV, Parquet, Feather, Excel or a `.zip` of them:

| Table | What it holds |
| --- | --- |
| **Fixations**, e.g. EyeLink's Fixation Report | One row per fixation: trial ID, duration, and x/y or a word ID |
| **Words** (interest areas), e.g. EyeLink's Interest Area Report | One box per word, as shown on screen, with any reading measures and word features |
| **Raw gaze** | The gaze samples, drawn under the fixations — or on their own |
| **Participants** | Metadata, one row per participant: language, age, group… |
| **Trials** | Metadata, one row per trial or per reading: condition, question… |
| **Texts** | Metadata, one row per text: difficulty, genre… |

A dataset needs at least one of the first three. Metadata columns work like
fields in your data: filters, chips, sorting and export. Columns are detected from common EyeLink, Tobii, Gazepoint, SMI and Pupil Labs names, and you can correct any guess. See [Loading public and own data](https://lacclab.github.io/scanpath-studio/guides/loading-data/) and the [data format](https://lacclab.github.io/scanpath-studio/data-format/).

<p align="center">
  <img src="https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/workflows/add-your-data.gif" alt="Adding a dataset from EyeLink fixation and interest-area reports"><br>
  <sub><b>Add your own data:</b> EyeLink's fixation and interest-area reports, their columns detected for you</sub>
</p>

## What you can do

### See the reading

Fixations, saccades, heatmaps and raw gaze over the text at its true on-screen position, with fixations colored by any column.

<p align="center">
  <img src="https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/workflows/plot-controls.gif" alt="Coloring regressions apart and adding word boxes, the reading order and another palette"><br>
  <sub><b>Style the plot:</b> regressions in their own color, word boxes, the reading order, a palette</sub>
</p>

### Replay it

Play a trial back in real time or faster, and export it as HTML, GIF or MP4.

<p align="center">
  <img src="https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/workflows/replay.gif" alt="Replaying a reading, sped up to four times real time"><br>
  <sub><b>Replay the reading</b> fixation by fixation, here at ×4</sub>
</p>

### Compare participants

Overlay two trials or place them side by side — even from two different datasets.

<p align="center">
  <img src="https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/workflows/compare.gif" alt="Two readers of one text side by side, stepping through the texts together"><br>
  <sub><b>Compare two readers</b> of a text side by side, stepping through the texts together</sub>
</p>

### Analyze a corpus

Per text, participant or group. Corpus Analysis uses the reading measures in your data (such as EyeLink's `IA_*` columns) and does not compute its own; each is defined in the [computation register](https://lacclab.github.io/scanpath-studio/computations/).

<p align="center">
  <img src="https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/workflows/corpus-analysis.gif" alt="Corpus Analysis: a measure on the stimulus, against surprisal, and between two groups"><br>
  <sub><b>Corpus Analysis:</b> a measure on the stimulus, against surprisal, and between two groups</sub>
</p>

### Find and tag trials

Narrow the trials by condition, participant or your own tags, and star the ones
worth coming back to.

<p align="center">
  <img src="https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/workflows/trial-filtering.gif" alt="Narrowing the trials by condition and participant"><br>
  <sub><b>Find trials:</b> narrow them by condition and participant, then step through what is left</sub>
</p>

### Export and share

Export one figure or a zip for every trial, and share a link that reopens the exact view.

<p align="center">
  <img src="https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/workflows/export-figure.gif" alt="Exporting the figure 180 mm wide at 300 dpi"><br>
  <sub><b>Export a figure for a paper,</b> 180 mm wide at 300 dpi</sub>
</p>

More recordings are in the [gallery](https://lacclab.github.io/scanpath-studio/gallery/#the-app-at-work).
The app has three views: 🗺️ **Scanpath** for one trial at a time, 📊 **Corpus Analysis** for the whole dataset, and 🗂️ **Data Management** for loading and configuring datasets. The [feature guides](https://lacclab.github.io/scanpath-studio/guides/) walk through each one.

## Command line & Python API

Everything the app draws is also available headless — same pipeline, same figure. These run as-is on the bundled demo:

```bash
scanpath-studio render --sample --list-trials          # the demo's trials
scanpath-studio render --sample -o scanpath.html       # one trial, interactive HTML
scanpath-studio render --sample --animate -o replay.html
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 -o compare.html
```

```python
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
print(sps.list_trials(words, fixations).head())
fig = sps.plot_scanpath(words, fixations, "l37_1129", "l37_1129_2_1_1_Ele_r0")
sps.save_figure(fig, "scanpath.html")
```

For your own files, pass `--words ia.csv --fixations fix.csv` to `render`, or use `sps.load_scanpath_data("ia.csv", "fix.csv")`; add raw gaze with `--raw-gaze` (`sps.load_raw_gaze`) and metadata with `--participant-metadata`, `--trial-metadata` and `--text-metadata` (`sps.load_participant_metadata` and its trial and text siblings). HTML output needs nothing else; PNG, SVG and PDF (and GIF/MP4 replays) go through Kaleido, which needs Chrome, Chromium or Edge, or run `plotly_get_chrome -y` once. The [CLI reference](https://lacclab.github.io/scanpath-studio/cli/) and the [Python API reference](https://lacclab.github.io/scanpath-studio/api/) list every flag and parameter.

## Where next

The full documentation is at **<https://lacclab.github.io/scanpath-studio/>**:

- [Install](https://lacclab.github.io/scanpath-studio/install/): install, launch and a first trial
- [Tutorials](https://lacclab.github.io/scanpath-studio/tutorials/): task walk-throughs, from checking a pilot to a figure for a paper
- [Feature guides](https://lacclab.github.io/scanpath-studio/guides/): every view and control
- [Loading public and own data](https://lacclab.github.io/scanpath-studio/guides/loading-data/): what the loader accepts and how to map it
- [CLI](https://lacclab.github.io/scanpath-studio/cli/) and [Python API](https://lacclab.github.io/scanpath-studio/api/): scripting and batch rendering
- [Plot gallery](https://lacclab.github.io/scanpath-studio/gallery/): the figures it draws, each with the code that makes it
- [Computation register](https://lacclab.github.io/scanpath-studio/computations/): how each measure is derived
- [FAQ](https://lacclab.github.io/scanpath-studio/faq/) 
- [Cite](https://lacclab.github.io/scanpath-studio/cite/)

## Contributing

```bash
git clone https://github.com/lacclab/scanpath-studio.git
cd scanpath-studio
pip install -e ".[test,lint]"     # or: uv sync --extra test --extra lint
streamlit run streamlit_app.py --server.address 127.0.0.1
pytest -n auto
```

[CONTRIBUTING.md](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md) covers setup, the checks that gate CI, and how work is tracked in [GitHub Issues](https://github.com/lacclab/scanpath-studio/issues); [AGENTS.md](https://github.com/lacclab/scanpath-studio/blob/main/AGENTS.md) is the architectural map. To preview the docs site locally, run `pip install -e ".[docs]"` and then `mkdocs serve`.

Taking part means following the [Code of Conduct](https://github.com/lacclab/scanpath-studio/blob/main/CODE_OF_CONDUCT.md).

## Citation

A paper is in preparation. Until then, please cite the software by its DOI.
In a methods section you could write:

> Scanpaths were visualized with Scanpath Studio (Shubi et al., 2026).

> Shubi, O., Gruteke Klein, K., Grossman, M., Lion, E., Jakobi, D. N., Reich,
> D. R., Jäger, L., & Berzak, Y. (2026). *Scanpath Studio* [Computer software].
> Zenodo. <https://doi.org/10.5281/zenodo.22933884>

```bibtex
@software{shubi2026scanpathstudio,
  title     = {Scanpath Studio},
  author    = {Shubi, Omer and Gruteke Klein, Keren and Grossman, Maya
               and Lion, Ella and Jakobi, Deborah N. and Reich, David R.
               and J{\"a}ger, Lena and Berzak, Yevgeni},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22933884},
  url       = {https://doi.org/10.5281/zenodo.22933884},
}
```

Add the version you used (`scanpath-studio version` prints it), e.g. "(Version 0.38.0)". 

If you use the bundled demo, a subset of [OneStop Eye Movements][onestop-corpus], please also cite:

```bibtex
@article{berzak2025onestop,
  title     = {{OneStop}: A 360-Participant {E}nglish Eye Tracking Dataset
               with Different Reading Regimes},
  author    = {Berzak, Yevgeni and Malmaud, Jonathan and Shubi, Omer
               and Meiri, Yoav and Lion, Ella and Levy, Roger},
  journal   = {Scientific Data},
  year      = {2025},
  publisher = {Nature Publishing Group},
  doi       = {10.1038/s41597-025-06272-2},
  url       = {https://www.nature.com/articles/s41597-025-06272-2},
}
```

[onestop-corpus]: https://github.com/lacclab/OneStop-Eye-Movements

## AI-assisted development

Scanpath Studio was developed with AI assistance. As with any research
software, cross-check its results before relying on them in published work. Found a
bug, or have a feature request?
[Open an issue](https://github.com/lacclab/scanpath-studio/issues).
