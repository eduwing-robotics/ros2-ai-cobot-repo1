// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from vision_interfaces:msg/Inspection.idl
// generated code does not contain a copyright notice
#include "vision_interfaces/msg/detail/inspection__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/detail/header__functions.h"
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

bool
vision_interfaces__msg__Inspection__init(vision_interfaces__msg__Inspection * msg)
{
  if (!msg) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__init(&msg->header)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // camera
  if (!rosidl_runtime_c__String__init(&msg->camera)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // board_id
  if (!rosidl_runtime_c__String__init(&msg->board_id)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // recipe_id
  if (!rosidl_runtime_c__String__init(&msg->recipe_id)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // status
  if (!rosidl_runtime_c__String__init(&msg->status)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // expected_total
  // found_total
  // names
  if (!rosidl_runtime_c__String__Sequence__init(&msg->names, 0)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // expected
  if (!rosidl_runtime_c__int32__Sequence__init(&msg->expected, 0)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // found
  if (!rosidl_runtime_c__int32__Sequence__init(&msg->found, 0)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // slot_ids
  if (!rosidl_runtime_c__String__Sequence__init(&msg->slot_ids, 0)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // slot_status
  if (!rosidl_runtime_c__String__Sequence__init(&msg->slot_status, 0)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  // errors
  if (!rosidl_runtime_c__String__Sequence__init(&msg->errors, 0)) {
    vision_interfaces__msg__Inspection__fini(msg);
    return false;
  }
  return true;
}

void
vision_interfaces__msg__Inspection__fini(vision_interfaces__msg__Inspection * msg)
{
  if (!msg) {
    return;
  }
  // header
  std_msgs__msg__Header__fini(&msg->header);
  // camera
  rosidl_runtime_c__String__fini(&msg->camera);
  // board_id
  rosidl_runtime_c__String__fini(&msg->board_id);
  // recipe_id
  rosidl_runtime_c__String__fini(&msg->recipe_id);
  // status
  rosidl_runtime_c__String__fini(&msg->status);
  // expected_total
  // found_total
  // names
  rosidl_runtime_c__String__Sequence__fini(&msg->names);
  // expected
  rosidl_runtime_c__int32__Sequence__fini(&msg->expected);
  // found
  rosidl_runtime_c__int32__Sequence__fini(&msg->found);
  // slot_ids
  rosidl_runtime_c__String__Sequence__fini(&msg->slot_ids);
  // slot_status
  rosidl_runtime_c__String__Sequence__fini(&msg->slot_status);
  // errors
  rosidl_runtime_c__String__Sequence__fini(&msg->errors);
}

bool
vision_interfaces__msg__Inspection__are_equal(const vision_interfaces__msg__Inspection * lhs, const vision_interfaces__msg__Inspection * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__are_equal(
      &(lhs->header), &(rhs->header)))
  {
    return false;
  }
  // camera
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->camera), &(rhs->camera)))
  {
    return false;
  }
  // board_id
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->board_id), &(rhs->board_id)))
  {
    return false;
  }
  // recipe_id
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->recipe_id), &(rhs->recipe_id)))
  {
    return false;
  }
  // status
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->status), &(rhs->status)))
  {
    return false;
  }
  // expected_total
  if (lhs->expected_total != rhs->expected_total) {
    return false;
  }
  // found_total
  if (lhs->found_total != rhs->found_total) {
    return false;
  }
  // names
  if (!rosidl_runtime_c__String__Sequence__are_equal(
      &(lhs->names), &(rhs->names)))
  {
    return false;
  }
  // expected
  if (!rosidl_runtime_c__int32__Sequence__are_equal(
      &(lhs->expected), &(rhs->expected)))
  {
    return false;
  }
  // found
  if (!rosidl_runtime_c__int32__Sequence__are_equal(
      &(lhs->found), &(rhs->found)))
  {
    return false;
  }
  // slot_ids
  if (!rosidl_runtime_c__String__Sequence__are_equal(
      &(lhs->slot_ids), &(rhs->slot_ids)))
  {
    return false;
  }
  // slot_status
  if (!rosidl_runtime_c__String__Sequence__are_equal(
      &(lhs->slot_status), &(rhs->slot_status)))
  {
    return false;
  }
  // errors
  if (!rosidl_runtime_c__String__Sequence__are_equal(
      &(lhs->errors), &(rhs->errors)))
  {
    return false;
  }
  return true;
}

bool
vision_interfaces__msg__Inspection__copy(
  const vision_interfaces__msg__Inspection * input,
  vision_interfaces__msg__Inspection * output)
{
  if (!input || !output) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__copy(
      &(input->header), &(output->header)))
  {
    return false;
  }
  // camera
  if (!rosidl_runtime_c__String__copy(
      &(input->camera), &(output->camera)))
  {
    return false;
  }
  // board_id
  if (!rosidl_runtime_c__String__copy(
      &(input->board_id), &(output->board_id)))
  {
    return false;
  }
  // recipe_id
  if (!rosidl_runtime_c__String__copy(
      &(input->recipe_id), &(output->recipe_id)))
  {
    return false;
  }
  // status
  if (!rosidl_runtime_c__String__copy(
      &(input->status), &(output->status)))
  {
    return false;
  }
  // expected_total
  output->expected_total = input->expected_total;
  // found_total
  output->found_total = input->found_total;
  // names
  if (!rosidl_runtime_c__String__Sequence__copy(
      &(input->names), &(output->names)))
  {
    return false;
  }
  // expected
  if (!rosidl_runtime_c__int32__Sequence__copy(
      &(input->expected), &(output->expected)))
  {
    return false;
  }
  // found
  if (!rosidl_runtime_c__int32__Sequence__copy(
      &(input->found), &(output->found)))
  {
    return false;
  }
  // slot_ids
  if (!rosidl_runtime_c__String__Sequence__copy(
      &(input->slot_ids), &(output->slot_ids)))
  {
    return false;
  }
  // slot_status
  if (!rosidl_runtime_c__String__Sequence__copy(
      &(input->slot_status), &(output->slot_status)))
  {
    return false;
  }
  // errors
  if (!rosidl_runtime_c__String__Sequence__copy(
      &(input->errors), &(output->errors)))
  {
    return false;
  }
  return true;
}

vision_interfaces__msg__Inspection *
vision_interfaces__msg__Inspection__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__Inspection * msg = (vision_interfaces__msg__Inspection *)allocator.allocate(sizeof(vision_interfaces__msg__Inspection), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(vision_interfaces__msg__Inspection));
  bool success = vision_interfaces__msg__Inspection__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
vision_interfaces__msg__Inspection__destroy(vision_interfaces__msg__Inspection * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    vision_interfaces__msg__Inspection__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
vision_interfaces__msg__Inspection__Sequence__init(vision_interfaces__msg__Inspection__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__Inspection * data = NULL;

  if (size) {
    data = (vision_interfaces__msg__Inspection *)allocator.zero_allocate(size, sizeof(vision_interfaces__msg__Inspection), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = vision_interfaces__msg__Inspection__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        vision_interfaces__msg__Inspection__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
vision_interfaces__msg__Inspection__Sequence__fini(vision_interfaces__msg__Inspection__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      vision_interfaces__msg__Inspection__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

vision_interfaces__msg__Inspection__Sequence *
vision_interfaces__msg__Inspection__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__Inspection__Sequence * array = (vision_interfaces__msg__Inspection__Sequence *)allocator.allocate(sizeof(vision_interfaces__msg__Inspection__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = vision_interfaces__msg__Inspection__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
vision_interfaces__msg__Inspection__Sequence__destroy(vision_interfaces__msg__Inspection__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    vision_interfaces__msg__Inspection__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
vision_interfaces__msg__Inspection__Sequence__are_equal(const vision_interfaces__msg__Inspection__Sequence * lhs, const vision_interfaces__msg__Inspection__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!vision_interfaces__msg__Inspection__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
vision_interfaces__msg__Inspection__Sequence__copy(
  const vision_interfaces__msg__Inspection__Sequence * input,
  vision_interfaces__msg__Inspection__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(vision_interfaces__msg__Inspection);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    vision_interfaces__msg__Inspection * data =
      (vision_interfaces__msg__Inspection *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!vision_interfaces__msg__Inspection__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          vision_interfaces__msg__Inspection__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!vision_interfaces__msg__Inspection__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
