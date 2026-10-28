#!/bin/sh
# Re-capture every picture of the app the README and the docs site show: the
# screenshots, the All controls pictures, the workflow GIFs and videos, the
# homepage montages with their PDF stills, and the README / docs-home demo.
# Each script starts its own app from this checkout, at the bundled demo's
# defaults, so run it from the commit whose UI the media should show.
#
#   sh scripts/refresh_docs_media.sh
#
# Needs ffmpeg on PATH, and OneStop under data/OneStop: the annotated Scanpath
# overview draws its ordinary-reading corpus, whose trials have several
# screens. Takes about half an hour; look through the result before committing.
set -eu
cd "$(dirname "$0")/.."

run() {
	echo "== $*"
	uv run --with playwright python "$@"
}

run scripts/capture_docs_screenshots.py
run scripts/capture_docs_screenshots.py --overview
run scripts/capture_docs_screenshots.py --controls
run scripts/record_workflow_demos.py
# The montages cut from the workflow videos just recorded.
run scripts/edit_docs_workflows.py --stills
run scripts/record_app_demo.py
