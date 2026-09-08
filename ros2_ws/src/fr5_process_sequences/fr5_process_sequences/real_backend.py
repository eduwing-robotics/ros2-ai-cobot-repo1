"""Fail-closed execution core for the Real robot operation contract.

This module is deliberately transport neutral and never reads YAML or a DB.
Vision, FR5 control, Ghost publication, and callbacks are injected ports.  A
production ROS node can bind those ports without moving contract ownership out
of this core.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import threading
from typing import Any, Callable, Mapping, Protocol, Sequence

from .real_contract import (
    Action,
    ContractError,
    ContractLimits,
    Event,
    OperationEvent,
    RobotOperation,
    parse_operation,
)


class BackendFailure(RuntimeError):
    """A named operation failure suitable for the completion callback."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CartesianTarget:
    """Internal FR5 TCP target; never accepted from Unity or the Sequencer."""

    frame_id: str
    x_mm: float
    y_mm: float
    z_mm: float
    rx_deg: float
    ry_deg: float
    rz_deg: float

    def __post_init__(self) -> None:
        values = (
            self.x_mm,
            self.y_mm,
            self.z_mm,
            self.rx_deg,
            self.ry_deg,
            self.rz_deg,
        )
        if self.frame_id != "base_link":
            raise BackendFailure(
                "FRAME_TRANSFORM_FAILED", "Vision target is not in base_link"
            )
        if not all(math.isfinite(value) for value in values):
            raise BackendFailure(
                "FRAME_TRANSFORM_FAILED", "Vision target contains a non-finite value"
            )

    def raised(self, dz_mm: float) -> "CartesianTarget":
        return CartesianTarget(
            self.frame_id,
            self.x_mm,
            self.y_mm,
            self.z_mm + dz_mm,
            self.rx_deg,
            self.ry_deg,
            self.rz_deg,
        )

    def controller_pose(self) -> tuple[float, ...]:
        return (
            self.x_mm,
            self.y_mm,
            self.z_mm,
            self.rx_deg,
            self.ry_deg,
            self.rz_deg,
        )


@dataclass(frozen=True)
class TransferTarget:
    pickup: CartesianTarget
    drop: CartesianTarget


@dataclass(frozen=True)
class HeldPart:
    job_id: str
    part_id: str
    slot_code: str
    order: int
    source_index: int | None = None


class VisionPort(Protocol):
    def locate_part(self, part_id: str, order: int) -> CartesianTarget: ...

    def locate_slot(self, part_id: str, slot_code: str, order: int) -> CartesianTarget: ...

    def locate_transfer(self, object_id: str) -> TransferTarget: ...


class RobotPort(Protocol):
    def assert_ready(self) -> None: ...

    def current_joints_deg(self) -> tuple[float, ...]: ...

    def validate_joint_target(self, joints_deg: Sequence[float]) -> None: ...

    def inverse_kinematics(
        self, target: CartesianTarget, reference_joints_deg: Sequence[float]
    ) -> tuple[float, ...]: ...

    def move_joint(self, joints_deg: Sequence[float]) -> None: ...

    def move_cartesian(
        self,
        target: CartesianTarget,
        joints_deg: Sequence[float],
        *,
        linear: bool,
    ) -> None: ...

    def move_gripper(self, opening_percent: float) -> None: ...

    def wait_arm_complete(
        self,
        target: CartesianTarget | None,
        joints_deg: Sequence[float],
        timeout_sec: float,
    ) -> None: ...

    def wait_gripper_complete(self, opening_percent: float, timeout_sec: float) -> None: ...

    def stop_motion(self) -> None: ...

    def pause_motion(self) -> None: ...


class GhostPort(Protocol):
    def publish_joint_target(self, joints_deg: Sequence[float]) -> bool: ...


EventSink = Callable[[OperationEvent], None]


@dataclass(frozen=True)
class _ArmMove:
    phase: str
    target: CartesianTarget | None
    joints_deg: tuple[float, ...]
    linear: bool


class RealRobotBackend:
    """Execute one operation at a time with preflighted IK and state gates."""

    def __init__(
        self,
        *,
        vision: VisionPort,
        robot: RobotPort,
        ghost: GhostPort,
        event_sink: EventSink,
        limits: ContractLimits | None = None,
        arm_timeout_sec: float = 90.0,
        gripper_timeout_sec: float = 30.0,
        execution_guard=None,
        commissioning_check=None,
        operation_store=None,
        step_executor=None,
        retained_resume_enabled=False,
    ) -> None:
        self._step_executor = step_executor
        self._completion_message = ""
        self._commissioning_check = commissioning_check
        self._operation_store = operation_store
        self._execution_guard = execution_guard
        self._vision = vision
        self._robot = robot
        self._ghost = ghost
        self._event_sink = event_sink
        self._limits = limits or ContractLimits()
        self._arm_timeout_sec = _positive_timeout(arm_timeout_sec, "arm_timeout_sec")
        self._gripper_timeout_sec = _positive_timeout(
            gripper_timeout_sec, "gripper_timeout_sec"
        )
        self._state_lock = threading.Lock()
        from .robot_event_context import RobotEventContext
        self.event_context = RobotEventContext()
        self._held: HeldPart | None = None
        self._completed: dict[str, tuple[str, OperationEvent]] = {}
        self._active: RobotOperation | None = None
        self._active_fingerprint: str | None = None
        self._active_event: OperationEvent | None = None
        self._paused = threading.Event()
        self._gripper_profiles = {}
        self._recovery_required = False
        from .retained_robot_control import RetainedRobotControl
        self.control = RetainedRobotControl(self, enabled=retained_resume_enabled)
        if operation_store is not None:
            self._completed, self._recovery_required = operation_store.restore()

    @property
    def held_part(self) -> HeldPart | None:
        with self._state_lock:
            return self._held

    def execute(self, payload: str | Mapping[str, Any]) -> OperationEvent:
        """Run a new command, replay a result, or return active request status.

        An identical active retransmission joins the original event stream;
        it never executes hardware again or publishes a terminal busy failure.
        Conflicting content for any reserved or completed ID gets
        REQUEST_REJECTED, deliberately nonterminal for the original operation.
        """
        try:
            operation = parse_operation(payload, limits=self._limits)
        except ContractError as error:
            terminal = self._invalid_event(payload, error)
            with self._state_lock:
                if ((self._active is not None and
                     self._active.operation_id == terminal.operation_id) or
                        terminal.operation_id in self._completed):
                    terminal = replace(terminal, event=Event.REQUEST_REJECTED)
            self._emit(terminal)
            return terminal

        fingerprint = _fingerprint(operation)
        # Checking IDs and reserving the execution slot must be one atomic step.
        # A separate try-lock leaves a gap in which a duplicate looks unrelated.
        response = None
        with self._state_lock:
            previous = self._completed.get(operation.operation_id)
            if previous is not None:
                previous_fingerprint, response = previous
                if previous_fingerprint != fingerprint:
                    response = self._event(
                        operation, phase="VALIDATE", event=Event.REQUEST_REJECTED,
                        error_code="INVALID_REQUEST",
                        message="operation_id was already used with different content",
                    )
            elif self.control.blocked.is_set() and self._active is None:
                response = self._event(operation, phase='VALIDATE', event=Event.REQUEST_REJECTED,
                    error_code='SAFETY_STOP', message='retained pause blocks new operation dispatch')
            elif self._recovery_required:
                response = self._event(operation, phase="VALIDATE", event=Event.OPERATION_FAILED,
                    error_code="SAFETY_STOP", message="Unresolved operation after API restart; inspect/reset equipment and start a new Unit through Sequencer. No automatic replay.")
            elif self._active is not None:
                if self._active.operation_id == operation.operation_id:
                    if self._active_fingerprint == fingerprint:
                        # The original worker will publish the one terminal result.
                        # No replayed phase can arrive after that terminal event.
                        assert self._active_event is not None
                        return self._active_event
                    response = self._event(
                        operation, phase="VALIDATE", event=Event.REQUEST_REJECTED,
                        error_code="INVALID_REQUEST",
                        message="active operation_id has different content; original operation continues",
                    )
                else:
                    response = self._event(
                        operation, phase="VALIDATE", event=Event.OPERATION_FAILED,
                        error_code="ROBOT_BUSY",
                        message="another Real robot operation is active",
                    )
                    self._completed[operation.operation_id] = (fingerprint, response)
            else:
                self._active = operation
                self._active_fingerprint = fingerprint
                self._active_event = self._event(
                    operation, phase="VALIDATE", event=Event.PHASE_STARTED)
                self._paused.clear()
        if response is not None:
            if self._operation_store is not None and not self._recovery_required and response.event is Event.OPERATION_FAILED:
                self._operation_store.finish(operation, fingerprint, response, self._held)
            self._emit(response)
            return response

        phase = "VALIDATE"
        self._phase_name = phase
        guard = None
        owns_execution = False
        try:
            if self._operation_store is not None:
                self._operation_store.begin(operation, fingerprint)
            if self._commissioning_check is not None:
                self._commissioning_check(operation)
            if self._execution_guard is not None:
                guard = self._execution_guard()
                guard.__enter__()
            owns_execution = True
            def validate_resume():
                if self._recovery_required or self._paused.is_set():
                    raise BackendFailure('SAFETY_STOP', 'failed/cancelled context cannot resume')
                self._robot.assert_ready()
            self.control.register(operation, validate_resume)
            self._robot.assert_ready()
            self._completion_message = ""
            self._gripper_profiles = {}
            if operation.source_index is not None and self._step_executor is None:
                self._gripper_profiles = self._vision.validate_operation(operation) or {}
            if operation.action is Action.MOVE_JOINT:
                phase = self._execute_move_joint(operation)
            elif operation.action is Action.PICK:
                phase = (self._step_executor.execute(self, operation) if self._step_executor
                         else self._execute_pick(operation))
            elif operation.action is Action.PLACE:
                phase = (self._step_executor.execute(self, operation) if self._step_executor
                         else self._execute_place(operation))
            else:
                phase = self._execute_transfer(operation)
            terminal = self._event(
                operation,
                phase=phase,
                event=Event.OPERATION_COMPLETED,
                message=self._completion_message,
            )
        except BackendFailure as error:
            stop_result = self._best_effort_stop() if owns_execution else ""
            terminal = self._event(
                operation,
                phase=self._phase_name,
                event=Event.OPERATION_FAILED,
                error_code=error.code,
                message=str(error) + ("; " + stop_result if stop_result else ""),
            )
        except Exception as error:
            stop_result = self._best_effort_stop() if owns_execution else ""
            terminal = self._event(
                operation,
                phase=self._phase_name,
                event=Event.OPERATION_FAILED,
                error_code="ROBOT_FAULT",
                message=f"unexpected backend failure: {error}" + ("; " + stop_result if stop_result else ""),
            )
        finally:
            if self._operation_store is not None:
                try:
                    if self._recovery_required:
                        self._operation_store.mark_recovery_required(operation)
                    self._operation_store.finish(operation, fingerprint, terminal, self._held)
                except Exception as storage_error:
                    self._recovery_required = True
                    terminal = self._event(operation, phase=self._phase_name, event=Event.OPERATION_FAILED,
                        error_code=terminal.error_code or 'SAFETY_STOP',
                        message=(terminal.message + '; result persistence failed: ' + str(storage_error)))
            if guard is not None and owns_execution:
                guard.__exit__(None, None, None)
            with self._state_lock:
                self._active = None
                self._active_fingerprint = None
                self._active_event = None
                self._completed[operation.operation_id] = (fingerprint, terminal)
        self._emit(terminal)
        return terminal

    def pause(self, message: str = "operation paused by request") -> OperationEvent | None:
        """Pause the active motion and emit the required PAUSED event."""
        with self._state_lock:
            operation = self._active
        if operation is None:
            return None
        self._paused.set()
        try:
            self._robot.pause_motion()
            observe = getattr(self._robot, "observe_stopped", None)
            message = "pause requested; " + (observe() if observe else "stop_not_verified")
        except Exception as error:
            message = f"pause requested; controller response failed: {error}"
        confirmed = 'fresh_feedback_verified_stopped' in message and 'failed' not in message
        event = self._event(operation, phase="PAUSE",
            event=Event.PAUSED if confirmed else Event.CONTROL_FAILED,
            error_code='' if confirmed else 'SAFETY_STOP',
            message=json.dumps(dict(reason=message, stop_verified=confirmed,
                resume_available=False, control_mode='legacy_cancel')) )
        self._emit(event)
        return event

    def _execute_move_joint(self, operation: RobotOperation) -> str:
        assert operation.joint_point is not None
        if self._step_executor is not None and operation.point_name in ('PlaceCamera','TrayHome','SMDView'):
            return self._step_executor.execute_camera(self, operation)
        joints = tuple(operation.joint_point)
        self._robot.validate_joint_target(joints)
        move = _ArmMove("MOVE_JOINT", None, joints, False)
        self._run_arm(operation, move, joint_only=True)
        return move.phase

    def _execute_pick(self, operation: RobotOperation) -> str:
        assert operation.part_id is not None
        assert operation.slot_code is not None
        assert operation.order is not None
        assert operation.approach_dz_mm is not None
        assert operation.retract_dz_mm is not None
        assert operation.grasp_opening_percent is not None
        assert operation.release_opening_percent is not None
        with self._state_lock:
            if self._held is not None:
                raise BackendFailure(
                    "GRIPPER_FAILED",
                    f"backend already tracks held slot {self._held.slot_code}",
                )

        contact = self._vision_phase(
            operation,
            "DETECT_PART",
            lambda: (self._vision.locate_part_by_index(
                operation.part_id, operation.source_index, operation.job_id)
                if operation.source_index is not None else
                self._vision.locate_part(operation.part_id, operation.order)),
        )
        moves = self._preflight_cartesian(
            (
                ("APPROACH", contact.raised(operation.approach_dz_mm), False),
                ("DESCEND", contact, True),
                ("RETRACT", contact.raised(operation.retract_dz_mm), True),
            )
        )
        self._run_arm(operation, moves[0])
        self._run_gripper(operation, "PREOPEN",
            operation.pregrasp_opening_percent if operation.pregrasp_opening_percent is not None
            else operation.release_opening_percent)
        self._run_arm(operation, moves[1])
        self._run_gripper(operation, "GRASP", operation.grasp_opening_percent)
        with self._state_lock:
            self._held = HeldPart(
                operation.job_id,
                operation.part_id,
                operation.slot_code,
                operation.order,
                operation.source_index,
            )
        self._run_arm(operation, moves[2])
        return "RETRACT"

    def _execute_place(self, operation: RobotOperation) -> str:
        assert operation.part_id is not None
        assert operation.slot_code is not None
        assert operation.order is not None
        assert operation.approach_dz_mm is not None
        assert operation.retract_dz_mm is not None
        assert operation.release_opening_percent is not None
        with self._state_lock:
            held = self._held
        expected = (
            operation.job_id,
            operation.part_id,
            operation.slot_code,
            operation.order,
            operation.source_index,
        )
        actual = None if held is None else (
            held.job_id,
            held.part_id,
            held.slot_code,
            held.order,
            held.source_index,
        )
        if actual != expected:
            raise BackendFailure(
                "GRIPPER_FAILED",
                "place does not match the successfully completed pick correlation",
            )

        contact = self._vision_phase(
            operation,
            "DETECT_SLOT",
            lambda: (self._vision.locate_slot_for_job(
                operation.part_id, operation.slot_code, operation.source_index, operation.job_id)
                if operation.source_index is not None else self._vision.locate_slot(
                    operation.part_id, operation.slot_code, operation.order)),
        )
        moves = self._preflight_cartesian(
            (
                ("APPROACH", contact.raised(operation.approach_dz_mm), False),
                ("DESCEND", contact, True),
                ("RETRACT", contact.raised(operation.retract_dz_mm), True),
            )
        )
        self._run_arm(operation, moves[0])
        self._run_arm(operation, moves[1])
        self._run_gripper(operation, "RELEASE", operation.release_opening_percent)
        with self._state_lock:
            self._held = None
        self._run_arm(operation, moves[2])
        return "RETRACT"

    def _execute_transfer(self, operation: RobotOperation) -> str:
        assert operation.object_id is not None
        assert operation.approach_dz_mm is not None
        assert operation.retract_dz_mm is not None
        assert operation.assembled_pcb_drop_approach_dz_mm is not None
        assert operation.grasp_opening_percent is not None
        assert operation.release_opening_percent is not None
        targets = self._vision_phase(
            operation,
            "DETECT_TRANSFER",
            lambda: self._vision.locate_transfer(operation.object_id),
        )
        moves = self._preflight_cartesian(
            (
                ("PICK_APPROACH", targets.pickup.raised(operation.approach_dz_mm), False),
                ("PICK_DESCEND", targets.pickup, True),
                ("PICK_RETRACT", targets.pickup.raised(operation.retract_dz_mm), True),
                (
                    "DROP_APPROACH",
                    targets.drop.raised(operation.assembled_pcb_drop_approach_dz_mm),
                    False,
                ),
                ("DROP_DESCEND", targets.drop, True),
                ("DROP_RETRACT", targets.drop.raised(operation.retract_dz_mm), True),
            )
        )
        self._run_arm(operation, moves[0])
        self._run_gripper(operation, "PREOPEN",
            operation.pregrasp_opening_percent if operation.pregrasp_opening_percent is not None
            else operation.release_opening_percent)
        self._run_arm(operation, moves[1])
        self._run_gripper(operation, "GRASP", operation.grasp_opening_percent)
        self._run_arm(operation, moves[2])
        self._run_arm(operation, moves[3])
        self._run_arm(operation, moves[4])
        self._run_gripper(operation, "RELEASE", operation.release_opening_percent)
        self._run_arm(operation, moves[5])
        return "DROP_RETRACT"

    def _vision_phase(
        self,
        operation: RobotOperation,
        phase: str,
        function: Callable[[], Any],
    ) -> Any:
        self._phase_event(operation, phase, Event.PHASE_STARTED)
        result = function()
        self._phase_event(operation, phase, Event.PHASE_COMPLETED)
        return result

    def _preflight_cartesian(
        self, specifications: Sequence[tuple[str, CartesianTarget, bool]]
    ) -> tuple[_ArmMove, ...]:
        reference = self._robot.current_joints_deg()
        if len(reference) != 6 or not all(math.isfinite(value) for value in reference):
            raise BackendFailure("ROBOT_FAULT", "invalid current J1..J6 state")
        moves: list[_ArmMove] = []
        for phase, target, linear in specifications:
            try:
                joints = tuple(self._robot.inverse_kinematics(target, reference))
                if len(joints) != 6 or not all(math.isfinite(value) for value in joints):
                    raise ValueError("IK did not return six finite joints")
                self._robot.validate_joint_target(joints)
            except BackendFailure:
                raise
            except Exception as error:
                raise BackendFailure(
                    "IK_FAILED", f"{phase} inverse kinematics failed: {error}"
                ) from error
            moves.append(_ArmMove(phase, target, joints, linear))
            reference = joints
        return tuple(moves)

    def _run_arm(
        self, operation: RobotOperation, move: _ArmMove, *, joint_only: bool = False
    ) -> None:
        self._phase_name = move.phase
        self._assert_phase_ready()
        prepare = getattr(self._robot, "prepare_motion", None)
        if prepare is not None:
            move = _ArmMove(move.phase, move.target,
                tuple(prepare(move.target, move.joints_deg)), move.linear)
        self._phase_event(operation, move.phase, Event.PHASE_STARTED)
        # Ghost is visualization-only.  A publish failure cannot authorize or
        # inhibit Real motion and is intentionally not a completion condition.
        publish_stage = getattr(self._ghost, "publish_stage_target", None)
        if publish_stage is not None:
            publish_stage(move.joints_deg, job_id=operation.job_id,
                operation_id=operation.operation_id, action=operation.action.value,
                phase=move.phase, point_name=operation.point_name)
        else:
            self._ghost.publish_joint_target(move.joints_deg)
        self._assert_not_paused()
        if joint_only:
            self._robot.move_joint(move.joints_deg)
        else:
            assert move.target is not None
            self._robot.move_cartesian(
                move.target, move.joints_deg, linear=move.linear
            )
        self._robot.wait_arm_complete(
            move.target, move.joints_deg, self._arm_timeout_sec
        )
        self._phase_event(operation, move.phase, Event.PHASE_COMPLETED)

    def _run_gripper(
        self, operation: RobotOperation, phase: str, opening_percent: float
    ) -> None:
        self._assert_phase_ready()
        self._phase_event(operation, phase, Event.PHASE_STARTED)
        if self._gripper_profiles:
            self._robot.move_profiled_gripper(opening_percent, self._gripper_profiles[phase])
        else:
            self._robot.move_gripper(opening_percent)
        self._robot.wait_gripper_complete(opening_percent, self._gripper_timeout_sec)
        self._phase_event(operation, phase, Event.PHASE_COMPLETED)

    def _assert_not_paused(self) -> None:
        self.control.checkpoint()
        if self._paused.is_set():
            raise BackendFailure("SAFETY_STOP", "operation paused; no subsequent phase permitted")

    def _assert_phase_ready(self) -> None:
        self._assert_not_paused()
        self._robot.assert_ready()

    def _phase_event(self, operation: RobotOperation, phase: str, event: Event, *, feedback=None) -> None:
        self._assert_not_paused()
        self._phase_name = phase
        self._emit(self._event(operation, phase=phase, event=event, feedback=feedback))

    def _event(
        self, operation: RobotOperation,
        *,
        phase: str,
        event: Event,
        error_code: str = "",
        message: str = "",
        feedback=None,
    ) -> OperationEvent:
        message = self.event_context.message(operation, phase, event, message, feedback)
        return OperationEvent(
            operation.job_id,
            operation.operation_id,
            operation.action.value,
            phase,
            event,
            error_code,
            message,
        )

    @staticmethod
    def _invalid_event(
        payload: str | Mapping[str, Any], error: ContractError
    ) -> OperationEvent:
        data: Mapping[str, Any] = {}
        if isinstance(payload, Mapping):
            data = payload
        elif isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, Mapping):
                    data = parsed
            except json.JSONDecodeError:
                pass
        return OperationEvent(
            str(data.get("job_id", "")),
            str(data.get("operation_id", "")),
            str(data.get("action", "")),
            "VALIDATE",
            Event.OPERATION_FAILED,
            error.code,
            str(error),
        )

    def _best_effort_stop(self) -> str:
        try:
            self._robot.stop_motion()
            observe = getattr(self._robot, "observe_stopped", None)
            return observe() if observe else ""
        except Exception as error:
            return f"stop_not_verified: {error}"

    def _emit(self, event: OperationEvent) -> None:
        self.event_context.observe(event)
        if event.event in (Event.PHASE_STARTED, Event.PHASE_COMPLETED, Event.PAUSED):
            with self._state_lock:
                if self._active is not None and self._active.operation_id == event.operation_id:
                    self._active_event = event
        try:
            self._event_sink(event)
        except Exception:
            # Callback transport cannot change the physical operation result.
            pass


def _fingerprint(operation: RobotOperation) -> str:
    encoded = json.dumps(
        operation.to_dict(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _positive_timeout(value: float, field: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{field} must be finite and positive")
    return result
