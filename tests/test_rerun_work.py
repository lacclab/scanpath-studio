"""What a rerun costs, on every view and panel.

Streamlit reruns the whole script on every click. The data work — reading and
normalizing tables, assigning fixations to words, the trial pool, the corpus
summaries, the data checks — is cached so a rerun skips it; a step that
misses its cache makes every click slower on a large corpus. Each view and
panel is drawn, then rerun: a rerun that changes nothing does no work at all,
and one that changes a plot setting only redraws the figure.

Three signals are counted:
- every miss of a `st.cache_data` / `st.cache_resource` function, by name, and
  every `data.frame_cache` build, by slot;
- the expensive data functions themselves, wherever they are imported, for
  work done outside any cache;
- `progress.report`, which a slow step calls while it works.

What runs while a figure builder draws is that figure's drawing, but it must
stay the size of a trial: the tables a builder is handed and the data work it
does hold a few trials' rows, and its gaze samples two readings'. A builder
handed the whole corpus would make every redraw corpus-sized.
"""

from __future__ import annotations

import sys
from collections import Counter

import pandas as pd
import pytest
from streamlit.runtime.caching import cache_utils
from streamlit.testing.v1 import AppTest

import scanpath_studio.app  # noqa: F401 — every importer exists before the patch
from scanpath_studio import aggregation, api, data, measures, plots, progress
from scanpath_studio import metadata as md
from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    DATA_INSPECTION_KEY,
)
from scanpath_studio.controls import trial_metadata_filter_key
from scanpath_studio.session_keys import CORPUS_SUBTAB
from tests.conftest import APP_SCRIPT, pin_view

#: The data work a rerun must not redo outside a cache.
DATA_WORK = [
    (data, "normalize_words"),
    (data, "normalize_fixations"),
    (data, "normalize_raw_gaze"),
    (data, "harmonize_frames"),
    (data, "infer_word_schema"),
    (data, "infer_fix_schema"),
    (data, "filter_to_keys"),
    (data, "trial_keys"),
    (measures, "compute_per_word_measures"),
    (measures, "enrich_fixations"),
    (measures, "assign_fixations_to_words"),
    (aggregation, "corpus_overview"),
]
#: The figure builders: a plot setting may redraw, nothing else may.
FIGURE_WORK = [
    (plots, "make_scanpath_figure"),
    (plots, "make_scanpath_animation"),
    (plots, "build_scanpath_replay"),
    (plots, "make_comparison_figure"),
]
#: The most rows a figure builder's tables, or the data work it does, may hold:
#: a few trials' worth, far below the bundled demo's whole corpus (about 1,700
#: fixations, 2,400 words).
TRIAL_ROWS = 1000
#: The most gaze samples a builder may be handed: Compare's two readings (the
#: demo's longest has about 25,500), far below the demo's 401,200.
TRIAL_SAMPLES = 60_000


_WORDS, _FIXATIONS = api.load_sample_data(names="canonical")
_STAR = {"star": True, "tags": [], "note": ""}


def _demo_reading(row: int = 0) -> tuple[str, str]:
    return tuple(map(str, api.list_trials(_WORDS, _FIXATIONS).iloc[row, :2]))


def _trial_halves():
    """A trial metadata table splitting the demo's trials in two by ``half``."""
    ids = sorted(_FIXATIONS["trial_id"].astype(str).unique())
    halves = ["x" if i % 2 else "y" for i in range(len(ids))]
    frame = pd.DataFrame({"trial_id": ids, "half": halves})
    return md.build_trial_metadata(frame, "trial_id", source_name="trials.csv")


def _subtab(name: str) -> str:
    from scanpath_studio.tabs import subtab_labels_for

    return next(
        label
        for label in subtab_labels_for(False, line_assignment=False)
        if label.endswith(name)
    )


_READING = _demo_reading()

VIEWS = {
    "scanpath": (_VIEW_SCANPATH, {}),
    **{
        f"scanpath · {name}": (_VIEW_SCANPATH, {"single_subtab": _subtab(name)})
        for name in ("Stimulus & context", "Comparisons", "Export", "Share")
    },
    "scanpath · filtered": (
        _VIEW_SCANPATH,
        {"trial_annotations": {_READING: _STAR}},
        # Filters are seeded on the first run, so they are set after it.
        {"filter_participants": [_READING[0]], "filter_favorites": True},
    ),
    "scanpath · trial metadata filter": (
        _VIEW_SCANPATH,
        {md.TRIAL_SESSION_KEY: _trial_halves()},
        {trial_metadata_filter_key("half"): ["x"]},
    ),
    "replay": (_VIEW_SCANPATH, {"single_animate": True}),
    "compare": (_VIEW_SCANPATH, {"single_compare_toggle": True}),
    "compare · B filtered": (
        _VIEW_SCANPATH,
        {
            "single_compare_toggle": True,
            "trial_annotations": {_READING: _STAR, _demo_reading(1): _STAR},
        },
        {"cmpfilter_favorites": True},
    ),
    **{
        f"corpus · {name}": (_VIEW_CORPUS, {CORPUS_SUBTAB: name})
        for name in ("Overview", "Per text", "Per participant", "Groups")
    },
    **{
        f"data · {name}": (_VIEW_DATA, {DATA_INSPECTION_KEY: name})
        for name in ("Overview", "Tables", "Data checks", "Annotations")
    },
}

#: Work that runs on every rerun of a view today, each with why. It must keep
#: running there, so an entry is dropped once it stops.
UNCACHED: dict[str, dict[str, str]] = {}

#: The caches a figure is drawn through: a plot setting misses them by design.
FIGURE_CACHES = (
    "_cached_scanpath_figure",
    "_cached_comparison_figure",
    "_cached_scanpath_animation",
    "_cached_replay_view",
    "_cached_panel_figure",
)


class Work(Counter):
    """Counts of the work done, the most rows a figure's tables or its data
    work held, and the most gaze samples a builder was handed."""

    drawn_rows = 0
    drawn_samples = 0

    def reset(self) -> None:
        self.clear()
        self.drawn_rows = self.drawn_samples = 0

    def check_drawn_sizes(self) -> None:
        assert self.drawn_rows <= TRIAL_ROWS, (
            f"a figure drew from {self.drawn_rows} rows, more than a trial's"
        )
        assert self.drawn_samples <= TRIAL_SAMPLES, (
            f"a figure was handed {self.drawn_samples} gaze samples, more than "
            "two readings'"
        )


@pytest.fixture()
def work(monkeypatch) -> Work:
    calls = Work()
    drawing: list[bool] = []

    def rows(args, kwargs) -> int:
        frames = [a for a in (*args, *kwargs.values()) if isinstance(a, pd.DataFrame)]
        return max((len(frame) for frame in frames), default=0)

    def record(name: str, args=(), kwargs=None) -> None:
        if drawing:
            calls["drawing"] += 1
            calls.drawn_rows = max(calls.drawn_rows, rows(args, kwargs or {}))
        else:
            calls[name] += 1

    def wrap(name, original, *, builder):
        def counting(*args, **kwargs):
            if not builder:
                record(name, args, kwargs)
            else:
                calls[name] += 1
                samples = kwargs.get("raw_gaze")
                tables = {k: v for k, v in kwargs.items() if k != "raw_gaze"}
                calls.drawn_rows = max(calls.drawn_rows, rows(args, tables))
                if isinstance(samples, pd.DataFrame):
                    calls.drawn_samples = max(calls.drawn_samples, len(samples))
            drawing.append(builder)
            try:
                return original(*args, **kwargs)
            finally:
                drawing.pop()

        counting.__wrapped__ = original
        return counting

    for module, name in DATA_WORK + FIGURE_WORK:
        original = getattr(module, name)
        counting = wrap(name, original, builder=(module, name) in FIGURE_WORK)
        for loaded in list(sys.modules.values()):
            if getattr(loaded, name, None) is original:
                monkeypatch.setattr(loaded, name, counting)

    real_miss = cache_utils.CachedFunc._handle_cache_miss

    def miss(self, cache, value_key, func_args, func_kwargs):
        record(f"miss in {self._info.func.__qualname__}", func_args, func_kwargs)
        return real_miss(self, cache, value_key, func_args, func_kwargs)

    monkeypatch.setattr(cache_utils.CachedFunc, "_handle_cache_miss", miss)

    real_shared_build = data._shared_build

    def shared_build(ident, build, **kwargs):
        def counted_build():
            record(f"build {ident[1]}")
            return build()

        return real_shared_build(ident, counted_build, **kwargs)

    monkeypatch.setattr(data, "_shared_build", shared_build)

    real_report = progress.report

    def report(*args, **kwargs):
        record(f"report in {sys._getframe(1).f_code.co_name}")
        return real_report(*args, **kwargs)

    for loaded in list(sys.modules.values()):
        if getattr(loaded, "report", None) is real_report:
            monkeypatch.setattr(loaded, "report", report)
    return calls


def _drawn(view: str, state: dict, then: dict | None = None) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    for key, value in state.items():
        at.session_state[key] = value
    pin_view(at, view)
    at.run()
    for key, value in (then or {}).items():
        at.session_state[key] = value
    at.run()
    at.run()
    assert not at.exception, at.exception
    for key, value in (then or {}).items():
        assert at.session_state[key] == value, f"{key} did not hold"
    return at


@pytest.mark.timeout(300)
@pytest.mark.parametrize("view", VIEWS)
def test_a_rerun_that_changes_nothing_does_no_work(view, work):
    at = _drawn(*VIEWS[view])
    work.reset()
    at.run()
    assert not at.exception, at.exception
    known = UNCACHED.get(view, {})
    redone = {name: n for name, n in work.items() if name not in {*known, "drawing"}}
    assert not redone, f"a rerun with nothing changed redid: {redone}"
    stopped = set(known) - set(work)
    assert not stopped, f"no longer redone on a rerun; drop from UNCACHED: {stopped}"
    work.check_drawn_sizes()


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    "view", ["scanpath", "replay", "compare", "scanpath · Comparisons"]
)
def test_a_plot_setting_only_redraws_the_figure(view, work):
    at = _drawn(*VIEWS[view])
    work.reset()
    at.session_state["global_saccade_width"] = 3.5
    at.run()
    assert not at.exception, at.exception
    figure = {name for _module, name in FIGURE_WORK} | {"drawing"}
    figure |= {f"miss in {name}" for name in FIGURE_CACHES}
    redone = {name: n for name, n in work.items() if name not in figure}
    assert not redone, f"a plot setting redid data work: {redone}"
    # The redraw is what puts a builder's own tables on the scale.
    assert work.keys() & {name for _module, name in FIGURE_WORK}, "nothing redrew"
    work.check_drawn_sizes()
