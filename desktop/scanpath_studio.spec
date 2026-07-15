# PyInstaller spec for the standalone desktop build (ENG-15).
#
# Build (from the repo root, in an env with the package + pyinstaller installed):
#   pyinstaller --clean --noconfirm desktop/scanpath_studio.spec
# Output: dist/ScanpathStudio/ (onedir — see plans/eng-15-desktop-app.md for
# the onedir-vs-onefile rationale). Verify with desktop/smoke_test.py.

import os
import sys

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

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

if sys.platform == "darwin":
    icon = [os.path.join(SPECPATH, "icons", "icon.icns")]  # noqa: F821
elif sys.platform.startswith("win"):
    icon = [os.path.join(SPECPATH, "icons", "icon.ico")]  # noqa: F821
else:
    icon = None  # Linux: no embedded exe icon

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
    # Keep the console: server logs + errors stay visible (v1 decision, see
    # the ADR — a windowed/native shell is a follow-up).
    console=True,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ScanpathStudio",
)
