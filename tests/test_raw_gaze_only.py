"""VIZ-45 — a dataset recorded as raw gaze alone is a first-class dataset.

It used to open as a blank plot: the 🔵 Raw gaze layer defaulted off (the only
data in the dataset hidden), the Illustration disclosure said "derived from raw
gaze" although nothing is derived, and the chips read "Total reading time (s) =
0.0 · Number of fixations = 0" — measured zeros for things nobody measured.

These tests build the raw-gaze-only fixture from the bundled demo's own raw
gaze (`sample_data/raw_gaze.csv`, one synthesized trial) and walk it through
every surface a fixation dataset works on: the API, the CLI, the code snippet,
the export bundle, and the app's Scanpath and Corpus views.

What is *not* here is fixation detection: nothing in the app turns samples into
fixations, and the tests pin that the surfaces say so rather than invent it.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

import scanpath_studio as sps
from scanpath_studio import api, cli, tabs
from scanpath_studio import code_snippet as cs
from scanpath_studio.app import seed_raw_gaze_default
from scanpath_studio.constants import (
    DEMO_CHOICE,
    RAW_GAZE_SEEDED_FOR_KEY,
    RAW_GAZE_SNAP_RESTORE_KEY,
)
from scanpath_studio.data import (
    empty_fixations_frame,
    empty_words_frame,
    raw_gaze_in_pool,
)
from scanpath_studio.illustration import illustration_reasons
from scanpath_studio.utils import combo_source
from tests.conftest import APP_SCRIPT

LAYER = "global_show_raw_gaze"
SAMPLE_RAW_GAZE = "scanpath_studio/sample_data/raw_gaze.csv"


@pytest.fixture(scope="module")
def raw_gaze() -> pd.DataFrame:
    """The bundled demo's raw gaze: one trial of samples, normalized."""
    return api.load_sample_raw_gaze()


@pytest.fixture(scope="module")
def two_trial_raw_gaze(raw_gaze) -> pd.DataFrame:
    """The same samples as a second reader's trial too, so a pool has two."""
    second = raw_gaze.assign(
        participant_id="p_other",
        trial_id=raw_gaze["trial_id"] + "_b",
        unique_trial_id=raw_gaze["trial_id"] + "_b",
        text_id=raw_gaze["trial_id"] + "_b",
    )
    return pd.concat([raw_gaze, second], ignore_index=True)


def _key(raw_gaze):
    return str(raw_gaze["participant_id"].iloc[0]), str(raw_gaze["trial_id"].iloc[0])


# -----------------------------------------------------------------------------
# (b) the Illustration disclosure — nothing is derived from samples
# -----------------------------------------------------------------------------


def test_raw_gaze_is_never_an_illustration_reason():
    import inspect

    assert "raw_gaze_only" not in inspect.signature(illustration_reasons).parameters
    assert illustration_reasons({}) == []


# -----------------------------------------------------------------------------
# (c) the chips — absent, not measured zeros
# -----------------------------------------------------------------------------


class TestSummaryRows:
    def test_a_raw_gaze_only_trial_counts_its_samples_and_nothing_else(self, raw_gaze):
        rows = tabs._summary_rows(
            empty_words_frame(), empty_fixations_frame(), raw_gaze
        )
        assert rows == [
            {"Field": "Number of gaze samples", "Value": f"{len(raw_gaze):,}"}
        ]

    def test_a_words_only_trial_has_no_reading_time_or_fixation_count(self):
        words, _ = sps.load_sample_data()
        pid, tid = words["participant_id"].iloc[0], words["trial_id"].iloc[0]
        trial_words = words[
            (words["participant_id"] == pid) & (words["trial_id"] == tid)
        ].drop(columns=["trial_dwell_time_ms"], errors="ignore")
        fields = [
            row["Field"]
            for row in tabs._summary_rows(trial_words, empty_fixations_frame())
        ]
        assert fields == ["Number of words"]

    def test_a_fixation_trial_keeps_every_row_it_had(self):
        words, fixations = sps.load_sample_data()
        pid, tid = fixations["participant_id"].iloc[0], fixations["trial_id"].iloc[0]

        def trial(frame):
            return frame[(frame["participant_id"] == pid) & (frame["trial_id"] == tid)]

        fields = [
            row["Field"] for row in tabs._summary_rows(trial(words), trial(fixations))
        ]
        assert fields == [
            "Total reading time (s)",
            "Number of words",
            "Number of fixations",
            "Fixations in word boxes",
        ]

    def test_the_chip_strip_writes_the_sample_count_and_no_zeros(
        self, raw_gaze, monkeypatch
    ):
        written: list[str] = []
        monkeypatch.setattr(
            tabs.st, "markdown", lambda body, **kw: written.append(str(body))
        )
        tabs._render_trial_condition_chips(
            empty_words_frame(),
            empty_fixations_frame(),
            "p1",
            ["@reading_time_s", "@fixation_count", "@gaze_sample_count"],
            trial_raw_gaze=raw_gaze,
        )
        strip = " ".join(written)
        assert f"Number of gaze samples = {len(raw_gaze):,}" in strip
        assert "Total reading time" not in strip
        assert "Number of fixations" not in strip


def test_the_note_above_the_plot_says_nothing_is_detected():
    note = tabs._no_fixations_note(
        trial_has_fixations=False,
        trial_has_raw_gaze=True,
        raw_gaze_shown=True,
        animate_requested=True,
        compare_requested=False,
    )
    assert "Raw gaze only" in note
    assert "does not detect fixations" in note
    assert "**Animate** draws fixations" in note
    # Off → it says how to see them.
    assert "Turn on" in tabs._no_fixations_note(
        trial_has_fixations=False,
        trial_has_raw_gaze=True,
        raw_gaze_shown=False,
        animate_requested=False,
        compare_requested=False,
    )
    # A trial with fixations says nothing.
    assert not tabs._no_fixations_note(
        trial_has_fixations=True,
        trial_has_raw_gaze=True,
        raw_gaze_shown=True,
        animate_requested=True,
        compare_requested=True,
    )


# -----------------------------------------------------------------------------
# (a) the per-dataset default, and the user's choice winning
# -----------------------------------------------------------------------------


class TestRawGazeDefault:
    RAW = ("Gaze", None)
    DEMO = (DEMO_CHOICE, None)

    def test_opening_a_samples_only_dataset_turns_the_layer_on(self):
        session = {LAYER: False}
        seed_raw_gaze_default(session, self.RAW, samples_only=True)
        assert session[LAYER] is True

    def test_an_explicit_off_on_that_dataset_sticks(self):
        session = {LAYER: False}
        seed_raw_gaze_default(session, self.RAW, samples_only=True)
        session[LAYER] = False  # the user switches it off
        seed_raw_gaze_default(session, self.RAW, samples_only=True)  # a rerun
        assert session[LAYER] is False

    def test_leaving_puts_back_what_the_next_dataset_had(self):
        session = {LAYER: False}
        seed_raw_gaze_default(session, self.RAW, samples_only=True)
        seed_raw_gaze_default(session, self.DEMO, samples_only=False)
        assert session[LAYER] is False
        assert RAW_GAZE_SNAP_RESTORE_KEY not in session
        # …and a never-set key goes back to absent, i.e. the factory default.
        session = {}
        seed_raw_gaze_default(session, self.RAW, samples_only=True)
        seed_raw_gaze_default(session, self.DEMO, samples_only=False)
        assert LAYER not in session

    def test_a_fixation_dataset_is_left_alone(self):
        session = {LAYER: True}
        seed_raw_gaze_default(session, self.DEMO, samples_only=False)
        assert session[LAYER] is True
        assert session[RAW_GAZE_SEEDED_FOR_KEY]

    def test_a_link_that_named_the_layer_wins(self):
        session = {LAYER: False}
        seed_raw_gaze_default(
            session, self.RAW, samples_only=True, link_names_layer=True
        )
        assert session[LAYER] is False

    def test_a_named_preset_or_reset_decides_again(self):
        from scanpath_studio.controls import _forget_raw_gaze_default

        session = {LAYER: False}
        seed_raw_gaze_default(session, self.RAW, samples_only=True)
        session[LAYER] = False  # e.g. the Scanpath preset's own value
        _forget_raw_gaze_default(session)
        seed_raw_gaze_default(session, self.RAW, samples_only=True)
        assert session[LAYER] is True

    def test_the_decision_rides_the_recovery_cache(self):
        from scanpath_studio.persistence import _SESSION_KEYS

        assert {RAW_GAZE_SEEDED_FOR_KEY, RAW_GAZE_SNAP_RESTORE_KEY} <= _SESSION_KEYS

    def test_a_link_value_is_not_stashed_as_the_users(self):
        """The link overwrote nothing, so leaving has nothing to put back."""
        session = {LAYER: False}
        seed_raw_gaze_default(
            session, self.RAW, samples_only=True, link_names_layer=True
        )
        assert RAW_GAZE_SNAP_RESTORE_KEY not in session
        seed_raw_gaze_default(session, self.DEMO, samples_only=False)
        assert session[LAYER] is False

    def test_a_link_on_leaving_drops_an_old_stash_rather_than_writing_it(self):
        """Relaunch + link: the recovery cache still holds a stash from a
        raw-gaze visit, and a link with `show_raw_gaze=1` opens a fixation
        dataset — the link's value stands, the stash goes."""
        session = {
            LAYER: True,  # seeded by the link
            RAW_GAZE_SNAP_RESTORE_KEY: {"value": False},  # from the cache
            RAW_GAZE_SEEDED_FOR_KEY: "Gaze\x1fNone",
        }
        seed_raw_gaze_default(
            session, self.DEMO, samples_only=False, link_names_layer=True
        )
        assert session[LAYER] is True
        assert RAW_GAZE_SNAP_RESTORE_KEY not in session

    def test_a_link_belongs_to_the_dataset_it_was_opened_on(self):
        asked = []

        def link() -> bool:
            asked.append(1)
            return True

        session = {LAYER: False}  # the link said 0
        seed_raw_gaze_default(
            session, self.RAW, samples_only=True, link_names_layer=link
        )
        assert session[LAYER] is False
        # The user opens another raw-gaze-only dataset of their own.
        seed_raw_gaze_default(
            session, ("Other gaze", None), samples_only=True, link_names_layer=link
        )
        assert session[LAYER] is True
        # And the link is asked once, not on every decision or rerun.
        seed_raw_gaze_default(
            session, ("Other gaze", None), samples_only=True, link_names_layer=link
        )
        assert len(asked) == 1


# -----------------------------------------------------------------------------
# The trial pool — trials only the samples have are trials
# -----------------------------------------------------------------------------


class TestPool:
    def test_samples_only_trials_survive_beside_fixations(self, raw_gaze):
        words, fixations = sps.load_sample_data()
        extra = raw_gaze.assign(trial_id="samples_only", unique_trial_id="samples_only")
        gaze = pd.concat([raw_gaze, extra], ignore_index=True)
        kept = raw_gaze_in_pool(gaze, words, fixations, words, fixations)
        assert set(kept["trial_id"]) == {raw_gaze["trial_id"].iloc[0], "samples_only"}

    def test_a_filtered_out_trial_takes_its_samples_with_it(self, raw_gaze):
        words, fixations = sps.load_sample_data()
        _, tid = _key(raw_gaze)
        pool = fixations[fixations["trial_id"] != tid]
        kept = raw_gaze_in_pool(raw_gaze, words, fixations, words.iloc[0:0], pool)
        assert kept.empty

    def test_nothing_dropped_is_the_same_frame(self, raw_gaze):
        assert (
            raw_gaze_in_pool(
                raw_gaze, empty_words_frame(), empty_fixations_frame(), None, None
            )
            is raw_gaze
        )

    def test_the_picker_lists_a_samples_only_trial(self, raw_gaze):
        words, fixations = sps.load_sample_data()
        extra = raw_gaze.assign(trial_id="samples_only", unique_trial_id="samples_only")
        source = combo_source(fixations, words, extra)
        assert "samples_only" in set(source["trial_id"].astype(str))
        assert set(fixations["trial_id"]) <= set(source["trial_id"])
        # No raw-gaze-only trial → the very same frame, so the cache is unchanged.
        assert combo_source(fixations, words, raw_gaze) is fixations
        assert combo_source(empty_fixations_frame(), empty_words_frame(), raw_gaze) is (
            raw_gaze
        )


# -----------------------------------------------------------------------------
# Headless API
# -----------------------------------------------------------------------------


class TestApi:
    def test_list_trials_takes_the_samples(self, raw_gaze):
        trials = sps.list_trials(raw_gaze=raw_gaze)
        assert list(trials.itertuples(index=False, name=None)) == [_key(raw_gaze)]

    def test_plot_scanpath_draws_the_samples_alone(self, raw_gaze):
        fig = sps.plot_scanpath(raw_gaze=raw_gaze)
        assert [trace.name for trace in fig.data] == ["Raw gaze"]
        assert len(fig.data[0].x) == len(raw_gaze)
        # Nothing derived, so no Illustration label.
        assert not [a for a in fig.layout.annotations if "Illustration" in str(a.text)]

    def test_plot_scanpath_over_words_without_fixations(self, raw_gaze):
        words, _ = sps.load_sample_data()
        pid, tid = _key(raw_gaze)
        fig = sps.plot_scanpath(words, None, pid, tid, raw_gaze=raw_gaze)
        names = [trace.name for trace in fig.data]
        assert "Raw gaze" in names and "words" in names

    def test_animate_scanpath_says_it_needs_fixations(self, raw_gaze):
        with pytest.raises(ValueError, match="no raw-gaze layer"):
            sps.animate_scanpath(raw_gaze=raw_gaze)
        words, _ = sps.load_sample_data()
        pid, tid = _key(raw_gaze)
        with pytest.raises(ValueError, match="no fixations to replay"):
            sps.animate_scanpath(words, None, pid, tid)

    def test_figure_code_writes_a_samples_only_recipe_that_runs(
        self, raw_gaze, tmp_path
    ):
        pid, tid = _key(raw_gaze)
        code = sps.figure_code(
            source="raw_gaze",
            source_options={"raw_gaze": [SAMPLE_RAW_GAZE]},
            participant=pid,
            trial=tid,
            show_raw_gaze=True,
            flavor="python",
            output=str(tmp_path / "rg.html"),
        )
        assert "words, fixations = None, None" in code
        assert "raw_gaze=raw_gaze" in code
        exec(compile(code, "<snippet>", "exec"), {})  # noqa: S102
        assert (tmp_path / "rg.html").is_file()


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


class TestCli:
    def test_raw_gaze_alone_is_an_input(self, capsys, raw_gaze):
        cli.main(["render", "--raw-gaze", SAMPLE_RAW_GAZE, "--list-trials"])
        out = capsys.readouterr().out
        assert raw_gaze["trial_id"].iloc[0] in out

    def test_it_renders_the_samples(self, tmp_path):
        out = tmp_path / "rg.html"
        cli.main(["render", "--raw-gaze", SAMPLE_RAW_GAZE, "-o", str(out)])
        assert "Raw gaze" in out.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "flags", [["--animate"], ["--compare-with", "p_other:t_other"]]
    )
    def test_the_fixation_modes_say_why_not(self, tmp_path, flags):
        with pytest.raises(SystemExit, match="does not turn into fixations"):
            cli.main(
                [
                    "render",
                    "--raw-gaze",
                    SAMPLE_RAW_GAZE,
                    "-o",
                    str(tmp_path / "rg.html"),
                    *flags,
                ]
            )

    def test_print_code_names_the_samples_as_the_data(self, tmp_path, capsys):
        cli.main(
            [
                "render",
                "--raw-gaze",
                SAMPLE_RAW_GAZE,
                "-o",
                str(tmp_path / "rg.html"),
                "--print-code",
                "both",
            ]
        )
        out = capsys.readouterr().out
        assert "words, fixations = None, None" in out
        assert "--sample" not in out
        assert f"render --raw-gaze {SAMPLE_RAW_GAZE}" in out

    def test_raw_gaze_beside_another_input_is_still_a_layer(self):
        with pytest.raises(SystemExit):
            cli.main(
                [
                    "render",
                    "--potec",
                    "nowhere",
                    "--sample",
                    "--raw-gaze",
                    SAMPLE_RAW_GAZE,
                    "-o",
                    "x.html",
                ]
            )


def test_the_share_snippet_of_an_uploaded_samples_only_dataset(raw_gaze):
    """Share → Code on an uploaded raw-gaze-only dataset: no two-table loader
    it could never have run, and the placeholder is said out loud."""
    from streamlit.testing.v1 import AppTest

    del raw_gaze  # the script builds its own session
    at = AppTest.from_function(_snippet_source_script, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["_kind"] == cs.SOURCE_RAW_GAZE


def _snippet_source_script():
    import streamlit as st

    from scanpath_studio import api
    from scanpath_studio.data import empty_fixations_frame, empty_words_frame
    from scanpath_studio.url_state import _snippet_source

    st.session_state["_datasets"] = {
        "Gaze": {
            "words": empty_words_frame(),
            "fixations": empty_fixations_frame(),
            "raw_gaze": api.load_sample_raw_gaze(),
        }
    }
    st.session_state["_kind"] = _snippet_source("Gaze").kind


# -----------------------------------------------------------------------------
# Export bundle
# -----------------------------------------------------------------------------


def test_the_bundle_draws_and_writes_a_samples_only_trial(raw_gaze):
    from scanpath_studio.export import ExportOptions, bulk_export
    from scanpath_studio.utils import build_combo_options

    combos, _, _ = build_combo_options(raw_gaze)
    # The layer switch is all the batch needs; every other option takes the
    # builder default.
    settings = {"show_raw_gaze": True}
    data, progress = bulk_export(
        combos,
        empty_words_frame(),
        empty_fixations_frame(),
        canvas_width=2560,
        canvas_height=1440,
        base_font_size=16,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings=settings,
        options=ExportOptions(
            include_png=False,
            include_svg=False,
            include_html=True,
            include_raw_gaze=True,
        ),
        raw_gaze=raw_gaze,
    )
    assert not progress.errors, progress.errors
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    figure = next(name for name in names if name.endswith("figure.html"))
    table = next(name for name in names if name.endswith("raw_gaze.csv"))
    archive = zipfile.ZipFile(io.BytesIO(data))
    assert "Raw gaze" in archive.read(figure).decode("utf-8")
    assert len(pd.read_csv(io.BytesIO(archive.read(table)))) == len(raw_gaze)


# -----------------------------------------------------------------------------
# The app — the Scanpath and Corpus views on a raw-gaze-only dataset
# -----------------------------------------------------------------------------


def _stored(words, fixations, gaze) -> dict:
    return {
        "words": words,
        "fixations": fixations,
        "raw_gaze": gaze,
        "filter_fields": [],
        "composite_trial_columns": [],
    }


@pytest.fixture
def figures(monkeypatch):
    """Every spatial figure the Scanpath view draws, in order."""
    drawn: list = []
    real = tabs._render_true_scale_chart

    def spy(fig, *args, **kwargs):
        drawn.append(fig)
        return real(fig, *args, **kwargs)

    monkeypatch.setattr(tabs, "_render_true_scale_chart", spy)
    return drawn


@pytest.mark.timeout(240)
class TestScanpathView:
    NAME = "Gaze"

    def _open(self, gaze, *, words=None, fixations=None, demo_first=True):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
        if demo_first:
            # The repro: the demo's layer default (off) is already in session
            # when the raw-gaze dataset is opened.
            at.run()
        at.session_state["_datasets"] = {
            self.NAME: _stored(
                empty_words_frame() if words is None else words,
                empty_fixations_frame() if fixations is None else fixations,
                gaze,
            )
        }
        at.session_state["data_source_choice"] = self.NAME
        at.run()
        assert not at.exception, at.exception
        return at

    def test_it_opens_showing_the_samples(self, raw_gaze, figures):
        at = self._open(raw_gaze)
        assert at.session_state[LAYER] is True
        figure = figures[-1]
        assert [trace.name for trace in figure.data] == ["Raw gaze"]
        assert not [
            a for a in figure.layout.annotations if "Illustration" in str(a.text)
        ]
        chips = " ".join(m.value for m in at.markdown if "sps-chip" in m.value)
        assert f"Number of gaze samples = {len(raw_gaze):,}" in chips
        assert "= 0.0" not in chips and "fixations = 0" not in chips
        captions = " ".join(c.value for c in at.caption)
        assert "Raw gaze only" in captions
        assert "does not detect fixations" in captions
        # The fixation layers grey with the reason, keeping their values.
        assert at.toggle(key="global_show_fix").disabled
        assert at.toggle(key="global_show_saccades").disabled

        # The user's own choice wins: off stays off across reruns…
        at.toggle(key=LAYER).set_value(False).run()
        at.run()
        assert at.session_state[LAYER] is False
        # …and leaving for the demo puts back the demo's own value.
        at.session_state["data_source_choice"] = DEMO_CHOICE
        at.run()
        assert not at.exception, at.exception
        assert at.session_state[LAYER] is False

    def test_animate_on_draws_the_static_figure_with_a_reason(self, raw_gaze, figures):
        at = self._open(raw_gaze, demo_first=False)
        at.toggle(key="single_animate").set_value(True).run()
        assert not at.exception, at.exception
        assert [trace.name for trace in figures[-1].data] == ["Raw gaze"]
        captions = " ".join(c.value for c in at.caption)
        assert "**Animate** draws fixations" in captions

    def test_every_samples_only_trial_is_pickable(self, two_trial_raw_gaze):
        at = self._open(two_trial_raw_gaze, demo_first=False)
        trials = set(at.selectbox(key="single_trial_id").options)
        assert len(trials) == 2

    def test_raw_gaze_beside_fixations_keeps_its_own_trials(self, raw_gaze):
        words, fixations = api.load_scanpath_data(*sps.load_sample_data())
        extra = raw_gaze.assign(trial_id="samples_only", unique_trial_id="samples_only")
        at = self._open(
            pd.concat([raw_gaze, extra], ignore_index=True),
            words=words,
            fixations=fixations,
            demo_first=False,
        )
        options = at.selectbox(key="single_trial_id").options
        assert any("samples_only" in str(option) for option in options)
        # A dataset with fixations keeps the factory default.
        assert at.session_state[LAYER] is False

    def test_the_share_link_round_trips_the_trial_and_the_layer(self, raw_gaze):
        """The link names the samples-only trial and the raw-gaze layer, and a
        recipient who has the same dataset open lands on both — including a
        sender's explicit *off*, which the dataset default must not override."""
        from urllib.parse import parse_qsl

        from streamlit.testing.v1 import AppTest

        at = self._open(raw_gaze, demo_first=False)
        at.toggle(key=LAYER).set_value(False).run()
        query, _ = at.session_state["_share_query_current"]
        params = dict(parse_qsl(query))
        _, tid = _key(raw_gaze)
        assert params["trial_id"] == tid
        assert params["show_raw_gaze"] == "0"

        recipient = AppTest.from_file(APP_SCRIPT, default_timeout=180)
        for name, value in params.items():
            recipient.query_params[name] = value
        recipient.session_state["_datasets"] = {
            self.NAME: _stored(empty_words_frame(), empty_fixations_frame(), raw_gaze)
        }
        recipient.session_state["data_source_choice"] = self.NAME
        recipient.run()
        assert not recipient.exception, recipient.exception
        assert recipient.session_state["single_trial_id"] == tid
        assert recipient.session_state[LAYER] is False

    def test_corpus_analysis_says_what_it_needs(self, raw_gaze):
        from scanpath_studio.constants import _VIEW_CORPUS
        from tests.conftest import pin_view

        at = self._open(raw_gaze, demo_first=False)
        pin_view(at, _VIEW_CORPUS)
        at.run()
        assert not at.exception, at.exception
        text = " ".join(i.value for i in at.info)
        assert "this dataset has no AOI table" in text
        assert "Raw gaze samples carry no reading measures" in text

    def test_the_heatmap_greys_only_with_neither_fixations_nor_words(self, raw_gaze):
        """No fixations and no words: nothing for the heatmap to draw. Words
        alone keep it live — it draws from the word boxes' own measures."""
        at = self._open(raw_gaze, demo_first=False)
        assert at.toggle(key="global_show_heatmap").disabled
        words, _ = api.load_scanpath_data(*sps.load_sample_data())
        pid, tid = _key(raw_gaze)
        trial_words = words[
            (words["participant_id"] == pid) & (words["trial_id"] == tid)
        ]
        at = self._open(raw_gaze, words=trial_words, demo_first=False)
        assert not at.toggle(key="global_show_heatmap").disabled
        assert at.toggle(key="global_show_fix").disabled


# -----------------------------------------------------------------------------
# Review round 2 — list_trials, multipart samples, the layer switched off
# -----------------------------------------------------------------------------


def test_list_trials_adds_only_trials_neither_table_covers(raw_gaze):
    """A trial the words∩fixations rule leaves out on purpose stays out when
    its samples are passed too — only a trial *neither* table has is added."""
    words, fixations = api.load_scanpath_data(*sps.load_sample_data())
    pid, tid = _key(raw_gaze)
    words = words[~((words["participant_id"] == pid) & (words["trial_id"] == tid))]
    without = sps.list_trials(words, fixations)
    assert len(sps.list_trials(words, fixations, raw_gaze=raw_gaze)) == len(without)
    extra = raw_gaze.assign(trial_id="samples_only", unique_trial_id="samples_only")
    assert len(sps.list_trials(words, fixations, raw_gaze=extra)) == len(without) + 1


@pytest.fixture(scope="module")
def two_screen_raw_gaze(raw_gaze) -> pd.DataFrame:
    half = len(raw_gaze) // 2
    screens = ["s1"] * half + ["s2"] * (len(raw_gaze) - half)
    return raw_gaze.assign(screen_id=screens)


def test_multipart_samples_draw_one_screen_at_a_time(two_screen_raw_gaze):
    pid, tid = _key(two_screen_raw_gaze)
    parts = sps.list_parts(None, None, pid, tid, raw_gaze=two_screen_raw_gaze)
    assert list(parts["screen_id"]) == ["s1", "s2"]
    first = sps.plot_scanpath(raw_gaze=two_screen_raw_gaze)
    second = sps.plot_scanpath(raw_gaze=two_screen_raw_gaze, screen="s2")
    n_first = int((two_screen_raw_gaze["screen_id"] == "s1").sum())
    assert len(first.data[0].x) == n_first
    assert len(second.data[0].x) == len(two_screen_raw_gaze) - n_first
    with pytest.raises(ValueError, match="Unknown screen"):
        sps.plot_scanpath(raw_gaze=two_screen_raw_gaze, screen="s9")


def test_render_lists_the_screens_of_multipart_samples(
    two_screen_raw_gaze, tmp_path, capsys
):
    path = tmp_path / "gaze.csv"
    two_screen_raw_gaze.to_csv(path, index=False)
    cli.main(
        [
            "render",
            "--raw-gaze",
            str(path),
            "--raw-gaze-schema",
            '{"participant": "participant_id", "trial": "trial_id", '
            '"screen_id": "screen_id", "x": "x", "y": "y", '
            '"timestamp": "timestamp_ms"}',
            "--list-parts",
        ]
    )
    out = capsys.readouterr().out
    assert "s1" in out and "s2" in out


def test_the_layer_switched_off_is_written_out(raw_gaze, tmp_path):
    """`plot_scanpath` turns the layer on for the frame it is handed, so on a
    samples-only source *off* must be written, in both flavours."""
    state = cs.FigureState(
        kind="static",
        settings={**api.figure_options("static"), "show_raw_gaze": False},
        participant=_key(raw_gaze)[0],
        trial=_key(raw_gaze)[1],
    )
    source = cs.SnippetSource(
        kind=cs.SOURCE_RAW_GAZE, options={"raw_gaze": [SAMPLE_RAW_GAZE]}
    )
    code = cs.reproduction_code(source, state)
    assert "show_raw_gaze=False" in code.python
    assert "--no-raw-gaze" in code.cli
    assert not code.cli_unsupported
    # …and both draw no samples.
    assert not sps.plot_scanpath(raw_gaze=raw_gaze, show_raw_gaze=False).data
    out = tmp_path / "off.html"
    cli.main(["render", "--raw-gaze", SAMPLE_RAW_GAZE, "--no-raw-gaze", "-o", str(out)])
    assert '"name":"Raw gaze"' not in out.read_text(encoding="utf-8").replace(" ", "")


def test_render_joins_metadata_against_the_samples(raw_gaze, tmp_path, capsys):
    """With raw gaze as the only input the metadata tables join against its
    readers and trials, not against the empty fixations."""
    pid, _ = _key(raw_gaze)
    readers = tmp_path / "readers.csv"
    readers.write_text(f"participant_id,age\n{pid},30\n", encoding="utf-8")
    cli.main(
        [
            "render",
            "--raw-gaze",
            SAMPLE_RAW_GAZE,
            "--participant-metadata",
            str(readers),
            "--list-trials",
        ]
    )
    err = capsys.readouterr().err
    assert "for 1 reader(s)" in err, err


# -----------------------------------------------------------------------------
# Review round 3
# -----------------------------------------------------------------------------


class TestLinkIsOneVisit:
    RAW = ("Gaze", None)

    def test_a_preset_after_a_link_turns_the_layer_back_on(self):
        from scanpath_studio.controls import _forget_raw_gaze_default

        session = {LAYER: False}  # the link said 0
        seed_raw_gaze_default(
            session, self.RAW, samples_only=True, link_names_layer=True
        )
        assert session[LAYER] is False
        # A built-in quick view: writes the preset's False, drops the link
        # params (so the link no longer names the layer), forgets the decision.
        _forget_raw_gaze_default(session)
        seed_raw_gaze_default(
            session, self.RAW, samples_only=True, link_names_layer=False
        )
        assert session[LAYER] is True

    def test_back_to_the_linked_dataset_does_not_drop_the_next_stash(self):
        """A (linked, off) → C (raw-gaze-only) → A → D (fixations): D keeps
        what it had before C turned the layer on."""
        session = {LAYER: False}

        def seed(name, samples_only):
            seed_raw_gaze_default(
                session, (name, None), samples_only=samples_only, link_names_layer=True
            )

        seed("A", True)
        assert session[LAYER] is False
        seed("C", True)
        assert session[LAYER] is True
        seed("A", True)  # an ordinary visit now — the link was spent on C
        seed("D", False)
        assert session[LAYER] is False


def _words_and_samples_without_fixations(raw_gaze):
    """The demo with the raw-gaze trial's fixations removed: that trial has
    words and samples, and every other trial has fixations."""
    words, fixations = api.load_scanpath_data(*sps.load_sample_data())
    pid, tid = _key(raw_gaze)
    fixations = fixations[
        ~((fixations["participant_id"] == pid) & (fixations["trial_id"] == tid))
    ]
    return words, fixations


def test_the_api_lists_and_draws_a_words_and_samples_trial(raw_gaze):
    words, fixations = _words_and_samples_without_fixations(raw_gaze)
    pid, tid = _key(raw_gaze)
    trials = sps.list_trials(words, fixations, raw_gaze=raw_gaze)
    assert (pid, tid) in set(trials.itertuples(index=False, name=None))
    fig = sps.plot_scanpath(words, fixations, pid, tid, raw_gaze=raw_gaze)
    names = [trace.name for trace in fig.data]
    assert "Raw gaze" in names and "words" in names


def test_list_parts_decides_per_trial(raw_gaze, two_screen_raw_gaze):
    """In a dataset with fixations for other trials, a samples-only trial
    keeps both of its screens headlessly, as it does in the app."""
    words, fixations = api.load_scanpath_data(*sps.load_sample_data())
    samples = two_screen_raw_gaze.assign(
        trial_id="samples_only", unique_trial_id="samples_only"
    )
    pid = str(samples["participant_id"].iloc[0])
    parts = sps.list_parts(words, fixations, pid, "samples_only", raw_gaze=samples)
    assert list(parts["screen_id"]) == ["s1", "s2"]
    second = sps.plot_scanpath(
        words, fixations, pid, "samples_only", raw_gaze=samples, screen="s2"
    )
    assert len(second.data[0].x) == int((samples["screen_id"] == "s2").sum())


def test_no_raw_gaze_without_a_table_warns(tmp_path, capsys):
    cli.main(["render", "--sample", "--no-raw-gaze", "-o", str(tmp_path / "x.html")])
    assert "--no-raw-gaze hides the raw-gaze layer" in capsys.readouterr().err


@pytest.mark.timeout(240)
class TestRound3App(TestScanpathView):
    def test_the_app_lists_the_trial_the_api_lists(self, raw_gaze):
        words, fixations = _words_and_samples_without_fixations(raw_gaze)
        at = self._open(raw_gaze, words=words, fixations=fixations, demo_first=False)
        _, tid = _key(raw_gaze)
        options = [str(o) for o in at.selectbox(key="single_trial_id").options]
        assert any(tid in option for option in options)

    def test_the_no_fixations_note_is_said_once_per_popover(self, raw_gaze):
        at = self._open(raw_gaze, demo_first=False)
        captions = [c.value for c in at.caption]
        note = [c for c in captions if "so there is nothing here to draw" in c]
        heat = [c for c in captions if "nothing for the heatmap to draw" in c]
        # Fixations, Saccades and Filter: one each.
        assert len(note) == 3, note
        assert len(heat) == 1, heat
