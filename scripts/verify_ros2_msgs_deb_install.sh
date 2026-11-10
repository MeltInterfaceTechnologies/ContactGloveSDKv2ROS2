#!/usr/bin/env bash
set -euo pipefail

# Run in a fresh ros:<distro>-ros-base container, with only this script and
# the standalone DEB mounted. No repository, build tree, SDK or hardware is
# required. This installs packages and must not run on a development host.
#
# Usage:
#   bash verify_ros2_msgs_deb_install.sh humble /input/contactglove-ros2-msgs_*.deb

fail() {
  echo "standalone msgs verification: $*" >&2
  exit 1
}

if [[ $# -lt 2 || $# -gt 3 || ( $# -eq 3 && "${3:-}" != --with-bridge ) ]]; then
  echo "usage: $0 <humble|jazzy> path/to/contactglove-ros2-msgs_<version>_<arch>.deb" >&2
  exit 2
fi
with_bridge="${3:-}"

ros_distro="$1"
case "${ros_distro}" in
  humble) codename=jammy ;;
  jazzy) codename=noble ;;
  *) fail "unsupported ROS distribution: ${ros_distro}" ;;
esac
deb_path="$(realpath "$2")"
[[ -r "${deb_path}" ]] || fail "missing DEB: ${deb_path}"
prefix="/opt/ros/${ros_distro}"
package_name=contactglove-ros2-msgs
[[ -r "${prefix}/setup.bash" ]] || fail "missing ROS base installation: ${prefix}"

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
elif command -v sudo >/dev/null 2>&1; then
  SUDO=(sudo)
else
  fail "root or sudo is required to install the DEB and consumer-test dependencies"
fi

# Discard inherited overlays. The test must resolve the installed DEB, not a
# previously sourced workspace's generated files or type-support libraries.
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_PACKAGE_PATH
unset PYTHONPATH LD_LIBRARY_PATH
source_ros() {
  set +u
  # Generated ROS setup files are not nounset-safe.
  # shellcheck disable=SC1090
  source "${prefix}/setup.bash"
  set -u
}
source_ros

assert_no_driver_or_sdk() {
  [[ "${with_bridge}" != --with-bridge ]] || return 0
  local package status
  for package in contactglove-sdk-v2 contactglove-ros2-bridge \
    "ros-${ros_distro}-contact-glove"; do
    status="$(dpkg-query -W -f='${db:Status-Status}' "${package}" 2>/dev/null || true)"
    [[ "${status}" != installed ]] || fail "unexpected installed package: ${package}"
  done
  if ros2 pkg prefix contact_glove >/dev/null 2>&1; then
    fail "contact_glove driver is discoverable in this supposed msgs-only environment"
  fi
  [[ ! -e "${prefix}/lib/contact_glove" ]] || fail "driver executables are installed"
}

assert_no_driver_or_sdk
if [[ "${with_bridge}" != --with-bridge ]] && ros2 pkg prefix contact_glove_msgs >/dev/null 2>&1; then
  fail "contact_glove_msgs is already available; use a fresh ROS base container"
fi
[[ "$(dpkg-deb -f "${deb_path}" Package)" == "${package_name}" ]] || \
  fail "expected a ${package_name} DEB"
[[ "$(dpkg-deb -f "${deb_path}" Architecture)" == "$(dpkg --print-architecture)" ]] || \
  fail "DEB architecture does not match this container"
[[ "$(dpkg-deb -f "${deb_path}" Version)" =~ -1${codename}\+ros2\.[1-9][0-9]*\.[1-9][0-9]*$ ]] || \
  fail "DEB version does not target ${codename}"
if dpkg-deb -f "${deb_path}" Depends | grep -Eq 'contactglove-sdk|contactglove-ros2-bridge'; then
  fail "standalone DEB declares a native SDK or bridge dependency"
fi

# Install the artifact itself first. In particular, do not install an SDK or
# manually supplement its ROS dependencies before apt resolves its metadata.
"${SUDO[@]}" apt-get update
"${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${deb_path}"
[[ "$(dpkg-query -W -f='${db:Status-Status}' "${package_name}")" == installed ]] || \
  fail "standalone DEB was not installed"
source_ros
assert_no_driver_or_sdk
[[ "$(ros2 pkg prefix contact_glove_msgs)" == "${prefix}" ]] || \
  fail "contact_glove_msgs resolved outside ${prefix}"

messages=(Controller Ergonomics FingerPose GloveData HapticsBody \
  RawSensorTransforms RawSkeleton Skeleton ThumbPose)
for message in "${messages[@]}"; do
  ros2 interface show "contact_glove_msgs/msg/${message}" >/dev/null
done
ros2 interface show contact_glove_msgs/srv/GetRetargetProfile >/dev/null

docs="${prefix}/share/contact_glove_msgs"
for document in README.md README_JA.md LICENSE.md NOTICE.md THIRD_PARTY_NOTICES.md; do
  [[ -s "${docs}/${document}" ]] || fail "missing or empty documentation: ${docs}/${document}"
done
grep -Fq 'contact_glove_msgs' "${docs}/README.md" || fail "README does not describe the message package"
grep -Fq 'Apache License' "${docs}/LICENSE.md" || fail "Apache license text is missing"
[[ ! -e "${docs}/legal" ]] || fail "obsolete legal documentation directory is installed"

# Check the artifact's package index and shared libraries, not just whatever
# happens to be installed by the base image. CDLL also catches missing runtime
# dependencies before additional consumer-test dependencies are installed.
python3 - "${prefix}" "${package_name}" <<'PY'
import ctypes
import pathlib
import subprocess
import sys

prefix = pathlib.Path(sys.argv[1])
paths = subprocess.check_output(["dpkg-query", "-L", sys.argv[2]], text=True).splitlines()
index = prefix / "share/ament_index/resource_index/packages"
packages = {pathlib.Path(path).name for path in paths if pathlib.Path(path).parent == index}
assert packages == {"contact_glove_msgs"}, f"unexpected ROS packages in DEB: {packages}"
for path in paths:
    assert "/contact_glove/" not in path, f"driver payload in DEB: {path}"
    assert "ContactGloveSDK" not in path, f"native SDK payload in DEB: {path}"
    if pathlib.Path(path).is_symlink():
        assert pathlib.Path(path).resolve().exists(), f"broken installed symlink: {path}"
for backend in (
    "rosidl_generator_c",
    "rosidl_typesupport_c",
    "rosidl_typesupport_cpp",
    "rosidl_typesupport_fastrtps_c",
    "rosidl_typesupport_fastrtps_cpp",
    "rosidl_typesupport_introspection_c",
    "rosidl_typesupport_introspection_cpp",
):
    library = prefix / "lib" / f"libcontact_glove_msgs__{backend}.so"
    assert str(library) in paths and library.is_file(), f"missing generated library: {library}"
    ctypes.CDLL(str(library))
print("Installed package index and C/C++ type-support libraries verified")
PY

# These belong to the test consumers, not to the interface package. Installing
# them after the runtime checks keeps this dependency boundary explicit.
"${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  build-essential cmake "ros-${ros_distro}-ament-cmake" \
  "ros-${ros_distro}-rclcpp" "ros-${ros_distro}-rclpy"
source_ros

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

# Exercise every Python message and both service parts with populated fields.
# This imports native type support explicitly: a successful Python import alone
# would not notice a missing generated extension or one of its linked libraries.
python3 - "${prefix}" <<'PY'
import importlib
import pathlib
import sys

from rclpy.serialization import deserialize_message, serialize_message
from rclpy.type_support import check_for_type_support
from rosidl_runtime_py.set_message import set_message_fields
from contact_glove_msgs import msg
from contact_glove_msgs.srv import GetRetargetProfile

prefix = pathlib.Path(sys.argv[1]).resolve()
header = {"stamp": {"sec": 123, "nanosec": 456}, "frame_id": "synthetic/wrist"}
identity = {"header": header, "id": "synthetic-left", "is_left": True}
timed = {**identity, "generated_at_ms": 1234567890}
transform = {
    "translation": {"x": 0.125, "y": -0.25, "z": 0.5},
    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
}
finger = {"mcp": 1.25, "pip": 2.5, "dip": 3.75, "tilt": -0.5}
thumb = {"cmc": 1.25, "mcp": 2.5, "ip": 3.75, "tilt": -0.5}
samples = [
    (msg.Controller, {**identity, "a": 2, "trigger": 0.5, "joystick_x": -0.25}),
    (msg.Ergonomics, {**timed, "thumb": thumb, **{name: finger for name in ("index", "middle", "ring", "little")}}),
    (msg.FingerPose, finger),
    (msg.GloveData, {**identity, "pair_id": "synthetic-right", "name": "DEB test", "battery_percentage": 87, "is_haptics": True}),
    (msg.HapticsBody, {"id": "synthetic-left", "frequency": 200.0, "amplitude": 0.5, "duration": 0.125}),
    (msg.RawSensorTransforms, {**timed, **{name: transform for name in ("thumb", "index", "middle", "ring", "little")}}),
    (msg.RawSkeleton, {**timed, "tracking_state": 1, "joints": [transform for _ in range(25)]}),
    (msg.Skeleton, {**timed, "profile_uuid": "synthetic-profile", "joints": [transform for _ in range(25)]}),
    (msg.ThumbPose, thumb),
    (GetRetargetProfile.Request, {"profile_uuid": "synthetic-profile"}),
    (GetRetargetProfile.Response, {"status": 0, "profile_uuid": "synthetic-profile", "name": "DEB test", "description": "No hardware required"}),
]
check_for_type_support(GetRetargetProfile)
for message_type, fields in samples:
    module_path = pathlib.Path(importlib.import_module(message_type.__module__).__file__).resolve()
    assert module_path.is_relative_to(prefix), f"generated module came from an overlay: {module_path}"
    check_for_type_support(message_type)
    assert message_type.__class__._TYPE_SUPPORT is not None, message_type
    original = message_type()
    set_message_fields(original, fields)
    restored = deserialize_message(serialize_message(original), message_type)
    assert restored == original, f"serialization mismatch: {message_type.__name__}"
    print(f"Python type support and round-trip passed: {message_type.__name__}")
assert len(samples) == 11  # Nine messages plus request and response.
PY

cat > "${work_dir}/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.8)
project(standalone_msgs_consumer LANGUAGES C CXX)
find_package(ament_cmake REQUIRED)
find_package(contact_glove_msgs REQUIRED)
find_package(rclcpp REQUIRED)
add_executable(c_consumer c_consumer.c)
target_link_libraries(c_consumer
  contact_glove_msgs::contact_glove_msgs__rosidl_generator_c
  contact_glove_msgs::contact_glove_msgs__rosidl_typesupport_c)
add_executable(cpp_subscriber cpp_subscriber.cpp)
target_compile_features(cpp_subscriber PRIVATE cxx_std_17)
ament_target_dependencies(cpp_subscriber contact_glove_msgs rclcpp)
CMAKE

# Include all public C headers and actually initialize/finalize each type.
# Requesting each type-support handle also forces native C symbols to link.
cat > "${work_dir}/c_consumer.c" <<'C'
#include <stdio.h>
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_runtime_c/service_type_support_struct.h"
#include "contact_glove_msgs/msg/controller.h"
#include "contact_glove_msgs/msg/ergonomics.h"
#include "contact_glove_msgs/msg/finger_pose.h"
#include "contact_glove_msgs/msg/glove_data.h"
#include "contact_glove_msgs/msg/haptics_body.h"
#include "contact_glove_msgs/msg/raw_sensor_transforms.h"
#include "contact_glove_msgs/msg/raw_skeleton.h"
#include "contact_glove_msgs/msg/skeleton.h"
#include "contact_glove_msgs/msg/thumb_pose.h"
#include "contact_glove_msgs/srv/get_retarget_profile.h"

#define CHECK_MESSAGE(KIND, NAME) do { \
  contact_glove_msgs__ ## KIND ## __ ## NAME value; \
  if (!contact_glove_msgs__ ## KIND ## __ ## NAME ## __init(&value)) return 1; \
  contact_glove_msgs__ ## KIND ## __ ## NAME ## __fini(&value); \
  if (!ROSIDL_GET_MSG_TYPE_SUPPORT(contact_glove_msgs, KIND, NAME)) return 2; \
} while (0)

int main(void) {
  CHECK_MESSAGE(msg, Controller);
  CHECK_MESSAGE(msg, Ergonomics);
  CHECK_MESSAGE(msg, FingerPose);
  CHECK_MESSAGE(msg, GloveData);
  CHECK_MESSAGE(msg, HapticsBody);
  CHECK_MESSAGE(msg, RawSensorTransforms);
  CHECK_MESSAGE(msg, RawSkeleton);
  CHECK_MESSAGE(msg, Skeleton);
  CHECK_MESSAGE(msg, ThumbPose);
  CHECK_MESSAGE(srv, GetRetargetProfile_Request);
  CHECK_MESSAGE(srv, GetRetargetProfile_Response);
  if (!ROSIDL_GET_SRV_TYPE_SUPPORT(contact_glove_msgs, srv, GetRetargetProfile)) return 3;
  puts("C generated headers, lifecycle functions and type support verified");
  return 0;
}
C

cat > "${work_dir}/cpp_subscriber.cpp" <<'CPP'
#include <chrono>
#include <iostream>
#include <memory>
#include <thread>
#include "rclcpp/rclcpp.hpp"
#include "contact_glove_msgs/msg/controller.hpp"
#include "contact_glove_msgs/msg/ergonomics.hpp"
#include "contact_glove_msgs/msg/finger_pose.hpp"
#include "contact_glove_msgs/msg/glove_data.hpp"
#include "contact_glove_msgs/msg/haptics_body.hpp"
#include "contact_glove_msgs/msg/raw_sensor_transforms.hpp"
#include "contact_glove_msgs/msg/raw_skeleton.hpp"
#include "contact_glove_msgs/msg/skeleton.hpp"
#include "contact_glove_msgs/msg/thumb_pose.hpp"
#include "contact_glove_msgs/srv/get_retarget_profile.hpp"

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("standalone_msgs_cpp_subscriber");
  bool received = false;
  bool valid = false;
  // Default NodeOptions keep intra-process transport disabled. The publisher
  // below is a separate Python process, so success exercises DDS serialization.
  auto subscription = node->create_subscription<contact_glove_msgs::msg::Skeleton>(
    "/standalone_msgs_verify/skeleton", rclcpp::QoS(10).reliable(),
    [&](contact_glove_msgs::msg::Skeleton::ConstSharedPtr value) {
      received = true;
      valid = value->id == "synthetic-left" && value->is_left &&
        value->profile_uuid == "synthetic-profile" && value->generated_at_ms == 1234567890 &&
        value->header.frame_id == "synthetic/wrist" && value->header.stamp.sec == 123 &&
        value->header.stamp.nanosec == 456 && value->joints.size() == 25 &&
        value->tracking_state == contact_glove_msgs::msg::Skeleton::TRACKING_STATE_TRACKED;
      for (std::size_t i = 0; i < value->joints.size(); ++i) {
        const auto & joint = value->joints[i];
        valid = valid && joint.translation.x == static_cast<double>(i) + 0.125 &&
          joint.translation.y == -0.25 && joint.translation.z == 0.5 &&
          joint.rotation.x == 0.0 && joint.rotation.y == 0.0 &&
          joint.rotation.z == 0.0 && joint.rotation.w == 1.0;
      }
    });
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
  while (rclcpp::ok() && !received && std::chrono::steady_clock::now() < deadline) {
    rclcpp::spin_some(node);
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  rclcpp::shutdown();
  if (!received || !valid) {
    std::cerr << (received ? "Received incorrect sample" : "Timed out waiting for sample") << '\n';
    return 1;
  }
  std::cout << "C++ subscriber received the complete synthetic Python sample" << std::endl;
  return 0;
}
CPP

cmake -S "${work_dir}" -B "${work_dir}/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "${work_dir}/build" --parallel 2
"${work_dir}/build/c_consumer"

# Keep synthetic traffic off the LAN and separate from other container tests.
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID="$((100 + $$ % 100))"
python3 - "${work_dir}/build/cpp_subscriber" <<'PY'
import subprocess
import sys
import time

import rclpy
from contact_glove_msgs.msg import Skeleton

rclpy.init()
node = rclpy.create_node("standalone_msgs_python_publisher")
publisher = node.create_publisher(Skeleton, "/standalone_msgs_verify/skeleton", 10)
message = Skeleton()
message.id = "synthetic-left"
message.is_left = True
message.profile_uuid = "synthetic-profile"
message.generated_at_ms = 1234567890
message.header.frame_id = "synthetic/wrist"
message.header.stamp.sec = 123
message.header.stamp.nanosec = 456
message.tracking_state = Skeleton.TRACKING_STATE_TRACKED
for index, joint in enumerate(message.joints):
    joint.translation.x = float(index) + 0.125
    joint.translation.y = -0.25
    joint.translation.z = 0.5
    joint.rotation.w = 1.0

subscriber = subprocess.Popen([sys.argv[1]])
try:
    deadline = time.monotonic() + 35.0
    while subscriber.poll() is None and time.monotonic() < deadline:
        publisher.publish(message)
        rclpy.spin_once(node, timeout_sec=0.1)
    if subscriber.poll() is None:
        raise RuntimeError("C++ subscriber did not finish before the test deadline")
    if subscriber.returncode:
        raise RuntimeError(f"C++ subscriber failed with exit code {subscriber.returncode}")
finally:
    if subscriber.poll() is None:
        subscriber.terminate()
        try:
            subscriber.wait(timeout=5)
        except subprocess.TimeoutExpired:
            subscriber.kill()
            subscriber.wait()
    node.destroy_node()
    rclpy.shutdown()
PY

assert_no_driver_or_sdk
echo "Standalone ROS2 msgs DEB installation and independent consumers verified: ${deb_path}"

# Remove and reinstall msgs in the subscriber-only environment too, checking
# that the ament entry and native/Python type support are restored from the DEB.
if [[ "${with_bridge}" != --with-bridge ]]; then
  "${SUDO[@]}" apt-get remove -y "${package_name}"
  [[ ! -e "${prefix}/share/ament_index/resource_index/packages/contact_glove_msgs" ]] || fail "msgs ament entry survived removal"
  "${SUDO[@]}" apt-get install -y --no-install-recommends "${deb_path}"
  source_ros
  python3 -c 'from contact_glove_msgs.msg import GloveData; from rclpy.type_support import check_for_type_support; check_for_type_support(GloveData)'
  ros2 interface show contact_glove_msgs/msg/GloveData >/dev/null
  assert_no_driver_or_sdk
fi
