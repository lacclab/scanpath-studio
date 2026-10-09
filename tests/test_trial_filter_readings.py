"""#412 — a trial filter decides each *reading*, from the table that has its field.

A condition such as ``difficulty_level`` may be on the Words table only, the
Fixations table only, or both. `data.filter_trials` used to filter each table
by its own column, so with the field on Words alone, choosing **Adv** dropped
the Ele word rows and kept the Ele fixations — and the trial pool, built from
every table, kept offering the Ele reading. Each condition is now resolved to
``(participant_id, trial_id)`` readings once, and that answer narrows every
table; readings the two tables disagree on are left out and reported.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api
from scanpath_studio.data import (
    TEXT_ID_MAPPED,
    filter_trials,
    raw_gaze_in_pool,
    select_trials,
    trial_filter_conflict_note,
)
from tests.conftest import APP_SCRIPT


def _readings(frame: pd.DataFrame) -> list[tuple[str, str]]:
    return sorted(set(zip(frame["participant_id"], frame["trial_id"])))


def _words(**extra) -> pd.DataFrame:
    """Two readings, two words each: Adv read by p_adv, Ele by p_ele."""
    return pd.DataFrame(
        {
            "participant_id": ["p_adv", "p_adv", "p_ele", "p_ele"],
            "trial_id": ["adv", "adv", "ele", "ele"],
            "word_id": [0, 1, 0, 1],
            **extra,
        }
    )


def _fixations(**extra) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p_adv", "p_adv", "p_ele", "p_ele"],
            "trial_id": ["adv", "adv", "ele", "ele"],
            "duration_ms": [100, 100, 300, 300],
            **extra,
        }
    )


LEVELS = ["Adv", "Adv", "Ele", "Ele"]


class TestTheFieldNarrowsEveryTable:
    def test_a_field_on_the_words_table_only(self):
        """The review's repro: Ele's fixations used to survive."""
        w, f = filter_trials(
            _words(difficulty_level=LEVELS),
            _fixations(),
            metadata={"difficulty_level": {"Adv"}},
        )
        assert _readings(w) == [("p_adv", "adv")]
        assert _readings(f) == [("p_adv", "adv")]

    def test_a_field_on_the_fixations_table_only(self):
        w, f = filter_trials(
            _words(),
            _fixations(difficulty_level=LEVELS),
            metadata={"difficulty_level": {"Ele"}},
        )
        assert _readings(w) == [("p_ele", "ele")]
        assert _readings(f) == [("p_ele", "ele")]

    def test_a_numeric_range_on_one_table(self):
        w, f = filter_trials(
            _words(score=[0.2, 0.2, 0.9, 0.9]),
            _fixations(),
            ranges={"score": (0.0, 0.5)},
        )
        assert _readings(w) == _readings(f) == [("p_adv", "adv")]

    def test_trial_ids_reused_across_participants(self):
        """Two readers' trial ``t``: the reading is the pair, not the trial id."""
        words = pd.DataFrame(
            {
                "participant_id": ["p1", "p2"],
                "trial_id": ["t", "t"],
                "difficulty_level": ["Adv", "Ele"],
            }
        )
        fixations = pd.DataFrame(
            {"participant_id": ["p1", "p1", "p2"], "trial_id": ["t", "t", "t"]}
        )
        w, f = filter_trials(words, fixations, metadata={"difficulty_level": {"Adv"}})
        assert _readings(w) == _readings(f) == [("p1", "t")]
        assert len(f) == 2

    def test_a_reading_only_the_other_table_has_is_unknown(self):
        """A category never matches a missing value; a range keeps one."""
        words = _words(difficulty_level=LEVELS, score=[0.2, 0.2, 0.9, 0.9])
        fixations = pd.concat(
            [
                _fixations(),
                pd.DataFrame(
                    {
                        "participant_id": ["p_x"],
                        "trial_id": ["fix_only"],
                        "duration_ms": [50],
                    }
                ),
            ],
            ignore_index=True,
        )
        _, f = filter_trials(words, fixations, metadata={"difficulty_level": {"Adv"}})
        assert _readings(f) == [("p_adv", "adv")]
        _, f = filter_trials(words, fixations, ranges={"score": (0.0, 0.5)})
        assert _readings(f) == [("p_adv", "adv"), ("p_x", "fix_only")]
        _, f = filter_trials(
            words, fixations, ranges={"score": (0.0, 0.5)}, drop_unknown=["score"]
        )
        assert _readings(f) == [("p_adv", "adv")]

    def test_nothing_dropped_hands_back_the_frames_themselves(self):
        words, fixations = _words(difficulty_level=LEVELS), _fixations()
        w, f = filter_trials(
            words, fixations, metadata={"difficulty_level": {"Adv", "Ele"}}
        )
        assert w is words and f is fixations

    def test_a_column_neither_table_has_is_ignored(self):
        words, fixations = _words(), _fixations()
        result = select_trials(words, fixations, metadata={"nope": {"x"}})
        assert result.words is words and result.fixations is fixations
        assert result.selection is None


class TestDisagreement:
    def test_a_reading_the_tables_disagree_on_is_left_out_and_reported(self):
        """Words say p_adv's reading is Adv, Fixations say Ele: neither wins."""
        result = select_trials(
            _words(difficulty_level=LEVELS),
            _fixations(difficulty_level=["Ele"] * 4),
            metadata={"difficulty_level": {"Adv"}},
        )
        assert result.words.empty and result.fixations.empty
        assert result.conflicts == {"difficulty_level": (("p_adv", "adv"),)}
        note = trial_filter_conflict_note(result.conflicts)
        assert "1 trial" in note and "p_adv · adv" in note
        assert "Words table" in note and "Fixations table" in note

    def test_a_selection_with_both_values_keeps_it(self):
        result = select_trials(
            _words(difficulty_level=LEVELS),
            _fixations(difficulty_level=["Ele"] * 4),
            metadata={"difficulty_level": {"Adv", "Ele"}},
        )
        assert result.conflicts == {}
        assert len(_readings(result.fixations)) == 2

    def test_a_fallback_text_id_gives_way_to_a_mapped_one(self):
        """With no Text ID mapped, a table's ``text_id`` is its trial id. That
        is not a text, so it does not contradict the Words table's real one."""
        words = _words(text_id=["passage"] * 4).assign(**{TEXT_ID_MAPPED: True})
        fixations = _fixations(text_id=["adv", "adv", "ele", "ele"]).assign(
            **{TEXT_ID_MAPPED: False}
        )
        result = select_trials(words, fixations, metadata={"text_id": {"passage"}})
        assert result.conflicts == {}
        assert len(_readings(result.fixations)) == 2


class TestRawGaze:
    def _samples(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "participant_id": ["p_adv", "p_ele", "p_s"],
                "trial_id": ["adv", "ele", "samples_only"],
                "x": [1.0, 2.0, 3.0],
                "y": [1.0, 2.0, 3.0],
            }
        )

    def test_samples_follow_the_readings_the_tables_know(self):
        words, fixations = _words(difficulty_level=LEVELS), _fixations()
        result = select_trials(words, fixations, metadata={"difficulty_level": {"Adv"}})
        kept = raw_gaze_in_pool(
            self._samples(),
            words,
            fixations,
            result.words,
            result.fixations,
            keep_unknown=result.selection.keeps_unknown,
        )
        assert _readings(kept) == [("p_adv", "adv")]
        assert _readings(result.selection.narrow(self._samples())) == [("p_adv", "adv")]

    def test_a_range_keeps_a_samples_only_trial(self):
        words = _words(score=[0.2, 0.2, 0.9, 0.9])
        result = select_trials(words, _fixations(), ranges={"score": (0.0, 0.5)})
        assert result.selection.keeps_unknown
        assert _readings(result.selection.narrow(self._samples())) == [
            ("p_adv", "adv"),
            ("p_s", "samples_only"),
        ]


# -----------------------------------------------------------------------------
# The app: the trial picker offers only what the filter keeps.
# -----------------------------------------------------------------------------


def _loaded(words_levels=None, fixation_levels=None):
    words = pd.DataFrame(
        {
            "participant_id": ["p_adv", "p_adv", "p_ele", "p_ele"],
            "trial_id": ["adv", "adv", "ele", "ele"],
            "word_id": [0, 1, 0, 1],
            "text": ["hello", "world", "hello", "world"],
            "x": [0, 100, 0, 100],
            "y": [0, 0, 0, 0],
            "width": [90, 90, 90, 90],
            "height": [20, 20, 20, 20],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p_adv", "p_adv", "p_ele", "p_ele"],
            "trial_id": ["adv", "adv", "ele", "ele"],
            "x": [5, 105, 5, 105],
            "y": [5, 5, 5, 5],
            "duration_ms": [100, 100, 300, 300],
        }
    )
    if words_levels is not None:
        words["difficulty_level"] = words_levels
    if fixation_levels is not None:
        fixations["difficulty_level"] = fixation_levels
    return api.load_scanpath_data(words, fixations, names="canonical")


@pytest.mark.timeout(240)
class TestTheApp:
    NAME = "Two tables"

    def _open(self, words, fixations, selection):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
        at.session_state["_datasets"] = {
            self.NAME: {
                "words": words,
                "fixations": fixations,
                "raw_gaze": pd.DataFrame(),
                "filter_fields": ["difficulty_level"],
                "composite_trial_columns": [],
            }
        }
        at.session_state["data_source_choice"] = self.NAME
        at.run()
        assert not at.exception, at.exception
        at.session_state["filter_difficulty_level"] = selection
        at.session_state["_trial_filters"] = {
            "participants": None,
            "metadata": {"difficulty_level": set(selection)},
            "ranges": {},
            "ranges_drop_unknown": (),
            "metadata_keys": {"difficulty_level": "filter_difficulty_level"},
            "participant_filter_keys": (),
            "trial_keys": None,
            "trial_filter_keys": (),
            "text_filter_keys": (),
            "favorites_only": False,
            "required_tags": [],
            "excluded_tags": [],
        }
        at.run()
        assert not at.exception, at.exception
        return at

    @pytest.mark.parametrize("owner", ["words", "fixations"])
    def test_choosing_adv_leaves_only_the_adv_reading(self, owner):
        levels = ["Adv", "Adv", "Ele", "Ele"]
        words, fixations = _loaded(
            words_levels=levels if owner == "words" else None,
            fixation_levels=levels if owner == "fixations" else None,
        )
        at = self._open(words, fixations, ["Adv"])
        options = [str(o) for o in at.selectbox(key="single_trial_id").options]
        assert any("adv" in o for o in options)
        assert not any("ele" in o for o in options), options

    def test_a_disagreement_is_said_on_the_page(self):
        words, fixations = _loaded(
            words_levels=["Adv", "Adv", "Ele", "Ele"],
            fixation_levels=["Ele", "Ele", "Ele", "Ele"],
        )
        at = self._open(words, fixations, ["Ele"])
        text = " ".join(w.value for w in at.warning)
        assert "in the Words table and another in the Fixations table" in text
        assert "p_adv · adv" in text
        options = [str(o) for o in at.selectbox(key="single_trial_id").options]
        assert not any("adv" in o for o in options), options
