"""Backend-owned adapter from a fresh fixed-cycle snapshot to API targets.

Uses the existing precision planner; never invents coordinates, re-stamps old
observations, changes recipe values, or sends hardware commands.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from uuid import UUID

from .real_backend import CartesianTarget

PART_TYPES = {'HBM': 'hbm', 'PM': 'long_orange', 'GPU': 'gpu',
              'CAP': 'right_white_brown', 'IND': 'marked_white', 'VRM': 'black_block'}


def source_time(capture, now, maximum_age):
    # captured_unix may be the snapshot creation time; include its recorded
    # source age so publishing never makes older observations appear newer.
    source_age = float(capture.get('source_age_sec', 0.0))
    if not math.isfinite(source_age) or source_age < 0:
        raise ValueError('invalid source age')
    stamp = float(capture['captured_unix']) - source_age
    if not math.isfinite(stamp) or not 0 <= now - stamp <= maximum_age:
        raise ValueError('fresh source observation required; snapshot is stale/future-dated')
    return stamp


def build_target_payload(*, snapshot, recipes, slots, steps, job_id, plan_builder,
                         now=None, maximum_age_sec=2.5, frozen_unit=False):
    if frozen_unit:
        maximum_age_sec = 1800.0
    now = time.time() if now is None else float(now)
    if not math.isfinite(now) or not math.isfinite(maximum_age_sec) or maximum_age_sec <= 0:
        raise ValueError('invalid clock or maximum age')
    job_id = str(UUID(job_id))
    board_stamp = source_time(snapshot['board_capture'], now, maximum_age_sec)
    counts, indexed, orders, slot_codes = {}, [], set(), set()
    for step in steps:
        part, slot, order = step['part_id'], step['slot_code'], step['order']
        if part not in PART_TYPES or slot in slot_codes or order in orders:
            raise ValueError('unknown part or duplicate step/slot')
        if isinstance(order, bool) or not isinstance(order, int) or order <= 0:
            raise ValueError('invalid order')
        slot_codes.add(slot); orders.add(order)
        counts[part] = counts.get(part, 0) + 1
        indexed.append((step, counts[part]))
    if not indexed:
        raise ValueError('no recipe steps')
    stamps = {}
    for part in counts:
        key = 'smd_close_capture' if part == 'CAP' else 'tray_capture'
        if part == 'CAP' and snapshot.get('smd_close_captured') is not True:
            raise ValueError('SMD close measurements are required')
        stamps[part] = source_time(snapshot[key], now, maximum_age_sec)
    # build_plan validates quality, corrections, taught heights, and successful
    # orientation branches; the adapter never constructs raw Cartesian guesses.
    requested = [s['slot_code'] for s, _ in indexed]
    if len(requested) == 25:
        selection = {}  # full planner validates the complete canonical part set
    elif set(counts) == {'CAP'}:
        selection = {'phase': 'smd'}
    elif len(requested) == 20 and 'CAP' not in counts:
        selection = {'phase': 'non-smd'}
    else:
        selection = {'selected_slots': requested}
    plan = plan_builder(snapshot, recipes, slots, **selection)
    items = plan['plan']
    payload = {'schema': 'fr5.real.vision_targets/v1', 'valid': True,
               'coordinate_frame': 'base_link', 'job_id': job_id,
               'timestamp_ros_ns': int(min(board_stamp, *stamps.values()) * 1e9),
               'source_cycle_id': snapshot.get('cycle_id'),
               'plan_sha256': hashlib.sha256(json.dumps(plan, sort_keys=True,
                    allow_nan=False).encode()).hexdigest(),
               'parts': [], 'slots': [], 'transfers': []}
    from .real_precision_steps import digest
    context = snapshot.get('execution_context')
    if context is not None:
        if not isinstance(context, dict) or context.get('execution_job_id') != job_id:
            raise ValueError('execution context must match Unit execution UUID')
        if set(context) - {'execution_job_id','production_job_id','unit_id','display_board_id'}:
            raise ValueError('unknown execution context field')
        if ('production_job_id' in context) != ('unit_id' in context):
            raise ValueError('production job and unit must be supplied together')
        if 'production_job_id' in context:
            if str(UUID(context['production_job_id'])) != context['production_job_id']:
                raise ValueError('production job must be canonical UUID')
            if type(context['unit_id']) is not int or context['unit_id'] < 1:
                raise ValueError('unit_id must be positive integer')
        if 'display_board_id' in context and (not isinstance(context['display_board_id'], str)
                or not context['display_board_id'].strip()):
            raise ValueError('display_board_id must be explicit nonempty string')
        payload['execution_context'] = dict(context)
    payload['calibration_digests'] = {'recipes': digest(recipes), 'slots': digest(slots)}
    payload['precision_plan'] = plan
    payload['target_mode'] = 'frozen_unit' if frozen_unit else 'live'
    # TrayHome coarse pixels identify cells, including CAP. SMD close-up pixels
    # are never substituted for this common registered tray coordinate system.
    reference_parts = snapshot.get('tray_capture', {}).get('parts', [])
    if isinstance(reference_parts, list) and reference_parts and all(
            p.get('reference_center_pixel') is not None for p in reference_parts):
        payload['tray_inspection_reference'] = {
            'handeye_sha256': snapshot['tray_capture'].get('handeye_sha256'),
            'bindings': [dict(part_type=p['part_type'], physical_index=p['instance_index'],
                reference_center_pixel=p['reference_center_pixel']) for p in reference_parts]}
    for step, index in indexed:
        part, slot = step['part_id'], step['slot_code']
        matches = [item for item in items if item['slot_code'] == slot]
        if len(matches) != 1:
            raise ValueError(f'{slot}: missing or ambiguous planner item')
        item = matches[0]
        if item['part_type'] != PART_TYPES[part] or item['tray_instance_index'] != index:
            raise ValueError(f'{slot}: planner source index does not match Sequencer recipe')
        common = dict(job_id=job_id, part_id=part, slot_code=slot,
                      order=step['order'], source_index=index)
        sources = [p for p in reference_parts if p['part_type'] == PART_TYPES[part]
                   and p['instance_index'] == index]
        if len(sources) == 1:
            # Never reconstruct IDs in a consumer; historical captures remain
            # usable for motion diagnostics but cannot authorize attachment.
            for key in ('source_id', 'tray_registration_id', 'source_observation_id'):
                common[key] = sources[0].get(key)
        recipe = recipes['parts'][PART_TYPES[part]]
        if part == 'VRM':
            recipe = recipe['horizontal']
        profiles = {}
        for phase, key in [('PREOPEN','tray_pick_open'),('GRASP','grip'),('RELEASE','release')]:
            args = recipe.get(key, recipe['release'])['args']
            profiles[phase] = {'velocity_percent': args[2], 'force_percent': args[3]}
        gripper = dict(pregrasp_opening_percent=item['tray_open_position'],
                       grasp_opening_percent=item['grip_position'],
                       release_opening_percent=item['release_position'])
        for group, key, stamp in [('parts', 'pick_final_tcp', stamps[part]),
                                 ('slots', 'place_final_tcp', min(board_stamp, stamps[part]))]:
            pose = CartesianTarget('base_link', *item[key]).controller_pose()
            payload[group].append(dict(common, tcp_pose_mm_deg=list(pose),
                timestamp_ros_ns=int(stamp*1e9), expected_gripper=gripper,
                gripper_profiles=profiles))
    return payload


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--sequence', type=Path, required=True, help='Sequencer YAML steps')
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frozen-unit', action='store_true', help='explicit fixed-scene Unit plan; original sources expire after 1800 s, never re-stamped')
    parser.add_argument('--publish', action='store_true', help='publish targets once; never move robot')
    a = parser.parse_args(args)
    import yaml
    sys.path.insert(0, str(a.project_root / 'vision_assembly/scripts'))
    from full_cycle_plan import build_plan
    snapshot = json.loads(a.snapshot.read_text())
    calibration = a.project_root / 'calibration/data/handeye_result.json'
    if snapshot['tray_capture'].get('handeye_sha256') != hashlib.sha256(calibration.read_bytes()).hexdigest():
        raise ValueError('snapshot hand-eye differs from active calibration')
    payload = build_target_payload(snapshot=snapshot,
        recipes=json.loads((a.project_root/'vision_assembly/config/part_gripper_recipes.json').read_text()),
        slots=json.loads((a.project_root/'vision_assembly/config/assembly_slots_r1.json').read_text()),
        steps=yaml.safe_load(a.sequence.read_text())['steps'], job_id=a.job_id, plan_builder=build_plan,
        frozen_unit=a.frozen_unit)
    encoded = json.dumps(payload, indent=2, allow_nan=False)
    a.output.write_text(encoded+'\n')
    if a.publish:
        import rclpy
        from std_msgs.msg import String
        from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
        rclpy.init()
        node = rclpy.create_node('real_precision_target_adapter')
        try:
            publisher = node.create_publisher(String, '/real/vision/targets',
                QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                           durability=DurabilityPolicy.VOLATILE))
            deadline = time.monotonic() + 2
            while publisher.get_subscription_count() == 0 and time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.05)
            if publisher.get_subscription_count() == 0:
                raise RuntimeError('no API subscriber; target file saved but not delivered')
            if time.time() - payload['timestamp_ros_ns']/1e9 > (1800.0 if a.frozen_unit else 2.5):
                raise ValueError('measurement expired before publication; recapture required')
            publisher.publish(String(data=encoded))
            publisher.wait_for_all_acked(rclpy.duration.Duration(seconds=1))
        finally:
            node.destroy_node(); rclpy.shutdown()
    print(f'Saved {len(payload["parts"])} calibrated targets to {a.output}; no robot motion')


if __name__ == '__main__':
    main()
