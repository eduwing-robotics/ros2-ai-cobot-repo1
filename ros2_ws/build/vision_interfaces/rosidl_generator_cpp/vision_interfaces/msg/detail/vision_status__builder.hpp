// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from vision_interfaces:msg/VisionStatus.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/vision_status.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__BUILDER_HPP_
#define VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "vision_interfaces/msg/detail/vision_status__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace vision_interfaces
{

namespace msg
{

namespace builder
{

class Init_VisionStatus_message
{
public:
  explicit Init_VisionStatus_message(::vision_interfaces::msg::VisionStatus & msg)
  : msg_(msg)
  {}
  ::vision_interfaces::msg::VisionStatus message(::vision_interfaces::msg::VisionStatus::_message_type arg)
  {
    msg_.message = std::move(arg);
    return std::move(msg_);
  }

private:
  ::vision_interfaces::msg::VisionStatus msg_;
};

class Init_VisionStatus_inference_count
{
public:
  explicit Init_VisionStatus_inference_count(::vision_interfaces::msg::VisionStatus & msg)
  : msg_(msg)
  {}
  Init_VisionStatus_message inference_count(::vision_interfaces::msg::VisionStatus::_inference_count_type arg)
  {
    msg_.inference_count = std::move(arg);
    return Init_VisionStatus_message(msg_);
  }

private:
  ::vision_interfaces::msg::VisionStatus msg_;
};

class Init_VisionStatus_missing_cameras
{
public:
  explicit Init_VisionStatus_missing_cameras(::vision_interfaces::msg::VisionStatus & msg)
  : msg_(msg)
  {}
  Init_VisionStatus_inference_count missing_cameras(::vision_interfaces::msg::VisionStatus::_missing_cameras_type arg)
  {
    msg_.missing_cameras = std::move(arg);
    return Init_VisionStatus_inference_count(msg_);
  }

private:
  ::vision_interfaces::msg::VisionStatus msg_;
};

class Init_VisionStatus_active_cameras
{
public:
  explicit Init_VisionStatus_active_cameras(::vision_interfaces::msg::VisionStatus & msg)
  : msg_(msg)
  {}
  Init_VisionStatus_missing_cameras active_cameras(::vision_interfaces::msg::VisionStatus::_active_cameras_type arg)
  {
    msg_.active_cameras = std::move(arg);
    return Init_VisionStatus_missing_cameras(msg_);
  }

private:
  ::vision_interfaces::msg::VisionStatus msg_;
};

class Init_VisionStatus_cameras
{
public:
  explicit Init_VisionStatus_cameras(::vision_interfaces::msg::VisionStatus & msg)
  : msg_(msg)
  {}
  Init_VisionStatus_active_cameras cameras(::vision_interfaces::msg::VisionStatus::_cameras_type arg)
  {
    msg_.cameras = std::move(arg);
    return Init_VisionStatus_active_cameras(msg_);
  }

private:
  ::vision_interfaces::msg::VisionStatus msg_;
};

class Init_VisionStatus_model_loaded
{
public:
  explicit Init_VisionStatus_model_loaded(::vision_interfaces::msg::VisionStatus & msg)
  : msg_(msg)
  {}
  Init_VisionStatus_cameras model_loaded(::vision_interfaces::msg::VisionStatus::_model_loaded_type arg)
  {
    msg_.model_loaded = std::move(arg);
    return Init_VisionStatus_cameras(msg_);
  }

private:
  ::vision_interfaces::msg::VisionStatus msg_;
};

class Init_VisionStatus_ready
{
public:
  explicit Init_VisionStatus_ready(::vision_interfaces::msg::VisionStatus & msg)
  : msg_(msg)
  {}
  Init_VisionStatus_model_loaded ready(::vision_interfaces::msg::VisionStatus::_ready_type arg)
  {
    msg_.ready = std::move(arg);
    return Init_VisionStatus_model_loaded(msg_);
  }

private:
  ::vision_interfaces::msg::VisionStatus msg_;
};

class Init_VisionStatus_header
{
public:
  Init_VisionStatus_header()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_VisionStatus_ready header(::vision_interfaces::msg::VisionStatus::_header_type arg)
  {
    msg_.header = std::move(arg);
    return Init_VisionStatus_ready(msg_);
  }

private:
  ::vision_interfaces::msg::VisionStatus msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::vision_interfaces::msg::VisionStatus>()
{
  return vision_interfaces::msg::builder::Init_VisionStatus_header();
}

}  // namespace vision_interfaces

#endif  // VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__BUILDER_HPP_
