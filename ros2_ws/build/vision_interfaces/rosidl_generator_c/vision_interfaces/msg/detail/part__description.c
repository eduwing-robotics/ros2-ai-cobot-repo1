// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from vision_interfaces:msg/Part.idl
// generated code does not contain a copyright notice

#include "vision_interfaces/msg/detail/part__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_vision_interfaces
const rosidl_type_hash_t *
vision_interfaces__msg__Part__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x38, 0x95, 0x7b, 0xfa, 0xea, 0xb7, 0x33, 0xa7,
      0x6c, 0xd1, 0x3c, 0x4c, 0xd4, 0x55, 0x5d, 0x30,
      0xcd, 0x7b, 0xa4, 0x08, 0x8c, 0x97, 0x34, 0xf3,
      0x66, 0xce, 0xff, 0x53, 0xe3, 0xe7, 0x0c, 0xa6,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types

// Hashes for external referenced types
#ifndef NDEBUG
#endif

static char vision_interfaces__msg__Part__TYPE_NAME[] = "vision_interfaces/msg/Part";

// Define type names, field names, and default values
static char vision_interfaces__msg__Part__FIELD_NAME__name[] = "name";
static char vision_interfaces__msg__Part__FIELD_NAME__class_id[] = "class_id";
static char vision_interfaces__msg__Part__FIELD_NAME__score[] = "score";
static char vision_interfaces__msg__Part__FIELD_NAME__x[] = "x";
static char vision_interfaces__msg__Part__FIELD_NAME__y[] = "y";
static char vision_interfaces__msg__Part__FIELD_NAME__width[] = "width";
static char vision_interfaces__msg__Part__FIELD_NAME__height[] = "height";
static char vision_interfaces__msg__Part__FIELD_NAME__angle_deg[] = "angle_deg";
static char vision_interfaces__msg__Part__FIELD_NAME__angle_valid[] = "angle_valid";
static char vision_interfaces__msg__Part__FIELD_NAME__depth_m[] = "depth_m";
static char vision_interfaces__msg__Part__FIELD_NAME__depth_valid[] = "depth_valid";
static char vision_interfaces__msg__Part__FIELD_NAME__camera_x_m[] = "camera_x_m";
static char vision_interfaces__msg__Part__FIELD_NAME__camera_y_m[] = "camera_y_m";
static char vision_interfaces__msg__Part__FIELD_NAME__camera_z_m[] = "camera_z_m";
static char vision_interfaces__msg__Part__FIELD_NAME__position_valid[] = "position_valid";

static rosidl_runtime_c__type_description__Field vision_interfaces__msg__Part__FIELDS[] = {
  {
    {vision_interfaces__msg__Part__FIELD_NAME__name, 4, 4},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__class_id, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__score, 5, 5},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_FLOAT,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__x, 1, 1},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__y, 1, 1},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__width, 5, 5},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__height, 6, 6},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__angle_deg, 9, 9},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_FLOAT,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__angle_valid, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__depth_m, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_FLOAT,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__depth_valid, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__camera_x_m, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_FLOAT,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__camera_y_m, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_FLOAT,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__camera_z_m, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_FLOAT,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__FIELD_NAME__position_valid, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
vision_interfaces__msg__Part__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {vision_interfaces__msg__Part__TYPE_NAME, 26, 26},
      {vision_interfaces__msg__Part__FIELDS, 15, 15},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "string name\n"
  "int32 class_id\n"
  "float32 score\n"
  "int32 x\n"
  "int32 y\n"
  "int32 width\n"
  "int32 height\n"
  "float32 angle_deg\n"
  "bool angle_valid\n"
  "float32 depth_m\n"
  "bool depth_valid\n"
  "float32 camera_x_m\n"
  "float32 camera_y_m\n"
  "float32 camera_z_m\n"
  "bool position_valid";

static char msg_encoding[] = "msg";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
vision_interfaces__msg__Part__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {vision_interfaces__msg__Part__TYPE_NAME, 26, 26},
    {msg_encoding, 3, 3},
    {toplevel_type_raw_source, 227, 227},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
vision_interfaces__msg__Part__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *vision_interfaces__msg__Part__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}
