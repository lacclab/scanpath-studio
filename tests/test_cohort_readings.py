"""A Corpus Analysis group is a set of readings, whichever table has its field.

Groups → *Independent filter sets* offers a condition from either table. A
group's fields are resolved to ``(participant_id, trial_id)`` readings across
both tables before any measure reads them, so a group defined on
``difficulty_level`` from the Words table takes only its own readings'
fixations — never every fixation of a frame that lacks the column, which would
pool both readers into both groups.
"""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from scanpath_studio import api, tabs
from scanpath_studio.aggregation import (
    MEASURES,
    READING_KEY,
    apply_group,
    group_mask,
    paired_group_summary,
    resolve_group_spec,
)
from tests.conftest import APP_SCRIPT

ADV = {"difficulty_level": ["Adv"]}
ELE = {"difficulty_level": ["Ele"]}


def _frames(owner: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The probe: two readers, one reading each, the condition on
    ``owner``'s table only."""
    words = pd.DataFrame(
        {
            "participant_id": ["p_adv", "p_ele"],
            "trial_id": ["adv", "ele"],
            "word_id": [0, 0],
            "first_fixation_ms": [100, 300],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p_adv", "p_ele"],
            "trial_id": ["adv", "ele"],
            "text_id": ["same", "same"],
            "duration_ms": [100, 300],
        }
    )
    target = words if owner == "words" else fixations
    target["difficulty_level"] = ["Adv", "Ele"]
    return words, fixations


@pytest.mark.parametrize("owner", ["words", "fixations"])
class TestEitherTable:
    def test_each_group_is_its_own_readings(self, owner):
        words, fixations = _frames(owner)
        adv = resolve_group_spec(ADV, words, fixations)
        assert adv.available and adv.conflicts == {}
        assert adv.spec == {READING_KEY: [("p_adv", "adv")]}
        assert apply_group(fixations, adv.spec)["duration_ms"].tolist() == [100]
        assert apply_group(words, adv.spec)["participant_id"].tolist() == ["p_adv"]

    def test_the_paired_bars_tell_the_groups_apart(self, owner):
        """Each group takes its own reading: 100 ms for Adv, 300 ms for Ele."""
        words, fixations = _frames(owner)
        bars = paired_group_summary(
            fixations,
            [MEASURES["fix_dur"]],
            ADV,
            ELE,
            words=words,
            fixations=fixations,
        )
        assert bars[["group", "value", "n_observations"]].to_dict("records") == [
            {"group": "Group A", "value": 100.0, "n_observations": 1},
            {"group": "Group B", "value": 300.0, "n_observations": 1},
        ]

    def test_the_counts_name_one_reader_each(self, owner):
        words, fixations = _frames(owner)
        assert tabs._cohort_reader_ids(fixations, words, ADV) == {"p_adv"}
        assert tabs._cohort_reader_ids(fixations, words, ELE) == {"p_ele"}


class TestResolution:
    def test_a_field_neither_table_has_forms_no_group(self):
        """Fail closed: an unresolvable field never selects everyone."""
        words, fixations = _frames("words")
        resolved = resolve_group_spec({"genre": ["news"]}, words, fixations)
        assert not resolved.available and resolved.missing == ("genre",)
        assert apply_group(fixations, resolved.spec).empty
        # The primitive itself never skips a column the frame lacks.
        assert not group_mask(fixations, ADV).any()

    def test_a_reading_the_tables_disagree_on_is_left_out(self):
        words, fixations = _frames("words")
        fixations["difficulty_level"] = ["Ele", "Ele"]
        resolved = resolve_group_spec(ELE, words, fixations)
        assert resolved.conflicts == {"difficulty_level": (("p_adv", "adv"),)}
        assert resolved.spec == {READING_KEY: [("p_ele", "ele")]}

    def test_the_fields_and_existing_readings_intersect(self):
        """A participant pick stays as it is; a spec's own readings intersect."""
        words, fixations = _frames("words")
        spec = {**ADV, "participant_id": ["p_adv"]}
        resolved = resolve_group_spec(spec, words, fixations)
        assert resolved.spec == {
            "participant_id": ["p_adv"],
            READING_KEY: [("p_adv", "adv")],
        }
        none = resolve_group_spec(
            {**ADV, READING_KEY: [("p_ele", "ele")]}, words, fixations
        )
        assert apply_group(fixations, none.spec).empty

    def test_a_spec_on_the_reading_key_alone_is_left_as_it_is(self):
        words, fixations = _frames("words")
        spec = {"participant_id": ["p_ele"]}
        assert resolve_group_spec(spec, words, fixations).spec == spec

    def test_the_page_says_why_a_group_cannot_be_formed(self):
        class _Host:
            def __init__(self):
                self.warned: list[str] = []

            def warning(self, body):
                self.warned.append(body)

        words, fixations = _frames("words")
        fixations["difficulty_level"] = ["Ele", "Ele"]
        host = _Host()
        blocked = tabs._cohort_unavailable(
            host,
            [
                ("Group A", resolve_group_spec({"genre": ["x"]}, words, fixations)),
                ("Group B", resolve_group_spec(ELE, words, fixations)),
            ],
        )
        assert blocked
        assert "**Group A** cannot be formed" in host.warned[0]
        assert "so **Group B** leaves it out (p_adv · adv)" in host.warned[1]


def _groups_app():
    """The Groups comparison over the probe, A = Adv and B = Ele."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio import tabs

    owner = st.session_state.get("_owner", "words")
    words = pd.DataFrame(
        {
            "participant_id": ["p_adv", "p_ele"],
            "trial_id": ["adv", "ele"],
            "word_id": [0, 0],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p_adv", "p_ele"],
            "trial_id": ["adv", "ele"],
            "duration_ms": [100.0, 300.0],
        }
    )
    (words if owner == "words" else fixations)["difficulty_level"] = ["Adv", "Ele"]
    real = tabs.make_paired_bars_figure

    def spy(df, **kwargs):
        st.session_state["_bars"] = df[["group", "value"]].to_dict("records")
        return real(df, **kwargs)

    tabs.make_paired_bars_figure = spy
    try:
        tabs.render_group_comparison_tab(
            words,
            fixations,
            viz_settings={},
            canvas_width=2560,
            canvas_height=1440,
            base_font_size=16,
            font_family="Arial",
        )
    finally:
        tabs.make_paired_bars_figure = real


@pytest.mark.parametrize("owner", ["words", "fixations"])
def test_the_groups_view_compares_the_two_readings(owner):
    at = AppTest.from_function(_groups_app)
    at.session_state["_owner"] = owner
    at.session_state["cmp_mode"] = "Independent filter sets"
    at.session_state["cmp_setA_difficulty_level"] = ["Adv"]
    at.session_state["cmp_setB_difficulty_level"] = ["Ele"]
    at.session_state["cmp_view"] = "Side-by-side summary bars"
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert not at.warning, [w.value for w in at.warning]
    assert any(
        c.value.startswith(
            "**Group A**: 1 participant · **Group B**: 1 participant · "
            "no participant in both"
        )
        for c in at.caption
    ), [c.value for c in at.caption]
    bars = at.session_state["_bars"]
    by_group = {row["group"]: row["value"] for row in bars}
    assert by_group == {"Group A": 100.0, "Group B": 300.0}


def _bookmarked_groups():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    at._page_hash = calc_hash("corpus-analysis")
    at.query_params["corpus_subtab"] = "Groups"
    return at


@pytest.mark.parametrize("owner", ["words", "fixations"])
def test_a_field_on_one_table_can_split_both_groups(owner):
    at = AppTest.from_function(_groups_app)
    at.session_state["_owner"] = owner
    at.session_state["cmp_view"] = "Side-by-side summary bars"
    at.run(timeout=60)
    assert not at.exception
    assert at.selectbox(key="cmp_field").value == "difficulty_level"
    assert [r["value"] for r in at.session_state["_bars"]] == [100.0, 300.0]


def test_group_field_keeps_values_with_different_filter_spellings():
    words = pd.DataFrame({"difficulty_level": [1, True, None]})
    assert tabs._both_frame_values(words, pd.DataFrame(), "difficulty_level") == [
        "1",
        "True",
    ]


def test_profile_becomes_group_a_and_an_unfinished_split_has_no_result(
    experimental_off,
):
    at = _bookmarked_groups().run()
    at.multiselect(key="pgrp_g").set_value(["Ele"]).run()
    at.toggle(key="groups_compare").set_value(True).run()
    assert at.multiselect(key="cmp_a").value == ["Ele"]
    assert at.multiselect(key="cmp_b").value == ["Adv"]
    at.selectbox(key="cmp_view").select("Group means & difference").run()
    downloads = {"dl_cmp21", "dl_cmp21_recipe"}
    assert downloads <= {button.key for button in at.download_button}

    # Either empty side or both together must hold back the result and its files.
    for key, values in (("cmp_a", []), ("cmp_b", []), ("cmp_a", ["Adv"])):
        at.multiselect(key=key).set_value(values).run()
        assert not at.exception
        assert any(
            "at least one value for each group" in info.value for info in at.info
        )
        assert "Difference (A − B)" not in {metric.label for metric in at.metric}
        assert downloads.isdisjoint(button.key for button in at.download_button)

    at.multiselect(key="cmp_b").set_value(["Ele"]).run()
    assert downloads <= {button.key for button in at.download_button}
    at.toggle(key="groups_compare").set_value(False).run()
    assert at.multiselect(key="pgrp_g").value == ["Adv"]


def test_independent_filters_keep_the_named_group_and_allow_the_whole_pool(
    experimental_off,
):
    at = _bookmarked_groups().run()
    at.radio(key="pgrp_mode").set_value("Independent filter sets").run()
    at.text_input(key="pgrp_set0_label").set_value("Elementary readings")
    at.multiselect(key="pgrp_set0_difficulty_level").set_value(["Ele"]).run()
    at.toggle(key="groups_compare").set_value(True).run()
    assert at.radio(key="cmp_mode").value == "Independent filter sets"
    assert at.multiselect(key="cmp_setA_difficulty_level").value == ["Ele"]
    assert at.text_input(key="cmp_setA_label").value == "Elementary readings"
    assert at.multiselect(key="cmp_setB_difficulty_level").value == []
    at.selectbox(key="cmp_view").select("Group means & difference").run()
    assert not at.exception
    words = api.load_sample_data(names="canonical").words
    for label, rows in (
        ("Elementary readings mean", words[words["difficulty_level"] == "Ele"]),
        ("Group B mean", words),
    ):
        mean = (
            rows.groupby("participant_id")["total_fixation_duration_ms"].mean().mean()
        )
        assert next(m.value for m in at.metric if m.label == label) == f"{mean:.2f} ms"
    assert any("all words with a value" in caption.value for caption in at.caption)
    assert any("no filters includes all selected trials" in c.value for c in at.caption)


def test_pool_without_a_split_field_shows_how_to_continue(experimental_off):
    words, fix = api.load_sample_data(names="canonical")
    reading = words.iloc[0]
    selection = {"participant_id": reading.participant_id, "trial_id": reading.trial_id}
    at = _bookmarked_groups()
    at.session_state["data_source_choice"] = "One reading"
    at.session_state["_datasets"] = {
        "One reading": {
            "words": words[words[list(selection)].eq(selection).all(axis=1)],
            "fixations": fix[fix[list(selection)].eq(selection).all(axis=1)],
            "raw_gaze": pd.DataFrame(),
        }
    }
    at.run()
    assert any("No field is available to split" in info.value for info in at.info)
    assert not at.get("plotly_chart")
    at.toggle(key="groups_compare").set_value(True).run()
    at.selectbox(key="cmp_view").select("Group means & difference").run()
    assert not at.exception
    assert "dl_cmp21" not in {button.key for button in at.download_button}
    at.radio(key="cmp_mode").set_value("Independent filter sets").run()
    assert not at.exception
    assert any(
        "Both groups contain the same readings" in note.value for note in at.info
    )
    assert (
        next(m.value for m in at.metric if m.label == "Difference (A − B)") == "0.00 ms"
    )
