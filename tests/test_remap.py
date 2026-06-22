"""Tests for post-normalization re-mapping of stored datasets.

Covers ``data.remap_normalized_frame`` (re-derive an already-normalized frame
under a new mapping, choosing among the columns that survived the first
normalization) and ``data.dropped_columns`` (the columns discarded at import,
surfaced as a note in the Data Inspection remap editor)."""

import pandas as pd

from scanpath_studio.data import (
    compute_keep_columns,
    dropped_columns,
    normalize_fixations,
    normalize_words,
    remap_normalized_frame,
)


def _raw_fixations() -> pd.DataFrame:
    """A small raw fixation table with two extra-kept columns (``dwell``,
    ``block``) and one column that should be dropped (``junk``)."""
    return pd.DataFrame(
        {
            "subj": ["p1", "p1", "p1", "p1"],
            "tr": ["t1", "t1", "t2", "t2"],
            "fx": [10.0, 20.0, 30.0, 40.0],
            "fy": [11.0, 21.0, 31.0, 41.0],
            "dur": [100, 150, 200, 250],
            "dwell": [111, 222, 333, 444],
            "block": ["b1", "b1", "b2", "b2"],
            "junk": ["a", "b", "c", "d"],
        }
    )


_FIX_SCHEMA = {
    "participant": "subj",
    "trial": "tr",
    "x": "fx",
    "y": "fy",
    "duration": "dur",
}


def _normalized_fixations():
    raw = _raw_fixations()
    keep = compute_keep_columns(_FIX_SCHEMA, keep_columns={"dwell", "block"})
    return raw, normalize_fixations(raw, _FIX_SCHEMA, keep_columns=keep)


class TestRemapNormalizedFrame:
    def test_identity_roundtrip(self):
        """Re-mapping with the canonical schema leaves the frame unchanged."""
        _, norm = _normalized_fixations()
        schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            "x": "x",
            "y": "y",
            "duration": "duration_ms",
        }
        out = remap_normalized_frame(norm, schema, kind="fixations")
        assert list(out["duration_ms"]) == list(norm["duration_ms"])
        assert list(out["trial_id"]) == list(norm["trial_id"])
        assert list(out["x"]) == list(norm["x"])
        assert len(out) == len(norm)
        # Kept extras survive the remap.
        assert "dwell" in out.columns
        assert "block" in out.columns

    def test_remap_duration_to_kept_extra(self):
        """Pointing Duration at a surviving extra column rebuilds duration_ms
        from it while preserving the other columns."""
        _, norm = _normalized_fixations()
        schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            "x": "x",
            "y": "y",
            "duration": "dwell",
        }
        out = remap_normalized_frame(norm, schema, kind="fixations")
        assert list(out["duration_ms"]) == [111.0, 222.0, 333.0, 444.0]
        # Unrelated fields untouched.
        assert list(out["x"]) == list(norm["x"])
        assert list(out["trial_id"]) == list(norm["trial_id"])

    def test_remap_trial_single_column_is_authoritative(self):
        """Changing the Trial mapping to a different surviving column re-derives
        trial_id from it — the stale unique_trial_id must not win."""
        _, norm = _normalized_fixations()
        schema = {
            "participant": "participant_id",
            "trial": "block",
            "x": "x",
            "y": "y",
            "duration": "duration_ms",
        }
        out = remap_normalized_frame(norm, schema, kind="fixations")
        assert list(out["trial_id"]) == ["b1", "b1", "b2", "b2"]
        # unique_trial_id is restored and consistent with trial_id.
        assert list(out["unique_trial_id"]) == ["b1", "b1", "b2", "b2"]

    def test_remap_trial_to_composite(self):
        """A multi-column Trial mapping builds a composite trial_id on the fly."""
        _, norm = _normalized_fixations()
        schema = {
            "participant": "participant_id",
            "trial": ["participant_id", "block"],
            "x": "x",
            "y": "y",
            "duration": "duration_ms",
        }
        out = remap_normalized_frame(norm, schema, kind="fixations")
        assert list(out["trial_id"]) == ["p1_b1", "p1_b1", "p1_b2", "p1_b2"]
        assert list(out["unique_trial_id"]) == list(out["trial_id"])
        # Composite component columns remain available for further remaps.
        assert "block" in out.columns
        assert "participant_id" in out.columns

    def test_words_identity_roundtrip(self):
        """Word boxes (stored as canonical x/y/width/height) round-trip, and a
        kept linguistic-feature column survives."""
        raw_w = pd.DataFrame(
            {
                "subj": ["p1", "p1"],
                "tr": ["t1", "t1"],
                "wid": [1, 2],
                "txt": ["The", "cat"],
                "L": [0.0, 50.0],
                "R": [40.0, 90.0],
                "T": [0.0, 0.0],
                "B": [20.0, 20.0],
                "freq": [0.1, 0.2],
            }
        )
        w_schema = {
            "participant": "subj",
            "trial": "tr",
            "word_id": "wid",
            "text": "txt",
            "left": "L",
            "right": "R",
            "top": "T",
            "bottom": "B",
        }
        keep_w = compute_keep_columns(w_schema, keep_columns={"freq"})
        norm_w = normalize_words(raw_w, w_schema, keep_columns=keep_w)
        schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            "word_id": "word_id",
            "text": "text",
            "x": "x",
            "y": "y",
            "width": "width",
            "height": "height",
        }
        out = remap_normalized_frame(norm_w, schema, kind="words")
        assert list(out["x"]) == [0.0, 50.0]
        assert list(out["width"]) == [40.0, 40.0]
        assert list(out["text"]) == ["The", "cat"]
        assert "freq" in out.columns


def _normalized_onestop_fixations():
    """A OneStop-shaped frame: text derives from ``unique_paragraph_id`` and the
    same paragraph is read twice (disambiguated via ``TRIAL_INDEX``)."""
    raw = pd.DataFrame(
        {
            "participant": ["p1", "p1", "p1", "p1"],
            "unique_paragraph_id": ["para1", "para1", "para1", "para1"],
            "TRIAL_INDEX": [1, 1, 2, 2],
            "fx": [1.0, 2.0, 3.0, 4.0],
            "fy": [1.0, 1.0, 1.0, 1.0],
            "dur": [100, 110, 120, 130],
        }
    )
    return raw


class TestRemapOneStopShaped:
    """Regression tests for datasets whose identity rides on unique_* columns."""

    def test_composite_trial_from_unique_paragraph_id_does_not_crash(self):
        """A composite trial built from unique_paragraph_id must not be dropped
        before re-normalizing (else trial_id_series raises KeyError)."""
        raw = _normalized_onestop_fixations()
        schema = {
            "participant": "participant",
            "trial": ["participant", "unique_paragraph_id"],
            "x": "fx",
            "y": "fy",
            "duration": "dur",
        }
        norm = normalize_fixations(
            raw, schema, keep_columns=compute_keep_columns(schema)
        )
        # Re-map with the same composite mapping (the component column survives
        # as unique_paragraph_id) — must not raise and must rebuild trial_id.
        remap_schema = {
            "participant": "participant_id",
            "trial": ["participant", "unique_paragraph_id"],
            "x": "x",
            "y": "y",
            "duration": "duration_ms",
            "text_id": "text_id",
        }
        out = remap_normalized_frame(norm, remap_schema, kind="fixations")
        assert list(out["trial_id"]) == ["p1_para1"] * 4

    def test_remap_preserves_text_id_and_unique_text_id(self):
        """A single-column trial remap must not collapse text_id into trial_id or
        lose unique_text_id (both derived from unique_paragraph_id originally)."""
        raw = _normalized_onestop_fixations()
        schema = {
            "participant": "participant",
            "trial": "unique_paragraph_id",
            "x": "fx",
            "y": "fy",
            "duration": "dur",
        }
        norm = normalize_fixations(
            raw, schema, keep_columns=compute_keep_columns(schema)
        )
        # The two readings share text "para1" but get distinct trial ids.
        assert list(norm["trial_id"]) == ["para1", "para1", "para1_r2", "para1_r2"]
        assert list(norm["text_id"]) == ["para1"] * 4

        # The editor seeds text_id -> "text_id" (see _remap_proposed).
        remap_schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            "x": "x",
            "y": "y",
            "duration": "duration_ms",
            "text_id": "text_id",
        }
        out = remap_normalized_frame(norm, remap_schema, kind="fixations")
        # trial_id is preserved; text_id stays the shared text, NOT trial_id.
        assert list(out["trial_id"]) == ["para1", "para1", "para1_r2", "para1_r2"]
        assert list(out["text_id"]) == ["para1"] * 4
        assert "unique_text_id" in out.columns
        assert list(out["unique_text_id"]) == ["para1"] * 4


def test_remap_proposed_always_seeds_text_id():
    """The editor must seed text_id even when the stored schema had no explicit
    text_id key — the normalized frame always has a text_id column to preserve."""
    from scanpath_studio.tabs import _FIX_REMAP_CANON, _remap_proposed

    cols = ["participant_id", "trial_id", "text_id", "x", "y", "duration_ms"]
    proposed = _remap_proposed(
        {"participant": "participant_id", "trial": "trial_id", "duration": "duration_ms"},
        cols,
        _FIX_REMAP_CANON,
    )
    assert proposed["text_id"] == "text_id"


class TestDroppedColumns:
    def test_dropped_columns_from_keep_set(self):
        """Everything in the raw frame that's not in the keep set is dropped."""
        raw = _raw_fixations()
        keep = compute_keep_columns(_FIX_SCHEMA, keep_columns={"dwell", "block"})
        assert dropped_columns(raw, keep=keep) == ["junk"]

    def test_dropped_columns_from_schema_for_raw_gaze(self):
        """Raw gaze keeps only schema-referenced columns, so the rest are
        reported as dropped."""
        rg = pd.DataFrame(
            {"subj": ["p"], "tr": ["t"], "gx": [1.0], "gy": [2.0], "extra": [9]}
        )
        rg_schema = {"participant": "subj", "trial": "tr", "x": "gx", "y": "gy"}
        assert dropped_columns(rg, schema=rg_schema) == ["extra"]

    def test_dropped_columns_empty_when_unspecified(self):
        raw = _raw_fixations()
        assert dropped_columns(raw) == []
