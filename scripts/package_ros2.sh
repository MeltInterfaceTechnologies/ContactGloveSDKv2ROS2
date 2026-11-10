#!/usr/bin/env bash
set -euo pipefail

# Builds one distributable ZIP for ContactGlove ROS2 SDK
# (contact_glove + contact_glove_msgs), for one ROS2 distribution / Ubuntu
# codename. The ZIP includes both the relocatable `install/` tree and the
# bridge and independent interfaces DEBs at its root:
#
#   dist/ContactGloveSDKv2ROS2-<version>-<ros_distro>-<arch>.zip
#     - `install/`: source this ROS overlay after installing the native SDK runtime.
#     - `contactglove-ros2-bridge_<version>-1<codename>+ros2.<build-id>_<arch>.deb`:
#       install it directly into an existing /opt/ros/<ros_distro> ROS2 install.
#
#     - `contactglove-ros2-msgs_<version>-1<codename>+ros2.<build-id>_<arch>.deb`:
#       install with the bridge, or alone on subscriber systems.
#
# Usage:
#   source /opt/ros/<ros_distro>/setup.bash
#   bash scripts/package_ros2.sh <ros_distro> <ubuntu_codename> [version]
#
# Example:
#   sudo apt-get install -y zip unzip
#   source /opt/ros/jazzy/setup.bash
#   bash scripts/package_ros2.sh jazzy noble

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 <ros_distro> <ubuntu_codename> [version]" >&2
  echo "example: $0 jazzy noble" >&2
  exit 2
fi

ros_distro="$1"
codename="$2"
: "${PACKAGE_BUILD_ID:?Set PACKAGE_BUILD_ID to the ID used to build the SDK DEB}"
[[ "$PACKAGE_BUILD_ID" =~ ^[1-9][0-9]*\.[1-9][0-9]*$ ]] || { echo "invalid PACKAGE_BUILD_ID" >&2; exit 2; }

if [[ -z "${ros_distro}" || -z "${codename}" ]]; then
  echo "usage: $0 <ros_distro> <ubuntu_codename> [version]" >&2
  echo "example: $0 jazzy noble" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

if [[ -z "${AMENT_PREFIX_PATH:-}" ]]; then
  echo "ROS2 ${ros_distro} environment is not sourced. Run:" >&2
  echo "  source /opt/ros/${ros_distro}/setup.bash" >&2
  exit 1
fi

if [[ "${ROS_DISTRO:-}" != "${ros_distro}" ]]; then
  echo "Sourced ROS2 distro (\"${ROS_DISTRO:-<none>}\") does not match the requested <ros_distro> argument (\"${ros_distro}\")." >&2
  echo "  source /opt/ros/${ros_distro}/setup.bash" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1 || ! command -v unzip >/dev/null 2>&1; then
  echo "Required commands 'zip' and 'unzip' are not installed. Install them with:" >&2
  echo "  sudo apt-get install -y zip unzip" >&2
  exit 1
fi

version="${3:-}"
if [[ -z "${version}" ]]; then
  version="$(sed -n 's:.*<version>\(.*\)</version>.*:\1:p' "${repo_root}/src/contact_glove/package.xml" | head -n1)"
fi
if [[ -z "${version}" ]]; then
  echo "Could not determine package version from src/contact_glove/package.xml" >&2
  exit 1
fi

arch="$(dpkg --print-architecture)"
package_name="contactglove-ros2-bridge"
deb_release="1${codename}+ros2.${PACKAGE_BUILD_ID}"
msgs_version="$(sed -n 's:.*<version>\(.*\)</version>.*:\1:p' "${repo_root}/src/contact_glove_msgs/package.xml" | head -n1)"
if [[ "${version}" != "${msgs_version}" ]]; then
  echo "distribution version must match contact_glove_msgs (${msgs_version})" >&2
  exit 2
fi

: "${SDK_BUILD_DIR:?Build the pinned SDK with scripts/build_cpp_sdk.sh and set SDK_BUILD_DIR}"
shopt -s nullglob
sdk_debs=("${SDK_BUILD_DIR}"/contactglove-sdk-v2_*.deb)
if [[ ${#sdk_debs[@]} != 1 || ! -r "${SDK_BUILD_DIR}/sdk-provenance.json" ]]; then
  echo "SDK_BUILD_DIR must contain one built SDK DEB and sdk-provenance.json." >&2
  exit 1
fi
sdk_deb="${sdk_debs[0]}"
sdk_version="$(dpkg-deb -f "${sdk_deb}" Version)"
sdk_dependencies="$(python3 "${repo_root}/scripts/native_sdk_dependency.py" "$sdk_version" "$codename")"
[[ "$sdk_version" == *"-${deb_release}" ]] || { echo "SDK DEB build ID does not match PACKAGE_BUILD_ID" >&2; exit 1; }

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

sdk_extract_root="${work_dir}/contactglove-sdk"
dpkg-deb -x "${sdk_deb}" "${sdk_extract_root}"
sdk_multiarch="$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
sdk_cmake_dir="${sdk_extract_root}/usr/lib/${sdk_multiarch}/cmake/ContactGloveSDKv2"
if [[ ! -r "${sdk_cmake_dir}/ContactGloveSDKv2Config.cmake" ]]; then
  echo "C++ SDK package is missing its CMake configuration: ${sdk_cmake_dir}" >&2
  exit 1
fi

# The ROS 2 packages own their license documents. Keep the C++ runtime's
# separate notices inside its DEB and reject stale proprietary inputs.
python3 "${repo_root}/scripts/verify_distribution_licenses.py" --cpp-deb "${sdk_deb}" --provenance "${SDK_BUILD_DIR}/sdk-provenance.json"

copy_ros2_legal_docs() {
  local destination="$1"
  install -d "${destination}"
  cp "${repo_root}/LICENSE.md" \
     "${repo_root}/NOTICE.md" \
     "${repo_root}/THIRD_PARTY_NOTICES.md" \
     "${destination}/"
}

build_base="${work_dir}/build"
install_base="${work_dir}/install"

echo "Building workspace (merge-install) for packaging..."
colcon build \
  --base-paths "${repo_root}/src" \
  --build-base "${build_base}" \
  --install-base "${install_base}" \
  --merge-install \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DContactGloveSDKv2_DIR="${sdk_cmake_dir}"

# Build the bridge into a separate prefix, using the combined workspace only
# for its interface dependency. Staging this prefix assigns every generated
# msgs file (including Python, type support and ament resources) exclusively
# to the msgs DEB, without fragile filename-based exclusions.
bridge_install="${work_dir}/bridge-install"
echo "Building bridge-only prefix for its DEB..."
AMENT_PREFIX_PATH="${install_base}:${AMENT_PREFIX_PATH}" \
CMAKE_PREFIX_PATH="${install_base}:${CMAKE_PREFIX_PATH:-}" \
colcon --log-base "${work_dir}/bridge-log" build \
  --base-paths "${repo_root}/src/contact_glove" \
  --packages-select contact_glove \
  --build-base "${work_dir}/bridge-build" --install-base "${bridge_install}" \
  --merge-install \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DContactGloveSDKv2_DIR="${sdk_cmake_dir}"

dist_dir="${repo_root}/dist"
mkdir -p "${dist_dir}"

# ---------------------------------------------------------------------------
# ZIP staging: documentation, the relocatable `install/` tree, and the
# ContactGlove SDK v2 C++ runtime package.
# ---------------------------------------------------------------------------
zip_name="ContactGloveSDKv2ROS2-${version}-${ros_distro}-${arch}"
zip_stage="${work_dir}/zip/${zip_name}"
mkdir -p "${zip_stage}"

# Use the minimal consumer-facing English README and its Japanese translation
# at the ZIP root, rather than the developer-facing repository README.
cp "${repo_root}/packaging/README.md" "${zip_stage}/README.md"
copy_ros2_legal_docs "${zip_stage}"

cp "${repo_root}/packaging/README_JA.md" "${zip_stage}/README_JA.md"

# The same package-level documentation is also installed under
# install/share/contact_glove[/_msgs] for ROS package and deb users.
cp -a "${install_base}" "${zip_stage}/install"
mkdir -p "${zip_stage}/scripts"
cp "${repo_root}/scripts/install_contactglove_sdk_deb.sh" "${zip_stage}/scripts/"
mkdir -p "${zip_stage}/lib"
cp "${sdk_deb}" "${zip_stage}/lib/"
sed "s/@ROS2_VERSION@/${version}/g" "${repo_root}/packaging/SDK_PROVENANCE.md" > "${zip_stage}/lib/README.md"
cp "${SDK_BUILD_DIR}/sdk-provenance.json" "${zip_stage}/lib/"

# ---------------------------------------------------------------------------
# Embedded DEB: installs directly into an existing /opt/ros/<ros_distro> ROS2
# installation. It is generated in the temporary work directory and copied
# into the root of the distributable ZIP below.
# ---------------------------------------------------------------------------
deb_stage="${work_dir}/deb"
deb_root="${deb_stage}/opt/ros/${ros_distro}"
mkdir -p "${deb_root}"
# Only stage this package's actual payload (bin/include/lib/local/share). The
# merge-install prefix's top-level files (setup.bash, local_setup.*,
# COLCON_IGNORE, .colcon_install_layout, ...) belong to the base ROS
# workspace package already installed at /opt/ros/<ros_distro>; shipping
# them here would make a plain `dpkg -i` (no --force-overwrite) refuse to
# install due to file conflicts.
for sub in bin include lib local share; do
  if [[ -d "${bridge_install}/${sub}" ]]; then
    mkdir -p "${deb_root}/${sub}"
    cp -a "${bridge_install}/${sub}/." "${deb_root}/${sub}/"
  fi
done
# `local` (not to be confused with the top-level local_setup.* files excluded
# above) is where rosidl_generator_py's Debian "dist-packages" install layout
# would place generated Python message modules (e.g.
# local/lib/python3/dist-packages/contact_glove_msgs) on some toolchains.
# On the verified Jazzy/Noble toolchain, ament_cmake_python detects the
# deb_system sysconfig scheme and forces posix_prefix, so Python packages are
# installed under lib/pythonX.Y/site-packages (already covered above) and this
# directory does not exist. It is staged defensively for other or future
# toolchains that produce the Debian layout.

mkdir -p "${deb_stage}/DEBIAN"
installed_size_kb="$(du -sk "${deb_stage}" | cut -f1)"
cat > "${deb_stage}/DEBIAN/control" <<EOF
Package: ${package_name}
Version: ${version}-${deb_release}
Section: devel
Priority: optional
Architecture: ${arch}
Installed-Size: ${installed_size_kb}
Maintainer: Melt Interface Technologies <info@melt-interface-technologies.com>
Depends: contactglove-ros2-msgs (= ${version}-${deb_release}), ros-${ros_distro}-rclcpp, ros-${ros_distro}-geometry-msgs, ros-${ros_distro}-std-msgs, ros-${ros_distro}-sensor-msgs, ros-${ros_distro}-visualization-msgs, ros-${ros_distro}-tf2-ros, ros-${ros_distro}-rosidl-default-runtime, ros-${ros_distro}-xacro, ros-${ros_distro}-robot-state-publisher, ros-${ros_distro}-rviz2, ${sdk_dependencies}
Homepage: https://melt-interface-technologies.com/
Description: ContactGlove ROS2 SDK for ROS2 ${ros_distro}.
 Provides the contact_glove ROS2 package, bridging
 ContactGlove SDK v2 device data to ROS2 topics. Installs into an existing
 /opt/ros/${ros_distro} ROS2 installation. Requires the contactglove-sdk-v2
 and contactglove-ros2-msgs packages. All three DEBs are included in the
 accompanying ContactGloveSDKv2ROS2 distribution ZIP.
EOF

deb_file="${work_dir}/${package_name}_${version}-${deb_release}_${arch}.deb"
dpkg-deb --build --root-owner-group "${deb_stage}" "${deb_file}"
cp "${deb_file}" "${zip_stage}/"

# Build the subscriber-only package in its own clean build directory. It is
# also used by bridge installations through an explicit Depends relationship.
msgs_dist="${work_dir}/msgs-dist"
MSGS_DIST_DIR="${msgs_dist}" bash "${repo_root}/scripts/package_ros2_msgs.sh" \
  "${ros_distro}" "${codename}"
msgs_deb="${msgs_dist}/contactglove-ros2-msgs_${version}-${deb_release}_${arch}.deb"
test -f "${msgs_deb}"
cp "${msgs_deb}" "${zip_stage}/"

# ---------------------------------------------------------------------------
# Finalize the single distributable ZIP after its embedded bridge deb exists.
# ---------------------------------------------------------------------------
zip_file="${dist_dir}/${zip_name}.zip"
zip_work_file="${work_dir}/${zip_name}.zip"
echo "Zipping ${zip_name}.zip ..."
( cd "${work_dir}/zip" && zip -r -q "${zip_work_file}" "${zip_name}" )
zip -T "${zip_work_file}" >/dev/null
cp "${zip_work_file}" "${zip_file}"
python3 "${repo_root}/scripts/verify_distribution_licenses.py" "${zip_file}"
python3 "${repo_root}/scripts/verify_ros2_distribution.py" "${zip_file}" "${ros_distro}" "${codename}"
echo "Built ${zip_file}"
