# Canal reading study

Three fictional readers each read “Rain fell” on a 640 × 360 pixel screen.
Reader p03 failed the calibration check before run-03. The annotation on that
reading carries the `exclude` tag. The cohort recipe excludes that tag and
requires two readers for each word. It uses the dwell times supplied in the
Words table.

## Recreate the results

With Scanpath Studio installed, run this from an empty folder to copy the
inputs and saved settings supplied with the package.

```sh
python -c "from importlib.resources import files; from shutil import copytree; copytree(files('scanpath_studio') / 'sample_data' / 'coauthor', 'canal-study')"
cd canal-study
```

The figure shows reader p02's run-02. Fixations are colored by duration on the
Blues scale, drawn at half opacity, and connected in reading order. The word
rectangles are visible and the fixation index numbers are hidden. Create the
self-contained HTML figure from the two raw CSVs.

```sh
scanpath-studio render --words words.csv --fixations fixations.csv --participant p02 --trial run-02 --canvas 640x360 --word-boxes --no-order --color-by duration_ms --fixation-colorscale Blues --fixation-opacity 0.5 -o panel.html
```

Rebuild the publication table from the source files and the reviewer's
annotations. The means should be 160 ms for “Rain” and 220 ms for “fell”,
with two contributing readers per word.

```sh
scanpath-studio recipe profile.recipe.json --words words.csv --fixations fixations.csv --annotations annotations.json -o profile.csv
python -c "from hashlib import sha256; from pathlib import Path; assert sha256(Path('profile.csv').read_bytes()).hexdigest() == Path('profile.sha256').read_text().split()[0]"
```

## Inspect the study in the app

Add `words.csv` and `fixations.csv` in the dataset wizard and use
`setup.json` for the column mapping and screen size. Under Data Management,
import `annotations.json` into this dataset. On Scanpath, open Share →
Settings file and restore `figure-settings.json` to select the reading and
figure settings. In Corpus Analysis, exclude the tag `exclude` before viewing
the cohort profile.

## File provenance

The settings, setup, annotations, recipe and reference CSV checksum were
produced with Scanpath Studio v0.37.0 at commit
`ab61b3d2f0315e041ab36446abcb0d82ed409076`. The release's
`tabs._build_studio_config`, `wizard._wizard_setup_config`,
`annotations.serialize` and `tabs._recipe_json` wrote the JSON payloads.
Its `aggregation.cohort_word_profile` calculated the two-reader reference
table and `tabs._tidy_csv` supplied the bytes used for the checksum.
The export timestamp records when those writers ran.
