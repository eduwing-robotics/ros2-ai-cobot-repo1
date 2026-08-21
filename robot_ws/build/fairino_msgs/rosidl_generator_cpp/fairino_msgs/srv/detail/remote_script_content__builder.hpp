// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from fairino_msgs:srv/RemoteScriptContent.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "fairino_msgs/srv/remote_script_content.hpp"


#ifndef FAIRINO_MSGS__SRV__DETAIL__REMOTE_SCRIPT_CONTENT__BUILDER_HPP_
#define FAIRINO_MSGS__SRV__DETAIL__REMOTE_SCRIPT_CONTENT__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "fairino_msgs/srv/detail/remote_script_content__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace fairino_msgs
{

namespace srv
{

namespace builder
{

class Init_RemoteScriptContent_Request_line_str
{
public:
  Init_RemoteScriptContent_Request_line_str()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  ::fairino_msgs::srv::RemoteScriptContent_Request line_str(::fairino_msgs::srv::RemoteScriptContent_Request::_line_str_type arg)
  {
    msg_.line_str = std::move(arg);
    return std::move(msg_);
  }

private:
  ::fairino_msgs::srv::RemoteScriptContent_Request msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::fairino_msgs::srv::RemoteScriptContent_Request>()
{
  return fairino_msgs::srv::builder::Init_RemoteScriptContent_Request_line_str();
}

}  // namespace fairino_msgs


namespace fairino_msgs
{

namespace srv
{

namespace builder
{

class Init_RemoteScriptContent_Response_res
{
public:
  Init_RemoteScriptContent_Response_res()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  ::fairino_msgs::srv::RemoteScriptContent_Response res(::fairino_msgs::srv::RemoteScriptContent_Response::_res_type arg)
  {
    msg_.res = std::move(arg);
    return std::move(msg_);
  }

private:
  ::fairino_msgs::srv::RemoteScriptContent_Response msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::fairino_msgs::srv::RemoteScriptContent_Response>()
{
  return fairino_msgs::srv::builder::Init_RemoteScriptContent_Response_res();
}

}  // namespace fairino_msgs


namespace fairino_msgs
{

namespace srv
{

namespace builder
{

class Init_RemoteScriptContent_Event_response
{
public:
  explicit Init_RemoteScriptContent_Event_response(::fairino_msgs::srv::RemoteScriptContent_Event & msg)
  : msg_(msg)
  {}
  ::fairino_msgs::srv::RemoteScriptContent_Event response(::fairino_msgs::srv::RemoteScriptContent_Event::_response_type arg)
  {
    msg_.response = std::move(arg);
    return std::move(msg_);
  }

private:
  ::fairino_msgs::srv::RemoteScriptContent_Event msg_;
};

class Init_RemoteScriptContent_Event_request
{
public:
  explicit Init_RemoteScriptContent_Event_request(::fairino_msgs::srv::RemoteScriptContent_Event & msg)
  : msg_(msg)
  {}
  Init_RemoteScriptContent_Event_response request(::fairino_msgs::srv::RemoteScriptContent_Event::_request_type arg)
  {
    msg_.request = std::move(arg);
    return Init_RemoteScriptContent_Event_response(msg_);
  }

private:
  ::fairino_msgs::srv::RemoteScriptContent_Event msg_;
};

class Init_RemoteScriptContent_Event_info
{
public:
  Init_RemoteScriptContent_Event_info()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_RemoteScriptContent_Event_request info(::fairino_msgs::srv::RemoteScriptContent_Event::_info_type arg)
  {
    msg_.info = std::move(arg);
    return Init_RemoteScriptContent_Event_request(msg_);
  }

private:
  ::fairino_msgs::srv::RemoteScriptContent_Event msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::fairino_msgs::srv::RemoteScriptContent_Event>()
{
  return fairino_msgs::srv::builder::Init_RemoteScriptContent_Event_info();
}

}  // namespace fairino_msgs

#endif  // FAIRINO_MSGS__SRV__DETAIL__REMOTE_SCRIPT_CONTENT__BUILDER_HPP_
