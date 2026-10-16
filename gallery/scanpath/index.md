# Scanpath

Fixations and saccades over the text.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization.
1. Keep the Scanpath design preset, with Fixations, Saccades and Stimulus on.
1. Use Export → Current figure to save it.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  -o scanpath.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
fig = sps.plot_scanpath(words, fixations, pid, tid)

sps.save_figure(fig, "scanpath.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
