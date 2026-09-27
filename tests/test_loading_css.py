"""UX-165: the loading states' CSS, and the retired spinner banner."""

from __future__ import annotations

import re

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


def test_reduced_motion_stops_the_bar_sliding_and_filling():
    """Under ``prefers-reduced-motion`` nothing moves: the sliding bar's
    animation is off, and the filling bar's width jumps instead of easing."""
    block = CSS[CSS.index("@media (prefers-reduced-motion: reduce)") :]
    block = block[: block.index("\n    }\n") + 6]
    assert ".sps-bar-indeterminate > span" in block
    assert re.search(r"\.sps-bar > span \{ transition: none !important; \}", block)


def test_the_step_the_live_region_speaks_is_not_drawn_twice():
    """The card's live region carries the current step for a screen reader
    (`loading.head_html`); the detail line or step list already shows it, so
    in the head it is visually hidden."""
    rule = re.search(r"\.sps-sr-only \{([^}]*)\}", CSS)
    assert rule is not None
    assert "clip-path: inset(50%)" in rule.group(1)
    assert "position: absolute" in rule.group(1)


def test_the_data_view_hides_what_the_previous_view_left():
    assert (
        ".st-key-sps_view:has(.sps-view-hidden) > :not(:first-child) "
        "{ display: none !important; }"
    ) in CSS


def test_a_card_takes_no_space_until_it_shows():
    """UX-166: a card opens hidden — the page card on every run — so until it is
    revealed its slot is out of the layout; otherwise each rerun pushes the view
    down by the card's margins and back. A size box is the exception: holding
    the area is what a region card's box is for."""
    assert (
        '[data-testid="stLayoutWrapper"]:has(> [class*="st-key-sps_card_"])'
        ":not(:has(.sps-reveal)):not(:has(.sps-size-box)) "
        "{ display: none !important; }"
    ) in CSS
    assert (
        ".st-key-sps_card_page:has(.sps-reveal) > "
        '[data-testid="stLayoutWrapper"]:has(> .st-key-sps_cardbody_page)'
    ) in CSS
    assert (
        ".st-key-sps_card_page > "
        '[data-testid="stLayoutWrapper"]:has(> .st-key-sps_cardbody_page) {'
    ) not in CSS


def test_a_card_sits_centred_over_the_figure_it_stands_in_for():
    """UX-167: Streamlit stretches a block's wrapper to the full width, so the
    body's wrapper takes a width of its own — or no `justify-self` places it.
    Every width resolves top-down from the column (the size box caps its card
    at the figure's width): a track sized by its content would overflow a
    narrow column or collapse to the card. A card with no size box sits where
    it is written; the page card keeps its own placement."""
    assert (
        '[class*="st-key-sps_card_"]:not(.st-key-sps_card_page) {\n'
        "        display: grid !important;\n"
        "        grid-template-columns: minmax(0, 1fr);"
    ) in CSS
    assert "fit-content" not in CSS[CSS.index("UX-165 · loading states") :]
    wrapper = (
        '[class*="st-key-sps_card_"] > [data-testid="stLayoutWrapper"]'
        ':has(> [class*="st-key-sps_cardbody_"]) {'
    )
    rule = CSS[CSS.index(wrapper) :].split("}", 1)[0]
    assert "width: min(24rem, 100%) !important;" in rule
    assert "justify-self: center;" in rule
    assert (
        '[class*="st-key-sps_card_"]:not(.st-key-sps_card_page)'
        ":not(:has(.sps-size-box)) > "
        '[data-testid="stLayoutWrapper"]:has(> [class*="st-key-sps_cardbody_"]) '
        "{ justify-self: start; }"
    ) in CSS
    assert ".sps-size-box { width: 100%; pointer-events: none; }" in CSS
    body = (
        '[class*="st-key-sps_card_"]:has(.sps-reveal) [class*="st-key-sps_cardbody_"] {'
    )
    assert "width: 100%;" in CSS[CSS.index(body) :].split("}", 1)[0]


def test_the_page_card_centres_on_the_corpus_and_data_views():
    """Every card's body wrapper has a width of its own, so the page card's
    `justify-self: center` places it — on the Scanpath view its own rule puts
    it over the plot column instead."""
    page = (
        ".st-key-sps_card_page:has(.sps-reveal) > "
        '[data-testid="stLayoutWrapper"]:has(> .st-key-sps_cardbody_page) {'
    )
    rule = CSS[CSS.index(page) :].split("}", 1)[0]
    assert "justify-self: center;" in rule
    wrapper = (
        '[class*="st-key-sps_card_"] > [data-testid="stLayoutWrapper"]'
        ':has(> [class*="st-key-sps_cardbody_"]) {'
    )
    assert (
        "width: min(24rem, 100%) !important;"
        in CSS[CSS.index(wrapper) :].split("}", 1)[0]
    )


def _nested_has(css: str) -> list[str]:
    """Every selector in ``css`` with a `:has()` inside another `:has()`."""
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    found = []
    for selector in re.findall(r"([^{}]+)\{", rules):
        inside: list[bool] = []  # one entry per open paren: is it a :has(?
        i = 0
        while i < len(selector):
            if selector.startswith(":has(", i):
                if any(inside):
                    found.append(selector.strip())
                    break
                inside.append(True)
                i += len(":has(")
                continue
            if selector[i] == "(":
                inside.append(False)
            elif selector[i] == ")" and inside:
                inside.pop()
            i += 1
    return found


def test_no_rule_nests_has_inside_has():
    """A browser drops a rule whose `:has()` holds another `:has()` — the
    first cut of the rule above did, silently, so the check is on every rule."""
    assert _nested_has(CSS) == []


def test_the_nesting_check_catches_what_it_is_for():
    """The check above passing means something only if it can fail: the first
    cut's shape is flagged, the flat form and a `:has()` in a comment are not."""
    nested = '.w:has(> [class*="c_"]:not(:has(.sps-reveal))) { display: none; }'
    flat = '.w:has(> [class*="c_"]):not(:has(.sps-reveal)) { display: none; }'
    comment = "/* `:has()` may not nest inside `:has()` */ .x { color: red; }"
    assert _nested_has(nested) == [nested.split("{")[0].strip()]
    assert _nested_has(flat) == []
    assert _nested_has(comment) == []
