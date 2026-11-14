"""MultiplEYE on every surface: Add dataset's format, Share → Code, the CLI, the API.
Experimental: the suite runs with ``SCANPATH_EXPERIMENTAL=1``.

The wizard reads a session set from a folder (a local install) or from uploaded
files, pre-answers Recording setup from the session set's own config, and stores
it like any dataset, with a recipe Share → Code turns back into
``load_multipleye``.
"""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import scanpath_studio as sps
from scanpath_studio import cli
from scanpath_studio import code_snippet as cs
from tests.conftest import APP_SCRIPT, pin_data_view
from tests.multipleye_fixtures import MONITOR, OFF_X, mpe_upload_frames
from tests.test_multipleye_enrichment import READER_A, build_multipleye_tree

pytestmark = pytest.mark.timeout(180)


def _wizard(monkeypatch, *, local: bool, source: str | None = None) -> AppTest:
    monkeypatch.setenv("SCANPATH_LOCAL_FS", "1" if local else "0")
    from scanpath_studio import app

    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.session_state["_show_upload_wizard"] = True
    at.session_state["setup_complete"] = False
    at.session_state["wizard_dataset_format"] = "MultiplEYE"
    if source is not None:
        at.session_state["wizard_multipleye_from"] = source
    pin_data_view(at)
    return at


def _uploads(monkeypatch, frames: dict) -> None:
    from scanpath_studio import app

    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
    )


@pytest.fixture
def session_set(tmp_path):
    return build_multipleye_tree(tmp_path / "MultiplEYE_Demo")


class TestFromAFolder:
    def test_a_folder_is_read_and_recording_setup_comes_from_its_config(
        self, monkeypatch, session_set
    ):
        at = _wizard(monkeypatch, local=True)
        at.session_state["wizard_multipleye_dir"] = str(session_set)
        at.run()

        assert not at.exception, at.exception
        assert at.error == [], [e.value for e in at.error]
        # The generic mapping is not drawn for this format.
        assert "col_map_fix_duration" not in {s.key for s in at.selectbox}
        payload = at.session_state["_wizard_finalize_payload"]
        fixations = payload["fixations"]
        assert set(fixations["text_id"]) == {"Lit_Demo_1", "Arg_Other_2"}
        # One Trial ID per reading: the session, then the stimulus.
        assert fixations.groupby("trial_id")["participant_id"].nunique().eq(1).all()
        assert fixations["x"].min() >= OFF_X  # placed on the monitor
        # Recording setup: the monitor is the config's, measured, not estimated.
        setup = payload["setup"]
        assert (setup["canvas_width"], setup["canvas_height"]) == MONITOR
        assert setup["provenance"]["screen"] == "measured"
        assert payload["source_recipe"]["multipleye"] == {"root": str(session_set)}
        # The session set's own reading measures come along, as they do from
        # `load_multipleye`, so Corpus Analysis has them.
        from scanpath_studio.data import brought_reading_measures
        from scanpath_studio.datasets import load_multipleye

        api_words, _ = load_multipleye(session_set, names="canonical")
        brought = brought_reading_measures(payload["words"])
        assert brought and brought == brought_reading_measures(api_words)

    def test_add_dataset_stores_it_and_share_code_reads_the_folder_again(
        self, monkeypatch, session_set
    ):
        at = _wizard(monkeypatch, local=True)
        at.session_state["wizard_dataset_name"] = "Zurich demo"
        at.session_state["wizard_multipleye_dir"] = str(session_set)
        at.run()
        finalize = next(b for b in at.button if b.key == "wizard_finalize")
        assert not finalize.disabled
        finalize.click().run()

        assert not at.exception, at.exception
        stored = at.session_state["_datasets"]["Zurich demo"]
        assert not stored["fixations"].empty
        source = cs.upload_source(
            "Zurich demo",
            stored["source_recipe"],
            words=True,
            fixations=True,
        )
        assert source.kind == cs.SOURCE_MULTIPLEYE
        python = "\n".join(cs._multipleye_python(source))
        assert f"sps.load_multipleye(\n    {str(session_set)!r}," in python
        assert cs._multipleye_cli(source) == ["--multipleye", str(session_set)]

    def test_a_folder_without_config_is_not_placed_on_any_monitor(
        self, monkeypatch, tmp_path
    ):
        root = build_multipleye_tree(
            tmp_path / "set", reading_measures=False, config=False
        )
        at = _wizard(monkeypatch, local=True)
        at.session_state["wizard_multipleye_dir"] = str(root)
        at.run()

        assert not at.exception, at.exception
        payload = at.session_state["_wizard_finalize_payload"]
        assert payload["fixations"]["x"].min() == 90  # image-relative
        assert "canvas_width" not in payload["fixations"].columns
        # The screen falls back to the answer every dataset starts from.
        assert payload["setup"]["provenance"]["screen"] == "estimated"
        notes = " ".join(c.value for c in at.caption)
        assert "doesn't give the monitor resolution, the stimulus image size" in notes

    def test_a_missing_folder_blocks_add_dataset(self, monkeypatch, tmp_path):
        at = _wizard(monkeypatch, local=True)
        at.session_state["wizard_multipleye_dir"] = str(tmp_path / "nowhere")
        at.run()

        assert not at.exception, at.exception
        assert any("There is no folder at" in e.value for e in at.error)
        assert "_wizard_finalize_payload" not in at.session_state
        finalize = next(b for b in at.button if b.key == "wizard_finalize")
        assert finalize.disabled

    def test_a_shared_server_offers_uploads_only(self, monkeypatch):
        _uploads(monkeypatch, {})
        at = _wizard(monkeypatch, local=False, source="folder")
        at.run()

        assert not at.exception, at.exception
        assert at.session_state["wizard_multipleye_from"] == "upload"
        assert not [t for t in at.text_input if t.label == "Data directory"]


class TestFromUploads:
    def test_uploads_build_one_trial_per_stimulus(self, monkeypatch):
        scan, aoi = mpe_upload_frames()
        _uploads(monkeypatch, {"mpe_fix": scan, "mpe_aoi": aoi})
        at = _wizard(monkeypatch, local=True, source="upload")
        at.run()

        assert not at.exception, at.exception
        assert at.error == [], [e.value for e in at.error]
        payload = at.session_state["_wizard_finalize_payload"]
        assert payload["composite_trial_columns"] == []
        assert payload["filter_fields"] == ["genre", "session", "is_practice"]
        fixations = payload["fixations"]
        assert set(fixations["trial_id"]) == {"001_ZH_CH_1_ET1_Lit_Demo_1"}
        assert set(fixations["screen_id"]) == {"page_1", "page_2"}
        assert not payload["words"].empty
        # No config uploaded: the coordinates stay the image's own.
        assert fixations["x"].min() == 90
        assert payload["source_recipe"]["multipleye"]["root"] is None

    def test_add_dataset_stores_the_upload(self, monkeypatch):
        scan, aoi = mpe_upload_frames()
        _uploads(monkeypatch, {"mpe_fix": scan, "mpe_aoi": aoi})
        at = _wizard(monkeypatch, local=True, source="upload")
        at.run()
        next(b for b in at.button if b.key == "wizard_finalize").click().run()

        assert not at.exception, at.exception
        stored = next(iter(at.session_state["_datasets"].values()))
        assert not stored["fixations"].empty
        assert stored["composite_trial_columns"] == []

    def test_unrecognized_file_names_block(self, monkeypatch):
        bad = pd.DataFrame(
            {
                "onset": [1],
                "duration": [1],
                "location_x": [1.0],
                "location_y": [1.0],
                "page": ["page_1"],
                "word_idx": [0],
            }
        )
        bad["source_file"] = "not_a_multipleye_name"
        _uploads(monkeypatch, {"mpe_fix": bad})
        at = _wizard(monkeypatch, local=True, source="upload")
        at.run()

        assert not at.exception, at.exception
        assert any("No MultiplEYE file names recognized" in e.value for e in at.error)
        assert "_wizard_finalize_payload" not in at.session_state

    def test_questions_and_participant_metadata_ride_along(self, monkeypatch):
        import json

        scan, aoi = mpe_upload_frames()
        questions = pd.DataFrame(
            {
                "stimulus_name": ["Lit_Demo"],
                "stimulus_id": [1],
                "question": ["Why?"],
                "target": ["Because"],
                "condition_name": ["local"],
                "question_no": [1],
                "condition_no": [1],
            }
        )
        participant = pd.DataFrame(
            {"participant_id": [1], "session": ["ET1"], "age": [22], "gender": ["F"]}
        )
        _uploads(
            monkeypatch,
            {
                "mpe_fix": scan,
                "mpe_aoi": aoi,
                "mpe_questions": questions,
                "mpe_participant": participant,
            },
        )
        at = _wizard(monkeypatch, local=True, source="upload")
        at.run()

        assert not at.exception, at.exception
        payload = at.session_state["_wizard_finalize_payload"]
        fixations = payload["fixations"]
        assert fixations["pp_age"].dropna().iloc[0] == 22
        assert fixations["pp_gender"].dropna().iloc[0] == "F"
        q = json.loads(payload["words"]["comprehension_questions"].dropna().iloc[0])
        assert q[0]["target"] == "Because"


def test_recording_setup_takes_each_value_the_config_gives():
    """`_apply_multipleye_screen` answers *I know it* with the config's values,
    and a new session set clears what the previous one set."""
    import streamlit as st

    from scanpath_studio import wizard
    from scanpath_studio.datasets import MultiplEYEScreen

    st.session_state.clear()
    wizard._apply_multipleye_screen(
        MultiplEYEScreen(
            monitor_px=(1920, 1080),
            image_px=(1310, 991),
            screen_size_cm=(54.2, 30.5),
            distance_cm=60.0,
            font_px=28.0,
            font_family="'Noto Sans Mono CJK SC', monospace",
        )
    )
    ss = st.session_state
    assert ss["wizard_setup_screen_mode"] == wizard._SCREEN_KNOW
    assert ss["wizard_setup_geometry_mode"] == wizard._GEOM_KNOW
    assert ss["wizard_setup_text_mode"] == wizard._TEXT_FONT
    assert ss["wizard_setup_font_unit"] == "px"
    recall = ss["_wizard_setup_recall"]
    assert (recall["canvas_width"], recall["canvas_height"]) == (1920, 1080)
    assert recall["monitor_width_mm"] == pytest.approx(542.0)
    assert recall["viewing_distance_mm"] == pytest.approx(600.0)
    assert recall["base_font_size"] == 28

    # A monitor without an image size places nothing, so it answers nothing.
    wizard._apply_multipleye_screen(MultiplEYEScreen(monitor_px=(1920, 1080)))
    assert "wizard_setup_screen_mode" not in ss
    assert "wizard_setup_geometry_mode" not in ss
    assert "wizard_setup_text_mode" not in ss
    st.session_state.clear()


class TestCliAndApi:
    def test_load_multipleye_resolves_from_the_package_but_is_not_listed(self):
        """Experimental: reachable as ``sps.load_multipleye``, not advertised."""
        assert "load_multipleye" not in sps.__all__
        assert sps.load_multipleye.__module__ == "scanpath_studio.datasets"

    def test_render_lists_and_draws_a_session_set(self, session_set, tmp_path, capsys):
        cli.main(["render", "--multipleye", str(session_set), "--list-trials"])
        listed = capsys.readouterr().out
        assert READER_A in listed and "Lit_Demo_1" in listed

        out = tmp_path / "page.html"
        cli.main(
            [
                "render",
                "--multipleye",
                str(session_set),
                "-p",
                READER_A.lower(),
                "-t",
                f"{READER_A}_Lit_Demo_1",
                "--screen",
                "page_1",
                "-o",
                str(out),
            ]
        )
        assert out.stat().st_size > 0

    def test_render_help_lists_one_multipleye_flag(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["render", "--help"])
        text = capsys.readouterr().out
        assert "--multipleye DIR" in text
        assert "--multipleye-fixations" not in text
        assert "--no-question-screens" not in text

    def test_the_snippet_reads_the_session_set_again(self):
        source = cs.SnippetSource(kind=cs.SOURCE_MULTIPLEYE, options={"root": "d/MPE"})
        python = "\n".join(cs._multipleye_python(source))
        assert python == "words, fixations = sps.load_multipleye(\n    'd/MPE',\n)"
        assert cs._multipleye_cli(source) == ["--multipleye", "d/MPE"]
        # Each session set stamps its own monitor, so the snippet passes none.
        assert cs.source_canvas(cs.SOURCE_MULTIPLEYE) is None


class TestTheFolderReadIsCachedHonestly:
    def test_the_signature_sees_a_new_trial_file_and_an_edited_config(
        self, session_set
    ):
        from scanpath_studio import wizard
        from tests.multipleye_fixtures import write_screen_config

        before = wizard._multipleye_folder_signature(str(session_set))
        assert before == wizard._multipleye_folder_signature(str(session_set))
        session = next((session_set / "scanpaths").iterdir())
        (session / "new_trial.csv").write_text("x\n")
        after_trial = wizard._multipleye_folder_signature(str(session_set))
        assert after_trial != before
        write_screen_config(session_set, monitor=(2560, 1440))
        assert wizard._multipleye_folder_signature(str(session_set)) != after_trial

    def test_a_folder_without_word_boxes_fails_before_reading_trials(
        self, session_set, monkeypatch
    ):
        import shutil

        from scanpath_studio import datasets

        shutil.rmtree(session_set / "stimuli_Demo" / "aoi_stimuli_demo")
        read = []
        monkeypatch.setattr(
            datasets, "_multipleye_fixations", lambda *a, **k: read.append(1)
        )
        with pytest.raises(FileNotFoundError, match="AOI directory"):
            datasets.multipleye_raw_frames(session_set)
        assert read == []


class TestWhatTheOtherSurfacesSay:
    def test_a_share_link_says_to_add_the_session_set_again(self, monkeypatch):
        """A MultiplEYE dataset has no mapping to send; the recipient adds the
        same session set the same way."""
        from scanpath_studio import url_state
        from tests.test_app import _FakeSt

        fake = _FakeSt()
        fake.session_state = {
            "_datasets": {
                "Zurich": {"source_recipe": {"multipleye": {"root": "/d/MPE"}}},
                "Mine": {"source_recipe": {"schemas": {}}},
            }
        }
        monkeypatch.setattr(url_state, "st", fake)
        _query, caveats = url_state._build_share_query("Zurich")
        assert any("MultiplEYE session set" in c for c in caveats)
        assert not any("Download setup file" in c for c in caveats)
        _query, caveats = url_state._build_share_query("Mine")
        assert any("Download setup file" in c for c in caveats)

    def test_edit_dataset_offers_no_setup_file_for_a_session_set(
        self, monkeypatch, session_set
    ):
        from scanpath_studio.constants import DATASET_EDITOR_OPEN_KEY

        at = _wizard(monkeypatch, local=True)
        at.session_state["wizard_dataset_name"] = "Zurich demo"
        at.session_state["wizard_multipleye_dir"] = str(session_set)
        at.run()
        next(b for b in at.button if b.key == "wizard_finalize").click().run()
        pin_data_view(at)
        at.session_state[DATASET_EDITOR_OPEN_KEY] = True
        at.run()

        assert not at.exception, at.exception
        assert any(b.key == "remap_apply_Zurich demo" for b in at.button)
        downloads = [d.proto.id for d in at.get("download_button")]
        assert not any("remap_setup_download" in d for d in downloads)
        assert any(
            "created from a MultiplEYE session set" in c.value for c in at.caption
        )

    def test_the_snippet_says_what_the_loader_cannot_replay(self):
        uploaded = cs.upload_source(
            "MPE", {"multipleye": {"root": None}}, words=True, fixations=True
        )
        assert "that the upload left out" in uploaded.note
        edited = cs.upload_source(
            "MPE",
            {"multipleye": {"root": "/d/MPE"}, "schemas": {"words": {"text": "word"}}},
            words=True,
            fixations=True,
        )
        assert "changed in Edit dataset" in edited.note


def test_labels_in_a_cjk_font_sit_on_the_stimulus_text():
    """Plotly centres every font's labels with one fixed shift, which draws
    Noto Sans (Mono) CJK about 0.15 em above the line its stimulus pages were
    typeset on; labels in a CJK font are lowered by that much, and a Latin
    font's are left at their box's middle."""
    import plotly.graph_objects as go

    from scanpath_studio import plots

    words = pd.DataFrame(
        {"text": ["月球", "Moon"], "x": [0.0, 100.0], "y": [10.0, 10.0]}
        | {"width": [56.0, 56.0], "height": [34.0, 34.0], "word_id": [1, 2]}
    )
    cjk = "'Noto Sans Mono CJK SC', 'Noto Sans CJK SC', monospace"
    for family, drop in ((cjk, 0.15 * 28), ("monospace", 0.0)):
        fig = go.Figure()
        plots._add_word_label_trace(fig, words, 28, family)
        assert list(fig.data[0].y) == pytest.approx([27.0 + drop, 27.0 + drop])
    # Half the screen px per data unit: the same drop is twice as many units.
    fig = go.Figure()
    plots._add_word_label_trace(fig, words, 28, cjk, px_per_unit=0.5)
    assert fig.data[0].y[0] == pytest.approx(27.0 + 0.15 * 56)


def test_adjacent_full_width_marks_keep_their_width():
    """A browser trims the space between two full-width marks side by side,
    so a centred label would slide off the stimulus text; a word joiner
    between them keeps each mark its em, and nothing else changes."""
    from scanpath_studio import plots

    wj = "⁠"
    assert plots._keep_punctuation_width("光秒），或约") == f"光秒）{wj}，或约"
    assert plots._keep_punctuation_width("好。」「好") == f"好。{wj}」{wj}「好"
    for unchanged in ("（即英里", "Moon", "30倍。", "a), b", ""):
        assert plots._keep_punctuation_width(unchanged) == unchanged
