#!/usr/bin/env python3
"""Production lifecycle orchestration; YAML motion execution is Mock-only."""

import os
import json
import sys
import uuid

import rclpy
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from .db import DbWriter
from .db.writer import DB_SYNC_TIMEOUT_SECONDS
from .mock_backend import MockBackend
from .real_backend import RealBackend
from .recipe_contract import (
    RELAY_STATES,
    apply_relay_feedback,
    assembly_snapshot,
    resolve_observations,
    failed_feedback,
    load_recipe,
    parse_command,
    parse_feedback,
    self_check,
    unavailable_snapshot,
)


PRODUCT_CODE = "HBM-ACCELERATOR-PACKAGE-BOARD"
PRODUCT_VERSION = "hbm-pkg-r1"
INTERNAL_START = "/mock_db_mvp/internal/assembly/start"
INTERNAL_FEEDBACK = "/mock_db_mvp/internal/assembly/feedback"
EXTERNAL_START = "/unity/assembly/start"
EXTERNAL_FEEDBACK = "/unity/assembly/feedback"


class AssemblySequencer(Node):
    def __init__(self):
        super().__init__("assembly_sequencer")
        self.runtime_mode = os.environ.get("ASSEMBLY_SEQUENCER_MODE", "mock")
        expected_domain = {"mock": 42, "real": 5}.get(self.runtime_mode)
        if expected_domain is None or self.context.get_domain_id() != expected_domain:
            raise RuntimeError("MODE_REJECTED stage=startup: runtime mode and ROS domain disagree")
        self.recipe = None
        self.recipe_version = None
        self.recipe_slots = []
        if self.runtime_mode == "mock":
            recipe_path = self.declare_parameter("recipe", "").value
            self.recipe = load_recipe(recipe_path)
            self.recipe_version = self.recipe["recipe_version"]
            self.recipe_slots = [(step["slot_code"], step["part_id"]) for step in self.recipe["steps"]]
            self_check(self.recipe)

        service_group = MutuallyExclusiveCallbackGroup()
        if self.runtime_mode == "mock":
            internal_client = self.create_client(
                RemoteCmdInterface, INTERNAL_START, callback_group=ReentrantCallbackGroup()
            )
            self.backend = MockBackend(self, internal_client)
            self.backend.configure_inspection(
                self.declare_parameter("inspection_fail_probability", 0.2).value,
                self.declare_parameter("random_seed", -1).value,
            )
            self.internal_subscription = self.create_subscription(
                String, INTERNAL_FEEDBACK, self.on_internal_feedback, 10,
                callback_group=MutuallyExclusiveCallbackGroup(),
            )
        else:
            self.backend = RealBackend(self)

        self.db_writer = DbWriter()
        try:
            recovered = self.db_writer.recover_interrupted()
            if recovered:
                self.get_logger().warning(
                    f"failed {recovered} interrupted Unit attempt(s)"
                )
        except Exception:
            self.db_writer.close(0.1)
            raise

        self.active = None
        self.pending_requests = {}
        self.terminal_snapshot = None
        self.external_service = self.create_service(
            RemoteCmdInterface,
            EXTERNAL_START,
            self.on_external_request,
            callback_group=service_group,
        )
        self.create_timer(
            0.5, self.on_pending_job, callback_group=service_group
        )
        self.external_publisher = self.create_publisher(
            String, EXTERNAL_FEEDBACK, 10
        )

    @staticmethod
    def set_response(response, accepted, job_id="", error_code="", message=""):
        response.cmd_res = json.dumps({
            "accepted": accepted,
            "job_id": job_id,
            "error_code": error_code,
            "message": message[:512],
        }, separators=(",", ":"))
        return response

    async def on_external_request(self, request, response):
        if request.cmd_str != '{"command":"status"}':
            prefix = self.runtime_mode + "\n"
            if not request.cmd_str.startswith(prefix):
                self.get_logger().error("MODE_REJECTED stage=assembly_request result=blocked_before_execution")
                return self.set_response(response, False, error_code="MODE_MISMATCH",
                                         message=f"{self.runtime_mode} mode prefix is required")
            request.cmd_str = request.cmd_str[len(prefix):]
        command = None
        try:
            command_type, command = parse_command(
                request.cmd_str, self.recipe_version, self.runtime_mode
            )
            if command_type == "observations":
                command["resolved_steps"] = resolve_observations(
                    self.recipe, command["observations"]
                )
        except ValueError as error:
            return self.set_response(
                response, False,
                job_id=command["job_id"] if command else "",
                error_code="INVALID_REQUEST", message=str(error)
            )

        # While active, status uses only feedback already committed by this bridge.
        if command_type == "status":
            if self.terminal_snapshot is not None:
                snapshot = self.sync_snapshot(self.terminal_snapshot)
            elif self.active is not None:
                snapshot = assembly_snapshot(
                    self.active,
                    self.active["state"],
                    db_sync_state=self.db_writer.sync_state,
                )
            else:
                try:
                    snapshot = await self.backend.status()
                    snapshot["placed_slot_codes"] = (
                        [step["slot_code"] for step in self.recipe["steps"]]
                        [:snapshot["placed_count"]]
                        if self.runtime_mode == "mock" and snapshot.get("recipe_version") == self.recipe_version else []
                    )
                    snapshot["db_sync_state"] = self.db_writer.sync_state
                except Exception as error:
                    snapshot = unavailable_snapshot(str(error))
            snapshot["runtime_mode"] = self.runtime_mode
            response.cmd_res = json.dumps(snapshot, separators=(",", ":"))
            return response

        if command_type in {"conveyor_arrived", "conveyor_failed", "transfer_assembled_pcb"}:
            active = self.active
            if (active is None or command["job_id"] != active["job_id"]
                    or command["unit_id"] != active["unit_id"]
                    or command["operation_id"] != active.get("conveyor_operation_id")):
                return self.set_response(response, False, command["job_id"], "NOT_ACTIVE",
                                         "matching Unit conveyor movement is not active")

        if command_type == "conveyor_arrived":
            return await self.conveyor_arrived(command, response)

        if command_type == "conveyor_failed":
            return self.conveyor_failed(command, response)

        if command_type in {"pause", "resume"}:
            job_id = command["job_id"]
            if self.active is None or self.active["job_id"] != job_id:
                return self.set_response(
                    response, False, job_id, "NOT_ACTIVE",
                    "matching assembly is not active",
                )
            if self.active.get("inspection_hold"):
                return self.set_response(response, False, job_id, "BUSY", "inspection resolution is required")
            if self.runtime_mode == "real":
                return self.set_response(response, False, job_id, "NOT_READY", RealBackend._connection_error())
            try:
                await self.backend.set_paused(job_id, command_type == "pause")
            except Exception as error:
                return self.set_response(
                    response, False, job_id, "INTERNAL_ERROR", str(error)
                )
            return self.set_response(response, True, job_id)

        if command_type == "transfer_assembled_pcb":
            active = self.active
            job_id = command["job_id"]
            if active is None or active["job_id"] != job_id:
                return self.set_response(
                    response, False, job_id, "NOT_ACTIVE",
                    "matching assembly is not active",
                )
            if active["transfer_requested"]:
                return self.set_response(response, True, job_id)
            if active["state"] != "ASSEMBLY_COMPLETED":
                return self.set_response(
                    response, False, job_id, "BUSY",
                    "assembly is not ready for inspection and PCB transfer",
                )

            try:
                self.backend.confirm_conveyor(
                    job_id, "INSPECTION", unit_id=command["unit_id"],
                    operation_id=command["operation_id"], assembled_pcb=command["assembled_pcb"])
            except Exception as error:
                return self.set_response(response, False, job_id, "BUSY", str(error))
            active["transfer_requested"] = True
            return self.set_response(response, True, job_id)

        job_id = command["job_id"]
        if command_type == "start":
            return self.set_response(response, False, job_id, "NOT_READY", RealBackend._connection_error())
        try:
            job = self.db_writer.get_job(job_id)
        except Exception as error:
            return self.set_response(
                response, False, job_id, "DB_ERROR", str(error)
            )
        if job["job_status"] not in {"PENDING", "RUNNING"}:
            return self.set_response(
                response, False, job_id, "NOT_ACTIVE", "Job is already finalized"
            )
        if self.active is None or self.active["job_id"] != job_id:
            self.pending_requests[job_id] = command
        return self.set_response(response, True, job_id)

    async def conveyor_arrived(self, command, response):
        active = self.active
        job_id = command["job_id"]
        if active is None or active["job_id"] != job_id:
            return self.set_response(
                response, False, job_id, "NOT_ACTIVE",
                "matching assembly is not active",
            )
        if active["state"] != "CONVEYOR_MOVING":
            return self.set_response(
                response, False, job_id, "BUSY",
                "conveyor arrival is not expected",
            )
        if active["conveyor_confirmed"]:
            return self.set_response(response, True, job_id)

        try:
            self.backend.confirm_conveyor(
                job_id, "ASSEMBLY", unit_id=command["unit_id"], operation_id=command["operation_id"])
        except Exception as error:
            return self.set_response(response, False, job_id, "BUSY", str(error))
        active["conveyor_confirmed"] = True
        return self.set_response(response, True, job_id)

    def conveyor_failed(self, command, response):
        active = self.active
        job_id = command["job_id"]
        if active is None or active["job_id"] != job_id:
            return self.set_response(
                response, False, job_id, "NOT_ACTIVE",
                "matching assembly is not active",
            )
        if active["state"] not in {"CONVEYOR_MOVING", "ASSEMBLY_COMPLETED"}:
            return self.set_response(
                response, False, job_id, "BUSY", "conveyor movement is not expected"
            )

        try:
            self.backend.fail_conveyor(job_id, command["message"],
                                       unit_id=command["unit_id"], operation_id=command["operation_id"])
        except Exception as error:
            return self.set_response(response, False, job_id, "BUSY", str(error))
        return self.set_response(response, True, job_id)

    async def on_pending_job(self):
        if self.runtime_mode == "real":
            return
        if self.active is not None or self.db_writer.sync_state in {"PENDING", "FAILED"}:
            return
        try:
            pending = self.db_writer.get_next_runnable_job(
                PRODUCT_CODE, PRODUCT_VERSION, self.recipe_version,
                ready_job_ids=list(self.pending_requests),
            )
        except Exception as error:
            self.get_logger().error(f"failed to read pending Job: {error}")
            return
        if pending is None or not self.backend.is_available():
            return
        job_id = pending["job_id"]
        command = self.pending_requests.get(job_id)
        if command is None:
            return
        result = await self.start_job(command, RemoteCmdInterface.Response())
        outcome = json.loads(result.cmd_res)
        self.pending_requests.pop(job_id, None)
        if outcome["accepted"]:
            return
        if outcome["error_code"] == "NOT_READY":
            # Equipment readiness failure does not turn a queued request into a
            # failed production attempt. A fresh start request is required.
            self.publish(failed_feedback(job_id, "NOT_READY", outcome["message"], self.db_writer.sync_state))
            return
        try:
            self.db_writer.abort(job_id)
        except Exception as error:
            outcome["error_code"] = "DB_ERROR"
            outcome["message"] = f"{outcome['message']}; cleanup failed: {error}"
        self.publish(failed_feedback(
            job_id, outcome["error_code"], outcome["message"],
            self.db_writer.sync_state,
        ))

    async def start_job(self, command, response):
        job_id = command["job_id"]
        if self.runtime_mode == "real":
            return self.set_response(response, False, job_id, "NOT_READY", RealBackend._connection_error())
        if self.active is not None:
            if self.active["job_id"] == job_id:
                return self.set_response(response, True, job_id)
            return self.set_response(
                response, False, job_id, "BUSY", "another Job is active"
            )

        try:
            await self.backend.prepare(self.recipe["joint_points"], self.recipe["frame"])
        except Exception as error:
            return self.set_response(response, False, job_id, "NOT_READY", str(error))
        try:
            product_slots = self.db_writer.get_product_slots(job_id)
            db_slots = {
                (slot["slot_code"], slot["part_id"])
                for slot in product_slots
            }
            if db_slots != set(self.recipe_slots):
                raise RuntimeError(
                    "database product slots do not match the loaded recipe"
                )
            work = self.db_writer.claim(
                job_id, PRODUCT_CODE, PRODUCT_VERSION, self.recipe_version
            )
            self.active = {
                "job_id": work["job_id"],
                "unit_id": work["unit_id"],
                "recipe_version": self.recipe_version,
                "resolved_steps": command.get("resolved_steps", []),
                "observations": command.get("observations", []),
                "before_action_index": 0,
                "after_action_index": 0,
                "backend_started": False,
                "conveyor_confirmed": False,
                "state": "STARTED",
                "placed_count": 0,
                "expected_step_count": len(self.recipe["steps"]),
                "held_step_order": 0,
                "held_part_id": "",
                "held_slot_code": "",
                "slot_codes": [slot_code for slot_code, _ in self.recipe_slots],
                "transfer_requested": False,
                "inspection_result": "",
            }
            self.terminal_snapshot = None
            self.executor.create_task(self.run_assembly_workflow(self.active))
            return self.set_response(response, True, job_id)
        except Exception as error:
            if self.active is not None:
                self.fail_active("INTERNAL_ERROR", error, immediate=True)
            return self.set_response(
                response, False, job_id, "INTERNAL_ERROR", str(error)
            )

    async def run_assembly_workflow(self, active):
        if self.runtime_mode != "mock":
            raise RuntimeError("NOT_READY: YAML execution is Mock-only")
        if self.active is not active:
            return
        error_code = "INTERNAL_ERROR"
        try:
            before_all = self.recipe["workflow"]["before_all"]
            while active["before_action_index"] < len(before_all):
                if self.active is not active:
                    return
                command = before_all[active["before_action_index"]]
                active["before_action_index"] += 1
                action, argument = next(iter(command.items()))
                if (action, argument) == ("conveyor.move_to", "ASSEMBLY"):
                    active["conveyor_confirmed"] = False
                    active["state"] = "CONVEYOR_MOVING"
                    active["conveyor_operation_id"] = str(uuid.uuid4())
                    error_code = "CONVEYOR_FAILED"
                    await self.backend.move_conveyor(
                        active["job_id"], "ASSEMBLY", unit_id=active["unit_id"],
                        operation_id=active["conveyor_operation_id"],
                        on_ready=lambda: self.publish({
                            "job_id": active["job_id"],
                            "state": "CONVEYOR_MOVING",
                            "step_order": 0,
                            "part_id": "",
                            "slot_code": "",
                            "error_code": "",
                            "message": "",
                            "db_sync_state": self.db_writer.sync_state,
                        }))
                    error_code = "INTERNAL_ERROR"
                    continue
                if (action, argument) == ("vision.resolve_targets", "recipe_steps"):
                    observations = await self.backend.resolve_targets(active["observations"])
                    active["resolved_steps"] = resolve_observations(self.recipe, observations)
                    continue
                raise RuntimeError(f"unknown preflight action: {command}")

            if self.active is not active:
                return
            await self.backend.start(
                active["job_id"], self.recipe_version,
                active["expected_step_count"],
            )
            active["backend_started"] = True
            active["state"] = "STARTED"
            self.publish({
                "job_id": active["job_id"],
                "state": "STARTED",
                "step_order": 0,
                "part_id": "",
                "slot_code": "",
                "error_code": "",
                "message": "",
                "db_sync_state": self.db_writer.sync_state,
            })

            motion = self.recipe["motion"]
            frame = self.recipe["frame"]
            joint_points = self.recipe["joint_points"]
            for resolved in active["resolved_steps"]:
                step = resolved["step"]
                gripper = {
                    "grasp_opening_percent": resolved[
                        "gripper_grasp_opening_percent"
                    ],
                    "release_opening_percent": resolved[
                        "gripper_release_opening_percent"
                    ],
                }
                for command in self.recipe["workflow"]["per_step"]:
                    if self.active is not active:
                        return
                    action, argument = next(iter(command.items()))
                    if action == "robot.move_joint":
                        await self.backend.move_joint(
                            active["job_id"], joint_points[argument]
                        )
                    elif (action, argument) == ("robot.pick", "current_part"):
                        await self.backend.pick(
                            active["job_id"], step, frame, resolved["source"],
                            motion, gripper,
                        )
                    elif (action, argument) == ("robot.place", "current_slot"):
                        await self.backend.place(
                            active["job_id"], step, frame, resolved["target"],
                            motion, gripper,
                        )
                    else:
                        raise RuntimeError(f"unknown assembly action: {command}")

            if self.active is not active:
                return
            await self.run_transfer_workflow(active)
        except Exception as error:
            if self.active is active:
                self.fail_active(
                    "INVALID_RECIPE" if isinstance(error, ValueError)
                    else error_code,
                    error,
                    immediate=not active["backend_started"],
                )

    async def run_transfer_workflow(self, active):
        if self.runtime_mode != "mock":
            raise RuntimeError("NOT_READY: YAML execution is Mock-only")
        if self.active is not active:
            return
        error_code = "INTERNAL_ERROR"
        try:
            after_all = self.recipe["workflow"]["after_all"]
            while active["after_action_index"] < len(after_all):
                if self.active is not active:
                    return
                command = after_all[active["after_action_index"]]
                active["after_action_index"] += 1
                action, argument = next(iter(command.items()))
                if (action, argument) == ("conveyor.move_to", "INSPECTION"):
                    active["state"] = "ASSEMBLY_COMPLETED"
                    active["conveyor_operation_id"] = str(uuid.uuid4())
                    error_code = "CONVEYOR_FAILED"
                    await self.backend.move_conveyor(
                        active["job_id"], "INSPECTION", unit_id=active["unit_id"],
                        operation_id=active["conveyor_operation_id"],
                        on_ready=lambda: self.publish({
                            "job_id": active["job_id"],
                            "state": "ASSEMBLY_COMPLETED",
                            "step_order": 0,
                            "part_id": "",
                            "slot_code": "",
                            "error_code": "",
                            "message": "",
                            "db_sync_state": self.db_writer.sync_state,
                        }))
                    error_code = "INTERNAL_ERROR"
                    continue
                if (action, argument) == ("inspection.run", "assembled_pcb"):
                    inspection = await self.backend.inspect_unit(
                        active["job_id"], active["unit_id"], active["slot_codes"]
                    )
                    error_code = "DB_ERROR"
                    self.db_writer.assembly_completed(active["unit_id"])
                    self.db_writer.inspection_recorded(active["unit_id"], **inspection)
                    active["inspection_result"] = inspection["result"]
                    # Do not move equipment past an unconfirmed production write.
                    self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
                    if active["inspection_result"] == "UNKNOWN":
                        # Uncertain inspection is not a failed execution or PASS.
                        # Preserve this Unit without moving the board or starting another.
                        active["state"] = "PAUSED"
                        active["inspection_hold"] = True
                        self.publish(failed_feedback(active["job_id"], "INSPECTION_UNKNOWN",
                                     "inspection requires an explicit resolution", self.db_writer.sync_state)
                                     | {"state": "PAUSED"})
                        return
                    error_code = "INTERNAL_ERROR"
                    continue
                if (action, argument) == ("robot.transfer", "assembled_pcb"):
                    assembled_pcb = active.get("assembled_pcb")
                    await self.backend.transfer_assembled_pcb(
                        active["job_id"], self.recipe["frame"],
                        assembled_pcb, self.recipe["motion"],
                        self.recipe["gripper"]["assembled_pcb"],
                    )
                    continue
                raise RuntimeError(f"unknown final assembly action: {command}")

            error_code = "DB_ERROR"
            self.finish_active_unit(active)
        except Exception as error:
            if self.active is active:
                self.fail_active(error_code, error)

    def finish_active_unit(self, active):
        self.db_writer.unit_completed(active["unit_id"])
        self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
        state = self.db_writer.get_job(active["job_id"])
        if state["completed_quantity"] < state["requested_quantity"]:
            work = self.db_writer.claim(
                active["job_id"], PRODUCT_CODE, PRODUCT_VERSION,
                self.recipe_version,
            )
            active.update({
                "unit_id": work["unit_id"],
                "before_action_index": 0,
                "after_action_index": 0,
                "backend_started": False,
                "conveyor_confirmed": False,
                "state": "STARTED",
                "placed_count": 0,
                "held_step_order": 0,
                "held_part_id": "",
                "held_slot_code": "",
                "transfer_requested": False,
                "inspection_result": "",
            })
            active.pop("assembled_pcb", None)
            self.executor.create_task(self.run_assembly_workflow(active))
            return

        self.db_writer.finish(active["job_id"], "COMPLETED")
        self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
        payload = {
            "job_id": active["job_id"],
            "state": "COMPLETED",
            "step_order": 0,
            "part_id": "",
            "slot_code": "",
            "error_code": "",
            "message": "",
            "db_sync_state": self.db_writer.sync_state,
        }
        self.terminal_snapshot = assembly_snapshot(
            active, "COMPLETED", db_sync_state=self.db_writer.sync_state
        )
        self.active = None
        self.publish(payload)
        self.get_logger().info(
            f"job {active['job_id']} completed with inspection "
            f"{active['inspection_result']}"
        )

    def fail_job(self, job_id, immediate=False):
        try:
            if self.db_writer.sync_state == "FAILED":
                raise RuntimeError(
                    "DB finalization is unconfirmed; restart recovery required: "
                    + self.db_writer.last_error
                )
            if immediate:
                self.db_writer.abort(job_id)
            else:
                self.db_writer.finish(job_id, "FAILED")
                self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
        except Exception as error:
            self.get_logger().error(f"failed to finalize job {job_id}: {error}")
            return error
        return None

    def fail_active(self, error_code, error, immediate=False):
        active = self.active
        if self.runtime_mode == "real" and str(error).startswith("SAFETY_STOP:"):
            # Unknown physical completion must not finalize the Unit or advance
            # the recipe. Recovery starts a new Unit after equipment reset.
            active["state"] = "PAUSED"
            self.publish(failed_feedback(active["job_id"], "SAFETY_STOP", str(error),
                                         self.db_writer.sync_state) | {"state": "PAUSED"})
            return
        cleanup_error = self.fail_job(active["job_id"], immediate)
        if cleanup_error is not None:
            error_code = "DB_ERROR"
            error = RuntimeError(f"{error}; cleanup failed: {cleanup_error}")
        failed = failed_feedback(
            active["job_id"],
            error_code,
            str(error),
            self.db_writer.sync_state,
        )
        self.terminal_snapshot = assembly_snapshot(
            active,
            "FAILED",
            failed["error_code"],
            failed["message"],
            self.db_writer.sync_state,
        )
        self.active = None
        self.publish(failed)
        self.get_logger().error(
            f"job {active['job_id']} failed: {failed['message']}"
        )

    def sync_snapshot(self, snapshot):
        snapshot = dict(snapshot)
        snapshot["db_sync_state"] = self.db_writer.sync_state
        if self.db_writer.sync_state == "FAILED":
            snapshot["error_code"] = "DB_SYNC_FAILED"
            snapshot["message"] = self.db_writer.last_error[:512]
        return snapshot

    def publish(self, payload):
        # Unit identity belongs to the Sequencer, including relayed backend events.
        # Terminal publication happens after self.active has been cleared.
        state = self.active or self.terminal_snapshot
        unit_id = (state["unit_id"] if state is not None
                   and state["job_id"] == payload["job_id"] else 0)
        payload = dict(payload, unit_id=unit_id)
        if state is not None and payload["state"] in {"CONVEYOR_MOVING", "ASSEMBLY_COMPLETED"}:
            payload["operation_id"] = state.get("conveyor_operation_id", "")
        self.external_publisher.publish(
            String(data=json.dumps(payload, separators=(",", ":")))
        )

    async def on_internal_feedback(self, message):
        if self.runtime_mode != "mock":
            return
        try:
            payload = parse_feedback(message.data)
        except ValueError as error:
            self.get_logger().error(f"invalid internal assembly feedback: {error}")
            return

        active = self.active
        job_id = payload["job_id"]
        if active is None or job_id != active["job_id"]:
            self.get_logger().warning(
                f"ignored feedback without matching active Job: {job_id}"
            )
            return

        if self.backend.accept_operation_feedback(payload):
            return

        state = payload["state"]
        if state in RELAY_STATES and state != "ASSEMBLY_COMPLETED":
            apply_relay_feedback(active, payload)
            payload["db_sync_state"] = self.db_writer.sync_state
            self.publish(payload)
            return

        if state == "FAILED":
            self.fail_active(
                payload["error_code"] or "INTERNAL_ERROR",
                payload["message"] or "internal Mock assembly failed",
            )
            return

        self.fail_active(
            "INTERNAL_ERROR",
            "backend reported completion without a matching operation",
        )

    def destroy_node(self):
        self.backend.close()
        if not self.db_writer.close():
            self.get_logger().error(self.db_writer.last_error)
        return super().destroy_node()


def main(args=None):
    command_line = sys.argv[1:] if args is None else args
    if command_line == ["--self-check"]:
        self_check()
        print("assembly_sequencer recipe self-check passed")
        return
    mode = os.environ.get("ASSEMBLY_SEQUENCER_MODE", "mock")
    expected_domain = {"mock": "42", "real": "5"}.get(mode)
    if expected_domain is None or os.environ.get("ROS_DOMAIN_ID") != expected_domain:
        raise SystemExit("MODE_REJECTED stage=startup: mode/domain mismatch; DB recovery not started")
    rclpy.init(args=args)
    node = AssemblySequencer()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
