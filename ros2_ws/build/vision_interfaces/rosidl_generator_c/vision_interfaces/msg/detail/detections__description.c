// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from vision_interfaces:msg/Detections.idl
// generated code does not contain a copyright notice

#include "vision_interfaces/msg/detail/detections__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_vision_interfaces
const rosidl_type_hash_t *
vision_interfaces__msg__Detections__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0xef, 0x7f, 0xed, 0xaf, 0x51, 0xf3, 0xd2, 0x8e,
      0x8e, 0xf3, 0x12, 0x47, 0xca, 0x56, 0x5f, 0xb2,
      0x25, 0x18, 0x2e, 0x44, 0x10, 0x62, 0xf6, 0xcd,
      0xeb, 0x94, 0x6d, 0x17, 0x2e, 0x33, 0x48, 0x91,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types
#include "builtin_interfaces/msg/detail/time__functions.h"
#include "std_msgs/msg/detail/header__functions.h"
#include "vision_interfaces/msg/detail/part__functions.h"

// Hashes for external referenced types
#ifndef NDEBUG
static const rosidl_type_hash_t builtin_interfaces__msg__Time__EXPECTED_HASH = {1, {
    0xb1, 0x06, 0x23, 0x5e, 0x25, 0xa4, 0xc5, 0xed,
    0x35, 0x09, 0x8a, 0xa0, 0xa6, 0x1a, 0x3e, 0xe9,
    0xc9, 0xb1, 0x8d, 0x19, 0x7f, 0x39, 0x8b, 0x0e,
    0x42, 0x06, 0xce, 0xa9, 0xac, 0xf9, 0xc1, 0x97,
  }};
static const rosidl_type_hash_t std_msgs__msg__Header__EXPECTED_HASH = {1, {
    0xf4, 0x9f, 0xb3, 0xae, 0x2c, 0xf0, 0x70, 0xf7,
    0x93, 0x64, 0x5f, 0xf7, 0x49, 0x68, 0x3a, 0xc6,
    0xb0, 0x62, 0x03, 0xe4, 0x1c, 0x89, 0x1e, 0x17,
    0x70, 0x1b, 0x1c, 0xb5, 0x97, 0xce, 0x6a, 0x01,
  }};
static const rosidl_type_hash_t vision_interfaces__msg__Part__EXPECTED_HASH = {1, {
    0x38, 0x95, 0x7b, 0xfa, 0xea, 0xb7, 0x33, 0xa7,
    0x6c, 0xd1, 0x3c, 0x4c, 0xd4, 0x55, 0x5d, 0x30,
    0xcd, 0x7b, 0xa4, 0x08, 0x8c, 0x97, 0x34, 0xf3,
    0x66, 0xce, 0xff, 0x53, 0xe3, 0xe7, 0x0c, 0xa6,
  }};
#endif

static char vision_interfaces__msg__Detections__TYPE_NAME[] = "vision_interfaces/msg/Detections";
static char builtin_interfaces__msg__Time__TYPE_NAME[] = "builtin_interfaces/msg/Time";
static char std_msgs__msg__Header__TYPE_NAME[] = "std_msgs/msg/Header";
static char vision_interfaces__msg__Part__TYPE_NAME[] = "vision_interfaces/msg/Part";

// Define type names, field names, and default values
static char vision_interfaces__msg__Detections__FIELD_NAME__header[] = "header";
static char vision_interfaces__msg__Detections__FIELD_NAME__camera[] = "camera";
static char vision_interfaces__msg__Detections__FIELD_NAME__image_width[] = "image_width";
static char vision_interfaces__msg__Detections__FIELD_NAME__image_height[] = "image_height";
static char vision_interfaces__msg__Detections__FIELD_NAME__parts[] = "parts";

static rosidl_runtime_c__type_description__Field vision_interfaces__msg__Detections__FIELDS[] = {
  {
    {vision_interfaces__msg__Detections__FIELD_NAME__header, 6, 6},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {std_msgs__msg__Header__TYPE_NAME, 19, 19},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Detections__FIELD_NAME__camera, 6, 6},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Detections__FIELD_NAME__image_width, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Detections__FIELD_NAME__image_height, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Detections__FIELD_NAME__parts, 5, 5},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE_UNBOUNDED_SEQUENCE,
      0,
      0,
      {vision_interfaces__msg__Part__TYPE_NAME, 26, 26},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription vision_interfaces__msg__Detections__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {builtin_interfaces__msg__Time__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {std_msgs__msg__Header__TYPE_NAME, 19, 19},
    {NULL, 0, 0},
  },
  {
    {vision_interfaces__msg__Part__TYPE_NAME, 26, 26},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
vision_interfaces__msg__Detections__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {vision_interfaces__msg__Detections__TYPE_NAME, 32, 32},
      {vision_interfaces__msg__Detections__FIELDS, 5, 5},
    },
    {vision_interfaces__msg__Detections__REFERENCED_TYPE_DESCRIPTIONS, 3, 3},
  };
  if (!constructed) {
    assert(0 == memcmp(&builtin_interfaces__msg__Time__EXPECTED_HASH, builtin_interfaces__msg__Time__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = builtin_interfaces__msg__Time__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&std_msgs__msg__Header__EXPECTED_HASH, std_msgs__msg__Header__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[1].fields = std_msgs__msg__Header__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&vision_interfaces__msg__Part__EXPECTED_HASH, vision_interfaces__msg__Part__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[2].fields = vision_interfaces__msg__Part__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "std_msgs/Header header\n"
  "string camera\n"
  "uint32 image_width\n"
  "uint32 image_height\n"
  "vision_interfaces/Part[] parts";

static char msg_encoding[] = "msg";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
vision_interfaces__msg__Detections__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {vision_interfaces__msg__Detections__TYPE_NAME, 32, 32},
    {msg_encoding, 3, 3},
    {toplevel_type_raw_source, 107, 107},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
vision_interfaces__msg__Detections__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[4];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 4, 4};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *vision_interfaces__msg__Detections__get_individual_type_description_source(NULL),
    sources[1] = *builtin_interfaces__msg__Time__get_individual_type_description_source(NULL);
    sources[2] = *std_msgs__msg__Header__get_individual_type_description_source(NULL);
    sources[3] = *vision_interfaces__msg__Part__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}
