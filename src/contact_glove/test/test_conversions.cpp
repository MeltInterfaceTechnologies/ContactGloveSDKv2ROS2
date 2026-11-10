// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#include <array>
#include <cmath>
#include <set>
#include <stdexcept>
#include <string>

#include "gtest/gtest.h"

#include "contact_glove/conversions.hpp"
#include "contact_glove_msgs/msg/skeleton.hpp"

TEST(ToTransform, CopiesPositionAndRotation)
{
  ContactGloveSDKv2::Transform tf;
  tf.position = {1.0f, 2.0f, 3.0f};
  tf.rotation = {0.5f, 0.1f, 0.2f, 0.3f};  // w, x, y, z

  const auto msg = contact_glove::to_transform(tf);

  EXPECT_FLOAT_EQ(msg.translation.x, 1.0f);
  EXPECT_FLOAT_EQ(msg.translation.y, 2.0f);
  EXPECT_FLOAT_EQ(msg.translation.z, 3.0f);
  EXPECT_FLOAT_EQ(msg.rotation.w, 0.5f);
  EXPECT_FLOAT_EQ(msg.rotation.x, 0.1f);
  EXPECT_FLOAT_EQ(msg.rotation.y, 0.2f);
  EXPECT_FLOAT_EQ(msg.rotation.z, 0.3f);
}

TEST(WristFrameId, UsesDefaultNamespaceWhenEmpty)
{
  EXPECT_EQ(
    contact_glove::wrist_frame_id("", "CG3-LEFT-001"),
    "ds2/contact_glove/CG3-LEFT-001/wrist");
  EXPECT_EQ(
    contact_glove::wrist_frame_id("/", "CG3-LEFT-001"),
    "ds2/contact_glove/CG3-LEFT-001/wrist");
}

TEST(WristFrameId, StripsLeadingAndTrailingSlashes)
{
  EXPECT_EQ(contact_glove::wrist_frame_id("/my_ns/", "glove-1"), "ds2/my_ns/glove-1/wrist");
  EXPECT_EQ(contact_glove::wrist_frame_id("my_ns", "glove-1"), "ds2/my_ns/glove-1/wrist");
}

TEST(SourceWristFrameId, KeepsSourceSkeletonSeparateFromRetargetedSkeleton)
{
  EXPECT_EQ(
    contact_glove::source_wrist_frame_id("/my_ns/", "glove-1"),
    "ds2/my_ns/glove-1/source_wrist");
  EXPECT_NE(
    contact_glove::source_wrist_frame_id("my_ns", "glove-1"),
    contact_glove::wrist_frame_id("my_ns", "glove-1"));
}

TEST(AssignErgonomicsPose, MapsIndicesToNamedJoints)
{
  std::array<float, ContactGloveSDKv2::ERGONOMICS_DATA_COUNT> d{};
  for (size_t i = 0; i < d.size(); ++i) {
    d[i] = static_cast<float>(i);
  }

  contact_glove_msgs::msg::Ergonomics msg;
  contact_glove::assign_ergonomics_pose(d, msg);

  EXPECT_FLOAT_EQ(msg.thumb.cmc, 0.0f);
  EXPECT_FLOAT_EQ(msg.thumb.mcp, 1.0f);
  EXPECT_FLOAT_EQ(msg.thumb.ip, 2.0f);
  EXPECT_FLOAT_EQ(msg.thumb.tilt, 3.0f);

  EXPECT_FLOAT_EQ(msg.index.mcp, 4.0f);
  EXPECT_FLOAT_EQ(msg.index.pip, 5.0f);
  EXPECT_FLOAT_EQ(msg.index.dip, 6.0f);
  EXPECT_FLOAT_EQ(msg.index.tilt, 7.0f);

  EXPECT_FLOAT_EQ(msg.middle.mcp, 8.0f);
  EXPECT_FLOAT_EQ(msg.middle.pip, 9.0f);
  EXPECT_FLOAT_EQ(msg.middle.dip, 10.0f);
  EXPECT_FLOAT_EQ(msg.middle.tilt, 11.0f);

  EXPECT_FLOAT_EQ(msg.ring.mcp, 12.0f);
  EXPECT_FLOAT_EQ(msg.ring.pip, 13.0f);
  EXPECT_FLOAT_EQ(msg.ring.dip, 14.0f);
  EXPECT_FLOAT_EQ(msg.ring.tilt, 15.0f);

  EXPECT_FLOAT_EQ(msg.little.mcp, 16.0f);
  EXPECT_FLOAT_EQ(msg.little.pip, 17.0f);
  EXPECT_FLOAT_EQ(msg.little.dip, 18.0f);
  EXPECT_FLOAT_EQ(msg.little.tilt, 19.0f);
}

TEST(JointFrameId, MatchesIssueExamples)
{
  EXPECT_EQ(
    contact_glove::joint_frame_id(
      "my_ns", "glove-1", contact_glove_msgs::msg::Skeleton::NODE_THUMB_CMC),
    "ds2/my_ns/glove-1/thumb/cmc");
  EXPECT_EQ(
    contact_glove::joint_frame_id(
      "my_ns", "glove-1", contact_glove_msgs::msg::Skeleton::NODE_INDEX_PIP),
    "ds2/my_ns/glove-1/index/pip");
  EXPECT_EQ(
    contact_glove::joint_frame_id(
      "my_ns", "glove-1", contact_glove_msgs::msg::Skeleton::NODE_LITTLE_TIP),
    "ds2/my_ns/glove-1/little/tip");
}

TEST(JointFrameId, UsesDefaultNamespaceWhenEmpty)
{
  EXPECT_EQ(
    contact_glove::joint_frame_id(
      "", "CG3-LEFT-001", contact_glove_msgs::msg::Skeleton::NODE_THUMB_CMC),
    "ds2/contact_glove/CG3-LEFT-001/thumb/cmc");
}

TEST(JointFrameId, CoversAllNonWristNodesUniquely)
{
  using Skel = contact_glove_msgs::msg::Skeleton;
  std::set<std::string> frames;
  for (int node = Skel::NODE_WRIST + 1; node <= Skel::NODE_LITTLE_TIP; ++node) {
    const auto frame = contact_glove::joint_frame_id(
      "ns", "glove", static_cast<uint8_t>(node));
    EXPECT_TRUE(frames.insert(frame).second) << "duplicate frame name: " << frame;
    EXPECT_NE(frame.find("ns/glove/"), std::string::npos);
  }
  EXPECT_EQ(frames.size(), static_cast<size_t>(Skel::NODE_LITTLE_TIP));
}

TEST(JointFrameId, ThrowsForNodeWristAndOutOfRangeIndices)
{
  using Skel = contact_glove_msgs::msg::Skeleton;
  EXPECT_THROW(
    contact_glove::joint_frame_id("ns", "glove", Skel::NODE_WRIST), std::invalid_argument);
  EXPECT_THROW(
    contact_glove::joint_frame_id("ns", "glove", Skel::NODE_LITTLE_TIP + 1),
    std::invalid_argument);
  EXPECT_THROW(
    contact_glove::joint_frame_id("ns", "glove", 255), std::invalid_argument);
}

TEST(SkeletonWristRelativeRotations, ComposesParentBeforeLocalAndKeepsFingerChainsSeparate)
{
  using Skel = contact_glove_msgs::msg::Skeleton;
  Skel skeleton;
  for (auto & joint : skeleton.joints) {
    joint.rotation.w = 1.0;
  }

  const double sin_cos_45 = std::sqrt(0.5);
  // index CMC: +90 deg around Z. index MCP: +90 deg around local X.
  skeleton.joints[Skel::NODE_INDEX_CMC].rotation.w = sin_cos_45;
  skeleton.joints[Skel::NODE_INDEX_CMC].rotation.z = sin_cos_45;
  skeleton.joints[Skel::NODE_INDEX_MCP].rotation.w = sin_cos_45;
  skeleton.joints[Skel::NODE_INDEX_MCP].rotation.x = sin_cos_45;

  // A different finger must start again from wrist, not from the preceding array element.
  skeleton.joints[Skel::NODE_MIDDLE_CMC].rotation.w = sin_cos_45;
  skeleton.joints[Skel::NODE_MIDDLE_CMC].rotation.y = sin_cos_45;

  const auto rotations = contact_glove::skeleton_wrist_relative_rotations(skeleton);

  EXPECT_DOUBLE_EQ(rotations[Skel::NODE_WRIST].w, 1.0);
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_CMC].w, sin_cos_45, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_CMC].z, sin_cos_45, 1e-12);

  // parent Z90 * local X90 = (w, x, y, z) = (0.5, 0.5, 0.5, 0.5).
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_MCP].w, 0.5, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_MCP].x, 0.5, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_MCP].y, 0.5, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_MCP].z, 0.5, 1e-12);

  // PIP/DIP/TIP are identity local rotations here, so the tip inherits MCP's absolute rotation.
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_TIP].w, 0.5, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_TIP].x, 0.5, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_TIP].y, 0.5, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_INDEX_TIP].z, 0.5, 1e-12);

  EXPECT_NEAR(rotations[Skel::NODE_MIDDLE_CMC].w, sin_cos_45, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_MIDDLE_CMC].x, 0.0, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_MIDDLE_CMC].y, sin_cos_45, 1e-12);
  EXPECT_NEAR(rotations[Skel::NODE_MIDDLE_CMC].z, 0.0, 1e-12);
}

TEST(ToJointState, ConvertsDegreesToRadiansInErgonomicsFieldOrder)
{
  contact_glove_msgs::msg::Ergonomics e;
  e.is_left = false;
  e.thumb.cmc = 10.0f;  e.thumb.mcp = 20.0f;  e.thumb.ip = 30.0f;  e.thumb.tilt = 40.0f;
  e.index.mcp = 50.0f;  e.index.pip = 60.0f;  e.index.dip = 70.0f;  e.index.tilt = 80.0f;
  e.middle.mcp = 90.0f; e.middle.pip = 100.0f; e.middle.dip = 110.0f; e.middle.tilt = 120.0f;
  e.ring.mcp = 130.0f; e.ring.pip = 140.0f; e.ring.dip = 150.0f; e.ring.tilt = 160.0f;
  e.little.mcp = 170.0f; e.little.pip = 180.0f; e.little.dip = -10.0f; e.little.tilt = 5.0f;

  const auto js = contact_glove::to_joint_state(e);

  ASSERT_EQ(js.name.size(), contact_glove::kJointStateCount);
  ASSERT_EQ(js.position.size(), contact_glove::kJointStateCount);

  EXPECT_EQ(js.name[0], "right_thumb_cmc_joint");
  EXPECT_NEAR(js.position[0], 10.0 * M_PI / 180.0, 1e-9);
  EXPECT_EQ(js.name[3], "right_thumb_tilt_joint");
  EXPECT_NEAR(js.position[3], 40.0 * M_PI / 180.0, 1e-9);
  EXPECT_EQ(js.name[4], "right_index_mcp_joint");
  EXPECT_NEAR(js.position[4], 50.0 * M_PI / 180.0, 1e-9);
  EXPECT_EQ(js.name[19], "right_little_tilt_joint");
  EXPECT_NEAR(js.position[19], 5.0 * M_PI / 180.0, 1e-9);
  // Negative degrees must convert to negative radians (no sign flip / clamping).
  EXPECT_EQ(js.name[18], "right_little_dip_joint");
  EXPECT_NEAR(js.position[18], -10.0 * M_PI / 180.0, 1e-9);
}

TEST(ToJointState, PrefixesNamesWithSideFromIsLeft)
{
  contact_glove_msgs::msg::Ergonomics left_e;
  left_e.is_left = true;
  const auto left_js = contact_glove::to_joint_state(left_e);
  for (const auto & name : left_js.name) {
    EXPECT_EQ(name.rfind("left_", 0), 0u) << name;
  }

  contact_glove_msgs::msg::Ergonomics right_e;
  right_e.is_left = false;
  const auto right_js = contact_glove::to_joint_state(right_e);
  for (const auto & name : right_js.name) {
    EXPECT_EQ(name.rfind("right_", 0), 0u) << name;
  }
}

TEST(ToJointState, CarriesHeaderThrough)
{
  contact_glove_msgs::msg::Ergonomics e;
  e.header.frame_id = "ds2/contact_glove/glove-1/wrist";
  e.header.stamp.sec = 42;
  const auto js = contact_glove::to_joint_state(e);
  EXPECT_EQ(js.header.frame_id, "ds2/contact_glove/glove-1/wrist");
  EXPECT_EQ(js.header.stamp.sec, 42);
}

TEST(SelectJointStateGloveId, LatchesFirstIdWhenTargetIsEmpty)
{
  std::string target_id;
  EXPECT_TRUE(contact_glove::select_joint_state_glove_id(target_id, "glove-A"));
  EXPECT_EQ(target_id, "glove-A");
}

TEST(SelectJointStateGloveId, AcceptsSubsequentMessagesFromTheSameId)
{
  std::string target_id = "glove-A";
  EXPECT_TRUE(contact_glove::select_joint_state_glove_id(target_id, "glove-A"));
  EXPECT_EQ(target_id, "glove-A");
}

TEST(SelectJointStateGloveId, RejectsADifferentIdOnceLatched)
{
  std::string target_id = "glove-A";
  EXPECT_FALSE(contact_glove::select_joint_state_glove_id(target_id, "glove-B"));
  // The originally latched id must not be clobbered by the rejected message.
  EXPECT_EQ(target_id, "glove-A");
}

TEST(SelectJointStateGloveId, RelatchesAfterTargetIsResetToEmpty)
{
  std::string target_id = "glove-A";
  EXPECT_FALSE(contact_glove::select_joint_state_glove_id(target_id, "glove-B"));
  target_id.clear();  // simulates contact_glove_node's reconnect reset
  EXPECT_TRUE(contact_glove::select_joint_state_glove_id(target_id, "glove-B"));
  EXPECT_EQ(target_id, "glove-B");
}

// Regression test for the SensorDataQoS(best-effort) -> reliable QoS change: a
// best-effort publisher cannot satisfy a subscriber requesting the ROS2 default
// (reliable) QoS, so robot_state_publisher/MoveIt-style consumers that don't
// explicitly ask for best-effort would silently receive nothing.
TEST(JointStateQos, IsReliable)
{
  EXPECT_EQ(
    contact_glove::joint_state_qos().get_rmw_qos_profile().reliability,
    RMW_QOS_POLICY_RELIABILITY_RELIABLE);
}
