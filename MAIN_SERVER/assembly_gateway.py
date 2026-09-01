"""Thin ROS2 client for MainServer AssemblySequencer status route."""
import json
import threading


SERVICE_NAME = "/unity/assembly/start"
SERVICE_TIMEOUT_SECONDS = 5.0


class GatewayUnavailable(RuntimeError):
    """The ROS2 runtime or assembly bridge cannot answer a request."""


class GatewayResponseError(RuntimeError):
    """The assembly bridge returned a response outside its JSON contract."""


class AssemblyGateway:
    """Query the existing assembly bridge without importing ROS2 at API import time."""

    def __init__(self, timeout_seconds=SERVICE_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()

    def status(self):
        """Return the current assembly snapshot."""
        return self._call('{"command":"status"}')

    def _call(self, command_json):
        """Forward one original JSON command and return its JSON object response."""
        with self._lock:
            try:
                import rclpy
                from fairino_msgs.srv import RemoteCmdInterface
            except ImportError as error:
                raise GatewayUnavailable("ROS2 runtime is unavailable") from error

            node = None
            try:
                if not rclpy.ok():
                    rclpy.init(args=None)
                node = rclpy.create_node("main_server_assembly_gateway")
                client = node.create_client(RemoteCmdInterface, SERVICE_NAME)
                if not client.wait_for_service(timeout_sec=self.timeout_seconds):
                    raise GatewayUnavailable("assembly bridge service is unavailable")
                request = RemoteCmdInterface.Request()
                request.cmd_str = command_json
                future = client.call_async(request)
                rclpy.spin_until_future_complete(
                    node, future, timeout_sec=self.timeout_seconds
                )
                if not future.done():
                    raise GatewayUnavailable("assembly bridge service timed out")
                response = future.result()
                if response is None:
                    raise GatewayUnavailable("assembly bridge service failed")
                return self._parse_response(response.cmd_res)
            except GatewayUnavailable:
                raise
            except Exception as error:
                raise GatewayUnavailable("assembly bridge service failed") from error
            finally:
                if node is not None:
                    node.destroy_node()

    @staticmethod
    def _parse_response(raw):
        try:
            response = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise GatewayResponseError("assembly bridge response is not valid JSON") from error
        if not isinstance(response, dict):
            raise GatewayResponseError("assembly bridge response must be a JSON object")
        return response
