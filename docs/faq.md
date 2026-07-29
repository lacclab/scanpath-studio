# FAQ

Short answers to the questions that come up most. Each one links to the page
with the long version.

## Data & loading

??? question "What file formats can I load?"
    **CSV, TSV, Parquet and Feather**, for up to three tables: **words /
    areas-of-interest**, **fixations**, and (optionally) **raw gaze**. Either of
    the two main tables can be omitted — the missing layer just isn't drawn, and
    a words-only table still draws a heatmap from its pre-aggregated measures.

    You can upload **several files per table**; they're concatenated and each row
    remembers which file it came from, which is how one-file-per-participant
    exports load. → [Data format](data-format.md)

??? question "The app mapped one of my columns to the wrong field. Where do I fix it?"
    In the app: 🔎 **Data Inspection → Column mapping** is an editable form that
    re-derives everything in place — no re-upload. During import, the wizard's
    mapping step does the same job, and every widget shows what it found
    (`✨ auto-detected IA_LEFT`, plus `· overridden` once you change it). **A
    field with no caption matched nothing.**

    Headlessly, pass `word_schema` / `fix_schema` to `load_scanpath_data`. An
    explicit schema **replaces** auto-detection for that table rather than adding
    to it. `scanpath_studio.api.propose_schema(frame, "words")` prints what
    auto-detection would pick.

    One catch: columns literally named `unique_trial_id` or `unique_paragraph_id`
    win over what you pick in the wizard. Rename or drop them before uploading.
    → [Bring your own data](bring-your-own-data.md#when-it-guesses-the-wrong-column)

??? question "A column I need disappeared after import."
    Anything not claimed at import is dropped, for speed. Mapped columns,
    recognised reading measures and linguistic fields, and recognised trial
    conditions are kept by default; everything else is **off** unless you tick it
    under *Filter & keep → Additional fields to keep* in the wizard. Getting one
    back needs a re-upload. → [Bring your own data](bring-your-own-data.md#when-it-goes-wrong)

??? question "What counts as a “trial”?"
    A trial is one reading event — **one participant reading one text once** —
    and it is whatever your **Trial ID** mapping says it is. Everything downstream
    (the trial picker, the filters, per-word measures, export scope) keys off it.

    Three consequences worth knowing:

    - **`TRIAL_INDEX` alone is not enough.** EyeLink's trial index only identifies
      a trial *within one reader*, and the **Text ID** falls back to the trial ID —
      so trial 3 of every reader looks like the same text. If trial order was
      randomised, map your item column as **Text ID**.
    - **Repeated readings.** With a single-column trial mapping, a second reading
      of the same passage is automatically split off (`par3` → `par3_r2`). Build a
      multi-column trial ID and that automatic split turns **off**, so add your
      repeat-marking column to the composite.
    - **A trial is not a text.** *Text* pools different readers of the same
      passage; that's what Corpus Analysis groups by. In OneStop the difficulty
      variant is part of the text id, so `2_2_1_Adv` and `2_2_1_Ele` are two
      different texts.

??? question "Every fixation is out of the text and no word gets a measure."
    The fixations and the word boxes are in different coordinate systems. Usually
    **y measured from the bottom** in one table and from the top in the other,
    different **recording resolutions**, or **degrees of visual angle vs. pixels**.
    The app applies **no** coordinate transform — compare the two ranges in 🔎
    Data Inspection, fix it in the export, re-upload.
    → [Bring your own data](bring-your-own-data.md#when-it-goes-wrong)

## Measures

??? question "Why don't the reading measures match what EyeLink reported?"
    Usually they do — because they *are* EyeLink's. **Pre-computed `IA_*` columns
    on your words table take precedence** over anything the app would compute, so
    a normal Data Viewer export is passed through unchanged
    (`IA_FIRST_FIXATION_DURATION`, `IA_DWELL_TIME`, …).

    That match is by **exact column name**. A renamed export loses it and falls
    back to the app's own computation, which is where differences come from:

    - **Fixation→word assignment.** The app assigns by bounding-box containment,
      then nearest word-center within 50 px, else no word. Your tracker's
      assignment (and its own AOI padding) may differ.
    - **Which fixations are in scope.** Blinks, out-of-text fixations, and
      duration cut-offs are excluded differently by different pipelines. The
      short/long/out-of-bounds highlighting in the app is **visual only** — it
      does not change the computed measures.
    - **Measure definitions.** The app follows Rayner (1998) and Inhoff & Radach
      (1998): FFD, FPRT (gaze duration), RPD (go-past), TFD (dwell), plus skips
      and regressions.

    The measures are pinned to a hand-traced ground-truth trial with expected
    values per measure (open it in the app with `?source=synthetic`). That is not
    the same as bug-free — **cross-check anything you publish against your own
    pipeline**. → [Data format → Reading measures](data-format.md#reading-measures)

??? question "Where do the areas of interest come from?"
    Straight from **your** word bounding boxes — either `x/y/width/height` or
    EyeLink's `IA_LEFT/RIGHT/TOP/BOTTOM`. The app does not compute AOIs, pad
    them, or infer them from the text. The only thing derived from geometry is
    the fixation→word assignment, and the visual line clustering used by
    "colour by line" (word-box `y` clustering, because `line_idx` is a constant
    in many IA exports).

??? question "What does drift correction actually do?"
    It reassigns each fixation to the text **line** it most likely belongs to,
    then snaps it onto that line — the standard remedy for vertical drift in a
    long recording. It does **not** change x, and it does not touch your stored
    data: it is applied to the figure you're looking at.

    Scanpath Studio ships a native port of the **ten algorithms** surveyed by
    [Carr et al. (2021)](https://doi.org/10.3758/s13428-021-01554-0) — `attach`,
    `chain`, `cluster`, `compare`, `merge`, `regress`, `segment`, `split`,
    `stretch`, `warp` — reimplemented rather than depending on the GPL-licensed
    `eyekit`.

    Two surfaces: **Fixations ⚙️ → Drift correction** applies one algorithm in
    place on the main plot (optionally drawing original→corrected connectors),
    and the **📐 Line assignment** subtab's *Show comparison grid* builds one
    panel per algorithm so you can see how they disagree before committing.
    Headlessly it's `plot_scanpath(..., drift_correction="warp",
    drift_connectors=True)`.

    They *are* heuristics, and they disagree most exactly where the data is
    worst. Look at the grid before trusting one.

## Running the app

??? question "I restarted the app / refreshed the tab and my data is gone."
    Expected. Uploaded tables, datasets you built in the wizard, and your
    favourites / tags / notes live in **session state** — there are no accounts
    and no database, so they die with the session. Two ways to not lose work:

    - ⬇️ **Download setup (JSON)** in the wizard saves the column mapping, and
      💾 **Save & restore** saves the plot configuration. Both are re-importable.
    - Annotations (favourites / tags / notes) export to JSON from the sidebar and
      restore the same way.

    The bundled demo and the public corpora reload themselves, so only *your*
    uploads are affected. → [Privacy](privacy.md)

??? question "I changed the code and the app doesn't show it."
    Restart the server. Streamlit doesn't reload imported modules on a rerun, and
    `st.cache_data` doesn't hash transitively-called helpers — so a rerun or
    "Clear cache" isn't enough. This one is for contributors; see
    `CONTRIBUTING.md` → *If a code change doesn't show up*.

??? question "PNG / SVG / PDF export fails, but HTML works."
    Static image export (and GIF/MP4) goes through
    [Kaleido](https://github.com/plotly/Kaleido), which drives a **headless
    Chrome** that `pip install` does not provide. Run it once:

    ```bash
    plotly_get_chrome -y      # or: kaleido_get_chrome
    ```

    Interactive **HTML** export is browser-free and always available as a
    fallback. → [Export & troubleshooting](export-troubleshooting.md)

??? question "Where does my data go? Is anything uploaded?"
    **Nowhere.** No accounts, no server of ours, no analytics of ours. Files are
    read into memory and parsed; nothing writes your tables to disk and nothing
    sends them anywhere.

    Two things worth knowing anyway:

    - **A plain `streamlit run` listens on your whole network, with no login.**
      On a lab network or anything with a public IP, start it with
      `scanpath-studio --server.address=127.0.0.1`. The
      [desktop app](desktop.md) already binds to your machine only.
    - **The [online demo](https://scanpath-studio.streamlit.app) runs on a server
      operated by Streamlit (Snowflake), not by us.** Don't put identifiable
      recordings there.

    → [Privacy](privacy.md) for the full picture, and the
    [security audit](security.md) for the function-by-function version.

??? question "The reading text looks too big / too small."
    Set the **monitor resolution** the stimulus was actually shown on
    (*Experimental setup* in the wizard, or `canvas_size=(W, H)` headlessly).
    Nothing in an eye-tracker export records it, so the app can't guess —
    uploads default to 2560 × 1440. Get it wrong and the plot stays internally
    consistent, but the text is the wrong size relative to the fixations.
    → [True-to-scale rendering](rendering.md)

??? question "Can I send someone the exact view I'm looking at?"
    Yes — the **🔗 Share** subtab builds a deep link that reopens the app on this
    trial with these settings. A built-in data source (the demo, the synthetic
    trial, a public corpus) is rebuilt from the link; **uploaded tables can't
    be**, so the recipient needs the same data loaded and only the view settings
    travel. The panel says so when that applies.

    For a bug report, attach the 💾 **Save & restore** JSON — it reproduces the
    exact view.

## Citing

??? question "How do I cite Scanpath Studio?"
    Citation metadata lives in
    [`CITATION.cff`](https://github.com/lacclab/scanpath-studio/blob/main/CITATION.cff)
    — GitHub renders a ready-made APA/BibTeX entry from it — and the same details
    are in the app's **About** panel.

    If you used the **bundled demo data**, cite OneStop Eye Movements as well:
    Berzak, Malmaud, Shubi, Meiri, Lion & Levy (2025), *OneStop: A
    360-Participant English Eye Tracking Dataset with Different Reading
    Regimes*, Scientific Data,
    [doi:10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2).

    If you used the **drift-correction algorithms**, cite
    [Carr et al. (2021)](https://doi.org/10.3758/s13428-021-01554-0) — the ten
    algorithms are adapted from the reference implementation at
    [jwcarr/drift](https://github.com/jwcarr/drift) (CC BY 4.0).

    Public corpora loaded through the app (PoTeC, MultiplEYE) have their own
    citations — see [Datasets](onestop.md).

---

Didn't find it? The [tutorials](tutorials/index.md) walk complete tasks
end-to-end, and anything still missing is worth an
[issue](https://github.com/lacclab/scanpath-studio/issues).
