"""An EyeLink study folder saved as a dataset the app opens (`api.add_eyelink_dataset`).

The study's TRIAL_VARs ride along as the dataset's trial metadata table, stored
where the app keeps a table attached on the 🗂️ Data page, so its trial filters
offer them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import scanpath_studio as sps_root
import scanpath_studio.api as sps
from scanpath_studio import eyelink, metadata, persistence
from scanpath_studio.constants import DATASET_DESCRIPTIONS_KEY
from scanpath_studio.experimental_setup import SetupSnapshot
from tests.conftest import APP_SCRIPT
from tests.eyelink_fixtures import write_experiment


@pytest.fixture(autouse=True)
def _experimental(monkeypatch):
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")


@pytest.fixture
def cache_dir(tmp_path, monkeypatch) -> Path:
    """A private cache folder, with saving on: never the user's own."""
    root = tmp_path / "cache"
    monkeypatch.setenv(persistence.STATE_DIR_ENV_VAR, str(root))
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "1")
    return root


def _study(root: Path, **options) -> Path:
    write_experiment(root, **options)
    study_dir = root / "study"
    report = eyelink.import_eyelink(root / "exp", study_dir, workers=1)
    assert report.imported == ["p01"] and report.failed == {}
    return study_dir


@pytest.fixture
def study(tmp_path) -> Path:
    return _study(tmp_path)


def _restored(root: Path) -> dict:
    """A fresh app session's view of the cache, as `restore_state` builds it."""
    session: dict = {}
    assert persistence.restore_state(session, root)
    return session


def _screens(frame: pd.DataFrame) -> set:
    keys = ["participant_id", "trial_id", "screen_id"]
    return set(frame[keys].astype(str).itertuples(index=False, name=None))


def test_add_eyelink_dataset_round_trip(cache_dir, study):
    name = sps.add_eyelink_dataset("Pilot EDF", study)
    assert name == "Pilot EDF"

    data = eyelink.load_eyelink(study)
    with_words = _screens(data.words)
    expected = data.fixations[
        [key in with_words for key in _screens_rows(data.fixations)]
    ]
    left_out = len(data.fixations) - len(expected)
    # The fixture's trial 1 has a fixation on a screen without words.
    assert left_out > 0

    session = _restored(cache_dir)
    entry = session["_datasets"]["Pilot EDF"]
    fixations = entry["fixations"]
    assert len(fixations) == len(expected)
    assert set(fixations["screen_id"].astype(str)) == set(
        expected["screen_id"].astype(str)
    )
    paths = fixations["image_path"].dropna()
    assert len(paths) and all(Path(p).is_absolute() for p in paths)
    assert all(Path(p).is_file() for p in paths)
    assert set(entry["words"]["image_path"].dropna()) == set(paths)
    assert SetupSnapshot.from_dict(entry["setup"]).canvas == (1280, 1024)
    description = session[DATASET_DESCRIPTIONS_KEY]["Pilot EDF"]
    assert description.startswith(f"EyeLink import of 1 session from {study}")
    assert f"{left_out} fixation" in description
    assert session["data_source_choice"] == "Pilot EDF"


def _screens_rows(frame: pd.DataFrame):
    keys = ["participant_id", "trial_id", "screen_id"]
    return frame[keys].astype(str).itertuples(index=False, name=None)


def test_a_study_without_words_loads_its_fixations_alone(cache_dir, tmp_path):
    study_dir = _study(tmp_path, with_session_files=False)
    data = eyelink.load_eyelink(study_dir)
    assert data.words.empty and len(data.fixations)

    sps.add_eyelink_dataset("No words", study_dir)
    entry = _restored(cache_dir)["_datasets"]["No words"]
    assert entry["words"].empty
    assert len(entry["fixations"]) == len(data.fixations)


def test_the_trial_variables_are_stored_as_its_trial_metadata(cache_dir, study):
    sps.add_eyelink_dataset("Pilot EDF", study, select=False)
    session = _restored(cache_dir)
    tables = session[metadata.DATASET_STORE_KEY]["Pilot EDF"]
    restored = metadata.trial_from_payload(tables["trial"])
    assert "condition" in restored.names
    assert set(restored.frame["condition"]) == {"Adv", "Ele"}


def test_add_dataset_trial_metadata_replace_keeps_it(cache_dir, study):
    data = eyelink.load_eyelink(study)
    words = data.words[data.words["screen_id"] == "screen_1"]
    fixations = data.fixations[data.fixations["screen_id"] == "screen_1"]
    sps.add_dataset(
        "With trials",
        words,
        fixations,
        _trial_metadata=data.trial_metadata,
        keep_columns=["image_path"],
    )

    def stored_conditions() -> set:
        tables = _restored(cache_dir)[metadata.DATASET_STORE_KEY]["With trials"]
        return set(metadata.trial_from_payload(tables["trial"]).frame["condition"])

    assert stored_conditions() == {"Adv", "Ele"}
    # Replacing the tables alone keeps the stored trial table.
    sps.add_dataset("With trials", words, fixations, replace=True)
    assert stored_conditions() == {"Adv", "Ele"}
    # A new one replaces it.
    changed = data.trial_metadata.assign(condition="Hard")
    sps.add_dataset(
        "With trials", words, fixations, replace=True, _trial_metadata=changed
    )
    assert stored_conditions() == {"Hard"}


def test_trial_metadata_is_kept_apart_per_dataset(cache_dir, study):
    data = eyelink.load_eyelink(study)
    words = data.words[data.words["screen_id"] == "screen_1"]
    fixations = data.fixations[data.fixations["screen_id"] == "screen_1"]
    sps.add_dataset("First", words, fixations, _trial_metadata=data.trial_metadata)
    sps.add_dataset(
        "Second",
        words,
        fixations,
        _trial_metadata=data.trial_metadata.assign(condition="Hard"),
    )
    store = _restored(cache_dir)[metadata.DATASET_STORE_KEY]
    first = metadata.trial_from_payload(store["First"]["trial"]).frame
    second = metadata.trial_from_payload(store["Second"]["trial"]).frame
    assert set(first["condition"]) == {"Adv", "Ele"}
    assert set(second["condition"]) == {"Hard"}


def test_the_raw_gaze_participants_must_have_raw_gaze(cache_dir, study):
    with pytest.raises(ValueError, match="raw gaze"):
        sps.add_eyelink_dataset("Gaze", study, raw_gaze_participants=["p01"])


def test_gate_off_refuses(cache_dir, study, monkeypatch):
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL", raising=False)
    for call in (
        lambda: sps.add_eyelink_dataset("Off", study),
        lambda: sps.load_eyelink(study),
        lambda: sps.import_eyelink(study, study.parent / "other"),
    ):
        with pytest.raises(ValueError, match="SCANPATH_EXPERIMENTAL"):
            call()
    assert not (cache_dir / "manifest.json").exists()


def test_the_entries_resolve_from_the_package_but_are_not_advertised():
    for name in ("import_eyelink", "load_eyelink", "add_eyelink_dataset"):
        assert callable(getattr(sps_root, name))
        assert name not in sps_root.__all__


@pytest.mark.timeout(400)
def test_trial_metadata_restored_in_app(cache_dir, study):
    """End to end: a fresh app session opens on the study and its trial
    filters offer the TRIAL_VAR ``condition``."""
    from streamlit.testing.v1 import AppTest

    from scanpath_studio.controls import trial_metadata_filter_key

    sps.add_eyelink_dataset("Pilot EDF", study)
    at = AppTest.from_file(APP_SCRIPT)
    at.run(timeout=180)
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["data_source_choice"] == "Pilot EDF"
    attached = at.session_state[metadata.TRIAL_SESSION_KEY]
    assert "condition" in attached.names
    key = trial_metadata_filter_key("condition")
    widgets = [
        w
        for kind in ("multiselect", "selectbox", "pills", "segmented_control")
        for w in getattr(at, kind, [])
        if getattr(w, "key", None) == key
    ]
    assert widgets, f"no trial filter widget {key!r}"
    assert set(widgets[0].options) >= {"Adv", "Ele"}


def test_replace_with_a_study_without_trial_variables_drops_the_table(
    cache_dir, tmp_path
):
    study = _study(tmp_path / "with")
    sps.add_eyelink_dataset("Pilot EDF", study, select=False)
    assert "trial" in _restored(cache_dir)[metadata.DATASET_STORE_KEY]["Pilot EDF"]
    # The same study read again from recordings that log no TRIAL_VAR.
    asc = write_experiment(tmp_path / "without")
    lines = asc.read_text(encoding="utf-8").splitlines()
    asc.write_text(
        "\n".join(line for line in lines if "TRIAL_VAR" not in line) + "\n",
        encoding="utf-8",
    )
    bare = tmp_path / "without" / "study"
    eyelink.import_eyelink(asc, bare, workers=1)
    sps.add_eyelink_dataset("Pilot EDF", bare, select=False, replace=True)
    store = _restored(cache_dir).get(metadata.DATASET_STORE_KEY) or {}
    assert "trial" not in (store.get("Pilot EDF") or {})


def test_an_unreadable_metadata_file_says_what_to_do(cache_dir, study):
    sps.add_eyelink_dataset("Pilot EDF", study, select=False)
    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
    persistence._metadata_path(cache_dir, manifest["metadata"]).write_text(
        "{not json", encoding="utf-8"
    )
    with pytest.raises(ValueError) as saving:
        sps.add_eyelink_dataset("Pilot EDF", study, replace=True)
    assert "nothing was saved. Open the app and attach the table" in str(saving.value)
    with pytest.raises(ValueError) as removing:
        sps.remove_dataset("Pilot EDF")
    assert "nothing was removed. Open the app and remove the dataset" in str(
        removing.value
    )


def test_trials_without_fixations_are_left_out_of_the_trial_table(cache_dir, tmp_path):
    """Every screen has both words and fixations, so none is left out, yet a
    reading with no fixations at all is still not offered as a trial."""
    asc = write_experiment(tmp_path)
    text = asc.read_text(encoding="utf-8")
    # Trial 1's question screen loses its one fixation: no screen lacks words.
    text = text.replace("EFIX\tR\t1720\t1919\t200\t500.0\t600.0\t980\n", "")
    text += (
        "MSG\t30000\tTRIALID 9\n"
        "MSG\t30010\t!V TRIAL_VAR condition Hard\n"
        "MSG\t30020\tTRIAL_RESULT 0\n"
    )
    asc.write_text(text, encoding="utf-8")
    study_dir = tmp_path / "study"
    eyelink.import_eyelink(tmp_path / "exp", study_dir, workers=1)
    assert "9" in set(eyelink.load_eyelink(study_dir).trial_metadata["trial_id"])
    sps.add_eyelink_dataset("Readings", study_dir, select=False)
    session = _restored(cache_dir)
    tables = session[metadata.DATASET_STORE_KEY]["Readings"]
    stored = metadata.trial_from_payload(tables["trial"]).frame
    assert set(stored["condition"]) == {"Adv", "Ele"}
    assert "left out" not in session[DATASET_DESCRIPTIONS_KEY]["Readings"]
