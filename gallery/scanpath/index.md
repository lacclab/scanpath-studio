# Scanpath

Fixations and saccades over the text.

1. Open your data in the **Scanpath** view and pick a trial in **Select trial**.
1. In **Design presets**, click **Scanpath**. It turns on **Fixations**, **Saccades** and **Stimulus**.
1. Save the figure from **Export** → **Current figure**.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --highlight-column '' \
  -o scanpath.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
fig = sps.plot_scanpath(words, fixations, pid, tid, highlight_column=None)

sps.save_figure(fig, "scanpath.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
