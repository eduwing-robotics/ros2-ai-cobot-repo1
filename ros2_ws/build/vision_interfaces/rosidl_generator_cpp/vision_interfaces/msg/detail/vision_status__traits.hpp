// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from vision_interfaces:msg/VisionStatus.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/vision_status.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__TRAITS_HPP_
#define VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "vision_interfaces/msg/detail/vision_status__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__traits.hpp"

namespace vision_interfaces
{

namespace msg
{

inline void to_flow_style_yaml(
  const VisionStatus & msg,
  std::ostream & out)
{
  out << "{";
  // member: header
  {
    out << "header: ";
    to_flow_style_yaml(msg.header, out);
    out << ", ";
  }

  // member: ready
  {
    out << "ready: ";
    rosidl_generator_traits::value_to_yaml(msg.ready, out);
    out << ", ";
  }

  // member: model_loaded
  {
    out << "model_loaded: ";
    rosidl_generator_traits::value_to_yaml(msg.model_loaded, out);
    out << ", ";
  }

  // member: cameras
  {
    if (msg.cameras.size() == 0) {
      out << "cameras: []";
    } else {
      out << "cameras: [";
      size_t pending_items = msg.cameras.size();
      for (auto item : msg.cameras) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: active_cameras
  {
    if (msg.active_cameras.size() == 0) {
      out << "active_cameras: []";
    } else {
      out << "active_cameras: [";
      size_t pending_items = msg.active_cameras.size();
      for (auto item : msg.active_cameras) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: missing_cameras
  {
    if (msg.missing_cameras.size() == 0) {
      out << "missing_cameras: []";
    } else {
      out << "missing_cameras: [";
      size_t pending_items = msg.missing_cameras.size();
      for (auto item : msg.missing_cameras) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: inference_count
  {
    out << "inference_count: ";
    rosidl_generator_traits::value_to_yaml(msg.inference_count, out);
    out << ", ";
  }

  // member: message
  {
    out << "message: ";
    rosidl_generator_traits::value_to_yaml(msg.message, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const VisionStatus & msg,
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

  // member: ready
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "ready: ";
    rosidl_generator_traits::value_to_yaml(msg.ready, out);
    out << "\n";
  }

  // member: model_loaded
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "model_loaded: ";
    rosidl_generator_traits::value_to_yaml(msg.model_loaded, out);
    out << "\n";
  }

  // member: cameras
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.cameras.size() == 0) {
      out << "cameras: []\n";
    } else {
      out << "cameras:\n";
      for (auto item : msg.cameras) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: active_cameras
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.active_cameras.size() == 0) {
      out << "active_cameras: []\n";
    } else {
      out << "active_cameras:\n";
      for (auto item : msg.active_cameras) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: missing_cameras
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.missing_cameras.size() == 0) {
      out << "missing_cameras: []\n";
    } else {
      out << "missing_cameras:\n";
      for (auto item : msg.missing_cameras) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: inference_count
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "inference_count: ";
    rosidl_generator_traits::value_to_yaml(msg.inference_count, out);
    out << "\n";
  }

  // member: message
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "message: ";
    rosidl_generator_traits::value_to_yaml(msg.message, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const VisionStatus & msg, bool use_flow_style = false)
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
  const vision_interfaces::msg::VisionStatus & msg,
  std::ostream & out, size_t indentation = 0)
{
  vision_interfaces::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use vision_interfaces::msg::to_yaml() instead")]]
inline std::string to_yaml(const vision_interfaces::msg::VisionStatus & msg)
{
  return vision_interfaces::msg::to_yaml(msg);
}

template<>
inline const char * data_type<vision_interfaces::msg::VisionStatus>()
{
  return "vision_interfaces::msg::VisionStatus";
}

template<>
inline const char * name<vision_interfaces::msg::VisionStatus>()
{
  return "vision_interfaces/msg/VisionStatus";
}

template<>
struct has_fixed_size<vision_interfaces::msg::VisionStatus>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<vision_interfaces::msg::VisionStatus>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<vision_interfaces::msg::VisionStatus>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__TRAITS_HPP_
