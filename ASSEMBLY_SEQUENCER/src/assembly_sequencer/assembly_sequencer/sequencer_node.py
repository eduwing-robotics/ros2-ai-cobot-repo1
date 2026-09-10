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
    validate_scene_confirmation,
    PRODUCTION_SLOTS, PRODUCTION_RECIPE_VERSION,
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
        self.recipe_version = PRODUCTION_RECIPE_VERSION if self.runtime_mode == "real" else None
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

        if command_type in {"status", "resume", "cancel"} and self.active is None:
            try:
                hold = self.db_writer.get_quality_hold()
                if isinstance(hold, dict):
                    slots = [slot for slot, _ in PRODUCTION_SLOTS] if self.runtime_mode == "real" else [step["slot_code"] for step in self.recipe["steps"]]
                    self.active = dict(hold, state="PAUSED", quality_hold=True,
                        inspection_result="FAIL", awaiting_next_unit=True, backend_started=False,
                        placed_count=len(slots), expected_step_count=len(slots), slot_codes=slots,
                        held_step_order=0, held_part_id="", held_slot_code="",
                        error_code="QUALITY_HOLD", message="검사 결과 · FAIL · 생산 일시정지 · 재개 또는 취소를 선택하세요.")
                    self.terminal_snapshot = None
            except Exception as error:
                return self.set_response(response, False, "", "DB_ERROR", str(error))

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

        if command_type in {"pause", "resume", "cancel"}:
            job_id = command["job_id"]
            terminal = (self.terminal_snapshot or {}) if command_type == "cancel" and self.active is None else {}
            if (command_type == "cancel" and self.active is None and terminal.get("job_id") == job_id and
                    terminal.get("error_code") == "EXECUTION_CANCELLED" and terminal.get("db_sync_state") == "SYNCED"):
                return self.set_response(response, True, job_id)
            if self.active is None or self.active["job_id"] != job_id:
                return self.set_response(
                    response, False, job_id, "NOT_ACTIVE",
                    "matching assembly is not active",
                )
            if self.active.get("quality_hold"):
                active = self.active
                try:
                    if command_type == "pause":
                        return self.set_response(response, True, job_id)
                    if command_type == "cancel":
                        self.db_writer.finish(job_id, "CANCELLED")
                        self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
                        self.terminal_snapshot = assembly_snapshot(active, "FAILED",
                            error_code="EXECUTION_CANCELLED", message="불량 확인 후 생산 취소",
                            db_sync_state=self.db_writer.sync_state)
                        self.active = None
                    else:
                        if self.runtime_mode == "real":
                            await self.backend.prepare_execution(active["recipe_version"])
                        elif not self.backend.is_available():
                            raise RuntimeError("Equipment is not ready")
                        elif not active.get("resolved_steps"):
                            observed = self.pending_requests.get(job_id, {})
                            if not observed.get("resolved_steps"):
                                raise RuntimeError("재시작 후 새 Mock 현장 관측을 등록하세요.")
                            active.update(resolved_steps=observed["resolved_steps"], observations=observed["observations"])
                        self.db_writer.resume_quality(job_id)
                        active.update(quality_hold=False, quality_resumed=True, error_code="", message="")
                        self.finish_active_unit(active)
                except Exception as error:
                    return self.set_response(response, False, job_id, "CONTROL_REJECTED", str(error))
                return self.set_response(response, True, job_id)
            if self.active.get("awaiting_next_unit"):
                return self.set_response(response, False, job_id, "NOT_READY", "새 현장 확인으로 다음 Unit을 시작하세요.")
            if self.active.get("inspection_hold"):
                return self.set_response(response, False, job_id, "BUSY", "inspection resolution is required")
            if self.runtime_mode == "real":
                if (command_type == "cancel" and not self.active.get("backend_started") and
                        self.active["state"] == "PAUSED"):
                    active = self.active
                    if active.get("control_pending"):
                        return self.set_response(response, True, job_id)
                    active.update(control_pending=True, error_code="", message="컨베이어 정지 확인 후 취소 처리 중")
                    self.executor.create_task(self.cancel_before_assembly(active))
                    return self.set_response(response, True, job_id)
                if not self.active.get("backend_started") or self.active["state"] not in {"STARTED", "PLACED", "PAUSED"}:
                    return self.set_response(response, False, job_id, "BUSY", "Control is available during robot assembly only")
                try:
                    await self.backend.request_control(self.active["execution_id"], command_type)
                except Exception as error:
                    return self.set_response(response, False, job_id, "CONTROL_REJECTED", str(error))
                self.active["control_pending"] = True
                self.active["message"] = command_type + " 요청 · 실제 상태 확인 중"
                return self.set_response(response, True, job_id)
            if command_type == "cancel":
                return self.set_response(response, False, job_id, "NOT_READY", "Mock cancel is unsupported")
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
        if command_type == "start" and self.runtime_mode == "real":
            return await self.start_real_job(command, response)
        try:
            job = self.db_writer.get_job(job_id)
        except Exception as error:
            return self.set_response(
                response, False, job_id, "DB_ERROR", str(error)
            )
        if job["job_status"] not in {"PENDING", "RUNNING", "PAUSED"}:
            return self.set_response(
                response, False, job_id, "NOT_ACTIVE", "Job is already finalized"
            )
        if job["job_status"] == "PAUSED" or self.active is None or self.active["job_id"] != job_id:
            self.pending_requests[job_id] = command
        return self.set_response(response, True, job_id)

    async def start_real_job(self, command, response):
        job_id = command["job_id"]
        try:
            validate_scene_confirmation(command.get("scene_confirmation"))
            if command["recipe_version"] != PRODUCTION_RECIPE_VERSION:
                raise ValueError("No production recipe binding for this request.")
        except ValueError as error:
            return self.set_response(response, False, job_id, "NOT_READY", str(error))
        previous = self.active
        confirmation = command["scene_confirmation"]
        execution_id = str(uuid.UUID(confirmation["execution_id"]))
        if previous is not None:
            if previous["job_id"] != job_id:
                return self.set_response(response, False, job_id, "BUSY", "Another Job is active.")
            if previous.get("quality_hold"):
                return self.set_response(response, False, job_id, "QUALITY_HOLD", "불량 확인 후 재개를 선택하세요.")
            if not previous.get("awaiting_next_unit"):
                if previous.get("execution_id") == execution_id:
                    return self.set_response(response, True, job_id)
                return self.set_response(response, False, job_id, "BUSY", "Current Unit must finish or recover before a new execution.")
            if previous.get("execution_id") == execution_id:
                return self.set_response(response, False, job_id, "NOT_READY", "The next Unit needs a new execution and scene confirmation.")
        try:
            revision = await self.backend.prepare_execution(command["recipe_version"])
        except Exception as error:
            return self.set_response(response, False, job_id, "NOT_READY", str(error))
        try:
            job = self.db_writer.get_job(job_id)
            if job["job_status"] not in {"PENDING", "RUNNING"}:
                return self.set_response(response, False, job_id, "NOT_ACTIVE", "Job is already finalized.")
            slots = self.db_writer.get_product_slots(job_id)
            if len(slots) != len(PRODUCTION_SLOTS) or {(s["slot_code"], s["part_id"]) for s in slots} != set(PRODUCTION_SLOTS):
                raise ValueError("Product slots do not match the production recipe binding.")
            validate_scene_confirmation(confirmation)
            work = self.db_writer.claim(job_id, PRODUCT_CODE, PRODUCT_VERSION, PRODUCTION_RECIPE_VERSION)
        except Exception as error:
            return self.set_response(response, False, job_id, "DB_ERROR", str(error))
        self.active = dict(job_id=job_id, unit_id=work["unit_id"], recipe_version=PRODUCTION_RECIPE_VERSION,
            execution_id=execution_id, robot_recipe_revision=revision, scene_confirmation=dict(confirmation),
            state="STARTED", placed_count=0, placed_slot_codes=[], expected_step_count=len(PRODUCTION_SLOTS),
            slot_codes=[s for s, _ in PRODUCTION_SLOTS], held_step_order=0, held_part_id="", held_slot_code="",
            backend_started=False, inspection_result="", error_code="", message="")
        self.terminal_snapshot = None
        self.executor.create_task(self.run_real_workflow(self.active))
        return self.set_response(response, True, job_id)

    def real_progress(self, active, data):
        if self.active is not active:
            return
        for key, expected in (("execution_id", active["execution_id"]), ("production_job_id", active["job_id"]),
                              ("unit_id", active["unit_id"])):
            if data.get(key) != expected:
                raise ValueError("Robot progress identity mismatch: " + key)
        completed = data.get("completed_slots", [])
        if (not isinstance(completed, list) or any(not isinstance(s, str) for s in completed) or
                len(set(completed)) != len(completed) or not set(completed).issubset(active["slot_codes"])):
            raise ValueError("Robot progress contains invalid completed slots.")
        if not set(active["placed_slot_codes"]).issubset(completed):
            return
        message = str(data.get("current_stage") or "Robot assembly running")
        # Display context is separate from held-part state and never acknowledges a motion.
        detail = {key: "" for key in ("current_part_id", "current_slot_code", "current_action", "current_phase", "current_event")}
        context = data.get("last_robot_event")
        if isinstance(context, dict):
            original, metadata = context.get("original"), context.get("metadata")
            if isinstance(original, dict) and isinstance(metadata, dict):
                identity = (metadata.get("server_instance_id"), metadata.get("event_sequence"),
                            original.get("operation_id"), original.get("phase"), original.get("event"))
                # Repeated snapshots can retain an event from the previous top-level stage.
                if identity != active.get("last_display_event"):
                    active["last_display_event"] = identity
                    slot, part = metadata.get("slot_code"), metadata.get("part_id")
                    if (message in {"assemble_non-smd", "assemble_smd"} and
                            original.get("job_id") == active["execution_id"] and
                            isinstance(slot, str) and isinstance(part, str) and
                            (slot, part) in PRODUCTION_SLOTS and slot in active["slot_codes"] and
                            all(isinstance(original.get(k), str) for k in ("action", "phase", "event"))):
                        detail.update(current_part_id=part, current_slot_code=slot,
                                      current_action=original["action"], current_phase=original["phase"],
                                      current_event=original["event"])
                elif message == active.get("message"):
                    detail = {key: active.get(key, "") for key in detail}
        changed = (completed != active["placed_slot_codes"] or message != active.get("message") or
                   any(value != active.get(key, "") for key, value in detail.items()))
        active.update(detail)
        active["placed_slot_codes"] = list(completed)
        active["placed_count"] = len(completed)
        paused = data.get("status") == "paused" and data.get("stop_verified") is True
        active["control_pending"] = bool(data.get("control_pending") or data.get("control_error"))
        changed = changed or paused != (active["state"] == "PAUSED")
        active["state"] = "PAUSED" if paused else ("PLACED" if completed else "STARTED")
        active["error_code"] = "CONTROL_UNCONFIRMED" if data.get("control_error") else ""
        if data.get("control_error"):
            message = data["control_error"]
        elif data.get("control_pending"):
            message = data["control_pending"] + " 요청 · 현재 동작 종료 및 상태 확인 대기"
        elif paused:
            message = "일시정지 확인 · 같은 실행에서 재개 가능"
        active["message"] = message
        if changed:
            self.publish(dict(job_id=active["job_id"], state=active["state"], step_order=len(completed),
                part_id=completed[-1].split("-")[0] if completed else "",
                slot_code=completed[-1] if completed else "", error_code="",
                message=active["message"], db_sync_state=self.db_writer.sync_state))

    async def cancel_before_assembly(self, active):
        try:
            await self.backend.confirm_conveyor_stopped()
            if self.active is not active:
                return
            self.db_writer.finish(active["job_id"], "CANCELLED")
            self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
            active["control_pending"] = False
            self.terminal_snapshot = assembly_snapshot(active, "FAILED", "EXECUTION_CANCELLED",
                "조립 전 컨베이어 정지 확인 · 작업 취소 완료", self.db_writer.sync_state)
            self.active = None
            self.publish(failed_feedback(active["job_id"], "EXECUTION_CANCELLED",
                "조립 전 컨베이어 정지 확인 · 작업 취소 완료", self.db_writer.sync_state))
        except Exception as error:
            if self.active is active:
                active.update(control_pending=False, state="PAUSED", error_code="CONTROL_UNCONFIRMED",
                    message="취소 미확인: " + str(error))
                self.publish(failed_feedback(active["job_id"], active["error_code"], active["message"],
                    self.db_writer.sync_state) | {"state": "PAUSED"})

    async def run_real_workflow(self, active):
        stage = "CONVEYOR_FAILED"
        try:
            active.update(state="CONVEYOR_MOVING", conveyor_operation_id=str(uuid.uuid4()), message="조립 위치 이동 중")
            self.publish(dict(job_id=active["job_id"], state=active["state"], step_order=0,
                part_id="", slot_code="", error_code="", message=active["message"], db_sync_state=self.db_writer.sync_state))
            await self.backend.move_conveyor("ASSEMBLY")
            stage = "ASSEMBLY_FAILED"
            active.update(state="STARTED", backend_started=True, message="전체 조립 실행 중")
            self.publish(dict(job_id=active["job_id"], state=active["state"], step_order=0,
                part_id="", slot_code="", error_code="", message=active["message"], db_sync_state=self.db_writer.sync_state))
            await self.backend.execute_assembly(active["job_id"], active["unit_id"], active["recipe_version"],
                active["robot_recipe_revision"], active["scene_confirmation"], active["slot_codes"],
                lambda data: self.real_progress(active, data))
            stage = "DB_ERROR"
            self.db_writer.assembly_completed(active["unit_id"])
            self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
            stage = "CONVEYOR_FAILED"
            active.update(state="ASSEMBLY_COMPLETED", conveyor_operation_id=str(uuid.uuid4()), message="검사 위치 이동 중")
            self.publish(dict(job_id=active["job_id"], state=active["state"], step_order=0,
                part_id="", slot_code="", error_code="", message=active["message"], db_sync_state=self.db_writer.sync_state))
            await self.backend.move_conveyor("INSPECTION")
            stage = "INSPECTION_FAILED"
            active["message"] = "검사 진행 중"
            # Real consumes this notification by re-reading status; it never drives a conveyor from feedback.
            self.publish(dict(job_id=active["job_id"], state=active["state"], step_order=0,
                part_id="", slot_code="", error_code="", message=active["message"], db_sync_state=self.db_writer.sync_state))
            inspection = await self.backend.inspect_unit(active["job_id"], active["unit_id"], active["slot_codes"])
            stage = "DB_ERROR"
            self.db_writer.inspection_recorded(active["unit_id"], **inspection)
            self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
            active["inspection_result"] = inspection["result"]
            active["message"] = "검사 결과 · " + inspection["result"]
            if inspection["result"] == "UNKNOWN":
                active.update(state="PAUSED", inspection_hold=True, error_code="INSPECTION_UNKNOWN",
                              message="검사 완료 · 판정 보류. 결과 자료를 확인하세요.")
                self.publish(failed_feedback(active["job_id"], active["error_code"], active["message"],
                                             self.db_writer.sync_state) | {"state": "PAUSED"})
                return
            self.finish_active_unit(active)
        except Exception as error:
            if self.active is active:
                self.fail_active(getattr(error, "error_code", stage), error)

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
            return await self.start_real_job(command, response)
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
        if active["inspection_result"] == "FAIL" and not active.get("quality_resumed"):
            active.update(state="PAUSED", quality_hold=True, awaiting_next_unit=True,
                          error_code="QUALITY_HOLD", message="검사 결과 · FAIL · 생산 일시정지 · 재개 또는 취소를 선택하세요.")
            self.publish(failed_feedback(active["job_id"], active["error_code"], active["message"],
                                         self.db_writer.sync_state) | {"state": "PAUSED"})
            return
        state = self.db_writer.get_job(active["job_id"])
        if state["completed_quantity"] < state["requested_quantity"]:
            if self.runtime_mode == "real":
                # A replacement PCB needs a new confirmation; do not reuse the previous Unit's.
                active.update(state="PAUSED", awaiting_next_unit=True, error_code="SCENE_CONFIRMATION_REQUIRED",
                              message="검사 결과 · " + active["inspection_result"] + " · 다음 PCB 준비 후 새 현장 확인이 필요합니다.")
                self.publish(failed_feedback(active["job_id"], active["error_code"], active["message"],
                                             self.db_writer.sync_state) | {"state": "PAUSED"})
                return
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
            active.pop("quality_resumed", None)
            active.pop("awaiting_next_unit", None)
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
            "message": active.get("message", ""),
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
            active.update(state="PAUSED", error_code=error_code, message=str(error))
            self.publish(failed_feedback(active["job_id"], error_code, str(error),
                                         self.db_writer.sync_state) | {"state": "PAUSED"})
            return
        if self.runtime_mode == "real" and error_code == "EXECUTION_CANCELLED":
            try:
                self.db_writer.finish(active["job_id"], "CANCELLED")
                self.db_writer.flush(DB_SYNC_TIMEOUT_SECONDS)
                active["control_pending"] = False
                self.terminal_snapshot = assembly_snapshot(active, "FAILED", error_code, str(error), self.db_writer.sync_state)
                self.active = None
                self.publish(failed_feedback(active["job_id"], error_code, str(error), self.db_writer.sync_state))
                return
            except Exception as cancel_error:
                error_code, error = "DB_ERROR", cancel_error
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
