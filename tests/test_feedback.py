"""❓ Help → Send feedback: three GitHub routes and the details for a bug report."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from scanpath_studio import __version__, feedback, menu
from scanpath_studio.constants import CITATION

ROOT = Path(__file__).resolve().parents[1]


def test_every_route_opens_a_page_of_this_repository():
    for _key, _label, _icon, url, _purpose in feedback.ROUTES:
        assert url.startswith(CITATION["url"] + "/")


def test_issue_routes_name_templates_that_exist():
    """A template name GitHub can't find silently opens a blank issue."""
    for url in (CITATION["bug_report_url"], CITATION["feature_request_url"]):
        template = url.split("template=", 1)[1]
        assert (ROOT / ".github" / "ISSUE_TEMPLATE" / template).is_file()


def test_details_carry_the_version_and_where_the_app_runs():
    details = feedback.environment_details()
    assert f"Scanpath Studio {__version__}" in details
    assert "Running on: " in details
    assert "Python " in details and "Streamlit " in details


def test_help_entry_arms_the_dialog():
    assert menu._HELP_PAGES["help_feedback"][2] == "help-feedback"


def _dialog_script() -> None:
    from scanpath_studio import feedback

    feedback._arm_feedback()
    feedback.maybe_show_feedback()


def test_dialog_shows_the_three_routes_and_the_details():
    at = AppTest.from_function(_dialog_script).run()
    assert not at.exception
    urls = [button.proto.url for button in at.get("link_button")]
    assert urls == [url for *_rest, url, _purpose in feedback.ROUTES]
    assert at.code[0].value == feedback.environment_details()
