import json
import shutil

import pandas as pd
import pytest

from scanpath_studio import data, eyegenbench


@pytest.fixture
def bundle(tmp_path):
    """A minimal two-word, two-fixation EyeGenBench bundle."""
    root = tmp_path / "EyeGenBench"
    ds = root / "PoTeC"
    ds.mkdir(parents=True)
    pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, 1],
            "ia_label": ["ab", "cd"],
            "line": [0, 0],
            "start_x": [10.0, 70.0],
            "end_x": [60.0, 120.0],
            "start_y": [20.0, 20.0],
            "end_y": [40.0, 40.0],
            "geometry_source": ["real", "real"],
        }
    ).to_parquet(ds / "words.parquet")
    pd.DataFrame(
        {
            # Not `unique_trial_id`: that literal name would override
            # EYEGENBENCH_FIX_SCHEMA's trial mapping inside
            # data.normalize_fixations (see eyegenbench.py's module
            # docstring). EyeGenBench's finer-grained per-reading id, if
            # carried at all, lives under this name instead.
            "eyegenbench_trial_id": ["t1", "t1"],
            "unique_participant_id": ["r1", "r1"],
            "unique_paragraph_id": ["p1", "p1"],
            "fix_index": [0, 1],
            "ia_index": [0, 1],
            "fix_duration": [200, 180],
            "x": [35.0, 95.0],
            "y": [30.0, 30.0],
            "geometry_source": ["real", "real"],
        }
    ).to_parquet(ds / "fixations.parquet")
    pd.DataFrame(
        {"unique_participant_id": ["r1"], "participant_language": ["de"]}
    ).to_parquet(ds / "participants.parquet")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "name": "PoTeC",
                        # The real manifest records an ISO code, not a name.
                        "language": "de",
                        "geometry_source": "real",
                        "monitor": [1680, 1050],
                        "n_readers": 1,
                        "n_texts": 1,
                        "n_fixations": 2,
                        "interpolated_fraction": 0.0,
                        "display_source": "pymovements:potec",
                    }
                ]
            }
        )
    )
    return root


def test_present_is_true_for_a_complete_bundle(bundle):
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is True


def test_present_is_false_when_a_parquet_is_missing(bundle):
    (bundle / "PoTeC" / "fixations.parquet").unlink()
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is False


def test_present_is_false_without_a_manifest(bundle):
    (bundle / "manifest.json").unlink()
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is False


def test_present_with_no_dataset_checks_the_whole_bundle(bundle):
    assert eyegenbench.eyegenbench_present(bundle) is True


def test_present_is_case_insensitive(bundle):
    assert eyegenbench.eyegenbench_present(bundle, "potec") is True
    assert eyegenbench.eyegenbench_present(bundle, "POTEC") is True


def test_present_is_false_for_a_directory_not_in_the_manifest(bundle):
    # A directory holding all three Parquet files under a name the manifest
    # doesn't list -- present() must not say True for a name load() would
    # reject.
    shutil.copytree(bundle / "PoTeC", bundle / "GhostCorpus")
    assert eyegenbench.eyegenbench_present(bundle, "GhostCorpus") is False


def test_datasets_lists_the_manifest_entries(bundle):
    names = [d["name"] for d in eyegenbench.eyegenbench_datasets(bundle)]
    assert names == ["PoTeC"]


def test_monitor_comes_from_the_manifest(bundle):
    assert eyegenbench.eyegenbench_monitor(bundle, "PoTeC") == (1680, 1050)


def test_raw_frames_returns_both_tables(bundle):
    words, fixations = eyegenbench.eyegenbench_raw_frames(bundle, dataset="PoTeC")
    assert list(words["ia_label"]) == ["ab", "cd"]
    assert len(fixations) == 2


def test_auto_detection_agrees_with_our_schemas(bundle):
    words, fixations = eyegenbench.eyegenbench_raw_frames(bundle, dataset="PoTeC")
    assert data.validate_word_schema(data.propose_word_schema(words)) == []
    assert data.validate_fix_schema(data.propose_fix_schema(fixations)) == []


def test_load_normalizes_and_broadcasts_to_the_reader(bundle):
    words, fixations = eyegenbench.load_eyegenbench(bundle, dataset="PoTeC")
    assert set(words["participant_id"]) == {"r1"}
    assert set(["x", "y", "width", "height"]) <= set(words.columns)
    assert fixations.loc[0, "duration_ms"] == 200


def test_geometry_source_survives_normalization(bundle):
    words, fixations = eyegenbench.load_eyegenbench(bundle, dataset="PoTeC")
    assert set(words["geometry_source"]) == {"real"}
    assert set(fixations["geometry_source"]) == {"real"}


def test_unknown_dataset_raises_value_error(bundle):
    with pytest.raises(ValueError, match="not in the bundle"):
        eyegenbench.eyegenbench_raw_frames(bundle, dataset="NoSuchCorpus")


def test_missing_bundle_says_what_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="prepare_eyegenbench.py"):
        eyegenbench.eyegenbench_raw_frames(tmp_path, dataset="PoTeC")


def test_load_eyegenbench_is_exported_from_the_package_root():
    import scanpath_studio

    assert "load_eyegenbench" in scanpath_studio.__all__
    assert callable(scanpath_studio.load_eyegenbench)


def test_load_eyegenbench_is_listed_in_dir():
    import scanpath_studio

    assert "load_eyegenbench" in dir(scanpath_studio)


def test_cli_accepts_the_eyegenbench_input(bundle, tmp_path):
    from scanpath_studio import cli

    out = tmp_path / "fig.png"
    # The bundle's trial identity is `unique_paragraph_id` ("p1") -- see
    # eyegenbench.EYEGENBENCH_FIX_SCHEMA's module docstring for why the
    # finer-grained `eyegenbench_trial_id` passthrough column ("t1") is not
    # what defines trial_id after normalization.
    code = cli.main(
        [
            "render",
            "--eyegenbench",
            str(bundle),
            "--eyegenbench-dataset",
            "PoTeC",
            "--participant",
            "r1",
            "--trial",
            "p1",
            "--out",
            str(out),
        ]
    )
    assert code is None
    assert out.is_file()


def test_cli_rejects_eyegenbench_combined_with_sample(bundle):
    from scanpath_studio import cli

    # `render`'s "exactly one input" guard is a plain `raise SystemExit(msg)`
    # (not routed through argparse's `parser.error`), so -- like the sibling
    # check at tests/test_cli.py:564 -- the message lives on the exception,
    # not on stderr.
    with pytest.raises(SystemExit, match="exactly one input"):
        cli.main(["render", "--sample", "--eyegenbench", str(bundle)])


def test_cli_requires_a_dataset_name_with_eyegenbench(bundle, capsys):
    from scanpath_studio import cli

    with pytest.raises(SystemExit):
        cli.main(["render", "--eyegenbench", str(bundle), "--out", "x.png"])
    assert "--eyegenbench-dataset" in capsys.readouterr().err


def test_registry_lists_each_prepared_corpus_as_its_own_entry(bundle, monkeypatch):
    """Task 11R: a prepared corpus is a top-level entry, not a nested choice."""
    from scanpath_studio import app

    monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(bundle))
    registry = app.public_dataset_registry()
    label = app.benchmark_corpus_label("PoTeC")
    assert label in registry
    # "EyeGenBench" is provenance — the pipeline that harmonises these corpora,
    # and one being extracted into its own repository. It belongs in the
    # description, never in an entry label.
    assert "EyeGenBench" not in label
    entry = registry[label]
    # PoTeC ships natively here too, so this copy says which one it is — by the
    # property that differs, not by the vendor's name.
    assert entry["short"] == "PoTeC (harmonised benchmark)"
    assert entry["language"] == "German"  # 'de' → a display name (R35)
    assert entry["monitor"] == (1680, 1050)
    assert entry["benchmark_dataset"] == "PoTeC"
    assert callable(entry["loader"])
    assert "EyeGenBench" in entry["description"]
    # The static built-ins stay exactly as they are; the function composes.
    assert set(app.PUBLIC_DATASET_REGISTRY) <= set(registry)
    # The bootstrap entry is only for when nothing is discovered.
    assert app.BENCHMARK_SETUP_CHOICE not in registry


def test_registry_offers_one_setup_entry_when_nothing_is_discovered(
    tmp_path, monkeypatch
):
    """R39: with no corpora there is nowhere to type the bundle path, so exactly
    one placeholder entry carries the directory input."""
    from scanpath_studio import app

    monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(tmp_path / "absent"))
    registry = app.public_dataset_registry()
    assert app.BENCHMARK_SETUP_CHOICE in registry
    assert not any(spec.get("benchmark_dataset") for spec in registry.values())


def test_a_manifest_entry_with_no_name_does_not_crash_discovery(bundle, monkeypatch):
    """M7: reading a nameless entry raises `KeyError`, which escapes the
    (FileNotFoundError, ValueError, OSError) catch and took the app down."""
    from scanpath_studio import app

    (bundle / "manifest.json").write_text(
        json.dumps({"datasets": [{"language": "de"}]})
    )
    monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(bundle))
    assert app.discovered_benchmark_datasets() == ()
    assert app.BENCHMARK_SETUP_CHOICE in app.public_dataset_registry()


def test_geometry_badge_never_claims_uniformly_real_geometry():
    """R34: `geometry_source` is the best tier *any* paragraph reached, so a
    corpus with one measured text in a thousand is scalar-"real". The scalar
    keeps that meaning (the per-word column refines it, and changing it would
    ripple into the manifest contract, the CLI and the API) — the *rendering* is
    what must not imply uniformity."""
    from scanpath_studio import app

    mixed = {
        "geometry_source": "real",
        "n_texts": 55,
        "paragraphs_without_real_boxes": 5,
    }
    assert "measured word boxes for 50 of 55 texts" in app.geometry_badge(mixed)
    full = {
        "geometry_source": "real",
        "n_texts": 55,
        "paragraphs_without_real_boxes": 0,
    }
    assert app.geometry_badge(full).endswith("measured word boxes.")
    assert "of 55" not in app.geometry_badge(full)
    # A reconstructed corpus already says it has no measured boxes at all —
    # which is exactly what its (always non-zero) count means.
    reconstructed = {
        "geometry_source": "reconstructed",
        "n_texts": 452,
        "paragraphs_without_real_boxes": 452,
    }
    assert "Reconstructed" in app.geometry_badge(reconstructed)
    assert app.geometry_badge({}) == ""


def test_language_codes_render_as_display_names():
    """R35: the manifest's `language` is an ISO code, and the picker shows it."""
    from scanpath_studio.constants import language_display

    # Verified against the real prepared bundle's manifest.
    assert language_display("zh") == "Chinese"  # BSC
    assert language_display("da") == "Danish"  # CopCo
    assert language_display("en") == "English"  # Provo, ZuCo1
    # A multilingual corpus records several codes in one field (MECO, celer).
    assert language_display("en,de,ru") == "English, German, Russian"
    # An unknown code renders as itself — never "Unknown", which would throw
    # away the one piece of real information there is.
    assert language_display("xx") == "xx"
    assert language_display("") == ""
