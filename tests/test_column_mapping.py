"""Tests for the column-mapping sidebar UI (controls.column_mapping_ui).

The Trial ID field is multi-capable: selecting several columns means "build a
unique trial ID on the fly by joining their values" (see data.trial_id_series).
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _mapping_app():
    """Minimal app rendering the Fixations column-mapping UI over a frame
    that has no recognizable unique-trial column."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.controls import FIX_FIELD_SPECS, column_mapping_ui
    from scanpath_studio.data import propose_fix_schema

    df = pd.DataFrame(
        {
            "participant_id": ["p1"],
            "paragraph": ["A"],
            "repeated": [False],
            "CURRENT_FIX_X": [1.0],
            "CURRENT_FIX_Y": [2.0],
            "CURRENT_FIX_DURATION": [100],
        }
    )
    mapping = column_mapping_ui(
        df,
        table_label="Fixations",
        state_key_prefix="col_map_fix",
        field_specs=FIX_FIELD_SPECS,
        proposed=propose_fix_schema(df),
    )
    st.session_state["_result_mapping"] = mapping


@pytest.mark.timeout(60)
class TestTrialMappingMultiselect:
    def test_trial_field_renders_as_multiselect(self):
        at = AppTest.from_function(_mapping_app)
        at.run(timeout=15)
        assert not at.exception
        keys = [m.key for m in at.multiselect]
        assert "col_map_fix_trial" in keys

    def test_single_selection_returns_plain_string(self):
        at = AppTest.from_function(_mapping_app)
        at.run(timeout=15)
        at.multiselect(key="col_map_fix_trial").set_value(["paragraph"]).run(timeout=15)
        mapping = at.session_state["_result_mapping"]
        assert mapping["trial"] == "paragraph"

    def test_multi_selection_returns_column_list(self):
        at = AppTest.from_function(_mapping_app)
        at.run(timeout=15)
        at.multiselect(key="col_map_fix_trial").set_value(
            ["participant_id", "paragraph", "repeated"]
        ).run(timeout=15)
        mapping = at.session_state["_result_mapping"]
        assert mapping["trial"] == ["participant_id", "paragraph", "repeated"]

    def test_empty_selection_returns_none_and_fails_validation(self):
        from scanpath_studio.data import validate_fix_schema

        at = AppTest.from_function(_mapping_app)
        at.run(timeout=15)
        at.multiselect(key="col_map_fix_trial").set_value([]).run(timeout=15)
        mapping = at.session_state["_result_mapping"]
        assert mapping["trial"] is None
        assert any("Trial" in p for p in validate_fix_schema(mapping))

    def test_composite_mapping_normalizes_end_to_end(self):
        """The list mapping returned by the UI feeds normalize_fixations and
        yields the joined on-the-fly unique trial id."""
        import pandas as pd

        from scanpath_studio.data import normalize_fixations

        at = AppTest.from_function(_mapping_app)
        at.run(timeout=15)
        at.multiselect(key="col_map_fix_trial").set_value(
            ["participant_id", "paragraph", "repeated"]
        ).run(timeout=15)
        mapping = at.session_state["_result_mapping"]

        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "paragraph": ["A", "A"],
                "repeated": [False, True],
                "CURRENT_FIX_X": [1.0, 2.0],
                "CURRENT_FIX_Y": [2.0, 3.0],
                "CURRENT_FIX_DURATION": [100, 90],
            }
        )
        result = normalize_fixations(df, mapping)
        assert result["trial_id"].tolist() == ["p1_A_False", "p1_A_True"]
        assert (result["unique_trial_id"] == result["trial_id"]).all()


class TestFixationFieldSpecs:
    """The Fixations panel's required markers must match validate_fix_schema:
    Participant/Trial/Duration are required; X/Y are conditional on a Word/IA ID
    (AOI-sequence data), so they must not be hard-required."""

    def test_required_flags_match_validator(self):
        from scanpath_studio.controls import FIX_FIELD_SPECS

        required = {s["key"] for s in FIX_FIELD_SPECS if s.get("required")}
        assert required == {"participant", "trial", "duration"}

    def test_aoi_only_fixations_pass_validation(self):
        # A Word/IA ID with no X/Y is valid (AOI-sequence fixations).
        from scanpath_studio.data import validate_fix_schema

        schema = {
            "participant": "p",
            "trial": "t",
            "duration": "d",
            "x": None,
            "y": None,
            "word_id": "w",
        }
        assert validate_fix_schema(schema) == []

    def test_no_location_fails_validation(self):
        from scanpath_studio.data import validate_fix_schema

        schema = {"participant": "p", "trial": "t", "duration": "d"}
        problems = validate_fix_schema(schema)
        assert any("X, Y" in p or "Word/IA" in p for p in problems)

    def test_fixation_extras_are_kept_not_mapped(self):
        # pass_index / saccade_type / saccade_amplitude / eye are no longer
        # explicit mapping fields — they ride the optional-keep registry instead
        # (auto-detected, kept, colour-by-able). noise_flag is gone entirely.
        from scanpath_studio.controls import FIX_FIELD_SPECS
        from scanpath_studio.data import FIX_OPTIONAL_FIELDS

        spec_keys = {s["key"] for s in FIX_FIELD_SPECS}
        optional_dests = {dest for _src, dest, _kind, _cat in FIX_OPTIONAL_FIELDS}
        for field in ("pass_index", "saccade_type", "saccade_amplitude", "eye"):
            assert field not in spec_keys
            assert field in optional_dests
        assert "noise_flag" not in spec_keys
        assert "noise_flag" not in optional_dests


class TestSwitchingToAnotherTable:
    """DATA-24: a mapping made for one dataset must not govern the next one.

    A mapping widget owns its key once it has rendered, and an existing key beats
    the ``index=`` auto-detection computes — that is what makes an override
    stick. But the app switches data sources *in place*, so those keys outlive
    the table they describe. Opening the bundled demo (no screen columns, so
    *Screen ID* = ``(none)``) and then switching to MultiplEYE left the field on
    ``(none)`` while the caption under it still read "✨ auto-detected ``page``"
    — the proposal had found the column and only the widget was stale, so the
    multipart trial never saw its own screens.
    """

    @staticmethod
    def _switch_app():
        import pandas as pd
        import streamlit as st

        from scanpath_studio.controls import FIX_FIELD_SPECS, column_mapping_ui
        from scanpath_studio.data import propose_fix_schema

        columns = {
            "participant_id": ["p1"],
            "trial": ["t1"],
            "CURRENT_FIX_X": [1.0],
            "CURRENT_FIX_Y": [2.0],
            "CURRENT_FIX_DURATION": [100],
        }
        if st.session_state.get("_multipart"):
            columns = {**columns, "page": ["page_1"], "screen_index": [1]}
        df = pd.DataFrame(columns)
        st.session_state["_mapping"] = column_mapping_ui(
            df,
            table_label="Fixations",
            state_key_prefix="col_map_fix",
            field_specs=FIX_FIELD_SPECS,
            proposed=propose_fix_schema(df),
        )

    def test_a_field_detected_only_in_the_new_table_is_used(self):
        at = AppTest.from_function(self._switch_app)
        at.run(timeout=30)
        assert at.session_state["_mapping"]["screen_id"] is None

        at.session_state["_multipart"] = True
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state["_mapping"]["screen_id"] == "page", (
            "the second table has a `page` column and auto-detection proposes "
            "it as the screen id, so the field must not stay on the (none) left "
            "behind by the first table"
        )
        # UX-88 removed the *Screen name* field, so `screen_index` is no longer
        # part of a mapping at all — the column is derived downstream instead.
        assert "screen_index" not in at.session_state["_mapping"]

    def test_a_pick_that_still_applies_survives_the_switch(self):
        """Only what has gone stale is cleared — the wizard grows its own frame
        mid-flow (`file_part_N`), so a column-universe change is routine there
        and must not reset the steps already filled in."""
        at = AppTest.from_function(self._switch_app)
        at.run(timeout=30)
        at.selectbox(key="col_map_fix_participant").select("trial").run(timeout=30)
        assert at.session_state["_mapping"]["participant"] == "trial"

        at.session_state["_multipart"] = True
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state["_mapping"]["participant"] == "trial"

    def test_none_is_respected_while_the_table_is_the_same(self):
        """Within one table the widget stays authoritative, so a field the user
        deliberately cleared is not quietly re-detected on the next rerun.

        Uses ``screen_id``, not ``screen_index`` (UX-88 removed *Screen name*
        from every mapping surface — there is no widget of its own for a "None
        stays None" check to apply to; `screen_id` exercises the identical
        mechanism and is still rendered)."""
        at = AppTest.from_function(self._switch_app)
        at.session_state["_multipart"] = True
        at.run(timeout=30)
        assert at.session_state["_mapping"]["screen_id"] == "page"

        at.selectbox(key="col_map_fix_screen_id").set_value(None).run(timeout=30)
        assert at.session_state["_mapping"]["screen_id"] is None
        at.run(timeout=30)
        assert at.session_state["_mapping"]["screen_id"] is None

    def test_the_table_marker_stays_out_of_the_saved_config(self):
        """It records this session's widget state, not the mapping.

        `tabs._collect_column_mapping` sweeps every `col_map_*` key that does not
        end in `_upload` into the saved-config JSON, so a marker named
        `col_map_fix__mapped_columns` would travel in one — and come back as a
        *list* rather than the tuple it was written as, never compare equal to the
        signature again, and clear the mapping on the first run after every
        restore.
        """

        def _sweep_app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.controls import FIX_FIELD_SPECS, column_mapping_ui
            from scanpath_studio.data import propose_fix_schema
            from scanpath_studio.tabs import _collect_column_mapping

            df = pd.DataFrame(
                {
                    "participant_id": ["p1"],
                    "trial": ["t1"],
                    "CURRENT_FIX_X": [1.0],
                    "CURRENT_FIX_Y": [2.0],
                    "CURRENT_FIX_DURATION": [100],
                }
            )
            column_mapping_ui(
                df,
                table_label="Fixations",
                state_key_prefix="col_map_fix",
                field_specs=FIX_FIELD_SPECS,
                proposed=propose_fix_schema(df),
            )
            st.session_state["_swept"] = _collect_column_mapping()

        at = AppTest.from_function(_sweep_app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        swept = at.session_state["_swept"]
        assert swept, "the sweep should still collect the real mapping keys"
        assert not any("mapped_columns" in key for key in swept), (
            f"the table marker rode into the saved config: {sorted(swept)}"
        )
        import json

        json.dumps(swept)  # the config is written as JSON; a tuple would survive


class TestConfirmingAnAutoDetectedField:
    """UX-92 — clicking the ✨ flag is "I chose this", and clears the amber.

    Re-picking the value a select already holds fires no ``on_change``:
    Streamlit dedupes it in the frontend and does not rerun at all. Since
    UX-53 r10 the value lives in the widget key with ``index=None`` (which is
    what makes the ✕ clear work), so the detected column *is* the widget's
    value and confirming it by hand is invisible to Python by construction.
    The flag button is the signal that case has instead.
    """

    @staticmethod
    def _app():
        import pandas as pd
        import streamlit as st

        from scanpath_studio.controls import WORD_FIELD_SPECS, column_mapping_ui
        from scanpath_studio.data import propose_word_schema

        df = pd.DataFrame(
            {
                "participant_id": ["p1"],
                "trial": ["t1"],
                "IA_ID": [1],
                "word": ["a"],
                "IA_LEFT": [0],
                "IA_RIGHT": [10],
                "IA_TOP": [0],
                "IA_BOTTOM": [10],
            }
        )
        st.session_state["_m"] = column_mapping_ui(
            df,
            table_label="AOI",
            state_key_prefix="col_map_words",
            field_specs=WORD_FIELD_SPECS,
            proposed=propose_word_schema(df),
            only_keys=["box"],
            columns_per_row=4,
        )

    @staticmethod
    def _amber(at) -> str:
        """The one <style> block carrying the auto-detected tint."""
        return " ".join(
            str(m.value)
            for m in at.markdown
            if "<style" in str(m.value) and "234, 179, 8" in str(m.value)
        )

    def test_the_flag_is_a_button_while_the_row_is_amber(self):
        at = AppTest.from_function(self._app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        keys = [b.key for b in at.button]

        assert "col_map_words_left_cell_confirm" in keys, (
            "an auto-detected row must offer the one-click confirm — a "
            f"same-value re-pick cannot report itself. Buttons: {keys}"
        )
        assert ".st-key-col_map_words_left_cell " in self._amber(at)

    def test_confirming_clears_the_amber_for_that_field_only(self):
        at = AppTest.from_function(self._app)
        at.run(timeout=30)
        at.button(key="col_map_words_left_cell_confirm").click()
        at.run(timeout=30)
        assert not at.exception, at.exception
        amber = self._amber(at)

        assert ".st-key-col_map_words_left_cell " not in amber, (
            "the confirmed field must go neutral, not stay auto-detected"
        )
        assert ".st-key-col_map_words_right_cell " in amber, (
            "confirming one field must not silently approve the rest"
        )
        # And the mapping itself is untouched — this is a claim about who
        # decided, not a change of value.
        assert at.session_state["_m"]["left"] == "IA_LEFT"
