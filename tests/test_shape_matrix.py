"""Every shape of data the app reads, through every surface that lists, draws
or exports it.

A new shape — raw gaze as the only table, trials over several screens, Word
IDs spelt as text, a trial ID composed of two columns — has repeatedly reached
some consumers and not others. Each cell loads one shape the way a user's files
arrive and runs one surface on it. What a cell expects is stated with the shape,
from its input files or as constants, never read back from what the code under
test loaded: so breaking a shape's defining feature (the escaping in a
composite id, the matching of text keys, the choice of one screen) fails its
cells. A cell that is not meant to work is in `UNSUPPORTED`, with the reason it
is refused for.
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
from scanpath_studio import aggregation, api, cli, plots
from scanpath_studio.export import ExportOptions, bulk_export
from scanpath_studio.synthetic import make_multipart_synthetic_data

SAMPLE = Path(scanpath_studio.__file__).parent / "sample_data"


@dataclass(frozen=True)
class Shape:
    """One shape's tables as the user's files hold them, their mappings, and
    what every surface should make of them."""

    words: pd.DataFrame | None
    fixations: pd.DataFrame | None
    raw_gaze: pd.DataFrame | None = None
    schemas: dict = field(default_factory=dict)
    #: Each reading the trial pool lists, with the fixations its figure draws
    #: (its first screen's, on a multipart trial).
    readings: dict = field(default_factory=dict)
    #: The figures the export bundle writes: one per reading, one per screen.
    figures: int = 1
    #: Where the first reading's fixations land, when the shape fixes it.
    fixation_x: tuple | None = None
    #: The Words column holding dwell time, and the input columns that name a
    #: reading: what Corpus Analysis's overview is checked against.
    dwell: str | None = None
    reading_columns: tuple[str, ...] = ()

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


_READING = ["participant_id", "unique_trial_id"]


def _standard() -> Shape:
    """Two readings of the bundled demo by one reader, with their gaze."""
    words = pd.read_parquet(SAMPLE / "ia.parquet")
    fixations = pd.read_parquet(SAMPLE / "fixations.parquet")
    raw_gaze = pd.read_parquet(SAMPLE / "raw_gaze.parquet")
    reader = fixations["participant_id"].iloc[0]
    trials = fixations.loc[fixations["participant_id"] == reader, _READING[1]]
    kept = trials.drop_duplicates().iloc[:2].tolist()

    def two(frame: pd.DataFrame) -> pd.DataFrame:
        mask = (frame["participant_id"] == reader) & frame[_READING[1]].isin(kept)
        return frame[mask].reset_index(drop=True)

    fixations = two(fixations)
    counts = fixations.groupby(_READING).size()
    return Shape(
        two(words),
        fixations,
        two(raw_gaze),
        readings={(str(p), str(t)): int(n) for (p, t), n in counts.items()},
        figures=2,
        dwell="IA_DWELL_TIME",
        reading_columns=tuple(_READING),
    )


def _raw_gaze_only() -> Shape:
    raw_gaze = _standard().raw_gaze
    pairs = raw_gaze[_READING].drop_duplicates().itertuples(index=False)
    return Shape(
        None,
        None,
        raw_gaze,
        readings={(str(p), str(t)): 0 for p, t in pairs},
        figures=2,
    )


def _multipart() -> Shape:
    """One trial over two screens; its figure is its first screen, "intro".
    The overview counts it as one reading, its dwell averaged over both."""
    words, fixations = make_multipart_synthetic_data()
    words = words.assign(IA_DWELL_TIME=[120.0, 180.0, 240.0, 400.0, 600.0])
    first = int((fixations["screen_id"] == "intro").sum())
    return Shape(
        words,
        fixations,
        readings={("synthetic", "multipart_demo"): first},
        figures=2,
        dwell="IA_DWELL_TIME",
        reading_columns=("participant_id", "trial_id"),
    )


def _text_word_ids() -> Shape:
    """Word IDs spelt as text, and fixations placed by them alone (no x/y):
    each lands on the centre of the word with exactly its key."""
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
            "dwell": [180.0, 200.0, 220.0],
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
                "measure_tfd": "dwell",
            },
            "fix_schema": common | {"word_id": "fix_ia", "duration": "duration"},
        },
        readings={("r1", "t1"): 3},
        fixation_x=(25.0, 225.0, 125.0),
        dwell="dwell",
        reading_columns=("reader", "trial"),
    )


def _composite_trial_id() -> Shape:
    """A trial named by two columns whose parts hold the separator: two readings,
    which joining the parts plainly would merge into one."""
    words, fixations = [], []
    for (session, item), x, dwell in (
        (("block_A", "B"), 100, 200.0),
        (("block", "A_B"), 400, 400.0),
    ):
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
                "dwell_time": dwell,
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
            "word_schema": api.propose_schema(words, "words")
            | trial
            | {"measure_tfd": "dwell_time"},
            "fix_schema": api.propose_schema(fixations, "fixations") | trial,
        },
        readings={("r1", "block\\_A_B"): 1, ("r1", "block_A\\_B"): 1},
        figures=2,
        dwell="dwell_time",
        reading_columns=("participant_id", "session", "item"),
    )


SHAPES = {
    "standard": _standard,
    "raw gaze only": _raw_gaze_only,
    "multipart": _multipart,
    "text word ids": _text_word_ids,
    "composite trial id": _composite_trial_id,
}


def _pool(words, fixations, raw_gaze) -> list[tuple[str, str]]:
    trials = api.list_trials(words, fixations, raw_gaze=raw_gaze)
    return [(str(p), str(t)) for p, t in trials.iloc[:, :2].itertuples(index=False)]


# --- The surfaces --------------------------------------------------------------


def _trial_pool(shape: Shape, tmp_path: Path) -> None:
    assert sorted(_pool(*shape.load())) == sorted(shape.readings)


def _drawn_fixations(fig) -> list[int]:
    """The fixation markers each scanpath of a figure draws."""
    return [
        len(trace.x)
        for trace in fig.data
        if plots._trace_layer(trace) == "fixations"
        and "markers" in (trace.mode or "")
        and not (trace.name or "").endswith("raw gaze")
    ]


def _draws_the_reading(fig, shape: Shape, reading: tuple[str, str]) -> None:
    markers = [trace for trace in fig.data if trace.name == "Fixations"]
    drawn = sum(len(trace.x) for trace in markers)
    expected = shape.readings[reading]
    assert drawn == expected, f"drew {drawn} fixations, the reading has {expected}"
    if shape.fixation_x is not None:
        assert tuple(markers[0].x) == shape.fixation_x, "fixations on the wrong words"


def _static(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    reading = _pool(words, fixations, raw_gaze)[0]
    fig = api.plot_scanpath(words, fixations, *reading, raw_gaze=raw_gaze)
    _draws_the_reading(fig, shape, reading)


def _replay(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    reading = _pool(words, fixations, raw_gaze)[0]
    fig = api.animate_scanpath(words, fixations, *reading)
    # The last frame shows every fixation of the replay, as its first trace.
    assert len(fig.frames[-1].data[0].x) == shape.readings[reading]


def _compare(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    pool = _pool(words, fixations, raw_gaze)
    a, b = pool[0], pool[-1]
    fig = api.compare_scanpaths(words, fixations, a, b, raw_gaze=raw_gaze)
    assert _drawn_fixations(fig) == [shape.readings[a], shape.readings[b]]


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
    if not extra:  # the static figure, of the first reading `render` lists
        reading = _pool(*shape.load())[0]
        _draws_the_reading(saved[0], shape, reading)


def _render_replay(shape: Shape, tmp_path: Path) -> None:
    _render(shape, tmp_path, "--animate")


def _render_compare(shape: Shape, tmp_path: Path) -> None:
    participant, trial = _pool(*shape.load())[-1]
    _render(shape, tmp_path, "--compare-with", f"{participant}:{trial}")


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
        figures = [n for n in archive.namelist() if n.endswith("/figure.html")]
    assert len(figures) == shape.figures, figures


def _data_checks(shape: Shape, tmp_path: Path) -> None:
    words, fixations, raw_gaze = shape.load()
    assert isinstance(api.check_data_health(words, fixations, raw_gaze), pd.DataFrame)


def _expected_overview(shape: Shape) -> dict[str, tuple]:
    """Each participant's readings, and the mean and range of their per-reading
    dwell, worked out from the input table: a reading is what its input
    columns name, however many screens it spans."""
    words = shape.words
    dwell = pd.to_numeric(words[shape.dwell], errors="coerce")
    per_reading = dwell.groupby([words[c] for c in shape.reading_columns]).mean()
    return {
        str(participant): (len(means), means.mean(), means.min(), means.max())
        for participant, means in per_reading.groupby(level=0)
    }


def _corpus_overview(shape: Shape, tmp_path: Path) -> None:
    """Corpus Analysis's overview by participant, on the dataset's own dwell."""
    words, _fixations, _raw_gaze = shape.load()
    table = aggregation.corpus_overview(
        pd.DataFrame() if words is None else words,
        aggregation.MEASURES["tfd"],
        "participant",
    )
    got = {
        str(row.participant_id): (row.n_readings, row.value, row.lo, row.hi)
        for row in table.itertuples()
    }
    expected = _expected_overview(shape)
    assert got.keys() == expected.keys()
    for participant, (readings, *stats) in expected.items():
        assert got[participant][0] == readings, participant
        assert got[participant][1:] == pytest.approx(tuple(stats)), participant


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
    "corpus overview": _corpus_overview,
}

#: The cells that are not meant to work: what the refusal must say, and why.
UNSUPPORTED: dict[tuple[str, str], tuple[str, str]] = {
    ("raw gaze only", "replay"): (
        "no fixations to replay",
        "a replay plays fixations, and nothing derives fixations from samples",
    ),
    ("raw gaze only", "compare"): (
        "compares two readings' fixations",
        "a comparison draws two readings' fixations, which raw gaze alone lacks",
    ),
    ("raw gaze only", "render replay"): (
        "fixation",
        "a replay plays fixations, and nothing derives fixations from samples",
    ),
    ("raw gaze only", "render compare"): (
        "fixation",
        "a comparison draws two readings' fixations, which raw gaze alone lacks",
    ),
    ("raw gaze only", "corpus overview"): (
        "needs a mapped word-level measure",
        "the overview summarises a measure the Words table brings, and raw gaze "
        "alone has no Words table",
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
def test_an_unsupported_cell_is_refused_with_its_reason(cell, tmp_path):
    """Refused, not crashed, and the message is the reason given here. An
    entry that starts working fails too, so the table stays the truth."""
    shape, surface = cell
    with pytest.raises((ValueError, SystemExit)) as refused:
        SURFACES[surface](SHAPES[shape](), tmp_path)
    if isinstance(refused.value, SystemExit):
        assert isinstance(refused.value.code, str), "an exit code, not a message"
    said, _why = UNSUPPORTED[cell]
    assert said in str(refused.value), str(refused.value)
