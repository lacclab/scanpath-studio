"""Tests for the bulk-export module."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest

from scanpath_studio.export import ExportOptions, bulk_export


@pytest.fixture
def minimal_combos():
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t2"],
            "text_id": ["para1", "para2"],
        }
    )


@pytest.fixture
def minimal_words():
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 4,
            "trial_id": ["t1", "t1", "t2", "t2"],
            "text_id": ["para1", "para1", "para2", "para2"],
            "word_id": [1, 2, 1, 2],
            "text": ["the", "cat", "the", "dog"],
            "line_idx": [1, 1, 1, 1],
            "x": [100, 200, 100, 200],
            "y": [50, 50, 50, 50],
            "width": [80, 80, 80, 80],
            "height": [40, 40, 40, 40],
        }
    )


@pytest.fixture
def minimal_fixations():
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 4,
            "trial_id": ["t1", "t1", "t2", "t2"],
            "text_id": ["para1", "para1", "para2", "para2"],
            "x": [140, 240, 140, 240],
            "y": [70, 70, 70, 70],
            "duration_ms": [200, 250, 220, 230],
            "timestamp_ms": [0, 200, 0, 220],
            "order_in_trial": [1, 2, 1, 2],
        }
    )


@pytest.fixture
def base_settings():
    return dict(
        show_words=True,
        show_word_labels=False,
        show_fixations=True,
        show_order=False,
        show_saccades=True,
        show_heatmap=False,
        color_by="duration_ms",
        heatmap_metric=None,
        marker_size_range=(8, 24),
        order_font_size=10,
        order_font_color="#111111",
        show_fixation_colorbar=False,
        show_heatmap_colorbar=False,
        fixation_color_range=None,
        heatmap_range=None,
        fixation_colorscale="Blues",
        heatmap_colorscale="Oranges",
    )


class TestBulkExport:
    def test_tabular_only_export(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=True,
            include_fixations=True,
            include_measures=True,
            table_format="csv",
        )
        zip_bytes, progress = bulk_export(
            minimal_combos,
            minimal_words.assign(total_fixation_duration_ms=[200, 250, 220, 230]),
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        assert progress.finished_trials == 2
        assert progress.errors == []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            assert "README.md" in names
            assert not any(n.startswith("aggregate/") for n in names)
            assert "per_trial/p1__t1/fixations.csv" in names
            assert "per_trial/p1__t1/measures.csv" in names
            assert "per_trial/p1__t1/plot_config.json" in names
            # No figures
            assert not any(n.endswith(".png") for n in names)
            assert not any(n.endswith(".svg") for n in names)
            cfg = json.loads(zf.read("per_trial/p1__t1/plot_config.json"))
            assert cfg["selection"]["participant_id"] == "p1"
            assert cfg["selection"]["trial_id"] == "t1"

    @pytest.mark.parametrize(
        "pattern",
        [
            "",
            "/abs/{artifact}.{ext}",
            "../{artifact}.{ext}",
            "a/../../{artifact}",
            "...",
            "..\\{artifact}.{ext}",
            "C:{artifact}",
            "a//{artifact}",
            "{artifact}/",
        ],
    )
    def test_a_path_pattern_that_leaves_the_zip_is_refused_up_front(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings, pattern
    ):
        """`../{artifact}.{ext}` would write `../plot_config.json`, and an empty
        pattern a member with no name."""
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=True,
            table_format="csv",
            path_pattern=pattern,
        )
        progress = []
        with pytest.raises(ValueError):
            bulk_export(
                minimal_combos,
                minimal_words,
                minimal_fixations,
                canvas_width=800,
                canvas_height=400,
                base_font_size=14,
                font_family="monospace",
                x_field="x",
                y_field="y",
                settings=base_settings,
                options=opts,
                progress_callback=progress.append,
            )
        assert progress == []  # nothing was rendered first

    def test_full_analysis_family_export(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_analysis_family=True,
            table_format="csv",
        )
        zip_bytes, progress = bulk_export(
            minimal_combos,
            minimal_words.assign(total_fixation_duration_ms=[200, 250, 220, 230]),
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        assert progress.errors == []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            assert "run_config.json" in names
            assert "per_trial/p1__t1/saccades.csv" in names
            assert "per_trial/p1__t1/word_measures.csv" in names
            assert "per_trial/p1__t1/trial_summary.csv" in names
            # Stacked copies only when the tables are combined — the
            # reader summary, which has no per-trial form, is always there.
            assert "aggregate/all_saccades.csv" not in names
            assert "aggregate/all_reader_summary.csv" in names

    @pytest.mark.parametrize("table_format", ["csv", "both"])
    def test_every_zip_member_name_is_unique(
        self,
        minimal_combos,
        minimal_words,
        minimal_fixations,
        base_settings,
        table_format,
    ):
        """With the combined tables *and* the full family ticked,
        `aggregate/all_fixations.*` must be written once — a zip keeps both
        entries of a duplicate name, and a reader silently sees only one."""
        import collections

        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_fixations=True,
            include_measures=True,
            include_analysis_family=True,
            combine_trials=True,
            table_format=table_format,
        )
        zip_bytes, progress = bulk_export(
            minimal_combos,
            minimal_words.assign(total_fixation_duration_ms=[200, 250, 220, 230]),
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        assert progress.errors == []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            duplicates = [n for n, c in collections.Counter(names).items() if c > 1]
            assert duplicates == []
            # The one that survives is the family's word-enriched table.
            fixations = pd.read_csv(zf.open("aggregate/all_fixations.csv"))
            assert "word_id" in fixations.columns
            # …and the family's word_measures stands in for `measures`.
            assert "aggregate/all_word_measures.csv" in names
            assert "aggregate/all_measures.csv" not in names

    def test_html_figures_need_no_kaleido(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        # HTML figures go through fig.to_html (no Kaleido/Chrome), so they export
        # cleanly even where the raster backend is unavailable.
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_pdf=False,
            include_html=True,
            include_plot_config=False,
        )
        assert opts.figure_formats() == ["html"]
        assert opts.raster_formats() == []
        zip_bytes, progress = bulk_export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        assert progress.finished_trials == 2
        assert progress.errors == []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            assert "per_trial/p1__t1/figure.html" in names
            assert "per_trial/p1__t2/figure.html" in names
            html = zf.read("per_trial/p1__t1/figure.html").decode("utf-8")
            assert "plotly" in html.lower()

    def test_parquet_format(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=False,
            include_fixations=True,
            include_measures=False,
            table_format="parquet",
        )
        zip_bytes, _ = bulk_export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert "per_trial/p1__t1/fixations.parquet" in zf.namelist()
            assert "per_trial/p1__t1/fixations.csv" not in zf.namelist()

    def test_skips_empty_trial(self, minimal_words, minimal_fixations, base_settings):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p999"],
                "trial_id": ["t1", "tNONE"],
                "text_id": ["para1", "paraX"],
            }
        )
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=True,
            include_fixations=False,
            include_measures=False,
            table_format="csv",
        )
        _, progress = bulk_export(
            combos,
            minimal_words,
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        assert progress.finished_trials == 2
        # The unknown participant trial should be reported as an error
        assert any("p999__tNONE" in e for e in progress.errors)

    def test_progress_callback_invoked(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        seen = []

        def cb(p):
            seen.append(p.finished_trials)

        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=False,
            include_fixations=False,
            include_measures=False,
            table_format="csv",
        )
        bulk_export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
            progress_callback=cb,
        )
        assert seen == [1, 2]


def _bulk(combos, words, fixations, settings, **options):
    zip_bytes, progress = bulk_export(
        combos,
        words,
        fixations,
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings=settings,
        options=ExportOptions(
            include_png=False, include_svg=False, include_plot_config=False, **options
        ),
    )
    assert progress.errors == []
    return zipfile.ZipFile(io.BytesIO(zip_bytes))


@pytest.mark.parametrize(
    ("dataset", "corpus"), [("Bundled demo", "onestop"), ("Upload tables", None)]
)
def test_the_bundle_cites_the_software_and_its_corpus(
    minimal_combos, minimal_words, minimal_fixations, base_settings, dataset, corpus
):
    from scanpath_studio.citation import CORPORA, cite, software_apa

    zf = _bulk(
        minimal_combos,
        minimal_words,
        minimal_fixations,
        base_settings,
        include_fixations=True,
        dataset_name=dataset,
    )
    readme = zf.read("README.md").decode()
    cited = readme.split("## Cite\n", 1)[1].split("\n## ", 1)[0]
    assert software_apa() in cited
    assert ("OneStop" in cited) == (corpus == "onestop")
    if corpus:
        assert CORPORA[corpus].apa() in cited
    assert zf.read("CITATION.bib").decode() == cite("bibtex", corpus) + "\n"
    assert "CITATION.bib,citation" in zf.read("index.csv").decode()


class TestExportComputesNoMeasures:
    """The word tables carry the reading measures the dataset brought, and
    nothing is computed."""

    def test_no_brought_measures_means_no_word_table_and_a_note(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        archive = _bulk(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include_measures=True,
            include_analysis_family=True,
        )
        names = archive.namelist()
        assert not any(
            n.endswith(("/measures.csv", "/word_measures.csv")) for n in names
        )
        # The rest of the family still comes out.
        assert "per_trial/p1__t1/saccades.csv" in names
        readme = archive.read("README.md").decode()
        assert "This dataset has none" in readme

    def test_brought_measures_are_written_as_they_came(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        words = minimal_words.assign(total_fixation_duration_ms=[1.0, 2.0, 3.0, 4.0])
        archive = _bulk(
            minimal_combos,
            words,
            minimal_fixations,
            base_settings,
            include_measures=True,
        )
        measures = pd.read_csv(archive.open("per_trial/p1__t1/measures.csv"))
        # The imported values, not the fixations' 200 / 250 ms…
        assert measures["total_fixation_duration_ms"].tolist() == [1.0, 2.0]
        # …and no measure the dataset did not bring.
        assert "first_fixation_ms" not in measures.columns
        assert "skip_flag" not in measures.columns
        assert "- total_fixation_duration_ms" in archive.read("README.md").decode()


class TestCombineTrials:
    """*Combine all trials into one file* writes each table once,
    every trial stacked, in place of the per-trial copies."""

    def test_tables_are_stacked_instead_of_per_trial(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        words = minimal_words.assign(total_fixation_duration_ms=[1.0, 2.0, 3.0, 4.0])
        archive = _bulk(
            minimal_combos,
            words,
            minimal_fixations,
            base_settings,
            include_fixations=True,
            include_measures=True,
            combine_trials=True,
        )
        names = archive.namelist()
        assert not any(n.endswith(".csv") and n.startswith("per_trial/") for n in names)
        fixations = pd.read_csv(archive.open("aggregate/all_fixations.csv"))
        assert sorted(fixations["trial_id"].unique()) == ["t1", "t2"]
        assert len(fixations) == len(minimal_fixations)
        measures = pd.read_csv(archive.open("aggregate/all_measures.csv"))
        assert measures["total_fixation_duration_ms"].tolist() == [1.0, 2.0, 3.0, 4.0]

    def test_family_tables_combine_too(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        archive = _bulk(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include_analysis_family=True,
            combine_trials=True,
        )
        names = set(archive.namelist())
        assert {
            "aggregate/all_fixations.csv",
            "aggregate/all_saccades.csv",
            "aggregate/all_trial_summary.csv",
            "aggregate/all_reader_summary.csv",
        } <= names
        assert "per_trial/p1__t1/saccades.csv" not in names


class TestBulkDriftCorrection:
    """Bulk-exported figures honour the drift correction; the exported tables
    deliberately stay uncorrected."""

    @pytest.fixture
    def two_line_words(self):
        # Two text lines (centers y=70 and y=170) so the correction has
        # somewhere to snap to — a single-line trial is a no-op by design.
        return pd.DataFrame(
            {
                "participant_id": ["p1"] * 4,
                "trial_id": ["t1"] * 4,
                "text_id": ["para1"] * 4,
                "word_id": [1, 2, 3, 4],
                "text": ["the", "cat", "sat", "down"],
                "line_idx": [1, 1, 2, 2],
                "x": [100, 200, 100, 200],
                "y": [50, 50, 150, 150],
                "width": [80, 80, 80, 80],
                "height": [40, 40, 40, 40],
            }
        )

    @pytest.fixture
    def drifted_fixations(self):
        # y values sit off the line centers (70 / 170), so a successful
        # correction must change them.
        return pd.DataFrame(
            {
                "participant_id": ["p1"] * 4,
                "trial_id": ["t1"] * 4,
                "text_id": ["para1"] * 4,
                "x": [140, 240, 140, 240],
                "y": [78.0, 85.0, 158.0, 179.0],
                "duration_ms": [200, 250, 220, 230],
                "timestamp_ms": [0, 200, 450, 700],
                "order_in_trial": [1, 2, 3, 4],
            }
        )

    def test_off_is_identity(self, two_line_words, drifted_fixations):
        from scanpath_studio.export import _drift_corrected_for_figure

        for settings in ({}, {"align_algorithm": "Off"}, {"align_algorithm": None}):
            fix, connector_y = _drift_corrected_for_figure(
                drifted_fixations, two_line_words, settings
            )
            assert fix is drifted_fixations  # same object — a true no-op
            assert connector_y is None

    def test_correction_snaps_y_and_reports_connectors(
        self, two_line_words, drifted_fixations
    ):
        from scanpath_studio.export import _drift_corrected_for_figure

        fix, connector_y = _drift_corrected_for_figure(
            drifted_fixations,
            two_line_words,
            {"align_algorithm": "Chain", "align_connectors": True},
        )
        assert fix is not drifted_fixations
        # Every corrected y sits on a line center; the originals did not.
        assert set(fix["y"]) <= {70.0, 170.0}
        assert list(drifted_fixations["y"]) == [78.0, 85.0, 158.0, 179.0]
        # Connectors carry the ORIGINAL y per fixation.
        assert connector_y == tuple(drifted_fixations["y"])

    def test_bulk_export_corrects_figure_but_not_tables(
        self,
        minimal_combos,
        two_line_words,
        drifted_fixations,
        base_settings,
        monkeypatch,
    ):
        import scanpath_studio.export as export_mod

        # Spy on the figure builder to see exactly what fixations it is handed.
        captured: dict = {}
        real_builder = export_mod.make_scanpath_figure

        def spy(words, fix, **kwargs):
            captured["y"] = list(fix["y"])
            captured["color_by_line"] = kwargs["settings"].color_by_line
            return real_builder(words, fix, **kwargs)

        monkeypatch.setattr(export_mod, "make_scanpath_figure", spy)

        combos = minimal_combos[minimal_combos["trial_id"] == "t1"]
        settings = dict(base_settings, align_algorithm="Chain", align_connectors=False)
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_html=True,
            include_plot_config=True,
            include_fixations=True,
            table_format="csv",
        )
        zip_bytes, progress = bulk_export(
            combos,
            two_line_words,
            drifted_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=settings,
            options=opts,
        )
        assert progress.errors == []
        # The figure was built from snapped fixations, coloured by line — the
        # same override the on-screen static path forces when correcting…
        assert set(captured["y"]) <= {70.0, 170.0}
        assert captured["color_by_line"] is True
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # The manifest records which correction produced the batch, and the
            # effective (forced) line colouring.
            cfg = json.loads(zf.read("per_trial/p1__t1/plot_config.json"))
            assert cfg["coloring"]["drift_correction"] == "Chain"
            assert cfg["coloring"]["drift_connectors"] is False
            assert cfg["coloring"]["color_by_line"] is True
            # …while the exported fixations table keeps the recorded y values.
            table = pd.read_csv(io.BytesIO(zf.read("per_trial/p1__t1/fixations.csv")))
            assert list(table["y"]) == [78.0, 85.0, 158.0, 179.0]


class TestSeparableLayers:
    """The per-layer figure breakdown dropped under `layers/`."""

    def test_layer_formats_defaults_to_svg(self):
        # Separable layers with no vector/raster figure format picked → SVG (the
        # publication default); off → no layer formats.
        no_fmts = dict(include_png=False, include_svg=False, include_pdf=False)
        assert ExportOptions(separable_layers=True, **no_fmts).layer_formats() == [
            "svg"
        ]
        assert ExportOptions(separable_layers=False, **no_fmts).layer_formats() == []
        # When a raster/vector figure format IS picked, layers follow it.
        opts = ExportOptions(
            separable_layers=True,
            include_png=True,
            include_svg=False,
            include_pdf=False,
        )
        assert opts.layer_formats() == ["png"]
        assert opts.needs_kaleido() is True

    def _fake_renderer(self):
        from contextlib import contextmanager

        @contextmanager
        def fake(enabled):  # avoids Kaleido/Chrome in tests
            def render(fig, fmt, width, height, scale):
                return f"{fmt}:{len(fig.data)}".encode()

            yield render

        return fake

    def test_writes_one_file_per_layer(
        self,
        monkeypatch,
        minimal_combos,
        minimal_words,
        minimal_fixations,
        base_settings,
    ):
        import scanpath_studio.export as export_mod

        monkeypatch.setattr(export_mod, "_figure_renderer", self._fake_renderer())
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_pdf=False,
            include_html=False,
            include_plot_config=False,
            separable_layers=True,
        )
        zip_bytes, progress = bulk_export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        assert progress.errors == []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
        # base_settings draws boxes + saccades + fixations (labels off, heatmap
        # off), so those layers + the frame land under layers/ for each trial.
        for layer in ("word_boxes", "saccades", "fixations", "frame"):
            assert f"per_trial/p1__t1/layers/{layer}.svg" in names
        # No combined figure was requested, so only the layer files are figures.
        assert not any(n.endswith("figure.svg") for n in names)
        # Labels/heatmap layers are absent (those layers weren't drawn).
        assert not any(n.endswith("layers/labels.svg") for n in names)
        assert not any(n.endswith("layers/heatmap.svg") for n in names)

    def test_layers_alongside_combined_figure(
        self,
        monkeypatch,
        minimal_combos,
        minimal_words,
        minimal_fixations,
        base_settings,
    ):
        import scanpath_studio.export as export_mod

        monkeypatch.setattr(export_mod, "_figure_renderer", self._fake_renderer())
        opts = ExportOptions(
            include_png=False,
            include_svg=True,  # combined SVG + per-layer SVGs
            include_pdf=False,
            include_html=False,
            include_plot_config=False,
            separable_layers=True,
        )
        zip_bytes, _ = bulk_export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
        assert "per_trial/p1__t1/figure.svg" in names  # the combined figure
        assert "per_trial/p1__t1/layers/word_boxes.svg" in names  # + its layers

    def test_layer_failure_reported_distinctly(
        self,
        monkeypatch,
        minimal_combos,
        minimal_words,
        minimal_fixations,
        base_settings,
    ):
        # A layer-split failure must be reported as a *layer* error and must NOT
        # drop the combined figure (they're in separate try blocks).
        import scanpath_studio.export as export_mod

        monkeypatch.setattr(export_mod, "_figure_renderer", self._fake_renderer())

        def boom(fig):
            raise RuntimeError("split kaboom")

        monkeypatch.setattr(export_mod, "split_scanpath_layers", boom)
        opts = ExportOptions(
            include_png=False,
            include_svg=True,  # combined SVG succeeds…
            include_pdf=False,
            include_html=False,
            include_plot_config=False,
            separable_layers=True,  # …but the layer split blows up
        )
        zip_bytes, progress = bulk_export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=opts,
        )
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
        # Combined figures survived; errors name the LAYER step, not "figure".
        assert "per_trial/p1__t1/figure.svg" in names
        assert not any("/layers/" in n for n in names)
        assert any("layer export failed" in e for e in progress.errors)
        assert not any("figure export failed" in e for e in progress.errors)


class TestLocalPathsAreNotExported:
    """Local paths never reach an exported file.

    `image_path` is a passthrough meta field on both schemas, so it survives
    normalization and rides into the exported fixation tables — and a fixations
    CSV is exactly the file that gets attached to a paper, posted to OSF, or
    mailed to a collaborator. `/Users/<name>/` discloses the OS account name and
    the rest discloses the directory layout, including where a corpus lives on
    the machine.
    """

    LEAKY = "/Users/someone/Projects/corpora/images/2_1_1_Ele__paragraph.png"

    def _export(self, combos, words, fixations, settings, fmt="csv"):
        # A brought measure, so the words table is written too.
        words = words.assign(total_fixation_duration_ms=200.0)
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=False,
            include_fixations=True,
            include_measures=True,
            table_format=fmt,
        )
        zip_bytes, _ = bulk_export(
            combos,
            words,
            fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=12,
            font_family="sans-serif",
            x_field="x",
            y_field="y",
            settings=settings,
            options=opts,
        )
        return zipfile.ZipFile(io.BytesIO(zip_bytes))

    def test_no_exported_table_carries_the_directory(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        """Grep every zip member for the directory."""
        fixations = minimal_fixations.assign(image_path=self.LEAKY)
        words = minimal_words.assign(image_path=self.LEAKY)
        archive = self._export(minimal_combos, words, fixations, base_settings)
        leaked = [
            name
            for name in archive.namelist()
            if b"/Users/someone" in archive.read(name)
        ]
        assert leaked == [], leaked

    def test_the_basename_is_kept_so_the_column_stays_useful(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        """Stripping the column entirely would break matching a row to its
        stimulus; the filename is what that matching uses."""
        fixations = minimal_fixations.assign(image_path=self.LEAKY)
        archive = self._export(minimal_combos, minimal_words, fixations, base_settings)
        name = next(n for n in archive.namelist() if n.endswith("fixations.csv"))
        body = archive.read(name).decode()
        assert "2_1_1_Ele__paragraph.png" in body

    def test_parquet_is_sanitized_too(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        """The fix belongs at the single write chokepoint, not per format."""
        fixations = minimal_fixations.assign(image_path=self.LEAKY)
        archive = self._export(
            minimal_combos, minimal_words, fixations, base_settings, fmt="parquet"
        )
        for name in archive.namelist():
            assert b"/Users/someone" not in archive.read(name), name


class TestStripLocalPaths:
    def test_a_frame_without_the_column_is_returned_unchanged(self):
        from scanpath_studio.export import strip_local_paths

        df = pd.DataFrame({"x": [1, 2]})
        assert strip_local_paths(df) is df

    def test_the_callers_frame_is_not_mutated(self):
        from scanpath_studio.export import strip_local_paths

        df = pd.DataFrame({"image_path": ["/a/b/c.png"]})
        out = strip_local_paths(df)
        assert out["image_path"].iloc[0] == "c.png"
        assert df["image_path"].iloc[0] == "/a/b/c.png"

    def test_missing_values_stay_missing(self):
        from scanpath_studio.export import strip_local_paths

        df = pd.DataFrame({"image_path": ["/a/b/c.png", None]})
        out = strip_local_paths(df)
        assert out["image_path"].iloc[0] == "c.png"
        assert pd.isna(out["image_path"].iloc[1])

    def test_a_windows_path_is_reduced_too(self):
        """An export produced on Windows leaks `C:\\Users\\<name>\\…` the same way."""
        from scanpath_studio.export import strip_local_paths

        df = pd.DataFrame({"image_path": [r"C:\Users\someone\corpora\stim.png"]})
        assert strip_local_paths(df)["image_path"].iloc[0] == "stim.png"

    def test_a_bare_filename_survives(self):
        from scanpath_studio.export import strip_local_paths

        df = pd.DataFrame({"image_path": ["stim.png"]})
        assert strip_local_paths(df)["image_path"].iloc[0] == "stim.png"


class TestAnnotationsInTheBundle:
    """The Export bundle can carry the exported trials' annotations."""

    RECORDS = [
        {
            "participant_id": "p1",
            "trial_id": "t1",
            "star": True,
            "tags": [],
            "note": "",
        },
        {
            "participant_id": "zz",
            "trial_id": "t9",
            "star": True,
            "tags": [],
            "note": "",
        },
    ]

    def _export(self, combos, words, fixations, settings, *, include: bool):
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=True,
            include_annotations=include,
        )
        zip_bytes, _ = bulk_export(
            combos,
            words,
            fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=settings,
            options=opts,
            annotation_records=self.RECORDS,
            annotation_dataset="Pilot",
        )
        return zipfile.ZipFile(io.BytesIO(zip_bytes))

    def test_only_the_exported_trials_annotations_go_in(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        from scanpath_studio.annotations import deserialize, file_dataset

        with self._export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include=True,
        ) as zf:
            assert "annotations.json" in zf.namelist()
            text = zf.read("annotations.json").decode("utf-8")
            store = deserialize(text)
            assert list(store) == [("p1", "t1")]
            # Schema 3 names the dataset the annotations were made on.
            assert file_dataset(text) == "Pilot"
            assert "annotations.json" in zf.read("README.md").decode("utf-8")

    def test_no_annotation_in_scope_means_no_file_and_no_readme_line(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        """The README never promises a file the scope left out."""
        others = minimal_combos[minimal_combos["trial_id"] != "t1"]
        with self._export(
            others, minimal_words, minimal_fixations, base_settings, include=True
        ) as zf:
            assert "annotations.json" not in zf.namelist()
            assert "annotations.json" not in zf.read("README.md").decode("utf-8")
            index = zf.read("index.csv").decode("utf-8")
            assert "annotations" not in index

    def test_off_by_default_and_when_off(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        assert ExportOptions().include_annotations is False
        with self._export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include=False,
        ) as zf:
            assert "annotations.json" not in zf.namelist()

    def test_the_figure_title_is_not_called_annotations(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        """`annotations` means trial annotations; the title and caption are
        `figure_text` in each trial's plot_config.json."""
        with self._export(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include=True,
        ) as zf:
            cfg = json.loads(zf.read("per_trial/p1__t1/plot_config.json"))
            assert "annotations" not in cfg
            assert set(cfg["figure_text"]) == {"title", "caption"}


class TestBuildSummary:
    """A built bundle says what it made and what failed, and a missing
    browser costs only the formats that need one."""

    @staticmethod
    def _failing_renderer():
        from contextlib import contextmanager

        @contextmanager
        def fake(enabled):
            def render(fig, fmt, width, height, scale):
                raise RuntimeError("no browser")

            yield render

        return fake

    def _build(self, monkeypatch, combos, words, fixations, settings, **formats):
        import scanpath_studio.export as export_mod

        monkeypatch.setattr(export_mod, "_figure_renderer", self._failing_renderer())
        return bulk_export(
            combos,
            words,
            fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=settings,
            options=ExportOptions(
                **{"include_png": False, "include_svg": False, **formats}
            ),
        )

    def test_html_survives_a_failed_png_and_the_summary_says_partly(
        self,
        monkeypatch,
        minimal_combos,
        minimal_words,
        minimal_fixations,
        base_settings,
    ):
        from scanpath_studio.export import summarize_export

        zip_bytes, progress = self._build(
            monkeypatch,
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include_png=True,
            include_html=True,
        )
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
        assert "per_trial/p1__t1/figure.html" in names
        assert not any(n.endswith(".png") for n in names)
        assert (progress.figures_written, progress.figures_failed) == (2, 2)
        assert progress.files_written == len(names)
        summary = summarize_export(progress, len(zip_bytes))
        assert summary.level == "warning"
        assert summary.expand_errors is False
        assert "2 of 4 figures made" in summary.message
        assert "2 failed" in summary.message

    def test_no_figure_made_is_an_error_with_the_list_open(
        self,
        monkeypatch,
        minimal_combos,
        minimal_words,
        minimal_fixations,
        base_settings,
    ):
        from scanpath_studio.export import summarize_export

        zip_bytes, progress = self._build(
            monkeypatch,
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include_png=True,
        )
        summary = summarize_export(progress, len(zip_bytes))
        assert summary.level == "error"
        assert summary.expand_errors is True
        assert summary.message.startswith("No figures were made")
        # The plot configs were still written — the zip is worth downloading.
        assert progress.files_written > 1

    def test_a_clean_tables_only_build_is_ready(self):
        from scanpath_studio.export import ExportProgress, summarize_export

        progress = ExportProgress(total_trials=2, finished_trials=2, files_written=5)
        summary = summarize_export(progress, 2 * 1_048_576)
        assert summary == summary.__class__(
            "success", "Ready · 5 files · 2.0 MB", False
        )

    def test_skipped_trials_are_counted(self):
        from scanpath_studio.export import ExportProgress, summarize_export

        progress = ExportProgress(
            total_trials=2,
            files_written=1,
            trials_skipped=1,
            errors=["p1__t9: empty data, skipped"],
        )
        summary = summarize_export(progress, 0)
        assert summary.level == "warning"
        assert "1 trial skipped" in summary.message


class TestMissingBrowserNote:
    def test_only_when_static_formats_meet_a_missing_browser(self, monkeypatch):
        import scanpath_studio.animation_export as anim
        from scanpath_studio.export import missing_browser_note

        monkeypatch.setattr(anim, "chrome_available", lambda: False)
        assert "HTML" in missing_browser_note(True)
        assert missing_browser_note(False) == ""
        monkeypatch.setattr(anim, "chrome_available", lambda: True)
        assert missing_browser_note(True) == ""


class TestInventory:
    """`index.csv` names every file in the bundle at its actual path."""

    @staticmethod
    def _build(combos, words, fixations, settings, **options):
        data, progress = bulk_export(
            combos,
            words,
            fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=settings,
            options=ExportOptions(include_png=False, include_svg=False, **options),
        )
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            index = pd.read_csv(
                io.BytesIO(zf.read("index.csv")), dtype=str, keep_default_na=False
            )
            readme = zf.read("README.md").decode("utf-8")
        return names, index, readme, progress

    def test_every_file_is_listed_with_its_reading(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        names, index, _, _ = self._build(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include_html=True,
            include_fixations=True,
        )
        written = index[index["status"] == "written"]
        assert set(written["path"]) == set(names) - {"index.csv"}
        figure = written[written["path"] == "per_trial/p1__t2/figure.html"].iloc[0]
        assert (figure["artifact"], figure["format"]) == ("figure", "html")
        assert (figure["participant_id"], figure["trial_id"]) == ("p1", "t2")

    def test_a_collision_suffix_is_the_path_listed(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        """A pattern without the trial id puts both trials at one name."""
        names, index, _, _ = self._build(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include_fixations=True,
            include_plot_config=False,
            path_pattern="{participant_id}/{artifact}.{ext}",
        )
        assert {"p1/fixations.csv", "p1/fixations-2.csv"} <= set(names)
        rows = index.set_index("path")
        assert rows.loc["p1/fixations.csv", "trial_id"] == "t1"
        assert rows.loc["p1/fixations-2.csv", "trial_id"] == "t2"

    def test_a_failed_figure_is_listed_as_failed(
        self,
        monkeypatch,
        minimal_combos,
        minimal_words,
        minimal_fixations,
        base_settings,
    ):
        import scanpath_studio.export as export_module

        def broken(*_args, **_kwargs):
            raise RuntimeError("no figure")

        monkeypatch.setattr(export_module, "make_scanpath_figure", broken)
        names, index, _, _ = self._build(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include_html=True,
            include_plot_config=False,
        )
        failed = index[index["status"] == "failed"]
        assert sorted(failed["path"]) == [
            "per_trial/p1__t1/figure.html",
            "per_trial/p1__t2/figure.html",
        ]
        assert not any(name.endswith(".html") for name in names)
        assert "no figure" in failed["note"].iloc[0]

    def test_the_readme_names_the_version_and_scope(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        from scanpath_studio import __version__

        _, _, readme, _ = self._build(
            minimal_combos,
            minimal_words,
            minimal_fixations,
            base_settings,
            include_fixations=True,
            scope="trial",
            scope_participant="p1",
            scope_trial="t2",
        )
        assert f"Version: {__version__}" in readme
        assert "one trial (participant p1, trial t2)" in readme
        assert "- 1 trial" in readme


class TestTheBundlesOwnFilesKeepTheirNames:
    """A valid path pattern can name a trial's file `README.md` (or
    `index.csv`, `columns.json`, a metadata or combined table). The bundle must
    not then hold two members of that name — a reader would open the plot
    config as the README, and the inventory would point at whichever one it
    met — so the trial's file takes the next free name, and each member is the
    file its row says."""

    @staticmethod
    def _bundle(combos, words, fixations, settings, pattern):
        import warnings

        from scanpath_studio.column_names import ColumnNames, SourceName

        options = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=True,
            include_analysis_family=True,
            include_annotations=True,
            table_format="csv",
            path_pattern=pattern,
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            data, progress = bulk_export(
                combos,
                words,
                fixations,
                canvas_width=800,
                canvas_height=400,
                base_font_size=14,
                font_family="monospace",
                x_field="x",
                y_field="y",
                settings={
                    **settings,
                    "participant_metadata": pd.DataFrame(
                        {"participant_id": ["p1"], "age": [30]}
                    ),
                },
                options=options,
                annotation_records=[
                    {
                        "participant_id": "p1",
                        "trial_id": "t1",
                        "star": True,
                        "tags": [],
                        "note": "",
                    }
                ],
                annotation_dataset="Pilot",
                column_names={
                    "fixations": ColumnNames({"x": SourceName(("CURRENT_FIX_X",))})
                },
            )
        assert progress.errors == []
        assert not [w for w in caught if "Duplicate name" in str(w.message)]
        return zipfile.ZipFile(io.BytesIO(data))

    @pytest.mark.parametrize(
        "pattern",
        [
            "README.md",
            "index.csv",
            "columns.json",
            "run_config.json",
            "annotations.json",
            "metadata/participants.csv",
            "aggregate/all_reader_summary.csv",
            "readme.md",
            "metadata",
            "README.md/{artifact}.{ext}",
            "{artifact}.{ext}",
        ],
    )
    def test_every_member_is_unique_and_is_what_the_inventory_says(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings, pattern
    ):
        from scanpath_studio.annotations import file_dataset
        from scanpath_studio.export import INVENTORY_COLUMNS

        with self._bundle(
            minimal_combos, minimal_words, minimal_fixations, base_settings, pattern
        ) as zf:
            names = zf.namelist()
            folded = [name.casefold() for name in names]
            # Unique — even unpacked where case does not count — and no file
            # has the name of a folder another member sits in.
            assert len(set(folded)) == len(folded)
            assert not [a for a in folded for b in folded if b.startswith(a + "/")]
            index = pd.read_csv(
                io.BytesIO(zf.read("index.csv")), dtype=str, keep_default_na=False
            )
            assert tuple(index.columns) == INVENTORY_COLUMNS
            written = index[index["status"] == "written"]
            assert sorted(written["path"]) == sorted(set(names) - {"index.csv"})
            by_artifact = written.groupby("artifact")["path"].apply(list).to_dict()

            def text(path):
                return zf.read(path).decode("utf-8")

            # The bundle's own files are where the README says they are…
            assert by_artifact["readme"] == ["README.md"]
            assert text("README.md").startswith("# Bulk export")
            assert by_artifact["columns"] == ["columns.json"]
            assert "tables" in json.loads(text("columns.json"))
            assert by_artifact["run_config"] == ["run_config.json"]
            assert "generated_at" in json.loads(text("run_config.json"))
            assert by_artifact["annotations"] == ["annotations.json"]
            assert file_dataset(text("annotations.json")) == "Pilot"
            assert by_artifact["participant_metadata"] == ["metadata/participants.csv"]
            assert "age" in pd.read_csv(zf.open("metadata/participants.csv")).columns
            assert by_artifact["reader_summary"] == ["aggregate/all_reader_summary.csv"]
            # …and every trial's file is the one its row describes.
            configs = by_artifact["plot_config"]
            assert len(configs) == 2
            for path in configs:
                row = written[written["path"] == path].iloc[0]
                selection = json.loads(text(path))["selection"]
                assert selection["trial_id"] == row["trial_id"]

    def test_the_readme_says_why_a_name_has_a_number(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        with self._bundle(
            minimal_combos, minimal_words, minimal_fixations, base_settings, "README.md"
        ) as zf:
            assert "README-2.md" in zf.namelist()
            assert "`-2`, `-3` … added to its name" in zf.read("README.md").decode()


class TestExportPlan:
    """What Build export will write, said before it runs — and Stop."""

    @staticmethod
    def _multipart(words, fixations):
        """t1 read over two screens; t2 on one."""
        screens = {"screen_id": ["s1", "s2", "s1", "s1"]}
        return words.assign(**screens), fixations.assign(**screens)

    def test_screens_and_formats_multiply(
        self, minimal_combos, minimal_words, minimal_fixations
    ):
        from scanpath_studio.export import describe_plan, plan_export
        from scanpath_studio.plots import SCANPATH_LAYER_ORDER

        words, fixations = self._multipart(minimal_words, minimal_fixations)
        options = ExportOptions(include_png=True, include_svg=True)
        plan = plan_export(minimal_combos, words, fixations, options)
        assert (plan.trials, plan.units, plan.figure_files) == (2, 3, 6)
        assert plan.layer_files == 0
        assert describe_plan(plan) == "Exports 2 trials (3 screens): 6 figure files."

        layered = ExportOptions(include_svg=False, separable_layers=True)
        plan = plan_export(minimal_combos, words, fixations, layered)
        assert plan.layer_files == 3 * len(SCANPATH_LAYER_ORDER)
        assert "up to" in describe_plan(plan)

    def test_the_plan_matches_what_the_build_writes(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        from scanpath_studio.export import plan_export

        words, fixations = self._multipart(minimal_words, minimal_fixations)
        options = ExportOptions(
            include_png=False,
            include_svg=False,
            include_html=True,
            scope="trial",
            scope_participant="p1",
            scope_trial="t1",
        )
        plan = plan_export(minimal_combos, words, fixations, options)
        _, progress = bulk_export(
            minimal_combos,
            words,
            fixations,
            canvas_width=800,
            canvas_height=400,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            settings=base_settings,
            options=options,
        )
        assert plan.units == progress.total_trials == 2
        assert plan.figure_files == progress.figures_written == 2

    def test_a_cancelled_build_stops_between_screens(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        from scanpath_studio import progress

        seen: list[int] = []

        def cancel_after_first(state):
            seen.append(state.finished_trials)
            progress.cancel("export-test")

        with (
            progress.task("export-test", title="Export"),
            pytest.raises(progress.Cancelled),
        ):
            bulk_export(
                minimal_combos,
                minimal_words,
                minimal_fixations,
                canvas_width=800,
                canvas_height=400,
                base_font_size=14,
                font_family="monospace",
                x_field="x",
                y_field="y",
                settings=base_settings,
                options=ExportOptions(
                    include_png=False, include_svg=False, include_fixations=True
                ),
                progress_callback=cancel_after_first,
            )
        assert seen == [1]


@pytest.mark.parametrize("self_contained", [False, True])
def test_bundle_html_follows_the_self_contained_choice(
    self_contained, minimal_combos, minimal_words, minimal_fixations, base_settings
):
    import re

    data, _ = bulk_export(
        minimal_combos,
        minimal_words,
        minimal_fixations,
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings=base_settings,
        options=ExportOptions(
            include_png=False,
            include_svg=False,
            include_html=True,
            html_self_contained=self_contained,
        ),
    )
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        page = zf.read("per_trial/p1__t1/figure.html").decode("utf-8")
    loads_from_a_host = bool(re.search(r'<script[^>]*\ssrc="https?://', page))
    assert loads_from_a_host is not self_contained


@pytest.mark.parametrize(
    ("scope", "selection", "expected"),
    [
        ("text", {"scope_text": "para1"}, 0),
        ("participant", {}, 0),
        ("trial", {"scope_participant": "p1"}, 0),
        ("trial", {"scope_trial": "t1"}, 0),
        ("participant", {"scope_participant": "missing"}, 0),
        ("all", {}, 2),
    ],
)
def test_an_unresolved_scope_never_widens_the_bundle(
    minimal_combos, minimal_words, minimal_fixations, scope, selection, expected
):
    from scanpath_studio.export import plan_export

    combos = minimal_combos.drop(columns="text_id")
    options = ExportOptions(
        include_png=False,
        include_svg=False,
        include_plot_config=False,
        include_fixations=True,
        scope=scope,
        **selection,
    )
    plan = plan_export(combos, minimal_words, minimal_fixations, options)
    assert (plan.trials, plan.units) == (expected, expected)
    payload, progress = bulk_export(
        combos,
        minimal_words,
        minimal_fixations,
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings={},
        options=options,
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert (
            sum(name.endswith("/fixations.csv") for name in archive.namelist())
            == expected
        )
        assert progress.total_trials == expected


def test_screen_discovery_skips_ordinary_trials_but_finds_sample_only_screens(
    minimal_combos, monkeypatch
):
    from scanpath_studio import export

    empty = pd.DataFrame()
    with monkeypatch.context() as m:

        def unexpected(*args):
            pytest.fail(
                "Sliced a trial to look for a screen column absent from every frame"
            )

        m.setattr(export, "extract_trial", unexpected)
        assert export.export_units(minimal_combos, empty, minimal_combos).equals(
            minimal_combos
        )
        assert export.export_units(
            minimal_combos, empty, minimal_combos, screens=("intro",)
        ).empty
    raw = minimal_combos.assign(screen_id=["intro", "question"], screen_index=[1, 1])
    units = export.export_units(minimal_combos, empty, empty, raw, screens=("intro",))
    assert units[["trial_id", "screen_id"]].values.tolist() == [["t1", "intro"]]


@pytest.mark.parametrize("other_recorded", [False, True])
def test_scoped_text_metadata_respects_recorded_ids_in_zip_and_preview(
    minimal_combos, minimal_words, minimal_fixations, base_settings, other_recorded
):
    from scanpath_studio.data import TEXT_ID_MAPPED
    from scanpath_studio.export import bundle_contents

    combos = minimal_combos.iloc[:1].assign(text_id="t1")
    words = minimal_words.assign(text_id="textA", **{TEXT_ID_MAPPED: True})
    fix = minimal_fixations.assign(text_id="t1", **{TEXT_ID_MAPPED: other_recorded})
    settings = {
        **base_settings,
        "text_metadata": pd.DataFrame(
            {"text_id": ["textA", "t1"], "credit": ["selected", "unrelated"]}
        ),
    }
    options = ExportOptions(
        include_png=False, include_svg=False, include_plot_config=False
    )
    preview = bundle_contents(
        combos, words, fix, None, options=options, settings=settings
    )
    planned = {entry["Path"]: entry["Contents"] for entry in preview.files}
    payload, _ = bulk_export(
        combos,
        words,
        fix,
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings=settings,
        options=options,
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        path = "metadata/texts.csv"
        if other_recorded:
            assert path not in planned and path not in archive.namelist()
        else:
            assert planned[path] == "Text metadata · 1 row"
            assert pd.read_csv(archive.open(path)).to_dict("records") == [
                {"text_id": "textA", "credit": "selected"}
            ]


def test_chunked_csv_preserves_exact_bytes_headers_and_paths():
    from scanpath_studio.column_names import ColumnNames, SourceName
    from scanpath_studio.export import _write_table

    rows = 5003
    frame = pd.DataFrame(
        {
            "x": [1.25] * rows,
            "note": ["hé,\nשלום"] * rows,
            "image_path": ["/private/stimuli/words.png"] * rows,
        }
    )
    frame.loc[5001, "x"] = None
    expected = (
        frame.rename(columns={"x": "Gaze X"})
        .assign(image_path="words.png")
        .to_csv(index=False)
        .encode()
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        count = _write_table(
            archive,
            "gaze.csv",
            frame,
            "csv",
            ColumnNames({"x": SourceName(("Gaze X",))}),
        )
    with zipfile.ZipFile(out) as archive:
        assert archive.read("gaze.csv") == expected
        assert count == len(expected) == archive.getinfo("gaze.csv").file_size


@pytest.mark.parametrize("screens", [("intro",), ("intro", "question"), None])
def test_bundle_notes_follow_the_selected_reading_and_screen(screens):
    from scanpath_studio.synthetic import make_multipart_synthetic_data

    words, fixations = make_multipart_synthetic_data()
    words, fixations = (
        pd.concat(
            [
                frame.assign(participant_id="p1"),
                frame.loc[frame["screen_id"] == "intro"].assign(participant_id="p2"),
            ],
            ignore_index=True,
        )
        for frame in (words, fixations)
    )
    combos = words[["participant_id", "trial_id"]].drop_duplicates()
    records = [
        {
            "participant_id": p,
            "trial_id": t,
            **({"screen_id": screen} if screen else {}),
            "note": f"{p}/{screen or 'trial'}",
        }
        for p, t in combos.itertuples(index=False, name=None)
        for screen in (None, "intro", "question")
    ]
    options = ExportOptions(
        include_png=False,
        include_svg=False,
        include_plot_config=False,
        include_fixations=True,
        include_annotations=True,
        screens=screens,
    )
    payload, _ = bulk_export(
        combos,
        words,
        fixations,
        canvas_width=800,
        canvas_height=400,
        base_font_size=12,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings={},
        options=options,
        annotation_records=records,
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        notes = {
            row["note"]
            for row in json.loads(archive.read("annotations.json"))["annotations"]
        }
        inventory = pd.read_csv(archive.open("index.csv"))
        tables = inventory[inventory["artifact"].eq("fixations")]
        drawn = set(zip(tables["participant_id"], tables["screen_id"], strict=True))
    assert notes == (
        {"p1/trial", "p2/trial"} | {f"{p}/{s}" for p, s in drawn}
        if screens is not None
        else {r["note"] for r in records}
    )


def test_handoff_plan_matches_collision_paths_and_discloses_stimulus_text(
    minimal_combos, minimal_words, minimal_fixations, base_settings
):
    from scanpath_studio.export import bundle_contents

    words = minimal_words.assign(text="Juniper", total_fixation_duration_ms=12.0)
    options = ExportOptions(
        include_png=False,
        include_svg=False,
        include_html=True,
        include_fixations=True,
        include_measures=True,
        include_annotations=True,
        path_pattern="{artifact}.{ext}",
        metadata_fields=("group",),
    )
    settings = {
        **base_settings,
        "redact_text": True,
        "participant_metadata": pd.DataFrame(
            {"participant_id": ["p1"], "group": ["c"], "initials": ["AB"]}
        ),
    }
    records = [{"participant_id": "p1", "trial_id": "t2", "note": "review"}]
    planned = bundle_contents(
        minimal_combos,
        words,
        minimal_fixations,
        None,
        options=options,
        settings=settings,
        annotation_records=records,
    )
    payload, _ = bulk_export(
        minimal_combos,
        words,
        minimal_fixations,
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings=settings,
        options=options,
        annotation_records=records,
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert {row["Path"] for row in planned.files} == set(archive.namelist())
        for row in planned.files:
            if row["Table columns"]:
                assert row["Table columns"] == ", ".join(
                    pd.read_csv(archive.open(row["Path"])).columns
                )
        assert pd.read_csv(archive.open("measures-2.csv"))["text"].tolist() == [
            "Juniper",
            "Juniper",
        ]
    paths = {row["Path"]: row for row in planned.files}
    assert paths["figure-2.html"]["Trial"] == "t2"
    assert (
        paths["metadata/participants.csv"]["Table columns"] == "participant_id, group"
    )
    assert paths["annotations.json"]["Contents"] == "1 annotation record"
    assert any("recorded stimulus words" in note for note in planned.notes)


@pytest.mark.parametrize("empty", [False, True])
def test_a_figure_only_or_empty_bundle_has_no_csv_reader_or_schema(
    minimal_combos, minimal_words, minimal_fixations, base_settings, empty
):
    from scanpath_studio.export import bundle_contents

    combos = minimal_combos.iloc[:0] if empty else minimal_combos.iloc[:1]
    options = ExportOptions(
        include_png=False,
        include_svg=False,
        include_html=True,
        include_plot_config=False,
    )
    preview = bundle_contents(
        combos,
        minimal_words,
        minimal_fixations,
        None,
        options=options,
        settings=base_settings,
    )
    data, _ = bulk_export(
        combos,
        minimal_words,
        minimal_fixations,
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="Arial",
        x_field="x",
        y_field="y",
        options=options,
        settings=base_settings,
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert {row["Path"] for row in preview.files} == set(archive.namelist())
        assert {"columns.json", "read_csv.R"}.isdisjoint(archive.namelist())


def test_retry_renders_only_failed_formats_and_reuses_successful_contents(
    minimal_combos, minimal_words, minimal_fixations, base_settings, monkeypatch
):
    from contextlib import contextmanager

    from scanpath_studio import export
    from scanpath_studio.export_retry import retry_failed_figures

    calls = []
    fail = True

    @contextmanager
    def renderer(_enabled):
        def render(_fig, fmt, *_dimensions):
            calls.append(fmt)
            if fmt == "pdf" and fail:
                raise ValueError("Renderer unavailable")
            return f"{fmt}:{len(calls)}".encode()

        yield render

    monkeypatch.setattr(export, "_figure_renderer", renderer)
    options = ExportOptions(
        include_png=True,
        include_svg=False,
        include_pdf=True,
        include_fixations=True,
        path_pattern="supplement",
    )
    args = dict(
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings=base_settings,
        options=options,
    )
    frames = minimal_combos, minimal_words, minimal_fixations
    original, partial = bulk_export(*frames, **args)
    assert calls == ["png", "pdf", "png", "pdf"]
    assert partial.retryable_figures == 2
    cache = {"data": original, "sig": ("frames", "settings"), "progress": partial}
    with pytest.raises(ValueError, match="changed"):
        retry_failed_figures(cache, ("changed data", "settings"), *frames, **args)
    assert len(calls) == 4
    fail = False
    repaired, progress = retry_failed_figures(cache, cache["sig"], *frames, **args)
    assert calls[4:] == ["pdf", "pdf"]
    assert (
        progress.figures_written,
        progress.figures_failed,
        progress.retryable_figures,
    ) == (4, 0, 0)
    with (
        zipfile.ZipFile(io.BytesIO(original)) as before,
        zipfile.ZipFile(io.BytesIO(repaired)) as after,
    ):
        inventory = pd.read_csv(before.open("index.csv"))
        previously_failed = set(inventory.loc[inventory.status == "failed", "path"])
        assert set(after.namelist()) == set(before.namelist()) | previously_failed
        assert all(
            after.read(path) == before.read(path)
            for path in before.namelist()
            if path != "index.csv"
        )
        assert all(after.read(path).startswith(b"pdf:") for path in previously_failed)
        assert set(pd.read_csv(after.open("index.csv")).status) == {"written"}


def test_uploaded_study_references_are_carried_through_a_comparison_bundle(
    minimal_combos, minimal_words, minimal_fixations, base_settings
):
    from scanpath_studio import dataset_credit, persistence

    state = {
        "data_source_choice": "upload-token-1",
        "single_compare_toggle": True,
        "_share_selection": {"compare": {"source": "upload-token-2"}},
    }
    dataset_credit.save_credit(
        state,
        "upload-token-1",
        {
            "title": "Pilot {one}",
            "authors": "García, Ana\nCanal Lab",
            "version": "2",
            "credit": "Canal Lab unpublished pilot, revision two.",
        },
    )
    dataset_credit.save_credit(
        state,
        "upload-token-2",
        {
            "title": "Repeat study",
            "doi": "https://doi.org/10.1234/example",
        },
    )
    restored = persistence._restorable_session(state)
    assert restored[dataset_credit.STORE_KEY] == state[dataset_credit.STORE_KEY]
    refs = dataset_credit.references(state)
    assert [ref["side"] for ref in refs] == ["A", "B"]
    bundle = _bulk(
        minimal_combos,
        minimal_words,
        minimal_fixations,
        {**base_settings, "dataset_references": refs},
        include_fixations=True,
    )
    bib = bundle.read("CITATION.bib").decode()
    assert bib.count("@misc{scanpath-dataset-") == 2
    first, second = bib.split("@misc{scanpath-dataset-a,", 1)[1].split(
        "@misc{scanpath-dataset-b,", 1
    )
    assert "doi " not in first and r"Pilot \{one\}" in first
    assert "10.1234/example" in second
    readme = bundle.read("README.md").decode()
    assert "Dataset for the exported trials: Canal Lab unpublished pilot" in readme
    assert "Second dataset in the on-screen comparison: Repeat study" in readme
    state["single_compare_toggle"] = False
    assert len(dataset_credit.references(state)) == 1
    dataset_credit.save_credit(state, "upload-token-1", {})
    assert dataset_credit.references(state) == []


@pytest.mark.parametrize("first_set_failure", ["figure", "split"])
def test_retry_layers_keeps_successful_files_and_retries_remaining_failures(
    minimal_combos,
    minimal_words,
    minimal_fixations,
    base_settings,
    monkeypatch,
    first_set_failure,
):
    from contextlib import contextmanager

    from scanpath_studio import export
    from scanpath_studio import progress as jobs
    from scanpath_studio.export_retry import retry_failed_figures
    from scanpath_studio.export_status import ExportStage

    # A single reading on two screens exercises the unit key. The naming
    # pattern omits both artifact and extension, so every filename collides.
    combos = minimal_combos.iloc[:1]

    def two_screens(frame):
        return frame.assign(
            screen_id=frame.trial_id.map({"t1": "A", "t2": "B"}),
            screen_index=frame.trial_id.map({"t1": 1, "t2": 2}),
            trial_id="t1",
        )

    frames = combos, two_screens(minimal_words), two_screens(minimal_fixations)
    options = ExportOptions(
        include_png=True,
        include_svg=False,
        include_pdf=True,
        include_fixations=True,
        separable_layers=True,
        path_pattern="panels/supplement",
    )
    args = dict(
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings=base_settings,
        options=options,
    )
    attempt = 0
    calls = []
    renderers = []
    make = export.make_scanpath_figure

    def make_for_screen(words, *rest, **kwargs):
        screen = words["screen_id"].iloc[0]
        if attempt == 0 and screen == "B" and first_set_failure == "figure":
            raise ValueError("Figure setup unavailable")
        return make(words, *rest, **kwargs).update_layout(meta={"screen": screen})

    def split(fig, *, only=None):
        screen = fig.layout.meta["screen"]
        if attempt == 2:
            assert only == ({"word_boxes"} if screen == "A" else {"fixations"})
        if (attempt == 0 and screen == "B") or (attempt == 1 and screen == "A"):
            raise ValueError("Split unavailable")
        return {
            layer: (screen, layer)
            for layer in ("word_boxes", "fixations")
            if only is None or layer in only
        }

    @contextmanager
    def renderer(enabled):
        renderers.append(enabled)

        def render(fig, fmt, *_):
            screen, layer = (
                fig if isinstance(fig, tuple) else (fig.layout.meta["screen"], "figure")
            )
            key = screen, layer, fmt
            calls.append(key)
            if attempt == 0 and key in {
                ("A", "word_boxes", "png"),
                ("A", "figure", "pdf"),
            }:
                raise ValueError("First attempt")
            if attempt == 1 and key == ("B", "fixations", "pdf"):
                raise ValueError("PDF still unavailable")
            return f"{attempt}/{screen}/{layer}/{fmt}".encode()

        yield render

    monkeypatch.setattr(export, "make_scanpath_figure", make_for_screen)
    monkeypatch.setattr(export, "split_scanpath_layers", split)
    monkeypatch.setattr(export, "_figure_renderer", renderer)

    def contents(payload):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names))
            inventory = pd.read_csv(archive.open("index.csv"), keep_default_na=False)
            paths = inventory.path[inventory.path.ne("")]
            assert paths.is_unique
            assert set(inventory.path[inventory.status.eq("written")]) == set(names) - {
                "index.csv"
            }
            return inventory, {p: archive.read(p) for p in names if p != "index.csv"}

    original, progress = bulk_export(*frames, **args)
    before, retained = contents(original)
    assert ("A", "fixations", "pdf") in calls  # Continued past the first failed layer.
    assert progress.retryable_figures == (5 if first_set_failure == "figure" else 3)
    assert set(before.loc[before.artifact == "layers", "screen_id"]) == {"B"}
    path = before.loc[
        (before.artifact == "layer:word_boxes") & (before.format == "png"), "path"
    ].item()
    assert path.startswith("panels/supplement")
    cache = {"data": original, "sig": ("all data and settings",), "progress": progress}
    attempt = 1
    calls.clear()
    updated, progress = retry_failed_figures(cache, cache["sig"], *frames, **args)
    middle, written = contents(updated)
    assert len(calls) == len(set(calls))
    expected = {
        ("A", "figure", "pdf"),
        *(
            ("B", layer, fmt)
            for layer in ("word_boxes", "fixations")
            for fmt in ("png", "pdf")
        ),
    }
    if first_set_failure == "figure":
        expected.update({("B", "figure", "png"), ("B", "figure", "pdf")})
    assert set(calls) == expected
    assert retained.items() <= written.items()
    assert (progress.figures_failed, progress.retryable_figures) == (2, 2)
    failures = middle[middle.status.eq("failed")]
    assert set(zip(failures.screen_id, failures.artifact, failures.format)) == {
        ("A", "layer:word_boxes", "png"),
        ("B", "layer:fixations", "pdf"),
    }
    assert failures.loc[failures.screen_id.eq("A"), "path"].item() == path
    assert set(
        middle.path[middle.artifact.str.startswith("layer:")].str.startswith(
            "panels/supplement"
        )
    ) == {True}

    cache = {**cache, "data": updated, "progress": progress}
    attempt = 2
    stages = []

    def cancel_on_merge(status):
        stages.append(status.stage)
        if (
            status.stage == ExportStage.FINALIZING
            and "original files" in status.message
        ):
            jobs.cancel("layer retry")

    with (
        pytest.raises(jobs.Cancelled),
        jobs.task("layer retry", title="Repairing a bundle"),
    ):
        retry_failed_figures(
            cache, cache["sig"], *frames, status_callback=cancel_on_merge, **args
        )
    assert ExportStage.READY not in stages
    assert cache["data"] == updated
    calls.clear()
    stages.clear()
    final, progress = retry_failed_figures(
        cache,
        cache["sig"],
        *frames,
        status_callback=lambda s: stages.append(s.stage),
        **args,
    )
    done, files = contents(final)
    assert stages.count(ExportStage.READY) == 1 and stages[-1] == ExportStage.READY
    assert len(renderers) == 4  # One warm renderer per build/retry.
    assert calls == [("A", "word_boxes", "png"), ("B", "fixations", "pdf")]
    assert written.items() <= files.items()
    assert files[path] == b"2/A/word_boxes/png"
    assert set(done.status) == {"written"}
    assert (
        progress.figures_written,
        progress.figures_failed,
        progress.retryable_figures,
    ) == (12, 0, 0)
