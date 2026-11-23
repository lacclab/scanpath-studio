"""Local troubleshooting answers and the project's GitHub support routes."""

from __future__ import annotations

import platform

import streamlit as st

from scanpath_studio import persistence
from scanpath_studio.build_info import INSTALL_KINDS, build_info, install_kind
from scanpath_studio.constants import CITATION, ICONS, drift_correction_enabled
from scanpath_studio.crash_report import guarded

_REQUESTED_KEY = "_feedback_dialog_requested"


def _storage_answer() -> str:
    """Describe this session's recovery state and the relevant next action."""
    local = persistence.server_bound_to_loopback()
    location = (
        "Your files are processed on this computer."
        if local
        else "Your files are processed on this server. Use the desktop app to keep uploads on your computer."
    )
    saving = persistence.persistence_enabled(str(st.context.url or ""))
    backups = (
        "Keep your original files. Before refreshing, export annotations from "
        "**Data Management → Annotations** and plot settings from "
        "**Scanpath → Share → Settings file**."
    )
    if not saving:
        recovery = f"Uploads stay in memory for this session. {backups}"
    elif persistence.persistence_paused(st.session_state):
        recovery = f"Recovery saving is paused for this session. {backups} Reload to retry the saved copy."
    elif st.session_state.get(persistence.SAVE_CONFLICT_KEY):
        recovery = f"The app couldn’t update the recovery copy. Your unsaved edits are still in this tab. {backups}"
    else:
        recovery = (
            "A recovery copy keeps your datasets, settings and annotations between visits. "
            "To remove it, open **Data Management → Saved on this computer → "
            "Clear what is saved…**."
        )
    return f"{location} {recovery}"


def troubleshooting_items() -> list[tuple[str, str]]:
    """Short answers available offline, with links into this edition's documentation."""
    docs = build_info().docs_url
    items = [
        (
            "The fixations don’t line up with the words.",
            "Check that the Words and Fixations tables describe the same trial and "
            "screen, with coordinates in pixels measured from the same origin. "
            "Correct any offset or scale difference in the source files before importing "
            "again. If only the figure’s framing is wrong, check **Data Management → "
            "Edit dataset → Recording setup → Screen**. "
            f"[Files and units]({docs}guides/loading-data/#tables)",
        ),
        (
            "An imported column is mapped to the wrong field.",
            "Open **Data Management → Edit dataset → Data tables & column mapping**, "
            "choose the right column and save your changes. If the column was left "
            "out during import, add the dataset again from the original files and "
            "keep that column.",
        ),
        (
            "Corpus Analysis shows no reading measures.",
            "Check which dataset and trials are selected. Corpus Analysis needs a Words "
            "table with a per-word measure such as first fixation duration. For an "
            "imported dataset, open **Data Management → Edit dataset** and map that "
            "column under **Words → Reading measures**. "
            f"[Reading measures]({docs}guides/loading-data/#reading-measures)",
        ),
        (
            "My coauthor can’t open my shared view.",
            "A link shares the trial and figure settings. The demo opens directly, "
            "and public corpora open where available. For uploads, send the original "
            "files and the setup file from **Edit dataset → Download setup file**. "
            "On another computer, import them under the name in the link, then reopen "
            "it using that app’s address. "
            f"[Sharing a view]({docs}guides/scanpath-visualization/controls/#under-the-plot)",
        ),
        (
            "Where is my data stored? Will it survive a refresh?",
            f"{_storage_answer()} [Privacy and storage]({docs}about/#privacy)",
        ),
        (
            "A PDF, image bundle or video won’t export.",
            "These exports need Chrome, Chromium or Edge on the computer running "
            "Scanpath Studio. Install one locally or ask the server administrator. "
            "For a figure you can save now, choose **HTML** or use **PNG** or **SVG** "
            "under the current plot. "
            f"[Export troubleshooting]({docs}faq/#export-fails)",
        ),
    ]
    if drift_correction_enabled():
        items.append(
            (
                "What does drift correction change?",
                "In Full mode, **Fixations → Drift correction** moves the displayed "
                "fixations to their estimated text lines. Your table keeps the recorded "
                "coordinates. Open **Line assignment** to compare the ten methods from "
                "Carr et al. (2021).",
            )
        )
    return items


def environment_details() -> str:
    """Version and system details the user can copy into a bug report."""
    from scanpath_studio import __version__

    where = "this computer" if persistence.server_bound_to_loopback() else "a server"
    kind = install_kind()
    return "\n".join(
        (
            f"Scanpath Studio {__version__}",
            f"Installed with: {INSTALL_KINDS.get(kind, kind)}",
            f"Running on: {where}",
            f"OS: {platform.platform(terse=True)} ({platform.machine()})",
            f"Python {platform.python_version()} · Streamlit {st.__version__}",
        )
    )


def _arm_feedback() -> None:
    """Request troubleshooting from Help or About before the next full rerun."""
    st.session_state[_REQUESTED_KEY] = True


def maybe_show_feedback() -> None:
    """Open the requested dialog before the app draws the current plot."""
    if st.session_state.pop(_REQUESTED_KEY, False):
        _feedback_dialog()


@st.dialog(f"{ICONS['feedback']} Troubleshooting & feedback", width="medium")
@guarded()
def _feedback_dialog() -> None:
    for problem, answer in troubleshooting_items():
        with st.expander(problem):
            st.markdown(answer)

    st.markdown("**Contact the project on GitHub**")
    with st.container(horizontal=True, gap="small"):
        st.link_button("Ask a question ↗", CITATION["questions_url"])
        reporting = st.button("Report a bug", key="help_report_bug")
        st.link_button("Suggest an improvement ↗", CITATION["ideas_url"])
    if reporting:
        st.markdown(
            "Tell us what you did, what you expected and what happened. "
            "Copy these details into the GitHub report."
        )
        st.code(environment_details(), language=None, wrap_lines=True)
        st.link_button("Open bug report on GitHub ↗", CITATION["bug_report_url"])
