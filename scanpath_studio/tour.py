"""First-visit welcome tour.

Two interchangeable styles, both introducing the app's main surfaces (data
sources, filters, viz controls, tabs, annotations) the first time a session
opens the app, re-playable any time via the sidebar's tutorial button:

- ``"spotlight"`` (default): a floating card that walks through the *actual*
  UI — each step scrolls the target section into view and pulses an outline
  around it. Rendered by ``render_spotlight_tour()`` at the end of ``main()``.
- ``"dialog"``: a self-contained multi-step ``st.dialog`` modal.

Switch styles with the ``TOUR_STYLE`` constant below.

Mechanics worth knowing before editing:

- Both styles run as *fragments*: Back/Next clicks rerun only the tour body,
  so navigation is instant instead of waiting for a full-app rerun (which
  re-renders the heavy plot embeds, ~10 s). The spotlight's Done / ✕ just
  clear ``tour_mode`` — the fragment then renders nothing and the card +
  highlight CSS disappear with it, again with no full rerun. The dialog's
  Skip/Done close the modal client-side (``_close_dialog_clientside``).
- The spotlight card streams to the browser *before* the heavy first-load
  work, but its Done / ✕ are ordinary Streamlit buttons — a click only
  schedules a rerun, which can't run until that ~10 s load finishes, so the
  card + dimming backdrop would linger the whole time. A same-origin listener
  (``_dismiss_listener_script``) hides them instantly on click; the button's
  native click still clears ``tour_mode`` once Streamlit catches up.
- Spotlight targets are ``.st-key-tour_grp_*`` classes from keyed wrapper
  containers around the sidebar sections (app.py / controls.py /
  annotations.py) plus Streamlit's stable ``data-testid``/``data-baseweb``
  attributes for the tab strip. Keep ``_SPOTLIGHT_STEPS`` in sync with them.
- ``tour_seen`` is set **before** the tour is shown, not when it's finished.
  For the dialog style, setting it on Done only would make an X-dismissal
  re-open the modal on the very next widget interaction (any full rerun
  re-calls ``maybe_show_welcome_tour``), making the X appear broken.
- The tour is suppressed for embeds (``?embed=true``) and deep links
  (``?source=…&participant=…``): those sessions arrive mid-workflow from an
  external tool and shouldn't be greeted by a tutorial.
- **"Don't show this again" (UX-12)** persists in a first-party *cookie*, not
  session state — there are no user accounts, and session state dies with the
  tab. A cookie is the one browser-side store Python can also *read*
  (``st.context.cookies``); ``localStorage`` would need a bidirectional custom
  component to get the value back to the server. The checkbox writes it via a
  same-origin script (``_tour_optout_script``); ``tour_opted_out()`` reads it.
  The replay button ignores the opt-out entirely, so the tour is never lost.
- **The FAQ (UX-15)** is the other half of the sidebar's Help group: a short
  ``st.dialog`` of recurring questions (``render_faq_button``), deliberately
  kept to a handful of answers with the complete version on the docs site
  (``docs/faq.md``). It is armed exactly like the tour — the button's
  ``on_click`` sets a request flag that ``maybe_show_faq`` serves early in
  ``main()`` — because the button renders at the *bottom* of ``main()``:
  opening the dialog from its return value made the modal wait out the whole
  rerun (~10 s of plot embeds) before appearing.
"""

from __future__ import annotations

import streamlit as st
from scanpath_studio.html_embed import embed_html_iframe

from .constants import CITATION

# UX-12: name of the first-party cookie holding the "don't show the welcome tour
# again" opt-out ("1" = opted out). One year, path=/, SameSite=Lax — no personal
# data, just a UI preference.
TOUR_OPTOUT_COOKIE = "sps_tour_optout"
_TOUR_OPTOUT_MAX_AGE = 365 * 24 * 60 * 60

# First-entry tutorial style: "spotlight" (floating card pointing at the real
# UI) or "dialog" (self-contained modal walkthrough). Both stay available in
# code; this only picks which one auto-opens / the replay button launches.
TOUR_STYLE = "spotlight"

# (title, markdown body) per step — keep bodies to a few lines each; the tour
# should take well under a minute.
_STEPS = [
    (
        "👀 Welcome to Scanpath Studio",
        "Visualize **eye movements in reading** — scanpaths drawn true-to-scale "
        "over the text. A demo dataset is loaded; this tour takes under a minute.",
    ),
    (
        "📂 Data",
        "Use the demo, or **upload your own** fixations / word tables "
        "(CSV / TSV / Parquet). Columns auto-detect — remap any field in the wizard.",
    ),
    (
        "🔍 Filter trials",
        "Narrow trials by participant or condition. Each tab has its own trial picker.",
    ),
    (
        "🎨 Visualization controls",
        "Toggle and style every layer — fixations, saccades, heatmap, word boxes, "
        "text. **Experimental Setup** sets your monitor so it stays true-to-scale.",
    ),
    (
        "🗂 Three views",
        "**Scanpath** (tick *Animate* to replay) · **Corpus Analysis** · "
        "**Data Inspection**. Bulk export is the **Export** subtab in Scanpath.",
    ),
    (
        "📝 Annotate & save",
        "Star, tag, and note trials, then filter to them. **💾 Save & restore** "
        "saves the whole setup + annotations to JSON. Replay this via "
        "**🎓 Show tutorial**. 👀",
    ),
]


def _close_dialog_clientside() -> None:
    """Hide the open dialog instantly by clicking its own ✕ from a tiny script.

    The documented way to close a dialog programmatically is a full-app
    ``st.rerun()`` — but on this app a full rerun re-renders the heavy plot
    embeds, so the modal lingered ~10 s after Skip/Done. Instead, run inside
    the (fast) dialog-fragment rerun and click the dialog's close button:
    the modal hides client-side immediately and Streamlit's normal dismiss
    handling syncs state in the background. ``st.iframe`` embeds are
    same-origin, so the script can reach the parent document.
    """
    embed_html_iframe(
        """<script>
        window.parent.document
            .querySelector('div[role="dialog"] button[aria-label="Close"]')
            ?.click();
        </script>""",
        height=0,
    )


def tour_opted_out() -> bool:
    """True when this browser asked never to be shown the welcome tour again.

    Reads the ``sps_tour_optout`` cookie (UX-12). Within a session the checkbox's
    own state wins, so ticking it takes effect without waiting for the browser to
    hand the cookie back on the next load. Defensive about ``st.context`` because
    bare-mode / AppTest runs have no request behind them.
    """
    if "tour_dont_show" in st.session_state:
        return bool(st.session_state["tour_dont_show"])
    try:
        return st.context.cookies.get(TOUR_OPTOUT_COOKIE) == "1"
    except Exception:  # no request context (bare mode, AppTest, headless import)
        return False


def _tour_optout_script(opted_out: bool) -> str:
    """A same-origin script that writes (or clears) the opt-out cookie.

    ``st.iframe`` embeds share the app's origin, so the parent document's
    ``cookie`` is writable from here — the only way to persist a preference
    browser-side without a user account.
    """
    if opted_out:
        value = f"{TOUR_OPTOUT_COOKIE}=1; max-age={_TOUR_OPTOUT_MAX_AGE}"
    else:
        value = f"{TOUR_OPTOUT_COOKIE}=; max-age=0"
    return (
        "<script>window.parent.document.cookie = "
        f'"{value}; path=/; SameSite=Lax";</script>'
    )


def _render_tour_optout() -> None:
    """The "Don't show this again" checkbox + the cookie write that backs it."""
    opted_out = st.checkbox(
        "Don't show this again",
        key="tour_dont_show",
        value=tour_opted_out(),
        help="Skip the tour on future visits. **🎓 Show tutorial** in the sidebar "
        "always brings it back.",
    )
    embed_html_iframe(_tour_optout_script(opted_out), height=0)


def _step_back() -> None:
    st.session_state["tour_step"] = max(0, st.session_state.get("tour_step", 0) - 1)


def _step_next() -> None:
    st.session_state["tour_step"] = st.session_state.get("tour_step", 0) + 1


@st.dialog("Quick tour", width="large")
def _tour_dialog() -> None:
    """One tour step + Back / Skip / Next navigation.

    Back/Next mutate ``tour_step`` via ``on_click`` callbacks — the callback
    runs before the fragment rerun, so the body re-renders at the new step.
    Skip/Done close the dialog client-side (see ``_close_dialog_clientside``).
    """
    step = min(st.session_state.get("tour_step", 0), len(_STEPS) - 1)
    title, body = _STEPS[step]
    st.subheader(title)
    st.markdown(body)
    st.progress((step + 1) / len(_STEPS), text=f"Step {step + 1} of {len(_STEPS)}")
    if step in (0, len(_STEPS) - 1):
        _render_tour_optout()

    back_col, skip_col, next_col = st.columns(3)
    back_col.button(
        "← Back",
        key="tour_back",
        width="stretch",
        disabled=step == 0,
        on_click=_step_back,
    )
    if step < len(_STEPS) - 1:
        if skip_col.button("Skip tour", key="tour_skip", width="stretch"):
            _close_dialog_clientside()
        next_col.button(
            "Next →",
            key="tour_next",
            width="stretch",
            type="primary",
            on_click=_step_next,
        )
    else:
        if next_col.button("✓ Done", key="tour_done", width="stretch", type="primary"):
            _close_dialog_clientside()


# Spotlight steps: (selector, title, body). ``selector`` is what gets the
# pulsing outline + scroll-into-view; None for the selector-less welcome step.
# Bodies are markdown, kept short — the card is ~400 px wide.
# Walks the whole Scanpath screen in reading order (UX-2): the plot → the
# selection/controls above it → the chips → the rail (view modes + controls) →
# the bottom panel → the left sidebar. Main-area steps pass ``in_sidebar: False``;
# the sidebar steps are kept LAST and contiguous so the sidebar opens once (the
# welcome step starts it collapsed). Keep selectors in sync with the keyed
# wrappers in tabs.py / app.py.
_SPOTLIGHT_STEPS = [
    {
        "selector": None,
        "title": "👀 Welcome to Scanpath Studio",
        "body": "Visualize **eye movements in reading** — scanpaths drawn "
        "true-to-scale over the text. A demo dataset is loaded; **Next** for a "
        "quick tour.",
    },
    {
        "selector": ".st-key-tour_grp_plot",
        "in_sidebar": False,
        "title": "🗺️ The scanpath",
        "body": "Each dot is a **fixation**, sized by duration; the lines are "
        "**saccades** between them. The reading text sits true-to-scale "
        "underneath.",
    },
    {
        "selector": ".st-key-tour_grp_trial_select",
        "in_sidebar": False,
        "title": "🎯 Pick a trial",
        "body": "Step through trials with the selector and ◀ ▶. **Filter by** Text "
        "or Participant to narrow the pool; **More** adds condition & annotation "
        "filters.",
    },
    {
        "selector": ".st-key-tour_grp_chips",
        "in_sidebar": False,
        "title": "🏷️ Trial at a glance",
        "body": "These chips show the trial's **identity, conditions, and summary "
        "stats**. Choose which fields appear — and drag to reorder — with "
        "**✏️ Edit chips** at the right of the strip.",
    },
    {
        "selector": ".st-key-scanpath_rail",
        "in_sidebar": False,
        "title": "🎬 Animate & compare",
        "body": "Top of the rail beside the plot: **Animate** replays the trial "
        "fixation by fixation, and **Compare** overlays a second scanpath. Each "
        "has a ⚙ popover for its settings.",
    },
    {
        "selector": ".st-key-tour_grp_viz_controls",
        "in_sidebar": False,
        "title": "🎨 Visualization",
        "body": "Toggle and style every layer — fixations, saccades, heatmap, word "
        "boxes, text. **Quick views** jump between Scanpath and Heatmap presets.",
    },
    {
        "selector": ".st-key-tour_grp_subtabs",
        "in_sidebar": False,
        "title": "📑 Per-trial panels",
        "body": "Below the plot: **📝 Annotations**, **Stimulus & questions**, "
        "**Export** (this trial or bulk), **🔎 Data Inspection**, and **🔗 Share** "
        "a deep link.",
    },
    {
        "selector": ".st-key-tour_grp_data_source",
        "in_sidebar": False,
        "title": "📂 Data source",
        "body": "Your **data source** (demo or your own upload) sits at the left "
        "of the filter row — ⚙️ beside it adds or removes datasets. Columns "
        "auto-detect; remap any field in the wizard.",
    },
    {
        "selector": ".st-key-tour_grp_save_restore",
        "title": "💾 Save, share & more",
        "body": "**💾 Save & restore** saves the whole setup + annotations to JSON. "
        "Switch to **📊 Corpus Analysis** from the top-right button. Replay this "
        "tour from **🎓 Show tutorial**. 👀",
    },
]

# The floating card: a keyed st.container pinned bottom-right via its
# `.st-key-tour_card` class. Plain strings (no .format) so the CSS braces
# don't need escaping.
_CARD_CSS = """
.st-key-tour_card {
    position: fixed;
    bottom: 1.25rem;
    right: 1.25rem;
    z-index: 999990;
    width: 410px;
    max-width: calc(100vw - 2.5rem);
    border-radius: 0.75rem;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    padding: 1rem 1.25rem 0.6rem;
}
/* The card title is an <h2> for a valid page heading outline (see the title
   render in render_spotlight_tour); pin it back to the original <h4> size so
   the card looks unchanged. */
.st-key-tour_card h2 {
    font-size: 24px !important;
    line-height: 1.3 !important;
    font-weight: 600 !important;
    letter-spacing: normal !important;
    padding: 0.25rem 1.5rem 0.75rem 0 !important;
    margin: 0 !important;
}
/* Close (✕) pinned to the card's top-right corner (top offset roughly matches
   the right one so it doesn't hug the edge). */
.st-key-tour_sp_close {
    position: absolute;
    top: 0.6rem;
    right: 0.5rem;
    width: auto;
    z-index: 1;
}
.st-key-tour_sp_close button {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    min-height: 0 !important;
    padding: 0.05rem 0.4rem !important;
    font-size: 1.05rem;
    line-height: 1;
    opacity: 0.55;
}
.st-key-tour_sp_close button:hover { opacity: 1; }
/* Vertical rhythm inside the card: body → progress → Back / Next footer (the
   gap around the progress bar is set on both sides — the column row is what
   actually carries it). The card's own bottom padding is trimmed to match. */
.st-key-tour_card [data-testid="stProgress"] {
    margin-top: 0.5rem;
    margin-bottom: 0.9rem;
}
.st-key-tour_card [data-testid="stHorizontalBlock"] { margin-top: 0.9rem; }
/* UX-12 "Don't show this again": a footnote between the progress bar and the
   footer, so it's muted and pulled tight rather than reading as another step. */
.st-key-tour_dont_show { margin-top: -0.5rem !important; }
.st-key-tour_dont_show label { opacity: 0.8; }
.st-key-tour_dont_show label p { font-size: 0.85rem !important; }
"""

# Welcome step only: center the card like a modal and dim the app behind it
# (the `.tour-backdrop` div is rendered only on that step). From step 2 on,
# the card drops to the bottom-right corner so it never covers the
# highlighted section.
_WELCOME_CSS = """
.st-key-tour_card {
    top: 50%;
    left: 50%;
    right: auto;
    bottom: auto;
    transform: translate(-50%, -50%);
    width: 500px;
}
.tour-backdrop {
    position: fixed;
    inset: 0;
    z-index: 999980;
    background: rgba(0, 0, 0, 0.45);
}
"""


def _exit_spotlight() -> None:
    st.session_state["tour_mode"] = None


def _dismiss_listener_script(
    selector: str | None,
    exit_keys: tuple[str, ...] = ("tour_sp_done", "tour_sp_close"),
) -> str:
    """JS that lets Done / ✕ close the tour *instantly*, even mid-load.

    The card streams to the browser early (before the ~10 s data/plot work),
    but its Done / ✕ are ordinary Streamlit buttons: a click only schedules a
    rerun, which Streamlit can't process until the in-flight first run
    finishes — so the card and its dimming backdrop linger for the whole load.

    This same-origin script attaches a plain ``click`` listener to those
    buttons that hides the card, backdrop, and highlight outline immediately
    via an injected ``!important`` stylesheet — no server roundtrip. The
    button's native click still fires too, so ``_exit_spotlight`` runs whenever
    Streamlit catches up and clears ``tour_mode`` durably. Re-arming the tour
    re-renders this script, which first drops any stale hide style so the
    replayed card is visible.
    """
    outline_clear = (
        f"{selector} {{ outline: none !important; animation: none !important; }}"
        if selector
        else ""
    )
    hide_css = (
        ".st-key-tour_card, .tour-backdrop { display: none !important; } "
        + outline_clear
    )
    btn_selectors = [f".st-key-{k} button" for k in exit_keys]
    return f"""<script>
    (function () {{
        const doc = window.parent.document;
        doc.getElementById("tour-instant-hide")?.remove();  // clear stale hide
        const hide = () => {{
            const s = doc.createElement("style");
            s.id = "tour-instant-hide";
            s.textContent = {hide_css!r};
            doc.head.appendChild(s);
            doc.querySelectorAll(".tour-backdrop").forEach((e) => e.remove());
        }};
        let tries = 0;
        (function wire() {{
            const btns = {btn_selectors!r}
                .map((sel) => doc.querySelector(sel)).filter(Boolean);
            if (!btns.length) {{
                if (++tries < 20) setTimeout(wire, 100);
                return;
            }}
            btns.forEach((b) => {{
                if (b.dataset.tourHideWired) return;
                b.dataset.tourHideWired = "1";
                b.addEventListener("click", hide, {{ once: true }});
            }});
        }})();
    }})();
    </script>"""


@st.fragment
def render_spotlight_tour() -> None:
    """Floating tour card + pulsing highlight for the current spotlight step.

    Call early in ``main()``, right after ``maybe_show_welcome_tour()``, so
    the card streams to the browser before the heavy data/plot work instead
    of seconds after the page opens. Replay clicks still activate it within
    the same run because the button arms the tour in its ``on_click``
    callback (``_arm_tour``), which runs before the rerun starts. Runs as a
    fragment: Back/Next/close rerun only this function, so the highlight moves
    instantly and ✕ makes the card + CSS vanish without a full-app rerun
    (the fragment then renders nothing, which clears its previous elements).
    """
    if st.session_state.get("tour_mode") != "spotlight":
        return
    n = len(_SPOTLIGHT_STEPS)
    step_idx = min(st.session_state.get("tour_step", 0), n - 1)
    step = _SPOTLIGHT_STEPS[step_idx]

    # BUG-6: fall back to the app's brand blue (matches the pinned theme
    # `.streamlit/config.toml` primaryColor), never Streamlit's default red, so
    # the tour accent stays consistent even if the runtime doesn't expose the
    # theme option.
    accent = st.get_option("theme.primaryColor") or "#1f77b4"
    # Card colors follow the active theme when the runtime exposes it
    # (st.context.theme, Streamlit ≥1.46); default to light otherwise.
    theme = getattr(getattr(st, "context", None), "theme", None)
    is_dark = getattr(theme, "type", "light") == "dark"
    bg, border = ("#262730", "#41434e") if is_dark else ("#ffffff", "#d5d6d9")

    highlight = ""
    if step["selector"]:
        highlight = f"""
{step["selector"]} {{
    outline: 3px solid {accent};
    outline-offset: 3px;
    border-radius: 0.5rem;
    animation: tour-pulse 1.6s ease-in-out infinite;
}}
@keyframes tour-pulse {{
    0%, 100% {{ box-shadow: 0 0 0 0 color-mix(in srgb, {accent} 50%, transparent); }}
    50% {{ box-shadow: 0 0 14px 7px color-mix(in srgb, {accent} 25%, transparent); }}
}}
"""
    st.markdown(
        "<style>"
        + _CARD_CSS
        + f".st-key-tour_card {{ background: {bg}; border: 1px solid {border}; }}"
        + (_WELCOME_CSS if step_idx == 0 else "")
        + highlight
        + "</style>",
        unsafe_allow_html=True,
    )
    if step_idx == 0:
        st.markdown('<div class="tour-backdrop"></div>', unsafe_allow_html=True)

    with st.container(key="tour_card"):
        # Close (✕) in the top-right corner — exits the tour like "Exit"/"Done"
        # (CSS pins it; the dismiss listener wires it for instant close too).
        st.button(
            "✕",
            key="tour_sp_close",
            on_click=_exit_spotlight,
            help="Close the tour",
        )
        # <h2> keeps the page heading outline valid (the card sits right under
        # the page <h1>; an <h4> here would be an h1→h4 jump). Sized back down
        # to the original compact look via `.st-key-tour_card h2` in _CARD_CSS.
        st.markdown(f"## {step['title']}")
        st.markdown(step["body"])
        st.progress((step_idx + 1) / n, text=f"Step {step_idx + 1} of {n}")
        # UX-12: the opt-out sits on the two steps where a user decides they're
        # finished with the tour — the welcome (bail out now) and the last step
        # (done, don't greet me again). Keeping it off the middle steps preserves
        # the card's tight vertical rhythm.
        if step_idx in (0, n - 1):
            _render_tour_optout()
        # No separate "Exit tour" button (UX-2a) — the ✕ in the corner closes the
        # tour, so the footer is just Back / Next (or Done on the last step).
        back_col, next_col = st.columns(2)
        back_col.button(
            "← Back",
            key="tour_sp_back",
            width="stretch",
            disabled=step_idx == 0,
            on_click=_step_back,
        )
        if step_idx < n - 1:
            next_col.button(
                "Next →",
                key="tour_sp_next",
                width="stretch",
                type="primary",
                on_click=_step_next,
            )
        else:
            next_col.button(
                "✓ Done",
                key="tour_sp_done",
                width="stretch",
                type="primary",
                on_click=_exit_spotlight,
            )

        # Make Done / ✕ hide the tour instantly, even while the app's first
        # run is still loading (the Streamlit click alone would only take
        # effect once that ~10 s run finishes). See _dismiss_listener_script.
        embed_html_iframe(_dismiss_listener_script(step["selector"]), height=0)

        if step["selector"]:
            # Bring the highlighted section into view. Same-origin iframe
            # trick as _close_dialog_clientside; no-op if the selector is
            # gone. Subtleties, all observed live:
            # - Sidebar steps first click Streamlit's expand control, since
            #   tour sessions start with the sidebar collapsed
            #   (spotlight_tour_pending → initial_sidebar_state).
            # - The find+scroll retries until the target is visible, riding
            #   out the sidebar-expand animation.
            # - Match the first *visible* element, not the first match:
            #   Streamlit keeps inactive tab panels laid out but
            #   visibility-hidden, so a selector can hit an invisible
            #   duplicate (e.g. the Raw Data panel's inner tab strip) and
            #   scroll the page to nowhere.
            # - No scrollIntoView: smooth gets cancelled by Streamlit's
            #   re-renders, and instant also scrolls the document, moving
            #   the main column for sidebar targets. Instead, center the
            #   target within its nearest scrollable ancestor only.
            # - Skip targets that are already fully on screen.
            # - The iframe stays INSIDE the fixed-position card: when it sat
            #   at the bottom of the main column, its (re)mount could yank
            #   the main scroller to the page bottom to reveal it.
            # Most keyed-wrapper targets live in the sidebar, but some (the viz
            # controls now sit in the Scanpath rail) are in the main area — let a
            # step opt out explicitly; otherwise fall back to the prefix rule.
            in_sidebar = step.get(
                "in_sidebar",
                bool(step["selector"])
                and step["selector"].startswith(".st-key-tour_grp_"),
            )
            embed_html_iframe(
                f"""<script>
                (function () {{
                    const doc = window.parent.document;
                    const win = doc.defaultView;
                    const findVisible = () =>
                        [...doc.querySelectorAll({step["selector"]!r})].find((e) => {{
                            const r = e.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) return false;
                            const cs = win.getComputedStyle(e);
                            return cs.visibility !== "hidden" && cs.display !== "none";
                        }});
                    let tries = 0;
                    (function attempt() {{
                        if ({str(in_sidebar).lower()}) {{
                            // The collapsed sidebar keeps its layout (nonzero
                            // rects), so gate on aria-expanded, not on
                            // findVisible(). Retries ride out hydration.
                            const sb = doc.querySelector(
                                'section[data-testid="stSidebar"]');
                            if (sb && sb.getAttribute("aria-expanded") !== "true") {{
                                doc.querySelector(
                                    'button[data-testid="stExpandSidebarButton"]'
                                )?.click();
                                if (++tries < 20) setTimeout(attempt, 150);
                                return;
                            }}
                        }}
                        const el = findVisible();
                        if (!el) {{
                            if (++tries < 20) setTimeout(attempt, 150);
                            return;
                        }}
                        for (let box = el.parentElement; box; box = box.parentElement) {{
                            const cs = win.getComputedStyle(box);
                            if (/(auto|scroll|overlay)/.test(cs.overflowY)
                                    && box.scrollHeight > box.clientHeight + 4) {{
                                const r = el.getBoundingClientRect();
                                const b = box.getBoundingClientRect();
                                const slack = 8;
                                if (r.top >= b.top - slack
                                        && r.bottom <= b.top + box.clientHeight + slack) {{
                                    return;  // already visible within its scroller
                                }}
                                box.scrollTop += r.top - b.top
                                    - Math.max(0, (box.clientHeight - r.height) / 2);
                                return;
                            }}
                        }}
                    }})();
                }})();
                </script>""",
                height=0,
            )
        else:
            # Welcome step: close the sidebar so the centered card sits over
            # a quiet page. initial_sidebar_state="collapsed" (configure_page)
            # covers fresh visitors, but the frontend's per-tab stored sidebar
            # state overrides it for returning tabs — so also click the
            # collapse control. Retries because a click during initial React
            # hydration is silently lost. The first sidebar step reopens it.
            embed_html_iframe(
                """<script>
                (function () {
                    const doc = window.parent.document;
                    let tries = 0;
                    (function attempt() {
                        const sb = doc.querySelector('section[data-testid="stSidebar"]');
                        if (!sb || sb.getAttribute("aria-expanded") !== "true") return;
                        (doc.querySelector(
                            '[data-testid="stSidebarCollapseButton"] button')
                            || doc.querySelector('section[data-testid="stSidebar"]'
                                + ' [data-testid="stBaseButton-headerNoPadding"]'))
                            ?.click();
                        if (++tries < 25) setTimeout(attempt, 200);
                    })();
                })();
                </script>""",
                height=0,
            )


def spotlight_tour_pending() -> bool:
    """True when this session is about to auto-open the spotlight tour.

    Read by ``app.configure_page`` *before* ``maybe_show_welcome_tour`` sets
    ``tour_seen``: tour sessions start with the sidebar collapsed so the
    centered welcome renders over a quiet page; the first sidebar step then
    opens it (the step script clicks Streamlit's expand control).
    """
    return (
        TOUR_STYLE == "spotlight"
        and not st.session_state.get("tour_seen")
        and not tour_suppressed(st.query_params)
        and not tour_opted_out()
    )


def tour_suppressed(query_params) -> bool:
    """True when the session shouldn't be greeted by the tour.

    Embeds (``?embed=true``) and deep links (``?source=…&participant=…``)
    arrive mid-workflow from an external tool. Takes the params as a mapping
    (rather than reading ``st.query_params`` itself) because AppTest can't
    inject query params — this stays unit-testable.
    """
    if (query_params.get("embed") or "").lower() in {"true", "1"}:
        return True
    return any(k in query_params for k in ("source", "participant", "trial", "tab"))


def _start_tour() -> None:
    """Kick off the configured tour style from step 0."""
    st.session_state["tour_step"] = 0
    if TOUR_STYLE == "spotlight":
        st.session_state["tour_mode"] = "spotlight"
    else:
        _tour_dialog()


def _arm_tour() -> None:
    """``on_click`` callback for the replay button: arm the tour from step 0.

    Callbacks run *before* the rerun, so the tour's render call early in
    ``main()`` — which executes long before the sidebar button — picks the
    request up within the same run. Dialogs can't be opened from callbacks,
    so the dialog style sets a request flag that ``maybe_show_welcome_tour``
    (the early call site) serves.
    """
    st.session_state["tour_step"] = 0
    if TOUR_STYLE == "spotlight":
        st.session_state["tour_mode"] = "spotlight"
    else:
        st.session_state["_tour_dialog_requested"] = True


def maybe_show_welcome_tour() -> None:
    """Start the welcome tour once per session, unless this is an embed/deep link.

    Call from ``main()`` after the URL presets are read (the suppression
    checks look at ``st.query_params``) but BEFORE the heavy data/plot work,
    immediately followed by ``render_spotlight_tour()`` — Streamlit streams
    elements in run order, so anything rendered after the data load appears
    seconds late. The dialog style opens here and overlays whatever renders
    after it; the spotlight style just arms ``tour_mode``.
    """
    if st.session_state.pop("_tour_dialog_requested", False):
        # Replay request from the sidebar button's on_click callback.
        _tour_dialog()
        return
    if st.session_state.get("tour_seen"):
        return
    if tour_suppressed(st.query_params):
        return
    if tour_opted_out():  # UX-12: "Don't show this again", persisted in a cookie
        return
    st.session_state["tour_seen"] = True  # before opening — see module docstring
    _start_tour()


def render_tour_replay_button() -> None:
    """Sidebar button that replays the tour from the first step.

    Deliberately ignores the UX-12 opt-out — "don't show this again" means "stop
    greeting me", not "take the tutorial away". The card's checkbox renders
    pre-ticked on a replay so the choice can be reversed from the same place.
    """
    st.sidebar.button(
        "🎓 Show tutorial",
        key="tour_replay",
        width="stretch",
        help="Replay the quick intro tour.",
        on_click=_arm_tour,
    )


# -----------------------------------------------------------------------------
# FAQ (UX-15) — the handful of questions that come up over and over, answered
# in-app so nobody has to leave to find out that (say) their measures are their
# eye-tracker's, not ours. Deliberately SHORT: the canonical, complete version
# is docs/faq.md on the docs site, linked from the bottom of the dialog. Keep
# these answers in sync with that page when either changes.
# -----------------------------------------------------------------------------

DOCS_FAQ_URL = f"{CITATION['docs_url']}faq/"
DOCS_TUTORIALS_URL = f"{CITATION['docs_url']}tutorials/"

# (question, markdown answer). Two-to-four lines each — anything longer belongs
# on the docs page.
_FAQ_ITEMS = [
    (
        "Why don't the measures match my eye-tracker's?",
        "Usually they do — because they **are** your eye-tracker's. Pre-computed "
        "EyeLink `IA_*` columns on your words table take precedence over anything "
        "this app would compute, matched by **exact column name**. A renamed "
        "export loses that match and falls back to the app's own computation "
        "(bounding-box fixation→word assignment, Rayner 1998 / Inhoff & Radach "
        "1998 definitions).",
    ),
    (
        "A column was mapped to the wrong field. Where do I fix it?",
        "🔎 **Data Inspection → Column mapping** — an editable form that "
        "re-derives everything in place, no re-upload. It can only offer columns "
        "that survived the import; anything dropped needs a re-upload.",
    ),
    (
        "What counts as a “trial”?",
        "One reading event — one participant reading one text once — and it is "
        "whatever your **Trial ID** mapping says it is. EyeLink's `TRIAL_INDEX` "
        "only identifies a trial *within* a reader, and the text id falls back to "
        "the trial id, so map your item column as **Text ID** if trial order was "
        "randomised.",
    ),
    (
        "What does drift correction do?",
        "It reassigns each fixation to the text **line** it most likely belongs "
        "to and snaps it there — the ten algorithms from Carr et al. (2021). It "
        "changes the figure, not your data. Apply one via **Fixations ⚙️ → Drift "
        "correction**, or compare all ten in the **📐 Line assignment** subtab.",
    ),
    (
        "Where does my data go?",
        "Nowhere. No accounts, no database, no analytics — files are read into "
        "memory and disappear when the session ends. Two caveats: a plain "
        "`streamlit run` listens on your whole network with no login (start it "
        "with `--server.address=127.0.0.1`), and the online demo runs on a server "
        "operated by Streamlit, not by us.",
    ),
    (
        "My uploaded data vanished after a refresh.",
        "Expected — uploads, wizard datasets and annotations live in session "
        "state, which dies with the session. Use **💾 Save & restore** for the "
        "plot config + annotations, and **⬇️ Download setup (JSON)** in the "
        "wizard for the column mapping; both are re-importable.",
    ),
    (
        "PNG / SVG / PDF export fails but HTML works.",
        "Static image export goes through Kaleido, which drives a headless "
        "Chrome that `pip install` doesn't provide. Run `plotly_get_chrome -y` "
        "once. **HTML** export is browser-free and always available.",
    ),
    (
        "How do I cite Scanpath Studio?",
        "See the **ℹ️ About** panel in this sidebar (and `CITATION.cff` in the "
        "repository). Cite the bundled demo data as OneStop Eye Movements too, "
        "and Carr et al. (2021) if you used the drift-correction algorithms.",
    ),
]


@st.dialog("❓ Frequently asked questions", width="large")
def _faq_dialog() -> None:
    """The in-app FAQ: short answers in expanders + links to the full docs.

    Kept short on purpose — this is the "before you file an issue" list, not a
    manual. The docs site carries the complete version (``docs/faq.md``), and
    the link buttons at the bottom are also the app's route into the docs from
    a help context.
    """
    st.caption(
        "Short answers to the questions that come up most. The full version — "
        "with the long explanations — lives on the documentation site."
    )
    for question, answer in _FAQ_ITEMS:
        with st.expander(question):
            st.markdown(answer)

    st.divider()
    docs_col, tutorials_col, close_col = st.columns(3)
    docs_col.link_button(
        "📚 Full FAQ ↗",
        DOCS_FAQ_URL,
        width="stretch",
        help="Every question, with the long answers. Opens in a new tab.",
    )
    tutorials_col.link_button(
        "🎓 Tutorials ↗",
        DOCS_TUTORIALS_URL,
        width="stretch",
        help="Task-by-task walkthroughs: load your own data, compare two "
        "readers, make a paper figure, run it headless. Opens in a new tab.",
    )
    if close_col.button("✓ Close", key="faq_close", width="stretch", type="primary"):
        _close_dialog_clientside()


def _arm_faq() -> None:
    """``on_click`` callback for the FAQ button: request the dialog.

    Dialogs can't be opened from a callback, so this only sets a flag that
    :func:`maybe_show_faq` — called early in ``main()`` — serves. Callbacks run
    *before* the rerun, so the request is picked up within the same run.
    """
    st.session_state["_faq_dialog_requested"] = True


def maybe_show_faq() -> None:
    """Open the FAQ dialog if the sidebar button armed it.

    Call from ``main()`` next to :func:`maybe_show_welcome_tour`, BEFORE the
    heavy data / plot work. The button sits at the *bottom* of ``main()``, so
    opening the dialog from its return value meant the modal only streamed to
    the browser after the whole rerun — including the ~10 s plot embeds — had
    finished. Served here it appears immediately and overlays whatever renders
    after it.
    """
    if st.session_state.pop("_faq_dialog_requested", False):
        _faq_dialog()


def render_faq_button() -> None:
    """Sidebar button that opens the in-app FAQ dialog.

    Sits in the sidebar's Help group next to :func:`render_tour_replay_button`,
    and is armed the same way: an ``on_click`` callback sets a request flag that
    the early :func:`maybe_show_faq` call serves, so the modal doesn't wait on
    the heavy data / plot work this button renders after.
    """
    st.sidebar.button(
        "❓ FAQ",
        key="faq_open",
        width="stretch",
        help="Short answers to common questions, plus a link to the full docs.",
        on_click=_arm_faq,
    )


# -----------------------------------------------------------------------------
# Dataset-setup guide (the "📂 Set up your dataset" wizard's own walkthrough).
#
# A bottom-right floating card (``render_spotlight_wizard_guide``) that walks the
# user through the upload wizard while they fill it in — the same card style and
# instant-dismiss machinery as the welcome spotlight tour, but keyed on its own
# step counter (``wizard_guide_step``) and run under ``tour_mode == "wizard"`` so
# the two never collide. Auto-opens once per session the first time the wizard is
# shown (unless suppressed for embeds/deep-links, or the welcome spotlight tour
# is still on screen so the two don't stack), and is replayable from the
# wizard's "❓ Show setup guide" button.
# -----------------------------------------------------------------------------

# (title, markdown body) per step — one per part of the wizard, in order.
_WIZARD_GUIDE_STEPS = [
    (
        "📂 Set up your dataset",
        "Turn your eye-tracking tables into an interactive dataset. The wizard "
        "**auto-advances** — only the step you still need stays open. Follow along "
        "with **Next**, or **Skip** to dive in.",
    ),
    (
        "1 · Name it",
        "Pick a name you'll recognise — it appears in **Data source** so you can "
        "switch back later without re-uploading.",
    ),
    (
        "2 · Experimental setup",
        "Set the recording **monitor resolution** (and font) so word boxes and "
        "fixations stay **true-to-scale**. Defaults to 1440p; tune it anytime.",
    ),
    (
        "3 · Upload",
        "Add your **Fixations** and/or **Words / IA** tables (CSV / TSV / Parquet; "
        "several files or either alone). Each upload previews its first rows.\n\n"
        "> 💡 Large dataset? Run locally: `pip install scanpath-studio`.",
    ),
    (
        "4 · Map columns",
        "Columns auto-detect — confirm or override the **trial id**, optional "
        "participant / text ids, and the required fixation/word columns. "
        "**Restore a saved setup** re-applies an earlier mapping.",
    ),
    (
        "5 · Keep & finish",
        "Optionally keep extra columns or filter fields. **⬇️ Download setup** "
        "saves the mapping; **✅ Add dataset** stores it and switches to it. 👀",
    ),
]


def _wizard_guide_back() -> None:
    st.session_state["wizard_guide_step"] = max(
        0, st.session_state.get("wizard_guide_step", 0) - 1
    )


def _wizard_guide_next() -> None:
    st.session_state["wizard_guide_step"] = (
        st.session_state.get("wizard_guide_step", 0) + 1
    )


def _exit_wizard_guide() -> None:
    st.session_state["tour_mode"] = None


@st.fragment
def render_spotlight_wizard_guide() -> None:
    """Floating bottom-right card walking through the dataset-setup wizard.

    The setup guide as a spotlight card (like the welcome tour) rather than a
    blocking modal, so it sits in the corner and the user follows along while
    filling in each wizard step. Shares the welcome tour's card CSS + instant
    dismiss machinery but uses its own ``wizard_guide_step`` counter and
    ``tour_mode == "wizard"`` so the two never collide. No backdrop / highlight /
    scroll — the steps are descriptive, not anchored to specific controls.

    Call early in the wizard's render (``app._render_data_setup``) so the card
    streams to the browser before the heavy upload/normalize work. Runs as a
    fragment: Back/Next/Skip rerun only this card.
    """
    if st.session_state.get("tour_mode") != "wizard":
        return
    n = len(_WIZARD_GUIDE_STEPS)
    step_idx = min(st.session_state.get("wizard_guide_step", 0), n - 1)
    title, body = _WIZARD_GUIDE_STEPS[step_idx]

    theme = getattr(getattr(st, "context", None), "theme", None)
    is_dark = getattr(theme, "type", "light") == "dark"
    bg, border = ("#262730", "#41434e") if is_dark else ("#ffffff", "#d5d6d9")
    st.markdown(
        "<style>"
        + _CARD_CSS
        + f".st-key-tour_card {{ background: {bg}; border: 1px solid {border}; }}"
        + "</style>",
        unsafe_allow_html=True,
    )

    with st.container(key="tour_card"):
        # <h2> for a valid heading outline; sized down via `.st-key-tour_card h2`.
        st.markdown(f"## {title}")
        st.markdown(body)
        st.progress((step_idx + 1) / n, text=f"Step {step_idx + 1} of {n}")
        back_col, exit_col, next_col = st.columns(3)
        back_col.button(
            "← Back",
            key="wizard_sp_back",
            width="stretch",
            disabled=step_idx == 0,
            on_click=_wizard_guide_back,
        )
        if step_idx < n - 1:
            exit_col.button(
                "Skip",
                key="wizard_sp_exit",
                width="stretch",
                on_click=_exit_wizard_guide,
            )
            next_col.button(
                "Next →",
                key="wizard_sp_next",
                width="stretch",
                type="primary",
                on_click=_wizard_guide_next,
            )
        else:
            next_col.button(
                "✓ Got it",
                key="wizard_sp_done",
                width="stretch",
                type="primary",
                on_click=_exit_wizard_guide,
            )
        # Hide the card instantly on Skip/Done, even while the wizard's first run
        # is still loading (see _dismiss_listener_script).
        embed_html_iframe(
            _dismiss_listener_script(
                None, exit_keys=("wizard_sp_exit", "wizard_sp_done")
            ),
            height=0,
        )


def _arm_wizard_guide() -> None:
    """``on_click`` callback for the wizard's "❓ Show setup guide" button.

    Arms the bottom-right guide card from step 0. Callbacks run before the rerun,
    so ``render_spotlight_wizard_guide`` (called as the wizard renders) picks it
    up on the same run — mirroring ``_arm_tour`` for the welcome tour.
    """
    st.session_state["wizard_guide_step"] = 0
    st.session_state["tour_mode"] = "wizard"


def maybe_show_wizard_guide() -> None:
    """Arm the dataset-setup guide automatically the first time the wizard is
    shown in a session (the replay button arms it on demand via ``_arm_wizard_guide``).

    Call as the active wizard renders, immediately followed by
    ``render_spotlight_wizard_guide()`` which draws the card. The auto-open is
    skipped for embeds/deep-links and while the welcome spotlight tour is still
    on screen, so the two walkthroughs never stack. ``wizard_guide_seen`` is set
    *before* arming (mirroring ``tour_seen``) so a dismissal doesn't re-open it
    on the next rerun.
    """
    if st.session_state.get("wizard_guide_seen"):
        return
    if (
        tour_suppressed(st.query_params)
        or st.session_state.get("tour_mode") == "spotlight"
    ):
        return
    st.session_state["wizard_guide_seen"] = True  # before arming — see docstring
    st.session_state["wizard_guide_step"] = 0
    st.session_state["tour_mode"] = "wizard"


def render_wizard_guide_button(host) -> None:
    """A button inside the wizard that (re)opens the setup guide from step 1."""
    host.button(
        "❓ Show setup guide",
        key="wizard_guide_replay",
        help="Walk through the dataset setup, step by step.",
        on_click=_arm_wizard_guide,
    )
