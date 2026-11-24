"""What a rerun costs, on every view.

Streamlit reruns the whole script on every click. The data work — reading and
normalizing tables, assigning fixations to words, the trial pool, the corpus
summaries — is cached on fingerprints so a rerun skips it; a step that
misses its cache, or a new frame built outside one, makes every click slower
on a large corpus. Each view is drawn, then rerun: a rerun that changes
nothing does no work at all, and one that changes a plot setting only redraws
the figure.

Two signals are counted. The expensive functions themselves, wherever they
are imported. And `progress.report`, which a cached step calls when it misses
and does real work, so it counts the misses of every step that follows that
convention.
"""

from __future__ import annotations

import sys
from collections import Counter

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import aggregation, data, measures, plots, progress
from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_DATA, _VIEW_SCANPATH
from tests.conftest import APP_SCRIPT, pin_view

#: The data work a rerun must not redo.
DATA_WORK = [
    (data, "normalize_words"),
    (data, "normalize_fixations"),
    (data, "normalize_raw_gaze"),
    (data, "harmonize_frames"),
    (data, "infer_word_schema"),
    (data, "infer_fix_schema"),
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

VIEWS = {
    "scanpath": (_VIEW_SCANPATH, {}),
    "replay": (_VIEW_SCANPATH, {"single_animate": True}),
    "compare": (_VIEW_SCANPATH, {"single_compare_toggle": True}),
    "corpus analysis": (_VIEW_CORPUS, {}),
    "data": (_VIEW_DATA, {}),
}


#: Figure work that runs on every rerun of a view today, each with why. It
#: must keep running there, so an entry is dropped once it stops.
UNCACHED = {
    "compare": {
        "make_comparison_figure": "the comparison figure is drawn uncached: "
        "about 50–115 ms a rerun on the demo, more with heatmaps on a full page",
    },
}

#: The steps that draw a replay: their cache misses are the figure's.
_FIGURE_STEPS = {"_render_scanpath_animation"}


@pytest.fixture()
def work(monkeypatch) -> Counter:
    """Calls to the expensive functions, wherever they are imported, and the
    cache misses `progress.report` announces, by the function that missed.
    What runs while a figure builder draws counts as that figure's drawing."""
    calls: Counter = Counter()
    drawing = []

    def wrap(name, original, *, builder):
        def counting(*args, **kwargs):
            calls["drawing" if drawing and not builder else name] += 1
            drawing.append(builder)
            try:
                return original(*args, **kwargs)
            finally:
                drawing.pop()

        return counting

    for module, name in DATA_WORK + FIGURE_WORK:
        original = getattr(module, name)
        counting = wrap(name, original, builder=(module, name) in FIGURE_WORK)
        for loaded in list(sys.modules.values()):
            if getattr(loaded, name, None) is original:
                monkeypatch.setattr(loaded, name, counting)
    real_report = progress.report

    def report(*args, **kwargs):
        step = sys._getframe(1).f_code.co_name
        drawn = drawing or step in _FIGURE_STEPS
        calls["drawing" if drawn else f"miss in {step}"] += 1
        return real_report(*args, **kwargs)

    monkeypatch.setattr(progress, "report", report)
    return calls


def _drawn(view: str, state: dict) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    for key, value in state.items():
        at.session_state[key] = value
    pin_view(at, view)
    at.run()
    at.run()
    assert not at.exception, at.exception
    return at


@pytest.mark.timeout(300)
@pytest.mark.parametrize("view", VIEWS)
def test_a_rerun_that_changes_nothing_does_no_work(view, work):
    at = _drawn(*VIEWS[view])
    work.clear()
    at.run()
    assert not at.exception, at.exception
    known = UNCACHED.get(view, {})
    redone = {name: n for name, n in work.items() if name not in {*known, "drawing"}}
    assert not redone, f"a rerun with nothing changed redid: {redone}"
    stopped = set(known) - set(work)
    assert not stopped, f"no longer redone on a rerun; drop from UNCACHED: {stopped}"


@pytest.mark.timeout(300)
@pytest.mark.parametrize("view", ["scanpath", "replay", "compare"])
def test_a_plot_setting_only_redraws_the_figure(view, work):
    at = _drawn(*VIEWS[view])
    work.clear()
    at.session_state["global_saccade_width"] = 3.5
    at.run()
    assert not at.exception, at.exception
    figure = {name for _module, name in FIGURE_WORK} | {"drawing"}
    redone = {name: n for name, n in work.items() if name not in figure}
    assert not redone, f"a plot setting redid data work: {redone}"
    assert work.keys() & figure, "the plot setting redrew nothing"
