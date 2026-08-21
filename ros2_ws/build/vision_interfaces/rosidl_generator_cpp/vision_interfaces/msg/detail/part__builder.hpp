// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from vision_interfaces:msg/Part.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/part.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__PART__BUILDER_HPP_
#define VISION_INTERFACES__MSG__DETAIL__PART__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "vision_interfaces/msg/detail/part__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace vision_interfaces
{

namespace msg
{

namespace builder
{

class Init_Part_position_valid
{
public:
  explicit Init_Part_position_valid(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  ::vision_interfaces::msg::Part position_valid(::vision_interfaces::msg::Part::_position_valid_type arg)
  {
    msg_.position_valid = std::move(arg);
    return std::move(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_camera_z_m
{
public:
  explicit Init_Part_camera_z_m(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_position_valid camera_z_m(::vision_interfaces::msg::Part::_camera_z_m_type arg)
  {
    msg_.camera_z_m = std::move(arg);
    return Init_Part_position_valid(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_camera_y_m
{
public:
  explicit Init_Part_camera_y_m(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_camera_z_m camera_y_m(::vision_interfaces::msg::Part::_camera_y_m_type arg)
  {
    msg_.camera_y_m = std::move(arg);
    return Init_Part_camera_z_m(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_camera_x_m
{
public:
  explicit Init_Part_camera_x_m(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_camera_y_m camera_x_m(::vision_interfaces::msg::Part::_camera_x_m_type arg)
  {
    msg_.camera_x_m = std::move(arg);
    return Init_Part_camera_y_m(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_depth_valid
{
public:
  explicit Init_Part_depth_valid(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_camera_x_m depth_valid(::vision_interfaces::msg::Part::_depth_valid_type arg)
  {
    msg_.depth_valid = std::move(arg);
    return Init_Part_camera_x_m(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_depth_m
{
public:
  explicit Init_Part_depth_m(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_depth_valid depth_m(::vision_interfaces::msg::Part::_depth_m_type arg)
  {
    msg_.depth_m = std::move(arg);
    return Init_Part_depth_valid(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_angle_valid
{
public:
  explicit Init_Part_angle_valid(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_depth_m angle_valid(::vision_interfaces::msg::Part::_angle_valid_type arg)
  {
    msg_.angle_valid = std::move(arg);
    return Init_Part_depth_m(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_angle_deg
{
public:
  explicit Init_Part_angle_deg(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_angle_valid angle_deg(::vision_interfaces::msg::Part::_angle_deg_type arg)
  {
    msg_.angle_deg = std::move(arg);
    return Init_Part_angle_valid(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_height
{
public:
  explicit Init_Part_height(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_angle_deg height(::vision_interfaces::msg::Part::_height_type arg)
  {
    msg_.height = std::move(arg);
    return Init_Part_angle_deg(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_width
{
public:
  explicit Init_Part_width(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_height width(::vision_interfaces::msg::Part::_width_type arg)
  {
    msg_.width = std::move(arg);
    return Init_Part_height(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_y
{
public:
  explicit Init_Part_y(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_width y(::vision_interfaces::msg::Part::_y_type arg)
  {
    msg_.y = std::move(arg);
    return Init_Part_width(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_x
{
public:
  explicit Init_Part_x(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_y x(::vision_interfaces::msg::Part::_x_type arg)
  {
    msg_.x = std::move(arg);
    return Init_Part_y(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_score
{
public:
  explicit Init_Part_score(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_x score(::vision_interfaces::msg::Part::_score_type arg)
  {
    msg_.score = std::move(arg);
    return Init_Part_x(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_class_id
{
public:
  explicit Init_Part_class_id(::vision_interfaces::msg::Part & msg)
  : msg_(msg)
  {}
  Init_Part_score class_id(::vision_interfaces::msg::Part::_class_id_type arg)
  {
    msg_.class_id = std::move(arg);
    return Init_Part_score(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

class Init_Part_name
{
public:
  Init_Part_name()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_Part_class_id name(::vision_interfaces::msg::Part::_name_type arg)
  {
    msg_.name = std::move(arg);
    return Init_Part_class_id(msg_);
  }

private:
  ::vision_interfaces::msg::Part msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::vision_interfaces::msg::Part>()
{
  return vision_interfaces::msg::builder::Init_Part_name();
}

}  // namespace vision_interfaces

#endif  // VISION_INTERFACES__MSG__DETAIL__PART__BUILDER_HPP_
