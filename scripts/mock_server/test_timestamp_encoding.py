"""Regression tests for the mock server's signed OSC timestamp words."""
import unittest

from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder

import server


class TimestampEncodingTest(unittest.TestCase):
    def test_timestamp_boundaries_round_trip_all_streams(self):
        # OSC i is signed int32; the protocol joins each word as uint32 bits.
        timestamps = (
            0, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x100000000,
            1_790_939_999_123, 0x7FFFFFFFFFFFFFFF,
            0x8000000000000000, 0xFFFFFFFFFFFFFFFF,
        )
        hand = {"joint_positions": {}}
        for timestamp in timestamps:
            for label, record, offset in (
                ("skeleton", server._hand_to_skeleton_record(
                    hand, "synthetic", server.PROFILE_UUID_LEFT, True, timestamp), 3),
                ("raw", server._hand_to_raw_skeleton_record(
                    hand, "synthetic", True, timestamp), 2),
                ("ergonomics", server._hand_to_ergonomics_record(
                    "synthetic", True, timestamp, 0.0), 2),
            ):
                with self.subTest(timestamp=timestamp, stream=label):
                    builder = OscMessageBuilder(address="/test")
                    for tag, value in record:
                        builder.add_arg(value, tag)
                    args = OscMessage(builder.build().dgram).params
                    hi, lo = args[offset:offset + 2]
                    self.assertGreaterEqual(hi, -0x80000000)
                    self.assertLessEqual(hi, 0x7FFFFFFF)
                    self.assertGreaterEqual(lo, -0x80000000)
                    self.assertLessEqual(lo, 0x7FFFFFFF)
                    actual = ((hi & 0xFFFFFFFF) << 32) | (lo & 0xFFFFFFFF)
                    self.assertEqual(actual, timestamp)


if __name__ == "__main__":
    unittest.main()
