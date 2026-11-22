"""Shared feedback for unreadable table uploads."""

from __future__ import annotations

from pathlib import Path

from .data import explain_read_error


def say_read_error(host, name: str, exc: BaseException) -> None:
    """Show the upload error and leave parser details in an expander."""
    error = explain_read_error(name, exc)
    shown = name if error.name == Path(str(name)).name else error.name
    host.error(
        error.sentence(f"**{shown}**")
        + " To remove the file, click the ✕ next to its name."
    )
    if error.detail:
        host.expander("Technical detail").code(error.detail, language=None)
