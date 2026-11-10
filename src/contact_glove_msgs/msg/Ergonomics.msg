# Finger opening and bending angles from the source skeleton before retargeting (SDK: ErgonomicsData).
# All values are in degrees [deg]. tracking_state reports the source-skeleton IK result.
# NOT_ATTEMPTED means the required IK was not performed. It includes earlier failures or missing
# input and intentional skips when pose calculation is unnecessary, such as update-interval control
# reusing an existing pose. It does not itself indicate an IK failure.
# IK_FAILED and NOT_ATTEMPTED values are for display and diagnostics only; do not use them for
# control, velocity estimation or interpolation. Only TRACKED values are valid for those uses.
std_msgs/Header header  # stamp: time at which the SDK callback was received (ROS time). frame_id: wrist frame of the target glove, "ds2/<namespace>/<glove_id>/wrist"
string id                # Glove ID
bool is_left              # Whether this is a left glove (true: left, false: right)
int64 generated_at_ms     # Unix timestamp at which the SDK / DivingStation Protocol v2 generated this frame [ms]
uint8 tracking_state      # Tracking state of IK-derived data. See the TRACKING_STATE_* constants below.
ThumbPose thumb           # Thumb joint angles [deg]
FingerPose index          # Index-finger joint angles [deg]
FingerPose middle         # Middle-finger joint angles [deg]
FingerPose ring           # Ring-finger joint angles [deg]
FingerPose little         # Little-finger joint angles [deg]

uint8 TRACKING_STATE_TRACKED=0        # Tracking the IK result
uint8 TRACKING_STATE_IK_FAILED=1      # IK failed
uint8 TRACKING_STATE_NOT_ATTEMPTED=2  # IK was not attempted
