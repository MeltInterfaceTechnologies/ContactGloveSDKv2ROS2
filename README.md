# ContactGlove ROS2 SDK V2

English | [日本語](README_JA.md)

Receive ContactGlove3 Pro data from DivingStation as ROS2 topics and services through the [ContactGlove C++/C/Rust SDK V2](https://github.com/MeltInterfaceTechnologies/ContactGloveSDKv2Cpp).

## Requirements

- Ubuntu 22.04 LTS / ROS2 Humble / amd64, or Ubuntu 24.04 LTS / ROS2 Jazzy / amd64.
- The bridge requires DivingStation v2 or later and the C++ runtime. A separate subscriber PC or container can use the messages-only package without the C++ runtime.

## Documentation

- [SDK guide](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2)
- [User manual](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/user-manual)
- [API reference](https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/api)

See the [package installation instructions](packaging/README.md) for bridge and subscriber-only installation and a minimal launch example. Full user documentation is maintained on the Web.

For source builds, tests, packaging and native SDK provenance, see [DEVELOPMENT.md](DEVELOPMENT.md). The [mock server](scripts/mock_server/README.md) provides synthetic data for local testing without hardware.

## License

[Apache-2.0](LICENSE.md). See also [NOTICE.md](NOTICE.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Third-party components retain their own license terms.
