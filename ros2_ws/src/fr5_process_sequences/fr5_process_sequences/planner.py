"""Build a fail-closed pick-transfer-place plan for later ROS execution.

This module deliberately has no robot SDK or ROS action client.  Its output is
only a validated dry-run plan; a separately commissioned adapter must translate
approved steps into controller commands.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Iterable


class PlanValidationError(ValueError):
    """Raised when a requested process cannot be proven safe enough to plan."""


class StepKind(str, Enum):
    """Controller-independent process primitives."""

    MOVE_PTP = 'move_ptp'
    MOVE_LIN = 'move_lin'
    GRIP = 'grip'
    RELEASE = 'release'
    VERIFY_GRIP = 'verify_grip'
    VERIFY_SLIP = 'verify_slip'
    VERIFY_RELEASE = 'verify_release'


@dataclass(frozen=True)
class CartesianPose:
    """Pose expressed in metres and a unit quaternion."""

    frame_id: str
    x_m: float
    y_m: float
    z_m: float
    qx: float
    qy: float
    qz: float
    qw: float


@dataclass(frozen=True)
class StationTarget:
    """Contact and hover poses connected by a qualified vertical LIN path."""

    station_id: str
    contact: CartesianPose
    hover: CartesianPose
    surface_normal: tuple[float, float, float]


@dataclass(frozen=True)
class TransferWaypoint:
    """A taught, collision-qualified point in the free-space transfer corridor."""

    waypoint_id: str
    pose: CartesianPose
    approved_free_space: bool


@dataclass(frozen=True)
class MotionPolicy:
    """Named profiles and bounded geometry used to construct the plan."""

    approach_profile: str = 'precision_linear'
    loaded_transfer_profile: str = 'loaded_transfer'
    empty_transfer_profile: str = 'empty_transfer'
    constraint_profile: str = 'held_part_upright'
    transfer_blend_radius_m: float = 0.0
    micro_lift_distance_m: float = 0.005
    minimum_station_clearance_m: float = 0.03
    maximum_transfer_blend_radius_m: float = 0.03
    vertical_tolerance_deg: float = 1.0


@dataclass(frozen=True)
class ProcessStep:
    """One dry-run process step with explicit stop and collision semantics."""

    step_id: str
    kind: StepKind
    target: CartesianPose | None = None
    profile: str | None = None
    constraint_profile: str | None = None
    gripper_profile_id: str | None = None
    blend_radius_m: float = 0.0
    collision_check_required: bool = True
    controlled_stop_required: bool = False


@dataclass(frozen=True)
class ProcessPlan:
    """Validated plan that cannot directly actuate hardware."""

    sequence_id: str
    part_id: str
    dry_run_only: bool
    steps: tuple[ProcessStep, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable data suitable for a web preview."""
        data = asdict(self)
        for step in data['steps']:
            step['kind'] = step['kind'].value
        return data


def build_pick_place_plan(
    *,
    sequence_id: str,
    part_id: str,
    pick: StationTarget,
    place: StationTarget,
    transfer_waypoints: Iterable[TransferWaypoint],
    grip_profile_id: str,
    release_profile_id: str,
    policy: MotionPolicy | None = None,
) -> ProcessPlan:
    """Build the standard vertical-pick, safe-transfer, vertical-place plan."""
    policy = policy or MotionPolicy()
    waypoints = tuple(transfer_waypoints)
    _validate_identifier(sequence_id, 'sequence_id')
    _validate_identifier(part_id, 'part_id')
    _validate_identifier(grip_profile_id, 'grip_profile_id')
    _validate_identifier(release_profile_id, 'release_profile_id')
    _validate_policy(policy)
    pick_clearance = _validate_station(pick, policy)
    _validate_station(place, policy)
    if place.contact.frame_id != pick.contact.frame_id:
        raise PlanValidationError(
            'pick and place must use one calibrated process frame'
        )
    _validate_transfer_waypoints(waypoints, pick.contact.frame_id)
    if policy.micro_lift_distance_m >= pick_clearance:
        raise PlanValidationError(
            'micro lift must remain below the qualified pick hover pose'
        )

    micro_lift = _offset_pose(
        pick.contact,
        pick.surface_normal,
        policy.micro_lift_distance_m,
    )
    steps: list[ProcessStep] = [
        _motion_step(
            'pick_hover',
            StepKind.MOVE_PTP,
            pick.hover,
            policy.empty_transfer_profile,
            policy.constraint_profile,
            controlled_stop=True,
        ),
        _motion_step(
            'pick_descend',
            StepKind.MOVE_LIN,
            pick.contact,
            policy.approach_profile,
            policy.constraint_profile,
            controlled_stop=True,
        ),
        ProcessStep(
            'grip',
            StepKind.GRIP,
            gripper_profile_id=grip_profile_id,
            controlled_stop_required=True,
        ),
        ProcessStep(
            'verify_grip',
            StepKind.VERIFY_GRIP,
            controlled_stop_required=True,
        ),
        _motion_step(
            'micro_lift',
            StepKind.MOVE_LIN,
            micro_lift,
            policy.approach_profile,
            policy.constraint_profile,
            controlled_stop=True,
        ),
        ProcessStep(
            'verify_slip',
            StepKind.VERIFY_SLIP,
            controlled_stop_required=True,
        ),
        _motion_step(
            'pick_retract',
            StepKind.MOVE_LIN,
            pick.hover,
            policy.approach_profile,
            policy.constraint_profile,
            controlled_stop=True,
        ),
    ]

    transfer_targets = [waypoint.pose for waypoint in waypoints] + [place.hover]
    _validate_blend_geometry(
        pick.hover, transfer_targets, policy.transfer_blend_radius_m
    )
    for index, target in enumerate(transfer_targets):
        is_final = index == len(transfer_targets) - 1
        steps.append(
            _motion_step(
                f'transfer_{index + 1}' if not is_final else 'place_hover',
                StepKind.MOVE_PTP,
                target,
                policy.loaded_transfer_profile,
                policy.constraint_profile,
                blend_radius=0.0 if is_final else policy.transfer_blend_radius_m,
                controlled_stop=is_final,
            )
        )

    steps.extend(
        [
            _motion_step(
                'place_descend',
                StepKind.MOVE_LIN,
                place.contact,
                policy.approach_profile,
                policy.constraint_profile,
                controlled_stop=True,
            ),
            ProcessStep(
                'release',
                StepKind.RELEASE,
                gripper_profile_id=release_profile_id,
                controlled_stop_required=True,
            ),
            ProcessStep(
                'verify_release',
                StepKind.VERIFY_RELEASE,
                controlled_stop_required=True,
            ),
            _motion_step(
                'place_retract',
                StepKind.MOVE_LIN,
                place.hover,
                policy.approach_profile,
                policy.constraint_profile,
                controlled_stop=True,
            ),
        ]
    )
    return ProcessPlan(sequence_id, part_id, True, tuple(steps))


def _motion_step(
    step_id: str,
    kind: StepKind,
    target: CartesianPose,
    profile: str,
    constraint_profile: str,
    *,
    blend_radius: float = 0.0,
    controlled_stop: bool,
) -> ProcessStep:
    return ProcessStep(
        step_id=step_id,
        kind=kind,
        target=target,
        profile=profile,
        constraint_profile=constraint_profile,
        blend_radius_m=blend_radius,
        collision_check_required=True,
        controlled_stop_required=controlled_stop,
    )


def _validate_policy(policy: MotionPolicy) -> None:
    numeric_fields = (
        policy.transfer_blend_radius_m,
        policy.micro_lift_distance_m,
        policy.minimum_station_clearance_m,
        policy.maximum_transfer_blend_radius_m,
        policy.vertical_tolerance_deg,
    )
    if not all(math.isfinite(value) for value in numeric_fields):
        raise PlanValidationError('motion policy values must be finite')
    if policy.micro_lift_distance_m <= 0.0:
        raise PlanValidationError('micro lift distance must be positive')
    if policy.minimum_station_clearance_m <= 0.0:
        raise PlanValidationError('minimum station clearance must be positive')
    if not 0.0 <= policy.transfer_blend_radius_m <= policy.maximum_transfer_blend_radius_m:
        raise PlanValidationError('transfer blend radius exceeds the approved bound')
    if not 0.0 < policy.vertical_tolerance_deg <= 5.0:
        raise PlanValidationError('vertical tolerance must be in (0, 5] degrees')


def _validate_station(station: StationTarget, policy: MotionPolicy) -> float:
    _validate_identifier(station.station_id, 'station_id')
    if len(station.surface_normal) != 3:
        raise PlanValidationError('station surface normal must have 3 values')
    _validate_pose(station.contact)
    _validate_pose(station.hover)
    if station.contact.frame_id != station.hover.frame_id:
        raise PlanValidationError(f'{station.station_id} poses must use one frame')
    if not _same_orientation(station.contact, station.hover):
        raise PlanValidationError(
            f'{station.station_id} contact and hover orientations must match'
        )
    normal = _unit_vector(station.surface_normal, f'{station.station_id} normal')
    delta = (
        station.hover.x_m - station.contact.x_m,
        station.hover.y_m - station.contact.y_m,
        station.hover.z_m - station.contact.z_m,
    )
    clearance = _norm(delta)
    if clearance < policy.minimum_station_clearance_m:
        raise PlanValidationError(
            f'{station.station_id} clearance is below the approved minimum'
        )
    alignment = sum(a * b for a, b in zip(_unit_vector(delta, 'hover delta'), normal))
    minimum_alignment = math.cos(math.radians(policy.vertical_tolerance_deg))
    if alignment < minimum_alignment:
        raise PlanValidationError(
            f'{station.station_id} hover is not vertically above contact'
        )
    return clearance


def _validate_transfer_waypoints(
    waypoints: tuple[TransferWaypoint, ...], frame_id: str
) -> None:
    if not waypoints:
        raise PlanValidationError(
            'at least one taught free-space transfer waypoint is required'
        )
    seen: set[str] = set()
    for waypoint in waypoints:
        _validate_identifier(waypoint.waypoint_id, 'waypoint_id')
        if waypoint.waypoint_id in seen:
            raise PlanValidationError('transfer waypoint ids must be unique')
        seen.add(waypoint.waypoint_id)
        _validate_pose(waypoint.pose)
        if waypoint.pose.frame_id != frame_id:
            raise PlanValidationError('all process poses must use one calibrated frame')
        if not waypoint.approved_free_space:
            raise PlanValidationError(
                f'transfer waypoint {waypoint.waypoint_id} is not approved free space'
            )


def _validate_blend_geometry(
    start: CartesianPose,
    targets: list[CartesianPose],
    blend_radius_m: float,
) -> None:
    if blend_radius_m == 0.0:
        return
    points = [start] + targets
    for index in range(1, len(points) - 1):
        incoming = _pose_distance(points[index - 1], points[index])
        outgoing = _pose_distance(points[index], points[index + 1])
        if 2.0 * blend_radius_m >= min(incoming, outgoing):
            raise PlanValidationError(
                'transfer blend spheres would overlap adjacent targets'
            )


def _pose_distance(left: CartesianPose, right: CartesianPose) -> float:
    return _norm(
        (left.x_m - right.x_m, left.y_m - right.y_m, left.z_m - right.z_m)
    )


def _validate_pose(pose: CartesianPose) -> None:
    if not pose.frame_id:
        raise PlanValidationError('pose frame_id must be non-empty')
    values = (pose.x_m, pose.y_m, pose.z_m, pose.qx, pose.qy, pose.qz, pose.qw)
    if not all(math.isfinite(value) for value in values):
        raise PlanValidationError('pose values must be finite')
    quaternion_norm = _norm((pose.qx, pose.qy, pose.qz, pose.qw))
    if not math.isclose(quaternion_norm, 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise PlanValidationError('pose quaternion must be normalized')


def _same_orientation(left: CartesianPose, right: CartesianPose) -> bool:
    dot = abs(
        left.qx * right.qx
        + left.qy * right.qy
        + left.qz * right.qz
        + left.qw * right.qw
    )
    return math.isclose(dot, 1.0, rel_tol=0.0, abs_tol=1e-6)


def _offset_pose(
    pose: CartesianPose,
    direction: tuple[float, float, float],
    distance_m: float,
) -> CartesianPose:
    unit = _unit_vector(direction, 'offset direction')
    return CartesianPose(
        frame_id=pose.frame_id,
        x_m=pose.x_m + unit[0] * distance_m,
        y_m=pose.y_m + unit[1] * distance_m,
        z_m=pose.z_m + unit[2] * distance_m,
        qx=pose.qx,
        qy=pose.qy,
        qz=pose.qz,
        qw=pose.qw,
    )


def _unit_vector(values: tuple[float, ...], label: str) -> tuple[float, ...]:
    if not all(math.isfinite(value) for value in values):
        raise PlanValidationError(f'{label} must be finite')
    magnitude = _norm(values)
    if magnitude <= 1e-12:
        raise PlanValidationError(f'{label} must be non-zero')
    return tuple(value / magnitude for value in values)


def _norm(values: tuple[float, ...]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _validate_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not value or not value.replace('_', '').isalnum():
        raise PlanValidationError(f'{label} must be a non-empty identifier')
