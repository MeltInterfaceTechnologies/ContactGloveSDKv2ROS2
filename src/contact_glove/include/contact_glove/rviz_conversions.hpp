// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#ifndef CONTACT_GLOVE__RVIZ_CONVERSIONS_HPP_
#define CONTACT_GLOVE__RVIZ_CONVERSIONS_HPP_

#include <utility>
#include <vector>

#include "builtin_interfaces/msg/duration.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "geometry_msgs/msg/transform.hpp"
#include "contact_glove_msgs/msg/skeleton.hpp"

namespace contact_glove
{

// Skeleton parent/child tree, expressed as (child, parent) index pairs using the
// contact_glove_msgs::msg::Skeleton::NODE_* constants (see Skeleton.msg for the
// authoritative node index / parent-child table). Each finger's CMC joint attaches
// to the wrist; the remaining joints form a straight chain within the finger.
extern const std::vector<std::pair<int, int>> kBonePairs;

geometry_msgs::msg::Point to_point(const geometry_msgs::msg::Transform & tf);

// Returns all 25 joint positions in skeleton node order
// (contact_glove_msgs::msg::Skeleton::NODE_*).
std::vector<geometry_msgs::msg::Point> extract_positions(
  const contact_glove_msgs::msg::Skeleton & s);

builtin_interfaces::msg::Duration to_duration(double seconds);

}  // namespace contact_glove

#endif  // CONTACT_GLOVE__RVIZ_CONVERSIONS_HPP_
