"""High-level client for the existing Mock assembly ROS service."""

import json

from fairino_msgs.srv import RemoteCmdInterface

from .mock_contract import parse_internal_response


SERVICE_TIMEOUT_SECONDS = 5.0


class MockBackend:
    def __init__(self, node, client):
        self._node = node
        self._client = client

    def is_available(self):
        return self._client.wait_for_service(timeout_sec=0.0)

    async def status(self):
        response = await self._call({"command": "status"})
        try:
            snapshot = json.loads(response.cmd_res)
        except (TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("Mock status response is not valid JSON") from error
        if not isinstance(snapshot, dict):
            raise RuntimeError("Mock status response must be an object")
        return snapshot

    async def start(self, command):
        result = parse_internal_response((await self._call(command)).cmd_res)
        if not result["accepted"]:
            raise RuntimeError(
                result.get("message") or "internal Mock assembly rejected the request"
            )

    async def transfer_assembled_pcb(self, job_id, assembled_pcb):
        result = parse_internal_response((await self._call({
            "command": "transfer_assembled_pcb",
            "job_id": job_id,
            "assembled_pcb": assembled_pcb,
        })).cmd_res)
        if not result["accepted"]:
            raise RuntimeError(
                result.get("message") or "internal Mock PCB transfer was rejected"
            )

    async def _call(self, payload):
        if not self._client.wait_for_service(timeout_sec=SERVICE_TIMEOUT_SECONDS):
            raise RuntimeError("internal Mock assembly service is unavailable")
        request = RemoteCmdInterface.Request()
        request.cmd_str = json.dumps(payload, separators=(",", ":"))
        response_future = self._client.call_async(request)
        timeout_timer = self._node.create_timer(
            SERVICE_TIMEOUT_SECONDS, response_future.cancel
        )
        try:
            response = await response_future
            if response_future.cancelled():
                raise RuntimeError("internal Mock assembly service timed out")
            if response is None:
                raise RuntimeError("internal Mock assembly service failed")
            return response
        finally:
            self._node.destroy_timer(timeout_timer)
