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

from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_DATA, _VIEW_SCANPATH

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
}

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
    help: DeltaGenerator
    notices: DeltaGenerator
    #: The page heading's slot — the left half of the row the menu shares.
    #: ``app._render_about_panel`` fills it; see :func:`render_top_menu`.
    title: DeltaGenerator | None = None
    debug: DeltaGenerator | None = None


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
    selected = st.navigation(list(_PAGES.values()), position="top")
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


def render_top_menu(*, show_debug: bool = False) -> TopMenu:
    """Draw the native top nav + the settings bar, returning the bar's slots.

    Call this once, early in ``app.main`` — before any data loading, so the
    loaders' UI lands in the bar rather than after the page content.

    **The bar shares the title's row.** Once UX-38 got it down to two triggers,
    a whole page row for two buttons was the wrong trade, so the row is a
    ``st.columns`` split: the heading on the left, the triggers right-aligned
    over roughly where the Scanpath view's control rail begins. The split
    mirrors that view's ``[4, 1]`` plot/rail proportion so the buttons land above
    the rail rather than at some unrelated offset.

    It is deliberately *not* lifted into Streamlit's own header strip beside the
    nav. There is no supported way to put a widget there — ``st.navigation``
    takes pages and ``st.logo`` takes a logo — so it would mean ``position:
    fixed`` against an internal test id, with a right offset that has to clear a
    toolbar whose width depends on which buttons that deployment shows.

    Args:
        show_debug: Add the 🐛 Debug popover. Only ``?debug=1`` sessions want it
            (``debug_log.debug_enabled``).

    Returns:
        The bar's empty slots, plus the heading's — ``app._render_about_panel``
        fills ``title``. The active view is *not* among them: read it from
        :func:`render_nav`'s return value, which ``app.main`` calls for its
        dispatch; this function calls it only so the nav is drawn.
    """
    render_nav()
    title_col, menu_col = st.columns([4, 1], vertical_alignment="bottom")
    bar = menu_col.container(
        key=MENU_KEY,
        horizontal=True,
        horizontal_alignment="right",
        vertical_alignment="center",
    )
    # UX-38: ❓ Help leads. It is the one group a first-time user is looking for,
    # and it is the only one they can reach before they have a dataset.
    help_ = bar.popover(
        "❓ Help",
        help="The guided tour, the task tutorials, the FAQ, the documentation, "
        "and what this app is.",
    )
    # UX-38: 💾 Save & restore and 🗄️ Recovery cache merged into one **💾 Session**
    # group. Both answer the same question — *what is kept, and how do I get it
    # back* — differing only in whether the state travels to another machine,
    # which is why neither sat comfortably beside dataset setup or figure
    # styling. Two containers, not one body: `main` fills them at very different
    # points (Save & restore after the view renders, the cache after this run's
    # `save_local_state`), and creation order is what keeps them in this order.
    session = bar.popover(
        "💾 Session",
        key=SAVE_RESTORE_KEY,
        help="Save or restore your work, and see what is kept on this computer.",
    )
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
    debug = bar.popover("🐛 Debug") if show_debug else None
    return TopMenu(
        save_restore=save_restore,
        recovery_cache=recovery_cache,
        start_fresh=start_fresh,
        help=help_,
        notices=st.container(key=NOTICES_KEY),
        title=title_col,
        debug=debug,
    )
