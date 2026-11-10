# ContactGlove ROS2 SDK V2 development

English | [日本語](DEVELOPMENT_JA.md)

Instructions for building the SDK from source, running tests, and creating distribution packages.
For installation, operation, and API details, see the [Web documentation](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2).

## Package layout

```
src/
├── contact_glove_msgs/  # Message definitions
└── contact_glove/       # Driver and visualizer nodes
vendor/contactglove-sdk-v2/  # C++ SDK submodule pinned to a specific commit
scripts/
├── install_contactglove_sdk_deb.sh  # Install the C++ SDK DEB for the target environment
├── package_ros2.sh                  # Create a distribution ZIP with bridge and messages-only DEBs
├── package_ros2_msgs.sh             # Build only contact_glove_msgs and create its DEB
└── mock_server/
    └── server.py          # Mock server for testing without hardware
packaging/
├── README.md              # Minimal package installation instructions (English)
└── README_JA.md           # Minimal package installation instructions (Japanese)
```

For the message types provided by `contact_glove_msgs` and the nodes provided by `contact_glove`,
see the [API reference](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/api).

---

## Build and run

### Tested environments

- Ubuntu 24.04 (Noble) + ROS2 Jazzy
- Ubuntu 22.04 (Jammy) + ROS2 Humble

### Supported versions

This repository supports **current LTS distributions only**. The only currently supported distributions are Jazzy and Humble, listed above, and `.deb` packages are provided only for these two configurations.

- Support is reviewed against each distribution's EOL (End of Life). As a guideline, **support ends approximately six months after EOL**; new features and fixes are no longer provided after that point.
  - ROS2 Humble: scheduled EOL 2027-05
  - ROS2 Jazzy: scheduled EOL 2029-05
- **ROS1, including Noetic, is not supported.**
- Other distributions that have reached EOL, such as Ubuntu 20.04 / ROS2 Foxy or Galactic, are also unsupported.

### Build the messages-only DEB

You can build `contactglove-ros2-msgs` alone without installing DivingStation or ContactGlove C++/C/Rust SDK V2.
The targets are Ubuntu 22.04 / ROS2 Humble / amd64 and Ubuntu 24.04 / ROS2 Jazzy / amd64.
Run the following from the repository root in an environment with the target OS and CPU architecture.

```bash
# Ubuntu 22.04 / ROS2 Humble
sudo apt update
sudo apt install build-essential cmake dpkg-dev python3-colcon-common-extensions \
  ros-humble-ament-cmake-auto ros-humble-rosidl-default-generators \
  ros-humble-geometry-msgs ros-humble-std-msgs
source /opt/ros/humble/setup.bash
export PACKAGE_BUILD_ID=12345.1  # Use a different ID for each distribution build
bash scripts/package_ros2_msgs.sh humble jammy

# For Ubuntu 24.04 / ROS2 Jazzy, replace humble with jazzy in the dependencies
# source /opt/ros/jazzy/setup.bash
# bash scripts/package_ros2_msgs.sh jazzy noble
```

The output is `dist/contactglove-ros2-msgs_<version>-1<codename>+ros2.<build-id>_amd64.deb`.
The script builds `contact_glove_msgs` in a temporary directory.
`scripts/verify_ros2_msgs_deb_install.sh` verifies DEB installation and the generated interfaces.
Use a disposable ROS container for verification because the script installs packages.

The remaining instructions build the complete SDK, including the bridge.

### Install dependencies

#### System packages

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  git \
  python3-colcon-common-extensions \
  ros-jazzy-rclcpp \
  ros-jazzy-rclpy \
  ros-jazzy-geometry-msgs \
  ros-jazzy-std-msgs \
  ros-jazzy-sensor-msgs \
  ros-jazzy-visualization-msgs \
  ros-jazzy-tf2-ros \
  ros-jazzy-rviz2 \
  ros-jazzy-xacro \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-ament-cmake-auto \
  ros-jazzy-ament-lint-auto \
  ros-jazzy-ament-lint-common \
  ros-jazzy-ament-cmake-gtest \
  ros-jazzy-rosidl-default-generators \
  ros-jazzy-rosidl-default-runtime
```

> If `ros-jazzy-desktop` is already installed, you do not need to install the runtime dependencies from `rclcpp` through `rviz2` individually. Install the `ament-*` / `rosidl-*` build and test dependencies as listed above.
> `ros-jazzy-xacro` / `ros-jazzy-robot-state-publisher` are required only for `contact_glove_with_urdf.launch.xml` (robot visualization with URDF and `robot_state_publisher`). Other features do not require them, but `colcon test` skips the URDF joint-name validation tests (`check_urdf_joint_names_*`) if xacro is unavailable.
> For ROS2 Humble, replace `ros-jazzy-*` with `ros-humble-*` above.

#### Python packages (only for the mock server)

```bash
sudo apt-get install python3-venv
python3 -m venv /tmp/contactglove-mock-venv
/tmp/contactglove-mock-venv/bin/python -m pip install python-osc
```

#### ContactGlove C++/C/Rust SDK V2 runtime

This ROS2 package links to the C++ SDK's `ContactGloveSDKv2::ContactGloveSDKv2` CMake target.
You can build C++ SDK 1.0.0 from the pinned submodule, extract its DEB into a working directory, and use it from there.
The required version in CMake is also 1.0.0.
`vendor/COLCON_IGNORE` prevents a normal `colcon build` from discovering the SDK itself.
Use DivingStation v2 or later.

### Set up the repository

```bash
git clone --recurse-submodules https://github.com/MeltInterfaceTechnologies/ContactGloveSDKv2ROS2.git
cd ContactGloveSDKv2ROS2
```

The C++ SDK is pinned to v1.0.0 (`8223da430eed7e5e41f601b59732a260d6ce1cd1`) in the public repository.
For an existing clone, run `git submodule sync --recursive`
followed by `git submodule update --init --recursive`.
The submodule is not required for messages-only builds. Building the C++ SDK fetches the pinned
oscpack revision over the network.

The following example uses Jazzy/Noble. For each distribution build, use a unique build ID
in the form `positive-integer.positive-integer`, with no leading zeros. Official distributions
use the GitHub Actions run ID and attempt. Do not redistribute different contents under the same
DEB version. Always use GitHub Actions artifacts for official distributions;
do not distribute local verification builds.

```bash
export PACKAGE_BUILD_ID=12345.1
export SDK_BUILD_DIR="$PWD/../sdk-package"
bash scripts/build_cpp_sdk.sh noble "$SDK_BUILD_DIR"
mkdir -p ../sdk-prefix
dpkg-deb -x "$SDK_BUILD_DIR"/*.deb ../sdk-prefix
export ContactGloveSDKv2_DIR="$PWD/../sdk-prefix/usr/lib/x86_64-linux-gnu/cmake/ContactGloveSDKv2"
export LD_LIBRARY_PATH="$PWD/../sdk-prefix/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
```

The build generates `$SDK_BUILD_DIR/sdk-provenance.json` and includes it as
`lib/sdk-provenance.json` in the distribution ZIP.

Building and packaging the SDK requires clean tracked files in both the ROS2 and C++ repositories.
Untracked and Git-ignored files are also rejected because they could be included in the installed files.
The ROS2 repository's root-level `build/`, `install/`, `log/`, and `dist/` directories,
and `scripts/__pycache__/`, are excluded as generated output.
Standard Git source archives do not include submodule contents.
To bundle the sources, run
`python3 scripts/create_source_archive.py ../contactglove-source.tar.gz` from a clean checkout.
This archive includes both source trees and file hashes, but no Git history.
The bundled hashes detect corruption; they are not signatures that authenticate the sources.

### Build

```bash
# For Ubuntu 24.04 / ROS2 Jazzy
source /opt/ros/jazzy/setup.bash

# For Ubuntu 22.04 / ROS2 Humble
# source /opt/ros/humble/setup.bash

colcon build --cmake-args -DContactGloveSDKv2_DIR="$ContactGloveSDKv2_DIR"
source install/setup.bash
```

> Run all subsequent commands after `source install/setup.bash`.

### Tests

`contact_glove` includes gtest unit tests for message conversion logic, such as `to_transform`, `wrist_frame_id`, and ergonomics index assignments.

```bash
colcon test
colcon test-result --verbose
```

The tests also verify 250 immediate connect/disconnect cycles and 100 immediate destructions of SDK instances
against the runtime built from the pinned C++ SDK, with a 30-second limit.
CI additionally uses two real ROS2 nodes to verify retries while awaiting approval,
source-port preservation, recovery of normal data after malformed OSC input, and sending
Disconnect only at shutdown. No hardware is used, and UDP traffic is limited to loopback.

```bash
timeout 45s python3 scripts/test_lan_retry.py \
  install/contact_glove/lib/contact_glove/contact_glove_node
```

`colcon test` also runs cppcheck, lint_cmake, and xmllint, plus cpplint for packages with C/C++ sources.
For lint configuration, see `src/contact_glove/CMakeLists.txt` and
`src/contact_glove_msgs/CMakeLists.txt`.

GitHub Actions (`.github/workflows/ci.yml`) runs `colcon build` and `colcon test` on both
Jazzy and Humble.

### Test without hardware (mock server)

`scripts/mock_server/server.py` is a mock server that stands in for a real DivingStation.
With no arguments, it generates synthetic left- and right-hand data for testing without hardware.
It listens only on `127.0.0.1:25791` (UDP). Run the ROS2 node on the same host and in the same network namespace.
For virtual-environment setup and testing instructions, see the [mock server guide](scripts/mock_server/README.md).

```bash
# Terminal 1: start the mock server
/tmp/contactglove-mock-venv/bin/python scripts/mock_server/server.py

# Terminal 2: start the ROS2 node
source install/setup.bash
ros2 launch contact_glove contact_glove_with_rviz.launch.xml
```

When the server starts, `[server] Client registered at 127.0.0.1:25788` is displayed and a skeleton appears in RViz2.

For `get_retarget_profile` requests to the mock server, the fixed left/right UUIDs (ending in `...0001` / `...0002`) succeed.
An unregistered valid UUID returns `status: 1`. The UUID ending in `...0003` deliberately receives no response, allowing you to test timeouts.

### Create the distribution ZIP

`scripts/package_ros2.sh` creates a distribution ZIP with `contactglove-ros2-bridge` and
`contactglove-ros2-msgs` DEBs for the same ROS2 distribution at its root
(`packaging/README.md` is included as `README.md`).
The distribution ZIP contains the README, bridge and msgs DEBs at the root, an `install/`
directory with the bridge and messages, a `lib/` directory with the C++ runtime DEB and provenance,
installation helper scripts, and license documents.
Both ROS2 packages also install the minimal English/Japanese READMEs and license documents.
The full guide, user manual, and API reference are maintained on the Web.
Install all three DEBs (bridge, msgs, and C++ runtime) on the publishing side, and only msgs on the subscribing side.

```bash
sudo apt-get install -y zip unzip dpkg-dev
source /opt/ros/jazzy/setup.bash
# Use the DEB and provenance from SDK_BUILD_DIR above.
bash scripts/package_ros2.sh jazzy noble
```

For details, see the comments in `scripts/package_ros2.sh`. To verify the DEBs included in the ZIP,
see `scripts/verify_ros2_deb_install.sh`.

## License

The first-party ROS 2 driver, messages, examples, and SDK documentation are licensed under [Apache-2.0](LICENSE.md).
Third-party components retain their own terms; [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) includes the full oscpack license text.
Check the respective providers for the licenses of ROS 2 dependencies.

The bundled C++ SDK is a DEB built from the pinned submodule by the ROS2 build process.

## C++ SDK provenance and checksums

The distribution ZIP's `lib/` directory contains the C++ runtime DEB and its provenance.
`$SDK_BUILD_DIR/sdk-provenance.json` is generated at build time and placed at
`lib/sdk-provenance.json` in the distribution ZIP. It records the source commit, build ID,
compiler and CMake versions, DEB control fields, and SHA-256.
Run the following from the root of the extracted ZIP and compare the result with `sha256` in `lib/sdk-provenance.json`.

```bash
sha256sum lib/contactglove-sdk-v2_*.deb
```

Building the C++ SDK fetches the pinned oscpack revision recorded in the SDK.
Each third-party component remains subject to its own license terms.

### Public C++ SDK and distribution packages

The C++ SDK source URL and gitlink are pinned to the public release. CI fetches it without
credentials and verifies clean installation, package ownership, ELF linking, msgs usage,
removal/reinstallation, and UDP/DDS recovery.
The bridge accepts only the official C++ DEB for the same Ubuntu release (`1.0.0-0jammy` /
`1.0.0-0noble`) or the exact full version of the C++ DEB bundled in that ZIP. These two verified
versions are listed explicitly because a simple version range could also accept a DEB built
for a different Ubuntu release.
When updating to a new C++ version, rebuild and verify the corresponding bridge as well.
Versions 2.0.0 and later, which change the ABI major version, are also rejected.
The bundled SDK is rebuilt from public sources in ROS2 CI and is not treated as byte-identical
to the official Release DEB.

This CI tests local DEBs. It does not verify APT server reachability or operation with real hardware.

### Upgrade to 1.0.0

In 1.0.0, the C++ runtime shared-library name changes from `.so.0` to `.so.1`.
Do not update only the C++ runtime while leaving an old bridge installed. Update the bridge,
msgs, and C++ runtime together as a compatible set for the same Ubuntu release.
The current CI does not verify upgrades from a complete set of the actual 0.2.5 distribution packages.
Before upgrading an existing installation, test the actual package combination in a disposable environment.
