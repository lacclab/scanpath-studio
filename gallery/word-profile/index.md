# Word profile

Mean total fixation duration across readers, with a standard-deviation band.

1. Select the bundled demo and clear any trial filters.
1. Open Corpus Analysis → Per text. Choose text `2_1_1_Ele` and Total fixation duration.
1. Choose Cohort profile, Mean aggregation and SD spread.
1. Download this table (CSV) saves the values.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

[Download the example table](https://lacclab.github.io/scanpath-studio/gallery/word-profile/word-profile.csv) first.

```
scanpath-studio corpus --input word-profile.csv --kind profile \
  --measure-label "Total fixation duration (ms)" -o word-profile.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
# The demo's word table carries EyeLink's own measures (IA_DWELL_TIME, …).
one_text = words[words["unique_paragraph_id"] == "2_1_1_Ele"]
profile = (
    one_text.groupby("IA_ID")
    .agg(
        value=("IA_DWELL_TIME", "mean"),
        sd=("IA_DWELL_TIME", "std"),
        word_text=("IA_LABEL", "first"),
    )
    .rename_axis("word_id")  # the column plot_corpus_figure reads
    .reset_index()
    .assign(lo=lambda d: d.value - d.sd, hi=lambda d: d.value + d.sd)
)
fig = sps.plot_corpus_figure(
    profile, kind="profile", measure_label="Total fixation duration (ms)"
)

sps.save_figure(fig, "word-profile.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
