"""The Simple / Advanced interface mode: which one is in force, and how it persists.

The mode is resolved once per session, in this order: a ``?ui=`` link
parameter, the browser cookie from the last visit, then Simple. It is the
viewer's own preference, so Share never writes it into a link. The functions
that decide take plain mappings, so they need no Streamlit runtime.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING

from scanpath_studio.constants import ICONS
from scanpath_studio.session_keys import (
    PARAM_UI,
    SINGLE_ANIMATE,
    UI_MODE,
    UI_MODE_COOKIE,
)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

#: The session flag that is set once the viewer has used the switch: only then
#: is the choice written to the cookie (a ``?ui=`` link alone never is).
CHOSEN_KEY = "_ui_mode_chosen"
SWITCH_KEY = "ui_mode_switch"
#: Set on a session's first run, whichever mode it opened in, so the Simple
#: start is never applied to a session that switched to Simple later.
START_DONE_KEY = "_ui_simple_start_done"
_ADV_PREFIX = "adv_only_"
_SIMPLE_PREFIX = "simple_only_"
#: The `advanced_only` name of the trial picker's slider; Simple also hides the
#: column that holds it.
TRIAL_SLIDER = "trial_slider"
#: The `advanced_only` name of the trial picker's sort popover, whose
#: ``railbtn_*`` cluster cell Simple drops when nothing else is in it.
TRIAL_SORT = "trial_sort"

SIMPLE = "simple"
ADVANCED = "advanced"
MODES = (SIMPLE, ADVANCED)
_LABELS = {SIMPLE: "Simple", ADVANCED: "Advanced"}

_COOKIE_MAX_AGE = 365 * 24 * 60 * 60

#: What Advanced adds, area by area, as ``(title, one line)`` pairs. Simple names
#: these where a viewer would look for them (the ＋ More lists) instead of
#: drawing the controls, so the lines describe features and carry no widget.
MORE_IN_ADVANCED: dict[str, tuple[tuple[str, str], ...]] = {
    "picker": (
        (
            "🔍 Filter trials",
            "Narrow the list by text, participant, condition or your annotations.",
        ),
        ("⇅ Sort the trial list", "Order trials by a statistic or a property."),
        (
            "🎚 Trial slider",
            "Sweep through the trials quickly, with the count and id on it.",
        ),
        (
            "✏️ Summary chips",
            "Choose and reorder the chips shown above the plot.",
        ),
    ),
    "rail": (
        ("🎬 Replay settings", "Speed and frame rate."),
        ("👥 Compare", "Two readings, overlaid or side by side."),
        (
            "🎨 Layer style",
            "Colour fixations by a measure; sizes, word boxes and raw gaze.",
        ),
        (
            "🎯 Filters & highlights",
            "A fixation window, short or long fixations, saccade types.",
        ),
        ("🖼 Figure & canvas", "The screen, axes, titles and legends."),
        ("💾 Saved designs", "Keep your own figure designs and reuse them."),
    ),
    "subtabs": (
        (
            "📝 Annotations",
            "Mark trials to come back to: a favourite, tags and notes.",
        ),
        (
            "📄 Stimulus & context",
            "The passage with highlights, and its comprehension questions.",
        ),
        ("🔬 Comparisons", "Every other reading of this text, side by side."),
        ("📤 Export bundle", "Figures and tables for all trials at once."),
    ),
}


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


def seed_simple_start(
    session: MutableMapping, query_params: Mapping, *, restored: bool
) -> None:
    """Open a fresh Simple session on the playing replay.

    The replay is a starting value, not a lock: it applies only when the session
    starts in Simple with no deep link and nothing restored, so a link, a saved
    configuration or a recovered session keeps what it carries, and Advanced
    keeps its static start. It runs once, on the first run, so switching to
    Simple mid-session never turns the replay on.
    """
    if session.get(START_DONE_KEY):
        return
    session[START_DONE_KEY] = True
    if (
        session.get(UI_MODE) == SIMPLE
        and not has_link_params(query_params)
        and not restored
    ):
        session.setdefault(SINGLE_ANIMATE, True)


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
    advanced = parse_mode(mode) == ADVANCED
    hidden = f'[class*="st-key-{_SIMPLE_PREFIX if advanced else _ADV_PREFIX}"]'
    # In the rail, a hidden container's wrapper block would still take the
    # rail's gap and the margin under each block: hide the wrapper with it. A
    # rule of its own, so a browser without `:has()` still hides the container.
    hide = (
        f"{hidden} {{ display: none !important; }}"
        ' .st-key-scanpath_rail [data-testid="stLayoutWrapper"]'
        f":has(> {hidden}) {{ display: none !important; }}"
    )
    if advanced:
        rules = hide
    else:
        cell = '[class*="st-key-railbtn_"] > div'
        sort = f'> [class*="st-key-railbtn_"] > div:only-child > .st-key-{_ADV_PREFIX}{TRIAL_SORT}'
        rules = hide + (
            # With the slider gone its column would still hold a gap: drop it.
            # Only the column that holds it directly, never one around the row.
            ' [data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"]'
            ' > [data-testid="stLayoutWrapper"]'
            f" > .st-key-{_ADV_PREFIX}{TRIAL_SLIDER})"
            " { display: none !important; }"
            # A ``railbtn_*`` cell holding only the hidden sort popover would
            # still take the cluster's 3px neighbour margin: drop the cell, and
            # the margin it gives the cell after it when it comes first.
            f" {cell}:has({sort}) {{ display: none !important; }}"
            f" {cell}:first-child:has({sort}) + div {{ margin-left: 0 !important; }}"
        )
    return f"<style>{rules}</style>"


def advanced_only(host: DeltaGenerator, name: str) -> DeltaGenerator:
    """A container under ``host`` that is shown in Advanced mode only."""
    return host.container(key=f"{_ADV_PREFIX}{name}")


def simple_only(host: DeltaGenerator, name: str) -> DeltaGenerator:
    """A container under ``host`` that is shown in Simple mode only."""
    return host.container(key=f"{_SIMPLE_PREFIX}{name}")


def _choose_mode(mode: object) -> None:
    """Make ``mode`` the session's mode as the viewer's own choice.

    Marks it chosen, which is what lets the cookie script remember it. Anything
    that is not a mode (a deselected switch) changes nothing.
    """
    import streamlit as st

    chosen = parse_mode(mode)
    if chosen is not None:
        st.session_state[UI_MODE] = chosen
        st.session_state[CHOSEN_KEY] = True


def _on_switch() -> None:
    """Copy the switch into the session's mode; a deselect keeps the old one."""
    import streamlit as st

    _choose_mode(st.session_state.get(SWITCH_KEY))


def _switch_to_advanced() -> None:
    """The ＋ More lists' button: the same choice the header switch makes."""
    _choose_mode(ADVANCED)


def render_more_list(host: DeltaGenerator, area: str) -> None:
    """Draw ``area``'s list of Advanced-only features, ending in a switch button.

    The list names features only and holds no control, so opening it never
    changes anything.
    """
    for title, line in MORE_IN_ADVANCED[area]:
        host.markdown(f"**{title}**  \n{line}")
    host.button(
        "Switch to Advanced",
        key=f"more_to_advanced_{area}",
        on_click=_switch_to_advanced,
    )


def render_more_popover(host: DeltaGenerator, area: str, label: str = "More") -> None:
    """Draw ``area``'s ＋ More popover, the list of what Advanced adds there."""
    popover = host.popover(
        label,
        icon=ICONS["add"],
        width="content",
        help="What Advanced adds here",
        key=f"iconpop_more_{area}",
    )
    render_more_list(popover, area)


#: What each hidden setting in play is called in the note, in the order it is
#: listed.
_HIDDEN_PHRASES = (
    ("narrowed", "a trial filter"),
    ("sorted_", "a sort order"),
    ("comparing", "Compare"),
    ("custom_view", "plot settings from Advanced"),
)


def hidden_settings_reasons(
    *, narrowed: bool, sorted_: bool, comparing: bool, custom_view: bool
) -> list[str]:
    """The Advanced-only settings shaping what Simple shows, as short phrases.

    ``narrowed``: a trial filter shortens the pool. ``sorted_``: the trial list
    is not in its default order. ``comparing``: Compare is on. ``custom_view``:
    the plot settings match none of Simple's View tiles.
    """
    flags = {
        "narrowed": narrowed,
        "sorted_": sorted_,
        "comparing": comparing,
        "custom_view": custom_view,
    }
    return [phrase for name, phrase in _HIDDEN_PHRASES if flags[name]]


def render_hidden_settings_note(host: DeltaGenerator, reasons: list[str]) -> None:
    """Say, in one line, which Advanced settings are shaping Simple's view.

    Draws nothing for no ``reasons``; otherwise a caption naming them and a
    button that switches to Advanced, where they can be changed.
    """
    if not reasons:
        return
    row = host.container(
        horizontal=True,
        vertical_alignment="center",
        gap="small",
        key="hidden_settings_note",
    )
    row.caption(
        f"{ICONS['info']} Settings from Advanced are shaping this view: "
        f"{', '.join(reasons)}."
    )
    row.button(
        "Switch to Advanced",
        key="hidden_note_to_advanced",
        type="tertiary",
        on_click=_switch_to_advanced,
    )


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
