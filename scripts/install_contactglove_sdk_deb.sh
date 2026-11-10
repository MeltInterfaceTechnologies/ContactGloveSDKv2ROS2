#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

dry_run=false
case "${1:-}" in
  --dry-run)
    dry_run=true
    shift
    ;;
  -h|--help)
    echo "Usage: bash scripts/install_contactglove_sdk_deb.sh [--dry-run]"
    exit 0
    ;;
esac
if (( $# > 0 )); then
  echo "Unexpected argument: $1" >&2
  echo "Usage: bash scripts/install_contactglove_sdk_deb.sh [--dry-run]" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "Unsupported system: /etc/os-release was not found." >&2
  exit 1
fi

# shellcheck disable=SC1091
. /etc/os-release

codename="${VERSION_CODENAME:-}"
case "${codename}" in
  jammy|noble)
    ;;
  *)
    echo "Unsupported Ubuntu codename: ${codename:-unknown}" >&2
    echo "Supported codenames are: jammy, noble." >&2
    exit 1
    ;;
esac

arch="$(dpkg --print-architecture)"
if [[ "${arch}" != "amd64" ]]; then
  echo "Unsupported architecture: ${arch}" >&2
  echo "The bundled ContactGlove SDK package currently supports amd64 only." >&2
  exit 1
fi

shopt -s nullglob
packages=("${repo_root}"/lib/contactglove-sdk-v2_*"${codename}"*_${arch}.deb)
if [[ ${#packages[@]} != 1 ]]; then
  echo "Expected one ContactGlove SDK package for ${codename}/${arch} under ${repo_root}/lib." >&2
  exit 1
fi
package="${packages[0]}"
echo "Installing ${package}"

if [[ "${dry_run}" == true ]]; then
  echo "Dry run: package selection succeeded; no changes were made."
  exit 0
fi

if [[ "${EUID}" -eq 0 ]]; then
  apt-get install -y "${package}"
else
  sudo apt-get install -y "${package}"
fi
