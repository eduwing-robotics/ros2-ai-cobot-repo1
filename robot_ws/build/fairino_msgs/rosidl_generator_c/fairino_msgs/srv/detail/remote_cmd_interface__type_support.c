// generated from rosidl_generator_c/resource/idl__type_support.c.em
// with input from fairino_msgs:srv/RemoteCmdInterface.idl
// generated code does not contain a copyright notice

#include <string.h>

#include "fairino_msgs/srv/detail/remote_cmd_interface__struct.h"
#include "rosidl_typesupport_interface/macros.h"
#include "fairino_msgs/srv/detail/remote_cmd_interface__functions.h"
#include "fairino_msgs/srv/detail/remote_cmd_interface__type_support.h"

#ifdef __cplusplus
extern "C"
{
#endif


void *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_CREATE_EVENT_MESSAGE_SYMBOL_NAME(
  rosidl_typesupport_c,
  fairino_msgs,
  srv,
  RemoteCmdInterface
)(
  const rosidl_service_introspection_info_t * info,
  rcutils_allocator_t * allocator,
  const void * request_message,
  const void * response_message)
{
  if (!allocator || !info) {
    return NULL;
  }
  fairino_msgs__srv__RemoteCmdInterface_Event * event_msg = (fairino_msgs__srv__RemoteCmdInterface_Event *)(allocator->allocate(sizeof(fairino_msgs__srv__RemoteCmdInterface_Event), allocator->state));
  if (!fairino_msgs__srv__RemoteCmdInterface_Event__init(event_msg)) {
    allocator->deallocate(event_msg, allocator->state);
    return NULL;
  }

  event_msg->info.event_type = info->event_type;
  event_msg->info.sequence_number = info->sequence_number;
  event_msg->info.stamp.sec = info->stamp_sec;
  event_msg->info.stamp.nanosec = info->stamp_nanosec;
  memcpy(event_msg->info.client_gid, info->client_gid, 16);
  if (request_message) {
    fairino_msgs__srv__RemoteCmdInterface_Request__Sequence__init(
      &event_msg->request,
      1);
    if (!fairino_msgs__srv__RemoteCmdInterface_Request__copy((const fairino_msgs__srv__RemoteCmdInterface_Request *)(request_message), event_msg->request.data)) {
      allocator->deallocate(event_msg, allocator->state);
      return NULL;
    }
  }
  if (response_message) {
    fairino_msgs__srv__RemoteCmdInterface_Response__Sequence__init(
      &event_msg->response,
      1);
    if (!fairino_msgs__srv__RemoteCmdInterface_Response__copy((const fairino_msgs__srv__RemoteCmdInterface_Response *)(response_message), event_msg->response.data)) {
      allocator->deallocate(event_msg, allocator->state);
      return NULL;
    }
  }
  return event_msg;
}

// Forward declare the get type support functions for this type.
bool
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_DESTROY_EVENT_MESSAGE_SYMBOL_NAME(
  rosidl_typesupport_c,
  fairino_msgs,
  srv,
  RemoteCmdInterface
)(
  void * event_msg,
  rcutils_allocator_t * allocator)
{
  if (!allocator) {
    return false;
  }
  if (NULL == event_msg) {
    return false;
  }
  fairino_msgs__srv__RemoteCmdInterface_Event * _event_msg = (fairino_msgs__srv__RemoteCmdInterface_Event *)(event_msg);

  fairino_msgs__srv__RemoteCmdInterface_Event__fini((fairino_msgs__srv__RemoteCmdInterface_Event *)(_event_msg));
  if (_event_msg->request.data) {
    allocator->deallocate(_event_msg->request.data, allocator->state);
  }
  if (_event_msg->response.data) {
    allocator->deallocate(_event_msg->response.data, allocator->state);
  }
  allocator->deallocate(_event_msg, allocator->state);
  return true;
}

#ifdef __cplusplus
}
#endif
