---
name: Bug report
about: Something in Scanpath Studio behaves wrongly
title: "[BUG-N] "
type: Bug
labels: ["area:bug"]
---

<!--
Maintainers: replace N in the title with the next free BUG number. Most IDs
live in only one place, so check all three (CLAUDE.md → Tracking work):
CHANGELOG.md plus the file names in changelog.d/, `gh issue list --state all
--search "[BUG-"`, and the open PRs' fragments (`gh pr list --state open`, then
the changelog.d/ files in each `gh pr diff <n> --name-only`).
IDs are stable and never renumbered.
Outside reporters: leave the title as-is; we will number it.
Maintainers: add it to the "Scanpath Studio" project board and set its Status.
-->

## Request

What you did, what you expected, and what happened instead. If it involves a
dataset, say which one (a bundled demo, a public corpus, or your own upload) and
which surface — 🗂️ Data, the Scanpath view, Corpus Analysis, the CLI, the API.

## Background

Version (`scanpath-studio --version` or the About dialog), OS, and how you are
running it (pip, desktop bundle, Streamlit Cloud). Paste any traceback in full,
and a share link if the trial can be linked to.
