#!/usr/bin/env python3
"""Local mock DivingStation with synthetic hand motion.

Run without arguments to generate a four-second open/close loop.
Listens on 127.0.0.1:25791 and sends OSC streams to registered local clients.
"""

import argparse
import math
import re
import socket
import threading
import time

from pythonosc import dispatcher
from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.osc_server import ThreadingOSCUDPServer

DS_HOST = "127.0.0.1"
DS_PORT = 25791
DEVICE_ID_LEFT = "CG3-LEFT-001"
DEVICE_ID_RIGHT = "CG3-RIGHT-001"
PROFILE_UUID_LEFT = "00000000-0000-4000-8000-000000000001"
PROFILE_UUID_RIGHT = "00000000-0000-4000-8000-000000000002"
# This valid UUID deliberately gets no reply, so the ROS2 service timeout path can be tested.
PROFILE_UUID_NO_RESPONSE = "00000000-0000-4000-8000-000000000003"

RETARGET_PROFILES = {
    PROFILE_UUID_LEFT: ("Mock left hand", "Retarget profile used by the mock left hand."),
    PROFILE_UUID_RIGHT: ("Mock right hand", "Retarget profile used by the mock right hand."),
}

_IDENTITY_QUAT = {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}
_PROFILE_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _send_osc(ip: str, port: int, address: str, args: list) -> None:
    builder = OscMessageBuilder(address=address)
    for tag, value in args:
        builder.add_arg(value, tag)
    msg = builder.build()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.sendto(msg.dgram, (ip, port))
        except OSError:
            pass


def _timestamp_words(timestamp_ms: int) -> tuple[int, int]:
    """Preserve timestamp bits as two signed OSC int32 words."""
    def signed_word(value: int) -> int:
        value &= 0xFFFF_FFFF
        return value if value < 0x8000_0000 else value - 0x1_0000_0000

    return signed_word(timestamp_ms >> 32), signed_word(timestamp_ms)


def _is_uuid(value: str) -> bool:
    return _PROFILE_UUID_RE.fullmatch(value) is not None


def _hand_to_skeleton_record(
    hand: dict, device_id: str, profile_uuid: str, is_left: bool, timestamp_ms: int
) -> list:
    """Return the 157 OSC args for one HandSkeleton record (without the leading version int).

    Node order matches SkeletonNode enum (25 positions):
        wrist, thumb_cmc..tip, index_cmc..tip, middle_cmc..tip, ring_cmc..tip, little_cmc..tip

    Rotation order matches SkeletonRotationNode enum (19 rotations):
        thumb_cmc/mcp/ip, index_cmc/mcp/pip/dip, middle_cmc/mcp/pip/dip,
        ring_cmc/mcp/pip/dip, little_cmc/mcp/pip/dip
    """
    joints = hand["joint_positions"]
    quats = hand.get("hand_quaternions", {})

    def q(finger: str, joint_name: str) -> dict:
        return quats.get(finger, {}).get(joint_name, _IDENTITY_QUAT)

    def pos(chain: list, i: int) -> list:
        return chain[i] if i < len(chain) else [0.0, 0.0, 0.0]

    thumb = joints.get("thumb", [])    # [wrist_origin, cmc, mcp, ip, tip] = 5 entries
    index = joints.get("index", [])    # [wrist_origin, cmc, mcp, pip, dip, tip] = 6 entries
    middle = joints.get("middle", [])
    ring = joints.get("ring", [])
    little = joints.get("little", [])    # little finger

    # 25 positions in SkeletonNode index order.
    # Each finger chain starts at the wrist origin; joints start at index 1.
    positions = [
        [0.0, 0.0, 0.0],                                              # wrist
        pos(thumb, 1), pos(thumb, 2), pos(thumb, 3), pos(thumb, 4),  # thumb cmc..tip
        pos(index, 1), pos(index, 2), pos(index, 3), pos(index, 4), pos(index, 5),
        pos(middle, 1), pos(middle, 2), pos(middle, 3), pos(middle, 4), pos(middle, 5),
        pos(ring, 1), pos(ring, 2), pos(ring, 3), pos(ring, 4), pos(ring, 5),
        pos(little, 1), pos(little, 2), pos(little, 3), pos(little, 4), pos(little, 5),
    ]

    # 19 local quaternions in SkeletonRotationNode index order.
    # The synthetic index/middle/ring/little CMC rotations use identity.
    rotations = [
        q("thumb", "cmc"), q("thumb", "mcp"), q("thumb", "ip"),
        _IDENTITY_QUAT, q("index", "mcp"), q("index", "pip"), q("index", "dip"),
        _IDENTITY_QUAT, q("middle", "mcp"), q("middle", "pip"), q("middle", "dip"),
        _IDENTITY_QUAT, q("ring", "mcp"), q("ring", "pip"), q("ring", "dip"),
        _IDENTITY_QUAT, q("little", "mcp"), q("little", "pip"), q("little", "dip"),
    ]

    hi, lo = _timestamp_words(timestamp_ms)

    args: list = [
        ("s", device_id),
        ("s", profile_uuid),         # profile_uuid
        ("i", 1 if is_left else 0),  # is_left
        ("i", hi), ("i", lo),        # generated_at_ms hi/lo
        ("i", 0),                    # tracking_state (tracked)
    ]
    for px, py, pz in positions:
        args += [("f", float(px)), ("f", float(py)), ("f", float(pz))]
    for rot in rotations:
        args += [
            ("f", float(rot["w"])), ("f", float(rot["x"])),
            ("f", float(rot["y"])), ("f", float(rot["z"])),
        ]
    return args  # 157 args total per the spec


def _hand_to_raw_skeleton_record(
    hand: dict, device_id: str, is_left: bool, timestamp_ms: int
) -> list:
    """Return the 156 OSC args for one HandSkeletonRaw record (without the version int).

    HandSkeletonRaw uses the same positions and rotations as HandSkeleton, without
    the profile UUID. This mock exercises the wire format, not retargeting.
    """
    skeleton_record = _hand_to_skeleton_record(
        hand, device_id, PROFILE_UUID_LEFT, is_left, timestamp_ms
    )
    return [skeleton_record[0], *skeleton_record[2:]]


def _hand_to_ergonomics_record(
    device_id: str, is_left: bool, timestamp_ms: int, flex_deg: float
) -> list:
    """Return the 25 OSC args for one Ergonomics record.

    string id, int is_left, int generated_at_ms_hi/lo, int tracking_state, float[20]
    (ErgonomicsDataType order: thumb.{cmc,mcp,ip,tilt}, then index/middle/ring/little each
    .{mcp,pip,dip,tilt}). Angles are synthetic;
    they exercise joint_states and the URDF demo, not measured biomechanics.
    """
    hi, lo = _timestamp_words(timestamp_ms)
    values = [
        flex_deg, flex_deg, flex_deg, 0.0,  # thumb: cmc, mcp, ip, tilt
        flex_deg, flex_deg, flex_deg, 0.0,  # index: mcp, pip, dip, tilt
        flex_deg, flex_deg, flex_deg, 0.0,  # middle
        flex_deg, flex_deg, flex_deg, 0.0,  # ring
        flex_deg, flex_deg, flex_deg, 0.0,  # little
    ]
    args: list = [
        ("s", device_id),
        ("i", 1 if is_left else 0),  # is_left
        ("i", hi), ("i", lo),
        ("i", 0),                    # tracking_state (tracked)
    ]
    args += [("f", float(v)) for v in values]
    return args  # 25 args total per the spec


def _synthetic_data() -> dict:
    """Generate a four-second hand-motion loop in metres.

    This is a simple illustrative hand, not an anatomical or calibration model.
    """
    frames = []
    for frame_index in range(200):
        timestamp_ms = frame_index * 20
        flex = math.radians(40.0 + 40.0 * math.sin(2 * math.pi * frame_index / 200))
        hands = {}
        for side, mirror in (("left", -1.0), ("right", 1.0)):
            joints = {}
            quaternions = {}
            for finger, x, length, count in (
                ("thumb", -0.04, 0.025, 4), ("index", -0.02, 0.025, 5),
                ("middle", 0.0, 0.028, 5), ("ring", 0.02, 0.025, 5),
                ("little", 0.04, 0.02, 5),
            ):
                chain = [[0.0, 0.0, 0.0], [mirror * x, 0.035, 0.0]]
                for segment in range(1, count):
                    angle = flex * segment / (count - 1)
                    previous = chain[-1]
                    chain.append([previous[0], previous[1] + length * math.cos(angle),
                                  previous[2] + length * math.sin(angle)])
                joints[finger] = chain
                local_angle = flex / (count - 1)
                rotation = {"w": math.cos(local_angle / 2),
                            "x": math.sin(local_angle / 2), "y": 0.0, "z": 0.0}
                names = ("cmc", "mcp", "ip") if finger == "thumb" else ("mcp", "pip", "dip")
                quaternions[finger] = {name: dict(rotation) for name in names}
            hands[side] = {"joint_positions": joints, "hand_quaternions": quaternions}
        frames.append({"elapsed_ms": timestamp_ms, "hands": hands})
    return {"frames": frames, "sample_interval_ms": 20, "loop_duration_ms": 4000}


class MockDivingStationServer:
    def __init__(self) -> None:
        self._data = _synthetic_data()
        self._clients: dict = {}   # (ip, port) -> True
        self._lock = threading.Lock()
        self._running = False

    # ------------------------------------------------------------------
    # OSC command handlers (called from the server receive thread)
    # ------------------------------------------------------------------

    def _on_connect(self, address: str, *args: object) -> None:
        if not args or not isinstance(args[0], int):
            return
        port = int(args[0])
        with self._lock:
            self._clients[("127.0.0.1", port)] = True
        print(f"[server] Client registered at 127.0.0.1:{port}")

    def _on_disconnect(self, address: str, *args: object) -> None:
        if not args or not isinstance(args[0], int):
            return
        port = int(args[0])
        with self._lock:
            self._clients.pop(("127.0.0.1", port), None)
        print(f"[server] Client unregistered from 127.0.0.1:{port}")

    def _on_get_retarget_profile(self, address: str, *args: object) -> None:
        """Reply with the protocol's request_id unchanged for each registered client.

        The mock's Connect command stores the receive port but not a unique connection token;
        broadcasting is therefore sufficient for its one-node development use case. Production
        DivingStation routes the reply to the connection that sent the request.
        """
        if len(args) != 3 or not isinstance(args[0], int) or not isinstance(args[1], int) or \
                not isinstance(args[2], str):
            return
        version, request_id, profile_uuid = args
        if version != 2:
            return

        if profile_uuid == PROFILE_UUID_NO_RESPONSE:
            print(f"[server] Suppressing profile response for request {request_id} (timeout test)")
            return

        if profile_uuid in RETARGET_PROFILES:
            status = 0
            name, description = RETARGET_PROFILES[profile_uuid]
            response_uuid = profile_uuid
        elif _is_uuid(profile_uuid):
            status = 1
            name = ""
            description = ""
            response_uuid = profile_uuid
        else:
            status = 2
            name = ""
            description = ""
            response_uuid = ""

        response_args = [
            ("i", 2), ("i", request_id), ("s", response_uuid), ("i", status),
            ("s", name), ("s", description),
        ]
        with self._lock:
            clients = list(self._clients.keys())
        for ip, port in clients:
            _send_osc(ip, port, "/DS2/HC/HandSkeleton/Profile", response_args)

    # ------------------------------------------------------------------
    # Frame streaming thread
    # ------------------------------------------------------------------

    def _stream_frames(self) -> None:
        frames = self._data["frames"]
        frame_interval_s = self._data["sample_interval_ms"] / 1000.0
        frame_idx = 0

        while self._running:
            frame = frames[frame_idx]
            ts = int(time.time() * 1000)
            hands = frame["hands"]

            # HandSkeleton is one complete device record per message in SDK 0.3.0.
            skeleton_messages: list[list] = []
            raw_skeleton_messages: list[list] = []
            if "left" in hands:
                skeleton_messages.append([("i", 2)] + _hand_to_skeleton_record(
                    hands["left"], DEVICE_ID_LEFT, PROFILE_UUID_LEFT, True, ts
                ))
                raw_skeleton_messages.append([("i", 2)] + _hand_to_raw_skeleton_record(
                    hands["left"], DEVICE_ID_LEFT, True, ts
                ))
            if "right" in hands:
                skeleton_messages.append([("i", 2)] + _hand_to_skeleton_record(
                    hands["right"], DEVICE_ID_RIGHT, PROFILE_UUID_RIGHT, False, ts
                ))
                raw_skeleton_messages.append([("i", 2)] + _hand_to_raw_skeleton_record(
                    hands["right"], DEVICE_ID_RIGHT, False, ts
                ))

            # Synthetic Ergonomics: simple 4-second open/close cycle (0..80 deg), shared by
            # both hands and all flex fields — see _hand_to_ergonomics_record() for why this
            # is synthesized rather than derived from the skeleton.
            flex_deg = 40.0 + 40.0 * math.sin(2.0 * math.pi * (frame["elapsed_ms"] / 1000.0) / 4.0)
            ergonomics_args: list = [("i", 2)]  # version = 2
            if "left" in hands:
                ergonomics_args += _hand_to_ergonomics_record(
                    DEVICE_ID_LEFT, True, ts, flex_deg
                )
            if "right" in hands:
                ergonomics_args += _hand_to_ergonomics_record(
                    DEVICE_ID_RIGHT, False, ts, flex_deg
                )

            # Device info: 2 records for left and right gloves.
            device_args: list = [
                ("i", 2),
                ("s", DEVICE_ID_LEFT), ("s", ""), ("i", 100), ("i", 0), ("i", 1),
                ("i", 3), ("i", 4), ("i", 1), ("s", "ContactGlove3 Left"), ("i", 0),
                ("s", DEVICE_ID_RIGHT), ("s", ""), ("i", 100), ("i", 0), ("i", 0),
                ("i", 3), ("i", 6), ("i", 1), ("s", "ContactGlove3 Right"), ("i", 0),
            ]

            with self._lock:
                clients = list(self._clients.keys())

            for ip, port in clients:
                for skeleton_args in skeleton_messages:
                    _send_osc(ip, port, "/DS2/HC/HandSkeleton", skeleton_args)
                for raw_skeleton_args in raw_skeleton_messages:
                    _send_osc(ip, port, "/DS2/HC/HandSkeletonRaw", raw_skeleton_args)
                _send_osc(ip, port, "/DS2/HC/Ergonomics", ergonomics_args)
                _send_osc(ip, port, "/DS2/HC/Device", device_args)

            frame_idx = (frame_idx + 1) % len(frames)
            time.sleep(frame_interval_s)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def start(self) -> None:
        disp = dispatcher.Dispatcher()
        disp.map("/DS2/HC/Connect", self._on_connect)
        disp.map("/DS2/HC/Disconnect", self._on_disconnect)
        disp.map("/DS2/HC/HandSkeleton/Profile/Get", self._on_get_retarget_profile)

        server = ThreadingOSCUDPServer((DS_HOST, DS_PORT), disp)
        frame_count = len(self._data["frames"])
        duration_s = self._data["loop_duration_ms"] / 1000.0
        print(f"[server] Mock DivingStation server starting on {DS_HOST}:{DS_PORT} (UDP)")
        print(f"[server] Generated {frame_count} synthetic frames  ({duration_s:.1f} s, looping)")
        print("[server] Press Ctrl+C to stop.\n")

        self._running = True
        threading.Thread(target=self._stream_frames, daemon=True).start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[server] Stopping.")
        finally:
            self._running = False
            server.server_close()


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Local mock DivingStation with synthetic hand motion."
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    _parse_args()
    MockDivingStationServer().start()
