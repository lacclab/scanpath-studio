from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from scanpath_studio import api, data, export, fixation_source, preprocessing


def load_reading(tmp_path):
    words = pd.DataFrame(
        {
            "participant_id": ["p"],
            "trial_id": ["t"],
            "word_id": [1],
            "text": ["stimulus_canary"],
            "x": [10],
            "y": [10],
            "width": [80],
            "height": [40],
        }
    )
    a, b = tmp_path / "first.csv", tmp_path / "second.csv"
    headings = "participant_id,trial_id,x,y,FPOGD,timestamp_ms,extra\n"
    a.write_text(
        headings + "p,,21,20,0.111,0,omit\np,t,21,20,0.200,50,secret_unselected\n"
    )
    b.write_text(
        headings + "p,t,22,20,0.040,300,omit\np,t,23,20,input_canary,400,omit\n"
    )
    return words, [a, b]


def test_parsed_input_row_source_units_assignment_and_missing_identity(tmp_path):
    words, paths = load_reading(tmp_path)
    study = api.load_scanpath_data(words, paths, include_source_cells=True)
    report = study.explain_fixation("p", "t", 1)
    assert report["location"] == {"File": "first.csv", "Row": 2}
    fields = {x["Field"]: x for x in report["fields"]}
    assert fields["duration_ms"] == {
        "Field": "duration_ms",
        "Input column": "FPOGD",
        "Input value": "0.2",
        "Input unit": "s",
        "Current value": "200.0",
    }
    assert (
        report["assignment"] == "Contained by word box" and float(report["word"]) == 1
    )
    assert study.explain_fixation("p", "t", 2)["location"] == {
        "File": "second.csv",
        "Row": 1,
    }
    assert (
        study.explain_fixation("p", "t", 3)["fields"][0]["Input value"]
        == "input_canary"
    )
    # Old datasets have no source record; keep that distinct from a first-row origin.
    ordinary = api.load_scanpath_data(words, paths)
    assert not fixation_source.PRIVATE_COLUMNS.intersection(ordinary.fixations)
    assert ordinary.explain_fixation("p", "t", 1)["location"] == {
        "File": None,
        "Row": None,
    }


def test_remapping_retains_only_previously_recorded_input_cells():
    raw = pd.DataFrame(
        [{"participant_id": "p", "trial_id": "t", "x": 21, "y": 20, "FPOGD": 0.04}]
    )
    schema = data.infer_fix_schema(raw)
    ordinary = data.normalize_fixations(raw, schema)
    recorded = data.normalize_fixations(raw, schema, keep_source_cells=True)
    mapping = data.infer_fix_schema(ordinary)

    remapped = data.remap_normalized_frame(ordinary, mapping, kind="fixations")
    assert not fixation_source.PRIVATE_COLUMNS.intersection(ordinary)
    assert not fixation_source.PRIVATE_COLUMNS.intersection(remapped)

    remapped = data.remap_normalized_frame(recorded, mapping, kind="fixations")
    columns = [fixation_source.SOURCE_ROW, fixation_source.INPUT_CELLS["duration_ms"]]
    pd.testing.assert_frame_equal(remapped[columns], recorded[columns])


def test_source_cells_stay_out_of_saved_redacted_figures_and_bundle(tmp_path):
    words, paths = load_reading(tmp_path)
    words, fixations = api.load_scanpath_data(
        words, paths, names="canonical", include_source_cells=True
    )
    options = dict(
        redact_text=True,
        fixation_hover_fields=[fixation_source.INPUT_CELLS["duration_ms"]],
    )
    builders = (api.plot_scanpath, api.animate_scanpath)
    for build in builders:
        fig = build(words, fixations, **options)
        target = tmp_path / f"{build.__name__}.html"
        api.save_figure(fig, target)
        for token in ("input_canary", "secret_unselected", "stimulus_canary"):
            assert token not in target.read_text()
    settings = {"redact_text": True}
    archive, _ = export.bulk_export(
        fixations[["participant_id", "trial_id"]].drop_duplicates(),
        words,
        fixations,
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings=settings,
        options=export.ExportOptions(
            include_html=True,
            include_svg=False,
            include_png=False,
            include_fixations=True,
        ),
    )
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        for name in zf.namelist():
            body = zf.read(name)
            assert b"input_canary" not in body and b"secret_unselected" not in body
            if name.endswith(".csv"):
                assert b"_fixation_input_" not in body


def test_merged_duration_lists_both_source_rows_without_duplicating_numeric_coordinates(
    tmp_path,
):
    words, paths = load_reading(tmp_path)
    study = api.load_scanpath_data(
        words, paths, names="canonical", include_source_cells=True
    )
    fx = study.fixations.iloc[:2]
    assert (
        fixation_source.INPUT_CELLS["x"] not in fx
        and fixation_source.INPUT_CELLS["y"] not in fx
    )
    merged, count, _ = preprocessing.merge_short_fixations(
        fx, study.words, threshold_ms=80
    )
    assert count == 1
    report = fixation_source.explain(
        merged.iloc[0], study.words, study.column_names["fixations"]
    )
    assert report["contributors"] == [
        {"File": "first.csv", "Row": 2},
        {"File": "second.csv", "Row": 1},
    ]
    assert float(report["fields"][0]["Current value"]) == pytest.approx(240)
    assert not fixation_source.PRIVATE_COLUMNS.intersection(
        data.drop_internal_columns(merged)
    )
