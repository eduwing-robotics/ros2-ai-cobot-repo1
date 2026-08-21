// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from vision_interfaces:msg/Detections.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/detections.h"


#ifndef VISION_INTERFACES__MSG__DETAIL__DETECTIONS__STRUCT_H_
#define VISION_INTERFACES__MSG__DETAIL__DETECTIONS__STRUCT_H_

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
// Member 'camera'
#include "rosidl_runtime_c/string.h"
// Member 'parts'
#include "vision_interfaces/msg/detail/part__struct.h"

/// Struct defined in msg/Detections in the package vision_interfaces.
typedef struct vision_interfaces__msg__Detections
{
  std_msgs__msg__Header header;
  rosidl_runtime_c__String camera;
  uint32_t image_width;
  uint32_t image_height;
  vision_interfaces__msg__Part__Sequence parts;
} vision_interfaces__msg__Detections;

// Struct for a sequence of vision_interfaces__msg__Detections.
typedef struct vision_interfaces__msg__Detections__Sequence
{
  vision_interfaces__msg__Detections * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} vision_interfaces__msg__Detections__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // VISION_INTERFACES__MSG__DETAIL__DETECTIONS__STRUCT_H_
