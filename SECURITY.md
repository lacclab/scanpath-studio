# Security policy

## Reporting a vulnerability

Please report security problems **privately**, not in a public issue:

1. Open the repository's **Security** tab and choose **Report a vulnerability**
   (GitHub's private vulnerability reporting). Only the maintainers see it.
2. If that button isn't there, open a regular issue that says only that you
   have a security report and would like a private channel. Leave out any
   details until a maintainer has replied.

Include what you found, how to reproduce it, and what an attacker could do
with it. We aim to acknowledge a report within a week and to agree on a fix
and a disclosure date with you.

## Supported versions

Fixes go into the latest release on
[PyPI](https://pypi.org/project/scanpath-studio/) and the hosted demo. Older
releases are not patched; upgrade with `pip install -U scanpath-studio`.

## What to know before deploying

Scanpath Studio is a local-first research tool **with no login**. Anyone who
can reach a running server can use everything it serves, including the loaded
data. `scanpath-studio run` and the desktop app therefore listen on this
computer only (`127.0.0.1`); serving on a network is a deliberate
`--server.address` choice, and on such a server local folder access is off
unless `SCANPATH_LOCAL_FS=1`.

A shared deployment should use these settings:

- **Keep the server on loopback when it holds participant data.** A bare
  `streamlit run` listens on every interface; pass
  `--server.address 127.0.0.1`, and reach it remotely through an SSH tunnel.
- **Leave local folder access off.** Supply the corpus location with
  `SCANPATH_DATA_ROOT` instead; `SCANPATH_LOCAL_FS=0` keeps access off even if
  the bind address later changes.
- **Cap uploads on a memory-limited host** with `SCANPATH_MAX_UPLOAD_MB`
  (on Streamlit Community Cloud, as a root-level secret). The browser enforces
  that cap; the server enforces only `server.maxUploadSize`.
- **Hide Streamlit's table download** with `client.disableDataExport = true`
  if the raw tables should not leave the server.
- **Restart the server, or use Streamlit's Clear cache, after working with a
  sensitive corpus.** Parsed tables stay in the server's memory until then.

A share link names a participant and a trial, and a saved plot config also
carries your annotation notes, so read either before sending it on.
