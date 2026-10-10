"""#422 — a picked word-box fill color shows, and survives closing the popover.

Two causes, both reproduced in a browser: the fill is drawn at 0.05 opacity by
default, so a picked color barely tinted the boxes; and a pick dismissed by a
click on the page was dropped, because the Word boxes popover closed (and
unmounted the picker) before the picker sent its value.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

FILL = "global_word_box_fill_color"
OPACITY = "global_word_box_fill_opacity"


def _app(opacity: float | None = None):
    at = AppTest.from_file(str(APP_SCRIPT), default_timeout=180)
    at.session_state["global_show_words"] = True
    if opacity is not None:
        at.session_state[OPACITY] = opacity
    at.run()
    assert not at.exception, at.exception
    return at


@pytest.mark.timeout(180)
def test_picking_a_fill_over_a_faint_one_makes_it_show(monkeypatch):
    from scanpath_studio import controls, tabs
    from scanpath_studio.constants import WORD_BOX_FILL_OPACITY

    built: list = []
    real = tabs.make_scanpath_figure

    def spy(words, fixations, *, settings=None, **kwargs):
        built.append((settings.word_box_fill_color, settings.word_box_fill_opacity))
        return real(words, fixations, settings=settings, **kwargs)

    monkeypatch.setattr(tabs, "make_scanpath_figure", spy)
    at = _app()
    assert at.session_state[OPACITY] == WORD_BOX_FILL_OPACITY
    assert WORD_BOX_FILL_OPACITY < controls._FILL_SHOWS_FROM
    at.color_picker(key=FILL).pick("#ff0000").run()
    assert not at.exception, at.exception
    assert at.session_state[FILL] == "#ff0000"
    assert at.session_state[OPACITY] == controls._FILL_PICKED_OPACITY
    # The figure is redrawn in the picked color, at an opacity that shows it.
    assert built[-1] == ("#ff0000", controls._FILL_PICKED_OPACITY)


@pytest.mark.timeout(180)
def test_a_fill_opacity_the_user_chose_is_kept():
    at = _app(opacity=0.5)
    at.color_picker(key=FILL).pick("#0000ff").run()
    assert not at.exception, at.exception
    assert at.session_state[OPACITY] == 0.5
    # …and a deliberate 0 (outlines only) is raised only by a color pick,
    # never by anything else on the rail.
    at = _app(opacity=0.0)
    at.run()
    assert at.session_state[OPACITY] == 0.0


def test_the_fill_help_says_a_pick_raises_the_opacity():
    from scanpath_studio import controls

    assert "raises" in controls._FILL_PICK_NOTE
    assert f"{controls._FILL_PICKED_OPACITY:.2f}" in controls._FILL_PICK_NOTE


def test_the_commit_script_installs_once_into_the_parent_document():
    from scanpath_studio import color_picker_commit as commit

    script = commit.commit_script()
    assert script.startswith("<script>") and script.endswith("</script>")
    assert "window.parent.document" in script
    assert f"getElementById({json.dumps(commit.SCRIPT_ID)})" in script
    # It sends an open picker's value on the press that starts a click
    # outside it, through the picker's own swatch.
    assert "pointerdown" in script and "swatch.click()" in script
    assert json.dumps(json.dumps(commit.OPEN_SWATCH_SELECTOR))[1:-1] in script


def test_app_mounts_the_commit_script():
    source = (Path(__file__).parents[1] / "scanpath_studio" / "app.py").read_text(
        encoding="utf-8"
    )
    assert "render_color_picker_commit()" in source
