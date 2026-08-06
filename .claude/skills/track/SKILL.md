---
name: track
description: Add or update an item in the improvements tracker (tracker/data.js) following the house conventions — stable IDs, four-paragraph write-up, approval gate. Use whenever work is started, finished (→ Review), or signed off (→ Closed + archived).
---

# Tracker item workflow

All work — open and archived — lives in `tracker/data.js` (view via
`tracker/index.html`). This skill edits that file correctly.

Arguments: free-form — e.g. `CMP "chips reset on rerun"` (new item),
`update ENG-15`, `approve CMP-3` (sign-off), `close VIZ-2 <reason>`
(close without implementing).

## Conventions (non-negotiable)

- **IDs are stable, never renumbered.** A new item takes the *next free
  number* in its prefix. Existing prefixes: `AN` (analysis), `BUG`, `CMP`
  (compare mode), `DATA`, `ENG`, `EXP` (export), `PERF`, `PRE`
  (preprocessing), `UX`, `VAL`, `VIZ`. Scan `data.js` for the highest used
  number in the prefix — including archived items — before assigning.
- **Statuses (six):** `Backlog | Planned | In progress | On hold | Review |
  Closed`. `archived: true` once signed off or closed. The retired wording
  (`Pending approval`, `Done`, `Parked`, `Dropped`) still appears on older
  items — never write it into a new or edited item, and don't mass-rewrite the
  historical ones.
- **Approval gate:** when implementation finishes, set `Status: Review` —
  **never** jump straight to `Closed`. Only on the user's explicit sign-off set
  `"status": "Closed"` **and** `"archived": true`, and add the leading status
  quote line to the body, e.g. `> **Closed — approved 2026-08-02.**` (use
  today's date). An item closed without implementation also gets
  `archived: true` plus the reason in `note`.
- **`body` is an array of markdown lines** (one array entry per source line).
  Link code as `[controls.py](scanpath_studio/controls.py:622)` and other
  items as `#ID`.

## Write-up shape

Four bold-led paragraphs, in this order (no `#` headings — the renderer has
none):

1. `**Request.**` — what was asked for, in the asker's terms.
2. `**What was done.**` — what actually shipped.
3. `**What's left.**` — what remains; link the follow-up item if the remainder
   was split out. An item you are moving to `Review` is **never** "Nothing" —
   what's left is the user's review, so name what to look at (the judgement
   calls you made, the surface to click). "Nothing" is only for an item that is
   finished *and* signed off.
4. `**Background (technical).**` — anchors, design calls, gotchas, related IDs.

A Backlog item has only *Request* + *Background*; *What was done* / *What's
left* appear once there is work behind it.

## Decisions to settle

Questions that need the **user's** call before the work can start do **not** go
in *Background* — they go in a structured `decisions` field on the item, a
sibling of `body`:

```js
"decisions": [
 "Rewrite the already-released sections too, or start at `[Unreleased]`?",
 "Is *Details* one flat list per release, or repeated per group?"
],
```

One self-contained line per decision (markdown inline is rendered; `#ID` refs
link). The tracker shows them as an amber callout pinned above the write-up,
badges the collapsed card **⚖ N to settle**, and collects them under the
*Waiting on my decision* filter — which is the point: the user should be able to
see every call waiting on them in one click. Rules:

- **Omit the field** when nothing is open. Never write an empty array.
- **Ask, don't hedge.** A decision is a question with options, not "TBD".
- **Clear it when settled**, in the same edit that acts on the answer, and
  record the call you made in *Background* so the reasoning survives.
- An open decision **does not** imply a status. `On hold` means the work is
  blocked; a decision can be open on an item nobody has started.
- Items created in the tracker UI have no `decisions` — the server's
  `_validate_created_item` takes an exact key set. Add it by editing `data.js`.

## Placement

Put the item in the matching group (`window.TRACKER.groups`); create a new
group only if genuinely nothing fits. Read a couple of neighboring items
first and match their tone and level of detail.
