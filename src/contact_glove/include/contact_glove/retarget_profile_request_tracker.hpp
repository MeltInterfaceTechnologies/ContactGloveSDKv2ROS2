// Copyright (c) 2026 Melt Interface Technologies Inc.
// SPDX-License-Identifier: Apache-2.0

#ifndef CONTACT_GLOVE__RETARGET_PROFILE_REQUEST_TRACKER_HPP_
#define CONTACT_GLOVE__RETARGET_PROFILE_REQUEST_TRACKER_HPP_

#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <utility>

#include "contactglove/ContactGloveSDKv2.hpp"

namespace contact_glove
{

// C++ SDK RequestRetargetProfileInfo() only issues an asynchronous response
// with a request_id; it provides no waiting, correlation, or timeout handling.
// This class allocates a unique positive request_id for each ROS service call
// and safely delivers callback responses to the matching waiting call.
class RetargetProfileRequestTracker
{
public:
  struct PendingResponse
  {
    std::mutex mutex;
    std::condition_variable condition;
    bool active = true;
    bool completed = false;
    ContactGloveSDKv2::RetargetProfileInfo info;
  };

  using PendingResponsePtr = std::shared_ptr<PendingResponse>;

  // Registers a new pending state and returns a positive request_id not used by
  // any other pending state.
  std::pair<int32_t, PendingResponsePtr> register_request()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    for (int64_t attempts = 0; attempts < std::numeric_limits<int32_t>::max(); ++attempts) {
      const int32_t request_id = next_request_id_;
      next_request_id_ = request_id == std::numeric_limits<int32_t>::max() ? 1 : request_id + 1;
      if (pending_.find(request_id) == pending_.end()) {
        auto pending = std::make_shared<PendingResponse>();
        pending_.emplace(request_id, pending);
        return {request_id, std::move(pending)};
      }
    }
    // In practice, every positive int32 request_id cannot be pending at once.
    // If that ever occurs, do not send an SDK request; the caller reports
    // SDK_REQUEST_REJECTED.
    return {0, nullptr};
  }

  // If request_id is pending, stores the response and wakes its waiter. A late
  // response after remove_request(), for example after timeout, returns false
  // and is discarded.
  bool fulfill(const ContactGloveSDKv2::RetargetProfileInfo & info)
  {
    PendingResponsePtr pending;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      const auto found = pending_.find(info.requestId);
      if (found == pending_.end()) {
        return false;
      }
      pending = found->second;
    }

    {
      std::lock_guard<std::mutex> lock(pending->mutex);
      if (!pending->active || pending->completed) {
        return false;
      }
      pending->info = info;
      pending->completed = true;
    }
    pending->condition.notify_one();
    return true;
  }

  bool wait_for(
    int32_t request_id,
    const PendingResponsePtr & pending,
    std::chrono::milliseconds timeout,
    ContactGloveSDKv2::RetargetProfileInfo * info)
  {
    if (!pending || !info) {
      return false;
    }
    std::unique_lock<std::mutex> lock(pending->mutex);
    if (!pending->condition.wait_for(lock, timeout, [&pending] {return pending->completed;})) {
      // Decide timeout and deactivate under the same mutex. Even if a callback
      // found request_id first, it sees inactive after acquiring pending->mutex
      // and discards its response.
      pending->active = false;
      lock.unlock();
      erase_request(request_id, pending);
      return false;
    }
    *info = pending->info;
    pending->active = false;
    lock.unlock();
    erase_request(request_id, pending);
    return true;
  }

  // Cancels without waiting, for example when the SDK rejected the request.
  void remove_request(int32_t request_id, const PendingResponsePtr & pending)
  {
    if (!pending) {
      return;
    }
    {
      std::lock_guard<std::mutex> pending_lock(pending->mutex);
      pending->active = false;
    }
    erase_request(request_id, pending);
  }

private:
  // Removes only the identical pending state from the map. If request_id wraps
  // and is reused, an old call cannot erase its newer pending state. Callers
  // deactivate pending->active first.
  void erase_request(int32_t request_id, const PendingResponsePtr & pending)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto found = pending_.find(request_id);
    if (found != pending_.end() && found->second == pending) {
      pending_.erase(found);
    }
  }

  std::mutex mutex_;
  std::map<int32_t, PendingResponsePtr> pending_;
  int32_t next_request_id_ = 1;
};

}  // namespace contact_glove

#endif  // CONTACT_GLOVE__RETARGET_PROFILE_REQUEST_TRACKER_HPP_
