"""The app's top menu bar — the horizontal replacement for the former sidebar.

Every group that used to be an ``st.sidebar`` section is now a **popover** in one
row directly under the header, and nothing in the app writes to ``st.sidebar``
any more (so Streamlit draws no sidebar chrome at all and the main content gets
the full page width).

**Why popovers and not ``st.dialog``.** A dialog body only executes while the
dialog is open, but these panels are not passive display — several of them drive
``app.prepare_data`` on every rerun, and Streamlit drops the state of a widget
that does not render. A popover is a plain ``DeltaGenerator`` — it executes every
run and can be filled long after later elements were written, which is exactly
the ``st.sidebar`` semantics being replaced. That is what keeps this a host swap
rather than a restructure: ``main`` still reserves a slot here and downstream
code still fills it by ``host=``.

**UX-100 brought 💾 Session back to this bar.** UX-63 had made it a nav *page*;
once UX-96 had cut it down to four short blocks, a whole top-level destination
for them was more chrome than they were worth — and a page you navigate *away*
from is the wrong shape for "check the recovery cache, then carry on". It is one
popover again, at the right end of the title row, which is also why the
off-screen-twin machinery below could go: a popover already executes every run.

**DATA-26 took two groups off this bar.** ⚙️ Configure and 🧹 Preprocessing are
now sections of the **Data** page (``constants._VIEW_DATA``), because setting a
dataset up was split across a menu group and a subtab on the other side of the
app. Their widgets keep the every-run execution the popovers gave them: the page
container is built every run and merely hidden off-screen when another view is
active (``constants.DATA_PAGE_OFFSCREEN_KEY`` + the ``display: none`` rule in
``styles.py``). What is left here is genuinely session-wide, under one 💾 Session
trigger: 🗄️ Automatic recovery · ⬇️ JSON backup · ♻️ Reset · 🐛 Debug tools.

**Consequences for panel authors.** A popover nests neither an expander nor
another popover, so a group that used to wrap itself in
``st.sidebar.expander("<title>")`` now renders **bare** into its slot — the
popover trigger *is* the disclosure, and repeating the title inside it would
just be the label twice. See ``app._preprocessing_settings``,
``app._render_recovery_cache_panel`` and ``tabs._render_save_restore_expander``.

Streamlit 1.62 owns the viewport-aware maximum width; ``styles.py`` keeps only
the preferred 28 rem minimum for roomy desktop panels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import streamlit as st

from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from streamlit.delta_generator import DeltaGenerator

#: The spotlight tour's selector for the navigation. Streamlit's own top nav has
#: no key of ours to hang a ``.st-key-*`` class on, so the step points at the
#: frontend's stable test id instead.
NAV_SELECTOR = '[data-testid="stTopNavLinkContainer"]'

#: Nav entries: view constant → (label, icon, url path). The labels are short —
#: "Scanpath", not "Scanpath Visualization" — because the nav sits in Streamlit's
#: header strip beside the toolbar, where a long label crowds it.
#: **Data comes last** (DATA-26) even though setting a dataset up comes first in
#: time: it is visited occasionally, while the two analysis views are where the
#: work happens, and moving them rightwards to make room for a setup page would
#: cost every existing user their aim.
_NAV_PAGES = {
    _VIEW_SCANPATH: ("Scanpath", "🗺️", "scanpath"),
    _VIEW_CORPUS: ("Corpus Analysis", "📊", "corpus-analysis"),
    _VIEW_DATA: ("Data", "🗂️", "data"),
    # 💾 Session is deliberately **not** here (UX-100). It is a popover on the
    # title row instead — see :func:`render_top_menu`. UX-63 had made it a nav
    # page; the four blocks it holds are chrome you dip into and leave, not a
    # destination, and a page cost a whole entry plus the off-screen twin that
    # kept its widgets alive.
}

#: UX-65 — the ❓ Help *section* of the nav: entry id → (label, icon, url path).
#: These are not views. Each one opens the dialog that used to sit behind a
#: button on the Help page, over whatever you were already looking at — see
#: :func:`render_nav` for the bounce that makes that work. Documentation is
#: absent on purpose: ``st.Page`` cannot be a URL, and the UX-62 wordmark beside
#: this nav already links to the docs site.
_HELP_PAGES = {
    "help_tutorials": ("Tutorials", "🧭", "help-tutorials"),
    "help_faq": ("FAQ", "❔", "help-faq"),
    "help_about": ("About", "ℹ️", "help-about"),
}

#: The nav section heading the four entries above collapse under.
HELP_SECTION = "❓ Help"

#: This run's ``st.Page`` objects, view constant → Page. Rebuilt every run (an
#: ``st.Page`` belongs to the run that made it) and read by
#: :func:`switch_to_view`, which is the only way to navigate programmatically.
_PAGES: dict[str, object] = {}

#: What :func:`render_nav` last mirrored into ``main_nav``. Session state, not a
#: module global — it is per-user. See ``render_nav`` for why it is load-bearing:
#: without it, a nav click is indistinguishable from a request to go back, and
#: the nav bounces.
_MIRROR_KEY = "_nav_mirrored"

#: Keyed wrapper around the settings row. The spotlight tour targets
#: ``.st-key-top_menu``; ``styles.py`` styles it.
MENU_KEY = "top_menu"

#: Keyed wrapper around the main-area strip just under the bar, where load-time
#: warnings land. They used to be ``st.sidebar.warning`` calls in an
#: always-visible column; a warning inside a *closed* popover would be invisible,
#: so these stay in the page where the user can't miss them.
NOTICES_KEY = "top_menu_notices"

#: The 💾 Session trigger's key, and the tour's historical one: the spotlight
#: selector (``tour._SPOTLIGHT_STEPS``) and the "jump to Save & restore"
#: affordance in ``tabs.py`` both look for ``.st-key-tour_grp_save_restore``.
#: UX-38 merged 💾 Save & restore and 🗄️ Recovery cache under it rather than
#: renaming the key — the blocks are still there, one popover down — and UX-100
#: put the key back on a real trigger after UX-63's page had left it unused.
SAVE_RESTORE_KEY = "tour_grp_save_restore"


@dataclass(frozen=True)
class TopMenu:
    """The reserved slots of one rendered menu bar.

    Each attribute is an empty container that downstream code fills by
    ``host=``, in whatever order the load happens to reach it.
    """

    save_restore: DeltaGenerator
    recovery_cache: DeltaGenerator
    #: Session-wide reset, rendered early so it survives data-load failures.
    reset_session: DeltaGenerator
    notices: DeltaGenerator
    #: The page heading's slot — the left half of the row the menu shares.
    #: ``app._render_about_panel`` fills it; see :func:`render_top_menu`.
    title: DeltaGenerator | None = None
    debug: DeltaGenerator | None = None
    #: UX-65 — where ``render_debug_toggle`` goes, on the 💾 Session page.
    debug_gate: DeltaGenerator | None = None


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
    computes, and the epilogue — Save & restore, the recovery cache,
    ``save_local_state`` — has to run *after* the body). So these never execute.
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
    """Arm the dialog a ❓ Help nav entry stands for (UX-65).

    The dialogs themselves are untouched — this only sets the request flag each
    ``maybe_show_*`` already serves early in ``app.main``, which is exactly what
    the Help *buttons* did through their ``on_click`` callbacks. Imports are
    local because ``app`` imports this module.
    """
    from scanpath_studio import tour

    if entry == "help_tour":
        tour._arm_tour()
    elif entry == "help_tutorials":
        tour._arm_tutorial_library()
    elif entry == "help_faq":
        tour._arm_faq()
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
    a view (``_go_corpus`` / ``_go_scanpath``, ``tour`` when a step drives the
    app to another view, and ``persistence`` restoring the view you were last
    on) — including from ``on_click`` callbacks, where ``st.switch_page`` is not
    allowed. So each run reconciles, then writes the resolved view back, and
    every existing reader of ``main_nav`` — the tour, ``persistence``,
    ``_active_view`` — keeps working unchanged.

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
    help_pages = {
        entry: st.Page(_unused_page_body, title=label, icon=icon, url_path=url_path)
        for entry, (label, icon, url_path) in _HELP_PAGES.items()
    }
    selected = st.navigation(
        {"": list(_PAGES.values()), HELP_SECTION: list(help_pages.values())},
        position="top",
    )
    # A Help entry is an *action*, not a destination: arm its dialog and go
    # straight back to the view the user was on, so the modal opens over their
    # work instead of over an empty page. The bounce reruns, and next run the
    # router has re-selected that view, so nothing re-arms.
    chosen_help = next(
        (entry for entry, page in help_pages.items() if page.title == selected.title),
        None,
    )
    if chosen_help is not None:
        _arm_help_action(chosen_help)
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


def render_top_menu(
    *, show_debug: bool = False, active_view: str | None = None
) -> TopMenu:
    """Draw the native top nav + the two menu pages, returning their slots.

    Call this once, early in ``app.main`` — before any data loading, so the
    loaders' UI lands in the bar rather than after the page content.

    **UX-63 made 💾 Session a nav page; UX-100 made it a popover again.** The
    nav is back to the three views the work happens on — Scanpath · Corpus
    Analysis · Data — and Session is one trigger at the right end of the title
    row, over where the Scanpath view's control rail begins. UX-96 had already
    cut the group to four short blocks, at which point a top-level destination
    for them was more chrome than they were worth: you open Session to check the
    recovery cache or download a backup and then carry on with what you were
    doing, which is a popover's job and not a page's.

    **The panel still renders on every run**, which is the whole reason it is a
    popover rather than an ``st.dialog``: a popover body is plain script that
    executes each run whether or not the panel is open, while a dialog body runs
    only while open — and Streamlit drops a widget's key at the end of any run in
    which it did not render, so a dialog would silently reset the 🐛 Debug gate
    and the persistence pause toggle between visits. Every ``host=`` fill site in
    ``app.main`` is unchanged, and the off-screen-twin container UX-63 needed to
    get the same guarantee out of a *page* is gone with it.

    Args:
        show_debug: Add the 🐛 Debug block. Only debug sessions want it
            (``debug_log.debug_enabled``).
        active_view: The entry the nav currently has selected, from
            :func:`render_nav`. Accepted so callers that already resolved the
            view do not resolve it twice.

    Returns:
        The panel's empty slots, plus ``title`` — ``app._render_about_panel``
        fills it.
    """
    if active_view is None:
        render_nav()
    title_col, menu_col = st.columns([4, 1], vertical_alignment="bottom")
    # Keyed :data:`SAVE_RESTORE_KEY`, which is load-bearing twice over: the
    # spotlight tour aims at it, and the annotations panel's "save these too"
    # shortcut clicks `.st-key-tour_grp_save_restore button` to open this panel.
    # Both had nothing to find while UX-63 made this a page (a nav entry carries
    # no key of ours), so the shortcut clicked into thin air. `styles.py` widens
    # the panel off the same class: four sections is more than the 28 rem a menu
    # popover defaults to.
    session = menu_col.popover(
        "💾 Session",
        key=SAVE_RESTORE_KEY,
        width="stretch",
        help="Automatic recovery, a JSON backup of your settings and "
        "annotations, a full reset, and the debug tools.",
    )
    # Recovery and a JSON backup are deliberately separate. Recovery contains
    # the local dataset tables and happens automatically; the portable JSON is
    # user-triggered and intentionally omits those tables. The order makes that
    # distinction the panel's hierarchy rather than a tooltip-only caveat.
    recovery_cache = session.container(key="session_auto_recovery")
    recovery_cache.markdown("#### 🗄️ Automatic recovery")
    recovery_body = recovery_cache.container()

    save_restore = session.container(key="session_json_backup")
    save_restore.markdown("#### ⬇️ JSON backup")
    reset_session = session.container(key="session_reset")
    reset_session.markdown("#### ♻️ Reset")
    # UX-65: 🐛 Debug mode moved here from the foot of ❓ Help. Help is a set of
    # dialog-opening nav entries now and hosts no widgets at all, and the toggle
    # was never a link — it *is* `DEBUG_STATE_KEY`, a gate that has to keep
    # rendering every run or Streamlit drops it. Session is where the rest of
    # "what is this session holding" already lives.
    debug_gate = session.container(key="session_debug_tools")
    debug_gate.markdown("#### 🐛 Debug tools")
    debug_toggle = debug_gate.container()
    debug = debug_gate.container() if show_debug else None
    return TopMenu(
        save_restore=save_restore,
        recovery_cache=recovery_body,
        reset_session=reset_session,
        notices=st.container(key=NOTICES_KEY),
        title=title_col,
        debug=debug,
        debug_gate=debug_toggle,
    )
