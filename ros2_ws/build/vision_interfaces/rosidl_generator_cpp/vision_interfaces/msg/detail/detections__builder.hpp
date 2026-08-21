// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from vision_interfaces:msg/Detections.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/detections.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__DETECTIONS__BUILDER_HPP_
#define VISION_INTERFACES__MSG__DETAIL__DETECTIONS__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "vision_interfaces/msg/detail/detections__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace vision_interfaces
{

namespace msg
{

namespace builder
{

class Init_Detections_parts
{
public:
  explicit Init_Detections_parts(::vision_interfaces::msg::Detections & msg)
  : msg_(msg)
  {}
  ::vision_interfaces::msg::Detections parts(::vision_interfaces::msg::Detections::_parts_type arg)
  {
    msg_.parts = std::move(arg);
    return std::move(msg_);
  }

private:
  ::vision_interfaces::msg::Detections msg_;
};

class Init_Detections_image_height
{
public:
  explicit Init_Detections_image_height(::vision_interfaces::msg::Detections & msg)
  : msg_(msg)
  {}
  Init_Detections_parts image_height(::vision_interfaces::msg::Detections::_image_height_type arg)
  {
    msg_.image_height = std::move(arg);
    return Init_Detections_parts(msg_);
  }

private:
  ::vision_interfaces::msg::Detections msg_;
};

class Init_Detections_image_width
{
public:
  explicit Init_Detections_image_width(::vision_interfaces::msg::Detections & msg)
  : msg_(msg)
  {}
  Init_Detections_image_height image_width(::vision_interfaces::msg::Detections::_image_width_type arg)
  {
    msg_.image_width = std::move(arg);
    return Init_Detections_image_height(msg_);
  }

private:
  ::vision_interfaces::msg::Detections msg_;
};

class Init_Detections_camera
{
public:
  explicit Init_Detections_camera(::vision_interfaces::msg::Detections & msg)
  : msg_(msg)
  {}
  Init_Detections_image_width camera(::vision_interfaces::msg::Detections::_camera_type arg)
  {
    msg_.camera = std::move(arg);
    return Init_Detections_image_width(msg_);
  }

private:
  ::vision_interfaces::msg::Detections msg_;
};

class Init_Detections_header
{
public:
  Init_Detections_header()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_Detections_camera header(::vision_interfaces::msg::Detections::_header_type arg)
  {
    msg_.header = std::move(arg);
    return Init_Detections_camera(msg_);
  }

private:
  ::vision_interfaces::msg::Detections msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::vision_interfaces::msg::Detections>()
{
  return vision_interfaces::msg::builder::Init_Detections_header();
}

}  // namespace vision_interfaces

#endif  // VISION_INTERFACES__MSG__DETAIL__DETECTIONS__BUILDER_HPP_
