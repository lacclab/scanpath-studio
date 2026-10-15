# OneStop dataset

[OneStop Eye Movements](https://github.com/lacclab/OneStop-Eye-Movements) is an
English eye-tracking-while-reading corpus of 360 participants (Berzak et al.,
*Scientific Data* 2025,
[doi:10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2)).
The bundled demo is a small part of it.

The full corpus is four datasets in :material/database: **Data Management**, one
per reading regime: ordinary reading, information seeking, repeated reading, and
information seeking (repeated). Open one, and the first time the app offers to
download it from [OSF](https://osf.io/2prdq/) (about 1 GB per regime, downloaded once).

Each trial is one reading of one paragraph, and its screens (title, paragraph,
question, answers, feedback) are steps of the **Screen** picker.

Headless: `sps.load_onestop(...)` in the Python API, or
`scanpath-studio render --onestop DIR` on the command line.
