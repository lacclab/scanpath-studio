"""UX-39: the title's triple-click easter egg.

It is browser-only, so what a test can pin is the *contract* around the script:
the selector it binds to still matches the header the app renders, the trigger
stays a triple-click, and the sessions that must not be interrupted (embeds, a
running tour or tutorial) get no script at all.
"""

from __future__ import annotations

import json

from scanpath_studio import easter_egg


def test_script_binds_the_triple_click_on_the_header_title() -> None:
    script = easter_egg.egg_script()
    assert script.startswith("<script>") and script.endswith("</script>")
    # The trigger and its target — the two things a refactor could quietly break.
    assert json.dumps(easter_egg.TITLE_SELECTOR) in script
    assert "ev.detail < 3" in script
    assert 'addEventListener("click"' in script


def test_script_is_inert_and_self_cleaning() -> None:
    """The three properties that keep an easter egg from becoming a bug."""
    script = easter_egg.egg_script()
    # Can never swallow a click meant for the Corpus Analysis button beside it.
    assert "pointer-events: none" in script
    # A rerun destroys the iframe mid-animation; leftovers must be dropped.
    assert '.querySelectorAll(".sps-egg").forEach' in script
    # And the eyes remove themselves rather than sitting there.
    assert "teardown" in script and "wrap.remove()" in script


def test_selector_matches_the_header_container_key() -> None:
    """`app._render_about_panel` keys the header container; the selector follows it."""
    from pathlib import Path

    source = Path(easter_egg.__file__).with_name("app.py").read_text()
    assert 'st.container(key="about_header")' in source
    assert easter_egg.TITLE_SELECTOR == ".st-key-about_header h1"


def test_embeds_get_no_egg() -> None:
    assert easter_egg.egg_suppressed({"embed": "true"}, {})
    assert easter_egg.egg_suppressed({"embed": "1"}, {})
    assert not easter_egg.egg_suppressed({"embed": "false"}, {})
    assert not easter_egg.egg_suppressed({}, {})


def test_a_running_tour_or_tutorial_gets_no_egg() -> None:
    assert easter_egg.egg_suppressed({}, {"tour_mode": "spotlight"})
    assert easter_egg.egg_suppressed({}, {"tour_mode": "wizard"})
    assert easter_egg.egg_suppressed({}, {"tutorial_active": "first-figure"})
    # A finished tour clears the mode and the egg comes back.
    assert not easter_egg.egg_suppressed({}, {"tour_mode": None})


def test_suppression_tolerates_a_missing_session_state() -> None:
    assert not easter_egg.egg_suppressed({})
