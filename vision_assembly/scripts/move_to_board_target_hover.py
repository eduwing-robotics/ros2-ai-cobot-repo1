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

from placement_orientation import plan_carried_part_orientation


PART_TYPE_BY_SLOT_PREFIX = {
    "GPU": "gpu",
    "HBM": "hbm",
    "PM": "long_orange",
    "VRM": "black_block",
    "IND": "marked_white",
    "CAP": "right_white_brown",
}


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

    @staticmethod
    def state_joints(state):
        return np.asarray([
            state.j1_cur_pos, state.j2_cur_pos, state.j3_cur_pos,
            state.j4_cur_pos, state.j5_cur_pos, state.j6_cur_pos,
        ], dtype=float)

    @staticmethod
    def safety_error(state):
        checks = {
            'emg': state.emg,
            'abnormal_stop': state.abnormal_stop,
            'main_error': state.main_error_code,
            'sub_error': state.sub_error_code,
            'collision': state.collision_err,
            'alarm': state.alarm,
            'motion_alarm': state.motionalarm,
            'safety_plane': state.safetyplanealarm,
        }
        active = [f'{key}={value}' for key, value in checks.items() if float(value) != 0.0]
        return ', '.join(active) if active else None

    def service(self, text):
        request = RemoteCmdInterface.Request(); request.cmd_str = text
        future = self.client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=90.0)
        if not future.done() or future.result() is None:
            raise RuntimeError(f'FR5 command timeout: {text}')
        result = str(future.result().cmd_res)
        if result.split(',', 1)[0] != '0':
            raise RuntimeError(f'FR5 rejected {text}: {result}')
        return result

    @staticmethod
    def response_values(result, count, label):
        fields = result.split(',')
        if not fields or fields[0] != '0' or len(fields) < count + 1:
            raise RuntimeError(f'invalid {label} response: {result}')
        values = np.asarray([float(value) for value in fields[1:count + 1]])
        if not np.all(np.isfinite(values)):
            raise RuntimeError(f'non-finite {label} response: {result}')
        return values

    def referenced_ik(self, target_pose, max_joint_step_deg=95.0):
        state = self.state
        if state is None or int(state.robot_motion_done) != 1:
            raise RuntimeError('robot must be stationary before planning a waypoint')
        error = self.safety_error(state)
        if error:
            raise RuntimeError('robot safety state is not clear: ' + error)
        reference = self.state_joints(state)
        soft = self.response_values(
            self.service('GetJointSoftLimitDeg(1)'), 12, 'joint soft-limit'
        )
        negative, positive = soft[:6], soft[6:]
        safety = self.response_values(
            self.service('GetSafetyStopState()'), 2, 'safety-stop'
        )
        if np.any(safety != 0.0):
            raise RuntimeError(f'safety stop is active: {safety.astype(int).tolist()}')
        request = 'GetInverseKinRef(' + ','.join(
            f'{value:.6f}' for value in [0.0, *target_pose, *reference.tolist()]
        ) + ')'
        joints = self.response_values(self.service(request), 6, 'referenced IK')
        margins = np.minimum(joints - negative, positive - joints)
        if np.any(margins < 10.0):
            joint = int(np.argmin(margins)) + 1
            raise RuntimeError(f'J{joint} soft-limit margin is below 10 deg')
        delta = np.abs(joints - reference)
        if np.any(delta > max_joint_step_deg):
            joint = int(np.argmax(delta)) + 1
            raise RuntimeError(
                f'J{joint} branch change {delta[joint - 1]:.1f} deg exceeds '
                f'{max_joint_step_deg:.1f} deg'
            )
        return joints

    def wait_pose(self, target_pose, target_joints, timeout=90.0):
        target_xyz = np.asarray(target_pose[:3], dtype=float)
        target_rotation = Rotation.from_euler('xyz', target_pose[3:], degrees=True)
        deadline = time.monotonic() + timeout
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            state = self.state
            if state is None:
                continue
            error = self.safety_error(state)
            if error:
                raise RuntimeError('robot safety fault during carry: ' + error)
            current_xyz = np.asarray([
                state.cart_x_cur_pos, state.cart_y_cur_pos, state.cart_z_cur_pos,
            ], dtype=float)
            current_rotation = Rotation.from_euler('xyz', [
                state.cart_a_cur_pos, state.cart_b_cur_pos, state.cart_c_cur_pos,
            ], degrees=True)
            angle_error = math.degrees(
                (current_rotation.inv() * target_rotation).magnitude()
            )
            joint_error = float(np.max(np.abs(self.state_joints(state) - target_joints)))
            if (int(state.robot_motion_done) == 1
                    and float(np.linalg.norm(current_xyz - target_xyz)) <= 1.0
                    and angle_error <= 1.0 and joint_error <= 1.0):
                return
        raise RuntimeError('waypoint pose/joint verification timeout; next stage blocked')

    def move(self, target_pose, speed, label, linear):
        joints = self.referenced_ik(target_pose)
        define = 'JNTPoint(1,' + ','.join(f'{value:.6f}' for value in joints) + ')'
        motion = 'MoveL' if linear else 'MoveJ'
        command = f'{motion}(JNT1,{speed},1,0)'
        print(f'Sending {label}: {command}; joints={np.round(joints, 3).tolist()}')
        self.service(define)
        self.service(command)
        self.wait_pose(target_pose, joints)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-file', type=Path, required=True)
    parser.add_argument('--hover-mm', type=float, default=100.0)
    parser.add_argument('--safe-clearance-mm', type=float, default=150.0)
    parser.add_argument('--speed-percent', type=int, default=40)
    parser.add_argument('--vertical-speed-percent', type=int, default=20)
    parser.add_argument('--rotation-speed-percent', type=int, default=40)
    parser.add_argument(
        '--placement-long-axis-board-deg', type=float,
        help='Override slot recipe angle; 0 is PCB horizontal/X and 90 is vertical/Y.',
    )
    parser.add_argument('--physical-board-file', type=Path, default=Path(__file__).resolve().parents[1] / 'config/physical_board.json')
    parser.add_argument('--slot-layout-file', type=Path, default=Path(__file__).resolve().parents[1] / 'config/assembly_slots_r1.json')
    parser.add_argument('--recipe-file', type=Path, default=Path(__file__).resolve().parents[1] / 'config/part_gripper_recipes.json')
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
    slot_layout = json.loads(args.slot_layout_file.read_text(encoding='utf-8'))
    assembly_slot = next(
        (item for item in slot_layout['slots'] if item['slot_code'] == target_slot),
        None,
    )
    orientation_slot = assembly_slot if assembly_slot is not None else slot
    if args.placement_long_axis_board_deg is None:
        if orientation_slot is None or 'long_axis_board_deg' not in orientation_slot:
            raise RuntimeError(f'no placement orientation configured for {target_slot}')
        placement_angle_deg = float(orientation_slot['long_axis_board_deg'])
    else:
        placement_angle_deg = float(args.placement_long_axis_board_deg)
    age = time.time() - float(payload['timestamp_unix'])
    if age > args.max_target_age_sec: raise RuntimeError(f'board target stale ({age:.1f}s); recapture it')
    target_surface = [float(v) for v in payload['position_base_mm']]
    board_quaternion = np.asarray(payload['orientation_xyzw'], dtype=float)
    if not np.all(np.isfinite(board_quaternion)) or np.linalg.norm(board_quaternion) < 0.9:
        raise RuntimeError('invalid board target orientation')
    compensation_source = assembly_slot if assembly_slot is not None else slot
    compensation_board_mm = np.asarray(
        compensation_source.get('place_tcp_compensation_board_mm', [0.0, 0.0])
        if compensation_source else [0.0, 0.0],
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
        target_axis_base_deg = math.degrees(
            math.atan2(desired_long_axis[1], desired_long_axis[0])
        )
        slot_prefix = target_slot.split('-', 1)[0].upper()
        part_type = PART_TYPE_BY_SLOT_PREFIX.get(slot_prefix)
        if part_type is None:
            raise RuntimeError(f'cannot infer part type from slot {target_slot}')
        recipes = json.loads(args.recipe_file.read_text(encoding='utf-8'))['parts']
        policy = recipes[part_type].get('placement_orientation_policy', {})
        if policy.get('mode') != 'align_actual_carried_axis_to_current_slot_axis':
            raise RuntimeError(f'no dynamic carried-axis orientation policy for {part_type}')
        preferred_c = (
            orientation_slot.get('preferred_tcp_c_deg')
            if orientation_slot is not None else None
        )
        orientation_plan = plan_carried_part_orientation(
            current[3:],
            target_axis_base_deg,
            str(policy['gripper_axis']),
            float(policy['symmetry_period_deg']),
            preferred_tcp_c_deg=preferred_c,
            preference_tie_threshold_deg=float(
                policy.get('preference_tie_threshold_deg', 5.0)
            ),
        )
        rotation_delta = float(orientation_plan['rotation_delta_deg'])
        maximum_rotation = float(policy['maximum_intentional_rotation_deg'])
        if abs(rotation_delta) > maximum_rotation + 1e-6:
            raise RuntimeError(
                f'required carried-part rotation {rotation_delta:.3f} deg exceeds '
                f'{maximum_rotation:.3f} deg policy'
            )
        skip_rotation = abs(rotation_delta) <= float(
            policy.get('skip_rotation_below_deg', 0.5)
        )
        target_abc = (
            current[3:]
            if skip_rotation else orientation_plan['target_tcp_abc_deg']
        )
        waypoints = [
            ([current[0], current[1], safe_z, current[3], current[4], current[5]], args.vertical_speed_percent, 'vertical raise', True),
        ]
        if not skip_rotation:
            waypoints.append(
                ([current[0], current[1], safe_z, *target_abc], args.rotation_speed_percent, 'minimal required carried-part rotation', False)
            )
        waypoints.extend([
            ([target[0], target[1], safe_z, *target_abc], args.speed_percent, 'horizontal positioning', False),
            ([target[0], target[1], target[2], *target_abc], args.vertical_speed_percent, 'vertical hover approach', True),
        ])
        print('GRASPED PART -> BOARD TARGET HOVER ONLY')
        print('Board surface/Base [mm]:', [round(v, 3) for v in target_surface])
        print('Placement TCP compensation/Board [mm]:', np.round(compensation_board_mm, 3).tolist())
        print('Commanded surface/Base [mm]:', [round(v, 3) for v in commanded_surface])
        print('Hover target/Base [mm]:', [round(v, 3) for v in target])
        print(f'Placement slot: {target_slot}')
        print(f'Placement long axis: PCB X + {placement_angle_deg:.1f} deg')
        print('Actual carried-part orientation plan:', {
            'current_axis_base_deg': round(orientation_plan['current_axis_base_deg'], 3),
            'slot_axis_base_deg': round(target_axis_base_deg, 3),
            'symmetry_period_deg': orientation_plan['symmetry_period_deg'],
            'rotation_delta_deg': round(rotation_delta, 3),
            'rotation_skipped': skip_rotation,
        })
        print('Target TCP ABC [deg]:', [round(v, 3) for v in target_abc])
        print('Carry invariant: verify pure vertical lift at pick XY before '
              'any wrist rotation or horizontal transfer')
        for index, (pose, speed, label, linear) in enumerate(waypoints, 1):
            print(f'Stage {index}/{len(waypoints)} {label}:', [round(float(v), 3) for v in pose], f'speed={speed}% motion={"MoveL" if linear else "MoveJ"}')
        if not args.execute:
            print('DRY RUN - ROBOT DID NOT MOVE'); return
        if not node.client.wait_for_service(timeout_sec=3): raise RuntimeError('command service unavailable')
        for index, (pose, speed, label, linear) in enumerate(waypoints, 1):
            node.move(pose, speed, f'stage {index}/{len(waypoints)} ({label})', linear)
            print(f'Verified stage {index}/{len(waypoints)} complete ({label})')
        print('Arrived at board target hover. No descent or gripper release was commanded.')
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()


if __name__ == '__main__': main()
