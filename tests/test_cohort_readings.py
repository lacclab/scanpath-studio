"""#412 — a Corpus Analysis group is a set of readings, whichever table has its field.

Groups → *Independent filter sets* offers a condition from either table, but
`aggregation.group_mask` skipped a column the frame it was given did not
carry. A group defined on ``difficulty_level`` from the Words table therefore
took *every* fixation: the Adv and Ele groups of the review's probe both
pooled the 100 ms and the 300 ms fixation (200 ms, n = 2, twice), and each
counted both readers. A group's fields are now resolved to ``(participant_id,
trial_id)`` readings across both tables before any measure reads them.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import tabs
from scanpath_studio.aggregation import (
    MEASURES,
    READING_KEY,
    apply_group,
    group_mask,
    paired_group_summary,
    resolve_group_spec,
)

ADV = {"difficulty_level": ["Adv"]}
ELE = {"difficulty_level": ["Ele"]}


def _frames(owner: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The review's probe: two readers, one reading each, the condition on
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
        """The review's acceptance: 100 ms for Adv, 300 ms for Ele."""
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
        # The primitive itself no longer skips a column the frame lacks.
        assert not group_mask(fixations, ADV).any()

    def test_a_reading_the_tables_disagree_on_is_left_out(self):
        words, fixations = _frames("words")
        fixations["difficulty_level"] = ["Ele", "Ele"]
        resolved = resolve_group_spec(ELE, words, fixations)
        assert resolved.conflicts == {"difficulty_level": (("p_adv", "adv"),)}
        assert resolved.spec == {READING_KEY: [("p_ele", "ele")]}

    def test_the_fields_and_existing_readings_intersect(self):
        """A participant pick stays as it is; AN-31's readings intersect."""
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
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_groups_app)
    at.session_state["_owner"] = owner
    at.session_state["cmp_mode"] = "Independent filter sets"
    at.session_state["cmp_setA_difficulty_level"] = ["Adv"]
    at.session_state["cmp_setB_difficulty_level"] = ["Ele"]
    at.session_state["cmp_view"] = "Paired summary bars"
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
