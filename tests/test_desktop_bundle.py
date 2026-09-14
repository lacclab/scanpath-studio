"""ENG-21: the macOS .app bundle's paths, logging and quit gesture.

The icon assertions and the signature gate stay in ``test_desktop_icon.py``;
this file covers what the signed bundle added.
"""

from __future__ import annotations

import pytest

from desktop import launcher, smoke_test


class _Exhausted(Exception):
    """The watcher asked for more polls than the test scripted — i.e. it never exited."""


class _Exited(Exception):
    """Stands in for ``os._exit`` so the watcher's exit is observable."""


def _scripted_counts(values):
    remaining = list(values)

    def next_count():
        if not remaining:
            raise _Exhausted
        return remaining.pop(0)

    return next_count


@pytest.fixture
def watcher(monkeypatch):
    """Run ``_watch_for_idle_exit`` with no real sleeping and a stepped clock."""
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)

    def _run(counts, grace_s=30.0, step_s=10.0):
        ticks = iter(range(0, 10_000, int(step_s)))
        monkeypatch.setattr(launcher.time, "monotonic", lambda: float(next(ticks)))
        monkeypatch.setattr(launcher, "_active_session_count", _scripted_counts(counts))

        def fake_exit(code):
            raise _Exited(code)

        monkeypatch.setattr(launcher.os, "_exit", fake_exit)
        launcher._watch_for_idle_exit(grace_s)

    return _run


# --------------------------------------------------------------------------
# Where the built artifact is


def test_default_binary_is_the_app_bundle_on_macos(monkeypatch):
    # The bundle, not dist/ScanpathStudio/ — PyInstaller's COLLECT leaves that
    # folder in place beside the .app, so the old path would still resolve and
    # the smoke test would pass against the artifact CI never ships.
    monkeypatch.setattr(smoke_test.sys, "platform", "darwin")
    assert smoke_test._default_binary().name == "ScanpathStudio.app"


@pytest.mark.parametrize(
    ("platform", "expected"),
    [("linux", "ScanpathStudio"), ("win32", "ScanpathStudio.exe")],
)
def test_default_binary_is_the_onedir_executable_elsewhere(
    monkeypatch, platform, expected
):
    monkeypatch.setattr(smoke_test.sys, "platform", platform)
    binary = smoke_test._default_binary()
    assert binary.name == expected
    assert binary.parent.name == "ScanpathStudio"


def test_executable_resolves_inside_the_app_bundle(tmp_path):
    bundle = tmp_path / "ScanpathStudio.app"
    (bundle / "Contents" / "MacOS").mkdir(parents=True)
    assert smoke_test._executable(bundle) == (
        bundle / "Contents" / "MacOS" / "ScanpathStudio"
    )


def test_executable_passes_a_plain_binary_through(tmp_path):
    binary = tmp_path / "ScanpathStudio"
    binary.touch()
    assert smoke_test._executable(binary) == binary


def test_executable_rejects_a_onedir_folder_by_name(tmp_path):
    # dist/ScanpathStudio/ is a directory too; running it would die inside Popen
    # with a bare PermissionError that names nothing useful.
    folder = tmp_path / "ScanpathStudio"
    folder.mkdir()
    with pytest.raises(SystemExit, match="not a .app bundle"):
        smoke_test._executable(folder)


# --------------------------------------------------------------------------
# Quitting when the last tab closes


def test_streamlit_active_session_seam_still_exists():
    """Pin the seam the quit gesture reads — *including* its private half.

    ``_active_session_count`` swallows every exception so the app never quits on
    a signal it cannot read, which means a Streamlit upgrade that moved this
    would break quitting *silently*. Fail here instead.

    The private half is the load-bearing one: ``num_active_sessions`` is public
    on ``SessionManager``, but the manager is only reachable through
    ``Runtime._session_mgr``, which is assigned in ``__init__`` rather than
    declared on the class — so it takes reading the bytecode's names to pin it
    without standing a Runtime up.
    """
    from streamlit.runtime import Runtime
    from streamlit.runtime.session_manager import SessionManager

    assert hasattr(Runtime, "exists")
    assert hasattr(Runtime, "instance")
    assert hasattr(SessionManager, "num_active_sessions")
    assert "_session_mgr" in Runtime.__init__.__code__.co_names


def test_watcher_exits_once_the_last_session_has_been_gone_for_the_grace(watcher):
    # zero (before any session) → one → gone; the clock steps 10s per idle poll,
    # so the 30s grace elapses on the fourth idle poll.
    with pytest.raises(_Exited):
        watcher([0, 1, 0, 0, 0, 0], grace_s=30.0, step_s=10.0)


def test_watcher_never_exits_before_a_session_has_connected(watcher):
    # The smoke test and `--server.headless` launches never open a browser;
    # quitting `grace_s` after boot would kill them.
    with pytest.raises(_Exhausted):
        watcher([0] * 12, grace_s=30.0, step_s=10.0)


def test_watcher_rearms_when_a_session_comes_back(watcher):
    # A page reload drops the session for about a second. Anything short of the
    # full grace must reset the timer, not accumulate toward it.
    with pytest.raises(_Exhausted):
        watcher([1, 0, 0, 1, 0, 0, 1, 0, 0], grace_s=30.0, step_s=10.0)


def test_watcher_treats_an_unreadable_count_as_unknown_not_idle(watcher):
    # None is "the runtime isn't up yet, or the seam moved". Quitting on that
    # would turn a Streamlit upgrade into an app that exits on launch.
    with pytest.raises(_Exhausted):
        watcher([1, None, None, None, None, None], grace_s=30.0, step_s=10.0)


def test_active_session_count_is_none_when_no_runtime_is_running():
    assert launcher._active_session_count() is None


# --------------------------------------------------------------------------
# When the quit gesture and the log redirect are armed


def test_idle_exit_is_off_outside_the_macos_app_bundle(monkeypatch):
    # Linux and Windows keep a console window whose closing already stops the
    # server; arming this there would be a behaviour change, not a fix.
    monkeypatch.delenv("SCANPATH_DESKTOP_IDLE_EXIT_S", raising=False)
    monkeypatch.setattr(launcher, "_in_macos_app_bundle", lambda: False)
    assert launcher._idle_exit_grace() == 0.0


def test_idle_exit_defaults_on_inside_the_app_bundle(monkeypatch):
    monkeypatch.delenv("SCANPATH_DESKTOP_IDLE_EXIT_S", raising=False)
    monkeypatch.setattr(launcher, "_in_macos_app_bundle", lambda: True)
    assert launcher._idle_exit_grace() == launcher.IDLE_EXIT_GRACE_S


@pytest.mark.parametrize(("raw", "expected"), [("0", 0.0), ("5", 5.0), ("2.5", 2.5)])
def test_idle_exit_grace_honours_the_env_var(monkeypatch, raw, expected):
    monkeypatch.setenv("SCANPATH_DESKTOP_IDLE_EXIT_S", raw)
    assert launcher._idle_exit_grace() == expected


@pytest.mark.parametrize("raw", ["soon", "inf", "-inf", "nan", "-5"])
def test_idle_exit_grace_falls_back_on_anything_not_a_duration(monkeypatch, raw):
    # float() accepts "inf" and "nan", and a negative would read as "disabled"
    # only by accident — all of them must be rejected like plain junk rather
    # than silently changing when the app quits.
    monkeypatch.setenv("SCANPATH_DESKTOP_IDLE_EXIT_S", raw)
    monkeypatch.setattr(launcher, "_in_macos_app_bundle", lambda: True)
    assert launcher._idle_exit_grace() == launcher.IDLE_EXIT_GRACE_S


def test_idle_grace_default_outlasts_streamlits_session_retention():
    """The default must exceed Streamlit's own reconnect window.

    A disconnected session stays restorable in MemorySessionStorage for
    ttl_seconds (2 minutes), so a shorter grace would tear down a session the
    framework would still have handed back — a browser that drops the socket and
    reconnects, or a discarded background tab.
    """
    import inspect

    from streamlit.runtime.memory_session_storage import MemorySessionStorage

    ttl = (
        inspect.signature(MemorySessionStorage.__init__)
        .parameters["ttl_seconds"]
        .default
    )
    assert launcher.IDLE_EXIT_GRACE_S > ttl


@pytest.mark.parametrize(
    ("platform", "frozen", "executable", "expected"),
    [
        ("darwin", True, "/A/ScanpathStudio.app/Contents/MacOS/ScanpathStudio", True),
        ("darwin", True, "/A/dist/ScanpathStudio/ScanpathStudio", False),
        ("darwin", False, "/A/ScanpathStudio.app/Contents/MacOS/ScanpathStudio", False),
        ("linux", True, "/A/ScanpathStudio.app/Contents/MacOS/ScanpathStudio", False),
    ],
)
def test_app_bundle_detection(monkeypatch, platform, frozen, executable, expected):
    monkeypatch.setattr(launcher.sys, "platform", platform)
    monkeypatch.setattr(launcher.sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(launcher.sys, "executable", executable)
    assert launcher._in_macos_app_bundle() is expected


def test_oversized_log_is_rotated_not_deleted(tmp_path, monkeypatch):
    # Deleting would throw away the session a bug report is about, which is
    # exactly the one that just filled the file.
    monkeypatch.setattr(launcher, "LOG_MAX_BYTES", 10)
    log = tmp_path / "scanpath-studio.log"
    log.write_text("x" * 50)
    launcher._rotate_if_large(log)
    assert not log.exists()
    assert (tmp_path / "scanpath-studio.log.1").read_text() == "x" * 50


def test_small_log_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "LOG_MAX_BYTES", 1000)
    log = tmp_path / "scanpath-studio.log"
    log.write_text("still small")
    launcher._rotate_if_large(log)
    assert log.read_text() == "still small"
    assert not (tmp_path / "scanpath-studio.log.1").exists()


def test_selfcheck_child_is_told_not_to_redirect_its_output(monkeypatch, tmp_path):
    """Regression: the selfcheck child is the binary *inside* the .app.

    Without an explicit env the launcher would redirect before reaching the
    --selfcheck branch, and `capture_output=True` makes stdout a pipe so the
    isatty() escape does not fire either — so the traceback this phase exists to
    surface would land in ~/Library/Logs on a throwaway runner, leaving CI red
    with no reason attached.
    """
    seen = {}

    class Result:
        returncode = 0
        stdout = "selfcheck ok"
        stderr = ""

    def fake_run(command, **kwargs):
        seen.update(kwargs)
        return Result()

    monkeypatch.setattr(smoke_test.subprocess, "run", fake_run)
    smoke_test._run_selfcheck(tmp_path / "ScanpathStudio")
    assert seen["env"]["SCANPATH_DESKTOP_NO_LOG_FILE"] == "1"
    assert seen["env"]["SCANPATH_DESKTOP_IDLE_EXIT_S"] == "0"


def test_log_redirect_is_skipped_when_asked(monkeypatch):
    # The smoke test sets this: it runs the executable inside the .app, which is
    # otherwise exactly the launcher's cue to redirect, and the server log it
    # diagnoses failures from would vanish into ~/Library/Logs.
    monkeypatch.setenv("SCANPATH_DESKTOP_NO_LOG_FILE", "1")
    monkeypatch.setattr(launcher, "_in_macos_app_bundle", lambda: True)
    assert launcher._redirect_output_to_log() is None


def test_log_redirect_is_skipped_outside_the_app_bundle(monkeypatch):
    monkeypatch.delenv("SCANPATH_DESKTOP_NO_LOG_FILE", raising=False)
    monkeypatch.setattr(launcher, "_in_macos_app_bundle", lambda: False)
    assert launcher._redirect_output_to_log() is None


# --------------------------------------------------------------------------
# The notarization gate


def test_notarization_check_is_skipped_without_the_expectation(monkeypatch, tmp_path):
    # An unsigned fork build has no ticket and must still pass the smoke test.
    monkeypatch.delenv("SCANPATH_EXPECT_NOTARIZED", raising=False)
    monkeypatch.setattr(smoke_test.sys, "platform", "darwin")
    monkeypatch.setattr(
        smoke_test.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("should not shell out"),
    )
    smoke_test._verify_notarization(tmp_path / "ScanpathStudio.app")


def test_notarization_check_requires_a_stapled_ticket(monkeypatch, tmp_path):
    monkeypatch.setenv("SCANPATH_EXPECT_NOTARIZED", "1")
    monkeypatch.setattr(smoke_test.sys, "platform", "darwin")

    class Result:
        returncode = 1
        stdout = ""
        stderr = "does not have a ticket stapled to it"

    monkeypatch.setattr(smoke_test.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(SystemExit, match="stapler validate FAILED"):
        smoke_test._verify_notarization(tmp_path / "ScanpathStudio.app")


def test_notarization_check_rejects_a_merely_signed_bundle(monkeypatch, tmp_path):
    """spctl accepting is not enough — it must accept it *as notarized*.

    A Developer ID signature with no ticket can still be accepted locally, which
    is exactly the state that fails on a downloader's machine.
    """
    monkeypatch.setenv("SCANPATH_EXPECT_NOTARIZED", "1")
    monkeypatch.setattr(smoke_test.sys, "platform", "darwin")

    class Result:
        returncode = 0
        stdout = "accepted\nsource=Developer ID\n"
        stderr = ""

    monkeypatch.setattr(smoke_test.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(SystemExit, match="not as notarized"):
        smoke_test._verify_notarization(tmp_path / "ScanpathStudio.app")


def test_notarization_check_passes_on_a_notarized_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("SCANPATH_EXPECT_NOTARIZED", "1")
    monkeypatch.setattr(smoke_test.sys, "platform", "darwin")

    class Result:
        returncode = 0
        stdout = "accepted\nsource=Notarized Developer ID\n"
        stderr = ""

    monkeypatch.setattr(smoke_test.subprocess, "run", lambda *a, **k: Result())
    smoke_test._verify_notarization(tmp_path / "ScanpathStudio.app")
