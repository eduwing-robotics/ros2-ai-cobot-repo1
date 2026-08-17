#!/usr/bin/env python3
"""Perform one explicitly confirmed Base-Z-only FR5 test move."""

import argparse
import json
import math
import time
from pathlib import Path

import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node


class VerticalTest(Node):
    def __init__(self):
        super().__init__('move_vertical_test')
        self.state = None
        self.create_subscription(RobotNonrtState, '/nonrt_state_data', self.state_cb, 10)
        self.client = self.create_client(
            RemoteCmdInterface, '/fairino_remote_command_service'
        )

    def state_cb(self, message):
        self.state = message

    def wait_state(self, timeout_sec=8.0):
        deadline = time.monotonic() + timeout_sec
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
            raise RuntimeError(f'No response for command: {command}')
        result = str(future.result().cmd_res)
        if result != '0':
            raise RuntimeError(f'FR5 rejected command: {command}, result={result}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--down-mm', type=float, default=100.0)
    parser.add_argument('--target-file', type=Path, required=True)
    parser.add_argument('--max-target-age-sec', type=float, default=300.0)
    parser.add_argument('--max-target-xy-error-mm', type=float, default=10.0)
    parser.add_argument('--speed-percent', type=int, default=15)
    parser.add_argument('--tool-id', type=int, default=1)
    parser.add_argument('--user-id', type=int, default=0)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-descent', action='store_true')
    args = parser.parse_args()

    if not 0.1 <= args.down_mm <= 100.0:
        parser.error('--down-mm must be between 0.1 and 100.0 for this test')
    if not 1 <= args.speed_percent <= 50:
        parser.error('--speed-percent must be between 1 and 50 for this test')
    if args.execute != args.confirm_descent:
        parser.error('실제 하강에는 --execute와 --confirm-descent가 모두 필요합니다')
    if args.dry_run and args.execute:
        parser.error('--dry-run and --execute cannot be combined')

    rclpy.init()
    node = VerticalTest()
    try:
        try:
            target_payload = json.loads(args.target_file.read_text(encoding='utf-8'))
            target_age = time.time() - float(target_payload['timestamp_unix'])
            detected_base = [
                float(value) for value in target_payload['part_center_base_mm']
            ]
        except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f'Cannot load target file: {exc}') from exc
        if target_age < -5.0 or target_age > args.max_target_age_sec:
            raise RuntimeError(
                f'Target file is stale ({target_age:.1f} s); detect the part again'
            )
        node.wait_state()
        state = node.state
        if int(state.tool_num) != args.tool_id:
            raise RuntimeError(
                f'active tool={state.tool_num}, expected tool={args.tool_id}'
            )
        if int(state.emg) != 0:
            raise RuntimeError('Emergency stop is active')
        if int(state.main_error_code) != 0 or float(state.collision_err) != 0.0:
            raise RuntimeError(
                f'robot error: main={state.main_error_code}, collision={state.collision_err}'
            )
        if int(state.robot_motion_done) != 1:
            raise RuntimeError('Robot is not stationary')
        if args.execute and int(state.robot_mode) != 0:
            raise RuntimeError(f'robot_mode={state.robot_mode}; AUTO mode 0 required')

        pose = [
            float(state.cart_x_cur_pos), float(state.cart_y_cur_pos),
            float(state.cart_z_cur_pos), float(state.cart_a_cur_pos),
            float(state.cart_b_cur_pos), float(state.cart_c_cur_pos),
        ]
        xy_error = math.hypot(
            pose[0] - detected_base[0], pose[1] - detected_base[1]
        )
        if xy_error > args.max_target_xy_error_mm:
            raise RuntimeError(
                f'TCP is not over the detected part: XY difference={xy_error:.1f} mm, '
                f'limit={args.max_target_xy_error_mm:.1f} mm. Run object approach first.'
            )
        target = list(pose)
        target[2] -= args.down_mm
        if not all(math.isfinite(value) for value in target):
            raise RuntimeError('Target contains NaN/Inf')

        print('VERTICAL DESCENT TEST - BASE Z ONLY')
        print(f'Current TCP/Base: {[round(value, 3) for value in pose]}')
        print(f'Detected part/Base: {[round(value, 3) for value in detected_base]}')
        print(f'Current-to-part XY difference: {xy_error:.3f} mm')
        print(f'Descent: {args.down_mm:.3f} mm')
        print(f'Target TCP/Base: {[round(value, 3) for value in target]}')
        print(f'Speed: {args.speed_percent}%')
        print('XY and orientation are preserved; gripper will not move.')
        if not args.execute:
            print('DRY RUN - ROBOT DID NOT MOVE')
            return

        if not node.client.wait_for_service(timeout_sec=3.0):
            raise RuntimeError('/fairino_remote_command_service unavailable')
        node.command(f'SetSpeed({args.speed_percent})')
        command = (
            f'MoveCart({target[0]:.3f},{target[1]:.3f},{target[2]:.3f},'
            f'{target[3]:.3f},{target[4]:.3f},{target[5]:.3f},'
            f'{args.tool_id},{args.user_id},{args.speed_percent},'
            f'{args.speed_percent},{args.speed_percent},-1,-1)'
        )
        print(f'Sending: {command}')
        node.command(command)
        print('100 mm descent completed; no gripper command was sent.')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
