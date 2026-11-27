---
name: verify
description: See a Scanpath Studio change working before calling it done — boot the app headless, render through the CLI and the API, and (for anything visible) look at it in a real browser. Use after implementing a feature or fix and before committing, setting an issue to Review, or saying "done".
---

# Verify — see the change work

Tests show the code agrees with itself; this shows the app does what the user
asked. Run it on every change that a user can observe. Report what you ran and
what you saw — the commands, the PASS/FAIL lines, a screenshot — not "verified".

## 1. The harness (always, about 15 s)

```bash
uv run --extra test python scripts/verify_change.py
```

It boots the three views headless (`AppTest`, Full mode), runs
`scanpath-studio render --sample`, and builds `plot_scanpath` on the bundled
demo; one PASS/FAIL line each, exit 1 on any failure. It writes nothing to the
recovery cache or the user's state directory.

**A feature option is checked on all four surfaces** by giving its spelling on
each — the deep-link param, the `render` flag, the API keyword (the four-surface
rule in `AGENTS.md`). Use `--check-option` to compare the actual Scanpath session
value with the value requested by a published deep-link option. Use `--query`
for navigation and source selections.

```bash
uv run --extra test python scripts/verify_change.py \
    --check-option order_label_position=below \
    --render-args "--order-label-position below" \
    --api-kwargs '{"order_label_position": "below"}'
```

`--ui essentials` boots Essentials instead. `--out-dir DIR` keeps the HTML the
CLI and API wrote, so you can open them.

## 2. Look at it (visible changes)

Find the feature in [`feature-map.md`](feature-map.md): where it lives, its
key, and what a user should see. Then check exactly that:

- **Headless first** — an `AppTest` drive (set the widget, `at.run()`, read the
  state or the drawn element) is fast and repeatable; prefer it, and keep it as
  a test when it caught something.
- **In a browser when it is about what is drawn** — CSS, the true-scale plot
  iframe, popovers, a replay, anything the frontend does. `preview_start
  {name: "scanpath-studio"}` (port 8511, the main checkout's code). From a
  worktree, start the worktree's own server instead:
  `SCANPATH_STUDIO_PERSIST=0 .venv/bin/python -m streamlit run streamlit_app.py
  --server.port <free port> --server.headless true --server.address 127.0.0.1`
  in the background, then `preview_start {url: …}`. Restart it after every code
  change — Streamlit does not reload imported modules.
- Never time an animation in the Browser pane (a hidden pane throttles
  `requestAnimationFrame`); use headless Chrome for that.
- Share a screenshot of the result with the user.

## 3. Fix, then re-run — three rounds at most

Fix what failed and run the harness again. **After three rounds on the same
failure, stop and tell the user** what fails, what you tried, and what you
suspect. A fourth guess costs more than the question.

## 4. Record it

Put a `Verified:` trailer on the commit naming what ran, e.g.
`Verified: harness, apptest, browser` or `Verified: tests` — and
`Verified: none` with the reason when nothing could (a docs-only change). See
*Before every commit / push* in `CLAUDE.md`.

## Keep the harness honest

The harness is only useful while it is fast and never flaky. If a check fails
for a reason that is not the code — a timeout, the environment — fix the
harness in its own commit; never add a sleep or a retry to get it green. When a
feature lands, add its row to `feature-map.md` in the same PR.
