#!/usr/bin/env bash
# ROS installation for disposable GitHub-hosted Ubuntu runners only.
# Repository setup follows https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html
# and the equivalent Jazzy guide, deliberately omitting their system-wide upgrade.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/setup_ros_ci.sh <humble|jazzy>" >&2
  exit 2
fi
ros_distro="$1"
case "$ros_distro" in
  humble)
    codename=jammy
    source_sha256=110b9a462d55252decb8b7c816f61c2ba0d9890ce5fb93ac504e97cae5860d76
    ;;
  jazzy)
    codename=noble
    source_sha256=f31d84adf5054c7d60ded0e82c0f776a77ea33af53d08f40b9ad7c94cca55296
    ;;
  *) echo "Unsupported ROS distribution: $ros_distro" >&2; exit 2 ;;
esac
if [[ "$(lsb_release -is)" != Ubuntu || "$(lsb_release -cs)" != "$codename" ||
      "$(dpkg --print-architecture)" != amd64 ]]; then
  echo "ROS $ros_distro requires Ubuntu $codename amd64" >&2
  exit 2
fi
: "${GITHUB_ENV:?Run this helper in a GitHub Actions job}"

# Bounded download retries; a partial/stale package index is a setup failure.
# --no-remove also guards the old Jammy systemd/udev issue noted by ROS docs.
apt_options=(-o Acquire::Retries=3 -o APT::Update::Error-Mode=any)
apt_install() {
  sudo env DEBIAN_FRONTEND=noninteractive apt-get "${apt_options[@]}" \
    install -y --no-install-recommends --no-remove "$@"
}
sudo apt-get "${apt_options[@]}" update
apt_install ca-certificates curl locales software-properties-common
sudo add-apt-repository --yes --no-update universe
sudo locale-gen en_US.UTF-8
printf 'LANG=en_US.UTF-8\nLC_ALL=en_US.UTF-8\n' >> "$GITHUB_ENV"

# Pin both the bootstrap version and per-Ubuntu release bytes. When updating,
# obtain digests from https://github.com/ros-infrastructure/ros-apt-source/releases
# and run both distro jobs. No moving /latest API lookup or hand-maintained key.
source_version=1.3.0
source_deb="ros2-apt-source_${source_version}.${codename}_all.deb"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT
curl --fail --silent --show-error --location --retry 3 --retry-delay 2 \
  --connect-timeout 30 --max-time 180 \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${source_version}/${source_deb}" \
  --output "$temporary/$source_deb"
printf '%s  %s\n' "$source_sha256" "$temporary/$source_deb" | sha256sum --check --strict
sudo dpkg --install "$temporary/$source_deb"
sudo apt-get "${apt_options[@]}" update

# Preserve the previous desktop ROS variant. Project-specific dependencies stay
# explicit in ci.yml; ros-dev-tools supplies colcon, rosdep and vcs without pip.
# Only named packages and dependencies may change; never upgrade the whole OS.
apt_install "ros-${ros_distro}-desktop" ros-dev-tools \
  build-essential cmake file python3-colcon-common-extensions
