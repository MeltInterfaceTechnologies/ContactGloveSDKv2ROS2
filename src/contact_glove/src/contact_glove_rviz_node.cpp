// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#include <array>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "builtin_interfaces/msg/duration.hpp"
#include "builtin_interfaces/msg/time.hpp"
#include "visualization_msgs/msg/marker_array.hpp"
#include "geometry_msgs/msg/transform.hpp"
#include "geometry_msgs/msg/transform_stamped.hpp"
#include "tf2_ros/transform_broadcaster.h"
#include "contact_glove_msgs/msg/skeleton.hpp"

#include "contact_glove/conversions.hpp"
#include "contact_glove/rviz_conversions.hpp"

class ContactGloveRvizNode : public rclcpp::Node
{
public:
  ContactGloveRvizNode()
  : Node("contact_glove_rviz_node"),
    tf_broadcaster_(this)
  {
    parent_frame_id_ = declare_parameter<std::string>("parent_frame_id", "world");
    publish_placeholder_wrist_tf_ =
      declare_parameter<bool>("publish_placeholder_wrist_tf", true);
    publish_joint_tf_ = declare_parameter<bool>("publish_joint_tf", false);
    left_wrist_offset_ =
      declare_parameter<std::vector<double>>("left_wrist_offset", {0.0, -0.15, 0.0});
    right_wrist_offset_ =
      declare_parameter<std::vector<double>>("right_wrist_offset", {0.0, 0.15, 0.0});
    marker_lifetime_ = declare_parameter<double>("marker_lifetime", 0.4);

    if (left_wrist_offset_.size() != 3 || right_wrist_offset_.size() != 3) {
      RCLCPP_WARN(
        get_logger(),
        "left_wrist_offset / right_wrist_offset must each have 3 elements; "
        "falling back to defaults.");
      left_wrist_offset_ = {0.0, -0.15, 0.0};
      right_wrist_offset_ = {0.0, 0.15, 0.0};
    }

    // Separate the hands into topics so ROS 2 users can naturally subscribe to
    // or remap a single hand.
    left_marker_pub_ = create_publisher<visualization_msgs::msg::MarkerArray>(
      "left/skeleton_markers", 10);
    right_marker_pub_ = create_publisher<visualization_msgs::msg::MarkerArray>(
      "right/skeleton_markers", 10);

    // contact_glove_node publishes Skeleton with SensorDataQoS (best effort),
    // so this must use the same QoS. Reliable would be incompatible and no
    // subscription would be established.
    left_skeleton_sub_ = create_subscription<contact_glove_msgs::msg::Skeleton>(
      "left/skeleton", rclcpp::SensorDataQoS(),
      [this](const contact_glove_msgs::msg::Skeleton & msg) {
        skeleton_callback(msg, left_marker_pub_);
      });
    right_skeleton_sub_ = create_subscription<contact_glove_msgs::msg::Skeleton>(
      "right/skeleton", rclcpp::SensorDataQoS(),
      [this](const contact_glove_msgs::msg::Skeleton & msg) {
        skeleton_callback(msg, right_marker_pub_);
      });
  }

private:
  using Pt = geometry_msgs::msg::Point;
  using Mk = visualization_msgs::msg::Marker;

  void skeleton_callback(
    const contact_glove_msgs::msg::Skeleton & msg,
    const rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr & marker_pub)
  {
    const std::string wrist_frame = msg.header.frame_id.empty() ?
      "contact_glove_" + msg.id + "_wrist" :
      msg.header.frame_id;
    builtin_interfaces::msg::Time stamp;
    if (msg.header.stamp.sec != 0 || msg.header.stamp.nanosec != 0) {
      stamp = msg.header.stamp;
    } else {
      // Backward-compatible fallback for Skeleton messages recorded before Header was populated.
      stamp = now();
    }

    // Placeholder wrist pose.
    // SkeletonData is in model-rooted space (wrist = origin). DSProtocol v2 / this SDK
    // does NOT sense a real 6DoF wrist pose. When enabled, we broadcast a fixed
    // left/right offset so the two hands appear side-by-side in RViz without an
    // external wrist tracker. Set publish_placeholder_wrist_tf:=false to supply your
    // own  parent_frame_id -> <wrist_frame>  transform instead (e.g. from a Lighthouse
    // tracker), in which case the hands are placed at their real positions.
    if (publish_placeholder_wrist_tf_) {
      const auto & off = msg.is_left ? left_wrist_offset_ : right_wrist_offset_;
      geometry_msgs::msg::TransformStamped tf;
      tf.header.stamp = stamp;
      tf.header.frame_id = parent_frame_id_;
      tf.child_frame_id = wrist_frame;
      tf.transform.translation.x = off[0];
      tf.transform.translation.y = off[1];
      tf.transform.translation.z = off[2];
      tf.transform.rotation.w = 1.0;
      tf.transform.rotation.x = 0.0;
      tf.transform.rotation.y = 0.0;
      tf.transform.rotation.z = 0.0;
      tf_broadcaster_.sendTransform(tf);
    }

    // publish_joint_tf is a debugging mode that publishes the 24 non-wrist
    // joints as children of the wrist frame on /tf. The frame tree remains
    // flat, but joints[i].rotation is local relative to the preceding joint,
    // not absolute relative to the wrist (see Skeleton.msg). It must therefore
    // be composed from parent to child before it is used as child_frame_id
    // rotation. translation is already absolute relative to the wrist.
    if (publish_joint_tf_) {
      using Skel = contact_glove_msgs::msg::Skeleton;
      const auto absolute_rotation = contact_glove::skeleton_wrist_relative_rotations(msg);
      std::vector<geometry_msgs::msg::TransformStamped> joint_tfs;
      joint_tfs.reserve(msg.joints.size() - 1);
      for (uint8_t node = Skel::NODE_WRIST + 1; node <= Skel::NODE_LITTLE_TIP; ++node) {
        geometry_msgs::msg::TransformStamped tf;
        tf.header.stamp = stamp;
        tf.header.frame_id = wrist_frame;
        tf.child_frame_id = contact_glove::joint_frame_id(get_namespace(), msg.id, node);
        tf.transform.translation = msg.joints[node].translation;
        tf.transform.rotation = absolute_rotation[node];
        joint_tfs.push_back(tf);
      }
      tf_broadcaster_.sendTransform(joint_tfs);
    }

    const auto positions = contact_glove::extract_positions(msg);

    // Left hand: blue, right hand: red
    std_msgs::msg::ColorRGBA color;
    color.a = 1.0f;
    if (msg.is_left) {
      color.r = 0.0f; color.g = 0.4f; color.b = 1.0f;
    } else {
      color.r = 1.0f; color.g = 0.2f; color.b = 0.0f;
    }

    const auto lifetime = contact_glove::to_duration(marker_lifetime_);

    visualization_msgs::msg::MarkerArray array;

    // Joint spheres (SPHERE_LIST), published in the per-hand wrist frame.
    // Positions are wrist-rooted, so they map directly into this frame.
    Mk joints;
    joints.header.stamp = stamp;
    joints.header.frame_id = wrist_frame;
    joints.ns = msg.id + "/joints";
    joints.id = 0;
    joints.type = Mk::SPHERE_LIST;
    joints.action = Mk::ADD;
    joints.scale.x = joints.scale.y = joints.scale.z = 0.012;
    joints.color = color;
    joints.lifetime = lifetime;
    joints.points = positions;
    array.markers.push_back(joints);

    // Bones (LINE_LIST): each pair of indices becomes one line segment
    Mk bones;
    bones.header.stamp = stamp;
    bones.header.frame_id = wrist_frame;
    bones.ns = msg.id + "/bones";
    bones.id = 1;
    bones.type = Mk::LINE_LIST;
    bones.action = Mk::ADD;
    bones.scale.x = 0.005;
    bones.color = color;
    bones.lifetime = lifetime;
    for (const auto & [a, b] : contact_glove::kBonePairs) {
      bones.points.push_back(positions[a]);
      bones.points.push_back(positions[b]);
    }
    array.markers.push_back(bones);

    marker_pub->publish(array);
  }

  std::string parent_frame_id_;
  bool publish_placeholder_wrist_tf_ = true;
  bool publish_joint_tf_ = false;
  std::vector<double> left_wrist_offset_;
  std::vector<double> right_wrist_offset_;
  double marker_lifetime_ = 0.4;
  tf2_ros::TransformBroadcaster tf_broadcaster_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr left_marker_pub_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr right_marker_pub_;
  rclcpp::Subscription<contact_glove_msgs::msg::Skeleton>::SharedPtr left_skeleton_sub_;
  rclcpp::Subscription<contact_glove_msgs::msg::Skeleton>::SharedPtr right_skeleton_sub_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ContactGloveRvizNode>());
  rclcpp::shutdown();
  return 0;
}
