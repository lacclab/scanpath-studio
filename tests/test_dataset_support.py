"""Tests for flexible dataset support: multi-file inputs, single-report
datasets (words-only / fixations-only), stimulus-level word tables, AOI-only
fixations, and the PoTeC loader."""

import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

import scanpath_studio as sps
from scanpath_studio import data as data_module
from scanpath_studio import datasets as datasets_module
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
    locally while a full report kills the cloud worker. Regression guard."""
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
    # The real bug: an in-memory upload named *.csv.zip — pandas infers
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
    with pytest.raises(ValueError, match="no readable table files"):
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
    words, fixations = sps.load_scanpath_data(fixations=[p1, p2])
    assert words.empty
    assert set(fixations["participant_id"]) == {"p0", "p1"}
    # the origin file survives normalization for traceability
    assert set(fixations["source_file"]) == {"f1", "f2"}


# ---------------------------------------------------------------------------
# Single-report datasets
# ---------------------------------------------------------------------------


def test_load_scanpath_data_requires_some_input():
    with pytest.raises(ValueError, match="at least one"):
        sps.load_scanpath_data()


def test_fixations_only_load_list_and_plot(tmp_path):
    path = tmp_path / "fix.csv"
    _write_fix_csv(path, "p0", "t1")
    words, fixations = sps.load_scanpath_data(fixations=path)
    assert words.empty and not fixations.empty

    combos = sps.list_trials(words, fixations)
    assert combos.to_records(index=False).tolist() == [("p0", "t1")]

    fig = sps.plot_scanpath(words, fixations, "p0", "t1")
    assert len(fig.data) > 0


def test_words_only_load_list_and_plot(sample_words_df):
    words, fixations = sps.load_scanpath_data(words=sample_words_df)
    assert fixations.empty and not words.empty

    combos = sps.list_trials(words, fixations)
    assert ("p1", "t1") in {tuple(r) for r in combos.to_numpy()}

    fig = sps.plot_scanpath(words, fixations, "p1", "t1")
    assert len(fig.data) > 0


def test_words_only_heatmap_uses_preaggregated_measures(sample_words_df):
    sample_words_df = sample_words_df.copy()
    sample_words_df["IA_DWELL_TIME"] = [500, 250, 0, 100, 100]
    words, fixations = sps.load_scanpath_data(words=sample_words_df)
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
            show_colorbars=False,
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
    words, fixations = sps.load_scanpath_data(fixations=path)
    filters = data_module.default_filters(words, fixations)
    assert filters["participants"] == ["p0"]
    assert filters["trials"] == ["t1"]
    w, f = data_module.filter_data(words, fixations, filters)
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
        words=stimulus_words_df, fixations=aoi_fixations_df
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
    words, fixations = sps.load_scanpath_data(words=stimulus_words_df)
    # No fixations to broadcast across → a single anonymous reader.
    assert (words["participant_id"] == data_module.SYNTHETIC_PARTICIPANT).all()
    assert data_module.STIMULUS_WORDS_FLAG not in words.columns


def test_aoi_fixations_without_words_raise_on_plot(aoi_fixations_df):
    words, fixations = sps.load_scanpath_data(fixations=aoi_fixations_df)
    assert fixations["x"].isna().all()
    with pytest.raises(ValueError, match="no usable coordinates"):
        sps.plot_scanpath(words, fixations, "7", "t1")


def test_fix_schema_requires_xy_or_word_id():
    no_position = pd.DataFrame(
        {"participant_id": ["p"], "trial_id": ["t"], "duration_ms": [100]}
    )
    with pytest.raises(ValueError, match="Word/IA ID"):
        sps.load_scanpath_data(fixations=no_position)


def test_participant_less_fixations_get_synthetic_participant():
    """A fixations table with no participant column loads (participant is now
    optional) and every row is stamped with the synthetic participant."""
    fixations = pd.DataFrame(
        {
            "trial_id": ["t1", "t1", "t2"],
            "x": [10.0, 20.0, 30.0],
            "y": [5.0, 5.0, 5.0],
            "duration_ms": [100, 120, 90],
        }
    )
    _words, fix = sps.load_scanpath_data(fixations=fixations)
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
    words_n, fix_n = sps.load_scanpath_data(words=words, fixations=fixations)
    assert set(fix_n["participant_id"]) == {data_module.SYNTHETIC_PARTICIPANT}
    assert set(words_n["participant_id"]) == {data_module.SYNTHETIC_PARTICIPANT}
    # The boxes for the trial the picker offers ('(all)', 't1') are now reachable.
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
    words, fixations = datasets_module.load_potec(potec_root, texts=["b0"])

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

    fig = sps.plot_scanpath(words, fixations, "1", "b0", canvas_size=(1680, 1050))
    assert len(fig.data) > 0


def test_load_potec_reader_subset(potec_root):
    words, fixations = datasets_module.load_potec(potec_root, readers=[1], texts=["b0"])
    assert set(fixations["participant_id"]) == {"1"}
    assert set(words["participant_id"]) == {"1"}


def test_load_potec_unknown_text(potec_root):
    with pytest.raises(ValueError, match="Unknown PoTeC text ids"):
        datasets_module.load_potec(potec_root, texts=["z9"])


def test_load_potec_missing_data_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="download=True"):
        datasets_module.load_potec(tmp_path, texts=["b0"])


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


def _fake_onestop_reports(root, regime):
    """Write minimal OneStop-shaped IA + fixation reports for ``regime``."""
    ia = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "unique_paragraph_id": ["1_Adv_1", "1_Adv_1"],
            "IA_ID": [1, 2],
            "IA_LABEL": ["The", "cat"],
            "IA_LEFT": [100.0, 140.0],
            "IA_RIGHT": [138.0, 180.0],
            "IA_TOP": [80.0, 80.0],
            "IA_BOTTOM": [110.0, 110.0],
            "difficulty_level": ["Adv", "Adv"],
        }
    )
    fix = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "unique_paragraph_id": ["1_Adv_1", "1_Adv_1"],
            "CURRENT_FIX_INDEX": [1, 2],
            "CURRENT_FIX_X": [110.0, 150.0],
            "CURRENT_FIX_Y": [95.0, 95.0],
            "CURRENT_FIX_DURATION": [200.0, 180.0],
        }
    )
    root = datasets_module.Path(root)
    root.mkdir(parents=True, exist_ok=True)
    _write_csv_zip_with_macosx(
        datasets_module._onestop_report_path(root, "ia", regime),
        ia,
        f"ia_Paragraph_{regime}.csv",
    )
    _write_csv_zip_with_macosx(
        datasets_module._onestop_report_path(root, "fixations", regime),
        fix,
        f"fixations_Paragraph_{regime}.csv",
    )


@pytest.fixture
def onestop_offline(monkeypatch):
    """Replace download_onestop with a network-free report writer."""

    def fake_download(root, *, regime="ordinary"):
        _fake_onestop_reports(root, regime)
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


def test_onestop_bad_regime():
    with pytest.raises(ValueError, match="regime must be one of"):
        datasets_module.onestop_raw_frames("x", regime="bogus")


def test_onestop_missing_report_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="download=True"):
        datasets_module.onestop_raw_frames(tmp_path, regime="ordinary")


def test_download_onestop_atomic_and_skips_existing(monkeypatch, tmp_path):
    """download_onestop writes via a temp file (no leftover .part) and skips
    reports already on disk on a re-run."""
    calls = []

    class _FakeResp:
        def __init__(self, data):
            self._data = data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._data

    def fake_urlopen(url):
        calls.append(url)
        return _FakeResp(_zip_bytes("x.csv", b"a\n1\n"))

    monkeypatch.setattr(datasets_module.urllib.request, "urlopen", fake_urlopen)
    datasets_module.download_onestop(tmp_path, regime="ordinary")

    ia = datasets_module._onestop_report_path(tmp_path, "ia", "ordinary")
    fix = datasets_module._onestop_report_path(tmp_path, "fixations", "ordinary")
    assert ia.is_file() and fix.is_file()
    assert not list(tmp_path.glob("*.part"))  # temp artifact renamed, not left
    assert len(calls) == 2

    # Re-run skips the reports already present (no new downloads).
    datasets_module.download_onestop(tmp_path, regime="ordinary")
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# MultiplEYE loader (against a tiny synthesized MultiplEYE-format tree)
# ---------------------------------------------------------------------------

# Two characters per "word", 20x30 boxes laid out side by side. Pages reuse the
# SAME coordinates (the real corpus does), so per-page trials are what keep them
# from overlapping.
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


@pytest.fixture
def multipleye_root(tmp_path):
    """A minimal MultiplEYE-shaped tree: two sessions reading disjoint stimuli.

    001_ZH_CH_1_ET1 reads Lit_Demo_1 (2 pages, reusing the same coords);
    014_ZH_CH_1_ET2 reads Arg_Other_2 (1 page). The raw fixations/ file carries a
    non-reading ``question_*`` screen that must be filtered out."""
    aoi_dir = tmp_path / "stimuli_Demo" / "aoi_stimuli_demo"
    aoi_dir.mkdir(parents=True)

    # Lit_Demo_1: page_1 = AA BB, page_2 = CC DD (same coords as page_1).
    rows = (
        _aoi_word("page_1", 0, "AA", 80)
        + _aoi_word("page_1", 1, "BB", 140)
        + _aoi_word("page_2", 0, "CC", 80)
        + _aoi_word("page_2", 1, "DD", 140)
    )
    pd.DataFrame(rows, columns=_AOI_COLS).to_csv(
        aoi_dir / "lit_demo_1_aoi.csv", index=False
    )
    pd.DataFrame(_aoi_word("page_1", 0, "EE", 80), columns=_AOI_COLS).to_csv(
        aoi_dir / "arg_other_2_aoi.csv", index=False
    )

    s1 = "001_ZH_CH_1_ET1"
    scan1 = tmp_path / "scanpaths" / s1
    fix1 = tmp_path / "fixations" / s1
    scan1.mkdir(parents=True)
    fix1.mkdir(parents=True)
    pd.DataFrame(
        [
            _scan_row(1000, 200, 90, 65, "page_1", 0),
            _scan_row(1300, 180, 150, 65, "page_1", 1),
            _scan_row(2000, 210, 90, 65, "page_2", 0),
        ]
    ).to_csv(scan1 / f"{s1}_trial_1_Lit_Demo_1_scanpath.csv", index=False)
    # Raw fixations/: no word_idx, and a question_* screen to be filtered.
    pd.DataFrame(
        [
            {
                "onset": 1000,
                "duration": 200,
                "location_x": 90,
                "location_y": 65,
                "page": "page_1",
            },
            {
                "onset": 1500,
                "duration": 100,
                "location_x": 500,
                "location_y": 500,
                "page": "question_1",
            },
            {
                "onset": 2000,
                "duration": 210,
                "location_x": 90,
                "location_y": 65,
                "page": "page_2",
            },
        ]
    ).to_csv(fix1 / f"{s1}_trial_1_Lit_Demo_1_fixation.csv", index=False)

    s2 = "014_ZH_CH_1_ET2"
    scan2 = tmp_path / "scanpaths" / s2
    scan2.mkdir(parents=True)
    pd.DataFrame([_scan_row(500, 150, 90, 65, "page_1", 0)]).to_csv(
        scan2 / f"{s2}_trial_1_Arg_Other_2_scanpath.csv", index=False
    )
    return tmp_path


def test_load_multipleye(multipleye_root):
    words, fixations = datasets_module.load_multipleye(multipleye_root)

    # Reader key = full session; ET1/ET2 are distinct readers.
    assert set(fixations["participant_id"]) == {"001_ZH_CH_1_ET1", "014_ZH_CH_1_ET2"}
    # One trial per (stimulus, page); the page is zero-padded so trials sort
    # numerically (page_01 < page_02 < … < page_10).
    assert set(words["trial_id"]) == {
        "Lit_Demo_1__page_01",
        "Lit_Demo_1__page_02",
        "Arg_Other_2__page_01",
    }
    # text_id stays the stimulus (for stimulus-level merges/grouping).
    assert set(words["text_id"]) == {"Lit_Demo_1", "Arg_Other_2"}

    # Char AOIs aggregated to one box per (page, word_idx): AA spans x 80..120 in
    # image space, shifted to where the centered stimulus sat on the monitor.
    off_x, off_y = datasets_module._MULTIPLEYE_IMAGE_ORIGIN
    aa = words[(words["trial_id"] == "Lit_Demo_1__page_01") & (words["word_id"] == 0)]
    assert aa["text"].iloc[0] == "AA"
    assert aa["x"].iloc[0] == 80 + off_x and aa["width"].iloc[0] == 40
    assert aa["y"].iloc[0] == 50 + off_y and aa["height"].iloc[0] == 30

    # Fixations carry the word index (scanpaths source) and link to boxes.
    f1 = fixations[fixations["participant_id"] == "001_ZH_CH_1_ET1"]
    assert f1["word_id"].notna().all()
    assert sorted(f1["trial_id"].unique()) == [
        "Lit_Demo_1__page_01",
        "Lit_Demo_1__page_02",
    ]

    fig = sps.plot_scanpath(
        words,
        fixations,
        "001_ZH_CH_1_ET1",
        "Lit_Demo_1__page_01",
        canvas_size=(1920, 1080),
    )
    assert len(fig.data) > 0


def test_load_multipleye_pages_are_separate_non_overlapping_trials(multipleye_root):
    # page_1 and page_2 reuse the SAME coordinates but are different trials with
    # different text — proving the per-page split avoids the overlap.
    words, _ = datasets_module.load_multipleye(multipleye_root, stimuli=["Lit_Demo_1"])
    p1 = words[words["trial_id"] == "Lit_Demo_1__page_01"]
    p2 = words[words["trial_id"] == "Lit_Demo_1__page_02"]
    assert set(p1["text"]) == {"AA", "BB"}
    assert set(p2["text"]) == {"CC", "DD"}
    # Same box geometry on both pages.
    assert sorted(p1["x"]) == sorted(p2["x"])


def test_load_multipleye_fixations_source_fallback(multipleye_root):
    # The raw fixations/ files have no word index, and the question_* screen is
    # dropped (3 rows in -> 2 reading-page fixations out).
    words, fixations = datasets_module.load_multipleye(
        multipleye_root, sessions=["001_ZH_CH_1_ET1"], fixation_source="fixations"
    )
    assert fixations["word_id"].isna().all()
    assert fixations["x"].notna().all()
    assert len(fixations) == 2
    assert set(fixations["trial_id"]) == {"Lit_Demo_1__page_01", "Lit_Demo_1__page_02"}


def test_multipleye_centered_offset(multipleye_root):
    _, fixations = datasets_module.load_multipleye(
        multipleye_root, sessions=["001_ZH_CH_1_ET1"], stimuli=["Lit_Demo_1"]
    )
    off_x, off_y = datasets_module._MULTIPLEYE_IMAGE_ORIGIN
    # The centering offset is (screen - image) / 2 = (305, 44.5) for the 1310x991
    # image on the 1920x1080 monitor — image-relative coords are shifted onto the
    # centered on-screen position.
    assert datasets_module.MULTIPLEYE_MONITOR == (1920, 1080)
    assert (off_x, off_y) == (305.0, 44.5)
    f0 = fixations.iloc[0]
    assert f0["x"] == 90 + off_x and f0["y"] == 65 + off_y  # _scan_row(…, 90, 65, …)


def test_multipleye_trial_id_page_is_zero_padded_for_numeric_sort():
    # The page is zero-padded in the trial id so the picker sorts numerically
    # (page_2 before page_10), unlike the raw "page_2" / "page_10" strings.
    assert datasets_module._multipleye_page_label("page_2") == "page_02"
    assert datasets_module._multipleye_page_label("page_10") == "page_10"
    assert (
        datasets_module._multipleye_page_label("question_1") == "question_1"
    )  # passthrough
    pages = ["page_2", "page_10", "page_1"]
    labels = sorted(datasets_module._multipleye_page_label(p) for p in pages)
    assert labels == ["page_01", "page_02", "page_10"]  # lexicographic == numeric


def test_load_multipleye_session_and_stimulus_filters(multipleye_root):
    words, fixations = datasets_module.load_multipleye(
        multipleye_root, sessions=["014_ZH_CH_1_ET2"]
    )
    assert set(fixations["participant_id"]) == {"014_ZH_CH_1_ET2"}
    assert set(words["text_id"]) == {"Arg_Other_2"}


def test_multipleye_raw_frames_auto_detect_path(multipleye_root):
    # The in-app "Public datasets" source feeds multipleye_raw_frames through
    # auto-detection (not the explicit schema), so the raw column names must
    # auto-map to the same result — including text_id = stimulus, not the
    # per-page trial id.
    words_raw, fix_raw = datasets_module.multipleye_raw_frames(
        multipleye_root, sessions=["001_ZH_CH_1_ET1"]
    )
    word_schema = data_module.propose_word_schema(words_raw)
    fix_schema = data_module.propose_fix_schema(fix_raw)
    assert not data_module.validate_word_schema(word_schema)
    assert not data_module.validate_fix_schema(fix_schema)
    assert word_schema["participant"] is None  # stimulus-level -> broadcast
    assert fix_schema["participant"] == "participant_id"  # the session string

    words = data_module.normalize_words(words_raw, word_schema)
    fixations = data_module.normalize_fixations(fix_raw, fix_schema)
    words, fixations = data_module.harmonize_frames(words, fixations)
    assert set(words["text_id"]) == {"Lit_Demo_1"}
    assert set(words["participant_id"]) == {"001_ZH_CH_1_ET1"}  # broadcast worked
    assert set(words["trial_id"]) == {"Lit_Demo_1__page_01", "Lit_Demo_1__page_02"}


def test_multipleye_inventory(multipleye_root):
    sessions, stimuli = datasets_module.multipleye_inventory(multipleye_root)
    assert sessions == ("001_ZH_CH_1_ET1", "014_ZH_CH_1_ET2")
    assert stimuli == ("Arg_Other_2", "Lit_Demo_1")


def test_load_multipleye_missing_aoi_raises(multipleye_root):
    (
        multipleye_root / "stimuli_Demo" / "aoi_stimuli_demo" / "lit_demo_1_aoi.csv"
    ).unlink()
    with pytest.raises(FileNotFoundError, match="AOI file not found"):
        datasets_module.load_multipleye(multipleye_root, stimuli=["Lit_Demo_1"])


def test_load_multipleye_bad_fixation_source(multipleye_root):
    with pytest.raises(ValueError, match="fixation_source"):
        datasets_module.load_multipleye(multipleye_root, fixation_source="saccades")


# Optional end-to-end check against the read-only ZH-CH-Zurich sample, when present.
_MULTIPLEYE_SAMPLE = __import__("pathlib").Path("data/MultiplEYE_ZH_CH_Zurich_1_2025")


@pytest.mark.skipif(
    not _MULTIPLEYE_SAMPLE.is_dir(), reason="MultiplEYE sample not present"
)
def test_load_multipleye_real_sample():
    words, fixations = datasets_module.load_multipleye(
        _MULTIPLEYE_SAMPLE, stimuli=["Lit_Alchemist_4"]
    )
    assert not words.empty and not fixations.empty
    # Per-page trials, all from the one stimulus.
    assert set(words["text_id"]) == {"Lit_Alchemist_4"}
    assert all(t.startswith("Lit_Alchemist_4__page_") for t in words["trial_id"])
    # Pages are zero-padded → lexicographic order == numeric order (no page_10
    # wedged between page_1 and page_2).
    pages = sorted(words["trial_id"].unique())
    nums = [int(t.rsplit("page_", 1)[1]) for t in pages]
    assert nums == sorted(nums)
    # Coords + image sit at the centered on-screen position (true-to-scale on the
    # 1920x1080 monitor), and the image origin matches the coordinate offset.
    off_x, off_y = datasets_module._MULTIPLEYE_IMAGE_ORIGIN
    assert fixations["x"].between(0, 1920).all()
    assert fixations["y"].between(0, 1080).all()
    assert (float(words["image_x"].iloc[0]), float(words["image_y"].iloc[0])) == (
        off_x,
        off_y,
    )
    pid = sorted(fixations["participant_id"])[0]
    tid = sorted(fixations["trial_id"])[0]
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, canvas_size=datasets_module.MULTIPLEYE_MONITOR
    )
    assert len(fig.data) > 0


@pytest.mark.skipif(
    not _MULTIPLEYE_SAMPLE.is_dir(), reason="MultiplEYE sample not present"
)
def test_multipleye_real_sample_stamps_font():
    # The stimulus FONT_SIZE (28) + CJK font are read from the config and stamped,
    # surviving normalization so the app can snap its font controls to them.
    words, fixations = datasets_module.load_multipleye(
        _MULTIPLEYE_SAMPLE, stimuli=["Lit_Alchemist_4"]
    )
    assert float(words["stimulus_font_px"].iloc[0]) == 28.0
    fam = words["stimulus_font_family"].iloc[0]
    assert "Noto Sans Mono CJK SC" in fam
    assert float(fixations["stimulus_font_px"].iloc[0]) == 28.0


def test_multipleye_font_config_and_css(tmp_path):
    cfg = tmp_path / "stimuli_X" / "config"
    cfg.mkdir(parents=True)
    (cfg / "config_zh_ch_X.py").write_text(
        "MAX_CHARS_PER_LINE = 82\n"
        "FONT_SIZE = 28\n"
        'FONT = "fonts/NotoSansMonoCJKsc-VF.ttf"\n',
        encoding="utf-8",
    )
    px, family = datasets_module._multipleye_font_config(tmp_path)
    assert px == 28.0
    assert family == "'Noto Sans Mono CJK SC', 'Noto Sans CJK SC', monospace"
    # Unknown font → humanised name + monospace; "cjk" in the name adds a CJK stack.
    assert datasets_module._multipleye_font_css("CourierPrime.ttf").endswith(
        ", monospace"
    )
    assert "Noto Sans CJK SC" in datasets_module._multipleye_font_css("MyCJKFont.otf")
    # No config under the root → (None, None), no stamping.
    assert datasets_module._multipleye_font_config(tmp_path / "empty") == (None, None)


def test_multipleye_stamps_font_when_config_present(multipleye_root):
    # Drop a config into the synthetic tree → the loader stamps the typeface.
    cfg = multipleye_root / "stimuli_Demo" / "config"
    cfg.mkdir(parents=True)
    (cfg / "config_zh_ch_demo.py").write_text(
        'FONT_SIZE = 22\nFONT = "fonts/NotoSansMonoCJKsc-VF.ttf"\n', encoding="utf-8"
    )
    words, fixations = datasets_module.load_multipleye(multipleye_root)
    assert (words["stimulus_font_px"] == 22.0).all()
    assert words["stimulus_font_family"].str.contains("CJK SC").all()


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
# MultiplEYE browser-upload recipe (identity from source_file)
# ---------------------------------------------------------------------------


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


def test_multipleye_uploads_case_match_join():
    # The load-bearing blocker: scanpath filenames are CamelCase, AOI filenames
    # lowercase — the recipe must relabel AOI stimuli to the CamelCase canonical
    # so the stimulus-words broadcast (inner join on trial_id) keeps the boxes.
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
    words, fixations = datasets_module.load_multipleye_uploads(scan, aoi)
    assert not words.empty  # boxes joined despite the lowercase AOI filename
    assert set(words["text_id"]) == {"Lit_Demo_1"}  # CamelCase canonical, not lowercase
    assert set(words["trial_id"]) <= set(fixations["trial_id"])
    assert set(fixations["participant_id"]) == {"001_ZH_CH_1_ET1"}


def test_multipleye_uploads_fixations_only():
    scan = _upload_frame(
        {
            "014_ZH_CH_1_ET2_trial_1_Arg_Other_2_scanpath": [
                _scan_row(500, 150, 90, 65, "page_1", 0)
            ]
        }
    )
    words, fixations = datasets_module.load_multipleye_uploads(scan, None)
    assert words.empty and not fixations.empty
    assert fixations["x"].notna().all()
    assert set(fixations["trial_id"]) == {"Arg_Other_2__page_01"}


def test_multipleye_uploads_unrecognized_filenames():
    bad = pd.DataFrame(
        {
            "onset": [1],
            "duration": [1],
            "location_x": [1.0],
            "location_y": [1.0],
            "page": ["page_1"],
            "word_idx": [0],
            "source_file": ["just_a_random_filename"],
        }
    )
    words, fixations = datasets_module.multipleye_frames_from_uploads(bad, None)
    assert words.empty and fixations.empty  # empty, not a raise


def test_multipleye_uploads_prefers_scanpath_over_fixation():
    # Both kinds uploaded for the same trial → scanpath wins (carries word_idx),
    # so rows aren't doubled.
    df = pd.concat(
        [
            _upload_frame(
                {
                    "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath": [
                        _scan_row(1000, 200, 90, 65, "page_1", 0)
                    ]
                }
            ),
            _upload_frame(
                {
                    "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_fixation": [
                        {
                            "onset": 1000,
                            "duration": 200,
                            "location_x": 90,
                            "location_y": 65,
                            "page": "page_1",
                        }
                    ]
                }
            ),
        ],
        ignore_index=True,
        sort=False,
    )
    words, fixations = datasets_module.multipleye_frames_from_uploads(df, None)
    assert len(fixations) == 1
    assert fixations["word_idx"].notna().all()


def test_multipleye_uploads_stimulus_without_aoi():
    scan = _upload_frame(
        {
            "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath": [
                _scan_row(1000, 200, 90, 65, "page_1", 0)
            ],
            "001_ZH_CH_1_ET1_trial_2_Arg_Other_2_scanpath": [
                _scan_row(1000, 200, 90, 65, "page_1", 0)
            ],
        }
    )
    aoi = _upload_frame(
        {"lit_demo_1_aoi": _aoi_pages(("page_1", 0, "AA", 80))}, columns=_AOI_COLS
    )
    words, fixations = datasets_module.load_multipleye_uploads(scan, aoi)
    assert "Lit_Demo_1" in set(words["text_id"])  # has boxes
    assert "Arg_Other_2" not in set(words["text_id"])  # no AOI → no boxes, no raise
    assert {"Lit_Demo_1", "Arg_Other_2"} <= set(fixations["text_id"])


def test_multipleye_uploads_match_directory_loader(multipleye_root):
    # Read the same files as "uploads" (tagging source_file) and assert the recipe
    # reproduces the directory loader exactly — guards against drift.
    import glob

    def tag(paths):
        frames = []
        for p in paths:
            df = pd.read_csv(p)
            df["source_file"] = __import__("pathlib").Path(p).stem
            frames.append(df)
        return pd.concat(frames, ignore_index=True, sort=False)

    scan = tag(glob.glob(str(multipleye_root / "scanpaths" / "*" / "*_scanpath.csv")))
    aoi = tag(
        glob.glob(str(multipleye_root / "stimuli_*" / "aoi_stimuli_*" / "*_aoi.csv"))
    )
    wu, fu = datasets_module.load_multipleye_uploads(scan, aoi)
    wd, fd = datasets_module.load_multipleye(multipleye_root)
    assert sorted(wu["trial_id"].unique()) == sorted(wd["trial_id"].unique())
    assert sorted(fu["trial_id"].unique()) == sorted(fd["trial_id"].unique())
    assert set(wu["text_id"]) == set(wd["text_id"])
    assert round(float(wu["x"].sum()), 3) == round(float(wd["x"].sum()), 3)


def test_multipleye_uploads_prefers_scanpath_fixation_first_order():
    # Same trial, the fixation file uploaded BEFORE the scanpath file → scanpath
    # still wins (the dedup is order-independent).
    df = pd.concat(
        [
            _upload_frame(
                {
                    "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_fixation": [
                        {
                            "onset": 1000,
                            "duration": 200,
                            "location_x": 90,
                            "location_y": 65,
                            "page": "page_1",
                        }
                    ]
                }
            ),
            _upload_frame(
                {
                    "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath": [
                        _scan_row(1000, 200, 90, 65, "page_1", 0)
                    ]
                }
            ),
        ],
        ignore_index=True,
        sort=False,
    )
    _, fixations = datasets_module.multipleye_frames_from_uploads(df, None)
    assert len(fixations) == 1
    assert fixations["word_idx"].notna().all()  # the scanpath rows (with word idx)


def test_multipleye_uploads_pageless_file_does_not_crash():
    # A stray / question-AOI upload without a `page` column must contribute zero
    # boxes, not crash the wizard (regression for the KeyError('page') guard).
    scan = _upload_frame(
        {
            "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath": [
                _scan_row(1000, 200, 90, 65, "page_1", 0)
            ]
        }
    )
    good_aoi = _upload_frame(
        {"lit_demo_1_aoi": _aoi_pages(("page_1", 0, "AA", 80))}, columns=_AOI_COLS
    )
    pageless = pd.DataFrame(
        {
            "char_idx": [0],
            "char": ["x"],
            "top_left_x": [1],
            "top_left_y": [1],
            "width": [1],
            "height": [1],
            "word_idx": [0],
            "word": ["x"],
            "source_file": ["lit_demo_1_aoi_questions"],  # no `page` column
        }
    )
    aoi = pd.concat([good_aoi, pageless], ignore_index=True, sort=False)
    words, _ = datasets_module.load_multipleye_uploads(scan, aoi)
    assert (
        not words.empty
    )  # the real AOI still produced boxes; the page-less one didn't


def test_multipleye_uploads_pageless_fixation_skipped():
    bad = pd.DataFrame(
        {"onset": [1], "duration": [1], "location_x": [1.0], "location_y": [1.0]}
    )
    bad["source_file"] = (
        "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath"  # no `page` column
    )
    words, fixations = datasets_module.multipleye_frames_from_uploads(bad, None)
    assert words.empty and fixations.empty  # skipped, not a crash


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
# MultiplEYE side data: questions / reader metadata / reading measures / images
# ---------------------------------------------------------------------------


def test_multipleye_questions_from_frame():
    qs = pd.DataFrame(
        {
            "stimulus_name": ["Lit_Alchemist", "Lit_Alchemist"],
            "stimulus_id": [4, 4],
            "question_no": [2, 1],
            "condition_no": [1, 1],
            "question": ["Q2?", "Q1?"],
            "target": ["A2", "A1"],
            "distractor_a": ["d1", "d1"],
            "distractor_b": ["nan", "d2"],  # 'nan' must be dropped
            "condition_name": ["local", "local"],
        }
    )
    out = datasets_module._multipleye_questions_from_frame(qs)
    # Join key is stimulus_name + "_" + stimulus_id.
    assert set(out) == {"Lit_Alchemist_4"}
    items = json.loads(out["Lit_Alchemist_4"])
    assert [q["question_no"] for q in items] == [1, 2]  # sorted by (cond, q_no)
    assert items[0]["target"] == "A1"
    assert items[1]["distractors"] == ["d1"]  # 'nan' distractor filtered


def test_multipleye_participant_meta_int_join():
    fixations = pd.DataFrame(
        {
            "participant": ["001", "014"],  # zero-padded text
            "session": ["ET1", "ET2"],
            "x": [1.0, 2.0],
        }
    )
    meta = datasets_module._normalize_multipleye_participant_meta(
        pd.DataFrame(
            {
                "participant_id": [1, 14],  # integer
                "session": ["ET1", "ET2"],
                "age": [25, 30],
                "gender": ["F", "M"],
            }
        )
    )
    merged = datasets_module._merge_multipleye_participant_meta(fixations, meta)
    assert merged["pp_age"].tolist() == [25, 30]  # int "001" joined int 1
    assert merged["pp_gender"].tolist() == ["F", "M"]
    assert "participant_id" not in merged.columns  # the meta key isn't leaked


def test_multipleye_rm_map_no_rr_and_derived_flags():
    # RR (re-reading) must NOT be mapped to a regression flag; in/out flags are
    # derived from the counts.
    assert "RR" not in datasets_module.MULTIPLEYE_RM_MAP
    assert datasets_module.MULTIPLEYE_RM_MAP["FFD"] == "IA_FIRST_FIXATION_DURATION"
    assert datasets_module.MULTIPLEYE_RM_MAP["TFT"] == "IA_DWELL_TIME"
    # Every IA_* target is a recognized pre-aggregated source the app prefers.
    word_sources = {src for src, *_ in data_module.WORD_OPTIONAL_FIELDS}
    assert set(datasets_module.MULTIPLEYE_RM_MAP.values()) <= word_sources


def test_multipleye_words_per_reader_merges_rm_by_page_word():
    # word_idx restarts per page, so the RM merge key MUST include page.
    boxes = pd.DataFrame(
        {
            "stimulus": ["S"] * 3,
            "page": ["page_1", "page_1", "page_2"],
            "word_idx": [0, 1, 0],
            "left": [0, 10, 0],
        }
    )
    rm = pd.DataFrame(
        {
            "participant_id": ["r1"] * 3,
            "stimulus": ["S"] * 3,
            "page": ["page_1", "page_1", "page_2"],
            "word_idx": [0, 1, 0],
            "IA_FIRST_FIXATION_DURATION": [100, 110, 120],
        }
    )
    fixations = pd.DataFrame({"participant_id": ["r1"], "stimulus": ["S"]})
    words = datasets_module._multipleye_words_per_reader(boxes, rm, fixations)
    assert set(words["participant_id"]) == {"r1"}
    # page_2 word 0 gets its own measure (not page_1 word 0's).
    p2 = words[(words["page"] == "page_2") & (words["word_idx"] == 0)]
    assert p2["IA_FIRST_FIXATION_DURATION"].iloc[0] == 120


def test_multipleye_uploads_with_questions_and_participant_meta():
    scan = _upload_frame(
        {
            "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath": [
                _scan_row(1000, 200, 90, 65, "page_1", 0)
            ]
        }
    )
    questions = pd.DataFrame(
        {
            "stimulus_name": ["Lit_Demo"],
            "stimulus_id": [1],
            "question": ["Why?"],
            "target": ["Because"],
            "condition_name": ["local"],
            "question_no": [1],
            "condition_no": [1],
        }
    )
    meta = pd.DataFrame(
        {"participant_id": [1], "session": ["ET1"], "age": [22], "gender": ["F"]}
    )
    _, fixations = datasets_module.load_multipleye_uploads(
        scan, None, questions_df=questions, participant_meta_df=meta
    )
    assert (
        json.loads(fixations["comprehension_questions"].iloc[0])[0]["target"]
        == "Because"
    )
    assert fixations["pp_age"].iloc[0] == 22
    assert fixations["pp_gender"].iloc[0] == "F"


@pytest.mark.skipif(
    not _MULTIPLEYE_SAMPLE.is_dir(), reason="MultiplEYE sample not present"
)
def test_load_multipleye_real_sample_side_data():
    words, fixations = datasets_module.load_multipleye(
        _MULTIPLEYE_SAMPLE, stimuli=["Lit_Alchemist_4"]
    )
    # Per-reader words with pre-aggregated reading measures (IA_* → canonical).
    assert "participant_id" in words.columns
    assert words["first_fixation_ms"].notna().any()  # FFD → IA_FIRST_FIXATION_DURATION
    assert words["total_fixation_duration_ms"].notna().any()  # TFT → IA_DWELL_TIME
    # Reader metadata + comprehension + image path on the fixations.
    assert fixations["pp_age"].notna().any()
    questions = json.loads(fixations["comprehension_questions"].dropna().iloc[0])
    assert len(questions) >= 1 and questions[0]["question"]
    img = fixations["image_path"].dropna().iloc[0]
    assert __import__("os").path.exists(img)


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
