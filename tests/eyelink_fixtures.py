"""A small EyeLink experiment on disk, shared by the EDF-import tests.

``write_experiment`` lays out one session the way Experiment Builder does:
``exp/results/p01/`` holds the ASC, ``aoi/IA_*.ias`` (interest areas) and
``graphics/VC_*.vcl`` (draw lists); ``exp/runtime/images/`` holds the pictures
the draw lists load.  The ASC is written out line by line so a reader can follow
it against ``EXPECTED``, which is traced by hand from those lines.

Two readings.  Trial 1 shows a text screen (three words) and then a question
screen with no words; trial 2 shows one text screen (two words).  Times are
tracker milliseconds; ``MSG t -13 ...`` happened at ``t + 13``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

SESSION = "p01"
DISPLAY = (1280, 1024)

# EyeLink's own line formats (EFIX: eye, start, end, duration, avg x, avg y, pupil).
_COMMON_HEADER = [
    "** CONVERTED FROM p01.edf using edf2asc version 4.2.1",
    "** DATE: Thu May  8 00:30:08 2014",
    "** TYPE: EDF_FILE BINARY EVENT SAMPLE TAGGED",
]

# The two draw lists / interest-area files each screen loads, then its fixations.
_RIGHT_TRIAL_1 = [
    "MSG\t990\tTRIALID 1",
    "START\t990 \tRIGHT\tEVENTS",
    "MSG\t1000\t-13 !V DRAW_LIST graphics/VC_1.vcl",
    "MSG\t1000\t-13 !V IAREA FILE aoi/IA_1.ias",
    "EFIX\tR\t1020\t1219\t200\t120.5\t200.0\t1000",
    "ESACC\tR\t1220\t1229\t10\t120.5\t200.0\t250.5\t201.0\t1.50\t300",
    "EFIX\tR\t1230\t1479\t250\t250.5\t201.0\t1010",
    "ESACC\tR\t1480\t1489\t10\t250.5\t201.0\t350.0\t199.5\t1.20\t250",
    "EFIX\tR\t1490\t1689\t200\t350.0\t199.5\t990",
    "MSG\t1700\t-13 !V DRAW_LIST graphics/VC_3.vcl",
    "EFIX\tR\t1720\t1919\t200\t500.0\t600.0\t980",
    "END\t2000 \tEVENTS\tRES\t80.26\t60.44",
    "MSG\t2010\t!V TRIAL_VAR condition Adv",
    "MSG\t2010\t!V TRIAL_VAR item 1",
    "MSG\t2010\t!V TRIAL_VAR Session_Name_ p01",
    "MSG\t2020\tTRIAL_RESULT 0",
]
_RIGHT_TRIAL_2 = [
    "MSG\t3000\tTRIALID 2",
    "START\t3010 \tRIGHT\tEVENTS",
    "MSG\t3020\t-13 !V DRAW_LIST graphics/VC_2.vcl",
    "MSG\t3020\t-13 !V IAREA FILE aoi/IA_2.ias",
    "EFIX\tR\t3050\t3249\t200\t160.0\t220.0\t1000",
    "EFIX\tR\t3260\t3409\t150\t340.0\t225.0\t1000",
    "END\t3500 \tEVENTS\tRES\t80.26\t60.44",
    "MSG\t3510\t!V TRIAL_VAR condition Ele",
    "MSG\t3510\t!V TRIAL_VAR item 2",
    "MSG\t3510\t!V TRIAL_VAR Session_Name_ p01",
    "MSG\t3520\tTRIAL_RESULT 0",
]
# The left eye of a binocular recording: same screens, its own positions.
_LEFT_TRIAL_1 = [
    "EFIX\tL\t1022\t1221\t200\t118.0\t203.0\t1100",
    "EFIX\tL\t1232\t1481\t250\t248.0\t204.0\t1110",
]
# A reading that never reached its END line (the experiment was aborted).
_ABORTED_TRIAL = [
    "MSG\t4000\tTRIALID 3",
    "START\t4010 \tRIGHT\tEVENTS",
    "MSG\t4020\t-13 !V DRAW_LIST graphics/VC_2.vcl",
    "EFIX\tR\t4050\t4249\t200\t170.0\t230.0\t1000",
]

_IAS = {
    "IA_1.ias": [
        (1, 100, 150, 200, 250, "The"),
        (2, 200, 150, 300, 250, "cat"),
        (3, 300, 150, 400, 250, "sat"),
    ],
    "IA_2.ias": [
        (1, 100, 150, 250, 250, "Dogs"),
        (2, 250, 150, 400, 250, "bark"),
    ],
}

_BOM = "\ufeff"
_VCL = {
    "VC_1.vcl": [
        f"{_BOM}0 CLEAR 255 255 255",
        "0 IMGLOAD TOP_LEFT ../../runtime/images/bg.png 0 0",
        "0 IMGLOAD TOP_LEFT ../../runtime/images/text1.png 100 150 300 100",
    ],
    "VC_2.vcl": [
        f"{_BOM}0 CLEAR 255 255 255",
        "0 IMGLOAD TOP_LEFT ../../runtime/images/bg.png 0 0",
        "0 IMGLOAD TOP_LEFT ../../runtime/images/text2.png 100 150 300 100",
    ],
    "VC_3.vcl": [
        f"{_BOM}0 CLEAR 200 200 200",
        "0 IMGLOAD TOP_LEFT ../../runtime/images/bg.png 0 0",
    ],
}

# Pictures the draw lists load: (name, size, colour).
_IMAGES = [
    ("bg.png", DISPLAY, (255, 255, 255)),
    ("text1.png", (300, 100), (230, 40, 40)),
    ("text2.png", (300, 100), (40, 40, 230)),
]


def _fix(eye, onset, offset, duration, x, y) -> dict:
    return {
        "eye": eye,
        "onset": onset,
        "offset": offset,
        "duration_ms": duration,
        "x": x,
        "y": y,
    }


_R1 = [
    _fix("R", 1020, 1219, 200, 120.5, 200.0),
    _fix("R", 1230, 1479, 250, 250.5, 201.0),
    _fix("R", 1490, 1689, 200, 350.0, 199.5),
]
_R1_QUESTION = [_fix("R", 1720, 1919, 200, 500.0, 600.0)]
_R2 = [
    _fix("R", 3050, 3249, 200, 160.0, 220.0),
    _fix("R", 3260, 3409, 150, 340.0, 225.0),
]
_LEFT = [
    _fix("L", 1022, 1221, 200, 118.0, 203.0),
    _fix("L", 1232, 1481, 250, 248.0, 204.0),
]
_ABORTED = [_fix("R", 4050, 4249, 200, 170.0, 230.0)]

EXPECTED = {
    "display": DISPLAY,
    "session": SESSION,
    # Right-eye fixations of the two complete readings, in file order.
    "fixations": _R1 + _R1_QUESTION + _R2,
    "fixations_left": _LEFT,
    "fixations_aborted": _ABORTED,
    # START / END line times of each reading.
    "blocks": [(990, 2000), (3010, 3500)],
    "block_aborted": (4010, None),
    "trials": {
        1: {
            "start": 990,
            "end": 2000,
            "vars": {"condition": "Adv", "item": "1", "Session_Name_": "p01"},
            # Each display: the time its DRAW_LIST message was logged (message
            # time minus its offset), the time the draw list's first display
            # begins (its offset-0 lines, so the same instant; a later display
            # of a list has a negative offset and begins that many ms after),
            # its draw list, interest-area file and fixations.
            "screens": [
                {
                    "drawn": 1013,
                    "begin": 1013,
                    "vcl": "graphics/VC_1.vcl",
                    "ias": "aoi/IA_1.ias",
                    "fixations": _R1,
                },
                {
                    "drawn": 1713,
                    "begin": 1713,
                    "vcl": "graphics/VC_3.vcl",
                    "ias": None,
                    "fixations": _R1_QUESTION,
                },
            ],
        },
        2: {
            "start": 3010,
            "end": 3500,
            "vars": {"condition": "Ele", "item": "2", "Session_Name_": "p01"},
            "screens": [
                {
                    "drawn": 3033,
                    "begin": 3033,
                    "vcl": "graphics/VC_2.vcl",
                    "ias": "aoi/IA_2.ias",
                    "fixations": _R2,
                },
            ],
        },
    },
    # Interest-area boxes as (word_id, left, top, right, bottom, text).
    "words": _IAS,
    "images": {name: size for name, size, _ in _IMAGES},
}


def _asc_text(*, binocular: bool, aborted_trial: bool, latin1: bool) -> str:
    eyes = "LEFT\tRIGHT" if binocular else "RIGHT"
    header = [_BOM + _COMMON_HEADER[0], *_COMMON_HEADER[1:]]
    lines = [
        *header,
        f"EVENTS\tGAZE\t{eyes}\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2",
        "MSG\t500\tDISPLAY_COORDS 0 0 1279 1023",
    ]
    if latin1:
        # What a non-ASCII message looks like in OneStop's latin-1 ASC files.
        lines.append("MSG\t600\tparticipant: Renée")
    trial_1 = list(_RIGHT_TRIAL_1)
    if binocular:
        trial_1.insert(4, _LEFT_TRIAL_1[0])
        trial_1.insert(7, _LEFT_TRIAL_1[1])
        trial_1[1] = "START\t990 \tLEFT\tRIGHT\tEVENTS"
    lines += trial_1 + _RIGHT_TRIAL_2
    if aborted_trial:
        lines += _ABORTED_TRIAL
    return "\n".join(lines) + "\n"


def write_experiment(
    root: Path,
    *,
    binocular: bool = False,
    with_session_files: bool = True,
    aborted_trial: bool = False,
    latin1: bool = False,
) -> Path:
    """Write the experiment under ``root`` and return the ``.asc`` path,
    ``root/exp/results/p01/p01.asc``.

    ``with_session_files=False`` writes the ASC alone (no ``aoi/``,
    ``graphics/`` or ``runtime/images/``).
    """
    session = Path(root) / "exp" / "results" / SESSION
    session.mkdir(parents=True, exist_ok=True)
    asc = session / f"{SESSION}.asc"
    text = _asc_text(binocular=binocular, aborted_trial=aborted_trial, latin1=latin1)
    if latin1:
        # The BOM stays UTF-8 bytes while the body is latin-1, as in OneStop's files.
        body = text.removeprefix(_BOM).encode("latin-1")
        asc.write_bytes(_BOM.encode("utf-8") + body)
    else:
        asc.write_text(text, encoding="utf-8")
    if not with_session_files:
        return asc
    (session / "aoi").mkdir(exist_ok=True)
    for name, boxes in _IAS.items():
        rows = [
            f"0 RECTANGLE\t{i}\t{left}\t{top}\t{right}\t{bottom}\t{word}"
            for i, left, top, right, bottom, word in boxes
        ]
        (session / "aoi" / name).write_text(
            _BOM + "\n".join(rows) + "\n", encoding="utf-8"
        )
    (session / "graphics").mkdir(exist_ok=True)
    for name, rows in _VCL.items():
        (session / "graphics" / name).write_text(
            "\n".join(rows) + "\n", encoding="utf-8"
        )
    images = Path(root) / "exp" / "runtime" / "images"
    images.mkdir(parents=True, exist_ok=True)
    for name, size, colour in _IMAGES:
        Image.new("RGB", size, colour).save(images / name)
    return asc
