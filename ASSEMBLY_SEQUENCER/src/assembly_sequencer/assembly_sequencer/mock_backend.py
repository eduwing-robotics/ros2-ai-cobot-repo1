"""Semantic assembly client for the existing Mock ROS service."""

import json
import random
import threading
import time
import uuid

from fairino_msgs.srv import RemoteCmdInterface
from rclpy.task import Future

from .recipe_contract import DEFECT_TYPES


SERVICE_TIMEOUT_SECONDS = 5.0
OPERATION_TIMEOUT_SECONDS = 600.0
CONVEYOR_SIGNAL_TIMEOUT_SECONDS = 60.0


class MockBackend:
    def __init__(self, node, client):
        self._node = node
        self._client = client
        self._operation_id = None
        self._operation_job_id = None
        self._operation_future = None
        self._timeout_lock = threading.Lock()
        self._paused_job_id = None
        self._operation_remaining_seconds = 0.0
        self._operation_running_since = None
        self._conveyor_future = None
        self._conveyor_job_id = None
        self._conveyor_unit_id = None
        self._conveyor_operation_id = None
        self._conveyor_station = None
        self._assembled_pcb = None
        self._rng = random.Random()
        self._fail_probability = 0.2

    def configure_inspection(self, probability, seed):
        if isinstance(probability, bool) or not 0.0 <= float(probability) <= 1.0:
            raise ValueError("inspection_fail_probability must be between 0 and 1")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("random_seed must be an integer")
        self._fail_probability = float(probability)
        self._rng = random.Random(None if seed == -1 else seed)

    async def prepare(self, joint_points, frame):
        # Observations are validated by the common recipe boundary before claim.
        snapshot = await self.status()
        if not snapshot.get("available", False) or snapshot.get("active", False):
            raise RuntimeError("Mock equipment is unavailable or already active")

    async def resolve_targets(self, observations):
        return observations

    async def move_conveyor(self, job_id, station, *, unit_id, operation_id, on_ready):
        if station not in {"ASSEMBLY", "INSPECTION"} or self._conveyor_future is not None:
            raise RuntimeError("another conveyor action is pending or station is invalid")
        future = Future(executor=self._node.executor)
        self._conveyor_future = future
        self._conveyor_job_id = job_id
        self._conveyor_station = station
        self._conveyor_unit_id = unit_id
        self._conveyor_operation_id = operation_id
        if station == "ASSEMBLY":
            self._assembled_pcb = None

        def expire():
            # Timer and service callbacks run on different executor threads. A timeout
            # and arrival must settle the wait atomically; rclpy permits set_result after cancel.
            with self._timeout_lock:
                future.cancel()

        timer = self._node.create_timer(CONVEYOR_SIGNAL_TIMEOUT_SECONDS, expire)
        try:
            # Register the waiter before exposing the movement to the external caller.
            on_ready()
            await future
            if future.cancelled():
                raise TimeoutError("conveyor completion was not reported within 60 seconds")
        finally:
            self._node.destroy_timer(timer)
            self._conveyor_future = None
            self._conveyor_job_id = None
            self._conveyor_station = None
            self._conveyor_unit_id = None
            self._conveyor_operation_id = None

    def confirm_conveyor(self, job_id, station, *, unit_id, operation_id, assembled_pcb=None):
        with self._timeout_lock:
            future = self._conveyor_future
            if (job_id != self._conveyor_job_id or station != self._conveyor_station
                    or unit_id != self._conveyor_unit_id or operation_id != self._conveyor_operation_id
                    or future is None):
                raise RuntimeError("matching conveyor movement is not awaiting completion")
            if future.cancelled():
                raise RuntimeError("conveyor completion deadline has expired")
            if future.done() and future.exception() is not None:
                raise RuntimeError("conveyor movement has already failed")
            if not future.done():
                if station == "INSPECTION":
                    if assembled_pcb is None:
                        raise ValueError("inspection arrival requires assembled PCB coordinates")
                    self._assembled_pcb = assembled_pcb
                future.set_result(None)

    def fail_conveyor(self, job_id, message, *, unit_id, operation_id):
        with self._timeout_lock:
            future = self._conveyor_future
            if (job_id != self._conveyor_job_id or unit_id != self._conveyor_unit_id
                    or operation_id != self._conveyor_operation_id or future is None
                    or future.cancelled() or future.done()):
                raise RuntimeError("matching conveyor movement is not awaiting completion")
            future.set_exception(RuntimeError(message))

    async def inspect_unit(self, job_id, unit_id, slot_codes):
        result, defects = choose_inspection(self._rng, self._fail_probability, slot_codes)
        return {"result": result, "defects": defects,
                "image_path": "InspectionSamples/mock-pass.jpg" if result == "PASS"
                else "InspectionSamples/mock-fail.jpg"}

    def close(self):
        with self._timeout_lock:
            for future in (self._conveyor_future, self._operation_future):
                if future is not None and not future.done():
                    future.cancel()

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
        if snapshot.get("runtime_mode") != "mock":
            raise RuntimeError("MODE_REJECTED stage=backend_status expected=mock result=blocked")
        return snapshot

    async def start(self, job_id, recipe_version, expected_step_count):
        await self._require_accepted({
            "command": "start",
            "job_id": job_id,
            "recipe_version": recipe_version,
            "expected_step_count": expected_step_count,
        }, "internal Mock assembly rejected the request")
        with self._timeout_lock:
            self._paused_job_id = None

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
        assembled_pcb = self._assembled_pcb if assembled_pcb is None else assembled_pcb
        if assembled_pcb is None:
            raise RuntimeError("assembled PCB coordinates have not been confirmed")
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
        with self._timeout_lock:
            if paused and self._paused_job_id != job_id:
                self._paused_job_id = job_id
                if self._operation_job_id == job_id and self._operation_running_since is not None:
                    self._operation_remaining_seconds -= time.monotonic() - self._operation_running_since
                    self._operation_running_since = None
            elif not paused and self._paused_job_id == job_id:
                self._paused_job_id = None
                if self._operation_job_id == job_id and self._operation_future is not None:
                    self._operation_running_since = time.monotonic()

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
            with self._timeout_lock:
                self._operation_remaining_seconds = OPERATION_TIMEOUT_SECONDS
                self._operation_running_since = (
                    None if self._paused_job_id == job_id else time.monotonic()
                )

            def check_timeout():
                # Pause/resume and timer callbacks can run on different executor threads.
                # Count only running time; repeated pauses must not renew the 600s budget.
                with self._timeout_lock:
                    running_since = self._operation_running_since
                    if (self._operation_future is future and running_since is not None
                            and time.monotonic() - running_since >= self._operation_remaining_seconds):
                        future.cancel()

            # Expire within one timer tick after the remaining running-time budget is spent.
            timeout_timer = self._node.create_timer(1.0, check_timeout)
            await future
            if future.cancelled():
                raise RuntimeError(f"internal Mock {action} operation timed out")
        finally:
            if timeout_timer is not None:
                self._node.destroy_timer(timeout_timer)
            with self._timeout_lock:
                if self._operation_id == operation_id:
                    self._operation_id = None
                    self._operation_job_id = None
                    self._operation_future = None
                    self._operation_running_since = None

    async def _require_accepted(self, payload, fallback_message):
        result = parse_internal_response((await self._call(payload)).cmd_res)
        if not result["accepted"]:
            raise RuntimeError(result.get("message") or fallback_message)

    async def _call(self, payload):
        if not self._client.wait_for_service(timeout_sec=SERVICE_TIMEOUT_SECONDS):
            raise RuntimeError("internal Mock assembly service is unavailable")
        request = RemoteCmdInterface.Request()
        request.cmd_str = "mock\n" + json.dumps(payload, separators=(",", ":"))
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


def choose_inspection(rng, fail_probability, slot_codes):
    if rng.random() >= fail_probability:
        return "PASS", []
    if not slot_codes:
        raise RuntimeError("Mock FAIL inspection requires a product slot")
    return "FAIL", [{
        "slot_code": rng.choice(slot_codes),
        "defect_type": rng.choice(DEFECT_TYPES),
    }]


def parse_internal_response(raw):
    try:
        response = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Mock response is not valid JSON") from error
    if not isinstance(response, dict) or not isinstance(response.get("accepted"), bool):
        raise RuntimeError("Mock response is missing accepted")
    return response
