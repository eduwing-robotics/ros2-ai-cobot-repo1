// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from vision_interfaces:msg/Inspection.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/inspection.h"


#ifndef VISION_INTERFACES__MSG__DETAIL__INSPECTION__STRUCT_H_
#define VISION_INTERFACES__MSG__DETAIL__INSPECTION__STRUCT_H_

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
// Member 'board_id'
// Member 'recipe_id'
// Member 'status'
// Member 'names'
// Member 'slot_ids'
// Member 'slot_status'
// Member 'errors'
#include "rosidl_runtime_c/string.h"
// Member 'expected'
// Member 'found'
#include "rosidl_runtime_c/primitives_sequence.h"

/// Struct defined in msg/Inspection in the package vision_interfaces.
typedef struct vision_interfaces__msg__Inspection
{
  std_msgs__msg__Header header;
  rosidl_runtime_c__String camera;
  rosidl_runtime_c__String board_id;
  rosidl_runtime_c__String recipe_id;
  rosidl_runtime_c__String status;
  int32_t expected_total;
  int32_t found_total;
  rosidl_runtime_c__String__Sequence names;
  rosidl_runtime_c__int32__Sequence expected;
  rosidl_runtime_c__int32__Sequence found;
  rosidl_runtime_c__String__Sequence slot_ids;
  rosidl_runtime_c__String__Sequence slot_status;
  rosidl_runtime_c__String__Sequence errors;
} vision_interfaces__msg__Inspection;

// Struct for a sequence of vision_interfaces__msg__Inspection.
typedef struct vision_interfaces__msg__Inspection__Sequence
{
  vision_interfaces__msg__Inspection * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} vision_interfaces__msg__Inspection__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // VISION_INTERFACES__MSG__DETAIL__INSPECTION__STRUCT_H_
