# Across the experiment

Mean total fixation duration per word across the demo reader’s recorded trials. Each point summarizes one trial; this is the bundled subset of the session.

1. Select the bundled demo and open Corpus Analysis → Per participant.
1. Choose `l37_1129`, Total fixation duration and Mean aggregation.
1. Open Per-trial trend. The horizontal axis uses the dataset’s `trial_index`.

[Follow the progression tutorial](https://lacclab.github.io/scanpath-studio/tutorials/corpus-analysis/progression-over-time/index.md)

The corpus CLI does not offer trial-order trends. Download the [Python recipe](https://lacclab.github.io/scanpath-studio/gallery/across-experiment/across-experiment.py) and run:

```
python across-experiment.py
```

This uses the app’s aggregation and trend builder.

```
import scanpath_studio as sps

from scanpath_studio.aggregation import metric_by_trial_index
from scanpath_studio.data import derive_trial_index
from scanpath_studio.plots import make_trend_figure

words, fixations = sps.load_sample_data(names="canonical")
reader = words[words["participant_id"] == "l37_1129"].copy()
reader["trial_index"] = derive_trial_index(reader)
trend = metric_by_trial_index(reader, "total_fixation_duration_ms")
fig = make_trend_figure(
    trend,
    x_col="trial_index",
    x_label="Recorded trial order",
    y_label="Mean total fixation duration per word (ms)",
    title="Across the experiment · Reader A",
    canvas_width=1000,
    base_font_size=18,
    font_family="Arial",
    height=450,
    break_gaps=True,
)

sps.save_figure(fig, "across-experiment.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
