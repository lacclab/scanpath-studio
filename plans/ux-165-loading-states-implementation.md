# UX-165 … UX-169 · Loading states — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every long wait in Scanpath Studio keeps the page whole, says what it
is doing (with a count or a step list and the elapsed time), and — where there
is a clear previous state — can be cancelled instantly.

**Architecture:** A Streamlit-free progress hook (`progress.py`) that loaders
and builders report into, and a Streamlit-side loading module (`loading.py`)
whose cards are drawn hidden by the script thread and revealed and refreshed by
a timer thread, exactly as `st.spinner`'s own timer works. Cancel is a real
button whose callback restores the previous choice; Streamlit's
`runner.fastReruns` starts the new run at once and drops the abandoned run's
output. The views render inside one reserved area, so a page skeleton can
stand in for them while a dataset loads.

**Tech Stack:** Python 3.11–3.14, Streamlit ≥ 1.64 (`st.empty`, keyed
containers, `st.spinner(show_time=)`, `add_script_run_ctx`), pandas 3, CSS
`:has()`. No new dependencies.

**Spec:** [`plans/ux-165-loading-states.md`](ux-165-loading-states.md) — read
it first; this plan argues from it. Tracking issue: **#241**.

## Global Constraints

- `from __future__ import annotations` at the top of every new Python file.
- No new dependencies. Icons as chrome come from `constants.ICONS`; in raw HTML
  use `constants.icon_html(concept)` (UX-138, `tests/test_icons.py`). Never a
  literal emoji or `:material/…:` in chrome.
- Lint with the pinned ruff: `uvx --from ruff==0.16.8 ruff check .` **and**
  `uvx --from ruff==0.16.8 ruff format .` before every commit (CI gates on both).
- Run tests in the worktree's own env: `uv run --extra test pytest …` (pandas 3,
  CI-grade). Never bare `python3`/`pytest` (miniforge pandas 2.3).
- Commit subjects cite the ID, e.g. `feat(ux): … (UX-165)`. **No
  `Co-Authored-By` trailer** — the repo's CLAUDE.md forbids it.
- `CHANGELOG.md` `[Unreleased]` in the two-tier shape: headline bullets
  (`- **Bold lead** (ID)`) per group, then `### Details` → `#### <Group>` with
  one short paragraph per item.
- Any app you start: `SCANPATH_STUDIO_PERSIST=0`, bound to `127.0.0.1`, on a
  free port other than 8501 and 8511.
- Delay before a card shows: **0.5 s** (`loading.DELAY_S`). Refresh once shown:
  **0.25 s** (`loading.REFRESH_S`).
- New session keys are underscore-prefixed internals (`_sps_*`): never in
  `session_keys.py`, never persisted by the recovery cache.
- Widget keys introduced: `sps_cancel_<card-key>`, `sps_try_again`. Container
  keys: `sps_view`, `sps_card_<card-key>`, `sps_cardbody_<card-key>`,
  `sps_cancelled_notice`.

## File map

| File | Change |
|---|---|
| `scanpath_studio/progress.py` | **New.** The hook: `Task`, `Snapshot`, `Cancelled`, `begin/activate/deactivate/task/report/step_to/cancel/last_duration/scope`. |
| `scanpath_studio/loading.py` | **New.** Markup helpers, plot sizes, `Cancel`, `Card`, `Page`, `card()`, `page()`, `release_page()`, `run_scope()`, `covered()`, `spinner()`. |
| `scanpath_studio/styles.py` | The card / skeleton / stage CSS; the pulsing spinner banner replaced by a calm pill. |
| `scanpath_studio/debug_log.py` | The log handler swallows Streamlit's control exceptions, so an abandoned run's cached build keeps its result. |
| `scanpath_studio/data.py` | `frame_cache` shares a build in flight between runs. |
| `scanpath_studio/datasets.py` | Progress reports in the PoTeC / MultiplEYE / OneStop readers; chunked, cancellable downloads. |
| `scanpath_studio/persistence.py` | Progress reports while restoring datasets. |
| `scanpath_studio/plots.py` | One `progress.report` per replay frame. |
| `scanpath_studio/app.py` | `main` inside `run_scope`; restore card; view area + page skeleton + dataset card; Cancel / Try again; download cards; spinners silenced under cards. |
| `scanpath_studio/tabs.py` | The plot stage; figure cards; animation card with count + Cancel; compare-B card + Cancel; Corpus measures card; in-frame placeholder; size recording. |
| `scanpath_studio/compare_source.py`, `utils.py` | Built-in spinners off where a card covers them. |
| `tests/test_progress.py`, `tests/test_loading_markup.py`, `tests/test_loading_runtime.py`, `tests/test_loading_css.py`, `tests/test_loading_app.py`, `tests/test_downloads.py` | **New** tests. |
| `tests/test_frame_cache.py`, `tests/test_debug_log.py`, `tests/test_dataset_support.py`, `tests/test_persistence.py` | Added tests. |
| `AGENTS.md`, `scanpath_studio/CLAUDE.md`, `CHANGELOG.md`, `docs/…`, `plans/ux-165-loading-states.md` | Docs. |

---

### Task 0: Set up the worktree and claim the work

**Files:** none changed.

- [ ] **Step 1: Confirm the branch and base**

Run: `git -C . branch --show-current && git log --oneline -3`
Expected: branch `claude/loading-state-ui-animations-85bdc2`; the spec commit
on top of `1b25285` (PERF-16). If `origin/main` has moved, merge it in first
(`git fetch origin && git merge origin/main`).

- [ ] **Step 2: Build the worktree env and prove it is CI-grade**

Run: `uv run --extra test python -c "import pandas, streamlit, sys; print(pandas.__version__, streamlit.__version__, sys.version.split()[0])"`
Expected: pandas `3.x`, streamlit `1.64.x` or later.

- [ ] **Step 3: Baseline the suites this plan touches**

Run: `uv run --extra test pytest tests/test_frame_cache.py tests/test_debug_log.py tests/test_empty_states.py -q -x`
Expected: all pass.

- [ ] **Step 4: Check for peers, then move #241 to In progress**

Run `ListAgents` (Claude tool). If a session is working in `tabs.py`'s plot
block or `app.main`, message it before editing. Then move the board card:

```bash
I=$(gh project item-list 5 --owner lacclab --format json --limit 500 --jq '.items[] | select(.content.number==241) | .id')
gh project item-edit --project-id PVT_kwDOBWtHfs4Bg-gS --id "$I" \
  --field-id PVTSSF_lADOBWtHfs4Bg-gSzhf7_0o --single-select-option-id 61d8ab45
```

---

### Task 1: The progress hook (UX-165)

**Files:**
- Create: `scanpath_studio/progress.py`
- Create: `tests/test_progress.py`
- Modify: `CHANGELOG.md` (headline stubs for all five IDs)

**Interfaces:**
- Produces:
  - `class Cancelled(BaseException)`
  - `@dataclass(frozen=True) class Snapshot: title: str; steps: tuple[str, ...]; step_seconds: tuple[float | None, ...]; current: int; done: int | None; total: int | None; unit: str; detail: str | None; elapsed: float; finished: bool`
  - `class Task` with `key`, `started`, `cancelled` (property), `finished` (property), `cancel()`, `report(done=None, total=None, *, unit="", detail=None)`, `step_to(index: int, label: str | None = None)`, `finish(*, duration_key=None) -> float`, `snapshot() -> Snapshot`
  - `begin(key, *, title: str, steps: Sequence[str] = ()) -> Task` — joins a running task under `key`, never a finished or cancelled one
  - `activate(task) -> contextvars.Token`, `deactivate(token) -> None`, `active() -> Task | None`
  - `task(key, *, title, steps=())` — context manager: `begin` + `activate`
  - `report(done=None, total=None, *, unit="", detail=None) -> None`, `step_to(index, label=None) -> None` — act on the active task; no-ops without one; raise `Cancelled` once cancelled
  - `cancel(key) -> None`, `last_duration(key) -> float | None`
  - `scope()` — context manager that clears the active task for one script run

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_progress.py
"""UX-165: the Streamlit-free progress hook (`scanpath_studio.progress`)."""

from __future__ import annotations

import threading

import pytest

from scanpath_studio import progress


def test_calls_without_an_active_task_do_nothing():
    progress.report(3, 10, unit="files")
    progress.step_to(1)
    assert progress.active() is None


def test_a_task_records_counts_and_moves_through_its_steps():
    with progress.task(("t", "steps"), title="Loading", steps=("Read", "Norm")) as task:
        progress.report(3, 10, unit="files")
        snap = task.snapshot()
        assert (snap.current, snap.done, snap.total, snap.unit) == (0, 3, 10, "files")
        progress.step_to(1, "Normalizing 5 rows")
        snap = task.snapshot()
        assert snap.current == 1
        assert snap.steps == ("Read", "Normalizing 5 rows")
        assert snap.done is None and snap.unit == ""
        assert snap.step_seconds[0] is not None and snap.step_seconds[1] is None


def test_step_to_never_moves_back():
    with progress.task(("t", "back"), title="x", steps=("a", "b", "c")) as task:
        progress.step_to(2)
        progress.step_to(1)
        assert task.snapshot().current == 2


def test_cancel_makes_the_next_checkpoint_raise():
    with progress.task(("t", "cancel"), title="x"):
        progress.cancel(("t", "cancel"))
        with pytest.raises(progress.Cancelled):
            progress.report(1, 2)
        with pytest.raises(progress.Cancelled):
            progress.step_to(1)


def test_cancelled_is_not_an_exception_so_broad_handlers_cannot_swallow_it():
    assert not issubclass(progress.Cancelled, Exception)
    assert issubclass(progress.Cancelled, BaseException)


def test_begin_joins_a_running_task_but_not_a_finished_or_cancelled_one():
    first = progress.begin(("t", "join"), title="x")
    assert progress.begin(("t", "join"), title="x") is first
    first.finish()
    second = progress.begin(("t", "join"), title="x")
    assert second is not first
    second.cancel()
    assert progress.begin(("t", "join"), title="x") is not second


def test_finish_records_the_duration_under_its_duration_key():
    task = progress.begin(("t", "dur"), title="x")
    seconds = task.finish(duration_key=("dataset", "Demo"))
    assert progress.last_duration(("dataset", "Demo")) == pytest.approx(seconds)
    assert task.snapshot().finished


def test_the_active_task_belongs_to_its_own_thread():
    seen = []
    with progress.task(("t", "thread"), title="x"):
        worker = threading.Thread(target=lambda: seen.append(progress.active()))
        worker.start()
        worker.join()
    assert seen == [None]


def test_snapshots_stay_consistent_while_another_thread_reports():
    task = progress.begin(("t", "race"), title="x")
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            i += 1
            task.report(i, i + 5)

    worker = threading.Thread(target=writer)
    worker.start()
    try:
        for _ in range(2000):
            snap = task.snapshot()
            assert snap.done is None or snap.done <= snap.total
    finally:
        stop.set()
        worker.join()


def test_scope_clears_a_task_left_active_by_an_earlier_run():
    token = progress.activate(progress.begin(("t", "stale"), title="x"))
    try:
        with progress.scope():
            assert progress.active() is None
    finally:
        progress.deactivate(token)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_progress.py -q`
Expected: FAIL — `ImportError: cannot import name 'progress'`.

- [ ] **Step 3: Write `progress.py`**

```python
# scanpath_studio/progress.py
"""UX-165: a Streamlit-free progress hook for slow work.

Loaders and figure builders call :func:`report` from inside their loops, and
the orchestrator calls :func:`step_to` between stages. With no task active both
return at once, so the headless API and the CLI see no change. With one active
— ``loading.card`` opens it — they update a thread-safe :class:`Task` that the
card's timer thread reads.

The two calls are also the **cancel checkpoint**: after :func:`cancel`, the next
call in the computing thread raises :class:`Cancelled`, so abandoned work stops
within one file, frame or chunk instead of running to the end of its step.

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
        if self._cancelled.is_set():
            raise Cancelled(self.key)

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


def begin(key: Hashable, *, title: str, steps: Sequence[str] = ()) -> Task:
    """The task for ``key`` — the one already running, or a new one.

    Joining is what lets a rerun that interrupted a load keep showing that
    load's counts instead of starting from zero. A finished or cancelled task
    is never joined: its record is replaced.
    """
    with _REGISTRY_LOCK:
        task = _REGISTRY.get(key)
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_progress.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Add the changelog headlines for all five IDs**

Under `## [Unreleased]`, add to `### Added`:

```markdown
- **A long wait says what the app is doing: a card with the step, a count, the elapsed time and a Cancel** (UX-165)
- **Cancel a dataset load, an animation build, Compare's second dataset or a download, and go back to where you were** (UX-168)
```

to `### Changed` (create the group if absent, keeping Keep-a-Changelog order Added → Changed → Fixed):

```markdown
- **A dataset that takes a while to open shows a skeleton of the page and its steps, not a lone banner** (UX-166)
- **Building an animation counts its frames, and the plot shows a placeholder until the browser has drawn it** (UX-169)
```

and to `### Fixed`:

```markdown
- **The plot-controls rail no longer looks cut off while a figure is being drawn** (UX-167)
```

Leave their `### Details` paragraphs for the tasks that land them (Task 12
writes them all).

- [ ] **Step 6: Lint, commit, push, and open a draft PR**

The draft PR makes the five IDs visible to other sessions' ID checks
(`gh pr diff <n> -- CHANGELOG.md`), per CLAUDE.md → *Tracking work*.

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/progress.py tests/test_progress.py CHANGELOG.md
git commit -m "feat(ux): a Streamlit-free progress hook for slow work (UX-165)"
git push
gh pr create --draft --base main --title "Loading states: keep the page whole, say what is happening, and cancel (UX-165 … UX-169)" --body "Draft — implements plans/ux-165-loading-states.md. Tracking: #241.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

### Task 2: Loading markup, plot sizes (UX-165)

**Files:**
- Create: `scanpath_studio/loading.py` (pure half)
- Create: `tests/test_loading_markup.py`

**Interfaces:**
- Consumes: `progress.Snapshot` (Task 1); `constants.SELECTOR_ROW_GRID`, `constants.icon_html`; `plots._fit_display_size`, `plots._CONTROLS_MARGIN_PX`, `plots._CONTROLS_SAFETY_PX`.
- Produces:
  - constants `DELAY_S = 0.5`, `REFRESH_S = 0.25`, `PLOT_SIZES_KEY = "_sps_plot_sizes"`, `VIEW_AREA_KEY = "sps_view"`, `PAGE_CARD_KEY = "page"`
  - `format_elapsed(seconds: float) -> str`, `format_count(done, total, unit: str) -> str`
  - `head_html(snap, *, last: float | None = None) -> str`, `detail_html(snap) -> str`, `steps_html(snap) -> str`, `bar_html(snap) -> str`, `size_box_html(width: int, height: int) -> str`
  - `skeleton_html(view: str, *, plot_height: int = 480) -> str` (`view` ∈ `"scanpath" | "corpus" | "data"`)
  - `estimate_plot_size(canvas_width, canvas_height, *, animation=False) -> tuple[int, int]` — `(width, iframe height)`
  - `record_plot_size(key: str, width: int, height: int) -> None`, `plot_size(key, canvas_width, canvas_height, *, animation=False) -> tuple[int, int]`, `recorded_plot_height(key: str, default: int) -> int`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_loading_markup.py
"""UX-165: the loading card's markup and the plot-size bookkeeping."""

from __future__ import annotations

from scanpath_studio import loading
from scanpath_studio.constants import SELECTOR_ROW_GRID
from scanpath_studio.progress import Snapshot


def _snap(**overrides) -> Snapshot:
    base = dict(
        title="Loading PoTeC",
        steps=("Reading files", "Normalizing", "Building the trial list"),
        step_seconds=(2.4, None, None),
        current=1,
        done=312,
        total=900,
        unit="files",
        detail=None,
        elapsed=4.2,
        finished=False,
    )
    base.update(overrides)
    return Snapshot(**base)


def test_elapsed_reads_naturally_at_every_scale():
    assert loading.format_elapsed(0.84) == "0.8 s"
    assert loading.format_elapsed(42.4) == "42 s"
    assert loading.format_elapsed(125) == "2 min 5 s"
    assert loading.format_elapsed(120) == "2 min"


def test_counts_name_their_unit_and_bytes_read_as_megabytes():
    assert loading.format_count(312, 900, "files") == "312 of 900 files"
    assert loading.format_count(1200, None, "rows") == "1,200 rows"
    assert loading.format_count(120_000_000, 450_000_000, "bytes") == "120 of 450 MB"
    assert loading.format_count(3_200_000, None, "bytes") == "3.2 MB so far"
    assert loading.format_count(None, None, "files") == ""


def test_the_head_carries_title_time_and_last_load_and_escapes_the_title():
    html = loading.head_html(_snap(title="Load <b>x</b>"), last=6.0)
    assert "Load &lt;b&gt;x&lt;/b&gt;" in html
    assert "4.2 s · last load 6.0 s" in html
    assert 'role="status"' in html


def test_the_detail_line_joins_step_detail_and_count():
    html = loading.detail_html(_snap(detail="archive"))
    assert "Normalizing · archive · 312 of 900 files" in html


def test_the_step_list_marks_done_current_and_todo():
    html = loading.steps_html(_snap())
    assert html.count("sps-step-done") == 1
    assert html.count("sps-step-now") == 1
    assert html.count("sps-step-todo") == 1
    assert "2.4 s" in html and "312 of 900 files" in html
    assert "check_circle" in html  # icon_html("step_done") ligature


def test_the_bar_is_determinate_only_with_a_total():
    assert 'aria-valuenow="35"' in loading.bar_html(_snap())
    assert "sps-bar-indeterminate" in loading.bar_html(_snap(total=None))


def test_the_size_box_holds_the_exact_iframe_height():
    html = loading.size_box_html(960, 702)
    assert "height:702px" in html and "max-width:960px" in html


def test_the_scanpath_skeleton_follows_the_selector_grid_and_plot_height():
    html = loading.skeleton_html("scanpath", plot_height=640)
    tracks = " ".join(f"{w}fr" for w in SELECTOR_ROW_GRID)
    assert f"grid-template-columns:{tracks}" in html
    assert "height:640px" in html
    assert "sps-sk-scanpath" in html
    assert "sps-sk-corpus" in loading.skeleton_html("corpus")
    assert "sps-sk-table" in loading.skeleton_html("data")


def test_an_animation_estimate_is_taller_than_the_static_one():
    static_w, static_h = loading.estimate_plot_size(1680, 1050)
    anim_w, anim_h = loading.estimate_plot_size(1680, 1050, animation=True)
    assert static_w == anim_w
    assert anim_h > static_h > 0


def test_plot_size_prefers_the_recorded_size(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(loading, "_session", lambda: store)
    assert loading.plot_size("single", 1680, 1050) == loading.estimate_plot_size(
        1680, 1050
    )
    loading.record_plot_size("single", 900, 612)
    assert loading.plot_size("single", 1680, 1050) == (900, 612)
    assert loading.recorded_plot_height("single", 480) == 612
    assert loading.recorded_plot_height("compare", 480) == 480
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_loading_markup.py -q`
Expected: FAIL — `ImportError: cannot import name 'loading'`.

- [ ] **Step 3: Write the pure half of `loading.py`**

```python
# scanpath_studio/loading.py
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_loading_markup.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/loading.py tests/test_loading_markup.py
git commit -m "feat(ux): the loading card's markup and plot-size bookkeeping (UX-165)"
```

---

### Task 3: Loading cards at runtime (UX-165)

**Files:**
- Modify: `scanpath_studio/loading.py` (append the runtime half)
- Create: `tests/test_loading_runtime.py`

**Interfaces:**
- Consumes: Task 1 (`progress.*`), Task 2 (markup helpers, constants).
- Produces:
  - `@dataclass(frozen=True) class Cancel: label: str; on_click: Callable[..., None]; args: tuple = ()`
  - `session_id() -> str`
  - `class Card(slot, *, key, title, steps=(), step_list=False, cancel=None, size=None, skeleton=None, task_key=None, duration_key=None, reveal_class="sps-reveal")` with `open(*, reveal_now=False) -> Card`, `step(index, label=None)`, `finish()`, `close(*, keep=False)`, properties `steps`, `revealed`, `task`, attribute `is_open`
  - `class Page(slot, *, view, plot_height=480)` with `open_card(*, title, steps=(), cancel=None, task_key=None, duration_key=None, reveal_now=False) -> Card`, `release() -> bool`, attribute `card`
  - `page(slot, *, view, plot_height=480) -> Page`, `release_page() -> bool`
  - `card(slot, *, key, title, steps=(), step_list=False, cancel=None, size=None, task_key=None, duration_key=None)` — context manager yielding the open `Card`; releases the page first and reveals at once if the page was showing
  - `run_scope()` — context manager: fresh per-run state, `progress.scope()`, stops every timer, swallows `progress.Cancelled`
  - `covered() -> bool`, `spinner(text: str)` — `st.spinner(text, show_time=True)` unless a card is open

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_loading_runtime.py
"""UX-165: loading cards at runtime — hidden, revealed, cancelled, released."""

from __future__ import annotations

import threading

import pytest

from scanpath_studio import loading, progress

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _frozen_card_script():
    import streamlit as st

    from scanpath_studio import loading

    def on_cancel():
        st.session_state["cancelled"] = True

    with loading.run_scope():
        slot = st.empty()
        loading.Card(
            slot,
            key="t",
            title="Building the thing",
            steps=("One", "Two"),
            step_list=True,
            cancel=loading.Cancel("Stop it", on_cancel),
        ).open()
        st.stop()


def test_a_revealed_card_shows_its_steps_and_a_working_cancel(monkeypatch):
    monkeypatch.setattr(loading, "DELAY_S", 0)
    at = AppTest.from_function(_frozen_card_script).run()
    assert not at.exception
    text = _markdown(at)
    assert "Building the thing" in text and "sps-steps" in text
    assert "sps-reveal" in text
    cancel = at.button(key="sps_cancel_t")
    assert cancel.label == "Stop it"
    cancel.click().run()
    assert at.session_state["cancelled"] is True


def _fast_card_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        slot = st.empty()
        with loading.card(slot, key="fast", title="Quick", size=(400, 300)) as opened:
            st.session_state["covered_inside"] = loading.covered()
        st.session_state["covered_after"] = loading.covered()
        st.session_state["was_revealed"] = opened.revealed
        st.write("after")


def test_a_fast_card_never_shows_and_leaves_nothing_behind():
    at = AppTest.from_function(_fast_card_script).run()
    assert not at.exception
    assert "sps-card-head" not in _markdown(at)
    assert "sps-size-box" not in _markdown(at)
    assert not [b for b in at.button if b.key and b.key.startswith("sps_cancel_")]
    assert at.session_state["covered_inside"] is True
    assert at.session_state["covered_after"] is False
    assert at.session_state["was_revealed"] is False


def _leaky_script():
    import streamlit as st

    from scanpath_studio import loading

    loading.DELAY_S = 30  # the test restores it
    with loading.run_scope():
        loading.Card(st.empty(), key="leak", title="Never closed").open()


def test_run_scope_stops_every_timer_a_run_leaves_open():
    before = {t.ident for t in threading.enumerate()}
    try:
        AppTest.from_function(_leaky_script).run()
    finally:
        loading.DELAY_S = 0.5
    leaked = [
        t
        for t in threading.enumerate()
        if t.ident not in before
        and t.name == "scanpath-loading-ticker"
        and t.is_alive()
    ]
    assert not leaked


def _cancelled_script():
    from scanpath_studio import loading, progress

    with loading.run_scope():
        raise progress.Cancelled("abandoned")


def test_run_scope_ends_a_cancelled_run_quietly():
    at = AppTest.from_function(_cancelled_script).run()
    assert not at.exception


def _page_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        area = st.container(key=loading.VIEW_AREA_KEY)
        first = area.empty()
        page = loading.page(first, view="scanpath", plot_height=300)
        dataset = page.open_card(
            title="Loading Demo", steps=("Reading files",), reveal_now=True
        )
        dataset.finish()
        dataset.close(keep=True)
        st.session_state["page_text_before"] = True
        with area:
            with loading.card(st.empty(), key="plot", title="Drawing") as plot:
                st.session_state["plot_inherited_reveal"] = plot.revealed
                st.stop()


def test_a_region_card_releases_the_page_and_inherits_its_reveal(monkeypatch):
    monkeypatch.setattr(loading, "DELAY_S", 5)
    at = AppTest.from_function(_page_script).run()
    assert not at.exception
    text = _markdown(at)
    assert "sps-sk-scanpath" not in text  # the page skeleton is gone
    assert "Drawing" in text  # the plot card took over, already revealed
    assert at.session_state["plot_inherited_reveal"] is True


def test_spinner_is_silent_under_a_card(monkeypatch):
    class _Run:
        cards = [type("C", (), {"is_open": True})()]
        page = None

    monkeypatch.setattr(
        loading, "_RUN", type("V", (), {"get": staticmethod(lambda: _Run())})()
    )
    assert loading.covered() is True
    assert loading.spinner("x").__class__.__name__ == "nullcontext"


def _task_script():
    import streamlit as st

    from scanpath_studio import loading, progress

    with loading.run_scope():
        with loading.card(st.empty(), key="p", title="t", task_key=("k", "run")):
            st.session_state["active_inside"] = progress.active() is not None
        st.session_state["active_after"] = progress.active() is not None


def test_a_card_activates_its_task_and_finishes_it_on_a_clean_exit():
    at = AppTest.from_function(_task_script).run()
    assert not at.exception
    assert at.session_state["active_inside"] is True
    assert at.session_state["active_after"] is False
    assert progress._REGISTRY[("k", "run")].finished is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_loading_runtime.py -q`
Expected: FAIL — `AttributeError: module 'scanpath_studio.loading' has no attribute 'Card'`.

- [ ] **Step 3: Append the runtime half to `loading.py`**

Add to the imports at the top of `loading.py` (ruff keeps them sorted):

```python
import contextlib
import contextvars
import threading
from collections.abc import Callable, Hashable, Iterator, Sequence
from dataclasses import dataclass, field

from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from scanpath_studio import progress
```

Then append:

```python
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
    cards: list = field(default_factory=list)
    page: Page | None = None


_RUN: contextvars.ContextVar[_RunState | None] = contextvars.ContextVar(
    "scanpath_loading_run", default=None
)


def _run() -> _RunState:
    state = _RUN.get()
    if state is None:
        state = _RunState()
        _RUN.set(state)
    return state


class _Ticker(threading.Thread):
    """The timer thread: wait out the delay, reveal, then refresh.

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
    ):
        super().__init__(daemon=True, name="scanpath-loading-ticker")
        self._delay = delay
        self._interval = interval
        self._on_reveal = on_reveal
        self._on_tick = on_tick
        self._halt = threading.Event()

    def run(self) -> None:
        if self._halt.wait(self._delay):
            return
        try:
            self._on_reveal()
            while not self._halt.wait(self._interval):
                self._on_tick()
        except Exception:
            # A placeholder whose run has ended: nothing left to update.
            return

    def halt(self) -> None:
        self._halt.set()


class Card:
    """One loading card in one slot (see the module docstring)."""

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
    ):
        self._slot = slot
        self.key = key
        self._title = title
        self._steps = tuple(steps)
        self._step_list = step_list
        self._cancel = cancel
        self._size = size
        self._skeleton = skeleton
        self._task_key = (
            task_key if task_key is not None else ("card", session_id(), key)
        )
        self._duration_key = duration_key
        self._reveal_class = reveal_class
        self._task: progress.Task | None = None
        self._token: contextvars.Token | None = None
        self._ticker: _Ticker | None = None
        self._revealed = False
        self.is_open = False
        self._skeleton_ph = self._head = self._detail = self._bar = self._reveal = None

    @property
    def steps(self) -> tuple[str, ...]:
        return self._steps

    @property
    def revealed(self) -> bool:
        return self._revealed

    @property
    def task(self) -> progress.Task | None:
        return self._task

    def open(self, *, reveal_now: bool = False) -> Card:
        """Draw the card hidden — its size box shows at once — and arm the timer."""
        self._task = progress.begin(
            self._task_key, title=self._title, steps=self._steps
        )
        self._token = progress.activate(self._task)
        box = self._slot.container(key=f"sps_card_{self.key}")
        if self._size is not None:
            box.markdown(size_box_html(*self._size), unsafe_allow_html=True)
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
        if reveal_now or DELAY_S <= 0:
            self._show()
            if DELAY_S > 0:
                self._arm(delay=REFRESH_S, revealed=True)
        else:
            self._arm(delay=DELAY_S, revealed=False)
        return self

    def _paint(self) -> None:
        snap = self._task.snapshot()
        last = (
            progress.last_duration(self._duration_key)
            if self._duration_key is not None
            else None
        )
        self._head.markdown(head_html(snap, last=last), unsafe_allow_html=True)
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
        self._revealed = True

    def _arm(self, *, delay: float, revealed: bool) -> None:
        ticker = _Ticker(
            delay=delay,
            interval=REFRESH_S,
            on_reveal=self._paint if revealed else self._show,
            on_tick=self._paint,
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
        # nothing else would repaint a shown card.
        if self._revealed and self._ticker is None:
            self._paint()

    def finish(self) -> None:
        if self._task is not None:
            self._task.finish(duration_key=self._duration_key)

    def close(self, *, keep: bool = False) -> None:
        """Stop the timer and take the card down — or, with ``keep``, leave it
        showing every step done (the page card, until its page is released)."""
        if not self.is_open:
            return
        self._halt()
        if self._token is not None:
            progress.deactivate(self._token)
            self._token = None
        self.is_open = False
        if keep:
            if self._revealed:
                self._paint()
        else:
            self._slot.empty()


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
        )
        return self.card.open(reveal_now=reveal_now)

    def release(self) -> bool:
        """Take the skeleton down; say whether it was showing."""
        if self._released:
            return False
        self._released = True
        revealed = bool(self.card is not None and self.card.revealed)
        if self.card is not None and self.card.is_open:
            self.card.close(keep=True)
        self._slot.empty()
        state = _RUN.get()
        if state is not None and state.page is self:
            state.page = None
        return revealed


def page(slot, *, view: str, plot_height: int = 480) -> Page:
    """Reserve ``slot`` as this run's page (see :class:`Page`)."""
    return Page(slot, view=view, plot_height=plot_height)


def release_page() -> bool:
    """Release this run's page, if any; say whether it was showing."""
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
) -> Iterator[Card]:
    """A region card for one ``with`` block.

    Opening one releases the page skeleton: the view has drawn its controls by
    the time it reaches its first slow region. When the skeleton was showing,
    the card shows at once too, so the wait reads as one continuous state.
    """
    page_was_showing = release_page()
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
    )
    region.open(reveal_now=page_was_showing)
    try:
        yield region
        region.finish()
    finally:
        region.close()


@contextlib.contextmanager
def run_scope() -> Iterator[None]:
    """Wrap one script run: fresh state in, every timer stopped out.

    It also ends quietly a run whose work was cancelled: only an abandoned run
    ever computes a cancelled task (`progress.begin` never joins one), so its
    page is gone and Streamlit drops whatever it sends.
    """
    token = _RUN.set(_RunState())
    try:
        with progress.scope():
            yield
    except progress.Cancelled:
        pass
    finally:
        state = _RUN.get()
        for opened in list(state.cards if state is not None else ()):
            opened._halt()
        _RUN.reset(token)


def covered() -> bool:
    """Is a card open in this run?"""
    state = _RUN.get()
    return bool(state is not None and any(c.is_open for c in state.cards))


def spinner(text: str):
    """``st.spinner`` with the elapsed time — silent while a card covers it."""
    if covered():
        return contextlib.nullcontext()
    return st.spinner(text, show_time=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_loading_runtime.py tests/test_loading_markup.py tests/test_progress.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/loading.py tests/test_loading_runtime.py
git commit -m "feat(ux): loading cards — hidden, revealed by a timer, cancellable (UX-165)"
```

---

### Task 4: The loading CSS; calm spinners (UX-165)

**Files:**
- Modify: `scanpath_studio/styles.py:202-241` (replace the "Emphasised loading spinner" block) and append the UX-165 block after it
- Create: `tests/test_loading_css.py`

**Interfaces:**
- Consumes: the class names and keys Tasks 2–3 emit: `.sps-reveal`, `.sps-reveal-page`, `[class*="st-key-sps_card_"]`, `[class*="st-key-sps_cardbody_"]`, `.st-key-sps_card_page`, `.st-key-sps_view`, `.sps-size-box`, `.sps-sk*`, `.sps-ring`, `.sps-steps`, `.sps-bar*`, `.st-key-tour_grp_plot`.
- Produces: nothing new in Python.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_loading_css.py
"""UX-165: the loading states' CSS, and the retired spinner banner."""

from __future__ import annotations

from scanpath_studio.styles import get_app_css

CSS = get_app_css()


def test_the_pulsing_spinner_banner_is_gone():
    assert "sps-spinner-pulse" not in CSS
    assert "Emphasised loading spinner" not in CSS


def test_a_card_body_is_hidden_until_revealed():
    assert '[class*="st-key-sps_cardbody_"] { display: none !important; }' in CSS
    assert (
        '[class*="st-key-sps_card_"]:has(.sps-reveal) [class*="st-key-sps_cardbody_"]'
        in CSS
    )


def test_the_page_skeleton_hides_the_rest_of_the_view_area():
    assert ".st-key-sps_view:has(.sps-reveal-page) > :not(:first-child)" in CSS


def test_the_plot_area_is_a_stage_with_two_stacked_children():
    assert ".st-key-tour_grp_plot { display: grid !important;" in CSS
    assert ".st-key-tour_grp_plot > :nth-child(-n + 2) { grid-area: 1 / 1; }" in CSS


def test_spinners_hide_while_a_card_shows_and_motion_can_be_reduced():
    assert '.stApp:has(.sps-reveal) div[data-testid="stSpinner"]' in CSS
    assert "prefers-reduced-motion: reduce" in CSS
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_loading_css.py -q`
Expected: FAIL (banner still present; new rules absent).

- [ ] **Step 3: Replace the banner block**

In `styles.py`, delete the whole block that starts
`    /* === Emphasised loading spinner ====` and ends with the closing `}` of
`@keyframes sps-spinner-pulse` (lines 202–241 on `1b25285`). Put this in its
place:

```css
    /* === Streamlit's spinners (UX-165) ======================================
       The cache_data spinners and st.spinner — calm and inline now. They used
       to be a pulsing blue banner; the long waits have loading cards
       (loading.py) since UX-165, and what is left is short enough that a
       banner shouted louder than the wait deserved. */
    div[data-testid="stSpinner"] {
        width: fit-content;
        padding: 0.35rem 0.75rem !important;
        margin: 0.3rem 0 !important;
        border: 1px solid var(--sps-border);
        border-radius: 999px;
        background: var(--sps-page-bg);
    }
    div[data-testid="stSpinner"] p { font-size: 0.9rem; margin: 0; }

    /* === UX-165 · loading states =============================================
       One card for every long wait (loading.py): hidden for its first
       loading.DELAY_S, then revealed by a timer thread writing `.sps-reveal`
       into it. A region card sits over a size box that holds its area at the
       height the content will take; the page card sits over a skeleton of the
       view. Nothing here animates for readers who ask for reduced motion. */
    [class*="st-key-sps_cardbody_"] { display: none !important; }
    [class*="st-key-sps_card_"]:has(.sps-reveal) [class*="st-key-sps_cardbody_"] {
        display: flex !important;
        flex-direction: column;
        gap: 0.4rem !important;
        width: min(24rem, 100%);
        box-sizing: border-box;
        padding: 0.8rem 1rem 0.75rem;
        border: 1px solid var(--sps-border);
        border-radius: 12px;
        background: var(--sps-page-bg);
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
    }
    [class*="st-key-sps_card_"]:not(.st-key-sps_card_page) {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr);
    }
    [class*="st-key-sps_card_"]:not(.st-key-sps_card_page) > * { grid-area: 1 / 1; }
    [class*="st-key-sps_card_"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-sps_cardbody_"]) {
        align-self: center;
        justify-self: center;
        z-index: 2;
    }
    .sps-size-box { width: 100%; pointer-events: none; }
    [class*="st-key-sps_card_"]:has(.sps-reveal) .sps-size-box {
        border-radius: 8px;
        background:
            linear-gradient(rgba(128, 128, 128, 0.10), rgba(128, 128, 128, 0.10)),
            color-mix(in srgb, var(--sps-page-bg) 60%, transparent);
        animation: sps-sk-pulse 1.6s ease-in-out infinite;
    }
    .sps-card-head { display: flex; align-items: center; gap: 0.55rem; }
    .sps-card-title { font-weight: 600; flex: 1; min-width: 0; }
    .sps-card-time {
        font-size: 0.8rem; opacity: 0.7; white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }
    .sps-card-detail, .sps-step-count, .sps-step-time {
        font-size: 0.85rem; opacity: 0.8; font-variant-numeric: tabular-nums;
    }
    .sps-ring {
        display: inline-block; flex: none;
        width: 0.95rem; height: 0.95rem; box-sizing: border-box;
        border-radius: 50%;
        border: 2px solid var(--sps-accent-border);
        border-top-color: var(--sps-accent);
        animation: sps-spin 0.8s linear infinite;
    }
    .sps-steps {
        list-style: none; margin: 0; padding: 0;
        display: flex; flex-direction: column; gap: 0.3rem;
    }
    .sps-step { display: flex; align-items: center; gap: 0.5rem; font-size: 0.88rem; margin: 0 !important; }
    .sps-step .sps-icon { font-size: 1rem; }
    .sps-step-done .sps-icon { color: #2e9d5b; }
    .sps-step-todo { opacity: 0.5; }
    .sps-step-label { flex: 1; min-width: 0; }
    .sps-bar { height: 4px; border-radius: 2px; overflow: hidden; background: var(--sps-accent-soft); }
    .sps-bar > span { display: block; height: 100%; background: var(--sps-accent); transition: width 0.25s ease; }
    .sps-bar-indeterminate > span { width: 35%; animation: sps-slide 1.3s ease-in-out infinite; }
    /* The page card: a skeleton of the view with the card over it. While it
       shows, everything else in the view's area — the previous page, or the
       new one being laid out underneath — stays hidden. */
    .st-key-sps_view:has(.sps-reveal-page) > :not(:first-child) { display: none !important; }
    .st-key-sps_card_page { display: grid !important; grid-template-columns: minmax(0, 1fr); }
    .st-key-sps_card_page > * { grid-area: 1 / 1; }
    .st-key-sps_card_page > [data-testid="stLayoutWrapper"]:has(> .st-key-sps_cardbody_page) {
        align-self: start; justify-self: center; margin-top: 7rem;
    }
    .st-key-sps_card_page:has(.sps-sk-scanpath) > [data-testid="stLayoutWrapper"]:has(> .st-key-sps_cardbody_page) {
        justify-self: start; margin-left: max(0px, calc(40% - 12rem));
    }
    .sps-page-skeleton { pointer-events: none; }
    .sps-sk {
        border-radius: 0.5rem; background: rgba(128, 128, 128, 0.12);
        animation: sps-sk-pulse 1.6s ease-in-out infinite;
    }
    .sps-sk-scanpath { display: grid; grid-template-columns: 4fr 1fr; gap: 3rem; }
    .sps-sk-main { display: flex; flex-direction: column; gap: 0.7rem; min-width: 0; }
    .sps-sk-selectors { display: grid; gap: 1rem; }
    .sps-sk-field { height: 2.5rem; }
    .sps-sk-chips { display: flex; gap: 0.45rem; flex-wrap: wrap; }
    .sps-sk-chip { width: 7.5rem; height: 1.7rem; border-radius: 999px; }
    .sps-sk-rail {
        display: flex; flex-direction: column; gap: 0.5rem;
        padding-left: 1rem; border-left: 1px solid var(--sps-border);
    }
    .sps-sk-row { height: 2.3rem; }
    .sps-sk-corpus { display: flex; flex-direction: column; gap: 1rem; }
    .sps-sk-tabs { height: 2.4rem; width: 60%; }
    .sps-sk-chart { height: 22rem; }
    .sps-sk-table { display: flex; flex-direction: column; gap: 0.4rem; }
    .sps-sk-table .sps-sk-row { height: 2rem; }
    /* UX-167 — the Scanpath plot area is a stage: its first child (the loading
       card) and its second (the figure) share one cell, so a card can open over
       a figure already on screen without moving it. Notes written after the
       figure flow into the rows below. */
    .st-key-tour_grp_plot { display: grid !important; grid-template-columns: minmax(0, 1fr); }
    .st-key-tour_grp_plot > :nth-child(-n + 2) { grid-area: 1 / 1; }
    .st-key-tour_grp_plot > :first-child { z-index: 3; }
    /* A card already says what the app is waiting on. */
    .stApp:has(.sps-reveal) div[data-testid="stSpinner"] { display: none !important; }
    @keyframes sps-spin { to { transform: rotate(360deg); } }
    @keyframes sps-sk-pulse { 50% { opacity: 0.55; } }
    @keyframes sps-slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(290%); } }
    @media (prefers-reduced-motion: reduce) {
        .sps-ring, .sps-sk, .sps-bar-indeterminate > span,
        [class*="st-key-sps_card_"]:has(.sps-reveal) .sps-size-box { animation: none !important; }
    }
```

- [ ] **Step 4: Elapsed time on the long spinners that remain**

These waits keep a plain spinner (they are panels, not whole regions), so they
get the spinner's own elapsed-time readout. Add `show_time=True` to each
decorator, keeping its message:

| File:line (`1b25285`) | Function | Decorator after |
|---|---|---|
| `tabs.py:7231` | `_c_sentence_measures` | `@st.cache_data(show_spinner="Computing sentence measures…", show_time=True)` |
| `tabs.py:9196` | `_build_stimuli_table_cached` | `@st.cache_data(show_spinner="Building stimuli list…", show_time=True)` |
| `tabs.py:9350` | `_dataset_statistics` | `@st.cache_data(show_spinner="Computing dataset statistics…", show_time=True)` |
| `tabs.py:11442` | `_c_derived_tables` | `@st.cache_data(show_spinner="Building the derived analysis tables…", show_time=True)` |
| `app.py:3260`, `app.py:3280` | `_read_uploaded_table_cached`, `_read_uploaded_tables_cached` | `@st.cache_data(show_spinner="Reading uploaded data…", show_time=True)` |

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_loading_css.py tests/test_theme.py tests/test_raw_gaze_style.py -q`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/styles.py scanpath_studio/tabs.py scanpath_studio/app.py tests/test_loading_css.py
git commit -m "feat(ux): loading-state CSS, and calm spinners instead of a pulsing banner (UX-165)"
```

---

### Task 5: Work survives a rerun, and loaders report progress (UX-166)

**Files:**
- Modify: `scanpath_studio/debug_log.py:179-203` (`_SessionStateHandler.emit`)
- Modify: `scanpath_studio/data.py:132-168` (`frame_cache`) + new `_shared_build`
- Modify: `scanpath_studio/datasets.py` (`_potec_fixations`, `_multipleye_fixations`, `onestop_raw_frames`)
- Modify: `scanpath_studio/persistence.py:409-418` (`restore_state`'s dataset loop)
- Modify: `scanpath_studio/app.py:2806-2835` (`_normalize_pair` / `_with_spinner`)
- Test: `tests/test_debug_log.py`, `tests/test_frame_cache.py`, `tests/test_dataset_support.py`, `tests/test_persistence.py`

**Interfaces:**
- Consumes: `progress.report`, `progress.task` (Task 1); `loading.spinner` (Task 3).
- Produces: `data._shared_build(ident: tuple, build: Callable[[], Any]) -> Any`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_debug_log.py`:

```python
def test_an_abandoned_runs_stop_does_not_escape_the_log_handler(monkeypatch):
    """UX-166: an abandoned run's session state raises StopException on any
    access. Escaping `emit`, it threw away the result of every cached build
    that logs through `timed()`."""
    import logging

    from streamlit.runtime.scriptrunner import StopException

    def _stopped():
        raise StopException()

    monkeypatch.setattr(debug_log, "_buffer", _stopped)
    record = logging.LogRecord(
        "scanpath_studio", logging.INFO, __file__, 1, "x", None, None
    )
    debug_log._SessionStateHandler().emit(record)  # must not raise
```

Append to `tests/test_frame_cache.py`:

```python
import threading
import time

from scanpath_studio.data import _shared_build


class TestSharedBuild:
    """UX-166: a rerun joins a build already in flight instead of starting one."""

    def test_two_callers_share_one_build(self):
        calls = []
        results = []

        def build():
            calls.append(1)
            time.sleep(0.2)
            return object()

        workers = [
            threading.Thread(
                target=lambda: results.append(_shared_build(("s", 1), build))
            )
            for _ in range(2)
        ]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        assert len(calls) == 1
        assert results[0] is results[1]

    def test_a_failed_owner_leaves_the_waiter_to_build_it_itself(self):
        started = threading.Event()
        calls = []

        def failing():
            calls.append("owner")
            started.set()
            time.sleep(0.1)
            raise RuntimeError("cancelled")

        def succeeding():
            calls.append("waiter")
            return "ok"

        errors = []

        def owner():
            try:
                _shared_build(("s", 2), failing)
            except RuntimeError as exc:
                errors.append(exc)

        t = threading.Thread(target=owner)
        t.start()
        started.wait()
        assert _shared_build(("s", 2), succeeding) == "ok"
        t.join()
        assert calls == ["owner", "waiter"] and errors
```

Append to `tests/test_dataset_support.py` (next to the `potec_root` fixture's
tests):

```python
def test_potec_reports_each_fixation_file(potec_root):
    from scanpath_studio import progress
    from scanpath_studio.datasets import potec_raw_frames

    with progress.task(("t", "potec"), title="Loading PoTeC") as task:
        potec_raw_frames(potec_root, texts=["b0"])
    snap = task.snapshot()
    assert (snap.done, snap.total, snap.unit) == (2, 2, "files")
```

Append to `tests/test_persistence.py` (it already imports `save_state`,
`restore_state` and defines `_dataset()`):

```python
def test_restoring_datasets_reports_each_one(tmp_path):
    """UX-166: the restore card counts datasets as they are read back."""
    from scanpath_studio import progress

    assert save_state({"_datasets": {"My corpus": _dataset()}}, tmp_path)
    with progress.task(("t", "restore"), title="Restoring") as task:
        assert restore_state({}, tmp_path)
    snap = task.snapshot()
    assert (snap.done, snap.total, snap.unit) == (1, 1, "datasets")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_debug_log.py tests/test_frame_cache.py tests/test_dataset_support.py -q -k "abandoned or SharedBuild or reports_each"`
Expected: FAIL — `StopException` escapes; `ImportError: _shared_build`; `snap.done is None`.

- [ ] **Step 3: Make the log handler swallow Streamlit's control exceptions**

In `debug_log.py`, add to the imports:

```python
from streamlit.runtime.scriptrunner import RerunException, StopException
```

and in `_SessionStateHandler.emit`, change the final handler from
`except Exception:  # pragma: no cover - logging must never crash callers` to:

```python
        except (Exception, StopException, RerunException):
            # UX-166: an abandoned run's session state raises StopException on
            # any access. Escaping here, it threw away the finished result of
            # every cached build that logs through `timed()` — the log line comes
            # after the value is computed. The run still stops, at its next
            # yield point; logging must never crash its caller.
            pass
```

- [ ] **Step 4: Share a build in flight in `frame_cache`**

In `data.py`, make sure `from dataclasses import dataclass, field` and
`from typing import Any` are imported (add what is missing), then add above
`frame_cache`:

```python
@dataclass
class _InFlight:
    done: threading.Event = field(default_factory=threading.Event)
    value: Any = None
    ok: bool = False


#: UX-166: builds in progress, so a rerun that asks for the same frame waits
#: for the one already running instead of starting a second. A click during a
#: long load abandons the running script and starts a new one at once
#: (`runner.fastReruns`); without this the new run normalized the corpus again
#: beside the first. `st.cache_data` has the same guarantee through its own
#: per-key lock.
_INFLIGHT: dict[tuple, _InFlight] = {}
_INFLIGHT_LOCK = threading.Lock()


def _shared_build(ident: tuple, build):
    """``build()``, run once for everyone asking for ``ident`` at the same time.

    A caller that finds a build running waits for it. If that build fails — or
    was cancelled (`progress.Cancelled`) — the waiter builds it itself.
    """
    while True:
        with _INFLIGHT_LOCK:
            entry = _INFLIGHT.get(ident)
            owner = entry is None
            if owner:
                entry = _InFlight()
                _INFLIGHT[ident] = entry
        if owner:
            try:
                entry.value = build()
                entry.ok = True
                return entry.value
            finally:
                with _INFLIGHT_LOCK:
                    _INFLIGHT.pop(ident, None)
                entry.done.set()
        entry.done.wait()
        if entry.ok:
            return entry.value
```

and in `frame_cache`, replace `    value = build()` with:

```python
    # UX-166: shared with a build already running for this session, slot and key.
    value = _shared_build((id(store), slot, key), build)
```

- [ ] **Step 5: Move the normalization spinner outside the cache**

In `app.py`'s `_normalize_pair`, replace the `notice = st.spinner(...)` +
`return frame_cache("normalized_pair", cache_key, lambda: _with_spinner(notice,
_normalize_pair_uncached, …))` block with:

```python
    # PERF-6: the spinner says how much data is being normalized, because on a
    # real corpus this is a ~20 s wait and "Normalizing data…" gives no sense of
    # whether that is expected. UX-166 moved it *outside* the cache: a spinner's
    # exit is a yield point, and inside `build` an abandoned run raised there
    # and threw the finished normalization away. `st.spinner` shows only after
    # 0.5 s, so a cache hit still never flashes it, and `loading.spinner` stays
    # silent under the dataset card, which lists normalization as a step.
    with loading.spinner(
        f"Normalizing {len(words_df):,} word rows and {len(fixations_df):,} fixations…"
    ):
        return frame_cache(
            "normalized_pair",
            cache_key,
            lambda: _normalize_pair_uncached(
                words_df,
                word_schema,
                fixations_df,
                fix_schema,
                cache_key,
                _keep_words=keep_words,
                _keep_fix=keep_fix,
            ),
        )
```

Delete `_with_spinner` (its only caller is gone; `grep -n "_with_spinner" -r
scanpath_studio tests` must print nothing afterwards). Add
`from scanpath_studio import loading, progress` to `app.py`'s imports.

- [ ] **Step 6: Report progress from the loaders**

In `datasets.py`, add `from . import progress` to the local imports. In
`_potec_fixations`, replace the loop from `    frames = []` through
`            frames.append(fixations)` with:

```python
    # UX-166: gather the files first, so the card can say "312 of 900 files".
    jobs: list[tuple[Path, pd.DataFrame]] = []
    for text_id in texts:
        char_boxes = _read_potec_ias(root, text_id)
        char_x = (char_boxes["start_x"] + char_boxes["end_x"]) / 2.0
        char_y = (char_boxes["start_y"] + char_boxes["end_y"]) / 2.0
        centers = pd.DataFrame(
            {"aoi": char_boxes["aoi"], "x": char_x, "y": char_y}
        ).drop_duplicates("aoi")
        for path in sorted((base / source).glob(f"reader*_{text_id}_{suffix}.tsv")):
            reader_id = path.stem.removeprefix("reader").split("_")[0]
            if reader_set is not None and reader_id not in reader_set:
                continue
            jobs.append((path, centers))
    frames = []
    for index, (path, centers) in enumerate(jobs, start=1):
        fixations = _read_potec_tsv(path)
        frames.append(fixations.merge(centers, on="aoi", how="left"))
        progress.report(index, len(jobs), unit="files")
```

In `_multipleye_fixations`, replace the first loop (from `    frames = []`
through the first `frames.append(stamped)`) with:

```python
    reading = [
        path
        for session_dir in sorted(p for p in base.iterdir() if p.is_dir())
        if session_filter is None or session_dir.name in session_filter
        for path in sorted(session_dir.glob(f"*_{suffix}.csv"))
    ]
    frames = []
    for index, path in enumerate(reading, start=1):
        info = _wanted(path)
        if info is not None:
            stamped = _stamp_multipleye_fixations(pd.read_csv(path), info, kinds=kinds)
            if not stamped.empty:
                frames.append(stamped)
        progress.report(index, len(reading), unit="files")
```

In `onestop_raw_frames`, replace the two list comprehensions with:

```python
    reports = [(kind, part) for kind in ("ia", "fixations") for part in part_list]
    word_frames, fix_frames = [], []
    for index, (kind, part) in enumerate(reports, start=1):
        frame = _read_onestop_part(root, kind, regime, part, variant)
        (word_frames if kind == "ia" else fix_frames).append(frame)
        progress.report(index, len(reports), unit="reports")
```

In `eyegenbench.py`, add `from . import progress` and replace the body of
`eyegenbench_raw_frames` after its docstring with:

```python
    directory = _dataset_dir(root, dataset)
    words = pd.read_parquet(directory / "words.parquet")
    progress.report(1, 2, unit="tables")
    fixations = pd.read_parquet(directory / "fixations.parquet")
    progress.report(2, 2, unit="tables")
    return words, fixations
```

In `persistence.py`, add `from . import progress`, and in `restore_state`
replace `for name, entry in _as_mapping(manifest.get("datasets", {})).items():`
with:

```python
            stored_datasets = _as_mapping(manifest.get("datasets", {}))
            for index, (name, entry) in enumerate(stored_datasets.items(), start=1):
```

and add as the loop body's last line (after `stored_entries[str(name)] = entry`):

```python
                progress.report(index, len(stored_datasets), unit="datasets")
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_debug_log.py tests/test_frame_cache.py tests/test_frame_immutability.py tests/test_dataset_support.py tests/test_persistence.py -q`
Expected: PASS.

- [ ] **Step 8: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/debug_log.py scanpath_studio/data.py scanpath_studio/datasets.py scanpath_studio/eyegenbench.py scanpath_studio/persistence.py scanpath_studio/app.py tests/test_debug_log.py tests/test_frame_cache.py tests/test_dataset_support.py tests/test_persistence.py
git commit -m "feat(ux): an interrupted load keeps its work, and the readers report progress (UX-166)"
```

---

### Task 6: The page skeleton and the dataset card (UX-166)

**Files:**
- Modify: `scanpath_studio/app.py` — `main` (entry point, restore, view area, data-page slot, dataset card, steps, early returns, dispatch); new helpers `_open_dataset_card`, `_finish_dataset_card`
- Modify: `scanpath_studio/app.py:1592,1650,1729,1848,2621`, `scanpath_studio/data.py:396`, `scanpath_studio/utils.py:80` — `show_spinner=False`
- Modify: `scanpath_studio/tabs.py` — `render_corpus_analysis_tab` gets a measures card
- Create: `tests/test_loading_app.py`

**Interfaces:**
- Consumes: `loading.page`, `Page.open_card`, `Card.step/finish/close`, `loading.card`, `loading.release_page`, `loading.run_scope`, `loading.session_id`, `loading.VIEW_AREA_KEY`, `loading.recorded_plot_height` (Tasks 2–3); `progress.cancel` (Task 1).
- Produces (app.py): `LAST_LOADED_SOURCE_KEY = "_sps_last_loaded_source"`, `DATASET_TASK_KEY = "_sps_dataset_task"`, `_open_dataset_card(page, data_choice, *, view_switched, finalizing) -> loading.Card | None`, `_finish_dataset_card(card) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_loading_app.py
"""UX-166 … UX-169 in the running app, via AppTest.

A run freezes with ``st.stop()`` inside the step under test, so the tree keeps
the card that step is showing. ``loading.DELAY_S = 0`` reveals cards on the
script thread, so what AppTest sees does not depend on timing.
"""

from __future__ import annotations

import pytest

from scanpath_studio import app, loading
from scanpath_studio.constants import _VIEW_CORPUS
from tests.conftest import APP_SCRIPT, pin_view

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
SYNTHETIC = "Synthetic test trial"


def _stop(*_args, **_kwargs):
    import streamlit as st

    st.stop()


def _markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


@pytest.fixture
def at():
    test = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    test.session_state["data_source_choice"] = SYNTHETIC
    return test


def test_a_finished_load_leaves_no_card_and_no_skeleton(at):
    at.run()
    assert not at.exception, at.exception
    text = _markdown(at)
    assert "sps-card-head" not in text and "sps-page-skeleton" not in text
    assert at.session_state[app.LAST_LOADED_SOURCE_KEY] == SYNTHETIC


def test_a_slow_load_shows_the_skeleton_and_its_step_list(at, monkeypatch):
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(app, "prepare_data", _stop)
    at.session_state["_pending_source_choice"] = "Bundled Demo"
    at.run()
    text = _markdown(at)
    assert "sps-sk-scanpath" in text and "sps-reveal-page" in text
    assert "sps-step-done" in text  # Reading files ✓
    assert "Normalizing" in text  # the current step, with the row counts


def test_switching_view_shows_the_target_skeleton_at_once(at, monkeypatch):
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(app, "render_corpus_analysis_tab", _stop)
    pin_view(at, _VIEW_CORPUS)
    at.run()
    text = _markdown(at)
    assert "Opening Corpus Analysis" in text
    assert "sps-sk-corpus" in text
```

(`app.py` imports `render_corpus_analysis_tab` from `tabs` at module level
(`app.py:231`), so patching `app.render_corpus_analysis_tab` is what the
dispatch sees. `DEMO_CHOICE` is `"Bundled Demo"` (`constants.py:565`).)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_loading_app.py -q`
Expected: FAIL — `AttributeError: LAST_LOADED_SOURCE_KEY`.

- [ ] **Step 3: Run `main` inside a loading scope**

In `app.py`, rename `def main() -> None:` to `def _run_app() -> None:` (keep
its docstring), and insert directly above it:

```python
def main() -> None:
    """Main application entry point: one script run, inside a loading scope.

    UX-165: ``loading.run_scope`` guarantees that no loading card's timer thread
    outlives the run that started it — whether the run ends normally, returns
    early, raises, or is abandoned by a click — and ends quietly a run whose
    work was cancelled. The run itself is `_run_app`.
    """
    with loading.run_scope():
        _run_app()
```

`grep -rn "app.main\b\|import main" scanpath_studio tests streamlit_app.py`
must show only `streamlit_app.py`'s import (and `if __name__` in `app.py`).

- [ ] **Step 4: Give the restore its own card**

Replace

```python
    app_url = str(getattr(st.context, "url", "") or "")
    if restore_local_state(
        st.session_state, app_url, protect_data_source=url_source is not None
    ):
```

with

```python
    app_url = str(getattr(st.context, "url", "") or "")
    # UX-166: restoring large uploads reads their Parquet files before even the
    # title is drawn, so it gets a card of its own at the very top of the page.
    with loading.card(
        st.empty(), key="restore", title="Restoring your datasets from this computer"
    ):
        restored = restore_local_state(
            st.session_state, app_url, protect_data_source=url_source is not None
        )
    if restored:
```

- [ ] **Step 5: Reserve the view area in place of `_view_bridge`**

Replace the block from the comment line
`    # Switching view is a full rerun — data load, filters, then a page of fresh`
through `    st.session_state["_last_rendered_view"] = active_view` with:

```python
    # UX-166 — the Scanpath and Corpus views render inside one reserved area.
    # Its first child is the page slot: `loading.Page` fills it with a skeleton
    # of the view and the dataset card while a load is slow, and CSS hides the
    # rest of the area meanwhile — the previous page, or the new one being laid
    # out under it. It replaces the old "Loading <view>…" bridge, which a view
    # switch now shows at once as that view's skeleton. The slot is recreated
    # empty on every run, so nothing it held can outlive the run (BUG-81).
    view_area = st.container(key=loading.VIEW_AREA_KEY)
    view_first_slot = view_area.empty()
    view_switched = st.session_state.get("_last_rendered_view") not in (
        None,
        active_view,
    )
    st.session_state["_last_rendered_view"] = active_view
```

- [ ] **Step 6: Reserve the Data page's card slot and create the page**

Replace

```python
    dataset_table_slot = setup_source_slot.container(key="tutorial_available_datasets")
```

with

```python
# UX-166: on the Data page the dataset card sits above the table.
data_page_slot = setup_source_slot.empty()
dataset_table_slot = setup_source_slot.container(key="tutorial_available_datasets")
page = loading.page(
    data_page_slot if data_view else view_first_slot,
    view="data"
    if data_view
    else "corpus"
    if active_view == _VIEW_CORPUS
    else "scanpath",
    plot_height=loading.recorded_plot_height("single", 480),
)
```

- [ ] **Step 7: Open the dataset card in place of `_finalizing_bridge`**

Replace the block from `    _finalizing_bridge = None` through the end of
`_clear_loading_bridges` (its `bridge.empty()` line) with:

```python
# UX-166 — one card over the dataset pipeline, drawn in the page slot. The
# post-wizard "Dataset added — loading your scanpaths…" bridge it replaces
# is this card shown at once.
dataset_card = _open_dataset_card(
    page,
    data_choice,
    view_switched=view_switched,
    finalizing=bool(st.session_state.pop("_wizard_finalizing", False)),
)


def _end_loading() -> None:
    """Take the dataset card and the page skeleton down on an early return.

    BUG-81: only the normal path cleared the old loading banners, so every
    early return (the wizard, a mapping that can't be satisfied, a filter
    that empties the pool) left one above the real content until the next
    click — on the very page the warning had just sent the user to.
    """
    if dataset_card is not None:
        dataset_card.close()
    st.session_state.pop(DATASET_TASK_KEY, None)
    page.release()
```

Replace each of the three early-return calls `_clear_loading_bridges()` (the
wizard, `mapping_problems`, the empty pool) with `_end_loading()`.

- [ ] **Step 8: Mark the pipeline's steps**

After `raw_words_df, raw_fixations_df = load_words_and_fixations(...)` and
before `declared_word_schema, declared_fix_schema = declared_schemas_for(...)`:

```python
        if dataset_card is not None and len(dataset_card.steps) == 3:
            dataset_card.step(
                1,
                f"Normalizing {len(raw_words_df):,} word rows and "
                f"{len(raw_fixations_df):,} fixations",
            )
```

Just before `    trial_filters = read_trial_filters()`:

```python
    if dataset_card is not None and dataset_card.steps:
        dataset_card.step(len(dataset_card.steps) - 1)  # Building the trial list
```

Replace the normal path's `    _clear_loading_bridges()` (just before the
dispatch comment "Render tabbed interface") with:

```python
    # UX-166: the load is done; the skeleton stays until the view has drawn its
    # controls and its first slow region opens (see `loading.card`).
    _finish_dataset_card(dataset_card)
```

- [ ] **Step 9: Render the views in the view area; release as a fallback**

In the dispatch, the `elif active_view == _VIEW_CORPUS:` branch's body and the
`else:` branch's `render_single_trial_tab(...)` call go under `with view_area:`
(indent them one level). The `if data_view:` branch gains, as its first line:

```python
        loading.release_page()  # UX-166: the Data page's card sits above its table
```

Directly after the dispatch (before
`    viz_settings = viz_settings_from_state(` that follows it), add:

```python
    # UX-166: a view that never reached a slow region (no trial selected, an
    # empty view) still takes the skeleton down.
    loading.release_page()
```

- [ ] **Step 10: Add the two helpers and the keys**

Near the other module-level session keys in `app.py`:

```python
#: UX-168: the last dataset whose pipeline finished — where Cancel goes back to.
#: Not the wizard's `_prev_source`, which only records where leaving the
#: add-dataset wizard returns to.
LAST_LOADED_SOURCE_KEY = "_sps_last_loaded_source"
#: UX-166: the dataset task this session's pipeline is running, set when the
#: card opens and cleared when it ends; found still set by the next run, it
#: means that run was abandoned mid-load.
DATASET_TASK_KEY = "_sps_dataset_task"
```

and before `main`:

```python
def _open_dataset_card(
    page, data_choice: str, *, view_switched: bool, finalizing: bool
):
    """UX-166: this run's dataset card, or ``None`` when there is no load to wait on.

    A view switch opens it at once, titled for the view, without steps: the
    dataset is loaded already, and the skeleton is what answers the click.
    """
    if data_choice in (UPLOAD_CHOICE, AUTHOR_CHOICE):
        return None
    token = str(st.session_state.get("data_source_choice") or data_choice)
    task_key = ("dataset", loading.session_id(), token)
    st.session_state[DATASET_TASK_KEY] = task_key
    if view_switched:
        return page.open_card(
            title=f"Opening {view_label(st.session_state.get('_last_rendered_view'))}",
            task_key=task_key,
            reveal_now=True,
        )
    stored = data_choice in st.session_state.get("_datasets", {})
    steps = (
        ("Building the trial list",)
        if stored
        else ("Reading files", "Normalizing", "Building the trial list")
    )
    return page.open_card(
        title=f"Loading {_dataset_display_name(token)}",
        steps=steps,
        task_key=task_key,
        duration_key=("dataset", token),
        reveal_now=finalizing,
    )


def _finish_dataset_card(card) -> None:
    """UX-166: the pipeline finished — every step ✓, the skeleton left up."""
    if card is None:
        return
    card.finish()
    card.close(keep=True)
    st.session_state[LAST_LOADED_SOURCE_KEY] = str(
        st.session_state.get("data_source_choice") or ""
    )
    st.session_state.pop(DATASET_TASK_KEY, None)
```

(`view_label` takes the view id; `_last_rendered_view` already holds the new
view when this runs. If `view_label` is imported under another name in
`app.py`, use that.)

- [ ] **Step 11: Silence the built-in spinners the dataset card covers**

Change `show_spinner="…"` to `show_spinner=False` on: `app.py`
`_cached_potec_raw_frames`, `_cached_multipleye_raw_frames`,
`_cached_onestop_raw_frames`, `_cached_eyegenbench_raw_frames`,
`_cached_multipleye_server_bundle`; `data.py` `load_onestop_server_bundle`;
`utils.py` `_build_combo_options_cached`. Each gets a one-line comment:
`# UX-166: the dataset card lists this step.`

- [ ] **Step 12: A measures card on the Corpus view**

In `tabs.render_corpus_analysis_tab`, replace
`    words_filtered = frame_cache(` … `    )` (the `"corpus_measures"` call) with:

```python
    # UX-166: the per-word measures of the whole pool are the Corpus view's
    # first slow region — opening its card releases the page skeleton, so the
    # view appears with this card at its top while they compute.
    with loading.card(
        st.empty(), key="corpus_measures", title="Computing reading measures"
    ):
        words_filtered = frame_cache(
            "corpus_measures",
            (frame_fingerprint(words_filtered), frame_fingerprint(fixations_filtered)),
            lambda: (
                compute_per_word_measures(fixations_filtered, words_filtered)
                if not words_filtered.empty and not fixations_filtered.empty
                else words_filtered
            ),
        )
```

and add `from scanpath_studio import loading` to `tabs.py`'s imports.

- [ ] **Step 13: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_loading_app.py tests/test_empty_states.py tests/test_apptest.py -q -n auto`
Expected: PASS. `test_empty_states.py`'s "no spinner" test asserts no `st.info`
starting with "Loading" — still true (the card is markdown, and it is released).

- [ ] **Step 14: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/app.py scanpath_studio/data.py scanpath_studio/utils.py scanpath_studio/tabs.py tests/test_loading_app.py
git commit -m "feat(ux): a slow load shows a skeleton of the page and its steps (UX-166)"
```

---

### Task 7: The plot stage — the rail keeps its height (UX-167)

**Files:**
- Modify: `scanpath_studio/tabs.py` — `render_single_trial_tab` (slots at `:4798`, the `with plot_slot:` block at `:5945`), `_render_true_scale_plot` (`:857`), `_cached_scanpath_figure` / `_cached_replay_view` decorators (`:1738`, `:1860`)
- Test: `tests/test_loading_app.py`

**Interfaces:**
- Consumes: `loading.card`, `loading.plot_size`, `loading.record_plot_size` (Tasks 2–3).
- Produces: the stage contract: `tour_grp_plot`'s first child is the loading slot; the figure is its second child.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loading_app.py`:

```python
from scanpath_studio import tabs


def test_a_drawn_figure_records_its_embedded_size(at):
    at.run()
    width, height = at.session_state[loading.PLOT_SIZES_KEY]["single"]
    assert width > 0 and height > 12


def test_a_slow_figure_holds_its_area_with_a_size_box(at, monkeypatch):
    at.run()
    expected = at.session_state[loading.PLOT_SIZES_KEY]["single"]
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(tabs, "_cached_scanpath_figure", _stop)
    at.run()
    text = _markdown(at)
    assert f"height:{expected[1]}px" in text
    assert "Drawing the scanpath" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_loading_app.py -q -k "size"`
Expected: FAIL — `KeyError: '_sps_plot_sizes'`.

- [ ] **Step 3: Record the embedded size**

In `_render_true_scale_plot`, after `_embed_html_iframe(html, height=iframe_height)`:

```python
    # UX-167: the next figure under this key holds its area at this size.
    loading.record_plot_size(key, width, iframe_height)
```

- [ ] **Step 4: Reserve the notes slot and the stage's first child**

Replace

```python
        plot_slot = st.container(key="tour_grp_plot")
```

with

```python
        # UX-167: notes about the figure that come *before* it sit above the
        # stage, so the figure is always the stage's second child and a figure
        # already on screen stays put while the next one is built.
        plot_notes_slot = st.container()
        plot_slot = st.container(key="tour_grp_plot")
        # The stage's first child: the size box + loading card (styles.py).
        plot_loading_slot = plot_slot.empty()
```

- [ ] **Step 5: Draw each figure under a card**

In the `with plot_slot:` block:

1. `st.warning("Raw gaze not available for this trial.", …)` → `plot_notes_slot.warning(...)`.
2. The `st.info("Animation needs a **fixations** table …")` →
   `loading.release_page()` then `plot_notes_slot.info(...)`.
3. Replace `with st.spinner("Building animation…"):` with:

```python
            with loading.card(
                plot_loading_slot,
                key="single_anim",
                title="Building the animation",
                size=loading.plot_size(
                    "single_anim", canvas_width, canvas_height, animation=True
                ),
            ):
```

4. Wrap `displayed_fig = _render_comparison_figure(...)` in:

```python
            with loading.card(
                plot_loading_slot,
                key="compare",
                title="Drawing the comparison",
                size=loading.plot_size("compare", canvas_width, canvas_height),
            ):
                displayed_fig = _render_comparison_figure(...)
```

5. In the static branch, wrap from `static_settings = render_settings.with_overrides(...)` through `_render_true_scale_chart(displayed_fig, key="single", …)` in:

```python
            with loading.card(
                plot_loading_slot,
                key="single",
                title="Drawing the scanpath",
                size=loading.plot_size("single", canvas_width, canvas_height),
            ):
```

- [ ] **Step 6: Silence the two figure caches' spinners**

`_cached_scanpath_figure`: `@st.cache_data(show_spinner=False)`.
`_cached_replay_view`: `@st.cache_data(show_spinner=False, max_entries=8)`, and
in its docstring replace "The spinner is this cache's — Streamlit shows only
the outermost one of nested caches." with "UX-167: no spinner — the plot's
loading card covers the build."

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_loading_app.py tests/test_tour.py tests/test_replay_view_cache.py tests/test_apptest.py -q -n auto`
Expected: PASS.

- [ ] **Step 8: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/tabs.py tests/test_loading_app.py
git commit -m "fix(ux): the plot area holds its size while a figure is built, so the rail isn't cut off (UX-167)"
```

---

### Task 8: Cancel a dataset load or Compare's second dataset (UX-168)

**Files:**
- Modify: `scanpath_studio/app.py` — `_open_dataset_card` (cancel), new `_cancel_dataset_load`, `_retry_load`, `_render_cancelled_load_notice`, the notice call after `render_top_menu`, the other-dataset cancel
- Modify: `scanpath_studio/tabs.py` — `_resolve_compare_source(..., loading_slot=None)`, `_render_compare_selector(..., loading_slot=None)` and its call, new `_cancel_compare_source`
- Modify: `scanpath_studio/compare_source.py:251,280` — `show_spinner=False`
- Test: `tests/test_loading_app.py`

**Interfaces:**
- Consumes: Task 6's `LAST_LOADED_SOURCE_KEY`, `DATASET_TASK_KEY`, `_open_dataset_card`; `loading.Cancel`; `progress.cancel`.
- Produces: `CANCELLED_LOAD_KEY = "_sps_cancelled_load"`; `_cancel_dataset_load(task_key, token, name, back) -> None`; `_retry_load(token) -> None`; `tabs._cancel_compare_source(task_key) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loading_app.py`:

```python
from scanpath_studio import progress
from scanpath_studio.session_keys import COMPARE_SOURCE_STATE_KEY


def test_cancel_goes_back_to_the_last_dataset_and_try_again_returns(at, monkeypatch):
    at.run()  # synthetic finishes: it is the dataset Cancel goes back to
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(app, "prepare_data", _stop)
    demo = app.DEMO_CHOICE
    at.session_state["_pending_source_choice"] = demo
    at.run()
    cancel = at.button(key="sps_cancel_page")
    assert cancel.label.startswith("Back to")
    monkeypatch.undo()
    cancel.click().run()
    assert at.session_state["data_source_choice"] == SYNTHETIC
    at.button(key="sps_try_again").click().run()
    assert at.session_state["data_source_choice"] == demo


def test_picking_another_dataset_mid_load_cancels_the_first(at):
    at.run()
    stale = ("dataset", "an-abandoned-run", "Other")
    task = progress.begin(stale, title="Loading Other")
    at.session_state[app.DATASET_TASK_KEY] = stale
    at.run()
    assert task.cancelled


def _compare_cancel_script():
    import streamlit as st

    from scanpath_studio import tabs

    st.session_state.setdefault("cmp_dataset", "Bundled Demo")
    st.button("x", key="c", on_click=tabs._cancel_compare_source, args=(("cmp", "k"),))


def test_the_compare_cancel_goes_back_to_this_dataset():
    at = AppTest.from_function(_compare_cancel_script).run()
    at.button(key="c").click().run()
    assert at.session_state[COMPARE_SOURCE_STATE_KEY] == tabs.THIS_DATASET
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_loading_app.py -q -k "cancel or another"`
Expected: FAIL.

- [ ] **Step 3: Give the dataset card its Cancel, and cancel an abandoned other load**

In `_open_dataset_card`, before `st.session_state[DATASET_TASK_KEY] = task_key`:

```python
    # UX-168: a run that finds another dataset's task still marked running was
    # started by picking this one mid-load — the user changed their mind, so the
    # first load stops at its next checkpoint instead of competing for the CPU.
    previous = st.session_state.get(DATASET_TASK_KEY)
    if previous is not None and tuple(previous) != task_key:
        progress.cancel(tuple(previous))
```

and in its non-switch `page.open_card(...)` call add:

```python
cancel = (_dataset_cancel(token, task_key),)
```

with, above `_open_dataset_card`:

```python
#: UX-168: set by Cancel on the dataset card, read once by the next run's notice.
CANCELLED_LOAD_KEY = "_sps_cancelled_load"


def _dataset_cancel(token: str, task_key: tuple) -> loading.Cancel | None:
    """The dataset card's Cancel: back to the last dataset that finished loading
    in this session, else the Bundled demo — never back to the one it cancels."""
    back = st.session_state.get(LAST_LOADED_SOURCE_KEY) or DEMO_CHOICE
    if back == token:
        back = DEMO_CHOICE
    if back == token:
        return None
    return loading.Cancel(
        f"Back to {_dataset_display_name(back)}",
        _cancel_dataset_load,
        args=(task_key, token, _dataset_display_name(token), back),
    )


def _cancel_dataset_load(task_key: tuple, token: str, name: str, back: str) -> None:
    """UX-168: Cancel on the dataset card — stop the load, reopen ``back``."""
    progress.cancel(task_key)
    st.session_state["_pending_source_choice"] = back
    st.session_state[CANCELLED_LOAD_KEY] = {"token": token, "name": name}


def _retry_load(token: str) -> None:
    st.session_state["_pending_source_choice"] = token


def _render_cancelled_load_notice(host) -> None:
    """UX-168: "Stopped loading X · Try again", once, where the notices go."""
    note = st.session_state.pop(CANCELLED_LOAD_KEY, None)
    if not note:
        return
    row = host.container(
        key="sps_cancelled_notice", horizontal=True, vertical_alignment="center"
    )
    row.caption(f"Stopped loading **{note['name']}**.")
    row.button(
        "Try again",
        key="sps_try_again",
        on_click=_retry_load,
        args=(note["token"],),
        type="tertiary",
    )
```

After `menu = render_top_menu(...)` and `_render_about_panel(menu.title)`, add:

```python
    _render_cancelled_load_notice(menu.notices)
```

- [ ] **Step 4: Card and Cancel for Compare's second dataset**

In `tabs.py`, add near `_resolve_compare_source`:

```python
def _cancel_compare_source(task_key: tuple) -> None:
    """UX-168: Cancel on B's dataset card — compare within A's dataset again."""
    progress.cancel(task_key)
    st.session_state[COMPARE_SOURCE_KEY] = THIS_DATASET
```

Give `_resolve_compare_source` a keyword parameter `loading_slot=None` and
replace `    source = load_secondary_dataset(chosen)` with:

```python
    if loading_slot is None:
        source = load_secondary_dataset(chosen)
    else:
        task_key = ("compare_dataset", loading.session_id(), chosen)
        with loading.card(
            loading_slot,
            key="cmp_dataset",
            title=f"Loading {chosen} for scanpath B",
            task_key=task_key,
            cancel=loading.Cancel(
                f"Compare within {current_dataset_name()}",
                _cancel_compare_source,
                args=(task_key,),
            ),
        ):
            source = load_secondary_dataset(chosen)
```

Thread `loading_slot=None` through `_render_compare_selector`'s signature into
its `_resolve_compare_source(...)` call, and pass
`loading_slot=plot_loading_slot` at the `_render_compare_selector(` call in
`render_single_trial_tab`. Add `from scanpath_studio import progress` to
`tabs.py`'s imports. In `compare_source.py`, set `show_spinner=False` on
`_load_public_frames` and `_load_builtin_frames` (comment:
`# UX-168: B's dataset card covers this.`).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_loading_app.py tests/test_compare_cross_dataset.py -q -n auto`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/app.py scanpath_studio/tabs.py scanpath_studio/compare_source.py tests/test_loading_app.py
git commit -m "feat(ux): cancel a dataset load or Compare's second dataset, and go back (UX-168)"
```

---

### Task 9: Downloads show progress and can be stopped (UX-168)

**Files:**
- Modify: `scanpath_studio/datasets.py:87-142` (`download_potec`), `:514-560` (`download_onestop`); new `_fetch_bytes`, `_fetch_to_file`, `_DOWNLOAD_CHUNK`
- Modify: `scanpath_studio/app.py` — `_render_dataset_unavailable` (`:1500-1514`) and `_dataset_access_status` (`:1581-1588`)
- Create: `tests/test_downloads.py`

**Interfaces:**
- Consumes: `progress.report`, `progress.task`, `progress.cancel`, `progress.Cancelled`; `loading.card`, `loading.Cancel`, `loading.session_id`.
- Produces: `datasets._fetch_bytes(url: str, *, detail: str) -> bytes`, `datasets._fetch_to_file(url: str, dest: Path, *, detail: str) -> None`, `datasets._DOWNLOAD_CHUNK: int`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_downloads.py
"""UX-168: corpus downloads report bytes and stop cleanly on Cancel."""

from __future__ import annotations

import io

import pytest

from scanpath_studio import datasets, progress


class _Response(io.BytesIO):
    def __init__(self, data: bytes, *, length: bool = True, on_read=None):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))} if length else {}
        self._on_read = on_read

    def read(self, size=-1):
        chunk = super().read(size)
        if self._on_read is not None:
            self._on_read()
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_a_download_reports_bytes_and_lands_atomically(monkeypatch, tmp_path):
    monkeypatch.setattr(datasets, "_DOWNLOAD_CHUNK", 4)
    monkeypatch.setattr(
        datasets.urllib.request, "urlopen", lambda url: _Response(b"x" * 10)
    )
    dest = tmp_path / "report.csv.zip"
    with progress.task(("t", "dl"), title="Downloading") as task:
        datasets._fetch_to_file("https://example.invalid/r", dest, detail="IA report")
    assert dest.read_bytes() == b"x" * 10
    assert not dest.with_name(dest.name + ".part").exists()
    snap = task.snapshot()
    assert (snap.done, snap.total, snap.unit, snap.detail) == (
        10,
        10,
        "bytes",
        "IA report",
    )


def test_cancelling_mid_download_leaves_no_file_behind(monkeypatch, tmp_path):
    monkeypatch.setattr(datasets, "_DOWNLOAD_CHUNK", 4)
    key = ("t", "dl-cancel")
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        lambda url: _Response(b"x" * 12, on_read=lambda: progress.cancel(key)),
    )
    dest = tmp_path / "report.csv.zip"
    with progress.task(key, title="Downloading"):
        with pytest.raises(progress.Cancelled):
            datasets._fetch_to_file(
                "https://example.invalid/r", dest, detail="IA report"
            )
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_fetch_bytes_without_a_length_still_reports(monkeypatch):
    monkeypatch.setattr(datasets, "_DOWNLOAD_CHUNK", 4)
    monkeypatch.setattr(
        datasets.urllib.request,
        "urlopen",
        lambda url: _Response(b"y" * 9, length=False),
    )
    with progress.task(("t", "bytes"), title="Downloading") as task:
        assert (
            datasets._fetch_bytes("https://example.invalid/z", detail="archive")
            == b"y" * 9
        )
    assert task.snapshot().done == 9 and task.snapshot().total is None


def test_a_cancelled_unpack_leaves_no_partial_corpus(monkeypatch, tmp_path):
    """A half-unpacked `scanpaths/` would pass `potec_present`'s "any .tsv"
    check and load as a silently partial corpus — so it unpacks to a staging
    folder and is renamed into place only when complete."""
    import zipfile

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        for reader in range(3):
            z.writestr(f"scanpaths/reader{reader}_b0_scanpath.tsv", "a\tb\n1\t2\n")
    key = ("t", "unpack")
    real_report = progress.report
    seen = {"calls": 0}

    def report(done=None, total=None, **kwargs):
        seen["calls"] += 1
        if seen["calls"] == 2:
            progress.cancel(key)
        real_report(done, total, **kwargs)

    monkeypatch.setattr(
        datasets, "_fetch_bytes", lambda url, *, detail: archive.getvalue()
    )
    monkeypatch.setattr(progress, "report", report)
    with progress.task(key, title="Downloading PoTeC"):
        with pytest.raises(progress.Cancelled):
            datasets.download_potec(tmp_path)
    assert not (tmp_path / "eyetracking_data" / "scanpaths").exists()
    assert not list((tmp_path / "eyetracking_data").glob(".*.part"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_downloads.py -q`
Expected: FAIL — `AttributeError: _DOWNLOAD_CHUNK`.

- [ ] **Step 3: Chunked, cancellable fetches**

In `datasets.py`, above `download_potec`:

```python
#: UX-168: download in chunks of this size, reporting bytes after each — the
#: progress the card shows, and the checkpoint a Cancel stops at.
_DOWNLOAD_CHUNK = 1 << 20


def _content_length(response) -> int | None:
    value = response.headers.get("Content-Length")
    return int(value) if value and str(value).isdigit() else None


def _fetch_bytes(url: str, *, detail: str) -> bytes:
    """``url``'s body, read in chunks with progress (UX-168)."""
    with urllib.request.urlopen(url) as response:
        total = _content_length(response)
        buffer = io.BytesIO()
        while chunk := response.read(_DOWNLOAD_CHUNK):
            buffer.write(chunk)
            progress.report(buffer.tell(), total, unit="bytes", detail=detail)
        return buffer.getvalue()


def _fetch_to_file(url: str, dest: Path, *, detail: str) -> None:
    """Stream ``url`` into ``dest`` through a ``.part`` file (UX-168).

    The ``.part`` → final rename keeps an interrupted fetch from passing for a
    complete file; a cancel (or any failure) deletes the partial file.
    """
    tmp = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url) as response, tmp.open("wb") as out:
            total = _content_length(response)
            done = 0
            while chunk := response.read(_DOWNLOAD_CHUNK):
                out.write(chunk)
                done += len(chunk)
                progress.report(done, total, unit="bytes", detail=detail)
        tmp.replace(dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
```

In `download_potec`, replace the archive fetch and unpack — from
`        with urllib.request.urlopen(url) as response:` through
`            archive.extractall(root / "eyetracking_data", members=members)` — with
(add `import shutil` to the module's imports):

```python
        payload = _fetch_bytes(url, detail=f"PoTeC {fixation_source} archive")
        target = root / "eyetracking_data"
        target.mkdir(parents=True, exist_ok=True)
        # UX-168: unpack into a staging folder and rename it into place only
        # when complete. A cancel mid-unpack would otherwise leave a partial
        # `scanpaths/` that `potec_present`'s "any .tsv" check accepts.
        staging = target / f".{fixation_source}.part"
        shutil.rmtree(staging, ignore_errors=True)
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = [
                    m
                    for m in archive.namelist()
                    # The OSF zips carry macOS resource-fork cruft; keep only the
                    # real per-trial TSVs.
                    if m.startswith(f"{fixation_source}/") and m.endswith(".tsv")
                ]
                for index, member in enumerate(members, start=1):
                    archive.extract(member, staging)
                    progress.report(
                        index, len(members), unit="files", detail="Unpacking the archive"
                    )
            (staging / fixation_source).replace(eyetracking_dir)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
```

Then replace the AOI loop's

```python
            tmp = dest.with_name(dest.name + ".part")
            with urllib.request.urlopen(url) as response:
                tmp.write_bytes(response.read())
            tmp.replace(dest)
```

with `            _fetch_to_file(url, dest, detail=f"AOI file {rel.rsplit('/', 1)[-1]}")`
(keep the comment above it). In `download_onestop`, replace the same three
lines with `            _fetch_to_file(url, dest, detail=f"{part} {kind} report")`.

- [ ] **Step 4: Download cards in the app**

In `app.py`, add:

```python
def _stop_download(task_key: tuple) -> None:
    """UX-168: Stop on a download card — the transfer ends at its next chunk."""
    progress.cancel(task_key)


def _download_with_card(slot, download, root: str, *, label: str, key: str) -> None:
    """Run ``download(root)`` under a card with a Stop button (UX-168)."""
    task_key = ("download", loading.session_id(), key)
    with loading.card(
        slot,
        key=f"download_{key}",
        title=f"Downloading {label}",
        task_key=task_key,
        cancel=loading.Cancel("Stop download", _stop_download, args=(task_key,)),
    ):
        download(root)
```

In `_render_dataset_unavailable`, replace

```python
        if st.button(
            "⬇ Download now",
            key=f"{note['key_prefix']}_download_main",
            type="primary",
        ):
            try:
                with st.spinner(f"Downloading into {note['root']} …"):
                    download(note["root"])
```

with

```python
        clicked = st.button(
            "⬇ Download now",
            key=f"{note['key_prefix']}_download_main",
            type="primary",
        )
        download_slot = st.empty()
        if clicked:
            try:
                _download_with_card(
                    download_slot,
                    download,
                    note["root"],
                    label=note["label"],
                    key=f"{note['key_prefix']}_main",
                )
```

In `_dataset_access_status`, replace

```python
    if cfg.button("⬇ Download", key=f"{key_prefix}_download", type="primary"):
        try:
            with st.spinner(f"Downloading into {root} …"):
                download(root)
```

with

```python
    clicked = cfg.button("⬇ Download", key=f"{key_prefix}_download", type="primary")
    download_slot = cfg.empty()
    if clicked:
        try:
            _download_with_card(download_slot, download, root, label=label, key=key_prefix)
```

(The existing `except (OSError, ValueError)` blocks and `st.rerun()` stay.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_downloads.py tests/test_dataset_support.py -q`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/datasets.py scanpath_studio/app.py tests/test_downloads.py
git commit -m "feat(ux): corpus downloads show their progress and can be stopped (UX-168)"
```

---

### Task 10: The animation card — frame count and Cancel (UX-169)

**Files:**
- Modify: `scanpath_studio/plots.py:4127-4225` (the frame loop in `_render_scanpath_animation`)
- Modify: `scanpath_studio/tabs.py` — the animate branch's card (from Task 7), `_build_and_render_animation.finished_figure`, new `_cancel_animation`
- Test: `tests/test_loading_app.py`, `tests/test_progress.py`

**Interfaces:**
- Consumes: `progress.report`, `progress.step_to`, `progress.cancel`; `loading.card`, `loading.Cancel`, `loading.session_id`.
- Produces: `tabs._cancel_animation(task_key) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_progress.py`:

```python
def test_building_a_replay_reports_every_frame():
    from scanpath_studio import api
    from scanpath_studio.synthetic import load_synthetic_data

    words, fixations = api.load_scanpath_data(*load_synthetic_data())
    pid = str(fixations["participant_id"].iloc[0])
    trial = str(fixations["trial_id"].iloc[0])
    with progress.task(("t", "replay"), title="x", steps=("Building frames",)) as task:
        fig = api.animate_scanpath(words, fixations, pid, trial)
    snap = task.snapshot()
    assert snap.unit == "frames"
    assert snap.done == snap.total == len(fig.frames)
```

Append to `tests/test_loading_app.py`:

```python
def _animation_cancel_script():
    import streamlit as st

    from scanpath_studio import tabs

    st.session_state.setdefault("single_animate", True)
    st.button("x", key="c", on_click=tabs._cancel_animation, args=(("anim", "k"),))


def test_the_animation_cancel_switches_animate_off():
    at = AppTest.from_function(_animation_cancel_script).run()
    at.button(key="c").click().run()
    assert at.session_state["single_animate"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra test pytest tests/test_progress.py tests/test_loading_app.py -q -k "replay or animation_cancel"`
Expected: FAIL.

- [ ] **Step 3: Report each frame**

In `plots.py`, add `from . import progress` to the local imports, and in
`_render_scanpath_animation` replace

```python
    frames = []
    for k, t in enumerate(frame_times):
```

with

```python
    frames = []
    n_frames = len(frame_times)
    for k, t in enumerate(frame_times):
        # UX-169: the card's "120 of 361 frames" — and a cancel checkpoint, so an
        # abandoned build stops within a frame. A no-op outside a card.
        progress.report(k + 1, n_frames, unit="frames")
```

- [ ] **Step 4: The animation card's steps and Cancel**

In `tabs.py`, add:

```python
def _cancel_animation(task_key: tuple) -> None:
    """UX-169: Cancel on the animation card — back to the static plot."""
    progress.cancel(task_key)
    st.session_state["single_animate"] = False
```

Replace Task 7's animation card opener with:

```python
            anim_task = ("anim", loading.session_id())
            with loading.card(
                plot_loading_slot,
                key="single_anim",
                title="Building the animation",
                steps=("Building frames", "Preparing the player"),
                size=loading.plot_size(
                    "single_anim", canvas_width, canvas_height, animation=True
                ),
                task_key=anim_task,
                cancel=loading.Cancel(
                    "Show static plot", _cancel_animation, args=(anim_task,)
                ),
            ):
```

In `_build_and_render_animation.finished_figure`, directly after the
`fig, frame_step_ms = _cached_scanpath_animation(...)` call:

```python
        # UX-169: the frames exist; what is left is the player — the clock, the
        # labels and the 10 MB of markup `_ReplayView.from_figure` writes.
        progress.step_to(1)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_progress.py tests/test_loading_app.py tests/test_replay_clock_cache.py tests/test_replay_view_cache.py tests/test_replay_player.py -q`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/plots.py scanpath_studio/tabs.py tests/test_progress.py tests/test_loading_app.py
git commit -m "feat(ux): the animation card counts frames and can go back to the static plot (UX-169)"
```

---

### Task 11: A placeholder inside the plot's frame (UX-169)

**Files:**
- Modify: `scanpath_studio/tabs.py:443` (`_TRUE_SCALE_TEMPLATE`)
- Test: `tests/test_loading_app.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: the template's `skel-__KEY__` element and its `dropSkeleton` poll.

- [ ] **Step 1: Write the failing test**

```python
def test_the_plot_frame_carries_a_placeholder_removed_on_first_draw():
    html, _ = tabs._true_scale_html(
        '<div id="truescale-k"></div>',
        key="k",
        width=100,
        height=50,
        max_height=None,
        zoomable=True,
    )
    assert 'id="skel-k"' in html
    assert "dropSkeleton" in html
    # It must run for the small multiples too, which return before the zoom code.
    assert html.index("dropSkeleton") < html.index("if (!ZOOMABLE)")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --extra test pytest tests/test_loading_app.py -q -k placeholder`
Expected: FAIL.

- [ ] **Step 3: Add the placeholder to the template**

In `_TRUE_SCALE_TEMPLATE`, change the `fit` div's opening tag to add
`position:relative;`:

```html
  <div id="fit-__KEY__" style="width:100%;overflow:hidden;position:relative;">
```

and insert, as the first child of that `fit` div (before `<div id="size-__KEY__"`):

```html
    <div id="skel-__KEY__" aria-hidden="true"></div>
```

Add before `<script>`:

```html
<style>
  /* UX-169: a placeholder at the figure's size while plotly.js loads and the
     figure draws — seconds for a big replay. It fades in only after 300 ms, so
     a small figure never flickers, and goes on Plotly's first draw. */
  @keyframes sps-skel-in { to { opacity: 1; } }
  @keyframes sps-skel-pulse { 50% { opacity: 0.55; } }
  #skel-__KEY__ { position: absolute; inset: 0; z-index: 4; pointer-events: none;
    opacity: 0; border-radius: 8px; background: rgba(128, 128, 128, 0.10);
    animation: sps-skel-in .2s ease .3s forwards,
               sps-skel-pulse 1.6s ease-in-out .5s infinite; }
  @media (prefers-reduced-motion: reduce) {
    #skel-__KEY__ { animation: sps-skel-in .01s linear .3s forwards; } }
</style>
```

In the script, directly after `  setTimeout(render, 150);` and before
`  if (!ZOOMABLE) { return; }`:

```js
  (function dropSkeleton() {
    var sk = document.getElementById("skel-__KEY__");
    if (!sk) { return; }
    var gd = document.getElementById("truescale-__KEY__");
    if (!gd || !gd._fullLayout) { setTimeout(dropSkeleton, 60); return; }
    sk.parentNode.removeChild(sk);
  })();
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra test pytest tests/test_loading_app.py -q -k placeholder && uv run --extra test pytest tests -q -k "true_scale or truescale" -n auto`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add scanpath_studio/tabs.py tests/test_loading_app.py
git commit -m "feat(ux): the plot's frame shows a placeholder until the figure has drawn (UX-169)"
```

---

### Task 12: Docs, changelog details, spec touch-ups

**Files:**
- Modify: `AGENTS.md` (architecture map), `scanpath_studio/CLAUDE.md` (module list + Gotchas), `CHANGELOG.md` (`### Details`), `plans/ux-165-loading-states.md` (§3.1 sizing, out-of-scope link), user docs page(s)

- [ ] **Step 1: The module maps**

In `AGENTS.md`'s tree, after the `easter_egg.py` line, add:

```text
├─ progress.py       UX-165: a Streamlit-free progress hook — loaders and builders `report()` counts, the orchestrator `step_to()`s; a no-op without a task, and the cancel checkpoint (`Cancelled`) with one
├─ loading.py        UX-165: loading cards drawn hidden by the script thread and revealed + refreshed by a timer thread (the `st.spinner` pattern); `card()` for a region, `Page` for the page skeleton + dataset card, `run_scope()` around each run, Cancel buttons that restore the previous choice
```

In `scanpath_studio/CLAUDE.md`'s *Modules* list, after the `easter_egg.py`
bullet, add:

```markdown
- [progress.py](progress.py) — **UX-165** a Streamlit-free progress hook. Loaders and builders call `report(done, total, unit=…)` from inside their loops and the orchestrator calls `step_to(i)` between stages; both are no-ops without an active `Task` (so the API and CLI are unchanged), and both are the **cancel checkpoint** — after `cancel(key)` the computing thread raises `Cancelled` (a `BaseException`, so broad `except Exception` handlers can't swallow it) within one file, frame or chunk. `begin(key)` joins a running task, never a finished or cancelled one, which is how a rerun that interrupted a load keeps its counts. Task keys carry the session id (`loading.session_id()`), so one session's cancel never stops another's work.
- [loading.py](loading.py) — **UX-165** loading cards. The script thread draws a card hidden when it opens (its Cancel button included — widgets belong to the script thread, once per run); a `_Ticker` thread carrying the script-run context reveals it after `DELAY_S` (0.5 s) and repaints its placeholders every `REFRESH_S`, the pattern `st.spinner`'s own timer uses. `card(slot, …)` is a region card over a `size=` box (a figure's iframe height, recorded per plot key by `record_plot_size`); `Page` is the page skeleton + dataset card in `sps_view`'s first slot, released by the view's first region card or `release_page()`; `run_scope()` wraps every run, so no timer outlives it and a cancelled, abandoned run ends quietly. Cancel is instant because Streamlit's `runner.fastReruns` abandons the running script on a click and drops the abandoned run's output — the callback only restores the previous choice. **The plot stage contract (UX-167):** `tour_grp_plot`'s first child is the loading slot and the figure is the second, stacked in one grid cell by `styles.py`.
```

In *Gotchas*, add:

```markdown
- **A new slow step gets a loading card, not `st.spinner`** (UX-165). Wrap it in
  `loading.card(slot, …)` with a `size=` when it replaces a figure, and report
  counts through `progress.report()` from inside its loop. Never create a
  Streamlit element inside the progress hook's callers' cached functions: the
  hook is a side channel precisely because `st.cache_data` replays elements.
- **Keep the plot stage's order** (UX-167): notes that come before the figure go
  to `plot_notes_slot`, never into `tour_grp_plot` ahead of the figure — the
  figure must be the stage's second child, or a figure on screen vanishes the
  moment the next build starts.
```

- [ ] **Step 2: The changelog details**

Under `### Details`, add under `#### Added` (create the heading if absent):

```markdown
- **A long wait says what the app is doing: a card with the step, a count, the elapsed time and a Cancel** (UX-165) — Every slow region — a dataset load, a figure, the Corpus view's measures, a download — opens a card after 0.5 s (never sooner, so ordinary clicks show nothing) with the step, a count where there is one ("312 of 900 files", "120 of 361 frames", "120 of 450 MB"), the elapsed time and, where there is somewhere to go back to, a Cancel. The card holds its area at the size the content will take, so nothing jumps when it lands, and a timer thread keeps it current while the app works (`loading.py`, on the Streamlit-free hook `progress.py`). The spinners that remain lost their pulsing blue banner for a small pill with its elapsed time. #241.
- **Cancel a dataset load, an animation build, Compare's second dataset or a download, and go back to where you were** (UX-168) — **Back to <dataset>** reopens the last dataset that finished loading (the Bundled demo on a fresh start) and leaves a "Stopped loading … · Try again" notice; **Show static plot** switches 🎬 Animate off; **Compare within <A>** returns scanpath B to A's dataset; **Stop download** ends the transfer and deletes the partial file. Each lands at once — a click abandons the running script (Streamlit's `runner.fastReruns`) and the abandoned work stops at its next file, frame or chunk — and picking another dataset mid-load cancels the first. Any other click during a load doesn't cancel it: the new run joins the step already running, and a finished step stays cached, which needed the log handler to stop letting an abandoned run's `StopException` escape (it threw away every cached build that logs through `timed()`). Downloads read in 1 MiB chunks, and PoTeC's archive unpacks into a staging folder, so a stopped unpack never passes for a complete corpus.
```

under `#### Changed`:

```markdown
- **A dataset that takes a while to open shows a skeleton of the page and its steps, not a lone banner** (UX-166) — The Scanpath and Corpus views render inside one reserved area, and while a load is slow a skeleton of the view you're on stands in for it — selector row, chips, plot box and rail — under the dataset card's step list: Reading files → Normalizing N word rows and M fixations → Building the trial list, each ✓ with its time, plus "last load: 6 s" when the dataset has loaded before. The skeleton hides the previous page and comes down only once the new page has drawn its controls, so the old page never flashes back. A view switch shows the target view's skeleton at once; together these replace the "Loading <view>…" and "Dataset added — loading your scanpaths…" banners. A click during normalization no longer starts a second normalization beside the first: `frame_cache` shares a build in flight.
- **Building an animation counts its frames, and the plot shows a placeholder until the browser has drawn it** (UX-169) — The animation card counts frames as the replay is built, then says "Preparing the player". The plot's own frame shows a placeholder at the figure's size until Plotly's first draw — seconds for a big replay, whose page is megabytes (PERF-17) — fading in only after 300 ms, so a small figure never flickers.
```

and under `#### Fixed`:

```markdown
- **The plot-controls rail no longer looks cut off while a figure is being drawn** (UX-167) — The rail is exactly as tall as the plot row (UX-43), so while the plot area held only a spinner the rail was cropped to ~90 px and faded out. The plot area is now a stage whose first child holds a box at the figure's embedded height (recorded per plot key; estimated for a first render), and a figure already on screen stays in place — veiled under the card if the next one takes longer than 0.5 s — until its replacement arrives.
```

- [ ] **Step 3: Spec touch-ups**

The plan settled three things more simply than the spec words them; bring the
spec in line:

1. **§3.1** — replace the sentence "It scales with the column as
   `_render_true_scale_chart` does — `width: min(100%, Wpx); aspect-ratio: W / H`
   for the script's `Math.min(1, avail / W)` — so the row keeps its height and
   the rail with it." with: "It takes the true-scale iframe's fixed height — the
   figure's height + 12; `html_embed.embed_html_iframe` passes an int to
   `st.iframe`, so the row is exactly that tall at any column width — capped at
   the figure's width, so the row keeps its height and the rail with it."
2. **§3.2** — replace its last paragraph ("A figure on screen" is the recorded
   size…) with: "Both cases are one mechanism: the size box always sits in the
   stage's first child. Unrevealed it is transparent and only holds the height;
   revealed it is a translucent veil — over an old figure it reads as dimming,
   over an empty area as a skeleton. No flag has to track whether a figure is on
   screen."
3. **§4.3** — in the last bullet, replace "is caught by the card's exit," with
   "is caught by `loading.run_scope`," and "`progress.task()`" with
   "`progress.begin()`".

In *Scope → Out*, change "filed as a backlog issue." to "filed as **PERF-17**
(#242)."

- [ ] **Step 4: User docs**

Only what Task 13's live check confirms — if a sentence below turns out
untrue in the live app, fix the app or drop the sentence.

`docs/guides/loading-data.md`, after the `## Choose a source` bullet list:

```markdown
While a dataset opens, the page shows a skeleton of the view with the steps of
the load — reading the files, normalizing them, building the trial list — each
ticked off with its time. **Back to *dataset*** stops the load and reopens the
dataset you had before, and a notice offers **Try again**. A dataset opened
once since the app started opens again without the wait.
```

`docs/onestop.md`, appended to the paragraph ending "…reports range from tens
to a few hundred MB each).":

```markdown
While it downloads, a card shows how much has arrived; **Stop download** ends
it and deletes the partial file.
```

`docs/guides/scanpath-visualization.md`, the *Replay and compare* list's
**Animate** bullet becomes:

```markdown
- **Animate** replays the selected trial. The **▾** beside it controls playback
  speed, autoplay, and smoothness. Building a replay shows a frame count;
  **Show static plot** cancels it.
```

- [ ] **Step 5: Build the docs and commit**

Run: `uv run --extra docs mkdocs build --strict` (no `-q`; check the exit code).
Expected: exit 0.

```bash
uvx --from ruff==0.16.8 ruff check . && uvx --from ruff==0.16.8 ruff format .
git add AGENTS.md scanpath_studio/CLAUDE.md CHANGELOG.md plans/ux-165-loading-states.md docs
git commit -m "docs: loading states in the module maps, changelog and user docs (UX-165 … UX-169)"
```

---

### Task 13: Verify, review, hand over

**Files:** none new.

- [ ] **Step 1: Full suite and lint**

Run: `uv run --extra test pytest -n auto -q`
Expected: PASS. Report the interpreter (`uv run --extra test python -c "import sys, pandas; print(sys.version, pandas.__version__)"`).

- [ ] **Step 2: The house reviewers**

Dispatch `perf-reviewer` (per-rerun cost of the hidden cards, the ticker
threads, `frame_cache`'s in-flight registry) and `surface-parity-reviewer`
(state the four-surface rule does not apply — no setting added; no wire-format
key added; the true-scale path is unchanged). Tell both: any app they start uses
`SCANPATH_STUDIO_PERSIST=0`, `--server.address 127.0.0.1`, a port other than
8501/8511. Fix what they confirm; re-run the affected tests.

- [ ] **Step 3: Live check**

Start the worktree's own server (the preview tool cannot read a worktree's
`launch.json`):

```bash
SCANPATH_STUDIO_PERSIST=0 uv run --extra test python -m streamlit run streamlit_app.py \
  --server.port 8541 --server.headless true --server.address 127.0.0.1
```

(run in the background; wait on `curl -s http://127.0.0.1:8541/_stcore/health`),
then `preview_start {url: "http://127.0.0.1:8541"}`. On the Data page, point
PoTeC's data location at `/Users/shubi/Projects/scanpath_studio/app/data/PoTeC`
(the worktree has no `data/`). Check, with a screenshot each:

1. A cold PoTeC load (restart the server first): skeleton + step list; the
   counts move; the rail is whole.
2. Switching Bundled demo → PoTeC → back: fast switches show nothing; a slow
   one shows the skeleton, never the old page.
3. 🎬 Animate on PoTeC `0/b0`: the static figure stays and dims, the card counts
   frames, then "Preparing the player"; the rail keeps its full height.
4. Each Cancel: dataset (→ previous + Try again), animation (→ static plot),
   Compare B (→ this dataset). Each lands within a second.
5. Dark theme: the card, skeletons and size box read correctly.

Stop the server afterwards.

- [ ] **Step 4: Ready the PR and move #241 to Review**

```bash
git push
gh pr ready
```

Rewrite #241's body (`gh issue view 241 --json body --jq .body > body.md`,
edit, `gh issue edit 241 --body-file body.md --add-label waiting-on-you`) to:

```markdown
> **Review.** Implemented in PR #<n>; update as of <date>.

### ⚖ Waiting on you

- [ ] Review in the app: a cold PoTeC load (skeleton + steps), a slow dataset switch, 🎬 Animate on PoTeC `0/b0` (frame count, rail whole), and each Cancel — dataset (→ previous + Try again), animation (→ static plot), Compare B (→ this dataset), a download (→ Stop).
- [ ] Judgement calls to agree or change: nothing shows for 0.5 s; a slow switch replaces the old page with a skeleton rather than dimming it; the card sits over the plot area (page card: over the skeleton's plot box); views and long computations have no Cancel (the nav is the change of mind); the remaining spinners are a small pill with elapsed time.

## Request

<unchanged>

## What was done

- **UX-165** — `progress.py` (the hook) and `loading.py` (cards drawn hidden, revealed and refreshed by a timer thread); the card / skeleton CSS; calm spinners with elapsed time.
- **UX-166** — the page skeleton and B's step list for dataset loads; a restore card; `frame_cache` shares a build in flight; the log handler no longer throws an abandoned run's finished build away; readers report counts.
- **UX-167** — the plot stage: a size box holds the figure's height, a figure on screen stays until its replacement lands, so the rail keeps its height.
- **UX-168** — Cancel for dataset loads (+ Try again), Compare's second dataset, and downloads (chunked, staged unpack).
- **UX-169** — the animation card counts frames and cancels to the static plot; a placeholder in the plot's frame until Plotly draws.

## What's left

Nothing.

## Background

<the design summary as before, plus: the spike (2026-09-27) — a timer thread revealed and refreshed a card while the script thread slept; Cancel landed in <150 ms; the abandoned run's output never reached the page. Measured costs from the live check.>
```

Then move the board card to **Review** (option `2d6ed3eb`, same
`gh project item-edit` form as Task 0 Step 4). Do not close the issue.
