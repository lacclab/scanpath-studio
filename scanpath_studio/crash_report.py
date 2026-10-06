"""What the user sees when the app itself breaks: an error that asks them to tell us.

Streamlit's own handler draws a bare traceback, which reads as the user's
problem to solve. :func:`run_app` runs the whole script — the import of
``app.py`` included, so an error at import time is caught too — inside
:func:`guarded`, which draws a short note saying this is a bug in the app and
where to report it, followed by the same traceback (with its *Copy* button) for
the report.

Streamlit's control flow (``st.rerun``, ``st.stop``) raises ``BaseException``
subclasses, so it passes through untouched. Streamlit 1.65's ``on_script_error``
hook would do this job, but it is only wired up for ``st.App`` (ASGI) servers,
not for ``streamlit run``, which is how every surface launches the app.

This module imports only the standard library, Streamlit and ``constants`` —
itself stdlib-only — so it still loads when the module that failed is one of
ours.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlencode

import streamlit as st

from scanpath_studio import __version__
from scanpath_studio.constants import CITATION, ICONS

_LOGGER = logging.getLogger(__name__)


def report_url(error: BaseException) -> str:
    """The bug-report form, its title pre-filled with the error type and version.

    Only the exception's *type* goes into the URL — its message and traceback
    can carry file paths or values from the user's data, so those are left for
    the user to paste from the details below.
    """
    title = f"Crash: {type(error).__name__} (v{__version__})"
    return f"{CITATION['bug_report_url']}&{urlencode({'title': title})}"


def crash_message(error: BaseException) -> str:
    """The markdown shown above the traceback."""
    return (
        "**Scanpath Studio ran into an unexpected error.** This is most likely "
        "a bug in the app, not something you did — please let us know so we "
        "can fix it.\n\n"
        f"{ICONS['bug']} [Report this bug]({report_url(error)}) ↗ and paste the "
        "error details below (use their **Copy** button), with what you were "
        "doing when it happened and your operating system. "
        f"{ICONS['question']} Questions are welcome on "
        f"[Discussions → Q&A]({CITATION['questions_url']}) ↗.\n\n"
        f"Version {__version__}. Reloading the page usually gets you going again."
    )


def show_crash(error: Exception) -> None:
    """Log ``error`` to the server terminal and draw the report-it note + traceback."""
    _LOGGER.exception("Uncaught error in the app script", exc_info=error)
    st.error(crash_message(error), icon=ICONS["error"])
    st.exception(error)


@contextmanager
def guarded() -> Iterator[None]:
    """Turn an uncaught app error into :func:`show_crash` instead of a bare traceback."""
    try:
        yield
    except Exception as error:
        show_crash(error)


def run_app() -> None:
    """One script run of the app, crash note included — every entry script calls this."""
    with guarded():
        from scanpath_studio.app import main

        main()
