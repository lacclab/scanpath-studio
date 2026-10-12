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
    normalize_raw_gaze,
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


def _normalized_raw_gaze() -> pd.DataFrame:
    raw = pd.DataFrame(
        {
            "reader": ["p1", "p1"],
            "trial": ["t1", "t1"],
            "gx": [100.0, 110.0],
            "gy": [200.0, 210.0],
            "alt_x": [333.0, 343.0],
            "time_ms": [50, 51],
            "pupil": [3.5, 3.6],
            "quality": ["good", "poor"],
            "source_file": ["s1", "s1"],
        }
    )
    schema = {
        "participant": "reader",
        "trial": "trial",
        "x": "gx",
        "y": "gy",
        "timestamp": "time_ms",
    }
    keep = {"alt_x", "pupil", "quality", "source_file"}
    return normalize_raw_gaze(raw, schema, keep_columns=keep)


_RAW_GAZE_IDENTITY = {
    "participant": "participant_id",
    "trial": "trial_id",
    "x": "x",
    "y": "y",
    "timestamp": "timestamp_ms",
}


class TestRawGazeRemapKeepsColumns:
    """A raw-gaze remap reassigns roles; it never drops retained columns."""

    def test_identity_remap_keeps_extras(self):
        before = _normalized_raw_gaze()
        after = remap_normalized_frame(before, _RAW_GAZE_IDENTITY, kind="raw_gaze")
        assert set(before.columns) <= set(after.columns)
        assert after["pupil"].tolist() == [3.5, 3.6]
        assert after["quality"].tolist() == ["good", "poor"]
        assert after["source_file"].tolist() == ["s1", "s1"]

    def test_changed_mapping_keeps_unrelated_extras(self):
        before = _normalized_raw_gaze()
        after = remap_normalized_frame(
            before, {**_RAW_GAZE_IDENTITY, "x": "alt_x"}, kind="raw_gaze"
        )
        assert after["x"].tolist() == [333.0, 343.0]
        assert after["pupil"].tolist() == [3.5, 3.6]
        assert after["quality"].tolist() == ["good", "poor"]
        assert after["source_file"].tolist() == ["s1", "s1"]


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

        raw_w, raw_f = self._raw()
        return harmonize_frames(
            normalize_words(raw_w, self._WORD_SCHEMA),
            normalize_fixations(raw_f, self._FIX_SCHEMA),
        )

    @staticmethod
    def _raw():
        """The two files that upload was read from."""
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
        return raw_w, raw_f

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

    def test_save_changes_keeps_a_mapping_the_files_can_be_loaded_with(self):
        """Share → Code loads the dataset's own files. ✅ Save changes stores
        a mapping onto the canonical columns, so the snippet's record of the
        mapping is restated in the files' names — and still loads them."""
        from scanpath_studio import api
        from scanpath_studio.column_names import for_tables

        raw_w, raw_f = self._raw()
        words, fixations = self._stored()
        entry, pending = self._entry_and_pending(words, fixations)
        entry["column_names"] = for_tables(
            entry["schemas"], {"words": raw_w, "fixations": raw_f}
        )
        problems, saved = self._apply(entry, pending)
        assert not problems
        recipe = saved["source_recipe"]
        assert not recipe.get("unresolved")
        schemas = recipe["schemas"]
        assert schemas["fixations"]["duration"] == "dur"
        assert schemas["words"]["left"] == "L" and schemas["words"]["right"] == "R"
        reloaded, _fix = api.load_scanpath_data(
            raw_w,
            raw_f,
            word_schema=schemas["words"],
            fix_schema=schemas["fixations"],
            names="canonical",
        )
        assert self._boxes(reloaded) == self._boxes(saved["words"])

    def test_save_changes_applies_the_name_typed_on_the_editor(self):
        """UX-178 — the editor's **Name** is applied by ✅ Save changes, after
        the entry is saved under the name its widgets were keyed by."""
        import streamlit as st

        from scanpath_studio import tabs

        words, fixations = self._stored()
        entry, pending = self._entry_and_pending(words, fixations)
        st.session_state.clear()
        st.session_state["data_source_choice"] = "study"
        st.session_state["_datasets"] = {"study": entry}
        st.session_state["_remap_pending_schemas"] = pending
        st.session_state[tabs.EDITOR_PENDING_NAME_KEY] = "Pilot study"
        tabs._apply_remap()
        assert not st.session_state.get("_remap_problems")
        assert set(st.session_state["_datasets"]) == {"Pilot study"}
        assert st.session_state["_pending_source_choice"] == "Pilot study"
        assert st.session_state["_remap_applied"] == "Pilot study"
        # The edit is over: the staged name goes with the rest of it.
        assert tabs.EDITOR_PENDING_NAME_KEY not in st.session_state

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
        """The broadcast keeps only texts someone read; a Trial *and* Text pick
        that match none would otherwise overwrite the boxes with nothing."""
        words, fixations = self._stored()
        words = words.assign(item=["zz"] * len(words))
        entry, pending = self._entry_and_pending(words, fixations)
        pending["words"] = {**pending["words"], "trial": "item", "text_id": "item"}
        problems, saved = self._apply(entry, pending)
        assert problems and "words" in problems
        # Refused by the join itself (`StimulusJoinError`, via
        # `app.mapping_failure_problem`), not by a later "no boxes" check.
        from scanpath_studio.app import MAPPING_FAILURE_LEAD

        (problem,) = problems["words"]
        assert problem.startswith(MAPPING_FAILURE_LEAD)
        assert "in the fixations finds them" in problem
        assert "share neither a Trial ID nor a Text ID" in problem
        assert saved is entry
        assert self._boxes(saved["words"]) == self._boxes(words)

    def test_a_text_joined_dataset_survives_a_new_fixation_trial_pick(self):
        """DATA-49 review: once joined by Text ID, the stored boxes carry each
        reading's own trial id. The save must collapse them back to one copy
        per *text*, or changing the fixations' Trial ID pick finds every text
        naming several trials and refuses a dataset that still joins."""
        from scanpath_studio.data import harmonize_frames
        from scanpath_studio.tabs import (
            _FIX_REMAP_CANON,
            _WORD_REMAP_CANON,
            _remap_proposed,
        )
        from scanpath_studio.utils import extract_trial

        word_schema = {**self._WORD_SCHEMA, "trial": "text", "text_id": "text"}
        fix_schema = {**self._FIX_SCHEMA, "text_id": "text"}
        raw_w = pd.DataFrame(
            {
                "text": ["t1", "t1", "t2"],
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
                "tr": ["p1_t1", "p1_t2", "p2_t1", "p2_t2"],
                "alt": ["A1", "A2", "B1", "B2"],
                "text": ["t1", "t2", "t1", "t2"],
                "fx": [10.0, 20.0, 12.0, 20.0],
                "fy": [5.0, 5.0, 5.0, 5.0],
                "dur": [100, 150, 90, 120],
            }
        )
        words, fixations = harmonize_frames(
            normalize_words(raw_w, word_schema),
            normalize_fixations(raw_f, fix_schema, keep_columns={"alt"}),
        )
        assert set(words["trial_id"]) == {"p1_t1", "p1_t2", "p2_t1", "p2_t2"}
        entry = {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "schemas": {"words": word_schema, "fixations": fix_schema},
        }
        pending = {
            "words": _remap_proposed(word_schema, words.columns, _WORD_REMAP_CANON),
            "fixations": {
                **_remap_proposed(fix_schema, fixations.columns, _FIX_REMAP_CANON),
                "trial": "alt",
            },
        }
        problems, saved = self._apply(entry, pending)
        assert not problems
        for reader, trial, text in (
            ("p1", "A1", ["The", "cat"]),
            ("p1", "A2", ["Dogs"]),
            ("p2", "B1", ["The", "cat"]),
            ("p2", "B2", ["Dogs"]),
        ):
            assert extract_trial(saved["words"], reader, trial)["text"].tolist() == text

    def test_a_trial_pick_that_matches_nothing_is_refused_without_a_text_id(self):
        """DATA-49 round 4: with no Text ID mapped on the fixations, their
        ``text_id`` is only their own trial id, which names no text — so it
        cannot stand in for a Trial pick the fixations do not share, and the
        save is refused rather than guessed. (With a real Text ID it saves:
        ``TestStimulusProvenanceOnRemap``.)"""
        words, fixations = self._stored()
        words = words.assign(item=["zz"] * len(words))
        entry, pending = self._entry_and_pending(words, fixations)
        pending["words"] = {**pending["words"], "trial": "item"}
        problems, saved = self._apply(entry, pending)
        assert problems and "words" in problems
        assert saved is entry

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


def _setup_file_raw_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """An AOI table with *edge* boxes and a fixation table with a seconds
    duration and a composite trial id, every column under a name the app does
    not use — the case a setup file has to restate faithfully."""
    words = pd.DataFrame(
        {
            "reader": ["p1", "p1"],
            "session": ["s1", "s1"],
            "item": ["i1", "i1"],
            "wid": [1, 2],
            "token": ["Hello", "world"],
            "L": [10.0, 70.0],
            "R": [60.0, 130.0],
            "T": [20.0, 20.0],
            "B": [40.0, 40.0],
        }
    )
    fixations = pd.DataFrame(
        {
            "reader": ["p1", "p1"],
            "session": ["s1", "s1"],
            "item": ["i1", "i1"],
            "fx": [30.0, 100.0],
            "fy": [30.0, 30.0],
            "dur [s]": [0.2, 0.25],
            "alt_x": [333.0, 444.0],
        }
    )
    return words, fixations


_SETUP_WORD_SCHEMA = {
    "participant": "reader",
    "trial": ["session", "item"],
    "word_id": "wid",
    "text": "token",
    "left": "L",
    "right": "R",
    "top": "T",
    "bottom": "B",
}
_SETUP_FIX_SCHEMA = {
    "participant": "reader",
    "trial": ["session", "item"],
    "x": "fx",
    "y": "fy",
    "duration": "dur [s]",
}


def _setup_file_editor_app():
    """✏️ Edit dataset over the tables above, with the real field grid; its
    setup file lands in ``config``. ``_choose_alt_x`` maps X to a kept column."""
    import streamlit as st

    from scanpath_studio.app import _edit_open_dataset
    from scanpath_studio.column_names import from_schema
    from scanpath_studio.data import (
        harmonize_frames,
        normalize_fixations,
        normalize_words,
    )
    from scanpath_studio.tabs import _editor_setup_config, _render_remap_editor
    from tests.test_remap import (
        _SETUP_FIX_SCHEMA,
        _SETUP_WORD_SCHEMA,
        _setup_file_raw_tables,
    )

    if "_datasets" not in st.session_state:
        raw_words, raw_fix = _setup_file_raw_tables()
        words, fixations = harmonize_frames(
            normalize_words(raw_words, _SETUP_WORD_SCHEMA),
            normalize_fixations(raw_fix, _SETUP_FIX_SCHEMA, keep_columns={"alt_x"}),
        )
        st.session_state["_datasets"] = {
            "Lab": {
                "words": words,
                "fixations": fixations,
                "schemas": {
                    "words": _SETUP_WORD_SCHEMA,
                    "fixations": _SETUP_FIX_SCHEMA,
                },
                "composite_trial_columns": ["session", "item"],
                "column_names": {
                    "words": from_schema(
                        "words", _SETUP_WORD_SCHEMA, raw_words.columns
                    ).to_payload(),
                    "fixations": from_schema(
                        "fixations", _SETUP_FIX_SCHEMA, raw_fix.columns
                    ).to_payload(),
                },
            }
        }
        st.session_state["data_source_choice"] = "Lab"
        _edit_open_dataset("Lab")
    stored = st.session_state["_datasets"]["Lab"]
    _render_remap_editor("Lab", stored)
    st.session_state["config"] = _editor_setup_config("Lab")


def _setup_file_restore_app():
    """A fresh add screen restoring that file over the *original* files: the
    real ``column_mapping_ui`` for each table, its mapping in ``restored``."""
    import streamlit as st

    from scanpath_studio.controls import (
        FIX_FIELD_SPECS,
        WORD_FIELD_SPECS,
        column_mapping_ui,
    )
    from scanpath_studio.data import propose_fix_schema, propose_word_schema
    from scanpath_studio.url_state import _seed_column_mapping
    from tests.test_remap import _setup_file_raw_tables

    if "restored" not in st.session_state:
        _seed_column_mapping(st.session_state["file"], overwrite=True)
    raw_words, raw_fix = _setup_file_raw_tables()
    st.session_state["restored"] = {
        "words": column_mapping_ui(
            raw_words,
            table_label="AOI",
            state_key_prefix="col_map_words",
            field_specs=WORD_FIELD_SPECS,
            proposed=propose_word_schema(raw_words),
        ),
        "fixations": column_mapping_ui(
            raw_fix,
            table_label="Fixations",
            state_key_prefix="col_map_fix",
            field_specs=FIX_FIELD_SPECS,
            proposed=propose_fix_schema(raw_fix),
        ),
    }


class TestEditorSetupExport:
    """The ✏️ Edit dataset footer's ⬇️ Download setup file — the add screen's own export,
    for the screen that edits what it created.

    It exists so an already-added dataset's mapping can travel: a share link
    carries settings but never files, so "send them the files and this JSON" is
    the only way the recipient skips re-mapping by hand. Which means the file
    has to name **the files' columns**, not the stored frame's canonical ones.
    """

    def _names(self, table, schema, raw):
        from scanpath_studio.column_names import from_schema

        return from_schema(table, schema, raw.columns).to_payload()

    def test_a_stored_table_is_written_in_its_files_column_names(self):
        from scanpath_studio.tabs import _setup_file_mapping

        raw_words, raw_fix = _setup_file_raw_tables()
        stored = {
            "column_names": {
                "words": self._names("words", _SETUP_WORD_SCHEMA, raw_words),
                "fixations": self._names("fixations", _SETUP_FIX_SCHEMA, raw_fix),
            }
        }
        # What the editor's pickers hold: the stored frame's canonical columns.
        pending = {
            "fixations": {
                "participant": "participant_id",
                "trial": ["session", "item"],
                "text_id": "text_id",
                "x": "alt_x",
                "y": "y",
                "duration": "duration_ms",
            },
            "words": {
                "participant": "participant_id",
                "trial": ["session", "item"],
                "word_id": "word_id",
                "text": "text",
                "x": "x",
                "y": "y",
                "width": "width",
                "height": "height",
                "left": None,
                "right": None,
                "top": None,
                "bottom": None,
            },
        }
        mapping, notes = _setup_file_mapping(pending, stored)

        assert mapping["col_map_fix_participant"] == "reader"
        assert mapping["col_map_fix_trial"] == ["session", "item"]
        # The pending edit, in the file's name; a seconds column by its own
        # name, which the add screen converts again.
        assert mapping["col_map_fix_x"] == "alt_x"
        assert mapping["col_map_fix_y"] == "fy"
        assert mapping["col_map_fix_duration"] == "dur [s]"
        # The app made the text id from the trial id: written unmapped, so the
        # add screen makes it again, never as a column the files lack.
        assert mapping["col_map_fix_text_id"] is None
        # A box read from edges is restated as those edges.
        assert mapping["col_map_words_box_format"] == "Edges"
        assert [mapping[f"col_map_words_{k}"] for k in ("left", "right")] == [
            "L",
            "R",
        ]
        assert [mapping[f"col_map_words_{k}"] for k in ("top", "bottom")] == [
            "T",
            "B",
        ]
        assert "col_map_words_width" not in mapping
        assert mapping["col_map_words_word_id"] == "wid"
        assert mapping["col_map_words_text"] == "token"
        assert notes == []

    def test_a_table_being_added_uses_the_add_screens_keys(self):
        """Its widgets carry an ``_add`` suffix in the editor; the file must
        not, or the add screen restores nothing for it."""
        from scanpath_studio.tabs import _setup_file_mapping

        pending = {"words": {"trial": "item", "x": "x0", "y": "y0", "width": "w"}}
        mapping, notes = _setup_file_mapping(
            pending, {}, added={"words"}, box_formats={"words": "Origin + size"}
        )
        assert mapping["col_map_words_x"] == "x0"
        assert mapping["col_map_words_box_format"] == "Origin + size"
        # Trial ID is a multiselect on the add screen.
        assert mapping["col_map_words_trial"] == ["item"]
        assert not [k for k in mapping if "_add" in k]
        assert notes == []

    def test_what_a_restore_cannot_reproduce_is_said(self):
        from scanpath_studio.tabs import _setup_file_mapping

        stored = {
            "column_names": {"fixations": {"trial_id": {"sources": ["item"]}}},
            "source_recipe": {"derived": ["item"], "steps": []},
        }
        _mapping, notes = _setup_file_mapping(
            {"fixations": {"trial": "trial_id"}}, stored
        )
        assert any("file names" in note for note in notes)
        # A dataset stored before the column-name map existed says so.
        _mapping, notes = _setup_file_mapping({"fixations": {"x": "x"}}, {})
        assert any("before the app kept" in note for note in notes)

    def test_edit_then_restore_over_the_original_files_gives_the_same_mapping(
        self,
    ):
        """End to end: the real editor writes the file, and a fresh add screen
        restoring it over the original files maps them exactly as the edit
        does — including the edit itself (X → ``alt_x``)."""
        from streamlit.testing.v1 import AppTest

        editor = AppTest.from_function(_setup_file_editor_app, default_timeout=30)
        editor.run()
        assert not editor.exception, editor.exception
        editor.selectbox(key="remap_Lab_fixations_x").set_value("alt_x").run()
        assert not editor.exception, editor.exception
        config = editor.session_state["config"]
        assert config["column_mapping_notes"] == []

        restore = AppTest.from_function(_setup_file_restore_app, default_timeout=30)
        restore.session_state["file"] = config["column_mapping"]
        restore.run()
        assert not restore.exception, restore.exception
        restored = restore.session_state["restored"]

        expected_fix = {**_SETUP_FIX_SCHEMA, "x": "alt_x"}
        for key, value in expected_fix.items():
            assert restored["fixations"][key] == value, key
        for key, value in _SETUP_WORD_SCHEMA.items():
            assert restored["words"][key] == value, key
        # And the frames it builds are the ones the edit saves.
        _raw_words, raw_fix = _setup_file_raw_tables()
        again = normalize_fixations(raw_fix, restored["fixations"])
        assert again["x"].tolist() == [333.0, 444.0]
        assert again["duration_ms"].tolist() == [200.0, 250.0]

    def test_the_footer_offers_both_halves_of_the_add_screens_pair(self):
        """Source-level: AppTest reports no download_button, and what must not
        silently regress is that the editor's last row is the *pair*."""
        import inspect

        from scanpath_studio.tabs import render_dataset_editor_footer

        source = inspect.getsource(render_dataset_editor_footer)
        assert "f\"{ICONS['download']} Download setup file\"" in source
        assert "f\"{ICONS['confirm']} Save changes\"" in source
        assert "_editor_setup_config" in source
        assert "column_mapping_notes" in source
        # It borrows the wizard's own column widths so the two rows line up.
        assert "_FOOTER_ROW_W" in source


class TestStimulusProvenanceOnRemap:
    """DATA-49 review, round 3: a broadcast copy carries the AOI trial it came
    from (`data.AOI_TRIAL_ID`), so ✏️ Edit dataset gets the stimulus table back
    exactly — one copy per AOI trial — whatever route each reading took."""

    _EDGE = {
        "word_id": "wid",
        "text": "txt",
        "left": "L",
        "right": "R",
        "top": "T",
        "bottom": "B",
    }
    _FIX = {
        "participant": "subj",
        "trial": "tr",
        "x": "fx",
        "y": "fy",
        "duration": "dur",
    }

    @staticmethod
    def _aoi(trials, texts, labels, **extra):
        n = len(trials)
        return pd.DataFrame(
            {
                "item": trials,
                "text": texts,
                "wid": list(range(n)),
                "txt": labels,
                "L": [0.0] * n,
                "R": [40.0] * n,
                "T": [0.0] * n,
                "B": [20.0] * n,
                **extra,
            }
        )

    @staticmethod
    def _fix(subjects, trials, texts, **extra):
        n = len(subjects)
        return pd.DataFrame(
            {
                "subj": subjects,
                "tr": trials,
                "text": texts,
                "fx": [10.0] * n,
                "fy": [5.0] * n,
                "dur": [100] * n,
                **extra,
            }
        )

    def _save(
        self,
        raw_w,
        word_schema,
        raw_f,
        fix_schema,
        *,
        words_pick=None,
        fix_pick=None,
        keep_w=(),
        keep_f=(),
    ):
        """Load the pair as the wizard stores it, then press ✅ Save changes with
        the editor's own proposals (optionally re-picking one Trial ID)."""
        from scanpath_studio.data import harmonize_frames
        from scanpath_studio.tabs import (
            _FIX_REMAP_CANON,
            _WORD_REMAP_CANON,
            _remap_proposed,
        )

        words, fixations = harmonize_frames(
            normalize_words(raw_w, word_schema, keep_columns=set(keep_w) or None),
            normalize_fixations(raw_f, fix_schema, keep_columns=set(keep_f) or None),
        )
        entry = {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "schemas": {"words": word_schema, "fixations": fix_schema},
        }
        pending = {
            "words": _remap_proposed(word_schema, words.columns, _WORD_REMAP_CANON),
            "fixations": _remap_proposed(
                fix_schema, fixations.columns, _FIX_REMAP_CANON
            ),
        }
        if words_pick:
            pending["words"] = {**pending["words"], "trial": words_pick}
        if fix_pick:
            pending["fixations"] = {**pending["fixations"], "trial": fix_pick}
        problems, saved = TestStimulusLevelWordsRemap._apply(entry, pending)
        return words, problems, saved

    @staticmethod
    def _cells(words, reader, trial, column="text"):
        from scanpath_studio.utils import extract_trial

        return extract_trial(words, reader, trial)[column].tolist()

    def test_a_kept_column_that_differs_between_identical_trials_survives(self):
        """F1: two AOI trials with the same text and boxes but a different
        `cond` stay two trials; an unchanged save rewrites neither."""
        raw_w = self._aoi(
            ["t4", "t5"], ["T", "T"], ["same", "same"], cond=["easy", "hard"]
        )
        raw_w["wid"] = [0, 0]
        raw_f = self._fix(["p1", "p1", "p2", "p2"], ["t4", "t5", "t4", "t5"], ["T"] * 4)
        _before, problems, saved = self._save(
            raw_w,
            {**self._EDGE, "trial": "item", "text_id": "text"},
            raw_f,
            {**self._FIX, "text_id": "text"},
            keep_w=("cond",),
        )
        assert not problems
        for reader in ("p1", "p2"):
            assert self._cells(saved["words"], reader, "t4", "cond") == ["easy"]
            assert self._cells(saved["words"], reader, "t5", "cond") == ["hard"]

    def test_a_mixed_route_dataset_survives_a_new_fixation_trial_pick(self):
        """F2: one reading joined by trial id, one by Text ID; a new fixations
        Trial ID pick re-joins both by text instead of refusing."""
        raw_w = self._aoi(["A", "B"], ["tA", "tB"], ["a", "b"])
        raw_f = self._fix(["p1", "p2"], ["A", "p2_B"], ["tA", "tB"], alt=["X1", "X2"])
        _before, problems, saved = self._save(
            raw_w,
            {**self._EDGE, "trial": "item", "text_id": "text"},
            raw_f,
            {**self._FIX, "text_id": "text"},
            fix_pick="alt",
            keep_f=("alt",),
        )
        assert not problems
        assert self._cells(saved["words"], "p1", "X1") == ["a"]
        assert self._cells(saved["words"], "p2", "X2") == ["b"]

    def _repeat_case(self, **kwargs):
        raw_w = self._aoi(["a1p1", "a1p2"], ["a1", "a1"], ["first", "second"])
        # The raw paragraph column the repro re-picks, kept as an extra field.
        raw_w["paragraph"] = raw_w["item"]
        raw_f = self._fix(
            ["r1", "r1", "r1"],
            ["a1p1", "a1p2", "a1p1"],
            ["a1"] * 3,
            TRIAL_INDEX=[1, 2, 3],
        )
        return self._save(
            raw_w,
            {**self._EDGE, "trial": "item", "text_id": "text"},
            raw_f,
            {**self._FIX, "text_id": "text"},
            keep_w=("paragraph",),
            **kwargs,
        )

    def test_a_repeat_keeps_one_copy_of_its_boxes_under_the_default_proposal(self):
        """F3, the editor's own proposal: the fixations' Trial ID stays the
        stored (suffixed) `trial_id`, so `_base_trial_id` must survive it."""
        before, problems, saved = self._repeat_case()
        assert not problems
        assert self._cells(before, "r1", "a1p1_r2") == ["first"]
        for trial, text in (
            ("a1p1", ["first"]),
            ("a1p1_r2", ["first"]),
            ("a1p2", ["second"]),
        ):
            assert self._cells(saved["words"], "r1", trial) == text, trial

    def test_a_repeat_keeps_one_copy_after_re_picking_the_words_trial_id(self):
        """F3, the repro: re-pick the words' Trial ID to the raw paragraph column —
        `a1p1` must not get its boxes twice, nor `a1p1_r2` none."""
        _before, problems, saved = self._repeat_case(words_pick="paragraph")
        assert not problems
        for trial, text in (
            ("a1p1", ["first"]),
            ("a1p1_r2", ["first"]),
            ("a1p2", ["second"]),
        ):
            assert self._cells(saved["words"], "r1", trial) == text, trial

    def test_a_partial_join_during_a_save_is_shown_on_the_page(self):
        """F5: the warning is raised inside the button's callback, so it is
        parked for the screen the save returns to."""
        import warnings

        import streamlit as st

        from scanpath_studio import tabs

        raw_w = self._aoi(["t1"], ["t1"], ["one"])
        raw_f = self._fix(["p1", "p2"], ["t1", "q"], ["t1", "zz"])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _before, problems, _saved = self._save(
                raw_w,
                {**self._EDGE, "trial": "item", "text_id": "text"},
                raw_f,
                {**self._FIX, "text_id": "text"},
            )
        assert not problems
        notices = st.session_state.get(tabs.STIMULUS_JOIN_NOTICE_KEY)
        assert notices and "1 of 2 trials have word boxes" in notices[0]


class TestLegacyStoredRepeats:
    """DATA-49 round 4: a dataset stored before the join recorded provenance
    (v0.32.0 — no `_aoi_trial_id`, no `_base_trial_id`) with a repeated
    reading. Its repeat's copy of the boxes carries the `_r2` id; the save
    must fold it back into the trial it copied, or it becomes a phantom AOI
    trial that makes its text ambiguous for good — and a later save that
    re-joins by Text ID then leaves 3 of 4 readings without boxes."""

    def test_two_saves_keep_every_readings_boxes(self):
        from scanpath_studio.data import AOI_TRIAL_ID, BASE_TRIAL_ID, harmonize_frames
        from scanpath_studio.tabs import (
            _FIX_REMAP_CANON,
            _WORD_REMAP_CANON,
            _remap_proposed,
        )
        from scanpath_studio.utils import extract_trial

        word_schema = {
            "trial": "tr",
            "word_id": "wid",
            "text": "txt",
            "left": "L",
            "right": "R",
            "top": "T",
            "bottom": "B",
        }
        fix_schema = {
            "participant": "subj",
            "trial": "tr",
            "text_id": "tx",
            "x": "fx",
            "y": "fy",
            "duration": "dur",
        }
        raw_w = pd.DataFrame(
            {
                "tr": ["a", "a", "b"],
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
                "subj": ["r1", "r1", "r1", "r2"],
                "tr": ["a", "b", "a", "a"],
                "tx": ["a", "b", "a", "a"],
                "alt": ["A1", "A2", "A3", "B1"],
                "TRIAL_INDEX": [1, 2, 3, 1],
                "fx": [10.0] * 4,
                "fy": [5.0] * 4,
                "dur": [100] * 4,
            }
        )
        words, fixations = harmonize_frames(
            normalize_words(raw_w, word_schema),
            normalize_fixations(raw_f, fix_schema, keep_columns={"TRIAL_INDEX", "alt"}),
        )
        # What v0.32.0 stored: no provenance columns.
        words = words.drop(columns=[AOI_TRIAL_ID])
        fixations = fixations.drop(columns=[BASE_TRIAL_ID])
        assert set(zip(words["participant_id"], words["trial_id"])) == {
            ("r1", "a"),
            ("r1", "a_r2"),
            ("r1", "b"),
            ("r2", "a"),
        }
        entry = {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "schemas": {"words": word_schema, "fixations": fix_schema},
        }
        cat, dogs = ["The", "cat"], ["Dogs"]
        saves = (
            (
                None,
                {
                    ("r1", "a"): cat,
                    ("r1", "a_r2"): cat,
                    ("r1", "b"): dogs,
                    ("r2", "a"): cat,
                },
            ),
            (
                "alt",
                {
                    ("r1", "A1"): cat,
                    ("r1", "A3"): cat,
                    ("r1", "A2"): dogs,
                    ("r2", "B1"): cat,
                },
            ),
        )
        for fix_pick, expected in saves:
            pending = {
                "words": _remap_proposed(
                    word_schema, entry["words"].columns, _WORD_REMAP_CANON
                ),
                "fixations": _remap_proposed(
                    fix_schema, entry["fixations"].columns, _FIX_REMAP_CANON
                ),
            }
            if fix_pick:
                pending["fixations"] = {**pending["fixations"], "trial": fix_pick}
            problems, entry = TestStimulusLevelWordsRemap._apply(entry, pending)
            assert not problems
            for (reader, trial), text in expected.items():
                got = extract_trial(entry["words"], reader, trial)["text"].tolist()
                assert got == text, (fix_pick, reader, trial, got)


class TestEditorEstimateUsesPendingMapping:
    """*Estimate from my data* on ✏️ Edit dataset measures the data as it will
    be **saved** — the pending mapping, and a table being added — not the
    stored frame's old coordinates."""

    def test_a_remapped_coordinate_is_what_the_estimate_encloses(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_function(_setup_file_editor_app, default_timeout=30)
        at.run()
        at.selectbox(key="remap_Lab_fixations_x").set_value("alt_x").run()
        at.segmented_control(key="edit_Lab_setup_screen_mode").set_value(
            "Estimate from my data"
        ).run()
        assert not at.exception, at.exception
        # The old X reaches 100 and the boxes 130; the new X reaches 444.
        assert at.session_state["_remap_pending_setup"]["canvas_width"] == 500

    def test_a_table_being_added_counts_towards_the_estimate(self):
        from scanpath_studio.tabs import _pending_canvas_estimate

        _raw_words, raw_fix = _setup_file_raw_tables()
        stored = {"fixations": normalize_fixations(raw_fix, _SETUP_FIX_SCHEMA)}
        added_words = pd.DataFrame(
            {"item": ["i1"], "L": [1000.0], "R": [1450.0], "T": [900.0], "B": [950.0]}
        )
        pending = {
            "fixations": {"x": "x", "y": "y"},
            "words": {"left": "L", "right": "R", "top": "T", "bottom": "B"},
        }
        assert _pending_canvas_estimate(stored, pending, {}) == (100, 100)
        assert _pending_canvas_estimate(stored, pending, {"words": added_words}) == (
            1500,
            1000,
        )


def _two_readings() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two readings of one text by one reader (trials r1/r2, both in block
    "b1") — the case a coarser Trial ID silently merges."""
    raw_fix = pd.DataFrame(
        {
            "subj": ["p1"] * 4,
            "tr": ["r1", "r1", "r2", "r2"],
            "block": ["b1"] * 4,
            "fx": [10.0, 20.0, 30.0, 40.0],
            "fy": [5.0, 5.0, 5.0, 5.0],
            "alt_x": [110.0, 120.0, 130.0, 140.0],
            "dur": [100, 100, 100, 100],
        }
    )
    schema = {
        "participant": "subj",
        "trial": "tr",
        "x": "fx",
        "y": "fy",
        "duration": "dur",
    }
    fixations = normalize_fixations(raw_fix, schema, keep_columns={"block", "alt_x"})
    raw_words = pd.DataFrame(
        {
            "tr": ["r1", "r2"],
            "wid": [1, 1],
            "w": ["Hi", "Hi"],
            "x": [0, 0],
            "y": [0, 0],
            "width": [50, 50],
            "height": [20, 20],
        }
    )
    words = normalize_words(
        raw_words,
        {
            "trial": "tr",
            "word_id": "wid",
            "text": "w",
            "x": "x",
            "y": "y",
            "width": "width",
            "height": "height",
        },
    )
    return words, fixations


_IDENTITY_PICKS = {
    "participant": "participant_id",
    "trial": "trial_id",
    "text_id": "text_id",
    "x": "x",
    "y": "y",
}


class TestPendingChangePreview:
    """✏️ Edit dataset says what ✅ Save changes will do to the ids and
    coordinates before it does — a few rows always, the counts and joins on
    request."""

    def test_an_untouched_mapping_previews_nothing(self):
        from scanpath_studio.tabs import pending_value_changes

        _words, fixations = _two_readings()
        assert pending_value_changes(fixations, dict(_IDENTITY_PICKS)) == []

    def test_a_changed_pick_shows_rows_now_and_after(self):
        from scanpath_studio.tabs import pending_value_changes

        _words, fixations = _two_readings()
        pending = {**_IDENTITY_PICKS, "trial": "block", "x": "alt_x"}
        rows = {row["field"]: row for row in pending_value_changes(fixations, pending)}
        assert set(rows) == {"trial", "x"}
        assert rows["trial"]["now"] == ["r1", "r2"]
        assert rows["trial"]["after"] == ["b1", "b1"]
        assert rows["x"]["now"][:2] == ["10", "20"]
        assert rows["x"]["after"][:2] == ["110", "120"]

    def test_the_census_counts_merged_readings_and_broken_joins(self):
        from scanpath_studio.tabs import pending_census

        words, fixations = _two_readings()
        pending = {"fixations": {**_IDENTITY_PICKS, "trial": "block"}}
        readers = pd.DataFrame({"participant_id": ["p1"], "age": [30]})
        trials = pd.DataFrame({"trial_id": ["r1", "r2"], "cond": ["a", "b"]})
        census = {
            row["what"]: (row["now"], row["after"])
            for row in pending_census(
                {"words": words, "fixations": fixations},
                pending,
                {"participants": readers, "trials": trials},
            )
        }
        # Two readings become one scanpath…
        assert census["Trials"] == (2, 1)
        # …which no word box and no trial-table row is keyed by any more.
        assert census["Trials with word boxes"] == ("2 of 2", "0 of 1")
        assert census["Trials in the trial table"] == ("2 of 2", "0 of 1")
        # The readers are untouched.
        assert census["Participants in the participant table"] == ("1 of 1", "1 of 1")

    def test_the_editor_shows_it_and_counts_on_request(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_function(_setup_file_editor_app, default_timeout=30)
        at.run()
        assert not [m for m in at.markdown if "What Save changes will do" in m.value]
        at.selectbox(key="remap_Lab_fixations_x").set_value("alt_x").run()
        assert not at.exception, at.exception
        preview = next(m.value for m in at.markdown if "Fixations · X" in m.value)
        assert "`30` → `333`" in preview
        at.button(key="remap_preview_census_Lab").click().run()
        assert not at.exception, at.exception
        table = at.dataframe[-1].value
        assert table.iloc[0].tolist() == ["Trials", "1", "1"]
