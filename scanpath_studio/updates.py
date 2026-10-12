"""Is there a newer Scanpath Studio than this build? (#139)

Asked only when someone clicks *Check for updates* (Help → About), runs
``scanpath-studio version --check`` or calls ``api.check_for_updates`` — never
on its own (docs/privacy.md → *Network activity*). One source serves every
install: GitHub's latest release, which leaves out drafts and pre-releases and
lists each desktop archive with its sha256. :func:`check_for_updates` never
raises; a check that could not be made says why in ``UpdateCheck.message``.
"""

from __future__ import annotations

import http.client
import json
import platform
import ssl
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import truststore
from packaging.version import InvalidVersion, Version

from .build_info import BuildInfo, build_info, install_kind

REPO = "lacclab/scanpath-studio"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
TIMEOUT_S = 5.0

#: The shell command that updates each kind of install (``build_info.INSTALL_KINDS``);
#: ``vcs`` is built from the URL pip recorded, and the desktop app downloads.
UPDATE_COMMANDS = {
    "checkout": "git pull",
    "uv-tool": "uv tool upgrade scanpath-studio",
    "pipx": "pipx upgrade scanpath-studio",
    "uv": "uv pip install -U scanpath-studio",
    "pip": "pip install -U scanpath-studio",
}

#: Each release's desktop download per (platform, machine) — the names
#: ``.github/workflows/desktop.yml`` gives them. There is no Intel Mac build.
#: Windows people get the per-user installer; the ``.zip`` stays on releases as
#: the folder #385's updater swaps.
DESKTOP_ARCHIVES = {
    ("darwin", "arm64"): "ScanpathStudio-macos-arm64.dmg",
    ("win32", "amd64"): "ScanpathStudio-windows-x86_64-setup.exe",
    ("win32", "x86_64"): "ScanpathStudio-windows-x86_64-setup.exe",
    ("linux", "x86_64"): "ScanpathStudio-linux-x86_64.tar.gz",
}

_OFFLINE = "Couldn't reach GitHub to check — are you offline?"
_BAD_CERT = (
    "GitHub's certificate couldn't be verified on this computer, so the check "
    "was not made."
)
_UNREADABLE = (
    "GitHub sent an answer this version of the app can't read; try again later."
)


@dataclass(frozen=True)
class Asset:
    """One file attached to a release; ``digest`` is ``"sha256:<hex>"`` or ``""``."""

    name: str
    url: str
    size: int = 0
    digest: str = ""


@dataclass(frozen=True)
class Release:
    """A published release: ``version`` is the tag without its ``v``, ``url`` its page."""

    version: str
    tag: str
    published_at: str
    url: str
    assets: tuple[Asset, ...] = ()

    def asset(self, name: str) -> Asset | None:
        """The attached file called ``name``, if the release has it yet."""
        return next((asset for asset in self.assets if asset.name == name), None)


@dataclass(frozen=True)
class UpdateCheck:
    """The answer to "is there a newer release than this build?".

    ``status`` is ``"up_to_date"``, ``"update_available"``, ``"ahead"`` (a
    development build past the latest release) or ``"error"`` (the check could
    not be made); ``message`` says it in a sentence. With an update available,
    ``command`` is the shell command that updates this install or, in the
    desktop app, ``download`` is this computer's archive (``None`` until the
    release's desktop builds are uploaded).
    """

    status: str
    current: str
    message: str
    latest: Release | None = None
    install_kind: str = "pip"
    command: str = ""
    download: Asset | None = None


class UpdateCheckError(Exception):
    """A check that could not be made; ``str()`` is the reason, for people."""


def _ssl_context() -> ssl.SSLContext:
    """TLS trust for the request: what the operating system trusts (#391).

    Python's own defaults read OpenSSL's CA list, which a python.org install
    on macOS ships empty and a frozen desktop build may not find at all, and
    which never holds the root a TLS-inspecting campus or company proxy
    re-signs with. `truststore` verifies against the macOS Keychain, the
    Windows certificate store or the system bundle instead, as the browser
    does — the same trust ``datasets._open_url`` uses for downloads.
    """
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def _urlopen(request: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context())


def latest_release(
    timeout: float = TIMEOUT_S, *, opener: Callable | None = None
) -> Release:
    """GitHub's latest release of Scanpath Studio. Raises :class:`UpdateCheckError`.

    ``opener(request, timeout)`` replaces the HTTP call (tests pass a fake).
    """
    opener = _urlopen if opener is None else opener
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"scanpath-studio/{build_info().version}",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise UpdateCheckError(_http_reason(error)) from error
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as error:
        if isinstance(error, ssl.SSLCertVerificationError) or isinstance(
            getattr(error, "reason", None), ssl.SSLCertVerificationError
        ):
            raise UpdateCheckError(_BAD_CERT) from error
        raise UpdateCheckError(_OFFLINE) from error
    except (
        OSError,
        http.client.HTTPException,
    ) as error:  # a refused connection, a timeout, a dropped answer
        raise UpdateCheckError(_OFFLINE) from error
    except ValueError as error:
        raise UpdateCheckError(_UNREADABLE) from error
    return _release_from(payload)


def _http_reason(error: urllib.error.HTTPError) -> str:
    headers = error.headers or {}
    if (
        error.code in (403, 429)
        and str(headers.get("X-RateLimit-Remaining", "")) == "0"
    ):
        try:
            reset = datetime.fromtimestamp(int(headers.get("X-RateLimit-Reset")))
            when = f" after {reset:%H:%M}"
        except (TypeError, ValueError, OverflowError, OSError):
            when = " later"
        return (
            f"GitHub's limit on checks from this network is used up; try again{when}."
        )
    if error.code == 404:
        return "GitHub lists no published release of Scanpath Studio."
    return f"GitHub answered with an error (HTTP {error.code}); try again later."


def _release_from(payload: object) -> Release:
    try:
        tag = str(payload["tag_name"])
        assets = tuple(
            Asset(
                name=str(item["name"]),
                url=str(item["browser_download_url"]),
                size=int(item.get("size") or 0),
                digest=str(item.get("digest") or ""),
            )
            for item in payload.get("assets") or ()
        )
        return Release(
            version=tag.removeprefix("v"),
            tag=tag,
            published_at=str(payload.get("published_at") or ""),
            url=str(payload.get("html_url") or RELEASES_PAGE),
            assets=assets,
        )
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise UpdateCheckError(_UNREADABLE) from error


def desktop_archive(
    system: str | None = None, machine: str | None = None
) -> str | None:
    """This computer's desktop archive name, or ``None`` where there is no build."""
    system = sys.platform if system is None else system
    machine = (platform.machine() if machine is None else machine).lower()
    if system.startswith("linux"):
        system = "linux"
    return DESKTOP_ARCHIVES.get((system, machine))


def update_command(kind: str, info: BuildInfo) -> str:
    """The shell command that updates this kind of install; ``""`` for the desktop app."""
    if kind == "vcs":
        url = info.vcs_url or f"https://github.com/{REPO}"
        return f'pip install -U "git+{url}"'
    return UPDATE_COMMANDS.get(kind, "")


def _released_on(iso: str) -> str:
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return f"{when.day} {when:%b %Y}"


def check_for_updates(
    timeout: float = TIMEOUT_S,
    *,
    latest: Callable[[], Release] | None = None,
    info: BuildInfo | None = None,
    kind: str | None = None,
) -> UpdateCheck:
    """Compare this build with GitHub's latest release. Never raises.

    ``latest`` replaces the GitHub request (the app passes a cached one, tests a
    fake); ``info`` and ``kind`` default to this process's build and install.
    """
    info = build_info() if info is None else info
    kind = install_kind(info) if kind is None else kind
    try:
        release = latest() if latest is not None else latest_release(timeout)
    except UpdateCheckError as error:
        return UpdateCheck("error", info.version, str(error), install_kind=kind)
    try:
        newest, current = Version(release.version), Version(info.version)
    except InvalidVersion:
        return UpdateCheck(
            "error",
            info.version,
            f"GitHub's latest release, {release.tag}, isn't a version this app "
            "can compare.",
            latest=release,
            install_kind=kind,
        )
    if newest == current:
        return UpdateCheck(
            "up_to_date",
            info.version,
            f"v{release.version} is the latest release.",
            latest=release,
            install_kind=kind,
        )
    if newest < current:
        return UpdateCheck(
            "ahead",
            info.version,
            f"{info.describe()}. The latest release is v{release.version}.",
            latest=release,
            install_kind=kind,
        )
    released = _released_on(release.published_at)
    message = (
        f"v{release.version} is out"
        + (f" (released {released})" if released else "")
        + f"; this is v{info.version}."
    )
    if kind != "desktop":
        return UpdateCheck(
            "update_available",
            info.version,
            message,
            latest=release,
            install_kind=kind,
            command=update_command(kind, info),
        )
    name = desktop_archive()
    download = release.asset(name) if name else None
    if download is None:
        message += (
            " Its download for this computer isn't on the release page yet; "
            "desktop builds are uploaded up to an hour after a release."
            if name
            else " There is no desktop build for this computer; see the release page."
        )
    return UpdateCheck(
        "update_available",
        info.version,
        message,
        latest=release,
        install_kind=kind,
        download=download,
    )
