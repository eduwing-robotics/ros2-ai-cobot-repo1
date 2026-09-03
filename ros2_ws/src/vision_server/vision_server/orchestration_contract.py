"""Validation and conversion for the Unity orchestration vision Actions.

This module is ROS-independent so the wire-contract rules can be unit tested
without starting cameras or an Action server. It never commands robot motion.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

import numpy as np


BASE_FRAME = "base_link"


class ContractFailure(RuntimeError):
    """A validation failure that maps directly to an Action error_code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PoseValue:
    position_m: tuple[float, float, float]
    orientation_xyzw: tuple[float, float, float, float]


@dataclass(frozen=True)
class TraySnapshot:
    stamp_ns: int
    part_ids: tuple[str, ...]
    poses: tuple[PoseValue, ...]


@dataclass(frozen=True)
class PcbSnapshot:
    stamp_ns: int
    pose: PoseValue


def _finite_vector(value: Any, length: int, label: str) -> np.ndarray:
    try:
        vector = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ContractFailure("FRAME_TRANSFORM_FAILED", f"{label} is not numeric") from exc
    if vector.shape != (length,) or not np.all(np.isfinite(vector)):
        raise ContractFailure(
            "FRAME_TRANSFORM_FAILED",
            f"{label} must contain {length} finite values",
        )
    return vector


def _source_stamp_ns(payload: Mapping[str, Any]) -> int:
    try:
        stamp_ns = int(payload["timestamp_ros_ns"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractFailure(
            "DETECTION_TIMEOUT", "vision result has no acquisition timestamp"
        ) from exc
    if stamp_ns <= 0:
        raise ContractFailure(
            "DETECTION_TIMEOUT", "vision acquisition timestamp is invalid"
        )
    return stamp_ns


def _validate_age(stamp_ns: int, now_ns: int, maximum_age_sec: float) -> None:
    age_sec = (int(now_ns) - int(stamp_ns)) / 1_000_000_000.0
    if age_sec < -5.0 or age_sec > float(maximum_age_sec):
        raise ContractFailure(
            "DETECTION_TIMEOUT",
            f"vision result is stale (age={age_sec:.3f}s)",
        )


def _normalize_quaternion(values: Sequence[float]) -> tuple[float, float, float, float]:
    quaternion = _finite_vector(values, 4, "quaternion")
    norm = float(np.linalg.norm(quaternion))
    if norm < 1e-9:
        raise ContractFailure("FRAME_TRANSFORM_FAILED", "quaternion norm is zero")
    quaternion /= norm
    # q and -q are identical. A canonical hemisphere prevents visual sign flips.
    if quaternion[3] < 0.0:
        quaternion = -quaternion
    return tuple(float(value) for value in quaternion)


def yaw_quaternion_deg(yaw_deg: float) -> tuple[float, float, float, float]:
    if not math.isfinite(float(yaw_deg)):
        raise ContractFailure("UNSTABLE_DETECTION", "part angle is not finite")
    half = math.radians(float(yaw_deg)) * 0.5
    return _normalize_quaternion((0.0, 0.0, math.sin(half), math.cos(half)))


def matrix_quaternion_xyzw(rotation: np.ndarray) -> tuple[float, float, float, float]:
    """Convert a proper 3x3 rotation matrix to a normalized xyzw quaternion."""

    matrix = np.asarray(rotation, dtype=float)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ContractFailure(
            "FRAME_TRANSFORM_FAILED", "PCB rotation must be a finite 3x3 matrix"
        )
    orthogonality_error = float(np.max(np.abs(matrix.T @ matrix - np.eye(3))))
    determinant = float(np.linalg.det(matrix))
    if orthogonality_error > 0.02 or abs(determinant - 1.0) > 0.02:
        raise ContractFailure(
            "FRAME_TRANSFORM_FAILED",
            "PCB rotation matrix is not orthonormal "
            f"(error={orthogonality_error:.4f}, det={determinant:.4f})",
        )

    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * scale
        x = (matrix[2, 1] - matrix[1, 2]) / scale
        y = (matrix[0, 2] - matrix[2, 0]) / scale
        z = (matrix[1, 0] - matrix[0, 1]) / scale
    else:
        diagonal = np.diag(matrix)
        index = int(np.argmax(diagonal))
        if index == 0:
            scale = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            w = (matrix[2, 1] - matrix[1, 2]) / scale
            x = 0.25 * scale
            y = (matrix[0, 1] + matrix[1, 0]) / scale
            z = (matrix[0, 2] + matrix[2, 0]) / scale
        elif index == 1:
            scale = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            w = (matrix[0, 2] - matrix[2, 0]) / scale
            x = (matrix[0, 1] + matrix[1, 0]) / scale
            y = 0.25 * scale
            z = (matrix[1, 2] + matrix[2, 1]) / scale
        else:
            scale = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            w = (matrix[1, 0] - matrix[0, 1]) / scale
            x = (matrix[0, 2] + matrix[2, 0]) / scale
            y = (matrix[1, 2] + matrix[2, 1]) / scale
            z = 0.25 * scale
    return _normalize_quaternion((x, y, z, w))


def tray_snapshot(
    payload: Mapping[str, Any],
    part_mappings: Mapping[str, Mapping[str, Any]],
    *,
    now_ns: int,
    maximum_age_sec: float,
    minimum_observation_frames: int,
) -> TraySnapshot:
    if payload.get("schema") != "fr5.tray.unity_state/v1":
        raise ContractFailure("CAMERA_NOT_READY", "unexpected tray result schema")
    if payload.get("valid") is not True:
        state = str(payload.get("registration_state", "UNKNOWN"))
        raise ContractFailure(
            "UNSTABLE_DETECTION", f"tray result is not stable (state={state})"
        )
    if str(payload.get("coordinate_frame", "")) != BASE_FRAME:
        raise ContractFailure(
            "FRAME_TRANSFORM_FAILED",
            f"tray coordinate frame must be {BASE_FRAME}",
        )
    stamp_ns = _source_stamp_ns(payload)
    _validate_age(stamp_ns, now_ns, maximum_age_sec)

    parts = payload.get("parts")
    if not isinstance(parts, list):
        raise ContractFailure("UNSTABLE_DETECTION", "tray parts is not an array")
    if not parts:
        raise ContractFailure("NO_PARTS_DETECTED", "no stable tray parts detected")

    identifiers: list[str] = []
    poses: list[PoseValue] = []
    physical_ids: set[str] = set()
    for index, part in enumerate(parts):
        if not isinstance(part, Mapping):
            raise ContractFailure(
                "UNSTABLE_DETECTION", f"tray part[{index}] is malformed"
            )
        detector_type = str(part.get("part_type", ""))
        mapping = part_mappings.get(detector_type)
        if mapping is None:
            raise ContractFailure(
                "UNKNOWN_PART", f"unmapped detector part type: {detector_type!r}"
            )
        part_id = str(mapping.get("part_id", "")).strip()
        if not part_id:
            raise ContractFailure(
                "UNKNOWN_PART", f"empty Recipe part_id for {detector_type!r}"
            )

        physical_id = str(part.get("id", "")).strip()
        if not physical_id or physical_id in physical_ids:
            raise ContractFailure(
                "UNSTABLE_DETECTION",
                f"missing or duplicate physical tray id: {physical_id!r}",
            )
        physical_ids.add(physical_id)

        try:
            observation_frames = int(part.get("observation_frames", 0))
        except (TypeError, ValueError) as exc:
            raise ContractFailure(
                "UNSTABLE_DETECTION", f"invalid observation count for {physical_id}"
            ) from exc
        if observation_frames < int(minimum_observation_frames):
            raise ContractFailure(
                "UNSTABLE_DETECTION",
                f"{physical_id} has only {observation_frames} stable frames",
            )

        xyz_mm = _finite_vector(
            part.get("base_xyz_mm"), 3, f"{physical_id} base_xyz_mm"
        )
        try:
            yaw_deg = float(part["angle_base_deg"]) + float(
                mapping.get("yaw_offset_deg", 0.0)
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractFailure(
                "UNSTABLE_DETECTION", f"invalid angle for {physical_id}"
            ) from exc
        orientation = yaw_quaternion_deg(yaw_deg)

        offset_local_m = _finite_vector(
            mapping.get("origin_offset_local_m", [0.0, 0.0, 0.0]),
            3,
            f"{detector_type} origin_offset_local_m",
        )
        yaw = math.radians(yaw_deg)
        cosine, sine = math.cos(yaw), math.sin(yaw)
        offset_base_m = np.array(
            [
                cosine * offset_local_m[0] - sine * offset_local_m[1],
                sine * offset_local_m[0] + cosine * offset_local_m[1],
                offset_local_m[2],
            ]
        )
        position_m = xyz_mm / 1000.0 + offset_base_m
        identifiers.append(part_id)
        poses.append(
            PoseValue(
                tuple(float(value) for value in position_m),
                orientation,
            )
        )

    return TraySnapshot(stamp_ns, tuple(identifiers), tuple(poses))


def pcb_snapshot(
    payload: Mapping[str, Any],
    *,
    requested_product_code: str,
    requested_product_version: str,
    expected_product_code: str,
    expected_product_version: str,
    now_ns: int,
    maximum_age_sec: float,
    maximum_hole_fit_rms_mm: float,
    maximum_plane_mad_mm: float,
    minimum_plane_inliers: int,
) -> PcbSnapshot:
    if not requested_product_code or not requested_product_version:
        raise ContractFailure(
            "INVALID_REQUEST", "product_code and product_version are required"
        )
    if (
        requested_product_code != expected_product_code
        or requested_product_version != expected_product_version
    ):
        raise ContractFailure(
            "WRONG_PCB",
            "requested PCB does not match the configured product "
            f"{expected_product_code}/{expected_product_version}",
        )
    if payload.get("schema") != "fr5.vision.board_pose_3d/v1":
        raise ContractFailure("CAMERA_NOT_READY", "unexpected PCB result schema")
    if payload.get("valid") is not True:
        reason = str(payload.get("reason", "PCB pose is invalid"))
        raise ContractFailure("PCB_NOT_FOUND", reason)
    if str(payload.get("coordinate_frame", "")) != BASE_FRAME:
        raise ContractFailure(
            "FRAME_TRANSFORM_FAILED",
            f"PCB coordinate frame must be {BASE_FRAME}",
        )
    if (
        str(payload.get("product_code", "")) != expected_product_code
        or str(payload.get("product_version", "")) != expected_product_version
    ):
        raise ContractFailure(
            "WRONG_PCB", "detected PCB identity does not match the configured product"
        )

    stamp_ns = _source_stamp_ns(payload)
    _validate_age(stamp_ns, now_ns, maximum_age_sec)
    try:
        rms = float(payload["hole_fit_rms_mm"])
        mad = float(payload["plane_residual_mad_mm"])
        inliers = int(payload["plane_inliers"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractFailure(
            "CALIBRATION_NOT_READY", "PCB quality metrics are incomplete"
        ) from exc
    if not math.isfinite(rms) or not math.isfinite(mad):
        raise ContractFailure(
            "CALIBRATION_NOT_READY", "PCB quality metrics are not finite"
        )
    if (
        rms > float(maximum_hole_fit_rms_mm)
        or mad > float(maximum_plane_mad_mm)
        or inliers < int(minimum_plane_inliers)
    ):
        raise ContractFailure(
            "UNSTABLE_POSE",
            "PCB pose quality rejected "
            f"(hole_rms={rms:.3f}mm, plane_mad={mad:.3f}mm, inliers={inliers})",
        )

    try:
        transform = np.asarray(payload["T_base_board"], dtype=float)
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractFailure(
            "FRAME_TRANSFORM_FAILED", "T_base_board is missing or invalid"
        ) from exc
    if transform.shape != (4, 4) or not np.all(np.isfinite(transform)):
        raise ContractFailure(
            "FRAME_TRANSFORM_FAILED", "T_base_board must be a finite 4x4 matrix"
        )
    if float(np.max(np.abs(transform[3] - np.array([0.0, 0.0, 0.0, 1.0])))) > 1e-6:
        raise ContractFailure(
            "FRAME_TRANSFORM_FAILED", "T_base_board has an invalid homogeneous row"
        )
    orientation = matrix_quaternion_xyzw(transform[:3, :3])
    position = tuple(float(value) for value in transform[:3, 3])
    return PcbSnapshot(stamp_ns, PoseValue(position, orientation))
