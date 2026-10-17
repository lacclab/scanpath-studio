"""The About heading's triple-click easter egg.

It is browser-only, so what a test can pin is the *contract* around the script:
the selector it binds to still finds the About dialog's heading, the trigger
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


def test_the_about_dialog_draws_the_script_the_selector_finds() -> None:
    """The selector finds the About dialog by the container the script is drawn
    in, so the dialog must draw it — and only About: every dialog has an ``h2``."""
    import inspect

    from scanpath_studio import app

    assert "render_easter_egg()" in inspect.getsource(app._about_dialog)
    assert f".st-key-{easter_egg.EGG_KEY}" in easter_egg.TITLE_SELECTOR
    assert easter_egg.TITLE_SELECTOR.startswith('[data-testid="stDialog"]')
    assert easter_egg.TITLE_SELECTOR.endswith(" h2")
    source = inspect.getsource(easter_egg.render_easter_egg)
    assert "st.container(key=EGG_KEY)" in source


def test_the_eyes_sit_above_the_dialog() -> None:
    """Streamlit draws its dialog at z-index 1000059 (measured in the browser);
    eyes under it would pop up invisible behind the heading they belong to."""
    assert easter_egg._Z_INDEX > 1000059
    assert f"z-index: {easter_egg._Z_INDEX}" in easter_egg.egg_script()


def test_an_orphaned_pair_still_fades() -> None:
    """Closing the dialog kills the script mid-animation, so the fade must not
    depend on it: it is a CSS animation delayed by the eyes' lifetime."""
    script = easter_egg.egg_script()
    assert (
        f"sps-egg-away {easter_egg._FADE_MS}ms ease-in "
        f"{easter_egg._LIFETIME_MS}ms forwards"
    ) in script


def test_a_remount_replaces_the_click_handler() -> None:
    """A rerun of the dialog keeps its heading but kills the old script, whose
    handler then never runs: the new mount must replace it, not skip binding."""
    script = easter_egg.egg_script()
    assert 'title.removeEventListener("click", title.__spsEgg)' in script
    assert "spsEggWired" not in script


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
