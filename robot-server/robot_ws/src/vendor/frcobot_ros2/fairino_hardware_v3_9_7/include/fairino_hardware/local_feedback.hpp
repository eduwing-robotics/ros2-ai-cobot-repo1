#pragma once
// Same-host control feedback. DDS remains available to remote observers.
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <endian.h>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <rclcpp/serialization.hpp>
#include <rclcpp/serialized_message.hpp>

class LocalFeedbackSender {
 public:
  LocalFeedbackSender() {
    const char* name = std::getenv("KSMC_LOCAL_FEEDBACK_SOCKET");
    if (!name || !*name) return;
    const auto length = std::strlen(name);
    if (length > sizeof(address_.sun_path)-2) throw std::runtime_error("local feedback socket name too long");
    address_.sun_family = AF_UNIX;
    std::memcpy(address_.sun_path+1, name, length);
    address_length_ = offsetof(sockaddr_un, sun_path)+1+length;
    fd_ = socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (fd_ < 0) throw std::runtime_error("cannot create local feedback socket");
    instance_ = monotonic_ns();
  }
  ~LocalFeedbackSender() { if (fd_ >= 0) close(fd_); }
  LocalFeedbackSender(const LocalFeedbackSender&) = delete;
  LocalFeedbackSender& operator=(const LocalFeedbackSender&) = delete;
  static uint64_t monotonic_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
  }
  template<class Message> void send(const Message& message) {
    if (fd_ < 0) return;
    const auto stamp = monotonic_ns();
    rclcpp::Serialization<Message> serializer;
    rclcpp::SerializedMessage serialized;
    serializer.serialize_message(&message, &serialized);
    const auto& cdr = serialized.get_rcl_serialized_message();
    unsigned char header[40];
    std::memcpy(header, "FR5FB002", 8);
    const uint64_t instance = htobe64(instance_), sequence = htobe64(++sequence_), timestamp = htobe64(stamp);
    const uint32_t length = htobe32(static_cast<uint32_t>(cdr.buffer_length));
    std::memcpy(header+8, &instance, 8); std::memcpy(header+16, &sequence, 8);
    std::memcpy(header+24, &timestamp, 8); std::memcpy(header+32, &length, 4);
    // Bit 0 certifies this compiled driver implements per-command blending.
    const uint32_t capabilities = htobe32(1U);
    std::memcpy(header+36, &capabilities, 4);
    iovec vectors[2]{{header, sizeof(header)}, {cdr.buffer, cdr.buffer_length}};
    msghdr packet{}; packet.msg_name=&address_; packet.msg_namelen=address_length_;
    packet.msg_iov=vectors; packet.msg_iovlen=2;
    // Never wait for a missing/full receiver. Missing samples cannot refresh API age.
    (void)sendmsg(fd_, &packet, MSG_DONTWAIT | MSG_NOSIGNAL);
  }
 private:
  int fd_{-1}; sockaddr_un address_{}; socklen_t address_length_{0};
  uint64_t instance_{0}, sequence_{0};
};
