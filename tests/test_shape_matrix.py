"""Every shape of data the app reads, through every surface that lists, draws,
measures or exports it.

A new shape — raw gaze as the only table, trials over several screens, Word
IDs spelt as text, a trial ID composed of two columns — has repeatedly reached
some consumers and not others. Each cell loads one shape the way a user's files
arrive and runs one surface on it. A cell that is not meant to work is in
`UNSUPPORTED`, with the reason; every other cell must work.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pytest

import scanpath_studio
from scanpath_studio import api, cli
from scanpath_studio.export import ExportOptions, bulk_export
from scanpath_studio.synthetic import make_multipart_synthetic_data

SAMPLE = Path(scanpath_studio.__file__).parent / "sample_data"


@dataclass(frozen=True)
class Shape:
    """One shape's tables as the user's files hold them, and their mappings."""

    words: pd.DataFrame | None
    fixations: pd.DataFrame | None
    raw_gaze: pd.DataFrame | None = None
    schemas: dict = field(default_factory=dict)

    def load(self) -> tuple:
        """``(words, fixations, raw_gaze)`` as the API loads them."""
        words = fixations = None
        if self.words is not None or self.fixations is not None:
            words, fixations = api.load_scanpath_data(
                self.words,
                self.fixations,
                word_schema=self.schemas.get("word_schema"),
                fix_schema=self.schemas.get("fix_schema"),
                names="canonical",
            )
        raw_gaze = (
            api.load_raw_gaze(self.raw_gaze, names="canonical")
            if self.raw_gaze is not None
            else None
        )
        return words, fixations, raw_gaze


def _standard() -> Shape:
    """One reading of the bundled demo, with its recorded gaze."""
    words = pd.read_parquet(SAMPLE / "ia.parquet")
    fixations = pd.read_parquet(SAMPLE / "fixations.parquet")
    raw_gaze = pd.read_parquet(SAMPLE / "raw_gaze.parquet")
    reading = fixations[["participant_id", "unique_trial_id"]].iloc[0].tolist()

    def one(frame: pd.DataFrame) -> pd.DataFrame:
        keys = frame[["participant_id", "unique_trial_id"]]
        return frame[(keys == reading).all(axis=1)].reset_index(drop=True)

    return Shape(one(words), one(fixations), one(raw_gaze))


def _raw_gaze_only() -> Shape:
    return Shape(None, None, _standard().raw_gaze)


def _multipart() -> Shape:
    words, fixations = make_multipart_synthetic_data()
    return Shape(words, fixations)


def _text_word_ids() -> Shape:
    """Word IDs spelt as text, and fixations placed by them alone (no x/y)."""
    ids = ("Hello_1", "big_2", "world_3")
    words = pd.DataFrame(
        {
            "reader": "r1",
            "trial": "t1",
            "ia": ids,
            "word": [i.split("_")[0] for i in ids],
            "x": [0.0, 100.0, 200.0],
            "y": 0.0,
            "width": 50.0,
            "height": 20.0,
        }
    )
    fixations = pd.DataFrame(
        {
            "reader": "r1",
            "trial": "t1",
            "fix_ia": ["Hello_1", "world_3", "big_2"],
            "duration": [180.0, 220.0, 200.0],
        }
    )
    common = {"participant": "reader", "trial": "trial"}
    return Shape(
        words,
        fixations,
        schemas={
            "word_schema": common
            | {
                "word_id": "ia",
                "text": "word",
                "x": "x",
                "y": "y",
                "width": "width",
                "height": "height",
            },
            "fix_schema": common | {"word_id": "fix_ia", "duration": "duration"},
        },
    )


def _composite_trial_id() -> Shape:
    """A trial named by two columns whose parts contain the separator."""
    words, fixations = [], []
    for (session, item), x in ((("block_A", "B"), 100), (("block", "A_B"), 400)):
        reading = {"participant_id": "r1", "session": session, "item": item}
        words.append(
            reading
            | {
                "word_id": 1,
                "text": "word",
                "x": x,
                "y": 100,
                "width": 50,
                "height": 20,
            }
        )
        fixations.append(
            reading
            | {
                "word_id": 1,
                "x": x + 10,
                "y": 110,
                "duration_ms": 200,
                "timestamp_ms": 0,
            }
        )
    words, fixations = pd.DataFrame(words), pd.DataFrame(fixations)
    trial = {"trial": ["session", "item"]}
    return Shape(
        words,
        fixations,
        schemas={
            "word_schema": api.propose_schema(words, "words") | trial,
            "fix_schema": api.propose_schema(fixations, "fixations") | trial,
        },
    )


SHAPES = {
    "standard": _standard,
    "raw gaze only": _raw_gaze_only,
    "multipart": _multipart,
    "text word ids": _text_word_ids,
    "composite trial id": _composite_trial_id,
}


def _first_reading(words, fixations, raw_gaze) -> tuple[str, str]:
    trials = api.list_trials(words, fixations, raw_gaze=raw_gaze)
    return str(trials.iloc[0, 0]), str(trials.iloc[0, 1])


# --- The surfaces --------------------------------------------------------------


def _trial_pool(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    trials = api.list_trials(words, fixations, raw_gaze=raw_gaze)
    assert len(trials) >= 1


def _draws_the_reading(fig, shape: Shape) -> None:
    """The figure's fixation markers are exactly the first reading's fixations,
    of its first screen when the trial has several: no screen pooled into
    another, no reading's fixations lost."""
    words, fixations, raw_gaze = shape.load()
    participant, trial = _first_reading(words, fixations, raw_gaze)
    expected = 0
    if fixations is not None:
        rows = fixations[
            (fixations["participant_id"].astype(str) == participant)
            & (fixations["trial_id"].astype(str) == trial)
        ]
        if "screen_id" in rows:
            first = rows.sort_values("screen_index")["screen_id"].iloc[0]
            rows = rows[rows["screen_id"] == first]
        expected = len(rows)
    markers = [trace for trace in fig.data if trace.name == "Fixations"]
    drawn = sum(len(trace.x) for trace in markers)
    assert drawn == expected, f"drew {drawn} fixations, the reading has {expected}"


def _static(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    p, t = _first_reading(words, fixations, raw_gaze)
    fig = api.plot_scanpath(words, fixations, p, t, raw_gaze=raw_gaze)
    assert fig.data, "the figure drew nothing"
    _draws_the_reading(fig, shape)


def _replay(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    p, t = _first_reading(words, fixations, raw_gaze)
    fig = api.animate_scanpath(words, fixations, p, t)
    assert fig.frames, "the replay has no frames"


def _compare(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    trials = api.list_trials(words, fixations, raw_gaze=raw_gaze)
    a = tuple(map(str, trials.iloc[0, :2]))
    b = tuple(map(str, trials.iloc[-1, :2]))
    fig = api.compare_scanpaths(words, fixations, a, b, raw_gaze=raw_gaze)
    assert fig.data, "the comparison drew nothing"


def _render(shape: Shape, tmp_path: Path, *extra: str) -> None:
    """`render`, from the files as written, with the mappings as flags."""
    argv = ["render"]
    for name, flag, schema_flag, option in (
        ("words", "--words", "--word-schema", "word_schema"),
        ("fixations", "--fixations", "--fix-schema", "fix_schema"),
        ("raw_gaze", "--raw-gaze", None, None),
    ):
        frame = getattr(shape, name)
        if frame is None:
            continue
        path = tmp_path / f"{name}.parquet"
        frame.to_parquet(path)
        argv += [flag, str(path)]
        if option and shape.schemas.get(option):
            argv += [schema_flag, json.dumps(shape.schemas[option])]
    out = tmp_path / "figure.html"
    saved: list = []
    real_save = api.save_figure
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            api,
            "save_figure",
            lambda fig, path, **kw: (saved.append(fig), real_save(fig, path, **kw)),
        )
        cli.main([*argv, *extra, "-o", str(out)])
    assert out.stat().st_size > 0
    if not extra:  # the static figure: the same reading the API draws
        _draws_the_reading(saved[0], shape)


def _export(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    combos = api.list_trials(words, fixations, raw_gaze=raw_gaze)
    payload, progress = bulk_export(
        combos,
        words if words is not None else pd.DataFrame(),
        fixations if fixations is not None else pd.DataFrame(),
        raw_gaze=raw_gaze,
        canvas_width=1200,
        canvas_height=800,
        base_font_size=16,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings={},
        options=ExportOptions(
            include_png=False,
            include_svg=False,
            include_html=True,
            include_plot_config=False,
            include_fixations=True,
            include_raw_gaze=raw_gaze is not None,
        ),
    )
    assert not progress.errors and not progress.figures_failed, progress.errors
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert any(name.endswith(".html") for name in archive.namelist())


def _data_checks(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    assert isinstance(api.check_data_health(words, fixations, raw_gaze), pd.DataFrame)


def _render_replay(shape: Shape, tmp_path: Path) -> None:
    _render(shape, tmp_path, "--animate")


def _render_compare(shape: Shape, tmp_path: Path) -> None:
    trials = api.list_trials(*shape.load()[:2], raw_gaze=shape.load()[2])
    participant, trial = map(str, trials.iloc[-1, :2])
    _render(shape, tmp_path, "--compare-with", f"{participant}:{trial}")


SURFACES = {
    "trial pool": _trial_pool,
    "static": _static,
    "replay": _replay,
    "compare": _compare,
    "render": _render,
    "render replay": _render_replay,
    "render compare": _render_compare,
    "export bundle": _export,
    "data checks": _data_checks,
}

#: The cells that are not meant to work, each with why. Each is refused with a
#: message (a `ValueError`, or `render`'s exit), never a crash.
UNSUPPORTED: dict[tuple[str, str], str] = {
    ("raw gaze only", "replay"): (
        "a replay plays fixations, and nothing derives fixations from samples"
    ),
    ("raw gaze only", "compare"): (
        "a comparison draws two readings' fixations, which raw gaze alone lacks"
    ),
    ("raw gaze only", "render replay"): (
        "a replay plays fixations, and nothing derives fixations from samples"
    ),
    ("raw gaze only", "render compare"): (
        "a comparison draws two readings' fixations, which raw gaze alone lacks"
    ),
}

CELLS = [
    (shape, surface)
    for shape in SHAPES
    for surface in SURFACES
    if (shape, surface) not in UNSUPPORTED
]


@pytest.mark.parametrize("cell", CELLS, ids=" / ".join)
def test_every_shape_reaches_every_surface(cell, tmp_path):
    shape, surface = cell
    SURFACES[surface](SHAPES[shape](), tmp_path)


@pytest.mark.parametrize("cell", UNSUPPORTED, ids=" / ".join)
def test_an_unsupported_cell_is_refused_with_a_reason(cell, tmp_path):
    """Refused, not crashed: the user is told why. An entry that starts
    working fails here too, so it is dropped and the table stays the truth."""
    shape, surface = cell
    with pytest.raises((ValueError, SystemExit)) as refused:
        SURFACES[surface](SHAPES[shape](), tmp_path)
    assert str(refused.value).strip(), "refused without saying why"
