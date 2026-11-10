# Raw positions and rotations for the five sensors, ordered thumb, index, middle, ring, and little.
# SDK: RawSensorTransformsData (from the /DS2/HC/RawSensorTransforms OSC address).
#
# Unlike Skeleton.msg, which has passed through retarget IK, this message stores each sensor's
# raw value. It is pre-retarget raw-sensor data; it has no concepts corresponding to profile_uuid
# or tracking_state.
#
# The coordinate system is the same right-handed model-rooted space as Skeleton.msg, in meters.
# Each Transform translation is the sensor-center position relative to the wrist. It is an absolute
# position in model-rooted space, not a value relative to the preceding sensor.
# rotation is a quaternion (x, y, z, w; the geometry_msgs/Quaternion convention) that describes the
# orientation from the sensor's local coordinate system to model-rooted space. Like translation, it is
# absolute in model-rooted space, unlike Skeleton.msg rotation, which is local relative to its parent
# joint. See the opening comments of Skeleton.msg and the API coordinate-system reference:
# https://docs.melt-interface-technologies.com/en/docs/contact/sdks/contact-glove-v2-ros2/api#message-coordinate-systems
std_msgs/Header header  # stamp: time at which the SDK callback was received (ROS time). frame_id: wrist frame of the target glove, "ds2/<namespace>/<glove_id>/wrist"
string id                # Glove ID
bool is_left              # Whether this is a left glove (true: left, false: right)
int64 generated_at_ms     # Unix timestamp at which the SDK / DivingStation Protocol v2 generated this frame [ms]
geometry_msgs/Transform thumb   # Thumb-sensor position and rotation
geometry_msgs/Transform index   # Index-finger sensor position and rotation
geometry_msgs/Transform middle  # Middle-finger sensor position and rotation
geometry_msgs/Transform ring    # Ring-finger sensor position and rotation
geometry_msgs/Transform little  # Little-finger sensor position and rotation
