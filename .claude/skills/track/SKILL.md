---
name: track
description: Add or update an item in the improvements tracker (tracker/data.js) following the house conventions — stable IDs, structured write-up fields, approval gate. Use whenever work is started, finished (→ Review), or signed off (→ Closed + archived).
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
  Closed`, moved along the path the UI's transition buttons offer — Backlog →
  *Plan it* / *Put on hold*; Planned → *Start work*; In progress → *Ready for
  review*; Review → *Approve & close* / *Send back*; On hold → *Resume*; Closed →
  *Reopen*. `archived: true` once signed off or closed. The retired wording
  (`Pending approval`, `Done`, `Parked`, `Dropped`) still appears on older
  items — never write it into a new or edited item, and don't mass-rewrite the
  historical ones.
- **Approval gate:** when implementation finishes, set `Status: Review` —
  **never** jump straight to `Closed`. Only on the user's explicit sign-off set
  `"status": "Closed"` **and** `"archived": true`, and add the sign-off line as
  the item's `statusNote`, e.g. `["**Closed — approved 2026-08-02.**"]` (use
  today's date). An item closed without implementation also gets
  `archived: true` plus the reason in `note`.
- **Every write-up field is an array of markdown lines** (one array entry per
  source line). Link code as
  `[controls.py](scanpath_studio/controls.py:622)` and other items as `#ID`.

## Write-up shape

The four sections are **structured fields on the item**, not bold leads inside
one blob — agents kept dropping, reordering, or rewording the prose version, so
the shape is now enforced by `tests/test_tracker_server.py`:

```js
"statusNote": ["**In progress.** The visualization half shipped 2026-06-23."],
"request": [
 "The 🗂️ Data page reads as one long divider-separated scroll — give it",
 "the same hierarchy pass #UX-51 gave the plot rail."
],
"whatWasDone": ["..."],
"whatsLeft": ["..."],
"background": ["..."],
```

1. `request` — what was asked for, in the asker's terms. **Required.**
2. `whatWasDone` — what actually shipped.
3. `whatsLeft` — **the developer's** remaining work, and nothing else; link the
   follow-up item if the remainder was split out. Think team lead / developer:
   you are the developer, so this field is your own to-do, not a message to the
   user. When the code is finished it says "Nothing." — including on an item you
   are moving to `Review`, because the review is not developer work. The ask to
   review goes in `decisions`.
4. `background` — anchors, design calls, gotchas, related IDs.

`statusNote` is the optional lede rendered above all four — the status or
"update as of ⟨date⟩" line that used to be a leading `>` quote.

Rules: **never repeat the section label inside its field** (`"request": ["**Request.** …"]`
double-prints it — the tracker draws the heading). **Omit a field** rather than
writing an empty array. A Backlog item has only `request` (+ `background`);
`whatWasDone` / `whatsLeft` appear once there is work behind it and are
**required** once the item is `In progress` or `Review`. Archived items still
carry the legacy single `body` array — leave them alone; both shapes render.

## Keep the tracker current as you work

Not a bookkeeping step at the end — the tracker is what the user and any other
session read to know the state of the project:

- **Claim it and flip to `In progress` when you pick the item up**, before
  writing code, so a parallel session doesn't start the same work. Claiming sets
  `owner` (a name from `TRACKER.people` in `data.js`) — in the UI that is the
  **Claim** button; editing `state.json` by hand, it is `"owner": "<name>"`.
- **Clear a `decisions` entry the moment it is answered** — including when you
  answered it yourself by making the call, before implementing — and record the
  call in `background` in the same edit.
- **Commit early and often.** One commit per feature or fix rather than one per
  session, tracker edit in the same commit as the code it describes.
- **Land in `Review`**, and put the ask to review in `decisions`, not
  `whatsLeft`.

## `decisions` — everything that is waiting on the user

Anything only the **user** can do goes in a `decisions` field on the item, a
sibling of `request` — both the design calls that block the work *and*, once it
is built, the review to run:

```js
"decisions": [
 "Rewrite the already-released sections too, or start at `[Unreleased]`?",
 "Is *Details* one flat list per release, or repeated per group?"
],
```

One self-contained line each (markdown inline is rendered; `#ID` refs link). The
tracker shows them as the amber **Waiting on you** box pinned above the write-up,
badges the collapsed card **⚖ N for you**, and collects them under the *Waiting
on me* filter — which is the point: one click shows every item holding on the
user. Rules:

- **Omit the field** when nothing is open. Never write an empty array.
- **Ask, don't hedge.** A decision is a question with options, not "TBD".
- **A `Review` item always has at least one entry** — the review ask itself.
  Name what to look at: the judgement calls you made, the surfaces to click, the
  things worth disagreeing with. A test enforces this.
- **Clear it when settled**, in the same edit that acts on the answer, and
  record the call you made in `background` so the reasoning survives. This holds
  even when you settle it yourself before implementing.
- An open decision **does not** imply a status. `On hold` means the work is
  blocked; a decision can be open on an item nobody has started.

## Placement

Put the item in the matching group (`window.TRACKER.groups`); create a new
group only if genuinely nothing fits. Read a couple of neighboring items
first and match their tone and level of detail.
