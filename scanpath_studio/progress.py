"""UX-165: a Streamlit-free progress hook for slow work.

Loaders and figure builders call :func:`report` from inside their loops, and
the orchestrator calls :func:`step_to` between stages. With no task active both
return at once, so the headless API and the CLI see no change. With one active
— ``loading.card`` opens it — they update a thread-safe :class:`Task` that the
card's timer thread reads.

The two calls are also the **cancel checkpoint**: after :func:`cancel`, the next
call in the computing thread raises :class:`Cancelled`, so abandoned work stops
within one file, frame or chunk instead of running to the end of its step.

And they are where slow work **lets the server talk**. A CPU-bound build on the
script thread holds Python's GIL, and the server's event loop needs several
handoffs of it to send one message, each waiting out the interpreter's switch
interval — so everything a run queues, a card's own reveal included, used to
reach the browser only once the build ended. Inside a task, a call therefore
sleeps for ``YIELD_S`` whenever ``YIELD_EVERY_S`` has passed since the task last
did: a sleep releases the GIL outright, and the loop drains its queue
uncontended.

Nothing here creates a Streamlit element, deliberately. The replay's frame loop
runs inside two nested ``st.cache_data`` functions, and Streamlit replays every
element created inside a cached function on each later hit — a progress bar
drawn from inside the loop would reappear on every rerun.
"""

from __future__ import annotations

import contextvars
import threading
import time
from collections.abc import Hashable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

#: How often a task's checkpoints hand the GIL over, and for how long — at most
#: YIELD_S / YIELD_EVERY_S (4%) of the work's time. Measured on the cold first
#: replay build: the rail reached the browser at 0.5 s instead of 3.2 s, and the
#: card showed on time instead of not at all.
YIELD_EVERY_S = 0.025
YIELD_S = 0.001

# The yield's clock and sleep: module attributes, so a test can replace them
# without patching the `time` module every thread shares.
_clock = time.monotonic
_sleep = time.sleep


class Cancelled(BaseException):
    """Raised at a checkpoint once the running task has been cancelled.

    A ``BaseException``, like Streamlit's own ``StopException``, so the broad
    ``except Exception`` handlers in the load path (a mapping that fails, a
    corpus that will not read) cannot mistake a cancel for a data error.
    """


@dataclass(frozen=True)
class Snapshot:
    """One consistent reading of a :class:`Task`, for a card to draw."""

    title: str
    steps: tuple[str, ...]
    step_seconds: tuple[float | None, ...]
    current: int
    done: int | None
    total: int | None
    unit: str
    detail: str | None
    elapsed: float
    finished: bool


class Task:
    """What one slow job has done so far.

    Written by the computing thread and read by a card's timer thread, so every
    field sits behind one lock and readers take a :class:`Snapshot`.
    """

    def __init__(self, key: Hashable, *, title: str, steps: Sequence[str] = ()):
        self.key = key
        self._lock = threading.Lock()
        self._title = title
        self._steps = list(steps)
        self._seconds: list[float | None] = [None] * len(self._steps)
        self._current = 0
        self._done: int | None = None
        self._total: int | None = None
        self._unit = ""
        self._detail: str | None = None
        self.started = time.monotonic()
        self._step_started = self.started
        self._finished = False
        self._cancelled = threading.Event()
        self._last_yield = float("-inf")

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def finished(self) -> bool:
        with self._lock:
            return self._finished

    def cancel(self) -> None:
        self._cancelled.set()

    def _checkpoint(self) -> None:
        """Stop a cancelled task here; otherwise let the server send (see the
        module docstring) at most every ``YIELD_EVERY_S``."""
        if self._cancelled.is_set():
            raise Cancelled(self.key)
        if _clock() - self._last_yield >= YIELD_EVERY_S:
            _sleep(YIELD_S)
            self._last_yield = _clock()

    def report(
        self,
        done: int | None = None,
        total: int | None = None,
        *,
        unit: str = "",
        detail: str | None = None,
    ) -> None:
        self._checkpoint()
        with self._lock:
            self._done = done
            self._total = total
            if unit:
                self._unit = unit
            if detail is not None:
                self._detail = detail

    def step_to(self, index: int, label: str | None = None) -> None:
        """Start step ``index``, finishing the ones before it.

        Never moves back: a run that joined a task another run was driving may
        ask for a step the other already reached.
        """
        self._checkpoint()
        now = time.monotonic()
        with self._lock:
            if label and 0 <= index < len(self._steps):
                self._steps[index] = label
            if index <= self._current:
                return
            for i in range(self._current, min(index, len(self._steps))):
                if self._seconds[i] is None:
                    self._seconds[i] = (
                        now - self._step_started if i == self._current else 0.0
                    )
            self._current = index
            self._step_started = now
            self._done = self._total = None
            self._unit = ""
            self._detail = None

    def finish(self, *, duration_key: Hashable | None = None) -> float:
        """Mark every step done; remember the duration under ``duration_key``."""
        now = time.monotonic()
        with self._lock:
            for i in range(len(self._steps)):
                if self._seconds[i] is None:
                    self._seconds[i] = (
                        now - self._step_started if i == self._current else 0.0
                    )
            self._current = len(self._steps)
            self._finished = True
        seconds = now - self.started
        if duration_key is not None:
            with _REGISTRY_LOCK:
                _DURATIONS[duration_key] = seconds
        return seconds

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(
                title=self._title,
                steps=tuple(self._steps),
                step_seconds=tuple(self._seconds),
                current=self._current,
                done=self._done,
                total=self._total,
                unit=self._unit,
                detail=self._detail,
                elapsed=time.monotonic() - self.started,
                finished=self._finished,
            )


_REGISTRY: dict[Hashable, Task] = {}
_DURATIONS: dict[Hashable, float] = {}
_REGISTRY_LOCK = threading.Lock()
_ACTIVE: contextvars.ContextVar[Task | None] = contextvars.ContextVar(
    "scanpath_progress_task", default=None
)


def begin(
    key: Hashable, *, title: str, steps: Sequence[str] = (), fresh: bool = False
) -> Task:
    """The task for ``key`` — the one already running, or a new one.

    Joining is what lets a rerun that interrupted a load keep showing that
    load's counts instead of starting from zero. A finished or cancelled task
    is never joined: its record is replaced. ``fresh=True`` replaces any
    existing record unconditionally, even one still mid-flight — for a caller
    with no stable identity to join across runs in the first place (e.g. a
    region card opened with no explicit task key).
    """
    with _REGISTRY_LOCK:
        task = None if fresh else _REGISTRY.get(key)
        if task is None or task.cancelled or task.finished:
            task = Task(key, title=title, steps=steps)
            _REGISTRY[key] = task
        return task


def activate(task: Task) -> contextvars.Token:
    return _ACTIVE.set(task)


def deactivate(token: contextvars.Token) -> None:
    _ACTIVE.reset(token)


def active() -> Task | None:
    return _ACTIVE.get()


@contextmanager
def task(key: Hashable, *, title: str, steps: Sequence[str] = ()) -> Iterator[Task]:
    """:func:`begin` + :func:`activate` for one block."""
    current = begin(key, title=title, steps=steps)
    token = activate(current)
    try:
        yield current
    finally:
        deactivate(token)


@contextmanager
def scope() -> Iterator[None]:
    """No active task inside, whatever an earlier run in this thread left."""
    token = _ACTIVE.set(None)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def report(
    done: int | None = None,
    total: int | None = None,
    *,
    unit: str = "",
    detail: str | None = None,
) -> None:
    """Record progress on the active task — a no-op without one."""
    current = _ACTIVE.get()
    if current is not None:
        current.report(done, total, unit=unit, detail=detail)


def step_to(index: int, label: str | None = None) -> None:
    """Move the active task to step ``index`` — a no-op without one."""
    current = _ACTIVE.get()
    if current is not None:
        current.step_to(index, label)


def cancel(key: Hashable) -> None:
    """Cancel ``key``'s task: its computing thread stops at its next checkpoint."""
    with _REGISTRY_LOCK:
        current = _REGISTRY.get(key)
    if current is not None:
        current.cancel()


def last_duration(key: Hashable) -> float | None:
    with _REGISTRY_LOCK:
        return _DURATIONS.get(key)
