# Mock DivingStation server

English | [日本語](README_JA.md)

A local mock for testing without a glove or DivingStation. It generates
synthetic left/right hand motion and sends `HandSkeleton`, `HandSkeletonRaw`,
`Ergonomics` and `Device` OSC messages.
The motion is illustrative, not measured hand data or a calibration model.

## Run with synthetic data

From the repository root on Ubuntu 22.04 or 24.04, install the dependency in a
virtual environment (do not install into Ubuntu's system Python):

```sh
sudo apt-get install python3-venv
python3 -m venv /tmp/contactglove-mock-venv
/tmp/contactglove-mock-venv/bin/python -m pip install python-osc
/tmp/contactglove-mock-venv/bin/python scripts/mock_server/server.py
```

The server listens only on `127.0.0.1:25791` (UDP) and sends data to registered
loopback clients. Run the ROS2 node on the same host, or in the same network
namespace. Do not run DivingStation on that port at the same time.
In a second terminal, after building and sourcing the ROS2 workspace:

```sh
source install/setup.bash
ros2 launch contact_glove contact_glove_with_rviz.launch.xml
```

Stop the mock with Ctrl+C. With real hardware, use DivingStation instead.

## Profile requests and tests

The fixed profile UUIDs ending in `0001` and `0002` return the mock left/right
profiles. An unknown valid UUID returns status 1. The UUID ending in `0003`
deliberately receives no response to exercise client timeouts. Profile replies
are sent to all registered local clients.

```sh
/tmp/contactglove-mock-venv/bin/python -m unittest discover -s scripts/mock_server -p 'test_*.py' -v
```
