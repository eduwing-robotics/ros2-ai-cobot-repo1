#!/usr/bin/env python3
"""Audit the S22 inspection model before a production authority decision.

This is a read-only gate.  It inventories the exact 25-slot contract, runtime
artifacts, model metadata, thresholds and one optional hybrid report.  It never
changes ``validated``/``authority`` fields and never turns an advisory result
into PASS or FAIL.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = PROJECT_DIR / "vision_assembly/config/inspection_fusion_contract.json"
DEFAULT_CONFIG = PROJECT_DIR / "vision_assembly/config/s22_fixed_reference_pose_candidate.json"
DEFAULT_PRESENCE_MODELS = PROJECT_DIR / "vision_assembly/slot_classifier/models"
DEFAULT_PATCHCORE_MODELS = PROJECT_DIR / "runtime/inspection/patchcore/pcb_components_strict_v4"

COMPONENT_KEYS = {
    "GPU": "gpu",
    "HBM": "hbm",
    "Power Module": "power_module",
    "VRM": "vrm",
    "Inductor": "inductor",
    "SMD Capacitor": "smd_capacitor",
}
REQUIRED_BASE_STAGES = ("presence", "pose", "orientation", "surface")
PIN_COMPONENTS = frozenset({"GPU", "HBM"})


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}"
    if not isinstance(value, dict):
        return None, "JSON_ROOT_NOT_OBJECT"
    return value, None


def _sha256(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def _resolve_path(project_dir: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_dir / path


def expected_slots(config: dict[str, Any], project_dir: Path = PROJECT_DIR) -> tuple[set[str], dict[str, str]]:
    """Return the expected slot IDs and their component types from the layout."""
    layout_value = config.get("board_layout")
    if not isinstance(layout_value, str):
        return set(), {}
    layout, error = _read_json(_resolve_path(project_dir, layout_value))
    if error or not layout:
        return set(), {}
    placements = layout.get("placements")
    if not isinstance(placements, list):
        return set(), {}
    slot_types = {
        str(item["slot_id"]): str(item["component_type"])
        for item in placements
        if isinstance(item, dict)
        and isinstance(item.get("slot_id"), str)
        and item.get("slot_id")
        and isinstance(item.get("component_type"), str)
    }
    return set(slot_types), slot_types


def _check_file(path: Path, *, sha: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
    if sha and result["exists"]:
        result["sha256"] = _sha256(path)
    return result


def _metadata_check(path: Path, *, required_authority: bool = False) -> dict[str, Any]:
    result = _check_file(path)
    if not result["exists"]:
        result.update(valid=False, reason="METADATA_MISSING")
        return result
    value, error = _read_json(path)
    if error:
        result.update(valid=False, reason=f"METADATA_INVALID:{error}")
        return result
    authority = value.get("authority")
    validated = value.get("validated")
    valid = isinstance(authority, str) and isinstance(validated, bool)
    if required_authority:
        valid = valid and authority == "AUTHORITATIVE" and validated is True
    result.update(
        valid=valid,
        authority=authority,
        validated=validated,
        reason=("OK" if valid else "AUTHORITY_OR_VALIDATION_NOT_RELEASED")
        if required_authority
        else ("OK" if valid else "AUTHORITY_METADATA_INCOMPLETE"),
    )
    return result


def _checkpoint_for(root: Path, component: str) -> Path | None:
    candidates = sorted(
        (root / component).glob("Patchcore/*/v*/weights/lightning/model.ckpt")
    )
    return candidates[-1] if candidates else None


def _threshold_check(path: Path, component: str) -> dict[str, Any]:
    result = _check_file(path)
    if not result["exists"]:
        result.update(valid=False, reason="CONTROLLED_DEFECT_THRESHOLD_MISSING")
        return result
    value, error = _read_json(path)
    if error:
        result.update(valid=False, reason=f"THRESHOLD_INVALID:{error}")
        return result
    settings = value.get("components", {}).get(component) if isinstance(value.get("components"), dict) else None
    if not isinstance(settings, dict):
        result.update(valid=False, reason="COMPONENT_THRESHOLD_MISSING")
        return result
    try:
        pass_max = float(settings["pass_max"])
        fail_min = float(settings["fail_min"])
    except (KeyError, TypeError, ValueError):
        result.update(valid=False, reason="COMPONENT_THRESHOLD_INVALID")
        return result
    authority = settings.get("authority", value.get("authority", "ADVISORY_ONLY"))
    valid = pass_max < fail_min and authority == "AUTHORITATIVE"
    result.update(
        valid=valid,
        pass_max=pass_max,
        fail_min=fail_min,
        authority=authority,
        reason="OK" if valid else "THRESHOLD_ADVISORY_OR_ORDER_INVALID",
    )
    return result


def _asset_inventory(
    contract: dict[str, Any],
    config: dict[str, Any],
    presence_root: Path,
    patchcore_root: Path,
    project_dir: Path,
    component_model_roots: dict[str, Path] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    assets: dict[str, Any] = {"presence": {}, "vrm_state": {}, "patchcore": {}, "pins": {}, "capture_quality": {}}

    for component_type, component in COMPONENT_KEYS.items():
        if component_type == "VRM":
            continue
        model = presence_root / "component_presence_candidate" / f"{component}_presence.torchscript.pt"
        metadata = presence_root / "component_presence_candidate" / f"{component}_presence.json"
        row = {
            "model": _check_file(model, sha=True),
            "metadata": _metadata_check(metadata, required_authority=True),
        }
        assets["presence"][component] = row
        if not row["model"]["exists"] or not row["metadata"].get("valid", False):
            blockers.append(f"presence:{component}")

    vrm_model = presence_root / "vrm_state.torchscript.pt"
    vrm_metadata = presence_root / "vrm_state.json"
    assets["vrm_state"] = {
        "model": _check_file(vrm_model, sha=True),
        "metadata": _metadata_check(vrm_metadata, required_authority=True),
    }
    if not assets["vrm_state"]["model"]["exists"] or not assets["vrm_state"]["metadata"].get("valid", False):
        blockers.append("vrm_state")

    component_model_roots = component_model_roots or {}
    for component_type, component in COMPONENT_KEYS.items():
        component_root = component_model_roots.get(component, patchcore_root)
        checkpoint = _checkpoint_for(component_root, component)
        normal = component_root / "normal_calibration.json"
        component_normal = component_root / component / "normal_calibration.json"
        if component_normal.is_file():
            normal = component_normal
        thresholds = component_root / "decision_thresholds.json"
        component_thresholds = component_root / component / "decision_thresholds.json"
        if component_thresholds.is_file():
            thresholds = component_thresholds
        row = {
            "checkpoint": _check_file(checkpoint, sha=True) if checkpoint else {"path": None, "exists": False},
            "normal_calibration": _check_file(normal),
            "decision_thresholds": _threshold_check(thresholds, component),
        }
        assets["patchcore"][component] = row
        if not row["checkpoint"]["exists"]:
            blockers.append(f"patchcore_checkpoint:{component}")
        if not row["normal_calibration"]["exists"]:
            blockers.append(f"patchcore_normal_calibration:{component}")
        if not row["decision_thresholds"].get("valid", False):
            blockers.append(f"patchcore_threshold:{component}")

    pin_config = project_dir / "vision_assembly/config/package_leg_inspection.json"
    hbm_config = project_dir / "vision_assembly/config/hbm_pin_reference.json"
    assets["pins"] = {
        "gpu": {"config": _check_file(pin_config), "reference": _check_file(project_dir / "runtime/inspection/reference/s22_package_legs_golden.png")},
        "hbm": {"config": _check_file(hbm_config)},
    }
    if not assets["pins"]["gpu"]["config"]["exists"] or not assets["pins"]["gpu"]["reference"]["exists"]:
        blockers.append("pins:gpu")
    if not assets["pins"]["hbm"]["config"]["exists"]:
        blockers.append("pins:hbm")

    quality = {
        "contract_status": next(
            (stage.get("current_status") for stage in contract.get("stages", [])
             if isinstance(stage, dict) and stage.get("id") == "capture_quality"),
            "MISSING",
        ),
        "validated": False,
        "reason": "CAPTURE_QUALITY_POLICY_REQUIRES_INDEPENDENT_CALIBRATION",
    }
    assets["capture_quality"] = quality
    blockers.append("capture_quality")
    return assets, blockers


def _report_audit(report: dict[str, Any] | None, expected: set[str], slot_types: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    if report is None:
        return {"provided": False, "ready": False, "reason": "REPORT_NOT_PROVIDED"}, ["report"]
    blockers: list[str] = []
    rows = report.get("slots")
    row_ids = {row.get("slot_id") for row in rows} if isinstance(rows, list) else set()
    roster_ok = row_ids == expected and len(row_ids) == 25
    if not roster_ok:
        blockers.append("report:incomplete_or_mismatched_25_slot_roster")
    missing: dict[str, list[str]] = {}
    non_authoritative: list[dict[str, str]] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("slot_id"), str):
                continue
            required = list(REQUIRED_BASE_STAGES)
            if slot_types.get(row["slot_id"]) in PIN_COMPONENTS:
                required.append("pins")
            stages = row.get("stages", {})
            for stage_name in required:
                stage = stages.get(stage_name) if isinstance(stages, dict) else None
                if not isinstance(stage, dict) or stage.get("status") != "PASS" or stage.get("authority") != "AUTHORITATIVE":
                    missing.setdefault(row["slot_id"], []).append(stage_name)
                    if isinstance(stage, dict):
                        non_authoritative.append({"slot_id": row["slot_id"], "stage": stage_name, "status": str(stage.get("status")), "authority": str(stage.get("authority"))})
    if missing:
        blockers.append("report:required_stage_not_authoritative_pass")
    quality = report.get("capture_quality", {})
    if not isinstance(quality, dict) or quality.get("policy", {}).get("validated") is not True:
        blockers.append("report:capture_quality_not_validated")
    result = {
        "provided": True,
        "status": report.get("status"),
        "input_image": report.get("input_image"),
        "input_sha256": report.get("input_sha256"),
        "roster_ok": roster_ok,
        "missing_or_non_authoritative": missing,
        "non_authoritative_count": len(non_authoritative),
        "capture_quality_validated": quality.get("policy", {}).get("validated") is True if isinstance(quality, dict) else False,
        "ready": not blockers,
    }
    return result, blockers


def build_gate(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    config_path: Path = DEFAULT_CONFIG,
    presence_models: Path = DEFAULT_PRESENCE_MODELS,
    patchcore_models: Path = DEFAULT_PATCHCORE_MODELS,
    report_path: Path | None = None,
    project_dir: Path = PROJECT_DIR,
    component_model_roots: dict[str, Path] | None = None,
) -> dict[str, Any]:
    contract, contract_error = _read_json(contract_path)
    config, config_error = _read_json(config_path)
    contract = contract or {}
    config = config or {}
    blockers: list[str] = []
    if contract_error:
        blockers.append(f"contract:{contract_error}")
    if config_error:
        blockers.append(f"config:{config_error}")
    expected, slot_types = expected_slots(config, project_dir)
    if len(expected) != 25:
        blockers.append(f"slot_roster:expected_25_found_{len(expected)}")
    assets, asset_blockers = _asset_inventory(
        contract,
        config,
        presence_models,
        patchcore_models,
        project_dir,
        component_model_roots,
    )
    blockers.extend(asset_blockers)
    report = None
    if report_path is not None:
        report, error = _read_json(report_path)
        if error:
            blockers.append(f"report:{error}")
    report_result, report_blockers = _report_audit(report, expected, slot_types)
    blockers.extend(report_blockers)
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema_version": 1,
        "contract_id": contract.get("contract_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready_for_production": not blockers,
        "expected_slots": len(expected),
        "assets": assets,
        "report": report_result,
        "blockers": blockers,
        "next_actions": [
            "Run the independent normal and controlled-defect capture plan for every required slot/stage.",
            "Generate slot-level PatchCore thresholds from held-out, slot-labelled data; keep them ADVISORY_ONLY until review.",
            "Validate capture-quality limits and exact preprocessing/model hashes on the inspection host.",
            "Promote authority only after physical review; this gate never performs promotion.",
        ] if blockers else [],
        "robot_command_sent": False,
        "conveyor_command_sent": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--presence-models", type=Path, default=DEFAULT_PRESENCE_MODELS)
    parser.add_argument("--patchcore-models", type=Path, default=DEFAULT_PATCHCORE_MODELS)
    parser.add_argument("--gpu-patchcore-models", type=Path, default=None)
    parser.add_argument("--inductor-patchcore-models", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--strict", action="store_true", help="exit 2 unless all release gates pass")
    args = parser.parse_args()
    result = build_gate(
        contract_path=args.contract.expanduser().resolve(),
        config_path=args.config.expanduser().resolve(),
        presence_models=args.presence_models.expanduser().resolve(),
        patchcore_models=args.patchcore_models.expanduser().resolve(),
        report_path=args.report.expanduser().resolve() if args.report else None,
        component_model_roots={
            key: value.expanduser().resolve()
            for key, value in (
                ("gpu", args.gpu_patchcore_models),
                ("inductor", args.inductor_patchcore_models),
            )
            if value is not None
        },
    )
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.expanduser().resolve().write_text(encoded, encoding="utf-8")
    print(json.dumps({"ready_for_production": result["ready_for_production"], "blockers": result["blockers"]}, ensure_ascii=False))
    return 0 if result["ready_for_production"] or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
