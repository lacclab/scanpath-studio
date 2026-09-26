"""BUG-89: one click on a popover's ▾ opens it, however long the popover takes to draw.

Streamlit swaps the trigger's chevron glyph (``expand_more`` → ``expand_less``)
when a popover opens, detaching the span the pointer hit. Its outside-click
handler then receives that same opening click on ``document`` and skips it only
inside a 50 ms window; past that, the detached target reads as "outside" and
the popover closes itself right after opening. The fix makes the chevron
transparent to the pointer, so the click's target is an element that survives
the re-render.

The failure needs a browser (AppTest renders no frontend), so what is pinned
here is the rule that carries the fix. It was verified in the browser by
stalling the click 70 ms after React handled it: the popover closed without the
rule and stayed open with it.
"""

from __future__ import annotations

import re

from scanpath_studio.styles import get_app_css


def _css() -> str:
    return re.sub(r"\s+", " ", get_app_css())


def test_the_popover_chevron_is_not_a_click_target():
    css = _css()
    rule = (
        '[data-testid="stPopoverButton"] [aria-hidden="true"], '
        '[data-testid="stPopoverButton"] [aria-hidden="true"] * { '
        "pointer-events: none; }"
    )
    assert rule in css


def test_only_the_chevron_is_made_transparent():
    # The trigger's label and icon keep their nodes on open, and a label may
    # carry the native `title=` that shows a truncated name in full, so the rule
    # must not reach every descendant of the button.
    css = _css()
    assert '[data-testid="stPopoverButton"] * {' not in css
    assert '[data-testid="stPopoverButton"] *{' not in css
