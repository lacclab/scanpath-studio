# Scanpath

Fixations and saccades over the text.

1. Open your data in the **Scanpath View** and pick a trial in **Select trial**.
1. Under **View**, click **Scanpath**. It turns on **Fixations**, **Saccades** and **Stimulus**.
1. Save the figure from **Export** → **Current figure**.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_273 -t l37_273_2_1_1_Ele --screen Paragraph \
  --highlight-column '' \
  -o scanpath.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_273", "l37_273_2_1_1_Ele"
fig = sps.plot_scanpath(words, fixations, pid, tid, screen="Paragraph")

sps.save_figure(fig, "scanpath.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
