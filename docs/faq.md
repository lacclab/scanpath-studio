---
description: "Answers to common questions about Scanpath Studio: fixations that do not line up with the text, wrongly detected columns, reading measures, export, privacy and citing."
---

# FAQ

## Loading data

### The fixations don't line up with the text

Words and fixations must use the same pixel coordinates and share trial IDs.
If the fixations are shifted, mirrored or scaled against the words, the two
tables use different coordinates: a different origin, unit or offset. No
setting in the app fixes that, so convert one of the tables
([What your data needs → Files and units](guides/loading-data/index.md#tables)).

If the fixations sit on the words but the figure is framed or sized wrongly,
set the screen resolution of the monitor used in the experiment. Open
:material/database: **Data Management** → :material/edit: **Edit dataset** →
**Recording setup** and choose **Screen** → **I know it**. *Estimate from my
data* gives only a lower bound.

### The text is too big or too small

The text is drawn to scale from the word boxes and the recording screen size.
Set the real resolution first (see above). For OneStop it is 2560×1440, and in
Python you pass `canvas_size=(2560, 1440)`. If the text is still off, set the
line spacing under **Recording setup** → **Text size** → **Fit to word boxes**,
or `line_spacing=` in Python. Line spacing is the distance between lines, in
font sizes.

### A column was detected wrongly

The app guesses columns from their names. Pick the right one under
:material/database: **Data Management** → :material/edit: **Edit dataset**, or
pass `word_schema` / `fix_schema` to
[`load_scanpath_data`][scanpath_studio.api.load_scanpath_data].

### Can I load only one table?

Yes. A Words table alone shows the text and any reading measures it carries. A
Fixations table alone shows the fixations without the text. A Raw gaze table
can also be the only table. Most features need both words and fixations. When
your tables cover different trials, every trial that any of them has is listed
and drawn with the layers it has.

### Can I open PoTeC or OneStop in the online demo?

No. The online demo has only the bundled demo, and it doesn't download public
datasets. In the desktop app or a pip install, each public dataset downloads
once, with one click, and stays on your computer.

### My zip file is refused as too large

The app limits how far a `.zip` may decompress: 32 GB per file and 64 GB in
total. The error names the setting that raises the limit, for example
`SCANPATH_ZIP_MAX_MEMBER_GB=64 scanpath-studio`.

## Results

### Does the app compute reading measures?

No. Corpus Analysis and Export show the reading measures in your Words table,
as your eye-tracking software defines them
([Reading measures](guides/loading-data/index.md#reading-measures)).

### Does :material/filter_list: Filters & highlights change my data?

No. It changes only what the figure draws. Your tables and measures stay as
they are.

## Export and sharing

### Image or video export fails { #export-fails }

These exports need Chrome, Chromium or Edge on the computer that runs Scanpath
Studio: PDF, GIF and MP4 files, static images from Python or the CLI, and
export bundles with images. Installing one of these browsers is enough. With a
pip install you can instead run `plotly_get_chrome -y` once. HTML files, and
the current figure's PNG and SVG, work without a browser.

### Can someone else open my share link?

Yes, but the link does not contain your data, so they need to load the same
dataset first. The bundled demo opens directly. A public dataset opens if they
have it set up.

## Privacy and storage

### Where does my data go?

When you run Scanpath Studio locally or as the desktop app, your data stays on
your computer. There are no accounts, and `scanpath-studio` and the desktop app
send no usage statistics. Don't upload identifiable data to the online demo.
See [Privacy](about.md#privacy).

### Can I share a figure without showing the text?

Yes. Turn on :material/article: **Stimulus** ▾ → **Text** → **Redact**. Each
word becomes a rounded block over its letters, so the figure keeps the layout
of the text but none of its words. Hovers and saved HTML hide the words too.
Also turn off the stimulus image, since it shows the screen as it was. On the
command line, use `render --redact-text`, and in Python `redact_text=True`. The
data tables and exported tables still hold the words.

### Will a refresh lose my work?

Not on a local or desktop install. When the app listens only on this computer,
as `scanpath-studio` and the desktop app do, it saves your datasets and
settings there. :material/database: **Data Management** → :material/history:
**Saved on this computer** shows what it holds. The online demo keeps nothing
and says so after your first upload, so export your annotations and settings
before you leave ([what to back up](guides/scanpath-visualization/index.md#back-up-your-work)).

If the files of one saved dataset go missing or are damaged, the rest of the
session still comes back. The app names the dataset it could not restore,
keeps that saved copy unchanged, and offers **Retry** and **Remove saved
copy**. Saved metadata tables that can't be read are kept the same way. If the
whole saved copy can't be read, the app opens without it and stops saving over
it until you retry or clear it.

### How do I stop saving, or delete what is saved?

Start the app with `scanpath-studio run --no-persist` to save nothing. To
delete what is saved and start over, use **Clear what is saved…** under
**Saved on this computer**, or close the app and run
`scanpath-studio cache --clear`. See [Recovery cache](cli.md#cache).

## Help and versions

### Where do I ask a question, report a bug or send feedback?

:material/help: **Help** → :material/feedback: **Send feedback** links each
kind of feedback to its page on GitHub: **Report a bug**, **Suggest a
feature**, **Share an idea** and **Ask a question**. It also shows the version
and system details a bug report needs, ready to copy. The app sends nothing.
You submit each one on GitHub yourself.

Ask questions in
[Discussions → Q&A](https://github.com/lacclab/scanpath-studio/discussions/categories/q-a).
Report a bug as a
[GitHub issue](https://github.com/lacclab/scanpath-studio/issues/new?template=bug_report.md),
with the version, your operating system and how you run the app (pip, the
desktop app or the online demo). :material/help: **Help** → :material/info:
**About** shows the version and links to both. On the command line, run
`scanpath-studio --version`.

### How do I update Scanpath Studio? { #updating }

Open :material/help: **Help** → :material/info: **About** →
:material/update: **Check for updates**. In the desktop app, choose
**Update & restart**. For a Python install, run:

```bash
pip install -U scanpath-studio
```

### Will my links, settings and scripts work after an update?

Not necessarily. Until version 1.0, any release may change the app, its share
links and saved settings, the Python API and the CLI. The
[changelog](https://github.com/lacclab/scanpath-studio/blob/main/CHANGELOG.md)
lists the changes in each release. To reproduce a result, note the version you
used and install that one: `pip install scanpath-studio==<version>`.

## Citing

### How do I cite Scanpath Studio?

See [Cite Scanpath Studio](about.md#cite-scanpath-studio) for BibTeX and APA
entries, and [Bundled demo](about.md#bundled-demo) for the bundled demo's
source.
