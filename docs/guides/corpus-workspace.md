# Corpus workspace

**📊 Corpus Analysis** summarises many readings at once. It uses the same
dataset and trial filters as the Scanpath view.

<figure class="sps-screenshot" markdown>
![Corpus Analysis, Per text: each reader's total fixation duration on every word of one text, against the cohort mean](../assets/screenshots/corpus-analysis.webp)
</figure>

## Reading measures come from your data

Corpus Analysis shows the reading measures your interest-area report provides
(first fixation duration, total fixation duration, regression path, and so on).
It does not compute them itself. An EyeLink report's `IA_*` columns are mapped
automatically; other names can be mapped under 🗂️ **Data → Edit dataset**.
Without any, the page says so.

## Four views

| View | Answers |
| --- | --- |
| **Per text** | How was this text read, word by word, across readers? |
| **Per sentence** | How was each sentence read? |
| **Per reader** | How does this reader behave across trials? |
| **Groups** | How do conditions or populations differ? |

Choose a measure, how to aggregate it, and the spread to show. Set a **minimum
number of readers** per word so sparse words don't look like stable estimates.

**Groups** defines a cohort by splitting on a field, or with its own filters.
Turn on **Compare** for a second cohort, with the difference and effect size.
Fields from attached participant, trial or text tables appear here too.

## From summary to evidence

Every result has **⬇ Download this table (CSV)**. When something looks odd,
open the trials behind it in the Scanpath view.
