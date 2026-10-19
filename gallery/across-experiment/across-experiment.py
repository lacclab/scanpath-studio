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
    title="Across the experiment · Participant A",
    canvas_width=1000,
    base_font_size=18,
    font_family="Arial",
    height=450,
    break_gaps=True,
)

sps.save_figure(fig, "across-experiment.html")
