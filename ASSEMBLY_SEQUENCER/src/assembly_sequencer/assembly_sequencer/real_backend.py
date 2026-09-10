"""Real orchestration API client and Vision HTTP boundary; no hardware drivers."""

import hashlib
import http.client
import json
import math
import os
import threading
import time
import uuid
from urllib.parse import urlsplit
from pathlib import Path

from . import api_contracts as api


class RealBackend:
    """Use documented equipment APIs only; never fall back to raw robot commands."""

    def __init__(self, node):
        from rclpy.callback_groups import ReentrantCallbackGroup
        from std_srvs.srv import Trigger
        from std_msgs.msg import String

        if node.runtime_mode != "real" or node.context.get_domain_id() != 5:
            raise RuntimeError("MODE_REJECTED stage=real_backend expected=real/domain5 result=blocked")
        self._node = node
        self._closed = False
        self._inspection_future = None
        self._pending_calls = set()
        self._lock = threading.RLock()
        self._conveyor_state = None
        self._conveyor_received = 0.0
        self._execution_id = None
        self._execution_response = None
        self._execution_server = None
        self._execution_sequence = -1
        self._pending_control = None
        self._execution_detached = False
        self._control_status = None
        self._control_status_received = 0.0
        self._control_sequence = 0
        self._assembly_status_client = node.create_client(
            Trigger, api.ASSEMBLY_STATUS, callback_group=ReentrantCallbackGroup())
        self._assembly_command = node.create_publisher(String, api.ASSEMBLY_COMMAND, 10)
        self._assembly_subscription = node.create_subscription(
            String, api.ASSEMBLY_EVENT, self._receive_execution, 100,
            callback_group=ReentrantCallbackGroup())
        self._conveyor_subscription = node.create_subscription(
            String, api.CONVEYOR_STATE, self._receive_conveyor, 10,
            callback_group=ReentrantCallbackGroup())
        self._conveyor_assembly = node.create_client(
            Trigger, api.CONVEYOR_ASSEMBLY, callback_group=ReentrantCallbackGroup())
        self._conveyor_inspection = node.create_client(
            Trigger, api.CONVEYOR_INSPECTION, callback_group=ReentrantCallbackGroup())
        self._conveyor_stop = node.create_client(
            Trigger, api.CONVEYOR_STOP, callback_group=ReentrantCallbackGroup())
        self._vision_url = node.declare_parameter("vision_base_url", os.environ.get("VISION_BASE_URL", "")).value
        self._status_client = node.create_client(
            Trigger, api.ROBOT_STATUS, callback_group=ReentrantCallbackGroup()
        )

    def is_available(self):
        return not self._closed and self._status_client.wait_for_service(timeout_sec=0.0)

    @staticmethod
    def _connection_error():
        return "Production readiness or a required equipment completion contract is unavailable."

    async def status(self):
        from .recipe_contract import unavailable_snapshot

        snapshot = unavailable_snapshot("")
        snapshot.update(runtime_mode="real", equipment_ready=False,
                        command_service_available=self.is_available())
        robot = await self._read_status(self._status_client)
        assembly = await self._read_status(self._assembly_status_client)
        snapshot["robot_api_status"] = robot
        snapshot["production_contract"] = assembly.get("production_contract")
        try:
            self._validate_readiness(robot, assembly)
            snapshot.update(available=True, equipment_ready=True, error_code="", message="")
        except RuntimeError as error:
            snapshot.update(error_code="NOT_READY", message=str(error))
        return snapshot

    def _validate_readiness(self, robot, assembly):
        production = assembly.get("production_contract", {})
        if (production.get("schema") != api.ASSEMBLY_SCHEMA or
                production.get("capabilities", {}).get("start") is not True):
            raise RuntimeError("Robot production v2 Start is unavailable.")
        if (assembly.get("hardware_execution_enabled") is not True or
                robot.get("hardware_execution_enabled") is not True or
                robot.get("state_fresh") is not True or robot.get("robot_health_clear") is not True or
                robot.get("robot_mode") != 0 or robot.get("robot_motion_done") != 1 or
                robot.get("recovery_required") is not False or robot.get("active_operation") is not None or
                ("held_candidate" not in robot or robot["held_candidate"] is not None and robot["held_candidate"] is not False) or
                production.get("equipment_busy_or_unresolved") is True or
                production.get("recovery_required") is True or
                production.get("status", "idle") not in {"idle", "failed_recovered", "failed_before_motion",
                    "motion_complete_awaiting_physical_verification"}):
            raise RuntimeError("Robot is busy, stale, holding a part, or requires recovery.")
        if not isinstance(production.get("current_recipe_revision"), str) or not production["current_recipe_revision"]:
            raise RuntimeError("Robot production recipe revision is missing.")
        self._ready_conveyor()
        origin = urlsplit(self._vision_url)
        if origin.scheme not in {"http", "https"} or not origin.hostname or origin.username or origin.password or origin.path not in {"", "/"} or origin.query or origin.fragment:
            raise RuntimeError("vision_base_url must identify the Real inspection HTTP origin.")
        token = os.environ.get("KSMC_VISION_API_TOKEN", "")
        if len(token) < 32 or not token.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in token):
            raise RuntimeError("KSMC_VISION_API_TOKEN must be configured on the Sequencer.")
        if not os.environ.get("DEFECT_IMAGE_ROOT", "").strip():
            raise RuntimeError("DEFECT_IMAGE_ROOT must identify shared execution and inspection storage.")
        return production["current_recipe_revision"]

    async def prepare_execution(self, recipe_version):
        if recipe_version != "assembly-r1":
            raise RuntimeError("Production recipe has no deployed robot binding.")
        robot = await self._read_status(self._status_client)
        assembly = await self._read_status(self._assembly_status_client)
        return self._validate_readiness(robot, assembly)

    async def _read_status(self, client):
        from rclpy.callback_groups import ReentrantCallbackGroup
        from std_srvs.srv import Trigger

        if self._closed or not client.wait_for_service(timeout_sec=0.0):
            raise RuntimeError("Equipment status service unavailable.")
        future = client.call_async(Trigger.Request())
        self._pending_calls.add(future)
        # The start service holds its default callback group while awaiting this response.
        # Its timeout must be able to run independently in that interval.
        timer = self._node.create_timer(api.SERVICE_TIMEOUT_SECONDS, future.cancel, callback_group=ReentrantCallbackGroup())
        try:
            response = await future
            if future.cancelled():
                raise TimeoutError("Equipment service response timed out; execution is unconfirmed.")
            if not response.success:
                raise RuntimeError(f"Equipment request rejected: {response.message}")
            data = json.loads(response.message)
            if not isinstance(data, dict):
                raise ValueError("Equipment response must be a JSON object.")
            return data
        finally:
            self._pending_calls.discard(future)
            self._node.destroy_timer(timer)

    def _receive_conveyor(self, message):
        try:
            state = json.loads(message.data)
            if not isinstance(state, dict) or state.get("schema_version") != api.CONVEYOR_SCHEMA_VERSION:
                return
            with self._lock:
                self._conveyor_state = state
                self._conveyor_received = time.monotonic()
        except (ValueError, TypeError):
            return

    def _ready_conveyor(self):
        with self._lock:
            state = self._conveyor_state
            age = time.monotonic() - self._conveyor_received
        if state is None or age > api.CONVEYOR_FRESHNESS_SECONDS:
            raise RuntimeError("Conveyor state heartbeat is unavailable or stale.")
        if (state.get("state") not in {"IDLE", "ASSEMBLY_STOP", "INSPECTION_STOP"} or
                state.get("moving") is not False or state.get("armed") is not True or
                state.get("vision_ready_fresh") is not True or state.get("vision_ready") is not True):
            raise RuntimeError("Conveyor interlocks or stationary state are not ready.")
        required = state.get("fr5_interlock_required")
        if type(required) is not bool or (required and
                (state.get("fr5_clear") is not True or state.get("fr5_clear_fresh") is not True)):
            raise RuntimeError("Conveyor FR5 interlock requirement is unknown or not satisfied.")
        if not state.get("server_instance_id"):
            raise RuntimeError("Conveyor server identity is missing.")
        return state

    async def _wait_tick(self):
        from rclpy.task import Future

        future = Future(executor=self._node.executor)
        def wake():
            if not future.done():
                future.set_result(None)
        timer = self._node.create_timer(api.WAIT_TICK_SECONDS, wake)
        try:
            await future
            if self._closed:
                raise RuntimeError("SAFETY_STOP: backend closed; equipment state is unconfirmed.")
        finally:
            self._node.destroy_timer(timer)

    async def move_conveyor(self, station):
        if station not in {"ASSEMBLY", "INSPECTION"}:
            raise ValueError("Unknown conveyor station.")
        before = self._ready_conveyor()
        client = self._conveyor_assembly if station == "ASSEMBLY" else self._conveyor_inspection
        # Trigger success only accepts a move. Never retry a move with an unknown
        # response: Trigger has no caller-supplied idempotency key.
        try:
            accepted = await self._read_status(client)
            motion_id = accepted.get("motion_id")
            if not isinstance(motion_id, str) or not motion_id or motion_id == before.get("motion_id"):
                raise RuntimeError("Conveyor acceptance has no new motion_id.")
            deadline = time.monotonic() + api.CONVEYOR_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                with self._lock:
                    state = self._conveyor_state
                    age = time.monotonic() - self._conveyor_received
                if age > api.CONVEYOR_FRESHNESS_SECONDS or state.get("server_instance_id") != before["server_instance_id"]:
                    raise RuntimeError("Conveyor heartbeat lost or server restarted.")
                if state.get("state") in {"FAULT", "MANUAL_STOP"}:
                    raise RuntimeError("Conveyor stopped: " + str(state.get("reason", "")))
                arrival = state.get("arrival") or {}
                if (state.get("motion_id") == motion_id and arrival.get("motion_id") == motion_id and
                        arrival.get("station") == station.lower() and state.get("state") == station + "_STOP" and
                        state.get("moving") is False):
                    return state
                await self._wait_tick()
            raise TimeoutError("Conveyor arrival timed out.")
        except Exception as error:
            # Best-effort HOLD uses the provider's existing safety endpoint. Its
            # acceptance is not encoder-based physical stop verification.
            try:
                await self._read_status(self._conveyor_stop)
            except Exception:
                pass
            raise RuntimeError("SAFETY_STOP: " + str(error)) from error

    async def confirm_conveyor_stopped(self):
        # Cancellation observes stop directly; motion readiness is not required.
        with self._lock:
            before = self._conveyor_state
        if not before or not before.get("server_instance_id"):
            raise RuntimeError("Conveyor identity is unavailable")
        sent_at = time.monotonic()
        await self._read_status(self._conveyor_stop)
        deadline = sent_at + api.CONTROL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            with self._lock:
                state, received = self._conveyor_state, self._conveyor_received
            if state and state.get("server_instance_id") != before["server_instance_id"]:
                raise RuntimeError("Conveyor server changed during cancellation")
            if (state and received > sent_at and
                    time.monotonic() - received <= api.CONVEYOR_FRESHNESS_SECONDS and
                    state.get("state") in {"IDLE", "ASSEMBLY_STOP", "INSPECTION_STOP", "MANUAL_STOP"} and
                    state.get("moving") is False and
                    type(state.get("command_linear_x_mps")) in (int, float) and
                    state["command_linear_x_mps"] == 0):
                return state
            await self._wait_tick()
        raise TimeoutError("Conveyor stop remains unconfirmed")

    async def request_control(self, execution_id, action):
        from std_msgs.msg import String

        if action not in {"pause", "resume", "cancel"}:
            raise ValueError("Unsupported production control")
        await self.reconcile_control()
        with self._lock:
            if self._execution_id != execution_id:
                raise RuntimeError("No matching execution")
            if self._execution_detached and action != "cancel":
                raise RuntimeError("Execution tracking stopped; only cancellation is available")
            pending = self._pending_control
            if pending is not None:
                if pending["request"]["action"] == "assembly." + action:
                    return pending["request"]
                raise RuntimeError("Another control confirmation is pending")
        status = await self._read_status(self._assembly_status_client)
        data = status.get("production_contract", {})
        if (data.get("execution_id") != execution_id or
                data.get("server_instance_id") != self._execution_server or
                data.get("capabilities", {}).get(action) is not True or
                data.get("recovery_required") is not False):
            raise RuntimeError("Production control unavailable for this execution")
        if action == "resume" and (data.get("status") != "paused" or
                data.get("resume_available") is not True or not data.get("pause_control_id")):
            raise RuntimeError("Matching confirmed pause is required before resume")
        with self._lock:
            if self._execution_id != execution_id or self._pending_control is not None:
                raise RuntimeError("Execution changed while preparing control")
            self._control_sequence += 1
            request = dict(schema=api.ASSEMBLY_SCHEMA, action="assembly." + action,
                execution_id=execution_id, control_id=str(uuid.uuid4()), control_sequence=self._control_sequence)
            if action == "resume":
                request["pause_control_id"] = data["pause_control_id"]
            self._pending_control = dict(request=request, sent_at=time.monotonic(), rejection=None)
        # Keep the identity on an uncertain send. Never create a second control implicitly.
        self._assembly_command.publish(String(data=json.dumps(request)))
        return request

    def release_cancelled_execution(self):
        with self._lock:
            data = self._control_status or {}
            if (data.get("execution_id") != self._execution_id or data.get("status") != "cancelled" or
                    data.get("stop_verified") is not True or data.get("recovery_required") is not False):
                raise RuntimeError("Confirmed cancellation is required before releasing execution")
            self._execution_id = None
            self._pending_control = None
            self._execution_detached = False

    @property
    def execution_tracking_stopped(self):
        return self._execution_detached

    def control_reason(self, execution_id, action, paused):
        with self._lock:
            if self._execution_id != execution_id:
                return "원격 실행 연결을 확인할 수 없습니다."
            if self._execution_detached and action != "cancel":
                return "실행 추적 중단 후에는 취소만 가능합니다."
            data = self._control_status
            if data is None or time.monotonic() - self._control_status_received > api.CONTROL_STATUS_FRESHNESS_SECONDS:
                return "최신 원격 제어 상태를 확인 중입니다."
            if data.get("capabilities", {}).get(action) is not True or data.get("recovery_required") is not False:
                return "장비가 해당 제어를 지원하지 않거나 복구가 필요합니다."
            if action == "resume" and (data.get("status") != "paused" or data.get("resume_available") is not True):
                return "장비가 재개 가능한 일시정지를 확인하지 않았습니다."
            pending = self._pending_control
            if pending:
                return "" if pending["request"]["action"] == "assembly." + action else "이전 제어 결과를 확인 중입니다."
            if action == "resume" and not paused:
                return "일시정지된 작업이 아닙니다."
            if action == "pause" and paused:
                return "이미 보류 또는 일시정지 상태입니다."
            return ""

    async def reconcile_control(self):
        from std_msgs.msg import String

        with self._lock:
            execution_id, server = self._execution_id, self._execution_server
            pending, generation = self._pending_control, self._control_sequence
            if execution_id is None:
                return None
        status = await self._read_status(self._assembly_status_client)
        data = status.get("production_contract", {})
        with self._lock:
            # Reentrant helpers below apply the response under this same lock. Never
            # hold it across network I/O; a replaced execution/control invalidates the reply.
            if (self._execution_id != execution_id or self._execution_server != server or
                    self._pending_control is not pending or self._control_sequence != generation):
                raise RuntimeError("Local execution/control changed during reconciliation")
            if (data.get("schema") != api.ASSEMBLY_SCHEMA or data.get("execution_id") != execution_id or
                    data.get("server_instance_id") != server):
                raise RuntimeError("Execution identity changed during control reconciliation")
            sequence = data.get("event_sequence")
            if type(sequence) is int and sequence < self._execution_sequence:
                raise RuntimeError("Control status predates the latest execution event")
            self._control_status = data
            self._control_status_received = time.monotonic()
            result = self.control_progress(data)
            self._receive_execution(String(data=json.dumps(data)))
            return result

    def control_progress(self, data):
        with self._lock:
            pending = self._pending_control
            if pending is None:
                return data
            request = pending["request"]
            last = data.get("last_control") or {}
            identity = data.get("control_id") or (last.get("control_id") if isinstance(last, dict) else None)
            action = request["action"]
            matches = identity == request["control_id"]
            if action == "assembly.pause":
                matches = matches or data.get("pause_control_id") == request["control_id"]
            confirmed = matches and (
                action == "assembly.pause" and data.get("status") == "paused" and
                data.get("stop_verified") is True and data.get("resume_available") is True or
                action == "assembly.resume" and data.get("status") == "running" or
                action == "assembly.cancel" and data.get("status") == "cancelled" and
                data.get("stop_verified") is True and data.get("recovery_required") is False)
            if confirmed:
                self._pending_control = None
                return data
            rejection = pending.get("rejection")
            # Only a rejection attributable to this exact control can release its lock.
            last_rejected = matches and isinstance(last, dict) and last.get("request_accepted") is False
            if (rejection and rejection.get("control_id") == request["control_id"]) or last_rejected:
                self._pending_control = None
                return dict(data, control_error=(rejection or last).get("message", "Control rejected"))
            if rejection or time.monotonic() - pending["sent_at"] > api.CONTROL_TIMEOUT_SECONDS:
                return dict(data, control_error=(rejection or {}).get("message", "Control confirmation timed out; state is unconfirmed"))
            return dict(data, control_pending=action)

    @staticmethod
    def _terminal(data):
        return (data.get("request_accepted") is False or
                data.get("event") in {"EXECUTION_COMPLETED", "EXECUTION_FAILED", "REQUEST_REJECTED", "EXECUTION_CANCELLED"} or
                data.get("status") in {"request_rejected", "failed_before_motion", "failed_recovered", "recovery_required", "cancelled"})

    def _receive_execution(self, message):
        try:
            data = json.loads(message.data)
            if not isinstance(data, dict) or data.get("schema") != api.ASSEMBLY_SCHEMA:
                return
            with self._lock:
                if self._execution_id is None or data.get("execution_id") != self._execution_id:
                    return
                if data.get("request_accepted") is False and self._pending_control is not None:
                    self._pending_control["rejection"] = data
                    return
                if self._execution_response is not None and self._terminal(self._execution_response):
                    return
                # Rejections can omit both event_sequence and server identity.
                server = data.get("server_instance_id")
                if server and self._execution_server and server != self._execution_server:
                    self._execution_response = dict(data, event="EXECUTION_FAILED", recovery_required=True,
                        error_code="SERVER_RESTARTED", error_message="Robot execution server changed.")
                    return
                sequence = data.get("event_sequence")
                if type(sequence) is int:
                    if sequence < self._execution_sequence:
                        return
                    self._execution_sequence = sequence
                self._execution_response = data
        except (ValueError, TypeError):
            return

    @staticmethod
    def _validate_completion(data, request, slot_codes):
        identities = ("execution_id", "production_job_id", "unit_id", "product_id",
                      "production_recipe_version", "robot_recipe_revision")
        if type(data.get("unit_id")) is not int or any(data.get(k) != request[k] for k in identities):
            raise ValueError("Assembly completion identity does not match its request.")
        expected, completed = data.get("expected_slots"), data.get("completed_slots")
        if (not isinstance(expected, list) or not isinstance(completed, list) or
                any(not isinstance(s, str) for s in expected + completed) or
                len(expected) != len(slot_codes) or len(completed) != len(slot_codes) or
                set(expected) != set(slot_codes) or set(completed) != set(slot_codes)):
            raise ValueError("Assembly completion slots do not match the production recipe.")
        hashes = data.get("plan_hashes", {})
        if (data.get("event") != "EXECUTION_COMPLETED" or
                data.get("status") != "motion_complete_awaiting_physical_verification" or
                data.get("stop_verified") is not True or data.get("recovery_required") is not False or
                "held_candidate" not in data or
                (data["held_candidate"] is not None and data["held_candidate"] is not False) or
                data.get("plan_complete") is not True or not isinstance(hashes, dict)):
            raise ValueError("Assembly completion has no verified stop/plan/empty-gripper evidence.")
        for kind in ("non-smd", "smd"):
            value = hashes.get(kind)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Assembly completion plan hash is invalid.")

    async def execute_assembly(self, job_id, unit_id, recipe_version, revision,
                               confirmation, slot_codes, on_progress):
        from std_msgs.msg import String
        from .recipe_contract import validate_scene_confirmation, PRODUCTION_PRODUCT_CODE

        if type(unit_id) is not int or unit_id <= 0 or str(uuid.UUID(job_id)) != job_id:
            raise ValueError("Execution requires a canonical Job UUID and positive Unit ID.")
        validate_scene_confirmation(confirmation)
        robot = await self._read_status(self._status_client)
        assembly = await self._read_status(self._assembly_status_client)
        if self._validate_readiness(robot, assembly) != revision:
            raise RuntimeError("Robot recipe revision changed after Job preparation.")
        validate_scene_confirmation(confirmation)
        request = dict(schema=api.ASSEMBLY_SCHEMA, action="assembly.start",
            execution_id=str(uuid.UUID(confirmation["execution_id"])), production_job_id=job_id,
            unit_id=unit_id, product_id=PRODUCTION_PRODUCT_CODE,
            production_recipe_version=recipe_version, robot_recipe_revision=revision,
            scene_confirmation=dict(confirmation))
        request["scene_confirmation"]["execution_id"] = request["execution_id"]
        directory = Path(os.environ["DEFECT_IMAGE_ROOT"]) / "executions" / str(unit_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "request.json"
        # Save before publication. Restart recovery fails this Unit instead of
        # constructing a new identity for a possibly executed request.
        encoded = json.dumps(request, sort_keys=True)
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if path.read_text(encoding="utf-8") != encoded:
                raise RuntimeError("An execution request already exists for this Unit.")
        if self._assembly_command.get_subscription_count() == 0:
            raise RuntimeError("Robot Start command subscriber unavailable.")
        with self._lock:
            if self._execution_id is not None:
                raise RuntimeError("Another robot execution is already pending.")
            self._execution_id = request["execution_id"]
            self._execution_response = None
            self._execution_server = assembly["production_contract"].get("server_instance_id")
            self._execution_sequence = -1
        sent = False
        try:
            sent = True
            self._assembly_command.publish(String(data=encoded))
            deadline = time.monotonic() + api.ASSEMBLY_TIMEOUT_SECONDS
            next_query = time.monotonic() + api.ASSEMBLY_POLL_SECONDS
            previous = None
            while time.monotonic() < deadline:
                with self._lock:
                    data = self._execution_response
                if data is not None and data is not previous:
                    with (directory / "events.jsonl").open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(data) + "\n")
                    previous = data
                    data = self.control_progress(data)
                    if data.get("event") == "EXECUTION_COMPLETED":
                        if self._pending_control is not None:
                            raise RuntimeError("SAFETY_STOP: assembly ended before control reconciliation")
                        self._validate_completion(data, request, slot_codes)
                        on_progress(data)
                        return data
                    if data.get("event") == "EXECUTION_CANCELLED" or data.get("status") == "cancelled":
                        if (self._pending_control is not None or data.get("stop_verified") is not True or
                                data.get("recovery_required") is not False):
                            raise RuntimeError("SAFETY_STOP: cancellation stop is unconfirmed")
                        error = RuntimeError("Production execution cancelled and stopped")
                        error.error_code = "EXECUTION_CANCELLED"
                        raise error
                    if self._terminal(data):
                        failure = data.get("failure") or {}
                        code = data.get("error_code") or failure.get("code") or "ASSEMBLY_FAILED"
                        stage = data.get("failed_stage") or failure.get("stage") or data.get("current_stage") or ""
                        message = data.get("error_message") or data.get("message") or failure.get("message") or "Robot execution failed."
                        detail = f"{code} stage={stage}: {message}"
                        if data.get("recovery_required") is True:
                            detail = "SAFETY_STOP: " + detail
                        error = RuntimeError(detail)
                        error.error_code = code
                        raise error
                    on_progress(data)
                if time.monotonic() >= next_query:
                    status = await self._read_status(self._assembly_status_client)
                    production = status.get("production_contract", {})
                    if production.get("execution_id") not in (None, request["execution_id"]):
                        raise RuntimeError("Robot status changed to another execution.")
                    self._receive_execution(String(data=json.dumps(production)))
                    next_query = time.monotonic() + api.ASSEMBLY_POLL_SECONDS
                await self._wait_tick()
            raise TimeoutError("Robot completion timed out; remote execution may continue.")
        except Exception as error:
            with self._lock:
                response = self._execution_response
            if sent and not (response and self._terminal(response) and
                             response.get("event") != "EXECUTION_COMPLETED" and
                             response.get("recovery_required") is not True):
                if not str(error).startswith("SAFETY_STOP:"):
                    raise RuntimeError("SAFETY_STOP: " + str(error)) from error
            raise
        finally:
            with self._lock:
                response = self._execution_response
                unresolved = sent and not (response and self._terminal(response) and
                    response.get("recovery_required") is not True)
                self._execution_detached = unresolved
                if not unresolved:
                    self._execution_id = None
                    self._pending_control = None

    async def inspect_unit(self, job_id, unit_id, slot_codes):
        from rclpy.task import Future

        if self._closed or self._inspection_future is not None:
            raise RuntimeError("Real backend is closed or another inspection is pending")
        future = Future(executor=self._node.executor)
        self._inspection_future = future
        inspection_id = str(uuid.uuid5(uuid.UUID(job_id), f"unit:{unit_id}"))

        def run():
            try:
                output = inspect(inspection_id, job_id, unit_id, base_url=self._vision_url)
                data = output["data"]
                value = {
                    "result": data["result"]["decision"], "defects": None,
                    "image_path": None, "inspection": data,
                    "image_bytes": output["image_bytes"],
                }
                if not future.done():
                    future.set_result(value)
            except Exception as error:
                if not future.done():
                    future.set_exception(error)

        # Vision capture and HTTP polling must not block the ROS executor. The
        # existing inspect function retries only the same inspection identity;
        # cancelling this local Future does not cancel the remote inspection.
        threading.Thread(target=run, name="real-vision-inspection", daemon=True).start()
        try:
            return await future
        finally:
            if self._inspection_future is future:
                self._inspection_future = None

    def close(self):
        if self._closed:
            return
        self._closed = True
        for future in tuple(self._pending_calls):
            future.cancel()
        if self._inspection_future is not None:
            self._inspection_future.cancel()
        for client in (self._status_client, self._assembly_status_client,
                       self._conveyor_assembly, self._conveyor_inspection, self._conveyor_stop):
            self._node.destroy_client(client)
        self._node.destroy_subscription(self._assembly_subscription)
        self._node.destroy_subscription(self._conveyor_subscription)
        self._node.destroy_publisher(self._assembly_command)


def inspect(inspection_id, job_id, unit_id, *, base_url, token=None,
            timeout=api.VISION_TIMEOUT_SECONDS, request_timeout=api.VISION_REQUEST_TIMEOUT_SECONDS,
            poll_interval=api.VISION_POLL_SECONDS):
    """Run or retrieve one inspection and return ``{data: dict, image_bytes: bytes | None}``.

    The caller owns persistent inspection IDs and UNKNOWN/reinspection policy.
    This blocking call belongs on a worker, never a ROS executor callback thread.
    ``data`` retains the Vision JSON fields unchanged; image_bytes is not JSON.
    FAILED raises RuntimeError; transport/deadline expiry raises TimeoutError.
    A client timeout does not cancel Vision: retry with the same three IDs.
    """
    for name, value in (("inspection_id", inspection_id), ("job_id", job_id)):
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError(f"{name} must be a canonical UUID string")
    if type(unit_id) is not int or unit_id <= 0:
        raise ValueError("unit_id must be a positive integer")
    for value in (timeout, request_timeout, poll_interval):
        if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            raise ValueError("timeouts and poll_interval must be finite and positive")
    token = os.environ.get("KSMC_VISION_API_TOKEN", "") if token is None else token
    if (not isinstance(token, str) or len(token) < 32
            or not token.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in token)):
        raise ValueError("a valid KSMC_VISION_API_TOKEN of at least 32 characters is required")
    url = urlsplit(base_url)
    if (url.scheme not in ("http", "https") or not url.hostname
            or url.username is not None or url.password is not None
            or url.path not in ("", "/") or url.query or url.fragment):
        raise ValueError("base_url must be an HTTP(S) origin without credentials")
    port = url.port
    connection_type = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    identity = {"inspection_id": inspection_id, "job_id": job_id, "unit_id": unit_id}
    path = f"{api.VISION_INSPECTIONS}/{inspection_id}"
    deadline = time.monotonic() + timeout

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError(f"Vision inspection {inspection_id} timed out; remote execution may continue")
        return seconds

    def request(method, target, payload=None):
        connection = connection_type(url.hostname, port, timeout=min(request_timeout, remaining()))
        headers = {"Authorization": f"Bearer {token}"}
        if payload is not None:
            headers.update({"Content-Type": "application/json", "Idempotency-Key": inspection_id})
        try:
            connection.request(method, target, body=json.dumps(payload) if payload is not None else None,
                               headers=headers)
            response = connection.getresponse()
            body = response.read()
            remaining()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, body
        finally:
            connection.close()

    method, target, payload = "POST", api.VISION_INSPECTIONS, identity
    while True:
        remaining()
        try:
            code, _, body = request(method, target, payload)
        except (OSError, http.client.HTTPException):
            # POST may already have started capture. Resolve that same ID before retrying.
            method, target, payload = "GET", path, None
            time.sleep(min(poll_interval, remaining()))
            continue
        if code == 404 and method == "GET":
            method, target, payload = "POST", api.VISION_INSPECTIONS, identity
            time.sleep(min(poll_interval, remaining()))
            continue
        if code != (202 if method == "POST" else 200):
            raise RuntimeError(f"Vision {method} {target} returned HTTP {code}: {body[:512]!r}")
        envelope = json.loads(body)
        data = envelope.get("data") if isinstance(envelope, dict) else None
        if (not isinstance(data, dict) or any(data.get(k) != v for k, v in identity.items())
                or type(data.get("unit_id")) is not int):
            raise ValueError("Vision response identity does not match the request")
        status = data.get("status")
        if status == "FAILED":
            raise RuntimeError(f"Vision inspection {inspection_id} FAILED: {data.get('error')!r}")
        if status == "COMPLETED":
            # Retrieve the authoritative completed JSON even when POST returns an existing result.
            if method == "GET":
                break
        elif status not in ("ACCEPTED", "RUNNING"):
            raise ValueError("unexpected Vision inspection status")
        method, target, payload = "GET", path, None
        time.sleep(min(poll_interval, remaining()))

    result, image = data.get("result"), data.get("image")
    if not isinstance(result, dict) or result.get("decision") not in ("PASS", "FAIL", "UNKNOWN"):
        raise ValueError("Vision completed result must contain an explicit decision")
    if not isinstance(image, dict) or type(image.get("ready")) is not bool:
        raise ValueError("Vision result must contain image.ready")
    if not image["ready"]:
        return {"data": data, "image_bytes": None}
    # Only the same inspection's relative endpoint receives the bearer token; no redirects.
    if (image.get("path") != path + "/image"
            or image.get("filename") != "02_annotated_report.png"
            or image.get("mime_type") != "image/png"
            or type(image.get("size_bytes")) is not int or image["size_bytes"] <= 0
            or not isinstance(image.get("sha256"), str)):
        raise ValueError("invalid Vision image metadata")
    while True:
        try:
            code, headers, png = request("GET", image["path"])
            break
        except (OSError, http.client.HTTPException):
            time.sleep(min(poll_interval, remaining()))
    if code != 200:
        raise RuntimeError(f"Vision image returned HTTP {code}")
    digest = hashlib.sha256(png).hexdigest()
    if (not png.startswith(b"\x89PNG\r\n\x1a\n")
            or headers.get("content-type", "").split(";", 1)[0] != "image/png"
            or headers.get("content-disposition") != 'inline; filename="02_annotated_report.png"'
            or len(png) != image["size_bytes"]
            or headers.get("content-length") != str(len(png))
            or digest != image["sha256"] or digest != headers.get("x-content-sha256")):
        raise ValueError("Vision PNG content, size or SHA256 does not match its metadata")
    return {"data": data, "image_bytes": png}


def _self_check():
    import copy
    from unittest.mock import patch

    identity = {"inspection_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4()), "unit_id": 1}
    png = b"\x89PNG\r\n\x1a\ncheck"
    digest = hashlib.sha256(png).hexdigest()
    data = dict(identity, status="COMPLETED", result={"decision": "UNKNOWN", "defects": []},
                image={"ready": True, "path": f"{api.VISION_INSPECTIONS}/{identity['inspection_id']}/image",
                       "filename": "02_annotated_report.png", "mime_type": "image/png",
                       "size_bytes": len(png), "sha256": digest})
    headers = {"Content-Type": "image/png", "Content-Length": str(len(png)),
               "X-Content-SHA256": digest,
               "Content-Disposition": 'inline; filename="02_annotated_report.png"'}

    def run(final, image_body=png, lost_post=False):
        responses = [(202, {}, json.dumps({"data": dict(identity, status="ACCEPTED")}).encode()),
                     (200, {}, json.dumps({"data": final}).encode()), (200, headers, image_body)]
        calls = []

        class Connection:
            def __init__(self, *args, **kwargs):
                pass

            def request(self, method, target, body=None, headers=None):
                calls.append((method, target, body))

            def getresponse(self):
                self.status, self.headers, self.body = responses.pop(0)
                if lost_post and len(calls) == 1:
                    raise TimeoutError("lost POST response")
                return self

            def read(self):
                return self.body

            def getheaders(self):
                return self.headers.items()

            def close(self):
                pass

        with patch.object(http.client, "HTTPConnection", Connection):
            output = inspect(**identity, base_url="http://vision.invalid:8766", token="x" * 32,
                             poll_interval=0.001)
        assert [call[0] for call in calls].count("POST") == 1
        return output

    assert run(data, lost_post=True) == {"data": data, "image_bytes": png}
    unavailable = copy.deepcopy(data)
    unavailable["image"] = {"ready": False, "error": "legacy_zip_record"}
    assert run(unavailable)["image_bytes"] is None
    for field, value in (("status", "FAILED"), ("unit_id", 2)):
        invalid = copy.deepcopy(data)
        invalid[field] = value
        try:
            run(invalid)
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError(f"accepted invalid {field}")
    try:
        run(data, png + b"corrupt")
    except ValueError:
        pass
    else:
        raise AssertionError("accepted corrupt image")
    print("Vision backend self-check passed")


if __name__ == "__main__":
    _self_check()
