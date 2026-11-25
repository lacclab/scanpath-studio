from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from scanpath_studio import eyelink
from tests.eyelink_fixtures import EXPECTED, write_experiment


@pytest.fixture(autouse=True)
def _experimental(monkeypatch):
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")


def _tables(asc: Path, session: Path | None = None):
    rec = eyelink.read_asc(asc)
    trials = eyelink.trial_table(rec)
    screens, notes = eyelink.screen_table(rec, trials, session)
    return rec, trials, screens, notes


def _expected_screens(trials: dict) -> list[tuple]:
    return [
        (str(trial_id), i, f"screen_{i}", screen["begin"], screen["end"])
        for trial_id, trial in trials.items()
        for i, screen in enumerate(trial["screens"], start=1)
    ]


def _screen_rows(screens: pd.DataFrame) -> list[tuple]:
    columns = ["trial_id", "screen_index", "screen_id", "begin", "end"]
    return list(screens[columns].itertuples(index=False, name=None))


def _words(boxes: pd.DataFrame | None) -> list[tuple]:
    """A screen's boxes as the fixture's (word_id, left, top, right, bottom, text)."""
    if boxes is None:
        return []
    return [
        (r.word_id, r.x, r.y, r.x + r.width, r.y + r.height, r.text)
        for r in boxes.itertuples()
    ]


def test_trial_bounds(tmp_path):
    _, trials, _, _ = _tables(write_experiment(tmp_path, multi_display=True))
    assert list(trials.columns) == ["trial_id", "start", "begin", "end"]
    expected = {**EXPECTED["trials"], **EXPECTED["multi_display_trials"]}
    assert list(trials.itertuples(index=False, name=None)) == [
        (str(trial_id), t["start"], t["begin"], t["end"])
        for trial_id, t in expected.items()
    ]


def test_aborted_trial_ends_at_next_trialid(tmp_path):
    asc = write_experiment(tmp_path, aborted_trial=True, multi_display=True)
    _, trials, _, _ = _tables(asc)
    aborted = EXPECTED["trial_aborted"]
    row = trials.set_index("trial_id").loc[aborted["trial_id"]]
    assert (row["start"], row["begin"], row["end"]) == (
        aborted["start"],
        aborted["begin"],
        aborted["end_at_next_trialid"],
    )


def test_aborted_last_trial_ends_at_file_end(tmp_path):
    _, trials, _, _ = _tables(write_experiment(tmp_path, aborted_trial=True))
    aborted = EXPECTED["trial_aborted"]
    row = trials.set_index("trial_id").loc[aborted["trial_id"]]
    assert row["end"] == aborted["end_at_file_end"]


def test_trial_vars_table(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path, multi_display=True))
    table = eyelink.trial_vars(rec)
    expected = {**EXPECTED["trials"], **EXPECTED["multi_display_trials"]}
    assert table.to_dict("records") == [
        {"trial_id": str(trial_id), **t["vars"]} for trial_id, t in expected.items()
    ]
    assert list(table.columns) == ["trial_id", "condition", "item", "Session_Name_"]


def test_screen_begins_one_draw_list_per_screen(tmp_path):
    asc = write_experiment(tmp_path)
    _, _, screens, notes = _tables(asc, asc.parent)
    assert _screen_rows(screens) == _expected_screens(EXPECTED["trials"])
    assert notes == []


def test_vcl_displays_and_times(tmp_path):
    asc = write_experiment(tmp_path, multi_display=True)
    _, trials, screens, notes = _tables(asc, asc.parent)
    multi = EXPECTED["multi_display_trials"]
    four = screens[screens["trial_id"] == "4"]
    assert _screen_rows(four) == _expected_screens(multi)
    # The draw list was logged at 5120; its -6620 and -9204 displays begin
    # that many ms after it.
    drawn = multi[4]["screens"][0]["drawn"]
    assert four["begin"].tolist() == [drawn, drawn + 6620, drawn + 9204]
    assert four["end"].tolist()[:-1] == four["begin"].tolist()[1:]
    assert four["end"].iloc[-1] == trials.set_index("trial_id").loc["4", "end"]
    images = tmp_path / "exp" / "runtime" / "images"
    first, second, question = four["display"]
    assert first.background == (255, 255, 255)
    assert first.images == [
        (images / "bg.png", 0, 0, None, None),
        (images / "text1.png", 100, 150, 300, 100),
    ]
    assert second.images == [
        (images / "bg.png", 0, 0, None, None),
        (images / "text2.png", 100, 150, None, None),
    ]
    assert (question.background, question.images) == ((200, 200, 200), [])
    assert all(path.is_file() for path, *_ in first.images + second.images)
    assert notes == []


def test_parse_vcl_offsets_and_skipped_commands(tmp_path):
    vcl = tmp_path / "graphics" / "VC_9.vcl"
    vcl.parent.mkdir()
    vcl.write_text(
        "﻿0 CLEAR 255 255 255\n"
        "0 IMGLOAD CENTER pic.png 640 512\n"
        "-250 CLEAR 0 0 0\n"
        "-250 DRAW_LINE 0 0 10 10\n"
        "-250 IMGLOAD TOP_LEFT pic.png 5 6\n",
        encoding="utf-8",
    )
    displays = eyelink.parse_vcl(vcl)
    assert [(d.offset, d.background) for d in displays] == [
        (0, (255, 255, 255)),
        (-250, (0, 0, 0)),
    ]
    assert displays[0].images == []
    assert displays[0].skipped == ["0 IMGLOAD CENTER pic.png 640 512"]
    # Without a session folder an image path stays as the .vcl wrote it.
    assert displays[1].images == [(Path("pic.png"), 5, 6, None, None)]
    assert displays[1].skipped == ["-250 DRAW_LINE 0 0 10 10"]
    session = eyelink.parse_vcl(vcl, session=tmp_path)
    assert session[1].images == [(tmp_path / "pic.png", 5, 6, None, None)]


def test_ias_boxes(tmp_path):
    asc = write_experiment(tmp_path, multi_display=True)
    boxes = eyelink.parse_ias(asc.parent / "aoi" / "IA_4.ias")
    assert list(boxes.columns) == [
        "offset",
        "word_id",
        "x",
        "y",
        "width",
        "height",
        "text",
    ]
    assert boxes.iloc[0].to_dict() == {
        "offset": 0,
        "word_id": 1,
        "x": 358,
        "y": 154,
        "width": 95,
        "height": 107,
        "text": "Food",
    }
    assert boxes["offset"].tolist() == [0, 0, -6623, -6623]
    assert boxes.attrs["skipped"] == []


def test_ias_other_shapes_skipped(tmp_path):
    ias = tmp_path / "IA_9.ias"
    ias.write_text(
        "0 RECTANGLE\t1\t10\t20\t30\t40\tTwo words\n"
        "0 ELLIPSE\t2\t30\t20\t50\t40\tround\n",
        encoding="utf-8",
    )
    boxes = eyelink.parse_ias(ias)
    assert boxes[["word_id", "text"]].values.tolist() == [[1, "Two words"]]
    assert boxes.attrs["skipped"] == ["0 ELLIPSE\t2\t30\t20\t50\t40\tround"]


def test_ias_bound_to_screen_by_time(tmp_path):
    asc = write_experiment(tmp_path, multi_display=True)
    _, _, screens, notes = _tables(asc, asc.parent)
    expected = {**EXPECTED["trials"], **EXPECTED["multi_display_trials"]}
    session = asc.parent
    for trial_id, trial in expected.items():
        rows = screens[screens["trial_id"] == str(trial_id)]
        assert [None if p is None else p for p in rows["ias"]] == [
            None if s["ias"] is None else session / s["ias"] for s in trial["screens"]
        ]
        assert [_words(b) for b in rows["boxes"]] == [
            s["words"] for s in trial["screens"]
        ]
    # A question screen has no interest areas.
    question = screens[(screens["trial_id"] == "4") & (screens["screen_index"] == 3)]
    assert question["ias"].iloc[0] is None and question["boxes"].iloc[0] is None
    assert notes == []


def test_ias_group_far_from_every_display_is_reported(tmp_path):
    asc = write_experiment(tmp_path, multi_display=True)
    ias = asc.parent / "aoi" / "IA_4.ias"
    ias.write_text(ias.read_text(encoding="utf-8").replace("-6623", "-6700"))
    _, _, screens, notes = _tables(asc, asc.parent)
    four = screens[screens["trial_id"] == "4"]
    assert [_words(b) for b in four["boxes"]] == [
        EXPECTED["multi_display_trials"][4]["screens"][0]["words"],
        [],
        [],
    ]
    assert notes == [
        "Trial 4: interest areas in aoi/IA_4.ias at 11820 ms match no display "
        "(the nearest begins 80 ms away); they were left out."
    ]


def test_older_layout_groups_bind_to_their_displays(tmp_path):
    asc = write_experiment(tmp_path, older_layout=True)
    _, _, screens, notes = _tables(asc, asc.parent)
    expected = EXPECTED["older_layout_trials"]
    five = screens[screens["trial_id"] == "5"]
    assert _screen_rows(five) == _expected_screens(expected)
    assert list(five["ias"]) == [
        None if s["ias"] is None else asc.parent / s["ias"]
        for s in expected[5]["screens"]
    ]
    assert [_words(b) for b in five["boxes"]] == [
        s["words"] for s in expected[5]["screens"]
    ]
    assert notes == []


def _move_line(asc: Path, old: str, new: str) -> None:
    text = asc.read_text(encoding="utf-8")
    assert text.count(old) == 1
    asc.write_text(text.replace(old, new), encoding="utf-8")


def test_ias_file_more_than_a_refresh_off_is_reported(tmp_path):
    asc = write_experiment(tmp_path, older_layout=True)
    # Logged at 21014, 30 ms before the paragraph display: groups at 21014 and
    # 25397, 30 and 29 ms from their displays.
    _move_line(
        asc,
        "MSG\t21023\t-11 !V IAREA FILE",
        "MSG\t21003\t-11 !V IAREA FILE",
    )
    _, _, screens, notes = _tables(asc, asc.parent)
    five = screens[screens["trial_id"] == "5"]
    assert five["boxes"].isna().all()
    assert notes == [
        "Trial 5: interest areas in aoi/IA_5.ias at 21014 ms match no display "
        "(the nearest begins 30 ms away); they were left out.",
        "Trial 5: interest areas in aoi/IA_5.ias at 25397 ms match no display "
        "(the nearest begins 29 ms away); they were left out.",
    ]


def test_groups_of_one_ias_file_move_together(tmp_path):
    asc = write_experiment(tmp_path, older_layout=True)
    ias = asc.parent / "aoi" / "IA_5.ias"
    # The second group now falls 1 ms after its display while the first stays
    # 10 ms before its own: no one shift brings both within IAS_MATCH_MS, so the
    # first is not moved on its own.
    ias.write_text(ias.read_text(encoding="utf-8").replace("-4383", "-4393"))
    _, _, screens, notes = _tables(asc, asc.parent)
    five = screens[screens["trial_id"] == "5"]
    groups = EXPECTED["older_layout_trials"][5]["screens"]
    assert [_words(b) for b in five["boxes"]] == [[], [], [], groups[3]["words"]]
    assert notes == [
        "Trial 5: interest areas in aoi/IA_5.ias at 21034 ms match no display "
        "(the nearest begins 10 ms away, and no one shift of the file's groups "
        "matches them all); they were left out."
    ]


def _add_displays(asc: Path, *offsets: int) -> None:
    """Add blank displays at ``offsets`` to trial 5's draw list."""
    vcl = asc.parent / "graphics" / "VC_5.vcl"
    lines = vcl.read_text(encoding="utf-8").splitlines()
    lines += [f"{offset} CLEAR 255 255 255" for offset in offsets]
    vcl.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_shift_never_moves_a_matched_group_to_another_display(tmp_path):
    asc = write_experiment(tmp_path, older_layout=True)
    # A display at 21030, 14 ms before the paragraph's: the first group (21034)
    # matches it as logged.  Only shifts of +4 to +14 would match the second
    # group (25417), and each moves the first onto 21044, so none is taken.
    _add_displays(asc, -947)
    _, _, screens, notes = _tables(asc, asc.parent)
    five = screens[screens["trial_id"] == "5"]
    groups = EXPECTED["older_layout_trials"][5]["screens"]
    assert list(five["begin"]) == [20083, 21030, 21044, 23225, 25426]
    assert [_words(b) for b in five["boxes"]] == [
        [],
        groups[1]["words"],
        [],
        [],
        [],
    ]
    assert notes == [
        "Trial 5: interest areas in aoi/IA_5.ias at 25417 ms match no display "
        "(the nearest begins 9 ms away, and no one shift of the file's groups "
        "matches them all); they were left out."
    ]


def test_ambiguous_shift_leaves_the_file_unbound(tmp_path):
    asc = write_experiment(tmp_path, older_layout=True)
    # Displays at 21026 and 25409 as well: a shift of -8 fits the groups
    # (21034, 25417) to those, +9 to 21044 and 25426.
    _add_displays(asc, -943, -5326)
    _, _, screens, notes = _tables(asc, asc.parent)
    five = screens[screens["trial_id"] == "5"]
    assert five["boxes"].isna().all()
    ambiguous = (
        "; the file's timing is ambiguous, since shifting its groups together "
        "fits more than one set of displays); they were left out."
    )
    assert notes == [
        "Trial 5: interest areas in aoi/IA_5.ias at 21034 ms match no display "
        "(the nearest begins 8 ms away" + ambiguous,
        "Trial 5: interest areas in aoi/IA_5.ias at 25417 ms match no display "
        "(the nearest begins 8 ms away" + ambiguous,
    ]


@pytest.mark.parametrize(
    ("begins", "times", "expected"),
    [
        # Every group matches as logged: no shift.
        ([1000, 5000], [1003, 4998], (0, False)),
        # The whole file 9 ms early: moved together.
        ([1000, 5000, 9000], [991, 4991, 8991], (9, False)),
        # A shift that matches the rest would move 1017 off the display it
        # matches as logged (onto 1003, or nowhere).
        ([1003, 1017, 5000, 9000], [1017, 5012, 9012], (0, False)),
        ([1000, 1017, 5000, 9000], [1017, 5012, 9012], (0, False)),
        # -4 keeps 1017 where it is and brings the others within reach.
        ([1003, 1017, 5000, 9000], [1017, 5009, 9009], (-4, False)),
        # No shift lands a group exactly on a display, but 3 brings both within
        # IAS_MATCH_MS of theirs.
        ([1000, 5000], [992, 5002], (3, False)),
        # -8 and +9 both match every group, to different displays.
        ([1000, 1017, 5000, 5017], [1008, 5008], (0, True)),
        # Beyond IAS_SHIFT_MS.
        ([1000, 5000], [970, 4970], (0, False)),
    ],
)
def test_ias_shift(begins, times, expected):
    assert eyelink._ias_shift(begins, times) == expected


def test_resolve_session_dir_order(tmp_path):
    asc = write_experiment(tmp_path / "lab")
    rec = eyelink.read_asc(asc)
    sibling = asc.parent
    explicit = tmp_path / "copy"
    shutil.copytree(sibling, explicit)
    assert (
        eyelink.resolve_session_dir(asc, rec, session_dir=explicit, experiment_dir=None)
        == explicit
    )
    assert (
        eyelink.resolve_session_dir(asc, rec, session_dir=None, experiment_dir=None)
        == sibling
    )
    # A folder holding none of the files the messages name is passed over.
    empty = tmp_path / "empty"
    empty.mkdir()
    assert (
        eyelink.resolve_session_dir(asc, rec, session_dir=empty, experiment_dir=None)
        == sibling
    )
    apart = tmp_path / "asc" / asc.name
    apart.parent.mkdir()
    shutil.copy(asc, apart)
    assert (
        eyelink.resolve_session_dir(
            apart, rec, session_dir=None, experiment_dir=tmp_path / "lab" / "exp"
        )
        == sibling
    )
    assert (
        eyelink.resolve_session_dir(apart, rec, session_dir=None, experiment_dir=None)
        is None
    )


def test_missing_session_files_are_named(tmp_path):
    asc = write_experiment(tmp_path, with_session_files=False)
    _, _, screens, notes = _tables(asc, asc.parent)
    # Each draw list still starts a screen at the time it was logged.
    assert _screen_rows(screens) == _expected_screens(EXPECTED["trials"])
    assert screens["display"].isna().all() and screens["ias"].isna().all()
    assert notes == [
        f"{name} was not found in {asc.parent}; trial {trial} {what}."
        for name, trial, what in [
            ("graphics/VC_1.vcl", 1, "has no stimulus for that draw list"),
            ("aoi/IA_1.ias", 1, "has no words from it"),
            ("graphics/VC_3.vcl", 1, "has no stimulus for that draw list"),
            ("graphics/VC_2.vcl", 2, "has no stimulus for that draw list"),
            ("aoi/IA_2.ias", 2, "has no words from it"),
        ]
    ]


def test_no_session_folder(tmp_path):
    asc = write_experiment(tmp_path, with_session_files=False)
    _, _, screens, notes = _tables(asc, None)
    assert _screen_rows(screens) == _expected_screens(EXPECTED["trials"])
    assert notes == [
        "The session folder was not found, so the screens have no stimulus "
        "images or words (graphics/VC_1.vcl, aoi/IA_1.ias, graphics/VC_3.vcl, "
        "graphics/VC_2.vcl, aoi/IA_2.ias)."
    ]


def test_inline_iarea_and_imgload(tmp_path):
    files = write_experiment(tmp_path / "files", multi_display=True)
    inline = write_experiment(tmp_path / "inline", multi_display=True, inline=True)
    _, f_trials, f_screens, f_notes = _tables(files, files.parent)
    _, i_trials, i_screens, i_notes = _tables(inline, inline.parent)
    assert not (inline.parent / "aoi").exists()
    assert not (inline.parent / "graphics").exists()
    pd.testing.assert_frame_equal(f_trials, i_trials)
    assert _screen_rows(i_screens) == _screen_rows(f_screens)
    for f_display, i_display in zip(f_screens["display"], i_screens["display"]):
        assert i_display.background == f_display.background
        assert [
            (path.relative_to(tmp_path / "inline"), *rest)
            for path, *rest in i_display.images
        ] == [
            (path.relative_to(tmp_path / "files"), *rest)
            for path, *rest in f_display.images
        ]
    assert [_words(b) for b in i_screens["boxes"]] == [
        _words(b) for b in f_screens["boxes"]
    ]
    assert i_screens["ias"].isna().all()
    assert f_notes == i_notes == []


def test_trial_without_display_is_one_screen(tmp_path):
    asc = tmp_path / "bare.asc"
    asc.write_text(
        "MSG\t100\tTRIALID 7\n"
        "START\t110 \tRIGHT\tEVENTS\n"
        "EFIX\tR\t120\t219\t100\t10.0\t20.0\t1000\n"
        "END\t300 \tEVENTS\tRES\t1\t1\n"
        "MSG\t310\tTRIAL_RESULT 0\n",
        encoding="utf-8",
    )
    _, _, screens, notes = _tables(asc, None)
    assert _screen_rows(screens) == [("7", 1, "screen_1", 100, 310)]
    assert screens["display"].iloc[0] is None
    assert notes == []
