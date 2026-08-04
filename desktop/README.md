# Desktop build (ENG-15)

Standalone per-OS bundles of the app (PyInstaller onedir + the system default
browser). Design + rationale: [`plans/eng-15-desktop-app.md`](../plans/eng-15-desktop-app.md).

```bash
pip install . pyinstaller                             # non-editable install
pyinstaller --clean --noconfirm desktop/scanpath_studio.spec
python desktop/smoke_test.py                          # selfcheck + boot test
```

- `launcher.py` — frozen entry point: Streamlit server on a free port, branded
  theme, opens the browser after the health check; `--selfcheck` for CI.
- `scanpath_studio.spec` — the PyInstaller build definition.
- `smoke_test.py` — verifies a built bundle (used by CI and locally).
- `make_icons.py` → `icons/` — generates the committed app icons.

CI builds all three OSes on `v*` tags / manual dispatch and attaches the
archives to the GitHub release (`.github/workflows/desktop.yml`).
The macOS leg ad-hoc signs the executable and the smoke test verifies that
signature. This provides integrity without claiming Apple notarization; users
still follow the documented Gatekeeper first-launch override.
