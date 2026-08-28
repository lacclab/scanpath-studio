"""ENG-37: `api.load_*_metadata` — the headless door onto the three grains.

The app resolves the id column through a picker; a script has only these three
functions, and their whole job is to guess the column and then say clearly what
happened. That guess-and-report path was untested, which matters because both
failure modes are quiet: an unguessable column raises (fine, loud), but a column
guessed *wrongly* still joins — it just means something else.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api


@pytest.fixture(scope="module")
def loaded():
    words, fixations = api.load_sample_data()[:2]
    return words, fixations


class TestParticipantTable:
    def test_the_id_column_is_inferred_and_the_join_reported(self, loaded):
        _words, fixations = loaded
        readers = sorted(fixations["participant_id"].astype(str).unique())
        table = pd.DataFrame({"participant_id": readers, "age": [21, 44]})

        attached = api.load_participant_metadata(table, participants=fixations)

        assert attached.names == ("age",)
        assert set(attached.report.matched) == set(readers)

    def test_an_explicit_column_overrides_the_guess(self, loaded):
        _words, fixations = loaded
        readers = sorted(fixations["participant_id"].astype(str).unique())
        table = pd.DataFrame({"who": readers, "age": [21, 44]})

        attached = api.load_participant_metadata(
            table, id_column="who", participants=fixations
        )

        assert set(attached.report.matched) == set(readers)
        assert "who" not in attached.names

    def test_an_unguessable_column_raises_rather_than_joining_on_nothing(self):
        with pytest.raises(ValueError, match="participant-id column"):
            api.load_participant_metadata(pd.DataFrame({"age": [21]}))

    def test_a_named_column_that_is_not_there_raises(self):
        with pytest.raises(ValueError, match="participant-id column"):
            api.load_participant_metadata(
                pd.DataFrame({"participant_id": ["p1"]}), id_column="nope"
            )


class TestTrialTable:
    def test_keyed_by_trial_alone_by_default(self, loaded):
        _words, fixations = loaded
        trials = sorted(fixations["trial_id"].astype(str).unique())
        table = pd.DataFrame({"trial_id": trials, "position": range(len(trials))})

        attached = api.load_trial_metadata(table, trials=fixations)

        assert not attached.keyed_by_participant
        assert attached.names == ("position",)

    def test_a_reader_column_makes_a_row_one_reading(self, loaded):
        """Never inferred: the table still joins either way, it just means
        something else — a text's property, or one reader's reading of it."""
        _words, fixations = loaded
        pairs = (
            fixations[["participant_id", "trial_id"]]
            .astype(str)
            .drop_duplicates()
            .assign(accuracy=1.0)
        )

        attached = api.load_trial_metadata(
            pairs, participant_column="participant_id", trials=fixations
        )

        assert attached.keyed_by_participant
        assert set(attached.report.matched)

    def test_an_unguessable_column_raises(self):
        with pytest.raises(ValueError, match="trial-id column"):
            api.load_trial_metadata(pd.DataFrame({"position": [1]}))


class TestTextTable:
    def test_the_id_column_is_inferred(self, loaded):
        words, _fixations = loaded
        texts = sorted(words["text_id"].astype(str).unique())
        table = pd.DataFrame({"text_id": texts, "genre": ["news"] * len(texts)})

        attached = api.load_text_metadata(table, texts=words)

        assert attached.names == ("genre",)
        assert set(attached.report.matched) == set(texts)

    def test_an_unguessable_column_raises(self):
        with pytest.raises(ValueError, match="text-id column"):
            api.load_text_metadata(pd.DataFrame({"genre": ["news"]}))


class TestTheyAcceptAPathAsWellAsAFrame:
    """`render --participant-metadata FILE` goes through the same door."""

    def test_a_csv_path_loads(self, tmp_path, loaded):
        _words, fixations = loaded
        readers = sorted(fixations["participant_id"].astype(str).unique())
        path = tmp_path / "readers.csv"
        pd.DataFrame({"participant_id": readers, "age": [21, 44]}).to_csv(
            path, index=False
        )

        attached = api.load_participant_metadata(str(path), participants=fixations)

        assert attached.names == ("age",)

    def test_a_missing_path_raises(self, tmp_path):
        with pytest.raises((ValueError, FileNotFoundError, OSError)):
            api.load_participant_metadata(str(tmp_path / "nope.csv"))
