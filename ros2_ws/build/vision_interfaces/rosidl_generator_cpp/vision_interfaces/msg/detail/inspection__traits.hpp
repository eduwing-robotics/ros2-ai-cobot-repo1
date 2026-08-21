// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from vision_interfaces:msg/Inspection.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/inspection.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__INSPECTION__TRAITS_HPP_
#define VISION_INTERFACES__MSG__DETAIL__INSPECTION__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "vision_interfaces/msg/detail/inspection__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__traits.hpp"

namespace vision_interfaces
{

namespace msg
{

inline void to_flow_style_yaml(
  const Inspection & msg,
  std::ostream & out)
{
  out << "{";
  // member: header
  {
    out << "header: ";
    to_flow_style_yaml(msg.header, out);
    out << ", ";
  }

  // member: camera
  {
    out << "camera: ";
    rosidl_generator_traits::value_to_yaml(msg.camera, out);
    out << ", ";
  }

  // member: board_id
  {
    out << "board_id: ";
    rosidl_generator_traits::value_to_yaml(msg.board_id, out);
    out << ", ";
  }

  // member: recipe_id
  {
    out << "recipe_id: ";
    rosidl_generator_traits::value_to_yaml(msg.recipe_id, out);
    out << ", ";
  }

  // member: status
  {
    out << "status: ";
    rosidl_generator_traits::value_to_yaml(msg.status, out);
    out << ", ";
  }

  // member: expected_total
  {
    out << "expected_total: ";
    rosidl_generator_traits::value_to_yaml(msg.expected_total, out);
    out << ", ";
  }

  // member: found_total
  {
    out << "found_total: ";
    rosidl_generator_traits::value_to_yaml(msg.found_total, out);
    out << ", ";
  }

  // member: names
  {
    if (msg.names.size() == 0) {
      out << "names: []";
    } else {
      out << "names: [";
      size_t pending_items = msg.names.size();
      for (auto item : msg.names) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: expected
  {
    if (msg.expected.size() == 0) {
      out << "expected: []";
    } else {
      out << "expected: [";
      size_t pending_items = msg.expected.size();
      for (auto item : msg.expected) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: found
  {
    if (msg.found.size() == 0) {
      out << "found: []";
    } else {
      out << "found: [";
      size_t pending_items = msg.found.size();
      for (auto item : msg.found) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: slot_ids
  {
    if (msg.slot_ids.size() == 0) {
      out << "slot_ids: []";
    } else {
      out << "slot_ids: [";
      size_t pending_items = msg.slot_ids.size();
      for (auto item : msg.slot_ids) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: slot_status
  {
    if (msg.slot_status.size() == 0) {
      out << "slot_status: []";
    } else {
      out << "slot_status: [";
      size_t pending_items = msg.slot_status.size();
      for (auto item : msg.slot_status) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: errors
  {
    if (msg.errors.size() == 0) {
      out << "errors: []";
    } else {
      out << "errors: [";
      size_t pending_items = msg.errors.size();
      for (auto item : msg.errors) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const Inspection & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: header
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "header:\n";
    to_block_style_yaml(msg.header, out, indentation + 2);
  }

  // member: camera
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "camera: ";
    rosidl_generator_traits::value_to_yaml(msg.camera, out);
    out << "\n";
  }

  // member: board_id
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "board_id: ";
    rosidl_generator_traits::value_to_yaml(msg.board_id, out);
    out << "\n";
  }

  // member: recipe_id
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "recipe_id: ";
    rosidl_generator_traits::value_to_yaml(msg.recipe_id, out);
    out << "\n";
  }

  // member: status
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "status: ";
    rosidl_generator_traits::value_to_yaml(msg.status, out);
    out << "\n";
  }

  // member: expected_total
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "expected_total: ";
    rosidl_generator_traits::value_to_yaml(msg.expected_total, out);
    out << "\n";
  }

  // member: found_total
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "found_total: ";
    rosidl_generator_traits::value_to_yaml(msg.found_total, out);
    out << "\n";
  }

  // member: names
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.names.size() == 0) {
      out << "names: []\n";
    } else {
      out << "names:\n";
      for (auto item : msg.names) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: expected
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.expected.size() == 0) {
      out << "expected: []\n";
    } else {
      out << "expected:\n";
      for (auto item : msg.expected) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: found
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.found.size() == 0) {
      out << "found: []\n";
    } else {
      out << "found:\n";
      for (auto item : msg.found) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: slot_ids
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.slot_ids.size() == 0) {
      out << "slot_ids: []\n";
    } else {
      out << "slot_ids:\n";
      for (auto item : msg.slot_ids) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: slot_status
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.slot_status.size() == 0) {
      out << "slot_status: []\n";
    } else {
      out << "slot_status:\n";
      for (auto item : msg.slot_status) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: errors
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.errors.size() == 0) {
      out << "errors: []\n";
    } else {
      out << "errors:\n";
      for (auto item : msg.errors) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const Inspection & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace msg

}  // namespace vision_interfaces

namespace rosidl_generator_traits
{

[[deprecated("use vision_interfaces::msg::to_block_style_yaml() instead")]]
inline void to_yaml(
  const vision_interfaces::msg::Inspection & msg,
  std::ostream & out, size_t indentation = 0)
{
  vision_interfaces::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use vision_interfaces::msg::to_yaml() instead")]]
inline std::string to_yaml(const vision_interfaces::msg::Inspection & msg)
{
  return vision_interfaces::msg::to_yaml(msg);
}

template<>
inline const char * data_type<vision_interfaces::msg::Inspection>()
{
  return "vision_interfaces::msg::Inspection";
}

template<>
inline const char * name<vision_interfaces::msg::Inspection>()
{
  return "vision_interfaces/msg/Inspection";
}

template<>
struct has_fixed_size<vision_interfaces::msg::Inspection>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<vision_interfaces::msg::Inspection>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<vision_interfaces::msg::Inspection>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // VISION_INTERFACES__MSG__DETAIL__INSPECTION__TRAITS_HPP_
