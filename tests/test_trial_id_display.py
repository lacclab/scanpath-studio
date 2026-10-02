"""UX-187 / UX-189: a trial id shown part by part, and the pickers' help.

The pickers *display* ``l37_1129_2_2_1_Adv_r0`` as
``l37_1129 · 2 · 2 · 1 · Adv · r0``. A plain split on ``_`` cannot do that —
the reader id has an underscore of its own — so the parts come from the ids the
trial is known to be made of, and an id none of them matches stays as it is.
Only the display changes: the selected value is still the id itself.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.utils import (
    trial_id_display,
    trial_id_help,
    trial_id_layout,
    trial_id_parts,
    trial_id_shown,
)

ONESTOP_TEXT_PARTS = ("batch", "article", "paragraph", "level")


class TestTrialIdParts:
    def test_onestop_id_splits_into_its_six_parts(self):
        parts = trial_id_parts(
            "l37_1129_2_2_1_Adv_r0",
            participant_id="l37_1129",
            text_id="2_2_1_Adv",
            text_part_names=ONESTOP_TEXT_PARTS,
        )
        assert parts == [
            ("participant", "l37_1129"),
            ("batch", "2"),
            ("article", "2"),
            ("paragraph", "1"),
            ("level", "Adv"),
            ("reading", "r0"),
        ]
        assert trial_id_display(parts) == "l37_1129 · 2 · 2 · 1 · Adv · r0"

    def test_unknown_text_composition_stays_one_part(self):
        parts = trial_id_parts(
            "l37_1129_2_2_1_Adv_r0", participant_id="l37_1129", text_id="2_2_1_Adv"
        )
        assert [name for name, _ in parts] == ["participant", "text", "reading"]
        assert trial_id_display(parts) == "l37_1129 · 2_2_1_Adv · r0"

    def test_disambiguated_repeat_reads_as_text_and_reading(self):
        # `data._disambiguate_repeated_readings` appends `_r2` to a text id.
        assert trial_id_parts("3_r2", participant_id="p1", text_id="3") == [
            ("text", "3"),
            ("reading", "r2"),
        ]

    @pytest.mark.parametrize(
        ("trial_id", "participant", "text"),
        [
            ("t5", "p1", "x"),  # nothing known in it
            ("reader0_b0", "reader1", "b1"),  # underscores, but not its parts
            ("p1_3_Adv", "p9", "p1_3_Adv"),  # text id fell back to the trial id
        ],
    )
    def test_an_id_matching_none_of_its_parts_is_shown_verbatim(
        self, trial_id, participant, text
    ):
        parts = trial_id_parts(trial_id, participant_id=participant, text_id=text)
        assert parts == [("trial id", trial_id)]
        assert trial_id_display(parts) == trial_id

    def test_per_page_ids_keep_their_page_dressing(self):
        parts = trial_id_parts("Lit_Alchemist_4__page_07")
        assert trial_id_display(parts) == "Lit_Alchemist_4 · page 7"

    def test_composite_components_win(self):
        parts = trial_id_parts(
            "A_p1_False",
            participant_id="p1",
            components=[("unique_paragraph_id", "A"), ("participant_id", "p1")],
        )
        assert parts == [("unique_paragraph_id", "A"), ("participant_id", "p1")]


class TestTrialIdLayout:
    def test_onestop_layout_needs_its_marker_columns(self):
        combos = pd.DataFrame(
            {
                "participant_id": ["l37_1129", "l37_1129"],
                "trial_id": ["l37_1129_2_2_1_Adv_r0", "l37_1129_2_2_2_Ele_r1"],
                "text_id": ["2_2_1_Adv", "2_2_2_Ele"],
            }
        )
        # `paragraph_id` is consumed as the text id by normalization, so the
        # marker is the three that survive it.
        columns = ["article_batch", "article_id", "difficulty_level"]
        display, names = trial_id_layout(combos, columns=columns)
        assert display["l37_1129_2_2_2_Ele_r1"] == "l37_1129 · 2 · 2 · 2 · Ele · r1"
        assert names == ("participant", *ONESTOP_TEXT_PARTS, "reading")

        display, names = trial_id_layout(combos)
        assert display["l37_1129_2_2_1_Adv_r0"] == "l37_1129 · 2_2_1_Adv · r0"
        assert names == ("participant", "text", "reading")

    def test_composite_columns_spell_the_id_out(self):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1"],
                "trial_id": ["A_p1_False"],
                "unique_paragraph_id": ["A"],
                "repeated_reading_trial": [False],
            }
        )
        display, names = trial_id_layout(
            combos,
            composite_cols=[
                "unique_paragraph_id",
                "participant_id",
                "repeated_reading_trial",
            ],
        )
        assert display == {"A_p1_False": "A · p1 · False"}
        assert names == (
            "unique_paragraph_id",
            "participant_id",
            "repeated_reading_trial",
        )

    def test_no_split_means_no_help(self):
        combos = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t5"]})
        display, names = trial_id_layout(combos)
        assert display == {"t5": "t5"}
        assert names == ()
        assert trial_id_help(names) == ""

    def test_help_names_the_parts_and_the_reading(self):
        text = trial_id_help(("participant", "text", "reading"))
        assert "participant · text · reading" in text
        assert "`r0`" in text
        assert "`r0`" not in trial_id_help(("participant", "text"))

    def test_shown_reads_one_trials_rows(self):
        rows = pd.DataFrame(
            {
                "participant_id": ["l37_1129"],
                "text_id": ["2_2_1_Adv"],
                "article_batch": [2],
                "article_id": [2],
                "difficulty_level": ["Adv"],
            }
        )
        assert (
            trial_id_shown("l37_1129_2_2_1_Adv_r0", None, rows)
            == "l37_1129 · 2 · 2 · 1 · Adv · r0"
        )
        # A cross-dataset B carries a namespaced participant; the raw one wins.
        rows["participant_id"] = "OneStop · l37_1129"
        assert (
            trial_id_shown("l37_1129_2_2_1_Adv_r0", rows, participant_id="l37_1129")
            == "l37_1129 · 2 · 2 · 1 · Adv · r0"
        )
        assert trial_id_shown("t5", None) == "t5"


def test_compare_label_keeps_markers_and_participant_suffix():
    from scanpath_studio.tabs import _compare_label_display

    shown = {"p_1_r0": "p · 1 · r0"}
    assert _compare_label_display("📄 p_1_r0", "p_1_r0", "📄", shown) == "📄 p · 1 · r0"
    assert (
        _compare_label_display("p_1_r0 [p2]", "p_1_r0", "", shown) == "p · 1 · r0 [p2]"
    )
    assert _compare_label_display("t5", "t5", "", {}) == "t5"


def test_iframes_sit_off_the_text_baseline():
    """UX-188: an inline iframe left a descender's gap under the plot, which its
    overflow:auto container showed as a scrollbar with nothing to scroll."""
    from scanpath_studio.styles import get_app_css

    css = get_app_css()
    assert 'iframe[data-testid="stIFrame"] {display: block;}' in css
    assert "overflow-y: hidden;" in css


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.timeout(180)
def test_the_scanpath_pickers_show_ids_by_part_and_explain_them():
    from tests.conftest import APP_SCRIPT

    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=90)
    at.run()
    at.session_state["single_compare_toggle"] = True
    at.run()
    assert not at.exception, at.exception

    picker = at.selectbox(key="single_trial_id")
    # The value is still the id itself; only the option text is split.
    assert "_" in picker.value
    assert all(" · " in option for option in picker.options), picker.options
    assert "participant · batch · article · paragraph · level · reading" in (
        picker.help
    )

    compare = at.selectbox(key="single_compare_trial")
    assert compare.label == "**Compare to**"
    assert "📄" in compare.help and "👤" in compare.help
    assert "participant · batch" in compare.help
    assert all(" · " in option for option in compare.options), compare.options
