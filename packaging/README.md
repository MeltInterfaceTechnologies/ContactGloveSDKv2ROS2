# ContactGlove ROS2 SDK V2

English | [日本語](README_JA.md)

## Requirements

- Supported hardware: ContactGlove3 Pro.
- Ubuntu 22.04 LTS / ROS 2 Humble / amd64 (x86-64), or Ubuntu 24.04 LTS / ROS 2 Jazzy / amd64 (x86-64).
- Configure ROS 2 and its APT repository first. Use the ZIP matching the OS and ROS 2 distribution; ARM64 and other OS/ROS 2 versions are outside this distribution's scope.
- Publishing requires DivingStation v2 or later and the bundled C++ runtime 1.0.0. Subscriber-only systems require neither DivingStation nor the C++ runtime.

## Install and start

Run from the extracted ZIP directory. To publish glove data, install all three local DEBs:

```bash
sudo apt update
sudo apt install ./lib/contactglove-sdk-v2_*.deb \
  ./contactglove-ros2-msgs_*.deb ./contactglove-ros2-bridge_*.deb
```

For a subscriber-only PC or container, install only `contactglove-ros2-msgs` (the `contact_glove_msgs` interfaces):

```bash
sudo apt update
sudo apt install ./contactglove-ros2-msgs_*.deb
```

Source ROS 2 in every new terminal. On the publishing system, start DivingStation and connect a glove before launching the bridge:

```bash
# Ubuntu 24.04 / Jazzy; use /opt/ros/humble/setup.bash for Ubuntu 22.04 / Humble.
source /opt/ros/jazzy/setup.bash
ros2 launch contact_glove contact_glove.launch.xml
```

On a subscriber-only system, source ROS 2 without launching the bridge or sourcing the ZIP's `install/`. Use the same ROS 2 distribution, compatible message definitions, and `ROS_DOMAIN_ID` as the publishing system; permit DDS discovery and communication.

## Web documentation

- [SDK guide](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2)
- [User Manual](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/user-manual): upgrades, ZIP overlay use, connections, visualization, and troubleshooting.
- [API reference](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/api)

Apache-2.0. See the bundled `LICENSE.md`, `NOTICE.md`, and `THIRD_PARTY_NOTICES.md` for license and third-party terms.
