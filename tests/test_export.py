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
        show_colorbars=False,
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
            include_mega_table=True,
            table_format="csv",
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
        assert progress.finished_trials == 2
        assert progress.errors == []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            assert "README.md" in names
            assert "aggregate/all_fixations.csv" in names
            assert "aggregate/all_measures.csv" in names
            assert "per_trial/p1__t1/fixations.csv" in names
            assert "per_trial/p1__t1/measures.csv" in names
            assert "per_trial/p1__t1/plot_config.json" in names
            # No figures
            assert not any(n.endswith(".png") for n in names)
            assert not any(n.endswith(".svg") for n in names)
            cfg = json.loads(zf.read("per_trial/p1__t1/plot_config.json"))
            assert cfg["selection"]["participant_id"] == "p1"
            assert cfg["selection"]["trial_id"] == "t1"

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
            assert "run_config.json" in names
            assert "per_trial/p1__t1/saccades.csv" in names
            assert "per_trial/p1__t1/word_measures.csv" in names
            assert "per_trial/p1__t1/trial_summary.csv" in names
            assert "aggregate/all_saccades.csv" in names
            assert "aggregate/all_word_measures.csv" in names
            assert "aggregate/all_reader_summary.csv" in names

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
            include_mega_table=False,
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
            include_mega_table=False,
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
            include_mega_table=False,
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
            captured["color_by_line"] = kwargs.get("color_by_line")
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
        opts = ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=False,
            include_fixations=True,
            include_measures=True,
            include_mega_table=True,
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
