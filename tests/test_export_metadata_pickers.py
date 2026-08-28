"""DATA-20 §10 / DATA-29: which metadata fields ride along in the export bundle.

Three near-identical pickers, one per grain, each with the same two contracts:

* **Every field selected returns `None`** — "no restriction" — so a bundle
  exported without touching the control is byte-identical to one made before the
  control existed. Returning the full tuple instead would work, but it makes the
  export options differ from a pre-DATA-20 export for no reason.
* **The persisted selection is pruned against *this* table's fields.** Attaching
  a second table leaves a selection naming only the first one's columns;
  Streamlit filters invalid values out silently and the widget yields `[]`, and
  an empty tuple means "leave the table out of the bundle" — so a stale key
  reads as a deliberate omission and the file is simply missing from the zip.

Both failure modes are silent in the produced artefact, which is why they are
pinned here rather than left to the panel that renders them.
"""

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
        """Byte-identical to a bundle made before the control existed."""
        session[state_key] = build()
        assert picker("bulk") is None

    def test_a_still_valid_selection_is_left_alone(
        self, session, picker, state_key, build, suffix
    ):
        """The prune must only remove what this table cannot offer.

        What the picker *returns* for a partial selection is not asserted here:
        outside a script run `st.multiselect` yields its `default=` rather than
        the session value, so bare mode cannot see the user's pick. The ordering
        rule that turns the pick into a tuple is one line
        (`tuple(n for n in names if n in chosen)`) and is exercised through the
        panel by `tests/test_export.py`; the pruning above it is what has a
        silent failure mode, and that is testable here.
        """
        table = build()
        session[state_key] = table
        kept = [table.fields[0].name]
        session[f"bulk{suffix}"] = list(kept)

        picker("bulk")

        assert session[f"bulk{suffix}"] == kept

    def test_a_stale_selection_is_pruned_not_read_as_an_omission(
        self, session, picker, state_key, build, suffix
    ):
        """The bug this guards: a leftover key naming another table's columns
        yields `[]`, and `()` means "leave the table out of the bundle"."""
        session[state_key] = build()
        session[f"bulk{suffix}"] = ["a_column_from_another_study"]

        chosen = picker("bulk")

        # Nothing survived the prune, so the key is dropped and the control
        # falls back to "everything" rather than to "nothing".
        assert f"bulk{suffix}" not in session
        assert chosen is None

    def test_a_partly_stale_selection_keeps_the_half_that_is_real(
        self, session, picker, state_key, build, suffix
    ):
        table = build()
        session[state_key] = table
        real = table.fields[0].name
        session[f"bulk{suffix}"] = [real, "gone_with_the_last_table"]

        picker("bulk")

        assert session[f"bulk{suffix}"] == [real]
