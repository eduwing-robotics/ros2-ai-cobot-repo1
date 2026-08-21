// generated from rosidl_typesupport_fastrtps_c/resource/idl__rosidl_typesupport_fastrtps_c.h.em
// with input from vision_interfaces:msg/VisionStatus.idl
// generated code does not contain a copyright notice
#ifndef VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_
#define VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_


#include <stddef.h>
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_interface/macros.h"
#include "vision_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "vision_interfaces/msg/detail/vision_status__struct.h"
#include "fastcdr/Cdr.h"

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_vision_interfaces
bool cdr_serialize_vision_interfaces__msg__VisionStatus(
  const vision_interfaces__msg__VisionStatus * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_vision_interfaces
bool cdr_deserialize_vision_interfaces__msg__VisionStatus(
  eprosima::fastcdr::Cdr &,
  vision_interfaces__msg__VisionStatus * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_vision_interfaces
size_t get_serialized_size_vision_interfaces__msg__VisionStatus(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_vision_interfaces
size_t max_serialized_size_vision_interfaces__msg__VisionStatus(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_vision_interfaces
bool cdr_serialize_key_vision_interfaces__msg__VisionStatus(
  const vision_interfaces__msg__VisionStatus * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_vision_interfaces
size_t get_serialized_size_key_vision_interfaces__msg__VisionStatus(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_vision_interfaces
size_t max_serialized_size_key_vision_interfaces__msg__VisionStatus(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_vision_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, vision_interfaces, msg, VisionStatus)();

#ifdef __cplusplus
}
#endif

#endif  // VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_
