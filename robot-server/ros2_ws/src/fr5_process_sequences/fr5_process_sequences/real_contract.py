"""Transport-neutral command and event contract for the Real robot backend.

The Sequencer owns ordering and process values.  It must never provide a
Cartesian robot target; those targets are produced inside the Real backend by
its Vision adapter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
import math
from typing import Any, Mapping
from uuid import UUID


class Action(str, Enum):
    MOVE_JOINT = "robot.move_joint"
    PICK = "robot.pick"
    PLACE = "robot.place"
    TRANSFER = "robot.transfer"


class Event(str, Enum):
    PHASE_STARTED = "PHASE_STARTED"
    PHASE_COMPLETED = "PHASE_COMPLETED"
    OPERATION_COMPLETED = "OPERATION_COMPLETED"
    OPERATION_FAILED = "OPERATION_FAILED"
    PAUSED = "PAUSED"
    PAUSE_CONFIRMED = "PAUSE_CONFIRMED"
    RESUME_CONFIRMED = "RESUME_CONFIRMED"
    CONTROL_FAILED = "CONTROL_FAILED"
    CONTROL_REJECTED = "CONTROL_REJECTED"
    # Reject conflicting content without replacing an active/completed ID's result.
    REQUEST_REJECTED = "REQUEST_REJECTED"


REQUIRED_FAILURE_CODES = frozenset(
    {
        "CAMERA_NOT_READY",
        "PART_NOT_FOUND",
        "SLOT_NOT_FOUND",
        "FRAME_TRANSFORM_FAILED",
        "IK_FAILED",
        "ROBOT_TIMEOUT",
        "ROBOT_FAULT",
        "GRIPPER_FAILED",
        "SAFETY_STOP",
    }
)

# Contract validation and concurrency errors are extensions to the minimum
# list.  They are necessary to reject malformed or duplicated commands before
# any hardware call is possible.
EXTENDED_FAILURE_CODES = frozenset({"INVALID_REQUEST", "ROBOT_BUSY"})
FAILURE_CODES = REQUIRED_FAILURE_CODES | EXTENDED_FAILURE_CODES


class ContractError(ValueError):
    """A command cannot be accepted by the Real backend."""

    def __init__(self, message: str, code: str = "INVALID_REQUEST") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ContractLimits:
    """Backend-owned safety bounds; these values never come from YAML."""

    maximum_approach_dz_mm: float = 200.0
    maximum_retract_dz_mm: float = 200.0
    maximum_drop_approach_dz_mm: float = 250.0
    maximum_absolute_joint_deg: float = 360.0

    def __post_init__(self) -> None:
        values = (
            self.maximum_approach_dz_mm,
            self.maximum_retract_dz_mm,
            self.maximum_drop_approach_dz_mm,
            self.maximum_absolute_joint_deg,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in values):
            raise ValueError("all Real backend safety limits must be finite and positive")


@dataclass(frozen=True)
class RobotOperation:
    job_id: str
    operation_id: str
    action: Action
    joint_point: tuple[float, ...] | None = None
    point_name: str | None = None
    source_index: int | None = None
    pregrasp_opening_percent: float | None = None
    order: int | None = None
    part_id: str | None = None
    slot_code: str | None = None
    object_id: str | None = None
    approach_dz_mm: float | None = None
    retract_dz_mm: float | None = None
    assembled_pcb_drop_approach_dz_mm: float | None = None
    grasp_opening_percent: float | None = None
    release_opening_percent: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action"] = self.action.value
        return {key: value for key, value in data.items() if value is not None}


@dataclass(frozen=True)
class OperationEvent:
    job_id: str
    operation_id: str
    action: str
    phase: str
    event: Event
    error_code: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        data["event"] = self.event.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))


_COMMON_FIELDS = {"job_id", "operation_id", "action"}
_FIELDS_BY_ACTION = {
    Action.MOVE_JOINT: _COMMON_FIELDS | {"joint_point"},
    Action.PICK: _COMMON_FIELDS
    | {
        "order",
        "part_id",
        "slot_code",
        "approach_dz_mm",
        "retract_dz_mm",
        "grasp_opening_percent",
        "release_opening_percent",
    },
    Action.PLACE: _COMMON_FIELDS
    | {
        "order",
        "part_id",
        "slot_code",
        "approach_dz_mm",
        "retract_dz_mm",
        "release_opening_percent",
    },
    Action.TRANSFER: _COMMON_FIELDS
    | {
        "object_id",
        "approach_dz_mm",
        "retract_dz_mm",
        "assembled_pcb_drop_approach_dz_mm",
        "grasp_opening_percent",
        "release_opening_percent",
    },
}


_OPTIONAL_FIELDS = {
    Action.MOVE_JOINT: {"point_name"},
    Action.PICK: {"source_index", "pregrasp_opening_percent"},
    Action.PLACE: {"source_index"},
    Action.TRANSFER: {"pregrasp_opening_percent"},
}

def parse_operation(
    payload: str | Mapping[str, Any],
    *,
    limits: ContractLimits | None = None,
) -> RobotOperation:
    """Parse one fail-closed operation and reject undeclared coordinates."""
    limits = limits or ContractLimits()
    data = _as_object(payload)
    job_id = _uuid(data.get("job_id"), "job_id")
    operation_id = _uuid(data.get("operation_id"), "operation_id")
    try:
        action = Action(str(data.get("action", "")))
    except ValueError as exc:
        raise ContractError("action must be one of the supported robot.* actions") from exc

    allowed = _FIELDS_BY_ACTION[action]
    unexpected = sorted(set(data) - allowed - _OPTIONAL_FIELDS[action])
    if unexpected:
        raise ContractError(
            "unexpected fields for " + action.value + ": " + ", ".join(unexpected)
        )
    missing = sorted(allowed - set(data))
    if missing:
        raise ContractError(
            "missing fields for " + action.value + ": " + ", ".join(missing)
        )

    if action is Action.MOVE_JOINT:
        joints = _joint_point(data["joint_point"], limits)
        return RobotOperation(job_id, operation_id, action, joint_point=joints,
            point_name=_identifier(data["point_name"], "point_name") if "point_name" in data else None)

    source_index = (_positive_integer(data["source_index"], "source_index")
                    if "source_index" in data else None)
    pregrasp = (_opening(data["pregrasp_opening_percent"], "pregrasp_opening_percent")
                if "pregrasp_opening_percent" in data else None)

    approach = _bounded_positive(
        data["approach_dz_mm"],
        "approach_dz_mm",
        limits.maximum_approach_dz_mm,
    )
    retract = _bounded_positive(
        data["retract_dz_mm"],
        "retract_dz_mm",
        limits.maximum_retract_dz_mm,
    )

    if action in (Action.PICK, Action.PLACE):
        order = _positive_integer(data["order"], "order")
        part_id = _identifier(data["part_id"], "part_id")
        slot_code = _identifier(data["slot_code"], "slot_code")
        release = _opening(data["release_opening_percent"], "release_opening_percent")
        grasp = None
        if action is Action.PICK:
            grasp = _opening(data["grasp_opening_percent"], "grasp_opening_percent")
        return RobotOperation(
            job_id,
            operation_id,
            action,
            order=order,
            source_index=source_index,
            pregrasp_opening_percent=pregrasp,
            part_id=part_id,
            slot_code=slot_code,
            approach_dz_mm=approach,
            retract_dz_mm=retract,
            grasp_opening_percent=grasp,
            release_opening_percent=release,
        )

    return RobotOperation(
        job_id,
        operation_id,
        action,
        pregrasp_opening_percent=pregrasp,
        object_id=_identifier(data["object_id"], "object_id"),
        approach_dz_mm=approach,
        retract_dz_mm=retract,
        assembled_pcb_drop_approach_dz_mm=_bounded_positive(
            data["assembled_pcb_drop_approach_dz_mm"],
            "assembled_pcb_drop_approach_dz_mm",
            limits.maximum_drop_approach_dz_mm,
        ),
        grasp_opening_percent=_opening(
            data["grasp_opening_percent"], "grasp_opening_percent"
        ),
        release_opening_percent=_opening(
            data["release_opening_percent"], "release_opening_percent"
        ),
    )


def _as_object(payload: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, str):
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ContractError(f"invalid JSON: {exc.msg}") from exc
    else:
        value = payload
    if not isinstance(value, Mapping):
        raise ContractError("operation payload must be a JSON object")
    return dict(value)


def _uuid(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a UUID string")
    try:
        return str(UUID(value.strip()))
    except ValueError as exc:
        raise ContractError(f"{field} must be a valid UUID") from exc


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > 128:
        raise ContractError(f"{field} exceeds 128 characters")
    return normalized


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{field} must be finite")
    return result


def _bounded_positive(value: Any, field: str, maximum: float) -> float:
    result = _number(value, field)
    if not 0.0 < result <= maximum:
        raise ContractError(f"{field} must be in (0, {maximum:g}] mm")
    return result


def _opening(value: Any, field: str) -> float:
    result = _number(value, field)
    if not 0.0 <= result <= 100.0:
        raise ContractError(f"{field} must be in [0, 100] percent")
    return result


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContractError(f"{field} must be a positive integer")
    return value


def _joint_point(value: Any, limits: ContractLimits) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        raise ContractError("joint_point must contain J1 through J6")
    joints = tuple(_number(item, f"joint_point[{index}]") for index, item in enumerate(value))
    if any(abs(value) > limits.maximum_absolute_joint_deg for value in joints):
        raise ContractError(
            "joint_point exceeds the backend absolute joint safety bound"
        )
    return joints
