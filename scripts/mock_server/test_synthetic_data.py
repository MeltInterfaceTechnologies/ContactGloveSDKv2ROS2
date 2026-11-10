"""Synthetic mock regressions; no ROS installation required."""
import math
from contextlib import redirect_stderr
from io import StringIO
import unittest
from unittest.mock import patch

from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder

import server


class SyntheticDataTest(unittest.TestCase):
    def test_default_generates_four_second_loop(self):
        mock = server.MockDivingStationServer()
        self.assertEqual(len(mock._data["frames"]), 200)
        self.assertEqual(mock._data["sample_interval_ms"], 20)
        self.assertEqual(mock._data["loop_duration_ms"], 4000)
        self.assertEqual([frame["elapsed_ms"] for frame in mock._data["frames"]],
                         list(range(0, 4000, 20)))

    def test_frames_have_finite_mirrored_positions_and_unit_quaternions(self):
        data = server._synthetic_data()
        for frame in data["frames"]:
            left, right = frame["hands"]["left"], frame["hands"]["right"]
            for finger in ("thumb", "index", "middle", "ring", "little"):
                positions = left["joint_positions"][finger]
                self.assertEqual(len(positions), 5 if finger == "thumb" else 6)
                self.assertEqual(positions[0], [0.0, 0.0, 0.0])
                for lp, rp in zip(positions, right["joint_positions"][finger]):
                    self.assertTrue(all(math.isfinite(v) for v in lp + rp))
                    self.assertEqual(lp, [-rp[0], rp[1], rp[2]])
                for quaternion in left["hand_quaternions"][finger].values():
                    self.assertAlmostEqual(sum(v * v for v in quaternion.values()), 1.0)
        self.assertNotEqual(data["frames"][0]["hands"], data["frames"][50]["hands"])

    def test_synthetic_frames_encode_protocol_record_lengths(self):
        for frame in server._synthetic_data()["frames"]:
            for side in ("left", "right"):
                hand = frame["hands"][side]
                for expected, record in (
                    (157, server._hand_to_skeleton_record(
                        hand, "mock", server.PROFILE_UUID_LEFT, side == "left", 123)),
                    (156, server._hand_to_raw_skeleton_record(
                        hand, "mock", side == "left", 123)),
                    (25, server._hand_to_ergonomics_record("mock", side == "left", 123, 40)),
                ):
                    builder = OscMessageBuilder(address="/test")
                    for tag, value in record:
                        builder.add_arg(value, tag)
                    self.assertEqual(len(OscMessage(builder.build().dgram).params), expected)

    def test_cli_accepts_no_data_file(self):
        self.assertEqual(vars(server._parse_args([])), {})
        for args in (["/tmp/motion.json"], ["--data-file", "/tmp/motion.json"]):
            with self.subTest(args=args), redirect_stderr(StringIO()), \
                    self.assertRaises(SystemExit) as error:
                server._parse_args(args)
            self.assertEqual(error.exception.code, 2)

    def test_constructor_rejects_external_data(self):
        with self.assertRaises(TypeError):
            server.MockDivingStationServer({})
        with self.assertRaises(TypeError):
            server.MockDivingStationServer(data={})

    def test_start_binds_only_loopback_and_closes_socket(self):
        mock = server.MockDivingStationServer()
        with patch.object(server, "ThreadingOSCUDPServer") as udp_server, \
                patch.object(server.threading, "Thread"):
            udp_server.return_value.serve_forever.side_effect = KeyboardInterrupt
            mock.start()
            self.assertEqual(udp_server.call_args.args[0], ("127.0.0.1", 25791))
            udp_server.return_value.server_close.assert_called_once_with()
            self.assertFalse(mock._running)

    def test_synthetic_stream_uses_current_timestamp(self):
        mock = server.MockDivingStationServer()
        mock._clients[("127.0.0.1", 12345)] = True
        mock._running = True

        def stop(_):
            mock._running = False

        with patch.object(server.time, "sleep", side_effect=stop), \
                patch.object(server.time, "time", return_value=1790939999.123), \
                patch.object(server, "_send_osc") as send:
            mock._stream_frames()
        skeleton = next(call.args[3] for call in send.call_args_list
                        if call.args[2] == "/DS2/HC/HandSkeleton")
        self.assertEqual(skeleton[4:6], [("i", value) for value in
                                       server._timestamp_words(1790939999123)])
        self.assertEqual({call.args[2] for call in send.call_args_list}, {
            "/DS2/HC/HandSkeleton", "/DS2/HC/HandSkeletonRaw",
            "/DS2/HC/Ergonomics", "/DS2/HC/Device"})

    def test_stream_loops_at_50_hz_with_two_hands_on_all_streams(self):
        mock = server.MockDivingStationServer()
        mock._clients[("127.0.0.1", 12345)] = True
        mock._running = True
        ticks = []

        def tick(interval):
            ticks.append(interval)
            if len(ticks) == 201:
                mock._running = False

        now_ms = 1790939999123
        with patch.object(server.time, "sleep", side_effect=tick), \
                patch.object(server.time, "time", return_value=now_ms / 1000), \
                patch.object(server, "_send_osc") as send:
            mock._stream_frames()
        self.assertEqual(ticks, [0.02] * 201)
        self.assertEqual(send.call_count, 6 * 201)
        expected = [
            ("HandSkeleton", 158), ("HandSkeleton", 158),
            ("HandSkeletonRaw", 157), ("HandSkeletonRaw", 157),
            ("Ergonomics", 51), ("Device", 21),
        ]
        for index, call in enumerate(send.call_args_list):
            ip, port, address, record = call.args
            stream, length = expected[index % 6]
            self.assertEqual((ip, port), ("127.0.0.1", 12345))
            self.assertEqual(address, "/DS2/HC/" + stream)
            builder = OscMessageBuilder(address=address)
            for tag, value in record:
                builder.add_arg(value, tag)
            params = OscMessage(builder.build().dgram).params
            self.assertEqual(len(params), length)
            self.assertEqual(params[0], 2)
            timestamp_offsets = {"HandSkeleton": [4], "HandSkeletonRaw": [3],
                                 "Ergonomics": [3, 28], "Device": []}
            for offset in timestamp_offsets[stream]:
                self.assertEqual(tuple(params[offset:offset + 2]),
                                 server._timestamp_words(now_ms))
        first = send.call_args_list[:6]
        last = send.call_args_list[-6:]
        self.assertEqual(first, last)
        self.assertNotEqual(first[0], send.call_args_list[50 * 6])
        self.assertEqual(first[0].args[3][1:4], [
            ("s", server.DEVICE_ID_LEFT), ("s", server.PROFILE_UUID_LEFT), ("i", 1)])
        self.assertEqual(first[1].args[3][1:4], [
            ("s", server.DEVICE_ID_RIGHT), ("s", server.PROFILE_UUID_RIGHT), ("i", 0)])

    def test_profile_replies_preserve_request_ids_and_status(self):
        mock = server.MockDivingStationServer()
        mock._on_connect("/DS2/HC/Connect", 12345)
        unknown_uuid = "00000000-0000-4000-8000-000000000004"
        for uuid, status in ((server.PROFILE_UUID_LEFT, 0),
                             (server.PROFILE_UUID_RIGHT, 0),
                             (unknown_uuid, 1), ("invalid", 2)):
            with self.subTest(uuid=uuid), patch.object(server, "_send_osc") as send:
                mock._on_get_retarget_profile("/DS2/HC/HandSkeleton/Profile/Get", 2, 42, uuid)
                send.assert_called_once()
                self.assertEqual(send.call_args.args[:3],
                                 ("127.0.0.1", 12345, "/DS2/HC/HandSkeleton/Profile"))
                name, description = server.RETARGET_PROFILES.get(uuid, ("", ""))
                self.assertEqual(send.call_args.args[3], [
                    ("i", 2), ("i", 42), ("s", uuid if status != 2 else ""),
                    ("i", status), ("s", name), ("s", description)])
        with patch.object(server, "_send_osc") as send:
            mock._on_get_retarget_profile("/test", 2, 42, server.PROFILE_UUID_NO_RESPONSE)
            mock._on_get_retarget_profile("/test", 1, 42, server.PROFILE_UUID_LEFT)
            mock._on_get_retarget_profile("/test", 2, 42)
            mock._on_get_retarget_profile("/test", 2, "42", server.PROFILE_UUID_LEFT)
            send.assert_not_called()
        mock._on_disconnect("/DS2/HC/Disconnect", 12345)
        self.assertEqual(mock._clients, {})


if __name__ == "__main__":
    unittest.main()
