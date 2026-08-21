import math

from fr5_process_sequences import (
    build_pick_place_plan,
    CartesianPose,
    MotionPolicy,
    PlanValidationError,
    StationTarget,
    StepKind,
    TransferWaypoint,
)
import pytest


def pose(x, y, z):
    return CartesianPose('cell_base', x, y, z, 0.0, 0.0, 0.0, 1.0)


def valid_inputs():
    pick = StationTarget('gpu_tray', pose(0.2, 0.1, 0.1), pose(0.2, 0.1, 0.18), (0, 0, 1))
    place = StationTarget('package_board', pose(0.6, -0.1, 0.12), pose(0.6, -0.1, 0.20), (0, 0, 1))
    waypoint = TransferWaypoint('safe_corridor', pose(0.4, 0.0, 0.35), True)
    return pick, place, [waypoint]


def build(**overrides):
    pick, place, waypoints = valid_inputs()
    arguments = {
        'sequence_id': 'gpu_pick_place',
        'part_id': 'gpu',
        'pick': pick,
        'place': place,
        'transfer_waypoints': waypoints,
        'grip_profile_id': 'gpu_grip',
        'release_profile_id': 'gpu_release',
    }
    arguments.update(overrides)
    return build_pick_place_plan(**arguments)


def test_plan_is_dry_run_and_uses_expected_process_shape():
    plan = build(policy=MotionPolicy(transfer_blend_radius_m=0.01))

    assert plan.dry_run_only is True
    assert [step.step_id for step in plan.steps] == [
        'pick_hover',
        'pick_descend',
        'grip',
        'verify_grip',
        'micro_lift',
        'verify_slip',
        'pick_retract',
        'transfer_1',
        'place_hover',
        'place_descend',
        'release',
        'verify_release',
        'place_retract',
    ]
    assert plan.steps[1].kind is StepKind.MOVE_LIN
    assert plan.steps[7].kind is StepKind.MOVE_PTP
    assert plan.steps[9].kind is StepKind.MOVE_LIN


def test_contact_steps_stop_and_never_blend():
    plan = build(policy=MotionPolicy(transfer_blend_radius_m=0.01))
    contact_ids = {
        'pick_hover',
        'pick_descend',
        'grip',
        'verify_grip',
        'micro_lift',
        'verify_slip',
        'pick_retract',
        'place_hover',
        'place_descend',
        'release',
        'verify_release',
        'place_retract',
    }

    for step in plan.steps:
        if step.step_id in contact_ids:
            assert step.controlled_stop_required is True
            assert step.blend_radius_m == 0.0
    assert plan.steps[7].blend_radius_m == 0.01


def test_micro_lift_follows_station_surface_normal():
    plan = build()
    lift = next(step for step in plan.steps if step.step_id == 'micro_lift')

    assert math.isclose(lift.target.x_m, 0.2)
    assert math.isclose(lift.target.y_m, 0.1)
    assert math.isclose(lift.target.z_m, 0.105)


def test_rejects_non_vertical_station_approach():
    pick, _, _ = valid_inputs()
    bad_pick = StationTarget(
        pick.station_id,
        pick.contact,
        pose(0.24, 0.1, 0.18),
        pick.surface_normal,
    )

    with pytest.raises(PlanValidationError, match='not vertically above'):
        build(pick=bad_pick)


def test_rejects_unapproved_or_missing_transfer_corridor():
    _, _, waypoints = valid_inputs()
    unapproved = TransferWaypoint(waypoints[0].waypoint_id, waypoints[0].pose, False)

    with pytest.raises(PlanValidationError, match='at least one taught'):
        build(transfer_waypoints=[])
    with pytest.raises(PlanValidationError, match='not approved free space'):
        build(transfer_waypoints=[unapproved])


def test_rejects_blend_above_approved_bound():
    policy = MotionPolicy(
        transfer_blend_radius_m=0.04,
        maximum_transfer_blend_radius_m=0.03,
    )

    with pytest.raises(PlanValidationError, match='blend radius'):
        build(policy=policy)


def test_web_preview_is_json_serializable_shape():
    preview = build().to_dict()

    assert preview['dry_run_only'] is True
    assert preview['steps'][0]['kind'] == 'move_ptp'
    assert preview['steps'][0]['target']['frame_id'] == 'cell_base'


def test_rejects_pick_and_place_in_different_frames():
    pick, place, waypoints = valid_inputs()
    other_frame_pose = CartesianPose(
        'uncalibrated_board',
        place.contact.x_m,
        place.contact.y_m,
        place.contact.z_m,
        place.contact.qx,
        place.contact.qy,
        place.contact.qz,
        place.contact.qw,
    )
    bad_place = StationTarget(
        place.station_id,
        other_frame_pose,
        CartesianPose(
            'uncalibrated_board', 0.6, -0.1, 0.20, 0.0, 0.0, 0.0, 1.0
        ),
        place.surface_normal,
    )

    with pytest.raises(PlanValidationError, match='one calibrated process frame'):
        build(pick=pick, place=bad_place, transfer_waypoints=waypoints)


def test_rejects_overlapping_transfer_blend_spheres():
    _, _, waypoints = valid_inputs()
    close_waypoint = TransferWaypoint(
        'close_corridor', pose(0.401, 0.0, 0.35), True
    )
    policy = MotionPolicy(transfer_blend_radius_m=0.01)

    with pytest.raises(PlanValidationError, match='blend spheres'):
        build(transfer_waypoints=[waypoints[0], close_waypoint], policy=policy)
