#!/usr/bin/env python3
"""Exercise real ROS2 nodes through delayed approval and malformed UDP traffic.

Source the ROS2 and contact_glove install environments before running.
Usage: python3 scripts/test_lan_retry.py <path-to-contact_glove_node>
"""
import argparse
import signal
import socket
import struct
import subprocess
import tempfile
import time

import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile
from contact_glove_msgs.msg import GloveData
def osc_string(value):
    raw = value.encode("utf-8") + b"\0"
    return raw + b"\0" * ((4 - len(raw) % 4) % 4)


def osc_address(packet):
    try:
        return packet[:packet.index(b"\0")].decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return ""


def device_message():
    return b"".join([
        osc_string("/DS2/HC/Device"),
        osc_string(",issiiiiiisi"),
        struct.pack(">i", 2),
        osc_string("sender-port-test"),
        osc_string(""),
        struct.pack(">iiiiii", 80, 1, 1, 3, 5, 1),
        osc_string("Sender Port Test"),
        struct.pack(">i", 0),
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable")
    args = parser.parse_args()
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 25811))
    server.setblocking(False)
    ports = (25812, 25814)
    endpoints = {port: set() for port in ports}
    requests = {port: 0 for port in ports}
    disconnects = []
    samples = [0, 0]
    processes = []
    logs = []
    succeeded = False
    rclpy.init()
    observer = rclpy.create_node("lan_retry_observer")
    subscriptions = []

    def sample(index):
        def receive(message):
            if message.id == "sender-port-test":
                samples[index] += 1
        return receive

    def poll(duration, send_data=False):
        end = time.monotonic() + duration
        next_packet = 0
        while time.monotonic() < end:
            while True:
                try:
                    packet, sender = server.recvfrom(4096)
                except BlockingIOError:
                    break
                address = osc_address(packet)
                if address == "/DS2/HC/Connect":
                    callback_port = struct.unpack(">i", packet[-4:])[0]
                    assert callback_port in endpoints, callback_port
                    endpoints[callback_port].add(sender)
                    requests[callback_port] += 1
                elif address == "/DS2/HC/Disconnect":
                    disconnects.append(sender)
            if send_data and time.monotonic() >= next_packet:
                for port in ports:
                    server.sendto(device_message(), ("127.0.0.1", port))
                next_packet = time.monotonic() + 0.05
            rclpy.spin_once(observer, timeout_sec=0.01)
            assert all(proc.poll() is None for proc in processes), "node exited early"

    try:
        for index, port in enumerate(ports):
            subscriptions.append(observer.create_subscription(
                GloveData, f"/lan_retry_{index}/left/glove_data", sample(index),
                QoSProfile(depth=16, durability=DurabilityPolicy.TRANSIENT_LOCAL)))
            log = tempfile.TemporaryFile(mode="w+")
            logs.append(log)
            processes.append(subprocess.Popen([
                args.executable, "--ros-args", "-r", f"__ns:=/lan_retry_{index}",
                "-p", "ds_port:=25811", "-p", f"receive_port:={port}",
                "-p", "timeout_duration:=250", "-p", "send_port:=0"],
                stdout=log, stderr=subprocess.STDOUT))

        poll(3.0)  # Human has not approved yet, exceeding several data timeouts.
        assert all(count >= 3 for count in requests.values()), requests
        assert all(len(values) == 1 for values in endpoints.values()), endpoints
        assert len(set.union(*endpoints.values())) == 2, endpoints
        assert not disconnects, disconnects
        # An unterminated OSC address previously escaped the receive thread
        # and aborted the process. Both nodes must survive it and still publish
        # the subsequent valid device messages through the native SDK library.
        for port in ports:
            server.sendto(b"/bad", ("127.0.0.1", port))
        poll(0.2)
        poll(2.0, send_data=True)
        assert all(count > 0 for count in samples), samples
        before = requests.copy()
        previous_samples = samples.copy()
        poll(1.5)  # Simulate data loss / DivingStation downtime after approval.
        assert all(requests[port] > before[port] for port in ports), requests
        assert not disconnects, disconnects
        poll(1.0, send_data=True)
        assert all(samples[i] > previous_samples[i] for i in range(2)), samples
        assert all(len(values) == 1 for values in endpoints.values()), endpoints
        succeeded = True
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        for log in logs:
            log.seek(0)
            output = log.read()
            if not succeeded:
                print(output)
            log.close()
        if succeeded:
            shutdown_ports = set()
            while True:
                try:
                    packet, sender = server.recvfrom(4096)
                except BlockingIOError:
                    break
                if osc_address(packet) == "/DS2/HC/Disconnect":
                    shutdown_ports.add(struct.unpack(">i", packet[-4:])[0])
            assert shutdown_ports == set(ports), shutdown_ports
        observer.destroy_node()
        rclpy.shutdown()
        server.close()
    print(f"PASS: two distinct stable endpoints {endpoints}; "
          f"requests={requests}; ROS samples={samples}; "
          "malformed-packet recovery; Disconnect only at explicit shutdown")


if __name__ == "__main__":
    main()
