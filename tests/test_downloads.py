"""UX-168: corpus downloads report bytes and stop cleanly on Cancel."""

from __future__ import annotations

import http.client
import io
import zipfile
from pathlib import Path

import pytest
import truststore

from scanpath_studio import datasets, progress


class _Response(io.BytesIO):
    """A response body. ``read1`` — what the downloads read with — returns what
    has arrived, up to the size asked; ``on_read`` fires after each one.

    ``promised`` is the ``Content-Length`` it announces, when that is not the
    body's own length (a connection that ends early); ``fail`` is raised by the
    read after the body runs out, as `http.client` does for a chunked body cut
    short."""

    def __init__(
        self,
        data: bytes,
        *,
        length: bool = True,
        promised: int | None = None,
        on_read=None,
        fail: BaseException | None = None,
    ):
        super().__init__(data)
        announced = len(data) if promised is None else promised
        self.headers = {"Content-Length": str(announced)} if length else {}
        self._on_read = on_read
        self._fail = fail
        self.reads: list[str] = []

    def read(self, size=-1):
        self.reads.append("read")
        return super().read(size)

    def read1(self, size=-1):
        self.reads.append("read1")
        chunk = super().read1(size)
        if not chunk and self._fail is not None:
            raise self._fail
        if self._on_read is not None:
            self._on_read()
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _serving(response: _Response, opened: list | None = None):
    """An `urlopen` that hands back ``response``, noting each call's timeout."""

    def urlopen(url, timeout=None, context=None):
        if opened is not None:
            opened.append(timeout)
            opened.append(context)
        return response

    return urlopen


@pytest.mark.parametrize("fetch", ["to_file", "bytes"])
def test_a_download_reads_what_has_arrived_and_times_out(monkeypatch, tmp_path, fetch):
    """Stop acts at the next checkpoint, which a download reaches once a read
    returns — and ``read(n)`` waits for all *n* bytes: ~10 s for a MiB at
    100 KB/s. ``read1`` returns whatever has arrived. A connection that stalls
    outright times out instead of hanging for good, as the `OSError` both
    download buttons already report."""
    response, opened = _Response(b"z" * 10), []
    monkeypatch.setattr(datasets.urllib.request, "urlopen", _serving(response, opened))
    if fetch == "to_file":
        datasets._fetch_to_file(
            "https://example.invalid/r", tmp_path / "r.zip", detail="IA report"
        )
    else:
        datasets._fetch_bytes("https://example.invalid/r", detail="archive")
    timeout, context = opened
    assert timeout is not None
    assert timeout == datasets._DOWNLOAD_TIMEOUT_S
    # HTTPS is verified against the OS certificate store, not OpenSSL's CA
    # list — which a python.org Python on macOS ships empty, so every download
    # failed there with CERTIFICATE_VERIFY_FAILED.
    assert isinstance(context, truststore.SSLContext)
    assert response.reads and set(response.reads) == {"read1"}


def test_a_download_reports_bytes_and_lands_atomically(monkeypatch, tmp_path):
    monkeypatch.setattr(datasets, "_DOWNLOAD_CHUNK", 4)
    monkeypatch.setattr(
        datasets.urllib.request, "urlopen", _serving(_Response(b"x" * 10))
    )
    dest = tmp_path / "report.csv.zip"
    with progress.task(("t", "dl"), title="Downloading") as task:
        datasets._fetch_to_file("https://example.invalid/r", dest, detail="IA report")
    assert dest.read_bytes() == b"x" * 10
    assert not dest.with_name(dest.name + ".part").exists()
    snap = task.snapshot()
    assert (snap.done, snap.total, snap.unit, snap.detail) == (
        10,
        10,
        "bytes",
        "IA report",
    )


def test_cancelling_mid_download_leaves_no_file_behind(monkeypatch, tmp_path):
    monkeypatch.setattr(datasets, "_DOWNLOAD_CHUNK", 4)
    key = ("t", "dl-cancel")
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        _serving(_Response(b"x" * 12, on_read=lambda: progress.cancel(key))),
    )
    dest = tmp_path / "report.csv.zip"
    with progress.task(key, title="Downloading"):
        with pytest.raises(progress.Cancelled):
            datasets._fetch_to_file(
                "https://example.invalid/r", dest, detail="IA report"
            )
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_fetch_bytes_without_a_length_still_reports(monkeypatch):
    monkeypatch.setattr(datasets, "_DOWNLOAD_CHUNK", 4)
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        _serving(_Response(b"y" * 9, length=False)),
    )
    with progress.task(("t", "bytes"), title="Downloading") as task:
        assert (
            datasets._fetch_bytes("https://example.invalid/z", detail="archive")
            == b"y" * 9
        )
    assert task.snapshot().done == 9 and task.snapshot().total is None


def test_a_cancelled_unpack_leaves_no_partial_corpus(monkeypatch, tmp_path):
    """A half-unpacked `scanpaths/` would pass `potec_present`'s "any .tsv"
    check and load as a silently partial corpus — so it unpacks to a staging
    folder and is renamed into place only when complete."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        for reader in range(3):
            z.writestr(f"scanpaths/reader{reader}_b0_scanpath.tsv", "a\tb\n1\t2\n")
    key = ("t", "unpack")
    real_report = progress.report
    seen = {"calls": 0}

    def report(done=None, total=None, **kwargs):
        seen["calls"] += 1
        if seen["calls"] == 2:
            progress.cancel(key)
        real_report(done, total, **kwargs)

    monkeypatch.setattr(
        datasets, "_fetch_bytes", lambda url, *, detail: archive.getvalue()
    )
    monkeypatch.setattr(datasets, "_check_download_size", lambda *a: None)
    monkeypatch.setattr(progress, "report", report)
    with progress.task(key, title="Downloading PoTeC"):
        with pytest.raises(progress.Cancelled):
            datasets.download_potec(tmp_path)
    assert not (tmp_path / "eyetracking_data" / "scanpaths").exists()
    assert not list((tmp_path / "eyetracking_data").glob(".*.part"))


def test_an_archive_without_the_fixation_files_fails_with_a_clear_message(
    monkeypatch, tmp_path
):
    """If the OSF archive ever stops carrying `scanpaths/*.tsv`, the download
    must say so — not fail on the hidden staging folder's path — and leave
    nothing behind that could pass for the corpus."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("__MACOSX/._scanpaths", "cruft")
        z.writestr("readme.txt", "no fixation files here")
    monkeypatch.setattr(
        datasets, "_fetch_bytes", lambda url, *, detail: archive.getvalue()
    )
    monkeypatch.setattr(datasets, "_check_download_size", lambda *a: None)
    with pytest.raises(ValueError, match="scanpaths"):
        datasets.download_potec(tmp_path)
    assert not (tmp_path / "eyetracking_data" / "scanpaths").exists()
    assert not list((tmp_path / "eyetracking_data").glob(".*.part"))


# UX-168 / FR-1 — a download cut short is an error, never a file.


def test_a_download_that_ends_early_is_an_error_and_leaves_no_file(
    monkeypatch, tmp_path
):
    """`read1` returns ``b""`` on an early EOF — a server, proxy or load balancer
    closing the connection mid-body — just as it does at the real end, so the
    loop alone can't tell them apart. Committed, the half file passed for the
    report: the ⬇ button went away and every load failed until a manual delete."""
    monkeypatch.setattr(datasets, "_DOWNLOAD_CHUNK", 32)
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        _serving(_Response(b"x" * 100, promised=200)),
    )
    dest = tmp_path / "report.csv.zip"
    with pytest.raises(OSError, match="stopped at 100 of 200 bytes"):
        datasets._fetch_to_file("https://example.invalid/r", dest, detail="IA report")
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_an_archive_that_ends_early_is_an_error(monkeypatch):
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        _serving(_Response(b"x" * 100, promised=200)),
    )
    with pytest.raises(OSError, match="stopped at 100 of 200 bytes"):
        datasets._fetch_bytes("https://example.invalid/z", detail="archive")


@pytest.mark.parametrize("fetch", ["to_file", "bytes"])
def test_a_chunked_body_cut_short_is_a_connection_error(monkeypatch, tmp_path, fetch):
    """A chunked body cut short raises `http.client.IncompleteRead` — an
    `HTTPException`, not an `OSError` — which neither ⬇ button catches: a raw
    traceback. As a `ConnectionError` it takes the same path as any failure."""
    cut = http.client.IncompleteRead(b"")
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        _serving(_Response(b"x" * 10, length=False, fail=cut)),
    )
    dest = tmp_path / "report.csv.zip"
    with pytest.raises(ConnectionError) as raised:
        if fetch == "to_file":
            datasets._fetch_to_file("https://example.invalid/r", dest, detail="IA")
        else:
            datasets._fetch_bytes("https://example.invalid/r", detail="archive")
    assert raised.value.__cause__ is cut
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_an_archive_that_is_not_a_zip_is_a_value_error(monkeypatch, tmp_path):
    """A damaged archive raised `zipfile.BadZipFile`, which neither ⬇ button
    catches; a `ValueError` naming the archive is reported like the rest."""
    monkeypatch.setattr(
        datasets, "_fetch_bytes", lambda url, *, detail: b"<html>not a zip</html>"
    )
    # Past DATA-65's size pin, so the unpack is what is tested.
    monkeypatch.setattr(datasets, "_check_download_size", lambda *a: None)
    with pytest.raises(ValueError, match="PoTeC archive") as raised:
        datasets.download_potec(tmp_path)
    assert isinstance(raised.value.__cause__, zipfile.BadZipFile)
    assert not (tmp_path / "eyetracking_data" / "scanpaths").exists()
    assert not list((tmp_path / "eyetracking_data").glob(".*.part"))


def test_a_cleanup_that_fails_never_masks_the_original_error(monkeypatch, tmp_path):
    """The ``.part`` cleanup runs while another error is on its way out; if it
    fails in turn, the caller must still see *that* error, not the cleanup's."""
    real_unlink = Path.unlink

    def unlink(self, missing_ok=False):
        if self.name.endswith(".part"):
            raise PermissionError(f"{self.name} is locked")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        _serving(_Response(b"", fail=ConnectionResetError("reset by peer"))),
    )
    with pytest.raises(ConnectionResetError, match="reset by peer"):
        datasets._fetch_to_file(
            "https://example.invalid/r", tmp_path / "report.csv.zip", detail="IA"
        )
