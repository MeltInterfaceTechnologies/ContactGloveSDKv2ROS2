# Controller input state (SDK: ControllerData).
# This message has no generated_at_ms field because the protocol does not provide a frame-generation time; use header.stamp instead.
std_msgs/Header header  # stamp: time at which the SDK callback was received (ROS time). frame_id: wrist frame of the target glove, "ds2/<namespace>/<glove_id>/wrist"
string id                     # Glove ID
bool is_left                   # Whether this is a left glove (true: left, false: right)
int32 a                       # A button state. See the BUTTON_STATE_* constants below.
int32 b                       # B button state. See the BUTTON_STATE_* constants below.
int32 sys                     # System button state. See the BUTTON_STATE_* constants below.
int32 trigger_button          # Trigger button state. See the BUTTON_STATE_* constants below.
int32 joystick_button         # Joystick button state. See the BUTTON_STATE_* constants below.
int32 trackpad_button         # Trackpad-touch button state. See the BUTTON_STATE_* constants below.
float32 trigger                # Trigger travel. Range: 0.0-1.0
float32 grip_value             # Grip closure. Range: 0.0-1.0
float32 grip_force             # Grip force. Range: 0.0-1.0
float32 joystick_x             # Joystick X-axis value. Range: -1.0-1.0
float32 joystick_y             # Joystick Y-axis value. Range: -1.0-1.0
float32 trackpad_x             # Trackpad X-axis value. Range: -1.0-1.0
float32 trackpad_y             # Trackpad Y-axis value. Range: -1.0-1.0

int32 BUTTON_STATE_IDLE=0
int32 BUTTON_STATE_TOUCHED=1
int32 BUTTON_STATE_PRESSED=2
