from __future__ import annotations

import gc
import json
import weakref

import pandas as pd
import pytest

from scanpath_studio import aggregation as agg
from scanpath_studio import cohort_audit, study_checks, utils
from scanpath_studio.data import filter_to_keys
from scanpath_studio.experimental_setup import Provenance, SetupSnapshot
from scanpath_studio.tabs import remap_reading_changes
from tests.conftest import APP_SCRIPT, pin_view


@pytest.mark.parametrize(
    ("section", "compare", "normalize"),
    [
        ("Per participant", False, "prdr7_norm"),
        ("Groups", False, "pgrp14_norm"),
        ("Groups", True, "cmp18_norm"),
    ],
)
def test_distribution_chart_labels_follow_normalization(section, compare, normalize):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_SCRIPT)
    pin_view(at, "Corpus Analysis")
    at.session_state["corpus_subtab"] = section
    at.session_state["groups_compare"] = compare
    if section == "Groups" and compare:
        at.session_state["cmp_view"] = "Overlaid distributions"
    at.run(timeout=60)
    if section == "Per participant":
        settings = next(
            p for p in at.get("popover") if p.proto.popover.label == "Chart settings"
        )
        assert settings.selectbox(key="prdr_view").value == "Distribution vs cohort"
        assert {s.key for s in settings.selectbox} == {"prdr_view", "prdr7_kind"}
        assert {s.key for s in at.selectbox} >= {"prdr_pid", "prdr_measure"}
    for normalized in (False, True):
        if normalized:
            at.toggle(key=normalize).set_value(True).run(timeout=60)
        assert not at.exception
        (chart,) = at.get("plotly_chart")
        layout = json.loads(chart.proto.spec)["layout"]
        label = agg.MEASURES["tfd"].value_label(normalized)
        assert layout["yaxis"]["title"]["text"] == label
        assert layout["title"]["text"] == f"{label} distribution"


def test_insufficient_word_breaks_profile_and_uncertainty_band():
    from scanpath_studio.plots import make_word_profile_figure

    table = pd.DataFrame(
        {
            "word_id": [3, 4, 5],
            "value": [1.0, 2.0, 3.0],
            "lo": [0.0, 1.0, 2.0],
            "hi": [2.0, 3.0, 4.0],
            "enough": [True, False, True],
        }
    )
    fig = make_word_profile_figure(
        {"Cohort": table},
        measure_label=agg.MEASURES["tfd"].value_label(True),
        spread_label="95% bootstrap CI",
        canvas_width=600,
        base_font_size=14,
        font_family="Arial",
    )
    bands = [list(t.x) for t in fig.data if t.fill == "toself"]
    assert bands == [[3, 3], [5, 5]]
    assert pd.isna(fig.data[-1].y[1])
    assert "SD units" in fig.layout.yaxis.title.text
    assert "95% bootstrap CI" in fig.layout.title.text


def test_containment_tiles_and_short_only_flags(monkeypatch):
    import numpy as np

    from scanpath_studio import measures, plots

    boxes = pd.DataFrame({"x": np.arange(4500), "y": 0.0, "width": 1.0, "height": 1.0})
    fix = pd.DataFrame(
        {
            "x": [0.0, 4499.9, 4500.0, np.nan] * 75,
            "y": 0.0,
            "duration_ms": [10, 100, 10, 100] * 75,
        }
    )
    original = measures.word_box_contains
    cells = []

    def measure_tiles(x, y, x0, y0, x1, y1):
        cells.append(x.size * x0.size)
        return original(x, y, x0, y0, x1, y1)

    monkeypatch.setattr(measures, "word_box_contains", measure_tiles)
    masks = plots._fixation_flag_masks(fix, boxes, {"short": {"mode": "Hide"}})
    assert set(masks) == {"short"} and masks["short"].sum() == 150
    assert cells == []
    assert measures._in_any_box(fix, boxes).tolist() == [True, True, False, False] * 75
    assert max(cells) <= 262_144


def test_run_sheet_keeps_parent_screen_and_raw_only_readings_separate():
    expected = pd.DataFrame(
        [
            ["01", "T", "", ""],
            ["1", "T", "left", ""],
            ["1", "T", "right", ""],
            ["NA", "T", "", "session canceled"],
        ],
        columns=["participant_id", "trial_id", "screen_id", "planned_omission"],
    )
    gaze = pd.DataFrame(
        [["01", "T", "x"], ["1", "T", "right"], ["extra", "T", "1"]],
        columns=expected.columns[:3],
    )
    report = study_checks.reconcile_run_sheet(expected, {"raw_gaze": gaze}).set_index(
        list(expected.columns[:3])
    )
    assert report.loc[("01", "T", ""), "status"] == "Raw gaze only"
    assert report.loc[("1", "T", "left"), "status"] == "Missing"
    assert report.loc[("1", "T", "right"), "tables"] == "raw_gaze"
    assert report.loc[("NA", "T", ""), "status"] == "Planned omission"
    assert report.loc[("extra", "T", "1"), "status"] == "Unscheduled"
    assert len(report) == 5


def test_changed_time_header_names_the_file_and_conversion():
    rows = study_checks.compare_file_mapping(
        "session2.csv",
        ["reader", "Duration [s]"],
        {"participant": "reader", "duration": "Duration [ms]"},
    )
    assert len(rows) == 1
    assert rows[0]["file"] == "session2.csv"
    assert "×1000" in rows[0]["finding"]


def test_inclusion_reports_overlapping_failures_once():
    keys = ["participant_id", "trial_id"]
    data = pd.DataFrame([["01", "t1"], ["01", "t2"], ["1", "t1"]], columns=keys)
    first = {("01", "t1"), ("1", "t1")}
    second = {("01", "t1")}
    steps = [
        ("condition", lambda w, f: filter_to_keys(w, f, first), ()),
        ("exclude tag", lambda w, f: filter_to_keys(w, f, second), ()),
    ]
    counts, report = study_checks.inclusion_report(
        data, data.iloc[:0], first & second, steps
    )
    assert list(counts["readings"]) == [3, 1, 2]
    assert list(counts["participants"]) == [2, 1, 1]
    assert (
        report.set_index(keys).loc[("01", "t2"), "exclusion_reasons"]
        == "condition · exclude tag"
    )


def test_the_open_inclusion_report_is_reused_until_what_it_reads_changes(
    monkeypatch,
):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import api, app

    app._c_inclusion_report.clear()
    reports = []
    original = study_checks.inclusion_report

    def counted(*args, **kwargs):
        reports.append(original(*args, **kwargs))
        return reports[-1]

    monkeypatch.setattr(study_checks, "inclusion_report", counted)
    _, fixations = api.load_sample_data(names="canonical")
    first, other = (
        (p, str(fixations.loc[fixations["participant_id"].eq(p), "trial_id"].iloc[0]))
        for p in ("l7_183", "l37_273")
    )
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.session_state["filter_participants"] = [first[0]]
    at.run()
    pin_view(at, "Corpus Analysis")
    at.session_state["corpus_pool_popover"] = True
    at.session_state["study_inclusion"] = True
    at.run()
    assert not at.exception
    assert len(reports) == 1
    assert reports[-1][0]["readings"].tolist() == [24, 12, 12]
    at.run()
    assert len(reports) == 1  # A rerun reads the cached report.

    # An annotation filter reads the stars: starring a reading that another
    # filter excludes changes its reasons but not the kept readings.
    star = {"star": True, "tags": [], "note": ""}
    at.session_state["trial_annotations"] = {first: star}
    at.checkbox(key="filter_favorites").check().run()
    assert reports[-1][0]["readings"].tolist() == [24, 1, 23]
    at.session_state["trial_annotations"] = {first: star, other: star}
    at.run()
    assert not at.exception
    reasons = reports[-1][1].set_index(["participant_id", "trial_id"])
    assert reports[-1][0]["readings"].tolist() == [24, 1, 23]
    assert reasons.loc[other, "exclusion_reasons"] == "Participant (1 selected)"


def test_repeated_readings_missing_values_and_a_changed_observation():
    frame = pd.DataFrame(
        [
            ["A", "one", 1, 0.0],
            ["A", "two", 1, 200.0],
            ["B", "one", 1, 500.0],
            ["A", "one", 2, float("inf")],
            ["B", "one", 2, float("nan")],
        ],
        columns=["participant_id", "trial_id", "word_id", "total_fixation_duration_ms"],
    )
    frame["text_id"] = "pilot"
    frame["text"] = frame.word_id.map({1: "The", 2: "end"})
    measure = agg.MEASURES["tfd"]

    def evidence(source):
        observations = agg.reading_word_contributions(
            source, "text_id", "pilot", measure
        )
        profile = agg.cohort_word_profile(source, "text_id", "pilot", measure)
        return (
            observations,
            profile,
            cohort_audit.profile_snapshot(
                observations, profile, profile.to_csv(index=False).encode(), {}
            ),
        )

    observations, profile, original = evidence(frame)
    assert len(observations) == 5
    assert profile.loc[0, "value"] == 300.0
    assert list(profile["n"]) == [2, 0]
    assert not profile.loc[1, "enough"]
    frame.loc[0, measure.column] = 2.0
    _, _, revised = evidence(frame)
    changes, note = cohort_audit.compare_profiles(original, revised)
    assert list(changes.change) == ["changed"]
    assert changes.iloc[0].trial_id == "one"
    assert "profile rows differ" in note
    assert not len(cohort_audit.compare_profiles(revised, revised)[0])


def test_within_reader_differences_exclude_unpaired_readers_only_from_the_average():
    def group(rows):
        return pd.DataFrame(
            rows, columns=["participant_id", "total_fixation_duration_ms"]
        )

    table = agg.within_reader_contrast(
        group([["1", 0], ["1", 4], ["2", 600]]),
        group([["1", 10], ["3", 0]]),
        agg.MEASURES["tfd"],
        participants={"1", "2", "3", "fixations-only"},
    )
    assert list(table.participant_id) == ["1", "2", "3", "fixations-only"]
    assert table.difference_a_minus_b.dropna().tolist() == [-8]
    assert table[["value_a", "value_b"]].isna().sum().tolist() == [2, 2]


def test_stimulus_revisions_and_remap_identify_the_concrete_readings():
    words = pd.DataFrame(
        [["01", "a", "gap", 0], ["01", "b", "gap", 0.4], ["01", "c", "new", 70]],
        columns=["participant_id", "trial_id", "text", "x"],
    )
    words = words.assign(text_id="pilot", word_id=1, passage="same")
    versions = agg.stimulus_revisions(words, "text_id", "pilot")
    assert versions == {
        ("01", "a"): [("01", "a"), ("01", "b")],
        ("01", "c"): [("01", "c")],
    }
    assert versions == agg.stimulus_revisions(words.iloc[::-1], "text_id", "pilot")
    changes = remap_reading_changes(
        {"words": words},
        {"words": {"trial": "passage"}},
        {("01", "b"): {"note": "pilot note"}},
    )
    assert changes.change.to_list() == ["Merged"] * 3
    assert (
        changes.loc[1, "annotations losing their reading"] == "Whole trial · pilot note"
    )


def test_trial_index_is_reused_and_released_with_its_source():
    frame = pd.DataFrame(
        {"participant_id": ["p", "p"], "trial_id": ["b", "a"], "value": [10, 1]}
    )
    other = frame.iloc[::-1].reset_index(drop=True).assign(value=[5, 50])
    assert utils._trial_positions(frame) is utils._trial_positions(frame)
    assert utils.extract_trial(frame, "p", "a").value.to_list() == [1]
    assert utils.extract_trial(other, "p", "a").value.to_list() == [5]
    ident, ref = id(frame), weakref.ref(frame)
    del frame
    gc.collect()
    assert ref() is None
    assert ident not in utils._TRIAL_INDICES


def test_copies_with_one_assigned_fingerprint_share_one_trial_index():
    from scanpath_studio.data import assign_fingerprint

    frame = pd.DataFrame(
        {"participant_id": ["p", "p"], "trial_id": ["b", "a"], "value": [10, 1]}
    )
    assign_fingerprint(frame, ("test", "shared index"))
    copy = frame.copy(deep=False)
    assign_fingerprint(copy, ("test", "shared index"))
    other = frame.copy(deep=False)
    assign_fingerprint(other, ("test", "another frame"))
    assert utils._trial_positions(copy) is utils._trial_positions(frame)
    assert utils._trial_positions(other) is not utils._trial_positions(frame)
    assert utils.extract_trial(copy, "p", "a").value.to_list() == [1]
    # The copy keeps the index alive after the frame that built it is gone.
    del frame
    gc.collect()
    assert utils.extract_trial(copy, "p", "b").value.to_list() == [10]


def test_a_trial_slice_is_named_by_its_source_and_reading(monkeypatch):
    """A rerun slices the reading again, so hashing the slice to key a cache
    would cost a full pass over its samples every time."""
    from scanpath_studio import data
    from scanpath_studio.data import assign_fingerprint, frame_fingerprint

    frame = pd.DataFrame(
        {"participant_id": ["p", "p", "q"], "trial_id": ["a", "a", "a"], "x": [1, 2, 3]}
    )
    assign_fingerprint(frame, ("test", "named slices"))
    edited = frame.assign(x=[1, 2, 30])
    assign_fingerprint(edited, ("test", "named slices, edited"))
    hashed = []
    real = data._compute_frame_fingerprint
    monkeypatch.setattr(
        data, "_compute_frame_fingerprint", lambda df: hashed.append(df) or real(df)
    )
    slices = {
        name: utils.extract_trial(source, participant, "a")
        for name, source, participant in (
            ("p", frame, "p"),
            ("p again", frame, "p"),
            ("q", frame, "q"),
            ("q edited", edited, "q"),
        )
    }
    keys = {name: frame_fingerprint(rows) for name, rows in slices.items()}
    assert not hashed
    assert keys["p"][0] == "assigned"
    assert keys["p"] == keys["p again"]
    assert len({keys["p"], keys["q"], keys["q edited"]}) == 3


@pytest.mark.parametrize("width", [None, -1, float("inf")])
def test_missing_measurements_are_not_resolved_as_measured(width):
    setup = SetupSnapshot.from_dict(
        {"monitor_width_mm": width, "provenance": {"geometry": "measured"}}
    )
    assert setup.geometry_provenance == Provenance.ASSUMED
    setup = SetupSnapshot.from_dict(
        {"monitor_width_mm": 550, "provenance": {"geometry": "measured"}}
    )
    assert setup.geometry_provenance == Provenance.MEASURED
    assert setup.viewing_distance_provenance == Provenance.ASSUMED
    assert setup == SetupSnapshot.from_dict(setup.to_dict())


def test_a_legacy_width_measurement_cannot_establish_viewing_distance():
    payload = {
        "monitor_width_mm": 550,
        "viewing_distance_mm": 800,
        "provenance": {"geometry": "measured"},
    }
    legacy = SetupSnapshot.from_dict(payload)
    assert (
        legacy.viewing_distance_mm == 800 and legacy.viewing_distance_provenance is None
    )
    assert SetupSnapshot.from_dict(legacy.to_dict()) == legacy
    measured = SetupSnapshot.from_dict(
        {**payload, "viewing_distance_provenance": "measured"}
    )
    assert measured.viewing_distance_provenance == Provenance.MEASURED
    assert SetupSnapshot.from_dict(measured.to_dict()) == measured
