# Get started

## Install

- **Desktop app** Recommended

  No coding required. Your data stays on your computer.

  [macOS](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg) [Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64-setup.exe) [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz)

  Setup details & other downloads

  - macOS 14+, Apple silicon: open the DMG, drag to Applications, then launch. If blocked: System Settings → Privacy & Security → Open Anyway. Intel Mac or older macOS? Use Python below.
  - Windows: run the installer, then launch from Start. If SmartScreen warns: More info → Run anyway. A [portable ZIP](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip) is also available.
  - Linux: extract, then run `./ScanpathStudio/ScanpathStudio`.

  [All downloads](https://github.com/lacclab/scanpath-studio/releases/latest)

- **Try online**

  Explore the bundled demo without installing anything.

  [Launch demo](https://scanpath-studio-dev.streamlit.app)

- **Install with Python**

  Requires Python 3.11–3.15. Runs on your computer and opens in your browser.

  ```
  pip install scanpath-studio
  scanpath-studio
  ```

## Try the Dev build

Stable is the published release on PyPI and the desktop downloads above. Dev follows the changes merged into `main`. You can [open the Dev app](https://scanpath-studio-dev.streamlit.app) or run it locally. In a separate Python environment with Git installed, run:

```
python -m pip install "git+https://github.com/lacclab/scanpath-studio.git@dev"
scanpath-studio
```

**Help** shows which channel you are running. Its release notes are in **About & citation → App details**.

For a Git installation, the update command keeps your repository, requested ref and package subdirectory. An install from an official release tag follows the Stable channel for updates. If you selected a commit hash, choose the new revision in your original install command when you are ready to move.

## Replay a sample reading

On your first visit, the app opens a reading from the [OneStop demo](https://lacclab.github.io/scanpath-studio/dev/guides/loading-data/#onestop). Choose **Replay this reading** to follow the reader’s fixations over the text. Press **Pause**, then **Next fixation** to step through the recording. You can return to the sample walkthrough from **Help → Task guides**.

To work with your own recording, choose **Import my data** or follow [Add your own data](https://lacclab.github.io/scanpath-studio/dev/guides/loading-data/#add-your-own-data).

## Your first figure

Choose a reading in the demo to explore and save as an interactive figure.

\[!\[

\](../assets/workflows/design-presets_poster.webp)\](../assets/workflows/design-presets.mp4)

- **1 · Open a reading**

  In the **Scanpath View**, choose **Bundled demo** in **Select dataset**. Then choose a reading in **Select trial**.

- **2 · Choose a view**

  Choose **Heatmap** to see where fixation time concentrates, or **Scanpath** to follow the order of fixations. Both tiles sit under **Presets** in Essentials and Full.

- **3 · Save your figure**

  In the **Export** tab under the plot, find **Current figure**. Set **Download format** to **HTML**, then click **⬇ Download HTML**. Open the saved file in your browser to zoom and hover over the figure.

## Next steps

- **[Bring your own data](https://lacclab.github.io/scanpath-studio/dev/guides/loading-data/#add-your-own-data)**

  Import your recordings and check the column mapping.

- **[Prepare a figure](https://lacclab.github.io/scanpath-studio/dev/tutorials/exporting-figures/export-one-figure/index.md)**

  Choose a format and size for your paper or slides.

- **[Explore more views](https://lacclab.github.io/scanpath-studio/dev/gallery/index.md)**

  Try an example, then follow its app instructions or the [feature guides](https://lacclab.github.io/scanpath-studio/dev/guides/index.md).

- **[Work in code](https://lacclab.github.io/scanpath-studio/dev/guides/scanpath-visualization/#render-in-code)**

  Reproduce a view in Python or with the CLI.
