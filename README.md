# Scanpath Studio


[![PyPI](https://img.shields.io/pypi/v/scanpath-studio.svg)](https://pypi.org/project/scanpath-studio/)
[![Python versions](https://img.shields.io/pypi/pyversions/scanpath-studio.svg)](https://pypi.org/project/scanpath-studio/)
[![Live demo](https://img.shields.io/badge/Live_demo-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://scanpath-studio.streamlit.app)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue)](https://lacclab.github.io/scanpath-studio/)
[![CI](https://github.com/lacclab/scanpath-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/lacclab/scanpath-studio/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Flacclab.github.io%2Fscanpath-studio%2Fcoverage%2Fbadge.json)](https://lacclab.github.io/scanpath-studio/coverage/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/lacclab/scanpath-studio/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22933884.svg)](https://doi.org/10.5281/zenodo.22933884)

An interactive workbench for **eye-tracking-while-reading** data. See each
scanpath the way the reader saw it: words at their true on-screen positions,
with fixations, saccades, a heatmap and an animated replay drawn over them, all
exportable as publication-ready figures. It works with your own data or the
bundled [OneStop][onestop-paper] demo, so you can try it with no setup at all.

![A reading scanpath replayed fixation by fixation](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/scanpath_animation.gif)

*A scanpath replayed fixation by fixation over the text the reader saw.*

## Get started

- **In the browser, nothing to install:** the live demo at
  <https://scanpath-studio.streamlit.app>.
- **With pip** (Python 3.11–3.14):

  ```bash
  pip install scanpath-studio
  scanpath-studio      # opens the app in your browser
  ```

- **As a desktop app**, no Python needed — download, unpack, and launch:
  **[Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip)** ·
  **[macOS (Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.tar.gz)** ·
  **[Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz)**.
  The builds are not code-signed yet, and the
  [desktop notes](https://lacclab.github.io/scanpath-studio/desktop/) cover the
  extra click at first launch.

The pip and desktop installs run on your own machine, so your data stays there.
The hosted demo runs on a Streamlit Community Cloud server; keep identifiable
recordings off it ([privacy](https://lacclab.github.io/scanpath-studio/privacy/)).

## What you can do

- **Layer the scanpath:** text at its exact pixel coordinates, word boxes,
  fixations, saccades (with regressions standing out), a word-level heatmap, and
  raw gaze. Each layer switches on and off independently.
- **Color fixations by any column** in your data: duration, GPT-2 surprisal,
  word frequency, and so on.
- **Replay a reading** at real or scaled speed, and export it as interactive
  HTML, GIF or MP4.
- **Compare readings:** overlay two trials or place them side by side, including
  trials from two *different* datasets.
- **Triage trials:** star, tag and annotate them, then filter the pool by
  condition or annotation.
- **Analyse a corpus** per text, per sentence, per reader, or by group, with
  effect sizes for group differences.
- **Export and share:** one zip of figures, settings and tables for every
  filtered trial, plus links that reopen the exact view.
- **Author a scanpath** by drawing fixations onto the stimulus, for a teaching
  figure or a schematic.
- **Check the math:** every derived value's formula, units and precedence is in
  the [computation register](https://lacclab.github.io/scanpath-studio/computations/).

![Two readers of the same paragraph, overlaid on one canvas](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/assets/demo_dual_scanpath.png)

*Two readers of the same bundled-demo paragraph, overlaid on one canvas — 305
fixations between them
([watch it animated](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/docs/assets/demo_dual_scanpath.gif)).*

The app has three views: 🗺️ **Scanpath** for one trial at a time, 📊 **Corpus
Analysis** for the whole dataset, and 🗂️ **Data** for loading and configuring
datasets. The [feature guides](https://lacclab.github.io/scanpath-studio/guides/)
walk through each one.

![The Scanpath Studio app](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/docs/assets/app_screenshot.png)

## Your data

Upload word/AoI, fixation and (optionally) raw-gaze tables as **CSV, TSV, TXT,
Parquet, Feather or Excel**, or as a **.zip** of them. Columns are auto-detected
from EyeLink, Gazepoint, Tobii, SMI, Pupil Labs and snake-case conventions, and
you can override any guess. If your data has only fixations, the app computes
the standard per-word measures itself — **FFD**, **FPRT** (gaze duration),
**RPD** (go-past), **TFD** (dwell), skips and regressions — following Rayner
(1998) and Inhoff & Radach (1998). Precomputed EyeLink measures take precedence.
See [Bring your own data](https://lacclab.github.io/scanpath-studio/bring-your-own-data/)
and the [data format](https://lacclab.github.io/scanpath-studio/data-format/).

Several public corpora load without an upload: **OneStop**,
[**PoTeC**](https://github.com/DiLi-Lab/PoTeC) and **MultiplEYE** have
ready-made loaders, and thirty-one
[harmonised benchmark corpora](https://lacclab.github.io/scanpath-studio/benchmark-corpora/)
— German, Chinese, Persian, Danish, Spanish, Dutch, Russian, English, and the
multilingual MECO waves — load from one locally prepared bundle in a single
common schema, which makes cross-corpus comparison practical.

## Command line & Python API

Everything the app draws is also available headless — same pipeline, same figure.

```bash
scanpath-studio render --sample --list-trials              # what's available
scanpath-studio render --sample -o scanpath.html           # interactive HTML
scanpath-studio render --words ia.csv --fixations fix.csv -p p1 -t t3 -o figure.png
scanpath-studio render --sample --animate -o replay.html   # animated replay
```

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data(
    "ia.csv", "fixations.csv"
)  # paths, globs, or lists; either table optional
sps.list_trials(words, fixations)
fig = sps.plot_scanpath(words, fixations, "p1", "t3")  # every layer toggle is a kwarg
sps.save_figure(fig, "scanpath.png")  # .html / .png / .svg / .pdf
measures = sps.compute_word_metrics(words, fixations)  # FFD / FPRT / RPD / TFD …
```

HTML export is browser-free; PNG/SVG/PDF/GIF/MP4 go through Kaleido (run
`plotly_get_chrome -y` once). The
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

A system-demo paper is in preparation — **citation TBD**. Until then, cite the
software by its Zenodo DOI,
[10.5281/zenodo.22933884](https://doi.org/10.5281/zenodo.22933884). That DOI always
resolves to the latest release; the Zenodo record also lists a DOI per version,
for pinning the exact release you used. GitHub's **"Cite this repository"**
button gives the same metadata as APA or BibTeX (generated from
[`CITATION.cff`](https://github.com/lacclab/scanpath-studio/blob/main/CITATION.cff)).

**Authors:** Omer Shubi, Keren Gruteke Klein, Maya Grossman, Ella Lion, Deborah N.
Jakobi, David R. Reich, Lena Jäger, and Yevgeni Berzak — Data and Decision
Sciences (Technion) and Department of Computational Linguistics (University of
Zurich).

If you use the bundled demo data, please cite the OneStop corpus:

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

The bundled demo is a subset of [OneStop Eye Movements][onestop-corpus], used
under its original license ([docs][onestop-docs]).

[onestop-paper]: https://www.nature.com/articles/s41597-025-06272-2
[onestop-corpus]: https://github.com/lacclab/OneStop-Eye-Movements
[onestop-docs]: https://lacclab.github.io/OneStop-Eye-Movements/

## Built with AI assistance

Much of this code was written with AI assistance. That is not the same as
bug-free. **Cross-check anything you publish against your own pipeline.** If
something looks wrong — or if you have a feature request or suggestion —
[open an issue](https://github.com/lacclab/scanpath-studio/issues).

## License

MIT — see [LICENSE](https://github.com/lacclab/scanpath-studio/blob/main/LICENSE); the bundled demo data carries its own licenses (see [NOTICE](https://github.com/lacclab/scanpath-studio/blob/main/NOTICE)).
