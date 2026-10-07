"""Check for updates (#139): the GitHub lookup and the comparison."""

from __future__ import annotations

import http.client
import io
import json
import ssl
import urllib.error
from email.message import Message
from pathlib import Path

import pytest

from scanpath_studio import desktop_update, updates
from scanpath_studio.build_info import BuildInfo, from_describe

RELEASE = BuildInfo("0.35.0", "0.35.0")
DEV = from_describe("v0.35.0-3-g8f18219")
ROOT = Path(__file__).resolve().parents[1]


def _payload(tag="v0.36.0", assets=()):
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/lacclab/scanpath-studio/releases/tag/{tag}",
        "published_at": "2026-10-09T10:00:00Z",
        "assets": [
            {
                "name": name,
                "browser_download_url": f"https://example.test/{name}",
                "size": 1024,
                "digest": "sha256:ab",
            }
            for name in assets
        ],
    }


def _opener(payload=None, error=None):
    seen = []

    def opener(request, timeout):
        seen.append((request, timeout))
        if error is not None:
            raise error
        return io.BytesIO(json.dumps(payload).encode())

    opener.seen = seen
    return opener


def _http_error(code, headers=None):
    hdrs = Message()
    for key, value in (headers or {}).items():
        hdrs[key] = value
    return urllib.error.HTTPError(updates.LATEST_RELEASE_API, code, "nope", hdrs, None)


def _latest(tag="v0.36.0", assets=()):
    # Parsed directly, not through `latest_release`, which some tests replace.
    release = updates._release_from(_payload(tag, assets))
    return lambda: release


def test_latest_release_reads_githubs_answer():
    opener = _opener(_payload(assets=["ScanpathStudio-macos-arm64.dmg"]))
    release = updates.latest_release(3.0, opener=opener)
    assert (release.version, release.tag) == ("0.36.0", "v0.36.0")
    assert release.asset("ScanpathStudio-macos-arm64.dmg").digest == "sha256:ab"
    assert release.asset("nothing.zip") is None
    request, timeout = opener.seen[0]
    assert request.full_url == updates.LATEST_RELEASE_API
    assert timeout == 3.0
    assert request.get_header("User-agent").startswith("scanpath-studio/")


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (urllib.error.URLError("no route"), "are you offline"),
        (TimeoutError("slow"), "are you offline"),
        (http.client.IncompleteRead(b""), "are you offline"),
        (http.client.RemoteDisconnected("closed"), "are you offline"),
        (
            urllib.error.URLError(ssl.SSLCertVerificationError("bad cert")),
            "certificate",
        ),
        (ssl.SSLCertVerificationError("bad cert"), "certificate"),
        (
            _http_error(
                403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1791500000"}
            ),
            "limit on checks",
        ),
        (_http_error(404), "no published release"),
        (_http_error(502), "HTTP 502"),
    ],
)
def test_a_failed_lookup_says_why(error, reason):
    with pytest.raises(updates.UpdateCheckError, match=reason):
        updates.latest_release(opener=_opener(error=error))


def test_the_default_opener_verifies_tls_with_a_context(monkeypatch):
    seen = {}

    def fake_urlopen(request, **kwargs):
        seen.update(kwargs)
        return io.BytesIO(json.dumps(_payload()).encode())

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    assert updates.latest_release(2.0).version == "0.36.0"
    assert isinstance(seen["context"], ssl.SSLContext)
    assert seen["timeout"] == 2.0


@pytest.mark.parametrize(
    "payload", [[], {"assets": []}, {"tag_name": "v1", "assets": [{"name": "x"}]}]
)
def test_an_unreadable_answer_is_an_error_not_a_crash(payload):
    with pytest.raises(updates.UpdateCheckError, match="can't read"):
        updates.latest_release(opener=_opener(payload))


@pytest.mark.parametrize(
    ("info", "tag", "status"),
    [
        (RELEASE, "v0.35.0", "up_to_date"),
        (RELEASE, "v0.36.0", "update_available"),
        (DEV, "v0.35.0", "ahead"),
        (DEV, "v0.35.1", "update_available"),
        (BuildInfo("0.36.0b1", "0.36.0b1"), "v0.35.0", "ahead"),
    ],
)
def test_the_build_is_compared_with_the_latest_release(info, tag, status):
    result = updates.check_for_updates(latest=_latest(tag), info=info, kind="pip")
    assert result.status == status
    assert result.current == info.version


def test_an_update_names_the_command_for_this_install():
    result = updates.check_for_updates(latest=_latest(), info=DEV, kind="checkout")
    assert result.command == "git pull"
    assert result.message == (
        "v0.36.0 is out (released 9 Oct 2026); this is v0.35.0.post3+g8f18219."
    )
    assert result.latest.url.endswith("/releases/tag/v0.36.0")


def test_a_development_build_past_the_release_says_so():
    result = updates.check_for_updates(
        latest=_latest("v0.35.0"), info=DEV, kind="checkout"
    )
    assert result.message == (
        "Development build — 3 commits after v0.35.0, at 8f18219. "
        "The latest release is v0.35.0."
    )


@pytest.mark.parametrize(
    ("kind", "command"),
    [
        ("checkout", "git pull"),
        ("uv-tool", "uv tool upgrade scanpath-studio"),
        ("pipx", "pipx upgrade scanpath-studio"),
        ("uv", "uv pip install -U scanpath-studio"),
        ("pip", "pip install -U scanpath-studio"),
        ("desktop", ""),
    ],
)
def test_each_install_kind_has_its_command(kind, command):
    assert updates.update_command(kind, RELEASE) == command


def test_a_git_install_reinstalls_from_its_own_url():
    info = BuildInfo(
        "0.35.0+gabc1234",
        "0.35.0",
        None,
        "abc1234",
        source="vcs",
        vcs_url="https://github.com/someone/fork",
    )
    assert (
        updates.update_command("vcs", info)
        == 'pip install -U "git+https://github.com/someone/fork"'
    )


def test_the_desktop_app_gets_its_archive(monkeypatch):
    monkeypatch.setattr(
        updates, "desktop_archive", lambda: "ScanpathStudio-macos-arm64.dmg"
    )
    result = updates.check_for_updates(
        latest=_latest(
            assets=[
                "ScanpathStudio-macos-arm64.dmg",
                "ScanpathStudio-windows-x86_64.zip",
            ]
        ),
        info=RELEASE,
        kind="desktop",
    )
    assert result.download.name == "ScanpathStudio-macos-arm64.dmg"
    assert result.command == ""


def test_a_desktop_archive_not_yet_uploaded_says_so(monkeypatch):
    monkeypatch.setattr(
        updates, "desktop_archive", lambda: "ScanpathStudio-macos-arm64.dmg"
    )
    result = updates.check_for_updates(latest=_latest(), info=RELEASE, kind="desktop")
    assert result.status == "update_available"
    assert result.download is None
    assert "isn't on the release page yet" in result.message


def test_a_computer_with_no_desktop_build_is_told_so(monkeypatch):
    monkeypatch.setattr(updates, "desktop_archive", lambda: None)
    result = updates.check_for_updates(latest=_latest(), info=RELEASE, kind="desktop")
    assert "no desktop build for this computer" in result.message


@pytest.mark.parametrize(
    ("system", "machine", "name"),
    [
        ("darwin", "arm64", "ScanpathStudio-macos-arm64.dmg"),
        ("darwin", "x86_64", None),
        ("win32", "AMD64", "ScanpathStudio-windows-x86_64-setup.exe"),
        ("linux", "x86_64", "ScanpathStudio-linux-x86_64.tar.gz"),
        ("linux", "aarch64", None),
    ],
)
def test_desktop_archive_per_computer(system, machine, name):
    assert updates.desktop_archive(system, machine) == name


def test_the_archive_names_are_the_ones_desktop_yml_builds():
    workflow = (ROOT / ".github" / "workflows" / "desktop.yml").read_text(
        encoding="utf-8"
    )
    for name in set(updates.DESKTOP_ARCHIVES.values()):
        assert f"archive: {name}" in workflow or f"installer: {name}" in workflow


def test_a_failed_check_is_a_result_not_an_exception():
    def offline():
        raise updates.UpdateCheckError(
            "Couldn't reach GitHub to check — are you offline?"
        )

    result = updates.check_for_updates(latest=offline, info=RELEASE, kind="pip")
    assert (result.status, result.latest) == ("error", None)
    assert "offline" in result.message


def test_the_api_reports_the_build_and_checks(monkeypatch):
    import scanpath_studio as sps
    from scanpath_studio.build_info import build_info

    assert sps.version_info() == build_info()
    assert {"version_info", "check_for_updates"} <= set(sps.__all__)
    monkeypatch.setattr(
        updates, "latest_release", lambda timeout=5.0: _latest("v99.0.0")()
    )
    result = sps.check_for_updates(timeout=2.0)
    assert result.status == "update_available"
    assert result.latest.version == "99.0.0"


def _about_script():
    from scanpath_studio import app

    app._about_dialog()


def _local_run(monkeypatch, tag="v99.0.0"):
    """About on a loopback server, with GitHub answering `tag`."""
    from scanpath_studio import app

    monkeypatch.setattr(app, "server_bound_to_loopback", lambda: True)
    monkeypatch.setattr(updates, "latest_release", lambda timeout=5.0: _latest(tag)())
    app._latest_release_cached.clear()


def test_about_offers_check_for_updates_on_a_local_run(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _local_run(monkeypatch)
    at = AppTest.from_function(_about_script).run()
    assert not at.exception, at.exception
    at.button(key="about_check_updates").click().run()
    assert not at.exception, at.exception
    assert any("v99.0.0 is out" in info.value for info in at.info)
    # the command that updates this install
    assert any(code.language == "bash" and code.value for code in at.code)
    assert any("What's new in v99.0.0" in md.value for md in at.markdown)


def test_about_says_when_this_is_the_latest(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _local_run(monkeypatch)
    # Whether this tree is a release or a dev build depends on the checkout's
    # tags, so pin the answer rather than the comparison (covered above).
    monkeypatch.setattr(
        updates,
        "check_for_updates",
        lambda **kw: updates.UpdateCheck(
            "up_to_date", "0.35.0", "v0.35.0 is the latest release."
        ),
    )
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    assert not at.exception, at.exception
    assert any("is the latest release" in ok.value for ok in at.success)


def test_about_has_no_update_check_on_a_hosted_server(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import app

    monkeypatch.setattr(app, "server_bound_to_loopback", lambda: False)
    at = AppTest.from_function(_about_script).run()
    assert not at.exception, at.exception
    assert not [button for button in at.button if button.key == "about_check_updates"]


def _desktop_update_check(version="99.0.0"):
    release = updates._release_from(
        _payload(
            f"v{version}",
            [
                "ScanpathStudio-macos-arm64.dmg",
                "ScanpathStudio-windows-x86_64.zip",
                "ScanpathStudio-windows-x86_64-setup.exe",
                "ScanpathStudio-linux-x86_64.tar.gz",
            ],
        )
    )
    return updates.UpdateCheck(
        "update_available",
        "0.36.0",
        f"v{version} is out; this is v0.36.0.",
        latest=release,
        install_kind="desktop",
        download=release.assets[0],
    )


def _desktop_about(monkeypatch, *, refusal=None):
    _local_run(monkeypatch)
    monkeypatch.setattr(
        updates, "check_for_updates", lambda **kw: _desktop_update_check()
    )
    monkeypatch.setattr(desktop_update, "current_install", lambda: "INSTALL")
    monkeypatch.setattr(desktop_update, "refusal", lambda check, install: refusal)
    monkeypatch.setattr(desktop_update, "last_result", lambda: None)


def test_the_desktop_app_offers_update_and_restart(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _desktop_about(monkeypatch)
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    assert not at.exception, at.exception
    assert at.button(key="about_update_restart").label == "Update & restart"


def test_a_refused_update_says_why_and_still_offers_the_download(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _desktop_about(monkeypatch, refusal="This account can't change /Applications.")
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    assert not at.exception, at.exception
    assert not [b for b in at.button if b.key == "about_update_restart"]
    assert any("can't change" in caption.value for caption in at.caption)


def test_update_and_restart_swaps_then_quits(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _desktop_about(monkeypatch)
    calls = []
    monkeypatch.setattr(
        desktop_update,
        "prepare",
        lambda check, install: (
            calls.append("prepare")
            or desktop_update.SwapPlan(
                1, None, Path("/s"), Path("/st"), "99.0.0", "0.36.0", ("x",)
            )
        ),
    )
    monkeypatch.setattr(desktop_update, "start_swap", lambda plan: calls.append("swap"))
    monkeypatch.setattr(desktop_update, "exit_soon", lambda: calls.append("exit"))
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    at.button(key="about_update_restart").click().run()
    assert not at.exception, at.exception
    assert calls == ["prepare", "swap", "exit"]
    assert any("Restarting into v99.0.0" in ok.value for ok in at.success)


def test_a_failed_update_changes_nothing_and_says_so(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _desktop_about(monkeypatch)

    def fail(check, install):
        raise desktop_update.UpdateFailed("The download stopped before it finished.")

    monkeypatch.setattr(desktop_update, "prepare", fail)
    monkeypatch.setattr(desktop_update, "exit_soon", lambda: pytest.fail("quit"))
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    at.button(key="about_update_restart").click().run()
    assert not at.exception, at.exception
    assert any("stopped before it finished" in e.value for e in at.error)
    assert any("Nothing was changed" in e.value for e in at.error)


@pytest.mark.parametrize(
    ("result", "where", "says"),
    [
        (
            ("rolled_back", "the new version did not start within 180 seconds"),
            "warning",
            "didn't go through",
        ),
        (("updated", ""), "caption", "Updated from v0.35.0"),
    ],
)
def test_about_reports_how_the_last_update_ended(monkeypatch, result, where, says):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import app

    _local_run(monkeypatch)
    status, reason = result
    monkeypatch.setattr(
        desktop_update,
        "last_result",
        lambda: desktop_update.UpdateResult(status, "0.36.0", "0.35.0", reason),
    )
    monkeypatch.setattr(app, "_build_info", lambda: BuildInfo("0.36.0", "0.36.0"))
    at = AppTest.from_function(_about_script).run()
    assert not at.exception, at.exception
    assert any(says in element.value for element in getattr(at, where))
