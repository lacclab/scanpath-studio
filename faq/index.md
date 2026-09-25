# FAQ

## Why is the plot empty or misaligned?

Check the 🗂️ **Data** page. The words and fixations must share trial IDs and the same pixel coordinate system. Also set the monitor size used in the experiment (🗂️ **Data → ✏️ Edit dataset → Recording setup**): most eye-tracker exports don't record it, and *Estimate from my data* gives only a lower bound. See [Loading data](https://lacclab.github.io/scanpath-studio/guides/loading-data/index.md).

## Why do the measures differ from EyeLink or my pipeline?

Recognized EyeLink IA measures are preserved. Otherwise the app assigns fixations using your word boxes and computes its own measures. AOI padding, fixation exclusions, and definitions can differ between pipelines. Cross-check values used in a publication.

## Does 🧹 Filter change the measures?

No. The plot rail's **🧹 Filter** section — duration, boundary, and index controls for fixations, reading classes for saccades — affects the rendered scanpath only. It does not edit the source tables or recompute the corpus measures.

## Can I load only one table?

Yes. A words-only table can visualize precomputed word measures; a fixations-only table can show gaze positions without stimulus text. Most features work best with both tables.

## A zip upload is refused as "above the per-file limit"

The app caps how far a `.zip` may decompress (32 GB per file and 64 GB in total by default). The error names the setting to raise, e.g. `SCANPATH_ZIP_MAX_MEMBER_GB=64 scanpath-studio`.

## Why does HTML export work but PNG/SVG/PDF fail?

Static formats use Kaleido and need Chrome/Chromium. See [Export troubleshooting](https://lacclab.github.io/scanpath-studio/export-troubleshooting/index.md).

## Can another person open my share link?

Yes, but uploaded data is not embedded in the URL. The recipient must load the same dataset. Share links include the current participant and trial; see [Outputs and sharing](https://lacclab.github.io/scanpath-studio/guides/outputs-sharing/index.md).

## Does a refresh erase my work?

Not on a local or desktop install: completed datasets and session state are restored from an on-device recovery cache. The hosted demo keeps nothing — download a **💾 Session → JSON backup** there.

## Where does my data go?

Local and desktop use stays on your machine: nothing is uploaded, and there are no accounts or analytics. A local or desktop run also keeps a recovery copy of your datasets and settings; **💾 Session → 🗄️ Automatic recovery** shows it, pauses it or deletes it. Don't upload identifiable data to the hosted demo. See [Privacy](https://lacclab.github.io/scanpath-studio/privacy/index.md).

## How do I cite the app?

By its Zenodo DOI, [10.5281/zenodo.22933884](https://doi.org/10.5281/zenodo.22933884), which always resolves to the latest release. [Cite](https://lacclab.github.io/scanpath-studio/cite/index.md) has the BibTeX and APA entries, and the citations for the demo data and any public corpus you used.
