"""UX-179: the saved-design library's own file — My designs → Export / Import.

It replaced the 💾 Session backup's ``design_presets`` section, which was the
only portable copy of the library.
"""

from __future__ import annotations

import json

import pytest

from scanpath_studio import controls

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def test_the_file_round_trips_a_library():
    library = {
        "Paper figure": {"global_show_fix": True, "global_font_family": "Courier New"},
        "Heatmap only": {"global_show_heatmap": True},
    }
    text = controls.designs_to_json(library)
    data = json.loads(text)
    assert data["kind"] == controls.DESIGNS_FILE_KIND
    assert controls.designs_from_json(text) == library


def test_only_plot_settings_come_in():
    """A design holds its own keys and nothing else — `_is_design_key`, the
    rule `_apply_view_preset` applies — so a hand-edited file cannot seed other
    state.
    """
    text = json.dumps(
        {
            "kind": controls.DESIGNS_FILE_KIND,
            "designs": {
                "  Mine  ": {
                    "global_show_fix": False,
                    "global_image_upload": "x",
                    "data_source_choice": "Upload",
                },
                "": {"global_show_fix": True},
                "Not a dict": [1, 2],
            },
        }
    )
    assert controls.designs_from_json(text) == {"Mine": {"global_show_fix": False}}


def test_compare_settings_come_in_with_the_design():
    """VIZ-47 widened a design past `global_*` (Compare, fixation windows,
    replay speed); an imported one must keep those too."""
    extra = next(iter(sorted(controls._DESIGN_EXTRA_KEYS)))
    text = json.dumps(
        {
            "kind": controls.DESIGNS_FILE_KIND,
            "designs": {"Mine": {extra: "value", "global_show_fix": True}},
        }
    )
    assert controls.designs_from_json(text) == {
        "Mine": {extra: "value", "global_show_fix": True}
    }


def test_a_built_in_name_is_not_shadowed():
    name = next(iter(controls._VIEW_PRESETS))
    text = json.dumps(
        {"kind": controls.DESIGNS_FILE_KIND, "designs": {name: {"global_x": 1}}}
    )
    assert list(controls.designs_from_json(text)) == [f"{name} (mine)"]


@pytest.mark.parametrize(
    "payload",
    [
        {"annotations": []},
        {"kind": "something_else", "designs": {}},
        {"kind": controls.DESIGNS_FILE_KIND},
        [],
    ],
)
def test_anything_else_is_refused(payload):
    with pytest.raises(ValueError):
        controls.designs_from_json(json.dumps(payload))


def _import_app():
    import streamlit as st

    from scanpath_studio import controls

    class _Upload:
        def __init__(self, text: str) -> None:
            self._data = text.encode("utf-8")

        def getvalue(self) -> bytes:
            return self._data

    st.session_state[controls.DESIGN_PRESETS_KEY] = {
        "Kept": {"global_show_fix": True},
        "Replaced": {"global_show_fix": True},
    }
    st.session_state[controls._DESIGN_IMPORT_KEY] = _Upload(st.session_state["_text"])
    controls._import_designs()


def test_import_merges_and_replaces_by_name():
    text = controls.designs_to_json(
        {"Replaced": {"global_show_fix": False}, "New": {"global_show_heatmap": True}}
    )
    at = AppTest.from_function(_import_app)
    at.session_state["_text"] = text
    at.run()
    assert not at.exception, at.exception
    library = at.session_state[controls.DESIGN_PRESETS_KEY]
    assert library == {
        "Kept": {"global_show_fix": True},
        "Replaced": {"global_show_fix": False},
        "New": {"global_show_heatmap": True},
    }
    assert at.session_state[controls._DESIGN_IMPORT_NOTE_KEY] == "Imported 2 designs."


def test_a_bad_file_says_so_and_changes_nothing():
    at = AppTest.from_function(_import_app)
    at.session_state["_text"] = '{"annotations": []}'
    at.run()
    assert not at.exception, at.exception
    assert set(at.session_state[controls.DESIGN_PRESETS_KEY]) == {"Kept", "Replaced"}
    assert at.session_state[controls._DESIGN_IMPORT_NOTE_KEY].startswith("error:")
