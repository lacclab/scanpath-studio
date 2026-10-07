"""Desktop-bundle entry point (ENG-15).

PyInstaller freezes this script (see ``scanpath_studio.spec``) into the
standalone Scanpath Studio app: it starts the Streamlit server on a free
localhost port with the branded theme, then — once the server answers its
health check — opens it in its own window through Chrome / Edge / Brave /
Chromium's app mode, or in a tab of the default browser when none is
installed (ENG-85).

Environment overrides (used by the smoke test, handy for debugging):
    SCANPATH_DESKTOP_PORT         fixed port instead of a free one
    SCANPATH_DESKTOP_NO_BROWSER   set to 1/true/yes to skip opening the browser
    SCANPATH_DESKTOP_BROWSER      "app" (default): its own window when a
                                  Chromium-family browser is installed;
                                  "default": a tab in the default browser
    SCANPATH_DESKTOP_NO_LOG_FILE  set to 1/true/yes to keep output on stdout
                                  instead of redirecting it to the log file
    SCANPATH_DESKTOP_IDLE_EXIT_S  seconds with no browser session before the
                                  server quits itself (0 disables; ENG-21)

``--selfcheck`` runs a headless sanity pass inside the frozen process (find
the plotly.min.js the app serves, load the bundled sample, build a figure,
render HTML) and exits — it catches missing hidden imports or data files
without needing a browser.

``--update`` is About's *Update & restart*, headless (#385): check GitHub
(or ``SCANPATH_UPDATE_FEED``, a local JSON release CI uses), download,
verify, stage and self-test the new version, then hand the swap to a
detached helper and exit. The helper relaunches the app; the relaunched
launcher reports in (``started`` at launch, ``booted`` once its server
answers), and the helper puts the old version back if it never does.
"""

from __future__ import annotations

import math
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

# Windows first launches can spend minutes under a Defender/SmartScreen scan
# of the unpacked bundle before the server answers; match the smoke test's
# boot budget rather than giving up while the server is still coming up.
HEALTH_TIMEOUT_S = 180.0

# ENG-21, macOS .app only. Launch Services wires stdout/stderr to /dev/null and
# gives the process no controlling terminal, so the log has to go to a file —
# ~/Library/Logs/<App Name>/ is the Apple convention, and Console.app reads it
# for free.
LOG_DIR = "~/Library/Logs/Scanpath Studio"
LOG_NAME = "scanpath-studio.log"
# Truncate rather than grow without bound: this file is append-per-launch and
# nothing rotates it.
LOG_MAX_BYTES = 5 * 1024 * 1024

# A .app has no Cocoa run loop, so it cannot answer Cmd-Q or Dock → Quit (those
# are Apple Events needing a handler) — the user would get "not responding" and
# Force Quit. Instead the server quits itself once the last browser session has
# been gone this long, which makes closing the app window (or tab) the quit gesture.
#
# The number is Streamlit's, not ours: a disconnected session stays restorable
# in `MemorySessionStorage` for `ttl_seconds = 2 * 60`, so any grace shorter than
# that can tear down a session the framework would still have handed back — a
# browser that drops the socket and reconnects, a discarded background tab.
# (Laptop sleep is *not* one of them: time.monotonic() does not advance while a
# Mac is asleep, so the grace cannot elapse across a closed lid.) Quitting a
# little late costs a lingering Dock icon; quitting early costs unsaved state.
IDLE_EXIT_GRACE_S = 150.0
IDLE_POLL_S = 2.0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _resolve_port() -> int:
    """``SCANPATH_DESKTOP_PORT`` when it's a usable port, else a free one."""
    raw = os.environ.get("SCANPATH_DESKTOP_PORT", "").strip()
    if raw:
        try:
            port = int(raw)
        except ValueError:
            port = 0
        if 0 < port < 65536:
            return port
        print(f"Ignoring invalid SCANPATH_DESKTOP_PORT={raw!r}; using a free port.")
    return _free_port()


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _in_macos_app_bundle() -> bool:
    """True when this process is the frozen executable inside a ``.app``.

    The precise test for "there is no console to print to": ``console=False``
    only applies to the macOS bundle, and Launch Services drops stdout/stderr
    only for a bundled launch. A Linux/Windows build, a source checkout, and the
    inner executable run by hand from Terminal all answer False.
    """
    if sys.platform != "darwin" or not getattr(sys, "frozen", False):
        return False
    return ".app/Contents/" in os.path.abspath(sys.executable)


def _log_path() -> Path:
    return Path(LOG_DIR).expanduser() / LOG_NAME


def _rotate_if_large(path: Path) -> None:
    """Move an oversized log aside, keeping exactly one previous generation.

    Nothing else rotates this file — it is appended to once per launch — so
    without a cap it grows forever on a build that logs an exception every
    rerun. Rotating rather than deleting because the run worth reporting a bug
    about is usually the one that just ended.
    """
    try:
        if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
            path.replace(path.with_name(path.name + ".1"))
    except OSError:
        pass


def _redirect_output_to_log() -> Path | None:
    """Point fds 1 and 2 at the log file; return where, or None if not redirected.

    Must run before Streamlit and Tornado are imported: they bind logging
    handlers to ``sys.stderr`` at import time, and a handler bound to the old
    stream would keep writing into /dev/null.

    The redirect is at file-descriptor level rather than only rebinding
    ``sys.stdout``, so C-level writes and Kaleido's Chrome subprocess land in the
    same file. A read-only home must never stop the app launching, so every
    failure here is swallowed and the app runs without a log.
    """
    if _env_flag("SCANPATH_DESKTOP_NO_LOG_FILE") or not _in_macos_app_bundle():
        return None
    try:
        # Someone running the inner executable from a terminal wants it live.
        if sys.stdout is not None and sys.stdout.isatty():
            return None
    except (AttributeError, OSError, ValueError):
        pass
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_large(path)
        handle = open(path, "a", buffering=1, encoding="utf-8", errors="replace")
        os.dup2(handle.fileno(), 1)
        os.dup2(handle.fileno(), 2)
        # Rebind the Python-level streams too: in a windowed build they can be
        # None, and print() would then raise rather than reach the new fd.
        sys.stdout = handle
        sys.stderr = handle
        return path
    except (OSError, RuntimeError):
        # RuntimeError is Path.expanduser()'s when there is no home directory to
        # expand. Either way the contract holds: a log that cannot be opened
        # must never stop the app launching.
        return None


def _active_session_count() -> int | None:
    """Browser sessions currently connected, or None if that can't be read.

    ``num_active_sessions`` is public on ``SessionManager``, but the manager
    itself is only reachable through the Runtime's private ``_session_mgr`` —
    Streamlit exposes no count on ``Runtime``.
    ``tests/test_desktop_bundle.py`` pins *both* halves, because this function
    swallows every exception: without that pin, a Streamlit upgrade that renamed
    the attribute would break the quit gesture silently rather than fail a test.

    None means "unknown", which never counts as idle.
    """
    try:
        from streamlit.runtime import Runtime

        if not Runtime.exists():
            return None
        return Runtime.instance()._session_mgr.num_active_sessions()
    except Exception:
        return None


def _watch_for_idle_exit(grace_s: float) -> None:
    """Exit once the last browser session has been gone for ``grace_s``.

    Waits for a first session before arming, so a launch whose browser never
    opens (the smoke test, ``--server.headless``) keeps running instead of
    quitting ``grace_s`` after boot.
    """
    seen_session = False
    idle_since: float | None = None
    while True:
        time.sleep(IDLE_POLL_S)
        active = _active_session_count()
        if active is None:
            continue  # runtime not up yet, or the seam moved — never quit blind
        if active:
            seen_session = True
            idle_since = None
            continue
        if not seen_session:
            continue
        now = time.monotonic()
        if idle_since is None:
            idle_since = now
        elif now - idle_since >= grace_s:
            print("Last app window closed; shutting down.")
            try:
                sys.stdout.flush()
            except (AttributeError, OSError, ValueError):
                pass
            # The Streamlit server runs in this process and owns the main
            # thread inside stcli.main(), which never returns — os._exit is the
            # only way out from a daemon thread.
            os._exit(0)


def _idle_exit_grace() -> float:
    """``SCANPATH_DESKTOP_IDLE_EXIT_S`` when set, else the default for this build.

    Off outside the macOS ``.app``: Linux and Windows keep a console window whose
    closing already quits the server, and changing that would be a regression.
    """
    raw = os.environ.get("SCANPATH_DESKTOP_IDLE_EXIT_S", "").strip()
    if raw:
        try:
            seconds = float(raw)
        except ValueError:
            seconds = None
        # float() happily accepts "inf" and "nan", and a negative reads as
        # "disable" only by accident. Reject all three the same way as junk,
        # rather than silently changing the quit behaviour.
        if seconds is None or not math.isfinite(seconds) or seconds < 0:
            print(
                f"Ignoring invalid SCANPATH_DESKTOP_IDLE_EXIT_S={raw!r} "
                f"(want a non-negative number of seconds; 0 disables)."
            )
        else:
            return seconds
    return IDLE_EXIT_GRACE_S if _in_macos_app_bundle() else 0.0


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


def _browser_mode() -> str:
    """``SCANPATH_DESKTOP_BROWSER``: ``app`` (the default) or ``default``."""
    raw = os.environ.get("SCANPATH_DESKTOP_BROWSER", "").strip().lower()
    if raw in ("", "app"):
        return "app"
    if raw in ("default", "tab"):
        return "default"
    print(
        f"Ignoring invalid SCANPATH_DESKTOP_BROWSER={raw!r} "
        f"(want 'app' or 'default'); opening an app window."
    )
    return "app"


def _app_browser_candidates() -> list[Path]:
    """Where a Chromium-family browser's executable lives on this OS, in order.

    Chrome, Edge, Brave and Chromium all take ``--app=<url>``; Safari and Firefox
    have no equivalent. The order is a preference, not the user's default
    browser — macOS and Windows keep that behind APIs a frozen Python cannot
    reach cheaply, and any of these gives the same window.
    """
    if sys.platform == "darwin":
        apps = [
            ("Google Chrome", "Google Chrome"),
            ("Microsoft Edge", "Microsoft Edge"),
            ("Brave Browser", "Brave Browser"),
            ("Chromium", "Chromium"),
        ]
        roots = [Path("/Applications"), Path.home() / "Applications"]
        return [
            root / f"{bundle}.app" / "Contents" / "MacOS" / exe
            for bundle, exe in apps
            for root in roots
        ]
    if sys.platform.startswith("win"):
        rel = [
            Path("Google/Chrome/Application/chrome.exe"),
            # Ships with every Windows 10/11, so the app window is the norm there.
            Path("Microsoft/Edge/Application/msedge.exe"),
            Path("BraveSoftware/Brave-Browser/Application/brave.exe"),
        ]
        roots = [
            os.environ.get(var)
            for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
        ]
        return [Path(root) / path for path in rel for root in roots if root]
    names = [
        "google-chrome",
        "google-chrome-stable",
        "microsoft-edge",
        "brave-browser",
        "chromium",
        "chromium-browser",
    ]
    return [Path(found) for name in names if (found := shutil.which(name))]


def _find_app_browser() -> Path | None:
    for path in _app_browser_candidates():
        if path.is_file():
            return path
    return None


def _open_app_window(browser: Path, url: str) -> bool:
    """Open ``url`` as a Chromium app window (no tabs, no address bar).

    Detached into its own session, so the browser outlives this process —
    the quit watcher's ``os._exit`` must not take the user's browser with it.
    If the browser is already running, the process started here hands the
    window to it and exits, which is what Chromium's singleton does anyway.
    """
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen([str(browser), f"--app={url}"], **kwargs)
    except OSError as exc:
        print(f"Could not start {browser} ({exc}); opening a browser tab instead.")
        return False
    _bring_to_front(browser)
    return True


def _bring_to_front(browser: Path) -> None:
    """Activate the browser on macOS so the new window is not buried.

    A running browser takes the window from the process started above, but macOS
    leaves that browser wherever it was — often behind the other windows, where a
    window with no tabs and no Dock icon of its own is hard to find. Activating
    the ``.app`` puts its newest window, the app window, in front. Best effort:
    the window is already open whether or not this works.
    """
    if sys.platform != "darwin":
        return
    bundle = next((p for p in browser.parents if p.suffix == ".app"), None)
    if bundle is None:
        return
    try:
        subprocess.run(
            ["open", "-a", str(bundle)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _open_browser_when_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}"
    if not _wait_for_server(f"{url}/_stcore/health"):
        print(
            f"Server did not answer within {HEALTH_TIMEOUT_S:.0f}s — if it is "
            f"still starting, open {url} yourself."
        )
        return
    # ENG-85: its own window, like a desktop app, when a browser that can do it
    # is installed; a tab in the default browser otherwise.
    if _browser_mode() == "app":
        browser = _find_app_browser()
        if browser is not None and _open_app_window(browser, url):
            print(f"Opened an app window with {browser}")
            return
    # A failed open is worth saying out loud rather than discarding: in the .app
    # there is no console, so a user who never gets a tab sees an app that looks
    # like it did nothing — and since the quit watcher arms only after a first
    # session, nothing would shut it down either.
    if not webbrowser.open(url):
        print(f"Could not open a browser automatically — open {url} yourself.")


def selfcheck() -> int:
    """Headless sanity pass over the frozen bundle; returns an exit code."""
    # Import the whole UI module tree (tabs, controls, wizard, the sortables
    # custom component, …): the boot test's health check passes before the app
    # script ever runs, so a module missing from the freeze would otherwise
    # only surface on the first real page load.
    import scanpath_studio.app  # noqa: F401
    from scanpath_studio import api
    from scanpath_studio.html_embed import PLOTLYJS_FILENAME, plotlyjs_dir

    # ENG-64: the app serves the frozen plotly package's own plotly.min.js to
    # every figure — without it the figure draws blank, whatever the network.
    plotlyjs = plotlyjs_dir() / PLOTLYJS_FILENAME
    if not plotlyjs.is_file():
        print(f"selfcheck FAILED: {plotlyjs} is missing from the bundle")
        return 1

    # #394: the update check and download (and dataset downloads, #391)
    # verify GitHub against the OS's own certificate store. Build that context
    # here, where the frozen truststore meets the real OS, not just imports it.
    from scanpath_studio.updates import _ssl_context

    try:
        _ssl_context()
    except Exception as error:
        print(f"selfcheck FAILED: no TLS context from the OS trust store: {error}")
        return 1

    words, fixations = api.load_sample_data()
    combos = api.list_trials(words, fixations)
    if combos.empty:
        print("selfcheck FAILED: bundled sample yielded no trials")
        return 1
    # (participant, trial), named as the dataset names them (DATA-66).
    participant, trial = combos.iloc[0]
    fig = api.plot_scanpath(
        words,
        fixations,
        str(participant),
        str(trial),
        canvas_size=(2560, 1440),
    )
    html = fig.to_html(include_plotlyjs=False)
    if "plotly" not in html.lower():
        print("selfcheck FAILED: figure HTML looks wrong")
        return 1
    from scanpath_studio import __version__

    print(
        f"selfcheck ok: v{__version__}, {len(combos)} trials, figure HTML {len(html)} bytes"
    )
    return 0


def update() -> int:
    """``--update``: About's *Update & restart*, headless (#385); an exit code."""
    from scanpath_studio import desktop_update, updates

    feed = os.environ.get(desktop_update.FEED_ENV, "").strip()
    latest = (lambda: desktop_update.feed_release(Path(feed))) if feed else None
    check = updates.check_for_updates(latest=latest)
    print(check.message)
    if check.status != "update_available":
        return 1 if check.status == "error" else 0
    try:
        plan = desktop_update.prepare(
            check,
            desktop_update.current_install(),
            # Only the test feed may hand over a local file.
            allow_file=bool(feed),
            on_step=lambda step: print(f"update: {step}..."),
        )
        desktop_update.start_swap(plan)
    except desktop_update.UpdateFailed as error:
        print(f"update FAILED: {error}")
        return 1
    print(
        f"update ok: swapping in v{plan.version}; the helper restarts the app "
        f"(log: {plan.state / 'helper.log'})"
    )
    return 0


def _note_update_start() -> None:
    """Tell a waiting update helper that this launch is the new version (#385)."""
    try:
        from scanpath_studio import desktop_update

        desktop_update.note_start()
    except Exception:
        pass  # an update's bookkeeping must never stop a launch


def _confirm_boot_when_ready(port: int) -> None:
    """Once the server answers, confirm a pending update (#385) — even with no
    browser to open, so a headless relaunch confirms too."""
    if not _wait_for_server(f"http://127.0.0.1:{port}/_stcore/health"):
        return
    try:
        from scanpath_studio import desktop_update

        desktop_update.note_boot()
    except Exception:
        pass


def main() -> None:
    # First, before anything imports Streamlit or Tornado: they bind logging
    # handlers to sys.stderr at import time, and in the .app that stream is
    # /dev/null.
    log_path = _redirect_output_to_log()

    if "--selfcheck" in sys.argv[1:]:
        sys.exit(selfcheck())

    if "--update" in sys.argv[1:]:
        sys.exit(update())

    _note_update_start()

    port = _resolve_port()
    threading.Thread(target=_confirm_boot_when_ready, args=(port,), daemon=True).start()

    if not _env_flag("SCANPATH_DESKTOP_NO_BROWSER"):
        threading.Thread(
            target=_open_browser_when_ready, args=(port,), daemon=True
        ).start()

    grace_s = _idle_exit_grace()
    if grace_s > 0:
        threading.Thread(
            target=_watch_for_idle_exit, args=(grace_s,), daemon=True
        ).start()

    print(f"Scanpath Studio starting on http://127.0.0.1:{port}")
    if sys.platform == "win32":
        # ENG-90: the console is all a Windows user sees during the scan
        # HEALTH_TIMEOUT_S waits out, so say that the wait is expected.
        print(
            "This can take a few minutes, especially the first time while "
            "Windows scans the app. The window opens on its own when it's "
            "ready; please keep this terminal open."
        )
    if grace_s > 0:
        print(f"Close the app window to quit (the server stops {grace_s:.0f}s later).")
    else:
        print("Close this window (or press Ctrl+C) to quit.")
    if log_path is not None:
        print(f"Logging to {log_path}")

    from scanpath_studio.cli import launch_app

    # launch_app resolves the packaged app.py, injects the branded theme
    # (BUG-6), and hands off to `streamlit run` — one launch path shared with
    # `scanpath-studio run`, so fixes there reach the frozen app too.
    launch_app(
        [
            # Frozen Streamlit can misdetect development mode, which then
            # rejects an explicit --server.port; force it off.
            "--global.developmentMode=false",
            # headless=true stops Streamlit's own browser-open; we open it
            # after the health check instead (and not at all under the smoke
            # test).
            "--server.headless=true",
            f"--server.port={port}",
            # Loopback only. Streamlit's server.address default is unset and
            # falls back to 0.0.0.0, so without this the desktop bundle serves
            # the user's loaded corpus to every host on the LAN — and the app
            # has no authentication of any kind (DATA-13 S1).
            "--server.address=127.0.0.1",
            # No hot reload in a frozen app; the watcher only costs threads.
            "--server.fileWatcherType=none",
            "--browser.gatherUsageStats=false",
            # No Deploy button (UX-183) — see cli.launch_app.
            "--client.toolbarMode=viewer",
        ]
    )


if __name__ == "__main__":
    main()
