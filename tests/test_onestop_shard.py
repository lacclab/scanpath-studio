"""ENG-2: the OneStop per-participant shard fast-path.

The full lacclab export is ~15 GB of CSV and takes ~3 min to load, so a
deep-linked page reads one participant's Parquet shard instead
(`data.load_onestop_server_bundle` ← `onestop_shard`). The behaviour that
matters is the *refusal*: when a participant is named and their shard is
missing, the loader must NOT quietly fall back to the whole-corpus read — the
link is for one pid, so loading 15 GB to discover it has no data is pure waste.

Two layers here: a synthetic shard tree in ``tmp_path`` that always runs, and an
agreement check against the real corpus, gated on ``$ONESTOP_DATA_DIR``.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from scanpath_studio import data as data_module
from scanpath_studio.data import (
    ONESTOP_DATA_DIR_ENV,
    load_onestop_server_bundle,
    onestop_data_dir,
    onestop_data_provenance,
    onestop_full_bundle_exists,
)
from scanpath_studio.onestop_shard import _shard_one

# -----------------------------------------------------------------------------
# Fixtures: a miniature stand-in for the export layout.
# -----------------------------------------------------------------------------

PIDS = ["l37_1129", "l7_1090"]


def _ia_rows(pid: str) -> pd.DataFrame:
    """Two IA (word) rows per pid, with a per-pid value to prove the slice."""
    return pd.DataFrame(
        {
            "participant_id": [pid, pid],
            "unique_paragraph_id": ["1_1_Ele", "1_1_Ele"],
            "IA_ID": [0, 1],
            "IA_LABEL": ["The", "cat"],
            "IA_LEFT": [100.0, 160.0],
            "IA_RIGHT": [155.0, 210.0],
            "IA_TOP": [50.0, 50.0],
            "IA_BOTTOM": [80.0, 80.0],
            "IA_DWELL_TIME": [200.0 if pid == PIDS[0] else 900.0, 300.0],
        }
    )


def _fix_rows(pid: str) -> pd.DataFrame:
    """Three fixation rows per pid."""
    return pd.DataFrame(
        {
            "participant_id": [pid] * 3,
            "unique_paragraph_id": ["1_1_Ele"] * 3,
            "CURRENT_FIX_X": [110.0, 170.0, 120.0],
            "CURRENT_FIX_Y": [65.0, 65.0, 65.0],
            "CURRENT_FIX_DURATION": [180.0, 220.0, 140.0],
            "CURRENT_FIX_INDEX": [1, 2, 3],
        }
    )


@pytest.fixture
def export_root(tmp_path):
    """A OneStop export folder holding the full CSV.zip pair for both pids."""
    ia = pd.concat([_ia_rows(p) for p in PIDS], ignore_index=True)
    fix = pd.concat([_fix_rows(p) for p in PIDS], ignore_index=True)
    ia.to_csv(tmp_path / "ia_Paragraph.csv.zip", index=False, compression="zip")
    fix.to_csv(tmp_path / "fixations_Paragraph.csv.zip", index=False, compression="zip")
    return tmp_path


def _write_shards(root, pids=PIDS):
    """Write `by_pid/{ia,fixations}/<pid>.parquet` for `pids`."""
    for kind, build in (("ia", _ia_rows), ("fixations", _fix_rows)):
        out = root / "by_pid" / kind
        out.mkdir(parents=True, exist_ok=True)
        for pid in pids:
            build(pid).to_parquet(out / f"{pid}.parquet", index=False)


class _RecordingSt:
    """Stand-in for the `streamlit` module inside `data.py`.

    ``st.stop()`` is the load-bearing part: in a real script run it raises and
    halts, but in pytest's bare mode it is a **no-op** — so without this the
    "must not fall through to the 15 GB read" assertions below would silently
    pass through to the slow path and still look green.
    """

    class Stopped(Exception):
        pass

    def __init__(self):
        self.errors: list[str] = []

    def error(self, message, **_kwargs):
        self.errors.append(str(message))

    def stop(self):
        raise self.Stopped()


@pytest.fixture
def fake_st(monkeypatch):
    recorder = _RecordingSt()
    monkeypatch.setattr(data_module, "st", recorder)
    return recorder


@pytest.fixture(autouse=True)
def _clear_bundle_cache():
    """The loader is `@st.cache_data`; without this a later test reads an
    earlier test's frames back out of the cache."""
    load_onestop_server_bundle.clear()
    yield
    load_onestop_server_bundle.clear()


@pytest.fixture
def at_root(monkeypatch, export_root):
    monkeypatch.setenv(ONESTOP_DATA_DIR_ENV, str(export_root))
    return export_root


# -----------------------------------------------------------------------------
# The fast path
# -----------------------------------------------------------------------------


class TestShardPaths:
    """Pin the path construction itself, not just an end-to-end read: macOS is
    case-insensitive, so a filesystem round-trip silently accepts the wrong
    case and only fails on Linux CI."""

    def test_the_pid_is_lowercased_and_stripped(self, tmp_path):
        ia, fix = data_module._onestop_shard_paths(tmp_path, "  L37_1129 ")
        assert ia.name == "l37_1129.parquet"
        assert fix.name == "l37_1129.parquet"

    def test_the_two_shards_live_in_their_own_subdirectories(self, tmp_path):
        ia, fix = data_module._onestop_shard_paths(tmp_path, "p1")
        assert ia.parent == tmp_path / "by_pid" / "ia"
        assert fix.parent == tmp_path / "by_pid" / "fixations"


class TestShardFastPath:
    def test_reads_only_the_named_participant(self, at_root, fake_st):
        _write_shards(at_root)
        words, fixations = load_onestop_server_bundle("l7_1090")
        assert set(words["participant_id"]) == {"l7_1090"}
        assert set(fixations["participant_id"]) == {"l7_1090"}
        assert len(words) == 2 and len(fixations) == 3
        # The per-pid value proves it's that pid's slice, not the other's.
        assert words["IA_DWELL_TIME"].iloc[0] == 900.0
        assert fake_st.errors == []

    def test_the_pid_is_matched_case_insensitively(self, at_root, fake_st):
        """Shards are written lowercase; a deep link may not be."""
        _write_shards(at_root)
        words, _ = load_onestop_server_bundle("  L37_1129 ")
        assert set(words["participant_id"]) == {"l37_1129"}

    def test_the_shard_columns_match_the_full_export(self, at_root, fake_st):
        """A shard is a row slice, not a reshape — the app's schema inference
        runs on whichever path served the data, so they must agree."""
        _write_shards(at_root)
        sharded_w, sharded_f = load_onestop_server_bundle("l37_1129")
        load_onestop_server_bundle.clear()
        full_w, full_f = load_onestop_server_bundle()
        assert list(sharded_w.columns) == list(full_w.columns)
        assert list(sharded_f.columns) == list(full_f.columns)

    def test_a_pid_with_no_shard_never_reads_the_whole_corpus(self, at_root, fake_st):
        """The whole point of the fast path. The full CSV.zip pair IS present
        here, so a fall-through would succeed silently and cost 3 minutes on the
        real corpus."""
        _write_shards(at_root)
        with pytest.raises(_RecordingSt.Stopped):
            load_onestop_server_bundle("l99_0000")
        assert len(fake_st.errors) == 1
        message = fake_st.errors[0]
        assert "l99_0000" in message
        assert "l99_0000.parquet" in message  # names what's missing
        assert "onestop_shard" in message  # and how to fix it

    def test_one_missing_shard_of_the_two_is_still_a_refusal(self, at_root, fake_st):
        """Half a participant is not usable, and the error should say which
        half is absent rather than a generic 'not found'."""
        _write_shards(at_root)
        (at_root / "by_pid" / "fixations" / "l7_1090.parquet").unlink()
        with pytest.raises(_RecordingSt.Stopped):
            load_onestop_server_bundle("l7_1090")
        (message,) = fake_st.errors
        assert "l7_1090.parquet" in message
        # Only the fixations shard is missing, so the IA one must not be blamed.
        assert message.count("l7_1090.parquet") == 1

    def test_no_shards_at_all_is_the_same_refusal(self, at_root, fake_st):
        with pytest.raises(_RecordingSt.Stopped):
            load_onestop_server_bundle("l37_1129")
        assert fake_st.errors


# -----------------------------------------------------------------------------
# The slow path + the environment gate
# -----------------------------------------------------------------------------


class TestFullExportPath:
    def test_no_participant_loads_the_whole_export(self, at_root, fake_st):
        words, fixations = load_onestop_server_bundle()
        assert set(words["participant_id"]) == set(PIDS)
        assert len(words) == 4 and len(fixations) == 6
        assert fake_st.errors == []

    def test_a_missing_export_reports_and_returns_empty(
        self, monkeypatch, tmp_path, fake_st
    ):
        monkeypatch.setenv(ONESTOP_DATA_DIR_ENV, str(tmp_path))
        words, fixations = load_onestop_server_bundle()
        assert words.empty and fixations.empty
        assert "ia_Paragraph.csv.zip" in fake_st.errors[0]

    def test_an_unset_env_var_is_not_an_error(self, monkeypatch, fake_st):
        """The OneStop source simply isn't in use — no error belongs here."""
        monkeypatch.delenv(ONESTOP_DATA_DIR_ENV, raising=False)
        words, fixations = load_onestop_server_bundle()
        assert words.empty and fixations.empty
        assert fake_st.errors == []
        assert onestop_data_dir() is None

    def test_a_blank_env_var_counts_as_unset(self, monkeypatch):
        monkeypatch.setenv(ONESTOP_DATA_DIR_ENV, "   ")
        assert onestop_data_dir() is None


class TestFullBundleExists:
    """Drives the app's choice between 'load once and filter in-app' and
    'one shard at a time' — a shards-only host can't materialize the corpus."""

    def test_true_when_both_exports_are_present(self, at_root):
        assert onestop_full_bundle_exists() is True

    def test_false_when_only_shards_exist(self, monkeypatch, tmp_path):
        monkeypatch.setenv(ONESTOP_DATA_DIR_ENV, str(tmp_path))
        _write_shards(tmp_path)
        assert onestop_full_bundle_exists() is False

    def test_false_when_one_export_is_missing(self, at_root):
        (at_root / "fixations_Paragraph.csv.zip").unlink()
        assert onestop_full_bundle_exists() is False

    def test_false_without_the_env_var(self, monkeypatch):
        monkeypatch.delenv(ONESTOP_DATA_DIR_ENV, raising=False)
        assert onestop_full_bundle_exists() is False


class TestProvenance:
    """The Data Inspection panel has to say which bytes are on screen."""

    def test_reports_the_shard_when_a_participant_is_set(self, at_root):
        _write_shards(at_root)
        info = onestop_data_provenance("l37_1129")
        assert info["loaded_from"] == "per-pid shard"
        assert info["ia_shard"].endswith("by_pid/ia/l37_1129.parquet")
        assert "ia_shard_mtime" in info and "fix_shard_mtime" in info

    def test_reports_the_full_export_without_one(self, at_root):
        info = onestop_data_provenance()
        assert info["loaded_from"] == "full CSV.zip export"
        assert info["ia_shard"].endswith("ia_Paragraph.csv.zip")

    def test_a_missing_shard_leaves_the_mtime_out_rather_than_guessing(self, at_root):
        info = onestop_data_provenance("l99_0000")
        assert info["loaded_from"] == "per-pid shard"
        assert "ia_shard_mtime" not in info

    def test_parses_cohort_source_and_date_from_the_canonical_layout(
        self, monkeypatch, tmp_path
    ):
        root = tmp_path / "onestop_L2" / "reports" / "lacclab" / "20260101" / "full"
        root.mkdir(parents=True)
        monkeypatch.setenv(ONESTOP_DATA_DIR_ENV, str(root))
        info = onestop_data_provenance()
        assert info["cohort"] == "L2"
        assert info["source"] == "lacclab"
        assert info["date"] == "20260101"

    def test_an_unrecognised_layout_degrades_to_just_the_directory(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setenv(ONESTOP_DATA_DIR_ENV, str(tmp_path))
        info = onestop_data_provenance()
        assert info["data_dir"] == str(tmp_path)
        assert "cohort" not in info and "source" not in info

    def test_empty_without_the_env_var(self, monkeypatch):
        monkeypatch.delenv(ONESTOP_DATA_DIR_ENV, raising=False)
        assert onestop_data_provenance("l37_1129") == {}


# -----------------------------------------------------------------------------
# The sharding step itself
# -----------------------------------------------------------------------------


class TestShardOne:
    def test_writes_one_lowercased_parquet_per_participant(self, export_root, tmp_path):
        out = tmp_path / "out"
        written, skipped, total = _shard_one(
            export_root / "ia_Paragraph.csv.zip", out, "ia", rebuild=False
        )
        assert (written, skipped, total) == (2, 0, 2)
        assert sorted(p.name for p in out.glob("*.parquet")) == [
            "l37_1129.parquet",
            "l7_1090.parquet",
        ]
        one = pd.read_parquet(out / "l7_1090.parquet")
        assert set(one["participant_id"]) == {"l7_1090"}
        assert len(one) == 2

    def test_an_uppercase_pid_lands_in_a_lowercase_file(self, tmp_path):
        """`_onestop_shard_paths` lowercases when it looks a shard up, so the
        writer has to lowercase too or the fast path never hits."""
        src = tmp_path / "ia.csv.zip"
        _ia_rows("L37_1129").to_csv(src, index=False, compression="zip")
        out = tmp_path / "out"
        _shard_one(src, out, "ia", rebuild=False)
        assert [p.name for p in out.glob("*.parquet")] == ["l37_1129.parquet"]

    def test_existing_shards_are_skipped_unless_rebuilding(self, export_root, tmp_path):
        out = tmp_path / "out"
        src = export_root / "ia_Paragraph.csv.zip"
        _shard_one(src, out, "ia", rebuild=False)
        stamp = (out / "l7_1090.parquet").stat().st_mtime_ns

        assert _shard_one(src, out, "ia", rebuild=False) == (0, 2, 2)
        assert (out / "l7_1090.parquet").stat().st_mtime_ns == stamp  # untouched

        written, skipped, _ = _shard_one(src, out, "ia", rebuild=True)
        assert (written, skipped) == (2, 0)

    def test_a_missing_source_raises_rather_than_writing_nothing_quietly(
        self, tmp_path
    ):
        with pytest.raises(FileNotFoundError):
            _shard_one(tmp_path / "nope.csv.zip", tmp_path / "out", "ia", False)

    def test_a_source_without_participant_id_raises_a_named_error(self, tmp_path):
        src = tmp_path / "ia.csv.zip"
        pd.DataFrame({"IA_ID": [0, 1]}).to_csv(src, index=False, compression="zip")
        with pytest.raises(ValueError, match="participant_id"):
            _shard_one(src, tmp_path / "out", "ia", False)


# -----------------------------------------------------------------------------
# Against the real corpus
# -----------------------------------------------------------------------------

_REAL_DIR = os.environ.get(ONESTOP_DATA_DIR_ENV, "").strip()


@pytest.mark.skipif(
    not _REAL_DIR,
    reason=f"set {ONESTOP_DATA_DIR_ENV} to run against the real OneStop export",
)
class TestAgainstTheRealExport:
    """The synthetic tree pins the logic; this pins the logic against the actual
    file layout, which is the part a fixture can drift away from."""

    def _a_sharded_pid(self):
        base = onestop_data_dir()
        shards = sorted((base / "by_pid" / "ia").glob("*.parquet"))
        if not shards:
            pytest.skip("no per-pid shards under by_pid/ia — run onestop_shard")
        return shards[0].stem

    def test_the_shard_and_the_full_export_agree(self):
        if not onestop_full_bundle_exists():
            pytest.skip("full CSV.zip export not present; nothing to compare to")
        pid = self._a_sharded_pid()
        load_onestop_server_bundle.clear()
        sharded_w, sharded_f = load_onestop_server_bundle(pid)
        load_onestop_server_bundle.clear()
        full_w, full_f = load_onestop_server_bundle()
        for sharded, full in ((sharded_w, full_w), (sharded_f, full_f)):
            slice_ = full[full["participant_id"].astype(str).str.lower() == pid]
            assert len(sharded) == len(slice_)
            assert list(sharded.columns) == list(full.columns)

    def test_a_real_shard_loads_and_carries_only_that_pid(self):
        pid = self._a_sharded_pid()
        load_onestop_server_bundle.clear()
        words, fixations = load_onestop_server_bundle(pid)
        assert not words.empty and not fixations.empty
        for frame in (words, fixations):
            assert set(frame["participant_id"].astype(str).str.lower()) == {pid}
