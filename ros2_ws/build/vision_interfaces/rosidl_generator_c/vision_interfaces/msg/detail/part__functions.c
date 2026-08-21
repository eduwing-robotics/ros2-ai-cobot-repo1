// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from vision_interfaces:msg/Part.idl
// generated code does not contain a copyright notice
#include "vision_interfaces/msg/detail/part__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `name`
#include "rosidl_runtime_c/string_functions.h"

bool
vision_interfaces__msg__Part__init(vision_interfaces__msg__Part * msg)
{
  if (!msg) {
    return false;
  }
  // name
  if (!rosidl_runtime_c__String__init(&msg->name)) {
    vision_interfaces__msg__Part__fini(msg);
    return false;
  }
  // class_id
  // score
  // x
  // y
  // width
  // height
  // angle_deg
  // angle_valid
  // depth_m
  // depth_valid
  // camera_x_m
  // camera_y_m
  // camera_z_m
  // position_valid
  return true;
}

void
vision_interfaces__msg__Part__fini(vision_interfaces__msg__Part * msg)
{
  if (!msg) {
    return;
  }
  // name
  rosidl_runtime_c__String__fini(&msg->name);
  // class_id
  // score
  // x
  // y
  // width
  // height
  // angle_deg
  // angle_valid
  // depth_m
  // depth_valid
  // camera_x_m
  // camera_y_m
  // camera_z_m
  // position_valid
}

bool
vision_interfaces__msg__Part__are_equal(const vision_interfaces__msg__Part * lhs, const vision_interfaces__msg__Part * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // name
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->name), &(rhs->name)))
  {
    return false;
  }
  // class_id
  if (lhs->class_id != rhs->class_id) {
    return false;
  }
  // score
  if (lhs->score != rhs->score) {
    return false;
  }
  // x
  if (lhs->x != rhs->x) {
    return false;
  }
  // y
  if (lhs->y != rhs->y) {
    return false;
  }
  // width
  if (lhs->width != rhs->width) {
    return false;
  }
  // height
  if (lhs->height != rhs->height) {
    return false;
  }
  // angle_deg
  if (lhs->angle_deg != rhs->angle_deg) {
    return false;
  }
  // angle_valid
  if (lhs->angle_valid != rhs->angle_valid) {
    return false;
  }
  // depth_m
  if (lhs->depth_m != rhs->depth_m) {
    return false;
  }
  // depth_valid
  if (lhs->depth_valid != rhs->depth_valid) {
    return false;
  }
  // camera_x_m
  if (lhs->camera_x_m != rhs->camera_x_m) {
    return false;
  }
  // camera_y_m
  if (lhs->camera_y_m != rhs->camera_y_m) {
    return false;
  }
  // camera_z_m
  if (lhs->camera_z_m != rhs->camera_z_m) {
    return false;
  }
  // position_valid
  if (lhs->position_valid != rhs->position_valid) {
    return false;
  }
  return true;
}

bool
vision_interfaces__msg__Part__copy(
  const vision_interfaces__msg__Part * input,
  vision_interfaces__msg__Part * output)
{
  if (!input || !output) {
    return false;
  }
  // name
  if (!rosidl_runtime_c__String__copy(
      &(input->name), &(output->name)))
  {
    return false;
  }
  // class_id
  output->class_id = input->class_id;
  // score
  output->score = input->score;
  // x
  output->x = input->x;
  // y
  output->y = input->y;
  // width
  output->width = input->width;
  // height
  output->height = input->height;
  // angle_deg
  output->angle_deg = input->angle_deg;
  // angle_valid
  output->angle_valid = input->angle_valid;
  // depth_m
  output->depth_m = input->depth_m;
  // depth_valid
  output->depth_valid = input->depth_valid;
  // camera_x_m
  output->camera_x_m = input->camera_x_m;
  // camera_y_m
  output->camera_y_m = input->camera_y_m;
  // camera_z_m
  output->camera_z_m = input->camera_z_m;
  // position_valid
  output->position_valid = input->position_valid;
  return true;
}

vision_interfaces__msg__Part *
vision_interfaces__msg__Part__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__Part * msg = (vision_interfaces__msg__Part *)allocator.allocate(sizeof(vision_interfaces__msg__Part), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(vision_interfaces__msg__Part));
  bool success = vision_interfaces__msg__Part__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
vision_interfaces__msg__Part__destroy(vision_interfaces__msg__Part * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    vision_interfaces__msg__Part__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
vision_interfaces__msg__Part__Sequence__init(vision_interfaces__msg__Part__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__Part * data = NULL;

  if (size) {
    data = (vision_interfaces__msg__Part *)allocator.zero_allocate(size, sizeof(vision_interfaces__msg__Part), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = vision_interfaces__msg__Part__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        vision_interfaces__msg__Part__fini(&data[i - 1]);
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
vision_interfaces__msg__Part__Sequence__fini(vision_interfaces__msg__Part__Sequence * array)
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
      vision_interfaces__msg__Part__fini(&array->data[i]);
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

vision_interfaces__msg__Part__Sequence *
vision_interfaces__msg__Part__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__Part__Sequence * array = (vision_interfaces__msg__Part__Sequence *)allocator.allocate(sizeof(vision_interfaces__msg__Part__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = vision_interfaces__msg__Part__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
vision_interfaces__msg__Part__Sequence__destroy(vision_interfaces__msg__Part__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    vision_interfaces__msg__Part__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
vision_interfaces__msg__Part__Sequence__are_equal(const vision_interfaces__msg__Part__Sequence * lhs, const vision_interfaces__msg__Part__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!vision_interfaces__msg__Part__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
vision_interfaces__msg__Part__Sequence__copy(
  const vision_interfaces__msg__Part__Sequence * input,
  vision_interfaces__msg__Part__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(vision_interfaces__msg__Part);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    vision_interfaces__msg__Part * data =
      (vision_interfaces__msg__Part *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!vision_interfaces__msg__Part__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          vision_interfaces__msg__Part__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!vision_interfaces__msg__Part__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
