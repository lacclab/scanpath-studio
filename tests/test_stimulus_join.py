"""DATA-49 — one join for a stimulus-level AOI table, whatever the trial ids.

An AOI table with no Participant ID holds one set of word boxes per *text*,
shared by every reading of it. Each reading — ``(participant_id, trial_id[,
screen_id])`` of the fixations — takes the boxes of its text through the key it
shares with the AOI table: its own trial id when the AOI table is keyed by the
readings' ids, else its Text ID (trial ids that embed the reader, a repeated
reading's ``_r2``). When neither reaches one reading the load refuses rather
than add a dataset with no AOIs.
"""

from __future__ import annotations

import pandas as pd
import pytest

import scanpath_studio as sps
from scanpath_studio import data as data_module
from scanpath_studio.data import (
    StimulusJoinError,
    normalize_fixations,
    normalize_words,
    plan_stimulus_join,
)
from scanpath_studio.utils import extract_trial


def _text_words() -> pd.DataFrame:
    """A text-level AOI table keyed by ``unique_paragraph_id`` — the DATA-49
    repro's shape: no reader, no per-reader trial id."""
    return pd.DataFrame(
        {
            "unique_paragraph_id": ["1_1_Ele"] * 2 + ["1_2_Adv"],
            "IA_ID": [1, 2, 1],
            "IA_LABEL": ["Hello", "world", "Bye"],
            "IA_LEFT": [100, 200, 100],
            "IA_RIGHT": [180, 280, 160],
            "IA_TOP": [50, 50, 50],
            "IA_BOTTOM": [100, 100, 100],
        }
    )


def _reader_fixations() -> pd.DataFrame:
    """Fixations whose trial id embeds the reader (`l37_…_r0`)."""
    rows = []
    for reader in ("l37", "l42"):
        for text in ("1_1_Ele", "1_2_Adv"):
            for x in (140.0, 240.0):
                rows.append(
                    {
                        "participant_id": reader,
                        "unique_trial_id": f"{reader}_1129_{text}_r0",
                        "unique_paragraph_id": text,
                        "CURRENT_FIX_X": x,
                        "CURRENT_FIX_Y": 75.0,
                        "CURRENT_FIX_DURATION": 200,
                    }
                )
    return pd.DataFrame(rows)


class TestReaderEmbeddedTrialIds:
    def test_every_reading_gets_the_boxes_of_its_text(self):
        words, fixations = sps.load_scanpath_data(
            words=_text_words(), fixations=_reader_fixations()
        )
        assert len(set(zip(fixations["participant_id"], fixations["trial_id"]))) == 4
        for reader in ("l37", "l42"):
            ele = extract_trial(words, reader, f"{reader}_1129_1_1_Ele_r0")
            adv = extract_trial(words, reader, f"{reader}_1129_1_2_Adv_r0")
            assert ele["text"].tolist() == ["Hello", "world"]
            assert adv["text"].tolist() == ["Bye"]
        # The boxes carry the reading's own ids, the AOI table's text id.
        assert set(words["trial_id"]) == set(fixations["trial_id"])
        assert set(words["text_id"]) == {"1_1_Ele", "1_2_Adv"}
        assert data_module.STIMULUS_WORDS_FLAG not in words.columns

    def test_the_plan_names_the_text_id(self):
        words = normalize_words(
            _text_words(), data_module.propose_word_schema(_text_words())
        )
        fixations = normalize_fixations(
            _reader_fixations(), data_module.propose_fix_schema(_reader_fixations())
        )
        join = plan_stimulus_join(words, fixations)
        assert join is not None
        assert (join.key, join.readings, join.matched) == ("text_id", 4, 4)
        assert join.describe().startswith("Words attach to readings by Text ID")

    def test_a_mapped_text_column_of_any_name_joins(self):
        """Nothing about `unique_paragraph_id` is special: a Text ID mapped to
        an arbitrary column in both tables is the same join."""
        words_raw = pd.DataFrame(
            {
                "item": ["a", "a", "b"],
                "wid": [0, 1, 0],
                "L": [0.0, 50.0, 0.0],
                "R": [40.0, 90.0, 60.0],
                "T": [0.0, 0.0, 0.0],
                "B": [20.0, 20.0, 20.0],
            }
        )
        fix_raw = pd.DataFrame(
            {
                "subj": ["p1", "p1", "p2"],
                "trial": ["p1-a", "p1-b", "p2-a"],
                "item": ["a", "b", "a"],
                "fx": [10.0, 10.0, 60.0],
                "fy": [5.0, 5.0, 5.0],
                "dur": [100, 120, 90],
            }
        )
        words, _ = sps.load_scanpath_data(
            words=words_raw,
            fixations=fix_raw,
            word_schema={
                "trial": "item",
                "text_id": "item",
                "word_id": "wid",
                "left": "L",
                "right": "R",
                "top": "T",
                "bottom": "B",
            },
            fix_schema={
                "participant": "subj",
                "trial": "trial",
                "text_id": "item",
                "x": "fx",
                "y": "fy",
                "duration": "dur",
            },
        )
        assert len(extract_trial(words, "p1", "p1-a")) == 2
        assert len(extract_trial(words, "p1", "p1-b")) == 1
        assert len(extract_trial(words, "p2", "p2-a")) == 2


class TestSharedAndRepeatedIds:
    def _words(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "text_id": ["t1", "t1", "t2"],
                "word_id": [1, 2, 1],
                "word": ["Hello", "world", "Bye"],
                "left": [100, 200, 100],
                "right": [180, 280, 160],
                "top": [50, 50, 50],
                "bottom": [100, 100, 100],
            }
        )

    def test_ids_shared_across_readers_join_by_trial_id(self):
        fixations = pd.DataFrame(
            {
                "reader_id": [7, 7, 8],
                "text_id": ["t1", "t2", "t1"],
                "x": [140.0, 130.0, 240.0],
                "y": [75.0] * 3,
                "fixation_duration": [180, 220, 150],
            }
        )
        words_norm = normalize_words(
            self._words(), data_module.propose_word_schema(self._words())
        )
        fix_norm = normalize_fixations(
            fixations, data_module.propose_fix_schema(fixations)
        )
        join = plan_stimulus_join(words_norm, fix_norm)
        assert join.key == "trial_id"
        assert join.matched == join.readings == 3
        words, _ = sps.load_scanpath_data(words=self._words(), fixations=fixations)
        for reader in ("7", "8"):
            assert extract_trial(words, reader, "t1")["text"].tolist() == [
                "Hello",
                "world",
            ]

    def test_a_repeated_reading_joins_by_the_id_it_was_recorded_under(self):
        """BUG-57 falls out of the general join: `_disambiguate_repeated_readings`
        records the id it suffixed (`base_trial_id`), so the `_r2` reading finds
        its boxes by trial id, and its fallback Text ID is the unsuffixed id."""
        fixations = pd.DataFrame(
            {
                "reader_id": [7, 7, 7, 7],
                "paragraph": ["t1", "t1", "t1", "t1"],
                "TRIAL_INDEX": [1, 1, 3, 3],
                "fixation_duration": [180, 220, 150, 200],
                "x": [140.0, 240.0, 140.0, 240.0],
                "y": [75.0] * 4,
            }
        )
        fix_schema = {
            "participant": "reader_id",
            "trial": "paragraph",
            "x": "x",
            "y": "y",
            "duration": "fixation_duration",
        }
        fix_norm = normalize_fixations(fixations, fix_schema)
        # No Text ID mapped: it falls back to the *unsuffixed* trial id.
        assert set(fix_norm["trial_id"]) == {"t1", "t1_r2"}
        assert set(fix_norm["text_id"]) == {"t1"}
        words_norm = normalize_words(
            self._words(), data_module.propose_word_schema(self._words())
        )
        assert set(fix_norm[data_module.BASE_TRIAL_ID]) == {"t1"}
        join = plan_stimulus_join(words_norm, fix_norm)
        assert (join.key, join.matched, join.readings) == ("trial_id", 2, 2)
        words, _ = sps.load_scanpath_data(
            words=self._words(), fixations=fixations, fix_schema=fix_schema
        )
        for trial in ("t1", "t1_r2"):
            assert extract_trial(words, "7", trial)["text"].tolist() == [
                "Hello",
                "world",
            ]

    def test_per_reader_word_tables_are_not_broadcast(self):
        words = self._words().assign(reader_id=7)
        fixations = pd.DataFrame(
            {
                "reader_id": [7],
                "text_id": ["t1"],
                "x": [140.0],
                "y": [75.0],
                "fixation_duration": [180],
            }
        )
        w = normalize_words(words, data_module.propose_word_schema(words))
        f = normalize_fixations(fixations, data_module.propose_fix_schema(fixations))
        assert plan_stimulus_join(w, f) is None


class TestNoJoinRefuses:
    def test_no_shared_trial_or_text_raises(self):
        fixations = _reader_fixations().assign(unique_paragraph_id="other")
        with pytest.raises(StimulusJoinError, match="Text ID"):
            sps.load_scanpath_data(words=_text_words(), fixations=fixations)

    def test_the_error_is_a_value_error_for_api_callers(self):
        assert issubclass(StimulusJoinError, ValueError)

    def test_an_ambiguous_text_id_is_not_used(self):
        """An article-level Text ID over paragraph-level boxes names several
        of the AOI table's trials; joining on it would hand a reading every
        paragraph of the article. The trial id is used instead when it joins,
        and the refusal says why when it does not."""
        words = pd.DataFrame(
            {
                "trial": ["art1_p1", "art1_p2"],
                "article": ["art1", "art1"],
                "wid": [0, 0],
                "L": [0.0, 0.0],
                "R": [40.0, 40.0],
                "T": [0.0, 0.0],
                "B": [20.0, 20.0],
            }
        )
        word_schema = {
            "trial": "trial",
            "text_id": "article",
            "word_id": "wid",
            "left": "L",
            "right": "R",
            "top": "T",
            "bottom": "B",
        }
        fix_schema = {
            "participant": "subj",
            "trial": "trial",
            "text_id": "article",
            "x": "fx",
            "y": "fy",
            "duration": "dur",
        }
        shared = pd.DataFrame(
            {
                "subj": ["p1", "p2"],
                "trial": ["art1_p1", "art1_p2"],
                "article": ["art1", "art1"],
                "fx": [10.0, 10.0],
                "fy": [5.0, 5.0],
                "dur": [100, 100],
            }
        )
        w, _ = sps.load_scanpath_data(
            words=words,
            fixations=shared,
            word_schema=word_schema,
            fix_schema=fix_schema,
        )
        assert len(extract_trial(w, "p1", "art1_p1")) == 1
        assert len(extract_trial(w, "p2", "art1_p2")) == 1
        per_reader = shared.assign(trial=["p1_art1_p1", "p2_art1_p2"])
        with pytest.raises(StimulusJoinError, match="'art1'"):
            sps.load_scanpath_data(
                words=words,
                fixations=per_reader,
                word_schema=word_schema,
                fix_schema=fix_schema,
            )

    def test_a_partial_join_keeps_the_readings_it_reaches(self):
        fixations = _reader_fixations()
        fixations.loc[fixations["participant_id"] == "l42", "unique_paragraph_id"] = (
            "unknown"
        )
        w = normalize_words(
            _text_words(), data_module.propose_word_schema(_text_words())
        )
        f = normalize_fixations(fixations, data_module.propose_fix_schema(fixations))
        join = plan_stimulus_join(w, f)
        assert (join.key, join.readings, join.matched) == ("text_id", 4, 2)
        assert "2 of 4 readings" in join.describe()

    def test_the_cli_prints_the_refusal(self, tmp_path, capsys):
        from scanpath_studio import cli

        words_path = tmp_path / "words.csv"
        fix_path = tmp_path / "fix.csv"
        _text_words().to_csv(words_path, index=False)
        _reader_fixations().assign(unique_paragraph_id="other").to_csv(
            fix_path, index=False
        )
        with pytest.raises(SystemExit) as excinfo:
            cli.main(
                [
                    "render",
                    "--words",
                    str(words_path),
                    "--fixations",
                    str(fix_path),
                    "--list-trials",
                ]
            )
        assert "Text ID" in str(excinfo.value)


class TestMultipart:
    def test_screens_join_by_text_and_screen(self):
        """A multipart AOI table keys each screen's boxes by (text, screen);
        a reading takes the boxes of its own screen of its own text."""
        words = pd.DataFrame(
            {
                "text": ["A", "A", "A"],
                "page": ["p1", "p1", "p2"],
                "wid": [0, 1, 0],
                "label": ["one", "two", "three"],
                "L": [0.0, 50.0, 0.0],
                "R": [40.0, 90.0, 40.0],
                "T": [0.0, 0.0, 0.0],
                "B": [20.0, 20.0, 20.0],
            }
        )
        fixations = pd.DataFrame(
            {
                "subj": ["r1", "r1", "r2"],
                "trial": ["r1_A", "r1_A", "r2_A"],
                "text": ["A", "A", "A"],
                "page": ["p1", "p2", "p2"],
                "fx": [10.0, 10.0, 10.0],
                "fy": [5.0, 5.0, 5.0],
                "dur": [100, 100, 100],
            }
        )
        words_norm, _ = sps.load_scanpath_data(
            words=words,
            fixations=fixations,
            word_schema={
                "trial": "text",
                "text_id": "text",
                "screen_id": "page",
                "word_id": "wid",
                "text": "label",
                "left": "L",
                "right": "R",
                "top": "T",
                "bottom": "B",
            },
            fix_schema={
                "participant": "subj",
                "trial": "trial",
                "text_id": "text",
                "screen_id": "page",
                "x": "fx",
                "y": "fy",
                "duration": "dur",
            },
        )
        r1 = words_norm[words_norm["participant_id"] == "r1"]
        assert sorted(r1["text"]) == ["one", "three", "two"]
        r2 = words_norm[words_norm["participant_id"] == "r2"]
        # r2 read only page 2, so only page 2's boxes are theirs.
        assert r2["text"].tolist() == ["three"]
        assert set(r2["trial_id"]) == {"r2_A"}


def test_the_join_is_one_merge_at_corpus_scale():
    """The join runs on ~1M-row corpora: planned over distinct keys and done
    as one merge. 100k fixations over 2,000 readings take a fraction of a
    second; the 5 s bound only catches a per-reading Python loop coming back
    (tens of seconds here) without flaking on a slow CI runner."""
    import time

    n_texts, n_readers, n_words = 40, 50, 100
    words = pd.DataFrame(
        {
            "participant_id": data_module.STIMULUS_PARTICIPANT,
            data_module.STIMULUS_WORDS_FLAG: True,
            "trial_id": [f"t{t}" for t in range(n_texts) for _ in range(n_words)],
            "text_id": [f"t{t}" for t in range(n_texts) for _ in range(n_words)],
            "word_id": [w for _ in range(n_texts) for w in range(n_words)],
            "x": 0.0,
        }
    )
    readings = [(f"r{r}", f"t{t}") for r in range(n_readers) for t in range(n_texts)]
    fixations = pd.DataFrame(
        {
            "participant_id": [r for r, _ in readings for _ in range(50)],
            "trial_id": [f"{r}_{t}" for r, t in readings for _ in range(50)],
            "text_id": [t for _, t in readings for _ in range(50)],
        }
    )
    start = time.perf_counter()
    out = data_module.broadcast_stimulus_words(words, fixations)
    elapsed = time.perf_counter() - start
    assert len(out) == n_texts * n_readers * n_words
    assert elapsed < 5.0, elapsed


def _boxes(words: pd.DataFrame, reader: str, trial: str) -> list:
    return extract_trial(words, reader, trial)["text"].tolist()


_EDGE_SCHEMA = {
    "word_id": "wid",
    "text": "label",
    "left": "L",
    "right": "R",
    "top": "T",
    "bottom": "B",
}
_FIX_SCHEMA = {
    "participant": "subj",
    "trial": "trial",
    "x": "fx",
    "y": "fy",
    "duration": "dur",
}


def _aoi(trials, texts, labels) -> pd.DataFrame:
    """One box per AOI-table trial."""
    n = len(trials)
    return pd.DataFrame(
        {
            "trial": trials,
            "text": texts,
            "wid": [0] * n,
            "label": labels,
            "L": [0.0] * n,
            "R": [40.0] * n,
            "T": [0.0] * n,
            "B": [20.0] * n,
        }
    )


def _fix(subjects, trials, texts, **extra) -> pd.DataFrame:
    n = len(subjects)
    return pd.DataFrame(
        {
            "subj": subjects,
            "trial": trials,
            "text": texts,
            "fx": [10.0] * n,
            "fy": [5.0] * n,
            "dur": [100] * n,
            **extra,
        }
    )


class TestPerReadingRule:
    """DATA-49 review: the key is chosen per reading — its exact trial id, then
    the id it had before a repeat's `_r2`, then its unambiguous Text ID."""

    def test_each_reading_uses_its_own_route(self):
        """One reading matches only by trial id, the others only by Text ID; a
        dataset-wide key would have left the first without boxes."""
        words = _aoi(["A", "B", "C"], ["tA", "tB", "tC"], ["a", "b", "c"])
        fixations = _fix(
            ["p1", "p1", "p2", "p3"], ["A", "q1", "q2", "q3"], ["xx", "tB", "tB", "tC"]
        )
        w, _ = sps.load_scanpath_data(
            words=words,
            fixations=fixations,
            word_schema={**_EDGE_SCHEMA, "trial": "trial", "text_id": "text"},
            fix_schema={**_FIX_SCHEMA, "text_id": "text"},
        )
        assert _boxes(w, "p1", "A") == ["a"]
        assert _boxes(w, "p1", "q1") == ["b"]
        assert _boxes(w, "p2", "q2") == ["b"]
        assert _boxes(w, "p3", "q3") == ["c"]

    def test_the_mixed_route_is_described(self):
        words = normalize_words(
            _aoi(["A", "B"], ["tA", "tB"], ["a", "b"]),
            {**_EDGE_SCHEMA, "trial": "trial", "text_id": "text"},
        )
        fixations = normalize_fixations(
            _fix(["p1", "p2"], ["A", "q2"], ["tA", "tB"]),
            {**_FIX_SCHEMA, "text_id": "text"},
        )
        join = plan_stimulus_join(words, fixations)
        assert (join.key, join.by_trial, join.by_text) == ("mixed", 1, 1)
        assert "trial ID (1) and by Text ID (1)" in join.describe()
        assert "all 2 readings have word boxes" in join.describe()

    def test_a_repeat_keeps_its_boxes_under_a_coarser_text_id(self):
        """Trial = paragraph, Text ID = article (two paragraphs per article):
        the article is ambiguous, and the `_r2` repeat of a paragraph must
        still find its paragraph's boxes (the old BUG-57 suffix fallback did)."""
        words = _aoi(["a1p1", "a1p2"], ["a1", "a1"], ["first", "second"])
        fixations = _fix(
            ["r1", "r1", "r1"],
            ["a1p1", "a1p2", "a1p1"],
            ["a1", "a1", "a1"],
            TRIAL_INDEX=[1, 2, 3],
        )
        w, f = sps.load_scanpath_data(
            words=words,
            fixations=fixations,
            word_schema={**_EDGE_SCHEMA, "trial": "trial", "text_id": "text"},
            fix_schema={**_FIX_SCHEMA, "text_id": "text"},
        )
        assert set(f["trial_id"]) == {"a1p1", "a1p2", "a1p1_r2"}
        assert _boxes(w, "r1", "a1p1") == ["first"]
        assert _boxes(w, "r1", "a1p1_r2") == ["first"]
        assert _boxes(w, "r1", "a1p2") == ["second"]
        # The bookkeeping column stays on the fixations, never on the words.
        assert data_module.BASE_TRIAL_ID not in w.columns

    def test_only_the_ambiguous_texts_are_left_out(self):
        """One text id over two AOI trials disables that text, not the Text ID
        join for every text; the warning names it."""
        words = _aoi(["T1", "T2", "T3"], ["X", "X", "Y"], ["x1", "x2", "y"])
        fixations = _fix(["r1", "r2"], ["r1_Y", "r2_X"], ["Y", "X"])
        with pytest.warns(UserWarning, match="'X'"):
            w, _ = sps.load_scanpath_data(
                words=words,
                fixations=fixations,
                word_schema={**_EDGE_SCHEMA, "trial": "trial", "text_id": "text"},
                fix_schema={**_FIX_SCHEMA, "text_id": "text"},
            )
        assert _boxes(w, "r1", "r1_Y") == ["y"]
        assert _boxes(w, "r2", "r2_X") == []


class TestZeroPadding:
    """BUG-59's zero-padding reconciliation runs before the join, and the join
    the wizard reports is the one that ran (DATA-49 review)."""

    def test_the_reported_join_is_the_one_made_after_padding(self):
        words = normalize_words(
            _aoi(["7"], ["7"], ["seven"]), {**_EDGE_SCHEMA, "trial": "trial"}
        )
        fixations = normalize_fixations(_fix(["p1"], ["007"], ["007"]), _FIX_SCHEMA)
        w, _f, join = data_module.harmonize_frames_with_join(words, fixations)
        assert join is not None and join.matched == join.readings == 1
        assert _boxes(w, "p1", "007") == ["seven"]

    def test_the_wizards_cached_normalization_reports_it_too(self):
        from scanpath_studio import app

        words = _aoi(["7"], ["7"], ["seven"])
        fixations = _fix(["p1"], ["007"], ["007"])
        w, _f, join = app._normalize_pair_uncached(
            words,
            {**_EDGE_SCHEMA, "trial": "trial"},
            fixations,
            _FIX_SCHEMA,
            ("zero-padding", 1),
        )
        assert join.matched == join.readings == 1
        assert _boxes(w, "p1", "007") == ["seven"]

    def test_a_zero_padded_text_id_is_reconciled(self):
        words = _aoi(["stim"], ["7"], ["seven"])
        fixations = _fix(["p1"], ["p1_stim"], ["007"])
        w, _ = sps.load_scanpath_data(
            words=words,
            fixations=fixations,
            word_schema={**_EDGE_SCHEMA, "trial": "trial", "text_id": "text"},
            fix_schema={**_FIX_SCHEMA, "text_id": "text"},
        )
        assert _boxes(w, "p1", "p1_stim") == ["seven"]


class TestHeadlessSurfaces:
    def test_a_partial_join_warns_api_callers(self):
        fixations = _reader_fixations()
        fixations.loc[fixations["participant_id"] == "l42", "unique_paragraph_id"] = (
            "unknown"
        )
        with pytest.warns(UserWarning, match="2 of 4 readings have word boxes"):
            sps.load_scanpath_data(words=_text_words(), fixations=fixations)

    def _run_cli(self, tmp_path, fixations):
        import subprocess
        import sys

        words_path = tmp_path / "words.csv"
        fix_path = tmp_path / "fix.csv"
        _text_words().to_csv(words_path, index=False)
        fixations.to_csv(fix_path, index=False)
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "scanpath_studio",
                "render",
                "--words",
                str(words_path),
                "--fixations",
                str(fix_path),
                "--list-trials",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

    def test_the_cli_prints_a_partial_join(self, tmp_path):
        fixations = _reader_fixations()
        fixations.loc[fixations["participant_id"] == "l42", "unique_paragraph_id"] = (
            "unknown"
        )
        result = self._run_cli(tmp_path, fixations)
        assert result.returncode == 0, result.stderr
        assert "2 of 4 readings have word boxes" in result.stderr

    def test_the_cli_refusal_names_the_schema_flags(self, tmp_path):
        result = self._run_cli(
            tmp_path, _reader_fixations().assign(unique_paragraph_id="other")
        )
        assert result.returncode != 0
        assert "Text ID" in result.stderr
        assert "--word-schema" in result.stderr and "--fix-schema" in result.stderr
