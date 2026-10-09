"""#417 — each dataset's stimulus-image folder is its own, saved with it.

The folder and filename pattern used to be two session-wide text boxes on
✏️ Edit dataset: they applied to whichever dataset was open, followed the user
to the next one, and were gone after a restart. They are now stored per dataset
(`constants.DATASET_STIMULUS_IMAGES_KEY`), asked for on the add screen too, and
saved by the editor's ✅ Save changes like everything else on it.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio.constants import DATASET_STIMULUS_IMAGES_KEY


@pytest.fixture
def session():
    import streamlit as st

    st.session_state.clear()
    yield st.session_state
    st.session_state.clear()


class TestTheStoredSource:
    def test_anything_malformed_names_no_folder(self):
        from scanpath_studio.data import stimulus_image_source

        for value in (None, "x", {}, {"folder": ""}, {"folder": "  "}, {"folder": 3}):
            assert stimulus_image_source(value) is None

    def test_a_blank_pattern_is_the_default_one(self):
        from scanpath_studio.data import stimulus_image_source

        assert stimulus_image_source({"folder": " ~/imgs ", "pattern": " "}) == {
            "folder": "~/imgs",
            "pattern": "{text_id}.png",
        }
        assert stimulus_image_source(
            {"folder": "/imgs", "pattern": "{trial_id}.jpg"}
        ) == {"folder": "/imgs", "pattern": "{trial_id}.jpg"}

    def test_the_recovery_cache_keeps_it_per_dataset(self, tmp_path):
        from scanpath_studio import persistence
        from scanpath_studio.persistence import restore_state, save_state

        assert DATASET_STIMULUS_IMAGES_KEY in persistence._SESSION_KEYS
        source = {
            DATASET_STIMULUS_IMAGES_KEY: {
                "My corpus": {"folder": "/imgs", "pattern": "{trial_id}.png"},
                "Bundled Demo": {"folder": "", "pattern": "x"},
                "Broken": "not a source",
            }
        }
        assert save_state(source, tmp_path)
        restored: dict = {}
        assert restore_state(restored, tmp_path)
        assert restored[DATASET_STIMULUS_IMAGES_KEY] == {
            "My corpus": {"folder": "/imgs", "pattern": "{trial_id}.png"}
        }

    def test_it_is_not_on_the_wire(self):
        """A machine-local path: never a share-link param or a settings-file
        key."""
        from scanpath_studio import session_keys

        names = {
            str(value)
            for value in vars(session_keys).values()
            if isinstance(value, str)
        }
        assert DATASET_STIMULUS_IMAGES_KEY not in names
        assert DATASET_STIMULUS_IMAGES_KEY not in session_keys.PLOT_CONFIG_STATE_KEYS


class TestTheEditorWaitsForSave:
    @staticmethod
    def _session(monkeypatch) -> dict:
        from scanpath_studio import app

        state: dict = {}
        monkeypatch.setattr(app.st, "session_state", state)
        return state

    def test_a_folder_is_a_draft_until_save(self, monkeypatch, tmp_path):
        from scanpath_studio import app

        state = self._session(monkeypatch)
        state["_datasets"] = {"Probe": {}}
        app.hold_editor_staging("Probe")
        folder_key, pattern_key = app._stimulus_field_keys("Probe")
        state[folder_key] = str(tmp_path)
        state[pattern_key] = "{trial_id}.png"
        assert app.editor_staging_dirty()
        assert DATASET_STIMULUS_IMAGES_KEY not in state
        app.commit_editor_staging("Probe")
        assert state[DATASET_STIMULUS_IMAGES_KEY] == {
            "Probe": {"folder": str(tmp_path), "pattern": "{trial_id}.png"}
        }
        assert folder_key not in state and pattern_key not in state

    def test_a_cancelled_folder_is_dropped(self, monkeypatch, tmp_path):
        from scanpath_studio import app

        state = self._session(monkeypatch)
        app.hold_editor_staging("Probe")
        folder_key, _ = app._stimulus_field_keys("Probe")
        state[folder_key] = str(tmp_path)
        app._discard_editor_staging()
        assert folder_key not in state
        assert DATASET_STIMULUS_IMAGES_KEY not in state

    def test_fields_showing_the_saved_folder_are_no_change(self, monkeypatch):
        from scanpath_studio import app

        state = self._session(monkeypatch)
        app.set_dataset_stimulus_images("Probe", "/imgs", "")
        app.hold_editor_staging("Probe")
        folder_key, pattern_key = app._stimulus_field_keys("Probe")
        state[folder_key] = "/imgs"
        state[pattern_key] = "{text_id}.png"
        assert app._stimulus_images_draft("Probe") is None
        assert not app.editor_staging_dirty()

    def test_clearing_the_folder_forgets_it(self, monkeypatch):
        from scanpath_studio import app

        state = self._session(monkeypatch)
        app.set_dataset_stimulus_images("Probe", "/imgs", "")
        app.set_dataset_stimulus_images("Other", "/other", "")
        app.hold_editor_staging("Probe")
        folder_key, pattern_key = app._stimulus_field_keys("Probe")
        state[folder_key] = ""
        state[pattern_key] = "{text_id}.png"
        assert app.editor_staging_dirty()
        app.commit_editor_staging("Probe")
        assert app.dataset_stimulus_images("Probe") is None
        assert app.dataset_stimulus_images("Other") == {
            "folder": "/other",
            "pattern": "{text_id}.png",
        }


def _resolve_app() -> None:
    import pandas as pd
    import streamlit as st

    from scanpath_studio import app

    words = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t2"],
            "text_id": ["a", "b"],
            "word_id": [0, 0],
        }
    )
    fixations = pd.DataFrame(
        {"participant_id": ["p1"], "trial_id": ["t1"], "text_id": ["a"]}
    )
    from scanpath_studio.data import frame_fingerprint

    out = {}
    for token in ("Mine", "Other"):
        result = app.with_dataset_stimulus_images(token, words, fixations)
        w, f = result.words, result.fixations
        out[token] = (
            w["image_path"].tolist() if "image_path" in w else None,
            f["image_path"].tolist() if "image_path" in f else None,
            id(w),
            frame_fingerprint(w),
            result.found,
            result.problem,
            w is words,
        )
    st.session_state["_probe"] = out


class TestTheFiguresUseTheOpenDatasetsFolder:
    def _run(self, tmp_path, at=None):
        if at is None:
            at = AppTest.from_function(_resolve_app)
            at.session_state[DATASET_STIMULUS_IMAGES_KEY] = {
                "Mine": {"folder": str(tmp_path), "pattern": "{text_id}.png"}
            }
        at.run()
        assert not at.exception, at.exception
        return at, at.session_state["_probe"]

    def test_only_the_dataset_it_was_saved_for(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"")
        _, out = self._run(tmp_path)
        words, fixations, *_ = out["Mine"]
        image = str((tmp_path / "a.png").resolve())
        assert words == [image, None]
        assert fixations == [image]
        assert out["Mine"][4] == 2  # rows the folder found an image for
        # Another dataset is drawn without them.
        assert out["Other"][:2] == (None, None)

    def test_a_folder_that_finds_nothing_hands_the_frames_back(self, tmp_path):
        """Nothing downstream is rebuilt for an empty, missing or unplugged
        folder: the frames are the very objects that came in."""
        _, out = self._run(tmp_path)
        assert out["Mine"][6] is True
        assert out["Mine"][4] == 0 and out["Mine"][5] is None

    @staticmethod
    def _touch(folder):
        stamp = folder.stat().st_mtime_ns
        os.utime(folder, ns=(stamp, stamp + 1_000_000_000))

    def test_kept_across_reruns_and_redone_when_the_folder_changes(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"")
        at, first = self._run(tmp_path)
        at, again = self._run(tmp_path, at)
        assert again["Mine"][2] == first["Mine"][2]  # the same frames, kept
        (tmp_path / "b.png").write_bytes(b"")
        self._touch(tmp_path)
        _, after = self._run(tmp_path, at)
        assert after["Mine"][0] == [
            str((tmp_path / "a.png").resolve()),
            str((tmp_path / "b.png").resolve()),
        ]
        assert after["Mine"][3] != first["Mine"][3]

    def test_a_stray_file_rebuilds_nothing_downstream(self, tmp_path):
        """The folder is looked at again when it changes, but the frames are
        named by what was found: the same images, the same fingerprint, so no
        cache keyed by them misses."""
        (tmp_path / "a.png").write_bytes(b"")
        at, first = self._run(tmp_path)
        (tmp_path / ".DS_Store").write_bytes(b"")
        self._touch(tmp_path)
        _, after = self._run(tmp_path, at)
        assert after["Mine"][3] == first["Mine"][3]

    def test_a_pattern_outside_the_folder_draws_none_and_says_why(self, tmp_path):
        at = AppTest.from_function(_resolve_app)
        at.session_state[DATASET_STIMULUS_IMAGES_KEY] = {
            "Mine": {"folder": str(tmp_path), "pattern": "../{text_id}.png"}
        }
        _, out = self._run(tmp_path, at)
        assert out["Mine"][:2] == (None, None)
        assert "outside the selected folder" in out["Mine"][5]

    def test_an_image_linked_into_the_folder_is_found(self, tmp_path):
        """Only the pattern's spelling must stay inside the folder: a file
        the user linked in from elsewhere is theirs to use."""
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "a.png").write_bytes(b"")
        folder = tmp_path / "images"
        folder.mkdir()
        (folder / "a.png").symlink_to(elsewhere / "a.png")
        _, out = self._run(folder)
        assert out["Mine"][4] == 2 and out["Mine"][5] is None


class TestTheAddScreen:
    @staticmethod
    def _payload():
        words = pd.DataFrame(
            {
                "participant_id": ["p1"],
                "trial_id": ["t1"],
                "word_id": [1],
                "text": ["a"],
                "x": [0.0],
                "y": [0.0],
                "width": [10.0],
                "height": [10.0],
            }
        )
        return {"words": words, "fixations": pd.DataFrame(), "raw_gaze": pd.DataFrame()}

    def test_add_dataset_saves_the_folder_under_its_name(self, session, tmp_path):
        from scanpath_studio import app, wizard

        session["_wizard_finalize_payload"] = self._payload()
        session["wizard_dataset_name"] = "My corpus"
        session[wizard.WIZARD_IMAGES_FOLDER_KEY] = str(tmp_path)
        session[wizard.WIZARD_IMAGES_PATTERN_KEY] = "{trial_id}.png"
        wizard._finalize_wizard_dataset()
        assert app.dataset_stimulus_images("My corpus") == {
            "folder": str(tmp_path),
            "pattern": "{trial_id}.png",
        }

    def test_a_blank_folder_saves_nothing(self, session):
        from scanpath_studio import wizard

        session["_wizard_finalize_payload"] = self._payload()
        session["wizard_dataset_name"] = "My corpus"
        session[wizard.WIZARD_IMAGES_PATTERN_KEY] = "{trial_id}.png"
        wizard._finalize_wizard_dataset()
        assert not session.get(DATASET_STIMULUS_IMAGES_KEY)

    def test_a_new_dataset_starts_with_empty_fields(self, session):
        from scanpath_studio import wizard

        session[wizard.WIZARD_IMAGES_FOLDER_KEY] = "/left/over"
        session[wizard.WIZARD_IMAGES_PATTERN_KEY] = "{trial_id}.png"
        wizard._reset_wizard_widgets()
        assert wizard.WIZARD_IMAGES_FOLDER_KEY not in session
        assert wizard.WIZARD_IMAGES_PATTERN_KEY not in session

    def test_the_folder_follows_a_rename_and_leaves_with_the_dataset(self, session):
        from scanpath_studio import app, wizard

        session["_datasets"] = {"My corpus": {"words": "My corpus"}}
        session["data_source_choice"] = "My corpus"
        app.set_dataset_stimulus_images("My corpus", "/imgs", "")
        wizard.rename_dataset("My corpus", "Pilot")
        assert set(session[DATASET_STIMULUS_IMAGES_KEY]) == {"Pilot"}
        wizard._remove_dataset("Pilot")
        assert session[DATASET_STIMULUS_IMAGES_KEY] == {}


@pytest.mark.timeout(180)
class TestThePart:
    @staticmethod
    def _wizard(monkeypatch, local: str):
        from scanpath_studio import app
        from tests.conftest import APP_SCRIPT

        monkeypatch.setenv("SCANPATH_LOCAL_FS", local)
        words = pd.DataFrame(
            {
                "reader": ["r0"] * 3,
                "trial": ["t1"] * 3,
                "IA_ID": [0, 1, 2],
                "IA_LABEL": ["the", "cat", "sat"],
                "IA_LEFT": [0, 80, 160],
                "IA_RIGHT": [80, 160, 240],
                "IA_TOP": [0, 0, 0],
                "IA_BOTTOM": [40, 40, 40],
            }
        )
        fixations = pd.DataFrame(
            {
                "reader": ["r0", "r0"],
                "trial": ["t1", "t1"],
                "CURRENT_FIX_X": [20.0, 100.0],
                "CURRENT_FIX_Y": [20.0, 20.0],
                "CURRENT_FIX_DURATION": [200, 220],
                "CURRENT_FIX_START": [0, 200],
            }
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                words
                if kw["state_prefix"] == "col_map_words"
                else fixations
                if kw["state_prefix"] == "col_map_fix"
                else pd.DataFrame()
            ),
        )
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state["setup_complete"] = False
        at.run(timeout=120)
        assert not at.exception, at.exception
        return at

    @staticmethod
    def _parts(at) -> list[str]:
        return [
            str(md.value)
            for md in at.markdown
            if str(md.value).startswith('<div class="sps-wiz-part"')
        ]

    def test_the_add_screen_asks_for_the_folder_on_a_local_install(
        self, monkeypatch, tmp_path
    ):
        from scanpath_studio import wizard

        at = self._wizard(monkeypatch, "1")
        parts = self._parts(at)
        assert len(parts) == 4 and "Stimulus images" in parts[3]
        assert '<span class="sps-wiz-part-n">4</span>' in parts[3]
        (tmp_path / "t1.png").write_bytes(b"")
        next(
            t for t in at.text_input if t.key == wizard.WIZARD_IMAGES_FOLDER_KEY
        ).input(str(tmp_path))
        next(
            t for t in at.text_input if t.key == wizard.WIZARD_IMAGES_PATTERN_KEY
        ).input("{trial_id}.png")
        at.run(timeout=120)
        assert not at.exception, at.exception
        captions = " ".join(str(c.value) for c in at.caption)
        # Three word boxes and two fixations, all of trial t1.
        assert "Found an image in this folder for 5 rows." in captions

    def test_and_not_where_a_path_means_nothing(self, monkeypatch):
        from scanpath_studio import wizard

        at = self._wizard(monkeypatch, "0")
        parts = self._parts(at)
        assert len(parts) == 3
        assert not any("Stimulus images" in part for part in parts)
        assert wizard.WIZARD_IMAGES_FOLDER_KEY not in {t.key for t in at.text_input}


@pytest.mark.timeout(300)
def test_the_editor_saves_the_folder_with_its_dataset(tmp_path):
    """✏️ Edit dataset draws the fields only while it is open, seeded from the
    open dataset's own folder, and ✅ Save changes is what stores them — for a
    built-in dataset as for an added one."""
    from scanpath_studio import app
    from scanpath_studio.constants import DEMO_CHOICE, SYNTHETIC_CHOICE
    from tests.conftest import APP_SCRIPT, pin_data_view

    folder_key, pattern_key = app._stimulus_field_keys(DEMO_CHOICE)

    def run(at):
        pin_data_view(at)
        at.run(timeout=90)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

    def field_keys(at):
        return {t.key for t in at.text_input}

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = DEMO_CHOICE
    run(at)
    assert folder_key not in field_keys(at)  # the editor is closed

    at.button(key=f"dataset_row_edit_{app._dataset_row_slug(DEMO_CHOICE)}").click()
    run(at)
    assert {folder_key, pattern_key} <= field_keys(at)
    at.text_input(key=folder_key).input(str(tmp_path))
    run(at)
    assert DATASET_STIMULUS_IMAGES_KEY not in at.session_state  # a draft

    at.button(key="builtin_mapping_save").click()
    run(at)
    assert at.session_state[DATASET_STIMULUS_IMAGES_KEY][DEMO_CHOICE] == {
        "folder": str(tmp_path),
        "pattern": "{text_id}.png",
    }

    # Another dataset's editor starts from its own (no) folder.
    at.session_state["data_source_choice"] = SYNTHETIC_CHOICE
    run(at)
    at.button(key=f"dataset_row_edit_{app._dataset_row_slug(SYNTHETIC_CHOICE)}").click()
    run(at)
    other_folder, _ = app._stimulus_field_keys(SYNTHETIC_CHOICE)
    assert at.text_input(key=other_folder).value == ""


def test_compares_b_draws_its_own_datasets_images(session, tmp_path):
    """Scanpath B from another dataset brings that dataset's folder, not A's."""
    from scanpath_studio import app
    from scanpath_studio.compare_source import load_secondary_dataset

    (tmp_path / "t1.png").write_bytes(b"")
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1"],
            "trial_id": ["t1"],
            "text_id": ["t1"],
            "x": [1.0],
            "y": [1.0],
            "duration_ms": [200.0],
        }
    )
    session["_datasets"] = {"B": {"words": None, "fixations": fixations}}
    app.set_dataset_stimulus_images("B", str(tmp_path), "{trial_id}.png")
    source = load_secondary_dataset("B")
    assert source.fixations["image_path"].tolist() == [
        str((tmp_path / "t1.png").resolve())
    ]
