---
paths:
  - "scanpath_studio/plots.py"
  - "scanpath_studio/tabs.py"
  - "scanpath_studio/html_embed.py"
  - "scanpath_studio/export.py"
  - "scanpath_studio/export_*.py"
  - "scanpath_studio/bulk_renderer.py"
  - "scanpath_studio/animation_export.py"
  - "scanpath_studio/file_citation.py"
  - "scanpath_studio/replay_frames.py"
  - "scanpath_studio/chart_axes.py"
  - "scanpath_studio/figure_views.py"
  - "scanpath_studio/publication.py"
  - "scanpath_studio/panel_proof.py"
  - "scanpath_studio/code_snippet.py"
  - "scanpath_studio/api.py"
  - "scanpath_studio/cli.py"
  - "tests/test_smoke.py"
  - "scanpath_studio/corpus_overview.py"
  - "scanpath_studio/publication_ui.py"
  - "scanpath_studio/panel_proof_ui.py"
  - "scanpath_studio/cite_button.py"
  - "scanpath_studio/save_dialog.py"
---

# Figures

- **Spatial plots go through `tabs._render_true_scale_chart`, never
  `st.plotly_chart`**, which pins the width to the column but keeps the layout
  height and so mis-scales the px-sized word labels. The embed draws the
  figure's HTML at its exact pixel size and CSS-scales it. plotly.js comes from
  the app's own server (`html_embed.plotlyjs_script`); HTML downloads take
  `export.html_plotlyjs(...)`.
- **The replay player owns the clock.** Plotly's frame queue rounds frames up
  to display ticks, so `make_scanpath_animation` stamps each frame's reading
  time on `fig.layout.meta` and every HTML surface passes
  `plots.animation_player_post_script(fig)`. Pages carry the frames packed
  (`plots.replay_page`: frame 0 whole, then deltas); the figure keeps its own.
- **Transport controls never shrink the plot.** The figure keeps Plotly's
  controls in a top band it grows by (`plots._CONTROLS_MARGIN_PX`; GIF/MP4
  strip it). HTML pages hide them, take the band back (`plots.replay_page_box`)
  and draw a `REPLAY_TOOLBAR_PX` row above the figure instead. A legend above
  the plot grows the figure past the band, never into it.
- **Set layout shapes in one assignment** (`fig.layout.shapes = …`); each
  `add_shape` re-validates every shape (`tests/test_smoke.py` counts them).
- **A new top-level trace** in `make_scanpath_figure` goes in
  `plots._trace_layer`, or separable-layer export files it under fixations.
- **Every exported file carries the citation** — `export._figure_renderer`,
  `file_citation.stamp_html` / `stamp_file`, `animation_export`, and the bytes
  `tabs._render_save_plot_button` hands its component. A new writer stamps its
  output too; only the toolbar camera's PNG can't.
- **Kaleido** (PNG/SVG/PDF, GIF/MP4) needs Chrome (`plotly_get_chrome -y`;
  `packages.txt` on Streamlit Cloud). Hold `animation_export.KALEIDO_LOCK`
  for native rendering. Single figures and animations use Kaleido's process-wide
  warm server. Multi-reading bundles reuse one browser page and periodically
  replace the browser to release native memory. The on-screen PNG/SVG is saved
  in the browser. HTML export works without Chrome.
- Bulk export iterates *all* filtered trials — narrow the filter first.

The checklist form of these rules — the diff that triggers each, the check, and
the bug behind it — is in [`REVIEW.md`](../../REVIEW.md).
