from __future__ import annotations

import builtins
import io
import sys

import pandas as pd
import pytest

from scanpath_studio import eyelink
from tests.eyelink_fixtures import EXPECTED, write_experiment


@pytest.fixture(autouse=True)
def _experimental(monkeypatch):
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")


def _rows(frame: pd.DataFrame) -> list[dict]:
    return frame.sort_values(["eye", "onset"]).to_dict("records")


def test_read_fixations_positions(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path))
    assert list(rec.fixations.columns) == [
        "eye",
        "onset",
        "offset",
        "duration_ms",
        "x",
        "y",
    ]
    assert _rows(rec.fixations) == EXPECTED["fixations"]


def test_messages_offset_corrected(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path))
    rows = list(zip(rec.messages["time"], rec.messages["text"]))
    assert (1013, "!V DRAW_LIST graphics/VC_1.vcl") in rows
    assert (1013, "!V IAREA FILE aoi/IA_1.ias") in rows
    # A message without an offset keeps its own time and text.
    assert (990, "TRIALID 1") in rows
    assert (2010, "!V TRIAL_VAR condition Adv") in rows


def test_display_size(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path))
    assert rec.display == EXPECTED["display"] == (1280, 1024)


def test_blocks(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path))
    assert list(zip(rec.blocks["start"], rec.blocks["end"])) == EXPECTED["blocks"]


def test_block_without_end_is_open(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path, aborted_trial=True))
    last = rec.blocks.iloc[-1]
    assert last["start"] == EXPECTED["block_aborted"][0]
    assert pd.isna(last["end"])
    assert len(rec.blocks) == 3


def test_binocular_keeps_both_eyes(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path, binocular=True))
    assert (
        _rows(rec.fixations[rec.fixations["eye"] == "L"]) == EXPECTED["fixations_left"]
    )
    assert _rows(rec.fixations[rec.fixations["eye"] == "R"]) == EXPECTED["fixations"]
    assert len(rec.blocks) == 2


def test_latin1_asc_parses(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path, latin1=True))
    assert "participant: Renée" in set(rec.messages["text"])
    assert _rows(rec.fixations) == EXPECTED["fixations"]


@pytest.mark.parametrize("latin1", [False, True])
def test_asc_parsed_once_in_its_encoding(tmp_path, monkeypatch, latin1):
    import pymovements as pm

    real = pm.gaze.from_asc
    files = []

    def counting(file, **kwargs):
        files.append(file)
        return real(file, **kwargs)

    monkeypatch.setattr(pm.gaze, "from_asc", counting)
    rec = eyelink.read_asc(write_experiment(tmp_path, latin1=latin1))
    # One parse, of text already decoded: pymovements never opens the file.
    assert len(files) == 1 and isinstance(files[0], io.TextIOBase)
    assert ("participant: Renée" in set(rec.messages["text"])) == latin1


def test_each_line_decoded_on_its_own(tmp_path):
    """A UTF-8 file with one stray latin-1 byte: that line reads as latin-1,
    every other line as UTF-8."""
    asc = write_experiment(tmp_path)
    lines = asc.read_bytes().split(b"\n")
    at = lines.index(b"MSG\t2010\t!V TRIAL_VAR item 1")
    lines.insert(at + 1, "MSG\t2010\t!V TRIAL_VAR title “Rising seas”".encode())
    lines.insert(4, "MSG\t600\tparticipant: Renée".encode("latin-1"))
    asc.write_bytes(b"\n".join(lines))
    rec = eyelink.read_asc(asc)
    assert "participant: Renée" in set(rec.messages["text"])
    variables = eyelink.trial_vars(rec).set_index("trial_id")
    assert variables.loc["1", "title"] == "“Rising seas”"
    assert _rows(rec.fixations) == EXPECTED["fixations"]


def _with_lines(asc, after: bytes, lines: list[bytes]) -> None:
    rows = asc.read_bytes().split(b"\n")
    at = rows.index(after) + 1
    rows[at:at] = lines
    asc.write_bytes(b"\n".join(rows))


def test_long_message_joined_from_its_chunks(tmp_path):
    """Experiment Builder's LONGMS chunks are joined as bytes: a chunk may
    begin with the message's own space, and a character may be cut between
    two chunks."""
    asc = write_experiment(tmp_path)
    quote = "“".encode()
    _with_lines(
        asc,
        b"MSG\t2010\t!V TRIAL_VAR item 1",
        [
            b"MSG\t2010\t!V LONGMS_ST_501 !V TRIAL_VAR paragraph Leading water",
            b"MSG\t2010\t!V LONGMS_CONT_501  scientists said " + quote[:2],
            b"MSG\t2010\t!V LONGMS_CONT_501 " + quote[2:] + "no” twice.".encode(),
            b"MSG\t2010\t!V TRIAL_VAR after long",
        ],
    )
    rec = eyelink.read_asc(asc)
    assert not any("LONGMS" in text for text in rec.messages["text"])
    variables = eyelink.trial_vars(rec).set_index("trial_id")
    assert (
        variables.loc["1", "paragraph"] == "Leading water scientists said “no” twice."
    )
    assert variables.loc["1", "after"] == "long"
    assert variables.loc["1", "item"] == "1"
    assert _rows(rec.fixations) == EXPECTED["fixations"]


def test_long_message_ids_crlf_and_reuse(tmp_path):
    asc = write_experiment(tmp_path)
    _with_lines(
        asc,
        b"MSG\t3510\t!V TRIAL_VAR item 2",
        [
            b"MSG\t3510\t!V LONGMS_ST_7 !V TRIAL_VAR title Ri",
            b"MSG\t3510\t!V LONGMS_CONT_7 sing",
            b"MSG\t3511\t!V LONGMS_ST_8a !V TRIAL_VAR note a",
            b"MSG\t3511\t!V LONGMS_CONT_8a b",
            b"MSG\t3512\t!V LONGMS_ST_7 !V TRIAL_VAR again one ",
            b"MSG\t3512\t!V LONGMS_CONT_7 more",
        ],
    )
    asc.write_bytes(asc.read_bytes().replace(b"\n", b"\r\n"))
    variables = eyelink.trial_vars(eyelink.read_asc(asc)).set_index("trial_id")
    assert variables.loc["2", "title"] == "Rising"
    assert variables.loc["2", "note"] == "ab"
    # An id used again starts a message of its own.
    assert variables.loc["2", "again"] == "one more"


def test_crlf_asc_parses(tmp_path):
    asc = write_experiment(tmp_path)
    asc.write_bytes(asc.read_bytes().replace(b"\n", b"\r\n"))
    rec = eyelink.read_asc(asc)
    assert _rows(rec.fixations) == EXPECTED["fixations"]
    assert "TRIALID 1" in set(rec.messages["text"])
    assert len(rec.blocks) == 2


def test_events_only_has_no_samples(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path), samples=False)
    assert rec.samples is None


def test_missing_pymovements_names_extra(tmp_path, monkeypatch):
    asc = write_experiment(tmp_path)
    for name in [m for m in sys.modules if m.split(".")[0] == "pymovements"]:
        monkeypatch.delitem(sys.modules, name)
    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name.split(".")[0] == "pymovements":
            raise ModuleNotFoundError(
                "No module named 'pymovements'", name="pymovements"
            )
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(ImportError, match=r"scanpath-studio\[edf\]"):
        eyelink.read_asc(asc)


def test_read_asc_is_gated(tmp_path, monkeypatch):
    asc = write_experiment(tmp_path)
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL")
    with pytest.raises(ValueError, match="SCANPATH_EXPERIMENTAL"):
        eyelink.read_asc(asc)


def test_fixture_session_files(tmp_path):
    asc = write_experiment(tmp_path)
    session = asc.parent
    assert asc == tmp_path / "exp" / "results" / "p01" / "p01.asc"
    for name in (
        "aoi/IA_1.ias",
        "aoi/IA_2.ias",
        "graphics/VC_1.vcl",
        "graphics/VC_2.vcl",
    ):
        assert (session / name).is_file()
    for name in ("bg.png", "text1.png", "text2.png"):
        assert (tmp_path / "exp" / "runtime" / "images" / name).is_file()
    bare = write_experiment(tmp_path / "bare", with_session_files=False)
    assert [p.name for p in bare.parent.iterdir()] == ["p01.asc"]


def test_aborted_trial_keeps_its_fixations(tmp_path):
    rec = eyelink.read_asc(write_experiment(tmp_path, aborted_trial=True))
    assert _rows(rec.fixations) == EXPECTED["fixations"] + EXPECTED["fixations_aborted"]


def _samples_asc(tmp_path, eyes: str, rows: list[str]):
    asc = tmp_path / "s.asc"
    head = [
        f"SAMPLES\tGAZE\t{eyes}\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2",
        f"START\t1000 \t{eyes}\tSAMPLES\tEVENTS",
        "PRESCALER\t1",
        "VPRESCALER\t1",
        "PUPIL\tAREA",
    ]
    asc.write_text(
        "\n".join([*head, *rows, "END\t1003 \tSAMPLES\tEVENTS\tRES\t1\t1"]) + "\n"
    )
    return asc


def test_samples_monocular_lost_tick_has_no_pupil(tmp_path):
    asc = _samples_asc(
        tmp_path,
        "RIGHT",
        ["1001\t100.0\t200.0\t1300.0\t...", "1002\t.\t.\t0.0\t..."],
    )
    samples = eyelink.read_asc(asc, samples=True).samples
    assert list(samples.columns) == ["time", "x", "y", "pupil", "eye"]
    assert samples["eye"].tolist() == ["R", "R"]
    assert samples["x"].tolist()[0] == 100.0
    assert samples[["x", "y", "pupil"]].iloc[1].isna().all()


def test_samples_binocular_has_a_row_per_eye(tmp_path):
    asc = _samples_asc(
        tmp_path,
        "LEFT\tRIGHT",
        ["1001\t100.0\t200.0\t1300.0\t110.0\t210.0\t1310.0\t..."],
    )
    samples = eyelink.read_asc(asc, samples=True).samples
    assert samples.to_dict("records") == [
        {"time": 1001, "x": 100.0, "y": 200.0, "pupil": 1300.0, "eye": "L"},
        {"time": 1001, "x": 110.0, "y": 210.0, "pupil": 1310.0, "eye": "R"},
    ]


def test_events_only_read_skips_the_sample_lines(tmp_path, monkeypatch):
    """Read events only, a recording with samples gives what a read with them
    gives, and pymovements is never handed a sample line."""
    asc = write_experiment(tmp_path, samples=True, binocular=True)
    full = eyelink.read_asc(asc, samples=True)
    real = eyelink._parse_asc
    handed: list[list[str]] = []

    def recording(lines, name):
        handed.append(list(lines))
        return real(lines, name)

    monkeypatch.setattr(eyelink, "_parse_asc", recording)
    events = eyelink.read_asc(asc, samples=False)
    assert events.samples is None
    assert handed and not any(line[:1].isdigit() for line in handed[0])
    pd.testing.assert_frame_equal(events.fixations, full.fixations)
    pd.testing.assert_frame_equal(events.messages, full.messages)
    pd.testing.assert_frame_equal(events.blocks, full.blocks)
    assert (events.display, events.pupil) == (full.display, full.pupil)


def test_decoded_lines_refuse_a_partial_read():
    stream = eyelink._DecodedLines(["a\n", "b\n"], "x.asc")
    assert stream.read() == "a\nb\n"
    assert stream.read(0) == ""
    with pytest.raises(io.UnsupportedOperation):
        stream.read(1)
