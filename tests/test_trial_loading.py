"""What a slow connection shows: a trial change's card over the figure, the
guide card clipped until its stylesheet applies, and a compressed WebSocket.

The card is drawn by the page itself (`loading.trial_loading_script`), so
``AppTest``, which runs no frontend, sees only its wiring; the browser smoke test
(`tests/test_browser_smoke.py`) clicks ▶ and watches it come and go.
"""

from __future__ import annotations

import inspect
import json
import re
import tomllib
from pathlib import Path
from types import SimpleNamespace

from scanpath_studio import app, loading, tabs, tour, utils
from scanpath_studio.styles import get_app_css

ROOT = Path(__file__).resolve().parents[1]


def _config() -> dict:
    script = loading.trial_loading_script()
    match = re.search(r"var CFG = (\{.*?\});\n", script)
    assert match is not None
    return json.loads(match.group(1))


def test_every_page_installs_the_trial_card_once():
    assert "loading.trial_loading_script()" in inspect.getsource(app.configure_page)
    script = loading.trial_loading_script()
    # Into the Streamlit page's own head, once per page load.
    assert "host.__spsTrialLoadingInstalled" in script
    assert "host.document.head.appendChild" in script


def test_the_card_waits_the_delay_every_card_waits():
    assert _config()["delayMs"] == round(loading.DELAY_S * 1000)


def test_the_card_is_the_one_every_other_card_draws():
    card = _config()["card"]
    assert 'class="sps-card-head"' in card and 'class="sps-ring"' in card
    assert f"{loading.TRIAL_LOADING_TITLE}…" in card
    # Its live region says it once, for a screen reader.
    assert 'role="status"' in card
    assert "sps-bar-indeterminate" in card


def test_no_closing_tag_can_end_the_frames_script_early():
    script = loading.trial_loading_script()
    assert script.count("</script>") == 1
    assert script.rstrip().endswith("</script>")


def test_the_card_is_raised_by_the_trial_controls_and_nothing_else():
    config = _config()
    assert config["steps"] == list(loading.TRIAL_STEP_KEYS)
    assert config["pickers"] == list(loading.TRIAL_PICKER_KEYS)
    assert config["stage"] == loading.PLOT_STAGE_SELECTOR == ".st-key-tour_grp_plot"
    # B's own ◀ ▶ and picker carry these keys (A's are checked on the running app
    # in test_apptest).
    source = inspect.getsource(tabs)
    assert 'key="single_compare_prev"' in source
    assert 'key="single_compare_next"' in source
    assert utils.COMPARE_TRIAL_KEY in loading.TRIAL_PICKER_KEYS


def test_a_figure_tells_the_page_when_it_has_drawn():
    html, _ = tabs._true_scale_html(
        '<div id="truescale-k"></div>',
        key="k",
        width=100,
        height=50,
        max_height=None,
        zoomable=True,
    )
    assert f'"{loading.PLOT_DRAWN_EVENT}"' in html
    assert "detail: window.frameElement" in html
    # After its first draw, where the placeholder goes.
    drop = html.index("function dropSkeleton()")
    assert html.index("gd._fullLayout", drop) < html.index(
        loading.PLOT_DRAWN_EVENT, drop
    )
    assert _config()["drawnEvent"] == loading.PLOT_DRAWN_EVENT


def test_the_card_is_styled_like_the_others_and_moves_for_no_one():
    css = get_app_css()
    rule = re.search(r"\.sps-trial-loading \{([^}]*)\}", css)
    assert rule is not None
    body = rule.group(1)
    assert "position: fixed" in body
    assert "pointer-events: none" in body
    # Nothing shows until the delay set where it is drawn has passed.
    assert "opacity: 0" in body
    assert "sps-trial-in" in body
    block = css[css.index("@media (prefers-reduced-motion: reduce)") :]
    assert ".sps-trial-loading::before" in block[: block.index("\n    }\n")]


def test_every_guide_card_is_clipped_until_its_stylesheet_applies(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tour.st, "container", lambda **kwargs: calls.append(kwargs) or SimpleNamespace()
    )
    tour._guide_card()
    assert calls == [{"key": "tour_card", "height": 1, "border": False}]
    source = inspect.getsource(tour)
    assert source.count('key="tour_card"') == 1  # `_guide_card`'s own
    assert source.count("with _guide_card():") == 3
    # The stylesheet that pins the card gives it its height back, and its slot.
    card_rule = tour._CARD_CSS[tour._CARD_CSS.index(".st-key-tour_card {") :]
    card_rule = card_rule[: card_rule.index("}")]
    for declaration in (
        "height: auto !important",
        "max-height: none !important",
        "overflow: visible !important",
    ):
        assert declaration in card_rule
    assert '[data-testid="stLayoutWrapper"]:has(> .st-key-tour_card)' in tour._CARD_CSS


def test_the_hosted_app_compresses_its_websocket():
    server = tomllib.loads(
        (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    )["server"]
    assert server["enableWebsocketCompression"] is True
