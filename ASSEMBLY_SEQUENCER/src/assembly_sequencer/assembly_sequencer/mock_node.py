#!/usr/bin/env python3
"""AssemblySequencer orchestration for the existing Mock robot runner."""

import json
import random
import sys

import rclpy
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from .db import DbWriter
from .mock_backend import MockBackend
from .mock_contract import (
    RECIPE_VERSION,
    RELAY_STATES,
    apply_relay_feedback,
    assembly_snapshot,
    choose_inspection,
    failed_feedback,
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
PASS_IMAGE_PATH = "InspectionSamples/mock-pass.jpg"
FAIL_IMAGE_PATH = "InspectionSamples/mock-fail.jpg"


class MockAssemblySequencer(Node):
    def __init__(self):
        super().__init__("assembly_sequencer_mock")
        probability = self.declare_parameter(
            "inspection_fail_probability", 0.2
        ).value
        seed = self.declare_parameter("random_seed", -1).value
        if isinstance(probability, bool) or not 0.0 <= float(probability) <= 1.0:
            raise ValueError("inspection_fail_probability must be between 0 and 1")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("random_seed must be an integer")

        self.db_writer = DbWriter()
        try:
            recovered = self.db_writer.recover_interrupted()
            if recovered:
                self.get_logger().warning(
                    f"failed {recovered} interrupted Mock Unit attempt(s)"
                )
        except Exception:
            self.db_writer.close(0.1)
            raise

        self.fail_probability = float(probability)
        self.rng = random.Random(None if seed == -1 else seed)
        self.active = None
        self.terminal_snapshot = None

        service_group = MutuallyExclusiveCallbackGroup()
        feedback_group = MutuallyExclusiveCallbackGroup()
        client_group = ReentrantCallbackGroup()
        internal_client = self.create_client(
            RemoteCmdInterface, INTERNAL_START, callback_group=client_group
        )
        self.backend = MockBackend(self, internal_client)
        self.external_service = self.create_service(
            RemoteCmdInterface,
            EXTERNAL_START,
            self.on_external_request,
            callback_group=service_group,
        )
        self.external_publisher = self.create_publisher(
            String, EXTERNAL_FEEDBACK, 10
        )
        self.internal_subscription = self.create_subscription(
            String,
            INTERNAL_FEEDBACK,
            self.on_internal_feedback,
            10,
            callback_group=feedback_group,
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
        try:
            command_type, command = parse_command(request.cmd_str)
        except ValueError as error:
            return self.set_response(
                response, False, error_code="INVALID_REQUEST", message=str(error)
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
                    snapshot["db_sync_state"] = self.db_writer.sync_state
                except Exception as error:
                    snapshot = unavailable_snapshot(str(error))
            response.cmd_res = json.dumps(snapshot, separators=(",", ":"))
            return response

        if command_type in {"pause", "resume"}:
            job_id = command["job_id"]
            if self.active is None or self.active["job_id"] != job_id:
                return self.set_response(
                    response, False, job_id, "NOT_ACTIVE",
                    "matching assembly is not active",
                )
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

            active["transfer_requested"] = True
            active["assembled_pcb"] = command["assembled_pcb"]
            try:
                result, defects = choose_inspection(
                    self.rng, self.fail_probability, active["slot_codes"]
                )
                self.db_writer.assembly_completed(active["unit_id"])
                image_path = PASS_IMAGE_PATH if result == "PASS" else FAIL_IMAGE_PATH
                self.db_writer.inspection_recorded(
                    active["unit_id"], result, defects, image_path
                )
                active["inspection_result"] = result
            except Exception as error:
                self.fail_active("DB_ERROR", error)
                return self.set_response(
                    response, False, job_id, "DB_ERROR", str(error)
                )

            try:
                await self.backend.transfer_assembled_pcb(
                    job_id, active["assembled_pcb"]
                )
            except Exception as error:
                self.fail_active("INTERNAL_ERROR", error)
                return self.set_response(
                    response, False, job_id, "INTERNAL_ERROR", str(error)
                )
            return self.set_response(response, True, job_id)

        return await self.start_job(command, response)

    async def start_job(self, command, response):
        job_id = command["job_id"]
        if self.active is not None:
            if self.active["job_id"] == job_id:
                return self.set_response(response, True, job_id)
            return self.set_response(
                response, False, job_id, "BUSY", "another Job is active"
            )
        if not self.backend.is_available():
            return self.set_response(
                response, False, job_id, "INTERNAL_ERROR",
                "internal Mock assembly service is unavailable",
            )

        try:
            work = self.db_writer.claim(
                job_id, PRODUCT_CODE, PRODUCT_VERSION, RECIPE_VERSION
            )
            self.active = {
                "job_id": work["job_id"],
                "unit_id": work["unit_id"],
                "command": command,
                "state": "STARTED",
                "placed_count": 0,
                "expected_step_count": len(command["observations"]),
                "held_step_order": 0,
                "held_part_id": "",
                "held_slot_code": "",
                "slot_codes": self.db_writer.get_product_slot_codes(job_id),
                "transfer_requested": False,
                "inspection_result": "",
            }
            self.terminal_snapshot = None
            await self.backend.start(command)
            return self.set_response(response, True, job_id)
        except Exception as error:
            if self.active is not None:
                self.fail_active("INTERNAL_ERROR", error, immediate=True)
            return self.set_response(
                response, False, job_id, "INTERNAL_ERROR", str(error)
            )

    def fail_job(self, job_id, immediate=False):
        try:
            if immediate:
                self.db_writer.abort(job_id)
            else:
                self.db_writer.finish(job_id, "FAILED")
        except Exception as error:
            self.get_logger().error(f"failed to finalize job {job_id}: {error}")
            return error
        return None

    def fail_active(self, error_code, error, immediate=False):
        active = self.active
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
        self.external_publisher.publish(
            String(data=json.dumps(payload, separators=(",", ":")))
        )

    async def on_internal_feedback(self, message):
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

        state = payload["state"]
        if state in RELAY_STATES:
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

        if not active["transfer_requested"] or not active["inspection_result"]:
            self.fail_active(
                "INTERNAL_ERROR",
                "backend completed before conveyor inspection and transfer request",
            )
            return

        try:
            if not self.db_writer.flush(5.0):
                raise RuntimeError(
                    self.db_writer.last_error or "DB updates did not finish in time"
                )
            state = self.db_writer.get_job(active["job_id"])
            if state["completed_quantity"] < state["requested_quantity"]:
                work = self.db_writer.claim(
                    active["job_id"], PRODUCT_CODE, PRODUCT_VERSION, RECIPE_VERSION
                )
                active.update({
                    "unit_id": work["unit_id"],
                    "state": "STARTED",
                    "placed_count": 0,
                    "held_step_order": 0,
                    "held_part_id": "",
                    "held_slot_code": "",
                    "transfer_requested": False,
                    "inspection_result": "",
                })
                await self.backend.start(active["command"])
                return
            self.db_writer.finish(active["job_id"], "COMPLETED")
            if not self.db_writer.flush(5.0):
                raise RuntimeError(
                    self.db_writer.last_error or "Job completion did not finish in time"
                )
        except Exception as error:
            self.fail_active("DB_ERROR", error)
            return

        payload["db_sync_state"] = self.db_writer.sync_state
        self.terminal_snapshot = assembly_snapshot(
            active,
            "COMPLETED",
            db_sync_state=self.db_writer.sync_state,
        )
        self.active = None
        self.publish(payload)
        self.get_logger().info(
            f"job {active['job_id']} completed with inspection "
            f"{active['inspection_result']}"
        )

    def destroy_node(self):
        if not self.db_writer.close():
            self.get_logger().error(self.db_writer.last_error)
        return super().destroy_node()


def main(args=None):
    command_line = sys.argv[1:] if args is None else args
    if command_line == ["--self-check"]:
        self_check()
        print("assembly_sequencer mock self-check passed")
        return
    self_check()
    rclpy.init(args=args)
    node = MockAssemblySequencer()
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
