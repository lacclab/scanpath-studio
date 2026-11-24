"""Metadata publication choices across table replacement and bundle creation."""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import export
from scanpath_studio import metadata as md


@pytest.fixture
def session():
    import streamlit as st

    st.session_state.clear()
    yield st.session_state
    st.session_state.clear()


def _participants():
    return md.build_participant_metadata(
        pd.DataFrame(
            {"participant_id": ["p1", "p2"], "age": [21, 44], "cohort": ["A", "B"]}
        ),
        "participant_id",
        participants=["p1", "p2"],
    )


def _trials():
    return md.build_trial_metadata(
        pd.DataFrame(
            {"trial_id": ["t1", "t2"], "position": [1, 2], "block": ["x", "y"]}
        ),
        "trial_id",
        keys={("p1", "t1"), ("p1", "t2")},
    )


def _texts():
    return md.build_text_metadata(
        pd.DataFrame({"text_id": ["x1", "x2"], "genre": ["news", "opinion"]}),
        "text_id",
        keys={"x1", "x2"},
    )


#: (picker, session key for the attached table, its fields, the widget's key suffix)
_GRAINS = [
    pytest.param(
        export._render_metadata_field_picker,
        md.SESSION_KEY,
        _participants,
        "_meta_fields",
        id="participant",
    ),
    pytest.param(
        export._render_trial_metadata_field_picker,
        md.TRIAL_SESSION_KEY,
        _trials,
        "_trial_meta_fields",
        id="trial",
    ),
    pytest.param(
        export._render_text_metadata_field_picker,
        md.TEXT_SESSION_KEY,
        _texts,
        "_text_meta_fields",
        id="text",
    ),
]


@pytest.mark.parametrize("picker, state_key, build, suffix", _GRAINS)
class TestEveryGrainPicker:
    def test_no_table_renders_nothing_and_restricts_nothing(
        self, session, picker, state_key, build, suffix
    ):
        assert picker("bulk") is None

    def test_all_fields_selected_means_no_restriction(
        self, session, picker, state_key, build, suffix
    ):
        """Byte-identical to a bundle made with no metadata control."""
        session[state_key] = build()
        assert picker("bulk") is None

    def test_a_still_valid_selection_is_left_alone(
        self, session, picker, state_key, build, suffix
    ):
        table = build()
        session[state_key] = table
        kept = [table.fields[0].name]
        session[f"bulk{suffix}"] = list(kept)

        picker("bulk")

        assert session[f"bulk{suffix}"] == kept

    def test_an_entirely_stale_selection_keeps_the_table_out(
        self, session, picker, state_key, build, suffix
    ):
        session[state_key] = build()
        session[f"bulk{suffix}"] = ["a_column_from_another_study"]

        assert picker("bulk") == ()
        assert session[f"bulk{suffix}"] == []

    def test_a_partly_stale_selection_keeps_the_half_that_is_real(
        self, session, picker, state_key, build, suffix
    ):
        table = build()
        session[state_key] = table
        real = table.fields[0].name
        session[f"bulk{suffix}"] = [real, "gone_with_the_last_table"]

        picker("bulk")

        assert session[f"bulk{suffix}"] == [real]


def _publication_picker_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio import export
    from scanpath_studio import metadata as md

    replacement = st.toggle("Replace tables")
    fields = (
        {"initials": ["AB"], "age": [25]}
        if replacement
        else {"group": ["C"], "condition": ["A"]}
    )
    combos = pd.DataFrame(
        {"participant_id": ["p1"], "trial_id": ["t1"], "text_id": ["x1"]}
    )
    st.session_state[md.SESSION_KEY] = md.build_participant_metadata(
        pd.DataFrame({"participant_id": ["p1"], **fields}),
        "participant_id",
        participants=["p1"],
    )
    st.session_state[md.TRIAL_SESSION_KEY] = md.build_trial_metadata(
        pd.DataFrame({"trial_id": ["t1"], **fields}), "trial_id", keys={("p1", "t1")}
    )
    st.session_state[md.TEXT_SESSION_KEY] = md.build_text_metadata(
        pd.DataFrame({"text_id": ["x1"], **fields}), "text_id", keys={"x1"}
    )
    options = export.ExportOptions(
        include_png=False,
        include_svg=False,
        include_plot_config=False,
        metadata_fields=export._render_metadata_field_picker("bulk"),
        trial_metadata_fields=export._render_trial_metadata_field_picker("bulk"),
        text_metadata_fields=export._render_text_metadata_field_picker("bulk"),
    )
    if st.button("Build"):
        st.session_state["zip"], _ = export.bulk_export(
            combos,
            pd.DataFrame(),
            combos,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            settings={
                "participant_metadata": md.active().frame,
                "trial_metadata": md.active_trials().frame,
                "text_metadata": md.active_texts().frame,
            },
            options=options,
        )


def test_replacing_metadata_cannot_widen_an_explicit_publication_choice():
    import io
    import zipfile

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_publication_picker_app).run()
    paths = {"participants": "participant_id", "trials": "trial_id", "texts": "text_id"}

    def headers():
        at.button[0].click().run()
        assert not at.exception
        with zipfile.ZipFile(io.BytesIO(at.session_state["zip"])) as archive:
            return {
                grain: pd.read_csv(
                    archive.open(f"metadata/{grain}.csv")
                ).columns.tolist()
                for grain in paths
                if f"metadata/{grain}.csv" in archive.namelist()
            }

    # Leave text untouched. Explicitly select one participant field and all
    # trial fields, then verify the ZIP, including the next table's headers.
    at.multiselect(key="bulk_meta_fields").set_value(["group"])
    at.multiselect(key="bulk_trial_meta_fields").set_value(["group"]).run()
    at.multiselect(key="bulk_trial_meta_fields").set_value(["group", "condition"]).run()
    assert headers() == {
        "participants": ["participant_id", "group"],
        "trials": ["trial_id", "group", "condition"],
        "texts": ["text_id", "group", "condition"],
    }
    at.toggle[0].set_value(True).run()
    assert headers() == {"texts": ["text_id", "initials", "age"]}
    assert (
        sum("none of your selected fields" in caption.value for caption in at.caption)
        == 2
    )
    at.multiselect(key="bulk_meta_fields").set_value(["age"])
    at.multiselect(key="bulk_trial_meta_fields").set_value(["age"])
    at.multiselect(key="bulk_text_meta_fields").set_value(["age"]).run()
    assert headers() == {grain: [key, "age"] for grain, key in paths.items()}
    at.toggle[0].set_value(False).run()
    assert headers() == {}
