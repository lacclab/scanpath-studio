"""#412 — one trial pool for every surface: each trial any table has.

A dataset whose Words and Fixations tables cover different trials loaded fine,
but the surfaces disagreed about which trials it held: the app's picker listed
the fixations' trials (and dropped a trial only the words had), while
`api.list_trials` intersected the two tables — so the API could list nothing
and `plot_scanpath` refused both trials. The user's call: the **union**. A
trial is listed when any table has it, once however many have it, and a table
that lacks it draws as an empty layer. A stimulus-level Words table adds no
phantom readings: its rows only count once they have been broadcast onto a
real reading.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from scanpath_studio import api, cli
from scanpath_studio.data import names_readings, trial_pool
from scanpath_studio.export import ExportOptions, bulk_export
from scanpath_studio.utils import build_combo_options_for, combo_source
from tests.conftest import APP_SCRIPT, picked_trial_id, picker_trial_id

WORD_SCHEMA = {
    "participant": "participant_id",
    "trial": "trial_id",
    "text_id": None,
    "word_id": "word_id",
    "text": "text",
    "line": None,
    "x": "x",
    "y": "y",
    "width": "width",
    "height": "height",
}
FIX_SCHEMA = {
    "participant": "participant_id",
    "trial": "trial_id",
    "text_id": None,
    "x": "x",
    "y": "y",
    "duration": "duration_ms",
    "timestamp": None,
    "fixation_id": None,
    "word_id": None,
}
EVERY = [("p", "both"), ("p", "fix_only"), ("p", "words_only")]


def _raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The review's probe, plus a trial both tables have."""
    words = pd.DataFrame(
        {
            "participant_id": ["p", "p"],
            "trial_id": ["words_only", "both"],
            "word_id": [1, 1],
            "text": ["hello", "hello"],
            "x": [0, 0],
            "y": [0, 0],
            "width": [80, 80],
            "height": [20, 20],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p", "p", "p", "p"],
            "trial_id": ["fix_only", "fix_only", "both", "both"],
            "x": [5, 50, 5, 50],
            "y": [5, 5, 5, 5],
            "duration_ms": [100, 200, 100, 200],
        }
    )
    return words, fixations


@pytest.fixture(scope="module")
def mixed() -> tuple[pd.DataFrame, pd.DataFrame]:
    words, fixations = _raw()
    return api.load_scanpath_data(
        words,
        fixations,
        word_schema=WORD_SCHEMA,
        fix_schema=FIX_SCHEMA,
        names="canonical",
    )


def _listed(frame: pd.DataFrame) -> list[tuple[str, str]]:
    return sorted(
        (str(p), str(t)) for p, t in zip(frame["participant_id"], frame["trial_id"])
    )


class TestEverySurfaceListsTheSameTrials:
    def test_the_api(self, mixed):
        assert _listed(api.list_trials(*mixed)) == EVERY

    def test_the_app_picker(self, mixed):
        words, fixations = mixed
        combos, _, _ = build_combo_options_for(combo_source(fixations, words))
        assert _listed(combos) == EVERY

    def test_the_cli(self, mixed, tmp_path, capsys):
        words, fixations = _raw()
        words.to_csv(tmp_path / "words.csv", index=False)
        fixations.to_csv(tmp_path / "fixations.csv", index=False)
        cli.main(
            [
                "render",
                "--words",
                str(tmp_path / "words.csv"),
                "--fixations",
                str(tmp_path / "fixations.csv"),
                "--list-trials",
            ]
        )
        out = capsys.readouterr()
        assert "3 trials." in out.err
        for _, trial in EVERY:
            assert trial in out.out

    def test_the_export_bundle(self, mixed, tmp_path):
        """The app hands its pool to the bundle, which writes each trial."""
        words, fixations = mixed
        combos, _, _ = build_combo_options_for(combo_source(fixations, words))
        payload, progress = bulk_export(
            combos,
            words,
            fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings={"show_words": True, "show_fixations": True},
            options=ExportOptions(
                include_png=False,
                include_svg=False,
                include_html=True,
                include_plot_config=False,
                include_fixations=True,
            ),
        )
        assert progress.errors == []
        assert progress.finished_trials == 3
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = set(archive.namelist())
        for _, trial in EVERY:
            assert any(f"p__{trial}/" in name for name in names), (trial, names)


class TestEachTrialPlots:
    def test_a_trial_with_words_alone(self, mixed):
        fig = api.plot_scanpath(*mixed, "p", "words_only")
        assert [trace.name for trace in fig.data] == ["words"]

    def test_a_trial_with_fixations_alone(self, mixed):
        fig = api.plot_scanpath(*mixed, "p", "fix_only")
        names = [trace.name for trace in fig.data]
        assert "words" not in names and "saccades" in names

    def test_a_trial_both_tables_have_is_one_entry_with_both_layers(self, mixed):
        assert _listed(api.list_trials(*mixed)).count(("p", "both")) == 1
        names = [trace.name for trace in api.plot_scanpath(*mixed, "p", "both").data]
        assert "words" in names and "saccades" in names

    def test_the_replay_and_the_comparison_say_they_need_fixations(self, mixed):
        with pytest.raises(ValueError, match="no fixations to replay"):
            api.animate_scanpath(*mixed, "p", "words_only")
        with pytest.raises(ValueError, match="each trial needs fixations"):
            api.compare_scanpaths(*mixed, ("p", "both"), ("p", "words_only"))


class TestStimulusLevelWords:
    """A words table with no participant names texts, not readings."""

    @staticmethod
    def _stimulus_words() -> pd.DataFrame:
        words, _ = _raw()
        return words.drop(columns="participant_id").assign(trial_id=["A", "B"])

    def test_it_adds_no_reading_beside_fixations(self):
        fixations = pd.DataFrame(
            {
                "participant_id": ["r1", "r2"],
                "trial_id": ["A", "A"],
                "x": [5, 5],
                "y": [5, 5],
                "duration_ms": [100, 100],
            }
        )
        # Text B, which nobody read, is not a reading of anyone's.
        words, fixations = api.load_scanpath_data(
            self._stimulus_words(),
            fixations,
            word_schema={**WORD_SCHEMA, "participant": None},
            fix_schema=FIX_SCHEMA,
            names="canonical",
        )
        assert _listed(api.list_trials(words, fixations)) == [("r1", "A"), ("r2", "A")]
        combos, _, _ = build_combo_options_for(combo_source(fixations, words))
        assert _listed(combos) == [("r1", "A"), ("r2", "A")]

    def test_before_the_broadcast_it_names_no_reading(self):
        from scanpath_studio.data import normalize_words

        words = normalize_words(
            self._stimulus_words(), {**WORD_SCHEMA, "participant": None}
        )
        assert not names_readings(words)
        fixations = pd.DataFrame({"participant_id": ["r1"], "trial_id": ["A"]})
        assert _listed(trial_pool(fixations, words)) == [("r1", "A")]

    def test_alone_it_is_one_reader_per_text(self):
        words, fixations = api.load_scanpath_data(
            self._stimulus_words(),
            None,
            word_schema={**WORD_SCHEMA, "participant": None},
            names="canonical",
        )
        assert len(api.list_trials(words, fixations)) == 2


@pytest.mark.timeout(240)
def test_the_app_offers_and_draws_both_trials(mixed):
    from streamlit.testing.v1 import AppTest

    words, fixations = mixed
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["_datasets"] = {
        "Mixed": {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": [],
            "composite_trial_columns": [],
        }
    }
    at.session_state["data_source_choice"] = "Mixed"
    at.run()
    assert not at.exception, at.exception
    picker = at.selectbox(key="single_trial_id")
    by_id = {picker_trial_id(option): option for option in picker.options}
    assert set(by_id) == {"both", "fix_only", "words_only"}
    for trial in ("words_only", "fix_only"):
        at.selectbox(key="single_trial_id").set_value(by_id[trial]).run()
        assert not at.exception, at.exception
        assert not at.error, [e.value for e in at.error]
        assert picked_trial_id(at.selectbox(key="single_trial_id").value) == trial
