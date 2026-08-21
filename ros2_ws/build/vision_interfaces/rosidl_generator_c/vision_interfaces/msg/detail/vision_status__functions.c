// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from vision_interfaces:msg/VisionStatus.idl
// generated code does not contain a copyright notice
#include "vision_interfaces/msg/detail/vision_status__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/detail/header__functions.h"
// Member `cameras`
// Member `active_cameras`
// Member `missing_cameras`
// Member `message`
#include "rosidl_runtime_c/string_functions.h"

bool
vision_interfaces__msg__VisionStatus__init(vision_interfaces__msg__VisionStatus * msg)
{
  if (!msg) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__init(&msg->header)) {
    vision_interfaces__msg__VisionStatus__fini(msg);
    return false;
  }
  // ready
  // model_loaded
  // cameras
  if (!rosidl_runtime_c__String__Sequence__init(&msg->cameras, 0)) {
    vision_interfaces__msg__VisionStatus__fini(msg);
    return false;
  }
  // active_cameras
  if (!rosidl_runtime_c__String__Sequence__init(&msg->active_cameras, 0)) {
    vision_interfaces__msg__VisionStatus__fini(msg);
    return false;
  }
  // missing_cameras
  if (!rosidl_runtime_c__String__Sequence__init(&msg->missing_cameras, 0)) {
    vision_interfaces__msg__VisionStatus__fini(msg);
    return false;
  }
  // inference_count
  // message
  if (!rosidl_runtime_c__String__init(&msg->message)) {
    vision_interfaces__msg__VisionStatus__fini(msg);
    return false;
  }
  return true;
}

void
vision_interfaces__msg__VisionStatus__fini(vision_interfaces__msg__VisionStatus * msg)
{
  if (!msg) {
    return;
  }
  // header
  std_msgs__msg__Header__fini(&msg->header);
  // ready
  // model_loaded
  // cameras
  rosidl_runtime_c__String__Sequence__fini(&msg->cameras);
  // active_cameras
  rosidl_runtime_c__String__Sequence__fini(&msg->active_cameras);
  // missing_cameras
  rosidl_runtime_c__String__Sequence__fini(&msg->missing_cameras);
  // inference_count
  // message
  rosidl_runtime_c__String__fini(&msg->message);
}

bool
vision_interfaces__msg__VisionStatus__are_equal(const vision_interfaces__msg__VisionStatus * lhs, const vision_interfaces__msg__VisionStatus * rhs)
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
  // ready
  if (lhs->ready != rhs->ready) {
    return false;
  }
  // model_loaded
  if (lhs->model_loaded != rhs->model_loaded) {
    return false;
  }
  // cameras
  if (!rosidl_runtime_c__String__Sequence__are_equal(
      &(lhs->cameras), &(rhs->cameras)))
  {
    return false;
  }
  // active_cameras
  if (!rosidl_runtime_c__String__Sequence__are_equal(
      &(lhs->active_cameras), &(rhs->active_cameras)))
  {
    return false;
  }
  // missing_cameras
  if (!rosidl_runtime_c__String__Sequence__are_equal(
      &(lhs->missing_cameras), &(rhs->missing_cameras)))
  {
    return false;
  }
  // inference_count
  if (lhs->inference_count != rhs->inference_count) {
    return false;
  }
  // message
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->message), &(rhs->message)))
  {
    return false;
  }
  return true;
}

bool
vision_interfaces__msg__VisionStatus__copy(
  const vision_interfaces__msg__VisionStatus * input,
  vision_interfaces__msg__VisionStatus * output)
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
  // ready
  output->ready = input->ready;
  // model_loaded
  output->model_loaded = input->model_loaded;
  // cameras
  if (!rosidl_runtime_c__String__Sequence__copy(
      &(input->cameras), &(output->cameras)))
  {
    return false;
  }
  // active_cameras
  if (!rosidl_runtime_c__String__Sequence__copy(
      &(input->active_cameras), &(output->active_cameras)))
  {
    return false;
  }
  // missing_cameras
  if (!rosidl_runtime_c__String__Sequence__copy(
      &(input->missing_cameras), &(output->missing_cameras)))
  {
    return false;
  }
  // inference_count
  output->inference_count = input->inference_count;
  // message
  if (!rosidl_runtime_c__String__copy(
      &(input->message), &(output->message)))
  {
    return false;
  }
  return true;
}

vision_interfaces__msg__VisionStatus *
vision_interfaces__msg__VisionStatus__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__VisionStatus * msg = (vision_interfaces__msg__VisionStatus *)allocator.allocate(sizeof(vision_interfaces__msg__VisionStatus), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(vision_interfaces__msg__VisionStatus));
  bool success = vision_interfaces__msg__VisionStatus__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
vision_interfaces__msg__VisionStatus__destroy(vision_interfaces__msg__VisionStatus * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    vision_interfaces__msg__VisionStatus__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
vision_interfaces__msg__VisionStatus__Sequence__init(vision_interfaces__msg__VisionStatus__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__VisionStatus * data = NULL;

  if (size) {
    data = (vision_interfaces__msg__VisionStatus *)allocator.zero_allocate(size, sizeof(vision_interfaces__msg__VisionStatus), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = vision_interfaces__msg__VisionStatus__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        vision_interfaces__msg__VisionStatus__fini(&data[i - 1]);
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
vision_interfaces__msg__VisionStatus__Sequence__fini(vision_interfaces__msg__VisionStatus__Sequence * array)
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
      vision_interfaces__msg__VisionStatus__fini(&array->data[i]);
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

vision_interfaces__msg__VisionStatus__Sequence *
vision_interfaces__msg__VisionStatus__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  vision_interfaces__msg__VisionStatus__Sequence * array = (vision_interfaces__msg__VisionStatus__Sequence *)allocator.allocate(sizeof(vision_interfaces__msg__VisionStatus__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = vision_interfaces__msg__VisionStatus__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
vision_interfaces__msg__VisionStatus__Sequence__destroy(vision_interfaces__msg__VisionStatus__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    vision_interfaces__msg__VisionStatus__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
vision_interfaces__msg__VisionStatus__Sequence__are_equal(const vision_interfaces__msg__VisionStatus__Sequence * lhs, const vision_interfaces__msg__VisionStatus__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!vision_interfaces__msg__VisionStatus__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
vision_interfaces__msg__VisionStatus__Sequence__copy(
  const vision_interfaces__msg__VisionStatus__Sequence * input,
  vision_interfaces__msg__VisionStatus__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(vision_interfaces__msg__VisionStatus);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    vision_interfaces__msg__VisionStatus * data =
      (vision_interfaces__msg__VisionStatus *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!vision_interfaces__msg__VisionStatus__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          vision_interfaces__msg__VisionStatus__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!vision_interfaces__msg__VisionStatus__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
