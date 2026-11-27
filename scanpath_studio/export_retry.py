"""Retry failed figure files in a matching, in-session export bundle."""

from __future__ import annotations

import csv
import io
import zipfile
from contextlib import nullcontext
from dataclasses import dataclass, replace
from tempfile import TemporaryFile
from time import perf_counter

import pandas as pd

from .export import _write_inventory, bulk_export, bundle_member_names
from .export_archive import open_bundle
from .export_status import ExportStage, emit_status
from .progress import report


def _index(archive):
    with (
        archive.open("index.csv") as member,
        io.TextIOWrapper(member, encoding="utf-8", newline="") as text,
    ):
        return list(csv.DictReader(text))


def _unit_key(row):
    return row["participant_id"], row["trial_id"], row["screen_id"]


def _figure_row(row):
    artifact = row["artifact"]
    return artifact in ("figure", "layers") or artifact.startswith("layer:")


class _UnitRetry:
    """Which named files to retry, and which layers are still undiscovered."""

    def __init__(self, rows):
        self.rows = {(r["artifact"], r["format"]): r for r in rows}
        self.paths = {
            (artifact.replace("layer:", "layers/", 1), fmt): row["path"]
            for (artifact, fmt), row in self.rows.items()
            if row["path"]
        }
        self.layer_failures = [
            (artifact, fmt, row["path"])
            for (artifact, fmt), row in self.rows.items()
            if artifact != "figure" and row["status"] == "failed"
        ]

    @property
    def layer_names(self):
        if ("layers", "") in self.rows:
            return None
        return {
            artifact.removeprefix("layer:") for artifact, _, _ in self.layer_failures
        }

    def wants(self, artifact, fmt):
        row = self.rows.get((artifact, fmt))
        if row is not None:
            return row["status"] == "failed"
        # An earlier split failed before finding every layer. Older inventories
        # can also have successful named layers beside that failure.
        return artifact.startswith("layer:") and ("layers", "") in self.rows


@dataclass
class _RetryPlan:
    units: dict[tuple[str, str, str], _UnitRetry]
    reserved: set[str]

    def needs_kaleido(self):
        return any(
            row["status"] == "failed" and row["format"] != "html"
            for unit in self.units.values()
            for row in unit.rows.values()
        )

    def select_units(self, units):
        keys = [
            (str(p), str(t), str(s) if pd.notna(s) else "")
            for p, t, s in units.reindex(
                columns=["participant_id", "trial_id", "screen_id"]
            ).itertuples(index=False, name=None)
        ]
        if self.units.keys() - set(keys):
            raise ValueError(
                "A reading or screen from the failed export is missing. Build a new bundle."
            )
        return units.loc[[key in self.units for key in keys]]


def _copy_member(source, destination, info):
    # A fresh header, not a copy of the source's: its extra field holds the
    # source's own Zip64 sizes and offset, which zipfile would write beside the
    # field it adds, leaving a local header extractors reject. The known size
    # still decides whether this member needs Zip64.
    target = zipfile.ZipInfo(info.filename, info.date_time)
    target.compress_type = info.compress_type
    target.external_attr = info.external_attr
    target.file_size = info.file_size
    with source.open(info) as src, destination.open(target, "w") as dest:
        while chunk := src.read(1024 * 1024):
            report()
            dest.write(chunk)


def retry_failed_figures(
    cache,
    signature,
    combos,
    words,
    fixations,
    *,
    options,
    status_callback=None,
    _archive=None,
    **kwargs,
):
    """Retain existing files and regenerate only failed figures or figure layers."""
    if cache["sig"] != signature:
        raise ValueError("The data or export settings changed. Build a new bundle.")
    started = perf_counter()

    def on_render_status(status):
        if status_callback and status.stage != ExportStage.READY:
            status_callback(status)

    with (
        open_bundle(cache["data"]) as original,
        zipfile.ZipFile(original) as previous,
        TemporaryFile() as repaired,
    ):
        inventory = _index(previous)
        failed = {
            _unit_key(row)
            for row in inventory
            if _figure_row(row) and row["status"] == "failed"
        }
        if not failed:
            return cache["data"], cache["progress"]
        rows_by_unit = {key: [] for key in failed}
        for row in inventory:
            key = _unit_key(row)
            if key in failed and _figure_row(row):
                rows_by_unit[key].append(row)
        plan = _RetryPlan(
            {key: _UnitRetry(rows) for key, rows in rows_by_unit.items()},
            set(bundle_member_names(options))
            | set(previous.namelist())
            | {row["path"] for row in inventory if row["path"]},
        )
        # All selected screens and formats share one renderer. Keep the user's
        # naming and title patterns when an earlier split could not name its layers.
        renderer_options = replace(
            options,
            include_plot_config=False,
            include_annotations=False,
            include_fixations=False,
            include_measures=False,
            include_raw_gaze=False,
            include_analysis_family=False,
            metadata_fields=(),
            trial_metadata_fields=(),
            text_metadata_fields=(),
        )
        readings = {(p, t) for p, t, _ in failed}
        selected = [
            (str(p), str(t)) in readings
            for p, t in combos[["participant_id", "trial_id"]].itertuples(
                index=False, name=None
            )
        ]
        with zipfile.ZipFile(repaired, "w", zipfile.ZIP_DEFLATED) as repair_archive:
            _, rerun = bulk_export(
                combos.loc[selected],
                words,
                fixations,
                options=renderer_options,
                _retry=plan,
                _archive=repair_archive,
                status_callback=on_render_status,
                **kwargs,
            )
        emit_status(
            status_callback,
            ExportStage.FINALIZING,
            "Combining the repaired figures with the original files…",
            started_at=started,
        )
        output = io.BytesIO() if _archive is None else None
        with (
            zipfile.ZipFile(repaired) as rebuilt,
            nullcontext(_archive)
            if _archive is not None
            else zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive,
        ):
            for info in previous.infolist():
                if info.filename != "index.csv":
                    _copy_member(previous, archive, info)
            # Replace each failed reading's old placeholder with the actual named
            # outcomes. A previously named layer stays failed if a later split
            # cannot find it, so its absence cannot count as a successful retry.
            new_rows = [row for row in _index(rebuilt) if _figure_row(row)]

            def file_key(row):
                return _unit_key(row), row["artifact"], row["format"]

            updated = {file_key(row) for row in new_rows}
            inventory = [
                row
                for row in inventory
                if row["status"] != "failed"
                or not _figure_row(row)
                or (row["artifact"] != "layers" and file_key(row) not in updated)
            ]
            still_failed = sum(
                row["status"] == "failed" and _figure_row(row) for row in inventory
            )
            for row in new_rows:
                if row["status"] == "written":
                    _copy_member(rebuilt, archive, rebuilt.getinfo(row["path"]))
            inventory.extend(new_rows)
            report()
            _write_inventory(archive, inventory)
            failed_count = sum(
                row["status"] == "failed" and _figure_row(row) for row in inventory
            )
            progress = replace(
                cache["progress"],
                files_written=len(archive.namelist()),
                bytes_written=sum(info.file_size for info in archive.infolist()),
                figures_written=sum(
                    row["status"] == "written" and _figure_row(row) for row in inventory
                ),
                figures_failed=failed_count,
                # A file this run failed on counts when the failure can pass on
                # another try; one it did not reach again counts as before.
                retryable_figures=rerun.retryable_figures + still_failed,
                errors=[
                    f"{row['participant_id']}/{row['trial_id']}: {row['note']}"
                    for row in inventory
                    if row["status"] in {"failed", "skipped"}
                ],
            )
    emit_status(
        status_callback,
        ExportStage.READY,
        "Export archive is ready.",
        started_at=started,
        completed=progress.finished_trials,
        total=progress.total_trials,
    )
    return output.getvalue() if output is not None else None, progress
