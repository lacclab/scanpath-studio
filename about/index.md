# About Scanpath Studio

**Scanpath Studio v0.44.0** — interactive visualization of eye movements in reading.

Developed by [Omer Shubi](https://omershubi.github.io/), [Keren Gruteke Klein](https://kerengruteke.github.io/), [Maya Grossman](https://www.linkedin.com/in/maya-grossman-32b547292/), [Ella Lion](https://ella-lion.github.io/), [Deborah N. Jakobi](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/lab-members/jakobi.html), [David R. Reich](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/lab-members/reich.html), [Lena Jäger](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/group-leader/jaeger.html), and [Yevgeni Berzak](https://dds.technion.ac.il/people/academic-staff/yevgeni-berzak/), at the Technion and the University of Zurich.

## Cite Scanpath Studio

Cite the software using its [Zenodo DOI](https://doi.org/10.5281/zenodo.22933884). `scanpath-studio cite` and cite print the entry in Python or a terminal, also as RIS or CSL-JSON.

Show BibTeX and APA

```
@software{Shubi_Scanpath_Studio_2026,
  author  = {Shubi, Omer and
             Gruteke Klein, Keren and
             Grossman, Maya and
             Lion, Ella and
             Jakobi, Deborah N. and
             Reich, David R. and
             J{\"a}ger, Lena and
             Berzak, Yevgeni},
  title   = {{Scanpath Studio}},
  year    = {2026},
  version = {0.44.0},
  doi     = {10.5281/zenodo.22933884},
  url     = {https://doi.org/10.5281/zenodo.22933884},
  license = {MIT},
}
```

Shubi, O., Gruteke Klein, K., Grossman, M., Lion, E., Jakobi, D. N., Reich, D. R., Jäger, L., & Berzak, Y. (2026). *Scanpath Studio* (Version 0.44.0) [Computer software]. https://doi.org/10.5281/zenodo.22933884

## Bundled demo

The bundled demo is a subset of **OneStop Eye Movements**. If you use it, also cite Berzak et al. (2025), *OneStop: A 360-Participant English Eye Tracking Dataset with Different Reading Regimes*, Scientific Data. [DOI: 10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2).

## Privacy

With the desktop app or a local install, your recordings stay on your computer and are processed locally. The online demo processes the files you upload on its hosted server. **Help** → **About** says which of the two you are using.

### Your data

A local install (`scanpath-studio`) and the desktop app save your work on your computer, so a refresh or a restart picks up where you left off.

- **What is saved:** the datasets you added, with their column mappings, your annotations, your saved designs, attached metadata tables, and your view, trial and plot settings. The bundled demo and public datasets are not copied, since they reload from their source.
- **Where:** `~/.cache/scanpath-studio/session-v1` in your home folder (`C:\Users\<you>\.cache\scanpath-studio\session-v1` on Windows), or the folder `SCANPATH_STUDIO_STATE_DIR` names. **Data Management** → **Saved on this computer** shows the folder and what it holds, and so does `scanpath-studio cache`.
- **How long:** until you clear it. Removing a dataset from the app removes its saved copy.
- **To clear it:** **Clear what is saved…** under **Saved on this computer**, or close the app and run `scanpath-studio cache --clear`.
- **To turn it off:** start the app with `scanpath-studio --no-persist`, or set `SCANPATH_STUDIO_PERSIST=0`.
- **Downloaded public datasets** stay in the folders you downloaded them to, and clearing what is saved leaves them. **Saved on this computer** lists them beside the datasets you added, each with its size and folder. Its button deletes that download's files, after a confirmation, and leaves anything else in the folder.

The online demo saves nothing. A file you upload there is processed on Streamlit Community Cloud and not kept, so closing or refreshing the tab loses it. The app itself has no analytics, but Community Cloud's page around the app does; see its [privacy policy](https://streamlit.io/privacy-policy). Export your annotations and settings before you leave ([what to back up](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#back-up-your-work)).

## Questions and feedback

[Ask a question](https://github.com/lacclab/scanpath-studio/discussions/categories/q-a), [report a bug](https://github.com/lacclab/scanpath-studio/issues/new?template=bug_report.md), or [request a feature](https://github.com/lacclab/scanpath-studio/issues/new?template=feature_request.md). For a bug report, include the version, your operating system and how you run the app. The app shows its version in **Help** → **About**.

Developed with AI assistance. Cross-check results before publishing.
