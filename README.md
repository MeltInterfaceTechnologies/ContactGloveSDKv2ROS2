# ContactGlove ROS2 SDK V2

English | [日本語](README_JA.md)

Receive ContactGlove3 Pro data from DivingStation as ROS2 topics and services through the [ContactGlove C++/C/Rust SDK V2](https://github.com/MeltInterfaceTechnologies/ContactGloveSDKv2Cpp).

## Requirements

- Ubuntu 22.04 LTS / ROS2 Humble / amd64, or Ubuntu 24.04 LTS / ROS2 Jazzy / amd64.
- The bridge requires DivingStation v2 or later and the C++ runtime. A separate subscriber PC or container can use the messages-only package without the C++ runtime.

## Install from APT

Configure the matching ROS2 distribution and its APT repository first, then follow the shared [APT repository setup](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/apt-repository). Refresh the package index and check candidates as described in the [ROS2 APT guide](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2#install-from-apt), then choose the package for this system:

- Publishing system: `sudo apt-get install contactglove-ros2-bridge`. APT also installs the same-version msgs package and the compatible C++ runtime.
- Subscriber-only PC or container: `sudo apt-get install contactglove-ros2-msgs`. This does not install the bridge or C++ runtime.

See the [ROS2 APT guide](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2#install-from-apt) for updates, terminal setup, and ZIP/APT compatibility notes.

## Documentation

- [SDK guide](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2)
- [User manual](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/user-manual)
- [API reference](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/api)

For the ZIP route, see the [ZIP installation instructions](packaging/README.md) for bridge and subscriber-only installation and a minimal launch example. Full user documentation is maintained on the Web.

For source builds, tests, packaging and native SDK provenance, see [DEVELOPMENT.md](DEVELOPMENT.md). The [mock server](scripts/mock_server/README.md) provides synthetic data for local testing without hardware.

## License

[Apache-2.0](LICENSE.md). See also [NOTICE.md](NOTICE.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Third-party components retain their own license terms.
