#!/bin/zsh
set -e

TRACKER_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$TRACKER_DIR/server.py"
