// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#include "contact_glove/rviz_conversions.hpp"

namespace contact_glove
{

using Skel = contact_glove_msgs::msg::Skeleton;

const std::vector<std::pair<int, int>> kBonePairs = {
  {Skel::NODE_THUMB_CMC, Skel::NODE_WRIST},
  {Skel::NODE_THUMB_MCP, Skel::NODE_THUMB_CMC},
  {Skel::NODE_THUMB_IP, Skel::NODE_THUMB_MCP},
  {Skel::NODE_THUMB_TIP, Skel::NODE_THUMB_IP},
  {Skel::NODE_INDEX_CMC, Skel::NODE_WRIST},
  {Skel::NODE_INDEX_MCP, Skel::NODE_INDEX_CMC},
  {Skel::NODE_INDEX_PIP, Skel::NODE_INDEX_MCP},
  {Skel::NODE_INDEX_DIP, Skel::NODE_INDEX_PIP},
  {Skel::NODE_INDEX_TIP, Skel::NODE_INDEX_DIP},
  {Skel::NODE_MIDDLE_CMC, Skel::NODE_WRIST},
  {Skel::NODE_MIDDLE_MCP, Skel::NODE_MIDDLE_CMC},
  {Skel::NODE_MIDDLE_PIP, Skel::NODE_MIDDLE_MCP},
  {Skel::NODE_MIDDLE_DIP, Skel::NODE_MIDDLE_PIP},
  {Skel::NODE_MIDDLE_TIP, Skel::NODE_MIDDLE_DIP},
  {Skel::NODE_RING_CMC, Skel::NODE_WRIST},
  {Skel::NODE_RING_MCP, Skel::NODE_RING_CMC},
  {Skel::NODE_RING_PIP, Skel::NODE_RING_MCP},
  {Skel::NODE_RING_DIP, Skel::NODE_RING_PIP},
  {Skel::NODE_RING_TIP, Skel::NODE_RING_DIP},
  {Skel::NODE_LITTLE_CMC, Skel::NODE_WRIST},
  {Skel::NODE_LITTLE_MCP, Skel::NODE_LITTLE_CMC},
  {Skel::NODE_LITTLE_PIP, Skel::NODE_LITTLE_MCP},
  {Skel::NODE_LITTLE_DIP, Skel::NODE_LITTLE_PIP},
  {Skel::NODE_LITTLE_TIP, Skel::NODE_LITTLE_DIP},
};

geometry_msgs::msg::Point to_point(const geometry_msgs::msg::Transform & tf)
{
  geometry_msgs::msg::Point p;
  p.x = tf.translation.x;
  p.y = tf.translation.y;
  p.z = tf.translation.z;
  return p;
}

std::vector<geometry_msgs::msg::Point> extract_positions(
  const contact_glove_msgs::msg::Skeleton & s)
{
  std::vector<geometry_msgs::msg::Point> positions;
  positions.reserve(s.joints.size());
  for (const auto & joint : s.joints) {
    positions.push_back(to_point(joint));
  }
  return positions;
}

builtin_interfaces::msg::Duration to_duration(double seconds)
{
  builtin_interfaces::msg::Duration d;
  d.sec = static_cast<int32_t>(seconds);
  d.nanosec = static_cast<uint32_t>((seconds - static_cast<double>(d.sec)) * 1e9);
  return d;
}

}  // namespace contact_glove
