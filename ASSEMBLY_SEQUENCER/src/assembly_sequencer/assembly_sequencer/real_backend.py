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


class RealBackend:
    """Use documented equipment APIs only; never fall back to raw robot commands."""

    def __init__(self, node):
        from rclpy.callback_groups import ReentrantCallbackGroup
        from std_msgs.msg import Bool, String
        from std_srvs.srv import Trigger

        if node.runtime_mode != "real" or node.context.get_domain_id() != 5:
            raise RuntimeError("MODE_REJECTED stage=real_backend expected=real/domain5 result=blocked")
        self._node = node
        self._closed = False
        self._inspection_future = None
        self._pending_calls = set()
        self._operation_lock = threading.RLock()
        self._operation = None
        self._operation_future = None
        self._terminal_event = None
        self._pause_future = None
        self._dispatch_blocked = False
        self._cancel_requested = False
        self._execution = None
        self._server_instance_id = None
        self._joint_points = {}
        self._held_part = None
        self._vision_url = node.declare_parameter("vision_base_url", "").value
        self._status_client = node.create_client(
            Trigger, "/real/robot/status", callback_group=ReentrantCallbackGroup()
        )
        # Subscribe before publishing; terminal events are volatile, not a durable queue.
        self._event_subscription = node.create_subscription(
            String, "/real/robot/event", self._receive_event, 100)
        self._command_publisher = node.create_publisher(String, "/real/robot/command", 10)
        self._pause_publisher = node.create_publisher(Bool, "/real/robot/pause", 10)

    def is_available(self):
        return not self._closed and self._status_client.wait_for_service(timeout_sec=0.0)

    @staticmethod
    def _connection_error():
        return (
            "NOT_READY: production assembly start/stop and correlated cycle results "
            "are not connected; individual robot operations or diagnostic check_completed "
            "cannot substitute for assembly completion; conveyor and PCB transfer are not connected"
        )

    async def status(self):
        from .recipe_contract import unavailable_snapshot

        snapshot = unavailable_snapshot(self._connection_error())
        snapshot.update(runtime_mode="real", equipment_ready=False, error_code="NOT_READY",
                        command_service_available=self.is_available())
        if not self.is_available():
            return snapshot
        snapshot["robot_api_status"] = await self._read_robot_status()
        return snapshot

    async def _read_robot_status(self):
        from std_srvs.srv import Trigger

        if not self.is_available():
            raise RuntimeError("NOT_READY: robot status service unavailable")
        future = self._status_client.call_async(Trigger.Request())
        self._pending_calls.add(future)
        timer = self._node.create_timer(5.0, future.cancel)
        try:
            response = await future
            if future.cancelled():
                raise TimeoutError("robot API status response timed out")
            if not response.success:
                raise RuntimeError(f"robot API status failed: {response.message}")
            data = json.loads(response.message)
            if not isinstance(data, dict):
                raise ValueError("robot API status must be a JSON object")
            return data
        finally:
            self._pending_calls.discard(future)
            self._node.destroy_timer(timer)

    async def prepare(self, joint_points, frame):
        # Full production remains blocked before claim. The selected ownership requires
        # a robot-owned assembly cycle; individual operations and diagnostic status
        # cannot substitute for that contract or enable production execution.
        raise RuntimeError(self._connection_error())

    @staticmethod
    def _require_robot_ready(data):
        if (any(data.get(key) is not True for key in
                ("hardware_execution_enabled", "state_fresh", "robot_health_clear",
                 "gripper_feedback_valid"))
                or any(type(data.get(key)) is not int or data[key] != value for key, value in
                       (("robot_mode", 0), ("tool_num", 1), ("work_num", 0), ("robot_motion_done", 1)))
                or data.get("recovery_required") is not False
                or "active_operation" not in data or data["active_operation"] is not None):
            raise RuntimeError("SAFETY_STOP: robot readiness or idle state is unconfirmed")

    async def start(self, job_id, recipe_version, expected_step_count):
        # No batch start is sent. Bind only the explicit snapshot to the Unit
        # already owned by the Sequencer, never reuse a production UUID as execution ID.
        active = self._node.active
        if type(expected_step_count) is not int or expected_step_count <= 0:
            raise RuntimeError("NOT_READY: a positive recipe step count is required")
        if (not isinstance(active, dict) or active.get("job_id") != job_id
                or type(active.get("unit_id")) is not int or active["unit_id"] <= 0):
            raise RuntimeError("NOT_READY: no matching production Unit")
        data = await self._read_robot_status()
        self._require_robot_ready(data)
        prepared = data.get("prepared_execution")
        context = prepared.get("execution_context") if isinstance(prepared, dict) else None
        if (not isinstance(context, dict) or context.get("production_job_id") != job_id
                or type(context.get("unit_id")) is not int or context["unit_id"] != active["unit_id"]
                or context.get("execution_job_id") != prepared.get("job_id")
                or prepared.get("job_id") == job_id
                or not prepared.get("plan_sha256") or not prepared.get("source_cycle_id")
                or prepared["plan_sha256"] != data.get("vision_plan_sha256")
                or not isinstance(prepared.get("parts"), list)
                or len(prepared["parts"]) != expected_step_count
                or data.get("held_candidate", True) is not None):
            raise RuntimeError("NOT_READY: prepared execution does not match the production Unit")
        try:
            uuid.UUID(prepared["job_id"])
        except (ValueError, TypeError, KeyError) as error:
            raise RuntimeError("NOT_READY: invalid execution UUID") from error
        if self._dispatch_blocked or self._operation_future is not None:
            raise RuntimeError("SAFETY_STOP: previous operation requires reconciliation")
        recipe = self._node.recipe
        if recipe["recipe_version"] != recipe_version:
            raise ValueError("recipe version does not match")
        event_context = data.get("event_context")
        server_id = event_context.get("server_instance_id") if isinstance(event_context, dict) else None
        if not isinstance(server_id, str) or not server_id:
            raise RuntimeError("NOT_READY: API process identity missing")
        self._server_instance_id = server_id
        self._joint_points = recipe["joint_points"]
        self._execution = json.loads(json.dumps(prepared))
        self._held_part = None

    def _require_execution(self, job_id):
        if self._closed or self._execution is None:
            raise RuntimeError("NOT_READY: no prepared Unit execution")
        if self._execution["execution_context"]["production_job_id"] != job_id:
            raise ValueError("production Job does not match prepared execution")
        if self._dispatch_blocked:
            raise RuntimeError("SAFETY_STOP: dispatch blocked pending physical reconciliation")

    async def move_joint(self, job_id, joint_point):
        self._require_execution(job_id)
        names = [name for name, point in self._joint_points.items() if point == joint_point]
        if len(names) != 1:
            raise ValueError("joint target must identify exactly one reviewed recipe point")
        if (not isinstance(joint_point, list) or len(joint_point) != 6
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in joint_point)):
            raise ValueError("joint_point requires six finite degree values")
        await self._execute(job_id, "robot.move_joint", {"point_name": names[0], "joint_point": joint_point})

    def _part_request(self, job_id, step, frame, motion, gripper, pick):
        self._require_execution(job_id)
        if frame != "base_link":
            raise ValueError("Real robot requests require base_link")
        parts = [part for part in self._execution["parts"] if isinstance(part, dict)
                 and all(part.get(key) == step.get(key) for key in ("order", "part_id", "slot_code"))]
        if len(parts) != 1:
            raise ValueError("recipe part does not uniquely match prepared execution")
        part = parts[0]
        if (type(part.get("source_index")) is not int or part["source_index"] <= 0
                or type(part.get("order")) is not int or part["order"] <= 0
                or any(not isinstance(part.get(key), str) or not part[key] for key in
                       ("source_id", "tray_registration_id", "source_observation_id", "part_id", "slot_code"))):
            raise ValueError("prepared part lacks source identity or registration generation")
        payload = {key: part[key] for key in ("part_id", "slot_code", "order", "source_index")}
        for key in ("approach_dz_mm", "retract_dz_mm"):
            if type(motion.get(key)) not in (int, float) or motion[key] != 100:
                raise ValueError("Real precision operations support only 100mm approach/retract")
            payload[key] = motion[key]
        fields = ("pregrasp_opening_percent", "grasp_opening_percent", "release_opening_percent") if pick else ("release_opening_percent",)
        for key in fields:
            value = gripper.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"recipe must explicitly provide {key} in 0..100")
            payload[key] = value
        return payload

    async def pick(self, job_id, step, frame, source, motion, gripper):
        payload = self._part_request(job_id, step, frame, motion, gripper, True)
        if self._held_part is not None:
            raise RuntimeError("SAFETY_STOP: a previous Pick has not been placed")
        await self._execute(job_id, "robot.pick", payload)
        self._held_part = {key: payload[key] for key in ("part_id", "slot_code", "order", "source_index")}

    async def place(self, job_id, step, frame, target, motion, gripper):
        payload = self._part_request(job_id, step, frame, motion, gripper, False)
        if self._held_part != {key: payload[key] for key in ("part_id", "slot_code", "order", "source_index")}:
            raise ValueError("Place must match the completed Pick")
        await self._execute(job_id, "robot.place", payload)
        self._held_part = None

    async def _execute(self, job_id, action, fields):
        from rclpy.task import Future
        from std_msgs.msg import String

        self._require_execution(job_id)
        try:
            data = await self._read_robot_status()
            self._require_robot_ready(data)
        except Exception as error:
            self._dispatch_blocked = True
            raise RuntimeError(f"SAFETY_STOP: pre-dispatch state unconfirmed: {error}") from error
        if data.get("prepared_execution") != self._execution:
            self._dispatch_blocked = True
            raise RuntimeError("SAFETY_STOP: prepared execution changed")
        event_context = data.get("event_context")
        server_id = event_context.get("server_instance_id") if isinstance(event_context, dict) else None
        if not server_id or server_id != self._server_instance_id:
            self._dispatch_blocked = True
            raise RuntimeError("SAFETY_STOP: API process identity missing or changed")
        self._require_execution(job_id)
        with self._operation_lock:
            if self._operation_future is not None:
                raise RuntimeError("another robot operation is pending")
            self._operation = dict(fields, job_id=self._execution["job_id"],
                                   operation_id=str(uuid.uuid4()), action=action)
            future = Future(executor=self._node.executor)
            self._operation_future = future
            self._terminal_event = None
            wire = json.dumps(self._operation, sort_keys=True, separators=(",", ":"), allow_nan=False)

        timed_out = False

        def expire():
            nonlocal timed_out
            with self._operation_lock:
                if not future.done():
                    timed_out = True
                    self._dispatch_blocked = True
                    future.set_exception(RuntimeError("SAFETY_STOP: operation deadline; physical result unconfirmed"))

        timer = self._node.create_timer(600.0, expire)
        try:
            # Pause can arrive while the timer is being registered. Serialize the
            # final dispatch check with pause so no new command follows the stop.
            with self._operation_lock:
                self._require_execution(job_id)
                self._command_publisher.publish(String(data=wire))
            await future
        except Exception as operation_error:
            self._dispatch_blocked = True
            # Preserve the request and block dispatch even if the status call fails.
            # Replay uses the exact same UUID and bytes; it must never create a new move.
            try:
                data = await self._read_robot_status()
                prepared = data.get("prepared_execution", {})
                if (timed_out and not self._cancel_requested and prepared == self._execution
                        and data.get("event_context", {}).get("server_instance_id") == server_id
                        and data.get("recovery_required") is False):
                    with self._operation_lock:
                        if not self._closed and not self._cancel_requested:
                            self._command_publisher.publish(String(data=wire))
            except Exception as error:
                self._node.get_logger().warning(f"robot reconciliation remains required: {error}")
            if self._terminal_event != "OPERATION_FAILED" and not str(operation_error).startswith("SAFETY_STOP:"):
                raise RuntimeError(f"SAFETY_STOP: physical result unconfirmed: {operation_error}") from operation_error
            raise
        finally:
            self._node.destroy_timer(timer)
            with self._operation_lock:
                if not future.done():
                    future.cancel()
                self._operation_future = None

    def _receive_event(self, message):
        try:
            payload = json.loads(message.data)
            self.accept_operation_feedback(payload)
        except (ValueError, TypeError, AttributeError) as error:
            self._node.get_logger().warning(f"ignored invalid robot event: {error}")

    async def transfer_assembled_pcb(self, job_id, frame, assembled_pcb, motion, gripper):
        raise RuntimeError(self._connection_error())

    async def move_conveyor(self, job_id, station, *, unit_id, operation_id, on_ready):
        raise RuntimeError("NOT_READY: conveyor service/state adapter is not connected; direct IO is prohibited")

    async def resolve_targets(self, observations):
        raise RuntimeError("NOT_READY: robot-side vision preparation API is not connected")

    async def set_paused(self, job_id, paused):
        from rclpy.task import Future
        from std_msgs.msg import Bool

        if self._closed:
            raise RuntimeError("Real API client is closed")
        if not paused:
            raise RuntimeError("NOT_READY: robot API does not provide resume; legacy pause cancels")
        with self._operation_lock:
            if self._execution is None or self._execution["execution_context"]["production_job_id"] != job_id:
                raise RuntimeError("NOT_READY: no matching robot execution to stop")
            if self._pause_future is not None:
                raise RuntimeError("a stop confirmation is already pending")
            self._dispatch_blocked = True
            self._cancel_requested = True
            future = Future(executor=self._node.executor)
            self._pause_future = future

        def expire():
            with self._operation_lock:
                if not future.done():
                    future.set_exception(RuntimeError("SAFETY_STOP: physical stop not confirmed"))

        timer = self._node.create_timer(60.0, expire)
        try:
            self._pause_publisher.publish(Bool(data=True))
            await future
        finally:
            self._node.destroy_timer(timer)
            self._pause_future = None

    def accept_operation_feedback(self, payload):
        if not isinstance(payload, dict):
            return False
        with self._operation_lock:
            operation = self._operation
            if operation is None or any(payload.get(key) != operation[key]
                                        for key in ("job_id", "operation_id", "action")):
                return False
            context = payload.get("message", "")
            try:
                context = json.loads(context) if isinstance(context, str) else None
            except ValueError:
                context = None
            event = payload.get("event")
            future = self._operation_future
            if (isinstance(context, dict) and context.get("server_instance_id")
                    and context["server_instance_id"] != self._server_instance_id):
                self._dispatch_blocked = True
                if future is not None and not future.done():
                    future.set_exception(RuntimeError("SAFETY_STOP: API process changed during operation"))
                return True
            if event in {"PAUSED", "CONTROL_FAILED"}:
                self._dispatch_blocked = True
                verified = (event == "PAUSED" and isinstance(context, dict)
                            and context.get("stop_verified") is True
                            and context.get("control_mode") == "legacy_cancel"
                            and context.get("resume_available") is False)
                if self._pause_future is not None and not self._pause_future.done():
                    if verified:
                        self._pause_future.set_result(None)
                    else:
                        self._pause_future.set_exception(RuntimeError("SAFETY_STOP: physical stop not confirmed"))
                if future is not None and not future.done():
                    future.set_exception(RuntimeError("SAFETY_STOP: legacy cancel; automatic resume prohibited"))
            elif event == "REQUEST_REJECTED":
                # A conflicting retransmission is not the original operation's terminal.
                self._dispatch_blocked = True
            elif event in {"OPERATION_COMPLETED", "OPERATION_FAILED"} and future is not None and not future.done():
                self._terminal_event = event
                if event == "OPERATION_COMPLETED" and not self._dispatch_blocked:
                    future.set_result(payload)
                else:
                    was_blocked = self._dispatch_blocked
                    self._dispatch_blocked = True
                    reason = payload.get("error_code") or "OPERATION_FAILED"
                    # A confirmed execution failure is FAILED at the Sequencer.
                    # Cancellation and uncertain completion preserve RUNNING instead.
                    prefix = "SAFETY_STOP: " if was_blocked else ""
                    future.set_exception(RuntimeError(f"{prefix}{reason}: {payload.get('message', '')}"))
            return True

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
        self._dispatch_blocked = True
        for future in (self._operation_future, self._pause_future):
            if future is not None and not future.done():
                future.set_exception(RuntimeError("SAFETY_STOP: robot client closed"))
        for future in tuple(self._pending_calls):
            future.cancel()
        if self._inspection_future is not None:
            self._inspection_future.cancel()
        self._node.destroy_client(self._status_client)
        self._node.destroy_publisher(self._pause_publisher)
        self._node.destroy_publisher(self._command_publisher)
        self._node.destroy_subscription(self._event_subscription)


def inspect(inspection_id, job_id, unit_id, *, base_url, token=None,
            timeout=330.0, request_timeout=10.0, poll_interval=1.0):
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
    path = f"/api/v1/inspections/{inspection_id}"
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

    method, target, payload = "POST", "/api/v1/inspections", identity
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
            method, target, payload = "POST", "/api/v1/inspections", identity
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
                image={"ready": True, "path": f"/api/v1/inspections/{identity['inspection_id']}/image",
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
