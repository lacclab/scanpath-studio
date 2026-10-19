# Scanpath Studio

**See how people read.**

A free, open-source app for exploring eye movements in reading. Check data quality, compare participants, and make figures and replay videos. No coding required.

**[Try it online](https://scanpath-studio.streamlit.app)** · **[Download the app](https://lacclab.github.io/scanpath-studio/install/)** · **[Browse the gallery](https://lacclab.github.io/scanpath-studio/gallery/)**

![Scanpath Studio: stepping through trials, replaying a reading, comparing two participants and analyzing a corpus](https://raw.githubusercontent.com/lacclab/scanpath-studio/main/docs/assets/app_demo.gif)

[![PyPI](https://img.shields.io/pypi/v/scanpath-studio.svg)](https://pypi.org/project/scanpath-studio/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/lacclab/scanpath-studio/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22933884.svg)](https://doi.org/10.5281/zenodo.22933884)

## From your data to a figure

- **Bring your own data.** Load your Fixations, Words or Raw gaze tables, and add participant, trial and text metadata. [Data guide →](https://lacclab.github.io/scanpath-studio/guides/loading-data/)
- **Explore and replay.** View fixations, saccades and heatmaps, and replay a reading fixation by fixation. Filter trials, then star or tag the ones to revisit.
- **Compare readings.** Overlay two scanpaths or place them side by side, from two participants, conditions or datasets.
- **Analyze a corpus.** Summarize the reading measures in your data by text, participant or group.
- **Export and share.** Save publication-ready figures, GIF or MP4 replays, or a batch of trials. Share a view as a link.

[Follow a tutorial](https://lacclab.github.io/scanpath-studio/tutorials/) · [See it in action](https://lacclab.github.io/scanpath-studio/#from-recording-to-publication)

## Run it on your computer

Download the desktop app. You don't need Python.

[Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64-setup.exe) · [macOS (Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg) · [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz)

A local install keeps your data on your computer. To try the app first, open the bundled demo [online](https://scanpath-studio.streamlit.app).

<details>
<summary>Prefer pip? Install with Python 3.11–3.14</summary>

```bash
pip install scanpath-studio
scanpath-studio
```

[Setup and update instructions](https://lacclab.github.io/scanpath-studio/install/)

</details>

## Python & command line

Build a figure in the app, then copy its Python or CLI code from **Share** → **Code**. The [feature guides](https://lacclab.github.io/scanpath-studio/guides/) also include Python and CLI examples.

[Python API](https://lacclab.github.io/scanpath-studio/api/) · [CLI reference](https://lacclab.github.io/scanpath-studio/cli/)

## Research & community

Using Scanpath Studio in your research? [Cite the software](https://lacclab.github.io/scanpath-studio/about/#cite-scanpath-studio) (Shubi et al., 2026). The bundled demo is a subset of [OneStop Eye Movements](https://doi.org/10.1038/s41597-025-06272-2).

[Report a bug or request a feature](https://github.com/lacclab/scanpath-studio/issues) · [Contribute](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md) · [Code of conduct](https://github.com/lacclab/scanpath-studio/blob/main/CODE_OF_CONDUCT.md)

<sub>Scanpath Studio was developed with AI assistance. As with any research software, cross-check its results before you rely on them in published work.</sub>
