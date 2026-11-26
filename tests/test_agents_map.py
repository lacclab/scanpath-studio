"""AGENTS.md's module map names every module of the package, and only modules
that exist.

The map is how an agent (or a person) finds where a rule lives. A module
missing from it is one nobody is pointed at, and a name left behind after a
move points at nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import scanpath_studio

ROOT = Path(scanpath_studio.__file__).parent.parent


def _mapped() -> set[str]:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    start = text.index("```text\nscanpath_studio/")
    block = text[start : text.index("```", start + len("```text"))]
    return set(re.findall(r"\b([a-z_][a-z0-9_]*\.py)\b", block))


def test_every_module_is_on_the_map():
    modules = {path.name for path in (ROOT / "scanpath_studio").glob("*.py")}
    missing = sorted(modules - _mapped())
    assert not missing, (
        f"add these to AGENTS.md's module map, with what each holds: {missing}"
    )


def test_every_name_on_the_map_is_a_module():
    modules = {path.name for path in (ROOT / "scanpath_studio").glob("*.py")}
    stale = sorted(_mapped() - modules)
    assert not stale, f"AGENTS.md's module map names files that are gone: {stale}"


def _rule_paths(text: str) -> set[str]:
    header = text.split("---", 2)[1]
    return set(re.findall(r'"scanpath_studio/([^"]+)"', header))


def test_every_rule_loads_for_the_modules_it_names():
    """A rule in `.claude/rules/` loads only for the files its `paths:` header
    lists, so a module the rule names (`data.pick_column`, `plots.py`) must be
    among them, or editing that module never shows the rule."""
    modules = {path.stem for path in (ROOT / "scanpath_studio").glob("*.py")}
    gaps = {}
    for rule in sorted((ROOT / ".claude" / "rules").glob("*.md")):
        text = rule.read_text(encoding="utf-8")
        listed = _rule_paths(text)
        named = set(re.findall(r"`([a-z_]+)\.[A-Za-z_]", text)) & modules
        missing = sorted(
            m
            for m in named
            if f"{m}.py" not in listed
            and not any(p.endswith("*.py") and m.startswith(p[:-4]) for p in listed)
        )
        if missing:
            gaps[rule.name] = missing
    assert not gaps, f"add these modules to the rules' paths: headers: {gaps}"
