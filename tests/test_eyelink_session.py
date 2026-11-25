from __future__ import annotations

import re
import shutil
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from scanpath_studio import api, eyelink
from tests.eyelink_fixtures import _IAS, _IAS_GROUPS, EXPECTED, write_experiment

FIXATION_COLUMNS = [
    "participant_id",
    "trial_id",
    "text_id",
    "screen_id",
    "screen_index",
    "fixation_id",
    "x",
    "y",
    "duration_ms",
    "timestamp_ms",
    "eye",
    "image_path",
]
WORD_COLUMNS = [
    "participant_id",
    "trial_id",
    "text_id",
    "screen_id",
    "screen_index",
    "word_id",
    "text",
    "x",
    "y",
    "width",
    "height",
    "image_path",
]


def _content_id(boxes: list[tuple]) -> str:
    """The text id of interest areas given as the fixture's
    ``(word_id, left, top, right, bottom, text)`` rows."""
    frame = pd.DataFrame(
        [
            (i, left, top, right - left, bottom - top, word)
            for i, left, top, right, bottom, word in boxes
        ],
        columns=["word_id", "x", "y", "width", "height", "text"],
    )
    return eyelink._text_id(frame)


TEXT_IDS = {
    "1": _content_id(_IAS["IA_1.ias"]),
    "2": _content_id(_IAS["IA_2.ias"]),
    "4": _content_id(_IAS_GROUPS["IA_4.ias"][0]),
}


@pytest.fixture(autouse=True)
def _experimental(monkeypatch):
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")


def _tables(asc: Path, tmp_path: Path, **kwargs) -> eyelink.SessionTables:
    return eyelink.session_tables(asc, image_dir=tmp_path / "images", **kwargs)


def _expected_fixations(trials: dict) -> list[tuple]:
    """(trial, screen_id, screen_index, fixation_id, x, y, duration, timestamp, eye)
    for each fixation of ``trials``, from the fixture's hand-traced values."""
    rows = []
    for trial_id, trial in trials.items():
        number = 0
        for index, screen in enumerate(trial["screens"], start=1):
            for fix in screen["fixations"]:
                number += 1
                rows.append(
                    (
                        str(trial_id),
                        f"screen_{index}",
                        index,
                        number,
                        fix["x"],
                        fix["y"],
                        fix["duration_ms"],
                        fix["onset"] - trial["start"],
                        fix["eye"],
                    )
                )
    return rows


def _fixation_rows(fixations: pd.DataFrame) -> list[tuple]:
    columns = [
        "trial_id",
        "screen_id",
        "screen_index",
        "fixation_id",
        "x",
        "y",
        "duration_ms",
        "timestamp_ms",
        "eye",
    ]
    return list(fixations[columns].itertuples(index=False, name=None))


def _expected_words(trials: dict) -> list[tuple]:
    return [
        (str(trial_id), f"screen_{index}", index, word_id, text, x0, y0, x1, y1)
        for trial_id, trial in trials.items()
        for index, screen in enumerate(trial["screens"], start=1)
        for word_id, x0, y0, x1, y1, text in screen["words"]
    ]


def _word_rows(words: pd.DataFrame) -> list[tuple]:
    return [
        (
            r.trial_id,
            r.screen_id,
            r.screen_index,
            r.word_id,
            r.text,
            r.x,
            r.y,
            r.x + r.width,
            r.y + r.height,
        )
        for r in words.itertuples()
    ]


def _image_of(frame: pd.DataFrame, trial: str, screen: int) -> str:
    rows = frame[(frame["trial_id"] == trial) & (frame["screen_index"] == screen)]
    return rows["image_path"].iloc[0]


def test_session_fixations_match_expected(tmp_path):
    t = _tables(write_experiment(tmp_path), tmp_path)
    assert list(t.fixations.columns) == FIXATION_COLUMNS
    assert _fixation_rows(t.fixations) == _expected_fixations(EXPECTED["trials"])
    assert (t.fixations["participant_id"] == "p01").all()
    assert t.fixations["text_id"].tolist() == [TEXT_IDS["1"]] * 4 + [TEXT_IDS["2"]] * 2
    assert t.display == EXPECTED["display"]
    assert t.raw_gaze is None
    assert t.notes == []


def test_trial_metadata_holds_the_trial_vars(tmp_path):
    t = _tables(write_experiment(tmp_path), tmp_path)
    assert t.trial_metadata.to_dict("records") == [
        {"participant_id": "p01", "trial_id": str(trial_id), **trial["vars"]}
        for trial_id, trial in EXPECTED["trials"].items()
    ]


def test_fixation_assigned_by_onset_across_screen_change(tmp_path):
    t = _tables(write_experiment(tmp_path, multi_display=True), tmp_path)
    four = t.fixations[t.fixations["trial_id"] == "4"]
    multi = EXPECTED["multi_display_trials"]
    assert _fixation_rows(four) == _expected_fixations(multi)
    # It starts at 11735, 5 ms before the second screen begins at 11740.
    straddling = four[four["timestamp_ms"] == 11735 - multi[4]["start"]]
    assert straddling["screen_id"].tolist() == ["screen_1"]


def test_fixations_outside_trials_dropped(tmp_path):
    asc = write_experiment(tmp_path)
    lines = asc.read_text(encoding="utf-8").splitlines()
    first = lines.index("MSG\t990\tTRIALID 1")
    # A calibration block before the first trial and another between trials.
    lines[first:first] = [
        "START\t700 \tRIGHT\tEVENTS",
        "EFIX\tR\t710\t909\t200\t640.0\t512.0\t1000",
        "END\t950 \tEVENTS\tRES\t80.26\t60.44",
    ]
    second = lines.index("MSG\t3000\tTRIALID 2")
    lines[second:second] = [
        "START\t2500 \tRIGHT\tEVENTS",
        "EFIX\tR\t2510\t2709\t200\t640.0\t512.0\t1000",
        "END\t2800 \tEVENTS\tRES\t80.26\t60.44",
    ]
    # Trial 2's recording starts at 3010 and its first screen at 3033.
    start = lines.index("START\t3010 \tRIGHT\tEVENTS")
    lines.insert(start + 1, "EFIX\tR\t3012\t3030\t19\t640.0\t512.0\t1000")
    asc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t = _tables(asc, tmp_path)
    assert _fixation_rows(t.fixations) == _expected_fixations(EXPECTED["trials"])
    assert t.notes == [
        "Fixations left out: 1 before their trial's first screen, "
        "2 outside every trial."
    ]


def test_words_from_ias(tmp_path):
    t = _tables(write_experiment(tmp_path, multi_display=True), tmp_path)
    assert list(t.words.columns) == WORD_COLUMNS
    expected = {**EXPECTED["trials"], **EXPECTED["multi_display_trials"]}
    assert _word_rows(t.words) == _expected_words(expected)
    assert (t.words["participant_id"] == "p01").all()
    assert t.words["text_id"].tolist() == [
        TEXT_IDS[trial] for trial in t.words["trial_id"]
    ]


def test_question_screen_has_no_words(tmp_path):
    t = _tables(write_experiment(tmp_path, multi_display=True), tmp_path)
    screens = set(zip(t.words["trial_id"], t.words["screen_index"]))
    assert screens == {("1", 1), ("2", 1), ("4", 1), ("4", 2)}
    # The question screens still have their fixations and stimulus image.
    question = t.fixations[
        (t.fixations["trial_id"] == "1") & (t.fixations["screen_index"] == 2)
    ]
    assert question["text_id"].tolist() == [TEXT_IDS["1"]]
    assert Path(question["image_path"].iloc[0]).is_file()


def test_text_id_without_ias(tmp_path):
    asc = write_experiment(tmp_path, with_session_files=False)
    t = _tables(asc, tmp_path)
    assert t.fixations["text_id"].tolist() == ["trial_1"] * 4 + ["trial_2"] * 2


def test_text_id_is_the_interest_areas_content(tmp_path):
    """Experiment Builder numbers ``.ias`` files per session, so one file name
    holds different texts in two sessions: the id follows the content."""
    first = write_experiment(tmp_path / "a")
    second = write_experiment(tmp_path / "b")
    # Session b's IA_1.ias holds IA_2's words, and its IA_2.ias IA_1's.
    aoi = second.parent / "aoi"
    one, two = (aoi / "IA_1.ias").read_bytes(), (aoi / "IA_2.ias").read_bytes()
    (aoi / "IA_1.ias").write_bytes(two)
    (aoi / "IA_2.ias").write_bytes(one)
    a = _tables(first, tmp_path / "a")
    b = _tables(second, tmp_path / "b")
    ids_a = a.words.groupby("trial_id")["text_id"].first().to_dict()
    ids_b = b.words.groupby("trial_id")["text_id"].first().to_dict()
    assert ids_a == {"1": TEXT_IDS["1"], "2": TEXT_IDS["2"]}
    # The same file name, a different text: a different id; the same text
    # under another name: the same id.
    assert ids_b == {"1": TEXT_IDS["2"], "2": TEXT_IDS["1"]}
    assert all(re.fullmatch(r"ias_[0-9a-f]{12}", i) for i in ids_a.values())


def test_image_composed_once_per_identical_display(tmp_path):
    t = _tables(write_experiment(tmp_path, multi_display=True), tmp_path)
    pngs = sorted((tmp_path / "images").iterdir())
    # Six screens, four distinct displays: trial 4's first two repeat trial 1's
    # first and trial 2's.
    assert len(pngs) == 4
    assert _image_of(t.fixations, "1", 1) == _image_of(t.fixations, "4", 1)
    assert _image_of(t.fixations, "2", 1) == _image_of(t.fixations, "4", 2)
    assert _image_of(t.words, "1", 1) == _image_of(t.fixations, "1", 1)
    assert set(t.fixations["image_path"]) == {str(p) for p in pngs}
    with Image.open(_image_of(t.fixations, "1", 1)) as image:
        assert image.size == EXPECTED["display"]
        # text1.png (red, 300 x 100) at (100, 150) over the white background.
        assert image.getpixel((100, 150)) == (230, 40, 40)
        assert image.getpixel((399, 249)) == (230, 40, 40)
        assert image.getpixel((99, 150)) == (255, 255, 255)
        assert image.getpixel((400, 250)) == (255, 255, 255)
    with Image.open(_image_of(t.fixations, "4", 3)) as image:
        assert image.getpixel((0, 0)) == (200, 200, 200)


def test_compose_display_resizes_to_given_size(tmp_path):
    picture = tmp_path / "dot.png"
    Image.new("RGB", (10, 10), (0, 128, 0)).save(picture)
    display = eyelink.Display(0, (10, 20, 30), [(picture, 5, 7, 40, 20)])
    out = eyelink.compose_display(display, tmp_path / "out", (100, 50))
    assert out.parent == tmp_path / "out" and out.suffix == ".png"
    assert len(out.stem) == 16
    with Image.open(out) as image:
        assert image.size == (100, 50)
        assert image.getpixel((5, 7)) == (0, 128, 0)
        assert image.getpixel((44, 26)) == (0, 128, 0)
        assert image.getpixel((45, 26)) == (10, 20, 30)
        assert image.getpixel((44, 27)) == (10, 20, 30)
        assert image.getpixel((4, 7)) == (10, 20, 30)
    # The same display again is the same file.
    assert eyelink.compose_display(display, tmp_path / "out", (100, 50)) == out


def test_missing_session_files_still_loads(tmp_path):
    asc = write_experiment(tmp_path, with_session_files=False)
    t = _tables(asc, tmp_path)
    assert _fixation_rows(t.fixations) == _expected_fixations(EXPECTED["trials"])
    assert t.words.empty and list(t.words.columns) == WORD_COLUMNS
    assert t.fixations["image_path"].isna().all()
    assert t.notes == [
        "The session folder was not found, so the screens have no stimulus "
        "images or words (graphics/VC_1.vcl, aoi/IA_1.ias, graphics/VC_3.vcl, "
        "graphics/VC_2.vcl, aoi/IA_2.ias)."
    ]


def test_one_missing_ias_is_named(tmp_path):
    asc = write_experiment(tmp_path)
    (asc.parent / "aoi" / "IA_2.ias").unlink()
    t = _tables(asc, tmp_path)
    assert _fixation_rows(t.fixations) == _expected_fixations(EXPECTED["trials"])
    assert set(t.words["trial_id"]) == {"1"}
    assert t.notes == [
        f"aoi/IA_2.ias was not found in {asc.parent}; trial 2 has no words from it."
    ]


def test_binocular_words_not_duplicated(tmp_path):
    mono = _tables(write_experiment(tmp_path / "mono"), tmp_path / "mono")
    bino = _tables(write_experiment(tmp_path / "bino", binocular=True), tmp_path)
    pd.testing.assert_frame_equal(
        bino.words.drop(columns="image_path"), mono.words.drop(columns="image_path")
    )
    one = bino.fixations[bino.fixations["trial_id"] == "1"]
    assert list(zip(one["fixation_id"], one["eye"], one["timestamp_ms"])) == [
        (1, "R", 30),
        (2, "L", 32),
        (3, "R", 240),
        (4, "L", 242),
        (5, "R", 500),
        (6, "R", 730),
    ]
    assert one["screen_index"].tolist() == [1, 1, 1, 1, 1, 2]


def test_edf_goes_through_edf2asc(tmp_path, monkeypatch):
    asc = write_experiment(tmp_path)
    edf = asc.with_suffix(".edf")
    edf.write_bytes(b"")
    calls = []

    def fake_convert(source, out_dir, *, samples=False):
        calls.append((source, out_dir, samples))
        return Path(shutil.copy(asc, Path(out_dir) / asc.name))

    monkeypatch.setattr(eyelink, "convert_edf", fake_convert)
    asc_dir = tmp_path / "asc"
    asc_dir.mkdir()
    t = eyelink.session_tables(
        edf, image_dir=tmp_path / "images", asc_dir=asc_dir, session_dir=asc.parent
    )
    assert calls == [(edf, asc_dir, False)]
    assert _fixation_rows(t.fixations) == _expected_fixations(EXPECTED["trials"])
    assert t.words["trial_id"].nunique() == 2


def test_requires_experimental_flag(tmp_path, monkeypatch):
    asc = write_experiment(tmp_path)
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL")
    with pytest.raises(ValueError, match="SCANPATH_EXPERIMENTAL"):
        _tables(asc, tmp_path)


def _secret(tmp_path: Path) -> Path:
    """A picture outside the experiment folder (``tmp_path / "exp"``)."""
    secret = tmp_path / "secret.png"
    Image.new("RGB", (300, 100), (0, 255, 0)).save(secret)
    return secret


def test_vcl_paths_outside_the_experiment_are_refused(tmp_path):
    asc = write_experiment(tmp_path)
    secret = _secret(tmp_path)
    vcl = asc.parent / "graphics" / "VC_1.vcl"
    vcl.write_text(
        "0 CLEAR 255 255 255\n"
        "0 IMGLOAD TOP_LEFT ../../../secret.png 0 0\n"
        f"0 IMGLOAD TOP_LEFT {secret} 500 500\n"
        "0 IMGLOAD TOP_LEFT ../../runtime/images/text1.png 100 150\n",
        encoding="utf-8",
    )
    t = _tables(asc, tmp_path)
    root = tmp_path / "exp"
    assert t.notes == [
        f"graphics/VC_1.vcl: ../../../secret.png is outside the experiment folder "
        f"{root}; it was not read.",
        f"graphics/VC_1.vcl: {secret} is outside the experiment folder {root}; it "
        "was not read.",
    ]
    with Image.open(_image_of(t.fixations, "1", 1)) as image:
        assert image.getpixel((0, 0)) == (255, 255, 255)
        assert image.getpixel((500, 500)) == (255, 255, 255)
        # The experiment's own runtime/images still load.
        assert image.getpixel((100, 150)) == (230, 40, 40)


def test_draw_list_outside_the_experiment_is_refused(tmp_path):
    asc = write_experiment(tmp_path)
    outside = tmp_path / "VC_9.vcl"
    outside.write_text("0 CLEAR 0 255 0\n", encoding="utf-8")
    text = asc.read_text(encoding="utf-8")
    asc.write_text(
        text.replace("graphics/VC_2.vcl", "../../../VC_9.vcl"), encoding="utf-8"
    )
    t = _tables(asc, tmp_path)
    root = tmp_path / "exp"
    assert t.notes == [
        f"Trial 2: ../../../VC_9.vcl is outside the experiment folder {root}; it "
        "was not read."
    ]
    assert pd.isna(_image_of(t.fixations, "2", 1))


def test_inline_imgload_outside_the_experiment_is_refused(tmp_path):
    asc = write_experiment(tmp_path, inline=True)
    secret = _secret(tmp_path)
    text = asc.read_text(encoding="utf-8")
    asc.write_text(
        text.replace("../../runtime/images/text2.png", str(secret)), encoding="utf-8"
    )
    t = _tables(asc, tmp_path)
    root = tmp_path / "exp"
    assert t.notes == [
        f"Trial 2: {secret} is outside the experiment folder {root}; it was not read."
    ]
    with Image.open(_image_of(t.fixations, "2", 1)) as image:
        assert image.getpixel((100, 150)) == (255, 255, 255)


def test_frames_load_in_the_app_pipeline(tmp_path):
    t = _tables(write_experiment(tmp_path), tmp_path)
    # The app's multipart check refuses a screen that is in one table only, so
    # the question screen (fixations, no words) is left out here.
    worded = t.fixations.merge(
        t.words[["trial_id", "screen_id"]].drop_duplicates(), how="inner"
    )
    data = api.load_scanpath_data(t.words, worded)
    fig = api.plot_scanpath(
        data.words,
        data.fixations,
        "p01",
        "1",
        screen="screen_1",
        show_stimulus_image=True,
    )
    assert len(fig.layout.images) == 1
    assert fig.layout.images[0].source
    assert len(data.fixations) == 5 and len(data.words) == 5


def test_repeated_trial_ids_kept_apart(tmp_path):
    asc = write_experiment(tmp_path)
    text = asc.read_text(encoding="utf-8")
    asc.write_text(text.replace("TRIALID 2", "TRIALID 1"), encoding="utf-8")
    t = _tables(asc, tmp_path)
    second = {"1_r2": EXPECTED["trials"][2]}
    assert _fixation_rows(t.fixations) == _expected_fixations(
        {1: EXPECTED["trials"][1], **second}
    )
    assert _word_rows(t.words) == _expected_words({1: EXPECTED["trials"][1], **second})
    assert t.words.groupby("trial_id")["text_id"].first().to_dict() == {
        "1": TEXT_IDS["1"],
        "1_r2": TEXT_IDS["2"],
    }
    assert t.trial_metadata["trial_id"].tolist() == ["1", "1_r2"]
    assert t.trial_metadata["condition"].tolist() == ["Adv", "Ele"]
    # Each reading keeps its own stimulus: red text1 for 1, blue text2 for 1_r2.
    with Image.open(_image_of(t.fixations, "1", 1)) as image:
        assert image.getpixel((100, 150)) == (230, 40, 40)
    with Image.open(_image_of(t.fixations, "1_r2", 1)) as image:
        assert image.getpixel((100, 150)) == (40, 40, 230)
    assert _image_of(t.words, "1_r2", 1) == _image_of(t.fixations, "1_r2", 1)
    assert t.notes == [
        "TRIALID 1 is logged more than once; its later readings are 1_r2."
    ]


def test_loose_session_folder_is_its_own_root(tmp_path):
    lab = write_experiment(tmp_path / "lab")
    loose = tmp_path / "dl" / "p01"
    shutil.copytree(lab.parent, loose)
    # Where the .vcl's ../../runtime/images would lead from the loose folder.
    shutil.copytree(tmp_path / "lab" / "exp" / "runtime", tmp_path / "runtime")
    asc = loose / lab.name
    t = _tables(asc, tmp_path)
    refused = (
        f"graphics/VC_1.vcl: ../../runtime/images/text1.png is outside the "
        f"experiment folder {loose}; it was not read."
    )
    assert refused in t.notes
    with Image.open(_image_of(t.fixations, "1", 1)) as image:
        assert image.getpixel((100, 150)) == (255, 255, 255)
    # Naming the experiment folder widens the root to it.
    t = eyelink.session_tables(
        asc, image_dir=tmp_path / "images2", experiment_dir=tmp_path
    )
    assert t.notes == []
    with Image.open(_image_of(t.fixations, "1", 1)) as image:
        assert image.getpixel((100, 150)) == (230, 40, 40)


def test_repeated_trial_id_never_takes_a_logged_one(tmp_path):
    """TRIALIDs ``1, 1, 1_r2``: the second ``1`` cannot be ``1_r2``, which the
    third reading is logged as."""
    asc = write_experiment(tmp_path, aborted_trial=True)
    text = asc.read_text(encoding="utf-8")
    text = text.replace("TRIALID 2", "TRIALID 1").replace("TRIALID 3", "TRIALID 1_r2")
    asc.write_text(text, encoding="utf-8")
    t = _tables(asc, tmp_path)
    assert t.trial_metadata["trial_id"].tolist() == ["1", "1_r3", "1_r2"]
    assert sorted(t.fixations["trial_id"].unique()) == ["1", "1_r2", "1_r3"]
    assert t.notes[-1] == (
        "TRIALID 1 is logged more than once; its later readings are 1_r3 "
        "(1_r2 is a TRIALID of its own)."
    )
