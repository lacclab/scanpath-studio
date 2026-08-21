# Automation & reference

Use the app for exploration, the CLI for one repeatable render, and Python for
loops or analysis pipelines.

| Need | Best surface |
| --- | --- |
| explore controls and inspect trials | app |
| render one known trial in a shell script | CLI |
| batch, compute measures, or integrate with code | Python API |

## CLI: one figure

```bash
scanpath-studio render --sample --list-trials
scanpath-studio render --sample -p 1 -t 1 -o scanpath.html
```

Replace `--sample` with `--words ia.csv --fixations fixations.csv`. Run
`scanpath-studio render --help` for every visualization flag, or use the
[short CLI guide](cli.md) for common combinations.

## Python: one pipeline

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
trials = sps.list_trials(words, fixations)
pid, tid = trials.iloc[0][["participant_id", "trial_id"]]

fig = sps.plot_scanpath(words, fixations, pid, tid)
sps.save_figure(fig, "scanpath.html")

metrics = sps.compute_word_metrics(words, fixations)
metrics.to_csv("word_measures.csv", index=False)
```

The [Python API](api.md) lists the public functions and parameters.

## Batch pattern

```python
from pathlib import Path
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
out = Path("figures")
out.mkdir(exist_ok=True)

for row in sps.list_trials(words, fixations).itertuples():
    fig = sps.plot_scanpath(words, fixations, row.participant_id, row.trial_id)
    sps.save_figure(fig, out / f"{row.participant_id}_{row.trial_id}.html")
```

Use explicit participant/trial IDs and keyword arguments for published output;
do not depend on the first row or a changing UI selection. HTML is the most
portable automated format. Static images require Chrome/Chromium.

## Reference map

- [Data format](data-format.md): accepted tables and canonical fields
- [Computations & methodology](computations.md): every derived value's formula,
  units, grouping keys, and precedence
- [Python API](api.md): loaders, measures, plot builders, and saving
- [CLI](cli.md): launch and render commands
- [Harmonised benchmark corpora](benchmark-corpora.md): thirty-one public corpora
  in one schema
- [True-to-scale rendering](rendering.md): coordinate and canvas details
- [Privacy](privacy.md): local, desktop, and hosted data handling
