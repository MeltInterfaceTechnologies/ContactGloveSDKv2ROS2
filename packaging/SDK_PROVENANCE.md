# Native SDK build provenance

The native SDK DEB in this distribution is built from the C++ submodule by
the ROS 2 build. The build generates `sdk-provenance.json` alongside the DEB
in `SDK_BUILD_DIR`, then places it
at `lib/sdk-provenance.json` inside the distribution ZIP. It records source
commits, build ID, compiler and CMake versions, DEB control fields and SHA-256.
From the extracted ZIP root, verify the DEB's checksum with:

```bash
sha256sum lib/contactglove-sdk-v2_*.deb
```

Compare the result with `sha256` in `lib/sdk-provenance.json`. The build also
downloads the fixed oscpack dependency recorded by the C++ SDK. Third-party
components retain their own license terms.

The ROS 2 SDK version is @ROS2_VERSION@.
