# Desktop build (ENG-15, signed under ENG-21)

Standalone per-OS bundles of the app (PyInstaller onedir + the system default
browser). Design + rationale: [`plans/eng-15-desktop-app.md`](../plans/eng-15-desktop-app.md)
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
  theme, opens the browser after the health check; `--selfcheck` for CI. In the
  macOS `.app` it also redirects output to `~/Library/Logs/Scanpath Studio/` and
  quits once the last browser tab has been closed for `IDLE_EXIT_GRACE_S`
  (150s — just past Streamlit's own two-minute session-retention window), since
  a bundle with no Cocoa run loop cannot answer Cmd-Q.
- `scanpath_studio.spec` — the PyInstaller build definition.
- `entitlements.plist` — hardened-runtime entitlements (one key; the reasoning
  for each omission is in the file).
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
