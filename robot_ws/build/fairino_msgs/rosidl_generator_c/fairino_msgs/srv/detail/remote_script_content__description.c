// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from fairino_msgs:srv/RemoteScriptContent.idl
// generated code does not contain a copyright notice

#include "fairino_msgs/srv/detail/remote_script_content__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_fairino_msgs
const rosidl_type_hash_t *
fairino_msgs__srv__RemoteScriptContent__get_type_hash(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0xe2, 0x8e, 0x95, 0x09, 0x59, 0x30, 0x58, 0xac,
      0xf7, 0x36, 0xdf, 0x16, 0x29, 0x60, 0x95, 0x05,
      0x6d, 0x82, 0xd6, 0xe3, 0x23, 0xbd, 0x9c, 0x30,
      0x0d, 0xc0, 0xa3, 0x37, 0x66, 0xae, 0x03, 0x7b,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_fairino_msgs
const rosidl_type_hash_t *
fairino_msgs__srv__RemoteScriptContent_Request__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x00, 0x7e, 0x03, 0x5f, 0xbc, 0xaf, 0x7b, 0x8e,
      0x48, 0x42, 0xf9, 0x7d, 0x59, 0x63, 0x61, 0x10,
      0xcc, 0x1f, 0xc6, 0x6e, 0xa4, 0x00, 0x09, 0x73,
      0x48, 0xda, 0x80, 0x02, 0x89, 0xc0, 0x2d, 0x7c,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_fairino_msgs
const rosidl_type_hash_t *
fairino_msgs__srv__RemoteScriptContent_Response__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x09, 0x61, 0x4d, 0xb1, 0xbf, 0xf2, 0xd8, 0x38,
      0xf9, 0x79, 0x3f, 0x79, 0xdd, 0x9e, 0xec, 0x17,
      0x21, 0xbe, 0x27, 0x08, 0xb5, 0x7e, 0x54, 0xa2,
      0x28, 0x57, 0x66, 0xc4, 0xc9, 0xd3, 0xa4, 0x39,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_fairino_msgs
const rosidl_type_hash_t *
fairino_msgs__srv__RemoteScriptContent_Event__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x29, 0x75, 0x0e, 0x41, 0xa4, 0xb7, 0x80, 0x36,
      0x18, 0x4d, 0x09, 0x60, 0x59, 0x9e, 0x5d, 0x9e,
      0xc4, 0x0e, 0x90, 0x78, 0x4d, 0x11, 0x93, 0x00,
      0x43, 0xcc, 0x8f, 0x89, 0x09, 0x93, 0x5c, 0x48,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types
#include "builtin_interfaces/msg/detail/time__functions.h"
#include "service_msgs/msg/detail/service_event_info__functions.h"

// Hashes for external referenced types
#ifndef NDEBUG
static const rosidl_type_hash_t builtin_interfaces__msg__Time__EXPECTED_HASH = {1, {
    0xb1, 0x06, 0x23, 0x5e, 0x25, 0xa4, 0xc5, 0xed,
    0x35, 0x09, 0x8a, 0xa0, 0xa6, 0x1a, 0x3e, 0xe9,
    0xc9, 0xb1, 0x8d, 0x19, 0x7f, 0x39, 0x8b, 0x0e,
    0x42, 0x06, 0xce, 0xa9, 0xac, 0xf9, 0xc1, 0x97,
  }};
static const rosidl_type_hash_t service_msgs__msg__ServiceEventInfo__EXPECTED_HASH = {1, {
    0x41, 0xbc, 0xbb, 0xe0, 0x7a, 0x75, 0xc9, 0xb5,
    0x2b, 0xc9, 0x6b, 0xfd, 0x5c, 0x24, 0xd7, 0xf0,
    0xfc, 0x0a, 0x08, 0xc0, 0xcb, 0x79, 0x21, 0xb3,
    0x37, 0x3c, 0x57, 0x32, 0x34, 0x5a, 0x6f, 0x45,
  }};
#endif

static char fairino_msgs__srv__RemoteScriptContent__TYPE_NAME[] = "fairino_msgs/srv/RemoteScriptContent";
static char builtin_interfaces__msg__Time__TYPE_NAME[] = "builtin_interfaces/msg/Time";
static char fairino_msgs__srv__RemoteScriptContent_Event__TYPE_NAME[] = "fairino_msgs/srv/RemoteScriptContent_Event";
static char fairino_msgs__srv__RemoteScriptContent_Request__TYPE_NAME[] = "fairino_msgs/srv/RemoteScriptContent_Request";
static char fairino_msgs__srv__RemoteScriptContent_Response__TYPE_NAME[] = "fairino_msgs/srv/RemoteScriptContent_Response";
static char service_msgs__msg__ServiceEventInfo__TYPE_NAME[] = "service_msgs/msg/ServiceEventInfo";

// Define type names, field names, and default values
static char fairino_msgs__srv__RemoteScriptContent__FIELD_NAME__request_message[] = "request_message";
static char fairino_msgs__srv__RemoteScriptContent__FIELD_NAME__response_message[] = "response_message";
static char fairino_msgs__srv__RemoteScriptContent__FIELD_NAME__event_message[] = "event_message";

static rosidl_runtime_c__type_description__Field fairino_msgs__srv__RemoteScriptContent__FIELDS[] = {
  {
    {fairino_msgs__srv__RemoteScriptContent__FIELD_NAME__request_message, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {fairino_msgs__srv__RemoteScriptContent_Request__TYPE_NAME, 44, 44},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent__FIELD_NAME__response_message, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {fairino_msgs__srv__RemoteScriptContent_Response__TYPE_NAME, 45, 45},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent__FIELD_NAME__event_message, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {fairino_msgs__srv__RemoteScriptContent_Event__TYPE_NAME, 42, 42},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription fairino_msgs__srv__RemoteScriptContent__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {builtin_interfaces__msg__Time__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent_Event__TYPE_NAME, 42, 42},
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent_Request__TYPE_NAME, 44, 44},
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent_Response__TYPE_NAME, 45, 45},
    {NULL, 0, 0},
  },
  {
    {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
fairino_msgs__srv__RemoteScriptContent__get_type_description(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {fairino_msgs__srv__RemoteScriptContent__TYPE_NAME, 36, 36},
      {fairino_msgs__srv__RemoteScriptContent__FIELDS, 3, 3},
    },
    {fairino_msgs__srv__RemoteScriptContent__REFERENCED_TYPE_DESCRIPTIONS, 5, 5},
  };
  if (!constructed) {
    assert(0 == memcmp(&builtin_interfaces__msg__Time__EXPECTED_HASH, builtin_interfaces__msg__Time__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = builtin_interfaces__msg__Time__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[1].fields = fairino_msgs__srv__RemoteScriptContent_Event__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[2].fields = fairino_msgs__srv__RemoteScriptContent_Request__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[3].fields = fairino_msgs__srv__RemoteScriptContent_Response__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&service_msgs__msg__ServiceEventInfo__EXPECTED_HASH, service_msgs__msg__ServiceEventInfo__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[4].fields = service_msgs__msg__ServiceEventInfo__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char fairino_msgs__srv__RemoteScriptContent_Request__FIELD_NAME__line_str[] = "line_str";

static rosidl_runtime_c__type_description__Field fairino_msgs__srv__RemoteScriptContent_Request__FIELDS[] = {
  {
    {fairino_msgs__srv__RemoteScriptContent_Request__FIELD_NAME__line_str, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
fairino_msgs__srv__RemoteScriptContent_Request__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {fairino_msgs__srv__RemoteScriptContent_Request__TYPE_NAME, 44, 44},
      {fairino_msgs__srv__RemoteScriptContent_Request__FIELDS, 1, 1},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char fairino_msgs__srv__RemoteScriptContent_Response__FIELD_NAME__res[] = "res";

static rosidl_runtime_c__type_description__Field fairino_msgs__srv__RemoteScriptContent_Response__FIELDS[] = {
  {
    {fairino_msgs__srv__RemoteScriptContent_Response__FIELD_NAME__res, 3, 3},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
fairino_msgs__srv__RemoteScriptContent_Response__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {fairino_msgs__srv__RemoteScriptContent_Response__TYPE_NAME, 45, 45},
      {fairino_msgs__srv__RemoteScriptContent_Response__FIELDS, 1, 1},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char fairino_msgs__srv__RemoteScriptContent_Event__FIELD_NAME__info[] = "info";
static char fairino_msgs__srv__RemoteScriptContent_Event__FIELD_NAME__request[] = "request";
static char fairino_msgs__srv__RemoteScriptContent_Event__FIELD_NAME__response[] = "response";

static rosidl_runtime_c__type_description__Field fairino_msgs__srv__RemoteScriptContent_Event__FIELDS[] = {
  {
    {fairino_msgs__srv__RemoteScriptContent_Event__FIELD_NAME__info, 4, 4},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent_Event__FIELD_NAME__request, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE_BOUNDED_SEQUENCE,
      1,
      0,
      {fairino_msgs__srv__RemoteScriptContent_Request__TYPE_NAME, 44, 44},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent_Event__FIELD_NAME__response, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE_BOUNDED_SEQUENCE,
      1,
      0,
      {fairino_msgs__srv__RemoteScriptContent_Response__TYPE_NAME, 45, 45},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription fairino_msgs__srv__RemoteScriptContent_Event__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {builtin_interfaces__msg__Time__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent_Request__TYPE_NAME, 44, 44},
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__srv__RemoteScriptContent_Response__TYPE_NAME, 45, 45},
    {NULL, 0, 0},
  },
  {
    {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
fairino_msgs__srv__RemoteScriptContent_Event__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {fairino_msgs__srv__RemoteScriptContent_Event__TYPE_NAME, 42, 42},
      {fairino_msgs__srv__RemoteScriptContent_Event__FIELDS, 3, 3},
    },
    {fairino_msgs__srv__RemoteScriptContent_Event__REFERENCED_TYPE_DESCRIPTIONS, 4, 4},
  };
  if (!constructed) {
    assert(0 == memcmp(&builtin_interfaces__msg__Time__EXPECTED_HASH, builtin_interfaces__msg__Time__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = builtin_interfaces__msg__Time__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[1].fields = fairino_msgs__srv__RemoteScriptContent_Request__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[2].fields = fairino_msgs__srv__RemoteScriptContent_Response__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&service_msgs__msg__ServiceEventInfo__EXPECTED_HASH, service_msgs__msg__ServiceEventInfo__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[3].fields = service_msgs__msg__ServiceEventInfo__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "string line_str\n"
  "---\n"
  "string res #\\xe5\\x88\\x9b\\xe5\\xbb\\xba\\xe7\\xbb\\x93\\xe6\\x9e\\x9c\\xe5\\x8f\\x8d\\xe9\\xa6\\x88\\xef\\xbc\\x8c0-\\xe6\\x88\\x90\\xe5\\x8a\\x9f\\xef\\xbc\\x8c-1-\\xe5\\xa4\\xb1\\xe8\\xb4\\xa5\n"
  "";

static char srv_encoding[] = "srv";
static char implicit_encoding[] = "implicit";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
fairino_msgs__srv__RemoteScriptContent__get_individual_type_description_source(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {fairino_msgs__srv__RemoteScriptContent__TYPE_NAME, 36, 36},
    {srv_encoding, 3, 3},
    {toplevel_type_raw_source, 51, 51},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
fairino_msgs__srv__RemoteScriptContent_Request__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {fairino_msgs__srv__RemoteScriptContent_Request__TYPE_NAME, 44, 44},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
fairino_msgs__srv__RemoteScriptContent_Response__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {fairino_msgs__srv__RemoteScriptContent_Response__TYPE_NAME, 45, 45},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
fairino_msgs__srv__RemoteScriptContent_Event__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {fairino_msgs__srv__RemoteScriptContent_Event__TYPE_NAME, 42, 42},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
fairino_msgs__srv__RemoteScriptContent__get_type_description_sources(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[6];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 6, 6};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *fairino_msgs__srv__RemoteScriptContent__get_individual_type_description_source(NULL),
    sources[1] = *builtin_interfaces__msg__Time__get_individual_type_description_source(NULL);
    sources[2] = *fairino_msgs__srv__RemoteScriptContent_Event__get_individual_type_description_source(NULL);
    sources[3] = *fairino_msgs__srv__RemoteScriptContent_Request__get_individual_type_description_source(NULL);
    sources[4] = *fairino_msgs__srv__RemoteScriptContent_Response__get_individual_type_description_source(NULL);
    sources[5] = *service_msgs__msg__ServiceEventInfo__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
fairino_msgs__srv__RemoteScriptContent_Request__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *fairino_msgs__srv__RemoteScriptContent_Request__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
fairino_msgs__srv__RemoteScriptContent_Response__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *fairino_msgs__srv__RemoteScriptContent_Response__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
fairino_msgs__srv__RemoteScriptContent_Event__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[5];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 5, 5};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *fairino_msgs__srv__RemoteScriptContent_Event__get_individual_type_description_source(NULL),
    sources[1] = *builtin_interfaces__msg__Time__get_individual_type_description_source(NULL);
    sources[2] = *fairino_msgs__srv__RemoteScriptContent_Request__get_individual_type_description_source(NULL);
    sources[3] = *fairino_msgs__srv__RemoteScriptContent_Response__get_individual_type_description_source(NULL);
    sources[4] = *service_msgs__msg__ServiceEventInfo__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}
