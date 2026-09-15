import math

import numpy as np
import pytest

from vision_server.orchestration_contract import (
    ContractFailure,
    pcb_snapshot,
    tray_snapshot,
)


PART_MAPPINGS = {
    "gpu": {
        "part_id": "GPU",
        "yaw_offset_deg": 0.0,
        "origin_offset_local_m": [0.0, 0.0, 0.0],
    },
    "hbm": {
        "part_id": "HBM",
        "yaw_offset_deg": 0.0,
        "origin_offset_local_m": [0.0, 0.0, 0.0],
    },
}


def tray_payload(stamp_ns=10_000_000_000):
    return {
        "schema": "fr5.tray.unity_state/v1",
        "timestamp_ros_ns": stamp_ns,
        "valid": True,
        "registration_state": "TRACKING",
        "coordinate_frame": "base_link",
        "parts": [
            {
                "id": "gpu:01",
                "part_type": "gpu",
                "base_xyz_mm": [100.0, -200.0, 50.0],
                "angle_base_deg": 90.0,
                "observation_frames": 20,
            },
            {
                "id": "hbm:01",
                "part_type": "hbm",
                "base_xyz_mm": [110.0, -210.0, 51.0],
                "angle_base_deg": 0.0,
                "observation_frames": 21,
            },
            {
                "id": "hbm:02",
                "part_type": "hbm",
                "base_xyz_mm": [120.0, -220.0, 52.0],
                "angle_base_deg": 180.0,
                "observation_frames": 22,
            },
        ],
    }


def pcb_payload(stamp_ns=10_000_000_000):
    return {
        "schema": "fr5.vision.board_pose_3d/v1",
        "timestamp_ros_ns": stamp_ns,
        "coordinate_frame": "base_link",
        "product_code": "printed_semiconductor_package_board",
        "product_version": "assembly-r1",
        "valid": True,
        "hole_fit_rms_mm": 0.5,
        "plane_residual_mad_mm": 0.8,
        "plane_inliers": 1000,
        "T_base_board": [
            [0.0, -1.0, 0.0, 0.10],
            [1.0, 0.0, 0.0, -0.20],
            [0.0, 0.0, 1.0, 0.30],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }


def test_tray_snapshot_maps_recipe_ids_units_and_shared_stamp():
    snapshot = tray_snapshot(
        tray_payload(),
        PART_MAPPINGS,
        now_ns=10_500_000_000,
        maximum_age_sec=2.0,
        minimum_observation_frames=5,
    )
    assert snapshot.stamp_ns == 10_000_000_000
    assert snapshot.part_ids == ("GPU", "HBM", "HBM")
    assert snapshot.poses[0].position_m == pytest.approx((0.1, -0.2, 0.05))
    assert snapshot.poses[0].orientation_xyzw == pytest.approx(
        (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
    )
    assert all(
        np.linalg.norm(pose.orientation_xyzw) == pytest.approx(1.0)
        for pose in snapshot.poses
    )


def test_tray_snapshot_rejects_unknown_part():
    payload = tray_payload()
    payload["parts"][0]["part_type"] = "mystery"
    with pytest.raises(ContractFailure) as caught:
        tray_snapshot(
            payload,
            PART_MAPPINGS,
            now_ns=10_500_000_000,
            maximum_age_sec=2.0,
            minimum_observation_frames=5,
        )
    assert caught.value.code == "UNKNOWN_PART"


def test_tray_snapshot_rejects_stale_or_non_base_data():
    payload = tray_payload()
    payload["coordinate_frame"] = "camera_link"
    with pytest.raises(ContractFailure) as caught:
        tray_snapshot(
            payload,
            PART_MAPPINGS,
            now_ns=10_500_000_000,
            maximum_age_sec=2.0,
            minimum_observation_frames=5,
        )
    assert caught.value.code == "FRAME_TRANSFORM_FAILED"

    payload = tray_payload()
    with pytest.raises(ContractFailure) as caught:
        tray_snapshot(
            payload,
            PART_MAPPINGS,
            now_ns=20_000_000_000,
            maximum_age_sec=2.0,
            minimum_observation_frames=5,
        )
    assert caught.value.code == "DETECTION_TIMEOUT"


def test_pcb_snapshot_returns_absolute_root_pose_and_normalized_quaternion():
    snapshot = pcb_snapshot(
        pcb_payload(),
        requested_product_code="printed_semiconductor_package_board",
        requested_product_version="assembly-r1",
        expected_product_code="printed_semiconductor_package_board",
        expected_product_version="assembly-r1",
        now_ns=10_500_000_000,
        maximum_age_sec=2.0,
        maximum_hole_fit_rms_mm=1.5,
        maximum_plane_mad_mm=2.0,
        minimum_plane_inliers=200,
    )
    assert snapshot.stamp_ns == 10_000_000_000
    assert snapshot.pose.position_m == pytest.approx((0.1, -0.2, 0.3))
    assert snapshot.pose.orientation_xyzw == pytest.approx(
        (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
    )


def test_pcb_snapshot_rejects_wrong_product_and_unstable_pose():
    with pytest.raises(ContractFailure) as caught:
        pcb_snapshot(
            pcb_payload(),
            requested_product_code="other",
            requested_product_version="assembly-r1",
            expected_product_code="printed_semiconductor_package_board",
            expected_product_version="assembly-r1",
            now_ns=10_500_000_000,
            maximum_age_sec=2.0,
            maximum_hole_fit_rms_mm=1.5,
            maximum_plane_mad_mm=2.0,
            minimum_plane_inliers=200,
        )
    assert caught.value.code == "WRONG_PCB"

    payload = pcb_payload()
    payload["hole_fit_rms_mm"] = 2.0
    with pytest.raises(ContractFailure) as caught:
        pcb_snapshot(
            payload,
            requested_product_code="printed_semiconductor_package_board",
            requested_product_version="assembly-r1",
            expected_product_code="printed_semiconductor_package_board",
            expected_product_version="assembly-r1",
            now_ns=10_500_000_000,
            maximum_age_sec=2.0,
            maximum_hole_fit_rms_mm=1.5,
            maximum_plane_mad_mm=2.0,
            minimum_plane_inliers=200,
        )
    assert caught.value.code == "UNSTABLE_POSE"


def test_pcb_snapshot_rejects_invalid_transform():
    payload = pcb_payload()
    payload["T_base_board"][0][0] = 2.0
    with pytest.raises(ContractFailure) as caught:
        pcb_snapshot(
            payload,
            requested_product_code="printed_semiconductor_package_board",
            requested_product_version="assembly-r1",
            expected_product_code="printed_semiconductor_package_board",
            expected_product_version="assembly-r1",
            now_ns=10_500_000_000,
            maximum_age_sec=2.0,
            maximum_hole_fit_rms_mm=1.5,
            maximum_plane_mad_mm=2.0,
            minimum_plane_inliers=200,
        )
    assert caught.value.code == "FRAME_TRANSFORM_FAILED"
