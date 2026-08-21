#!/usr/bin/env python3
"""Explicitly confirmed same-position grasp, lift, place, and retreat test."""

import argparse
import json
import math
import time
from pathlib import Path

import rclpy
import numpy as np
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node


class Cycle(Node):
    def __init__(self):
        super().__init__('grasp_place_cycle')
        self.state = None
        self.create_subscription(RobotNonrtState, '/nonrt_state_data', self.state_cb, 10)
        self.client = self.create_client(RemoteCmdInterface, '/fairino_remote_command_service')

    def state_cb(self, message):
        self.state = message

    def wait_state(self, timeout=8.0):
        deadline = time.monotonic() + timeout
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is not None:
                return
        raise RuntimeError('No /nonrt_state_data received')

    def command(self, command):
        request = RemoteCmdInterface.Request()
        request.cmd_str = command
        future = self.client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        if future.result() is None:
            raise RuntimeError(f'No response: {command}')
        result = str(future.result().cmd_res)
        if result.split(',', 1)[0] != '0':
            raise RuntimeError(f'FR5 rejected {command}: {result}')

    def wait_motion_done(self, target_xyz, timeout=30.0, tolerance_mm=1.0):
        deadline = time.monotonic() + timeout
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is None:
                continue
            current = np.asarray([
                self.state.cart_x_cur_pos,
                self.state.cart_y_cur_pos,
                self.state.cart_z_cur_pos,
            ], dtype=float)
            error = float(np.linalg.norm(current - np.asarray(target_xyz, dtype=float)))
            # MoveCart with blendT=-1 is blocking. The service response can
            # arrive after robot_motion_done has already returned to 1, so do
            # not require observing the transient 0 state.
            if int(self.state.robot_motion_done) == 1 and error <= tolerance_mm:
                return
        raise RuntimeError('Robot motion completion/target verification timeout')

    def wait_gripper_done(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is not None and int(self.state.grip_motion_done) in (1, 2):
                return int(self.state.grip_motion_done)
        raise RuntimeError('Gripper completion timeout')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-file', type=Path, required=True)
    parser.add_argument('--max-target-age-sec', type=float, default=900.0)
    parser.add_argument('--max-target-xy-error-mm', type=float, default=10.0)
    parser.add_argument('--lift-mm', type=float, default=20.0)
    parser.add_argument('--retreat-mm', type=float, default=20.0)
    parser.add_argument('--motion-speed-percent', type=int, default=10)
    parser.add_argument('--gripper-index', type=int, default=1)
    parser.add_argument('--close-position', type=int, default=5)
    parser.add_argument('--open-position', type=int, default=100)
    parser.add_argument('--tool-id', type=int, default=1)
    parser.add_argument('--user-id', type=int, default=0)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-gripper', action='store_true')
    parser.add_argument('--confirm-cycle', action='store_true')
    parser.add_argument(
        '--resume-after-lift', action='store_true',
        help='Current pose is already lifted with the part: lower, open, and retreat only.',
    )
    args = parser.parse_args()

    if not 5.0 <= args.lift_mm <= 50.0 or not 5.0 <= args.retreat_mm <= 50.0:
        parser.error('--lift-mm and --retreat-mm must be between 5 and 50')
    if not 1 <= args.motion_speed_percent <= 50:
        parser.error('--motion-speed-percent must be between 1 and 50')
    if not 0 <= args.open_position <= 100 or not 0 <= args.close_position <= 100:
        parser.error('gripper positions must be between 0 and 100')
    confirmations = (args.execute, args.confirm_gripper, args.confirm_cycle)
    if any(confirmations) and not all(confirmations):
        parser.error('actual cycle requires --execute --confirm-gripper --confirm-cycle')
    if args.dry_run and args.execute:
        parser.error('--dry-run and --execute cannot be combined')

    try:
        payload = json.loads(args.target_file.read_text(encoding='utf-8'))
        age = time.time() - float(payload['timestamp_unix'])
        part_base = [float(value) for value in payload['part_center_base_mm']]
    except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.error(f'cannot read target file: {exc}')
    if age < -5.0 or age > args.max_target_age_sec:
        parser.error(f'target file is stale ({age:.1f} s); detect the part again')

    rclpy.init()
    node = Cycle()
    try:
        node.wait_state()
        state = node.state
        if int(state.tool_num) != args.tool_id:
            raise RuntimeError(f'active tool={state.tool_num}, expected={args.tool_id}')
        if int(state.robot_motion_done) != 1:
            raise RuntimeError('robot is not stationary')
        if int(state.emg) != 0 or int(state.main_error_code) != 0 or float(state.collision_err) != 0.0:
            raise RuntimeError('robot emergency/error/collision state is not clear')
        if args.execute and int(state.robot_mode) != 0:
            raise RuntimeError(f'robot_mode={state.robot_mode}; AUTO mode 0 required')

        pick = [
            float(state.cart_x_cur_pos), float(state.cart_y_cur_pos),
            float(state.cart_z_cur_pos), float(state.cart_a_cur_pos),
            float(state.cart_b_cur_pos), float(state.cart_c_cur_pos),
        ]
        xy_error = math.hypot(pick[0] - part_base[0], pick[1] - part_base[1])
        if xy_error > args.max_target_xy_error_mm:
            raise RuntimeError(
                f'TCP is not at detected part XY: difference={xy_error:.1f} mm'
            )
        lifted = list(pick); lifted[2] += args.lift_mm
        retreated = list(pick); retreated[2] += args.retreat_mm

        print('GRASP/PLACE CYCLE AT CURRENT XY - NO HORIZONTAL TRANSFER')
        print(f'Pick pose: {[round(v, 3) for v in pick]}')
        print(f'Detected part/Base: {[round(v, 3) for v in part_base]}')
        print(f'XY difference: {xy_error:.3f} mm')
        if args.resume_after_lift:
            print(f'RESUME MODE: lower {-args.lift_mm:.1f} mm, open={args.open_position}, retreat=+{args.retreat_mm:.1f} mm')
        else:
            print(f'1. Close gripper: position={args.close_position}')
            print('   Gripper device=1, speed=50%, torque=1%, max_time=3000 ms')
            print(f'2. Lift Base Z: +{args.lift_mm:.1f} mm')
            print('3. Return to the same pick Z')
            print(f'4. Open gripper: position={args.open_position}')
            print(f'5. Retreat Base Z: +{args.retreat_mm:.1f} mm')
        if not args.execute:
            print('DRY RUN - ROBOT AND GRIPPER DID NOT MOVE')
            return

        if not node.client.wait_for_service(timeout_sec=3.0):
            raise RuntimeError('/fairino_remote_command_service unavailable')
        def move(pose, name):
            command = (
                f'MoveCart({pose[0]:.3f},{pose[1]:.3f},{pose[2]:.3f},'
                f'{pose[3]:.3f},{pose[4]:.3f},{pose[5]:.3f},'
                f'{args.tool_id},{args.user_id},{args.motion_speed_percent},'
                f'{args.motion_speed_percent},{args.motion_speed_percent},-1,-1)'
            )
            print(f'{name}: {command}')
            node.command(command)
            node.wait_motion_done(pose[:3])

        if args.resume_after_lift:
            place = list(pick); place[2] -= args.lift_mm
            retreat = list(place); retreat[2] += args.retreat_mm
            move(place, 'Resume: return to place')
            node.command(f'MoveGripper({args.gripper_index},{args.open_position})')
            node.wait_gripper_done()
            print('Gripper open completed')
            move(retreat, 'Resume: retreat')
            print('Resumed place/retreat completed')
            return

        node.command(f'MoveGripper({args.gripper_index},{args.close_position})')
        grip_state = node.wait_gripper_done()
        print(f'Gripper close completed: state={grip_state}')

        move(lifted, 'Lift')
        move(pick, 'Return to place')
        node.command(f'MoveGripper({args.gripper_index},{args.open_position})')
        node.wait_gripper_done()
        print('Gripper open completed')
        move(retreated, 'Retreat')
        print('Grasp/place cycle completed')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
