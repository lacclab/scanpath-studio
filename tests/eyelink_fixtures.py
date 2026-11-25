"""A small EyeLink experiment on disk, shared by the EDF-import tests.

``write_experiment`` lays out one session the way Experiment Builder does:
``exp/results/p01/`` holds the ASC, ``aoi/IA_*.ias`` (interest areas) and
``graphics/VC_*.vcl`` (draw lists); ``exp/runtime/images/`` holds the pictures
the draw lists load.  The ASC is written out line by line so a reader can follow
it against ``EXPECTED``, which is traced by hand from those lines.

Two readings.  Trial 1 shows a text screen (three words) and then a question
screen with no words; trial 2 shows one text screen (two words).  Times are
tracker milliseconds; ``MSG t -13 ...`` happened at ``t + 13``.

Two optional readings follow them: an aborted trial 3 (no ``END``, no
``TRIAL_RESULT``) and, as OneStop logs every reading, a trial 4 whose single
``DRAW_LIST`` / ``IAREA FILE`` pair holds three displays and two interest-area
groups at negative offsets.  ``inline=True`` logs every display and interest
area as ``!V CLEAR`` / ``!V IMGLOAD`` / ``!V IAREA RECTANGLE`` messages instead
of ``.vcl`` / ``.ias`` files.

``samples=True`` records gaze samples too (``SAMPLES`` lines), a few ticks
of the two complete readings at the times in ``_SAMPLES``: some on a screen,
some before a trial's first screen, one the tracker lost.

``older_layout=True`` adds trial 5, logged as OneStop's older experiments log
some readings: the ``IAREA FILE`` message is timed 10 ms before the display its
``.vcl`` places, so each interest-area group is that far from its display while
the groups' own offsets agree with the draw list's.
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

# One reading over three displays, logged OneStop's way: TRIALID 70 ms before
# START, one draw list (displays at offsets 0, -6620 and -9204, so at 5120,
# 11740 and 14324) and one interest-area file (groups at offsets 0 and -6623,
# so at 5120 and 11743, 3 ms after the second display as in real files).  The
# second fixation starts 5 ms before the second display.
_MULTI_DISPLAY_TRIAL = [
    "MSG\t5000\tTRIALID 4",
    "START\t5070 \tRIGHT\tEVENTS",
    "MSG\t5100\t-20 !V DRAW_LIST graphics/VC_4.vcl",
    "MSG\t5100\t-20 !V IAREA FILE aoi/IA_4.ias",
    "EFIX\tR\t5150\t5349\t200\t400.0\t200.0\t1000",
    "EFIX\tR\t11735\t11934\t200\t420.0\t205.0\t1000",
    "EFIX\tR\t11950\t12149\t200\t380.0\t210.0\t1000",
    "EFIX\tR\t14400\t14599\t200\t900.0\t700.0\t1000",
    "END\t15000 \tEVENTS\tRES\t80.26\t60.44",
    "MSG\t15010\t!V TRIAL_VAR condition Adv",
    "MSG\t15010\t!V TRIAL_VAR item 4",
    "MSG\t15010\t!V TRIAL_VAR Session_Name_ p01",
    "MSG\t15020\tTRIAL_RESULT 0",
]

# A reading laid out as in OneStop's older experiments (l10_202, trial 5):
# the draw list is logged with the fixation target, at 20083, and its displays
# begin at 20083 (target), 21044 (paragraph), 23225 (question target) and
# 25426 (question).  The IAREA FILE message is logged with DISPLAY_PARAG at
# 21034, 10 ms before the paragraph display, so the groups at offsets 0 and
# -4383 fall at 21034 and 25417: 10 and 9 ms before their displays.
_OLDER_LAYOUT_TRIAL = [
    "MSG\t20000\tTRIALID 5",
    "START\t20016 \tRIGHT\tEVENTS",
    "MSG\t20071\t-12 DISPLAY_PARAG_TARGET",
    "MSG\t20071\t-12 !V DRAW_LIST graphics/VC_5.vcl",
    "MSG\t21023\t-11 DISPLAY_PARAG",
    "MSG\t21023\t-11 !V IAREA FILE aoi/IA_5.ias",
    "EFIX\tR\t21100\t21299\t200\t150.0\t200.0\t1000",
    "MSG\t23205\t-11 DISPLAY_Q_TARGET",
    "MSG\t25406\t-11 DISPLAY_Q",
    "EFIX\tR\t25500\t25699\t200\t160.0\t420.0\t1000",
    "END\t26000 \tEVENTS\tRES\t80.26\t60.44",
    "MSG\t26010\t!V TRIAL_VAR condition Ele",
    "MSG\t26010\t!V TRIAL_VAR item 5",
    "MSG\t26010\t!V TRIAL_VAR Session_Name_ p01",
    "MSG\t26020\tTRIAL_RESULT 0",
]

# Right-eye gaze samples of the two complete readings: (time, x, y, pupil).
# 995 and 3020 fall inside a trial but before its first screen; 2500 after
# trial 1's END and before trial 2's TRIALID; 1800 is a tick the tracker lost
# (EyeLink writes ``.`` positions and a 0 pupil).
_SAMPLES = [
    (995, 50.0, 60.0, 1200.0),
    (1100, 110.0, 210.0, 1300.0),
    (1500, 260.0, 205.0, 1310.0),
    (1800, None, None, 0.0),
    (1990, 505.0, 601.0, 1290.0),
    (2500, 600.0, 610.0, 1240.0),
    (3020, 70.0, 80.0, 1250.0),
    (3100, 165.0, 221.0, 1280.0),
    (3400, 345.0, 226.0, 1270.0),
]
# The left eye of a binocular recording sees each tick this far off.
_LEFT_EYE_SHIFT = (-2.0, 3.0, 100.0)


def _sample_line(time, x, y, pupil, *, binocular: bool) -> str:
    def eye(dx: float, dy: float, dp: float) -> list[str]:
        if x is None:
            return [".", ".", f"{pupil:.1f}"]
        return [f"{x + dx:.1f}", f"{y + dy:.1f}", f"{pupil + dp:.1f}"]

    fields = [str(time)]
    if binocular:
        fields += eye(*_LEFT_EYE_SHIFT)
    fields += eye(0.0, 0.0, 0.0)
    fields.append("....." if binocular else "...")
    return "\t".join(fields)


def _with_samples(lines: list[str], *, binocular: bool) -> list[str]:
    """``lines`` with each sample line placed before the first line written
    after its tick."""
    out = list(lines)
    for time, x, y, pupil in _SAMPLES:
        at = next(
            (
                i
                for i, line in enumerate(out)
                if not line.startswith("**")
                and line.split("\t")[0] in ("MSG", "START", "END", "EFIX", "ESACC")
                and _line_time(line) > time
            ),
            len(out),
        )
        out.insert(at, _sample_line(time, x, y, pupil, binocular=binocular))
    return out


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
# Interest-area files with several groups, by offset.
_IAS_GROUPS = {
    "IA_4.ias": {
        0: [
            (1, 358, 154, 453, 261, "Food"),
            (2, 453, 154, 643, 261, "Shortages"),
        ],
        -6623: [
            (1, 358, 153, 548, 264, "According"),
            (2, 548, 153, 605, 264, "to"),
        ],
    },
    "IA_5.ias": {
        0: [
            (1, 100, 150, 180, 250, "Rising"),
            (2, 180, 150, 260, 250, "seas"),
        ],
        -4383: [
            (1, 100, 370, 160, 470, "Why"),
            (2, 160, 370, 240, 470, "now?"),
        ],
    },
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
    # As Experiment Builder writes them: two spaces before a sized image's path,
    # and image paths relative to the session folder, not the .vcl's.
    "VC_4.vcl": [
        f"{_BOM}0 CLEAR 255 255 255",
        "0 IMGLOAD TOP_LEFT ../../runtime/images/bg.png 0 0",
        "0 IMGLOAD TOP_LEFT  ../../runtime/images/text1.png 100 150 300 100",
        "-6620 CLEAR 255 255 255",
        "-6620 IMGLOAD TOP_LEFT ../../runtime/images/bg.png 0 0",
        "-6620 IMGLOAD TOP_LEFT ../../runtime/images/text2.png 100 150",
        "-9204 CLEAR 200 200 200",
    ],
    "VC_5.vcl": [
        f"{_BOM}0 CLEAR 255 255 255",
        "-961 CLEAR 255 255 255",
        "-961 IMGLOAD TOP_LEFT  ../../runtime/images/text1.png 100 150 300 100",
        "-3142 CLEAR 200 200 200",
        "-5343 CLEAR 255 255 255",
        "-5343 IMGLOAD TOP_LEFT ../../runtime/images/text2.png 100 370",
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


def _sample(trial_id, screen, start, time, x, y, pupil, eye) -> dict:
    lost = x is None
    return {
        "trial_id": trial_id,
        "screen_id": f"screen_{screen}",
        "screen_index": screen,
        "x": float("nan") if lost else x,
        "y": float("nan") if lost else y,
        "timestamp_ms": time - start,
        "pupil": float("nan") if lost else pupil,
        "eye": eye,
    }


# Where each kept sample lands: (time, trial, screen, the trial's START).
_SAMPLE_PLACES = {
    1100: ("1", 1, 990),
    1500: ("1", 1, 990),
    1800: ("1", 2, 990),
    1990: ("1", 2, 990),
    3100: ("2", 1, 3010),
    3400: ("2", 1, 3010),
}


def _expected_samples(eye: str) -> list[dict]:
    rows = []
    for time, x, y, pupil in _SAMPLES:
        if time not in _SAMPLE_PLACES:
            continue
        if eye == "L" and x is not None:
            dx, dy, dp = _LEFT_EYE_SHIFT
            x, y, pupil = x + dx, y + dy, pupil + dp
        trial_id, screen, start = _SAMPLE_PLACES[time]
        rows.append(_sample(trial_id, screen, start, time, x, y, pupil, eye))
    return rows


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
_M1 = [
    _fix("R", 5150, 5349, 200, 400.0, 200.0),
    _fix("R", 11735, 11934, 200, 420.0, 205.0),
]
_M2 = [_fix("R", 11950, 12149, 200, 380.0, 210.0)]
_M3 = [_fix("R", 14400, 14599, 200, 900.0, 700.0)]
_O2 = [_fix("R", 21100, 21299, 200, 150.0, 200.0)]
_O4 = [_fix("R", 25500, 25699, 200, 160.0, 420.0)]

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
    # Each reading: its TRIALID time (begin), the START line of its recording
    # (start) and its TRIAL_RESULT time (end).
    "trials": {
        1: {
            "begin": 990,
            "start": 990,
            "end": 2020,
            "vars": {"condition": "Adv", "item": "1", "Session_Name_": "p01"},
            # Each display: the time its DRAW_LIST message was logged (message
            # time minus its offset), the time the display begins (its draw
            # list's offset-0 lines, so the same instant; a later display of a
            # list has a negative offset and begins that many ms after), the
            # time it ends (the next display, or the trial's end), its draw
            # list, interest-area file, words and fixations.
            "screens": [
                {
                    "drawn": 1013,
                    "begin": 1013,
                    "end": 1713,
                    "vcl": "graphics/VC_1.vcl",
                    "ias": "aoi/IA_1.ias",
                    "words": _IAS["IA_1.ias"],
                    "fixations": _R1,
                },
                {
                    "drawn": 1713,
                    "begin": 1713,
                    "end": 2020,
                    "vcl": "graphics/VC_3.vcl",
                    "ias": None,
                    "words": [],
                    "fixations": _R1_QUESTION,
                },
            ],
        },
        2: {
            "begin": 3000,
            "start": 3010,
            "end": 3520,
            "vars": {"condition": "Ele", "item": "2", "Session_Name_": "p01"},
            "screens": [
                {
                    "drawn": 3033,
                    "begin": 3033,
                    "end": 3520,
                    "vcl": "graphics/VC_2.vcl",
                    "ias": "aoi/IA_2.ias",
                    "words": _IAS["IA_2.ias"],
                    "fixations": _R2,
                },
            ],
        },
    },
    # The aborted trial 3 ends at the next TRIALID (trial 4's, with
    # ``multi_display``), else at the file's last event (its EFIX's end).
    "trial_aborted": {
        "trial_id": "3",
        "begin": 4000,
        "start": 4010,
        "end_at_next_trialid": 5000,
        "end_at_file_end": 4249,
    },
    "multi_display_trials": {
        4: {
            "begin": 5000,
            "start": 5070,
            "end": 15020,
            "vars": {"condition": "Adv", "item": "4", "Session_Name_": "p01"},
            "screens": [
                {
                    "drawn": 5120,
                    "begin": 5120,
                    "end": 11740,
                    "vcl": "graphics/VC_4.vcl",
                    "ias": "aoi/IA_4.ias",
                    "words": _IAS_GROUPS["IA_4.ias"][0],
                    "fixations": _M1,
                },
                {
                    "drawn": 5120,
                    "begin": 11740,
                    "end": 14324,
                    "vcl": "graphics/VC_4.vcl",
                    "ias": "aoi/IA_4.ias",
                    "words": _IAS_GROUPS["IA_4.ias"][-6623],
                    "fixations": _M2,
                },
                {
                    "drawn": 5120,
                    "begin": 14324,
                    "end": 15020,
                    "vcl": "graphics/VC_4.vcl",
                    "ias": None,
                    "words": [],
                    "fixations": _M3,
                },
            ],
        },
    },
    # Each group binds to the display it was shown with, 10 and 9 ms away.
    "older_layout_trials": {
        5: {
            "begin": 20000,
            "start": 20016,
            "end": 26020,
            "vars": {"condition": "Ele", "item": "5", "Session_Name_": "p01"},
            "screens": [
                {
                    "drawn": 20083,
                    "begin": 20083,
                    "end": 21044,
                    "vcl": "graphics/VC_5.vcl",
                    "ias": None,
                    "words": [],
                    "fixations": [],
                },
                {
                    "drawn": 20083,
                    "begin": 21044,
                    "end": 23225,
                    "vcl": "graphics/VC_5.vcl",
                    "ias": "aoi/IA_5.ias",
                    "words": _IAS_GROUPS["IA_5.ias"][0],
                    "fixations": _O2,
                },
                {
                    "drawn": 20083,
                    "begin": 23225,
                    "end": 25426,
                    "vcl": "graphics/VC_5.vcl",
                    "ias": None,
                    "words": [],
                    "fixations": [],
                },
                {
                    "drawn": 20083,
                    "begin": 25426,
                    "end": 26020,
                    "vcl": "graphics/VC_5.vcl",
                    "ias": "aoi/IA_5.ias",
                    "words": _IAS_GROUPS["IA_5.ias"][-4383],
                    "fixations": _O4,
                },
            ],
        },
    },
    # The right-eye samples kept: those on a screen, on the fixations' clock.
    "samples": _expected_samples("R"),
    "samples_left": _expected_samples("L"),
    # Sample ticks on no screen: before a trial's first screen, or between
    # one trial's END and the next TRIALID.
    "samples_between_screens": [995, 2500, 3020],
    # Interest-area boxes as (word_id, left, top, right, bottom, text).
    "words": _IAS,
    "images": {name: size for name, size, _ in _IMAGES},
}


def _ias_rows(name: str) -> list[tuple[int, tuple]]:
    """An interest-area file's boxes, each with its offset."""
    if name in _IAS:
        return [(0, box) for box in _IAS[name]]
    return [
        (offset, box) for offset, boxes in _IAS_GROUPS[name].items() for box in boxes
    ]


def _line_time(line: str) -> int:
    """When a line was written: a message's or START / END line's own time, an
    event's end."""
    fields = line.split("\t")
    if fields[0] in ("EFIX", "ESACC"):
        return int(fields[3])
    return int(fields[1])


def _inline(lines: list[str]) -> list[str]:
    """``lines`` with each DRAW_LIST / IAREA FILE message replaced by the
    ``!V`` messages it stands for, logged at their own times."""
    out = []
    for line in lines:
        fields = line.split("\t")
        if fields[0] != "MSG" or not (
            " !V DRAW_LIST " in fields[2] or " !V IAREA FILE " in fields[2]
        ):
            out.append(line)
            continue
        offset, command = fields[2].split(" ", 1)
        logged = int(fields[1]) - int(offset)
        if command.startswith("!V DRAW_LIST "):
            for row in _VCL[Path(command.split()[-1]).name]:
                row_offset, draw = row.removeprefix(_BOM).split(" ", 1)
                out.append(f"MSG\t{logged - int(row_offset)}\t!V {draw}")
        elif command.startswith("!V IAREA FILE "):
            for row_offset, box in _ias_rows(Path(command.split()[-1]).name):
                word_id, left, top, right, bottom, word = box
                out.append(
                    f"MSG\t{logged - row_offset}\t!V IAREA RECTANGLE "
                    f"{word_id} {left} {top} {right} {bottom} {word}"
                )
        else:
            out.append(line)
    return sorted(out, key=_line_time)


def _asc_text(
    *,
    binocular: bool,
    aborted_trial: bool,
    latin1: bool,
    multi_display: bool,
    inline: bool,
    older_layout: bool,
    samples: bool,
    pupil: str,
) -> str:
    eyes = "LEFT\tRIGHT" if binocular else "RIGHT"
    header = [_BOM + _COMMON_HEADER[0], *_COMMON_HEADER[1:]]
    lines = [
        *header,
        f"EVENTS\tGAZE\t{eyes}\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2",
        "MSG\t500\tDISPLAY_COORDS 0 0 1279 1023",
    ]
    if samples:
        lines += [
            f"SAMPLES\tGAZE\t{eyes}\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2",
            f"PUPIL\t{pupil}",
        ]
    if latin1:
        # What a non-ASCII message looks like in OneStop's latin-1 ASC files.
        lines.append("MSG\t600\tparticipant: Renée")
    trial_1 = list(_RIGHT_TRIAL_1)
    if binocular:
        trial_1.insert(4, _LEFT_TRIAL_1[0])
        trial_1.insert(7, _LEFT_TRIAL_1[1])
        trial_1[1] = "START\t990 \tLEFT\tRIGHT\tEVENTS"
    trial_2 = list(_RIGHT_TRIAL_2)
    if binocular:
        # Every block of a binocular recording tracks both eyes.
        trial_2[1] = "START\t3010 \tLEFT\tRIGHT\tEVENTS"
    trials = trial_1 + trial_2
    if aborted_trial:
        trials += _ABORTED_TRIAL
    if multi_display:
        trials += _MULTI_DISPLAY_TRIAL
    if older_layout:
        trials += _OLDER_LAYOUT_TRIAL
    trials = _inline(trials) if inline else trials
    if samples:
        trials = [
            line.replace("\tEVENTS", "\tSAMPLES\tEVENTS", 1)
            if line.startswith("START")
            else line
            for line in trials
        ]
        trials = _with_samples(trials, binocular=binocular)
    lines += trials
    return "\n".join(lines) + "\n"


def write_experiment(
    root: Path,
    *,
    binocular: bool = False,
    with_session_files: bool = True,
    aborted_trial: bool = False,
    latin1: bool = False,
    multi_display: bool = False,
    inline: bool = False,
    older_layout: bool = False,
    samples: bool = False,
    pupil: str = "AREA",
) -> Path:
    """Write the experiment under ``root`` and return the ``.asc`` path,
    ``root/exp/results/p01/p01.asc``.

    ``with_session_files=False`` writes the ASC alone (no ``aoi/``,
    ``graphics/`` or ``runtime/images/``); ``inline=True`` writes no ``aoi/``
    or ``graphics/``, since the ASC's messages carry what they hold.
    """
    session = Path(root) / "exp" / "results" / SESSION
    session.mkdir(parents=True, exist_ok=True)
    asc = session / f"{SESSION}.asc"
    text = _asc_text(
        binocular=binocular,
        aborted_trial=aborted_trial,
        latin1=latin1,
        multi_display=multi_display,
        inline=inline,
        older_layout=older_layout,
        samples=samples,
        pupil=pupil,
    )
    if latin1:
        # The BOM stays UTF-8 bytes while the body is latin-1, as in OneStop's files.
        body = text.removeprefix(_BOM).encode("latin-1")
        asc.write_bytes(_BOM.encode("utf-8") + body)
    else:
        asc.write_text(text, encoding="utf-8")
    if not with_session_files:
        return asc
    if not inline:
        _write_draw_lists(session)
    images = Path(root) / "exp" / "runtime" / "images"
    images.mkdir(parents=True, exist_ok=True)
    for name, size, colour in _IMAGES:
        Image.new("RGB", size, colour).save(images / name)
    return asc


def _write_draw_lists(session: Path) -> None:
    (session / "aoi").mkdir(exist_ok=True)
    for name in [*_IAS, *_IAS_GROUPS]:
        rows = [
            f"{offset} RECTANGLE\t{i}\t{left}\t{top}\t{right}\t{bottom}\t{word}"
            for offset, (i, left, top, right, bottom, word) in _ias_rows(name)
        ]
        (session / "aoi" / name).write_text(
            _BOM + "\n".join(rows) + "\n", encoding="utf-8"
        )
    (session / "graphics").mkdir(exist_ok=True)
    for name, rows in _VCL.items():
        (session / "graphics" / name).write_text(
            "\n".join(rows) + "\n", encoding="utf-8"
        )
