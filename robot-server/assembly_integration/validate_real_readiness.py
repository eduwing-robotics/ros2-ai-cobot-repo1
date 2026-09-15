#!/usr/bin/env python3
"""Fail closed until every recipe step has a taught physical board slot."""
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
recipe_path = ROOT / "config/assembly_recipe.yaml"
recipe = yaml.safe_load(recipe_path.read_text())
board = json.loads((recipe_path.parent / recipe["physical_board_file"]).resolve().read_text())
mapping = recipe["part_mapping"]
available = {
    slot["slot_id"]
    for part in board.get("physical_slot_overrides", {}).values()
    for slot in part.get("slots", [])
}
missing = []
for step in recipe["steps"]:
    internal = mapping[step["part_id"]]
    internal_slot = f"{internal}_{int(step['slot_code'].split('-')[-1]):02d}"
    if internal_slot not in available:
        missing.append({**step, "required_internal_slot": internal_slot})
print(json.dumps({"real_execution_ready": not missing and bool(recipe.get("real_execution_ready")),
                  "missing_slots": missing}, indent=2))
raise SystemExit(0 if not missing and recipe.get("real_execution_ready") else 2)
