# Unreleased changes

One file per changelog entry (ENG-86). A PR adds its file here and never edits
`CHANGELOG.md`, so parallel PRs don't conflict over it.

- **Name:** `<ID>.<group>.md`, e.g. `VIZ-47.fixed.md`. For an item with several
  IDs, join them with `+`: `AN-32+UX-176.changed.md`.
- **Group:** `added`, `changed`, `deprecated`, `removed`, `fixed` or `security`.
- **Content:** one line of plain text saying what changed for the user, with no
  bullet and no ID (the file name supplies both). Put the reasoning in the PR
  description or the issue instead.

`python scripts/changelog_fragments.py check` validates the files, `preview`
prints the section they make, and `/release` runs `release <version>`, which
writes them into `CHANGELOG.md` and deletes them.
