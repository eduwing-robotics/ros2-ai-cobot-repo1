"""ROS 2 transport and FAIRINO adapter for the Real robot operation API.

The node never reads YAML or a database.  Its backend-owned Vision component
must publish fresh, calibrated internal targets on ``/real/vision/targets``.
Hardware execution is disabled by default and must be explicitly armed with a
ROS parameter after commissioning.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Any, Mapping, Sequence

import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger
from rcl_interfaces.srv import GetParameters

from .real_backend import (
    BackendFailure,
    CartesianTarget,
    RealRobotBackend,
    TransferTarget,
)
from .real_contract import Action, Event, ContractLimits, OperationEvent
from .real_ghost import RealGhostTargetPublisher
from .real_preview import JointGhostPreview, PREVIEW_COMMAND_TOPIC, PREVIEW_EVENT_TOPIC


COMMAND_TOPIC = "/real/robot/command"
EVENT_TOPIC = "/real/robot/event"
PAUSE_TOPIC = "/real/robot/pause"
VISION_TARGET_TOPIC = "/real/vision/targets"
ROBOT_STATE_TOPIC = "/nonrt_state_data"
ROBOT_COMMAND_SERVICE = "/fairino_remote_command_service"
VISION_SCHEMA = "fr5.real.vision_targets/v1"


class RosTargetVisionPort:
    """Consume fresh targets produced by the backend-owned Vision pipeline."""

    def __init__(self, node: Node, topic: str, maximum_age_sec: float) -> None:
        self._node = node
        self._maximum_age_sec = float(maximum_age_sec)
        self._lock = threading.Lock()
        self._payload: dict[str, Any] | None = None
        self._parse_error: str | None = None
        node.create_subscription(String, topic, self._callback, 10)

    def _callback(self, message: String) -> None:
        try:
            payload = json.loads(message.data)
            if not isinstance(payload, dict):
                raise ValueError("top-level JSON is not an object")
        except (json.JSONDecodeError, ValueError) as error:
            with self._lock:
                self._parse_error = str(error)
            return
        with self._lock:
            self._payload = payload
            self._parse_error = None

    def precision_snapshot(self, operation):
        from copy import deepcopy
        # Frozen targets retain original acquisition time. Only explicitly
        # prepared per-Unit plans may use the bounded fixed-fixture lifetime.
        payload = self._snapshot(allow_frozen=True)
        if payload.get('job_id') != operation.job_id:
            raise BackendFailure('INVALID_REQUEST', 'precision plan belongs to another Unit/job')
        return deepcopy(payload)

    def locate_part(self, part_id: str, order: int) -> CartesianTarget:
        payload = self._snapshot()
        item = self._unique(
            payload,
            "parts",
            lambda value: value.get("part_id") == part_id and value.get("order") == order,
            "PART_NOT_FOUND",
            f"part {part_id} order {order} was not found",
        )
        return self._target(item.get("tcp_pose_mm_deg"), f"part {part_id}/{order}")

    def locate_part_by_index(self, part_id, source_index, job_id):
        payload = self._snapshot()
        item = self._unique(payload, "parts", lambda v:
            v.get("part_id") == part_id and v.get("source_index") == source_index
            and v.get("job_id") == job_id, "PART_NOT_FOUND", "indexed part not found for job")
        self._check_item_age(item)
        return self._target(item.get("tcp_pose_mm_deg"), "indexed part")

    def locate_slot_for_job(self, part_id, slot_code, source_index, job_id):
        payload = self._snapshot()
        item = self._unique(payload, "slots", lambda v:
            v.get("part_id") == part_id and v.get("slot_code") == slot_code
            and v.get("source_index") == source_index and v.get("job_id") == job_id,
            "SLOT_NOT_FOUND", "slot not found for job/source")
        self._check_item_age(item)
        return self._target(item.get("tcp_pose_mm_deg"), "job slot")

    def validate_operation(self, operation):
        payload = self._snapshot()
        key = "parts" if operation.action.value == "robot.pick" else "slots"
        item = self._unique(payload, key, lambda v:
            v.get("part_id") == operation.part_id and v.get("slot_code") == operation.slot_code
            and v.get("source_index") == operation.source_index
            and v.get("job_id") == operation.job_id and v.get("order") == operation.order,
            "INVALID_REQUEST", "operation does not match resolved recipe step")
        self._check_item_age(item)
        expected = item.get("expected_gripper")
        if not isinstance(expected, dict):
            raise BackendFailure("INVALID_REQUEST", "validated gripper recipe missing from target")
        fields = ["release_opening_percent"]
        if key == "parts":
            fields += ["grasp_opening_percent", "pregrasp_opening_percent"]
        for field in fields:
            if getattr(operation, field) != expected.get(field) or field not in expected:
                raise BackendFailure("INVALID_REQUEST",
                    f"{field}: requested {getattr(operation, field)}, calibrated {expected.get(field)}")

        profiles = item.get("gripper_profiles", {})
        for phase in ("PREOPEN", "GRASP", "RELEASE"):
            profile = profiles.get(phase, {})
            for field in ("velocity_percent", "force_percent"):
                value = profile.get(field)
                if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not 0 <= value <= 100:
                    raise BackendFailure("INVALID_REQUEST", "calibrated gripper speed/force missing or invalid")
        return profiles

    def _check_item_age(self, item):
        try:
            age = (self._node.get_clock().now().nanoseconds - int(item["timestamp_ros_ns"])) / 1e9
        except (KeyError, TypeError, ValueError) as error:
            raise BackendFailure("CAMERA_NOT_READY", "missing original target timestamp") from error
        if not math.isfinite(age) or not 0 <= age <= self._maximum_age_sec:
            raise BackendFailure("CAMERA_NOT_READY", "target acquisition is stale or future-dated")

    def locate_slot(self, part_id: str, slot_code: str, order: int) -> CartesianTarget:
        payload = self._snapshot()
        item = self._unique(
            payload,
            "slots",
            lambda value: value.get("part_id") == part_id
            and value.get("slot_code") == slot_code
            and value.get("order") == order,
            "SLOT_NOT_FOUND",
            f"slot {slot_code} for {part_id} order {order} was not found",
        )
        return self._target(item.get("tcp_pose_mm_deg"), f"slot {slot_code}")

    def locate_transfer(self, object_id: str) -> TransferTarget:
        payload = self._snapshot()
        item = self._unique(
            payload,
            "transfers",
            lambda value: value.get("object_id") == object_id,
            "SLOT_NOT_FOUND",
            f"transfer targets for {object_id} were not found",
        )
        return TransferTarget(
            self._target(item.get("pickup_tcp_pose_mm_deg"), f"{object_id} pickup"),
            self._target(item.get("drop_tcp_pose_mm_deg"), f"{object_id} drop"),
        )

    def _snapshot(self, *, allow_frozen=False) -> Mapping[str, Any]:
        with self._lock:
            payload = None if self._payload is None else dict(self._payload)
            parse_error = self._parse_error
        if parse_error:
            raise BackendFailure("CAMERA_NOT_READY", f"invalid Vision JSON: {parse_error}")
        if payload is None:
            raise BackendFailure("CAMERA_NOT_READY", "no Vision target has been received")
        if payload.get("schema") != VISION_SCHEMA or payload.get("valid") is not True:
            raise BackendFailure("CAMERA_NOT_READY", "Vision targets are not valid")
        if payload.get("coordinate_frame") != "base_link":
            raise BackendFailure(
                "FRAME_TRANSFORM_FAILED", "Vision target frame must be base_link"
            )
        try:
            stamp_ns = int(payload["timestamp_ros_ns"])
        except (KeyError, TypeError, ValueError) as error:
            raise BackendFailure(
                "CAMERA_NOT_READY", "Vision target has no valid acquisition timestamp"
            ) from error
        now_ns = int(self._node.get_clock().now().nanoseconds)
        age_sec = (now_ns - stamp_ns) / 1_000_000_000.0
        maximum_age = (1800.0 if allow_frozen and payload.get("target_mode") == "frozen_unit"
                       else self._maximum_age_sec)
        if age_sec < -1.0 or age_sec > maximum_age:
            raise BackendFailure(
                "CAMERA_NOT_READY", f"Vision target is stale (age={age_sec:.3f}s)"
            )
        return payload

    @staticmethod
    def _unique(payload, key, predicate, code, message):
        values = payload.get(key)
        if not isinstance(values, list):
            raise BackendFailure("CAMERA_NOT_READY", f"Vision {key} is not an array")
        matches = [value for value in values if isinstance(value, Mapping) and predicate(value)]
        if len(matches) != 1:
            detail = "not found" if not matches else "ambiguous"
            raise BackendFailure(code, f"{message} ({detail})")
        return matches[0]

    @staticmethod
    def _target(value: Any, label: str) -> CartesianTarget:
        if not isinstance(value, (list, tuple)) or len(value) != 6:
            raise BackendFailure(
                "FRAME_TRANSFORM_FAILED", f"{label} TCP pose must contain XYZABC"
            )
        try:
            numbers = tuple(float(item) for item in value)
        except (TypeError, ValueError) as error:
            raise BackendFailure(
                "FRAME_TRANSFORM_FAILED", f"{label} TCP pose is not numeric"
            ) from error
        return CartesianTarget("base_link", *numbers)


class FairinoRobotPort:
    """Translate preflighted backend operations to the existing FR5 service."""

    def __init__(
        self,
        node: Node,
        *,
        enabled: bool,
        state_topic: str,
        command_service: str,
        travel_speed_percent: int,
        vertical_speed_percent: int,
        state_max_age_sec: float = 0.25,
        service_timeout_sec: float = 10.0,
        maximum_joint_step_deg: float = 95.0,
        minimum_soft_limit_margin_deg: float = 10.0,
        j6_operational_bounds_deg: tuple[float, float] = (-178.0, 178.0),
    ) -> None:
        self._node = node
        self._enabled = bool(enabled)
        self._travel_speed = int(travel_speed_percent)
        self._vertical_speed = int(vertical_speed_percent)
        self._state_max_age = float(state_max_age_sec)
        self._service_timeout = float(service_timeout_sec)
        self._maximum_joint_step = float(maximum_joint_step_deg)
        self._minimum_margin = float(minimum_soft_limit_margin_deg)
        self._j6_bounds = j6_operational_bounds_deg
        self._lock = threading.Lock()
        self._state: RobotNonrtState | None = None
        self._state_sequence = 0
        self._state_received_at = 0.0
        node.create_subscription(RobotNonrtState, state_topic, self._state_callback, 10)
        self._client = node.create_client(RemoteCmdInterface, command_service)
        self._driver_parameters = node.create_client(GetParameters, "/fr_command_server/get_parameters")

    def _state_callback(self, state: RobotNonrtState) -> None:
        with self._lock:
            self._state = state
            self._state_sequence = getattr(self, "_state_sequence", 0) + 1
            self._state_received_at = time.monotonic()

    def assert_continuous_driver(self):
        client = self._driver_parameters
        if not client.wait_for_service(timeout_sec=2):
            raise BackendFailure('SAFETY_STOP', 'continuous driver capability service unavailable')
        request = GetParameters.Request(names=['continuous_movej_revision'])
        future = client.call_async(request)
        deadline = time.monotonic() + 2
        while not future.done() and time.monotonic() < deadline:
            time.sleep(.01)
        if not future.done() or future.result() is None:
            raise BackendFailure('SAFETY_STOP', 'continuous driver capability timeout')
        values = future.result().values
        if len(values) != 1 or values[0].string_value != 'per-command-blend-v1':
            raise BackendFailure('SAFETY_STOP', 'driver lacks per-command blending; restart updated driver first')

    def assert_ready(self) -> None:
        if not self._enabled:
            raise BackendFailure(
                "SAFETY_STOP",
                "Real hardware execution is not armed (enable_hardware_execution=false)",
            )
        state = self._fresh_state()
        self._assert_health(state)
        if int(state.robot_mode) != 0:
            raise BackendFailure("SAFETY_STOP", "FR5 must be in AUTO mode")
        if int(state.tool_num) != 1 or int(state.work_num) != 0:
            raise BackendFailure("ROBOT_FAULT", "FR5 must use Tool1/User0")
        if int(state.robot_motion_done) != 1:
            raise BackendFailure("ROBOT_BUSY", "FR5 is not stationary")

    def current_joints_deg(self) -> tuple[float, ...]:
        state = self._fresh_state()
        self._assert_health(state)
        return tuple(float(getattr(state, f"j{index}_cur_pos")) for index in range(1, 7))

    def validate_joint_target(self, joints_deg: Sequence[float]) -> None:
        values = tuple(float(value) for value in joints_deg)
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            raise BackendFailure("IK_FAILED", "joint target must contain six finite values")
        response = self._service("GetJointSoftLimitDeg(1)", "IK_FAILED")
        limits = self._response_numbers(response, 12, "joint soft limits", "IK_FAILED")
        lower, upper = limits[:6], limits[6:]
        for index, value in enumerate(values):
            margin = min(value - lower[index], upper[index] - value)
            if margin < self._minimum_margin:
                raise BackendFailure(
                    "IK_FAILED",
                    f"J{index + 1} soft-limit margin {margin:.3f}deg is below "
                    f"{self._minimum_margin:.3f}deg",
                )
        if not self._j6_bounds[0] <= values[5] <= self._j6_bounds[1]:
            raise BackendFailure(
                "IK_FAILED", f"J6 {values[5]:.3f}deg exceeds commissioned bounds"
            )

    def inverse_kinematics(
        self, target: CartesianTarget, reference_joints_deg: Sequence[float]
    ) -> tuple[float, ...]:
        reference = tuple(float(value) for value in reference_joints_deg)
        command = "GetInverseKinRef(" + ",".join(
            f"{value:.6f}" for value in (0.0, *target.controller_pose(), *reference)
        ) + ")"
        response = self._service(command, "IK_FAILED")
        joints = self._response_numbers(response, 6, "referenced IK", "IK_FAILED")
        delta = [abs(value - seed) for value, seed in zip(joints, reference)]
        if max(delta) > self._maximum_joint_step:
            index = delta.index(max(delta))
            raise BackendFailure(
                "IK_FAILED",
                f"J{index + 1} branch step {delta[index]:.3f}deg exceeds "
                f"{self._maximum_joint_step:.3f}deg",
            )
        return tuple(joints)

    def prepare_motion(self, target, planned_joints):
        """Recheck live state and IK branch before publishing the exact command target."""
        self.assert_ready()
        current = self.current_joints_deg()
        joints = tuple(planned_joints)
        if target is not None:
            checked = self.inverse_kinematics(target, current)
            if max(abs(a-b) for a,b in zip(checked, joints)) > 1.0:
                raise BackendFailure("IK_FAILED", "live IK differs from preflight branch; replan required")
            joints = checked
        if max(abs(a-b) for a,b in zip(joints, current)) > self._maximum_joint_step:
            raise BackendFailure("IK_FAILED", "live joint step exceeds commissioned bound")
        self.validate_joint_target(joints)
        return joints

    def move_joint(self, joints_deg: Sequence[float]) -> None:
        self._define_joint_point(joints_deg)
        self._service(f"MoveJ(JNT1,{self._travel_speed},1,0)", "ROBOT_FAULT")

    def move_cartesian(
        self,
        target: CartesianTarget,
        joints_deg: Sequence[float],
        *,
        linear: bool,
    ) -> None:
        del target  # The controller uses the already IK-qualified JNTPoint.
        self._define_joint_point(joints_deg)
        command = "MoveL" if linear else "MoveJ"
        speed = self._vertical_speed if linear else self._travel_speed
        self._service(f"{command}(JNT1,{speed},1,0)", "ROBOT_FAULT")

    def move_gripper(self, opening_percent: float) -> None:
        self._service(f"MoveGripper(1,{float(opening_percent):.3f})", "GRIPPER_FAILED")

    def move_profiled_gripper(self, opening_percent, profile):
        # The installed v3.9.7 wrapper consumes the first four arguments.
        # It hardcodes controller max_time=30000 and block=1; completion is
        # independently checked by wait_gripper_complete below.
        self._service("MoveGripper(1," + ",".join(str(float(value)) for value in
            (opening_percent, profile["velocity_percent"], profile["force_percent"])) + ")",
            "GRIPPER_FAILED")

    def wait_arm_complete(
        self,
        target: CartesianTarget | None,
        joints_deg: Sequence[float],
        timeout_sec: float,
    ) -> None:
        deadline = time.monotonic() + timeout_sec
        expected_joints = tuple(float(value) for value in joints_deg)
        while rclpy.ok() and time.monotonic() < deadline:
            state = self._fresh_state()
            self._assert_health(state)
            current_joints = tuple(
                float(getattr(state, f"j{index}_cur_pos")) for index in range(1, 7)
            )
            joint_error = max(
                abs(current - expected)
                for current, expected in zip(current_joints, expected_joints)
            )
            pose_ok = True
            if target is not None:
                xyz = (
                    float(state.cart_x_cur_pos),
                    float(state.cart_y_cur_pos),
                    float(state.cart_z_cur_pos),
                )
                xyz_error = math.sqrt(
                    sum((current - expected) ** 2 for current, expected in zip(xyz, target.controller_pose()[:3]))
                )
                actual_abc = (
                    float(state.cart_a_cur_pos),
                    float(state.cart_b_cur_pos),
                    float(state.cart_c_cur_pos),
                )
                abc_error = max(
                    abs(_wrapped_degrees(current - expected))
                    for current, expected in zip(actual_abc, target.controller_pose()[3:])
                )
                pose_ok = xyz_error <= 1.0 and abc_error <= 1.0
            if int(state.robot_motion_done) == 1 and joint_error <= 1.0 and pose_ok:
                return
            time.sleep(0.02)
        raise BackendFailure("ROBOT_TIMEOUT", "arm completion verification timed out")

    def wait_gripper_complete(self, opening_percent: float, timeout_sec: float) -> None:
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            state = self._fresh_state()
            self._assert_health(state)
            if int(state.gripperfaultnum) or int(state.grippererro):
                raise BackendFailure("GRIPPER_FAILED", "FR5 reported a gripper fault")
            if (
                int(state.grip_motion_done) == 1
                and bool(state.gripper_feedback_valid)
                and abs(float(state.gripper_position) - opening_percent) <= 1.0
            ):
                return
            time.sleep(0.02)
        raise BackendFailure("GRIPPER_FAILED", "gripper completion verification timed out")

    def stop_motion(self) -> None:
        if not self._enabled:
            return
        self._service("StopMotion()", "SAFETY_STOP")

    def pause_motion(self) -> None:
        if not self._enabled:
            return
        self._service("PauseMotion()", "SAFETY_STOP")

    def resume_motion(self):
        self.assert_ready()
        self._service('ResumeMotion()', 'SAFETY_STOP')
        baseline = self._state_sequence  # require feedback received after acknowledgment
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            state = self._fresh_state()
            self._assert_health(state)
            if self._state_sequence > baseline:
                return 'fresh_feedback_resume_applied'
            time.sleep(.01)
        raise BackendFailure('ROBOT_TIMEOUT', 'no fresh feedback after ResumeMotion')

    def observe_stopped(self, timeout_sec=3.0):
        # Do not reject fault bits here: stopping must also be observed on faults.
        baseline = self._state_sequence
        deadline = time.monotonic() + timeout_sec
        anchor = None; since = None; count = 0; last_at = None
        while time.monotonic() < deadline:
            with self._lock:
                state = self._state; sequence = self._state_sequence
                stamp = self._state_received_at
            now = time.monotonic()
            if state is None or sequence <= baseline or now-stamp > .25:
                time.sleep(.01); continue
            baseline = sequence
            pose = [float(getattr(state, f"cart_{axis}_cur_pos")) for axis in 'xyzabc']
            if anchor is None: anchor = pose
            stable = (int(state.robot_motion_done) == 1 and all(math.isfinite(v) for v in pose)
                and max(abs(pose[i]-anchor[i]) for i in range(3)) <= .2
                and max(abs(_wrapped_degrees(pose[i]-anchor[i])) for i in range(3,6)) <= .1)
            if not stable or (last_at is not None and stamp-last_at > .25):
                anchor = pose; since = None; count = 0
            last_at = stamp
            if stable:
                if since is None: since = now
                count += 1
                if count >= 5 and now-since >= .5:
                    return 'fresh_feedback_verified_stopped'
        return 'stop_not_verified_feedback_timeout'

    def _define_joint_point(self, joints_deg: Sequence[float]) -> None:
        command = "JNTPoint(1," + ",".join(f"{float(value):.6f}" for value in joints_deg) + ")"
        self._service(command, "ROBOT_FAULT")

    def _fresh_state(self) -> RobotNonrtState:
        with self._lock:
            state = self._state
            age = time.monotonic() - self._state_received_at
        if state is None or age > self._state_max_age:
            raise BackendFailure("ROBOT_TIMEOUT", "FR5 state is missing or stale")
        return state

    @staticmethod
    def _assert_health(state: RobotNonrtState) -> None:
        if int(state.emg) or int(state.abnormal_stop) or int(state.safetydoor_alarm) or int(state.safetyplanealarm):
            raise BackendFailure("SAFETY_STOP", "FR5 safety or emergency stop is active")
        faults = (
            int(state.main_error_code),
            int(state.sub_error_code),
            int(state.alarm),
            int(state.motionalarm),
            int(state.cmdpointerror),
            float(state.collision_err),
        )
        if any(value != 0 for value in faults):
            raise BackendFailure("ROBOT_FAULT", f"FR5 fault state is active: {faults}")

    def _service(self, command: str, failure_code: str) -> str:
        if not self._client.wait_for_service(timeout_sec=self._service_timeout):
            raise BackendFailure("ROBOT_TIMEOUT", "FR5 command service is unavailable")
        request = RemoteCmdInterface.Request()
        request.cmd_str = command
        future = self._client.call_async(request)
        timeout = self._service_timeout
        if command.startswith(('MoveJ(', 'MoveL(')): timeout = 90.0
        elif command.startswith('MoveGripper('): timeout = 30.0
        elif command in ('StopMotion()', 'PauseMotion()'): timeout = 4.0
        deadline = time.monotonic() + timeout
        while rclpy.ok() and not future.done() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not future.done() or future.result() is None:
            raise BackendFailure("ROBOT_TIMEOUT", f"FR5 command timed out: {command}")
        response = str(future.result().cmd_res)
        if response.split(",", 1)[0] != "0":
            raise BackendFailure(failure_code, f"FR5 rejected {command}: {response}")
        return response

    @staticmethod
    def _response_numbers(response: str, count: int, label: str, code: str) -> tuple[float, ...]:
        fields = response.split(",")
        if not fields or fields[0] != "0" or len(fields) < count + 1:
            raise BackendFailure(code, f"invalid {label} response: {response}")
        try:
            values = tuple(float(value) for value in fields[1 : count + 1])
        except ValueError as error:
            raise BackendFailure(code, f"non-numeric {label} response: {response}") from error
        if not all(math.isfinite(value) for value in values):
            raise BackendFailure(code, f"non-finite {label} response: {response}")
        return values


class OperationJournal:
    """Internal operation evidence only; never reads or writes production Job/Unit DB."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _path(self, operation_id):
        from uuid import UUID
        return self.directory / (str(UUID(operation_id)) + '.json')

    def _write(self, path, value):
        temporary = path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            json.dump(value, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def restore(self):
        completed, unresolved = {}, False
        paths = sorted(self.directory.glob('*.json'), key=lambda p: p.stat().st_mtime_ns)
        last_held = False
        for path in paths:
            row = json.loads(path.read_text())
            request = row['request']
            if row['status'] == 'terminal':
                payload = row['event']
                event = OperationEvent(**(payload | {'event': Event(payload['event'])}))
                last_held = bool(row.get('held_candidate'))
                unresolved = unresolved or bool(row.get("recovery_required"))
            else:
                unresolved = True
                event = OperationEvent(request['job_id'], request['operation_id'], request['action'],
                    'VALIDATE', Event.OPERATION_FAILED, 'SAFETY_STOP',
                    'Operation outcome unknown after API restart; original intent retained, no physical replay.')
            completed[request['operation_id']] = (row['fingerprint'], event)
        return completed, unresolved or last_held

    def begin(self, operation, fingerprint):
        with self.lock:
            path = self._path(operation.operation_id)
            if path.exists():
                raise BackendFailure('SAFETY_STOP', 'operation already journaled; never reexecute')
            self._write(path, dict(status='intent', request=operation.to_dict(), fingerprint=fingerprint,
                                   started_unix=time.time()))

    def mark_recovery_required(self, operation):
        with self.lock:
            path = self._path(operation.operation_id)
            row = json.loads(path.read_text())
            self._write(path, dict(row, recovery_required=True))

    def finish(self, operation, fingerprint, event, held):
        with self.lock:
            path = self._path(operation.operation_id)
            existing = json.loads(path.read_text()) if path.exists() else {}
            if existing.get('status') == 'terminal':
                return  # Terminal replay must not rewrite the original outcome/holding evidence.
            self._write(path, dict(existing, status='terminal', request=operation.to_dict(),
                fingerprint=fingerprint, event=event.to_dict(), held_candidate=held is not None,
                finished_unix=time.time()))


def require_commissioned_step(operation):
    """No public contract change: reject uncommissioned physical operations before motion."""
    if operation.action is Action.TRANSFER:
        raise BackendFailure('SAFETY_STOP', 'Assembled PCB transfer is not commissioned')
    if operation.point_name in ('item_ready', 'assembly_ready'):
        raise BackendFailure('SAFETY_STOP',
            'Ready point remains an uncommissioned Home placeholder. No robot motion sent.')


class RealRobotApiNode(Node):
    """JSON command/event transport for the fail-closed Real backend."""

    def __init__(self) -> None:
        super().__init__("real_robot_api")
        self.declare_parameter("enable_hardware_execution", False)
        self.declare_parameter("enable_retained_resume", False)
        self.declare_parameter("enable_continuous_transfer", False)
        self.declare_parameter("command_topic", COMMAND_TOPIC)
        self.declare_parameter("event_topic", EVENT_TOPIC)
        self.declare_parameter("pause_topic", PAUSE_TOPIC)
        self.declare_parameter("vision_target_topic", VISION_TARGET_TOPIC)
        self.declare_parameter("robot_state_topic", ROBOT_STATE_TOPIC)
        self.declare_parameter("robot_command_service", ROBOT_COMMAND_SERVICE)
        self.declare_parameter("vision_max_age_sec", 2.5)
        self.declare_parameter("arm_timeout_sec", 90.0)
        self.declare_parameter("gripper_timeout_sec", 30.0)
        self.declare_parameter("travel_speed_percent", 25)
        self.declare_parameter("vertical_speed_percent", 10)
        self.declare_parameter("maximum_approach_dz_mm", 200.0)
        self.declare_parameter("maximum_retract_dz_mm", 200.0)
        self.declare_parameter("maximum_drop_approach_dz_mm", 250.0)

        event_qos = QoSProfile(
            depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._event_publisher = self.create_publisher(
            String, str(self.get_parameter("event_topic").value), event_qos
        )
        vision = RosTargetVisionPort(
            self,
            str(self.get_parameter("vision_target_topic").value),
            float(self.get_parameter("vision_max_age_sec").value),
        )
        robot = FairinoRobotPort(
            self,
            enabled=bool(self.get_parameter("enable_hardware_execution").value),
            state_topic=str(self.get_parameter("robot_state_topic").value),
            command_service=str(self.get_parameter("robot_command_service").value),
            travel_speed_percent=int(self.get_parameter("travel_speed_percent").value),
            vertical_speed_percent=int(self.get_parameter("vertical_speed_percent").value),
        )
        self._vision_port = vision
        self._robot_port = robot
        self._status_service = self.create_service(Trigger, "/real/robot/status", self._status_callback)
        ghost = RealGhostTargetPublisher(self, backend="real")
        limits = ContractLimits(
            maximum_approach_dz_mm=float(
                self.get_parameter("maximum_approach_dz_mm").value
            ),
            maximum_retract_dz_mm=float(
                self.get_parameter("maximum_retract_dz_mm").value
            ),
            maximum_drop_approach_dz_mm=float(
                self.get_parameter("maximum_drop_approach_dz_mm").value
            ),
        )
        self._preview_publisher = self.create_publisher(String, PREVIEW_EVENT_TOPIC, event_qos)
        self._preview = JointGhostPreview(validate_joint_target=robot.validate_joint_target,
                                          ghost=ghost, limits=limits)
        self.create_subscription(String, PREVIEW_COMMAND_TOPIC, self._preview_callback, 10)
        root = Path(os.environ["KSMC_ROOT"]).resolve() if os.environ.get("KSMC_ROOT") else None
        execution_guard = None
        if root is not None and (root / "run_fr5_cycle.sh").is_file():
            from .assembly_cycle_api import robot_execution_guard
            execution_guard = lambda: robot_execution_guard(root, job_id=self._backend._active.job_id)
        from .real_precision_steps import PrecisionSteps
        precision_steps = PrecisionSteps(root) if root is not None else None
        def commissioning_check(operation):
            require_commissioned_step(operation)
            if operation.action in (Action.PICK, Action.PLACE) and precision_steps is None:
                raise BackendFailure('SAFETY_STOP', 'precision adapter requires KSMC_ROOT')
        self._backend = RealRobotBackend(
            vision=vision,
            robot=robot,
            ghost=ghost,
            event_sink=self._publish_event,
            execution_guard=execution_guard,
            commissioning_check=commissioning_check,
            step_executor=precision_steps,
            retained_resume_enabled=bool(self.get_parameter("enable_retained_resume").value),
            operation_store=OperationJournal(root / "runtime/robot_operations") if root is not None else None,
            limits=limits,
            arm_timeout_sec=float(self.get_parameter("arm_timeout_sec").value),
            gripper_timeout_sec=float(self.get_parameter("gripper_timeout_sec").value),
        )
        self.create_subscription(
            String,
            str(self.get_parameter("command_topic").value),
            self._command_callback,
            10,
        )
        self.create_subscription(
            Bool,
            str(self.get_parameter("pause_topic").value),
            self._pause_callback,
            10,
        )
        self.create_subscription(String, "/real/robot/control", self._control_callback, 10)
        self._assembly_bridge = None
        if execution_guard is not None:
            from .assembly_cycle_ros import AssemblyCycleRosBridge
            self._assembly_bridge = AssemblyCycleRosBridge(self, root)
        self._backend.continuous_transfer_enabled = bool(self.get_parameter("enable_continuous_transfer").value)
        state = "ARMED" if bool(self.get_parameter("enable_hardware_execution").value) else "DISARMED"
        self.get_logger().warning(
            f"Real robot API ready in {state} mode; it reads no YAML or DB"
        )

    def _status_callback(self, request, response):
        """Read cached state only; never sends a FAIRINO command."""
        status = {"schema": "fr5.robot_api_status/v1",
                  "hardware_execution_enabled": self._robot_port._enabled,
                  "state_fresh": False,
                  "ghost_preview_enabled": True,
                  "ghost_preview_command_topic": PREVIEW_COMMAND_TOPIC,
                  "ghost_preview_event_topic": PREVIEW_EVENT_TOPIC,
                  "ghost_preview_actions": ["robot.move_joint"]}
        try:
            state = self._robot_port._fresh_state()
            status.update(state_fresh=True, robot_mode=int(state.robot_mode),
                tool_num=int(state.tool_num), work_num=int(state.work_num),
                robot_motion_done=int(state.robot_motion_done),
                gripper_feedback_valid=bool(state.gripper_feedback_valid))
        except BackendFailure as error:
            status["state_error"] = str(error)
        try:
            self._robot_port._assert_health(self._robot_port._fresh_state())
            status['robot_health_clear'] = True
        except BackendFailure:
            status['robot_health_clear'] = False
        status['api_capabilities_revision'] = 'step-cycle-20260908'
        status['continuous_transfer_enabled'] = bool(getattr(self._backend, 'continuous_transfer_enabled', False))
        status['event_context_revision'] = 'attachment-callbacks-v1'
        status['event_context'] = self._backend.event_context.snapshot()
        status['control'] = self._backend.control.status()
        status['control_topic'] = '/real/robot/control'
        status['recovery_required'] = self._backend._recovery_required
        with self._backend._state_lock:
            active = self._backend._active
            status['active_operation'] = None if active is None else dict(job_id=active.job_id,operation_id=active.operation_id,action=active.action.value)
        with self._vision_port._lock:
            payload = self._vision_port._payload or {}
            status['vision_plan_sha256'] = payload.get('plan_sha256')
            status['prepared_execution'] = {
                'job_id': payload.get('job_id'),
                'source_cycle_id': payload.get('source_cycle_id'),
                'plan_sha256': payload.get('plan_sha256'),
                'execution_context': payload.get('execution_context'),
                'parts': [{k: row.get(k) for k in ('source_id','tray_registration_id',
                    'source_observation_id','part_id','source_index','slot_code','order')}
                    for row in payload.get('parts', [])]}
        status['observed_unix'] = time.time()
        held = self._backend.held_part
        status["held_candidate"] = None if held is None else {
            "job_id": held.job_id, "part_id": held.part_id, "slot_code": held.slot_code}
        response.success = True  # API availability; not permission to move
        response.message = json.dumps(status)
        return response

    def _preview_callback(self, message: String) -> None:
        def publish_preview():
            result = self._preview.execute(message.data)
            self._preview_publisher.publish(String(data=json.dumps(result, allow_nan=False)))
        threading.Thread(target=publish_preview, daemon=True, name="ghost-preview").start()

    def _command_callback(self, message: String) -> None:
        threading.Thread(
            target=self._backend.execute,
            args=(message.data,),
            daemon=True,
            name="real-robot-operation",
        ).start()

    def _control_callback(self, message: String) -> None:
        threading.Thread(target=self._backend.control.request, args=(message.data,),
                         daemon=True, name='real-robot-control').start()

    def _pause_callback(self, message: Bool) -> None:
        if bool(message.data):
            threading.Thread(target=self._backend.pause, daemon=True, name="real-robot-pause").start()

    def _publish_event(self, event: OperationEvent) -> None:
        message = String()
        message.data = event.to_json()
        self._event_publisher.publish(message)


def _wrapped_degrees(value: float) -> float:
    return (float(value) + 180.0) % 360.0 - 180.0


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RealRobotApiNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node._assembly_bridge is not None:
            node._assembly_bridge.controller.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
