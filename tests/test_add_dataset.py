"""A dataset added from a script (`api.add_dataset`, `scanpath-studio add`).

It is written where a local app keeps the datasets added with ➕ Add dataset,
so the next app session restores it like one of those: same tables, same
mapping, the setup it was given, opened on it unless told otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import scanpath_studio.api as sps
from scanpath_studio import cli, persistence
from scanpath_studio.constants import (
    DATASET_ALIASES_KEY,
    DATASET_DESCRIPTIONS_KEY,
    RESERVED_SOURCE_NAMES,
)
from scanpath_studio.data import read_sample_raw_gaze, read_sample_tables
from scanpath_studio.dataset_identity import DATASET_IDS_KEY
from scanpath_studio.experimental_setup import Provenance, SetupSnapshot
from tests.conftest import APP_SCRIPT


@pytest.fixture
def cache_dir(tmp_path, monkeypatch) -> Path:
    """A private cache folder, with saving on: never the user's own."""
    root = tmp_path / "cache"
    monkeypatch.setenv(persistence.STATE_DIR_ENV_VAR, str(root))
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "1")
    return root


@pytest.fixture(scope="module")
def sample():
    words, fixations = read_sample_tables()
    return words, fixations


def _manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _restored(root: Path) -> dict:
    """A fresh app session's view of the cache, as `restore_state` builds it."""
    session: dict = {}
    assert persistence.restore_state(session, root)
    return session


def _display_names(session: dict) -> dict[str, str]:
    aliases = session.get(DATASET_ALIASES_KEY) or {}
    return {aliases.get(token, token): token for token in session["_datasets"]}


def test_an_added_dataset_restores_as_the_app_loads_it(cache_dir, sample):
    words, fixations = sample
    name = sps.add_dataset(
        "Pilot 3",
        words,
        fixations,
        raw_gaze=read_sample_raw_gaze(),
        canvas_size=(2560, 1440),
        description="Two readers, two articles.",
    )
    assert name == "Pilot 3"

    session = _restored(cache_dir)
    token = _display_names(session)["Pilot 3"]
    entry = session["_datasets"][token]
    expected_words, expected_fixations = sps.load_scanpath_data(
        words, fixations, names="canonical"
    )
    pd.testing.assert_frame_equal(
        entry["words"].reset_index(drop=True),
        expected_words.reset_index(drop=True),
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        entry["fixations"].reset_index(drop=True),
        expected_fixations.reset_index(drop=True),
        check_dtype=False,
    )
    assert len(entry["raw_gaze"]) == len(read_sample_raw_gaze())
    # The mapping the app shows and ✏️ Edit dataset starts from.
    assert entry["schemas"]["words"]["trial"]
    assert entry["schemas"]["fixations"]["duration"]
    assert entry["source_recipe"]["schemas"] == entry["schemas"]
    assert set(entry["column_names"]) == {"words", "fixations", "raw_gaze"}
    setup = SetupSnapshot.from_dict(entry["setup"])
    assert setup.canvas == (2560, 1440)
    assert setup.screen_provenance is Provenance.MEASURED
    # Opened on next time, described, and given a share ID like an upload.
    assert session["data_source_choice"] == token
    assert session[DATASET_DESCRIPTIONS_KEY][token] == "Two readers, two articles."
    assert session[DATASET_IDS_KEY][token]


def test_without_a_screen_it_is_estimated_from_the_data(cache_dir, sample):
    sps.add_dataset("Estimated", *sample)
    entry = _manifest(cache_dir)["datasets"]["Estimated"]["metadata"]
    setup = SetupSnapshot.from_dict(entry["setup"])
    assert setup.screen_provenance is Provenance.ESTIMATED
    assert setup.canvas_width > 0 and setup.canvas_height > 0


def test_a_raw_gaze_only_dataset_is_added(cache_dir):
    sps.add_dataset("Gaze only", raw_gaze=read_sample_raw_gaze(), select=False)
    session = _restored(cache_dir)
    entry = session["_datasets"]["Gaze only"]
    assert entry["words"].empty and entry["fixations"].empty
    assert not entry["raw_gaze"].empty
    assert "data_source_choice" not in session


def test_the_other_saved_work_is_left_as_it_was(cache_dir, sample):
    words, fixations = sample
    sps.add_dataset("First", words, fixations)
    before = _manifest(cache_dir)
    sps.add_dataset("Second", fixations=fixations, select=False)
    after = _manifest(cache_dir)
    assert after["datasets"]["First"] == before["datasets"]["First"]
    assert after["session"]["data_source_choice"] == "First"
    assert after["annotations"] == before["annotations"]


def test_a_saved_name_is_refused_unless_replaced(cache_dir, sample):
    words, fixations = sample
    sps.add_dataset("Pilot", words, fixations, description="first")
    share_id = _manifest(cache_dir)["session"][DATASET_IDS_KEY]["Pilot"]
    old_files = {
        cache_dir / relative
        for relative in _manifest(cache_dir)["datasets"]["Pilot"]["frames"].values()
    }
    with pytest.raises(sps.StoredDatasetExistsError, match="already saved"):
        sps.add_dataset("pilot", fixations=fixations)

    sps.add_dataset("Pilot", fixations=fixations, replace=True)
    manifest = _manifest(cache_dir)
    assert list(manifest["datasets"]) == ["Pilot"]
    assert manifest["datasets"]["Pilot"]["rows"]["words"] == 0
    # The same dataset, new tables: its share links and description stay.
    assert manifest["session"][DATASET_IDS_KEY]["Pilot"] == share_id
    assert manifest["session"][DATASET_DESCRIPTIONS_KEY]["Pilot"] == "first"
    assert not any(path.exists() for path in old_files)


def test_replacing_keeps_the_datasets_annotations(cache_dir, sample):
    words, fixations = sample
    sps.add_dataset("Annotated", words, fixations)
    session = _restored(cache_dir)
    reading = session["_datasets"]["Annotated"]["fixations"].iloc[0]
    record = {
        "participant_id": str(reading["participant_id"]),
        "trial_id": str(reading["trial_id"]),
        "favorite": True,
        "tags": ["check"],
        "note": "drift?",
    }
    manifest = _manifest(cache_dir)
    manifest["annotations"] = {"datasets": {"Annotated": [record]}}
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    sps.add_dataset("Annotated", words, fixations, replace=True)
    assert _manifest(cache_dir)["annotations"] == {"datasets": {"Annotated": [record]}}


@pytest.mark.parametrize("name", ["", "   ", "x" * 81, *sorted(RESERVED_SOURCE_NAMES)])
def test_a_name_the_list_cannot_take_is_refused(cache_dir, sample, name):
    with pytest.raises(ValueError):
        sps.add_dataset(name, *sample)
    assert not (cache_dir / "manifest.json").exists()


def test_a_reserved_name_is_matched_ignoring_case(cache_dir, sample):
    with pytest.raises(ValueError, match="built-in"):
        sps.add_dataset("bundled DEMO", *sample)


def test_saved_work_that_does_not_read_is_never_written_over(cache_dir, sample):
    cache_dir.mkdir(parents=True)
    (cache_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="can't be read"):
        sps.add_dataset("Pilot", *sample)
    assert (cache_dir / "manifest.json").read_text(encoding="utf-8") == "{not json"
    assert not any(cache_dir.glob("datasets/*"))


def test_saved_work_from_another_version_is_never_written_over(cache_dir, sample):
    cache_dir.mkdir(parents=True)
    other = {"schema": persistence.SCHEMA_VERSION + 1, "datasets": {}}
    (cache_dir / "manifest.json").write_text(json.dumps(other), encoding="utf-8")
    with pytest.raises(ValueError, match="another version"):
        sps.add_dataset("Pilot", *sample)
    assert _manifest(cache_dir) == other


def test_a_table_that_does_not_load_saves_nothing(cache_dir):
    with pytest.raises(ValueError):
        sps.add_dataset("Broken", fixations=pd.DataFrame({"a": [1]}))
    assert not (cache_dir / "manifest.json").exists()


def test_saving_turned_off_is_an_error(cache_dir, sample, monkeypatch):
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "0")
    with pytest.raises(RuntimeError, match="turned off"):
        sps.add_dataset("Pilot", *sample)
    assert not cache_dir.exists()


def test_an_open_tab_that_saved_before_sees_a_conflict(cache_dir, sample):
    """A tab must not save over a dataset a script added under it: its next
    save is the same conflict two tabs changing the saved work get."""
    words, fixations = sample
    tab: dict = {}
    persistence.restore_state(tab, cache_dir)
    tab["_datasets"] = {"In the tab": {"words": words, "fixations": fixations}}
    assert persistence.save_state(tab, cache_dir)

    sps.add_dataset("From a script", fixations=fixations)
    tab["data_source_choice"] = "In the tab"
    tab[DATASET_DESCRIPTIONS_KEY] = {"In the tab": "edited"}
    with pytest.raises(persistence.RecoveryConflictError):
        persistence.save_state(tab, cache_dir)
    assert set(_manifest(cache_dir)["datasets"]) == {"In the tab", "From a script"}


def test_a_name_other_saved_work_still_holds_gets_its_own_store_key(cache_dir, sample):
    """A name an annotation store still holds (a removed dataset's) is shown,
    but stored under a fresh key, so the new dataset inherits nothing."""
    cache_dir.mkdir(parents=True)
    manifest = {
        "schema": persistence.SCHEMA_VERSION,
        "datasets": {},
        "session": {},
        "annotations": {"datasets": {"Pilot": []}},
    }
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    sps.add_dataset("Pilot", *sample)
    session = _restored(cache_dir)
    token = _display_names(session)["Pilot"]
    assert token != "Pilot"
    assert session[DATASET_ALIASES_KEY][token] == "Pilot"


def test_reserved_names_match_the_apps_registry():
    from scanpath_studio.app import reserved_source_names

    assert RESERVED_SOURCE_NAMES == reserved_source_names()


def test_the_trial_conditions_are_offered_as_filters(cache_dir, sample):
    """As ➕ Add dataset keeps them: the registry's trial-level fields the
    tables carry, so the app's trial filters offer them."""
    sps.add_dataset("Conditions", *sample)
    fields = _restored(cache_dir)["_datasets"]["Conditions"]["filter_fields"]
    for condition in ("difficulty_level", "question_preview", "is_correct"):
        assert condition in fields
    assert len(fields) == len(set(fields))


def test_share_code_names_the_files_columns_for_a_prepared_frame(cache_dir, sample):
    """A table given as a frame this API loaded is mapped under the internal
    names; the recipe Share → Code writes still names the files' own."""
    words, fixations = sps.load_scanpath_data(*sample)
    sps.add_dataset("Prepared", words, fixations)
    entry = _restored(cache_dir)["_datasets"]["Prepared"]
    recipe = entry["source_recipe"]
    assert recipe["schemas"]["fixations"]["duration"] == "CURRENT_FIX_DURATION"
    assert recipe["schemas"]["fixations"]["x"] == "CURRENT_FIX_X"
    assert not recipe.get("unresolved")


def test_a_trial_parts_manifest_is_named_as_a_step(cache_dir, sample, monkeypatch):
    seen = {}

    def load(*args, **kwargs):
        seen["manifest"] = kwargs.get("trial_parts_manifest")
        kwargs["trial_parts_manifest"] = None
        return original(*args, **kwargs)

    original = sps.load_scanpath_data
    monkeypatch.setattr(sps, "load_scanpath_data", load)
    sps.add_dataset("Parts", *sample, trial_parts_manifest={"stand": "in"})
    assert seen["manifest"] == {"stand": "in"}
    recipe = _manifest(cache_dir)["datasets"]["Parts"]["metadata"]["source_recipe"]
    assert recipe["steps"] == ["trial_parts_manifest"]


def test_replacing_keeps_the_setup_unless_a_new_one_is_given(cache_dir, sample):
    words, fixations = sample
    measured = SetupSnapshot(
        canvas_width=1920,
        canvas_height=1080,
        monitor_width_mm=530.0,
        screen_provenance=Provenance.MEASURED,
        geometry_provenance=Provenance.MEASURED,
    )
    sps.add_dataset("Pilot", words, fixations, setup=measured)
    sps.add_dataset("Pilot", fixations=fixations, replace=True)
    kept = _manifest(cache_dir)["datasets"]["Pilot"]["metadata"]["setup"]
    assert SetupSnapshot.from_dict(kept) == measured

    sps.add_dataset("Pilot", fixations=fixations, replace=True, canvas_size=(800, 600))
    new = _manifest(cache_dir)["datasets"]["Pilot"]["metadata"]["setup"]
    assert SetupSnapshot.from_dict(new).canvas == (800, 600)


def test_a_name_a_renamed_dataset_shows_is_refused(cache_dir, sample):
    cache_dir.mkdir(parents=True)
    manifest = {
        "schema": persistence.SCHEMA_VERSION,
        "datasets": {},
        "session": {DATASET_ALIASES_KEY: {"Bundled demo": "Pilot"}},
        "annotations": {"datasets": {}},
    }
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="renamed"):
        sps.add_dataset("pilot", *sample)


def _attach_metadata(root: Path, tables: dict) -> None:
    """Store metadata tables beside the manifest, as the app's save does."""
    name = "metadata-0123456789abcdef.json"
    (root / name).write_text(json.dumps({"datasets": tables}), encoding="utf-8")
    manifest = _manifest(root)
    manifest["metadata"] = {
        "file": name,
        "tables": [f"{d}:{grain}" for d, grains in tables.items() for grain in grains],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class TestRemove:
    def test_everything_the_app_keeps_for_it_goes(self, cache_dir, sample):
        """What the app's own Remove takes: no key of the saved work still names
        the dataset, and the next session opens on the default."""
        words, fixations = sample
        sps.add_dataset("Zebra pilot", words, fixations, description="To go")
        sps.add_dataset("Keeper", fixations=fixations, select=False)
        manifest = _manifest(cache_dir)
        manifest["annotations"] = {
            "datasets": {"Zebra pilot": [{"participant_id": "p", "trial_id": "t"}]}
        }
        manifest["session"]["single_trial_id"] = "t"
        manifest["session"]["cmp_dataset"] = "Zebra pilot"
        manifest["dataset_counts"] = {"Zebra pilot": {"words": 1}}
        (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        _attach_metadata(
            cache_dir,
            {"Zebra pilot": {"participant": {}}, "Keeper": {"participant": {}}},
        )
        files = {
            cache_dir / relative
            for relative in manifest["datasets"]["Zebra pilot"]["frames"].values()
        }

        assert sps.remove_dataset("zebra PILOT") is True

        after = _manifest(cache_dir)
        assert "Zebra pilot" not in json.dumps(after)
        assert list(after["datasets"]) == ["Keeper"]
        assert after["metadata"]["tables"] == ["Keeper:participant"]
        sidecar = json.loads((cache_dir / after["metadata"]["file"]).read_text())
        assert list(sidecar["datasets"]) == ["Keeper"]
        assert not (cache_dir / "metadata-0123456789abcdef.json").exists()
        assert not any(path.exists() for path in files)
        session = _restored(cache_dir)
        assert "data_source_choice" not in session
        assert list(session["_datasets"]) == ["Keeper"]

    def test_the_other_datasets_are_left_as_they_were(self, cache_dir, sample):
        words, fixations = sample
        sps.add_dataset("One", words, fixations)
        sps.add_dataset("Two", fixations=fixations)
        before = _manifest(cache_dir)
        sps.remove_dataset("Two")
        after = _manifest(cache_dir)
        assert after["datasets"] == {"One": before["datasets"]["One"]}
        # "One" was not the dataset the session had open, so the choice of
        # "Two" goes and nothing else.
        assert "data_source_choice" not in after["session"]
        assert after["session"][DATASET_IDS_KEY] == {
            "One": before["session"][DATASET_IDS_KEY]["One"]
        }

    def test_an_unknown_name_raises_unless_missing_is_ok(self, cache_dir, sample):
        with pytest.raises(sps.StoredDatasetNotFoundError):
            sps.remove_dataset("Nothing here")
        assert sps.remove_dataset("Nothing here", missing_ok=True) is False
        sps.add_dataset("Pilot", *sample)
        with pytest.raises(LookupError, match="Nothing here"):
            sps.remove_dataset("Nothing here")
        assert sps.remove_dataset("Nothing here", missing_ok=True) is False

    def test_a_built_in_dataset_is_not_removed(self, cache_dir, sample):
        sps.add_dataset("Pilot", *sample)
        with pytest.raises(sps.StoredDatasetNotFoundError):
            sps.remove_dataset("Bundled demo")

    def test_a_renamed_upload_is_removed_by_its_shown_name(self, cache_dir, sample):
        cache_dir.mkdir(parents=True)
        manifest = {
            "schema": persistence.SCHEMA_VERSION,
            "datasets": {},
            "session": {},
            "annotations": {"datasets": {"Pilot": []}},
        }
        (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        sps.add_dataset("Pilot", *sample)
        token = next(iter(_manifest(cache_dir)["datasets"]))
        assert token != "Pilot"
        sps.remove_dataset("Pilot")
        after = _manifest(cache_dir)
        assert after["datasets"] == {}
        assert token not in json.dumps(after["session"])

    def test_unreadable_metadata_tables_remove_nothing(self, cache_dir, sample):
        sps.add_dataset("Pilot", *sample)
        _attach_metadata(cache_dir, {"Pilot": {"participant": {}}})
        before = _manifest(cache_dir)
        (cache_dir / before["metadata"]["file"]).write_text("{bad", encoding="utf-8")
        with pytest.raises(ValueError, match="metadata"):
            sps.remove_dataset("Pilot")
        assert _manifest(cache_dir) == before

    def test_saving_turned_off_is_an_error(self, cache_dir, monkeypatch):
        monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "0")
        with pytest.raises(RuntimeError, match="turned off"):
            sps.remove_dataset("Pilot")


class TestCli:
    @pytest.fixture
    def files(self, tmp_path, sample):
        words, fixations = sample
        words_path, fixations_path = tmp_path / "words.csv", tmp_path / "fix.csv"
        words.to_csv(words_path, index=False)
        fixations.to_csv(fixations_path, index=False)
        return str(words_path), str(fixations_path)

    def test_add_saves_the_tables(self, cache_dir, files, capsys):
        words, fixations = files
        cli.main(
            [
                "add",
                "Pilot 3",
                "--words",
                words,
                "--fixations",
                fixations,
                "--canvas",
                "1920x1080",
                "--description",
                "From the CLI.",
            ]
        )
        out = capsys.readouterr().out
        assert "Added 'Pilot 3'." in out
        assert "scanpath-studio" in out
        entry = _manifest(cache_dir)["datasets"]["Pilot 3"]
        assert entry["rows"]["words"] > 0 and entry["rows"]["fixations"] > 0
        assert SetupSnapshot.from_dict(entry["metadata"]["setup"]).canvas == (
            1920,
            1080,
        )

    def test_a_saved_name_names_the_flag_that_replaces_it(self, cache_dir, files):
        words, fixations = files
        cli.main(["add", "Pilot", "--fixations", fixations])
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["add", "Pilot", "--fixations", fixations])
        message = str(exit_info.value)
        assert "--replace" in message and "replace=True" not in message
        cli.main(["add", "Pilot", "--words", words, "--replace", "--no-select"])
        manifest = _manifest(cache_dir)
        assert manifest["datasets"]["Pilot"]["rows"]["fixations"] == 0

    def test_nothing_to_add_is_an_error(self, cache_dir):
        with pytest.raises(SystemExit, match="Nothing to add"):
            cli.main(["add", "Empty"])

    def test_replace_on_a_new_name_says_added(self, cache_dir, files, capsys):
        _, fixations = files
        cli.main(["add", "Fresh", "--fixations", fixations, "--replace"])
        assert "Added 'Fresh'." in capsys.readouterr().out

    def test_remove(self, cache_dir, files, capsys):
        _, fixations = files
        cli.main(["add", "Pilot", "--fixations", fixations])
        cli.main(["remove", "pilot"])
        assert "Removed 'Pilot'." in capsys.readouterr().out
        assert _manifest(cache_dir)["datasets"] == {}
        with pytest.raises(SystemExit, match="No dataset named 'Pilot'"):
            cli.main(["remove", "Pilot"])
        cli.main(["remove", "Pilot", "--missing-ok"])
        assert "nothing removed" in capsys.readouterr().out


@pytest.mark.timeout(300)
def test_the_app_opens_on_a_dataset_a_script_added(cache_dir, sample):
    """End to end: added from a script, then a fresh app session — what
    `scanpath-studio` after `add` is — restores it, opens on it and draws it."""
    from streamlit.testing.v1 import AppTest

    words, fixations = sample
    sps.add_dataset("From a script", words, fixations, canvas_size=(2560, 1440))

    at = AppTest.from_file(APP_SCRIPT)
    at.run(timeout=180)
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["data_source_choice"] == "From a script"
    stored = at.session_state["_datasets"]["From a script"]
    assert len(stored["fixations"]) == len(sps.load_scanpath_data(words, fixations)[1])
    assert not at.error, [e.value for e in at.error]


@pytest.mark.timeout(400)
def test_a_dataset_the_app_used_is_removed_without_a_trace(cache_dir, sample):
    """End to end: the app opens a dataset a script added and saves what it
    keeps about it; after `remove_dataset` no saved key names it, and the next
    session opens on the default dataset without an error."""
    from streamlit.testing.v1 import AppTest

    words, fixations = sample
    sps.add_dataset("Zebra pilot", words, fixations)
    first = AppTest.from_file(APP_SCRIPT)
    first.run(timeout=180)
    assert first.session_state["data_source_choice"] == "Zebra pilot"
    first.session_state["global_show_saccades"] = False
    first.run(timeout=180)
    assert not first.exception, [e.value for e in first.exception]

    sps.remove_dataset("Zebra pilot")
    saved = (cache_dir / "manifest.json").read_text(encoding="utf-8")
    assert "Zebra pilot" not in saved

    second = AppTest.from_file(APP_SCRIPT)
    second.run(timeout=180)
    assert not second.exception, [e.value for e in second.exception]
    assert second.session_state["data_source_choice"] != "Zebra pilot"
    stored = (
        second.session_state["_datasets"] if "_datasets" in second.session_state else {}
    )
    assert "Zebra pilot" not in stored
