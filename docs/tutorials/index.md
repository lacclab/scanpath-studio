# Tutorials

The rest of the docs describe *what each control does*. These four walk a real
task from start to finish — every control name, CLI flag and Python call below
was run against the shipping app, so you can copy-paste your way through.

<div class="grid cards" markdown>

- :material-database-import:{ .lg .middle } **[Load your own data](load-your-own-data.md)**

    ---

    From an eye-tracker export to a working dataset — in the app's wizard and
    headlessly — plus the four checks that catch a bad load in 30 seconds.

    *~10 minutes · needs your own export (or follow along with the demo)*

- :material-account-multiple:{ .lg .middle } **[Compare two readers](compare-two-readers.md)**

    ---

    Two readings of the same paragraph, side by side and on one animation
    clock, then the same comparison as numbers you can put in a table.

    *~10 minutes · works on the bundled demo*

- :material-file-image:{ .lg .middle } **[Produce a figure for a paper](figure-for-a-paper.md)**

    ---

    A publication-ready scanpath: what to switch off, how to export vector
    output, and how to get separable layers for Illustrator / Inkscape.

    *~15 minutes · needs Chrome for PNG/SVG/PDF*

- :material-console:{ .lg .middle } **[Run it headless from a script](run-it-headless.md)**

    ---

    Render every trial in a corpus, dump the reading measures, and wire the
    whole thing into a reproducible analysis script or Makefile.

    *~15 minutes · Python or shell*

</div>

## Before you start

Every tutorial assumes the package is installed and the bundled demo loads:

```bash
pip install scanpath-studio
scanpath-studio                    # opens the app at http://localhost:8501
```

If that works you're set — a 3-participant [OneStop](../onestop.md) demo is
preloaded, and each tutorial says up front whether it runs on the demo or needs
your own export. Full install options (conda, source checkout, the desktop
build) are in [Getting started](../getting-started.md).

!!! tip "Static image export needs a browser"
    Interactive **HTML** export is browser-free. **PNG / SVG / PDF** (and GIF /
    MP4) go through [Kaleido](https://github.com/plotly/Kaleido), which drives a
    headless Chrome — run `plotly_get_chrome -y` once. Tutorials 3 and 4 need
    it; 1 and 2 don't.

## Where to go afterwards

| You want | Read |
| --- | --- |
| Every column name the loader recognises | [Data format](../data-format.md) |
| A mapping that went wrong | [Bring your own data](../bring-your-own-data.md) |
| Corpus-level questions (per text / per reader / groups) | [Corpus analysis](../corpus-analysis.md) |
| The full function signatures | [Python API](../api.md) |
| Every `render` flag | [CLI reference](../cli.md) |
| Short answers to recurring questions | [FAQ](../faq.md) |
