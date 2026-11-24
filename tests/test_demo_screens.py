"""The bundled demo's screens: old links and files, and the builder's draw lists."""

from __future__ import annotations

import json

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from scanpath_studio.update_sample_data import (
    DrawnImage,
    DrawnScreen,
    compose_screen,
    match_screens,
    read_draw_list,
)
from tests.conftest import APP_SCRIPT

# l37_273's reading of 2_2_2_Adv: 7 fixations on its question preview, then
# the paragraph's 92, numbered 8-99 over the whole trial.
READER, TRIAL = "l37_273", "l37_273_2_2_2_Adv"


def _open(**params: str) -> AppTest:
    """The app opened on a link, and run once more: the link stays in the
    address, and a second run must not move what the first one restored."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["ui"] = "full"
    for key, value in params.items():
        at.query_params[key] = value
    at.run()
    at.run()
    assert not at.exception, at.exception
    return at


def test_a_demo_link_naming_no_screen_opens_the_paragraph_on_the_same_fixations():
    """A link Share wrote for the demo before it had several screens names no
    screen; it meant the paragraph, and its window counted the paragraph's
    fixations alone."""
    at = _open(source="demo", participant=READER, trial_id=TRIAL, fix_range="3,10")
    assert at.session_state["single_screen_id"] == "Paragraph"
    assert tuple(at.session_state["single_fix_range"]) == (10, 17)


# l7_183's reading of the same paragraph: 11 question-preview fixations first.
READER_B, TRIAL_B = "l7_183", "l7_183_2_2_2_Adv"


def test_a_demo_compare_link_naming_no_screens_opens_both_paragraphs():
    at = _open(
        source="demo",
        participant=READER,
        trial_id=TRIAL,
        fix_range="3,10",
        compare=f"{READER_B}:{TRIAL_B}",
        cmp_b_fix_range="3,10",
    )
    assert at.session_state["single_screen_id"] == "Paragraph"
    assert tuple(at.session_state["single_fix_range"]) == (10, 17)
    assert at.session_state["single_compare_screen_id"] == "Paragraph"
    assert tuple(at.session_state["single_compare_fix_range"]) == (14, 21)


def test_a_compare_link_naming_no_dataset_opens_b_like_a():
    """With no `source`, the link opens the demo, B in A's dataset with it."""
    at = _open(participant=READER, trial_id=TRIAL, compare=f"{READER_B}:{TRIAL_B}")
    assert at.session_state["single_screen_id"] == "Paragraph"
    assert at.session_state["single_compare_screen_id"] == "Paragraph"


def _restore_file(config: dict) -> AppTest:
    from tests.wire_golden import _Upload

    at = _open()
    at.session_state["plot_config_upload"] = _Upload(json.dumps(config).encode())
    at.run()
    at.run()  # the rerun the next click would cause
    assert not at.exception, at.exception
    return at


def test_a_demo_settings_file_naming_no_screens_opens_both_paragraphs():
    from tests.wire_golden import write_settings_file

    config = write_settings_file(
        f"source=demo&participant={READER}&trial_id={TRIAL}&screen=Paragraph"
        f"&compare={READER_B}:{TRIAL_B}&cmp_screen=Paragraph"
    )
    selection = config["selection"]
    compare = selection["compare"]
    assert compare["screen_id"] == selection["screen_id"] == "Paragraph"
    # The file as a release whose demo held only paragraphs wrote it.
    for saved in (selection, compare):
        del saved["screen_id"]
        saved["fixation_window"] = [3, 10]
    at = _restore_file(config)
    assert at.session_state["single_screen_id"] == "Paragraph"
    assert tuple(at.session_state["single_fix_range"]) == (10, 17)
    assert at.session_state["single_compare_screen_id"] == "Paragraph"
    assert tuple(at.session_state["single_compare_fix_range"]) == (14, 21)


def test_a_demo_link_naming_a_screen_opens_that_screen_as_written():
    at = _open(
        source="demo",
        participant=READER,
        trial_id=TRIAL,
        screen="Questions",
        fix_range="100,105",
    )
    assert at.session_state["single_screen_id"] == "Questions"
    assert tuple(at.session_state["single_fix_range"]) == (100, 105)


def _draw_list(tmp_path, text: str):
    path = tmp_path / "VC_1.vcl"
    path.write_text(text)
    return read_draw_list(path)


def test_a_draw_list_reads_each_screen_and_its_images(tmp_path):
    screens = _draw_list(
        tmp_path,
        "0 CLEAR 255 255 255\n"
        "0 IMGLOAD TOP_LEFT  ../../runtime/images/title.png 368 186 1824 228\n"
        "-1552 CLEAR 255 255 255\n"
        "-1552 IMGLOAD TOP_LEFT ..\\..\\runtime\\images\\target.png 368 186\n"
        "-25822 CLEAR 0 0 0\n",
    )
    assert [(s.onset_ms, s.background) for s in screens] == [
        (0, (255, 255, 255)),
        (1552, (255, 255, 255)),
        (25822, (0, 0, 0)),
    ]
    assert screens[0].images == [DrawnImage("title.png", 368, 186, (1824, 228))]
    assert screens[1].images == [DrawnImage("target.png", 368, 186, None)]
    assert screens[2].images == []


def test_a_draw_command_it_cannot_draw_stops_the_build(tmp_path):
    with pytest.raises(ValueError, match="unsupported draw command"):
        _draw_list(tmp_path, "0 CLEAR 255 255 255\n0 DRAW_TEXT 10 10 hello\n")


def _screens(*onsets: int) -> list[DrawnScreen]:
    return [DrawnScreen(onset, (255, 255, 255)) for onset in onsets]


def test_each_part_lands_on_the_screen_shown_when_its_period_began():
    # The draw list counts from its first screen; the report in tracker time.
    screens = _screens(0, 1552, 2919, 4254, 5022)
    start = 1_391_690
    onsets = {
        "Title": start + 2,
        "Question_Preview": start + 2917,
        "Paragraph": start + 5019,
    }
    matched = match_screens(onsets, screens, reading="r")
    assert {part: s.onset_ms for part, s in matched.items()} == {
        "Title": 0,
        "Question_Preview": 2919,
        "Paragraph": 5022,
    }


def test_a_part_with_no_screen_at_its_onset_stops_the_build():
    screens = _screens(0, 2919)
    onsets = {"Title": 1000, "Paragraph": 1000 + 5022}
    with pytest.raises(ValueError, match="no screen of its own"):
        match_screens(onsets, screens, reading="r")


def test_a_screen_is_drawn_over_its_background_and_cut_to_its_images(tmp_path):
    ink = Image.new("RGBA", (4, 2), (0, 0, 0, 0))
    ink.putpixel((1, 0), (0, 0, 0, 255))
    ink.save(tmp_path / "word.png")
    Image.new("RGBA", (3, 3), (0, 0, 0, 255)).save(tmp_path / "hidden.png")
    screen = DrawnScreen(
        0,
        (255, 255, 255),
        [
            DrawnImage("word.png", 10, 20, (4, 2)),
            DrawnImage("word.png", 20, 25, None),
            DrawnImage("hidden.png", -1000, -1000, None),
        ],
    )
    image, x, y = compose_screen(screen, tmp_path)
    assert (x, y, image.size) == (10, 20, (14, 7))
    # Transparent pixels show the background; the ink stays where it was drawn.
    assert image.getpixel((0, 0)) == (255, 255, 255)
    assert image.getpixel((1, 0)) == (0, 0, 0)
    assert image.getpixel((11, 5)) == (0, 0, 0)


def test_an_image_drawn_at_another_size_stops_the_build(tmp_path):
    Image.new("RGBA", (4, 2)).save(tmp_path / "word.png")
    screen = DrawnScreen(0, (255, 255, 255), [DrawnImage("word.png", 0, 0, (8, 4))])
    with pytest.raises(ValueError, match="draws it at 8x4"):
        compose_screen(screen, tmp_path)
