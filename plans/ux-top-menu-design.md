# Top menu instead of sidebar — design

**Date:** 2026-08-12
**Status:** Approved, ready for an implementation plan

## Goal

Replace Scanpath Studio's left sidebar with a horizontal menu bar at the top of
the page. After this change nothing renders into `st.sidebar`, so Streamlit draws
no sidebar chrome at all and the main content gets the full page width.

Out of scope: the Scanpath view's **right-hand plot rail** (presets/palette,
Fixations, Saccades, Stimulus, Overlays, Figure & canvas). It stays exactly where
it is — per-figure styling belongs next to the figure, and BUG-24 has just
settled its layout.

Also out of scope: the Corpus⇄Scanpath view switch. It is already a header
button (`main_nav`, set in `url_state._render_about_panel`), not a sidebar
control, and keeps its current position on the row below the menu.

## What is in the sidebar today

Rendered from `app.main()`, top to bottom:

| Group | Origin |
| --- | --- |
| ⚙️ Configure — description · source options · data location · column mapping | `app.py` ~L3138 (`dataset_options_slot`) |
| 🧹 Preprocessing | `app._preprocessing_settings` ~L2923 |
| 💾 Save & restore | `app.py` ~L3500 (`save_restore_slot`, key `tour_grp_save_restore`) |
| 🗄️ Recovery cache | `app.py` ~L3615 (`recovery_cache_slot`) |
| ❓ Help — replay tour · 🧭 Tutorials · FAQ · 📚 Documentation ↗ · ℹ️ About | `app.py` ~L3624, `tour.py`, `url_state._render_about_sidebar` |
| 🐛 Debug (only under `?debug=1`) | `debug_log.render_debug_panel` |
| Transient load messages | `app.py` L1876, L1898, L3409 |

## Mechanism: popovers, not dialogs

Each group becomes an `st.popover` in a single columns row.

**Dialogs were considered and rejected.** An `@st.dialog` body only executes
while the dialog is open, but the ⚙️ Configure widgets are not passive display —
the data-location text input, the ⬇ Download button and the column-mapping
selectboxes drive `prepare_data` on every rerun. Inside a dialog they would not
render on a closed run, and Streamlit drops widget state for widgets that do not
render (the codebase already works around this with `persist_state="session"`
and `controls._pin`). A popover is a plain `DeltaGenerator`: it executes every
run and can be filled after later elements have been written, which is precisely
the `st.sidebar` semantics being replaced.

Consequence: the migration is a **host swap**, not a restructure. Every
`host = slot if slot is not None else st.sidebar` fallback repoints at a menu
slot, and the existing reserve-a-slot-then-fill-it-downstream pattern carries
over unchanged.

## Structure

A `st.container(key="top_menu")` reserved at the very top of `main()`, directly
after the title and before any data loading, holding one `st.columns` row:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Scanpath Studio                                                      │
│ ⚙️ Configure ▾  🧹 Preprocessing ▾  💾 Save ▾  🗄️ Cache ▾  ❓ Help ▾ │
├──────────────────────────────────────────────────────────────────────┤
│ [ Corpus Analysis | Scanpath ]                                       │
│                                                                      │
│ ── main content, full width ──                                       │
└──────────────────────────────────────────────────────────────────────┘
```

The bar is **not sticky**. It scrolls with the page. Pinning it would require
CSS against Streamlit's internal DOM, and these are setup controls touched once
per session, not per scroll.

## Group-by-group

| Today | Becomes |
| --- | --- |
| ⚙️ Configure | Wide popover (~620px). Its *Column mapping* `st.expander` flattens into a bordered `st.container` — expanders do not nest cleanly inside popovers. The four sub-slots (description / options / data location / column mapping) stay as containers reserved inside the popover, so downstream loaders keep filling them by `host=`. |
| 🧹 Preprocessing | Popover, contents unchanged. |
| 💾 Save & restore | Popover. Keeps `key="tour_grp_save_restore"` so the spotlight tour still finds it. |
| 🗄️ Recovery cache | Popover. Still filled *after* `save_local_state`, as today. |
| ❓ Help | Popover. The nested 🧭 Tutorials popover (`tour.py` L1139) flattens to buttons — popovers do not nest. |
| 🐛 Debug | Popover appended to the row, only under `?debug=1`. |
| Transient load messages (`st.sidebar.warning` on unusable raw-gaze schema, `st.sidebar.caption` on non-overlapping raw gaze) | **Main area.** This is the one behaviour change rather than a relocation: a warning inside a closed popover is invisible, which the always-visible sidebar was not. |

## Knock-on work

- **`app.py`** — reserve `top_menu`; repoint the `st.sidebar` fallbacks at
  L491, L1063, L1130–1131, L1211–1212, L1357, L1795, L1876, L1879, L1898,
  L1914, L2471, L2923, L3138, L3409, L3499–3500, L3615, L3637. Rename or drop
  `_sidebar_group` (L1912) — a popover already carries its own label. Drop
  `initial_sidebar_state` from `set_page_config` (L243).
- **`controls.py`** — L1194, L2312, L4144 fallbacks. Docstrings at L2289 that
  say "defaults to `st.sidebar`".
- **`tabs.py`** — L2247 fallback.
- **`debug_log.py`** — L143, L148.
- **`url_state.py`** — `_render_about_sidebar` (`app.py` L597 popover) hosts
  into the Help popover.
- **`tour.py`** — the largest single piece. Spotlight steps carrying
  `in_sidebar: True` lose their meaning; the sidebar open/collapse machinery
  (`stExpandSidebarButton` click, the `aria-expanded` gate, the
  `spotlight_tour_pending → initial_sidebar_state="collapsed"` coupling) is
  deleted, and those steps retarget onto `.st-key-top_menu`. Sidebar-referring
  help text (L353: "**🎓 Show tutorial** in the sidebar") is reworded.
- **`styles.py`** — delete the UX-8 sidebar-dismiss CSS (~L55) and the sidebar
  group-card CSS (~L221). Revisit the width assumptions at ~L405 and ~L474,
  which reason about the sidebar being open or closed changing column width;
  with no sidebar those comments and rules are dead.
- **`scanpath_studio/CLAUDE.md`** and **`AGENTS.md`** — both describe the
  sidebar as the home of these panels; update the module map accordingly.

## Explicitly unchanged

**Widget keys.** Every `global_*` / `single_*` / `filter_*` key keeps its name.
They are a wire format for deep links and saved plot configs, pinned by
`tests/test_session_key_contract.py`. Only the *container* a widget renders into
changes. This means the four-surface rule (UI · deep link · CLI · headless API)
needs no work: no new user-facing option is being added, and the deep
link/CLI/API surfaces never referenced the sidebar.

## Testing

- `tests/test_session_key_contract.py` must pass **unchanged**. That is the
  regression signal that no wire-format key moved.
- `tests/test_apptest.py` — extend the existing boot test to assert that
  `at.sidebar` holds no elements, and that the expected menu popovers exist.
- `tests/test_smoke.py` unaffected (it exercises the data/plot pipeline, which
  this change does not touch).
- Manual check of the spotlight tour end to end, since its step targeting is
  rewritten and it cannot be asserted from `AppTest`.

## Tracker

Open a `UX-` item in `tracker/data.js` for this work, with the four bold-led
paragraphs (Request · What was done · What's left · Background). Note in
*Background* that the dialog mechanism was evaluated and rejected for the reason
above, so it is not re-litigated later.

## Risks

- **Tour breakage.** The spotlight tour is the most sidebar-coupled code in the
  app and the least testable. Budget the most time here.
- **Popover width on narrow screens.** The Configure popover is wide; verify it
  degrades sanely below ~900px rather than overflowing.
- **Concurrent sessions.** Several Claude sessions share this checkout and
  `scanpath_studio/controls.py` currently carries uncommitted work from another
  one. Coordinate before editing `controls.py`.
