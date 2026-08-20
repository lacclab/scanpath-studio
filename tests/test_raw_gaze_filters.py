"""BUG-12 (annotation filters reach the raw-gaze table) + DATA-16 (zip size cap).

Both live in ``data.py``: the raw-gaze samples table has to be narrowed by the
same ``(participant_id, trial_id)`` key set as the words and fixations frames,
and ``_read_zipped_table`` must refuse an archive that would decompress past the
``ZIP_MAX_*`` limits instead of discovering the size by exhausting RAM.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from scanpath_studio.annotations import select_keys
from scanpath_studio.data import (
    ZIP_MAX_COMPRESSION_RATIO,
    ZIP_MAX_MEMBER_ENV,
    ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES,
    ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES,
    ZIP_RATIO_CHECK_MIN_BYTES,
    _zip_limit_from_env,
    filter_frame_to_keys,
    filter_to_keys,
    read_table,
    trial_keys,
)


def _words() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2"],
            "trial_id": ["a", "b", "a", "b"],
            "word_id": [0.0, 0.0, 0.0, 0.0],
        }
    )


def _fixations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2"],
            "trial_id": ["a", "b", "a", "b"],
            "duration_ms": [100.0, 200.0, 300.0, 400.0],
        }
    )


def _raw_gaze() -> pd.DataFrame:
    # Sample-level: several rows per trial.
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 4 + ["p2"] * 4,
            "trial_id": ["a", "a", "b", "b", "a", "a", "b", "b"],
            "x": range(8),
            "y": range(8),
        }
    )


class TestTrialKeys:
    def test_dedupes_sample_level_rows(self):
        assert trial_keys(_raw_gaze()) == {
            ("p1", "a"),
            ("p1", "b"),
            ("p2", "a"),
            ("p2", "b"),
        }

    def test_empty_and_id_less_frames_yield_nothing(self):
        assert trial_keys(pd.DataFrame()) == set()
        assert trial_keys(pd.DataFrame({"x": [1, 2]})) == set()

    def test_keys_are_stringified(self):
        frame = pd.DataFrame({"participant_id": [1], "trial_id": [2]})
        assert trial_keys(frame) == {("1", "2")}


class TestFilterFrameToKeys:
    def test_excluded_trial_is_dropped_from_raw_gaze(self):
        kept = {("p1", "a"), ("p2", "a")}
        out = filter_frame_to_keys(_raw_gaze(), kept)
        assert set(zip(out["participant_id"], out["trial_id"])) == kept
        assert len(out) == 4  # two sample rows per surviving trial

    def test_full_key_set_is_a_no_op(self):
        raw = _raw_gaze()
        out = filter_frame_to_keys(raw, trial_keys(raw))
        pd.testing.assert_frame_equal(out, raw)

    def test_empty_frame_passes_through(self):
        empty = pd.DataFrame()
        assert filter_frame_to_keys(empty, {("p1", "a")}).empty

    def test_frame_without_id_columns_passes_through(self):
        frame = pd.DataFrame({"x": [1, 2]})
        pd.testing.assert_frame_equal(filter_frame_to_keys(frame, set()), frame)

    def test_filter_to_keys_still_narrows_both_frames(self):
        w, f = filter_to_keys(_words(), _fixations(), {("p1", "a")})
        assert len(w) == 1 and len(f) == 1
        assert w.iloc[0]["trial_id"] == "a" and f.iloc[0]["trial_id"] == "a"


class TestAllThreeFramesEmptyTogether:
    """BUG-12's user-visible consequence: with nothing starred, the raw-gaze
    frame used to survive "⭐ Favorites only" while words + fixations emptied, so
    ``app.main``'s all-three-empty guard (and the UX-7 guidance panel behind it)
    never fired."""

    def test_favorites_only_with_nothing_starred_empties_every_frame(self):
        words, fixations, raw = _words(), _fixations(), _raw_gaze()
        present = trial_keys(words) | trial_keys(fixations) | trial_keys(raw)
        # Empty annotation store == nothing starred.
        kept = set(select_keys({}, list(present), favorites_only=True))
        assert kept == set()
        words, fixations = filter_to_keys(words, fixations, kept)
        raw = filter_frame_to_keys(raw, kept)
        assert words.empty and fixations.empty and raw.empty

    def test_no_annotation_filter_leaves_raw_gaze_untouched(self):
        raw = _raw_gaze()
        present = trial_keys(_words()) | trial_keys(_fixations()) | trial_keys(raw)
        kept = set(select_keys({}, list(present)))
        assert kept == present
        pd.testing.assert_frame_equal(filter_frame_to_keys(raw, kept), raw)

    def test_one_starred_trial_keeps_only_its_raw_gaze(self):
        store = {("p1", "b"): {"star": True}}
        raw = _raw_gaze()
        present = trial_keys(_words()) | trial_keys(_fixations()) | trial_keys(raw)
        kept = set(select_keys(store, list(present), favorites_only=True))
        out = filter_frame_to_keys(raw, kept)
        assert set(zip(out["participant_id"], out["trial_id"])) == {("p1", "b")}


def _zip_bytes(members: dict[str, bytes]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members.items():
            zf.writestr(name, payload)
    buf.seek(0)
    buf.name = "upload.zip"
    return buf


class TestZipSizeCap:
    """DATA-16 / security finding S6."""

    def test_limits_are_ordered_sanely(self):
        assert ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES <= ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES
        assert ZIP_RATIO_CHECK_MIN_BYTES < ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES
        assert ZIP_MAX_COMPRESSION_RATIO > 1

    def test_a_normal_zipped_csv_still_reads(self):
        csv = b"participant_id,trial_id,x\np1,a,1\np1,a,2\n"
        frame = read_table(_zip_bytes({"fix.csv": csv}))
        assert len(frame) == 2
        assert frame["participant_id"].tolist() == ["p1", "p1"]

    def test_declared_oversize_member_is_rejected(self, monkeypatch):
        # A tiny archive, checked against a tiny cap: the declared uncompressed
        # size is what trips, before any member is opened.
        monkeypatch.setattr("scanpath_studio.data.ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES", 8)
        buf = _zip_bytes({"fix.csv": b"a,b\n1,2\n3,4\n"})
        with pytest.raises(ValueError, match="above the per-file limit"):
            read_table(buf)

    def test_declared_oversize_total_is_rejected(self, monkeypatch):
        monkeypatch.setattr(
            "scanpath_studio.data.ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES", 10**9
        )
        monkeypatch.setattr("scanpath_studio.data.ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES", 10)
        buf = _zip_bytes({"a.csv": b"a,b\n1,2\n", "b.csv": b"a,b\n3,4\n"})
        with pytest.raises(ValueError, match="decompression limit"):
            read_table(buf)

    def test_compression_ratio_is_rejected(self, monkeypatch):
        monkeypatch.setattr("scanpath_studio.data.ZIP_RATIO_CHECK_MIN_BYTES", 1)
        monkeypatch.setattr("scanpath_studio.data.ZIP_MAX_COMPRESSION_RATIO", 5.0)
        # A zip bomb in miniature: 1 MB of zeroes deflates to a few hundred bytes.
        buf = _zip_bytes({"fix.csv": b"0" * (1024 * 1024)})
        with pytest.raises(ValueError, match="doesn't look like a normal data export"):
            read_table(buf)

    def test_small_but_very_compressible_archive_is_allowed(self, monkeypatch):
        # Under ZIP_RATIO_CHECK_MIN_BYTES the ratio isn't checked — expanding a
        # small repetitive table costs nothing.
        monkeypatch.setattr("scanpath_studio.data.ZIP_MAX_COMPRESSION_RATIO", 2.0)
        csv = b"a,b\n" + b"1,2\n" * 5000
        frame = read_table(_zip_bytes({"fix.csv": csv}))
        assert len(frame) == 5000

    def test_forged_declared_size_is_caught_while_reading(self, monkeypatch):
        # The declared sizes pass, but the member really does exceed the budget.
        monkeypatch.setattr(
            "scanpath_studio.data.ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES", 10**9
        )
        monkeypatch.setattr(
            "scanpath_studio.data.ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES", 10**9
        )
        buf = _zip_bytes({"fix.csv": b"a,b\n1,2\n3,4\n"})
        with zipfile.ZipFile(buf) as zf:
            info = zf.getinfo("fix.csv")
        real_size = info.file_size
        # Now shrink the budget below the real payload while _check_zip_limits
        # sees a (lying) declared size of 0.
        monkeypatch.setattr(
            "scanpath_studio.data.ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES", real_size - 1
        )
        monkeypatch.setattr(
            "scanpath_studio.data._check_zip_limits", lambda infos: None
        )
        buf.seek(0)
        with pytest.raises(ValueError, match="declared size was wrong"):
            read_table(buf)

    def test_forged_member_cannot_exceed_per_file_budget(self, monkeypatch):
        payload = b"a,b\n1,2\n3,4\n"
        buf = _zip_bytes({"fix.csv": payload})
        monkeypatch.setattr(
            "scanpath_studio.data.ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES",
            len(payload) - 1,
        )
        monkeypatch.setattr(
            "scanpath_studio.data.ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES", 10**9
        )
        # Simulate a forged central-directory size that passed the fast check.
        monkeypatch.setattr(
            "scanpath_studio.data._check_zip_limits", lambda infos: None
        )
        with pytest.raises(ValueError, match="per-file limit"):
            read_table(buf)

    def test_defaults_clear_a_full_fixation_report(self):
        # DATA-34: one OneStop fixation report is a single ~8 GB CSV inside its
        # zip. The 4 GB per-member default refused it outright; the caps are a
        # memory guard, and the machine holding a corpus has the memory.
        assert ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES >= 16 * 1024**3
        assert ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES >= 32 * 1024**3

    def test_env_var_overrides_a_limit(self, monkeypatch):
        monkeypatch.setenv(ZIP_MAX_MEMBER_ENV, "2.5")
        assert _zip_limit_from_env(ZIP_MAX_MEMBER_ENV, 32.0) == 2.5

    def test_a_useless_env_value_keeps_the_default(self, monkeypatch):
        for raw in ("", "   ", "lots", "0", "-4"):
            monkeypatch.setenv(ZIP_MAX_MEMBER_ENV, raw)
            assert _zip_limit_from_env(ZIP_MAX_MEMBER_ENV, 32.0) == 32.0

    def test_a_zipped_parquet_member_still_reads(self):
        # Parquet's reader seeks, so that member takes the read-into-memory
        # path rather than the streamed one — both stay under the budget.
        frame = pd.DataFrame({"participant_id": ["p1", "p1"], "x": [1, 2]})
        payload = io.BytesIO()
        frame.to_parquet(payload, index=False)
        out = read_table(_zip_bytes({"fix.parquet": payload.getvalue()}))
        assert out["x"].tolist() == [1, 2]

    def test_empty_archive_still_raises_its_own_error(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass
        buf.seek(0)
        buf.name = "empty.zip"
        with pytest.raises(ValueError, match="no readable table files"):
            read_table(buf)
