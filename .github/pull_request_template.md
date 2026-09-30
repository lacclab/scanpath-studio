<!--
Keep it tight — a sentence or two of what changed and why is plenty.
See CONTRIBUTING.md for the full pre-PR checklist.
-->

## Summary

<!-- What does this change and why? Link any related issue (#123). -->

## Verification

<!-- How you confirmed it works — e.g. which tests cover it, ruff clean, manual app check.
     For UI/visual changes, drop in a before/after screenshot or GIF. -->

## Checklist

- [ ] `pytest` passes
- [ ] Added/updated tests for any new behavior
- [ ] `ruff check .` and `ruff format --check .` are clean
- [ ] Added a changelog fragment in [`changelog.d/`](https://github.com/lacclab/scanpath-studio/blob/main/changelog.d/README.md) (every feature/bugfix/notable change) — not an edit to `CHANGELOG.md`
- [ ] Dependency change? Declared in `pyproject.toml` (the only dependency manifest)
