"""Semantic assembly client for the existing Mock ROS service."""

import json
import uuid

from fairino_msgs.srv import RemoteCmdInterface
from rclpy.task import Future

from .mock_contract import parse_internal_response


SERVICE_TIMEOUT_SECONDS = 5.0
OPERATION_TIMEOUT_SECONDS = 600.0


class MockBackend:
    def __init__(self, node, client):
        self._node = node
        self._client = client
        self._operation_id = None
        self._operation_job_id = None
        self._operation_future = None

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

    async def start(self, job_id, recipe_version, expected_step_count):
        await self._require_accepted({
            "command": "start",
            "job_id": job_id,
            "recipe_version": recipe_version,
            "expected_step_count": expected_step_count,
        }, "internal Mock assembly rejected the request")

    async def move_joint(self, job_id, joint_point):
        await self._execute(job_id, "robot.move_joint", {
            "joint_point": joint_point,
        })

    async def pick(self, job_id, step, frame, source, motion, gripper):
        await self._execute(job_id, "robot.pick", {
            "step": step,
            "frame": frame,
            "source": source,
            "approach_dz_mm": motion["approach_dz_mm"],
            "retract_dz_mm": motion["retract_dz_mm"],
            "gripper": gripper,
        })

    async def place(self, job_id, step, frame, target, motion, gripper):
        await self._execute(job_id, "robot.place", {
            "step": step,
            "frame": frame,
            "target": target,
            "approach_dz_mm": motion["approach_dz_mm"],
            "retract_dz_mm": motion["retract_dz_mm"],
            "gripper": gripper,
        })

    async def transfer_assembled_pcb(
        self, job_id, frame, assembled_pcb, motion, gripper
    ):
        await self._execute(job_id, "robot.transfer", {
            "frame": frame,
            "source": assembled_pcb["source"],
            "target": assembled_pcb["target"],
            "approach_dz_mm": motion["approach_dz_mm"],
            "retract_dz_mm": motion["retract_dz_mm"],
            "drop_approach_dz_mm": motion[
                "assembled_pcb_drop_approach_dz_mm"
            ],
            "gripper": gripper,
        })

    async def set_paused(self, job_id, paused):
        await self._require_accepted({
            "command": "pause" if paused else "resume",
            "job_id": job_id,
        }, "internal Mock pause request was rejected")

    def accept_operation_feedback(self, payload):
        operation_id = payload.get("operation_id")
        if operation_id is None:
            return False
        future = self._operation_future
        if (operation_id != self._operation_id
                or payload["job_id"] != self._operation_job_id
                or future is None):
            self._node.get_logger().warning(
                f"ignored stale Mock operation feedback: {operation_id}"
            )
            return True
        if future.done():
            return True
        if payload["state"] == "COMPLETED":
            future.set_result(None)
        elif payload["state"] == "FAILED":
            future.set_exception(RuntimeError(
                payload["message"] or "internal Mock operation failed"
            ))
        else:
            future.set_exception(RuntimeError(
                f"invalid Mock operation result state: {payload['state']}"
            ))
        return True

    async def _execute(self, job_id, action, arguments):
        if self._operation_future is not None:
            raise RuntimeError("another Mock operation is already pending")
        operation_id = str(uuid.uuid4())
        future = Future(executor=self._node.executor)
        self._operation_id = operation_id
        self._operation_job_id = job_id
        self._operation_future = future
        timeout_timer = None
        try:
            await self._require_accepted({
                "command": "execute",
                "job_id": job_id,
                "operation_id": operation_id,
                "action": action,
                "arguments": arguments,
            }, f"internal Mock {action} request was rejected")
            timeout_timer = self._node.create_timer(
                OPERATION_TIMEOUT_SECONDS, future.cancel
            )
            await future
            if future.cancelled():
                raise RuntimeError(f"internal Mock {action} operation timed out")
        finally:
            if timeout_timer is not None:
                self._node.destroy_timer(timeout_timer)
            if self._operation_id == operation_id:
                self._operation_id = None
                self._operation_job_id = None
                self._operation_future = None

    async def _require_accepted(self, payload, fallback_message):
        result = parse_internal_response((await self._call(payload)).cmd_res)
        if not result["accepted"]:
            raise RuntimeError(result.get("message") or fallback_message)

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
