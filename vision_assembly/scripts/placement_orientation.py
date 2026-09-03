#!/usr/bin/env python3
"""Plan the smallest carried-part rotation from its actual grasp orientation.

The tray detector reports an unoriented part axis.  Once the part is grasped,
that axis is rigidly attached to either Tool X or Tool Y.  Placement therefore
has to align the *current carried-part axis* with the board slot axis; a fixed
TCP C angle is not sufficient when tray parts or the board can be rotated.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.spatial.transform import Rotation


def wrap_degrees(value: float) -> float:
    """Wrap an angle to [-180, 180)."""
    return (float(value) + 180.0) % 360.0 - 180.0


def circular_distance_deg(first: float, second: float) -> float:
    return abs(wrap_degrees(float(first) - float(second)))


def _unit_xy(vector: np.ndarray, label: str) -> np.ndarray:
    xy = np.asarray(vector, dtype=float)[:2]
    norm = float(np.linalg.norm(xy))
    if not np.all(np.isfinite(xy)) or norm < 0.5:
        raise ValueError(f"{label} has no stable Base-XY projection")
    return xy / norm


def tool_axis_base_angle_deg(tcp_abc_deg: list[float], gripper_axis: str) -> float:
    """Return the current Base-XY angle of the part-holding tool axis."""
    if gripper_axis not in ("tool_x", "tool_y"):
        raise ValueError("gripper_axis must be tool_x or tool_y")
    abc = np.asarray(tcp_abc_deg, dtype=float)
    if abc.shape != (3,) or not np.all(np.isfinite(abc)):
        raise ValueError("tcp_abc_deg must contain three finite values")
    rotation = Rotation.from_euler("xyz", abc, degrees=True).as_matrix()
    index = 0 if gripper_axis == "tool_x" else 1
    axis = _unit_xy(rotation[:, index], gripper_axis)
    return math.degrees(math.atan2(axis[1], axis[0]))


def slot_axis_base_angle_deg(
    board_rotation: np.ndarray,
    long_axis_board_deg: float,
) -> float:
    """Transform a slot's Board-XY long axis into a Base-XY angle."""
    matrix = np.asarray(board_rotation, dtype=float)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ValueError("board_rotation must be a finite 3x3 matrix")
    angle = math.radians(float(long_axis_board_deg))
    board_axis = np.array([math.cos(angle), math.sin(angle), 0.0])
    base_axis = _unit_xy(matrix @ board_axis, "slot long axis")
    return math.degrees(math.atan2(base_axis[1], base_axis[0]))


def _alignment_candidates_deg(
    current_axis_deg: float,
    target_axis_deg: float,
    symmetry_period_deg: float,
) -> list[float]:
    period = float(symmetry_period_deg)
    if not math.isfinite(period) or period <= 0.0 or period > 360.0:
        raise ValueError("symmetry_period_deg must be in (0, 360]")
    raw = float(target_axis_deg) - float(current_axis_deg)
    candidates: list[float] = []
    steps = int(math.ceil(360.0 / period)) + 2
    for index in range(-steps, steps + 1):
        candidate = wrap_degrees(raw + index * period)
        if not any(abs(wrap_degrees(candidate - old)) < 1e-7 for old in candidates):
            candidates.append(candidate)
    return sorted(candidates, key=lambda value: (abs(value), value))


def plan_carried_part_orientation(
    current_tcp_abc_deg: list[float],
    target_axis_base_deg: float,
    gripper_axis: str,
    symmetry_period_deg: float,
    *,
    preferred_tcp_c_deg: float | None = None,
    preference_tie_threshold_deg: float = 5.0,
) -> dict:
    """Return the smallest valid Base-Z rotation for the carried part.

    A preferred TCP C value is only a tie-breaker between nearly equal travel
    candidates.  It can preserve a physically taught head/tail choice without
    reintroducing unconditional absolute-C motion.
    """
    current = np.asarray(current_tcp_abc_deg, dtype=float)
    current_axis = tool_axis_base_angle_deg(current.tolist(), gripper_axis)
    candidates = _alignment_candidates_deg(
        current_axis,
        float(target_axis_base_deg),
        float(symmetry_period_deg),
    )
    minimum = abs(candidates[0])
    eligible = [
        value for value in candidates
        if abs(value) <= minimum + float(preference_tie_threshold_deg) + 1e-9
    ]

    def target_for(delta: float) -> list[float]:
        rotation = (
            Rotation.from_euler("z", delta, degrees=True)
            * Rotation.from_euler("xyz", current, degrees=True)
        )
        return rotation.as_euler("xyz", degrees=True).tolist()

    if preferred_tcp_c_deg is None:
        delta = candidates[0]
    else:
        preference = float(preferred_tcp_c_deg)
        if not math.isfinite(preference):
            raise ValueError("preferred_tcp_c_deg must be finite")
        delta = min(
            eligible,
            key=lambda value: (
                circular_distance_deg(target_for(value)[2], preference),
                abs(value),
            ),
        )
    target_abc = target_for(delta)
    final_axis = tool_axis_base_angle_deg(target_abc, gripper_axis)
    residual_candidates = _alignment_candidates_deg(
        final_axis,
        float(target_axis_base_deg),
        float(symmetry_period_deg),
    )
    residual = abs(residual_candidates[0])
    if residual > 1e-5:
        raise RuntimeError(f"orientation planner residual is {residual:.6f} deg")
    return {
        "current_axis_base_deg": current_axis,
        "target_axis_base_deg": float(target_axis_base_deg),
        "symmetry_period_deg": float(symmetry_period_deg),
        "rotation_delta_deg": float(delta),
        "target_tcp_abc_deg": [float(value) for value in target_abc],
        "preferred_tcp_c_deg": (
            None if preferred_tcp_c_deg is None else float(preferred_tcp_c_deg)
        ),
    }
