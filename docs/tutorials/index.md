# Tutorials

Six walkthroughs, each following one task from start to finish. Unless a
tutorial says otherwise, it runs on the bundled demo.

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

- :material-format-align-middle:{ .lg .middle } **[Correct vertical drift](line-assignment.md)**

    ---

    Assign fixations to text lines: compare the ten algorithms on your own
    trial, apply one, and know what it does and doesn't change.

    *~10 minutes · works on the bundled demo*

- :material-folder-zip:{ .lg .middle } **[Export a batch](batch-export.md)**

    ---

    Figures and tables for many trials in one zip — scoping, file naming, and
    the same run as a script.

    *~10 minutes · needs Chrome for PNG/SVG/PDF*

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
