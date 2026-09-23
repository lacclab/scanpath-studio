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
        {
            "participant": "participant_id",
            "trial": "trial_id",
            "duration": "duration_ms",
        },
        cols,
        _FIX_REMAP_CANON,
    )
    assert proposed["text_id"] == "text_id"


class TestStimulusLevelWordsRemap:
    """DATA-39 — a per-*text* AOI table (no participant column) is broadcast onto
    the readers at import, so the stored words carry real reader ids while their
    schema maps no Participant. ✅ Save changes on the ✏️ Edit dataset screen —
    which attaching a metadata table there requires — re-derived those words onto
    the ``""`` placeholder reader and never broadcast them back, so every
    scanpath lost its AOIs and its text."""

    _WORD_SCHEMA = {
        "trial": "tr",
        "word_id": "wid",
        "text": "txt",
        "left": "L",
        "right": "R",
        "top": "T",
        "bottom": "B",
    }
    _FIX_SCHEMA = {
        "participant": "subj",
        "trial": "tr",
        "x": "fx",
        "y": "fy",
        "duration": "dur",
    }

    def _stored(self):
        """The frames a finished upload stores: normalized, then harmonized."""
        from scanpath_studio.data import harmonize_frames

        raw_w = pd.DataFrame(
            {
                "tr": ["t1", "t1", "t2"],
                "wid": [0, 1, 0],
                "txt": ["The", "cat", "Dogs"],
                "L": [0.0, 50.0, 0.0],
                "R": [40.0, 90.0, 60.0],
                "T": [0.0, 0.0, 0.0],
                "B": [20.0, 20.0, 20.0],
            }
        )
        raw_f = pd.DataFrame(
            {
                "subj": ["p1", "p1", "p2", "p2"],
                "tr": ["t1", "t1", "t1", "t2"],
                "fx": [10.0, 60.0, 12.0, 20.0],
                "fy": [5.0, 5.0, 5.0, 5.0],
                "dur": [100, 150, 90, 120],
            }
        )
        return harmonize_frames(
            normalize_words(raw_w, self._WORD_SCHEMA),
            normalize_fixations(raw_f, self._FIX_SCHEMA),
        )

    def _save(self, words, fixations):
        """What ✅ Save changes does to an untouched mapping."""
        from scanpath_studio.data import harmonize_frames
        from scanpath_studio.tabs import (
            _FIX_REMAP_CANON,
            _WORD_REMAP_CANON,
            _remap_proposed,
        )

        w_schema = _remap_proposed(self._WORD_SCHEMA, words.columns, _WORD_REMAP_CANON)
        f_schema = _remap_proposed(
            self._FIX_SCHEMA, fixations.columns, _FIX_REMAP_CANON
        )
        # The premise: the editor seeds no Participant for these words.
        assert w_schema["participant"] is None
        return harmonize_frames(
            remap_normalized_frame(words, w_schema, kind="words"),
            remap_normalized_frame(fixations, f_schema, kind="fixations"),
        )

    @staticmethod
    def _boxes(words):
        return sorted(
            zip(words["participant_id"], words["trial_id"], words["text"]),
        )

    def test_every_reader_keeps_their_boxes_after_a_save(self):
        from scanpath_studio.utils import extract_trial

        words, fixations = self._stored()
        before = self._boxes(words)
        words, fixations = self._save(words, fixations)
        assert self._boxes(words) == before
        assert len(extract_trial(words, "p1", "t1")) == 2
        assert len(extract_trial(words, "p2", "t2")) == 1
        assert "_stimulus_words" not in words.columns

    def test_saving_twice_neither_duplicates_nor_drops_boxes(self):
        words, fixations = self._stored()
        before = self._boxes(words)
        for _ in range(2):
            words, fixations = self._save(words, fixations)
        assert self._boxes(words) == before

    def test_a_dataset_saved_before_the_fix_is_repaired_by_the_next_save(self):
        """The broken shape the bug stored — every word on the ``""`` reader,
        still flagged — is broadcast back rather than kept broken."""
        from scanpath_studio.data import STIMULUS_WORDS_FLAG

        words, fixations = self._stored()
        before = self._boxes(words)
        broken = words.drop_duplicates(subset=["trial_id", "word_id"]).copy()
        broken["participant_id"] = ""
        broken[STIMULUS_WORDS_FLAG] = True
        words, fixations = self._save(broken, fixations)
        assert self._boxes(words) == before

    # -- through ✅ Save changes itself (`tabs._apply_remap`) -------------------

    @staticmethod
    def _apply(entry, pending, *, added=(), raws=None):
        """Press ✅ Save changes on ``entry`` with ``pending`` mappings."""
        import streamlit as st

        from scanpath_studio import tabs

        st.session_state.clear()
        st.session_state["data_source_choice"] = "study"
        st.session_state["_datasets"] = {"study": entry}
        st.session_state["_remap_pending_schemas"] = pending
        st.session_state["_remap_added_tables"] = list(added)
        for table_key, raw in (raws or {}).items():
            st.session_state[tabs._added_raw_key("study", table_key)] = raw
        tabs._apply_remap()
        problems = st.session_state.get("_remap_problems")
        return problems, st.session_state["_datasets"]["study"]

    def _entry_and_pending(self, words, fixations):
        from scanpath_studio.tabs import (
            _FIX_REMAP_CANON,
            _WORD_REMAP_CANON,
            _remap_proposed,
        )

        entry = {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "schemas": {"words": self._WORD_SCHEMA, "fixations": self._FIX_SCHEMA},
        }
        pending = {
            "words": _remap_proposed(
                self._WORD_SCHEMA, words.columns, _WORD_REMAP_CANON
            )
        }
        if not fixations.empty:
            pending["fixations"] = _remap_proposed(
                self._FIX_SCHEMA, fixations.columns, _FIX_REMAP_CANON
            )
        return entry, pending

    def test_save_changes_keeps_every_readers_boxes(self):
        words, fixations = self._stored()
        entry, pending = self._entry_and_pending(words, fixations)
        problems, saved = self._apply(entry, pending)
        assert not problems
        assert self._boxes(saved["words"]) == self._boxes(words)

    def test_a_fixations_table_added_to_a_words_only_dataset_gets_the_boxes(self):
        """UX-104 — adding the missing fixations on the edit screen harmonizes
        the added table with the words itself. Harmonizing the words against
        the (still empty) fixations *first* would stamp them with the synthetic
        reader and leave nothing to broadcast onto the added readers."""
        from scanpath_studio.data import harmonize_frames
        from scanpath_studio.utils import extract_trial

        words_only, _empty = harmonize_frames(
            normalize_words(
                pd.DataFrame(
                    {
                        "tr": ["t1", "t1"],
                        "wid": [0, 1],
                        "txt": ["The", "cat"],
                        "L": [0.0, 50.0],
                        "R": [40.0, 90.0],
                        "T": [0.0, 0.0],
                        "B": [20.0, 20.0],
                    }
                ),
                self._WORD_SCHEMA,
            ),
            normalize_fixations(
                pd.DataFrame(columns=["subj", "tr", "fx", "fy", "dur"]),
                self._FIX_SCHEMA,
            ),
        )
        entry, pending = self._entry_and_pending(words_only, pd.DataFrame())
        pending["fixations"] = self._FIX_SCHEMA
        raw_fix = pd.DataFrame(
            {
                "subj": ["p1", "p2"],
                "tr": ["t1", "t1"],
                "fx": [10.0, 60.0],
                "fy": [5.0, 5.0],
                "dur": [100, 90],
            }
        )
        problems, saved = self._apply(
            entry, pending, added=["fixations"], raws={"fixations": raw_fix}
        )
        assert not problems
        for reader in ("p1", "p2"):
            assert sorted(extract_trial(saved["words"], reader, "t1")["text"]) == [
                "The",
                "cat",
            ]

    def test_rows_that_are_not_reader_copies_are_never_merged(self):
        """The collapse keeps one *reader's* copy, never one row per word id:
        character AOIs share a word id, and word ids that are not numbers all
        fold to NaN — deduplicating on the id would merge either into one box."""
        words, fixations = self._stored()
        # Two boxes per word (character AOIs) for t1, on every reader's copy.
        doubled = pd.concat([words, words.assign(x=words["x"] + 5)])
        doubled.loc[doubled["trial_id"] == "t2", "word_id"] = float("nan")
        entry, pending = self._entry_and_pending(doubled, fixations)
        problems, saved = self._apply(entry, pending)
        assert not problems
        assert len(saved["words"]) == len(doubled)

    def test_a_mapping_that_matches_no_trial_is_refused_not_saved(self):
        """The broadcast keeps only trials someone read; a Trial pick that
        matches none would otherwise overwrite the boxes with nothing."""
        words, fixations = self._stored()
        words = words.assign(item=["zz"] * len(words))
        entry, pending = self._entry_and_pending(words, fixations)
        pending["words"] = {**pending["words"], "trial": "item"}
        problems, saved = self._apply(entry, pending)
        assert problems and "words" in problems
        assert saved is entry
        assert self._boxes(saved["words"]) == self._boxes(words)

    # -- datasets the bug already saved --------------------------------------

    def _stranded(self):
        """What the old ✅ Save changes stored: every word on the ``""``
        placeholder reader, the broadcast flag still set."""
        from scanpath_studio.data import STIMULUS_WORDS_FLAG

        words, fixations = self._stored()
        broken = words.drop_duplicates(subset=["trial_id", "word_id"]).copy()
        broken["participant_id"] = ""
        broken[STIMULUS_WORDS_FLAG] = True
        return words, broken, fixations

    def test_a_stranded_table_is_repaired(self):
        from scanpath_studio.data import repair_stranded_stimulus_words

        healthy, broken, fixations = self._stranded()
        repaired = repair_stranded_stimulus_words(broken, fixations)
        assert repaired is not None
        assert self._boxes(repaired[0]) == self._boxes(healthy)
        assert "_stimulus_words" not in repaired[0].columns

    def test_a_healthy_table_is_left_alone(self):
        from scanpath_studio.data import repair_stranded_stimulus_words

        words, fixations = self._stored()
        assert repair_stranded_stimulus_words(words, fixations) is None

    def test_opening_a_stranded_dataset_repairs_it_in_the_store(self):
        """The app repairs it on load — in `_datasets` itself, so the recovery
        cache writes the repaired frames and it stays fixed."""
        from streamlit.testing.v1 import AppTest

        from tests.conftest import APP_SCRIPT

        healthy, broken, fixations = self._stranded()
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["_datasets"] = {
            "study": {
                "words": broken,
                "fixations": fixations,
                "raw_gaze": pd.DataFrame(),
                "schemas": {"words": self._WORD_SCHEMA, "fixations": self._FIX_SCHEMA},
            }
        }
        at.session_state["data_source_choice"] = "study"
        at.session_state["setup_complete"] = True
        at.run(timeout=90)
        assert not at.exception, at.exception
        stored = at.session_state["_datasets"]["study"]["words"]
        assert self._boxes(stored) == self._boxes(healthy)

    def test_per_reader_aoi_tables_are_untouched(self):
        """The ordinary shape — a Participant mapped on the words — takes the
        same save and comes back identical."""
        from scanpath_studio.data import harmonize_frames

        raw_w = pd.DataFrame(
            {
                "subj": ["p1", "p1"],
                "tr": ["t1", "t1"],
                "wid": [0, 1],
                "txt": ["The", "cat"],
                "L": [0.0, 50.0],
                "R": [40.0, 90.0],
                "T": [0.0, 0.0],
                "B": [20.0, 20.0],
            }
        )
        raw_f = pd.DataFrame(
            {"subj": ["p1"], "tr": ["t1"], "fx": [10.0], "fy": [5.0], "dur": [100]}
        )
        w_schema = {**self._WORD_SCHEMA, "participant": "subj"}
        words, fixations = harmonize_frames(
            normalize_words(raw_w, w_schema),
            normalize_fixations(raw_f, self._FIX_SCHEMA),
        )
        canonical = {
            "participant": "participant_id",
            "trial": "trial_id",
            "word_id": "word_id",
            "text": "text",
            "x": "x",
            "y": "y",
            "width": "width",
            "height": "height",
        }
        out = remap_normalized_frame(words, canonical, kind="words")
        out, _ = harmonize_frames(out, fixations)
        assert self._boxes(out) == self._boxes(words)


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


class TestEditorSetupExport:
    """The ✏️ Edit dataset footer's ⬇️ Save setup — the add screen's own export,
    for the screen that edits what it created.

    It exists so an already-added dataset's mapping can travel: a share link
    carries settings but never files, so "send them the files and this JSON" is
    the only way the recipient skips re-mapping by hand.
    """

    def _session(self, monkeypatch):
        import streamlit as st

        st.session_state.clear()
        return st.session_state

    def test_the_editor_keys_are_rewritten_into_the_add_screens(self, monkeypatch):
        from scanpath_studio.tabs import _editor_setup_config

        session = self._session(monkeypatch)
        session["remap_My corpus_words_x"] = "left_px"
        session["remap_My corpus_words_box_format"] = "Origin + size"
        session["remap_My corpus_fixations_duration"] = "dur_ms"
        session["remap_My corpus_fixations_trial"] = ["reader", "item"]
        session["remap_My corpus_raw_gaze_timestamp"] = "t"
        # Scaffolding under the same prefix that is not part of the mapping.
        session["remap_My corpus_words_x_cell_confirm"] = False
        session["remap_My corpus_words_header"] = ["left_px", "top_px"]
        session["_remap_pending_setup"] = {"canvas_width": 1920}

        mapping = _editor_setup_config("My corpus")["column_mapping"]

        assert mapping["col_map_words_x"] == "left_px"
        assert mapping["col_map_words_box_format"] == "Origin + size"
        assert mapping["col_map_fix_duration"] == "dur_ms"
        # A composite trial id survives as a list, which is what it means.
        assert mapping["col_map_fix_trial"] == ["reader", "item"]
        assert mapping["col_map_raw_gaze_timestamp"] == "t"
        assert not [k for k in mapping if "_cell" in k or k.endswith("_header")]

    def test_the_file_is_the_shape_the_wizards_restore_reads(self, monkeypatch):
        """`_seed_column_mapping` only writes keys that start with `col_map_`, so
        a file whose keys were left in the editor's namespace would restore
        nothing at all — silently."""
        from scanpath_studio.tabs import _editor_setup_config
        from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA, _seed_column_mapping

        session = self._session(monkeypatch)
        session["remap_My corpus_words_x"] = "left_px"
        session["_remap_pending_setup"] = {"canvas_width": 1920}
        config = _editor_setup_config("My corpus")

        assert config["schema"] == PLOT_CONFIG_SCHEMA
        assert config["data_source"] == "My corpus"
        assert config["experimental_setup"] == {"canvas_width": 1920}

        session.clear()
        _seed_column_mapping(config["column_mapping"], overwrite=True)
        assert session["col_map_words_x"] == "left_px"

    def test_the_footer_offers_both_halves_of_the_add_screens_pair(self):
        """Source-level: AppTest reports no download_button, and what must not
        silently regress is that the editor's last row is the *pair*."""
        import inspect

        from scanpath_studio.tabs import render_dataset_editor_footer

        source = inspect.getsource(render_dataset_editor_footer)
        assert "⬇️ Save setup" in source
        assert "✅ Save changes" in source
        assert "_editor_setup_config" in source
        # It borrows the wizard's own column widths so the two rows line up.
        assert "_FOOTER_ROW_W" in source
