# Desktop app

Standalone builds of Scanpath Studio for **Windows / macOS / Linux** — no
Python toolchain, no terminal. The app starts a local server and opens in your
default browser; the console window that stays open *is* the server (close it,
or press ++ctrl+c++, to quit). Everything runs on your machine.

Builds are attached to every
[GitHub release](https://github.com/lacclab/scanpath-studio/releases)
(120–190 MB download).

!!! warning "Unsigned builds"
    The builds are not code-signed yet, so your OS will warn on first launch —
    the per-OS steps below include the extra click that gets you past it.

## Install & launch

=== "Windows"

    1. Download [`ScanpathStudio-windows-x86_64.zip`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip)
       from the [latest release](https://github.com/lacclab/scanpath-studio/releases/latest).
    2. Right-click → **Extract All**, open the extracted `ScanpathStudio` folder.
    3. Double-click **`ScanpathStudio.exe`**. On first launch SmartScreen will
       warn — click **More info → Run anyway**.
    4. A console window shows the server log; your browser opens the app.

=== "macOS (Apple silicon)"

    1. Download [`ScanpathStudio-macos-arm64.tar.gz`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.tar.gz)
       from the [latest release](https://github.com/lacclab/scanpath-studio/releases/latest)
       (Safari usually unpacks it; otherwise double-click the archive).
    2. In the `ScanpathStudio` folder, double-click `ScanpathStudio`. When macOS
       blocks it, open **System Settings → Privacy & Security** and click
       **Open Anyway**.
    3. If macOS says the app *cannot be opened* and offers no override, open
       Terminal and clear quarantine from the **extracted folder**:

       ```bash
       xattr -dr com.apple.quarantine /path/to/ScanpathStudio
       ```

       Type `xattr -dr com.apple.quarantine ` (including the final space), drag
       the extracted folder into Terminal, and press Return. Then run
       `./ScanpathStudio/ScanpathStudio` once.
    4. A Terminal window shows the server log; your browser opens the app.

    The build is not notarized by Apple, so this is needed once; the quarantine
    command changes only the folder you name.

    The build is **Apple silicon (M-series) only** — on an Intel Mac, use the
    [pip install](getting-started.md#install) instead.

=== "Linux"

    1. Download [`ScanpathStudio-linux-x86_64.tar.gz`](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz)
       from the [latest release](https://github.com/lacclab/scanpath-studio/releases/latest).
    2. `tar -xzf ScanpathStudio-linux-x86_64.tar.gz`.
    3. Run `./ScanpathStudio/ScanpathStudio` — from a terminal, or double-click
       in a file manager that executes binaries.

## Good to know

- **Static image / video export needs Chrome, Chromium or Edge installed on the
  machine**; interactive HTML export always works.
- **Advanced:** two environment variables tweak the launch —
  `SCANPATH_DESKTOP_PORT` pins the server port (default: a free one), and
  `SCANPATH_DESKTOP_NO_BROWSER=1` skips opening the browser.
- **Building it yourself:** see
  [`desktop/`](https://github.com/lacclab/scanpath-studio/tree/main/desktop).
