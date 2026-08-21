// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from vision_interfaces:msg/VisionStatus.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/vision_status.h"


#ifndef VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__STRUCT_H_
#define VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Constants defined in the message

// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__struct.h"
// Member 'cameras'
// Member 'active_cameras'
// Member 'missing_cameras'
// Member 'message'
#include "rosidl_runtime_c/string.h"

/// Struct defined in msg/VisionStatus in the package vision_interfaces.
typedef struct vision_interfaces__msg__VisionStatus
{
  std_msgs__msg__Header header;
  bool ready;
  bool model_loaded;
  rosidl_runtime_c__String__Sequence cameras;
  rosidl_runtime_c__String__Sequence active_cameras;
  rosidl_runtime_c__String__Sequence missing_cameras;
  uint64_t inference_count;
  rosidl_runtime_c__String message;
} vision_interfaces__msg__VisionStatus;

// Struct for a sequence of vision_interfaces__msg__VisionStatus.
typedef struct vision_interfaces__msg__VisionStatus__Sequence
{
  vision_interfaces__msg__VisionStatus * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} vision_interfaces__msg__VisionStatus__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__STRUCT_H_
