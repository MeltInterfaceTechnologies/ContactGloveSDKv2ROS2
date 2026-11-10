# Hand skeleton positions and rotations for 25 joints (SDK: SkeletonData).
#
# --- Coordinate-system and rotation conventions ---
# The coordinate system is the same right-handed model-rooted space as the SDK, in meters.
# joints[i].translation is the position relative to the wrist (NODE_WRIST, index 0). It is an absolute
# position in model-rooted space (world-like), not a value relative to the preceding joint.
#
# joints[i].rotation is a normalized quaternion representing rotation (x, y, z, w; the standard
# geometry_msgs/Quaternion ordering). Unlike translation, it is a local rotation relative to the parent
# joint, not an absolute orientation in model-rooted space. This differs from RawSensorTransforms.msg
# rotation. The parent-child relationships are described by the NODE_* constants below. The wire format
# sends local rotations for 19 joints, including every CMC joint. The SDK fills NODE_WRIST and the five
# *_TIP rotations with identity quaternions; those six values are not measured rotations.
#
# Axis directions:
#   +X: fingertip to wrist
#   +Y: palm to back of hand
#   +Z: little-finger side to thumb side on the right hand; thumb side to little-finger side on the left hand
#   (reversing +Z between hands makes each hand's local coordinate system right-handed: +X x +Y = +Z)
#
# This message contains values after retargeting, where DivingStation Core reconstructs joint positions
# and angles with IK. The SDK decodes those values; it does not run IK. Use RawSensorTransforms.msg for
# raw sensor values. Frames whose
# tracking_state is IK_FAILED failed retargeting IK, so their joint values may be unreliable.
# NOT_ATTEMPTED means the required IK was not performed. It includes earlier failures or missing
# input and intentional skips when pose calculation is unnecessary, such as update-interval control
# reusing an existing pose. It does not itself indicate an IK failure.
# IK_FAILED and NOT_ATTEMPTED values are for display and diagnostics only; do not use them for
# control, velocity estimation or interpolation. Only TRACKED values are valid for those uses.
std_msgs/Header header  # stamp: time at which the SDK callback was received (ROS time). frame_id: wrist frame of the target glove, "ds2/<namespace>/<glove_id>/wrist"
string id                # Glove ID
string profile_uuid      # Stable UUID of the retarget profile
bool is_left              # Whether this is a left glove (true: left, false: right)
int64 generated_at_ms     # Unix timestamp at which the SDK / DivingStation Protocol v2 generated this frame [ms]
uint8 tracking_state      # Tracking state of retarget IK. See the TRACKING_STATE_* constants below.

uint8 TRACKING_STATE_TRACKED=0        # Tracking the IK result
uint8 TRACKING_STATE_IK_FAILED=1      # IK failed
uint8 TRACKING_STATE_NOT_ATTEMPTED=2  # IK was not attempted

# --- 25-joint index constants (same order and values as SDK SkeletonDataType) ---
#
# Use these as indices into the joints array. Their order and values match
# ContactGloveSDKv2::SkeletonDataType in the SDK.
#
# Parent-child relationships (the skeleton tree, used for bone rendering and IK):
#   NODE_WRIST is the root node (no parent). Each finger's CMC joint has NODE_WRIST as its parent.
#   Every other joint's parent is the preceding joint, forming a chain for each finger.
#     NODE_THUMB_CMC  <- NODE_WRIST
#     NODE_THUMB_MCP  <- NODE_THUMB_CMC
#     NODE_THUMB_IP   <- NODE_THUMB_MCP
#     NODE_THUMB_TIP  <- NODE_THUMB_IP
#     NODE_INDEX_CMC  <- NODE_WRIST
#     NODE_INDEX_MCP  <- NODE_INDEX_CMC
#     NODE_INDEX_PIP  <- NODE_INDEX_MCP
#     NODE_INDEX_DIP  <- NODE_INDEX_PIP
#     NODE_INDEX_TIP  <- NODE_INDEX_DIP
#     (middle, ring, and little follow the same pattern: CMC <- WRIST, then a serial chain)
uint8 NODE_WRIST=0
uint8 NODE_THUMB_CMC=1
uint8 NODE_THUMB_MCP=2
uint8 NODE_THUMB_IP=3
uint8 NODE_THUMB_TIP=4
uint8 NODE_INDEX_CMC=5
uint8 NODE_INDEX_MCP=6
uint8 NODE_INDEX_PIP=7
uint8 NODE_INDEX_DIP=8
uint8 NODE_INDEX_TIP=9
uint8 NODE_MIDDLE_CMC=10
uint8 NODE_MIDDLE_MCP=11
uint8 NODE_MIDDLE_PIP=12
uint8 NODE_MIDDLE_DIP=13
uint8 NODE_MIDDLE_TIP=14
uint8 NODE_RING_CMC=15
uint8 NODE_RING_MCP=16
uint8 NODE_RING_PIP=17
uint8 NODE_RING_DIP=18
uint8 NODE_RING_TIP=19
uint8 NODE_LITTLE_CMC=20
uint8 NODE_LITTLE_MCP=21
uint8 NODE_LITTLE_PIP=22
uint8 NODE_LITTLE_DIP=23
uint8 NODE_LITTLE_TIP=24

# Position and rotation for every joint. Use NODE_* values as indices.
# See the opening comments in this file for coordinate-system and rotation conventions.
geometry_msgs/Transform[25] joints
