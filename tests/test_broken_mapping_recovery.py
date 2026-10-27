"""A column mapping the pipeline *rejects* must not take the whole app down.

`prepare_data` has a recovery path for a mapping that is merely
**incomplete** (a required field unmapped → `problems` → the raw tables plus the
still-editable Column mapping panels). A mapping that is complete but
**impossible** — the one-sided `screen_id` below, which `multipart` rejects
because two coordinate spaces must not be joined — must take it too: escaping
as a raw `ValueError` out of `main()` would kill the run *before* it rendered
the mapping panels, the source picker or the signpost to them, leaving
everything the user could click to undo it on the far side of the exception.
"""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio.constants import _VIEW_SCANPATH, ICONS
from tests.conftest import (
    APP_SCRIPT,
    edit_builtin_mapping,
    open_data_view,
    open_dataset_editor,
    pin_data_view,
    pin_view,
)

#: Any real fixation column: mapping it as `screen_id` on one report only is
#: what `multipart.validate_matching_parts` refuses.
BOGUS_SCREEN_COLUMN = "TRIAL_INDEX"


def _boot() -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.run()
    assert not at.exception
    return at


def _remap(at: AppTest, picks: dict) -> AppTest:
    """Save ``picks`` in ✏️ Edit dataset, then go back to the Scanpath view."""
    edit_builtin_mapping(at, picks, timeout=180)
    pin_view(at, _VIEW_SCANPATH)
    return at.run(timeout=180)


def _break_the_mapping(at: AppTest) -> AppTest:
    """Map `screen_id` on the fixations report and nowhere else."""
    return _remap(at, {"col_map_fix_screen_id": BOGUS_SCREEN_COLUMN})


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
    assert "Screen ID" in said, f"the failure was not explained: {said!r}"


def test_the_rejected_mapping_stays_editable_so_it_can_be_undone():
    at = _break_the_mapping(_boot())

    # The panel that made the mistake is still in ✏️ Edit dataset, still
    # holding it.
    open_dataset_editor(at, timeout=180)
    assert at.selectbox(key="col_map_fix_screen_id").value == BOGUS_SCREEN_COLUMN

    _remap(at, {"col_map_fix_screen_id": None})

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
    assert at.session_state["col_map_fix_screen_id"] is None


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
    assert at.session_state["col_map_fix_screen_id"] is None


def test_the_data_page_still_reports_the_cache_while_the_app_is_wedged(
    monkeypatch, tmp_path
):
    """*Saved on this computer* survives `main`'s early return.

    A dataset that cannot be drawn never reaches the epilogue, so each early
    return fills the section itself (`_finish_page`) — or the panel someone
    opens when stuck would show its heading with nothing under it. The
    recovery cache has to be forced on: nothing under AppTest reads as
    loopback, so persistence reads as a hosted deployment and the section says
    nothing is stored.
    """
    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path))

    at = _boot()
    at = _break_the_mapping(at)
    at = open_data_view(at, timeout=180)

    body = " ".join(str(m.value) for m in at.markdown)
    assert f"**Session folder:** `{tmp_path}`" in body


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
    assert any("Screen ID" in e.value for e in at.error)
    # …and it cannot be added as a dataset in that state.
    finalize = [b for b in at.button if b.key == "wizard_finalize"]
    assert finalize and finalize[0].disabled


def _upload_text_word_ids(
    monkeypatch, *, word_ids, fixation_ids, keep_xy: bool = False
) -> AppTest:
    """The wizard over an AOI-sequence pair: fixations with no X/Y (unless
    ``keep_xy``), placed by their Word ID alone."""
    from scanpath_studio import app

    words = _WIZARD_WORDS.drop(columns=["page"]).assign(word_id=list(word_ids))
    fixations = (
        _WIZARD_FIXATIONS if keep_xy else _WIZARD_FIXATIONS.drop(columns=["x", "y"])
    )
    fixations = fixations.assign(word_id=list(fixation_ids))
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {"col_map_words": words, "col_map_fix": fixations}.get(
            kw["state_prefix"], pd.DataFrame()
        ),
    )
    at = _upload_apptest(wizard_active=True)
    assert not at.exception
    return at


def test_text_word_ids_with_no_xy_place_the_fixations(monkeypatch):
    """Text Word IDs are keys: each fixation is placed at the box of the word
    with the same id, and the add goes ahead with nothing to warn about."""
    at = _upload_text_word_ids(
        monkeypatch, word_ids=("w0", "w1", "w2"), fixation_ids=("w2", "w0", "w1")
    )

    assert not [e.value for e in at.error]
    assert not [w.value for w in at.warning if "Word ID" in w.value]
    payload = at.session_state["_wizard_finalize_payload"]
    fixations = payload["fixations"]
    assert fixations["word_id"].tolist() == [3.0, 1.0, 2.0]
    assert fixations["x"].tolist() == [130.0, 30.0, 80.0]  # the boxes' centers
    # The ids themselves are kept, under the file's own column name.
    names = payload["column_names"]["fixations"]
    assert names["word_key"]["sources"] == ["word_id"]


def test_the_wizard_says_which_text_word_ids_name_no_word(monkeypatch):
    at = _upload_text_word_ids(
        monkeypatch, word_ids=("w0", "w1", "w2"), fixation_ids=("w0", "w1", "nope")
    )

    said = [w.value for w in at.warning if "no word of" in w.value]
    assert said, "a fixation whose text id names no word was dropped silently"
    assert "1 of 3 Word IDs names no word of its trial" in said[0]
    assert "'nope'" in said[0]


def test_text_word_ids_against_numeric_ones_block_the_add(monkeypatch):
    """A text id never names a numbered word, so with no X/Y nothing can be
    placed, and the add is blocked, saying why, directly above ✅ Add dataset."""
    at = _upload_text_word_ids(
        monkeypatch, word_ids=(0, 1, 2), fixation_ids=("w0", "w1", "w2")
    )

    said = [e.value for e in at.error if "Word IDs are text" in e.value]
    assert said, "text Word IDs loaded against numeric ones without a word"
    assert "Map the fixations' X and Y" in said[0]
    finalize = [b for b in at.button if b.key == "wizard_finalize"]
    assert finalize and finalize[0].disabled
    assert "_wizard_finalize_payload" not in at.session_state


def test_numeric_word_ids_against_text_ones_are_said_to_be_set_aside(monkeypatch):
    at = _upload_text_word_ids(
        monkeypatch, word_ids=("w0", "w1", "w2"), fixation_ids=(2, 0, 1), keep_xy=True
    )

    said = [w.value for w in at.warning if "Word IDs are numbers" in w.value]
    assert said and "matched to the word box it falls in" in said[0]


def test_a_blank_fixation_word_id_beside_text_ones_is_not_warned_about(monkeypatch):
    """The wizard warns on what the load did: a mapped fixations Word ID with
    no value in it set nothing aside, so there is nothing to say."""
    at = _upload_text_word_ids(
        monkeypatch,
        word_ids=("w0", "w1", "w2"),
        fixation_ids=(None, None, None),
        keep_xy=True,
    )

    assert at.selectbox(key="col_map_fix_word_id").value == "word_id"
    assert not [w.value for w in at.warning if "Word IDs are numbers" in w.value]


def test_a_collapsed_wizard_upload_recovers_like_any_other_bad_mapping(
    one_sided_upload,
):
    at = _upload_apptest(wizard_active=False)

    assert not at.exception
    assert any("Screen ID" in e.value for e in at.error)


# --- a complete mapping whose numbers don't parse -----------------------------


def test_the_wizard_names_a_numeric_column_that_did_not_parse(monkeypatch):
    """The mapping is complete and the load carries on — which is exactly why
    an unreadable coordinate column has to be said, above ✅ Add dataset."""
    from scanpath_studio import app

    fixations = _WIZARD_FIXATIONS.assign(x=["15px", "65px", "115px"])
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {"col_map_fix": fixations}.get(kw["state_prefix"], pd.DataFrame()),
    )
    at = _upload_apptest(wizard_active=True)

    assert not at.exception
    said = [w.value for w in at.warning if "aren't numbers" in w.value]
    assert said, "an unreadable X column loaded without a word"
    assert "`x`" in said[0] and "'15px'" in said[0]


def test_the_wizard_says_when_the_readers_do_not_line_up(monkeypatch):
    """The trial-id overlap check passing — both tables have `t0` — is not
    enough: no (participant, trial) pair is in both, so nothing has word boxes,
    and the wizard says so."""
    from scanpath_studio import app

    words = _WIZARD_WORDS.drop(columns=["page"]).assign(participant_id="r9")
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {"col_map_words": words, "col_map_fix": _WIZARD_FIXATIONS}.get(
            kw["state_prefix"], pd.DataFrame()
        ),
    )
    at = _upload_apptest(wizard_active=True)

    assert not at.exception
    assert any("share Trial IDs but no participant" in w.value for w in at.warning)


def test_a_words_table_that_joins_nothing_is_said_on_every_page(monkeypatch):
    """Words that load but join none of the fixations are reported on every
    page — not only the empty-*pool* case (all three frames empty) — rather
    than every trial drawing without its text, silently."""
    from scanpath_studio import app

    words = _WIZARD_WORDS.drop(columns=["page"]).assign(trial_id="another_trial")
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {"col_map_words": words, "col_map_fix": _WIZARD_FIXATIONS}.get(
            kw["state_prefix"], pd.DataFrame()
        ),
    )
    at = _upload_apptest(wizard_active=False)

    assert not at.exception
    assert any("No fixation has word boxes" in w.value for w in at.warning)


def test_a_fixations_only_dataset_is_not_warned_about(monkeypatch):
    """No words table was loaded at all — a legitimate dataset, not a failed join."""
    from scanpath_studio import app

    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {"col_map_fix": _WIZARD_FIXATIONS}.get(
            kw["state_prefix"], pd.DataFrame()
        ),
    )
    at = _upload_apptest(wizard_active=False)

    assert not at.exception
    assert not any("No fixation has word boxes" in w.value for w in at.warning)


def test_a_duration_mapped_to_words_is_named_at_the_field_and_above_add(
    monkeypatch,
):
    """A numeric field mapped to a column of words loads — every duration
    reads as 0 ms — so the warning names the field and the column to choose,
    and the field itself turns red with the same advice under it. The add is
    not blocked: the user may mean it."""
    from scanpath_studio import app

    fixations = _WIZARD_FIXATIONS.assign(duration_ms=["The", "cat", "sat"])
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {"col_map_fix": fixations}.get(kw["state_prefix"], pd.DataFrame()),
    )
    at = _upload_apptest(wizard_active=True)

    assert not at.exception
    said = [w.value for w in at.warning if "aren't numbers" in w.value]
    assert said, "a duration mapped to words loaded without a word"
    assert said[0].startswith(
        "Fixations: **Duration (ms)** is mapped to "
        "`duration_ms`, but 3 of its 3 values aren't numbers"
    )
    assert said[0].endswith("Choose the column that holds fixation durations.")
    at_field = [
        c.value for c in at.caption if "3 of 3 values aren't numbers" in c.value
    ]
    assert [v.removeprefix(ICONS["warning"]).strip() for v in at_field] == [
        "3 of 3 values aren't numbers (e.g. 'The', 'cat', "
        "'sat'). Choose the column that holds fixation durations."
    ]
    tint = " ".join(m.value for m in at.markdown if "<style>" in str(m.value))
    assert ".st-key-col_map_fix_duration_cell" in tint
    assert not any(
        "aren't numbers" in p for p in at.session_state["_wizard_problems_last"]
    )


def test_out_of_range_values_are_said_above_add(monkeypatch):
    from scanpath_studio import app

    fixations = _WIZARD_FIXATIONS.assign(
        duration_ms=[-50.0, 1e20, 200.0], y=[24.0, -1e300, float("inf")]
    )
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {"col_map_fix": fixations}.get(kw["state_prefix"], pd.DataFrame()),
    )
    at = _upload_apptest(wizard_active=True)

    assert not at.exception
    said = " ".join(w.value for w in at.warning)
    assert "1 value is negative and 1 is longer than an hour" in said
    assert "1 value is infinite and 1 is too far off the screen to draw" in said


def test_the_scanpath_view_says_when_the_data_checks_fail_badly():
    """Duration mapped to the word labels: every fixation reads as 0 ms and
    the figure still draws. The Scanpath view says so and links the checks."""
    at = _boot()
    assert not any("fails the data checks" in w.value for w in at.warning)

    at = _remap(at, {"col_map_fix_duration": "CURRENT_FIX_INTEREST_AREA_LABEL"})

    assert not at.exception
    (notice,) = [w.value for w in at.warning if "fails the data checks" in w.value]
    assert "**Fixations lasting 0 ms or less**: 3,199 of 3,209 fixation rows." in (
        notice
    )
    (open_checks,) = [b for b in at.button if b.key == "data_health_notice_open"]
    open_checks.click().run(timeout=180)
    assert not at.exception
    assert any("Data checks" in c.value for c in at.caption)
