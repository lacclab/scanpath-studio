"""Retry named figure failures in a matching, in-session export bundle."""

from __future__ import annotations

import csv
import io
import shutil
import zipfile
from copy import copy
from dataclasses import replace

from .export import DEFAULT_PATH_PATTERN, _write_inventory, bulk_export


def _index(archive):
    with (
        archive.open("index.csv") as member,
        io.TextIOWrapper(member, encoding="utf-8", newline="") as text,
    ):
        return list(csv.DictReader(text))


def _file_key(row):
    return tuple(
        row[key] for key in ("participant_id", "trial_id", "screen_id", "format")
    )


def retry_failed_figures(
    cache, signature, combos, words, fixations, *, options, **kwargs
):
    """Reuse prior members only while data, scope and rendering settings match.

    The input is the session's own last completed bundle. A failed layer set has
    no individual file names in the inventory, so it stays listed for a full rebuild.
    """
    if cache["sig"] != signature:
        raise ValueError("The data or export settings changed. Build a new bundle.")
    with zipfile.ZipFile(io.BytesIO(cache["data"])) as previous:
        inventory = _index(previous)
        failures = {
            _file_key(row): row
            for row in inventory
            if row["artifact"] == "figure"
            and row["status"] == "failed"
            and row["format"] in options.figure_formats()
        }
        if not failures:
            return cache["data"], cache["progress"]
        # A reading can need just PDF while its neighbour still needs SVG and
        # PDF. Batch identical requests so they share a renderer.
        per_reading = {}
        for pid, tid, screen, fmt in failures:
            per_reading.setdefault((pid, tid, screen), []).append(fmt)
        batches = {}
        for (pid, tid, screen), formats in per_reading.items():
            batches.setdefault((screen, tuple(sorted(formats))), set()).add((pid, tid))
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for info in previous.infolist():
                if info.filename == "index.csv":
                    continue
                with previous.open(info) as src, archive.open(copy(info), "w") as dest:
                    shutil.copyfileobj(src, dest, length=1024 * 1024)
            for (screen, formats), readings in batches.items():
                selected = [
                    (str(pid), str(tid)) in readings
                    for pid, tid in combos[["participant_id", "trial_id"]].itertuples(
                        index=False, name=None
                    )
                ]
                retry_options = replace(
                    options,
                    scope="all",
                    screens=(screen,) if screen else None,
                    include_png="png" in formats,
                    include_svg="svg" in formats,
                    include_pdf="pdf" in formats,
                    include_html="html" in formats,
                    include_plot_config=False,
                    include_annotations=False,
                    include_fixations=False,
                    include_measures=False,
                    include_raw_gaze=False,
                    include_analysis_family=False,
                    separable_layers=False,
                    metadata_fields=(),
                    trial_metadata_fields=(),
                    text_metadata_fields=(),
                    path_pattern=DEFAULT_PATH_PATTERN,
                )
                payload, _ = bulk_export(
                    combos[selected], words, fixations, options=retry_options, **kwargs
                )
                with zipfile.ZipFile(io.BytesIO(payload)) as rebuilt:
                    for result in _index(rebuilt):
                        if result["artifact"] != "figure":
                            continue
                        row = failures[_file_key(result)]
                        row["status"], row["note"] = result["status"], result["note"]
                        if result["status"] == "written":
                            archive.writestr(row["path"], rebuilt.read(result["path"]))
            _write_inventory(archive, inventory)
            progress = replace(
                cache["progress"],
                files_written=len(archive.namelist()),
                bytes_written=sum(info.file_size for info in archive.infolist()),
                figures_written=sum(
                    row["status"] == "written"
                    and (
                        row["artifact"] == "figure"
                        or row["artifact"].startswith("layer:")
                    )
                    for row in inventory
                ),
                figures_failed=sum(row["status"] == "failed" for row in inventory),
                retryable_figures=sum(
                    row["status"] == "failed" for row in failures.values()
                ),
                errors=[
                    f"{row['participant_id']}/{row['trial_id']}: {row['note']}"
                    for row in inventory
                    if row["status"] in {"failed", "skipped"}
                ],
            )
    return output.getvalue(), progress
