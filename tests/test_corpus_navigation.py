"""Corpus destinations, nested profiles and previously published bookmarks."""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from scanpath_studio import api
from scanpath_studio.aggregation import MEASURES
from scanpath_studio.data import TEXT_ID_MAPPED
from tests.conftest import APP_SCRIPT


def _bookmarked(**query):
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    at._page_hash = calc_hash("corpus-analysis")
    at.query_params.update(query)
    return at


@pytest.mark.parametrize(
    ("section", "destination"),
    [
        ("Per text", "Texts"),
        ("Per participant", "Participants"),
        ("Groups", "Groups"),
        ("Per sentence", "Sentences"),
    ],
)
def test_legacy_section_bookmarks_select_their_parent_destination(section, destination):
    at = _bookmarked(corpus_subtab=section).run()
    assert not at.exception
    assert at.segmented_control(key="corpus_destination").value == destination
    assert at.session_state["corpus_subtab"] == section
    assert at.query_params["corpus_subtab"] == section
    if section in ("Per text", "Per participant"):
        profile_measure = "ptext_measure" if section == "Per text" else "prdr_measure"
        at.selectbox(key=profile_measure).select(MEASURES["ffd"].label).run()
        address = dict(at.query_params)
        at.segmented_control(key="corpus_destination").set_value("Groups").run()
        assert at.selectbox(key="cmp_measure").value == MEASURES["ffd"].label
        at.query_params.clear()
        at.query_params.update(address)
        at.run()
        at.button(key="corpus_back_to_summary").click().run()
        assert not at.exception
        assert at.segmented_control(key="corpus_destination").value == destination
        assert at.session_state["corpus_subtab"] == "Overview"
        assert "corpus_subtab" not in at.query_params


@pytest.mark.parametrize(
    ("group", "picker", "measure_key"),
    [
        ("Text", "ptext_text", "ptext_measure"),
        ("Participant", "prdr_pid", "prdr_measure"),
    ],
)
def test_profile_opens_before_selecting_a_summary_point(group, picker, measure_key):
    measure = MEASURES["ffd"].label
    at = _bookmarked(corpus_group_by=group, corpus_measure=measure).run()
    assert at.selectbox(key=f"corpus_inspect_{group.lower()}").value is None
    at.button(key="corpus_open_profile").click().run()
    assert not at.exception
    assert at.selectbox(key=picker).value
    assert at.selectbox(key=measure_key).value == measure


def test_browser_history_reopens_the_summary_profile_and_measure(experimental_off):
    measure = MEASURES["ffd"].label
    at = _bookmarked(
        corpus_group_by="Participant", corpus_measure=measure, keep=["a", "b"]
    ).run()
    assert not at.exception
    chooser = at.segmented_control(key="corpus_destination")
    assert chooser.options == ["Texts", "Participants", "Groups"]
    assert chooser.value == "Participants"
    assert at.selectbox(key="corpus_measure").value == "ffd"
    summary_link = dict(at.query_params)
    participant = at.selectbox(key="corpus_inspect_participant")
    participant.select(participant.options[-1]).run()
    at.button(key="corpus_open_profile").click().run()
    assert not at.exception
    assert at.segmented_control(key="corpus_destination").value == "Participants"
    assert at.selectbox(key="prdr_measure").value == measure
    profile_link = dict(at.query_params)
    assert profile_link == {
        k: v for k, v in summary_link.items() if k != "corpus_group_by"
    } | {"corpus_subtab": "Per participant"}
    at.selectbox(key="prdr_measure").select(MEASURES["tfd"].label).run()
    assert "corpus_measure" not in at.query_params
    at.segmented_control(key="corpus_destination").set_value("Groups").run()
    assert at.session_state["corpus_subtab"] == "Groups"
    for address, section in (
        (profile_link, "Per participant"),
        (summary_link, "Overview"),
    ):
        at.query_params.clear()
        at.query_params.update(address)
        at.run()
        assert not at.exception
        assert at.session_state["corpus_subtab"] == section
        assert at.segmented_control(key="corpus_destination").value == "Participants"
        assert at.query_params == address
        if section == "Per participant":
            assert at.selectbox(key="prdr_measure").value == measure

    at.segmented_control(key="corpus_destination").set_value("Groups").run()
    assert at.session_state["cmp_measure"] == measure
    assert at.query_params["keep"] == ["a", "b"]
    at.segmented_control(key="corpus_destination").set_value("Texts").run()
    assert at.session_state["corpus_subtab"] == "Overview"
    assert at.selectbox(key="corpus_measure").value == "ffd"
    at.session_state["corpus_subtab"] = (
        "Per participant"  # A tutorial opens its detailed view.
    )
    at.run()
    assert at.segmented_control(key="corpus_destination").value == "Participants"
    assert at.query_params["corpus_subtab"] == "Per participant"


@pytest.mark.parametrize(
    ("section", "measure_key", "measure"),
    [
        ("Groups", "cmp_measure", "sacc_amp"),
        ("Per participant", "prdr_measure", "fix_dur"),
    ],
)
def test_detail_bookmark_restores_a_fixation_measure_while_the_summary_keeps_its_word_measure(
    section, measure_key, measure, experimental_off
):
    word_measure = MEASURES["ffd"].label
    fixation_measure = MEASURES[measure].label
    words, fix = api.load_sample_data(names="canonical")

    def open_source(**query):
        at = _bookmarked(**query)
        at.session_state["data_source_choice"] = "Recorded amplitudes"
        at.session_state["_datasets"] = {
            "Recorded amplitudes": {
                "words": words,
                "fixations": fix.assign(saccade_amplitude=4.0),
                "raw_gaze": pd.DataFrame(),
            }
        }
        return at.run()

    at = open_source(corpus_subtab=section, corpus_measure=word_measure)
    at.selectbox(key=measure_key).select(fixation_measure).run()
    assert not at.exception
    assert at.query_params["corpus_measure"] == fixation_measure
    fresh = open_source(**at.query_params)
    assert not fresh.exception
    assert fresh.selectbox(key=measure_key).value == fixation_measure
    if section == "Per participant":
        fresh.segmented_control(key="corpus_destination").set_value("Groups").run()
        assert fresh.selectbox(key="cmp_measure").value == fixation_measure
        at.session_state["cmp_view"] = "Difference word profile"
        at.segmented_control(key="corpus_destination").set_value("Groups").run()
        assert not at.exception
        assert at.selectbox(key="cmp_measure").value == word_measure
        assert at.query_params["corpus_measure"] == word_measure
    at.segmented_control(key="corpus_destination").set_value("Texts").run()
    summary = at.selectbox(key="corpus_measure")
    assert summary.value == "ffd"
    assert fixation_measure not in summary.options
    assert at.query_params["corpus_measure"] == word_measure


def test_without_text_ids_participants_open_first_and_one_reading_can_still_be_inspected(
    experimental_off,
):
    words, fix = api.load_sample_data(names="canonical")
    first = words.iloc[0]
    reading = {"participant_id": first.participant_id, "trial_id": first.trial_id}
    at = _bookmarked()
    at.session_state["data_source_choice"] = "One reading"
    at.session_state["_datasets"] = {
        "One reading": {
            "words": words[words[list(reading)].eq(reading).all(axis=1)].assign(
                **{TEXT_ID_MAPPED: False}
            ),
            "fixations": fix[fix[list(reading)].eq(reading).all(axis=1)],
            "raw_gaze": pd.DataFrame(),
        }
    }
    at.run()
    assert not at.exception
    assert at.segmented_control(key="corpus_destination").value == "Participants"
    at.segmented_control(key="corpus_destination").set_value("Texts").run()
    assert not at.exception
    assert at.query_params["corpus_subtab"] == "Per text"
    assert at.selectbox(key="ptext_text").value


def test_corpus_tutorial_opens_a_word_profile_and_returns_to_texts(experimental_off):
    at = _bookmarked(corpus_subtab="Groups")
    at.session_state["_tutorial_library_requested"] = True
    at.run()
    at.button(key="tutorial_start_explore_corpus").click().run()
    assert at.segmented_control(key="corpus_destination").value == "Texts"
    assert at.session_state["corpus_subtab"] == "Overview"
    at.button(key="tutorial_next").click().run()
    assert at.selectbox(key="ptext_text").value
    assert at.query_params["corpus_subtab"] == "Per text"
    at.button(key="tutorial_back").click().run()
    assert not at.exception
    assert at.session_state["corpus_subtab"] == "Overview"
    assert at.segmented_control(key="corpus_destination").value == "Texts"
