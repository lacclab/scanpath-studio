# Desktop app

Standalone builds of Scanpath Studio for **Windows / macOS / Linux** — no
Python toolchain, no terminal. The app starts a local server and opens in your
default browser. Everything runs on your machine — **no data leaves it**, which
makes the desktop build the right choice for private eye-tracking corpora.

Builds are attached to every
[GitHub release](https://github.com/lacclab/scanpath-studio/releases) from
**v0.25.0** on (earlier releases predate the desktop build).

!!! warning "Windows and Linux builds are unsigned"
    They are not code-signed, so Windows SmartScreen warns on first launch — the
    steps below include the extra click. Signing them is tracked as
    [ENG-47](https://github.com/lacclab/scanpath-studio/issues/146).

## Install & launch

=== "macOS (Apple silicon)"

    1. Download `ScanpathStudio-macos-arm64.dmg` from the
       [latest release](https://github.com/lacclab/scanpath-studio/releases/latest)
       (≈145 MB; ≈340 MB once installed).
    2. Double-click the `.dmg`, then drag **Scanpath Studio** onto the
       **Applications** shortcut beside it.
    3. Open it from Applications (or Launchpad). The first time, macOS confirms
       the app was downloaded from the Internet and says it checked it for
       malicious software — click **Open**. That prompt appears once per app,
       and every downloaded app gets it.
    4. Your browser opens the app. **Close the browser tab to quit** — the
       server stops a couple of minutes later. (The wait is deliberate:
       Streamlit can restore a session that reconnects within two minutes, so
       quitting sooner would throw away your work after a sleep or a network
       blip.)

    Release builds carry an Apple Developer ID signature and Apple
    notarization, with the ticket stapled to both the app and the disk image so
    the check works offline. If yours does not — a download from before signing
    was set up, or a build from a fork — macOS blocks it; see below.

    ??? question "If macOS refuses to open it"
        Most likely it is an unsigned build — a fork, a local build, or a
        release from before signing was configured. Open **System Settings →
        Privacy & Security**, scroll to the message naming Scanpath Studio, and
        click **Open Anyway**. macOS 15 removed the old Control-click → *Open*
        shortcut, so System Settings is the way through, and there is no need
        for the `xattr` terminal command earlier versions of this page
        suggested.

        If macOS instead says the app is **damaged**, *Open Anyway* will not
        help — that is a truncated or corrupted download. Download it again.

    Requires **macOS 14 or later on Apple silicon** — the bundled scipy and
    numpy wheels set that floor. On an Intel Mac, or an older macOS, use the
    [pip install](getting-started.md#install) instead.

=== "Windows"

    1. Download `ScanpathStudio-windows-x86_64.zip` from the
       [latest release](https://github.com/lacclab/scanpath-studio/releases/latest)
       (≈190 MB; ≈500 MB unpacked).
    2. Right-click → **Extract All**, open the extracted `ScanpathStudio` folder.
    3. Double-click **`ScanpathStudio.exe`**. On first launch SmartScreen will
       warn — click **More info → Run anyway**.
    4. A console window shows the server log; your browser opens the app. That
       console window *is* the server — close it, or press ++ctrl+c++, to quit.

=== "Linux"

    1. Download `ScanpathStudio-linux-x86_64.tar.gz` from the
       [latest release](https://github.com/lacclab/scanpath-studio/releases/latest)
       (≈190 MB; ≈500 MB unpacked).
    2. `tar -xzf ScanpathStudio-linux-x86_64.tar.gz` (the tarball preserves the
       executable bit — that's why it isn't a zip).
    3. Run `./ScanpathStudio/ScanpathStudio` — from a terminal, or double-click
       in a file manager that executes binaries. The terminal window *is* the
       server — close it, or press ++ctrl+c++, to quit.

## Good to know

- **Static image / video export needs a Chrome/Chromium on the machine** —
  same as the pip install; interactive HTML export always works. Details in
  [Export & troubleshooting](export-troubleshooting.md).
- **Where the macOS log goes.** The macOS app has no console window, so it
  writes its server log to
  `~/Library/Logs/Scanpath Studio/scanpath-studio.log` — open it from
  **Console.app** under *Log Reports*, or attach it to a bug report. Windows and
  Linux keep the console instead.
- **Advanced:** four environment variables tweak the launch —
  `SCANPATH_DESKTOP_PORT` pins the server port (default: a free one),
  `SCANPATH_DESKTOP_NO_BROWSER=1` skips opening the browser,
  `SCANPATH_DESKTOP_IDLE_EXIT_S` sets how many seconds to wait after the last
  tab closes before quitting (`0` keeps it running; honoured everywhere, but
  only the macOS app quits this way by default), and
  `SCANPATH_DESKTOP_NO_LOG_FILE=1` keeps output on stdout instead of the log
  file.
- **Building it yourself / how it's put together:** the launcher, PyInstaller
  spec, smoke test, and CI matrix live in
  [`desktop/`](https://github.com/lacclab/scanpath-studio/tree/main/desktop),
  with the design rationale in the
  [ENG-15 ADR](https://github.com/lacclab/scanpath-studio/blob/main/plans/eng-15-desktop-app.md)
  and the signing pipeline in the
  [ENG-21 ADR](https://github.com/lacclab/scanpath-studio/blob/main/plans/eng-21-signing-notarization.md).
