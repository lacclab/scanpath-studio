"""The Simple / Advanced interface mode: which one is in force, and how it persists.

The mode is resolved once per session, in this order: a ``?ui=`` link
parameter, the browser cookie from the last visit, then Simple. It is the
viewer's own preference, so Share never writes it into a link. The functions
that decide take plain mappings, so they need no Streamlit runtime.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING

from scanpath_studio.session_keys import PARAM_UI, UI_MODE, UI_MODE_COOKIE

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

#: The session flag that is set once the viewer has used the switch: only then
#: is the choice written to the cookie (a ``?ui=`` link alone never is).
CHOSEN_KEY = "_ui_mode_chosen"
SWITCH_KEY = "ui_mode_switch"
_ADV_PREFIX = "adv_only_"
_SIMPLE_PREFIX = "simple_only_"

SIMPLE = "simple"
ADVANCED = "advanced"
MODES = (SIMPLE, ADVANCED)
_LABELS = {SIMPLE: "Simple", ADVANCED: "Advanced"}

_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def parse_mode(value: object) -> str | None:
    """The mode ``value`` names, or ``None`` when it is not a string naming one."""
    if not isinstance(value, str):
        return None
    mode = value.strip().lower()
    return mode if mode in MODES else None


def resolve_mode(param: object, cookie: object) -> str:
    """The link's mode, else the cookie's, else Simple; junk values are skipped."""
    return parse_mode(param) or parse_mode(cookie) or SIMPLE


def seed_mode(session: MutableMapping, query_params: Mapping, cookies: Mapping) -> str:
    """Fix the session's mode on its first run and return it.

    A mode already in the session wins: the header switch writes it, and a
    link's ``?ui=`` must not undo a choice made after the page opened.
    """
    session[UI_MODE] = parse_mode(session.get(UI_MODE)) or resolve_mode(
        query_params.get(PARAM_UI), cookies.get(UI_MODE_COOKIE)
    )
    return session[UI_MODE]


def current_mode() -> str:
    """The session's mode (Simple before it is seeded)."""
    import streamlit as st

    return st.session_state.get(UI_MODE, SIMPLE)


def is_simple() -> bool:
    """Whether the session is in Simple mode."""
    return current_mode() == SIMPLE


def cookie_script(mode: str) -> str:
    """A same-origin script that remembers ``mode`` in a year-long cookie.

    ``st.iframe`` embeds share the app's origin, so the parent document's
    ``cookie`` is writable from here, the only way to keep a preference
    browser-side without an account.
    """
    value = f"{UI_MODE_COOKIE}={parse_mode(mode) or SIMPLE}; max-age={_COOKIE_MAX_AGE}"
    return (
        "<script>window.parent.document.cookie = "
        f'"{value}; path=/; SameSite=Lax";</script>'
    )


def has_link_params(query_params: Mapping) -> bool:
    """Whether the URL carries anything besides ``?ui=``, i.e. is a deep link."""
    return any(key != PARAM_UI for key in query_params)


def mode_css(mode: str) -> str:
    """A ``<style>`` hiding the containers that belong to the other mode.

    Containers made by :func:`advanced_only` / :func:`simple_only` stay in the
    page in both modes and are hidden by CSS, so switching mode never changes
    which elements a rerun draws, and no widget loses its value.
    """
    hidden = _SIMPLE_PREFIX if parse_mode(mode) == ADVANCED else _ADV_PREFIX
    return f'<style>[class*="st-key-{hidden}"] {{ display: none !important; }}</style>'


def advanced_only(host: DeltaGenerator, name: str) -> DeltaGenerator:
    """A container under ``host`` that is shown in Advanced mode only."""
    return host.container(key=f"{_ADV_PREFIX}{name}")


def simple_only(host: DeltaGenerator, name: str) -> DeltaGenerator:
    """A container under ``host`` that is shown in Simple mode only."""
    return host.container(key=f"{_SIMPLE_PREFIX}{name}")


def _on_switch() -> None:
    """Copy the switch into the session's mode; a deselect keeps the old one."""
    import streamlit as st

    chosen = parse_mode(st.session_state.get(SWITCH_KEY))
    if chosen is not None:
        st.session_state[UI_MODE] = chosen
        st.session_state[CHOSEN_KEY] = True


def render_switch(host: DeltaGenerator) -> None:
    """Draw the Simple | Advanced switch in ``host``.

    The widget's value is re-written from the session's mode on every run, so
    a link or a restore that moves the mode moves the switch with it. Once the
    viewer has used it, a same-origin script keeps the choice in the browser's
    cookie for the next visit.
    """
    import streamlit as st

    from scanpath_studio.html_embed import embed_html_iframe

    st.session_state[SWITCH_KEY] = current_mode()
    box = host.container(key="tour_grp_ui_mode")
    box.segmented_control(
        "Interface",
        options=list(MODES),
        format_func=_LABELS.__getitem__,
        key=SWITCH_KEY,
        label_visibility="collapsed",
        persist_state="session",
        on_change=_on_switch,
    )
    if st.session_state.get(CHOSEN_KEY):
        with box:
            embed_html_iframe(cookie_script(current_mode()), height=0)
