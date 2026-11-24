"""Time ordinary actions in one Scanpath Studio session, and what they cost.

Run in a fresh process:

    python benchmarks/interaction_benchmark.py --json interactions.json
    python benchmarks/interaction_benchmark.py --scale 300 --gaze-scale 10

The default run uses the bundled demo. ``--scale`` copies the demo's words and
fixations that many times, and ``--gaze-scale`` its raw gaze, renaming each
copy's participants and trials, and opens the result as an added dataset: the
per-reading and per-row costs that the two-reader demo hides show there.

Each interaction records the elapsed time of Streamlit's Python rerun (a
browser's layout and paint are outside it), the stage counts (real work inside
the app), and the frames hashed in full to key a cache
(``data._compute_frame_fingerprint``) — a large frame there on every rerun is a
frame the app should have named instead. ``new_sessions`` records the resident
memory each further session adds to the process, which a shared server such as
the hosted demo pays for every visitor.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import time
import traceback
from collections import Counter
from contextlib import ExitStack
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import psutil

INTERACTIONS = (
    "open_first_trial",
    "switch_trial",
    "change_marker_color",
    "filter_participants",
)
SCALED_DATASET = "Scaled demo"
#: A frame at least this long that is hashed gets its call site recorded.
HASH_SITE_MIN_ROWS = 1000


def scaled_corpus(copies: int, gaze_copies: int) -> dict[str, pd.DataFrame]:
    """The bundled demo copied ``copies`` times (raw gaze ``gaze_copies``),
    each copy under its own participant and trial ids, normalized."""
    from scanpath_studio import api, data

    words, fixations = data.read_sample_tables()
    samples = data.read_sample_raw_gaze()

    def copied(frame: pd.DataFrame, count: int) -> pd.DataFrame:
        parts = []
        for index in range(count):
            part = frame.drop(columns=["image_path"], errors="ignore").copy()
            for column in ("participant_id", "unique_trial_id"):
                part[column] = part[column].astype(str) + f"_{index}"
            parts.append(part)
        return pd.concat(parts, ignore_index=True)

    words, fixations = api.load_scanpath_data(
        copied(words, copies), copied(fixations, copies), names="canonical"
    )
    gaze = (
        api.load_raw_gaze(copied(samples, gaze_copies), names="canonical")
        if gaze_copies
        else pd.DataFrame()
    )
    return {"words": words, "fixations": fixations, "raw_gaze": gaze}


def _rss_mb() -> float:
    gc.collect()
    return psutil.Process().memory_info().rss / 1e6


def profile_interactions(
    dataset: dict[str, pd.DataFrame] | None = None, *, sessions: int = 2
) -> dict:
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import app, data, tabs
    from scanpath_studio.utils import split_reading_key

    stages = {
        "read_demo": (data, "read_sample_tables"),
        "normalize": (app, "_normalize_pair_uncached"),
        "select_trial_rows": (tabs, "extract_trial"),
        "build_figure": (tabs, "make_scanpath_figure"),
    }
    counts: Counter = Counter()
    hashed: list[tuple[int, float, str]] = []

    def counted(name, original):
        @wraps(original)
        def wrapped(*args, **kwargs):
            counts[name] += 1
            return original(*args, **kwargs)

        return wrapped

    full_hash = data._compute_frame_fingerprint

    @wraps(full_hash)
    def timed_hash(frame, *args, **kwargs):
        start = time.perf_counter()
        value = full_hash(frame, *args, **kwargs)
        elapsed = time.perf_counter() - start
        site = ""
        if len(frame) >= HASH_SITE_MIN_ROWS:
            site = " <- ".join(
                f"{Path(f.filename).name}:{f.lineno}:{f.name}"
                for f in reversed(traceback.extract_stack(limit=8)[:-1])
                if "scanpath_studio" in f.filename and "data.py" not in f.filename
            )
        hashed.append((len(frame), elapsed, site))
        return value

    if dataset is None:
        readers = data.read_sample_tables()[1]["participant_id"]
    else:
        readers = dataset["fixations"]["participant_id"]
    readers = sorted(readers.dropna().astype(str).unique())

    def open_session():
        study = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "streamlit_app.py"),
            default_timeout=900,
        )
        study.query_params["ui"] = "full"
        if dataset is not None:
            study.query_params["dataset"] = SCALED_DATASET
            study.session_state["_datasets"] = {SCALED_DATASET: dict(dataset)}
            study.session_state["tour_seen"] = True
        return study

    def run(study, label: str) -> float:
        start = time.perf_counter()
        study.run()
        elapsed = time.perf_counter() - start
        if study.exception or study.error:
            raise RuntimeError(
                f"{label}: {[e.value for e in [*study.exception, *study.error]]}"
            )
        return elapsed

    with ExitStack() as hooks:
        for name, (module, attr) in stages.items():
            hooks.enter_context(
                patch.object(module, attr, counted(name, getattr(module, attr)))
            )
        hooks.enter_context(
            patch.object(data, "_compute_frame_fingerprint", timed_hash)
        )
        study = open_session()
        results = []
        kept_readers: list[str] = []
        for interaction in INTERACTIONS:
            counts.clear()
            hashed.clear()
            if interaction == "switch_trial":
                study.button(key="single_next_trial").click()
            elif interaction == "change_marker_color":
                study.selectbox(key="global_color_by").set_value("line")
            elif interaction == "filter_participants":
                # The current reader and a sixth of the others: the reading
                # stays, the pool every picker and filter reads shrinks.
                current, _ = split_reading_key(study.session_state["single_trial_id"])
                others = [r for r in readers if r != current]
                kept_readers = [current, *others[: len(readers) // 6]]
                study.multiselect(key="filter_participants").set_value(kept_readers)
            elapsed = run(study, interaction)
            if interaction == "filter_participants" and sorted(
                study.session_state["_trial_filters"]["participants"]
            ) != sorted(kept_readers):
                raise RuntimeError("The participant filter was not applied.")
            participant, trial = split_reading_key(
                study.session_state["single_trial_id"]
            )
            sites = Counter()
            for rows, _, site in hashed:
                if site:
                    sites[f"{rows} rows: {site}"] += 1
            results.append(
                {
                    "interaction": interaction,
                    "elapsed_s": round(elapsed, 4),
                    "reading": {"participant": participant, "trial": trial},
                    "color_by": study.session_state["global_color_by"],
                    "stages": {name: counts[name] for name in stages},
                    "hashed": {
                        "frames": len(hashed),
                        "rows": sum(rows for rows, _, _ in hashed),
                        "largest_rows": max((rows for rows, _, _ in hashed), default=0),
                        "ms": round(sum(t for _, t, _ in hashed) * 1000, 2),
                        "sites": dict(sites.most_common(5)),
                    },
                }
            )
        # Each further session holds what the server keeps per visitor; the
        # earlier ones stay open, as they would on a shared server.
        new_sessions = []
        held = [study]
        for index in range(sessions):
            before = _rss_mb()
            other = open_session()
            elapsed = run(other, f"new session {index + 1}")
            held.append(other)
            new_sessions.append(
                {
                    "first_run_s": round(elapsed, 4),
                    "rss_growth_mb": round(_rss_mb() - before, 1),
                }
            )
    if (
        results[0]["reading"] == results[1]["reading"]
        or results[1]["reading"] != results[2]["reading"]
        or results[2]["reading"] != results[3]["reading"]
    ):
        raise RuntimeError("The trial switch did not select and keep a second reading.")
    if (
        results[1]["color_by"] == results[2]["color_by"]
        or results[2]["color_by"] != "line"
    ):
        raise RuntimeError("The marker color control did not change.")
    return {"interactions": results, "new_sessions": new_sessions}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", type=Path, help="Write the results to this file.")
    parser.add_argument(
        "--scale",
        type=int,
        default=0,
        help="Open the demo's words and fixations copied this many times.",
    )
    parser.add_argument(
        "--gaze-scale",
        type=int,
        default=None,
        help="Copies of the demo's raw gaze with --scale (default: --scale).",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=2,
        help="Further sessions to open after the interactions, for memory.",
    )
    args = parser.parse_args()
    with TemporaryDirectory() as state:
        os.environ["SCANPATH_STUDIO_PERSIST"] = "0"
        os.environ["SCANPATH_STUDIO_STATE_DIR"] = state
        dataset = None
        label = "bundled demo"
        if args.scale:
            gaze_copies = args.scale if args.gaze_scale is None else args.gaze_scale
            dataset = scaled_corpus(args.scale, gaze_copies)
            label = f"bundled demo x{args.scale} (raw gaze x{gaze_copies})"
        results = profile_interactions(dataset, sessions=args.sessions)
    payload = {"dataset": label}
    if dataset is not None:
        payload["rows"] = {table: len(frame) for table, frame in dataset.items()}
    payload.update(results)
    text = json.dumps(payload, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
