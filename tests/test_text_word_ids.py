"""Word IDs spelled as text (`w1`, `Hello_3`) are word keys.

A Word ID column with text and not one number is read as keys
(`data.read_word_ids`): the text is kept in `word_key`, each word's numeric
`word_id` is its place in its trial in the Words table's row order, and a
fixation's is the number of the word with exactly its key in the same trial
(`data.match_text_word_ids`). Every numeric consumer then works unchanged, and
a numeric Word ID reads exactly as it always did.
"""

from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import api, cli, measures, plots
from scanpath_studio import data as data_module
from scanpath_studio.column_names import ColumnNames
from scanpath_studio.constants import WORD_KEY
from scanpath_studio.data import (
    harmonize_frames,
    harmonize_frames_reporting,
    normalize_fixations,
    normalize_words,
    read_word_ids,
)

WORD_SCHEMA = {
    "participant": "reader",
    "trial": "trial",
    "word_id": "ia",
    "text": "word",
    "x": "x",
    "y": "y",
    "width": "width",
    "height": "height",
}
FIX_SCHEMA = {
    "participant": "reader",
    "trial": "trial",
    "word_id": "fix_ia",
    "duration": "duration",
}


def _words(ids=("Hello_1", "big_2", "world_3"), *, trial="t1", reader="r1"):
    """One line of boxes 100 px apart, 50 px wide: word n is centred at
    x = 100 (n − 1) + 25."""
    n = len(ids)
    return pd.DataFrame(
        {
            "reader": [reader] * n,
            "trial": [trial] * n,
            "ia": list(ids),
            "word": [str(i).split("_")[0] for i in ids],
            "x": [100.0 * i for i in range(n)],
            "y": [0.0] * n,
            "width": [50.0] * n,
            "height": [20.0] * n,
        }
    )


def _fixations(ids, *, trial="t1", reader="r1", **extra):
    n = len(ids)
    return pd.DataFrame(
        {
            "reader": [reader] * n,
            "trial": [trial] * n,
            "fix_ia": list(ids),
            "duration": [100.0 + 10 * i for i in range(n)],
            **extra,
        }
    )


def _load(words, fixations, *, word_schema=None, fix_schema=None, names="canonical"):
    return api.load_scanpath_data(
        words,
        fixations,
        word_schema=word_schema or WORD_SCHEMA,
        fix_schema=fix_schema or FIX_SCHEMA,
        names=names,
    )


def _quiet_load(*args, **kwargs):
    """`_load`, failing on any warning: a clean text-id pair has none."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return _load(*args, **kwargs)


class TestReadingTheColumn:
    def test_text_with_no_number_is_keys(self):
        number, key = read_word_ids(pd.Series([" w1", "w2 ", None, "", ".", "w3"]))
        assert number.isna().all()
        assert key.tolist()[:2] == ["w1", "w2"]  # stripped
        assert key.isna().tolist() == [False, False, True, True, True, False]

    def test_any_number_makes_it_numbers(self):
        """A column of numbers with a few words in it is a numeric column with
        blanks — what `numeric_parse_issues` reports — never keys."""
        number, key = read_word_ids(pd.Series(["1", "2", "w3"]))
        assert key is None
        assert number.tolist()[:2] == [1.0, 2.0]
        assert np.isnan(number.iloc[2])

    def test_a_numeric_column_is_numbers(self):
        number, key = read_word_ids(pd.Series([3, 1, 2]))
        assert key is None
        assert number.tolist() == [3, 1, 2]

    def test_a_column_of_blanks_is_no_keys(self):
        number, key = read_word_ids(pd.Series([None, " ", "."], dtype=object))
        assert key is None
        assert number.isna().all()

    def test_a_repeated_index_is_read_by_position(self):
        """A concatenated table repeats its row labels."""
        values = pd.Series(["w1", "w2"], index=[0, 0])
        _number, key = read_word_ids(values)
        assert key.tolist() == ["w1", "w2"]


class TestNumberingTheWords:
    def test_each_key_is_numbered_by_its_row_in_the_trial(self):
        raw = pd.concat(
            [
                _words(("b", "a", "c"), trial="t1"),
                _words(("x", "y"), trial="t2"),
            ],
            ignore_index=True,
        )
        words = normalize_words(raw, WORD_SCHEMA)
        # The table's order, not the keys' sort order; restarted per trial.
        assert words["word_id"].tolist() == [1.0, 2.0, 3.0, 1.0, 2.0]
        assert words[WORD_KEY].tolist() == ["b", "a", "c", "x", "y"]

    def test_a_key_listed_twice_is_one_word(self):
        words = normalize_words(_words(("w1", "w2", "w1", "w3")), WORD_SCHEMA)
        assert words["word_id"].tolist() == [1.0, 2.0, 1.0, 3.0]

    def test_a_blank_key_has_no_number(self):
        words = normalize_words(_words(("w1", None, "w2")), WORD_SCHEMA)
        assert words["word_id"].tolist()[0] == 1.0
        assert np.isnan(words["word_id"].iloc[1])
        assert words["word_id"].tolist()[2] == 2.0

    def test_no_text_column_shows_the_key(self):
        schema = {**WORD_SCHEMA, "text": None}
        words = normalize_words(_words(("Hello_1", "world_2")), schema)
        assert words["text"].tolist() == ["Hello_1", "world_2"]

    def test_each_screen_numbers_its_own_words(self):
        raw = pd.concat(
            [
                _words(("w1", "w2")).assign(page="p1"),
                _words(("w1", "w2")).assign(page="p2"),
            ],
            ignore_index=True,
        )
        words = normalize_words(raw, {**WORD_SCHEMA, "screen_id": "page"})
        assert words["word_id"].tolist() == [1.0, 2.0, 1.0, 2.0]


class TestPlacingTheFixations:
    def test_fixations_with_no_xy_land_on_their_words(self):
        words, fixations = _quiet_load(
            _words(), _fixations(["world_3", "Hello_1", "big_2"])
        )
        assert fixations["word_id"].tolist() == [3.0, 1.0, 2.0]
        assert fixations[WORD_KEY].tolist() == ["world_3", "Hello_1", "big_2"]
        assert fixations["x"].tolist() == [225.0, 25.0, 125.0]
        assert fixations["y"].tolist() == [10.0, 10.0, 10.0]
        assert words[WORD_KEY].tolist() == ["Hello_1", "big_2", "world_3"]

    def test_a_key_is_looked_up_in_its_own_trial(self):
        raw_words = pd.concat(
            [_words(("a", "b"), trial="t1"), _words(("b", "a"), trial="t2")],
            ignore_index=True,
        )
        raw_fix = pd.concat(
            [_fixations(["a"], trial="t1"), _fixations(["a"], trial="t2")],
            ignore_index=True,
        )
        _words_out, fixations = _quiet_load(raw_words, raw_fix)
        # 'a' is t1's first word and t2's second.
        assert fixations["word_id"].tolist() == [1.0, 2.0]
        assert fixations["x"].tolist() == [25.0, 125.0]

    def test_a_key_the_trial_does_not_list_is_no_word(self):
        """Never a near spelling, never the first box with no id: pandas
        joins NaN to NaN, so a missing key must stay out of the lookup."""
        with pytest.warns(UserWarning, match=r"2 of 3 Word IDs name no word") as said:
            _words_out, fixations = _load(
                _words(), _fixations(["Hello_1", "hello_1", "nope"])
            )
        assert "'hello_1', 'nope'" in str(said[0].message)
        assert fixations["word_id"].isna().tolist() == [False, True, True]
        assert fixations["x"].isna().tolist() == [False, True, True]

    def test_a_blank_fixation_id_stays_blank(self):
        _words_out, fixations = _quiet_load(_words(), _fixations(["big_2", None]))
        assert fixations["word_id"].isna().tolist() == [False, True]

    def test_stimulus_level_words_are_keyed_per_reader(self):
        """A Words table with no reader is copied onto each reading, keys and
        numbers alike."""
        raw_fix = pd.concat(
            [
                _fixations(["big_2"], reader="r1"),
                _fixations(["world_3"], reader="r2"),
            ],
            ignore_index=True,
        )
        word_schema = {**WORD_SCHEMA, "participant": None}
        _words_out, fixations = _quiet_load(
            _words().drop(columns="reader"), raw_fix, word_schema=word_schema
        )
        assert fixations["word_id"].tolist() == [2.0, 3.0]
        assert fixations["x"].tolist() == [125.0, 225.0]

    def test_keys_restarting_per_screen_find_their_screens_box(self):
        raw_words = pd.concat(
            [
                _words(("w1", "w2")).assign(page="p1"),
                _words(("w1", "w2")).assign(page="p2", y=200.0),
            ],
            ignore_index=True,
        )
        raw_fix = _fixations(["w2", "w1"], page=["p1", "p2"])
        _words_out, fixations = _quiet_load(
            raw_words,
            raw_fix,
            word_schema={**WORD_SCHEMA, "screen_id": "page"},
            fix_schema={**FIX_SCHEMA, "screen_id": "page"},
        )
        assert fixations["x"].tolist() == [125.0, 25.0]
        assert fixations["y"].tolist() == [10.0, 210.0]

    def test_recorded_positions_stand_beside_text_ids(self):
        _words_out, fixations = _quiet_load(
            _words(),
            _fixations(["big_2", "world_3"], fx=[110.0, 230.0], fy=[5.0, 5.0]),
            fix_schema={**FIX_SCHEMA, "x": "fx", "y": "fy"},
        )
        assert fixations["x"].tolist() == [110.0, 230.0]
        assert fixations["word_id"].tolist() == [2.0, 3.0]


class TestTextAgainstNumbers:
    """A text id never names a numbered word, nor a number a text-keyed one:
    either would be a guess."""

    def test_text_fixation_ids_against_numeric_words_are_refused_without_xy(self):
        with pytest.raises(data_module.UnplacedFixationsError, match="are text"):
            _load(_words((1, 2, 3)), _fixations(["w1", "w2"]))

    def test_numeric_fixation_ids_against_text_words_are_refused_without_xy(self):
        with pytest.raises(
            data_module.UnplacedFixationsError, match="Word IDs are numbers"
        ):
            _load(_words(), _fixations([1, 2]))

    def test_with_xy_numeric_ids_are_set_aside_for_the_geometry(self):
        """The numbers are not the words' places, so they are not used; the
        boxes the fixations fall in decide their words."""
        with pytest.warns(UserWarning, match="so they are not used"):
            words, fixations = _load(
                _words(),
                _fixations([3, 1], fx=[125.0, 225.0], fy=[5.0, 5.0]),
                fix_schema={**FIX_SCHEMA, "x": "fx", "y": "fy"},
            )
        assert fixations["word_id"].isna().all()
        assigned = measures.assign_fixations_to_words(fixations, words)
        assert assigned["word_id"].tolist() == [2.0, 3.0]

    def test_with_xy_text_ids_against_numbers_are_not_used(self):
        with pytest.warns(UserWarning, match="text ID never names a numbered word"):
            words, fixations = _load(
                _words((1, 2, 3)),
                _fixations(["w3", "w1"], fx=[225.0, 25.0], fy=[5.0, 5.0]),
                fix_schema={**FIX_SCHEMA, "x": "fx", "y": "fy"},
            )
        assert fixations["word_id"].isna().all()
        assigned = measures.assign_fixations_to_words(fixations, words)
        assert assigned["word_id"].tolist() == [3.0, 1.0]

    def test_no_fixation_naming_a_word_is_refused_without_xy(self):
        with pytest.raises(data_module.UnplacedFixationsError) as raised:
            _load(_words(), _fixations(["a1", "a2"]))
        message = str(raised.value)
        assert message.startswith(
            "Fixations: no fixation's Word ID (e.g. 'a1', 'a2') names a word"
        )
        assert "'Hello_1', 'big_2'" in message
        assert "Map the fixations' X and Y" in message

    def test_text_fixation_ids_with_no_words_table_are_refused(self):
        with pytest.raises(data_module.UnplacedFixationsError, match="no Words"):
            api.load_scanpath_data(
                fixations=_fixations(["w1"]), fix_schema=FIX_SCHEMA, names="canonical"
            )


class TestConsumersLineUp:
    """The numeric consumers read the derived `word_id` unchanged."""

    @pytest.fixture
    def pair(self):
        return _quiet_load(
            _words(("w1", "w2", "w3")),
            _fixations(["w1", "w3", "w2", "w3"]),
        )

    def test_measures_attach_to_the_fixated_words(self, pair):
        words, fixations = pair
        per_word = measures.compute_per_word_measures(fixations, words)
        counts = dict(zip(per_word[WORD_KEY], per_word["n_fixations"]))
        assert counts == {"w1": 1, "w2": 1, "w3": 2}

    def test_the_row_order_is_the_reading_order(self, pair):
        """w3 → w2 is a regression: the numbers order the words as the Words
        table lists them."""
        words, fixations = pair
        enriched = measures.enrich_fixations(fixations, words)
        assert enriched["is_regression"].tolist() == [False, False, True, False]

    def test_heatmap_keys_join_the_word_boxes(self, pair):
        words, fixations = pair
        values, *_ = plots._comparison_word_heatmap_data(
            [{"trial_fix": fixations}],
            metric="count",
            heatmap_range=None,
            heatmap_norm="Linear",
        )
        box_keys = set(plots._word_id_keys(words["word_id"]))
        assert set(values[0]) <= box_keys
        assert values[0] == {"1": 1.0, "2": 1.0, "3": 2.0}

    def test_the_fixation_hover_names_the_word_by_its_own_id(self, pair):
        words, fixations = pair
        head = plots._fixation_hover_head(
            fixations, ["order_in_trial", "word_id"], words
        )
        assert head.iloc[1] == "Fixation 2 · on “w3” (w3)"

    def test_redacted_text_takes_the_text_ids_with_it(self, pair):
        """`Hello_3` spells its word, so a figure that masks the words does
        not name them by it either."""
        words, fixations = pair
        redacted = plots.redact_word_text(words)
        assert WORD_KEY not in redacted.columns
        head = plots._fixation_hover_head(fixations, ["word_id"], redacted)
        assert "w3" not in head.iloc[1] and "word 3" in head.iloc[1]

    def test_the_word_hover_shows_the_text_id(self, pair):
        words, _fixations_out = pair
        customdata, template = plots._hover_payload(
            words, ["text", "word_id"], table="words"
        )
        assert "Word ID: %{customdata[1]}" in template
        assert customdata[:, 1].tolist() == ["w1", "w2", "w3"]


class TestWhatTheUserSees:
    def test_the_text_ids_keep_the_files_column_name(self):
        words, fixations = _quiet_load(_words(), _fixations(["big_2"]), names="source")
        assert words["ia"].tolist() == ["Hello_1", "big_2", "world_3"]
        assert fixations["fix_ia"].tolist() == ["big_2"]
        # The numbers are the app's, under their own name.
        assert words["word_id"].tolist() == [1.0, 2.0, 3.0]
        assert fixations["word_id"].tolist() == [2.0]

    def test_the_column_map_says_which_is_which(self):
        data = _quiet_load(_words(), _fixations(["big_2"]))
        words_map = data.column_names["words"]
        assert words_map.label(WORD_KEY) == "ia"
        assert words_map.field_label(WORD_KEY) == "Word ID"
        assert words_map.to_canonical("ia") == WORD_KEY
        assert words_map.kind_of("word_id") == "generated"
        assert words_map.label("word_id") == "Word # (computed)"
        assert words_map.export_headers([WORD_KEY, "word_id"]) == {WORD_KEY: "ia"}
        assert data.column_names["fixations"].label(WORD_KEY) == "fix_ia"

    def test_a_text_id_column_is_not_reported_as_unreadable_numbers(self):
        raw = _fixations(["w1", "w2"])
        assert data_module.numeric_parse_issues(raw, FIX_SCHEMA, table="F") == []
        assert data_module.wrong_column_note(raw, "fix_ia", "word_id") == ""

    def test_a_mostly_text_column_with_a_number_still_says_so(self):
        raw = _fixations(["w1", "w2", "3"])
        issues = data_module.numeric_parse_issues(raw, FIX_SCHEMA, table="F")
        assert issues and "read as text only when none of its values" in issues[0]


class TestLoadingItAgain:
    def test_the_apps_own_tables_load_again_with_their_keys(self):
        """`word_key` is proposed first, so a table the app wrote keeps its
        ids and numbers."""
        words, fixations = _quiet_load(_words(), _fixations(["world_3", "big_2"]))
        again = api.load_scanpath_data(words, fixations, names="canonical")
        assert again.words[WORD_KEY].tolist() == words[WORD_KEY].tolist()
        assert again.words["word_id"].tolist() == words["word_id"].tolist()
        assert again.fixations["word_id"].tolist() == [3.0, 2.0]

    def test_an_edit_remaps_the_stored_keys(self):
        """✏️ Edit dataset seeds the Word ID with the stored keys
        (`tabs._remap_proposed`), re-numbers the words and matches the
        fixations again — the same numbers, the same keys."""
        from scanpath_studio.tabs import (
            _FIX_REMAP_CANON,
            _WORD_REMAP_CANON,
            _remap_proposed,
        )

        words, fixations = _quiet_load(_words(), _fixations(["world_3", "big_2"]))
        word_schema = _remap_proposed(WORD_SCHEMA, words.columns, _WORD_REMAP_CANON)
        fix_schema = _remap_proposed(FIX_SCHEMA, fixations.columns, _FIX_REMAP_CANON)
        assert word_schema["word_id"] == fix_schema["word_id"] == WORD_KEY
        remapped_words = data_module.remap_normalized_frame(
            words, word_schema, kind="words"
        )
        remapped_fix = data_module.remap_normalized_frame(
            fixations, fix_schema, kind="fixations"
        )
        words_again, fixations_again = harmonize_frames(remapped_words, remapped_fix)
        assert words_again["word_id"].tolist() == words["word_id"].tolist()
        assert fixations_again["word_id"].tolist() == [3.0, 2.0]
        assert fixations_again[WORD_KEY].tolist() == ["world_3", "big_2"]

    def test_an_edit_to_numeric_ids_drops_the_stored_keys(self):
        """A `word_key` left over from the old mapping would match fixations
        by ids the new one no longer names."""
        words, _fixations_out = _quiet_load(_words(), _fixations(["big_2"]))
        stored = words.assign(numbers=[10, 20, 30])
        schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            "word_id": "numbers",
            "text": "text",
            "x": "x",
            "y": "y",
            "width": "width",
            "height": "height",
        }
        remapped = data_module.remap_normalized_frame(stored, schema, kind="words")
        assert WORD_KEY not in remapped.columns
        assert remapped["word_id"].tolist() == [10, 20, 30]


class TestNumericIdsAreUnchanged:
    def test_numeric_ids_carry_no_key_and_read_as_numbers(self):
        words, fixations = _quiet_load(_words((5, 7, 9)), _fixations([9, 5]))
        assert WORD_KEY not in words.columns
        assert WORD_KEY not in fixations.columns
        assert words["word_id"].tolist() == [5, 7, 9]
        assert fixations["word_id"].tolist() == [9, 5]
        assert fixations["x"].tolist() == [225.0, 25.0]

    def test_the_demo_loads_without_keys_or_new_rewrites(self):
        raw_words, raw_fix = data_module.load_sample_data()
        words, fixations, _join, rewrites = harmonize_frames_reporting(
            normalize_words(raw_words, data_module.propose_word_schema(raw_words)),
            normalize_fixations(raw_fix, data_module.propose_fix_schema(raw_fix)),
        )
        assert WORD_KEY not in words.columns and WORD_KEY not in fixations.columns
        assert rewrites == (("fixations", "word_id", " − 1"),)

    def test_the_numeric_map_has_no_key_entry(self):
        data = _quiet_load(_words((1, 2, 3)), _fixations([2]))
        assert WORD_KEY not in data.column_names["words"].entries
        assert data.column_names["words"].label("word_id") == "ia"

    def test_a_map_without_a_word_id_source_ignores_the_key_rewrite(self):
        names = ColumnNames().with_rewrites("words", [("words", WORD_KEY, ", x")])
        assert names.entries == {}


class TestTheCommandLine:
    """`render` loads through `api.load_scanpath_data`, so it reads text ids
    the same way."""

    @staticmethod
    def _files(tmp_path, words, fixations):
        words_csv, fix_csv = tmp_path / "words.csv", tmp_path / "fixations.csv"
        words.to_csv(words_csv, index=False)
        fixations.to_csv(fix_csv, index=False)
        return [
            "render",
            "--words",
            str(words_csv),
            "--fixations",
            str(fix_csv),
            "--word-schema",
            json.dumps(WORD_SCHEMA),
            "--fix-schema",
            json.dumps(FIX_SCHEMA),
        ]

    def test_render_draws_text_keyed_fixations(self, tmp_path):
        args = self._files(tmp_path, _words(), _fixations(["big_2", "world_3"]))
        out = tmp_path / "out.html"
        cli.main([*args, "-o", str(out)])
        assert out.exists() and out.stat().st_size > 0

    def test_render_refuses_text_ids_that_name_no_word(self, tmp_path):
        args = self._files(tmp_path, _words((1, 2, 3)), _fixations(["w1"]))
        with pytest.raises(SystemExit) as raised:
            cli.main([*args, "-o", str(tmp_path / "out.html")])
        said = str(raised.value)
        assert "the Word IDs are text (e.g. 'w1')" in said
        assert "--fix-schema" in said
