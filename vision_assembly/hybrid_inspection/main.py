#!/usr/bin/env python3
"""Run the S22 fixed-slot hybrid PCB inspection pipeline."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
from vrm_boundary_advisory import VrmBoundaryAdvisory
from capture_quality import assess_capture_quality, build_evidence_audit, build_provider_health
from active_slot_pose_reference import bind_active_slot_centers
from fixed_pose_reference import validate_fixed_reference
from vrm_rotation_geometry import corroborated_rotation, multi_axis_rotation, strong_boundary_rotation
from vrm_context_pose import context_pose_codes
from vrm_presence_advisory import inspect_context, corroborates_missing, summarize_presence_state


PROJECT_DIR = Path(__file__).resolve().parents[2]
MODULE_DIR = Path(__file__).resolve().parent
INSPECTION_DIR = PROJECT_DIR / "vision_assembly/inspection"
for directory in (MODULE_DIR, INSPECTION_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from opencv_inspectors import (  # noqa: E402
    CheckEvidence,
    check_auxiliary_pose,
    check_gpu_hbm_dot,
    check_inductor_marker,
    estimate_common_projection_bias,
)
from hbm_pin_bands import inspect_hbm_pins  # noqa: E402
from patchcore_inspector import ComponentPatchCoreInspector, PatchCoreEvidence  # noqa: E402
from package_leg_inspector import inspect as inspect_package_legs  # noqa: E402
from predict_component_patchcore import _restore_slot_map, _trim_map_to_slot  # noqa: E402
from preprocessor_and_cropper import (  # noqa: E402
    FixedSlot,
    FixedSlotCropper,
    PresenceEvidence,
    SlotPresenceClassifier,
    VrmSeatingClassifier,
    VrmSeatingEvidence,
    VrmStateClassifier,
    VrmStateEvidence,
    YoloSegAuxiliary,
)


DEFAULT_IMAGE = PROJECT_DIR / "runtime/inspection/s22_inspection_roi_latest.png"
# Provider pixels still use full_board_inspection.json through provider_crop_config.
# Pose uses a frozen normal reference; live component populations cannot move it.
DEFAULT_CONFIG = PROJECT_DIR / "vision_assembly/config/s22_fixed_reference_pose_candidate.json"
DEFAULT_OUTPUT = PROJECT_DIR / "runtime/inspection/hybrid_fixed_slot"
DEFAULT_PRESENCE_MODELS = PROJECT_DIR / "vision_assembly/slot_classifier/models"
DEFAULT_PATCHCORE_MODELS = (
    PROJECT_DIR / "runtime/inspection/patchcore/pcb_components_smd_v3"
)
DEFAULT_INDUCTOR_PATCHCORE_MODELS = (
    PROJECT_DIR / "runtime/inspection/patchcore/inductor_morning_candidate_20260907/models"
)
# GPU must not follow Inductor-only model promotions.
DEFAULT_GPU_PATCHCORE_MODELS = (
    PROJECT_DIR / "runtime/inspection/patchcore/pcb_components_strict_v4"
)
DEFAULT_PIN_CONFIG = PROJECT_DIR / "vision_assembly/config/package_leg_inspection.json"
DEFAULT_PIN_REFERENCE = PROJECT_DIR / "runtime/inspection/reference/s22_package_legs_golden.png"
DEFAULT_BOARD_LAYOUT = PROJECT_DIR / "vision_assembly/config/board_layout_from_unity.json"
STATUS_COLORS = {
    "PASS": (65, 220, 115),
    "FAIL": (55, 65, 245),
    "UNKNOWN": (35, 190, 255),
}
CANDIDATE_COLORS = {
    "RIGHT?": (25, 165, 255),
    "ROT?": (55, 65, 245),
    "MISSING?": (55, 65, 245),
    "DIR?": (55, 65, 245),
    "PINS?": (55, 65, 245),
    "SEATING?": (20, 125, 255),
    "POSE?": (25, 165, 255),
    "SURFACE?": (245, 205, 30),
}
CANDIDATE_PRIORITY = {
    "RIGHT?": 3,
    "ROT?": 4,
    "MISSING?": 6,
    "PINS?": 5,
    "DIR?": 4,
    "SEATING?": 3,
    "POSE?": 2,
    "SURFACE?": 1,
}
# SMD PatchCore cannot independently nominate a surface defect yet because its
# normal pixel baseline is very sensitive to compression/reflection.  Its map
# may still be displayed when another provider independently flags that slot.
SURFACE_ONLY_CANDIDATE_SUPPRESSED = {"smd_capacitor"}
from smd01_small_lip import RULE as SMD01_SMALL_LIP_RULE, small_lip_candidate, independent_lip_candidate
from vrm05_pose_disagreement import conflicting_pose as vrm05_conflicting_pose

SMD_SEATING_PATCHCORE_MIN = 0.25
SMD_SEATING_AUX_CONFIDENCE_MIN = 0.10
SMD_SEATING_AUX_CONFIDENCE_MAX = 0.30
# An SMD can rest on the socket lip while retaining a plausible 2-D centre.
# Five verified-normal captures and three controlled lip-seating captures per
# listed slot separated the observations below.  Keep these rules slot-specific
# until the same defect has been measured on the remaining SMD sockets.  They
# remain display-only ADVISORY evidence.
SMD_LIP_SEATING_RULES = {
    "smd_capacitor_01": {
        "aux_outline_confidence_min": 0.20,
        "mask_area_px_min": 4400.0,
        "patchcore_score_min": 0.10,
    },
    "smd_capacitor_02": {
        "aux_outline_confidence_min": 0.20,
        "mask_area_px_min": 4500.0,
        "patchcore_score_min": 0.25,
    },
    "smd_capacitor_04": {
        "aux_outline_confidence_min": 0.65,
        "mask_area_px_min": 4700.0,
        "patchcore_score_min": 0.17,
    },
    "smd_capacitor_05": {
        "aux_outline_confidence_min": 0.45,
        "mask_area_px_min": 4600.0,
        "patchcore_score_min": 0.25,
    },
}
# VRM01 and VRM02 have repeated physical lip-seating controls.  A normal-only
# PatchCore score cannot identify this defect by itself because verified normal
# and lip-seated score ranges can overlap.  Require a confidently non-empty
# slot, calibrated lateral geometry, a usable auxiliary outline, and local
# appearance evidence together.  The result remains display-only ADVISORY
# evidence.
VRM_LIP_SEATING_RULES = {
    "vrm_01": {
        "non_empty_confidence_min": 0.90,
        "aux_outline_confidence_min": 0.25,
        "absolute_transverse_offset_mm_min": 0.70,
        "mask_area_px_min": 21_800.0,
        "patchcore_score_min": 0.70,
    },
    "vrm_02": {
        "non_empty_confidence_min": 0.90,
        "aux_outline_confidence_min": 0.25,
        "absolute_transverse_offset_mm_min": 1.00,
        "mask_area_px_min": 21_000.0,
        "patchcore_score_min": 0.80,
    },
}
# The VRM surface is dark and nearly square, so its auxiliary segmentation
# outline is less confident than the large yellow parts.  Six user-verified
# normal captures had calibrated centre residuals <=0.252 mm, and an independent
# normal holdout remained <=0.413 mm.  Preserve the physical 0.75 mm limit, but
# expose a 0.70 mm near-boundary result as an operator-facing advisory candidate
# when an independent VRM state model still confirms a non-empty slot.
VRM_CALIBRATED_POSE_CANDIDATE_MIN_MM = 0.70
VRM_CALIBRATED_POSE_AUX_CONFIDENCE_MIN = 0.20
# A sub-0.90 ROTATED vote remains UNKNOWN under the locked fusion contract.  It
# may be displayed as DIR? only when the independent normal-only appearance
# model also exceeds every verified-normal VRM image score (normal max 0.768).
VRM_ROTATION_RAW_CONFIDENCE_MIN = 0.75
VRM_ROTATION_PATCHCORE_MIN = 0.85
# In the repeated all-VRM controlled scene, VRM01 kept a plausible centre but
# its outline expanded well beyond the six calibration frames (<=21585 px) and
# the independent normal holdout (22152 px), while PatchCore rose from a normal
# maximum of 0.768 to 1.0.  Keep this evidence specific to VRM01 until the same
# failure mode is controlled on the other slots.
VRM_OUTLINE_APPEARANCE_RULES = {
    "vrm_01": {
        "non_empty_confidence_min": 0.90,
        "aux_outline_confidence_min": 0.20,
        "mask_area_px_min": 23_000.0,
        "patchcore_score_min": 0.85,
    },
}
CORROBORATED_PRESENT_CONFIDENCE_MIN = 0.90
# A Power Module that is pushed well outside its long slot can leave the slot
# classifier looking mostly at the exposed socket, producing a weak EMPTY vote.
# Three controlled S22 captures separated that case from an actual empty slot:
# the displaced yellow body still produced a near-full auxiliary mask and a
# repeatable >3.16 mm centre error.  Use this only to correct the operator-facing
# cause label; all participating providers remain ADVISORY_ONLY.
POWER_MODULE_DISPLACED_BODY_POSE_CONFIDENCE_MIN = 0.55
POWER_MODULE_DISPLACED_BODY_POSITION_ERROR_MIN_MM = 2.0
POWER_MODULE_DISPLACED_BODY_MASK_AREA_MIN_PX = 90_000.0
# SMD masks have a repeatable slot-dependent offset along their long axis.
# Compare sideways displacement separately so the normal top-right SMD does
# not hide, or get confused with, a component leaving the socket sideways.
# This remains an operator-facing advisory gate, not an automatic FAIL vote.
SMD_TRANSVERSE_POSE_AUX_CONFIDENCE_MIN = 0.20
SMD_TRANSVERSE_POSE_OFFSET_MM = 0.84
# User-confirmed normal SMD01 reaches0.857649mm. Slot-specific advisory
# headroom only; independent seating/angle checks and raw CAD status remain.
SMD_SLOT_TRANSVERSE_POSE_OFFSET_MM = {"smd_capacitor_01": 0.90}


def _image_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _atomic_symlink(target: Path, link: Path) -> None:
    temporary = link.with_name(f".{link.name}.tmp")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target.resolve())
    temporary.replace(link)


def _provider_dict(
    item: PresenceEvidence | VrmSeatingEvidence | CheckEvidence | PatchCoreEvidence,
) -> dict[str, Any]:
    if isinstance(item, CheckEvidence):
        return item.to_dict()
    if isinstance(item, PatchCoreEvidence):
        return item.report_dict()
    return asdict(item)


REQUIRED_SLOT_STAGES = frozenset({"presence", "pose", "orientation", "surface"})


def fuse_required_stages(
    stages: dict[str, dict[str, Any]],
    required_stages: frozenset[str] = REQUIRED_SLOT_STAGES,
) -> tuple[str, str]:
    """Apply the locked PASS/FAIL/UNKNOWN provider contract."""
    authoritative = {
        name: evidence
        for name, evidence in stages.items()
        if isinstance(evidence, dict)
        and evidence.get("authority") == "AUTHORITATIVE"
        and evidence.get("status") in {"PASS", "FAIL", "UNKNOWN"}
        and _finite_vote(evidence)
    }
    failed = [name for name, evidence in authoritative.items() if evidence["status"] == "FAIL"]
    if failed:
        return "FAIL", "AUTHORITATIVE_FAIL:" + ",".join(sorted(failed))
    missing = (REQUIRED_SLOT_STAGES | required_stages) - stages.keys()
    if not missing and len(authoritative) == len(stages) and all(
        evidence["status"] == "PASS" for evidence in authoritative.values()
    ):
        return "PASS", "ALL_REQUIRED_STAGES_AUTHORITATIVE_PASS"
    unavailable = [
        name
        for name, evidence in stages.items()
        if name not in authoritative or evidence.get("status") != "PASS"
    ]
    return "UNKNOWN", "REQUIRED_STAGE_UNVERIFIED_OR_UNKNOWN:" + ",".join(sorted(set(unavailable) | missing))


def _finite_vote(evidence: dict[str, Any]) -> bool:
    """Reject corrupt numerical votes; authority is still provider-owned."""
    try:
        for key in ("confidence", "score"):
            if key in evidence:
                value = float(evidence[key])
                if not np.isfinite(value) or (key == "confidence" and not 0 <= value <= 1):
                    return False
        return True
    except (TypeError, ValueError, OverflowError):
        return False


def fuse_board_result(slot_reports, alignment_valid, alignment_reason, capture_quality, *, expected_slot_ids=None):
    if not alignment_valid:
        return 'UNKNOWN', f'BOARD_REGISTRATION_UNCERTAIN:{alignment_reason}'
    if capture_quality['blocks_decision']:
        return 'UNKNOWN', 'CAPTURE_QUALITY_RECHECK:' + ','.join(capture_quality['flags'])
    slot_ids = [item.get('slot_id') for item in slot_reports]
    if (len(slot_reports) != 25
            or any(not isinstance(slot_id, str) or not slot_id for slot_id in slot_ids)
            or len(set(slot_ids)) != 25
            or (expected_slot_ids is not None and set(slot_ids) != set(expected_slot_ids))):
        return 'UNKNOWN', 'INCOMPLETE_BOARD_SLOT_SET'
    if any(item['status'] == 'FAIL' for item in slot_reports):
        return 'FAIL', 'AT_LEAST_ONE_AUTHORITATIVE_SLOT_FAIL'
    if all(item['status'] == 'PASS' for item in slot_reports):
        if capture_quality['policy']['validated'] is True:
            return 'PASS', 'ALL_25_SLOTS_AND_CAPTURE_QUALITY_PASS'
        return 'UNKNOWN', 'CAPTURE_QUALITY_NOT_YET_CALIBRATED'
    return 'UNKNOWN', 'ONE_OR_MORE_SLOTS_UNKNOWN'


def abstain_direction_for_empty_slot(presence: dict, orientation: dict) -> dict:
    """An empty-slot feature is not a component direction; retain raw evidence."""
    if presence.get('predicted_state') != 'EMPTY':
        return orientation
    return {
        **orientation,
        'status': 'UNKNOWN',
        'authority': 'ADVISORY_ONLY',
        'confidence': 0.0,
        'reason': 'DIRECTION_UNDEFINED_FOR_EMPTY_CANDIDATE',
        'raw_orientation_evidence': orientation.copy(),
    }


def _vrm_presence_evidence(state: VrmStateEvidence) -> PresenceEvidence:
    if state.predicted_state == "UNKNOWN":
        status = "UNKNOWN"
    elif state.predicted_state == "EMPTY":
        status = "FAIL"
    else:
        status = "PASS"
    return PresenceEvidence(
        state.slot_id,
        state.predicted_state,
        status,
        state.confidence,
        state.authority,
        state.reason,
        state.model_path,
    )


def _vrm_non_empty_confidence(state: VrmStateEvidence) -> float:
    empty_probability = state.probabilities.get("EMPTY")
    if empty_probability is not None:
        return float(np.clip(1.0 - float(empty_probability), 0.0, 1.0))
    return float(state.confidence) if state.raw_predicted_state != "EMPTY" else 0.0


def _gpu_pin_evidence(pin_report: dict[str, Any]) -> CheckEvidence:
    component = next(
        (
            item
            for item in pin_report.get("components", [])
            if item.get("slot_id") == "ai_gpu"
        ),
        None,
    )
    if component is None:
        return CheckEvidence(
            "gpu_white_pin_continuity",
            "UNKNOWN",
            "UNAVAILABLE",
            0.0,
            "GPU_PIN_RESULT_MISSING",
            {},
            {},
        )
    observed = str(component.get("status", "RECHECK"))
    if observed == "FAIL":
        status, reason = "FAIL", "GPU_WHITE_PIN_PATTERN_DEFECT"
    elif observed == "PASS":
        status, reason = "PASS", "GPU_WHITE_PIN_PATTERN_WITHIN_REFERENCE"
    else:
        status, reason = "UNKNOWN", "GPU_WHITE_PIN_PATTERN_UNCERTAIN"
    sides = list(component.get("sides", []))
    return CheckEvidence(
        "gpu_white_pin_continuity",
        status,
        "ADVISORY_ONLY",
        float(component.get("local_match_score", 0.0)),
        reason,
        {
            "component_status": observed,
            "failed_sides": [
                str(side.get("side"))
                for side in sides
                if side.get("status") == "FAIL"
            ],
            "missing_points_px": [
                point
                for side in sides
                for point in side.get("missing_points_px", [])
            ],
            "sides": sides,
        },
        {"scope": "GPU_ONLY_UNTIL_HBM_FALSE_POSITIVES_ARE_RESOLVED"},
    )


def _orientation_check(
    slot: FixedSlot,
    cropper: FixedSlotCropper,
    vrm_state: VrmStateEvidence | None = None,
) -> CheckEvidence:
    if slot.component_type in {"GPU", "HBM"}:
        return check_gpu_hbm_dot(
            slot.crop_bgr,
            suppress_pin_columns=slot.component_type == "HBM",
            slot_inset_fraction=(0.22 / 1.44) if slot.component_type == "GPU" else 0.0,
        )
    if slot.component_type == "Inductor":
        settings = cropper.config["white_features"]
        return check_inductor_marker(
            slot.crop_bgr,
            expected_angle_deg=float(settings["inductor_expected_mark_angle_deg"]),
            tolerance_deg=float(settings["inductor_mark_angle_tolerance_deg"]),
            minimum_contrast=float(settings["inductor_mark_contrast_min"]),
            axis_tolerance_deg=float(settings.get("inductor_mark_axis_tolerance_deg", 10.0)),
            expected_inner_edge_deg=settings.get("inductor_mark_inner_edge_reference_deg", {}).get(slot.slot_id),
        )
    if slot.component_type == "VRM" and vrm_state is not None:
        if vrm_state.predicted_state == "CORRECT":
            status, reason = "PASS", "VRM_STATE_CORRECT_ORIENTATION"
        elif vrm_state.predicted_state == "ROTATED":
            status, reason = "FAIL", "VRM_STATE_ROTATED_ORIENTATION"
        elif vrm_state.predicted_state == "EMPTY":
            status, reason = "UNKNOWN", "VRM_ORIENTATION_NOT_APPLICABLE_WHEN_EMPTY"
        else:
            status, reason = "UNKNOWN", vrm_state.reason
        return CheckEvidence(
            "vrm_state_orientation",
            status,
            vrm_state.authority,
            vrm_state.confidence,
            reason,
            {"predicted_state": vrm_state.predicted_state},
            {"minimum_confidence": vrm_state.minimum_confidence},
        )
    return CheckEvidence(
        "axis_orientation",
        "UNKNOWN",
        "ADVISORY_ONLY",
        0.0,
        "INDEPENDENT_TYPE_ORIENTATION_PROVIDER_NOT_CALIBRATED",
        {},
        {"expected_axis_angle_deg": slot.expected_axis_angle_deg},
    )


def _slot_rect(slot: FixedSlot) -> tuple[int, int, int, int]:
    center_x, center_y, size_x, size_y = slot.geometry
    return (
        int(round(center_x - size_x * 0.5)),
        int(round(center_y - size_y * 0.5)),
        int(round(center_x + size_x * 0.5)),
        int(round(center_y + size_y * 0.5)),
    )


def display_codes(codes: list[str]) -> list[str]:
    """Operator categories only; keep detailed provider codes in JSON."""
    # Presence is a prerequisite for explaining a component's pose or pins.
    # This is presentation precedence only: raw contradictory evidence remains
    # available to fusion/debugging and an advisory absence is never a PASS.
    if "MISSING?" in codes:
        return ["MISSING?"]
    mapping = {"RIGHT?": "POSITION?", "POSE?": "POSITION?", "SEATING?": "POSITION?",
               "ROT?": "DIRECTION?", "DIR?": "DIRECTION?", "PINS?": "PINS?",
               "MISSING?": "MISSING?", "SURFACE?": "SURFACE?"}
    return list(dict.fromkeys(mapping.get(c, c) for c in codes))


def inductor_anomaly_visible(surface: dict) -> bool:
    """Display-only gray band; neither a calibrated defect threshold nor PASS.

    A user-confirmed normal crop scored 0.3302 against p99=0.3091.
    Provisional 20% headroom avoids promoting small baseline excursions to
    surface candidates. Raw maps/scores and independent direction checks stay
    intact; this requires validation on additional unseen normal/defect scenes.
    """
    if surface.get('component_key') != 'inductor' or surface.get('authority') != 'ADVISORY_ONLY':
        return False
    score, baseline = surface.get('score'), surface.get('normal_p99')
    return (score is not None and baseline is not None and
            np.isfinite(score) and np.isfinite(baseline) and baseline > 0 and score > baseline * 1.20)


def build_pose_display_audit(slot_reports, candidates):
    """Expose raw auxiliary failures without relabelling or changing heatmaps."""
    displayed = {c['slot_id'] for c in candidates
                 if set(c.get('codes', [])) & {'POSE?', 'RIGHT?', 'ROT?', 'SEATING?'}}
    rows = []
    for row in slot_reports:
        pose = row.get('stages', {}).get('pose', {})
        if pose.get('status') != 'FAIL':
            continue
        visible = row['slot_id'] in displayed
        rows.append(dict(slot_id=row['slot_id'], raw_status='FAIL',
                         authority=pose.get('authority'), confidence=pose.get('confidence'),
                         displayed_as_position_candidate=visible,
                         explanation=('POSITION_CANDIDATE_SHOWN' if visible else
                                      'VRM05_GEOMETRY_DISAGREEMENT_NOT_A_PASS' if vrm05_conflicting_pose(row) else
                                      'RAW_AUXILIARY_FAIL_NOT_PROMOTED_BY_DISPLAY_RULES_NOT_A_PASS'),
                         measured=pose.get('measured', {}), limits=pose.get('limits', {})))
    hidden = [r['slot_id'] for r in rows if not r['displayed_as_position_candidate']]
    return dict(raw_pose_fail_count=len(rows), undisplayed_count=len(hidden),
                undisplayed_slots=hidden, items=rows,
                note='Diagnostic only. No candidate is not a PASS; raw evidence and fusion remain unchanged.')


def apply_vrm_socket_policy(boundary: dict) -> dict:
    """Remove process-clearance nomination, not socket/rotation evidence."""
    if 'RIGHT?' not in boundary.get('codes', []):
        return boundary
    codes = [code for code in boundary['codes'] if code != 'RIGHT?']
    return {**boundary, 'codes': codes, 'status': 'UNKNOWN',
            'authority': 'ADVISORY_ONLY',
            'reason': 'VRM_BOUNDARY_' + '/'.join(codes) if codes else 'VRM_PROCESS_CLEARANCE_EXCLUDED',
            'reason_ko': '회전 의심' if codes else '우측 공정 여유는 검사 기준에서 제외',
            'raw_process_clearance_evidence': boundary.copy(),
            'inspection_policy': 'SOCKET_SEATING_NOT_RIGHT_CLEARANCE',
            'socket_seating_verified': False}


def build_advisory_candidates(slot_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize observed evidence without promoting it to a final defect.

    These candidates are a development-time reading aid.  They deliberately
    preserve the authority/status fields from the locked fusion contract and
    therefore cannot turn an UNKNOWN slot into PASS or FAIL.
    """
    candidates: list[dict[str, Any]] = []
    for row in slot_reports:
        stages = row["stages"]
        codes: list[str] = []
        details: list[str] = []
        boundary = apply_vrm_socket_policy(stages.get("vrm_boundary", {}))
        codes.extend(c for c in boundary.get("codes", []) if c in {"RIGHT?", "ROT?"})
        if codes:
            details.append(str(boundary.get("reason", "VRM_BOUNDARY_CANDIDATE")))
        presence = stages["presence"]
        pose = stages["pose"]
        orientation = stages["orientation"]
        pins = stages.get("pins", {})
        surface = stages["surface"]
        seating = stages.get("seating", {})
        missing_candidate = bool(presence.get("status") == "FAIL" or (
            presence.get("predicted_state", presence.get("predicted")) == "EMPTY"
            and presence.get("authority") not in {"UNAVAILABLE", "INVALID"}
        ))
        if row.get("component_type") == "VRM" and corroborates_missing(
            presence, row.get("vrm_presence_context") or {}
        ):
            missing_candidate = True
            details.append("UNCALIBRATED_STATE_AND_RGB_CONTEXT_AGREE_EMPTY")
        if orientation.get("status") == "FAIL":
            codes.append("DIR?")
            details.append(str(orientation.get("reason", "ORIENTATION_FAIL")))
        if "DIR?" not in codes and corroborated_rotation(row):
            codes.append("DIR?")
            details.append("VRM_FIXED_BOUNDARY_AXES_AGREE_ROTATION_GE_8_DEG_ADVISORY")
        if "DIR?" not in codes and multi_axis_rotation(row):
            codes.append("DIR?")
            details.append("VRM_THREE_AXES_MEDIAN_GE_8_DEG_SPREAD_LE_2_DEG_ADVISORY")
        if "DIR?" not in codes and strong_boundary_rotation(row):
            codes.append("DIR?")
            details.append("VRM_STRONG_CONTEXT_AND_BOUNDARY_ROTATION_OVER_TOLERANCE_PLUS_2_DEG_ADVISORY")
        context_codes = context_pose_codes(row) if not missing_candidate else []
        if context_codes:
            codes.extend(c for c in context_codes if c not in codes)
            details.append("VRM_RGB_CONTEXT_AND_TWO_OUTLINES_AGREE_POSE_ADVISORY_NOT_HEIGHT")
        if pins.get("status") == "FAIL":
            codes.append("PINS?")
            details.append(str(pins.get("reason", "PIN_PATTERN_FAIL")))
        # Keep the summary readable: weak auxiliary mask geometry remains in
        # JSON but only strong candidates are drawn on the operator image.
        measured_pose = pose.get("measured", {})
        smd_large_angle = (
            row.get("component_type") == "SMD Capacitor"
            and float(pose.get("confidence", 0.0)) >= 0.15
            and float(measured_pose.get("axis_angle_error_deg", 0.0)) >= 8.0
        )
        position_error = float(measured_pose.get("position_error_mm", 0.0))
        position_tolerance = float(
            pose.get("limits", {}).get("position_tolerance_mm", 0.0)
        )
        position_excess = max(0.0, position_error - position_tolerance)
        angle_error = float(measured_pose.get("axis_angle_error_deg", 0.0))
        angle_tolerance = float(
            pose.get("limits", {}).get("angle_tolerance_deg", 0.0)
        )
        angle_excess = max(0.0, angle_error - angle_tolerance)
        angle_checked = bool(measured_pose.get("axis_angle_checked", True))
        component_type = str(row.get("component_type", ""))
        presence_prediction = str(
            presence.get("predicted_state", presence.get("predicted", "UNKNOWN"))
        )
        corroborated_present_candidate = bool(
            presence_prediction == "PRESENT"
            and float(presence.get("confidence", 0.0))
            >= CORROBORATED_PRESENT_CONFIDENCE_MIN
        )
        transverse_offset = measured_pose.get("absolute_transverse_offset_mm")
        if transverse_offset is None:
            offset = measured_pose.get("offset_mm")
            expected_axis = pose.get("limits", {}).get("expected_axis_angle_deg")
            if (
                isinstance(offset, (list, tuple))
                and len(offset) == 2
                and expected_axis is not None
            ):
                radians = np.deg2rad(float(expected_axis))
                transverse_offset = abs(
                    -float(offset[0]) * np.sin(radians)
                    + float(offset[1]) * np.cos(radians)
                )
        smd_transverse_limit = SMD_SLOT_TRANSVERSE_POSE_OFFSET_MM.get(
            str(row.get("slot_id", "")), SMD_TRANSVERSE_POSE_OFFSET_MM)
        smd_transverse_displacement = bool(
            component_type == "SMD Capacitor"
            and corroborated_present_candidate
            and float(pose.get("confidence", 0.0))
            >= SMD_TRANSVERSE_POSE_AUX_CONFIDENCE_MIN
            and transverse_offset is not None
            and float(transverse_offset) >= smd_transverse_limit
        )
        # A raw auxiliary status can alternate at the exact numeric boundary.
        # Require a small display margin before drawing a high-confidence POSE?
        # candidate.  This leaves the measured status/evidence unchanged and
        # only suppresses sub-resolution operator-overlay chatter.
        meaningful_high_confidence_pose = bool(
            float(pose.get("confidence", 0.0)) >= 0.80
            and (
                position_excess >= 0.10
                or (angle_checked and angle_excess >= 1.0)
            )
        )
        component_pose_rules = {
            # Five unchanged, user-verified normal S22 captures placed PM02
            # 0.36--0.47 mm beyond the CAD+measurement tolerance after the
            # shared projection-bias correction.  A previously controlled
            # displaced PM01 was 0.58 mm beyond it.  Keep the underlying
            # 0.75 mm CAD pose check intact and suppress only the noisy
            # operator candidate below the measured 0.50 mm separation.
            "Power Module": (0.55, 0.50),
            "Inductor": (0.50, 0.25),
        }
        component_rule = component_pose_rules.get(component_type)
        significant_component_displacement = bool(
            component_rule
            and float(pose.get("confidence", 0.0)) >= component_rule[0]
            and position_excess >= component_rule[1]
        )
        # A strongly displaced long Power Module can partially leave its
        # expected slot and make the auxiliary segmentation confidence fall.
        # Do not let that confidence collapse hide a large measured shift when
        # the independent slot classifier still sees the component.  This is
        # display-only advisory evidence; it does not grant FAIL authority.
        severe_power_module_displacement = bool(
            component_type == "Power Module"
            and corroborated_present_candidate
            and float(pose.get("confidence", 0.0)) >= 0.10
            and position_excess >= 0.60
        )
        mask_area_px = measured_pose.get("mask_area_px")
        displaced_power_module_body = bool(
            component_type == "Power Module"
            and missing_candidate
            and presence_prediction == "EMPTY"
            and presence.get("status") != "FAIL"
            and str(presence.get("reason", "")) == "LOW_CONFIDENCE"
            and float(presence.get("confidence", 0.0))
            < CORROBORATED_PRESENT_CONFIDENCE_MIN
            and pose.get("status") == "FAIL"
            and float(pose.get("confidence", 0.0))
            >= POWER_MODULE_DISPLACED_BODY_POSE_CONFIDENCE_MIN
            and position_error >= POWER_MODULE_DISPLACED_BODY_POSITION_ERROR_MIN_MM
            and mask_area_px is not None
            and float(mask_area_px) >= POWER_MODULE_DISPLACED_BODY_MASK_AREA_MIN_PX
        )
        if missing_candidate and not displaced_power_module_body:
            # Keep MISSING first so it remains the primary cause whenever the
            # empty-slot evidence was not independently contradicted.
            codes.insert(0, "MISSING?")
            details.insert(0, str(presence.get("reason", "PRESENCE_FAIL")))
        if pose.get("status") == "FAIL" and (
            meaningful_high_confidence_pose
            or smd_large_angle
            or smd_transverse_displacement
            or significant_component_displacement
            or severe_power_module_displacement
        ):
            codes.append("POSE?")
            if smd_transverse_displacement:
                details.append(
                    "SMD_TRANSVERSE_OFFSET_"
                    f"{float(transverse_offset):.3f}_MM_GE_"
                    f"{smd_transverse_limit:.3f}_MM"
                )
            else:
                details.append(str(pose.get("reason", "POSE_FAIL")))
        score = surface.get("score")
        fail_min = surface.get("fail_min")
        component_key = str(surface.get("component_key", ""))
        # A partly lifted SMD can keep a plausible 2-D centre and long axis,
        # while its projected outline degrades and the fixed-slot appearance
        # changes sharply.  Require all three independent observations before
        # showing a seating candidate: the slot classifier still sees a part,
        # the auxiliary outline is available but weak, and PatchCore exceeds
        # the controlled separation from verified normal captures.  This is
        # deliberately advisory and does not re-enable SMD surface-only FAIL.
        pose_confidence = float(pose.get("confidence", 0.0))
        smd_seating_candidate = bool(
            component_key == "smd_capacitor"
            and corroborated_present_candidate
            and SMD_SEATING_AUX_CONFIDENCE_MIN
            <= pose_confidence
            < SMD_SEATING_AUX_CONFIDENCE_MAX
            and score is not None
            and float(score) >= SMD_SEATING_PATCHCORE_MIN
        )
        lip_rule = SMD_LIP_SEATING_RULES.get(str(row.get("slot_id", "")))
        smd_lip_seating_candidate = bool(
            component_key == "smd_capacitor"
            and lip_rule is not None
            and corroborated_present_candidate
            and pose_confidence
            >= float(lip_rule["aux_outline_confidence_min"])
            and mask_area_px is not None
            and float(mask_area_px) >= float(lip_rule["mask_area_px_min"])
            and score is not None
            and float(score) >= float(lip_rule["patchcore_score_min"])
        )
        smd_small_lip_candidate = small_lip_candidate(row)
        smd_independent_lip_candidate = independent_lip_candidate(row)
        if row.get("slot_id") == "smd_capacitor_01":
            # Area and appearance overlap verified normal seating. Retain this
            # evidence, but do not infer physical lifting from it alone. The
            # existing signed-position rule supplies additional 2-D evidence;
            # it is not independent height metrology or a PASS condition.
            row["smd01_lip_evidence_review"] = {
                "status": "UNKNOWN", "authority": "ADVISORY_ONLY",
                "area_appearance_trigger": smd_lip_seating_candidate,
                "position_corroborated": smd_small_lip_candidate,
                "reason": ("AREA_APPEARANCE_ONLY_AMBIGUOUS"
                           if smd_lip_seating_candidate and not smd_small_lip_candidate
                           else "NO_AREA_ONLY_NOMINATION"),
                "limitation": "No measured height; absent candidate is not PASS.",
                "position_boundary_deadband_px": SMD01_SMALL_LIP_RULE["boundary_deadband_px"],
                "position_deadband_is_measured_uncertainty": False,
            }
            smd_lip_seating_candidate = bool(
                smd_lip_seating_candidate and smd_small_lip_candidate
            )
            # User-scoped deferral: 2-D appearance does not establish lip height.
            # Keep all raw providers, missing/rotation/position checks and UNKNOWN.
            row["smd01_lip_evidence_review"].update({
                "reason": "SMD01_MICRO_SEATING_DEFERRED",
                "scope_status": "NOT_VALIDATED",
                "raw_candidate_triggers": {
                    "area_and_position": smd_lip_seating_candidate,
                    "signed_position_and_surface": smd_small_lip_candidate,
                    "independent_outline": smd_independent_lip_candidate,
                    "weak_segmentation_and_surface": smd_seating_candidate,
                },
                "limitation": "Micro lip seating is unresolved, not PASS. Other placement checks remain active.",
            })
            smd_lip_seating_candidate = False
            smd_small_lip_candidate = False
            smd_independent_lip_candidate = False
            smd_seating_candidate = False
        vrm_lip_rule = VRM_LIP_SEATING_RULES.get(str(row.get("slot_id", "")))
        vrm_state_evidence = row.get("vrm_state_evidence") or {}
        vrm_raw_state = str(
            vrm_state_evidence.get("raw_predicted_state", presence_prediction)
        )
        vrm_probabilities = vrm_state_evidence.get("probabilities") or {}
        empty_probability = vrm_probabilities.get("EMPTY")
        if empty_probability is None:
            vrm_non_empty_confidence = (
                float(presence.get("confidence", 0.0))
                if vrm_raw_state != "EMPTY"
                else 0.0
            )
        else:
            vrm_non_empty_confidence = float(
                np.clip(1.0 - float(empty_probability), 0.0, 1.0)
            )
        vrm_lip_seating_candidate = bool(
            component_key == "vrm"
            and vrm_lip_rule is not None
            and vrm_raw_state in {"CORRECT", "ROTATED"}
            and vrm_non_empty_confidence
            >= float(vrm_lip_rule["non_empty_confidence_min"])
            and pose.get("status") == "FAIL"
            and pose_confidence
            >= float(vrm_lip_rule["aux_outline_confidence_min"])
            and transverse_offset is not None
            and float(transverse_offset)
            >= float(vrm_lip_rule["absolute_transverse_offset_mm_min"])
            and mask_area_px is not None
            and float(mask_area_px) >= float(vrm_lip_rule["mask_area_px_min"])
            and score is not None
            and float(score) >= float(vrm_lip_rule["patchcore_score_min"])
        )
        vrm_learned_seating_candidate = bool(
            component_type == "VRM"
            and seating.get("predicted_state") == "SEATING"
            and seating.get("status") == "FAIL"
            and seating.get("authority") not in {"UNAVAILABLE", "INVALID"}
        )
        slot_reference_calibration_id = (
            measured_pose.get("slot_reference_calibration_id")
            or pose.get("limits", {}).get("slot_reference_calibration_id")
        )
        vrm_calibrated_pose_candidate = bool(
            component_type == "VRM"
            and slot_reference_calibration_id
            and vrm_non_empty_confidence >= CORROBORATED_PRESENT_CONFIDENCE_MIN
            and pose_confidence >= VRM_CALIBRATED_POSE_AUX_CONFIDENCE_MIN
            and position_error >= VRM_CALIBRATED_POSE_CANDIDATE_MIN_MM
            and not vrm05_conflicting_pose(row)
        )
        vrm_rotation_probability = float(vrm_probabilities.get("ROTATED", 0.0))
        vrm_rotation_candidate = bool(
            component_type == "VRM"
            and vrm_raw_state == "ROTATED"
            and vrm_non_empty_confidence >= CORROBORATED_PRESENT_CONFIDENCE_MIN
            and vrm_rotation_probability >= VRM_ROTATION_RAW_CONFIDENCE_MIN
            and score is not None
            and float(score) >= VRM_ROTATION_PATCHCORE_MIN
        )
        vrm_outline_rule = VRM_OUTLINE_APPEARANCE_RULES.get(
            str(row.get("slot_id", ""))
        )
        vrm_outline_appearance_candidate = bool(
            component_type == "VRM"
            and vrm_outline_rule is not None
            and vrm_non_empty_confidence
            >= float(vrm_outline_rule["non_empty_confidence_min"])
            and pose_confidence
            >= float(vrm_outline_rule["aux_outline_confidence_min"])
            and mask_area_px is not None
            and float(mask_area_px) >= float(vrm_outline_rule["mask_area_px_min"])
            and score is not None
            and float(score) >= float(vrm_outline_rule["patchcore_score_min"])
        )
        if vrm_rotation_candidate and "DIR?" not in codes:
            codes.append("DIR?")
            details.append(
                "VRM_ROTATION_CORROBORATED_BY_STATE_"
                f"{vrm_rotation_probability:.3f}_AND_PATCHCORE_{float(score):.3f}"
            )
        if vrm_learned_seating_candidate:
            codes.append("SEATING?")
            seating_probability = float(
                seating.get("probabilities", {}).get("SEATING", 0.0)
            )
            details.append(
                "VRM_FIXED_SLOT_SEATING_MODEL_"
                f"P_{seating_probability:.4f}_GE_"
                f"{float(seating.get('seating_min_probability', 1.0)):.4f}"
            )
        elif vrm_lip_seating_candidate:
            codes.append("SEATING?")
            slot_label = str(row.get("slot_id", "vrm")).replace("_", "").upper()
            details.append(
                f"{slot_label}_LIP_SEATING_CORROBORATED_BY_"
                f"NON_EMPTY_{vrm_non_empty_confidence:.3f}_"
                f"TRANSVERSE_{float(transverse_offset):.3f}_MM_"
                f"OUTLINE_{pose_confidence:.3f}_MASK_AREA_{float(mask_area_px):.1f}_"
                f"AND_PATCHCORE_{float(score):.3f}"
            )
        elif smd_lip_seating_candidate:
            codes.append("SEATING?")
            details.append(
                "SMD_LIP_SEATING_CORROBORATED_BY_"
                f"OUTLINE_{pose_confidence:.3f}_MASK_AREA_{float(mask_area_px):.1f}_"
                f"AND_PATCHCORE_{float(score):.3f}"
            )
        elif smd_small_lip_candidate:
            codes.append("SEATING?")
            details.append(
                "SMD01_SMALL_LIP_ADVISORY_RAW_Y_"
                f"{float(measured_pose['raw_offset_mm'][1]):.4f}_MM_"
                f"AND_PATCHCORE_{float(score):.3f}"
            )
        elif smd_independent_lip_candidate:
            codes.append("SEATING?")
            details.append(
                "SMD01_INDEPENDENT_OUTLINE_RAW_Y_"
                f"{float(row['smd01_outline_evidence']['raw_y_mm']):.4f}_MM_"
                f"AND_PATCHCORE_{float(score):.3f}"
            )
        elif smd_seating_candidate:
            codes.append("SEATING?")
            details.append(
                f"SMD_PRESENT_WITH_WEAK_OUTLINE_{pose_confidence:.3f}_AND_PATCHCORE_{float(score):.3f}"
            )
        if (
            not (vrm_lip_seating_candidate or vrm_learned_seating_candidate)
            and "POSE?" not in codes
            and (
                vrm_calibrated_pose_candidate
                or vrm_outline_appearance_candidate
            )
        ):
            codes.append("POSE?")
            if vrm_calibrated_pose_candidate:
                details.append(
                    "VRM_CALIBRATED_POSITION_"
                    f"{position_error:.3f}_MM_GE_"
                    f"{VRM_CALIBRATED_POSE_CANDIDATE_MIN_MM:.3f}_MM_"
                    f"WITH_NON_EMPTY_{vrm_non_empty_confidence:.3f}"
                )
            else:
                details.append(
                    "VRM_OUTLINE_AND_APPEARANCE_OUTSIDE_NORMAL_"
                    f"MASK_{float(mask_area_px):.1f}_"
                    f"PATCHCORE_{float(score):.3f}"
                )
        if (
            component_key not in SURFACE_ONLY_CANDIDATE_SUPPRESSED
            and score is not None
            and fail_min is not None
            and float(score) >= float(fail_min)
        ):
            codes.append("SURFACE?")
            details.append(
                f"PATCHCORE_SCORE_{float(score):.3f}_ABOVE_CONTROLLED_FAIL_MIN_{float(fail_min):.3f}"
            )
        if fail_min is None and inductor_anomaly_visible(surface) and not codes:
            codes.append("SURFACE?")
            details.append("INDUCTOR_PATCHCORE_ABOVE_1_20_NORMAL_P99_DISPLAY_ONLY_NOT_DEFECT_THRESHOLD")
        if not codes:
            continue
        primary = max(codes, key=lambda item: CANDIDATE_PRIORITY[item])
        candidates.append(
            {
                "slot_id": row["slot_id"],
                "codes": codes,
                "display_codes": display_codes(codes),
                "display_categories_ko": [
                    {"POSITION?": "위치 오류 의심", "DIRECTION?": "방향 오류 의심",
                     "PINS?": "핀 오류 의심", "MISSING?": "누락 의심", "SURFACE?": "표면 오류 의심"}[c]
                    for c in display_codes(codes)
                ],
                "primary_code": primary,
                "pin_points_crop_px": pins.get("measured", {}).get("defect_points_crop_px", []),
                "details": details,
                "authority": "ADVISORY_ONLY",
                "confirmed_defect": False,
            }
        )
    return candidates


def _absolute_patchcore_evidence_map(
    aligned: np.ndarray,
    slots: list[FixedSlot],
    patchcore: dict[str, PatchCoreEvidence],
) -> np.ndarray:
    """Map relative PatchCore evidence without granting it verdict authority.

    A normal-only pixel percentile is not a defect threshold.  The heatmap is
    therefore restored as explicitly unverified visual evidence while the
    candidate list and final fusion ignore it until controlled thresholds exist.
    """
    evidence_map = np.zeros(aligned.shape[:2], np.float32)
    for slot in slots:
        evidence = patchcore.get(slot.slot_id)
        if (
            evidence is None
            or evidence.anomaly_map is None
            or evidence.normal_pixel_p999 is None
        ):
            continue
        center_x, center_y, size_x, size_y = slot.geometry
        crop_width = max(12, int(round(size_x * 1.44)))
        crop_height = max(12, int(round(size_y * 1.44)))
        rotated = crop_height > crop_width
        restored = _restore_slot_map(
            np.asarray(evidence.anomaly_map, np.float32),
            (crop_width, crop_height),
            rotated,
        )
        restored = _trim_map_to_slot(restored, (size_x, size_y))
        normal_limit = max(float(evidence.normal_pixel_p999), 0.01)
        display_span = max(normal_limit * 0.75, 0.04)
        normalized = np.clip((restored - normal_limit) / display_span, 0.0, 1.0)
        raw_x0, raw_y0, raw_x1, raw_y1 = _slot_rect(slot)
        x0, y0 = max(0, raw_x0), max(0, raw_y0)
        x1, y1 = min(aligned.shape[1], raw_x1), min(aligned.shape[0], raw_y1)
        if x1 <= x0 or y1 <= y0:
            continue
        normalized = cv2.resize(
            normalized, (raw_x1 - raw_x0, raw_y1 - raw_y0), interpolation=cv2.INTER_LINEAR
        )
        # Clip the restored map at the board edge; never squeeze off-board
        # evidence into the visible portion of the physical slot.
        normalized = normalized[y0 - raw_y0:y1 - raw_y0, x0 - raw_x0:x1 - raw_x0]
        evidence_map[y0:y1, x0:x1] = np.maximum(
            evidence_map[y0:y1, x0:x1], normalized
        )
    return evidence_map


def _gate_evidence_map_to_candidates(
    evidence_map: np.ndarray,
    slots: list[FixedSlot],
    candidates: list[dict[str, Any]],
) -> np.ndarray:
    """Show unverified PatchCore colour only in independently flagged slots.

    The complete relative map is still archived for engineering diagnostics.
    This prevents ordinary normal-baseline excess in an otherwise unflagged
    slot from looking like a confirmed defect on the operator report.
    """
    candidate_ids = {str(item["slot_id"]) for item in candidates}
    gated = np.zeros_like(evidence_map)
    for slot in slots:
        if slot.slot_id not in candidate_ids:
            continue
        x0, y0, x1, y1 = _slot_rect(slot)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(evidence_map.shape[1], x1), min(evidence_map.shape[0], y1)
        if x1 > x0 and y1 > y0:
            gated[y0:y1, x0:x1] = evidence_map[y0:y1, x0:x1]
    return gated


def _heatmap_images(aligned: np.ndarray, evidence_map: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if (aligned.ndim != 3 or aligned.shape[2] != 3 or aligned.dtype != np.uint8
            or evidence_map.ndim != 2 or evidence_map.shape != aligned.shape[:2]
            or not evidence_map.size or not np.isfinite(evidence_map).all()):
        raise ValueError("Heatmap requires a matching finite 2-D map and uint8 BGR image")
    color = cv2.applyColorMap(
        np.clip(evidence_map * 255.0, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO
    )
    visible = evidence_map > 0.015
    heat_only = np.full_like(aligned, (13, 11, 20))
    heat_only[visible] = color[visible]
    overlay = aligned.copy()
    alpha = np.clip(0.18 + evidence_map * 0.68, 0.0, 0.82)
    alpha[~visible] = 0.0
    blended = (
        aligned.astype(np.float32) * (1.0 - alpha[..., None])
        + color.astype(np.float32) * alpha[..., None]
    )
    overlay[visible] = np.clip(blended[visible], 0, 255).astype(np.uint8)
    return heat_only, overlay


def _annotate_candidates(
    image: np.ndarray,
    slots: list[FixedSlot],
    candidates: list[dict[str, Any]],
) -> np.ndarray:
    canvas = image.copy()
    slot_by_id = {slot.slot_id: slot for slot in slots}
    for candidate in candidates:
        slot = slot_by_id[candidate["slot_id"]]
        code = candidate["primary_code"]
        color = CANDIDATE_COLORS[code]
        x0, y0, x1, y1 = _slot_rect(slot)
        cv2.rectangle(canvas, (x0, y0), (x1, y1), color, 3, cv2.LINE_AA)
        for px, py in candidate.get("pin_points_crop_px", []):
            ox, oy = slot.crop_origin_px
            point = (int(round(ox + px)), int(round(oy + py)))
            if 0 <= point[0] < canvas.shape[1] and 0 <= point[1] < canvas.shape[0]:
                cv2.circle(canvas, point, 6, CANDIDATE_COLORS["PINS?"], 2, cv2.LINE_AA)
        label = f"{slot.slot_id} {'/'.join(display_codes(candidate['codes']))}"
        (text_w, text_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1
        )
        label_y = max(text_h + 4, y0 - 5)
        cv2.rectangle(
            canvas,
            (x0, label_y - text_h - 4),
            (min(canvas.shape[1] - 1, x0 + text_w + 6), label_y + baseline + 2),
            (15, 15, 18),
            -1,
        )
        cv2.putText(
            canvas,
            label,
            (x0 + 3, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            color,
            1,
            cv2.LINE_AA,
        )
    return canvas


def _render_slot_diagnostic(
    aligned: np.ndarray,
    slots: list[FixedSlot],
    slot_reports: list[dict[str, Any]],
    board_status: str,
    alignment_score: float,
) -> np.ndarray:
    panel_height = 74
    panel = np.full((panel_height, aligned.shape[1], 3), 22, np.uint8)
    color = STATUS_COLORS[board_status]
    cv2.putText(
        panel,
        f"S22 FIXED-SLOT HYBRID AOI | {board_status} | ALIGN {alignment_score:.3f}",
        (20, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.78,
        color,
        2,
        cv2.LINE_AA,
    )
    counts = {status: sum(row["status"] == status for row in slot_reports) for status in STATUS_COLORS}
    cv2.putText(
        panel,
        f"PASS {counts['PASS']}   FAIL {counts['FAIL']}   UNKNOWN {counts['UNKNOWN']}   | unverified providers never create PASS",
        (20, 61),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        (210, 215, 220),
        1,
        cv2.LINE_AA,
    )
    canvas = aligned.copy()
    reports = {row["slot_id"]: row for row in slot_reports}
    for slot in slots:
        row = reports[slot.slot_id]
        color = STATUS_COLORS[row["status"]]
        x0, y0, x1, y1 = _slot_rect(slot)
        cv2.rectangle(canvas, (x0, y0), (x1, y1), color, 2, cv2.LINE_AA)
        label = f"{slot.slot_id} {row['status'][0]}"
        cv2.putText(
            canvas,
            label,
            (x0 + 2, max(14, y0 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            color,
            1,
            cv2.LINE_AA,
        )
    return np.vstack((panel, canvas))


def _render_evidence_report(
    aligned: np.ndarray,
    heat_only: np.ndarray,
    overlay: np.ndarray,
    slots: list[FixedSlot],
    candidates: list[dict[str, Any]],
    board_status: str,
    alignment_score: float,
    boundary_items: dict | None = None,
    pose_display_audit: dict | None = None,
    capture_quality: dict | None = None,
    evidence_audit: dict | None = None,
    provider_health: dict | None = None,
) -> np.ndarray:
    original = _annotate_candidates(aligned, slots, candidates)
    overlay = _annotate_candidates(overlay, slots, candidates)
    display_height = 690
    display_width = int(round(aligned.shape[1] * display_height / aligned.shape[0]))
    gap = 12
    panels = [
        cv2.resize(item, (display_width, display_height), interpolation=cv2.INTER_AREA)
        for item in (original, heat_only, overlay)
    ]
    total_width = display_width * 3 + gap * 4
    header_height = 136 if pose_display_audit is not None else 104
    if capture_quality is not None:
        header_height += 98
    title_height = 42
    footer_height = 154
    output = np.full(
        (header_height + title_height + display_height + footer_height, total_width, 3),
        20,
        np.uint8,
    )
    final_color = STATUS_COLORS[board_status]
    cv2.putText(
        output,
        f"FINAL {board_status} | ALIGN {alignment_score:.3f} | ADVISORY CANDIDATES {len(candidates)}",
        (22, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.90,
        final_color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        output,
        "COLOUR = PATCHCORE RESPONSE ABOVE NORMAL BASELINE; NOT A CONFIRMED DEFECT",
        (22, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.66,
        (220, 225, 230),
        2,
        cv2.LINE_AA,
    )
    hidden_pose = (pose_display_audit or {}).get('undisplayed_count', 0)
    if pose_display_audit is not None:
        cv2.putText(output,
                    f"UNDISPLAYED AUXILIARY POSE FLAGS: {hidden_pose} | NO CANDIDATE DOES NOT MEAN PASS | DETAILS: JSON / SLOT DIAGNOSTIC",
                    (22, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.61, (180, 200, 220), 1, cv2.LINE_AA)
    if capture_quality is not None:
        base_y = header_height - 78
        quality_text = ' / '.join(capture_quality.get('flags', [])) or 'NO GROSS ISSUE (NOT QUALITY CERTIFIED)'
        cv2.putText(output, f'PHOTO QUALITY: {quality_text}', (22, base_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                    (35, 190, 255) if capture_quality.get('blocks_decision') else (180, 200, 220), 1, cv2.LINE_AA)
        hidden = [f"{r['slot_id']}({r['stage']})" for r in (evidence_audit or {}).get('items', [])
                  if not r['displayed_as_candidate']]
        labels = ', '.join(hidden)
        if len(labels) > 145:
            labels = labels[:142] + '...'
        cv2.putText(output, f'RAW FLAGS NOT DRAWN ({len(hidden)}): {labels or "none"} | JSON: diagnostics',
                    (22, base_y + 29), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (180, 200, 220), 1, cv2.LINE_AA)
        unavailable = (provider_health or {}).get('unavailable_count', 0)
        missing_maps = len((provider_health or {}).get('patchcore_unavailable_slots', []))
        cv2.putText(output, f'UNAVAILABLE CHECKS: {unavailable} | PATCHCORE MISSING: {missing_maps}/{len(slots)}'
                    ' | EMPTY HEATMAP IS NOT A PASS', (22, base_y + 58), cv2.FONT_HERSHEY_SIMPLEX,
                    0.61, (35, 190, 255) if unavailable else (180, 200, 220), 1, cv2.LINE_AA)
    titles = (
        "1  REGISTERED ORIGINAL",
        "2  ALL-SLOT PATCHCORE HEATMAP (UNVERIFIED)",
        "3  EVIDENCE OVERLAY",
    )
    image_y = header_height + title_height
    for index, (panel, title) in enumerate(zip(panels, titles)):
        x = gap + index * (display_width + gap)
        cv2.putText(
            output,
            title,
            (x + 8, header_height + 29),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (230, 230, 232),
            2,
            cv2.LINE_AA,
        )
        output[image_y : image_y + display_height, x : x + display_width] = panel
    footer_y = image_y + display_height
    legend = "MISSING? | POSITION? | DIRECTION? | PINS? | SURFACE?     '?' = SUSPECT, NOT CONFIRMED"
    cv2.putText(
        output,
        legend,
        (22, footer_y + 31),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (225, 225, 225),
        2,
        cv2.LINE_AA,
    )
    compact = " | ".join(
        f"{item['slot_id']}:{'/'.join(display_codes(item['codes']))}" for item in candidates
    )
    if not compact:
        compact = "No selected defect candidates. Heatmap response is independent; this is not PASS."
    max_chars = max(70, total_width // 16)
    lines = [compact[index : index + max_chars] for index in range(0, len(compact), max_chars)][:2]
    for index, line in enumerate(lines):
        cv2.putText(
            output,
            line,
            (22, footer_y + 62 + index * 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (180, 190, 200),
            1,
            cv2.LINE_AA,
        )
    if boundary_items:
        summary = "VRM BOUNDARY: " + " | ".join(
            f"{slot}:" + ("/".join(display_codes(item.get("codes", []))) or
                          ("UNAVAILABLE" if "UNAVAILABLE" in item.get("reason", "") else "UNCERTAIN"))
            for slot, item in sorted(boundary_items.items())
        )
        cv2.putText(output, summary, (22, footer_y + 115), cv2.FONT_HERSHEY_SIMPLEX,
                    0.60, (225, 225, 225), 1, cv2.LINE_AA)
        cv2.putText(output, "POSITION / DIRECTION ARE ADVISORY CHECKS. UNCERTAIN != PASS",
                    (22, footer_y + 140), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (180, 190, 200), 1, cv2.LINE_AA)
    return output


def inspect_pcb(
    image_path: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path = DEFAULT_OUTPUT,
    presence_models: str | Path = DEFAULT_PRESENCE_MODELS,
    patchcore_models: str | Path = DEFAULT_PATCHCORE_MODELS,
    gpu_patchcore_models: str | Path | None = DEFAULT_GPU_PATCHCORE_MODELS,
    inductor_patchcore_models: str | Path | None = DEFAULT_INDUCTOR_PATCHCORE_MODELS,
    run_yolo: bool = True,
    run_patchcore: bool = True,
) -> dict[str, Any]:
    image_path = Path(image_path).expanduser().resolve()
    if not image_path.is_file():
        raise FileNotFoundError(image_path)
    source = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if source is None:
        raise RuntimeError(f"Cannot decode inspection image: {image_path}")

    output_root = Path(output_root).expanduser().resolve()
    run_dir = output_root / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir.mkdir(parents=True, exist_ok=False)
    geometry_cropper = FixedSlotCropper(Path(config_path))
    provider_config = geometry_cropper.config.get("provider_crop_config")
    cropper = (FixedSlotCropper(Path(provider_config)) if provider_config else geometry_cropper)
    # Learned inputs/references retain their fixed training frame. CAD geometry
    # is projected into that same registered board, never locally fitted.
    registered = cropper.register(source)
    capture_quality = assess_capture_quality(
        registered.image_bgr, cropper.reference, cropper.static_board_mask(),
        alignment_valid=(registered.alignment_reason == 'OK' and registered.alignment_score >=
                         float(cropper.config['global_alignment']['minimum_score'])),
    )
    aligned_path = run_dir / "aligned_board.png"
    cv2.imwrite(str(aligned_path), registered.image_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 2])
    slots = cropper.fixed_slots(registered.image_bgr)
    geometry_slots = geometry_cropper.fixed_slots(registered.image_bgr)
    if provider_config:
        if {s.slot_id for s in slots} != {s.slot_id for s in geometry_slots}:
            raise ValueError("Provider/CAD slot IDs differ")
        (run_dir / "geometry_reference.json").write_text(json.dumps({
            "provider_config": str(provider_config), "geometry_config": str(config_path),
            "geometry_config_sha256": hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
            "provider_config_sha256": hashlib.sha256(Path(provider_config).read_bytes()).hexdigest(),
            "slots": {s.slot_id: list(s.geometry) for s in geometry_slots},
            "note": "CAD centers for auxiliary pose; fixed original provider crops. No polygon containment authority."
        }, indent=2))
    boundary_items = VrmBoundaryAdvisory().inspect(
        registered.image_bgr, slots, enabled=run_yolo,
        alignment_valid=(registered.alignment_reason == "OK" and
                         registered.alignment_score >= float(cropper.config["global_alignment"]["minimum_score"])),
    )

    pin_debug_path: Path | None = None
    try:
        pin_reference = cv2.imread(str(DEFAULT_PIN_REFERENCE), cv2.IMREAD_COLOR)
        if pin_reference is None:
            raise RuntimeError(f"Cannot decode pin reference: {DEFAULT_PIN_REFERENCE}")
        pin_config = json.loads(DEFAULT_PIN_CONFIG.read_text(encoding="utf-8"))
        pin_layout = json.loads(DEFAULT_BOARD_LAYOUT.read_text(encoding="utf-8"))
        pin_report, pin_debug = inspect_package_legs(
            pin_reference,
            registered.image_bgr,
            pin_config,
            pin_layout,
        )
        gpu_pin_result = _gpu_pin_evidence(pin_report)
        pin_debug_path = run_dir / "gpu_pin_continuity_debug.png"
        cv2.imwrite(
            str(pin_debug_path), pin_debug, [cv2.IMWRITE_PNG_COMPRESSION, 2]
        )
    except Exception as exc:
        pin_report = {"status": "UNAVAILABLE", "reason": str(exc)}
        gpu_pin_result = CheckEvidence(
            "gpu_white_pin_continuity",
            "UNKNOWN",
            "UNAVAILABLE",
            0.0,
            f"GPU_PIN_INSPECTOR_UNAVAILABLE:{type(exc).__name__}",
            {},
            {},
        )

    crop_dir = run_dir / "fixed_slots"
    for slot in slots:
        destination = crop_dir / slot.component_key / f"{slot.slot_id}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(destination), slot.crop_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 2])

    yolo = YoloSegAuxiliary(run_yolo)
    yolo_items = yolo.inspect(aligned_path, run_dir / "yolo_auxiliary")
    if geometry_cropper.config.get("auxiliary_pose_use_active_slot_centers", False):
        yolo_items = bind_active_slot_centers(yolo_items, geometry_slots)
    presence = SlotPresenceClassifier(Path(presence_models))
    vrm_state_provider = VrmStateClassifier(Path(presence_models))
    vrm_seating_provider = VrmSeatingClassifier(Path(presence_models))
    vrm_context = inspect_context(registered.image_bgr, slots,
        registered.alignment_reason == 'OK' and registered.alignment_score >=
        float(cropper.config['global_alignment']['minimum_score']) and
        not capture_quality['blocks_decision'])

    patchcore_component_roots: dict[str, Path] = {}
    if run_patchcore:
        component_roots = {}
        if gpu_patchcore_models is not None:
            gpu_root = Path(gpu_patchcore_models).expanduser().resolve()
            if gpu_root.is_dir():
                component_roots["gpu"] = gpu_root
        if inductor_patchcore_models is not None:
            inductor_root = Path(inductor_patchcore_models).expanduser().resolve()
            if inductor_root.is_dir():
                component_roots["inductor"] = inductor_root
        patchcore_component_roots = component_roots
        patchcore_provider = ComponentPatchCoreInspector(
            Path(patchcore_models), component_model_roots=component_roots
        )
        patchcore_items = patchcore_provider.inspect(
            registered.image_bgr, slots, run_dir
        )
    else:
        patchcore_items = {
            slot.slot_id: PatchCoreEvidence(
                slot.slot_id,
                slot.component_key,
                "UNKNOWN",
                "DISABLED",
                None,
                "PATCHCORE_DISABLED",
                None,
                None,
                None,
                None,
                None,
            )
            for slot in slots
        }

    clearance = cropper.socket_clearance["component_types"]
    uncertainty = float(cropper.config["measurement_uncertainty"]["position_mm"])
    common_bias_limit = float(
        cropper.config["measurement_uncertainty"]["common_projection_bias_max_mm"]
    )
    common_pose_bias_mm, common_pose_bias_evidence = estimate_common_projection_bias(
        yolo_items,
        registered.image_bgr.shape,
        cropper.board_size_mm,
        maximum_bias_mm=common_bias_limit,
        diagnostic_only=bool(geometry_cropper.config.get("component_bias_diagnostic_only", False)),
    )
    slot_reports = []
    slot_reference_config = geometry_cropper.config.get(
        "auxiliary_pose_slot_reference_offsets_mm", {}
    )
    fixed_reference_health = validate_fixed_reference(
        geometry_cropper.config, PROJECT_DIR, [slot.slot_id for slot in slots], yolo.weights,
    ) if geometry_cropper.config.get('fixed_pose_reference') is not None else None
    if fixed_reference_health and fixed_reference_health['status'] != 'AVAILABLE':
        slot_reference_config = {}
    for slot in slots:
        vrm_state_result = (
            vrm_state_provider.inspect(slot, registered.image_bgr)
            if slot.component_type == "VRM"
            else None
        )
        presence_result = (
            _vrm_presence_evidence(vrm_state_result)
            if vrm_state_result is not None
            else presence.inspect(slot, registered.image_bgr)
        )
        vrm_seating_result = (
            vrm_seating_provider.inspect(
                slot,
                registered.image_bgr,
                non_empty_confidence=_vrm_non_empty_confidence(vrm_state_result),
            )
            if vrm_state_result is not None
            else None
        )
        tolerance = max(
            float(value)
            for value in clearance[slot.component_type]["center_tolerance_mm"]
        ) + uncertainty
        reference_entry = slot_reference_config.get(slot.slot_id, {})
        reference_offset = reference_entry.get("offset_mm", (0.0, 0.0))
        if not isinstance(reference_offset, (list, tuple)) or len(reference_offset) != 2:
            raise ValueError(
                "auxiliary_pose_slot_reference_offsets_mm."
                f"{slot.slot_id}.offset_mm must contain exactly two values"
            )
        pose_result = check_auxiliary_pose(
            yolo_items.get(slot.slot_id),
            slot.expected_axis_angle_deg,
            registered.image_bgr.shape,
            cropper.board_size_mm,
            position_tolerance_mm=tolerance,
            angle_tolerance_deg=3.0,
            common_bias_mm=common_pose_bias_mm,
            slot_reference_offset_mm=(
                float(reference_offset[0]), float(reference_offset[1])
            ),
            slot_reference_calibration_id=reference_entry.get("calibration_id"),
            # A round inductor segmentation mask has no meaningful long axis.
            # Its asymmetric black marker remains the independent direction check.
            check_axis_angle=slot.component_type != "Inductor",
        )
        if fixed_reference_health and fixed_reference_health['status'] != 'AVAILABLE':
            pose_result = CheckEvidence(
                'auxiliary_pose', 'UNKNOWN', 'INVALID', 0.0,
                'FIXED_POSE_REFERENCE_INVALID', {},
                {'reference_validation': fixed_reference_health},
            )
        orientation_result = _orientation_check(slot, cropper, vrm_state_result)
        patchcore_result = patchcore_items[slot.slot_id]
        stages = {
            "presence": _provider_dict(presence_result),
            "pose": _provider_dict(pose_result),
            "orientation": _provider_dict(orientation_result),
            "surface": _provider_dict(patchcore_result),
        }
        stages['orientation'] = abstain_direction_for_empty_slot(
            stages['presence'], stages['orientation'])
        if vrm_seating_result is not None:
            stages["seating"] = _provider_dict(vrm_seating_result)
        if slot.slot_id in boundary_items:
            stages["vrm_boundary"] = apply_vrm_socket_policy(boundary_items[slot.slot_id])
            boundary_items[slot.slot_id] = stages["vrm_boundary"]
        if slot.component_type == "GPU":
            stages["pins"] = _provider_dict(gpu_pin_result)
        elif slot.component_type == "HBM":
            stages["pins"] = _provider_dict(inspect_hbm_pins(
                slot.slot_id, slot.crop_bgr,
                stages["presence"].get("predicted_state", "UNKNOWN"),
                registered.alignment_reason == "OK" and registered.alignment_score >=
                float(cropper.config["global_alignment"]["minimum_score"]),
            ))
        required = REQUIRED_SLOT_STAGES | ({"pins"} if slot.component_type in {"GPU", "HBM"} else set())
        status, reason = fuse_required_stages(stages, required)
        smd01_outline_evidence = None
        if slot.slot_id == 'smd_capacitor_01' and pose_result.reason == 'YOLO_AUXILIARY_CANDIDATE_MISSING':
            from probe_smd01_independent_outline import measure as measure_smd01_body
            alignment_ok = (registered.alignment_reason == 'OK' and registered.alignment_score >=
                            float(cropper.config['global_alignment']['minimum_score']))
            smd01_outline_evidence = dict(valid=False, alignment_valid=alignment_ok,
                                          authority='ADVISORY_ONLY', reason='ALIGNMENT_INVALID')
            if alignment_ok:
                cx, cy, _, _ = slot.geometry
                ox, oy = int(cx)-90, int(cy)-70
                measurement = measure_smd01_body(registered.image_bgr[oy:oy+140,ox:ox+180])
                smd01_outline_evidence.update(measurement)
                smd01_outline_evidence['crop_origin_px'] = [ox,oy]
                if measurement['valid']:
                    smd01_outline_evidence['raw_y_mm'] = (
                        measurement['center'][1]+oy-cy
                    ) / (registered.image_bgr.shape[0]/cropper.board_size_mm[1])
        slot_reports.append(
            {
                "slot_id": slot.slot_id,
                "component_type": slot.component_type,
                "fixed_slot_geometry": list(next(s.geometry for s in geometry_slots if s.slot_id == slot.slot_id)),
                "fixed_slot_geometry_frame": "REGISTERED_BOARD_CXCYWH",
                "status": status,
                "reason": reason,
                "stages": stages,
                "smd01_outline_evidence": smd01_outline_evidence,
                "vrm_presence_context": vrm_context.get(slot.slot_id),
                "vrm_presence_state_summary": (
                    summarize_presence_state(asdict(vrm_state_result), vrm_context.get(slot.slot_id))
                    if vrm_state_result is not None else None
                ),
                "vrm_state_evidence": (
                    asdict(vrm_state_result) if vrm_state_result is not None else None
                ),
                "vrm_seating_evidence": (
                    asdict(vrm_seating_result)
                    if vrm_seating_result is not None
                    else None
                ),
            }
        )

    minimum_alignment = float(cropper.config["global_alignment"]["minimum_score"])
    alignment_valid = (
        registered.alignment_reason == "OK"
        and registered.alignment_score >= minimum_alignment
    )
    board_status, board_reason = fuse_board_result(
        slot_reports, alignment_valid, registered.alignment_reason, capture_quality,
        expected_slot_ids=[slot.slot_id for slot in slots])

    if capture_quality['blocks_decision']:
        for row in slot_reports:
            row['pre_quality_status'] = row['status']
            row['pre_quality_reason'] = row['reason']
            row['status'] = 'UNKNOWN'
            row['reason'] = 'CAPTURE_QUALITY_RECHECK; RAW_STAGE_EVIDENCE_PRESERVED'

    diagnostic_image = _render_slot_diagnostic(
        registered.image_bgr,
        slots,
        slot_reports,
        board_status,
        registered.alignment_score,
    )
    diagnostic_path = run_dir / "hybrid_slot_diagnostic.png"
    cv2.imwrite(
        str(diagnostic_path), diagnostic_image, [cv2.IMWRITE_PNG_COMPRESSION, 2]
    )
    advisory_candidates = build_advisory_candidates(slot_reports)
    pose_display_audit = build_pose_display_audit(slot_reports, advisory_candidates)
    evidence_audit = build_evidence_audit(slot_reports, advisory_candidates)
    provider_health = build_provider_health(slot_reports, yolo_status=yolo.last_status, yolo_reason=yolo.last_reason)
    full_evidence_map = _absolute_patchcore_evidence_map(
        registered.image_bgr, slots, patchcore_items
    )
    evidence_map = _gate_evidence_map_to_candidates(
        full_evidence_map, slots, advisory_candidates
    )
    heat_only, heatmap_overlay = _heatmap_images(
        registered.image_bgr, evidence_map
    )
    full_heat_only, full_heatmap_overlay = _heatmap_images(
        registered.image_bgr, full_evidence_map
    )
    report_image = _render_evidence_report(
        registered.image_bgr,
        full_heat_only,
        full_heatmap_overlay,
        slots,
        advisory_candidates,
        board_status,
        registered.alignment_score,
        boundary_items,
        pose_display_audit,
        capture_quality,
        evidence_audit,
        provider_health,
    )
    report_image_path = run_dir / "hybrid_report.png"
    cv2.imwrite(str(report_image_path), report_image, [cv2.IMWRITE_PNG_COMPRESSION, 2])
    heat_only_path = run_dir / "patchcore_excess_map.png"
    cv2.imwrite(
        str(heat_only_path), heat_only, [cv2.IMWRITE_PNG_COMPRESSION, 2]
    )
    heatmap_path = run_dir / "patchcore_heatmap_overlay.png"
    cv2.imwrite(
        str(heatmap_path),
        heatmap_overlay,
        [cv2.IMWRITE_PNG_COMPRESSION, 2],
    )
    full_heat_only_path = run_dir / "patchcore_unverified_full_excess_map.png"
    cv2.imwrite(
        str(full_heat_only_path), full_heat_only, [cv2.IMWRITE_PNG_COMPRESSION, 2]
    )
    full_heatmap_path = run_dir / "patchcore_unverified_full_heatmap_overlay.png"
    cv2.imwrite(
        str(full_heatmap_path),
        full_heatmap_overlay,
        [cv2.IMWRITE_PNG_COMPRESSION, 2],
    )

    report = {
        "schema_version": 1,
        "contract_id": "s22_hybrid_aoi_v1",
        "input_image": str(image_path),
        "input_sha256": _image_hash(image_path),
        "status": board_status,
        "reason": board_reason,
        "pose_display_audit": pose_display_audit,
        "capture_quality": capture_quality,
        "evidence_audit": evidence_audit,
        "provider_health": provider_health,
        "registration": {
            "alignment_score": registered.alignment_score,
            "minimum_alignment_score": minimum_alignment,
            "alignment_valid": alignment_valid,
            "alignment_reason": registered.alignment_reason,
            "input_was_canonical": registered.input_was_canonical,
            "source_homography": registered.source_homography.astype(float).tolist(),
            "alignment_warp": registered.alignment_warp.astype(float).tolist(),
        },
        "providers": {
            "presence": "per-component TorchScript slot classifier; VRM uses EMPTY/CORRECT/ROTATED state model",
            "vrm_seating": {
                "name": "S22 fixed-slot FLAT/SEATING classifier",
                "status": (
                    "ADVISORY_ONLY"
                    if vrm_seating_provider.model is not None
                    else (
                        "DEVELOPMENT_ONLY_NOT_DEPLOYED"
                        if vrm_seating_provider.metadata
                        else "UNAVAILABLE"
                    )
                ),
                "authority": "ADVISORY_ONLY",
                "runtime_enabled": bool(
                    (vrm_seating_provider.metadata or {}).get(
                        "runtime_enabled", False
                    )
                ),
                "candidate_status": (
                    (vrm_seating_provider.metadata or {}).get("candidate_status")
                ),
                "promotion_blocker": (
                    (vrm_seating_provider.metadata or {}).get("promotion_blocker")
                ),
                "model": str(vrm_seating_provider.model_path),
                "metadata": str(vrm_seating_provider.metadata_path),
                "flat_max_seating_probability": (
                    (vrm_seating_provider.metadata or {}).get(
                        "flat_max_seating_probability"
                    )
                ),
                "seating_min_probability": (
                    (vrm_seating_provider.metadata or {}).get(
                        "seating_min_probability"
                    )
                ),
                "fixed_regression_passed": bool(
                    (vrm_seating_provider.metadata or {}).get(
                        "fixed_regression_passed", False
                    )
                ),
                "restriction": (
                    "Requires strong non-empty VRM evidence and remains "
                    "ADVISORY_ONLY until fresh independent physical validation."
                ),
            },
            "yolo": {
                "name": "S22 YOLO segmentation auxiliary candidate",
                "status": yolo.last_status,
                "reason": yolo.last_reason,
                "candidate_slots": len(yolo_items),
                "common_projection_bias": common_pose_bias_evidence,
                "fixed_reference_validation": fixed_reference_health,
                "smd_transverse_pose_candidate_gate": {
                    "authority": "ADVISORY_ONLY",
                    "presence_confidence_min": CORROBORATED_PRESENT_CONFIDENCE_MIN,
                    "aux_outline_confidence_min": SMD_TRANSVERSE_POSE_AUX_CONFIDENCE_MIN,
                    "absolute_transverse_offset_mm_min": SMD_TRANSVERSE_POSE_OFFSET_MM,
                    "slot_specific_offset_mm_min": SMD_SLOT_TRANSVERSE_POSE_OFFSET_MM,
                    "note": (
                        "Long-axis and transverse offsets are kept separate; "
                        "no per-frame slot normalization is used."
                    ),
                },
                "slot_reference_offsets_mm": slot_reference_config,
                "vrm_calibrated_pose_candidate_gate": {
                    "authority": "ADVISORY_ONLY",
                    "non_empty_confidence_min": CORROBORATED_PRESENT_CONFIDENCE_MIN,
                    "aux_outline_confidence_min": VRM_CALIBRATED_POSE_AUX_CONFIDENCE_MIN,
                    "position_error_mm_min": VRM_CALIBRATED_POSE_CANDIDATE_MIN_MM,
                    "note": (
                        "The physical 0.75 mm pose tolerance is unchanged; "
                        "0.70--0.75 mm is exposed as a fail-safe recheck band."
                    ),
                },
            },
            "opencv": "local CLAHE dot/marker evidence",
            "gpu_white_pins": {
                "name": "golden-reference white-pin continuity",
                "status": gpu_pin_result.status,
                "authority": gpu_pin_result.authority,
                "reason": gpu_pin_result.reason,
                "scope": "GPU_ONLY",
                "hbm_excluded_reason": "current HBM pin provider has normal false positives",
            },
            "patchcore": {
                "name": "Anomalib 2.6 per-component memory bank",
                "status": ('DISABLED' if not run_patchcore else
                           'UNAVAILABLE' if len(provider_health['patchcore_unavailable_slots']) == len(slots) else
                           'PARTIAL_UNAVAILABLE' if provider_health['patchcore_unavailable_slots'] else 'ADVISORY_ONLY'),
                "authority": "ADVISORY_ONLY",
                "default_model_root": str(Path(patchcore_models).expanduser().resolve())
                if run_patchcore
                else None,
                "component_model_roots": {
                    key: str(value) for key, value in patchcore_component_roots.items()
                },
                "surface_only_candidate_suppressed": sorted(
                    SURFACE_ONLY_CANDIDATE_SUPPRESSED
                ),
                "smd_seating_candidate_gate": {
                    "authority": "ADVISORY_ONLY",
                    "presence_confidence_min": CORROBORATED_PRESENT_CONFIDENCE_MIN,
                    "aux_outline_confidence_min": SMD_SEATING_AUX_CONFIDENCE_MIN,
                    "aux_outline_confidence_max_exclusive": SMD_SEATING_AUX_CONFIDENCE_MAX,
                    "patchcore_score_min": SMD_SEATING_PATCHCORE_MIN,
                },
                "smd01_small_lip_candidate_rule": dict(SMD01_SMALL_LIP_RULE),
                "vrm05_pose_disagreement_policy": "Abstain from calibrated-centroid nomination when confident independent boundary is within reference uncertainty; raw pose and UNKNOWN preserved, not PASS.",
                "smd_lip_seating_candidate_rules": {
                    slot_id: {
                        "authority": "ADVISORY_ONLY",
                        **settings,
                    }
                    for slot_id, settings in SMD_LIP_SEATING_RULES.items()
                },
                "vrm_lip_seating_candidate_rules": {
                    slot_id: {
                        "authority": "ADVISORY_ONLY",
                        **settings,
                    }
                    for slot_id, settings in VRM_LIP_SEATING_RULES.items()
                },
                "vrm_low_confidence_rotation_candidate_gate": {
                    "authority": "ADVISORY_ONLY",
                    "raw_rotated_probability_min": VRM_ROTATION_RAW_CONFIDENCE_MIN,
                    "patchcore_score_min": VRM_ROTATION_PATCHCORE_MIN,
                    "non_empty_confidence_min": CORROBORATED_PRESENT_CONFIDENCE_MIN,
                },
                "vrm_outline_appearance_candidate_rules": {
                    slot_id: {
                        "authority": "ADVISORY_ONLY",
                        **settings,
                    }
                    for slot_id, settings in VRM_OUTLINE_APPEARANCE_RULES.items()
                },
                "suppression_reason": (
                    "SMD PatchCore cannot nominate a surface-only candidate. All component "
                    "maps remain visible in the all-slot report independently of candidate "
                    "selection. Separate candidate-gated images are retained for diagnostics. "
                    "Heatmap colour does not promote a candidate or grant decision authority."
                ),
            },
        },
        "slots": slot_reports,
        "advisory_candidates": {
            "authority": "ADVISORY_ONLY",
            "confirmed_defect": False,
            "count": len(advisory_candidates),
            "items": advisory_candidates,
        },
        "visualization": {
            "report": str(report_image_path),
            "report_heatmap_mode": "ALL_SLOT_FIXED_BASELINE_UNVERIFIED",
            "heatmap_is_confirmed_defect": False,
            "slot_status_diagnostic": str(diagnostic_path),
            "patchcore_excess_map": str(heat_only_path),
            "patchcore_heatmap_overlay": str(heatmap_path),
            "patchcore_unverified_full_excess_map": str(full_heat_only_path),
            "patchcore_unverified_full_heatmap_overlay": str(full_heatmap_path),
            "gpu_pin_continuity_debug": (
                str(pin_debug_path) if pin_debug_path is not None else None
            ),
            "aligned_board": str(aligned_path),
        },
        "runtime_action": (
            "PASS may continue; FAIL routes NG; UNKNOWN must recapture and then hold/NG_UNCERTAIN."
        ),
        "robot_command_sent": False,
        "conveyor_command_sent": False,
    }
    report_path = run_dir / "hybrid_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for source_path, name in (
        (report_path, "hybrid_report_latest.json"),
        (report_image_path, "hybrid_report_latest.png"),
        (diagnostic_path, "hybrid_slot_diagnostic_latest.png"),
        (heat_only_path, "hybrid_excess_map_latest.png"),
        (heatmap_path, "hybrid_heatmap_latest.png"),
        (full_heat_only_path, "hybrid_unverified_full_excess_map_latest.png"),
        (full_heatmap_path, "hybrid_unverified_full_heatmap_latest.png"),
    ):
        _atomic_symlink(source_path, output_root / name)
    print(f"HYBRID_STATUS={board_status}")
    print(f"HYBRID_REPORT={report_path}")
    print(f"HYBRID_VISUALIZATION={report_image_path}")
    print(f"HYBRID_SLOT_DIAGNOSTIC={diagnostic_path}")
    print(f"HYBRID_EXCESS_MAP={heat_only_path}")
    print(f"HYBRID_HEATMAP={heatmap_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--presence-models", type=Path, default=DEFAULT_PRESENCE_MODELS)
    parser.add_argument("--patchcore-models", type=Path, default=DEFAULT_PATCHCORE_MODELS)
    parser.add_argument(
        "--gpu-patchcore-models",
        type=Path,
        default=DEFAULT_GPU_PATCHCORE_MODELS,
    )
    parser.add_argument(
        "--inductor-patchcore-models",
        type=Path,
        default=DEFAULT_INDUCTOR_PATCHCORE_MODELS,
    )
    parser.add_argument("--skip-yolo", action="store_true")
    parser.add_argument("--skip-patchcore", action="store_true")
    args = parser.parse_args()
    inspect_pcb(
        args.image,
        config_path=args.config,
        output_root=args.output,
        presence_models=args.presence_models,
        patchcore_models=args.patchcore_models,
        gpu_patchcore_models=args.gpu_patchcore_models,
        inductor_patchcore_models=args.inductor_patchcore_models,
        run_yolo=not args.skip_yolo,
        run_patchcore=not args.skip_patchcore,
    )


if __name__ == "__main__":
    main()
