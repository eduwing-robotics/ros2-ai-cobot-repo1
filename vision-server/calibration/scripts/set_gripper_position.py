#!/usr/bin/env python3
"""Move the FR5 gripper only after explicit confirmation and verify completion."""

import argparse
import time

import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node


class GripperMover(Node):
    def __init__(self):
        super().__init__('set_gripper_position')
        self.state = None
        self.create_subscription(
            RobotNonrtState, '/nonrt_state_data', self.state_cb, 10
        )
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
        if result.split(',', 1)[0] != '0':
            raise RuntimeError(f'FR5 rejected {command}: {result}')

    def wait_gripper(self, expected_state, timeout_sec=10.0):
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is None:
                continue
            if int(self.state.gripperfaultnum) != 0 or int(self.state.grippererro) != 0:
                raise RuntimeError(
                    f'gripper fault={self.state.gripperfaultnum}, '
                    f'error={self.state.grippererro}'
                )
            if int(self.state.grip_motion_done) == expected_state:
                return
        raise RuntimeError(
            f'gripper did not reach completion state {expected_state}'
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--position', type=int, required=True)
    parser.add_argument('--gripper-index', type=int, default=1)
    parser.add_argument('--expected-motion-state', type=int, choices=(1, 2), required=True)
    parser.add_argument('--tool-id', type=int, default=1)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-gripper', action='store_true')
    args = parser.parse_args()

    if not 0 <= args.position <= 100:
        parser.error('--position must be in [0, 100]')
    if not args.execute or not args.confirm_gripper:
        parser.error('actual gripper command requires --execute --confirm-gripper')

    rclpy.init()
    node = GripperMover()
    try:
        node.wait_state()
        state = node.state
        if int(state.tool_num) != args.tool_id:
            raise RuntimeError(
                f'active tool={state.tool_num}, expected={args.tool_id}'
            )
        if int(state.robot_motion_done) != 1:
            raise RuntimeError('robot is not stationary')
        if (
            int(state.emg) != 0
            or int(state.main_error_code) != 0
            or float(state.collision_err) != 0.0
            or int(state.gripperfaultnum) != 0
            or int(state.grippererro) != 0
        ):
            raise RuntimeError('robot/gripper error state is not clear')
        if not node.client.wait_for_service(timeout_sec=3.0):
            raise RuntimeError('/fairino_remote_command_service unavailable')
        node.command(f'MoveGripper({args.gripper_index},{args.position})')
        node.wait_gripper(args.expected_motion_state)
        print(
            f'Gripper position {args.position} completed; '
            f'state={args.expected_motion_state}'
        )
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
