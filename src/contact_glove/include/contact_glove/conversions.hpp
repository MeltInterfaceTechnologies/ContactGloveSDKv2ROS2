// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#ifndef CONTACT_GLOVE__CONVERSIONS_HPP_
#define CONTACT_GLOVE__CONVERSIONS_HPP_

#include <array>
#include <cstdint>
#include <string>

#include "geometry_msgs/msg/transform.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "contact_glove_msgs/msg/ergonomics.hpp"
#include "contact_glove_msgs/msg/skeleton.hpp"
#include "rclcpp/qos.hpp"

#include "contactglove/ContactGloveSDKv2.hpp"

namespace contact_glove
{

// Number of fields for one hand in Ergonomics.msg: thumb 4 plus four fingers
// times 4. It matches the number of URDF revolute joints and JointState
// name/position elements.
constexpr std::size_t kJointStateCount = 20;

// Converts an SDK Transform (position plus quaternion) to geometry_msgs::msg::Transform.
geometry_msgs::msg::Transform to_transform(const ContactGloveSDKv2::Transform & tf);

// Builds the wrist frame name used by header.frame_id:
// "ds2/<ns>/<glove_id>/wrist". Leading and trailing '/' are removed from ns;
// an empty result defaults to "contact_glove".
std::string wrist_frame_id(std::string ns, const std::string & glove_id);

// Builds the source-skeleton wrist frame used by RawSkeleton.msg header.frame_id:
// "ds2/<ns>/<glove_id>/source_wrist". RawSkeleton uses a hand-model coordinate
// system distinct from post-retarget Skeleton, so it must not use wrist_frame_id().
std::string source_wrist_frame_id(std::string ns, const std::string & glove_id);

// Builds the 24 non-wrist child-frame names used by contact_glove_rviz_node
// publish_joint_tf (25-joint debug TF): "ds2/<ns>/<glove_id>/<finger>/<joint>".
// node_index must be a contact_glove_msgs::msg::Skeleton::NODE_* value other
// than NODE_WRIST (NODE_THUMB_CMC through NODE_LITTLE_TIP, 1 through 24).
// ns is normalized like wrist_frame_id(). Throws std::invalid_argument for
// values outside that range, including NODE_WRIST (0).
std::string joint_frame_id(std::string ns, const std::string & glove_id, uint8_t node_index);

// Composes Skeleton.joints[*].rotation (local rotation relative to the parent)
// in parent-to-child order with Hamilton products, producing absolute rotations
// relative to the wrist. publish_joint_tf publishes all 24 non-wrist frames as
// direct wrist children, so it uses these converted rotations.
std::array<geometry_msgs::msg::Quaternion, ContactGloveSDKv2::SKELETON_DATA_COUNT>
skeleton_wrist_relative_rotations(const contact_glove_msgs::msg::Skeleton & skeleton);

// Assigns SDK ErgonomicsData::data (ERGONOMICS_DATA_COUNT elements in
// ErgonomicsDataType order) to Ergonomics.msg thumb/index/middle/ring/little.
void assign_ergonomics_pose(
  const std::array<float, ContactGloveSDKv2::ERGONOMICS_DATA_COUNT> & d,
  contact_glove_msgs::msg::Ergonomics & msg);

// Converts Ergonomics.msg values in degrees to sensor_msgs::msg::JointState,
// matching joint names, order, and radians used by the left and right hand URDF.
// Joint names are "<left|right>_<finger>_<field>_joint" (for example,
// left_thumb_cmc_joint); is_left chooses the prefix. Conversion is degrees to
// radians only, without left/right sign inversion. The URDF joint axes and
// placement represent the visual mirror image.
sensor_msgs::msg::JointState to_joint_state(const contact_glove_msgs::msg::Ergonomics & e);

// left/joint_states and right/joint_states each drive one robot model with
// fixed joint names from urdf/{left,right}_hand.urdf.xacro. Even when multiple
// gloves are connected on one side, publish exactly one selected glove ID.
// Multiplexing several gloves into one JointState topic, as id-bearing Skeleton,
// Ergonomics, and MarkerArray messages do, would make robot_state_publisher
// alternate between indistinguishable glove values and produce a jittering view.
//
// target_id (in/out): currently selected glove ID for the side; empty means
// unselected and is set to msg_id by this call.
// msg_id: Ergonomics.id received for this message.
// Returns true when msg_id is the selected target and should be published.
// Returns false when another glove ID is already selected and this message must
// be ignored.
bool select_joint_state_glove_id(std::string & target_id, const std::string & msg_id);

// QoS for left/joint_states and right/joint_states publishers. Unlike streaming
// topics (ergonomics/skeleton/raw_sensor_transforms/controller), it is
// reliable/volatile. robot_state_publisher, MoveIt, and similar JointState
// consumers commonly request reliable QoS, which cannot connect to a
// best-effort publisher. A reliable publisher remains compatible with a
// best-effort consumer. This named function also makes the reliability policy
// testable.
rclcpp::QoS joint_state_qos();

}  // namespace contact_glove

#endif  // CONTACT_GLOVE__CONVERSIONS_HPP_
