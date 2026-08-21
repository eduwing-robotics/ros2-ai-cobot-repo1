// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from vision_interfaces:msg/VisionStatus.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "vision_interfaces/msg/vision_status.hpp"


#ifndef VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__STRUCT_HPP_
#define VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__STRUCT_HPP_

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

#ifndef _WIN32
# define DEPRECATED__vision_interfaces__msg__VisionStatus __attribute__((deprecated))
#else
# define DEPRECATED__vision_interfaces__msg__VisionStatus __declspec(deprecated)
#endif

namespace vision_interfaces
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct VisionStatus_
{
  using Type = VisionStatus_<ContainerAllocator>;

  explicit VisionStatus_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->ready = false;
      this->model_loaded = false;
      this->inference_count = 0ull;
      this->message = "";
    }
  }

  explicit VisionStatus_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_alloc, _init),
    message(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->ready = false;
      this->model_loaded = false;
      this->inference_count = 0ull;
      this->message = "";
    }
  }

  // field types and members
  using _header_type =
    std_msgs::msg::Header_<ContainerAllocator>;
  _header_type header;
  using _ready_type =
    bool;
  _ready_type ready;
  using _model_loaded_type =
    bool;
  _model_loaded_type model_loaded;
  using _cameras_type =
    std::vector<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>>>;
  _cameras_type cameras;
  using _active_cameras_type =
    std::vector<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>>>;
  _active_cameras_type active_cameras;
  using _missing_cameras_type =
    std::vector<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>>>;
  _missing_cameras_type missing_cameras;
  using _inference_count_type =
    uint64_t;
  _inference_count_type inference_count;
  using _message_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _message_type message;

  // setters for named parameter idiom
  Type & set__header(
    const std_msgs::msg::Header_<ContainerAllocator> & _arg)
  {
    this->header = _arg;
    return *this;
  }
  Type & set__ready(
    const bool & _arg)
  {
    this->ready = _arg;
    return *this;
  }
  Type & set__model_loaded(
    const bool & _arg)
  {
    this->model_loaded = _arg;
    return *this;
  }
  Type & set__cameras(
    const std::vector<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>>> & _arg)
  {
    this->cameras = _arg;
    return *this;
  }
  Type & set__active_cameras(
    const std::vector<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>>> & _arg)
  {
    this->active_cameras = _arg;
    return *this;
  }
  Type & set__missing_cameras(
    const std::vector<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>>> & _arg)
  {
    this->missing_cameras = _arg;
    return *this;
  }
  Type & set__inference_count(
    const uint64_t & _arg)
  {
    this->inference_count = _arg;
    return *this;
  }
  Type & set__message(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->message = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    vision_interfaces::msg::VisionStatus_<ContainerAllocator> *;
  using ConstRawPtr =
    const vision_interfaces::msg::VisionStatus_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<vision_interfaces::msg::VisionStatus_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<vision_interfaces::msg::VisionStatus_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      vision_interfaces::msg::VisionStatus_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<vision_interfaces::msg::VisionStatus_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      vision_interfaces::msg::VisionStatus_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<vision_interfaces::msg::VisionStatus_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<vision_interfaces::msg::VisionStatus_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<vision_interfaces::msg::VisionStatus_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__vision_interfaces__msg__VisionStatus
    std::shared_ptr<vision_interfaces::msg::VisionStatus_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__vision_interfaces__msg__VisionStatus
    std::shared_ptr<vision_interfaces::msg::VisionStatus_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const VisionStatus_ & other) const
  {
    if (this->header != other.header) {
      return false;
    }
    if (this->ready != other.ready) {
      return false;
    }
    if (this->model_loaded != other.model_loaded) {
      return false;
    }
    if (this->cameras != other.cameras) {
      return false;
    }
    if (this->active_cameras != other.active_cameras) {
      return false;
    }
    if (this->missing_cameras != other.missing_cameras) {
      return false;
    }
    if (this->inference_count != other.inference_count) {
      return false;
    }
    if (this->message != other.message) {
      return false;
    }
    return true;
  }
  bool operator!=(const VisionStatus_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct VisionStatus_

// alias to use template instance with default allocator
using VisionStatus =
  vision_interfaces::msg::VisionStatus_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace vision_interfaces

#endif  // VISION_INTERFACES__MSG__DETAIL__VISION_STATUS__STRUCT_HPP_
