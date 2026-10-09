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
        """Round 10, finding 5: `../{artifact}.{ext}` wrote `../plot_config.json`,
        and an empty pattern a member with no name."""
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
            # EXP-23: stacked copies only when the tables are combined — the
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
        """EXP-15: with the combined tables *and* the full family ticked,
        `aggregate/all_fixations.*` was written twice with different columns —
        a zip keeps both entries, and a reader silently sees only one."""
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


class TestExportComputesNoMeasures:
    """EXP-23: Export follows AN-32 — the word tables carry the reading
    measures the dataset brought, and nothing is computed."""

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
        assert "This dataset brought none" in readme

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
    """EXP-23: *Combine all trials into one file* writes each table once,
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
    """EXP-4 / VIZ-24: bulk-exported figures honour the PRE-3 drift correction;
    the exported tables deliberately stay uncorrected."""

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
    """VIZ-5: the per-layer figure breakdown dropped under `layers/`."""

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
        # drop the combined figure (they're in separate try blocks now).
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
    """DATA-16 / security audit S4.

    `image_path` is a passthrough meta field on both schemas, so it survives
    normalization and rides into the exported fixation tables — and a fixations
    CSV is exactly the file that gets attached to a paper, posted to OSF, or
    mailed to a collaborator. `/Users/<name>/` discloses the OS account name and
    the rest discloses the directory layout, including where a MultiplEYE corpus
    lives on the machine.
    """

    LEAKY = "/Users/someone/Projects/corpora/images/2_1_1_Ele__paragraph.png"

    def _export(self, combos, words, fixations, settings, fmt="csv"):
        # A brought measure, so the words table is written too (EXP-23).
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
        """Checked the way the audit found it: grep every zip member."""
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
    """UX-179: the Export bundle can carry the exported trials' annotations."""

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
            # DATA-48: schema 3 names the dataset the annotations were made on.
            assert file_dataset(text) == "Pilot"
            assert "annotations.json" in zf.read("README.md").decode("utf-8")

    def test_no_annotation_in_scope_means_no_file_and_no_readme_line(
        self, minimal_combos, minimal_words, minimal_fixations, base_settings
    ):
        """Round 10, finding 6: the README promised a file the scope left out."""
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
    """EXP-24: a built bundle says what it made and what failed, and a missing
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
    """#412 — a valid path pattern could name a trial's file `README.md` (or
    `index.csv`, `columns.json`, a metadata or combined table): the bundle then
    held two members of that name, a reader opened the plot config as the
    README, and the inventory pointed at whichever one it met. The trial's file
    now takes the next free name, and each member is the file its row says."""

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
