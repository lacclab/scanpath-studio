# Get started

## Install

Recommended for your own data. No Python needed.

- [macOS (14+, Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg): open the DMG, drag Scanpath Studio to Applications, then launch it. If blocked, use System Settings → Privacy & Security → Open Anyway.
- [Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64-setup.exe): run the installer, then launch from the Start menu. If SmartScreen warns, choose More info → Run anyway. Or use the [portable ZIP](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip).
- [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz): extract and run `./ScanpathStudio/ScanpathStudio`.

On an Intel Mac or older macOS, use pip. [All downloads](https://github.com/lacclab/scanpath-studio/releases/latest).

Python 3.11–3.14:

```
pip install scanpath-studio
scanpath-studio
```

Opens the app at <http://localhost:8501>.

Open the [live demo](https://scanpath-studio.streamlit.app). No installation needed.

Desktop and pip installs keep your data on your computer and download OneStop and PoTeC in one click. The online demo has limited memory and no corpus downloads.

## Explore

The app opens with a small [OneStop sample](https://lacclab.github.io/scanpath-studio/guides/loading-data/#onestop).

1. Pick a trial above the plot.
1. Toggle fixations, saccades, text, word boxes and heatmaps in Plot controls.
1. Turn on Animate to replay the reading.
1. Download a figure from Export.
1. Add your own data with + → Import files.

## Update

Open Help → About → Check for updates. For the desktop app, choose Update & restart. With pip:

```
pip install -U scanpath-studio
```

## Next steps

- [Tutorials](https://lacclab.github.io/scanpath-studio/tutorials/index.md): common research tasks
- [Feature guides](https://lacclab.github.io/scanpath-studio/guides/index.md): each view and its controls
- [Plot gallery](https://lacclab.github.io/scanpath-studio/gallery/index.md): example figures
- [Python API](https://lacclab.github.io/scanpath-studio/api/index.md) and [CLI reference](https://lacclab.github.io/scanpath-studio/cli/index.md): full technical references
