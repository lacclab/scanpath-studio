#!/usr/bin/env bash
# ENG-21: submit one artifact to Apple's notary service, wait, and fail loudly.
#
# Usage: .github/scripts/notarize.sh path/to/artifact.{zip,dmg,pkg}
#
# Factored out of the workflow for two reasons. First, `notarytool submit --wait`
# does not have a trustworthy exit code: a transient CFNetwork timeout while it
# polls for status makes it exit non-zero while Apple is still processing
# happily, so the JSON `status` field is what decides. Second, when a submission
# really is rejected the only useful detail lives in `notarytool log`, which
# nobody remembers to fetch by hand from a failed release build.
#
# Credentials come from the environment (App Store Connect API key):
#   APPLE_API_KEY_ID, APPLE_API_ISSUER_ID, and the .p8 at
#   $RUNNER_TEMP/AuthKey_${APPLE_API_KEY_ID}.p8
set -euo pipefail

ARTIFACT="${1:?usage: notarize.sh <artifact>}"
KEY="${RUNNER_TEMP:?RUNNER_TEMP is unset}/AuthKey_${APPLE_API_KEY_ID:?}.p8"
RESPONSE="$RUNNER_TEMP/notarytool-response.json"

AUTH=(--key "$KEY" --key-id "$APPLE_API_KEY_ID" --issuer "${APPLE_API_ISSUER_ID:?}")

# Read one top-level string field out of the response. Separate calls rather
# than one `read a b`: an absent id prints an empty first field, and word
# splitting would then shift the status into it and misreport the failure.
field() {
  python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as handle:
        print(json.load(handle).get(sys.argv[2], "") or "")
except Exception:
    print("")
' "$RESPONSE" "$1"
}

echo "Submitting $ARTIFACT to the Apple notary service..."
set +e
xcrun notarytool submit "$ARTIFACT" "${AUTH[@]}" \
  --wait --timeout 30m --output-format json > "$RESPONSE"
RC=$?
set -e
cat "$RESPONSE"
echo

ID="$(field id)"
STATUS="$(field status)"

if [ "$STATUS" != "Accepted" ]; then
  echo "::error::notarization of $ARTIFACT finished with status='${STATUS:-unknown}' (notarytool exit $RC)"
  if [ -n "$ID" ]; then
    echo "---- notarytool log $ID ----"
    xcrun notarytool log "$ID" "${AUTH[@]}" /dev/stdout || true
  else
    echo "No submission id was returned — check the credentials and the artifact format."
  fi
  exit 1
fi

echo "Notarization accepted (submission $ID)."
