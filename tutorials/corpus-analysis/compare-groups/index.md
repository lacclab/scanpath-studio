# Compare groups or conditions

To compare two reading conditions in the bundled demo, use the advanced (**Adv**) and elementary (**Ele**) versions of its texts.

1. [Select the trials](https://lacclab.github.io/scanpath-studio/tutorials/corpus-analysis/#before-you-start), then open **Corpus Analysis** and select **Groups**. Choose a measure.
1. In **Edit groups**, use **Split a field** and choose `difficulty_level`. Select **Adv** for Group A and **Ele** for Group B. Each group needs at least one value. To choose participants, texts or conditions separately for each group, use **Independent filter sets**. A group with no filters includes all selected trials.
1. Read **Difference (A − B)**. For total fixation duration, a difference of 20 ms means that Group A spent 20 ms longer per word on average. The counts show how many participants contributed a value to each mean. For a rate, a change from 30% in B to 40% in A is a difference of 10 percentage points.
1. [Download the table and recipe](https://lacclab.github.io/scanpath-studio/tutorials/corpus-analysis/#keep-the-result).

For a different comparison, open **Chart settings** and choose a **View**. To explore Group A on its own, turn off **Compare two groups**.

For each participant, **Group means & difference** averages the words with a recorded value across all their selected trials. A trial with more measured words has more weight in that participant's mean. The group mean then gives each participant equal weight. In **Participants**, each reading contributes one mean to the summary, so the two views can give different values.

A participant who read both conditions contributes to both group means. The **Standardized difference** (Cohen's d) is available only for groups with no participants in common.
