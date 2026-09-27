"""UX-168: corpus downloads report bytes and stop cleanly on Cancel."""

from __future__ import annotations

import io
import zipfile

import pytest

from scanpath_studio import datasets, progress


class _Response(io.BytesIO):
    def __init__(self, data: bytes, *, length: bool = True, on_read=None):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))} if length else {}
        self._on_read = on_read

    def read(self, size=-1):
        chunk = super().read(size)
        if self._on_read is not None:
            self._on_read()
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_a_download_reports_bytes_and_lands_atomically(monkeypatch, tmp_path):
    monkeypatch.setattr(datasets, "_DOWNLOAD_CHUNK", 4)
    monkeypatch.setattr(
        datasets.urllib.request, "urlopen", lambda url: _Response(b"x" * 10)
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
        lambda url: _Response(b"x" * 12, on_read=lambda: progress.cancel(key)),
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
        lambda url: _Response(b"y" * 9, length=False),
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
    with pytest.raises(ValueError, match="scanpaths"):
        datasets.download_potec(tmp_path)
    assert not (tmp_path / "eyetracking_data" / "scanpaths").exists()
    assert not list((tmp_path / "eyetracking_data").glob(".*.part"))
