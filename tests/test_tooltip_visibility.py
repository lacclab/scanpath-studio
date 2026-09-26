"""BUG-86: a `help=` tooltip shows only while its trigger is hovered or keyboard-focused.

Streamlit 1.64's tooltip trigger keeps the panel open for as long as focus is
inside it, whatever the pointer does — so clicking any button or popover that
has `help=` left its tooltip floating over the page after the pointer moved on.
The fix is CSS in `styles.get_app_css` that hides the panel unless a trigger is
`:hover` or holds `:focus-visible`, the browser's own bookkeeping.

The CSS names Streamlit's frontend test ids, so the second test reads the
installed Streamlit bundle for them: BUG-48's JavaScript sweeper went dead
without a single failing test when an upgrade dropped the Base Web
`data-baseweb="tooltip"` layer it looked for, and this is the guard against the
same silent break.
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit

from scanpath_studio import app
from scanpath_studio.styles import get_app_css

TRIGGERS = ("stTooltipHoverTarget", "stTooltipErrorHoverTarget")
PANELS = ("stTooltipContent", "stTooltipErrorContent")


def _hide_rule(css: str) -> tuple[str, str]:
    """The selector and body of the rule that hides the tooltip panels."""
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "visibility: hidden" in body and all(p in selector for p in PANELS):
            return selector, body
    raise AssertionError("no rule hides the Streamlit tooltip panels")


def test_panel_hidden_unless_a_trigger_is_hovered_or_keyboard_focused() -> None:
    selector, _ = _hide_rule(get_app_css())
    condition = selector.split(":not(:has(", 1)[1]
    for trigger in TRIGGERS:
        assert f'[data-testid="{trigger}"]:hover' in condition
        # Keyboard focus keeps a tooltip up; focus left by a click must not.
        assert f'[data-testid="{trigger}"] :focus-visible' in condition
    assert ":focus-within" not in condition
    assert ":focus," not in condition


def test_streamlit_bundle_still_uses_the_tooltip_test_ids() -> None:
    js = Path(streamlit.__file__).parent / "static" / "static" / "js"
    bundle = "".join(
        text
        for text in (path.read_text(errors="ignore") for path in js.glob("*.js"))
        if "stTooltip" in text
    )
    for test_id in (*TRIGGERS, *PANELS):
        assert f"`{test_id}`" in bundle, (
            f"Streamlit {streamlit.__version__} no longer names {test_id!r}; "
            "the BUG-86 rule in styles.get_app_css hides nothing until it is "
            "re-pointed at the new tooltip DOM"
        )


def test_the_dead_base_web_sweeper_is_gone() -> None:
    """BUG-48/51's sweeper waited for a `[data-baseweb="tooltip"]` layer that
    Streamlit 1.64 no longer renders, so it polled every 250 ms for nothing."""
    assert not hasattr(app, "_TOOLTIP_SWEEPER_SCRIPT")
