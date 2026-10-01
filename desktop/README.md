# Desktop build (ENG-15, signed under ENG-21)

Standalone per-OS bundles of the app (PyInstaller onedir + a Chromium app
window, or the default browser without one — ENG-85). Design + rationale: [`plans/eng-15-desktop-app.md`](https://github.com/lacclab/scanpath-studio/blob/v0.31.2/plans/eng-15-desktop-app.md) (at `v0.31.2`)
and [`plans/eng-21-signing-notarization.md`](../plans/eng-21-signing-notarization.md).

```bash
pip install . pyinstaller                             # non-editable install
pyinstaller --clean --noconfirm desktop/scanpath_studio.spec
python desktop/smoke_test.py                          # selfcheck + boot test
```

Output is `dist/ScanpathStudio.app` on macOS and `dist/ScanpathStudio/`
elsewhere. Note that on macOS PyInstaller leaves the onedir folder in place
*beside* the bundle — the smoke test deliberately targets the `.app`, because a
path-based default that picked the folder would test an artifact that is never
released.

- `launcher.py` — frozen entry point: Streamlit server on a free port, branded
  theme, opens the app after the health check — `--app=<url>` in Chrome / Edge /
  Brave / Chromium when installed, else `webbrowser.open` (ENG-85;
  `SCANPATH_DESKTOP_BROWSER=default` forces the tab); `--selfcheck` for CI. In the
  macOS `.app` it also redirects output to `~/Library/Logs/Scanpath Studio/` and
  quits once the last app window or tab has been closed for `IDLE_EXIT_GRACE_S`
  (150s — just past Streamlit's own two-minute session-retention window), since
  a bundle with no Cocoa run loop cannot answer Cmd-Q.
- Launch environment variables: `SCANPATH_DESKTOP_PORT` pins the server port
  (default: a free one), `SCANPATH_DESKTOP_NO_BROWSER=1` opens nothing,
  `SCANPATH_DESKTOP_BROWSER=default` uses a default-browser tab,
  `SCANPATH_DESKTOP_IDLE_EXIT_S` sets the quit delay after the last window
  closes (`0` keeps it running), and `SCANPATH_DESKTOP_NO_LOG_FILE=1` keeps the
  macOS app's output on stdout.
- `scanpath_studio.spec` — the PyInstaller build definition.
- `entitlements.plist` — hardened-runtime entitlements (one key; the reasoning
  for each omission is in `plans/eng-21-signing-notarization.md` → *Entitlements*.
  No XML comments in it: `codesign` rejects a `--` inside one).
- `smoke_test.py` — verifies a built bundle (used by CI and locally).
- `make_icons.py` → `icons/` — generates the committed app icons.

CI builds all three OSes on `v*` tags / manual dispatch and attaches the
archives to the GitHub release (`.github/workflows/desktop.yml`).

**Signing.** One-time credential setup — enrolment, certificate, API key and the
seven repository secrets — is in [`SIGNING.md`](SIGNING.md).

Set `SCANPATH_CODESIGN_IDENTITY` to a `Developer ID Application:`
identity and PyInstaller signs every collected binary inside-out with the
hardened runtime, a secure timestamp and the entitlements; CI then notarizes and
staples the `.app` and the `.dmg`. Leave it unset — as a fork, or any local build
— and PyInstaller ad-hoc signs the bundle instead, which still produces a
deep, valid signature but no notarization. Every signing step in the workflow is
gated on the secrets being present, so an unsigned build never fails.
