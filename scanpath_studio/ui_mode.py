"""The Simple / Advanced interface mode: which one is in force, and how it persists.

The mode is resolved once per session, in this order: a ``?ui=`` link
parameter, the browser cookie from the last visit, then Simple. It is the
viewer's own preference, so Share never writes it into a link. The functions
that decide take plain mappings, so they need no Streamlit runtime.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from scanpath_studio.session_keys import PARAM_UI, UI_MODE, UI_MODE_COOKIE

SIMPLE = "simple"
ADVANCED = "advanced"
MODES = (SIMPLE, ADVANCED)

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
    return session.setdefault(
        UI_MODE, resolve_mode(query_params.get(PARAM_UI), cookies.get(UI_MODE_COOKIE))
    )


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
    value = f"{UI_MODE_COOKIE}={mode}; max-age={_COOKIE_MAX_AGE}"
    return (
        "<script>window.parent.document.cookie = "
        f'"{value}; path=/; SameSite=Lax";</script>'
    )


def has_link_params(query_params: Mapping) -> bool:
    """Whether the URL carries anything besides ``?ui=``, i.e. is a deep link."""
    return any(key != PARAM_UI for key in query_params)
