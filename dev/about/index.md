# About Scanpath Studio

Scanpath Studio visualizes eye movements in reading. **Help** opens the documentation for your Stable or Dev build. **About & citation → App details** links to [what’s new in that build](https://lacclab.github.io/scanpath-studio/dev/whats-new/index.md).

Developed by [Omer Shubi](https://omershubi.github.io/), [Maya Grossman](https://www.linkedin.com/in/maya-grossman-32b547292/), [Keren Gruteke Klein](https://kerengruteke.github.io/), [Deborah N. Jakobi](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/lab-members/jakobi.html), [Ella Lion](https://ella-lion.github.io/), [Carlson Büth](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/lab-members/bueth.html), [David R. Reich](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/lab-members/reich.html), [Lena Jäger](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/group-leader/jaeger.html), and [Yevgeni Berzak](https://dds.technion.ac.il/people/academic-staff/yevgeni-berzak/), at the Technion and the University of Zurich.

## Cite Scanpath Studio

Cite the software using its [Zenodo DOI](https://doi.org/10.5281/zenodo.22933884). In the app, **Help** → **About & citation** → **Citation** gives the APA reference and a copyable BibTeX entry. Use `scanpath-studio cite` in a terminal or cite in Python to get the citation. Both also offer RIS and CSL-JSON formats.

Show BibTeX and APA

```
@software{Shubi_Scanpath_Studio_2026,
  author  = {Shubi, Omer and
             Grossman, Maya and
             Gruteke Klein, Keren and
             Jakobi, Deborah N. and
             Lion, Ella and
             B{\"u}th, Carlson and
             Reich, David R. and
             J{\"a}ger, Lena and
             Berzak, Yevgeni},
  title   = {{Scanpath Studio}},
  year    = {2026},
  version = {0.49.0},
  doi     = {10.5281/zenodo.22933884},
  url     = {https://doi.org/10.5281/zenodo.22933884},
  license = {MIT},
}
```

Shubi, O., Grossman, M., Gruteke Klein, K., Jakobi, D. N., Lion, E., Büth, C., Reich, D. R., Jäger, L., & Berzak, Y. (2026). *Scanpath Studio* (Version 0.49.0) [Computer software]. https://doi.org/10.5281/zenodo.22933884

## Bundled demo

The bundled demo is a subset of **OneStop Eye Movements**. If you use it, also cite Berzak et al. (2025), *OneStop: A 360-Participant English Eye Tracking Dataset with Different Reading Regimes*, Scientific Data. [DOI: 10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2).

## Privacy

With the desktop app or a local install, your recordings stay on your computer and are processed locally. The online demo processes the files you upload on its hosted server. **Help** → **About & citation** → **App details** shows where your files are processed and whether a recovery copy is saved.

### Your data

A local install (`scanpath-studio`) and the desktop app save your work on your computer, so a refresh or a restart picks up where you left off.

- **What is saved:** the datasets you added, with their column mappings, your annotations, your saved designs, attached metadata tables, and your view, trial and plot settings. The bundled demo and public datasets are not copied, since they reload from their source.
- **Where:** `~/.cache/scanpath-studio/session-v1` in your home folder (`C:\Users\<you>\.cache\scanpath-studio\session-v1` on Windows), or the folder set by `SCANPATH_STUDIO_STATE_DIR`. **Data Management** → **Saved work → Your session** lists the saved items. Open **Saved session details** for the folder. You can also check with `scanpath-studio cache`.
- **How long:** until you clear it. Removing a dataset from the app removes its saved copy.
- **To clear it:** **Clear saved session…** under **Saved session details**, or close the app and run `scanpath-studio cache --clear`.
- **To turn it off:** start the app with `scanpath-studio --no-persist`, or set `SCANPATH_STUDIO_PERSIST=0`.
- **Downloaded public datasets** remain in their download folders when you clear saved work. **Dataset downloads** lists each one with its size and folder. Its button deletes that download's files, after a confirmation, and leaves anything else in the folder.

The online demo processes uploads on Streamlit Community Cloud and does not save your work between sessions. Before closing or refreshing the tab, export your annotations and settings, and keep your source files ([what to back up](https://lacclab.github.io/scanpath-studio/dev/guides/scanpath-visualization/#back-up-your-work)). The app itself has no analytics. Community Cloud's surrounding page has its own analytics; see its [privacy policy](https://streamlit.io/privacy-policy).

## Questions and feedback

[Ask a question](https://github.com/lacclab/scanpath-studio/discussions/categories/q-a), [report a bug](https://github.com/lacclab/scanpath-studio/issues/new?template=bug_report.md), or [suggest an improvement on GitHub Ideas](https://github.com/lacclab/scanpath-studio/discussions/new?category=ideas). In the app, **Help → Troubleshooting & feedback → Report a bug** gives you the app version and system details to copy into your report.

Developed with AI assistance. Cross-check results before publishing.
