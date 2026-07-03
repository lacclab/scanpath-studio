"""BUG-5: the upload-size guard that protects the memory-limited hosted demo."""

from __future__ import annotations

from dataclasses import dataclass

from scanpath_studio.data import (
    UPLOAD_SIZE_WARN_BYTES,
    upload_exceeds_limit,
    uploaded_files_total_bytes,
)


@dataclass
class _FakeUpload:
    """Stand-in for a Streamlit ``UploadedFile`` (only ``.size`` is read)."""

    size: int


def test_total_bytes_none_and_empty():
    assert uploaded_files_total_bytes(None) == 0
    assert uploaded_files_total_bytes([]) == 0


def test_total_bytes_single_and_list():
    assert uploaded_files_total_bytes(_FakeUpload(10)) == 10
    assert uploaded_files_total_bytes([_FakeUpload(10), _FakeUpload(5)]) == 15


def test_exceeds_limit_boundary():
    # At the threshold is fine; one byte over trips the guard.
    assert not upload_exceeds_limit(_FakeUpload(UPLOAD_SIZE_WARN_BYTES))
    assert upload_exceeds_limit(_FakeUpload(UPLOAD_SIZE_WARN_BYTES + 1))


def test_small_upload_is_under_limit():
    assert not upload_exceeds_limit(_FakeUpload(1_000_000))  # 1 MB
    assert not upload_exceeds_limit(None)


def test_onestop_repeated_export_would_trip_guard():
    # The OneStop repeated-reading export that first surfaced BUG-5: ~37 MB
    # (fixations) and ~29 MB (IA) zipped tables — each over the guard.
    assert upload_exceeds_limit(_FakeUpload(36_529_375))
    assert upload_exceeds_limit(_FakeUpload(28_875_283))
