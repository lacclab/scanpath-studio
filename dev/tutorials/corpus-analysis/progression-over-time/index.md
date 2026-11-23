# Track changes over time

Inspect a measure within trials or across a session.

1. [Select the trials](https://lacclab.github.io/scanpath-studio/dev/tutorials/corpus-analysis/#before-you-start) and open **Corpus Analysis**.

1. To follow one reader, choose **Participants**, select a reader and open their profile. To follow a group, choose **Groups** and turn off **Compare two groups**. In **Chart settings**, choose the **View** you need.

   | Scope                                                       | View                            |
   | ----------------------------------------------------------- | ------------------------------- |
   | One participant across trials                               | **Per-trial trend**             |
   | Fixation duration within trials, pooled for one participant | **Fixation duration over time** |
   | A group across trials                                       | **Group trend**                 |

1. Choose a measure, and an **Aggregate** where the view offers one. Across-trial trends order each participant's trials by a `trial_index` or `TRIAL_INDEX` column. Without one, the app orders them by fixation time, or as listed, and this may differ from the order the trials were shown. For the within-trial view, set **X axis** to **Fixation order**, or to **Time (ms)** when the data records fixation onsets.

1. [Download the table and recipe](https://lacclab.github.io/scanpath-studio/dev/tutorials/corpus-analysis/#keep-the-result).
