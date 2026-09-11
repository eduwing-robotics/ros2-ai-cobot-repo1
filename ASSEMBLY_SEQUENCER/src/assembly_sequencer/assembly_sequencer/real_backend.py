"""Real orchestration API client and Vision ROS boundary; no hardware drivers."""

import hashlib
import json
import os
import threading
import time
import uuid
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
        self._display_wait = None
        self._inspection_pending = False
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
        from vision_interfaces.srv import SubmitInspection, GetInspection, GetInspectionImage
        self._vision_submit = node.create_client(SubmitInspection, api.VISION_SUBMIT, callback_group=ReentrantCallbackGroup())
        self._vision_get = node.create_client(GetInspection, api.VISION_GET, callback_group=ReentrantCallbackGroup())
        self._vision_image = node.create_client(GetInspectionImage, api.VISION_IMAGE, callback_group=ReentrantCallbackGroup())
        self._vision_health = node.create_client(Trigger, api.VISION_HEALTH, callback_group=ReentrantCallbackGroup())
        self._status_client = node.create_client(
            Trigger, api.ROBOT_STATUS, callback_group=ReentrantCallbackGroup()
        )

    def is_available(self):
        return not self._closed and self._status_client.wait_for_service(timeout_sec=0.0)

    async def status(self):
        from .recipe_contract import unavailable_snapshot

        snapshot = unavailable_snapshot("")
        snapshot.update(runtime_mode="real", equipment_ready=False,
                        command_service_available=self.is_available(),
                        readiness=self._readiness_snapshot())
        robot_available = False
        assembly_available = False
        try:
            robot = await self._read_status(self._status_client)
            robot_available = True
            assembly = await self._read_status(self._assembly_status_client)
            assembly_available = True
        except (RuntimeError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            snapshot["readiness"] = self._readiness_snapshot()
            snapshot["readiness"]["robot_status_available"] = robot_available
            snapshot["readiness"]["assembly_status_available"] = assembly_available
            snapshot.update(error_code="NOT_READY", message=str(error))
            return snapshot
        snapshot["readiness"] = self._readiness_snapshot()
        snapshot["readiness"]["robot_status_available"] = True
        snapshot["readiness"]["assembly_status_available"] = True
        snapshot["robot_api_status"] = robot
        snapshot["production_contract"] = assembly.get("production_contract")
        try:
            self._validate_readiness(robot, assembly)
            await self._check_vision_health()
            snapshot.update(available=True, equipment_ready=True, error_code="", message="")
        except (RuntimeError, TimeoutError, ValueError) as error:
            snapshot.update(error_code="NOT_READY", message=str(error))
        return snapshot

    def _readiness_snapshot(self):
        with self._lock:
            state = dict(self._conveyor_state) if self._conveyor_state is not None else None
            age = time.monotonic() - self._conveyor_received
        conveyor_fresh = state is not None and age <= api.CONVEYOR_FRESHNESS_SECONDS
        phase = state.get("state", "") if conveyor_fresh else ""
        stopped = (phase in {"IDLE", "ASSEMBLY_STOP", "INSPECTION_STOP"} and
                   state.get("moving") is False) if conveyor_fresh else False
        return {
            "ros_domain_id": self._node.context.get_domain_id(),
            "robot_status_available": False,
            "assembly_status_available": False,
            "conveyor_state_fresh": conveyor_fresh,
            "conveyor_services_available": all(client.wait_for_service(timeout_sec=0.0) for client in (
                self._conveyor_assembly, self._conveyor_inspection, self._conveyor_stop)),
            "conveyor_state": phase,
            "conveyor_armed": state.get("armed") is True if conveyor_fresh else False,
            "conveyor_stopped": stopped,
            "vision_signal_fresh": state.get("vision_ready_fresh") is True if conveyor_fresh else False,
            "vision_ready": state.get("vision_ready") is True if conveyor_fresh else False,
            "vision_services_available": all(client.wait_for_service(timeout_sec=0.0) for client in (
                self._vision_submit, self._vision_get, self._vision_image, self._vision_health)),
        }

    def _vision_configuration_error(self):
        if not all(client.wait_for_service(timeout_sec=0.0) for client in (
                self._vision_submit, self._vision_get, self._vision_image, self._vision_health)):
            return "Vision inspection ROS services are unavailable."
        if not os.environ.get("DEFECT_IMAGE_ROOT", "").strip():
            return "DEFECT_IMAGE_ROOT must identify shared execution and inspection storage."
        return None

    def _validate_readiness(self, robot, assembly):
        production = assembly.get("production_contract", {})
        if (production.get("schema") != api.ASSEMBLY_SCHEMA or
                production.get("capabilities", {}).get("start") is not True):
            raise RuntimeError("Robot production v2 Start is unavailable.")
        if assembly.get("hardware_execution_enabled") is not True or robot.get("hardware_execution_enabled") is not True:
            raise RuntimeError("Robot hardware execution is disabled.")
        if robot.get("state_fresh") is not True:
            raise RuntimeError("Robot status is stale.")
        if robot.get("robot_health_clear") is not True:
            raise RuntimeError("Robot health is not clear.")
        if robot.get("robot_mode") != 0:
            raise RuntimeError("Robot must be in automatic mode.")
        if robot.get("robot_motion_done") != 1 or robot.get("active_operation") is not None:
            raise RuntimeError("Robot operation is still active.")
        if robot.get("recovery_required") is not False or production.get("recovery_required") is True:
            raise RuntimeError("Robot recovery is required.")
        if ("held_candidate" not in robot or
                robot["held_candidate"] is not None and robot["held_candidate"] is not False):
            raise RuntimeError("Robot gripper state is unresolved or holding a part.")
        if (production.get("equipment_busy_or_unresolved") is True or
                production.get("status", "idle") not in {"idle", "failed_recovered", "failed_before_motion",
                    "motion_complete_awaiting_physical_verification"}):
            raise RuntimeError("Robot production execution is busy or unresolved.")
        if not isinstance(production.get("current_recipe_revision"), str) or not production["current_recipe_revision"]:
            raise RuntimeError("Robot production recipe revision is missing.")
        self._ready_conveyor()
        vision_error = self._vision_configuration_error()
        if vision_error is not None:
            raise RuntimeError(vision_error)
        return production["current_recipe_revision"]

    async def prepare_execution(self, recipe_version):
        if recipe_version != "assembly-r1":
            raise RuntimeError("Production recipe has no deployed robot binding.")
        robot = await self._read_status(self._status_client)
        assembly = await self._read_status(self._assembly_status_client)
        revision = self._validate_readiness(robot, assembly)
        await self._check_vision_health()
        return revision

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
        phase = state.get("state")
        if phase == "MANUAL_STOP":
            raise RuntimeError("컨베이어 정지 상태 · 컨베이어 서버에서 정지 해제(reset) 후 다시 시도하세요. 사유: " + str(state.get("reason", "")))
        if phase == "FAULT":
            raise RuntimeError("컨베이어 오류 · 원인 확인 후 정지 해제(reset)가 필요합니다. 사유: " + str(state.get("reason", "")))
        if phase not in {"IDLE", "ASSEMBLY_STOP", "INSPECTION_STOP"} or state.get("moving") is not False:
            raise RuntimeError("컨베이어 이동 중 또는 상태 미확인 · 정지 상태를 기다리세요.")
        if state.get("armed") is not True:
            raise RuntimeError("컨베이어 제어가 비활성화되어 있습니다 (armed=false).")
        if state.get("vision_ready_fresh") is not True:
            raise RuntimeError("S22 비전 준비 신호 수신이 지연되거나 끊겼습니다.")
        if state.get("vision_ready") is not True:
            raise RuntimeError("S22 비전이 준비되지 않았습니다 (vision_ready=false).")
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
            self._display_wait = ("컨베이어 이동 요청 응답 대기", time.monotonic() + api.SERVICE_TIMEOUT_SECONDS)
            accepted = await self._read_status(client)
            motion_id = accepted.get("motion_id")
            if not isinstance(motion_id, str) or not motion_id or motion_id == before.get("motion_id"):
                raise RuntimeError("Conveyor acceptance has no new motion_id.")
            deadline = time.monotonic() + api.CONVEYOR_TIMEOUT_SECONDS
            self._display_wait = ("컨베이어 도착 대기", deadline)
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
        finally:
            self._display_wait = None

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
        # Reconciliation already reads and identity-checks the current remote status. Reuse it so
        # a control is published after one equipment round trip instead of two.
        data = await self.reconcile_control() or {}
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
            self._display_wait = ("로봇 조립 완료 대기", deadline)
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
            self._display_wait = None
            with self._lock:
                response = self._execution_response
                unresolved = sent and not (response and self._terminal(response) and
                    response.get("recovery_required") is not True)
                self._execution_detached = unresolved
                if not unresolved:
                    self._execution_id = None
                    self._pending_control = None

    async def _check_vision_health(self):
        health = await self._read_status(self._vision_health)
        if health.get("transport") != "ros2" or health.get("closing") is not False:
            raise RuntimeError("Vision inspection server is unavailable.")
        # The PCB is not yet at inspection during preflight. station_ready
        # governs submit admission after arrival, not production startup.
        if health.get("active_inspection_id") is not None:
            raise RuntimeError("Vision inspection is already active.")

    async def _vision_call(self, client, request, deadline):
        from rclpy.callback_groups import ReentrantCallbackGroup

        if self._closed:
            raise RuntimeError("Real backend is closed")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Vision deadline expired; remote inspection may continue")
        if not client.wait_for_service(timeout_sec=0.0):
            raise TimeoutError("Vision ROS service unavailable")
        future = client.call_async(request)
        self._pending_calls.add(future)
        timer = self._node.create_timer(
            min(api.VISION_REQUEST_TIMEOUT_SECONDS, remaining), future.cancel,
            callback_group=ReentrantCallbackGroup())
        try:
            response = await future
            if future.cancelled() or response is None:
                raise TimeoutError("Vision response lost; query the same inspection ID")
            if time.monotonic() >= deadline:
                raise TimeoutError("Vision deadline expired; remote inspection may continue")
            return response
        finally:
            client.remove_pending_request(future)
            self._pending_calls.discard(future)
            self._node.destroy_timer(timer)

    async def _vision_poll(self, deadline):
        until = min(deadline, time.monotonic() + api.VISION_POLL_SECONDS)
        while time.monotonic() < until:
            await self._wait_tick()
        if time.monotonic() >= deadline:
            raise TimeoutError("Vision deadline expired; remote inspection may continue")

    async def inspect_unit(self, job_id, unit_id, slot_codes):
        from vision_interfaces.srv import SubmitInspection, GetInspection, GetInspectionImage

        if str(uuid.UUID(job_id)) != job_id or type(unit_id) is not int or not 0 < unit_id < 2**63:
            raise ValueError("Inspection requires a canonical Job UUID and positive int64 Unit ID")
        if (not isinstance(slot_codes, list) or not slot_codes
                or any(not isinstance(code, str) or not code for code in slot_codes)
                or len(slot_codes) != len(set(slot_codes))):
            raise ValueError("Inspection requires unique expected product slot codes")
        if self._closed or self._inspection_pending:
            raise RuntimeError("Real backend is closed or another inspection is pending")
        self._inspection_pending = True
        identity = dict(inspection_id=str(uuid.uuid5(uuid.UUID(job_id), f"unit:{unit_id}")),
                        job_id=job_id, unit_id=unit_id)
        deadline = time.monotonic() + api.VISION_TIMEOUT_SECONDS
        self._display_wait = ("검사 결과 대기", deadline)
        submit = True
        try:
            while True:
                client = self._vision_submit if submit else self._vision_get
                request = (SubmitInspection.Request(**identity) if submit else
                           GetInspection.Request(inspection_id=identity["inspection_id"]))
                try:
                    response = await self._vision_call(client, request, deadline)
                except TimeoutError:
                    # A lost acceptance may have started capture. Resolve this
                    # durable ID before resubmitting; never use a new identity.
                    submit = False
                    await self._vision_poll(deadline)
                    continue
                if not response.success:
                    if not submit and response.error_code == "inspection_not_found":
                        submit = True
                    elif not (submit and response.error_code == "station_not_ready"):
                        raise RuntimeError("Vision inspection: " + response.error_code)
                    await self._vision_poll(deadline)
                    continue
                data = json.loads(response.record_json)
                if (not isinstance(data, dict) or data.get("transport") != api.VISION_TRANSPORT or
                        any(data.get(k) != v for k, v in identity.items()) or
                        type(data.get("unit_id")) is not int):
                    raise ValueError("Vision response identity or transport mismatch")
                status = data.get("status")
                if status == "FAILED":
                    raise RuntimeError(f"Vision inspection failed: {data.get('error')!r}")
                if status == "COMPLETED" and not submit:
                    break
                if status not in (api.VISION_STATUS_ACCEPTED, api.VISION_STATUS_RUNNING,
                        api.VISION_STATUS_COMPLETED, api.VISION_STATUS_FAILED):
                    raise ValueError("Unexpected Vision inspection status")
                submit = False
                await self._vision_poll(deadline)

            result, info = data.get("result"), data.get("image")
            if not isinstance(result, dict) or result.get("decision") not in (api.VISION_DECISION_PASS, api.VISION_DECISION_FAIL,
                    api.VISION_DECISION_UNKNOWN):
                raise ValueError("Vision must return an explicit decision")
            slots, findings, defects = (result.get(key) for key in ("slots", "findings", "defects"))
            if not all(isinstance(items, list) for items in (slots, findings, defects)):
                raise ValueError("Vision completed result must contain slots, findings and defects arrays")
            received_codes = [slot.get("slot_code") for slot in slots if isinstance(slot, dict)]
            if (len(received_codes) != len(slots) or len(received_codes) != len(set(received_codes))
                    or set(received_codes) != set(slot_codes)
                    or any(slot.get("decision") not in (api.VISION_DECISION_PASS, api.VISION_DECISION_FAIL,
                        api.VISION_DECISION_UNKNOWN) for slot in slots)):
                raise ValueError("Vision slots must exactly match the requested product slots")
            if not isinstance(info, dict) or type(info.get("ready")) is not bool:
                raise ValueError("Vision must return image.ready")
            png = None
            if info["ready"]:
                if (info.get("service") != api.VISION_IMAGE or info.get("slot_code") != "" or
                        info.get("filename") != api.VISION_IMAGE_FILENAME or
                        info.get("mime_type") != api.VISION_IMAGE_MIME_TYPE or
                        type(info.get("size_bytes")) is not int or
                        not 0 < info["size_bytes"] <= api.VISION_MAX_IMAGE_BYTES or
                        type(info.get("max_chunk_bytes")) is not int or
                        not 0 < info["max_chunk_bytes"] <= api.VISION_CHUNK_BYTES or
                        not isinstance(info.get("sha256"), str)):
                    raise ValueError("Invalid Vision image metadata")
                content = bytearray()
                while len(content) < info["size_bytes"]:
                    request = GetInspectionImage.Request(
                        inspection_id=identity["inspection_id"], slot_code="",
                        offset=len(content), max_bytes=info["max_chunk_bytes"])
                    try:
                        response = await self._vision_call(self._vision_image, request, deadline)
                    except TimeoutError:
                        await self._vision_poll(deadline)
                        continue
                    if not response.success:
                        raise RuntimeError("Vision image: " + response.error_code)
                    chunk = bytes(response.data)
                    end = len(content) + len(chunk)
                    if (response.inspection_id != identity["inspection_id"] or response.slot_code != "" or
                            response.offset != len(content) or response.filename != info["filename"] or
                            response.mime_type != api.VISION_IMAGE_MIME_TYPE or response.sha256 != info["sha256"] or
                            response.total_bytes != info["size_bytes"] or
                            not 0 < len(chunk) <= request.max_bytes or end > info["size_bytes"] or
                            response.eof != (end == info["size_bytes"])):
                        raise ValueError("Vision image chunk mismatch")
                    content.extend(chunk)
                png = bytes(content)
                if not png.startswith(b"\x89PNG\r\n\x1a\n") or hashlib.sha256(png).hexdigest() != info["sha256"]:
                    raise ValueError("Vision PNG signature or SHA256 mismatch")
            return dict(result=result["decision"], defects=None, image_path=None,
                        inspection=data, image_bytes=png)
        finally:
            self._inspection_pending = False
            self._display_wait = None

    def close(self):
        if self._closed:
            return
        self._closed = True
        for future in tuple(self._pending_calls):
            future.cancel()
        for client in (self._status_client, self._assembly_status_client,
                       self._conveyor_assembly, self._conveyor_inspection, self._conveyor_stop,
                       self._vision_submit, self._vision_get, self._vision_image, self._vision_health):
            self._node.destroy_client(client)
        self._node.destroy_subscription(self._assembly_subscription)
        self._node.destroy_subscription(self._conveyor_subscription)
        self._node.destroy_publisher(self._assembly_command)
