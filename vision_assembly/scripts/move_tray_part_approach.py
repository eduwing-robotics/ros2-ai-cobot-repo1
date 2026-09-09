#!/usr/bin/env python3
"""Move the FR5 TCP to exactly 50 mm above a fresh non-SMD tray target."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node
from scipy.spatial.transform import Rotation

from tray_hover_contract import (
    TrayHoverContractError,
    load_contract,
    normalize_part_type,
    validate_surface_workspace,
)


def symmetric_angle_delta_deg(target_deg, current_deg):
    """Smallest rotation aligning an unoriented rectangular axis."""
    return (target_deg - current_deg + 90.0) % 180.0 - 90.0


def orientation_error_deg(current_abc, target_abc):
    """Geodesic orientation error, independent of equivalent Euler wrapping."""
    current = Rotation.from_euler('xyz', current_abc, degrees=True)
    target = Rotation.from_euler('xyz', target_abc, degrees=True)
    return float(np.degrees((target * current.inv()).magnitude()))


def build_waypoints(
    current,
    target_xyz,
    target_orientation,
    rotation_delta,
    safe_clearance_mm,
    horizontal_speed_percent,
    vertical_speed_percent,
    rotation_speed_percent,
):
    """Build an overhead-only path; this function cannot create a grasp stage."""
    current = np.asarray(current, dtype=float)
    target_xyz = np.asarray(target_xyz, dtype=float)
    orientation = current[3:].tolist()
    safe_z = max(float(current[2]), float(target_xyz[2] + safe_clearance_mm))
    waypoints = []
    if abs(safe_z - float(current[2])) > 0.5:
        waypoints.append((
            [current[0], current[1], safe_z, *orientation],
            vertical_speed_percent,
            'vertical raise',
        ))
    if abs(rotation_delta) > 0.05:
        waypoints.append(
            (
                [current[0], current[1], safe_z, *target_orientation],
                rotation_speed_percent,
                'part-axis alignment',
            )
        )
    waypoints.extend([
        (
            [target_xyz[0], target_xyz[1], safe_z, *target_orientation],
            horizontal_speed_percent,
            'horizontal positioning',
        ),
        (
            [target_xyz[0], target_xyz[1], target_xyz[2], *target_orientation],
            vertical_speed_percent,
            '50 mm hover approach',
        ),
    ])
    return waypoints, safe_z


class TrayApproach(Node):
    def __init__(self):
        super().__init__('move_tray_part_approach')
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
            raise RuntimeError(f'No response to {command}')
        result = str(future.result().cmd_res)
        if result.split(',', 1)[0] != '0':
            raise RuntimeError(f'FR5 rejected {command}: {result}')

    def wait_motion_done(
        self,
        target_pose,
        timeout_sec=45.0,
        position_tolerance_mm=1.5,
        orientation_tolerance_deg=1.0,
    ):
        deadline = time.monotonic() + timeout_sec
        target = np.asarray(target_pose, dtype=float)
        position_error = math.inf
        angle_error = math.inf
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is None:
                continue
            current = np.asarray([
                self.state.cart_x_cur_pos,
                self.state.cart_y_cur_pos,
                self.state.cart_z_cur_pos,
                self.state.cart_a_cur_pos,
                self.state.cart_b_cur_pos,
                self.state.cart_c_cur_pos,
            ], dtype=float)
            position_error = float(np.linalg.norm(current[:3] - target[:3]))
            angle_error = orientation_error_deg(current[3:], target[3:])
            if (
                int(self.state.robot_motion_done) == 1
                and position_error <= position_tolerance_mm
                and angle_error <= orientation_tolerance_deg
            ):
                return
        raise RuntimeError(
            'Robot motion completion/pose verification timeout '
            f'(position={position_error:.3f} mm, orientation={angle_error:.3f} deg)'
        )


def load_target(path, part_type, instance_index, max_age_sec):
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Cannot read detection file: {exc}') from exc
    if payload.get('mode') == 'frozen_tray_part_target':
        if (
            payload.get('part_type') != part_type
            or int(payload.get('instance_index', -1)) != instance_index
        ):
            raise RuntimeError('Frozen target does not match requested part type/instance')
        timestamp = payload.get('timestamp_unix')
        if timestamp is None:
            raise RuntimeError('Frozen target has no timestamp')
        age = time.time() - float(timestamp)
        if age < -5.0 or age > max_age_sec:
            raise RuntimeError(f'Frozen target is stale ({age:.1f} s); capture it again')
        if payload.get('workflow') == 'non_smd_tray_hover_only':
            required = {
                'tray_at_home': True,
                'base_transform_status': 'VALID_COORDINATES_ONLY',
                'coordinate_frame': 'base_link',
                'position_units': 'mm',
                'contact_pick_authorized': False,
            }
            for key, expected in required.items():
                if payload.get(key) != expected:
                    raise RuntimeError(
                        f'Frozen live target {key}={payload.get(key)!r}; expected {expected!r}'
                    )
        xyz = np.asarray(payload.get('part_center_base_mm'), dtype=float)
        if xyz.shape != (3,) or not np.all(np.isfinite(xyz)):
            raise RuntimeError('Frozen target has invalid Base XYZ')
        return payload, {
            'part_type': part_type,
            'instance_index': instance_index,
            'display_name': payload.get('display_name', part_type),
            'long_axis_angle_base_deg': payload.get('long_axis_angle_base_deg'),
        }, xyz
    if not str(payload.get('tray_registration', '')).startswith('TRACKING'):
        raise RuntimeError('Tray is not registered; run tray detection again')
    status = payload.get('base_transform_status')
    if status != 'VALID_COORDINATES_ONLY':
        raise RuntimeError(
            f'Base coordinates are not valid ({status or "missing"}); '
            'start the FR5 state server and detect again'
        )
    timestamp = payload.get('timestamp_unix')
    if timestamp is None:
        raise RuntimeError('Detection file lacks timestamp_unix; rerun the updated tray detector')
    age = time.time() - float(timestamp)
    if age < -5.0 or age > max_age_sec:
        raise RuntimeError(f'Detection file is stale ({age:.1f} s); detect the tray part again')
    matches = [
        item for item in payload.get('stable_detections', [])
        if item.get('part_type') == part_type
        and int(item.get('instance_index', -1)) == instance_index
    ]
    if len(matches) != 1:
        available = [
            f"{item.get('part_type')}#{item.get('instance_index')}"
            for item in payload.get('stable_detections', [])
        ]
        raise RuntimeError(
            f'No unique stable detection for {part_type}#{instance_index}. '
            f'Available: {", ".join(available) or "none"}'
        )
    part = matches[0]
    xyz = np.asarray(part.get('base_xyz_mm'), dtype=float)
    if xyz.shape != (3,) or not np.all(np.isfinite(xyz)):
        raise RuntimeError(f'{part_type}#{instance_index} has invalid Base XYZ')
    return payload, part, xyz


def parse_args(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=root / 'config/tray_hover_5cm.json')
    parser.add_argument(
        '--target-file',
        type=Path,
        default=root / 'data/tray_hover_target_last.json',
    )
    parser.add_argument('--part-type', required=True)
    parser.add_argument('--instance', type=int, default=1, help='1-based live index')
    parser.add_argument('--approach-offset-mm', type=float)
    parser.add_argument('--safe-clearance-mm', type=float)
    parser.add_argument(
        '--speed-percent',
        type=int,
        help='legacy compatibility: sets both horizontal and vertical speed',
    )
    parser.add_argument('--horizontal-speed-percent', type=int)
    parser.add_argument('--vertical-speed-percent', type=int)
    parser.add_argument('--rotation-speed-percent', type=int)
    parser.add_argument(
        '--align-part',
        action='store_true',
        help='legacy opt-in; rectangular parts align automatically',
    )
    parser.add_argument('--gripper-axis', choices=('tool_x', 'tool_y'))
    parser.add_argument('--max-rotation-deg', type=float, default=90.0)
    parser.add_argument('--max-target-age-sec', type=float, default=15.0)
    parser.add_argument('--max-distance-mm', type=float)
    parser.add_argument('--tool-id', type=int)
    parser.add_argument('--user-id', type=int)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-hover-only', action='store_true')
    parser.add_argument(
        '--confirm-move',
        action='store_true',
        help='legacy alias for --confirm-hover-only',
    )
    args = parser.parse_args(argv)
    try:
        contract = load_contract(args.config)
        args.part_type = normalize_part_type(args.part_type, contract)
    except TrayHoverContractError as exc:
        parser.error(str(exc))
    motion = contract['motion']
    args.approach_offset_mm = float(
        args.approach_offset_mm
        if args.approach_offset_mm is not None
        else contract['hover_offset_mm']
    )
    args.safe_clearance_mm = float(
        args.safe_clearance_mm
        if args.safe_clearance_mm is not None
        else motion['safe_clearance_mm']
    )
    args.horizontal_speed_percent = int(
        args.horizontal_speed_percent
        if args.horizontal_speed_percent is not None
        else motion['horizontal_speed_percent']
    )
    args.vertical_speed_percent = int(
        args.vertical_speed_percent
        if args.vertical_speed_percent is not None
        else motion['vertical_speed_percent']
    )
    if args.speed_percent is not None:
        args.horizontal_speed_percent = args.speed_percent
        args.vertical_speed_percent = args.speed_percent
    args.rotation_speed_percent = int(
        args.rotation_speed_percent
        if args.rotation_speed_percent is not None
        else motion['rotation_speed_percent']
    )
    args.max_distance_mm = float(
        args.max_distance_mm
        if args.max_distance_mm is not None
        else motion['maximum_target_distance_mm']
    )
    args.tool_id = int(args.tool_id if args.tool_id is not None else motion['tool_id'])
    args.user_id = int(args.user_id if args.user_id is not None else motion['user_id'])
    profile = contract['parts'][args.part_type]
    if args.gripper_axis is not None and args.gripper_axis != profile['gripper_axis']:
        parser.error(
            f'--gripper-axis is fixed at {profile["gripper_axis"]} for {args.part_type}'
        )
    args.gripper_axis = profile['gripper_axis']
    args.align_part = bool(
        args.align_part or profile['orientation_mode'] == 'long_axis'
    )
    if profile['orientation_mode'] == 'preserve' and args.align_part:
        parser.error(f'{args.part_type} has no stable grasp axis; preserve TCP orientation')
    confirmed = bool(args.confirm_hover_only or args.confirm_move)
    if args.execute != confirmed:
        parser.error(
            'actual motion requires both --execute and --confirm-hover-only '
            '(--confirm-move is a legacy alias)'
        )
    if args.dry_run and args.execute:
        parser.error('--dry-run and --execute cannot be combined')
    if args.instance < 1:
        parser.error('--instance must be at least 1')
    if abs(args.approach_offset_mm - 50.0) > 1e-9:
        parser.error('--approach-offset-mm is fixed at exactly 50 mm')
    if not 75.0 <= args.safe_clearance_mm <= 200.0:
        parser.error('--safe-clearance-mm must be in [75, 200] mm')
    for name in (
        'horizontal_speed_percent',
        'vertical_speed_percent',
        'rotation_speed_percent',
    ):
        speed = getattr(args, name)
        if not 1 <= speed <= 30:
            parser.error(f'--{name.replace("_", "-")} must be 1..30')
    if not 0.0 < args.max_rotation_deg <= 90.0:
        parser.error('--max-rotation-deg must be in (0, 90]')
    if not 0 < args.max_target_age_sec <= 15.0:
        parser.error('--max-target-age-sec must be in (0, 15]')
    if not 0 < args.max_distance_mm <= float(motion['maximum_target_distance_mm']):
        parser.error(
            '--max-distance-mm must be in '
            f'(0, {float(motion["maximum_target_distance_mm"]):g}]'
        )
    if args.tool_id != int(motion['tool_id']) or args.user_id != int(motion['user_id']):
        parser.error('tool/user IDs are fixed by the tray-hover safety contract')
    return args, contract


def main(argv=None):
    args, contract = parse_args(argv)
    payload, part, surface_xyz = load_target(
        args.target_file,
        args.part_type,
        args.instance,
        args.max_target_age_sec,
    )
    try:
        surface_xyz = validate_surface_workspace(surface_xyz, contract)
    except TrayHoverContractError as exc:
        raise RuntimeError(str(exc)) from exc
    recorded_offset = payload.get('hover_offset_mm')
    if recorded_offset is not None and abs(float(recorded_offset) - 50.0) > 1e-9:
        raise RuntimeError('Frozen target was not captured for the fixed 50 mm hover')
    if payload.get('workflow') == 'non_smd_tray_hover_only':
        current_contract_sha256 = hashlib.sha256(args.config.read_bytes()).hexdigest()
        if payload.get('contract_sha256') != current_contract_sha256:
            raise RuntimeError(
                'Tray-hover safety contract changed after target capture; capture again'
            )
    target_xyz = surface_xyz + np.array([0.0, 0.0, 50.0])
    rclpy.init()
    node = TrayApproach()
    try:
        node.wait_state()
        state = node.state
        if int(state.tool_num) != args.tool_id:
            raise RuntimeError(f'Active tool={state.tool_num}; expected Tool {args.tool_id}')
        if int(state.robot_motion_done) != 1:
            raise RuntimeError('Robot is not stationary')
        if (
            int(state.emg) != 0
            or int(state.main_error_code) != 0
            or float(state.collision_err) != 0.0
        ):
            raise RuntimeError('Robot emergency/error/collision state is not clear')
        if args.execute and int(state.robot_mode) != 0:
            raise RuntimeError(f'robot_mode={state.robot_mode}; AUTO mode (0) is required')
        current = np.array([
            state.cart_x_cur_pos,
            state.cart_y_cur_pos,
            state.cart_z_cur_pos,
            state.cart_a_cur_pos,
            state.cart_b_cur_pos,
            state.cart_c_cur_pos,
        ], dtype=float)
        if not np.all(np.isfinite(current)):
            raise RuntimeError('Current TCP pose contains NaN/Inf')
        distance = float(np.linalg.norm(target_xyz - current[:3]))
        if distance > args.max_distance_mm:
            raise RuntimeError(
                f'Target distance {distance:.1f} mm exceeds limit '
                f'{args.max_distance_mm:.1f} mm'
            )
        orientation = current[3:].tolist()
        target_orientation = list(orientation)
        rotation_delta = 0.0
        part_angle = None
        if args.align_part:
            try:
                part_angle = float(part['long_axis_angle_base_deg'])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    'Target has no valid Base-frame long-axis angle; recapture it'
                ) from exc
            if not math.isfinite(part_angle):
                raise RuntimeError('Invalid part angle')
            current_rotation = Rotation.from_euler(
                'xyz', orientation, degrees=True
            ).as_matrix()
            axis_index = 0 if args.gripper_axis == 'tool_x' else 1
            axis_xy = current_rotation[:2, axis_index]
            if np.linalg.norm(axis_xy) < 0.5:
                raise RuntimeError(f'{args.gripper_axis} is nearly vertical')
            current_axis_angle = math.degrees(math.atan2(axis_xy[1], axis_xy[0]))
            rotation_delta = symmetric_angle_delta_deg(part_angle, current_axis_angle)
            if abs(rotation_delta) > args.max_rotation_deg + 1e-6:
                raise RuntimeError(
                    f'Required rotation {rotation_delta:.1f} deg exceeds safety limit'
                )
            target_rotation = (
                Rotation.from_euler('z', rotation_delta, degrees=True).as_matrix()
                @ current_rotation
            )
            target_orientation = Rotation.from_matrix(target_rotation).as_euler(
                'xyz', degrees=True
            ).tolist()
        waypoints, safe_z = build_waypoints(
            current,
            target_xyz,
            target_orientation,
            rotation_delta,
            args.safe_clearance_mm,
            args.horizontal_speed_percent,
            args.vertical_speed_percent,
            args.rotation_speed_percent,
        )
        print('TRAY PART 50 MM HOVER ONLY - no contact descent or gripper command')
        print(
            f'Selected part: {part["part_type"]} #{part["instance_index"]} '
            f'({part["display_name"]})'
        )
        print(
            'Depth/transform basis:',
            payload.get('depth_basis', payload.get('transform_chain', 'not recorded')),
        )
        print('Part surface/Base [mm]:', np.round(surface_xyz, 3).tolist())
        print('Hover offset: Base +Z 50.0 mm (fixed)')
        print('Target TCP/Base [mm]:', np.round(target_xyz, 3).tolist())
        if args.align_part:
            print(f'Part long axis/Base XY: {part_angle:.3f} deg')
            print(
                f'Gripper alignment: {args.gripper_axis}, '
                f'delta={rotation_delta:.3f} deg, '
                f'target ABC={np.round(target_orientation, 3).tolist()}'
            )
        else:
            print(
                'Circular/square part: current TCP ABC preserved:',
                np.round(orientation, 3).tolist(),
            )
        print(f'Target distance: {distance:.1f} mm; safe Z: {safe_z:.1f} mm')
        print(
            f'Speeds: horizontal={args.horizontal_speed_percent}%, '
            f'vertical={args.vertical_speed_percent}%, '
            f'rotation={args.rotation_speed_percent}%'
        )
        for index, (pose, speed, label) in enumerate(waypoints, 1):
            print(
                f'Stage {index}/{len(waypoints)} {label}: '
                f'{np.round(pose, 3).tolist()} speed={speed}%'
            )
        if not args.execute:
            print('DRY RUN - ROBOT AND GRIPPER DID NOT MOVE')
            return 0
        if not node.client.wait_for_service(timeout_sec=3.0):
            raise RuntimeError('/fairino_remote_command_service unavailable')
        global_speed = max(
            args.horizontal_speed_percent,
            args.vertical_speed_percent,
            args.rotation_speed_percent,
        )
        node.command(f'SetSpeed({global_speed})')
        for index, (pose, speed, label) in enumerate(waypoints, 1):
            command = (
                f'MoveCart({pose[0]:.3f},{pose[1]:.3f},{pose[2]:.3f},'
                f'{pose[3]:.3f},{pose[4]:.3f},{pose[5]:.3f},'
                f'{args.tool_id},{args.user_id},{speed},{speed},{speed},-1,-1)'
            )
            print(f'Sending stage {index}/{len(waypoints)} ({label}): {command}')
            node.command(command)
            node.wait_motion_done(pose)
        print(
            'Arrived exactly 50 mm above the part. '
            'No contact descent or gripper action was sent.'
        )
        return 0
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
