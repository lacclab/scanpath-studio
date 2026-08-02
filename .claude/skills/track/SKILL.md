---
name: track
description: Add or update an item in the improvements tracker (tracker/data.js) following the house conventions — stable IDs, four-paragraph write-up, approval gate. Use whenever work is started, finished (→ Pending approval), or signed off (→ Done + archived).
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
- **Statuses:** `Backlog | Planned | In progress | Blocked | Parked |
  Pending approval | Done | Dropped`. `archived: true` once signed off or
  closed.
- **Approval gate:** when implementation finishes, set
  `Status: Pending approval` — **never** jump straight to `Done`. Only on the
  user's explicit sign-off set `"status": "Done"` **and** `"archived": true`,
  and add the leading status quote line to the body, e.g.
  `> **Done — approved 2026-08-02.**` (use today's date). An item closed
  without implementation also gets `archived: true` plus the reason in `note`.
- **`body` is an array of markdown lines** (one array entry per source line).
  Link code as `[controls.py](scanpath_studio/controls.py:622)` and other
  items as `#ID`.

## Write-up shape

Four bold-led paragraphs, in this order (no `#` headings — the renderer has
none):

1. `**Request.**` — what was asked for, in the asker's terms.
2. `**What was done.**` — what actually shipped.
3. `**What's left.**` — what remains, or "Nothing" — say it either way; link
   the follow-up item if the remainder was split out.
4. `**Background (technical).**` — anchors, design calls, gotchas, related IDs.

A Backlog item has only *Request* + *Background*; *What was done* / *What's
left* appear once there is work behind it.

## Placement

Put the item in the matching group (`window.TRACKER.groups`); create a new
group only if genuinely nothing fits. Read a couple of neighboring items
first and match their tone and level of detail.
