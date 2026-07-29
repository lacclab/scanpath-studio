# Privacy — where your data goes

**Short answer: nowhere.** Scanpath Studio has no accounts, no server of ours,
and no analytics of ours. The data you load stays in the memory of the app while
it's running and disappears when you close it. Nothing in the code writes your
tables to disk, and nothing sends them anywhere.

There are a few things worth knowing anyway — mostly about *who else can open the
app while it's running*. Those are below.

If you want the technical version, with the exact function behind each claim,
that's the [security audit](security.md).

## The short version

| How you run it | Where your data is | Who else can reach it |
| --- | --- | --- |
| **On your own machine** (`pip` or source) | In memory, on your machine | Anyone on your network, unless you change one setting — see [below](#one-thing-to-set-on-a-shared-network) |
| **[Desktop app](desktop.md)** | In memory, on your machine | Nobody — it listens on your machine only |
| **[Online demo](https://scanpath-studio.streamlit.app)** | In memory on a server run by Streamlit (Snowflake), not by us | Anyone with the link, plus that company — [see below](#the-online-demo) |

!!! warning "Working with participant data?"
    Use the desktop app, or run it locally after reading
    [the one setting](#one-thing-to-set-on-a-shared-network) below. Don't put
    identifiable recordings on the online demo — that's someone else's server,
    with no login and no agreement covering your data.

## What happens to a file you upload

It's read into memory and parsed. That's it — there's no database, no upload
folder, nothing written to disk. Close the tab or restart the app and it's gone.
The same goes for datasets you build in the wizard, and for your favourites,
tags and notes: those only persist if you download the JSON yourself.

The one wrinkle worth knowing on a **shared** server: the parsed results are
cached per *app process*, not per person. Two people who load the identical file
share one cached copy. Nobody can pull your data out of that cache without
already having the same file, but on a machine several people use, it's worth
knowing the caching is shared.

**What does get written to disk:** exporting an MP4 writes one temporary video
file and deletes it afterwards. Exporting a PNG, SVG or PDF runs a headless
Chrome in a temporary folder, also cleaned up — your figure is passed into it
rather than written there, though we haven't checked what Chrome caches for
itself. And downloading a public corpus (OneStop, PoTeC) writes that corpus into
the folder you name, which is the point. CSV, Parquet, JSON and HTML exports go
straight to your browser without touching the server's disk.

## One thing to set on a shared network

This one is worth two minutes, and it isn't specific to Scanpath Studio — it's
how Streamlit ships.

**A plain `streamlit run` listens on your whole network, and there's no login.**
That's why the startup banner prints a "Network URL" next to the local one — that
address works from any other machine on the network, and whoever opens it sees
your loaded data.

On a home network that's usually harmless. On a lab network, a university VLAN,
or anything with a public IP, it isn't. To limit it to your own machine:

```bash
scanpath-studio --server.address=127.0.0.1
```

Or set it once for every Streamlit app you run:

```toml
# ~/.streamlit/config.toml
[server]
address = "127.0.0.1"
```

!!! tip "The desktop app already does this"
    The [desktop build](desktop.md) binds to your machine only, so there's
    nothing to configure. If you work with participant data and don't want to
    think about this, that's the setup to use.

If your app should be reachable but shouldn't offer a filesystem browser, set
`SCANPATH_LOCAL_FS=0` to hide the "Data directory" box, or `SCANPATH_DATA_ROOT`
to confine it to one folder.

## What leaves your machine

Your data: nothing. But a few requests do go out, and none of them carries a row
of your data:

- **Downloading a public corpus.** When you click ⬇ Download for OneStop or
  PoTeC, the app fetches those published datasets from OSF and GitHub. That's
  data coming *in*. Like any download, those sites see your IP address.
- **The plotting library.** The scanpath view loads Plotly from a public CDN, so
  the plot needs an internet connection. Your figure is already in the page — only
  the library comes over the network. The same applies to an HTML figure you
  export and send to someone: their browser fetches Plotly when they open it. If
  the figure has to work offline, use the [Python API](api.md) or the
  `scanpath-studio render` command, which bundle the library into the file.

There's nothing else. No `requests`, no cloud SDK, no telemetry of ours anywhere
in the package.

**Streamlit's own usage statistics** are a separate thing, and they're on by
default in Streamlit generally. Scanpath Studio turns them off on every way you
launch it — the desktop app, `scanpath-studio` from a pip install, and the
deployed demo. If you launch via `streamlit run` yourself, add
`gatherUsageStats = false` under `[browser]` in `~/.streamlit/config.toml`.

This matters more than it sounds: with those statistics on, Streamlit's telemetry
receives the page URL — and a Scanpath Studio share link can carry a participant
ID in it (see below for how to leave it out).

## What's in a link, a config file, and an export

These are the things you hand to other people, so here's exactly what's in them.

**A share link** (🔗 Share) carries your view settings, which data source to
open, and — this is the one to notice — by default **the participant ID and trial
ID, verbatim from your data**, plus the names of any columns you picked. In most
corpora a participant ID is a pseudonym, but it still names one person, and a
link lands in browser history, server logs and chat previews.

The Share panel's **What the link includes** picker decides how much identity
travels:

| Mode | The link carries | Opens on |
| --- | --- | --- |
| **Participant + trial** (default) | Both ids | The exact trial |
| **Trial only** | The trial id, no participant | The same trial — it falls back to matching on the trial id alone |
| **Settings only** | Neither id | Whatever trial the recipient already has selected |

A link never contains fixations, durations, word text or measures; if your data
came from an upload, the recipient has to load it themselves.

**A saved config** (💾 Save & restore → Download JSON) has all of that plus your
column names and **all your notes** — the free text you typed about each trial.
That's the field to check before emailing the file around.

**An exported table** is your data, so no surprises. Local file paths are
stripped out before the file is written, so an export won't reveal your username
or folder layout.

## The online demo

<https://scanpath-studio.streamlit.app> runs on Streamlit Community Cloud, a free
service operated by Snowflake. It's there so you can try the tool without
installing anything.

We don't receive, read or store anything you upload — we have no access to that
machine at all. But that cuts both ways, and here's what we can't promise:

- **The machine isn't ours.** Snowflake runs it; they can restart it, collect
  their own logs, and set their own retention. Their terms apply, not ours. We
  haven't audited what they log.
- **There's no login.** Anyone with the link uses the same app.
- **Everyone shares one process.** Sessions are isolated from each other, but all
  visitors' data sits in one server's memory at the same time.
- **It's small.** It has roughly 1 GB of memory, so a large corpus can crash it.

!!! danger "Don't upload identifiable participant data here"
    Use it with the bundled sample, a public corpus, or data you'd be comfortable
    posting publicly. For anything under an ethics approval, a consent form, or a
    data-use agreement, run it [locally](getting-started.md#install) or use the
    [desktop build](desktop.md).

## What we didn't check

So you know where the line is between "we verified this" and "we assume this":

- Everything about **our own code** was read out of this repository against
  Streamlit 1.58 and Plotly 6.5.2. It describes this code, not a fork.
- We didn't enumerate **Streamlit's telemetry payload** field by field — see
  [their privacy policy](https://streamlit.io/privacy-policy).
- We didn't audit what **Chrome writes into its temporary folder** during image
  export.
- We didn't audit **Streamlit Community Cloud's** own logging. Treat the online
  demo as a third party.
- We didn't audit **our dependencies** end to end for network activity.
- We haven't tested how much works **fully offline** — the plot needs the Plotly
  CDN at minimum.

Found something here that doesn't match the code? Please
[open an issue](https://github.com/lacclab/scanpath-studio/issues) — a privacy
page that's drifted from the implementation is worse than none.
