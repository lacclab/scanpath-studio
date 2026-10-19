# Scanpath Studio

**See how people read.**

A free, open-source app for exploring eye movements in reading. Check data quality, compare readers, and create figures and scanpath videos — no coding required.

**[Try it online](https://scanpath-studio.streamlit.app)** · **[Download the app](https://lacclab.github.io/scanpath-studio/install/)** · **[Browse the gallery](https://lacclab.github.io/scanpath-studio/gallery/)**

![Scanpath Studio: exploring trials, replaying a reading, comparing readers and analyzing a corpus](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/docs/assets/app_demo.gif)

[![PyPI](https://img.shields.io/pypi/v/scanpath-studio.svg)](https://pypi.org/project/scanpath-studio/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/lacclab/scanpath-studio/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22933884.svg)](https://doi.org/10.5281/zenodo.22933884)

## From your data to a figure

- **Bring your own data.** Load a Fixations table and a Words table, with optional raw gaze and metadata. [Data guide →](https://lacclab.github.io/scanpath-studio/guides/loading-data/)
- **Explore and replay.** View fixations, saccades and heatmaps; filter trials, then star or tag the ones to revisit.
- **Compare readings.** Overlay two scanpaths or place them side by side, across readers, conditions or datasets.
- **Analyze a corpus.** Explore the reading measures in your data by text, reader or group.
- **Export and share.** Save publication-ready figures, GIF/MP4 replays or a batch of trials, and share a view with a link.

[Follow a tutorial](https://lacclab.github.io/scanpath-studio/tutorials/) · [See it in action](https://lacclab.github.io/scanpath-studio/#from-recording-to-publication)

## Run it on your computer

Download the desktop app — **no Python needed**:

[Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64-setup.exe) · [macOS (Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg) · [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz)

Local installs keep your data on your machine. To try the app first, open the [online demo](https://scanpath-studio.streamlit.app) with its bundled data.

<details>
<summary>Prefer pip? Install with Python 3.11–3.14</summary>

```bash
pip install scanpath-studio
scanpath-studio
```

[Setup and update instructions](https://lacclab.github.io/scanpath-studio/install/)

</details>

## Python & command line

Build a figure in the app, then copy its Python or CLI code from **Share**. The [feature guides](https://lacclab.github.io/scanpath-studio/guides/) include scripting examples alongside the app instructions.

[Python API](https://lacclab.github.io/scanpath-studio/api/) · [CLI reference](https://lacclab.github.io/scanpath-studio/cli/)

## Research & community

Using Scanpath Studio in your research? [Cite the software](https://lacclab.github.io/scanpath-studio/about/#cite-scanpath-studio) (Shubi et al., 2026). The bundled demo is a subset of [OneStop Eye Movements](https://doi.org/10.1038/s41597-025-06272-2).

[Report a bug or request a feature](https://github.com/lacclab/scanpath-studio/issues) · [Contribute](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md) · [Code of conduct](https://github.com/lacclab/scanpath-studio/blob/main/CODE_OF_CONDUCT.md)

<sub>Developed with AI assistance. As with any research software, cross-check results before using them in published work.</sub>
