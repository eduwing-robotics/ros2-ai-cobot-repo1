#!/usr/bin/env python3
"""Pure helpers for planning and validating one full-cycle slot motion.

This module deliberately has no ROS, SDK, service, or robot-command imports.
It only builds TCP waypoint data and rejects unsafe joint solutions so the
same checks can be used by an offline planner and by a later executor.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence


CANONICAL_WAYPOINT_COUNT = 14
DEFAULT_J6_OPERATIONAL_BOUNDS_DEG = (-178.0, 178.0)
DEFAULT_MAX_JOINT_STEP_DEG = 95.0
PRESERVE_PICK_TCP_ORIENTATION = "preserve_pick_tcp_orientation"


class MotionPlanError(RuntimeError):
    """Raised when an offline motion plan violates an operational invariant."""


@dataclass(frozen=True)
class MotionWaypoint:
    """One robot-independent TCP waypoint."""

    label: str
    tcp: tuple[float, float, float, float, float, float]
    linear: bool

    def as_dict(self) -> dict:
        """Return a JSON-friendly representation."""
        return {
            "label": self.label,
            "tcp": list(self.tcp),
            "linear": self.linear,
        }


@dataclass(frozen=True)
class JointPathValidation:
    """Summary returned after every joint waypoint passes validation."""

    waypoint_count: int
    maximum_step_deg: float
    minimum_j6_deg: float
    maximum_j6_deg: float


def _finite_six(
    values: Sequence[float], label: str
) -> tuple[float, float, float, float, float, float]:
    try:
        result = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise MotionPlanError(f"{label} must contain six finite values") from exc
    if len(result) != 6 or not all(math.isfinite(value) for value in result):
        raise MotionPlanError(f"{label} must contain six finite values")
    return result  # type: ignore[return-value]


def normalize_controller_tcp(values: Sequence[float]) -> tuple[float, float, float, float, float, float]:
    """Canonical Euler representation for FR5 IK; same physical TCP pose.

    Planning may unwrap Euler angles to preserve interpolation direction.
    The controller query must receive each angle within [-180,180]. Keep
    in-range endpoints (including +180) unchanged.
    """
    pose = list(_finite_six(values, "controller TCP"))
    for axis in (3, 4, 5):
        if pose[axis] < -180.0 or pose[axis] > 180.0:
            pose[axis] = (pose[axis] + 180.0) % 360.0 - 180.0
    return tuple(pose)


def _finite_scalar(value: float, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise MotionPlanError(f"{label} must be finite") from exc
    if not math.isfinite(result):
        raise MotionPlanError(f"{label} must be finite")
    return result


def validate_hbm_preserve_orientation(
    part_type: str | None,
    orientation_policy_mode: str | None,
    pick_final_tcp: Sequence[float],
    place_final_tcp: Sequence[float],
    *,
    tolerance_deg: float = 1e-9,
) -> None:
    """Require literal pick/place ABC preservation for the HBM policy.

    The check is intentionally component-wise rather than modulo 360 degrees.
    The preserved policy must carry the exact planned pick ABC through the
    placement descent; an equivalent Euler representation could otherwise
    reintroduce a wrist branch change.
    """

    part = "" if part_type is None else str(part_type).strip().lower()
    mode = "" if orientation_policy_mode is None else str(
        orientation_policy_mode
    ).strip()
    if mode != PRESERVE_PICK_TCP_ORIENTATION:
        return
    if part != "hbm":
        raise MotionPlanError(
            f"{PRESERVE_PICK_TCP_ORIENTATION} is only supported for hbm"
        )

    pick = _finite_six(pick_final_tcp, "pick_final_tcp")
    place = _finite_six(place_final_tcp, "place_final_tcp")
    tolerance = _finite_scalar(tolerance_deg, "tolerance_deg")
    if tolerance < 0.0:
        raise MotionPlanError("tolerance_deg must be non-negative")
    differences = [abs(pick[index] - place[index]) for index in range(3, 6)]
    if any(value > tolerance for value in differences):
        raise MotionPlanError(
            "HBM preserve policy requires place ABC to equal pick ABC; "
            f"pick={list(pick[3:])}, place={list(place[3:])}"
        )


def build_canonical_slot_waypoints(
    start_tcp: Sequence[float],
    pick_final_tcp: Sequence[float],
    place_final_tcp: Sequence[float],
    transfer_z_mm: float,
    *,
    clearance_mm: float = 100.0,
    close_clearance_mm: float = 50.0,
    part_type: str | None = None,
    orientation_policy_mode: str | None = None,
) -> tuple[MotionWaypoint, ...]:
    """Build the canonical fourteen-waypoint smooth motion for one slot.

    Pick and place XY+ABC changes happen only in two combined MoveJ-style
    waypoints at ``transfer_z_mm``.  There is no in-place rotation waypoint.
    Each descent reaches a 100 mm hover, moves quickly to 50 mm, then covers
    only the final 50 mm at the slow vertical speed. Retreats reverse that
    profile: 50 mm slow, then 100 mm fast. All vertical waypoints keep XY and
    ABC constant.
    """

    start = _finite_six(start_tcp, "start_tcp")
    pick = _finite_six(pick_final_tcp, "pick_final_tcp")
    place = _finite_six(place_final_tcp, "place_final_tcp")
    transfer_z = _finite_scalar(transfer_z_mm, "transfer_z_mm")
    clearance = _finite_scalar(clearance_mm, "clearance_mm")
    close_clearance = _finite_scalar(
        close_clearance_mm, "close_clearance_mm"
    )
    if clearance <= 0.0:
        raise MotionPlanError("clearance_mm must be positive")
    if close_clearance <= 0.0 or close_clearance >= clearance:
        raise MotionPlanError(
            "close_clearance_mm must be positive and below clearance_mm"
        )

    validate_hbm_preserve_orientation(
        part_type,
        orientation_policy_mode,
        pick,
        place,
    )

    pick_hover_z = pick[2] + clearance
    pick_approach_z = pick[2] + close_clearance
    place_hover_z = place[2] + clearance
    place_approach_z = place[2] + close_clearance
    if transfer_z + 1e-9 < max(pick_hover_z, place_hover_z):
        raise MotionPlanError(
            "transfer_z_mm must not be below either clearance waypoint"
        )

    waypoints = (
        MotionWaypoint(
            "pre_pick_safe_vertical",
            (start[0], start[1], transfer_z, *start[3:]),
            True,
        ),
        MotionWaypoint(
            "pick_combined_xy_abc",
            (pick[0], pick[1], transfer_z, *pick[3:]),
            False,
        ),
        MotionWaypoint(
            "pick_hover_100mm_vertical",
            (pick[0], pick[1], pick_hover_z, *pick[3:]),
            True,
        ),
        MotionWaypoint(
            "pick_approach_50mm_vertical",
            (pick[0], pick[1], pick_approach_z, *pick[3:]),
            True,
        ),
        MotionWaypoint("pick_final_50mm_vertical", pick, True),
        MotionWaypoint(
            "post_grasp_lift_50mm_vertical",
            (pick[0], pick[1], pick_approach_z, *pick[3:]),
            True,
        ),
        MotionWaypoint(
            "post_grasp_proof_lift_100mm_vertical",
            (pick[0], pick[1], pick_hover_z, *pick[3:]),
            True,
        ),
        MotionWaypoint(
            "carry_safe_vertical",
            (pick[0], pick[1], transfer_z, *pick[3:]),
            True,
        ),
        MotionWaypoint(
            "place_combined_xy_abc",
            (place[0], place[1], transfer_z, *place[3:]),
            False,
        ),
        MotionWaypoint(
            "place_hover_100mm_vertical",
            (place[0], place[1], place_hover_z, *place[3:]),
            True,
        ),
        MotionWaypoint(
            "place_approach_50mm_vertical",
            (place[0], place[1], place_approach_z, *place[3:]),
            True,
        ),
        MotionWaypoint("place_final_50mm_vertical", place, True),
        MotionWaypoint(
            "post_release_lift_50mm_vertical",
            (place[0], place[1], place_approach_z, *place[3:]),
            True,
        ),
        MotionWaypoint(
            "post_release_lift_100mm_vertical",
            (place[0], place[1], place_hover_z, *place[3:]),
            True,
        ),
    )
    if len(waypoints) != CANONICAL_WAYPOINT_COUNT:
        raise AssertionError("canonical slot profile must contain fourteen waypoints")
    if any("rotate" in waypoint.label.lower() for waypoint in waypoints):
        raise AssertionError("canonical slot profile must not split out rotation")
    return waypoints


def validate_j6_operational_envelope(
    j6_values_deg: Iterable[float],
    *,
    bounds_deg: Sequence[float] = DEFAULT_J6_OPERATIONAL_BOUNDS_DEG,
) -> tuple[float, ...]:
    """Validate absolute J6 values against the real controller envelope."""

    try:
        bounds = tuple(float(value) for value in bounds_deg)
    except (TypeError, ValueError) as exc:
        raise MotionPlanError("J6 bounds must contain two finite values") from exc
    if (
        len(bounds) != 2
        or not all(math.isfinite(value) for value in bounds)
        or bounds[0] >= bounds[1]
    ):
        raise MotionPlanError("J6 bounds must contain increasing finite values")

    values = tuple(_finite_scalar(value, "J6") for value in j6_values_deg)
    for index, value in enumerate(values, 1):
        if value < bounds[0] - 1e-9 or value > bounds[1] + 1e-9:
            raise MotionPlanError(
                f"J6 waypoint {index}={value:.3f} deg is outside operational "
                f"envelope [{bounds[0]:.3f}, {bounds[1]:.3f}] deg"
            )
    return values


def validate_joint_path(
    waypoint_joints_deg: Iterable[Sequence[float]],
    *,
    initial_joints_deg: Sequence[float] | None = None,
    j6_bounds_deg: Sequence[float] = DEFAULT_J6_OPERATIONAL_BOUNDS_DEG,
    max_step_deg: float = DEFAULT_MAX_JOINT_STEP_DEG,
) -> JointPathValidation:
    """Reject an unsafe six-joint waypoint sequence.

    The J6 operational envelope is independent of the controller's broader
    advertised soft limits.  The per-step gate applies to every joint and to
    the initial-state-to-first-waypoint transition when an initial state is
    supplied.
    """

    waypoints = tuple(
        _finite_six(values, f"joint waypoint {index}")
        for index, values in enumerate(waypoint_joints_deg, 1)
    )
    if not waypoints:
        raise MotionPlanError("joint path must contain at least one waypoint")

    initial = (
        None
        if initial_joints_deg is None
        else _finite_six(initial_joints_deg, "initial_joints_deg")
    )
    all_vectors = ((initial,) if initial is not None else ()) + waypoints
    j6_values = validate_j6_operational_envelope(
        (values[5] for values in all_vectors), bounds_deg=j6_bounds_deg
    )

    maximum_allowed = _finite_scalar(max_step_deg, "max_step_deg")
    if maximum_allowed <= 0.0:
        raise MotionPlanError("max_step_deg must be positive")

    maximum_seen = 0.0
    previous = initial
    for waypoint_index, current in enumerate(waypoints, 1):
        if previous is not None:
            deltas = tuple(
                abs(current[index] - previous[index]) for index in range(6)
            )
            step = max(deltas)
            maximum_seen = max(maximum_seen, step)
            if step > maximum_allowed + 1e-9:
                joint_index = deltas.index(step) + 1
                raise MotionPlanError(
                    f"joint waypoint {waypoint_index} changes J{joint_index} by "
                    f"{step:.3f} deg; maximum is {maximum_allowed:.3f} deg"
                )
        previous = current

    return JointPathValidation(
        waypoint_count=len(waypoints),
        maximum_step_deg=maximum_seen,
        minimum_j6_deg=min(j6_values),
        maximum_j6_deg=max(j6_values),
    )
