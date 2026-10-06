"""Streamlit Community Cloud entry point.

Cloud deployments by convention look for ``streamlit_app.py`` at the repo root.
This is a thin shim that runs the packaged app — through ``crash_report``, so an
unexpected error asks the user to report it instead of showing a bare traceback.
"""

from scanpath_studio.crash_report import run_app

run_app()
