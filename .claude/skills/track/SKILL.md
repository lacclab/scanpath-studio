---
name: track
description: Add or update a work item in GitHub Issues and on the Scanpath Studio project board, following the house conventions — stable [PREFIX-N] IDs, the board's Status and Priority columns, native issue types, the four-section body, and the approval gate. Use whenever work is started, finished (→ Review), or signed off (→ closed).
---

# Tracking work

Work lives in **GitHub Issues** on `lacclab/scanpath-studio`, arranged on the
**[Scanpath Studio board](https://github.com/orgs/lacclab/projects/5)** (project
5) and driven with `gh`. The in-repo tracker (`tracker/`) was migrated on
2026-08-20 (ENG-32) and is a read-only archive of everything closed before then —
read it, never edit it.

**Prefer GitHub's structured fields to labels.** Status, priority and kind are
native fields, so they are deliberately *not* also labels — two vocabularies for
one fact is how they drift. Only `area:*` and `waiting-on-you` are labels, because
GitHub has no field for either.

Arguments: free-form — e.g. `CMP "chips reset on rerun"` (new issue),
`update VIZ-37`, `approve 117` (sign-off), `close 117 <reason>` (close without
implementing).

## Conventions (non-negotiable)

- **IDs are stable, never renumbered.** Every issue is titled
  `[PREFIX-N] <title>`. The IDs are cited across `AGENTS.md`, `CLAUDE.md`, the
  `plans/` notes and the git history, so they outlive GitHub's numbering — cite
  the tracker ID in prose and commits, with `#N` alongside when a link helps.
  Prefixes: `AN` (analysis), `BUG`, `CMP` (compare mode), `DATA`, `ENG`, `EXP`
  (export), `PERF`, `PRE` (preprocessing), `UX`, `VAL`, `VIZ`. A new item takes
  the next free number in its prefix — check **both** the issues and the
  archive, which holds every number used before the migration:

  ```bash
  gh issue list --state all --limit 200 --search "[DATA-" --json title
  grep -o '"id": "DATA-[0-9]*"' tracker/data.js | sort -uV | tail -3
  ```

- **Status** is the board's `Status` column: `Backlog · Planned · In progress ·
  On hold · Review`. Closing the issue is the sixth state. Moving it from the CLI
  needs the `project` token scope (`gh auth refresh -s project`, once):

  ```bash
  python3 tracker/to_github_issues.py --sync-board   # the archive's statuses, in bulk
  ```

  For a single move, drag the card in the web UI, or use `gh project item-edit`
  with the item, project, field and option ids from `gh project item-list 5
  --owner lacclab --format json` and `gh project field-list 5 --owner lacclab`.
- **Priority** is the board's `Priority` column: `Urgent · High · Medium · Low`,
  Medium being the default.
- **Kind** is the native issue type — `Bug`, `Feature` (a capability) or `Task`
  (a chore, a validation pass, infrastructure). `gh` has no flag for it:

  ```bash
  gh api -X PATCH repos/lacclab/scanpath-studio/issues/117 -f type=Task
  ```

- **`area:*` labels** mirror the old groups and decide the prefix: `area:ux`,
  `area:compare`, `area:viz`, `area:data`, `area:perf`, `area:analysis`,
  `area:preprocessing`, `area:export`, `area:validation`, `area:bug`,
  `area:engineering`.
- **Approval gate.** When implementation finishes, set Status **Review** and leave
  the issue **open** — never close it yourself. Closing is the user's sign-off.
  An item closed without being implemented gets the reason in a closing comment
  and `--reason "not planned"`.
- **Link code with full blob URLs** —
  `https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/controls.py#L622`.
  A repo-relative path renders as a dead link in an issue body.

## Body shape

Four markdown sections, in this order, optionally under a `>` blockquote lede
carrying the status / "update as of ⟨date⟩" line:

```markdown
> **In progress.** The visualization half shipped 2026-06-23.

### ⚖ Waiting on you

- [ ] Should the overlay share one scale, or keep each screen's own?

## Request

The 🗂️ Data page reads as one long divider-separated scroll — give it the same
hierarchy pass VIZ-31 (#88) gave the plot rail.

## What was done
…
## What's left
…
## Background
…
```

1. `## Request` — what was asked for, in the asker's terms. **Required.**
2. `## What was done` — what actually shipped.
3. `## What's left` — **the developer's** remaining work, and nothing else. You
   are the developer, so this is your own to-do, not a message to the user. When
   the code is finished it says "Nothing." — including on an issue you are moving
   to *Review*, because the review is not developer work.
4. `## Background` — anchors, design calls, gotchas, related IDs.

A backlog issue has only *Request* (+ *Background*). *What was done* / *What's
left* are **required** once it reaches *In progress* or *Review*.

## `⚖ Waiting on you` — everything that needs the user

Anything only the **user** can do goes in one checklist at the top of the body,
plus the `waiting-on-you` label — both the design calls that block the work
*and*, once it is built, the review to run. `gh issue list
--label waiting-on-you` is then one query for everything holding on them.

- **Omit the section** when nothing is open, and remove the label with it.
- **Ask, don't hedge.** A decision is a question with options, not "TBD".
- **One self-contained line per entry** — markdown inline renders; `[VIZ-37](…)`
  and `#117` link.
- **An issue in *Review* always has at least one entry** — the review ask
  itself. Name what to look at: the judgement calls you made, the surfaces to
  click, the things worth disagreeing with.
- **Clear it when settled**, in the same edit that acts on the answer, and record
  the call under *Background* so the reasoning survives. This holds even when you
  settled it yourself before implementing.
- An open call **does not** imply a status. *On hold* means the work is
  blocked; a question can be open on something nobody has started.

## Keep it current as you work

- **Claim it and move it to *In progress* when you pick it up**, before writing
  code, so a parallel session doesn't start the same work:
  `gh issue edit <n> --add-assignee @me`, plus the board move.
- **Commit early and often** — one commit per feature or fix, with the tracker ID
  in the subject: `fix(viz): keep the fullscreen control in sync (VIZ-37)`.
- **Land in *Review***, and put the ask to review in the *Waiting on you*
  checklist — *What's left* is your own remainder, not a message to the user.

## Recipes

```bash
# New issue. Read a couple of neighbours in the same area first and match their
# tone and level of detail.
gh issue create --title "[VIZ-38] <title>" --label area:viz --body-file body.md
gh api -X PATCH repos/lacclab/scanpath-studio/issues/<n> -f type=Feature
# then add it to the board and set Status — `--sync-board` does this in bulk

# Finish implementing → review (never close it yourself)
gh issue edit 117 --add-label waiting-on-you --body-file body.md
# then move the board card to Review

# Sign-off, on the user's explicit approval only
gh issue close 117 --comment "Approved 2026-08-20."

# Closed without implementing
gh issue close 117 --reason "not planned" --comment "<why>"
```

Write the body to a file and pass `--body-file`: it keeps the markdown readable
and avoids shell-quoting the emoji, backticks and headings.
