import copy
import pytest
from full_cycle_plan import DEFAULT_SPEEDS_PERCENT
from execute_full_fixed_cycle import waypoint_speed, REQUIRED_SPEEDS_PERCENT


def test_contact_zone_and_proof_lift_keep_prior_speeds():
    speeds = DEFAULT_SPEEDS_PERCENT
    assert speeds == REQUIRED_SPEEDS_PERCENT
    for label in ('pick_final_50mm_vertical', 'place_final_50mm_vertical',
                  'post_grasp_lift_50mm_vertical', 'post_release_lift_50mm_vertical'):
        assert waypoint_speed(label, speeds) == 10
    assert waypoint_speed('post_grasp_proof_lift_100mm_vertical', speeds) == 25
    assert waypoint_speed('tray_after_inspect', speeds) == 10
    assert waypoint_speed('tray_after_depart', speeds) == 10


def test_only_clearance_raise_and_high_transfers_accelerate():
    speeds = DEFAULT_SPEEDS_PERCENT
    assert waypoint_speed('tray_after_raise', speeds) == 30
    for label in ('pick_combined_xy_abc', 'place_combined_xy_abc_midpoint',
                  'tray_after_mid_travel', 'tray_after_travel'):
        assert waypoint_speed(label, speeds) == 40
    assert waypoint_speed('pick_approach_50mm_vertical', speeds) == 25


def test_explicit_camera_and_recovery_speeds_are_not_silently_raised():
    old = dict(travel=10, combined_rotation=10, vertical=10)
    for label in ('tray_after_raise', 'tray_after_mid_travel', 'place_combined_xy_abc'):
        assert waypoint_speed(label, old) == 10
