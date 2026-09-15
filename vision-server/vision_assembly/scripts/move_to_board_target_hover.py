#!/usr/bin/env python3
"""Move a grasped part to a saved board target hover pose; no descent/release."""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import rclpy
from scipy.spatial.transform import Rotation
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node


class HoverMover(Node):
    def __init__(self):
        super().__init__('move_to_board_target_hover')
        self.state = None
        self.create_subscription(RobotNonrtState, '/nonrt_state_data', self.cb, 10)
        self.client = self.create_client(RemoteCmdInterface, '/fairino_remote_command_service')

    def cb(self, message): self.state = message

    def wait_state(self):
        deadline = time.monotonic() + 8.0
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is not None: return
        raise RuntimeError('No robot state')

    def command(self, text):
        request = RemoteCmdInterface.Request(); request.cmd_str = text
        future = self.client.call_async(request); rclpy.spin_until_future_complete(self, future)
        result = str(future.result().cmd_res)
        if result.split(',', 1)[0] != '0': raise RuntimeError(f'FR5 rejected {text}: {result}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-file', type=Path, required=True)
    parser.add_argument('--hover-mm', type=float, default=100.0)
    parser.add_argument('--safe-clearance-mm', type=float, default=150.0)
    parser.add_argument('--speed-percent', type=int, default=50)
    parser.add_argument('--vertical-speed-percent', type=int, default=50)
    parser.add_argument('--rotation-speed-percent', type=int, default=50)
    parser.add_argument(
        '--placement-long-axis-board-deg', type=float,
        help='Override slot recipe angle; 0 is PCB horizontal/X and 90 is vertical/Y.',
    )
    parser.add_argument('--physical-board-file', type=Path, default=Path(__file__).resolve().parents[1] / 'config/physical_board.json')
    parser.add_argument('--max-target-age-sec', type=float, default=1800.0)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-carry', action='store_true')
    args = parser.parse_args()
    if args.execute != args.confirm_carry: parser.error('requires --execute --confirm-carry')
    if not 50 <= args.hover_mm <= 150: parser.error('--hover-mm must be 50..150')
    payload = json.loads(args.target_file.read_text(encoding='utf-8'))
    target_slot = str(payload['target_slot'])
    physical = json.loads(args.physical_board_file.read_text(encoding='utf-8'))
    slots = physical['physical_slot_overrides']['right_white_brown']['slots']
    slot = next((item for item in slots if item['slot_id'] == target_slot), None)
    if args.placement_long_axis_board_deg is None:
        if slot is None or 'long_axis_board_deg' not in slot:
            raise RuntimeError(f'no placement orientation configured for {target_slot}')
        placement_angle_deg = float(slot['long_axis_board_deg'])
    else:
        placement_angle_deg = float(args.placement_long_axis_board_deg)
    age = time.time() - float(payload['timestamp_unix'])
    if age > args.max_target_age_sec: raise RuntimeError(f'board target stale ({age:.1f}s); recapture it')
    target_surface = [float(v) for v in payload['position_base_mm']]
    board_quaternion = np.asarray(payload['orientation_xyzw'], dtype=float)
    if not np.all(np.isfinite(board_quaternion)) or np.linalg.norm(board_quaternion) < 0.9:
        raise RuntimeError('invalid board target orientation')
    compensation_board_mm = np.asarray(
        slot.get('place_tcp_compensation_board_mm', [0.0, 0.0]) if slot else [0.0, 0.0],
        dtype=float,
    )
    rclpy.init(); node = HoverMover()
    try:
        node.wait_state(); state = node.state
        if int(state.robot_mode) != 0: raise RuntimeError('AUTO mode required')
        if int(state.emg) != 0 or int(state.main_error_code) != 0: raise RuntimeError('robot error state')
        current = [state.cart_x_cur_pos, state.cart_y_cur_pos, state.cart_z_cur_pos,
                   state.cart_a_cur_pos, state.cart_b_cur_pos, state.cart_c_cur_pos]
        R_base_board = Rotation.from_quat(board_quaternion).as_matrix()
        compensation_base_mm = R_base_board @ np.asarray([
            compensation_board_mm[0], compensation_board_mm[1], 0.0
        ])
        commanded_surface = (
            np.asarray(target_surface, dtype=float) + compensation_base_mm
        ).tolist()
        target = [commanded_surface[0], commanded_surface[1], commanded_surface[2] + args.hover_mm]
        if math.dist(current[:3], target) > 650: raise RuntimeError('target distance exceeds 650 mm')
        safe_z = max(float(current[2]), target[2] + args.safe_clearance_mm)
        angle = math.radians(placement_angle_deg)
        desired_long_axis = (
            math.cos(angle) * R_base_board[:, 0]
            + math.sin(angle) * R_base_board[:, 1]
        )
        desired_long_axis[2] = 0.0
        desired_long_axis /= np.linalg.norm(desired_long_axis)
        current_rotation = Rotation.from_euler('xyz', current[3:], degrees=True).as_matrix()
        tool_z = current_rotation[:, 2]
        if tool_z[2] > 0.0:
            tool_z = -tool_z
        tool_z /= np.linalg.norm(tool_z)
        tool_x = np.cross(desired_long_axis, tool_z)
        tool_x /= np.linalg.norm(tool_x)
        tool_y = np.cross(tool_z, tool_x)
        tool_y /= np.linalg.norm(tool_y)
        target_abc = Rotation.from_matrix(
            np.column_stack((tool_x, tool_y, tool_z))
        ).as_euler('xyz', degrees=True).tolist()
        waypoints = [
            ([current[0], current[1], safe_z, current[3], current[4], current[5]], args.vertical_speed_percent, 'vertical raise'),
            ([current[0], current[1], safe_z, *target_abc], args.rotation_speed_percent, 'PCB horizontal orientation'),
            ([target[0], target[1], safe_z, *target_abc], args.speed_percent, 'horizontal positioning'),
            ([target[0], target[1], target[2], *target_abc], args.vertical_speed_percent, 'vertical hover approach'),
        ]
        print('GRASPED PART -> BOARD TARGET HOVER ONLY')
        print('Board surface/Base [mm]:', [round(v, 3) for v in target_surface])
        print('Placement TCP compensation/Board [mm]:', np.round(compensation_board_mm, 3).tolist())
        print('Commanded surface/Base [mm]:', [round(v, 3) for v in commanded_surface])
        print('Hover target/Base [mm]:', [round(v, 3) for v in target])
        print(f'Placement slot: {target_slot}')
        print(f'Placement long axis: PCB X + {placement_angle_deg:.1f} deg')
        print('Target TCP ABC [deg]:', [round(v, 3) for v in target_abc])
        for index, (pose, speed, label) in enumerate(waypoints, 1):
            print(f'Stage {index}/{len(waypoints)} {label}:', [round(float(v), 3) for v in pose], f'speed={speed}%')
        if not args.execute:
            print('DRY RUN - ROBOT DID NOT MOVE'); return
        if not node.client.wait_for_service(timeout_sec=3): raise RuntimeError('command service unavailable')
        for index, (pose, speed, label) in enumerate(waypoints, 1):
            command = (f'MoveCart({pose[0]:.3f},{pose[1]:.3f},{pose[2]:.3f},'
                       f'{pose[3]:.3f},{pose[4]:.3f},{pose[5]:.3f},1,0,'
                       f'{speed},{speed},{speed},-1,-1)')
            print(f'Sending stage {index}/{len(waypoints)} ({label}): {command}'); node.command(command)
        print('Arrived at board target hover. No descent or gripper release was commanded.')
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()


if __name__ == '__main__': main()
