// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#include <cmath>
#include <stdexcept>

#include "contact_glove/conversions.hpp"
#include "contact_glove_msgs/msg/skeleton.hpp"

// M_PI is a long-standing POSIX/glibc extension to <cmath>, not part of the C++ standard, so it
// is not guaranteed to be defined on every toolchain/standard-library configuration. Define it
// ourselves when missing instead of depending on the extension being present.
#ifndef M_PI
#   define M_PI 3.1415926535897932384626433832
#endif

namespace contact_glove
{

namespace
{

// Namespace normalization shared by wrist_frame_id() and joint_frame_id():
// remove leading/trailing '/' and default an empty result to "contact_glove".
std::string normalize_namespace(std::string ns)
{
  while (!ns.empty() && ns.front() == '/') {
    ns.erase(ns.begin());
  }
  while (!ns.empty() && ns.back() == '/') {
    ns.pop_back();
  }
  if (ns.empty()) {
    ns = "contact_glove";
  }
  return ns;
}

// "finger/joint" names for contact_glove_msgs::msg::Skeleton::NODE_* indices
// 1 through 24. Index 0 (NODE_WRIST) is not used by joint_frame_id(); use
// wrist_frame_id() for it.
constexpr std::array<const char *, 25> kJointFrameSuffixes = {
  "",  // NODE_WRIST (unused here)
  "thumb/cmc", "thumb/mcp", "thumb/ip", "thumb/tip",
  "index/cmc", "index/mcp", "index/pip", "index/dip", "index/tip",
  "middle/cmc", "middle/mcp", "middle/pip", "middle/dip", "middle/tip",
  "ring/cmc", "ring/mcp", "ring/pip", "ring/dip", "ring/tip",
  "little/cmc", "little/mcp", "little/pip", "little/dip", "little/tip",
};

// contact_glove::kJointStateCount "<finger>_<field>_joint" suffixes in the
// Ergonomics.msg field order, matching ErgonomicsDataType and
// assign_ergonomics_pose().
constexpr std::array<const char *, kJointStateCount> kJointStateSuffixes = {
  "thumb_cmc_joint", "thumb_mcp_joint", "thumb_ip_joint", "thumb_tilt_joint",
  "index_mcp_joint", "index_pip_joint", "index_dip_joint", "index_tilt_joint",
  "middle_mcp_joint", "middle_pip_joint", "middle_dip_joint", "middle_tilt_joint",
  "ring_mcp_joint", "ring_pip_joint", "ring_dip_joint", "ring_tilt_joint",
  "little_mcp_joint", "little_pip_joint", "little_dip_joint", "little_tilt_joint",
};

uint8_t skeleton_joint_parent(uint8_t node)
{
  using Skel = contact_glove_msgs::msg::Skeleton;
  switch (node) {
    case Skel::NODE_THUMB_CMC:
    case Skel::NODE_INDEX_CMC:
    case Skel::NODE_MIDDLE_CMC:
    case Skel::NODE_RING_CMC:
    case Skel::NODE_LITTLE_CMC:
      return Skel::NODE_WRIST;
    default:
      return node - 1;
  }
}

geometry_msgs::msg::Quaternion quaternion_multiply(
  const geometry_msgs::msg::Quaternion & parent,
  const geometry_msgs::msg::Quaternion & local)
{
  geometry_msgs::msg::Quaternion q;
  q.w = parent.w * local.w - parent.x * local.x - parent.y * local.y -
    parent.z * local.z;
  q.x = parent.w * local.x + parent.x * local.w + parent.y * local.z -
    parent.z * local.y;
  q.y = parent.w * local.y - parent.x * local.z + parent.y * local.w +
    parent.z * local.x;
  q.z = parent.w * local.z + parent.x * local.y - parent.y * local.x +
    parent.z * local.w;
  return q;
}

}  // namespace

geometry_msgs::msg::Transform to_transform(const ContactGloveSDKv2::Transform & tf)
{
  geometry_msgs::msg::Transform jt;
  jt.translation.x = tf.position.x;
  jt.translation.y = tf.position.y;
  jt.translation.z = tf.position.z;
  jt.rotation.w = tf.rotation.w;
  jt.rotation.x = tf.rotation.x;
  jt.rotation.y = tf.rotation.y;
  jt.rotation.z = tf.rotation.z;
  return jt;
}

std::string wrist_frame_id(std::string ns, const std::string & glove_id)
{
  return "ds2/" + normalize_namespace(std::move(ns)) + "/" + glove_id + "/wrist";
}

std::string source_wrist_frame_id(std::string ns, const std::string & glove_id)
{
  return "ds2/" + normalize_namespace(std::move(ns)) + "/" + glove_id + "/source_wrist";
}

std::string joint_frame_id(std::string ns, const std::string & glove_id, uint8_t node_index)
{
  using Skel = contact_glove_msgs::msg::Skeleton;
  // kJointFrameSuffixes only has real entries for the 24 non-wrist nodes (index 0, NODE_WRIST,
  // is a placeholder — see the comment above kJointFrameSuffixes). All current callers only ever
  // pass values in this range, but the function is public API, so reject anything else instead
  // of risking an out-of-bounds array access (or a malformed frame name for NODE_WRIST) here.
  if (node_index < Skel::NODE_THUMB_CMC || node_index > Skel::NODE_LITTLE_TIP) {
    throw std::invalid_argument(
      "contact_glove::joint_frame_id: node_index must be in "
      "[Skeleton::NODE_THUMB_CMC, Skeleton::NODE_LITTLE_TIP] (1..24), got " +
      std::to_string(node_index));
  }
  return "ds2/" + normalize_namespace(std::move(ns)) + "/" + glove_id + "/" +
         kJointFrameSuffixes.at(node_index);
}

std::array<geometry_msgs::msg::Quaternion, ContactGloveSDKv2::SKELETON_DATA_COUNT>
skeleton_wrist_relative_rotations(const contact_glove_msgs::msg::Skeleton & skeleton)
{
  using Skel = contact_glove_msgs::msg::Skeleton;
  std::array<geometry_msgs::msg::Quaternion, ContactGloveSDKv2::SKELETON_DATA_COUNT> rotations;
  rotations[Skel::NODE_WRIST].w = 1.0;
  for (uint8_t node = Skel::NODE_WRIST + 1; node <= Skel::NODE_LITTLE_TIP; ++node) {
    rotations[node] = quaternion_multiply(
      rotations[skeleton_joint_parent(node)], skeleton.joints[node].rotation);
  }
  return rotations;
}

namespace
{
// ErgonomicsData::data always contains one hand (ERGONOMICS_DATA_COUNT
// elements). As required by the SDK ErgonomicsDataType documentation, derive
// every index from the Left* enum value modulo ERGONOMICS_DATA_COUNT.
std::size_t ergonomics_index(ContactGloveSDKv2::ErgonomicsDataType type)
{
  return static_cast<std::size_t>(type) % ContactGloveSDKv2::ERGONOMICS_DATA_COUNT;
}
}  // namespace

void assign_ergonomics_pose(
  const std::array<float, ContactGloveSDKv2::ERGONOMICS_DATA_COUNT> & d,
  contact_glove_msgs::msg::Ergonomics & msg)
{
  using E = ContactGloveSDKv2::ErgonomicsDataType;

  msg.thumb.cmc = d[ergonomics_index(E::LeftThumbCMCFlex)];
  msg.thumb.mcp = d[ergonomics_index(E::LeftThumbMCPFlex)];
  msg.thumb.ip = d[ergonomics_index(E::LeftThumbIPFlex)];
  msg.thumb.tilt = d[ergonomics_index(E::LeftThumbMCPTilt)];

  msg.index.mcp = d[ergonomics_index(E::LeftIndexMCPFlex)];
  msg.index.pip = d[ergonomics_index(E::LeftIndexPIPFlex)];
  msg.index.dip = d[ergonomics_index(E::LeftIndexDIPFlex)];
  msg.index.tilt = d[ergonomics_index(E::LeftIndexMCPTilt)];

  msg.middle.mcp = d[ergonomics_index(E::LeftMiddleMCPFlex)];
  msg.middle.pip = d[ergonomics_index(E::LeftMiddlePIPFlex)];
  msg.middle.dip = d[ergonomics_index(E::LeftMiddleDIPFlex)];
  msg.middle.tilt = d[ergonomics_index(E::LeftMiddleMCPTilt)];

  msg.ring.mcp = d[ergonomics_index(E::LeftRingMCPFlex)];
  msg.ring.pip = d[ergonomics_index(E::LeftRingPIPFlex)];
  msg.ring.dip = d[ergonomics_index(E::LeftRingDIPFlex)];
  msg.ring.tilt = d[ergonomics_index(E::LeftRingMCPTilt)];

  msg.little.mcp = d[ergonomics_index(E::LeftLittleMCPFlex)];
  msg.little.pip = d[ergonomics_index(E::LeftLittlePIPFlex)];
  msg.little.dip = d[ergonomics_index(E::LeftLittleDIPFlex)];
  msg.little.tilt = d[ergonomics_index(E::LeftLittleMCPTilt)];
}

sensor_msgs::msg::JointState to_joint_state(const contact_glove_msgs::msg::Ergonomics & e)
{
  const std::array<float, kJointStateCount> degrees = {
    e.thumb.cmc, e.thumb.mcp, e.thumb.ip, e.thumb.tilt,
    e.index.mcp, e.index.pip, e.index.dip, e.index.tilt,
    e.middle.mcp, e.middle.pip, e.middle.dip, e.middle.tilt,
    e.ring.mcp, e.ring.pip, e.ring.dip, e.ring.tilt,
    e.little.mcp, e.little.pip, e.little.dip, e.little.tilt,
  };

  sensor_msgs::msg::JointState js;
  js.header = e.header;
  const std::string prefix = e.is_left ? "left_" : "right_";
  js.name.reserve(kJointStateCount);
  js.position.reserve(kJointStateCount);
  for (std::size_t i = 0; i < kJointStateCount; ++i) {
    js.name.push_back(prefix + kJointStateSuffixes[i]);
    js.position.push_back(static_cast<double>(degrees[i]) * M_PI / 180.0);
  }
  return js;
}

bool select_joint_state_glove_id(std::string & target_id, const std::string & msg_id)
{
  if (target_id.empty()) {
    target_id = msg_id;
  }
  return target_id == msg_id;
}

rclcpp::QoS joint_state_qos()
{
  return rclcpp::QoS(10);
}

}  // namespace contact_glove
