"""Every trace and shape of the scanpath figure is filed under the layer whose
switch draws it.

`plots._trace_layer` names a handful of layers by their traces' fixed names
and files everything else under fixations; `split_scanpath_layers` (the export's
separable layers) relies on it. A new top-level trace that is not given its
layer there lands in the fixations file. Here each layer switch is turned off
on a figure with every layer on: what disappears must be that layer's, and
something must.
"""

from __future__ import annotations

from collections import Counter

import pytest

from scanpath_studio import api, plots

#: Each layer switch, and the layer it draws.
SWITCHES = {
    "show_fixations": "fixations",
    "show_order": "fixations",
    "show_saccades": "saccades",
    "show_saccade_arrows": "saccades",
    "show_raw_gaze": "raw_gaze",
    "show_heatmap": "heatmap",
    "show_word_labels": "labels",
    "show_words": "word_boxes",
    "show_plot_frame": "frame",
}

#: Figures with every layer on, in each family of fixation traces: one flat
#: colour, a category legend, one trace per line, and flagged fixations.
VARIANTS = {
    "uniform": {},
    "category legend": {"color_by": "eye", "show_color_legend": True},
    "per line": {"color_by_line": True},
    "flagged": {"fixation_flags": {"oob": {"mode": "Highlight"}}},
}


@pytest.fixture(scope="module")
def demo():
    words, fixations = api.load_sample_data(names="canonical")
    raw_gaze = api.load_sample_raw_gaze(names="canonical")
    participant, trial = map(str, api.list_trials(words, fixations).iloc[0, :2])
    return words, fixations, raw_gaze, participant, trial


def _figure(demo, variant: dict, **off):
    words, fixations, raw_gaze, participant, trial = demo
    options = {**dict.fromkeys(SWITCHES, True), **variant, **off}
    return api.plot_scanpath(
        words, fixations, participant, trial, raw_gaze=raw_gaze, **options
    )


def _drawn(fig) -> Counter:
    """Each trace and shape, by what it is and the layer it is filed under."""
    traces = Counter(
        (
            trace.type,
            trace.name,
            getattr(trace, "mode", None),
            plots._trace_layer(trace),
        )
        for trace in fig.data
    )
    shapes = Counter(
        ("shape", shape.type, None, plots._shape_layer(shape))
        for shape in fig.layout.shapes or ()
    )
    return traces + shapes


def _only_its_layer(every: Counter, without: Counter, switch: str) -> None:
    gone = every - without
    assert gone, f"{switch}=False took nothing away"
    filed = {layer for (*_, layer) in gone}
    assert filed == {SWITCHES[switch]}, (
        f"{switch}=False took away {dict(gone)}, filed under {filed}; give each "
        "new trace its layer in plots._trace_layer (or tag a shape with "
        "plots._shape_layer_tag)"
    )


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("switch", SWITCHES)
def test_a_layer_switch_takes_away_only_its_own_layer(demo, switch, variant):
    every = _drawn(_figure(demo, VARIANTS[variant]))
    without = _drawn(_figure(demo, VARIANTS[variant], **{switch: False}))
    _only_its_layer(every, without, switch)


def _comparison(demo, layout: str, **off):
    """Two readings of one reader compared, every layer on: its traces are
    named by each scanpath's label, so they say their layer otherwise."""
    words, fixations, raw_gaze, _participant, _trial = demo
    trials = api.list_trials(words, fixations)
    a, b = (tuple(map(str, trials.iloc[i, :2])) for i in (0, 1))
    options = {**dict.fromkeys(SWITCHES, True), **off}
    return api.compare_scanpaths(
        words, fixations, a, b, raw_gaze=raw_gaze, layout=layout, **options
    )


@pytest.mark.parametrize("layout", ["overlay", "side_by_side"])
@pytest.mark.parametrize("switch", SWITCHES)
def test_a_comparisons_layer_switch_takes_away_only_its_own_layer(demo, switch, layout):
    every = _drawn(_comparison(demo, layout))
    without = _drawn(_comparison(demo, layout, **{switch: False}))
    _only_its_layer(every, without, switch)
