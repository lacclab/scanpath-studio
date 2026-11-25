"""A saved dataset's annotations read and written from a script
(`api.read_annotations` / `write_annotations`, `scanpath-studio annotations`).

They live where the app keeps them — the recovery cache's manifest — so a
reviewer sees a script's tags in the app, and a script reads back what the
reviewers marked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import scanpath_studio.annotations as ann
import scanpath_studio.api as sps
from scanpath_studio import cli, persistence
from scanpath_studio.constants import DEMO_CHOICE
from scanpath_studio.data import read_sample_tables
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
    """The demo's paragraph screens, as a dataset of one screen per reading.

    Multi-screen datasets have their own tests below."""
    return tuple(
        frame[frame["part"].eq("Paragraph")].drop(columns=["part", "screen_index"])
        for frame in read_sample_tables()
    )


@pytest.fixture
def pilot(cache_dir, sample) -> list[tuple[str, str]]:
    """A saved dataset, *Pilot*; its readings as the trial picker lists them."""
    sps.add_dataset("Pilot", *sample)
    trials = sps.list_trials(*sps.load_scanpath_data(*sample))
    return sorted(zip(trials["participant_id"], trials["unique_trial_id"]))


def _manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _rows(frame: pd.DataFrame) -> list[dict]:
    """The table's rows, a blank cell as ``None``."""
    return frame.astype(object).where(frame.notna(), None).to_dict("records")


def test_a_dataset_without_annotations_reads_as_an_empty_table(pilot):
    frame = sps.read_annotations("pilot")
    assert frame.empty
    assert list(frame.columns) == [
        "participant_id",
        "trial_id",
        "favorite",
        "tags",
        "note",
    ]


def test_merging_joins_tags_and_a_given_favorite_or_note_wins(pilot):
    (p, t), (p2, t2) = pilot[0], pilot[1]
    sps.write_annotations(
        "Pilot",
        [
            {"participant_id": p, "trial_id": t, "star": True, "tags": ["Review"]},
            {"participant_id": p2, "trial_id": t2, "note": "Keep"},
        ],
    )
    result = sps.write_annotations(
        "Pilot",
        pd.DataFrame(
            {
                "participant_id": [p, p, p2],
                "trial_id": [t, t, t2],
                # Two rows on one reading add their tags together.
                "tags": ["Few fixations", ["Long"], None],
                "note": [None, "Short", None],
                # A blank favorite leaves the reading's own.
                "favorite": [None, None, False],
            }
        ),
    )
    assert (result.dataset, result.written, result.annotated) == ("Pilot", 2, 2)
    assert result.unknown.empty
    assert _rows(sps.read_annotations("Pilot")) == [
        {
            "participant_id": p,
            "trial_id": t,
            "favorite": True,
            "tags": ["Few fixations", "Long", "Review"],
            "note": "Short",
        },
        {
            "participant_id": p2,
            "trial_id": t2,
            "favorite": False,
            "tags": [],
            "note": "Keep",
        },
    ]


def test_replace_makes_the_annotations_exactly_the_ones_given(pilot):
    (p, t), (p2, t2) = pilot[0], pilot[1]
    sps.write_annotations("Pilot", [{"participant_id": p, "trial_id": t, "star": True}])
    result = sps.write_annotations(
        "Pilot",
        pd.DataFrame({"participant_id": [p2], "trial_id": [t2], "tags": ["A; B"]}),
        mode="replace",
    )
    assert result.annotated == 1
    assert _rows(sps.read_annotations("Pilot")) == [
        {
            "participant_id": p2,
            "trial_id": t2,
            "favorite": False,
            "tags": ["A", "B"],
            "note": "",
        }
    ]
    # Replaced by an entry with nothing on it: none left, and none stored.
    sps.write_annotations(
        "Pilot", [{"participant_id": p2, "trial_id": t2, "star": False}], mode="replace"
    )
    assert sps.read_annotations("Pilot").empty
    assert (
        "Pilot"
        not in _manifest(Path(persistence.state_directory()))["annotations"]["datasets"]
    )


@pytest.mark.parametrize(
    "given",
    [[], [{"participant_id": "ghost", "trial_id": "t9", "tags": ["A"]}]],
    ids=["nothing", "another-datasets-readings"],
)
def test_a_replace_that_names_none_of_the_readings_deletes_nothing(pilot, given):
    """An empty file, or one made for another dataset, would otherwise leave
    the dataset with no annotations at all."""
    p, t = pilot[0]
    sps.write_annotations(
        "Pilot", [{"participant_id": p, "trial_id": t, "note": "Keep"}]
    )
    with pytest.raises(ValueError, match="not replaced"):
        sps.write_annotations("Pilot", given, mode="replace")
    assert _rows(sps.read_annotations("Pilot"))[0]["note"] == "Keep"


def test_two_file_records_on_one_reading_must_agree(pilot):
    """As the app's Import requires of an annotations file."""
    p, t = pilot[0]
    with pytest.raises(ValueError, match="disagree"):
        sps.write_annotations(
            "Pilot",
            [
                {"participant_id": p, "trial_id": t, "tags": ["A"]},
                {"participant_id": p, "trial_id": t, "tags": ["B"]},
            ],
        )


def test_text_ids_are_kept_as_written_and_numbers_as_ids(cache_dir):
    """A text id ending in `.0` is a different id from the one without it, as
    in the app; a number read as a decimal (`3.0`) is the trial `3`."""
    fixations = pd.DataFrame(
        {"participant_id": ["1", "p"], "trial_id": ["3", "t.0"], "x": [1.0, 2.0]}
    )
    persistence.store_dataset(
        {"words": pd.DataFrame(), "fixations": fixations}, "Ids", root=cache_dir
    )
    result = sps.write_annotations(
        "Ids",
        pd.DataFrame(
            {"participant_id": [1.0, "p"], "trial_id": [3.0, "t.0"], "tags": "A"}
        ).astype({"trial_id": object}),
    )
    assert result.unknown.empty, result.unknown
    numbers = pd.DataFrame({"participant_id": [1.0], "trial_id": [3.0], "tags": "B"})
    assert sps.write_annotations("Ids", numbers).unknown.empty


def test_readings_the_dataset_lacks_are_reported_and_left_out(pilot):
    p, t = pilot[0]
    result = sps.write_annotations(
        "Pilot",
        pd.DataFrame(
            {
                "participant_id": [p, "ghost", p],
                "trial_id": [t, "t9", t],
                "screen_id": [None, None, "page 2"],
                "tags": ["Review"] * 3,
            }
        ),
    )
    assert result.written == 1
    assert _rows(result.unknown) == [
        {"participant_id": "ghost", "trial_id": "t9", "screen_id": None},
        {"participant_id": p, "trial_id": t, "screen_id": "page 2"},
    ]
    assert len(sps.read_annotations("Pilot")) == 1


def test_a_frame_under_the_datasets_own_names_is_read(pilot, sample):
    """`load_scanpath_data` names columns as the dataset does — the sample's
    trial id is `unique_trial_id` — and a table built from it still names
    the readings the app lists."""
    _, fixations = sps.load_scanpath_data(*sample)
    first = fixations.groupby(["participant_id", "unique_trial_id"]).size()
    flagged = first.head(2).reset_index()[["participant_id", "unique_trial_id"]]
    flagged["tags"] = "Few fixations"
    result = sps.write_annotations("Pilot", flagged)
    assert result.written == 2 and result.unknown.empty


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (pd.DataFrame({"trial_id": ["t"], "tags": ["x"]}), "participant_id"),
        (pd.DataFrame({"participant_id": ["p"], "trial_id": ["t"]}), "annotates"),
        (
            pd.DataFrame({"participant_id": ["p"], "trial_id": ["t"], "favorite": [3]}),
            "true or false",
        ),
        (
            pd.DataFrame(
                {
                    "participant_id": ["p", "p"],
                    "trial_id": ["t", "t"],
                    "note": ["a", "b"],
                }
            ),
            "another note",
        ),
        ({"schema": 3}, "no annotations list"),
        ([{"participant_id": "p", "trial_id": "t", "star": "yes"}], "true or false"),
    ],
)
def test_annotations_in_no_usable_form_save_nothing(pilot, table, message):
    root = Path(persistence.state_directory())
    before = (root / "manifest.json").read_bytes()
    with pytest.raises(ValueError, match=message):
        sps.write_annotations("Pilot", table)
    assert (root / "manifest.json").read_bytes() == before


def test_the_wrong_kind_of_value_is_a_type_error(pilot):
    with pytest.raises(TypeError):
        sps.write_annotations("Pilot", 3)


def test_an_unknown_mode_is_refused(pilot):
    with pytest.raises(ValueError, match="merge"):
        sps.write_annotations("Pilot", [], mode="append")


def test_a_name_no_saved_dataset_has_is_not_found(pilot):
    with pytest.raises(sps.StoredDatasetNotFoundError, match="Nope"):
        sps.read_annotations("Nope")
    with pytest.raises(sps.StoredDatasetNotFoundError, match="in the app"):
        sps.write_annotations(DEMO_CHOICE, [])


def test_saving_turned_off_is_an_error(pilot, monkeypatch):
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "0")
    with pytest.raises(RuntimeError, match="turned off"):
        sps.write_annotations("Pilot", [])


def test_the_app_files_written_by_a_path_import(pilot, tmp_path):
    """The app's exported `annotations.json` and a CSV both import by path."""
    (p, t), (p2, t2) = pilot[0], pilot[1]
    exported = tmp_path / "annotations.json"
    exported.write_text(
        ann.serialize({(p, t): {"star": True, "tags": ["Review"], "note": "n"}}),
        encoding="utf-8",
    )
    sps.write_annotations("Pilot", exported)
    table = tmp_path / "flags.csv"
    table.write_text(
        f"participant_id,trial_id,favorite,tags,note\n{p2},{t2},yes,A;B,\n",
        encoding="utf-8",
    )
    sps.write_annotations("Pilot", str(table))
    assert _rows(sps.read_annotations("Pilot")) == [
        {
            "participant_id": p,
            "trial_id": t,
            "favorite": True,
            "tags": ["Review"],
            "note": "n",
        },
        {
            "participant_id": p2,
            "trial_id": t2,
            "favorite": True,
            "tags": ["A", "B"],
            "note": "",
        },
    ]


def test_the_other_saved_annotations_are_left_as_they_were(pilot, sample):
    (p, t) = pilot[0]
    sps.add_dataset("Other", *sample, select=False)
    sps.write_annotations("Other", [{"participant_id": p, "trial_id": t, "note": "B"}])
    sps.write_annotations("Pilot", [{"participant_id": p, "trial_id": t, "note": "A"}])
    sps.write_annotations(
        "Pilot", [{"participant_id": p, "trial_id": t, "star": False}], mode="replace"
    )
    assert sps.read_annotations("Pilot").empty
    assert _rows(sps.read_annotations("Other"))[0]["note"] == "B"


def test_screens_are_checked_on_a_multipart_dataset(cache_dir):
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1"],
            "trial_id": ["t1", "t1", "t2"],
            "screen_id": ["s1", "s2", "s1"],
            "x": [1.0, 2.0, 3.0],
            "y": [1.0, 2.0, 3.0],
        }
    )
    persistence.store_dataset(
        {"words": pd.DataFrame(), "fixations": fixations}, "Pages", root=cache_dir
    )
    result = sps.write_annotations(
        "Pages",
        pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "trial_id": ["t1", "t2", "t1"],
                "screen_id": ["s2", "s2", None],
                "tags": ["Page", "Page", "Trial"],
            }
        ),
    )
    assert result.written == 2
    assert _rows(result.unknown) == [
        {"participant_id": "p1", "trial_id": "t2", "screen_id": "s2"}
    ]
    frame = sps.read_annotations("Pages")
    assert list(frame.columns) == list(ann.FRAME_COLUMNS)
    assert _rows(frame[["trial_id", "screen_id"]]) == [
        {"trial_id": "t1", "screen_id": None},
        {"trial_id": "t1", "screen_id": "s2"},
    ]


def test_an_open_tabs_own_edits_are_kept_beside_a_scripts(pilot):
    """A tab that restored the saved work, then edited another reading while a
    script wrote, saves both: annotations merge by reading."""
    root = Path(persistence.state_directory())
    (p, t), (p2, t2) = pilot[0], pilot[1]
    session: dict = {}
    assert persistence.restore_state(session, root)
    persistence.save_state(session, root)
    sps.write_annotations(
        "Pilot", [{"participant_id": p, "trial_id": t, "tags": ["QC"]}]
    )
    ann.activate_dataset(session, "Pilot", adopt=False)
    session[ann.ANNOTATIONS_STATE_KEY] = {
        **session[ann.ANNOTATIONS_STATE_KEY],
        (p2, t2): {"star": True, "tags": [], "note": ""},
    }
    assert persistence.save_state(session, root)
    store = ann.records_to_store(_manifest(root)["annotations"]["datasets"]["Pilot"])
    assert store == {
        (p, t): {"star": False, "tags": ["QC"], "note": ""},
        (p2, t2): {"star": True, "tags": [], "note": ""},
    }


class TestCli:
    def test_export_and_import(self, pilot, tmp_path, capsys):
        p, t = pilot[0]
        table = tmp_path / "flags.csv"
        table.write_text(
            f"participant_id,trial_id,tags,note\n{p},{t},Review; Long,Check\n"
            "ghost,t9,Review,\n",
            encoding="utf-8",
        )
        cli.main(["annotations", "import", "pilot", str(table)])
        out = capsys.readouterr().out
        assert "Saved annotations on 1 reading of 'Pilot'" in out
        assert "1 reading is not in the dataset and was left out" in out
        assert "ghost / t9" in out

        as_json, as_csv = tmp_path / "out.json", tmp_path / "out.csv"
        cli.main(["annotations", "export", "Pilot", "-o", str(as_json)])
        cli.main(["annotations", "export", "Pilot", "-o", str(as_csv)])
        assert "Wrote 1 annotated reading of 'Pilot'" in capsys.readouterr().out
        document = json.loads(as_json.read_text(encoding="utf-8"))
        assert document["dataset"] == "Pilot"
        assert ann.deserialize(as_json.read_text(encoding="utf-8")) == {
            (p, t): {"star": False, "tags": ["Long", "Review"], "note": "Check"}
        }
        assert pd.read_csv(as_csv).to_dict("records") == [
            {
                "participant_id": p,
                "trial_id": t,
                "favorite": False,
                "tags": "Long; Review",
                "note": "Check",
            }
        ]
        # What `export` writes imports back as it was, in either format.
        cli.main(["annotations", "import", "Pilot", str(as_csv), "--replace"])
        cli.main(["annotations", "import", "Pilot", str(as_json), "--replace"])
        assert (
            ann.deserialize(as_json.read_text(encoding="utf-8"))
            == (persistence.stored_annotations("Pilot")[1])
        )

    def test_errors_exit_with_the_reason(self, pilot, tmp_path):
        with pytest.raises(SystemExit, match="No dataset named 'Nope'"):
            cli.main(["annotations", "export", "Nope", "-o", str(tmp_path / "a.csv")])
        with pytest.raises(SystemExit, match=r"\.json or \.csv"):
            cli.main(["annotations", "export", "Pilot", "-o", str(tmp_path / "a.txt")])
        bad = tmp_path / "bad.json"
        bad.write_text('{"schema": 3}', encoding="utf-8")
        with pytest.raises(SystemExit, match="Nothing imported"):
            cli.main(["annotations", "import", "Pilot", str(bad)])


@pytest.mark.timeout(300)
def test_the_app_filters_by_a_tag_a_script_wrote(pilot):
    """End to end: a script tags two readings of the saved dataset; a fresh
    app session offers the tag as a trial filter, and filtering by it leaves
    exactly those readings."""
    from streamlit.testing.v1 import AppTest

    from tests.conftest import picker_trial_id

    participant = pilot[0][0]
    tagged = [t for p, t in pilot if p == participant][:2]
    sps.write_annotations(
        "Pilot",
        pd.DataFrame(
            {
                "participant_id": [participant] * 2,
                "trial_id": tagged,
                "tags": ["Flagged by QC"] * 2,
            }
        ),
    )

    at = AppTest.from_file(APP_SCRIPT)
    at.run(timeout=180)
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["data_source_choice"] == "Pilot"
    tags = at.multiselect(key="filter_req_tags")
    assert "Flagged by QC" in tags.options
    tags.set_value(["Flagged by QC"]).run(timeout=180)
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["_trial_filters"]["required_tags"] == ["Flagged by QC"]
    picker = at.selectbox(key="single_trial_id")
    # The picker marks a tagged trial with 🏷️ after its id.
    shown = sorted(picker_trial_id(o).split()[0] for o in picker.options)
    assert shown == sorted(tagged)


def test_a_concatenated_table_with_repeated_labels_is_read(pilot):
    """`pd.concat` repeats index labels; rows are still read one by one, and
    a missing value inside a list of tags is no tag."""
    (p, t), (p2, t2) = pilot[0], pilot[1]
    first = pd.DataFrame(
        {"participant_id": [p], "trial_id": [t], "tags": [["A", None]]}
    )
    second = pd.DataFrame({"participant_id": [p2], "trial_id": [t2], "tags": ["B"]})
    result = sps.write_annotations("Pilot", pd.concat([first, second]))
    assert result.written == 2
    assert sps.read_annotations("Pilot")["tags"].tolist() == [["A"], ["B"]]


def test_a_record_without_a_star_agrees_with_one_whose_star_is_false(pilot):
    """As the app's file reader reads them, both are not starred."""
    p, t = pilot[0]
    sps.write_annotations(
        "Pilot",
        [
            {"participant_id": p, "trial_id": t, "tags": ["A"]},
            {"participant_id": p, "trial_id": t, "tags": ["A"], "star": False},
        ],
    )
    assert _rows(sps.read_annotations("Pilot"))[0]["tags"] == ["A"]


def test_the_cli_lists_a_missing_whole_trial_without_a_screen(pilot, tmp_path, capsys):
    p, t = pilot[0]
    table = tmp_path / "flags.csv"
    table.write_text(
        f"participant_id,trial_id,screen_id,tags\nghost,t9,,A\n{p},{t},page 9,A\n",
        encoding="utf-8",
    )
    cli.main(["annotations", "import", "Pilot", str(table)])
    out = capsys.readouterr().out
    assert "  ghost / t9\n" in out and f"{p} / {t} / screen page 9" in out
    assert "nan" not in out
