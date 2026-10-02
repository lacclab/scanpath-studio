"""A corrected re-upload is never served the old file's results (BUG-103).

Until BUG-103 a table over 200,000 rows was keyed on ~384 sampled rows. A
corrected file of the same shape, edited in a row the sample skipped, matched
the original, so the normalization handed back the *old* tables — which the
add-dataset screen then stored, and the recovery cache wrote to disk, as the
new dataset. These tests run that sequence through the real upload reader and
the real normalization.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import app
from scanpath_studio.data import adopt_source, frame_fingerprint, propose_fix_schema

ROWS = 200_001
#: Past the first 64 rows and between two of the old stride's sampled rows.
EDITED_ROW = 100


class _Upload(io.BytesIO):
    """What `st.file_uploader` hands over: a named, seekable byte buffer."""

    def __init__(self, data: bytes, file_id: str):
        super().__init__(data)
        self.name = "fixations.csv"
        self.file_id = file_id
        self.size = len(data)


def _fixations(duration_at_edit: float) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "participant_id": "p1",
            "trial_id": "t1",
            "duration_ms": np.full(ROWS, 100.0),
            "x": 1.0,
            "y": 1.0,
        }
    )
    frame.loc[EDITED_ROW, "duration_ms"] = duration_at_edit
    return frame


def _upload(frame: pd.DataFrame, file_id: str) -> _Upload:
    return _Upload(frame.to_csv(index=False).encode(), file_id)


def _read(upload: _Upload) -> pd.DataFrame:
    """The upload box's read: the cached parse, then its label onto the frame."""
    frame = app._read_uploaded_table_cached(upload, app._uploaded_file_key(upload))
    adopt_source(frame)
    return frame


def _read_plain(upload: _Upload) -> pd.DataFrame:
    """A frame with no loader label, as the API or a test seam passes one in."""
    return pd.read_csv(io.BytesIO(upload.getvalue()))


def _normalized_duration(raw: pd.DataFrame) -> float:
    schema = propose_fix_schema(raw)
    _, fixations = app._normalize_pair(pd.DataFrame(), None, raw, schema)
    return float(fixations["duration_ms"].iloc[EDITED_ROW])


@pytest.mark.parametrize("read", [_read, _read_plain], ids=["labelled", "unlabelled"])
def test_a_corrected_reupload_is_normalized_afresh(read):
    original = read(_upload(_fixations(100.0), f"{read.__name__}-1"))
    assert _normalized_duration(original) == 100.0
    corrected = read(_upload(_fixations(999.0), f"{read.__name__}-2"))
    assert _normalized_duration(corrected) == 999.0


def test_the_same_upload_keeps_one_id_across_reruns():
    """A rerun re-reads the cached parse — a new copy, the same load — and must
    reuse the normalization rather than redo it."""
    upload = _upload(_fixations(100.0), "same-upload")
    first, second = _read(upload), _read(upload)
    assert first is not second
    assert frame_fingerprint(first) == frame_fingerprint(second)
    assert frame_fingerprint(first)[0] == "assigned"
