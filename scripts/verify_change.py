"""Exercise a change on every surface the app has, in about a minute.

The smoke harness behind the ``/verify`` skill: it boots the app headless,
renders through the CLI and through the Python API, and reports one line per
check, so a change is seen *working*, not only compiling. A feature option is
checked on all four surfaces by passing its spelling on each:

    uv run --extra test python scripts/verify_change.py \\
        --query fixation_index_position=below \\
        --render-args "--order-label-position below" \\
        --api-kwargs '{"order_label_position": "below"}'

Without options it checks the defaults: the three views draw without an
exception, ``render --sample`` writes a figure, and ``plot_scanpath`` builds
one. Exit status is non-zero when any check fails. Nothing is written to the
recovery cache or the user's state directory.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "streamlit_app.py")


def _isolate_state(state_dir: Path) -> None:
    """Keep every check off the user's recovery cache and saved settings."""
    os.environ["SCANPATH_STUDIO_PERSIST"] = "0"
    os.environ["SCANPATH_STUDIO_STATE_DIR"] = str(state_dir)


def _check_app(query: dict[str, str], ui: str) -> list[tuple[str, bool, str]]:
    from streamlit.testing.v1 import AppTest

    from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_DATA, _VIEW_SCANPATH

    results = []
    for view in (_VIEW_SCANPATH, _VIEW_CORPUS, _VIEW_DATA):
        at = AppTest.from_file(APP, default_timeout=180)
        at.query_params["ui"] = ui
        for key, value in query.items():
            at.query_params[key] = value
        if view != _VIEW_SCANPATH:
            at.session_state["main_nav"] = view
        start = time.perf_counter()
        at.run()
        took = time.perf_counter() - start
        errors = [e.value for e in at.exception]
        # A link value the app refused is reported as a warning naming it.
        refused = [w.value for w in at.warning if "Ignored the link" in str(w.value)]
        ok = not errors and not refused
        detail = f"{took:.1f}s"
        if errors:
            detail += f" — exception: {str(errors[0])[:300]}"
        if refused:
            detail += f" — {refused[0][:200]}"
        results.append((f"app: {view}", ok, detail))
    return results


def _check_cli(render_args: str, out_dir: Path) -> tuple[str, bool, str]:
    out = out_dir / "cli.html"
    cmd = [
        sys.executable,
        "-m",
        "scanpath_studio.cli",
        "render",
        "--sample",
        "-o",
        str(out),
        *shlex.split(render_args),
    ]
    start = time.perf_counter()
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=ROOT)
    took = time.perf_counter() - start
    ok = proc.returncode == 0 and out.exists() and out.stat().st_size > 0
    detail = f"{took:.1f}s → {out}"
    if not ok:
        detail += f" — exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}"
    return ("cli: render --sample " + render_args).strip(), ok, detail


def _check_api(api_kwargs: dict, out_dir: Path) -> tuple[str, bool, str]:
    import scanpath_studio as sps

    start = time.perf_counter()
    try:
        words, fixations = sps.load_sample_data()
        first = sps.list_trials(words, fixations).iloc[0]
        kwargs = {
            "participant": first["participant_id"],
            "trial": first.get("unique_trial_id", first.get("trial_id")),
            **api_kwargs,
        }
        fig = sps.plot_scanpath(words, fixations, **kwargs)
        out = out_dir / "api.html"
        sps.save_figure(fig, out)
    except Exception as exc:  # the report is the point; never hide the cause
        return ("api: plot_scanpath", False, f"{type(exc).__name__}: {exc}")
    took = time.perf_counter() - start
    return (
        f"api: plot_scanpath(**{api_kwargs})" if api_kwargs else "api: plot_scanpath",
        True,
        f"{took:.1f}s, {len(fig.data)} traces → {out}",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        metavar="PARAM=VALUE",
        help="A deep-link parameter to open the app with (repeatable).",
    )
    parser.add_argument(
        "--ui",
        choices=("full", "essentials"),
        default="full",
        help="The interface mode to boot (default: full).",
    )
    parser.add_argument(
        "--render-args", default="", help="Extra `render` flags, one string."
    )
    parser.add_argument(
        "--api-kwargs", default="{}", help="Extra `plot_scanpath` keywords, JSON."
    )
    parser.add_argument("--skip-app", action="store_true")
    parser.add_argument("--skip-cli", action="store_true")
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument(
        "--out-dir", type=Path, help="Where to write the figures (default: a temp dir)."
    )
    args = parser.parse_args(argv)

    query = dict(item.split("=", 1) for item in args.query)
    out_dir = args.out_dir or Path(tempfile.mkdtemp(prefix="sps-verify-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    _isolate_state(out_dir / "state")

    results: list[tuple[str, bool, str]] = []
    if not args.skip_app:
        results += _check_app(query, args.ui)
    if not args.skip_cli:
        results.append(_check_cli(args.render_args, out_dir))
    if not args.skip_api:
        results.append(_check_api(json.loads(args.api_kwargs), out_dir))

    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    failed = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
