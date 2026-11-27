---
paths:
  - "scanpath_studio/compare_source.py"
  - "scanpath_studio/utils.py"
  - "scanpath_studio/similarity.py"
  - "scanpath_studio/controls.py"
  - "scanpath_studio/experimental_setup.py"
  - "scanpath_studio/plots.py"
  - "scanpath_studio/api.py"
  - "scanpath_studio/cli.py"
  - "scanpath_studio/tabs.py"
  - "scanpath_studio/app.py"
  - "scanpath_studio/url_state.py"
  - "scanpath_studio/session_keys.py"
---

# Compare

- **Scanpath B's id is namespaced only in the throwaway compare frames**
  (`utils.qualify_for_compare`), since two corpora can share a
  `(participant_id, trial_id)`; everything user-facing goes through
  `utils.unqualify_for_export`.
- **Overlay and co-animation across datasets need equal canvases**
  (`experimental_setup.setups_comparable`): the app falls back to side by side,
  the API raises `IncomparableScreensError`, the CLI exits.
- **Filter helpers are prefix-scoped**: B's use `cmp`, and
  `controls.FILTER_PREFIXES` keeps clearing A's from wiping B's.

The checklist form of these rules — the diff that triggers each, the check, and
the bug behind it — is in [`REVIEW.md`](../../REVIEW.md).
