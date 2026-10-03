# Unreleased changes

One file per changelog entry (ENG-86). A PR adds its file here and never edits
`CHANGELOG.md`, so parallel PRs don't conflict over it.

- **Name:** `<issue>.<group>.md` when the change has an issue, e.g.
  `341.fixed.md` (several issues join with `+`: `340+341.changed.md`).
  Otherwise a short slug: `trial-picker-ids.changed.md`. A slug needs no
  number: the release cites the PR that merged it, read from the squash-merge
  subject (`… (#327)`).
- **Group:** `added`, `changed`, `deprecated`, `removed`, `fixed` or `security`.
- **Content:** one line of plain text saying what changed for the user, with no
  bullet and no number (the file name supplies both). Put the reasoning in the
  PR description or the issue instead.

Fragments from before the `[PREFIX-N]` IDs were dropped (`UX-190.changed.md`)
are slugs like any other and resolve to their PR the same way.

`python scripts/changelog_fragments.py check` validates the files, `preview`
prints the section they make, and `/release` runs `release <version>`, which
writes them into `CHANGELOG.md` and deletes them.
