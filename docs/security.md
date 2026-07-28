# Security audit

This is the engineering counterpart to [Privacy & where your data goes](privacy.md).
That page tells a researcher what happens to their corpus. This one records what
was actually checked in the code, what was found, and what is still open.

Every claim below cites the `module.py:function` it was verified in. Where a
claim depends on a dependency's behaviour, the dependency file and line are cited
too. Nothing here is inferred from documentation alone.

- **Audited version:** `scanpath_studio` 0.25.0
- **Dependency versions the runtime claims were checked against:** Streamlit
  1.58.0, pandas 2.3.3, CPython 3.12.12
- **Method:** source read of every write-to-disk, URL-building, path-handling,
  archive-reading and `@st.cache_data` site, plus targeted scripts that exercised
  the share-link builder, the bulk exporter, the export path sanitizer, the
  cache-key fingerprint and the log-handler installer against the bundled sample.
  Dependency claims were checked against the installed source, never the docs.

!!! warning "Scanpath Studio has no authentication, on any deployment"
    There is no login, no session token, and no per-user authorization anywhere
    in the codebase. Every access-control decision is made by whatever binds the
    port. Several findings below follow from that single fact.

## What was checked

| Dimension | Verdict |
| --- | --- |
| On-disk residue from loaded data | Clean, with one narrow exception (S8) |
| `@st.cache_data` persistence to disk | **Clean** — no `persist="disk"` anywhere |
| Share links / saved configs carrying identifiers | Participant + trial ids ride in the URL, and the saved config also carries your notes (S3) |
| Share links / saved configs carrying local file paths | **Clean** — no path in either |
| Exported figures carrying local file paths | **Clean** — images are inlined as `data:` URIs |
| Exported *tables* carrying local file paths | **Leaks an absolute path** (S4) |
| Zip-slip / path traversal on ingest | **Clean** — uploads never hit disk; corpus extraction is traversal-safe |
| Path traversal on export | Data values are sanitized; the user's own pattern is not (S9) |
| Desktop bundle bind address | **Binds all interfaces** (S1) |
| Server-side path handling from the browser | Path oracle + arbitrary-directory write (S2) |
| Cross-session bleed via the upload cache | **Clean** — keyed on a server-generated UUID |
| Cross-session bleed / staleness via the analysis caches | Real collision, by construction (S5) |
| Cross-session sharing via the corpus-directory caches | Shared, but keyed on the path — same key means same files (see *What is clean*) |
| Code-execution surface (`eval` / `exec` / `pickle` / `subprocess` / `df.query`) | **Clean** — none in the shipped package |
| Data interpolated into raw HTML | One unescaped site (S7) |

## Findings

Ranked by what an attacker or an accident can actually achieve, not by how
alarming the mechanism sounds.

---

### S1 · High — the desktop bundle serves the whole network, not just localhost

`desktop/launcher.py:main` starts the server through `cli.launch_app` with
exactly five flags — `--global.developmentMode=false`, `--server.headless=true`,
`--server.port=<port>`, `--server.fileWatcherType=none` and
`--browser.gatherUsageStats=false`. It never sets `--server.address`.

Streamlit's default is not loopback. `starlette_server.py:_get_server_address`
returns `config.get_option("server.address") or DEFAULT_SERVER_ADDRESS`, and
`starlette_server_config.py:52` defines `DEFAULT_SERVER_ADDRESS = "0.0.0.0"`.
The socket therefore binds every interface.

`_free_port` binds `("127.0.0.1", 0)` only to *choose* a free port number; the
server then binds that port on all interfaces. The launcher's own docstring
("starts the Streamlit server on a free localhost port") and the message it
prints (`Scanpath Studio starting on http://127.0.0.1:<port>`) both describe
loopback, so the user has no way to notice.

**Impact.** A researcher opens the desktop app on a laptop joined to a campus,
lab, conference or café network, loads a participant corpus, and every host on
that subnet can open `http://<their-ip>:<port>` and drive the app: browse every
trial, read the stimulus text, download the tabular exports. There is no login
to stop them. The randomized port is not a control — the whole range scans in
seconds.

**Fix.** Add `"--server.address=127.0.0.1"` to the argument list in
`desktop/launcher.py:main`. One line, no behaviour change for the intended user.

!!! note "Same exposure, different visibility, for `scanpath-studio run`"
    `cli.launch_app` also passes no address, so `scanpath-studio run` and a bare
    `streamlit run` bind `0.0.0.0` too. That is standard Streamlit behaviour and
    Streamlit prints a "Network URL" line announcing it, so the user is at least
    told. The desktop launcher suppresses Streamlit's own output and prints a
    loopback URL instead, which is why it is ranked separately and higher.

**Status:** **fixed** 2026-07-28 — `desktop/launcher.py` now passes
`--server.address=127.0.0.1`. [privacy.md](privacy.md) states the same thing in user-facing
terms ("it does not restrict the bind address, so the same LAN exposure
applies") and tells readers how to set `server.address` themselves in the
meantime. When this fix lands, that page needs updating too.

---

### S2 · High (hosted deployments only) — the dataset directory box is a server-side path oracle and an arbitrary-directory write

`app.py:_dataset_dir_input` renders a free-text **Data directory** input whose
value is resolved by `app.py:_resolve_data_dir` and handed straight to the corpus
loaders. `app.py:_dataset_access_status` then reports the outcome back into the
page:

- present → `` Found in `<path>` ``
- absent → `` No data found in `<path>` `` or `Not downloaded yet` plus a
  **⬇ Download** button.

Presence is decided by `datasets.potec_present`, `datasets.onestop_present` and
`datasets.multipleye_inventory` — all pure `is_dir()` / `glob` stats.

Two consequences on any deployment reachable by someone other than the machine's
owner:

1. **Path-existence oracle.** Typing any absolute path reveals, one bit at a
   time, whether it exists and whether it holds files matching the corpus layout.
   The bit is coarse by design — `multipleye_inventory` does parse session and
   stimulus names out of filenames under `<root>/<fixation_source>/*/`, but
   `app.py:_load_multipleye_source` consumes only `present=bool(sessions_all)`,
   so the names themselves reach the browser only once a *real* corpus loads.
   The sharper disclosure is the failure branch: `app.py:_load_multipleye_source`
   and `_load_potec_source` both render
   `` st.error(f"Couldn't load … from `{root}`: {exc}") ``, and an `OSError`'s
   message carries the filename the loader tried.
2. **Arbitrary-directory write.** Clicking **⬇ Download** calls
   `datasets.download_potec(root)` or `datasets.download_onestop(root)` with that
   same browser-supplied path. Both do `root.mkdir(parents=True, exist_ok=True)`
   (`datasets.py:108`, `datasets.py:538`) and write fetched files into it. A
   remote visitor can create directory trees anywhere the server process can
   write and fill the disk — the OneStop reports are tens to hundreds of MB each.

The written *content* is not attacker-controlled (fixed OSF/GitHub URLs, fixed
filenames), so this is not code execution. It is disclosure plus a write/DoS
primitive.

**This is on by default.** `app.py:public_datasets_enabled` returns `True` unless
`SCANPATH_PUBLIC_DATASETS` is explicitly set to `0` / `false` / `no`, so the
Public datasets source — and its directory box — is present on any deployment
that does not set that variable. (`scanpath_studio/CLAUDE.md` still describes
this source as "**feature-flagged off** until a future release: shown only when
`SCANPATH_PUBLIC_DATASETS=1`"; that is stale — the code opts *out*, not in, and
its own docstring says "Enabled by default".)

**Fix (either, ideally both).**

- Gate the directory input and the Download button on a deployment flag: read the
  data root from an environment variable when one is set, and hide the free-text
  input and the download button when the app is not running locally.
- Constrain the accepted path to a configured allow-root and reject anything that
  resolves outside it, rather than passing the string through
  `_resolve_data_dir` untouched.

**Status:** **fixed** 2026-07-28 — `app.local_filesystem_enabled()`
(`SCANPATH_LOCAL_FS`, default *local*, so an existing install is unaffected on
upgrade) gates the path box, the 📁 picker and the ⬇ Download button; a shared
deployment sets it to `0` and supplies the corpus location through
`SCANPATH_DATA_ROOT`. That variable also acts as an allow-root wherever it is
set: `app._resolve_data_dir` compares the *resolved* path against it, so `..`
and symlinks collapse to the root rather than being stat'd or written into.
Covered by `tests/test_deployment_gate.py`.

!!! danger "Related: the folder picker opens a dialog on the *server's* screen"
    `app.py:_pick_directory_dialog` opens a `tkinter.filedialog.askdirectory()`.
    On a host that has a display, a remote visitor clicking **📁** pops a modal
    file dialog on the host's desktop and blocks the calling thread until someone
    dismisses it. The function is written for the local case and degrades to
    `None` on a headless host, but it is not gated on being local. The same
    deployment flag proposed above should hide this button.

---

### S3 · Medium — a share link names a participant, in the URL

`url_state.py:_build_share_query` emits `participant=<participant_id>` and
`trial_id=<trial_id>` verbatim, read out of `st.session_state["_share_selection"]`.
Verified by driving the builder directly; a demo-source link comes back as:

```text
source=demo&participant=l37_1129&trial_id=l37_1129_2_1_1_Ele_r0&show_words=1
```

It also emits the *column names* the user picked (`color_by`,
`highlight_column`, `x_field`, `y_field`, `word_hover_measure` in
`_SHARE_VALUE_PARAMS`), which reveal the dataset's schema.

URLs are the least private place to put an identifier: they land in browser
history, proxy and server access logs, `Referer` headers on outbound clicks, and
chat/mail link previews. In most reading corpora a participant id is a pseudonym,
but it is still a stable per-person key — a link is a document that names one
participant and one trial.

**Not found, and worth stating:** no absolute or relative filesystem path ever
enters a share link, in either direction. `_SHAREABLE_SOURCES` maps only the five
built-in sources to short tokens; a directory-backed corpus is not shareable at
all and the panel emits a caveat instead. On the read side, `_URL_PRESETS` is
built entirely from the same toggle / value / number maps, so no URL parameter
can point the app at a server-side path (contrast S2, which is a *widget*, not a
link).

**The saved plot-config JSON carries more than the link does.**
`tabs._build_studio_config` writes no filesystem path — its `data_source` is a
display label and its `column_mapping` is column names, with the `*_upload`
widget keys deliberately excluded by `tabs._collect_column_mapping` because an
`UploadedFile` is not JSON-serializable. But it does write two things a reader
should know about before mailing the file around:

- `"selection": {"participant_id": …, "trial_id": …}` — the same identifiers as
  the link.
- `"annotations": [...]` — the whole annotation store, flattened by
  `annotations.store_to_records` into `{participant_id, trial_id, star, tags,
  note}` for **every** annotated trial, not just the selected one. `note` is
  free text the researcher typed, so a config saved after a review session can
  contain clinical or subject-identifying prose that no other export carries.

No fixation rows and no word rows are in either artifact.

Don't confuse this with the `plot_config.json` a bulk export writes: that one
comes from `export._plot_config_dict`, and its `"annotations"` key holds the
figure's title and caption (EXP-2), not the per-trial notes. Only the sidebar's
**💾 Save & restore** download carries the annotation store.

**Assessment.** This is inherent to the feature: a link that reopens a specific
trial has to identify that trial. The right response is disclosure, not removal,
and [privacy.md](privacy.md#what-a-share-link-and-a-saved-config-contain) already
spells out exactly what a link carries. The residual gap is that the Share panel
itself does not say so at the point of copying.

**Fix.** Add a one-line caption in `url_state.py:_render_share_body` next to the
copy button: *"This link contains the participant and trial ids."* Optionally add
a toggle that drops `participant` / `trial_id` and shares view settings only. Say
the same thing next to the **💾 Save & restore** download button, naming the
annotation notes.

**Status:** open (documentation-level mitigation already in place).

---

### S4 · Medium — exported tables carry an absolute local path, which leaks the OS username

`image_path` is registered as a `passthrough` meta field on both the words and
the fixations schema (`data.py:1388`, `data.py:1435`), so it survives
normalization. For the bundled demo it is made absolute at load time by
`data.py:_resolve_sample_image_paths`; for MultiplEYE it is stamped absolute by
`datasets.py:_multipleye_stamp_image_path` from the user's own corpus root.

It then rides into the fixation exports. Running `export.bulk_export` over one
bundled trial with every artifact enabled and grepping each zip entry for
`/Users/` gives:

```text
README.md                                                   clean
per_trial/l37_1129__l37_1129_2_1_1_Ele_r0/figure.html       clean
per_trial/l37_1129__l37_1129_2_1_1_Ele_r0/plot_config.json  clean
per_trial/l37_1129__l37_1129_2_1_1_Ele_r0/measures.csv      clean
per_trial/l37_1129__l37_1129_2_1_1_Ele_r0/fixations.csv     LEAKS
aggregate/all_measures.csv                                  clean
aggregate/all_fixations.csv                                 LEAKS
```

with the leaked value being

```text
image_path = /Users/<username>/Projects/scanpath_studio/app/scanpath_studio/sample_data/images/2_1_1_Ele__paragraph.png
```

The measures tables are clean only incidentally: `data.compute_word_metrics`
rebuilds its output from a fixed column list, so `image_path` never reaches it.
The normalized **words** frame carries `image_path` as well (both schemas
register it), so any future export of the words table inherits the same problem.

**Impact.** A fixations CSV is exactly the kind of file that gets attached to a
paper, posted to OSF, or mailed to a collaborator. `/Users/<name>/` or
`/home/<name>/` discloses the OS account name, and the rest of the path discloses
the local directory layout — including, for a MultiplEYE load, where that corpus
is stored on the machine. (PoTeC is unaffected: nothing in its loader stamps an
`image_path`, and an uploaded corpus only carries one if the user's own file
does.)

**Verified clean by contrast:** exported *figures* do not leak the path.
`plots._image_to_data_uri` base64-inlines the PNG before it reaches
`layout.images`, so neither `fig.to_json()` nor the saved HTML contains the
source path — confirmed by rendering the same trial with its stimulus image and
checking that `fig.to_json()` holds a `data:image/png;base64,…` payload and no
`/Users/`.

**Latent, not live: the Data Inspection download buttons.**
`tabs._render_download_buttons` feeds the raw frames straight to
`_frame_to_csv_bytes` / `_frame_to_parquet_bytes` and would leak the column the
same way — but it is currently **unreachable**. Its only caller is
`tabs._render_paginated_dataframe`, which calls it under
`if download_name and not df.empty`, and none of that function's four call sites
(`render_metrics_tab`, `render_fixations_tab`, `render_raw_gaze_tab`,
`render_stimuli_tab`) passes `download_name`. So the tab renders tables with no
download button at all, and the leak there is latent. See S11.

**Fix.** In `export.bulk_export`, drop or relativize `image_path` on the frames
written to CSV/Parquet (and in the mega-table), and do the same in
`tabs._render_download_buttons` before anyone wires it up. Relativizing to the
basename keeps the column useful for matching a stimulus without disclosing the
tree.

**Status:** **fixed** 2026-07-28 — `export.strip_local_paths` reduces
`image_path` to its basename at `export._write_table`, the single chokepoint
every exported table (per-trial, aggregate, mega-table; CSV and Parquet) passes
through. The basename is kept so the column still matches a row to its stimulus.
Covered by `tests/test_export.py::TestLocalPathsAreNotExported`, which greps
every zip member the way this audit did.

---

### S5 · Medium — `frame_fingerprint` does not look at the middle of a frame, so edited data can serve a stale cached result

`data.py:frame_fingerprint` is the explicit cache key for every `@st.cache_data`
function that takes an un-hashed frame — 32 call sites across `app.py`,
`data.py`, `controls.py`, `tabs.py` and `utils.py`. Most consequential first:

- **`app._normalize_pair_cached`**, whose `cache_key` is assembled by
  `app._normalize_pair` from `frame_fingerprint(words_df)` and
  `frame_fingerprint(fixations_df)` — the whole normalize + harmonize step. A
  collision here serves the *entire normalized corpus* of the other frame, not
  one derived table.
- `tabs._cached_scanpath_figure`, the corpus-analysis wrappers
  (`tabs._c_per_reader_word`, `_c_cohort_profile`, `_c_word_rate`, …), the
  reading measures (`data._compute_word_metrics_cached`), the trial list
  (`utils._build_combo_options_cached`), the sidebar filter options
  (`controls._column_unique_strs` / `_column_present_bools`), the default filter
  set (`data._default_filters_cached`), the stimuli table
  (`tabs._build_stimuli_table_cached`) and the dataset statistics
  (`tabs._dataset_statistics`).

It returns `(n_rows, column_names, hash(df.head(64)), hash(df.tail(64)))`. The
middle of the frame is never sampled. This is not a probabilistic hash collision
— it is structural:

```python
a = pd.DataFrame({"participant_id": [f"p{i}" for i in range(300)],
                  "duration_ms": list(range(300))})
b = a.copy()
b.loc[150, "duration_ms"] = 999999      # one cell, in the middle

frame_fingerprint(a) == frame_fingerprint(b)   # -> True
```

Any table of **129 rows or more** whose change falls outside the first and last
64 rows produces an identical key. (Verified at the boundary: 127 and 128 rows
still detect a middle edit; 129 and 130 do not.)

**Impact, in order of likelihood.**

1. **Stale results within a session.** A user fixes a value mid-corpus and
   re-uploads a table with the same row count and columns. Every cached figure,
   reading measure and aggregate is served from the *pre-edit* data, silently and
   with no warning. That is a route to a wrong number in a paper.
2. **Cross-session bleed on a shared server.** `@st.cache_data` is global to the
   process, not to the session, so two visitors whose frames agree on shape,
   columns and first/last 64 rows share cache entries. The realistic trigger is
   two people loading the same public corpus with different de-identification
   applied to the middle rows.

The docstring already concedes a collision is possible but calls it
"astronomically unlikely for real eye-tracking tables". For a *random* collision
that is fair. For an edit outside the sampled window it is wrong: the probability
is 1.

The `except Exception: head = tail = 0` fallback at the end of the function
widens this further — on that path the key degrades to `(n, columns, 0, 0)` and
every frame of the same shape collides. It is a genuine last resort (the
`TypeError` retry with `astype(str)` catches the realistic failure) but it should
not fail *open*.

**Fix.** Sample a fixed-size stride across the whole frame instead of only the
ends — e.g. hash `df.iloc[:: max(1, n // 256)]` alongside head and tail. That
stays O(1) in the row count, costs a few hundred rows, and catches a middle edit.
Separately, make the last-resort branch return a value that cannot be reused
(a fresh `uuid4`, or `None` meaning "do not cache") rather than `0`.

**Status:** **fixed** 2026-07-28 — `data.frame_fingerprint` now hashes the
**whole frame** up to 200,000 rows, so any edit anywhere changes the key
(measured: ~12 ms at the cap). Above it the key stays a sample — both ends plus a
stride — because a full hash costs ~237 ms at 5M rows and roughly six
corpus-sized fingerprints are taken per rerun; that limit is stated on the
function, with the advice to use **Clear cache** after editing a corpus that
large. The last-resort branch now returns a `uuid4` instead of `0`, so an
unhashable frame *misses* the cache rather than matching every frame of its
shape. Writing the tests surfaced a second collision the audit didn't name: the
per-row hashes were combined with `.sum()`, which is order-invariant, so a frame
and a `sort_values` of itself — same rows, same index labels — shared a key; they
are now digested in order. Covered by
`tests/test_data.py::TestFrameFingerprint`.

---

### S6 · Low–Medium — a zip upload is decompressed without a size cap

`data.py:_read_zipped_table` reads every member of an uploaded `.zip` into memory
with `zf.open(member).read()` and no ceiling on the decompressed size.

The existing guard measures the wrong thing. `data.py:upload_exceeds_limit` reads
each `UploadedFile.size` — the *compressed* bytes — against
`UPLOAD_SIZE_WARN_BYTES` (25 MB), and even then it only warns and offers a
"Load it anyway" checkbox.

How much can arrive in the first place depends on where you launched from, and
that is worth being precise about: the repo's `.streamlit/config.toml` sets
`server.maxUploadSize = 5000` (5 GB), but that file is **not shipped in the
wheel** — `MANIFEST.in` packages only `sample_data`, and Streamlit resolves the
config relative to the launch directory. So the hosted demo and a source
checkout accept 5 GB per file, while `pip install scanpath-studio &&
scanpath-studio run` from any other directory, and the desktop bundle, fall back
to Streamlit's own default of 200 MB (`config.py`, `server.maxUploadSize`,
`default_val=200`). Every one of those ceilings is far above the 25 MB warn
threshold, and none of them bounds the *decompressed* size.

A 25 MB zip of highly compressible CSV expands to many gigabytes. On the hosted
demo (~1 GB container) that is an OOM kill of the process — which takes every
concurrent visitor's session with it. Locally it is a hang.

This is availability only. It is not a confidentiality issue and it needs no
attacker: an honest multi-gigabyte corpus does the same thing.

**Fix.** In `_read_zipped_table`, sum `ZipInfo.file_size` across the members it
intends to read and raise a clear `ValueError` above a threshold before opening
any of them, rather than discovering the size by exhausting RAM.

**Status:** open.

---

### S7 · Low — stimulus text is interpolated into raw HTML without escaping

`tabs._render_paragraph_panel` builds a highlighted-span line with
`unsafe_allow_html=True` and interpolates two data-derived values unescaped
(`tabs.py:1122-1127`):

```python
st.markdown(
    f'<span style="background-color:{span_bg[col]};'
    f'color:{_HIGHLIGHT_TEXT_COLOR};padding:0 4px;border-radius:2px;">'
    f"<b>{_humanize_field(col)}:</b></span> {span_str}{note}",
    unsafe_allow_html=True,
)
```

`span_str` is the stimulus text joined straight from the words table
(`tabs._span_text`) and `_humanize_field(col)` is a column name from the user's
file. `note` is tool-generated HTML and is correctly left raw.

The sibling renderer in the same file gets this right:
`tabs._render_paragraph_with_spans` (`tabs.py:889`) escapes each word with
`html.escape` before interpolating (`tabs.py:914`), and so do the chip strip
(`tabs.py:1882`), the summary stats (`tabs.py:1906-1907`) and the comparison
labels (`tabs.py:2295`, `tabs.py:2304`). Of the seven `unsafe_allow_html=True`
sites in `tabs.py`, this is the only one that interpolates unescaped data;
the remaining six either escape or interpolate tool-controlled constants
(`_chip_color` and `_span_bg_for` both return values from fixed palettes, so the
`style="background:…"` attributes are not attacker-reachable either).

Streamlit's markdown path does not compensate. Inspecting the shipped 1.58.0
frontend bundle (`static/static/js/index.*.js`), the `allowHTML` branch lazily
loads `rehype-raw` and no sanitizer plugin — `rehype-sanitize` is not in the
distribution at all; the only guard is a URL transform rejecting `javascript:`
and `vbscript:` schemes, and `disallowedElements` is empty for non-label
markdown. The app-side escape is the only control there is.

**Impact is bounded by who supplies the data.** The injected content comes from
the corpus the user loaded and is rendered back to that same user's session. On a
single-user local install it is self-inflicted. It matters when a corpus arrives
from someone else — a collaborator's CSV, a shared lab dataset, or an upload on
the hosted demo — and it matters more given the app has no authentication (S1,
S2).

**Fix.** Escape both values, matching `_render_paragraph_with_spans`:

```python
f"<b>{html.escape(_humanize_field(col))}:</b></span> "
f"{html.escape(span_str)}{note}"
```

**Status:** open.

---

### S8 · Low — the MP4 export leaves a temp file behind if the process is killed

`animation_export.encode_mp4` creates a `tempfile.NamedTemporaryFile(suffix=".mp4",
delete=False)`, encodes into it via `imageio`, reads it back, and unlinks it in a
`finally` block.

The hygiene is right: `NamedTemporaryFile` creates with `O_CREAT|O_EXCL` and mode
`0600` (verified), so the file is not world-readable and cannot be pre-created by
another local user; the `finally` runs on both the success and the exception path.
The residue only survives a `SIGKILL` or a power loss mid-encode, and its content
is rendered animation frames — the figure as displayed — not the underlying
tables.

This is the **only** place the running app writes user-derived content to disk.
Everything else is in memory: `@st.cache_data` uses no `persist="disk"` anywhere
in the package, Streamlit's uploads live in `MemoryUploadedFileManager`
(`web/server/server.py:62`), the export zip is assembled in an `io.BytesIO`
(`export.py:887`), and the GIF encoder saves into a buffer
(`animation_export.py:273`). `~/.streamlit/cache` is never created.

The corpus downloads in `datasets.py` do leave residue on an interrupted fetch —
`download_potec` and `download_onestop` stage each file as `<dest>.part` and
`Path.replace` it into position (`datasets.py:136`, `datasets.py:555`), so a
killed process leaves a truncated `.part` behind. That is deliberate (an atomic
rename is what stops a truncated file from being mistaken for a complete one),
and the content is a public corpus fetched from a fixed URL, not the user's data.

**Assessment.** Accepted risk. It is inherent to `imageio`'s FFMPEG writer, which
needs a real path. Documented in
[privacy.md](privacy.md#where-an-upload-actually-goes) so a user on a shared
machine knows.

**Status:** accepted.

---

### S9 · Low — the export path pattern can escape the zip root, but only via the user's own typing

`export.render_pattern` sanitizes every *substituted value* through
`_path_component`, which collapses `.` and `..` and replaces separators. A
malicious value in the data cannot escape:

```text
pattern "per_trial/{participant_id}__{trial_id}/{artifact}.{ext}"
trial_id "../../../etc/evil"
      ->  per_trial/p1__.._.._.._etc_evil/figure.png
```

The literal text of the pattern is not sanitized, because its `/` have to stay
real separators. `resolve_export_path` only does `.lstrip("/")`:

```text
pattern "/tmp/{artifact}.{ext}"      ->  tmp/figure.png          (absolute stripped)
pattern "../../{participant_id}/…"   ->  ../../p1/figure.png     (traversal kept)
```

**Assessment.** Accepted risk, low. The traversal has to be typed by the person
downloading the zip, into their own zip, and the extractor decides what to do with
it — `unzip` and macOS Archive Utility refuse traversal entries, and Python's own
`ZipFile.extractall` strips `..` components. The self-inflicted case is a
misplaced file, not a compromise.

**Fix if hardened anyway.** Reject a pattern containing a `..` segment in
`export.pattern_error`, which already validates patterns up front in the UI, so
the user gets told before a 200-trial render rather than after.

**Status:** accepted (fix is cheap if wanted).

---

### S10 · Low — the debug log handler is added once per session to the process-wide root logger

`debug_log.install_log_capture` guards on `st.session_state[_HANDLER_FLAG]`, which
is per-session, but attaches to `logging.getLogger()`, which is per-process. Three
simulated sessions add three root handlers; they are never removed when a session
ends. Reproduced by driving `install_log_capture` with three successive
session-state dicts: three `_SessionStateHandler` instances on the root logger,
and one subsequent `logging.warning` lands **four** times in the fourth session's
buffer.

Effects: every log record is appended N times to the buffer of whichever session
is currently running (N = number of sessions the process has served), which
divides the 500-record ring buffer's useful history by N; and handlers accumulate
for the process's lifetime.

**Not a cross-session leak.** `_SessionStateHandler.emit` resolves
`st.session_state` through the *calling* thread's script-run context, so a record
logged during session A's run lands in session A's buffer regardless of which
handler instance emits it. A record logged from a thread with no context raises
and is swallowed by the handler's bare `except`.

**Fix.** Key the installed flag on the handler's own presence rather than session
state — e.g. skip if any root handler is already a `_SessionStateHandler` — so at
most one exists per process.

**Status:** open (correctness / resource, not confidentiality).

---

### S11 · Low — the Data Inspection download helper is unreachable, so a latent leak sits in dead code

`tabs._render_download_buttons` (CSV + Parquet of the raw frame, via
`_frame_to_csv_bytes` / `_frame_to_parquet_bytes`) is called from exactly one
place: `tabs._render_paginated_dataframe`, under `if download_name and not
df.empty`. None of that function's four call sites — `render_metrics_tab`,
`render_fixations_tab`, `render_raw_gaze_tab`, and the stimuli table in
`render_stimuli_tab` — passes `download_name`, and no other module calls either
function.

So the Data Inspection tab ships a download path that never renders, and the
`image_path` disclosure of S4 is latent there rather than live. Recorded because
the natural reading of the code is that those buttons exist, and because whoever
wires them up would ship the leak with them.

**Fix.** Either delete the helper and the `download_name` parameter, or pass
`download_name` at the call sites *and* strip `image_path` first (S4).

**Status:** open (correctness, not confidentiality).

## What is fixed, and what is accepted

**Fixed so far: S1, S2, S4** (2026-07-28), each with its own tests — see the
`Status:` line on each finding, which is the authoritative record. The audit
itself produced no code change; the fixes landed afterwards as reviewable
commits, tracked as **DATA-16** in `IMPROVEMENTS.md`.

S1 and S2 went first because they are the only findings a stranger on the network
can reach at all. **Still open: S3, S5, S6, S7, S10, S11** — all of which need
someone who can already open the app.

**Accepted, with the reason:**

| # | Accepted because |
| --- | --- |
| S8 · MP4 temp file | Inherent to `imageio`'s FFMPEG writer, which needs a real path. Mode `0600`, unlinked in a `finally`, survives only a `SIGKILL`, and holds rendered frames rather than the underlying tables. Documented in [privacy.md](privacy.md#where-an-upload-actually-goes) instead. |
| S9 · `..` in a user-typed export pattern | Self-inflicted by definition — the traversal has to be typed by the person who then extracts their own zip, and `unzip`, macOS Archive Utility and CPython's `extractall` all refuse or strip it. Cheap to harden in `export.pattern_error` if wanted. |

Everything else in the table above is either `open` or explicitly clean. Nothing
was closed by arguing the impact away.

## What is clean

Stated explicitly, because "we found nothing" is only useful if you know what was
looked for.

**No disk persistence of loaded data.** There is no `persist="disk"` on any
`@st.cache_data` in the package, so Streamlit's `LocalDiskCacheStorage` is never
engaged and `~/.streamlit/cache` is never created. Uploads go to Streamlit's
`MemoryUploadedFileManager` (RAM, dropped by `remove_session_files` when the
session ends). Wizard-finished datasets live in `st.session_state["_datasets"]`
(`wizard._finalize_wizard_dataset`) — session memory, no on-disk store.
Annotations live in session state. The only disk writes in the whole package are
the corpus downloads in `datasets.py`, the CLI/headless `api.save_figure*`, and
the MP4 temp file of S8.

**No zip-slip on ingest.** An uploaded archive is never extracted.
`data._read_zipped_table` reads each member into an `io.BytesIO` and hands it to
pandas; member names are used only as `source_file` labels via `Path(member).stem`.
The one `extractall` in the package (`datasets.download_potec`, `datasets.py:117`)
extracts an archive fetched from a fixed HTTPS OSF URL, and CPython's
`ZipFile._extract_member` independently strips drive letters, leading separators
and `..` components before writing, so a hostile member name could not escape even
if OSF served one. Symlink members are written as regular files by `zipfile`, not
recreated as links.

**No path leak in share links or saved configs.** `_build_share_query` emits only
the maps in `_SHARE_TOGGLE_PARAMS` / `_SHARE_VALUE_PARAMS` / `_SHARE_INT_PARAMS` /
`_SHARE_FLOAT_PARAMS` / the two range maps, plus `source`, `participant`,
`trial_id` and the OneStop variant/regime/parts. None of those is a path, and the
read side (`_URL_PRESETS`) is derived from the same maps, so no link can steer the
app at a server-side directory. `tabs._build_studio_config` records `data_source`
(a display label) and `column_mapping` (column names from
`tabs._collect_column_mapping`, which explicitly excludes the `*_upload` widget
keys because an `UploadedFile` is not JSON-serializable). Neither carries fixation
rows, word rows or a filesystem path — but see S3 for what the config *does*
carry.

**No SQL/expression injection surface from URL params or column choices.** There
is no `DataFrame.query`, `eval` or `numexpr` path anywhere in the package, so a
deep-linked `color_by` / `highlight_column` / `x_field` value is only ever used as
a dictionary lookup or a column label.

**No `source_file` path leak.** `data.read_tables` tags rows with
`Path(...).stem` — the filename stem only, never the directory.

**No cross-session bleed through the upload cache.** `app._read_uploaded_table_cached`
and `_read_uploaded_tables_cached` pass the file object un-hashed (underscore
prefix) and key on `app._uploaded_file_key` = `(file_id, name, size)`. Streamlit
generates `file_id` as `str(uuid.uuid4())` server-side, per upload
(`memory_uploaded_file_manager.py:110`), so two sessions can never collide on a
cache entry — not even by uploading byte-identical files. (The analysis caches are
a different story; see S5.)

**The corpus-directory caches are shared across sessions, and that is fine.**
`app._cached_potec_raw_frames(root)`, `_cached_multipleye_raw_frames(root,
fixation_source)`, `_cached_multipleye_inventory(root, fixation_source)` and
`_cached_onestop_raw_frames(root, regime, parts, variant)` are keyed on the
directory *path string*, so on a multi-user server two sessions pointing at the
same root share one parse. Equal key means equal files on disk, so no session
sees data it could not have read itself — this is caching, not bleed. The one
real consequence is staleness: no `mtime` is in the key, so replacing a corpus
under a live server keeps serving the old parse until the cache is cleared.

**No code-execution surface in the shipped package.** No `eval`, `exec`, `pickle`,
`os.system`, or `subprocess` anywhere under `scanpath_studio/` — the only
`subprocess` use is `desktop/smoke_test.py`, a development tool that is not
imported by the app. Untrusted files are parsed only by pandas readers
(`data._read_by_extension`: parquet, feather, xlsx/xls, tsv, csv); `read_pickle`
and `read_hdf` are not reachable. MultiplEYE's stimulus config is read by regex
(`datasets._multipleye_font_config`), never executed. The uploader's accepted
types (`app._UPLOAD_TYPES`) exclude macro-enabled workbook formats.

**No telemetry of ours.** There is no analytics call anywhere in the package, and
the single cookie the app sets (`tour.TOUR_OPTOUT_COOKIE` = `sps_tour_optout`,
`SameSite=Lax`, `path=/`, one year) holds the literal `"1"` and no identifier.

Streamlit's *own* telemetry is a different matter and is not fully covered.
`browser.gatherUsageStats` defaults to `True` (`config.py`, `default_val=True`).
It is turned off in the repo's `.streamlit/config.toml` and explicitly on the
desktop launcher's command line — but `cli.launch_app` injects only the
`--theme.*` flags, and the config file is not in the wheel (same packaging gap as
S6), so `pip install scanpath-studio && scanpath-studio run` from an arbitrary
directory leaves it **on**. That is Streamlit's collection, not ours;
[privacy.md](privacy.md) enumerates what it sends and how to turn it off per
deployment. Adding `--browser.gatherUsageStats=false` to `cli.launch_app`'s
injected flags would close the gap for every launch path at once.

**Streamlit's own request-level protections are on.** `server.enableXsrfProtection`
and `server.enableCORS` both default to `True` (`config.py`) and nothing in the
repo's config or the app's launch flags disables either.

**HTML escaping is right almost everywhere.** Thirteen sites in the package pass
`unsafe_allow_html=True` — seven in `tabs.py`, three in `tour.py`, two in
`app.py`, one in `debug_log.py`. All but S7 either escape their data
(`html.escape` in `tabs.py` at 914, 1882, 1906-1907, 2295, 2304; `debug_log._escape`
for log messages) or interpolate only tool-controlled constants (`app.py` emits
the stylesheet and a spacer `<div>`; `tour.py` emits `<style>` blocks built from
module constants and a theme-derived colour pair). The share widget's client-side
script embeds its payload via `json.dumps` of an already `urlencode`d string, so
no `<` can reach it.

## Deployment guidance that follows from this

- **A machine holding participant data should not run this app on an
  untrusted network.** Until S1 lands, pass `--server.address=127.0.0.1`
  explicitly, or bind to loopback and use an SSH tunnel for remote access.
- **A shared/hosted deployment should set `SCANPATH_PUBLIC_DATASETS=0`** until
  S2 is fixed, which removes the directory input, the path oracle and the
  download-to-arbitrary-path button.
- **Do not treat a share link as non-identifying.** It names a participant and a
  trial (S3). A saved plot config additionally carries every annotation note you
  have typed, for every trial — read it before sending it to a collaborator.
- **Check exported tables before publishing them.** Drop the `image_path` column
  if it is present (S4).
- **Re-upload with a changed row count, or clear the cache, after correcting a
  corpus.** A same-shape edit in the middle of a table does not bust the cache
  (S5).
- **Restart the server after working with a sensitive corpus.** No
  `@st.cache_data` entry in the package sets `ttl` or `max_entries`, so parsed
  tables stay in the process's memory for its whole lifetime — well past the
  browser tab that produced them. **Clear cache** in the ☰ menu does the same
  thing without a restart.

## Limits of this audit

- It covers `scanpath_studio/` and `desktop/` at version 0.25.0. It does not cover
  forks, `other_vis/`, or any modified deployment.
- Dependencies were checked only where a claim depended on them: Streamlit's bind
  default, upload storage, cache storage, config defaults and markdown
  sanitization; CPython's `zipfile` extraction and `tempfile` permissions.
  Streamlit, Plotly, Kaleido, pandas and pyarrow were not audited as a whole. In
  particular, `pandas.read_parquet` / `read_feather` / `read_excel` deserialize
  untrusted uploads through pyarrow and openpyxl, and those parsers were taken on
  trust.
- Streamlit Community Cloud's platform-side logging, retention and isolation were
  not audited and are not ours to describe. See
  [privacy.md](privacy.md#the-hosted-demo).
- No penetration testing was performed. The findings are the result of reading
  the code and reproducing specific behaviours in scripts, not of probing a
  running deployment.
- Nothing here is a warranty. If you find a claim that no longer matches the
  code, please
  [open an issue](https://github.com/lacclab/scanpath-studio/issues).
