"""A column mapping the pipeline *rejects* must not take the whole app down.

`prepare_data` has always had a recovery path for a mapping that is merely
**incomplete** (a required field unmapped → `problems` → the raw tables plus the
still-editable Column mapping panels). A mapping that is complete but
**impossible** — the one-sided `screen_id` below, which `multipart` rejects
because two coordinate spaces must not be joined — used to escape as a raw
`ValueError` out of `main()`, so the run died *before* rendering the mapping
panels, the source picker or the signpost to them. Everything the user could
have clicked to undo it was on the far side of the exception.
"""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_SCRIPT, open_data_view, pin_data_view

#: Any real fixation column: mapping it as `screen_id` on one report only is
#: what `multipart.validate_matching_parts` refuses.
BOGUS_SCREEN_COLUMN = "TRIAL_INDEX"


def _boot() -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.run()
    assert not at.exception
    return at


def _break_the_mapping(at: AppTest) -> AppTest:
    """Map `screen_id` on the fixations report and nowhere else."""
    at.selectbox(key="col_map_fix_screen_id").select(BOGUS_SCREEN_COLUMN).run()
    return at


def test_a_rejected_mapping_does_not_crash_the_app():
    at = _break_the_mapping(_boot())

    assert not at.exception, "a rejected mapping killed the whole app"


def test_a_rejected_mapping_says_what_is_wrong_and_where_to_fix_it():
    at = _break_the_mapping(_boot())

    # The Scanpath view can draw nothing, so it signposts the Data page (the
    # mapping panels live there, hidden while another view is active).
    assert any("isn't set up yet" in info.value for info in at.info)

    at = open_data_view(at, timeout=180)
    said = " ".join(w.value for w in at.warning) + " ".join(e.value for e in at.error)
    assert "screen_id" in said, f"the failure was not explained: {said!r}"


def test_the_rejected_mapping_stays_editable_so_it_can_be_undone():
    at = _break_the_mapping(_boot())

    # The panel that made the mistake is still on the page, still holding it.
    assert at.selectbox(key="col_map_fix_screen_id").value == BOGUS_SCREEN_COLUMN

    at.selectbox(key="col_map_fix_screen_id").set_value(None).run()

    assert not at.exception
    assert not any("isn't set up yet" in info.value for info in at.info)


def test_resetting_the_column_mapping_recovers_a_wedged_dataset():
    """The escape hatch for "I don't know which field broke it"."""
    at = _break_the_mapping(_boot())
    at = open_data_view(at, timeout=180)

    reset = [b for b in at.button if b.key == "reset_column_mapping"]
    assert reset, "no way out but to edit the very mapping that wedged the app"
    reset[0].click().run(timeout=180)

    assert not at.exception
    assert at.selectbox(key="col_map_fix_screen_id").value is None


# --- the escape hatches that don't go through the 🗂️ Data page -----------------


def test_a_wedged_dataset_can_be_abandoned_without_visiting_the_data_page():
    """The signpost's second button: one click back to something that draws."""
    at = _break_the_mapping(_boot())
    assert any("isn't set up yet" in info.value for info in at.info)

    demo = [b for b in at.button if b.key == "offpage_load_demo"]
    assert demo, "the only way out was the page the user is being sent to"
    demo[0].click().run(timeout=180)

    assert not at.exception
    assert not any("isn't set up yet" in info.value for info in at.info)
    assert at.selectbox(key="col_map_fix_screen_id").value is None


def test_the_session_menu_keeps_its_escape_hatches_while_the_app_is_wedged(
    monkeypatch, tmp_path
):
    """The 💾 Session popover's controls survive `main`'s early return.

    They used to be written in the epilogue, which a dataset that cannot be
    drawn never reaches — so the menu someone opens when stuck showed its
    headings with nothing under them. The recovery cache has to be forced on:
    AppTest has no URL, so persistence reads as a hosted deployment and the
    panel correctly explains that nothing is stored instead of offering Forget.
    """
    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path))

    at = _break_the_mapping(_boot())

    keys = {b.key for b in at.button}
    assert {"session_load_demo", "session_clear_cache"} <= keys
    # …including the recovery cache's own Forget, which lives past that return.
    assert any("Clear recovery cache" in b.label for b in at.button)


def test_clearing_the_computation_cache_leaves_the_app_running():
    at = _boot()
    clear = [b for b in at.button if b.key == "session_clear_cache"]
    assert clear

    clear[0].click().run(timeout=180)

    assert not at.exception
    assert not at.error


# --- the upload wizard, which reaches the same pipeline -----------------------

#: A word table whose `page` column auto-detects as `screen_id`, against a
#: fixation table with no screen column at all — the same one-sided multipart
#: identity, arrived at without the user mapping anything.
_WIZARD_WORDS = pd.DataFrame(
    {
        "participant_id": ["r0"] * 3,
        "trial_id": ["t0"] * 3,
        "word_id": [0, 1, 2],
        "text": ["The", "cat", "sat"],
        "page": ["p1", "p1", "p1"],
        "x": [10.0, 60.0, 110.0],
        "y": [20.0, 20.0, 20.0],
        "width": [40.0, 40.0, 40.0],
        "height": [18.0, 18.0, 18.0],
    }
)
_WIZARD_FIXATIONS = pd.DataFrame(
    {
        "participant_id": ["r0"] * 3,
        "trial_id": ["t0"] * 3,
        "duration_ms": [200.0, 180.0, 240.0],
        "x": [15.0, 65.0, 115.0],
        "y": [24.0, 24.0, 24.0],
    }
)


@pytest.fixture
def one_sided_upload(monkeypatch):
    """Feed the wizard's per-table upload seam (AppTest can't drive uploaders)."""
    from scanpath_studio import app

    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {
            "col_map_words": _WIZARD_WORDS,
            "col_map_fix": _WIZARD_FIXATIONS,
        }.get(kw["state_prefix"], pd.DataFrame()),
    )


def _upload_apptest(*, wizard_active: bool) -> AppTest:
    from scanpath_studio import app

    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.session_state["setup_complete"] = not wizard_active
    pin_data_view(at)
    return at.run(timeout=180)


def test_the_open_wizard_survives_an_upload_the_pipeline_rejects(one_sided_upload):
    at = _upload_apptest(wizard_active=True)

    assert not at.exception, "a rejected upload killed the whole app"
    assert any("screen_id" in e.value for e in at.error)
    # …and it cannot be added as a dataset in that state.
    finalize = [b for b in at.button if b.key == "wizard_finalize"]
    assert finalize and finalize[0].disabled


def test_a_collapsed_wizard_upload_recovers_like_any_other_bad_mapping(
    one_sided_upload,
):
    at = _upload_apptest(wizard_active=False)

    assert not at.exception
    assert any("screen_id" in e.value for e in at.error)


def test_the_multipleye_preset_reports_a_rejected_load_instead_of_dying(monkeypatch):
    """The format preset skips the mapping steps but runs the same pipeline.

    Fault-injected rather than contrived from files: which MultiplEYE upload
    combinations `multipart` still rejects is a moving target (the loader drops
    screens without boxes precisely to avoid one), and what is under test here
    is the guard, not today's list of rejections.
    """
    # The one MultiplEYE-shaped upload fixture in the suite; sharing it beats a
    # second hand-built copy of the filename conventions the loader parses.
    from scanpath_studio import app
    from tests.test_apptest import _mpe_upload_frames

    scan, aoi = _mpe_upload_frames()
    frames = {"mpe_fix": scan, "mpe_aoi": aoi}
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
    )

    def _rejected(*_args, **_kwargs):
        raise ValueError("Multipart reports contain orphan screens: no words for x")

    monkeypatch.setattr(app, "_normalize_pair", _rejected)

    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.session_state["_show_upload_wizard"] = True
    at.session_state["setup_complete"] = False
    at.session_state["wizard_dataset_format"] = "MultiplEYE"
    pin_data_view(at)
    at.run(timeout=180)

    assert not at.exception
    assert any("orphan screens" in e.value for e in at.error)
    assert "_wizard_finalize_payload" not in at.session_state
