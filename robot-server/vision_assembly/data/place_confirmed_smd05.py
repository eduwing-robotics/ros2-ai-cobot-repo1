"""Place operator-confirmed SMD05 from PlaceCamera; no pick or batch execution."""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import rclpy

from execute_cached_hbm_remaining import Executor, atomic_write
from execute_full_fixed_cycle import (
    REQUIRED_SPEEDS_PERCENT, pose_error, preflight_route,
    move_preflighted, validate_start_state,
)
from full_cycle_motion import MotionWaypoint
from placement_orientation import plan_carried_part_orientation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-held-smd05', action='store_true')
    args = parser.parse_args()
    if args.execute and not args.confirm_held_smd05:
        parser.error('operator-confirmed SMD05 required')
    if args.record.exists():
        raise RuntimeError('record already exists; no repeated release allowed')
    import hashlib
    root=Path('/home/juchan-yoon/FR5_robot_control')
    held_path=root/'vision_assembly/data/smd05_pick_attempt_20260906.json'
    held=json.loads(held_path.read_text())
    if held.get('physical_grasp_verified') is not True or held.get('placement_completed'):
        raise RuntimeError('SMD05 confirmed held state required')
    recipe_file=root/'vision_assembly/config/part_gripper_recipes.json'
    if hashlib.sha256(recipe_file.read_bytes()).hexdigest()!=held['recipe_sha256']:
        raise RuntimeError('recipe changed since successful pick')
    recipe=json.loads(recipe_file.read_text())['parts']['right_white_brown']
    if recipe['placement_release_position']!=17:raise RuntimeError('release recipe mismatch')
    board = json.loads(args.board.read_text())
    captured = float(board['board_capture']['captured_unix'])
    if not 0 <= time.time() - captured <= 120:
        raise RuntimeError('fresh board capture within 120 seconds required')
    target = board['resolved_placements']['CAP-05']
    if target.get('placement_ready') is not True or target['part_type'] != 'right_white_brown':
        raise RuntimeError('SMD05 placement blocked')
    policy = target['placement_orientation']
    if policy['gripper_axis'] != 'tool_x' or policy['symmetry_period_deg'] != 180:
        raise RuntimeError('unexpected holding-axis policy')
    rclpy.init()
    node = Executor()
    started = False
    record = {'slot_code': 'CAP-05', 'board_file': str(args.board.resolve()),
              'board_captured_unix': captured, 'physical_placement_verified': False}
    try:
        if not node.client.wait_for_service(timeout_sec=8):
            raise RuntimeError('command service unavailable')
        initial=node.spin_state();deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.1)
            if node.state.timestamp>initial.timestamp:break
        else:raise RuntimeError('controller timestamp not advancing')
        state = validate_start_state(node)
        node.assert_gripper_ready()
        start = node.snapshot()
        pos, angle = pose_error(start, [36.943,-449.135,321.342,179.998,.001,180])
        if pos > 1 or angle > 1 or int(state.gripper_position) != 12:
            raise RuntimeError('requires PlaceCamera pose and closed gripper18')
        orientation = plan_carried_part_orientation(
            start[3:], policy['slot_long_axis_base_deg'], 'tool_x', 180,
            preferred_tcp_c_deg=90,
            preference_tie_threshold_deg=policy['preference_tie_threshold_deg'])
        if abs(orientation['rotation_delta_deg']) > 95:
            raise RuntimeError('unexpected alignment change at PlaceCamera')
        final = [*target['corrected_place_xy_base_mm'],
                 float(target['final_tcp_z_mm']) + .3,
                 *orientation['target_tcp_abc_deg']]
        if not all(math.isfinite(v) for v in final):
            raise RuntimeError('nonfinite target')
        if not (90 < final[0] < 115 and -495 < final[1] < -470 and 80 < final[2] < 95):
            raise RuntimeError('SMD05 target outside reviewed local envelope')
        def at(z): return tuple([*final[:2], z, *final[3:]])
        route = [('CAP-05', MotionWaypoint(label, tcp, linear)) for label,tcp,linear in [
            ('carry_safe_vertical', tuple([*start[:2],350,*start[3:]]), True),
            *[('place_combined_xy_abc_midpoint', tuple([start[0]+(final[0]-start[0])*i/3,start[1]+(final[1]-start[1])*i/3,350,*[start[k]+((final[k]-start[k]+180)%360-180)*i/3 for k in (3,4,5)]]),False) for i in (1,2)],
            ('place_combined_xy_abc', at(350), False),
            ('place_hover_100mm_vertical', at(final[2]+100), True),
            ('place_approach_50mm_vertical', at(final[2]+50), True),
            ('place_final_50mm_vertical', tuple(final), True),
            ('post_release_lift_50mm_vertical', at(final[2]+50), True),
            ('post_release_lift_100mm_vertical', at(final[2]+100), True),
        ]]
        checked, summary = preflight_route(node, route, node.state_joints(state), REQUIRED_SPEEDS_PERCENT)
        print(json.dumps({'target': final, 'preflight': summary}), flush=True)
        if not args.execute:
            print('DRY RUN: NO MOTION OR GRIPPER COMMAND', flush=True)
            return
        if time.time()-captured > 120:
            raise RuntimeError('board expired during preflight')
        record.update(status='running', start_tcp=start, final_tcp=final,
                      operator_confirmed_held=True, preflight=summary)
        atomic_write(args.record, record)
        started = True
        node.service('SetSpeed(40)')
        for waypoint in checked:
            if waypoint.label.startswith('post_release_') and not record.get('release_feedback_settled'):
                raise RuntimeError('retreat requires verified release')
            state=validate_start_state(node)
            if not record.get('release_feedback_settled') and state.gripper_position!=12:
                raise RuntimeError('held gripper changed before placement')
            move_preflighted(node, waypoint)
            record['last_waypoint'] = waypoint.label
            if waypoint.label == 'place_final_50mm_vertical':
                node.gripper(17, 'SMD05 release after operator-confirmed grasp')
                record['release_feedback_settled'] = True
            atomic_write(args.record, record)
        record.update(status='motion_complete_awaiting_physical_verification',
                      last_tcp=node.snapshot(), completed_unix=time.time())
        atomic_write(args.record, record)
        held.update(placement_completed=True,placement_record=str(args.record),part_held_candidate=False,status='released_at_CAP05_and_retreated',placement_completed_unix=time.time())
        atomic_write(held_path,held)
        print('SMD05 RELEASE AND RETREAT COMPLETED; PHYSICAL SEATING NOT YET VERIFIED', flush=True)
    except BaseException as exc:
        if started:
            try:
                node.service('StopMotion()')
            finally:
                record.update(status='error', error=str(exc))
                atomic_write(args.record, record)
        raise
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
