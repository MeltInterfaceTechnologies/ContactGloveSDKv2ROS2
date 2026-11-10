#!/usr/bin/env bash
# Build only the ROS interfaces, without the bridge or ContactGlove C++ SDK.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "usage: $0 <humble|jazzy> <jammy|noble>" >&2
  exit 2
fi
ros_distro="$1"
codename="$2"
case "${ros_distro}/${codename}" in
  humble/jammy|jazzy/noble) ;;
  *) echo "unsupported ROS/Ubuntu pair: ${ros_distro}/${codename}" >&2; exit 2 ;;
esac
: "${PACKAGE_BUILD_ID:?Set PACKAGE_BUILD_ID to a unique numeric build ID and attempt}"
[[ "$PACKAGE_BUILD_ID" =~ ^[1-9][0-9]*\.[1-9][0-9]*$ ]] || { echo "invalid PACKAGE_BUILD_ID" >&2; exit 2; }
deb_release="1${codename}+ros2.${PACKAGE_BUILD_ID}"
# Reject cross-distro/architecture builds: Python and ELF artifacts are native.
. /etc/os-release
arch="$(dpkg --print-architecture)"
if [[ "${ID}" != ubuntu || "${VERSION_CODENAME}" != "${codename}" || "${arch}" != amd64 ]]; then
  echo "build on Ubuntu ${codename} amd64" >&2
  exit 2
fi
if [[ "${ROS_DISTRO:-}" != "${ros_distro}" || -z "${AMENT_PREFIX_PATH:-}" ]]; then
  echo "source /opt/ros/${ros_distro}/setup.bash first" >&2
  exit 2
fi
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(python3 -c 'import sys,xml.etree.ElementTree as E; print(E.parse(sys.argv[1]).getroot().findtext("version"))' "${repo_root}/src/contact_glove_msgs/package.xml")"
dpkg --validate-version "${version}"
package_name=contactglove-ros2-msgs
work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT
install_base="${work_dir}/install"
# A dedicated base path prevents even discovery of contact_glove and its SDK.
colcon --log-base "${work_dir}/log" build \
  --base-paths "${repo_root}/src/contact_glove_msgs" \
  --packages-select contact_glove_msgs \
  --build-base "${work_dir}/build" --install-base "${install_base}" \
  --merge-install --event-handlers console_direct+ \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF

deb_stage="${work_dir}/deb"
deb_root="${deb_stage}/opt/ros/${ros_distro}"
mkdir -p "${deb_root}"
# Never overwrite the base ROS prefix's setup files.
for sub in bin include lib local share; do
  if [[ -d "${install_base}/${sub}" ]]; then
    mkdir -p "${deb_root}/${sub}"
    cp -a "${install_base}/${sub}/." "${deb_root}/${sub}/"
  fi
done
# Extract ABI-versioned system dependencies from all generated shared objects.
# Locally generated ROS libraries have no dpkg shlibs database yet; their ROS
# dependencies are declared explicitly below. The clean install test also
# checks every ELF for unresolved dependencies.
mkdir -p "${work_dir}/debian"
printf 'Source: %s\nSection: devel\nPriority: optional\nMaintainer: Melt Interface Technologies <info@melt-interface-technologies.com>\n\nPackage: %s\nArchitecture: any\nDescription: ContactGlove interfaces\n' "${package_name}" "${package_name}" > "${work_dir}/debian/control"
elf_args=()
while IFS= read -r -d '' library; do
  elf_args+=("-e${library}")
done < <(find "${deb_root}" -type f -name '*.so*' -print0)
if (( ${#elf_args[@]} == 0 )); then
  echo "no generated shared libraries found" >&2
  exit 1
fi
system_deps="$(cd "${work_dir}" && dpkg-shlibdeps -O --ignore-missing-info \
  "-l${install_base}/lib" "-l/opt/ros/${ros_distro}/lib" "${elf_args[@]}" | sed -n 's/^shlibs:Depends=//p')"
if [[ -z "${system_deps}" ]]; then
  echo "could not determine shared-library dependencies" >&2
  exit 1
fi
read -r python_min python_max < <(python3 -c 'import sys; a,b=sys.version_info[:2]; print(f"{a}.{b}", f"{a}.{b+1}")')
mkdir -p "${deb_stage}/DEBIAN"
cat > "${deb_stage}/DEBIAN/control" <<CONTROL
Package: ${package_name}
Version: ${version}-${deb_release}
Section: devel
Priority: optional
Architecture: ${arch}
Installed-Size: $(du -sk "${deb_stage}" | cut -f1)
Maintainer: Melt Interface Technologies <info@melt-interface-technologies.com>
Depends: ${system_deps}, python3 (>= ${python_min}), python3 (<< ${python_max}), python3-numpy, ros-${ros_distro}-geometry-msgs, ros-${ros_distro}-std-msgs, ros-${ros_distro}-rosidl-default-runtime
Breaks: contactglove-ros2-bridge (<< 0.2.4)
Replaces: contactglove-ros2-bridge (<< 0.2.4)
Homepage: https://melt-interface-technologies.com/
Description: Standalone ContactGlove ROS2 interfaces for ${ros_distro}
 Provides contact_glove_msgs message/service definitions, generated C/C++ and
 Python interfaces, type support, and ament metadata for subscriber systems.
 Does not require DivingStation or the ContactGlove C++ SDK on this system.
 Also supplies the interfaces used by contactglove-ros2-bridge 0.2.4 and later.
CONTROL
dist_dir="${MSGS_DIST_DIR:-${repo_root}/dist}"
mkdir -p "${dist_dir}"
deb_file="${dist_dir}/${package_name}_${version}-${deb_release}_${arch}.deb"
dpkg-deb --build --root-owner-group "${deb_stage}" "${deb_file}"
echo "Built ${deb_file}"
