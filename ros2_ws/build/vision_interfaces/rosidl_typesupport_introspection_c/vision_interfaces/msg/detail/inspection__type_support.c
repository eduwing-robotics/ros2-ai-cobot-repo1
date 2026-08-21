// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from vision_interfaces:msg/Inspection.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "vision_interfaces/msg/detail/inspection__rosidl_typesupport_introspection_c.h"
#include "vision_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "vision_interfaces/msg/detail/inspection__functions.h"
#include "vision_interfaces/msg/detail/inspection__struct.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/header.h"
// Member `header`
#include "std_msgs/msg/detail/header__rosidl_typesupport_introspection_c.h"
// Member `camera`
// Member `board_id`
// Member `recipe_id`
// Member `status`
// Member `names`
// Member `slot_ids`
// Member `slot_status`
// Member `errors`
#include "rosidl_runtime_c/string_functions.h"
// Member `expected`
// Member `found`
#include "rosidl_runtime_c/primitives_sequence_functions.h"

#ifdef __cplusplus
extern "C"
{
#endif

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  vision_interfaces__msg__Inspection__init(message_memory);
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_fini_function(void * message_memory)
{
  vision_interfaces__msg__Inspection__fini(message_memory);
}

size_t vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__names(
  const void * untyped_member)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__names(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__names(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__names(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const rosidl_runtime_c__String * item =
    ((const rosidl_runtime_c__String *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__names(untyped_member, index));
  rosidl_runtime_c__String * value =
    (rosidl_runtime_c__String *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__names(
  void * untyped_member, size_t index, const void * untyped_value)
{
  rosidl_runtime_c__String * item =
    ((rosidl_runtime_c__String *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__names(untyped_member, index));
  const rosidl_runtime_c__String * value =
    (const rosidl_runtime_c__String *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__names(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  rosidl_runtime_c__String__Sequence__fini(member);
  return rosidl_runtime_c__String__Sequence__init(member, size);
}

size_t vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__expected(
  const void * untyped_member)
{
  const rosidl_runtime_c__int32__Sequence * member =
    (const rosidl_runtime_c__int32__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__expected(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__int32__Sequence * member =
    (const rosidl_runtime_c__int32__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__expected(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__int32__Sequence * member =
    (rosidl_runtime_c__int32__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__expected(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const int32_t * item =
    ((const int32_t *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__expected(untyped_member, index));
  int32_t * value =
    (int32_t *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__expected(
  void * untyped_member, size_t index, const void * untyped_value)
{
  int32_t * item =
    ((int32_t *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__expected(untyped_member, index));
  const int32_t * value =
    (const int32_t *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__expected(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__int32__Sequence * member =
    (rosidl_runtime_c__int32__Sequence *)(untyped_member);
  rosidl_runtime_c__int32__Sequence__fini(member);
  return rosidl_runtime_c__int32__Sequence__init(member, size);
}

size_t vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__found(
  const void * untyped_member)
{
  const rosidl_runtime_c__int32__Sequence * member =
    (const rosidl_runtime_c__int32__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__found(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__int32__Sequence * member =
    (const rosidl_runtime_c__int32__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__found(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__int32__Sequence * member =
    (rosidl_runtime_c__int32__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__found(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const int32_t * item =
    ((const int32_t *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__found(untyped_member, index));
  int32_t * value =
    (int32_t *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__found(
  void * untyped_member, size_t index, const void * untyped_value)
{
  int32_t * item =
    ((int32_t *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__found(untyped_member, index));
  const int32_t * value =
    (const int32_t *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__found(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__int32__Sequence * member =
    (rosidl_runtime_c__int32__Sequence *)(untyped_member);
  rosidl_runtime_c__int32__Sequence__fini(member);
  return rosidl_runtime_c__int32__Sequence__init(member, size);
}

size_t vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__slot_ids(
  const void * untyped_member)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__slot_ids(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__slot_ids(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__slot_ids(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const rosidl_runtime_c__String * item =
    ((const rosidl_runtime_c__String *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__slot_ids(untyped_member, index));
  rosidl_runtime_c__String * value =
    (rosidl_runtime_c__String *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__slot_ids(
  void * untyped_member, size_t index, const void * untyped_value)
{
  rosidl_runtime_c__String * item =
    ((rosidl_runtime_c__String *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__slot_ids(untyped_member, index));
  const rosidl_runtime_c__String * value =
    (const rosidl_runtime_c__String *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__slot_ids(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  rosidl_runtime_c__String__Sequence__fini(member);
  return rosidl_runtime_c__String__Sequence__init(member, size);
}

size_t vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__slot_status(
  const void * untyped_member)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__slot_status(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__slot_status(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__slot_status(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const rosidl_runtime_c__String * item =
    ((const rosidl_runtime_c__String *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__slot_status(untyped_member, index));
  rosidl_runtime_c__String * value =
    (rosidl_runtime_c__String *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__slot_status(
  void * untyped_member, size_t index, const void * untyped_value)
{
  rosidl_runtime_c__String * item =
    ((rosidl_runtime_c__String *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__slot_status(untyped_member, index));
  const rosidl_runtime_c__String * value =
    (const rosidl_runtime_c__String *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__slot_status(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  rosidl_runtime_c__String__Sequence__fini(member);
  return rosidl_runtime_c__String__Sequence__init(member, size);
}

size_t vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__errors(
  const void * untyped_member)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__errors(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__errors(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__errors(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const rosidl_runtime_c__String * item =
    ((const rosidl_runtime_c__String *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__errors(untyped_member, index));
  rosidl_runtime_c__String * value =
    (rosidl_runtime_c__String *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__errors(
  void * untyped_member, size_t index, const void * untyped_value)
{
  rosidl_runtime_c__String * item =
    ((rosidl_runtime_c__String *)
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__errors(untyped_member, index));
  const rosidl_runtime_c__String * value =
    (const rosidl_runtime_c__String *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__errors(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  rosidl_runtime_c__String__Sequence__fini(member);
  return rosidl_runtime_c__String__Sequence__init(member, size);
}

static rosidl_typesupport_introspection_c__MessageMember vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_member_array[13] = {
  {
    "header",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, header),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "camera",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, camera),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "board_id",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, board_id),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "recipe_id",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, recipe_id),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "status",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, status),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "expected_total",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_INT32,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, expected_total),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "found_total",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_INT32,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, found_total),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "names",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, names),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__names,  // size() function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__names,  // get_const(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__names,  // get(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__names,  // fetch(index, &value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__names,  // assign(index, value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__names  // resize(index) function pointer
  },
  {
    "expected",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_INT32,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, expected),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__expected,  // size() function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__expected,  // get_const(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__expected,  // get(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__expected,  // fetch(index, &value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__expected,  // assign(index, value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__expected  // resize(index) function pointer
  },
  {
    "found",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_INT32,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, found),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__found,  // size() function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__found,  // get_const(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__found,  // get(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__found,  // fetch(index, &value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__found,  // assign(index, value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__found  // resize(index) function pointer
  },
  {
    "slot_ids",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, slot_ids),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__slot_ids,  // size() function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__slot_ids,  // get_const(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__slot_ids,  // get(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__slot_ids,  // fetch(index, &value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__slot_ids,  // assign(index, value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__slot_ids  // resize(index) function pointer
  },
  {
    "slot_status",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, slot_status),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__slot_status,  // size() function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__slot_status,  // get_const(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__slot_status,  // get(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__slot_status,  // fetch(index, &value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__slot_status,  // assign(index, value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__slot_status  // resize(index) function pointer
  },
  {
    "errors",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Inspection, errors),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__size_function__Inspection__errors,  // size() function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_const_function__Inspection__errors,  // get_const(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__get_function__Inspection__errors,  // get(index) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__fetch_function__Inspection__errors,  // fetch(index, &value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__assign_function__Inspection__errors,  // assign(index, value) function pointer
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__resize_function__Inspection__errors  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_members = {
  "vision_interfaces__msg",  // message namespace
  "Inspection",  // message name
  13,  // number of fields
  sizeof(vision_interfaces__msg__Inspection),
  false,  // has_any_key_member_
  vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_member_array,  // message members
  vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_init_function,  // function to initialize message memory (memory has to be allocated)
  vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_type_support_handle = {
  0,
  &vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_members,
  get_message_typesupport_handle_function,
  &vision_interfaces__msg__Inspection__get_type_hash,
  &vision_interfaces__msg__Inspection__get_type_description,
  &vision_interfaces__msg__Inspection__get_type_description_sources,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_vision_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, vision_interfaces, msg, Inspection)() {
  vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, std_msgs, msg, Header)();
  if (!vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_type_support_handle.typesupport_identifier) {
    vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &vision_interfaces__msg__Inspection__rosidl_typesupport_introspection_c__Inspection_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
