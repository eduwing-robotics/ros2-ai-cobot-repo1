from __future__ import annotations

import json
import sys
import time
from argparse import Namespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "vision_assembly" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from fixed_cycle_snapshot import (
    load_smd_close_angles,
    merge_smd_close_angles,
    update_readiness,
    validate_tray_detection_quality,
)
from smd_set_selection import select_smd_set


QUALITY = json.loads(
    (ROOT / "vision_assembly" / "config" / "part_gripper_recipes.json").read_text(
        encoding="utf-8"
    )
)["tray_snapshot_quality"]


def detection(**overrides) -> dict:
    payload = {
        "part_type": "long_orange",
        "instance_index": 4,
        "observation_frames": 40,
        "median_detection_confidence": 0.98,
        "median_mask_shape_score": 0.91,
        "median_rectangularity": 0.94,
    }
    payload.update(overrides)
    return payload


def test_tray_quality_gate_accepts_complete_high_quality_track() -> None:
    metrics = validate_tray_detection_quality(detection(), QUALITY)

    assert metrics == {
        "observation_frames": 40,
        "median_detection_confidence": 0.98,
        "median_mask_shape_score": 0.91,
        "median_rectangularity": 0.94,
    }


def test_tray_quality_gate_rejects_low_confidence_power_module() -> None:
    with pytest.raises(RuntimeError, match=r"median_detection_confidence=0\.271"):
        validate_tray_detection_quality(
            detection(median_detection_confidence=0.271),
            QUALITY,
        )


def test_tray_quality_gate_rejects_legacy_track_without_shape_metrics() -> None:
    legacy = {
        "part_type": "long_orange",
        "instance_index": 4,
        "observation_frames": 40,
        "median_cad_area_match_score": 0.271,
    }

    with pytest.raises(RuntimeError, match="missing median_mask_shape_score"):
        validate_tray_detection_quality(legacy, QUALITY)


SMD_LAYOUT = {
    "set_count": 2,
    "parts_per_set": 5,
    "required_count": 10,
    "canonical_y_ranges": [[0, 360], [360, 720]],
}


def smd_items(set_index: int) -> list[dict]:
    y = 180 if set_index == 1 else 540
    return [{"center": [100 * index, y]} for index in range(1, 6)]


def test_smd_set_selection_allows_other_set_to_be_empty_or_populated() -> None:
    first_only = select_smd_set(smd_items(1), SMD_LAYOUT, 1)
    both_sets = select_smd_set(smd_items(1) + smd_items(2), SMD_LAYOUT, 1)

    assert [item["center"][0] for item in first_only] == [100, 200, 300, 400, 500]
    assert [item["center"][0] for item in both_sets] == [100, 200, 300, 400, 500]


def test_smd_set_selection_selects_second_row_independently() -> None:
    selected = select_smd_set(smd_items(1) + smd_items(2), SMD_LAYOUT, 2)

    assert len(selected) == 5
    assert all(item["center"][1] == 540 for item in selected)


def close_batch(set_index: int = 1, timestamp_unix: float | None = None) -> dict:
    cycle_count = 5
    return {
        "schema_version": 2,
        "mode": "smd_close_multiframe_base_targets",
        "timestamp_unix": time.time() if timestamp_unix is None else timestamp_unix,
        "validation_passed": True,
        "handeye_sha256": "a" * 64,
        "set_index": set_index,
        "required_count": cycle_count,
        "layout_capacity": 10,
        "parts": [
            {
                "part_type": "right_white_brown",
                "instance_index": instance,
                "physical_instance_index": (set_index - 1) * cycle_count + instance,
                "set_index": set_index,
                "frame_count": 8,
                "confidence_median": 0.9,
                "long_axis_angle_base_deg": float(instance * 10),
                "validation_passed": True,
            }
            for instance in range(1, cycle_count + 1)
        ],
    }


def close_args(path: Path, set_index: int = 1) -> Namespace:
    return Namespace(
        smd_close_input=path,
        max_smd_close_age_sec=120.0,
        min_smd_close_frames=8,
        min_smd_close_confidence=0.5,
        smd_set_index=set_index,
    )


def test_close_batch_maps_second_set_physical_indices_to_cycle_1_through_5(
    tmp_path: Path,
) -> None:
    path = tmp_path / "close.json"
    path.write_text(json.dumps(close_batch(set_index=2)), encoding="utf-8")

    angles, metadata = load_smd_close_angles(close_args(path, set_index=2))

    assert set(angles) == {1, 2, 3, 4, 5}
    assert metadata["physical_instance_indices"] == [6, 7, 8, 9, 10]


def test_close_batch_rejects_wrong_requested_set(tmp_path: Path) -> None:
    path = tmp_path / "close.json"
    path.write_text(json.dumps(close_batch(set_index=2)), encoding="utf-8")

    with pytest.raises(RuntimeError, match="SMD close set mismatch"):
        load_smd_close_angles(close_args(path, set_index=1))


def test_close_batch_rejects_old_capture_even_when_file_is_new(tmp_path: Path) -> None:
    path = tmp_path / "close.json"
    path.write_text(
        json.dumps(close_batch(timestamp_unix=time.time() - 121.0)),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="SMD close capture is stale"):
        load_smd_close_angles(close_args(path))


def test_smd_merge_keeps_trayhome_xyz_and_requires_close_angles() -> None:
    payload = {
        "board_captured": True,
        "tray_captured": True,
        "smd_close_captured": False,
        "resolved_placements": {
            f"slot-{index}": {"placement_ready": True} for index in range(25)
        },
        "tray_capture": {
            "parts": [
                {
                    "part_type": "right_white_brown",
                    "instance_index": instance,
                    "base_xyz_mm": [instance, instance + 1, instance + 2],
                    "long_axis_angle_base_deg": 1.5,
                }
                for instance in range(1, 6)
            ]
        },
    }
    update_readiness(payload)
    assert payload["ready_for_continuous_execution"] is False
    angles = {
        instance: {
            "long_axis_angle_base_deg": 1.5 + instance,
            "confidence_median": 0.9,
            "frame_count": 8,
            "physical_instance_index": instance,
        }
        for instance in range(1, 6)
    }

    merged = merge_smd_close_angles(
        payload,
        angles,
        {"angle_source": "SMD close-view robust OBB only", "set_index": 1},
    )

    assert merged["ready_for_continuous_execution"] is True
    for cap in merged["tray_capture"]["parts"]:
        instance = cap["instance_index"]
        assert cap["base_xyz_mm"] == [instance, instance + 1, instance + 2]
        assert cap["coarse_long_axis_angle_base_deg"] == 1.5
        assert cap["long_axis_angle_base_deg"] == 1.5 + instance
        assert cap["smd_physical_instance_index"] == instance

    bad_payload = json.loads(json.dumps(payload))
    for cap in bad_payload["tray_capture"]["parts"]:
        cap["long_axis_angle_base_deg"] = cap["coarse_long_axis_angle_base_deg"]
    bad_angles = json.loads(json.dumps(angles))
    bad_angles["1"]["long_axis_angle_base_deg"] = 91.5
    with pytest.raises(RuntimeError, match="coarse/close angle contradiction"):
        merge_smd_close_angles(
            bad_payload,
            {int(key): value for key, value in bad_angles.items()},
            {"angle_source": "SMD close-view robust OBB only", "set_index": 1},
        )

    sign_payload = json.loads(json.dumps(bad_payload))
    sign_payload["tray_capture"]["parts"][0]["long_axis_angle_base_deg"] = 1.657
    sign_angles = json.loads(json.dumps(angles))
    sign_angles["1"]["long_axis_angle_base_deg"] = 7.026
    with pytest.raises(RuntimeError, match="coarse/close angle contradiction"):
        merge_smd_close_angles(
            sign_payload,
            {int(key): value for key, value in sign_angles.items()},
            {"angle_source": "SMD close-view robust OBB only", "set_index": 1},
        )
