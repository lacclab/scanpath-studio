"""The dataset table's count columns, filled before anything is loaded (DATA-36).

A public corpus is not read until it is opened, so its row on 🗂️ Data used to be
blank — which is most of the table on a fresh session. Each dataset now declares
the figures its own documentation (or its bundle manifest) publishes, and the
table shows those until the dataset is actually loaded, at which point what
loaded takes over.

Two contracts are pinned here. **Honesty**: a declared figure names where it came
from, is a real count, and — for the two datasets that ship inside this repo — is
checked against the files themselves, so a regenerated demo corpus fails a test
instead of quietly publishing a stale number. **Precedence**: a row shows one
side or the other, never a mixture, and a load that finds *more* than was
published is the one case that says the published figure is wrong (you cannot
load more of a corpus than exists; you can easily load less).
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import app
from scanpath_studio.constants import DEMO_CHOICE, SYNTHETIC_CHOICE
from scanpath_studio.data import (
    load_sample_data,
    load_sample_raw_gaze,
    normalize_fixations,
    normalize_words,
    propose_fix_schema,
    propose_word_schema,
    text_ids,
)
from scanpath_studio.synthetic import load_synthetic_data


def _measure(words, fixations, raw_gaze=None, key=("k",)) -> dict:
    """The counts the table computes for frames in memory."""
    return app._dataset_counts(
        words,
        fixations,
        pd.DataFrame() if raw_gaze is None else raw_gaze,
        key,
    )


def _normalized_sample() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    words_raw, fixations_raw = load_sample_data()
    return (
        normalize_words(words_raw, propose_word_schema(words_raw), keep_columns=None),
        normalize_fixations(
            fixations_raw, propose_fix_schema(fixations_raw), keep_columns=None
        ),
        load_sample_raw_gaze(),
    )


def _declaring_entries() -> dict[str, dict]:
    """Every catalogue entry that publishes figures, by token."""
    entries = dict(app._BUILTIN_DATASET_ABOUT)
    entries.update(app.PUBLIC_DATASET_REGISTRY)
    return {
        token: spec for token, spec in entries.items() if spec.get("published_counts")
    }


class TestDeclaredFigures:
    """What a catalogue entry is allowed to publish."""

    def test_every_field_is_one_of_the_table_columns(self):
        """A typo (`Readers`) would be silently dropped rather than shown."""
        for token, spec in _declaring_entries().items():
            unknown = set(spec["published_counts"]) - set(app.DATASET_COUNT_FIELDS)
            assert not unknown, f"{token} publishes unknown field(s): {unknown}"

    def test_every_figure_is_a_positive_count(self):
        for token, spec in _declaring_entries().items():
            for field, value in spec["published_counts"].items():
                assert isinstance(value, int) and not isinstance(value, bool), (
                    f"{token}/{field} is not an int"
                )
                assert value > 0, f"{token}/{field} is not a count"

    def test_every_figure_says_where_it_came_from(self):
        """The honesty rule: a number with no stated basis is a guess, and the
        ℹ️ dialog has nowhere to send a reader who wants to check it."""
        for token, spec in _declaring_entries().items():
            assert str(spec.get("published_counts_source") or "").strip(), (
                f"{token} publishes figures with no source"
            )

    def test_the_source_is_reachable_through_the_one_about_lookup(self):
        """`dataset_about` is the single lookup over both halves of the
        catalogue (DATA-35); the figures ride it rather than a second one."""
        for token in _declaring_entries():
            about = app.dataset_about(token)
            assert about.get("published_counts")
            assert about.get("published_counts_source")


class TestDatasetsThatShipHere:
    """The two datasets inside this repo are checked against their own files."""

    def test_the_demo_figures_match_the_bundled_corpus(self):
        words, fixations, raw_gaze = _normalized_sample()
        measured = _measure(words, fixations, raw_gaze, key=("demo",))
        published = app.published_dataset_counts(DEMO_CHOICE)
        assert published, "the bundled demo publishes no figures"
        assert published == {k: v for k, v in measured.items() if v is not None}

    def test_the_synthetic_figures_match_the_fixture(self):
        words, fixations = load_synthetic_data()
        measured = _measure(words, fixations, key=("synthetic",))
        published = app.published_dataset_counts(SYNTHETIC_CHOICE)
        assert published, "the synthetic trial publishes no figures"
        assert published == {k: v for k, v in measured.items() if v is not None}


class TestWhichNumbersARowShows:
    """Loaded beats published, and the two are never mixed."""

    published = {"Participants": 75, "Texts": 12, "Trials": 900}

    def test_a_corpus_nobody_opened_shows_the_published_figures(self):
        row = app.dataset_row_counts(measured={}, published=self.published)
        assert row.counts == self.published
        assert row.source == "published"

    def test_a_loaded_dataset_shows_what_loaded(self):
        measured = {"Participants": 75, "Texts": 12, "Trials": 900, "Words": 142125}
        row = app.dataset_row_counts(measured=measured, published=self.published)
        assert row.counts == measured
        assert row.source == "loaded"

    def test_a_row_never_mixes_the_two(self):
        """A load that measures fewer fields than were published must not have
        the gaps back-filled from the catalogue — the row would then read as one
        set of measurements while being two."""
        measured = {"Participants": 70, "Texts": None, "Trials": None}
        row = app.dataset_row_counts(measured=measured, published=self.published)
        assert row.counts == {"Participants": 70}
        assert row.counts.get("Texts") is None
        assert row.source == "loaded"

    def test_all_none_is_not_a_measurement(self):
        """`remembered_dataset_counts` answers with every field `None` for a
        dataset it has never seen frames for; that is 'unknown', not 'zero'."""
        measured = dict.fromkeys(app.DATASET_COUNT_FIELDS)
        row = app.dataset_row_counts(measured=measured, published=self.published)
        assert row.counts == self.published
        assert row.source == "published"

    def test_a_dataset_with_neither_shows_nothing(self):
        row = app.dataset_row_counts(measured={}, published={})
        assert row.counts == {}
        assert row.source == ""


class TestCheckingThePublishedFigures:
    """Comparison is only meaningful where both sides know the field."""

    def test_reports_a_field_both_sides_know_and_disagree_on(self):
        row = app.dataset_row_counts(
            measured={"Participants": 70, "Texts": 12},
            published={"Participants": 75, "Texts": 12},
        )
        assert row.differences == {"Participants": (75, 70)}

    def test_ignores_a_field_only_one_side_knows(self):
        row = app.dataset_row_counts(
            measured={"Participants": 75, "Words": 142125},
            published={"Participants": 75, "Trials": 900},
        )
        assert row.differences == {}

    def test_loading_less_is_a_subset_not_a_wrong_figure(self):
        """One regime of OneStop, or a filtered export, is the normal case —
        it says nothing about whether the published figure is right."""
        row = app.dataset_row_counts(
            measured={"Participants": 180}, published={"Participants": 360}
        )
        assert row.differences == {"Participants": (360, 180)}
        assert row.exceeds_published == ()

    def test_loading_more_than_published_means_the_figure_is_wrong(self):
        """You cannot load more of a corpus than it has."""
        row = app.dataset_row_counts(
            measured={"Participants": 400}, published={"Participants": 360}
        )
        assert row.exceeds_published == ("Participants",)

    def test_nothing_to_compare_when_the_dataset_was_never_loaded(self):
        row = app.dataset_row_counts(measured={}, published={"Participants": 360})
        assert row.differences == {}
        assert row.exceeds_published == ()


class TestTheLookup:
    def test_the_catalogue_cannot_be_edited_through_the_lookup(self):
        """`dataset_about` hands out the entry's own figures; a caller that
        edited them in place would be editing the catalogue for the session."""
        app.dataset_about(DEMO_CHOICE)["published_counts"]["Participants"] = 999
        assert app.published_dataset_counts(DEMO_CHOICE)["Participants"] == 2


class TestPreparedBenchmarkCorpora:
    """Their figures are already in the bundle manifest — per column, not prose."""

    def test_manifest_counts_become_table_counts(self):
        entry = {"name": "Provo", "n_readers": 84, "n_texts": 55, "n_fixations": 219556}
        counts = app.benchmark_published_counts(entry)
        assert counts == {"Participants": 84, "Texts": 55, "Fixations": 219556}

    def test_an_unreadable_count_is_left_out_rather_than_read_as_zero(self):
        """`entry_count` returns `None` for a value it cannot parse and `0` for
        one that is absent; publishing either as a count would assert a corpus
        with no readers (the overclaim `entry_count` warns about)."""
        entry = {"name": "Provo", "n_readers": "many", "n_texts": 0, "n_fixations": 12}
        assert app.benchmark_published_counts(entry) == {"Fixations": 12}

    def test_a_corpus_with_no_counts_publishes_nothing(self):
        assert app.benchmark_published_counts({"name": "Provo"}) == {}


class TestTrialsAreTrialsNotTrialIds:
    """A trial is a (participant, trial) pair — what the trial picker lists.

    PoTeC names its trials after the text, so all 75 readers share the same
    twelve ``trial_id`` values: counting distinct ids reported **12 trials** for
    a corpus whose own README says 900 (75 participants × 12 texts).
    """

    @staticmethod
    def _shared_ids() -> tuple[pd.DataFrame, pd.DataFrame]:
        rows = [
            {"participant_id": p, "trial_id": t, "text_id": t, "x": 1.0, "y": 1.0}
            for p in ("r1", "r2")
            for t in ("b0", "b1", "b2")
        ]
        words = pd.DataFrame(rows)
        fixations = pd.DataFrame(rows)
        return words, fixations

    def test_counts_reader_trial_pairs(self):
        words, fixations = self._shared_ids()
        counts = _measure(words, fixations, key=("shared",))
        assert counts["Trials"] == 6

    def test_the_data_page_summary_agrees(self):
        """Two 'Trials' numbers on one page that disagree is a bug in itself."""
        from scanpath_studio import tabs

        words, fixations = self._shared_ids()
        stats = tabs._dataset_statistics(words, fixations, pd.DataFrame(), ("shared",))
        assert stats["n_trials"] == 6

    def test_a_reader_who_skipped_a_text_is_not_counted(self):
        words, fixations = self._shared_ids()
        words = words[
            ~((words["participant_id"] == "r2") & (words["trial_id"] == "b2"))
        ]
        fixations = fixations[
            ~((fixations["participant_id"] == "r2") & (fixations["trial_id"] == "b2"))
        ]
        assert _measure(words, fixations, key=("gap",))["Trials"] == 5


class TestTextsAreCountedFromEveryTable:
    """DATA-50: the Texts figure read the words table only, so a fixations-only
    dataset whose fixations name twelve texts said there were none."""

    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2"],
            "trial_id": ["t1", "t2", "t1"],
            "text_id": ["a", "b", "a"],
            "x": [1.0, 2.0, 3.0],
        }
    )

    def test_a_fixations_only_dataset_counts_its_texts(self):
        counts = _measure(pd.DataFrame(), self.fixations, key=("fix-only",))
        assert counts["Texts"] == 2

    def test_texts_from_several_tables_are_one_union(self):
        words = pd.DataFrame({"participant_id": ["p1"], "text_id": ["c"]})
        counts = _measure(words, self.fixations, key=("union",))
        assert counts["Texts"] == 3

    def test_the_stats_tab_counts_the_same_way(self):
        from scanpath_studio import tabs

        empty_words = pd.DataFrame(columns=["participant_id", "trial_id"])
        stats = tabs._dataset_statistics(
            empty_words, self.fixations, pd.DataFrame(), ("stats-fix-only",)
        )
        assert stats["n_texts"] == 2

    def test_unique_text_id_wins_over_text_id_everywhere(self):
        """One id space: a frame carrying only `text_id` is not mixed in."""
        words = pd.DataFrame({"unique_text_id": ["u1", "u2"], "text_id": ["1", "2"]})
        assert text_ids(words, self.fixations, None) == {"u1", "u2"}


@pytest.mark.parametrize("token", [DEMO_CHOICE, SYNTHETIC_CHOICE])
def test_the_packaged_sources_publish_figures(token):
    assert app.published_dataset_counts(token)


def test_the_public_corpora_publish_figures():
    """The rows this item exists for: opened by nobody, and no longer blank."""
    assert app.published_dataset_counts("PoTeC — Potsdam Textbook Corpus")


@pytest.mark.parametrize("regime", list(app.ONESTOP_REGIME_CHOICES))
def test_a_onestop_regime_publishes_only_its_own_measured_figures(regime):
    """DATA-63: the corpus publishes whole-release figures, not per regime, so a
    regime never quotes them. DATA-65 pinned the reports, which makes a regime's
    own count stable enough to publish: a counted regime shows exactly what was
    measured, and one not yet counted says *Not counted* until it is opened."""
    published = app.published_dataset_counts(app.ONESTOP_REGIME_CHOICES[regime])
    assert published == app._ONESTOP_REGIME_COUNTS.get(regime, {})
    if published:
        assert set(published) <= set(app.DATASET_COUNT_FIELDS)
        # Never the whole release's 360 readers: each regime holds half.
        assert published["Participants"] < 360


class TestTheTableItself:
    """End to end: what the 🗂️ Data page's table actually renders."""

    @staticmethod
    def _table(at) -> pd.DataFrame:
        records = at.session_state[app.DATASET_TABLE_ROWS_KEY]
        assert records, "the dataset table did not render"
        return pd.DataFrame(records)

    @pytest.fixture(scope="class")
    def table(self) -> pd.DataFrame:
        from streamlit.testing.v1 import AppTest

        from tests.conftest import APP_SCRIPT, pin_data_view

        at = AppTest.from_file(APP_SCRIPT, default_timeout=90)
        pin_data_view(at)
        at.run()
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        return self._table(at)

    def test_a_corpus_nobody_opened_arrives_with_its_figures(self, table):
        row = table.set_index("Dataset").loc["PoTeC"]
        assert row["Counts"] == "Published"
        assert (row["Participants"], row["Texts"], row["Trials"]) == (75, 12, 900)

    def test_the_open_dataset_shows_what_it_loaded(self, table):
        row = table.set_index("Dataset").loc["Bundled demo"]
        assert row["Counts"] == "Loaded"
        assert row["Participants"] == 2

    def test_the_manual_sample_is_counted_without_being_opened(self, table):
        """It is built in memory, so it is counted even with no recovery cache
        to remember it — as on Streamlit Community Cloud."""
        row = table.set_index("Dataset").loc["Hand-drawn sample"]
        assert row["Counts"] == "Loaded"
        assert row["Participants"] == 1
        assert row["Fixations"] > 0

    def test_a_source_that_publishes_nothing_stays_blank(self, table):
        """MultiplEYE reads whatever session folders are on this machine, so no
        figure would be true of the next person's copy."""
        row = table.set_index("Dataset").loc["MultiplEYE"]
        assert row["Counts"] == ""
        assert pd.isna(row["Participants"])
        # UX-174: and the cell says why, rather than showing a blank or a 0.
        assert row["_cells"]["Participants"] == "Not counted"


class TestWhatTheDataPageSays:
    """UX-177: one sentence per dataset, a note only where it matters."""

    def _catalogue(self):
        registry = app.public_dataset_registry()
        return list(registry) + list(app._BUILTIN_DATASET_ABOUT), registry

    def test_every_description_is_one_sentence(self):
        tokens, registry = self._catalogue()
        for token in tokens:
            text = app.dataset_about(token, registry).get("description") or ""
            assert app._overview_sentence(text)[1] == "", (token, text)

    def test_no_coordinate_badge_is_left_in_the_catalogue(self):
        tokens, registry = self._catalogue()
        for token in tokens:
            assert "geometry" not in app.dataset_about(token, registry)

    def test_only_the_datasets_whose_figures_read_differently_carry_a_note(self):
        tokens, registry = self._catalogue()
        noted = {
            token
            for token in tokens
            if app.dataset_about(token, registry).get("reading_note")
        }
        assert noted == {"PoTeC — Potsdam Textbook Corpus", DEMO_CHOICE}
