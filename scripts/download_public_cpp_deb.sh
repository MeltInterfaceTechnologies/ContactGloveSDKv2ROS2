#!/usr/bin/env bash
# Download the published SDK runtime used for the official-DEB compatibility test.
# Hashes are from the v1.0.0 Release and must be updated with the SDK gitlink.
set -euo pipefail
[[ $# == 2 ]] || { echo "usage: $0 <jammy|noble> <empty-output-directory>" >&2; exit 2; }
codename="$1"
case "$codename" in
  jammy) digest=498b72f00ec4405c642a36aa55fa19b213bdd2cccfaced1fa6e8a55f51c98105 ;;
  noble) digest=4d8529fec723806ea7924088888992bdd1b8e29aaf658aed275ce335049a774b ;;
  *) echo "unsupported codename" >&2; exit 2 ;;
esac
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_commit="$(python3 "${root}/scripts/source_revisions.py" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sdk_commit"])')"
[[ "$sdk_commit" == 8223da430eed7e5e41f601b59732a260d6ce1cd1 ]] || {
  echo "Update the pinned public Release and checksums when changing the SDK gitlink" >&2; exit 1;
}
output="$(realpath -m "$2")"
[[ -z "$(ls -A "$output" 2>/dev/null)" ]] || { echo "output directory must be empty" >&2; exit 2; }
mkdir -p "$output"
name="contactglove-sdk-v2_1.0.0-0${codename}_amd64.deb"
curl --fail --location --proto '=https' --proto-redir '=https' \
  "https://github.com/MeltInterfaceTechnologies/ContactGloveSDKv2Cpp/releases/download/v1.0.0/${name}" \
  --output "${output}/${name}"
printf '%s  %s\n' "$digest" "${output}/${name}" | sha256sum --strict --check
[[ "$(dpkg-deb -f "${output}/${name}" Package)" == contactglove-sdk-v2 ]]
[[ "$(dpkg-deb -f "${output}/${name}" Version)" == "1.0.0-0${codename}" ]]
[[ "$(dpkg-deb -f "${output}/${name}" Architecture)" == amd64 ]]
