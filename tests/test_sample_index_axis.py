"""The sample-number axis works on samples recorded with a clock too.

Samples imported without a clock carry ``sample_index``; those with one are
numbered when a chart asks for it, so the axis ``render`` and the API offer
never draws an empty chart. In the app a chart whose field this reading lacks
falls back to the screen axes together, never to one field against itself.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api, chart_axes, cli
from scanpath_studio.constants import SAMPLE_INDEX

TRIAL = ("l37_273", "l37_273_2_2_2_Adv")
OTHER = ("l7_183", "l7_183_2_2_2_Adv")


@pytest.fixture(scope="module")
def demo():
    words, fixations = api.load_sample_data(names="canonical")
    samples = api.load_sample_raw_gaze(names="canonical")
    assert SAMPLE_INDEX not in samples and "timestamp_ms" in samples
    return words, fixations, samples


def _sample_trace(fig):
    return next(t for t in fig.data if t.name == "Raw gaze")


def test_plot_scanpath_numbers_timestamped_samples(demo):
    words, fixations, samples = demo
    fig = api.plot_scanpath(
        words,
        fixations,
        *TRIAL,
        raw_gaze=samples,
        x_field=SAMPLE_INDEX,
        y_field="x",
    )
    trial = samples[
        (samples.participant_id == TRIAL[0]) & (samples.trial_id == TRIAL[1])
    ]
    numbers = list(_sample_trace(fig).x)
    assert numbers and numbers == sorted(numbers)
    assert numbers[0] == 1 and numbers[-1] == len(trial)
    assert fig.layout.xaxis.title.text == "Sample #"


def test_the_comparison_numbers_each_readings_samples(demo):
    words, fixations, samples = demo
    fig = api.compare_scanpaths(
        words,
        fixations,
        TRIAL,
        OTHER,
        raw_gaze=samples,
        x_field=SAMPLE_INDEX,
        y_field="x",
    )
    clouds = [
        t
        for t in fig.data
        if t.mode == "markers" and t.x is not None and len(t.x) > 100
    ]
    assert len(clouds) == 2
    assert all(min(t.x) == 1 for t in clouds)


def test_render_draws_the_sample_axis(demo, monkeypatch):
    figures = []
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **_: figures.append(fig))
    cli.main(
        [
            "render",
            "--sample",
            "--sample-raw-gaze",
            "-p",
            TRIAL[0],
            "-t",
            TRIAL[1],
            "--x-field",
            SAMPLE_INDEX,
            "--y-field",
            "x",
            "-o",
            "unused.png",
        ]
    )
    assert len(_sample_trace(figures[0]).x) > 0


def test_numbering_follows_the_clock_per_reading_screen_and_eye():
    samples = pd.DataFrame(
        {
            "participant_id": ["p"] * 6,
            "trial_id": ["t"] * 6,
            "screen_id": ["a", "a", "b", "a", "b", "a"],
            "eye": ["L", "R", "L", "L", "L", "L"],
            "timestamp_ms": [30.0, 10.0, 5.0, 10.0, 1.0, float("nan")],
            "x": [1.0, float("nan"), 2.0, 3.0, 4.0, 5.0],
        },
        index=[7, 7, 3, 2, 1, 0],
    )
    numbered = chart_axes.with_sample_index(samples)
    assert list(numbered[SAMPLE_INDEX]) == [2, 1, 2, 1, 1, 3]
    assert numbered.index.equals(samples.index)
    # A clockless import's own numbers are kept.
    kept = samples.assign(**{SAMPLE_INDEX: range(10, 16)})
    assert chart_axes.with_sample_index(kept) is kept


def test_a_chart_field_the_reading_lacks_falls_back_with_its_pair():
    """A link's sample-number chart on samples that carry no such column
    opens on the screen axes, not horizontal position against itself."""
    import streamlit as st

    from scanpath_studio import controls

    words, fixations = api.load_sample_data(names="canonical")
    samples = api.load_sample_raw_gaze(names="canonical")
    pick = (fixations.participant_id == TRIAL[0]) & (fixations.trial_id == TRIAL[1])
    trial_samples = samples[
        (samples.participant_id == TRIAL[0]) & (samples.trial_id == TRIAL[1])
    ]
    st.session_state.clear()
    st.session_state["global_x_field"] = SAMPLE_INDEX
    st.session_state["global_y_field"] = "x"
    controls._seed_viz_state(fixations[pick], 16, words, trial_samples)
    assert (st.session_state["global_x_field"], st.session_state["global_y_field"]) == (
        "x",
        "y",
    )
    # A chart the reading can draw is kept.
    st.session_state["global_x_field"] = "timestamp_ms"
    st.session_state["global_y_field"] = "pupil_area"
    controls._seed_viz_state(fixations[pick], 16, words, trial_samples)
    assert (st.session_state["global_x_field"], st.session_state["global_y_field"]) == (
        "timestamp_ms",
        "pupil_area",
    )
    st.session_state.clear()
