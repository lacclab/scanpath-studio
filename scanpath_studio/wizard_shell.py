"""The Add-dataset wizard's shell: step registry, status, accordion, progress
and navigation (DATA-22).

Knows nothing about columns or dataframes — ``wizard.py`` keeps the step bodies
and finalize. What lives here is the *chrome*: which steps exist, what each one's
status badge is, which one is open, and the buttons that move between them.

**The one rule that makes the accordion work.** A step's open flag
(``wiz_open_<id>``) is written *only* by `seed_open_step`, `go_to_step`,
the guide, and `seed_open_step`. Nothing inside a step body may touch it. The old wizard recomputed ``expanded=`` from whether the step was
"done", so the first pick in a step flipped ``done`` and the expander collapsed
under the user's cursor mid-edit (DATA-19 patched that with a one-shot marker
that survived exactly one rerun; this replaces the mechanism rather than
patching it again). Here the flag is a keyed-expander widget value: the user's
own click owns it, and code only moves it on an explicit navigation.

**A keyed expander's label and icon must be CONSTANT.** Changing either remounts
the widget at its default — i.e. collapsed — on the very next run, no matter what
its key holds. That is not a theory: an upload flips step 1 from *action* to
*done*, and while the status badge was passed as ``icon=`` the step slammed shut
the instant the file finished uploading, which is exactly the DATA-19 symptom
this design set out to remove, arriving through a different door. The badge
therefore lives on the progress chips (`render_progress`) and nowhere else; the
expander header carries only the fixed number + title. Reproduced and pinned by
``tests/test_wizard_helpers.py::TestWizardAccordion::
test_a_changing_header_would_collapse_a_keyed_expander``.

**Step bodies must never be gated on the expander being open.** Streamlit drops
a widget's key from session state at the end of any run in which the widget did
not render, and ``controls.column_mapping_ui`` builds its ``col_map_*`` widgets
without ``persist_state`` — so a collapsed-and-therefore-unrendered step would
silently discard its mapping. Collapsed-but-rendered is correct; see the comment
at the `step_panel` call sites in ``wizard.py``.
"""

from __future__ import annotations

import html
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

import streamlit as st

#: Prefix for the accordion's per-step open flags. Deliberately *not* the
#: ``col_map_`` prefix — ``tabs._collect_column_mapping`` sweeps that whole
#: namespace into the saved config, and a UI open/closed flag is not mapping.
OPEN_KEY_PREFIX = "wiz_open_"


class StepStatus(Enum):
    """What the badge beside a step says."""

    DONE = "done"
    """Satisfied — nothing more is required here."""
    ACTION = "action"
    """Required, started, and currently blocked on something specific."""
    TODO = "todo"
    """Required and not started."""
    OPTIONAL = "optional"
    """Optional and untouched."""


_BADGES: dict[StepStatus, str] = {
    StepStatus.DONE: "✅",
    StepStatus.ACTION: "⚠️",
    StepStatus.TODO: "⬜",
    StepStatus.OPTIONAL: "➖",
}


@dataclass(frozen=True)
class WizardStep:
    """One accordion step. ``number`` is the 1-based label the user reads."""

    id: str
    number: int
    title: str
    caption: str
    required: bool


#: UX-53 folded the original seven steps into two, then UX-113 unfolded them
#: to five — flat and same-size, not the old per-step expanders. UX-114 folded
#: "Keep extra fields" back into "Map data fields" (each table's own keep
#: picker now sits directly under that table's own mapping — a cross-table
#: pick was a second, confusing decision), leaving four. UX-129 folded "Map
#: data fields" itself into "Upload data tables" — UX-122/127 had already
#: moved every table's uploader into its own mapping row, so by this point the
#: two stages held the same content split across two headings for no reason;
#: a second numbered heading with nothing under it that the one above didn't
#: already cover just read as a bare divider. `_part("data")` alone now
#: covers both, leaving three. Upload always precedes mapping (there is
#: nothing to map until a file is read), so the three are labelled but not
#: navigable: no chips, no accordion, no open state. `part()` renders each as
#: a one-line numbered headline. The dataset name is its own numbered stage
#: rather than an unlabeled header above everything, and Recording setup is
#: its own numbered stage rather than a sub-heading nested inside "Upload data
#: tables" — all three read as one flat sequence.
STEPS: tuple[WizardStep, ...] = (
    WizardStep("name", 1, "Dataset name", "What to call it", True),
    WizardStep("data", 2, "Upload data tables", "The tables you exported", True),
    WizardStep("setup", 3, "Recording setup", "The screen it was recorded on", True),
)

STEPS_BY_ID: dict[str, WizardStep] = {s.id: s for s in STEPS}


#: UX-135 — the ✏️ Edit dataset screen's parts, in page order.
#:
#: The ask was that the two screens read the same ("make it be as similar as
#: possible to add dataset page"), so the editor uses this module's `part()`
#: headline rather than the `st.divider()` + `st.subheader()` + `st.caption()`
#: stack it grew section by section. The first two ids line up one-for-one with
#: `STEPS` — an existing dataset's tables and mapping are the same question as
#: uploading them, and its recording setup is the *same renderer* — and the rest
#: are the questions that only have an answer once the dataset exists.
#:
#: The ids are prefixed ``edit_`` because `part_key` makes them container keys
#: and a key may be used once per run. The editor's *slots* are reserved on
#: every run (the screen is hidden by CSS, not skipped — see the slot comments
#: in `app.main`), and `edit_stimulus` is drawn on every run outside the view
#: guard, so an unprefixed id could meet the wizard's own while the add screen
#: is open.
#:
#: ``number`` here is a *placeholder*: two of the five are conditional (stimulus
#: images need a local filesystem, preprocessing is behind PRE-22's flag), and a
#: screen numbered 1 · 2 · 3 · 5 reads as a missing section rather than as a
#: hidden one. `numbered()` renumbers whatever is actually on screen.
EDITOR_STEPS: tuple[WizardStep, ...] = (
    WizardStep(
        "edit_data",
        1,
        "Data tables & column mapping",
        "How each source column maps onto the app's canonical fields — the one "
        "thing that decides what every measure downstream is computed from. Any "
        "metadata tables attached to the dataset are here too.",
        True,
    ),
    WizardStep(
        "edit_setup",
        2,
        "Recording setup",
        "Screen, physical geometry and reading-text setup for this dataset.",
        True,
    ),
    WizardStep(
        "edit_identity",
        3,
        "Trial identity",
        "Whether the Trial ID above actually identifies one reading — checked "
        "on the whole dataset, before any filtering.",
        False,
    ),
    WizardStep(
        "edit_stimulus",
        4,
        "Stimulus images",
        "Attach screenshots of the stimulus from a local folder, without adding "
        "an image_path column to your data.",
        False,
    ),
    WizardStep(
        "edit_preproc",
        5,
        "Preprocessing",
        "Optional soft exclusion and merging of short fixations, applied to "
        "every view. Off by default; original rows remain available.",
        False,
    ),
)

EDITOR_STEPS_BY_ID: dict[str, WizardStep] = {s.id: s for s in EDITOR_STEPS}


def numbered(
    steps: Iterable[WizardStep], shown: Iterable[str]
) -> dict[str, WizardStep]:
    """``steps`` renumbered 1..n over the subset named in ``shown``.

    Returns a mapping keyed by step id, so a caller can draw a part without
    knowing where in the sequence it landed. Ids in ``shown`` that no step
    declares are ignored; steps not in ``shown`` are absent from the result,
    which is what a caller should check rather than tracking the condition
    twice.
    """
    keep = set(shown)
    out: dict[str, WizardStep] = {}
    for step in steps:
        if step.id not in keep:
            continue
        out[step.id] = WizardStep(
            step.id, len(out) + 1, step.title, step.caption, step.required
        )
    return out


def open_key(step_id: str) -> str:
    """Session key holding whether ``step_id``'s expander is open."""
    return f"{OPEN_KEY_PREFIX}{step_id}"


def part_key(step_id: str) -> str:
    """Container key for a part, and so its `.st-key-…` CSS/tour selector."""
    return f"wiz_part_{step_id}"


def part(
    host,
    step: WizardStep,
    *,
    status: StepStatus | None = None,
    trailing=None,
    note: str = "",
):
    """One linear part of the wizard: a minimal headline, then its body.

    UX-53 r8. The parts run in a fixed order — there is nothing to map before a
    file is read — so this is a *label*, not navigation: no expander, no chips,
    no open state, and therefore none of the DATA-19 / DATA-22 collapse
    machinery. It costs one line, which is the point; the previous shapes spent
    a header and a click each on a sequence with no choices in it.

    ``trailing`` (UX-113), when given, is called with a column beside the
    title — e.g. stage 2's "↩️ Restore a saved setup" popover trigger — so it
    reads as part of the title line instead of as the first thing in the body.
    Only the title line splits; the returned body container stays full width.

    ``note`` (UX-135) hangs the part's explanation off the title as the same
    hover tooltip the rest of the wizard's prose uses, instead of a `st.caption`
    line under it. The add screen's own three titles say everything they need to
    ("Dataset name"), so only the ✏️ Edit dataset screen passes one — its parts
    carry judgements a title cannot ("does the Trial ID identify one reading?").
    """
    box = host.container(key=part_key(step.id))
    mark = f"{badge(status)} " if status else ""
    title = html.escape(step.title)
    if note:
        title = (
            f'<span class="sps-fhelp" data-tip="{html.escape(note, quote=True)}">'
            f"{title}</span>"
        )
    title_html = (
        f'<div class="sps-wiz-part"><span class="sps-wiz-part-n">{step.number}</span>'
        f"{mark}{title}</div>"
    )
    if trailing is not None:
        title_col, trailing_col = box.columns(
            [0.6, 0.4], gap="small", vertical_alignment="center"
        )
        title_col.markdown(title_html, unsafe_allow_html=True)
        trailing(trailing_col)
    else:
        box.markdown(title_html, unsafe_allow_html=True)
    return box.container()


def badge(status: StepStatus) -> str:
    """The emoji shown against a step with this status."""
    return _BADGES.get(status, _BADGES[StepStatus.TODO])


def first_incomplete(statuses: Mapping[str, StepStatus]) -> str | None:
    """Id of the first step that still wants attention, or ``None`` when the
    wizard is fully answered.

    "Wants attention" excludes ``OPTIONAL``: an untouched optional step must not
    stop the accordion advancing past it, or *Extra fields* would grab focus
    ahead of *Name & add* on every fresh upload.
    """
    for step in STEPS:
        status = statuses.get(step.id, StepStatus.TODO)
        if status in (StepStatus.TODO, StepStatus.ACTION):
            return step.id
    return None


def go_to_step(step_id: str) -> None:
    """Open exactly one step and close the others.

    Safe as an ``on_click``/``on_change`` callback: callbacks run as part of the
    click event, *before* the script re-executes, so these writes land before the
    expander widgets instantiate and Streamlit never sees a key being set for an
    already-created widget.
    """
    for step in STEPS:
        st.session_state[open_key(step.id)] = step.id == step_id


def seed_open_step(statuses: Mapping[str, StepStatus]) -> None:
    """On first entry to the wizard, open the first step that needs attention.

    Runs once per wizard entry (guarded by ``_wizard_accordion_seeded``) — after
    that the accordion is the user's to drive, and re-seeding on later runs would
    be exactly the auto-advance-under-the-cursor behaviour this design removes.
    """
    if st.session_state.get("_wizard_accordion_seeded"):
        return
    st.session_state["_wizard_accordion_seeded"] = True
    go_to_step(first_incomplete(statuses) or STEPS[0].id)


def reset_accordion() -> None:
    """Forget the accordion state so the next wizard entry re-seeds.

    Called by ``wizard._reset_wizard_widgets`` when *Add data* starts a fresh
    dataset; without it the second dataset would open on whichever step the
    first one was left on.
    """
    st.session_state.pop("_wizard_accordion_seeded", None)
    for step in STEPS:
        st.session_state.pop(open_key(step.id), None)


def step_panel(host, step: WizardStep, status: StepStatus, *, active: bool):
    """The container a step's body renders into.

    ``active`` (the guided wizard) gives a keyed expander; ``on_change="rerun"``
    is what makes Streamlit track its open state at all — with ``key=`` alone the
    frontend keeps one open state while session state keeps another, so the
    user's manual collapse is never recorded and the next rerun re-opens it.

    ``active=False`` is the collapsed *Data & mapping* review panel, which is
    itself an expander: Streamlit forbids expander-in-expander, so the step
    degrades to a bold heading and renders inline into ``host``. That preserves
    today's review-panel behaviour and the ``wizard_reconfigure`` assertion in
    ``tests/test_apptest.py``.

    ``status`` is deliberately **not** rendered into the active header. A keyed
    expander whose label or icon changes remounts collapsed on the next run, so a
    status badge there would slam the step shut the moment an upload or a mapping
    pick completed it — see the module docstring. The badges live on the progress
    chips directly above, which are buttons and re-render harmlessly.
    """
    if not active:
        host.markdown(f"**{badge(status)} {step.number}. {step.title}**")
        return host
    return host.expander(
        f"{step.number}. {step.title}",
        key=open_key(step.id),
        on_change="rerun",
    )


def blockers(
    statuses: Mapping[str, StepStatus], reasons: Mapping[str, Iterable[str]]
) -> list[tuple[WizardStep, list[str]]]:
    """Steps still blocking *Add dataset*, each with its reasons.

    Feeds the review step's "what's left" list, where every entry gets a
    *Go to step N* button — a blocker the user cannot navigate to is just a
    complaint.
    """
    out: list[tuple[WizardStep, list[str]]] = []
    for step in STEPS:
        if statuses.get(step.id, StepStatus.TODO) in (
            StepStatus.TODO,
            StepStatus.ACTION,
        ):
            out.append((step, list(reasons.get(step.id, []))))
    return out
