// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#include <set>

#include "gtest/gtest.h"

#include "contact_glove/rviz_conversions.hpp"

TEST(ToPoint, CopiesTranslationOnly)
{
  geometry_msgs::msg::Transform tf;
  tf.translation.x = 1.0;
  tf.translation.y = 2.0;
  tf.translation.z = 3.0;
  tf.rotation.w = 0.0;  // rotation must not leak into the point

  const auto p = contact_glove::to_point(tf);
  EXPECT_DOUBLE_EQ(p.x, 1.0);
  EXPECT_DOUBLE_EQ(p.y, 2.0);
  EXPECT_DOUBLE_EQ(p.z, 3.0);
}

TEST(ExtractPositions, PreservesJointOrder)
{
  contact_glove_msgs::msg::Skeleton s;
  for (size_t i = 0; i < s.joints.size(); ++i) {
    s.joints[i].translation.x = static_cast<double>(i);
  }

  const auto positions = contact_glove::extract_positions(s);
  ASSERT_EQ(positions.size(), s.joints.size());
  for (size_t i = 0; i < positions.size(); ++i) {
    EXPECT_DOUBLE_EQ(positions[i].x, static_cast<double>(i));
  }
}

TEST(ToDuration, SplitsSecondsAndNanoseconds)
{
  const auto d = contact_glove::to_duration(1.5);
  EXPECT_EQ(d.sec, 1);
  EXPECT_NEAR(d.nanosec, 500000000u, 1000u);
}

TEST(ToDuration, HandlesZero)
{
  const auto d = contact_glove::to_duration(0.0);
  EXPECT_EQ(d.sec, 0);
  EXPECT_EQ(d.nanosec, 0u);
}

TEST(BonePairs, CoverAllNonWristNodesExactlyOnce)
{
  using Skel = contact_glove_msgs::msg::Skeleton;

  std::set<int> children;
  for (const auto & pair : contact_glove::kBonePairs) {
    EXPECT_TRUE(children.insert(pair.first).second) << "duplicate child index: " << pair.first;
    EXPECT_NE(pair.first, pair.second);
  }

  // Every joint other than the wrist itself must appear as a child exactly once.
  for (int node = Skel::NODE_WRIST + 1; node <= Skel::NODE_LITTLE_TIP; ++node) {
    EXPECT_EQ(children.count(node), 1u) << "node " << node << " missing from bone pairs";
  }
  EXPECT_EQ(contact_glove::kBonePairs.size(), static_cast<size_t>(Skel::NODE_LITTLE_TIP));
}
