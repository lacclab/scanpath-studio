# Tutorial 6 — Export a batch

**Goal:** get figures *and* tables for many trials at once — as one zip from the
app, or as a scripted step in a pipeline — with the files landing where your
project expects them rather than where the tool guessed.

**You need:** the bundled demo. HTML figures and every table need no browser;
PNG / SVG / PDF do.

!!! tip "Static image export needs a browser"
    Interactive **HTML** export is browser-free. **PNG / SVG / PDF** go through
    [Kaleido](https://github.com/plotly/Kaleido), which drives a headless
    Chrome — run `plotly_get_chrome -y` once. Batch exports keep *one* warm
    browser across trials, so the cost is paid at the start of the run.

---

## 1. Decide the scope first

A batch is defined by the trials it covers, and that is the setting people get
wrong. Two of the choices look identical until a filter is active:

| Scope | Means |
| --- | --- |
| **All** | Every trial in the loaded dataset, **ignoring** the sidebar *Filter trials* panel. |
| **All filtered trials** | Exactly what the sidebar filter currently leaves — the default. |
| **All trials of one participant** | One reader, every trial. |
| **All trials of one text** | One text, every reader of it. |

The app prints the count (*"**24** of **24** trials will be exported"*) before
you commit, which is the cheapest sanity check available. Headlessly, the
equivalent is passing the `combos` frame you actually want.

---

## 2. Run the batch

=== "In the app"

    **Export** subtab → scroll past *This trial* to **Multiple trials**.

    1. **Scope** — the radio above, plus a participant / text selector when the
       scope needs one, and the live count.
    2. **Figures** — pick formats as pills: **PDF · SVG · PNG · HTML** (PDF by
       default). PNG adds a **PNG scale** stepper (1–4; 2 = retina, 4 = poster).
    3. **Also include** —
        - **Separable layers**: one file per layer (word boxes, fixations,
          saccades, heatmap, labels, stimulus image) under `layers/`, for
          restyling in Illustrator / Inkscape. See
          [figure for a paper → separable layers](figure-for-a-paper.md#5-separable-layers).
        - **Plot config (JSON)** (on by default): a snapshot of every plot
          setting, so the batch can be reproduced later.
        - **Tabular data**: *Fixations* · *Word measures* · *Mega-table*, plus a
          **csv / parquet / both** switch.
    4. **Naming & labels** — the path pattern and the optional on-figure title
       and caption (§3).
    5. **Build export**, watch the progress bar, then **Download zip**. Trials
       that failed are listed in an *Export warnings* expander rather than
       silently dropped.

    The figures use the settings from the control rail as they are right now, so
    style the on-screen figure first and export second.

=== "Python"

    The same code path, minus Streamlit:

    ```python
    import io
    import zipfile

    import scanpath_studio as sps
    from scanpath_studio.export import ExportOptions, bulk_export

    words, fixations = sps.load_sample_data()
    combos = sps.list_trials(words, fixations)

    options = ExportOptions(
        include_pdf=False, include_svg=False, include_png=False,
        include_html=True,          # browser-free
        include_measures=True,
        include_mega_table=True,
        table_format="csv",
        scope="participant",
        scope_participant="l37_1129",
    )

    zip_bytes, progress = bulk_export(
        combos, words, fixations,
        canvas_width=2560, canvas_height=1440,
        base_font_size=16, font_family="monospace",
        x_field="x", y_field="y",
        settings=dict(show_heatmap=False),
        options=options,
    )

    print(f"{progress.finished_trials} trials, {len(zip_bytes) / 1e6:.1f} MB, "
          f"errors={progress.errors}")
    zipfile.ZipFile(io.BytesIO(zip_bytes)).extractall("export")
    ```

    ```text
    12 trials, 0.3 MB, errors=[]
    ```

    Two things about the signature:

    - `settings` is the figure styling, and **every key has a default** — pass
      only what you want to change. It mirrors the control rail
      (`show_heatmap`, `show_order`, `saccade_color_mode`, `fixation_opacity`, …).
    - `progress_callback` is called with an `ExportProgress` after each trial
      (`finished_trials`, `bytes_written`, `errors`) — that is what drives the
      app's progress bar, and it is how you print one in a script.

=== "CLI"

    There is no batch flag: `render` draws **one** trial per invocation. For a
    scripted batch, loop over `--list-trials`, which prints to stdout while
    progress messages go to stderr:

    ```bash
    scanpath-studio render --sample --list-trials | tail -n +2 | while read -r pid tid; do
        scanpath-studio render --sample -p "$pid" -t "$tid" \
            --no-heatmap -o "out/${pid}__${tid}.html"
    done
    ```

    Two costs to know about: each invocation reloads the data, and each
    PNG/SVG/PDF cold-starts a headless Chrome — the app's batch exporter reuses
    one warm browser across the whole run. For a large corpus, prefer the Python
    loop in
    [run it headless](run-it-headless.md#3-render-a-whole-corpus), or
    `bulk_export` above.

---

## 3. Make the files land where you want them

By default every artifact goes to

```text
per_trial/{participant_id}__{trial_id}/{artifact}.{ext}
```

`{artifact}` is the file's role (`figure`, `fixations`, `measures`,
`plot_config`, or a layer name) and `{ext}` its format; every other placeholder
comes from the trial's own row — `{participant_id}`, `{trial_id}`, `{text_id}`,
plus `{n_fixations}`, `{n_words}`, `{reading_time_s}`. A `/` makes a folder. So

```text
figures/{text_id}/{participant_id}.{ext}
```

drops a batch straight into an existing per-text folder structure. In the app
the pattern is validated **and previewed against the first trial in scope as you
type** — a typo found after a 200-trial render is a typo found in the worst
possible place. Headlessly it is `ExportOptions(path_pattern=...)`.

Two patterns can collide (one that omits the trial id, say); colliding names are
disambiguated rather than silently overwriting each other.

### Provenance on the figure itself

**Title & caption on the figure** renders a title and caption *into* the
exported image, using the same placeholders:

| | Default pattern |
| --- | --- |
| Title | `{participant_id} · {trial_id}` |
| Caption | `{text_id} · {n_fixations} fixations · {settings}` |

`{settings}` expands to a summary of the settings that produced the figure. Both
are also recorded in `plot_config.json`. The plot is not shrunk to make room —
the figure grows. A figure pulled into a slide otherwise loses its provenance
immediately; this is the cheapest way to keep it.

---

## 4. What's in the zip

```text
scanpath_export_<timestamp>.zip
├─ README.md                       ← generation time, citation, data dictionary
├─ per_trial/
│  └─ l37_1129__l37_1129_2_1_1_Ele_r0/
│     ├─ figure.html               (and/or .pdf / .svg / .png)
│     ├─ layers/                   (only with Separable layers)
│     ├─ plot_config.json
│     ├─ fixations.csv
│     └─ measures.csv
└─ aggregate/
   ├─ all_fixations.csv
   └─ all_measures.csv
```

- The **mega-table** is the `aggregate/` pair: every selected trial's fixations
  and per-word measures concatenated into one long table each. Ticking it gives
  you **both** files, and their paths are fixed — the path pattern applies to
  per-trial artifacts only.
- **Measures need the words table.** A fixations-only trial exports its
  fixations and its figure but no `measures.csv`.
- A trial with neither words nor fixations is skipped and reported in the
  warnings, not silently dropped.
- An `image_path` column in an exported table is reduced to the file's
  basename, so a zip you share doesn't carry your directory layout.

---

## 5. Before you run it on a real corpus

- **Do a scoped dry run first.** One participant, HTML only — the whole shape of
  the output is visible in seconds, and a wrong path pattern costs nothing to
  find.
- **HTML for review, vector for the paper.** PDF / SVG are the ones to keep; PNG
  only when a raster is required, at scale 3+.
- **The batch does not apply drift correction.** Correction is a property of the
  on-screen figure; the batch exporter rebuilds each figure from the recorded
  coordinates. See
  [line assignment → what the correction reaches](line-assignment.md#4-what-the-correction-reaches).
- **Keep `plot_config.json`.** It is the difference between "we exported some
  figures" and a batch you can rebuild in six months.

---

## Next

- Style the figure before you batch it →
  **[Produce a figure for a paper](figure-for-a-paper.md)**
- Script the whole pipeline → **[Run it headless from a script](run-it-headless.md)**
- Chrome / Kaleido problems → **[Export & troubleshooting](../export-troubleshooting.md)**
