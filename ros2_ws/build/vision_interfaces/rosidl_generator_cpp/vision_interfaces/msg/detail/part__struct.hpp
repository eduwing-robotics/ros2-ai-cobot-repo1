// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from vision_interfaces:msg/Part.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/part.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__PART__STRUCT_HPP_
#define VISION_INTERFACES__MSG__DETAIL__PART__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


#ifndef _WIN32
# define DEPRECATED__vision_interfaces__msg__Part __attribute__((deprecated))
#else
# define DEPRECATED__vision_interfaces__msg__Part __declspec(deprecated)
#endif

namespace vision_interfaces
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct Part_
{
  using Type = Part_<ContainerAllocator>;

  explicit Part_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->name = "";
      this->class_id = 0l;
      this->score = 0.0f;
      this->x = 0l;
      this->y = 0l;
      this->width = 0l;
      this->height = 0l;
      this->angle_deg = 0.0f;
      this->angle_valid = false;
      this->depth_m = 0.0f;
      this->depth_valid = false;
      this->camera_x_m = 0.0f;
      this->camera_y_m = 0.0f;
      this->camera_z_m = 0.0f;
      this->position_valid = false;
    }
  }

  explicit Part_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : name(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->name = "";
      this->class_id = 0l;
      this->score = 0.0f;
      this->x = 0l;
      this->y = 0l;
      this->width = 0l;
      this->height = 0l;
      this->angle_deg = 0.0f;
      this->angle_valid = false;
      this->depth_m = 0.0f;
      this->depth_valid = false;
      this->camera_x_m = 0.0f;
      this->camera_y_m = 0.0f;
      this->camera_z_m = 0.0f;
      this->position_valid = false;
    }
  }

  // field types and members
  using _name_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _name_type name;
  using _class_id_type =
    int32_t;
  _class_id_type class_id;
  using _score_type =
    float;
  _score_type score;
  using _x_type =
    int32_t;
  _x_type x;
  using _y_type =
    int32_t;
  _y_type y;
  using _width_type =
    int32_t;
  _width_type width;
  using _height_type =
    int32_t;
  _height_type height;
  using _angle_deg_type =
    float;
  _angle_deg_type angle_deg;
  using _angle_valid_type =
    bool;
  _angle_valid_type angle_valid;
  using _depth_m_type =
    float;
  _depth_m_type depth_m;
  using _depth_valid_type =
    bool;
  _depth_valid_type depth_valid;
  using _camera_x_m_type =
    float;
  _camera_x_m_type camera_x_m;
  using _camera_y_m_type =
    float;
  _camera_y_m_type camera_y_m;
  using _camera_z_m_type =
    float;
  _camera_z_m_type camera_z_m;
  using _position_valid_type =
    bool;
  _position_valid_type position_valid;

  // setters for named parameter idiom
  Type & set__name(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->name = _arg;
    return *this;
  }
  Type & set__class_id(
    const int32_t & _arg)
  {
    this->class_id = _arg;
    return *this;
  }
  Type & set__score(
    const float & _arg)
  {
    this->score = _arg;
    return *this;
  }
  Type & set__x(
    const int32_t & _arg)
  {
    this->x = _arg;
    return *this;
  }
  Type & set__y(
    const int32_t & _arg)
  {
    this->y = _arg;
    return *this;
  }
  Type & set__width(
    const int32_t & _arg)
  {
    this->width = _arg;
    return *this;
  }
  Type & set__height(
    const int32_t & _arg)
  {
    this->height = _arg;
    return *this;
  }
  Type & set__angle_deg(
    const float & _arg)
  {
    this->angle_deg = _arg;
    return *this;
  }
  Type & set__angle_valid(
    const bool & _arg)
  {
    this->angle_valid = _arg;
    return *this;
  }
  Type & set__depth_m(
    const float & _arg)
  {
    this->depth_m = _arg;
    return *this;
  }
  Type & set__depth_valid(
    const bool & _arg)
  {
    this->depth_valid = _arg;
    return *this;
  }
  Type & set__camera_x_m(
    const float & _arg)
  {
    this->camera_x_m = _arg;
    return *this;
  }
  Type & set__camera_y_m(
    const float & _arg)
  {
    this->camera_y_m = _arg;
    return *this;
  }
  Type & set__camera_z_m(
    const float & _arg)
  {
    this->camera_z_m = _arg;
    return *this;
  }
  Type & set__position_valid(
    const bool & _arg)
  {
    this->position_valid = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    vision_interfaces::msg::Part_<ContainerAllocator> *;
  using ConstRawPtr =
    const vision_interfaces::msg::Part_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<vision_interfaces::msg::Part_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<vision_interfaces::msg::Part_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      vision_interfaces::msg::Part_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<vision_interfaces::msg::Part_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      vision_interfaces::msg::Part_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<vision_interfaces::msg::Part_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<vision_interfaces::msg::Part_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<vision_interfaces::msg::Part_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__vision_interfaces__msg__Part
    std::shared_ptr<vision_interfaces::msg::Part_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__vision_interfaces__msg__Part
    std::shared_ptr<vision_interfaces::msg::Part_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const Part_ & other) const
  {
    if (this->name != other.name) {
      return false;
    }
    if (this->class_id != other.class_id) {
      return false;
    }
    if (this->score != other.score) {
      return false;
    }
    if (this->x != other.x) {
      return false;
    }
    if (this->y != other.y) {
      return false;
    }
    if (this->width != other.width) {
      return false;
    }
    if (this->height != other.height) {
      return false;
    }
    if (this->angle_deg != other.angle_deg) {
      return false;
    }
    if (this->angle_valid != other.angle_valid) {
      return false;
    }
    if (this->depth_m != other.depth_m) {
      return false;
    }
    if (this->depth_valid != other.depth_valid) {
      return false;
    }
    if (this->camera_x_m != other.camera_x_m) {
      return false;
    }
    if (this->camera_y_m != other.camera_y_m) {
      return false;
    }
    if (this->camera_z_m != other.camera_z_m) {
      return false;
    }
    if (this->position_valid != other.position_valid) {
      return false;
    }
    return true;
  }
  bool operator!=(const Part_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct Part_

// alias to use template instance with default allocator
using Part =
  vision_interfaces::msg::Part_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace vision_interfaces

#endif  // VISION_INTERFACES__MSG__DETAIL__PART__STRUCT_HPP_
