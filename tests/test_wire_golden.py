"""Links, settings files and caches that users already hold keep restoring.

Each release's share links, Share → File settings files and recovery cache are
captured under `tests/fixtures/golden/v<release>/` by
`scripts/capture_golden.py`. Every capture must keep restoring to the state it
restored to when it was captured, so a refactor of the link reader, the
settings-file reader or the cache cannot quietly change what an old link opens.

Only the captured keys are compared: adding a setting never fails here. A
failure means a value users hold now restores differently. Fix the reader
(an alias, a migration), or, for a deliberate break, delete the affected keys
from the capture and name the break in a `changed`/`removed` changelog fragment.

`figures.json` pins how the public API draws a few figures on the bundled demo.
When a change is meant to alter a figure, re-capture it with
`scripts/capture_golden.py --figures`.
"""

from __future__ import annotations

import json
import shutil

import pytest

from tests import wire_golden as g

pytestmark = pytest.mark.usefixtures("experimental_off")


def _version(path) -> tuple[int, ...]:
    return tuple(int(part) for part in path.name.removeprefix("v").split("."))


RELEASES = sorted((p for p in g.GOLDEN.glob("v*") if p.is_dir()), key=_version)


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _cases(filename, *, need=None):
    return [
        pytest.param(release, name, case, id=f"{release.name}-{name}")
        for release in RELEASES
        if (release / filename).exists()
        for name, case in _load(release / filename).items()
        if need is None or need in case
    ]


def _report(what, problems):
    return (
        f"{what} restores differently ({len(problems)} key(s)):\n  "
        + "\n  ".join(problems[:20])
        + "\nUsers hold this. Fix the reader, or for a deliberate break remove the"
        " keys from the capture and say what breaks in the changelog fragment."
    )


def test_there_is_a_capture():
    assert RELEASES, f"no golden captures under {g.GOLDEN}"
    assert FIGURES, "figures.json pins no figure"


@pytest.mark.parametrize("release", RELEASES, ids=lambda r: r.name)
def test_each_release_capture_is_complete(release):
    """A capture file emptied or deleted would silently drop its cases."""
    for name in ("links.json", "settings_restored.json", "cache_restored.json"):
        assert _load(release / name), f"{release.name}/{name} is empty or missing"
    assert (release / "cache" / "manifest.json").is_file()


@pytest.mark.parametrize(("release", "name", "case"), _cases("links.json"))
def test_a_share_link_restores_as_captured(release, name, case):
    problems = g.differences(case["state"], g.read_link(case["query"]))
    assert not problems, _report(f"The {release.name} link '{name}'", problems)


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    ("release", "name", "case"), _cases("links.json", need="app_state")
)
def test_a_share_link_opens_the_captured_view(release, name, case):
    """The whole app, not just the settings: the dataset and reading too."""
    problems = g.differences(case["app_state"], g.open_link_in_app(case["query"]))
    assert not problems, _report(
        f"The {release.name} link '{name}' in the app", problems
    )


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    ("release", "name", "expected"), _cases("settings_restored.json")
)
def test_a_settings_file_restores_as_captured(release, name, expected):
    config = _load(release / "settings" / f"{name}.json")
    problems = g.differences(expected, g.read_settings_file(config))
    assert not problems, _report(f"The {release.name} settings file '{name}'", problems)


@pytest.mark.parametrize(
    "release", [r for r in RELEASES if (r / "cache").is_dir()], ids=lambda r: r.name
)
def test_a_recovery_cache_restores_as_captured(release, tmp_path):
    # A copy: restoring may take the lock or migrate files in place.
    root = tmp_path / "cache"
    shutil.copytree(release / "cache", root)
    expected = _load(release / "cache_restored.json")
    restored = g.read_cache(root)
    problems = g.differences(expected["state"], restored["state"])
    problems += g.differences(expected["datasets"], restored["datasets"])
    assert not problems, _report(f"The {release.name} recovery cache", problems)
    assert restored["annotations"] == expected["annotations"], (
        f"The {release.name} recovery cache restores different annotations"
    )
    assert restored["frames"] == expected["frames"], (
        f"The {release.name} recovery cache restores different data"
    )


FIGURES = _load(g.GOLDEN / "figures.json")


@pytest.mark.parametrize("name", sorted(FIGURES))
def test_the_api_draws_the_captured_figure(name):
    case = FIGURES[name]
    actual = g.figure_digest(g.build_figure(case["kind"], case["options"]))
    assert actual == case["digest"], (
        f"'{name}' is drawn differently from its capture. If the change is meant "
        "to alter the figure, re-capture with `scripts/capture_golden.py "
        "--figures`; otherwise it is a regression."
    )
