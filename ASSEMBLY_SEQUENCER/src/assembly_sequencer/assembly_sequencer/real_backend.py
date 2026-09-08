"""Real equipment commands, physical completion and Vision; no production writes."""

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
    """Execute semantic robot operations through the existing FAIRINO service."""

    def __init__(self, node):
        from fairino_msgs.msg import RobotNonrtState
        from fairino_msgs.srv import RemoteCmdInterface
        from rclpy.callback_groups import ReentrantCallbackGroup

        if node.runtime_mode != "real" or node.context.get_domain_id() != 43:
            raise RuntimeError(
                "MODE_REJECTED stage=real_backend expected=real/domain43 result=blocked"
            )
        self._node = node
        self._closed = False
        self._state = None
        self._received_at = 0.0
        self._inspection_future = None
        self._prepared = False
        self._operation_active = False
        self._paused = False
        self._pending_calls = set()
        self._motion_speed = node.declare_parameter("real_motion_speed_percent", 20).value
        self._tool = node.declare_parameter("real_tool", -1).value
        self._user = node.declare_parameter("real_user", -1).value
        self._gripper_speed = node.declare_parameter("real_gripper_speed_percent", 50).value
        self._gripper_force = node.declare_parameter("real_gripper_force_percent", 30).value
        self._conveyor_do = node.declare_parameter("real_conveyor_drive_do", -1).value
        self._arrival_di = {
            "ASSEMBLY": node.declare_parameter("real_conveyor_assembly_di", -1).value,
            "INSPECTION": node.declare_parameter("real_conveyor_inspection_di", -1).value,
        }
        self._drive_level = node.declare_parameter("real_conveyor_drive_level", 1).value
        self._arrival_level = node.declare_parameter("real_conveyor_arrival_level", 1).value
        self._conveyor_active = False
        self._vision_url = node.declare_parameter("vision_base_url", "").value
        group = ReentrantCallbackGroup()
        self._client = node.create_client(
            RemoteCmdInterface, "/fairino_remote_command_service", callback_group=group
        )
        self._subscription = node.create_subscription(
            RobotNonrtState, "/nonrt_state_data", self._on_state, 10,
            callback_group=group,
        )

    def _on_state(self, message):
        self._state = message
        # The existing publisher timestamp has one-second resolution. Local
        # receive time diagnoses a missing stream without implying motion completion.
        self._received_at = time.monotonic()

    def is_available(self):
        return not self._closed and self._client.wait_for_service(timeout_sec=0.0)

    @staticmethod
    def _commissioning_error():
        # Motion primitives exist below. These missing plant inputs must be
        # resolved before enabling automatic execution; none are SDK API gaps.
        return (
            "NOT_READY: missing commissioned ItemReady/AssemblyReady and Tool/User, "
            "tray-part to recipe mapping and calibrated TCP grasp/place offsets, "
            "PCB destination pose, conveyor drive/arrival IO and reset feedback; "
            "shared point-table ownership with manual commands is not established"
        )

    async def status(self):
        from .recipe_contract import unavailable_snapshot

        snapshot = unavailable_snapshot(self._commissioning_error())
        state = self._state
        fresh = (state is not None and time.monotonic() - self._received_at <= 0.5
                 and state.reconnect_flag == 0)
        snapshot.update(runtime_mode="real", equipment_ready=False, error_code="NOT_READY",
                        command_service_available=self.is_available(),
                        robot_state_fresh=fresh)
        return snapshot

    async def prepare(self, joint_points, frame):
        self._prepared = False
        if frame != "base_link":
            raise ValueError("Real recipe frame must be base_link")
        for name, point in joint_points.items():
            if (not isinstance(point, (list, tuple)) or len(point) != 6
                    or any(isinstance(value, bool) or not isinstance(value, (int, float))
                           or not math.isfinite(value) for value in point)):
                raise ValueError(f"{name} must contain six finite joint angles in degrees")
        if not self.is_available():
            raise RuntimeError("NOT_READY: Real FAIRINO command service is unavailable")
        state = self._state
        if state is None or time.monotonic() - self._received_at > 0.5 or state.reconnect_flag != 0:
            raise RuntimeError("NOT_READY: Real robot state is missing, stale or disconnected")
        if any((state.emg, state.abnormal_stop, state.alarm, state.main_error_code,
                state.sub_error_code, state.gripperfaultnum, state.grippererro,
                state.safetydoor_alarm, state.safetyplanealarm)):
            raise RuntimeError("NOT_READY: Real robot or gripper reports a fault or safety stop")
        for name, value, minimum, maximum in (
            ("real_tool", self._tool, 0, 14),
            ("real_user", self._user, 0, 14),
            ("real_motion_speed_percent", self._motion_speed, 1, 100),
            ("real_gripper_speed_percent", self._gripper_speed, 1, 100),
            ("real_gripper_force_percent", self._gripper_force, 1, 100),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise RuntimeError(f"NOT_READY: {name} must be configured in [{minimum}, {maximum}]")
        # This runs before the shared Sequencer claims a Job. The current recipe
        # contains placeholder teaching poses, and hardware preparation/reset has
        # no verified source. Reject without changing DB state or sending motion.
        raise RuntimeError(self._commissioning_error())

    def _require_ready(self):
        if self._paused:
            raise RuntimeError("SAFETY_STOP: automatic operation is stopped; reset is required")
        if not self._prepared or self._closed:
            raise RuntimeError("NOT_READY: Real automatic equipment preparation is incomplete")
        state = self._state
        if state is None or time.monotonic() - self._received_at > 0.5 or state.reconnect_flag:
            raise RuntimeError("SAFETY_STOP: robot state is missing, stale or disconnected")
        if any((state.emg, state.abnormal_stop, state.alarm, state.main_error_code,
                state.sub_error_code, state.gripperfaultnum, state.grippererro,
                state.safetydoor_alarm, state.safetyplanealarm)):
            raise RuntimeError("SAFETY_STOP: robot or gripper reports a fault")
        if state.tool_num != self._tool or state.work_num != self._user:
            raise RuntimeError("SAFETY_STOP: active Tool/User changed")

    async def _delay(self, seconds):
        from rclpy.task import Future

        future = Future(executor=self._node.executor)
        def wake():
            if not future.done():
                future.set_result(None)
        timer = self._node.create_timer(seconds, wake)
        try:
            await future
        finally:
            self._node.destroy_timer(timer)

    async def _command(self, command, result_count=0):
        from fairino_msgs.srv import RemoteCmdInterface

        if self._closed or not self.is_available():
            raise RuntimeError("FAIRINO command service is unavailable")
        request = RemoteCmdInterface.Request()
        request.cmd_str = "real\n" + command
        future = self._client.call_async(request)
        self._pending_calls.add(future)
        timer = self._node.create_timer(5.0, future.cancel)
        try:
            response = await future
            if future.cancelled():
                # A lost response does not prove that the robot rejected the command.
                # Never resend a motion or gripper command after an ambiguous timeout.
                raise TimeoutError(f"FAIRINO response timeout: {command.split('(')[0]}")
            fields = response.cmd_res.split(",")
            if fields[0].strip() != "0":
                raise RuntimeError(f"FAIRINO {command.split('(')[0]} failed: {response.cmd_res}")
            if len(fields) != result_count + 1:
                raise RuntimeError("FAIRINO response has an unexpected field count")
            values = [float(value) for value in fields[1:]]
            if not all(math.isfinite(value) for value in values):
                raise RuntimeError("FAIRINO response contains non-finite values")
            return values
        finally:
            self._pending_calls.discard(future)
            self._node.destroy_timer(timer)

    @staticmethod
    def _numbers(values):
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) for value in values):
            raise ValueError("robot coordinates must contain finite numbers")
        # The point parser accepts decimal notation, but not scientific notation.
        return ",".join(f"{value:.6f}" for value in values)

    async def _wait_motion(self, target, joint=False):
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            self._require_ready()
            done, = await self._command("GetRobotMotionDone()", 1)
            if done not in (0, 1):
                raise RuntimeError("invalid robot completion state")
            actual = await self._command(
                "GetActualJointPosDegree(1)" if joint else "GetActualTCPPose(1)", 6
            )
            # Completion can still describe the previous command. Require the new
            # target as well; no-op and short moves need not expose a Running edge.
            errors = [abs(a - b) for a, b in zip(actual, target)]
            if not joint:
                errors[3:] = [abs((a - b + 180) % 360 - 180)
                              for a, b in zip(actual[3:], target[3:])]
            limits = [0.2] * 6 if joint else [0.5] * 3 + [0.5] * 3
            if done == 1 and all(error <= limit for error, limit in zip(errors, limits)):
                self._require_ready()
                return
            await self._delay(0.05)
        raise TimeoutError("robot did not reach the requested target within 30 seconds")

    async def _move(self, target, joint=False):
        self._require_ready()
        if len(target) != 6:
            raise ValueError("robot target must contain six coordinates")
        point = "JNT" if joint else "CART"
        await self._command(f"{point}Point(1,{self._numbers(target)})")
        self._require_ready()
        await self._command(
            f"{'MoveJ' if joint else 'MoveL'}({point}1,{self._motion_speed},{self._tool},{self._user})"
        )
        await self._wait_motion(target, joint)

    async def _grip(self, opening):
        self._require_ready()
        if isinstance(opening, bool) or not isinstance(opening, (int, float)) \
                or not math.isfinite(opening) or not 0 <= opening <= 100:
            raise ValueError("gripper opening must be between 0 and 100 percent")
        await self._command(
            f"MoveGripper(1,{round(opening)},{self._gripper_speed},{self._gripper_force},3000,1)"
        )
        deadline = time.monotonic() + 5.0
        saw_busy = False
        while time.monotonic() < deadline:
            self._require_ready()
            fault, done = await self._command("GetGripperMotionDone()", 2)
            if fault != 0 or done not in (0, 1):
                raise RuntimeError("gripper completion reports a fault or invalid state")
            saw_busy |= done == 0
            state = self._state
            at_target = (state.gripper_feedback_valid
                         and abs(state.gripper_position - round(opening)) <= 1)
            # Contact can prevent reaching the requested opening. A confirmed
            # busy-to-done transition is valid; stale done alone is never valid.
            if done == 1 and (saw_busy or at_target):
                self._require_ready()
                return
            await self._delay(0.05)
        raise TimeoutError("gripper physical completion was not confirmed")

    @staticmethod
    def _tcp_pose(pose, frame, dz=0.0):
        from .recipe_contract import validate_ros_pose

        if frame != "base_link":
            raise ValueError("Real pose must be in base_link")
        pose = validate_ros_pose(pose, "TCP target")
        if not math.isfinite(dz) or dz < 0:
            raise ValueError("approach/retract distance must be finite and non-negative")
        x, y, z, w = pose["xyzw"]
        roll = math.atan2(2 * (w*x + y*z), 1 - 2 * (x*x + y*y))
        pitch = math.asin(max(-1.0, min(1.0, 2 * (w*y - z*x))))
        yaw = math.atan2(2 * (w*z + x*y), 1 - 2 * (y*y + z*z))
        px, py, pz = pose["xyz_mm"]
        return [px, py, pz + dz, *map(math.degrees, (roll, pitch, yaw))]

    async def _run_robot_operation(self, action):
        self._require_ready()
        if self._operation_active or self._conveyor_active:
            raise RuntimeError("another Real equipment operation is active")
        self._operation_active = True
        try:
            await action()
        except Exception as error:
            self._prepared = False
            try:
                await self._command("StopMotion()")
            except Exception as stop_error:
                self._node.get_logger().error(f"physical stop could not be confirmed: {stop_error}")
            raise RuntimeError(f"SAFETY_STOP: {error}") from error
        finally:
            self._operation_active = False

    async def start(self, job_id, recipe_version, expected_step_count):
        self._require_ready()

    async def move_joint(self, job_id, joint_point):
        async def move():
            await self._move(joint_point, joint=True)
        await self._run_robot_operation(move)

    async def pick(self, job_id, step, frame, source, motion, gripper):
        target = self._tcp_pose(source, frame)
        approach = self._tcp_pose(source, frame, motion["approach_dz_mm"])
        retract = self._tcp_pose(source, frame, motion["retract_dz_mm"])
        async def move():
            await self._move(approach)
            await self._grip(gripper["release_opening_percent"])
            await self._move(target)
            await self._grip(gripper["grasp_opening_percent"])
            await self._move(retract)
        await self._run_robot_operation(move)

    async def place(self, job_id, step, frame, target, motion, gripper):
        pose = self._tcp_pose(target, frame)
        approach = self._tcp_pose(target, frame, motion["approach_dz_mm"])
        retract = self._tcp_pose(target, frame, motion["retract_dz_mm"])
        async def move():
            await self._move(approach)
            await self._move(pose)
            await self._grip(gripper["release_opening_percent"])
            await self._move(retract)
        await self._run_robot_operation(move)

    async def transfer_assembled_pcb(self, job_id, frame, assembled_pcb, motion, gripper):
        if not isinstance(assembled_pcb, dict) or set(assembled_pcb) != {"source", "target"}:
            raise ValueError("calibrated PCB source and destination TCP poses are required")
        # Validate both ends before picking up the board.
        self._tcp_pose(assembled_pcb["source"], frame)
        self._tcp_pose(assembled_pcb["target"], frame)
        await self.pick(job_id, None, frame, assembled_pcb["source"], motion, gripper)
        drop_motion = dict(motion, approach_dz_mm=motion["assembled_pcb_drop_approach_dz_mm"])
        await self.place(job_id, None, frame, assembled_pcb["target"], drop_motion, gripper)

    async def move_conveyor(self, job_id, station):
        self._require_ready()
        pin = self._arrival_di.get(station, -1)
        if any(type(value) is not int or not 0 <= value <= 15
               for value in (pin, self._conveyor_do)):
            raise RuntimeError("NOT_READY: conveyor drive DO and station arrival DI are not configured")
        if self._drive_level not in (0, 1) or self._arrival_level not in (0, 1):
            raise ValueError("conveyor signal levels must be 0 or 1")
        if self._conveyor_active or self._operation_active:
            raise RuntimeError("another equipment operation is active")
        self._conveyor_active = True
        try:
            initial, = await self._command(f"GetDI({pin},1)", 1)
            if initial not in (0, 1) or initial == self._arrival_level:
                raise RuntimeError("arrival sensor must be clear before a new conveyor movement")
            await self._command(f"SetDO({self._conveyor_do},{self._drive_level},0,1)")
            deadline = time.monotonic() + 60.0
            while time.monotonic() < deadline:
                self._require_ready()
                arrived, = await self._command(f"GetDI({pin},1)", 1)
                if arrived not in (0, 1):
                    raise RuntimeError("invalid conveyor arrival signal")
                if arrived == self._arrival_level:
                    return
                await self._delay(0.05)
            raise TimeoutError("conveyor arrival was not confirmed within 60 seconds")
        except Exception as error:
            self._prepared = False
            raise RuntimeError(f"SAFETY_STOP: {error}") from error
        finally:
            try:
                await self._command(f"SetDO({self._conveyor_do},{1-self._drive_level},0,1)")
            except Exception as error:
                self._prepared = False
                raise RuntimeError(f"SAFETY_STOP: conveyor stop could not be confirmed: {error}") from error
            finally:
                self._conveyor_active = False

    async def resolve_targets(self, observations):
        raise RuntimeError(
            "Real calibrated target provider is not connected; Unity poses are not accepted"
        )

    async def set_paused(self, job_id, paused):
        if not paused:
            raise RuntimeError("NOT_READY: reset and a new Unit are required after an automatic stop")
        self._paused = True
        self._prepared = False
        try:
            await self._command("StopMotion()")
        finally:
            if self._conveyor_active:
                await self._command(f"SetDO({self._conveyor_do},{1-self._drive_level},0,1)")

    def accept_operation_feedback(self, payload):
        return False

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
        self._prepared = False
        for future in tuple(self._pending_calls):
            future.cancel()
        if self._inspection_future is not None:
            self._inspection_future.cancel()
        self._node.destroy_subscription(self._subscription)
        self._node.destroy_client(self._client)


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
