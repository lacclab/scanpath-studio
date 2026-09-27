# UX-165 · Loading states that keep the page whole, say what is happening, and can be cancelled

> **Status: design, 2026-09-27.** Agreed with the user section by section in
> the design session: approach 1 ("loading regions inside the current script"),
> look **A** (a card over a size-holding placeholder) everywhere, with **B**'s
> step list for dataset loads. Five IDs, **UX-165 … UX-169**, one per commit
> (§7). UX-169 builds on **PERF-16** (#240), which the "Animation timing
> issue" session landed on 2026-09-26 (§8). Code anchors are on `main` at
> `1b25285`.

## Context

The user's report, with a screenshot of the Scanpath view in Animate mode on
PoTeC: "the app looks cut off while things load … the current implementation is
bad." The request has three parts: how the app **looks** while work happens,
how **informative** the loading indicators are, and the user's **options to
change their mind** — cancelling a dataset load that takes too long, for
example.

### What causes it

1. **The rail is cropped.** UX-43 gives the rail its own scroll area, exactly as
   tall as the plot row: `.st-key-scanpath_rail` is `height: 100%` inside a
   column whose block is `position: absolute; inset: 0`
   ([styles.py:1370](../scanpath_studio/styles.py:1370),
   [styles.py:1400](../scanpath_studio/styles.py:1400)). While the plot slot
   ([tabs.py:4798](../scanpath_studio/tabs.py:4798)) holds only a ~90 px spinner,
   the row is ~90 px tall, and the rail is cut to that height and fades out.
2. **A cold load shows nothing below the title.** `main` loads and normalizes
   the dataset before any view is laid out, so until the trial list exists the
   page is the title row plus a banner.
3. **One loud, uninformative spinner.** Every `st.spinner` and every
   `show_spinner=` message renders as the same pulsing blue banner
   ([styles.py:202](../scanpath_studio/styles.py:202)). It has no progress,
   no elapsed time and no way out. Some waits nest two of them — "Building
   animation…" ([tabs.py:5956](../scanpath_studio/tabs.py:5956)) around the
   replay cache's "Building the replay…".
4. **Most of the Animate wait can be avoided.** Every rerun re-reads the cached
   replay and re-serializes it to HTML, even when nothing about it changed.
   This is not ours to fix: it is **PERF-16**, in the other session (§8).

A figure that has finished on the server also takes a moment to draw in the
browser, and until it does the plot's iframe is blank white. A 361-frame replay
is a 14.8 MB page.

### Measurements

Measured on PoTeC, trial `0/b0` (412 fixations), before BUG-93 and PERF-15:

| Step | Time |
|---|---|
| Read PoTeC's raw frames (900 fixation files + AOIs) | 2.4 s |
| Normalize (404,420 fixations) | 0.8 s |
| Build the trial list (900 trials) | 0.02 s |
| Build the static figure | 1.6 s |
| Build the replay (361 frames) | 6.5 s |
| Serialize the replay to HTML (14.8 MB) | 3.1 s |
| Unpickle the cached replay on a `st.cache_data` hit | 2.1 s |

The other session measured an 18.8 s rerun on the demo's longest trial (2,001
frames): 8.9 s unpickling and most of the rest in `to_html`. OneStop's full
corpus is ~20× PoTeC's size; PERF-6's own note puts its normalization alone at
~20 s.

### The Streamlit behaviour this design relies on

All checked against the installed Streamlit 1.64:

- **A click abandons the running script at once.** With `runner.fastReruns`
  (the default), a widget interaction does not queue a rerun behind the current
  one. `AppSession.request_rerun` stops the current `ScriptRunner` and starts a
  new one immediately, in a new thread.
- **The abandoned run stops at its next checkpoint and cannot write state.**
  Every `st.*` call *and* every `st.session_state` read or write is a yield
  point (`SafeSessionState` calls `_yield_callback` first), where a stopped
  runner raises `StopException`.
- **Nothing the abandoned run sends reaches the page.** `AppSession` drops
  events from a non-current `ScriptRunner`
  (`_handle_scriptrunner_event_on_event_loop`: "This event was sent by a
  non-current ScriptRunner; ignore it").
- **Finished work is not wasted.** `st.cache_data` writes the result *inside*
  the spinner context, before the spinner's exit reaches a yield point, so a
  step the abandoned run completes is cached. The per-key `compute_value_lock`
  makes a new run that asks for the same value wait for the in-flight
  computation instead of starting another.
- **A side thread can update the page while the script thread is blocked.**
  `st.spinner` is a transient element shown after `DELAY_SECS = 0.5` by a
  `threading.Timer` carrying the script-run context. The card below uses the
  same mechanism.

## Scope

**In:**

1. **The loading component** — a Streamlit-free progress hook and a card
   (§1, UX-165).
2. **Calmer spinners everywhere else** (§1, UX-165).
3. **Dataset loads** — a page skeleton, a step list, in-flight sharing, and
   the restore on a fresh start (§2, UX-166).
4. **Plot placeholders for static and comparison figures** — the rail keeps its
   height (§3, UX-167).
5. **Cancel, and downloads that show progress and can be stopped** (§4,
   UX-168).
6. **The animation card with its frame count, and the in-frame placeholder**
   (§3, UX-169).

**Out:**

- **Caching the finished replay, and labelling GIF/MP4 exports from inputs** —
  PERF-16, in the other session.
- **Shrinking the replay page itself** (14.8 MB for 361 frames). A real cost,
  but a separate job; filed as **PERF-17** (#242).
- **Keeping the page fully usable during loads** (approach 2, background jobs).
  It restructures `main`'s single pipeline for no gain in cancelling, which
  fast reruns already make instant.
- **The Export panels' own progress display** (EXP-6's `st.status`), which
  stays as it is.

## 1. The loading component (UX-165)

### 1.1 `progress.py` — the hook

A new module with **no Streamlit import**, so `datasets.py` and `plots.py` can
call it and the headless API and CLI stay byte-identical.

```python
class Cancelled(Exception): ...


@contextmanager
def task(key, *, title: str, steps: Sequence[str] = ()) -> Iterator[Task]:
    """Register (or join) the task for ``key`` and make it this context's own."""


def report(
    done: int | None = None, total: int | None = None, *, detail: str | None = None
) -> None:
    """Update the active task's current step; a cancel checkpoint."""


def advance(label: str | None = None) -> None:
    """Finish the current step (recording its time) and start the next."""


def cancel(key) -> None:
    """Mark ``key``'s task cancelled; its next ``report``/``advance`` raises."""


def last_duration(key) -> float | None:
    """How long ``key`` took the last time it finished in this process."""
```

- **It does nothing unless something is watching.** With no active task,
  `report` and `advance` return at once. The API, the CLI and the tests that
  call loaders directly see no change.
- **The active task is a `ContextVar`,** which cached functions see because
  they run in the caller's thread and context.
- **Tasks live in a module-level registry keyed by task, not by run.** A run
  that starts while an abandoned run is still computing the same key joins its
  `Task`, so the card's counts carry on instead of resetting (§2.4). Each `Task`
  guards its fields with a lock, and readers take a snapshot.
- **`report` and `advance` are the cancel checkpoints.** After `cancel(key)`,
  the next call in the computing thread raises `Cancelled`, so the work stops
  within one file, frame or chunk (§4.3).
- **It creates no Streamlit elements.** The frame loop will run inside two
  nested `st.cache_data` functions since PERF-16, and elements created there
  are replayed on every cache hit. The hook only updates the record; the card
  is drawn from outside the cached call.

### 1.2 `loading.py` — the card

```python
with loading.card(slot, title="Building the animation",
                  size=(width, height),
                  cancel=Cancel("Show static plot", on_click=…),
                  key="single_anim") as task:
    ...  # the slow work, unchanged
```

**Look A:**

- a small spinner, the title and the elapsed time ("Building the animation ·
  4 s");
- a detail line ("Frame 120 of 361") or, for dataset loads, **B's step list**
  (§1.3);
- a thin progress bar, filling when a total is known and sliding otherwise;
- a Cancel button, secondary style, whose label says where it goes.

The card uses the app's own colours (`--sps-*`), with the accent blue only on
the bar, and works in the dark theme. Its icons are Material Symbols from
`constants.ICONS` (UX-138; `tests/test_icons.py`). Its title and current
step form a `role="status"` region with `aria-live="polite"` (the step
visually hidden there, since the detail line or step list shows it); the
elapsed time and the count sit outside it, so a screen reader hears each step
once rather than the clock at every refresh. Cancel is a real, focusable
button.

**Timing:**

- **Nothing shows for the first 0.5 s** — the same delay as Streamlit's
  spinner. Most reruns are fast and must not flash.
- **A card over work that is cheap on a cache hit waits for real work.** The
  dataset card, Compare's B card and the Corpus measures card open on every
  run, and on a big corpus a plain rerun's cache checks alone can outlast the
  delay. They are gated (`reveal_on_work`): past the delay, the timer reveals
  one only once its task has reported — a miss — checking again at each
  refresh. Every build they cover reports at the start of a miss: one with no
  loop to count calls a bare `report()` first thing, and a corpus reader
  reports "0 of N" before its first file. Waiting on another run's build in
  flight counts too: the waiter reports once before it waits.
- **The area holds its final size from the first instant,** so nothing jumps
  even when the card never appears (§2.2, §3.1).
- **The card refreshes about four times a second** — elapsed time, counts and
  steps.

**Mechanics:**

- **The script thread draws the card hidden when the block starts,** including
  its Cancel button. A widget has to be created on the script thread, and
  exactly once per run.
- **A timer thread reveals the card after the delay** and rewrites only its
  text and bar placeholders. It carries the script-run context, the way
  `st.spinner`'s timer does. The reveal is a marker element that the CSS keys
  on.
- **The block's exit clears the slot,** on a normal return, an early return or
  an exception.
- **An abandoned run's timer is harmless:** `AppSession` drops its messages.
- **`DELAY_S = 0` makes the reveal synchronous on the script thread,** which is
  how the headless app tests exercise a revealed card (§7).

### 1.3 The step list (dataset loads)

- **Finished steps** show ✓ and their own time.
- **The current step** shows a spinner and its count ("Reading files · 312 of
  900").
- **Later steps** are greyed out.
- **The title line** carries the total elapsed time and, when known, "last load:
  6 s" — `progress.last_duration` for the same dataset in this server process,
  recorded only by a load that did work and took at least the delay. There is
  no estimate otherwise.

### 1.4 Every other spinner

`styles.py`'s "Emphasised loading spinner" banner is replaced by the card's
calm look, applied to Streamlit's own `stSpinner`: the small spinner, the text,
no pulse and no gradient. Where Streamlit offers it, elapsed time goes on too:
`show_time=True` on `st.spinner`, and on the `st.cache_data` decorators whose
waits run long. Where a card is on screen, the spinners it covers are silenced
(`show_spinner=False` on the cached loaders the card wraps), so banners no
longer stack.

### 1.5 Slow work lets the server send

A CPU-bound build on the script thread holds the GIL, and the server's event loop needs several handoffs of it to
send one message, so a run's queue — the card's reveal included — used to
reach the browser only once the build ended (measured on the cold first
replay: the rail at 3.2 s, the card never). Inside a task, every checkpoint
therefore sleeps 1 ms at most every 25 ms (`progress.YIELD_EVERY_S` /
`YIELD_S`); measured again, the rail arrived at 0.6 s and the card showed on
time, counting frames.

## 2. Dataset loads (UX-166)

### 2.1 What the card covers

In `main`, one `loading.card` spans the dataset pipeline, from the load
([app.py:2628](../scanpath_studio/app.py:2628)) and `prepare_data`
([app.py:2985](../scanpath_studio/app.py:2985)) through the trial-identity
report to `build_combo_options`
([utils.py:45](../scanpath_studio/utils.py:45)). `main` calls `advance()` at
each boundary, and the loaders call `report()` inside a step.

| Source | Steps (with the count each reports) |
|---|---|
| PoTeC · MultiplEYE · OneStop (public, server bundle) · a prepared benchmark corpus | Reading files (*i* of *N*) → Normalizing *N* word rows and *M* fixations (words, fixations, cross-checks) → Building the trial list (*N* trials) |
| Bundled demo · synthetic trial | The same steps; in practice under 0.5 s, so never shown |
| An uploaded dataset already in the session | None — it opens instantly |
| A fresh start that restores large uploads from this computer | "Restoring your datasets from this computer" (*i* of *N* datasets), in its own card at the very top of the page, before the nav; no Cancel |

The figure is not a step. Once the trial list exists the real page appears,
and the plot shows its own card if the figure is slow (§3).

The count sources: `potec_raw_frames` reports per file, `multipleye_raw_frames`
per file, the OneStop readers per report part, and the benchmark reader per
Parquet file — each starting with "0 of N" before its first, so the card is
armed from the start. Counts are as fine as each loader's own loop, and a
source with no loop reports none, so its step shows no count.

### 2.2 Where it shows: the view's reserved area

The Scanpath and Corpus Analysis views render inside **one reserved area**,
`st.container(key="sps_view")`. It is created where `_view_bridge` is today
([app.py:6823](../scanpath_studio/app.py:6823)), before the Data page's
container.

- **Its first child is a placeholder created on every run,** which stays empty
  unless a load is slow. Its position is therefore stable, and it never replaces
  the view by accident.
- **During a slow load,** the timer fills that placeholder with a **skeleton of
  the view you are on** and the step-list card:
  - Scanpath: the selector row on `SELECTOR_ROW_GRID`'s tracks, the chip row,
    the plot box at the dataset's screen proportions (the registry's declared
    monitor, else the current canvas), and the rail, with the card centred on
    the plot box;
  - Corpus Analysis: the subtab bar and chart blocks.
- **While the skeleton shows, CSS hides everything after it in the area** —
  `.st-key-sps_view:has(.sps-page-skeleton)` hides its later siblings. That
  covers whatever sits below: the previous page, or the new one being laid out.
- **The skeleton outlives the card.** When the pipeline finishes, every step
  shows ✓ and the skeleton stays up. It comes down only once the new page has
  drawn its controls and its plot area's placeholder: the view calls
  `page.release()` as it enters its first slow region (the plot build in
  Scanpath, the charts in Corpus Analysis), and `main`'s dispatch calls it as
  a fallback. So the old page never flashes back between the skeleton and the
  new page.

```python
page = loading.page(view_area, view=active_view)  # reserves the placeholder
with page.card(title="Loading PoTeC", steps=[...], cancel=Cancel(...)):
    ...  # the dataset pipeline; main calls progress.advance() between steps
...
page.release()  # inside the view, as its first slow region starts
```
- **On the Data page,** the header and "Available datasets" still draw at once.
  The card sits in the dataset-table slot, with a few skeleton rows, until the
  table can be filled.

### 2.3 Switching views and datasets

- **Switching dataset from a page on screen** goes straight to the new page when
  it takes under 0.5 s. When it is slower, the skeleton replaces the old page:
  every number and control is about to change, so an honest skeleton beats a
  dimmed old dataset.
- **Switching view** reveals the skeleton of the *target* view at once, with no
  delay. A view switch always rebuilds the page, and the click needs an
  immediate answer — the reason today's `_view_bridge` exists.
- **Three mechanisms become one.** Today's `_view_bridge` ("Loading Corpus
  Analysis…") and `_finalizing_bridge` ("Dataset added — loading your
  scanpaths…", [app.py:7043](../scanpath_studio/app.py:7043)) are both replaced
  by this skeleton and card. BUG-81's "clear the bridges on every early return"
  becomes structural: the placeholder is recreated empty on every run.

### 2.4 Clicking during a load does not restart the work

- **`st.cache_data` already shares in-flight work** through its per-key lock
  (see *Context*).
- **`data.frame_cache` gets the same** ([data.py:132](../scanpath_studio/data.py:132)).
  It holds the normalized frames (PERF-6) and today has no in-flight guard, so
  a click during normalization starts a second normalization beside the first.
  A module-level registry keyed by *(session, slot, key)* holds an event per
  running build; a second caller waits on it and then reads the stored result.
- **The card attaches to the running task** (§1.1), so its counts carry on.

## 3. Figure builds (UX-167; UX-169 for the animation)

### 3.1 The plot stage

`plot_slot` becomes a **stage**, still keyed `tour_grp_plot` so the tour keeps
its target:

- **The warnings** that are written above the figure today move to their own
  slot just above the stage, so the figure's position no longer depends on
  them.
- **The stage's first child is the overlay slot,** created on every run. It
  holds the size placeholder and the card.
- **The figure is written as the stage's second child, and only once it is
  ready.** So a figure already on screen stays where it is until its
  replacement arrives.
- **CSS stacks the two in one grid cell,** with the card centred over the
  figure.

**The size.** The placeholder takes the figure's display size: the last figure
rendered under the same plot key (`single`, `single_anim`, `compare`), recorded
in session state when it is embedded, else an estimate from the canvas and the
display caps. It takes the true-scale iframe's fixed height — the figure's
height + 12; `html_embed.embed_html_iframe` passes an int to `st.iframe`, so the
row is exactly that tall at any column width — and the figure's own width,
capped by the column. The row keeps its height, and the rail with it; and since
the box also caps its card's container at the figure's width, the card centres
over the figure, not the column — with every width resolved from the column
down, so the card can neither overflow a narrow column nor collapse.

**The view keeps its place.** Streamlit matches a rerun's elements to the last
run's by position, so anything drawn only sometimes above the view — the page
chrome, a run's notices, the view area's own notices — sits inside a container
drawn every run; one element more above `sps_view` would otherwise drop the
whole view and redraw it from nothing.

### 3.2 Two cases

- **No figure on screen yet** — the first render in the view, or after a
  dataset load or a view switch: the overlay slot shows the plot-sized
  placeholder at once (blank, shimmering after 0.5 s), then the card.
- **A figure on screen** — stepping trials with ◀ ▶, changing a setting,
  switching Animate on: the overlay slot holds only the card. If the new figure
  takes over 0.5 s, the old one dims under the card; then the new figure
  replaces it in place. Stepping through trials stays continuous.

Both cases are one mechanism: the size box always sits in the stage's first
child. Unrevealed it is transparent and only holds the height; revealed it is a
translucent veil — over an old figure it reads as dimming, over an empty area
as a skeleton. No flag has to track whether a figure is on screen.

### 3.3 Per figure type

- **Static and comparison figures:** the placeholder and a card without a count
  (each is one build call) and without Cancel. They are short, and there is
  nothing sensible to go back to.
- **The animation (UX-169):** one card, replacing the two nested banners:
  "Building the animation · Frame 120 of 361", then "Preparing the player".
  - The count is one `progress.report(i, n)` in the replay's frame loop
    (`plots._render_scanpath_animation` after PERF-15).
  - After PERF-16 the replay's spinner belongs to the outer cache,
    `_cached_replay_view`; UX-169 sets its `show_spinner=False`, since the card
    replaces it.
  - On a cache hit no frame is built, so the card never appears.
  - Its task is keyed by what it is a replay *of*: the trial and its screen
    (and B's, for a co-replay) and the replay's own input key — `anim_key`, the
    replay cache's key, built with the clock fixed (PERF-15) and worked out
    before the card opens (`tabs._plan_replay`) — and remembered in
    `_sps_anim_task` while the build runs. Stepping to another trial or screen,
    or a setting that changes the frames (marker size, colours, saccades, the
    fixation flags or window, drift correction …), mid-build cancels the build
    of the replay no longer wanted; a speed or autoplay change keeps the key and
    joins it. A run that builds no replay —
    Animate switched off, or a trial with nothing to animate — cancels a
    remembered one too.
  - Cancel: "Show static plot" (§4).

### 3.4 Inside the plot's frame (UX-169)

`_TRUE_SCALE_TEMPLATE` ([tabs.py:443](../scanpath_studio/tabs.py:443)) gets a
skeleton at the figure's exact size, behind the plot:

- it fades in only after ~300 ms, so small figures do not flicker;
- it is removed on Plotly's first draw, detected the way `killNativeZoom`
  already polls for `gd._fullLayout`.

That covers the seconds a big replay page takes to parse and draw after the
server has finished.

## 4. Cancel (UX-168)

### 4.1 Where each Cancel goes

| Wait | Label | Effect |
|---|---|---|
| Dataset load, cold or switching | **Back to *previous dataset*** | Reopens the last dataset you had open in this session, instantly from cache. On a fresh start with nothing open yet, the Bundled demo. |
| Animation build | **Show static plot** | `single_animate = False`. |
| Compare's second dataset | **Compare within *A's dataset*** | Returns B to A's dataset (`cmp_dataset` = "This dataset"). |
| Corpus download (PoTeC, OneStop) | **Stop download** | Stops the transfer and deletes the partial `.part` file. |

- **"Previous dataset" is a new session value,** `_sps_last_loaded_source`:
  the `data_source_choice` written by every run that leaves a dataset on
  screen (`app._remember_open_dataset`) — a finished pipeline, the ✏️ Author
  editor (which opens no card), and the early returns for a mapping still to
  fix or a filter that emptied the pool; never the add-dataset wizard, which
  shows none. It holds
  the corpus label itself, and `resolve_data_source` re-derives
  `public_dataset_choice` from it. It is not the wizard's `_prev_source`, which only records
  where to return when leaving the add-dataset wizard. The callback writes
  through the existing pre-widget `_pending_source_choice` seam
  ([app.py:3678](../scanpath_studio/app.py:3678)).
- **After a dataset cancel,** `menu.notices` shows "Stopped loading PoTeC ·
  **Try again**". Try again re-selects that dataset through the same seam.
- **A slow rerun of the dataset already on screen offers no Cancel:** there is
  nothing to go back to. A view switch that lands on a load in flight shows
  that load's card, with its steps and Cancel — in flight meaning a live task
  still holds it (`progress.running`), not just that `_sps_dataset_task` is
  set: a run that ended by `st.stop()`, an exception or `st.rerun()` mid-load
  leaves the key behind with nothing computing it, and the switch after it
  shows the view's own skeleton.
- **After an animation cancel,** the Animate switch being off says what
  happened, so there is no notice.
- **Views and long computations** (Corpus Analysis charts, the Data page's
  statistics) get the card but **no Cancel**. The top nav stays clickable
  during any wait, and clicking it abandons the current work at once. For a
  view, going somewhere else *is* the change of mind; Cancel is reserved for
  choices with a clear previous state.

### 4.2 Downloads

`download_potec` and `download_onestop`
([datasets.py:87](../scanpath_studio/datasets.py:87),
[datasets.py:514](../scanpath_studio/datasets.py:514)) read each response in
one `response.read()`. They switch to reads of at most 1 MiB written to the
existing `.part` file, reporting bytes against `Content-Length` ("120 of 450
MB"). Each is a `read1`, which returns whatever has arrived — a `read` waits for
the whole MiB, so Stop could take ~10 s on a slow line — and the connection
times out after 60 s without data, so a stalled download ends too (an
`OSError`, which the ⬇ Download buttons report). A cancel deletes the `.part`
file. The atomic `.part` → final rename they already
do means a stopped download can never pass for a complete one — and it happens
only once the whole body has arrived: `read1` returns `b""` on an early EOF
exactly as at the real end, so a body shorter than its `Content-Length`, or a
chunked one cut short (`http.client.IncompleteRead`, not an `OSError`), is a
`ConnectionError`, and a cleanup that fails never masks it. PoTeC's zip is
then unpacked with a per-member count; a damaged one is a `ValueError`. `_dataset_access_status`'s and
`_render_dataset_unavailable`'s `st.spinner("Downloading into …")` become
download cards.

### 4.3 What happens to the interrupted work

- **An explicit Cancel stops it at the next checkpoint** (a file, a frame, a
  download chunk). The callback runs at the start of the new run: it restores
  the previous choice and calls `progress.cancel(key)`. The computing thread's
  next `report()` raises `Cancelled`, which frees the CPU for what the user
  picked instead. Steps that had already finished stay cached — if the files
  were read and the user cancelled during normalization, Try again skips the
  reading.
- **Any other click during a load does not cancel it.** The work continues,
  and the new run joins it (§2.4).
- **Picking a different dataset while one is loading counts as cancelling the
  first.** The new run sees the session's in-flight dataset task under a
  different key and cancels it, so two corpora never load at once. The same
  holds for Compare's B: its card's task is remembered in `_sps_compare_task`
  while B's dataset loads, so another dataset for B cancels it, and so does a
  run that loads nothing for B — "This dataset", a corpus not set up yet, or
  Compare switched off.
- **If Cancel lands just as the work finishes, Cancel still wins,** since the
  user asked to go back. The finished result stays cached, so Try again is
  instant.
- **Another session waiting on the same computation is unaffected:** when the
  cancelled thread releases the compute lock without a result, the waiting
  thread computes it itself.
- **`Cancelled` is caught by `loading.run_scope`,** which ends that run as a
  stopped one: it re-raises it as Streamlit's own `StopException`, so the run
  is a premature stop — no error on the page or in the server log, and
  Streamlit skips its stale-widget sweep, keeping the state of every widget the
  run never reached (a normal finish would drop it). Only an abandoned run ever
  computes a cancelled task — `progress.begin()` never joins a cancelled one,
  it starts afresh — so there is no page left to show anything on; the stop
  keeps a cut-short run from ever ending as a successful one.

## 5. The four-surface rule and the wire format

- **The four-surface rule does not apply.** Nothing here is a setting, toggle or
  parameter, so the deep link, the CLI and the API have nothing to expose. The
  progress hook does nothing without a watcher, so headless output is
  byte-identical. State this for `surface-parity-reviewer`.
- **No wire-format keys.** Loading state never travels in a link or a saved
  config. `_sps_last_loaded_source`, the recorded plot sizes and the in-flight
  bookkeeping are underscore-prefixed session internals, outside
  `session_keys.py`, like `share_identity_mode` before them. They are not
  persisted by the recovery cache.

## 6. Risks

- **Moving the views into `sps_view` adds one nesting level.** CSS and tour
  selectors are key-based (`.st-key-…`), so they should not care; the rail's
  column rules and `_SPOTLIGHT_STEPS` are checked by `tests/test_tour.py` and
  in the live check.
- **The card is drawn by a side thread.** This follows `st.spinner`'s own timer
  pattern, but it is still Streamlit-internal behaviour. The timer only
  rewrites placeholders the script thread created, and never creates a widget.
- **Every run now builds a hidden card** in each region it wraps — a few
  elements and one button. `perf-reviewer` measures the per-rerun cost.
- **`:has()` selectors.** Every supported browser has them, and `styles.py`
  already relies on them.

## 7. Tracking, delivery, testing, docs

### 7.1 IDs, commits and PRs

| ID | Part |
|---|---|
| UX-165 | Loading component and calmer spinners |
| UX-166 | Dataset loads: skeleton, step list, in-flight sharing |
| UX-167 | Plot placeholders; the rail keeps its height |
| UX-168 | Cancel, and downloads with progress |
| UX-169 | Animation card and in-frame placeholder |

- **One GitHub issue, `[UX-165] Loading states`,** holds this design and the
  review checklist. It spans five commits and a user review, so it needs one.
- **One commit per ID,** with the ID in the subject.
- **One PR, based on `main` at `1b25285` or later,** which includes PERF-15 and
  PERF-16. The design once split UX-169 into a second PR to wait for PERF-16;
  PERF-16 merged on 2026-09-26, before implementation began, so nothing waits.
- **Before a number is taken,** the registries are re-checked, the open PRs
  included. UX-164 was the highest on 2026-09-27.

### 7.2 Testing

- **`progress.py`:** does nothing without a watcher; counts and steps; `cancel`
  makes the next `report` raise; joining a running task; thread safety of
  snapshots.
- **`loading.py`:** the card and step-list markup, built from a pure state
  function; time formatting; placeholder sizing from a recorded or estimated
  size.
- **`frame_cache`:** two threads, one build.
- **Downloads:** a fake `urlopen` — chunked progress; a cancel mid-transfer
  leaves no `.part` file and no final file.
- **Headless app tests** (`AppTest`, with `DELAY_S = 0` to force the reveal):
  the app opens in each view; each Cancel callback restores the previous state;
  Try again re-selects the dataset; spinners never stack. Plus the existing
  `test_apptest.py`, `test_tour.py` and `test_icons.py`.
- **A live check at the end:** a cold PoTeC load, a dataset switch, Animate on,
  and each Cancel, with screenshots. It runs on a port other than 8511, with
  `SCANPATH_STUDIO_PERSIST=0`. Animation timing is measured only in headless
  Chrome, never in the hidden Browser pane (rAF there is throttled to ~1 Hz).
- **Before Review:** `perf-reviewer` and `surface-parity-reviewer`, the full
  suite under `uv run`, and `mkdocs build --strict`.

### 7.3 Docs

- **`AGENTS.md`'s architecture map and `scanpath_studio/CLAUDE.md`'s module
  list** gain `progress.py` and `loading.py`.
- **The Gotchas section** gains two rules:
  - wrap a new slow step in `loading.card` rather than `st.spinner`;
  - never create Streamlit elements inside the progress hook.
- **`CHANGELOG.md`** gets the two-tier entries per ID.
- **User docs** mention only what is user-visible and verified: the Cancel
  destinations, and the downloads' progress.

## 8. Coordination with PERF-16

The "Animation timing issue" session owns PERF-16: caching the finished
replay's page, and labelling GIF/MP4 exports from inputs rather than
`fig.to_json()`. It merged on 2026-09-26 as `1b25285` (PR #240, issue #239),
which is this design's base. It restructures
`_build_and_render_animation` around a new `_cached_replay_view`, splits
`_render_true_scale_chart` into `_true_scale_plot_html` +
`_render_true_scale_plot`, and changes `_render_animation_export`,
`_render_export_panel`, `_apply_preprocessing_caption`,
`export_status.static_export_signature` and `html_embed.embed_html_iframe`'s
fragment detection. The last is no concern here: the true-scale template stays
a fragment.

Where UX-169 builds on it:

1. **`_TRUE_SCALE_TEMPLATE` / `_true_scale_html`:** the PERF-16 cache stores the
   figure's own markup, and the template wrapper is still applied on every run,
   so the in-frame placeholder (§3.4) goes into the template.
2. **The `with plot_slot:` block in `render_single_trial_tab`:** it now reads
   `anim_view, save_slug, anim_file_stem = …` and passes `replay=anim_view` to
   the Export panel; the plot stage (§3.1) keeps both.
3. **The frame loop:** PERF-16 does not touch it. On a cached view no frame is
   built, and the hook's side-channel design (§1.1) keeps it out of Streamlit's
   replay.
4. **`_cached_replay_view`'s spinner:** a one-line change in PERF-16's new
   function — `show_spinner=False`, because the card takes over (§3.3).

The other session was told about items 1–4 before PERF-16 merged; check with it
before touching these functions, in case it has more work there.
