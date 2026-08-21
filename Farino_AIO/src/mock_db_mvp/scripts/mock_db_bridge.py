#!/usr/bin/env python3
"""Keep DB work between Unity and the existing disposable Mock runner."""

import json
import random
import sys
import uuid

import rclpy
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

import production_store as store


PRODUCT_CODE = "HBM-ACCELERATOR-PACKAGE-BOARD"
PRODUCT_VERSION = "hbm-pkg-r1"
RECIPE_VERSION = "mock-r1"
INTERNAL_START = "/mock_db_mvp/internal/assembly/start"
INTERNAL_FEEDBACK = "/mock_db_mvp/internal/assembly/feedback"
EXTERNAL_START = "/unity/assembly/start"
EXTERNAL_FEEDBACK = "/unity/assembly/feedback"
DEFECT_TYPES = ("MISSING", "POSITION_ERROR", "ORIENTATION_ERROR", "CRACK")
RELAY_STATES = {"STARTED", "PICKED", "PLACED"}


def parse_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    if command == {"command": "status"}:
        return "status", None
    if not isinstance(command, dict) or set(command) != {
        "command", "request_id", "recipe_version", "observations"
    }:
        raise ValueError(
            "command, request_id, recipe_version and observations are required"
        )
    if command["command"] != "start":
        raise ValueError("command must be start or status")
    try:
        uuid.UUID(command["request_id"])
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("request_id must be a UUID string") from error
    if len(command["request_id"]) > 64:
        raise ValueError("request_id must be at most 64 characters")
    if command["recipe_version"] != RECIPE_VERSION:
        raise ValueError(f"recipe_version must be {RECIPE_VERSION}")
    if not isinstance(command["observations"], list) or not command["observations"]:
        raise ValueError("observations must be a non-empty list")
    return "start", command


def parse_internal_response(raw):
    try:
        response = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Mock start response is not valid JSON") from error
    if not isinstance(response, dict) or not isinstance(response.get("accepted"), bool):
        raise RuntimeError("Mock start response is missing accepted")
    return response


def failed_feedback(request_id, error_code, message):
    return {
        "request_id": request_id,
        "state": "FAILED",
        "step_order": 0,
        "part_id": "",
        "slot_code": "",
        "error_code": error_code,
        "message": message[:512],
    }


def unavailable_snapshot(message):
    return {
        "available": False,
        "active": False,
        "request_id": "",
        "recipe_version": "",
        "state": "IDLE",
        "placed_count": 0,
        "expected_step_count": 0,
        "held_step_order": 0,
        "held_part_id": "",
        "held_slot_code": "",
        "error_code": "UNAVAILABLE",
        "message": message[:512],
    }


def assembly_snapshot(active, state, error_code="", message=""):
    completed = state == "COMPLETED"
    return {
        "available": True,
        "active": state in RELAY_STATES,
        "request_id": active["request_id"],
        "recipe_version": RECIPE_VERSION,
        "state": state,
        "placed_count": (
            active["expected_step_count"] if completed else active["placed_count"]
        ),
        "expected_step_count": active["expected_step_count"],
        "held_step_order": active["held_step_order"],
        "held_part_id": active["held_part_id"],
        "held_slot_code": active["held_slot_code"],
        "error_code": error_code,
        "message": message[:512],
    }


def choose_inspection(rng, fail_probability, slot_codes):
    if rng.random() >= fail_probability:
        return "PASS", []
    if not slot_codes:
        raise RuntimeError("Mock FAIL inspection requires a product slot")
    return "FAIL", [{
        "slot_code": rng.choice(slot_codes),
        "defect_type": rng.choice(DEFECT_TYPES),
    }]


def self_check():
    request_id = "12345678-1234-5678-1234-567812345678"
    command = json.dumps({
        "command": "start",
        "request_id": request_id,
        "recipe_version": RECIPE_VERSION,
        "observations": [{}],
    })
    assert parse_command(command)[0] == "start"
    assert parse_command('{"command":"status"}')[0] == "status"
    assert choose_inspection(random.Random(1), 0.0, []) == ("PASS", [])
    result, defects = choose_inspection(random.Random(1), 1.0, ["SLOT-01"])
    assert result == "FAIL" and defects[0]["slot_code"] == "SLOT-01"
    assert failed_feedback(request_id, "DB_ERROR", "x")["state"] == "FAILED"
    active = {
        "request_id": request_id,
        "placed_count": 1,
        "expected_step_count": 2,
        "held_step_order": 0,
        "held_part_id": "",
        "held_slot_code": "",
    }
    assert assembly_snapshot(active, "PLACED")["active"]
    completed = assembly_snapshot(active, "COMPLETED")
    assert not completed["active"] and completed["placed_count"] == 2


class MockDbBridge(Node):
    def __init__(self):
        super().__init__("mock_db_bridge")
        probability = self.declare_parameter(
            "inspection_fail_probability", 0.2
        ).value
        seed = self.declare_parameter("random_seed", -1).value
        if isinstance(probability, bool) or not 0.0 <= float(probability) <= 1.0:
            raise ValueError("inspection_fail_probability must be between 0 and 1")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("random_seed must be an integer")

        # Fail before advertising Unity endpoints when DB config or recovery is unsafe.
        active_job = store.get_active_job_state()
        if active_job is not None:
            raise RuntimeError(
                f"active DB job {active_job['job_id']} exists; "
                "this MVP cannot recover its Unity request_id"
            )

        self.fail_probability = float(probability)
        self.rng = random.Random(None if seed == -1 else seed)
        self.active = None
        self.terminal_snapshot = None

        service_group = MutuallyExclusiveCallbackGroup()
        feedback_group = MutuallyExclusiveCallbackGroup()
        client_group = ReentrantCallbackGroup()
        self.internal_client = self.create_client(
            RemoteCmdInterface, INTERNAL_START, callback_group=client_group
        )
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
    def set_response(response, accepted, request_id="", error_code="", message=""):
        response.cmd_res = json.dumps({
            "accepted": accepted,
            "request_id": request_id,
            "error_code": error_code,
            "message": message[:512],
        }, separators=(",", ":"))
        return response

    async def call_internal(self, request):
        if not self.internal_client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError("internal Mock assembly service is unavailable")
        return await self.internal_client.call_async(request)

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
                snapshot = self.terminal_snapshot
            elif self.active is not None:
                snapshot = assembly_snapshot(self.active, self.active["state"])
            else:
                try:
                    internal = await self.call_internal(request)
                    response.cmd_res = internal.cmd_res
                    return response
                except Exception as error:
                    snapshot = unavailable_snapshot(str(error))
            response.cmd_res = json.dumps(snapshot, separators=(",", ":"))
            return response

        request_id = command["request_id"]
        if self.active is not None:
            return self.set_response(
                response, False, request_id, "BUSY", "assembly is already active"
            )
        if not self.internal_client.wait_for_service(timeout_sec=5.0):
            return self.set_response(
                response, False, request_id, "UNAVAILABLE",
                "internal Mock assembly service is unavailable",
            )

        job_id = None
        try:
            # These two committed rows make ROS2, rather than Unity, own the work ID.
            job_id = store.start_job(
                PRODUCT_CODE, PRODUCT_VERSION, 1, RECIPE_VERSION
            )
            unit_id = store.start_next_unit(job_id)
            self.active = {
                "request_id": request_id,
                "job_id": job_id,
                "unit_id": unit_id,
                "state": "STARTED",
                "placed_count": 0,
                "expected_step_count": len(command["observations"]),
                "held_step_order": 0,
                "held_part_id": "",
                "held_slot_code": "",
            }
            self.terminal_snapshot = None
        except Exception as error:
            if job_id is not None:
                cleanup_error = self.fail_job(job_id)
                if cleanup_error is not None:
                    error = RuntimeError(
                        f"{error}; cleanup failed: {cleanup_error}"
                    )
            return self.set_response(
                response, False, request_id, "DB_ERROR", str(error)
            )

        try:
            internal = await self.internal_client.call_async(request)
            result = parse_internal_response(internal.cmd_res)
            if result["accepted"]:
                return self.set_response(response, True, request_id)
            cleanup_error = self.fail_job(job_id)
            self.active = None
            if cleanup_error is not None:
                return self.set_response(
                    response, False, request_id, "DB_ERROR", str(cleanup_error)
                )
            response.cmd_res = internal.cmd_res
            return response
        except Exception as error:
            cleanup_error = self.fail_job(job_id)
            if cleanup_error is not None:
                error = RuntimeError(
                    f"{error}; cleanup failed: {cleanup_error}"
                )
            self.active = None
            return self.set_response(
                response, False, request_id, "INTERNAL_ERROR", str(error)
            )

    def fail_job(self, job_id):
        try:
            # finish_job also marks the running Unit FAILED in the same transaction.
            store.finish_job(job_id, "FAILED")
        except Exception as error:
            self.get_logger().error(f"failed to finalize job {job_id}: {error}")
            return error
        return None

    def publish(self, payload):
        self.external_publisher.publish(
            String(data=json.dumps(payload, separators=(",", ":")))
        )

    def on_internal_feedback(self, message):
        try:
            payload = json.loads(message.data)
            state = payload["state"]
            request_id = payload["request_id"]
        except (TypeError, KeyError, json.JSONDecodeError) as error:
            self.get_logger().error(f"invalid internal assembly feedback: {error}")
            return

        active = self.active
        if active is None or request_id != active["request_id"]:
            self.get_logger().warning(
                f"ignored feedback without matching active request: {request_id}"
            )
            return
        if state in RELAY_STATES:
            active["state"] = state
            if state == "STARTED":
                active.update({
                    "placed_count": 0,
                    "held_step_order": 0,
                    "held_part_id": "",
                    "held_slot_code": "",
                })
            elif state == "PICKED":
                active.update({
                    "held_step_order": payload["step_order"],
                    "held_part_id": payload["part_id"],
                    "held_slot_code": payload["slot_code"],
                })
            else:
                active.update({
                    "placed_count": payload["step_order"],
                    "held_step_order": 0,
                    "held_part_id": "",
                    "held_slot_code": "",
                })
            self.publish(payload)
            return
        if state == "FAILED":
            cleanup_error = self.fail_job(active["job_id"])
            if cleanup_error is not None:
                payload = failed_feedback(request_id, "DB_ERROR", str(cleanup_error))
            self.terminal_snapshot = assembly_snapshot(
                active, "FAILED", payload.get("error_code", ""),
                payload.get("message", ""),
            )
            self.active = None
            self.publish(payload)
            return
        if state != "COMPLETED":
            self.get_logger().error(f"unknown internal assembly state: {state}")
            return

        try:
            # Unity sees COMPLETED only after all three DB commits have succeeded.
            store.complete_assembly_and_consume_stock(active["unit_id"])
            result, defects = choose_inspection(
                self.rng,
                self.fail_probability,
                store.get_product_slot_codes(active["job_id"]),
            )
            store.record_inspection(active["unit_id"], result, defects)
            store.finish_job(active["job_id"], "COMPLETED")
        except Exception as error:
            cleanup_error = self.fail_job(active["job_id"])
            if cleanup_error is not None:
                error = RuntimeError(
                    f"{error}; cleanup failed: {cleanup_error}"
                )
            failed = failed_feedback(request_id, "DB_ERROR", str(error))
            self.terminal_snapshot = assembly_snapshot(
                active, "FAILED", failed["error_code"], failed["message"]
            )
            self.active = None
            self.publish(failed)
            return

        self.terminal_snapshot = assembly_snapshot(active, "COMPLETED")
        self.active = None
        self.publish(payload)
        self.get_logger().info(
            f"job {active['job_id']} completed with inspection {result}"
        )


def main(args=None):
    command_line = sys.argv[1:] if args is None else args
    if command_line == ["--self-check"]:
        self_check()
        print("mock_db_bridge self-check passed")
        return
    self_check()
    rclpy.init(args=args)
    node = MockDbBridge()
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
