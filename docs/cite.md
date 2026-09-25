---
description: How to cite Scanpath Studio, and the data you used with it.
---

# Cite Scanpath Studio

A paper is in preparation. Until it is out, cite the software by its Zenodo
DOI, [10.5281/zenodo.22933884](https://doi.org/10.5281/zenodo.22933884):

```python exec="true"
from docs_support import software_citation

print(software_citation())
```

The DOI always resolves to the latest release; the
[Zenodo record](https://doi.org/10.5281/zenodo.22933884) lists a DOI for each
version if you need to pin the one you used. The entry above is generated from
[`CITATION.cff`](https://github.com/lacclab/scanpath-studio/blob/main/CITATION.cff),
the same file behind GitHub's **Cite this repository** button and the app's
❓ **Help → About** dialog.

## The data

The bundled demo is a subset of
[OneStop Eye Movements](onestop.md). If you used it, please cite the corpus as
well:

```bibtex
@article{berzak2025onestop,
  title     = {{OneStop}: A 360-Participant {E}nglish Eye Tracking Dataset
               with Different Reading Regimes},
  author    = {Berzak, Yevgeni and Malmaud, Jonathan and Shubi, Omer
               and Meiri, Yoav and Lion, Ella and Levy, Roger},
  journal   = {Scientific Data},
  year      = {2025},
  publisher = {Nature Publishing Group},
  doi       = {10.1038/s41597-025-06272-2},
  url       = {https://www.nature.com/articles/s41597-025-06272-2},
}
```

Any other corpus you load is cited in its own right.
