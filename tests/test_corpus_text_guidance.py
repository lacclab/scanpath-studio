"""A word profile needs a common text and observations for its chosen measure."""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import data
from tests.conftest import APP_SCRIPT, edit_builtin_mapping, pin_data_view, pin_view


def _profile_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio import tabs

    tabs.render_per_text_tab(
        st.session_state["words"],
        pd.DataFrame(),
        viz_settings={},
        canvas_width=700,
        canvas_height=460,
        base_font_size=14,
        font_family="Arial",
    )


def _profile(words):
    at = AppTest.from_function(_profile_app)
    at.session_state["words"] = words
    at.session_state["ptext_view"] = "Cohort profile"
    return at.run()


def test_a_trial_number_cannot_combine_unconfirmed_passages():
    words = pd.DataFrame(
        {
            "participant_id": ["a", "b"],
            "trial_id": ["1", "1"],
            "text_id": ["1", "1"],
            "word_id": [1, 1],
            "text": ["Fire", "Snow"],
            "total_fixation_duration_ms": [100, 300],
            data.TEXT_ID_MAPPED: [False, False],
        }
    )
    at = _profile(words)
    assert not at.exception
    assert any("map a **Text ID**" in note.value for note in at.info)
    assert not at.get("plotly_chart")
    at.session_state["words"] = words.assign(**{data.TEXT_ID_MAPPED: [True, False]})
    at.run()
    assert not at.exception
    assert not at.get("plotly_chart")
    at.session_state["words"] = words.iloc[:1]
    at.run()
    assert not at.exception and at.get("plotly_chart")
    # The spelling of the IDs may coincide in a genuine cross-reader text.
    at.session_state["words"] = words.assign(
        **{data.TEXT_ID_MAPPED: True, "text": "Fire"}
    )
    at.run()
    assert not at.exception and at.get("plotly_chart")


def test_an_empty_cohort_profile_explains_the_cause_and_keeps_individual_readings():
    words = pd.DataFrame(
        {
            "participant_id": ["a"],
            "trial_id": ["t"],
            "text_id": ["passage"],
            "word_id": [1],
            "text": ["Word"],
            "first_fixation_ms": pd.array([None], dtype="Float64"),
        }
    )
    at = _profile(words)
    assert not at.exception
    assert not at.get("plotly_chart")
    assert any("No word has a recorded value" in note.value for note in at.info)
    at.session_state["ptext3_readings"] = True
    at.run()
    assert at.dataframe[0].value["source_value"].isna().all()

    at.session_state["words"] = words.assign(first_fixation_ms=200.0)
    at.number_input(key="ptext3_min").set_value(2).run()
    assert not at.exception
    assert not at.get("plotly_chart")
    assert any("Lower it in **Analysis settings**" in note.value for note in at.info)
    assert at.dataframe[0].value["source_value"].tolist() == [200.0]
    at.number_input(key="ptext3_min").set_value(1).run()
    assert not at.exception and at.get("plotly_chart")


def _group_word_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio import tabs

    render = (
        tabs.render_group_comparison_tab
        if st.session_state["comparison"]
        else tabs.render_per_group_tab
    )
    render(
        st.session_state["words"],
        pd.DataFrame(),
        viz_settings={},
        canvas_width=700,
        canvas_height=460,
        base_font_size=14,
        font_family="Arial",
    )


@pytest.mark.parametrize(
    ("view", "download"),
    [
        ("Word profile", "dl_pgrp15"),
        ("Difference word profile", "dl_cmp19"),
        ("Two-group word heatmap", "dl_cmp22"),
    ],
)
def test_group_word_views_need_a_common_text_only_among_the_selected_readings(
    view, download
):
    words = pd.DataFrame(
        {
            "participant_id": ["a", "b", "c", "d"],
            "trial_id": ["1", "1", "1", "2"],
            "text_id": ["1", "1", "1", "elsewhere"],
            "word_id": [1, 1, 1, 1],
            "text": ["Fire", "Snow", "Wind", "Ice"],
            "total_fixation_duration_ms": [100, 300, 400, 600],
            data.TEXT_ID_MAPPED: [False, True, False, True],
        }
    )
    comparison = view != "Word profile"
    prefix = "cmp" if comparison else "pgrp"
    at = AppTest.from_function(_group_word_app)
    at.session_state["comparison"] = comparison
    at.session_state["words"] = words
    at.session_state[f"{prefix}_view"] = view
    at.session_state[f"{prefix}_mode"] = "Independent filter sets"
    if comparison:
        at.session_state["cmp_setA_participant_id"] = ["a"]
        at.session_state["cmp_setB_participant_id"] = ["b"]
    else:
        at.session_state["pgrp_set0_participant_id"] = ["a", "b"]
    at.run()
    assert not at.exception
    assert any("map a **Text ID**" in note.value for note in at.info)
    assert not at.get("plotly_chart")
    assert download not in {button.key for button in at.download_button}

    # An unrelated third reader's unmapped trial 1 cannot disqualify a and b.
    at.session_state["words"] = words.assign(
        **{data.TEXT_ID_MAPPED: [True, True, False, True]},
        text=["Snow", "Snow", "Wind", "Ice"],
    )
    at.run()
    assert not at.exception and at.get("plotly_chart")
    assert at.selectbox(key=f"{prefix}_text").options == ["1  (2 participants)"]
    assert download in {button.key for button in at.download_button}

    # One fallback reading is unambiguous, even if both groups include it.
    at.session_state["words"] = words
    key = "cmp_setB_participant_id" if comparison else "pgrp_set0_participant_id"
    at.multiselect(key=key).set_value(["a"]).run()
    assert not at.exception and at.get("plotly_chart")
    assert at.selectbox(key=f"{prefix}_text").options == ["1  (1 participant)"]


def test_missing_demo_measures_can_be_remapped_from_corpus_analysis():
    from tests.test_apptest import _make_apptest

    at = _make_apptest()
    edit_builtin_mapping(
        at, {f"col_map_words_{key}": None for key in data.READING_MEASURE_KEYS}
    )
    pin_view(at, "Corpus Analysis")
    at.run(timeout=90)
    assert not at.exception
    assert all("can't be remapped" not in note.value for note in at.info)
    at.button(key="corpus_map_measures").click().run(timeout=90)
    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception
    at.selectbox(key="col_map_words_measure_tfd").select("IA_DWELL_TIME").run(
        timeout=90
    )
    at.button(key="builtin_mapping_save").click().run(timeout=90)
    pin_view(at, "Corpus Analysis")
    at.run(timeout=90)
    assert not at.exception
    assert at.selectbox(key="corpus_measure").value == "tfd"


def test_a_fixations_only_upload_can_open_its_words_table_uploader(
    normalized_fixations_df,
):
    name = "Fixations only"
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90)
    at.session_state["_datasets"] = {
        name: {
            "words": data.empty_words_frame(),
            "fixations": normalized_fixations_df,
            "raw_gaze": pd.DataFrame(),
        }
    }
    at.session_state["data_source_choice"] = name
    pin_view(at, "Corpus Analysis")
    at.run()
    assert not at.exception
    button = at.button(key="corpus_map_measures")
    assert button.label == "Add a Words table"
    button.click().run()
    pin_data_view(at)
    at.run()
    assert not at.exception
    assert at.file_uploader(key=f"remap_add_upload_{name}_words")


def test_filtering_out_existing_words_offers_mapping_for_the_dataset(
    normalized_words_df, normalized_fixations_df
):
    name = "Different readers"
    words = normalized_words_df.drop(
        columns=list(data.READING_MEASURE_COLUMNS), errors="ignore"
    )
    words = words.assign(participant_id="word-reader")
    fixations = normalized_fixations_df.assign(participant_id="fixation-reader")
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90)
    at.session_state["_datasets"] = {
        name: {"words": words, "fixations": fixations, "raw_gaze": pd.DataFrame()}
    }
    at.session_state["data_source_choice"] = name
    pin_view(at, "Corpus Analysis")
    at.run()
    assert not at.exception
    at.multiselect(key="filter_participants").set_value(["fixation-reader"]).run()
    assert not at.exception
    assert at.button(key="corpus_map_measures").label == "Map reading measures"
