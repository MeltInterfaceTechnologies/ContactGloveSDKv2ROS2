#!/usr/bin/env bash
# Destructive fresh-install/removal checks: use a fresh ROS base container only.
set -euo pipefail
[[ $# == 4 ]] || { echo "usage: $0 <distro> <bridge.deb> <msgs.deb> <sdk.deb>" >&2; exit 2; }
source "$(dirname "${BASH_SOURCE[0]}")/ros2_deb_test_common.sh" "$@"
# apt must resolve all dependencies from a clean image and the explicitly
# supplied local files. Preserve the existing RViz/xacro/RSP dependencies.
bash "${script_dir}/verify_ros2_deb_install.sh" "${ros_distro}" "${bridge}" "${msgs}" "${sdk}"
for package in rviz2 xacro robot-state-publisher; do assert_installed "ros-${ros_distro}-${package}"; done
verify_split
bash "${script_dir}/verify_ros2_msgs_deb_install.sh" "${ros_distro}" "${msgs}" --with-bridge
verify_installed_bridge

# Removing only bridge must leave functioning msgs. Reinstall the driver,
# then removing msgs through apt must remove its dependent bridge as well.
apt-get remove -y contactglove-ros2-bridge
assert_absent contactglove-ros2-bridge
assert_installed contactglove-ros2-msgs
python3 -c 'from contact_glove_msgs.msg import GloveData; from rclpy.type_support import check_for_type_support; check_for_type_support(GloveData)'
apt-get install -y --no-install-recommends "${bridge}" "${msgs}" "${sdk}"
verify_split
apt-get remove -y contactglove-ros2-msgs
assert_absent contactglove-ros2-bridge
assert_absent contactglove-ros2-msgs
apt-get install -y --no-install-recommends "${bridge}" "${msgs}" "${sdk}"
verify_split
remove_all

echo "Fresh install, ownership, ELF links and removal/reinstall passed for ${ros_distro}"
