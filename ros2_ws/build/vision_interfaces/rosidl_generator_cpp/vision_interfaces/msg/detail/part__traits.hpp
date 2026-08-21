// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from vision_interfaces:msg/Part.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/part.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__PART__TRAITS_HPP_
#define VISION_INTERFACES__MSG__DETAIL__PART__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "vision_interfaces/msg/detail/part__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace vision_interfaces
{

namespace msg
{

inline void to_flow_style_yaml(
  const Part & msg,
  std::ostream & out)
{
  out << "{";
  // member: name
  {
    out << "name: ";
    rosidl_generator_traits::value_to_yaml(msg.name, out);
    out << ", ";
  }

  // member: class_id
  {
    out << "class_id: ";
    rosidl_generator_traits::value_to_yaml(msg.class_id, out);
    out << ", ";
  }

  // member: score
  {
    out << "score: ";
    rosidl_generator_traits::value_to_yaml(msg.score, out);
    out << ", ";
  }

  // member: x
  {
    out << "x: ";
    rosidl_generator_traits::value_to_yaml(msg.x, out);
    out << ", ";
  }

  // member: y
  {
    out << "y: ";
    rosidl_generator_traits::value_to_yaml(msg.y, out);
    out << ", ";
  }

  // member: width
  {
    out << "width: ";
    rosidl_generator_traits::value_to_yaml(msg.width, out);
    out << ", ";
  }

  // member: height
  {
    out << "height: ";
    rosidl_generator_traits::value_to_yaml(msg.height, out);
    out << ", ";
  }

  // member: angle_deg
  {
    out << "angle_deg: ";
    rosidl_generator_traits::value_to_yaml(msg.angle_deg, out);
    out << ", ";
  }

  // member: angle_valid
  {
    out << "angle_valid: ";
    rosidl_generator_traits::value_to_yaml(msg.angle_valid, out);
    out << ", ";
  }

  // member: depth_m
  {
    out << "depth_m: ";
    rosidl_generator_traits::value_to_yaml(msg.depth_m, out);
    out << ", ";
  }

  // member: depth_valid
  {
    out << "depth_valid: ";
    rosidl_generator_traits::value_to_yaml(msg.depth_valid, out);
    out << ", ";
  }

  // member: camera_x_m
  {
    out << "camera_x_m: ";
    rosidl_generator_traits::value_to_yaml(msg.camera_x_m, out);
    out << ", ";
  }

  // member: camera_y_m
  {
    out << "camera_y_m: ";
    rosidl_generator_traits::value_to_yaml(msg.camera_y_m, out);
    out << ", ";
  }

  // member: camera_z_m
  {
    out << "camera_z_m: ";
    rosidl_generator_traits::value_to_yaml(msg.camera_z_m, out);
    out << ", ";
  }

  // member: position_valid
  {
    out << "position_valid: ";
    rosidl_generator_traits::value_to_yaml(msg.position_valid, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const Part & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: name
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "name: ";
    rosidl_generator_traits::value_to_yaml(msg.name, out);
    out << "\n";
  }

  // member: class_id
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "class_id: ";
    rosidl_generator_traits::value_to_yaml(msg.class_id, out);
    out << "\n";
  }

  // member: score
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "score: ";
    rosidl_generator_traits::value_to_yaml(msg.score, out);
    out << "\n";
  }

  // member: x
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "x: ";
    rosidl_generator_traits::value_to_yaml(msg.x, out);
    out << "\n";
  }

  // member: y
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "y: ";
    rosidl_generator_traits::value_to_yaml(msg.y, out);
    out << "\n";
  }

  // member: width
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "width: ";
    rosidl_generator_traits::value_to_yaml(msg.width, out);
    out << "\n";
  }

  // member: height
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "height: ";
    rosidl_generator_traits::value_to_yaml(msg.height, out);
    out << "\n";
  }

  // member: angle_deg
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "angle_deg: ";
    rosidl_generator_traits::value_to_yaml(msg.angle_deg, out);
    out << "\n";
  }

  // member: angle_valid
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "angle_valid: ";
    rosidl_generator_traits::value_to_yaml(msg.angle_valid, out);
    out << "\n";
  }

  // member: depth_m
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "depth_m: ";
    rosidl_generator_traits::value_to_yaml(msg.depth_m, out);
    out << "\n";
  }

  // member: depth_valid
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "depth_valid: ";
    rosidl_generator_traits::value_to_yaml(msg.depth_valid, out);
    out << "\n";
  }

  // member: camera_x_m
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "camera_x_m: ";
    rosidl_generator_traits::value_to_yaml(msg.camera_x_m, out);
    out << "\n";
  }

  // member: camera_y_m
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "camera_y_m: ";
    rosidl_generator_traits::value_to_yaml(msg.camera_y_m, out);
    out << "\n";
  }

  // member: camera_z_m
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "camera_z_m: ";
    rosidl_generator_traits::value_to_yaml(msg.camera_z_m, out);
    out << "\n";
  }

  // member: position_valid
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "position_valid: ";
    rosidl_generator_traits::value_to_yaml(msg.position_valid, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const Part & msg, bool use_flow_style = false)
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
  const vision_interfaces::msg::Part & msg,
  std::ostream & out, size_t indentation = 0)
{
  vision_interfaces::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use vision_interfaces::msg::to_yaml() instead")]]
inline std::string to_yaml(const vision_interfaces::msg::Part & msg)
{
  return vision_interfaces::msg::to_yaml(msg);
}

template<>
inline const char * data_type<vision_interfaces::msg::Part>()
{
  return "vision_interfaces::msg::Part";
}

template<>
inline const char * name<vision_interfaces::msg::Part>()
{
  return "vision_interfaces/msg/Part";
}

template<>
struct has_fixed_size<vision_interfaces::msg::Part>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<vision_interfaces::msg::Part>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<vision_interfaces::msg::Part>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // VISION_INTERFACES__MSG__DETAIL__PART__TRAITS_HPP_
