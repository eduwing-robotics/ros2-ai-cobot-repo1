// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from vision_interfaces:msg/Detections.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/detections.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__DETECTIONS__STRUCT_HPP_
#define VISION_INTERFACES__MSG__DETAIL__DETECTIONS__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__struct.hpp"
// Member 'parts'
#include "vision_interfaces/msg/detail/part__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__vision_interfaces__msg__Detections __attribute__((deprecated))
#else
# define DEPRECATED__vision_interfaces__msg__Detections __declspec(deprecated)
#endif

namespace vision_interfaces
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct Detections_
{
  using Type = Detections_<ContainerAllocator>;

  explicit Detections_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->camera = "";
      this->image_width = 0ul;
      this->image_height = 0ul;
    }
  }

  explicit Detections_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_alloc, _init),
    camera(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->camera = "";
      this->image_width = 0ul;
      this->image_height = 0ul;
    }
  }

  // field types and members
  using _header_type =
    std_msgs::msg::Header_<ContainerAllocator>;
  _header_type header;
  using _camera_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _camera_type camera;
  using _image_width_type =
    uint32_t;
  _image_width_type image_width;
  using _image_height_type =
    uint32_t;
  _image_height_type image_height;
  using _parts_type =
    std::vector<vision_interfaces::msg::Part_<ContainerAllocator>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<vision_interfaces::msg::Part_<ContainerAllocator>>>;
  _parts_type parts;

  // setters for named parameter idiom
  Type & set__header(
    const std_msgs::msg::Header_<ContainerAllocator> & _arg)
  {
    this->header = _arg;
    return *this;
  }
  Type & set__camera(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->camera = _arg;
    return *this;
  }
  Type & set__image_width(
    const uint32_t & _arg)
  {
    this->image_width = _arg;
    return *this;
  }
  Type & set__image_height(
    const uint32_t & _arg)
  {
    this->image_height = _arg;
    return *this;
  }
  Type & set__parts(
    const std::vector<vision_interfaces::msg::Part_<ContainerAllocator>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<vision_interfaces::msg::Part_<ContainerAllocator>>> & _arg)
  {
    this->parts = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    vision_interfaces::msg::Detections_<ContainerAllocator> *;
  using ConstRawPtr =
    const vision_interfaces::msg::Detections_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<vision_interfaces::msg::Detections_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<vision_interfaces::msg::Detections_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      vision_interfaces::msg::Detections_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<vision_interfaces::msg::Detections_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      vision_interfaces::msg::Detections_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<vision_interfaces::msg::Detections_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<vision_interfaces::msg::Detections_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<vision_interfaces::msg::Detections_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__vision_interfaces__msg__Detections
    std::shared_ptr<vision_interfaces::msg::Detections_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__vision_interfaces__msg__Detections
    std::shared_ptr<vision_interfaces::msg::Detections_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const Detections_ & other) const
  {
    if (this->header != other.header) {
      return false;
    }
    if (this->camera != other.camera) {
      return false;
    }
    if (this->image_width != other.image_width) {
      return false;
    }
    if (this->image_height != other.image_height) {
      return false;
    }
    if (this->parts != other.parts) {
      return false;
    }
    return true;
  }
  bool operator!=(const Detections_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct Detections_

// alias to use template instance with default allocator
using Detections =
  vision_interfaces::msg::Detections_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace vision_interfaces

#endif  // VISION_INTERFACES__MSG__DETAIL__DETECTIONS__STRUCT_HPP_
