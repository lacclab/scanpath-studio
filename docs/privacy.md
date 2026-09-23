# Privacy

For sensitive participant data, use the desktop app or run Scanpath Studio on
your own machine. Do not upload identifiable recordings to the hosted demo.

| Where you run it | Where the data is processed |
| --- | --- |
| desktop app | your machine |
| local `scanpath-studio` | your machine |
| hosted demo | a Streamlit Community Cloud server operated by Snowflake |

## What happens to a file you upload

Uploaded tables are parsed locally. Completed datasets, mappings, view settings,
and annotations are stored in an on-device recovery cache so a refresh does not
erase the session. This happens only when the app listens on this machine
alone — the desktop app, or a launch with `server.address` set to `127.0.0.1`,
`::1` or `localhost` — or when you opt in with `SCANPATH_STUDIO_PERSIST=1`. A
server other machines can reach stores nothing: a hosted deployment, and a bare
`streamlit run`, which listens on every interface. The app decides this from the
address its own server is bound to, never from the address a browser reports,
which any client on the network could set to `localhost`.

The cache is visible and removable from inside the app: 💾 **Session →
🗄️ Automatic recovery** (the dialog the nav's 💾 Session entry opens) names the
folder, reports what is stored and how large it
is, pauses saving for the session, and deletes the stored copy (**Forget saved
session**). The same from a terminal, with the app closed:

```bash
scanpath-studio cache                       # what is stored, where, how big
scanpath-studio cache --clear               # delete it
SCANPATH_STUDIO_PERSIST=0 scanpath-studio   # disable recovery storage
SCANPATH_STUDIO_STATE_DIR=/secure/path scanpath-studio   # store it elsewhere
```

The cache holds the research tables themselves, not just settings — treat that
folder like the data files it came from (disk encryption, shared-machine
accounts). It is single-user and unencrypted: anyone with your account on that
machine can read it.

The desktop app binds to your machine only. A direct Streamlit launch may listen
on the local network; on a shared or untrusted network, bind explicitly:

```bash
scanpath-studio --server.address=127.0.0.1
```

## The online demo

The public demo has no account or data-use agreement. Use it with the bundled
sample, public corpora, or data you are comfortable sending to the hosting
provider. Sessions are temporary and server resources are limited.

## What's in a link, a config file, and an export

- A **share link** contains the participant and trial IDs plus the visualization
  settings. It does not contain the data tables.
- A **saved configuration** can contain column names and annotation notes.
- An **exported table** contains the selected research data.

Review these artifacts before sharing them. Share links can enter browser
history, logs, or chat previews, so do not copy one when its participant or
trial identifiers should not be exposed there.

## Network activity

Downloading a public corpus contacts its host. Interactive plots may load
Plotly in the browser. The application does not add its own analytics service.

The code-level audit and accepted limitations are in the
[security audit](security.md).
