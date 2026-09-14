# PyInstaller spec for the standalone desktop build (ENG-15, signed under ENG-21).
#
# Build (from the repo root, in an env with the package + pyinstaller installed):
#   pyinstaller --clean --noconfirm desktop/scanpath_studio.spec
# Output: dist/ScanpathStudio/ on Linux/Windows; dist/ScanpathStudio.app on macOS
# (onedir either way — see plans/eng-15-desktop-app.md for the onedir-vs-onefile
# rationale). Verify with desktop/smoke_test.py.
#
# Signing (macOS, ENG-21): set SCANPATH_CODESIGN_IDENTITY to a "Developer ID
# Application: …" identity and PyInstaller signs every collected binary
# inside-out with the hardened runtime, a secure timestamp and the entitlements.
# Leave it unset — a fork, or any local build — and PyInstaller ad-hoc signs the
# bundle instead, which still yields a deep, valid signature but no notarization.
# Either way PyInstaller does the signing; there is no separate codesign step in
# CI. That is not a stylistic choice: PyInstaller rewrites Mach-O load paths as
# it assembles the bundle, which invalidates anything signed earlier, so the
# moment it signs is the only one a signature survives.

import os
import re
import sys

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

from scanpath_studio import __version__

datas = []
hiddenimports = []

# The whole scanpath_studio package must ship as on-disk *source*, not only as
# compiled modules in the archive: Streamlit re-execs app.py from its file
# path, and sample_data/ rides along as package data.
datas += collect_data_files("scanpath_studio", include_py_files=True)
hiddenimports += collect_submodules("scanpath_studio")

# Streamlit serves its frontend from package data, resolves its own version
# via importlib.metadata, and imports many of its modules dynamically.
datas += collect_data_files("streamlit")
datas += copy_metadata("streamlit")
hiddenimports += collect_submodules("streamlit")

# Asset-heavy deps whose data files the import analysis alone won't collect:
# plotly (plotly.min.js + validation json), the streamlit-sortables custom
# component frontend, kaleido's runtime support files, and the bundled ffmpeg
# used for MP4 animation export.
for pkg in ("plotly", "streamlit_sortables", "kaleido", "imageio_ffmpeg"):
    datas += collect_data_files(pkg)
hiddenimports += ["streamlit_sortables", "imageio_ffmpeg"]

is_macos = sys.platform == "darwin"

if is_macos:
    icon_path = os.path.join(SPECPATH, "icons", "icon.icns")  # noqa: F821
elif sys.platform.startswith("win"):
    icon_path = os.path.join(SPECPATH, "icons", "icon.ico")  # noqa: F821
else:
    icon_path = None  # Linux: no embedded exe icon

# EXE takes the list form; BUNDLE does not (it calls os.path.isabs on the value
# and raises TypeError on a list), so the bare string is kept for it.
icon = [icon_path] if icon_path else None

codesign_identity = os.environ.get("SCANPATH_CODESIGN_IDENTITY") or None
entitlements_file = (
    os.path.join(SPECPATH, "entitlements.plist")  # noqa: F821
    if codesign_identity
    else None
)

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],  # noqa: F821
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ScanpathStudio",
    debug=False,
    strip=False,
    upx=False,
    # Linux/Windows keep the console: server logs + errors stay visible (the
    # ENG-15 decision). macOS cannot — inside a .app, Launch Services wires
    # stdout/stderr to /dev/null in *both* modes, and console=True additionally
    # sets LSBackgroundOnly, which costs the Dock icon and Cmd-Tab and makes a
    # double-click look like nothing happened. So the .app is windowed and the
    # launcher redirects its own output to ~/Library/Logs instead (ENG-21).
    console=not is_macos,
    icon=icon,
    codesign_identity=codesign_identity,
    entitlements_file=entitlements_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ScanpathStudio",
)

if is_macos:
    # CFBundleShortVersionString takes at most three period-separated integers,
    # so a PEP 440 pre-release ("0.31.0rc1", "0.31.0.dev0") has to be trimmed to
    # its numeric prefix — Apple's validation can reject the raw string, and a
    # tag build is the wrong place to discover that.
    bundle_version = re.match(r"\d+(?:\.\d+){0,2}", __version__)
    bundle_version = bundle_version.group(0) if bundle_version else "0"

    app = BUNDLE(
        # The COLLECT, never the EXE: onedir + BUNDLE is the only supported
        # combination (onefile + BUNDLE is deprecated and becomes an error in
        # PyInstaller 7.0).
        coll,
        name="ScanpathStudio.app",
        icon=icon_path,
        # codesign requires a bundle identifier, and PyInstaller's default is the
        # bare app name — neither unique nor reverse-DNS.
        bundle_identifier="io.github.lacclab.scanpath-studio",
        version=bundle_version,  # -> CFBundleShortVersionString; must be a str
        info_plist={
            # PyInstaller writes CFBundleShortVersionString but not CFBundleVersion.
            "CFBundleVersion": bundle_version,
            "CFBundleDisplayName": "Scanpath Studio",
            "NSHighResolutionCapable": True,
            # Launch Services enforces this, so an old-macOS user gets a clean
            # dialog instead of a dyld crash — but only if it is honest. The
            # floor is set by the bundled wheels, not by our code: scipy and
            # numpy ship arm64 binaries with `minos 14.0` (98 of them in a
            # current build), so 12.0 here would let the app start on macOS 12
            # and die in dyld, which is exactly what this key exists to prevent.
            # orjson is built for 15.0 but is optional — plotly imports it in a
            # try/except and falls back — so it does not raise the floor.
            # Re-check with `otool -l` after any scipy/numpy bump.
            "LSMinimumSystemVersion": "14.0",
        },
    )
