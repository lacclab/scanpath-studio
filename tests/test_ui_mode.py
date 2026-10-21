from __future__ import annotations

import pytest

from scanpath_studio import session_keys as sk
from scanpath_studio import ui_mode


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


def test_ui_param_alone_is_not_a_link():
    assert not ui_mode.has_link_params({"ui": "simple"})
    assert ui_mode.has_link_params({"ui": "simple", "trial": "3"})
    assert not ui_mode.has_link_params({})
