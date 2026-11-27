#!/usr/bin/env python
"""Compare one session's EyeLink import with Data Viewer's reports for it.

A maintainer check, not part of the package and not run in CI: it imports one
OneStop recording with ``import_eyelink`` and sets it against Data Viewer's
fixation and interest-area reports of the same session (the per-part reports
``update_sample_data --source-dir`` reads, ``.csv``, ``.tsv`` or ``.zip``):

    SCANPATH_EXPERIMENTAL=1 uv run --extra edf python scripts/eyelink_onestop_check.py \\
        "/path/to/asc/l42_2070.asc" \\
        --experiment-dir "/path/to/ose_3p_l1_l60_tower_st_mit_l1_latest_widthfix" \\
        --fixations /path/to/fixations_P.tsv --ia /path/to/ia_P.tsv

Trials are matched on a ``TRIAL_VAR`` both carry (``Trial_Index_`` by default:
a report column, and a column of the import's trial metadata). Both sides time a
fixation from the trial's ``START`` line, so a fixation is paired with Data
Viewer's by its end (``CURRENT_FIX_END`` is the last millisecond); Data Viewer
cuts a fixation that straddles its interest period's start to that start, which
shows up as an onset difference. The import's screen is the one holding most of
the paired fixations, and its word boxes are compared with the report's
interest areas (``IA_LEFT .. IA_RIGHT``, ``IA_TOP .. IA_BOTTOM``).
"""

from __future__ import annotations

import argparse
import io
import os
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

FIXATION_COLUMNS = [
    "CURRENT_FIX_START",
    "CURRENT_FIX_END",
    "CURRENT_FIX_X",
    "CURRENT_FIX_Y",
]
IA_COLUMNS = ["IA_ID", "IA_LABEL", "IA_LEFT", "IA_RIGHT", "IA_TOP", "IA_BOTTOM"]
BOX_COLUMNS = ["word_id", "text", "x", "y", "width", "height"]


def read_report(path: Path, session: str, columns: list[str]) -> pd.DataFrame:
    """The rows of ``session`` in a Data Viewer report, read line by line so
    that a multi-gigabyte report is never loaded whole."""
    sep = "\t" if ".tsv" in path.name else ","
    if path.suffix == ".zip":
        archive = zipfile.ZipFile(path)
        raw = archive.open(archive.namelist()[0])
    else:
        raw = path.open("rb")
    prefix = (session + sep, f'"{session}"{sep}')
    rows: list[str] = []
    with io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace") as lines:
        header = next(lines)
        for line in lines:
            if line.startswith(prefix):
                rows.append(line)
            elif rows:  # a report lists each session's rows together
                break
    frame = pd.read_csv(
        io.StringIO(header + "".join(rows)), sep=sep, na_values=["."], low_memory=False
    )
    return frame[columns]


def compare_trial(
    dv: pd.DataFrame, ours: pd.DataFrame, ias: pd.DataFrame, words: pd.DataFrame
) -> dict:
    dv = dv.assign(
        start=dv["CURRENT_FIX_START"].astype("int64"),
        end=dv["CURRENT_FIX_END"].astype("int64"),
    )
    ours = ours.assign(
        start=ours["timestamp_ms"], end=ours["timestamp_ms"] + ours["duration_ms"] - 1
    )
    # By the last millisecond, then -- for a fixation Data Viewer cut at its
    # interest period's end -- by the first.
    by_end = dv.merge(ours, on="end", suffixes=("_dv", ""))
    by_start = dv[~dv["end"].isin(by_end["end"])].merge(
        ours[~ours["end"].isin(by_end["end"])], on="start", suffixes=("", "_dv")
    )
    by_start["start_dv"] = by_start["start"]
    by_end["end_dv"] = by_end["end"]
    paired = pd.concat([by_end, by_start], ignore_index=True)
    screen = paired["screen_id"].mode().iloc[0] if len(paired) else None
    on_screen = ours[ours["screen_id"] == screen]
    onset = (paired["start_dv"] - paired["start"]).abs()
    cut = onset + (paired["end_dv"] - paired["end"]).abs()
    dxy = pd.concat(
        [
            (paired["CURRENT_FIX_X"] - paired["x"]).abs(),
            (paired["CURRENT_FIX_Y"] - paired["y"]).abs(),
        ]
    )
    theirs = pd.DataFrame(
        {
            "word_id": ias["IA_ID"].astype("int64"),
            "text": ias["IA_LABEL"].astype(str),
            "x": ias["IA_LEFT"].astype("int64"),
            "y": ias["IA_TOP"].astype("int64"),
            "width": (ias["IA_RIGHT"] - ias["IA_LEFT"]).astype("int64"),
            "height": (ias["IA_BOTTOM"] - ias["IA_TOP"]).astype("int64"),
        }
    ).sort_values("word_id", ignore_index=True)
    mine = words[words["screen_id"] == screen][BOX_COLUMNS].astype(
        theirs.dtypes.to_dict()
    )
    mine = mine.sort_values("word_id", ignore_index=True)
    return {
        "screen": screen,
        "dv_fix": len(dv),
        "our_fix": len(on_screen),
        "paired": len(paired),
        "cut_by_dv": int((cut > 0).sum()),
        "other_screen": int((paired["screen_id"] != screen).sum()),
        "dv_only": len(dv) - len(paired),
        "ours_only": len(on_screen) - int((paired["screen_id"] == screen).sum()),
        "onset_max": onset.max(),
        "onset_med": onset.median(),
        "dxy_max": dxy.max(),
        "dxy_med": dxy.median(),
        "dv_boxes": len(theirs),
        "our_boxes": len(mine),
        "boxes_equal": mine.equals(theirs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("asc", type=Path, help="the session's .asc (or .edf)")
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument(
        "--fixations", type=Path, required=True, help="Data Viewer fixation report"
    )
    parser.add_argument(
        "--ia", type=Path, required=True, help="Data Viewer interest-area report"
    )
    parser.add_argument("--trial-var", default="Trial_Index_")
    parser.add_argument(
        "--study", type=Path, help="study folder (default: a temporary one)"
    )
    args = parser.parse_args()
    os.environ.setdefault("SCANPATH_EXPERIMENTAL", "1")
    from scanpath_studio import eyelink

    session = args.asc.stem
    study = args.study or Path(tempfile.mkdtemp(prefix="eyelink-check-"))
    report = eyelink.import_eyelink(
        args.asc, study, experiment_dir=args.experiment_dir, workers=1
    )
    if report.failed:
        raise SystemExit(f"import failed: {report.failed}")
    data = eyelink.load_eyelink(study, participants=[session])
    trial_of = dict(
        zip(
            data.trial_metadata[args.trial_var].astype(int),
            data.trial_metadata["trial_id"],
        )
    )
    fixations = read_report(
        args.fixations, session, [args.trial_var, *FIXATION_COLUMNS]
    )
    ias = read_report(args.ia, session, [args.trial_var, *IA_COLUMNS])

    rows = []
    for index, dv in fixations.groupby(args.trial_var):
        trial = trial_of.get(int(index))
        if trial is None:
            rows.append({args.trial_var: index, "screen": "no such trial"})
            continue
        row = compare_trial(
            dv,
            data.fixations[data.fixations["trial_id"] == trial],
            ias[ias[args.trial_var] == index],
            data.words[data.words["trial_id"] == trial],
        )
        rows.append({args.trial_var: index, "trial_id": trial, **row})
    table = pd.DataFrame(rows)
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(table.to_string(index=False))
    counts = ["dv_fix", "our_fix", "paired", "cut_by_dv", "other_screen"]
    total = table[[*counts, "dv_only", "ours_only"]].sum()
    print(
        f"\n{len(table)} trials; fixations: {total['dv_fix']} Data Viewer, "
        f"{total['our_fix']} imported on the matched screens, {total['paired']} "
        f"paired ({total['cut_by_dv']} cut by Data Viewer at its interest period, "
        f"{total['other_screen']} on another imported screen), {total['dv_only']} "
        f"only in Data Viewer, {total['ours_only']} only imported; onset difference "
        f"max {table['onset_max'].max()} ms; position difference max "
        f"{table['dxy_max'].max()} px; word boxes equal in "
        f"{int(table['boxes_equal'].sum())} of {len(table)} trials."
    )
    print(f"import notes: {report.notes.get(session, [])}")


if __name__ == "__main__":
    main()
