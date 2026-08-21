// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from vision_interfaces:msg/Detections.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "vision_interfaces/msg/detail/detections__rosidl_typesupport_introspection_c.h"
#include "vision_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "vision_interfaces/msg/detail/detections__functions.h"
#include "vision_interfaces/msg/detail/detections__struct.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/header.h"
// Member `header`
#include "std_msgs/msg/detail/header__rosidl_typesupport_introspection_c.h"
// Member `camera`
#include "rosidl_runtime_c/string_functions.h"
// Member `parts`
#include "vision_interfaces/msg/part.h"
// Member `parts`
#include "vision_interfaces/msg/detail/part__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  vision_interfaces__msg__Detections__init(message_memory);
}

void vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_fini_function(void * message_memory)
{
  vision_interfaces__msg__Detections__fini(message_memory);
}

size_t vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__size_function__Detections__parts(
  const void * untyped_member)
{
  const vision_interfaces__msg__Part__Sequence * member =
    (const vision_interfaces__msg__Part__Sequence *)(untyped_member);
  return member->size;
}

const void * vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__get_const_function__Detections__parts(
  const void * untyped_member, size_t index)
{
  const vision_interfaces__msg__Part__Sequence * member =
    (const vision_interfaces__msg__Part__Sequence *)(untyped_member);
  return &member->data[index];
}

void * vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__get_function__Detections__parts(
  void * untyped_member, size_t index)
{
  vision_interfaces__msg__Part__Sequence * member =
    (vision_interfaces__msg__Part__Sequence *)(untyped_member);
  return &member->data[index];
}

void vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__fetch_function__Detections__parts(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const vision_interfaces__msg__Part * item =
    ((const vision_interfaces__msg__Part *)
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__get_const_function__Detections__parts(untyped_member, index));
  vision_interfaces__msg__Part * value =
    (vision_interfaces__msg__Part *)(untyped_value);
  *value = *item;
}

void vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__assign_function__Detections__parts(
  void * untyped_member, size_t index, const void * untyped_value)
{
  vision_interfaces__msg__Part * item =
    ((vision_interfaces__msg__Part *)
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__get_function__Detections__parts(untyped_member, index));
  const vision_interfaces__msg__Part * value =
    (const vision_interfaces__msg__Part *)(untyped_value);
  *item = *value;
}

bool vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__resize_function__Detections__parts(
  void * untyped_member, size_t size)
{
  vision_interfaces__msg__Part__Sequence * member =
    (vision_interfaces__msg__Part__Sequence *)(untyped_member);
  vision_interfaces__msg__Part__Sequence__fini(member);
  return vision_interfaces__msg__Part__Sequence__init(member, size);
}

static rosidl_typesupport_introspection_c__MessageMember vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_member_array[5] = {
  {
    "header",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Detections, header),  // bytes offset in struct
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
    offsetof(vision_interfaces__msg__Detections, camera),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "image_width",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_UINT32,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Detections, image_width),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "image_height",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_UINT32,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Detections, image_height),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "parts",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(vision_interfaces__msg__Detections, parts),  // bytes offset in struct
    NULL,  // default value
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__size_function__Detections__parts,  // size() function pointer
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__get_const_function__Detections__parts,  // get_const(index) function pointer
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__get_function__Detections__parts,  // get(index) function pointer
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__fetch_function__Detections__parts,  // fetch(index, &value) function pointer
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__assign_function__Detections__parts,  // assign(index, value) function pointer
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__resize_function__Detections__parts  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_members = {
  "vision_interfaces__msg",  // message namespace
  "Detections",  // message name
  5,  // number of fields
  sizeof(vision_interfaces__msg__Detections),
  false,  // has_any_key_member_
  vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_member_array,  // message members
  vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_init_function,  // function to initialize message memory (memory has to be allocated)
  vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_type_support_handle = {
  0,
  &vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_members,
  get_message_typesupport_handle_function,
  &vision_interfaces__msg__Detections__get_type_hash,
  &vision_interfaces__msg__Detections__get_type_description,
  &vision_interfaces__msg__Detections__get_type_description_sources,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_vision_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, vision_interfaces, msg, Detections)() {
  vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, std_msgs, msg, Header)();
  vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_member_array[4].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, vision_interfaces, msg, Part)();
  if (!vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_type_support_handle.typesupport_identifier) {
    vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &vision_interfaces__msg__Detections__rosidl_typesupport_introspection_c__Detections_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
