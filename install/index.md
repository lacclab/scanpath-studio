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

  Explore the bundled demo. No installation.

  [Launch demo](https://scanpath-studio.streamlit.app)

- **Install with Python**

  Python 3.11–3.14. Opens in your browser.

  ```
  pip install scanpath-studio
  scanpath-studio
  ```

## Your first figure

Start with the bundled demo, a subset of the [OneStop corpus](https://lacclab.github.io/scanpath-studio/guides/loading-data/#onestop). You don't need to prepare any files. Choose a look, then save an interactive figure.

\[!\[

\](../assets/workflows/design-presets_poster.webp)\](../assets/workflows/design-presets.mp4)

- **1 · Open a reading**

  In the **Scanpath** view, choose **Bundled demo** in **Select dataset**. Then choose a reading in **Select trial**.

- **2 · Choose a view**

  In **Design presets**, click **Heatmap** to see where fixation time concentrates. Click **Scanpath** to follow the order of fixations.

- **3 · Save your figure**

  In the **Export** tab under the plot, find **Current figure**. Set **Download format** to **HTML**, then click **⬇ Download HTML**. Open the saved file in your browser to zoom and hover over the figure.

## Next steps

- **[Bring your own data](https://lacclab.github.io/scanpath-studio/guides/loading-data/#add-your-own-data)**

  Import your recordings and check the column mapping.

- **[Prepare a figure](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/export-one-figure/index.md)**

  Choose a format and size for your paper or slides.

- **[Explore more views](https://lacclab.github.io/scanpath-studio/gallery/index.md)**

  Try an example, then follow its app instructions or the [feature guides](https://lacclab.github.io/scanpath-studio/guides/index.md).

- **[Work in code](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#render-in-code)**

  Reproduce a view in Python or with the CLI.
