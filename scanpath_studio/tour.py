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
  ``st.dialog`` of recurring questions (``_faq_dialog``), deliberately kept to a
  handful of answers with the complete version on the docs site
  (``docs/faq.md``). It is armed exactly like the tour — the ❓ Help nav entry
  (``menu._arm_help_action``) calls ``_arm_faq``, which sets a request flag that
  ``maybe_show_faq`` serves early in ``main()``, so the modal never waits out the
  rest of the rerun (~10 s of plot embeds) before appearing.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from scanpath_studio.crash_report import guarded
from scanpath_studio.html_embed import embed_html_iframe
from scanpath_studio.menu import NAV_SELECTOR

from .constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    CITATION,
    ICONS,
    SUBTAB_ANNOTATIONS,
    SUBTAB_COMPARISONS,
    SUBTAB_EXPORT,
    SUBTAB_SHARE,
    drift_correction_enabled,
    preprocessing_enabled,
    similarity_enabled,
    spoken,
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

# UX-101: the trial filters live behind one funnel since UX-64, and a *closed*
# Streamlit popover renders no body — so `tour_grp_narrow_by` is absent from the
# page until the funnel is clicked, and a step aimed at it silently spotlighted
# nothing. A step that points inside a popover names the trigger that opens it
# here, and the spotlight opens it (see `_popover_script`).
#
# Two selectors because the picker row has two layouts: `select_trial` drops the
# slider for a pool of one and gives the funnel its own trailing column
# (`railbtn_single_filter_solo`) — exactly the case a filter *causes*, so the
# tour must reach it there too.
FUNNEL_TRIGGER = (
    ".st-key-railbtn_single_filter button, .st-key-railbtn_single_filter_solo button"
)


@dataclass(frozen=True)
class TutorialStep:
    """One reusable spotlight step in a task-oriented tutorial."""

    title: str
    body: str
    selector: str
    view: str = _VIEW_SCANPATH
    subtab: str | None = None
    #: PERF-9 made the Corpus Analysis subtabs lazy (only the open one renders),
    #: so a step aimed at a control inside one has to open it, as ``subtab``
    #: does for the Scanpath view. A label from ``tabs.CORPUS_SUBTABS``.
    corpus_subtab: str | None = None
    #: DATA-35 — the step's target lives on the 🗂️ Data page's **✏️ Edit dataset**
    #: screen rather than its overview, so opening the view is not enough: the
    #: editor has to be raised too, or the spotlight aims at a hidden container.
    dataset_editor: bool = False
    #: UX-101 — the step's target is built inside a popover, so it is not in the
    #: page until that popover's trigger is clicked. The selector of the trigger;
    #: the spotlight opens it before it looks for the target (`_popover_script`).
    popover: str = ""
    optional: bool = False
    #: PRE-22 — a step about a feature this build may not show. ``"preprocessing"``
    #: is the only value so far; a step whose gate is closed is dropped from the
    #: tutorial entirely (`steps_of`), so it never spotlights a surface that is
    #: not there or counts toward "step 3 of 7".
    gate: str | None = None


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


# Each tutorial's "Matching written tutorial" button opens the docs page that
# covers the same task (ENG-88), not a copy of these steps.
DOCS_URL = CITATION["docs_url"]
DOCS_TUTORIALS_URL = f"{DOCS_URL}tutorials/"

# PRE-21 hides NLD similarity scoring unless SCANPATH_EXPERIMENTAL=1, so the
# comparison tutorial must not promise a ranking this build does not show —
# the same honesty rule `faq_items()` applies to the drift-correction answers.
# The flag is an environment variable, fixed for the life of the process, so
# resolving it once at import is equivalent to checking it per render.
_SIMILARITY_SENTENCE = (
    " Similarity scores (NLD) rank the closest trials for you."
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
        docs_url=f"{DOCS_URL}guides/loading-data/",
        steps=(
            TutorialStep(
                "Choose the dataset",
                f"Everything about the dataset lives on the {ICONS['view_data']} **Data Management** page, in the "
                "order the pipeline uses it. Start at the list of datasets — "
                "click a row to open it, or **+ Add dataset** for your own tables.",
                ".st-key-tutorial_available_datasets",
                view=_VIEW_DATA,
            ),
            TutorialStep(
                "Check the column mapping",
                f"The {ICONS['edit']} on a dataset's row opens its setup screen — "
                "the add screen's parts, for a dataset that exists. Part **2 · "
                "Data tables & column mapping** decides which columns everything "
                "reads. Rows marked ✨ were auto-detected; override any that "
                "guessed wrong.",
                ".st-key-tutorial_column_mapping",
                view=_VIEW_DATA,
                dataset_editor=True,
            ),
            TutorialStep(
                "Verify what was parsed",
                f"**{ICONS['search']} What's in the … dataset** opens on {ICONS['stats']} Stats — the "
                "counts and their spread, the quickest check that the mapping "
                "worked. The six raw tables and its annotations are the tabs "
                "beside it.",
                ".st-key-tutorial_data_inspection",
                view=_VIEW_DATA,
            ),
            TutorialStep(
                "Check one trial id is one reading",
                "The **Trial identity** part checks the whole dataset, before any "
                "filtering, and says so either way. A warning here means the "
                "Trial ID above is missing a column — several readings are being "
                "drawn as one scanpath, which renders happily as a reading with a "
                "lot of regressions.",
                ".st-key-tutorial_trial_identity",
                view=_VIEW_DATA,
                dataset_editor=True,
            ),
            TutorialStep(
                "Decide on preprocessing",
                f"**Preprocessing**, the last part of the {ICONS['edit']} Edit screen, can "
                "soft-exclude or merge short fixations before anything is "
                "measured. It is off by default, applies to every view, and "
                "never discards your original rows.",
                ".st-key-tutorial_preprocessing",
                view=_VIEW_DATA,
                dataset_editor=True,
                optional=True,
                gate="preprocessing",
            ),
        ),
    ),
    TutorialDefinition(
        id="filter_annotate",
        title="Filter and mark trials",
        outcome="Finish with reviewed trials starred or tagged, and exported.",
        estimated_time="4 min",
        prerequisite="At least one trial",
        availability="has_trials",
        completion_test="Export panel reached after annotation review",
        docs_url=f"{DOCS_TUTORIALS_URL}data-filtering/",
        steps=(
            TutorialStep(
                "Narrow the review pool",
                "The funnel beside the trial picker — opened for you here — "
                "holds the text and participant pickers at the top (*All texts* "
                "/ *All participants* until you narrow), then condition and "
                "annotation filters (favorites, tags). This tutorial only "
                "points; it never changes a filter.",
                ".st-key-tour_grp_narrow_by",
                popover=FUNNEL_TRIGGER,
            ),
            TutorialStep(
                "Review one trial at a time",
                "One picker for every dataset: the **Select trial** dropdown, a scrubbing "
                "slider showing *index / total*, and ◀ ▶ to step through the pool "
                "you just narrowed.",
                ".st-key-tour_grp_trial_picker",
            ),
            TutorialStep(
                "Move between screens",
                "A multipart trial (one reading spread over several screens) adds a "
                "screen picker at the right end of the trial row. Each screen is its own "
                "coordinate space, so nothing is ever drawn across two of them.",
                ".st-key-tour_grp_screen_picker",
                optional=True,
            ),
            TutorialStep(
                "Annotate at the right scope",
                "Star, tag, or note the parent trial. Multipart data can instead attach "
                "a separate annotation to the active screen.",
                ".st-key-tutorial_annotations",
                subtab=SUBTAB_ANNOTATIONS,
            ),
            TutorialStep(
                "Export the marked result",
                "Open **Export** and choose the filtered scope and tabular files. "
                "Screen identity is retained in multipart exports.",
                ".st-key-tutorial_export",
                subtab=SUBTAB_EXPORT,
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
        docs_url=f"{DOCS_TUTORIALS_URL}exporting-figures/",
        steps=(
            TutorialStep(
                "Choose the visual language",
                "Use design presets, palette, and the layer controls. Heatmap and scanpath "
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
                "Open **Export** for this figure (PNG, SVG, PDF, HTML) or a bundle "
                "of many. Keep the settings file in a bundle so it can be redrawn.",
                ".st-key-tutorial_export",
                subtab=SUBTAB_EXPORT,
            ),
            TutorialStep(
                "Keep the figure reproducible",
                f"**{ICONS['share']} Share** turns the exact configuration into a **Link**, the "
                "**Code** that redraws it, or a settings **File**. Any of them "
                "reproduces this figure later — the PNG on its own does not.",
                ".st-key-tutorial_share",
                subtab=SUBTAB_SHARE,
                optional=True,
            ),
        ),
    ),
    TutorialDefinition(
        id="compare_readings",
        title="Compare trials of one text",
        outcome=(
            "Finish with the other trials of one text side by side, at one scale."
        ),
        estimated_time="3 min",
        prerequisite="Two trials sharing a text (and screen for multipart data)",
        availability="has_comparable_readings",
        completion_test="Comparisons panel reached",
        docs_url=f"{DOCS_URL}guides/scanpath-visualization/#replay-and-compare",
        steps=(
            TutorialStep(
                "Choose the reference trial",
                "Pick the trial that should anchor the comparison. The comparison "
                "panel reuses this exact parent trial and active screen.",
                ".st-key-tour_grp_trial_picker",
            ),
            TutorialStep(
                "Compare like with like",
                f"Open **{ICONS['comparisons']} Comparisons** and set **Match field** to the text id: "
                "the grid shows the other trials that share this trial's value in "
                "that field — here, the other trials of *this* text — at one "
                "scale." + _SIMILARITY_SENTENCE,
                ".st-key-tutorial_comparisons",
                subtab=SUBTAB_COMPARISONS,
            ),
        ),
    ),
    TutorialDefinition(
        id="explore_corpus",
        title="Explore a corpus question",
        outcome=(
            "Finish having answered one worked question — how a participant's average "
            "fixation duration moved across the experiment."
        ),
        estimated_time="4 min",
        prerequisite="Variation across trials, participants, or texts",
        availability="has_corpus_variation",
        completion_test="Corpus Analysis opened",
        docs_url=f"{DOCS_TUTORIALS_URL}corpus-analysis/",
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
                "Each subtab answers one shape of question: **Per text** (one text, "
                "many participants), **Per participant** (one participant, all their "
                "trials) and **Groups** (a cohort, or two compared). Our question — "
                "*did this participant speed up over the experiment?* — is "
                "**Per participant**.",
                ".st-key-tutorial_corpus_subtabs",
                view=_VIEW_CORPUS,
            ),
            TutorialStep(
                "Choose the participant and the view",
                "Pick the participant on the left, then set **View** to **Per-trial trend**. "
                "That plots one point per trial in presentation order — the whole "
                "experiment on one axis, rather than a single trial's dynamics.",
                ".st-key-tutorial_per_reader_view",
                view=_VIEW_CORPUS,
                corpus_subtab="Per participant",
            ),
            TutorialStep(
                "Read average fixation duration across the experiment",
                "Set the measure to **fixation duration**; each point is that trial's "
                "mean. A downward slope is the participant settling in — but check the "
                "spread and the trial count before believing it, because one short "
                "trial moves a mean a long way.",
                ".st-key-tutorial_corpus_analysis",
                view=_VIEW_CORPUS,
            ),
            TutorialStep(
                "Put it against the cohort",
                "**Distribution vs cohort** answers the companion question — is this "
                "participant unusual, or is the whole cohort like this? Read the sample size "
                "with the effect, never the plotted mean on its own.",
                ".st-key-tutorial_per_reader_view",
                corpus_subtab="Per participant",
                view=_VIEW_CORPUS,
                optional=True,
            ),
        ),
    ),
)

_TUTORIAL_BY_ID = {tutorial.id: tutorial for tutorial in TUTORIALS}

#: PRE-22 — which builds show a gated step. Read at *call* time, not at import,
#: so a test (or a session started with the env var) sees the current answer.
_STEP_GATES = {"preprocessing": preprocessing_enabled}


def steps_of(tutorial: TutorialDefinition) -> tuple[TutorialStep, ...]:
    """The tutorial's steps this build can honestly walk (PRE-22).

    A step about a feature held back from the release is dropped rather than
    shown-and-skipped: it would otherwise spotlight a surface that does not
    exist, and count toward "step 3 of 7" for something the reader cannot do.
    """
    return tuple(
        step
        for step in tutorial.steps
        if step.gate is None or _STEP_GATES.get(step.gate, lambda: True)()
    )


# (title, markdown body) per step — keep bodies to a few lines each; the tour
# should take well under a minute.
_STEPS = [
    (
        f"{ICONS['app']} Welcome to Scanpath Studio",
        "Visualize **eye movements in reading** — scanpaths drawn true-to-scale "
        "over the text. This tour takes under a minute.",
    ),
    (
        f"{ICONS['datasets']} Data Management",
        "Use the demo, or **upload your own** fixations / word tables "
        "(CSV / TSV / Parquet). Columns auto-detect — remap any field in the wizard.",
    ),
    (
        f"{ICONS['trial_filter']} Filter trials",
        "Narrow trials by participant or condition. Each tab has its own trial picker.",
    ),
    (
        f"{ICONS['plot_controls']} Plot controls",
        "Toggle and style every layer — fixations, saccades, heatmap, word boxes, "
        f"text. The monitor is set in {ICONS['view_data']} **Edit dataset → Recording "
        "setup**, so it stays true-to-scale.",
    ),
    (
        f"{ICONS['views']} Three views",
        "**Scanpath** (tick *Animate* to replay) · **Corpus Analysis** · "
        "**Data Management** (set up and inspect the dataset). Bulk export is the "
        "**Export** subtab in Scanpath.",
    ),
    (
        f"{ICONS['annotations']} Annotate & save",
        f"Star, tag, and note trials, then filter to them. **{ICONS['view_data']} Data Management → "
        "Annotations** exports them as JSON. Replay this via "
        "**Tutorials → Welcome tour**. 👀",
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

    Reads the ``sps_tour_optout`` cookie (UX-12). Within a session
    ``_tour_dismissed`` — a plain data flag, not any checkbox's own widget
    key (UX-110) — wins, so ticking either the tour's own checkbox or the 🧭
    Tutorials picker's copy of it takes effect immediately rather than
    waiting for the browser to hand the cookie back on the next load. The
    legacy ``tour_dont_show`` key (the tour's own checkbox, or a value parked
    there directly before either checkbox has rendered) is still honoured as
    a fallback, so setting it directly — as tests, and any future caller that
    predates UX-110, do — keeps working. Defensive about ``st.context``
    because bare-mode / AppTest runs have no request behind them.
    """
    if "_tour_dismissed" in st.session_state:
        return bool(st.session_state["_tour_dismissed"])
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


def _render_tour_optout(host=st, *, key_suffix: str = "") -> None:
    """The "Don't show this again" checkbox + the cookie write that backs it.

    Two call sites (UX-110): the welcome tour's own first/last step
    (``host=st``, ``key_suffix=""`` — the original ``tour_dont_show`` key,
    unchanged, so existing links/tests keep working) and the 🧭 Tutorials
    picker's Welcome tour card (``host=<that card's container>``,
    ``key_suffix="_picker"``). Both can be on screen in the same run — the
    picker can be reopened while the tour it started is still settling onto
    screen — so they need distinct widget keys, synced as a pair: seeded from
    :func:`tour_opted_out` only when nothing has touched *this* particular
    checkbox since it last agreed with that shared truth (``_synced_key``),
    not via ``value=``, which Streamlit only consults before a widget's key
    first exists.

    Whichever is ticked writes ``_tour_dismissed`` — a plain data flag,
    deliberately never a widget's own key — rather than the other checkbox's
    ``tour_dont_show``/``tour_dont_show_picker`` key directly: Streamlit
    refuses `st.session_state[key] = ...` for any key whose widget has
    already been instantiated *anywhere* in the current run, and both
    checkboxes CAN render in the same run (see above), so writing into the
    other one's own key would raise the moment that happens. `tour_opted_out`
    reads `_tour_dismissed` first, which is what makes either checkbox's
    click visible to the auto-open gate and to the other checkbox.
    """
    key = f"tour_dont_show{key_suffix}"
    synced_key = f"_{key}_synced"
    shared_truth = tour_opted_out()
    if key not in st.session_state or (
        st.session_state.get(synced_key) == st.session_state[key]
        and st.session_state[key] != shared_truth
    ):
        st.session_state[key] = shared_truth
    opted_out = host.checkbox(
        "Don't show this again",
        key=key,
        help="Skip the tour on future visits. **Tutorials → Welcome tour** under "
        f"{ICONS['help']} Help always brings it back.",
    )
    st.session_state[synced_key] = opted_out
    st.session_state["_tour_dismissed"] = opted_out
    embed_html_iframe(_tour_optout_script(opted_out), height=0)


def _step_back() -> None:
    st.session_state["tour_step"] = max(0, st.session_state.get("tour_step", 0) - 1)


def _step_next() -> None:
    st.session_state["tour_step"] = st.session_state.get("tour_step", 0) + 1


@st.dialog("Quick tour", width="large")
@guarded()
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
        "title": f"{ICONS['app']} Welcome to Scanpath Studio",
        # #374 F32: the dataset sentence is `_welcome_body`'s, from the one
        # actually open — "A demo dataset is loaded" greeted users' own data.
        "body": "Visualize **eye movements in reading** — scanpaths drawn "
        "true-to-scale over the text. **Next** for a quick tour, or **Skip "
        "tour** to start exploring.",
    },
    {
        "selector": ".st-key-tour_grp_plot",
        "title": f"{ICONS['view_scanpath']} The scanpath",
        "body": "This is the main plot. Each circle is a **fixation**, sized by "
        "duration on one scale shared by every figure (the key in the corner "
        "gives sizes in ms); the lines are **saccades** between them.",
    },
    {
        "selector": ".st-key-tour_grp_data_source",
        "title": f"{ICONS['datasets']} Your datasets",
        "body": "The **dataset** you're viewing is picked at the top left; "
        f"{ICONS['view_data']} **Data Management** lists them all — click a row "
        "there to open one, **+ Add dataset** for your own.",
    },
    # Picking comes before narrowing: the picker is the control a new reader
    # reaches for first, and narrowing only means something once they have seen
    # the pool it narrows. (UX-34 walked them the other way round, top-to-bottom
    # by screen position; the workflow order reads better in the tour.) Each step
    # targets its own container — they used to share one wrapper, so both lit up
    # the whole block.
    {
        "selector": ".st-key-tour_grp_trial_picker",
        "title": f"{ICONS['pick_trial']} Pick a trial",
        "body": "Step through trials with the selector and ◀ ▶, or scrub the "
        "slider — it shows the trial's position and id.",
    },
    {
        "selector": ".st-key-tour_grp_narrow_by",
        "popover": FUNNEL_TRIGGER,
        "title": f"{ICONS['trial_filter']} Narrow the pool",
        # The icon, not the word: the trigger beside the picker is Streamlit's
        # Material funnel (`tabs._FILTER_ICON`), and "the funnel" sent readers
        # hunting for an emoji the app never draws.
        "body": f"{ICONS['trial_filter']} beside the trial picker — opened for you "
        "here — holds every way to narrow the pool: the text and participant "
        "pickers first (*All texts* / *All participants*), then condition and "
        "annotation filters (favorites, tags).",
    },
    {
        "selector": ".st-key-tour_grp_chips",
        "title": f"{ICONS['chips']} Trial at a glance",
        "body": "These chips show the trial's **identity, conditions, and summary "
        "stats**. Choose which fields appear — and drag to reorder — with "
        f"**{ICONS['edit']}** at the end of the trial row, which also hides them.",
    },
    {
        "selector": ".st-key-tour_grp_view_modes",
        "title": f"{ICONS['animate']} Animate & compare",
        "body": "**Animate** replays the trial fixation by fixation, and "
        "**Compare** adds a second scanpath, overlaid or side by side — from this dataset or, "
        "via **Dataset B**, from another one. The ▾ beside each toggle "
        "opens its settings.",
    },
    {
        "selector": ".st-key-tour_grp_viz_controls",
        "title": f"{ICONS['plot_controls']} Plot controls",
        "body": "Toggle and style every layer — fixations, saccades, stimulus, word "
        "boxes, heatmap, raw gaze. **Design presets** jump between Scanpath, "
        "Heatmap, Illustration and Custom; "
        f"**{ICONS['designs']} My designs** keeps yours under a name.",
    },
    {
        "selector": ".st-key-tour_grp_subtabs",
        "title": f"{ICONS['panels']} Per-trial panels",
        "body": f"Below the plot: **{ICONS['annotations']} Annotations**, **{ICONS['stimulus']} Stimulus & context**, "
        f"**{ICONS['comparisons']} Comparisons**, **{ICONS['export']} Export**, and "
        f"**{ICONS['share']} Share** (link, code or settings file).",
    },
    {
        # UX-100 merged the old "📚 The menu bar" step into this one. It named
        # `.st-key-top_menu`, a container that stopped being created when
        # #UX-63 emptied the settings row — so it had been highlighting nothing
        # (`tests/test_tour.py` now catches that) — and its two subjects are
        # nav entries themselves, which makes this the same target.
        "selector": NAV_SELECTOR,
        "title": f"{ICONS['nav']} The nav",
        "body": f"**{ICONS['view_scanpath']} Scanpath** is this view. "
        f"**{ICONS['view_corpus']} Corpus Analysis** pools all participants; "
        f"**{ICONS['view_data']} Data Management** lists your "
        f"datasets and adds new ones. **{ICONS['help']} Help** opens over your work.",
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
/* UX-200: `box-shadow: none` above took Streamlit's focus ring too. */
.st-key-tour_sp_close button:focus-visible {
    opacity: 1;
    outline: 2px solid var(--sps-accent);
    outline-offset: 1px;
}
/* Vertical rhythm inside the card: body → progress → Back / Next footer (the
   gap around the progress bar is set on both sides — the column row is what
   actually carries it). The card's own bottom padding is trimmed to match. */
.st-key-tour_card [data-testid="stProgress"] {
    margin-top: 0.5rem;
    margin-bottom: 0.9rem;
}
.st-key-tour_card [data-testid="stHorizontalBlock"] { margin-top: 0.9rem; }
/* UX-12 "Don't show this again": a footnote between the progress bar and the
   footer, so it's muted and pulled tight rather than reading as another step.
   UX-110 gives the wizard-setup-guide card (same `tour_card` shape) the
   identical treatment for its own opt-out. */
.st-key-tour_dont_show,
.st-key-wizard_guide_dont_show { margin-top: -0.5rem !important; }
.st-key-tour_dont_show label,
.st-key-wizard_guide_dont_show label { opacity: 0.8; }
.st-key-tour_dont_show label p,
.st-key-wizard_guide_dont_show label p { font-size: 0.85rem !important; }
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


def _card_colors_css() -> str:
    """The guide card's and its folded tab's colours, following the theme
    when the runtime exposes it (st.context.theme, Streamlit ≥1.46)."""
    theme = getattr(getattr(st, "context", None), "theme", None)
    is_dark = getattr(theme, "type", "light") == "dark"
    bg, border = ("#262730", "#41434e") if is_dark else ("#ffffff", "#d5d6d9")
    return (
        f'.st-key-tour_card, [class*="st-key-guide_pill_"] {{ background: {bg}; '
        f"border: 1px solid {border}; }}"
    )


# -----------------------------------------------------------------------------
# Moving and folding a guide card (2026-10-09)
# -----------------------------------------------------------------------------
# Every guide card — the welcome tour, a tutorial, the setup guide — can be
# dragged by its title to wherever it covers nothing, and folded (—) to a small
# tab that keeps its place. ``kind`` names the card ("tour", "tutorial",
# "wizard"): its folded flag, its buttons' keys and its remembered spot are its
# own. Arming a guide unfolds it.


def _guide_folded_key(kind: str) -> str:
    return f"_guide_folded_{kind}"


def guide_folded(kind: str) -> bool:
    """Whether the ``kind`` guide is folded to its tab."""
    return bool(st.session_state.get(_guide_folded_key(kind)))


def _set_guide_folded(kind: str, folded: bool) -> None:
    st.session_state[_guide_folded_key(kind)] = folded


def _render_guide_fold_button(kind: str, name: str) -> None:
    """The card's — button, pinned to its top-right corner (left of a ✕)."""
    st.button(
        f"— {spoken(f'Fold the {name}')}",
        key=f"guide_fold_{kind}",
        on_click=_set_guide_folded,
        args=(kind, True),
        help=f"Fold the {name} to a small tab. Drag it by its title to move it.",
    )


def _render_guide_pill(kind: str, label: str, progress: str, name: str) -> None:
    """The folded card: a tab naming the guide and where it is, with Open."""
    with st.container(
        key=f"guide_pill_{kind}",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
    ):
        st.markdown(f"**{label}** · {progress}")
        st.button(
            "Open",
            key=f"guide_unfold_{kind}",
            on_click=_set_guide_folded,
            args=(kind, False),
            help=f"Open the {name} again.",
        )
        embed_html_iframe(_guide_drag_script(kind), height=0)


#: The card's title is its handle; the fold button sits in the corner, left of
#: the welcome tour's ✕ where there is one; the folded tab is a fixed pill.
_GUIDE_MOVE_CSS = """
.st-key-tour_card h2 { cursor: move; user-select: none; }
[class*="st-key-guide_fold_"] {
    position: absolute;
    top: 0.6rem;
    right: 0.5rem;
    width: auto;
    z-index: 1;
}
.st-key-tour_card:has(.st-key-tour_sp_close) [class*="st-key-guide_fold_"] {
    right: 2.3rem;
}
.st-key-tour_card:has(.st-key-tour_sp_close) h2 { padding-right: 3.6rem !important; }
[class*="st-key-guide_fold_"] button {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    min-height: 0 !important;
    padding: 0.05rem 0.4rem !important;
    font-size: 1.05rem;
    line-height: 1;
    opacity: 0.6;
}
[class*="st-key-guide_fold_"] button:hover { opacity: 1; }
[class*="st-key-guide_fold_"] button:focus-visible {
    opacity: 1;
    outline: 2px solid var(--sps-accent);
    outline-offset: 1px;
}
[class*="st-key-guide_pill_"] {
    position: fixed;
    bottom: 1.25rem;
    right: 1.25rem;
    z-index: 999990;
    width: auto;
    padding: 0.35rem 0.5rem 0.35rem 0.85rem;
    border-radius: 999px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.3);
    cursor: move;
    user-select: none;
}
[class*="st-key-guide_pill_"] p { margin: 0; font-size: 0.88rem; white-space: nowrap; }
[class*="st-key-guide_pill_"] button { min-height: 1.8rem; padding: 0 0.6rem; }
/* The drag script's carrier: out of the tab's row, still loaded. */
[class*="st-key-guide_pill_"] [data-testid="stElementContainer"]:has(iframe) {
    position: absolute;
    width: 0;
    height: 0;
    overflow: hidden;
}
"""

#: Drags the card by its title (the folded tab from anywhere but its button)
#: and puts it back where it was last left — in this tab's `sessionStorage`,
#: so a reload keeps it and a new tab starts where the card's CSS puts it.
#: Listens on the card's container, which survives a step change, rather than
#: on the title, which a new step's text can replace. ``transform: none``
#: un-centres the welcome card once it has been moved.
_GUIDE_DRAG_SCRIPT = """<script>
(function () {
  const doc = window.parent.document;
  const win = doc.defaultView;
  const KEY = "sps_guide_pos___KIND__";
  const PILL = ".st-key-guide_pill___KIND__";
  const SEL = ".st-key-tour_card, " + PILL;
  const place = (el, x, y) => {
    const r = el.getBoundingClientRect();
    x = Math.min(Math.max(0, x), Math.max(0, win.innerWidth - r.width));
    y = Math.min(Math.max(0, y), Math.max(0, win.innerHeight - r.height));
    el.style.left = x + "px";
    el.style.top = y + "px";
    el.style.right = "auto";
    el.style.bottom = "auto";
    el.style.transform = "none";
  };
  // A card being drawn is meant to be seen: drop a ✕'s instant-hide style
  // left from an earlier guide (a tutorial card draws no listener to do it).
  doc.getElementById("tour-instant-hide")?.remove();
  let tries = 0;
  (function wire() {
    const el = doc.querySelector(SEL);
    if (!el) {
      if (++tries < 30) setTimeout(wire, 100);
      return;
    }
    try {
      const saved = JSON.parse(win.sessionStorage.getItem(KEY) || "null");
      if (saved) place(el, saved[0], saved[1]);
    } catch (e) {}
    if (el.dataset.spsDrag) return;
    el.dataset.spsDrag = "1";
    el.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0 || ev.target.closest("button, input, label, a")) return;
      if (!el.matches(PILL) && !ev.target.closest("h2")) return;
      const r = el.getBoundingClientRect();
      const dx = ev.clientX - r.left, dy = ev.clientY - r.top;
      const move = (e) => place(el, e.clientX - dx, e.clientY - dy);
      const up = () => {
        doc.removeEventListener("pointermove", move);
        doc.removeEventListener("pointerup", up);
        const r2 = el.getBoundingClientRect();
        try {
          win.sessionStorage.setItem(KEY, JSON.stringify([r2.left, r2.top]));
        } catch (e) {}
      };
      doc.addEventListener("pointermove", move);
      doc.addEventListener("pointerup", up);
      ev.preventDefault();
    });
  })();
})();
</script>"""


def _guide_drag_script(kind: str) -> str:
    """`_GUIDE_DRAG_SCRIPT` for the ``kind`` guide's card and tab."""
    return _GUIDE_DRAG_SCRIPT.replace("__KIND__", kind)


def _exit_spotlight() -> None:
    st.session_state["tour_mode"] = None


def _dismiss_listener_script(
    selector: str | None,
    exit_keys: tuple[str, ...] = ("tour_sp_done", "tour_sp_close", "tour_sp_skip"),
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
        '.st-key-tour_card, [class*="st-key-guide_pill_"], .tour-backdrop, '
        f"#{_GROUP_RING_ID} {{ display: none !important; }} " + outline_clear
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


#: Targets that match several elements which read as one control — the nav's
#: links, one `stTopNavLinkContainer` each. Outlining every match drew a row of
#: separate brackets, so these get one ring drawn around all of them instead
#: (`_group_ring_script`), an element of its own the step's CSS styles.
_GROUP_SELECTORS = frozenset({NAV_SELECTOR})
_GROUP_RING_ID = "tour-group-ring"


def _highlight_css(selector: str, accent: str) -> str:
    """The pulsing outline drawn around a tour/guide target.

    Factored out of `render_spotlight_tour` (DATA-22 §4) so the setup guide can
    highlight wizard steps with exactly the same treatment the welcome tour uses
    — the guide documented its own gap ("the steps are descriptive, not anchored
    to specific controls") while this machinery sat 800 lines above it.

    A `_GROUP_SELECTORS` target outlines the one ring `_group_ring_script`
    places around its matches, not each match.
    """
    if not selector:
        return ""
    if selector in _GROUP_SELECTORS:
        selector = f"#{_GROUP_RING_ID}"
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


def _group_ring_script(selector: str) -> str:
    """Place one ring around every visible match of a `_GROUP_SELECTORS` target.

    The ring is a ``position: fixed`` box in the page, sized to the matches'
    union (the nav's whole row, ❓ Help included, when they sit in Streamlit's
    nav strip) and styled by the step's own `_highlight_css`. It is added to the
    page by a script that runs in the page, not in this iframe, so it keeps
    following the nav after the iframe is gone — and it removes itself once the
    tour card has gone, or once the step's CSS no longer outlines it (the next
    step, or the tour ended), so no ring can outlive its step.
    """
    page_js = f"""
(function () {{
    const win = window, doc = document;
    if (win.__tourGroupRing) win.clearInterval(win.__tourGroupRing);
    const selector = {selector!r};
    const visible = (el) => {{
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return false;
        const cs = win.getComputedStyle(el);
        return cs.visibility !== "hidden" && cs.display !== "none"
            && cs.opacity !== "0";
    }};
    let ticks = 0, styled = false;
    const stop = () => {{
        win.clearInterval(win.__tourGroupRing);
        win.__tourGroupRing = null;
        doc.getElementById({_GROUP_RING_ID!r})?.remove();
    }};
    const place = () => {{
        ticks += 1;
        let ring = doc.getElementById({_GROUP_RING_ID!r});
        if (!ring) {{
            ring = doc.createElement("div");
            ring.id = {_GROUP_RING_ID!r};
            // Above Streamlit's header (the nav lives in it), under popovers.
            ring.style.cssText = "position:fixed;pointer-events:none;"
                + "z-index:1000050;";
            doc.body.appendChild(ring);
        }}
        const outlined = win.getComputedStyle(ring).outlineStyle !== "none";
        styled = styled || outlined;
        const cardGone = !doc.querySelector(".st-key-tour_card");
        if ((styled && !outlined) || (ticks > 50 && (cardGone || !outlined))) {{
            stop();
            return;
        }}
        const matches = [...doc.querySelectorAll(selector)].filter(visible);
        const strip = matches[0]?.closest(".rc-overflow");
        const boxes = strip
            ? [...strip.children].filter(visible)
            : matches;
        if (!boxes.length) {{
            ring.style.display = "none";
            return;
        }}
        const rects = boxes.map((el) => el.getBoundingClientRect());
        const left = Math.min(...rects.map((r) => r.left));
        const top = Math.min(...rects.map((r) => r.top));
        const right = Math.max(...rects.map((r) => r.right));
        const bottom = Math.max(...rects.map((r) => r.bottom));
        Object.assign(ring.style, {{
            display: "block",
            left: left + "px",
            top: top + "px",
            width: right - left + "px",
            height: bottom - top + "px",
        }});
    }};
    place();
    win.__tourGroupRing = win.setInterval(place, 200);
}})();
"""
    return f"""<script>
    (function () {{
        const doc = window.parent.document;
        const s = doc.createElement("script");
        s.textContent = {page_js!r};
        doc.head.appendChild(s);
        s.remove();
    }})();
    </script>"""


#: UX-101, measured live (Streamlit 1.62, 1440×900): a popover's panel is drawn
#: at ``z-index: 1000060``, above the card's 999990 — so on a step that opens
#: one, the panel covered the card's left edge and cut the first word off every
#: line. Raise the card **only on those steps**; everywhere else it stays under
#: Streamlit's own overlays, where a floating card belongs.
_CARD_OVER_POPOVER_CSS = ".st-key-tour_card { z-index: 1000070; }"


def _all_popover_triggers() -> str:
    """One selector matching every popover trigger the tour knows how to open.

    Derived from the steps themselves rather than listed, so a step that starts
    opening a second popover is closed again by the steps after it for free.
    """
    declared = {step.get("popover") for step in _SPOTLIGHT_STEPS}
    declared |= {step.popover for tutorial in TUTORIALS for step in tutorial.steps}
    return ", ".join(sorted(trigger for trigger in declared if trigger))


def _popover_script(trigger: str) -> str:
    """Open the popover this step points inside, and close the last step's.

    A closed Streamlit popover renders **no body**: before UX-101 the two
    *narrow the pool* steps pointed at a container that only exists while the
    funnel is open, so the spotlight retried for 30 s and then gave up in
    silence — no highlight, no scroll, no error, and the card still advanced.

    Opening it is the one piece of state the tour touches, and it is chrome, not
    data: no widget inside is read or written, so the tutorial's promise that it
    "never changes a filter" holds. Clicking is gated on ``aria-expanded`` so a
    funnel the user already opened is left alone (a second click would close
    it), and every *other* trigger the tour opens is closed, so the panel from
    the previous step cannot sit over this step's target.
    """
    others = _all_popover_triggers()
    if not (trigger or others):
        return ""
    return f"""<script>
                (function () {{
                    const doc = window.parent.document;
                    const win = doc.defaultView;
                    const wanted = {trigger!r};
                    const all = {others!r};
                    // Only ever click a trigger that is really on screen.
                    // Streamlit keeps a 0x0 twin of the picker row in the DOM,
                    // so a plain querySelector can land on a button nobody can
                    // see — the same trap `_scroll_into_view_script` documents.
                    const visible = (el) => {{
                        const r = el.getBoundingClientRect();
                        if (!r.width || !r.height) return false;
                        const cs = win.getComputedStyle(el);
                        return cs.visibility !== "hidden" && cs.display !== "none";
                    }};
                    let tries = 0;
                    (function attempt() {{
                        if (wanted) {{
                            const target = [...doc.querySelectorAll(wanted)]
                                .find(visible);
                            if (!target) {{
                                // Riding out the first run, where the card
                                // streams to the browser well before the picker
                                // row it points at (see render_spotlight_tour).
                                if (++tries < 200) setTimeout(attempt, 150);
                                return;
                            }}
                            if (target.getAttribute("aria-expanded") !== "true") {{
                                target.click();
                            }}
                        }}
                        if (!all) return;
                        for (const other of doc.querySelectorAll(all)) {{
                            if (wanted && other.matches(wanted)) continue;
                            if (other.getAttribute("aria-expanded") === "true"
                                    && visible(other)) {{
                                other.click();
                            }}
                        }}
                    }})();
                }})();
                </script>"""


#: What covers the top of the page: Streamlit's fixed header, and the sticky
#: bar of the add-dataset wizard and of ✏️ Edit dataset (`styles.py` makes each
#: bar's `stLayoutWrapper` the sticky element).
_TOP_OVERLAYS = (
    '[data-testid="stHeader"], '
    '[data-testid="stLayoutWrapper"]:has(> .st-key-wiz_sticky_bar), '
    '[data-testid="stLayoutWrapper"]:has(> .st-key-dataset_editor_bar)'
)


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

    The scroller's top is not all on screen: Streamlit's fixed header and the
    wizard's sticky bar (`_TOP_OVERLAYS`) cover it. Measured from the
    scroller's own top, the setup guide's part 2 landed under both — its title
    and first fields hidden, the card over what was left — so a target now
    lands below them, and one taller than the room left is aligned by its top.
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
                    // Where the uncovered viewport starts: below the fixed
                    // header, and below a sticky bar where it rests (its `top`
                    // + height), whether or not it is stuck yet.
                    const coveredTo = () => {{
                        let bottom = 0;
                        for (const el of doc.querySelectorAll({_TOP_OVERLAYS!r})) {{
                            const r = el.getBoundingClientRect();
                            if (!r.width || !r.height) continue;
                            const cs = win.getComputedStyle(el);
                            if (cs.position === "fixed") {{
                                bottom = Math.max(bottom, r.bottom);
                            }} else if (cs.position === "sticky") {{
                                bottom = Math.max(
                                    bottom, (parseFloat(cs.top) || 0) + r.height);
                            }}
                        }}
                        return bottom;
                    }};
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
                                const top = Math.max(b.top, coveredTo());
                                const room = b.top + box.clientHeight - top;
                                const slack = 8;
                                if (r.top >= top - slack
                                        && r.bottom <= top + room + slack) {{
                                    return;  // already visible within its scroller
                                }}
                                box.scrollTop += r.top - top
                                    - Math.max(0, (room - r.height) / 2);
                                return;
                            }}
                        }}
                    }})();
                }})();
                </script>"""


@st.fragment
@guarded()
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
    progress_text = f"Step {step_idx + 1} of {n}"
    if guide_folded("tour"):
        # Folded: the tab alone — no backdrop, highlight or opened popover.
        st.markdown(
            "<style>" + _card_colors_css() + _GUIDE_MOVE_CSS + "</style>",
            unsafe_allow_html=True,
        )
        _render_guide_pill("tour", "Welcome tour", progress_text, "tour")
        return

    highlight = _highlight_css(step["selector"], accent)
    st.markdown(
        "<style>"
        + _CARD_CSS
        + _card_colors_css()
        + _GUIDE_MOVE_CSS
        + (_WELCOME_CSS if step_idx == 0 else "")
        + (_CARD_OVER_POPOVER_CSS if step.get("popover") else "")
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
            # UX-200: `spoken` names the glyph for screen readers.
            f"✕ {spoken('Close the tour')}",
            wrap=True,
            key="tour_sp_close",
            on_click=_exit_spotlight,
            help="Close the tour",
        )
        _render_guide_fold_button("tour", "tour")
        # <h2> keeps the page heading outline valid (the card sits right under
        # the page <h1>; an <h4> here would be an h1→h4 jump). Sized back down
        # to the original compact look via `.st-key-tour_card h2` in _CARD_CSS.
        st.markdown(f"## {step['title']}")
        st.markdown(_welcome_body(step["body"]) if step_idx == 0 else step["body"])
        st.progress((step_idx + 1) / n, text=progress_text)
        # UX-12: the opt-out sits on the two steps where a user decides they're
        # finished with the tour — the welcome (bail out now) and the last step
        # (done, don't greet me again). Keeping it off the middle steps preserves
        # the card's tight vertical rhythm.
        if step_idx in (0, n - 1):
            _render_tour_optout()
        # The ✕ in the corner closes the tour from any step, so the footer is
        # Back / Next (Skip tour / Next on the welcome, Back / Done on the last).
        back_col, next_col = st.columns(2)
        if step_idx == 0:
            # The welcome has nothing to go back to, so its left slot is a
            # plainly labelled way out instead of a disabled Back — a first-time
            # reader should not have to read the ✕ glyph to start exploring.
            # Same exit as ✕ / Done; Help → Tutorials replays it.
            back_col.button(
                "Skip tour",
                key="tour_sp_skip",
                width="stretch",
                on_click=_exit_spotlight,
                help="Close the tour and start exploring. Replay it any time "
                "from Help → Tutorials.",
            )
        else:
            back_col.button(
                "← Back",
                key="tour_sp_back",
                width="stretch",
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
        embed_html_iframe(_guide_drag_script("tour"), height=0)

        # UX-101: raise the popover this step points inside (and lower the one
        # the last step raised) BEFORE the find-and-scroll below goes looking —
        # a closed popover has no body for it to find.
        popover_script = _popover_script(step.get("popover", ""))
        if popover_script:
            embed_html_iframe(popover_script, height=0)

        if step["selector"] in _GROUP_SELECTORS:
            embed_html_iframe(_group_ring_script(step["selector"]), height=0)
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
    _set_guide_folded("tour", False)
    if TOUR_STYLE == "spotlight":
        st.session_state["tour_mode"] = "spotlight"
    else:
        _tour_dialog()


def _open_dataset_name() -> str | None:
    """The name of the dataset this session has open, as the picker shows it."""
    from scanpath_studio.constants import DEMO_CHOICE, PUBLIC_DATASETS_CHOICE

    token = st.session_state.get("data_source_choice", DEMO_CHOICE)
    if token == PUBLIC_DATASETS_CHOICE:
        token = st.session_state.get("public_dataset_choice")
    if not token:
        return None
    from scanpath_studio.app import _dataset_display_name  # app imports tour

    return _dataset_display_name(str(token))


def _welcome_body(body: str) -> str:
    """The welcome card's text, naming the dataset that is open (#374 F32)."""
    name = _open_dataset_name()
    if not name:
        return body
    lead, _, rest = body.partition("**Next**")
    return f"{lead}**{name}** is open; **Next**{rest}" if rest else body


def _arm_tour() -> None:
    """``on_click`` callback for the replay button: arm the tour from step 0.

    Callbacks run *before* the rerun, so the tour's render call early in
    ``main()`` — which executes long before the menu button — picks the
    request up within the same run. Dialogs can't be opened from callbacks,
    so the dialog style sets a request flag that ``maybe_show_welcome_tour``
    (the early call site) serves.
    """
    st.session_state["tour_step"] = 0
    _set_guide_folded("tour", False)
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
    # #374 F32: a session recovered from *Saved on this computer* belongs to
    # someone who has used the app here before — a new browser, or cleared
    # site data, cleared the cookie opt-out, not their experience.
    from scanpath_studio.persistence import session_was_restored

    if session_was_restored(st.session_state):
        return
    _start_tour()


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
        return available, "Open a dataset with trials, or loosen the filters."
    if rule == "has_visual_data":
        available = bool(context.get("has_words") or context.get("has_fixations"))
        return (
            available,
            "Open a dataset with words or fixations, or loosen the filters.",
        )
    if rule == "has_comparable_readings":
        available = bool(context.get("has_comparable_readings"))
        return available, "Need two trials of the same text."
    if rule == "has_corpus_variation":
        available = bool(context.get("has_corpus_variation"))
        return available, "Need variation across trials, participants, or texts."
    return False, f"Unknown availability rule: {rule}."


#: #374 F31 — what a rule lacks when the trial filters, not the dataset, are
#: why a tutorial cannot start.
_FILTERED_REASONS = {
    "has_trials": "no trial is left in the pool.",
    "has_visual_data": "the pool has no words or fixations.",
    "has_comparable_readings": "no two trials in the pool share a text.",
    "has_corpus_variation": "the pool holds one trial.",
}


def filtered_reason(
    tutorial: TutorialDefinition, context: dict[str, object]
) -> str | None:
    """Why the **filters** keep ``tutorial`` from starting, or ``None``.

    ``None`` unless the tutorial is unavailable on the filtered pool but would
    be available on the whole dataset — the context's ``unfiltered`` snapshot,
    which `app.main` stashes only while a filter narrows the pool."""
    unfiltered = context.get("unfiltered")
    if not isinstance(unfiltered, dict) or tutorial_availability(tutorial, context)[0]:
        return None
    if not tutorial_availability(tutorial, unfiltered)[0]:
        return None
    return _FILTERED_REASONS.get(tutorial.availability)


def _tutorial_progress() -> dict[str, int]:
    return st.session_state.setdefault("tutorial_progress", {})


def _tutorial_completed() -> dict[str, bool]:
    return st.session_state.setdefault("tutorial_completed", {})


def _start_use_case(tutorial_id: str, *, restart: bool = False) -> None:
    """Start/resume one tutorial while remembering where Exit should return."""
    if tutorial_id not in _TUTORIAL_BY_ID:
        return
    context = st.session_state.get("_tutorial_context") or {}
    tutorial = _TUTORIAL_BY_ID[tutorial_id]
    available, _ = tutorial_availability(tutorial, context)
    if not available:
        return
    st.session_state["tutorial_return"] = {
        "main_nav": st.session_state.get("main_nav", _VIEW_SCANPATH),
        "single_subtab": st.session_state.get("single_subtab", SUBTAB_ANNOTATIONS),
    }
    if restart:
        _tutorial_progress()[tutorial_id] = 0
        _tutorial_completed().pop(tutorial_id, None)
    else:
        _tutorial_progress().setdefault(tutorial_id, 0)
    # UX-83: navigate to the step's own page right away when it names a
    # different view, instead of opening the card on whatever page the user
    # already stood on and offering a "Show me / Open this panel" button to
    # get there. Covers resume too — the current step (not always index 0)
    # is what the card is about to show. `tutorial_return` above already
    # captured the page being left, so Exit still comes back to it.
    step_index = int(_tutorial_progress().get(tutorial_id, 0))
    steps = steps_of(tutorial)
    if 0 <= step_index < len(steps):
        _open_tutorial_surface(steps[step_index])
    st.session_state["tutorial_active"] = tutorial_id
    _set_guide_folded("tutorial", False)
    # Never stack this task card over the automatic welcome/setup card.
    st.session_state["tour_mode"] = None


def _move_use_case(tutorial_id: str, delta: int) -> None:
    tutorial = _TUTORIAL_BY_ID[tutorial_id]
    current = int(_tutorial_progress().get(tutorial_id, 0))
    _tutorial_progress()[tutorial_id] = max(
        0, min(len(steps_of(tutorial)) - 1, current + delta)
    )


def _finish_use_case(tutorial_id: str) -> None:
    _tutorial_completed()[tutorial_id] = True
    _tutorial_progress()[tutorial_id] = len(steps_of(_TUTORIAL_BY_ID[tutorial_id])) - 1
    st.session_state["tutorial_active"] = None


def _restore_tutorial_return() -> None:
    location = st.session_state.get("tutorial_return") or {}
    if location.get("main_nav") is not None:
        st.session_state["main_nav"] = location["main_nav"]
    if location.get("single_subtab") is not None:
        st.session_state["single_subtab"] = location["single_subtab"]
    st.session_state["tutorial_active"] = None


def _open_tutorial_surface(step: TutorialStep) -> None:
    from scanpath_studio.constants import DATASET_EDITOR_OPEN_KEY

    st.session_state["main_nav"] = step.view
    if step.subtab is not None:
        st.session_state["single_subtab"] = step.subtab
    if step.corpus_subtab is not None:
        st.session_state["corpus_subtab"] = step.corpus_subtab
    # DATA-35: the Data page's two screens. A step that points into the editor
    # opens it; one that points at the overview closes it, so walking back up a
    # tutorial does not leave the editor covering the table the previous step
    # was about.
    if step.view == _VIEW_DATA:
        if step.dataset_editor:
            st.session_state[DATASET_EDITOR_OPEN_KEY] = True
        else:
            st.session_state.pop(DATASET_EDITOR_OPEN_KEY, None)


_KNOWN_VIEWS = (_VIEW_SCANPATH, _VIEW_CORPUS, _VIEW_DATA)


def _tutorial_surface_is_open(step: TutorialStep) -> bool:
    """Is the view (and subtab) this step points at the one on screen?

    UX-40: this used to fold everything that was not Corpus Analysis into
    Scanpath, which predates DATA-26's third view — so a step with
    ``view=_VIEW_DATA`` reported "not open" *while the user was standing on the
    Data page*, and the card offered to open the panel they were already
    looking at (and withheld the spotlight that should have been on it).
    """
    from scanpath_studio.constants import DATASET_EDITOR_OPEN_KEY

    current_view = st.session_state.get("main_nav", _VIEW_SCANPATH)
    if current_view not in _KNOWN_VIEWS:
        current_view = _VIEW_SCANPATH
    if current_view != step.view:
        return False
    # DATA-35: on the Data page, "which screen" is part of the answer — an
    # editor step is not open while the overview is showing, and vice versa.
    if step.view == _VIEW_DATA and bool(
        st.session_state.get(DATASET_EDITOR_OPEN_KEY)
    ) != bool(step.dataset_editor):
        return False
    if (
        step.corpus_subtab is not None
        and st.session_state.get("corpus_subtab", "Per text") != step.corpus_subtab
    ):
        return False
    return (
        step.subtab is None
        or st.session_state.get("single_subtab", SUBTAB_ANNOTATIONS) == step.subtab
    )


def _arm_tutorial_library() -> None:
    """Request the tutorial chooser. Called by the ❓ Help nav entry
    (``menu._arm_help_action``)."""
    st.session_state["_tutorial_library_requested"] = True


def maybe_show_tutorial_library() -> None:
    """Open the tutorial chooser if the ❓ Help menu button armed it.

    Served early in ``main()`` beside :func:`maybe_show_faq`, for the same
    reason: the button renders at the bottom of the run.
    """
    if st.session_state.pop("_tutorial_library_requested", False):
        _tutorial_library_dialog()


def stash_tutorial_context(context: dict[str, object]) -> None:
    """Park the context the tutorial chooser reads, without rendering anything.

    UX-65 turned the ❓ Help buttons into nav entries, so there is no longer a
    widget to hang this on — but the dialog still needs to know what is loaded,
    and it can be opened from any view, so the stash has to happen every run.
    """
    st.session_state["_tutorial_context"] = dict(context)


@st.dialog(f"{ICONS['tutorials']} Tutorials", width="large")
@guarded()
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
        "filters and settings are exactly where you left them."
    )
    welcome = st.container(border=True)
    welcome_head, welcome_action = welcome.columns([3, 1], vertical_alignment="center")
    welcome_head.markdown("**Welcome tour**")
    welcome_head.caption("A quick introduction to Scanpath Studio.")
    welcome_head.caption("App overview · about 2 minutes")
    if welcome_action.button("Start", key="tutorial_start_welcome", width="stretch"):
        _arm_tour()
        st.rerun(scope="app")
    # UX-110: the welcome tour's own "Don't show this again" (UX-12), reachable
    # here too — every other card in this dialog already offers its own
    # opt-out (below), so the welcome card was the one place in the whole
    # chooser missing it.
    _render_tour_optout(welcome, key_suffix="_picker")
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
            state = f"Paused at step {progress + 1} of {len(steps_of(tutorial))}"
        elif completed:
            state = "Completed — replay any time"
        else:
            state = f"{len(steps_of(tutorial))} steps · {tutorial.estimated_time}"
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
            because = filtered_reason(tutorial, context)
            card.caption(
                f"{ICONS['warning']} Unavailable with the current filters — {because}"
                if because
                else f"{ICONS['warning']} Unavailable — {reason.lower()}"
            )


@st.fragment
@guarded()
def render_use_case_tutorial() -> None:
    """Render the active named tutorial with safe, explicit navigation."""
    tutorial_id = st.session_state.get("tutorial_active")
    tutorial = _TUTORIAL_BY_ID.get(tutorial_id)
    if tutorial is None:
        return
    context = st.session_state.get("_tutorial_context") or {}
    available, reason = tutorial_availability(tutorial, context)
    if not available:
        because = filtered_reason(tutorial, context)
        st.warning(
            f"Tutorial paused: with the current filters, {because}"
            if because
            else f"Tutorial paused: {reason}"
        )
        return
    step_index = min(
        int(_tutorial_progress().get(tutorial.id, 0)), len(steps_of(tutorial)) - 1
    )
    steps = steps_of(tutorial)
    step = steps[step_index]
    progress_text = f"Step {step_index + 1} of {len(steps)}"
    if guide_folded("tutorial"):
        # Folded: the tab alone — no highlight or opened popover.
        st.markdown(
            "<style>" + _card_colors_css() + _GUIDE_MOVE_CSS + "</style>",
            unsafe_allow_html=True,
        )
        _render_guide_pill("tutorial", tutorial.title, progress_text, "tutorial")
        return
    surface_open = _tutorial_surface_is_open(step)
    selector = step.selector if surface_open else None
    accent = st.get_option("theme.primaryColor") or "#1f77b4"
    highlight = _highlight_css(selector or "", accent)
    st.markdown(
        "<style>"
        + _CARD_CSS
        + _card_colors_css()
        + _GUIDE_MOVE_CSS
        + (_CARD_OVER_POPOVER_CSS if step.popover else "")
        + highlight
        + "</style>",
        unsafe_allow_html=True,
    )
    with st.container(key="tour_card"):
        if selector in _GROUP_SELECTORS:
            # Inside the card, like every tour iframe (see render_spotlight_tour).
            embed_html_iframe(_group_ring_script(selector), height=0)
        st.markdown(f"## {tutorial.title}")
        _render_guide_fold_button("tutorial", "tutorial")
        st.markdown(f"**{step.title}**")
        st.markdown(step.body)
        if not surface_open and st.button(
            "Open this panel",
            key="tutorial_open_surface",
            type="primary",
            width="stretch",
        ):
            _open_tutorial_surface(step)
            st.rerun()
        st.progress(
            (step_index + 1) / len(steps),
            text=progress_text,
        )
        st.link_button(
            "Read this in the docs ↗",
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
        if step_index < len(steps) - 1:
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

        embed_html_iframe(_guide_drag_script("tutorial"), height=0)

        popover_script = _popover_script(step.popover)
        if popover_script:
            embed_html_iframe(popover_script, height=0)

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

# (question, markdown answer). Two-to-four lines each — anything longer belongs
# on the docs page.
_WHERE_DATA_GOES = "Where does my data go?"

_FAQ_ITEMS = [
    (
        "A column was mapped to the wrong field. Where do I fix it?",
        f"{ICONS['view_data']} **Data Management → {ICONS['edit']} Edit dataset → 2 · Data tables & column mapping** — an "
        "editable form that "
        "re-derives everything in place, no re-upload. It can only offer columns "
        "that survived the import; anything dropped needs a re-upload.",
    ),
    (
        "What counts as a “trial”?",
        "One reading event — one participant reading one text once — and it is "
        "whatever your **Trial ID** mapping says it is. EyeLink's `TRIAL_INDEX` "
        "only identifies a trial *within* a participant, and the text id falls back to "
        "the trial id, so map your item column as **Text ID** if trial order was "
        "randomized.",
    ),
    # #374 F22: the answer depends on where the app runs — `faq_items` fills
    # it in from `_where_data_goes`, so a hosted copy never says "nowhere".
    (_WHERE_DATA_GOES, ""),
    (
        "My uploaded data vanished after a refresh.",
        "Local and desktop runs normally recover uploaded datasets, settings and "
        f"annotations automatically. Check **{ICONS['view_data']} Data Management → Saved on this computer** "
        "to see whether it is enabled and where it is saved. For a portable "
        f"copy, export annotations from **{ICONS['view_data']} Data Management → Annotations** and the "
        f"figure's settings from **{ICONS['view_scanpath']} Scanpath → {ICONS['share']} Share → File**; neither file "
        "holds dataset rows.",
    ),
    (
        "How do I turn the recovery copy off, or delete it?",
        "Start the app with `scanpath-studio run --no-persist` (or set "
        "`SCANPATH_STUDIO_PERSIST=0`) and nothing is saved. "
        "`scanpath-studio cache --clear` deletes what is already stored, and "
        "`SCANPATH_STUDIO_STATE_DIR=/your/folder` saves it somewhere else.",
    ),
    (
        "PDF or video export fails but HTML works.",
        "The current figure's **PNG** and **SVG** are saved by your browser from "
        "the plot on screen, so they always work. **PDF**, **GIF**/**MP4** and "
        "the images in the export and Compare bundles go through Kaleido, which "
        "drives a headless "
        "Chrome, Chromium or Edge — install one of them (in a pip install, "
        "`plotly_get_chrome -y` also works). **HTML** export is browser-free and "
        "always available.",
    ),
    (
        "How do I cite Scanpath Studio?",
        f"See **{ICONS['about']} About** under {ICONS['help']} Help (and `CITATION.cff` in the "
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
        f"correction**, or compare all ten in the **{ICONS['line_assignment']} Line assignment** subtab.",
    ),
]


def _where_data_goes() -> str:
    """ "Where does my data go?" for where this app is running (#374 F22).

    Local means the server listens on loopback only — its own configuration,
    which ENG-56 made the test for the recovery copy too — as ``scanpath-studio``
    and the desktop app do. Anything else (the online demo, a bare
    ``streamlit run``) processes an upload on a server other machines reach.
    """
    from scanpath_studio.persistence import (
        persistence_enabled,
        server_bound_to_loopback,
    )

    if not server_bound_to_loopback():
        kept = (
            "a recovery copy is kept there"  # opted in: SCANPATH_STUDIO_PERSIST=1
            if persistence_enabled()
            else "not kept"
        )
        return (
            "To the server this app runs on, not your computer: a file you "
            f"upload is processed there and {kept}. No accounts, no database, "
            "no analytics — but don't upload identifiable data to a server you "
            "don't control. Run it locally (`pip install scanpath-studio`, then "
            "`scanpath-studio`) to keep it on your computer; a bare `streamlit "
            "run` also needs `--server.address=127.0.0.1`."
        )
    answer = (
        "Nowhere: it stays on your computer — no accounts, no database, no "
        "analytics, no upload."
    )
    if persistence_enabled():
        answer += (
            " This run also keeps a **recovery copy** (datasets, mappings, "
            "settings, annotations), so a refresh resumes where you left off; "
            f"**{ICONS['view_data']} Data Management → Saved on this computer** "
            "says what is stored and where."
        )
    return answer


def faq_items() -> list:
    """The FAQ entries this build can honestly answer (PRE-21)."""
    items = [
        (question, _where_data_goes() if question == _WHERE_DATA_GOES else answer)
        for question, answer in _FAQ_ITEMS
    ]
    if drift_correction_enabled():
        items.extend(_DRIFT_FAQ_ITEMS)
    return items


@st.dialog(f"{ICONS['faq']} Frequently asked questions", width="large")
@guarded()
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
    docs_col, tutorials_col, close_col = st.columns(3)
    docs_col.link_button(
        f"{ICONS['docs']} Full FAQ ↗",
        DOCS_FAQ_URL,
        width="stretch",
        help="Every question, with the long answers. Opens in a new tab.",
    )
    tutorials_col.link_button(
        f"{ICONS['course']} Tutorials ↗",
        DOCS_TUTORIALS_URL,
        width="stretch",
        help="Task-by-task walkthroughs: data collection, data filtering, "
        "exporting figures, corpus analysis. Opens in a new tab.",
    )
    if close_col.button("✓ Close", key="faq_close", width="stretch", type="primary"):
        _close_dialog_clientside()


def _arm_faq() -> None:
    """Request the FAQ dialog. Called by the ❓ Help nav entry
    (``menu._arm_help_action``).

    Dialogs can't be opened from there, so this only sets a flag that
    :func:`maybe_show_faq` — called early in ``main()`` — serves.
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


# -----------------------------------------------------------------------------
# Dataset-setup guide (the "📂 Set up your dataset" wizard's own walkthrough).
#
# A floating card (``render_spotlight_wizard_guide``) — bottom-right until it is
# dragged, foldable to a tab — that walks the user through the upload wizard while they fill it in — the same card style and
# instant-dismiss machinery as the welcome spotlight tour, but keyed on its own
# step counter (``wizard_guide_step``) and run under ``tour_mode == "wizard"`` so
# the two never collide. Auto-opens once per session the first time the wizard is
# shown (unless suppressed for embeds/deep-links, or the welcome spotlight tour
# is still on screen so the two don't stack), and is replayable from the
# wizard's "❓ Show setup guide" button.
#
# UX-110: this is the third first-visit walkthrough in the app (after the
# welcome tour and the per-tutorial cards), and until now the only one with no
# persistent opt-out — ``wizard_guide_seen`` gates the auto-open, but it is
# plain session state, so the guide came back to greet every new tab/session
# regardless of a prior "I get it, stop". It now carries the same cookie +
# checkbox shape as the other two.
# -----------------------------------------------------------------------------

# One year, path=/, SameSite=Lax — same shape as ``TOUR_OPTOUT_COOKIE``, no
# personal data, just a UI preference.
WIZARD_GUIDE_OPTOUT_COOKIE = "sps_wizard_guide_optout"


def wizard_guide_opted_out() -> bool:
    """True when this browser asked never to auto-open the setup guide again.

    Same shape as :func:`tour_opted_out`: ``_wizard_guide_dismissed`` (a plain
    flag, not the checkbox's own widget key — see that function's docstring
    for why) wins within a session, falling back to the cookie, then to
    ``False`` with no request context (bare mode / AppTest).
    """
    if "_wizard_guide_dismissed" in st.session_state:
        return bool(st.session_state["_wizard_guide_dismissed"])
    try:
        return st.context.cookies.get(WIZARD_GUIDE_OPTOUT_COOKIE) == "1"
    except Exception:
        return False


def _wizard_guide_optout_script(opted_out: bool) -> str:
    """A same-origin script that writes (or clears) the opt-out cookie."""
    if opted_out:
        value = f"{WIZARD_GUIDE_OPTOUT_COOKIE}=1; max-age={_TOUR_OPTOUT_MAX_AGE}"
    else:
        value = f"{WIZARD_GUIDE_OPTOUT_COOKIE}=; max-age=0"
    return (
        "<script>window.parent.document.cookie = "
        f'"{value}; path=/; SameSite=Lax";</script>'
    )


def _render_wizard_guide_optout() -> None:
    """The "Don't show this again" checkbox for the setup guide (UX-110).

    One call site today (the guide's own running card) — there is no picker
    equivalent to sync with, unlike the welcome tour and the per-tutorial
    cards, so this is simpler than :func:`_render_tour_optout`: no second
    widget key, no last-synced reconciliation, just seed-once-then-let-the-
    widget-own-it, same as any ordinary Streamlit checkbox. Kept as its own
    function (rather than inlined) so a second surface — should one ever
    replay this guide from somewhere else — has one place to reuse.
    """
    key = "wizard_guide_dont_show"
    if key not in st.session_state:
        st.session_state[key] = wizard_guide_opted_out()
    opted_out = st.checkbox(
        "Don't show this again",
        key=key,
        help=f"Skip the setup guide on future visits. **{ICONS['help']} Show setup guide** in "
        "the wizard always brings it back.",
    )
    st.session_state["_wizard_guide_dismissed"] = opted_out
    embed_html_iframe(_wizard_guide_optout_script(opted_out), height=0)


# (title, markdown body) per step — an overview, one per part of the wizard in
# order, then the closing Save card.
# DATA-22 §4: the guide is now *anchored*. Each step names the wizard step it
# talks about (so Next drives the accordion instead of narrating beside it) and a
# CSS selector to highlight + scroll to. Keyed expanders give every step a
# `.st-key-wiz_open_<id>` selector for free, so no new wrapper containers were
# needed; finer targets reuse existing widget keys.
_WIZARD_GUIDE_STEPS = [
    {
        "title": f"{ICONS['datasets']} Set up your dataset",
        "body": (
            "Turn your eye-tracking tables into an interactive dataset: name "
            "it, upload and map each table (and pick which extras to keep), "
            "and describe the recording setup — then save it. "
            "Follow along with **Next**, or **Skip** to dive in."
        ),
        "selector": "",
        "step_id": None,
    },
    {
        "title": "1 · Name & description",
        "body": (
            f"Name it — this is what shows up on the {ICONS['view_data']} **Data Management** page and in the "
            "dataset picker, so you can switch back to it later. A description "
            "is optional."
        ),
        "selector": ".st-key-wiz_part_name",
        "step_id": "name",
    },
    {
        "title": "2 · Upload data tables",
        "body": (
            "Every table uploads and maps in its own row here — Fixations, "
            "Words (interest areas), Raw gaze, then Participant/Trial/Text "
            "metadata. "
            "Under each mapping, pick which extra columns to keep. "
            "Anything still missing is listed "
            f"above **{ICONS['confirm']} Add dataset**."
        ),
        "selector": ".st-key-wiz_part_data",
        "step_id": "data",
    },
    {
        "title": "3 · Recording setup",
        "body": (
            "Say how you know the screen, physical size and text size the "
            "data was recorded with. Pick one answer for each — nothing is "
            "chosen for you, because a wrong guess here silently rescales "
            "every figure."
        ),
        "selector": ".st-key-wiz_part_setup",
        "step_id": "setup",
    },
    # #417 — the add screen's optional fourth part, drawn only on a local
    # install; `_wizard_guide_steps` leaves this card out wherever it is not.
    {
        "title": "4 · Stimulus images",
        "body": (
            "Optional: a folder on this computer with a screenshot of each "
            "text or trial, drawn under the scanpath. The pattern names each "
            "file from your fields, such as `{text_id}.png`."
        ),
        "selector": ".st-key-wiz_part_images",
        "step_id": "images",
        "local_only": True,
    },
    # The way out of the parts, not one more part — no `step_id`, so the
    # progress line reads "Last step" rather than "Part 5 of 4".
    {
        "title": f"{ICONS['confirm']} Save it",
        "body": (
            f"**{ICONS['confirm']} Add dataset** saves it and opens it, ready to "
            f"explore. **{ICONS['download']} Download setup file** saves this mapping "
            "and recording setup as a file. Next time, *Start from* reuses "
            "either the file or this dataset."
        ),
        "selector": ".st-key-wizard_footer_row",
        "step_id": None,
    },
]


#: The setup guide is a floating card over the wizard (2026-10-09): the wizard
#: used to keep a gutter the card's width down the right of the page, so the
#: card sat beside its fields — at the cost of squeezing every mapping row into
#: what was left. The card is dragged by its title to wherever it covers
#: nothing and folded to a small tab instead, like the welcome tour's and the
#: tutorials' cards. The page keeps room at its foot, so whatever the card
#: covers at the bottom can still be scrolled clear of it.
_WIZARD_GUIDE_PAGE_CSS = """
[data-testid="stMainBlockContainer"] { padding-bottom: 16rem !important; }
"""


def _wizard_guide_steps() -> list[dict]:
    """The guide's cards for the add screen as it is drawn here: the
    *Stimulus images* card only where that part is (a local install)."""
    from .app import local_filesystem_enabled

    local = local_filesystem_enabled()
    return [s for s in _WIZARD_GUIDE_STEPS if local or not s.get("local_only")]


def _wizard_guide_go(step_idx: int) -> None:
    """Move the guide to ``step_idx`` and open the wizard step it describes.

    This is what makes the card *drive* the wizard rather than narrate beside it.
    ``go_to_step`` is safe here because a guide button is an ``on_click``
    callback: it runs before the script re-executes, so the ``wiz_open_*`` writes
    land before the expanders instantiate.
    """
    from . import wizard_shell

    steps = _wizard_guide_steps()
    step_idx = max(0, min(step_idx, len(steps) - 1))
    st.session_state["wizard_guide_step"] = step_idx
    target = steps[step_idx].get("step_id")
    if target:
        wizard_shell.go_to_step(target)


def _wizard_guide_back() -> None:
    _wizard_guide_go(st.session_state.get("wizard_guide_step", 0) - 1)


def _wizard_guide_next() -> None:
    _wizard_guide_go(st.session_state.get("wizard_guide_step", 0) + 1)


def _exit_wizard_guide() -> None:
    st.session_state["tour_mode"] = None


def _wizard_guide_progress(step_idx: int, step: dict) -> str:
    """Where the guide is, counted in the screen's own parts ("2 · Upload data
    tables" is part 2 of 3), not in cards: neither the overview card nor the
    closing Save card is a part, and "Step 3 of 4" under a "2 ·" heading
    contradicted the parts the screen numbers."""
    n_parts = sum(1 for s in _wizard_guide_steps() if s["step_id"])
    if step["step_id"]:
        return f"Part {step_idx} of {n_parts}"
    if step_idx:
        return "Last step · save"
    return f"Overview · {n_parts} parts"


def _wizard_guide_buttons(back_col, exit_col, next_col, step_idx: int, n: int) -> None:
    """Back · Skip · Next (or ✓ Got it on the last step), one column each."""
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


@st.fragment
@guarded()
def render_spotlight_wizard_guide() -> None:
    """The dataset-setup wizard's step-by-step guide card.

    A floating card, draggable by its title and foldable to a tab (see
    *Moving and folding a guide card*). Shares the welcome tour's highlight,
    scroll and instant-dismiss machinery but uses its own ``wizard_guide_step``
    counter and ``tour_mode == "wizard"`` so the two never collide.

    Call early in the wizard's render (``wizard._render_data_setup``) so it
    streams to the browser before the heavy upload/normalize work. Runs as a
    fragment: Back/Next/Skip rerun only the guide.
    """
    if st.session_state.get("tour_mode") != "wizard":
        return
    steps = _wizard_guide_steps()
    n = len(steps)
    step_idx = min(st.session_state.get("wizard_guide_step", 0), n - 1)
    step = steps[step_idx]
    progress_text = _wizard_guide_progress(step_idx, step)
    if guide_folded("wizard"):
        # Folded: the tab alone — no highlight, and nothing scrolled.
        st.markdown(
            "<style>"
            + _card_colors_css()
            + _GUIDE_MOVE_CSS
            + _WIZARD_GUIDE_PAGE_CSS
            + "</style>",
            unsafe_allow_html=True,
        )
        _render_guide_pill("wizard", "Setup guide", progress_text, "setup guide")
        return

    selector = step["selector"]
    accent = st.get_option("theme.primaryColor") or "#1f77b4"
    st.markdown(
        "<style>"
        + _CARD_CSS
        + _card_colors_css()
        + _GUIDE_MOVE_CSS
        + _WIZARD_GUIDE_PAGE_CSS
        + _highlight_css(selector, accent)
        + "</style>",
        unsafe_allow_html=True,
    )
    if selector:
        embed_html_iframe(_scroll_into_view_script(selector), height=0)

    with st.container(key="tour_card"):
        # <h2> for a valid heading outline; sized down via `.st-key-tour_card h2`.
        st.markdown(f"## {step['title']}")
        _render_guide_fold_button("wizard", "setup guide")
        st.markdown(step["body"])
        st.progress((step_idx + 1) / n, text=progress_text)
        # UX-110: same placement rule as the welcome tour's own opt-out — only
        # where a user decides they're done with the guide (the first step,
        # bailing out now, or the last, got it, don't greet me again), so the
        # short middle step keeps its tight vertical rhythm.
        if step_idx in (0, n - 1):
            _render_wizard_guide_optout()
        back_col, exit_col, next_col = st.columns(3)
        _wizard_guide_buttons(back_col, exit_col, next_col, step_idx, n)
    embed_html_iframe(_guide_drag_script("wizard"), height=0)
    # Hide the guide instantly on Skip/Done, even while the wizard's first run
    # is still loading (see _dismiss_listener_script).
    embed_html_iframe(
        _dismiss_listener_script(None, exit_keys=("wizard_sp_exit", "wizard_sp_done")),
        height=0,
    )


def _arm_wizard_guide() -> None:
    """``on_click`` callback for the wizard's "❓ Show setup guide" button.

    Arms the guide card from step 0, unfolded. Callbacks run before the rerun,
    so ``render_spotlight_wizard_guide`` (called as the wizard renders) picks it
    up on the same run — mirroring ``_arm_tour`` for the welcome tour.
    """
    st.session_state["wizard_guide_step"] = 0
    _set_guide_folded("wizard", False)
    st.session_state["tour_mode"] = "wizard"


def maybe_show_wizard_guide() -> None:
    """Arm the dataset-setup guide automatically the first time the wizard is
    shown in a session (the replay button arms it on demand via ``_arm_wizard_guide``).

    Call as the active wizard renders, immediately followed by
    ``render_spotlight_wizard_guide()`` which draws the card. The auto-open is
    skipped for embeds/deep-links, while the welcome spotlight tour is still
    on screen (so the two walkthroughs never stack), and — UX-110 — for a
    browser that already asked never to see it again via
    :func:`wizard_guide_opted_out`. ``wizard_guide_seen`` is set *before*
    arming (mirroring ``tour_seen``) so a dismissal doesn't re-open it on the
    next rerun.
    """
    if st.session_state.get("wizard_guide_seen"):
        return
    if (
        tour_suppressed(st.query_params)
        or st.session_state.get("tour_mode") == "spotlight"
        or wizard_guide_opted_out()
    ):
        return
    st.session_state["wizard_guide_seen"] = True  # before arming — see docstring
    st.session_state["wizard_guide_step"] = 0
    _set_guide_folded("wizard", False)
    st.session_state["tour_mode"] = "wizard"


def render_wizard_guide_button(host) -> None:
    """A button inside the wizard that (re)opens the setup guide from step 1."""
    host.button(
        "Show setup guide",
        key="wizard_guide_replay",
        icon=ICONS["help"],
        # A menu row in the wizard's *Setup help* popover, matching the
        # documentation link beneath it.
        type="tertiary",
        help="Walk through the dataset setup, step by step.",
        on_click=_arm_wizard_guide,
    )
