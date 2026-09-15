"""Recover operator-confirmed VRM04 from TrayHome without a second pick."""
import argparse
import json
import time
from pathlib import Path

import rclpy
from execute_cached_hbm_remaining import Executor, atomic_write
from execute_full_fixed_cycle import (
    load_plan_json, validate_plan, validate_start_state, pose_error,
    preflight_route, move_preflighted, REQUIRED_SPEEDS_PERCENT,
)
from full_cycle_motion import MotionWaypoint
from tray_home_gate import HOME


def route_from_home(start, final):
    height = max(350.0, start[2], final[2] + 100.0)
    high = [*start[:2], height, *start[3:]]
    end = [*final[:2], height, *final[3:]]
    delta = [(end[k] - high[k] + 180.0) % 360.0 - 180.0 for k in (3, 4, 5)]
    rows = [('carry_safe_vertical', tuple(high), True)]
    for fraction in (1 / 3, 2 / 3):
        xyz = [high[k] + fraction * (end[k] - high[k]) for k in range(3)]
        abc = [(high[k + 3] + fraction * delta[k] + 180) % 360 - 180 for k in range(3)]
        rows.append(('place_combined_xy_abc_midpoint', tuple(xyz + abc), False))
    rows.append(('place_combined_xy_abc', tuple(end), False))
    for label, offset in (
        ('place_hover_100mm_vertical', 100),
        ('place_approach_50mm_vertical', 50),
        ('place_final_50mm_vertical', 0),
        ('post_release_lift_50mm_vertical', 50),
        ('post_release_lift_100mm_vertical', 100),
    ):
        rows.append((label, tuple([*final[:2], final[2] + offset, *final[3:]]), True))
    return [('VRM-04', MotionWaypoint(label, tcp, linear)) for label, tcp, linear in rows]


def run_checked(node, checked, item, record, save):
    for waypoint in checked:
        if waypoint.label.startswith('post_release_') and not record.get('release_feedback_settled'):
            raise RuntimeError('retreat forbidden before verified release')
        move_preflighted(node, waypoint)
        record['last_waypoint'] = waypoint.label
        save(record)
        if waypoint.label == 'place_final_50mm_vertical':
            node.gripper(int(item['release_position']), 'VRM04 release at placement target')
            record['release_feedback_settled'] = True
            record['part_held_candidate'] = False
            save(record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--source-record', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-held', action='store_true')
    args = parser.parse_args()
    if args.execute and not args.confirm_held:
        parser.error('operator-held confirmation required')
    if args.record.exists():
        raise RuntimeError('recovery record exists; repeated execution forbidden')
    payload, digest = load_plan_json(args.plan)
    items = validate_plan(payload, 1800, requested_selected_slots=['VRM-04'])
    item = items[0]
    source = json.loads(args.source_record.read_text())
    if (source.get('status') != 'stopped_on_error' or source.get('held_slot') != 'VRM-04'
            or source.get('part_held_candidate') is not True or source.get('plan_sha256') != digest
            or source.get('cycle_id') != payload.get('cycle_id')
            or source.get('motion_completed_slots')):
        raise RuntimeError('source record is not the stopped held VRM04 run')
    rclpy.init()
    node = Executor()
    started = False
    record = dict(slot_code='VRM-04', source_record=str(args.source_record.resolve()),
                  plan_sha256=digest, operator_confirmed_held=bool(args.confirm_held),
                  part_held_candidate=True, physical_placement_verified=False)
    save = lambda value: atomic_write(args.record, value)
    try:
        if not node.client.wait_for_service(timeout_sec=8):
            raise RuntimeError('command service unavailable')
        # Spin continuously through a controller timestamp change; do not reuse
        # the cached state that caused misleading reset feedback in prior attempts.
        initial = node.spin_state()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.1)
            if node.state.timestamp > initial.timestamp:
                break
        else:
            raise RuntimeError('no advancing controller timestamp')
        state = validate_start_state(node)
        node.assert_gripper_ready()
        start = node.snapshot()
        pos, angle = pose_error(start, list(HOME))
        if pos > 1 or angle > 1 or int(state.gripper_position) != int(item['grip_position']):
            raise RuntimeError('requires TrayHome and original held gripper position')
        checked, summary = preflight_route(node, route_from_home(start, item['place_final_tcp']),
                                          node.state_joints(state), REQUIRED_SPEEDS_PERCENT)
        print(json.dumps(dict(target=item['place_final_tcp'], preflight=summary)), flush=True)
        if not args.execute:
            print('DRY RUN ONLY: no motion or gripper command', flush=True)
            return
        validate_plan(payload, 1800, requested_selected_slots=['VRM-04'])
        validate_start_state(node)
        record.update(status='running_held_recovery', start_tcp=start, preflight=summary)
        save(record)
        started = True
        node.service('SetSpeed(40)')
        run_checked(node, checked, item, record, save)
        record.update(status='motion_complete_awaiting_physical_verification',
                      last_tcp=node.snapshot(), completed_unix=time.time())
        save(record)
        print('VRM04 RELEASE AND RETREAT COMPLETED', flush=True)
    except BaseException as exc:
        if started:
            try:
                record['stop_response'] = node.service('StopMotion()')
            finally:
                record.update(status='stopped_on_error', error=str(exc))
                save(record)
        raise
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
