#!/bin/sh
# Keep deployment-only commits while advancing stable to a release.
set -eu

release=$(git rev-parse --verify "${1:?Pass the release ref}^{commit}")
git fetch origin stable
git switch --detach origin/stable
git merge --no-edit "$release"
git push origin HEAD:refs/heads/stable
