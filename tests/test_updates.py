"""Check for updates (#139): the GitHub lookup and the comparison."""

from __future__ import annotations

import io
import json
import urllib.error
from email.message import Message
from pathlib import Path

import pytest

from scanpath_studio import updates
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
        ("win32", "AMD64", "ScanpathStudio-windows-x86_64.zip"),
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
        assert f"archive: {name}" in workflow


def test_a_failed_check_is_a_result_not_an_exception():
    def offline():
        raise updates.UpdateCheckError(
            "Couldn't reach GitHub to check — are you offline?"
        )

    result = updates.check_for_updates(latest=offline, info=RELEASE, kind="pip")
    assert (result.status, result.latest) == ("error", None)
    assert "offline" in result.message
