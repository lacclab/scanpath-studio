# Privacy

For sensitive participant data, use the desktop app or run Scanpath Studio on your own machine. Do not upload identifiable recordings to the hosted demo.

| Where you run it        | Where the data is processed                              |
| ----------------------- | -------------------------------------------------------- |
| desktop app             | your machine                                             |
| local `scanpath-studio` | your machine                                             |
| hosted demo             | a Streamlit Community Cloud server operated by Snowflake |

## What happens to a file you upload

Completed datasets, mappings, view settings, and annotations are stored in an on-device recovery cache so a refresh does not erase the session. This happens only when the app listens on this machine alone — the desktop app, or a launch with `server.address` set to `127.0.0.1`, `::1` or `localhost` — or when you opt in with `SCANPATH_STUDIO_PERSIST=1`. A server other machines can reach stores nothing: a hosted deployment, and a bare `streamlit run`, which listens on every interface.

The cache is visible and removable from inside the app: 💾 **Session → 🗄️ Automatic recovery** (the dialog the nav's 💾 Session entry opens) names the folder, reports what is stored and how large it is, pauses saving for the session (**Save changes automatically**), and deletes the stored copy (**🗑 Clear recovery cache**, which leaves saving on). The same from a terminal, with the app closed:

```
scanpath-studio cache                       # what is stored, where, how big
scanpath-studio cache --clear               # delete it
SCANPATH_STUDIO_PERSIST=0 scanpath-studio   # disable recovery storage
SCANPATH_STUDIO_STATE_DIR=/secure/path scanpath-studio   # store it elsewhere
```

The cache holds the research tables themselves, not just settings — treat that folder like the data files it came from (disk encryption, shared-machine accounts). It is single-user and unencrypted: anyone with your account on that machine can read it.

Exporting an **MP4** replay also writes to disk: the encoder needs a real file, so the clip is written to a temporary file in the system's temp folder (readable by your account only) and deleted as soon as it has been read back. Only a crash or a forced kill mid-encode leaves it behind, and it holds the rendered frames, not your tables.

## The online demo

The public demo has no account or data-use agreement. Use it with the bundled sample or data you are comfortable sending to the hosting provider. Sessions are temporary and server resources are limited.

## What's in a link, a config file, and an export

- A **share link** contains the participant and trial IDs plus the visualization settings. It does not contain the data tables — except for a scanpath made with **✏️ Author a scanpath**, whose link carries the typed text and every hand-placed fixation, because they *are* its data.
- A **saved configuration** (JSON backup) can contain column names, annotation notes, and every row of any attached participant, trial or text metadata table.
- An **exported table** contains the selected research data.

Review these artifacts before sharing them. Share links can enter browser history, logs, or chat previews, so do not copy one when its participant or trial identifiers should not be exposed there.

## Network activity

Downloading a public corpus contacts its host, and only when you click **⬇ Download** — or, headlessly, the first time `scanpath-studio render --potec` or `--onestop` (the Public variant) runs against a folder that doesn't have it yet. The scanpath, animation and comparison figures load the Plotly charting library from the app's own server — the copy installed with the app — so drawing a figure contacts no other host and works without an internet connection, the desktop app included. A figure you download as **HTML** is different: a saved file has no app server behind it, so it loads the library from **cdn.plot.ly** when you open it, which needs an internet connection and tells that host the file was opened (no data travels with the request). HTML written headlessly (`save_figure`, `scanpath-studio render -o figure.html`) embeds the library instead and makes no request. Streamlit's own usage statistics are switched off on every launch path (`scanpath-studio run`, the desktop app and the repository's `.streamlit/config.toml`). The application adds no analytics service of its own.
