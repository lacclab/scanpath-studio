# Scanpath Studio


[![PyPI](https://img.shields.io/pypi/v/scanpath-studio.svg)](https://pypi.org/project/scanpath-studio/)
[![Python versions](https://img.shields.io/pypi/pyversions/scanpath-studio.svg)](https://pypi.org/project/scanpath-studio/)
[![Live demo](https://img.shields.io/badge/Live_demo-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://scanpath-studio.streamlit.app)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue)](https://lacclab.github.io/scanpath-studio/)
[![CI](https://github.com/lacclab/scanpath-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/lacclab/scanpath-studio/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Flacclab.github.io%2Fscanpath-studio%2Fcoverage%2Fbadge.json)](https://lacclab.github.io/scanpath-studio/coverage/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/lacclab/scanpath-studio/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22933884.svg)](https://doi.org/10.5281/zenodo.22933884)

**Scanpath Studio shows you how people read.** Load eye-tracking-while-reading
data and watch each reading unfold over the text, exactly where it sat on the
screen — then compare readers, analyse a corpus, and export figures ready for a
paper.

![Using Scanpath Studio: stepping through trials, a heatmap, a replay, a two-reader comparison and Corpus Analysis](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/docs/assets/app_demo.gif)

## Get started

- **In the browser:** the live demo at
  <https://scanpath-studio.streamlit.app>.
- **With pip** (Python 3.11–3.14):

  ```bash
  pip install scanpath-studio
  scanpath-studio      # opens the app in your browser
  ```

- **As a desktop app:** [Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip) ·
  [macOS (Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.tar.gz) ·
  [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz).

The pip and desktop installs keep your data on your own machine; the hosted demo
runs on Streamlit Community Cloud.

## What you can do

- **See the reading:** fixations, saccades, heatmaps and raw gaze over the text
  at its true on-screen position, with fixations colored by any column.
- **Replay it** in real time or faster, and export it as HTML, GIF or MP4.
- **Compare readers:** overlay two trials or place them side by side — even
  from two different datasets.
- **Analyse a corpus** per text, sentence, reader or group, with every measure
  documented in the
  [computation register](https://lacclab.github.io/scanpath-studio/computations/).
- **Triage, export and share:** tag and filter trials, export one figure or a
  zip for every trial, and share a link that reopens the exact view.

| | |
|:---:|:---:|
| ![A reading scanpath replayed fixation by fixation](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/scanpath_animation.gif) | ![Two readers of the same paragraph, overlaid on one canvas](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/demo_dual_scanpath.png) |
| A reading, replayed fixation by fixation | Two readers of one paragraph, overlaid ([animated](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/docs/assets/demo_dual_scanpath.gif)) |

The app has three views: 🗺️ **Scanpath** for one trial at a time, 📊 **Corpus
Analysis** for the whole dataset, and 🗂️ **Data** for loading and configuring
datasets. The [feature guides](https://lacclab.github.io/scanpath-studio/guides/)
walk through each one.

## Your data

Load word, fixation and raw-gaze tables in CSV, Parquet, Excel or another
common format. Scanpath Studio adapts to how your study was recorded, so there
is rarely anything to reformat first — see
[Bring your own data](https://lacclab.github.io/scanpath-studio/bring-your-own-data/).

## Command line & Python API

Everything the app draws is also available headless — same pipeline, same
figure. These run as-is on the bundled demo:

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
measures = sps.compute_word_metrics(words, fixations)  # FFD, FPRT, RPD, TFD, …
```

For your own files, pass `--words ia.csv --fixations fix.csv` to `render`, or
use `sps.load_scanpath_data("ia.csv", "fix.csv")`. HTML output needs nothing
else; PNG, SVG, PDF, GIF and MP4 go through Kaleido, which needs Chrome once:
`plotly_get_chrome -y`. The
[CLI reference](https://lacclab.github.io/scanpath-studio/cli/) and the
[Python API reference](https://lacclab.github.io/scanpath-studio/api/) list
every flag and parameter.

## Where next

The full documentation is at **<https://lacclab.github.io/scanpath-studio/>**:

- [Getting started](https://lacclab.github.io/scanpath-studio/getting-started/): install, launch and a first trial
- [Tutorials](https://lacclab.github.io/scanpath-studio/tutorials/): task walk-throughs, from checking a pilot to a figure for a paper
- [Feature guides](https://lacclab.github.io/scanpath-studio/guides/): every view and control
- [Bring your own data](https://lacclab.github.io/scanpath-studio/bring-your-own-data/): what the loader accepts and how to map it
- [CLI](https://lacclab.github.io/scanpath-studio/cli/) and [Python API](https://lacclab.github.io/scanpath-studio/api/): scripting and batch rendering
- [Computation register](https://lacclab.github.io/scanpath-studio/computations/): how each measure is derived
- [FAQ](https://lacclab.github.io/scanpath-studio/faq/)

## Contributing

```bash
git clone https://github.com/lacclab/scanpath-studio.git
cd scanpath-studio
pip install -e ".[test]"          # or: uv sync --extra test --extra lint
streamlit run streamlit_app.py --server.address 127.0.0.1
pytest -n auto
```

[CONTRIBUTING.md](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md)
covers setup, the checks that gate CI, and how work is tracked in
[GitHub Issues](https://github.com/lacclab/scanpath-studio/issues);
[AGENTS.md](https://github.com/lacclab/scanpath-studio/blob/main/AGENTS.md) is
the architectural map. To preview the docs site locally, run
`pip install -e ".[docs]"` and then `mkdocs serve`.

## Citation

A paper is in preparation. Until then, cite the software by its DOI,
[10.5281/zenodo.22933884](https://doi.org/10.5281/zenodo.22933884) (GitHub's
**Cite this repository** button formats it as APA or BibTeX). If you use the
bundled demo, a subset of [OneStop Eye Movements][onestop-corpus], please also
cite:

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

## AI-assisted software

Scanpath Studio was built with AI assistance. Cross-check results before
publishing. If something looks wrong — or if you have a feature request or
suggestion — [report it](https://github.com/lacclab/scanpath-studio/issues).
