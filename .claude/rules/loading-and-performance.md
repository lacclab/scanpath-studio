---
paths:
  - "scanpath_studio/loading.py"
  - "scanpath_studio/progress.py"
  - "scanpath_studio/tabs.py"
  - "scanpath_studio/app.py"
  - "scanpath_studio/datasets.py"
  - "scanpath_studio/eyelink.py"
  - "scanpath_studio/export.py"
  - "scanpath_studio/aggregation.py"
  - "scanpath_studio/tour.py"
  - "scanpath_studio/publication_ui.py"
  - "scanpath_studio/data.py"
  - "scanpath_studio/utils.py"
  - "scanpath_studio/controls.py"
  - "scanpath_studio/corpus_overview.py"
  - "scanpath_studio/wizard.py"
  - "scanpath_studio/compare_source.py"
---

# Loading and performance

- **A new slow step gets a `loading.card`, not `st.spinner`**, with
  `progress.report()` from inside its loop. Under a *gated* card it reports at
  the start of its work on a miss, or the card shows late or never. Never create
  a Streamlit element inside a cached function.
- **Keep the plot stage's order**: notes before the figure go to
  `plot_notes_slot`, never into `tour_grp_plot` ahead of the figure.

The checklist form of these rules — the diff that triggers each, the check, and
the bug behind it — is in [`REVIEW.md`](../../REVIEW.md).
