"""Desktop-bundle entry point (ENG-15).

PyInstaller freezes this script (see ``scanpath_studio.spec``) into the
standalone Scanpath Studio app: it starts the Streamlit server on a free
localhost port with the branded theme, then opens the user's default browser
once the server answers its health check.

Environment overrides (used by the smoke test, handy for debugging):
    SCANPATH_DESKTOP_PORT        fixed port instead of a free one
    SCANPATH_DESKTOP_NO_BROWSER  set to 1 to skip opening the browser

``--selfcheck`` runs a headless sanity pass inside the frozen process (load
the bundled sample, build a figure, render HTML) and exits — it catches
missing hidden imports or data files without needing a browser.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

HEALTH_TIMEOUT_S = 60.0


def _app_script() -> Path:
    """The packaged ``app.py`` on disk (Streamlit re-execs it as a script).

    Under PyInstaller the package sources are collected next to the bundle's
    other data files, and ``scanpath_studio.__file__`` points into that tree,
    so the same lookup works frozen and unfrozen.
    """
    import scanpath_studio

    return Path(scanpath_studio.__file__).resolve().parent / "app.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(url: str, timeout_s: float = HEALTH_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.3)
    return False


def _open_browser_when_ready(port: int) -> None:
    if _wait_for_server(f"http://127.0.0.1:{port}/_stcore/health"):
        webbrowser.open(f"http://127.0.0.1:{port}")


def selfcheck() -> int:
    """Headless sanity pass over the frozen bundle; returns an exit code."""
    # Import the whole UI module tree (tabs, controls, wizard, the sortables
    # custom component, …): the boot test's health check passes before the app
    # script ever runs, so a module missing from the freeze would otherwise
    # only surface on the first real page load.
    import scanpath_studio.app  # noqa: F401
    from scanpath_studio import api

    words, fixations = api.load_sample_data()
    combos = api.list_trials(words, fixations)
    if combos.empty:
        print("selfcheck FAILED: bundled sample yielded no trials")
        return 1
    first = combos.iloc[0]
    fig = api.plot_scanpath(
        words,
        fixations,
        str(first["participant_id"]),
        str(first["trial_id"]),
        canvas_size=(2560, 1440),
    )
    html = fig.to_html(include_plotlyjs="cdn")
    if "plotly" not in html.lower():
        print("selfcheck FAILED: figure HTML looks wrong")
        return 1
    print(f"selfcheck ok: {len(combos)} trials, figure HTML {len(html)} bytes")
    return 0


def main() -> None:
    if "--selfcheck" in sys.argv[1:]:
        sys.exit(selfcheck())

    port = int(os.environ.get("SCANPATH_DESKTOP_PORT") or _free_port())
    open_browser = os.environ.get("SCANPATH_DESKTOP_NO_BROWSER", "") not in (
        "1",
        "true",
    )

    from scanpath_studio.cli import _theme_cli_flags

    flags = [
        # Frozen Streamlit can misdetect development mode, which then rejects
        # an explicit --server.port; force it off.
        "--global.developmentMode=false",
        # headless=true stops Streamlit's own browser-open; we open it after
        # the health check instead (and not at all under the smoke test).
        "--server.headless=true",
        f"--server.port={port}",
        # No hot reload in a frozen app; the watcher only costs threads.
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        *_theme_cli_flags(),
    ]

    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready, args=(port,), daemon=True
        ).start()

    print(f"Scanpath Studio starting on http://127.0.0.1:{port}")
    print("Close this window (or press Ctrl+C) to quit.")

    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(_app_script()), *flags]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
