#!/usr/bin/env bash
# Shared helpers for fresh-image DEB checks. Source from a lifecycle entrypoint.
set -euo pipefail
ros_distro="$1"
case "$ros_distro" in humble|jazzy) ;; *) echo "unsupported ROS distro" >&2; exit 2 ;; esac
bridge="$(realpath "$2")"
msgs="$(realpath "$3")"
sdk="$(realpath "$4")"
prefix="/opt/ros/${ros_distro}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ "$(id -u)" == 0 ]] || { echo "use a root container" >&2; exit 2; }
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_PACKAGE_PATH
unset PYTHONPATH LD_LIBRARY_PATH
export DEBIAN_FRONTEND=noninteractive
# ROS Docker images omit /usr/share/doc through dpkg path-exclude rules.
# Keep the bundled SDK's actual license/docs in this test container so the
# ownership audit can check every declared file, including documentation.
printf '%s\n' 'path-include=/usr/share/doc/ContactGloveSDKv2' \
  'path-include=/usr/share/doc/ContactGloveSDKv2/*' \
  > /etc/dpkg/dpkg.cfg.d/zz-contactglove-sdk-docs
apt-get update

source_ros() {
  set +u
  source "${prefix}/setup.bash"
  set -u
}
assert_installed() {
  [[ "$(dpkg-query -W -f='${db:Status-Status}' "$1")" == installed ]]
}
assert_absent() {
  [[ "$(dpkg-query -W -f='${db:Status-Status}' "$1" 2>/dev/null || true)" != installed ]]
}
verify_split() {
  for package in contactglove-ros2-bridge contactglove-ros2-msgs contactglove-sdk-v2; do
    assert_installed "${package}"
  done
  [[ "$(dpkg-query -W -f='${Version}' contactglove-ros2-bridge)" == "$(dpkg-deb -f "${bridge}" Version)" ]]
  [[ "$(dpkg-query -W -f='${Version}' contactglove-ros2-msgs)" == "$(dpkg-deb -f "${msgs}" Version)" ]]
  [[ "$(dpkg-query -W -f='${Version}' contactglove-sdk-v2)" == "$(dpkg-deb -f "${sdk}" Version)" ]]
  [[ -z "$(dpkg --audit)" ]]
  source_ros
  [[ "$(ros2 pkg prefix contact_glove)" == "${prefix}" ]]
  [[ "$(ros2 pkg prefix contact_glove_msgs)" == "${prefix}" ]]
  # All regular files and symlinks must have exactly one owner. Test every
  # shared object/executable before installing additional consumer tools.
  python3 - <<'PY'
import pathlib
import subprocess

owners = {}
for package in ('contactglove-ros2-bridge', 'contactglove-ros2-msgs', 'contactglove-sdk-v2'):
    for name in subprocess.check_output(['dpkg-query', '-L', package], text=True).splitlines():
        path = pathlib.Path(name)
        if path.is_dir() and not path.is_symlink():
            continue
        assert path.exists(), f'missing or broken installed payload: {name}'
        assert name not in owners, f'duplicate ownership: {name}'
        owners[name] = package
        actual = subprocess.check_output(['dpkg-query', '-S', name], text=True).strip()
        assert actual == f'{package}: {name}', f'incorrect ownership: {actual}'
        if path.is_file() and path.open('rb').read(4) == b'\x7fELF':
            result = subprocess.run(['ldd', name], text=True, capture_output=True)
            assert result.returncode == 0 and 'not found' not in result.stdout + result.stderr, (name, result.stdout, result.stderr)
print(f'Unique ownership and ELF links verified for {len(owners)} installed files')
PY
}
remove_all() {
  apt-get remove -y contactglove-ros2-bridge contactglove-ros2-msgs contactglove-sdk-v2
  for package in contactglove-ros2-bridge contactglove-ros2-msgs contactglove-sdk-v2; do
    assert_absent "${package}"
  done
  [[ ! -e "${prefix}/share/ament_index/resource_index/packages/contact_glove" ]]
  [[ ! -e "${prefix}/share/ament_index/resource_index/packages/contact_glove_msgs" ]]
  # The base ROS prefix must survive every removal.
  [[ -f "${prefix}/setup.bash" ]]
}
verify_installed_bridge() {
  # Use the same synthetic UDP/DDS recovery test against the actual installed
  # ZIP executable, with traffic confined to this container's loopback.
  ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=187 timeout 45s python3 \
    "${script_dir}/test_lan_retry.py" "${prefix}/lib/contact_glove/contact_glove_node"
}

