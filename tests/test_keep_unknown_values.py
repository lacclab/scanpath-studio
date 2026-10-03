"""*Keep unknown values* — the explicit choice beside a numeric range filter.

A range narrows, it does not exclude the unmeasured (UX-49): a trial with no
value stays in the pool whatever the range. That stays the default. Unticking
*Keep unknown values* asks the other question — "only trials with a measured
value in this range" — for ordinary numeric trial fields and for the
participant, trial and text metadata tables alike, including a reading the
table has no row for.
"""

from __future__ import annotations

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from scanpath_studio import controls
from scanpath_studio import metadata as md
from scanpath_studio.data import filter_trials


@pytest.fixture(autouse=True)
def clean_state():
    st.session_state.clear()
    yield
    st.session_state.clear()


def _frame():
    """Three readings of one text: scores 0.2, 0.9 and none."""
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2", "p3", "p3"],
            "trial_id": ["a"] * 6,
            "score": [0.2, 0.2, 0.9, 0.9, float("nan"), float("nan")],
        }
    )


class TestTheKey:
    def test_it_sits_in_the_filter_layer_beside_its_range(self):
        assert controls.keep_unknown_key("filter_score_range") == (
            "filter_keepunknown_score_range"
        )
        assert controls.keep_unknown_key("cmpfilter_meta_age") == (
            "cmpfilter_keepunknown_meta_age"
        )

    def test_clear_all_sweeps_it_and_leaves_the_other_layer(self):
        st.session_state["filter_keepunknown_score_range"] = False
        st.session_state["cmpfilter_keepunknown_score_range"] = False
        controls.clear_trial_filters("")
        assert "filter_keepunknown_score_range" not in st.session_state
        assert st.session_state["cmpfilter_keepunknown_score_range"] is False

    def test_clearing_one_range_takes_its_choice_with_it(self):
        st.session_state["filter_score_range"] = (0.3, 0.9)
        st.session_state["filter_keepunknown_score_range"] = False
        st.session_state["_trial_filters_raw"] = {
            "filter_keepunknown_score_range": False
        }
        controls.clear_trial_filter("filter_score_range")
        assert "filter_keepunknown_score_range" not in st.session_state
        assert st.session_state["_trial_filters_raw"] == {}


class TestOrdinaryNumericFields:
    def test_filter_trials_leaves_out_the_unknown_only_when_asked(self):
        _, kept = filter_trials(_frame(), _frame(), ranges={"score": (0.0, 1.0)})
        assert set(kept["participant_id"]) == {"p1", "p2", "p3"}
        _, kept = filter_trials(
            _frame(), _frame(), ranges={"score": (0.0, 1.0)}, drop_unknown=["score"]
        )
        assert set(kept["participant_id"]) == {"p1", "p2"}

    def _compute(self, chosen=None, keep=None, *, mirror=False):
        st.session_state["wizard_filter_fields"] = ["score"]
        if chosen is not None:
            st.session_state["filter_score_range"] = chosen
        if keep is not None:
            if mirror:
                st.session_state["_trial_filters_raw"] = {
                    "filter_keepunknown_score_range": keep
                }
            else:
                st.session_state["filter_keepunknown_score_range"] = keep
        return controls._compute_trial_filters(_frame(), _frame())

    def test_kept_by_default(self):
        result = self._compute((0.0, 0.5))
        assert result["ranges"] == {"score": (0.0, 0.5)}
        assert result["ranges_drop_unknown"] == ()

    def test_off_at_full_extent_still_narrows_to_the_measured(self):
        result = self._compute((0.2, 0.9), keep=False)
        assert result["ranges"] == {"score": (0.2, 0.9)}
        assert result["ranges_drop_unknown"] == ("score",)
        assert result["metadata_keys"]["score"] == "filter_score_range"

    def test_the_choice_is_read_back_from_the_mirror(self):
        """A run where the panel is not drawn (another view) keeps it."""
        result = self._compute((0.2, 0.9), keep=False, mirror=True)
        assert result["ranges_drop_unknown"] == ("score",)


def _filter_panel_app() -> None:
    import pandas as pd
    import streamlit as st

    from scanpath_studio.controls import render_trial_filters

    frame = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2", "p3", "p3"],
            "trial_id": ["a"] * 6,
            "score": [0.2, 0.2, 0.9, 0.9, float("nan"), float("nan")],
        }
    )
    st.session_state["wizard_filter_fields"] = ["score"]
    if st.query_params.get("view", "scanpath") == "scanpath":
        render_trial_filters(frame, frame, host=st)
    else:
        st.write("Corpus Analysis")


class TestThePanel:
    def test_the_choice_is_drawn_with_its_count_and_survives_a_view_switch(self):
        at = AppTest.from_function(_filter_panel_app).run()
        assert not at.exception, at.exception
        box = at.checkbox(key="filter_keepunknown_score_range")
        assert box.label == "Keep unknown values" and box.value is True
        captions = [c.value for c in at.caption]
        assert "1 trial has no value and stays in the pool." in captions

        box.uncheck().run()
        assert at.session_state["_trial_filters"]["ranges_drop_unknown"] == ("score",)
        assert "1 trial has no value and is left out." in [c.value for c in at.caption]

        # Another view drops the widget; coming back finds the choice again.
        at.query_params["view"] = "analysis"
        at.run()
        at.query_params["view"] = "scanpath"
        at.run()
        assert at.checkbox(key="filter_keepunknown_score_range").value is False
        assert at.session_state["_trial_filters"]["ranges_drop_unknown"] == ("score",)


# -- metadata tables ----------------------------------------------------------

LOADED = {("p1", "t1"), ("p2", "t1"), ("p3", "t1"), ("p4", "t1")}


def _paired_trials():
    """The round-7 example: p1 10, p2 90, p3 missing, p4 no row."""
    return md.build_trial_metadata(
        pd.DataFrame(
            {
                "reader": ["p1", "p2", "p3"],
                "trial": ["t1"] * 3,
                "score": [10, 90, None],
            }
        ),
        "trial",
        "reader",
        keys=LOADED,
    )


class TestMetadataRanges:
    def test_a_reader_keyed_trial_table(self):
        built = _paired_trials()
        ranges = {"score": (0.0, 20.0)}
        assert md.trials_matching(built, ranges=ranges, keys=LOADED) == {
            ("p1", "t1"),
            ("p3", "t1"),
            ("p4", "t1"),
        }
        assert md.trials_matching(
            built, ranges=ranges, keys=LOADED, keep_unknown={"score": False}
        ) == {("p1", "t1")}
        assert md.unknown_count(built, "score", LOADED) == 2

    def test_a_trial_id_keyed_table_counts_readings(self):
        built = md.build_trial_metadata(
            pd.DataFrame({"trial": ["t1", "t2"], "score": [10, None]}),
            "trial",
            keys={("p1", "t1"), ("p2", "t1"), ("p1", "t2"), ("p1", "t3")},
        )
        loaded = {("p1", "t1"), ("p2", "t1"), ("p1", "t2"), ("p1", "t3")}
        assert md.trials_matching(
            built, ranges={"score": (0, 50)}, keys=loaded, keep_unknown={"score": False}
        ) == {("p1", "t1"), ("p2", "t1")}
        assert md.unknown_count(built, "score", loaded) == 2

    def test_the_participant_table(self):
        built = md.build_participant_metadata(
            pd.DataFrame({"reader": ["p1", "p2", "p3"], "age": [20, 40, None]}),
            "reader",
            participants=["p1", "p2", "p3", "p4"],
        )
        ranges = {"age": (0.0, 30.0)}
        assert md.participants_matching(built, ranges=ranges) == {"p1", "p3", "p4"}
        assert md.participants_matching(
            built, ranges=ranges, keep_unknown={"age": False}
        ) == {"p1"}
        assert md.unknown_count(built, "age") == 2

    def test_the_text_table(self):
        built = md.build_text_metadata(
            pd.DataFrame({"text": ["a", "b", "c"], "length": [100, 300, None]}),
            "text",
            keys=["a", "b", "c", "d"],
        )
        ranges = {"length": (0.0, 200.0)}
        assert md.texts_matching(built, ranges=ranges) == {"a", "c", "d"}
        assert md.texts_matching(
            built, ranges=ranges, keep_unknown={"length": False}
        ) == {"a"}
        assert md.unknown_count(built, "length") == 2

    def test_one_field_leaving_out_unknowns_leaves_out_the_unlisted(self):
        """A reader with no row is unknown for every field, so one range that
        leaves unknowns out is enough to leave them out."""
        built = md.build_participant_metadata(
            pd.DataFrame({"reader": ["p1", "p2"], "age": [20, 40], "iq": [None, 1]}),
            "reader",
            participants=["p1", "p2", "p3"],
        )
        assert md.participants_matching(
            built,
            ranges={"age": (0, 50), "iq": (0, 5)},
            keep_unknown={"age": False},
        ) == {"p1", "p2"}


def _metadata_panel_app() -> None:
    import pandas as pd
    import streamlit as st

    from scanpath_studio import metadata as md
    from scanpath_studio.controls import render_trial_filters

    frame = pd.DataFrame(
        {
            "participant_id": ["p1", "p2", "p3"],
            "trial_id": ["t1", "t2", "t3"],
            "x": [1.0, 2.0, 3.0],
        }
    )
    keys = {("p1", "t1"), ("p2", "t2"), ("p3", "t3")}
    grain = st.query_params.get("grain", "trial")
    if grain == "trial":
        table = md.build_trial_metadata(
            pd.DataFrame({"trial": ["t1", "t2"], "level": [20, None]}),
            "trial",
            keys=keys,
        )
    else:
        table = md.build_participant_metadata(
            pd.DataFrame({"reader": ["p1", "p2"], "level": [20, None]}),
            "reader",
            participants=["p1", "p2", "p3"],
        )
    st.session_state[md.grain_keys(grain)[0]] = table
    st.session_state["wizard_filter_fields"] = []
    render_trial_filters(frame, frame, host=st)


@pytest.mark.parametrize(
    ("grain", "key", "slot", "expected"),
    [
        ("trial", "filter_keepunknown_trialmeta_level", "trial_keys", {("p1", "t1")}),
        ("participant", "filter_keepunknown_meta_level", "participants", ["p1"]),
    ],
)
def test_a_constant_metadata_field_can_still_leave_its_unknowns_out(
    grain, key, slot, expected
):
    """One value among missing rows: no slider, the value shown, and the
    choice is the narrowing it offers — counted over the loaded records."""
    at = AppTest.from_function(_metadata_panel_app)
    at.query_params["grain"] = grain
    at.run()
    assert not at.exception, at.exception
    assert len(at.slider) == 0
    noun = "trials" if grain == "trial" else "readers"
    captions = [c.value for c in at.caption]
    assert f"2 {noun} have no value and stay in the pool." in captions
    assert any("20" in c and "that has a value" in c for c in captions)
    assert at.session_state["_trial_filters"][slot] is None

    at.checkbox(key=key).uncheck().run()
    assert not at.exception, at.exception
    result = at.session_state["_trial_filters"][slot]
    assert (set(result) if slot == "trial_keys" else result) == expected


def test_the_empty_pool_diagnosis_names_and_applies_the_choice():
    from scanpath_studio.app import _filter_diagnosis_steps

    steps = _filter_diagnosis_steps(
        {
            "participants": None,
            "metadata": {},
            "ranges": {"score": (0.0, 1.0)},
            "ranges_drop_unknown": ("score",),
            "metadata_keys": {"score": "filter_score_range"},
            "favorites_only": False,
            "required_tags": [],
            "excluded_tags": [],
        }
    )
    [(label, apply, keys)] = steps
    assert label.endswith("(unknown values excluded)")
    assert keys == ("filter_score_range",)
    _, kept = apply(_frame(), _frame())
    assert set(kept["participant_id"]) == {"p1", "p2"}
