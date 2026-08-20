#!/usr/bin/env python3
"""One-command FR5 workflow: capture PCB slot, pick a part, carry to slot hover."""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / 'calibration'
VISION = ROOT / 'vision_assembly'
PART_TARGET = CAL / 'data/small_part_last.json'
BOARD_TARGET = VISION / 'data/board_target_last.json'


def run(command, label, timeout=90.0):
    print(f'\n=== {label} ===', flush=True)
    print(' '.join(str(value) for value in command), flush=True)
    try:
        result = subprocess.run(command, check=False, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'{label} timed out after {timeout:.1f} s') from exc
    if result.returncode != 0:
        raise RuntimeError(f'{label} failed with exit code {result.returncode}')


def teaching_move(name, args):
    run([
        str(CAL / 'run_return_to_teaching_point.sh'),
        '--point-name', name,
        '--speed-percent', str(args.travel_speed_percent),
        '--vertical-speed-percent', str(args.teaching_vertical_speed_percent),
        '--safe-clearance-mm', str(args.safe_clearance_mm),
        '--max-distance-mm', str(args.teaching_max_distance_mm),
        '--execute', '--confirm-return',
    ], f'MOVE TO TEACHING POINT {name}')


def open_gripper(position):
    command = [
        'ros2', 'service', 'call', '/fairino_remote_command_service',
        'fairino_msgs/srv/RemoteCmdInterface',
        f"{{cmd_str: 'MoveGripper(1,{position})'}}",
    ]
    result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=15.0)
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')
    if result.returncode != 0 or "cmd_res='0'" not in result.stdout:
        raise RuntimeError('gripper open command failed')


def select_board_overlay(target_slot):
    subprocess.run([
        'ros2', 'topic', 'pub', '--once', '/vision/board/selected_target',
        'std_msgs/msg/String', f"{{data: '{target_slot}'}}",
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--board-point', default='PCB')
    parser.add_argument('--part-view-point', default='ClosePin')
    parser.add_argument('--target-slot', default='right_white_brown_01')
    parser.add_argument('--part-length-mm', type=float, default=6.0)
    parser.add_argument('--part-width-mm', type=float, default=3.5)
    parser.add_argument('--part-height-mm', type=float, default=2.5)
    parser.add_argument('--part-color', default='light')
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--detection-timeout-sec', type=float, default=20.0)
    parser.add_argument('--hover-mm', type=float, default=100.0)
    parser.add_argument('--safe-clearance-mm', type=float, default=150.0)
    parser.add_argument('--teaching-max-distance-mm', type=float, default=800.0)
    parser.add_argument('--travel-speed-percent', type=int, default=50)
    parser.add_argument('--teaching-vertical-speed-percent', type=int, default=50)
    parser.add_argument('--vertical-speed-percent', type=int, default=50)
    parser.add_argument('--approach-speed-percent', type=int, default=50)
    parser.add_argument('--rotation-speed-percent', type=int, default=50)
    parser.add_argument('--final-descent-speed-percent', type=int, default=15)
    parser.add_argument('--lift-mm', type=float, default=5.0)
    parser.add_argument('--open-position', type=int, default=100)
    parser.add_argument('--close-position', type=int, default=5)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-full-cycle', action='store_true')
    args = parser.parse_args()
    if args.execute != args.confirm_full_cycle:
        parser.error('actual workflow requires --execute --confirm-full-cycle')
    if not args.execute:
        parser.error('this stateful workflow supports actual execution only')

    print('FULL PICK -> PCB SLOT HOVER WORKFLOW')
    print('ClosePin -> detect/pick/lift -> PCB view -> fresh board target -> 100 mm hover')
    print('Stops 100 mm above the slot. No board descent or gripper release.')
    grasped = False
    board_view = None
    try:
        teaching_move(args.part_view_point, args)
        try:
            run([
                str(CAL / 'run_small_part_detection.sh'),
                '--part-length-mm', str(args.part_length_mm),
                '--part-width-mm', str(args.part_width_mm),
                '--part-height-mm', str(args.part_height_mm),
                '--part-color', args.part_color,
                '--frames', str(args.frames),
                '--output-file', str(PART_TARGET),
            ], 'DETECT PART', timeout=args.detection_timeout_sec)
        except RuntimeError:
            print('\nPART NOT DETECTED; returning empty gripper to part-view point.', flush=True)
            teaching_move(args.part_view_point, args)
            raise

        print('\n=== OPEN GRIPPER ===', flush=True)
        open_gripper(args.open_position)
        run([
            str(CAL / 'run_object_approach.sh'),
            '--target-file', str(PART_TARGET),
            '--approach-offset-mm', '100',
            '--speed-percent', str(args.approach_speed_percent),
            '--descent-speed-percent', str(args.approach_speed_percent),
            '--rotation-speed-percent', str(args.rotation_speed_percent),
            '--align-part', '--gripper-axis', 'tool_y',
            '--execute', '--confirm-move',
        ], 'APPROACH PART')
        run([
            str(CAL / 'run_vertical_test.sh'), '--target-file', str(PART_TARGET),
            '--speed-percent', str(args.approach_speed_percent), '--down-mm', '100',
            '--execute', '--confirm-descent',
        ], 'DESCEND 100 MM')
        run([
            str(CAL / 'run_vertical_test.sh'), '--target-file', str(PART_TARGET),
            '--speed-percent', str(args.final_descent_speed_percent), '--down-mm', '5',
            '--execute', '--confirm-descent',
        ], 'FINAL 5 MM DESCENT')
        run([
            str(CAL / 'run_lift_grasped_part.sh'),
            '--lift-mm', str(args.lift_mm),
            '--speed-percent', str(args.final_descent_speed_percent),
            '--close-position', str(args.close_position),
            '--execute', '--confirm-grasp',
        ], 'GRASP AND LIFT')
        grasped = True

        teaching_move(args.board_point, args)

        print('\n=== START TEMPORARY BOARD VIEW ===', flush=True)
        select_board_overlay(args.target_slot)
        board_view = subprocess.Popen(
            [
                str(VISION / 'run_board_view.sh'),
                '--node-name', 'board_target_capture',
                '--target-slot', args.target_slot,
                '--target-pose-topic', '/vision/board/capture/target_pose',
                '--output-topic', '/vision/board/capture/image/compressed',
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        time.sleep(2.0)
        run([
            str(VISION / 'run_capture_board_target.sh'),
            '--topic', '/vision/board/capture/target_pose',
            '--frames', str(args.frames),
            '--target-slot', args.target_slot,
            '--output', str(BOARD_TARGET),
        ], 'CAPTURE CURRENT PCB TARGET', timeout=20.0)
        os.killpg(board_view.pid, signal.SIGINT)
        board_view.wait(timeout=5.0)
        board_view = None

        run([
            str(VISION / 'run_move_to_board_hover.sh'),
            '--target-file', str(BOARD_TARGET),
            '--hover-mm', str(args.hover_mm),
            '--safe-clearance-mm', str(args.safe_clearance_mm),
            '--speed-percent', str(args.travel_speed_percent),
            '--vertical-speed-percent', str(args.vertical_speed_percent),
            '--rotation-speed-percent', str(args.rotation_speed_percent),
            '--execute', '--confirm-carry',
        ], 'CARRY TO PCB SLOT HOVER')
        print('\nWORKFLOW COMPLETE: part is grasped at PCB slot hover; no placement descent.')
    except Exception:
        if grasped:
            print('\nSTOPPED AFTER GRASP: holding position; no automatic recovery move.', file=sys.stderr)
        raise
    finally:
        select_board_overlay('')
        if board_view is not None and board_view.poll() is None:
            os.killpg(board_view.pid, signal.SIGINT)
            try:
                board_view.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                os.killpg(board_view.pid, signal.SIGTERM)


if __name__ == '__main__':
    main()
