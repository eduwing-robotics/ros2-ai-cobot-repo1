"""Validated Mock assembly messages and state transitions."""

import json
import math
import random
import uuid
from collections import Counter
from pathlib import Path

import yaml

DEFECT_TYPES = ("MISSING", "POSITION_ERROR", "ORIENTATION_ERROR", "CRACK")
RELAY_STATES = {
    "CONVEYOR_MOVING", "STARTED", "PICKED", "PLACED", "ASSEMBLY_COMPLETED",
    "PCB_PICKED", "PCB_PLACED", "PAUSED",
}
FEEDBACK_STATES = RELAY_STATES | {"COMPLETED", "FAILED"}
WORKFLOW_ACTIONS = {
    "before_all": (
        ("conveyor.move_to", "ASSEMBLY"),
        ("vision.resolve_targets", "recipe_steps"),
    ),
    "per_step": (
        ("robot.move_joint", "home"),
        ("robot.move_joint", "item_ready"),
        ("robot.pick", "current_part"),
        ("robot.move_joint", "home"),
        ("robot.move_joint", "assembly_ready"),
        ("robot.place", "current_slot"),
    ),
    "after_all": (
        ("conveyor.move_to", "INSPECTION"),
        ("inspection.run", "assembled_pcb"),
        ("robot.transfer", "assembled_pcb"),
    ),
}


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _validate_joint_point(value, label):
    if not isinstance(value, list) or len(value) != 6:
        raise ValueError(f"{label} must contain six numbers")
    for index, number in enumerate(value):
        _finite_number(number, f"{label}[{index}]")


def _validate_workflow(workflow):
    if not isinstance(workflow, dict) or set(workflow) != set(WORKFLOW_ACTIONS):
        raise ValueError("workflow must contain before_all, per_step and after_all")
    for section, allowed in WORKFLOW_ACTIONS.items():
        commands = workflow[section]
        if not isinstance(commands, list) or not commands:
            raise ValueError(f"workflow.{section} must be a non-empty list")
        actions = []
        for index, command in enumerate(commands):
            if not isinstance(command, dict) or len(command) != 1:
                raise ValueError(
                    f"workflow.{section}[{index}] must contain one action"
                )
            action = next(iter(command.items()))
            actions.append(action)
            if action not in allowed:
                raise ValueError(
                    f"unsupported workflow.{section} action: {command}"
                )
        if Counter(actions) != Counter(allowed):
            raise ValueError(
                f"workflow.{section} must contain each required action"
            )


def validate_recipe(recipe):
    if not isinstance(recipe, dict):
        raise ValueError("recipe must be a YAML object")
    required_fields = {
        "recipe_version", "frame", "joint_points", "motion",
        "workflow", "gripper", "steps",
    }
    if set(recipe) != required_fields:
        raise ValueError(
            "recipe must contain exactly recipe_version, frame, joint_points, "
            "motion, workflow, gripper and steps"
        )
    if recipe["frame"] != "base_link":
        raise ValueError("recipe frame must be base_link")

    joint_points = recipe["joint_points"]
    if not isinstance(joint_points, dict) or set(joint_points) != {
        "home", "item_ready", "assembly_ready"
    }:
        raise ValueError(
            "joint_points must contain home, item_ready and assembly_ready"
        )
    for name in ("home", "item_ready", "assembly_ready"):
        _validate_joint_point(joint_points[name], f"joint_points.{name}")

    motion = recipe["motion"]
    if not isinstance(motion, dict) or set(motion) != {
        "approach_dz_mm", "retract_dz_mm",
        "assembled_pcb_drop_approach_dz_mm",
    }:
        raise ValueError(
            "motion must contain approach_dz_mm, retract_dz_mm and "
            "assembled_pcb_drop_approach_dz_mm"
        )
    for name, value in motion.items():
        if _finite_number(value, f"motion.{name}") <= 0.0:
            raise ValueError(f"motion.{name} must be greater than zero")

    _validate_workflow(recipe["workflow"])

    steps = recipe["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("recipe steps must be a non-empty list")
    slot_codes = set()
    for expected_order, step in enumerate(steps, 1):
        if not isinstance(step, dict) or set(step) != {
            "order", "part_id", "slot_code"
        }:
            raise ValueError(
                f"recipe step {expected_order} must contain order, part_id and slot_code"
            )
        if isinstance(step["order"], bool) \
                or not isinstance(step["order"], int) \
                or step["order"] != expected_order:
            raise ValueError("recipe step order must be consecutive integers from 1")
        for field in ("part_id", "slot_code"):
            if not isinstance(step[field], str) or not step[field].strip():
                raise ValueError(
                    f"recipe step {expected_order} {field} must be non-empty"
                )
        if step["slot_code"] in slot_codes:
            raise ValueError(f"duplicate slot_code: {step['slot_code']}")
        slot_codes.add(step["slot_code"])

    gripper = recipe["gripper"]
    if not isinstance(gripper, dict) or set(gripper) != {
        "parts", "assembled_pcb"
    }:
        raise ValueError("gripper must contain parts and assembled_pcb")
    part_profiles = gripper["parts"]
    part_ids = {step["part_id"] for step in steps}
    if not isinstance(part_profiles, dict) or set(part_profiles) != part_ids:
        raise ValueError("gripper.parts must contain exactly the recipe part IDs")
    profiles = list(part_profiles.items())
    profiles.append(("assembled_pcb", gripper["assembled_pcb"]))
    for name, profile in profiles:
        if not isinstance(profile, dict) or set(profile) != {
            "grasp_opening_percent", "release_opening_percent"
        }:
            raise ValueError(
                f"gripper.{name} must contain grasp_opening_percent and "
                "release_opening_percent"
            )
        for field, value in profile.items():
            value = _finite_number(value, f"gripper.{name}.{field}")
            if not 0.0 <= value <= 100.0:
                raise ValueError(
                    f"gripper.{name}.{field} must be between 0 and 100"
                )
    return recipe


def load_recipe(path):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("recipe path must be a non-empty string")
    recipe_path = Path(path)
    with recipe_path.open(encoding="utf-8") as stream:
        recipe = yaml.safe_load(stream)
    if not isinstance(recipe, dict):
        raise ValueError("recipe must be a YAML object")
    recipe_version = recipe.get("recipe_version")
    if not isinstance(recipe_version, str) or not recipe_version.strip():
        raise ValueError("recipe_version must be a non-empty string")
    if recipe_path.stem != recipe_version:
        raise ValueError("recipe_version does not match the recipe filename")
    return validate_recipe(recipe)


def validate_ros_pose(value, label):
    if not isinstance(value, dict) or set(value) != {"xyz_mm", "xyzw"}:
        raise ValueError(f"{label} must contain xyz_mm and xyzw")
    xyz_mm = value["xyz_mm"]
    xyzw = value["xyzw"]
    if not isinstance(xyz_mm, list) or len(xyz_mm) != 3:
        raise ValueError(f"{label}.xyz_mm must contain three numbers")
    if not isinstance(xyzw, list) or len(xyzw) != 4:
        raise ValueError(f"{label}.xyzw must contain four numbers")
    xyz_mm = [
        _finite_number(number, f"{label}.xyz_mm[{index}]")
        for index, number in enumerate(xyz_mm)
    ]
    xyzw = [
        _finite_number(number, f"{label}.xyzw[{index}]")
        for index, number in enumerate(xyzw)
    ]
    norm = math.sqrt(sum(number * number for number in xyzw))
    if norm < 1e-9:
        raise ValueError(f"{label}.xyzw must not be zero")
    return {
        "xyz_mm": xyz_mm,
        "xyzw": [number / norm for number in xyzw],
    }


def validate_observations(observations):
    if not isinstance(observations, list) or not observations:
        raise ValueError("observations must be a non-empty list")
    validated = []
    for expected_order, observation in enumerate(observations, 1):
        if not isinstance(observation, dict) or set(observation) != {
            "order", "part_id", "source", "target"
        }:
            raise ValueError(
                f"observation {expected_order} must contain order, part_id, "
                "source and target"
            )
        if isinstance(observation["order"], bool) \
                or not isinstance(observation["order"], int) \
                or observation["order"] != expected_order:
            raise ValueError("observation order must be consecutive integers from 1")
        part_id = observation["part_id"]
        if not isinstance(part_id, str) or not part_id.strip():
            raise ValueError(f"observation {expected_order} part_id must be non-empty")
        validated.append({
            "order": expected_order,
            "part_id": part_id,
            "source": validate_ros_pose(
                observation["source"], f"observation {expected_order}.source"
            ),
            "target": validate_ros_pose(
                observation["target"], f"observation {expected_order}.target"
            ),
        })
    return validated


def resolve_observations(recipe, observations):
    recipe_steps = recipe["steps"]
    if len(recipe_steps) != len(observations):
        raise ValueError("Unity observation count does not match the recipe")
    resolved = []
    for recipe_step, observation in zip(recipe_steps, observations):
        if recipe_step["order"] != observation["order"]:
            raise ValueError("Unity observation order does not match the recipe")
        if recipe_step["part_id"] != observation["part_id"]:
            raise ValueError(
                f"Unity observation part_id does not match recipe step "
                f"{recipe_step['order']}"
            )
        profile = recipe["gripper"]["parts"][recipe_step["part_id"]]
        resolved.append({
            "step": recipe_step,
            "gripper_grasp_opening_percent": profile[
                "grasp_opening_percent"
            ],
            "gripper_release_opening_percent": profile[
                "release_opening_percent"
            ],
            "source": observation["source"],
            "target": observation["target"],
        })
    return resolved


def parse_command(raw, expected_recipe_version):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    if command == {"command": "status"}:
        return "status", None
    if not isinstance(command, dict):
        raise ValueError("cmd_str must be a JSON object")

    command_name = command.get("command")
    if command_name in {"pause", "resume", "conveyor_arrived"}:
        if set(command) != {"command", "job_id"}:
            raise ValueError("command and job_id are required")
        command_type = command_name
    elif command_name == "conveyor_failed":
        if set(command) != {"command", "job_id", "message"}:
            raise ValueError("command, job_id and message are required")
        if not isinstance(command["message"], str) or not command["message"].strip():
            raise ValueError("message must be a nonblank string")
        command_type = command_name
    elif command_name == "transfer_assembled_pcb":
        if set(command) != {"command", "job_id", "assembled_pcb"}:
            raise ValueError("command, job_id and assembled_pcb are required")
        assembled_pcb = command["assembled_pcb"]
        if not isinstance(assembled_pcb, dict) or set(assembled_pcb) != {
            "source", "target"
        }:
            raise ValueError("assembled_pcb must contain source and target")
        command["assembled_pcb"] = {
            "source": validate_ros_pose(
                assembled_pcb["source"], "assembled_pcb.source"
            ),
            "target": validate_ros_pose(
                assembled_pcb["target"], "assembled_pcb.target"
            ),
        }
        command_type = "transfer_assembled_pcb"
    else:
        if set(command) != {
            "command", "job_id", "recipe_version", "observations",
        }:
            raise ValueError(
                "command, job_id, recipe_version and observations are required"
            )
        if command_name != "observations":
            raise ValueError(
                "command must be observations, conveyor_arrived, conveyor_failed, "
                "pause, resume, transfer_assembled_pcb or status"
            )
        if command["recipe_version"] != expected_recipe_version:
            raise ValueError(
                f"recipe_version must be {expected_recipe_version}"
            )
        command["observations"] = validate_observations(
            command["observations"]
        )
        command_type = "observations"

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
    if "operation_id" in payload:
        try:
            payload["operation_id"] = str(uuid.UUID(payload["operation_id"]))
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("feedback operation_id must be a UUID string") from error
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
        "recipe_version": active["recipe_version"],
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


def self_check(recipe=None):
    job_id = "12345678-1234-5678-1234-567812345678"
    recipe_version = recipe["recipe_version"] if recipe else "assembly-r1"
    steps = recipe["steps"] if recipe else [{
        "order": 1, "part_id": "PART-01", "slot_code": "SLOT-01",
    }]
    pose = {"xyz_mm": [100.0, 200.0, 300.0], "xyzw": [0.0, 0.0, 0.0, 1.0]}
    command = json.dumps({
        "command": "observations",
        "job_id": job_id,
        "recipe_version": recipe_version,
        "observations": [{
            "order": step["order"],
            "part_id": step["part_id"],
            "source": pose,
            "target": pose,
        } for step in steps],
    })
    parsed = parse_command(command, recipe_version)
    assert parsed[0] == "observations" and parsed[1]["job_id"] == job_id
    if recipe is not None:
        resolved = resolve_observations(recipe, parsed[1]["observations"])
        assert len(resolved) == len(steps)
    assert parse_command(json.dumps({
        "command": "conveyor_arrived", "job_id": job_id,
    }), recipe_version)[0] == "conveyor_arrived"
    assert parse_command(json.dumps({
        "command": "conveyor_failed", "job_id": job_id, "message": "stopped",
    }), recipe_version)[0] == "conveyor_failed"
    assert parse_command(json.dumps({
        "command": "transfer_assembled_pcb",
        "job_id": job_id,
        "assembled_pcb": {"source": pose, "target": pose},
    }), recipe_version)[0] == "transfer_assembled_pcb"
    assert parse_command('{"command":"status"}', recipe_version)[0] == "status"
    assert parse_command(json.dumps({
        "command": "pause", "job_id": job_id,
    }), recipe_version)[0] == "pause"
    assert parse_command(json.dumps({
        "command": "resume", "job_id": job_id,
    }), recipe_version)[0] == "resume"
    assert unavailable_snapshot("offline")["job_id"] == ""
    assert choose_inspection(random.Random(1), 0.0, []) == ("PASS", [])
    result, defects = choose_inspection(random.Random(1), 1.0, ["SLOT-01"])
    assert result == "FAIL" and defects[0]["slot_code"] == "SLOT-01"
    assert failed_feedback(job_id, "DB_ERROR", "x")["state"] == "FAILED"
    active = {
        "job_id": job_id,
        "unit_id": 22,
        "recipe_version": recipe_version,
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
    assert assembly_snapshot(active, "PAUSED")["active"]
    assert assembly_snapshot(active, "PLACED")["job_id"] == job_id
    assert assembly_snapshot(active, "PLACED")["unit_id"] == 22
    completed = assembly_snapshot(active, "COMPLETED")
    assert not completed["active"] and completed["placed_count"] == 2
