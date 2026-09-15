#!/usr/bin/env python3
"""Place VRM-01..05 from one frozen tray/board capture."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from scipy.spatial.transform import Rotation

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from execute_cached_hbm_remaining import (  # noqa: E402
    Executor,
    atomic_write,
    finite,
    nearest_symmetric_c,
)
from placement_orientation import (  # noqa: E402
    plan_carried_part_orientation,
    slot_axis_base_angle_deg,
)


ROOT = Path(__file__).resolve().parents[2]
VISION = ROOT / 'vision_assembly'
BOARD_SNAPSHOT = VISION / 'data/fixed_cycle_vrm_retry_2026-09-02.json'
TRAY_SNAPSHOT = VISION / 'data/fixed_cycle_tray_vrm_retry_2026-09-02.json'
RECIPES = VISION / 'config/part_gripper_recipes.json'
SLOT_FILE = VISION / 'config/assembly_slots_r1.json'
RUN_RECORD = VISION / 'data/cached_vrm_01_05_retry_run.json'
SLOTS = [f'VRM-{index:02d}' for index in range(1, 6)]


class VrmExecutor(Executor):
    """Use the recipe's validated 95-degree intentional-rotation envelope."""

    def referenced_ik(
        self, target: list[float], max_joint_step_deg: float = 95.0
    ) -> np.ndarray:
        return super().referenced_ik(target, max_joint_step_deg=max_joint_step_deg)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def build_plan(args: argparse.Namespace) -> list[dict]:
    board = load(args.board_snapshot)
    if board.get('schema') != 'fr5.fixed_fixture_cycle_snapshot/v1':
        raise RuntimeError('wrong board snapshot schema')
    if not board.get('board_captured'):
        raise RuntimeError('board snapshot is not captured')
    board_age = time.time() - float(board['created_unix'])
    if board_age < -5.0 or board_age > args.max_board_snapshot_age_sec:
        raise RuntimeError(f'board snapshot is stale ({board_age:.1f}s)')
    capture = board.get('board_capture', {})
    if int(capture.get('slot_count', 0)) != 25:
        raise RuntimeError('board snapshot does not contain all 25 slots')
    if float(capture.get('hole_fit_rms_mm', math.inf)) > 1.5:
        raise RuntimeError('board snapshot hole-fit quality is invalid')
    if float(capture.get('plane_residual_mad_mm', math.inf)) > 2.0:
        raise RuntimeError('board snapshot plane quality is invalid')
    board_transform = np.asarray(capture.get('T_base_board'), dtype=float)
    if board_transform.shape != (4, 4) or not np.all(np.isfinite(board_transform)):
        raise RuntimeError('board snapshot has no valid Base transform')
    board_rotation = board_transform[:3, :3]
    placements = board.get('resolved_placements', {})

    tray = load(args.tray_snapshot)
    if tray.get('tray_registration') != 'TRACKING':
        raise RuntimeError('frozen tray snapshot was not TRACKING')
    if tray.get('base_transform_status') not in ('OK', 'VALID_COORDINATES_ONLY'):
        raise RuntimeError('frozen tray snapshot has no valid Base transform')
    if float(tray.get('robot_pose_span_mm', math.inf)) > 0.5:
        raise RuntimeError('robot moved during frozen tray capture')
    detections = [
        item for item in tray.get('stable_detections', [])
        if item.get('part_type') == 'black_block'
    ]
    detections.sort(key=lambda item: int(item['instance_index']))
    if len(detections) != len(SLOTS):
        raise RuntimeError(
            f'expected exactly {len(SLOTS)} frozen VRM detections, got {len(detections)}'
        )
    if any(int(item.get('observation_frames', 0)) < 40 for item in detections):
        raise RuntimeError('VRM tray detections require 40 stable frames')

    recipe = load(args.recipe_file)['parts']['black_block']
    correction = recipe.get('grasp_center_correction_base_mm', {})
    pick_xy_correction = finite(
        [correction.get('x'), correction.get('y')], 2, 'VRM grasp Base correction'
    )
    if not np.allclose(pick_xy_correction, [-2.0, 1.6], atol=1e-6):
        raise RuntimeError(f'unexpected VRM pick correction {pick_xy_correction.tolist()}')
    pick_z_offset = float(
        recipe['grasp_height']['tcp_z_offset_from_detected_surface_mm']
    )
    place_z_offset = float(recipe['placement_surface_to_tcp_z_offset_mm'])
    if not -15.0 <= pick_z_offset <= 0.0:
        raise RuntimeError('unsafe VRM grasp Z offset')
    if not -5.0 <= place_z_offset <= 5.0:
        raise RuntimeError('unsafe VRM placement Z offset')

    horizontal = recipe['horizontal']
    tray_open = int(horizontal['tray_pick_open']['args'][1])
    grip = int(horizontal['grip']['args'][1])
    release = int(horizontal['release']['args'][1])
    if (tray_open, grip, release) != (28, 24, 26):
        raise RuntimeError(
            f'unexpected VRM horizontal gripper values '
            f'{(tray_open, grip, release)}'
        )

    policy = recipe.get('placement_orientation_policy', {})
    if policy.get('mode') != 'align_actual_carried_axis_to_current_slot_axis':
        raise RuntimeError('VRM dynamic carried-axis policy is missing')
    gripper_axis = str(policy['gripper_axis'])
    symmetry = float(policy['symmetry_period_deg'])
    maximum_rotation = float(policy['maximum_intentional_rotation_deg'])
    tie_threshold = float(policy.get('preference_tie_threshold_deg', 5.0))
    skip_rotation = float(policy.get('skip_rotation_below_deg', 2.0))
    slot_config = {item['slot_code']: item for item in load(args.slot_file)['slots']}

    plan = []
    reference_c = 90.0
    for slot_code, detection in zip(SLOTS, detections):
        tray_surface = finite(detection['base_xyz_mm'], 3, 'VRM tray surface')
        tray_angle = float(detection['long_axis_angle_base_deg'])
        if not math.isfinite(tray_angle):
            raise RuntimeError('invalid VRM tray angle')
        pick_c = nearest_symmetric_c(tray_angle, reference_c)
        reference_c = pick_c
        pick_final = [
            float(tray_surface[0] + pick_xy_correction[0]),
            float(tray_surface[1] + pick_xy_correction[1]),
            float(tray_surface[2] + pick_z_offset),
            -180.0,
            0.0,
            float(pick_c),
        ]

        slot = slot_config.get(slot_code)
        if slot is None:
            raise RuntimeError(f'missing slot configuration for {slot_code}')
        placement = placements.get(slot_code)
        if not placement or not placement.get('placement_ready'):
            raise RuntimeError(f'{slot_code} placement is not ready')
        board_surface = finite(
            placement['surface_base_mm'], 3, f'{slot_code} board surface'
        )
        place_xy = finite(
            placement['corrected_place_xy_base_mm'], 2, f'{slot_code} place XY'
        )
        final_z = float(placement['final_tcp_z_mm'])
        if abs(final_z - (board_surface[2] + place_z_offset)) > 1e-5:
            raise RuntimeError(f'{slot_code} final Z does not match VRM common offset')
        target_axis = slot_axis_base_angle_deg(
            board_rotation, float(slot['long_axis_board_deg'])
        )
        preferred_c = slot.get('preferred_tcp_c_deg')
        orientation = plan_carried_part_orientation(
            pick_final[3:],
            target_axis,
            gripper_axis,
            symmetry,
            preferred_tcp_c_deg=preferred_c,
            preference_tie_threshold_deg=tie_threshold,
        )
        if abs(float(orientation['rotation_delta_deg'])) > maximum_rotation + 1e-6:
            raise RuntimeError(f'{slot_code} required rotation exceeds policy')
        place_abc = (
            pick_final[3:]
            if abs(float(orientation['rotation_delta_deg'])) <= skip_rotation
            else orientation['target_tcp_abc_deg']
        )
        plan.append({
            'slot_code': slot_code,
            'tray_instance_index': int(detection['instance_index']),
            'tray_surface_base_mm': tray_surface.tolist(),
            'tray_long_axis_base_deg': tray_angle,
            'pick_final_tcp': pick_final,
            'board_snapshot': str(args.board_snapshot),
            'board_surface_base_mm': board_surface.tolist(),
            'place_final_tcp': [
                float(place_xy[0]),
                float(place_xy[1]),
                final_z,
                *[float(value) for value in place_abc],
            ],
            'placement_z_offset_mm': place_z_offset,
            'placement_orientation': {
                'target_axis_base_deg': target_axis,
                'gripper_axis': gripper_axis,
                'symmetry_period_deg': symmetry,
                'maximum_intentional_rotation_deg': maximum_rotation,
                'preference_tie_threshold_deg': tie_threshold,
                'skip_rotation_below_deg': skip_rotation,
                'preferred_tcp_c_deg': preferred_c,
                'planned_from_pick': orientation,
            },
            'tray_open_position': tray_open,
            'grip_position': grip,
            'release_position': release,
        })
    return plan


def print_plan(plan: list[dict], transfer_z: float) -> None:
    print('CACHED VRM-01..05 PLAN')
    print(f'Common transfer Z: {transfer_z:.3f} mm')
    for item in plan:
        orientation = item['placement_orientation']['planned_from_pick']
        print(
            f"{item['slot_code']} <- tray#{item['tray_instance_index']} "
            f"pick={[round(value, 3) for value in item['pick_final_tcp']]} "
            f"place={[round(value, 3) for value in item['place_final_tcp']]} "
            f"rotation_delta={orientation['rotation_delta_deg']:.3f}deg"
        )


def execute(args: argparse.Namespace, plan: list[dict]) -> None:
    record = {
        'schema': 'fr5.cached_vrm_02_05_run/v1',
        'started_unix': time.time(),
        'board_snapshot': str(args.board_snapshot.resolve()),
        'tray_snapshot': str(args.tray_snapshot.resolve()),
        'transfer_z_mm': args.transfer_z_mm,
        'plan': plan,
        'completed_slots': [],
        'actual_orientation_decisions': [],
        'status': 'running',
        'resumed_after_first_pick_confirmation': bool(args.resume_after_first_pick),
    }
    atomic_write(args.run_record, record)
    rclpy.init()
    node = VrmExecutor()
    try:
        if not node.client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError('FR5 command service unavailable')
        state = node.spin_state()
        if int(state.robot_mode) != 0:
            raise RuntimeError('AUTO mode required')
        if int(state.tool_num) != 1 or int(state.work_num) != 0:
            raise RuntimeError('expected Tool1/User0')
        if int(state.robot_motion_done) != 1:
            raise RuntimeError('robot must be stationary')
        if args.resume_after_first_pick:
            if int(state.gripper_position) != 24:
                raise RuntimeError(
                    f'expected held VRM gripper position 24 for resume, got '
                    f'{state.gripper_position}'
                )
        elif int(state.gripper_position) not in (26, 28):
            raise RuntimeError(
                f'expected VRM open position 26 or 28 before start, got '
                f'{state.gripper_position}'
            )
        node.snapshot()

        for index, item in enumerate(plan, 1):
            slot = item['slot_code']
            pick = list(item['pick_final_tcp'])
            place = list(item['place_final_tcp'])
            print(f'\n=== {index}/{len(plan)} {slot} ===', flush=True)

            resume_held_pick = args.resume_after_first_pick and index == 1
            if resume_held_pick:
                current = node.snapshot()
                expected = np.asarray([pick[0], pick[1], pick[2] + 100.0])
                position_error = float(
                    np.linalg.norm(np.asarray(current[:3]) - expected)
                )
                orientation_error = math.degrees(
                    (
                        Rotation.from_euler('xyz', current[3:], degrees=True).inv()
                        * Rotation.from_euler('xyz', pick[3:], degrees=True)
                    ).magnitude()
                )
                if position_error > 1.0 or orientation_error > 1.0:
                    raise RuntimeError(
                        f'held {slot} resume pose mismatch: '
                        f'position={position_error:.3f}mm, '
                        f'orientation={orientation_error:.3f}deg'
                    )
                print(
                    f'VERIFIED {slot}: resuming from operator-confirmed centered '
                    f'pick at 100mm lift; position_error={position_error:.3f}mm',
                    flush=True,
                )
            else:
                node.vertical(args.transfer_z_mm, args.travel_speed_percent, f'{slot} pre-pick safe vertical')
                current = node.snapshot()
                pick_rotation_delta = abs(
                    ((pick[5] - current[5] + 180.0) % 360.0) - 180.0
                )
                if pick_rotation_delta <= 0.5:
                    pick[3:] = current[3:]
                    print(
                        f'VERIFIED {slot}: pick rotation skipped '
                        f'({pick_rotation_delta:.3f}deg)', flush=True
                    )
                node.move(
                    [pick[0], pick[1], args.transfer_z_mm, *pick[3:]],
                    min(args.travel_speed_percent, args.rotation_speed_percent),
                    f'{slot} combined body-turn transfer to tray',
                    linear=False,
                )
                node.vertical(pick[2] + 100.0, args.travel_speed_percent, f'{slot} pick 100mm hover')
                node.gripper(item['tray_open_position'], f'{slot} pre-pick open')
                node.vertical(pick[2], args.vertical_speed_percent, f'{slot} final pick descent')
                node.gripper(item['grip_position'], f'{slot} grasp')
                node.vertical(pick[2] + 100.0, args.vertical_speed_percent, f'{slot} post-grasp 100mm lift')
            if args.pause_after_first_pick and index == 1:
                record['status'] = 'paused_after_first_pick_for_operator_center_check'
                record['held_slot'] = slot
                record['part_held'] = True
                record['last_verified_tcp'] = node.snapshot()
                atomic_write(args.run_record, record)
                print(
                    f'PAUSED AFTER {slot} PICK AND 100MM VERTICAL LIFT; '
                    'NO BOARD TRANSFER OR ROTATION WAS COMMANDED',
                    flush=True,
                )
                return
            node.vertical(args.transfer_z_mm, args.travel_speed_percent, f'{slot} carry safe vertical')

            policy = item['placement_orientation']
            actual_abc = node.snapshot()[3:]
            actual_orientation = plan_carried_part_orientation(
                actual_abc,
                policy['target_axis_base_deg'],
                policy['gripper_axis'],
                policy['symmetry_period_deg'],
                preferred_tcp_c_deg=policy['preferred_tcp_c_deg'],
                preference_tie_threshold_deg=policy['preference_tie_threshold_deg'],
            )
            rotation_delta = float(actual_orientation['rotation_delta_deg'])
            if abs(rotation_delta) > policy['maximum_intentional_rotation_deg'] + 1e-6:
                raise RuntimeError(f'{slot} actual required rotation exceeds policy')
            rotation_skipped = abs(rotation_delta) <= policy['skip_rotation_below_deg']
            place[3:] = (
                actual_abc
                if rotation_skipped
                else actual_orientation['target_tcp_abc_deg']
            )
            record['actual_orientation_decisions'].append({
                'slot_code': slot,
                'rotation_skipped': rotation_skipped,
                **actual_orientation,
            })
            atomic_write(args.run_record, record)
            if rotation_skipped:
                print(
                    f'VERIFIED {slot}: placement rotation skipped '
                    f'({rotation_delta:.3f}deg)', flush=True
                )
            node.move(
                [place[0], place[1], args.transfer_z_mm, *place[3:]],
                min(args.travel_speed_percent, args.rotation_speed_percent),
                f'{slot} combined body-turn transfer to board',
                linear=False,
            )
            node.vertical(place[2] + 100.0, args.travel_speed_percent, f'{slot} place 100mm hover')
            node.vertical(place[2], args.vertical_speed_percent, f'{slot} final place descent')
            node.gripper(item['release_position'], f'{slot} release')
            node.vertical(place[2] + 100.0, args.vertical_speed_percent, f'{slot} post-release 100mm lift')

            record['completed_slots'].append(slot)
            record['last_verified_tcp'] = node.snapshot()
            atomic_write(args.run_record, record)
            print(f'COMPLETED {slot}', flush=True)

        record['status'] = 'complete'
        record['completed_unix'] = time.time()
        atomic_write(args.run_record, record)
        print('\nALL REMAINING VRM COMPLETED', flush=True)
    except Exception as exc:
        record['status'] = 'stopped_on_error'
        record['error'] = str(exc)
        record['stopped_unix'] = time.time()
        try:
            record['last_verified_tcp'] = node.snapshot()
        except Exception:
            pass
        atomic_write(args.run_record, record)
        raise
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--board-snapshot', type=Path, default=BOARD_SNAPSHOT)
    parser.add_argument('--tray-snapshot', type=Path, default=TRAY_SNAPSHOT)
    parser.add_argument('--recipe-file', type=Path, default=RECIPES)
    parser.add_argument('--slot-file', type=Path, default=SLOT_FILE)
    parser.add_argument('--run-record', type=Path, default=RUN_RECORD)
    parser.add_argument('--transfer-z-mm', type=float, default=387.88)
    parser.add_argument('--travel-speed-percent', type=int, default=20)
    parser.add_argument('--rotation-speed-percent', type=int, default=15)
    parser.add_argument('--vertical-speed-percent', type=int, default=10)
    parser.add_argument('--pause-after-first-pick', action='store_true')
    parser.add_argument('--resume-after-first-pick', action='store_true')
    parser.add_argument('--max-board-snapshot-age-sec', type=float, default=1800.0)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-four-vrm', action='store_true')
    args = parser.parse_args()
    if args.dry_run == args.execute:
        parser.error('choose exactly one of --dry-run or --execute')
    if args.pause_after_first_pick and args.resume_after_first_pick:
        parser.error('pause and resume modes cannot be combined')
    if args.execute != args.confirm_four_vrm:
        parser.error('execution requires --execute --confirm-four-vrm')
    if not 350.0 <= args.transfer_z_mm <= 420.0:
        parser.error('transfer Z must be 350..420 mm')
    if not all(1 <= value <= 20 for value in (
        args.travel_speed_percent,
        args.rotation_speed_percent,
        args.vertical_speed_percent,
    )):
        parser.error('test speeds must be between 1 and 20 percent')
    plan = build_plan(args)
    print_plan(plan, args.transfer_z_mm)
    if args.dry_run:
        print('DRY RUN - ROBOT DID NOT MOVE')
        return
    execute(args, plan)


if __name__ == '__main__':
    main()
