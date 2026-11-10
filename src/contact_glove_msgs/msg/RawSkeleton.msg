# Source skeleton before applying a retarget profile (SDK: RawSkeletonData).
#
# Positions use a right-handed model-rooted space, in meters, with the source-skeleton wrist at the
# origin. This differs from the retarget-profile coordinate system in Skeleton.msg, so header.frame_id
# is "ds2/<namespace>/<glove_id>/source_wrist". This SDK does not publish a TF for source_wrist; users
# who need one must supply a TF for the source skeleton separately.
#
# joints[i].translation is an absolute position relative to source_wrist. rotation is a local quaternion
# relative to the parent joint (x, y, z, w in the geometry_msgs/Quaternion convention). The wire format
# sends rotations for only 19 joints; the SDK fills NODE_WRIST and each finger's *_TIP rotation with an
# identity quaternion. Those six identity quaternions are not measured values.
#
# RawSkeleton contains the calibrated-EMF source skeleton after IK / forward kinematics. It is not the
# raw sensor Transform data in RawSensorTransforms.msg. Retarget-profile bind points, bind rotations,
# rest alignment, and model-space transforms are not applied.
# NOT_ATTEMPTED means the required IK was not performed. It includes earlier failures or missing
# input and intentional skips when pose calculation is unnecessary, such as update-interval control
# reusing an existing pose. It does not itself indicate an IK failure.
# IK_FAILED and NOT_ATTEMPTED values are for display and diagnostics only; do not use them for
# control, velocity estimation or interpolation. Only TRACKED values are valid for those uses.
std_msgs/Header header  # stamp: time at which the SDK callback was received. frame_id: "ds2/<namespace>/<glove_id>/source_wrist"
string id
bool is_left
int64 generated_at_ms
uint8 tracking_state

uint8 TRACKING_STATE_TRACKED=0
uint8 TRACKING_STATE_IK_FAILED=1
uint8 TRACKING_STATE_NOT_ATTEMPTED=2

# The same fixed 25-joint topology and indices as Skeleton.msg.
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

geometry_msgs/Transform[25] joints
