---
name: track
description: Add or update a work item in GitHub Issues and on the Scanpath Studio project board, following the house conventions — plain titles cited by their #N, the board's Status and Priority columns, native issue types, the four-section body, and the approval gate. Use whenever work is started, finished (→ Review), or signed off (→ closed).
---

# Tracking work

Work lives in **GitHub Issues** on `lacclab/scanpath-studio`, arranged on the
**[Scanpath Studio board](https://github.com/orgs/lacclab/projects/5)** (project
5) and driven with `gh`. The in-repo tracker (`tracker/`) was migrated on
2026-08-20 (ENG-32) and removed on 2026-09-30 (ENG-84); everything closed before
the migration is still at the `v0.31.2` tag (`git show v0.31.2:tracker/data.js`).

**Prefer GitHub's structured fields to labels.** Status, priority and kind are
native fields, so they are deliberately *not* also labels — two vocabularies for
one fact is how they drift. Only `area:*` and `waiting-on-you` are labels, because
GitHub has no field for either.

Arguments: free-form — e.g. `"chips reset on rerun" compare` (new issue),
`update 117`, `approve 117` (sign-off), `close 117 <reason>` (close without
implementing). An old ID (`update VIZ-37`) is found with
`gh issue list --state all --search VIZ-37`.

## Conventions (non-negotiable)

- **GitHub's `#N` is the ID** (since 2026-10-03). New issues get a plain
  title — no `[PREFIX-N]` — and commits, PRs, changelog fragments and prose cite
  `#N`. Nothing is allocated by hand, so parallel sessions cannot collide.
  The `[VIZ-37]`-style IDs of the old tracker are retired: **never mint one.**
  Those already written down stay — in the changelog, docs, `plans/`, code
  comments, git history and the titles of the issues that carry one — and
  `gh issue list --state all --search VIZ-37` still finds them. Leave old
  citations alone; write `#N` in new text.
- **Not every change gets an issue.** One finished inside a session is cited by
  its PR: its changelog fragment takes a slug name
  (`changelog.d/trial-picker-ids.changed.md`) and the release reads the PR
  number from the squash-merge subject. Open an issue when the item reaches
  *Review*, is blocked on the user, or is carried across sessions — and then
  name the fragment by it (`changelog.d/341.fixed.md`).

- **Status** is the board's `Status` column: `Backlog · Planned · In progress ·
  On hold · Review`. Closing the issue is the sixth state. Drag the card in the
  web UI, or move it from the CLI with `gh project item-edit` (needs the
  `project` token scope — `gh auth refresh -s project`, once):

  ```bash
  gh project view 5 --owner lacclab --format json --jq .id            # project id
  gh project field-list 5 --owner lacclab --format json               # Status / Priority field + option ids
  gh project item-list 5 --owner lacclab --format json --limit 500    # the issue's item id
  gh project item-edit --project-id <project-id> --id <item-id> \
      --field-id <status-field-id> --single-select-option-id <option-id>
  ```
- **Priority** is the board's `Priority` column: `Urgent · High · Medium · Low`,
  Medium being the default.
- **Kind** is the native issue type — `Bug`, `Feature` (a capability) or `Task`
  (a chore, a validation pass, infrastructure). `gh` has no flag for it:

  ```bash
  gh api -X PATCH repos/lacclab/scanpath-studio/issues/117 -f type=Task
  ```

- **`area:*` labels** mirror the old groups: `area:ux`,
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
hierarchy pass #88 gave the plot rail.

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
4. `## Background` — anchors, design calls, gotchas, related issues.

A backlog issue has only *Request* (+ *Background*). *What was done* / *What's
left* are **required** once it reaches *In progress* or *Review*.

## `⚖ Waiting on you` — everything that needs the user

Anything only the **user** can do goes in one checklist at the top of the body,
plus the `waiting-on-you` label — both the design calls that block the work
*and*, once it is built, the review to run. `gh issue list
--label waiting-on-you` is then one query for everything holding on them.

- **Omit the section** when nothing is open, and remove the label with it.
- **Ask, don't hedge.** A decision is a question with options, not "TBD".
- **One self-contained line per entry** — markdown inline renders; `#117`
  links.
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
- **Commit early and often** — one commit per feature or fix, with the issue
  in the subject: `fix(viz): keep the fullscreen control in sync (#117)`.
- **Land in *Review***, and put the ask to review in the *Waiting on you*
  checklist — *What's left* is your own remainder, not a message to the user.

## Recipes

```bash
# New issue. Read a couple of neighbours in the same area first and match their
# tone and level of detail.
gh issue create --title "<title>" --label area:viz --body-file body.md
gh api -X PATCH repos/lacclab/scanpath-studio/issues/<n> -f type=Feature
gh project item-add 5 --owner lacclab --url <issue-url> --format json --jq .id
# then set its Status (and Priority) with `gh project item-edit` — see Conventions

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
