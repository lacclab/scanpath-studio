# Redacted text

Show where the text was without showing what it said. Each word is drawn as a rounded block over its letters, and the hovers hide the words too.

1. Open your data in the **Scanpath** view and pick a trial in **Select trial**.
1. In **Stimulus** ▾ → **Text**, tick **Redact**. The blocks take the text color.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele \
  --redact-text --highlight-column '' \
  -o redacted-text.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
fig = sps.plot_scanpath(words, fixations, pid, tid, redact_text=True)

sps.save_figure(fig, "redacted-text.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
