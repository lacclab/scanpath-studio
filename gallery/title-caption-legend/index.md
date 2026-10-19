# Title, caption & legend

A figure ready for a slide or a paper. It has a title above the plot, a caption below it, the **Saccade types** legend down the right side and the **Fixation sizes** legend below the plot.

1. Open your data in the **Scanpath** view and pick a trial in **Select trial**.
1. In **Saccades** ▾ → **Line** → **Color**, choose **By type**.
1. In **Figure & canvas** ▾ → **Title & labels**, tick **Title** and **Caption**. Enter a title for your reading and a caption that explains the markers and colors. Set each one's **Size**, here 34 px and 20 px.
1. Under **Legends**, set **Saccade types** to **Right, outside** and **Fixation sizes** to **Bottom right, outside**, both with text size 18.
1. Under **Screen & framing**, tick **Frame** → **Crop to data**. Untick **Margin** → **Auto** and enter 60 px.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --saccade-color-by-type \
  --title "One participant, one article" --title-size 34 \
  --caption "Marker size: fixation duration. Line color: saccade type." --caption-size 20 \
  --legend saccades=right-outside,,18 --legend size-key=bottom-right-outside,,18 \
  --crop-to-data --crop-margin 60 \
  --highlight-column '' \
  -o title-caption-legend.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    highlight_column=None,
    saccade_color_mode="By type",
    title="One participant, one article",
    title_font_size=34,
    caption="Marker size: fixation duration. Line color: saccade type.",
    caption_font_size=20,
    legend_layout={
        "saccades": {"position": "right-outside", "size": 18},
        "size_key": {"position": "bottom-right-outside", "size": 18},
    },
    fit_to_monitor=False,
    crop_margin=60,
)

sps.save_figure(fig, "title-caption-legend.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
