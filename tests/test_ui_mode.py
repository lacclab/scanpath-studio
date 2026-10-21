from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import session_keys as sk
from scanpath_studio import ui_mode
from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_DATA, _VIEW_SCANPATH
from tests.conftest import APP_SCRIPT, pin_view

SWITCH = "ui_mode_switch"


@pytest.mark.parametrize(
    ("param", "cookie", "expected"),
    [
        (None, None, "simple"),
        (None, "advanced", "advanced"),
        ("advanced", "simple", "advanced"),
        ("SIMPLE", "advanced", "simple"),
        (" Advanced ", None, "advanced"),
        ("foo", "advanced", "advanced"),
        ("", None, "simple"),
        ("foo", "bar", "simple"),
    ],
)
def test_resolve_mode_precedence(param, cookie, expected):
    assert ui_mode.resolve_mode(param, cookie) == expected


@pytest.mark.parametrize("value", [None, 3, ["advanced"], b"advanced", object()])
def test_parse_mode_never_raises_on_a_non_string(value):
    assert ui_mode.parse_mode(value) is None


def test_seed_mode_reads_the_link_then_the_cookie():
    assert ui_mode.seed_mode({}, {sk.PARAM_UI: "advanced"}, {}) == "advanced"
    cookies = {sk.UI_MODE_COOKIE: "advanced"}
    assert ui_mode.seed_mode({}, {}, cookies) == "advanced"
    assert ui_mode.seed_mode({}, {}, {}) == "simple"


def test_seed_mode_writes_the_session_key():
    session: dict = {}
    ui_mode.seed_mode(session, {sk.PARAM_UI: "advanced"}, {})
    assert session[sk.UI_MODE] == "advanced"


def test_seed_mode_keeps_an_existing_session_choice():
    session = {sk.UI_MODE: "advanced"}
    assert ui_mode.seed_mode(session, {sk.PARAM_UI: "simple"}, {}) == "advanced"


def test_cookie_script_sets_a_year_long_cookie():
    script = ui_mode.cookie_script("advanced")
    assert "sps_ui_mode=advanced" in script
    assert "max-age=31536000" in script and "path=/" in script
    assert "SameSite=Lax" in script


def test_cookie_script_only_embeds_a_valid_mode():
    script = ui_mode.cookie_script('x"; alert(1); "')
    assert "sps_ui_mode=simple" in script and "alert" not in script


def test_seed_mode_replaces_a_junk_session_value():
    session = {sk.UI_MODE: "junk"}
    assert ui_mode.seed_mode(session, {sk.PARAM_UI: "advanced"}, {}) == "advanced"
    assert session[sk.UI_MODE] == "advanced"


def test_ui_param_alone_is_not_a_link():
    assert not ui_mode.has_link_params({"ui": "simple"})
    assert ui_mode.has_link_params({"ui": "simple", "trial": "3"})
    assert not ui_mode.has_link_params({})


def test_mode_css_hides_the_other_mode():
    simple = ui_mode.mode_css("simple")
    assert "st-key-adv_only_" in simple and "st-key-simple_only_" not in simple
    advanced = ui_mode.mode_css("advanced")
    assert "st-key-simple_only_" in advanced and "st-key-adv_only_" not in advanced
    assert "display: none !important" in simple


def _boot(view: str = _VIEW_SCANPATH, mode: str | None = "simple") -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    if mode is None:
        del at.query_params["ui"]  # the conftest pins ?ui=advanced
    else:
        at.query_params["ui"] = mode
    pin_view(at, view)
    at.run()
    assert not at.exception
    return at


def test_fresh_session_is_simple():
    at = _boot(mode=None)
    assert at.session_state["ui_mode"] == "simple"
    assert at.segmented_control(key=SWITCH).value == "simple"


def test_switch_flips_mode_and_keeps_every_value():
    at = _boot()
    assert at.session_state["ui_mode"] == "simple"
    prefixes = ("global_", "single_", "filter_")

    def snapshot() -> dict:
        return {
            k: at.session_state[k] for k in at.session_state if k.startswith(prefixes)
        }

    before = snapshot()
    assert before
    at.segmented_control(key=SWITCH).set_value("advanced").run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "advanced"
    assert at.session_state["_ui_mode_chosen"] is True
    assert snapshot() == before
    at.segmented_control(key=SWITCH).set_value("simple").run()
    assert at.session_state["ui_mode"] == "simple"


def test_ui_param_does_not_write_the_cookie():
    at = _boot(mode="advanced")
    assert at.session_state["ui_mode"] == "advanced"
    assert "_ui_mode_chosen" not in at.session_state


@pytest.mark.parametrize("view", [_VIEW_SCANPATH, _VIEW_CORPUS, _VIEW_DATA])
def test_switch_shows_on_every_view(view):
    at = _boot(view)
    assert at.segmented_control(key=SWITCH).value == "simple"
