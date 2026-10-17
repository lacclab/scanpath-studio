"""*Send feedback* — the ❓ Help entry that says where each kind of feedback goes.

**Nothing is sent from the app.** Every route is a GitHub page the user opens in
their browser and submits themselves, so recordings stay on the user's computer
and the app needs no feedback service. The dialog lists four routes (a bug
report, a feature request, an idea or general comment, a question) and, for a
bug report, the details its template asks for — version, install, Python,
Streamlit, OS — in a block with a *Copy* button, so a report doesn't depend on
the user finding the version first.

The details are shown, not put into the issue URL: the user sees exactly what
they paste, and the template's own sections stay intact (a ``body=`` parameter
would replace them).
"""

from __future__ import annotations

import platform

import streamlit as st

from scanpath_studio.constants import CITATION, ICONS
from scanpath_studio.crash_report import guarded

#: The session flag the ❓ Help entry sets and :func:`maybe_show_feedback` serves.
_REQUESTED_KEY = "_feedback_dialog_requested"

#: (key, label, icon key, url, what it is for) — the dialog's routes, in order.
ROUTES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "bug",
        "Report a bug",
        "bug",
        CITATION["bug_report_url"],
        "Something behaves wrongly, shows a wrong value, or crashes. "
        "Paste the details below into it.",
    ),
    (
        "feature",
        "Suggest a feature",
        "feature_request",
        CITATION["feature_request_url"],
        "Something you want the app to do, in your own terms.",
    ),
    (
        "idea",
        "Share an idea or comment",
        "comment",
        CITATION["ideas_url"],
        "Anything else: what works, what is confusing, what you use it for.",
    ),
    (
        "question",
        "Ask a question",
        "question",
        CITATION["questions_url"],
        "How do I…? Is this expected? The answer helps the next person too.",
    ),
)


def environment_details() -> str:
    """The lines a bug report needs, as plain text for the user to paste.

    Where the server is not on loopback (the online demo, a shared install),
    the OS and install are the *server's*, so it says so rather than let them
    read as the user's own computer.
    """
    import streamlit

    from scanpath_studio import __version__
    from scanpath_studio.build_info import INSTALL_KINDS, install_kind
    from scanpath_studio.persistence import server_bound_to_loopback

    where = "this computer" if server_bound_to_loopback() else "a server"
    return "\n".join(
        (
            f"Scanpath Studio {__version__}",
            f"Installed with: {INSTALL_KINDS.get(install_kind(), install_kind())}",
            f"Running on: {where}",
            f"OS: {platform.platform(terse=True)} ({platform.machine()})",
            f"Python {platform.python_version()} · Streamlit {streamlit.__version__}",
        )
    )


def _arm_feedback() -> None:
    """Request the dialog. Called by the ❓ Help nav entry
    (``menu._arm_help_action``); a dialog can't open from there, so this only
    sets the flag :func:`maybe_show_feedback` serves early in ``main()``."""
    st.session_state[_REQUESTED_KEY] = True


def maybe_show_feedback() -> None:
    """Open the dialog if the ❓ Help entry armed it. Served beside
    ``maybe_show_about`` for the same reason: before the heavy plot work, so the
    modal does not wait out the rerun."""
    if st.session_state.pop(_REQUESTED_KEY, False):
        _feedback_dialog()


@st.dialog(f"{ICONS['feedback']} Send feedback", width="medium")
@guarded()
def _feedback_dialog() -> None:
    """Four routes to GitHub, and the details to paste into a bug report."""
    from scanpath_studio.menu import close_open_popovers

    close_open_popovers()
    st.caption(
        "Nothing is sent from the app. Each button opens a page on GitHub, "
        "where you write and submit it yourself (a free GitHub account is "
        "needed)."
    )
    for key, label, icon, url, purpose in ROUTES:
        st.link_button(
            f"{label} ↗",
            url,
            icon=ICONS[icon],
            width="stretch",
            type="primary" if key == "bug" else "secondary",
        )
        st.caption(purpose)
    st.markdown("**Details for a bug report**")
    st.code(environment_details(), language=None, wrap_lines=True)
    st.caption(
        "Add what you did, what you expected and what happened instead — and, "
        "if a trial shows it, a share link from 🗺️ Scanpath → 🔗 Share."
    )
