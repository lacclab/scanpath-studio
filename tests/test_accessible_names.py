"""What a screen reader announces for the app's controls.

Streamlit sets a widget's ``aria-label`` to its label string verbatim, so a
label written as ``**Select Trial**`` or ``:material/star: Favorite`` would be
read out with its markdown. These pin the source side; the parent-page script
that cleans the labels which must keep an icon is verified in a browser.
"""

from __future__ import annotations

from unittest import mock

import pytest

from scanpath_studio import app, html_embed, tabs
from scanpath_studio.fields import accessible_name


def test_accessible_name_drops_icons_and_bold():
    assert accessible_name(":material/star: Favorite (star this trial)") == (
        "Favorite (star this trial)"
    )
    assert accessible_name("**Select trial**  ·  by Fixations ↑") == (
        "Select trial · by Fixations ↑"
    )
    assert accessible_name("Plain") == "Plain"


@pytest.mark.timeout(180)
def test_the_main_pickers_have_plain_labels():
    """The dataset and trial pickers, and B's trial picker, as drawn: no
    markdown or icon for a screen reader to read out."""
    from streamlit.testing.v1 import AppTest

    from tests.conftest import APP_SCRIPT

    at = AppTest.from_file(APP_SCRIPT, default_timeout=150)
    at.session_state["tour_seen"] = True
    at.session_state["single_compare_toggle"] = True
    at.run()
    assert not at.exception, at.exception
    for key in ("data_source_picker", "single_trial_id", "single_compare_trial"):
        label = at.selectbox(key=key).label
        assert label and accessible_name(label) == label, (key, label)


def test_a_figure_summary_names_participant_text_and_count():
    assert tabs._scanpath_alt("l37_1129", "2_2_1_Adv", 178) == (
        "Scanpath of participant l37_1129 on text 2_2_1_Adv: 178 fixations"
    )
    assert tabs._scanpath_alt("p", "t", 1).endswith(": 1 fixation")


def test_only_a_visible_embed_takes_a_tab_stop():
    with mock.patch.object(html_embed.st, "iframe") as iframe:
        html_embed.embed_html_iframe("<p>x</p>", height=10)
        html_embed.embed_html_iframe("<p>x</p>", height=10, alt="Fig", focusable=True)
    assert [c.kwargs["tab_index"] for c in iframe.call_args_list] == [-1, 0]


def test_the_zoom_buttons_are_named():
    html, _ = tabs._true_scale_html(
        "", key="k", width=10, height=10, max_height=None, zoomable=True
    )
    for name in ("Zoom out", "Zoom in", "Reset zoom", "Fullscreen"):
        assert f'aria-label="{name}"' in html


def test_the_page_installs_the_name_cleaner():
    script = app._A11Y_NAMES_SCRIPT
    assert 'aria-hidden", "true"' in script
    assert ":material" in script
