"""VIZ-48: Compare mode draws each reading's raw gaze under its scanpath."""

from __future__ import annotations

import pandas as pd
import pytest

import scanpath_studio.api as sps
from scanpath_studio import cli
from scanpath_studio.constants import compare_palette_color
from scanpath_studio.tabs import _raw_gaze_missing_note

PID = "l37_1129"
A = (PID, "l37_1129_2_2_2_Adv_r0")  # the trial the demo's samples belong to
B = (PID, "l37_1129_2_1_1_Ele_r0")


@pytest.fixture(scope="module")
def demo():
    words, fixations = sps.load_sample_data(names="canonical")
    return words, fixations, sps.load_sample_raw_gaze(names="canonical")


@pytest.fixture(scope="module")
def both_samples(demo):
    """The demo's samples for A, plus a shifted copy standing in for B's."""
    raw = demo[2]
    return pd.concat([raw, raw.assign(trial_id=B[1], x=raw["x"] + 5)])


def _raw_traces(fig):
    return [t for t in fig.data if t.name and t.name.endswith("raw gaze")]


@pytest.mark.parametrize("layout", ["overlay", "side_by_side", "stacked"])
def test_each_reading_draws_its_own_samples_in_its_colour(demo, both_samples, layout):
    words, fixations, _ = demo
    fig = sps.compare_scanpaths(
        words, fixations, A, B, raw_gaze=both_samples, layout=layout
    )
    traces = _raw_traces(fig)
    assert len(traces) == 2
    a_samples = both_samples[both_samples["trial_id"] == A[1]]
    assert list(traces[0].x) == list(a_samples["x"])
    # Each in its scanpath's own colour — the A/B cue — not one time ramp.
    assert [t.marker.color for t in traces] == [
        compare_palette_color(0),
        compare_palette_color(1),
    ]
    if layout != "overlay":
        assert [t.xaxis for t in traces] == ["x", "x2"]


def test_samples_sit_under_both_scanpaths_in_an_overlay(demo, both_samples):
    words, fixations, _ = demo
    fig = sps.compare_scanpaths(words, fixations, A, B, raw_gaze=both_samples)
    names = [t.name or "" for t in fig.data]
    raw_at = [i for i, n in enumerate(names) if n.endswith("raw gaze")]
    first_scanpath = min(
        i for i, t in enumerate(fig.data) if t.legendgroup and i not in raw_at
    )
    assert max(raw_at) < first_scanpath


def test_the_size_and_opacity_settings_apply(demo):
    words, fixations, raw = demo
    fig = sps.compare_scanpaths(
        words,
        fixations,
        A,
        B,
        raw_gaze=raw,
        raw_gaze_marker_size=7.0,
        raw_gaze_opacity=0.3,
    )
    (trace,) = _raw_traces(fig)
    assert trace.marker.size == 7.0
    assert trace.marker.opacity == 0.3


def test_the_layer_can_be_switched_off(demo, both_samples):
    words, fixations, _ = demo
    fig = sps.compare_scanpaths(
        words, fixations, A, B, raw_gaze=both_samples, show_raw_gaze=False
    )
    assert not _raw_traces(fig)


def test_a_trial_compared_with_itself_draws_its_samples_twice(demo):
    words, fixations, raw = demo
    fig = sps.compare_scanpaths(words, fixations, A, A, raw_gaze=raw)
    traces = _raw_traces(fig)
    assert [len(t.x) for t in traces] == [len(raw), len(raw)]


def test_a_second_dataset_takes_its_own_samples(demo):
    words, fixations, raw = demo
    common = dict(words_b=words, fixations_b=fixations, layout="side_by_side")
    only_a = sps.compare_scanpaths(words, fixations, A, A, raw_gaze=raw, **common)
    assert len(_raw_traces(only_a)) == 1
    both = sps.compare_scanpaths(
        words, fixations, A, A, raw_gaze=raw, raw_gaze_b=raw, **common
    )
    assert len(_raw_traces(both)) == 2


def test_the_cli_draws_raw_gaze_in_a_comparison(tmp_path, capsys):
    out = tmp_path / "compare.html"
    cli.main(
        [
            "render",
            "--sample",
            "--sample-raw-gaze",
            "-p",
            A[0],
            "-t",
            A[1],
            "--compare-with",
            f"{B[0]}:{B[1]}",
            "-o",
            str(out),
        ]
    )
    assert "raw gaze" in out.read_text()
    assert "no raw-gaze layer" not in capsys.readouterr().err


def test_compare_raw_gaze_needs_a_second_dataset(tmp_path):
    with pytest.raises(SystemExit, match="second dataset's raw gaze"):
        cli.main(
            [
                "render",
                "--sample",
                "-p",
                A[0],
                "-t",
                A[1],
                "--compare-with",
                f"{B[0]}:{B[1]}",
                "--compare-raw-gaze",
                str(tmp_path / "gaze.csv"),
                "-o",
                str(tmp_path / "out.html"),
            ]
        )


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (True, True, ""),
        (True, False, "Raw gaze not available for scanpath B."),
        (False, True, "Raw gaze not available for scanpath A."),
        (False, False, "Raw gaze not available for either trial."),
    ],
)
def test_the_missing_samples_note_names_the_reading(a, b, expected):
    assert (
        _raw_gaze_missing_note(
            True, trial_has_raw_gaze=a, comparing=True, compare_has_raw_gaze=b
        )
        == expected
    )


def test_the_note_outside_compare_names_this_trial():
    assert _raw_gaze_missing_note(False, trial_has_raw_gaze=False) == ""
    # VIZ-50 reworded it; tests/test_raw_gaze_provenance.py pins the wording.
    assert "this trial" in _raw_gaze_missing_note(True, trial_has_raw_gaze=False)


def test_compare_raw_gaze_needs_compare_with(tmp_path):
    with pytest.raises(SystemExit, match="pass --compare-with"):
        cli.main(
            [
                "render",
                "--sample",
                "--compare-raw-gaze",
                str(tmp_path / "gaze.csv"),
                "-o",
                str(tmp_path / "out.html"),
            ]
        )


def test_the_rail_peeks_at_bs_dataset_for_samples():
    """VIZ-48: the rail is drawn before B loads, so whether B's dataset has
    raw gaze is read without loading it."""
    import streamlit as st

    from scanpath_studio.compare_source import THIS_DATASET, source_has_raw_gaze
    from scanpath_studio.constants import DEMO_CHOICE

    st.session_state["_datasets"] = {
        "with": {"raw_gaze": pd.DataFrame({"x": [1.0]})},
        "without": {"raw_gaze": pd.DataFrame()},
    }
    try:
        assert source_has_raw_gaze(DEMO_CHOICE)
        assert source_has_raw_gaze("with")
        assert not source_has_raw_gaze("without")
        assert not source_has_raw_gaze(THIS_DATASET)
        assert not source_has_raw_gaze("PoTeC — Potsdam Textbook Corpus")
    finally:
        del st.session_state["_datasets"]


def test_a_snippet_whose_samples_are_all_bs_loads_none_for_a():
    from scanpath_studio import code_snippet as cs

    state = cs.FigureState(
        kind="comparison",
        settings={**sps.figure_options("comparison"), "show_raw_gaze": True},
        participant="p1",
        trial="t1",
        compare=cs.CompareTarget(
            participant="p2",
            trial="t2",
            dataset="Lab B",
            raw_gaze=("b.csv",),
            primary_raw_gaze=False,
        ),
    )
    code = cs.reproduction_code(cs.SnippetSource(kind=cs.SOURCE_DEMO), state)
    assert "raw_gaze = " not in code.python
    assert "raw_gaze_b = sps.load_raw_gaze('b.csv')" in code.python
    assert "--sample-raw-gaze" not in code.cli
    assert "--compare-raw-gaze b.csv" in code.cli
