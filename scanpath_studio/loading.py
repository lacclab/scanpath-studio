"""UX-165: loading cards that keep the page whole, say what is happening, and
can be cancelled.

Three pieces, all built on :mod:`scanpath_studio.progress`:

* :func:`card` — a region card. It holds its region at the height the content
  will take (``size``), shows nothing for :data:`DELAY_S`, then reveals a card —
  title, elapsed time, a count or a step list, a bar, an optional Cancel — that
  a timer thread keeps current while the script thread is blocked. A card over
  work that is cheap on a cache hit is *gated* (``reveal_on_work``): it waits,
  past the delay, for its task's first report — a miss.
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

import contextlib
import contextvars
import html
import logging
import re
import threading
import time
from collections.abc import Callable, Hashable, Iterator, MutableMapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import streamlit as st
from streamlit.runtime.scriptrunner import (
    RerunException,
    StopException,
    add_script_run_ctx,
    get_script_run_ctx,
)

from scanpath_studio import progress
from scanpath_studio.constants import SELECTOR_ROW_GRID, icon_html
from scanpath_studio.progress import Snapshot
from scanpath_studio.styles import selector_track_floor

_LOGGER = logging.getLogger(__name__)

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
#: Tests that inspect a card frozen by ``st.stop()`` set this so the off-thread
#: clear (`_clear_off_thread`) doesn't fire; production code never does.
_KEEP_ON_STOP: bool = False


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
    """The card's first line: spinner, title, elapsed (+ the last load's time).

    Its live region (``role="status"``) is the title and the current step's
    label only — the label visually hidden, since the detail line or the step
    list already shows it — so a screen reader hears each step once. The
    elapsed time and the count, repainted about four times a second, sit
    outside it: still on the card, just not announced on every tick.
    """
    when = format_elapsed(snap.elapsed)
    if last is not None:
        when += f" · last load {format_elapsed(last)}"
    step = snap.steps[snap.current] if 0 <= snap.current < len(snap.steps) else ""
    spoken = _esc(snap.title)
    if step:
        spoken += f'<span class="sps-sr-only"> · {_esc(step)}</span>'
    return (
        '<div class="sps-card-head">'
        '<span class="sps-ring" aria-hidden="true"></span>'
        f'<span class="sps-card-title" role="status" aria-live="polite">{spoken}</span>'
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
    """A thin bar: filling when a total is known, sliding otherwise — and full
    once the task has finished (a kept page card, every step ticked)."""
    if snap.finished or snap.total:
        pct = (
            100
            if snap.finished
            else max(0, min(100, round(100 * (snap.done or 0) / snap.total)))
        )
        return (
            '<div class="sps-bar" role="progressbar" aria-valuemin="0" '
            f'aria-valuemax="100" aria-valuenow="{pct}">'
            f'<span style="width:{pct}%"></span></div>'
        )
    return '<div class="sps-bar sps-bar-indeterminate" aria-hidden="true"><span></span></div>'


#: A card key the size box can name in a selector.
_CARD_KEY = re.compile(r"[A-Za-z0-9_-]+")


def size_box_html(width: int, height: int, *, card_key: str) -> str:
    """The placeholder that holds a figure's place, and its card's width.

    ``height`` is the true-scale iframe's *fixed* height (the figure's own
    height + 12): `html_embed.embed_html_iframe` passes an int to `st.iframe`,
    so the row is exactly that tall at any column width. ``width`` is where the
    figure itself stops; the rule beside the box caps the card's own container
    there, so the card — box and body — spans exactly the figure in a wide
    column and the column in a narrow one, and centres over the figure
    (styles.py). A definite cap from above, deliberately: a grid track sized by
    its content grows past a narrow column or collapses to the card.

    Raises `ValueError` for a ``card_key`` that isn't a plain name (letters,
    digits, ``_`` and ``-``): it becomes a selector in a raw ``<style>``, where
    anything else would make the rule invalid and leave the card unstyled.
    """
    if not _CARD_KEY.fullmatch(card_key):
        # It becomes a selector in a raw <style>: fail loudly, not unstyled.
        raise ValueError(f"card key {card_key!r} must be a plain name")
    return (
        f'<div class="sps-size-box" aria-hidden="true" style="height:{int(height)}px"></div>'
        f"<style>.st-key-sps_card_{card_key}{{max-width:{int(width)}px}}</style>"
    )


def selector_row_tracks() -> str:
    """The skeleton's `grid-template-columns` for the selector row.

    Each track takes the real row's weight and the floor `styles.py` gives it
    (UX-181), so the skeleton draws the row the page is about to show.
    """
    return " ".join(
        f"minmax({selector_track_floor(i)}, {w}fr)"
        for i, w in enumerate(SELECTOR_ROW_GRID)
    )


def _scanpath_skeleton(plot_height: int) -> str:
    tracks = selector_row_tracks()
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


def _session() -> MutableMapping[str, Any]:
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


@dataclass(frozen=True)
class Cancel:
    """A card's Cancel button: its label says where it goes."""

    label: str
    on_click: Callable[..., None]
    args: tuple = ()


def session_id() -> str:
    """This run's session id — part of every task key, so one session's cancel
    can never stop another session's work."""
    ctx = get_script_run_ctx(suppress_warning=True)
    return ctx.session_id if ctx is not None else "local"


@dataclass
class _RunState:
    cards: list[Card] = field(default_factory=list)
    page: Page | None = None
    #: The page stood for a wait the user saw, and no ungated region card has
    #: carried it on yet (`card`): set by the region card whose opening released
    #: the page, cleared by the first ungated one — a gated card never clears it.
    inherit_seen: bool = False


_RUN: contextvars.ContextVar[_RunState | None] = contextvars.ContextVar(
    "scanpath_loading_run", default=None
)


def _run() -> _RunState:
    """The current run's state — or a throwaway one outside `run_scope`.

    Never sets the ContextVar itself: `run_scope` owns that set/reset pairing.
    A fragment rerun can reuse the same ScriptRunner thread, so a stray
    `_RUN.set(...)` here — with nothing that would ever reset it — would leak
    one run's cards/page into a later one that never entered `run_scope`.
    """
    state = _RUN.get()
    if state is None:
        return _RunState()
    return state


class _Ticker(threading.Thread):
    """The timer thread: wait out the delay, reveal, then refresh.

    With ``ready`` (a gated card, `Card`'s ``reveal_on_work``) the reveal also
    waits for ``ready()`` to hold, asked again every ``interval`` once the delay
    is over — so a card over a cache hit never shows, however long the hit takes.

    Its event is ``_halt``, never ``_stop``: `threading.Thread` has an internal
    ``_stop`` method that ``join`` calls.
    """

    def __init__(
        self,
        *,
        delay: float,
        interval: float,
        on_reveal: Callable[[], None],
        on_tick: Callable[[], None],
        ready: Callable[[], bool] | None = None,
    ):
        super().__init__(daemon=True, name="scanpath-loading-ticker")
        self._delay = delay
        self._interval = interval
        self._on_reveal = on_reveal
        self._on_tick = on_tick
        self._ready = ready
        self._halt = threading.Event()

    def run(self) -> None:
        if self._halt.wait(self._delay):
            return
        try:
            while self._ready is not None and not self._ready():
                if self._halt.wait(self._interval):
                    return
            self._on_reveal()
            while not self._halt.wait(self._interval):
                self._on_tick()
        except StopException:
            # The run's coordinator has been told to stop; nothing left to
            # update, and this is an expected outcome, not a bug — no log.
            return
        except Exception:
            # A placeholder whose run has ended: nothing left to update, but
            # unlike a stop this wasn't expected, so leave a trace of it.
            _LOGGER.debug("Loading card ticker stopped early", exc_info=True)
            return

    def halt(self) -> None:
        self._halt.set()


def _clear_off_thread(slot) -> None:
    """Clear ``slot`` from a short-lived helper thread.

    Once a run is stopped or superseded, Streamlit raises `StopException` /
    `RerunException` on the SCRIPT thread the next time it tries to send a
    message, instead of sending it — so `slot.empty()` never lands there.
    Off the script thread, Streamlit only checks a parallel-fragment
    coordinator (absent for a plain helper thread like this one), so the same
    call from here goes through.
    """

    def _clear() -> None:
        try:
            slot.empty()
        except Exception:
            pass

    thread = threading.Thread(target=_clear, daemon=True, name="scanpath-loading-clear")
    add_script_run_ctx(thread)
    thread.start()
    thread.join(timeout=1.0)


class Card:
    """One loading card in one slot (see the module docstring).

    ``reveal_on_work`` gates the card, for one over work that is cheap on a
    cache hit and slow only on a miss (the dataset pipeline, Compare's second
    dataset, the Corpus view's measures): its timer reveals it only once its
    task has reported (`progress.Task.worked`), so a plain rerun — however long
    its cache checks take on a big corpus — never shows it. ``reveal_now``
    still shows it at once. A region card that continues a wait the user saw
    (``inherit``, see `card`) skips the delay instead: ungated it shows at
    once; gated it shows the moment its task reports, and never on a hit.
    """

    def __init__(
        self,
        slot,
        *,
        key: str,
        title: str,
        steps: Sequence[str] = (),
        step_list: bool = False,
        cancel: Cancel | None = None,
        size: tuple[int, int] | None = None,
        skeleton: str | None = None,
        task_key: Hashable | None = None,
        duration_key: Hashable | None = None,
        reveal_class: str = "sps-reveal",
        reveal_on_work: bool = False,
    ):
        self._slot = slot
        self.key = key
        self._title = title
        self._steps = tuple(steps)
        self._step_list = step_list
        self._cancel = cancel
        self._size = size
        self._skeleton = skeleton
        self._explicit_task_key = task_key is not None
        self._task_key = (
            task_key if task_key is not None else ("card", session_id(), key)
        )
        self._duration_key = duration_key
        self._reveal_class = reveal_class
        self._reveal_on_work = reveal_on_work
        self._task: progress.Task | None = None
        self._token: contextvars.Token | None = None
        self._ticker: _Ticker | None = None
        self._revealed = False
        self._revealed_at: float | None = None
        self._revealed_by_timer = False
        self.is_open = False
        self._skeleton_ph = self._head = self._detail = self._bar = self._reveal = None
        # The "last load" hint, read once when the card opens: `finish` records
        # this load's own time, and the final repaint mustn't quote it back.
        self._last_duration: float | None = None

    @property
    def steps(self) -> tuple[str, ...]:
        return self._steps

    @property
    def revealed(self) -> bool:
        return self._revealed

    @property
    def was_seen(self) -> bool:
        """Did this card stand for a wait the user saw?

        Revealed by its timer (the wait outlasted `DELAY_S` — and, for a gated
        card, did real work), or on screen for at least `DELAY_S` since an
        immediate reveal (``reveal_now``). A page card
        revealed at once and taken down a moment later — a quick view switch —
        was not: nothing should carry its reveal on to the next card.
        """
        if not self._revealed:
            return False
        if self._revealed_by_timer:
            return True
        return (
            self._revealed_at is not None
            and time.monotonic() - self._revealed_at >= DELAY_S
        )

    @property
    def task(self) -> progress.Task | None:
        return self._task

    def open(self, *, reveal_now: bool = False, inherit: bool = False) -> Card:
        """Draw the card hidden — its size box shows at once — and arm the timer.

        Drawing happens before the task is begun and activated: if drawing
        itself fails (e.g. the run is already being torn down), no task is
        left active or half-started for something to have to clean up.

        ``reveal_now`` shows the card here, gated or not — a view switch's
        skeleton, the card after adding a dataset, a view switch onto a load in
        flight: the wait is known to be long before it starts. ``DELAY_S <= 0``
        (the headless tests' setting) does the same for every card: "show
        everything at once" is what that setting is for.

        ``inherit`` — the card continues a wait the user saw (`card`) — skips
        the delay but not the gate: an ungated card shows here, as with
        ``reveal_now``; a gated one is armed with no delay, so it shows the
        moment its task reports work and never on a cache hit.
        """
        box = self._slot.container(key=f"sps_card_{self.key}")
        if self._size is not None:
            box.markdown(
                size_box_html(*self._size, card_key=self.key), unsafe_allow_html=True
            )
        if self._skeleton is not None:
            self._skeleton_ph = box.empty()
        body = box.container(key=f"sps_cardbody_{self.key}")
        self._head = body.empty()
        self._detail = body.empty()
        self._bar = body.empty()
        if self._cancel is not None:
            body.button(
                self._cancel.label,
                key=f"sps_cancel_{self.key}",
                on_click=self._cancel.on_click,
                args=self._cancel.args,
                width="content",
            )
        self._reveal = body.empty()
        self.is_open = True
        _run().cards.append(self)
        if self._duration_key is not None:
            self._last_duration = progress.last_duration(self._duration_key)
        self._task = progress.begin(
            self._task_key,
            title=self._title,
            steps=self._steps,
            fresh=not self._explicit_task_key,
        )
        self._token = progress.activate(self._task)
        if reveal_now or DELAY_S <= 0 or (inherit and not self._reveal_on_work):
            self._show()
            if DELAY_S > 0:
                self._arm(delay=REFRESH_S, revealed=True)
        elif inherit:
            self._arm(delay=0, revealed=False)
        else:
            self._arm(delay=DELAY_S, revealed=False)
        return self

    def _paint(self) -> None:
        snap = self._task.snapshot()
        self._head.markdown(
            head_html(snap, last=self._last_duration), unsafe_allow_html=True
        )
        body = steps_html(snap) if self._step_list and snap.steps else detail_html(snap)
        if body:
            self._detail.markdown(body, unsafe_allow_html=True)
        else:
            self._detail.empty()
        self._bar.markdown(bar_html(snap), unsafe_allow_html=True)

    def _show(self) -> None:
        if self._skeleton_ph is not None:
            self._skeleton_ph.markdown(self._skeleton, unsafe_allow_html=True)
        self._paint()
        self._reveal.markdown(
            f'<span class="{self._reveal_class}"></span>', unsafe_allow_html=True
        )
        self._revealed_at = time.monotonic()
        self._revealed = True

    def _show_by_timer(self) -> None:
        self._show()
        self._revealed_by_timer = True

    def _has_worked(self) -> bool:
        return self._task is not None and self._task.worked

    def _arm(self, *, delay: float, revealed: bool) -> None:
        ticker = _Ticker(
            delay=delay,
            interval=REFRESH_S,
            on_reveal=self._paint if revealed else self._show_by_timer,
            on_tick=self._paint,
            ready=self._has_worked if self._reveal_on_work and not revealed else None,
        )
        add_script_run_ctx(ticker)
        ticker.start()
        self._ticker = ticker

    def _halt(self) -> None:
        if self._ticker is not None:
            self._ticker.halt()
            self._ticker.join(timeout=1.0)
            self._ticker = None

    def step(self, index: int, label: str | None = None) -> None:
        if self._task is None:
            return
        self._task.step_to(index, label)
        # With no timer running (DELAY_S == 0, as the headless tests use),
        # nothing else would repaint a shown card. `is_open` also guards a
        # card whose slot is already cleared: `_ticker` goes back to None
        # once halted, but `_revealed` stays True forever.
        if self.is_open and self._revealed and self._ticker is None:
            self._paint()

    def finish(self) -> None:
        """Every step done — and the "last load" time recorded, for a real load.

        Only a task that did real work (`progress.Task.worked` — something
        reported) *and* took at least `DELAY_S` records its duration: the
        dataset card opens on every run, and a plain rerun's 0.04 s would
        otherwise overwrite the real load's time, so a slow load read "last
        load 0.0 s" — nor is a plain rerun that happened to be slow, all cache
        checks on a big corpus, a load. A task that is already finished —
        retired by `Page.release` when something else interrupted the load, an
        inline download say — records nothing either.
        """
        task = self._task
        if task is None or task.finished:
            return
        waited = time.monotonic() - task.started
        record = task.worked and waited >= DELAY_S
        task.finish(duration_key=self._duration_key if record else None)

    def _retire(self) -> None:
        """Finish this card's task with no duration key, so a later run's
        `progress.begin` for the same key never joins it.

        Called whenever this card's run ends in a way that will not itself
        resume the task (a normal close, or an ordinary exception) — never
        when `close()` hits `StopException`/`RerunException`, the one case
        `progress.begin`'s joining exists for (see `Card.close`).
        """
        if self._task is not None:
            self._task.finish()

    def close(self, *, keep: bool = False) -> None:
        """Stop the timer and take the card down — or, with ``keep``, leave it
        showing every step done (the page card, until its page is released).

        A stopped or superseded run can't clear its own slot from the script
        thread — Streamlit raises `StopException`/`RerunException` there
        instead of sending the message (see `_clear_off_thread`) — so that's
        caught here and retried off-thread before the exception is re-raised,
        unless `_KEEP_ON_STOP` (tests only) says to leave the card frozen. A
        slot that clears normally retires this card's task; one Streamlit
        aborted stays joinable, since a rerun that interrupted a load is
        exactly the case joining exists for.
        """
        if not self.is_open:
            return
        self._halt()
        try:
            if keep:
                if self._revealed:
                    self._paint()
            else:
                try:
                    self._slot.empty()
                except (StopException, RerunException):
                    if not _KEEP_ON_STOP:
                        _clear_off_thread(self._slot)
                    raise
                else:
                    self._retire()
        finally:
            if self._token is not None:
                progress.deactivate(self._token)
                self._token = None
            self.is_open = False


class Page:
    """The page skeleton and its dataset card, in the view's first slot."""

    def __init__(self, slot, *, view: str, plot_height: int = 480):
        self._slot = slot
        self._view = view
        self._plot_height = plot_height
        self.card: Card | None = None
        self._released = False
        _run().page = self

    def open_card(
        self,
        *,
        title: str,
        steps: Sequence[str] = (),
        cancel: Cancel | None = None,
        task_key: Hashable | None = None,
        duration_key: Hashable | None = None,
        reveal_now: bool = False,
        reveal_on_work: bool = False,
    ) -> Card:
        self.card = Card(
            self._slot,
            key=PAGE_CARD_KEY,
            title=title,
            steps=steps,
            step_list=bool(steps),
            cancel=cancel,
            skeleton=skeleton_html(self._view, plot_height=self._plot_height),
            task_key=task_key,
            duration_key=duration_key,
            reveal_class="sps-reveal sps-reveal-page",
            reveal_on_work=reveal_on_work,
        )
        return self.card.open(reveal_now=reveal_now)

    def release(self) -> bool:
        """Take the skeleton down; say whether its wait was one the user saw.

        A region card opening next shows at once only then (`card`), so a long
        wait reads as one continuous state — but a page revealed at once for a
        quick view switch (`Card.was_seen`) must not make the view's first card
        flash for a frame.

        Closes the card *before* reading it: a concurrently-ticking card could
        still be mid-`_show()` on its timer thread, and closing joins that
        thread first, so the read afterwards can't race a reveal that was
        already underway.

        Once its own slot has cleared, an unfinished task of the card's is
        retired (finished, no duration): something released the page in the
        middle of the load — an inline download, say — and the next run must
        start that load's card afresh, not join a task stopped mid-step. A clear
        Streamlit aborts (a stopped or superseded run) raises before that point,
        so an abandoned run's task stays joinable.
        """
        if self._released:
            return False
        self._released = True
        card = self.card
        if card is not None and card.is_open:
            card.close(keep=True)
        seen = bool(card is not None and card.was_seen)
        self._slot.empty()
        if card is not None and card.task is not None and not card.task.finished:
            card.task.finish()
        state = _RUN.get()
        if state is not None and state.page is self:
            state.page = None
        return seen


def page(slot, *, view: str, plot_height: int = 480) -> Page:
    """Reserve ``slot`` as this run's page (see :class:`Page`)."""
    return Page(slot, view=view, plot_height=plot_height)


def release_page() -> bool:
    """Release this run's page, if any; say whether its wait was one the user
    saw (`Page.release`)."""
    state = _RUN.get()
    current = state.page if state is not None else None
    return current.release() if current is not None else False


@contextlib.contextmanager
def card(
    slot,
    *,
    key: str,
    title: str,
    steps: Sequence[str] = (),
    step_list: bool = False,
    cancel: Cancel | None = None,
    size: tuple[int, int] | None = None,
    task_key: Hashable | None = None,
    duration_key: Hashable | None = None,
    reveal_on_work: bool = False,
) -> Iterator[Card]:
    """A region card for one ``with`` block.

    Opening one releases the page skeleton: the view has drawn its controls by
    the time it reaches its first slow region. When the skeleton stood for a
    wait the user saw (`Page.release`), the wait carries on (`Card.open`'s
    ``inherit``), so it reads as one continuous state: to the first **ungated**
    region card of the run, which shows at once and uses it up. A gated card
    (``reveal_on_work``, see `Card`) on the way shows through its gate with no
    delay — the moment it reports work, never on a cache hit — and passes the
    wait on: Compare's B card, cached, must not flash, nor leave the figure's
    card after it to wait its own delay with the previous dataset's figure
    unveiled. Only this function's own release starts the carry; one
    `release_page()` made elsewhere (an inline download, a view with nothing to
    draw) hands nothing on.

    An ordinary exception from the block retires the card's task (see
    `Card._retire`) before re-raising — a card with an explicit `task_key`
    that failed must not look, to a later run, like one still safely loading.
    `open()` is inside the ``try`` too, so `close()` still runs (a no-op,
    since it never got to `is_open = True`) if opening itself raises.
    """
    state = _run()
    if release_page():
        state.inherit_seen = True
    inherit = state.inherit_seen
    if inherit and not reveal_on_work:
        state.inherit_seen = False  # the first ungated card carries it on
    region = Card(
        slot,
        key=key,
        title=title,
        steps=steps,
        step_list=step_list,
        cancel=cancel,
        size=size,
        task_key=task_key,
        duration_key=duration_key,
        reveal_on_work=reveal_on_work,
    )
    try:
        region.open(inherit=inherit)
        yield region
        region.finish()
    except Exception:
        region._retire()
        raise
    finally:
        region.close()


@contextlib.contextmanager
def run_scope() -> Iterator[None]:
    """Wrap one script run: fresh state in, every timer stopped out.

    A run whose work was cancelled ends as a **stopped** one: the `Cancelled`
    is re-raised as Streamlit's own `StopException`, which Streamlit treats as
    a premature stop and so skips its stale-widget sweep — the state of every
    widget the run never reached is kept, where a normal finish would drop it.
    Today only an abandoned run ever computes a cancelled task
    (`progress.begin` never joins one), so its page is gone and Streamlit drops
    whatever it sends either way; the stop is what keeps a cut-short run from
    ending as a successful one, should a cancel ever reach a run on screen.

    A card or the page left open when the run ends — interrupted, or simply
    never closed — is cleared off-thread here too, the same
    `StopException`/`RerunException` problem `Card.close()` guards against,
    for whatever this run didn't get to close itself. `_KEEP_ON_STOP` (tests
    only) skips it, same as in `close()`.

    A run that ends with an ordinary exception also retires the tasks of the
    cards it left open (see `Card._retire`) before the exception carries on:
    nothing will resume them, and a later run must not join a load that
    failed. A stopped or superseded run (`StopException`/`RerunException`,
    which are not `Exception`s) leaves them joinable, as `Card.close` does.
    """
    token = _RUN.set(_RunState())
    failed = False
    try:
        with progress.scope():
            yield
    except progress.Cancelled:
        raise StopException() from None
    except Exception:
        failed = True
        raise
    finally:
        state = _RUN.get()
        if state is not None:
            for opened in list(state.cards):
                opened._halt()
                if opened.is_open and failed:
                    opened._retire()
                if opened.is_open and not _KEEP_ON_STOP:
                    _clear_off_thread(opened._slot)
            run_page = state.page
            if run_page is not None and not run_page._released and not _KEEP_ON_STOP:
                _clear_off_thread(run_page._slot)
        _RUN.reset(token)


def covered() -> bool:
    """Is a card open in this run?"""
    state = _RUN.get()
    return bool(state is not None and any(c.is_open for c in state.cards))


def spinner(text: str) -> contextlib.AbstractContextManager[Any]:
    """``st.spinner`` with the elapsed time — silent while a card covers it."""
    if covered():
        return contextlib.nullcontext()
    return st.spinner(text, show_time=True)
