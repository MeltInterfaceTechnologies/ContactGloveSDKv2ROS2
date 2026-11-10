#!/usr/bin/env bash
set -euo pipefail

# Installs a contactglove-ros2-bridge_*.deb built by package_ros2.sh and
# verifies that the packages it provides are discoverable and runnable.
#
# Usage:
#   source /opt/ros/<ros_distro>/setup.bash
#   bash scripts/verify_ros2_deb_install.sh <distro> <bridge.deb> <msgs.deb> <sdk.deb>

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <ros_distro> <bridge.deb> <msgs.deb> <sdk.deb>" >&2
  exit 2
fi

ros_distro="$1"
deb_path="$2"

if [[ ! -f "${deb_path}" ]]; then
  echo "missing deb: ${deb_path}" >&2
  exit 2
fi

if command -v sudo >/dev/null 2>&1 && [[ "$(id -u)" -ne 0 ]]; then
  SUDO=(sudo)
else
  SUDO=()
fi

"${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  "$(realpath "${deb_path}")" "$(realpath "$3")" "$(realpath "$4")"

# The deb installs straight into the existing /opt/ros/<ros_distro> prefix, so
# a package that was already sourced needs to be re-sourced to pick up the
# newly added ament resource index entries. Generated ROS2 setup scripts
# reference setup variables (e.g. AMENT_TRACE_SETUP_FILES) without
# defaults and are not nounset-safe, so `set -u` (from this script's
# `set -euo pipefail`) would abort on them; nounset is temporarily disabled
# around the source.
set +u
# shellcheck disable=SC1090
source "/opt/ros/${ros_distro}/setup.bash"
set -u

require_pkg_prefix() {
  local pkg="$1"
  if ! ros2 pkg prefix "${pkg}" >/dev/null 2>&1; then
    echo "ros2 pkg prefix failed to resolve package: ${pkg}" >&2
    exit 1
  fi
}

require_pkg_prefix contact_glove
require_pkg_prefix contact_glove_msgs

require_executable() {
  local exe_path="/opt/ros/${ros_distro}/lib/contact_glove/$1"
  if [[ ! -x "${exe_path}" ]]; then
    echo "missing expected installed executable: ${exe_path}" >&2
    exit 1
  fi
}

require_executable contact_glove_node
require_executable contact_glove_rviz_node

require_installed_file() {
  local relative_path="$1"
  local installed_path="/opt/ros/${ros_distro}/share/contact_glove/${relative_path}"
  if [[ ! -f "${installed_path}" ]]; then
    echo "missing expected installed documentation: ${installed_path}" >&2
    exit 1
  fi
}

require_installed_file README.md
require_installed_file README_JA.md
require_installed_file LICENSE.md
require_installed_file NOTICE.md
require_installed_file THIRD_PARTY_NOTICES.md

if ! grep -Fq "Apache License" \
  "/opt/ros/${ros_distro}/share/contact_glove/LICENSE.md"; then
  echo "installed LICENSE.md does not contain the expected license text" >&2
  exit 1
fi

for package in contact_glove contact_glove_msgs; do
  docs="/opt/ros/${ros_distro}/share/${package}"
  for document in LICENSE.md NOTICE.md THIRD_PARTY_NOTICES.md; do
    test -f "${docs}/${document}"
  done
  if [[ -e "${docs}/legal" ]]; then
    echo "obsolete legal documents installed: ${docs}/legal" >&2
    exit 1
  fi
done

if ! ros2 interface show contact_glove_msgs/msg/GloveData >/dev/null 2>&1; then
  echo "ros2 interface show failed for contact_glove_msgs/msg/GloveData" >&2
  exit 1
fi

if ! python3 -c 'from contact_glove_msgs.msg import GloveData' >/dev/null 2>&1; then
  echo "Python import failed for contact_glove_msgs.msg.GloveData" >&2
  exit 1
fi

echo "ROS2 deb install verification passed: ${deb_path}"
