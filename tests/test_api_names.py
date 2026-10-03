"""DATA-66 phase 4: the API and CLI speak the dataset's own column names."""

from __future__ import annotations

import json
import pickle

import pandas as pd
import pytest

import scanpath_studio as sps
from scanpath_studio import api
from scanpath_studio import column_names as cn


@pytest.fixture(scope="module")
def demo():
    return sps.load_sample_data()


@pytest.fixture(scope="module")
def demo_trial(demo):
    words, fixations = demo
    return tuple(sps.list_trials(words, fixations).iloc[0])


class TestLoading:
    def test_the_frames_are_named_as_the_files_name_them(self, demo):
        words, fixations = demo
        assert "CURRENT_FIX_DURATION" in fixations and "duration_ms" not in fixations
        assert {"IA_ID", "IA_LABEL", "IA_DWELL_TIME"} <= set(words.columns)

    def test_it_unpacks_and_carries_the_map(self, demo):
        words, fixations = demo
        assert isinstance(demo, api.ScanpathData)
        assert demo.words is words and demo.fixations is fixations
        assert demo.column_names["fixations"].label("duration_ms") == (
            "CURRENT_FIX_DURATION"
        )

    def test_canonical_names_on_request(self):
        _words, fixations = sps.load_sample_data(names="canonical")
        assert "duration_ms" in fixations and cn.ATTRS_KEY not in fixations.attrs

    def test_an_unknown_vocabulary_is_refused(self):
        with pytest.raises(ValueError, match="names must be"):
            sps.load_sample_data(names="mine")

    def test_it_pickles_with_its_map(self, demo):
        # Our own object, round-tripped in-process — what `st.cache_data`
        # does with it; nothing untrusted is unpickled.
        again = pickle.loads(pickle.dumps(demo))
        words, _fixations = again
        assert again.column_names.keys() == demo.column_names.keys()
        assert list(words.columns) == list(demo.words.columns)

    def test_a_frame_the_api_returned_loads_again(self, demo):
        words, fixations = demo
        again = sps.load_scanpath_data(words, fixations)
        assert {"CURRENT_FIX_DURATION", "CURRENT_FIX_X"} <= set(again.fixations.columns)
        assert {"IA_ID", "IA_DWELL_TIME"} <= set(again.words.columns)
        assert len(again.fixations) == len(fixations)

    def test_raw_gaze_is_named_too(self):
        raw = sps.load_sample_raw_gaze()
        canonical = sps.load_sample_raw_gaze(names="canonical")
        assert cn.frame_names(raw) is not None
        assert {"participant_id", "trial_id", "x", "y"} <= set(canonical.columns)


class TestEveryFunctionTakesEitherKind:
    def test_a_sliced_frame_still_plots(self, demo, demo_trial):
        words, fixations = demo
        pid, tid = demo_trial
        mask = fixations.iloc[:, 0].astype(str) == str(pid)
        fig = sps.plot_scanpath(words, fixations[mask], pid, tid)
        assert fig.data

    def test_a_column_option_takes_either_name(self, demo, demo_trial):
        words, fixations = demo
        by_own = sps.plot_scanpath(
            words, fixations, *demo_trial, color_by="CURRENT_FIX_DURATION"
        )
        by_internal = sps.plot_scanpath(
            words, fixations, *demo_trial, color_by="duration_ms"
        )
        assert by_own.to_json() == by_internal.to_json()

    def test_the_figure_text_uses_the_files_names(self, demo, demo_trial):
        words, fixations = demo
        fig = sps.plot_scanpath(
            words,
            fixations,
            *demo_trial,
            color_by="duration_ms",
            show_colorbars=True,
            fixation_hover_fields=["duration_ms"],
        )
        text = fig.to_json()
        assert "CURRENT_FIX_DURATION" in text

    def test_a_word_option_reads_the_words_tables_names(self, demo, demo_trial):
        # `word_id` is the AOI table's IA_ID but the fixations' shifted
        # interest-area id: a word hover is in the words table's names.
        words, fixations = demo
        fig = sps.plot_scanpath(
            words, fixations, *demo_trial, word_hover_fields=["IA_ID"]
        )
        (labels,) = (trace for trace in fig.data if trace.name == "words")
        assert "IA_ID:" in labels.hovertemplate
        assert "CURRENT_FIX_INTEREST_AREA_ID" not in labels.hovertemplate

    def test_canonical_frames_draw_as_before(self, demo_trial):
        words, fixations = sps.load_sample_data(names="canonical")
        fig = sps.plot_scanpath(words, fixations, *demo_trial, color_by="duration_ms")
        assert "CURRENT_FIX_DURATION" not in fig.to_json()

    def test_canonical_frames_take_the_map_explicitly(self, demo_trial):
        data = sps.load_sample_data(names="canonical")
        fig = sps.plot_scanpath(
            *data,
            *demo_trial,
            color_by="CURRENT_FIX_DURATION",
            show_colorbars=True,
            column_names=data.column_names,
        )
        assert "CURRENT_FIX_DURATION" in fig.to_json()

    def test_a_misspelt_heatmap_metric_is_refused(self, demo, demo_trial):
        words, fixations = demo
        with pytest.raises(ValueError, match="CURRENT_FIX_DURATION"):
            sps.plot_scanpath(
                words, fixations, *demo_trial, heatmap_metric="CURRENT_FIX_DURATON"
            )

    def test_animation_and_comparison_take_named_frames(self, demo):
        words, fixations = demo
        trials = sps.list_trials(words, fixations)
        a, b = (tuple(trials.iloc[i]) for i in (0, 1))
        assert sps.animate_scanpath(words, fixations, *a).frames
        assert sps.compare_scanpaths(
            words, fixations, a, b, color_by="CURRENT_FIX_DURATION"
        ).data


class TestOutputsFollowTheInputs:
    def test_the_trial_list_names_its_ids_as_the_file_does(self, demo):
        words, fixations = demo
        trials = sps.list_trials(words, fixations)
        assert list(trials.columns) == ["participant_id", "unique_trial_id"]

    def test_word_metrics_keep_the_files_names(self, demo):
        words, fixations = demo
        measures = sps.compute_word_metrics(words, fixations)
        assert "IA_DWELL_TIME" in measures
        # A measure the app computed keeps its internal name.
        assert "single_fixation_duration_ms" in measures

    def test_a_derived_table_names_only_its_ids(self, demo):
        words, fixations = demo
        tables = sps.analysis_tables(words, fixations)
        assert "CURRENT_FIX_DURATION" in tables["fixations"]
        summary = tables["trial_summary"]
        assert "unique_trial_id" in summary
        assert "IA_FIXATION_COUNT" not in summary

    def test_the_cleaning_report_names_its_ids_as_the_fixations_do(self, demo):
        words, fixations = demo
        _words, cleaned, report = sps.preprocess_data(words, fixations, enabled=True)
        assert "CURRENT_FIX_DURATION" in cleaned
        assert "unique_trial_id" in report and "trial_id" not in report

    def test_canonical_in_canonical_out(self):
        words, fixations = sps.load_sample_data(names="canonical")
        assert list(sps.list_trials(words, fixations).columns) == [
            "participant_id",
            "trial_id",
        ]


class TestCli:
    def test_list_trials_prints_the_files_names(self, capsys):
        from scanpath_studio import cli

        cli.main(["render", "--sample", "--list-trials"])
        header = capsys.readouterr().out.splitlines()[0]
        assert "unique_trial_id" in header

    def test_analyze_writes_the_files_names_and_a_map(self, tmp_path):
        from scanpath_studio import cli
        from scanpath_studio.data import load_sample_data as raw_demo

        words, fixations = raw_demo()
        words.to_csv(tmp_path / "ia.csv", index=False)
        fixations.to_csv(tmp_path / "fix.csv", index=False)
        out = tmp_path / "out"
        cli.main(
            [
                "analyze",
                "--words",
                str(tmp_path / "ia.csv"),
                "--fixations",
                str(tmp_path / "fix.csv"),
                "--output-dir",
                str(out),
            ]
        )
        written = pd.read_csv(out / "fixations.csv", nrows=1)
        assert "CURRENT_FIX_DURATION" in written
        manifest = json.loads((out / "columns.json").read_text())
        rows = {r["canonical"]: r["column"] for r in manifest["tables"]["fixations"]}
        assert rows["duration_ms"] == "CURRENT_FIX_DURATION"

    def test_a_column_flag_takes_the_files_name(self, tmp_path):
        from scanpath_studio import cli

        out = tmp_path / "fig.html"
        cli.main(
            [
                "render",
                "--sample",
                "--color-by",
                "CURRENT_FIX_DURATION",
                "-o",
                str(out),
            ]
        )
        assert out.exists()
