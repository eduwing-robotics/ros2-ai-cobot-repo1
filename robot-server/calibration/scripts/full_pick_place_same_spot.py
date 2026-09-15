#!/usr/bin/env python3
"""Run the validated small-part pick/place-at-same-spot workflow end to end."""

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'data/small_part_last.json'


def run(command, label, timeout=None):
    print(f'\n=== {label} ===', flush=True)
    print(' '.join(str(value) for value in command), flush=True)
    try:
        completed = subprocess.run(command, check=False, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'{label} timed out after {timeout:.1f} s') from exc
    if completed.returncode != 0:
        raise RuntimeError(f'{label} failed with exit code {completed.returncode}')


def gripper_open(position):
    command = [
        'ros2', 'service', 'call', '/fairino_remote_command_service',
        'fairino_msgs/srv/RemoteCmdInterface',
        f"{{cmd_str: 'MoveGripper(1,{position})'}}",
    ]
    print('\n=== OPEN GRIPPER BEFORE APPROACH ===', flush=True)
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    print(completed.stdout, end='')
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end='')
    if completed.returncode != 0 or "cmd_res='0'" not in completed.stdout:
        raise RuntimeError('gripper open command failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--part-length-mm', type=float, default=6.0)
    parser.add_argument('--part-width-mm', type=float, default=3.5)
    parser.add_argument('--part-height-mm', type=float, default=2.5)
    parser.add_argument('--part-color', choices=('light', 'orange', 'brown', 'any'), default='light')
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--detection-timeout-sec', type=float, default=15.0)
    parser.add_argument('--approach-offset-mm', type=float, default=100.0)
    parser.add_argument('--extra-descent-mm', type=float, default=5.0)
    parser.add_argument('--xy-speed-percent', type=int, default=40)
    parser.add_argument('--vertical-speed-percent', type=int, default=40)
    parser.add_argument('--grasp-descent-speed-percent', type=int, default=15)
    parser.add_argument('--rotation-speed-percent', type=int, default=50)
    parser.add_argument('--lift-mm', type=float, default=50.0)
    parser.add_argument('--retreat-mm', type=float, default=50.0)
    parser.add_argument('--cycle-speed-percent', type=int, default=40)
    parser.add_argument('--gripper-open-position', type=int, default=100)
    parser.add_argument('--gripper-close-position', type=int, default=5)
    parser.add_argument('--gripper-axis', choices=('tool_x', 'tool_y'), default='tool_y')
    parser.add_argument('--return-point', default='TrayHome')
    parser.add_argument('--return-safe-clearance-mm', type=float, default=100.0)
    parser.add_argument('--no-return', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-full-cycle', action='store_true')
    args = parser.parse_args()

    if args.execute != args.confirm_full_cycle:
        parser.error('실제 전체 동작에는 --execute와 --confirm-full-cycle이 모두 필요합니다')
    if args.dry_run and args.execute:
        parser.error('--dry-run and --execute cannot be combined')
    if args.execute:
        parser.error('legacy continuous-descent workflow is disabled; use vision_assembly/run_safe_part_pick.sh prepare and descend')
    if not 0.0 <= args.extra_descent_mm <= 10.0:
        parser.error('--extra-descent-mm must be between 0 and 10')
    if not 1 <= args.grasp_descent_speed_percent <= 50:
        parser.error('--grasp-descent-speed-percent must be between 1 and 50')

    print('FULL SMALL-PART PICK/PLACE-AT-SAME-SPOT WORKFLOW')
    print('1 detect, 2 open, 3 approach, 4 descend, 5 grasp/lift/place/retreat')
    print('No horizontal transfer to a different placement target is included.')

    detection_command = [
        str(ROOT / 'run_small_part_detection.sh'),
        '--part-length-mm', str(args.part_length_mm),
        '--part-width-mm', str(args.part_width_mm),
        '--part-height-mm', str(args.part_height_mm),
        '--part-color', args.part_color,
        '--frames', str(args.frames),
        '--output-file', str(TARGET),
    ]
    try:
        run(detection_command, '1/5 DETECT CURRENT PART', timeout=args.detection_timeout_sec)
    except RuntimeError:
        if args.execute:
            print('\nPART NOT DETECTED - returning empty gripper to safe observation point', flush=True)
            run([
                str(ROOT / 'run_return_to_teaching_point.sh'),
                '--point-name', args.return_point,
                '--speed-percent', str(args.xy_speed_percent),
                '--vertical-speed-percent', str(args.vertical_speed_percent),
                '--safe-clearance-mm', str(args.return_safe_clearance_mm),
                '--execute', '--confirm-return',
            ], f'FAIL-SAFE RETURN TO {args.return_point}')
        raise

    approach = [
        str(ROOT / 'run_object_approach.sh'),
        '--target-file', str(TARGET),
        '--approach-offset-mm', str(args.approach_offset_mm),
        '--speed-percent', str(args.xy_speed_percent),
        '--descent-speed-percent', str(args.vertical_speed_percent),
        '--rotation-speed-percent', str(args.rotation_speed_percent),
        '--align-part', '--gripper-axis', args.gripper_axis,
    ]

    if not args.execute:
        run(approach + ['--dry-run'], '2/5 APPROACH DRY RUN')
        print('\nDRY RUN STOP: subsequent descent depends on the robot reaching the approach pose.')
        print('ROBOT AND GRIPPER DID NOT MOVE.')
        return

    gripper_open(args.gripper_open_position)
    run(approach + ['--execute', '--confirm-move'], '2/5 MOVE TO SAFE APPROACH')

    descent_base = [
        str(ROOT / 'run_vertical_test.sh'),
        '--target-file', str(TARGET),
        '--speed-percent', str(args.vertical_speed_percent),
        '--execute', '--confirm-descent',
    ]
    run(descent_base + ['--down-mm', str(args.approach_offset_mm)], '3/5 DESCEND APPROACH OFFSET')
    if args.extra_descent_mm > 0.0:
        grasp_descent = [
            str(ROOT / 'run_vertical_test.sh'),
            '--target-file', str(TARGET),
            '--speed-percent', str(args.grasp_descent_speed_percent),
            '--execute', '--confirm-descent',
            '--down-mm', str(args.extra_descent_mm),
        ]
        run(grasp_descent, '4/5 DESCEND TO GRASP HEIGHT')
    else:
        print('\n=== 4/5 EXTRA DESCENT SKIPPED ===')

    run([
        str(ROOT / 'run_grasp_place_cycle.sh'),
        '--target-file', str(TARGET),
        '--lift-mm', str(args.lift_mm),
        '--retreat-mm', str(args.retreat_mm),
        '--motion-speed-percent', str(args.cycle_speed_percent),
        '--close-position', str(args.gripper_close_position),
        '--open-position', str(args.gripper_open_position),
        '--execute', '--confirm-gripper', '--confirm-cycle',
    ], '5/5 GRASP, LIFT, PLACE, RETREAT')
    if not args.no_return:
        run([
            str(ROOT / 'run_return_to_teaching_point.sh'),
            '--point-name', args.return_point,
            '--speed-percent', str(args.xy_speed_percent),
            '--vertical-speed-percent', str(args.vertical_speed_percent),
            '--safe-clearance-mm', str(args.return_safe_clearance_mm),
            '--execute', '--confirm-return',
        ], f'6/6 RETURN TO {args.return_point}')
    else:
        print('\n=== 6/6 RETURN SKIPPED ===')
    print('\nFULL SAME-SPOT PICK/PLACE TEST COMPLETED')


if __name__ == '__main__':
    main()
