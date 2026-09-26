"""UX-165: loading cards that keep the page whole, say what is happening, and
can be cancelled.

Three pieces, all built on :mod:`scanpath_studio.progress`:

* :func:`card` — a region card. It holds its region at the height the content
  will take (``size``), shows nothing for :data:`DELAY_S`, then reveals a card —
  title, elapsed time, a count or a step list, a bar, an optional Cancel — that
  a timer thread keeps current while the script thread is blocked.
* :class:`Page` — the page skeleton and the dataset card, for a load that holds
  up a whole view. It outlives its card: :meth:`Page.release` takes it down once
  the new page has drawn its controls, and a region card opening releases it.
* :func:`run_scope` — wraps each script run, so no timer outlives its run.

Mechanics, proved by the UX-165 spike: the **script thread** draws each card
hidden when it opens — its Cancel button included, since a widget must be
created on the script thread and once per run — and a **timer thread**
carrying the script-run context reveals it and rewrites only its text
placeholders, the way ``st.spinner``'s own timer does. A click abandons the
running script at once (``runner.fastReruns``); Streamlit drops everything the
abandoned run's timer sends, and the abandoned run cannot write session state.
"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from scanpath_studio.constants import SELECTOR_ROW_GRID, icon_html
from scanpath_studio.progress import Snapshot

#: Nothing shows for this long — Streamlit's own spinner delay.
DELAY_S: float = 0.5
#: How often a card refreshes once it shows.
REFRESH_S: float = 0.25
#: Session-state home of the last embedded size per plot key.
PLOT_SIZES_KEY = "_sps_plot_sizes"
#: The Scanpath and Corpus views' reserved area (``app.main``).
VIEW_AREA_KEY = "sps_view"
#: The page card's key — there is one page per run.
PAGE_CARD_KEY = "page"


def _esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def format_elapsed(seconds: float) -> str:
    """``0.8 s`` · ``42 s`` · ``2 min 5 s``."""
    if seconds < 10:
        return f"{seconds:.1f} s"
    if seconds < 60:
        return f"{seconds:.0f} s"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} min {rest} s" if rest else f"{minutes} min"


def _megabytes(n: int) -> str:
    return f"{n / 1e6:,.1f}" if n < 10e6 else f"{n / 1e6:,.0f}"


def format_count(done: int | None, total: int | None, unit: str) -> str:
    """``312 of 900 files`` · ``120 of 450 MB`` · ``3.2 MB so far``."""
    if done is None:
        return ""
    if unit == "bytes":
        if total:
            return f"{_megabytes(done)} of {_megabytes(total)} MB"
        return f"{_megabytes(done)} MB so far"
    suffix = f" {unit}" if unit else ""
    if total:
        return f"{done:,} of {total:,}{suffix}"
    return f"{done:,}{suffix}"


def head_html(snap: Snapshot, *, last: float | None = None) -> str:
    """The card's first line: spinner, title, elapsed (+ the last load's time)."""
    when = format_elapsed(snap.elapsed)
    if last is not None:
        when += f" · last load {format_elapsed(last)}"
    return (
        '<div class="sps-card-head" role="status" aria-live="polite">'
        '<span class="sps-ring" aria-hidden="true"></span>'
        f'<span class="sps-card-title">{_esc(snap.title)}</span>'
        f'<span class="sps-card-time">{_esc(when)}</span></div>'
    )


def detail_html(snap: Snapshot) -> str:
    """The detail line: the current step, a detail, the count — or nothing."""
    parts = []
    if snap.steps and snap.current < len(snap.steps):
        parts.append(snap.steps[snap.current])
    if snap.detail:
        parts.append(snap.detail)
    count = format_count(snap.done, snap.total, snap.unit)
    if count:
        parts.append(count)
    if not parts:
        return ""
    return f'<div class="sps-card-detail">{_esc(" · ".join(parts))}</div>'


def steps_html(snap: Snapshot) -> str:
    """B's step list: done steps with ✓ and their time, the current one with a
    spinner and its count, later ones greyed out."""
    items = []
    for i, label in enumerate(snap.steps):
        if i < snap.current:
            items.append(
                '<li class="sps-step sps-step-done">'
                f"{icon_html('step_done')}"
                f'<span class="sps-step-label">{_esc(label)}</span>'
                f'<span class="sps-step-time">'
                f"{_esc(format_elapsed(snap.step_seconds[i] or 0.0))}</span></li>"
            )
        elif i == snap.current:
            extra = " · ".join(
                part
                for part in (
                    snap.detail or "",
                    format_count(snap.done, snap.total, snap.unit),
                )
                if part
            )
            items.append(
                '<li class="sps-step sps-step-now">'
                '<span class="sps-ring" aria-hidden="true"></span>'
                f'<span class="sps-step-label">{_esc(label)}</span>'
                f'<span class="sps-step-count">{_esc(extra)}</span></li>'
            )
        else:
            items.append(
                '<li class="sps-step sps-step-todo">'
                f"{icon_html('step_todo')}"
                f'<span class="sps-step-label">{_esc(label)}</span></li>'
            )
    return f'<ol class="sps-steps">{"".join(items)}</ol>'


def bar_html(snap: Snapshot) -> str:
    """A thin bar: filling when a total is known, sliding otherwise."""
    if snap.total:
        pct = max(0, min(100, round(100 * (snap.done or 0) / snap.total)))
        return (
            '<div class="sps-bar" role="progressbar" aria-valuemin="0" '
            f'aria-valuemax="100" aria-valuenow="{pct}">'
            f'<span style="width:{pct}%"></span></div>'
        )
    return '<div class="sps-bar sps-bar-indeterminate" aria-hidden="true"><span></span></div>'


def size_box_html(width: int, height: int) -> str:
    """The placeholder that holds a figure's place.

    ``height`` is the true-scale iframe's *fixed* height (the figure's own
    height + 12): `html_embed.embed_html_iframe` passes an int to `st.iframe`,
    so the row is exactly that tall at any column width. ``width`` caps it where
    the figure itself will stop.
    """
    return (
        '<div class="sps-size-box" aria-hidden="true" '
        f'style="height:{int(height)}px;max-width:{int(width)}px"></div>'
    )


def _scanpath_skeleton(plot_height: int) -> str:
    tracks = " ".join(f"{w}fr" for w in SELECTOR_ROW_GRID)
    fields = '<div class="sps-sk sps-sk-field"></div>' * len(SELECTOR_ROW_GRID)
    chips = '<div class="sps-sk sps-sk-chip"></div>' * 4
    rail = '<div class="sps-sk sps-sk-row"></div>' * 9
    return (
        '<div class="sps-page-skeleton sps-sk-scanpath" aria-hidden="true">'
        '<div class="sps-sk-main">'
        f'<div class="sps-sk-selectors" style="grid-template-columns:{tracks}">'
        f"{fields}</div>"
        f'<div class="sps-sk-chips">{chips}</div>'
        f'<div class="sps-sk sps-sk-plot" style="height:{int(plot_height)}px"></div>'
        "</div>"
        f'<div class="sps-sk-rail">{rail}</div>'
        "</div>"
    )


def skeleton_html(view: str, *, plot_height: int = 480) -> str:
    """A skeleton of ``view``: ``"scanpath"`` · ``"corpus"`` · ``"data"``."""
    if view == "scanpath":
        return _scanpath_skeleton(plot_height)
    if view == "corpus":
        return (
            '<div class="sps-page-skeleton sps-sk-corpus" aria-hidden="true">'
            '<div class="sps-sk sps-sk-tabs"></div>'
            '<div class="sps-sk sps-sk-chart"></div>'
            '<div class="sps-sk sps-sk-chart"></div></div>'
        )
    rows = '<div class="sps-sk sps-sk-row"></div>' * 6
    return (
        f'<div class="sps-page-skeleton sps-sk-table" aria-hidden="true">{rows}</div>'
    )


def estimate_plot_size(
    canvas_width: int, canvas_height: int, *, animation: bool = False
) -> tuple[int, int]:
    """``(width, iframe height)`` a first figure on this canvas will take.

    The builders' own fit (`plots._fit_display_size`) for a figure framed on the
    full canvas, plus the axes' margins and, for a replay, the transport
    controls under it. Only a first render uses it; later ones reuse the size
    the last figure under the same plot key actually had (:func:`plot_size`).
    """
    from scanpath_studio.plots import (
        _CONTROLS_MARGIN_PX,
        _CONTROLS_SAFETY_PX,
        _fit_display_size,
    )

    cw, ch = max(int(canvas_width), 1), max(int(canvas_height), 1)
    width, height = _fit_display_size(cw, ch, [0, cw], [ch, 0], True)
    height += 60
    if animation:
        height += _CONTROLS_MARGIN_PX + _CONTROLS_SAFETY_PX
    return int(width), int(height) + 12


def _session():
    """Session state, or a throwaway dict outside a script run."""
    try:
        return st.session_state
    except Exception:
        return {}


def record_plot_size(key: str, width: int, height: int) -> None:
    """Remember the size a figure under ``key`` was embedded at."""
    state = _session()
    sizes = dict(state.get(PLOT_SIZES_KEY) or {})
    sizes[str(key)] = (int(width), int(height))
    state[PLOT_SIZES_KEY] = sizes


def plot_size(
    key: str, canvas_width: int, canvas_height: int, *, animation: bool = False
) -> tuple[int, int]:
    """The recorded size for ``key``, else :func:`estimate_plot_size`."""
    recorded = (_session().get(PLOT_SIZES_KEY) or {}).get(str(key))
    if recorded:
        return int(recorded[0]), int(recorded[1])
    return estimate_plot_size(canvas_width, canvas_height, animation=animation)


def recorded_plot_height(key: str, default: int) -> int:
    recorded = (_session().get(PLOT_SIZES_KEY) or {}).get(str(key))
    return int(recorded[1]) if recorded else int(default)
