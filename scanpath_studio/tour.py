"""First-visit welcome tour.

Two interchangeable styles, both introducing the app's main surfaces (data
sources, filters, viz controls, tabs, annotations) the first time a session
opens the app, re-playable any time from the ❓ Help menu's tutorial button:

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
  containers around the page + menu sections (app.py / controls.py /
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
- **The FAQ (UX-15)** is the other half of the ❓ Help menu group: a short
  ``st.dialog`` of recurring questions (``render_faq_button``), deliberately
  kept to a handful of answers with the complete version on the docs site
  (``docs/faq.md``). It is armed exactly like the tour — the button's
  ``on_click`` sets a request flag that ``maybe_show_faq`` serves early in
  ``main()`` — because the button renders at the *bottom* of ``main()``:
  opening the dialog from its return value made the modal wait out the whole
  rerun (~10 s of plot embeds) before appearing.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from scanpath_studio.html_embed import embed_html_iframe
from scanpath_studio.menu import NAV_SELECTOR

from .constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    CITATION,
    drift_correction_enabled,
    similarity_enabled,
)

# UX-12: name of the first-party cookie holding the "don't show the welcome tour
# again" opt-out ("1" = opted out). One year, path=/, SameSite=Lax — no personal
# data, just a UI preference.
TOUR_OPTOUT_COOKIE = "sps_tour_optout"
_TOUR_OPTOUT_MAX_AGE = 365 * 24 * 60 * 60

# First-entry tutorial style: "spotlight" (floating card pointing at the real
# UI) or "dialog" (self-contained modal walkthrough). Both stay available in
# code; this only picks which one auto-opens / the replay button launches.
TOUR_STYLE = "spotlight"


@dataclass(frozen=True)
class TutorialStep:
    """One reusable spotlight step in a task-oriented tutorial."""

    title: str
    body: str
    selector: str
    view: str = _VIEW_SCANPATH
    subtab: str | None = None
    optional: bool = False


@dataclass(frozen=True)
class TutorialDefinition:
    """Registry entry shown by the Help chooser."""

    id: str
    title: str
    outcome: str
    estimated_time: str
    prerequisite: str
    availability: str
    completion_test: str
    docs_url: str
    steps: tuple[TutorialStep, ...]


DOCS_TUTORIALS_URL = f"{CITATION['docs_url']}tutorials/"

# PRE-21 hides NLD similarity scoring unless SCANPATH_EXPERIMENTAL=1, so the
# comparison tutorial must not promise a ranking this build does not show —
# the same honesty rule `faq_items()` applies to the drift-correction answers.
# The flag is an environment variable, fixed for the life of the process, so
# resolving it once at import is equivalent to checking it per render.
_SIMILARITY_SENTENCE = (
    " Similarity scores (NLD) rank the closest readings for you."
    if similarity_enabled()
    else ""
)

TUTORIALS: tuple[TutorialDefinition, ...] = (
    TutorialDefinition(
        id="load_inspect",
        title="Load and verify a dataset",
        outcome="Finish with the parsed words, fixations, and mapping visibly checked.",
        estimated_time="3 min",
        prerequisite="A demo or uploaded dataset",
        availability="always",
        completion_test="Data page opened",
        docs_url=f"{DOCS_TUTORIALS_URL}#load-your-own-data",
        steps=(
            TutorialStep(
                "Choose the data source",
                "Everything about the dataset lives on the 🗂️ **Data** page, in the "
                "order the pipeline uses it. Start at **📂 Data source** — keep the "
                "demo, or use ➕ to add your own tables.",
                ".st-key-tour_grp_data_source",
                view=_VIEW_DATA,
            ),
            TutorialStep(
                "Check the column mapping",
                "**🔤 Column mapping** is the one thing that decides what every "
                "measure downstream is computed from. Rows marked ✨ were "
                "auto-detected; override any that guessed wrong.",
                ".st-key-tutorial_column_mapping",
                view=_VIEW_DATA,
            ),
            TutorialStep(
                "Verify what was parsed",
                "**🔎 What's in this dataset** opens on the counts — the quickest "
                "check that the mapping worked. The raw and derived tables fold "
                "open below them.",
                ".st-key-tutorial_data_inspection",
                view=_VIEW_DATA,
            ),
            TutorialStep(
                "Check one trial id is one reading",
                "**🧾 Trial identity** checks the whole dataset, before any "
                "filtering, and says so either way. A warning here means the "
                "Trial ID above is missing a column — several readings are being "
                "drawn as one scanpath, which renders happily as a reading with a "
                "lot of regressions.",
                ".st-key-tutorial_trial_identity",
                view=_VIEW_DATA,
            ),
            TutorialStep(
                "Decide on preprocessing",
                "**🧹 Preprocessing** (bottom of the page) can soft-exclude or merge "
                "short fixations before anything is measured. It is off by default, "
                "applies to every view, and never discards your original rows.",
                ".st-key-tutorial_preprocessing",
                view=_VIEW_DATA,
                optional=True,
            ),
        ),
    ),
    TutorialDefinition(
        id="filter_annotate",
        title="Filter and mark trials",
        outcome="Finish with reviewed trials annotated and ready for ID export.",
        estimated_time="4 min",
        prerequisite="At least one trial",
        availability="has_trials",
        completion_test="Export panel reached after annotation review",
        docs_url=f"{DOCS_TUTORIALS_URL}#filter-and-annotate-trials",
        steps=(
            TutorialStep(
                "Narrow the review pool",
                "Use **Filter by** and **More** for participant, condition, favorites, "
                "or tags. This tutorial only points; it never changes a filter.",
                ".st-key-tour_grp_narrow_by",
            ),
            TutorialStep(
                "Review one trial at a time",
                "One picker for every dataset: the **Trial id** dropdown, a scrubbing "
                "slider showing *index / total*, and ◀ ▶ to step through the pool "
                "you just narrowed.",
                ".st-key-tour_grp_trial_picker",
            ),
            TutorialStep(
                "Move between screens",
                "A multipart trial (one reading spread over several screens) adds a "
                "screen navigator under the picker. Each screen is its own "
                "coordinate space, so nothing is ever drawn across two of them.",
                ".st-key-tour_grp_screen_picker",
                optional=True,
            ),
            TutorialStep(
                "Annotate at the right scope",
                "Star, tag, or note the parent trial. Multipart data can instead attach "
                "a separate annotation to the active screen.",
                ".st-key-tutorial_annotations",
                subtab="📝 Annotations",
            ),
            TutorialStep(
                "Export the marked result",
                "Open **Export** and choose the filtered scope and tabular files. "
                "Screen identity is retained in multipart exports.",
                ".st-key-tutorial_export",
                subtab="Export",
            ),
        ),
    ),
    TutorialDefinition(
        id="publication_figure",
        title="Build a publication figure",
        outcome="Finish at a ready figure download with a reproducible configuration.",
        estimated_time="4 min",
        prerequisite="Words or fixations for a selected trial",
        availability="has_visual_data",
        completion_test="Export panel reached",
        docs_url=f"{DOCS_TUTORIALS_URL}#make-a-paper-ready-figure",
        steps=(
            TutorialStep(
                "Choose the visual language",
                "Use quick views, palette, and the layer controls. Heatmap and scanpath "
                "are settings on the same figure, not separate data transformations.",
                ".st-key-tour_grp_viz_controls",
            ),
            TutorialStep(
                "Decide static or animated",
                "Use **Animate** only when motion is the outcome. Multipart replay keeps "
                "screen boundaries explicit and draws no connector between canvases.",
                ".st-key-tour_grp_view_modes",
            ),
            TutorialStep(
                "Download and preserve settings",
                "Open **Export** for PNG/SVG/HTML or bulk output. Include the plot config "
                "when the figure must be reproducible later.",
                ".st-key-tutorial_export",
                subtab="Export",
            ),
            TutorialStep(
                "Keep the figure reproducible",
                "**🔗 Share** turns the exact configuration into a link, and 💾 "
                "**Session** saves it (with your annotations) as JSON. Either one "
                "reproduces this figure later — the PNG on its own does not.",
                ".st-key-tutorial_share",
                subtab="🔗 Share",
                optional=True,
            ),
        ),
    ),
    TutorialDefinition(
        id="compare_readings",
        title="Compare readings of one text",
        outcome=(
            "Finish with the other readings of one text side by side, at one scale."
        ),
        estimated_time="3 min",
        prerequisite="Two readings sharing a text (and screen for multipart data)",
        availability="has_comparable_readings",
        completion_test="Comparisons panel reached",
        docs_url=f"{DOCS_TUTORIALS_URL}#compare-two-readers",
        steps=(
            TutorialStep(
                "Choose the reference reading",
                "Pick the reading that should anchor the comparison. The comparison "
                "panel reuses this exact parent trial and active screen.",
                ".st-key-tour_grp_trial_picker",
            ),
            TutorialStep(
                "Compare like with like",
                "Open **🔬 Comparisons** and pick the column that separates the "
                "readings — participant, session, condition. You get the other "
                "readings of *this* text at the same scale, so the grid compares "
                "like with like." + _SIMILARITY_SENTENCE,
                ".st-key-tutorial_comparisons",
                subtab="🔬 Comparisons",
            ),
        ),
    ),
    TutorialDefinition(
        id="explore_corpus",
        title="Explore a corpus question",
        outcome=(
            "Finish having answered one worked question — how a reader's average "
            "fixation duration moved across the experiment."
        ),
        estimated_time="4 min",
        prerequisite="Variation across trials, readers, or texts",
        availability="has_corpus_variation",
        completion_test="Corpus Analysis opened",
        docs_url=f"{DOCS_TUTORIALS_URL}#explore-the-corpus",
        # UX-40 round 2: this was two steps where the others are four or five,
        # and it named the three subtabs without answering anything. It now walks
        # one real question end to end — the user's own example — because "here
        # are three subtabs" is a menu, not a tutorial.
        steps=(
            TutorialStep(
                "Switch analysis level",
                "Open **Corpus Analysis** to aggregate instead of inspecting one trial. "
                "Your loaded data and filters stay in place, so whatever you narrowed "
                "to on the Scanpath view is what gets aggregated here.",
                NAV_SELECTOR,
            ),
            TutorialStep(
                "Pick the question, not the chart",
                "Three subtabs, three shapes of question. **Per text** — one text, many "
                "readers. **Per reader** — one reader, all their trials. **Groups** — a "
                "cohort, or two compared. Our worked question is *did this reader speed "
                "up over the experiment?*, so open **Per reader**.",
                ".st-key-tutorial_corpus_subtabs",
                view=_VIEW_CORPUS,
            ),
            TutorialStep(
                "Choose the reader and the view",
                "Pick the reader on the left, then set **View** to **Per-trial trend**. "
                "That plots one point per trial in presentation order — the whole "
                "experiment on one axis, rather than a single trial's dynamics.",
                ".st-key-tutorial_per_reader_view",
                view=_VIEW_CORPUS,
            ),
            TutorialStep(
                "Read average fixation duration across the experiment",
                "Set the measure to **fixation duration**; each point is that trial's "
                "mean. A downward slope is the reader settling in — but check the "
                "spread and the trial count before believing it, because one short "
                "trial moves a mean a long way.",
                ".st-key-tutorial_corpus_analysis",
                view=_VIEW_CORPUS,
            ),
            TutorialStep(
                "Put it against the cohort",
                "**Distribution vs cohort** answers the companion question — is this "
                "reader unusual, or is the whole cohort like this? Read the sample size "
                "with the effect, never the plotted mean on its own.",
                ".st-key-tutorial_per_reader_view",
                view=_VIEW_CORPUS,
                optional=True,
            ),
        ),
    ),
)

_TUTORIAL_BY_ID = {tutorial.id: tutorial for tutorial in TUTORIALS}

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
        "🎛️ Plot controls",
        "Toggle and style every layer — fixations, saccades, heatmap, word boxes, "
        "text. **📐 Figure & canvas → 🖥️ Screen & geometry** sets your monitor so "
        "it stays true-to-scale.",
    ),
    (
        "🗂 Three views",
        "**Scanpath** (tick *Animate* to replay) · **Corpus Analysis** · "
        "**Data** (set up and inspect the dataset). Bulk export is the "
        "**Export** subtab in Scanpath.",
    ),
    (
        "📝 Annotate & save",
        "Star, tag, and note trials, then filter to them. **💾 Session** "
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
        help="Skip the tour on future visits. **🎓 Show tutorial** under ❓ Help "
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
# the bottom panel → the top menu bar. There is no `in_sidebar` flag any more:
# every target is in the page or on the menu bar, so no step has to expand a
# panel before it can scroll to it. Keep selectors in sync with the keyed
# wrappers in tabs.py / app.py / menu.py.
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
        "title": "🗺️ The scanpath",
        "body": "This is the main plot. Each dot is a **fixation**, sized by "
        "duration; the lines are **saccades** between them.",
    },
    {
        "selector": ".st-key-tour_grp_data_source",
        "title": "📂 Data source",
        "body": "Your **data source** (demo or your own upload) sits at the left "
        "of the filter row — ➕ beside it adds or removes datasets. Columns "
        "auto-detect; remap any field in the wizard.",
    },
    # UX-34: narrowing comes before picking, both on screen (the Filter-by row
    # sits above the picker) and in the workflow, so the spotlight now walks them
    # top-to-bottom instead of jumping down to the picker and back up. Each step
    # targets its own container — they used to share one wrapper, so both lit up
    # the whole block.
    {
        "selector": ".st-key-tour_grp_narrow_by",
        "title": "🔍 Narrow the pool",
        "body": "**Filter by** Text or Participant to shrink the trial list; "
        "**More** adds condition & annotation filters (favorites, tags).",
    },
    {
        "selector": ".st-key-tour_grp_trial_picker",
        "title": "🎯 Pick a trial",
        "body": "Step through trials with the selector and ◀ ▶, or scrub the "
        "slider — it shows the trial's position and id.",
    },
    {
        "selector": ".st-key-tour_grp_chips",
        "title": "🏷️ Trial at a glance",
        "body": "These chips show the trial's **identity, conditions, and summary "
        "stats**. Choose which fields appear — and drag to reorder — with "
        "**✏️ Edit chips** at the right of the strip.",
    },
    {
        "selector": ".st-key-tour_grp_view_modes",
        "title": "🎬 Animate & compare",
        "body": "**Animate** replays the trial fixation by fixation, and "
        "**Compare** adds a second scanpath beside it — from this dataset or, "
        "via **Compare with**, from another one. Each has a ⚙ popover for its "
        "settings.",
    },
    {
        "selector": ".st-key-tour_grp_viz_controls",
        "title": "🎛️ Plot controls",
        "body": "Toggle and style every layer — fixations, saccades, heatmap, word "
        "boxes, text. **Quick views** jump between Scanpath and Heatmap presets.",
    },
    {
        "selector": ".st-key-tour_grp_subtabs",
        "title": "📑 Per-trial panels",
        "body": "Below the plot: **📝 Annotations**, **Stimulus & questions**, "
        "**🔬 Comparisons**, **Export** (this trial or bulk), and "
        "**🔗 Share** a deep link.",
    },
    {
        "selector": NAV_SELECTOR,
        "title": "📊 Corpus Analysis · 🗂️ Data",
        "body": "The nav at the very top moves between the three views. "
        "**📊 Corpus Analysis** aggregates across readers, texts and groups "
        "instead of one trial at a time; **🗂️ Data** is where a dataset is set "
        "up and checked.",
    },
    {
        "selector": ".st-key-top_menu",
        "title": "📚 The menu bar",
        "body": "**❓ Help** has the tutorials, the FAQ and the docs. "
        "**💾 Session** keeps your work — a portable JSON of the whole setup + "
        "annotations, plus the on-device cache. Replay this tour from "
        "**🎓 Show tutorial**. 👀",
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


def _highlight_css(selector: str, accent: str) -> str:
    """The pulsing outline drawn around a tour/guide target.

    Factored out of `render_spotlight_tour` (DATA-22 §4) so the setup guide can
    highlight wizard steps with exactly the same treatment the welcome tour uses
    — the guide documented its own gap ("the steps are descriptive, not anchored
    to specific controls") while this machinery sat 800 lines above it.
    """
    if not selector:
        return ""
    return f"""
{selector} {{
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


def _scroll_into_view_script(selector: str) -> str:
    """Centre `selector`'s first *visible* match within its own scroller.

    Every subtlety here was observed live; see the call site in
    `render_spotlight_tour` for the full list. The short version: match the first
    visible element (inactive tab panels hold invisible duplicates), and scroll
    the nearest scrollable ancestor instead of calling `scrollIntoView` (which
    moves the document).

    There is no sidebar branch any more. Targets used to need an
    ``aria-expanded`` gate plus a retrying click on ``stExpandSidebarButton``,
    because a *collapsed* sidebar still reports nonzero layout rects so plain
    visibility couldn't tell whether the panel was really on screen. Every step
    now points at something in the page or on the top menu bar, where
    ``findVisible()`` answers correctly on its own.
    """
    return f"""<script>
                (function () {{
                    const doc = window.parent.document;
                    const win = doc.defaultView;
                    const findVisible = () =>
                        [...doc.querySelectorAll({selector!r})].find((e) => {{
                            const r = e.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) return false;
                            const cs = win.getComputedStyle(e);
                            return cs.visibility !== "hidden" && cs.display !== "none";
                        }});
                    let tries = 0;
                    (function attempt() {{
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

    highlight = _highlight_css(step["selector"], accent)
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
            # - The find+scroll retries until the target is visible, riding
            #   out Streamlit's re-render.
            # - Match the first *visible* element, not the first match:
            #   Streamlit keeps inactive tab panels laid out but
            #   visibility-hidden, so a selector can hit an invisible
            #   duplicate (e.g. the Raw Data panel's inner tab strip) and
            #   scroll the page to nowhere.
            # - No scrollIntoView: smooth gets cancelled by Streamlit's
            #   re-renders, and instant also scrolls the document. Instead,
            #   center the target within its nearest scrollable ancestor only.
            # - Skip targets that are already fully on screen.
            # - The iframe stays INSIDE the fixed-position card: when it sat
            #   at the bottom of the main column, its (re)mount could yank
            #   the main scroller to the page bottom to reveal it.
            # The sidebar branch is gone with the sidebar: every target is now
            # either in the page or on the top menu bar, both of which are
            # always laid out and visible, so there is nothing to expand first
            # and no `in_sidebar` flag to carry.
            embed_html_iframe(
                _scroll_into_view_script(step["selector"]),
                height=0,
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
    ``main()`` — which executes long before the menu button — picks the
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
        # Replay request from the menu button's on_click callback.
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


def render_tour_replay_button(host=None) -> None:
    """Button in the ❓ Help menu popover that replays the tour from step one.

    Deliberately ignores the UX-12 opt-out — "don't show this again" means "stop
    greeting me", not "take the tutorial away". The card's checkbox renders
    pre-ticked on a replay so the choice can be reversed from the same place.
    """
    (host if host is not None else st).button(
        "🎓 Show tutorial",
        key="tour_replay",
        width="stretch",
        help="Replay the quick intro tour.",
        on_click=_arm_tour,
    )


# -----------------------------------------------------------------------------
# Use-case tutorials (UX-40)
# -----------------------------------------------------------------------------


def build_tutorial_context(words, fixations, combos) -> dict[str, object]:
    """Small, serializable availability snapshot for the tutorial chooser."""
    n_trials = len(combos) if combos is not None else 0
    has_words = bool(words is not None and not words.empty)
    has_fixations = bool(fixations is not None and not fixations.empty)
    comparable = False
    corpus_variation = n_trials >= 2
    if combos is not None and not combos.empty:
        source = (
            fixations
            if fixations is not None and not fixations.empty
            else words
            if words is not None and not words.empty
            else combos
        )
        if not {"participant_id", "trial_id"}.issubset(source.columns):
            source = combos
        comparison_columns = [
            column for column in ("text_id", "screen_id") if column in source.columns
        ]
        if "text_id" in comparison_columns:
            readings = source[
                [
                    "participant_id",
                    "trial_id",
                    *comparison_columns,
                ]
            ].drop_duplicates()
            comparable = bool(
                readings.groupby(comparison_columns, dropna=False).size().max() >= 2
            )
        elif "text_id" in combos.columns:
            comparable = bool(combos.groupby("text_id", dropna=False).size().max() >= 2)
        if "text_id" in combos.columns:
            corpus_variation |= combos["text_id"].nunique(dropna=True) >= 2
        if "participant_id" in combos.columns:
            corpus_variation |= combos["participant_id"].nunique(dropna=True) >= 2
    return {
        "n_trials": n_trials,
        "has_words": has_words,
        "has_fixations": has_fixations,
        "has_comparable_readings": comparable,
        "has_corpus_variation": corpus_variation,
    }


def tutorial_availability(
    tutorial: TutorialDefinition, context: dict[str, object]
) -> tuple[bool, str]:
    """Whether a tutorial can start, plus an actionable explanation."""
    rule = tutorial.availability
    if rule == "always":
        return True, ""
    if rule == "has_trials":
        available = int(context.get("n_trials", 0)) >= 1
        return available, "Load at least one trial first."
    if rule == "has_visual_data":
        available = bool(context.get("has_words") or context.get("has_fixations"))
        return available, "Load a words or fixations table first."
    if rule == "has_comparable_readings":
        available = bool(context.get("has_comparable_readings"))
        return available, "Need two readings with the same text id."
    if rule == "has_corpus_variation":
        available = bool(context.get("has_corpus_variation"))
        return available, "Need variation across trials, readers, or texts."
    return False, f"Unknown availability rule: {rule}."


def _tutorial_progress() -> dict[str, int]:
    return st.session_state.setdefault("tutorial_progress", {})


def _tutorial_completed() -> dict[str, bool]:
    return st.session_state.setdefault("tutorial_completed", {})


def _start_use_case(tutorial_id: str, *, restart: bool = False) -> None:
    """Start/resume one tutorial while remembering where Exit should return."""
    if tutorial_id not in _TUTORIAL_BY_ID:
        return
    context = st.session_state.get("_tutorial_context") or {}
    available, _ = tutorial_availability(_TUTORIAL_BY_ID[tutorial_id], context)
    if not available:
        return
    st.session_state["tutorial_return"] = {
        "main_nav": st.session_state.get("main_nav", _VIEW_SCANPATH),
        "single_subtab": st.session_state.get("single_subtab", "📝 Annotations"),
    }
    if restart:
        _tutorial_progress()[tutorial_id] = 0
        _tutorial_completed().pop(tutorial_id, None)
    else:
        _tutorial_progress().setdefault(tutorial_id, 0)
    st.session_state["tutorial_active"] = tutorial_id
    # Never stack this task card over the automatic welcome/setup card.
    st.session_state["tour_mode"] = None


def _move_use_case(tutorial_id: str, delta: int) -> None:
    tutorial = _TUTORIAL_BY_ID[tutorial_id]
    current = int(_tutorial_progress().get(tutorial_id, 0))
    _tutorial_progress()[tutorial_id] = max(
        0, min(len(tutorial.steps) - 1, current + delta)
    )


def _finish_use_case(tutorial_id: str) -> None:
    _tutorial_completed()[tutorial_id] = True
    _tutorial_progress()[tutorial_id] = len(_TUTORIAL_BY_ID[tutorial_id].steps) - 1
    st.session_state["tutorial_active"] = None


def _restore_tutorial_return() -> None:
    location = st.session_state.get("tutorial_return") or {}
    if location.get("main_nav") is not None:
        st.session_state["main_nav"] = location["main_nav"]
    if location.get("single_subtab") is not None:
        st.session_state["single_subtab"] = location["single_subtab"]
    st.session_state["tutorial_active"] = None


def _open_tutorial_surface(step: TutorialStep) -> None:
    st.session_state["main_nav"] = step.view
    if step.subtab is not None:
        st.session_state["single_subtab"] = step.subtab


_KNOWN_VIEWS = (_VIEW_SCANPATH, _VIEW_CORPUS, _VIEW_DATA)


def _tutorial_surface_is_open(step: TutorialStep) -> bool:
    """Is the view (and subtab) this step points at the one on screen?

    UX-40: this used to fold everything that was not Corpus Analysis into
    Scanpath, which predates DATA-26's third view — so a step with
    ``view=_VIEW_DATA`` reported "not open" *while the user was standing on the
    Data page*, and the card offered to open the panel they were already
    looking at (and withheld the spotlight that should have been on it).
    """
    current_view = st.session_state.get("main_nav", _VIEW_SCANPATH)
    if current_view not in _KNOWN_VIEWS:
        current_view = _VIEW_SCANPATH
    if current_view != step.view:
        return False
    return (
        step.subtab is None
        or st.session_state.get("single_subtab", "📝 Annotations") == step.subtab
    )


def _arm_tutorial_library() -> None:
    """``on_click`` callback for the Tutorials button: request the dialog."""
    st.session_state["_tutorial_library_requested"] = True


def maybe_show_tutorial_library() -> None:
    """Open the tutorial chooser if the ❓ Help menu button armed it.

    Served early in ``main()`` beside :func:`maybe_show_faq`, for the same
    reason: the button renders at the bottom of the run.
    """
    if st.session_state.pop("_tutorial_library_requested", False):
        _tutorial_library_dialog()


def render_tutorial_library(context: dict[str, object], *, host=None) -> None:
    """Button in the ❓ Help menu popover that opens the tutorial chooser.

    A dialog rather than the nested ``🧭 Tutorials`` popover it used to be: the
    Help group is itself a popover now, and Streamlit nests no popover in a
    popover. The chooser is a modal-shaped thing anyway — pick an outcome, start,
    and the tutorial takes over the page.
    """
    st.session_state["_tutorial_context"] = dict(context)
    (host if host is not None else st).button(
        "🧭 Tutorials",
        key="tutorial_library_open",
        width="stretch",
        help="Task-oriented walkthroughs, independent of the welcome tour.",
        on_click=_arm_tutorial_library,
    )


@st.dialog("🧭 Tutorials", width="large")
def _tutorial_library_dialog() -> None:
    """The chooser: outcome, prerequisites, time, and progress per tutorial."""
    from scanpath_studio.menu import close_open_popovers

    # Opened from a button inside the ❓ Help popover, whose open state is
    # client-side — without this it floats on top of the modal.
    close_open_popovers()
    context = st.session_state.get("_tutorial_context") or {}
    st.markdown("**Choose the outcome you want to reach.**")
    st.caption(
        "Each one points at the real controls and changes nothing — your data, "
        "filters and settings are exactly where you left them. Independent of "
        "the automatic welcome tour."
    )
    # UX-40: one bordered card per tutorial instead of five identical
    # caption/caption/caption/two-buttons stacks separated by dividers — at that
    # density the eye had nothing to land on, and "Start over" sat there at full
    # weight even for a tutorial nobody had started yet.
    for tutorial in TUTORIALS:
        available, reason = tutorial_availability(tutorial, context)
        completed = bool(_tutorial_completed().get(tutorial.id))
        progress = int(_tutorial_progress().get(tutorial.id, 0))
        started = progress > 0 and not completed
        card = st.container(border=True)
        head, action = card.columns([3, 1], vertical_alignment="center")
        badge = " ✓" if completed else ""
        head.markdown(f"**{tutorial.title}**{badge}")
        head.caption(tutorial.outcome)
        if started:
            state = f"Paused at step {progress + 1} of {len(tutorial.steps)}"
        elif completed:
            state = "Completed — replay any time"
        else:
            state = f"{len(tutorial.steps)} steps · {tutorial.estimated_time}"
        head.caption(f"{state} · needs {tutorial.prerequisite.lower()}")
        # Handled by return value, not `on_click`, because **an `st.dialog` body
        # is a fragment**: a callback here reruns only the dialog, so the state
        # `_start_use_case` writes never reached `main()` — the chooser sat
        # there unchanged and the task card it was supposed to hand over to was
        # never drawn. `st.rerun(scope="app")` both closes the modal (the
        # `_tutorial_library_requested` flag was already popped, so the next run
        # does not re-open it) and renders the card underneath.
        if action.button(
            "Resume" if started else "Start",
            key=f"tutorial_start_{tutorial.id}",
            disabled=not available,
            type="primary" if started else "secondary",
            width="stretch",
        ):
            _start_use_case(tutorial.id)
            st.rerun(scope="app")
        # Only offered once there is progress to discard.
        if (started or completed) and action.button(
            "Start over",
            key=f"tutorial_restart_{tutorial.id}",
            disabled=not available,
            width="stretch",
        ):
            _start_use_case(tutorial.id, restart=True)
            st.rerun(scope="app")
        if not available:
            card.caption(f"⚠️ Unavailable — {reason.lower()}")


@st.fragment
def render_use_case_tutorial() -> None:
    """Render the active named tutorial with safe, explicit navigation."""
    tutorial_id = st.session_state.get("tutorial_active")
    tutorial = _TUTORIAL_BY_ID.get(tutorial_id)
    if tutorial is None:
        return
    context = st.session_state.get("_tutorial_context") or {}
    available, reason = tutorial_availability(tutorial, context)
    if not available:
        st.warning(f"Tutorial paused: {reason}")
        return
    step_index = min(
        int(_tutorial_progress().get(tutorial.id, 0)), len(tutorial.steps) - 1
    )
    step = tutorial.steps[step_index]
    surface_open = _tutorial_surface_is_open(step)
    selector = step.selector if surface_open else None
    accent = st.get_option("theme.primaryColor") or "#1f77b4"
    theme = getattr(getattr(st, "context", None), "theme", None)
    is_dark = getattr(theme, "type", "light") == "dark"
    bg, border = ("#262730", "#41434e") if is_dark else ("#ffffff", "#d5d6d9")
    highlight = (
        f"{selector} {{ outline: 3px solid {accent}; outline-offset: 3px; "
        "border-radius: .5rem; animation: tour-pulse 1.6s ease-in-out infinite; }}"
        if selector
        else ""
    )
    st.markdown(
        "<style>"
        + _CARD_CSS
        + f".st-key-tour_card {{ background: {bg}; border: 1px solid {border}; }}"
        + highlight
        + "</style>",
        unsafe_allow_html=True,
    )
    with st.container(key="tour_card"):
        st.markdown(f"## {tutorial.title}")
        st.markdown(f"**{step.title}**")
        st.markdown(step.body)
        if not surface_open and st.button(
            "Show me / Open this panel",
            key="tutorial_open_surface",
            type="primary",
            width="stretch",
        ):
            _open_tutorial_surface(step)
            st.rerun()
        st.progress(
            (step_index + 1) / len(tutorial.steps),
            text=f"Step {step_index + 1} of {len(tutorial.steps)}",
        )
        st.link_button(
            "Matching written tutorial ↗",
            tutorial.docs_url,
            width="stretch",
        )
        back_col, exit_col, next_col = st.columns(3)
        back_col.button(
            "← Back",
            key="tutorial_back",
            disabled=step_index == 0,
            on_click=_move_use_case,
            args=(tutorial.id, -1),
            width="stretch",
        )
        if exit_col.button("Exit", key="tutorial_exit", width="stretch"):
            _restore_tutorial_return()
            st.rerun()
        if step_index < len(tutorial.steps) - 1:
            next_col.button(
                "Next →",
                key="tutorial_next",
                type="primary",
                on_click=_move_use_case,
                args=(tutorial.id, 1),
                width="stretch",
            )
        else:
            if next_col.button(
                "✓ Done",
                key="tutorial_done",
                type="primary",
                width="stretch",
            ):
                # Completion leaves the app at the promised outcome even when
                # the user did not press the last step's optional Open button.
                _open_tutorial_surface(step)
                _finish_use_case(tutorial.id)
                st.rerun()

        # A Streamlit popover is client-side state, so its server callback can
        # start a tutorial but cannot close the chooser that contained the
        # Start button. Close only the expanded Tutorials trigger once it
        # appears later in this rerun; otherwise the chooser sits over the
        # menu while the task card is already active.
        embed_html_iframe(
            """<script>
            (function () {
                const doc = window.parent.document;
                let tries = 0;
                (function closeTutorialChooser() {
                    const trigger = [...doc.querySelectorAll(
                        'button[aria-expanded="true"]'
                    )].find((button) =>
                        (button.textContent || '').includes('Tutorials')
                    );
                    if (trigger) {
                        trigger.click();
                        return;
                    }
                    if (++tries < 200) setTimeout(closeTutorialChooser, 150);
                })();
            })();
            </script>""",
            height=0,
        )

        if selector:
            embed_html_iframe(
                f"""<script>
                (function () {{
                    const doc = window.parent.document;
                    let tries = 0;
                    (function findAndScroll() {{
                        const el = [...doc.querySelectorAll({selector!r})].find((e) => {{
                            const r = e.getBoundingClientRect();
                            const s = window.getComputedStyle(e);
                            return r.width && r.height && s.display !== "none"
                                && s.visibility !== "hidden";
                        }});
                        if (!el) {{
                            if (++tries < 200) setTimeout(findAndScroll, 150);
                            return;
                        }}
                        el.scrollIntoView({{behavior: "smooth", block: "center"}});
                    }})();
                }})();
                </script>""",
                height=0,
            )


# -----------------------------------------------------------------------------
# FAQ (UX-15) — the handful of questions that come up over and over, answered
# in-app so nobody has to leave to find out that (say) their measures are their
# eye-tracker's, not ours. Deliberately SHORT: the canonical, complete version
# is docs/faq.md on the docs site, linked from the bottom of the dialog. Keep
# these answers in sync with that page when either changes.
# -----------------------------------------------------------------------------

DOCS_FAQ_URL = f"{CITATION['docs_url']}faq/"
# VAL-5's generated register page — the app's one link into the methodology.
DOCS_COMPUTATIONS_URL = f"{CITATION['docs_url']}computations/"

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
        "🗂️ **Data → Column mapping** — an editable form that "
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
        "state, which dies with the session. Use **💾 Session → Save & restore** for the "
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
        "I edited the code (or a setting looks stale) and nothing changed.",
        "Streamlit doesn't reload already-imported modules on a rerun, and "
        "`st.cache_data` doesn't hash the helpers a cached loader calls — a "
        "rerun or **Clear cache** isn't enough after editing code. Restart the "
        "server process. This is a different cache from the menu bar's "
        "**💾 Session → 🗄️ Recovery cache** panel, which stores your data and settings, "
        "not code.",
    ),
    (
        "How do I cite Scanpath Studio?",
        "See **ℹ️ About** under ❓ Help (and `CITATION.cff` in the "
        "repository). Cite the bundled demo data as OneStop Eye Movements too.",
    ),
]

# PRE-21: FAQ entries that only make sense while a gated feature is exposed.
# Appended by `faq_items()` rather than living in `_FAQ_ITEMS`, so the default
# build never offers an answer about a control it doesn't have.
_DRIFT_FAQ_ITEMS = [
    (
        "What does drift correction do?",
        "It reassigns each fixation to the text **line** it most likely belongs "
        "to and snaps it there — the ten algorithms from Carr et al. (2021). It "
        "changes the figure, not your data. Apply one via **Fixations ⚙️ → Drift "
        "correction**, or compare all ten in the **📐 Line assignment** subtab.",
    ),
]


def faq_items() -> list:
    """The FAQ entries this build can honestly answer (PRE-21)."""
    items = list(_FAQ_ITEMS)
    if drift_correction_enabled():
        items.extend(_DRIFT_FAQ_ITEMS)
    return items


@st.dialog("❓ Frequently asked questions", width="large")
def _faq_dialog() -> None:
    """The in-app FAQ: short answers in expanders + links to the full docs.

    Kept short on purpose — this is the "before you file an issue" list, not a
    manual. The docs site carries the complete version (``docs/faq.md``), and
    the link buttons at the bottom are also the app's route into the docs from
    a help context.
    """
    from scanpath_studio.menu import close_open_popovers

    # Opened from a button inside the ❓ Help popover, whose open state is
    # client-side — without this it floats on top of the modal.
    close_open_popovers()
    st.caption(
        "Short answers to the questions that come up most. The full version — "
        "with the long explanations — lives on the documentation site."
    )
    for question, answer in faq_items():
        with st.expander(question):
            st.markdown(answer)

    st.divider()
    docs_col, tutorials_col, methods_col, close_col = st.columns(4)
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
    # VAL-5 — one link to the whole computation register, rather than a help
    # anchor per measure picker (the user's call: that end is a much bigger job
    # for a research tool, and this is where someone goes looking anyway).
    methods_col.link_button(
        "🔬 Methodology ↗",
        DOCS_COMPUTATIONS_URL,
        width="stretch",
        help="Every computation the app performs: the exact formula, its units, "
        "its missing-data behaviour, and how far it has been verified. Opens in "
        "a new tab.",
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
    """Open the FAQ dialog if the ❓ Help menu button armed it.

    Call from ``main()`` next to :func:`maybe_show_welcome_tour`, BEFORE the
    heavy data / plot work. The button sits at the *bottom* of ``main()``, so
    opening the dialog from its return value meant the modal only streamed to
    the browser after the whole rerun — including the ~10 s plot embeds — had
    finished. Served here it appears immediately and overlays whatever renders
    after it.
    """
    if st.session_state.pop("_faq_dialog_requested", False):
        _faq_dialog()


def render_faq_button(host=None) -> None:
    """Button in the ❓ Help menu popover that opens the in-app FAQ dialog.

    Sits next to :func:`render_tour_replay_button` and is armed the same way: an
    ``on_click`` callback sets a request flag that the early
    :func:`maybe_show_faq` call serves, so the modal doesn't wait on the heavy
    data / plot work this button renders after.
    """
    (host if host is not None else st).button(
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
# DATA-22 §4: the guide is now *anchored*. Each step names the wizard step it
# talks about (so Next drives the accordion instead of narrating beside it) and a
# CSS selector to highlight + scroll to. Keyed expanders give every step a
# `.st-key-wiz_open_<id>` selector for free, so no new wrapper containers were
# needed; finer targets reuse existing widget keys.
_WIZARD_GUIDE_STEPS = [
    {
        "title": "📂 Set up your dataset",
        "body": (
            "Turn your eye-tracking tables into an interactive dataset in two "
            "parts: upload them, then say which columns mean what and add it. "
            "Follow along with **Next** — the wizard opens each part as you go — "
            "or **Skip** to dive in."
        ),
        "selector": "",
        "step_id": None,
    },
    {
        "title": "1 · Your data",
        "body": (
            "Add your **Fixations** and/or **Words / IA** tables — CSV / TSV / "
            "Parquet, several files or either alone. Optionally attach a "
            "one-row-per-reader table at the foot.\n\n"
            "> 💡 Large dataset? Run locally: `pip install scanpath-studio`."
        ),
        "selector": ".st-key-wiz_open_data",
        "step_id": "data",
    },
    {
        "title": "2 · Map it & add it",
        "body": (
            "Name it, then work down one screen: **Trials & readers**, "
            "**Fixations & text**, **Recording setup**, **Extra fields**. "
            "Anything still missing is listed right above **✅ Add dataset**. 👀"
        ),
        "selector": ".st-key-wiz_open_mapping",
        "step_id": "mapping",
    },
]


def _wizard_guide_go(step_idx: int) -> None:
    """Move the guide to ``step_idx`` and open the wizard step it describes.

    This is what makes the card *drive* the wizard rather than narrate beside it.
    ``go_to_step`` is safe here because a guide button is an ``on_click``
    callback: it runs before the script re-executes, so the ``wiz_open_*`` writes
    land before the expanders instantiate.
    """
    from . import wizard_shell

    step_idx = max(0, min(step_idx, len(_WIZARD_GUIDE_STEPS) - 1))
    st.session_state["wizard_guide_step"] = step_idx
    target = _WIZARD_GUIDE_STEPS[step_idx].get("step_id")
    if target:
        wizard_shell.go_to_step(target)


def _wizard_guide_back() -> None:
    _wizard_guide_go(st.session_state.get("wizard_guide_step", 0) - 1)


def _wizard_guide_next() -> None:
    _wizard_guide_go(st.session_state.get("wizard_guide_step", 0) + 1)


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
    step = _WIZARD_GUIDE_STEPS[step_idx]
    title, body, selector = step["title"], step["body"], step["selector"]

    accent = st.get_option("theme.primaryColor") or "#1f77b4"
    theme = getattr(getattr(st, "context", None), "theme", None)
    is_dark = getattr(theme, "type", "light") == "dark"
    bg, border = ("#262730", "#41434e") if is_dark else ("#ffffff", "#d5d6d9")
    st.markdown(
        "<style>"
        + _CARD_CSS
        + f".st-key-tour_card {{ background: {bg}; border: 1px solid {border}; }}"
        + _highlight_css(selector, accent)
        + "</style>",
        unsafe_allow_html=True,
    )
    if selector:
        embed_html_iframe(_scroll_into_view_script(selector), height=0)

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
