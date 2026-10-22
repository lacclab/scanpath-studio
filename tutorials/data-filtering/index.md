# Filter data

- **[Exclude unsuitable trials](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/exclude-unsuitable-trials/index.md)**

  Leave tagged trials out.

- **[Select participants by a field](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/select-participants/index.md)**

  Use participant metadata.

- **[Find the trials an analysis needs](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/find-trials-for-an-analysis/index.md)**

  Select trials after inspecting fixations.

## Before you start

Open a dataset in the **Scanpath** view. The filter () beside **Select trial** selects whole trials. **Filters & highlights** in the Plot controls changes which fixations and saccades the figure draws. Both, and the export these tasks end with, are in the **Full** mode: switch to it in the top bar of the Scanpath view, or add `ui=full` to the app's address ([Essentials and Full](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#essentials-and-full)).

\[!\[

\](../../assets/workflows/trial-filtering_poster.webp)\](../../assets/workflows/trial-filtering.mp4)

## Check and export the selection

1. Check the remaining trial and participant counts and inspect a few trials.
1. Follow [Export every trial](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/export-every-trial/index.md) and choose **All filtered trials**. The bundle's `index.csv` lists its files with their participant and trial IDs.
1. Keep a full decision record with [Data Management → Annotations → Export](https://lacclab.github.io/scanpath-studio/tutorials/data-collection/check-a-session/#5-save-the-review). The annotations in a bundle cover only the exported trials.
