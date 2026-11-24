"""The upload-size guard that protects the memory-limited hosted demo."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

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
    # A OneStop repeated-reading export: ~37 MB (fixations) and ~29 MB (IA)
    # zipped tables — each over the guard.
    assert upload_exceeds_limit(_FakeUpload(36_529_375))
    assert upload_exceeds_limit(_FakeUpload(28_875_283))


# --- the guard is a *hosted-demo* guard ---------------------------------------
# It exists because the ~1 GB demo OOM-kills without a traceback. Running
# locally there is no such ceiling, so the warning would be noise and the "Load
# it anyway" tick a step between the user and their own data on their own
# machine. Same loopback test the wizard's "run locally" tip uses.


def _upload_box_app():
    """One upload box; the rows it read go to ``_rows``."""
    import streamlit as st

    from scanpath_studio import app

    frame = app._read_uploaded_frame(
        uploader_label="Fixations",
        upload_help="",
        state_prefix="col_map_fix",
        multi=False,
    )
    st.session_state["_rows"] = len(frame)


@pytest.mark.parametrize("local", [True, False], ids=["local", "hosted"])
def test_the_size_warning_is_skipped_on_a_local_run(monkeypatch, local):
    """A local run must not be asked to confirm its own file size; the
    hosted demo reads a large upload only once it is ticked."""
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import app

    monkeypatch.setattr(app, "upload_exceeds_limit", lambda uploaded: True)
    monkeypatch.setattr(app, "is_loopback_url", lambda url: local)
    at = AppTest.from_function(_upload_box_app, default_timeout=60).run()
    at.file_uploader[0].set_value(
        (
            "fixations.csv",
            b"participant,trial,x,y,duration\np1,t1,1,2,200\n",
            "text/csv",
        )
    ).run()
    assert not at.exception, at.exception
    asked = [box for box in at.checkbox if box.label == "Load it anyway"]
    if local:
        assert not asked and not at.warning
        assert at.session_state["_rows"] == 1
        return
    assert asked and any("online demo" in w.value for w in at.warning)
    assert at.session_state["_rows"] == 0
    asked[0].check().run()
    assert not at.exception, at.exception
    assert at.session_state["_rows"] == 1
