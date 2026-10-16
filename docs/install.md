# Get started

## Install { #install }

=== "Desktop app"

    Recommended for your own data. No Python needed.

    - [macOS (14+, Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg):
      open the DMG, drag Scanpath Studio to Applications, then launch it.
      If blocked, use System Settings → Privacy & Security → Open Anyway.
    - [Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64-setup.exe):
      run the installer, then launch from the Start menu.
      If SmartScreen warns, choose More info → Run anyway.
    - [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz):
      extract and run `./ScanpathStudio/ScanpathStudio`.

    On an Intel Mac or older macOS, use pip.
    [All downloads](https://github.com/lacclab/scanpath-studio/releases/latest).

=== "pip"

    Python 3.11–3.14:

    ```bash
    pip install scanpath-studio
    scanpath-studio
    ```

    Opens the app at <http://localhost:8501>.

=== "Try online"

    Open the [live demo](https://scanpath-studio.streamlit.app).
    No installation needed.

Desktop and pip installs keep your data on your computer and download OneStop
and PoTeC in one click. The online demo has limited memory and no corpus downloads.

## Explore

The app opens with a small [OneStop sample](guides/loading-data/index.md#onestop).

1. Pick a trial above the plot.
2. Toggle fixations, saccades, text, word boxes and heatmaps in Plot controls.
3. Turn on Animate to replay the reading.
4. Download a figure from Export.
5. Add your own data with + → Import files.

## Update { #updating }

Open :material/help: Help → :material/info: About → Check for updates.
For the desktop app, choose Update & restart. With pip:

```bash
pip install -U scanpath-studio
```

## Next steps

- [Tutorials](tutorials/index.md): common research tasks
- [Feature guides](guides/index.md): each view and its controls
- [Plot gallery](gallery.md): example figures
- [Python API](api.md) and [CLI reference](cli.md): full technical references
