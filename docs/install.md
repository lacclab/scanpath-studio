# Install

## Download { #install }

=== "Desktop app"

    The easiest way to work with your own data: no Python needed, your data
    stays on your computer, and the public corpora download in one click.
    Download the build for your system, then:

    - **macOS** (14 or later, Apple silicon):
      [`ScanpathStudio-macos-arm64.dmg`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg).
      Open it, drag **Scanpath Studio** to **Applications**, and launch it from
      there. If macOS refuses to open it, go to **System Settings → Privacy &
      Security** and click **Open Anyway**.
    - **Windows**:
      [`ScanpathStudio-windows-x86_64-setup.exe`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64-setup.exe).
      Run it to install Scanpath Studio for your account (no administrator
      rights needed), then launch it from the Start menu. The installer is not
      code-signed, so SmartScreen warns the first time: click
      **More info → Run anyway**. Uninstall it from **Settings → Apps**. To run
      it without installing, use
      [`ScanpathStudio-windows-x86_64.zip`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip)
      instead: extract it and run `ScanpathStudio.exe`.
    - **Linux**:
      [`ScanpathStudio-linux-x86_64.tar.gz`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz).
      Extract it and run `./ScanpathStudio/ScanpathStudio`.

    The app opens in its own window. To quit, close that window on macOS, or
    the console window on Windows and Linux. A download there asks where to
    save the file. On an Intel Mac or an older macOS, use pip instead.

=== "pip"

    ```bash
    pip install scanpath-studio
    scanpath-studio
    ```

    Needs Python 3.11–3.14. The app opens at <http://localhost:8501>.

=== "Try online"

    Open the [live demo](https://scanpath-studio.streamlit.app) to try the app
    on its bundled data. Nothing to install. The demo has limited memory and
    can't download the public corpora, so for your own data use the desktop
    app or pip.

## Explore the demo

The app opens on a small bundled sample of the
[OneStop](guides/loading-data/index.md#onestop) corpus.

1. Pick a trial with the picker above the plot.
2. Switch layers on and off in **Plot controls**: Fixations, Saccades,
   Stimulus (the text), Word boxes, Heatmap.
3. Turn on **Animate** to replay the trial.
4. Open **Export → Current figure** to download it.
5. Load your own data: click **+** beside **Select dataset** and choose
   **Import files** (see [Loading data](guides/loading-data/index.md)).

## Updating { #updating }

**:material/help: Help → :material/info: About** shows your version. Click
**:material/update: Check for updates** to see if a newer one is out. In the
desktop app, **:material/update: Update & restart** installs it and keeps your
datasets and settings; with pip, run `pip install -U scanpath-studio`.

## Next steps

- [Plot gallery](gallery.md) shows what the app draws, for ideas.
- [Tutorials](tutorials/index.md) walk through common tasks, from checking a
  pilot to exporting a figure.
- [Feature guides](guides/index.md) explain each part of the app.
- [API & CLI](automation.md) covers the Python API and the command line.
