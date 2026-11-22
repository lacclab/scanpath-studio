"""The benchmark and change verifier run on the files and options named by a maintainer."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks import computation_benchmark as bench
from scripts import verify_change


def test_benchmark_reads_a_shared_cohort_in_each_files_format(tmp_path):
    words = tmp_path / "words.csv"
    words.write_text(
        "participant_id;trial_id;word_id;text;x;y;width;height\n"
        "word-only;1;1;A;1;2;3;4\n001;2;1;B;1;2;3;4\n002;3;1;C;1;2;3;4\n",
        encoding="utf-16",
    )
    fix = tmp_path / "fixations.txt"
    fix.write_text(
        "participant_id\ttrial_id\tx\ty\tduration_ms\n"
        "002\t3\t2\t4\t80\n001\t2\t3\t4\t90\nfix-only\t5\t4\t4\t100\n001\t2\t5\t4\t110\n"
    )
    w_col, f_col, selected = bench._cohort(words, fix, 1)
    assert selected == ["001"]
    w = bench.read_table(words, "words", w_col, selected)
    f = bench.read_table(fix, "fixations", f_col, selected)
    assert w["participant_id"].tolist() == ["001"]
    assert f["duration_ms"].tolist() == [90, 110]
    assert bench.read_table(words, "words", None, [])["text"].tolist() == [
        "A",
        "B",
        "C",
    ]


def test_post_stage_memory_distinguishes_released_and_retained_allocations(monkeypatch):
    memory = [100.0]
    monkeypatch.setattr(bench, "_rss_mib", lambda: memory[0])
    profiler = bench.Profiler()

    def transient():
        memory[0] += 32
        memory[0] -= 32

    def retained():
        memory[0] += 16

    profiler.run("transient", [], transient)
    profiler.run("retained", [], retained)
    assert [(m.rss_delta_mib, m.rss_after_mib) for m in profiler.measurements] == [
        (0, 100),
        (16, 116),
    ]


def test_verifier_keeps_an_earlier_render_when_this_command_only_lists(tmp_path):
    old = tmp_path / "cli.html"
    old.write_bytes(b"last good figure")
    _, ok, detail = verify_change._check_cli("--list-trials", tmp_path)
    assert not ok and "produced no figure" in detail
    assert old.read_bytes() == b"last good figure"


def test_verifier_rejects_an_unknown_link_option_without_booting_the_app(
    tmp_path, capsys
):
    with pytest.raises(SystemExit) as failure:
        verify_change.main(
            ["--query", "unknown_lab_option=blue", "--out-dir", str(tmp_path)]
        )
    assert failure.value.code == 2
    assert "unknown_lab_option" in capsys.readouterr().err


def test_paper_validation_uses_geometry_even_with_mapped_fixation_ids(
    monkeypatch, capsys
):
    from paper import paper_stats
    from scanpath_studio import api

    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")
    words, fix = api.load_sample_data(names="canonical")
    reader, trial = next(
        iter(api.list_trials(words, fix).itertuples(index=False, name=None))
    )
    words = words[(words["participant_id"] == reader) & (words["trial_id"] == trial)]
    fix = fix[(fix["participant_id"] == reader) & (fix["trial_id"] == trial)]
    reference = api.compute_word_metrics(words, fix)
    from scanpath_studio import data

    raw = data.read_table(Path(data.__file__).parent / "sample_data/ia.csv")
    raw = raw[(raw["participant_id"] == reader) & (raw["unique_trial_id"] == trial)]
    paper_stats.validate(words, fix.assign(word_id=0), reference, raw, "geometry")
    out = capsys.readouterr().out
    assert "n=0 words" not in out and "r=nan" not in out


def test_interaction_benchmark_distinguishes_real_data_work_and_reruns(tmp_path):
    import json
    import subprocess
    import sys

    target = tmp_path / "interactions.json"
    subprocess.run(
        [
            sys.executable,
            str(Path(bench.__file__).with_name("interaction_benchmark.py")),
            "--json",
            str(target),
        ],
        check=True,
        capture_output=True,
    )
    first, switch, color = json.loads(target.read_bytes())["interactions"]
    assert first["stages"]["read_demo"] > 0 and first["stages"]["normalize"] > 0
    assert first["reading"] != switch["reading"] == color["reading"]
    assert switch["color_by"] != color["color_by"]
    for interaction in (switch, color):
        assert (
            interaction["stages"]["read_demo"]
            == interaction["stages"]["normalize"]
            == 0
        )
        assert (
            interaction["stages"]["build_figure"] > 0
            and interaction["stages"]["select_trial_rows"] > 0
        )


def test_corpus_paper_uses_canonical_passage_ids_and_breaks_ties(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setenv("PAPER_FIGURES_DIR", str(tmp_path))
    from paper import paper_fig_corpus as paper

    # The ordinary reports have several equally large reader cohorts. A reader
    # supplies many word rows, and the loader has already composed the text ID.
    words = pd.DataFrame(
        {
            "text_id": ["2_0_1_Adv"] * 2 + ["1_0_1_Adv"] * 3,
            "participant_id": ["q", "r", "s", "t", "s"],
        }
    )
    assert paper._busiest_text(words) == ("1_0_1_Adv", 2)
    assert paper._busiest_text(words.iloc[::-1]) == ("1_0_1_Adv", 2)
