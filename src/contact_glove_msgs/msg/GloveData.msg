# Device information for one glove (SDK: GloveData).
# This message has no generated_at_ms field because the protocol does not provide a frame-generation time; use header.stamp instead.
std_msgs/Header header  # stamp: time at which the SDK callback was received (ROS time). frame_id: wrist frame of the target glove, "ds2/<namespace>/<glove_id>/wrist"
string id                     # Glove ID (for example, "CG3-LEFT-001")
string pair_id                 # ID of the paired glove; an empty string when no glove is paired
int32 battery_percentage       # Battery percentage [%]. Range: 0-100; -1 when unknown
bool is_haptics                # Whether the glove has haptics capability
bool is_left                   # Whether this is a left glove (true: left, false: right)
int32 family_type              # Device family. See the FAMILY_TYPE_* constants below.
int32 color                    # Device display-color setting. See the COLOR_* constants below.
int32 connected_state          # Connection state. See the CONNECTED_STATE_* constants below.
string name                    # Device name
bool is_external_power_present # Whether external power is detected

int32 FAMILY_TYPE_CONTACT_GLOVE=0
int32 FAMILY_TYPE_CONTACT_SHEET=1
int32 FAMILY_TYPE_CONTACT_GLOVE2=2
int32 FAMILY_TYPE_CONTACT_GLOVE3=3
int32 COLOR_MAGENTA=0
int32 COLOR_RED=1
int32 COLOR_ORANGE=2
int32 COLOR_YELLOW=3
int32 COLOR_GREEN=4
int32 COLOR_CYAN=5
int32 COLOR_BLUE=6
int32 COLOR_ACHROMATIC=7
int32 CONNECTED_STATE_UNKNOWN=0
int32 CONNECTED_STATE_CONNECTED=1
int32 CONNECTED_STATE_UNCONNECTED=2
int32 CONNECTED_STATE_PAIRING=3
