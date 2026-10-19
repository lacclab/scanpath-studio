---
description: "About Scanpath Studio: developers, citation, bundled demo, privacy and feedback."
hide:
  - navigation
---

# About Scanpath Studio

```python exec="true"
from scanpath_studio import __release__

print(
    f"**Scanpath Studio v{__release__}** — interactive visualization of eye movements in reading."
)
```

Developed by [Omer Shubi](https://omershubi.github.io/),
[Keren Gruteke Klein](https://kerengruteke.github.io/),
[Maya Grossman](https://www.linkedin.com/in/maya-grossman-32b547292/),
[Ella Lion](https://ella-lion.github.io/),
[Deborah N. Jakobi](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/lab-members/jakobi.html),
[David R. Reich](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/lab-members/reich.html),
[Lena Jäger](https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people/group-leader/jaeger.html), and
[Yevgeni Berzak](https://dds.technion.ac.il/people/academic-staff/yevgeni-berzak/),
at the Technion and the University of Zurich.

## Cite Scanpath Studio

Cite the software using its [Zenodo DOI](https://doi.org/10.5281/zenodo.22933884).

??? quote "Show BibTeX and APA"

    ```python exec="true"
    from docs_support import software_citation

    print(software_citation())
    ```

## Bundled demo

The bundled demo is a subset of **OneStop Eye Movements**. If you use it, also cite
Berzak et al. (2025), *OneStop: A 360-Participant English Eye Tracking Dataset
with Different Reading Regimes*, Scientific Data.
[DOI: 10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2).

## Privacy

With the desktop app or a local install, your recordings stay on your computer
and are processed locally. The online demo processes the files you upload on
its hosted server.

## Questions and feedback

[Ask a question](https://github.com/lacclab/scanpath-studio/discussions/categories/q-a),
[report a bug](https://github.com/lacclab/scanpath-studio/issues/new?template=bug_report.md),
or [request a feature](https://github.com/lacclab/scanpath-studio/issues/new?template=feature_request.md).
For a bug report, include the version, your operating system and how you run
the app. The app shows its version in :material/help: **Help** → :material/info: **About**.

<div class="sps-development-note" markdown>

Developed with AI assistance. Cross-check results before publishing.

</div>
