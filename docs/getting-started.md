# Getting started

## 1. Install { #install }

=== "Try online"

    Open the [live demo](https://scanpath-studio.streamlit.app). Nothing to
    install.

=== "pip"

    ```bash
    pip install scanpath-studio
    scanpath-studio
    ```

    Needs Python 3.11–3.14. The app opens at <http://localhost:8501>.

=== "Desktop app"

    No Python needed. Download the build for your system, then:

    - **macOS** (14 or later, Apple silicon):
      [`ScanpathStudio-macos-arm64.dmg`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg).
      Open it, drag **Scanpath Studio** to **Applications**, and launch it from
      there. If macOS refuses to open it, go to **System Settings → Privacy &
      Security** and click **Open Anyway**.
    - **Windows**:
      [`ScanpathStudio-windows-x86_64.zip`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip).
      Extract it and run `ScanpathStudio.exe`. The build is not code-signed, so
      SmartScreen warns the first time: click **More info → Run anyway**.
    - **Linux**:
      [`ScanpathStudio-linux-x86_64.tar.gz`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz).
      Extract it and run `./ScanpathStudio/ScanpathStudio`.

    The app opens in its own window. To quit, close that window on macOS, or
    the console window on Windows and Linux. On an Intel Mac or an older macOS,
    use pip instead.

## 2. Explore the demo

The app opens on a small bundled sample of the
[OneStop](onestop.md) corpus.

1. Pick a trial with the picker above the plot.
2. Switch layers on and off in the controls beside the plot: fixations,
   saccades, text, word boxes, heatmap.
3. Turn on **Animate** to replay the reading.
4. Open **Export → Current figure** to download it.

## 3. Load your own data

Click **+** beside **Select Dataset** and choose **Import files**. Upload a
fixation table and a words (interest-area) table, check the column mapping the
app proposes, describe the **Recording setup**, then click **:material/check: Add dataset**.

[Loading data](guides/loading-data.md) lists the accepted formats and what each
table needs.

## Next steps

- [Tutorials](tutorials/index.md) walk through common tasks, from checking a
  pilot to exporting a figure.
- [Feature guides](guides/index.md) explain each part of the app.
- [Automation](automation.md) covers the Python API and the command line.
