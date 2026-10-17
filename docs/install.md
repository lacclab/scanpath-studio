---
description: "Download Scanpath Studio for Windows, macOS or Linux, install it with pip, or try the eye-tracking visualization demo in the browser, then draw a first scanpath."
---

# Get started

## Install { #install }

<div class="grid cards sps-install-options" markdown>

- :material-monitor:{ .lg .middle } **Desktop app** <span class="sps-install-badge">Recommended</span>

    No coding required. Your data stays on your computer.

    [:fontawesome-brands-apple: macOS](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg){ .md-button .md-button--primary }
    [:fontawesome-brands-windows: Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64-setup.exe){ .md-button .md-button--primary }
    [:fontawesome-brands-linux: Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz){ .md-button .md-button--primary }


    ??? info "Setup details & other downloads"

        - macOS 14+, Apple silicon: open the DMG, drag to Applications, then launch.
          If blocked: System Settings → Privacy & Security → Open Anyway.
          Intel Mac or older macOS? Use Python below.
        - Windows: run the installer, then launch from Start.
          If SmartScreen warns: More info → Run anyway.
          A [portable ZIP](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip) is also available.
        - Linux: extract, then run `./ScanpathStudio/ScanpathStudio`.

        [All downloads](https://github.com/lacclab/scanpath-studio/releases/latest)

- :material-cloud-outline:{ .lg .middle } **Try online**

    Explore the bundled demo. No installation.

    [Launch demo :material-arrow-right:](https://scanpath-studio.streamlit.app){ .md-button }

- :fontawesome-brands-python:{ .lg .middle } **Install with Python**

    Python 3.11–3.14. Opens in your browser.

    ```bash
    pip install scanpath-studio
    scanpath-studio
    ```

</div>

## Your first figure { #explore }

Start with the bundled [OneStop sample](guides/loading-data/index.md#onestop).
No files to prepare: choose a look and save an interactive figure.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/design-presets_poster.webp" data-autoplay
       aria-label="Switching between Scanpath, Heatmap and Illustration designs">
  <source src="../assets/workflows/design-presets.mp4" type="video/mp4">
</video>

<div class="grid cards sps-first-figure" markdown>

- **1 · Open a reading**

    In Scanpath, keep **Bundled demo** selected. Use **Select trial** to choose a reading.

- **2 · Choose a view**

    Click **Heatmap** in Design presets to see where fixation time concentrates.
    Switch to **Scanpath** to follow the sequence.

- **3 · Save your figure**

    Open **Export → Current figure**, choose **HTML**, then download.
    Open the saved file to explore the figure in your browser.

</div>

## Next steps

<div class="grid cards" markdown>

- **[Bring your own data](guides/loading-data/index.md#add-your-own-data)**

    Import your recordings and check the column mapping.

- **[Prepare a figure](tutorials/exporting-figures/export-one-figure.md)**

    Choose a format and size for your paper or slides.

- **[Explore more views](gallery.md)**

    Try an example, then follow its app instructions or the [feature guides](guides/index.md).

- **[Work in code](guides/scanpath-visualization/index.md#render-in-code)**

    Reproduce a view in Python or with the CLI.

</div>
