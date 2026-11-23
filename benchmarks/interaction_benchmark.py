"""Time three ordinary actions in one Scanpath Studio session on the bundled demo.

Run in a fresh process: python benchmarks/interaction_benchmark.py --json interactions.json
The elapsed time covers Streamlit's Python rerun. A browser's layout and paint
are outside this measurement. The stage counts record real work inside the app.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from contextlib import ExitStack
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def profile_interactions() -> list[dict]:
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

    def counted(name, original):
        @wraps(original)
        def wrapped(*args, **kwargs):
            counts[name] += 1
            return original(*args, **kwargs)

        return wrapped

    with ExitStack() as hooks:
        for name, (module, attr) in stages.items():
            hooks.enter_context(
                patch.object(module, attr, counted(name, getattr(module, attr)))
            )
        study = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "streamlit_app.py"),
            default_timeout=120,
        )
        study.query_params["ui"] = "full"
        results = []
        for interaction in ("open_first_trial", "switch_trial", "change_marker_color"):
            counts.clear()
            start = time.perf_counter()
            if interaction == "switch_trial":
                study.button(key="single_next_trial").click()
            elif interaction == "change_marker_color":
                study.selectbox(key="global_color_by").set_value("line")
            study.run()
            elapsed = time.perf_counter() - start
            if study.exception or study.error:
                raise RuntimeError(
                    f"{interaction}: {[e.value for e in [*study.exception, *study.error]]}"
                )
            participant, trial = split_reading_key(
                study.session_state["single_trial_id"]
            )
            results.append(
                {
                    "interaction": interaction,
                    "elapsed_s": round(elapsed, 4),
                    "reading": {"participant": participant, "trial": trial},
                    "color_by": study.session_state["global_color_by"],
                    "stages": {name: counts[name] for name in stages},
                }
            )
    if (
        results[0]["reading"] == results[1]["reading"]
        or results[1]["reading"] != results[2]["reading"]
    ):
        raise RuntimeError("The trial switch did not select and keep a second reading.")
    if (
        results[1]["color_by"] == results[2]["color_by"]
        or results[2]["color_by"] != "line"
    ):
        raise RuntimeError("The marker color control did not change.")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Write the results to this file.")
    args = parser.parse_args()
    with TemporaryDirectory() as state:
        os.environ["SCANPATH_STUDIO_PERSIST"] = "0"
        os.environ["SCANPATH_STUDIO_STATE_DIR"] = state
        results = profile_interactions()
    payload = json.dumps({"dataset": "bundled demo", "interactions": results}, indent=2)
    if args.json:
        args.json.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
