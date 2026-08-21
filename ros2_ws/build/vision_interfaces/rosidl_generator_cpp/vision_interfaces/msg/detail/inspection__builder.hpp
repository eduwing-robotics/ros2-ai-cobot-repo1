// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from vision_interfaces:msg/Inspection.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/inspection.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__INSPECTION__BUILDER_HPP_
#define VISION_INTERFACES__MSG__DETAIL__INSPECTION__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "vision_interfaces/msg/detail/inspection__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace vision_interfaces
{

namespace msg
{

namespace builder
{

class Init_Inspection_errors
{
public:
  explicit Init_Inspection_errors(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  ::vision_interfaces::msg::Inspection errors(::vision_interfaces::msg::Inspection::_errors_type arg)
  {
    msg_.errors = std::move(arg);
    return std::move(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_slot_status
{
public:
  explicit Init_Inspection_slot_status(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_errors slot_status(::vision_interfaces::msg::Inspection::_slot_status_type arg)
  {
    msg_.slot_status = std::move(arg);
    return Init_Inspection_errors(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_slot_ids
{
public:
  explicit Init_Inspection_slot_ids(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_slot_status slot_ids(::vision_interfaces::msg::Inspection::_slot_ids_type arg)
  {
    msg_.slot_ids = std::move(arg);
    return Init_Inspection_slot_status(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_found
{
public:
  explicit Init_Inspection_found(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_slot_ids found(::vision_interfaces::msg::Inspection::_found_type arg)
  {
    msg_.found = std::move(arg);
    return Init_Inspection_slot_ids(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_expected
{
public:
  explicit Init_Inspection_expected(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_found expected(::vision_interfaces::msg::Inspection::_expected_type arg)
  {
    msg_.expected = std::move(arg);
    return Init_Inspection_found(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_names
{
public:
  explicit Init_Inspection_names(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_expected names(::vision_interfaces::msg::Inspection::_names_type arg)
  {
    msg_.names = std::move(arg);
    return Init_Inspection_expected(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_found_total
{
public:
  explicit Init_Inspection_found_total(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_names found_total(::vision_interfaces::msg::Inspection::_found_total_type arg)
  {
    msg_.found_total = std::move(arg);
    return Init_Inspection_names(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_expected_total
{
public:
  explicit Init_Inspection_expected_total(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_found_total expected_total(::vision_interfaces::msg::Inspection::_expected_total_type arg)
  {
    msg_.expected_total = std::move(arg);
    return Init_Inspection_found_total(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_status
{
public:
  explicit Init_Inspection_status(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_expected_total status(::vision_interfaces::msg::Inspection::_status_type arg)
  {
    msg_.status = std::move(arg);
    return Init_Inspection_expected_total(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_recipe_id
{
public:
  explicit Init_Inspection_recipe_id(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_status recipe_id(::vision_interfaces::msg::Inspection::_recipe_id_type arg)
  {
    msg_.recipe_id = std::move(arg);
    return Init_Inspection_status(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_board_id
{
public:
  explicit Init_Inspection_board_id(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_recipe_id board_id(::vision_interfaces::msg::Inspection::_board_id_type arg)
  {
    msg_.board_id = std::move(arg);
    return Init_Inspection_recipe_id(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_camera
{
public:
  explicit Init_Inspection_camera(::vision_interfaces::msg::Inspection & msg)
  : msg_(msg)
  {}
  Init_Inspection_board_id camera(::vision_interfaces::msg::Inspection::_camera_type arg)
  {
    msg_.camera = std::move(arg);
    return Init_Inspection_board_id(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

class Init_Inspection_header
{
public:
  Init_Inspection_header()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_Inspection_camera header(::vision_interfaces::msg::Inspection::_header_type arg)
  {
    msg_.header = std::move(arg);
    return Init_Inspection_camera(msg_);
  }

private:
  ::vision_interfaces::msg::Inspection msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::vision_interfaces::msg::Inspection>()
{
  return vision_interfaces::msg::builder::Init_Inspection_header();
}

}  // namespace vision_interfaces

#endif  // VISION_INTERFACES__MSG__DETAIL__INSPECTION__BUILDER_HPP_
