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

**DATA-26 took two groups off this bar.** ⚙️ Configure and 🧹 Preprocessing are
now sections of the **Data** page (``constants._VIEW_DATA``), because setting a
dataset up was split across a menu group and a subtab on the other side of the
app. Their widgets keep the every-run execution the popovers gave them: the page
container is built every run and merely hidden off-screen when another view is
active (``constants.DATA_PAGE_OFFSCREEN_KEY`` + the ``display: none`` rule in
``styles.py``). What is left here is genuinely session-wide: 💾 Save & restore ·
🗄️ Recovery cache · ❓ Help (+ 🐛 Debug).

**Consequences for panel authors.** A popover nests neither an expander nor
another popover, so a group that used to wrap itself in
``st.sidebar.expander("<title>")`` now renders **bare** into its slot — the
popover trigger *is* the disclosure, and repeating the title inside it would
just be the label twice. See ``app._preprocessing_settings``,
``app._render_recovery_cache_panel`` and ``tabs._render_save_restore_expander``.

Widths need no CSS: the old sidebar was ~21 rem, while a popover body is
28–32 rem (``styles.py``), so every panel here is *roomier* than it was.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import streamlit as st

from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    _VIEW_SESSION,
    SESSION_PAGE_KEY,
    SESSION_PAGE_OFFSCREEN_KEY,
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
    # UX-63: the two menu groups joined the nav rather than sitting in a row of
    # popovers beneath it. Last, after the three analysis views — they are
    # chrome, visited on purpose and rarely, and putting them earlier would cost
    # every existing user their aim at the views they use.
    _VIEW_SESSION: ("Session", "💾", "session"),
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

#: The 💾 Session trigger keeps the tour's historical key: the spotlight
#: selector (``tour._SPOTLIGHT_STEPS``) and the "jump to Save & restore"
#: affordance in ``annotations.py`` both look for ``.st-key-tour_grp_save_restore``.
#: UX-38 merged 💾 Save & restore and 🗄️ Recovery cache under it rather than
#: renaming the key — the two blocks are still there, one popover down.
SAVE_RESTORE_KEY = "tour_grp_save_restore"


@dataclass(frozen=True)
class TopMenu:
    """The reserved slots of one rendered menu bar.

    Each attribute is an empty container that downstream code fills by
    ``host=``, in whatever order the load happens to reach it.
    """

    save_restore: DeltaGenerator
    recovery_cache: DeltaGenerator
    #: BUG-28's escape hatches — back to the demo, and clear the computed cache.
    start_fresh: DeltaGenerator
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

    **UX-63 moved the two groups into the nav.** They were popovers in a
    ``st.columns`` row *under* the nav; they are now entries of the nav itself,
    so the header carries one menu — Scanpath · Corpus Analysis · Data ·
    Session · Help — instead of a menu plus a row of buttons beneath it. The
    earlier note here said this was impossible without ``position: fixed``
    against Streamlit's internals; that was true of lifting a *widget* into the
    header strip, and false of the route taken: ``st.navigation`` takes pages,
    and these two are now pages.

    **They still render on every run**, into a container that is off-screen
    unless its entry is active — the same trick DATA-26 uses for the Data page.
    That is not incidental: a popover executes every run, and Streamlit drops a
    widget's key at the end of any run in which it did not render, so content
    that only rendered while its own page was open would silently reset the 🐛
    Debug gate and the persistence pause toggle between visits. Rendering always
    and hiding with CSS keeps exactly the popovers' semantics, so every
    ``host=`` fill site in ``app.main`` is unchanged.

    Args:
        show_debug: Add the 🐛 Debug block. Only debug sessions want it
            (``debug_log.debug_enabled``).
        active_view: The entry the nav currently has selected, from
            :func:`render_nav`. Decides which of the two pages is visible.

    Returns:
        The pages' empty slots, plus ``title`` — ``app._render_about_panel``
        fills it.
    """
    active = active_view if active_view is not None else render_nav()
    title_col, _menu_col = st.columns([4, 1], vertical_alignment="bottom")
    # One container per group, keyed by whether it is the active view. `styles`
    # hides the `*_offscreen` twins; the widgets inside keep executing.
    session = st.container(
        key=SESSION_PAGE_KEY if active == _VIEW_SESSION else SESSION_PAGE_OFFSCREEN_KEY
    )
    if active == _VIEW_SESSION:
        session.subheader("💾 Session")
        session.caption(
            "Save or restore your work, and see what is kept on this computer."
        )
    # UX-38: 💾 Save & restore and 🗄️ Recovery cache merged into one **💾 Session**
    # group. Both answer the same question — *what is kept, and how do I get it
    # back* — differing only in whether the state travels to another machine,
    # which is why neither sat comfortably beside dataset setup or figure
    # styling. Two containers, not one body: `main` fills them at very different
    # points (Save & restore after the view renders, the cache after this run's
    # `save_local_state`), and creation order is what keeps them in this order.
    # UX-53: one short line per block, with the detail folded into its `?` —
    # the panel opens on a menu click, so nobody arrives here to read prose.
    save_restore = session.container()
    save_restore.markdown("**💾 Save & restore**")
    save_restore.caption(
        "One JSON file — opens on any machine.",
        help="Holds the plot configuration, every annotation, the data source "
        "and the column mapping. On restore, everything that fits the loaded "
        "data is re-applied and the rest is skipped.",
    )
    recovery_cache = session.container()
    recovery_cache.divider()
    recovery_cache.markdown("**🗄️ Recovery cache**")
    recovery_cache.caption(
        "Kept on *this* computer, so a refresh doesn't lose your work.",
        help="Uploaded datasets, column mappings, view settings and "
        "annotations are written to this computer only — nothing is sent "
        "anywhere.",
    )
    # BUG-28: the two "get me back to something that works" actions, reachable
    # from every view — the analysis views have no source picker, and a dataset
    # the pipeline rejects is exactly when the 🗂️ Data page is the last place
    # the user wants to be sent. Third block of 💾 Session rather than a group of
    # its own: it answers the same question ("what is kept, and how do I get it
    # back") from the other end.
    start_fresh = session.container()
    start_fresh.divider()
    start_fresh.markdown("**🧹 Start fresh**")
    start_fresh.caption(
        "Back to a known-good state without losing your uploads.",
        help="Reload the bundled demo with a freshly detected column mapping, "
        "or recompute everything from the data already loaded.",
    )
    # UX-65: 🐛 Debug mode moved here from the foot of ❓ Help. Help is a set of
    # dialog-opening nav entries now and hosts no widgets at all, and the toggle
    # was never a link — it *is* `DEBUG_STATE_KEY`, a gate that has to keep
    # rendering every run or Streamlit drops it. Session is where the rest of
    # "what is this session holding" already lives.
    debug_gate = session.container()
    debug_gate.divider()
    debug = session.container() if show_debug else None
    return TopMenu(
        save_restore=save_restore,
        recovery_cache=recovery_cache,
        start_fresh=start_fresh,
        notices=st.container(key=NOTICES_KEY),
        title=title_col,
        debug=debug,
        debug_gate=debug_gate,
    )
