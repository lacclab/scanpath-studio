"""An added dataset's recording setup is that dataset's alone.

The setup the add screen records (screen size, physical geometry, text sizing,
font) is written onto the figure's shared ``global_*`` keys whenever the dataset
is opened, and leaving it puts back what those keys held before — so adding a
dataset with a different screen never redraws the demo on that screen.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.constants import DEMO_CHOICE
from scanpath_studio.experimental_setup import Provenance, SetupSnapshot

pytest.importorskip("streamlit.testing.v1")

_WORDS = pd.DataFrame(
    {
        "participant_id": ["p1"],
        "trial_id": ["t1"],
        "word_id": [1],
        "text": ["a"],
        "x": [0.0],
        "y": [0.0],
        "width": [10.0],
        "height": [10.0],
    }
)
_FIXATIONS = pd.DataFrame(
    {
        "participant_id": ["p1"],
        "trial_id": ["t1"],
        "x": [1.0],
        "y": [1.0],
        "duration_ms": [100],
    }
)

#: What the add screen records for an import it can only estimate: a screen
#: read off the data's extent, with the text not fitted to its boxes.
_ESTIMATED = SetupSnapshot(
    canvas_width=2100,
    canvas_height=800,
    base_font_size=18,
    line_spacing=1.2,
    scale_text_to_boxes=False,
    screen_provenance=Provenance.ESTIMATED,
    geometry_provenance=Provenance.ASSUMED,
    text_provenance=Provenance.ASSUMED,
)


@pytest.fixture
def session():
    import streamlit as st

    st.session_state.clear()
    yield st.session_state
    st.session_state.clear()


def _open(choice):
    """One run's canvas resolution for ``choice``, as `main` does it."""
    import streamlit as st

    from scanpath_studio import app

    st.session_state["data_source_choice"] = choice
    return app.seed_canvas_state(_WORDS, _FIXATIONS, data_choice=choice)


def _add(session, name, setup: SetupSnapshot):
    """➕ Add dataset → ✅ Add dataset, over whichever dataset is open."""
    from scanpath_studio import wizard

    wizard._enter_add_data_wizard()
    session["_wizard_finalize_payload"] = {
        "words": _WORDS,
        "fixations": _FIXATIONS,
        "raw_gaze": pd.DataFrame(),
        "setup": setup.to_dict(),
    }
    session["wizard_dataset_name"] = name
    wizard._finalize_wizard_dataset()
    return session.pop("_pending_source_choice")


def _figure(session):
    return (
        session["global_canvas_width"],
        session["global_canvas_height"],
        session["global_scale_text_to_boxes"],
    )


class TestAddingADataset:
    def test_the_demo_keeps_its_own_screen(self, session):
        _open(DEMO_CHOICE)
        assert _figure(session) == (2560, 1440, True)

        added = _add(session, "Mine", _ESTIMATED)
        _open(added)
        # The new dataset is drawn on the screen it was set up with.
        assert _figure(session) == (2100, 800, False)

        _open(DEMO_CHOICE)
        assert _figure(session) == (2560, 1440, True)

    def test_the_new_dataset_gets_its_setup_back_on_every_visit(self, session):
        _open(DEMO_CHOICE)
        added = _add(session, "Mine", _ESTIMATED)
        _open(added)
        _open(DEMO_CHOICE)
        _open(added)
        assert _figure(session) == (2100, 800, False)
        assert session["global_base_font_size"] == 18
        assert session["global_line_spacing"] == pytest.approx(1.2)

    def test_answers_typed_on_the_add_screen_do_not_reach_the_demo(self, session):
        """The add screen publishes a chosen answer as it is given; adding the
        dataset files it under the new dataset, not the one it was opened over."""
        from scanpath_studio import wizard

        _open(DEMO_CHOICE)
        wizard._enter_add_data_wizard()
        session["global_canvas_width"] = 1920
        session["global_canvas_height"] = 1080
        session["_wizard_finalize_payload"] = {
            "words": _WORDS,
            "fixations": _FIXATIONS,
            "raw_gaze": pd.DataFrame(),
            "setup": SetupSnapshot(
                canvas_width=1920,
                canvas_height=1080,
                screen_provenance=Provenance.MEASURED,
            ).to_dict(),
        }
        session["wizard_dataset_name"] = "Mine"
        wizard._finalize_wizard_dataset()
        _open(session.pop("_pending_source_choice"))
        assert _figure(session)[:2] == (1920, 1080)
        _open(DEMO_CHOICE)
        assert _figure(session) == (2560, 1440, True)

    def test_cancelling_the_add_screen_puts_the_demo_back(self, session):
        from scanpath_studio import app, wizard

        _open(DEMO_CHOICE)
        wizard._enter_add_data_wizard()
        session["global_canvas_width"] = 1920
        session["global_scale_text_to_boxes"] = False
        app.leave_add_data_wizard()
        _open(session.pop("_pending_source_choice"))
        assert _figure(session) == (2560, 1440, True)

    def test_a_tune_on_the_demo_survives_a_visit_to_the_new_dataset(self, session):
        _open(DEMO_CHOICE)
        session["global_scale_text_to_boxes"] = False
        session["global_base_font_size"] = 30
        added = _add(session, "Mine", _ESTIMATED)
        _open(added)
        _open(DEMO_CHOICE)
        assert session["global_scale_text_to_boxes"] is False
        assert session["global_base_font_size"] == 30
        assert _figure(session)[:2] == (2560, 1440)

    def test_a_tune_on_the_new_dataset_lasts_the_visit(self, session):
        _open(DEMO_CHOICE)
        added = _add(session, "Mine", _ESTIMATED)
        _open(added)
        session["global_canvas_width"] = 2200
        _open(added)
        assert session["global_canvas_width"] == 2200

    def test_renaming_it_keeps_the_visit(self, session):
        from scanpath_studio import wizard

        _open(DEMO_CHOICE)
        added = _add(session, "Mine", _ESTIMATED)
        _open(added)
        session["global_canvas_width"] = 2200
        renamed = wizard.rename_dataset(added, "Theirs")
        _open(renamed)
        assert session["global_canvas_width"] == 2200
        _open(DEMO_CHOICE)
        assert _figure(session) == (2560, 1440, True)
