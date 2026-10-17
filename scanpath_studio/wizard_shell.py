"""The Add-dataset wizard's shell: part registries and status badges.

Knows nothing about columns or dataframes — ``wizard.py`` keeps the part bodies
and finalize. What lives here is the *chrome*:

- `STEPS` — the add screen's linear parts (name → data → setup, then the
  optional stimulus images on a local install), drawn by `part()` as numbered
  one-line headlines. They are labels, not navigation: there
  is nothing to map until a file is read, so no chips, no accordion, no open state.
- `EDITOR_STEPS` + `numbered()` — the ✏️ Edit dataset screen's parts, renumbered
  over the ones that actually render.
- `step_panel` — a part's heading inside the collapsed *Data & mapping* review
  panel.
"""

from __future__ import annotations

import html
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from .constants import ICONS, icon_html
from .fields import tooltip


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


#: Status → its `constants.ICONS` concept. A concept rather than the
#: shortcode, because the badge is drawn two ways: as markdown on the review
#: panel (:func:`badge`) and inside the part title's raw HTML (:func:`part`),
#: where a shortcode is inert.
_BADGES: dict[StepStatus, str] = {
    StepStatus.DONE: "step_done",
    StepStatus.ACTION: "step_action",
    StepStatus.TODO: "step_todo",
    StepStatus.OPTIONAL: "step_optional",
}


@dataclass(frozen=True)
class WizardStep:
    """One part of the wizard. ``number`` is the 1-based label the user reads."""

    id: str
    number: int
    title: str
    caption: str
    required: bool


#: The add screen's parts, in page order. Every table's uploader sits in its
#: own mapping row, with that table's *Extra fields to keep* picker directly
#: under its mapping, so `_part("data")` covers uploading and mapping alike.
#: Upload always precedes mapping (there is nothing to map until a file is
#: read), so the parts are labelled but not navigable: no chips, no accordion,
#: no open state. `part()` renders each as a one-line numbered headline. The
#: dataset name is its own numbered part rather than an unlabeled header above
#: everything, and Recording setup is its own rather than a sub-heading nested
#: inside "Data tables & column mapping" — they read as one flat sequence.
#:
#: The fourth, *Stimulus images* (a folder of screenshots saved with the
#: dataset), is optional and last. Only a local install draws it (a path on the
#: server means nothing to a visitor), and being last it renumbers nothing when
#: it is left out.
STEPS: tuple[WizardStep, ...] = (
    WizardStep("name", 1, "Name & description", "What to call it", True),
    WizardStep(
        "data", 2, "Data tables & column mapping", "The tables you exported", True
    ),
    WizardStep("setup", 3, "Recording setup", "The screen it was recorded on", True),
    WizardStep(
        "images", 4, "Stimulus images", "Screenshots of what was on screen", False
    ),
)

STEPS_BY_ID: dict[str, WizardStep] = {s.id: s for s in STEPS}


#: The ✏️ Edit dataset screen's parts, in page order.
#:
#: The two screens read the same, so the editor draws this module's `part()`
#: headline too. The first four ids line up one-for-one with `STEPS` — naming
#: it, its tables and mapping (the same question as uploading them), its
#: recording setup (the *same renderer*) and its stimulus images (the same
#: fields). The rest are the questions that only have an answer once the
#: dataset exists.
#:
#: The ids are prefixed ``edit_`` because `part_key` makes them container keys
#: and a key may be used once per run. The editor's *slots* are reserved on
#: every run (the screen is hidden by CSS, not skipped — see the slot comments
#: in `app.main`), and `edit_stimulus` is drawn on every run outside the view
#: guard, so an unprefixed id could meet the wizard's own while the add screen
#: is open.
#:
#: ``number`` here is a *placeholder*: two of the six are conditional (stimulus
#: images need a local filesystem, preprocessing is behind the
#: ``SCANPATH_EXPERIMENTAL`` flag), and a
#: screen numbered 1 · 2 · 3 · 5 reads as a missing section rather than as a
#: hidden one. `numbered()` renumbers whatever is actually on screen.
EDITOR_STEPS: tuple[WizardStep, ...] = (
    # The add screen's part 1, for a dataset that already has a name:
    # renaming it and its description are here, not in a dialog or on a row.
    WizardStep(
        "edit_name",
        1,
        "Name & description",
        "The dataset's name in the dataset list and picker, and the description "
        "shown under it.",
        False,
    ),
    WizardStep(
        "edit_data",
        1,
        "Data tables & column mapping",
        "Which of your columns the app reads as participant, trial, word, "
        "position and duration. Metadata tables attached to the dataset are "
        "here too.",
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
        "edit_stimulus",
        3,
        "Stimulus images",
        "Screenshots of the stimulus from a folder on this computer, drawn under "
        "the scanpath. Your data needs no image_path column for this. Saved with "
        "the dataset.",
        False,
    ),
    WizardStep(
        "edit_identity",
        4,
        "Trial identity",
        "Whether the Trial ID above identifies a single trial, checked on the "
        "whole dataset before any filtering.",
        False,
    ),
    WizardStep(
        "edit_preproc",
        5,
        "Preprocessing",
        "Optionally exclude or merge short fixations in every view. Off by "
        "default; the original rows stay available.",
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

    The parts run in a fixed order — there is nothing to map before a file is
    read — so this is a *label*, not navigation: no expander, no chips, no open
    state. It costs one line, which is the point: a sequence with no choices in
    it needs no header and click per part.

    ``trailing``, when given, is called with a column beside the
    title — a control that belongs on the title line rather than in the body — so it
    reads as part of the title line instead of as the first thing in the body.
    Only the title line splits; the returned body container stays full width.

    ``note`` hangs the part's explanation off the title as the same hover
    tooltip the rest of the wizard's prose uses, instead of a `st.caption` line
    under it. The add screen's own titles say everything they need to, so only
    the ✏️ Edit dataset screen passes one — its parts carry judgements a title
    cannot ("does the Trial ID identify one reading?").
    """
    box = host.container(key=part_key(step.id))
    mark = f"{icon_html(_badge_concept(status))} " if status else ""
    title = html.escape(step.title)
    if note:
        title = f'<span class="sps-fhelp" data-tip="{tooltip(note)}">{title}</span>'
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


def _badge_concept(status: StepStatus) -> str:
    return _BADGES.get(status, _BADGES[StepStatus.TODO])


def badge(status: StepStatus) -> str:
    """The icon shortcode shown against a step with this status."""
    return ICONS[_badge_concept(status)]


def step_panel(host, step: WizardStep, status: StepStatus):
    """A part's bold heading in the collapsed *Data & mapping* review panel.

    The panel is itself an expander, and Streamlit forbids expander-in-expander,
    so each part renders inline into ``host`` under this heading. The
    ``wizard_reconfigure`` assertion in ``tests/test_apptest.py`` relies on that.
    """
    host.markdown(f"**{badge(status)} {step.number}. {step.title}**")
    return host
