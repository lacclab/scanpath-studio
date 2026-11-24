"""The app's navigation, interface mode switch and load notices.

Nothing in the app writes to ``st.sidebar``, so Streamlit draws no sidebar
chrome and the main content gets the full page width.

**The nav** (:func:`render_nav`) is Streamlit's own
``st.navigation(position="top")``: three **views** — 🗺️ Scanpath View · 📊 Corpus
Analysis · 🗂️ Data — and a ❓ Help section for task guides, troubleshooting
and feedback, the current edition's documentation, and About & citation.
Selecting a dialog action arms it and bounces the router
straight back to the view you were on, so the modal opens over your work.

Data Management → Saved work shows the recovery copy
(``app._render_saved_here_section``). Annotations are exported under Current
dataset → Annotations. Scanpath → Share → Settings file exports plot settings
(``tabs.render_settings_file``).

The Data page's sections run on every run: the page container is built every
run and hidden off-screen when another view is active
(``constants.DATA_PAGE_OFFSCREEN_KEY`` + the ``display: none`` rule in
``styles.py``), because Streamlit drops the state of a widget that does not
render and several of them drive ``app.prepare_data``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from scanpath_studio import ui_mode
from scanpath_studio.build_info import build_info
from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    DATA_WORKSPACE_LAST,
    DATA_WORKSPACE_REQUEST,
    ICONS,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from streamlit.delta_generator import DeltaGenerator

#: Nav entries: view constant → (label, icon, URL path).
#: **Data comes last** even though setting a dataset up comes first in time: it
#: is visited occasionally, while the two analysis views are where the work
#: happens.
_NAV_PAGES = {
    _VIEW_SCANPATH: ("Scanpath View", ICONS["view_scanpath"], "scanpath"),
    _VIEW_CORPUS: ("Corpus Analysis", ICONS["view_corpus"], "corpus-analysis"),
    _VIEW_DATA: ("Data Management", ICONS["view_data"], "data"),
}

#: The tooltip each view's nav entry shows on hover.
_NAV_HELP = {
    _VIEW_SCANPATH: (
        "Draw one reading's scanpath over its text, replay it, or compare it "
        "with another reading."
    ),
    _VIEW_CORPUS: (
        "Summarize the selected trials and their reading measures by text, "
        "participant and group."
    ),
    _VIEW_DATA: (
        "Add, open and edit datasets with their metadata and annotations, and "
        "find saved figures and sessions."
    ),
}

#: The ❓ Help *section* of the nav: entry id → (label, icon, url path).
#: These are not views. Each one opens a dialog over whatever you were already
#: looking at — see :func:`render_nav` for the bounce that makes that work.
_HELP_PAGES = {
    "help_tutorials": ("Task guides", ICONS["tutorials"], "help-tutorials"),
    "help_faq": ("Troubleshooting & feedback", ICONS["faq"], "help-faq"),
    "help_about": ("About & citation", ICONS["about"], "help-about"),
    # A hidden page keeps existing feedback bookmarks working.
    "help_feedback": ("Send feedback", ICONS["feedback"], "help-feedback"),
}

#: The nav section heading the entries above collapse under.
HELP_SECTION = f"{ICONS['help']} Help · {build_info().channel.title()}"

#: What :func:`render_nav` last mirrored into ``main_nav``. Session state, not a
#: module global — it is per-user. See ``render_nav`` for why it is load-bearing:
#: without it, a nav click is indistinguishable from a request to go back, and
#: the nav bounces.
_MIRROR_KEY = "_nav_mirrored"

#: True on a run that lands on its view from elsewhere: a nav click, a
#: programmatic switch, or a Help action's bounce back to the view you were on.
#: Each of those drops the page's query parameters, so a view that keeps its
#: place in the URL (Corpus Analysis) reads this to restore that place from
#: session state instead of taking the empty address for browser history.
ARRIVED_KEY = "_nav_arrived"
_SWITCHED_KEY = "_nav_switched"

#: Keyed wrapper around the main-area strip just under the bar, where load-time
#: warnings land. A warning inside a *closed* popover would be invisible, so
#: these stay in the page where the user can't miss them.
NOTICES_KEY = "top_menu_notices"


def view_label(view: str) -> str:
    """The nav's short label for ``view`` (e.g. "Scanpath View"), for use in prose.

    The ``_VIEW_*`` constants are the wire values ("Scanpath Visualization");
    quoting those at the user would name something the nav doesn't say.
    """
    entry = _NAV_PAGES.get(view)
    return entry[0] if entry else view


def _unused_page_body() -> None:  # pragma: no cover - never executed
    """Placeholder body for the ``st.Page`` objects.

    ``st.navigation`` is used here only to *render* the nav and report which
    entry is selected — we never call ``.run()``, because ``app.main`` owns
    the dispatch (it has to: the view bodies close over frames the long prelude
    computes, and the epilogue — ``save_local_state``, then the Data page's
    *Saved work* — has to run *after* the body). So these never execute.
    """
    raise AssertionError("page body should never run — app.main owns dispatch")


def _view_page(view: str):
    label, icon, path = _NAV_PAGES[view]
    return st.Page(
        _unused_page_body,
        title=label,
        icon=icon,
        url_path=path,
        default=view == _VIEW_SCANPATH,
        help=_NAV_HELP[view],
    )


def switch_to_view(view: str) -> None:
    """Navigate to ``view`` programmatically. Reruns; does not return.

    The router owns the selection, so writing ``main_nav`` is not enough on
    its own — this is what actually moves the nav. Not callable from a widget
    callback (Streamlit forbids ``st.switch_page`` there); callbacks should write
    ``main_nav`` and let :func:`render_nav`'s reconciliation do the switch on the
    next run.
    """
    if view in _NAV_PAGES:
        st.session_state[_SWITCHED_KEY] = True
        # Replace the previous page's parameters explicitly. The Corpus subtab
        # binds its selection to the URL, so the default clear can be refused.
        st.switch_page(_view_page(view), query_params={})


def _arm_help_action(entry: str) -> None:
    """Arm the dialog a nav *action* entry stands for.

    This only sets the request flag each ``maybe_show_*`` serves in
    ``app.main``; the dialog itself is drawn there. Imports are local because
    ``app`` imports this module.
    """
    if entry == "help_tutorials":
        from scanpath_studio import tour

        tour._arm_tutorial_library()
    elif entry == "help_about":
        from scanpath_studio import app

        app._arm_about()
    elif entry in {"help_faq", "help_feedback"}:
        from scanpath_studio import feedback

        feedback._arm_feedback()


def render_nav() -> str:
    """Draw Streamlit's native top nav and return the active view.

    Uses ``st.navigation(position="top")`` — the platform's own navigation,
    rendered into the header strip beside the toolbar, so it costs no page
    height and looks like Streamlit rather than like an app control.

    **``main_nav`` is kept as a mirror, not the source of truth.** The router
    owns the selection, but several places *write* ``main_nav`` to request
    a view (``url_state._go_scanpath`` / ``_go_data``, ``tour`` when a step drives the
    app to another view, and ``persistence`` restoring the view you were last
    on) — including from ``on_click`` callbacks, where ``st.switch_page`` is not
    allowed. So each run reconciles, then writes the resolved view back for
    every reader of ``main_nav`` — the tour, ``persistence``.

    The reconciliation turns on ``_nav_mirrored``: the value this function wrote
    last run. Without it the two directions are indistinguishable and the nav
    is unusable — clicking "Corpus Analysis" makes ``main_nav`` (still holding
    last run's "Scanpath") disagree with the router, which reads as a request to
    go *back*, and the click bounces. Comparing against what we last mirrored
    separates them: ``main_nav`` still equal to it means nobody asked for
    anything and the router simply moved (the user clicked); ``main_nav``
    changed out from under it is a genuine request, honoured by switching —
    which reruns, and next run the two agree and it stops.
    """
    pages = {view: _view_page(view) for view in _NAV_PAGES}
    # A *dict* of sections. The entries under the empty-string key are
    # drawn first, at the top level; every other key becomes a collapsible item
    # — Streamlit's own documented behaviour for `position="top"`, so ❓ Help
    # opens a menu with no CSS of ours.
    action_pages = {
        entry: st.Page(
            _unused_page_body,
            title=label,
            icon=icon,
            url_path=url_path,
            visibility="hidden" if entry == "help_feedback" else "visible",
        )
        for entry, (label, icon, url_path) in _HELP_PAGES.items()
    }
    selected = st.navigation(
        {
            "": list(pages.values()),
            HELP_SECTION: [
                action_pages["help_tutorials"],
                action_pages["help_faq"],
                st.Page(
                    build_info().docs_url, title="Documentation ↗", icon=ICONS["docs"]
                ),
                action_pages["help_about"],
                action_pages["help_feedback"],
            ],
        },
        position="top",
    )
    # An action entry is not a destination: arm its dialog and go straight back
    # to the view the user was on, so the modal opens over their work instead of
    # over an empty page. The bounce reruns, and next run the router has
    # re-selected that view, so nothing re-arms.
    chosen_action = next(
        (entry for entry, page in action_pages.items() if page.title == selected.title),
        None,
    )
    # A direct visit to a named page or Help action already has a destination.
    if (
        _MIRROR_KEY not in st.session_state
        and selected.title != pages[_VIEW_SCANPATH].title
    ):
        st.session_state["tour_seen"] = True
    if chosen_action is not None:
        _arm_help_action(chosen_action)
        back = st.session_state.get(_MIRROR_KEY)
        if back == _VIEW_DATA and DATA_WORKSPACE_LAST in st.session_state:
            st.session_state.setdefault(
                DATA_WORKSPACE_REQUEST, st.session_state[DATA_WORKSPACE_LAST]
            )
        switch_to_view(back if back in pages else _VIEW_SCANPATH)  # reruns
    active = next(
        (view for view, page in pages.items() if page.title == selected.title),
        _VIEW_SCANPATH,
    )
    requested = st.session_state.get("main_nav")
    mirrored = st.session_state.get(_MIRROR_KEY)
    # On a session's first run (nothing mirrored yet), a page the URL names —
    # `/data`, `/corpus-analysis` — is where the user asked to go, and wins over
    # the view the recovery cache restored into `main_nav`. Only the bare root
    # (the default page) resumes the last view.
    url_named_page = _MIRROR_KEY not in st.session_state and active != _VIEW_SCANPATH
    if (
        requested in pages
        and requested != active
        and requested != mirrored
        and not url_named_page
    ):
        st.session_state[_MIRROR_KEY] = requested
        switch_to_view(requested)  # reruns
    st.session_state[ARRIVED_KEY] = bool(
        st.session_state.pop(_SWITCHED_KEY, False)
        or (mirrored is not None and mirrored != active)
    )
    st.session_state["main_nav"] = active
    st.session_state[_MIRROR_KEY] = active
    return active


def render_top_menu(*, active_view: str) -> DeltaGenerator:
    """Draw the mode switch and reserve a stable place for load notices."""
    ui_mode.render_switch(st, visible=active_view == _VIEW_SCANPATH)
    return st.container(key=NOTICES_KEY)
