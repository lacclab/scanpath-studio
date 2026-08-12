"""A composite trial id gets **no picker of its own** — trial selection is always
the standard selectbox + scrubbing slider + ◀ ▶ arrows.

BUG-23, round 3. The composite mapping used to fork the picker: first one selector
per raw component (minus UX-5's pruning of the ones that were also trial-filter
columns), then a Participant → Text cascade. Both made the shape of the *mapping*
visible in the UI and neither offered the slider or the step buttons, so stepping
through trials worked on some datasets and not others. Participant and Text are
what the **Narrow by** row is for; the joined id is shown verbatim in the picker
and spelled out part-by-part by the trial chips.
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _picker_app():
    """Render select_trial over a small composite-trial combos frame."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.utils import build_combo_options, select_trial

    # Two texts, two participants, one repeated reading — trial id composed of
    # unique_paragraph_id + participant_id + repeated_reading_trial.
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p1"],
            "unique_paragraph_id": ["A", "B", "A", "A"],
            "repeated_reading_trial": [False, False, False, True],
        }
    )
    fixations["trial_id"] = (
        fixations[["unique_paragraph_id", "participant_id", "repeated_reading_trial"]]
        .astype(str)
        .agg("_".join, axis=1)
    )
    fixations["unique_trial_id"] = fixations["trial_id"]
    fixations["paragraph_id"] = fixations["unique_paragraph_id"]

    st.session_state["_composite_trial_columns"] = [
        "unique_paragraph_id",
        "participant_id",
        "repeated_reading_trial",
    ]
    combos, _, _ = build_combo_options(fixations)
    participant, trial, mode, text = select_trial(combos, key_prefix="single")
    st.session_state["_picked"] = (participant, trial, mode, text)


@pytest.mark.timeout(60)
class TestCompositeTrialPicker:
    def test_composite_mapping_gets_the_standard_picker(self):
        # The whole point of round 3: one picker for every dataset. No cascade
        # selectors, no "Reading" fallback — just **Select Trial** (plus the ⇅
        # popover's own "Sort trials by" selectbox).
        at = AppTest.from_function(_picker_app)
        at.run(timeout=15)
        assert not at.exception
        labels = [s.label for s in at.selectbox]
        assert any(label.startswith("**Select Trial**") for label in labels), labels
        assert "Participant" not in labels, labels
        assert "Text" not in labels, labels
        assert not any(label.startswith("Reading") for label in labels), labels
        assert "repeated_reading_trial" not in labels, labels

    def test_composite_picker_has_the_slider_and_arrows(self):
        # The reported symptom was two bare dropdowns: no slider, no ◀ ▶. Both
        # must be there for a composite mapping like any other.
        at = AppTest.from_function(_picker_app)
        at.run(timeout=15)
        assert not at.exception
        assert "single_trial_pos" in [s.key for s in at.select_slider]
        btn_keys = {b.key for b in at.button if b.key}
        assert {"single_prev_trial", "single_next_trial"} <= btn_keys, btn_keys

    def test_arrow_steps_to_the_next_composite_trial(self):
        at = AppTest.from_function(_picker_app)
        at.run(timeout=15)
        first = at.session_state["_picked"][1]
        at.button(key="single_next_trial").click().run(timeout=15)
        assert not at.exception
        stepped = at.session_state["_picked"][1]
        assert stepped != first
        # Options are the joined ids, in sorted order.
        assert [first, stepped] == ["A_p1_False", "A_p1_True"]

    def test_condition_beyond_participant_and_text_is_just_another_trial(self):
        # A trial id carrying a *condition* (repeated_reading_trial) beyond the two
        # identities used to need a "Reading (multiple trials available)" fallback
        # under the cascade. In one flat picker it is simply one more option.
        at = AppTest.from_function(_picker_app)
        at.run(timeout=15)
        picker = next(s for s in at.selectbox if s.label.startswith("**Select Trial**"))
        assert list(picker.options) == [
            "A_p1_False",
            "A_p1_True",
            "A_p2_False",
            "B_p1_False",
        ]

    def test_single_composite_trial_degrades_without_slider(self):
        # A composite mapping is exactly the shape that narrows to ONE trial, so
        # this path is now hit often: a one-option st.select_slider throws
        # `RangeError` in the browser (invisible to AppTest), so the picker must
        # fall back to the selectbox alone.
        def _one_trial_app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.utils import build_combo_options, select_trial

            fixations = pd.DataFrame(
                {
                    "participant_id": ["p1"],
                    "unique_paragraph_id": ["A"],
                    "trial_id": ["A_p1"],
                    "unique_trial_id": ["A_p1"],
                }
            )
            st.session_state["_composite_trial_columns"] = [
                "unique_paragraph_id",
                "participant_id",
            ]
            combos, _, _ = build_combo_options(fixations)
            st.session_state["_picked"] = select_trial(combos, key_prefix="single")

        at = AppTest.from_function(_one_trial_app)
        at.run(timeout=15)
        assert not at.exception
        assert "single_trial_pos" not in [s.key for s in at.select_slider]
        assert at.session_state["_picked"][1] == "A_p1"

    def test_select_trial_takes_no_prune_list(self):
        # The behavioural tests above can't catch a reintroduced prune on their
        # own: UX-5's version fired only when the caller passed the More-filter
        # column list, so a test that doesn't pass one passes either way. Pin the
        # decision at the seam instead — the picker takes no such input.
        import inspect

        from scanpath_studio.utils import select_trial

        params = set(inspect.signature(select_trial).parameters)
        assert "filter_cols" not in params, params

    def test_onestop_composite_shape_is_one_standard_picker(self):
        # BUG-23, the reported shape: Trial ID maps to participant + the four
        # columns that jointly ARE the paragraph identity (paragraph_id,
        # article_id, article_batch, difficulty_level), and Text ID maps to those
        # same four. Five mapped columns, one picker — labelled **Select Trial**,
        # listing the joined ids verbatim (the user's call: no relabelling).
        def _onestop_app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.utils import build_combo_options, select_trial

            text_cols = ["paragraph_id", "article_id", "article_batch", "difficulty"]
            comp = ["participant_id", *text_cols]
            # One participant, paragraph 1 of two different articles, two
            # difficulties: four trials that collide on (participant, paragraph).
            fixations = pd.DataFrame(
                {
                    "participant_id": ["l10_338"] * 4,
                    "paragraph_id": [1, 1, 1, 1],
                    "article_id": [10, 10, 11, 11],
                    "article_batch": [3, 3, 3, 3],
                    "difficulty": ["Adv", "Ele", "Adv", "Ele"],
                }
            )
            # What `data.normalize_fixations` writes for a multi-column Text ID
            # mapping (`trial_id_series` joins it the same way as the trial id).
            fixations["text_id"] = (
                fixations[text_cols].astype(str).agg("_".join, axis=1)
            )
            fixations["trial_id"] = fixations[comp].astype(str).agg("_".join, axis=1)
            fixations["unique_trial_id"] = fixations["trial_id"]
            st.session_state["_composite_trial_columns"] = comp
            # What the wizard ticks under "Filter trials by" (every detected meta
            # column) must not shape the picker.
            st.session_state["wizard_filter_fields"] = list(text_cols)
            combos, _, _ = build_combo_options(fixations)
            st.session_state["_picked"] = select_trial(combos, key_prefix="single")

        at = AppTest.from_function(_onestop_app)
        at.run(timeout=15)
        assert not at.exception
        picker = next(s for s in at.selectbox if s.label.startswith("**Select Trial**"))
        assert "Participant" not in [s.label for s in at.selectbox]
        assert list(picker.options) == [
            "l10_338_1_10_3_Adv",
            "l10_338_1_10_3_Ele",
            "l10_338_1_11_3_Adv",
            "l10_338_1_11_3_Ele",
        ]
        _, trial, _, text = at.session_state["_picked"]
        assert trial == "l10_338_1_10_3_Adv"
        assert text == "1_10_3_Adv"

    def test_selecting_a_composite_trial_id_resolves_it(self):
        at = AppTest.from_function(_picker_app)
        at.run(timeout=15)
        at.selectbox(key="single_trial_id").set_value("B_p1_False").run(timeout=15)
        assert not at.exception
        participant, trial, mode, text = at.session_state["_picked"]
        assert mode == "Trial"
        assert trial == "B_p1_False"
        assert participant == "p1"
        assert text == "B"

    def test_header_breaks_out_composite_parts(self):
        # The trial-info header spells out the composite id's remaining parts on
        # their own labeled lines (like Participant / Text), instead of only the
        # opaque joined id.
        def _header_app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.tabs import _render_trial_header

            trial_words = pd.DataFrame(
                {
                    "participant_id": ["l37_1129"],
                    "unique_paragraph_id": ["2_1_1_Ele"],
                    "paragraph_id": ["2_1_1_Ele"],
                    "repeated_reading_trial": [False],
                }
            )
            st.session_state["_composite_trial_columns"] = [
                "unique_paragraph_id",
                "participant_id",
                "repeated_reading_trial",
            ]
            _render_trial_header("l37_1129", "2_1_1_Ele_l37_1129_False", trial_words)

        at = AppTest.from_function(_header_app)
        at.run(timeout=15)
        assert not at.exception
        body = " ".join(m.value for m in at.markdown)
        assert "Participant:" in body
        assert "Text:" in body
        # The extra (non participant/text) component is spelled out, humanized.
        assert "Repeated reading trial:" in body
        assert "False" in body

    def test_header_no_extra_rows_without_composite(self):
        def _header_app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.tabs import _render_trial_header

            trial_words = pd.DataFrame(
                {"participant_id": ["p1"], "paragraph_id": ["A"]}
            )
            st.session_state["_composite_trial_columns"] = None
            _render_trial_header("p1", "t1", trial_words)

        at = AppTest.from_function(_header_app)
        at.run(timeout=15)
        assert not at.exception
        body = " ".join(m.value for m in at.markdown)
        assert "Repeated reading trial:" not in body

    def test_single_column_mapping_keeps_plain_dropdown(self):
        # Sanity: with no composite columns flagged, Trial mode still shows the
        # single unique-trial dropdown.
        def _plain_app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.utils import build_combo_options, select_trial

            fixations = pd.DataFrame(
                {
                    "participant_id": ["p1", "p2"],
                    "trial_id": ["t1", "t2"],
                    "paragraph_id": ["A", "B"],
                }
            )
            st.session_state["_composite_trial_columns"] = None
            combos, _, _ = build_combo_options(fixations)
            select_trial(combos, key_prefix="single")

        at = AppTest.from_function(_plain_app)
        at.run(timeout=15)
        assert not at.exception
        labels = [s.label for s in at.selectbox]
        assert any(label.startswith("**Select Trial**") for label in labels), labels


@pytest.mark.timeout(60)
def test_annotation_markers_compose():
    """UX-6: ★ favorite · 🏷️ tagged · 📝 noted compose independently (zero, one,
    two, or all three), and an un-annotated trial gets no markers."""

    def _markers_app():
        import streamlit as st

        from scanpath_studio.annotations import set_entry
        from scanpath_studio.utils import annotation_markers

        set_entry("p1", "t_star", star=True, tags=[], note="")
        set_entry("p1", "t_tag", star=False, tags=["Review"], note="")
        set_entry("p1", "t_note", star=False, tags=[], note="hi")
        set_entry("p1", "t_all", star=True, tags=["Review"], note="hi")
        st.session_state["_marks"] = {
            "none": annotation_markers("p1", "t_none"),
            "star": annotation_markers("p1", "t_star"),
            "tag": annotation_markers("p1", "t_tag"),
            "note": annotation_markers("p1", "t_note"),
            "all": annotation_markers("p1", "t_all"),
        }

    at = AppTest.from_function(_markers_app)
    at.run(timeout=15)
    assert not at.exception
    marks = at.session_state["_marks"]
    assert marks["none"] == ""
    assert marks["star"] == "★"
    assert marks["tag"] == "🏷️"
    assert marks["note"] == "📝"
    assert marks["all"] == "★🏷️📝"


def test_restore_selection_seeds_the_trial_id_for_a_composite_mapping(monkeypatch):
    """A deep link / saved config must seed the key the picker really reads. There
    is now one such key for every dataset (`<prefix>_trial_id`); a leftover
    `_composite_*` key reads nothing, and the link would land on whatever trial the
    picker defaulted to instead of the requested one."""
    import pandas as pd

    from scanpath_studio import url_state as url_state_module

    class _FakeSt:
        def __init__(self):
            self.session_state: dict = {}

    fake = _FakeSt()
    fake.session_state["_composite_trial_columns"] = [
        "participant_id",
        "paragraph_id",
        "difficulty",
    ]
    monkeypatch.setattr(url_state_module, "st", fake)
    combos = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "text_id": ["1_Adv", "1_Ele"],
            "paragraph_id": [1, 1],
            "difficulty": ["Adv", "Ele"],
            "trial_id": ["p1_1_Adv", "p1_1_Ele"],
        }
    )
    ok = url_state_module._restore_selection(
        {"participant_id": "p1", "trial_id": "p1_1_Ele"}, combos
    )
    assert ok is True
    state = fake.session_state
    assert state["single_trial_id"] == "p1_1_Ele"
    # No `_composite_*` keys at all — the cascade they fed is gone.
    assert not [k for k in state if k.startswith("single_composite")], state


def test_trial_display_label_prettifies_multipleye_pages():
    """MultiplEYE per-page ids read as 'stimulus · page N' (zero-pad dropped for
    display); other ids pass through unchanged."""
    from scanpath_studio.utils import _trial_display_label

    assert (
        _trial_display_label("Lit_Alchemist_4__page_01") == "Lit_Alchemist_4 · page 1"
    )
    assert (
        _trial_display_label("Lit_Alchemist_4__page_13") == "Lit_Alchemist_4 · page 13"
    )
    # Non-page ids untouched (no-op for every other corpus).
    assert _trial_display_label("reader0_b0") == "reader0_b0"
    assert _trial_display_label("p1_3_Adv") == "p1_3_Adv"
