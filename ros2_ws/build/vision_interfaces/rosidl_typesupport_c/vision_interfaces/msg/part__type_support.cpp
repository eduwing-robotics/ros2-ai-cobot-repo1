// generated from rosidl_typesupport_c/resource/idl__type_support.cpp.em
// with input from vision_interfaces:msg/Part.idl
// generated code does not contain a copyright notice

#include "cstddef"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "vision_interfaces/msg/detail/part__struct.h"
#include "vision_interfaces/msg/detail/part__type_support.h"
#include "vision_interfaces/msg/detail/part__functions.h"
#include "rosidl_typesupport_c/identifier.h"
#include "rosidl_typesupport_c/message_type_support_dispatch.h"
#include "rosidl_typesupport_c/type_support_map.h"
#include "rosidl_typesupport_c/visibility_control.h"
#include "rosidl_typesupport_interface/macros.h"

namespace vision_interfaces
{

namespace msg
{

namespace rosidl_typesupport_c
{

typedef struct _Part_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _Part_type_support_ids_t;

static const _Part_type_support_ids_t _Part_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _Part_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _Part_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _Part_type_support_symbol_names_t _Part_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, vision_interfaces, msg, Part)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, vision_interfaces, msg, Part)),
  }
};

typedef struct _Part_type_support_data_t
{
  void * data[2];
} _Part_type_support_data_t;

static _Part_type_support_data_t _Part_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _Part_message_typesupport_map = {
  2,
  "vision_interfaces",
  &_Part_message_typesupport_ids.typesupport_identifier[0],
  &_Part_message_typesupport_symbol_names.symbol_name[0],
  &_Part_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t Part_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_Part_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &vision_interfaces__msg__Part__get_type_hash,
  &vision_interfaces__msg__Part__get_type_description,
  &vision_interfaces__msg__Part__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace msg

}  // namespace vision_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, vision_interfaces, msg, Part)() {
  return &::vision_interfaces::msg::rosidl_typesupport_c::Part_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif
