# Privacy & where your data goes

Scanpath Studio is a visualization tool, not a service. It has no accounts, no
backend of ours, and no analytics of ours. No code path in the package sends the
eye-tracking data you load anywhere, and none writes your tables to disk — the
[three things that do write](#what-does-touch-the-disk) are spelled out below.

That is the easy half. The harder half — who can reach the server while it is
running, what Streamlit itself sends, and what ends up inside a file you hand to
someone — follows, verified against the code rather than assumed. Where
something could not be verified, it says so instead of reassuring you.

The engineering counterpart to this page is the
[security audit](security.md), which cites the exact
`module.py:function` behind each finding.

## The short version

| Deployment | Where your data lives | Who else can reach it |
| --- | --- | --- |
| **Local install** (`pip` / source) | Memory of the Streamlit process on your machine | **Anyone who can reach the port** — Streamlit binds every interface by default and has no login |
| **[Desktop bundle](desktop.md)** | Memory of the bundled server | **Same** — the launcher does not restrict the bind address either |
| **[Hosted demo](https://scanpath-studio.streamlit.app)** | Memory of a container Streamlit Community Cloud (Snowflake) operates | Anyone with the URL, plus the platform operator — see [below](#the-hosted-demo) |

!!! warning "Human-participant data"
    Run it locally or from the desktop bundle, and read
    [Anyone who can reach the port](#anyone-who-can-reach-the-port) first — "local"
    does **not** mean "loopback only" out of the box. Do not put identifiable
    recordings on the hosted demo: that is third-party infrastructure with no
    authentication and no agreement covering your data.

## Where an upload actually goes

Tracing an upload through the code:

- **The upload itself.** `st.file_uploader` hands the bytes to Streamlit's
  `MemoryUploadedFileManager`, which keeps them in a per-session dictionary in
  the server process's RAM under a server-generated `uuid4` and drops the whole
  entry when the session ends (`remove_session_files`). No spooling to a temp
  directory.
- **Parsing and normalization.** The parsed and normalized tables are held by
  `@st.cache_data` (`_read_uploaded_table_cached`, `_normalize_pair_cached`,
  and the per-view aggregation caches). Every one of them uses the defaults —
  `persist=None`, so **memory only, never disk**; `ttl=None` and
  `max_entries=None`, so an entry is **not** evicted on a timer. This cache is
  global to the *process*, not to your session, so a parsed table outlives the
  browser tab that produced it. Restarting the server clears it; so does
  **Clear cache** in the ☰ menu, which Streamlit shows on local runs.
- **Cache keys.** The parse cache is keyed on the upload's server-generated
  `uuid4` plus its filename and size, so no other session can address your entry.
  The downstream normalization and analysis caches are keyed on a *content
  fingerprint* (`data.frame_fingerprint` — row count, column names, and a hash of
  the first and last rows). Two sessions that load the same table therefore share
  one cached result. That is only reachable with matching content, not by
  guessing, but it is worth knowing on a server several people use.
- **Datasets you finish in the wizard.** Stored in
  `st.session_state["_datasets"]` — session memory. There is no on-disk dataset
  store; closing the session discards them and you re-upload next time.
- **Annotations** (favourites, tags, notes) live in session state only. The
  only way they persist is the JSON you download yourself.
- **Exports.** The bulk-export zip is assembled entirely in an `io.BytesIO`
  buffer and handed to the browser as a download; Streamlit serves download and
  media payloads from `MemoryMediaFileStorage`, also RAM.

### What does touch the disk

Three things, none of which is a copy of your tables — but all three are real
writes, so they are stated rather than glossed:

!!! note "1 · MP4 export writes one temporary file"
    `animation_export.encode_mp4` writes the encoded video to a
    `tempfile.NamedTemporaryFile(suffix=".mp4")` in your system temp directory,
    reads it back, and unlinks it in a `finally` block. It contains rendered
    frames of the figure, not your tables. A hard kill (SIGKILL, power loss)
    during encoding can leave the file behind.

!!! note "2 · Static export runs a headless Chrome with a temp profile"
    PNG / SVG / PDF — and the rasterized GIF / MP4 — go through Kaleido, which
    launches Chrome with `--user-data-dir=<temporary directory>`
    (`choreographer/browsers/chromium.py`). The directory is created and removed
    per session. The figure is passed into the page rather than written to that
    directory, but **we have not audited what Chrome itself caches inside its
    own profile**, so "static export writes nothing to disk" is not a claim we
    make. Interactive HTML export runs no browser at all.

!!! note "3 · Downloading a public corpus writes that corpus"
    The ⬇ **Download** buttons for OneStop and PoTeC write the fetched archives
    and extracted files into the directory *you* name — via a `.part` temp file
    renamed into place. That is data arriving from OSF/GitHub, not your data
    leaving, but it is the one path where the app creates files you did not.

CSV, Parquet, JSON and HTML export never touch the disk on the server side; the
bytes go straight to your browser's download.

## Anyone who can reach the port

This is the part most likely to surprise you, and it is not specific to Scanpath
Studio — it is how Streamlit ships.

- **Streamlit has no authentication.** No login, no token, no per-user
  authorization anywhere in this codebase. Whoever can open the URL gets the
  running app: the loaded corpus, any upload, the annotations.
- **The default bind address is every interface.** `server.address` defaults to
  unset, and Streamlit falls back to `0.0.0.0`
  (`DEFAULT_SERVER_ADDRESS` in `streamlit/web/server/starlette/`). This is why a
  plain `streamlit run` prints a **Network URL** with your LAN address next to
  the Local URL — that URL works from any other machine on the network. Neither
  the repo's `.streamlit/config.toml` nor `desktop/launcher.py` overrides it.
- **The desktop bundle is no different.** It prints and opens
  `http://127.0.0.1:<port>`, but it passes no `--server.address`, so the server
  still listens on all interfaces.

On a laptop behind a home router this is usually harmless. On a shared lab
network, a university VLAN, or a machine with a public IP, it is not. To bind
loopback only, pass the address on the command line:

```bash
scanpath-studio --server.address=127.0.0.1
```

The desktop bundle builds its own argument list and forwards nothing from the
command line, so set it in Streamlit's global config instead — which also covers
every other way you launch the app:

```toml
# ~/.streamlit/config.toml
[server]
address = "127.0.0.1"
```

!!! danger "Fix this before loading a participant corpus on a shared network"
    Nothing in the app narrows the bind for you, and the app's own UI never says
    it is reachable from outside the machine — the only hint is the **Network
    URL** line in the terminal banner at startup.

## What leaves the machine

### Corpus downloads (data coming *in*)

The **only** outbound calls made by Scanpath Studio's own code are in
`datasets.py`:

| Call | URL | Purpose |
| --- | --- | --- |
| `download_onestop` | `https://osf.io/download/<id>` | Fetch OneStop reports from OSF |
| `download_potec` | `https://osf.io/download/<id>` | Fetch the PoTeC eye-tracking archive |
| `download_potec` | `https://raw.githubusercontent.com/DiLi-Lab/PoTeC/main/…` | Fetch PoTeC stimulus AOI files |

These are plain `urllib.request.urlopen` **GET**s for public corpora. They carry
no request body, no identifier, and nothing derived from data you loaded — they
are downloads of published datasets, triggered only when you click **Download**
for that corpus (or pass `download=True` headlessly). Like any download, your IP
address is visible to OSF and GitHub. That is data coming *in*, not your data
going *out*.

There is no other network-capable import in the package: no `requests`,
`httpx`, `socket`, `smtplib`, or cloud SDK. (`url_state.py` imports
`urllib.parse.urlencode`, which builds a query string and opens no connection;
`desktop/launcher.py` uses `socket` to pick a free port and `urllib` to poll
`http://127.0.0.1:<port>/_stcore/health` — both loopback only.)

### Requests Streamlit, Plotly and Kaleido make anyway

None carries your data. All are requests to a third party, so they are worth
knowing about — especially on an air-gapped lab machine.

- **Streamlit looks up your public IP on a headless launch.** When
  `server.headless` is true, `streamlit.net_util.get_external_ip()` does a
  **plain-HTTP** `GET http://checkip.amazonaws.com` (1 s timeout, HTTPS
  fallback) to print the "External URL" banner. The desktop bundle sets
  `--server.headless=true` on every launch, so **the desktop build makes this
  call at startup**; a Linux box with no `DISPLAY` defaults to headless too. On
  macOS and Windows a normal `streamlit run` is not headless and skips it,
  though the same lookup can fire later if you reach the app by a non-loopback
  hostname (it backs the origin allowlist).
- **The scanpath plot loads Plotly from a CDN.** The true-to-scale chart embeds
  the figure with `include_plotlyjs="cdn"`, so your browser fetches
  `https://cdn.plot.ly/plotly-3.3.1.min.js`. The CDN sees your IP, User-Agent and
  referrer; the figure itself is already in the page your own server sent, and is
  never posted anywhere. This also means the spatial plot needs network access —
  it will not render on a fully air-gapped machine.
- **Exported HTML figures load Plotly from the same CDN.** Both the single-trial
  HTML download and the bulk-export `figure.html` use `include_plotlyjs="cdn"`,
  so the *recipient's* browser fetches from `cdn.plot.ly` when they open the
  file. Your data is inside the file; only the plotting library comes over the
  network. The headless writers (`api.save_figure`, `scanpath-studio render`)
  use Plotly's default and **inline** the library instead, producing a
  self-contained file — use those if the figure has to open offline.
- **Static export loads MathJax from a CDN.** Kaleido's render page loads
  `plotly.min.js` from a local `file://` path inside your Python environment, but
  MathJax from
  `https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.5/MathJax.js`. Again: a
  script fetch, no data in it. We have not tested whether export still succeeds
  with that request blocked.

## Streamlit's own usage statistics

This is Streamlit's telemetry, not ours, and it is the one thing that is **on by
default** if you do nothing.

- Streamlit's `browser.gatherUsageStats` defaults to **`true`**. When on, the
  frontend fetches its metrics endpoint from
  `https://data.streamlit.io/metrics.json` and posts usage events to it, and the
  server writes a random `uuid4` to `~/.streamlit/machine_id_v4` (that file is
  not created at all when the flag is off). A second id, `machine_id_v3`, is a
  `uuid5` hash of `/etc/machine-id` or `/var/lib/dbus/machine-id` where those
  exist — and of the machine's **MAC address** (`uuid.getnode()`) otherwise,
  which is the macOS and Windows case. It is a hash, not the address itself, but
  it is stable per machine rather than per install.
- The repository ships `.streamlit/config.toml` with
  `gatherUsageStats = false`. **But Streamlit resolves that file relative to the
  directory you launch from, and it is not part of the wheel** — the packaging
  config ships only `sample_data`. So:

=== "Source checkout"

    Off. You launch from the repo root, so `.streamlit/config.toml` applies.

=== "`pip install scanpath-studio`"

    **On**, unless you turn it off. Launching `scanpath-studio` from your own
    working directory does not see the repo's config, and the CLI injects only
    the `--theme.*` flags, not this one. Turn it off with either:

    ```bash
    scanpath-studio --browser.gatherUsageStats=false
    ```

    ```toml
    # ~/.streamlit/config.toml — applies to every Streamlit app you run
    [browser]
    gatherUsageStats = false
    ```

=== "Desktop bundle"

    Off. `desktop/launcher.py` passes `--browser.gatherUsageStats=false`
    explicitly on every launch, independent of the working directory.

=== "Hosted demo"

    Off. Community Cloud runs the app from the repo root, so the deployed
    `.streamlit/config.toml` applies. This flag governs the *frontend* telemetry
    only — it says nothing about the platform's own server-side logging.

!!! danger "With usage stats on, the URL — including a deep link's participant id — is transmitted"
    Streamlit's metrics event carries `contextPageUrl: window.location.href` and
    `contextPageSearch: window.location.search` (verified in the bundled
    frontend's `MetricsManager.getContextData`). A Scanpath Studio share link
    puts `participant=<participant_id>` and `trial_id=<trial_id>` in that query
    string. So on a **pip install that has not turned usage stats off**, opening
    a deep link sends those identifiers to Streamlit's telemetry endpoint along
    with your locale, timezone and User-Agent. Turning `gatherUsageStats` off
    stops the whole event.

!!! note "Streamlit's first-run email prompt"
    On a first `streamlit run`, Streamlit itself may ask for an email address.
    If you type one, `credentials._send_email` reads an endpoint from
    `https://data.streamlit.io/metrics.json` and POSTs the address there as both
    `author_email` and `userId`. Press Enter to leave it blank and nothing is
    sent (the function returns early on a blank value). The prompt is skipped
    entirely when `server.headless=true`, so the desktop bundle never shows it.
    This prompt belongs to Streamlit, not to Scanpath Studio.

We verified the config gate, the endpoints, the machine-id files, and the URL
fields in the event. We did **not** enumerate the full payload field by field —
for that, see [Streamlit's privacy policy](https://streamlit.io/privacy-policy).

## Cookies and browser storage

Three things can end up in your browser. Only the first is ours.

| Name | Set by | When | Contents |
| --- | --- | --- | --- |
| `sps_tour_optout` | Scanpath Studio (`tour.py`) | You tick "Don't show this again" | `"1"`. One year, `path=/`, `SameSite=Lax`, first-party. No identifier. |
| `_streamlit_xsrf` | Streamlit | Always (`server.enableXsrfProtection` defaults on) | A CSRF double-submit token. Deliberately not `HttpOnly` — the frontend must read it. |
| `ajs_anonymous_id` | Streamlit | **Only when usage stats are on** | A random analytics id, written to both a one-year cookie and `localStorage` (alongside `stMetricsConfig`). |

Turning `gatherUsageStats` off removes the third one. Scanpath Studio itself
reads no cookie other than its own and stores nothing in `localStorage`.

## What a share link and a saved config contain

Both are things you hand to someone else, so here is exactly what is in them.

**A Share link** (🔗 **Share** subtab) is a query string of view settings plus:

- `source=` — which built-in data source to reopen (demo / OneStop / MultiplEYE
  / synthetic / public OneStop), and for public OneStop its variant, regime and
  parts.
- `participant=<participant_id>` and `trial_id=<trial_id>` — **the identifiers
  from your data, verbatim.** In most reading corpora a participant id is a
  pseudonym, but it is still a per-person key: a share link is a document that
  names a specific participant and trial. Treat it accordingly — and see the
  telemetry warning above, which is the same fact from the other direction.
- **Column names you selected** — `color_by`, `highlight_column`, `x_field`,
  `y_field`, `word_hover_measure`. These are names from your table's header, so
  a link can reveal what columns your dataset has.

It does **not** contain fixation coordinates, durations, word text, measures, or
any file path. If your data came from an upload or a stored dataset, the link
cannot rebuild it and the Share panel says so — the recipient has to load the
same data themselves.

**A saved config** (💾 **Save & restore** → *Download (JSON)*) is a superset:
everything above, plus

- `column_mapping` — every `col_map_*` choice, i.e. **your source column
  names**;
- `data_source` — the label of the source you were on;
- `annotations` — **all** favourites, tags and **free-text notes**, each keyed by
  `(participant_id, trial_id)`.

The notes field is the one to check before mailing this file around: it is
whatever you typed about a given participant's trial. The config still contains
no fixation or word rows.

## What an export contains

An exported table (Export subtab → CSV / Parquet, single-trial or bulk) is your
data, so no surprises there — with one:

!!! warning "Exported fixation tables can carry an absolute path from your machine"
    Datasets that ship a stimulus image (the bundled demo, MultiplEYE) carry an
    `image_path` column, and normalization resolves it to an **absolute** local
    path. It survives into `fixations.csv` and `aggregate/all_fixations.csv`.
    On the bundled sample the exported value is literally
    `/Users/<you>/…/scanpath_studio/sample_data/images/2_1_1_Ele__paragraph.png` —
    so the file reveals your username and directory layout. Drop the column
    before sharing an export if that matters. Exported *figures* are clean:
    images are inlined as `data:` URIs, not referenced by path.

A debug export (only reachable with `?debug=1` plus the 🐛 **Debug mode** toggle)
contains captured log lines, the loaded frames' row/column counts, and the
selected participant id — no data rows.

## Per deployment

### Local install

The server runs on your machine and your browser talks to it over the loopback
interface — but the server itself listens on every interface unless you say
otherwise, and there is no login. See
[Anyone who can reach the port](#anyone-who-can-reach-the-port); on a shared
network, set `server.address = "127.0.0.1"` before you load a participant
corpus.

Your data itself never leaves the machine. The outbound traffic is the corpus
downloads you trigger, the CDN script fetches your browser makes, and — on a
headless Linux box — Streamlit's public-IP lookup. None of them carries a row of
your data.

### Desktop bundle

The [bundled launcher](desktop.md) improves on a plain pip install in one
respect — it disables Streamlit's usage statistics explicitly rather than
relying on the working directory, which also means it never shows the email
prompt. Two things it does **not** do, despite printing a `127.0.0.1` URL:

- it does not restrict the bind address, so the same LAN exposure applies;
- it runs headless, which triggers the `checkip.amazonaws.com` public-IP lookup
  at startup.

Add `address = "127.0.0.1"` to `~/.streamlit/config.toml` and it becomes the
simplest private-corpus setup available: no Python toolchain, usage stats
already off, and nothing listening beyond loopback. The public-IP lookup still
fires at startup unless you block it.

### The hosted demo

<https://scanpath-studio.streamlit.app> runs on **Streamlit Community Cloud**, a
free service operated by Snowflake. It exists so you can try the tool on the
bundled OneStop sample without installing anything.

What is true there, from the same code paths as everywhere else:

- Uploads go to that container's process memory, not to a disk or a database.
- Session state — stored datasets, annotations, filters — is per-session and
  dies with the session.
- Streamlit's frontend usage statistics are off (the deployed repo's config
  applies).
- We do not receive, read, or store anything you upload. We have no access to
  the container.

What we cannot promise, and will not pretend to:

- **The machine is not ours.** Streamlit Community Cloud's operator controls the
  container: they can restart it, collect platform logs, and set their own
  retention. `gatherUsageStats` governs the browser-side event stream, not the
  platform's own instrumentation. Their terms govern, not ours. We have not
  audited what they log.
- **One process serves everyone.** All concurrent visitors share a single
  Streamlit process. Uploads are isolated per session id and the parse cache is
  keyed on a server-generated `uuid4`, so nobody can pull your table out of the
  cache by guessing — but the bytes of every visitor's data sit in one process's
  memory at the same time, and the downstream caches are content-keyed (see
  above). A bug or a crash dump in that process is a shared blast radius.
- **There is no login.** Anyone with the URL uses the same app.
- **It is small.** The app's own upload warning assumes roughly 1 GB of RAM and
  asks you to confirm before parsing a large corpus, because parsing it can kill
  the process. We have not independently verified the container's limit.

!!! danger "Do not upload identifiable participant data to the hosted demo"
    Use it with the bundled sample, a public corpus, or de-identified data you
    would be comfortable posting publicly. For anything covered by an ethics
    approval, a consent form, or a data-use agreement, run Scanpath Studio
    locally ([install](getting-started.md#install)) or use the
    [desktop build](desktop.md).

## Limitations of this statement

Stated plainly, so you can judge what is claim and what is verified fact:

- Everything above about **Scanpath Studio's own code** was read out of this
  repository at v0.25.0, against Streamlit 1.58, Plotly 6.5.2 and CPython 3.12.
  It describes this code, not any fork or modified deployment.
- **Streamlit's telemetry payload** was not enumerated field by field. We
  verified that `browser.gatherUsageStats` gates it, that the endpoint is
  discovered via `data.streamlit.io/metrics.json`, that machine ids are written
  to `~/.streamlit/` and derived from the MAC address as a fallback, and that
  the event carries the page URL and query string.
- **What Chrome writes into Kaleido's temporary profile directory** during
  static export was not audited.
- **Streamlit Community Cloud's platform-side logging and retention** were not
  audited and are not ours to describe. Treat the hosted demo as a third party.
- **Dependencies** (Streamlit, Plotly, Kaleido, pandas, and their transitive
  dependencies) were not audited end to end for network activity. The requests
  documented above are the ones we found and confirmed.
- **Offline behaviour** was not tested: the plot needs the Plotly CDN, the
  Kaleido render page references a MathJax CDN, and a headless launch tries
  `checkip.amazonaws.com`. We have not measured what degrades on a machine with
  no outbound access.

Found something here that does not match the code? Please
[open an issue](https://github.com/lacclab/scanpath-studio/issues) — a privacy
statement that has drifted from the implementation is worse than none.
