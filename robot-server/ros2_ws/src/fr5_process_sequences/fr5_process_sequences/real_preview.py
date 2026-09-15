"""Explicit joint-target preview. Has no robot execution or stop interface."""
from collections import OrderedDict
import json
import threading
from .real_contract import Action, ContractError, parse_operation

PREVIEW_COMMAND_TOPIC = "/real/ghost/command"
PREVIEW_EVENT_TOPIC = "/real/ghost/event"


class JointGhostPreview:
    def __init__(self, *, validate_joint_target, ghost, limits=None):
        self.validate_joint_target = validate_joint_target
        self.ghost = ghost
        self.limits = limits
        self.lock = threading.Lock()
        self.completed = OrderedDict()

    def execute(self, payload):
        data = {}
        result = dict(schema="fr5.ghost_preview_event/v1", job_id="", operation_id="",
                      action="", event="PREVIEW_FAILED", preview_only=True,
                      robot_motion_authorized=False, error_code="", message="")
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
            if not isinstance(data, dict):
                raise ContractError("request must be an object")
            for key in ("job_id", "operation_id", "action"):
                result[key] = data.get(key, "") if isinstance(data.get(key, ""), str) else ""
            operation = parse_operation(data, limits=self.limits)
            if operation.action is not Action.MOVE_JOINT:
                raise ContractError("Ghost preview supports robot.move_joint only")
            fingerprint = json.dumps(data, sort_keys=True, allow_nan=False)
            if not self.lock.acquire(blocking=False):
                result.update(error_code="ROBOT_BUSY", message="another Ghost preview is active")
                return result
            try:
                previous = self.completed.get(operation.operation_id)
                if previous is not None:
                    if previous[0] != fingerprint:
                        raise ContractError("operation_id reused with different content")
                    return dict(previous[1])
                self.validate_joint_target(operation.joint_point)
                published = self.ghost.publish_stage_target(operation.joint_point,
                    job_id=operation.job_id, operation_id=operation.operation_id,
                    action=operation.action.value, phase="MOVE_JOINT",
                    point_name=operation.point_name, preview_only=True)
                if not published:
                    raise RuntimeError("Ghost publisher failed; delivery may be partial")
                result.update(event="PREVIEW_PUBLISHED", phase="MOVE_JOINT",
                    message="Ghost targets published; no robot motion sent; subscriber receipt is not acknowledged")
                self.completed[operation.operation_id] = (fingerprint, dict(result))
                if len(self.completed) > 128:
                    self.completed.popitem(last=False)
                return result
            finally:
                self.lock.release()
        except Exception as error:
            result.update(error_code=getattr(error, "code", "PREVIEW_FAILED"), message=str(error))
            return result
