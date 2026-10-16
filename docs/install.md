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

Local installs support public corpus downloads. The online demo has limited memory.

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
