"""The app's header: the native top nav, the title row and the notices strip.

What replaced the sidebar (UX-38 → UX-100). Nothing in the app writes to
``st.sidebar``, so Streamlit draws no sidebar chrome and the main content gets
the full page width.

**The nav** (:func:`render_nav`) is Streamlit's own
``st.navigation(position="top")``: three **views** — 🗺️ Scanpath · 📊 Corpus
Analysis · 🗂️ Data — and a ❓ Help section of **action** entries (Tutorials,
FAQ, About, Debug). Selecting an action arms a dialog and bounces the router
straight back to the view you were on, so the modal opens over your work.

**UX-179 retired 💾 Session**, the last top-level action entry. Its four blocks
went where each is used: Debug to ❓ Help, the recovery cache and *Reset
everything* to the foot of the Data page (``app._render_saved_here_section``),
and the settings file to 🗺️ Scanpath → 🔗 Share → File
(``tabs.render_settings_file``) — its annotations having already got their own
export on 🗂️ Data → Annotations.

**DATA-26 took ⚙️ Configure and 🧹 Preprocessing off the bar** and made them
sections of the Data page. Their widgets keep every-run execution: the page
container is built every run and hidden off-screen when another view is active
(``constants.DATA_PAGE_OFFSCREEN_KEY`` + the ``display: none`` rule in
``styles.py``), because Streamlit drops the state of a widget that does not
render and several of them drive ``app.prepare_data``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import streamlit as st

from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    ICONS,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from streamlit.delta_generator import DeltaGenerator

#: The spotlight tour's selector for the navigation. Streamlit's own top nav has
#: no key of ours to hang a ``.st-key-*`` class on, so the step points at the
#: frontend's stable test id instead.
NAV_SELECTOR = '[data-testid="stTopNavLinkContainer"]'

#: Nav entries: view constant → (label, icon, url path). The labels are short —
#: "Scanpath", not "Scanpath Visualization" — because the nav sits in Streamlit's
#: header strip beside the toolbar, where a long label crowds it. UX-196 is the
#: one exception: beta testers looked for the page by its header, *Data
#: Management*, so the nav says that too.
#: **Data comes last** (DATA-26) even though setting a dataset up comes first in
#: time: it is visited occasionally, while the two analysis views are where the
#: work happens, and moving them rightwards to make room for a setup page would
#: cost every existing user their aim.
_NAV_PAGES = {
    _VIEW_SCANPATH: ("Scanpath", ICONS["view_scanpath"], "scanpath"),
    _VIEW_CORPUS: ("Corpus Analysis", ICONS["view_corpus"], "corpus-analysis"),
    _VIEW_DATA: ("Data Management", ICONS["view_data"], "data"),
}

#: UX-65 — the ❓ Help *section* of the nav: entry id → (label, icon, url path).
#: These are not views. Each one opens the dialog that used to sit behind a
#: button on the Help page, over whatever you were already looking at — see
#: :func:`render_nav` for the bounce that makes that work. Documentation is
#: absent on purpose: ``st.Page`` cannot be a URL, and the UX-62 wordmark beside
#: this nav already links to the docs site.
_HELP_PAGES = {
    "help_tutorials": ("Tutorials", ICONS["tutorials"], "help-tutorials"),
    "help_faq": ("FAQ", ICONS["faq"], "help-faq"),
    "help_about": ("About", ICONS["about"], "help-about"),
    # UX-179 — the debug gate and log, which used to be the last block of the
    # 💾 Session dialog. Help is where you go when something is wrong, and the
    # log's use is attaching it to a bug report.
    "help_debug": ("Debug", ICONS["debug"], "help-debug"),
}

#: The nav section heading the four entries above collapse under.
HELP_SECTION = f"{ICONS['help']} Help"

#: This run's ``st.Page`` objects, view constant → Page. Rebuilt every run (an
#: ``st.Page`` belongs to the run that made it) and read by
#: :func:`switch_to_view`, which is the only way to navigate programmatically.
_PAGES: dict[str, object] = {}

#: What :func:`render_nav` last mirrored into ``main_nav``. Session state, not a
#: module global — it is per-user. See ``render_nav`` for why it is load-bearing:
#: without it, a nav click is indistinguishable from a request to go back, and
#: the nav bounces.
_MIRROR_KEY = "_nav_mirrored"

#: Keyed wrapper around the main-area strip just under the bar, where load-time
#: warnings land. They used to be ``st.sidebar.warning`` calls in an
#: always-visible column; a warning inside a *closed* popover would be invisible,
#: so these stay in the page where the user can't miss them.
NOTICES_KEY = "top_menu_notices"


@dataclass(frozen=True)
class TopMenu:
    """What one rendered header row leaves behind for the rest of the run."""

    #: The main-area strip just under the header, where load-time warnings land.
    notices: DeltaGenerator
    #: The page heading's slot — the left half of the row the menu shares.
    #: ``app._render_about_panel`` fills it; see :func:`render_top_menu`.
    title: DeltaGenerator | None = None


def close_open_popovers() -> None:
    """Dismiss whichever menu popover is open, client-side.

    A popover's open/closed state lives in the browser, so a server callback can
    arm a dialog but cannot close the ❓ Help popover the button was inside —
    leaving the popover panel floating on top of the modal it just opened. Call
    this from a dialog body: it clicks the expanded trigger, which toggles it
    shut. Retried, because a click during React hydration is silently lost.

    Same trick as ``tour``'s tutorial-chooser closer, generalized: match any
    expanded popover trigger rather than one by label.
    """
    from scanpath_studio.html_embed import embed_html_iframe

    embed_html_iframe(
        """<script>
        (function () {
            const doc = window.parent.document;
            let tries = 0;
            (function closePopover() {
                const trigger = doc.querySelector(
                    '[data-testid="stPopover"] button[aria-expanded="true"]');
                if (trigger) { trigger.click(); return; }
                if (++tries < 20) setTimeout(closePopover, 50);
            })();
        })();
        </script>""",
        height=0,
    )


def view_label(view: str) -> str:
    """The nav's short label for ``view`` (e.g. "Scanpath"), for use in prose.

    The ``_VIEW_*`` constants are the wire values ("Scanpath Visualization");
    quoting those at the user would name something the nav doesn't say.
    """
    entry = _NAV_PAGES.get(view)
    return entry[0] if entry else view


def _unused_page_body() -> None:  # pragma: no cover - never executed
    """Placeholder body for the ``st.Page`` objects.

    ``st.navigation`` is used here only to *render* the nav and report which
    entry is selected — we never call ``.run()``, because ``app.main`` still owns
    the dispatch (it has to: the view bodies close over frames the long prelude
    computes, and the epilogue — ``save_local_state``, then the Data page's
    *Saved on this computer* — has to run *after* the body). So these never execute.
    """
    raise AssertionError("page body should never run — app.main owns dispatch")


def switch_to_view(view: str) -> None:
    """Navigate to ``view`` programmatically. Reruns; does not return.

    The router owns the selection now, so writing ``main_nav`` is not enough on
    its own — this is what actually moves the nav. Not callable from a widget
    callback (Streamlit forbids ``st.switch_page`` there); callbacks should write
    ``main_nav`` and let :func:`render_nav`'s reconciliation do the switch on the
    next run.
    """
    page = _PAGES.get(view)
    if page is not None:
        st.switch_page(page)


def _arm_help_action(entry: str) -> None:
    """Arm the dialog a nav *action* entry stands for (UX-65, UX-100).

    The dialogs themselves are untouched — this only sets the request flag each
    ``maybe_show_*`` already serves in ``app.main``, which is exactly what the
    Help *buttons* did through their ``on_click`` callbacks. Imports are local
    because ``app`` imports this module.
    """
    from scanpath_studio import tour

    if entry == "help_tour":
        tour._arm_tour()
    elif entry == "help_tutorials":
        tour._arm_tutorial_library()
    elif entry == "help_faq":
        tour._arm_faq()
    elif entry == "help_debug":
        from scanpath_studio.debug_log import _arm_debug

        _arm_debug()
    elif entry == "help_about":
        from scanpath_studio import app

        app._arm_about()


def render_nav() -> str:
    """Draw Streamlit's native top nav and return the active view.

    Uses ``st.navigation(position="top")`` — the platform's own navigation,
    rendered into the header strip beside the toolbar, so it costs no page
    height and looks like Streamlit rather than like an app control.

    **``main_nav`` is kept as a mirror, not the source of truth.** The router
    owns the selection, but several places still *write* ``main_nav`` to request
    a view (``url_state._go_scanpath`` / ``_go_data``, ``tour`` when a step drives the
    app to another view, and ``persistence`` restoring the view you were last
    on) — including from ``on_click`` callbacks, where ``st.switch_page`` is not
    allowed. So each run reconciles, then writes the resolved view back, and
    every existing reader of ``main_nav`` — the tour, ``persistence`` — keeps
    working unchanged.

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
    _PAGES.clear()
    for view, (label, icon, url_path) in _NAV_PAGES.items():
        _PAGES[view] = st.Page(
            _unused_page_body,
            title=label,
            icon=icon,
            url_path=url_path,
            default=view == _VIEW_SCANPATH,
        )
    # UX-65: a *dict* of sections. The entries under the empty-string key are
    # drawn first, at the top level; every other key becomes a collapsible item
    # — Streamlit's own documented behaviour for `position="top"`, so ❓ Help
    # opens a menu with no CSS of ours.
    action_pages = {
        entry: st.Page(_unused_page_body, title=label, icon=icon, url_path=url_path)
        for entry, (label, icon, url_path) in _HELP_PAGES.items()
    }
    selected = st.navigation(
        {
            "": [*_PAGES.values()],
            HELP_SECTION: [action_pages[entry] for entry in _HELP_PAGES],
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
    if chosen_action is not None:
        _arm_help_action(chosen_action)
        back = st.session_state.get(_MIRROR_KEY)
        switch_to_view(back if back in _PAGES else _VIEW_SCANPATH)  # reruns
    active = next(
        (view for view, page in _PAGES.items() if page.title == selected.title),
        _VIEW_SCANPATH,
    )
    requested = st.session_state.get("main_nav")
    mirrored = st.session_state.get(_MIRROR_KEY)
    if requested in _PAGES and requested != active and requested != mirrored:
        st.session_state[_MIRROR_KEY] = requested
        switch_to_view(requested)  # reruns
    st.session_state["main_nav"] = active
    st.session_state[_MIRROR_KEY] = active
    return active


def render_top_menu(*, active_view: str | None = None) -> TopMenu:
    """Draw the native top nav, then the title row and the notices strip.

    Call this once, early in ``app.main`` — before any data loading, so load
    warnings land in the notices strip rather than after the page content.

    Args:
        active_view: The entry the nav currently has selected, from
            :func:`render_nav`. Accepted so callers that already resolved the
            view do not resolve it twice.

    Returns:
        ``title`` — ``app._render_about_panel`` fills it — plus the main-area
        ``notices`` strip.
    """
    if active_view is None:
        render_nav()
    title_col, _ = st.columns([4, 1], vertical_alignment="bottom")
    return TopMenu(
        notices=st.container(key=NOTICES_KEY),
        title=title_col,
    )
