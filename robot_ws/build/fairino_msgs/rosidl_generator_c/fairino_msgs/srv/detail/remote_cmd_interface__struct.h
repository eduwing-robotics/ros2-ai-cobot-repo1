// NOLINT: This file starts with a BOM since it contain non-ASCII characters
// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from fairino_msgs:srv/RemoteCmdInterface.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "fairino_msgs/srv/remote_cmd_interface.h"


#ifndef FAIRINO_MSGS__SRV__DETAIL__REMOTE_CMD_INTERFACE__STRUCT_H_
#define FAIRINO_MSGS__SRV__DETAIL__REMOTE_CMD_INTERFACE__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'cmd_str'
#include "rosidl_runtime_c/string.h"

/// Struct defined in srv/RemoteCmdInterface in the package fairino_msgs.
typedef struct fairino_msgs__srv__RemoteCmdInterface_Request
{
  /// ros用户输入的字符串指令，比如movej(p1,100)
  rosidl_runtime_c__String cmd_str;
} fairino_msgs__srv__RemoteCmdInterface_Request;

// Struct for a sequence of fairino_msgs__srv__RemoteCmdInterface_Request.
typedef struct fairino_msgs__srv__RemoteCmdInterface_Request__Sequence
{
  fairino_msgs__srv__RemoteCmdInterface_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} fairino_msgs__srv__RemoteCmdInterface_Request__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'cmd_res'
// already included above
// #include "rosidl_runtime_c/string.h"

/// Struct defined in srv/RemoteCmdInterface in the package fairino_msgs.
typedef struct fairino_msgs__srv__RemoteCmdInterface_Response
{
  /// 创建结果反馈，0-成功，-1-失败
  rosidl_runtime_c__String cmd_res;
} fairino_msgs__srv__RemoteCmdInterface_Response;

// Struct for a sequence of fairino_msgs__srv__RemoteCmdInterface_Response.
typedef struct fairino_msgs__srv__RemoteCmdInterface_Response__Sequence
{
  fairino_msgs__srv__RemoteCmdInterface_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} fairino_msgs__srv__RemoteCmdInterface_Response__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__struct.h"

// constants for array fields with an upper bound
// request
enum
{
  fairino_msgs__srv__RemoteCmdInterface_Event__request__MAX_SIZE = 1
};
// response
enum
{
  fairino_msgs__srv__RemoteCmdInterface_Event__response__MAX_SIZE = 1
};

/// Struct defined in srv/RemoteCmdInterface in the package fairino_msgs.
typedef struct fairino_msgs__srv__RemoteCmdInterface_Event
{
  service_msgs__msg__ServiceEventInfo info;
  fairino_msgs__srv__RemoteCmdInterface_Request__Sequence request;
  fairino_msgs__srv__RemoteCmdInterface_Response__Sequence response;
} fairino_msgs__srv__RemoteCmdInterface_Event;

// Struct for a sequence of fairino_msgs__srv__RemoteCmdInterface_Event.
typedef struct fairino_msgs__srv__RemoteCmdInterface_Event__Sequence
{
  fairino_msgs__srv__RemoteCmdInterface_Event * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} fairino_msgs__srv__RemoteCmdInterface_Event__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // FAIRINO_MSGS__SRV__DETAIL__REMOTE_CMD_INTERFACE__STRUCT_H_
