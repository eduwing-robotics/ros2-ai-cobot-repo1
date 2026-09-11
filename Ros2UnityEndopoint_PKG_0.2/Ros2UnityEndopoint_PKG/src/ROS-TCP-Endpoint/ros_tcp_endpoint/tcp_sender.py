#  Copyright 2020 Unity Technologies
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import rclpy
import socket
import time
import threading
import json
from collections import deque

from rclpy.node import Node
from rclpy.serialization import deserialize_message
from rclpy.serialization import serialize_message

from .client import ClientThread
from .thread_pauser import ThreadPauser

# queue module was renamed between python 2 and 3
try:
    from queue import Empty
except:
    from Queue import Empty


class _LatestMessageQueue:
    """A bounded queue that keeps the newest item for each keyed stream.

    Camera frames are much more useful when they are current.  A regular
    unbounded ``Queue`` lets a slow Unity TCP client accumulate old JPEGs and
    eventually sends seconds-old frames.  Keyed entries replace the pending
    frame for the same topic while control messages remain FIFO.  The hard
    bound also protects the endpoint when a client disappears without closing
    its socket cleanly.
    """

    def __init__(self, max_entries=128):
        self._items = deque()
        self._max_entries = max_entries
        self._condition = threading.Condition()
        self._closed = False

    def put(self, item, key=None):
        with self._condition:
            if self._closed:
                return False

            if key is not None:
                # Keep the original position so a control message that was
                # already ahead of the frame is not reordered.
                items = list(self._items)
                for index, (old_key, _) in enumerate(items):
                    if old_key == key:
                        items[index] = (key, item)
                        self._items = deque(items)
                        self._condition.notify()
                        return True

            if len(self._items) >= self._max_entries:
                # A keyed camera entry normally prevents this path.  If a
                # client is stalled by control traffic, discard the oldest
                # pending packet instead of blocking ROS callbacks.
                self._items.popleft()
            self._items.append((key, item))
            self._condition.notify()
            return True

    def get(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while not self._items:
                if self._closed:
                    raise Empty
                if deadline is None:
                    self._condition.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Empty
                self._condition.wait(remaining)
            return self._items.popleft()[1]

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()


class UnityTcpSender:
    """
    Sends messages to Unity.
    """

    def __init__(self, tcp_server):
        # super().__init__(f'UnityTcpSender')

        self.sender_id = 1
        self.time_between_halt_checks = 5
        self.tcp_server = tcp_server

        # Every Unity TCP client gets an independent queue.  The previous
        # implementation stored one global queue and silently redirected all
        # ROS messages to whichever client connected last.
        self.queues = {}
        self.queue_lock = threading.RLock()

        # variables needed for matching up unity service requests with responses
        self.next_srv_id = 1001
        self.srv_lock = threading.Lock()
        self.services_waiting = {}

    @property
    def queue(self):
        """Return the newest client queue for compatibility with old callers."""
        with self.queue_lock:
            if not self.queues:
                return None
            return self.queues[max(self.queues)]

    def _enqueue(self, serialized_bytes, key=None, client_ids=None):
        with self.queue_lock:
            if client_ids is None:
                queues = list(self.queues.values())
            else:
                queues = [
                    self.queues[client_id]
                    for client_id in set(client_ids)
                    if client_id in self.queues
                ]
        for client_queue in queues:
            client_queue.put(serialized_bytes, key=key)

    def send_unity_info(self, text, client_id=None):
        command = SysCommand_Log()
        command.text = text
        serialized_bytes = ClientThread.serialize_command("__log", command)
        self._enqueue(
            serialized_bytes,
            client_ids=None if client_id is None else [client_id],
        )

    def send_unity_warning(self, text, client_id=None):
        command = SysCommand_Log()
        command.text = text
        serialized_bytes = ClientThread.serialize_command("__warn", command)
        self._enqueue(
            serialized_bytes,
            client_ids=None if client_id is None else [client_id],
        )

    def send_unity_error(self, text, client_id=None):
        command = SysCommand_Log()
        command.text = text
        serialized_bytes = ClientThread.serialize_command("__error", command)
        self._enqueue(
            serialized_bytes,
            client_ids=None if client_id is None else [client_id],
        )

    def send_ros_service_response(self, srv_id, destination, response, client_id=None):
        command = SysCommand_Service()
        command.srv_id = srv_id
        serialized_header = ClientThread.serialize_command("__response", command)
        serialized_message = ClientThread.serialize_message(destination, response)
        self._enqueue(
            b"".join([serialized_header, serialized_message]),
            key="__response:{}".format(srv_id),
            client_ids=None if client_id is None else [client_id],
        )

    def send_unity_message(self, topic, message, client_ids=None):
        serialized_message = ClientThread.serialize_message(topic, message)
        # A camera stream is keyed by topic, so each client has at most one
        # pending frame.  This keeps latency bounded during conveyor traffic.
        self._enqueue(serialized_message, key="topic:{}".format(topic), client_ids=client_ids)

    def send_unity_service_request(self, topic, service_class, request):
        with self.queue_lock:
            if not self.queues:
                return None
            # Unity service requests originate from ROS and have no client
            # context in the existing API.  Preserve the old behavior by
            # sending them to the newest connected client only.
            target_client_id = max(self.queues)
        thread_pauser = ThreadPauser()
        with self.srv_lock:
            srv_id = self.next_srv_id
            self.next_srv_id += 1
            self.services_waiting[srv_id] = thread_pauser

        command = SysCommand_Service()
        command.srv_id = srv_id
        serialized_header = ClientThread.serialize_command("__request", command)
        serialized_message = ClientThread.serialize_message(topic, request)
        self._enqueue(
            b"".join([serialized_header, serialized_message]),
            key="__request:{}:{}".format(topic, srv_id),
            client_ids=[target_client_id],
        )

        # rospy starts a new thread for each service request,
        # so it won't break anything if we sleep now while waiting for the response
        thread_pauser.sleep_until_resumed()

        response = deserialize_message(thread_pauser.result, service_class.Response())
        return response

    def send_unity_service_response(self, srv_id, data):
        thread_pauser = None
        with self.srv_lock:
            thread_pauser = self.services_waiting[srv_id]
            del self.services_waiting[srv_id]

        thread_pauser.resume_with_result(data)

    def get_registered_topic(self, topic):
        if topic in self.tcp_server.publishers_table:
            return self.tcp_server.publishers_table[topic]
        elif topic in self.tcp_server.subscribers_table:
            return self.tcp_server.subscribers_table[topic]
        elif topic in self.tcp_server.ros_services_table:
            return self.tcp_server.ros_services_table[topic]
        elif topic in self.tcp_server.unity_services_table:
            return self.tcp_server.unity_services_table[topic]
        else:
            return None

    def send_topic_list(self, client_id=None):
        topic_list = SysCommand_TopicsResponse()
        topics_and_types = self.tcp_server.get_topic_names_and_types()
        topic_list.topics = [item[0] for item in topics_and_types]
        for i in topics_and_types:
            node = self.get_registered_topic(i[0])
            if len(i[1]) > 1:
                if node is not None:
                    self.tcp_server.get_logger().warning(
                        "Only one message type per topic is supported, but found multiple types for topic {}; maintaining {} as the subscribed type.".format(
                            i[0], self.parse_message_name(node.msg)
                        )
                    )
        topic_list.types = [
            item[1][0].replace("/msg/", "/")
            if (len(item[1]) <= 1)
            else self.parse_message_name(
                self.get_registered_topic(item[0]).msg
            )
            if self.get_registered_topic(item[0]) is not None
            else item[1][0].replace("/msg/", "/")
            for item in topics_and_types
        ]
        serialized_bytes = ClientThread.serialize_command("__topic_list", topic_list)
        self._enqueue(
            serialized_bytes,
            client_ids=None if client_id is None else [client_id],
        )

    def start_sender(self, conn, halt_event):
        local_queue = _LatestMessageQueue()
        # Put the handshake before making the queue visible so a newly
        # connected client always receives protocol metadata first.
        handshake_metadata = SysCommand_Handshake_Metadata()
        handshake = SysCommand_Handshake(handshake_metadata)
        local_queue.put(ClientThread.serialize_command("__handshake", handshake), key="__handshake")

        with self.queue_lock:
            client_id = self.sender_id
            self.sender_id += 1
            self.queues[client_id] = local_queue

        sender_thread = threading.Thread(
            target=self.sender_loop, args=(conn, client_id, local_queue, halt_event)
        )

        # Exit the server thread when the main thread terminates
        sender_thread.daemon = True
        sender_thread.start()
        return client_id

    def sender_loop(self, conn, tid, local_queue, halt_event):
        try:
            while not halt_event.is_set():
                try:
                    item = local_queue.get(timeout=self.time_between_halt_checks)
                except Empty:
                    # I'd like to just wait on the queue, but we also need to check occasionally for the connection being closed
                    # (otherwise the thread never terminates.)
                    continue

                # print("Sender {} sending an item".format(tid))

                try:
                    conn.sendall(item)
                except Exception as e:
                    self.tcp_server.logerr("Exception {}".format(e))
                    break
        finally:
            halt_event.set()
            with self.queue_lock:
                if self.queues.get(tid) is local_queue:
                    del self.queues[tid]
            local_queue.close()

    def parse_message_name(self, name):
        try:
            # Example input string: <class 'std_msgs.msg._string.Metaclass_String'>
            names = (str(type(name))).split(".")
            module_name = names[0][8:]
            class_name = names[-1].split("_")[-1][:-2]
            return "{}/{}".format(module_name, class_name)
        except (IndexError, AttributeError, ImportError) as e:
            self.tcp_server.logerr("Failed to resolve message name: {}".format(e))
            return None


class SysCommand_Log:
    def __init__(self):
        text = ""


class SysCommand_Service:
    def __init__(self):
        srv_id = 0


class SysCommand_TopicsResponse:
    def __init__(self):
        topics = []
        types = []


class SysCommand_Handshake:
    def __init__(self, metadata):
        self.version = "v0.7.0"
        self.metadata = json.dumps(metadata.__dict__)


class SysCommand_Handshake_Metadata:
    def __init__(self):
        self.protocol = "ROS2"
