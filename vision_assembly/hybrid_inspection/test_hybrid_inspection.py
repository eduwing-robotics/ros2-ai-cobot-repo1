#!/usr/bin/env python3
"""Offline checks for the fixed-slot hybrid inspection contract."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import sys

import cv2
import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from main import (  # noqa: E402
    _absolute_patchcore_evidence_map,
    _gate_evidence_map_to_candidates,
    _gpu_pin_evidence,
    _orientation_check,
    _vrm_non_empty_confidence,
    _vrm_presence_evidence,
    build_advisory_candidates,
    fuse_required_stages,
)


def test_report_uses_full_heatmap_without_candidate_gate():
    import ast
    tree = ast.parse((MODULE_DIR / 'main.py').read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == '_render_evidence_report']
    assert len(calls) == 1
    assert [node.id for node in calls[0].args[1:3]] == ['full_heat_only', 'full_heatmap_overlay']


def test_empty_slot_direction_abstains_and_preserves_raw_signal():
    from main import abstain_direction_for_empty_slot
    for status in ('PASS', 'FAIL', 'UNKNOWN'):
        raw = dict(status=status, authority='ADVISORY_ONLY', confidence=.3,
                   reason='WHITE_DOT_AT_EXPECTED_CORNER')
        output = abstain_direction_for_empty_slot({'predicted_state': 'EMPTY'}, raw)
        assert output['status'] == 'UNKNOWN'
        assert output['confidence'] == 0
        assert output['raw_orientation_evidence'] == raw
        assert raw['status'] == status
    for state in ('PRESENT', 'CORRECT', 'ROTATED', 'UNKNOWN'):
        assert abstain_direction_for_empty_slot({'predicted_state': state}, raw) is raw


def test_vrm_socket_policy_removes_only_process_clearance():
    from main import apply_vrm_socket_policy
    for codes, expected in [(['RIGHT?'], []), (['RIGHT?', 'ROT?'], ['ROT?']),
                            (['RIGHT?', 'SEATING?'], ['SEATING?'])]:
        raw = dict(codes=codes, status='UNKNOWN', authority='ADVISORY_ONLY')
        result = apply_vrm_socket_policy(raw)
        assert result['codes'] == expected
        assert result['raw_process_clearance_evidence'] == raw
        assert result['status'] == 'UNKNOWN'
        assert not result['socket_seating_verified']
        assert raw['codes'] == codes
        assert apply_vrm_socket_policy(result) == result


def test_empty_candidate_report_preserves_supplied_heat_pixels():
    from main import _render_evidence_report
    original = np.zeros((1266, 1600, 3), np.uint8)
    heat = np.full_like(original, (10, 30, 200))
    candidates = []
    rendered = _render_evidence_report(original, heat, heat, [], candidates, 'UNKNOWN', .98)
    width = round(1600 * 690 / 1266)
    # Centre of the middle panel, away from labels and borders.
    assert tuple(rendered[146 + 345, 24 + width + width // 2]) == (10, 30, 200)
    assert candidates == []

from opencv_inspectors import (  # noqa: E402
    check_auxiliary_pose,
    check_gpu_hbm_dot,
    check_inductor_marker,
    clahe_gray,
    estimate_common_projection_bias,
)
from patchcore_inspector import PatchCoreEvidence  # noqa: E402
from preprocessor_and_cropper import (  # noqa: E402
    FixedSlot,
    FixedSlotCropper,
    VrmSeatingClassifier,
    VrmStateEvidence,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]


def test_pose_display_audit_preserves_raw_evidence():
    from copy import deepcopy
    from main import build_pose_display_audit
    rows = [{'slot_id': 'a', 'stages': {'pose': {'status': 'FAIL', 'authority': 'ADVISORY_ONLY'}}},
            {'slot_id': 'b', 'stages': {'pose': {'status': 'FAIL', 'authority': 'ADVISORY_ONLY'}}},
            {'slot_id': 'c', 'stages': {'pose': {'status': 'PASS'}}}]
    original = deepcopy(rows)
    audit = build_pose_display_audit(rows, [{'slot_id': 'b', 'codes': ['POSE?']}])
    assert audit['raw_pose_fail_count'] == 2
    assert audit['undisplayed_slots'] == ['a']
    assert rows == original
    assert build_pose_display_audit([], [])['undisplayed_count'] == 0


def test_inductor_model_promotion_does_not_change_gpu_model():
    from main import DEFAULT_INDUCTOR_PATCHCORE_MODELS, DEFAULT_GPU_PATCHCORE_MODELS
    assert DEFAULT_GPU_PATCHCORE_MODELS == PROJECT_DIR / 'runtime/inspection/patchcore/pcb_components_strict_v4'
    assert DEFAULT_INDUCTOR_PATCHCORE_MODELS != DEFAULT_GPU_PATCHCORE_MODELS
    assert DEFAULT_INDUCTOR_PATCHCORE_MODELS == PROJECT_DIR / 'runtime/inspection/patchcore/inductor_morning_candidate_20260907/models'


def test_missing_display_precedence_preserves_raw_codes():
    from main import display_codes
    raw = ['MISSING?', 'DIR?', 'POSE?', 'PINS?', 'SURFACE?']
    original = raw.copy()
    assert display_codes(raw) == ['MISSING?']
    assert raw == original
    assert display_codes(['DIR?', 'POSE?']) == ['DIRECTION?', 'POSITION?']


def test_gpu_dot_excludes_neighbour_in_padding():
    crop = np.zeros((400, 200, 3), np.uint8)
    cv2.circle(crop, (160, 75), 7, (255, 255, 255), -1)
    cv2.circle(crop, (20, 75), 8, (255, 255, 255), -1)
    evidence = check_gpu_hbm_dot(crop, slot_inset_fraction=.22/1.44)
    assert evidence.status == 'FAIL'
    assert evidence.measured['winner'] == 'upper_right'
    assert evidence.measured['selected_corner_components']['upper_left'] is None
    assert evidence.authority == 'ADVISORY_ONLY'


def test_gpu_saved_orientation_regression():
    import pytest
    root = PROJECT_DIR / 'runtime/inspection/hybrid_fixed_slot'
    cases = [('20260906_184959_868834', 'FAIL'),
             ('20260906_183337_961766', 'PASS'),
             ('20260906_182517_135335', 'PASS')]
    for name, expected in cases:
        path = root / name / 'fixed_slots/gpu/ai_gpu.png'
        if not path.exists():
            pytest.skip('Local capture fixtures unavailable')
        result = check_gpu_hbm_dot(cv2.imread(str(path)), slot_inset_fraction=.22/1.44)
        assert result.status == expected


def test_fixed_layout_always_exports_25_slots() -> None:
    cropper = FixedSlotCropper(
        PROJECT_DIR / "vision_assembly/config/full_board_inspection.json"
    )
    slots = cropper.fixed_slots(np.zeros((1266, 1600, 3), np.uint8))
    assert len(slots) == 25
    assert Counter(slot.component_type for slot in slots) == {
        "GPU": 1,
        "HBM": 8,
        "Power Module": 4,
        "VRM": 5,
        "Inductor": 2,
        "SMD Capacitor": 5,
    }


def test_clahe_is_local_grayscale_only() -> None:
    image = np.full((80, 120, 3), 90, np.uint8)
    image[:, 60:] = 105
    output = clahe_gray(image)
    assert output.shape == image.shape[:2]
    assert output.dtype == np.uint8


def test_white_dot_distinguishes_zero_and_180_orientation() -> None:
    normal = np.full((240, 160, 3), 30, np.uint8)
    cv2.circle(normal, (26, 210), 12, (245, 245, 245), -1)
    reversed_image = np.full_like(normal, 30)
    cv2.circle(reversed_image, (134, 30), 12, (245, 245, 245), -1)
    assert check_gpu_hbm_dot(normal).status == "PASS"
    assert check_gpu_hbm_dot(reversed_image).status == "FAIL"


def test_hbm_dot_beats_nearby_smaller_end_pin() -> None:
    image = np.full((240, 160, 3), 30, np.uint8)
    cv2.circle(image, (27, 207), 12, (245, 245, 245), -1)
    for y in (31, 68, 105, 142, 179, 216):
        cv2.circle(image, (136, y), 10, (245, 245, 245), -1)
    result = check_gpu_hbm_dot(image, suppress_pin_columns=True)
    assert result.status == "PASS"
    assert result.measured["winner"] == "lower_left"


def test_inductor_black_marker_direction() -> None:
    image = np.full((220, 220, 3), 25, np.uint8)
    cv2.circle(image, (110, 110), 72, (235, 235, 235), -1)
    cv2.circle(image, (72, 110), 16, (20, 20, 20), -1)
    result = check_inductor_marker(
        image, expected_angle_deg=180.0, tolerance_deg=30.0
    )
    # A round dot locates the side but cannot certify the new fine-axis check.
    assert result.status == "UNKNOWN"
    assert result.reason == "BLACK_MARKER_FINE_AXIS_UNCERTAIN"
    assert result.measured["angle_error_deg"] < 10.0


def _pose_item(center, expected, confidence=0.9):
    return {
        "confidence": confidence,
        "evidence": {
            "present": True,
            "center_px": list(center),
            "expected_center_px": list(expected),
            "long_axis_angle_deg_undirected": 90.0,
        },
    }


def test_common_projection_bias_removes_only_shared_offset() -> None:
    items = {
        f"hbm_{index:02d}": _pose_item(
            (100.0 + index + 10.0, 200.0 + index - 8.0),
            (100.0 + index, 200.0 + index),
        )
        for index in range(1, 9)
    }
    bias, evidence = estimate_common_projection_bias(
        items, (1000, 1000, 3), (100.0, 100.0), maximum_bias_mm=1.5
    )
    assert evidence["applied"] is True
    assert np.allclose(bias, (1.0, -0.8))
    result = check_auxiliary_pose(
        items["hbm_01"], 90.0, (1000, 1000, 3), (100.0, 100.0),
        position_tolerance_mm=0.75, common_bias_mm=bias,
    )
    assert result.status == "PASS"
    assert result.measured["position_error_mm"] < 1e-6


def test_diagnostic_bias_keeps_shared_component_displacement():
    items = {f"hbm_{i:02d}": _pose_item((110.,192.), (100.,200.)) for i in range(8)}
    bias, evidence = estimate_common_projection_bias(
        items, (1000,1000,3), (100.,100.), diagnostic_only=True)
    assert bias == (0.,0.)
    assert evidence['applied'] is False
    assert np.allclose(evidence['estimated_bias_mm'], (1.,-.8))
    result = check_auxiliary_pose(items['hbm_00'],90.,(1000,1000,3),(100.,100.),
                                  position_tolerance_mm=.75, common_bias_mm=bias)
    assert result.status == 'FAIL'


def test_slot_reference_offset_is_removed_after_common_bias() -> None:
    item = _pose_item((521.0, 496.0), (500.0, 500.0))
    result = check_auxiliary_pose(
        item,
        90.0,
        (1000, 1000, 3),
        (100.0, 100.0),
        position_tolerance_mm=0.75,
        common_bias_mm=(1.0, -0.5),
        slot_reference_offset_mm=(1.1, 0.1),
        slot_reference_calibration_id="unit_test_reference",
    )
    assert result.status == "PASS"
    assert np.allclose(result.measured["offset_mm"], (0.0, 0.0))
    assert result.measured["slot_reference_calibration_id"] == "unit_test_reference"


def test_pm01_reference_accepts_verified_position_and_keeps_large_shift() -> None:
    reference = (0.7629, 0.0062)
    accepted = check_auxiliary_pose(
        _pose_item((512.4146, 497.1574), (500.0, 500.0), confidence=0.30),
        90.0,
        (1000, 1000, 3),
        (100.0, 100.0),
        position_tolerance_mm=0.75,
        slot_reference_offset_mm=reference,
    )
    displaced = check_auxiliary_pose(
        _pose_item((531.2740, 504.7633), (500.0, 500.0), confidence=0.60),
        90.0,
        (1000, 1000, 3),
        (100.0, 100.0),
        position_tolerance_mm=0.75,
        slot_reference_offset_mm=reference,
    )
    assert accepted.status == "PASS"
    assert accepted.measured["position_error_mm"] < 0.60
    assert displaced.status == "FAIL"
    assert displaced.measured["position_error_mm"] > 2.3


def test_auxiliary_pose_exports_longitudinal_and_transverse_offsets() -> None:
    item = _pose_item((509.0, 492.0), (500.0, 500.0))
    result = check_auxiliary_pose(
        item,
        90.0,
        (1000, 1000, 3),
        (100.0, 100.0),
        position_tolerance_mm=2.0,
    )
    assert np.isclose(result.measured["longitudinal_offset_mm"], -0.8)
    assert np.isclose(result.measured["transverse_offset_mm"], -0.9)
    assert np.isclose(result.measured["absolute_transverse_offset_mm"], 0.9)


def test_inductor_pose_ignores_circular_mask_axis() -> None:
    item = _pose_item((500.0, 500.0), (500.0, 500.0))
    result = check_auxiliary_pose(
        item, 0.0, (1000, 1000, 3), (100.0, 100.0),
        check_axis_angle=False,
    )
    assert result.status == "PASS"
    assert result.measured["axis_angle_error_deg"] == 90.0
    assert result.measured["axis_angle_checked"] is False


def test_fusion_is_fail_safe() -> None:
    passing = {
        name: {"status": "PASS", "authority": "AUTHORITATIVE"}
        for name in ("presence", "pose", "orientation", "surface")
    }
    assert fuse_required_stages(passing)[0] == "PASS"
    passing["surface"] = {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"}
    assert fuse_required_stages(passing)[0] == "UNKNOWN"
    passing["presence"] = {"status": "FAIL", "authority": "AUTHORITATIVE"}
    assert fuse_required_stages(passing)[0] == "FAIL"


def test_advisory_candidates_do_not_claim_confirmed_defect() -> None:
    row = {
        "slot_id": "hbm_03",
        "stages": {
            "presence": {"status": "UNKNOWN", "authority": "UNAVAILABLE"},
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.8,
                "measured": {
                    "position_error_mm": 1.0,
                    "axis_angle_error_deg": 0.0,
                },
                "limits": {
                    "position_tolerance_mm": 0.75,
                    "angle_tolerance_deg": 3.0,
                },
            },
            "orientation": {"status": "FAIL", "authority": "ADVISORY_ONLY"},
            "surface": {
                "status": "UNKNOWN", "authority": "ADVISORY_ONLY",
                "score": 0.8, "fail_min": 0.6,
            },
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["DIR?", "POSE?", "SURFACE?"]
    assert candidates[0]["authority"] == "ADVISORY_ONLY"
    assert candidates[0]["confirmed_defect"] is False


def test_patchcore_map_uses_absolute_normal_baseline() -> None:
    aligned = np.zeros((100, 100, 3), np.uint8)
    slot = FixedSlot(
        "hbm_01",
        "HBM",
        "hbm",
        (50.0, 50.0, 30.0, 40.0),
        0.0,
        np.zeros((40, 30, 3), np.uint8),
        (35, 30),
        (30, 40),
    )
    uncalibrated = PatchCoreEvidence(
        "hbm_01", "hbm", "UNKNOWN", "ADVISORY_ONLY", 0.8,
        "CONTROLLED_DEFECT_THRESHOLD_MISSING", None, None, 0.3, 0.2,
        np.full((16, 16), 0.5, np.float32),
    )
    calibrated_above = PatchCoreEvidence(
        "hbm_01", "hbm", "UNKNOWN", "ADVISORY_ONLY", 0.8,
        "TEST", 0.3, 0.6, 0.3, 0.2, np.full((16, 16), 0.5, np.float32),
    )
    assert float(_absolute_patchcore_evidence_map(
        aligned, [slot], {slot.slot_id: uncalibrated}
    ).max()) > 0.9
    assert float(_absolute_patchcore_evidence_map(
        aligned, [slot], {slot.slot_id: calibrated_above}
    ).max()) > 0.9


def test_operator_heatmap_keeps_only_independently_flagged_slots() -> None:
    evidence = np.ones((100, 100), np.float32)
    slots = [
        FixedSlot(
            "hbm_01", "HBM", "hbm", (25.0, 50.0, 30.0, 40.0), 0.0,
            np.zeros((40, 30, 3), np.uint8), (10, 30), (30, 40),
        ),
        FixedSlot(
            "hbm_02", "HBM", "hbm", (75.0, 50.0, 30.0, 40.0), 0.0,
            np.zeros((40, 30, 3), np.uint8), (60, 30), (30, 40),
        ),
    ]
    gated = _gate_evidence_map_to_candidates(
        evidence, slots, [{"slot_id": "hbm_02"}]
    )
    assert float(gated[50, 25]) == 0.0
    assert float(gated[50, 75]) == 1.0


def test_smd_map_is_available_when_presence_or_pose_flags_its_slot() -> None:
    aligned = np.zeros((100, 100, 3), np.uint8)
    slot = FixedSlot(
        "smd_capacitor_05", "SMD Capacitor", "smd_capacitor",
        (50.0, 50.0, 20.0, 30.0), 90.0,
        np.zeros((30, 20, 3), np.uint8), (40, 35), (20, 30),
    )
    evidence = PatchCoreEvidence(
        slot.slot_id, slot.component_key, "UNKNOWN", "ADVISORY_ONLY", 0.58,
        "CONTROLLED_DEFECT_THRESHOLD_MISSING", None, None, 0.0, 0.01,
        np.full((16, 16), 0.20, np.float32),
    )
    full = _absolute_patchcore_evidence_map(
        aligned, [slot], {slot.slot_id: evidence}
    )
    gated = _gate_evidence_map_to_candidates(
        full, [slot], [{"slot_id": slot.slot_id}]
    )
    assert float(full.max()) > 0.0
    assert float(gated.max()) > 0.0


def test_significant_power_module_displacement_is_not_hidden() -> None:
    row = {
        "slot_id": "power_module_01",
        "component_type": "Power Module",
        "stages": {
            "presence": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.67,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 1.33,
                    "axis_angle_error_deg": 0.0,
                },
                "limits": {"position_tolerance_mm": 0.75},
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["POSE?"]


def test_repeated_normal_power_module_residual_is_not_shown_as_pose_candidate() -> None:
    row = {
        "slot_id": "power_module_02",
        "component_type": "Power Module",
        "stages": {
            "presence": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.66,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 1.224,
                    "axis_angle_error_deg": 0.13,
                },
                "limits": {"position_tolerance_mm": 0.75},
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    assert build_advisory_candidates([row]) == []


def test_large_power_module_shift_survives_auxiliary_confidence_drop() -> None:
    row = {
        "slot_id": "power_module_02",
        "component_type": "Power Module",
        "stages": {
            "presence": {
                "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY",
                "predicted_state": "PRESENT",
                "confidence": 0.996,
            },
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.138,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 1.464,
                    "axis_angle_error_deg": 0.40,
                },
                "limits": {"position_tolerance_mm": 0.75},
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["slot_id"] == "power_module_02"
    assert candidates[0]["codes"] == ["POSE?"]


def test_large_low_confidence_power_module_mask_without_presence_is_hidden() -> None:
    row = {
        "slot_id": "power_module_02",
        "component_type": "Power Module",
        "stages": {
            "presence": {
                "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY",
                "predicted_state": "UNKNOWN",
                "confidence": 0.40,
            },
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.138,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 1.464,
                    "axis_angle_error_deg": 0.40,
                },
                "limits": {"position_tolerance_mm": 0.75},
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    assert build_advisory_candidates([row]) == []


def test_displaced_power_module_body_overrides_weak_empty_cause_label() -> None:
    row = {
        "slot_id": "power_module_01",
        "component_type": "Power Module",
        "stages": {
            "presence": {
                "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY",
                "predicted_state": "EMPTY",
                "confidence": 0.762,
                "reason": "LOW_CONFIDENCE",
            },
            "pose": {
                "status": "FAIL",
                "authority": "ADVISORY_ONLY",
                "confidence": 0.598,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 3.219,
                    "axis_angle_error_deg": 0.40,
                    "mask_area_px": 98_821.0,
                },
                "limits": {
                    "position_tolerance_mm": 0.75,
                    "angle_tolerance_deg": 3.0,
                },
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["POSE?"]
    assert candidates[0]["primary_code"] == "POSE?"


def test_power_module_empty_remains_missing_without_displaced_body_evidence() -> None:
    row = {
        "slot_id": "power_module_01",
        "component_type": "Power Module",
        "stages": {
            "presence": {
                "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY",
                "predicted_state": "EMPTY",
                "confidence": 0.762,
                "reason": "LOW_CONFIDENCE",
            },
            "pose": {
                "status": "FAIL",
                "authority": "ADVISORY_ONLY",
                "confidence": 0.598,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 3.219,
                    "axis_angle_error_deg": 0.40,
                    "mask_area_px": 8_821.0,
                },
                "limits": {
                    "position_tolerance_mm": 0.75,
                    "angle_tolerance_deg": 3.0,
                },
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["primary_code"] == "MISSING?"
    assert candidates[0]["codes"] == ["MISSING?", "POSE?"]


def test_borderline_inductor_position_does_not_create_display_noise() -> None:
    row = {
        "slot_id": "inductor_02",
        "component_type": "Inductor",
        "stages": {
            "presence": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.52,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 0.758,
                    "axis_angle_error_deg": 90.0,
                    "axis_angle_checked": False,
                },
                "limits": {"position_tolerance_mm": 0.75},
            },
            "orientation": {"status": "PASS", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    assert build_advisory_candidates([row]) == []


def test_high_confidence_hbm_sub_resolution_pose_overrun_is_hidden() -> None:
    row = {
        "slot_id": "hbm_06",
        "component_type": "HBM",
        "stages": {
            "presence": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.94,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 0.769,
                    "axis_angle_error_deg": 0.0,
                    "axis_angle_checked": True,
                },
                "limits": {
                    "position_tolerance_mm": 0.75,
                    "angle_tolerance_deg": 3.0,
                },
            },
            "orientation": {"status": "PASS", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    assert build_advisory_candidates([row]) == []


def test_high_confidence_hbm_meaningful_pose_overrun_is_shown() -> None:
    row = {
        "slot_id": "hbm_06",
        "component_type": "HBM",
        "stages": {
            "presence": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.94,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": 0.95,
                    "axis_angle_error_deg": 0.0,
                    "axis_angle_checked": True,
                },
                "limits": {
                    "position_tolerance_mm": 0.75,
                    "angle_tolerance_deg": 3.0,
                },
            },
            "orientation": {"status": "PASS", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["POSE?"]


def test_gpu_pin_failure_becomes_advisory_candidate() -> None:
    pin = _gpu_pin_evidence(
        {
            "components": [
                {
                    "slot_id": "ai_gpu",
                    "status": "FAIL",
                    "local_match_score": 0.97,
                    "sides": [
                        {
                            "side": "right",
                            "status": "FAIL",
                            "reason": "LEG_PATTERN_DEFECT",
                            "missing_points_px": [[967, 356]],
                        }
                    ],
                }
            ]
        }
    )
    assert pin.status == "FAIL"
    assert pin.authority == "ADVISORY_ONLY"
    row = {
        "slot_id": "ai_gpu",
        "component_type": "GPU",
        "stages": {
            "presence": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "pose": {"status": "PASS", "authority": "ADVISORY_ONLY"},
            "orientation": {"status": "PASS", "authority": "ADVISORY_ONLY"},
            "pins": pin.to_dict(),
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["PINS?"]


def test_unverified_empty_prediction_is_visible_as_missing_candidate() -> None:
    row = {
        "slot_id": "smd_capacitor_05",
        "stages": {
            "presence": {
                "predicted_state": "EMPTY", "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY", "reason": "UNVERIFIED_EMPTY_CANDIDATE",
            },
            "pose": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["MISSING?"]


def test_large_smd_angle_candidate_survives_low_detector_confidence() -> None:
    row = {
        "slot_id": "smd_capacitor_03",
        "component_type": "SMD Capacitor",
        "stages": {
            "presence": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "pose": {
                "status": "FAIL", "authority": "ADVISORY_ONLY", "confidence": 0.18,
                "measured": {"axis_angle_error_deg": 24.4},
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["POSE?"]


def _smd_position_row(
    position_error: float,
    pose_confidence: float,
    offset_mm: tuple[float, float],
    presence_confidence: float = 0.999,
) -> dict:
    return {
        "slot_id": "smd_capacitor_04",
        "component_type": "SMD Capacitor",
        "stages": {
            "presence": {
                "predicted_state": "PRESENT",
                "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY",
                "confidence": presence_confidence,
            },
            "pose": {
                "status": "FAIL",
                "authority": "ADVISORY_ONLY",
                "confidence": pose_confidence,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": position_error,
                    "offset_mm": list(offset_mm),
                    "axis_angle_error_deg": 0.0,
                    "axis_angle_checked": True,
                },
                "limits": {
                    "position_tolerance_mm": 0.75,
                    "expected_axis_angle_deg": 90.0,
                    "angle_tolerance_deg": 3.0,
                },
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
        },
    }


def test_confirmed_smd_sideways_socket_exit_is_shown() -> None:
    candidates = build_advisory_candidates(
        [_smd_position_row(0.926, 0.293, (0.895, -0.239))]
    )
    assert candidates[0]["codes"] == ["POSE?"]
    assert "SMD_TRANSVERSE_OFFSET" in candidates[0]["details"][0]


def test_smd01_confirmed_normal_margin_preserves_raw_status():
    row = _smd_position_row(1.302, 0.381, (0.858, 0.98))
    row['slot_id'] = 'smd_capacitor_01'
    assert build_advisory_candidates([row]) == []
    assert row['stages']['pose']['status'] == 'FAIL'
    row['stages']['pose']['measured']['offset_mm'][0] = .91
    assert 'POSE?' in build_advisory_candidates([row])[0]['codes']


def test_normal_smd_long_axis_detector_bias_is_hidden() -> None:
    assert build_advisory_candidates(
        [_smd_position_row(0.890, 0.382, (0.369, -0.810))]
    ) == []


def test_largest_verified_normal_smd_transverse_offset_is_hidden() -> None:
    assert build_advisory_candidates(
        [_smd_position_row(0.832, 0.212, (0.815, -0.165))]
    ) == []


def test_smd_transverse_candidate_requires_independent_presence() -> None:
    assert build_advisory_candidates(
        [_smd_position_row(0.926, 0.293, (0.895, -0.239), 0.50)]
    ) == []


def _smd_seating_row(
    surface_score: float,
    pose_confidence: float = 0.195,
    slot_id: str = "smd_capacitor_03",
    mask_area_px: float | None = None,
) -> dict:
    return {
        "slot_id": slot_id,
        "component_type": "SMD Capacitor",
        "stages": {
            "presence": {
                "predicted_state": "PRESENT",
                "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY",
                "confidence": 0.999,
            },
            "pose": {
                "status": "PASS",
                "authority": "ADVISORY_ONLY",
                "confidence": pose_confidence,
                "measured": {
                    "position_error_mm": 0.552,
                    "axis_angle_error_deg": 0.0,
                    "mask_area_px": mask_area_px,
                },
                "limits": {
                    "position_tolerance_mm": 0.75,
                    "angle_tolerance_deg": 3.0,
                },
            },
            "orientation": {"status": "UNKNOWN", "authority": "ADVISORY_ONLY"},
            "surface": {
                "component_key": "smd_capacitor",
                "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY",
                "score": surface_score,
                "fail_min": None,
            },
        },
    }


def test_corroborated_smd_lift_is_shown_as_seating_candidate() -> None:
    candidates = build_advisory_candidates([_smd_seating_row(0.399)])
    assert candidates[0]["codes"] == ["SEATING?"]
    assert candidates[0]["authority"] == "ADVISORY_ONLY"


def test_normal_smd_patchcore_response_does_not_trigger_seating_candidate() -> None:
    assert build_advisory_candidates([_smd_seating_row(0.146)]) == []


def test_smd_surface_score_without_weak_outline_stays_suppressed() -> None:
    assert build_advisory_candidates(
        [_smd_seating_row(0.399, pose_confidence=0.45)]
    ) == []


def test_smd04_lip_seating_with_large_outline_and_patchcore_is_shown() -> None:
    candidates = build_advisory_candidates(
        [
            _smd_seating_row(
                0.188,
                pose_confidence=0.710,
                slot_id="smd_capacitor_04",
                mask_area_px=4809.5,
            )
        ]
    )
    assert candidates[0]["codes"] == ["SEATING?"]
    assert "SMD_LIP_SEATING_CORROBORATED" in candidates[0]["details"][0]
    assert candidates[0]["authority"] == "ADVISORY_ONLY"


def test_smd02_lip_seating_with_large_mask_and_patchcore_is_shown() -> None:
    candidates = build_advisory_candidates(
        [
            _smd_seating_row(
                0.305,
                pose_confidence=0.265,
                slot_id="smd_capacitor_02",
                mask_area_px=4623.5,
            )
        ]
    )
    assert candidates[0]["codes"] == ["SEATING?"]
    assert "SMD_LIP_SEATING_CORROBORATED" in candidates[0]["details"][0]


def test_verified_normal_smd02_envelope_does_not_trigger_lip_seating() -> None:
    assert build_advisory_candidates(
        [
            _smd_seating_row(
                0.0,
                pose_confidence=0.340,
                slot_id="smd_capacitor_02",
                mask_area_px=4222.5,
            )
        ]
    ) == []


def test_verified_normal_smd_envelope_does_not_trigger_lip_seating() -> None:
    assert build_advisory_candidates(
        [
            _smd_seating_row(
                0.1461,
                pose_confidence=0.4741,
                slot_id="smd_capacitor_04",
                mask_area_px=4490.0,
            )
        ]
    ) == []


def test_smd01_area_and_patchcore_without_position_is_ambiguous() -> None:
    candidates = build_advisory_candidates(
        [
            _smd_seating_row(
                0.155,
                pose_confidence=0.264,
                slot_id="smd_capacitor_01",
                mask_area_px=4574.0,
            )
        ]
    )
    assert candidates == []


def test_verified_normal_smd01_envelope_does_not_trigger_lip_seating() -> None:
    assert build_advisory_candidates(
        [
            _smd_seating_row(
                0.0038,
                pose_confidence=0.311,
                slot_id="smd_capacitor_01",
                mask_area_px=4215.0,
            )
        ]
    ) == []


def test_smd01_confirmed_normal_area_response_is_retained_as_unknown() -> None:
    row = _smd_seating_row(0.1073495, pose_confidence=0.5003345,
                           slot_id="smd_capacitor_01", mask_area_px=4486.0)
    row["stages"]["pose"]["measured"]["raw_offset_mm"] = [1.16207, -0.66697]
    assert build_advisory_candidates([row]) == []
    evidence = row["smd01_lip_evidence_review"]
    assert evidence["area_appearance_trigger"]
    assert not evidence["position_corroborated"]
    assert evidence["status"] == "UNKNOWN"
    assert evidence["reason"] == "SMD01_MICRO_SEATING_DEFERRED"


def test_smd01_micro_seating_scope_retains_raw_trigger_without_candidate() -> None:
    from copy import deepcopy
    row = _smd_seating_row(0.15459, pose_confidence=0.46992,
                           slot_id="smd_capacitor_01", mask_area_px=4711.5)
    row["stages"]["pose"]["measured"]["raw_offset_mm"] = [0.84394, 0.68797]
    original_stages = deepcopy(row["stages"])
    assert build_advisory_candidates([row]) == []
    assert row["smd01_lip_evidence_review"]["position_corroborated"]
    assert row["smd01_lip_evidence_review"]["raw_candidate_triggers"]["signed_position_and_surface"]
    assert row["smd01_lip_evidence_review"]["status"] == "UNKNOWN"
    assert row["stages"] == original_stages


def test_smd05_lip_seating_with_large_mask_and_patchcore_is_shown() -> None:
    candidates = build_advisory_candidates(
        [
            _smd_seating_row(
                0.341,
                pose_confidence=0.547,
                slot_id="smd_capacitor_05",
                mask_area_px=4811.0,
            )
        ]
    )
    assert candidates[0]["codes"] == ["SEATING?"]
    assert "SMD_LIP_SEATING_CORROBORATED" in candidates[0]["details"][0]


def test_verified_normal_smd05_envelope_does_not_trigger_lip_seating() -> None:
    assert build_advisory_candidates(
        [
            _smd_seating_row(
                0.0,
                pose_confidence=0.384,
                slot_id="smd_capacitor_05",
                mask_area_px=4438.0,
            )
        ]
    ) == []


def test_lip_seating_rule_is_not_generalized_to_unvalidated_smd_slots() -> None:
    assert build_advisory_candidates(
        [
            _smd_seating_row(
                0.273,
                pose_confidence=0.726,
                slot_id="smd_capacitor_99",
                mask_area_px=4866.0,
            )
        ]
    ) == []


def _vrm_lip_seating_row(
    *,
    surface_score: float,
    transverse_offset_mm: float,
    mask_area_px: float,
    pose_confidence: float = 0.30,
    presence_confidence: float = 0.95,
    empty_probability: float = 0.01,
    raw_state: str = "CORRECT",
    slot_id: str = "vrm_01",
) -> dict:
    return {
        "slot_id": slot_id,
        "component_type": "VRM",
        "vrm_state_evidence": {
            "raw_predicted_state": raw_state,
            "probabilities": {
                "EMPTY": empty_probability,
                "CORRECT": 1.0 - empty_probability if raw_state == "CORRECT" else 0.0,
                "ROTATED": 1.0 - empty_probability if raw_state == "ROTATED" else 0.0,
            },
        },
        "stages": {
            "presence": {
                "predicted_state": raw_state,
                "status": "PASS",
                "authority": "ADVISORY_ONLY",
                "confidence": presence_confidence,
            },
            "pose": {
                "status": "FAIL",
                "authority": "ADVISORY_ONLY",
                "confidence": pose_confidence,
                "reason": "AUXILIARY_POSE_OUTSIDE_LIMIT",
                "measured": {
                    "position_error_mm": transverse_offset_mm,
                    "absolute_transverse_offset_mm": transverse_offset_mm,
                    "axis_angle_error_deg": 0.0,
                    "axis_angle_checked": True,
                    "mask_area_px": mask_area_px,
                },
                "limits": {
                    "position_tolerance_mm": 0.75,
                    "angle_tolerance_deg": 3.0,
                },
            },
            "orientation": {"status": "PASS", "authority": "ADVISORY_ONLY"},
            "surface": {
                "component_key": "vrm",
                "status": "UNKNOWN",
                "authority": "ADVISORY_ONLY",
                "score": surface_score,
                "fail_min": None,
            },
        },
    }


def test_vrm01_lip_seating_requires_corroborated_geometry_and_patchcore() -> None:
    candidates = build_advisory_candidates(
        [_vrm_lip_seating_row(
            surface_score=0.801,
            transverse_offset_mm=0.761,
            mask_area_px=22_032.5,
        )]
    )
    assert candidates[0]["codes"] == ["SEATING?"]
    assert "VRM01_LIP_SEATING_CORROBORATED" in candidates[0]["details"][0]
    assert "NON_EMPTY_0.990" in candidates[0]["details"][0]
    assert candidates[0]["authority"] == "ADVISORY_ONLY"


def test_vrm01_high_normal_patchcore_score_alone_is_not_seating() -> None:
    assert build_advisory_candidates(
        [_vrm_lip_seating_row(
            surface_score=0.768,
            transverse_offset_mm=0.12,
            mask_area_px=21_585.0,
        )]
    ) == []


def test_vrm01_uncertain_correct_vs_rotated_still_uses_non_empty_support() -> None:
    candidates = build_advisory_candidates(
        [_vrm_lip_seating_row(
            surface_score=0.801,
            transverse_offset_mm=0.741,
            mask_area_px=22_032.5,
            pose_confidence=0.317,
            presence_confidence=0.570,
            empty_probability=0.070,
            raw_state="ROTATED",
        )]
    )
    assert candidates[0]["codes"] == ["SEATING?"]


def test_vrm02_lip_seating_uses_slot_specific_calibrated_envelope() -> None:
    candidates = build_advisory_candidates(
        [_vrm_lip_seating_row(
            slot_id="vrm_02",
            surface_score=1.0,
            transverse_offset_mm=1.115,
            mask_area_px=21_128.0,
            pose_confidence=0.346,
            empty_probability=0.012,
        )]
    )
    assert candidates[0]["codes"] == ["SEATING?"]
    assert "VRM02_LIP_SEATING_CORROBORATED" in candidates[0]["details"][0]


def test_verified_normal_vrm02_envelope_does_not_trigger_lip_seating() -> None:
    assert build_advisory_candidates(
        [_vrm_lip_seating_row(
            slot_id="vrm_02",
            surface_score=0.517,
            transverse_offset_mm=0.100,
            mask_area_px=21_522.0,
            pose_confidence=0.42,
            empty_probability=0.01,
        )]
    ) == []


def test_vrm_lip_seating_is_not_generalized_to_unvalidated_slots() -> None:
    assert build_advisory_candidates(
        [_vrm_lip_seating_row(
            slot_id="vrm_03",
            surface_score=1.0,
            transverse_offset_mm=1.2,
            mask_area_px=22_000.0,
            pose_confidence=0.40,
        )]
    ) == []


def test_learned_vrm_seating_provider_exposes_vrm05_candidate() -> None:
    row = _vrm_lip_seating_row(
        slot_id="vrm_05",
        surface_score=0.20,
        transverse_offset_mm=0.10,
        mask_area_px=20_000.0,
        pose_confidence=0.25,
    )
    row["stages"]["pose"]["status"] = "PASS"
    row["stages"]["seating"] = {
        "predicted_state": "SEATING",
        "status": "FAIL",
        "authority": "ADVISORY_ONLY",
        "confidence": 0.1012,
        "probabilities": {"FLAT": 0.8988, "SEATING": 0.1012},
        "flat_max_seating_probability": 0.0524,
        "seating_min_probability": 0.0787,
    }
    candidates = build_advisory_candidates([row])
    assert len(candidates) == 1
    assert candidates[0]["slot_id"] == "vrm_05"
    assert candidates[0]["codes"] == ["SEATING?"]
    assert "VRM_FIXED_SLOT_SEATING_MODEL" in candidates[0]["details"][0]
    assert candidates[0]["authority"] == "ADVISORY_ONLY"


def test_learned_vrm_flat_or_unknown_result_does_not_create_candidate() -> None:
    for predicted, status in (("FLAT", "PASS"), ("UNKNOWN", "UNKNOWN")):
        row = _vrm_lip_seating_row(
            slot_id="vrm_05",
            surface_score=0.20,
            transverse_offset_mm=0.10,
            mask_area_px=20_000.0,
            pose_confidence=0.25,
        )
        row["stages"]["pose"]["status"] = "PASS"
        row["stages"]["seating"] = {
            "predicted_state": predicted,
            "status": status,
            "authority": "ADVISORY_ONLY",
            "confidence": 0.95,
            "probabilities": {"FLAT": 0.95, "SEATING": 0.05},
            "flat_max_seating_probability": 0.0524,
            "seating_min_probability": 0.0787,
        }
        assert build_advisory_candidates([row]) == []


def test_advisory_seating_fail_cannot_promote_final_fail() -> None:
    stages = {
        "presence": {"status": "PASS", "authority": "AUTHORITATIVE"},
        "pose": {"status": "PASS", "authority": "AUTHORITATIVE"},
        "orientation": {"status": "PASS", "authority": "AUTHORITATIVE"},
        "surface": {"status": "PASS", "authority": "AUTHORITATIVE"},
        "seating": {"status": "FAIL", "authority": "ADVISORY_ONLY"},
    }
    status, reason = fuse_required_stages(stages)
    assert status == "UNKNOWN"
    assert "seating" in reason


def test_vrm_non_empty_probability_uses_full_state_distribution() -> None:
    evidence = VrmStateEvidence(
        "vrm_05",
        "UNKNOWN",
        0.55,
        "ADVISORY_ONLY",
        "LOW_CONFIDENCE",
        "vrm_state.torchscript.pt",
        0.80,
        "EMPTY",
        {"EMPTY": 0.08, "CORRECT": 0.47, "ROTATED": 0.45},
    )
    assert _vrm_non_empty_confidence(evidence) == 0.92


def test_vrm_seating_candidate_requires_explicit_runtime_enable(tmp_path: Path) -> None:
    candidate = tmp_path / "vrm_seating_candidate"
    candidate.mkdir()
    (candidate / "vrm_seating.torchscript.pt").write_bytes(b"not-a-model")
    (candidate / "vrm_seating.json").write_text(
        json.dumps({"runtime_enabled": False}), encoding="utf-8"
    )
    provider = VrmSeatingClassifier(tmp_path, device="cpu")
    provider._load()
    assert provider.metadata == {"runtime_enabled": False}
    assert provider.model is None


def test_vrm_calibrated_near_limit_pose_is_visible_as_advisory() -> None:
    row = _vrm_lip_seating_row(
        slot_id="vrm_05",
        surface_score=0.595,
        transverse_offset_mm=0.592,
        mask_area_px=21_647.0,
        pose_confidence=0.362,
    )
    row["stages"]["pose"]["status"] = "PASS"
    row["stages"]["pose"]["measured"].update({
        "position_error_mm": 0.741,
        "slot_reference_calibration_id": "verified_normal_vrm05",
    })
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["POSE?"]
    assert "VRM_CALIBRATED_POSITION" in candidates[0]["details"][0]
    assert candidates[0]["authority"] == "ADVISORY_ONLY"


def test_vrm_uncalibrated_pose_is_not_generalized() -> None:
    row = _vrm_lip_seating_row(
        slot_id="vrm_05",
        surface_score=1.0,
        transverse_offset_mm=1.2,
        mask_area_px=22_000.0,
        pose_confidence=0.40,
    )
    assert build_advisory_candidates([row]) == []


def test_vrm_weak_rotated_vote_requires_patchcore_corroboration() -> None:
    row = _vrm_lip_seating_row(
        slot_id="vrm_04",
        surface_score=1.0,
        transverse_offset_mm=0.0,
        mask_area_px=22_000.0,
        pose_confidence=0.0,
        empty_probability=0.006,
        raw_state="ROTATED",
    )
    row["vrm_state_evidence"]["probabilities"].update({
        "CORRECT": 0.158,
        "ROTATED": 0.836,
    })
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["DIR?"]
    assert "VRM_ROTATION_CORROBORATED" in candidates[0]["details"][0]

    row["stages"]["surface"]["score"] = 0.80
    assert build_advisory_candidates([row]) == []


def test_vrm01_outline_and_patchcore_pose_candidate() -> None:
    row = _vrm_lip_seating_row(
        slot_id="vrm_01",
        surface_score=1.0,
        transverse_offset_mm=0.209,
        mask_area_px=24_014.0,
        pose_confidence=0.296,
    )
    row["stages"]["pose"]["status"] = "PASS"
    row["stages"]["pose"]["measured"]["position_error_mm"] = 0.215
    candidates = build_advisory_candidates([row])
    assert candidates[0]["codes"] == ["POSE?"]
    assert "VRM_OUTLINE_AND_APPEARANCE_OUTSIDE_NORMAL" in candidates[0]["details"][0]


def test_vrm01_normal_outline_or_patchcore_alone_is_hidden() -> None:
    normal = _vrm_lip_seating_row(
        slot_id="vrm_01",
        surface_score=0.768,
        transverse_offset_mm=0.10,
        mask_area_px=22_152.0,
        pose_confidence=0.61,
    )
    normal["stages"]["pose"]["status"] = "PASS"
    assert build_advisory_candidates([normal]) == []

    normal["stages"]["surface"]["score"] = 1.0
    normal["stages"]["pose"]["measured"]["mask_area_px"] = 21_585.0
    assert build_advisory_candidates([normal]) == []


def test_vrm_state_produces_presence_and_orientation_evidence() -> None:
    slot = FixedSlot(
        "vrm_04", "VRM", "vrm", (50.0, 50.0, 30.0, 40.0), 90.0,
        np.zeros((40, 30, 3), np.uint8), (35, 30), (30, 40),
    )
    empty = VrmStateEvidence(
        "vrm_04", "EMPTY", 0.95, "ADVISORY_ONLY", "VRM_STATE_EMPTY",
        "vrm_state.torchscript.pt", 0.80,
    )
    rotated = VrmStateEvidence(
        "vrm_04", "ROTATED", 0.93, "ADVISORY_ONLY", "VRM_STATE_ROTATED",
        "vrm_state.torchscript.pt", 0.80,
    )
    presence = _vrm_presence_evidence(empty)
    orientation = _orientation_check(slot, None, rotated)
    assert presence.status == "FAIL"
    assert presence.authority == "ADVISORY_ONLY"
    assert orientation.status == "FAIL"
    assert orientation.reason == "VRM_STATE_ROTATED_ORIENTATION"
