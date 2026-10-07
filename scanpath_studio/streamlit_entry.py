"""The script ``scanpath-studio run`` (and the desktop app) hands to ``streamlit run``.

It imports the app rather than being it, so that an error raised while
``app.py`` itself is imported still reaches ``crash_report``'s note asking the
user to report it — run as the script, ``app.py`` would fail before any guard
of its own could start. ``streamlit_app.py`` at the repo root is the same shim
for Streamlit Community Cloud.
"""

from scanpath_studio.crash_report import run_app

run_app()
