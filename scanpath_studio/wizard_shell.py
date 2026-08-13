"""The Add-dataset wizard's shell: step registry, status, accordion, progress
and navigation (DATA-22).

Knows nothing about columns or dataframes — ``wizard.py`` keeps the step bodies
and finalize. What lives here is the *chrome*: which steps exist, what each one's
status badge is, which one is open, and the buttons that move between them.

**The one rule that makes the accordion work.** A step's open flag
(``wiz_open_<id>``) is written *only* by `seed_open_step`, `go_to_step`,
`continue_button`, the progress chips, and the guide. Nothing inside a step body
may touch it. The old wizard recomputed ``expanded=`` from whether the step was
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

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Optional

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


STEPS: tuple[WizardStep, ...] = (
    WizardStep("data", 1, "Your data", "The tables you exported", True),
    WizardStep(
        "identity", 2, "Trials & readers", "Which columns identify a trial", True
    ),
    WizardStep(
        "geometry",
        3,
        "Fixations & text",
        "Where the eyes landed, where the words are",
        True,
    ),
    WizardStep(
        "setup", 4, "Recording setup", "The screen and font it was recorded on", True
    ),
    # DATA-20: the participant table's main home. It was a Data-page section
    # only, which every source can reach — but a first-time uploader never sees
    # it during setup, and "what do you know about your readers" is a setup
    # question. Optional, and after `identity`, which settles the reader id it
    # joins on.
    WizardStep("readers", 5, "About your readers", "Optional participant table", False),
    WizardStep("fields", 6, "Extra fields", "What else to carry along", False),
    WizardStep("review", 7, "Name & add", "Check it over and add the dataset", True),
)

STEPS_BY_ID: dict[str, WizardStep] = {s.id: s for s in STEPS}


def open_key(step_id: str) -> str:
    """Session key holding whether ``step_id``'s expander is open."""
    return f"{OPEN_KEY_PREFIX}{step_id}"


def badge(status: StepStatus) -> str:
    """The emoji shown against a step with this status."""
    return _BADGES.get(status, _BADGES[StepStatus.TODO])


def first_incomplete(statuses: Mapping[str, StepStatus]) -> Optional[str]:
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


def continue_button(host, step: WizardStep, *, label: str = "Continue →") -> None:
    """A step-footer button that closes this step and opens the next one."""
    idx = next((i for i, s in enumerate(STEPS) if s.id == step.id), None)
    if idx is None or idx + 1 >= len(STEPS):
        return
    nxt = STEPS[idx + 1]
    host.button(
        label,
        key=f"wiz_continue_{step.id}",
        on_click=go_to_step,
        args=(nxt.id,),
        help=f"Go to {nxt.number}. {nxt.title}",
    )


def render_progress(host, statuses: Mapping[str, StepStatus]) -> None:
    """The header: a completion bar plus one clickable chip per step.

    The chips are the navigation — a user who realises at step 5 that the trial
    id is wrong should be one click from step 2, not scrolling for it.
    """
    done_n = sum(
        1
        for s in STEPS
        if statuses.get(s.id, StepStatus.TODO) in (StepStatus.DONE, StepStatus.OPTIONAL)
    )
    host.progress(
        done_n / len(STEPS), text=f"Setup progress — {done_n} / {len(STEPS)} steps"
    )
    cols = host.columns(len(STEPS))
    for col, step in zip(cols, STEPS):
        status = statuses.get(step.id, StepStatus.TODO)
        col.button(
            f"{badge(status)} {step.number}. {step.title}",
            key=f"wiz_chip_{step.id}",
            on_click=go_to_step,
            args=(step.id,),
            help=step.caption,
            width="stretch",
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
