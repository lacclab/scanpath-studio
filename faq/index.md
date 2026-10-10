# FAQ

## Loading data

### The fixations don't line up with the text

Words and fixations must use the same pixel coordinates and share trial IDs. If the fixations are shifted, mirrored or scaled against the words, the two tables are in different coordinate frames — a different origin, unit or offset — and no setting here fixes that; convert one of them ([Data format → Units](https://lacclab.github.io/scanpath-studio/data-format/#tables)). If the alignment is right but the figure is framed or sized wrongly, the recording screen size is: set the resolution of the monitor used in the experiment under **Data Management → Edit dataset → Recording setup** (**Screen → I know it**). *Estimate from my data* only gives a lower bound.

### The text is too big or too small

Text is drawn to scale from the word boxes and the recording screen size. Set the real resolution (see above); for OneStop it is 2560×1440. In Python, pass `canvas_size=(2560, 1440)`. If it is still off, set the line spacing (how far apart the lines are, in font sizes) under **Recording setup → Text size → Fit to word boxes**, or `line_spacing=` in Python.

### A column was detected wrongly

The app guesses columns from their names. Pick the right one under **Data Management → Edit dataset**, or pass `word_schema` / `fix_schema` to load_scanpath_data.

### Can I load only one table?

Yes. A Words table alone shows the text and any reading measures it carries; a fixations table alone shows gaze positions without text. Most features need both. The same holds trial by trial: when the two tables cover different trials, every trial either one has is listed, and drawn with what it has.

### Can I open PoTeC or OneStop in the online demo?

No. The online demo has only the bundled demo data, and it doesn't download corpora. In the desktop app or a pip install, each public corpus downloads once, with one click, and stays on your computer.

### My zip file is refused as too large

The app limits how far a `.zip` may decompress (32 GB per file, 64 GB in total). The error names the setting that raises it, for example `SCANPATH_ZIP_MAX_MEMBER_GB=64 scanpath-studio`.

## Results

### Does the app compute reading measures?

No. Corpus Analysis and Export show the measures your interest-area report provides, as your eye-tracking software defines them; [Computations](https://lacclab.github.io/scanpath-studio/computations/index.md) gives how Scanpath Studio would compute each.

### Does Filters & highlights change my data?

No. It changes only what the figure draws. Your tables and measures stay as they are.

## Export and sharing

### PDF, GIF or MP4 export fails

These formats need Chrome, Chromium or Edge installed on the computer running the app. Installing one is enough. With a pip install you can instead run `plotly_get_chrome -y` once. HTML, and the current figure's PNG and SVG, work without a browser.

### Can someone else open my share link?

Yes, but the link does not contain your uploaded data, so they need to load the same dataset first. The bundled demo opens directly, and a public corpus opens if they have it set up.

## Privacy and storage

### Where does my data go?

When you run it locally or as the desktop app, nowhere: it stays on your computer. There are no accounts and no analytics. Don't upload identifiable data to the online demo. See [Privacy](https://lacclab.github.io/scanpath-studio/privacy/index.md).

### Will a refresh lose my work?

Not on a local or desktop install: the app saves your datasets and settings on this computer (when it listens only on this computer, as `scanpath-studio` and the desktop app do — see [Privacy](https://lacclab.github.io/scanpath-studio/privacy/index.md)), and **Data Management → Saved on this computer** shows what it holds. The online demo keeps nothing, and says so after your first upload, so export your annotations and settings before you leave ([what to back up](https://lacclab.github.io/scanpath-studio/guides/outputs-sharing/#back-up-your-work)).

If one saved dataset's files go missing or are damaged, the rest of the session still comes back. The app names the dataset that didn't, keeps its saved copy as it is, and offers **Retry** and **Remove saved copy**. Saved metadata tables that can't be read are kept the same way. If the whole saved copy can't be read, the app opens without it and stops saving over it until you retry or clear it.

### How do I stop saving, or delete what is saved?

Start the app with `scanpath-studio run --no-persist` to save nothing. To delete what is saved and start over, use **Clear what is saved…** under **Saved on this computer**, or close the app and run `scanpath-studio cache --clear`. See [Recovery cache](https://lacclab.github.io/scanpath-studio/cli/#recovery-cache).

## Help and versions

### Where do I ask a question or report a bug?

Ask in [Discussions → Q&A](https://github.com/lacclab/scanpath-studio/discussions/categories/q-a). Report a bug as a [GitHub issue](https://github.com/lacclab/scanpath-studio/issues/new?template=bug_report.md), with the version, your operating system and how you run the app (pip, the desktop app or the online demo). **Help → About** shows the version and links both; on the command line, `scanpath-studio --version`.

### Will my links, settings and scripts work after an update?

Scanpath Studio is in beta, so they may not. Until 1.0, any release may change the app, its share links and saved settings, the Python API and the CLI. The [Changelog](https://lacclab.github.io/scanpath-studio/changelog/index.md) lists every change. To reproduce a result exactly, note the version you used and install that one: `pip install scanpath-studio==<version>`.

## Citing

### How do I cite Scanpath Studio?

See [Cite](https://lacclab.github.io/scanpath-studio/cite/index.md) for BibTeX and APA entries, and for the datasets you used.
