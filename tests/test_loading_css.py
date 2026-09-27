"""UX-165: the loading states' CSS, and the retired spinner banner."""

from __future__ import annotations

from scanpath_studio.styles import get_app_css

CSS = get_app_css()


def test_the_pulsing_spinner_banner_is_gone():
    assert "sps-spinner-pulse" not in CSS
    assert "Emphasised loading spinner" not in CSS


def test_a_card_body_is_hidden_until_revealed():
    assert '[class*="st-key-sps_cardbody_"] { display: none !important; }' in CSS
    assert (
        '[class*="st-key-sps_card_"]:has(.sps-reveal) [class*="st-key-sps_cardbody_"]'
        in CSS
    )


def test_the_page_skeleton_hides_the_rest_of_the_view_area():
    assert ".st-key-sps_view:has(.sps-reveal-page) > :not(:first-child)" in CSS


def test_the_plot_area_is_a_stage_with_two_stacked_children():
    assert ".st-key-tour_grp_plot { display: grid !important;" in CSS
    assert ".st-key-tour_grp_plot > :nth-child(-n + 2) { grid-area: 1 / 1; }" in CSS


def test_spinners_hide_while_a_card_shows_and_motion_can_be_reduced():
    assert '.stApp:has(.sps-reveal) div[data-testid="stSpinner"]' in CSS
    assert "prefers-reduced-motion: reduce" in CSS


def test_the_data_view_hides_what_the_previous_view_left():
    assert (
        ".st-key-sps_view:has(.sps-view-hidden) > :not(:first-child) "
        "{ display: none !important; }"
    ) in CSS
