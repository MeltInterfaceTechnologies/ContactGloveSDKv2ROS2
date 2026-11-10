// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#include <exception>
#include <iostream>
#include <stdexcept>

#include "contactglove/ContactGloveSDKv2.hpp"

int main()
{
  using ContactGloveSDKv2::Host;
  using ContactGloveSDKv2::SDK;
  using ContactGloveSDKv2::SDKReturnCode;

  // No server or physical device is needed. A zero receive port asks the OS
  // for an unused socket; callback delivery is covered by test_lan_retry.py.
  Host host;
  host.hostName = "ros2-native-lifecycle-test";
  host.ipAddress = "127.0.0.1";
  host.port = 25811;
  host.receivePort = 0;
  host.sendPort = 0;

  try {
    SDK sdk;
    for (int iteration = 0; iteration < 250; ++iteration) {
      if (sdk.ConnectToHost(host) != SDKReturnCode::Success ||
        sdk.Disconnect(host) != SDKReturnCode::Success ||
        sdk.Disconnect(host) != SDKReturnCode::NotConnected)
      {
        throw std::runtime_error("immediate connect/disconnect failed");
      }
    }
    for (int iteration = 0; iteration < 100; ++iteration) {
      SDK temporary;
      if (temporary.ConnectToHost(host) != SDKReturnCode::Success) {
        throw std::runtime_error("connect before immediate destruction failed");
      }
    }
  } catch (const std::exception & error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
  std::cout << "PASS: 250 immediate connect/disconnect cycles and "
    "100 immediate SDK destructions using the native SDK library\n";
  return 0;
}
