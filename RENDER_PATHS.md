# Which viz settings apply in which render path

Part of the contributor map in [`AGENTS.md`](AGENTS.md), kept in its own file
because it is needed only when a figure option or a builder's parameters change.
Update it in the same PR as such a change; `tests/test_mode_parity.py` checks
the code side.

The scanpath rail (`controls.render_plot_controls`) is **one** control set
feeding **three** figure builders, picked by the rail's Animate / Compare
toggles (`single_animate` / `single_compare_toggle`, rendered in `tabs.py`
before `render_plot_controls`):

| mode | builder | thread |
| --- | --- | --- |
| neither toggle | `plots.make_scanpath_figure` | `tabs._build_figure_settings` → `_cached_scanpath_figure` |
| **Animate** | `plots.make_scanpath_animation` | `tabs._build_and_render_animation` |
| **Compare** | `plots.make_comparison_figure` (split layouts: `_make_split_comparison_figure`) | `tabs._render_comparison_figure` |
| **Animate + Compare** | `make_scanpath_animation(fixations_b=…)` — the co-animation | same as Animate |

The table below describes the app's controls. For the headless API and CLI,
the [figure options reference](https://lacclab.github.io/scanpath-studio/api/#figure-options)
lists the four render views. The reference and compact Share snippets use
`figure_views.options_for_view`; `api.figure_options` lists accepted keywords.

| setting (`viz_settings` name) | static | animation | compare | notes |
| --- | :---: | :---: | :---: | --- |
| `show_words`, `show_labels`, `show_saccades`, `show_order`, `order_font_size`, `order_label_position` | ✅ | ✅ | ✅ | |
| `word_box_*` (colour, line / fill opacity) | ✅ | ✅ | fill and both opacities | Compare outlines each reading's boxes in its own `cmp{idx}_box_color` (its scanpath colour by default); each style can also override the fill and opacities |
| `show_fix` | ✅ | ❌ | ✅ | The replay *is* the fixation trail |
| `show_saccade_arrows`, `saccade_arrow_size`, `saccade_opacity` | ✅ | ✅ | ✅ | One figure-wide value in Compare |
| `legend_layout` | ✅ | ✅ (not saccades) | ✅ (not saccades) | `plots.apply_legend_layout`; one `legend_<kind>=SPOT[,ARR][,SIZE]` link param per moved legend, `render --legend` |
| Global fixation index color, marker color, opacity and hollow markers, saccade color / style / width | ✅ | ✅ (single only) | ❌ | Compare and the co-animation use the per-scanpath `cmp{idx}_*` styles; fixation indices use each scanpath's fixation color |
| `marker_size_range` | ✅ | ✅ | ✅ | A/B controls set each scanpath's range. A style without a range inherits the figure-wide value. |
| `color_by`, `fixation_colorscale`, `fixation_color_range` | ✅ | ✅ | ✅ | Compare colours the fill and makes the scanpath colour the outline; a range is present only when explicit (absent = scale to the data, A+B together) |
| `fixation_symbol` | ✅ | ✅ | ✅ | Glyph shapes (♥) are drawn as text by `plots._glyph_scatter_traces` in every builder |
| `marker_size_scale`, `marker_duration_range`, `duration_size_legend` | ✅ | ✅ | ✅ | One duration scale; the size key draws in Compare only while A and B share a px range |
| `fix_index_range` | ✅ | ✅ | ✅ | Sliced in `tabs._slice_fix_range`; Compare's B has its own window (`single_compare_fix_range`) |
| `fixation_flags` (short / long / out-of-bounds) | ✅ | ✅ | ✅ | Compare applies each scanpath's own (B: `cmp1_fixclass_*`) |
| `illustration_label` / `illustration_text` | ✅ | ✅ | ❌ | `compare_scanpaths` takes no label; the app stamps it itself |
| drift correction (`align_algorithm`) | ✅ | ✅ | ✅ | Experimental; `tabs._drift_corrected` runs once above the mode split; "Off" returns the same frame object |
| drift connectors (`align_connectors`) | ✅ | ❌ | ❌ | Only the static figure has the original→corrected layer |
| `fixation_snap_to_line` / `_position`, Arc saccades | ✅ | ❌ | ❌ | The linear-reading schematic |
| saccade colour by type, `saccade_classes` | ✅ | ❌ | classes only | Reading-class colouring is static-only; Compare filters classes per scanpath |
| heatmap (`show_heatmap`, metric / norm / colour scale / range / opacity) | ✅ | ❌ | ✅ | Compare is always word boxes (`heatmap_style` static-only), on a scale shared by A and B |
| raw gaze (`show_raw_gaze`, size / opacity) | ✅ | ❌ | ✅ | Compare draws each reading's samples in its scanpath's colour |
| stimulus image (`background_image*`, opacity / offset / scale) | ✅ | ✅ | ✅ | Split layouts get one image per panel |
| `highlight_column`, `highlight_text_color`, `text_color` | ✅ | ✅ | ✅ | Only *Mark text* reaches all three; *Mark border* (`span_border_color`) is static-only |
| `redact_text` | ✅ | ✅ | ✅ | `plots.redact_word_text` masks the words at each builder's entry; the blocks take the text / highlight colour |
| `word_hover_measure` | ✅ | ✅ | ✅ | The measure appears when the word hover includes it. |
| colour bars (`{fixation,heatmap}_colorbar_*`) | ✅ | ✅ fixation only | ✅ | Through `plots._colorbar_dict` |
| `x_field` / `y_field` | ✅ | ❌ | ❌ | Index and elapsed-time presets set these same two fields. On a position chart, index supports a sequence line and elapsed seconds show fixation durations. Raw samples require both plotted fields. Animation and comparison use screen `x` / `y` |
| `fit_to_monitor`, `crop_margin`, coordinate grid + font size, title / caption styling, `show_credit`, `background_color`, `show_plot_frame` / `plot_frame_color` | ✅ | ✅ | ✅ | |
| `fixation_outline_width` / `_color` | ✅ | ✅ | ✅ | |
| `show_compare_legend`, `compare_stimulus` | ❌ | ✅ (co-animation) | ✅ | Widgets in `tabs.py` (⚙ Compare options) |
| `anim_autoplay`, replay grid step / max frames, `playback_speed` | ❌ | ✅ | ❌ | Widgets in `tabs.py` (⚙ Playback) |
| `canvas_b`, `background_image_b*` | ❌ | ❌ | ✅ (split only) | B's own screen and page; `None` = same as A |

The canvas / font controls (`app.render_canvas_controls`: line spacing,
scale-to-boxes, base font, canvas size, text colour) reach all three builders.
`app.seed_canvas_state` seeds their keys before any view renders, so the
rail-less Corpus view resolves the same geometry.
