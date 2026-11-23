"""Capture this release's share links, settings files, cache and figures as
golden fixtures (`tests/fixtures/golden/<release>/`).

Run it once per release, on the released code, from the repository root:

    SCANPATH_STUDIO_PERSIST=0 uv run --extra test python scripts/capture_golden.py

`tests/test_wire_golden.py` then checks that every release's captures keep
restoring to the same state. A capture is never rewritten to make that test
pass: an older release's folder is what users of that release hold. Only a
deliberate, changelogged break deletes the keys it breaks from the captured
state (say so in the `changed`/`removed` fragment). The figure digests are the
exception: they are this release's drawing, so a deliberate visual change
re-captures them (`--figures`).
"""

from __future__ import annotations

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
    shutil.rmtree(target, ignore_errors=True)
    assert save_state(g.cache_session(), target), "the cache saved nothing"
    print(f"wrote {target.relative_to(ROOT)}/")
    reads = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "cache"
            shutil.copytree(target, copy)
            reads.append(g.read_cache(copy))
    _write(
        out / "cache_restored.json",
        {
            "state": _stable(reads[0]["state"], reads[1]["state"]),
            "frames": reads[0]["frames"],
        },
    )


def capture_figures(out: Path) -> None:
    digests = {}
    for name, build in g.golden_figures().items():
        first, second = g.figure_digest(build()), g.figure_digest(build())
        assert first == second, f"{name} is not deterministic"
        digests[name] = first
    _write(out / "figures.json", digests)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--figures", action="store_true", help="re-capture only the figure digests"
    )
    args = parser.parse_args()
    out = g.GOLDEN / f"v{__release__}"
    if args.figures:
        capture_figures(out)
        return
    if out.exists():
        sys.exit(f"{out} exists; a release's captures are never rewritten")
    queries = capture_links(out)
    capture_settings(out, queries)
    capture_cache(out)
    capture_figures(out)


if __name__ == "__main__":
    main()
