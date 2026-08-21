// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from vision_interfaces:msg/VisionStatus.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "vision_interfaces/msg/detail/vision_status__rosidl_typesupport_introspection_c.h"
#include "vision_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "vision_interfaces/msg/detail/vision_status__functions.h"
#include "vision_interfaces/msg/detail/vision_status__struct.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/header.h"
// Member `header`
#include "std_msgs/msg/detail/header__rosidl_typesupport_introspection_c.h"
// Member `cameras`
// Member `active_cameras`
// Member `missing_cameras`
// Member `message`
#include "rosidl_runtime_c/string_functions.h"

#ifdef __cplusplus
extern "C"
{
#endif

void vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  vision_interfaces__msg__VisionStatus__init(message_memory);
}

void vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_fini_function(void * message_memory)
{
  vision_interfaces__msg__VisionStatus__fini(message_memory);
}

size_t vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__size_function__VisionStatus__cameras(
  const void * untyped_member)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__cameras(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__cameras(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__fetch_function__VisionStatus__cameras(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const rosidl_runtime_c__String * item =
    ((const rosidl_runtime_c__String *)
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__cameras(untyped_member, index));
  rosidl_runtime_c__String * value =
    (rosidl_runtime_c__String *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__assign_function__VisionStatus__cameras(
  void * untyped_member, size_t index, const void * untyped_value)
{
  rosidl_runtime_c__String * item =
    ((rosidl_runtime_c__String *)
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__cameras(untyped_member, index));
  const rosidl_runtime_c__String * value =
    (const rosidl_runtime_c__String *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__resize_function__VisionStatus__cameras(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  rosidl_runtime_c__String__Sequence__fini(member);
  return rosidl_runtime_c__String__Sequence__init(member, size);
}

size_t vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__size_function__VisionStatus__active_cameras(
  const void * untyped_member)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__active_cameras(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__active_cameras(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__fetch_function__VisionStatus__active_cameras(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const rosidl_runtime_c__String * item =
    ((const rosidl_runtime_c__String *)
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__active_cameras(untyped_member, index));
  rosidl_runtime_c__String * value =
    (rosidl_runtime_c__String *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__assign_function__VisionStatus__active_cameras(
  void * untyped_member, size_t index, const void * untyped_value)
{
  rosidl_runtime_c__String * item =
    ((rosidl_runtime_c__String *)
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__active_cameras(untyped_member, index));
  const rosidl_runtime_c__String * value =
    (const rosidl_runtime_c__String *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__resize_function__VisionStatus__active_cameras(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  rosidl_runtime_c__String__Sequence__fini(member);
  return rosidl_runtime_c__String__Sequence__init(member, size);
}

size_t vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__size_function__VisionStatus__missing_cameras(
  const void * untyped_member)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__missing_cameras(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__missing_cameras(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__fetch_function__VisionStatus__missing_cameras(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const rosidl_runtime_c__String * item =
    ((const rosidl_runtime_c__String *)
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__missing_cameras(untyped_member, index));
  rosidl_runtime_c__String * value =
    (rosidl_runtime_c__String *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__assign_function__VisionStatus__missing_cameras(
  void * untyped_member, size_t index, const void * untyped_value)
{
  rosidl_runtime_c__String * item =
    ((rosidl_runtime_c__String *)
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__missing_cameras(untyped_member, index));
  const rosidl_runtime_c__String * value =
    (const rosidl_runtime_c__String *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__resize_function__VisionStatus__missing_cameras(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  rosidl_runtime_c__String__Sequence__fini(member);
  return rosidl_runtime_c__String__Sequence__init(member, size);
}

static rosidl_typesupport_introspection_c__MessageMember vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_member_array[8] = {
  {
    "header",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__VisionStatus, header),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "ready",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__VisionStatus, ready),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "model_loaded",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__VisionStatus, model_loaded),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "cameras",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__VisionStatus, cameras),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__size_function__VisionStatus__cameras,  // size() function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__cameras,  // get_const(index) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__cameras,  // get(index) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__fetch_function__VisionStatus__cameras,  // fetch(index, &value) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__assign_function__VisionStatus__cameras,  // assign(index, value) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__resize_function__VisionStatus__cameras  // resize(index) function pointer
  },
  {
    "active_cameras",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__VisionStatus, active_cameras),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__size_function__VisionStatus__active_cameras,  // size() function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__active_cameras,  // get_const(index) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__active_cameras,  // get(index) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__fetch_function__VisionStatus__active_cameras,  // fetch(index, &value) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__assign_function__VisionStatus__active_cameras,  // assign(index, value) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__resize_function__VisionStatus__active_cameras  // resize(index) function pointer
  },
  {
    "missing_cameras",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__VisionStatus, missing_cameras),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__size_function__VisionStatus__missing_cameras,  // size() function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_const_function__VisionStatus__missing_cameras,  // get_const(index) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__get_function__VisionStatus__missing_cameras,  // get(index) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__fetch_function__VisionStatus__missing_cameras,  // fetch(index, &value) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__assign_function__VisionStatus__missing_cameras,  // assign(index, value) function pointer
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__resize_function__VisionStatus__missing_cameras  // resize(index) function pointer
  },
  {
    "inference_count",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_UINT64,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__VisionStatus, inference_count),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "message",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__VisionStatus, message),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_members = {
  "vision_interfaces__msg",  // message namespace
  "VisionStatus",  // message name
  8,  // number of fields
  sizeof(vision_interfaces__msg__VisionStatus),
  false,  // has_any_key_member_
  vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_member_array,  // message members
  vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_init_function,  // function to initialize message memory (memory has to be allocated)
  vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_type_support_handle = {
  0,
  &vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_members,
  get_message_typesupport_handle_function,
  &vision_interfaces__msg__VisionStatus__get_type_hash,
  &vision_interfaces__msg__VisionStatus__get_type_description,
  &vision_interfaces__msg__VisionStatus__get_type_description_sources,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_vision_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, vision_interfaces, msg, VisionStatus)() {
  vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, std_msgs, msg, Header)();
  if (!vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_type_support_handle.typesupport_identifier) {
    vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &vision_interfaces__msg__VisionStatus__rosidl_typesupport_introspection_c__VisionStatus_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
