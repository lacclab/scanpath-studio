"""Tests for flexible dataset support: multi-file inputs, single-report
datasets (words-only / fixations-only), stimulus-level word tables, AOI-only
fixations, and the PoTeC loader."""

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import scanpath_studio as sps
from scanpath_studio import data as data_module
from scanpath_studio import datasets as datasets_module
from scanpath_studio import progress
from scanpath_studio.plots import make_scanpath_figure

# ---------------------------------------------------------------------------
# Multi-file reading
# ---------------------------------------------------------------------------


def _write_fix_csv(path, participant, trial, n=3):
    pd.DataFrame(
        {
            "participant_id": [participant] * n,
            "trial_id": [trial] * n,
            "x": np.linspace(100, 300, n),
            "y": [80.0] * n,
            "duration_ms": [200.0] * n,
        }
    ).to_csv(path, index=False)


def test_read_table_tsv(tmp_path):
    path = tmp_path / "words.tsv"
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_csv(path, sep="\t", index=False)
    df = data_module.read_table(path)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


@pytest.mark.parametrize("ext, sep", [("csv", ","), ("tsv", "\t")])
def test_read_table_uses_single_pass_dtype_inference(tmp_path, monkeypatch, ext, sep):
    """CSV/TSV reads must pass ``low_memory=False`` so a column that is numeric
    in early parser chunks and a sentinel (e.g. EyeLink's ``.``) in a later one
    can't become a single ``object`` column mixing Python ``float`` and ``str``.
    That mix emits a ``DtypeWarning`` and crashes pyarrow when Streamlit displays
    the frame — only on big (multi-chunk) files, so a small upload reads fine
    locally while a full report kills the cloud worker."""
    captured = {}
    real_read_csv = data_module.pd.read_csv

    def spy(buf, **kwargs):
        captured.update(kwargs)
        return real_read_csv(buf, **kwargs)

    monkeypatch.setattr(data_module.pd, "read_csv", spy)
    path = tmp_path / f"fix.{ext}"
    pd.DataFrame({"CURRENT_FIX_PRECISION_MEASURE_RMS_S2S": [0.1, 2.0]}).to_csv(
        path, sep=sep, index=False
    )
    data_module.read_table(path)
    assert captured.get("low_memory") is False


class _NamedBytesIO(io.BytesIO):
    """A BytesIO that carries a ``name`` like Streamlit's UploadedFile, so we
    can exercise the upload path (where pandas can't infer compression)."""

    def __init__(self, data, name):
        super().__init__(data)
        self.name = name


def _zip_bytes(member_name, data: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member_name, data)
    return buf.getvalue()


def test_read_table_csv_zip_path(tmp_path):
    path = tmp_path / "words.csv.zip"
    path.write_bytes(_zip_bytes("words.csv", b"a,b\n1,x\n2,y\n"))
    df = data_module.read_table(path)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


def test_read_table_csv_zip_uploaded_file_like():
    # An in-memory upload named *.csv.zip — pandas infers
    # compression only from string paths, so this must be handled explicitly.
    upload = _NamedBytesIO(_zip_bytes("data.csv", b"a,b\n1,x\n2,y\n"), "data.csv.zip")
    df = data_module.read_table(upload)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


def test_read_table_tsv_zip():
    upload = _NamedBytesIO(_zip_bytes("d.tsv", b"a\tb\n1\tx\n"), "d.tsv.zip")
    df = data_module.read_table(upload)
    assert list(df.columns) == ["a", "b"]


def test_read_table_zip_ignores_macosx_cruft():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("real.csv", b"a,b\n1,2\n")
        zf.writestr("__MACOSX/._real.csv", b"junk")
        zf.writestr(".DS_Store", b"junk")
    upload = _NamedBytesIO(buf.getvalue(), "bundle.zip")
    df = data_module.read_table(upload)
    assert list(df.columns) == ["a", "b"]


def test_read_table_zip_multiple_members_concatenates():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("reader0.csv", b"a,b\n1,x\n2,y\n")
        zf.writestr("reader1.csv", b"a,b\n3,z\n")
    upload = _NamedBytesIO(buf.getvalue(), "bundle.zip")
    df = data_module.read_table(upload)
    assert len(df) == 3
    # Each member's rows are traceable via the source_file stem.
    assert set(df["source_file"]) == {"reader0", "reader1"}


def test_read_table_zip_same_stem_in_different_folders_stays_distinct():
    """Two readers' ``fixations.csv`` must not become one."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("reader-a/fixations.csv", "trial_id,x,y,duration_ms\nt1,1,2,100\n")
        zf.writestr("reader-b\\fixations.csv", "trial_id,x,y,duration_ms\nt1,3,4,120\n")
        zf.writestr("words.csv", "trial_id,x,y,duration_ms\nt2,5,6,90\n")
    raw = data_module.read_table(_NamedBytesIO(buf.getvalue(), "readers.zip"))
    assert raw["source_file"].tolist() == [
        "reader-a/fixations",
        "reader-b/fixations",
        "words",
    ]
    schema = data_module.propose_fix_schema(raw)
    schema["participant"] = data_module.SOURCE_FILE_COLUMN
    normalized = data_module.normalize_fixations(raw, schema)
    readings = normalized[["participant_id", "trial_id"]].drop_duplicates()
    assert len(readings) == 3


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["a.csv", "b.tsv"], ["a", "b"]),
        (["x/a/f.csv", "y/a/f.csv", "z/b/f.csv"], ["x/a/f", "y/a/f", "b/f"]),
        (["a/f.csv", "a/f.tsv"], ["f.csv", "f.tsv"]),
        (["x/f.csv", "x/f.tsv", "y/f.csv"], ["x/f.csv", "x/f.tsv", "y/f"]),
        # Only folders that differ: an absolute path's shared prefix stays out.
        (["/Users/me/data/a.csv", "/Users/me/data/a.parquet"], ["a.csv", "a.parquet"]),
        (["/Users/me/d/a.csv", "/Users/me/d/a.csv"], ["a#1", "a#2"]),
        (["/Users/me/r1/x/f.csv", "/Users/me/r2/x/f.csv"], ["r1/x/f", "r2/x/f"]),
        (["f.csv", "f.csv"], ["f#1", "f#2"]),
        (["./a/f.csv", "a\\g.csv"], ["f", "g"]),
    ],
)
def test_source_labels(paths, expected):
    assert data_module.source_labels(paths) == expected
    assert len(set(data_module.source_labels(paths))) == len(paths)


@pytest.mark.parametrize(
    ("label", "name"),
    [
        ("r/001_x_fixation#2", "001_x_fixation"),
        ("001_x_fixation.csv", "001_x_fixation"),
        ("a/b/stim_aoi", "stim_aoi"),
        ("v1.2_thing", "v1.2_thing"),
    ],
)
def test_source_file_name(label, name):
    assert data_module.source_file_name(label) == name


def test_read_tables_same_name_in_different_folders(tmp_path):
    for reader in ("r1", "r2"):
        (tmp_path / reader).mkdir()
        _write_fix_csv(tmp_path / reader / "fix.csv", "p", "t")
    df = data_module.read_tables(str(tmp_path / "*" / "fix.csv"))
    assert sorted(df["source_file"].unique()) == ["r1/fix", "r2/fix"]


def test_read_table_zip_mixed_formats_concatenates():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.csv", b"x\n1\n")
        zf.writestr("b.tsv", b"x\n2\n")
    upload = _NamedBytesIO(buf.getvalue(), "mixed.zip")
    df = data_module.read_table(upload)
    assert sorted(df["x"]) == [1, 2]


def test_read_table_zip_no_data_files_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("__MACOSX/._x", b"junk")
        zf.writestr(".DS_Store", b"junk")
    upload = _NamedBytesIO(buf.getvalue(), "empty.zip")
    with pytest.raises(ValueError, match="holds no table file"):
        data_module.read_table(upload)


def test_read_tables_list_adds_source_file(tmp_path):
    p1, p2 = tmp_path / "reader0_t1.csv", tmp_path / "reader1_t1.csv"
    _write_fix_csv(p1, "p0", "t1")
    _write_fix_csv(p2, "p1", "t1")
    df = data_module.read_tables([p1, p2])
    assert len(df) == 6
    assert set(df["source_file"]) == {"reader0_t1", "reader1_t1"}


def test_read_tables_single_file_tags_source_file(tmp_path):
    # A single file still gets a source_file column (the filename stem), so a
    # dataset keying identity in the filename can recover it via the wizard.
    p1 = tmp_path / "only.csv"
    _write_fix_csv(p1, "p0", "t1")
    df = data_module.read_tables(p1)
    assert set(df["source_file"]) == {"only"}


def test_read_tables_glob(tmp_path):
    for i in range(3):
        _write_fix_csv(tmp_path / f"reader{i}_fix.csv", f"p{i}", "t1")
    df = data_module.read_tables(str(tmp_path / "reader*_fix.csv"))
    assert len(df) == 9
    assert df["source_file"].nunique() == 3


def test_read_tables_glob_no_match_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="No files match"):
        data_module.read_tables(str(tmp_path / "nope*.csv"))


def test_load_scanpath_data_accepts_path_list(tmp_path):
    p1, p2 = tmp_path / "f1.csv", tmp_path / "f2.csv"
    _write_fix_csv(p1, "p0", "t1")
    _write_fix_csv(p2, "p1", "t1")
    words, fixations = sps.load_scanpath_data(fixations=[p1, p2], names="canonical")
    assert words.empty
    assert set(fixations["participant_id"]) == {"p0", "p1"}
    # the origin file survives normalization for traceability
    assert set(fixations["source_file"]) == {"f1", "f2"}


# ---------------------------------------------------------------------------
# Single-report datasets
# ---------------------------------------------------------------------------


def test_load_scanpath_data_requires_some_input():
    with pytest.raises(ValueError, match="at least one"):
        sps.load_scanpath_data(names="canonical")


def test_fixations_only_load_list_and_plot(tmp_path):
    path = tmp_path / "fix.csv"
    _write_fix_csv(path, "p0", "t1")
    words, fixations = sps.load_scanpath_data(fixations=path, names="canonical")
    assert words.empty and not fixations.empty

    combos = sps.list_trials(words, fixations)
    assert combos.to_records(index=False).tolist() == [("p0", "t1")]

    fig = sps.plot_scanpath(words, fixations, "p0", "t1")
    assert len(fig.data) > 0


def test_words_only_load_list_and_plot(sample_words_df):
    words, fixations = sps.load_scanpath_data(words=sample_words_df, names="canonical")
    assert fixations.empty and not words.empty

    combos = sps.list_trials(words, fixations)
    assert ("p1", "t1") in {tuple(r) for r in combos.to_numpy()}

    fig = sps.plot_scanpath(words, fixations, "p1", "t1")
    assert len(fig.data) > 0


def test_words_only_heatmap_uses_preaggregated_measures(sample_words_df):
    sample_words_df = sample_words_df.copy()
    sample_words_df["IA_DWELL_TIME"] = [500, 250, 0, 100, 100]
    words, fixations = sps.load_scanpath_data(words=sample_words_df, names="canonical")
    trial_words = words[words["participant_id"] == "p1"]

    def n_shapes(show_heatmap):
        fig = make_scanpath_figure(
            trial_words,
            fixations,
            canvas_width=800,
            canvas_height=600,
            base_font_size=14,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=False,
            show_fixations=False,
            show_order=False,
            show_saccades=False,
            show_heatmap=show_heatmap,
            color_by="duration_ms",
            heatmap_metric="duration_ms",
            marker_size_range=(6, 30),
            order_font_size=12,
            order_font_color="#000",
            show_fixation_colorbar=False,
            show_heatmap_colorbar=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        return len(fig.layout.shapes or [])

    # word boxes only vs. word boxes + heatmap rectangles for the two
    # words with nonzero pre-aggregated dwell time
    assert n_shapes(True) == n_shapes(False) + 2


def test_default_filters_fixations_only(tmp_path):
    path = tmp_path / "fix.csv"
    _write_fix_csv(path, "p0", "t1")
    words, fixations = sps.load_scanpath_data(fixations=path, names="canonical")
    filters = data_module.default_filters(words, fixations)
    assert filters["participants"] == ["p0"]
    assert filters["trials"] == ["t1"]
    _w, f = data_module.filter_data(words, fixations, filters)
    assert len(f) == 3


# ---------------------------------------------------------------------------
# Stimulus-level words + AOI-only fixations
# ---------------------------------------------------------------------------


@pytest.fixture
def stimulus_words_df():
    """Word boxes keyed by text only — no participant column."""
    return pd.DataFrame(
        {
            "text_id": ["t1", "t1", "t2"],
            "word_id": [1, 2, 1],
            "word": ["Hello", "world", "Bye"],
            "left": [100, 200, 100],
            "right": [180, 280, 160],
            "top": [50, 50, 50],
            "bottom": [100, 100, 100],
        }
    )


@pytest.fixture
def aoi_fixations_df():
    """AOI-sequence fixations: word ids but no pixel coordinates."""
    return pd.DataFrame(
        {
            "reader_id": [7, 7, 7, 8],
            "text_id": ["t1", "t1", "t1", "t2"],
            "fixation_duration": [180, 220, 150, 200],
            "word_index": [1, 2, 1, 1],
        }
    )


def test_stimulus_words_broadcast_and_aoi_xy(stimulus_words_df, aoi_fixations_df):
    words, fixations = sps.load_scanpath_data(
        words=stimulus_words_df, fixations=aoi_fixations_df, names="canonical"
    )
    # words replicated across the readers that read each text
    assert set(words["participant_id"]) == {"7", "8"}
    t1_words = words[words["trial_id"] == "t1"]
    assert len(t1_words) == 2  # only reader 7 read t1
    # t2 words exist only for reader 8
    assert set(words[words["trial_id"] == "t2"]["participant_id"]) == {"8"}

    # fixation coordinates = word box centers
    assert fixations["x"].tolist() == [140.0, 240.0, 140.0, 130.0]
    assert fixations["y"].tolist() == [75.0] * 4

    fig = sps.plot_scanpath(words, fixations, "7", "t1")
    assert len(fig.data) > 0


def test_stimulus_words_without_fixations_get_synthetic_participant(stimulus_words_df):
    words, _fixations = sps.load_scanpath_data(
        words=stimulus_words_df, names="canonical"
    )
    # No fixations to broadcast across → a single anonymous reader.
    assert (words["participant_id"] == data_module.SYNTHETIC_PARTICIPANT).all()
    assert data_module.STIMULUS_WORDS_FLAG not in words.columns


def test_a_repeated_reading_gets_the_stimulus_words_too(stimulus_words_df):
    """The second reading's id is `t1_r2`, which a table keyed by the text
    alone never has — the broadcast must still find its boxes."""
    fixations = pd.DataFrame(
        {
            "reader_id": [7, 7, 7, 7],
            "text_id": ["t1", "t1", "t1", "t1"],
            "TRIAL_INDEX": [1, 1, 3, 3],
            "fixation_duration": [180, 220, 150, 200],
            "x": [140.0, 240.0, 140.0, 240.0],
            "y": [75.0] * 4,
        }
    )
    words, fixations = sps.load_scanpath_data(
        words=stimulus_words_df, fixations=fixations, names="canonical"
    )
    assert set(fixations["trial_id"]) == {"t1", "t1_r2"}
    for trial in ("t1", "t1_r2"):
        boxes = words[(words["participant_id"] == "7") & (words["trial_id"] == trial)]
        assert boxes["text"].tolist() == ["Hello", "world"], trial


def test_a_trial_named_like_a_repeat_keeps_its_own_words(stimulus_words_df):
    """The fallback only applies when the exact id has no boxes."""
    words_df = pd.concat(
        [stimulus_words_df, stimulus_words_df.assign(text_id="t1_r2", word="Other")]
    )
    fixations = pd.DataFrame(
        {
            "reader_id": [7, 7],
            "text_id": ["t1", "t1_r2"],
            "fixation_duration": [180, 220],
            "x": [140.0, 140.0],
            "y": [75.0, 75.0],
        }
    )
    words, _ = sps.load_scanpath_data(
        words=words_df, fixations=fixations, names="canonical"
    )
    own = words[words["trial_id"] == "t1_r2"]
    assert set(own["text"]) == {"Other"}


def test_aoi_fixations_without_words_raise_on_plot(aoi_fixations_df):
    words, fixations = sps.load_scanpath_data(
        fixations=aoi_fixations_df, names="canonical"
    )
    assert fixations["x"].isna().all()
    with pytest.raises(ValueError, match="no usable coordinates"):
        sps.plot_scanpath(words, fixations, "7", "t1")


def test_fix_schema_requires_xy_or_word_id():
    no_position = pd.DataFrame(
        {"participant_id": ["p"], "trial_id": ["t"], "duration_ms": [100]}
    )
    with pytest.raises(ValueError, match="Word ID"):
        sps.load_scanpath_data(fixations=no_position, names="canonical")


def test_participant_less_fixations_get_synthetic_participant():
    """A fixations table with no participant column loads (participant is
    optional) and every row is stamped with the synthetic participant."""
    fixations = pd.DataFrame(
        {
            "trial_id": ["t1", "t1", "t2"],
            "x": [10.0, 20.0, 30.0],
            "y": [5.0, 5.0, 5.0],
            "duration_ms": [100, 120, 90],
        }
    )
    _words, fix = sps.load_scanpath_data(fixations=fixations, names="canonical")
    assert (fix["participant_id"] == data_module.SYNTHETIC_PARTICIPANT).all()


def test_asymmetric_participant_reconciles_word_boxes():
    """Words carry a participant id but fixations don't — the boxes must be
    re-keyed to the synthetic participant the trial picker uses, or they'd be
    silently invisible (extract_trial would find none)."""
    words = pd.DataFrame(
        {
            "participant_id": ["sub1", "sub1"],
            "trial_id": ["t1", "t1"],
            "word_id": [1, 2],
            "word": ["Hello", "world"],
            "left": [100, 200],
            "right": [180, 280],
            "top": [50, 50],
            "bottom": [100, 100],
        }
    )
    fixations = pd.DataFrame(
        {
            "trial_id": ["t1", "t1"],
            "x": [140.0, 240.0],
            "y": [75.0, 75.0],
            "duration_ms": [180, 200],
        }
    )
    words_n, fix_n = sps.load_scanpath_data(
        words=words, fixations=fixations, names="canonical"
    )
    assert set(fix_n["participant_id"]) == {data_module.SYNTHETIC_PARTICIPANT}
    assert set(words_n["participant_id"]) == {data_module.SYNTHETIC_PARTICIPANT}
    # The boxes for the trial the picker offers ('(all)', 't1') are reachable.
    fig = sps.plot_scanpath(words_n, fix_n, data_module.SYNTHETIC_PARTICIPANT, "t1")
    assert len(fig.data) > 0


def test_frame_fingerprint_distinguishes_unhashable_columns():
    """Two frames identical in shape + columns but differing in a list-valued
    (unhashable) column must not collapse to the same cache key."""
    a = pd.DataFrame({"x": [1, 2], "spans": [[1, 2], [3, 4]]})
    b = pd.DataFrame({"x": [1, 2], "spans": [[9, 9], [8, 8]]})
    assert data_module.frame_fingerprint(a) != data_module.frame_fingerprint(b)


# ---------------------------------------------------------------------------
# PoTeC loader (against a tiny synthesized PoTeC-format tree, no download)
# ---------------------------------------------------------------------------


@pytest.fixture
def potec_root(tmp_path):
    """A minimal PoTeC-shaped directory: one text (b0), two readers (0, 1)."""
    aoi_dir = tmp_path / "stimuli" / "aoi_texts"
    word_dir = tmp_path / "stimuli" / "word_aoi_texts"
    scan_dir = tmp_path / "eyetracking_data" / "scanpaths"
    for d in (aoi_dir, word_dir, scan_dir):
        d.mkdir(parents=True)

    # text "Um null" — two words, char AOIs 1..7 (space belongs to no AOI in
    # real PoTeC, but a simple consecutive layout is fine here). "null" guards
    # the keep_default_na handling (PoTeC text p3 contains the word "null").
    chars = pd.DataFrame(
        {
            "aoi_type": ["0 RECTANGLE"] * 7,
            "aoi": range(1, 8),
            "start_x": [80, 93, 115, 137, 150, 163, 176],
            "start_y": [21] * 7,
            "end_x": [93, 115, 137, 150, 163, 176, 189],
            "end_y": [99] * 7,
            "character": list("Um") + [" "] + list("null"),
            "line": [1] * 7,
        }
    )
    chars.to_csv(aoi_dir / "b0.ias", sep="\t", index=False)

    words = pd.DataFrame(
        {
            "aoi_type": ["0 RECTANGLE"] * 2,
            "aoi": [1.0, 2.0],
            "start_x": [80.0, 115.0],
            "start_y": [21.0, 21.0],
            "end_x": [115.0, 189.0],
            "end_y": [99.0, 99.0],
            "word": ["Um", "null"],
        }
    )
    words.to_csv(word_dir / "word_aoi_b0.tsv", sep="\t", index=False)

    for reader in (0, 1):
        pd.DataFrame(
            {
                "fixation_index": [1, 2, 3],
                "fixation_duration": [210, 190, 250],
                "line": [1, 1, 1],
                "aoi": [2, 5, 1],  # chars m, u, U
                "reader_id": [reader] * 3,
                "text_id": ["b0"] * 3,
                "word_index_in_text": [1, 2, 1],
                "word": ["Um", "null", "Um"],
            }
        ).to_csv(scan_dir / f"reader{reader}_b0_scanpath.tsv", sep="\t", index=False)
    return tmp_path


def test_load_potec(potec_root):
    words, fixations = datasets_module.load_potec(
        potec_root, texts=["b0"], names="canonical"
    )

    # stimulus words broadcast across both readers
    assert set(words["participant_id"]) == {"0", "1"}
    assert len(words) == 4  # 2 words x 2 readers
    assert set(words["text"]) == {"Um", "null"}  # "null" must stay a string
    assert words["line_idx"].eq(1).all()

    # fixation x/y reconstructed from the character AOI centers
    reader0 = fixations[fixations["participant_id"] == "0"]
    assert reader0["x"].tolist() == [104.0, 156.5, 86.5]
    assert reader0["y"].tolist() == [60.0] * 3
    assert reader0["duration_ms"].tolist() == [210.0, 190.0, 250.0]
    # word ids link fixations to the word AOIs
    assert reader0["word_id"].tolist() == [1.0, 2.0, 1.0]

    # A trial is one reader's reading of one text — the text name alone repeats
    # across readers — and each reading finds its text's boxes by Text ID.
    readings = fixations[["participant_id", "trial_id", "text_id"]].drop_duplicates()
    assert sorted(map(tuple, readings.values)) == [
        ("0", "0_b0", "b0"),
        ("1", "1_b0", "b0"),
    ]
    assert set(words["trial_id"]) == {"0_b0", "1_b0"}
    assert set(words["text_id"]) == {"b0"}

    fig = sps.plot_scanpath(words, fixations, "1", "1_b0", canvas_size=(1680, 1050))
    assert len(fig.data) > 0


def test_load_potec_reader_subset(potec_root):
    words, fixations = datasets_module.load_potec(
        potec_root, readers=[1], texts=["b0"], names="canonical"
    )
    assert set(fixations["participant_id"]) == {"1"}
    assert set(words["participant_id"]) == {"1"}


@pytest.mark.timeout(120)
def test_the_app_maps_potec_trials_as_reader_and_text(potec_root, monkeypatch):
    """The app declares PoTeC's schema rather than detecting it, so its
    Trial ID is the reader + text the headless loader uses, not the text alone."""
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT, pin_data_view

    label = next(k for k in app.PUBLIC_DATASET_REGISTRY if "PoTeC" in k)
    frames = datasets_module.potec_raw_frames(potec_root, texts=["b0"])
    monkeypatch.setitem(
        app.PUBLIC_DATASET_REGISTRY[label], "loader", lambda *_slots: frames
    )
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90)
    at.session_state["data_source_choice"] = app.PUBLIC_DATASETS_CHOICE
    at.session_state["public_dataset_choice"] = label
    # A pick restored from an older session's recovery cache does not survive
    # the session's first run of the source.
    at.session_state["col_map_fix_trial"] = ["text_id"]
    pin_data_view(at)
    at.run()
    assert not at.exception, at.exception
    assert at.multiselect(key="col_map_fix_trial").value == ["reader_id", "text_id"]
    assert at.multiselect(key="col_map_words_trial").value == ["text_id"]
    rows = at.session_state[app.DATASET_TABLE_ROWS_KEY]
    potec = next(r for r in rows if r["_token"] == label)
    assert (potec["Participants"], potec["Trials"], potec["Words"]) == (2, 2, 4)


def test_load_potec_unknown_text(potec_root):
    with pytest.raises(ValueError, match="Unknown PoTeC text ids"):
        datasets_module.load_potec(potec_root, texts=["z9"], names="canonical")


def test_load_potec_missing_data_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="download=True"):
        datasets_module.load_potec(tmp_path, texts=["b0"], names="canonical")


def test_potec_reports_each_fixation_file(potec_root, monkeypatch):
    """`_potec_fixations` reports each file read, so a card can say
    "1 of 2 files" while loading. This pins the FULL call sequence via a spy
    on `progress.report` — not just the final
    snapshot, since a cancel checkpoint needs the intermediate reports to
    actually have happened, in order, one per file. The first, "0 of 2", comes
    before any file is read (see the next test)."""
    from scanpath_studio.datasets import potec_raw_frames

    calls = []
    real_report = progress.report

    def spy(done=None, total=None, *, unit="", detail=None):
        calls.append((done, total, unit))
        return real_report(done, total, unit=unit, detail=detail)

    monkeypatch.setattr(progress, "report", spy)
    with progress.task(("t", "potec"), title="Loading PoTeC") as task:
        potec_raw_frames(potec_root, texts=["b0"])
    assert calls == [(0, 2, "files"), (1, 2, "files"), (2, 2, "files")]
    snap = task.snapshot()
    assert (snap.done, snap.total, snap.unit) == (2, 2, "files")


def _state_of_the_active_task() -> tuple:
    task = progress.active()
    snap = task.snapshot()
    return (task.worked, snap.done, snap.total, snap.unit)


def test_a_potec_load_has_reported_before_its_first_fixation_file(
    potec_root, monkeypatch
):
    """A gated card shows once its task reports, and a loop that reports
    only *after* each file hides its first file — for OneStop, a whole report —
    behind the delay. So a reader reports "0 of N" before it reads anything."""
    seen = []
    real_read = datasets_module._read_potec_tsv

    def _read(path):
        if "eyetracking_data" in Path(path).parts:
            seen.append(_state_of_the_active_task())
        return real_read(path)

    monkeypatch.setattr(datasets_module, "_read_potec_tsv", _read)
    with progress.task(("t", "potec-first"), title="Loading PoTeC"):
        datasets_module.potec_raw_frames(potec_root, texts=["b0"])
    assert seen[0] == (True, 0, 2, "files")


def test_a_onestop_load_has_reported_before_its_first_report(
    onestop_offline, tmp_path, monkeypatch
):
    seen = []
    real_read = datasets_module._read_onestop_part

    def _read(*args, **kwargs):
        seen.append(_state_of_the_active_task())
        return real_read(*args, **kwargs)

    monkeypatch.setattr(datasets_module, "_read_onestop_part", _read)
    with progress.task(("t", "onestop-first"), title="Loading OneStop"):
        datasets_module.onestop_raw_frames(tmp_path, regime="ordinary", download=True)
    assert seen[0] == (True, 0, 2, "reports")


def test_potec_present(tmp_path):
    # The app loads the whole corpus, so "present" requires every text's word +
    # char AOI files (what download_potec fetches), not just one.
    root = tmp_path / "potec"
    word_dir = root / "stimuli" / "word_aoi_texts"
    char_dir = root / "stimuli" / "aoi_texts"
    scan_dir = root / "eyetracking_data" / "scanpaths"
    for d in (word_dir, char_dir, scan_dir):
        d.mkdir(parents=True)
    (scan_dir / "reader0_b0_scanpath.tsv").write_text("x\n", encoding="utf-8")
    for text_id in datasets_module._POTEC_TEXTS:
        (word_dir / f"word_aoi_{text_id}.tsv").write_text("x\n", encoding="utf-8")
        (char_dir / f"{text_id}.ias").write_text("x\n", encoding="utf-8")

    assert datasets_module.potec_present(root) is True
    assert datasets_module.potec_present(tmp_path / "empty") is False
    # Missing even one text's AOI → the full-corpus load can't run → not present.
    (word_dir / "word_aoi_b0.tsv").unlink()
    assert datasets_module.potec_present(root) is False


# ---------------------------------------------------------------------------
# OneStop public loader (OSF download-on-demand). Network is monkeypatched —
# download_onestop is replaced with one that writes tiny OneStop-shaped reports,
# each as a .csv.zip carrying the macOS __MACOSX cruft the real OSF archives do.
# ---------------------------------------------------------------------------


def _write_csv_zip_with_macosx(path, frame, member_name):
    """Write ``frame`` as ``member_name`` inside a .csv.zip, plus a __MACOSX
    resource-fork entry — mirroring the OneStop OSF archives."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(member_name, frame.to_csv(index=False))
        zf.writestr(f"__MACOSX/._{member_name}", b"\x00\x00")


# The composing columns every OneStop report carries, and the id the loader
# builds out of them (batch_article_paragraph_level -- update_sample_data's
# convention). The public OSF release ships NO unique_paragraph_id, so the
# loader composes one; `shape="lacclab"` adds the lab export's own instead.
_FAKE_ONESTOP_IDS = {
    "article_batch": 2,
    "article_id": 3,
    "paragraph_id": 1,
    "difficulty_level": "Adv",
    "repeated_reading_trial": 0,
}
_FAKE_ONESTOP_PARAGRAPH = "2_3_1_Adv"
_FAKE_ONESTOP_TRIAL = "p1_2_3_1_Adv"


def _fake_onestop_part_frames(part, label_a, label_b, shape="public"):
    """Minimal OneStop-shaped (ia, fixations) frames for a part.

    Distinct IA_LABELs per part let a multi-part load prove the parts stayed
    separate (each part's words carry its own labels). ``shape`` picks which
    release the columns imitate: ``"public"`` (the OSF reports -- the composing
    id columns only) or ``"lacclab"`` (which also ships its own
    ``unique_paragraph_id``, in its own field order)."""
    ids = {key: [value, value] for key, value in _FAKE_ONESTOP_IDS.items()}
    if shape == "lacclab":
        ids["unique_paragraph_id"] = ["3_2_Adv_1", "3_2_Adv_1"]
    ia = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            **ids,
            "IA_ID": [1, 2],
            "IA_LABEL": [label_a, label_b],
            "IA_LEFT": [100.0, 140.0],
            "IA_RIGHT": [138.0, 180.0],
            "IA_TOP": [80.0, 80.0],
            "IA_BOTTOM": [110.0, 110.0],
        }
    )
    fix = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            **ids,
            "CURRENT_FIX_INDEX": [1, 2],
            "CURRENT_FIX_X": [110.0, 150.0],
            "CURRENT_FIX_Y": [95.0, 95.0],
            "CURRENT_FIX_DURATION": [200.0, 180.0],
        }
    )
    return ia, fix


# Per-part word labels for the fake reports (so multi-part loads are separable).
_FAKE_ONESTOP_PART_LABELS = {
    "Paragraph": ("The", "cat"),
    "Title": ("Bold", "Head"),
    "Question_Preview": ("What", "when"),
    "Questions": ("Which", "who"),
    "Answers": ("First", "Second"),
    "QA": ("Both", "combined"),
    "Feedback": ("Correct", "yes"),
}


def _fake_onestop_reports(
    root, regime, parts=("Paragraph",), variant="public", shape="public"
):
    """Write minimal OneStop-shaped IA + fixation reports for regime + parts."""
    root = datasets_module.Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for part in parts:
        la, lb = _FAKE_ONESTOP_PART_LABELS[part]
        ia, fix = _fake_onestop_part_frames(part, la, lb, shape=shape)
        ia_path = datasets_module._onestop_part_paths(root, "ia", regime, part, variant)
        fix_path = datasets_module._onestop_part_paths(
            root, "fixations", regime, part, variant
        )
        _write_csv_zip_with_macosx(ia_path, ia, ia_path.name.removesuffix(".zip"))
        _write_csv_zip_with_macosx(fix_path, fix, fix_path.name.removesuffix(".zip"))


@pytest.fixture
def onestop_offline(monkeypatch):
    """Replace download_onestop with a network-free report writer."""

    def fake_download(root, *, regime="ordinary", parts=None):
        _fake_onestop_reports(
            root, regime, parts or list(datasets_module.ONESTOP_DEFAULT_PARTS)
        )
        return datasets_module.Path(root)

    monkeypatch.setattr(datasets_module, "download_onestop", fake_download)


def test_onestop_raw_frames_reads_macosx_zip(onestop_offline, tmp_path):
    words, fixations = datasets_module.onestop_raw_frames(
        tmp_path, regime="ordinary", download=True
    )
    # The __MACOSX cruft member must be filtered out, leaving the real CSV only.
    assert len(words) == 2
    assert list(words["IA_LABEL"]) == ["The", "cat"]
    assert len(fixations) == 2
    assert "source_file" not in words.columns  # single member → no concat tag


def test_onestop_raw_frames_auto_detect_and_plot(onestop_offline, tmp_path):
    words, fixations = datasets_module.onestop_raw_frames(
        tmp_path, regime="repeated", download=True
    )
    ws = data_module.propose_word_schema(words)
    fs = data_module.propose_fix_schema(fixations)
    assert data_module.validate_word_schema(ws) == []
    assert data_module.validate_fix_schema(fs) == []
    nw = data_module.normalize_words(words, ws)
    nf = data_module.normalize_fixations(fixations, fs)
    nw, nf = data_module.harmonize_frames(nw, nf)
    fig = sps.plot_scanpath(nw, nf)
    assert len(fig.data) > 0


def test_onestop_present(onestop_offline, tmp_path):
    assert datasets_module.onestop_present(tmp_path, regime="ordinary") is False
    datasets_module.download_onestop(tmp_path, regime="ordinary")
    assert datasets_module.onestop_present(tmp_path, regime="ordinary") is True
    # A different regime's reports aren't there yet.
    assert datasets_module.onestop_present(tmp_path, regime="repeated") is False


def test_onestop_bad_regime():
    with pytest.raises(ValueError, match="regime must be one of"):
        datasets_module.onestop_raw_frames("x", regime="bogus")


def test_onestop_missing_report_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="download=True"):
        datasets_module.onestop_raw_frames(tmp_path, regime="ordinary")


class TestPinnedDownloads:
    """A download names one OSF file version (and one commit of the
    PoTeC repo), and a file that is not that version is refused — or two users
    could open two different corpora under one name, and the dataset table's
    published figures would describe neither."""

    def test_every_onestop_report_is_pinned(self):
        resources = {
            *(
                r
                for kinds in datasets_module._ONESTOP_FULL_OSF.values()
                for r in kinds.values()
            ),
            *(
                r
                for kinds in datasets_module._ONESTOP_REGIMES.values()
                for r in kinds.values()
            ),
        }
        assert resources == set(datasets_module._ONESTOP_OSF_SIZES)

    def test_a_pinned_url_names_its_version(self):
        pin = datasets_module.OsfFile("xkgfz", 1, 177_291_322)
        assert pin.url == "https://osf.io/download/xkgfz/?version=1"
        for pin in datasets_module._POTEC_OSF_RESOURCES.values():
            assert f"/?version={pin.version}" in pin.url
        commit = datasets_module._POTEC_REPO_COMMIT
        assert len(commit) == 40 and f"/{commit}/" in datasets_module._POTEC_RAW_URL

    def test_a_download_of_another_size_is_refused_and_removed(
        self, monkeypatch, tmp_path
    ):
        def fake_fetch(url, dest, *, detail):
            assert "?version=1" in url
            Path(dest).write_bytes(b"not the pinned file")

        monkeypatch.setattr(datasets_module, "_fetch_to_file", fake_fetch)
        with pytest.raises(OSError, match="sent a different file"):
            datasets_module.download_onestop(
                tmp_path, regime="ordinary", parts=["Paragraph"]
            )
        assert not list(tmp_path.glob("*.csv.zip"))

    def test_a_potec_archive_of_another_size_is_refused(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            datasets_module, "_fetch_bytes", lambda url, *, detail: b"short"
        )
        with pytest.raises(OSError, match="sent a different file"):
            datasets_module.download_potec(tmp_path)
        assert not (tmp_path / "eyetracking_data" / "scanpaths").exists()


def test_download_onestop_atomic_and_skips_existing(monkeypatch, tmp_path):
    """download_onestop writes via a temp file (no leftover .part) and skips
    reports already on disk on a re-run."""
    calls = []

    class _FakeResp(io.BytesIO):
        """`download_onestop` reads in chunks (`.read1(size)`), so this has to
        behave like a real response body — `io.BytesIO` does — rather than
        returning the whole payload on every call. It declares no
        Content-Length."""

        def __init__(self, data):
            super().__init__(data)
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, timeout=None, context=None):
        calls.append(url)
        return _FakeResp(_zip_bytes("x.csv", b"a\n1\n"))

    monkeypatch.setattr(datasets_module.urllib.request, "urlopen", fake_urlopen)
    # The fake reports are not the pinned files (see TestPinnedDownloads).
    monkeypatch.setattr(datasets_module, "_check_download_size", lambda *a: None)
    datasets_module.download_onestop(tmp_path, regime="ordinary")

    ia = datasets_module._onestop_report_path(tmp_path, "ia", "ordinary")
    fix = datasets_module._onestop_report_path(tmp_path, "fixations", "ordinary")
    assert ia.is_file() and fix.is_file()
    assert not list(tmp_path.glob("*.part"))  # temp artifact renamed, not left
    assert len(calls) == 2

    # Re-run skips the reports already present (no new downloads).
    datasets_module.download_onestop(tmp_path, regime="ordinary")
    assert len(calls) == 2


def test_onestop_default_part_is_paragraph(onestop_offline, tmp_path):
    words, _ = datasets_module.onestop_raw_frames(
        tmp_path, regime="ordinary", download=True
    )
    assert set(words["part"]) == {"Paragraph"}
    # Single-part load keeps the plain (unfolded) paragraph id.
    assert set(words["unique_paragraph_id"]) == {_FAKE_ONESTOP_PARAGRAPH}


def test_onestop_parts_are_screens_of_one_trial(onestop_offline, tmp_path):
    """A reading's parts are the *screens* of one trial, in presentation
    order — not one trial per part."""
    words, fixations = datasets_module.load_onestop(
        tmp_path,
        regime="ordinary",
        parts=["Title", "Paragraph"],
        download=True,
        names="canonical",
    )
    for frame in (words, fixations):
        assert frame["trial_id"].nunique() == 1
        screens = frame[["screen_id", "screen_index"]].drop_duplicates()
        # Numbered 1..N within the trial, in presentation order.
        assert sorted(map(tuple, screens.to_numpy())) == [
            ("Paragraph", 2),
            ("Title", 1),
        ]
    # Each screen keeps its own words.
    by_screen = words.groupby("screen_id")["text"].agg(set).to_dict()
    assert by_screen == {"Title": {"Bold", "Head"}, "Paragraph": {"The", "cat"}}


def test_onestop_qa_deduplicates(tmp_path):
    """QA repeats rows with the same IA_ID; the loader drops exact duplicates so
    word ids stay unique per trial."""
    ia = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1"],
            "unique_paragraph_id": ["1_Adv_1"] * 3,
            "IA_ID": [1, 1, 2],  # first row duplicated (the QA artifact)
            "IA_LABEL": ["According", "According", "to"],
            "IA_LEFT": [100.0, 100.0, 140.0],
            "IA_RIGHT": [138.0, 138.0, 180.0],
            "IA_TOP": [80.0, 80.0, 80.0],
            "IA_BOTTOM": [110.0, 110.0, 110.0],
        }
    )
    root = datasets_module.Path(tmp_path)
    _write_csv_zip_with_macosx(
        datasets_module._onestop_report_path(root, "ia", "ordinary", "QA"),
        ia,
        "ia_QA.csv",
    )
    _write_csv_zip_with_macosx(
        datasets_module._onestop_report_path(root, "fixations", "ordinary", "QA"),
        pd.DataFrame(
            {
                "participant_id": ["p1"],
                "unique_paragraph_id": ["1_Adv_1"],
                "CURRENT_FIX_INDEX": [1],
                "CURRENT_FIX_X": [110.0],
                "CURRENT_FIX_Y": [95.0],
                "CURRENT_FIX_DURATION": [200.0],
            }
        ),
        "fixations_QA.csv",
    )
    words, _ = datasets_module.onestop_raw_frames(
        tmp_path, regime="ordinary", parts=["QA"]
    )
    # The exact-duplicate IA_ID=1 row is gone → 2 unique words.
    assert len(words) == 2
    assert list(words["IA_ID"]) == [1, 2]


def test_onestop_bad_part(tmp_path):
    with pytest.raises(ValueError, match="Unknown OneStop parts"):
        datasets_module.onestop_raw_frames(tmp_path, parts=["Bogus"])


def test_onestop_bad_variant(tmp_path):
    with pytest.raises(ValueError, match="variant must be one of"):
        datasets_module.onestop_raw_frames(tmp_path, variant="bogus")


def test_onestop_lacclab_variant_paths(tmp_path):
    """The lacclab variant reads plain <kind>_<part>.csv.zip files (no regime
    suffix) from a local folder — no download."""
    _fake_onestop_reports(tmp_path, "ordinary", parts=["Paragraph"], variant="lacclab")
    # The lacclab file name has no regime suffix.
    assert (tmp_path / "ia_Paragraph.csv.zip").is_file()
    assert datasets_module.onestop_present(
        tmp_path, regime="ordinary", parts=["Paragraph"], variant="lacclab"
    )
    words, _fixations = datasets_module.onestop_raw_frames(
        tmp_path, regime="ordinary", parts=["Paragraph"], variant="lacclab"
    )
    assert set(words["part"]) == {"Paragraph"}
    assert list(words["IA_LABEL"]) == ["The", "cat"]


def test_onestop_present_per_part(onestop_offline, tmp_path):
    datasets_module.download_onestop(tmp_path, regime="ordinary", parts=["Paragraph"])
    assert datasets_module.onestop_present(
        tmp_path, regime="ordinary", parts=["Paragraph"]
    )
    # A part that wasn't downloaded is reported missing.
    assert not datasets_module.onestop_present(
        tmp_path, regime="ordinary", parts=["Paragraph", "Title"]
    )


def test_load_onestop_normalized(onestop_offline, tmp_path):
    """The normalized headless loader returns plot-ready frames."""
    words, fixations = datasets_module.load_onestop(
        tmp_path,
        regime="ordinary",
        parts=["Paragraph"],
        download=True,
        names="canonical",
    )
    assert not words.empty
    assert {"participant_id", "trial_id", "word_id", "text"} <= set(words.columns)
    fig = sps.plot_scanpath(words, fixations)
    assert len(fig.data) > 0


# ---------------------------------------------------------------------------
# The public release has no unique_paragraph_id, so the loader composes
# one. Without it `paragraph_id` (the index of the paragraph WITHIN its article,
# 1..7) is the whole text identity, and every article's paragraph 3 is the same
# "text".
# ---------------------------------------------------------------------------


def _onestop_public_report(root, ia, fix, *, regime="ordinary", part="Paragraph"):
    """Write one public-shaped (ia, fixations) pair for ``part`` under ``root``."""
    root = datasets_module.Path(root)
    for kind, frame in (("ia", ia), ("fixations", fix)):
        path = datasets_module._onestop_report_path(root, kind, regime, part)
        _write_csv_zip_with_macosx(path, frame, path.name.removesuffix(".zip"))


def _onestop_public_words(**overrides):
    """A public-shaped IA frame; each keyword overrides one column's values."""
    frame = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            **{key: [value, value] for key, value in _FAKE_ONESTOP_IDS.items()},
            "IA_ID": [1, 2],
            "IA_LABEL": ["The", "cat"],
            "IA_LEFT": [100.0, 140.0],
            "IA_RIGHT": [138.0, 180.0],
            "IA_TOP": [80.0, 80.0],
            "IA_BOTTOM": [110.0, 110.0],
        }
    )
    for column, values in overrides.items():
        frame[column] = values
    return frame


def _onestop_public_fixations(**overrides):
    """A public-shaped fixation frame; each keyword overrides one column."""
    frame = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            **{key: [value, value] for key, value in _FAKE_ONESTOP_IDS.items()},
            "CURRENT_FIX_INDEX": [1, 2],
            "CURRENT_FIX_X": [110.0, 150.0],
            "CURRENT_FIX_Y": [95.0, 95.0],
            "CURRENT_FIX_DURATION": [200.0, 180.0],
        }
    )
    for column, values in overrides.items():
        frame[column] = values
    return frame


def test_onestop_public_composes_a_unique_paragraph_id(onestop_offline, tmp_path):
    """The public reports carry no unique_paragraph_id; the loader builds one
    out of batch + article + paragraph + level, on both frames."""
    words, fixations = datasets_module.onestop_raw_frames(
        tmp_path, regime="ordinary", download=True
    )
    assert set(words["unique_paragraph_id"]) == {_FAKE_ONESTOP_PARAGRAPH}
    assert set(fixations["unique_paragraph_id"]) == {_FAKE_ONESTOP_PARAGRAPH}


def test_onestop_public_composes_a_unique_trial_id(onestop_offline, tmp_path):
    """…and a trial id under it: the reader and the paragraph. A regime is one
    reading, so the reading flag adds nothing to it."""
    words, fixations = datasets_module.onestop_raw_frames(
        tmp_path, regime="ordinary", download=True
    )
    assert set(words["unique_trial_id"]) == {_FAKE_ONESTOP_TRIAL}
    assert set(fixations["unique_trial_id"]) == {_FAKE_ONESTOP_TRIAL}


def test_onestop_composed_ids_match_the_bundled_demo(onestop_offline, tmp_path):
    """The composed ids are the same strings update_sample_data writes into the
    bundled demo — the demo IS a subset of this corpus, so a trial must not
    change identity depending on which of the two you opened."""
    from scanpath_studio import update_sample_data

    words, _ = datasets_module.onestop_raw_frames(
        tmp_path, regime="ordinary", download=True
    )
    demo = update_sample_data.add_unique_ids(
        _onestop_public_words().assign(
            repeated_reading_trial=[False, False],
        )
    )
    assert set(words["unique_paragraph_id"]) == set(demo["unique_paragraph_id"])
    assert set(words["unique_trial_id"]) == set(demo["unique_trial_id"])


@pytest.mark.parametrize("table", ["fixations", "ia", "raw_gaze"])
@pytest.mark.parametrize("suffix", ["csv", "parquet"])
def test_bundled_demo_trial_ids_are_reader_and_paragraph(table, suffix):
    """The demo holds first readings only, so each trial id is the reader and
    the paragraph, with no reading suffix, in every bundled table and format."""
    from scanpath_studio import update_sample_data

    path = update_sample_data.DEFAULT_OUTPUT_DIR / f"{table}.{suffix}"
    frame = pd.read_csv(path) if suffix == "csv" else pd.read_parquet(path)
    ids = frame["unique_trial_id"].astype(str)
    assert not ids.str.contains(r"_r\d+$").any()
    if "unique_paragraph_id" in frame.columns:
        expected = (
            frame["participant_id"].astype(str)
            + "_"
            + frame["unique_paragraph_id"].astype(str)
        )
        assert (ids == expected).all()


def test_demo_builder_composes_reader_and_paragraph():
    from scanpath_studio import update_sample_data

    demo = update_sample_data.add_unique_ids(
        _onestop_public_words().assign(repeated_reading_trial=[False, False])
    )
    assert set(demo["unique_trial_id"]) == {_FAKE_ONESTOP_TRIAL}


def test_onestop_paragraph_three_of_two_articles_is_two_texts(tmp_path):
    """The bug itself: paragraph 3 of article 1 and paragraph 3 of article 27
    are different texts, and normalization must see them that way."""
    _onestop_public_report(
        tmp_path,
        _onestop_public_words(article_id=[1, 27], paragraph_id=[3, 3]),
        _onestop_public_fixations(article_id=[1, 27], paragraph_id=[3, 3]),
    )
    words, fixations = datasets_module.load_onestop(
        tmp_path, regime="ordinary", names="canonical"
    )
    assert words["text_id"].nunique() == 2
    assert fixations["text_id"].nunique() == 2


def test_onestop_repeated_regime_ids_carry_no_reading_suffix(tmp_path):
    """The repeated regime holds second readings only — one per reader and
    paragraph — so its trial ids are reader + paragraph, as in the other
    regimes."""
    _onestop_public_report(
        tmp_path,
        _onestop_public_words(repeated_reading_trial=[True, True]),
        _onestop_public_fixations(repeated_reading_trial=[True, True]),
        regime="repeated",
    )
    words, fixations = datasets_module.onestop_raw_frames(tmp_path, regime="repeated")
    assert set(words["unique_trial_id"]) == {_FAKE_ONESTOP_TRIAL}
    assert set(fixations["unique_trial_id"]) == {_FAKE_ONESTOP_TRIAL}


def test_onestop_repeated_reading_is_its_own_trial(tmp_path):
    """A report that mixes both readings of a paragraph — the same text, read
    twice — gives two trials, told apart by the flag rather than by their order
    on disk."""
    _onestop_public_report(
        tmp_path,
        _onestop_public_words(repeated_reading_trial=[0, 1], IA_ID=[1, 1]),
        _onestop_public_fixations(repeated_reading_trial=[0, 1]),
    )
    words, _ = datasets_module.load_onestop(
        tmp_path, regime="ordinary", names="canonical"
    )
    assert words["text_id"].nunique() == 1
    assert set(words["trial_id"]) == {
        f"p1_{_FAKE_ONESTOP_PARAGRAPH}_r0",
        f"p1_{_FAKE_ONESTOP_PARAGRAPH}_r1",
    }


def test_onestop_keeps_the_lab_exports_own_paragraph_id(tmp_path):
    """The lacclab export ships its own unique_paragraph_id (in its own field
    order). That is the publisher's id — compose the trial id under it, don't
    overwrite it."""
    _fake_onestop_reports(
        tmp_path, "ordinary", parts=["Paragraph"], variant="lacclab", shape="lacclab"
    )
    words, _ = datasets_module.onestop_raw_frames(
        tmp_path, regime="ordinary", parts=["Paragraph"], variant="lacclab"
    )
    assert set(words["unique_paragraph_id"]) == {"3_2_Adv_1"}
    assert set(words["unique_trial_id"]) == {"p1_3_2_Adv_1"}


def test_onestop_without_the_composing_columns_is_left_alone(tmp_path):
    """A report missing one of the composing columns gets no invented id — the
    loader falls back to whatever identity the frame already carries."""
    words = _onestop_public_words().drop(columns=["article_batch"])
    fixations = _onestop_public_fixations().drop(columns=["article_batch"])
    _onestop_public_report(tmp_path, words, fixations)
    loaded, _ = datasets_module.onestop_raw_frames(tmp_path, regime="ordinary")
    assert "unique_paragraph_id" not in loaded.columns
    assert "unique_trial_id" not in loaded.columns


# ---------------------------------------------------------------------------
# MultiplEYE-flavoured auto-detect + filename derivation
# ---------------------------------------------------------------------------


def test_auto_detect_multipleye_columns():
    fix = pd.DataFrame(
        {
            "trial_id": ["t"],
            "onset": [100],
            "duration": [50],
            "location_x": [1.0],
            "location_y": [2.0],
            "word_idx": [3],
        }
    )
    sf = data_module.propose_fix_schema(fix)
    assert sf["x"] == "location_x"
    assert sf["y"] == "location_y"
    assert sf["timestamp"] == "onset"
    assert sf["word_id"] == "word_idx"

    words = pd.DataFrame(
        {
            "trial_id": ["t"],
            "word_idx": [0],
            "word": ["a"],
            "top_left_x": [10.0],
            "top_left_y": [20.0],
            "width": [5.0],
            "height": [6.0],
        }
    )
    sw = data_module.propose_word_schema(words)
    assert sw["word_id"] == "word_idx"
    assert sw["x"] == "top_left_x"
    assert sw["y"] == "top_left_y"
    assert not data_module.validate_word_schema(sw)


def test_split_source_file():
    df = pd.DataFrame(
        {"source_file": ["reader0_b0_scanpath", "reader1_b1_scanpath"], "x": [1, 2]}
    )
    out = data_module.split_source_file(df, delimiter="_")
    assert out["file_part_1"].tolist() == ["reader0", "reader1"]
    assert out["file_part_2"].tolist() == ["b0", "b1"]
    assert out["file_part_3"].tolist() == ["scanpath", "scanpath"]


def test_split_source_file_uneven_and_noop():
    df = pd.DataFrame({"source_file": ["a_b_c", "a_b"]})
    out = data_module.split_source_file(df)
    assert out["file_part_3"].tolist() == ["c", ""]  # short names pad with ""
    # No source_file column -> returned unchanged.
    df2 = pd.DataFrame({"x": [1]})
    assert data_module.split_source_file(df2) is df2


def test_extract_columns_from_source_file_named_groups():
    df = pd.DataFrame(
        {
            "source_file": [
                "001_ZH_CH_1_ET1_trial_1_Lit_Alchemist_4_scanpath",
                "no_match",
            ]
        }
    )
    pattern = (
        r"(?P<session>\d+_[A-Z]{2}_[A-Z]{2}_\d+_ET\d+)_.*trial_\d+_"
        r"(?P<stimulus>.+)_scanpath"
    )
    out = data_module.extract_columns_from_source_file(df, pattern)
    assert out["session"].tolist() == ["001_ZH_CH_1_ET1", np.nan] or pd.isna(
        out["session"].iloc[1]
    )
    assert out["stimulus"].iloc[0] == "Lit_Alchemist_4"
    # lowercase folds the captured values (useful for case-insensitive matching).
    low = data_module.extract_columns_from_source_file(df, pattern, lowercase=True)
    assert low["stimulus"].iloc[0] == "lit_alchemist_4"


def test_extract_columns_from_source_file_noops():
    df = pd.DataFrame({"source_file": ["a_b"]})
    # empty pattern, no named groups, uncompilable pattern, and absent column.
    assert data_module.extract_columns_from_source_file(df, "") is df
    assert data_module.extract_columns_from_source_file(df, "a_b") is df  # no groups
    assert data_module.extract_columns_from_source_file(df, "(((") is df  # bad regex
    assert (
        data_module.extract_columns_from_source_file(
            pd.DataFrame({"x": [1]}), "(?P<g>.)"
        )
        is not None
    )


def test_split_and_extract_from_a_column_other_than_source_file():
    # The wizard's "derive from a column" tool isn't pinned to
    # `source_file` — a `page`-style column encoding identity in its own text
    # (e.g. MultiplEYE's question-AOI screens) works the same way.
    df = pd.DataFrame(
        {
            "page": [
                "Lit_Alchemist_4_question_04111_target",
                "Lit_Alchemist_4_question_04111_distractor1",
            ],
            "source_file": ["aoi_export", "aoi_export"],
        }
    )
    split = data_module.split_source_file(df, delimiter="_", column="page")
    assert split["file_part_1"].tolist() == ["Lit", "Lit"]

    out = data_module.extract_columns_from_source_file(
        df, r"question_(?P<question_id>\d+)_(?P<aoi_block>\w+)$", column="page"
    )
    assert out["question_id"].tolist() == ["04111", "04111"]
    assert out["aoi_block"].tolist() == ["target", "distractor1"]

    # `column=` is accepted for signature symmetry with the other two, but a
    # collision is against df's real columns regardless of which one the
    # regex reads from — a group named after an existing column collides...
    assert data_module.source_file_regex_collisions(
        df, r"(?P<page>.)", column="page"
    ) == ["page"]
    # ...one that isn't an existing column name does not.
    assert (
        data_module.source_file_regex_collisions(
            df, r"(?P<question_id>\d+)", column="page"
        )
        == []
    )


def test_aggregate_char_boxes_origin_size():
    # 2 words x 2 chars/word, origin+size boxes; aggregate to one box per word.
    chars = pd.DataFrame(
        {
            "trial_id": ["t"] * 4,
            "word_idx": [0, 0, 1, 1],
            "word": ["AA", "AA", "BB", "BB"],
            "top_left_x": [80, 100, 140, 160],
            "top_left_y": [50, 50, 50, 50],
            "width": [20, 20, 20, 20],
            "height": [30, 30, 30, 30],
            "char_idx": [0, 1, 2, 3],
        }
    )
    schema = dict(
        trial="trial_id",
        word_id="word_idx",
        text="word",
        x="top_left_x",
        y="top_left_y",
        width="width",
        height="height",
    )
    out = data_module.aggregate_char_boxes(chars, schema)
    assert len(out) == 2
    w0 = out[out["word_idx"] == 0].iloc[0]
    assert (w0["top_left_x"], w0["width"], w0["top_left_y"], w0["height"]) == (
        80,
        40,
        50,
        30,
    )


def test_aggregate_char_boxes_with_block_keeps_blocks_apart_and_renumbers():
    # Two blocks (e.g. a question's stem/target answer blocks) each
    # restart their own local word_idx — without block-aware grouping, both
    # blocks' word 0 would silently merge into one box spanning both
    # locations. "stem" sits above "target" (lower y = earlier reading order).
    rows = []
    for block, y0, words in (
        ("stem", 10, [("AA", 0, 0), ("BB", 1, 20)]),
        ("target", 50, [("CC", 0, 0), ("DD", 1, 20)]),
    ):
        for word, word_idx, x0 in words:
            for i, ch in enumerate(word):
                rows.append(
                    {
                        "trial_id": "t1",
                        "block": block,
                        "word_idx": word_idx,
                        "char": ch,
                        "left": x0 + i * 10,
                        "right": x0 + i * 10 + 10,
                        "top": y0,
                        "bottom": y0 + 10,
                    }
                )
    chars = pd.DataFrame(rows)
    schema = dict(
        trial="trial_id",
        word_id="word_idx",
        block="block",
        left="left",
        right="right",
        top="top",
        bottom="bottom",
    )
    out = data_module.aggregate_char_boxes(chars, schema)
    # 4 distinct words survive (not 2 merged ones), renumbered
    # sequentially per screen in block-reading-order (stem's two words first,
    # since it sits above target) then original word-id order within a block.
    assert len(out) == 4
    assert sorted(out["word_idx"].tolist()) == [0, 1, 2, 3]
    by_block = out.set_index("block")
    assert sorted(by_block.loc["stem", "word_idx"].tolist()) == [0, 1]
    assert sorted(by_block.loc["target", "word_idx"].tolist()) == [2, 3]
    # No box spans both blocks' rows (a merged box would run from 10 to 60).
    assert out["top"].max() - out["top"].min() < 50

    # Leaving `block` unmapped keeps the block-blind merge — behavior is
    # unchanged when the field is left unused.
    schema_noblock = {k: v for k, v in schema.items() if k != "block"}
    legacy = data_module.aggregate_char_boxes(chars, schema_noblock)
    assert len(legacy) == 2


def test_aggregate_char_boxes_edges_and_noop():
    chars = pd.DataFrame(
        {
            "trial_id": ["t"] * 2,
            "word_idx": [0, 0],
            "left": [80, 100],
            "right": [100, 120],
            "top": [50, 50],
            "bottom": [80, 80],
        }
    )
    schema = dict(
        trial="trial_id",
        word_id="word_idx",
        left="left",
        right="right",
        top="top",
        bottom="bottom",
    )
    out = data_module.aggregate_char_boxes(chars, schema)
    assert len(out) == 1
    assert (out["left"].iloc[0], out["right"].iloc[0]) == (80, 120)
    # No-op when the word id (or trial) isn't mapped.
    assert data_module.aggregate_char_boxes(chars, dict(schema, word_id=None)) is chars


# ---------------------------------------------------------------------------
# The generic wizard tools on a MultiplEYE-shaped upload (identity from
# source_file)
# ---------------------------------------------------------------------------

# Two characters per "word", 20x30 boxes laid out side by side. Pages reuse the
# SAME coordinates (the real corpus does), so the per-page SCREENS inside one
# stimulus trial are what keep them from overlapping.
_AOI_COLS = [
    "char_idx",
    "char",
    "top_left_x",
    "top_left_y",
    "width",
    "height",
    "char_idx_in_line",
    "line_idx",
    "page",
    "word_idx",
    "word_idx_in_line",
    "word",
]


def _aoi_word(page, word_idx, word, x0):
    """Two char-AOI rows for one word starting at x0 (boxes 20px wide)."""
    return [
        {
            "char_idx": word_idx * 2 + i,
            "char": word[i],
            "top_left_x": x0 + i * 20,
            "top_left_y": 50,
            "width": 20,
            "height": 30,
            "char_idx_in_line": word_idx * 2 + i,
            "line_idx": 0,
            "page": page,
            "word_idx": word_idx,
            "word_idx_in_line": word_idx,
            "word": word,
        }
        for i in range(2)
    ]


def _scan_row(onset, dur, x, y, page, word_idx):
    return {
        "onset": onset,
        "duration": dur,
        "name": "fixation",
        "location_x": x,
        "location_y": y,
        "page": page,
        "word_idx": word_idx,
    }


def _upload_frame(rows_by_file, columns=None):
    """Concatenate per-file rows, tagging each with source_file (filename stem) —
    mimicking ``data.read_tables`` on a multi-file upload."""
    frames = []
    for stem, rows in rows_by_file.items():
        df = pd.DataFrame(rows, columns=columns)
        df["source_file"] = stem
        frames.append(df)
    return pd.concat(frames, ignore_index=True, sort=False)


def _aoi_pages(*specs):
    """Flatten (page, word_idx, word, x0) specs into AOI char rows."""
    rows = []
    for page, word_idx, word, x0 in specs:
        rows.extend(_aoi_word(page, word_idx, word, x0))
    return rows


def test_generic_wizard_tools_load_a_multipleye_shaped_upload():
    # The wizard's generic tools — column-derive via
    # extract_columns_from_source_file, character-AOI aggregation and
    # api.load_scanpath_data — build one reading of a stimulus, its pages as
    # screens, from the file names alone. Case is folded on both derived
    # columns (the CamelCase scanpath name and the lowercase AOI name), so the
    # two tables meet on the same trial.
    from scanpath_studio import api

    scan = _upload_frame(
        {
            "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath": [
                _scan_row(1000, 200, 90, 65, "page_1", 0),
                _scan_row(1300, 180, 150, 65, "page_1", 1),
                _scan_row(2000, 210, 90, 65, "page_2", 0),
            ]
        }
    )
    aoi = _upload_frame(
        {
            "lit_demo_1_aoi": _aoi_pages(
                ("page_1", 0, "AA", 80),
                ("page_1", 1, "BB", 140),
                ("page_2", 0, "CC", 80),
            )
        },
        columns=_AOI_COLS,
    )

    fix_raw = data_module.extract_columns_from_source_file(
        scan,
        r"^(?P<session>\d+_[A-Za-z]{2}_[A-Za-z]{2}_\d+_ET\d+)_"
        r"(?:(?P<practice>PRACTICE)_)?trial_(?P<trial_num>\d+)_"
        r"(?P<stimulus>.+)_(?P<kind>fixation|scanpath)$",
        lowercase=True,
    )
    aoi_raw = data_module.extract_columns_from_source_file(
        aoi, r"(?P<stimulus>.+)_aoi$", lowercase=True
    )
    word_schema = {
        "trial": "stimulus",
        "text_id": "stimulus",
        "word_id": "word_idx",
        "text": "word",
        "line": "line_idx",
        "x": "top_left_x",
        "y": "top_left_y",
        "width": "width",
        "height": "height",
        "screen_id": "page",
    }
    aoi_raw = data_module.aggregate_char_boxes(aoi_raw, word_schema)
    fix_schema = {
        "participant": "session",
        "trial": "stimulus",
        "text_id": "stimulus",
        "duration": "duration",
        "timestamp": "onset",
        "x": "location_x",
        "y": "location_y",
        "word_id": "word_idx",
        "screen_id": "page",
    }
    words, fixations = api.load_scanpath_data(
        words=aoi_raw,
        fixations=fix_raw,
        word_schema=word_schema,
        fix_schema=fix_schema,
        names="canonical",
    )

    assert len(words) == 3  # one box per word: AA, BB on page 1, CC on page 2
    assert len(fixations) == 3
    assert set(words["trial_id"]) == {"lit_demo_1"}
    assert set(fixations["participant_id"]) == {"001_zh_ch_1_et1"}
    assert set(words["screen_id"]) == {"page_1", "page_2"}
    assert set(fixations["screen_id"]) == {"page_1", "page_2"}


def test_extract_columns_skips_existing_columns():
    # A named group that collides with a real column must NOT clobber it.
    df = pd.DataFrame({"source_file": ["p1_t1"], "duration": [123.0]})
    out = data_module.extract_columns_from_source_file(
        df, r"(?P<duration>p\d+)_(?P<trial>t\d+)"
    )
    assert out["duration"].tolist() == [123.0]  # real data preserved
    assert out["trial"].tolist() == ["t1"]  # non-colliding group still added
    assert data_module.source_file_regex_collisions(df, r"(?P<duration>.)") == [
        "duration"
    ]


def test_aggregate_char_boxes_feeds_normalize_words():
    # The aggregation output must be consumable by normalize_words (same schema).
    chars = pd.DataFrame(
        {
            "trial_id": ["t"] * 4,
            "word_idx": [0, 0, 1, 1],
            "word": ["AA", "AA", "BB", "BB"],
            "top_left_x": [80, 100, 140, 160],
            "top_left_y": [50] * 4,
            "width": [20] * 4,
            "height": [30] * 4,
        }
    )
    schema = dict(
        trial="trial_id",
        word_id="word_idx",
        text="word",
        x="top_left_x",
        y="top_left_y",
        width="width",
        height="height",
    )
    words = data_module.normalize_words(
        data_module.aggregate_char_boxes(chars, schema), schema
    )
    assert len(words) == 2
    w0 = words[words["word_id"] == 0].iloc[0]
    assert (w0["x"], w0["width"], w0["y"], w0["height"]) == (80, 40, 50, 30)


def test_extract_columns_feeds_trial_mapping():
    # Regex-extracted columns must work as trial / participant mappings.
    fix = pd.DataFrame(
        {
            "source_file": ["p1_t1_scan", "p1_t2_scan"],
            "x": [1.0, 2.0],
            "y": [1.0, 1.0],
            "duration_ms": [10, 10],
        }
    )
    out = data_module.extract_columns_from_source_file(
        fix, r"(?P<pid>p\d+)_(?P<trial>t\d+)_scan"
    )
    norm = data_module.normalize_fixations(
        out,
        dict(participant="pid", trial="trial", x="x", y="y", duration="duration_ms"),
    )
    assert set(norm["trial_id"]) == {"t1", "t2"}
    assert set(norm["participant_id"]) == {"p1"}


# ---------------------------------------------------------------------------
# Column keep-list / pruning (perf core)
# ---------------------------------------------------------------------------


def test_keep_columns_prunes_normalized_frame():
    words = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "word_id": [1, 2],
            "IA_LEFT": [0, 10],
            "IA_RIGHT": [10, 20],
            "IA_TOP": [0, 0],
            "IA_BOTTOM": [10, 10],
            "IA_LABEL": ["a", "b"],
            "gpt2_surprisal": [1.0, 2.0],
            "difficulty_level": ["Adv", "Adv"],
            "junk": [9, 9],
        }
    )
    schema = data_module.propose_word_schema(words)

    # Default (keep_columns=None): all detected optional fields kept, junk dropped.
    full = data_module.normalize_words(words, schema)
    assert "gpt2_surprisal" in full.columns
    assert "difficulty_level" in full.columns
    assert "junk" not in full.columns

    # Pruned: only the chosen optional + explicit extra keep survive.
    keep = data_module.compute_keep_columns(
        schema, optional_sources=["gpt2_surprisal"], keep_columns=["junk"]
    )
    thin = data_module.normalize_words(words, schema, keep_columns=keep)
    assert "gpt2_surprisal" in thin.columns
    assert "junk" in thin.columns  # carried verbatim
    assert "difficulty_level" not in thin.columns  # detected but not chosen


def test_categorize_columns_splits_mapped_detected_unclaimed():
    words = pd.DataFrame(
        {
            "participant_id": ["p1"],
            "trial_id": ["t1"],
            "word_id": [1],
            "x": [0],
            "y": [0],
            "width": [1],
            "height": [1],
            "gpt2_surprisal": [1.0],
            "my_custom_col": [3],
        }
    )
    schema = data_module.propose_word_schema(words)
    cats = data_module.categorize_columns(
        words, schema, data_module.WORD_OPTIONAL_FIELDS
    )
    assert "participant_id" in cats["mapped"]
    assert any(d["source"] == "gpt2_surprisal" for d in cats["detected_optional"])
    assert "my_custom_col" in cats["unclaimed"]


# --- The comparison-dataset readiness gate -----------------------------------
# The one hard constraint on the secondary loader is that it must not RENDER —
# the app's public-corpus loaders draw directory inputs and ⬇ Download buttons,
# none of which can appear inside the compare picker. So a corpus whose files
# aren't already where the main picker last looked is offered *disabled*, and is
# never loaded blind (which would fall back to the demo, silently comparing
# against the wrong data).


def _secondary_options_app():
    import streamlit as st

    from scanpath_studio.compare_source import (
        load_secondary_dataset,
        secondary_dataset_options,
    )

    st.session_state["potec_dir"] = "/nonexistent/potec"
    st.session_state["_datasets"] = {"My upload": {"words": None, "fixations": None}}
    options = secondary_dataset_options()
    st.session_state["_options"] = options
    # A corpus that isn't present must come back as None rather than loading
    # something else in its place.
    st.session_state["_loaded_absent"] = load_secondary_dataset(
        next(name for name, ready, _ in options if not ready and "PoTeC" in name)
    )


def test_a_missing_public_corpus_is_offered_but_disabled_never_loaded():
    apptest = pytest.importorskip("streamlit.testing.v1")
    at = apptest.AppTest.from_function(_secondary_options_app)
    at.run(timeout=30)
    assert not at.exception, at.exception

    options = {name: (ready, why) for name, ready, why in at.session_state["_options"]}
    potec = next(name for name in options if "PoTeC" in name)
    ready, why = options[potec]
    assert ready is False
    assert "as the main dataset" in why  # names the fix, not just the failure
    assert at.session_state["_loaded_absent"] is None
    # The always-available sources are offered ready.
    assert options["Bundled demo"][0] is True
    assert options["Synthetic test trial"][0] is True
    assert options["My upload"][0] is True


def test_this_dataset_and_unknown_names_load_to_none():
    from scanpath_studio.compare_source import THIS_DATASET, load_secondary_dataset

    assert load_secondary_dataset(None) is None
    assert load_secondary_dataset(THIS_DATASET) is None


def _secondary_load_app():
    """Load the bundled demo as a comparison source and inspect what came back."""
    import streamlit as st

    from scanpath_studio.compare_source import load_secondary_dataset

    source = load_secondary_dataset("Bundled demo")
    st.session_state["_name"] = source.name
    st.session_state["_rows"] = len(source.fixations)
    st.session_state["_trials"] = len(source.combos)
    st.session_state["_canvas"] = source.setup.canvas
    st.session_state["_screen_prov"] = str(source.setup.screen_provenance)


def test_a_built_in_source_loads_with_its_own_combos_and_screen():
    """The loader must answer for *B's* geometry, never the live `global_*` keys
    (which describe A) — the demo declares a 2560x1440 monitor, so that is what
    comes back regardless of what the session's canvas is set to."""
    apptest = pytest.importorskip("streamlit.testing.v1")
    at = apptest.AppTest.from_function(_secondary_load_app)
    at.run(timeout=60)
    assert not at.exception, at.exception

    assert at.session_state["_name"] == "Bundled demo"
    assert at.session_state["_rows"] > 0
    assert at.session_state["_trials"] > 0
    assert at.session_state["_canvas"] == (2560, 1440)
    assert at.session_state["_screen_prov"] == "measured"


def _secondary_stored_upload_app():
    """A stored upload carries the snapshot its wizard captured."""
    import streamlit as st

    from scanpath_studio import api
    from scanpath_studio.compare_source import load_secondary_dataset
    from scanpath_studio.data import load_sample_data
    from scanpath_studio.experimental_setup import Provenance, SetupSnapshot

    words, fixations = api.load_scanpath_data(*load_sample_data(), names="canonical")
    st.session_state["_datasets"] = {
        "My upload": {
            "words": words,
            "fixations": fixations,
            "raw_gaze": None,
            "composite_trial_columns": [],
            "setup": SetupSnapshot(
                canvas_width=1280,
                canvas_height=1024,
                screen_provenance=Provenance.ESTIMATED,
            ).to_dict(),
        }
    }
    source = load_secondary_dataset("My upload")
    st.session_state["_canvas"] = source.setup.canvas
    st.session_state["_prov"] = str(source.setup.screen_provenance)


def test_a_stored_upload_reports_the_setup_its_wizard_captured():
    apptest = pytest.importorskip("streamlit.testing.v1")
    at = apptest.AppTest.from_function(_secondary_stored_upload_app)
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert at.session_state["_canvas"] == (1280, 1024)
    assert at.session_state["_prov"] == "estimated"


# ---------------------------------------------------------------------------
# One dataset per regime. Only Paragraph is regime-split on OSF, so a
# regime's other parts are the all-regimes reports cut by the corpus' own flags.
# ---------------------------------------------------------------------------


def test_a_regime_lists_every_part_it_shows():
    assert datasets_module.onestop_regime_parts("information_seeking") == [
        p for p in datasets_module._ONESTOP_PARTS if p != "QA"
    ]
    # QA is Questions + Answers as one interest period — not a screen, so no
    # regime's dataset loads it.
    for regime in datasets_module._ONESTOP_REGIME_FLAGS:
        assert "QA" not in datasets_module.onestop_regime_parts(regime)
    # Only the information-seeking regimes show the question first.
    assert "Question_Preview" not in datasets_module.onestop_regime_parts("ordinary")
    with pytest.raises(ValueError):
        datasets_module.onestop_regime_parts("speed_reading")


@pytest.mark.parametrize(
    ("regime", "kept"),
    [
        ("ordinary", "p00"),
        ("information_seeking", "p10"),
        ("repeated", "p01"),
        ("information_seeking_repeated", "p11"),
    ],
)
def test_an_all_regimes_part_is_cut_to_the_regime(tmp_path, regime, kept):
    """A QA report holding all four regimes keeps only the asked regime's rows."""
    flags = {"question_preview": [], "repeated_reading_trial": [], "pid": []}
    for preview in (False, True):
        for repeated in (False, True):
            flags["question_preview"] += [preview, preview]
            flags["repeated_reading_trial"] += [repeated, repeated]
            flags["pid"] += [f"p{int(preview)}{int(repeated)}"] * 2

    def _four(frame):
        frame = pd.concat([frame] * 4, ignore_index=True)
        frame["participant_id"] = flags["pid"]
        frame["question_preview"] = flags["question_preview"]
        frame["repeated_reading_trial"] = flags["repeated_reading_trial"]
        return frame

    _onestop_public_report(
        tmp_path,
        _four(_onestop_public_words()),
        _four(_onestop_public_fixations()),
        regime=regime,
        part="QA",
    )
    words, fixations = datasets_module.onestop_raw_frames(
        tmp_path, regime=regime, parts=["QA"]
    )
    assert set(words["participant_id"]) == {kept}
    assert set(fixations["participant_id"]) == {kept}


def test_a_screen_only_one_report_has_is_dropped_not_fatal(tmp_path, caplog):
    """The OSF Answers fixation report holds a trial its interest-area report
    lacks. Several parts make each part a screen, and one such orphan must not
    abort the whole load in `multipart.validate_matching_parts`."""
    _onestop_public_report(
        tmp_path, _onestop_public_words(), _onestop_public_fixations()
    )
    orphan = _onestop_public_fixations(participant_id=["p2", "p2"])
    _onestop_public_report(
        tmp_path,
        _onestop_public_words(),
        pd.concat([_onestop_public_fixations(), orphan], ignore_index=True),
        part="Answers",
    )
    with caplog.at_level("WARNING", logger="scanpath_studio.datasets"):
        words, fixations = datasets_module.load_onestop(
            tmp_path,
            regime="ordinary",
            parts=["Paragraph", "Answers"],
            names="canonical",
        )
    assert set(fixations["participant_id"]) == {"p1"}
    assert set(words["participant_id"]) == {"p1"}
    assert "the other report does not have" in caplog.text
