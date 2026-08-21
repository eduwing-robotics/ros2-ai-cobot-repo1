// generated from rosidl_typesupport_introspection_cpp/resource/idl__type_support.cpp.em
// with input from vision_interfaces:msg/Detections.idl
// generated code does not contain a copyright notice

#include "array"
#include "cstddef"
#include "string"
#include "vector"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_cpp/message_type_support.hpp"
#include "rosidl_typesupport_interface/macros.h"
#include "vision_interfaces/msg/detail/detections__functions.h"
#include "vision_interfaces/msg/detail/detections__struct.hpp"
#include "rosidl_typesupport_introspection_cpp/field_types.hpp"
#include "rosidl_typesupport_introspection_cpp/identifier.hpp"
#include "rosidl_typesupport_introspection_cpp/message_introspection.hpp"
#include "rosidl_typesupport_introspection_cpp/message_type_support_decl.hpp"
#include "rosidl_typesupport_introspection_cpp/visibility_control.h"

namespace vision_interfaces
{

namespace msg
{

namespace rosidl_typesupport_introspection_cpp
{

void Detections_init_function(
  void * message_memory, rosidl_runtime_cpp::MessageInitialization _init)
{
  new (message_memory) vision_interfaces::msg::Detections(_init);
}

void Detections_fini_function(void * message_memory)
{
  auto typed_message = static_cast<vision_interfaces::msg::Detections *>(message_memory);
  typed_message->~Detections();
}

size_t size_function__Detections__parts(const void * untyped_member)
{
  const auto * member = reinterpret_cast<const std::vector<vision_interfaces::msg::Part> *>(untyped_member);
  return member->size();
}

const void * get_const_function__Detections__parts(const void * untyped_member, size_t index)
{
  const auto & member =
    *reinterpret_cast<const std::vector<vision_interfaces::msg::Part> *>(untyped_member);
  return &member[index];
}

void * get_function__Detections__parts(void * untyped_member, size_t index)
{
  auto & member =
    *reinterpret_cast<std::vector<vision_interfaces::msg::Part> *>(untyped_member);
  return &member[index];
}

void fetch_function__Detections__parts(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const auto & item = *reinterpret_cast<const vision_interfaces::msg::Part *>(
    get_const_function__Detections__parts(untyped_member, index));
  auto & value = *reinterpret_cast<vision_interfaces::msg::Part *>(untyped_value);
  value = item;
}

void assign_function__Detections__parts(
  void * untyped_member, size_t index, const void * untyped_value)
{
  auto & item = *reinterpret_cast<vision_interfaces::msg::Part *>(
    get_function__Detections__parts(untyped_member, index));
  const auto & value = *reinterpret_cast<const vision_interfaces::msg::Part *>(untyped_value);
  item = value;
}

void resize_function__Detections__parts(void * untyped_member, size_t size)
{
  auto * member =
    reinterpret_cast<std::vector<vision_interfaces::msg::Part> *>(untyped_member);
  member->resize(size);
}

static const ::rosidl_typesupport_introspection_cpp::MessageMember Detections_message_member_array[5] = {
  {
    "header",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    ::rosidl_typesupport_introspection_cpp::get_message_type_support_handle<std_msgs::msg::Header>(),  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces::msg::Detections, header),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "camera",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces::msg::Detections, camera),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "image_width",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_UINT32,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces::msg::Detections, image_width),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "image_height",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_UINT32,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces::msg::Detections, image_height),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "parts",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    ::rosidl_typesupport_introspection_cpp::get_message_type_support_handle<vision_interfaces::msg::Part>(),  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces::msg::Detections, parts),  // bytes offset in struct
    nullptr,  // default value
    size_function__Detections__parts,  // size() function pointer
    get_const_function__Detections__parts,  // get_const(index) function pointer
    get_function__Detections__parts,  // get(index) function pointer
    fetch_function__Detections__parts,  // fetch(index, &value) function pointer
    assign_function__Detections__parts,  // assign(index, value) function pointer
    resize_function__Detections__parts  // resize(index) function pointer
  }
};

static const ::rosidl_typesupport_introspection_cpp::MessageMembers Detections_message_members = {
  "vision_interfaces::msg",  // message namespace
  "Detections",  // message name
  5,  // number of fields
  sizeof(vision_interfaces::msg::Detections),
  false,  // has_any_key_member_
  Detections_message_member_array,  // message members
  Detections_init_function,  // function to initialize message memory (memory has to be allocated)
  Detections_fini_function  // function to terminate message instance (will not free memory)
};

static const rosidl_message_type_support_t Detections_message_type_support_handle = {
  ::rosidl_typesupport_introspection_cpp::typesupport_identifier,
  &Detections_message_members,
  get_message_typesupport_handle_function,
  &vision_interfaces__msg__Detections__get_type_hash,
  &vision_interfaces__msg__Detections__get_type_description,
  &vision_interfaces__msg__Detections__get_type_description_sources,
};

}  // namespace rosidl_typesupport_introspection_cpp

}  // namespace msg

}  // namespace vision_interfaces


namespace rosidl_typesupport_introspection_cpp
{

template<>
ROSIDL_TYPESUPPORT_INTROSPECTION_CPP_PUBLIC
const rosidl_message_type_support_t *
get_message_type_support_handle<vision_interfaces::msg::Detections>()
{
  return &::vision_interfaces::msg::rosidl_typesupport_introspection_cpp::Detections_message_type_support_handle;
}

}  // namespace rosidl_typesupport_introspection_cpp

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_INTROSPECTION_CPP_PUBLIC
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_cpp, vision_interfaces, msg, Detections)() {
  return &::vision_interfaces::msg::rosidl_typesupport_introspection_cpp::Detections_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif
