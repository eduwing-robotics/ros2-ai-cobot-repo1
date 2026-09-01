#!/usr/bin/env python3
"""Strict loader for the AssemblySequencer-owned Mock/Real recipe."""

import math
from pathlib import Path
import sys

import yaml


ROOT_FIELDS = {
    "recipe_version", "frame", "joint_points", "motion",
    "sequence", "gripper", "steps",
}
JOINT_POINT_NAMES = {"home", "item_ready", "assembly_ready"}
MOTION_FIELDS = {
    "approach_dz_mm", "retract_dz_mm",
    "assembled_pcb_drop_approach_dz_mm",
}
SEQUENCES = {
    "before_all": [
        "move_conveyor_to_assembly", "ensure_camera_calibrated",
    ],
    "per_step": [
        "home", "item_ready", "pick", "home", "assembly_ready", "place",
    ],
    "after_all": [
        "move_conveyor_to_inspection", "inspect_assembled_pcb",
        "transfer_assembled_pcb",
    ],
}


def _exact_object(value, fields, label):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} must contain exactly {', '.join(sorted(fields))}")


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(float(value)):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def validate_recipe(recipe, expected_version=None):
    _exact_object(recipe, ROOT_FIELDS, "recipe")
    recipe_version = recipe["recipe_version"]
    if not isinstance(recipe_version, str) or not recipe_version.strip():
        raise ValueError("recipe_version must be a non-empty string")
    if expected_version is not None:
        if not isinstance(expected_version, str) or not expected_version.strip():
            raise ValueError("expected recipe version must be a non-empty string")
        if recipe_version != expected_version:
            raise ValueError("recipe_version does not match the requested version")
    if recipe["frame"] != "base_link":
        raise ValueError("recipe frame must be base_link")

    joint_points = recipe["joint_points"]
    _exact_object(joint_points, JOINT_POINT_NAMES, "joint_points")
    for name, point in joint_points.items():
        if not isinstance(point, list) or len(point) != 6:
            raise ValueError(f"joint_points.{name} must contain six numbers")
        for index, value in enumerate(point):
            _finite_number(value, f"joint_points.{name}[{index}]")

    motion = recipe["motion"]
    _exact_object(motion, MOTION_FIELDS, "motion")
    for name, value in motion.items():
        if _finite_number(value, f"motion.{name}") <= 0.0:
            raise ValueError(f"motion.{name} must be greater than zero")

    sequence = recipe["sequence"]
    _exact_object(sequence, set(SEQUENCES), "sequence")
    if sequence != SEQUENCES:
        raise ValueError("recipe sequence does not match the supported assembly flow")

    steps = recipe["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("recipe steps must be a non-empty list")
    slot_codes = set()
    for expected_order, step in enumerate(steps, 1):
        _exact_object(
            step, {"order", "part_id", "slot_code"}, f"step {expected_order}"
        )
        if isinstance(step["order"], bool) or not isinstance(step["order"], int) \
                or step["order"] != expected_order:
            raise ValueError("step order must be consecutive integers from 1")
        for field in ("part_id", "slot_code"):
            if not isinstance(step[field], str) or not step[field].strip():
                raise ValueError(f"step {expected_order} {field} must be non-empty")
        if step["slot_code"] in slot_codes:
            raise ValueError(f"duplicate slot_code: {step['slot_code']}")
        slot_codes.add(step["slot_code"])

    gripper = recipe["gripper"]
    _exact_object(gripper, {"parts", "assembled_pcb"}, "gripper")
    part_ids = {step["part_id"] for step in steps}
    _exact_object(gripper["parts"], part_ids, "gripper.parts")
    profiles = list(gripper["parts"].items())
    profiles.append(("assembled_pcb", gripper["assembled_pcb"]))
    profile_fields = {"grasp_opening_percent", "release_opening_percent"}
    for name, profile in profiles:
        _exact_object(profile, profile_fields, f"gripper.{name}")
        for field, value in profile.items():
            value = _finite_number(value, f"gripper.{name}.{field}")
            if not 0.0 <= value <= 100.0:
                raise ValueError(
                    f"gripper.{name}.{field} must be between 0 and 100"
                )
    return recipe


def load_recipe(path, expected_version=None):
    recipe_path = Path(path)
    with recipe_path.open(encoding="utf-8") as stream:
        recipe = yaml.safe_load(stream)
    recipe = validate_recipe(recipe, expected_version)
    if recipe_path.stem != recipe["recipe_version"]:
        raise ValueError("recipe_version does not match the recipe filename")
    return recipe


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit("usage: python -m assembly_sequencer.recipe RECIPE.yaml")
    try:
        recipe = load_recipe(argv[0])
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise SystemExit(f"recipe validation failed: {error}") from error
    print(f"validated {recipe['recipe_version']}: {len(recipe['steps'])} steps")


if __name__ == "__main__":
    main()
