"""BUG-86: a `help=` tooltip shows only while *its own* trigger is hovered or keyboard-focused.

Streamlit 1.64's tooltip trigger keeps the panel open for as long as focus is
inside it, whatever the pointer does, and it can leave several panels open at
once — so clicking buttons or popovers that have `help=` left their tooltips
floating over the page, and hovering any other tooltip button brought all of
them back. Two layers fix it, both keyed on the browser's own `:hover` /
`:focus-visible` rather than on React's open state:

* `app._TOOLTIP_OWNER_SCRIPT` marks a panel *owned* while its own trigger (the
  element whose `aria-describedby` names the panel) is hovered or keyboard-
  focused, and once it is running `styles.get_app_css` hides every panel that
  is not — including one that has just appeared, before it is ever painted;
* the same CSS rule hides every panel while *no* trigger is hovered or
  keyboard-focused — the floor if the script cannot run.

Both hide at once: a hide delayed for a fade (which Streamlit's own animation
pins at full opacity anyway) is what let a stale panel flash for 100 ms.

Both name Streamlit's frontend DOM, so the last test reads the installed
Streamlit bundle for it: BUG-48's JavaScript sweeper went dead without a single
failing test when an upgrade dropped the Base Web `data-baseweb="tooltip"` layer
it looked for, and this is the guard against the same silent break.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import streamlit

from scanpath_studio import app
from scanpath_studio.styles import get_app_css

TRIGGERS = ("stTooltipHoverTarget", "stTooltipErrorHoverTarget")
PANELS = ("stTooltipContent", "stTooltipErrorContent")
OWNED_MARK = "data-sps-tooltip-owned"
INSTALLED_MARK = "data-sps-tooltip-owners"


def _hide_rule(css: str) -> tuple[str, str]:
    """The selector and body of the rule that hides the tooltip panels."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)  # its comment names both
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "visibility: hidden" in body and all(p in selector for p in PANELS):
            return selector, body
    raise AssertionError("no rule hides the Streamlit tooltip panels")


def test_panel_hidden_unless_a_trigger_is_hovered_or_keyboard_focused() -> None:
    selector, _ = _hide_rule(get_app_css())
    condition = selector.split(":not(:has(", 1)[1].split("))", 1)[0]
    for trigger in TRIGGERS:
        assert f'[data-testid="{trigger}"]:hover' in condition
        # Keyboard focus keeps a tooltip up; focus left by a click must not.
        assert f'[data-testid="{trigger}"] :focus-visible' in condition
    assert ":focus-within" not in condition
    assert ":focus," not in condition


def test_a_panel_its_own_trigger_does_not_claim_is_hidden() -> None:
    selector, _ = _hide_rule(get_app_css())
    # Only once the script is running, or no tooltip would ever show without it.
    assert f'html[{INSTALLED_MARK}] [role="tooltip"]:not([{OWNED_MARK}])' in selector


def test_the_hide_is_immediate() -> None:
    _, body = _hide_rule(get_app_css())
    assert "transition" not in body


def test_owner_script_judges_each_panel_by_its_own_trigger() -> None:
    script = app._TOOLTIP_OWNER_SCRIPT
    assert OWNED_MARK in script and INSTALLED_MARK in script
    assert '[aria-describedby~="' in script  # the panel's own trigger, by id
    assert '[role="tooltip"]' in script
    assert ":hover" in script and ":focus-visible" in script
    assert ":focus-within" not in script
    # Re-evaluated when the pointer or focus moves and when a panel opens.
    for trigger in ("pointerover", "pointerout", "focusin", "focusout"):
        assert f'"{trigger}"' in script
    assert "MutationObserver" in script
    assert "_TOOLTIP_OWNER_SCRIPT" in inspect.getsource(app.configure_page)


def test_streamlit_bundle_still_has_the_tooltip_dom_this_relies_on() -> None:
    js = Path(streamlit.__file__).parent / "static" / "static" / "js"
    chunks = [
        text
        for text in (path.read_text(errors="ignore") for path in js.glob("*.js"))
        if "stTooltip" in text
    ]
    bundle = "".join(chunks)
    for test_id in (*TRIGGERS, *PANELS):
        assert f"`{test_id}`" in bundle, (
            f"Streamlit {streamlit.__version__} no longer names {test_id!r}; "
            "the BUG-86 tooltip rules hide nothing until they are re-pointed at "
            "the new tooltip DOM"
        )
    # The owner script finds a panel's trigger through `aria-describedby` on
    # the hover target and the panel's `role="tooltip"`.
    trigger_chunk = next(c for c in chunks if "`stTooltipHoverTarget`" in c)
    assert '"aria-describedby"' in trigger_chunk
    assert "role:`tooltip`" in trigger_chunk


def test_the_dead_base_web_sweeper_is_gone() -> None:
    """BUG-48/51's sweeper waited for a `[data-baseweb="tooltip"]` layer that
    Streamlit 1.64 no longer renders, so it polled every 250 ms for nothing."""
    assert not hasattr(app, "_TOOLTIP_SWEEPER_SCRIPT")
