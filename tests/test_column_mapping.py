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


class TestTheResolverAgreesWithTheEditor:
    """DATA-26: the mapping editor moves onto the **Data** page, whose body only
    executes while that page is the active view — but the mapping has to drive
    `prepare_data` on the Scanpath and Corpus views too.

    So there are two ways to obtain a mapping: render the editor, or read the
    session keys it wrote (`controls.resolve_column_mapping`). They share
    `_assemble_mapping`, and these tests are what stops them drifting: a
    divergence would show up as the app quietly normalizing under a mapping
    other than the one the user can see.
    """

    @staticmethod
    def _agreement_app():
        import pandas as pd
        import streamlit as st

        from scanpath_studio.controls import (
            FIX_FIELD_SPECS,
            WORD_FIELD_SPECS,
            column_mapping_ui,
            resolve_column_mapping,
        )
        from scanpath_studio.data import propose_fix_schema, propose_word_schema

        fix = pd.DataFrame(
            {
                "participant_id": ["p1"],
                "paragraph": ["A"],
                "CURRENT_FIX_X": [1.0],
                "CURRENT_FIX_Y": [2.0],
                "CURRENT_FIX_DURATION": [100],
            }
        )
        words = pd.DataFrame(
            {
                "RECORDING_SESSION_LABEL": ["p1"],
                "unique_paragraph_id": ["1_1_Ele"],
                "IA_ID": [0],
                "IA_LABEL": ["The"],
                "IA_LEFT": [10.0],
                "IA_RIGHT": [40.0],
                "IA_TOP": [5.0],
                "IA_BOTTOM": [25.0],
            }
        )
        rendered_fix = column_mapping_ui(
            fix,
            table_label="Fixations",
            state_key_prefix="col_map_fix",
            field_specs=FIX_FIELD_SPECS,
            proposed=propose_fix_schema(fix),
        )
        # The word table exercises the two shapes a plain selectbox doesn't:
        # a `kind: "box"` field expanding into all eight box keys, and the
        # multi-capable Trial ID.
        rendered_words = column_mapping_ui(
            words,
            table_label="Words/IA",
            state_key_prefix="col_map_words",
            field_specs=WORD_FIELD_SPECS,
            proposed=propose_word_schema(words),
        )
        st.session_state["_rendered"] = (rendered_fix, rendered_words)
        st.session_state["_resolved"] = (
            resolve_column_mapping(
                fix, "col_map_fix", FIX_FIELD_SPECS, propose_fix_schema(fix)
            ),
            resolve_column_mapping(
                words, "col_map_words", WORD_FIELD_SPECS, propose_word_schema(words)
            ),
        )

    def test_they_produce_the_same_mapping(self):
        at = AppTest.from_function(self._agreement_app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        rendered_fix, rendered_words = at.session_state["_rendered"]
        resolved_fix, resolved_words = at.session_state["_resolved"]
        assert resolved_fix == rendered_fix
        assert resolved_words == rendered_words
        # Not a vacuous pass: the box field really did expand into all
        # eight keys, with the inactive format's four left at None.
        from scanpath_studio.controls import _ALL_BOX_KEYS

        assert set(_ALL_BOX_KEYS) <= set(rendered_words)
        assert rendered_words["left"] == "IA_LEFT"
        assert rendered_words["width"] is None

    def test_a_user_override_is_what_the_resolver_reports(self):
        """The point of reading the keys rather than re-proposing: an override
        must survive a run in which the editor never renders."""
        at = AppTest.from_function(self._agreement_app)
        at.run(timeout=30)
        at.selectbox(key="col_map_fix_participant").set_value("paragraph")
        at.run(timeout=30)
        assert not at.exception, at.exception
        resolved_fix, _ = at.session_state["_resolved"]
        assert resolved_fix["participant"] == "paragraph"

    def test_a_stale_stored_column_falls_back_to_auto_detection(self):
        """A new upload with different headers must not resolve to nothing —
        the rendering editor self-heals via its index lookup, so this does too."""

        def _stale_app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.controls import FIX_FIELD_SPECS, resolve_column_mapping
            from scanpath_studio.data import propose_fix_schema

            df = pd.DataFrame(
                {
                    "participant_id": ["p1"],
                    "CURRENT_FIX_X": [1.0],
                    "CURRENT_FIX_Y": [2.0],
                    "CURRENT_FIX_DURATION": [100],
                }
            )
            st.session_state["col_map_fix_participant"] = (
                "a_column_from_the_last_upload"
            )
            st.session_state["_out"] = resolve_column_mapping(
                df, "col_map_fix", FIX_FIELD_SPECS, propose_fix_schema(df)
            )

        at = AppTest.from_function(_stale_app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state["_out"]["participant"] == "participant_id"


class TestSwitchingToAnotherTable:
    """DATA-24: a mapping made for one dataset must not govern the next one.

    A mapping widget owns its key once it has rendered, and an existing key beats
    the ``index=`` auto-detection computes — that is what makes an override
    stick. But the app switches data sources *in place*, so those keys outlive
    the table they describe. Opening the bundled demo (no screen columns, so
    *Screen order* = ``(none)``) and then switching to MultiplEYE left the field
    on ``(none)`` while the caption under it still read
    "✨ auto-detected ``screen_index``" — the proposal had found the column and
    only the widget was stale, so the multipart trial ordered its screens by name
    instead of by reading order.
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
        assert at.session_state["_mapping"]["screen_index"] is None

        at.session_state["_multipart"] = True
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state["_mapping"]["screen_index"] == "screen_index", (
            "the second table has a screen_index column and auto-detection "
            "proposes it, so the field must not stay on the (none) left behind "
            "by the first table"
        )
        assert at.session_state["_mapping"]["screen_id"] == "page"

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
        deliberately cleared is not quietly re-detected on the next rerun."""
        at = AppTest.from_function(self._switch_app)
        at.session_state["_multipart"] = True
        at.run(timeout=30)
        assert at.session_state["_mapping"]["screen_index"] == "screen_index"

        at.selectbox(key="col_map_fix_screen_index").select("(none)").run(timeout=30)
        assert at.session_state["_mapping"]["screen_index"] is None
        at.run(timeout=30)
        assert at.session_state["_mapping"]["screen_index"] is None

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
