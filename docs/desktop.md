# Desktop app

Standalone builds of Scanpath Studio for **Windows / macOS / Linux** — no
Python toolchain, no terminal. The app starts a local server and opens in your
default browser; the console window that stays open *is* the server (close it,
or press ++ctrl+c++, to quit). Everything runs on your machine — **no data
leaves it**, which makes the desktop build the right choice for private
eye-tracking corpora.

Builds are attached to every
[GitHub release](https://github.com/lacclab/scanpath-studio/releases) from
**v0.25.0** on (≈190 MB download, ≈500 MB unpacked; earlier releases predate
the desktop build).

!!! warning "Unsigned builds"
    The builds are not code-signed yet, so your OS will warn on first launch —
    the per-OS steps below include the extra click that gets you past it.

## Install & launch

=== "Windows"

    1. Download `ScanpathStudio-windows-x86_64.zip` from the
       [latest release](https://github.com/lacclab/scanpath-studio/releases/latest).
    2. Right-click → **Extract All**, open the extracted `ScanpathStudio` folder.
    3. Double-click **`ScanpathStudio.exe`**. On first launch SmartScreen will
       warn — click **More info → Run anyway**.
    4. A console window shows the server log; your browser opens the app.

=== "macOS (Apple silicon)"

    1. Download `ScanpathStudio-macos-arm64.tar.gz` from the
       [latest release](https://github.com/lacclab/scanpath-studio/releases/latest)
       (Safari usually unpacks it; otherwise double-click the archive).
    2. In the `ScanpathStudio` folder, **right-click `ScanpathStudio` → Open →
       Open** the first time — a plain double-click is blocked by Gatekeeper
       because the build isn't notarized. (Alternative: System Settings →
       Privacy & Security → *Open Anyway*.)
    3. A Terminal window shows the server log; your browser opens the app.

    The build is **Apple silicon (M-series) only** — on an Intel Mac, use the
    [pip install](getting-started.md#install) instead.

=== "Linux"

    1. Download `ScanpathStudio-linux-x86_64.tar.gz` from the
       [latest release](https://github.com/lacclab/scanpath-studio/releases/latest).
    2. `tar -xzf ScanpathStudio-linux-x86_64.tar.gz` (the tarball preserves the
       executable bit — that's why it isn't a zip).
    3. Run `./ScanpathStudio/ScanpathStudio` — from a terminal, or double-click
       in a file manager that executes binaries.

## Good to know

- **Static image / video export needs a Chrome/Chromium on the machine** —
  same as the pip install; interactive HTML export always works. Details in
  [Export & troubleshooting](export-troubleshooting.md).
- **Advanced:** two environment variables tweak the launch —
  `SCANPATH_DESKTOP_PORT` pins the server port (default: a free one), and
  `SCANPATH_DESKTOP_NO_BROWSER=1` skips opening the browser.
- **Building it yourself / how it's put together:** the launcher, PyInstaller
  spec, smoke test, and CI matrix live in
  [`desktop/`](https://github.com/lacclab/scanpath-studio/tree/main/desktop),
  with the design rationale in the
  [ENG-15 ADR](https://github.com/lacclab/scanpath-studio/blob/main/plans/eng-15-desktop-app.md).
