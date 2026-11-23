"""Capture this release's share links, settings files and cache as golden
fixtures (`tests/fixtures/golden/v<release>/`), and the figure digests
(`tests/fixtures/golden/figures.json`).

Run it once per release, on the released code, from the repository root:

    uv run --extra test python scripts/capture_golden.py

`tests/test_wire_golden.py` then checks that every release's captures keep
restoring to the same state. A release's folder is never rewritten to make that
test pass: it is what users of that release hold. Only a deliberate,
changelogged break deletes the keys it breaks from a capture (say so in the
`changed`/`removed` fragment). The figure digests are the current drawing, not
something users hold, so a change meant to alter a figure re-captures them:

    uv run --extra test python scripts/capture_golden.py --figures
"""

from __future__ import annotations

import os

# The default build, with nothing read from or written to the user's cache.
os.environ.pop("SCANPATH_EXPERIMENTAL", None)
os.environ["SCANPATH_STUDIO_PERSIST"] = "0"

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scanpath_studio import __release__  # noqa: E402
from tests import wire_golden as g  # noqa: E402


def _stable(first: dict, second: dict) -> dict:
    """The keys two captures agree on; anything volatile is left out."""
    return {k: v for k, v in first.items() if k in second and second[k] == v}


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def capture_links(out: Path) -> dict[str, str]:
    queries = {"maximal": g.write_link(g.maximal_link_state())}
    for name, state in g.palette_link_states().items():
        queries[f"palette: {name}"] = g.write_link(state)
    links = {
        name: {"query": q, "state": _stable(g.read_link(q), g.read_link(q))}
        for name, q in queries.items()
    }
    # One link through the whole app: the dataset and reading it opens on.
    maximal = queries["maximal"]
    links["maximal"]["app_state"] = _stable(
        g.open_link_in_app(maximal), g.open_link_in_app(maximal)
    )
    _write(out / "links.json", links)
    return queries


def capture_settings(out: Path, queries: dict[str, str]) -> None:
    expected = {}
    for name in ("maximal", "palette: Print / grayscale"):
        config = g.write_settings_file(queries[name])
        slug = name.replace(": ", "-").replace(" / ", "-").replace(" ", "-").lower()
        _write(out / "settings" / f"{slug}.json", config)
        expected[slug] = _stable(
            g.read_settings_file(config), g.read_settings_file(config)
        )
    _write(out / "settings_restored.json", expected)


def capture_cache(out: Path) -> None:
    from scanpath_studio.persistence import save_state

    target = out / "cache"
    assert save_state(g.cache_session(), target), "the cache saved nothing"
    (target / ".scanpath-recovery.lock").unlink(missing_ok=True)
    print(f"wrote {target.relative_to(ROOT)}/")
    reads = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "cache"
            shutil.copytree(target, copy)
            reads.append(g.read_cache(copy))
    assert reads[0]["annotations"], "the cache restored no annotations"
    _write(
        out / "cache_restored.json",
        {**reads[0], "state": _stable(reads[0]["state"], reads[1]["state"])},
    )


def capture_figures() -> None:
    figures = {}
    for name, (kind, options) in g.FIGURE_CASES.items():
        fig = g.build_figure(kind, options)
        assert fig.data, f"{name} draws nothing"
        digest = g.figure_digest(fig)
        assert digest == g.figure_digest(g.build_figure(kind, options)), (
            f"{name} is not deterministic"
        )
        figures[name] = {"kind": kind, "options": options, "digest": digest}
    _write(g.GOLDEN / "figures.json", figures)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--figures", action="store_true", help="re-capture only the figure digests"
    )
    args = parser.parse_args()
    if args.figures:
        capture_figures()
        return
    out = g.GOLDEN / f"v{__release__}"
    if out.exists():
        sys.exit(f"{out} exists; a release's captures are never rewritten")
    queries = capture_links(out)
    capture_settings(out, queries)
    capture_cache(out)
    capture_figures()


if __name__ == "__main__":
    main()
