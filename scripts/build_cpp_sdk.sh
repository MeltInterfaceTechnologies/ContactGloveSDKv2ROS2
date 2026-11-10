#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 2 ]]; then
  echo "usage: $0 <jammy|noble> <empty-output-directory>" >&2
  exit 2
fi
codename="$1"
output="$(realpath -m "$2")"
case "$codename" in jammy|noble) ;; *) echo "unsupported codename" >&2; exit 2 ;; esac
: "${PACKAGE_BUILD_ID:?Set PACKAGE_BUILD_ID to an immutable, unique numeric build ID and attempt (e.g. 12345.1)}"
[[ "$PACKAGE_BUILD_ID" =~ ^[1-9][0-9]*\.[1-9][0-9]*$ ]] || { echo "invalid PACKAGE_BUILD_ID" >&2; exit 2; }
. /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_CODENAME:-}" != "$codename" || "$(dpkg --print-architecture)" != amd64 ]]; then
  echo "Build on the matching Ubuntu release for amd64" >&2
  exit 2
fi
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk="${root}/vendor/contactglove-sdk-v2"
if [[ ! -f "${sdk}/CMakeLists.txt" ]]; then
  echo "C++ SDK submodule missing. Run git submodule update --init --recursive." >&2
  exit 1
fi
[[ -z "$(ls -A "$output" 2>/dev/null)" ]] || { echo "output directory must be empty" >&2; exit 2; }
mkdir -p "$output"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
python3 "${root}/scripts/source_revisions.py" > "$work/revisions.json"
actual="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sdk_commit"])' "$work/revisions.json")"
ros_revision="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["ros2_commit"])' "$work/revisions.json")"
cmake -S "$sdk" -B "$work/build" -DCMAKE_BUILD_TYPE=Release \
  -DCONTACTGLOVE_PACKAGE_DEB=ON -DCONTACTGLOVE_DEB_DISTRIBUTION="$codename"
cmake --build "$work/build" --parallel 2
cpack --config "$work/build/CPackConfig.cmake" -B "$output" \
  -D "CPACK_DEBIAN_PACKAGE_RELEASE=1${codename}+ros2.${PACKAGE_BUILD_ID}"
shopt -s nullglob
debs=("$output"/contactglove-sdk-v2_*.deb)
[[ ${#debs[@]} == 1 ]] || { echo "expected one native SDK DEB" >&2; exit 1; }
sdk_pkg_version="$(dpkg-deb -f "${debs[0]}" Version)"
dpkg --compare-versions "$sdk_pkg_version" gt "${sdk_pkg_version%%-*}-0${codename}" || {
  echo "generated package must upgrade the previously shipped SDK" >&2; exit 1;
}
python3 - "${debs[0]}" "$actual" "$ros_revision" "$codename" "$PACKAGE_BUILD_ID" <<'PY'
import hashlib, json, pathlib, subprocess, sys
deb = pathlib.Path(sys.argv[1])
fields = {k: subprocess.check_output(['dpkg-deb', '-f', str(deb), k], text=True).strip()
          for k in ('Package', 'Version', 'Architecture', 'Depends')}
metadata = {'kind': 'ros2-ci-native-rebuild', 'sdk_commit': sys.argv[2],
            'ros2_commit': sys.argv[3], 'codename': sys.argv[4], 'build_id': sys.argv[5],
            'sha256': hashlib.sha256(deb.read_bytes()).hexdigest(), 'control': fields,
            'cmake': subprocess.check_output(['cmake', '--version'], text=True).splitlines()[0],
            'compiler': subprocess.check_output(['c++', '--version'], text=True).splitlines()[0],
            'build_type': 'Release', 'cmake_options': ['CONTACTGLOVE_PACKAGE_DEB=ON',
                'CONTACTGLOVE_DEB_DISTRIBUTION=' + sys.argv[4]],
            'build_packages': subprocess.check_output(['dpkg-query', '-W', '-f=${binary:Package}=${Version}\n',
                'cmake', 'g++', 'dpkg', 'git'], text=True).splitlines(),
            'filename': deb.name}
(deb.parent / 'sdk-provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
PY
