"""Validated Mock assembly messages and state transitions."""

import json
import random
import uuid


RECIPE_VERSION = "assembly-r1"
DEFECT_TYPES = ("MISSING", "POSITION_ERROR", "ORIENTATION_ERROR", "CRACK")
RELAY_STATES = {
    "STARTED", "PICKED", "PLACED", "ASSEMBLY_COMPLETED",
    "PCB_PICKED", "PCB_PLACED",
}
FEEDBACK_STATES = RELAY_STATES | {"COMPLETED", "FAILED"}


def parse_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    if command == {"command": "status"}:
        return "status", None
    if not isinstance(command, dict):
        raise ValueError("cmd_str must be a JSON object")

    command_name = command.get("command")
    if command_name == "transfer_assembled_pcb":
        if set(command) != {"command", "job_id", "assembled_pcb"}:
            raise ValueError("command, job_id and assembled_pcb are required")
        if not isinstance(command["assembled_pcb"], dict):
            raise ValueError("assembled_pcb must be an object")
        command_type = "transfer_assembled_pcb"
    else:
        if set(command) != {
            "command", "job_id", "recipe_version", "observations",
        }:
            raise ValueError(
                "command, job_id, recipe_version and observations are required"
            )
        if command_name != "start":
            raise ValueError(
                "command must be start, transfer_assembled_pcb or status"
            )
        if command["recipe_version"] != RECIPE_VERSION:
            raise ValueError(f"recipe_version must be {RECIPE_VERSION}")
        if not isinstance(command["observations"], list) \
                or not command["observations"]:
            raise ValueError("observations must be a non-empty list")
        command_type = "start"

    try:
        command["job_id"] = str(uuid.UUID(command["job_id"]))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("job_id must be a UUID string") from error
    return command_type, command


def parse_internal_response(raw):
    try:
        response = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Mock response is not valid JSON") from error
    if not isinstance(response, dict) or not isinstance(response.get("accepted"), bool):
        raise RuntimeError("Mock response is missing accepted")
    return response


def parse_feedback(raw):
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("feedback must be a JSON object") from error
    if not isinstance(payload, dict):
        raise ValueError("feedback must be a JSON object")

    required = {
        "job_id", "state", "step_order", "part_id", "slot_code",
        "error_code", "message",
    }
    if not required.issubset(payload):
        raise ValueError("feedback is missing required fields")
    try:
        payload["job_id"] = str(uuid.UUID(payload["job_id"]))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("feedback job_id must be a UUID string") from error
    if payload["state"] not in FEEDBACK_STATES:
        raise ValueError(f"unknown feedback state: {payload['state']}")
    if (isinstance(payload["step_order"], bool)
            or not isinstance(payload["step_order"], int)
            or payload["step_order"] < 0):
        raise ValueError("feedback step_order must be a non-negative integer")
    for field in ("part_id", "slot_code", "error_code", "message"):
        if not isinstance(payload[field], str):
            raise ValueError(f"feedback {field} must be a string")
    if payload["state"] in {"PICKED", "PLACED"}:
        if payload["step_order"] == 0:
            raise ValueError(f"{payload['state']} requires a positive step_order")
        if not payload["part_id"].strip() or not payload["slot_code"].strip():
            raise ValueError(f"{payload['state']} requires part_id and slot_code")
    return payload


def failed_feedback(
    job_id, error_code, message, db_sync_state="NOT_STARTED"
):
    return {
        "job_id": job_id,
        "state": "FAILED",
        "step_order": 0,
        "part_id": "",
        "slot_code": "",
        "error_code": error_code,
        "message": message[:512],
        "db_sync_state": db_sync_state,
    }


def unavailable_snapshot(message):
    return {
        "available": False,
        "active": False,
        "job_id": "",
        "unit_id": 0,
        "recipe_version": "",
        "state": "IDLE",
        "placed_count": 0,
        "expected_step_count": 0,
        "held_step_order": 0,
        "held_part_id": "",
        "held_slot_code": "",
        "error_code": "UNAVAILABLE",
        "message": message[:512],
        "db_sync_state": "NOT_STARTED",
    }


def assembly_snapshot(
    active, state, error_code="", message="", db_sync_state="NOT_STARTED"
):
    completed = state == "COMPLETED"
    return {
        "available": True,
        "active": state in RELAY_STATES,
        "job_id": active["job_id"],
        "unit_id": active["unit_id"],
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
        "db_sync_state": db_sync_state,
    }


def apply_relay_feedback(active, payload):
    state = payload["state"]
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
    elif state == "PLACED":
        active.update({
            "placed_count": payload["step_order"],
            "held_step_order": 0,
            "held_part_id": "",
            "held_slot_code": "",
        })


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
    job_id = "12345678-1234-5678-1234-567812345678"
    command = json.dumps({
        "command": "start",
        "job_id": job_id,
        "recipe_version": RECIPE_VERSION,
        "observations": [{}],
    })
    assert parse_command(command)[0] == "start"
    assert parse_command(command)[1]["job_id"] == job_id
    assert parse_command(json.dumps({
        "command": "transfer_assembled_pcb",
        "job_id": job_id,
        "assembled_pcb": {},
    }))[0] == "transfer_assembled_pcb"
    assert parse_command('{"command":"status"}')[0] == "status"
    assert unavailable_snapshot("offline")["job_id"] == ""
    assert choose_inspection(random.Random(1), 0.0, []) == ("PASS", [])
    result, defects = choose_inspection(random.Random(1), 1.0, ["SLOT-01"])
    assert result == "FAIL" and defects[0]["slot_code"] == "SLOT-01"
    assert failed_feedback(job_id, "DB_ERROR", "x")["state"] == "FAILED"
    active = {
        "job_id": job_id,
        "unit_id": 22,
        "placed_count": 0,
        "expected_step_count": 2,
        "held_step_order": 0,
        "held_part_id": "",
        "held_slot_code": "",
    }
    picked = parse_feedback(json.dumps({
        "job_id": job_id,
        "state": "PICKED",
        "step_order": 1,
        "part_id": "PART-01",
        "slot_code": "SLOT-01",
        "error_code": "",
        "message": "",
    }))
    apply_relay_feedback(active, picked)
    assert active["held_part_id"] == "PART-01"
    assert assembly_snapshot(active, "PLACED")["active"]
    assert assembly_snapshot(active, "ASSEMBLY_COMPLETED")["active"]
    assert assembly_snapshot(active, "PCB_PICKED")["placed_count"] == 0
    assert assembly_snapshot(active, "PLACED")["job_id"] == job_id
    assert assembly_snapshot(active, "PLACED")["unit_id"] == 22
    completed = assembly_snapshot(active, "COMPLETED")
    assert not completed["active"] and completed["placed_count"] == 2
