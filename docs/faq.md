# FAQ

## Loading data

### The fixations don't line up with the text

Words and fixations must use the same pixel coordinates and share trial IDs.
If the fixations are shifted, mirrored or scaled against the words, the two
tables are in different coordinate frames — a different origin, unit or offset
— and no setting here fixes that; convert one of them
([Data format → Units](data-format.md#tables)). If the alignment is right but
the figure is framed or sized wrongly, the recording screen size is: set the
resolution of the monitor used in the experiment under :material/database: **Data Management → :material/edit: Edit dataset → Recording
setup**. *Estimate from my data* only gives a lower bound.

### The text is too big or too small

Text is drawn to scale from the word boxes and the recording screen size. Set
the real resolution (see above); for OneStop it is 2560×1440. In Python, pass
`canvas_size=(2560, 1440)`.

### A column was detected wrongly

The app guesses columns from their names. Pick the right one under
:material/database: **Data Management → :material/edit: Edit dataset**, or pass `word_schema` / `fix_schema` to
[`load_scanpath_data`][scanpath_studio.api.load_scanpath_data].

### Can I load only one table?

Yes. A words table alone shows the text and any reading measures it carries; a
fixations table alone shows gaze positions without text. Most features need
both.

### My zip file is refused as too large

The app limits how far a `.zip` may decompress (32 GB per file, 64 GB in
total). The error names the setting that raises it, for example
`SCANPATH_ZIP_MAX_MEMBER_GB=64 scanpath-studio`.

## Results

### Does the app compute reading measures?

No. Corpus Analysis and Export show the measures your interest-area report
provides, as they are; [Computations](computations.md) defines each one.

### Does :material/cleaning_services: Filter change my data?

No. It changes only what the figure draws. Your tables and measures stay as
they are.

## Export and sharing

### PDF, GIF or MP4 export fails { #export-fails }

These formats need Chrome, Chromium or Edge installed on the computer running
the app. Installing one is enough. With a pip install you can instead run
`plotly_get_chrome -y` once. HTML, and the current figure's PNG and SVG, work
without a browser.

### Can someone else open my share link?

Yes, but the link does not contain your uploaded data, so they need to load the
same dataset first. The bundled demo opens directly, and a public corpus opens
if they have it set up.

## Privacy and storage

### Where does my data go?

When you run it locally or as the desktop app, nowhere: it stays on your
computer. There are no accounts and no analytics. Don't upload identifiable
data to the online demo. See [Privacy](privacy.md).

### Will a refresh lose my work?

Not on a local or desktop install: the app keeps a recovery copy of your
datasets and settings (when it listens only on this computer, as
`scanpath-studio` and the desktop app do — see [Privacy](privacy.md)), and
**:material/database: Data Management → Saved on this computer** shows what it holds. The online demo keeps nothing, and says so after your first upload,
so export your annotations and settings before you leave
([what to back up](guides/outputs-sharing.md#back-up-your-work)).

If one saved dataset's files go missing or are damaged, the rest of the
session still comes back. The app names the dataset that didn't, keeps its
saved copy as it is, and offers **Retry** and **Remove from cache**. Saved
metadata tables that can't be read are kept the same way. If the
whole recovery copy can't be read, the app opens without it and stops saving
over it until you retry or clear it.

### How do I turn the recovery copy off, or delete it?

Start the app with `scanpath-studio run --no-persist` to save nothing. To
delete what is saved, close the app and run `scanpath-studio cache --clear`.
See [Recovery cache](cli.md#recovery-cache).

## Citing

### How do I cite Scanpath Studio?

See [Cite](cite.md) for BibTeX and APA entries, and for the datasets you used.
