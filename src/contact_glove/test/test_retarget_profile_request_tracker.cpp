// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#include <chrono>

#include "gtest/gtest.h"

#include "contact_glove/retarget_profile_request_tracker.hpp"

using namespace std::chrono_literals;

TEST(RetargetProfileRequestTracker, CorrelatesOutOfOrderResponsesToTheirRequestIds)
{
  contact_glove::RetargetProfileRequestTracker tracker;
  const auto [first_id, first_pending] = tracker.register_request();
  const auto [second_id, second_pending] = tracker.register_request();

  ASSERT_GT(first_id, 0);
  ASSERT_GT(second_id, 0);
  ASSERT_NE(first_id, second_id);

  ContactGloveSDKv2::RetargetProfileInfo second_info;
  second_info.requestId = second_id;
  second_info.profileUuid = "00000000-0000-4000-8000-000000000002";
  second_info.status = 1;
  EXPECT_TRUE(tracker.fulfill(second_info));

  ContactGloveSDKv2::RetargetProfileInfo first_info;
  first_info.requestId = first_id;
  first_info.profileUuid = "00000000-0000-4000-8000-000000000001";
  first_info.status = 0;
  first_info.name = "Left profile";
  EXPECT_TRUE(tracker.fulfill(first_info));

  ContactGloveSDKv2::RetargetProfileInfo received;
  ASSERT_TRUE(tracker.wait_for(first_id, first_pending, 0ms, &received));
  EXPECT_EQ(received.requestId, first_id);
  EXPECT_EQ(received.name, "Left profile");
  ASSERT_TRUE(tracker.wait_for(second_id, second_pending, 0ms, &received));
  EXPECT_EQ(received.requestId, second_id);
  EXPECT_EQ(received.status, 1);
}

TEST(RetargetProfileRequestTracker, TimesOutAndDropsLateResponsesAfterRemoval)
{
  contact_glove::RetargetProfileRequestTracker tracker;
  const auto [request_id, pending] = tracker.register_request();

  ContactGloveSDKv2::RetargetProfileInfo received;
  EXPECT_FALSE(tracker.wait_for(request_id, pending, 1ms, &received));

  ContactGloveSDKv2::RetargetProfileInfo late_info;
  late_info.requestId = request_id;
  late_info.status = 0;
  EXPECT_FALSE(tracker.fulfill(late_info));
}

TEST(RetargetProfileRequestTracker, IgnoresResponsesForUnknownRequestIds)
{
  contact_glove::RetargetProfileRequestTracker tracker;
  ContactGloveSDKv2::RetargetProfileInfo info;
  info.requestId = 123;
  EXPECT_FALSE(tracker.fulfill(info));
}
