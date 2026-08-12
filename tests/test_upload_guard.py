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


# --- DATA-22 review · the guard is a *hosted-demo* guard ----------------------
# It exists because the ~1 GB demo OOM-kills without a traceback. Running
# locally there is no such ceiling, so the warning was noise and the "Load it
# anyway" tick was a step between the user and their own data on their own
# machine. Same loopback test the wizard's "run locally" tip uses.


def test_the_size_warning_is_skipped_on_a_local_run():
    """A local run must not be asked to confirm its own file size.

    Asserted at the source rather than through the UI: the warning lives inside
    `_read_uploaded_frame`, whose whole reason for existing is that
    `st.file_uploader` cannot be driven from `AppTest` — so there is no headless
    path that renders it. What this pins is that the gate stays welded to the
    size check; a separate `if` elsewhere would not stop the warning rendering.
    """
    import inspect

    from scanpath_studio import app as app_module

    source = inspect.getsource(app_module._read_uploaded_frame)
    # The gate must be *on the same condition* as the size check — a separate
    # `if` elsewhere would not stop the warning rendering.
    assert "upload_exceeds_limit(uploaded) and not is_loopback_url(" in source, (
        "the large-upload warning is no longer gated on being hosted"
    )
    assert "Load it anyway" in source  # still there for the hosted demo
