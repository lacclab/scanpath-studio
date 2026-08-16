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
    assert {"x", "y", "width", "height"} <= set(words.columns)
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


def test_a_harmonised_label_reaches_the_benchmark_loader_not_the_native_corpus(
    bundle, monkeypatch
):
    """I4: `compare_source` must dispatch on the entry, never on the label text.

    PoTeC ships both natively and harmonised, so the harmonised entry's label
    *contains* `_POTEC_LABEL_HINT` — a plain substring test that would send it
    to `datasets.load_potec`, i.e. to a different corpus in a different
    directory, with no error anywhere. Today the `benchmark_dataset` branch sits
    above the hints at all three sites; this pins the ordering, because the
    failure it prevents is silent (compare scanpath B would simply be someone
    else's data) and would leave the suite green.
    """
    from scanpath_studio import app, compare_source, datasets

    for module in (app, compare_source):
        monkeypatch.setattr(module, "EYEGENBENCH_DEFAULT_DIR", str(bundle))
    label = app.benchmark_corpus_label("PoTeC")

    root, kwargs = compare_source._public_location(label)
    assert kwargs == {"dataset": "PoTeC"}
    assert root == str(bundle), "resolved PoTeC's *native* directory, not the bundle"

    def _native_loader_must_not_run(*_args, **_kwargs):
        raise AssertionError("a harmonised label reached the native PoTeC loader")

    monkeypatch.setattr(datasets, "load_potec", _native_loader_must_not_run)
    monkeypatch.setattr(datasets, "load_multipleye", _native_loader_must_not_run)
    words, fixations = compare_source._load_public_frames.__wrapped__(
        label, root, tuple(sorted(kwargs.items()))
    )
    assert not words.empty and not fixations.empty

    monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
    names = [name for name, _ready, _why in compare_source.secondary_dataset_options()]
    assert label in names


def test_the_bootstrap_placeholder_is_never_offered_as_a_comparison_source(
    tmp_path, monkeypatch
):
    """The `setup_only` skip in `secondary_dataset_options`, actually pinned.

    N3: the version of this assertion that lived in the dispatch test above ran
    with a corpus discovered — and with one discovered the placeholder is not in
    the registry at all, so "it isn't in the options" held whether or not
    `setup_only` was honoured. The state that can fail is the *empty* bundle
    directory, which is the only state the placeholder exists in: it is a place
    to type a path, not a dataset, so compare mode must skip it rather than
    offer the user a source B that would load the demo.
    """
    from scanpath_studio import app, compare_source

    empty = tmp_path / "no-bundle-here"
    empty.mkdir()
    for module in (app, compare_source):
        monkeypatch.setattr(module, "EYEGENBENCH_DEFAULT_DIR", str(empty))
    monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
    app._cached_eyegenbench_datasets.clear()

    registry = app.public_dataset_registry()
    assert app.BENCHMARK_SETUP_CHOICE in registry, (
        "premise: with nothing discovered the placeholder IS in the registry, "
        "so the enumeration has something to skip"
    )
    names = [name for name, _ready, _why in compare_source.secondary_dataset_options()]
    assert app.BENCHMARK_SETUP_CHOICE not in names
    # The built-ins are still offered, so this isn't passing by enumerating
    # nothing at all.
    assert set(app.PUBLIC_DATASET_REGISTRY) <= set(names)


def test_the_two_potec_entries_get_distinguishable_unready_hints(bundle, monkeypatch):
    """M12: "Open PoTeC…" named an entry the user couldn't pick out of two."""
    from scanpath_studio import app, compare_source

    for module in (app, compare_source):
        monkeypatch.setattr(module, "EYEGENBENCH_DEFAULT_DIR", str(bundle))
    native = next(k for k in app.PUBLIC_DATASET_REGISTRY if "PoTeC" in k)
    harmonised = app.benchmark_corpus_label("PoTeC")
    assert compare_source._short_name(native) != compare_source._short_name(harmonised)


def test_a_nameless_manifest_row_before_a_valid_one_does_not_crash(bundle, monkeypatch):
    """I2: the crash M7 named is reachable from every surface, not just the app.

    A row with no `name` used to raise `KeyError` out of `_find_entry` — outside
    the `(FileNotFoundError, ValueError, OSError)` triple every caller guards
    with. The earlier fixture put the nameless row *alone* in the manifest,
    which is the one arrangement that cannot reach the raise: discovery filters
    it out and nothing then looks a name up. Ordered before a valid row, it took
    down the compare-B enumeration and the app with it.
    """
    from scanpath_studio import app, compare_source

    (bundle / "manifest.json").write_text(
        json.dumps(
            {"datasets": [{"language": "de"}, {"name": "PoTeC", "language": "de"}]}
        )
    )
    assert eyegenbench.entry_name({"language": "de"}) == ""
    # The name lookups every surface runs, with the malformed row in front.
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is True
    assert eyegenbench.eyegenbench_present(bundle) is True
    assert eyegenbench.eyegenbench_monitor(bundle, "PoTeC") is None

    for module in (app, compare_source):
        monkeypatch.setattr(module, "EYEGENBENCH_DEFAULT_DIR", str(bundle))
    monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
    app._cached_eyegenbench_datasets.clear()
    label = app.benchmark_corpus_label("PoTeC")
    # Discovery drops the unusable row and keeps the usable one…
    assert label in app.public_dataset_registry()
    # …and the compare-B enumeration, which probes *every* registry entry on
    # every rerun Compare is on, is where the escaping KeyError took the app
    # down.
    compare_source._public_ready_cached.clear()
    ready = {name: ok for name, ok, _why in compare_source.secondary_dataset_options()}
    assert ready[label] is True


def test_an_invented_default_screen_is_declined_by_both_surfaces(bundle, monkeypatch):
    """I3: one rule for "does this corpus document a screen?".

    `monitor_source: "default"` is the pipeline's generic 1920x1080 guess for a
    corpus that documents nothing. The app declines it (the canvas then falls
    back to data extents, which is honest); the CLI used to accept it, so the
    same corpus rendered at two different scales depending on the surface.
    """
    from scanpath_studio import app

    real = {"monitor": [1680, 1050], "monitor_source": "paper"}
    invented = {"monitor": [1920, 1080], "monitor_source": "default"}
    assert eyegenbench.declared_monitor(real) == (1680, 1050)
    assert eyegenbench.declared_monitor(invented) is None
    assert eyegenbench.declared_monitor({"monitor_source": "paper"}) is None

    # The CLI's canvas resolution and the picker entry read the same function.
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["datasets"][0].update(invented)
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    assert eyegenbench.eyegenbench_monitor(bundle, "PoTeC") is None
    monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(bundle))
    app._cached_eyegenbench_datasets.clear()
    entry = app.public_dataset_registry()[app.benchmark_corpus_label("PoTeC")]
    assert "monitor" not in entry


def test_the_description_qualifies_partial_geometry_like_the_badge_does():
    """M8/M11: the caption beside the badge must not re-make the claim R34 bans."""
    from scanpath_studio import app

    mixed = {
        "name": "Provo",
        "geometry_source": "real",
        "n_texts": 12,
        "paragraphs_without_real_boxes": 3,
    }
    description = app._benchmark_description(mixed, harmonised_overlap=False)
    assert "Screen geometry: real —" in description
    assert "measured word boxes for 9 of 12 texts" in description
    # Nothing is "above" anything in a searchable picker (M10).
    overlap = app._benchmark_description(mixed, harmonised_overlap=True)
    assert "entry above" not in overlap
    assert "this app's own Provo entry" in overlap
    # Full coverage keeps the short form on both surfaces.
    full = dict(mixed, paragraphs_without_real_boxes=0)
    assert "Screen geometry: real." in app._benchmark_description(
        full, harmonised_overlap=False
    )
    # M11: with `n_texts` absent, prefer the vaguer claim to the confident one.
    unknown_total = {"geometry_source": "real", "paragraphs_without_real_boxes": 3}
    assert "some but not all" in app.geometry_badge(unknown_total)


def test_the_cli_and_the_picker_resolve_the_same_screen(bundle, tmp_path, monkeypatch):
    """I3 where the two surfaces meet (N6).

    `declared_monitor` exists so one corpus cannot render at the manifest's
    invented 1920x1080 through `cli render --eyegenbench` while the app renders
    it at data extents. Only the app half was pinned, so a CLI regression — the
    shape this bug had for a whole task — would not have failed anything. This
    drives the real `render` command and compares the canvas it passes to the
    figure builder against the registry entry the picker builds from the same
    manifest row.
    """
    from scanpath_studio import api, app, cli

    manifest = json.loads((bundle / "manifest.json").read_text())
    row = manifest["datasets"][0]

    def _cli_canvas():
        seen = {}

        def _spy(*_args, **kwargs):
            import plotly.graph_objects as go

            seen["canvas"] = kwargs.get("canvas_size")
            return go.Figure()

        monkeypatch.setattr(api, "plot_scanpath", _spy)
        assert (
            cli.main(
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
                    str(tmp_path / f"{len(seen)}.html"),
                ]
            )
            is None
        )
        return seen["canvas"]

    def _picker_monitor():
        monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(bundle))
        app._cached_eyegenbench_datasets.clear()
        entry = app.public_dataset_registry()[app.benchmark_corpus_label("PoTeC")]
        return entry.get("monitor")

    # 1. A corpus that documents its screen: both surfaces snap to it.
    row["monitor_source"] = "paper"
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    assert _cli_canvas() == (1680, 1050)
    assert _picker_monitor() == (1680, 1050)

    # 2. A corpus that documents nothing: the manifest's 1920x1080 is the
    # pipeline's invented default, so neither surface may adopt it. `None`
    # canvas is the CLI's "no canvas given" path — the figure falls back to the
    # data's own extents, exactly as the app does with no `monitor` on the entry.
    row["monitor_source"] = "default"
    row["monitor"] = [1920, 1080]
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    assert _cli_canvas() is None
    assert _picker_monitor() is None


def test_a_malformed_count_does_not_take_the_picker_down(bundle, monkeypatch):
    """N1: the registry build reads manifest counts, so they must not raise.

    `_benchmark_description` runs for every discovered corpus while the picker
    builds its option list, and it reads `paragraphs_without_real_boxes` and
    `n_texts`. A bare `int()` on a hand-edited manifest (`"n_texts": "many"`)
    raised `ValueError` straight out of the enumeration — the same crash class
    as the nameless row, on the same path, reintroduced one level up.
    """
    from scanpath_studio import app

    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["datasets"][0].update(
        {
            "geometry_source": "real",
            "n_texts": "many",
            "n_readers": [1, 2],
            "paragraphs_without_real_boxes": 3,
        }
    )
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(bundle))
    app._cached_eyegenbench_datasets.clear()

    entry = app.public_dataset_registry()[app.benchmark_corpus_label("PoTeC")]
    # Unreadable counts drop out of the caption rather than crashing or
    # printing garbage…
    assert "many" not in entry["size"] and "text" not in entry["size"]
    # …and the geometry claim degrades to the vaguer honest wording, never to
    # the confident "measured word boxes." R34 forbids.
    assert "some but not all texts" in entry["description"]
    assert "some but not all texts" in app.geometry_badge(
        {
            "geometry_source": "real",
            "n_texts": "many",
            "paragraphs_without_real_boxes": 3,
        }
    )
    # An unreadable *missing* count is likewise unknown coverage, not full.
    assert "some but not all texts" in app.geometry_badge(
        {"geometry_source": "real", "n_texts": 12, "paragraphs_without_real_boxes": "?"}
    )
