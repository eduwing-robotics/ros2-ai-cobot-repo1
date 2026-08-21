// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from vision_interfaces:msg/Part.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/part.h"


#ifndef VISION_INTERFACES__MSG__DETAIL__PART__STRUCT_H_
#define VISION_INTERFACES__MSG__DETAIL__PART__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Constants defined in the message

// Include directives for member types
// Member 'name'
#include "rosidl_runtime_c/string.h"

/// Struct defined in msg/Part in the package vision_interfaces.
typedef struct vision_interfaces__msg__Part
{
  rosidl_runtime_c__String name;
  int32_t class_id;
  float score;
  int32_t x;
  int32_t y;
  int32_t width;
  int32_t height;
  float angle_deg;
  bool angle_valid;
  float depth_m;
  bool depth_valid;
  float camera_x_m;
  float camera_y_m;
  float camera_z_m;
  bool position_valid;
} vision_interfaces__msg__Part;

// Struct for a sequence of vision_interfaces__msg__Part.
typedef struct vision_interfaces__msg__Part__Sequence
{
  vision_interfaces__msg__Part * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} vision_interfaces__msg__Part__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // VISION_INTERFACES__MSG__DETAIL__PART__STRUCT_H_
