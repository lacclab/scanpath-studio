# All controls

Every control on the :material/route: **Scanpath** page, where it is and what it
does — in the order you meet them on screen. Search this page (++ctrl+f++, or
++cmd+f++ on a Mac) for the thing you want to change, such as *colors*,
*legends* or *axes*.

The page has two sets of controls:

- The **trial control bar**, above the plot, decides *what* you see: the
  dataset, the trial, and which trials are in the list.
- The **plot controls**, the column on the right, decide *how* it is drawn:
  each layer of the figure, its colors and sizes, and the figure as a whole.

The tabs under the plot then work with the trial on screen: annotate it, read
its context, compare it, export it or share it. For how the parts fit
together, see the [Scanpath visualization](index.md) guide.

## Trial control bar

<a class="sps-ctl sps-ctl--wide" href="../../../assets/screenshots/controls/trial-row.webp" title="Open full size"><img src="../../../assets/screenshots/controls/trial-row.webp" alt="The trial control bar" loading="lazy"></a>

<a class="sps-ctl sps-ctl--menu" data-label="Show chips menu" href="../../../assets/screenshots/controls/chips.webp" title="Open full size"><img src="../../../assets/screenshots/controls/chips.webp" alt="The chips menu, opened from the pencil button" loading="lazy"></a>

The bar above the plot: pick a dataset and a trial, step through the trials,
and narrow, sort or label the list.

| Control | What it does |
| --- | --- |
| **Select dataset** | The dataset the page shows. |
| **+** → **Create manually** | Add a dataset by manual illustration: write a text and place its fixations by hand. |
| **+** → **Import files** | Add a dataset from data tables: upload your own tables as a new dataset. |
| **Select trial** | The trial to show. Click it and type to narrow the list. |
| **Trial** slider | Scrub through the trials in the list. |
| **◀ ▶** | The previous or next trial. |
| **⇅** → **Sort trials by** | Reorder the trial list by a statistic (such as reading time), a participant, text or condition field, or a column of a metadata table you attached. |
| **⇅** → **Descending** | Reverse that order. |
| :material/filter_alt: → **Text** / **Participant** | Keep only these texts or participants. |
| :material/filter_alt: → *a field of your data* | Keep only trials with these values, or, for a number, in this range. |
| :material/filter_alt: → **By participant** / **By trial** / **By text** | The same, for the columns of an attached metadata table. |
| :material/filter_alt: → **Favorites only** | Keep only starred trials. |
| :material/filter_alt: → **With any of these tags** | Keep only trials with any of these tags. |
| :material/filter_alt: → **Excluding tags** | Hide trials with any of these tags, such as `exclude`. |
| :material/filter_alt: → **Clear all filters** | Reset every filter in the panel. |
| **✏️** → **Show chips above the plot** | Show or hide the row of facts about the trial above the plot. |
| **✏️** → field lists | Drag fields between *Shown* and *Available* to choose the chips. *Available* holds every field with one value per trial: participant, text and condition columns, the columns of any metadata table you attached, and statistics such as reading time and fixation count. |
| **✏️** → field colors | Give a chip a highlight color; its **✕** puts it back to the default gray. |
| **✏️** → **Refresh fields** | Look again for which fields are trial-level. |
| **Screen** and its **◀ ▶** | On a trial recorded over several screens: the screen to show. |

## Plot controls

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/plot-controls.webp" title="Open full size"><img src="../../../assets/screenshots/controls/plot-controls.webp" alt="The Plot controls column" loading="lazy"></a>


The column on the right of the plot. At the top, the modes and designs change
the whole figure at once. Under them, each layer of the figure has a row of its
own: the switch turns the layer on or off, and the **▾** beside it opens that
layer's settings, described below one menu at a time. The last two rows,
**Filters & highlights** and **Figure & canvas**, cover the figure as a whole.
A greyed-out control says why when you hover over it.

### :material/movie: Animate: play the reading as a video

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/animate.webp" title="Open full size"><img src="../../../assets/screenshots/controls/animate.webp" alt="The Animate menu" loading="lazy"></a>

The **Animate** switch turns the figure into an animation, a video of the
reading played back fixation by fixation, with play and pause buttons and a
time slider under the plot. Its **▾** holds:

| Control | What it does |
| --- | --- |
| **Replay** → **Speed** | How fast the video plays, from ×0.25 to ×8: ×1 is the reader's own pace, ×2 twice as fast, ×0.5 half as fast. |
| **Replay** → **Autoplay** → **On load** | Start playing the animation automatically as soon as the plot is shown; otherwise it starts only when you click play. |
| **Replay** → **Duration** | For information only: the trial's reading time, and how long the video runs at this speed. |
| **Frames** → **Quality** | How smooth the video is: more frames play more smoothly but take longer to build. **Custom** sets the two below by hand. |
| **Frames** → **Every** | Reading time between frames, in ms. |
| **Frames** → **Limit** | The most frames a video gets; a long trial gets wider frame steps to fit. |
| **Frames** → **Result** | For information only: how many frames this trial's video has, and how far apart they ended up. |

### :material/compare: Compare

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/compare-menu.webp" title="Open full size"><img src="../../../assets/screenshots/controls/compare-menu.webp" alt="The Compare menu" loading="lazy"></a>

The **Compare** switch shows a second scanpath, B, beside or over this one
(pick it in the [trial control bar](#trial-control-bar), above the plot);
its **▾** holds:

| Control | What it does |
| --- | --- |
| **View** | **Overlay** both scanpaths, or give each its own panel, **Side by side** or **Top & bottom**. |
| **Stimulus from** | In an overlay, whose word boxes and text are drawn: both, A's or B's. |
| **Label A** / **Label B** | Each scanpath's name in the legend, written with fields such as `{participant_id}`; empty uses the automatic one. |
| **Available fields** | The fields a label can use. |
| **Step** → **A and B together** | ◀ ▶ move both scanpaths at once. |

### :material/palette: Design presets and palette

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/designs.webp" title="Open full size"><img src="../../../assets/screenshots/controls/designs.webp" alt="Design presets, My designs open on two saved designs, and the palette" loading="lazy"></a>

Restyle the whole figure in one click, with a ready-made design or one of your
own saved designs:

| Control | What it does |
| --- | --- |
| **Scanpath** / **Heatmap** / **Illustration** | Ready-made designs: a classic scanpath, a word-box heatmap, or a clean schematic. |
| **Custom** | Your most recent hand-made settings. |
| **My designs** | Your saved designs: click one to apply it; the pencil renames it and the bin deletes it. |
| **My designs** → save button | Save the settings on screen as a named design, to apply again later in one click. |
| **My designs** → **Export** / **Import** | Download your designs as a file, or load a file of designs: share a look with co-authors and partners, reproduce a figure exactly, or move your designs to another computer. |
| **Palette** | A color scheme for the whole figure, such as colorblind-safe or print. |

### :material/blur_on: Fixations

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/fixations.webp" title="Open full size"><img src="../../../assets/screenshots/controls/fixations.webp" alt="The Fixations menu" loading="lazy"></a>


The **Fixations** switch draws the fixation markers; its **▾** holds:

| Control | What it does |
| --- | --- |
| **Marker** → **Color** | What decides each marker's color. **One color** paints them all alike. Pick a number column, such as fixation duration or surprisal, and the markers follow a color scale: with the default blues, longer fixations show darker. Pick a category, such as the line, the fixation pass or a condition, and each value gets its own color, with a legend. |
| **Marker** → color box | The single color every marker wears. |
| **Marker** → **Shape** | Marker shape: circle, square, diamond, triangle, star… |
| **Marker** → **Size** | The smallest and largest marker diameter, in px. |
| **Marker** → **Scale** | How duration sets marker size: square root, linear, log, or relative to the trial. |
| **Marker** → **Durations** | The durations that get the smallest and the largest marker. |
| **Marker** → **Opacity** | Marker opacity; lower it to see overlapping fixations. |
| **Marker** → **Outline** | The width and color of the ring round each marker. |
| **Color bar** → **Show** | The color scale's bar, when markers are colored by a number. |
| **Color bar** → orientation, **Angle**, **Size**, **Thickness**, **Length** | The bar's direction, tick-label angle and size, and its thickness and length. |
| **Fixation index** → **Show** | Number each fixation in reading order. |
| **Fixation index** → color, **Size** | The numbers' color and size. |
| **Snap** → **To line** | Move each fixation onto its line of text — a schematic, labelled *Illustration*. |
| **Snap** → **Position** | Where on its line a snapped fixation sits. |

### :material/arrow_outward: Saccades

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/saccades.webp" title="Open full size"><img src="../../../assets/screenshots/controls/saccades.webp" alt="The Saccades menu" loading="lazy"></a>


The **Saccades** switch draws the lines between fixations; its **▾** holds:

| Control | What it does |
| --- | --- |
| **Line** → **Color** | One color; forward and regression apart; or by type (forward, skip, refixation, return sweep, regression). |
| **Line** → color box | The single saccade color. |
| **Line** → type colors | With **By type**: each type's color. |
| **Line** → **Style** | Solid, dashed, dotted or dash-dot lines. |
| **Line** → **Width** | Line thickness. |
| **Line** → **Opacity** | Line and arrow opacity; lower it to bring the fixations forward. |
| **Shape** | Straight lines, or arcs over the text. |
| **Direction arrows** → **Show** | An arrowhead on each saccade. |
| **Direction arrows** → **Arrow size** | Arrowhead size. |

### :material/article: Stimulus

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/stimulus.webp" title="Open full size"><img src="../../../assets/screenshots/controls/stimulus.webp" alt="The Stimulus menu" loading="lazy"></a>


The **Stimulus** switch draws the text and the stimulus image; its **▾** holds:

| Control | What it does |
| --- | --- |
| **Text** → **Show** | Draw the reading text. |
| **Fit** → **Fit to word boxes** | Size the text to fill its word boxes. |
| **Spacing** | How far apart the lines are, in font sizes. |
| **Size** | The text size, in px or pt. |
| **Font** | The text's typeface; *Other…* takes any font name. |
| **Color** → text color | The reading text's color. |
| **Background** | The plot's background color: a preset, or any color in the box beside it. |
| **Highlight** → **Show** | Mark words, such as the answer span. |
| **Highlight** → **Highlight words by** | The true/false column that picks the words. |
| **Style** | Color the highlighted words, or draw a border round them; and the color. |
| **Image** → **Show** | Draw the stimulus image under the scanpath. |
| **File** | Upload a stimulus image. |
| **Opacity** | Image opacity; lower it so the scanpath reads over it. |
| **Offset** → **X** / **Y** | Nudge the image, in px. |
| **Scale** | Scale the image so its text matches the word boxes. |

### :material/crop_square: Word boxes

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/word-boxes.webp" title="Open full size"><img src="../../../assets/screenshots/controls/word-boxes.webp" alt="The Word boxes menu" loading="lazy"></a>


The **Word boxes** switch draws each word's interest area; its **▾** holds:

| Control | What it does |
| --- | --- |
| **Box** → **Line** color | The color of each word box's outline. |
| **Box** → **Line** opacity | The outline's opacity; 0 hides it. |
| **Box** → **Fill** color | The color inside each box. |
| **Box** → **Fill** opacity | How strongly the fill shows; 0 draws outlines only. |

### :material/local_fire_department: Heatmap

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/heatmap.webp" title="Open full size"><img src="../../../assets/screenshots/controls/heatmap.webp" alt="The Heatmap menu" loading="lazy"></a>


The **Heatmap** switch shows where reading concentrated; its **▾** holds:

| Control | What it does |
| --- | --- |
| **Style** | Word boxes, a smooth interpolated map, or fixation density. |
| **Blur** | How far each fixation spreads, for the smooth styles; **Auto** picks it. |
| **Color** → **By** | What the heat counts: total fixation duration, or the number of fixations. |
| **Color** → **Colors** | The color scale. |
| **Scale** | Linear or log scaling. |
| **Range** | The values the color scale spans; **Auto** fits the trial. |
| **Opacity** | Heatmap opacity; **Auto** uses each style's own. |
| **Color bar** → **Show**, orientation, **Angle**, **Size**, **Thickness**, **Length** | The heatmap's color bar, as for fixations. |

### :material/grain: Raw gaze

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/raw-gaze.webp" title="Open full size"><img src="../../../assets/screenshots/controls/raw-gaze.webp" alt="The Raw gaze menu" loading="lazy"></a>


The **Raw gaze** switch draws the gaze samples as recorded; its **▾** holds:

| Control | What it does |
| --- | --- |
| **Marker** → **Color** | The samples' color. |
| **Marker** → **Size** | Sample marker size. |
| **Marker** → **Opacity** | Sample opacity. |

### :material/filter_list: Filters & highlights

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/filters.webp" title="Open full size"><img src="../../../assets/screenshots/controls/filters.webp" alt="The Filters & highlights menu" loading="lazy"></a>


Which fixations and saccades are drawn, and which stand out:

| Control | What it does |
| --- | --- |
| **Fixations** → **Index range** | Draw only the fixations in this range of the reading order. |
| **Fixations** → **All trials** | Keep that range when you move to another trial. |
| **Short** / **Long** | Fixations shorter or longer than a threshold (ms): **Highlight** marks them, **Discard** hides them. |
| **Out of bounds** | Fixations in no word box: highlight or discard them. |
| **Blink** | Fixations at or next to a blink (needs a blink column): highlight or discard them. |
| marker and color | The marker and color of each highlighted kind. |
| **Saccades** → **Types** | Draw only saccades of these types. |

### :material/aspect_ratio: Figure & canvas

<a class="sps-ctl sps-ctl--menu" href="../../../assets/screenshots/controls/figure-canvas.webp" title="Open full size"><img src="../../../assets/screenshots/controls/figure-canvas.webp" alt="The Figure & canvas menu" loading="lazy"></a>


The figure as a whole:

| Control | What it does |
| --- | --- |
| **Frame** → **Crop to data** | Show only the part of the screen with data, instead of the whole screen. |
| **Margin** | Space round the data when cropping; **Auto** uses 5%. |
| **Border** → **Show**, color | The line round the plot area, and its color. |
| **Grid** → **Show** | Pixel grid lines over the screen. |
| **Grid** → **Auto**, interval | The grid spacing, chosen for you or in px. |
| **Labels** | Grid label size. |
| **Axes** → **X** / **Y** | The fixation fields on the axes; anything but x / y draws a chart of the fixations alone. |
| **Illustration** → **Label** | When to label the figure *Illustration*: when a setting changes its geometry, always, or never. |
| **Illustration** → **Text** | That label's text. |
| **Title** → **Show**, text, **Size** | A line of text above the plot; `{field}` inserts a value of the trial. |
| **Caption** → **Show**, text, **Size**, color | A line of text below the plot. |
| **Hover** → **Words** / **Fixations** | The fields shown when hovering a word or a fixation. |
| **Legends** → **Show** | Draw this legend: Compare (A/B), Saccade types, Fixation colors, Size key or Text highlight. |
| **Legends** → **Position** | Where it sits: a corner, the middle of an edge, or down a side, outside or inside the plot. |
| **Legends** → **Arrangement** | Its items stacked or side by side. |
| **Legends** → **Text size** | Its text size, in px. |

### :material/restart_alt: Reset visualization

The button at the foot of the column.

| Control | What it does |
| --- | --- |
| **Reset visualization** | Reset every plot setting. Annotations, filters, data and the selected trial stay. |

## In Compare

<a class="sps-ctl sps-ctl--wide" href="../../../assets/screenshots/controls/compare-row.webp" title="Open full size"><img src="../../../assets/screenshots/controls/compare-row.webp" alt="Scanpath B's row in Compare" loading="lazy"></a>

With **Compare** on, scanpath B gets a row of its own, and several menus split
into a **Scanpath A** and a **Scanpath B** group.

| Control | What it does |
| --- | --- |
| **Dataset B** | The dataset scanpath B comes from. |
| **Trial B**, slider, **◀ ▶** | Scanpath B's trial: 📄 marks the same text, 👤 the same participant. |
| **⇅** on B's row | Sort scanpath B's candidates. |
| :material/filter_alt: on B's row | Filter scanpath B's trials, apart from A's. |
| **Fixations ▾** → **Scanpath A / B** → **Color**, **Size**, **Opacity** | Each scanpath's marker color, size range and opacity. |
| **Saccades ▾** → **Scanpath A / B** → **Color**, **Style**, **Width** | Each scanpath's lines. |
| **Word boxes ▾** → **Scanpath A / B** → **Line**, **Fill** | Each scanpath's word-box colors and opacities. |
| **Heatmap ▾** → **Scanpath A / B** → **Colors** | Each scanpath's heatmap color scale. |
| **Raw gaze ▾** → **Scanpath A / B** → **Color** | Each scanpath's sample color. |
| **Filters & highlights ▾** → **· B** groups | Scanpath B's own index range, fixation highlights and saccade types. |

## Under the plot

<a class="sps-ctl sps-ctl--wide" href="../../../assets/screenshots/controls/under-the-plot.webp" title="Open full size"><img src="../../../assets/screenshots/controls/under-the-plot.webp" alt="The tabs under the plot" loading="lazy"></a>

The tabs under the figure:

| Tab | Control | What it does |
| --- | --- | --- |
| **Annotations** | **Favorite** | Star the trial. |
| | **Tags** / **Add a tag** | Tag the trial, with an existing tag or a new one. |
| | **Notes** | A free-text note on the trial. |
| **Stimulus & context** | **Context fields** | Trial-level context to show, such as a title, a question or an answer. |
| | **Highlighted spans** | True/false word columns to tint in the text, each with a summary. |
| **Comparisons** | **Match field** | Show the other trials that share this trial's value of a field. |
| | **Columns** | Panels per row. |
| **Export** | **Download format** | Save the figure on screen as PNG, SVG, PDF or HTML — or a replay as HTML, GIF or MP4. |
| | **Width**, unit, **DPI** | The PNG's print size. |
| | **Trials to include** | Bundle this trial, the filtered trials, or all of them. |
| | **Formats** / **Tabular data** | The bundle's figure formats and data tables. |
| | **Separable layers** | Each visual layer as its own file, to stack in a vector editor. |
| | **Annotations (JSON)** / **Settings file (JSON)** | Add the annotations or the settings to the bundle. |
| | **File path pattern** | The file names inside the bundle. |
| | **Build export** | Build the bundle to download. |
| **Share** | **Link** | A link that reopens this trial with these settings. |
| | **Code** → **Flavour**, **Show every option** | The Python or command line that redraws the figure. |
| | **File** → **Download settings** / **Restore settings** | Save the settings to a file, or apply a saved one. |
