"""In-app help for replaying a reading, following a task and setting up a dataset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import streamlit as st

from scanpath_studio import ui_mode
from scanpath_studio.build_info import build_info
from scanpath_studio.crash_report import guarded
from scanpath_studio.html_embed import embed_html_iframe
from scanpath_studio.session_keys import (
    CORPUS_GROUP_BY,
    CORPUS_MEASURE,
    CORPUS_SUBTAB,
    SINGLE_ANIMATE,
    SINGLE_COMPARE_TOGGLE,
    SINGLE_SCREEN_ID,
    SINGLE_TRIAL_ID,
    UI_MODE,
)

from .constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    DATA_CURRENT,
    DATA_INSPECTION_KEY,
    DATA_LIBRARY,
    DATA_WORKSPACE_KEY,
    DATA_WORKSPACE_REQUEST,
    DATASET_EDITOR_OPEN_KEY,
    DEMO_CHOICE,
    GUIDE_RETURN_KEY,
    ICONS,
    SUBTAB_ANNOTATIONS,
    SUBTAB_EXPORT,
    SUBTAB_SHARE,
    preprocessing_enabled,
    spoken,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from streamlit.delta_generator import DeltaGenerator

# Reuse the welcome preference so a browser that previously dismissed it stays quiet.
TOUR_OPTOUT_COOKIE = "sps_tour_optout"
_TOUR_OPTOUT_MAX_AGE = 365 * 24 * 60 * 60

# The trial filters live behind one funnel, and a *closed* Streamlit popover
# renders no body — so `tour_grp_narrow_by` is absent from the page until the
# funnel is clicked, and a step aimed at it would silently spotlight nothing. A
# step that points inside a popover names the trigger that opens it here, and
# the spotlight opens it (see `_popover_script`).
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
    #: The published Corpus section, plus the summary unit when the step
    #: targets Texts or Participants in Overview.
    corpus_subtab: str | None = None
    corpus_group_by: str | None = None
    #: The step's target lives on the 🗂️ Data page's **✏️ Edit dataset**
    #: screen rather than its overview, so opening the view is not enough: the
    #: editor has to be raised too, or the spotlight aims at a hidden container.
    dataset_editor: bool = False
    data_section: str = DATA_CURRENT
    #: The step's target is built inside a popover, so it is not in the
    #: page until that popover's trigger is clicked. The selector of the trigger;
    #: the spotlight opens it before it looks for the target (`_popover_script`).
    popover: str = ""
    gate: str | None = None


@dataclass(frozen=True)
class TutorialDefinition:
    """The same instructions are available to read or follow in the app."""

    id: str
    title: str
    docs_url: str
    steps: tuple[TutorialStep, ...]
    requires_full: bool = False


DOCS_URL = build_info().docs_url
DOCS_TUTORIALS_URL = f"{DOCS_URL}tutorials/"


TUTORIALS = (
    TutorialDefinition(
        "load_inspect",
        "Import and check a recording",
        f"{DOCS_URL}guides/loading-data/#add-your-own-data",
        (
            TutorialStep(
                "Add your files",
                "In **Data Management → Dataset library**, choose **Add dataset → Import files**. "
                "Add a Fixations, Words or Raw gaze table, map its columns, and check the recording setup.",
                ".st-key-data_page_add",
                view=_VIEW_DATA,
                data_section=DATA_LIBRARY,
            ),
            TutorialStep(
                "Check the column mapping",
                "In **Current dataset**, open **Edit dataset → Data tables & column mapping**. Check that the participant, "
                "trial, and coordinates match your source columns. Save changes if you correct a mapping.",
                ".st-key-tutorial_column_mapping",
                view=_VIEW_DATA,
                dataset_editor=True,
            ),
            TutorialStep(
                "Check what loaded",
                "In **Current dataset → Overview**, check the participant and trial counts. "
                "Open **Tables** to inspect the records or **Data checks** to review problems.",
                ".st-key-tutorial_data_inspection",
                view=_VIEW_DATA,
            ),
            TutorialStep(
                "Review preprocessing if needed",
                "Under **Edit dataset → Preprocessing**, you can exclude or merge short fixations. "
                "This is optional and is off by default.",
                ".st-key-tutorial_preprocessing",
                view=_VIEW_DATA,
                dataset_editor=True,
                gate="preprocessing",
            ),
        ),
    ),
    TutorialDefinition(
        "filter_annotate",
        "Filter and mark trials",
        f"{DOCS_TUTORIALS_URL}data-filtering/exclude-unsuitable-trials/",
        (
            TutorialStep(
                "Pick a reading",
                "In **Scanpath View**, choose a reading in **Select trial**.",
                ".st-key-tour_grp_trial_picker",
            ),
            TutorialStep(
                "Mark the trial",
                "Under **Annotations**, add a tag or favorite. For a reading with "
                "several screens, choose whether the mark applies to one screen or the whole trial.",
                ".st-key-tutorial_annotations",
                subtab=SUBTAB_ANNOTATIONS,
            ),
            TutorialStep(
                "Filter the trial list",
                "Open the filter beside **Select trial**. Under **By trial annotation**, "
                "include or exclude a tag, or show favorites. The trial picker now lists the matching readings.",
                ".st-key-tour_grp_narrow_by",
                popover=FUNNEL_TRIGGER,
            ),
        ),
        requires_full=True,
    ),
    TutorialDefinition(
        "compare_readings",
        "Compare readings",
        f"{DOCS_URL}guides/scanpath-visualization/controls/#compare",
        (
            TutorialStep(
                "Choose the first reading",
                "In **Scanpath View**, pick a trial with fixations. Choose the **Scanpath** tile for a static comparison.",
                ".st-key-tour_grp_trial_picker",
            ),
            TutorialStep(
                "Choose the second reading",
                "Turn on **Compare readings**. Choose a different reading with fixations in **Trial B**. "
                "If you only have one, choose another dataset under **Dataset B**.",
                ".st-key-tour_grp_view_modes",
            ),
            TutorialStep(
                "Compare the paths",
                "Open **Compare settings** and choose **Side by side** or **Overlay**. "
                "An overlay across datasets needs the same recording screen size.",
                ".st-key-tour_grp_view_modes",
            ),
        ),
        requires_full=True,
    ),
    TutorialDefinition(
        "explore_corpus",
        "Analyze a corpus",
        f"{DOCS_TUTORIALS_URL}corpus-analysis/analyze-one-text/",
        (
            TutorialStep(
                "Choose a text and a measure",
                "In **Texts**, select a dot or search for a text. Choose a reading measure, "
                "such as first fixation duration. The view uses the trials in your current selection.",
                ".st-key-tutorial_corpus_subtabs",
                view=_VIEW_CORPUS,
                corpus_subtab="Overview",
                corpus_group_by="Text",
            ),
            TutorialStep(
                "Read the result",
                "Open **Chart settings** and choose **Cohort profile**. Set **Aggregate** "
                "to how you want to combine the readings and check how many participants contributed.",
                ".st-key-tutorial_corpus_analysis",
                view=_VIEW_CORPUS,
                corpus_subtab="Per text",
            ),
            TutorialStep(
                "Save the table and recipe",
                "Open **Download results**. Save the **CSV** for the values and the **JSON recipe** for the analysis choices. "
                "Keep the original dataset with them.",
                ".st-key-tutorial_corpus_analysis",
                view=_VIEW_CORPUS,
                corpus_subtab="Per text",
            ),
        ),
    ),
    TutorialDefinition(
        "publication_figure",
        "Export or reproduce a figure",
        f"{DOCS_URL}guides/exporting/#from-the-app-to-a-script",
        (
            TutorialStep(
                "Save the current figure",
                "In **Scanpath → Export**, choose a download format under **Current figure**. "
                "HTML keeps the figure interactive. Use **Cite** beside the download for the reference.",
                ".st-key-tutorial_export",
                subtab=SUBTAB_EXPORT,
            ),
            TutorialStep(
                "Reproduce the figure in code",
                "Open **Share → Code**, choose **Python** or **CLI**, and copy the example. "
                "For an uploaded dataset, point it to your own files.",
                ".st-key-tutorial_share",
                subtab=SUBTAB_SHARE,
            ),
            TutorialStep(
                "Share the settings",
                "Choose **Share → Settings file** to download the plot settings. Send your "
                "coauthor the source data separately so they can use the same reading.",
                ".st-key-tutorial_share",
                subtab=SUBTAB_SHARE,
            ),
        ),
    ),
)


_TUTORIAL_BY_ID = {tutorial.id: tutorial for tutorial in TUTORIALS}

#: Which builds show a gated step. Read at *call* time, not at import,
#: so a test (or a session started with the env var) sees the current answer.
_STEP_GATES = {"preprocessing": preprocessing_enabled}


def steps_of(tutorial: TutorialDefinition) -> tuple[TutorialStep, ...]:
    """The tutorial's steps this build can honestly walk.

    A step about a feature this build does not show is dropped rather than
    shown-and-skipped: it would otherwise spotlight a surface that does not
    exist, and count toward "step 3 of 7" for something the reader cannot do.
    """
    return tuple(
        step
        for step in tutorial.steps
        if step.gate is None or _STEP_GATES.get(step.gate, lambda: True)()
    )


def sample_reading_available() -> bool:
    """Whether the current dataset has a bundled sample reading to replay."""
    state = st.session_state
    source = state.get("_pending_source_choice") or state.get(
        "data_source_choice", DEMO_CHOICE
    )
    context = state.get("_tutorial_context") or {}
    return (
        source == DEMO_CHOICE
        and not state.get("_show_upload_wizard")
        and bool(context.get("selected_has_fixations"))
    )


def sample_replay_outside_scanpath(words, fixations, combos) -> bool:
    """Can the Scanpath selection replay when its trial picker is off screen?"""
    from .data import trial_keys
    from .multipart import PART_KEY, SCREEN_ID, extract_part
    from .utils import extract_trial, split_reading_key

    if fixations.empty or combos.empty:
        return False
    selection = st.session_state.get("_share_selection") or {}
    participant = selection.get("participant_id")
    trial = selection.get("trial_id")
    screen = selection.get("screen_id")
    if trial is None:
        participant, trial = split_reading_key(st.session_state.get(SINGLE_TRIAL_ID))
        screen = st.session_state.get(SINGLE_SCREEN_ID)
    if participant is not None and trial is not None:
        rows = extract_trial(fixations, participant, trial)
        if rows.empty or (SCREEN_ID not in words and SCREEN_ID not in rows):
            return not rows.empty
        from .tabs import _part_catalog_for_display

        catalog = _part_catalog_for_display(
            extract_trial(words, participant, trial), rows
        )
        if catalog.empty:
            return True
        screens = catalog[SCREEN_ID].astype(str).tolist()
        screen = screen if screen in screens else screens[0]
        return (
            SCREEN_ID in rows
            and not extract_part(rows, participant, trial, screen).empty
        )
    if not trial_keys(combos).issubset(trial_keys(fixations)):
        # Before a first visit to the picker, its sort can choose any reading.
        return False
    if SCREEN_ID not in words:
        return True
    if SCREEN_ID not in fixations:
        return False
    # Any screen the picker could open must have recorded fixations.
    return bool(
        words.set_index(list(PART_KEY))
        .index.isin(fixations.set_index(list(PART_KEY)).index)
        .all()
    )


def _dismiss_invitation() -> None:
    st.session_state.pop("_sample_invitation", None)
    st.session_state["_tour_dismissed"] = True
    st.session_state["_write_invitation_cookie"] = True


def _use_own_data() -> None:
    from .wizard import _enter_add_data_wizard

    _dismiss_invitation()
    _enter_add_data_wizard()


_SPOTLIGHT_STEPS = (
    {
        "selector": ".st-key-tour_grp_plot",
        "title": "Follow the fixations",
        "body": "During a fixation, the eyes stay relatively still. The replay follows one "
        "reader's fixations in time order. Choose **Pause**, then **Next fixation** "
        "to see when a fixation began and how long it lasted, in milliseconds.",
    },
    {
        "selector": ".st-key-tour_grp_trial_picker",
        "title": "Try another reading",
        "body": "Choose another trial to see how the eyes moved during that reading. "
        "To watch the same trial again, choose **Restart**, then **Play** above the plot.",
    },
)


#: The stacking order of the floating card and its folded tab (written as a
#: literal in `_CARD_CSS` / `_GUIDE_MOVE_CSS`, which are plain strings): above
#: Streamlit's header (999990) and the Essentials | Full switch
#: (`ui_mode.SWITCH_Z_INDEX`, which sits in the header's bar), so a tour never
#: runs under either, and below Streamlit's popovers and modals (1000060 and up).
GUIDE_Z_INDEX = 999995

# The floating card: a keyed st.container pinned bottom-right via its
# `.st-key-tour_card` class. Plain strings (no .format) so the CSS braces
# don't need escaping.
_CARD_CSS = """
.st-key-tour_card {
    position: fixed;
    bottom: 1.25rem;
    right: 1.25rem;
    z-index: 999995;
    width: 410px;
    max-width: calc(100vw - 2.5rem);
    border-radius: 0.75rem;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    padding: 1rem 1.25rem 0.6rem;
    /* `_guide_card` draws the card 1px tall, so nothing of it shows until this
       stylesheet applies; these rules give it its own height back. */
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
}
/* The card's slot in the page: the 1px Streamlit gives a fixed-height
   container, gone once the card itself is fixed out of the flow. */
[data-testid="stLayoutWrapper"]:has(> .st-key-tour_card) {
    height: auto !important;
    flex-basis: auto !important;
}
/* The card title is an <h2> for a valid page heading outline (see the title
   render in render_spotlight_tour), sized like an <h4> so the card stays
   compact. */
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
/* `box-shadow: none` above removes Streamlit's focus ring too, so draw one. */
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
# Moving and folding a guide card
# -----------------------------------------------------------------------------
# Every guide card — sample replay, task walkthrough or setup guide — can be
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


def _guide_card() -> DeltaGenerator:
    """The guide card's container, drawn 1px tall until `_CARD_CSS` applies.

    The card's stylesheet is raw HTML in a markdown block, which the browser
    draws only once Streamlit has fetched its HTML renderer, a separate script
    loaded on first use (seconds on a slow connection). The card's title, body
    and buttons need no such script and would otherwise show first, inline at
    the top of the page as if they were its heading. A fixed-height container
    clips its content without any stylesheet of ours, and `_CARD_CSS` releases
    the height in the same paint that pins the card.
    """
    return st.container(key="tour_card", height=1, border=False)


def _render_guide_fold_button(kind: str, name: str) -> None:
    """The card's — button, pinned to its top-right corner (left of a ✕)."""
    st.button(
        f"— {spoken(f'Minimize the {name}')}",
        key=f"guide_fold_{kind}",
        on_click=_set_guide_folded,
        args=(kind, True),
        help=f"Minimize the {name} to a small tab. Drag it by its title to move it.",
    )


def _render_guide_pill(
    kind: str, label: str, progress: str, name: str, *, on_close=None
) -> None:
    """The folded card: a tab naming the guide and where it is, with Open.

    ``on_close`` adds a ✕ that ends the guide from the tab, so a folded guide
    can be dismissed without opening it again first.
    """
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
        if on_close is not None and st.button(
            f"✕ {spoken(f'Close the {name}')}",
            key=f"guide_close_{kind}",
            help=f"Close the {name}",
        ):
            on_close()
            st.rerun(scope="app")
        embed_html_iframe(_guide_drag_script(kind), height=0)


#: The card's title is its handle; the fold button sits in the corner, left of
#: the sample guide's ✕ where there is one. The folded tab is a fixed pill.
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
    z-index: 999995;
    width: auto;
    padding: 0.35rem 0.5rem 0.35rem 0.85rem;
    border-radius: 999px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.3);
    cursor: move;
    user-select: none;
}
[class*="st-key-guide_pill_"] p { margin: 0; font-size: 0.88rem; white-space: nowrap; }
[class*="st-key-guide_pill_"] button { min-height: 1.8rem; padding: 0 0.6rem; }
/* The folded guide has a close button beside Open. */
[class*="st-key-guide_close_"] button {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 0.35rem !important;
    opacity: 0.6;
}
[class*="st-key-guide_close_"] button:hover { opacity: 1; }
[class*="st-key-guide_close_"] button:focus-visible {
    opacity: 1;
    outline: 2px solid var(--sps-accent);
    outline-offset: 1px;
}
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
    el.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      const close = el.querySelector('.st-key-tour_sp_close button, .st-key-tutorial_exit button, ' +
        '.st-key-wizard_sp_exit button, .st-key-wizard_sp_done button, [class*="st-key-guide_close_"] button');
      if (close) {
        event.preventDefault();
        close.click();
      }
    });
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


def _request_sample_exit(*, return_to_view: bool = True) -> None:
    st.session_state["_sample_exit"] = return_to_view


def restore_sample_on_rerun() -> None:
    """Restore the plot before widgets mount when the guide closed on the last run."""
    if "_sample_exit" in st.session_state:
        _exit_spotlight(return_to_view=st.session_state.pop("_sample_exit"))


def _data_location() -> dict:
    """Remember the Data Management tab, its inspection panel and an open editor."""
    state = st.session_state
    return {
        DATA_WORKSPACE_KEY: state.get(DATA_WORKSPACE_REQUEST)
        or state.get(DATA_WORKSPACE_KEY, DATA_CURRENT),
        DATA_INSPECTION_KEY: state.get(DATA_INSPECTION_KEY, "Overview"),
        DATASET_EDITOR_OPEN_KEY: bool(state.get(DATASET_EDITOR_OPEN_KEY)),
    }


def _restore_guide_location(original: dict) -> None:
    """Apply the user's settings through the same paths as their controls."""
    if CORPUS_SUBTAB in original:
        from .corpus_navigation import request_route

        request_route()
    for key, value in original.items():
        if key == DATA_WORKSPACE_KEY:
            # The tab may still belong to the previous page's widget tree.
            # The Data page consumes this request before mounting its tabs.
            st.session_state[DATA_WORKSPACE_REQUEST] = value
        elif key == "global_anim_autoplay":
            from .controls import write_through

            write_through(key, value)
        else:
            st.session_state[key] = value


def _exit_spotlight(*, return_to_view: bool = True) -> None:
    """Undo the sample guide's temporary plot choices and return to its caller."""
    state = st.session_state
    state["tour_mode"] = None
    state.pop("_sample_restart", None)
    original = state.pop(GUIDE_RETURN_KEY, {})
    if not return_to_view:
        for key in (
            "main_nav",
            CORPUS_SUBTAB,
            CORPUS_GROUP_BY,
            CORPUS_MEASURE,
            DATA_WORKSPACE_KEY,
            DATA_INSPECTION_KEY,
            DATASET_EDITOR_OPEN_KEY,
        ):
            original.pop(key, None)
    _restore_guide_location(original)


def _dismiss_listener_script(
    selector: str | None,
    exit_keys: tuple[str, ...] = ("tour_sp_done", "tour_sp_close"),
) -> str:
    """Hide the guide immediately while a busy app handles its close button."""
    outline_clear = (
        f"{selector} {{ outline: none !important; animation: none !important; }}"
        if selector
        else ""
    )
    hide_css = (
        '.st-key-tour_card, [class*="st-key-guide_pill_"] { display: none !important; } '
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
    """Outline the control named in the current guide step."""
    if not selector:
        return ""
    return f"""
{selector} {{
    outline: 3px solid {accent};
    outline-offset: 3px;
    border-radius: 0.5rem;
    animation: tour-pulse 1.6s ease-in-out infinite;
}}
@media (prefers-reduced-motion: reduce) {{
    {selector} {{ animation: none; }}
}}
@keyframes tour-pulse {{
    0%, 100% {{ box-shadow: 0 0 0 0 color-mix(in srgb, {accent} 50%, transparent); }}
    50% {{ box-shadow: 0 0 14px 7px color-mix(in srgb, {accent} 25%, transparent); }}
}}
"""


_CARD_OVER_POPOVER_CSS = ".st-key-tour_card { z-index: 1000070; }"


def _all_popover_triggers() -> str:
    """One selector matching every popover trigger the tour knows how to open.

    Derived from the steps themselves rather than listed, so a step that starts
    opening a second popover is closed again by the steps after it for free.
    """
    declared = {step.popover for tutorial in TUTORIALS for step in tutorial.steps}
    return ", ".join(sorted(trigger for trigger in declared if trigger))


def _popover_script(trigger: str) -> str:
    """Open the popover this step points inside, and close the last step's.

    A closed Streamlit popover renders **no body**: the *narrow the pool* steps
    point at a container that only exists while the funnel is open, and with
    the funnel closed the spotlight would retry and then give up in silence —
    no highlight, no scroll, no error, and the card still advancing.

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

    Match the first visible element (inactive tab panels hold invisible duplicates), and scroll
    the nearest scrollable ancestor instead of calling `scrollIntoView` (which
    moves the document).

    Every step points at something in the page or on the nav bar, where
    ``findVisible()`` answers correctly on its own.

    The scroller's top is not all on screen: Streamlit's fixed header and the
    wizard's sticky bar (`_TOP_OVERLAYS`) cover it. Measured from the
    scroller's own top, the setup guide's part 2 would land under both — its
    title and first fields hidden, the card over what was left — so a target
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


# A replay that was already open can be paused, finished, or mid-trial. Its
# iframe might be reused, so mounting Animation with autoplay would not alone
# replay that reading. Use the player's own controls once, as it becomes ready.
_RESTART_SAMPLE_SCRIPT = """<script>
(() => {
    const parentDoc = window.parent.document;
    const stage = ".st-key-tour_grp_plot iframe[tabindex='0']";
    let attempts = 0;
    function replay() {
        const frame = parentDoc.querySelector(stage);
        const bar = frame?.contentDocument?.querySelector('[data-sps-transport]');
        const play = bar?.querySelector('[data-name="play"]');
        const restart = bar?.querySelector('[data-name="restart"]');
        if (play && restart) {
            restart.click();
            play.click();
        } else if (++attempts < 200) {
            window.setTimeout(replay, 150);
        }
    }
    replay();
})();
</script>"""


def _arm_tour() -> None:
    """Replay the selected bundled reading in its current interface mode."""
    if not sample_reading_available():
        return
    state = st.session_state
    if state.get("tutorial_active"):
        _restore_tutorial_return()
    view = state.get("main_nav", _VIEW_SCANPATH)
    if state.get("tour_mode") != "spotlight":
        original = {"main_nav": view}
        if view == _VIEW_CORPUS and CORPUS_SUBTAB in state:
            original.update(
                {
                    k: state[k]
                    for k in (CORPUS_SUBTAB, CORPUS_GROUP_BY, CORPUS_MEASURE)
                    if k in state
                }
            )
        elif view == _VIEW_DATA:
            original.update(_data_location())
        state[GUIDE_RETURN_KEY] = original
    # This guide follows one reader's fixation markers, including when the
    # original view was a heatmap or a replay showing only saccades.
    from .controls import write_through

    desired = {
        SINGLE_ANIMATE: True,
        SINGLE_COMPARE_TOGGLE: False,
        "global_show_fix": True,
        "global_anim_autoplay": True,
    }
    for key, value in desired.items():
        previous = state.get(key, key in {"global_show_fix", "global_anim_autoplay"})
        if previous != value:
            state[GUIDE_RETURN_KEY].setdefault(key, previous)
            if key == "global_anim_autoplay":
                write_through(key, value)
            else:
                state[key] = value
    if state.get("_sample_invitation"):
        _dismiss_invitation()
    state["main_nav"] = _VIEW_SCANPATH
    state["tour_seen"] = True
    state["tour_step"] = 0
    state["tour_mode"] = "spotlight"
    state["_sample_restart"] = True
    _set_guide_folded("tour", False)


def maybe_show_welcome_tour(active_view: str | None = None) -> None:
    """Offer the sample on a fresh demo visit, in the page beside the work."""
    from .persistence import session_was_restored

    state = st.session_state
    view = active_view or state.get("main_nav", _VIEW_SCANPATH)
    if state.pop("_write_invitation_cookie", False):
        embed_html_iframe(
            f'<script>window.parent.document.cookie = "{TOUR_OPTOUT_COOKIE}=1; '
            f'max-age={_TOUR_OPTOUT_MAX_AGE}; path=/; SameSite=Lax";</script>',
            height=0,
        )
    if state.get("tour_mode") == "wizard" and not state.get("_show_upload_wizard"):
        _exit_wizard_guide()
    if not state.get("tour_seen"):
        state["tour_seen"] = True
        if (
            view == _VIEW_SCANPATH
            and not st.context.is_embedded
            and not ui_mode.has_link_params(st.query_params)
            and not session_was_restored(state)
            and not state.get("_tour_dismissed")
            and st.context.cookies.get(TOUR_OPTOUT_COOKIE) != "1"
            and sample_reading_available()
        ):
            state["_sample_invitation"] = True
    if view != _VIEW_SCANPATH or not sample_reading_available():
        state.pop("_sample_invitation", None)
        if state.get("tour_mode") == "spotlight":
            _request_sample_exit(return_to_view=False)
            st.rerun(scope="app")
        return
    if state.get("tutorial_active"):
        state.pop("_sample_invitation", None)
    if not state.get("_sample_invitation"):
        return
    with st.container(
        key="sample_invitation",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
    ):
        st.markdown("A sample reading is open.", width="content")
        st.button(
            "Replay this reading", key="sample_invitation_replay", on_click=_arm_tour
        )
        st.button(
            "Import my data", key="sample_invitation_import", on_click=_use_own_data
        )
        st.button(
            "Dismiss",
            key="sample_invitation_dismiss",
            type="tertiary",
            on_click=_dismiss_invitation,
        )


@st.fragment
@guarded()
def render_spotlight_tour() -> None:
    """Two optional steps on the sample's plot and trial picker, shared by both modes."""
    state = st.session_state
    if state.get("tour_mode") != "spotlight":
        return
    step_index = min(state.get("tour_step", 0), len(_SPOTLIGHT_STEPS) - 1)
    step = _SPOTLIGHT_STEPS[step_index]
    progress = f"Step {step_index + 1} of {len(_SPOTLIGHT_STEPS)}"
    styles = _card_colors_css() + _GUIDE_MOVE_CSS
    if guide_folded("tour"):
        st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)
        _render_guide_pill(
            "tour",
            "Replay a sample reading",
            progress,
            "sample guide",
            on_close=_request_sample_exit,
        )
        return
    accent = st.get_option("theme.primaryColor") or "#1f77b4"
    highlight = _highlight_css(step["selector"], accent)
    st.markdown(
        f"<style>{_CARD_CSS}{styles}{highlight}</style>", unsafe_allow_html=True
    )
    with _guide_card():
        if st.button(
            f"✕ {spoken('Close the sample guide')}",
            key="tour_sp_close",
            wrap=True,
            help="Close the sample guide and return to your work.",
        ):
            _request_sample_exit()
            st.rerun(scope="app")
        _render_guide_fold_button("tour", "sample guide")
        st.markdown(f"## {step['title']}")
        st.markdown(step["body"])
        st.progress((step_index + 1) / len(_SPOTLIGHT_STEPS), text=progress)
        back, forward = st.columns(2)
        if step_index:
            back.button(
                "Back",
                key="tour_sp_back",
                on_click=state.update,
                args=({"tour_step": step_index - 1},),
            )
        if step_index + 1 < len(_SPOTLIGHT_STEPS):
            forward.button(
                "Next",
                key="tour_sp_next",
                type="primary",
                on_click=state.update,
                args=({"tour_step": step_index + 1},),
            )
        elif forward.button("Done", key="tour_sp_done", type="primary"):
            _request_sample_exit()
            st.rerun(scope="app")
        embed_html_iframe(_guide_drag_script("tour"), height=0)
        embed_html_iframe(_dismiss_listener_script(step["selector"]), height=0)
        embed_html_iframe(_scroll_into_view_script(step["selector"]), height=0)
        if state.pop("_sample_restart", False):
            embed_html_iframe(_RESTART_SAMPLE_SCRIPT, height=0)


# -----------------------------------------------------------------------------
# Use-case tutorials
# -----------------------------------------------------------------------------


def build_tutorial_context(words, fixations, combos) -> dict[str, object]:
    """The trial picker covers every table. Compare and Corpus require more."""
    from scanpath_studio.aggregation import available_measures

    return {
        "n_trials": len(combos) if combos is not None else 0,
        # Dataset B has independent filters and includes the packaged sources.
        # A single A reading with fixations can be compared across datasets.
        "has_fixations": fixations is not None and not fixations.empty,
        "has_word_measures": bool(
            words is not None
            and not words.empty
            and available_measures(words, None, per_word_only=True)
        ),
    }


def tutorial_availability(
    tutorial: TutorialDefinition,
    context: dict[str, object],
    *,
    needs_add_button: bool = False,
) -> tuple[bool, str]:
    """Whether this walkthrough can reach its controls in the current session."""
    if context.get("wizard_open"):
        return False, "Finish adding your dataset, or use Setup help in the form."
    if tutorial.id == "load_inspect":
        if needs_add_button and context.get("editor_open"):
            return False, (
                "In **Data Management → Current dataset**, save or cancel your open edit "
                "to use **Add dataset**."
            )
        return True, ""
    if tutorial.id == "compare_readings":
        return (
            bool(context.get("n_trials") and context.get("has_fixations")),
            "For the first reading, choose a dataset that contains fixations.",
        )
    if tutorial.id == "explore_corpus":
        return (
            bool(context.get("has_word_measures")),
            "To try this, map a reading measure in your Words table.",
        )
    return bool(context.get("n_trials")), "Open a dataset with at least one trial."


def filtered_reason(
    tutorial: TutorialDefinition, context: dict[str, object]
) -> str | None:
    """Say how to start a walkthrough that the trial filters rule out."""
    unfiltered = context.get("unfiltered")
    if not isinstance(unfiltered, dict) or tutorial_availability(tutorial, context)[0]:
        return None
    if not tutorial_availability(tutorial, unfiltered)[0]:
        return None
    if tutorial.id == "compare_readings":
        return "Widen the trial filters to include a reading with fixations."
    if tutorial.id == "explore_corpus":
        return "Widen the trial filters to include readings with a mapped word measure."
    return "Widen the trial filters to include at least one reading."


def _navigate_from_guide(action, *args) -> None:
    """Apply navigation in a widget callback, before any target widgets mount."""
    action(*args)
    st.session_state["_guide_navigation_requested"] = True


def _rerun_after_guide_navigation() -> None:
    # A fragment can disappear as a result of its own callback (Exit or Done).
    # Its parent must still redraw the view, even if the button is gone.
    if st.session_state.pop("_guide_navigation_requested", False):
        st.rerun(scope="app")


def _tutorial_progress() -> dict[str, int]:
    return st.session_state.setdefault("tutorial_progress", {})


def _tutorial_completed() -> dict[str, bool]:
    return st.session_state.setdefault("tutorial_completed", {})


def _start_use_case(tutorial_id: str) -> None:
    """Start on the first unfinished step and remember where the guide was opened."""
    tutorial = _TUTORIAL_BY_ID.get(tutorial_id)
    if (
        tutorial is None
        or not tutorial_availability(
            tutorial,
            st.session_state.get("_tutorial_context", {}),
            needs_add_button=True,
        )[0]
    ):
        return
    if st.session_state.get("tour_mode") == "spotlight":
        _exit_spotlight()
    if st.session_state.get("tutorial_active"):
        _restore_tutorial_return()
    st.session_state[GUIDE_RETURN_KEY] = {
        "main_nav": st.session_state.get("main_nav", _VIEW_SCANPATH),
        "single_subtab": _current_subtab(),
        **{
            k: st.session_state[k]
            for k in (CORPUS_SUBTAB, CORPUS_GROUP_BY, CORPUS_MEASURE)
            if k in st.session_state
        },
        **_data_location(),
        UI_MODE: ui_mode.current_mode(),
    }
    if tutorial.requires_full:
        st.session_state[UI_MODE] = ui_mode.ADVANCED
    progress = _tutorial_progress()
    completed = _tutorial_completed().pop(tutorial_id, False)
    if completed:
        progress[tutorial_id] = 0
    steps = steps_of(tutorial)
    step_index = max(0, min(progress.get(tutorial_id, 0), len(steps) - 1))
    progress[tutorial_id] = step_index
    _open_tutorial_surface(steps[step_index])
    st.session_state["tutorial_active"] = tutorial_id
    _set_guide_folded("tutorial", False)
    st.session_state["tour_mode"] = None


def _move_use_case(tutorial_id: str, delta: int) -> None:
    tutorial = _TUTORIAL_BY_ID[tutorial_id]
    current = _tutorial_progress().get(tutorial_id, 0)
    steps = steps_of(tutorial)
    target = max(0, min(len(steps) - 1, current + delta))
    _tutorial_progress()[tutorial_id] = target
    _open_tutorial_surface(steps[target])


def _finish_use_case(tutorial_id: str) -> None:
    _tutorial_completed()[tutorial_id] = True
    _restore_tutorial_return()


def _restore_tutorial_return() -> None:
    """Leave from any step, including a paused guide, with the original view and mode."""
    location = st.session_state.pop(GUIDE_RETURN_KEY, {})
    _restore_guide_location(location)
    st.session_state["tutorial_active"] = None


def change_tutorial_mode(mode: str) -> None:
    """Honor an explicit mode change while the viewer follows a task."""
    active = _TUTORIAL_BY_ID.get(st.session_state.get("tutorial_active"))
    if active is None:
        return
    if active.requires_full and mode == ui_mode.SIMPLE:
        _restore_tutorial_return()
    else:
        st.session_state[GUIDE_RETURN_KEY][UI_MODE] = mode


def _open_tutorial_surface(step: TutorialStep) -> None:
    st.session_state["main_nav"] = step.view
    if step.subtab is not None:
        st.session_state["single_subtab"] = step.subtab
    if step.corpus_subtab is not None:
        from .corpus_navigation import request_route

        request_route()
        st.session_state[CORPUS_SUBTAB] = step.corpus_subtab
    if step.corpus_group_by is not None:
        st.session_state["corpus_group_by"] = step.corpus_group_by
    if step.view == _VIEW_DATA:
        if step.dataset_editor:
            st.session_state[DATASET_EDITOR_OPEN_KEY] = True
        elif step.data_section == DATA_CURRENT or st.session_state.get(
            DATASET_EDITOR_OPEN_KEY
        ):
            from .app import open_dataset_panel

            open_dataset_panel("Overview")
            # Going Back to Add files can leave the editor. Its normal leave
            # prompt keeps an unfinished edit on screen until the user decides.
            if st.session_state.get(DATASET_EDITOR_OPEN_KEY):
                return
        st.session_state[DATA_WORKSPACE_REQUEST] = step.data_section


_KNOWN_VIEWS = (_VIEW_SCANPATH, _VIEW_CORPUS, _VIEW_DATA)


def _tutorial_surface_is_open(step: TutorialStep) -> bool:
    """Is the view (and subtab) this step points at the one on screen?

    Each known view is compared as itself; only an unknown ``main_nav`` value
    counts as Scanpath. Folding the Data page into Scanpath would report a
    ``view=_VIEW_DATA`` step "not open" *while the user stands on the Data
    page*, offering to open the panel they are looking at and withholding its
    spotlight.
    """
    current_view = st.session_state.get("main_nav", _VIEW_SCANPATH)
    if current_view not in _KNOWN_VIEWS:
        current_view = _VIEW_SCANPATH
    if current_view != step.view:
        return False
    if step.view == _VIEW_DATA and (
        st.session_state.get(DATA_WORKSPACE_KEY, DATA_CURRENT) != step.data_section
        or (
            step.data_section == DATA_CURRENT
            and not step.dataset_editor
            and st.session_state.get(DATA_INSPECTION_KEY, "Overview") != "Overview"
        )
    ):
        return False
    # On the Data page, "which screen" is part of the answer — an
    # editor step is not open while the overview is showing, and vice versa.
    if (
        step.view == _VIEW_DATA
        and step.data_section == DATA_CURRENT
        and bool(st.session_state.get(DATASET_EDITOR_OPEN_KEY))
        != bool(step.dataset_editor)
    ):
        return False
    if (
        step.corpus_subtab is not None
        and st.session_state.get("corpus_subtab", "Overview") != step.corpus_subtab
    ):
        return False
    if (
        step.corpus_group_by is not None
        and st.session_state.get("corpus_group_by") != step.corpus_group_by
    ):
        return False
    return step.subtab is None or _current_subtab() == step.subtab


def _current_subtab() -> str:
    """The selected per-trial subtab, defaulting to the mode's first one."""
    first = SUBTAB_EXPORT if ui_mode.is_simple() else SUBTAB_ANNOTATIONS
    return st.session_state.get("single_subtab", first)


def _arm_tutorial_library() -> None:
    """Request the tutorial chooser. Called by the ❓ Help nav entry
    (``menu._arm_help_action``)."""
    st.session_state["_tutorial_library_requested"] = True


def maybe_show_tutorial_library() -> None:
    """Open Task guides after this run has resolved its dataset and filters."""
    if st.session_state.pop("_tutorial_library_requested", False):
        _tutorial_library_dialog()


def stash_tutorial_context(context: dict[str, object]) -> None:
    """Save the small availability snapshot the guide fragments read."""
    context["editor_open"] = bool(st.session_state.get(DATASET_EDITOR_OPEN_KEY))
    st.session_state["_tutorial_context"] = context


@st.dialog(f"{ICONS['tutorials']} Task guides", width="medium")
@guarded()
def _tutorial_library_dialog() -> None:
    """Each row can be read locally, even when its walkthrough is unavailable."""
    _rerun_after_guide_navigation()
    context = st.session_state.get("_tutorial_context", {})
    with st.expander("Replay a sample reading"):
        st.markdown(
            "1. In **Scanpath View**, choose **Bundled demo**.\n"
            "2. Pick a reading in **Select trial** and turn on **Animation**.\n"
            "3. Press **Play** to watch the reading. Use **Pause** and **Next fixation** to inspect one fixation at a time. "
            "Turn off **Animation** to return to your figure."
        )
        if sample_reading_available():
            st.button(
                "Show me in the app",
                key="tutorial_start_welcome",
                on_click=_navigate_from_guide,
                args=(_arm_tour,),
            )
        else:
            st.caption(
                "In **Scanpath View**, open **Bundled demo** and select a trial with fixations. "
                "For a trial with several screens, choose a screen with fixations."
            )
        st.markdown(
            f"[Read the replay guide online ↗]({DOCS_URL}install/#replay-a-sample-reading)"
        )
    for tutorial in TUTORIALS:
        with st.expander(tutorial.title):
            if tutorial.requires_full:
                st.caption("Uses Full mode.")
            st.markdown(
                "\n".join(
                    f"{i}. {step.body}" for i, step in enumerate(steps_of(tutorial), 1)
                )
            )
            available, reason = tutorial_availability(
                tutorial, context, needs_add_button=True
            )
            if available:
                completed = bool(_tutorial_completed().get(tutorial.id))
                paused = not completed and tutorial.id in _tutorial_progress()
                if tutorial.requires_full and ui_mode.is_simple():
                    label = "Resume in Full" if paused else "Open in Full"
                elif paused:
                    label = "Resume walkthrough"
                elif completed:
                    label = "Start again"
                else:
                    label = "Show me in the app"
                st.button(
                    label,
                    key=f"tutorial_start_{tutorial.id}",
                    on_click=_navigate_from_guide,
                    args=(_start_use_case, tutorial.id),
                )
            else:
                st.caption(filtered_reason(tutorial, context) or reason)
            st.markdown(f"[Read the guide online ↗]({tutorial.docs_url})")


@st.fragment
@guarded()
def render_use_case_tutorial() -> None:
    """Render the active guide and return to its launching view on Exit or Done."""
    _rerun_after_guide_navigation()
    tutorial_id = st.session_state.get("tutorial_active")
    tutorial = _TUTORIAL_BY_ID.get(tutorial_id)
    if tutorial is None:
        return
    context = st.session_state.get("_tutorial_context") or {}
    steps = steps_of(tutorial)
    step_index = max(0, min(_tutorial_progress().get(tutorial.id, 0), len(steps) - 1))
    available, reason = tutorial_availability(
        tutorial, context, needs_add_button=step_index == 0
    )
    if not available:
        st.info(
            f"**{tutorial.title}** is paused. {filtered_reason(tutorial, context) or reason}"
        )
        st.button(
            "Exit guide",
            key="tutorial_exit",
            on_click=_navigate_from_guide,
            args=(_restore_tutorial_return,),
        )
        return
    step = steps[step_index]
    progress_text = f"Step {step_index + 1} of {len(steps)}"
    if guide_folded("tutorial"):
        st.markdown(
            "<style>" + _card_colors_css() + _GUIDE_MOVE_CSS + "</style>",
            unsafe_allow_html=True,
        )
        _render_guide_pill(
            "tutorial",
            tutorial.title,
            progress_text,
            "guide",
            on_close=_restore_tutorial_return,
        )
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
    with _guide_card():
        st.markdown(f"## {tutorial.title}")
        _render_guide_fold_button("tutorial", "tutorial")
        st.markdown(f"**{step.title}**")
        st.markdown(step.body)
        if not surface_open:
            st.button(
                "Open this panel",
                key="tutorial_open_surface",
                type="primary",
                width="stretch",
                on_click=_navigate_from_guide,
                args=(_open_tutorial_surface, step),
            )
        st.progress(
            (step_index + 1) / len(steps),
            text=progress_text,
        )
        st.markdown(f"[Read the guide online ↗]({tutorial.docs_url})")
        back_col, exit_col, next_col = st.columns(3)
        back_col.button(
            "Back",
            key="tutorial_back",
            disabled=step_index == 0,
            width="stretch",
            on_click=_navigate_from_guide,
            args=(_move_use_case, tutorial.id, -1),
        )
        exit_col.button(
            "Exit",
            key="tutorial_exit",
            width="stretch",
            on_click=_navigate_from_guide,
            args=(_restore_tutorial_return,),
        )
        if step_index < len(steps) - 1:
            next_col.button(
                "Next",
                key="tutorial_next",
                type="primary",
                width="stretch",
                on_click=_navigate_from_guide,
                args=(_move_use_case, tutorial.id, 1),
            )
        else:
            next_col.button(
                "Done",
                key="tutorial_done",
                type="primary",
                width="stretch",
                on_click=_navigate_from_guide,
                args=(_finish_use_case, tutorial.id),
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
                        el.scrollIntoView({{
                            behavior: doc.defaultView.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
                            block: "center"
                        }});
                    }})();
                }})();
                </script>""",
                height=0,
            )


# -----------------------------------------------------------------------------
# On-demand guide to the Add dataset wizard
# -----------------------------------------------------------------------------

WIZARD_HELP_KEY = "wizard_setup_help"


def _focus_setup_guide_script() -> str:
    """Focus the guide heading once its launching popover has closed."""
    return """<script>
    (() => {
        const doc = window.parent.document;
        let attempts = 0;
        function focusGuide() {
            const heading = doc.querySelector(".st-key-tour_card h2");
            const launch = doc.querySelector(".st-key-wizard_guide_replay button");
            if (heading && !launch?.checkVisibility()) {
                heading.tabIndex = -1;
                heading.focus({preventScroll: true});
            } else if (++attempts < 120) {
                window.requestAnimationFrame(focusGuide);
            }
        }
        window.requestAnimationFrame(focusGuide);
    })();
    </script>"""


# (title, markdown body) per step — an overview, one per part of the wizard in
# order, then the closing Save card. Each card names the wizard part it talks
# about (``step_id``) and a CSS selector to highlight + scroll to: every part's
# container is keyed by `wizard_shell.part_key`, which gives it a
# `.st-key-wiz_part_<id>` selector; finer targets reuse existing widget keys.
_WIZARD_GUIDE_STEPS = [
    {
        "title": f"{ICONS['datasets']} Set up your dataset",
        "body": (
            "You need at least one table of fixations, words or raw gaze. "
            "Measurements from the recording setup help place the text and gaze on screen."
        ),
        "selector": "",
        "step_id": None,
    },
    {
        "title": "1 · Name & description",
        "body": (
            "Give the dataset a **Name**. It shows on the "
            f"{ICONS['view_data']} **Data Management** page and in the dataset "
            "picker. A **Description** is optional."
        ),
        "selector": ".st-key-wiz_part_name",
        "step_id": "name",
    },
    {
        "title": "2 · Data tables & column mapping",
        "body": (
            "Upload a table and check which column supplies each field. "
            "Use **Extra fields to keep** for other columns you need. "
            "Anything missing is listed above **Add dataset**."
        ),
        "selector": ".st-key-wiz_part_data",
        "step_id": "data",
    },
    {
        "title": "3 · Recording setup",
        "body": (
            "Choose *I know it* for values recorded during the experiment, "
            "such as the screen resolution or font size. Check any estimates "
            "and defaults before saving."
        ),
        "selector": ".st-key-wiz_part_setup",
        "step_id": "setup",
    },
    # The add screen's optional fourth part, drawn only on a local
    # install; `_wizard_guide_steps` leaves this card out wherever it is not.
    {
        "title": "4 · Stimulus images",
        "body": (
            "Optionally, choose a folder of stimulus screenshots to display "
            "behind the scanpath. Use a filename pattern such as `{text_id}.png` "
            "to match each image to a text or trial."
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
            "Click **Add dataset**, then **Open in Scanpath view** or "
            "**Add another**. Use **Download setup file** to save the mapping "
            "and recording setup. When adding similar data, choose the saved "
            "file or this dataset under *Start from*."
        ),
        "selector": ".st-key-wizard_footer_row",
        "step_id": None,
    },
]


#: The setup guide is a floating card over the wizard, dragged by its title to
#: wherever it covers nothing and folded to a small tab, like the welcome
#: tour's and the tutorials' cards. The page keeps room at its foot, so
#: whatever the card covers at the bottom can still be scrolled clear of it.
_WIZARD_GUIDE_PAGE_CSS = """
[data-testid="stMainBlockContainer"] { padding-bottom: 16rem !important; }
@media (max-width: 44rem) {
    .st-key-tour_card {
        position: relative !important; inset: auto !important; transform: none !important;
        width: 100% !important; max-width: 100% !important; max-height: 45dvh; overflow-y: auto;
    }
}
"""


def _wizard_guide_steps() -> list[dict]:
    """The guide's cards for the add screen as it is drawn here: the
    *Stimulus images* card only where that part is (a local install)."""
    from .app import local_filesystem_enabled

    local = local_filesystem_enabled()
    return [s for s in _WIZARD_GUIDE_STEPS if local or not s.get("local_only")]


def _wizard_guide_go(step_idx: int) -> None:
    """Move the guide to ``step_idx``, clamped to its cards."""
    steps = _wizard_guide_steps()
    st.session_state["wizard_guide_step"] = max(0, min(step_idx, len(steps) - 1))


def _wizard_guide_back() -> None:
    _wizard_guide_go(st.session_state.get("wizard_guide_step", 0) - 1)


def _wizard_guide_next() -> None:
    _wizard_guide_go(st.session_state.get("wizard_guide_step", 0) + 1)


def _exit_wizard_guide() -> None:
    st.session_state["tour_mode"] = None


def _wizard_guide_progress(step_idx: int, step: dict) -> str:
    """Where the guide is, counted in the screen's own parts ("2 · Data tables &
    column mapping" is part 2), not in cards: neither the overview card nor the
    closing Save card is a part, and a card count under a "2 ·" heading would
    contradict the parts the screen numbers."""
    n_parts = sum(1 for s in _wizard_guide_steps() if s["step_id"])
    if step["step_id"]:
        return f"Part {step_idx} of {n_parts}"
    if step_idx:
        return "Last step · save"
    return f"Overview · {n_parts} parts"


def _wizard_guide_buttons(back_col, exit_col, next_col, step_idx: int, n: int) -> None:
    """Navigation for the optional setup guide."""
    back_col.button(
        "← Back",
        key="wizard_sp_back",
        width="stretch",
        disabled=step_idx == 0,
        on_click=_wizard_guide_back,
    )
    if step_idx < n - 1:
        exit_col.button(
            "Close guide",
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
            "Done",
            key="wizard_sp_done",
            width="stretch",
            type="primary",
            on_click=_exit_wizard_guide,
        )


@st.fragment
@guarded()
def render_spotlight_wizard_guide() -> None:
    """Show the requested setup step alongside the editable form."""
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
        _render_guide_pill(
            "wizard",
            "Setup guide",
            progress_text,
            "setup guide",
            on_close=_exit_wizard_guide,
        )
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

    with _guide_card():
        # <h2> for a valid heading outline; sized down via `.st-key-tour_card h2`.
        st.markdown(f"## {step['title']}")
        _render_guide_fold_button("wizard", "setup guide")
        if st.session_state.pop("_focus_setup_guide", False):
            embed_html_iframe(_focus_setup_guide_script(), height=0)
        st.markdown(step["body"])
        st.progress((step_idx + 1) / n, text=progress_text)
        back_col, exit_col, next_col = st.columns(3)
        _wizard_guide_buttons(back_col, exit_col, next_col, step_idx, n)
    embed_html_iframe(_guide_drag_script("wizard"), height=0)
    # A busy upload can finish after the user closes the guide.
    embed_html_iframe(
        _dismiss_listener_script(None, exit_keys=("wizard_sp_exit", "wizard_sp_done")),
        height=0,
    )


def _arm_wizard_guide() -> None:
    """Open the optional setup guide at its first step."""
    st.session_state[WIZARD_HELP_KEY] = False
    st.session_state["_focus_setup_guide"] = True
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
