// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#include <array>
#include <atomic>
#include <chrono>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/transform.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "std_msgs/msg/header.hpp"

#include "contact_glove_msgs/msg/glove_data.hpp"
#include "contact_glove_msgs/msg/ergonomics.hpp"
#include "contact_glove_msgs/msg/skeleton.hpp"
#include "contact_glove_msgs/msg/raw_skeleton.hpp"
#include "contact_glove_msgs/msg/raw_sensor_transforms.hpp"
#include "contact_glove_msgs/msg/controller.hpp"
#include "contact_glove_msgs/msg/haptics_body.hpp"
#include "contact_glove_msgs/srv/get_retarget_profile.hpp"

#include "contactglove/ContactGloveSDKv2.hpp"

#include "contact_glove/conversions.hpp"
#include "contact_glove/retarget_profile_request_tracker.hpp"

using namespace std::chrono_literals;

// glove_data multiplexes several glove states through the id field on a single topic.
// With a transient_local history depth of 1, only the last-published glove is cached,
// so a subscriber that starts later misses the states of the other gloves.
// To prevent this, publish_glove_data() republishes every known glove on each update,
// keeping one latest sample per glove in the transient_local history.
// This depth is therefore the practical maximum number of simultaneously known gloves.
// The SDK itself has no glove-count limit; 16 is an operational default and must be
// increased when more gloves are used concurrently.
constexpr size_t kGloveDataHistoryDepth = 16;

class ContactGloveNode : public rclcpp::Node
{
public:
  ContactGloveNode()
  : Node("contact_glove_node"),
    last_received_time_nanoseconds_(get_clock()->now().nanoseconds())
  {
    ds_ip_ = declare_parameter<std::string>("ds_ip", "127.0.0.1");
    ds_port_ = declare_parameter<int>("ds_port", 25791);
    receive_port_ = declare_parameter<int>("receive_port", 25788);
    send_port_ = declare_parameter<int>("send_port", 0);
    if (send_port_ < 0 || send_port_ > 65535) {
      throw std::invalid_argument("send_port must be in the range 0..65535");
    }
    timeout_duration_ = rclcpp::Duration::from_nanoseconds(
      static_cast<int64_t>(1e6) * declare_parameter<int>("timeout_duration", 1000));
    const int retarget_profile_timeout_ms =
      declare_parameter<int>("retarget_profile_timeout_ms", 1000);
    if (retarget_profile_timeout_ms <= 0) {
      throw std::invalid_argument("retarget_profile_timeout_ms must be greater than zero");
    }
    retarget_profile_timeout_ = std::chrono::milliseconds(retarget_profile_timeout_ms);
    try_reconnect_param_ = declare_parameter<bool>("try_reconnect", true);
    try_reconnect_.store(try_reconnect_param_, std::memory_order_relaxed);

    // left/joint_states and right/joint_states each carry the joint angles of one glove
    // because the URDF describes one robot with fixed joint names. Mixing the id-
    // multiplexed states of several gloves (as used by glove_data, skeleton, and
    // ergonomics) on one topic would make robot_state_publisher alternate between
    // gloves without distinguishing their ids, resulting in a visibly jerky model.
    // Select one target glove ID for each side. The default empty value automatically
    // selects the first glove received for that side and records it in
    // left_joint_state_glove_id_ or right_joint_state_glove_id_. To use more than one
    // glove on the same side, explicitly select the target through this parameter or
    // launch separate node instances in separate namespaces.
    left_joint_state_glove_id_param_ =
      declare_parameter<std::string>("left_joint_state_glove_id", "");
    right_joint_state_glove_id_param_ =
      declare_parameter<std::string>("right_joint_state_glove_id", "");
    left_joint_state_glove_id_ = left_joint_state_glove_id_param_;
    right_joint_state_glove_id_ = right_joint_state_glove_id_param_;

    // glove_data contains infrequently changing state such as battery level and
    // connection state, so it uses transient_local (latched) delivery to immediately
    // provide the current state to subscribers that start later. See the
    // kGloveDataHistoryDepth comment and publish_glove_data() for the per-glove history
    // depth and republishing rationale. Separate left/right topics allow ROS 2 users to
    // subscribe to or remap a single hand naturally; id and is_left remain in the message.
    reset_glove_data_publishers();
    // Streaming topics carry high-rate sensor data, so use best-effort/volatile QoS to
    // avoid blocking publishers when subscribers are slow or the network is interrupted.
    left_ergonomics_pub_ = create_publisher<contact_glove_msgs::msg::Ergonomics>(
      "left/ergonomics", rclcpp::SensorDataQoS());
    right_ergonomics_pub_ = create_publisher<contact_glove_msgs::msg::Ergonomics>(
      "right/ergonomics", rclcpp::SensorDataQoS());
    left_skeleton_pub_ = create_publisher<contact_glove_msgs::msg::Skeleton>(
      "left/skeleton", rclcpp::SensorDataQoS());
    right_skeleton_pub_ = create_publisher<contact_glove_msgs::msg::Skeleton>(
      "right/skeleton", rclcpp::SensorDataQoS());
    left_raw_skeleton_pub_ = create_publisher<contact_glove_msgs::msg::RawSkeleton>(
      "left/raw_skeleton", rclcpp::SensorDataQoS());
    right_raw_skeleton_pub_ = create_publisher<contact_glove_msgs::msg::RawSkeleton>(
      "right/raw_skeleton", rclcpp::SensorDataQoS());
    // Publish Ergonomics values converted from degrees to radians using the joint names
    // and order in urdf/left_hand.urdf.xacro and urdf/right_hand.urdf.xacro. These
    // topics are intended for use with robot_state_publisher; see
    // contact_glove::to_joint_state() and the Web API reference. For why these use reliable/volatile
    // QoS rather than the other streaming topics, see contact_glove::joint_state_qos().
    left_joint_state_pub_ = create_publisher<sensor_msgs::msg::JointState>(
      "left/joint_states", contact_glove::joint_state_qos());
    right_joint_state_pub_ = create_publisher<sensor_msgs::msg::JointState>(
      "right/joint_states", contact_glove::joint_state_qos());
    left_raw_sensor_pub_ = create_publisher<contact_glove_msgs::msg::RawSensorTransforms>(
      "left/raw_sensor_transforms", rclcpp::SensorDataQoS());
    right_raw_sensor_pub_ = create_publisher<contact_glove_msgs::msg::RawSensorTransforms>(
      "right/raw_sensor_transforms", rclcpp::SensorDataQoS());
    left_controller_pub_ = create_publisher<contact_glove_msgs::msg::Controller>(
      "left/controller", rclcpp::SensorDataQoS());
    right_controller_pub_ = create_publisher<contact_glove_msgs::msg::Controller>(
      "right/controller", rclcpp::SensorDataQoS());

    // Keep haptics_body reliable/volatile to avoid dropping vibration commands.
    left_haptics_sub_ = create_subscription<contact_glove_msgs::msg::HapticsBody>(
      "left/haptics_body", rclcpp::QoS(10),
      std::bind(&ContactGloveNode::haptics_callback, this, std::placeholders::_1));
    right_haptics_sub_ = create_subscription<contact_glove_msgs::msg::HapticsBody>(
      "right/haptics_body", rclcpp::QoS(10),
      std::bind(&ContactGloveNode::haptics_callback, this, std::placeholders::_1));

    get_retarget_profile_service_ =
      create_service<contact_glove_msgs::srv::GetRetargetProfile>(
      "get_retarget_profile",
      std::bind(
        &ContactGloveNode::get_retarget_profile_callback, this,
        std::placeholders::_1, std::placeholders::_2));

    timer_ = create_wall_timer(
      std::chrono::nanoseconds(timeout_duration_.nanoseconds()),
      std::bind(&ContactGloveNode::check_timeout, this));

    // Register SDK callbacks before connecting so no data is missed.
    sdk_.RegisterCallbackForGloveDataStream(
      [this](const ContactGloveSDKv2::GloveData & g) {publish_glove_data(g);});
    sdk_.RegisterCallbackForErgonomicsStream(
      [this](const ContactGloveSDKv2::ErgonomicsData & e) {publish_ergonomics(e);});
    sdk_.RegisterCallbackForSkeletonStream(
      [this](const ContactGloveSDKv2::SkeletonData & s) {publish_skeleton(s);});
    sdk_.RegisterCallbackForRawSkeletonStream(
      [this](const ContactGloveSDKv2::RawSkeletonData & s) {publish_raw_skeleton(s);});
    sdk_.RegisterCallbackForRawSensorTransformsStream(
      [this](const ContactGloveSDKv2::RawSensorTransformsData & r) {publish_raw_sensor(r);});
    sdk_.RegisterCallbackForControllerDataStream(
      [this](const ContactGloveSDKv2::ControllerData & c) {publish_controller(c);});
    sdk_.RegisterCallbackForRetargetProfileInfoStream(
      [this](const ContactGloveSDKv2::RetargetProfileInfo & info) {
        receive_retarget_profile_info(info);
      });

    connect();
  }

  ~ContactGloveNode()
  {
    sdk_.Disconnect(host_);
  }

private:
  // Recreate the left/right glove_data publishers. A transient_local DDS writer retains
  // its own history (up to depth recently published samples), which clearing
  // known_gloves_--the node's application-level cache--does not remove. Clearing only
  // known_gloves_ on reconnect would therefore continue to deliver stale glove states
  // from the prior session to new subscribers through transient_local until enough new
  // samples displaced them. Recreating the publisher destroys that old DDS writer and
  // replaces it with a writer without history, reliably removing prior-session samples.
  void reset_glove_data_publishers()
  {
    left_glove_data_pub_ = create_publisher<contact_glove_msgs::msg::GloveData>(
      "left/glove_data", rclcpp::QoS(kGloveDataHistoryDepth).transient_local());
    right_glove_data_pub_ = create_publisher<contact_glove_msgs::msg::GloveData>(
      "right/glove_data", rclcpp::QoS(kGloveDataHistoryDepth).transient_local());
  }

  void connect()
  {
    if (try_reconnect_param_) {
      try_reconnect_.store(true, std::memory_order_relaxed);
    }
    host_ = {"contact_glove", ds_ip_,
      static_cast<uint32_t>(ds_port_),
      static_cast<uint32_t>(receive_port_),
      static_cast<uint32_t>(send_port_)};
    auto rc = sdk_.ConnectToHost(host_);
    if (rc == ContactGloveSDKv2::SDKReturnCode::Success) {
      RCLCPP_INFO(
        get_logger(), "Connection requested to DivingStation at %s:%d (callback port: %d, send port: %d%s)",
        ds_ip_.c_str(), ds_port_, receive_port_, send_port_,
        send_port_ == 0 ? " (auto)" : "");
    } else {
      RCLCPP_ERROR(
        get_logger(), "Failed to connect to DivingStation at %s:%d",
        ds_ip_.c_str(), ds_port_);
    }
  }

  void check_timeout()
  {
    if (!try_reconnect_.load(std::memory_order_relaxed)) {
      return;
    }
    const auto last_received_time = rclcpp::Time(
      last_received_time_nanoseconds_.load(std::memory_order_relaxed),
      get_clock()->get_clock_type());
    if (get_clock()->now() - last_received_time > timeout_duration_) {
      RCLCPP_WARN(
        get_logger(),
        "No data received for %.1f seconds. Retrying Connect on the same socket...",
        timeout_duration_.seconds());
      // Preserve the source endpoint and pending LAN approval. ConnectToHost
      // in SDK 0.4.2 resends Connect using the existing socket.
      // Only explicit shutdown should send Disconnect.
      // After reconnecting, the glove configuration from the prior session (count and
      // connection state) may no longer be valid: only some gloves might return or
      // they might be replaced. Leaving known_gloves_ intact would republish stale
      // prior-session data on every new update, causing late subscribers to receive it
      // as current state through transient_local. Clear known_gloves_ on reconnect and
      // thereafter republish only gloves actually received in the new session.
      //
      // Clearing known_gloves_, the application cache, alone does not erase the prior
      // publish history retained by the transient_local DDS writer. A new subscriber
      // immediately after reconnect could still receive stale pre-disconnect state from
      // that writer. Recreate the publishers as well to destroy the writer with its old
      // history.
      {
        std::lock_guard<std::mutex> lock(glove_data_mutex_);
        known_gloves_.clear();
        reset_glove_data_publishers();
      }
      // Reset the joint_states target glove IDs whenever the session changes for the
      // same reason as known_gloves_. When left/right_joint_state_glove_id_param_ is
      // non-empty, this simply restores the fixed configured ID. Otherwise it resumes
      // automatic selection of the first glove received after reconnection.
      {
        std::lock_guard<std::mutex> lock(joint_state_glove_id_mutex_);
        left_joint_state_glove_id_ = left_joint_state_glove_id_param_;
        right_joint_state_glove_id_ = right_joint_state_glove_id_param_;
      }
      connect();
    }
  }

  void mark_data_received()
  {
    last_received_time_nanoseconds_.store(
      get_clock()->now().nanoseconds(), std::memory_order_relaxed);
  }

  std_msgs::msg::Header make_stream_header(const std::string & glove_id)
  {
    std_msgs::msg::Header header;
    header.stamp = get_clock()->now();
    header.frame_id = contact_glove::wrist_frame_id(get_namespace(), glove_id);
    return header;
  }

  std_msgs::msg::Header make_source_skeleton_header(const std::string & glove_id)
  {
    std_msgs::msg::Header header;
    header.stamp = get_clock()->now();
    header.frame_id = contact_glove::source_wrist_frame_id(get_namespace(), glove_id);
    return header;
  }

  void publish_glove_data(const ContactGloveSDKv2::GloveData & g)
  {
    mark_data_received();
    contact_glove_msgs::msg::GloveData msg;
    msg.id = g.id;
    msg.header = make_stream_header(g.id);
    msg.pair_id = g.pairId;
    msg.battery_percentage = static_cast<int32_t>(g.batteryPercentage);
    msg.is_haptics = g.isHaptics;
    msg.is_left = g.isLeft;
    msg.family_type = static_cast<int32_t>(g.familyType);
    msg.color = static_cast<int32_t>(g.color);
    msg.connected_state = static_cast<int32_t>(g.connectedState);
    msg.name = g.name;
    msg.is_external_power_present = g.isExternalPowerPresent;

    // Republish the latest state of every known glove on every update, not only the
    // updated glove. Otherwise the transient_local depth history would retain only the
    // last-published glove and a subscriber that starts later would miss other gloves.
    // This maintains one latest sample per glove in the cache. Each glove publishes to
    // only left/glove_data or right/glove_data according to is_left.
    // known_gloves_ and the left/right publisher pointers are also accessed by
    // check_timeout() on another thread when reconnecting and recreating publishers.
    // Protect them with a mutex, snapshot both the cache and current publisher pointers,
    // then call publish after releasing the lock.
    std::vector<contact_glove_msgs::msg::GloveData> snapshot;
    rclcpp::Publisher<contact_glove_msgs::msg::GloveData>::SharedPtr left_pub;
    rclcpp::Publisher<contact_glove_msgs::msg::GloveData>::SharedPtr right_pub;
    {
      std::lock_guard<std::mutex> lock(glove_data_mutex_);
      known_gloves_[g.id] = msg;
      snapshot.reserve(known_gloves_.size());
      for (const auto & [id, cached] : known_gloves_) {
        snapshot.push_back(cached);
      }
      left_pub = left_glove_data_pub_;
      right_pub = right_glove_data_pub_;
    }
    for (const auto & cached : snapshot) {
      auto & pub = cached.is_left ? left_pub : right_pub;
      pub->publish(cached);
    }
  }

  void publish_ergonomics(const ContactGloveSDKv2::ErgonomicsData & e)
  {
    mark_data_received();
    contact_glove_msgs::msg::Ergonomics msg;
    msg.id = e.id;
    msg.header = make_stream_header(e.id);
    msg.is_left = e.isLeft;
    msg.generated_at_ms = static_cast<int64_t>(e.generatedAt);
    msg.tracking_state = static_cast<uint8_t>(e.trackingState);

    contact_glove::assign_ergonomics_pose(e.data, msg);

    (msg.is_left ? left_ergonomics_pub_ : right_ergonomics_pub_)->publish(msg);

    publish_joint_state_if_target_glove(msg);
  }

  // Publish joint_states only for the Ergonomics data of the target glove selected by
  // left/right_joint_state_glove_id_. See contact_glove::select_joint_state_glove_id()
  // for the tested selection logic.
  void publish_joint_state_if_target_glove(const contact_glove_msgs::msg::Ergonomics & msg)
  {
    bool is_target;
    std::string target_id_snapshot;
    {
      std::lock_guard<std::mutex> lock(joint_state_glove_id_mutex_);
      std::string & target_id =
        msg.is_left ? left_joint_state_glove_id_ : right_joint_state_glove_id_;
      is_target = contact_glove::select_joint_state_glove_id(target_id, msg.id);
      target_id_snapshot = target_id;
    }
    if (!is_target) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 5000,
        "Ignoring ergonomics from glove id=%s for %s/joint_states (already publishing id=%s "
        "there). JointState + URDF tracks only one glove per side per contact_glove_node "
        "instance; set the %s_joint_state_glove_id parameter to choose which one, or run a "
        "separate namespaced instance for additional gloves.",
        msg.id.c_str(), msg.is_left ? "left" : "right", target_id_snapshot.c_str(),
        msg.is_left ? "left" : "right");
      return;
    }
    const auto joint_state = contact_glove::to_joint_state(msg);
    (msg.is_left ? left_joint_state_pub_ : right_joint_state_pub_)->publish(joint_state);
  }

  void publish_skeleton(const ContactGloveSDKv2::SkeletonData & s)
  {
    mark_data_received();
    contact_glove_msgs::msg::Skeleton msg;
    msg.id = s.id;
    msg.header = make_stream_header(s.id);
    msg.profile_uuid = s.profileUuid;
    msg.is_left = s.isLeft;
    msg.generated_at_ms = static_cast<int64_t>(s.generatedAt);
    msg.tracking_state = static_cast<uint8_t>(s.trackingState);

    // SDK SkeletonDataType values 0..24 are defined to match the order and values of
    // contact_glove_msgs::msg::Skeleton::NODE_*. These static_asserts verify each
    // NODE_* mapping as well as the element count. A count-only assertion would not
    // catch a future SDK enum reordering that kept 25 elements and would cause t[i] to
    // refer to the wrong joint.
    using T = ContactGloveSDKv2::SkeletonDataType;
    using S = contact_glove_msgs::msg::Skeleton;
    static_assert(
      static_cast<uint32_t>(T::SkeletonWrist) == S::NODE_WRIST &&
      static_cast<uint32_t>(T::SkeletonThumbCMC) == S::NODE_THUMB_CMC &&
      static_cast<uint32_t>(T::SkeletonThumbMCP) == S::NODE_THUMB_MCP &&
      static_cast<uint32_t>(T::SkeletonThumbIP) == S::NODE_THUMB_IP &&
      static_cast<uint32_t>(T::SkeletonThumbTip) == S::NODE_THUMB_TIP &&
      static_cast<uint32_t>(T::SkeletonIndexCMC) == S::NODE_INDEX_CMC &&
      static_cast<uint32_t>(T::SkeletonIndexMCP) == S::NODE_INDEX_MCP &&
      static_cast<uint32_t>(T::SkeletonIndexPIP) == S::NODE_INDEX_PIP &&
      static_cast<uint32_t>(T::SkeletonIndexDIP) == S::NODE_INDEX_DIP &&
      static_cast<uint32_t>(T::SkeletonIndexTip) == S::NODE_INDEX_TIP &&
      static_cast<uint32_t>(T::SkeletonMiddleCMC) == S::NODE_MIDDLE_CMC &&
      static_cast<uint32_t>(T::SkeletonMiddleMCP) == S::NODE_MIDDLE_MCP &&
      static_cast<uint32_t>(T::SkeletonMiddlePIP) == S::NODE_MIDDLE_PIP &&
      static_cast<uint32_t>(T::SkeletonMiddleDIP) == S::NODE_MIDDLE_DIP &&
      static_cast<uint32_t>(T::SkeletonMiddleTip) == S::NODE_MIDDLE_TIP &&
      static_cast<uint32_t>(T::SkeletonRingCMC) == S::NODE_RING_CMC &&
      static_cast<uint32_t>(T::SkeletonRingMCP) == S::NODE_RING_MCP &&
      static_cast<uint32_t>(T::SkeletonRingPIP) == S::NODE_RING_PIP &&
      static_cast<uint32_t>(T::SkeletonRingDIP) == S::NODE_RING_DIP &&
      static_cast<uint32_t>(T::SkeletonRingTip) == S::NODE_RING_TIP &&
      static_cast<uint32_t>(T::SkeletonLittleCMC) == S::NODE_LITTLE_CMC &&
      static_cast<uint32_t>(T::SkeletonLittleMCP) == S::NODE_LITTLE_MCP &&
      static_cast<uint32_t>(T::SkeletonLittlePIP) == S::NODE_LITTLE_PIP &&
      static_cast<uint32_t>(T::SkeletonLittleDIP) == S::NODE_LITTLE_DIP &&
      static_cast<uint32_t>(T::SkeletonLittleTip) == S::NODE_LITTLE_TIP,
      "SDK SkeletonDataType each value must match the corresponding Skeleton.msg NODE_* constant");
    static_assert(
      S::NODE_LITTLE_TIP + 1 == std::tuple_size<std::decay_t<decltype(s.transforms)>>::value,
      "Skeleton.msg NODE_* count must match SDK SkeletonDataType count");

    const auto & t = s.transforms;
    for (std::size_t i = 0; i < msg.joints.size(); ++i) {
      msg.joints[i] = contact_glove::to_transform(t[i]);
    }

    (msg.is_left ? left_skeleton_pub_ : right_skeleton_pub_)->publish(msg);
  }

  void publish_raw_skeleton(const ContactGloveSDKv2::RawSkeletonData & s)
  {
    mark_data_received();
    contact_glove_msgs::msg::RawSkeleton msg;
    msg.id = s.id;
    msg.header = make_source_skeleton_header(s.id);
    msg.is_left = s.isLeft;
    msg.generated_at_ms = static_cast<int64_t>(s.generatedAt);
    msg.tracking_state = static_cast<uint8_t>(s.trackingState);

    // RawSkeletonData has the same fixed 25-joint topology as SkeletonData.
    // RawSkeleton.msg exposes each index, so verify every SDK enum mapping at compile time.
    using T = ContactGloveSDKv2::SkeletonDataType;
    using R = contact_glove_msgs::msg::RawSkeleton;
    static_assert(
      static_cast<uint32_t>(T::SkeletonWrist) == R::NODE_WRIST &&
      static_cast<uint32_t>(T::SkeletonThumbCMC) == R::NODE_THUMB_CMC &&
      static_cast<uint32_t>(T::SkeletonThumbMCP) == R::NODE_THUMB_MCP &&
      static_cast<uint32_t>(T::SkeletonThumbIP) == R::NODE_THUMB_IP &&
      static_cast<uint32_t>(T::SkeletonThumbTip) == R::NODE_THUMB_TIP &&
      static_cast<uint32_t>(T::SkeletonIndexCMC) == R::NODE_INDEX_CMC &&
      static_cast<uint32_t>(T::SkeletonIndexMCP) == R::NODE_INDEX_MCP &&
      static_cast<uint32_t>(T::SkeletonIndexPIP) == R::NODE_INDEX_PIP &&
      static_cast<uint32_t>(T::SkeletonIndexDIP) == R::NODE_INDEX_DIP &&
      static_cast<uint32_t>(T::SkeletonIndexTip) == R::NODE_INDEX_TIP &&
      static_cast<uint32_t>(T::SkeletonMiddleCMC) == R::NODE_MIDDLE_CMC &&
      static_cast<uint32_t>(T::SkeletonMiddleMCP) == R::NODE_MIDDLE_MCP &&
      static_cast<uint32_t>(T::SkeletonMiddlePIP) == R::NODE_MIDDLE_PIP &&
      static_cast<uint32_t>(T::SkeletonMiddleDIP) == R::NODE_MIDDLE_DIP &&
      static_cast<uint32_t>(T::SkeletonMiddleTip) == R::NODE_MIDDLE_TIP &&
      static_cast<uint32_t>(T::SkeletonRingCMC) == R::NODE_RING_CMC &&
      static_cast<uint32_t>(T::SkeletonRingMCP) == R::NODE_RING_MCP &&
      static_cast<uint32_t>(T::SkeletonRingPIP) == R::NODE_RING_PIP &&
      static_cast<uint32_t>(T::SkeletonRingDIP) == R::NODE_RING_DIP &&
      static_cast<uint32_t>(T::SkeletonRingTip) == R::NODE_RING_TIP &&
      static_cast<uint32_t>(T::SkeletonLittleCMC) == R::NODE_LITTLE_CMC &&
      static_cast<uint32_t>(T::SkeletonLittleMCP) == R::NODE_LITTLE_MCP &&
      static_cast<uint32_t>(T::SkeletonLittlePIP) == R::NODE_LITTLE_PIP &&
      static_cast<uint32_t>(T::SkeletonLittleDIP) == R::NODE_LITTLE_DIP &&
      static_cast<uint32_t>(T::SkeletonLittleTip) == R::NODE_LITTLE_TIP,
      "SDK SkeletonDataType each value must match the corresponding RawSkeleton.msg NODE_* "
      "constant");
    static_assert(
      R::NODE_LITTLE_TIP + 1 == std::tuple_size<std::decay_t<decltype(s.transforms)>>::value,
      "RawSkeleton.msg NODE_* count must match SDK RawSkeletonData count");

    for (std::size_t i = 0; i < msg.joints.size(); ++i) {
      msg.joints[i] = contact_glove::to_transform(s.transforms[i]);
    }

    (msg.is_left ? left_raw_skeleton_pub_ : right_raw_skeleton_pub_)->publish(msg);
  }

  void publish_raw_sensor(const ContactGloveSDKv2::RawSensorTransformsData & r)
  {
    mark_data_received();
    contact_glove_msgs::msg::RawSensorTransforms msg;
    msg.id = r.id;
    msg.header = make_stream_header(r.id);
    msg.is_left = r.isLeft;
    msg.generated_at_ms = static_cast<int64_t>(r.generatedAt);

    // RawSensorTransformsData has no per-sensor index enum equivalent to SkeletonDataType
    // for Skeleton or ErgonomicsDataType for Ergonomics. Its documentation specifies only
    // the thumb, index, middle, ring, little order. These indices therefore remain based
    // on that documented order rather than an enum; at least assert the element count to
    // catch changes to the array size.
    static_assert(
      std::tuple_size<std::decay_t<decltype(r.transforms)>>::value == 5,
      "RawSensorTransformsData::transforms count must match the 5 fields "
      "(thumb/index/middle/ring/little) of RawSensorTransforms.msg");
    msg.thumb = contact_glove::to_transform(r.transforms[0]);
    msg.index = contact_glove::to_transform(r.transforms[1]);
    msg.middle = contact_glove::to_transform(r.transforms[2]);
    msg.ring = contact_glove::to_transform(r.transforms[3]);
    msg.little = contact_glove::to_transform(r.transforms[4]);
    (msg.is_left ? left_raw_sensor_pub_ : right_raw_sensor_pub_)->publish(msg);
  }

  void publish_controller(const ContactGloveSDKv2::ControllerData & c)
  {
    mark_data_received();
    contact_glove_msgs::msg::Controller msg;
    msg.id = c.id;
    msg.header = make_stream_header(c.id);
    msg.is_left = c.isLeft;
    msg.a = static_cast<int32_t>(c.aButton);
    msg.b = static_cast<int32_t>(c.bButton);
    msg.sys = static_cast<int32_t>(c.sysButton);
    msg.trigger_button = static_cast<int32_t>(c.triggerButton);
    msg.joystick_button = static_cast<int32_t>(c.joystickButton);
    msg.trackpad_button = static_cast<int32_t>(c.trackpadButton);
    msg.trigger = c.trigger;
    msg.grip_value = c.gripValue;
    msg.grip_force = c.gripForce;
    msg.joystick_x = c.joystickX;
    msg.joystick_y = c.joystickY;
    msg.trackpad_x = c.trackpadX;
    msg.trackpad_y = c.trackpadY;
    (msg.is_left ? left_controller_pub_ : right_controller_pub_)->publish(msg);
  }

  void receive_retarget_profile_info(const ContactGloveSDKv2::RetargetProfileInfo & info)
  {
    mark_data_received();
    if (!retarget_profile_requests_.fulfill(info)) {
      RCLCPP_DEBUG(
        get_logger(), "Ignoring unmatched retarget profile response request_id=%d", info.requestId);
    }
  }

  void get_retarget_profile_callback(
    const std::shared_ptr<contact_glove_msgs::srv::GetRetargetProfile::Request> request,
    std::shared_ptr<contact_glove_msgs::srv::GetRetargetProfile::Response> response)
  {
    using Service = contact_glove_msgs::srv::GetRetargetProfile;
    const auto [request_id, pending] = retarget_profile_requests_.register_request();
    if (!pending) {
      response->status = Service::Response::STATUS_SDK_REQUEST_REJECTED;
      RCLCPP_ERROR(get_logger(), "No request_id is available for retarget profile lookup");
      return;
    }

    const auto rc = sdk_.RequestRetargetProfileInfo(request->profile_uuid, request_id);
    if (rc != ContactGloveSDKv2::SDKReturnCode::Success) {
      retarget_profile_requests_.remove_request(request_id, pending);
      response->status = Service::Response::STATUS_SDK_REQUEST_REJECTED;
      RCLCPP_WARN(
        get_logger(), "Retarget profile lookup was rejected for uuid=%s (code=%u)",
        request->profile_uuid.c_str(), static_cast<uint32_t>(rc));
      return;
    }

    ContactGloveSDKv2::RetargetProfileInfo info;
    const bool received = retarget_profile_requests_.wait_for(
      request_id, pending, retarget_profile_timeout_, &info);
    if (!received) {
      response->status = Service::Response::STATUS_TIMEOUT;
      RCLCPP_WARN(
        get_logger(), "Timed out after %ld ms waiting for retarget profile uuid=%s",
        retarget_profile_timeout_.count(), request->profile_uuid.c_str());
      return;
    }

    response->status = static_cast<uint8_t>(info.status);
    response->profile_uuid = info.profileUuid;
    response->name = info.name;
    response->description = info.description;
  }

  void haptics_callback(const contact_glove_msgs::msg::HapticsBody & msg)
  {
    RCLCPP_INFO(
      get_logger(),
      "Send haptics body id: %s, frequency: %.1f, amplitude: %.2f, duration: %.3f",
      msg.id.c_str(), msg.frequency, msg.amplitude, msg.duration);
    auto rc = sdk_.VibrateGlove(msg.id, msg.frequency, msg.amplitude, msg.duration);
    if (rc != ContactGloveSDKv2::SDKReturnCode::Success) {
      RCLCPP_WARN(
        get_logger(), "VibrateGlove failed for id=%s (code=%u)",
        msg.id.c_str(), static_cast<uint32_t>(rc));
    }
  }

  ContactGloveSDKv2::SDK sdk_;
  ContactGloveSDKv2::Host host_;

  std::string ds_ip_;
  int ds_port_;
  int receive_port_;
  int send_port_;

  rclcpp::Publisher<contact_glove_msgs::msg::GloveData>::SharedPtr left_glove_data_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::GloveData>::SharedPtr right_glove_data_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::Ergonomics>::SharedPtr left_ergonomics_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::Ergonomics>::SharedPtr right_ergonomics_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::Skeleton>::SharedPtr left_skeleton_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::Skeleton>::SharedPtr right_skeleton_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::RawSkeleton>::SharedPtr left_raw_skeleton_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::RawSkeleton>::SharedPtr right_raw_skeleton_pub_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr left_joint_state_pub_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr right_joint_state_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::RawSensorTransforms>::SharedPtr left_raw_sensor_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::RawSensorTransforms>::SharedPtr right_raw_sensor_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::Controller>::SharedPtr left_controller_pub_;
  rclcpp::Publisher<contact_glove_msgs::msg::Controller>::SharedPtr right_controller_pub_;
  rclcpp::Subscription<contact_glove_msgs::msg::HapticsBody>::SharedPtr left_haptics_sub_;
  rclcpp::Subscription<contact_glove_msgs::msg::HapticsBody>::SharedPtr right_haptics_sub_;
  rclcpp::Service<contact_glove_msgs::srv::GetRetargetProfile>::SharedPtr
    get_retarget_profile_service_;
  rclcpp::TimerBase::SharedPtr timer_;

  // Protect left_glove_data_pub_ and right_glove_data_pub_ in addition to known_gloves_;
  // the publishers are recreated by reset_glove_data_publishers() on reconnect.
  // publish_glove_data() runs from the SDK stream callback thread, while
  // check_timeout() runs from the ROS timer/executor thread.
  std::mutex glove_data_mutex_;
  std::map<std::string, contact_glove_msgs::msg::GloveData> known_gloves_;

  std::atomic<int64_t> last_received_time_nanoseconds_;
  rclcpp::Duration timeout_duration_{1, 0};
  std::chrono::milliseconds retarget_profile_timeout_{1000};
  bool try_reconnect_param_ = true;
  std::atomic<bool> try_reconnect_{true};
  contact_glove::RetargetProfileRequestTracker retarget_profile_requests_;

  // Lock for the same reason as glove_data_mutex_: both publish_ergonomics() on the SDK
  // stream callback thread and check_timeout() on the ROS timer thread access these IDs.
  std::mutex joint_state_glove_id_mutex_;
  std::string left_joint_state_glove_id_param_;
  std::string right_joint_state_glove_id_param_;
  std::string left_joint_state_glove_id_;
  std::string right_joint_state_glove_id_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ContactGloveNode>());
  rclcpp::shutdown();
  return 0;
}
